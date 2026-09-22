# -*- coding: utf-8 -*-
"""Prefarbenie uz postaveneho okna pri zmene temy - BEZ prestavby.

PRECO TO EXISTUJE
-----------------
Prepnutie temy volalo `DandurfApp._build_ui()`, ktore znicilo a odznova
postavilo cele okno. Odmerane: 1374 widgetov, 101 878 volani Tk, **2,97 s**
blokovania (rovnako v oboch smeroch) - a hrac tie tri sekundy pozeral, ako
sa okno sklada po castiach (29 roznych medzistavov). Ziadne jedno pomale
miesto tam nie je, je to holy objem: kazdy CustomTkinter widget sa kresli
na vlastne platno zaoblenymi tvarmi.

Namiesto toho tu prejdeme uz existujuci strom widgetov a prepiseme im
farby. Ziadne `destroy()`, ziadne stavanie - len `configure()`.

AKO SA MAPUJE
-------------
Nepotrebujeme vediet, z ktoreho tokenu ktora farba pochadza: staci mapa
"stara hodnota -> nova hodnota" postavena z dvoch paliet. Widget, ktory ma
`fg_color` rovny `zen['surface']`, dostane `modern['surface']`.

Farby, ktore v starej palete NIE SU (napr. vlastna farba vizualu, ktoru si
hrac vybral color pickerom, alebo predvolene farby CustomTkinteru), sa
zamerne nedotykame - nie su temou riadene.

NEJEDNOZNACNOST
---------------
Niektore tokeny maju v ramci temy rovnaku hodnotu. Vacsina je neskodna
(`surface` == `card` a mapuju sa na to iste), ale napr. v Sumi maju
`accent` aj `keycap_text` hodnotu #d9b868, kym v Modern sa rozchadzaju.
Pre take pripady je `_PREFERENCIA`: vyhrava semanticky dominantny token a
widgety, ktorym by to nesedelo, sa doriesia vlastnym `set_pal()`
(viz `IMAGE_HOOKS` a `ui_kit.Keycap`).

OBRAZKY
-------
Co je nakreslene ako obrazok (enso, kontrolka tepu, nahlad HUD), sa
prefarbit neda - treba prekreslit. Kazdy taky prvok ma vlastny
`set_pal()`, ktory zavola `DandurfApp._recolor_ui` po prejdeni stromu.
Rovnako to plati pre prvky, ktore si drzia VLASTNU kopiu palety
(Sidebar, _NavRow, TitleBar) - tie by inak vratili stare
farby pri prvom hover/kliku.
"""

# Ktory token vyhrava, ked ma viac tokenov rovnaku hodnotu. Vsetko
# neuvedene ma nizsiu prioritu nez uvedene, v poradi ako su tu.
_PREFERENCIA = (
    "bg", "surface", "surface_alt", "text", "text_dim", "text_faint",
    "border", "line_soft", "accent", "accent_hover", "accent2",
    "accent2_hover", "danger", "success", "warn",
)

# Volby, ktore nesu farbu. `bg`/`background` a `fg`/`foreground` su v Tk
# aliasy toho isteho - staci nastavit jednu, druhu preto v zozname nemame.
COLOR_OPTIONS = (
    # `bg_color` je odvodena farba pozadia, ktoru si CustomTkinter zisti z
    # rodica a ULOZI. Ked sa rodicovi zmeni `fg_color`, tato kopia ostane
    # stara a presvita v zaoblenych rohoch widgetu. Odhalil to az test
    # "prefarbenie == prestavba" na vnutornom platne segmentoveho
    # prepinaca tem - okom by si toho clovek vsimol nanajvys svetlejsi
    # lem okolo rohov.
    "bg_color",
    "fg_color", "text_color", "hover_color", "border_color",
    "button_color", "button_hover_color", "progress_color",
    "selected_color", "selected_hover_color",
    "unselected_color", "unselected_hover_color",
    "scrollbar_button_color", "scrollbar_button_hover_color",
    "dropdown_fg_color", "dropdown_text_color", "dropdown_hover_color",
    "placeholder_text_color",
    "bg", "fg", "selectbackground", "selectforeground",
    "highlightbackground", "insertbackground",
)


