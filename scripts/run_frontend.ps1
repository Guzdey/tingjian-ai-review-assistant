param(
  [string]$PythonPath = 'D:\CodexData\tingjian-ai\.venv\Scripts\python.exe'
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
if (-not (Test-Path -LiteralPath $PythonPath)) {
  throw "找不到Python环境：$PythonPath。请先运行 scripts\setup.ps1。"
}

Push-Location $repoRoot
try {
  Write-Host '打开 http://127.0.0.1:5500/'
  & $PythonPath -m http.server 5500 --bind 127.0.0.1
} finally {
  Pop-Location
}
