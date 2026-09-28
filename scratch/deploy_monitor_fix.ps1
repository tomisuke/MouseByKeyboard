$ErrorActionPreference = 'Stop'
$workspace = 'C:\Users\Tomisuke\local\Activity\MouseByKeyboard'
$target = Join-Path $workspace 'KeyNavigator.exe'
$source = Join-Path $workspace 'dist_monitor_fix\KeyNavigator.exe'
$backup = Join-Path $workspace 'scratch\KeyNavigator.before-monitor-fix.exe'
Start-Transcript -Path (Join-Path $workspace 'scratch\deploy_monitor_fix.log') -Force
try {
    if (-not (Test-Path -LiteralPath $source)) { throw 'Built executable missing' }
    Copy-Item -LiteralPath $target -Destination $backup -Force
    $running = @(Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -eq $target })
    foreach ($process in $running) {
        Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
    }
    foreach ($process in $running) {
        Wait-Process -Id $process.ProcessId -Timeout 10 -ErrorAction SilentlyContinue
    }
    Copy-Item -LiteralPath $source -Destination $target -Force
    Copy-Item -LiteralPath $source -Destination (Join-Path $workspace 'dist\KeyNavigator.exe') -Force
    $started = Start-Process -FilePath $target -WorkingDirectory $workspace -WindowStyle Hidden -PassThru
    Write-Output "DEPLOYED PID=$($started.Id)"
    Get-FileHash -LiteralPath $target
} finally {
    Stop-Transcript
}
