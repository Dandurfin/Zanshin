<!-- Vznikla 19. 9. 2026 z prieskumu (5 oblasti, 8 adversarialne overenych
tvrdeni o cistote a podmienkach). NIE JE to hotove rozhodnutie - je to
podklad. Kazde tvrdenie je oznacene OVERENE / PRAVDEPODOBNE / NEOVERENE a
sekcia 8 vymenuva, co sa overit nepodarilo.

ZAVER V JEDNEJ VETE: cesta cez Overwolf NIE JE cista - nie technicky, nie
licencne a nie voci podmienkam. Cista cesta zacina inde; Overwolf je
najsirsi, ale opt-in a s priznanim rizika. Viz sekcia 6 a 7. -->

# SPECIFIKACIA: Zanshin DojoSync — most hernych udalosti (Bridge Spec v1.0-draft)

Datum: 19. 9. 2026. Vsetko v tomto dokumente je oznacene ako OVERENE / PRAVDEPODOBNE / NEOVERENE.
Co som overil sam dnes, je oznacene "overene dnes" vratane prikazu/endpointu.

---

## 0. ZAKLADNE ROZHODNUTIE (meni zadanie)

Most NIE JE "Overwolf appka". Most je **protokol na porte 4456 plus mnozina adapterov**.
Overwolf je iba jeden adapter — ten najsirsi, ale zaroven jediny, pri ktorom existuje realna seda zona.

Dovod: poziadavky (a) najsirsie publikum a (b) uplna cistota su v priamom konflikte, ak je Overwolf jediny zdroj. Rozdelenim na adaptery sa konflikt rusi — cista zakladna cesta funguje pre 100 % hier, Overwolf je opt-in rozsirenie.

| Adapter | Pokrytie | Cistota | Default |
|---|---|---|---|
| A0 `manual` | vsetky hry, vsetky platformy | uplne cista, ziadny kontakt s hrou | ZAPNUTY |
| A1 `valve-gsi` | CS2, Dota 2 | oficialne API Valve, konfig si nasadzuje uzivatel | opt-in |
| A2 `riot-lcd` | League of Legends | oficialne Riot Live Client Data API | opt-in, vyzaduje schvalenie Riotom |
| A3 `overwolf-gep` | 74 hier | seda zona, viz sekcia 6 | opt-in, s disclosure obrazovkou |

Jadro DojoSync nevie, ktory adapter bezi. Vie to len z `capabilities` spravy.

---

## 1. CO MOST ROBI A CO ZAMERNE NEROBI

### Robi
1. Nadviaze spojenie na `127.0.0.1:4456` (WebSocket alebo surovy TCP, oboje uz prijimac vie).
2. Hned po pripojeni posle `hello` a `capabilities` — teda **povie pravdu o tom, co v tejto hre realne vie dodat**, este predtym, nez cokolvek posle.
3. Posiela typovane JSON udalosti — vyhradne casove branky a diskretne herne momenty.
4. Ked zdroj zlyha alebo degraduje, posle `degraded` / `bridge_error`. Nikdy nemlci.

### Zamerne nerobi (tvrde zakazy, patria do code review checklistu)
- Nekresli **nic** do hry. Ziadny in-game overlay, ziadne Overwolf overlay okno, ziadny transparentny window nad hrou.
- Necita pamat ziadneho cudzieho procesu. Ziadne `ReadProcessMemory`, `OpenProcess`, `CreateRemoteThread`.
- Neinjektuje. Nehookuje. Nenacitava sa do procesu hry.
- Nemodifikuje subory hry. Jedina vynimka je A1, kde **uzivatel sam** vlozi Valve GSI konfig (viz 8.3).
- Nenahrava obrazovku, nezapina `overwolf.media.replays`, nesaha na video. Auto-highlights su vo v1 **uplne vylucene** (odovodnenie v 6.4).
- Neposiela nic mimo `127.0.0.1` okrem jedineho HTTPS GET na Overwolf status endpoint (len adapter A3).
- Neposiela do jadra ziadne PII: ziadny `steam_id`, `player_name`, `battle_tag`, `account_id`, `match_id`, `media_path`, `media_url`. Filtruje sa **allow-listom**, nie blacklistom.
- Neposkytuje ziadnu informaciu, ktoru hrac v danom momente uz nema na obrazovke. Ziadne odvodzovanie polohy supera, ziadne agregovanie do "live stats".

