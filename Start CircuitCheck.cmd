@echo off
setlocal
cd /d "%~dp0"
title CircuitCheck local server
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start.ps1"
if errorlevel 1 (
  echo.
  echo CircuitCheck could not start. Review the error above.
  pause
)
endlocal
