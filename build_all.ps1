# Postavi Zanshin.exe a z neho instalacku Zanshin-<verzia>-setup.exe
# (verzia = MyAppVersion v Dandurf.iss)
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
    # Python install manager (dnes hlavne tlacidlo na python.org) nema ziadne
    # zaskrtavatko PATH - 'py' ide cez alias vo WindowsApps a Python si pri
    # prvom 'py -3' stiahne sam. Ak ani to neprejde, byva to bez internetu.
    Fail ("Nenasiel som Python (alebo sa ho nepodarilo stiahnut - skontroluj internet). " +
          "Nainstaluj 'Python install manager' z https://www.python.org/downloads/ " +
          "a spusti build.bat znova. Klasicka instalacka z python.org funguje tiez.")
}

function Invoke-Py {
    $callArgs = $PY.Pre + $args
    & $PY.Exe @callArgs
}

$version = Invoke-Py '-c' 'import sys; print(sys.version.split()[0])'
Write-Host "Python $version  ($($PY.Exe) $($PY.Pre))" -ForegroundColor Green

# pyttsx3 (zaloha hlasu Windows) a psutil (automaticke profily) tu chybali -
# bez nich build presiel, ale appka potom ticho prisla o tieto funkcie.
foreach ($module in @('edge_tts', 'comtypes', 'pystray', 'PIL',
                     'customtkinter', 'numpy', 'pygame', 'pyttsx3', 'psutil')) {
    Invoke-Py '-c' "import $module" 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Chyba modul $module - instalujem zavislosti..." -ForegroundColor Yellow
        Invoke-Py '-m' 'pip' 'install' '-r' 'requirements.txt'
        if ($LASTEXITCODE -ne 0) { Fail "pip install zlyhal." }
        break
    }
}

# edge-tts (prirodzeny hlas) build stiahne pri KAZDOM behu v najnovsej
# verzii: Microsoft od novembra 2026 odmieta starsie verzie (HTTP 403) a ked
# nieco zmeni znova, oprava zvycajne pride v novom edge-tts - aj do buildu po
# mesiaci bez vydania. Cyklus vyssie instaluje len CHYBAJUCI modul.
# Strop verzie zamerne nie je (moze zablokovat presne tu opravu) - novu
# verziu preto build za upgradom vyskusa: API bez siete a jedno skusobne
# slovo (nizsie).
# Poziadavka (minimum) je len v requirements.txt. Upgrade dostane
# LEN edge-tts: pip predvolene (--upgrade-strategy only-if-needed) zdvihne
# jeho zavislost, len ked jej verzia edge-tts nestaci; ostatne balicky necha.
# Medzera za menom je zamerna: argument s medzerou da PowerShell 5.1 do
# uvodzoviek, takze ani Python cez .bat (napr. pyenv-win) neberie '<' a '>'
# ako presmerovanie. Verzie porovnava importlib.metadata ciselne - bez
# 'packaging', ten nemusi byt nainstalovany.
$edgeMinVzor = '^\s*edge-tts\s*(>=\s*([0-9]+(?:\.[0-9]+)*)[^#;\r\n]*)'
$edgeMin = $null
foreach ($riadok in Get-Content 'requirements.txt') {
    if ($riadok -match $edgeMinVzor) {
        $edgePoziadavka = 'edge-tts ' + $Matches[1].Trim()
        $edgeMin = $Matches[2]
        break
    }
}
if (-not $edgeMin) { Fail "requirements.txt nema minimum pre edge-tts (riadok edge-tts>=...)." }
$edgeKontrola = "import re, sys, importlib.metadata as m; d = next(iter(m.distributions(name='edge-tts')), None); v = d.version if d else '?'; t = lambda s: tuple(int(c) for c in re.findall(r'\d+', s)); print(v); sys.exit(0 if t(v) >= t(sys.argv[1]) else 1)"
Write-Host "Hladam najnovsi edge-tts ($edgePoziadavka)..." -ForegroundColor DarkGray
Invoke-Py '-m' 'pip' 'install' '--upgrade' '--retries' '1' '--timeout' '15' $edgePoziadavka
$edgePip = $LASTEXITCODE
if ($edgePip -eq 0) {
    # Bez internetu pip skonci OK, ked nainstalovany edge-tts poziadavke
    # vyhovuje (vypise len WARNING Retrying). Index sa preto spytame este raz,
    # bez ohladu na nainstalovany: --dry-run nic neinstaluje, bez siete zlyha.
    Invoke-Py '-m' 'pip' 'install' '--dry-run' '--ignore-installed' '--no-deps' '--quiet' '--retries' '1' '--timeout' '15' $edgePoziadavka 2>&1 | Out-Null
    $edgePip = $LASTEXITCODE
}
$edgeVerzia = "$(Invoke-Py '-c' $edgeKontrola $edgeMin)".Trim()
if ($LASTEXITCODE -ne 0) {
    if ($edgePip -ne 0) {
        Fail "edge-tts je $edgeVerzia, treba aspon $edgeMin, a novsi som nestiahol (skontroluj internet) - prirodzeny hlas by v builde nefungoval."
    }
    Fail "edge-tts je stale $edgeVerzia, treba aspon $edgeMin - prirodzeny hlas by v builde nefungoval."
}
if ($edgePip -ne 0) {
    Write-Host "Najnovsi edge-tts som nevedel overit (bez internetu?) - build pokracuje s nainstalovanym $edgeVerzia." -ForegroundColor Yellow
}

