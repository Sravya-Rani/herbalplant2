# Script to start both backend and frontend servers
Write-Host "Starting Herbal Plant Identification System..." -ForegroundColor Green
Write-Host ""

# Start Backend Server
Write-Host "Starting Backend Server..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\backend'; python start_server.py" -WindowStyle Normal

# Wait a bit for backend to start
Start-Sleep -Seconds 3

# Start Frontend Server
Write-Host "Starting Frontend Server..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\frontend'; npm start" -WindowStyle Normal

Write-Host ""
Write-Host "Both servers are starting in separate windows!" -ForegroundColor Green
Write-Host "Backend: http://127.0.0.1:8000" -ForegroundColor Cyan
Write-Host "Frontend: http://localhost:3000" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press any key to exit this script (servers will continue running)..." -ForegroundColor Yellow
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

