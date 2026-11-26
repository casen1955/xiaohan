' 小涵开机自启（微信 4.x + pythonw）
' 把这个文件放进启动文件夹：Win+R -> shell:startup
' 说明：中文注释会让 cscript 按 ANSI 读 UTF-8 出错，所以这里只写英文注释。

base = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\"))
Set sh = CreateObject("WScript.Shell")
Set svc = GetObject("winmgmts:\\.\root\cimv2")

' 1) 微信没开就先开（路径按自己机器改）
wxExe = "C:\Program Files\Tencent\Weixin\Weixin.exe"
If svc.ExecQuery("SELECT * FROM Win32_Process WHERE Name='Weixin.exe'").Count = 0 Then
    On Error Resume Next
    sh.Run """" & wxExe & """", 1, False
    On Error GoTo 0
    WScript.Sleep 25000
End If

' 2) 拉起小涵（pythonw 无窗口；路径按自己机器改）
py = "pythonw.exe"
sh.CurrentDirectory = base
sh.Run """" & py & """ -m app.main --wx4", 0, False
