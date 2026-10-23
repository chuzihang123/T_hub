@echo off
rem Launch MCHOSE HUB with a Chrome DevTools port so the HID traffic can be
rem inspected from outside. Close any running HUB first, otherwise the
rem single-instance lock swallows the flag.
set "EXE=C:\Program Files\MCHOSE HUB\MCHOSE HUB.exe"
start "" "%EXE%" --remote-debugging-port=9222
