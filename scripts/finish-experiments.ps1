# Follow-up after run-experiments.ps1: re-run rows lost to infrastructure errors (bench resumes and
# retries only those), refresh the 1.5B profile from cached runs, and regenerate the README charts.
param([int]$WaitPid = 0)
$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$env:OLLAMA_HOST = '127.0.0.1:11436'
$env:TVASHTR_UPSTREAM = 'http://127.0.0.1:11436'
$env:PYTHONIOENCODING = 'utf-8'
$py = Join-Path $root '.venv\Scripts\python.exe'
$log = Join-Path $root 'results\experiments.log'
function Log($m) { "$(Get-Date -Format s) $m" | Out-File -Append -Encoding utf8 $log }
function Run([string[]]$argv) { & $py -m tvashtr @argv 2>&1 | ForEach-Object { "$_" } | Out-File -Append -Encoding utf8 $log }

if ($WaitPid) { while (Get-Process -Id $WaitPid -ErrorAction SilentlyContinue) { Start-Sleep 20 } }
Log '== finish: re-running infrastructure-errored rows'
foreach ($r in @(@('s_star', 'test'), @('s_star', 'dev'), @('codet', 'dev'), @('adaptive', 'dev'))) {
    Run @('bench', '--model', 'qc15:control', '--strategy', $r[0], '--part', $r[1], '--workers', '1')
}
Run @('bench', '--model', 'qc7:control', '--strategy', 'direct', '--part', 'dev', '--workers', '1')
Log '== finish: refreshing 1.5B profile'
Run @('autotune', '--model', 'qc15:control', '--workers', '1')
& $py (Join-Path $root 'scripts\make_charts.py') 2>&1 | Out-File -Append -Encoding utf8 $log
Log '== finish complete'