---

## 2. AKE HRY A CO Z NICH VIEME DOSTAT

### 2.1 Tiery (formalna cast protokolu)

| Tier | Co adapter garantuje | Co z toho ma jadro | Pocet hier (A3) |
|---|---|---|---|
| T0 | `scene`, `match_start`, `match_end` | casova branka "teraz je prirodzena pauza" | ~69 / 74 |
| T1 | T0 + `death` alebo `elimination` | detekcia vrcholu zatazenia | ~23 |
| T2 | T1 + `kill` aj `death` | presnejsi kontext spicky | ~18 |
| T3 | T2 + ciselne skore | napatie zapasu (12:12) | 7 |

**Toto je jadro navrhu:** zataz sa pocita z TEPU, ktory mame nezavisle od hry. Herne udalosti su len branka na dorucenie. Preto je appka pouzitelna v T0 — teda prakticky vo vsetkych hrach — a `kill`/`death` su cisto vylepsenie presnosti, nie podmienka funkcnosti.

### 2.2 Tabulka referencnych hier

Stlpec "keys" je **overene dnes** priamym fetchom `https://game-events-status.overwolf.com/<id>_prod.json`.
Stlpec `is_vgep` je pole z toho isteho feedu (viz varovanie 2.3).

| gameId | Hra | Adapter | Realne dostupne (keys z feedu) | Tier | is_vgep | Istota |
|---|---|---|---|---|---|---|
| 22730 | Counter-Strike 2 | A1 alebo A3 | kill, death, assist, kill_feed, round_start/end, match_start/end, score, round_number | T3 | false | overene dnes |
| 7314 | Dota 2 | A1 alebo A3 | kill, death, assist, clock_time_changed, match_state_changed, game_state | T2/T3 | false | overene dnes |
| 5426 | League of Legends | A2 alebo A3 | kill(+double/triple/quadra/penta), death, assist, respawn, match_clock, live_client_data | T2 | false | overene dnes |
| 21640 | Valorant | A3 | kill, death, assist, headshot, score, match_score, round_number, round_phase, scoreboard | T3 | false | overene dnes |
| 21566 | Apex Legends | A3 | kill, knockdown, death, knocked_out, respawn, match_start/end, phase | T2 | false | overene dnes |
| 21216 | Fortnite | A3 | kill, knockout, death, killed, killer, revived, matchStart/matchEnd | T2 | false | overene dnes |
| 10906 | PUBG | A3 | kill, headshot, death, knockedout, revived, matchStart/End, phase | T2 | false | overene dnes |
| 10844 | Overwatch 2 | A3 | elimination, death, assist, kill_feed, match/round start-end | T2 | false | overene dnes |
| 24890 | Marvel Rivals | A3 | kill, death, assist, kill_feed, round_start/end, match_outcome | T2 | false | overene dnes |
| 10826 | Rainbow Six Siege | A3 | kill, death, headshot, knockedout, roundStart/End, score | T3 | false | overene dnes; **state=2 (yellow)** |
| 10798 | Rocket League | A3 | goal, teamGoal, opposingTeamGoal, team1_score/team2_score, death (demolicia) | T3 | false | overene dnes |
| 24482 | Deadlock | A3 | kill, death, assist, match_clock, team_score, tower_destroyed | T3 | false | overene dnes |
| 26462 | Battlefield 6 | A3 | elimination, knockdown, round_outcome, match_start/end, scene | T1 | false | overene dnes |
| 23478 | The Finals | A3 | death, elimination, match_start/end, scene | T1 | **true** | overene dnes |
| 24000 | Helldivers 2 | A3 | death, match_start/end, scene | T1 | **true** | overene dnes |
| 27168 | ARC Raiders | A3 | death, extraction, match_start/end, scene | T1 | **true** | overene dnes |
| 21634 | Escape from Tarkov | A3 | death, match_start/end, phase, raid_type | T1 | false | overene dnes |
| 22894 | Street Fighter 6 | A3 | round_start, round_end, match_start/end, match_outcome, scene | T0+ | **true** | overene dnes |
| 25448 | R.E.P.O | A3 | death, round_start/end, match_outcome, scene | T1 | **true** | overene dnes |
| 27860 | Call of Duty (BO6/BO7/MW3/WZ) | A3 | **len** mode, scene, match_start, match_end | T0 | **true** | overene dnes |

