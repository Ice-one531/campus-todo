' ============================================
'  校园通知智能待办 - 启动器
'  注意：本文件在 tools 子目录下，根目录要往上找一级
' ============================================
Dim ws, fso, scriptDir, base, py, main, logDir
Set ws = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' 本文件在 <根>\tools\launch.vbs，所以根目录是它的上两级
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
base = fso.GetParentFolderName(scriptDir)

py   = base & "\python\python.exe"
main = base & "\app\main.py"
logDir = base & "\data"

If Not fso.FolderExists(logDir) Then fso.CreateFolder(logDir)

' 先检查服务是否已在运行
Dim http, running
running = False
On Error Resume Next
Set http = CreateObject("MSXML2.XMLHTTP")
http.Open "GET", "http://127.0.0.1:8000/health", False
http.Send
If Err.Number = 0 And http.Status = 200 Then running = True
Err.Clear
On Error GoTo 0

If Not running Then
    ' 启动服务（窗口完全隐藏，日志写文件）
    ws.Run "cmd /c cd /d """ & base & "\app"" && """ & py & """ main.py >> """ & logDir & "\service.log"" 2>&1", 0, False

    ' 等最多 30 秒
    Dim i
    For i = 1 To 60
        WScript.Sleep 500
        On Error Resume Next
        http.Open "GET", "http://127.0.0.1:8000/health", False
        http.Send
        If Err.Number = 0 And http.Status = 200 Then
            running = True
            Exit For
        End If
        Err.Clear
        On Error GoTo 0
    Next
End If

' 打开界面
ws.Run "cmd /c start http://127.0.0.1:8000/console/", 0, False