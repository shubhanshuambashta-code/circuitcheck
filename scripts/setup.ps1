$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
New-Item -ItemType Directory -Path 'data\tmp' -Force | Out-Null
$env:TMP = Join-Path $projectRoot 'data\tmp'
$env:TEMP = $env:TMP
python -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'Python venv creation failed.' }
& '.\.venv\Scripts\python.exe' -m pip install -r requirements.lock.txt
if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
npm.cmd ci --no-audit --no-fund
if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
npm.cmd run build
if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
Write-Output 'Setup complete. Configure KICAD_CLI in .env if needed, then run scripts\start.ps1.'
