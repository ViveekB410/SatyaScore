# Start Satya-Score Version 2 (LLM cross-check) for a demo: the API on http://localhost:8000 and the web app on
# http://localhost:5173, each in its own window, then open the web app in the browser once the API is ready.
# To confirm the mode, open http://localhost:8000/health: it should show "mode":"v2".
#   powershell -ExecutionPolicy Bypass -File start_v2.ps1           (Groq first if GROQ_API_KEY is set, else local)
#   powershell -ExecutionPolicy Bypass -File start_v2.ps1 -LocalOnly (local Ollama model only)
# "Start Satya-Score.bat" runs this script on a double-click.
param([switch]$LocalOnly)
$root = $PSScriptRoot
$groqKey = $env:GROQ_API_KEY
if (-not $groqKey) { $groqKey = [Environment]::GetEnvironmentVariable('GROQ_API_KEY', 'User') }
$providers = if ($LocalOnly -or -not $groqKey) { "ollama" } else { "groq,ollama" }
$models = if ($providers -eq "ollama") { "gpt-oss:20b" } else { "openai/gpt-oss-20b,gpt-oss:20b" }

function Test-Port($port) { [bool](Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue) }

# API (skipped if something already listens on 8000)
if (Test-Port 8000) {
  "API already running on port 8000 (check http://localhost:8000/health for the mode)"
} else {
  $backend = @"
`$env:SATYASCORE_VERDICT_MODE = 'crosscheck'
`$env:SATYASCORE_LLM_PROVIDER = '$providers'
`$env:SATYASCORE_LLM_MODEL = '$models'
`$env:SATYASCORE_FLAG_NEEDS_LLM = 'true'
`$env:SATYASCORE_SECOND_READING_FLAGS = 'true'
Set-Location '$root'
.venv\Scripts\python.exe -m uvicorn member3_backend.api:app --port 8000
"@
  Start-Process powershell -ArgumentList '-NoExit', '-ExecutionPolicy', 'Bypass', '-Command', $backend
  "Starting the API ($providers)..."
}

# Web app: npm.cmd, not npm (npm.ps1 is blocked where PowerShell scripts are not allowed)
if (Test-Port 5173) {
  "Web app already running on port 5173"
} else {
  Start-Process cmd -ArgumentList '/k', "cd /d `"$root\web`" && npm.cmd run dev"
  "Starting the web app..."
}

# Wait for the API to load its models (about a minute), then open the browser
$deadline = (Get-Date).AddMinutes(4)
while ((Get-Date) -lt $deadline) {
  try { $h = Invoke-RestMethod http://localhost:8000/health -TimeoutSec 3; if ($h.status -eq 'ok') { break } } catch { }
  Start-Sleep 3
}
if ($h.status -eq 'ok') {
  "API ready: mode $($h.mode), $($h.index_size) passages. Opening http://localhost:5173/analyse"
  Start-Process "http://localhost:5173/analyse"
} else {
  "The API did not answer within 4 minutes: look at the API window for an error."
}
