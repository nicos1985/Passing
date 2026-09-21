$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
$env:UV_CACHE_DIR = Join-Path $PWD '.uv-cache'
$env:UV_PYTHON_INSTALL_DIR = Join-Path $PWD '.python'

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw 'Se necesita uv instalado para preparar el entorno.'
}
uv --native-tls python install 3.12 --no-bin
if ($LASTEXITCODE -ne 0) { throw 'No se pudo instalar Python.' }
if (-not (Test-Path '.venv/Scripts/python.exe')) {
    uv --native-tls venv .venv --python 3.12
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear .venv.' }
}
uv --native-tls pip install --python .venv/Scripts/python.exe -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'No se pudieron instalar las dependencias.' }
& ./.venv/Scripts/python.exe manage.py migrate --settings=passing.local --noinput
if ($LASTEXITCODE -ne 0) { throw 'Fallaron las migraciones locales.' }
& ./.venv/Scripts/python.exe manage.py prepare_local --settings=passing.local
if ($LASTEXITCODE -ne 0) { throw 'No se pudieron preparar los usuarios locales.' }
& ./.venv/Scripts/python.exe manage.py check --settings=passing.local
if ($LASTEXITCODE -ne 0) { throw 'Fallaron las comprobaciones de Django.' }
