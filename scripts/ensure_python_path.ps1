# Add Local Python install dirs to the current user's PATH (idempotent).
$localPython = Join-Path $env:LOCALAPPDATA "Python"
$toAdd = [System.Collections.Generic.List[string]]::new()

$bin = Join-Path $localPython "bin"
if (Test-Path $bin) { $toAdd.Add($bin) }

Get-ChildItem -Path $localPython -Directory -Filter "pythoncore-*" -ErrorAction SilentlyContinue |
    Sort-Object Name -Descending |
    ForEach-Object {
        $toAdd.Add($_.FullName)
        $scripts = Join-Path $_.FullName "Scripts"
        if (Test-Path $scripts) { $toAdd.Add($scripts) }
    }

if ($toAdd.Count -eq 0) {
    Write-Host "No Python install found under $localPython"
    Write-Host "Install from https://www.python.org/downloads/ (check 'Add to PATH')."
    exit 1
}

$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
$parts = @()
if ($userPath) {
    $parts = $userPath -split ";" | Where-Object { $_.Trim() -ne "" }
}

$changed = $false
foreach ($dir in ($toAdd | Select-Object -Unique)) {
    if ($parts -notcontains $dir) {
        $parts = , $dir + $parts
        $changed = $true
        Write-Host "Added to user PATH: $dir"
    }
}

if (-not $changed) {
    Write-Host "Python paths already on user PATH."
    foreach ($dir in $toAdd) { Write-Host "  $dir" }
    exit 0
}

$newPath = ($parts | Select-Object -Unique) -join ";"
[Environment]::SetEnvironmentVariable("Path", $newPath, "User")

# Refresh PATH for this shell session
$env:Path = $newPath + ";" + [Environment]::GetEnvironmentVariable("Path", "Machine")

Write-Host ""
Write-Host "User PATH updated. New terminals and double-click .bat files will see python and pip."
Write-Host "If a window was already open, close and reopen it (or sign out/in once)."
exit 0
