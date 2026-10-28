@echo off
setlocal
cd /d "%~dp0"
set "PYCMD=python"
python -c "import sys;sys.exit(0 if sys.version_info>=(3,11) else 2)" >nul 2>nul
if errorlevel 1 (
    set "PYCMD=py -3"
    py -3 -c "import sys;sys.exit(0 if sys.version_info>=(3,11) else 2)" >nul 2>nul
    if errorlevel 1 goto missing_python
)
%PYCMD% -B "%~dp0image-image-generation-portable\install.py"
if errorlevel 1 goto failed
%PYCMD% -c "from PIL import Image" >nul 2>nul
if not errorlevel 1 goto ok
echo Installing Pillow image dependency...
%PYCMD% -m pip install --disable-pip-version-check --no-index --find-links="%~dp0bundled-dependencies\windows-x64" "Pillow>=10"
if not errorlevel 1 goto ok
echo Offline wheel is not compatible with this Python. Trying pip index...
%PYCMD% -m pip install --disable-pip-version-check "Pillow>=10"
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
echo Skill installed, but Pillow dependency is missing. See installation instructions.
pause
exit /b 2
:failed
echo Skill installation failed. See error above.
pause
exit /b 1
