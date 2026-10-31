@echo off
setlocal
cd /d "%~dp0"
py -3 -m venv .venv-build
if errorlevel 1 goto fail
.venv-build\Scripts\python.exe -m pip install -r requirements-build.txt
if errorlevel 1 goto fail
.venv-build\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --windowed --name SimpleFlow --collect-all playwright --collect-all cv2 desktop_app.py
if errorlevel 1 goto fail
.venv-build\Scripts\python.exe -c "import subprocess; subprocess.run(['dist/SimpleFlow.exe', '--self-test'], check=True, timeout=90)"
if errorlevel 1 goto fail
echo Built: dist\SimpleFlow.exe
pause
exit /b 0
:fail
echo Build failed. Install Python 3.12 x64 from python.org and retry.
pause
exit /b 1
