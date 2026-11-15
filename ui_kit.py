"""Stavebne prvky noveho rozhrania - to, co v makete robilo CSS.

Preco samostatny modul
----------------------
Maketa stavala na veciach, ktore CSS vie zadarmo a Tk nevie vobec:
priehladnost, mierka, prechody, `grid-template-columns`. Kazdy taky prvok
tu ma jednu triedu, ktora to dorobi rucne - a app.py potom sklada uz len
hotove diely, nie pixely.

Tri veci, ktore sa museli vymysliet inak nez v HTML:

  * DYCHAJUCI PAS. V CSS to bola animacia mierky a priehladnosti. Tk ani
    jedno nevie, tak `KamaeBar` dycha PLYNULYM PRECHODOM VYPLNE medzi
    `plate` a `plate_glow` (viz theme.mix) plus rastucou linkou na spodnej
    hrane. Su to dva signaly namiesto jedneho, cize to funguje aj pre toho,
    kto farebny rozdiel nevidi.

  * KEYCAP. `border-bottom: 3px` sa v CTkFrame zadat neda, tak je keycap
    dva ramy nad sebou: tmavsi spodny (hrana) a svetlejsi vrchny (plocha),
    posunuty o 3 px hore.

  * PEVNY RASTER. `grid-template-columns: 108px 1fr 100px ...` je v Tk
    `grid_columnconfigure(i, minsize=..., weight=...)`. Rozdiel je, ze Tk
    minsize NEOREZAVA obsah - sirsi widget stlpec roztiahne. Preto maju
    vsetky prvky v rastri pevnu `width`.

Ziadny prvok tu nema vlastnu logiku appky - vsetko berie cez callbacky.
"""

import math
import os
import sys
import time
import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox    # len zaloha okien appky (`_systemove_okno`)

import customtkinter as ctk

import display as display_mod     # `display` je v tomto module font (nizsie)
import hr_stats
import theme as theme_mod


# --------------------------------------------------------------------------
# Pisma
# --------------------------------------------------------------------------
#
# Maketa pouzivala Zen Kaku Gothic New a Chivo Mono z Google Fonts. Tk vie
# len pisma nainstalovane v systeme, takze sa berie prve dostupne z radu.
# Bahnschrift (DIN-ovsky uzky technicky rez) je sucastou Windows 10 aj 11 a
# je najblizsie technickemu charakteru, aky cisla na HUD-e potrebuju.

_UI = ["Segoe UI Variable Text", "Segoe UI", "Inter", "DejaVu Sans", "TkDefaultFont"]
_DISPLAY = ["Bahnschrift", "Segoe UI Semibold", "Segoe UI", "DejaVu Sans"]
_MONO = ["Cascadia Mono", "Consolas", "DejaVu Sans Mono", "Courier New"]

# JAPONCINA A CINSTINA maju vlastne pismo (0.2.2, audit UX). Segoe UI
# kanji nema, takze Tk kazdy znak dohladal v inom nahradnom pisme -
# "メインスイッチ" vyslo tenko, "心拍と負荷" inym rezom, v jednom riadku dve
# pisma. Pismo s CJK znakmi od Windows (Yu Gothic UI / Microsoft YaHei UI)
# kresli latinku aj znaky jednym rezom. Plati pre texty aj nadpisy;
# cisla (mono) ostavaju.
_UI_LANG = {
    "ja": ["Yu Gothic UI", "Meiryo UI", "MS UI Gothic"],
    "zh": ["Microsoft YaHei UI", "Microsoft YaHei", "SimHei"],
}

_resolved = {}


def _pick(candidates):
    try:
        available = {name.lower() for name in tkfont.families()}
    except Exception:
        return candidates[-1]
    for name in candidates:
        if name.lower() in available:
            return name
    return candidates[-1]


def _jazyk_pisma():
    """Jazyk rozhrania, ak ma vlastne pismo (ja/zh), inak "".

    Cita sa pri kazdom volani: prepnutie jazyka stavia okno znova, takze
    nove widgety si nove pismo vezmu samy."""
    try:
        import i18n
        kod = i18n._lang.get("code", "")
    except Exception:
        return ""
    return kod if kod in _UI_LANG else ""


def fonts():
    """Nazvy pisiem - zisti sa raz pre kazdy jazyk, az ked existuje Tk root."""
    kod = _jazyk_pisma()
    if kod not in _resolved:
        sada = {"mono": _pick(_MONO)}
        if kod:
            cjk = _pick(_UI_LANG[kod] + _UI)
            sada["ui"] = cjk
            sada["display"] = cjk
        else:
            sada["ui"] = _pick(_UI)
            sada["display"] = _pick(_DISPLAY)
        _resolved[kod] = sada
    return _resolved[kod]


# Kanji a hanzi maju v jednom znaku viac tahov nez latinka - pri 10 px sa
# zlievaju (audit: "kanji v 9 pt"). V japoncine a cinstine je preto
# najmensie pismo rozhrania 11.
_CJK_MIN_SIZE = 11


def ui(size, weight="normal"):
    if _jazyk_pisma() and size < _CJK_MIN_SIZE:
        size = _CJK_MIN_SIZE
    return (fonts()["ui"], size, weight)


def display(size, weight="normal"):
    return (fonts()["display"], size, weight)


def mono(size, weight="normal"):
    return (fonts()["mono"], size, weight)


# --------------------------------------------------------------------------
# Kreslenie na Canvas
# --------------------------------------------------------------------------

def round_rect(canvas, x0, y0, x1, y1, r, **kw):
    """Zaobleny obdlznik - Tk Canvas ho ako primitivum nema.

    Skladá sa z jedneho vyhladeneho polygonu; zdvojene rohove body nutia
    `smooth=True` zaoblit len rohy a hrany nechat rovne.
    """
    r = max(0, min(r, (x1 - x0) / 2, (y1 - y0) / 2))
    points = [
        x0 + r, y0, x1 - r, y0, x1 - r, y0, x1, y0,
        x1, y0 + r, x1, y1 - r, x1, y1 - r, x1, y1,
        x1 - r, y1, x0 + r, y1, x0 + r, y1, x0, y1,
        x0, y1 - r, x0, y0 + r, x0, y0 + r, x0, y0,
    ]
    return canvas.create_polygon(points, smooth=True, **kw)


# --------------------------------------------------------------------------
# Jednotne zaoblenie
# --------------------------------------------------------------------------
#
# Feedback z testu: appka miesala hranate (radius 3-4) a zaoblene (12-14)
# prvky. Odteraz JEDEN styl: panely a karty RADIUS_PANEL, tlacidla, polia
# a chipy RADIUS_CONTROL. Nove prvky maju pouzit tieto konstanty, nie cisla.

RADIUS_PANEL = 10
RADIUS_CONTROL = 8


# --------------------------------------------------------------------------
# Jedna miera pre celu appku (0.2.2, audit UX)
# --------------------------------------------------------------------------
#
# Audit nasiel styri lave hrany (karty na x=161, obsah na 171, nadpisy raz
# na 170, raz na 179) a zubaty pravy stlpec: rozbalovacky koncili na inej
# x nez posuvniky, lebo CTkOptionMenu bez `dynamic_resizing=False` rastie s
# textom zvolenej polozky. Odteraz:
#   * PAGE_GUTTER - lavy a pravy okraj kazdej stranky, radu kariet (SubNav)
#     aj dychajuceho pasu, nech vsetko zacina na jednej zvislici,
#   * CONTROL_W - sirka ovladaca v pravom stlpci riadku nastavenia
#     (rozbalovacka, posuvnik), nech maju jednu pravu hranu.

PAGE_GUTTER = 24
CONTROL_W = 250
# Sirka zvisleho posuvnika CTkScrollableFrame vratane jeho 1 px okraja
# (CTkScrollbar ma 16 px). Prvok NAD posuvanou plochou (dychajuci pas na
# Dnes) si ju nechava vpravo volnu, aby koncil tam, kde karty pod nim.
SCROLLBAR_W = 17


def linka(master, pal, token="rule"):
    """Vodorovna deliaca linka 1 px vo farbe `pal[token]`.

    PRECO NIE HOLY `CTkFrame(height=1)`: CTk pri vyske 1 px nakresli
    obdlznik s nulovou vyskou (y0 == y1) a platno pod nim ma farbu RODICA -
    linka nebola vidno vobec, bez ohladu na kontrast (overene na CTk 6.0).
    Odtial "nevysvetlene medzery" z auditu. `bg_color` v tej istej farbe
    zafarbi samotne platno, takze linka ma vzdy presne 1 px. Aby ju pri zmene
    temy neprepisal rodic, drzi `_drz_pozadie_linky`."""
    farba = pal[token]
    ciara = ctk.CTkFrame(master, fg_color=farba, bg_color=farba, height=1,
                         corner_radius=0)
    _drz_pozadie_linky(ciara)
    return ciara


def _drz_pozadie_linky(ciara):
    """Pozadie linky ostane VZDY v jej vlastnej farbe (`bg_color` = `fg_color`).

    PRECO: CTkFrame pri zmene svojho `fg_color` posle vsetkym CTk detom
    `configure(bg_color=<svoja vypln>)` (a priehladny ramec posiela
    "transparent"). `theme_recolor` prefarbuje rodica SKOR nez dieta, takze
    po prepnuti sveta Hra <-> Praca dostala linka pozadie panela a zase
    zmizla - na snimkach 09/09b ziadna linka pod nadpisom panela, kym sa
    okno neprestavalo. Kazde `bg_color` sa tu preto nahradi vyplnou linky
    (nova vypln, ak prisla v tom istom volani). Vlastna metoda na INSTANCII,
    nie podtrieda: `ctk.CTkFrame` ide v testoch nahradit atrapou."""
    povodne = getattr(ciara, "configure", None)
    if povodne is None:
        return

    def configure(require_redraw=False, **kw):
        if "fg_color" in kw:
            kw["bg_color"] = kw["fg_color"]
        elif "bg_color" in kw:
            kw["bg_color"] = getattr(ciara, "_fg_color", None) or kw["bg_color"]
        return povodne(require_redraw=require_redraw, **kw)

    try:
        ciara.configure = configure
    except Exception:
        pass


def stranka_scroll(master, pal):
    """Posuvana plocha stranky so spolocnym vzhladom.

    `corner_radius=0` nie je kozmetika: CTkScrollableFrame odsadzuje obsah
    o svoj radius (predvolene 6 px), takze karty v nom zacinali o 6 px
    dalej nez rad kariet a pas nad nimi - odtial "styri lave hrany" z
    auditu. Volajuci ju packuje s `padx=PAGE_GUTTER`."""
    return ctk.CTkScrollableFrame(
        master, fg_color="transparent", corner_radius=0,
        scrollbar_button_color=pal["surface_alt"],
        scrollbar_button_hover_color=pal["accent"])


def switch(master, pal, text="", **kw):
    """Jediny prepinac appky.

    Zapnuty ma drahu v `accent`, vypnuty v `switch_off`, gombik je vzdy
    svetly (`text`). Do 0.2.2 malo sedem z deviatich prepinacov zapnutu
    drahu v `accent2` - proti vypnutej to bol kontrast 1,07:1, takze
    zapnute "Tazisko" vyzeralo presne ako vypnute (nahlasene v audite). Dva
    zvysne mali zlatu drahu, cize appka mala dva styly naraz.

    Bez textu je prepinac kompaktny (36x18), ako v pravom stlpci riadku
    nastavenia; s textom ma predvolenu velkost CTk. Vsetko ide prepisat cez
    `kw`, len farby stavu nie - tie su pravidlo, nie vkus.
    """
    style = {
        "progress_color": pal["accent"],
        "fg_color": pal["switch_off"],
        "button_color": pal["text"],
        "button_hover_color": pal["accent_hover"],
        "text_color": pal["text_dim"],
        "font": ui(12),
    }
    if not text:
        style.update(width=40, switch_width=36, switch_height=18)
    style.update(kw)
    return ctk.CTkSwitch(master, text=text, **style)


def nastav_prepinac_aktivny(sw, pal, aktivny):
    """Zosedivi prepinac, ktory prave nema co ovladat (napr. ikonky HUD-u,
    kym je panel s tepom vypnuty).

    `state="disabled"` v CTk zosedivi len text - zapnuta zlata draha by
    dalej tvrdila "zapnute a funguje". Preto sa ztlmi aj draha a gombik."""
    try:
        if aktivny:
            sw.configure(state="normal", progress_color=pal["accent"],
                         button_color=pal["text"])
        else:
            sw.configure(state="disabled", progress_color=pal["control_border"],
                         button_color=pal["text_faint"])
    except Exception:
        pass


# Styri druhy tlacidla. Kazde miesto si predtym skladalo farby samo, takze
# "Exportovat" malo vypln, "Zmazat historiu" vyzeralo ako "Importovat" a
# ram "Nahrat"/"Subor" mal kontrast 1,11:1 - tlacidla vyzerali vypnute.
BUTTON_KINDS = ("primary", "secondary", "quiet", "danger")
_BUTTON_PAD_X = 14          # vnutorny okraj textu pri prirodzenej sirke


def _sirka_textu(text, font):
    """Sirka textu v LOGICKYCH px (CTk pismo ma velkost v px, nie v bodoch).

    Bez Tk rootu (testy) vrati odhad - presnost tu nie je funkcia, len
    vzhlad."""
    try:
        family, size = font[0], font[1]
        weight = font[2] if len(font) > 2 else "normal"
        return tkfont.Font(family=family, size=-abs(int(size)),
                           weight=weight).measure(str(text))
    except Exception:
        return int(len(str(text)) * float(font[1]) * 0.6)


def button(master, pal, text, command=None, kind="secondary", width=None,
           height=30, font=None, fit_texts=(), **kw):
    """Tlacidlo jedneho zo styroch druhov (`BUTTON_KINDS`).

      primary   - vypln `accent`; najviac jedno na kartu, je to "hlavna
                  vec, kvoli ktorej tu si",
      secondary - ram `control_border` (>= 3:1), text `text`,
      quiet     - bez ramu, text `text_dim` (pomocne akcie),
      danger    - ram aj text v `danger_text` (zmazat, odobrat).

    `width=None` = PRIRODZENA sirka podla textu. Tlacidlo roztiahnute cez
    celu kartu (napr. "Ako sparovat hodinky..." cez ~1500 px) kricalo
    hlasnejsie nez obsah karty. Radius je ten isty ako pri ostatnych
    ovladacoch (`RADIUS_CONTROL`), nie vlastny.

    `fit_texts` = dalsie texty, ktore tlacidlo neskor ukaze (prepinac
    "Ukazat IP" / "Skryt IP"): prirodzena sirka sa vezme z najdlhsieho, aby
    tlacidlo pri prepnuti neposkocilo.

    VYPNUTE TLACIDLO (0.2.2 davka 4b) ma jeden vzhlad pre vsetky druhy
    (`vzhlad_vypnuteho`): text `text_faint`, ram `control_border`. CTk pri
    `state="disabled"` zosedivi len text - "Zmazat historiu" pocas
    sledovania si nechalo cerveny ram a vyzeralo zapnute. Vzhlad sa prepne
    pri kazdom `configure(state=...)` a pri zapnuti sa vrati (`_drz_vzhlad_
    vypnuteho`), takze volajuci nic dalsie robit nemusi.
    """
    if kind not in BUTTON_KINDS:
        kind = "secondary"
    font = font or ui(12)
    style = _farby_druhu(kind, pal)
    style["text_color_disabled"] = pal["text_faint"]
    if width is None:
        width = max(_sirka_textu(t, font) for t in (text,) + tuple(fit_texts or ())) \
            + 2 * _BUTTON_PAD_X
    style.update(corner_radius=RADIUS_CONTROL, height=height, width=width, font=font)
    style.update(kw)
    vypnute = str(style.get("state", "")) == "disabled"
    style.pop("state", None)
    btn = ctk.CTkButton(master, text=text, command=command, **style)
    _drz_vzhlad_vypnuteho(btn, kind, pal)
    if vypnute:
        try:
            btn.configure(state="disabled")
        except Exception:
            pass
    return btn


def _farby_druhu(kind, pal):
    """Farby ZAPNUTEHO tlacidla druhu `kind` (viz `button`)."""
    if kind == "primary":
        return {"fg_color": pal["accent"], "hover_color": pal["accent_hover"],
                "text_color": pal["bg"], "border_width": 0}
    if kind == "danger":
        return {"fg_color": "transparent", "hover_color": pal["surface_alt"],
                "text_color": pal["danger_text"], "border_width": 1,
                "border_color": pal["danger_text"]}
    if kind == "quiet":
        return {"fg_color": "transparent", "hover_color": pal["surface_alt"],
                "text_color": pal["text_dim"], "border_width": 0}
    return {"fg_color": "transparent", "hover_color": pal["surface_alt"],
            "text_color": pal["text"], "border_width": 1,
            "border_color": pal["control_border"]}


# Token textu zapnuteho tlacidla - podla neho sa pozna, v ktorej teme prave
# je (`_paleta_podla_farby`), aj ked sa medzitym prepol svet.
_TOKEN_TEXTU = {"primary": "bg", "secondary": "text", "quiet": "text_dim",
                "danger": "danger_text"}
_FARBY_TLACIDLA = ("fg_color", "hover_color", "text_color", "border_color")


def vzhlad_vypnuteho(kind, pal):
    """Farby VYPNUTEHO tlacidla - jeden vzhlad pre vsetky druhy.

    Text `text_faint` (>= 4,5:1, takze sa da precitat, preco tam je), ram
    `control_border` u druhov, ktore ram maju (aj `danger` - vypnute
    "Zmazat" nesmie svietit cervenou), `primary` straca zlatu vypln. Vypnute
    tlacidlo nema hover, to zariadi CTk samo."""
    st = {"text_color": pal["text_faint"], "text_color_disabled": pal["text_faint"]}
    if kind == "primary":
        st["fg_color"] = pal["surface_alt"]
    if kind in ("secondary", "danger"):
        st["border_color"] = pal["control_border"]
    return st


def _paleta_podla_farby(farba, token):
    """Paleta temy, v ktorej ma `token` hodnotu `farba` (inak None)."""
    farba = str(farba or "").lower()
    for paleta in theme_mod.THEMES.values():
        if str(paleta.get(token, "")).lower() == farba:
            return paleta
    return None


def _drz_vzhlad_vypnuteho(btn, kind, pal):
    """`configure(state=...)` na tlacidle prepne aj jeho vzhlad.

    Vlastna metoda na INSTANCII (ako `_drz_pozadie_linky`), nie podtrieda -
    `ctk.CTkButton` ide v testoch nahradit atrapou. Pri vypnuti si zapamata
    farby, ktore tlacidlo prave ma (aj volajucim zmenene, napr. Test pocas
    testu), a pri zapnuti ich vrati. Ked sa medzitym prepla tema (prefarbenie
    `theme_recolor` meni farby podla hodnoty), zapamatane farby sa do novej
    temy prelozia. Farby, ktore volajuci posle v tom istom volani, maju
    prednost. Nikdy nevyhodi vlastnu vynimku."""
    povodne = getattr(btn, "configure", None)
    if povodne is None:
        return
    stav = {"zapnute": None, "pal": pal}

    def _cget(meno):
        try:
            return btn.cget(meno)
        except Exception:
            return None

    def _doplnok(kw):
        """Farby, ktore treba k `kw` pridat (nikdy nie tie, co v nom su)."""
        novy = str(kw.get("state", ""))
        vypnut = novy == "disabled"
        bolo_vypnute = stav["zapnute"] is not None
        if vypnut and not bolo_vypnute:
            aktualna = (_paleta_podla_farby(_cget("text_color"), _TOKEN_TEXTU[kind])
                        or stav["pal"])
            stav["zapnute"] = {k: _cget(k) for k in _FARBY_TLACIDLA}
            stav["pal"] = aktualna
            return vzhlad_vypnuteho(kind, aktualna)
        if novy == "normal" and bolo_vypnute:
            aktualna = (_paleta_podla_farby(_cget("text_color"), "text_faint")
                        or stav["pal"])
            zapnute, stav["zapnute"] = stav["zapnute"], None
            mapa = {}
            if aktualna is not stav["pal"]:
                import theme_recolor
                mapa = theme_recolor.build_color_map(stav["pal"], aktualna)
            stav["pal"] = aktualna
            von = {}
            for meno, farba in zapnute.items():
                if farba is None:
                    continue
                von[meno] = mapa.get(str(farba).lower(), farba) \
                    if isinstance(farba, str) else farba
            return von
        if bolo_vypnute and "text_color" in kw and "state" not in kw:
            # prefarbenie temy pocas vypnutia - aj text vypnuteho stavu
            return {"text_color_disabled": kw["text_color"]}
        return {}

    def configure(require_redraw=False, **kw):
        try:
            for meno, farba in _doplnok(kw).items():
                kw.setdefault(meno, farba)
        except Exception:
            pass
        if require_redraw:
            return povodne(require_redraw=True, **kw)
        return povodne(**kw)

    try:
        btn.configure = configure
    except Exception:
        pass


_MENU_CHROME_W = 56        # lavy okraj textu + sipka vpravo + rezerva


def option_menu(master, pal, width=CONTROL_W, **kw):
    """Rozbalovacka pevnej sirky (`CONTROL_W`), aby vsetky v jednom stlpci
    koncili na tej istej pravej hrane - CTk ju inak nafukuje podla textu
    zvolenej polozky a pri kazdom vybere by poskocila.

    Pevna, ale nie orezavajuca: ked je niektora z `values` dlhsia, nez sa do
    `width` zmesti (dlhy preklad, nazov motora hlasu), sirka sa raz nastavi
    podla najdlhsej - text sa nikdy neodreze a pri vybere uz neposkoci.
    Prava hrana ostava rovnaka, lebo riadok nastavenia drzi ovladac vpravo."""
    font = kw.get("font") or ui(12)
    hodnoty = kw.get("values") or []
    min_width = width
    if hodnoty and not kw.get("dynamic_resizing"):
        width = sirka_menu(hodnoty, font, min_width)
    style = {
        "width": width, "height": 28, "corner_radius": RADIUS_CONTROL,
        "dynamic_resizing": False,
        "fg_color": pal["surface_alt"], "button_color": pal["accent2"],
        "button_hover_color": pal["accent2_hover"], "text_color": pal["text"],
        "dropdown_fg_color": pal["surface"], "dropdown_text_color": pal["text"],
        "dropdown_hover_color": pal["surface_alt"], "font": font,
    }
    style.update(kw)
    style["width"] = width
    menu = ctk.CTkOptionMenu(master, **style)
    try:
        menu._zanshin_menu = (font, min_width, bool(kw.get("dynamic_resizing")))
    except Exception:
        pass
    return menu


