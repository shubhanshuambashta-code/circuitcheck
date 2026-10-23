param([string]$KiCadCli = '', [int]$Port = 8000)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
if ($KiCadCli) { $env:KICAD_CLI = $KiCadCli }
$runtime = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $runtime)) {
    # Reuse the already installed task-local environment in this delivered workspace.
    $runtime = Join-Path $projectRoot '..\..\work\venv\Scripts\python.exe'
}
if (-not (Test-Path -LiteralPath $runtime)) { throw 'Run scripts\setup.ps1 first.' }
if (-not $env:KICAD_CLI) {
    $taskEngine = Join-Path $projectRoot '..\..\work\tools\kicad\bin\kicad-cli.exe'
    if (Test-Path -LiteralPath $taskEngine) { $env:KICAD_CLI = (Resolve-Path -LiteralPath $taskEngine).Path }
}
& $runtime scripts\start.py --port $Port --open
