$projectRoot = $PSScriptRoot
$python = Join-Path $projectRoot 'venv\Scripts\python.exe'

if (!(Test-Path $python)) {
    $python = Join-Path $projectRoot 'banking-agent\.venv\Scripts\python.exe'
}
if (!(Test-Path $python)) {
    throw 'No project virtual environment was found. Create one, then install requirements.txt.'
}

Set-Location $projectRoot
if (!$env:KEY_PASSPHRASE) {
    $env:KEY_PASSPHRASE = 'finn-local-development-only'
}

& $python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