# Retazce pre 'py -c' nizsie: bez uvodzoviek (PowerShell 5.1 ich nativnemu
# programu pokazi, viz $edgeKontrola) a bez znaku percenta - Python cez .bat
# ide cez cmd.exe a ten by %...% bral ako premennu; preto rate='+0' + chr(37)
# (= '+0%', ako edge_rate_str v audio_engine). sys.excepthook vypise namiesto
# tracebacku jeden riadok "Trieda: sprava" - ten ide do hlasky buildu.
# (a) API bez siete: presne volanie z audio_engine (EdgeTTSCache.ensure) -
# Communicate(text, hlas, rate=...) a async save. Ked neprejde, novy edge-tts
# zmenil API: exe by mal prirodzeny hlas mrtvy, build preto zastavi a povie,
# ako sa vratit na posledny fungujuci.
$edgeApi = "import inspect, sys; sys.excepthook = lambda t, e, b: print(t.__name__ + ': ' + str(e)[:160]); import edge_tts; k = edge_tts.Communicate('Zanshin', 'en-GB-SoniaNeural', rate='+0' + chr(37)); ok = inspect.iscoroutinefunction(getattr(k, 'save', None)); ok or print('Communicate.save nie je async'); sys.exit(0 if ok else 1)"
$edgeApiDovod = "$(Invoke-Py '-c' $edgeApi)".Trim()
if ($LASTEXITCODE -ne 0) {
    $pyPrikaz = (@($PY.Exe) + $PY.Pre) -join ' '
    if ($edgeVerzia -eq $edgeMin) {
        # zlyhalo aj samotne minimum - edge-tts sa nezmenil, chyba je okolo neho
        Fail ("edge-tts $edgeVerzia sa neda pouzit ($edgeApiDovod) - chyba je asi v jeho zavislosti. " +
              "Preinstaluj ho: $pyPrikaz -m pip install --force-reinstall `"edge-tts==$edgeVerzia`" a spusti build znova.")
    }
    # Posledny fungujuci: o hlavnu verziu nizsie (8.0 -> <8, najnovsia 7.x);
    # v ramci tej istej hlavnej verzie najnovsia pred tou pokazenou.
    $edgeHlavna = 0
    if ($edgeVerzia -match '^(\d+)') { $edgeHlavna = [int]$Matches[1] }
    $edgeMinHlavna = 0
    if ($edgeMin -match '^(\d+)') { $edgeMinHlavna = [int]$Matches[1] }
    if ($edgeHlavna -gt $edgeMinHlavna) { $edgeSpat = "edge-tts>=$edgeMin,<$edgeHlavna" }
    else { $edgeSpat = "edge-tts>=$edgeMin,<$edgeVerzia" }
    Fail ("edge-tts $edgeVerzia sa zmenil tak, ze ho Zanshin nevie pouzit ($edgeApiDovod). " +
          "Vrat sa na posledny fungujuci: v requirements.txt zmen riadok edge-tts na $edgeSpat a spusti build znova " +
          "(zo zdrojakov rucne: $pyPrikaz -m pip install `"$edgeSpat`"). Natrvalo to opravi az novsi Zanshin.")
}
Write-Host "edge-tts $edgeVerzia ide do buildu (treba aspon $edgeMin)" -ForegroundColor Green

# (b) Skusobne slovo, len s internetom (sonda indexu vyssie): "Zanshin" cez
# Microsoft do docasneho suboru v %TEMP%, ktory sa hned zmaze. Ked neprejde,
# build NEzastavi - exe funguje aj s hlasom z Windows a prirodzeny hlas neskor
# opravi tlacidlo Aktualizovat hlas v appke (alebo dalsi build s novsim
# edge-tts). Hlaska je ale hlasna, nech ju vidno.
if ($edgePip -ne 0) {
    Write-Host "Skusobne slovo vynechavam (bez internetu) - prirodzeny hlas s edge-tts $edgeVerzia som neoveril." -ForegroundColor Yellow
} else {
    $edgeSlovo = "import asyncio, os, sys; sys.excepthook = lambda t, e, b: print(t.__name__ + ': ' + str(e)[:160]); import edge_tts; p = sys.argv[1]; asyncio.run(asyncio.wait_for(edge_tts.Communicate('Zanshin', 'en-GB-SoniaNeural', rate='+0' + chr(37)).save(p), 30)); n = os.path.getsize(p); n or print('prazdny zvuk'); sys.exit(0 if n else 1)"
    $edgeSubor = Join-Path $env:TEMP ('zanshin-edge-tts-' + [guid]::NewGuid().ToString('N') + '.mp3')
    $edgeSlovoDovod = "$(Invoke-Py '-c' $edgeSlovo $edgeSubor)".Trim()
    $edgeSlovoKod = $LASTEXITCODE
    Remove-Item -LiteralPath $edgeSubor -Force -ErrorAction SilentlyContinue
    if ($edgeSlovoKod -eq 0) {
        Write-Host "prirodzeny hlas overeny (edge-tts $edgeVerzia)" -ForegroundColor Green
    } else {
        Write-Host ""
        Write-Host "!!! POZOR: Microsoft odmieta aj edge-tts $edgeVerzia, alebo jeho hlasova sluzba prave neodpoveda ($edgeSlovoDovod)." -ForegroundColor Yellow
        Write-Host "!!! Build pokracuje, ale prirodzeny hlas v nom teraz nejde - pripomienky povie hlas z Windows." -ForegroundColor Yellow
        Write-Host "!!! Opravit ho vie tlacidlo Aktualizovat hlas v appke (ked vyjde novsi edge-tts) alebo dalsi build." -ForegroundColor Yellow
        Write-Host ""
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

# Predbezna kontrola (preklady, volania, ziadny klavesovy hook, ziadna Steam
# vrstva). Doteraz ju spustal len Steam build - verejny instalator nie.
Write-Host "Predbezna kontrola (check_before_run.py)..." -ForegroundColor DarkGray
$env:PYTHONIOENCODING = 'utf-8'
Invoke-Py 'check_before_run.py'
if ($LASTEXITCODE -ne 0) { Fail "check_before_run.py nasiel problem - build som nespustil." }

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
    # Instalacka sa nevydava (bez podpisoveho certifikatu) - hrac ju nepotrebuje,
    # takze ho tu neposielame stahovat Inno Setup. Vyvojar, ktory ju chce,
    # vie z DEVELOPMENT.md, ze staci Inno Setup 6 nainstalovat a skript spustit znova.
    Write-Host "Inno Setup som nenasiel - instalacku som nepostavil (netreba ju)." -ForegroundColor Yellow
    Write-Host "HOTOVO: appka je dist\Zanshin\Zanshin.exe - staci ju spustit." -ForegroundColor Green
    exit 0
}

# Instalator hovori vsetkymi 11 jazykmi appky. Cinstinu Inno Setup nedodava,
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
Write-Host "Instalator ma 11 jazykov (en, sk, ja, zh, ru, es, de, fr, pt, cs, bg), predvolena je anglictina."
Write-Host "Instaluje sa do %LOCALAPPDATA%\Programs\Zanshin (bez UAC)."
Write-Host "Pouzivatelske data (nastavenia, nahravky, TTS cache) idu do %APPDATA%\Zanshin."
Write-Host "Pri prvom spusteni ta SmartScreen moze upozornit - 'Dalsie informacie' -> 'Spustit aj tak'." -ForegroundColor DarkGray
