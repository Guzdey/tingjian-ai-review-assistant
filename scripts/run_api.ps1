param(
  [string]$PythonPath = 'D:\CodexData\tingjian-ai\.venv\Scripts\python.exe',
  [ValidateSet('auto','local','qwen')]
  [string]$Mode = 'auto',
  [string]$DataPath = ''
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
if (-not (Test-Path -LiteralPath $PythonPath)) {
  throw "找不到Python环境：$PythonPath。请先运行 scripts\setup.ps1。"
}

$defaultPrivateData = 'D:\CodexData\tingjian-ai\processed\private_derived.json'
if (-not $DataPath -and -not $env:TINGJIAN_DEMO_DATA_PATH -and (Test-Path -LiteralPath $defaultPrivateData)) {
  $DataPath = $defaultPrivateData
}
if ($DataPath) {
  $resolvedData = (Resolve-Path -LiteralPath $DataPath).Path
  $env:TINGJIAN_DEMO_DATA_PATH = $resolvedData
}

$env:TINGJIAN_AI_MODE = $Mode
if ($env:TINGJIAN_DEMO_DATA_PATH) {
  Write-Host "证据数据：$env:TINGJIAN_DEMO_DATA_PATH"
} else {
  Write-Host '证据数据：仓库内明确标注的合成演示缓存'
}
Write-Host "AI模式：$Mode（auto在无DASHSCOPE_API_KEY时使用本地规则）"

Push-Location $repoRoot
try {
  & $PythonPath -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
} finally {
  Pop-Location
}
