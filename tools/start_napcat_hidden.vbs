' 校园待办 - NapCat 静默启动
' 有 uin.txt 就走快速登录，没有就显示二维码
Dim WshShell, fso, uin, args, cmd
Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

args = ""
If fso.FileExists("E:\CampusTodo\NapCat\uin.txt") Then
    On Error Resume Next
    uin = Trim(fso.OpenTextFile("E:\CampusTodo\NapCat\uin.txt", 1).ReadLine)
    On Error GoTo 0
    If Len(uin) > 4 Then args = " -q " & uin
End If

cmd = "cmd /c cd /d ""E:\CampusTodo\NapCat"" && launcher-user.bat" & args & _
      " >> ""E:\CampusTodo\data\logs\napcat.log"" 2>&1"
WshShell.Run cmd, 0, False