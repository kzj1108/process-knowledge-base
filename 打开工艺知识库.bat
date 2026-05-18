@echo off
cd /d "%~dp0backend"
start "ProcessKB" cmd /k "%~dp0backend\启动.bat"
timeout /t 4 /nobreak >nul
start http://127.0.0.1:8090/
