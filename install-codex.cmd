@echo off
setlocal
set "SCRIPT=%~dp0install.py"
where py >nul 2>nul
if not errorlevel 1 (
    py -3 -B "%SCRIPT%" %*
) else (
    where python >nul 2>nul
    if errorlevel 1 (
        echo Python 3.11 or newer is required.
        pause
        exit /b 2
    )
    python -B "%SCRIPT%" %*
)
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
    echo Installation failed with exit code %EXIT_CODE%.
) else (
    echo Codex Skill installation completed.
)
pause
exit /b %EXIT_CODE%