Feed dnes: **74 hier**, state 1 = 67, state 2 = 2, state 0 = 5, `disabled=true` = 0. (overene dnes)

### 2.3 DOLEZITA OPRAVA PROTI PRIESKUMU

Prieskum tvrdil: "feature zoznam v statusovom feede sa neda pouzit na klasifikaciu, kill/death su skryte v match_info."
**To plati len pre `features[].name`. Neplati pre `features[].keys[].name`.**
Overil som dnes: Deadlock `keys` obsahuje `kill, death, assist, team_score`; CS2 `keys` obsahuje `kill, death, round_start`; Marvel Rivals `keys` obsahuje `kill, death, kill_feed`. Klasifikacia do tierov sa teda **da robit plne za behu z feedu**, bez rucneho citania doc stranok a bez zoznamu hier v kode. To je priama odpoved na bod 4 zadania.

Nikdy nepiseme "podporujeme Call of Duty". Pisme konkretny gameId a titul: 27860 dava len zaciatok/koniec zapasu, 21876 (Vanguard) ma kill+death. Jedna znacka, dve uplne odlisne urovne.

---

## 3. NAPOJENIE NA OVERWOLF API (adapter A3)

Most je **background controller bez UI**. Ziadne okno, ziadny overlay.

Manifest (`manifest.json`):
```
"launch_events": [{ "event": "AllGamesLaunch", "start_minimized": true }]
"data.game_targeting": { "type": "none" }
"data.game_events": [ ...vygenerovany zoznam ID... ]
"permissions": [ "GameInfo" ]        // NIE VideoCaptureSettings
```
- `AllGamesLaunch` nepotrebuje `game_ids` — overene (Overwolf manifest reference).
- `game_targeting: none`, lebo nekreslime overlay. Toto je zaroven hlavny compliance argument.
- `game_events` **nepodporuje wildcard** — pole ID sa generuje pri builde z `gamestatus_prod.json`, nie rucne (viz 7.3).

Poradie volani po starte hry (bez zbytocneho cakania — dokumentacia hovori, ze cim neskor sa GEP registruje, tym vyssia sanca na chybajuce udalosti):

```
1. overwolf.games.onGameInfoUpdated / getRunningGameInfo2
   -> classId = Math.floor(gameInfo.id / 10)        // povinne, inak zle URL
2. GET https://game-events-status.overwolf.com/<classId>_prod.json   (TTL cache, viz 4)
   -> features[].name        = kandidati pre setRequiredFeatures
   -> features[].keys[].name = ocakavane udalosti -> tier
3. setRequiredFeatures(features, cb) s oficialnym retry vzorom (nizsie)
4. supportedFeatures z odpovede = JEDINA pravda -> prepocitaj tier
5. posli hello + capabilities do 4456
6. registruj onNewEvents / onInfoUpdates2 / onError
7. (volitelne) getInfo() pre pociatocny stav
8. onGameInfoUpdated: isRunning=false -> posli bye, odhlas handlery
```

Retry vzor — **doslovne z dokumentacie, nic vlastne**:
```js
while (tries <= MAX_RETRIES) {
  const result = await new Promise(r => overwolf.games.events.setRequiredFeatures(FEATURES, r));
  if (result.success === true) return result.supportedFeatures.length > 0;
  await new Promise(r => setTimeout(r, 3000));
  tries++;
}
console.warn("setRequiredFeatures failed");
```
Nase jedine doplnenie: `success === true` a zaroven `supportedFeatures.length === 0` nie je chyba — je to stav "hra bezi, GEP pre nu nic nedava". Posiela sa ako `degraded`, nie ako ticho.

---

## 4. RUNTIME DETEKCIA SCHOPNOSTI (ziadny zoznam hier v kode)

Tri zdroje, presne definovana priorita:

| # | Zdroj | Co dava | Kedy vyhrava |
|---|---|---|---|
| 1 | `<classId>_prod.json` | ocakavane features, keys, `state` (health) | len ako predikcia a health |
| 2 | `setRequiredFeatures` -> `supportedFeatures` | co sa realne zaregistrovalo | **vzdy vyhrava nad 1** |
| 3 | prve prijate udalosti | co realne tecie | vyhrava nad 2 pri `degraded` timeoute |

Cache: per-classId, TTL 6 hodin (feed sa podla dokumentacie aktualizuje s oneskorenim ~10 min — kratsie TTL nema zmysel). Pri offline/HTTP chybe sa pouzije posledna ulozena kopia a do `capabilities` ide `"health":"unknown","stale":true`. Ked cache nie je, pokracuje sa bez nej — feed nikdy neblokuje start.

`state` (0 unsupported, 1 green, 2 yellow, 3 red — mapovanie PRAVDEPODOBNE, nie je v dokumentacii ako tabulka): `state > 0` znamena "skus to". Feature sa **nikdy** neodmietne len na zaklade tohto cisla.

Watchdog: ak je tier >= T1 a do 180 s od `match_start` nepride ziadna udalost, posli `degraded` s `reason:"no_events_after_match_start"`. Toto chyta presne Dotu bez `-gamestateintegration` a CS2 pod beziacim FACEIT AC.

Zoznam hier existuje **len ako build artefakt** v manifeste. V kode nie je ani jeden gameId natvrdo.

---

## 5. PROTOKOL SMEROM K ZANSHINU

Transport: WebSocket alebo newline-delimited JSON cez TCP na `127.0.0.1:4456`. Bind vyhradne na loopback.
Spatna kompatibilita: existujuce spravy (`{"type":"kill"}`, `{"type":"round_end","score":13,"score_opponent":9}`) zostavaju platne. Nove polia su aditivne.

Spolocne polia kazdej spravy: `type`, `ts` (ms, monotonny), `src` (napr. `"overwolf-gep"`, `"valve-gsi"`, `"manual"`), `seq`.

```json
{"type":"hello","protocol":1,"src":"overwolf-gep","adapter_version":"1.0.0"}

{"type":"capabilities","game_id":27860,"game":"Call of Duty","tier":"T0",
 "health":"green","stale":false,
 "has":["match_start","match_end","game_info"],
 "mechanism":"unknown","mechanism_note":"is_vgep=true vo feede, ale viz 6.3",
 "requires_user_setup":false}

{"type":"game_info","feature":"game_info","info":{"scene":"in_game","mode":"bo6"}}
{"type":"match_start"}
{"type":"round_end","score":13,"score_opponent":9}
{"type":"kill"} {"type":"death"} {"type":"elimination"} {"type":"knockdown"}
{"type":"degraded","reason":"no_events_after_match_start","tier_now":"T0"}
{"type":"bridge_error","reason":"<retazec z onError>"}
{"type":"bye","reason":"game_exited"}
```

### Mapovanie Overwolf -> nase
| Overwolf | Nase |
|---|---|
| `onNewEvents` -> `events[].name` | `type` |
| `onNewEvents` -> `events[].data` | **JE TO STRING**. Povinne `JSON.parse`. Vysledok ide pod `raw`, a len allow-listovane kluce (`score`, `score_opponent`, `round_number`, `count`) sa dvihnu na top level. Nikdy sa nespreaduje cely objekt — prepisal by `type`. |
| `onInfoUpdates2(e)` | `{"type":"game_info","feature":e.feature,"info":e.info}` po allow-liste |
| `onError(e)` | `{"type":"bridge_error","reason":e.reason}` |

Normalizacny slovnik (rovnaky pre vsetky adaptery): `elimination` a `knockout` sa **neprepisuju** na `kill` — su to ine veci a prepis by bol klamstvo v datach. Jadro si ich mapuje samo podla tieru.

Odporucanie: `capabilities` posielat aj pri kazdej zmene (nova hra, degradacia, obnovenie). Jadro ma mat stavovy automat riadeny poslednou `capabilities`, nie predpokladom.

Autentifikacia: v1 sa pri starte posiela `token` z lokalneho suboru, ktory zapisuje jadro (chmod/ACL na uzivatela). Bez neho moze na port poslat udalost hocijaky lokalny proces. NEOVERENE, ci to prijimac dnes vie — treba doplnit.

