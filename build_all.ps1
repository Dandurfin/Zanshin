# Postavi Zanshin.exe a z neho instalacku Zanshin-0.1-setup.exe
#
# Spustenie (funguje z hociakeho adresara):
#     powershell -ExecutionPolicy Bypass -File ".\build_all.ps1"
#
# Potrebujes:
#   Python 3   ->  https://www.python.org/downloads/
#   Inno Setup 6  ->  https://jrsoftware.org/isdl.php   (na krok 3/3)
#
# Pozn.: zamerne NEnastavujeme $ErrorActionPreference = "Stop" - v PowerShelli
# 5.1 vie externy program zapisom na stderr vyhodit vynimku aj ked dobehol
# v poriadku. Navratove kody preto kontrolujeme rucne.

Set-Location -Path $PSScriptRoot
Write-Host "Priecinok: $PSScriptRoot" -ForegroundColor DarkGray

function Fail($message) {
    Write-Host ""
    Write-Host "CHYBA: $message" -ForegroundColor Red
    exit 1
}

# --------------------------------------------------------------------------
# 1/3  Python a zavislosti
# --------------------------------------------------------------------------
Write-Host ""
Write-Host "=== 1/3  Kontrola zavislosti ===" -ForegroundColor Cyan

# Na Windows sa Python vola raz 'python', inokedy len 'py'. Skusime oboje.
# Pozor: holy 'python' byva aliasom na Microsoft Store, ktory nic nespusti -
# preto kazdeho kandidata realne otestujeme.
$pythonCandidates = @(
    @{ Exe = 'py';      Pre = @('-3') },
    @{ Exe = 'python';  Pre = @() },
    @{ Exe = 'python3'; Pre = @() }
)
$PY = $null
foreach ($candidate in $pythonCandidates) {
    if (-not (Get-Command $candidate.Exe -ErrorAction SilentlyContinue)) { continue }
    $probeArgs = $candidate.Pre + @('-c', 'import sys')
    & $candidate.Exe @probeArgs 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) { $PY = $candidate; break }
}
if (-not $PY) {
    Fail "Nenasiel som Python. Nainstaluj ho z python.org a pri instalacii zaskrtni 'Add python.exe to PATH'."
}

function Invoke-Py {
    $callArgs = $PY.Pre + $args
    & $PY.Exe @callArgs
}

$version = Invoke-Py '-c' 'import sys; print(sys.version.split()[0])'
Write-Host "Python $version  ($($PY.Exe) $($PY.Pre))" -ForegroundColor Green

foreach ($module in @('edge_tts', 'comtypes', 'pystray', 'PIL',
                     'customtkinter', 'numpy', 'pygame')) {
    Invoke-Py '-c' "import $module" 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Chyba modul $module - instalujem zavislosti..." -ForegroundColor Yellow
        Invoke-Py '-m' 'pip' 'install' '-r' 'requirements.txt'
        if ($LASTEXITCODE -ne 0) { Fail "pip install zlyhal." }
        break
    }
}

Invoke-Py '-m' 'PyInstaller' '--version' 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Chyba PyInstaller - instalujem..." -ForegroundColor Yellow
    Invoke-Py '-m' 'pip' 'install' 'pyinstaller'
    if ($LASTEXITCODE -ne 0) { Fail "Instalacia PyInstalleru zlyhala." }
}

if (-not (Test-Path "Dandurf.ico")) {
    Write-Host "Chyba Dandurf.ico - generujem..." -ForegroundColor Yellow
    Invoke-Py 'make_icon.py'
    if ($LASTEXITCODE -ne 0) { Fail "make_icon.py zlyhal." }
}

# --------------------------------------------------------------------------
# 2/3  Balenie .exe
# --------------------------------------------------------------------------
Write-Host ""
Write-Host "=== 2/3  Balim Zanshin.exe ===" -ForegroundColor Cyan

# Windows drzi zamok na kazdom spustenom .exe. Ak appka prave bezi (typicky
# minimalizovana v systemovej liste), PyInstaller ju neprepise a spadne na
# "Access is denied". Zatvorime ju teda sami.
$running = Get-Process -Name 'Zanshin' -ErrorAction SilentlyContinue
if ($running) {
    Write-Host "Appka prave bezi - zatvaram ju, inak sa novy build neda zapisat." -ForegroundColor Yellow
    $running | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
}

