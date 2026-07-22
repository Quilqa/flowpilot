' Stops the FlowPilot server started by start_silent.vbs.
' Kills any pythonw.exe process whose command line runs server.py.

Option Explicit

Dim wmi, procs, p, killed
Set wmi = GetObject("winmgmts:\\.\root\cimv2")
Set procs = wmi.ExecQuery( _
    "SELECT ProcessId, CommandLine FROM Win32_Process " & _
    "WHERE Name = 'pythonw.exe'")

killed = 0
For Each p In procs
    If Not IsNull(p.CommandLine) Then
        If InStr(LCase(p.CommandLine), "server.py") > 0 Then
            p.Terminate()
            killed = killed + 1
        End If
    End If
Next

If killed = 0 Then
    WScript.Echo "FlowPilot server was not running."
End If
