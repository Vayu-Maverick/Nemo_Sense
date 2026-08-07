@echo off
title NEMO_SENSE -- AI Navigation Dashboard

echo.
echo  +-----------------------------------------------------------+
echo  ^|   NEMO_SENSE  --  AI Navigation Dashboard v4             ^|
echo  ^|   Live webcam + AR path overlay + Quarky control         ^|
echo  +-----------------------------------------------------------+
echo.
echo  [1]  START  (webcam only -- no robot)
echo  [2]  START + Quarky auto-detect (USB)
echo  [3]  START + Quarky on specific COM port
echo  [4]  WiFi stream from Arduino Q
echo  [5]  Exit
echo.
set /p C="  Choose: "

if "%C%"=="1" goto SOLO
if "%C%"=="2" goto QAUTO
if "%C%"=="3" goto QPORT
if "%C%"=="4" goto STREAM
if "%C%"=="5" exit /b
goto SOLO

:INSTALL
python -m pip install opencv-python numpy onnxruntime pyserial -q
goto :EOF

:SOLO
call :INSTALL
echo.
echo [*] Webcam-only mode (no robot). AR path shown on screen.
python nemo_demo.py
pause & exit /b

:QAUTO
call :INSTALL
echo.
echo [*] Auto-detecting Quarky...
python nemo_demo.py --quarky auto
pause & exit /b

:QPORT
call :INSTALL
echo.
set /p PORT="  Quarky COM port (e.g. COM5): "
python nemo_demo.py --quarky %PORT%
pause & exit /b

:STREAM
call :INSTALL
echo.
set /p IP="  Arduino Q IP (e.g. 192.168.1.50): "
python nemo_demo.py --stream "http://%IP%:8080/"
pause & exit /b