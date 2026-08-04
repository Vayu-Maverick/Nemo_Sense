@echo off
cd /d "%~dp0"
echo Starting Netra Guide Rover (Demo Mode with LIDAR Map)
echo =======================================================
echo.
python python\main.py --mode vision-only
pause
