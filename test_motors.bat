@echo off
echo =======================================================
echo Testing Nemo~Sense Motors...
echo =======================================================

set ADB="C:\Users\Admin\AppData\Local\Arduino15\packages\arduino\tools\adb\32.0.0\adb.exe"

echo Pushing test script to Arduino...
%ADB% push test_motors.py /home/arduino/test_motors.py

echo.
echo Running motor test...
echo WATCH YOUR QUARKY CAREFULLY! IT SHOULD MOVE NOW!
echo.
%ADB% shell "python3 /home/arduino/test_motors.py"

echo.
echo =======================================================
echo Test complete.
pause
