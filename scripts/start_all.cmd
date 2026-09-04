@echo off
setlocal EnableExtensions
set "ROOT=%~dp0.."
for %%I in ("%ROOT%") do set "ROOT=%%~fI"
set "PYTHON=%ROOT%\.venv\Scripts\python.exe"

if /I "%~1"=="--check" goto check

if not exist "%PYTHON%" (
  echo Missing %PYTHON%.
  echo Create the environment with: py -3.12 -m venv "%ROOT%\.venv"
  exit /b 1
)
if not exist "%ROOT%\frontend\node_modules\.bin\vite.cmd" (
  echo Frontend dependencies are missing.
  echo Install them with: cd /d "%ROOT%\frontend" ^&^& npm install
  exit /b 1
)
where npm >nul 2>&1
if errorlevel 1 (
  echo npm was not found on PATH. Install Node.js 20 or newer.
  exit /b 1
)

start "Voice Assistant API" /D "%ROOT%" cmd /k call "%ROOT%\scripts\start_api.cmd"
start "Voice Assistant UI" /D "%ROOT%" cmd /k call "%ROOT%\scripts\start_ui.cmd"
start "Voice Assistant Desktop" /D "%ROOT%" cmd /k "%PYTHON%" -m src.main desktop
exit /b 0

:check
echo Voice Assistant root: %ROOT%
if not exist "%PYTHON%" (
  echo [missing] %PYTHON%
  exit /b 1
)
echo [ok] %PYTHON%
if not exist "%ROOT%\frontend\node_modules\.bin\vite.cmd" (
  echo [missing] %ROOT%\frontend\node_modules\.bin\vite.cmd
  exit /b 1
)
echo [ok] frontend dependencies
where npm >nul 2>&1
if errorlevel 1 (
  echo [missing] npm on PATH
  exit /b 1
)
echo [ok] npm on PATH
exit /b 0
