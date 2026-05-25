@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
set "PYTHONDONTWRITEBYTECODE=1"

:: 初始化 conda
call :init_conda
if errorlevel 1 (
    echo Conda is not available.
    pause
    exit /b 1
)

:: 激活 fh6 环境
call conda activate fh6
if errorlevel 1 (
    echo Failed to activate environment 'fh6'
    pause
    exit /b 1
)

:: 验证环境是否激活成功
where python | findstr "fh6" >nul
if errorlevel 1 (
    echo Warning: Python might not be from fh6 environment
)

:: 运行脚本
echo Running auto_scripts.py with environment 'fh6'...
python auto_scripts.py buy.cfg

pause
exit /b %errorlevel%

:init_conda
:: 尝试查找 conda 安装路径
set "CONDA_ROOT="
for %%P in (
    "%USERPROFILE%\anaconda3"
    "%USERPROFILE%\miniconda3"
    "%ProgramData%\anaconda3"
    "%ProgramData%\miniconda3"
    "C:\anaconda3"
    "C:\miniconda3"
) do (
    if exist "%%~P\Scripts\conda.exe" (
        set "CONDA_ROOT=%%~P"
        goto :found_conda
    )
)

:: 尝试通过 where 命令查找
where conda >nul 2>nul
if not errorlevel 1 (
    for /f "delims=" %%i in ('where conda') do (
        set "CONDA_ROOT=%%~dpi\.."
        goto :found_conda
    )
)

exit /b 1

:found_conda
:: 初始化 conda（添加到 PATH 并定义 conda 函数）
call "%CONDA_ROOT%\Scripts\activate.bat" >nul 2>nul
if errorlevel 1 (
    exit /b 1
)
exit /b 0