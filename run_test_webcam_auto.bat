@echo off
set IP_ADDRESS=172.16.0.94
echo ===================================================
echo     Uploading and Running Webcam Power Test
echo     Target: %IP_ADDRESS% (Arduino UNO Q)
echo ===================================================
echo.
echo Please enter the root password for the Arduino if prompted.
echo.

scp "%~dp0python\test_webcam_power.py" root@%IP_ADDRESS%:/root/netra/python/

echo.
echo Running the webcam power test...
ssh root@%IP_ADDRESS% "cd /root/netra/python && python3 test_webcam_power.py"

echo.
pause
