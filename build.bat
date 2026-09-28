@echo off
echo ===================================================
echo  KeyNavigator Build and Register Startup
echo ===================================================
echo.
python build.py
if errorlevel 1 (
    echo.
    echo [ERROR] ビルドまたは起動に失敗しました。
    pause
    exit /b 1
)
echo.
echo [SUCCESS] 正常に完了しました！
pause
