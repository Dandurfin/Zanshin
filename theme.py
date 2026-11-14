"""Farebne tokeny pre dva vizualne rezimy.

SUMI (predvolena) - teply atramentovy variant so zlatym akcentom ("Sumi
noc"). Zlato (`accent`/`kin`) je hlavny akcent v celom rozhrani; modra
(`blue`) sa pouziva len na oznacenie pokojnych/nizkych hodnot (napr.
zotavenie tepu), nie ako ozdoba.

AIZOME - indigo variant. Rovnaka architektura, len iny podklad a modry
akcent. Od 0.2 je to vzhlad PRACOVNEHO sveta (viz `WORLD_THEME`). Aj tu
plati, ze cislo v modrej (`blue`) je len zotavenie tepu - pasmo pokoja
(`zone_calm`) preto nie je modre, ale asagi (modrozelena).

STAVOVE FARBY (0.2.2, audit UX). Bodka stavu v bocnom paneli
(`ui_shell._StateDot`) je pri sledovani plna `success`, zastavena je len
duty kruzok v `text_faint` a "teraz nie" ma jantarovy prstenec (`warn`).
Zastavena appka je BEZNY stav, nie poplach - cervena (`danger`) by tam
kricala pri kazdom spusteni PC. `danger` je len pre chybu a pre
destruktivnu akciu (zmazat), nikdy pre "zastavene" ani pre maximum tepu.

PRAVIDLA, ktore z tokenov vyplyvaju (aby ich kazde miesto neriesilo samo):
  * ZAPNUTE a ZVOLENE = `accent` (prepinac, aktivna karta, zvoleny svet).
    `accent2` je len tlmena vypln POD ramom v `accent`, sama nic neznaci -
    zapnuty prepinac v `accent2` mal proti vypnutemu kontrast 1,07:1.
  * Obsahovy text (vysvetlivky, osi, legendy) ma kontrast aspon 4,5:1 na
    `surface`; preto je `text_faint` od 0.2.2 svetlejsi (2,85 -> 4,72 v
    Sumi, 3,01 -> 4,76 v Aizome). Hierarchiu nesie velkost a hrubka, nie
    neviditelnost.
  * Deliace linky (`rule`) maju aspon 1,5:1, inak su to len nevysvetlene
    medzery. Ram panela ostava tichy (`line_soft`) - ram nema kricat.
  * Ram vedlajsieho tlacidla (`control_border`) ma aspon 3:1, inak tlacidlo
    vyzera vypnute. Text destruktivnej akcie (`danger_text`) ma 4,5:1;
    samotny `danger` je na drobny text pritmavy.

POZOR NA KLUCE: `ZEN` a `MODERN` NIE SU nazvy farebnych schem - su to aj
identifikatory SFX sad (`sfx_key` v nastaveniach ma tvar "zen:earth_thud").
Premenovat sa NESMU, inak kazdy existujuci profil stratí svoje zvuky.
Zobrazovane nazvy temy su v i18n (theme.modern.label / theme.zen.label:
Aizome / Sumi).
"""

ZEN = "zen"
MODERN = "modern"
DEFAULT_THEME = ZEN

# DVA SVETY, DVA VZHLADY (0.2, B3-worlds). Tema uz nie je vec vkusu, ale
# znamenie sveta: jeden pohlad na okno povie, ci si v Hre alebo v Praci.
# Kluce sveta su tie iste ako `hr_stats.ACTIVITY_KINDS` - napisane rucne,
# aby tema nemusela importovat hr_stats.
WORLD_THEME = {"play": ZEN, "work": MODERN}


def theme_world(theme_key):
    """Opak `WORLD_THEME`: tema -> svet. Neznama tema patri Hre."""
    for world, key in WORLD_THEME.items():
        if key == theme_key:
            return world
    return "play"

