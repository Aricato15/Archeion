@echo off
rem Starts Archeion: the backend and the frontend dev server, each in its own window.
rem Works from any folder. Refuses to start until an admin password is set.
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\start.ps1"
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" pause
endlocal & exit /b %RC%
