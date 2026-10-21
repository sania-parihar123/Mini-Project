#!/usr/bin/env pwsh
# scripts/run_dev.ps1 - Start ProcessFoundry AI in development mode (FastAPI + Streamlit)

Write-Host "Starting ProcessFoundry AI Development Environment..." -ForegroundColor Cyan

# Verify we're in the project root
if (-not (Test-Path "app/main.py")) {
    Write-Error "Run this script from the project root directory."
    exit 1
}

# Start FastAPI backend in background
Write-Host "[1/2] Starting FastAPI backend on http://localhost:8000" -ForegroundColor Green
$api_job = Start-Job -ScriptBlock {
    Set-Location $using:PWD
    & C:\Python314\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload 2>&1
}

# Give FastAPI time to start
Start-Sleep -Seconds 3

# Verify API health
try {
    $health = Invoke-RestMethod -Uri "http://localhost:8000/api/health" -TimeoutSec 5
    Write-Host "  API health: $($health.status)" -ForegroundColor Green
} catch {
    Write-Warning "  API may still be starting. Proceeding..."
}

# Start Streamlit frontend in foreground
Write-Host "[2/2] Starting Streamlit UI on http://localhost:8501" -ForegroundColor Green
& C:\Python314\python.exe -m streamlit run app/ui/streamlit_app.py `
    --server.port 8501 `
    --server.address localhost `
    --server.headless false

# Clean up background job on exit
Write-Host "Stopping background API server..." -ForegroundColor Yellow
Stop-Job $api_job -ErrorAction SilentlyContinue
Remove-Job $api_job -ErrorAction SilentlyContinue
