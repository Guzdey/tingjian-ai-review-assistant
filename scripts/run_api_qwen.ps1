param(
  [string]$PythonPath = 'D:\CodexData\tingjian-ai\.venv\Scripts\python.exe',
  [string]$DataPath = 'D:\CodexData\tingjian-ai\processed\private_derived.json'
)

$ErrorActionPreference = 'Stop'
$secureKey = Read-Host '请输入阿里云百炼 API Key（输入不会显示，也不会写入文件）' -AsSecureString
$pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)

try {
  $plainKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
  if ([string]::IsNullOrWhiteSpace($plainKey) -or $plainKey.Length -lt 10) {
    throw 'API Key为空或长度异常。'
  }
  $env:DASHSCOPE_API_KEY = $plainKey
  & (Join-Path $PSScriptRoot 'run_api.ps1') `
    -PythonPath $PythonPath `
    -Mode qwen `
    -DataPath $DataPath
} finally {
  $env:DASHSCOPE_API_KEY = $null
  if ($pointer -ne [IntPtr]::Zero) {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
  }
  $plainKey = $null
  $secureKey = $null
}
