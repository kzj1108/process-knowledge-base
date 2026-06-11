@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Creating venv...
    python -m venv .venv
    call .venv\Scripts\pip install -r requirements.txt -q
)

set PKB_DB_PATH=%~dp0..\database\process_kb.db
set PKB_API_KEY=pkb-dev-key-change-me
set PKB_ADMIN_PASS=admin123

echo.
echo ========================================
echo   Process Knowledge Base is running
echo   URL:  http://127.0.0.1:8090/
echo   User: admin   Pass: admin123
echo ========================================
echo.

for /f "tokens=2 delims=:" %%i in ('ipconfig ^| findstr /c:"IPv4"') do (
    echo LAN: http://%%i:8090/
    goto :done_ip
)
:done_ip
echo.

.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8090
pause
