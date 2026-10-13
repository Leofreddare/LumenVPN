@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 goto usepython
py -3 build_client.py %*
goto done
:usepython
python build_client.py %*
:done
if errorlevel 1 (
  echo.
  echo Build failed. Read the error above. No finished release was published.
  pause
  exit /b 1
)
echo.
pause
