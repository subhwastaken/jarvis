# NIKO Windows Quickstart Launcher
Write-Host "⚡ Starting NIKO Desktop Assistant..." -ForegroundColor Cyan

$RepoDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RepoDir

# Check Python 3
$PythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $PythonCmd) {
    $PythonCmd = Get-Command py -ErrorAction SilentlyContinue
}
if (-not $PythonCmd) {
    Write-Host "❌ Python 3.10+ is required. Please install Python from https://www.python.org" -ForegroundColor Red
    exit 1
}

# Create .venv if not present
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "📦 Creating virtual environment in .venv..." -ForegroundColor Yellow
    & $PythonCmd.Source -m venv .venv
    Write-Host "📥 Installing dependencies from requirements.txt..." -ForegroundColor Yellow
    & .venv\Scripts\python.exe -m pip install -q --upgrade pip
    & .venv\Scripts\python.exe -m pip install -q -r requirements.txt
}

Write-Host "🚀 Launching NIKO Dynamic Island HUD..." -ForegroundColor Green
if ($args.Count -eq 0) {
    & .venv\Scripts\python.exe siri.py --ui
} else {
    & .venv\Scripts\python.exe siri.py @args
}
