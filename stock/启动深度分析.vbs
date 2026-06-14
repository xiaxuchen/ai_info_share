' 金十快讯深度影响分析 - 一键启动 (VBS)
' 双击此文件即可启动
Set objShell = CreateObject("WScript.Shell")
objShell.CurrentDirectory = "J:\zss\stock"

' 1. 检查后台服务
WScript.Echo "正在检查金十后台服务..."
objShell.Run "pythonw.exe J:\zss\stock\jin10_keepalive.py", 1, True

' 2. 运行深度影响分析
WScript.Echo "正在启动深度影响分析..."
objShell.Run "python.exe J:\zss\stock\jin10_impact_analysis.py", 1, True

WScript.Echo "分析完成！请查看飞书多维表格。"
