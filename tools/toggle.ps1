# 小涵 开关 —— 一键开/关（Windows）
# 用法：右键 -> 使用 PowerShell 运行；或做成快捷方式：
#   powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File toggle.ps1
# 注意：本文件必须保存成 UTF-8 with BOM，否则 Windows PowerShell 5.1 会把中文注释读坏。

$ErrorActionPreference = "Stop"

# 项目根目录 = 本脚本所在目录的上一级（tools 的父目录）
$root = Split-Path -Parent $PSScriptRoot

# 读 config.json 里的 client 段；没配就按下面的默认值猜
$cfgPath = Join-Path $root "config.json"
$cfg = Get-Content $cfgPath -Raw -Encoding UTF8 | ConvertFrom-Json
$py = $cfg.client.python
if (-not $py) { $py = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source }
if (-not $py) { $py = (Get-Command python.exe -ErrorAction SilentlyContinue).Source }
$wxExe = $cfg.client.exe
$wxProc = $cfg.client.process
if (-not $wxProc) { $wxProc = "Weixin" }

function Get-XiaohanProcs {
    Get-CimInstance Win32_Process |
        Where-Object { $_.Name -in @("python.exe", "pythonw.exe") -and $_.CommandLine -like "*app.main*" }
}

$procs = Get-XiaohanProcs
if ($procs) {
    $procs | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    "$(Get-Date -Format 'HH:mm:ss') 已关闭（pid $($procs.ProcessId -join ',')）" |
        Tee-Object -FilePath (Join-Path $root "data\toggle.log") -Append
    exit 0
}

if ($wxExe -and $wxProc) {
    $running = Get-CimInstance Win32_Process | Where-Object { $_.Name -like "$wxProc*" }
    if (-not $running -and (Test-Path $wxExe)) {
        Start-Process -FilePath $wxExe
        Start-Sleep -Seconds 28   # 等微信自动登录
    }
}

Start-Process -FilePath $py -ArgumentList "-m", "app.main", "--wx4" -WorkingDirectory $root -WindowStyle Hidden
Start-Sleep -Seconds 3
$now = Get-XiaohanProcs
"$(Get-Date -Format 'HH:mm:ss') 已启动（pid $($now.ProcessId -join ',')）" |
    Tee-Object -FilePath (Join-Path $root "data\toggle.log") -Append
