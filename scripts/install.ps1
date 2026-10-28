# Run from a normal PowerShell window. Requires Python 3.11+, Git and Node.js 22+.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot
foreach ($Tool in @('git', 'node', 'npm', 'py')) {
    if (-not (Get-Command $Tool -ErrorAction SilentlyContinue)) { throw "Install prerequisite: $Tool" }
}
py -3 -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'Python virtual environment creation failed' }
& .\.venv\Scripts\python.exe -m pip install -r requirements-dev.lock
if ($LASTEXITCODE -ne 0) { throw 'Locked Python dependency installation failed' }
& .\.venv\Scripts\python.exe -m pip install --no-deps -e '.[test]'
if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed' }
Push-Location dashboard
try {
    npm.cmd ci --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) { throw 'Dashboard dependency installation failed' }
    npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw 'Dashboard build failed' }
} finally { Pop-Location }
& .\.venv\Scripts\python.exe -m pytest -q
if ($LASTEXITCODE -ne 0) { throw 'Backend tests failed' }
if (-not (Get-Command codex -ErrorAction SilentlyContinue)) {
    Write-Host 'Install Codex CLI with npm install -g @openai/codex, then run codex login.'
} else {
    codex --version
    if ($LASTEXITCODE -ne 0) { throw 'Codex CLI is unavailable' }
}
Write-Host 'Installed. Run .\scripts\start.ps1 -ProjectsRoot C:\Projects'
