# Ako tento strom vznikol a co mu treba verit

**Zdrojak 2.0 na disku neexistoval.** `<lokalny priecinok>`,
na ktory ukazuje `docs/PROJECT.md` aj `README.md` zbuildovaneho depotu, bol
zmazany a Kos je prazdny. Tento strom je obnova - nie kopia.

## Co bolo k dispozicii

| Zdroj | Co v nom je |
|---|---|
| `ZanshinDojoSync.exe` (depot 2.0) | vsetkych 30 modulov appky ako Python 3.14 bytecode |
| `<lokalny priecinok>\file-history` | snapshoty suborov z tej noci, ked 2.0 vznikala |
| `<lokalna zaloha>.zip` | stav stromu k 13.9. 18:52 (vychodisko tej noci) |
| transkripty sedeni v `<lokalny priecinok>` | presne znenie uprav, ktore sa do file-history nedostali |

## Ako sa overovalo

Depot je jediny bod, o ktory sa da opriet - je to to, co realne bezi. Pre kazdy
modul sa preto vyskusali **vsetky** ulozene verzie a vybrala sa ta, ktora sa
tymto Pythonom skompiluje na **rovnaky bytecode**, ako je v `.exe`:
rovnake instrukcie, rovnake konstanty, rovnake mena.

Bez toho by sa nedalo rozlisit spravnu verziu od nespravnej. Niektore snapshoty
v file-history su totiz NOVSIE nez build - pochadzaju zo sedeni, ktore bezali az
po tom, co depot vznikol, a obsahuju zmeny, ktore sa do 2.0 nikdy nedostali.
Napriklad `settings_model.default_slots` mal v najnovsom snapshote auto SFX a
cooldown 12 s, kym v depote su explicitne Zen zvuky a ciste casovanie.

**Vysledok: 30/30 modulov sa bytovo zhoduje s depotom.**
Overit sa to da kedykolvek znova - `verify_tree.py` v scratchpade.

Co sa timto NEoveruje: komentare, formatovanie a prazdne riadky. Tie v bytecode
nie su. Docstringy ano - tie su sucastou konstant, takze sedia.

## Co sa muselo doplnit rucne

Styri veci neboli v ziadnej zalohe a boli odvodene z depotu:

| Kde | Co | Odkial sa to vie |
|---|---|---|
| `app.py` | `"voice_id": ""` (nie natvrdo zapisany SAPI token Zira) | konstanta v `.pyc` |
| `app.py` | `"strict_global_lock": False`, `"hr_critical_bpm": 110`, `"hr_monitoring_enabled": False` | instrukcie v `.pyc` |
| `i18n.py` | `_win_locale()` + `system_lang()` | presne znenie z transkriptu, overene proti bytecode |
| `theme_recolor.py` | modulovy docstring (novsie znenie) | konstanta v `.pyc` |

Plus verzia 1.0 -> 2.0 na styroch miestach. Tri z nich boli v zalohe este
stare; ze maju byt 2.0, potvrdzuje zbuildovany `.exe`
(`FileVersion = 2.0.0.0`) a `steam\app_build.vdf` v depote.

## Co sa NEPODARILO obnovit

**`tests/test_version_sync.py`.** Nie je v ziadnej zalohe ani v transkriptoch.
Je napisany **nanovo** podla popisu v `docs/PROJECT.md` §12 - kontroluje, ze
verzia sedi na vsetkych styroch miestach. Povodny test mal podla dokumentacie
viac pripadov: `PROJECT.md` hovori o 194 testoch, tento strom ich ma 190.
Tie styri chybajuce su v tomto subore.

Ak sa niekedy najde povodna verzia, tuto prepis.

## Stav

```
python -m pytest tests -q     190 passed
python check_before_run.py    vsetky strukturalne kontroly presli,
                              vratane vsetkych devatich prekladov
```

`gui_screenshots.py` (12 vykreslovacich kontrol) zatial spusteny nebol -
potrebuje realne okno.

## Povod jednotlivych suborov

- **30 modulov appky** - overene proti depotu, bytova zhoda
- **testy a dev nastroje** - najnovsia verzia z file-history
- **assety, zvuky, instalator, prekladove CSV** - snapshot z 13.9. 18:52

Jediny subor v strome, ktory nikdy neexistoval v tejto podobe, je
`tests/test_version_sync.py` a tento subor.
