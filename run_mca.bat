@echo off
REM Starts the Mining Certificate Authority.
REM Usage: run_mca.bat [port]
cd /d "%~dp0"
if "%1"=="" (set MCA_PORT=6060) else (set MCA_PORT=%1)
python mca_server.py
