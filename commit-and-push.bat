@echo off
cd /d "%~dp0"

git add backend/app/main.py
git add backend/app/services/process_sheet.py
git add backend/app/services/drawing_annotation.py
git add backend/app/static/app-extra.js
git add backend/app/static/index.html
git add backend/app/static/styles.css
git add backend/start.bat
git add "backend/启动.bat"
git add push-github.bat
git add "打开工艺知识库.bat"

git restore backend/app/__pycache__/main.cpython-38.pyc 2>nul

git commit -m "feat: process sheet with plan view, datums and surface roughness"

echo.
git status -sb
echo.
echo Pushing to GitHub...
git push origin main
if %ERRORLEVEL% NEQ 0 (
  echo.
  echo Push failed. Try VPN then run this bat again, or:
  echo   git -c http.version=HTTP/1.1 push origin main
)
pause
