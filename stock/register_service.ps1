# 金十快讯订阅 - Windows 计划任务注册脚本
$taskName = 'Jin10FlashSubscribe'
$scriptPath = 'J:\zss\stock\jin10_service.bat'
$workDir = 'J:\zss\stock'

Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

$action = New-ScheduledTaskAction -Execute $scriptPath -WorkingDirectory $workDir
$trigger = New-ScheduledTaskTrigger -AtStartup -RandomDelay (New-TimeSpan -Minutes 1)
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1)
$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force

Write-Host ('Task registered: ' + $taskName)
Write-Host ('Start: schtasks /run /tn ' + $taskName)
Write-Host 'Stop: taskkill /fi "imagename eq pythonw.exe" /f'
Write-Host 'Logs: J:\zss\stock\logs'