def sirka_menu(hodnoty, font, min_width=CONTROL_W):
    """Sirka rozbalovacky, do ktorej sa zmesti najdlhsia z `hodnoty`
    (aspon `min_width`) - pravidlo `option_menu` na jednom mieste."""
    try:
        najdlhsia = max(_sirka_textu(h, font) for h in hodnoty)
    except ValueError:
        return min_width
    return max(min_width, najdlhsia + _MENU_CHROME_W)


def nastav_hodnoty_menu(menu, values):
    """Nove polozky rozbalovacky z `option_menu` - a s nimi aj nova sirka.

    `configure(values=...)` sirku nemeni: vyber hlasu sa plni az po starte
    (hlasy Windows, prirodzene hlasy), takze rozbalovacka ostala na sirke
    "Nacitavam..." a dlhe meno hlasu Windows ("Microsoft Hedda Desktop -
    German (Germany)") sa orezalo. Sirka sa preto prepocita tym istym
    pravidlom ako pri stavbe (`sirka_menu`); nikdy nie mensia nez povodna
    minimalna. Nikdy nevyhodi vynimku."""
    values = list(values or [])
    try:
        font, min_width, dynamicka = getattr(menu, "_zanshin_menu", (ui(12), CONTROL_W, False))
        kw = {"values": values}
        if values and not dynamicka:
            kw["width"] = sirka_menu(values, font, min_width)
        menu.configure(**kw)
    except Exception:
        try:
            menu.configure(values=values)
        except Exception:
            pass


def oznac_zvoleny_segment(seg, pal):
    """Zvoleny segment CTkSegmentedButton ma text v `accent_hover`, ostatne
    v `text_dim`.

    Vypln zvoleneho segmentu (`accent2`) mala proti nezvolenemu kontrast
    1,15:1 - v liste "Hra | Praca" nebolo vidno, v ktorom svete si. CTk
    nevie farbu textu po segmentoch, tak sa nastavi priamo na tlacidlach
    (`_buttons_dict`, to iste, cez co ide bublina v `ui_shell.TitleBar`).
    `set()` CTk meni len vypln, takze text treba prekreslit po kazdom
    `set()` aj po prefarbeni temy. Nikdy nevyhodi vynimku."""
    try:
        zvolene = seg.get()
        for hodnota, tlacidlo in getattr(seg, "_buttons_dict", {}).items():
            tlacidlo.configure(text_color=pal["accent_hover"] if hodnota == zvolene
                               else pal["text_dim"])
    except Exception:
        pass


# --------------------------------------------------------------------------
# Panel
# --------------------------------------------------------------------------

class Panel(ctk.CTkFrame):
    """Panel s hlavickou a telom.

    Rozdiel oproti povodnym kartam: hlavicka ma vlastnu deliacu linku a telo
    vlastny odsadenie, takze sa da do neho sypat obsah bez toho, aby si ho
    kazde miesto v appke odsadzovalo samo (a zakazde inak).
    """

    def __init__(self, master, pal, title=None, right=None, **kw):
        kw.setdefault("fg_color", pal["surface"])
        kw.setdefault("corner_radius", RADIUS_PANEL)
        kw.setdefault("border_width", 1)
        kw.setdefault("border_color", pal["line_soft"])
        super().__init__(master, **kw)
        self.pal = pal
        self.right_label = None

        # ROZOSTUPY 8/16 (0.2.2, audit UX, davka 4): nadpis -> linka -> telo
        # mali 9 + 14 px a riadok nastavenia pod tym este svojich 9, takze
        # medzi linkou a prvym textom bolo 23 px - viac nez medzi dvoma
        # panelmi. Teraz 8 px nad linkou aj pod nou (+ odsadenie riadku).
        if title is not None:
            head = ctk.CTkFrame(self, fg_color="transparent", height=40)
            head.pack(fill="x", padx=16, pady=(11, 0))
            ctk.CTkLabel(head, text=title, font=ui(13, "bold"),
                         text_color=pal["text"]).pack(side="left")
            # Veta vpravo ("3 relacie", "Analyza z ...") je proza, nie
            # cislo v tabulke - monospace jej davalo vzhlad vypisu z konzoly.
            self.right_label = ctk.CTkLabel(head, text=right or "",
                                            font=ui(11), text_color=pal["text_dim"])
            self.right_label.pack(side="right")
            # `rule` (>= 1,5:1), nie `line_soft` (1,11:1): linka, ktoru
            # nevidno, nechava len nevysvetlenu medzeru pod nadpisom.
            rule = linka(self, pal)
            rule.pack(fill="x", pady=(8, 0))

        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=16,
                       pady=(8 if title is not None else 14, 14))

    def set_right(self, text):
        if self.right_label is not None:
            try:
                self.right_label.configure(text=text)
            except Exception:
                pass


def priprav_popup(top):
    """Obycajny `tk.Toplevel`, do ktoreho sa chystaju CTk widgety.

    CUSTOMTKINTER SI TAKE OKNO ZAREGISTRUJE, HOCI NIE JE JEHO. Staci don
    vlozit jediny CTk widget a `ScalingTracker` si ho prida do zoznamu,
    ktory potom periodicky obchadza a vola na nom
    `block_update_dimensions_event()`. Ta metoda existuje len na
    `CTk`/`CTkToplevel`, takze na obycajnom `tk.Toplevel` to spadne na
    AttributeError - v `after` callbacku, cize appku to nezhodi, len to
    potichu pristane v crash.log pri kazdej zmene DPI.

    `CTkToplevel` tu pouzit nemozeme: prekresluje sa s vlastnou titulkovou
    listou a `overrideredirect` mu ju neodoberie. Doplnime teda tie dve
    metody - nie je co blokovat, tieto okna si velkost nastavuju samy a na
    zmenu rozmerov nepocuvaju.

    Vracia to iste okno, aby sa dalo zavolat v retazci.
    """
    top.block_update_dimensions_event = lambda: None
    top.unblock_update_dimensions_event = lambda: None
    return top


def fit_popup(x, y, width, height, area, above_y, margin=8):
    """Poloha (x, y) popupu tak, aby cely ostal v `area` = (x0, y0, x1, y1).

    Vodorovne sa len pritlaci dovnutra. Ked sa nezmesti POD kotvu, vysunie
    sa NAD nu: `above_y` je horny okraj kotvy (tlacidla) a popup potom konci
    4 px nad nim - rovnako ako ⓘ na karte (`StatCard._toggle_info`)."""
    x0, y0, x1, y1 = area
    x = max(x0 + margin, min(int(x), x1 - width - margin))
    if y + height > y1 - margin:
        y = max(y0 + margin, above_y - height - 4)
    return int(x), int(y)


def work_area(widget):
    """Pracovna plocha (bez listy uloh) TOHO monitora, na ktorom je stred
    `widget` - v suradniciach virtualnej plochy, ako winfo_rootx/rooty.

    Nie `winfo_screenwidth/height`: ta vracia len primarnu obrazovku, takze
    na druhom monitore by popup odskocil spat na prvy."""
    try:
        cx = widget.winfo_rootx() + widget.winfo_width() // 2
        cy = widget.winfo_rooty() + widget.winfo_height() // 2
        for mon in display_mod.monitors(widget):
            if mon.contains(cx, cy):
                return (mon.work_x, mon.work_y,
                        mon.work_x + mon.work_width, mon.work_y + mon.work_height)
    except Exception:
        pass
    return (0, 0, widget.winfo_screenwidth(), widget.winfo_screenheight())


def _window_hwnd(window):
    try:
        import ctypes
        u = ctypes.windll.user32
        u.GetAncestor.restype = ctypes.c_void_p
        u.GetAncestor.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        return u.GetAncestor(ctypes.c_void_p(int(window.winfo_id())), 2)  # GA_ROOT
    except Exception:
        return None


def pripni_k_vlastnikovi(top):
    """Windows: dialog nech PATRI hlavnemu oknu - potom je vzdy nad nim.

    Tk bezramovym (overrideredirect) oknam na Windows zahodi vlastnika
    ("Parent must be desktop even if we have a transient parent" v
    tkWinWm.c), takze `transient(root)` sa neprejavi. Hlavne okno potom
    moze dialog prekryt - 24. 9. zostal dotaznik po relacii schovany za
    appkou a hrac ho nevedel vyplnit (hlavne okno malo WS_EX_TOPMOST).

    Vlastnika nastavime priamo (GWLP_HWNDPARENT). Vlastnene okno je vo
    Windows v poradi okien VZDY nad svojim vlastnikom. Ak je vlastnik
    topmost, dialog dostane topmost tiez, aby sa pred neho vzdy dostal.
    Vlastny WinDLL handle - nemenime argtypes zdielanych funkcii windll.
    Nikdy nevyhodi vynimku; vrati True, ked sa vlastnik nastavil."""
    try:
        import ctypes
        master = getattr(top, "master", None)
        if master is None:
            return False
        dlg = _window_hwnd(top)
        own = _window_hwnd(master.winfo_toplevel())
        if not dlg or not own or int(dlg) == int(own):
            return False
        u = ctypes.WinDLL("user32")
        nastav = getattr(u, "SetWindowLongPtrW", None) or u.SetWindowLongW
        nastav.restype = ctypes.c_void_p
        nastav.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
        nastav(ctypes.c_void_p(dlg), -8, ctypes.c_void_p(own))    # GWLP_HWNDPARENT
        u.GetWindowLongW.restype = ctypes.c_long
        u.GetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int]
        if u.GetWindowLongW(ctypes.c_void_p(own), -20) & 0x00000008:   # WS_EX_TOPMOST
            top.attributes("-topmost", True)
        return True
    except Exception:
        return False


def freeze_repaint(window, frozen):
    """Zmrazi/odmrazi kreslenie okna cez WM_SETREDRAW.

    Pouziva sa okolo prestavby UI (zmena jazyka -> cely `_build_ui`) aj
    okolo prepoctu DPI (presun na monitor s inou mierkou): medzikroky sa
    inak zobrazia ako blikanie/prestavba. Pocas zmrazenia Windows nekresli;
    po odmrazeni sa vynuti JEDNO ciste prekreslenie celeho okna. Geometria
    (rozmiestnenie, mierka) sa medzitym normalne prepocita - WM_SETREDRAW
    blokuje len KRESLENIE, nie layout."""
    try:
        import ctypes
        h = _window_hwnd(window)
        if not h:
            return
        u = ctypes.windll.user32
        u.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint,
                                   ctypes.c_void_p, ctypes.c_void_p]
        u.SendMessageW(h, 0x000B, 1 if not frozen else 0, 0)   # WM_SETREDRAW
        if not frozen:
            u.RedrawWindow.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                       ctypes.c_void_p, ctypes.c_uint]
            # RDW_INVALIDATE | RDW_ERASE | RDW_ALLCHILDREN | RDW_UPDATENOW
            u.RedrawWindow(h, None, None, 0x0001 | 0x0004 | 0x0080 | 0x0100)
    except Exception:
        pass


# DWM "cloak" (Windows 8+). Zahalene okno je pre Windows ZOBRAZENE - dostava
# WM_PAINT a Tk ho normalne nakresli -, len ho DWM nepusti na obrazovku.
# Presne to treba pri starte: okno sa ukaze az cele nakreslene, naraz.
_DWMWA_CLOAK = 13      # zapis: 1 = zahalit, 0 = odhalit
_DWMWA_CLOAKED = 14    # citanie: nenulove = okno je zahalene (appkou/shellom)
_dwmapi = None


def _dwm():
    """Vlastny handle na dwmapi.dll, NIE zdielany `ctypes.windll.dwmapi`.

    CustomTkinter vola ten isty `DwmSetWindowAttribute` cez `windll` (tmava
    titulkova lista v ctk_tk.py) bez `argtypes`. Keby sme ich nastavili na
    zdielanom objekte, menili by sme knizniciam cestu volania. `WinDLL` ma
    vlastne funkcne objekty, takze nase `argtypes` nevidi nikto iny."""
    global _dwmapi
    if _dwmapi is None:
        import ctypes
        lib = ctypes.WinDLL("dwmapi")
        for meno in ("DwmSetWindowAttribute", "DwmGetWindowAttribute"):
            fn = getattr(lib, meno)
            fn.argtypes = [ctypes.c_void_p, ctypes.c_uint,
                           ctypes.c_void_p, ctypes.c_uint]
            fn.restype = ctypes.c_long            # HRESULT, 0 = S_OK
        _dwmapi = lib
    return _dwmapi


def zahal_okno(window, zahalit):
    """Zahali (`zahalit=True`) alebo odhali okno cez DWM (DWMWA_CLOAK).

    Na rozdiel od `withdraw()` sa okno pritom normalne kresli, len ho nevidno.
    Vracia True, ked to Windows prijal; inak False a nedeje sa nic - okno sa
    sprava ako doteraz. Nikdy nevyhodi vynimku (najlepsia snaha, ako
    `freeze_repaint`).

    POZOR: plasti sa HWND obalu okna. `overrideredirect(False)` (napr.
    minimalizacia bezramoveho okna v `ui_shell.TitleBar`) necha Tk obal
    znova vytvorit a NOVE okno zahalene nie je - teda sa ukaze. To je
    bezpecna strana (okno nikdy neostane neviditelne); neopravovat to
    opatovnym zahalenim stareho handle."""
    try:
        import ctypes
        h = _window_hwnd(window)
        if not h:
            return False
        hodnota = ctypes.c_int(1 if zahalit else 0)
        return _dwm().DwmSetWindowAttribute(
            h, _DWMWA_CLOAK, ctypes.byref(hodnota), ctypes.sizeof(hodnota)) == 0
    except Exception:
        return False


def je_zahalene(window):
    """Je okno prave zahalene (DWMWA_CLOAKED)? Pri akejkolvek chybe False.

    Pre harnessy: zahalene okno ma `winfo_viewable()` stale True, takze len
    podla Tk by "neviditelna" appka presla kazdou kontrolou."""
    try:
        import ctypes
        h = _window_hwnd(window)
        if not h:
            return False
        stav = ctypes.c_uint(0)
        hr = _dwm().DwmGetWindowAttribute(
            h, _DWMWA_CLOAKED, ctypes.byref(stav), ctypes.sizeof(stav))
        return hr == 0 and stav.value != 0
    except Exception:
        return False


def potlac_dpi_alpha_blik(window):
    """Zabrani "duchu" aj prestavbe okna pri presune medzi monitormi.

    CUSTOMTKINTER pri zmene DPI (aj ked okno len prejde na monitor s inou
    mierkou) stlmi okno na `-alpha 0.15`, prepocita mierku a vrati na 1 -
    aby POCAS prepoctu skryl prestavbu. Lenze pri presune sa to spusta znova
    a vysledok je priesvitny "duch"/blikanie (presne to hlasil hrac).

    Tie dve volania alpha su ale presne HRANICE prepoctu mierky. Namiesto
    stlmenia na 0.15 (duch) na nich ZMRAZIME/ODMRAZIME kreslenie
    (`freeze_repaint`): okno ostane nepriehladne (ziadny duch) a prestavba
    pri prepocte sa neukaze (ziadne blikanie). Poistka `after` odmrazi aj
    keby druhe volanie neprislo (vynimka v CTk), aby okno nikdy neostalo
    zamrznute. Query (`attributes('-alpha')`) a ine atributy prechadzaju."""
    try:
        orig = window.wm_attributes
    except Exception:
        return window

    def _wrap(*args):
        if len(args) >= 2 and str(args[0]) in ("-alpha", "alpha"):
            try:
                a = float(args[1])
            except (TypeError, ValueError):
                return orig(*args)
            if a < 1.0:
                freeze_repaint(window, True)
                try:
                    window.after(160, lambda: freeze_repaint(window, False))
                except Exception:
                    pass
            else:
                freeze_repaint(window, False)
            return          # samotnu alpha nikdy nemenime (ziadny duch)
        return orig(*args)

    window.wm_attributes = _wrap
    window.attributes = _wrap
    return window


# --------------------------------------------------------------------------
# Okno s pevnym rozmerom na monitore: mierka a stred
# --------------------------------------------------------------------------
#
# Ako CTk rata rozmery (overene v customtkinter/.../scaling_tracker.py):
#
#   fyzicky rozmer okna = logicky * DPI monitora * ScalingTracker.window_scaling
#   fyzicky rozmer prvku = logicky * DPI monitora * ScalingTracker.widget_scaling
#
# `window_scaling` a `widget_scaling` su JEDNA hodnota pre celu appku (atribut
# triedy, nie okna) a `ctk.set_*_scaling(x)` ju PREPISE, nenasobi. DPI si CTk
# drzi pre kazde okno zvlast (`window_dpi_scaling_dict`) a kazdych 100 ms
# kontroluje, ci sa okno nepresunulo na monitor s inym DPI.
#
# Zmensit appku teda znamena vynasobit OBE hodnoty tym istym faktorom:
# keby sa zmensilo len okno, obsah navrhnuty na 1180x760 by z neho vytiekol.


def _ctk_tracker():
    """`ScalingTracker` z customtkinter. Samostatna funkcia, aby ju testy
    vedeli nahradit - skutocny tracker je globalny stav celeho procesu."""
    from customtkinter.windows.widgets.scaling.scaling_tracker import ScalingTracker
    return ScalingTracker


def dpi_mierka_monitora(mon):
    """DPI cast mierky CTk na monitore `mon` (bez mierky appky).

    CTk na starych Windows (pred 8.1) DPI nesleduje vobec a nasobi len
    mierkou appky - vtedy je DPI cast 1.0, nech by monitor hlasil cokolvek."""
    try:
        if _ctk_tracker().deactivate_automatic_dpi_awareness:
            return 1.0
    except Exception:
        pass
    return display_mod.dpi_scale(mon)


def zosuladi_dpi_s_monitorom(window, mon):
    """Nastavi CTk mierku okna na DPI monitora `mon` HNED, nie az o 100 ms.

    Tk vytvori okno tam, kam ho da Windows (byva to hlavny monitor), a CTk si
    DPI zapamata odtial. Ked okno hned potom posunieme na monitor s inou
    mierkou, CTk to zisti az pri najblizsej kontrole - po `_build_ui`, teda
    nad viac nez tisickou hotovych widgetov, ktore by vsetky prestaval pred
    hracom. Kym je okno prazdne, je prepocet lacny.

    Ak by okno predsa skoncilo inde, CTk ho opravi sam ako doteraz. Vracia
    True, ked sa mierka zmenila. Nikdy nevyhodi vynimku."""
    try:
        st = _ctk_tracker()
        if st.deactivate_automatic_dpi_awareness:
            return False
        if window not in st.window_dpi_scaling_dict:
            return False
        nova = dpi_mierka_monitora(mon)
        if abs(float(st.window_dpi_scaling_dict[window]) - nova) < 1e-6:
            return False
        st.window_dpi_scaling_dict[window] = nova
        st.update_scaling_callbacks_for_window(window)
        return True
    except Exception:
        return False


def prisposob_mierku_monitoru(width, height, mon):
    """Zmensi celu appku, ak sa okno `width` x `height` (logicke px) nezmesti
    do pracovnej plochy monitora `mon`. Vracia pouzity faktor (1.0 = nic sa
    nezmenilo).

    Volat PRED stavbou UI: CTk pri zmene mierky prestavuje kazdy widget, a
    kym ziadne nie su, nestoji to nic. Faktor sa rata z mierky, ktoru appka
    uz ma, takze druhe volanie nezmensi appku este raz - okno sa uz zmesti.
    Zmena plati pre celu appku (aj dialogy), nie len pre jedno okno."""
    try:
        st = _ctk_tracker()
        okna = float(st.window_scaling or 1.0)
        prvky = float(st.widget_scaling or 1.0)
        faktor = display_mod.window_fit_factor(
            width, height, dpi_mierka_monitora(mon) * okna,
            mon.work_width, mon.work_height)
        if faktor < 1.0:
            st.set_widget_scaling(prvky * faktor)
            st.set_window_scaling(okna * faktor)
        return faktor
    except Exception:
        return 1.0


def vycentrovana_geometria(window, width, height, mon=None):
    """Geometria "SxV+x+y" okna vycentrovaneho v pracovnej ploche monitora.

    Bezramove okno nikto neumiestni (OS ho nespravuje) a CTk v `geometry()`
    nasobi mierkou len SIRKU a VYSKU, nie polohu - stred sa preto rata z
    fyzickeho rozmeru na CIELOVOM monitore (jeho DPI, nie DPI monitora, kde
    okno prave je). `mon=None` = monitor pod kurzorom: tam sa clovek prave
    pozera. Ked sa okno nezmesti, prilepi sa hore (viz
    `display.center_in_work_area`). Pri akejkolvek chybe vrati len rozmer.
    """
    try:
        if mon is None:
            mon = display_mod.monitor_at_cursor(window)
        try:
            okna = float(_ctk_tracker().window_scaling or 1.0)
        except Exception:
            okna = 1.0
        mierka = dpi_mierka_monitora(mon) * okna
        x, y = display_mod.center_in_work_area(
            mon, round(width * mierka), round(height * mierka))
        return f"{width}x{height}+{x}+{y}"
    except Exception:
        return f"{width}x{height}"


def umiestni_pevne_okno(window, width, height, mon=None):
    """Pevne okno appky na obrazovku: monitor, mierka, stred - v tomto poradi.

    1. monitor pod kurzorom (ten isty, na ktorom sa ukaze sprievodca prveho
       spustenia),
    2. CTk mierka okna podla DPI TOHO monitora (`zosuladi_dpi_s_monitorom`),
    3. ak sa okno nezmesti do pracovnej plochy, zmensi sa cela appka
       (`prisposob_mierku_monitoru`),
    4. okno sa vycentruje v pracovnej ploche.

    Kde sa okno zmesti (1080p pri 100 %, 1440p, 4K pri 150 %...), mierka
    ostane presne taka ako doteraz. `minsize`/`maxsize` nastavuje volajuci.
    Vracia (faktor, monitor); monitor je None, ak sa nedal zistit."""
    if mon is None:
        try:
            mon = display_mod.monitor_at_cursor(window)
        except Exception:
            mon = None
    if mon is None:
        window.geometry(f"{width}x{height}")
        return 1.0, None
    zosuladi_dpi_s_monitorom(window, mon)
    faktor = prisposob_mierku_monitoru(width, height, mon)
    window.geometry(vycentrovana_geometria(window, width, height, mon))
    return faktor, mon


