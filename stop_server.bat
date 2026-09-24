@echo off
echo Stopping E.V Assistant Backend...
taskkill /F /IM python.exe /T 2>nul
taskkill /F /IM py.exe /T 2>nul
echo Done!
