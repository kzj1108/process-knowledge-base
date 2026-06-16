@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo   Push to GitHub (for Render deploy)
echo ========================================
echo.

git status -sb
echo.

echo Trying: git push origin main
git push origin main
if %ERRORLEVEL% EQU 0 goto :ok

echo.
echo Push failed. Common fixes:
echo   1. Turn on VPN, then run this bat again
echo   2. Or use GitHub Desktop to push
echo   3. Or set proxy (if you have one):
echo        git config --global http.proxy http://127.0.0.1:7890
echo        git config --global https.proxy http://127.0.0.1:7890
echo   4. Or switch to SSH:
echo        git remote set-url origin git@github.com:kzj1108/process-knowledge-base.git
echo        git push origin main
echo.
pause
exit /b 1

:ok
echo.
echo Push OK. Open Render and click Manual Deploy.
pause
