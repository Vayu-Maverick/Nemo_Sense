@echo off
echo =======================================================
echo Setting up Auto-Start for Netra AI Rover
echo =======================================================

set ADB="C:\Users\Admin\AppData\Local\Arduino15\packages\arduino\tools\adb\32.0.0\adb.exe"

echo Checking for connected Arduino UNO Q...
%ADB% devices

echo.
echo Creating the startup loop script...
%ADB% shell "echo '#!/bin/bash' > /home/arduino/nemosense/autostart.sh"
%ADB% shell "echo 'cd /home/arduino/nemosense/python' >> /home/arduino/nemosense/autostart.sh"
%ADB% shell "echo '# Disable USB autosuspend to wake up the webcam' >> /home/arduino/nemosense/autostart.sh"
%ADB% shell "echo 'for dev in /sys/bus/usb/devices/*/power/control; do echo on > $dev 2>/dev/null; done' >> /home/arduino/nemosense/autostart.sh"
%ADB% shell "echo 'sleep 2' >> /home/arduino/nemosense/autostart.sh"
%ADB% shell "echo '# Force v4l2 to ping the camera' >> /home/arduino/nemosense/autostart.sh"
%ADB% shell "echo 'v4l2-ctl --list-devices > /dev/null 2>&1' >> /home/arduino/nemosense/autostart.sh"
%ADB% shell "echo 'while true; do' >> /home/arduino/nemosense/autostart.sh"
%ADB% shell "echo '    /usr/bin/python3 main.py --mode full' >> /home/arduino/nemosense/autostart.sh"
%ADB% shell "echo '    sleep 5' >> /home/arduino/nemosense/autostart.sh"
%ADB% shell "echo 'done' >> /home/arduino/nemosense/autostart.sh"
%ADB% shell "chmod +x /home/arduino/nemosense/autostart.sh"

echo.
echo Installing into crontab to run on boot...
%ADB% shell "(crontab -l 2>/dev/null | grep -v 'autostart.sh'; echo '@reboot bash /home/arduino/nemosense/autostart.sh > /home/arduino/nemosense/autostart.log 2>&1') | crontab -"

echo.
echo =======================================================
echo Setup Complete!
echo Next time you turn on the battery, the rover will
echo automatically start driving after about 30 seconds!
echo =======================================================
pause
