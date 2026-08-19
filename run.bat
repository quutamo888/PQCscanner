@echo off
title PQC Compliance Web Scanner
echo.
echo  ============================================
echo   PQC Compliance Web Scanner
echo   Post-Quantum Cryptography Readiness Tool
echo  ============================================
echo.
cd /d "%~dp0"

if defined PQC_OPENSSL_PATH (
    "%PQC_OPENSSL_PATH%" version
    if errorlevel 1 echo WARNING: PQC_OPENSSL_PATH is not executable.
    "%PQC_OPENSSL_PATH%" version | findstr /r /c:"OpenSSL 3\.[5-9]" >nul
    if errorlevel 1 echo WARNING: OpenSSL 3.5+ PQC groups unavailable.
) else (
    where openssl >nul 2>&1
    if errorlevel 1 (
        echo WARNING: OpenSSL 3.5+ PQC engine unavailable.
        echo Set PQC_OPENSSL_PATH to an OpenSSL 3.5+ executable for verified PQC scans.
    ) else (
        openssl version
        openssl version | findstr /r /c:"OpenSSL 3\.[5-9]" >nul
        if errorlevel 1 echo WARNING: OpenSSL 3.5+ PQC groups unavailable.
    )
)

echo.
echo  Starting server at http://127.0.0.1:8000
echo  Press Ctrl+C to stop
echo.
start "" "http://127.0.0.1:8000"
uvicorn main:app --host 127.0.0.1 --port 8000
pause