def rozmer_dialogu(window, width, height, mon=None):
    """(sirka, vyska, monitor) dialogu v LOGICKYCH px, zmensene tak, aby sa
    cele okno zmestilo do pracovnej plochy monitora `mon` (s okrajom
    `display.WINDOW_FIT_MARGIN_PX`).

    Hlavne okno sa zmesti vdaka zmenseniu celej appky
    (`prisposob_mierku_monitoru`), lenze to sa zastavi na 70 %. Na 1366x768
    pri 125-150 % je dialog 640 px vysoky aj po zmenseni vyssi nez plocha a
    jeho spodok s tlacidlom Zavriet skoncil pod listou uloh - pri okne bez
    ramu, ktore sa neda zmensit tahanim za okraj. Dialog tu preto radsej
    ostane nizsi; obsah ma posuvnik, paticka s tlacidlami ostane vidno.
    Pri akejkolvek chybe vrati rozmer nezmeneny a monitor None."""
    try:
        if mon is None:
            mon = display_mod.monitor_at_cursor(window)
        try:
            okna = float(_ctk_tracker().window_scaling or 1.0)
        except Exception:
            okna = 1.0
        mierka = dpi_mierka_monitora(mon) * okna
        if not mierka > 0:
            mierka = 1.0
        okraj = display_mod.WINDOW_FIT_MARGIN_PX
        max_w = int((mon.work_width - okraj) / mierka)
        max_h = int((mon.work_height - okraj) / mierka)
        return max(1, min(int(width), max_w)), max(1, min(int(height), max_h)), mon
    except Exception:
        return int(width), int(height), None


def umiestni_dialog(top, owner, width, height, min_width=None, min_height=None):
    """Dialog bez ramu (DialogChrome) na stred pracovnej plochy a cely na nej.

    Okno bez ramu OS neumiestni ani nezmensi: bez polohy sa otvaralo v rohu
    obrazovky, a vyssie nez plocha malo tlacidla mimo nej. Rozmer zmensi
    `rozmer_dialogu`, stred rata `vycentrovana_geometria` (ten isty vypocet
    ako hlavne okno a sprievodca). `minsize` nikdy nie je vacsi nez rozmer,
    ktory sa na plochu zmesti - inak by ho Tk natiahol spat cez okraj.
    Vracia (sirka, vyska) v logickych px."""
    w, h, mon = rozmer_dialogu(owner, width, height)
    try:
        top._zanshin_umiestnene = True      # DialogChrome ho uz nepresuva
    except Exception:
        pass
    try:
        if min_width or min_height:
            top.minsize(min(int(min_width or w), w), min(int(min_height or h), h))
        if mon is not None:
            top.geometry(vycentrovana_geometria(owner, w, h, mon))
        else:
            top.geometry(f"{w}x{h}")
    except Exception:
        pass
    return w, h


def vycentruj_podla_obsahu(top, owner=None):
    """Dialog, ktory si velkost urci obsahom (bez pevnej geometrie), posunie
    na stred pracovnej plochy monitora pod kurzorom.

    Bezramove okno bez polohy Tk polozi do laveho horneho rohu - pri dvoch
    monitoroch aj na iny, nez na ktorom clovek prave je. Rozmer sa necha
    taky, aky si obsah vypytal; meni sa len poloha (CTk ju neskaluje)."""
    try:
        top.update_idletasks()
        sirka = max(top.winfo_reqwidth(), top.winfo_width())
        vyska = max(top.winfo_reqheight(), top.winfo_height())
        mon = display_mod.monitor_at_cursor(owner or top)
        x, y = display_mod.center_in_work_area(mon, sirka, vyska)
        top.geometry(f"+{x}+{y}")
    except Exception:
        pass


class Collapsible(ctk.CTkFrame):
    """Panel, ktory sa da zabalit. Zvonka sa sprava ako `Panel` - ma `.body`,
    do ktoreho sa sype obsah, takze sa da za `Panel` priamo vymenit.

    PRECO EXISTUJE: appka mala tri miesta, kde sa nieco rozbaluje (karty
    Sprievodcu, karta hlasky, sekcie nastaveni), a kazde si to pisalo samo.
    Tri implementacie znamenaju tri rozne sirky sipky, tri rozne odsadenia
    a tri miesta, kde sa da zabudnut prepnut sipku spat.

    Zacina ZABALENY. Sekcia, ktora sa otvara sama, nie je zabalena - je to
    len panel s ozdobnou sipkou.
    """

    SIPKA_ZAVRETA = "▸"    # >
    SIPKA_OTVORENA = "▾"   # v

    def __init__(self, master, pal, title, expanded=False, **kw):
        kw.setdefault("fg_color", pal["surface"])
        kw.setdefault("corner_radius", RADIUS_PANEL)
        kw.setdefault("border_width", 1)
        kw.setdefault("border_color", pal["line_soft"])
        super().__init__(master, **kw)
        self.pal = pal
        self._title = title
        self._expanded = bool(expanded)

        self.header = ctk.CTkButton(
            self, text=self._header_text(), anchor="w", height=34,
            corner_radius=RADIUS_PANEL, fg_color="transparent",
            hover_color=pal["surface_alt"], text_color=pal["text"],
            font=ui(13, "bold"), command=self.toggle)
        self.header.pack(fill="x", padx=6, pady=6)

        self.body = ctk.CTkFrame(self, fg_color="transparent")
        if self._expanded:
            self._pack_body()

    def _header_text(self):
        sipka = self.SIPKA_OTVORENA if self._expanded else self.SIPKA_ZAVRETA
        return f"{sipka}   {self._title}"

    def _pack_body(self):
        self.body.pack(fill="both", expand=True, padx=16, pady=(0, 14))

    @property
    def expanded(self):
        return self._expanded

    def toggle(self, _event=None):
        self._expanded = not self._expanded
        if self._expanded:
            self._pack_body()
        else:
            self.body.pack_forget()
        self._apply_header_color()

    def _apply_header_color(self):
        self.header.configure(
            text=self._header_text(),
            text_color=self.pal["accent"] if self._expanded else self.pal["text"])

    def set_pal(self, pal):
        """Prefarbi hlavicku pri zmene temy.

        `theme_recolor.recolor_tree` prepisuje farby podla HODNOTY, lenze
        farba hlavicky sa tu pocita z `self.pal` az v okamihu rozbalenia -
        po prepnuti temy by rozbalena sekcia svietila prizvukom zo starej
        palety. Zvysok obsahu su obycajne CTk widgety, tie zvladne strom sam.
        """
        self.pal = pal
        try:
            self.configure(fg_color=pal["surface"], border_color=pal["line_soft"])
            self.header.configure(hover_color=pal["surface_alt"])
            self._apply_header_color()
        except Exception:
            pass


class SlotIcon(ctk.CTkLabel):
    """Piktogram vizualu (grounding / jaw / release / breath ...) tym istym
    stetcom, ktory kresli hru (`hud_paint.render_slot_icon`).

    Je to OBRAZOK so zapecenou farbou, takze pri zmene temy ho
    `theme_recolor` neprefarbi - `set_pal` ho nakresli znova (vola ho
    `DandurfApp._recolor_ui`). Bez toho by po prepnuti sveta ostali zlate
    ikonky v indigovom okne."""

    def __init__(self, master, pal, name, size=26):
        super().__init__(master, text="", width=size, height=size)
        self._name = name
        self._size = size
        self._photo = None
        self.set_pal(pal)

    def set_pal(self, pal):
        try:
            import hud_paint      # lazy: ui_kit sa importuje aj bez GUI
            img = hud_paint.render_slot_icon(self._name, self._size,
                                             hud_paint.Style(pal))
            self._photo = ctk.CTkImage(light_image=img, dark_image=img,
                                       size=(self._size, self._size))
            self.configure(image=self._photo)
        except Exception:
            pass


def bez_ikony(text):
    """Text bez uvodneho symbolu: "🥾 Tazisko (drep/slide)" -> "Tazisko ...".

    Nazvy vizualov v prekladoch nesu emoji (🥾 💀 🖱️ 🫁). Vedla obrazka,
    ktory appka kresli sama (`hud_paint.render_slot_icon`), boli emoji
    treti styl ikon v tichom rozhrani - a lebka pri celusti najhlasnejsi
    symbol celej appky. Prvy "token" sa odstrani len vtedy, ked v nom nie je
    ziadne pismeno ani cislica, takze text bez emoji ostane cely (aj ked
    preklad emoji raz strati, nazov sa neodreze)."""
    text = str(text or "")
    prvy, medzera, zvysok = text.partition(" ")
    # Len symbol mimo ASCII (emoji, piktogram) - "+ Novy" si svoje plus necha.
    if (medzera and zvysok.strip() and prvy
            and not any(ch.isalnum() for ch in prvy)
            and any(ord(ch) > 0x2000 for ch in prvy)):
        return zvysok.strip()
    return text


def dlzka_text(seconds, preklad=None):
    """Dlzka "45 min" alebo "2 h 05 min" v jazyku appky; pokazena hodnota
    -> "—". Jeden zdroj pre kartu "Dĺžka relácie", detail relacie v
    Historii (`HistoryMixin._fmt_dlzka`) aj koniec osi stopy relacie.

    `preklad` = vlastna funkcia `tr` (HUD v hre pise v jazyku hry,
    `_game_text`); bez nej jazyk appky."""
    try:
        total_min = int(max(0.0, float(seconds or 0.0)) // 60)
    except (TypeError, ValueError, OverflowError):
        return "—"
    if preklad is None:
        from i18n import tr as preklad
    hodiny, minuty = divmod(total_min, 60)
    if hodiny:
        return preklad("dashboard.fmt.h_min", h=hodiny, m=f"{minuty:02d}")
    return preklad("dashboard.fmt.min", n=minuty)


# Od hodiny vyssie sa cas pise ako dlzka ("1 h 15 min"), nie m:ss - "75:12"
# vyzeralo ako cas na hodinkach (0.2.2, audit UX). Ta ista hranica plati pre
# koniec osi stopy relacie (`SessionTrace.OS_DLZKA_OD_S`).
DLZKA_OD_S = 3600


def cas_text(seconds, preklad=None):
    """Cas "m:ss" pod hodinu, od hodiny "1 h 15 min" (`dlzka_text`).

    Pre "Nad hranicou" (Dnes, Historia, panel v hre) a cas relacie nad
    stopou - rovnako ako os stopy. Pokazena hodnota -> "—"."""
    try:
        total = int(max(0.0, float(seconds or 0.0)))
    except (TypeError, ValueError, OverflowError):
        return "—"
    if total >= DLZKA_OD_S:
        return dlzka_text(total, preklad)
    return f"{total // 60}:{total % 60:02d}"


# --------------------------------------------------------------------------
# Datum v jazyku appky (0.2.2 davka 4b)
# --------------------------------------------------------------------------
#
# "%d.%m.%Y" nie je datum v kazdom jazyku: Anglican cita "12.11.2026" ako
# 11. decembra a Japonec ho tak nepise vobec. Kazdy jazyk ma jeden tvar
# (s rokom / bez roku); skratky mesiacov su tie iste ako nad mriezkou
# Pravidelnost (`history.grid_months`) - jeden zdroj. Cas ostava HH:MM,
# nazov exportovaneho suboru ISO (`zanshin-relacie-2026-11-12.csv`).
# {d} den, {dd} den s nulou, {m}/{mm} mesiac, {mes} skratka mesiaca, {r} rok.
_TVAR_DATUMU = {
    "sk": ("{d}. {m}. {r}", "{d}. {m}."),
    "cs": ("{d}. {m}. {r}", "{d}. {m}."),
    "de": ("{dd}.{mm}.{r}", "{dd}.{mm}."),
    "ru": ("{dd}.{mm}.{r}", "{dd}.{mm}"),
    "bg": ("{dd}.{mm}.{r}", "{dd}.{mm}"),
    "en": ("{d} {mes} {r}", "{d} {mes}"),
    "fr": ("{d} {mes} {r}", "{d} {mes}"),
    "es": ("{d} {mes} {r}", "{d} {mes}"),
    "pt": ("{d} {mes} {r}", "{d} {mes}"),
    "ja": ("{r}年{m}月{d}日", "{m}月{d}日"),
    "zh": ("{r}年{m}月{d}日", "{m}月{d}日"),
}
_TVAR_MESIACA = {"ja": "{r}年{m}月", "zh": "{r}年{m}月", "de": "{mes} {r}",
                 "ru": "{mm}.{r}", "bg": "{mm}.{r}"}


def _jazyk_appky():
    try:
        import i18n
        return i18n._lang.get("code", "sk")
    except Exception:
        return "sk"


def _cast_datumu(ts):
    """time.struct_time z casu `ts` (sekundy), alebo None pri zlej hodnote."""
    try:
        return time.localtime(float(ts))
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def _mesiac_skratka(mesiac, jazyk):
    try:
        from i18n import tr_lang
        mena = tr_lang(jazyk, "history.grid_months").split()
        if len(mena) == 12:
            return mena[mesiac - 1]
    except Exception:
        pass
    return str(mesiac)


def _vypln_tvar(tvar, t, jazyk):
    return tvar.format(d=t.tm_mday, dd=f"{t.tm_mday:02d}", m=t.tm_mon,
                       mm=f"{t.tm_mon:02d}", r=t.tm_year,
                       mes=_mesiac_skratka(t.tm_mon, jazyk) if "{mes}" in tvar else "")


def datum_text(ts, rok=True, cas=False, jazyk=None):
    """Datum relacie v jazyku appky: sk "12. 11. 2026", de "12.11.2026",
    en "12 Nov 2026", fr "12 nov. 2026", ja "2026年11月12日".

    `rok=False` - kratky tvar ("12. 11.", "12 Nov", "11月12日"),
    `cas=True` - za datum " HH:MM". Pokazeny cas -> "—"."""
    t = _cast_datumu(ts)
    if t is None:
        return "—"
    jazyk = jazyk or _jazyk_appky()
    tvar = _TVAR_DATUMU.get(jazyk, _TVAR_DATUMU["en"])[0 if rok else 1]
    text = _vypln_tvar(tvar, t, jazyk)
    if cas:
        text += f" {t.tm_hour:02d}:{t.tm_min:02d}"
    return text


def mesiac_text(ts, jazyk=None):
    """Mesiac a rok ("nov 2026", "Nov 2026", "2026年11月") - popisok
    mesacneho stlpca v grafe trendu."""
    t = _cast_datumu(ts)
    if t is None:
        return "—"
    jazyk = jazyk or _jazyk_appky()
    return _vypln_tvar(_TVAR_MESIACA.get(jazyk, "{mes} {r}"), t, jazyk)


# --------------------------------------------------------------------------
# Zalamovanie japonciny a cinstiny (kinsoku, 0.2.2 davka 4b)
# --------------------------------------------------------------------------
#
# Tk zalamuje len na medzere; text bez medzier (ja/zh) zlomi KDEKOLVEK -
# riadok potom zacinal 「。」 alebo 「）」, co je v japonskej sadzbe chyba.
# `zalom_kinsoku` zlomi text sam: riadok nezacne zatvaracim znakom,
# interpunkciou ani malou kanou a neskonci otvaracou zatvorkou (znak sa
# vtedy presunie na dalsi riadok, nikdy nevycnieva - Tk by ho inak zlomil
# znova). Latinske slova v texte sa nedelia.
_KINSOKU_ZACIATOK = frozenset(
    "、。，．・：；？！ー）」』】〕〉》〙〗｝］〟"
    "ぁぃぅぇぉっゃゅょゎゕゖァィゥェォッャュョヮヵヶㇰㇱㇲㇳㇴㇵㇶㇷㇸㇹㇺㇻㇼㇽㇾㇿ々〻"
    "゛゜ゝゞヽヾ〜～…‥%,.!?:;)]}"
    # cinstina dava nazvy do “…” (nie 「…」): zatvaracia ” nesmie zacat
    # riadok, otvaracia “ ho nesmie skoncit (`_KINSOKU_KONIEC`)
    "”’")
_KINSOKU_KONIEC = frozenset("（「『【〔〈《〘〖｛［〝([{“‘")


def _cjk_znak(ch):
    o = ord(ch)
    return (0x3000 <= o <= 0x30FF or 0x31F0 <= o <= 0x31FF or 0x3400 <= o <= 0x9FFF
            or 0xF900 <= o <= 0xFAFF or 0xFF00 <= o <= 0xFFEF)


def _tokeny_zlomu(riadok):
    """Kusy, medzi ktorymi sa smie zlomit: kazdy CJK znak, kazda medzera a
    cele latinske slovo."""
    tokeny, slovo = [], ""
    for ch in riadok:
        if ch == " " or _cjk_znak(ch):
            if slovo:
                tokeny.append(slovo)
                slovo = ""
            tokeny.append(ch)
        else:
            slovo += ch
    if slovo:
        tokeny.append(slovo)
    return tokeny


def zalom_kinsoku(text, sirka, zmeraj):
    """`text` so zlomami riadkov ("\\n") tak, aby ziadny riadok nebol sirsi
    nez `sirka` (v jednotkach funkcie `zmeraj(retazec) -> sirka`) a
    dodrzal kinsoku (viz vyssie). Text bez CJK znakov sa vrati nezmeneny -
    latinku Tk zalamuje na medzerach spravne. Existujuce zlomy ostanu."""
    text = "" if text is None else str(text)
    if not text or not sirka or sirka <= 0 or not any(_cjk_znak(c) for c in text):
        return text
    von = []
    for odsek in text.split("\n"):
        tokeny = _tokeny_zlomu(odsek)
        n, start, i = len(tokeny), 0, 0
        while i < n:
            if i > start and zmeraj("".join(tokeny[start:i + 1]).rstrip()) > sirka:
                zlom = i
                while zlom - start > 1 and (tokeny[zlom][0] in _KINSOKU_ZACIATOK
                                            or tokeny[zlom - 1][-1] in _KINSOKU_KONIEC):
                    zlom -= 1
                von.append("".join(tokeny[start:zlom]).rstrip())
                start = zlom
                while start < n and tokeny[start] == " ":
                    start += 1
                i = start
                continue
            i += 1
        von.append("".join(tokeny[start:]).rstrip())
    return "\n".join(von)


def _merac_pisma(font):
    """`zmeraj(retazec) -> px` pre pismo labelu (tuple alebo CTkFont) v
    LOGICKYCH px - v tych istych ako `wraplength` (CTk nasobi oboje tou
    istou mierkou). Bez Tk (testy) odhad podla velkosti pisma."""
    try:
        if isinstance(font, (tuple, list)):
            family, size = font[0], font[1]
            weight = font[2] if len(font) > 2 else "normal"
        else:
            family, size, weight = font.cget("family"), font.cget("size"), font.cget("weight")
        return tkfont.Font(family=family, size=-abs(int(size)), weight=weight).measure
    except Exception:
        try:
            velkost = float(font[1])
        except Exception:
            velkost = 12.0

        def zmeraj(s):
            return sum(velkost if _cjk_znak(c) else velkost * 0.55 for c in s)
        return zmeraj


def _kinsoku_labelu(label):
    """CTkLabel s `wraplength` v japoncine/cinstine ukaze text zlomeny
    podla kinsoku (`zalom_kinsoku`), 2 % pod `wraplength`, aby ho Tk
    nezlomil znova.

    Zlomy dostane len vnutorny tk.Label - `_text` CTkLabelu ostava povodny,
    takze `cget("text")` vrati presne to, co volajuci poslal. Ine jazyky,
    label bez `wraplength` ci s `textvariable` sa nemenia. Nikdy nevyhodi
    vynimku."""
    try:
        if not _jazyk_pisma():
            return
        text, wrap = getattr(label, "_text", None), getattr(label, "_wraplength", 0)
        if not isinstance(text, str) or not text or not wrap:
            return
        zlomeny = zalom_kinsoku(text, float(wrap) * 0.98, _merac_pisma(label._font))
        if zlomeny != text:
            label._label.configure(text=zlomeny)
    except Exception:
        pass


def zapni_kinsoku_v_labeloch(trieda=None):
    """Kazdy CTkLabel s `wraplength` zlomi ja/zh text podla kinsoku - pri
    stavbe aj pri `configure(text= / wraplength= / font=)`.

    Labelov so `wraplength` je v appke vyse sto (Nastavenia, dialogy,
    Sprievodca, Historia); upravit kazdy zvlast by bolo sto miest, kde sa
    na to da zabudnut. Preto jeden hacik na triede, raz pri importe
    `ui_kit` (opakovane volanie nic nespravi). Latinku a cyriliku necha
    tak - tie Tk zalamuje na medzerach spravne."""
    trieda = trieda or ctk.CTkLabel
    if getattr(trieda, "_zanshin_kinsoku", False):
        return
    povodny_init, povodny_configure = trieda.__init__, trieda.configure

    def __init__(self, *args, **kwargs):
        povodny_init(self, *args, **kwargs)
        _kinsoku_labelu(self)

    def configure(self, require_redraw=False, **kwargs):
        zmena = bool(kwargs.keys() & {"text", "wraplength", "font"})
        vysledok = povodny_configure(self, require_redraw=require_redraw, **kwargs)
        if zmena:
            _kinsoku_labelu(self)
        return vysledok

    trieda.__init__ = __init__
    trieda.configure = configure
    trieda._zanshin_kinsoku = True


try:
    zapni_kinsoku_v_labeloch()
except Exception:              # pragma: no cover - atrapa ctk bez CTkLabel
    pass


class SettingRow(ctk.CTkFrame):
    """Riadok nastavenia: nazov, vysvetlenie pod nim, ovladac vpravo.

    Vysvetlenie je sucastou riadku, nie tooltip - nastavenie, ktore treba
    vysvetlit az po najdeni otaznika, je nastavenie, ktore nikto nezapne.

    `icon` (volitelne) ide do stlpca PEVNEJ sirky pred nazvom - emoji maju
    kazde inu sirku, takze nazov v texte "🖱️ Uvolnenie" zacinal inde nez
    "🥾 Tazisko" (nahlasene ako "prepinac mimo osi"). Rovnaky princip ako
    bocne menu (_NavRow).

    `note` (volitelne) je drobna tichsia vysvetlivka pod CELYM riadkom -
    pod nazvom aj pod ovladacom, este nad deliacou ciarou. Je pre vetu,
    ktora patri k vyberu, ale nie je jeho popisom (napr. veta o prekladoch
    pod vyberom jazyka).
    """

    ICON_W = 40      # aj sirsie emoji (🖱️ s variacnym selektorom) sa zmesti

    def __init__(self, master, pal, title, sub=None, wrap=430, icon=None,
                 note=None, note_wrap=560, icon_slot=None):
        super().__init__(master, fg_color="transparent")
        self.pack(fill="x")
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="x", pady=9)

        self.control = ctk.CTkFrame(inner, fg_color="transparent")
        self.control.pack(side="right", padx=(14, 0))

        # `icon_slot` (meno vizualu) ma prednost pred textovou ikonou:
        # obrazok z `hud_paint` je to, co hrac uvidi v hre - emoji nie.
        if icon_slot:
            ikona_wrap = ctk.CTkFrame(inner, fg_color="transparent",
                                      width=self.ICON_W, height=26)
            ikona_wrap.pack(side="left")
            ikona_wrap.pack_propagate(False)
            self.icon = SlotIcon(ikona_wrap, pal, icon_slot, size=26)
            self.icon.pack(side="left")
        elif icon:
            self.icon = ctk.CTkLabel(inner, text=icon, width=self.ICON_W, anchor="w",
                                     font=ui(13), text_color=pal["text"])
            self.icon.pack(side="left")
        text_col = ctk.CTkFrame(inner, fg_color="transparent")
        text_col.pack(side="left", fill="x", expand=True)
        # Stlpec textu je verejny (0.2.2 davka 4b): stav, ktory k riadku
        # patri (priprava hlasu pod "Zdrojom hlasu"), ide POD vysvetlenie -
        # este nad deliacu linku riadku, nie pod nu do dalsieho riadku.
        self.text_col = text_col
        self.title_label = ctk.CTkLabel(text_col, text=title, font=ui(13),
                                        text_color=pal["text"], anchor="w", justify="left")
        self.title_label.pack(fill="x")
        # Vetu si drzime, aby sa dala prepisat, ked sa zmeni to, co
        # popisuje (ukazka zvuku ide za stylom hlasky).
        self.sub_label = None
        if sub:
            # Vysvetlenie je OBSAH (preco a co to robi), nie dekoracia -
            # preto `text_dim` (5,75:1), nie `text_faint`. V ja/zh ho zlomi
            # kinsoku (`zapni_kinsoku_v_labeloch`) - Tk by zacal riadok 「。」.
            self.sub_label = ctk.CTkLabel(
                text_col, text=sub, font=ui(11), text_color=pal["text_dim"],
                anchor="w", justify="left", wraplength=wrap)
            self.sub_label.pack(fill="x", pady=(2, 0))

        self.note_label = None
        if note:
            self.note_label = ctk.CTkLabel(
                self, text=note, font=ui(10), text_color=pal["text_faint"],
                anchor="w", justify="left", wraplength=note_wrap)
            self.note_label.pack(fill="x", pady=(0, 9))

        # Deliaca linka je MEDZI riadkami, nie pod poslednym (0.2.2, audit
        # UX, davka 4): pod poslednym riadkom panela lezala ~13 px nad jeho
        # ramom - dve ciary tesne nad sebou. Ci je riadok posledny, sa vie
        # az ked je cely panel postaveny. Samotne `after_idle` nestacilo:
        # rozbalovacka v DALSOM riadku si pri stavbe vola `update_idletasks`,
        # takze sa kontrola spustila skor, nez dalsi riadok existoval, a linky
        # zmizli aj medzi riadkami. Preto sa to prepocita pri kazdej zmene
        # rozmeru rodica (pribudol riadok = rodic narastie) - `obnov_linky`.
        self.deliaca_linka = linka(self, pal)
        self.deliaca_linka.pack(fill="x")
        self._linka_vidno = True
        master = self.master
        try:
            if not getattr(master, "_zanshin_linky_riadkov", False):
                master._zanshin_linky_riadkov = True
                # `tk.Misc.bind` priamo na ramec (CTk `bind` by ho dal na
                # vnutorny canvas) a "+" - CTk tam ma svoj <Configure>.
                tk.Misc.bind(master, "<Configure>",
                             lambda _e, m=master: SettingRow.obnov_linky(m), "+")
            self.after_idle(lambda m=master: SettingRow.obnov_linky(m))
        except Exception:
            pass

    @staticmethod
    def obnov_linky(master):
        """Linka pod kazdym riadkom nastavenia v `master` okrem posledneho.

        Posledny riadok svojho rodica nema linku pod sebou. Riadok, za
        ktorym este nieco nasleduje (dalsi riadok, tlacidlo, veta), ju ma -
        oddeluje ho od toho, co je pod nim. Vola sa opakovane (kazdy
        <Configure> rodica); meni len to, co sa zmenilo. Nikdy nevyhodi
        vynimku."""
        try:
            susedia = master.pack_slaves()
        except Exception:
            return
        for i, riadok in enumerate(susedia):
            if not isinstance(riadok, SettingRow):
                continue
            riadok._nastav_linku(i < len(susedia) - 1)

    def _nastav_linku(self, vidno):
        try:
            if vidno and not self._linka_vidno:
                self.deliaca_linka.pack(fill="x")
            elif not vidno and self._linka_vidno:
                self.deliaca_linka.pack_forget()
            self._linka_vidno = bool(vidno)
        except Exception:
            pass

    def skry_linku_ak_je_posledny(self):
        """Prepocita linky vsetkych riadkov u rodica (`obnov_linky`)."""
        SettingRow.obnov_linky(self.master)


