@echo off
rem Restarts Archeion: runs stop.bat's shutdown (clean Ctrl+C first, kill only if needed),
rem then start.bat's start. Doesn't start again if something couldn't be stopped.
rem Works from any folder.
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\stop.ps1"
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
    echo Not starting again, because Archeion isn't fully stopped.
    pause
    endlocal & exit /b %RC%
)
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\start.ps1"
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" pause
endlocal & exit /b %RC%
