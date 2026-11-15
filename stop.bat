@echo off
rem Stops Archeion: asks the backend and frontend to shut down cleanly (Ctrl+C), kills them
rem only if they don't, closes the windows start.bat opened, and checks both ports are free.
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\stop.ps1"
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" pause
endlocal & exit /b %RC%
