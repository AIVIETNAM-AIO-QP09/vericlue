@echo off
setlocal
set "VC_ACTION=%~1"
if not defined VC_ACTION set "VC_ACTION=start"
if /I "%VC_ACTION%"=="start" goto run
if /I "%VC_ACTION%"=="stop" goto run
if /I "%VC_ACTION%"=="status" goto run
echo Usage: server.cmd start^|stop^|status
exit /b 2
:run
"%~dp0..\tmp\session-api-runtime\Scripts\python.exe" "%~dp0server.py" "%VC_ACTION%" --runtime-dir "%~dp0..\tmp\vericlue-server"
exit /b %ERRORLEVEL%
