$ErrorActionPreference = "Stop"
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$casa = Join-Path $env:USERPROFILE ".hodor-sup"
$dest = Join-Path $casa "kit"
$py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $py) { throw "Falta Python 3." }
if (-not (Get-Command aws -ErrorAction SilentlyContinue)) { Write-Host "Aviso: no encuentro el AWS CLI (aws.exe). Sin él no podrás aprobar desde el panel." }
New-Item -ItemType Directory -Force -Path $dest | Out-Null
if (Test-Path (Join-Path $dir ".git")) { Set-Content -Path (Join-Path $casa "repo") -Value $dir -Encoding UTF8 } else { Write-Host "Aviso: no instalaste desde el clon de hodor-supervisor; Buscar actualización no va a poder actualizarlo." }
$config = Join-Path $casa "config.json"
if (-not (Test-Path $config)) {
  $origen = if (Test-Path (Join-Path $dir "config.json")) { Join-Path $dir "config.json" } else { Join-Path $dir "config.ejemplo.json" }
  Copy-Item $origen $config
  Write-Host "Dejé tu configuración en $($config). Pon ahí tu token y tu perfil de AWS."
}
Copy-Item (Join-Path $dir "servidor.py"), (Join-Path $dir "panel.html"), (Join-Path $dir "VERSION") $dest -Force
& $py (Join-Path $dest "servidor.py") --estado
$pyw = $py -replace "python.exe$", "pythonw.exe"
$accion = New-ScheduledTaskAction -Execute $pyw -Argument "`"$(Join-Path $dest 'servidor.py')`" --sin-navegador" -WorkingDirectory $dest
$disparo = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$ajustes = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 99 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero)
Register-ScheduledTask -TaskName "HodorSupervisor" -Action $accion -Trigger $disparo -Settings $ajustes -Force | Out-Null
Stop-ScheduledTask -TaskName "HodorSupervisor" -ErrorAction SilentlyContinue
Get-CimInstance Win32_Process -Filter "Name like 'python%'" | Where-Object { $_.CommandLine -like "*hodor-sup*servidor.py*" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 2
Start-ScheduledTask -TaskName "HodorSupervisor"
Start-Sleep -Seconds 3
Start-Process "http://127.0.0.1:7790"
Write-Host "Listo: Hodor Supervisor corre en segundo plano. Tu panel: http://127.0.0.1:7790"
