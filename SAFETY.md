# Anti-cheat: čo appka robí a čo zámerne nerobí

Tento dokument existuje preto, aby sa dal ukázať — komukoľvek, kto sa spýta,
prečo má hráč počas hrania na obrazovke cudzie okno.

## Krátka odpoveď

Zanshin DojoSync je bežná desktopová aplikácia, ktorá kreslí vlastné
priehľadné okno a prehráva zvuky. **Nedotýka sa procesu hry žiadnym
spôsobom a neinštaluje žiadne systémové hooky.**

## Čo appka nerobí — a nebude robiť

| Technika | Stav | Prečo |
|---|---|---|
| Injekcia DLL do procesu hry | **nikdy** | Prvá vec, ktorú EAC/BattlEye/Ricochet hľadajú |
| Hook `Present` / `SwapChain` (D3D, OpenGL, Vulkan) | **nikdy** | Vykresľovanie ide cez samostatné okno, nie cez hru |
| `ReadProcessMemory` / čítanie pamäte hry | **nikdy** | Appka o hre nevie nič okrem názvu procesu |
| `SetWindowsHookEx` — akýkoľvek, vrátane `WH_KEYBOARD_LL` | **nikdy** | Od verzie 2.1 žiadny. Viď nižšie |
| `WDA_EXCLUDEFROMCAPTURE` (skrytie pred screenshotmi) | **zámerne nie** | Viď nižšie — je to dôležité |
| Čítanie alebo zachytávanie obsahu obrazovky | **nikdy** | Appka nevie, čo je na obrazovke |
| Simulovanie vstupu do hry | **nikdy** | Žiadne `SendInput`, `keybd_event` ani `mouse_event` |
| Elevácia (administrátorské práva) | **nikdy** | `uac_admin=False`, `PrivilegesRequired=lowest` |

## Klávesnicu appka nepočúva

Do verzie 2.0 appka inštalovala globálny klávesový hook (`WH_KEYBOARD_LL`
cez knižnicu `pynput`), pretože hlášku spúšťalo stlačenie klávesu. Hook bol
čisto pasívny — nikdy nič nepohltil ani neoneskoril — ale navonok to bola
jediná časť appky, ktorá vyzerala ako keylogger.

**Vo verzii 2.1 je preč.** Hlášku už nespúšťa klávesa, ale telo: záťaž
odvodená z tepu z hodiniek. Knižnica `pynput` nie je v závislostiach ani
v builde.

Appka potrebuje vedieť jedinú vec o vstupe — či je hráč práve aktívny, aby
hlášku doručila v prestávke a nie uprostred prestrelky. Zisťuje to cez
`GetLastInputInfo`, čo je funkcia Win32 API, ktorá vracia **jedno číslo:
koľko milisekúnd uplynulo od posledného vstupu.** Neprezradí, ktorý kláves
to bol, ani či to kláves vôbec bol. Neinštaluje sa pri tom nič.

Voliteľne appka číta aj stav gamepadu cez štandardnú SDL2 vrstvu (`pygame`)
— tiež len na to, aby vedela, že hráč je aktívny. Ktoré tlačidlo sa stlačilo,
sa nikam nezapisuje.

Overiť sa to dá: `pynput` nie je v `requirements.txt`, v `.spec` súboroch ani
nikde v kóde, a `check_before_run.py` build zastaví, keby sa vrátil.

## Prečo nie `WDA_EXCLUDEFROMCAPTURE`

`SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)` by spôsobil, že
overlay nie je vidieť na screenshotoch ani v OBS. Znie to ako slušnosť voči
streamerom, ale je to **presne to správanie, podľa ktorého sa hľadajú
podvodné prekrytia** — ESP/wallhacky sa skrývajú rovnakým volaním.

Náš overlay má byť na každom zázname a screenshote vidno. To je jeho
najlepšia obhajoba: čokoľvek, čo appka kreslí, vie hráč komukoľvek ukázať.

## Čo appka robí

Jedno alebo viac okien typu `WS_EX_LAYERED` s týmito štýlmi:

- `WS_EX_TRANSPARENT` — klik prejde naskrz do hry. Okno nikdy neukradne vstup.
- `WS_EX_NOACTIVATE` — okno sa nikdy nestane aktívnym. Hra nestratí focus.
- `WS_EX_TOOLWINDOW` — nie je v Alt+Tab ani na paneli úloh.

Obsah okna sa skladá cez `UpdateLayeredWindow` — ten istý systémový
mechanizmus, aký používajú systémové tooltipy a Windows Ink.

### Úplný zoznam toho, čo sa appka dozvedá zvonku

1. **Obdĺžnik aktívneho okna** (`GetForegroundWindow` + `GetWindowRect`) —
   len aby vedela, na ktorom monitore kresliť.
