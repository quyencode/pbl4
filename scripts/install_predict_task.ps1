param(
    [string]$DeviceId = "node-01",
    [string]$PythonLauncher = "py.exe",
    [string]$TaskName = "PBL4-AirQuality-Predict"
)

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$predictScript = Join-Path $repoRoot "ai\predict.py"
if (-not (Test-Path -LiteralPath $predictScript)) {
    throw "Không tìm thấy ai\predict.py trong $repoRoot"
}

$arguments = "-3.12 `"$predictScript`" --device_id $DeviceId"
$action = New-ScheduledTaskAction -Execute $PythonLauncher -Argument $arguments -WorkingDirectory $repoRoot
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Hours 1) -RepetitionDuration (New-TimeSpan -Days 3650)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 1)
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings `
    -Description "Chạy ai\predict.py cho $DeviceId mỗi giờ; do BPL4 AI schedule." -Force | Out-Null
Write-Host "Đã tạo Scheduled Task '$TaskName' chạy mỗi giờ cho $DeviceId."
Write-Host "Xem trạng thái bằng: Get-ScheduledTask -TaskName '$TaskName'"
