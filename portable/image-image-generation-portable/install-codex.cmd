@echo off
setlocal
set "SCRIPT=%~dp0install.py"
where python >nul 2>nul
if not errorlevel 1 (
    python -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)" >nul 2>nul
    if not errorlevel 1 (
        python -B "%SCRIPT%" %*
        goto finished
    )
)
where py >nul 2>nul
if not errorlevel 1 (
    py -3 -B "%SCRIPT%" %*
    goto finished
)
echo Python 3.11 or newer is required.
pause
exit /b 2
:finished
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
    echo Installation failed with exit code %EXIT_CODE%.
) else (
    echo Codex Skill installation completed.
)
pause
exit /b %EXIT_CODE%
