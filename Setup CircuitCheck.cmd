@echo off
setlocal
cd /d "%~dp0"
title CircuitCheck first-time setup
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup.ps1"
if errorlevel 1 (
  echo.
  echo Setup could not finish. Review the error above.
  pause
  exit /b 1
)
echo.
echo Setup complete. Double-click Start CircuitCheck.cmd to open CircuitCheck.
pause
endlocal
