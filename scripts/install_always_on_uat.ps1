# Install Chronos always-on remote UAT at Windows logon (+ start now).
param(
    [switch]$Uninstall,
    [switch]$NoStartNow,
    [int]$Port = 8080
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$TaskName = "ChronosAlwaysOnUAT"
$Runner = Join-Path $Root "scripts\always_on_uat.ps1"
$Wrapper = Join-Path $Root "scripts\always_on_uat_logon.cmd"

if ($Uninstall) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    & powershell -NoProfile -ExecutionPolicy Bypass -File $Runner -Stop -Port $Port
    Write-Host "Uninstalled $TaskName and stopped UAT processes."
    exit 0
}

if (-not (Test-Path $Runner)) { throw "Missing $Runner" }

# cloudflared on PATH for scheduled tasks (system may not have user PATH fully)
$cfDir = "${env:ProgramFiles(x86)}\cloudflared"
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ((Test-Path "$cfDir\cloudflared.exe") -and ($userPath -notlike "*$cfDir*")) {
    [Environment]::SetEnvironmentVariable("Path", ($userPath.TrimEnd(";") + ";" + $cfDir), "User")
    Write-Host "Ensured cloudflared on User PATH"
}

# Hidden-ish logon wrapper (cmd → powershell)
$cmd = @"
@echo off
cd /d "$Root"
set PATH=%PATH%;$cfDir
powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "$Runner" -Port $Port
"@
Set-Content -Path $Wrapper -Value $cmd -Encoding ASCII

$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$Wrapper`"" -WorkingDirectory $Root
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 5 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null
Write-Host "Installed scheduled task: $TaskName (At logon for $env:USERNAME)"
Write-Host "  Runner: $Runner"
Write-Host "  URL file after start: $Root\logs\remote_uat_url.txt"

if (-not $NoStartNow) {
    Write-Host "Starting now..."
    # Stop any prior instance then launch supervisor in background
    & powershell -NoProfile -ExecutionPolicy Bypass -File $Runner -Stop -Port $Port 2>$null
    Start-Process -FilePath "powershell.exe" `
        -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-File", $Runner, "-Port", "$Port") `
        -WorkingDirectory $Root
    Write-Host "Waiting for public URL..."
    $urlFile = Join-Path $Root "logs\remote_uat_url.txt"
    $deadline = (Get-Date).AddSeconds(90)
    while ((Get-Date) -lt $deadline) {
        if (Test-Path $urlFile) {
            $u = (Get-Content $urlFile -Raw).Trim()
            if ($u -match '^https://') {
                Write-Host ""
                Write-Host "LIVE URL: $u" -ForegroundColor Green
                Write-Host "Tester: open URL then Enter full product (Administration)"
                Write-Host "Card: logs\remote_uat_live.txt"
                break
            }
        }
        Start-Sleep -Seconds 2
    }
    if (-not (Test-Path $urlFile)) {
        Write-Host "URL not ready yet - check logs\always_on_uat.log"
    }
}

Write-Host ""
Write-Host "Tips:"
Write-Host "  - PC Sleep: Settings > System > Power > Sleep = Never (while testing remotely)"
Write-Host "  - Code edits: always-on restarts Chronos automatically; testers Ctrl+F5"
Write-Host "  - Stable URL (optional): Cloudflare named tunnel + CHRONOS_CF_TUNNEL_NAME / CHRONOS_PUBLIC_URL"
Write-Host "  - Stop: Uninstall Always-On UAT.bat  OR  scripts\always_on_uat.ps1 -Stop"
