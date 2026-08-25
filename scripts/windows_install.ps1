$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw 'Python was not found. Install Python 3.9+ and make sure python is in PATH.'
}

if (-not (Test-Path '.venv\Scripts\python.exe')) {
    python -m venv .venv
}

& .\.venv\Scripts\python.exe -m pip install --disable-pip-version-check -e .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ''
Write-Host 'ShowDoc2MD installation complete.'
Write-Host 'Example:'
Write-Host '  $env:SHOWDOC_PASSWORD="your-password"'
Write-Host '  .\showdoc2md.cmd probe "https://www.showdoc.com.cn/<item_id>/<page_id>"'
Write-Host '  .\showdoc2md.cmd export "https://www.showdoc.com.cn/<item_id>/<page_id>" --output .\output'
