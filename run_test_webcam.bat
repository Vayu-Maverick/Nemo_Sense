@echo off
echo ===================================================
echo     Testing Webcam Power on Arduino UNO Q
echo ===================================================
echo.

set /p IP_ADDRESS="Enter the IP address of your Arduino UNO Q: "

echo.
echo Uploading test_webcam_power.py to Arduino Q...
scp "%~dp0python\test_webcam_power.py" root@%IP_ADDRESS%:/root/netra/python/

echo.
echo Running the webcam power test...
echo (You may be prompted for the root password)
ssh root@%IP_ADDRESS% "cd /root/netra/python && python3 test_webcam_power.py"

echo.
pause
