@echo off
rem Spusti appku priamo zo zdrojoveho kodu (bez instalacie, bez .exe).
rem Smart App Control tu nic neblokuje - spusta sa len python.exe (dovryhodny,
rem podpisany), skript main.py je len jeho vstup, nie samostatny program.
cd /d "%~dp0"
py -m pip install --quiet -r requirements.txt
py main.py
if errorlevel 1 pause
