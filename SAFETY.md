# Anti-cheat: čo appka robí a čo zámerne nerobí

## In English, in short

**Anti-cheat in short.** Zanshin draws its own transparent, click-through
window and nothing more. It never enters the game process, never hooks
rendering, never reads game memory or the screen, never simulates input,
installs no keyboard hook and never asks for administrator rights. It
deliberately does not hide from screenshots or OBS, because that's what cheat
overlays do. Only an anti-cheat's maker can guarantee it won't flag you.

The one time the window takes clicks is while you preview a picture
(**▶ Show**) to drag it into place; the preview ends when you close that
dialog or start watching.

| Technique | Status | Why |
|---|---|---|
| DLL injection into the game process | **never** | The first thing EAC, BattlEye and Ricochet look for |
| Hooking `Present` / `SwapChain` (D3D, OpenGL, Vulkan) | **never** | Drawing goes through a separate window, not through the game |
| `ReadProcessMemory` / reading game memory | **never** | The app knows nothing about the game except the process name and the position and size of the window in front |
| `SetWindowsHookEx` — any kind, including `WH_KEYBOARD_LL` | **never** | Not in any public version |
| `WDA_EXCLUDEFROMCAPTURE` (hiding from screenshots) | **deliberately not** | Hiding is exactly what cheat overlays do |
| Reading or capturing the screen | **never** | The app doesn't know what's on screen; that's why its colour picker has no eyedropper |
| Simulating input to the game | **never** | No `SendInput`, `keybd_event` or `mouse_event` |
| Elevation (administrator rights) | **never** | `uac_admin=False`, `PrivilegesRequired=lowest` |

