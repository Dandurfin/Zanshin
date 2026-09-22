@echo off
setlocal enableextensions
title Zanshin DojoSync
cd /d "%~dp0"

rem ---------------------------------------------------------------
rem Spusti appku priamo zo zdrojoveho kodu (bez instalacie, bez .exe).
rem Bezi len python.exe (dovryhodny, podpisany), main.py je jeho vstup.
rem Tento subor je vytvoreny lokalne, takze nema "Mark of the Web"
rem (Zone.Identifier) zo ZIPu - SmartScreen ho neblokuje.
rem ---------------------------------------------------------------

rem --- 1. najdi Python -------------------------------------------
set "PY="
where py >nul 2>nul
if not errorlevel 1 set "PY=py"
if not defined PY (
    where python >nul 2>nul
    if not errorlevel 1 set "PY=python"
)
if not defined PY goto :nopython

rem --- 2. zavislosti: instaluj len ked naozaj chybaju -------------
%PY% -c "import customtkinter, pygame, psutil, numpy, PIL" >nul 2>nul
if errorlevel 1 (
    echo.
    echo Prve spustenie - instalujem kniznice, chvilu to potrva...
    echo.
    %PY% -m pip install --disable-pip-version-check -r requirements.txt
    if errorlevel 1 goto :pipfail
)

rem --- 3. spusti appku -------------------------------------------
%PY% main.py
if errorlevel 1 goto :apperror
exit /b 0


:nopython
echo.
echo   Python sa nenasiel.
echo   Nainstaluj ho z https://www.python.org/downloads/
echo   a pri instalacii zaskrtni "Add python.exe to PATH".
echo.
pause
exit /b 1

:pipfail
echo.
echo   Instalacia kniznic zlyhala (pozri chybu vyssie).
echo   Skus rucne:  py -m pip install -r requirements.txt
echo.
pause
exit /b 1

:apperror
echo.
echo   Appka skoncila s chybou. Detaily su v:
echo   %%APPDATA%%\Dandurf\logs\crash.log  (alebo v priecinku logs\)
echo.
pause
exit /b 1
