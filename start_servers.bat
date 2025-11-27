@echo off
echo Starting Herbal Plant Identification System...
echo.

echo Starting Backend Server...
start "Backend Server" cmd /k "cd backend && python start_server.py"

timeout /t 3 /nobreak >nul

echo Starting Frontend Server...
start "Frontend Server" cmd /k "cd frontend && npm start"

echo.
echo Both servers are starting in separate windows!
echo Backend: http://127.0.0.1:8000
echo Frontend: http://localhost:3000
echo.
pause

