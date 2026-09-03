@echo off
setlocal
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" (
  echo Missing .venv\Scripts\python.exe. Create the project environment first.
  exit /b 1
)
".venv\Scripts\python.exe" -m src.main api
exit /b %ERRORLEVEL%
