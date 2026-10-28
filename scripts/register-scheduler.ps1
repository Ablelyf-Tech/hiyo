param(
    [Parameter(Mandatory=$true)][string]$ProjectsRoot,
    [string]$StateDirectory = "$env:LOCALAPPDATA\Grofloo",
    [string]$TaskName = 'Grofloo Engineering OS'
)
$ErrorActionPreference = 'Stop'
# Register the private dashboard only, never automatically authorize paid model runs.
# Run as the current interactive user without elevated privileges.
foreach ($Value in @($ProjectsRoot, $StateDirectory)) {
    if ($Value.Contains('"') -or $Value.Contains("`n") -or $Value.Contains("`r")) { throw 'Invalid path' }
}
$StartScript = Join-Path $PSScriptRoot 'start.ps1'
if ($StartScript.Contains('"')) { throw 'Invalid script path' }
$Arguments = '-NoProfile -File "{0}" -ProjectsRoot "{1}" -StateDirectory "{2}"' -f $StartScript, $ProjectsRoot, $StateDirectory
$Action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $Arguments
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name)
$Principal = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
$Settings = New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew -StartWhenAvailable
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Principal $Principal -Settings $Settings -Description 'Private Grofloo dashboard. Interrupted tasks require inspection before retry.'
Write-Host "Registered $TaskName. Remove with Unregister-ScheduledTask -TaskName '$TaskName'."
