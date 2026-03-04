param(
  [string]$BaseUrl = "http://localhost:8000"
)

$ErrorActionPreference = "Stop"

$stamp = [int64]([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds())
$username = "mvp_smoke_$stamp"
$password = "testpass123"
$email = "mvp_smoke_$stamp@example.com"

Write-Host "Running Mentorix MVP smoke test..."
Write-Host "Base URL   : $BaseUrl"
Write-Host "Username   : $username"

try {
  Write-Host "`n[1/8] Health check"
  $health = Invoke-RestMethod -Method Get -Uri "$BaseUrl/health"
  if ($health.status -ne "ok") {
    throw "Health check failed. Response: $($health | ConvertTo-Json -Depth 5)"
  }
  Write-Host "Health OK"

  Write-Host "`n[2/8] Start signup"
  $signupStartBody = @{
    username = $username
    password = $password
    name = "MVP Smoke Student"
    date_of_birth = "2010-06-15"
    student_email = $email
    selected_timeline_weeks = 14
    math_9_percent = 68
  } | ConvertTo-Json
  $signupStart = Invoke-RestMethod -Method Post -Uri "$BaseUrl/auth/start-signup" -Body $signupStartBody -ContentType "application/json"
  if (-not $signupStart.signup_draft_id) {
    throw "Missing signup_draft_id from /auth/start-signup response."
  }
  Write-Host "Signup draft created."

  Write-Host "`n[3/8] Get diagnostic questions"
  $diagBody = @{ signup_draft_id = $signupStart.signup_draft_id } | ConvertTo-Json
  $diag = Invoke-RestMethod -Method Post -Uri "$BaseUrl/onboarding/diagnostic-questions" -Body $diagBody -ContentType "application/json"
  if (-not $diag.questions) {
    throw "Diagnostic questions not returned."
  }
  Write-Host "Diagnostic questions received: $($diag.questions.Count)"

  Write-Host "`n[4/8] Submit onboarding"
  $answers = @()
  foreach ($q in $diag.questions) {
    $pick = $null
    if ($q.options -and $q.options.Count -gt 0) { $pick = $q.options[0] } else { $pick = "sample answer" }
    $answers += @{
      question_id = $q.question_id
      answer = $pick
    }
  }
  $submitBody = @{
    signup_draft_id = $signupStart.signup_draft_id
    diagnostic_attempt_id = $diag.diagnostic_attempt_id
    answers = $answers
    time_spent_minutes = 12
  } | ConvertTo-Json
  $submit = Invoke-RestMethod -Method Post -Uri "$BaseUrl/onboarding/submit" -Body $submitBody -ContentType "application/json"
  if (-not $submit.learner_id -or -not $submit.token) {
    throw "Onboarding submit did not return token/learner_id."
  }
  $learnerId = $submit.learner_id
  $headers = @{ Authorization = "Bearer $($submit.token)" }
  Write-Host "Onboarding complete for learner: $learnerId"

  Write-Host "`n[5/8] Learning dashboard"
  $dash = Invoke-RestMethod -Method Get -Uri "$BaseUrl/learning/dashboard/$learnerId" -Headers $headers
  if ($null -eq $dash.current_week) {
    throw "Dashboard response missing current_week."
  }
  Write-Host "Dashboard OK. Week: $($dash.current_week)"

  Write-Host "`n[6/8] Comparative analytics"
  $cmp = Invoke-RestMethod -Method Get -Uri "$BaseUrl/onboarding/comparative-analytics/$learnerId" -Headers $headers
  if ($null -eq $cmp.cohort_size) { throw "Comparative analytics missing cohort_size." }
  Write-Host "Comparative analytics OK."

  Write-Host "`n[7/8] Reminder diagnostics"
  $diagRem = Invoke-RestMethod -Method Get -Uri "$BaseUrl/onboarding/reminders/diagnostics" -Headers $headers
  if ($null -eq $diagRem.dispatch_policy) { throw "Reminder diagnostics missing dispatch_policy." }
  Write-Host "Reminder diagnostics OK."

  Write-Host "`n[8/8] Metrics MCP visibility"
  $metrics = Invoke-RestMethod -Method Get -Uri "$BaseUrl/metrics/app" -Headers $headers
  if ($null -eq $metrics.mcp) { throw "MCP metrics missing from /metrics/app." }
  Write-Host "MCP metrics OK."

  Write-Host "`nSmoke test PASSED."
  Write-Host "`nSummary:"
  [PSCustomObject]@{
    learner_id = $learnerId
    current_week = $dash.current_week
    week_label = $dash.current_week_label
    completion_percent = $dash.overall_completion_percent
    cohort_size = $cmp.cohort_size
    reminder_runtime_ready = $diagRem.runtime_ready
    mcp_calls_total = $metrics.mcp.mcp_calls_total
  } | Format-List
}
catch {
  Write-Error "`nSmoke test FAILED: $($_.Exception.Message)"
  exit 1
}
