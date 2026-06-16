@echo off
cd /d "%~dp0backend"
start "ProcessKB" cmd /k "%~dp0backend\start.bat"
timeout /t 4 /nobreak >nul
start http://127.0.0.1:8090/