2. **Názov bežiaceho procesu** (`psutil`) — voliteľne, na automatické
   prepínanie profilov. Nič sa z procesu nečíta.
3. **Milisekundy od posledného vstupu** (`GetLastInputInfo`) — bez toho,
   aby vedela, aký vstup to bol.
4. **Stav gamepadu** (SDL2) — voliteľne, tiež len ako známka aktivity.
   Názov stlačeného tlačidla sa nikam nezapisuje.
5. **Tep zo siete** — appka *počúva* na lokálnom porte, sama nikam
   nepripája. Z hodiniek chodí jedno číslo za sekundu.
5b. **Kroky a rýchlosť z hodiniek** — ak ich appka na hodinkách posiela
   (prémiová verzia), Zanshin ich prečíta z tej istej správy ako tep.
   Slúžia na jedinú vec: **keď sa hýbeš, appka mlčí a meranie sa nezapočíta**.
   Chôdza dvihne tep rovnako ako stres a z tepu sa to rozlíšiť nedá — ani
   plné EKG s 55 príznakmi to pri strednej aktivite nezvládne. Nikam sa
   neposielajú a do histórie sa ukladá len to, či si bol v pohybe, nie kde
   si bol. Kód: `heart_rate.parse_metrics`, `hr_stats.note_metrics`.
6. **Jedna klávesová kombinácia** (`RegisterHotKey`) — „teraz nie".
7. **Poloha kurzora myši** (`GetCursorPos`) — len súradnice bodu, a len na
   to, aby sa zistilo, na ktorom monitore je hráč. Nečíta sa, čo je pod ním,
   ani sa nikam nezapisuje trasa. Kód: `display.monitor_at_cursor`.

To je celé. Nič z toho neopúšťa počítač.

### Prečo bod 6 nie je návrat hooku

Je to jediné miesto, kde appka vôbec počuje klávesnicu, a stojí za to
povedať presne, ako. `RegisterHotKey` funguje **naopak než hook**: appka
Windowsu vopred ohlási jednu konkrétnu kombináciu a systém jej pošle správu
až vtedy, keď ju niekto stlačí. Žiadny prúd vstupu cez ňu netečie — o
žiadnom inom klávese sa appka nedozvie, ani keby chcela.

| | čo vidí | dá sa ním odpočúvať? |
|---|---|---|
| `WH_KEYBOARD_LL` (zrušené vo fáze 3) | **každý** stlačený kláves | áno |
| `RegisterHotKey` | len ohlásenú kombináciu | nie |

Keď je kombinácia obsadená inou aplikáciou, registrácia jednoducho zlyhá a
appka beží ďalej bez nej. Admin práva to nepotrebuje. Vypnúť sa dá — prázdny
`snooze_hotkey` v nastaveniach.

Kód je v `hotkey.py` a `tests/test_hotkey.py` stráži aj to, že sa v ňom
neobjaví `SetWindowsHookEx`, `WH_KEYBOARD`, `GetAsyncKeyState` ani
`GetKeyboardState`.

### Jediná vec, ktorú appka z týchto zdrojov odvodzuje

Z prieniku bodov 3 a 4 vie povedať **triedu zariadenia**: `GetLastInputInfo`
vidí všetko vrátane ovládača, ale nepovie čo to bolo; SDL2 vidí len ovládač.
Keď teda hlási ovládač, hrá sa na ovládači; keď mlčí a systém hlási vstup,
je to klávesnica alebo myš.

Slúži to na jediné — aby appka vedela napísať, z čoho číta aktivitu.
**Nie je to odtlačok zariadenia.** Výsledok má presne tri hodnoty: ovládač,
klávesnica/myš, alebo *nevieme*. Keď gamepad listener nebeží, je to vždy
*nevieme* — ticho ovládača sa zámerne **neháda** ako klávesnica, lebo by to
bola nepravda napísaná na obrazovke.

Kód je v `activity.py` (`ActivityTracker.source`) a testy v
`tests/test_activity.py` strážia aj to, že sa v objekte nikdy neuloží nič
iné než tie tri hodnoty.

## Exkluzívny fullscreen

V ňom Windows cudzie vrstvené okná nevykreslí vôbec. Nie je to obrana
anti-cheatu, je to vlastnosť systému. Appka to rozpozná
(`display.is_fullscreen_foreground`) a raz za reláciu poradí prepnúť hru na
„Bez okrajov / Borderless".

## Pravidlo pri ďalšom vývoji

Ak sa niekedy objaví požiadavka typu „zobraz v overlayi niečo z hry" —
životy, muníciu, čas do konca kola — odpoveď je nie. V tom momente by appka
musela čítať hru a všetko vyššie by prestalo platiť. Všetko, čo overlay
ukazuje, musí pochádzať **z tela hráča**.
