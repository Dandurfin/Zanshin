"""Rebrik hlasky - appka sa sama stisi, ked hlaska prekaza (0.2).

    hlas  ->  obrazok  ->  pauza

Kazda relacia bezi na jednom stupni. Urci sa pri jej OTVORENI z ulozenych
relacii toho isteho sveta a uz sa nemeni (ako svet relacie, B3-worlds).

VRCHOL (najhlasnejsi dovoleny stupen) urcuje hrac a svet, nie rebrik:
  * PRACA je len obraz - rozhodnutie zadavatela z B3-worlds. Svet sa tu
    nepocita znova; volajuci posle ten, ktory B3 opecatil pri otvoreni.
  * styl, ktory si hrac vybral (nastavenie `cue_style`; otazka v
    onboardingu, riadok "Ako sa ozyvam" v Nastaveniach -> Zvuk): "visual" =
    len obraz; "sound" = stupen hlasu so stlmenymi slovami (slot zahra svoj
    zvuk a ukaze obrazok, TTS ani vlastna nahravka nezaznie); "voice" alebo
    chybajuci kluc = hlas. Odpoved "neviem" v onboardingu = hlas.
Rebrik ide len POD vrchol, nikdy nad neho.

DOLE, o jeden stupen za relaciu, ked:
  * dotaznik po relacii s hlaskou povie "rusila" alebo "rozhodila ma",
  * alebo hrac do `SNOOZE_PO_HLASKE_S` po dorucenej hlaske stlacil "teraz
    nie" (Ctrl+Alt+Z) - ALE len ked relacia po nom este bezala aspon
    `SNOOZE_POTOM_S` a verdikt tej relacie nie je "sadla". Zadavatel si nie
    je isty, ci tou skratkou nemysli "koncim"; hlasky chodia prave na konci
    kol, kedy sa aj konci. Rata sa to preto len ked sa hralo dalej.
    Od 24. 9. "teraz nie" relaciu NEZATVARA - len stisi hlasky a meria sa
    dalej (`app._start_snooze`), takze `snooze_then_s` je skutocny cas,
    ktory relacia po nom este bezala, a signal sa naozaj moze prejavit.
HORE pomaly: o stupen po `NAVRAT_RELACII` relaciach s hlaskou bez signalu.
Hlaska = DORUCENA (obraz sa naozaj ukazal, viz `_hlasok`); nedorucena sa
nerata ani na navrat, ani ako relacia s hlaskou pri verdikte.
PAUZA trva `PAUZA_RELACII` relacii aspon `PAUZA_MIN_TRVANIE_S` (alebo
skonci verdiktom "ano, mala") a potom sa skusi obrazok.

Zvuk ako samostatny stupen tu zamerne nie je (review stress-cue): kto chce
zvuk bez slov, ma styl "sound" alebo rezim slotu "Zvuk". Ani merane
"hlas je horsi nez obrazok" - na to zatial nie su data.

Cisty modul (ziadny Tk, ziadne I/O), rovnako ako `trigger.py`.
"""

HLAS = "voice"
OBRAZ = "visual"
PAUZA = "pause"
STUPNE = (HLAS, OBRAZ, PAUZA)

# Styl hlasky, ktory si vybral hrac (kluc nastaveni `cue_style`).
STYL_HLAS = "voice"
STYL_ZVUK = "sound"
STYL_OBRAZ = "visual"
STYLY = (STYL_HLAS, STYL_ZVUK, STYL_OBRAZ)

# Retazce z `hr_stats` (svet, verdikty). Nie import: modul ostava samostatny.
SVET_PRACA = "work"
DOLE_VERDIKTY = ("disruptive", "agitated")
VERDIKT_SADLA = "landed"
VERDIKT_MALA = "missed"

SNOOZE_PO_HLASKE_S = 60.0
SNOOZE_POTOM_S = 120.0
NAVRAT_RELACII = 3
PAUZA_RELACII = 3
PAUZA_MIN_TRVANIE_S = 300.0

# Preco je rebrik tam, kde je (`stupen()["dovod"]`).
D_RUSILA = "disruptive"
D_ROZHODILA = "agitated"
D_SNOOZE = "snooze"
D_NAVRAT = "climb"
D_ZNOVA = "retry"
D_MALA = "missed"
# Tieto mozu stat pod vrcholom (a maju vetu v Historii). `climb` nie: s
# tromi stupnami vedie navrat vzdy az na vrchol.
DOVODY_POD_VRCHOLOM = (D_RUSILA, D_ROZHODILA, D_SNOOZE, D_ZNOVA, D_MALA)


def normalize_cue_style(raw):
    """Jeden zo `STYLY`; chybajuci alebo nezmyselny styl = hlas."""
    return raw if raw in STYLY else STYL_HLAS


def je_tichsi(novy, stary):
    """Je styl `novy` tichsi nez `stary`? `STYLY` idu od najhlasnejsieho."""
    return (STYLY.index(normalize_cue_style(novy))
            > STYLY.index(normalize_cue_style(stary)))


def vrchol(svet, styl):
    """Najhlasnejsi stupen, na ktory sa rebrik v tomto svete smie dostat."""
    if svet == SVET_PRACA:
        return OBRAZ
    if normalize_cue_style(styl) == STYL_OBRAZ:
        return OBRAZ
    return HLAS


