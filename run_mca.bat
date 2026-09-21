@echo off
REM Starts the validator registry (MCA).
REM Usage: run_mca.bat [port]
cd /d "%~dp0"
if "%1"=="" (set MCA_PORT=6060) else (set MCA_PORT=%1)
python mca_server.py
