$ErrorActionPreference = 'Stop'
$Host.UI.RawUI.WindowTitle = '听荐千问后端 - 安全启动'
Clear-Host

$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$pythonPath = 'D:\CodexData\tingjian-ai\.venv\Scripts\python.exe'
$dataPath = 'D:\CodexData\tingjian-ai\processed\private_derived.json'
$logRoot = 'D:\CodexData\tingjian-ai\logs'
$statusPath = Join-Path $logRoot 'qwen_api_process.json'
$errorPath = Join-Path $logRoot 'qwen_startup_last_error.txt'
$pointer = [IntPtr]::Zero
$plainKey = $null
$secureKey = $null

function Write-SanitizedError([string]$Message) {
  $safeMessage = $Message -replace '(?i)sk-[A-Za-z0-9._-]+', '[REDACTED_API_KEY]'
  [IO.File]::WriteAllText($errorPath, $safeMessage, [Text.UTF8Encoding]::new($false))
  Write-Host "启动失败：$safeMessage" -ForegroundColor Red
  Write-Host "脱敏错误已写入：$errorPath" -ForegroundColor DarkYellow
}

try {
  Write-Host '听荐千问后端安全启动' -ForegroundColor Cyan
  Write-Host '正在进行无密钥预检……' -ForegroundColor Gray
  if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "找不到Python环境：$pythonPath"
  }
  if (-not (Test-Path -LiteralPath $dataPath)) {
    throw "找不到私有派生数据：$dataPath"
  }
  if (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) {
    throw '8000端口已被其他程序占用。'
  }
  New-Item -ItemType Directory -Force -Path $logRoot | Out-Null
  Write-Host '预检通过。' -ForegroundColor Green
  Write-Host '请只在下一行提示出现后粘贴Key；输入时不会显示字符。' -ForegroundColor Yellow
  Write-Host ''

  $secureKey = Read-Host '请输入阿里云百炼 API Key' -AsSecureString
  $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
  $plainKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
  if ([string]::IsNullOrWhiteSpace($plainKey) -or $plainKey.Length -lt 10) {
    throw 'API Key为空或长度异常。'
  }

  $env:DASHSCOPE_API_KEY = $plainKey
  $env:TINGJIAN_AI_MODE = 'qwen'
  $env:TINGJIAN_DEMO_DATA_PATH = $dataPath
  $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
  $stdoutPath = Join-Path $logRoot "qwen-api-$stamp.stdout.log"
  $stderrPath = Join-Path $logRoot "qwen-api-$stamp.stderr.log"
  $arguments = @(
    '-m', 'uvicorn', 'backend.app.main:app',
    '--host', '127.0.0.1', '--port', '8000'
  )
  $process = Start-Process `
    -FilePath $pythonPath `
    -ArgumentList $arguments `
    -WorkingDirectory $repoRoot `
    -WindowStyle Hidden `
    -RedirectStandardOutput $stdoutPath `
    -RedirectStandardError $stderrPath `
    -PassThru

  $env:DASHSCOPE_API_KEY = $null
  $plainKey = $null
  $ready = $false
  for ($attempt = 0; $attempt -lt 30; $attempt++) {
    Start-Sleep -Milliseconds 250
    if ($process.HasExited) { break }
    if (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) {
      $ready = $true
      break
    }
  }
  if (-not $ready) {
    $details = if (Test-Path -LiteralPath $stderrPath) {
      (Get-Content -LiteralPath $stderrPath -Tail 12) -join "`n"
    } else {
      '后端进程未监听8000端口，且没有产生错误日志。'
    }
    if (-not $process.HasExited) {
      Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    }
    throw $details
  }

  [pscustomobject]@{
    process_id = $process.Id
    mode = 'qwen'
    data_path = $dataPath
    stdout_log = $stdoutPath
    stderr_log = $stderrPath
    started_at = (Get-Date).ToString('o')
  } | ConvertTo-Json | Set-Content -LiteralPath $statusPath -Encoding UTF8
  [IO.File]::WriteAllText($errorPath, '', [Text.UTF8Encoding]::new($false))
  Write-Host ''
  Write-Host '启动成功：千问模式已在 http://127.0.0.1:8000 运行。' -ForegroundColor Green
  Write-Host '现在可以回到Codex并回复“启动成功”。' -ForegroundColor Cyan
} catch {
  New-Item -ItemType Directory -Force -Path $logRoot | Out-Null
  Write-SanitizedError $_.Exception.Message
} finally {
  $env:DASHSCOPE_API_KEY = $null
  $env:TINGJIAN_AI_MODE = $null
  $env:TINGJIAN_DEMO_DATA_PATH = $null
  $plainKey = $null
  $secureKey = $null
  if ($pointer -ne [IntPtr]::Zero) {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
  }
}

Write-Host ''
Read-Host '按回车关闭此启动窗口（后端成功时会继续在后台运行）'