THEMES = {
    # ---- AIZOME (indigo) ----
    MODERN: {
        "font_family": "Segoe UI",
        "bg": "#0D1119",
        "surface": "#121826",
        "surface_alt": "#182033",
        "card": "#121826",
        "card_border": "#212B41",
        "border": "#212B41",
        "line_soft": "#18202F",
        "accent": "#5C86C9",
        "accent_hover": "#8FB0E8",
        "accent2": "#26395F",
        "accent2_hover": "#35507F",
        "text": "#E7EAF2",
        "text_dim": "#8F99B2",
        # 4,76:1 na surface (predtym #5A6480 = 3,01:1 - vysvetlivky pod
        # nastaveniami a osi grafov sa citali s namahou)
        "text_faint": "#7A84A0",
        "success": "#7FB39A",
        "danger": "#C04A3E",
        "danger_text": "#D86A5E",    # text/ram "Zmazat": 5,19:1 na surface
        "warn": "#C9A24D",
        "entry_bg": "#0B0F17",
        "switch_off": "#212B41",
        "rule": "#2C3854",           # deliace linky: 1,52:1 na surface
        "control_border": "#56658A",  # ram vedlajsieho tlacidla: 3,06:1
        # --- prvky noveho rozhrania ---
        "plate": "#101725",          # pokojny stav dychajuceho pasu
        "plate_glow": "#1B2740",     # vrchol nadychu
        # Zastaveny pas bol v Aizome jedina tepla plocha okna (#131013 s
        # hnedym ramom) - vyzeral ako vystrihnuty zo Sumi. Teraz je to
        # tmave indigo, pas "nedycha" tym, ze je tmavsi nez `plate`.
        "plate_idle": "#0F131C",
        "plate_idle_border": "#26324A",
        "keycap_face": "#1C2536",
        "keycap_edge": "#2C374F",
        "keycap_text": "#8FB0E8",
        "washi": "#DCD3C0",          # znacka 残
        # --- stavove/sekundarne farby (dashboard, enso) ---
        "bengara": "#C04A3E",        # POZN: enso uz pouziva success/danger
        "blue": "#5C86C9",           # pokojne/nizke hodnoty (Aizome uz je modra)
        "murasaki": "#9C8FC9",
        # --- pasma tepu (viz poznamka pod THEMES) ---
        # Aizome zacina na STUDENOM konci, horuci koniec ostava horuci -
        # teplo je teplo v kazdej teme. Pokoj je ASAGI (modrozelena, odtien
        # z tej istej indigovej farbiarne), NIE modra: do 0.2.2 bol #6FA5C9 a
        # karta "Pokojovy tep" vedla karty "Zotavenie" (`blue`) boli dve modre
        # - modra pritom patri len zotaveniu (0.2.2 davka 4, audit UX). Ako
        # v Sumi, kde je pokoj matcha: zelenkavy, studenejsi nez zvysok radu.
        # 7,15:1 na surface; od `success` sa lisi odtienom aj sytostou.
        "zone_calm": "#5FB3A3",
        "zone_raised": "#B9A25F",
        "zone_high": "#C97C43",
        "zone_critical": "#C04A3E",
    },
    # ---- SUMI noc (atrament + zlato) ----
    ZEN: {
        "font_family": "Segoe UI",
        "bg": "#0D0E13",
        "surface": "#191A22",
        "surface_alt": "#20222C",
        "card": "#191A22",
        "card_border": "#2A2B36",
        "border": "#2A2B36",
        "line_soft": "#22232E",
        "accent": "#D9B868",
        "accent_hover": "#E3CA8E",
        "accent2": "#2A2620",
        "accent2_hover": "#3A342A",
        "text": "#ECE8E0",
        "text_dim": "#9A9488",
        # 4,72:1 na surface (predtym #66625A = 2,85:1)
        "text_faint": "#8A857B",
        "success": "#8FBF9F",
        "danger": "#C1553D",
        "danger_text": "#D46F57",    # text/ram "Zmazat": 5,12:1 na surface
        "warn": "#C9A24D",
        "entry_bg": "#0A0B0F",
        "switch_off": "#2A2B36",
        "rule": "#393A46",           # deliace linky: 1,54:1 na surface
        "control_border": "#66676F",  # ram vedlajsieho tlacidla: 3,08:1
        "plate": "#17181F",
        "plate_glow": "#29241A",
        "plate_idle": "#131319",
        "plate_idle_border": "#3A2F22",
        "keycap_face": "#20212B",
        "keycap_edge": "#2E2F3B",
        "keycap_text": "#D9B868",
        "washi": "#DCD3C0",
        # --- stavove/sekundarne farby (dashboard, enso) ---
        "bengara": "#A6432E",        # POZN: enso uz pouziva success/danger
        "blue": "#7B93C9",           # pokojne/nizke hodnoty (napr. zotavenie HRR)
        "murasaki": "#B888C0",
        # --- pasma tepu (viz poznamka pod THEMES) ---
        # Sumi ide cely rad v teplej rodine: matcha -> zlato -> kvet slivky
        # -> bengara. Je to atrament a zlato, nic studene.
        #
        # `zone_calm` bola povodne #8FBF9F - mätova zelena, ktora sa v
        # atramente so zlatom citala ako cudzi prvok (nahlasene). Matcha je
        # tepla, zelenkava a z tej istej slovnej zasoby ako zvysok temy;
        # `success` (bezi / v poriadku) ostava ta povodna, to je stav, nie
        # pasmo tepu.
        "zone_calm": "#9CAE7B",
        "zone_raised": "#C9A24D",
        "zone_high": "#D9843F",
        "zone_critical": "#C1553D",
    },
}

