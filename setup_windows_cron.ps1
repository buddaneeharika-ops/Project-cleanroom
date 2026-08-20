$Action = New-ScheduledTaskAction -Execute "python" -Argument "C:\Work\Form 20 Backlog Dashboard\cron_daily_state_glance.py" -WorkingDirectory "C:\Work\Form 20 Backlog Dashboard"
$Trigger = New-ScheduledTaskTrigger -Daily -At 12:00AM
$Principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -DontStopOnIdleEnd -ExecutionTimeLimit (New-TimeSpan -Hours 2)

Register-ScheduledTask -TaskName "Votex Nightly Dashboard Aggregation" -Action $Action -Trigger $Trigger -Principal $Principal -Settings $Settings -Description "Runs the heavy DB queries and builds the JSON cache for the State Glance Dashboard every night at midnight." -Force

Write-Host "Scheduled Task 'Votex Nightly Dashboard Aggregation' created successfully!"
Write-Host "It will run silently in the background every night at 12:00 AM."
