@echo off
rem Creates or edits .env interactively: prompts for each setting in scripts\settings.schema.json
rem (Enter keeps the current value), validates it, and writes .env (gitignored). It also
rem regenerates .env.example from the schema. Works from any folder.
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\configure.ps1" %*
pause
endlocal
