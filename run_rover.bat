@echo off
title NETRA AI -- Simulation Dashboard

echo.
echo  +-----------------------------------------------------------+
echo  ^|   NETRA AI SIMULATION DASHBOARD                          ^|
echo  ^|   Live webcam + Cinematic AR Path Overlay                ^|
echo  +-----------------------------------------------------------+
echo.
echo  [1] Run Simulator (USB Webcam + BLE)
echo  [2] Run Simulator (Webcam ONLY, no BLE)
echo  [3] Run Simulator (Simulated Camera, no hardware)
echo  [4] Exit
echo.
set /p C="  Choose (1-4): "

if "%C%"=="1" goto SIM_FULL
if "%C%"=="2" goto SIM_NO_BLE
if "%C%"=="3" goto SIM_ONLY
if "%C%"=="4" exit /b
goto SIM_NO_BLE

:INSTALL
python -m pip install opencv-python numpy onnxruntime bleak pyttsx3 pyserial -q 2>&1
goto :EOF

:SIM_FULL
call :INSTALL
echo.
echo [*] Starting Simulator (Webcam + BLE)...
python rover_simulator.py
pause & exit /b

:SIM_NO_BLE
call :INSTALL
echo.
echo [*] Starting Simulator (Webcam only, no BLE)...
python rover_simulator.py --no-ble
pause & exit /b

:SIM_ONLY
call :INSTALL
echo.
echo [*] Starting Simulator (Simulated camera)...
python rover_simulator.py --sim --no-ble
pause & exit /b
