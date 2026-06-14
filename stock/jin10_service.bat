@echo off
REM 金十快讯订阅服务 - 后台启动脚本
REM 使用 pythonw.exe 运行，无控制台窗口

cd /d "%~dp0"

REM 检查是否已在运行
tasklist /fi "imagename eq pythonw.exe" /fo csv 2>NUL | findstr /i "pythonw" >NUL
if %errorlevel% equ 0 (
    echo 服务可能已在运行中
    exit /b 0
)

REM 日志目录
if not exist logs mkdir logs

REM 使用 pythonw.exe 无窗口运行
start "" pythonw.exe jin10_subscriber.py

echo 金十订阅服务已启动
echo 日志目录: logs\
exit /b 0