# PASMA TEPU - vlastny rad farieb pre kazdu temu
# ----------------------------------------------
# Styri pasma (pokoj / zvysena / vysoka / kriticka) kreslili povodne
# success -> accent -> warn -> danger. Dva problemy naraz:
#
#   * v Sumi je `accent` #D9B868 a `warn` #C9A24D - dve takmer rovnake
#     zlate, ktore vedla seba na jednom pruhu nikto nerozlisi;
#   * v Aizome je `accent` modra a `blue` (pokojne, nizke hodnoty) ma tu
#     istu hodnotu, takze modra by znamenala aj "pokoj" aj "zvysena".
#
# Prva oprava zaviedla oranzovy medziclen a spolocny rad success -> warn ->
# oranzova -> danger. Lenze `warn` ma v OBOCH temach tu istu hodnotu
# (#C9A24D), takze
# pruh zataze v indigovej Aizome svietil sumijskym zlatom - vyzeral ako
# vystrihnuty z druhej temy.
#
# Preto ma teraz kazda tema svoje vlastne `zone_*` tokeny:
#   Sumi   - cely rad v teplej rodine (zelena -> zlato -> slivka -> bengara)
#   Aizome - studeny zaciatok (asagi, modrozelena pre pokoj - modra `blue`
#            patri len zotaveniu tepu), horuci koniec ostava horuci, lebo
#            teplo je teplo v kazdej teme
#
# Co plati v oboch: rad musi byt TEPLOTNE monotonny (od pokojneho ku
# horucemu) a vsetky styri farby navzajom rozlisitelne - to stapi
# `tests/test_hr_charts.py`. Akcent medzi nimi nie je vobec; ten patri
# ovladacim prvkom, nie stavu tepu.
#
# Farba pasma je JEDNA v celom rozhrani - stopa relacie, legenda aj pruh
# zataze ju beru cez `zone_color` nizsie.
ZONE_TOKENS = {
    "calm": "zone_calm",
    "raised": "zone_raised",
    "high": "zone_high",
    "critical": "zone_critical",
}


def zone_color(pal, zone):
    """Farba pasma tepu z palety - jediny zdroj pravdy pre vsetky grafy."""
    return pal[ZONE_TOKENS.get(zone, "accent")]


def tokens(theme_key):
    return THEMES.get(theme_key, THEMES[DEFAULT_THEME])


def mix(color_a, color_b, t):
    """Linearne miesanie dvoch #rrggbb farieb (t = 0 -> a, 1 -> b).

    Pouziva to dychajuci pas: Tk nevie animovat priehladnost ani mierku,
    takze sa "dych" robi plynulym prechodom vyplne medzi `plate` a
    `plate_glow`.
    """
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    a = [int(color_a.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    b = [int(color_b.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    return "#%02x%02x%02x" % tuple(
        int(round(x + (y - x) * t)) for x, y in zip(a, b))
