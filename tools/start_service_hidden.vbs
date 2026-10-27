' 校园待办 - 开机静默启动
' 为什么不用 pythonw：pythonw 没有 stdout，uvicorn 写日志时会崩
' 改用 python.exe + 隐藏窗口 + 输出重定向到日志文件
Dim WshShell, cmd
Set WshShell = CreateObject("WScript.Shell")
cmd = "cmd /c cd /d ""E:\CampusTodo\app"" && " & _
      """C:\Users\20289_53h193v\.venv_campus\Scripts\python.exe"" main.py " & _
      ">> ""E:\CampusTodo\data\logs\service.log"" 2>&1"
WshShell.Run cmd, 0, False