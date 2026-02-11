@echo off
REM 批量启动所有项目（Windows 版本）
REM Usage: scripts\run_all.bat

SET ROOT=%~dp0..

FOR /D %%P IN ("%ROOT%\project_*") DO (
    IF EXIST "%%P\app.py" (
        echo Starting %%~nxP ...
        start "%%~nxP" cmd /k "cd /d %%P && uv run streamlit run app.py"
        timeout /t 2 >nul
    )
)

echo.
echo All projects launched in separate windows.
