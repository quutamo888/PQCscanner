@echo off
title PQC Compliance Web Scanner
echo.
echo  ============================================
echo   PQC Compliance Web Scanner
echo   Post-Quantum Cryptography Readiness Tool
echo  ============================================
echo.
cd /d "%~dp0"
echo  Starting server at http://127.0.0.1:8000
echo  Press Ctrl+C to stop
echo.
start "" "http://127.0.0.1:8000"
uvicorn main:app --host 127.0.0.1 --port 8000
pause
