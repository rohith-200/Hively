@echo off
setlocal
pushd "%~dp0frontend"
node scripts\start.mjs
if errorlevel 1 (
  echo.
  pause
  popd
  exit /b 1
)
start "" "http://127.0.0.1:5173/"
popd
