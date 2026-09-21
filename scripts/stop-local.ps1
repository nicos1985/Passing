$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path '.local/server.pid')) {
    Write-Output 'Si iniciaste el servidor en una terminal, detenelo con Ctrl+C.'
    exit 0
}
$localServerId = [int](Get-Content '.local/server.pid')
$localProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $localServerId"
if ($localProcess) {
    $expectedPython = (Resolve-Path '.venv/Scripts/python.exe').Path
    if ($localProcess.ExecutablePath -ne $expectedPython -or
        $localProcess.CommandLine -notlike '*--settings=passing.local*') {
        throw 'El PID ya no corresponde al servidor local de Passing; no se detuvo.'
    }
    # A Windows venv launcher can spawn a child Python that owns the listening socket.
    & taskkill.exe /PID $localServerId /T /F
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo detener el servidor local.' }
}
Remove-Item -LiteralPath '.local/server.pid'
Write-Output 'Servidor local detenido.'
