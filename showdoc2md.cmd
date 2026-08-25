@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [ShowDoc2MD] 未找到 .venv，请先运行：
  echo powershell -ExecutionPolicy Bypass -File .\scripts\windows_install.ps1
  exit /b 1
)

".venv\Scripts\python.exe" -m showdoc2md %*
exit /b %errorlevel%
