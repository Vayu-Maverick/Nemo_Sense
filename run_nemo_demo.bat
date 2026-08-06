@echo off
:: ╔══════════════════════════════════════════════════════════════════╗
:: ║   NEMO_SENSE  —  PC Demo Launcher                                ║
:: ║   Runs AI pipeline on PC, shows Arduino UNO Q dashboard          ║
:: ╚══════════════════════════════════════════════════════════════════╝
setlocal EnableDelayedExpansion

set PYTHON=C:\Users\Admin\AppData\Local\Programs\Python\Python311\python.exe
set DIR=%~dp0

echo.
echo  ╔══════════════════════════════════════════════════════════╗
echo  ║    NEMO_SENSE — AI Navigation Demo                       ║
echo  ║    YOLOv5n  ^|  Obstacle Detection  ^|  Real-time UI      ║
echo  ╚══════════════════════════════════════════════════════════╝
echo.

:: Check Python
if not exist "%PYTHON%" (
    echo [ERROR] Python 3.11 not found. Trying system python...
    set PYTHON=python
)

:: Install deps silently
echo [SETUP] Installing/checking dependencies...
"%PYTHON%" -m pip install opencv-python numpy onnxruntime -q 2>&1 | findstr /v "already"
echo [OK] Dependencies ready.
echo.

:: Menu
echo  Choose mode:
echo.
echo  [1]  WEBCAM + AI  (plug in webcam first)
echo  [2]  SIMULATED    (no webcam needed — demo mode)
echo  [3]  Camera 1     (if default webcam is wrong index)
echo  [4]  Exit
echo.
set /p CHOICE="  Enter 1-4: "

if "%CHOICE%"=="1" goto WEBCAM
if "%CHOICE%"=="2" goto SIM
if "%CHOICE%"=="3" goto CAM1
if "%CHOICE%"=="4" goto END
goto SIM

:WEBCAM
echo.
echo [RUN] Starting with webcam...
echo       Press Q or ESC to quit the dashboard window.
echo.
"%PYTHON%" "%DIR%nemo_demo.py"
pause
goto END

:SIM
echo.
echo [RUN] Starting in simulated mode (no webcam needed)...
echo       Press Q or ESC to quit.
echo.
"%PYTHON%" "%DIR%nemo_demo.py" --sim
pause
goto END

:CAM1
echo.
echo [RUN] Starting with camera index 1...
"%PYTHON%" "%DIR%nemo_demo.py" --camera 1
pause
goto END

:END
echo.
echo Done!
