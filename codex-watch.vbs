' codex-watch.vbs — Windows launcher for codex-watch.py
' Runs silently in background.  Edit paths below to match your setup.
'
' Usage: place in shell:startup or run via Task Scheduler at logon.

Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "python C:\Users\YOUR_USERNAME\.codex\codex-watch.py", 0, False
'                ^^^^^^              ^^^^^^^^^^^^^
'                Your Python          Your .codex path
'                (or full path to python.exe)
