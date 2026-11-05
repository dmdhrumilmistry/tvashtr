# Combined coding + security evaluation, then build the tvashtr/auto router from dev-selected results.
# Detached-safe and sequential: one model in memory at a time.
param([int]$WaitPid = 0, [string]$Store = 'D:\models\ollama', [string]$Port = '11437', [int]$DevLimit = 60)
$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$py = Join-Path $root '.venv\Scripts\python.exe'
$log = Join-Path $root 'results\unified.log'
function Log($m) { "$(Get-Date -Format s) $m" | Out-File -Append -Encoding utf8 $log }
function Tv([string[]]$argv) { & $py -m tvashtr @argv 2>&1 | ForEach-Object { "$_" } | Out-File -Append -Encoding utf8 $log }
function Think($v) { if ($v) { $env:TVASHTR_THINK = $v } else { Remove-Item Env:TVASHTR_THINK -ErrorAction SilentlyContinue } }

if ($WaitPid) { while (Get-Process -Id $WaitPid -ErrorAction SilentlyContinue) { Start-Sleep 30 } }
$env:PYTHONIOENCODING = 'utf-8'

# --- security-tuned and general models on the D: store -------------------------------------------
$env:OLLAMA_MODELS = $Store; $env:OLLAMA_HOST = "127.0.0.1:$Port"
$env:OLLAMA_MAX_LOADED_MODELS = '1'; $env:OLLAMA_NUM_PARALLEL = '2'; $env:OLLAMA_KEEP_ALIVE = '2m'
$srv = Start-Process ollama -ArgumentList serve -WindowStyle Hidden -PassThru -RedirectStandardError (Join-Path $root "results\ollama-$Port.log")
Start-Sleep 5
$env:TVASHTR_UPSTREAM = "http://127.0.0.1:$Port"
$models = [ordered]@{ 'hf.co/Mungert/Foundation-Sec-8B-Instruct-GGUF:Q4_K_M' = ''; 'qwen3:14b' = 'false'; 'gpt-oss:20b' = 'low' }
foreach ($m in $models.Keys) {
    Think $models[$m]
    Log "== $m : HumanEval direct"
    foreach ($part in 'dev', 'test') { Tv @('bench', '--model', $m, '--strategy', 'direct', '--part', $part, '--workers', '2') }
    Log "== $m : retrieval strategies"
    Tv @('sectune', '--model', $m, '--datasets', 'cti-rcm', '--strategies', 'direct,cot,sc5,rag,rag_cot,rag_hyde', '--dev-limit', "$DevLimit")
    Tv @('sectune', '--model', $m, '--datasets', 'cti-mcq', '--strategies', 'direct,cot,sc5,rag,rag_cot', '--dev-limit', "$DevLimit")
    Tv @('sectune', '--model', $m, '--datasets', 'cybermetric', '--strategies', 'direct,cot,sc5,rag', '--dev-limit', "$DevLimit")
}
Stop-Process -Id $srv.Id -ErrorAction SilentlyContinue
Start-Sleep 5

# --- the coding model on the main Ollama store, alone in memory ------------------------------------
Remove-Item Env:OLLAMA_MODELS, Env:OLLAMA_HOST -ErrorAction SilentlyContinue
$env:TVASHTR_UPSTREAM = 'http://127.0.0.1:11434'
Think ''
Log '== qwen3-coder:30b : HumanEval dev + security'
Tv @('bench', '--model', 'qwen3-coder:30b', '--strategy', 'direct', '--part', 'dev', '--workers', '1')
Tv @('sectune', '--model', 'qwen3-coder:30b', '--strategies', 'direct,rag', '--dev-limit', "$DevLimit", '--workers', '1')

Log '== building router and scorecard'
Tv @('router', '--think', '{"qwen3:14b": false, "gpt-oss:20b": "low"}')
& $py (Join-Path $root 'scripts\make_charts.py') 2>&1 | Out-File -Append -Encoding utf8 $log
Log '== unified evaluation complete'
