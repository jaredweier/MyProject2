# Wire Chronos always-on UAT to a Cloudflare-managed domain (stable URL).
#
# Example:
#   powershell -ExecutionPolicy Bypass -File scripts\setup_domain_tunnel.ps1 -Domain chronoscommand.com -Subdomain "@"
#   -> https://chronoscommand.com
#
#   powershell -ExecutionPolicy Bypass -File scripts\setup_domain_tunnel.ps1 -Domain example.com -Subdomain chronos
#   -> https://chronos.example.com
#
param(
    [Parameter(Mandatory = $true)]
    [string]$Domain,

    [string]$Subdomain = "chronos",

    [string]$TunnelName = "chronos-uat",

    [int]$Port = 8080,

    [switch]$SkipRestart,

    [switch]$LoginOnly
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$Domain = $Domain.Trim().TrimEnd(".")
$Subdomain = $Subdomain.Trim().TrimEnd(".")
if (-not $Domain) { throw "Domain is required (e.g. chronoscommand.com)" }

if ($Subdomain -eq "" -or $Subdomain -eq "@" -or $Subdomain -eq ".") {
    $PublicHost = $Domain
} else {
    $PublicHost = "$Subdomain.$Domain"
}
$PublicUrl = "https://$PublicHost"

function Resolve-Cloudflared {
    if (Get-Command cloudflared -ErrorAction SilentlyContinue) {
        return (Get-Command cloudflared).Source
    }
    foreach ($p in @(
            "${env:ProgramFiles(x86)}\cloudflared\cloudflared.exe",
            "$env:ProgramFiles\cloudflared\cloudflared.exe"
        )) {
        if (Test-Path $p) { return $p }
    }
    return $null
}

function Write-Info([string]$Msg) { Write-Host $Msg -ForegroundColor Cyan }
function Write-Ok([string]$Msg) { Write-Host $Msg -ForegroundColor Green }

$cf = Resolve-Cloudflared
if (-not $cf) {
    Write-Host "cloudflared not found. Install: winget install Cloudflare.cloudflared" -ForegroundColor Yellow
    throw "cloudflared missing"
}
Write-Ok "cloudflared: $cf"

$cfDir = Join-Path $env:USERPROFILE ".cloudflared"
if (-not (Test-Path $cfDir)) {
    New-Item -ItemType Directory -Path $cfDir | Out-Null
}

Write-Info ""
Write-Info "=== Chronos domain tunnel setup ==="
Write-Info "Public URL:  $PublicUrl"
Write-Info "Tunnel name: $TunnelName"
Write-Info "Origin:      http://127.0.0.1:$Port"
Write-Info ""

$credCert = Join-Path $cfDir "cert.pem"
if (-not (Test-Path $credCert)) {
    Write-Info "Opening browser for Cloudflare login..."
    Write-Info "Authorize the account that owns DNS for: $Domain"
    & $cf tunnel login
    if (-not (Test-Path $credCert)) {
        throw "Login did not create cert.pem - re-run after authorizing in the browser."
    }
    Write-Ok "Cloudflare login OK"
} else {
    Write-Ok "Already logged in ($credCert)"
}

if ($LoginOnly) {
    Write-Ok "Login only - done."
    exit 0
}

$listJson = & $cf tunnel list --output json 2>$null
$existing = $null
if ($listJson) {
    try {
        $tunnels = $listJson | ConvertFrom-Json
        $existing = @($tunnels | Where-Object { $_.name -eq $TunnelName }) | Select-Object -First 1
    } catch {}
}

if ($existing) {
    $tunnelId = [string]$existing.id
    Write-Ok "Using existing tunnel: $TunnelName ($tunnelId)"
} else {
    Write-Info "Creating tunnel: $TunnelName"
    & $cf tunnel create $TunnelName
    $listJson = & $cf tunnel list --output json 2>$null
    $tunnels = $listJson | ConvertFrom-Json
    $existing = @($tunnels | Where-Object { $_.name -eq $TunnelName }) | Select-Object -First 1
    if (-not $existing) { throw "Tunnel create failed - check Cloudflare dashboard." }
    $tunnelId = [string]$existing.id
    Write-Ok "Created tunnel: $tunnelId"
}

$credFile = Join-Path $cfDir "$tunnelId.json"
if (-not (Test-Path $credFile)) {
    throw "Missing credentials file: $credFile"
}

$labDir = Join-Path $Root "lab_data"
if (-not (Test-Path $labDir)) { New-Item -ItemType Directory -Path $labDir | Out-Null }
$configPath = Join-Path $labDir "cloudflared-chronos.yml"

# Build YAML without here-string quirks
$yamlLines = @(
    "# Chronos Command - named Cloudflare tunnel (setup_domain_tunnel.ps1)",
    "tunnel: $tunnelId",
    "credentials-file: '$credFile'",
    "",
    "ingress:",
    "  - hostname: $PublicHost",
    "    service: http://127.0.0.1:$Port",
    "    originRequest:",
    "      noTLSVerify: true",
    "      connectTimeout: 30s",
    "      keepAliveTimeout: 90s",
    "  - service: http_status:404"
)
Set-Content -Path $configPath -Value ($yamlLines -join "`n") -Encoding UTF8
Write-Ok "Wrote $configPath"

Write-Info "Creating DNS route: $PublicHost -> tunnel $TunnelName"
$ErrorActionPreference = "Continue"
$dnsOut = & $cf tunnel route dns --overwrite-dns $TunnelName $PublicHost 2>&1
$dnsOut | ForEach-Object { Write-Host "  $_" }
if ($LASTEXITCODE -ne 0) {
    Write-Host "DNS auto-route failed (often apex). Add manually in Cloudflare DNS:" -ForegroundColor Yellow
    Write-Host "  Type: CNAME" -ForegroundColor Yellow
    Write-Host "  Name: @   (or the subdomain)" -ForegroundColor Yellow
    Write-Host "  Target: $tunnelId.cfargotunnel.com" -ForegroundColor Yellow
    Write-Host "  Proxy: ON (orange cloud)" -ForegroundColor Yellow
}
$ErrorActionPreference = "Stop"

$cfgObj = [ordered]@{
    public_url  = $PublicUrl
    public_host = $PublicHost
    domain      = $Domain
    subdomain   = $Subdomain
    tunnel_name = $TunnelName
    tunnel_id   = $tunnelId
    config_path = $configPath
    port        = $Port
    updated_utc = (Get-Date).ToUniversalTime().ToString("o")
}
$cfgPath = Join-Path $labDir "domain_tunnel.json"
($cfgObj | ConvertTo-Json) | Set-Content -Path $cfgPath -Encoding UTF8
Write-Ok "Wrote $cfgPath"

[Environment]::SetEnvironmentVariable("CHRONOS_CF_TUNNEL_NAME", $TunnelName, "User")
[Environment]::SetEnvironmentVariable("CHRONOS_PUBLIC_URL", $PublicUrl, "User")
$env:CHRONOS_CF_TUNNEL_NAME = $TunnelName
$env:CHRONOS_PUBLIC_URL = $PublicUrl
Write-Ok "User env set for tunnel + public URL"

$logs = Join-Path $Root "logs"
if (-not (Test-Path $logs)) { New-Item -ItemType Directory -Path $logs | Out-Null }
Set-Content -Path (Join-Path $logs "remote_uat_url.txt") -Value $PublicUrl -Encoding UTF8
$live = @(
    "CHRONOS ALWAYS-ON REMOTE UAT (FIXED DOMAIN)",
    "URL: $PublicUrl",
    "Tester:",
    "  1) Open $PublicUrl",
    "  2) Click: Enter full product (Administration)",
    "  3) Full left nav + UAT Lab map every page",
    "Login: admin/admin  (optional supervisor/supervisor | officer/officer)",
    "This PC: keep awake while remotes test",
    "Tunnel: named ($TunnelName) - URL stays the same across restarts"
)
Set-Content -Path (Join-Path $logs "remote_uat_live.txt") -Value ($live -join "`r`n") -Encoding UTF8

if (-not $SkipRestart) {
    Write-Info "Restarting always-on UAT with named tunnel..."
    $runner = Join-Path $Root "scripts\always_on_uat.ps1"
    & powershell -NoProfile -ExecutionPolicy Bypass -File $runner -Stop -Port $Port 2>$null
    Start-Sleep -Seconds 2
    Start-Process -FilePath "powershell.exe" `
        -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-File", $runner, "-Port", "$Port", "-NoReload") `
        -WorkingDirectory $Root
    Write-Info "Waiting for local Chronos :$Port ..."
    $deadline = (Get-Date).AddSeconds(90)
    $up = $false
    while ((Get-Date) -lt $deadline) {
        try {
            $c = New-Object System.Net.Sockets.TcpClient
            $iar = $c.BeginConnect("127.0.0.1", $Port, $null, $null)
            if ($iar.AsyncWaitHandle.WaitOne(500, $false)) {
                $c.EndConnect($iar) | Out-Null
                $c.Close()
                $up = $true
                break
            }
            $c.Close()
        } catch {}
        Start-Sleep -Seconds 2
    }
    if ($up) { Write-Ok "Chronos listening on :$Port" }
    else { Write-Host "Chronos not up yet - check logs\always_on_uat.log" -ForegroundColor Yellow }
}

Write-Host ""
Write-Ok "========================================"
Write-Ok " FIXED PUBLIC URL"
Write-Ok " $PublicUrl"
Write-Ok "========================================"
Write-Host ""
Write-Host "Next:"
Write-Host "  1. Wait ~30-60s for DNS, then open: $PublicUrl"
Write-Host "  2. Login admin / admin"
Write-Host "  3. If DNS fails: Cloudflare DNS -> CNAME @ or chronos -> $tunnelId.cfargotunnel.com (Proxied ON)"
Write-Host ""
Write-Host "Share only: $PublicUrl"