Everything Zanshin learns from outside its own window: the rectangle of the
window in front (to pick the monitor), the names of running programs (only
with automatic profile switching on), the milliseconds since your last input
(not which key), controller activity (while it's watching), heart rate and
steps from your phone over the network, one shortcut ("not now", Ctrl+Alt+Z
by default, through `RegisterHotKey`, not a hook; you can change it or switch
it off in Settings → General), the list of installed keyboard layouts (only
to check whether that shortcut would type a letter), where the mouse pointer
is (to pick the monitor), the microphone (only while you record your own
cue), and this PC's network adapters, IP addresses and monitors. None of it
leaves the PC.

The rest of this document is in Slovak.

---

Tento dokument existuje preto, aby sa dal ukázať — komukoľvek, kto sa spýta,
prečo má hráč počas hrania na obrazovke cudzie okno.

## Krátka odpoveď

Zanshin je bežná desktopová aplikácia, ktorá kreslí vlastné
priehľadné okno a prehráva zvuky. **Nedotýka sa procesu hry žiadnym
spôsobom a neinštaluje žiadne systémové hooky.**

Tento dokument presne opisuje, čo appka robí a čo nie. Záruku, že ťa
konkrétny anti-cheat nezablokuje, však môže dať len jeho výrobca.

## Čo appka nerobí — a nebude robiť

| Technika | Stav | Prečo |
|---|---|---|
| Injekcia DLL do procesu hry | **nikdy** | Prvá vec, ktorú EAC/BattlEye/Ricochet hľadajú |
| Hook `Present` / `SwapChain` (D3D, OpenGL, Vulkan) | **nikdy** | Vykresľovanie ide cez samostatné okno, nie cez hru |
| `ReadProcessMemory` / čítanie pamäte hry | **nikdy** | Appka o hre nevie nič okrem názvu procesu a polohy/veľkosti okna v popredí |
| `SetWindowsHookEx` — akýkoľvek, vrátane `WH_KEYBOARD_LL` | **nikdy** | V žiadnej verejnej verzii. Viď nižšie |
| `WDA_EXCLUDEFROMCAPTURE` (skrytie pred screenshotmi) | **zámerne nie** | Viď nižšie — je to dôležité |
| Čítanie alebo zachytávanie obsahu obrazovky | **nikdy** | Appka nevie, čo je na obrazovke. Preto ani výber farby nemá pipetku — tá by musela odfotiť plochu aj s hrou |
| Simulovanie vstupu do hry | **nikdy** | Žiadne `SendInput`, `keybd_event` ani `mouse_event` |
| Elevácia (administrátorské práva) | **nikdy** | `uac_admin=False`, `PrivilegesRequired=lowest` |

Repozitár obsahuje aj vývojárske testovacie skripty na ručné testovanie okna
(`gui_harness_auto.py`, `gui_harness_onboarding.py`, `gui_screenshots.py`).
Prvé dva ovládajú skutočnú myš (pohyb, klik, ťahanie, koliesko) a stláčajú
Escape; všetky tri fotia okná a obrázky appky s malým okrajom okolo
(`gui_screenshots.py` s voľbou `--okno` len samotné okno appky). Nie sú
súčasťou postavenej appky ani ZIP-u na stiahnutie: build balí `main.py`,
moduly, ktoré importuje, a priečinok `assets`, a tieto skripty neimportuje
nič. Čo počas behu robia s dátami Zanshinu spusteného zo zdrojákov a ako ich
vracajú, je v [DEVELOPMENT.md](DEVELOPMENT.md).

## Klávesnicu appka nepočúva

Skoršie, neverejné verzie appky inštalovali globálny klávesový hook (`WH_KEYBOARD_LL`
cez knižnicu `pynput`), pretože pripomienku spúšťalo stlačenie klávesu. Hook
bol čisto pasívny — nikdy nič nepohltil ani neoneskoril — ale navonok to bola
jediná časť appky, ktorá vyzerala ako keylogger.

**Pred prvou verejnou alfou bol zrušený.** Pripomienku už nespúšťa klávesa,
ale telo: záťaž odvodená z tepu z hodiniek. Knižnica `pynput` nie je
v závislostiach ani v builde.

Appka potrebuje vedieť jedinú vec o vstupe — či je hráč práve aktívny, aby
pripomienku doručila v krátkej pauze vo vstupe, nie kým stláčaš klávesy.
Zisťuje to cez `GetLastInputInfo`, čo je funkcia Win32 API, ktorá vracia
**jedno číslo: koľko milisekúnd uplynulo od posledného vstupu.** Neprezradí,
ktorý kláves to bol, ani či to kláves vôbec bol. Neinštaluje sa pri tom nič.

Kým appka sleduje, číta aj ovládač cez štandardnú SDL2 vrstvu (`pygame`)
— tiež len na to, aby vedela, že hráč je aktívny. Samostatný vypínač na to
nie je. Ktoré tlačidlo sa stlačilo, sa nikam nezapisuje; do lokálneho denníka
ide len názov ovládača, keď sa pripojí.

Overiť sa to dá: `pynput` nie je v `requirements.txt` ani v `.spec` súboroch
a appka ho nikde neimportuje. Keby sa import vrátil do `app.py`, spadnú
testy (`tests/test_hotkey.py`, `tests/test_slot_selection.py`) aj
`check_before_run.py`.

## Prečo nie `WDA_EXCLUDEFROMCAPTURE`

`SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)` by spôsobil, že
overlay nie je vidieť na screenshotoch ani v OBS. Znie to ako slušnosť voči
streamerom, ale je to **presne to správanie, podľa ktorého sa hľadajú
podvodné prekrytia** — ESP/wallhacky sa skrývajú rovnakým volaním.

Obrázky appky majú byť na každom zázname a screenshote vidno. To je ich
najlepšia obhajoba: čokoľvek, čo appka kreslí, vie hráč komukoľvek ukázať.

## Čo appka robí

Jedno alebo viac okien typu `WS_EX_LAYERED` s týmito štýlmi:

- `WS_EX_TRANSPARENT` — klik prejde naskrz do hry. Počas hry okno vstup
  neukradne. Jediná výnimka je **ukážka obrázka** (tlačidlo **▶ Ukázať**):
  vtedy obrázok kliky berie, aby si ho mohol potiahnuť myšou. Ukážka sa
  skončí zatvorením dialógu alebo spustením sledovania.
- `WS_EX_NOACTIVATE` — okno sa nikdy nestane aktívnym. Hra nestratí focus.
- `WS_EX_TOOLWINDOW` — nie je v Alt+Tab ani na paneli úloh.

Obsah okna sa skladá cez `UpdateLayeredWindow` — ten istý systémový
mechanizmus, aký používajú systémové tooltipy a Windows Ink.

### Úplný zoznam toho, čo sa appka dozvedá zvonku

1. **Obdĺžnik aktívneho okna** (`GetForegroundWindow` + `GetWindowRect`) —
   aby vedela, na ktorom monitore kresliť, a na odhad exkluzívneho
   fullscreenu (viď nižšie).
2. **Názvy bežiacich procesov** (`psutil`) — len pri zapnutom automatickom
   prepínaní profilov (predvolene zapnuté, vypínač je na stránke
   Pripomienky). Každých pár sekúnd ich porovná so zoznamom hier
   v `game_profiles.py` (dnes CS2, Valorant, Apex Legends a Call of Duty).
   Pri zhode prepne na profil tej hry (chýbajúci založí) a sama spustí
   sledovanie; keď hra skončí, sledovanie zastaví, ak ho spustila ona.
   Vypnutý prepínač = zoznam procesov sa nečíta vôbec. Z procesu samotného sa
   nič nečíta.
3. **Milisekundy od posledného vstupu** (`GetLastInputInfo`) — bez toho,
   aby vedela, aký vstup to bol.
4. **Stav gamepadu** (SDL2) — kým appka sleduje, tiež len ako známka
   aktivity. Názov stlačeného tlačidla sa nikam nezapisuje; do lokálneho
   denníka ide len názov ovládača pri pripojení.
5. **Tep zo siete** — appka *prijíma* spojenia na porte 4455 (TCP aj UDP),
   predvolene na všetkých sieťových rozhraniach a bez hesla; sama nikam
   nepripája. Pred cudzími sieťami ju chráni firewall (viď `PRIVACY.md`).
   Z hodiniek chodí približne jedno číslo za sekundu. Naraz má otvorených
   najviac 16 socketov (plný strop odmietne len nové spojenie, príjem beží
   ďalej). Spojenie, ktoré do 10 s nedokončí WebSocket handshake, zavrie; po
   minúte ticha pošle do spojenia ping, a keď nepríde odpoveď ani za ďalšiu
   minútu, spojenie zavrie. Z jednej WebSocket správy prijme najviac 64 kB;
   UDP paket väčší než 4 kB zahodí.
5b. **Kroky a rýchlosť z hodiniek** — ak ich appka na hodinkách posiela
   (prémiová verzia), Zanshin ich prečíta z toho istého spojenia ako tep.
   Slúžia na jedinú vec: **keď sa hýbeš, appka mlčí**. Chôdza dvihne tep
   rovnako ako stres a z tepu sa to rozlíšiť nedá — aj model s 55 príznakmi
   z EKG pri strednej aktivite označil väčšinu chôdze ako stres (Uendes
   a kol., 2026, JMIR: špecificita 0,42). Nikam sa neposielajú a do histórie
   sa neukladajú; prvých pár hodnôt za reláciu ide len do lokálneho denníka
   (`logs/app.log`) na ladenie prahu. Kód: `heart_rate.parse_metrics`,
   `hr_stats.note_metrics`.
6. **Jedna klávesová kombinácia** (`RegisterHotKey`) — „teraz nie": na pol
   hodiny stíši pripomienky a sledovanie nezastaví; druhé stlačenie to
   zruší. Predvolene Ctrl+Alt+Z; inú alebo žiadnu si vyberieš v Nastavenia →
   Všeobecné → „Klávesová skratka“.
6b. **Zoznam rozložení klávesnice** (`GetKeyboardLayoutList`) — len na to,
   aby appka vedela, či by kombinácia na niektorom rozložení nepísala znak
   (AltGr je to isté ako Ctrl+Alt, napr. poľské ż). Pýta sa cez
   `ToUnicodeEx` s vymysleným stavom klávesov: Windows preloží kláves na
   znak a zo skutočnej klávesnice sa nečíta nič.
7. **Poloha kurzora myši** (`GetCursorPos`) — len súradnice bodu, a len na
   to, aby sa zistilo, na ktorom monitore je hráč. Nečíta sa, čo je pod ním,
   ani sa nikam nezapisuje trasa. Kód: `display.monitor_at_cursor`.
8. **Mikrofón** — len kým nahrávaš vlastný hlas pre pripomienku (tlačidlo
   **Nahrať** v karte pripomienky). Nahrávka ostáva lokálne v priečinku
   `audio/`. Inokedy sa mikrofón nepoužíva.
9. **IP adresy tohto PC, jeho sieťové adaptéry a zoznam monitorov** —
   adresy len na zobrazenie pri párovaní hodiniek (čo zadať v telefóne; na
   obrazovke sú skryté, kým neklikneš „Ukázať IP“), názvy, popisy, typy a
   stav (pripojený či nie) adaptérov (`GetAdaptersAddresses`) a adresa, cez
   ktorú by Windows posielal dáta von (UDP socket sa len „pripojí“, nič sa
   neodošle), len na to, aby VPN a virtuálne adaptéry išli až za skutočné a
   mali značku „(VPN/virtuálna)“; adresa Mobilného hotspotu Windowsu má
   namiesto nej značku „(hotspot)“ a varovanie nedostane. Monitory
   s rozlíšením a DPI len na umiestnenie obrázkov. Kód: `netinfo.py`,
   `display.monitors`.

To je celé. Nič z toho neopúšťa počítač.

### Prečo bod 6 nie je návrat hooku

Je to jediné miesto, kde appka vôbec počuje klávesnicu, a stojí za to
povedať presne, ako. `RegisterHotKey` funguje **naopak než hook**: appka
Windowsu vopred ohlási jednu konkrétnu kombináciu a systém jej pošle správu
až vtedy, keď ju niekto stlačí. Žiadny prúd vstupu cez ňu netečie — o
žiadnom inom klávese sa appka nedozvie, ani keby chcela.

| | čo vidí | dá sa ním odpočúvať? |
|---|---|---|
| `WH_KEYBOARD_LL` (zrušené pred prvou verejnou alfou) | **každý** stlačený kláves | áno |
| `RegisterHotKey` | len ohlásenú kombináciu | nie |

Keď je kombinácia obsadená inou aplikáciou, registrácia jednoducho zlyhá a
appka beží ďalej bez nej (od 0.2.2 to povie aj riadok v nastaveniach). Admin
práva to nepotrebuje. Od 0.2.2 sa skratka vyberá alebo vypína v Nastavenia →
Všeobecné → „Klávesová skratka“ (voľba „Vypnutá“); v 0.2.1 sa dala vypnúť len
prázdnym `"snooze_hotkey"` v súbore `dandurf_settings.json`. „Teraz nie“ je od
0.2.1 aj v ponuke ikony v lište (pravý klik), takže ide aj bez skratky.

Kód je v `hotkey.py` a `tests/test_hotkey.py` stráži aj to, že sa v ňom
neobjaví `SetWindowsHookEx`, `WH_KEYBOARD`, `GetAsyncKeyState` ani
`GetKeyboardState`.

## Exkluzívny fullscreen

V ňom Windows cudzie vrstvené okná nevykreslí vôbec. Nie je to obrana
anti-cheatu, je to vlastnosť systému. Appka sa ho pokúsi rozpoznať
(`display.is_fullscreen_foreground`): keď okno v popredí zaberá presne celý
monitor, raz za spustenie appky zapíše do denníka radu prepnúť hru na
„Bez okrajov / Borderless", ak obrázky nevidíš. Je to len odhad — rovnako
veľké je aj okno bez okrajov, takže istotu to nedáva.

## Pravidlo pri ďalšom vývoji

Ak sa niekedy objaví požiadavka typu „zobraz v overlayi niečo z hry" —
životy, muníciu, čas do konca kola — odpoveď je nie. V tom momente by appka
musela čítať hru a všetko vyššie by prestalo platiť. Všetko, čo overlay
ukazuje, musí pochádzať **z tela hráča**.
