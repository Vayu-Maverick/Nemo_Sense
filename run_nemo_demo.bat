@echo off
title NEMO_SENSE -- AI Navigation Dashboard

echo.
echo  +-----------------------------------------------------------+
echo  ^|   NEMO_SENSE  --  AI Navigation Dashboard v4             ^|
echo  ^|   Live webcam + AR path overlay + Quarky BLE control     ^|
echo  +-----------------------------------------------------------+
echo.
echo  [1]  START  (webcam only -- no robot)
echo  [2]  START + Quarky BLE Connect
echo  [3]  WiFi stream from Arduino Q
echo  [4]  Exit
echo.
set /p C="  Choose: "

if "%C%"=="1" goto SOLO
if "%C%"=="2" goto QBLE
if "%C%"=="3" goto STREAM
if "%C%"=="4" exit /b
goto SOLO

:INSTALL
python -m pip install opencv-python numpy onnxruntime bleak -q
goto :EOF

:SOLO
call :INSTALL
echo.
echo [*] Webcam-only mode (no robot). AR path shown on screen.
python nemo_demo.py
pause & exit /b

:QBLE
call :INSTALL
echo.
echo [*] Connecting to Quarky over BLE...
python nemo_demo.py --quarky-ble
pause & exit /b

:STREAM
call :INSTALL
echo.
set /p IP="  Arduino Q IP (e.g. 192.168.1.50): "
python nemo_demo.py --stream "http://%IP%:8080/"
pause & exit /b