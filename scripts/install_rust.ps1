# Install Rust toolchain on Windows (rustup).
# https://rustup.rs/

$ErrorActionPreference = "Stop"

if (Get-Command rustc -ErrorAction SilentlyContinue) {
    rustc --version
    cargo --version
    Write-Host "Rust already installed." -ForegroundColor Green
    exit 0
}

Write-Host "Installing Rust via rustup..." -ForegroundColor Cyan
Invoke-WebRequest -Uri "https://win.rustup.rs/x86_64" -OutFile "$env:TEMP\rustup-init.exe"
& "$env:TEMP\rustup-init.exe" -y --default-toolchain stable

$userCargo = Join-Path $env:USERPROFILE ".cargo\bin"
if (Test-Path $userCargo) {
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($userPath -notlike "*$userCargo*") {
        $newPath = if ($userPath) { $userPath + ';' + $userCargo } else { $userCargo }
        [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    }
}

Write-Host "Restart terminal, then: python dev.py build-rust" -ForegroundColor Green
