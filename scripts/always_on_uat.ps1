# Chronos Command - always-on remote UAT (logon; crash restart; code-change restart)
#
# Install (logon):  powershell -File scripts\install_always_on_uat.ps1
# Run now:          powershell -File scripts\always_on_uat.ps1
# Stop:             powershell -File scripts\always_on_uat.ps1 -Stop
#
param(
    [int]$Port = 8080,
    [switch]$Stop,
    [switch]$NoReload,
    [int]$WatchSeconds = 3,
    [int]$HealthSeconds = 15
)

$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$PidDir = Join-Path $Root "lab_data"
$StateFile = Join-Path $PidDir "always_on_uat.state.json"
$UrlFile = Join-Path $Root "logs\remote_uat_url.txt"
$LiveFile = Join-Path $Root "logs\remote_uat_live.txt"
$LogFile = Join-Path $Root "logs\always_on_uat.log"
$TunnelLog = Join-Path $Root "logs\remote_tunnel.err.log"
$TunnelOut = Join-Path $Root "logs\remote_tunnel.log"

function Write-Log([string]$Msg) {
    $line = "{0:u} {1}" -f (Get-Date).ToUniversalTime(), $Msg
    Add-Content -Path $LogFile -Value $line -Encoding UTF8 -ErrorAction SilentlyContinue
    Write-Host $line
}

function Ensure-Dirs {
    foreach ($d in @($PidDir, (Join-Path $Root "logs"))) {
        if (-not (Test-Path $d)) { New-Item -ItemType Directory -Path $d | Out-Null }
    }
}

function Test-PortOpen([int]$P) {
    try {
        $c = New-Object System.Net.Sockets.TcpClient
        $iar = $c.BeginConnect("127.0.0.1", $P, $null, $null)
        $ok = $iar.AsyncWaitHandle.WaitOne(800, $false)
        if (-not $ok) { $c.Close(); return $false }
        $c.EndConnect($iar) | Out-Null
        $c.Close()
        return $true
    } catch { return $false }
}

function Resolve-Cloudflared {
    if (Get-Command cloudflared -ErrorAction SilentlyContinue) { return "cloudflared" }
    foreach ($p in @(
            "${env:ProgramFiles(x86)}\cloudflared\cloudflared.exe",
            "$env:ProgramFiles\cloudflared\cloudflared.exe"
        )) {
        if (Test-Path $p) { return $p }
    }
    return $null
}

function Stop-PortListeners([int]$P) {
    try {
        Get-NetTCPConnection -LocalPort $P -State Listen -ErrorAction SilentlyContinue | ForEach-Object {
            if ($_.OwningProcess) {
                Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
                Write-Log "stopped PID $($_.OwningProcess) on :$P"
            }
        }
    } catch {}
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match 'main\.py' } |
        ForEach-Object {
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
            Write-Log "stopped python main.py PID $($_.ProcessId)"
        }
}

function Stop-AlwaysOn {
    Ensure-Dirs
    Write-Log "Stopping always-on UAT..."
    if (Test-Path $StateFile) {
        try {
            $st = Get-Content $StateFile -Raw | ConvertFrom-Json
            foreach ($id in @($st.server_pid, $st.tunnel_pid, $st.supervisor_pid)) {
                if ($id) { Stop-Process -Id ([int]$id) -Force -ErrorAction SilentlyContinue }
            }
        } catch {}
        Remove-Item $StateFile -Force -ErrorAction SilentlyContinue
    }
    Stop-PortListeners $Port
    Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Write-Log "Stopped."
}

function Import-DomainTunnelConfig {
    # Prefer project file (works for scheduled tasks) over User env alone
    $cfgPath = Join-Path $Root "lab_data\domain_tunnel.json"
    if (-not (Test-Path $cfgPath)) { return $null }
    try {
        $d = Get-Content $cfgPath -Raw | ConvertFrom-Json
        if ($d.tunnel_name) { $env:CHRONOS_CF_TUNNEL_NAME = [string]$d.tunnel_name }
        if ($d.public_url) { $env:CHRONOS_PUBLIC_URL = [string]$d.public_url }
        if ($d.config_path -and (Test-Path ([string]$d.config_path))) {
            $env:CHRONOS_CF_CONFIG = [string]$d.config_path
        } else {
            $fallback = Join-Path $Root "lab_data\cloudflared-chronos.yml"
            if (Test-Path $fallback) { $env:CHRONOS_CF_CONFIG = $fallback }
        }
        return $d
    } catch {
        Write-Log "WARN: could not read domain_tunnel.json: $_"
        return $null
    }
}

