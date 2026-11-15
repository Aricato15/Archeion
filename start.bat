@echo off
rem Starts Archeion: the backend and the frontend dev server, each in its own window.
rem Works from any folder. On a fresh start the viewer asks you to create the admin password.
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\start.ps1"
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" pause
endlocal & exit /b %RC%