def build_color_map(old_pal, new_pal):
    """Mapa 'stara hodnota (lowercase) -> nova hodnota'.

    Berie do uvahy `_PREFERENCIA`, ked ma viac tokenov rovnaku staru
    hodnotu ale rozne nove.
    """
    poradie = {meno: i for i, meno in enumerate(_PREFERENCIA)}
    kandidati = {}
    for token, stara in old_pal.items():
        nova = new_pal.get(token)
        if not isinstance(stara, str) or not isinstance(nova, str):
            continue
        if not stara.startswith("#") or not nova.startswith("#"):
            continue
        kluc = stara.lower()
        vaha = poradie.get(token, len(poradie) + 1)
        if kluc not in kandidati or vaha < kandidati[kluc][0]:
            kandidati[kluc] = (vaha, nova)
    return {k: v for k, (_, v) in kandidati.items()}


def _preloz(hodnota, mapa):
    """Vrati novu hodnotu, alebo None ked sa nema menit."""
    if isinstance(hodnota, (list, tuple)):
        nove = [_preloz(h, mapa) for h in hodnota]
        if all(n is None for n in nove):
            return None
        return tuple(n if n is not None else s for n, s in zip(nove, hodnota))
    if not isinstance(hodnota, str):
        return None
    s = hodnota.lower()
    if not s.startswith("#"):
        return None          # "transparent" a nazvy farieb nechavame tak
    return mapa.get(s)


def recolor_widget(widget, mapa):
    """Prefarbi JEDEN widget. Vrati pocet zmenenych volieb.

    Vsetky zmeny idu JEDNYM volanim `configure()`. Je to podstatne:
    kazdy `configure()` na CustomTkinter widgete spusti cele prekreslenie
    na platno, takze volanie po jednej farbe znamenalo az 4 prekreslenia
    toho isteho tlacidla. Zlucenim sa prefarbenie zrychlilo takmer o
    polovicu.
    """
    zmeny = {}
    for opt in COLOR_OPTIONS:
        try:
            stara = widget.cget(opt)
        except Exception:
            continue
        nova = _preloz(stara, mapa)
        if nova is None or nova == stara:
            continue
        zmeny[opt] = nova
    if not zmeny:
        return 0
    try:
        widget.configure(**zmeny)
        return len(zmeny)
    except Exception:
        pass
    # Davka nepresla (napr. jedna volba sa uz nastavit neda) - skusime
    # po jednej, nech sa kvoli jednej zlej nestrati zvysok.
    zmen = 0
    for opt, nova in zmeny.items():
        try:
            widget.configure(**{opt: nova})
            zmen += 1
        except Exception:
            pass
    return zmen


def recolor_tree(widget, mapa, skip=()):
    """Prejde strom a prefarbi vsetko. Vrati (widgetov, zmenenych volieb).

    `skip` su triedy, ktore sa maju preskocit aj s potomkami - typicky
    samostatne Toplevel okna (HUD, in-game vizualy), ktore maju vlastnu
    cestu na zmenu temy.
    """
    widgetov = 0
    zmien = 0
    zasobnik = [widget]
    while zasobnik:
        w = zasobnik.pop()
        if skip and isinstance(w, skip):
            continue
        widgetov += 1
        zmien += recolor_widget(w, mapa)
        try:
            zasobnik.extend(w.winfo_children())
        except Exception:
            pass
    return widgetov, zmien


def find_theme_colored(widget, old_pal, new_pal=None, skip=()):
    """Najde widgety, ktore este drzia farbu zo STAREJ palety.

    Pouzite po prefarbeni ako poistka: co sa najde, je zabudnuty widget.
    Vracia zoznam (cesta_widgetu, volba, hodnota).

    `new_pal` je dolezite zadat: tokeny, ktore maju v oboch temach TU ISTU
    hodnotu (`warn`, `washi`, `font_family`), sa spravne nemenia - bez
    tohto by sa hlasili ako zabudnute, hoci su v poriadku.
    """
    nemenne = set()
    if new_pal:
        nemenne = {str(v).lower() for k, v in old_pal.items()
                   if isinstance(v, str) and str(new_pal.get(k, "")).lower() == str(v).lower()}
    hodnoty = {str(v).lower() for v in old_pal.values()
               if isinstance(v, str) and v.startswith("#")} - nemenne
    najdene = []
    zasobnik = [widget]
    while zasobnik:
        w = zasobnik.pop()
        if skip and isinstance(w, skip):
            continue
        for opt in COLOR_OPTIONS:
            try:
                val = w.cget(opt)
            except Exception:
                continue
            vals = val if isinstance(val, (list, tuple)) else [val]
            for v in vals:
                if isinstance(v, str) and v.lower() in hodnoty:
                    najdene.append((str(w), opt, str(v)))
        try:
            zasobnik.extend(w.winfo_children())
        except Exception:
            pass
    return najdene
