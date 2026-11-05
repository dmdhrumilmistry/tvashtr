# Weight-only cyber + coding merge: graft DeepHat-V1-7B's task vector (DeepHat - Qwen2.5-Coder-7B base)
# onto Qwen2.5-Coder-7B-Instruct, no training. Each variant is built, registered with Ollama, scored on
# the dev halves of HumanEval + CyberMetric + CTI-MCQ + CTI-RCM, then removed to save disk (the graft is
# deterministic, so the winner is rebuilt for the test confirmation). Detached-safe.
param([string]$Port = '11436', [string]$Donor = 'D:\models\DeepHat-V1-7B', [string]$Work = 'D:\models\gguf',
      [string]$VariantSpec = '', [switch]$SkipControl, [int]$WaitPid = 0)
$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$env:OLLAMA_HOST = "127.0.0.1:$Port"
$env:TVASHTR_UPSTREAM = "http://127.0.0.1:$Port"
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUNBUFFERED = '1'
Remove-Item Env:TVASHTR_THINK -ErrorAction SilentlyContinue
$py = Join-Path $root '.venv\Scripts\python.exe'
$log = Join-Path $root 'results\graft.log'
function Log($m) { "$(Get-Date -Format s) $m" | Out-File -Append -Encoding utf8 $log }
function Run([string[]]$argv) { & $py -m tvashtr @argv 2>&1 | ForEach-Object { "$_" } | Out-File -Append -Encoding utf8 $log }
function Eval([string]$m, [switch]$SkipCode) {
    if (-not $SkipCode) { Run @('bench', '--model', $m, '--strategy', 'direct', '--part', 'dev', '--workers', '1') }
    foreach ($d in 'cybermetric', 'cti-mcq', 'cti-rcm') {
        Run @('secbench', '--model', $m, '--dataset', $d, '--strategy', 'direct', '--part', 'dev', '--workers', '1')
    }
}

if ($WaitPid) { Wait-Process -Id $WaitPid -ErrorAction SilentlyContinue }
$base = 'qwen2.5-coder:7b-base-fp16'
$inst = 'qwen2.5-coder:7b-instruct-fp16'

if (-not $SkipControl) {
    Log '== control: qc7:control security dev (coding dev already measured: 75/82)'
    Eval 'qc7:control' -SkipCode
}

# name, base, beta, dare. DeepHat itself = instruct + 1.0 * (DeepHat - instruct), so it keeps the
# instruct GGUF header (chat template, <|im_end|> stop) and is a fair baseline.
$variants = @(
    @('cs7:deephat', $inst, '1.0', '0'),
    @('cs7:b0.5-d0.9', $base, '0.5', '0.9'),
    @('cs7:b1.0-d0.9', $base, '1.0', '0.9'),
    @('cs7:b0.3', $base, '0.3', '0')
)
# override, e.g. -VariantSpec 'cs7:b0.7=base,0.7,0;cs7:b1.0=base,1.0,0'
if ($VariantSpec) {
    $variants = @()
    foreach ($spec in $VariantSpec.Split(';')) {
        $n, $r = $spec.Split('=')
        $f = $r.Split(',')
        $vb = if ($f[0] -eq 'inst') { $inst } else { $base }
        $variants += , @($n, $vb, $f[1], $f[2])
    }
}
foreach ($v in $variants) {
    $name, $b, $beta, $dare = $v
    $gguf = Join-Path $Work (($name -replace '[:]', '_') + '.gguf')
    Log "== build $name (base=$b beta=$beta dare=$dare)"
    Run @('graft', '--base', $b, '--target', $inst, '--donor', $Donor, '--beta', $beta, '--dare', $dare,
          '--out', $gguf, '--name', $name)
    Remove-Item $gguf -ErrorAction SilentlyContinue
    Log "== eval $name"
    Eval $name
    ollama rm $name *> $null
    Log "== done $name"
}
Log '== graft sweep complete'