---

## 6. CISTOTA

### 6.1 Co v README moze byt doslova (dolozitelne)
- "Zanshin DojoSync nepristupuje k hre nijako. Necita pamat, neinjektuje, nehookuje, nekresli do hry. Otvori lokalny socket a caka."
- "Instalaciou DojoSync nepribudne na stroji ziadny kernel driver." (Overwolf nema `.sys` — overene lokalne.)
- "Somaticka pripomienka sa doruci v prirodzenej pauze — medzi kolami, po zapase, v lobby." Zhoduje sa s oficialnym compliance pravidlom Overwolfu pre overlaye.

### 6.2 Co v README NESMIE byt
- "Ziadny injection" bez upresnenia. Overwolf klient **ma** injekcny subsystem (EasyHook.dll 216120 B; log "Injection system ON - Games injection only"; `ProcessInjector` slucka; 4072 z 11178 zaznamov `InjectionDecision=Supported`). Povinna formulacia: *"Zanshin neinjektuje nic. Volitelny Overwolf most vyzaduje Overwolf klienta, ktory pre podporovane hry injektuje vlastne DLL do procesu hry. To je vlastnost Overwolfu, nie nasho kodu, a uzivatel sa pre nu rozhoduje instalaciou Overwolfu."*
- "Activision to schvalil." Activision nema verejny allow-list; jeho politika zakazuje "any code and/or software not authorized by Activision". Maximum: "Overwolf uvadza, ze spolupracuje s vydavatelmi. Activision nezverejnuje zoznam povolenych aplikacii. Pouzivate na vlastne riziko."
- "Overwolf je na whiteliste Riotu." Riot Vanguard FAQ: *"There is absolutely no allow list for Vanguard."*
- "113M pouzivatelov" bez vysvetlenia. Je to cely ekosystem vratane CurseForge (mody pre Minecraft a Sims). Nas realny dosah je podmnozina hracov tier T2/T3 titulov.
- Citovanie Overwolf support clanku "Overwolf Won't Get You Banned" ako dokazu. Je to vendor marketing.