function Set-UatEnv {
    $env:SCHEDULER_UAT_LAB = "1"
    $env:SCHEDULER_DB_PATH = Join-Path $PidDir "virtual_uat.db"
    $env:SCHEDULER_UI_MODE = "web"
    $env:SCHEDULER_HOST = "127.0.0.1"
    $env:SCHEDULER_PORT = "$Port"
    $env:SCHEDULER_SKIP_GATES = "1"
    $env:SCHEDULER_SKIP_STARTUP_GATES = "1"
    # Long reconnect keeps NiceGUI socket.io sessions through Cloudflare blips
    $env:SCHEDULER_RECONNECT_TIMEOUT = "180"
    $env:SCHEDULER_UAT_STABLE = "1"
    Import-DomainTunnelConfig | Out-Null
    $secretFile = Join-Path $Root "storage_secret.txt"
    if (-not $env:SCHEDULER_STORAGE_SECRET) {
        if (Test-Path $secretFile) {
            $env:SCHEDULER_STORAGE_SECRET = (Get-Content $secretFile -Raw).Trim()
        } else {
            $bytes = New-Object byte[] 32
            [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
            $env:SCHEDULER_STORAGE_SECRET = ($bytes | ForEach-Object { $_.ToString("x2") }) -join ""
            Set-Content -Path $secretFile -Value $env:SCHEDULER_STORAGE_SECRET -Encoding ASCII
        }
    }
}

function Test-ChronosHttp([int]$P) {
    try {
        $req = [System.Net.HttpWebRequest]::Create("http://127.0.0.1:$P/")
        $req.Method = "GET"
        $req.Timeout = 4000
        $req.ReadWriteTimeout = 4000
        $resp = $req.GetResponse()
        $code = [int]$resp.StatusCode
        $resp.Close()
        return ($code -ge 200 -and $code -lt 500)
    } catch {
        return $false
    }
}

function Test-ProcessAlive($Proc) {
    if (-not $Proc) { return $false }
    try {
        $p = Get-Process -Id $Proc.Id -ErrorAction SilentlyContinue
        return [bool]$p
    } catch { return $false }
}

function Invoke-LabPrep {
    Write-Log "prepare_uat_lab..."
    & python -c "import os; os.environ['SCHEDULER_UAT_LAB']='1'; os.environ['SCHEDULER_DB_PATH']=r'$($env:SCHEDULER_DB_PATH)'; from logic.uat_lab import prepare_uat_lab; print(prepare_uat_lab())" 2>&1 | ForEach-Object { Write-Log "$_" }
}

function Start-Chronos {
    Stop-PortListeners $Port
    Start-Sleep -Seconds 1
    $argList = @("main.py", "--web", "--host", "127.0.0.1", "--port", "$Port")
    $outLog = Join-Path $Root "logs\chronos_uat.out.log"
    $errLog = Join-Path $Root "logs\chronos_uat.err.log"
    Write-Log "Starting Chronos: python $($argList -join ' ')"
    # Redirect stdout/stderr so silent crashes are diagnosable
    $p = Start-Process -FilePath "python" -ArgumentList $argList -WorkingDirectory $Root -PassThru `
        -WindowStyle Hidden -RedirectStandardOutput $outLog -RedirectStandardError $errLog
    $deadline = (Get-Date).AddSeconds(90)
    while (-not (Test-PortOpen $Port)) {
        if ((Get-Date) -gt $deadline) {
            Write-Log "FAIL: Chronos did not bind :$Port (see logs\chronos_uat.err.log)"
            return $null
        }
        if (-not (Test-ProcessAlive $p)) {
            Write-Log "FAIL: Chronos exited early code=$($p.ExitCode) (see logs\chronos_uat.err.log)"
            return $null
        }
        Start-Sleep -Milliseconds 500
    }
    # Require HTTP 200-class response, not just TCP accept
    $httpOk = $false
    for ($i = 0; $i -lt 20; $i++) {
        if (Test-ChronosHttp $Port) { $httpOk = $true; break }
        Start-Sleep -Milliseconds 500
    }
    if (-not $httpOk) {
        Write-Log "WARN: port open but HTTP not ready yet"
    }
    Write-Log "Chronos up PID=$($p.Id) http=$(if ($httpOk) { 'ok' } else { 'pending' })"
    return $p
}

function Write-LiveCard([string]$Url) {
    $lines = @(
        "CHRONOS ALWAYS-ON REMOTE UAT",
        "URL: $Url",
        "Tester:",
        "  1) Open URL",
        "  2) Click: Enter full product (Administration)",
        "  3) Full left nav + UAT Lab map every page",
        "Optional: supervisor/supervisor | officer/officer",
        "This PC: keep awake (Sleep=Never recommended while remotes test)",
        "Code changes: auto-restart Chronos; testers Ctrl+F5",
        "URL file: logs\remote_uat_url.txt",
        "Stop: scripts\always_on_uat.ps1 -Stop  OR  Uninstall Always-On UAT.bat"
    )
    Set-Content -Path $LiveFile -Value ($lines -join "`r`n") -Encoding UTF8
}

function Start-Tunnel {
    $cf = Resolve-Cloudflared
    if (-not $cf) {
        Write-Log "FAIL: cloudflared not found"
        return $null
    }
    Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Remove-Item $TunnelLog, $TunnelOut -Force -ErrorAction SilentlyContinue

    Import-DomainTunnelConfig | Out-Null
    $named = ""
    if ($env:CHRONOS_CF_TUNNEL_NAME) { $named = $env:CHRONOS_CF_TUNNEL_NAME.Trim() }
    $cfgFile = ""
    if ($env:CHRONOS_CF_CONFIG) { $cfgFile = $env:CHRONOS_CF_CONFIG.Trim() }
    if (-not $cfgFile) {
        $fallback = Join-Path $Root "lab_data\cloudflared-chronos.yml"
        if (Test-Path $fallback) { $cfgFile = $fallback }
    }

    # Prefer named/fixed-domain tunnel (stable hostname, better for WebSockets)
    if ($cfgFile -and (Test-Path $cfgFile)) {
        Write-Log "Starting named tunnel config: $cfgFile"
        $p = Start-Process -FilePath $cf -ArgumentList @("tunnel", "--config", $cfgFile, "run") `
            -WorkingDirectory $Root -PassThru -WindowStyle Hidden `
            -RedirectStandardOutput $TunnelOut -RedirectStandardError $TunnelLog
        Start-Sleep -Seconds 4
        if ($env:CHRONOS_PUBLIC_URL) {
            $u = $env:CHRONOS_PUBLIC_URL.Trim()
            Set-Content -Path $UrlFile -Value $u -Encoding UTF8
            Write-LiveCard $u
            Write-Log "Public URL (fixed domain): $u"
        } elseif ($named) {
            Write-Log "Named tunnel $named running - set CHRONOS_PUBLIC_URL or lab_data/domain_tunnel.json"
        }
        return $p
    }
    if ($named) {
        Write-Log "Starting named tunnel: $named"
        $p = Start-Process -FilePath $cf -ArgumentList @("tunnel", "run", $named) `
            -WorkingDirectory $Root -PassThru -WindowStyle Hidden `
            -RedirectStandardOutput $TunnelOut -RedirectStandardError $TunnelLog
        Start-Sleep -Seconds 3
        if ($env:CHRONOS_PUBLIC_URL) {
            $u = $env:CHRONOS_PUBLIC_URL.Trim()
            Set-Content -Path $UrlFile -Value $u -Encoding UTF8
            Write-LiveCard $u
        }
        return $p
    }

    Write-Log "Starting quick tunnel to http://127.0.0.1:$Port (ephemeral URL - prefer Setup Domain Tunnel.bat)"
    $p = Start-Process -FilePath $cf -ArgumentList @("tunnel", "--url", "http://127.0.0.1:$Port", "--protocol", "http2") `
        -WorkingDirectory $Root -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput $TunnelOut -RedirectStandardError $TunnelLog

    $url = $null
    for ($i = 0; $i -lt 45; $i++) {
        Start-Sleep -Seconds 1
        $txt = ""
        if (Test-Path $TunnelLog) { $txt += Get-Content $TunnelLog -Raw -ErrorAction SilentlyContinue }
        if (Test-Path $TunnelOut) { $txt += Get-Content $TunnelOut -Raw -ErrorAction SilentlyContinue }
        if ($txt -match 'https://[a-z0-9-]+\.trycloudflare\.com') {
            $url = $Matches[0]
            break
        }
        if ($p.HasExited) {
            Write-Log "FAIL: tunnel exited early"
            return $null
        }
    }
    if ($url) {
        Set-Content -Path $UrlFile -Value $url -Encoding UTF8
        Write-Log "Public URL: $url"
        Write-LiveCard $url
    } else {
        Write-Log "WARN: tunnel URL not parsed yet - check $TunnelLog"
    }
    return $p
}

function Get-CodeSignature {
    # Signature must NOT include generated assets written on every Chronos boot
    # (gui/static/chronos.css is synced from GLOBAL_CSS in shell.apply_theme).
    # Watching *.css caused a restart loop: start → write css → sig change → restart.
    # Source of truth for live product: Python modules only.
    $paths = @(
        (Join-Path $Root "gui"),
        (Join-Path $Root "logic"),
        (Join-Path $Root "config.py"),
        (Join-Path $Root "main.py"),
        (Join-Path $Root "database.py"),
        (Join-Path $Root "validators.py"),
        (Join-Path $Root "seed_data.py")
    )
    $excludeDirNames = @(
        "static", "__pycache__", ".pytest_cache", "node_modules", ".nicegui"
    )
    $sum = [int64]0
    foreach ($p in $paths) {
        if (Test-Path $p -PathType Leaf) {
            $i = Get-Item $p
            $sum = $sum -bxor ([int64]$i.LastWriteTimeUtc.Ticks) -bxor $i.Length
        } elseif (Test-Path $p) {
            Get-ChildItem $p -Recurse -Filter "*.py" -File -ErrorAction SilentlyContinue |
                Where-Object {
                    $rel = $_.FullName.Substring($Root.Length).TrimStart('\', '/')
                    $parts = $rel -split '[\\/]'
                    -not ($parts | Where-Object { $excludeDirNames -contains $_ })
                } |
                ForEach-Object {
                    $sum = $sum -bxor ([int64]$_.LastWriteTimeUtc.Ticks) -bxor $_.Length
                }
        }
    }
    return $sum
}

function Save-State($Server, $Tunnel) {
    $obj = [ordered]@{
        updated        = (Get-Date).ToUniversalTime().ToString("o")
        port           = $Port
        server_pid     = if ($Server) { $Server.Id } else { $null }
        tunnel_pid     = if ($Tunnel) { $Tunnel.Id } else { $null }
        supervisor_pid = $PID
        url            = if (Test-Path $UrlFile) { (Get-Content $UrlFile -Raw).Trim() } else { "" }
        reload         = -not $NoReload
    }
    ($obj | ConvertTo-Json) | Set-Content -Path $StateFile -Encoding UTF8
}

# --- entry ---
Ensure-Dirs
if (-not (Test-Path $LogFile)) { New-Item -ItemType File -Path $LogFile | Out-Null }

if ($Stop) {
    Stop-AlwaysOn
    exit 0
}

if (Test-Path $StateFile) {
    try {
        $prev = Get-Content $StateFile -Raw | ConvertFrom-Json
        if ($prev.supervisor_pid -and (Get-Process -Id ([int]$prev.supervisor_pid) -ErrorAction SilentlyContinue)) {
            if ([int]$prev.supervisor_pid -ne $PID) {
                Write-Log "Already running supervisor PID=$($prev.supervisor_pid) - exit"
                if (Test-Path $UrlFile) { Write-Host "URL: $((Get-Content $UrlFile -Raw).Trim())" }
                exit 0
            }
        }
    } catch {}
}

Write-Log "=== Always-on UAT start (PID $PID) ==="
Set-UatEnv
Invoke-LabPrep

# Default STABLE: no code-watch restarts (public testers need a steady WebSocket).
# Opt-in live reload: set CHRONOS_UAT_RELOAD=1 or pass without -NoReload after env.
if ($NoReload) {
    $useReload = $false
} elseif ($env:CHRONOS_UAT_RELOAD -eq "1") {
    $useReload = $true
} else {
    $useReload = $false
    Write-Log "Stable mode: code-watch reload OFF (set CHRONOS_UAT_RELOAD=1 to enable)"
}

$server = Start-Chronos
$tunnel = Start-Tunnel
if (-not $server) { Write-Log "Cannot start without Chronos"; exit 1 }
if (-not $tunnel) { Write-Log "WARN: tunnel missing - local only :$Port" }

Save-State $server $tunnel
$codeSig = Get-CodeSignature
$lastRestart = Get-Date
$failStreak = 0

Write-Log "Supervisor loop (watch=$WatchSeconds health=$HealthSeconds reload=$useReload)"
while ($true) {
    Start-Sleep -Seconds $HealthSeconds

    $serverAlive = Test-ProcessAlive $server
    $tunnelAlive = Test-ProcessAlive $tunnel
    $portOpen = Test-PortOpen $Port
    $httpOk = if ($portOpen) { Test-ChronosHttp $Port } else { $false }

    if (-not $serverAlive -or -not $portOpen -or -not $httpOk) {
        $failStreak++
        Write-Log "Chronos unhealthy (alive=$serverAlive port=$portOpen http=$httpOk streak=$failStreak) - restarting"
        # One quick retry of health before hard restart (avoid thrash on slow boot)
        if ($failStreak -lt 2 -and $portOpen) {
            Start-Sleep -Seconds 2
            if (Test-ChronosHttp $Port) {
                Write-Log "HTTP recovered without restart"
                $failStreak = 0
            }
        }
        if ($failStreak -ge 1 -and -not (Test-ChronosHttp $Port)) {
            try { Invoke-LabPrep } catch {}
            $server = Start-Chronos
            $codeSig = Get-CodeSignature
            $lastRestart = Get-Date
            $failStreak = 0
            Save-State $server $tunnel
        }
    } else {
        $failStreak = 0
    }

    if (-not $tunnelAlive) {
        Write-Log "Tunnel died - restarting (URL may change for quick tunnels)"
        $tunnel = Start-Tunnel
        Save-State $server $tunnel
    }

    if ($useReload) {
        $sig = Get-CodeSignature
        if ($sig -ne $codeSig) {
            # Debounce: require stable signature + cooldown so boot-time file
            # writes (or editor temp saves) cannot thrash the browser session.
            Start-Sleep -Seconds ([Math]::Max(3, $WatchSeconds))
            $sig2 = Get-CodeSignature
            $cooldownOk = ((Get-Date) - $lastRestart).TotalSeconds -gt 60
            if ($sig2 -ne $codeSig -and $sig2 -eq $sig -and $cooldownOk) {
                Write-Log "Code change detected - restarting Chronos (tunnel stays)"
                $server = Start-Chronos
                Start-Sleep -Seconds 2
                $codeSig = Get-CodeSignature
                $lastRestart = Get-Date
                Save-State $server $tunnel
                Write-Log "Dev tip: testers should Ctrl+F5 after big UI changes"
            } elseif ($sig2 -eq $codeSig) {
                Write-Log "Code sig flicker ignored (reverted)"
            }
        }
    }

    if (Test-Path $TunnelLog) {
        $txt = Get-Content $TunnelLog -Raw -ErrorAction SilentlyContinue
        if ($txt -match 'https://[a-z0-9-]+\.trycloudflare\.com') {
            $u = $Matches[0]
            $cur = if (Test-Path $UrlFile) { (Get-Content $UrlFile -Raw).Trim() } else { "" }
            if ($u -ne $cur) {
                Set-Content -Path $UrlFile -Value $u -Encoding UTF8
                Write-LiveCard $u
                Write-Log "URL updated: $u"
            }
        }
    }
    Save-State $server $tunnel
}
