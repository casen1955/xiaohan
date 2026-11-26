# 关闭微信 3.9 自动更新（仅旧路线 WeChatFerry / 微信 3.9 需要）
# 用法：右键「使用 PowerShell 运行」（会弹 UAC）
# 原理：把 WeChatUpdate.exe / WeChatUpdate.bin 改名成 .orig，再建同名空目录占位，
#       微信想更新时写不进去就放弃了。
# 微信 4.x 走界面自动化，不需要这个脚本。

$ErrorActionPreference = "Stop"
# 版本子目录按自己机器调整（注意路径里有方括号，必须用 -LiteralPath）
$dir = "C:\Program Files\Tencent\WeChat\[3.9.12.17]"

foreach ($name in @("WeChatUpdate.exe", "WeChatUpdate.bin")) {
    $p = Join-Path $dir $name
    if (Test-Path -LiteralPath $p -PathType Leaf) {
        Move-Item -LiteralPath $p -Destination "$p.orig" -Force
    }
    if (-not (Test-Path -LiteralPath $p)) {
        New-Item -ItemType Directory -Path $p -Force | Out-Null
    }
}

Get-ChildItem -LiteralPath $dir -Filter "WeChatUpdate*" | Select-Object Name, Mode
