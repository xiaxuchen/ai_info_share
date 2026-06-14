@echo off
REM 停止金十订阅服务
taskkill /fi "imagename eq pythonw.exe" /f 2>NUL
echo 已停止
