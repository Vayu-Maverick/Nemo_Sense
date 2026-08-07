@echo off
title NEMO_SENSE -- AI Navigation Dashboard

echo.
echo  +-----------------------------------------------------------+
echo  ^|   NEMO_SENSE  --  AI Navigation Dashboard v5             ^|
echo  ^|   Live webcam + AR path overlay + Quarky UDP control     ^|
echo  +-----------------------------------------------------------+
echo.
echo  [1]  START  (webcam only -- no robot)
echo  [2]  START + Quarky WiFi Connect -- Camera 0
echo  [3]  START + Quarky WiFi Connect -- Camera 1 (Secondary Cam)
echo  [4]  WiFi stream from Arduino Q
echo  [5]  Exit
echo.
set /p C="  Choose: "

if "%C%"=="1" goto SOLO
if "%C%"=="2" goto QWIFI0
if "%C%"=="3" goto QWIFI1
if "%C%"=="4" goto STREAM
if "%C%"=="5" exit /b
goto SOLO

:INSTALL
python -m pip install opencv-python numpy onnxruntime -q
goto :EOF

:SOLO
call :INSTALL
echo.
echo [*] Webcam-only mode (no robot). AR path shown on screen.
python nemo_demo.py
pause & exit /b

:QWIFI0
call :INSTALL
echo.
set /p IP="  Enter Quarky's IP address (e.g. 192.168.43.100): "
python nemo_demo.py --quarky-ip %IP%
pause & exit /b

:QWIFI1
call :INSTALL
echo.
set /p IP="  Enter Quarky's IP address (e.g. 192.168.43.100): "
python nemo_demo.py --quarky-ip %IP% --camera 1
pause & exit /b

:STREAM
call :INSTALL
echo.
set /p IP="  Arduino Q Camera IP (e.g. 192.168.1.50): "
python nemo_demo.py --stream "http://%IP%:8080/"
pause & exit /b