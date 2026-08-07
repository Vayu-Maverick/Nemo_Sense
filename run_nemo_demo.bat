@echo off
title NEMO_SENSE -- AI Navigation Dashboard

echo.
echo  +----------------------------------------------------------+
echo  ^|   NEMO_SENSE  --  AI Navigation Dashboard               ^|
echo  ^|   Live webcam + AR path overlay + YOLOv5n               ^|
echo  +----------------------------------------------------------+
echo.
echo  [1]  START  (auto-detect webcam)
echo  [2]  Camera 1  (if you have multiple cameras)
echo  [3]  WiFi stream from Arduino Q
echo  [4]  Hide path overlay  (dashboard only)
echo  [5]  Exit
echo.

set /p C="  Choose: "

if "%C%"=="1" goto AUTO
if "%C%"=="2" goto CAM1
if "%C%"=="3" goto STREAM
if "%C%"=="4" goto NOPTH
if "%C%"=="5" exit /b
goto AUTO

:AUTO
echo.
echo [*] Installing dependencies...
python -m pip install opencv-python numpy onnxruntime -q
echo [*] Launching...
echo     Point webcam at the path. AR corridor will appear on screen.
echo     Q = quit   P = pause
echo.
python nemo_demo.py
pause
exit /b

:CAM1
echo.
python -m pip install opencv-python numpy onnxruntime -q
python nemo_demo.py --camera 1
pause
exit /b

:STREAM
echo.
set /p IP="  Arduino Q IP address (e.g. 192.168.1.50): "
python -m pip install opencv-python numpy onnxruntime -q
python nemo_demo.py --stream "http://%IP%:8080/"
pause
exit /b

:NOPTH
echo.
python -m pip install opencv-python numpy onnxruntime -q
python nemo_demo.py --no-path
pause
exit /b