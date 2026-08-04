@echo off
setlocal

echo ===================================================
echo     GuideSense Webcam Diagnostic Tool
echo ===================================================
echo.
set /p IP_ADDRESS="Enter the IP address of your Arduino UNO Q (e.g. 192.168.1.100): "

echo.
echo Checking connected USB devices...
ssh root@%IP_ADDRESS% "lsusb"

echo.
echo Checking for video devices (/dev/video*)...
ssh root@%IP_ADDRESS% "ls -l /dev/video*"

echo.
echo Checking system logs for USB/Webcam errors...
ssh root@%IP_ADDRESS% "dmesg | grep -i 'usb\|uvc\|video' | tail -n 15"

echo.
echo Done. Please share this output with Antigravity!
pause
