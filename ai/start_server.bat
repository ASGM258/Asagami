@echo off
chcp 65001 >nul
REM ============================================================
REM  Anime AI Service - launcher
REM  NOTE: Keep this file pure ASCII. cmd.exe parses .bat using the
REM  system ANSI codepage (GBK on Chinese Windows), so UTF-8 Chinese
REM  text here gets mangled into invalid commands. All output text is
REM  therefore in English on purpose.
REM
REM  NOTE: no --loop flag needed. app/main.py sets the Windows event
REM  loop policy (SelectorEventLoop) at import time, because psycopg's
REM  async pool cannot run on the default ProactorEventLoop.
REM ============================================================

cd /d "%~dp0"

set "PYTHON=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"

echo ============================================================
echo   Anime AI Service (FastAPI)
echo ============================================================
echo   Python : %PYTHON%
echo   Config : %~dp0.env
echo   URL    : http://localhost:5000
echo   Docs   : http://localhost:5000/api/docs
echo ============================================================
echo.
echo Starting... (press Ctrl+C to stop)
echo.

REM --reload watches file changes; drop it for production.
"%PYTHON%" -m uvicorn app.main:app --host 0.0.0.0 --port 5000 --reload

echo.
echo Service stopped.
pause
