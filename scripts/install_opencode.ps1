# Install OpenCode on Windows - run from project root.
# https://github.com/anomalyco/opencode

$ErrorActionPreference = "Stop"

Write-Host "Dodgeville PD Scheduler - OpenCode installer" -ForegroundColor Cyan

if (Get-Command opencode -ErrorAction SilentlyContinue) {
    opencode --version 2>$null
    Write-Host "OpenCode already installed." -ForegroundColor Green
    exit 0
}

function Install-FromGitHubRelease {
    $repo = "anomalyco/opencode"
    Write-Host "Fetching latest release from GitHub..."
    $headers = @{ "User-Agent" = "Dodgeville-Scheduler" }
    $uri = "https://api.github.com/repos/$repo/releases/latest"
    $release = Invoke-RestMethod -Uri $uri -Headers $headers
    $asset = $release.assets | Where-Object { $_.name -eq 'opencode-windows-x64.zip' } | Select-Object -First 1
    if (-not $asset) {
        $asset = $release.assets | Where-Object {
            $_.name -match '^opencode-windows-x64.*\.zip$' -and $_.name -notmatch 'arm64'
        } | Select-Object -First 1
    }
    if (-not $asset) {
        $asset = $release.assets | Where-Object { $_.name -eq 'opencode-desktop-win-x64.exe' } | Select-Object -First 1
    }
    if (-not $asset) {
        Write-Host "No Windows zip asset found in $($release.tag_name)." -ForegroundColor Yellow
        return $false
    }

    $dest = Join-Path $env:LOCALAPPDATA "opencode"
    New-Item -ItemType Directory -Force -Path $dest | Out-Null
    Write-Host ("Downloading " + $asset.name + "...")
    $download = Join-Path $env:TEMP ("opencode-" + $release.tag_name + "-" + $asset.name)
    Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $download -Headers $headers

    if ($asset.name -like '*.exe') {
        $exePath = Join-Path $dest "opencode.exe"
        Copy-Item $download $exePath -Force
        Remove-Item $download -Force -ErrorAction SilentlyContinue
        $exe = Get-Item $exePath
    } else {
        Expand-Archive -Path $download -DestinationPath $dest -Force
        Remove-Item $download -Force -ErrorAction SilentlyContinue
        $exe = Get-ChildItem -Path $dest -Recurse -Filter "opencode.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
    }
    if (-not $exe) {
        Write-Host ("Downloaded archive but opencode.exe not found under " + $dest) -ForegroundColor Yellow
        return $false
    }

    $bin = $exe.Directory.FullName
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($userPath -notlike ("*" + $bin + "*")) {
        if ($userPath) {
            $newPath = $userPath + ';' + $bin
        } else {
            $newPath = $bin
        }
        [Environment]::SetEnvironmentVariable('Path', $newPath, 'User')
        if ($env:Path) {
            $env:Path = $env:Path + ';' + $bin
        } else {
            $env:Path = $bin
        }
    }
    Write-Host ("Installed to " + $bin) -ForegroundColor Green
    & $exe.FullName --version
    return $true
}

if (Get-Command winget -ErrorAction SilentlyContinue) {
    Write-Host "Trying winget..."
    winget install --id Anomaly.OpenCode -e --accept-source-agreements --accept-package-agreements 2>$null
    if ($LASTEXITCODE -eq 0 -and (Get-Command opencode -ErrorAction SilentlyContinue)) { exit 0 }
}

if (Get-Command npm -ErrorAction SilentlyContinue) {
    Write-Host "Trying npm..."
    npm install -g opencode-ai@latest 2>$null
    if ($LASTEXITCODE -eq 0 -and (Get-Command opencode -ErrorAction SilentlyContinue)) { exit 0 }
}

if (Get-Command scoop -ErrorAction SilentlyContinue) {
    Write-Host "Trying scoop..."
    scoop install opencode 2>$null
    if ($LASTEXITCODE -eq 0 -and (Get-Command opencode -ErrorAction SilentlyContinue)) { exit 0 }
}

if (Install-FromGitHubRelease) {
    Write-Host "OpenCode installed via GitHub release." -ForegroundColor Green
    Write-Host "Restart terminal, then run: opencode" -ForegroundColor Cyan
    exit 0
}

Write-Host "Could not auto-install OpenCode." -ForegroundColor Yellow
Write-Host "  winget install Anomaly.OpenCode"
Write-Host "  npm install -g opencode-ai"
Write-Host "  scoop install opencode"
Write-Host "  https://github.com/anomalyco/opencode/releases"
Write-Host ("Project root: " + (Split-Path $PSScriptRoot -Parent))
exit 1
