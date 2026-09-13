@echo off
REM Starts a wallet/mining node.
REM Usage: run_node.bat [port] [mca_url]
REM   run_node.bat 5000 http://localhost:6060
REM   run_node.bat 5001 http://192.168.1.10:6060
cd /d "%~dp0"
if "%1"=="" (set PORT=5000) else (set PORT=%1)
if "%2"=="" (set MCA_URL=http://localhost:6060) else (set MCA_URL=%2)
python node_server.py
