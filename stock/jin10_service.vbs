' 金十快讯订阅 - 后台启动 (VBS)
' 完全无窗口运行 pythonw.exe
Set objShell = CreateObject("WScript.Shell")
strPath = objShell.CurrentDirectory
objShell.CurrentDirectory = "J:\zss\stock"
objShell.Run "pythonw.exe J:\zss\stock\jin10_subscriber.py", 0, False
