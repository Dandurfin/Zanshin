# ============================================================================
# build_steam.ps1 - postavi Steam build Zanshin DojoSync na Windows
#
# Co robi:
#   1. overi zavislosti (Python, PyInstaller)
#   2. ak chyba ikona, vyrobi ju (make_icon.py)
#   3. spusti predbeznu kontrolu (check_before_run.py) - build sa NEspusti,
#      ak kontrola zlyha
#   4. postavi .exe cez ZanshinDojoSync_steam.spec (bez UAC)
#   5. vypise dalsi krok (nahratie depotu cez steamcmd)
#
# NEnahrava nic na Steam - to je posledny krok, ktory spustis rucne s
# vlastnym Steamworks uctom (viz steam\README_STEAM.md).
#
# Spustenie:  powershell -ExecutionPolicy Bypass -File build_steam.ps1
# ============================================================================

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Step($msg) { Write-Host "`n=== $msg ===" -ForegroundColor Cyan }

Step "1/5  Kontrola zavislosti"
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { Write-Error "Python nie je v PATH. Nainstaluj Python 3 a skus znova."; exit 1 }
python -m PyInstaller --version 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "PyInstaller chyba - instalujem..." -ForegroundColor Yellow
    python -m pip install pyinstaller
    if ($LASTEXITCODE -ne 0) { Write-Error "Instalacia PyInstalleru zlyhala."; exit 1 }
}
python -m pip install -r requirements.txt --quiet

Step "2/5  Ikona"
if (-not (Test-Path "Dandurf.ico")) {
    python make_icon.py
} else {
    Write-Host "Dandurf.ico uz existuje - preskakujem (zmaz ju, ak ju chces prekreslit)"
}

Step "3/5  Predbezna kontrola"
python check_before_run.py
if ($LASTEXITCODE -ne 0) {
    Write-Error "check_before_run.py zlyhal - build zastaveny. Oprav chyby vyssie."
    exit 1
}

Step "4/5  Build .exe (Steam variant, bez UAC)"
if (Test-Path "build") { Remove-Item "build" -Recurse -Force }
if (Test-Path "dist\ZanshinDojoSync") { Remove-Item "dist\ZanshinDojoSync" -Recurse -Force }
# POZN: `python -m PyInstaller`, NIE holy prikaz `pyinstaller`. PyInstaller
# sa da mat nainstalovany ako modul bez toho, aby jeho Scripts\ priecinok
# bol v PATH - a presne to tu bol pripad: kontrola vyssie overila, ze sa
# MODUL da importovat, a build potom spadol na "pyinstaller: The term is
# not recognized". build_all.ps1 to uz robilo spravne cez `-m PyInstaller`,
# tento skript ostal pozadu. `--clean` zahodi aj cache z predosleho behu.
python -m PyInstaller --noconfirm --clean ZanshinDojoSync_steam.spec
if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller skoncil s kodom $LASTEXITCODE."
    exit 1
}
if (-not (Test-Path "dist\ZanshinDojoSync\ZanshinDojoSync.exe")) {
    Write-Error "Build nevytvoril .exe - pozri vystup PyInstalleru vyssie."
    exit 1
}

Step "5/5  Hotovo"
$exe = Resolve-Path "dist\ZanshinDojoSync\ZanshinDojoSync.exe"
Write-Host "Build hotovy:" -ForegroundColor Green
Write-Host "  $exe"
Write-Host ""
Write-Host "Dalsi krok - nahratie na Steam (potrebujes App ID a steamcmd):" -ForegroundColor Yellow
Write-Host "  1. v steam\app_build.vdf nahrad oba PLACEHOLDER svojimi ID"
Write-Host "  2. steamcmd +login TVOJ_UCET +run_app_build `"$PSScriptRoot\steam\app_build.vdf`" +quit"
Write-Host ""
Write-Host "Podrobnosti: steam\README_STEAM.md a STEAM_BUILD.md"
