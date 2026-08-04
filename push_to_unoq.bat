@echo off
echo =======================================================
echo Pushing Netra AI to Arduino UNO Q via USB (ADB)
echo =======================================================

:: Path to the ADB tool installed by the Arduino IDE
set ADB="C:\Users\Admin\AppData\Local\Arduino15\packages\arduino\tools\adb\32.0.0\adb.exe"

echo Checking for connected Arduino UNO Q...
%ADB% devices

echo.
echo Pushing Python code to the Arduino UNO Q (/home/arduino/netra)...
%ADB% shell "mkdir -p /home/arduino/netra"
%ADB% push "%~dp0python" /home/arduino/netra/
%ADB% push "%~dp0config.py" /home/arduino/netra/ 2>NUL

echo.
echo =======================================================
echo Transfer Complete! 
echo Now opening the Arduino UNO Q Linux Terminal...
echo Type 'python3 /home/arduino/netra/python/main.py --mode full' inside the terminal!
echo =======================================================
pause

%ADB% shell
