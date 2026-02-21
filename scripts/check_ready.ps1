param(
  [string]$BaseUrl = "http://localhost:8000",
  [string]$EnvFile = "CONFIG/local.env"
)

$ErrorActionPreference = "Stop"

function Get-EnvMap([string]$path) {
  $map = @{}
  if (!(Test-Path $path)) { return $map }
  Get-Content $path | ForEach-Object {
    $line = $_.Trim()
    if (!$line -or $line.StartsWith("#")) { return }
    $idx = $line.IndexOf("=")
    if ($idx -gt 0) {
      $k = $line.Substring(0, $idx).Trim()
      $v = $line.Substring($idx + 1).Trim()
      $map[$k] = $v
    }
  }
  return $map
}

Write-Host "Mentorix readiness check starting..."

# 1) Docker service status
Write-Host "`n[1/6] Docker containers"
$required = @("mentorix-api", "mentorix-postgres", "mentorix-redis", "mentorix-frontend")
$supportsJson = $true
try {
  $psJson = docker compose ps --format json 2>$null
  if (-not $psJson) { $supportsJson = $false }
} catch {
  $supportsJson = $false
}

if ($supportsJson) {
  $rows = $psJson | ConvertFrom-Json
  foreach ($svc in $required) {
    $hit = $rows | Where-Object { $_.Name -eq $svc }
    if (-not $hit) { throw "Missing container: $svc" }
    if ($hit.State -notin @("running", "Running")) {
      throw "Container not running: $svc ($($hit.State))"
    }
  }
} else {
  $psText = docker compose ps 2>$null | Out-String
  if (-not $psText.Trim()) { throw "docker compose is unavailable or no services found." }
  foreach ($svc in $required) {
    if ($psText -notmatch [regex]::Escape($svc)) { throw "Missing container: $svc" }
  }
  if ($psText -notmatch "running") {
    throw "Containers are not in running state. Output:`n$psText"
  }
}
Write-Host "Containers running."

# 2) API health
Write-Host "`n[2/6] API health"
$health = Invoke-RestMethod -Method Get -Uri "$BaseUrl/health" -TimeoutSec 8
if ($health.status -ne "ok") {
  throw "API health check failed: $($health | ConvertTo-Json -Depth 5)"
}
Write-Host "API healthy."

# 3) Env validity
Write-Host "`n[3/6] Environment config"
$envMap = Get-EnvMap $EnvFile
if (-not $envMap["GEMINI_API_KEY"]) { throw "GEMINI_API_KEY missing in $EnvFile" }
if (-not $envMap["EMBEDDING_MODEL"]) { throw "EMBEDDING_MODEL missing in $EnvFile" }
if (-not $envMap["OLLAMA_BASE_URL"]) { throw "OLLAMA_BASE_URL missing in $EnvFile" }
Write-Host "Env file looks valid."

# 4) Ollama embeddings endpoint
Write-Host "`n[4/6] Ollama embeddings endpoint"
$ollamaBase = $envMap["OLLAMA_BASE_URL"]
if ($ollamaBase -like "*host.docker.internal*") {
  $ollamaBase = $ollamaBase -replace "host\.docker\.internal", "localhost"
}
$embedPayload = @{
  model = $envMap["EMBEDDING_MODEL"]
  prompt = "Mentorix readiness check"
} | ConvertTo-Json

$embedResp = Invoke-RestMethod -Method Post -Uri "$($ollamaBase.TrimEnd('/'))/api/embeddings" -Body $embedPayload -ContentType "application/json" -TimeoutSec 15
if (-not $embedResp.embedding) { throw "Ollama embedding response missing embedding vector." }
Write-Host "Ollama embedding OK (dim=$($embedResp.embedding.Count))."

# 5) Frontend health
Write-Host "`n[5/6] Frontend health"
$front = Invoke-WebRequest -Method Get -Uri "http://localhost:5500" -TimeoutSec 8
if ($front.StatusCode -ne 200) {
  throw "Frontend health check failed with status code $($front.StatusCode)"
}
Write-Host "Frontend reachable."

# 6) MVP smoke test
Write-Host "`n[6/6] MVP smoke test"
powershell -ExecutionPolicy Bypass -File ".\scripts\test_mvp.ps1" -BaseUrl $BaseUrl | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Smoke test failed." }
Write-Host "Smoke test passed."

Write-Host "`nReadiness check PASSED. System is demo-ready."
