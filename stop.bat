@echo off
rem Stops the Archeion backend and frontend by port (from .env, or 20300/20301).
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\stop.ps1"
endlocal
