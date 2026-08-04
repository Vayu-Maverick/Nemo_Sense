@echo off
:: ╔══════════════════════════════════════════════════════════════╗
:: ║   NETRA Guide Rover — Quick Launcher                        ║
:: ║   Double-click to run! Works with USB webcam or simulation. ║
:: ╚══════════════════════════════════════════════════════════════╝
setlocal EnableDelayedExpansion

set PYTHON=C:\Users\Admin\AppData\Local\Programs\Python\Python311\python.exe
set DIR=%~dp0

echo.
echo  ████████████████████████████████████████████████████████
echo  █         NETRA — Blind Guide Rover Software           █
echo  ████████████████████████████████████████████████████████
echo.

:: ── Check Python ──────────────────────────────────────────────
if not exist "%PYTHON%" (
    echo [ERROR] Python 3.11 not found at:
    echo   %PYTHON%
    echo Please install Python 3.11 from python.org
    pause
    exit /b 1
)
echo [OK] Python found: %PYTHON%

:: ── Install dependencies if needed ───────────────────────────
echo.
echo [SETUP] Checking Python packages...
"%PYTHON%" -m pip install opencv-python numpy onnxruntime bleak pyttsx3 pyserial -q 2>&1
echo [OK] Packages ready.

:: ── Menu ──────────────────────────────────────────────────────
echo.
echo  What do you want to do?
echo.
echo  [1] Run Smoke Test (webcam detection + AI)
echo  [2] Run Rover Simulator — USB Webcam + BLE mode
echo  [3] Run Rover Simulator — USB Webcam ONLY (no BLE)
echo  [4] Run Rover Simulator — SIMULATED camera (no hardware needed)
echo  [5] Run HARDWARE Loop Test — PC computes, Arduino drives (COM4)
echo  [6] Exit
echo.
set /p CHOICE="  Enter choice (1-6): "

if "%CHOICE%"=="1" goto SMOKE_TEST
if "%CHOICE%"=="2" goto SIM_FULL
if "%CHOICE%"=="3" goto SIM_NO_BLE
if "%CHOICE%"=="4" goto SIM_ONLY
if "%CHOICE%"=="5" goto HW_TEST
if "%CHOICE%"=="6" goto END
goto END

:HW_TEST
echo.
echo [RUN] Starting Hardware Loop Test (PC computes, Arduino drives via COM4)...
echo       -> Ensure Webcam is plugged into PC
echo       -> Ensure Arduino is plugged into PC (COM4)
echo       -> Press 'q' on the video window to stop.
echo.
"%PYTHON%" "%DIR%q_brain.py" --show --port COM4
pause
goto END

:SMOKE_TEST
echo.
echo [RUN] Starting webcam + AI smoke test...
echo       -> Plug your webcam in BEFORE running!
echo.
"%PYTHON%" "%DIR%test_webcam_ai.py" --show --frames 10
pause
goto END

:SIM_FULL
echo.
echo [RUN] Starting Rover Simulator (Webcam + BLE)...
echo       -> Plug webcam directly into rover/PC
echo       -> Connect Android GuideSense app via Bluetooth
echo.
"%PYTHON%" "%DIR%rover_simulator.py"
pause
goto END

:SIM_NO_BLE
echo.
echo [RUN] Starting Rover Simulator (Webcam only, no BLE)...
echo       -> Plug webcam directly into rover/PC
echo.
"%PYTHON%" "%DIR%rover_simulator.py" --no-ble
pause
goto END

:SIM_ONLY
echo.
echo [RUN] Starting Rover Simulator (Simulated camera — no hardware needed)...
echo.
"%PYTHON%" "%DIR%rover_simulator.py" --sim --no-ble
pause
goto END

:END
echo.
echo Bye!
