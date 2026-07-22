' FlowPilot silent launcher.
' Starts the web UI server with no console window and no taskbar entry.
' Double-click this file (or point Task Scheduler / a Startup shortcut at it).
'
' It runs pythonw.exe (the windowless Python) on server.py from this folder,
' redirecting all output to logs\server_silent.log. The redirect matters:
' under pythonw the standard streams are absent, so server.py's startup
' print() would otherwise crash the process on launch.
'
' To stop the server, run stop_silent.vbs (or kill pythonw.exe).

Option Explicit

Dim shell, fso, scriptDir, pythonw, q, cmd

Set shell = CreateObject("WScript.Shell")
Set fso   = CreateObject("Scripting.FileSystemObject")

' Always run from the folder this .vbs lives in, whatever the caller's cwd is.
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = scriptDir

' Locate pythonw.exe (the windowless Python). Task Scheduler starts with a
' bare environment where PATH may not include Python, so look in the standard
' per-user install location first and only then fall back to PATH.
pythonw = FindPythonW(fso, shell)

Function FindPythonW(fso, shell)
    Dim base, folder, sub_, candidate
    FindPythonW = "pythonw.exe"  ' fallback: whatever is on PATH

    base = shell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Programs\Python"
    If fso.FolderExists(base) Then
        Set folder = fso.GetFolder(base)
        For Each sub_ In folder.SubFolders   ' e.g. Python310, Python312
            candidate = sub_.Path & "\pythonw.exe"
            If fso.FileExists(candidate) Then
                FindPythonW = candidate
            End If
        Next
    End If
End Function

q = Chr(34)  ' double-quote character

' cmd /c "<pythonw> <server.py> > <logfile> 2>&1"
cmd = "cmd /c " & q & q & pythonw & q & " " & _
      q & scriptDir & "\server.py" & q & " > " & _
      q & scriptDir & "\logs\server_silent.log" & q & " 2>&1" & q

' Run: 0 = hidden window (hides the cmd wrapper too), False = don't wait.
shell.Run cmd, 0, False
