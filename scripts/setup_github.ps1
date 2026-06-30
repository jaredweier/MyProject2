# Link this repo to GitHub and push (enables .github/workflows/ci.yml).
# Usage: .\scripts\setup_github.ps1 -RepoUrl "https://github.com/YOU/Dodgeville_PD_Scheduler.git"

param(
    [Parameter(Mandatory = $true)]
    [string]$RepoUrl
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Test-Path ".git")) {
    Write-Error "Not a git repository."
}

$remote = git remote get-url origin 2>$null
if ($LASTEXITCODE -ne 0) {
    git remote add origin $RepoUrl
    Write-Host "Added remote origin: $RepoUrl"
} else {
    Write-Host "Remote origin already set: $remote"
}

# Ensure CI-critical paths are tracked (not logs/dist/build)
git add .gitignore .github/ .pre-commit-config.yaml requirements-dev.txt opencode.json .opencode/ AGENTS.md dev.py scripts/ tests/ ui/ logic/ docs/OPEN_SOURCE_TOOLING.md docs/UI_OBSERVATION.md docs/USAGE_MINIMIZATION.md .grok/skills/cost-efficient-workflow/
git add tests/ui_snapshots/baseline/*.png 2>$null

Write-Host @"

Next steps (manual):
  1. Review .gitignore — ensure logs/, dist/, *.db, terminals/ stay untracked
  2. git add -A   (or selective add)
  3. git commit -m "chore: agent tooling, CI, UI observation pipeline"
  4. git push -u origin master

GitHub Actions will run: doctor, preflight, check, ui-smoke, scenarios
"@ -ForegroundColor Cyan
