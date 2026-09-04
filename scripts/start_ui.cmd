@echo off
setlocal
cd /d "%~dp0.."
if not exist "frontend\node_modules\.bin\vite.cmd" (
  echo Frontend dependencies are missing. Run: cd frontend ^&^& npm install
  exit /b 1
)
cd frontend
npm run dev
exit /b %ERRORLEVEL%