def chip(master, pal, text, command=None, pressed=False, width=0):
    """Ploche tlacidlo s ramom - zakladny ovladac celeho rozhrania."""
    btn = ctk.CTkButton(
        master, text=text, command=command, height=28,
        corner_radius=RADIUS_CONTROL, border_width=1,
        border_color=pal["accent"] if pressed else pal["border"],
        fg_color=pal["accent2"] if pressed else "transparent",
        hover_color=pal["surface_alt"],
        text_color=pal["text"] if pressed else pal["text_dim"],
        font=ui(12))
    if width:
        btn.configure(width=width)
    return btn


# --------------------------------------------------------------------------
# Prazdny stav
# --------------------------------------------------------------------------

class EmptyState(ctk.CTkFrame):
    """Prazdny stav: JEDNA veta a nanajvys JEDNA akcia (0.2.2 davka 4).

    Audit UX: bez dat appka ukazovala pomlcky, "0 %" a prazdne grafy - to
    vyzeralo ako meranie, nie ako "zatial nic". Jedina vyzva, ktora mala
    zmysel (sparovat hodinky), bola navyse az pod okrajom okna. Prazdny stav
    ma povedat, co sa tu objavi a co pre to spravit - nic viac.

    Akcia je `button(kind="secondary")`, nie `chip()`: chip ostava pre
    externe odkazy (pravidla dizajnu v audite). Druh ide zmenit cez `kind`.
    Veta je v `text_dim` (>= 4,5:1), lebo je to obsah, nie dekoracia.
    Farby su z palety, takze prefarbenie temy (`theme_recolor`) ich zvladne
    bez vlastneho `set_pal`.
    """

    def __init__(self, master, pal, text, action=None, command=None,
                 kind="secondary", wraplength=440, anchor="center", pady=(8, 8)):
        super().__init__(master, fg_color="transparent")
        self.pal = pal
        stred = anchor == "center"
        self.label = ctk.CTkLabel(self, text=text, font=ui(12),
                                  text_color=pal["text_dim"], wraplength=wraplength,
                                  justify="center" if stred else "left",
                                  anchor="center" if stred else "w")
        self.action = None
        if action and command is not None:
            self._veta_pack = dict(anchor=anchor, pady=(pady[0], 0))
            self.label.pack(**self._veta_pack)
            self.action = button(self, pal, action, command=command, kind=kind)
            self.action.pack(anchor=anchor, pady=(10, pady[1]))
        else:
            self._veta_pack = dict(anchor=anchor, pady=pady)
            self.label.pack(**self._veta_pack)

    def set_text(self, text):
        try:
            self.label.configure(text=text)
        except Exception:
            pass

    def ukaz_vetu(self, ukaz):
        """Schova / vrati vetu, akcia ostava (0.2.2 davka 4b).

        Pri obsadenom porte tepu hovori o probleme pas aj hlavicka panela -
        "Ked sparujes hodinky..." pod tym by bola druha, ina sprava (a navyse
        nepravdiva: hodinky su v poriadku). Nikdy nevyhodi vynimku."""
        try:
            vidno = bool(self.label.winfo_manager())
            if ukaz and not vidno:
                if self.action is not None and self.action.winfo_manager():
                    self.label.pack(before=self.action, **self._veta_pack)
                else:
                    self.label.pack(**self._veta_pack)
            elif not ukaz and vidno:
                self.label.pack_forget()
        except Exception:
            pass


# --------------------------------------------------------------------------
# Keycap
# --------------------------------------------------------------------------

class Keycap(ctk.CTkFrame):
    """Spustac vyzera ako kláves, lebo to kláves je.

    Sirka nesie typ vstupu (kláves / mys / ovladac) - mapa sa da precitat
    bez toho, aby k nej ktokolvek pisal stitky. Spodna hrana je druhy,
    tmavsi ram pod plochou; `border-bottom` CTkFrame nepozna.
    """

    FACE_H = 42
    LIP = 3

    def __init__(self, master, pal, text, width=48, command=None):
        super().__init__(master, fg_color=pal["keycap_edge"], corner_radius=RADIUS_CONTROL,
                         width=width, height=self.FACE_H + self.LIP)
        self.pack_propagate(False)
        self.grid_propagate(False)
        self.face = ctk.CTkButton(
            self, text=text, command=command, corner_radius=RADIUS_CONTROL,
            height=self.FACE_H, width=width,
            fg_color=pal["keycap_face"], hover_color=pal["surface_alt"],
            border_width=1, border_color=pal["keycap_edge"],
            text_color=pal["keycap_text"],
            font=mono(13 if len(str(text)) <= 3 else 10))
        self.face.pack(fill="x", side="top")

    def set_text(self, text):
        try:
            self.face.configure(text=text,
                                font=mono(13 if len(str(text)) <= 3 else 10))
        except Exception:
            pass

    def set_pal(self, pal):
        """Prefarbi klavesu pri zmene temy.

        Nutne zvlast: `theme_recolor` mapuje farby podla HODNOTY a v teme
        Sumi ma `keycap_text` tu istu hodnotu ako `accent` (#d9b868), kym
        v Modern sa rozchadzaju (#8FB0E8 vs #5C86C9). Mechanicka mapa by
        teda klavese dala akcent namiesto jej vlastnej farby. Tu ju
        nastavime z tokenu, takze je to vzdy spravne.
        """
        try:
            self.configure(fg_color=pal["keycap_edge"])
            self.face.configure(fg_color=pal["keycap_face"],
                                hover_color=pal["surface_alt"],
                                border_color=pal["keycap_edge"],
                                text_color=pal["keycap_text"])
        except Exception:
            pass


def set_label_text(widget, text):
    """Prepise popisok widgetu bez ohladu na to, ci je to Keycap alebo
    obycajny CTkButton/CTkLabel.

    Existuje preto, lebo Keycap je zlozeny CTkFrame a `.configure(text=)`
    na nom vyhodi ValueError. Presne na tom padal rebind spustaca: jedno
    volanie sa opravilo na set_text(), druhe (app.begin_rebind) ostalo
    a padalo pri kazdom kliknuti na klaves. Volajuci teraz nemusi vediet,
    ktory z tych dvoch widgetov prave drzi."""
    setter = getattr(widget, "set_text", None)
    if setter is not None:
        setter(text)
    else:
        widget.configure(text=text)


# --------------------------------------------------------------------------
# Kamae - dychajuci pas
# --------------------------------------------------------------------------

