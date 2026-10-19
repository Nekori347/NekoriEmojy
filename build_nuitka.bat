@echo off
setlocal
cd /d "%~dp0"
set "BUILD_PYTHON=%~dp0.venv\Scripts\python.exe"
if not exist "%BUILD_PYTHON%" (
    echo ERROR: Create Source\.venv and install build dependencies first.
    exit /b 1
)
set "NUITKA_UPDATE_CHECK=never"
"%BUILD_PYTHON%" build_nuitka.py %*
exit /b %ERRORLEVEL%
