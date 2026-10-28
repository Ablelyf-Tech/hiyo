$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
& .\.venv\Scripts\python.exe -m pytest -q
if ($LASTEXITCODE -ne 0) { throw 'Backend tests failed' }
Push-Location dashboard
try {
    npm.cmd test
    if ($LASTEXITCODE -ne 0) { throw 'Frontend tests failed' }
    npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw 'Dashboard build failed' }
} finally { Pop-Location }
codex --version
if ($LASTEXITCODE -ne 0) { throw 'Codex CLI is unavailable' }
Write-Host 'Application checks passed. Validate Codex authentication/sandbox and scheduler on this Windows machine separately.'
