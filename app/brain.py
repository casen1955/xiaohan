"""大脑：拼上下文、调模型、决定说不说。"""

from __future__ import annotations

import time

from . import policy
from .memory import Memory
from .model import LLM
from .persona import Persona


class Brain:
    def __init__(self, cfg: dict, memory: Memory, persona: Persona, llm: LLM,
                 stickers=None):
        self.cfg = cfg
        self.memory = memory
        self.persona = persona
        self.llm = llm
        self.stickers = stickers
        self.self_name = "我"

    def _life_note(self, now: float) -> str:
        """今天的状态（一天一次，落 kv）。"""
        try:
            from . import life
            return life.state_note(life.daily(self.memory, self.llm, now=now))
        except Exception:
            return ""

    def _hot_note(self, now: float) -> str:
        """这会儿网上在聊什么（两小时一刷，缓存兜底）。"""
        try:
            from . import hot
            return hot.note(self.memory, now)
        except Exception:
            return ""

    def _sticker_labels(self) -> list[str]:
        try:
            return self.stickers.captions() if self.stickers else []
        except Exception:  # noqa: BLE001
            return []

    # ---------- 上下文 ----------

    def _history_lines(self, chat_id: str, is_group: bool, limit: int = 24,
                       drop_last_user: bool = True) -> list[str]:
        rows = self.memory.recent(chat_id, limit)
        # 最后一条 user 就是当前这条消息，别在上下文里重复一次
        if drop_last_user and rows and rows[-1]["role"] == "user":
            rows = rows[:-1]
        lines = []
        for row in rows:
            if row["role"] == "assistant":
                lines.append(f"我：{row['content']}")
            else:
                name = row["sender_name"] or "对方"
                if is_group:
                    lines.append(f"{name}：{row['content']}")
                else:
                    lines.append(f"{name}：{row['content']}")
        return lines

    def _history_messages(self, chat_id: str, is_group: bool, limit: int = 24,
                          drop_last_user: bool = True,
                          peer_name: str = "") -> list[dict]:
        """历史按真正的对话轮次给模型：assistant 是她说的话，user 是对方说的话。

        以前是用「我：…／哥哥：…」拼成一大段，模型会分不清谁是「我」、谁是「他」，
        出现「哥他刚才说…」这种人称呼乱。改成标准多轮消息后这个歧义就没了。
        """
        rows = self.memory.recent(chat_id, limit)
        if drop_last_user and rows and rows[-1]["role"] == "user":
            rows = rows[:-1]
        out: list[dict] = []
        for row in rows:
            content = (row["content"] or "").strip()
            if not content:
                continue
            if row["role"] == "assistant":
                role = "assistant"
            else:
                role = "user"
                name = (row["sender_name"] or "").strip()
                # 群聊必须带说话人；私聊也带一句（对方的名字），
                # 否则模型容易把眼前这个人当成别人（比如把姐姐当成哥）
                if is_group and name:
                    content = f"{name}：{content}"
                elif peer_name:
                    content = f"{peer_name}：{content}"
            if out and out[-1]["role"] == role:
                out[-1]["content"] += "\n" + content
            else:
                out.append({"role": role, "content": content})
        return out

    def _stage(self, contact: dict | None, chat_id: str, now: float) -> str:
        """情感过渡：stranger（刚加）→ familiar（眼熟）→ close（熟人）。

        判据：有备注/关系 = 直接熟人；否则看聊过多少句、认识多少天。
        """
        if contact and ((contact.get("relation") or "").strip()
                        or (contact.get("note") or "").strip()):
            return "close"
        try:
            n, first = self.memory.chat_stats(chat_id)
        except Exception:
            return "stranger"
        days = 0.0 if not first else max(0.0, (now - first) / 86400.0)
        if n >= 40 and days >= 3:
            return "close"
        if n >= 6 or days >= 1:
            return "familiar"
        return "stranger"

    _ELDER_WORDS = ("爸爸", "妈妈", "爸", "妈", "老师", "长辈", "爷爷", "奶奶",
                    "姥姥", "姥爷", "叔叔", "阿姨", "领导")

    def _is_close_friend(self, contact: dict | None, chat_name: str) -> bool:
        """熟人=有备注的人，且不是长辈/老师。只有熟人才允许开荤。"""
        if not contact:
            return False
        label = (contact.get("name") or "") + (chat_name or "")
        if any(w in label for w in self._ELDER_WORDS):
            return False
        return bool((contact.get("relation") or "").strip()
                    or (contact.get("note") or "").strip())

    def _facts(self, contact_wxid: str | None, chat_id: str) -> list[dict]:
        scopes = ["global"]
        if contact_wxid:
            scopes.append(f"contact:{contact_wxid}")
        scopes.append(f"chat:{chat_id}")
        return self.memory.facts(scopes)

    # ---------- 回复 ----------

    def respond(self, *, chat_id: str, chat_name: str, is_group: bool,
                group_name: str, peers: list[str], contact_wxid: str | None,
                user_name: str, text: str, is_mentioned: bool,
                now: float | None = None, correction: str = "") -> list[str]:
        now = now or time.time()
        contact = self.memory.contact(contact_wxid) if contact_wxid else None
        system = self.persona.build_system_prompt(
            now=now, chat_name=chat_name, is_group=is_group, peers=peers,
            facts=self._facts(contact_wxid, chat_id), contact=contact,
            group_name=group_name, sticker_labels=self._sticker_labels(),
            life_note=self._life_note(now), hot_note=self._hot_note(now),
            stranger=(not is_group and not ((contact or {}).get("relation")
                                            or (contact or {}).get("note"))),
            close_friend=(not is_group and self._is_close_friend(contact, chat_name)),
            stage=self._stage(contact, chat_id, now),
        )
        if correction:
            system += (
                "\n\n【刚刚对方纠正了你】" + correction +
                "。这一次先顺着改（「好 我记住了」这种），别辩解、别反问，"
                "然后自然接着聊。这条已经记进你的记忆了，以后都按新的来。"
            )
        messages = [{"role": "system", "content": system}]
        messages.extend(self._history_messages(chat_id, is_group, limit=14,
                                               peer_name=chat_name))
        tail = text if not is_group else f"{user_name}：{text}（这条 @ 了你）" if is_mentioned else f"{user_name}：{text}"
        try:
            from . import emoji as emoji_mod

            note = emoji_mod.note(text)
            if note:
                tail = f"{tail}\n{note}"
        except Exception:  # noqa: BLE001
            pass
        messages.append({"role": "user", "content": tail})
        messages[0]["content"] += (
            "\n\n【这一轮只回最后这一条】" + ("（" + user_name + "）" if is_group else "")
            + "说的话。先把最后这条读懂：他在说谁、在问什么、是真问还是要吐槽。"
            "别去接更早的话题，别把上一条的问题再答一遍；"
            "实在没看懂就先问一句「你是指…吧」，别硬答。"
        )

        raw = self.llm.chat(
            messages,
            temperature=self.cfg["model"].get("temperature", 1.1),
            max_tokens=self.cfg["model"].get("max_tokens", 700),
        )
        raw = self._resolve_searches(raw, messages)

        # 跑题自检：问句和回答一个词都不沾，就让它重看一遍这条消息再答
        if raw and not raw.strip().upper().startswith(policy.SKIP_TOKEN):
            try:
                from . import policy as _pol

                if _pol.looks_like_question(text) and self._looks_offtopic(text, raw):
                    retry = [dict(m) for m in messages]
                    retry[0]["content"] += (
                        "\n\n【注意】你上一条回答跑题了。重新看最后这条："
                        + text + "。直接针对这句话回答，一两句就够。"
                    )
                    again = self.llm.chat(
                        retry,
                        temperature=self.cfg["model"].get("temperature", 1.1),
                        max_tokens=self.cfg["model"].get("max_tokens", 700),
                    )
                    if again and not again.strip().upper().startswith(policy.SKIP_TOKEN):
                        print(f"[答非所问自检] 重答：{text[:20]}", flush=True)
                        raw = self._resolve_searches(again, retry)
            except Exception as exc:  # noqa: BLE001
                print(f"[答非所问自检] 跳过：{exc}", flush=True)

        if not raw or raw.strip().upper().startswith(policy.SKIP_TOKEN):
            return []
        cfg_bubbles = self.cfg["limits"]["bubbles"].get("max", 3)
        return policy.split_bubbles(raw, cfg_bubbles)

    @staticmethod
    def _bigrams(text: str) -> set[str]:
        s = "".join(ch for ch in (text or "") if "\u4e00" <= ch <= "\u9fff"
                    or ch.isalnum())
        return {s[i:i + 2] for i in range(len(s) - 1)}

    def _looks_offtopic(self, question: str, reply: str) -> bool:
        """粗判：问句和回答完全没有共同的词，就认为可能答偏了。"""
        if not question or not reply:
            return False
        q = self._bigrams(question)
        r = self._bigrams(reply)
        if not q or not r:
            return False
        return len(q & r) == 0

    def _resolve_searches(self, raw: str | None, messages: list[dict]) -> str | None:
        """她要是写了 [搜:xxx]，替她搜完再让她说一遍。"""
        if not raw:
            return raw
        wants = policy.RESOURCE_RE.findall(raw)[:2]
        if wants:
            return self._resolve_resources(raw, messages, wants)
        # 她没写标签，但对方明显在要资源/教程 → 替她兜底搜一次
        ask = (messages[-1].get("content") or "") if messages else ""
        if policy.RESOURCE_ASK_RE.search(ask) and len(ask) < 80:
            return self._resolve_resources(raw, messages, [ask.strip()[:40]])
        queries = policy.SEARCH_RE.findall(raw)[:2]
        if not queries:
            return raw
        try:
            from . import websearch
        except Exception:  # noqa: BLE001
            return policy.SEARCH_RE.sub("", raw).strip()
        notes = []
        for q in queries:
            try:
                notes.append(websearch.query(q, n=4, with_url=True))
            except Exception:  # noqa: BLE001
                notes.append(f"（搜「{q}」失败了）")
        messages.append({"role": "assistant", "content": raw})
        messages.append({
            "role": "user",
            "content": "（系统：你刚查到这些资料，用你自己的话说给对方听。"
                       "如果是学术、技术、课程、论文这类正事：把要点讲清楚（两三句），"
                       "最后可以甩一个最有用的链接给对方，让他自己去看；"
                       "如果是闲聊八卦，就别念链接、别提「搜索」，挑能用的讲两句。）\n"
                       + "\n".join(n for n in notes if n),
        })
        try:
            again = self.llm.chat(
                messages,
                temperature=self.cfg["model"].get("temperature", 1.1),
                max_tokens=self.cfg["model"].get("max_tokens", 700),
            )
        except Exception:  # noqa: BLE001
            again = None
        if again:
            return policy.SEARCH_RE.sub("", again).strip()
        return policy.SEARCH_RE.sub("", raw).strip()

    def _resolve_resources(self, raw: str, messages: list[dict], wants: list[str]) -> str:
        """她写了 [资源:xxx]：去 GitHub / 官网捞真链接，再让她用自己的话说。"""
        try:
            from . import websearch
        except Exception:  # noqa: BLE001
            return policy.RESOURCE_RE.sub("", raw).strip()
        found = []
        for q in wants:
            try:
                got = websearch.resources(q, n=4)
            except Exception:  # noqa: BLE001
                got = ""
            found.append(f"【{q}】\n{got or '（没找到干净的官方链接）'}")
        messages.append({"role": "assistant", "content": raw})
        messages.append({
            "role": "user",
            "content": "（系统：你刚替对方找过资源链接。用你自己的话说——"
                       "1) 先一句「找到这个」；2) 从下面挑**最多两条**，把 URL 一字不改地原样贴出来"
                       "（就在下面那些以 http 开头的串，别改写、别加书名号），每条后面半句话说明是什么；"
                       "3) 提醒一句「链接你自己点开看，我不点陌生链接的」。"
                       "**不许编链接、不许自己造 URL**；下面没有 http 链接时，就直接说没找到干净的，别硬凑。\n"
                       + "\n".join(found),
        })
        try:
            again = self.llm.chat(
                messages,
                temperature=self.cfg["model"].get("temperature", 1.1),
                max_tokens=self.cfg["model"].get("max_tokens", 700),
            )
        except Exception:  # noqa: BLE001
            again = None
        return policy.RESOURCE_RE.sub("", (again or raw)).strip()

    # ---------- 主动开口 ----------

    def proactive(self, *, contact_wxid: str, chat_name: str, kind: str, hint: str = "",
                  now: float | None = None) -> list[str]:
        """kind: morning / night / miss / share"""
        now = now or time.time()
        contact = self.memory.contact(contact_wxid)
        system = self.persona.build_system_prompt(
            now=now, chat_name=chat_name, is_group=False, peers=[],
            facts=self._facts(contact_wxid, f"p:{contact_wxid}"), contact=contact,
            sticker_labels=self._sticker_labels(), life_note=self._life_note(now),
            hot_note=self._hot_note(now),
        )
        cue = {
            "morning": "现在是早上，你想主动跟哥说句话。像刚醒过来那样，别太正式。",
            "night": "现在挺晚了，你想提醒他早点睡，顺嘴聊两句。",
            "miss": "你有几天没跟他说话了，有点想他，主动发一条。别显得黏人。",
            "share": "你刚做完一件小事（画完画、听到一首歌、看到好笑的图），想分享给他。",
            "callback": f"你昨天听他说起「{hint}」，今天忽然又想起来，主动补一句——像‘你说的那个我后来想了下’。",
            "browse": (f"你刚才在网上瞎逛，{hint}，觉得有点意思，想随手发给他一句。"
                       "别像推荐位、别介绍平台，就用你自己的话说一句你看到啥、你咋想的，"
                       "他愿意接就聊，不接就算了。"),
            "promise": (f"你之前跟他说过「{hint}」，现在到时候了。"
                        "像忽然想起来那样提一句（别像闹钟、别说「提醒您」），"
                        "顺口、轻快，最多两条。"),
        }.get(kind, "你想主动说句话。")

        messages = [{"role": "system", "content": system}]
        messages.extend(self._history_messages(contact_wxid, False, 12))
        messages.append({"role": "user", "content": f"（系统提示：{cue} 直接写出你要发的话，最多 2 条，用 ||| 分隔。）"})

        raw = self.llm.chat(messages, temperature=1.25,
                            max_tokens=self.cfg["model"].get("max_tokens", 500))
        if not raw or raw.strip().upper().startswith(policy.SKIP_TOKEN):
            return []
        return policy.split_bubbles(raw, 2)

    def moment_caption(self, now: float | None = None, hint: str = "") -> str:
        """给朋友圈写一句配文（她自己的口吻，短）。"""
        now = now or time.time()
        system = self.persona.build_system_prompt(
            now=now, chat_name="朋友圈", is_group=False, peers=[],
            facts=[], contact=None, sticker_labels=self._sticker_labels(),
            life_note=self._life_note(now), hot_note=self._hot_note(now),
        )
        cue = hint or "你今天想发条朋友圈，配一张自己画的图。写配文。"
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": (
                f"（系统提示：{cue} 只写配文本身，一到两句，"
                "不超过 40 字，不要引号，不要表情包标签，不要解释。）"
            )},
        ]
        raw = self.llm.chat(messages, temperature=1.3, max_tokens=200) or ""
        raw = raw.strip().strip('"').strip("“”")
        raw = raw.replace("|||", " ").replace("\n", " ")
        return raw[:80]

    # ---------- 记忆沉淀 ----------

    def remember(self, *, chat_id: str, chat_name: str, is_group: bool,
                 contact_wxid: str | None = None, limit: int = 40) -> int:
        """把最近这段聊天里值得记住的东西，写成一条条事实存进库。

        返回写入/更新的条数。失败静默（记忆是加分项，不该拖垮聊天）。
        """
        rows = self.memory.recent(chat_id, limit)
        if len(rows) < 8:
            return 0
        convo = []
        for row in rows:
            who = "我" if row["role"] == "assistant" else (row["sender_name"] or "对方")
            convo.append(f"{who}：{row['content']}")
        scope = f"contact:{contact_wxid}" if contact_wxid else f"chat:{chat_id}"
        known = self.memory.facts([scope])
        known_txt = "\n".join(f"- {f['k']}：{f['v']}" for f in known) or "（没有）"
        if is_group:
            head = (
                "下面是你在群里的一段聊天记录（接话的可能是好几个人），"
                "以及你已经记住的东西。\n\n"
                f"【已经记住的】\n{known_txt}\n\n"
                f"【这段聊天】\n" + "\n".join(convo) + "\n\n"
                "请提炼出关于**群里这些人**的稳定信息：谁是谁、怎么称呼、在做什么、"
                "脾气口味偏好、最近在意的事、群里的梗或约定、有没有人拜托过什么事。\n"
                "只写确实出现过的，不要编、不要写你自己的事；分不清是谁的就别写。\n"
                "键优先用这些：称呼、身份、近况、喜好、雷区、约定、事件、原话。\n"
                "「事件」要带时间点（如「11-25 说要去面试」）；"
                "「原话」挑一句他说过、以后能拿来打趣或接梗的原句（照抄，别改写）。\n"
                "输出格式：每行一条 `发言人｜键：值`，发言人写他在这段聊天里的名字，"
                "值一句话，不超过 40 字。最多 8 条。没有值得记的就输出 NONE。"
            )
        else:
            head = (
                "下面是你和这个人的一段聊天记录，以及你已经记住的东西。\n\n"
                f"【已经记住的】\n{known_txt}\n\n"
                f"【这段聊天】\n" + "\n".join(convo) + "\n\n"
                "请提炼出关于**这个人**的、以后聊天用得上的东西：他是谁、怎么称呼、"
                "在做什么、脾气口味喜好、最近在意的事、你们之间的梗或约定、"
                "有没有答应过他什么、有没有他说过的关键一句。\n"
                "只写确实出现过的，不要编、不要写你自己的事；已经记住的别重复。\n"
                "键优先用这些：称呼、身份、近况、喜好、雷区、约定、事件、原话。\n"
                "「事件」要带时间点（如「11-25 说下周要交论文」）；"
                "「原话」挑一句他说过、以后能拿来打趣或接梗的原句（照抄，别改写）。\n"
                "输出格式：每行一条 `键：值`，值一句话，不超过 40 字。"
                "最多 8 条。没有值得记的就输出 NONE。"
            )
        prompt = head
        try:
            raw = self.llm.chat(
                [{"role": "user", "content": prompt}],
                temperature=0.2, max_tokens=400,
            )
        except Exception:  # noqa: BLE001
            return 0
        if not raw:
            return 0
        raw = raw.strip()
        if raw.upper().startswith("NONE"):
            return 0
        n = 0
        by_name = {}
        for c in self.memory.contacts():
            key_name = (c.get("name") or "").strip()
            wxid = str(c.get("wxid") or "").strip()
            # 只认「wxid 不是名字本身」的正式档案，占位档（wxid 就是"韩硕"这种）跳过
            if key_name and wxid and wxid != key_name:
                by_name[key_name] = wxid
        # 私聊时：如果这条 chat_id 只是名字（不是 wxid），尽量找回到真 wxid 档案
        if not is_group and not contact_wxid:
            contact_wxid = by_name.get((chat_name or "").strip())
            if contact_wxid:
                scope = f"contact:{contact_wxid}"
        for line in raw.splitlines():
            line = line.strip().lstrip("-•* ")
            # 「发言人｜键：值」：把关于某个人的印象记到他自己的档案上，
            # 这样群聊里听到的事，私聊时她也认得出来（群记忆 ↔ 私聊记忆打通）
            if "｜" in line or ("|" in line and not line.startswith("http")):
                speaker, rest = line.replace("|", "｜").split("｜", 1)
                speaker = speaker.strip()
                wxid = by_name.get(speaker)
                if wxid:
                    target_scope = f"contact:{wxid}"
                    line = rest
                elif is_group:
                    continue
            else:
                target_scope = scope
            line = line.replace("：", ":", 1)
            if ":" not in line:
                continue
            k, v = line.split(":", 1)
            k, v = k.strip()[:20], v.strip()[:120]
            if not k or not v:
                continue
            self.memory.set_fact(target_scope, k, v)
            n += 1
        return n
