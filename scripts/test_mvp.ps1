param(
  [string]$BaseUrl = "http://localhost:8000",
  [string]$LearnerId = ""
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($LearnerId)) {
  $LearnerId = [guid]::NewGuid().ToString()
}

Write-Host "Running Mentorix MVP smoke test..."
Write-Host "Base URL   : $BaseUrl"
Write-Host "Learner ID : $LearnerId"

try {
  Write-Host "`n[1/4] Health check"
  $health = Invoke-RestMethod -Method Get -Uri "$BaseUrl/health"
  if ($health.status -ne "ok") {
    throw "Health check failed. Response: $($health | ConvertTo-Json -Depth 5)"
  }
  Write-Host "Health OK"

  Write-Host "`n[2/4] Start session"
  $startBody = @{ learner_id = $LearnerId } | ConvertTo-Json
  $start = Invoke-RestMethod -Method Post -Uri "$BaseUrl/start-session" -Body $startBody -ContentType "application/json"
  if (-not $start.session_id) {
    throw "Missing session_id from /start-session response."
  }
  Write-Host "Session started: $($start.session_id)"
  Write-Host "Concept: $($start.concept), Difficulty: $($start.difficulty)"

  Write-Host "`n[3/4] Submit answer"
  $submitBody = @{
    session_id = $start.session_id
    answer = "A learner solves this by applying concept rules step by step and checking the final result."
    response_time = 8.5
  } | ConvertTo-Json
  $submit = Invoke-RestMethod -Method Post -Uri "$BaseUrl/submit-answer" -Body $submitBody -ContentType "application/json"
  if ($null -eq $submit.score) {
    throw "Missing score from /submit-answer response."
  }
  Write-Host "Score: $($submit.score), Error Type: $($submit.error_type)"

  Write-Host "`n[4/4] Dashboard"
  $dash = Invoke-RestMethod -Method Get -Uri "$BaseUrl/dashboard/$LearnerId"
  if (-not $dash.mastery_map) {
    throw "Missing mastery_map from /dashboard response."
  }
  Write-Host "Dashboard OK. Weak Areas: $($dash.weak_areas -join ', ')"

  Write-Host "`nSmoke test PASSED."
  Write-Host "`nSummary:"
  [PSCustomObject]@{
    learner_id = $LearnerId
    session_id = $start.session_id
    concept = $start.concept
    score = $submit.score
    error_type = $submit.error_type
    weak_areas = ($dash.weak_areas -join ", ")
  } | Format-List
}
catch {
  Write-Error "`nSmoke test FAILED: $($_.Exception.Message)"
  exit 1
}
