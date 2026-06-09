@echo off
echo KeyNavigator Setup
echo.
echo Installing dependencies...
python -m pip install -r requirements.txt
echo.
if %ERRORLEVEL% EQU 0 (
    echo Done! Run with: python main.py
) else (
    echo Error: python not found or pip failed.
)
echo.
pause