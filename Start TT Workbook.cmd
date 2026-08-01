@echo off
setlocal
cd /d "%~dp0"
title TT Workbook

where uv >nul 2>&1
if errorlevel 1 (
    echo Installing uv. This happens only once.
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    rem The installer only updates PATH for new sessions.
    set "PATH=%USERPROFILE%\.local\bin;%PATH%"
)

where uv >nul 2>&1
if errorlevel 1 (
    echo uv could not be installed automatically.
    echo Check the internet connection, then run this file again.
    echo.
    pause
    exit /b 1
)

if not exist ".env" copy ".env.example" ".env" >nul

findstr /r /c:"^OPENAI_API_KEY=..*" ".env" >nul
if errorlevel 1 (
    echo.
    echo Notepad will open. Add your key after OPENAI_API_KEY=
    echo Save the file and close Notepad to continue.
    echo.
    start /wait notepad ".env"
)

findstr /r /c:"^OPENAI_API_KEY=..*" ".env" >nul
if errorlevel 1 (
    echo No API key was saved in .env. Run this file again once you have the key.
    echo.
    pause
    exit /b 1
)

echo Preparing TT Workbook. The first run downloads Python and dependencies.
uv sync
if errorlevel 1 (
    echo Setup failed. Check the internet connection and try again.
    echo.
    pause
    exit /b 1
)

echo.
echo Starting TT Workbook. Keep this window open while using the app.
echo Close this window to stop the app.
echo.
uv run streamlit run "src\tt_automation\app.py"

pause
