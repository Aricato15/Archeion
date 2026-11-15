@echo off
rem Installs the backend venv (app\backend\venv) and the frontend node_modules. Run once per clone,
rem and again after pulling dependency changes.
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\setup.ps1"
pause
endlocal