class KamaeBar(ctk.CTkFrame):
    """Hlavny vypinac na stranke Dnes - a jediny pohyblivy prvok v okne.

    Dycha v rovnakom rytme ako dychovy kruh v hre (5 s nadych, 5 s vydych) a
    ked je appka zastavena, stoji. Stav sa necita z odznaku ani z farby
    textu, ale z toho, ci sa rozhranie hybe.

    JEDNO TLACIDLO S TEXTOM (0.2.2 davka 4, audit UX). Do 0.2.2 tu bol
    34 px kruh s ▶, nadpis "Hlavny vypinac" a pod nim navod "Klikni ▶
    vlavo" - ovladac, ktory potreboval navod. Teraz je vlavo jedno tlacidlo
    "▶ Spustit sledovanie" / "■ Zastavit sledovanie" (texty `dock.start` /
    `dock.stop`, tie iste slova ako v ponuke ikony v liste) a vedla neho
    len ticha veta, preco pas dycha. Zastavena appka ma tlacidlo `primary`
    (vypln `accent`), sledujuca `secondary` (ram `control_border`) - tie
    iste farby ako `button(kind=...)`. Stav prepina kazda cesta rovnako
    (`DandurfApp._apply_listening_visuals` -> `set_live`): tlacidlo, ponuka
    v liste aj spustenie hrou.

    KLAVESNICA: platno sa da zamerat (Tab) a Enter alebo medzernik prepnu
    to iste, co klik. Zameranie ukaze prstenec okolo tlacidla - klik mysou
    platno nezameria, takze prstenec nevyskoci pri kazdom kliknuti.

    PRECO KRESLENE, NIE CTkButton: plat pod tlacidlom pocas sledovania dycha
    - kazdych 90 ms ma inu vypln. CTkButton ma rohy vo farbe pozadia, ktora
    sa nastavi raz, takze v dychajucom plate by sedel ostrovcek inej farby.
    Tlacidlo je preto obrazok s priehladnymi rohmi (vyhladeny cez PIL;
    bez PIL obycajny polygon) a text je text platna.

    Animacia sa zastavi vzdy, ked okno nie je viditelne (minimalizovane do
    listy) - appka bezi na pozadi celu hraciu seansu a prekreslovat pritom
    nieco, na co sa nikto nepozera, by bolo plytvanie.
    """

    # 92 -> 64 (0.2.2 davka 4): pas uz nenesie dva riadky textu (nadpis a
    # navod), len tlacidlo a jednu vetu. Okno ma pevnu vysku a kazdy riadok
    # pasu chyba stranke pod nim.
    HEIGHT = 64
    TICK_MS = 90
    # Tlacidlo vlavo v pase. Do verzie 2.1 bola na tomto mieste len farebna
    # bodka a prepinal KLIK KAMKOLVEK do pasu - o com sa hrac dozvedel len
    # zo sprievodcu. Prepina UZ LEN tlacidlo: jeden zamer, jedno miesto.
    BTN_X = 14
    BTN_SIZE = 36               # vyska tlacidla (logicke px), audit: 36 px
    BTN_PAD = 18                # okraj textu vnutri tlacidla
    BTN_MIN_W = 150
    FOCUS_GAP = 3               # medzera medzi tlacidlom a prstencom zamerania
    FOCUS_W = 2                 # hrubka prstenca zamerania
    HALF_CYCLE_MS = 5000.0      # rovnaka faza ako _SlotOverlay.HALF_CYCLE_S

    def __init__(self, master, pal, on_toggle, start_label="", stop_label="",
                 hint=""):
        super().__init__(master, fg_color="transparent", height=self.HEIGHT)
        self.pack_propagate(False)
        self.pal = pal
        self.on_toggle = on_toggle
        self.live = False
        self._phase = 0.0
        self._job = None
        self._start_label = start_label
        self._stop_label = stop_label
        self._hint = hint
        # Stav tlacidla: kurzor nad nim / zamerane klavesnicou. Obrazky
        # tlacidla su v cache podla (rozmer, druh, stav, farby) - pri tiku
        # dychu sa nemenia, vymienaju sa len pri zmene stavu.
        self._hover_btn = False
        self._focus = False
        self._btn_imgs = {}
        self._btn_stav = None
        self._btn_rect = None     # (x0, y0, x1, y1) vo FYZICKYCH px platna
        # Znovupouzitie prvkov platna namiesto delete("all")+znovu-vytvorenie
        # kazdy tik (90 ms). `_it` su id-cka poloziek, `_it_sig` je (sirka, vyska,
        # mierka), pre ktore su postavene - pri zmene sa postavia nanovo, inak
        # sa len upravia (coords/itemconfigure). Rovnaky vzor ako Dnes stred.
        self._it = None
        self._it_sig = None       # (w, h, mierka), pre ktore su polozky postavene
        self._last_mierka = 1.0

        # `takefocus=1`: na hlavny vypinac sa da dostat klavesnicou (Tab).
        self.canvas = tk.Canvas(self, height=self.HEIGHT, bg=pal["bg"],
                                highlightthickness=0, bd=0, takefocus=1)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Button-1>", self._clicked)
        self.canvas.bind("<Motion>", self._hover)
        self.canvas.bind("<Leave>", self._leave)
        self.canvas.bind("<Configure>", lambda _e: self._redraw())
        self.canvas.bind("<FocusIn>", lambda _e: self._set_focus(True))
        self.canvas.bind("<FocusOut>", lambda _e: self._set_focus(False))
        for klaves in ("<Return>", "<KP_Enter>", "<space>"):
            self.canvas.bind(klaves, self._key)

    def _set_scaling(self, *args, **kwargs):
        """Prekresli aj pri zmene DPI (presun okna na monitor s inou mierkou).

        `<Configure>` sa spusti len ked sa zmeni FYZICKA velkost platna. Dva
        monitory s rovnakou sirkou v px ale inym DPI: pri presune sa zmeni
        mierka (a velkost pisma), ale platno ostane rovnako velke - Configure
        sa nespusti a text ostane zalomeny postaru (na stare `width=`). CTk sem
        posle novu mierku, tak pri tom rovno prekreslime na spravnu sirku."""
        try:
            super()._set_scaling(*args, **kwargs)
        except Exception:
            pass
        try:
            self._it = None      # nova mierka -> polozky nanovo (font/zalomenie)
            self._redraw()
        except Exception:
            pass

    # ---- verejne ----

    def set_live(self, live):
        live = bool(live)
        # Fazu nulujeme LEN pri skutocnej zmene stavu. `set_live` sa vola
        # aj pri prestavbe okna (zmena temy/jazyka) s tou istou hodnotou a
        # vtedy sa dych odsekaval do nuly - navyse odteraz na nom visi aj
        # znacka (enso cita `phase()`), takze by poskocili obe naraz.
        if live != self.live:
            self._phase = 0.0
        self.live = live
        self._redraw()
        self._schedule()

    def set_texts(self, start_label, stop_label, hint=""):
        """Texty tlacidla (zastavene / sleduje) a ticha veta vedla neho.

        Sirka tlacidla sa rata z DLHSIEHO z dvoch textov, aby pri prepnuti
        neposkocilo - preto sa pri zmene textu polozky postavia nanovo. Vola
        sa casto (kazda vzorka tepu prepisuje stav na Dnes), takze rovnake
        texty nerobia nic."""
        texty = (start_label, stop_label, hint)
        if texty == (self._start_label, self._stop_label, self._hint):
            return
        self._start_label, self._stop_label, self._hint = texty
        self._it = None
        self._redraw()

    def button_label(self):
        """Text, ktory tlacidlo prave ukazuje (pre testy a sprievodcu)."""
        return self._stop_label if self.live else self._start_label

    def set_pal(self, pal):
        """Prekresli pas v novej teme.

        Bez tejto metody si pas drzal paletu z chvile, kedy vznikol.
        `theme_recolor.recolor_tree` prepisuje len OPTIONS widgetov, cize
        pozadie plátna sa zmenilo, ale plát, dychova linka, bodka aj text
        sa kreslia z `self.pal` a ostavali v starej teme - po prepnuti zo
        Sumi na Aizome sedel hnedy plat so zlatou linkou v indigovom okne.

        Nechytil to nikto: `PalCanvas` ma `set_pal` a je v prehladavanom
        zozname v `_recolor_ui`, ale `KamaeBar` je holy `tk.Canvas` a v tom
        zozname nebol. `theme_recolor.find_theme_colored` je presne na toto,
        ale nevola ju nic.
        """
        self.pal = pal
        # obrazky tlacidla maju farby zapecene - stara tema do novej nepatri
        self._btn_imgs = {}
        self._btn_stav = None
        try:
            self.canvas.configure(bg=pal["bg"])
        except Exception:
            pass
        self._redraw()

    # POZN: tu bolo `set_metrics([(hodnota, popisok), ...])` - tri cisla
    # vpravo v pase: dlzka relacie, pocet pripomienok, tep. Odstranene
    # preto, ze dlzka aj pocet stoja o kusok vedla v pravom paneli stranky
    # Dnes a pas ich len opakoval. Pas ma niest STAV, nie skore - to je
    # cely dovod, preco je v nom spinac a preco dycha.
    #
    # TEP tym z ostatnych stranok zmizol uplne (v pravom paneli je len na
    # Dnes). Je to vedomy ustupok za tichsi pas, nie prehliadnutie.

    def phase(self):
        """Faza dychu 0..1 - VEREJNY rytmus appky.

        `KamaeBar` je jediny pohyblivy prvok hlavicky a jeho dychova linka
        na spodnej hrane udava tempo. Znacka (enso v bocnom paneli) si ju
        cita odtialto, takze oba dychaju NARAZ a v jednom rytme - keby si
        kazdy pocital vlastnu fazu, mali by rovnaku periodu, ale postupne
        by sa rozisli a v okne by sa hybali dve veci proti sebe.
        """
        return self._phase if self.live else 0.0

    def stop(self):
        if self._job is not None:
            try:
                self.after_cancel(self._job)
            except Exception:
                pass
            self._job = None

    # ---- vnutro ----

    def _v_spinaci(self, event):
        """Je klik v tlacidle? Suradnice udalosti su FYZICKE px - obdlznik
        tlacidla sa preto pamata z kreslenia (`_btn_rect`, uz skalovany
        mierkou). Kym este nie je nakreslene, odhad z konstant a realnej
        vysky platna - inak by klik na 150 % netrafil tam, kde tlacidlo je."""
        rect = self._btn_rect
        if rect is None:
            m = self._last_mierka or 1.0
            bs = self.BTN_SIZE * m
            bx = self.BTN_X * m
            try:
                h = int(self.canvas.winfo_height())
            except Exception:
                h = int(self.HEIGHT * m)
            by = (h - bs) / 2.0
            rect = (bx, by, bx + self.BTN_MIN_W * m, by + bs)
        x0, y0, x1, y1 = rect
        return x0 <= event.x <= x1 and y0 <= event.y <= y1

    def _clicked(self, event):
        if self._v_spinaci(event) and callable(self.on_toggle):
            self.on_toggle()

    def _key(self, _event=None):
        """Enter / medzernik na zameranom pase = klik na tlacidlo."""
        if callable(self.on_toggle):
            self.on_toggle()
        return "break"

    def _hover(self, event):
        """Ruka a zvyraznenie len nad tlacidlom. Kurzor je jediny nahlad,
        ktory hrac dostane pred klikom - keby bola ruka nad celym pasom,
        slubovala by akciu, ktora sa uz nikde inde nestane."""
        nad = self._v_spinaci(event)
        try:
            self.canvas.configure(cursor="hand2" if nad else "")
        except Exception:
            pass
        if nad != self._hover_btn:
            self._hover_btn = nad
            self._redraw()

    def _leave(self, _event=None):
        if self._hover_btn:
            self._hover_btn = False
            self._redraw()

    def _set_focus(self, zamerane):
        zamerane = bool(zamerane)
        if zamerane != self._focus:
            self._focus = zamerane
            self._redraw()

    def _schedule(self):
        self.stop()
        if not self.live:
            return
        self._job = self.after(self.TICK_MS, self._tick)

    def _tick(self):
        self._job = None
        if not self.live:
            return
        try:
            visible = bool(self.winfo_viewable())
        except Exception:
            visible = False
        if visible:
            self._phase = (self._phase + self.TICK_MS / (self.HALF_CYCLE_MS * 2)) % 1.0
            self._redraw()
        self._schedule()

    def _breath(self):
        """0..1 - plynuly nadych a vydych, spomaleny na koncoch."""
        return 0.5 - 0.5 * math.cos(2 * math.pi * self._phase)

    def _redraw(self):
        try:
            w = int(self.canvas.winfo_width())
            h = int(self.canvas.winfo_height())
        except Exception:
            return
        if w < 40 or h < 10:
            return
        # DPI: platno je obycajny tk.Canvas, takze mierku si dorobime sami -
        # inak sa na 150 % displeji kreslilo do hornych 92 px z ~138 px a pod
        # pasom ostavala tmava diera (+ spinac a text boli primale a nalavo).
        try:
            mierka = float(ctk.ScalingTracker.get_widget_scaling(self)) or 1.0
        except Exception:
            mierka = 1.0
        self._last_mierka = mierka
        sig = (w, h, round(mierka, 2))
        if self._it is None or self._it_sig != sig:
            self._build_items(w, h, mierka)
            self._it_sig = sig
        self._update_items(w, h, mierka, self._breath() if self.live else 0.0)

    def _cvfont(self, size, weight="normal"):
        """Font pre kreslenie na Canvas vo FYZICKYCH px (zaporny size = px,
        ktore `tk scaling` uz nenasobi) - rovnaky trik ako Dnes stred."""
        return (ui(size)[0], -max(1, int(round(size * self._last_mierka))), weight)

    def _build_items(self, w, h, m):
        """Postavi prvky platna RAZ pre danu (sirku, vysku, mierku); pri kazdom
        tiku sa uz len upravuju (`_update_items`) - ziadne delete("all") ani
        znovu-vytvorenie, takze pas nebliká ani na buildoch Tk bez dvojiteho
        bufferu. `w`/`h` su FYZICKE px platna; logicke konstanty (tlacidlo,
        medzery) skalujeme mierkou `m`, aby na 150 % pas vyplnili proporcne."""
        c = self.canvas
        c.delete("all")
        it = {"glow": []}
        it["plate"] = round_rect(c, 1, 1, w - 1, h - 1, int(round(7 * m)),
                                 fill="", outline="")
        # NAPLNAJUCI SA LESK - pevny bazen 22 obdlznikov od stredu do bokov;
        # ktore su vidno rozhoduje `state` pri tiku (nemenny pocet prvkov).
        seg = 22
        for i in range(seg):
            x0 = 2 + (w - 4) * i / seg
            x1 = 2 + (w - 4) * (i + 1) / seg
            it["glow"].append(c.create_rectangle(x0, 2, x1, h - 2, fill="",
                                                 outline="", state="hidden"))
        it["line"] = c.create_line(0, h - 3, 0, h - 3, width=max(1, int(round(2 * m))),
                                   capstyle="round", state="hidden")
        # TLACIDLO. Sirka zo sirsieho z dvoch textov - pri prepnuti
        # Spustit <-> Zastavit nesmie poskocit ani tlacidlo, ani veta vedla.
        pismo = self._cvfont(13, "bold")
        try:
            meradlo = tkfont.Font(family=pismo[0], size=pismo[1], weight=pismo[2])
            sirka_textu = max(meradlo.measure(t) for t in
                              (self._start_label, self._stop_label, ""))
        except Exception:
            sirka_textu = int(max(len(self._start_label), len(self._stop_label)) * 8 * m)
        bw = int(round(max(self.BTN_MIN_W * m, sirka_textu + 2 * self.BTN_PAD * m)))
        bh = int(round(self.BTN_SIZE * m))
        bx = int(round(self.BTN_X * m))
        by = int((h - bh) / 2)
        self._btn_rect = (bx, by, bx + bw, by + bh)
        okraj = self._btn_okraj(m)
        it["btn_img"] = c.create_image(bx - okraj, by - okraj, anchor="nw")
        it["btn_poly"] = round_rect(c, bx, by, bx + bw, by + bh,
                                    int(round(RADIUS_CONTROL * m)), fill="",
                                    outline="", state="hidden")
        it["btn_text"] = c.create_text(bx + bw / 2.0, by + bh / 2.0, text="",
                                       anchor="center", font=pismo)
        # TICHA VETA vedla tlacidla - preco pas dycha. Ked sa nezmesti
        # (uzke okno, dlhy preklad tlacidla), radsej ziadna nez orezana.
        tx = bx + bw + 16 * m
        sirka = int(w - tx - 16 * m)
        it["hint"] = c.create_text(tx, h / 2.0, text=self._hint if sirka > 80 * m else "",
                                   anchor="w", font=self._cvfont(12),
                                   width=max(1, sirka))
        self._it = it
        self._btn_stav = None       # nove polozky -> tlacidlo nakreslit znova

    def _btn_okraj(self, m):
        """O kolko je obrazok tlacidla vacsi nez tlacidlo (miesto na prstenec
        zamerania), vo fyzickych px."""
        return int(math.ceil((self.FOCUS_GAP + self.FOCUS_W) * m))

    def _btn_obrazok(self, bw, bh, m, vypln, ram, prstenec):
        """Vyhladene tlacidlo (a prstenec zamerania) ako obrazok s priehladnymi
        rohmi, alebo None bez PIL. Kresli sa 4x vacsie a zmensi - Tk polygon
        na Windows hrany nevyhladzuje. Zmensuje sa v predvynasobenej alfe
        ("RGBa"), inak by priehladne pixely do hrany primiesali ciernu."""
        kluc = (bw, bh, round(m, 2), vypln, ram, prstenec)
        obr = self._btn_imgs.get(kluc)
        if obr is not None:
            return obr
        try:
            from PIL import Image, ImageDraw, ImageTk
        except Exception:
            return None
        try:
            ss = 4
            okraj = self._btn_okraj(m)
            sirka, vyska = bw + 2 * okraj, bh + 2 * okraj
            img = Image.new("RGBA", (sirka * ss, vyska * ss), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            r = RADIUS_CONTROL * m
            if prstenec:
                hr = (self.FOCUS_GAP + self.FOCUS_W) * m
                d.rounded_rectangle(
                    [(okraj - hr) * ss, (okraj - hr) * ss,
                     (okraj + bw + hr) * ss - 1, (okraj + bh + hr) * ss - 1],
                    radius=(r + hr) * ss, outline=prstenec,
                    width=max(1, int(round(self.FOCUS_W * m * ss))))
            d.rounded_rectangle(
                [okraj * ss, okraj * ss, (okraj + bw) * ss - 1, (okraj + bh) * ss - 1],
                radius=r * ss, fill=vypln, outline=ram,
                width=max(1, int(round(m * ss))) if ram else 0)
            img = img.convert("RGBa").resize((sirka, vyska), Image.LANCZOS).convert("RGBA")
            obr = ImageTk.PhotoImage(img, master=self.canvas)
        except Exception:
            return None
        if len(self._btn_imgs) > 24:
            self._btn_imgs = {}
        self._btn_imgs[kluc] = obr
        return obr

    def _kresli_tlacidlo(self, druh, m):
        """Prekresli tlacidlo pre `druh` ("primary" zastavene / "secondary"
        sleduje), kurzor nad nim a zameranie. Farby su tie iste ako pri
        `button(kind=...)`: primary = vypln `accent` a text `bg`, secondary =
        ram `control_border` (>= 3:1) a text `text`."""
        c, it, pal = self.canvas, self._it, self.pal
        x0, y0, x1, y1 = self._btn_rect
        if druh == "primary":
            vypln = pal["accent_hover"] if self._hover_btn else pal["accent"]
            ram, farba_textu = None, pal["bg"]
        else:
            vypln = pal["surface_alt"] if self._hover_btn else None
            ram, farba_textu = pal["control_border"], pal["text"]
        prstenec = pal["accent_hover"] if self._focus else None
        obr = self._btn_obrazok(x1 - x0, y1 - y0, m, vypln, ram, prstenec)
        if obr is not None:
            c.itemconfigure(it["btn_img"], image=obr, state="normal")
            c.itemconfigure(it["btn_poly"], state="hidden")
        else:
            c.itemconfigure(it["btn_img"], state="hidden")
            c.itemconfigure(it["btn_poly"], state="normal", fill=vypln or "",
                            outline=prstenec or ram or "",
                            width=max(1, int(round((2 if prstenec else 1) * m))))
        c.itemconfigure(it["btn_text"], text=self.button_label(), fill=farba_textu)

    def _update_items(self, w, h, m, t):
        """Upravi farbu/polohu/viditelnost prvkov podla stavu a fazy dychu,
        bez mazania. Vsetky farby berie z AKTUALNEJ palety, takze to zvlada aj
        zmenu temy (`set_pal` -> `_redraw` -> sem)."""
        c = self.canvas
        it = self._it
        pal = self.pal
        live = self.live
        if live:
            fill = theme_mod.mix(pal["plate"], pal["plate_glow"], t)
            outline = theme_mod.mix(pal["accent2"], pal["accent"], 0.5 * t)
        else:
            fill = pal["plate_idle"]
            outline = pal["plate_idle_border"]
        c.itemconfigure(it["plate"], fill=fill, outline=outline)
        cxf = w / 2.0
        seg = len(it["glow"])
        for i, rid in enumerate(it["glow"]):
            if live and t > 0.01:
                x0 = 2 + (w - 4) * i / seg
                x1 = 2 + (w - 4) * (i + 1) / seg
                d = abs((x0 + x1) / 2.0 - cxf) / (w / 2.0)
                jas = max(0.0, 1.0 - d) ** 1.6 * t
                if jas >= 0.02:
                    c.itemconfigure(rid, state="normal",
                                    fill=theme_mod.mix(fill, pal["accent_hover"], 0.5 * jas))
                    continue
            c.itemconfigure(rid, state="hidden")
        if live:
            half = (w * 0.06) + (w * 0.40) * t
            cx = w / 2.0
            c.coords(it["line"], cx - half, h - 3, cx + half, h - 3)
            c.itemconfigure(it["line"], fill=pal["accent_hover"], state="normal")
        else:
            c.itemconfigure(it["line"], state="hidden")
        # Tlacidlo sa prekresluje len pri zmene stavu, nie pri kazdom tiku
        # dychu: obrazok ma priehladne rohy a vnutro `secondary`, takze
        # dychajuci plat pod nim presvita sam.
        druh = "secondary" if live else "primary"
        stav = (druh, self._hover_btn, self._focus, self._btn_rect)
        if stav != self._btn_stav:
            self._btn_stav = stav
            self._kresli_tlacidlo(druh, m)
        c.itemconfigure(it["hint"], fill=pal["text_dim"] if live else pal["text_faint"])


# --------------------------------------------------------------------------
# Krivka tepu
# --------------------------------------------------------------------------

class PalCanvas(ctk.CTkFrame):
    """Spolocny zaklad vsetkeho, co sa kresli na `tk.Canvas`.

    Drzi platno, paletu a prekreslenie pri zmene sirky. `set_pal` tu je
    preto, ze prefarbenie temy (`theme_recolor`) vie prepisat VOLBY
    widgetu, ale nie to, co uz na platne lezi - ciara by ostala v starej
    farbe, kym ju nieco neprekresli. Zive grafy sa prekresluju kazdou
    vzorkou tepu a zahoja sa samy; graf v Historii stoji, kym ho niekto
    nepreklikne, takze bez `set_pal` by po zmene temy svietil postarom.
    `DandurfApp._recolor_ui` prejde strom a zavola ho na kazdom potomkovi.
    """

    def __init__(self, master, pal, height):
        super().__init__(master, fg_color="transparent", height=height)
        self.pack_propagate(False)
        self.pal = pal
        self.height = height
        self.canvas = tk.Canvas(self, height=height, bg=pal["surface"],
                                highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda _e: self._redraw())

    def set_pal(self, pal):
        self.pal = pal
        try:
            self.canvas.configure(bg=pal["surface"])
        except Exception:
            pass
        self._redraw()

    def _canvas_size(self, min_width=20):
        """(sirka, vyska, mierka) platna v SKUTOCNYCH pixeloch; (0, 0, 1.0)
        kym nie je rozlozene.

        `mierka` je pomer skutocnej vysky platna k logickej vyske widgetu.
        CustomTkinter berie rozmery vo "svojich" jednotkach a sam ich
        nasobi mierkou displeja, lenze `tk.Canvas` pod nimi kresli v
        skutocnych pixeloch. Na 150 % displeji (co je na Windows bezne
        nastavenie) by graf kreslil do hornych dvoch tretin platna a pod
        nim by ostala diera - presne to sa na tejto appke aj stalo.
        Vsetky rozmery v `_redraw` sa preto nasobia touto mierkou.
        """
        try:
            w = int(self.canvas.winfo_width())
            h = int(self.canvas.winfo_height())
        except Exception:
            return 0, 0, 1.0
        if w < min_width or h < 2:
            return 0, 0, 1.0
        return w, h, (h / float(self.height)) if self.height else 1.0

    def _redraw(self):
        pass


class Sparkline(PalCanvas):
    """Priebeh tepu s kritickou hranicou a vlastnou pokojovou zakladnou.

    Bez zakladny je krivka necitatelna: 90 BPM je pre jedneho pokoj a pre
    druheho panika. Preto su v grafe obe ciary - hranica (prerusovana) aj
    zakladna (tenka), a az voci nim krivka nieco znamena.
    """

    def __init__(self, master, pal, height=64):
        super().__init__(master, pal, height)
        self._values, self._threshold, self._baseline = [], None, None
        self._color = None

    def set_series(self, values, threshold=None, baseline=None, color=None):
        """`color` je volitelny prepis farby ciary (napr. Historia meni
        farbu podla zvolenej metriky) - bez neho ostava predvolena accent.

        POZOR NA NULU: filter tu bol `if v`, cize zahadzoval aj nuly. Pri
        tepe je to jedno (0 BPM neexistuje), ale Historia sem posiela aj
        "cas nad hranicou" - a tam je nula PLATNA hodnota. Den bez
        prekrocenia z grafu vypadol a krivka sa o jeden bod posunula.
        """
        self._values = [v for v in (values or []) if v is not None]
        self._threshold = threshold
        self._baseline = baseline
        self._color = color
        self._redraw()

    def _redraw(self):
        pal, c = self.pal, self.canvas
        w, h, s = self._canvas_size()
        if not w:
            return
        c.delete("all")
        pad = 6 * s
        values = self._values

        if len(values) < 2:
            c.create_line(0, h - pad, w, h - pad, fill=pal["text_faint"], width=1)
            return

        lo, hi = min(values), max(values)
        if self._threshold:
            lo, hi = min(lo, self._threshold - 4), max(hi, self._threshold + 4)
        if hi - lo < 12:
            mid = (hi + lo) / 2.0
            lo, hi = mid - 6, mid + 6
        span = float(hi - lo)

        def y_of(value):
            return h - pad - (value - lo) / span * (h - 2 * pad)

        if self._baseline and lo <= self._baseline <= hi:
            c.create_line(0, y_of(self._baseline), w, y_of(self._baseline),
                          fill=pal["text_faint"], width=1)
        if self._threshold and lo <= self._threshold <= hi:
            c.create_line(0, y_of(self._threshold), w, y_of(self._threshold),
                          fill=pal["danger"], width=1, dash=(4, 4))

        step = w / float(len(values) - 1)
        points = []
        for i, value in enumerate(values):
            points.extend((i * step, y_of(value)))
        c.create_line(*points, fill=self._color or pal["accent_hover"],
                      width=max(1, round(2 * s)), smooth=True, capstyle="round",
                      joinstyle="round")
        r = 3 * s
        c.create_oval(points[-2] - r, points[-1] - r, points[-2] + r, points[-1] + r,
                      fill=pal["text"], outline="")


class SegmentBar(PalCanvas):
    """Zataz ako delený pruh. Plynula lišta by tvrdila presnost, ktoru
    cislo z tepu nema - dvadsat dielikov je poctivejsie.

    Dlzka je zataz, farba plnych dielikov je AKTUALNE pasmo (`zone` z
    `HeartStats.zone`, tep voci pokoju) - vsetky rovnako, ako na HUD-e.
    Vlastne hranice pasiem pruh nema: predtym farbil dieliky podla
    35/60/80 % dlzky, takze pri zatazi 57 koncil "zvysenou", HUD pri tej
    istej zatazi "vysokou" (stvrtiny pruhu) a slovo nad nim mohlo hovorit
    este nieco ine. Bez `zone` su dieliky neutralne (akcent).
    """

    SEGMENTS = 20

    def __init__(self, master, pal, height=8):
        super().__init__(master, pal, height)
        self._value = 0.0
        self._zone = None

    def set_value(self, percent, zone=None):
        self._value = max(0.0, min(100.0, float(percent or 0)))
        self._zone = zone
        self._redraw()

    def _redraw(self):
        pal, c = self.pal, self.canvas
        w, h, _s = self._canvas_size()
        if not w:
            return
        c.delete("all")
        filled = int(round(self.SEGMENTS * self._value / 100.0))
        seg = w / float(self.SEGMENTS)
        plna = theme_mod.zone_color(pal, self._zone)
        for i in range(self.SEGMENTS):
            x0 = i * seg
            x1 = x0 + seg * 0.72
            color = plna if i < filled else pal["switch_off"]
            c.create_rectangle(x0, 0, x1, h, fill=color, outline="")


# --------------------------------------------------------------------------
# Grafy histórie a relácie
# --------------------------------------------------------------------------

class ZoneBar(PalCanvas):
    """Rozdelenie casu relacie do pasiem ako jeden pomerovy pruh.

    `zone_seconds` appka pocitala od zaciatku a nikde ich neukazovala.
    Pritom jedno cislo ("12 minut nad hranicou") nepovie to, co povie
    pomer: ci bol vecer prevazne pokojny s dvoma spickami, alebo hodinu
    v cervenom.
    """

    ORDER = ("calm", "raised", "high", "critical")

    def __init__(self, master, pal, height=14):
        super().__init__(master, pal, height)
        self._zones = {}

    def set_zones(self, zone_seconds):
        self._zones = dict(zone_seconds or {})
        self._redraw()

    def _redraw(self):
        pal, c = self.pal, self.canvas
        w, h, s = self._canvas_size()
        if not w:
            return
        c.delete("all")
        diely = [(z, max(0.0, float(self._zones.get(z, 0.0) or 0.0))) for z in self.ORDER]
        celkom = sum(d for _z, d in diely)
        if celkom <= 0:
            round_rect(c, 0, 0, w, h, 3 * s, fill=pal["line_soft"], outline="")
            return
        x = 0.0
        for zona, sekundy in diely:
            sirka = sekundy / celkom * w
            if sirka <= 0:
                continue
            c.create_rectangle(x, 0, min(float(w), x + sirka), h,
                               fill=theme_mod.zone_color(pal, zona), outline="")
            x += sirka


class TrendChart(PalCanvas):
    """Vyvoj metriky naprieC relaciami - stlpce alebo ciara, s osami.

    Preco osi: povodne to kreslil `Sparkline`, cize hola ciara bez
    jedineho popisku - z grafu sa nedalo precitat ani KEDY, ani KOLKO.
    Pritom popisok kazdeho bucketu uz `hr_stats.aggregate_by_period`
    pocita, len ho nikto nekreslil.

    Tvar podla metriky: cas a spicky su stlpce od nuly (nula je vtedy
    vypoved, nie diera), zakladna a zotavenie su ciara okolo vlastnej
    urovne - pri nich by stlpec od nuly zobral celu vysku grafu na usek
    60-70 BPM, ktory hraca zaujima.

    `band` je "tvoje bezne rozpatie" (p25-p75 z historie): hodnota vnutri
    pasu je tvoj normal, hodnota mimo neho je to jedine, co si zasluzi
    pozornost.
    """

    PAD_L = 48      # popisky osi y
    PAD_R = 10
    PAD_T = 12
    PAD_B = 20      # popisky osi x
    MAX_X_LABELS = 8

    # PRAZDNY STAV (0.2.2, audit UX): bez dat bola na mieste grafu prazdna
    # plocha ~230 px a veta "zatial nic" az pod nou. Teraz graf zmensi na
    # EMPTY_H a vetu napise do svojho stredu.
    EMPTY_H = 80

    def __init__(self, master, pal, height=150):
        super().__init__(master, pal, height)
        self._full_height = height
        self._values, self._labels = [], []
        self._color, self._band, self._band_label = None, None, ""
        self._bars = False
        self._decimals = 0
        self._empty_text = ""

    def set_series(self, values, labels=None, color=None, band=None,
                   band_label="", bars=False, decimals=0, empty_text=""):
        self._values = list(values or [])
        self._labels = list(labels or [])
        self._color = color
        self._band = band
        self._band_label = band_label or ""
        self._bars = bool(bars)
        self._decimals = int(decimals)
        self._empty_text = empty_text or ""
        prazdny = not [v for v in self._values if v is not None]
        vyska = self.EMPTY_H if (prazdny and self._empty_text) else self._full_height
        if vyska != self.height:
            # `self.height` je zaroven zaklad mierky v `_canvas_size`
            self.height = vyska
            try:
                self.configure(height=vyska)
            except Exception:
                pass
        self._redraw()

    def _fmt(self, value):
        return f"{value:.{self._decimals}f}"

    def _bounds(self):
        """(lo, hi) osi y. Stlpce vzdy od nuly, ciara s rezervou okolo dat."""
        values = [v for v in self._values if v is not None]
        lo, hi = min(values), max(values)
        if self._band:
            lo, hi = min(lo, self._band[0]), max(hi, self._band[1])
        if self._bars:
            lo = 0.0
            if hi <= 0:
                hi = 1.0
        else:
            if hi - lo < 1.0:
                mid = (hi + lo) / 2.0
                lo, hi = mid - 0.5, mid + 0.5
            rezerva = (hi - lo) * 0.15
            lo, hi = lo - rezerva, hi + rezerva
        return lo, hi

    def _draw_x_labels(self, x0, slot, h, s):
        """Popisky osi x, preriedene tak, aby sa neprekryvali. Posledny
        bucket sa kresli vzdy - "kde som teraz" je to, co clovek hlada."""
        pal, c = self.pal, self.canvas
        n = len(self._labels)
        every = max(1, int(math.ceil(n / float(self.MAX_X_LABELS))))
        indexy = list(range(0, n, every))
        if n and indexy[-1] != n - 1:
            if n - 1 - indexy[-1] < max(1, every // 2):
                indexy.pop()
            indexy.append(n - 1)
        for i in indexy:
            c.create_text(x0 + slot * (i + 0.5), h - 5 * s, text=self._labels[i],
                          anchor="s", fill=pal["text_faint"], font=mono(10))

    def _redraw(self):
        pal, c = self.pal, self.canvas
        w, h, s = self._canvas_size(120)
        if not w:
            return
        c.delete("all")
        x0, x1 = self.PAD_L * s, w - self.PAD_R * s
        y0, y1 = self.PAD_T * s, h - self.PAD_B * s
        if not [v for v in self._values if v is not None]:
            if self._empty_text:
                c.create_text(w / 2.0, h / 2.0, text=self._empty_text,
                              fill=pal["text_dim"], font=ui(12),
                              width=max(40, int(w - 2 * self.PAD_L * s)))
            else:
                c.create_line(x0, y1, x1, y1, fill=pal["line_soft"], width=1)
            return

        lo, hi = self._bounds()
        span = float(hi - lo) or 1.0

        def y_of(value):
            return y1 - (value - lo) / span * (y1 - y0)

        if self._band:
            # Pas je pozadie, nie udaj: `accent2` bol na plnu sirku taky
            # vyrazny, ze prekrical samotnu ciaru. Jemne primiesany akcent
            # do podkladu drzi vyznam ("tu si obvykle") a nekradne pozornost.
            vrch_pasu = y_of(self._band[1])
            c.create_rectangle(x0, vrch_pasu, x1, y_of(self._band[0]),
                               fill=theme_mod.mix(pal["surface"], pal["accent"], 0.14),
                               outline="")
            # Pas bez popisku je len farebny obdlznik - clovek netusi, ci
            # je to ciel, norma alebo ozdoba.
            if self._band_label:
                c.create_text(x1, vrch_pasu - 3 * s, text=self._band_label,
                              anchor="se", fill=pal["text_faint"], font=ui(10))
        for value in (lo, (lo + hi) / 2.0, hi):
            y = y_of(value)
            c.create_line(x0, y, x1, y, fill=pal["line_soft"], width=1)
            c.create_text(x0 - 7 * s, y, text=self._fmt(value), anchor="e",
                          fill=pal["text_faint"], font=mono(10))

        color = self._color or pal["accent_hover"]
        n = len(self._values)
        slot = (x1 - x0) / float(n)
        if self._bars:
            sirka = max(3.0 * s, min(30.0 * s, slot * 0.62))
            spodok = y_of(lo)
            for i, value in enumerate(self._values):
                if value is None:
                    continue
                stred = x0 + slot * (i + 0.5)
                vrch = y_of(value)
                # nulovy den ma ostat viditelny ako nulovy, nie zmiznut
                if spodok - vrch < 2.0 * s:
                    vrch = spodok - 2.0 * s
                c.create_rectangle(stred - sirka / 2, vrch, stred + sirka / 2,
                                   spodok, fill=color, outline="")
        else:
            body = []
            for i, value in enumerate(self._values):
                if value is None:
                    continue
                body.extend((x0 + slot * (i + 0.5), y_of(value)))
            if len(body) >= 4:
                c.create_line(*body, fill=color, width=max(1, round(2 * s)),
                              smooth=True, capstyle="round", joinstyle="round")
            if body:
                r = 3 * s
                c.create_oval(body[-2] - r, body[-1] - r, body[-2] + r,
                              body[-1] + r, fill=pal["text"], outline="")
        if self._labels:
            self._draw_x_labels(x0, slot, h, s)


class SessionTrace(PalCanvas):
    """Stopa CELEJ relacie: krivka, hranica, zakladna, pas pasiem a znacky
    spustenia dychania.

    `Sparkline` vedla ukazuje posledne tri minuty - to je "teraz". Toto je
    "cely vecer": kde tep vyskocil, ako dlho tam ostal a kedy appka
    spustila dychanie. Bez tohto sa relacia dala precitat uz len ako
    riadok cisel.

    Pas pod krivkou farbi cas podla `hr_stats.zone_of_bpm` - tej istej
    funkcie, ktora scitava sekundy v pasmach. Keby si pruh pasma pocital
    sam, obrazok a cisla pod nim by si po case prestali sediet.
    """

    STRIP_H = 9
    ACT_H = 7        # pruh 'kde sa hralo'
    TIME_H = 14
    # Prava rezerva na cisla hranice a zakladne (0.2.2, audit UX). Popisky
    # lezali NA krivke, ktora po vecere s tepom pri hranici "110" aj "76"
    # prekryla. Krivka, pasy aj znacky koncia pred rezervou, cisla su v nej.
    LABEL_W = 28

    def __init__(self, master, pal, height=88):
        super().__init__(master, pal, height)
        self._values, self._baseline, self._threshold = [], None, None
        self._duration, self._triggers = 0.0, []
        self._activity = []

    def set_trace(self, values, baseline=None, threshold=None, duration_s=0.0,
                  triggers=(), activity=()):
        self._values = [v for v in (values or []) if v]
        self._baseline = baseline
        self._threshold = threshold
        self._duration = float(duration_s or 0.0)
        self._triggers = list(triggers or [])
        self._activity = [a for a in (activity or [])]
        self._redraw()

    @staticmethod
    def _mmss(seconds):
        total = int(max(0.0, seconds))
        return f"{total // 60}:{total % 60:02d}"

    # Od hodiny vyssie sa koniec osi pise ako dlzka ("2 h 18 min"), nie m:ss:
    # "138:02" vyzeralo ako cas na hodinkach (0.2.2, audit UX, davka 4). Ta
    # ista hranica ako `cas_text` ("Nad hranicou", cas relacie).
    OS_DLZKA_OD_S = DLZKA_OD_S

    @classmethod
    def os_popisky(cls, duration_s):
        """(zaciatok, koniec) osi casu pre relaciu dlhu `duration_s`."""
        if duration_s >= cls.OS_DLZKA_OD_S:
            return dlzka_text(0), dlzka_text(duration_s)
        return "0:00", cls._mmss(duration_s)

    def _draw_strip(self, w, top, vyska):
        """Pas pasiem - susedne rovnake pasma sa spajaju do jedneho
        obdlznika, nech na platne nelezi 120 utvarov namiesto piatich."""
        pal, c = self.pal, self.canvas
        base = self._baseline or min(self._values)
        critical = self._threshold or (base + 40)
        n = len(self._values)
        krok = w / float(n)
        start, zona = 0, hr_stats.zone_of_bpm(self._values[0], base, critical)
        for i in range(1, n + 1):
            aktualna = (hr_stats.zone_of_bpm(self._values[i], base, critical)
                        if i < n else None)
            if aktualna == zona:
                continue
            c.create_rectangle(start * krok, top, i * krok, top + vyska,
                               fill=theme_mod.zone_color(pal, zona), outline="")
            start, zona = i, aktualna

    def _draw_activity(self, w, top, vyska):
        """Tenky pruh nad pasom pasiem: kde sa naozaj hralo.

        Kazdy bod je PODIEL casu so vstupom v danom useku (0..1), nie
        hodnota v okamihu. Vysoka hodnota = husty vstup = hra; nizka =
        menu alebo odchod od PC.

        Je to ODHAD, nie pravda o hre. `GetLastInputInfo` vidi vstup kdekolvek,
        takze pisanie do Discordu pocas hry vyzera rovnako ako hranie. Preto
        sa kresli jemne a bez popisku, ktory by tvrdil viac, nez vieme.
        """
        if not self._activity:
            return
        pal, c = self.pal, self.canvas
        n = len(self._activity)
        krok = w / float(n)
        for i, hodnota in enumerate(self._activity):
            if hodnota is None:
                continue
            try:
                podiel = max(0.0, min(1.0, float(hodnota)))
            except (TypeError, ValueError):
                continue
            if podiel <= 0.02:
                continue
            # Vyska stlpca nesie hustotu; farba ostava jedna, aby sa pruh
            # nepomylil s pasom pasiem hned pod nim.
            #
            # `text_faint`, nie `text_dim` a uz vobec nie akcent: je to
            # ODHAD, nie meranie. Pri `text_dim` (#9A9488) bol pruh jasnejsi
            # nez samotna krivka tepu - odhad tak prekrikoval to, kvoli comu
            # graf existuje. Musi byt citatelny a zaroven podriadeny.
            vyska_st = max(1.0, vyska * podiel)
            c.create_rectangle(i * krok, top + vyska - vyska_st,
                               (i + 1) * krok, top + vyska,
                               fill=pal["text_faint"], outline="")

    def _draw_triggers(self, w, bottom, s):
        """Kedy appka spustila dychanie - mala znacka nad pasom pasiem."""
        pal, c = self.pal, self.canvas
        if not self._triggers or self._duration <= 0:
            return
        for offset in self._triggers:
            try:
                podiel = float(offset) / self._duration
            except (TypeError, ValueError, ZeroDivisionError):
                continue
            if not 0.0 <= podiel <= 1.0:
                continue
            x = podiel * w
            c.create_polygon(x - 4 * s, bottom - 6 * s, x + 4 * s, bottom - 6 * s,
                             x, bottom, fill=pal["murasaki"], outline="")

    def _redraw(self):
        pal, c = self.pal, self.canvas
        w, h, s = self._canvas_size(60)
        if not w:
            return
        c.delete("all")
        strip_h, time_h = self.STRIP_H * s, self.TIME_H * s
        strip_top = h - time_h - strip_h
        values = self._values
        if len(values) < 2:
            c.create_line(0, strip_top, w, strip_top, fill=pal["line_soft"], width=1)
            return

        lo, hi = min(values), max(values)
        for ciara in (self._threshold, self._baseline):
            if ciara:
                lo, hi = min(lo, ciara - 3), max(hi, ciara + 3)
        if hi - lo < 12:
            mid = (hi + lo) / 2.0
            lo, hi = mid - 6, mid + 6
        span = float(hi - lo)
        vrch, spodok = 4 * s, strip_top - 10 * s
        pw = max(10.0, w - self.LABEL_W * s)     # sirka krivky bez rezervy
        obsadene = []                             # y uz nakreslenych cisel

        def y_of(value):
            return spodok - (value - lo) / span * (spodok - vrch)

        def popisok(y, hodnota, farba):
            """Cislo k ciare v pravej rezerve, na vysku ciary. Dve blizke
            ciary (hranica tesne nad zakladnou) by si cisla prekryli - druhe
            sa odsunie o riadok."""
            riadok = 11 * s
            for ine in obsadene:
                if abs(y - ine) < riadok:
                    y = ine - riadok if y <= ine else ine + riadok
            y = min(max(y, 6 * s), spodok)
            obsadene.append(y)
            c.create_text(w - 1 * s, y, text=str(int(round(hodnota))), anchor="e",
                          fill=farba, font=mono(10))

        if self._baseline and lo <= self._baseline <= hi:
            y = y_of(self._baseline)
            c.create_line(0, y, pw, y, fill=pal["text_faint"], width=1)
            popisok(y, self._baseline, pal["text_faint"])
        if self._threshold and lo <= self._threshold <= hi:
            y = y_of(self._threshold)
            c.create_line(0, y, pw, y, fill=pal["danger"], width=1, dash=(4, 4))
            # cislo je drobny text (mono 10) - `danger_text`, nie `danger`
            # (pravidlo v theme.py); ciara ostava `danger`
            popisok(y, self._threshold, pal["danger_text"])

        krok = pw / float(len(values) - 1)
        body = []
        for i, value in enumerate(values):
            body.extend((i * krok, y_of(value)))
        c.create_line(*body, fill=pal["accent_hover"], width=max(1, round(2 * s)),
                      smooth=True, capstyle="round", joinstyle="round")

        self._draw_triggers(pw, strip_top - 2 * s, s)
        self._draw_activity(pw, strip_top - self.ACT_H - 2, self.ACT_H)
        self._draw_strip(pw, strip_top, strip_h)
        if self._duration > 0:
            zaciatok, koniec = self.os_popisky(self._duration)
            c.create_text(0, h - 2 * s, text=zaciatok, anchor="sw",
                          fill=pal["text_faint"], font=mono(10))
            c.create_text(pw, h - 2 * s, text=koniec, anchor="se",
                          fill=pal["text_faint"], font=mono(10))


# POZN: tu bola trieda `MicroChart` - mikrograf pri cisle na karte
# statistiky, bez osi a mierky. Jediny ukol mal povedat "stupa /
# klesa / stoji".
#
# Odisla s prestavbou karty (`StatCard`): karta ma byt JEDEN pokojny
# udaj a mikrograf s vetou o odchylke z nej robili tri. Mala jedineho
# volajuceho, takze tu ostala bez pouzitia. Trend zije dalej v Historii,
# kde je na to cely graf (`Sparkline`, `DayGrid`).


class CueEffectChart(PalCanvas):
    """Ucinnost jednotlivych kategorii hlasok - jeden riadok na kategoriu.

    CO KRESLI
    ---------
    Vodorovna os je posun tepu po hlaske. Nula je v strede; doľava klesol,
    doprava stupol. Pruh je odhad, tenka ciarka cez neho je 95% interval.

    PRECO INTERVAL A NIE HOLE CISLO
    -------------------------------
    Pri siestich oknach je "-4,2 BPM" cislo, ktoremu sa da verit asi tak
    ako predpovedi pocasia na buduci mesiac. Interval to ukaze na prvy
    pohlad: ked ciarka presahuje nulu, rozdiel moze byt aj opacny.
    Zadanie 2.1b, B2: "vystup nech je odhad s intervalom, nikdy hole cislo".

    KED JE DAT MALO, NEKRESLI SA PRUH VOBEC
    ---------------------------------------
    Pod `measure.MIN_OKIEN` sa ukaze len pocet okien. Pruh dlhy cez pol
    panela by tvrdil nieco, co v datach nie je - a prave na zaciatku, ked
    hrac graf otvara najcastejsie.
    """

    RIADOK = 26          # vyska jedneho riadku v logickych px
    POPIS = 84           # sirka stlpca s nazvom kategorie

    def __init__(self, master, pal, height=120):
        super().__init__(master, pal, height)
        self._riadky = []
        self._malo_textu = ""

    def set_data(self, riadky, malo_textu=""):
        """`riadky` su (nazov, n, delta_bpm, ci95, dost_dat)."""
        self._riadky = list(riadky or [])
        self._malo_textu = malo_textu or ""
        # `self.height` musi ist s `configure(height=...)` - `_canvas_size` z nej
        # rata mierku; bez toho by po zmene poctu riadkov mierka nesedela.
        self.height = max(self.RIADOK * max(1, len(self._riadky)) + 18, 40)
        self.configure(height=self.height)
        self._redraw()

    def _redraw(self):
        c, pal = self.canvas, self.pal
        try:
            c.delete("all")
        except Exception:
            return
        w, h, s = self._canvas_size()
        if w < 60 or not self._riadky:
            return

        popis = self.POPIS * s
        lavo = popis + 8 * s
        pravo = w - 10 * s
        stred = (lavo + pravo) / 2.0
        if pravo - lavo < 40 * s:
            return

        # Mierka: najvacsia hodnota (aj s intervalom) ma zaplnit polovicu.
        vrchol = 1.0
        for _n, _p, delta, ci, dost in self._riadky:
            if not dost or delta is None:
                continue
            vrchol = max(vrchol, abs(delta) + (ci or 0.0))
        jednotka = (pravo - stred) / vrchol

        # nulova os
        c.create_line(stred, 4 * s, stred, h - 4 * s,
                      fill=pal["border"], width=max(1, round(s)))

        y = 12 * s
        for nazov, n, delta, ci, dost in self._riadky:
            c.create_text(popis, y, text=nazov, anchor="e",
                          fill=pal["text_dim"], font=ui(11))
            if not dost:
                c.create_text(lavo + 4 * s, y, text=self._malo_textu.format(n=n),
                              anchor="w", fill=pal["text_faint"], font=ui(10))
                y += self.RIADOK * s
                continue

            # Zaporny posun = tep klesol = hlaska zabrala.
            dobra = delta < 0
            farba = pal["success"] if dobra else pal["warn"]
            x = stred + delta * jednotka
            c.create_rectangle(min(stred, x), y - 5 * s, max(stred, x), y + 5 * s,
                               fill=farba, outline="")
            if ci:
                c1, c2 = x - ci * jednotka, x + ci * jednotka
                c.create_line(c1, y, c2, y, fill=pal["text_faint"],
                              width=max(1, round(s)))
                for kx in (c1, c2):
                    c.create_line(kx, y - 4 * s, kx, y + 4 * s,
                                  fill=pal["text_faint"], width=max(1, round(s)))
            # cislo podla jazyka appky ("−4,2", nie "-4.2" - `i18n.cislo`)
            from i18n import cislo
            c.create_text(pravo, y, text="%s  (n=%d)" % (cislo(delta, 1, sign=True), n),
                          anchor="e",
                          fill=pal["text_faint"], font=mono(10))
            y += self.RIADOK * s


class DayGrid(PalCanvas):
    """Mriezka dni - stlpec je tyzden, riadok den v tyzdni (pondelok hore),
    sytost stvorceka kolko si v ten den odohral.

    Cita sa z nej to, co zo ziadneho ineho grafu v appke nevidno: vzor.
    Vikendy, serie vecerov, tyzden, ked appka lezala vypnuta. Prazdne dni
    su preto rovnako dolezite ako plne a kreslia sa tiez.
    """

    # VELKOST STVORCEKA PODLA SIRKY (0.2.2 davka 4b). Pevnych 12 px kreslilo
    # 26 tyzdnov do ~170 px panela sirokeho ~1000 px - zvysok bola prazdna
    # plocha a vzor sa v drobnych stvorcekoch hladal. Stvorcek teraz rastie,
    # kym tyzdne nezaplnia sirku (`rozmer_bunky`), najviac na CELL_MAX - pri
    # par tyzdnoch by inak boli obrie. Medzera rastie s nim (GAP..GAP_MAX)
    # a s nimi aj vyska mriezky; popisky mesiacov a dni idu po tom istom
    # kroku, takze sedia nad stlpcami a vedla riadkov.
    CELL = 12           # najmensi stvorcek (uzke okno)
    CELL_MAX = 22
    GAP = 3
    GAP_MAX = 5
    LEGEND_H = 18
    # POPISKY (0.2.2, audit UX, davka 4): mesiace nad stlpcami a dni vlavo.
    # Bez nich sa z mriezky nedalo povedat, ktory stlpec je ktory tyzden ani
    # ktory riadok je nedela - vzor (vikendy, vecery) sa citat nedal.
    MONTH_H = 15
    STEPS = 4       # kolko odtienov nad "prazdny den"
    # Ktore riadky nesu meno dna: pondelok, streda, piatok - siedmy popisok
    # pri 12 px riadku by sa s vedlajsimi slial. Od kroku VSETKY_DNI_OD
    # (stvorcek + medzera) sa zmesti meno kazdeho dna, aj soboty a nedele.
    DAY_ROWS = (0, 2, 4)
    VSETKY_DNI_OD = 20

    def __init__(self, master, pal):
        super().__init__(master, pal, self.vyska_mriezky(self.CELL, self.GAP))
        self._days = []
        self._legend = ("", "")
        self._months = ()
        self._weekdays = ()

    def set_days(self, days, legend=("", ""), months=(), weekdays=()):
        """`days` je vystup `hr_stats.day_activity` (od najstarsieho).

        `months` = 12 skratiek mesiacov (januar prvy), `weekdays` = 7 skratiek
        dni (pondelok prvy) - v jazyku APPKY, preto ich dava volajuci z i18n.
        Prazdne = bez popiskov."""
        self._days = list(days or [])
        self._legend = legend
        self._months = tuple(months or ())
        self._weekdays = tuple(weekdays or ())
        self._redraw()

    @staticmethod
    def stlpce_mesiacov(prvy_datum, prvy_den, stlpcov):
        """[(stlpec, mesiac 1..12)] - kde zacina mesiac nad mriezkou.

        Mesiac sa pise nad stlpec, v ktorom je jeho 1. den. Prvy stlpec
        dostane mesiac svojho prveho dna, len ked do dalsieho popisku ostavaju
        aspon tri stlpce - inak by sa dve skratky prekryli."""
        from datetime import timedelta
        vysledok = []
        for stlpec in range(stlpcov):
            for riadok in range(7):
                index = stlpec * 7 + riadok - prvy_den
                if index < 0:
                    continue
                datum = prvy_datum + timedelta(days=index)
                if datum.day == 1:
                    vysledok.append((stlpec, datum.month))
                    break
        if not vysledok or vysledok[0][0] >= 3:
            vysledok.insert(0, (0, prvy_datum.month))
        return vysledok

    @classmethod
    def rozmer_bunky(cls, sirka, stlpcov):
        """(stvorcek, medzera) v logickych px, aby `stlpcov` tyzdnov zaplnilo
        `sirka` - stvorcek najviac CELL_MAX, najmenej CELL (vtedy sa zaciatok
        historie oreze, viz `_redraw`)."""
        if stlpcov <= 0 or sirka <= 0:
            return float(cls.CELL), float(cls.GAP)
        # medzera ~18 % kroku; za poslednym stlpcom medzera nie je
        medzera = float(max(cls.GAP, min(cls.GAP_MAX,
                                         round((float(sirka) + cls.GAP) / stlpcov * 0.18))))
        krok = (float(sirka) + medzera) / stlpcov
        bunka = max(float(cls.CELL), min(float(cls.CELL_MAX), krok - medzera))
        return bunka, medzera

    @classmethod
    def vyska_mriezky(cls, bunka, medzera):
        """Vyska celeho prvku v logickych px: mesiace + 7 riadkov + legenda."""
        return int(math.ceil(cls.MONTH_H + 7 * (bunka + medzera) - medzera
                             + cls.LEGEND_H))

    def _mierka(self):
        """Mierka DPI prvku (fyzicke px / logicke) - nie z vysky platna:
        vyska sa tu meni so sirkou, takze by sa s nou menila aj mierka."""
        try:
            return float(self._get_widget_scaling()) or 1.0
        except Exception:
            try:
                return int(self.canvas.winfo_height()) / float(self.height)
            except Exception:
                return 1.0

    def _odtiene(self):
        # odtiene smerom k farbe POKOJA danej temy, nie k univerzalnej
        # zelenej - v indigovej teme bola mriezka jediny zeleny ostrovcek
        return [theme_mod.mix(self.pal["surface_alt"],
                              theme_mod.zone_color(self.pal, "calm"),
                              (i + 1) / float(self.STEPS))
                for i in range(self.STEPS)]

    def _redraw(self):
        pal, c = self.pal, self.canvas
        try:
            w = int(c.winfo_width())
        except Exception:
            return
        if w < 60 or not self._days:
            return
        s = self._mierka()
        c.delete("all")
        odtiene = self._odtiene()
        # Prah kazdeho odtiena je percentil TVOJICH dni, nie pevna minutaz -
        # hodinu denne ma niekto ako maximum a niekto ako rozcvicku.
        aktivne = sorted(d["seconds"] for d in self._days if d["seconds"] > 0)
        prahy = [aktivne[min(len(aktivne) - 1, int(len(aktivne) * (i + 1) / float(self.STEPS)))]
                 for i in range(self.STEPS)] if aktivne else []
        # Popisky su v `text_faint` (>= 4,5:1 v oboch temach) a ui(10) -
        # najmensi obsahovy text appky.
        farba_popisu = pal["text_faint"]
        vrch = self.MONTH_H * s
        # Stlpec dni vlavo: sirka podla najdlhsieho popisku v tomto jazyku
        # ("Mon" / "月" / "seg"), nie natvrdo - inak by "lun" prekryl mriezku.
        # Popisky sa najprv len zmeraju; kam patria, sa vie az s krokom.
        lavo = 0
        popisky_dni = []
        if len(self._weekdays) == 7:
            for riadok in range(7):
                polozka = c.create_text(0, 0, text=self._weekdays[riadok], anchor="w",
                                        fill=farba_popisu, font=ui(10))
                box = c.bbox(polozka)
                if box:
                    lavo = max(lavo, box[2] - box[0])
                popisky_dni.append((riadok, polozka))
            lavo += 6 * s if lavo else 0
        # Velkost stvorceka podla sirky a poctu tyzdnov (`rozmer_bunky`).
        tyzdnov = max(1, (len(self._days) + self._days[0]["date"].weekday() + 6) // 7)
        bunka, medzera = self.rozmer_bunky((w - lavo) / s, tyzdnov)
        vyska = self.vyska_mriezky(bunka, medzera)
        if vyska != self.height:
            # Vyska ide so sirkou: nova sa nastavi a <Configure> prekresli.
            self.height = vyska
            try:
                self.configure(height=vyska)
            except Exception:
                pass
        cell, gap = bunka * s, medzera * s
        krok = cell + gap
        # CELE PX (skeptik UX 4b): krok je podiel sirky (napr. 40,5 px) a Tk
        # kresli vyhladeny polygon na zlomkovych suradniciach s ostnami na
        # hranach - velke stvorceky mali zubate okraje. Roh stvorceka ide
        # nadol na cely px, strana sa zaokruhli; popisky idu po tych istych
        # suradniciach, takze sedia presne nad stlpcom a vedla riadku.
        strana = max(1, int(round(cell)))

        def px(v):
            return math.floor(v + 1e-6)
        vsetky_dni = bunka + medzera >= self.VSETKY_DNI_OD
        for riadok, polozka in popisky_dni:
            if vsetky_dni or riadok in self.DAY_ROWS:
                c.coords(polozka, 0, px(vrch + riadok * krok) + strana / 2.0)
            else:
                c.delete(polozka)
        # Kolko tyzdnov sa zmesti - a orezava sa ZACIATOK, nie koniec:
        # dnesok musi byt v mriezke vzdy, aj keby sa historia nezmestila
        # cela. Volajuci preto moze pokojne poslat cely rok.
        # (+1e-6: krok je presne podiel sirky - 25,9999 tyzdna nie je 25)
        stlpcov = max(1, int((w - lavo + gap) / krok + 1e-6))
        dni = self._days
        for _ in range(3):
            prebytok = len(dni) + dni[0]["date"].weekday() - stlpcov * 7
            if prebytok <= 0:
                break
            dni = dni[prebytok:]
        prvy_den = dni[0]["date"].weekday()
        for i, den in enumerate(dni):
            poradie = i + prvy_den
            x = lavo + (poradie // 7) * krok
            y = vrch + (poradie % 7) * krok
            if x + cell > w + 0.5:
                break
            if den["seconds"] <= 0:
                farba = pal["line_soft"]
            else:
                stupen = sum(1 for p in prahy if den["seconds"] > p)
                farba = odtiene[min(stupen, self.STEPS - 1)]
            x, y = px(x), px(y)
            round_rect(c, x, y, x + strana, y + strana, max(3.0, bunka * 0.2) * s,
                       fill=farba, outline="")
        if len(self._months) == 12:
            pouzite = (len(dni) + prvy_den + 6) // 7
            koniec = -1.0
            for stlpec, mesiac in self.stlpce_mesiacov(dni[0]["date"], prvy_den,
                                                       min(stlpcov, pouzite)):
                x = px(lavo + stlpec * krok)
                if x < koniec:
                    continue            # predosla skratka by sa prekryla
                polozka = c.create_text(x, vrch - 3 * s, text=self._months[mesiac - 1],
                                        anchor="sw", fill=farba_popisu, font=ui(10))
                box = c.bbox(polozka)
                koniec = (box[2] if box else x) + 4 * s
        legenda_y = vrch + 7 * krok - gap + (self.LEGEND_H - 6) * s
        menej, viac = self._legend
        polozka = c.create_text(0, legenda_y, text=menej, anchor="sw",
                                fill=pal["text_faint"], font=ui(10))
        # Stvorceky legendy za slovom "menej" podla jeho skutocnej sirky -
        # "weniger" / "меньше" su sirsie nez slovenske "menej".
        box = c.bbox(polozka)
        x = max(46 * s, (box[2] + 6 * s) if box else 0)
        for farba in [pal["line_soft"]] + odtiene:
            x0, y0 = px(x), px(legenda_y - 10 * s)
            round_rect(c, x0, y0, x0 + int(round(10 * s)), y0 + int(round(10 * s)), 2 * s,
                       fill=farba, outline="")
            x += 13 * s
        c.create_text(x + 3 * s, legenda_y, text=viac, anchor="sw",
                      fill=pal["text_faint"], font=ui(10))


class StatList(ctk.CTkFrame):
    """Zoznam "nazov ... hodnota" s deliacimi linkami a pevnym poradim."""

    def __init__(self, master, pal):
        super().__init__(master, fg_color="transparent")
        self.pal = pal
        self._values = {}

    def add(self, key, name, value="-"):
        pal = self.pal
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x")
        ctk.CTkLabel(row, text=name, font=ui(12), text_color=pal["text_dim"],
                     anchor="w").pack(side="left", pady=7)
        label = ctk.CTkLabel(row, text=str(value), font=mono(13),
                             text_color=pal["text"], anchor="e")
        label.pack(side="right", pady=7)
        linka(self, pal).pack(fill="x")
        self._values[key] = label
        return label

    def set(self, key, value):
        label = self._values.get(key)
        if label is not None:
            try:
                label.configure(text=str(value))
            except Exception:
                pass


# --------------------------------------------------------------------------
# StatCard - jedna volitelna statistika na stranke Dnes (mriezka 2x2)
# --------------------------------------------------------------------------

class StatCard(ctk.CTkFrame):
    """Karta jednej metriky: VELKE farebne cislo a pod nim jednoslovny
    popisok. ⓘ rozbali kratke vysvetlenie, ✕ (len pri hoveri nad kartou) ju
    odstrani z vyberu. Kartu mozno chytit (cislo, popisok alebo okraj - nie
    ⓘ/✕) a pustit na inu: vymenia si miesto (`on_drag`, rozhoduje appka).

    Farba cisla je identita metriky - rovnaka farba ako bodka vo vybere v
    `_build_dnes_page`, takze si hrac vie kartu a polozku vo vybere spojit
    aj bez citania textu. Drzi sa ako TOKEN palety, nie ako hodnota: pri
    zmene temy si ju karta vie najst sama (`set_pal`).

    PRECO CISLO HORE A POPISOK DOLE
    -------------------------------
    Do 2.1 to bolo naopak: hore popisok (`metric.*.title`, cela veta typu
    "POKOJOVA ZAKLADNA"), pod nim cislo, pod nim druhy riadok a vpravo
    mikrograf. Malo to dva problemy naraz:
      - Karta sa citala ako riadok tabulky, nie ako jeden udaj.
      - `title` je dlhy a v nemcine, francuzstine a rustine rozsiril cely
        pravy stlpec na ukor stredu, kde je znacka. Odmerane: stred klesol
        zo 659 na 554 px, teda az o 105 px, a text sa pritom NEorezal -
        zaplatila to znacka.
    Teraz nesie popisok kluc `metric.*.tag` - jedno slovo ("pokoj",
    "zotavenie"), ktore nerastie s jazykom.

    ⓘ tym ZOSTAVA DOLEZITEJSIE, nie menej: "POKOJ" samo o sebe nepovie, o
    co ide, a plati to vo vsetkych jazykoch.

    POZN: mikrograf poslednych relacii a veta o odchylke odtialto odisli
    (`set_trend`, `MicroChart`). Bola to poctiva myslienka - "62 BPM"
    nehovori nic, kym clovek nevie, co je uneho bezne - ale na karte, ktora
    ma byt jeden pokojny udaj, to boli tri udaje. Trend patri do Historie,
    kde je na to cely graf.
    """

    def __init__(self, master, pal, color_token, tag, value, info_text,
                on_remove=None, on_drag=None):
        super().__init__(master, fg_color=pal["surface"], corner_radius=RADIUS_PANEL,
                         border_width=1, border_color=pal["line_soft"])
        self.pal = pal
        self.color_token = color_token

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=13, pady=11)

        self.value_label = ctk.CTkLabel(body, text=str(value), font=display(22),
                                        text_color=pal[color_token], anchor="w")
        self.value_label.pack(fill="x")

        # Popisok a ovladace su v jednom riadku POD cislom. ✕ je vpravo,
        # ⓘ hned za textom - patri k popisku, nie do rohu.
        head = ctk.CTkFrame(body, fg_color="transparent")
        head.pack(fill="x", pady=(2, 0))
        self.tag_label = ctk.CTkLabel(head, text=tag.upper(), font=ui(10, "bold"),
                                      text_color=pal["text_faint"], anchor="w")
        self.tag_label.pack(side="left")
        self._info_btn = ctk.CTkButton(
            head, text="ⓘ", width=16, height=16, corner_radius=8,
            fg_color="transparent", hover_color=pal["surface_alt"],
            text_color=pal["text_faint"], font=ui(10), command=self._toggle_info)
        self._info_btn.pack(side="left", padx=(5, 0))

        self._remove_btn = None
        if on_remove is not None:
            self._remove_btn = ctk.CTkButton(
                head, text="✕", width=16, height=16, corner_radius=8,
                fg_color="transparent", hover_color=pal["surface_alt"],
                text_color=pal["text_faint"], font=ui(10), command=on_remove)
        # Enter/Leave vzdy: ukaze ✕ (ak je) a hlavne zavrie ⓘ popup, ked
        # kurzor opusti kartu.
        for widget in (self, body, head):
            widget.bind("<Enter>", self._on_enter)
            widget.bind("<Leave>", self._on_leave)

        # Vysvetlenie ⓘ sa uz NEROZBALUJE v karte, ale ukazuje v plavajucom
        # popupe. Inline rozbalenie totiz rastie kartu -> mriezku statistik ->
        # a kedze stred (dojo/enso) je v tom istom riadku mriezky, cely hrdina
        # sa pri kliknuti na ⓘ zrazu zvacsil (najma v rustine/nemcine, kde je
        # text dlhy). Popup nema na rozlozenie stranky ziadny vplyv.
        self._info_text = info_text
        self._info_pop = None
        self.bind("<Destroy>", lambda _e: self._close_info())

        # Presun potiahnutim. Karta len HLASI stlacenie / pohyb / pustenie;
        # co s tym (vymena, ulozenie) rozhoduje appka. Viaze sa len na plochy
        # karty, NIKDY na ⓘ a ✕ - tie su tlacidla a musia klikat normalne.
        # Tk po stlaceni posiela pohyb aj pustenie widgetu, ktory dostal
        # stlacenie (implicitny grab), takze netreba globalny grab.
        if on_drag is not None:
            def _press(event):
                self._close_info()
                on_drag("press", event)
            for widget in (self, body, head, self.value_label, self.tag_label):
                widget.bind("<ButtonPress-1>", _press)
                widget.bind("<B1-Motion>", lambda e: on_drag("move", e))
                widget.bind("<ButtonRelease-1>", lambda e: on_drag("release", e))

    def set_drag_look(self, role=None):
        """Okraj pocas tahania: 'source' = karta, ktoru drzis, 'target' =
        karta, s ktorou si vymeni miesto. None = bezny okraj."""
        color = {"source": "accent", "target": "accent_hover"}.get(role, "line_soft")
        try:
            self.configure(border_color=self.pal[color])
        except Exception:
            pass

    def set_value(self, value):
        try:
            self.value_label.configure(text=str(value))
        except Exception:
            pass

    def set_pal(self, pal):
        """Cislo si farbu drzi ako hodnotu, nie ako volbu widgetu - po zmene
        temy si ju musi vziat z novej palety samo."""
        self.pal = pal
        try:
            self.value_label.configure(text_color=pal[self.color_token])
        except Exception:
            pass

    def _toggle_info(self):
        if self._info_pop is not None:
            self._close_info()
            return
        pop = priprav_popup(tk.Toplevel(self))
        pop.overrideredirect(True)
        pop.attributes("-topmost", True)
        pop.configure(bg=self.pal["line_soft"])
        frame = ctk.CTkFrame(pop, fg_color=self.pal["surface_alt"], corner_radius=8,
                             border_width=1, border_color=self.pal["line_soft"])
        frame.pack(fill="both", expand=True, padx=1, pady=1)
        ctk.CTkLabel(frame, text=self._info_text, font=ui(10),
                     text_color=self.pal["text_dim"], anchor="w", justify="left",
                     wraplength=250).pack(padx=12, pady=10)
        self._info_pop = pop
        pop.update_idletasks()
        bx = self._info_btn.winfo_rootx()
        by = self._info_btn.winfo_rooty() + self._info_btn.winfo_height() + 4
        try:
            pw, ph = pop.winfo_reqwidth(), pop.winfo_reqheight()
            sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
            if bx + pw > sw - 8:
                bx = max(8, sw - pw - 8)
            if by + ph > sh - 8:            # nezmesti sa dole -> vysun nad tlacidlo
                by = max(8, self._info_btn.winfo_rooty() - ph - 4)
        except Exception:
            pass
        pop.geometry(f"+{int(bx)}+{int(by)}")
        # Zavri popup, ked strati zameranie (klik inam, paleta Ctrl+K,
        # minimalizacia do listy) alebo ked nan clovek klikne. Stranky sa
        # neprestavuju (place+tkraise), takze bez tohto by popup pri prepnuti
        # bez pohybu mysou ostal plavat nad novou strankou ci plochou.
        pop.bind("<FocusOut>", lambda _e: self._close_info())
        pop.bind("<Button-1>", lambda _e: self._close_info())
        try:
            pop.focus_set()
        except Exception:
            pass

    def _close_info(self):
        pop, self._info_pop = self._info_pop, None
        if pop is not None:
            try:
                pop.destroy()
            except Exception:
                pass

    def _on_enter(self, _event=None):
        if self._remove_btn is not None and not self._remove_btn.winfo_ismapped():
            self._remove_btn.pack(side="right")

    def _on_leave(self, _event=None):
        # Leave prichadza aj pri prechode na vlastne diet'a - reaguj az ked
        # kurzor naozaj opustil celu kartu (rovnaky trik ako _NavRow._leave).
        if self._still_inside():
            return
        if self._remove_btn is not None:
            self._remove_btn.pack_forget()
        self._close_info()

    def _still_inside(self):
        try:
            px, py = self.winfo_pointerxy()
            x0, y0 = self.winfo_rootx(), self.winfo_rooty()
            return (x0 <= px < x0 + self.winfo_width()
                    and y0 <= py < y0 + self.winfo_height())
        except Exception:
            return False


# --------------------------------------------------------------------------
# QrReveal - znacka QR, ktora kod odkryje az na klik
# --------------------------------------------------------------------------

class QrReveal(ctk.CTkFrame):
    """Piktogram QR + popisok; skutocny kod sa rozbali POD nim az na klik.

    Skutocny QR musi byt biely stvorec s ostrymi modulmi, inak ho telefon
    neprecita - a biely stvorec je v tmavom paneli to najkriklavejsie, co
    tam moze byt. Pritom ho vacsina ludi ani nepotrebuje: kto appku v
    telefone uz ma, kod nechce vidiet vobec. Navonok je preto len znacka
    kreslena rovnakym stetcom ako ostatne piktogramy appky
    (`hud_paint.render_slot_icon("qr")`), v akcente temy.

    Obrazok sa nacita az pri prvom otvoreni - kym nikto neklikne, appka
    subor ani neotvori.
    """

    ICON = 40

    def __init__(self, master, pal, codes, show_label, hide_label, size=150):
        """`codes` je [(cesta k PNG, popisok)] - kolko kodov, tolko stlpcov
        vedla seba (Android a iOS su dve rozne appky, teda dva kody)."""
        super().__init__(master, fg_color="transparent")
        self.pal = pal
        self._codes = [c for c in codes if c and os.path.exists(c[0])]
        self._size = size
        self._show_label, self._hide_label = show_label, hide_label
        self._open = False
        self._built = False
        self._photos = []
        self._captions = []

        self.toggle = ctk.CTkButton(
            self, text="  " + show_label, image=self._icon(pal), compound="left",
            anchor="w", height=self.ICON + 10, corner_radius=RADIUS_CONTROL,
            fg_color="transparent", hover_color=pal["surface_alt"],
            text_color=pal["accent_hover"], font=ui(11), command=self._flip)
        self.toggle.pack(anchor="w")

        self.holder = ctk.CTkFrame(self, fg_color="transparent")

    def _icon(self, pal):
        try:
            import hud_paint      # lazy: ui_kit sa importuje aj bez GUI
            img = hud_paint.render_slot_icon("qr", self.ICON, hud_paint.Style(pal))
            self._icon_photo = ctk.CTkImage(light_image=img, dark_image=img,
                                            size=(self.ICON, self.ICON))
            return self._icon_photo
        except Exception:
            return None

    def _build_codes(self):
        """Kody sa nacitaju a postavia az pri prvom otvoreni - kym nikto
        neklikne, appka subory ani neotvori."""
        from PIL import Image as PILImage
        pal = self.pal
        for cesta, popis in self._codes:
            stlpec = ctk.CTkFrame(self.holder, fg_color="transparent")
            stlpec.pack(side="left", anchor="n", padx=(0, 16))
            img = PILImage.open(cesta).convert("RGB")
            photo = ctk.CTkImage(light_image=img, dark_image=img,
                                 size=(self._size, self._size))
            self._photos.append(photo)          # drz referenciu, inak GC
            ctk.CTkLabel(stlpec, text="", image=photo).pack(anchor="w",
                                                            pady=(6, 4))
            popisok = ctk.CTkLabel(stlpec, text=popis, font=ui(10),
                                   text_color=pal["text_faint"], anchor="w",
                                   justify="left", wraplength=self._size + 30)
            popisok.pack(anchor="w")
            self._captions.append(popisok)

    def _flip(self):
        if self._open:
            self.holder.pack_forget()
            self.toggle.configure(text="  " + self._show_label)
            self._open = False
            return
        # vlastny priznak, nie `winfo_children()` - `holder` moze mat deti
        # uz od konstruktora a test "nema deti" by nikdy neplatil (stalo sa)
        if not self._built:
            try:
                self._build_codes()
            except Exception:
                return      # chybajuci obrazok nesmie zhodit dialog
            self._built = True
        self.holder.pack(fill="x", anchor="w")
        self.toggle.configure(text="  " + self._hide_label)
        self._open = True

    def set_pal(self, pal):
        """Znacka je obrazok s farbou zapecenou dovnutra - po zmene temy ju
        treba prekreslit (`DandurfApp._recolor_ui` prejde strom sam)."""
        self.pal = pal
        try:
            self.toggle.configure(image=self._icon(pal),
                                  text_color=pal["accent_hover"],
                                  hover_color=pal["surface_alt"])
            for popisok in self._captions:
                popisok.configure(text_color=pal["text_faint"])
        except Exception:
            pass


# --------------------------------------------------------------------------
# SubNav - karty v hornej casti skupinovej stranky (Nastavenia)
# --------------------------------------------------------------------------

class SubNav(ctk.CTkFrame):
    """Rad kariet nad obsahom - Spustace | Zvuk | Vseobecne.

    Bocne menu ma po feedbacku len 3 hlavne polozky; vsetko ostatne su
    karty tu. Kazda karta ma kluc, ktory je zaroven kluc stranky, takze
    `app.navigate(key)` funguje pre karty rovnako ako pre hlavne polozky.
    Odznak (pocet spustacov, bodka senzora) sa pripaja k textu karty.

    KARTY SU TEXT, NIE CHIPY (0.2.2, audit UX). Oramovany chip v appke
    znamenal styri rozne veci naraz (karta, filter, akcia, odkaz), takze
    karty nevyzerali ako karty. Teraz je karta holy text a aktivnu nesie
    2 px linka v `accent` pod nou plus plny `text` - dva signaly, nie len
    farba. Lavu hranu radu urcuje volajuci (`PAGE_GUTTER`)."""

    LINE_H = 2

    def __init__(self, master, pal, items, on_select):
        """items: [(key, label)]"""
        super().__init__(master, fg_color="transparent")
        self.pal = pal
        self.on_select = on_select
        self.buttons = {}
        self._lines = {}
        self._labels = {}
        self._badges = {}
        self.active = None
        for poradie, (key, label) in enumerate(items):
            tab = ctk.CTkFrame(self, fg_color="transparent", width=1, height=1)
            # prva karta zacina presne na lavej hrane stranky, dalsie maju
            # medzi sebou 20 px - text bez ramu potrebuje vzduch, nie ram
            tab.pack(side="left", padx=(0 if poradie == 0 else 20, 0))
            btn = ctk.CTkButton(
                tab, text=label, height=30, width=0, corner_radius=RADIUS_CONTROL,
                border_width=0, fg_color="transparent",
                hover_color=pal["surface_alt"], text_color=pal["text_dim"],
                font=ui(13), command=lambda k=key: self.select(k))
            btn.pack(side="top")
            # width=1: CTkFrame si inak pyta predvolenych 200 px a kazda
            # karta by bola siroka 200 px bez ohladu na text
            line = ctk.CTkFrame(tab, fg_color="transparent", height=self.LINE_H,
                                width=1, corner_radius=0)
            line.pack(side="top", fill="x", padx=8)
            self.buttons[key] = btn
            self._lines[key] = line
            self._labels[key] = label

    def select(self, key, notify=True):
        self.set_active(key)
        if notify and callable(self.on_select):
            self.on_select(key)

    def set_active(self, key):
        self.active = key
        pal = self.pal
        for k, btn in self.buttons.items():
            active = (k == key)
            try:
                btn.configure(text_color=pal["text"] if active else pal["text_dim"])
                self._lines[k].configure(
                    fg_color=pal["accent"] if active else "transparent")
            except Exception:
                pass

    def set_pal(self, pal):
        """Prefarbi linku aj text aktivnej karty z novej palety (pri zmene
        temy) - aktivny stav sa pocita z `self.pal`, nie z widgetu."""
        self.pal = pal
        self.set_active(self.active)

    def set_badge(self, key, text=""):
        btn = self.buttons.get(key)
        if btn is None:
            return
        self._badges[key] = str(text or "")
        suffix = f"   {self._badges[key]}" if self._badges[key] else ""
        try:
            btn.configure(text=f"{self._labels[key]}{suffix}")
        except Exception:
            pass


# --------------------------------------------------------------------------
# Info riadok k metrike: veta pri cisle + rozbalitelne "co to znamena"
# --------------------------------------------------------------------------

class InfoRow(ctk.CTkFrame):
    """Kratky text pod metrikou a prepinac "ⓘ co to znamena", ktory rozbali
    2-3 vety pre hraca. Texty su v i18n (metric.<id>.short / .more) - tu sa
    len skladaju; ziadna logika appky.

    Preco rozbalovanie a nie tooltip: tooltip vidno len s mysou nad
    otaznikom a hrac ho vacsinou nikdy nenajde. Veta pri cisle je vzdy
    vidno, podrobnosti su na jeden klik a ostanu otvorene."""

    def __init__(self, master, pal, short, more, more_label, less_label, wrap=420,
                 title=None):
        super().__init__(master, fg_color="transparent")
        self.pal = pal
        self._more_label, self._less_label = more_label, less_label
        self._open = False
        # Meno metriky nad vetou (volitelne): tri vysvetlivky pod sebou bez
        # mena boli tri rovnake "ⓘ co to znamena" bez adresata.
        if title:
            ctk.CTkLabel(self, text=title, font=ui(11, "bold"), text_color=pal["text"],
                         anchor="w", justify="left", wraplength=wrap).pack(fill="x")
        # Veta je obsah, nie dekoracia - `text_dim` (>= 4,5:1).
        ctk.CTkLabel(self, text=short, font=ui(11), text_color=pal["text_dim"],
                     anchor="w", justify="left", wraplength=wrap).pack(fill="x")
        self.toggle = ctk.CTkButton(
            self, text=more_label, height=22, corner_radius=RADIUS_CONTROL, anchor="w",
            fg_color="transparent", hover_color=pal["surface_alt"],
            text_color=pal["accent_hover"], font=ui(10), command=self._flip)
        self.toggle.pack(anchor="w", pady=(2, 0))
        self.more = ctk.CTkLabel(self, text=more, font=ui(11), text_color=pal["text_dim"],
                                 anchor="w", justify="left", wraplength=wrap)

    def _flip(self):
        self._open = not self._open
        if self._open:
            self.more.pack(fill="x", pady=(2, 4))
            self.toggle.configure(text=self._less_label)
        else:
            self.more.pack_forget()
            self.toggle.configure(text=self._more_label)

    @property
    def is_open(self):
        return self._open


# --------------------------------------------------------------------------
# Vlastna listka pre dialogy (bez OS ramu)
# --------------------------------------------------------------------------

DIALOG_RAM_TOKEN = "rule"


def nastav_ram_okna(top, pal):
    """1 px ram okolo okna dialogu vo farbe `pal[DIALOG_RAM_TOKEN]`.

    Tk `highlightthickness` na samotnom okne: ram je VNUTRI okna a obsah
    (pack) ide az za nim, takze ho nic neprekryje. `highlightcolor` (okno
    s fokusom) aj `highlightbackground` (bez fokusu) maju tu istu farbu -
    ram sa pri kliknuti nemeni. Volane cez `tk.Misc.configure`, lebo
    `CTkToplevel.configure` `highlightcolor` nepozna. Nikdy nevyhodi
    vynimku."""
    try:
        farba = pal[DIALOG_RAM_TOKEN]
        tk.Misc.configure(top, highlightthickness=1, highlightbackground=farba,
                          highlightcolor=farba)
    except Exception:
        pass


class DialogChrome:
    """Da dialogu (CTkToplevel) vlastnu listku ako ma hlavne okno.

    Preco to je
    -----------
    Hlavne okno appky bezi bez OS ramu (overrideredirect=True) s vlastnou
    listkou. Dialogy vsak boli obycajne CTkToplevel S OS ramom, takze nad
    "O aplikacii" a spol. presvital Windows titulok - prvok, ktory pri
    hlavnom okne nie je, takze posobil cudzo.

    Riesenie je rovnake ako pri hlavnom okne: overrideredirect(True) +
    vlastna listka s nazvom a tlacidlom zavriet + tahanie za nu. Aby modalny
    dialog (grab_set) s vypnutym ramom fungoval spolahlivo, obnovujeme
    override po kazdom <Map> (rovnaky vzor ako enable_frameless pre root).

    POZOR PRI OVERENI NA WINDOWS: bezramove modalne okno je v Tk jemne.
    Over, ze sa da tahat za listku, ze ho ide zavriet krizikom aj Escape, a
    ze po minimalizovani hlavneho okna a navrate dialog nezmizne. Ak by
    override na modalnom okne robil problem (okno bez fokusu / neda sa
    tahat), zmen `_FRAMELESS` nizsie na False - dialog potom ostane s OS
    ramom (kozmeticky horsie, ale spolahlive).
    """

    _FRAMELESS = True    # False = nechaj OS ram (fallback, ak override zlobi)

    def __init__(self, top, pal, title, on_close, closable=True):
        """`closable=False` = bez krizika a bez Escape - pre okna, ktore sa
        nesmu zavriet "do prazdna" (onboarding). `on_close` sa vtedy nevola."""
        self.top = top
        self.pal = pal
        self.on_close = on_close
        self.closable = bool(closable)
        self.close_btn = None
        self._drag = None

        if self._FRAMELESS:
            try:
                top.overrideredirect(True)
                # obnov override po navrate z minimalizacie (ako root)
                # a po kazdom zobrazeni znova pripni k hlavnemu oknu - Tk pri
                # obnove overrideredirect vlastnika zahadzuje
                top.bind("<Map>", lambda _e: (top.overrideredirect(True),
                                              pripni_k_vlastnikovi(top)), add="+")
            except Exception:
                pass

        # RAM OKNA 1 px (0.2.2 davka 4b). Okno bez OS ramu malo pozadie `bg`
        # ako hlavne okno za nim - dialog nad tmavou appkou nemal hranu a
        # splyval s nou. `rule` je token hrany plochy (>= 1,5:1, viz
        # theme.py), nie ovladaca: ram okna nema vyzerat ako tlacidlo.
        # Kresli ho samo Tk okno (highlight), takze ide okolo vsetkeho
        # obsahu a nezavisi od toho, co do okna kto zabali.
        nastav_ram_okna(top, pal)

        bar = ctk.CTkFrame(top, fg_color=pal["bg"], height=34, corner_radius=0)
        bar.pack(fill="x", side="top")
        bar.pack_propagate(False)
        self.bar = bar

        # POZOR: velkost pisma MUSI byt cislo, nie retazec. customtkinter ju
        # pri skalovani nasobi floatom, takze ui("11") skonci na
        # TypeError: can't multiply sequence by non-int of type 'float'
        # a cely dialog sa neotvori.
        self.title_label = ctk.CTkLabel(bar, text=title, font=ui(11),
                                        text_color=pal["text_dim"], anchor="w")
        self.title_label.pack(side="left", padx=14)
        if self.closable:
            self.close_btn = ctk.CTkButton(
                bar, text="✕", width=40, height=34, corner_radius=0,
                fg_color="transparent", hover_color=pal["danger"],
                text_color=pal["text_dim"], font=ui(12), command=on_close)
            self.close_btn.pack(side="right")

        rule = linka(top, pal)
        rule.pack(fill="x", side="top")

        # tahanie za listu - aj za jej popisok (label prekryva vacsinu listy)
        for widget in (bar, self.title_label):
            widget.bind("<ButtonPress-1>", self._begin)
            widget.bind("<B1-Motion>", self._move)
        # Escape zavrie dialog (aj ked nema OS krizik). Samotny bind ale
        # NESTACI: klavesy chodia tomu oknu, ktore ma fokus, a ten po
        # otvoreni ostaval na hlavnom okne - Escape sa sem teda nikdy
        # nedostal. Fokus nastavujeme s malym odkladom, lebo CTkToplevel sa
        # v __init__ sam withdrawne a znova deiconifikuje (kvoli tmavej
        # titulkovej liste) a okamzity focus_force by ten trik prebil.
        def _take_focus():
            try:
                pripni_k_vlastnikovi(top)   # inak ho hlavne okno moze prekryt
                top.lift()
                top.focus_force()
            except Exception:
                pass          # dialog uz medzitym zavreli

        try:
            if self.closable:
                top.bind("<Escape>", lambda _e: on_close())
            top.after(10, _take_focus)
        except Exception:
            pass

        # POLOHA (0.2.2, audit UX). Dialog, ktory si rozmer neurcil sam cez
        # `umiestni_dialog` (velkost mu dava obsah: novy profil, import,
        # nahravanie, vyber farby...), sa po postaveni obsahu vycentruje v
        # pracovnej ploche monitora pod kurzorom. Bezramove okno bez polohy
        # Tk polozi do laveho horneho rohu hlavneho monitora.
        def _vycentruj():
            if not getattr(top, "_zanshin_umiestnene", False):
                vycentruj_podla_obsahu(top)

        try:
            top.after(15, _vycentruj)
        except Exception:
            pass

        self.body = ctk.CTkFrame(top, fg_color="transparent")
        self.body.pack(fill="both", expand=True)

    def _begin(self, event):
        self._drag = (event.x_root, event.y_root,
                      self.top.winfo_x(), self.top.winfo_y())

    def _move(self, event):
        if not self._drag:
            return
        sx, sy, wx, wy = self._drag
        self.top.geometry(f"+{wx + event.x_root - sx}+{wy + event.y_root - sy}")


# --------------------------------------------------------------------------
# Okna appky namiesto systemovych (confirm / notify / choose)
# --------------------------------------------------------------------------
#
# PRECO (0.2.2, audit UX): biele systemove okno v tmavej appke malo tlacidla
# v jazyku Windows ("Ano / Nie"), nie appky, a vyzeralo ako cudzi program.
# Vsetky tri funkcie stavaju to iste okno (`_okno_appky`): vlastna listka
# (DialogChrome), text zalomeny na DIALOG_TEXT_W, tlacidla vpravo dole,
# stred pracovnej plochy a cele na nej. Systemove okno ostava len ZALOHA -
# ked sa okno appky postavit neda (ziadne hlavne okno, TclError).

DIALOG_TEXT_W = 440       # zlom textu v okne appky (logicke px)
DIALOG_MIN_W = 400        # kratky oznam nema byt uzky prúžok


class _OknoSaNedaPostavit(Exception):
    """Okno appky sa postavit neda - volajuci ukaze systemove okno."""


def _systemove_okno(druh, title, text):
    """ZALOHA: systemove okno Windows. `druh` "yesno" vrati True/False,
    "warning" / "error" / "info" vrati None. Nikdy nevyhodi vynimku."""
    try:
        if druh == "yesno":
            return bool(messagebox.askyesno(title, text))
        {"warning": messagebox.showwarning,
         "error": messagebox.showerror}.get(druh, messagebox.showinfo)(title, text)
    except Exception:
        pass
    return False if druh == "yesno" else None


def _vlastnik_pouzitelny(owner):
    """Da sa nad `owner` postavit viditelne modalne okno?

    Bez hlavneho okna nie. A ani nad oknom schovanym v liste: `transient`
    zdedi stav vlastnika, takze dialog by ostal schovany s grabom - appka
    by cakala na odpoved, ktoru nikto nevidi. Atrapa bez tychto metod
    (testy) sa berie ako pouzitelna."""
    if owner is None:
        return False
    try:
        if hasattr(owner, "winfo_exists") and not owner.winfo_exists():
            return False
        if hasattr(owner, "winfo_viewable") and not owner.winfo_viewable():
            return False
    except Exception:
        return False
    return True


def _okno_appky(owner, pal, title, text, tlacidla, zrusit, fokus):
    """Modalne okno appky s textom a tlacidlami; vrati hodnotu kliknuteho.

    `tlacidla` = [(hodnota, text, druh), ...] zlava doprava, `druh` z
    `BUTTON_KINDS`. Escape, krizik aj zlyhane cakanie = `zrusit`. Enter
    stlaci tlacidlo s fokusom - a fokus po otvoreni stoji na tom s hodnotou
    `fokus` (to bezpecne: Enter omylom nesmie zmazat ani ukoncit).

    Ked sa okno postavit neda, vyhodi `_OknoSaNedaPostavit`."""
    if pal is None or not _vlastnik_pouzitelny(owner):
        raise _OknoSaNedaPostavit("bez pouzitelneho hlavneho okna")
    vysledok = {"hodnota": zrusit}
    top = None
    hotove = []               # (hodnota, tlacidlo) sprava dolava

    def zavri(hodnota):
        vysledok["hodnota"] = hodnota
        try:
            top.grab_release()
        except Exception:
            pass
        try:
            top.destroy()
        except Exception:
            pass

    try:
        top = ctk.CTkToplevel(owner)
        top.title(title)
        top.configure(fg_color=pal["bg"])
        top.resizable(False, False)
        top.protocol("WM_DELETE_WINDOW", lambda: zavri(zrusit))
        chrome = DialogChrome(top, pal, title, on_close=lambda: zavri(zrusit))
        # Paticka sa packuje PRVA a k spodku: ked je text vyssi, nez sa na
        # plochu zmesti, oreze sa text, nie tlacidla.
        paticka = ctk.CTkFrame(chrome.body, fg_color="transparent")
        paticka.pack(side="bottom", fill="x", padx=24, pady=(0, 18))
        telo = ctk.CTkFrame(chrome.body, fg_color="transparent")
        telo.pack(fill="both", expand=True, padx=24, pady=(18, 16))
        ctk.CTkLabel(telo, text=text, font=ui(12), text_color=pal["text"],
                     anchor="w", justify="left",
                     wraplength=DIALOG_TEXT_W).pack(fill="x")
        for hodnota, popis, druh in reversed(list(tlacidla)):
            tlacidlo = button(paticka, pal, popis, kind=druh,
                              command=lambda h=hodnota: zavri(h))
            tlacidlo.pack(side="right", padx=(0, 8) if hotove else 0)
            hotove.append((hodnota, tlacidlo))
    except Exception as exc:
        if top is not None:
            try:
                top.destroy()
            except Exception:
                pass
        raise _OknoSaNedaPostavit(str(exc)) from exc

    def enter(_e=None):
        try:
            meno = str(top.focus_get() or "")
        except Exception:
            meno = ""
        for hodnota, tlacidlo in hotove:
            cesta = str(tlacidlo)
            if meno and (meno == cesta or meno.startswith(cesta + ".")):
                zavri(hodnota)
                return "break"
        zavri(fokus)
        return "break"

    def umiestni():
        # Rozmer dava obsah; `umiestni_dialog` ho zmensi na pracovnu plochu
        # a polozi na jej stred (inak by okno bez ramu stalo v rohu).
        top.update_idletasks()
        try:
            mierka = float(top._get_window_scaling() or 1.0)
        except Exception:
            mierka = 1.0
        sirka = int(top.winfo_reqwidth() / mierka) + 1
        vyska = int(top.winfo_reqheight() / mierka) + 1
        umiestni_dialog(top, owner, max(sirka, DIALOG_MIN_W), vyska)

    fokus_tlacidlo = next((t for h, t in hotove if h == fokus), None)
    # Oznam nad INYM modalnym dialogom (nahravanie, nastavenia hlasky) mu
    # grab vezme; po zavreti ho treba vratit, inak by ten dialog prestal
    # byt modalny. Systemovy messagebox to robil sam.
    try:
        predosly_grab = top.grab_current()
    except Exception:
        predosly_grab = None
    # Kazdy krok zvlast: ked zlyha len `grab_set` (iny grab, okno este nie je
    # namapovane), dialog uz na obrazovke JE - keby sa hned vratilo `zrusit`,
    # ostal by tam s tlacidlom, ktore nic neurobi. Bez grabu je dialog len
    # nemodalny, na odpoved sa aj tak pocka.
    kroky = [lambda: top.bind("<Return>", enter),
             lambda: top.bind("<KP_Enter>", enter),
             umiestni,
             lambda: top.transient(owner), top.grab_set]
    if fokus_tlacidlo is not None:
        kroky.append(lambda: top.after(30, fokus_tlacidlo.focus_set))
    for krok in kroky:
        try:
            krok()
        except Exception:
            pass
    try:
        owner.wait_window(top)
    except Exception:
        zavri(zrusit)         # nepockali sme - neviditelne "ano" nesmie ostat
        return zrusit
    if predosly_grab is not None:
        try:
            if predosly_grab.winfo_exists():
                predosly_grab.grab_set()
        except Exception:
            pass
    return vysledok["hodnota"]


def confirm(owner, pal, title, text, ok_label, cancel_label, danger=False):
    """Otazka ano/nie v okne appky (DialogChrome), nie systemovy messagebox.

    Tlacidla nesu sloveso akcie (`ok_label`), destruktivna akcia je
    `danger`, nie hlavne tlacidlo. Fokus aj Enter su na "nie" (`cancel_label`)
    - Enter omylom nesmie zmazat. Escape aj krizik = nie. Modalne: vrati
    True/False az po zavreti. Ked sa okno appky postavit neda, opyta sa
    systemovym oknom."""
    try:
        return bool(_okno_appky(
            owner, pal, title, text,
            [(True, ok_label, "danger" if danger else "primary"),
             (False, cancel_label, "secondary")],
            zrusit=False, fokus=False))
    except _OknoSaNedaPostavit:
        return _systemove_okno("yesno", title, text)


def notify(owner, pal, title, text, ok_label=None, kind="info"):
    """Oznam v okne appky namiesto messagebox.showinfo / showwarning /
    showerror. Jedno tlacidlo (`ok_label`, inak "OK" v jazyku appky);
    Enter, Escape aj krizik ho zavru. Modalne - vrati sa po zavreti.

    `kind` ("info" / "warning" / "error") rozhoduje len o systemovom okne,
    ktore sa ukaze, ked sa okno appky postavit neda. Okno appky vyzera pre
    vsetky tri rovnako: pokojne, bez vykricnika - zavaznost nesie veta."""
    if ok_label is None:
        try:
            from i18n import tr
            ok_label = tr("dialog.ok")
        except Exception:
            ok_label = "OK"
    try:
        _okno_appky(owner, pal, title, text, [(True, ok_label, "primary")],
                    zrusit=None, fokus=True)
    except _OknoSaNedaPostavit:
        _systemove_okno(kind, title, text)


def choose(owner, pal, title, text, choices, cancel=None, default=None):
    """Volba z viacerych tlacidiel v okne appky.

    `choices` = [(hodnota, text, druh), ...] zlava doprava. Escape a krizik
    vratia `cancel` (nic sa nedeje), Enter a fokus po otvoreni patria
    `default`. Ked sa okno appky postavit neda, povie text systemovym oknom
    a vrati `default` - bezpecnu volbu, ktora nic nezmaze ani neukonci."""
    try:
        return _okno_appky(owner, pal, title, text, choices,
                           zrusit=cancel, fokus=default)
    except _OknoSaNedaPostavit:
        _systemove_okno("info", title, text)
        return default


# --------------------------------------------------------------------------
# Blokovanie kolieska na slideroch
# --------------------------------------------------------------------------

def block_slider_wheel(slider):
    """Zabrani slideru menit hodnotu kolieskom mysi.

    Preco to je
    -----------
    CTkSlider standardne reaguje na koliesko mysi. Lenze slidery byvaju v
    scrollovatelnych stránkach (napr. detail slotu, nastavenia vizualov) -
    ked chce hrac len posunut obsah nizsie a kurzor mu pritom prejde nad
    sliderom, omylom zmeni hodnotu. Klasicky "ukradnuty scroll".

    Riesenie: na slideri zachytime wheel udalosti a namiesto zmeny hodnoty
    ich POSUNIEME na rodicovsky scrollframe (aby sa stránka aj tak
    scrollovala). Slider sa tak da menit uz len tahanim, presne ako ma.

    Kryje Windows/Mac (<MouseWheel>) aj Linux/X11 (<Button-4/5>).

    PRECO SA VIAZE NA `slider._canvas`, NIE CEZ `slider.bind()`
    ----------------------------------------------------------
    `CTkSlider.bind()` vzdy PRIDAVA (add=True) a zamerne odmieta cokolvek
    ine, takze interny handler kolieska (`_mouse_scroll_event`) ostane prvy
    v poradi. Tk vykona handlery jedneho widgetu v poradi pridania - interny
    hodnotu ZMENIL skor, nez sa nas `return "break"` vobec dostal na rad.
    Overene nazivo (ctk 6.0, Tk 9.0): koliesko menilo hodnotu aj s obalom.
    Obycajny `tkinter.Canvas.bind` bez `add` interny handler nahradi.
    """
    def _redirect(event):
        widget = slider.master
        # najdi najblizsi rodicovsky canvas scrollframu a posun ho
        while widget is not None:
            if isinstance(widget, ctk.CTkScrollableFrame):
                canvas = getattr(widget, "_parent_canvas", None)
                if canvas is not None:
                    try:
                        # rovnake kroky ako CTkScrollableFrame: na Windows ma
                        # canvas yscrollincrement=1 px, takze 1 "unit" na
                        # notch by stranku prakticky nepohol
                        if getattr(event, "num", None) == 4:
                            canvas.yview_scroll(-1, "units")
                        elif getattr(event, "num", None) == 5:
                            canvas.yview_scroll(1, "units")
                        elif sys.platform.startswith("win"):
                            canvas.yview_scroll(-int(event.delta / 6), "units")
                        elif sys.platform == "darwin":
                            canvas.yview_scroll(-int(event.delta), "units")
                        else:
                            canvas.yview_scroll(int(-event.delta / 120), "units")
                    except Exception:
                        pass
                break
            widget = getattr(widget, "master", None)
        return "break"      # NIKDY nenechaj slider spracovat koliesko

    canvas = getattr(slider, "_canvas", None)
    for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
        if canvas is not None:
            canvas.bind(seq, _redirect)      # NAHRADI interny handler
        else:
            slider.bind(seq, _redirect)
    return slider


def slider(master, pal, **kw):
    """Jediny posuvnik appky: draha `switch_off`, vyplnena cast aj gombik
    `accent`, koliesko zablokovane (`block_slider_wheel`).

    PRECO (0.2.2, audit UX, davka 4): v okne "Doladit obrazky" mali posuvniky
    X/Y tmavu vypln `accent2` a posuvnik velkosti hned nad nimi zlatu - dva
    styly v jednej karte, a X/Y vyzerali vypnute. Rozmery a rozsah ide
    prepisat cez `kw`, farby len zamerne (napr. nevyplneny posuvnik v
    dotazniku, ktory az prvy dotyk zafarbi)."""
    style = {"progress_color": pal["accent"], "button_color": pal["accent"],
             "button_hover_color": pal["accent_hover"],
             "fg_color": pal["switch_off"]}
    style.update(kw)
    return block_slider_wheel(ctk.CTkSlider(master, **style))
