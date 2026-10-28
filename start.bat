@echo off
cd /d "%~dp0"
if "%PORT%"=="" set PORT=8000
start "" cmd /c "timeout /t 2 /nobreak >nul & start http://localhost:%PORT%/admin"
python server.py
pause
