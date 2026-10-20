@echo off
REM Install bilibili-cognitive-server into an isolated venv (ai\.venv-mcp).
REM NOTE: keep this file ASCII-only. cmd.exe parses .bat with the ANSI codepage,
REM so non-ASCII text here shows up as mojibake.
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] main venv not found: ai\.venv
  exit /b 1
)

if not exist ".venv-mcp\Scripts\python.exe" (
  echo [1/3] creating .venv-mcp ...
  ".venv\Scripts\python.exe" -m venv .venv-mcp
  if errorlevel 1 goto :fail
)

echo [2/3] installing bilibili-cognitive-server ^(no ASR deps^) ...
".venv-mcp\Scripts\python.exe" -m pip install --no-deps bilibili-cognitive-server
if errorlevel 1 goto :fail

echo [3/3] installing runtime deps ...
".venv-mcp\Scripts\python.exe" -m pip install fastmcp httpx pydantic pydantic-settings loguru redis protobuf
if errorlevel 1 goto :fail

echo.
echo [OK] bili-mcp is ready: .venv-mcp\Scripts\bili-mcp.exe
echo      Video search works anonymously; fill BILI_SESSDATA / BILI_BILI_JCT
echo      in .env only if you need login-only tools.
exit /b 0

:fail
echo [ERROR] installation failed, see messages above
exit /b 1
