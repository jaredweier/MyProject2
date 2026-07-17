# Chronos Command — start local lab server + public tunnel (cloudflared or ngrok)
# Called by: Start Remote UAT Tunnel.bat
param(
    [int]$Port = 8080,
    [switch]$SkipGates,
    [string]$Prefer = ""  # cloudflared | ngrok | auto
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

function Test-Cmd($Name) {
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Resolve-Cloudflared {
    if (Test-Cmd "cloudflared") { return "cloudflared" }
    $candidates = @(
        "${env:ProgramFiles(x86)}\cloudflared\cloudflared.exe",
        "$env:ProgramFiles\cloudflared\cloudflared.exe",
        "$env:LOCALAPPDATA\Microsoft\WinGet\Links\cloudflared.exe"
    )
    foreach ($p in $candidates) {
        if ($p -and (Test-Path $p)) { return $p }
    }
    return $null
}

function Resolve-Ngrok {
    if (Test-Cmd "ngrok") { return "ngrok" }
    $candidates = @(
        "$env:LOCALAPPDATA\Microsoft\WinGet\Links\ngrok.exe",
        "$env:ProgramFiles\ngrok\ngrok.exe"
    )
    foreach ($p in $candidates) {
        if ($p -and (Test-Path $p)) { return $p }
    }
    return $null
}

function Test-PortOpen([int]$P) {
    try {
        $c = New-Object System.Net.Sockets.TcpClient
        $c.Connect("127.0.0.1", $P)
        $c.Close()
        return $true
    } catch {
        return $false
    }
}

Write-Host ""
Write-Host "=== Chronos Command — Remote UAT Tunnel ===" -ForegroundColor Cyan
Write-Host "Doc: docs\VIRTUAL_UAT.md · Cloud VM: docs\deploy\CLOUD_VM.md"
Write-Host ""

if (-not $env:SCHEDULER_STORAGE_SECRET) {
    $secretFile = Join-Path $Root "storage_secret.txt"
    if (Test-Path $secretFile) {
        $env:SCHEDULER_STORAGE_SECRET = (Get-Content $secretFile -Raw).Trim()
    } else {
        $bytes = New-Object byte[] 32
        [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
        $env:SCHEDULER_STORAGE_SECRET = ($bytes | ForEach-Object { $_.ToString("x2") }) -join ""
        Set-Content -Path $secretFile -Value $env:SCHEDULER_STORAGE_SECRET -Encoding ASCII
        Write-Host "[ok] wrote storage_secret.txt"
    }
}

$labDir = Join-Path $Root "lab_data"
if (-not (Test-Path $labDir)) { New-Item -ItemType Directory -Path $labDir | Out-Null }
$env:SCHEDULER_DB_PATH = Join-Path $labDir "virtual_uat.db"
$env:SCHEDULER_UI_MODE = "web"
$env:SCHEDULER_HOST = "127.0.0.1"
$env:SCHEDULER_PORT = "$Port"
$env:SCHEDULER_SKIP_GATES = "1"
$env:SCHEDULER_SKIP_STARTUP_GATES = "1"
$env:SCHEDULER_UAT_LAB = "1"
$env:SCHEDULER_RECONNECT_TIMEOUT = "45"

# Prep demo accounts + sample rows (full product as admin)
Write-Host "Preparing UAT lab (admin full access, sample data)..."
python -c "import os; os.environ['SCHEDULER_UAT_LAB']='1'; os.environ['SCHEDULER_DB_PATH']=r'$($env:SCHEDULER_DB_PATH)'; from logic.uat_lab import prepare_uat_lab; import json; print(json.dumps(prepare_uat_lab(), indent=2))"
if ($LASTEXITCODE -ne 0) {
    Write-Host "[warn] prepare_uat_lab returned non-zero — continuing"
}

# Always start a fresh UAT-enabled Chronos (stale server lacks /uat + one-click login)
if (Test-PortOpen $Port) {
    Write-Host "Stopping process(es) on port $Port for UAT restart..."
    try {
        $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        foreach ($c in $conns) {
            if ($c.OwningProcess) {
                Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue
                Write-Host "  stopped PID $($c.OwningProcess)"
            }
        }
    } catch {
        # fallback: kill python main.py (best effort)
        Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandLine -match 'main\.py' } |
            ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    }
    Start-Sleep -Seconds 2
}

$serverProc = $null
Write-Host "Starting Chronos UAT lab on 127.0.0.1:$Port ..."
$serverProc = Start-Process -FilePath "python" `
    -ArgumentList @("main.py", "--web", "--host", "127.0.0.1", "--port", "$Port") `
    -WorkingDirectory $Root `
    -PassThru `
    -WindowStyle Minimized
$deadline = (Get-Date).AddSeconds(60)
while (-not (Test-PortOpen $Port)) {
    if ((Get-Date) -gt $deadline) {
        Write-Host "[FAIL] Chronos did not open port $Port" -ForegroundColor Red
        if ($serverProc -and -not $serverProc.HasExited) { Stop-Process -Id $serverProc.Id -Force -ErrorAction SilentlyContinue }
        exit 1
    }
    Start-Sleep -Milliseconds 500
}
Write-Host "[ok] Chronos UAT listening on :$Port (PID $($serverProc.Id))"

$cf = Resolve-Cloudflared
$ng = Resolve-Ngrok
$tool = $Prefer.ToLowerInvariant()
if ($tool -eq "" -or $tool -eq "auto") {
    if ($cf) { $tool = "cloudflared" }
    elseif ($ng) { $tool = "ngrok" }
    else { $tool = "" }
}

Write-Host ""
Write-Host "Send testers (full product):" -ForegroundColor Yellow
Write-Host "  1) Open the https://…trycloudflare.com URL below"
Write-Host "  2) Click: Enter full product (Administration)"
Write-Host "  3) Use left nav or UAT Lab page for every feature"
Write-Host "  Optional roles: supervisor/supervisor · officer/officer"
Write-Host "  Keep this window open. Ctrl+C stops tunnel (+ Chronos if we started it)."
Write-Host ""

if ($tool -eq "cloudflared" -and $cf) {
    Write-Host "Tunnel: $cf → http://127.0.0.1:$Port"
    Write-Host "Copy the https://*.trycloudflare.com URL from the log below."
    Write-Host ""
    try {
        # http2 more reliable than quic on some Windows hosts (avoids 530)
        & $cf tunnel --url "http://127.0.0.1:$Port" --protocol http2
    } finally {
        if ($serverProc -and -not $serverProc.HasExited) {
            Write-Host "Stopping Chronos PID $($serverProc.Id)..."
            Stop-Process -Id $serverProc.Id -Force -ErrorAction SilentlyContinue
        }
    }
    exit 0
}

if ($tool -eq "ngrok" -and $ng) {
    Write-Host "Tunnel: $ng → http://127.0.0.1:$Port"
    Write-Host "Copy the https:// URL from the ngrok UI or log."
    Write-Host ""
    try {
        & $ng http $Port
    } finally {
        if ($serverProc -and -not $serverProc.HasExited) {
            Write-Host "Stopping Chronos PID $($serverProc.Id)..."
            Stop-Process -Id $serverProc.Id -Force -ErrorAction SilentlyContinue
        }
    }
    exit 0
}

Write-Host "[FAIL] Neither cloudflared nor ngrok found on PATH." -ForegroundColor Red
Write-Host ""
Write-Host "Install ONE of:"
Write-Host "  winget install Cloudflare.cloudflared"
Write-Host "  winget install Ngrok.Ngrok"
Write-Host "  Or: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/"
Write-Host "      https://ngrok.com/download"
Write-Host ""
Write-Host "Chronos is still running on http://127.0.0.1:$Port (local only)."
Write-Host "After install, re-run this script (or: cloudflared tunnel --url http://127.0.0.1:$Port)"
Write-Host ""
Write-Host "Cloud VM (no laptop): docs\deploy\CLOUD_VM.md"
if ($serverProc) {
    Write-Host "Server PID $($serverProc.Id) left running. Stop it from Task Manager if needed."
}
exit 1
