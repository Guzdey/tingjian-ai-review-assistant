param(
  [string]$DataRoot = 'D:\CodexData\tingjian-ai'
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$venvPath = Join-Path $DataRoot '.venv'
$pythonPath = Join-Path $venvPath 'Scripts\python.exe'

New-Item -ItemType Directory -Path $DataRoot -Force | Out-Null
if (-not (Test-Path -LiteralPath $pythonPath)) {
  python -m venv $venvPath
}

& $pythonPath -m pip install -r (Join-Path $repoRoot 'backend\requirements.txt')
Write-Host "环境准备完成：$venvPath"
Write-Host '下一步分别运行 scripts\run_api.ps1 和 scripts\run_frontend.ps1'
