param(
  [string]$ComposeService = "api",
  [string]$BaseUrl = "http://localhost:8000"
)

$ErrorActionPreference = "Stop"

Write-Host "Running FULL regression profile (docker + smoke)..."

docker compose exec -T $ComposeService python -m pytest tests -q
if ($LASTEXITCODE -ne 0) {
  throw "Full pytest profile failed."
}

powershell -ExecutionPolicy Bypass -File ".\\scripts\\test_mvp.ps1" -BaseUrl $BaseUrl
if ($LASTEXITCODE -ne 0) {
  throw "UI journey smoke failed."
}

Write-Host "FULL profile passed."
