param(
  [string]$ComposeService = "api"
)

$ErrorActionPreference = "Stop"

Write-Host "Running FAST regression profile (docker)..."
docker compose exec -T $ComposeService python -m pytest `
  tests/test_chapter_progression.py `
  tests/test_threshold_logic.py `
  tests/test_iteration11_smoke.py `
  -q

if ($LASTEXITCODE -ne 0) {
  throw "FAST profile failed."
}

Write-Host "FAST profile passed."
