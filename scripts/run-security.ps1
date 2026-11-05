# Security benchmark sweep: pull candidate models, then pick the best PTE per benchmark on dev and
# confirm on test (tvashtr sectune). Detached-safe; one model in memory at a time.
param([string]$Store = 'D:\models\ollama', [string]$Port = '11437', [int]$DevLimit = 60)
$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$py = Join-Path $root '.venv\Scripts\python.exe'
$log = Join-Path $root 'results\security.log'
function Log($m) { "$(Get-Date -Format s) $m" | Out-File -Append -Encoding utf8 $log }

# dedicated server for benchmarking (two parallel requests for self-consistency sampling)
$env:OLLAMA_MODELS = $Store; $env:OLLAMA_HOST = "127.0.0.1:$Port"
$env:OLLAMA_MAX_LOADED_MODELS = '1'; $env:OLLAMA_NUM_PARALLEL = '2'; $env:OLLAMA_KEEP_ALIVE = '2m'
$srv = Start-Process ollama -ArgumentList serve -WindowStyle Hidden -PassThru -RedirectStandardError (Join-Path $root "results\ollama-$Port.log")
Start-Sleep 5
$env:TVASHTR_UPSTREAM = "http://127.0.0.1:$Port"
$env:PYTHONIOENCODING = 'utf-8'

# model tag -> thinking mode (false = answer directly; low = gpt-oss minimum; '' = model default)
$models = [ordered]@{
    'hf.co/Mungert/Foundation-Sec-8B-Instruct-GGUF:Q4_K_M' = ''
    'qwen3:14b'                                           = 'false'
    'gpt-oss:20b'                                         = 'low'
}
foreach ($m in $models.Keys) {
    ollama pull $m *> $null
    Log "pull $m exit $LASTEXITCODE"
}
foreach ($m in $models.Keys) {
    if ($models[$m]) { $env:TVASHTR_THINK = $models[$m] } else { Remove-Item Env:TVASHTR_THINK -ErrorAction SilentlyContinue }
    Log "== sectune $m (think=$($models[$m]))"
    & $py -m tvashtr sectune --model $m --dev-limit $DevLimit --workers 2 2>&1 | ForEach-Object { "$_" } | Out-File -Append -Encoding utf8 $log
    Log "== done $m"
}
Log '== security sweep complete'
Stop-Process -Id $srv.Id -ErrorAction SilentlyContinue
