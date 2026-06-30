# Add Cursor CLI (cursor.cmd) to the Windows user PATH.
# Usage:
#   .\scripts\install_cursor_cli_path.ps1
#   .\scripts\install_cursor_cli_path.ps1 -CursorBinPath "C:\Users\You\AppData\Local\Programs\cursor\resources\app\bin"

param(
    [string]$CursorBinPath = "",
    [switch]$AddExpectedPath
)

$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent

function Find-CursorBin {
    param([string]$Override)

    if ($Override -and (Test-Path (Join-Path $Override "cursor.cmd"))) {
        return (Resolve-Path $Override).Path
    }

    $candidates = @(
        "$env:LOCALAPPDATA\Programs\cursor\resources\app\bin",
        "$env:LOCALAPPDATA\Programs\Cursor\resources\app\bin",
        "${env:ProgramFiles}\Cursor\resources\app\bin",
        "${env:ProgramFiles}\cursor\resources\app\bin",
        "${env:ProgramFiles(x86)}\Cursor\resources\app\bin"
    )

    foreach ($dir in $candidates) {
        if (Test-Path (Join-Path $dir "cursor.cmd")) {
            return (Resolve-Path $dir).Path
        }
    }

    # Search LOCALAPPDATA\Programs (depth-limited)
    $programs = Join-Path $env:LOCALAPPDATA "Programs"
    if (Test-Path $programs) {
        $hit = Get-ChildItem $programs -Recurse -Filter "cursor.cmd" -ErrorAction SilentlyContinue -Depth 5 |
            Select-Object -First 1
        if ($hit) {
            return $hit.DirectoryName
        }
    }

    return $null
}

Write-Host "Dodgeville PD - install Cursor CLI on PATH"
Write-Host ("-" * 40)

$bin = Find-CursorBin -Override $CursorBinPath
if (-not $bin) {
    $expected = Join-Path $env:LOCALAPPDATA "Programs\cursor\resources\app\bin"
    Write-Host "Could not find cursor.cmd on this machine." -ForegroundColor Yellow
    if ($AddExpectedPath -or $CursorBinPath) {
        if ($CursorBinPath) { $expected = $CursorBinPath }
        Write-Host "Adding expected Cursor CLI path anyway: $expected"
        $bin = $expected
    } else {
        Write-Host ""
        Write-Host "Option A (easiest): In Cursor press Ctrl+Shift+P and run:"
        Write-Host "  Shell Command: Install 'cursor' command in PATH"
        Write-Host ""
        Write-Host "Option B: Add expected path now (works after Cursor install):"
        Write-Host "  .\scripts\install_cursor_cli_path.ps1 -AddExpectedPath"
        Write-Host ""
        Write-Host "Option C: Explicit bin folder:"
        Write-Host "  .\scripts\install_cursor_cli_path.ps1 -CursorBinPath $expected"
        exit 1
    }
}

$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if (-not $userPath) { $userPath = "" }

$normBin = $bin.TrimEnd([char]92)
$already = ($userPath -split ';' | Where-Object { $_.TrimEnd([char]92) -ieq $normBin }).Count -gt 0
if ($already) {
    Write-Host "Already on user PATH: $bin"
} else {
    $newPath = if ($userPath.Trim().Length -gt 0) { $userPath + ';' + $bin } else { $bin }
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    Write-Host "Added to user PATH: $bin"
}

# Current session
if ($env:Path -notlike "*$bin*") {
    $env:Path = $env:Path + ';' + $bin
}

Write-Host ""
Write-Host "Verify in a NEW terminal:"
Write-Host "  where cursor"
Write-Host "  cursor --version"
Write-Host ("-" * 40)

# Log for project tooling
$logDir = Join-Path $root "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
@{
    timestamp = (Get-Date).ToUniversalTime().ToString("o")
    cursor_bin = $bin
    user = $env:USERNAME
} | ConvertTo-Json | Set-Content -Path (Join-Path $logDir 'cursor_cli_path.json') -Encoding utf8

exit 0
