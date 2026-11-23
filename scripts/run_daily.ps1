# hintdle 每日自动同步（计划任务入口）
# 用法: powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_daily.ps1
# 动作: 校验 poople.io 数据 -> 必要时重建词图 -> 重新构建静态站（只到 dist/，不部署）
# 日志: data\daily\run.log（追加）
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$logDir = Join-Path $root 'data\daily'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir 'run.log'

"[$(Get-Date -Format s)] ===== run_daily start =====" | Add-Content -Path $log -Encoding utf8

& python (Join-Path $PSScriptRoot 'daily_sync.py') *>&1 | Tee-Object -FilePath $log -Append
$code = $LASTEXITCODE

"[$(Get-Date -Format s)] ===== run_daily exit=$code =====" | Add-Content -Path $log -Encoding utf8
exit $code