### 6.3 Priznana seda zona: mechanizmus sa **neda spolahlivo zistit za behu**
Prieskum tvrdil, ze CoD a The Finals su "ciste computer vision, najcistejsi mechanizmus". To ako argument neobstoji a dokument to musi povedat otvorene:
- Feed ma pole `is_vgep`. Dnes je `true` pre 19 zo 74 hier. **Ale lokalne goop configy existuju pre 20 hier a mnoziny sa nezhoduju**: Valorant (21640) a Battlefield 6 (26462) maju lokalny goop config, a vo feede maju `is_vgep=false`; naopak CoD Vanguard (21876) a Roblox Rivals (46883) maju `is_vgep=true` bez lokalneho configu. (overene dnes — porovnanie feedu a adresara `...\312.5.6\goop\`)
- Zaver: `is_vgep=true` je indicia, nie dokaz; `is_vgep=false` nevylucuje vision. Hybrid (nativny plugin + vision detekcie) je PRAVDEPODOBNY, ale nepotvrdeny.
- Aj tam, kde ide o vision, snimky dodava vrstva s `ingame_plugins` (GEPPlugin64.dll) — teda DLL v procese hry. "Vision = ziadny hook" je nespravne spojenie.
- Activision hodnoti **autorizaciu, nie mechanizmus**. Cistota mechanizmu nie je obrana.

Preto sa argument cistoty **nestavia na "GEP je vision-based"**. Stavia sa na mechanizmovo neutralnej zmluve: jadro prijima udalosti z lubovolneho zdroja, most je oddeleny proces a volitelny, a pri kazdej hre sa zobrazi, odkial data pochadzaju a ze mechanizmus urcuje Overwolf a moze sa zmenit.

### 6.4 Auto-highlights: vo v1 NEPOUZIVAME
`replays.turnOn` vyzaduje permission `VideoCaptureSettings` a realne spusta video buffer. Appka, ktora slubuje "nic nenahravame", by potichu nahravala hru. To je presne ta seda zona, ktorej sa vyhybame. Ziska sa tym `kill` v par hrach navyse — nestoji to za to. Ak by sa to niekedy pridalo: default OFF, samostatny suhlas, `getHighlightsFeatures` pred `turnOn`, a **nikdy** neposielat `media_path`/`media_url`.

### 6.5 Per-hra pravidla
- **Call of Duty**: Ricochet monitoruje a hlasi aplikacie, ktore sa pokusaju interagovat s hrou. Compliance zakazuje live stats pocas zapasu aj warm-upu. Pre CoD: ziadny overlay vobec, pripomienka len mimo hry (desktop okno, zvuk, haptika), a v UI explicitne upozornenie "pouzivate na vlastne riziko".
- **Riot hry (Valorant, LoL)**: verejna distribucia vyzaduje prejst Riot 3rd Party Application procesom. Bez neho tieto hry v predvolenom builde nezapinat.
- **Dota 2 (A1/A3)**: vyzaduje, aby si hrac sam pridal launch option `-gamestateintegration`. Stav `requires_user_setup: true` + watchdog z bodu 4.
- **CS2 + FACEIT AC**: Overwolf sam uvadza, ze FACEIT AC mu moze zablokovat pristup ku game events v CS2. Musi to byt v UI ako ocakavany stav, nie ako chyba.
- **Yellow/unsupported**: R6 Siege (10826) a Rematch (26120) su dnes `state=2`. 5 hier je `state=0`. Adapter to hlasi cez `health`.

---

## 7. DISTRIBUCIA A LICENCIA

**7.1 Hranice**
- Jadro Zanshin DojoSync: **GPLv3**, samostatny repozitar, ziadna zavislost na Overwolfe.
- Protokol (tento dokument + JSON schema + testovaci harness): **CC0 alebo Apache-2.0**, aby hocikto mohol napisat vlastny adapter. To je hlavny nastroj pre "najsirsie publikum" — komunita prinesie adaptery, ktore my pisat nemusime.
- Adaptery: samostatne repozitare, samostatne licencie. A3 (Overwolf) **nesmie** byt v GPLv3 repozitari.
- Hranica GPL je dodrzana tym, ze adapter je **samostatny proces** komunikujuci cez zverejneny protokol (arm's length). Pravnu istotu tohto tvrdenia nemame — NEOVERENE, treba konzultaciu.

**7.2 Default instalacia**
Instaluje sa jadro + A0. Ziadny adapter, ktory sa dotyka hry, nie je aktivny bez explicitneho suhlasu na disclosure obrazovke, ktora obsahuje text z 6.2 doslova.

**7.3 Generovanie zoznamu hier**
CI job (tyzdenne): stiahne `gamestatus_prod.json`, vygeneruje `game_events` pole, porovna s manifestom, otvori PR s diffom (+nove hry, -odobrane). Zoznam sa needituje rucne. Kod mosta sa pri novej hre **nemeni**.

**7.4 Realne riziko obchodu**
Overwolf podla vlastnych materialov vyzaduje whitelisting napadu cez App proposal a neschvaluje appky bez Overwolf reklam alebo subscriptions. Pre zadarmo/GPL most bez reklam je to existencne riziko. **Toto treba vyriesit s Overwolf review timom PRED napisanim prveho riadku A3.** Ak sa nevyriesi, A3 ostane unpacked extension pre vyvojarov a produkt stoji na A0/A1/A2 — co je stale pouzitelne a cistejsie.

---

## 8. CO NEVIEME — treba overit pred implementaciou

**8.1 Overwolf / obchod**
1. Ci Overwolf schvali bezreklamnu GPL appku. NEOVERENE, blokujuce pre A3.
2. Ci existuje limit na pocet ID v `game_events` a ci prejde review appka s desiatkami hier. NEOVERENE.
3. Ci `OOPO=True` (44 hier vratane CoD) znamena nulove DLL v procese hry, alebo len rendering mimo procesu. Z verejnej dokumentacie sa to zistit nedalo. NEOVERENE — ovplyvnuje to znenie v README.
4. Ci sa `OWClient.dll` realne injektuje do hry — na tomto stroji to nie je zalogovane, je to odvodenie z nazvu a velkosti. NEOVERENE.
5. Presne ciselne mapovanie `state` (0/1/2/3). PRAVDEPODOBNE, nie je v dokumentacii ako tabulka.
6. Spravanie `getHighlightsFeatures` pre nepodporovanu hru (prazdne pole vs. chyba). NEOVERENE — irelevantne, kym highlights nepouzivame.
7. Ci existuje oficialne `overwolf.*` API na zistenie podporovanych features. Nenasiel sa — argument z absencie, PRAVDEPODOBNE.

**8.2 Mechanizmus a anti-cheat**
8. Ziadne vyjadrenie Activisionu, Embarku, Epic/EAC ani NetEase, ktore by Overwolf alebo tento sposob ziskavania udalosti autorizovalo, sa nenaslo. NEOVERENE a pravdepodobne neexistuje.
9. Ci Ricochet povazuje vision capture za "interakciu s hrou". NEOVERENE. Historicky precedens (oktober 2021, permabany Warzone na Windows 11 u pouzivatelov Overwolfu, ktore neboli plosne vratene) je varovanie, nie dokaz.
10. Rozpor `is_vgep` vs. lokalne goop configy pre Valorant a BF6 (6.3). NEOVERENE, treba to ziskat od Overwolfu pisomne.

**8.3 Adaptery mimo Overwolfu — treba primarny zdroj**
11. Valve Game State Integration (CS2, Dota 2): mechanizmus `gamestate_integration_*.cfg` + HTTP POST na lokalny endpoint je PRAVDEPODOBNE spravny, ale primarny zdroj som nestiahol. **Pred pisanim A1 treba precitat oficialnu Valve dokumentaciu.** Otvorene otazky: presna cesta konfigu, schema payloadu, ci je legitimne, aby konfig zapisala nasa appka, alebo ho ma vlozit uzivatel rucne (bezpecnejsie: uzivatel, s naším navodom).
12. Riot Live Client Data API (`127.0.0.1:2999`): PRAVDEPODOBNE, neoverene primarnym zdrojom. Treba potvrdit endpointy, polling limity a podmienky Riot 3rd Party Application procesu.

**8.4 Pokrytie**
13. Zvysnych ~45 hier tier C bolo klasifikovanych z feedu, nie z doc stranok. Po oprave v 2.3 je klasifikacia z `keys` spolahlivejsia, ale odporucam rucne overit aspon Teamfight Tactics (21570/28164 — dlhe pauzy medzi kolami a velke publikum, potencialne idealny titul), Supervive, Splitgate 2, Space Marine 2, Diablo IV.
14. Oficialna HTML tabulka "GEP Supported Environments" ukazuje 60 hier, feed ma 74. Nikdy nestavat spec ani marketing na tej tabulke.

**8.5 Chyby v podkladoch, ktore som nasiel**
15. V zisteniach je zdroj uvedeny ako `game-essentsstatus.overwolf.com` — je to preklep, spravna domena je `game-events-status.overwolf.com` (overene dnes, HTTP 200).
16. Tretí verdikt (k tvrdeniu o 20 GOOP provideroch) je v podkladoch **utaty uprostred vety** pri The Finals. Zoznamy udalosti odvodene z goop configov preto v tomto dokumente povazujem za NEOVERENE a nepouzivam ich — tabulka v sekcii 2 stoji vyhradne na feede, ktory som overil dnes.
17. Tvrdenie "vsetkych 20 goop configov ma `use_gep_ai:1`" je vyvratene (22328 ma len `fps` a `downscale`). Nepouzivat.

---

## 9. PORADIE PRAC (co sa da zacat pisat zajtra)

1. Protokol v1: JSON schema + referencny prijimac test + fake adapter, ktory prehra nahratu stopu udalosti. Bez toho sa neda testovat nic.
2. A0 `manual` — hotkey + heartbeat. Funguje vsade, nic nerisikuje, da sa s nim otestovat cely produkt.
3. A1 `valve-gsi` — az po precitani primarneho zdroja Valve (8.3.11). Prvy adapter, ktory realne cita hru, a zaroven najcistejsi.
4. Paralelne: napisat Overwolf App proposal a spytat sa na 8.1.1 a 8.1.2. Odpoved urcuje, ci A3 vobec ma zmysel.
5. A3 `overwolf-gep` — az ako posledny, opt-in, s disclosure obrazovkou a textom z 6.2.