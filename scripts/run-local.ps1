$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path '.venv/Scripts/python.exe')) {
    throw 'Primero ejecutá scripts/setup-local.ps1.'
}
& ./.venv/Scripts/python.exe manage.py runserver 127.0.0.1:8000 --settings=passing.local
exit $LASTEXITCODE
