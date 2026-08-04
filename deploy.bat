@echo off
setlocal

echo ===================================================
echo     GuideSense Arduino UNO Q Deployment Script
echo ===================================================
echo.

set /p IP_ADDRESS="Enter the IP address of your Arduino UNO Q (e.g. 192.168.1.100): "

echo.
echo Pushing codebase to Arduino Q at %IP_ADDRESS%...
ssh root@%IP_ADDRESS% "mkdir -p /root/netra"
scp -r "%~dp0python" root@%IP_ADDRESS%:/root/netra/
scp -r "%~dp0scripts" root@%IP_ADDRESS%:/root/netra/
scp -r "%~dp0quarky" root@%IP_ADDRESS%:/root/netra/
scp -r "%~dp0docs" root@%IP_ADDRESS%:/root/netra/
scp "%~dp0requirements.txt" root@%IP_ADDRESS%:/root/netra/
scp "%~dp0README.md" root@%IP_ADDRESS%:/root/netra/
if exist "%~dp0yolov5n.onnx" scp "%~dp0yolov5n.onnx" root@%IP_ADDRESS%:/root/netra/python/models/

set /p RUN_SETUP="Do you want to run the first-time setup on the Arduino Q? (y/n): "
if /i "%RUN_SETUP%"=="y" (
    echo.
    echo Running first-time setup on Arduino Q...
    ssh root@%IP_ADDRESS% "chmod +x /root/netra/scripts/*.sh && /root/netra/scripts/setup_q.sh"
)

echo.
set /p RUN_MODE="Run mode [indoor/full/demo] (default: indoor): "
if "%RUN_MODE%"=="" set RUN_MODE=indoor

echo Connecting via SSH to start GuideSense in %RUN_MODE% mode...
ssh root@%IP_ADDRESS% "cd /root/netra && chmod +x scripts/run_netra.sh && bash scripts/run_netra.sh %RUN_MODE%"

echo.
echo Done.
pause
