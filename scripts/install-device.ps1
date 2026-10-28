param([Parameter(Mandatory=$true)][string]$TicketFile,[string]$DeviceName='My computer',[string]$StateDirectory="$env:LOCALAPPDATA\HiyoDevice")
$ErrorActionPreference='Stop'
$RepoRoot=Split-Path -Parent $PSScriptRoot
$Python=Join-Path $RepoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $Python)) { throw 'Run install.ps1 first' }
& $Python -m pip install -e "${RepoRoot}[device]"
if ($LASTEXITCODE -ne 0) { throw 'Device dependencies failed' }
& $Python -m device_agent.agent --home $StateDirectory enroll --ticket-file $TicketFile --name $DeviceName
if ($LASTEXITCODE -ne 0) { throw 'Device enrollment failed' }
foreach ($Value in @($StateDirectory,$Python)) { if ($Value.Contains('"')) { throw 'Invalid path' } }
$Arguments='-m device_agent.agent --home "{0}" daily' -f $StateDirectory
$Action=New-ScheduledTaskAction -Execute $Python -Argument $Arguments -WorkingDirectory $RepoRoot
$Trigger=New-ScheduledTaskTrigger -Daily -At '09:00' -RandomDelay (New-TimeSpan -Hours 1)
$Principal=New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
$Settings=New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 35) -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 10)
Register-ScheduledTask -TaskName 'Hiyo Daily Device Sync' -Action $Action -Trigger $Trigger -Principal $Principal -Settings $Settings -Description 'Daily local-first approved workflow processing and signed dashboard sync. Runs for the enrolled user without elevation.'
Write-Host 'Enrolled. Daily sync is scheduled at 09:00 local time with up to one hour of jitter. Keep the user logged in; missed work remains queued. Local AI requires an already installed Ollama model.'
