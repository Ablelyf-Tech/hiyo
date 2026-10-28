param(
    [Parameter(Mandatory=$true)][string]$ProjectsRoot,
    [string]$StateDirectory = "$env:LOCALAPPDATA\Hiyo",
    [int]$Port = 8787
)
$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $RepoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $Python)) { throw 'Run scripts\install.ps1 first' }
New-Item -ItemType Directory -Force -Path $ProjectsRoot | Out-Null
& $Python -m engineering_os.cli --home $StateDirectory serve --projects-root $ProjectsRoot --port $Port --dashboard (Join-Path $RepoRoot 'dashboard\dist')
exit $LASTEXITCODE
