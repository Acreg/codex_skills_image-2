@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
set "PYEXE="
set "PYARG="
REM Prefer normal installed Python over transient virtualenvs on PATH.
for %%P in ("%LOCALAPPDATA%\Programs\Python\Python314\python.exe" "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" "%LOCALAPPDATA%\Programs\Python\Python311\python.exe") do (
    if not defined PYEXE if exist "%%~P" (
        "%%~P" -c "import sys;sys.exit(0 if sys.version_info>=(3,11) else 1)" >nul 2>nul
        if not errorlevel 1 set "PYEXE=%%~P"
    )
)
if not defined PYEXE (
    py -3.14 -c "import sys;sys.exit(0 if sys.version_info>=(3,11) else 1)" >nul 2>nul
    if not errorlevel 1 (
        set "PYEXE=py"
        set "PYARG=-3.14"
    )
)
if not defined PYEXE (
    py -3 -c "import sys;sys.exit(0 if sys.version_info>=(3,11) else 1)" >nul 2>nul
    if not errorlevel 1 (
        set "PYEXE=py"
        set "PYARG=-3"
    )
)
if not defined PYEXE (
    python -c "import sys;sys.exit(0 if sys.version_info>=(3,11) else 1)" >nul 2>nul
    if not errorlevel 1 set "PYEXE=python"
)
if not defined PYEXE goto missing_python
echo Python selected: %PYEXE% %PYARG%
"%PYEXE%" %PYARG% -B "%~dp0image-image-generation-portable\install.py"
if errorlevel 1 goto failed
"%PYEXE%" %PYARG% -c "from PIL import Image" >nul 2>nul
if not errorlevel 1 goto ok
echo Installing Pillow image dependency...
"%PYEXE%" %PYARG% -m pip install --disable-pip-version-check --no-index --find-links="%~dp0bundled-dependencies\windows-x64" "Pillow>=10"
if not errorlevel 1 goto ok
echo Offline wheel not compatible; trying pip index...
"%PYEXE%" %PYARG% -m pip install --disable-pip-version-check "Pillow>=10"
if errorlevel 1 goto missing_pillow
:ok
echo GPT-image2 Skill installed. Restart Codex and edit image-image-generation\.env if needed.
pause
exit /b 0
:missing_python
echo Python 3.11 or newer is required. Please run:
echo python-installers\windows-x64\python-3.14.10-amd64.exe
echo Then run this script again.
pause
exit /b 2
:missing_pillow
echo Skill installed but Pillow dependency is missing. See installation instructions.
pause
exit /b 2
:failed
echo Skill installation failed. See error above.
pause
exit /b 1
