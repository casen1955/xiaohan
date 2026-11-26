@echo off
chcp 65001 >nul
cd /d "%~dp0"
if "%1"=="" (
  python -m app.main --mock
) else (
  python -m app.main %*
)
pause
