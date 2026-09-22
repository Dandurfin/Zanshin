# Zanshin DojoSync na Steame — čo treba prehodnotiť

> **Stav od 13. 9. 2026:** `uac_admin=False` v `Dandurf.spec` a
> `PrivilegesRequired=lowest` v `Dandurf.iss` sú **hotové**. Inštalátor ide do
> `%LOCALAPPDATA%\Programs\Zanshin DojoSync` bez UAC (tým zmizol aj „Error
> 707" z live testu) a appka beží bez elevácie — klávesové hooky aj overlay
> overené naživo (`gui_harness_auto.py`). Text nižšie ostáva ako zdôvodnenie.
> **Nikdy to nevracaj na admin** — kvôli Valorantu (Vanguard).
>
> **Redizajn „Sumi noc" (13. 9. 2026, viď interné poznámky):**
> čisto vizuálny/UI redizajn (paleta, sidebar, enso, vybrateľné štatistiky,
> obdobia v Historii) — `Dandurf.spec`/`Dandurf.iss` sa nedotkol,
> `uac_admin=False` overené naživo nezmenené po redizajne.
> *(Dojo pozadie, ktoré redizajn priniesol, bolo 14. 9. 2026 odstránené —
> viď interné poznámky.)*

Pôvodný build (`Dandurf.spec` + `Dandurf.iss`) bol stavaný na **samostatný
inštalátor mimo Steamu** — inštaloval do Program Files a pýtal si
administrátorské práva (UAC). Pre Steam to nefunguje a tu je prečo.

## Prečo admin/UAC na Steame nejde

Steam sťahuje hry do svojej vlastnej knižnice
(`SteamLibrary\steamapps\common\...`), nie do Program Files. Tú zložku
Steam vytvára a spravuje sám, bez UAC. Ak by `.exe` pri každom spustení
vyžadoval administrátorské práva:

- **hráč dostane UAC výzvu pri každom spustení hry** — nič, na čo je na
  Steame zvyknutý, a väčšina to vyhodnotí ako podozrivé;
- **Steam Overlay a sledovanie času hrania sa rozbijú** — Steam injektuje
  overlay do procesu hry a k elevovanému procesu sa nedostane, keď sám
  beží bez elevácie;
- **cloud-save a automatické aktualizácie** cez Steam sa komplikujú,
  pretože Steam nemá prístup zapisovať do elevovaného procesu.

## Pôvodný dôvod pre admin — a či ešte platí

`Dandurf.spec` píše, že `uac_admin=True` je preto, aby Smart App Control
nepovažoval globálne klávesové hooky za podozrivé. Lenže:

1. **Globálne hooky admin práva nepotrebovali.** `WH_KEYBOARD_LL` fungoval
   aj v bežnom používateľskom procese. Admin bol poistka, nie nutnosť.

   > **Od verzie 2.1 je to bezpredmetné:** fáza 3 klávesový hook úplne
   > zrušila a `pynput` nie je ani v závislostiach, ani v builde
   > (`check_before_run.py` build zastaví, keby sa vrátil). Hlášku spúšťa
   > telo. Dôvod pre admin tým odpadol dvakrát.
2. **Reputáciu admin práva aj tak neriešia.** Elevácia nerobí `.exe`
   dôveryhodnejším — o tom rozhoduje podpis a reputácia, nie práva. Dôvod
   pre admin tým odpadá.

   > **OPRAVA (13. 9. 2026):** Tu pôvodne stálo, že „hru podpisuje a
   > distribuuje Steam" a že Smart App Control ju preto nevidí ako
   > nepodpísaný súbor. **To nie je pravda a je to nebezpečný predpoklad** —
   > Valve cudzie buildy **nepodpisuje**, depot doručí presne tie bajty,
   > ktoré doňho nahráš. Viď „Smart App Control" nižšie.

**Záver: pre Steam build zmeň `uac_admin=True` na `False` v `Dandurf.spec`.**
Je to jednoriadková zmena. Otestuj, že appka po nej stále hookuje vstup a
kreslí overlay (mala by — viď bod 1).

## Čo Steam build vôbec nepotrebuje

- **Inno Setup inštalátor** (`Dandurf.iss`) — Steam si inštaláciu rieši
  sám cez depoty. `.iss` si nechaj len pre prípadnú distribúciu mimo
  Steamu (web, itch.io).
- **Zápis do Program Files** — appka aj tak píše používateľské dáta do
  `%APPDATA%\Zanshin DojoSync` (viď `paths.py`), takže z knižnice Steamu
  jej nič nechýba. `getattr(sys, "frozen")` vetva v `paths.py` funguje
  rovnako bez ohľadu na to, kde `.exe` sedí.

## Čo Steam build potrebuje navyše

1. **`steam_appid.txt`** vedľa `.exe` počas vývoja (číslo dostaneš po
   založení appky v Steamworks). Do finálneho depotu nepatrí.
2. **Steamworks SDK**, ak chceš Steam featury — ale pre túto appku
   pravdepodobne stačí „nespotrebné" vydanie bez SDK: žiadne achievementy,
   žiadny multiplayer, len sa to spustí. Rozhodni podľa toho, či chceš
   herný čas a achievementy, alebo len distribúciu.
3. **Rozmyslieť kategóriu.** Zanshin nie je hra — je to nástroj, ktorý
   beží popri hre. Na Steame patrí skôr do **Software**, nie Games, alebo
   ako **Application**. Over v Steamworks, či ti to schvália ako softvér;
   overlay-nad-hrou appky sú v šedej zóne a Valve sa na ne pýta.

## Anti-cheat na Steame — dôležité

Toto je jadro. Zanshin kreslí okno nad hrou a hookuje vstup. Na Steame,
kde bežia hry s Ricochet/EAC/BattlEye, to znamená:

- **`SAFETY.md` musí ísť do Steam popisu appky**, nie len do repa. Hráč aj
  Valve musia vedieť, že appka nič neinjektuje a needíta hru.
- **Otestuj s reálnym anti-cheatom zapnutým** predtým, než to vydáš.
  Konkrétne CS2 (VAC), Valorant (Vanguard — najtvrdší, beží na úrovni
  kernelu) a nejakú EAC hru. Ak Vanguard appku toleruje, ostatné skoro
  určite tiež.
- **Elevovaný proces + hooky + overlay je presne profil, ktorý anti-cheaty
  chytajú najprísnejšie.** Vypnutie admin práv (vyššie) teda nie je len
  kvôli Steam UX — je to aj kvôli anti-cheatu. Menej práv = menej dôvodov
  na podozrenie.

  Od verzie 2.1 z tej trojice ostal **len overlay**: hook zrušila fáza 3 a
  admin práva sú vypnuté (`uac_admin=False`, `PrivilegesRequired=lowest`).
  Zostáva teda okno, ktoré sa zámerne neskrýva — viď `SAFETY.md`.

## Smart App Control — build je nepodpísaný a Windows ho blokuje

**Nameraný stav (13. 9. 2026, tento počítač):** Smart App Control je
zapnutý (`HKLM\SYSTEM\CurrentControlSet\Control\CI\Policy` →
`VerifiedAndReputablePolicyState = 1`) a čerstvo postavený
`dist\ZanshinDojoSync\ZanshinDojoSync.exe` **sa nedá spustiť**:

```
OSError: [WinError 4551] An Application Control policy has blocked this file
```

Nejde o Defender ani o karanténu — súbor na disku zostáva nedotknutý,
Windows mu len odmieta dať bežať. Prvý build tej istej session ešte
nabehol, ďalší už nie: verdikt SAC pre neznámy nepodpísaný súbor nie je
stabilný, takže „u mňa to išlo" nie je dôkaz, že to pôjde u hráča.

**Prečo to Steam nevyrieši za teba:** Valve cudzie buildy nepodpisuje.
Depot doručí presne tie bajty, ktoré doňho nahráš — ak je `.exe`
nepodpísaný, príde k hráčovi nepodpísaný. SAC je na čerstvých
inštaláciách Windows 11 zapnutý predvolene, takže časť hráčov appku
jednoducho nespustí a uvidí len hlásenie od Windowsu.

**Čo s tým (v poradí podľa účinnosti):**

1. **Podpísať `.exe` certifikátom na podpis kódu.** OV certifikát reputáciu
   buduje postupne, EV certifikát má dôveru hneď. Toto je jediné skutočné
   riešenie, zvyšok je obchádzka.
2. **Nechať build „dozrieť".** Reputácia sa časom buduje aj pre nepodpísané
   súbory, ale je to mimo tvojej kontroly a pri každom novom builde
   (= nový hash) začína odznova. Pri častých aktualizáciách nepoužiteľné.
3. **Otestovať na stroji so zapnutým SAC pred vydaním.** Nie na svojom
   vývojovom, kde už môže byť výnimka.

Metadáta `.exe` (`version_info.txt` — názov, autor, popis, verzia) sú
doplnené a pomáhajú dôveryhodnosti, ale **podpis nenahradia**.

## Zhrnutie zmien pre Steam

| Vec | Teraz | Pre Steam |
|---|---|---|
| `uac_admin` v spec | **`False`** (hotové) | **`False`** |
| Inštalátor | Inno Setup, `PrivilegesRequired=lowest` | Steam depoty (`.iss` nechať len pre web) |
| Inštalačná zložka | `%LOCALAPPDATA%\Programs` (bez UAC) | Steam knižnica (rieši Steam) |
| Používateľské dáta | `%APPDATA%` | `%APPDATA%` (bez zmeny) |
| Kategória v obchode | — | Software / Application, nie Games |
| `SAFETY.md` | v repe | + do Steam popisu |
| UPX | `False` (už opravené) | `False` |
| Metadáta `.exe` | `version_info.txt` (hotové) | bez zmeny |
| Podpis `.exe` | **žiadny — SAC build blokuje** | **certifikát na podpis kódu (blokujúce)** |
