@echo off
setlocal

echo ===================================================
echo     GuideSense UNO Q Linux Factory Reset Script
echo ===================================================
echo.
echo WARNING: This will completely delete the Python brain, 
echo OpenCV models, virtual environments, and all auto-boot 
echo services from the Linux core of the Arduino UNO Q!
echo.
set /p CONFIRM="Are you absolutely sure you want to factory reset? (y/n): "
if /i not "%CONFIRM%"=="y" (
    echo Factory reset aborted.
    exit /b
)

echo.
set /p IP_ADDRESS="Enter the IP address of your Arduino UNO Q (e.g. 192.168.1.100): "

echo.
echo Wiping Netra files and configurations...
ssh root@%IP_ADDRESS% "systemctl stop netra-brain.service 2>/dev/null; systemctl disable netra-brain.service 2>/dev/null; rm -f /etc/systemd/system/netra-brain.service; systemctl daemon-reload; rm -rf /root/netra"

echo.
echo Factory Reset of the Linux environment is complete!
echo The board is now clean. You can re-run deploy.bat later to install everything from scratch.
pause
