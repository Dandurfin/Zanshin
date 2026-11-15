@echo off
rem Builds Zanshin and the installer in one go (double-click it).
rem Just a thin wrapper around build_all.ps1 - a .ps1 can't be started by a
rem double-click (Windows opens it in Notepad by default), this file can.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_all.ps1"
pause
