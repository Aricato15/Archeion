@echo off
rem Sets or changes the admin password. The input is hidden, only a salted scrypt hash is stored
rem (in the backend database), and every logged-in session is logged out.
setlocal
cd /d "%~dp0app\backend"
if not exist "venv\Scripts\python.exe" (
  echo The backend environment is missing. Run setup.bat first.
  pause
  exit /b 1
)
"venv\Scripts\python.exe" -m app password set
pause
endlocal
