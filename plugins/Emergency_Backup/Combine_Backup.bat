@echo off
setlocal
cd /d "%~dp0"
echo Emergency Backup - join parts in this folder
echo.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0Combine_Backup.ps1"
if errorlevel 1 (
  echo.
  echo ERROR: Backup could not be combined. Original parts are untouched.
  pause
  exit /b 1
)
echo.
echo Backup image is ready.
pause