# Onedir build (Dandurf.spec) - vysledok je priecinok dist\Zanshin\,
# nie jeden .exe. Zmazeme ho vopred cely, nech nezostavaju stare kniznice
# zo starsich verzii zavislosti.
if (Test-Path "dist\Zanshin") {
    try {
        Remove-Item "dist\Zanshin" -Recurse -Force -ErrorAction Stop
    } catch {
        Fail ("Stary dist\Zanshin\ sa neda zmazat. Zatvor bezucu appku " +
              "(pravy klik na ikonu v systemovej liste -> Ukoncit). " +
              "Ak nebezi, subor moze drzat antivirus alebo otvoreny Prieskumnik.")
    }
}

Write-Host "Trva to zvycajne 1-3 minuty..." -ForegroundColor DarkGray

Invoke-Py '-m' 'PyInstaller' '--noconfirm' '--clean' 'Dandurf.spec'
if ($LASTEXITCODE -ne 0) { Fail "PyInstaller skoncil s kodom $LASTEXITCODE." }
if (-not (Test-Path "dist\Zanshin\Zanshin.exe")) {
    Fail "PyInstaller nevyrobil dist\Zanshin\Zanshin.exe"
}

$distMb = [math]::Round((Get-ChildItem "dist\Zanshin" -Recurse |
    Measure-Object -Property Length -Sum).Sum / 1MB, 1)
Write-Host "dist\Zanshin\ hotovo ($distMb MB)" -ForegroundColor Green

# --------------------------------------------------------------------------
# 3/3  Instalacka
# --------------------------------------------------------------------------
Write-Host ""
Write-Host "=== 3/3  Skladam instalacku ===" -ForegroundColor Cyan

$isccCandidates = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "${env:LOCALAPPDATA}\Programs\Inno Setup 6\ISCC.exe"
)
$iscc = $isccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) {
    $found = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($found) { $iscc = $found.Source }
}

if (-not $iscc) {
    Write-Host ""
    Write-Host "Inno Setup som nenasiel - instalacku som nepostavil." -ForegroundColor Yellow
    Write-Host "Stiahni ho zadarmo z https://jrsoftware.org/isdl.php a spusti tento skript znova."
    Write-Host "Priecinok dist\Zanshin\ uz funguje aj takto - staci spustit .exe v nom." -ForegroundColor Green
    exit 0
}

# Instalator hovori vsetkymi 9 jazykmi appky. Cinstinu Inno Setup nedodava,
# preklad je v projekte (installer_lang\ChineseSimplified.isl) a MUSI byt
# UTF-8 s BOM - bez BOM by kompilator znaky precital ako ANSI a v dialogu
# by boli rozsypane. Radsej to overime, nez by sme dodali pokazeny build.
$zhIsl = "installer_lang\ChineseSimplified.isl"
if (-not (Test-Path $zhIsl)) { Fail "Chyba $zhIsl (cinsky preklad instalatora)." }
$bom = [IO.File]::ReadAllBytes($zhIsl)[0..2]
if (-not ($bom[0] -eq 0xEF -and $bom[1] -eq 0xBB -and $bom[2] -eq 0xBF)) {
    Fail "$zhIsl nie je ulozeny ako UTF-8 s BOM - uloz ho tak (napr. v Poznamkovom bloku: Ulozit ako -> UTF-8 s BOM)."
}

& $iscc "Dandurf.iss"
if ($LASTEXITCODE -ne 0) { Fail "Inno Setup skoncil s kodom $LASTEXITCODE." }

$setup = Get-ChildItem "installer\*setup.exe" -ErrorAction SilentlyContinue |
         Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $setup) { Fail "Inno Setup nevyrobil ziadny setup.exe v priecinku installer\." }

$setupMb = [math]::Round($setup.Length / 1MB, 1)
Write-Host ""
Write-Host "HOTOVO: $($setup.FullName) ($setupMb MB)" -ForegroundColor Green
Write-Host "Instalator ma 9 jazykov (en, sk, ja, zh, ru, es, de, fr, pt), predvolena je anglictina."
Write-Host "Instaluje sa do %LOCALAPPDATA%\Programs\Zanshin (bez UAC)."
Write-Host "Pouzivatelske data (nastavenia, nahravky, TTS cache) idu do %APPDATA%\Zanshin."
Write-Host "Pri prvom spusteni ta SmartScreen moze upozornit - 'Dalsie informacie' -> 'Spustit aj tak'." -ForegroundColor DarkGray
