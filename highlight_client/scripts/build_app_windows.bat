@echo off
setlocal
cd /d "%~dp0\.."
python scripts\build_sidecar.py
npm install
npm run build