def _cislo(hodnota):
    try:
        return float(hodnota)
    except (TypeError, ValueError):
        return None


def _hlasok(session):
    """Kolko hlasok hrac v relacii naozaj DOSTAL (obraz sa vykreslil).

    RATA SA LEN DORUCENA HLASKA. `auto_triggers` rata aj hlasku, ktorej
    obraz zlyhal (`note_trigger(delivered=False)`) - hrac z nej nic nevidel
    a dotaznik mu povedal "neozvala som sa", takze sa ani nemal ako
    stazovat. Rebrik by taku relaciu ratal ako "s hlaskou a bez vyhrad" a
    stupal k hlasu z ticha. `cues_delivered` (od 0.2.1, `_close_hr_session`)
    ma rovnake pravidlo ako dotaznik a "teraz nie" po hlaske
    (`hr_stats.last_auto_cue_ts`): tiche rameno sa rata - obraz ukazalo.
    Starsie relacie ho nemaju a ostava im `auto_triggers`."""
    pocet = _cislo(session.get("cues_delivered"))
    if pocet is None:
        pocet = _cislo(session.get("auto_triggers"))
    try:
        return max(0, int(pocet or 0))
    except (ValueError, OverflowError):
        # NaN / nekonecno z rucne upraveneho suboru - rebrik nesmie spadnut.
        return 0


def signal_dole(session):
    """Preco sa po tejto relacii ide o stupen nizsie - alebo None.

    Verdikt ma prednost pred snooze: je to priame slovo hraca. Na jednu
    relaciu je vzdy najviac jeden stupen."""
    if not isinstance(session, dict):
        return None
    verdikt = session.get("cue_verdict")
    if _hlasok(session) > 0 and verdikt in DOLE_VERDIKTY:
        return verdikt
    if verdikt == VERDIKT_SADLA:
        # "Sadla" a hned "teraz nie" = skor "koncim" nez "prekazala".
        return None
    po = _cislo(session.get("snooze_after_cue_s"))
    potom = _cislo(session.get("snooze_then_s"))
    if (po is not None and 0.0 <= po <= SNOOZE_PO_HLASKE_S
            and potom is not None and potom >= SNOOZE_POTOM_S):
        return D_SNOOZE
    return None


def stupen(sessions, svet="play", styl=STYL_HLAS):
    """Na akom stupni pobezi dalsia relacia v tomto svete.

    `sessions` su ulozene relacie JEDNEHO sveta (volajuci ich filtruje cez
    `hr_stats.sessions_in_world`). Importovane (cudzie telo) sa nerataju.

    Vracia {"stupen", "vrchol", "dovod", "started", "zostava"}: `dovod` a
    `started` hovoria, ktora relacia rebrik naposledy posunula (alebo
    None), `zostava` kolko relacii chyba do dalsieho pokusu o hlasnejsi
    stupen (0 na vrchole).
    """
    vrch_meno = vrchol(svet, styl)
    vrch = STUPNE.index(vrch_meno)
    obraz, pauza = STUPNE.index(OBRAZ), STUPNE.index(PAUZA)
    rel = sorted((s for s in sessions or ()
                  if isinstance(s, dict) and not s.get("imported")),
                 key=lambda s: _cislo(s.get("started")) or 0.0)

    st = vrch
    # ZACIATOK Z PECIATKY NAJSTARSEJ DRZANEJ RELACIE. Historia sa po
    # `hr_stats.MAX_SESSIONS` orezava - bez toho by odchod starych zaznamov
    # potichu vratil hlas. Peciatka plati, len ked bola pod VLASTNYM
    # vrcholom: kto mal styl "obraz" a prepol na hlas, nema ostat na obraze.
    if rel and rel[0].get("cue_rung") in STUPNE:
        jej = STUPNE.index(rel[0]["cue_rung"])
        if jej > STUPNE.index(vrchol(svet, rel[0].get("cue_style"))):
            st = max(vrch, jej)

    ciste = 0
    v_pauze = 0
    dovod, kedy = None, None
    for s in rel:
        zacala = s.get("started")
        if st == pauza:
            if (_cislo(s.get("duration_s")) or 0.0) >= PAUZA_MIN_TRVANIE_S:
                v_pauze += 1
            if s.get("cue_verdict") == VERDIKT_MALA:
                st, v_pauze, ciste = obraz, 0, 0
                dovod, kedy = D_MALA, zacala
            elif v_pauze >= PAUZA_RELACII:
                st, v_pauze, ciste = obraz, 0, 0
                dovod, kedy = D_ZNOVA, zacala
            continue
        dole = signal_dole(s)
        if dole:
            st = min(pauza, st + 1)
            ciste = 0
            dovod, kedy = dole, zacala
        elif _hlasok(s) > 0:
            ciste += 1
            if ciste >= NAVRAT_RELACII and st > vrch:
                st, ciste = st - 1, 0
                dovod, kedy = D_NAVRAT, zacala
        # Nikdy nad vrchol (styl sa mohol medzitym stisit).
        st = max(st, vrch)

    if st == pauza:
        zostava = PAUZA_RELACII - v_pauze
    elif st > vrch:
        zostava = NAVRAT_RELACII - ciste
    else:
        zostava = 0
    return {"stupen": STUPNE[st], "vrchol": vrch_meno, "dovod": dovod,
            "started": kedy, "zostava": zostava}
