@echo off
REM FORLIU CLI Launcher (Windows)
REM 用法: forliu <command> [options]

setlocal

REM 找到脚本所在目录
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

REM 优先 python3，fallback 到 python
where python3 >nul 2>&1
if %ERRORLEVEL%==0 (
    python3 -m code.main %*
) else (
    python -m code.main %*
)
