Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "py C:\sanjay\E.V\backend\run.py", 0, False
WshShell.Run "cmd /c ""%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"" reverse tcp:8000 tcp:8000", 0, False
