@echo off
rem Postavi Zanshin a instalacku na jedno kliknutie (dvojklik).
rem Iba tenky wrapper okolo build_all.ps1 - .ps1 sa nedá spustit dvojklikom
rem (Windows ho standardne otvara v Poznamkovom bloku), toto ano.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_all.ps1"
pause
