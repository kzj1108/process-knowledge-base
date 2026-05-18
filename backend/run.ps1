# 工艺知识库 API + Web 管理后台
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}
& .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt -q

$env:PKB_DB_PATH = Join-Path $PSScriptRoot "..\database\process_kb.db"
if (-not $env:PKB_API_KEY) { $env:PKB_API_KEY = "pkb-dev-key-change-me" }
if (-not $env:PKB_ADMIN_PASS) { $env:PKB_ADMIN_PASS = "admin123" }

Write-Host ""
Write-Host "  工艺知识库已启动"
Write-Host "  管理后台: http://127.0.0.1:8090/"
Write-Host "  API 文档: http://127.0.0.1:8090/docs"
Write-Host "  账号: admin / $env:PKB_ADMIN_PASS"
Write-Host ""

uvicorn app.main:app --host 0.0.0.0 --port 8090 --reload
