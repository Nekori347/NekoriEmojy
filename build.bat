@echo off
setlocal
cd /d "%~dp0"
set "BUILD_PYTHON=python"
if exist ".venv\Scripts\python.exe" set "BUILD_PYTHON=.venv\Scripts\python.exe"
"%BUILD_PYTHON%" scripts\build_release.py %*
exit /b %ERRORLEVEL%
