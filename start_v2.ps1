# Start Satya-Score Version 2 (LLM cross-check) for a demo: the API on http://localhost:8000 and the web app on
# http://localhost:5173, each in its own window. To confirm the mode, open http://localhost:8000/health: it should
# show "mode":"v2".
#   powershell -ExecutionPolicy Bypass -File start_v2.ps1           (Groq first if GROQ_API_KEY is set, else local)
#   powershell -ExecutionPolicy Bypass -File start_v2.ps1 -LocalOnly (local Ollama model only)
param([switch]$LocalOnly)
$root = $PSScriptRoot
$providers = if ($LocalOnly -or -not $env:GROQ_API_KEY) { "ollama" } else { "groq,ollama" }
$models = if ($providers -eq "ollama") { "gpt-oss:20b" } else { "openai/gpt-oss-20b,gpt-oss:20b" }
$backend = @"
`$env:SATYASCORE_VERDICT_MODE = 'crosscheck'
`$env:SATYASCORE_LLM_PROVIDER = '$providers'
`$env:SATYASCORE_LLM_MODEL = '$models'
`$env:SATYASCORE_FLAG_NEEDS_LLM = 'true'
`$env:SATYASCORE_SECOND_READING_FLAGS = 'true'
Set-Location '$root'
.venv\Scripts\python.exe -m uvicorn member3_backend.api:app --port 8000
"@
Start-Process powershell -ArgumentList '-NoExit', '-Command', $backend
Start-Process powershell -ArgumentList '-NoExit', '-Command', "Set-Location '$root\web'; npm run dev"
"Started Version 2 ($providers). Wait for 'Application startup complete' in the API window, then open http://localhost:5173"
