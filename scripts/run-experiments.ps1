# Sequential experiments, safe to run detached:
#   1. autotune all post-training enhancements on Qwen2.5-Coder-1.5B (control GGUF)
#   2. ExPO sweep on Qwen2.5-Coder-7B
# Uses a dedicated Ollama instance on port 11436 with its model store on D: and one model in memory.
$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$env:OLLAMA_HOST = '127.0.0.1:11436'
$env:TVASHTR_UPSTREAM = 'http://127.0.0.1:11436'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUNBUFFERED = '1'
$py = Join-Path $root '.venv\Scripts\python.exe'
$log = Join-Path $root 'results\experiments.log'
function Log($m) { "$(Get-Date -Format s) $m" | Out-File -Append -Encoding utf8 $log }
function Run([string[]]$argv) { & $py -m tvashtr @argv 2>&1 | ForEach-Object { "$_" } | Out-File -Append -Encoding utf8 $log }

Log '== 1/2 autotune PTEs on qc15:control (Qwen2.5-Coder-1.5B-Instruct fp16)'
Run @('autotune', '--model', 'qc15:control', '--workers', '1')
Log '== 1/2 done'

Log '== 2/2 ExPO sweep on Qwen2.5-Coder-7B'
foreach ($m in 'qwen2.5-coder:7b-base-fp16', 'qwen2.5-coder:7b-instruct-fp16') {
    ollama pull $m *> $null
    Log "pull $m exit $LASTEXITCODE"
}
Run @('expo-sweep', '--base', 'qwen2.5-coder:7b-base-fp16', '--instruct', 'qwen2.5-coder:7b-instruct-fp16',
      '--prefix', 'qc7', '--workdir', 'D:\models\gguf', '--workers', '1')
Log '== 2/2 done'
Log '== all experiments complete'
