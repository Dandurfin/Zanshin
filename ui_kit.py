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
import tkinter as tk
from tkinter import font as tkfont

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


def fonts():
    """Nazvy pisiem - zisti sa raz, az ked existuje Tk root."""
    if not _resolved:
        _resolved["ui"] = _pick(_UI)
        _resolved["display"] = _pick(_DISPLAY)
        _resolved["mono"] = _pick(_MONO)
    return _resolved


def ui(size, weight="normal"):
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

        if title is not None:
            head = ctk.CTkFrame(self, fg_color="transparent", height=40)
            head.pack(fill="x", padx=16, pady=(11, 0))
            ctk.CTkLabel(head, text=title, font=ui(13, "bold"),
                         text_color=pal["text"]).pack(side="left")
            self.right_label = ctk.CTkLabel(head, text=right or "",
                                            font=mono(10), text_color=pal["text_faint"])
            self.right_label.pack(side="right")
            rule = ctk.CTkFrame(self, fg_color=pal["line_soft"], height=1,
                                corner_radius=0)
            rule.pack(fill="x", pady=(9, 0))

        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=16, pady=14)

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
                 note=None, note_wrap=560):
        super().__init__(master, fg_color="transparent")
        self.pack(fill="x")
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="x", pady=9)

        self.control = ctk.CTkFrame(inner, fg_color="transparent")
        self.control.pack(side="right", padx=(14, 0))

        if icon:
            self.icon = ctk.CTkLabel(inner, text=icon, width=self.ICON_W, anchor="w",
                                     font=ui(13), text_color=pal["text"])
            self.icon.pack(side="left")
        text_col = ctk.CTkFrame(inner, fg_color="transparent")
        text_col.pack(side="left", fill="x", expand=True)
        self.title_label = ctk.CTkLabel(text_col, text=title, font=ui(13),
                                        text_color=pal["text"], anchor="w", justify="left")
        self.title_label.pack(fill="x")
        # Vetu si drzime, aby sa dala prepisat, ked sa zmeni to, co
        # popisuje (ukazka zvuku ide za stylom hlasky).
        self.sub_label = None
        if sub:
            self.sub_label = ctk.CTkLabel(
                text_col, text=sub, font=ui(11), text_color=pal["text_faint"],
                anchor="w", justify="left", wraplength=wrap)
            self.sub_label.pack(fill="x", pady=(2, 0))

        self.note_label = None
        if note:
            self.note_label = ctk.CTkLabel(
                self, text=note, font=ui(10), text_color=pal["text_faint"],
                anchor="w", justify="left", wraplength=note_wrap)
            self.note_label.pack(fill="x", pady=(0, 9))

        ctk.CTkFrame(self, fg_color=pal["line_soft"], height=1,
                     corner_radius=0).pack(fill="x")


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
    """Jediny pohyblivy prvok v celom okne.

    Dycha v rovnakom rytme ako dychovy kruh v hre (5 s nadych, 5 s vydych) a
    ked je appka zastavena, stoji. Stav sa necita z odznaku ani z farby
    textu, ale z toho, ci sa rozhranie hybe - a je to zaroven hlavne
    tlacidlo, takze ziadne dalsie netreba.

    Animacia sa zastavi vzdy, ked okno nie je viditelne (minimalizovane do
    listy) - appka bezi na pozadi celu hraciu seansu a prekreslovat pritom
    nieco, na co sa nikto nepozera, by bolo plytvanie.
    """

    HEIGHT = 92
    TICK_MS = 90
    # Spinac vlavo v pase. Do verzie 2.1 bola na tomto mieste len farebna
    # bodka a prepinal KLIK KAMKOLVEK do pasu - o com sa hrac dozvedel len
    # zo sprievodcu. Teraz je to ovladac, ktory vyzera ako ovladac, a
    # prepina UZ LEN on: jeden zamer, jedno miesto.
    BTN_X = 18
    BTN_SIZE = 34
    HALF_CYCLE_MS = 5000.0      # rovnaka faza ako _SlotOverlay.HALF_CYCLE_S

    def __init__(self, master, pal, on_toggle, label="", sub=""):
        super().__init__(master, fg_color="transparent", height=self.HEIGHT)
        self.pack_propagate(False)
        self.pal = pal
        self.on_toggle = on_toggle
        self.live = False
        self._phase = 0.0
        self._job = None
        self._label = label
        self._sub = sub
        # Znovupouzitie prvkov platna namiesto delete("all")+znovu-vytvorenie
        # kazdy tik (90 ms). `_it` su id-cka poloziek, `_it_sig` je (sirka, vyska,
        # mierka), pre ktore su postavene - pri zmene sa postavia nanovo, inak
        # sa len upravia (coords/itemconfigure). Rovnaky vzor ako Dnes stred.
        self._it = None
        self._it_sig = None       # (w, h, mierka), pre ktore su polozky postavene
        self._last_mierka = 1.0

        self.canvas = tk.Canvas(self, height=self.HEIGHT, bg=pal["bg"],
                                highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Button-1>", self._clicked)
        self.canvas.bind("<Motion>", self._hover)
        self.canvas.bind("<Configure>", lambda _e: self._redraw())

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

    def set_texts(self, label, sub):
        self._label, self._sub = label, sub
        if self._it is not None:
            try:
                self.canvas.itemconfigure(self._it["title"], text=label)
                self.canvas.itemconfigure(self._it["sub"], text=sub)
            except Exception:
                pass
        self._redraw()

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
        """Je klik v spinaci? Suradnice udalosti su FYZICKE px, takze spinac
        skalujeme mierkou (rovnako ako sa kresli) a beriem realnu vysku platna -
        inak by klik na 150 % netrafil tam, kde je spinac nakresleny."""
        m = self._last_mierka or 1.0
        bs = self.BTN_SIZE * m
        bx = self.BTN_X * m
        try:
            h = int(self.canvas.winfo_height())
        except Exception:
            h = int(self.HEIGHT * m)
        by = (h - bs) / 2.0
        return (bx <= event.x <= bx + bs and by <= event.y <= by + bs)

    def _clicked(self, event):
        if self._v_spinaci(event) and callable(self.on_toggle):
            self.on_toggle()

    def _hover(self, event):
        """Ruka len nad spinacom. Kurzor je jediny nahlad, ktory hrac dostane
        pred klikom - keby bola ruka nad celym pasom, slubovala by akciu,
        ktora sa uz nikde inde nestane."""
        try:
            self.canvas.configure(
                cursor="hand2" if self._v_spinaci(event) else "")
        except Exception:
            pass

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
        bufferu. `w`/`h` su FYZICKE px platna; logicke konstanty (spinac, medzery)
        skalujeme mierkou `m`, aby na 150 % pas vyplnili proporcne."""
        c = self.canvas
        c.delete("all")
        it = {"glow": [], "pause": []}
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
        # SPINAC - kruh + tvar znaku (pauza = pocuvam / play = zastavene)
        bx = self.BTN_X * m
        bs = self.BTN_SIZE * m
        scx, scy = bx + bs / 2.0, h / 2.0
        rr = bs / 2.0 - 3 * m
        it["oval"] = c.create_oval(scx - rr, scy - rr, scx + rr, scy + rr,
                                   width=max(1, int(round(2 * m))))
        for smer in (-1, 1):
            x0 = scx + smer * 3.8 * m - 1.3 * m
            it["pause"].append(c.create_rectangle(x0, scy - 5.5 * m, x0 + 2.6 * m,
                                                  scy + 5.5 * m, outline="", state="hidden"))
        it["play"] = c.create_polygon(scx - 4.5 * m, scy - 6.5 * m, scx - 4.5 * m,
                                      scy + 6.5 * m, scx + 6.5 * m, scy,
                                      outline="", state="hidden")
        # TEXT - medzera -18/+16 (skalovana) aby zostup 'ý' z nadpisu nenarazal
        # na 'ľ'/'ď' z podtitulku; `width` = zalomenie na sirku pasu.
        tx = bx + bs + 14 * m
        sirka = max(1, int(w - tx - 16 * m))
        it["title"] = c.create_text(tx, h / 2 - 18 * m, text=self._label, anchor="w",
                                    font=self._cvfont(17, "bold"), width=sirka)
        it["sub"] = c.create_text(tx, h / 2 + 16 * m, text=self._sub, anchor="w",
                                  font=self._cvfont(11), width=sirka)
        self._it = it

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
        glyf = pal["accent_hover"] if live else pal["accent"]
        c.itemconfigure(it["oval"], outline=pal["accent"])
        for rid in it["pause"]:
            c.itemconfigure(rid, fill=glyf, state="normal" if live else "hidden")
        c.itemconfigure(it["play"], fill=glyf, state="hidden" if live else "normal")
        c.itemconfigure(it["title"], fill=pal["text"])
        c.itemconfigure(it["sub"], fill=pal["text_dim"] if live else pal["text_faint"])


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

    def __init__(self, master, pal, height=150):
        super().__init__(master, pal, height)
        self._values, self._labels = [], []
        self._color, self._band, self._band_label = None, None, ""
        self._bars = False
        self._decimals = 0

    def set_series(self, values, labels=None, color=None, band=None,
                   band_label="", bars=False, decimals=0):
        self._values = list(values or [])
        self._labels = list(labels or [])
        self._color = color
        self._band = band
        self._band_label = band_label or ""
        self._bars = bool(bars)
        self._decimals = int(decimals)
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
                          anchor="s", fill=pal["text_faint"], font=mono(9))

    def _redraw(self):
        pal, c = self.pal, self.canvas
        w, h, s = self._canvas_size(120)
        if not w:
            return
        c.delete("all")
        x0, x1 = self.PAD_L * s, w - self.PAD_R * s
        y0, y1 = self.PAD_T * s, h - self.PAD_B * s
        if not [v for v in self._values if v is not None]:
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
                          fill=pal["text_faint"], font=mono(9))

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

        def y_of(value):
            return spodok - (value - lo) / span * (spodok - vrch)

        def popisok(y, hodnota, farba):
            """Cislo k ciare. Ked ciara lezi pri hornom okraji, popisok ide
            POD nu - nad nou by ho orezal okraj platna (a prave hranica
            konci hore vzdy, ked ju relacia neprekrocila)."""
            nad = y >= 14 * s
            c.create_text(w - 4 * s, y - 2 * s if nad else y + 2 * s,
                          text=str(int(round(hodnota))), anchor="se" if nad else "ne",
                          fill=farba, font=mono(9))

        if self._baseline and lo <= self._baseline <= hi:
            y = y_of(self._baseline)
            c.create_line(0, y, w, y, fill=pal["text_faint"], width=1)
            popisok(y, self._baseline, pal["text_faint"])
        if self._threshold and lo <= self._threshold <= hi:
            y = y_of(self._threshold)
            c.create_line(0, y, w, y, fill=pal["danger"], width=1, dash=(4, 4))
            popisok(y, self._threshold, pal["danger"])

        krok = w / float(len(values) - 1)
        body = []
        for i, value in enumerate(values):
            body.extend((i * krok, y_of(value)))
        c.create_line(*body, fill=pal["accent_hover"], width=max(1, round(2 * s)),
                      smooth=True, capstyle="round", joinstyle="round")

        self._draw_triggers(w, strip_top - 2 * s, s)
        self._draw_activity(w, strip_top - self.ACT_H - 2, self.ACT_H)
        self._draw_strip(w, strip_top, strip_h)
        if self._duration > 0:
            c.create_text(0, h - 2 * s, text="0:00", anchor="sw",
                          fill=pal["text_faint"], font=mono(9))
            c.create_text(w, h - 2 * s, text=self._mmss(self._duration), anchor="se",
                          fill=pal["text_faint"], font=mono(9))


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
            c.create_text(pravo, y, text="%+.1f  (n=%d)" % (delta, n), anchor="e",
                          fill=pal["text_faint"], font=mono(10))
            y += self.RIADOK * s


class DayGrid(PalCanvas):
    """Mriezka dni - stlpec je tyzden, riadok den v tyzdni (pondelok hore),
    sytost stvorceka kolko si v ten den odohral.

    Cita sa z nej to, co zo ziadneho ineho grafu v appke nevidno: vzor.
    Vikendy, serie vecerov, tyzden, ked appka lezala vypnuta. Prazdne dni
    su preto rovnako dolezite ako plne a kreslia sa tiez.
    """

    CELL = 12
    GAP = 3
    LEGEND_H = 18
    STEPS = 4       # kolko odtienov nad "prazdny den"

    def __init__(self, master, pal):
        super().__init__(master, pal, 7 * (self.CELL + self.GAP) - self.GAP
                         + self.LEGEND_H)
        self._days = []
        self._legend = ("", "")

    def set_days(self, days, legend=("", "")):
        """`days` je vystup `hr_stats.day_activity` (od najstarsieho)."""
        self._days = list(days or [])
        self._legend = legend
        self._redraw()

    def _odtiene(self):
        # odtiene smerom k farbe POKOJA danej temy, nie k univerzalnej
        # zelenej - v indigovej teme bola mriezka jediny zeleny ostrovcek
        return [theme_mod.mix(self.pal["surface_alt"],
                              theme_mod.zone_color(self.pal, "calm"),
                              (i + 1) / float(self.STEPS))
                for i in range(self.STEPS)]

    def _redraw(self):
        pal, c = self.pal, self.canvas
        w, _h, s = self._canvas_size(60)
        if not w or not self._days:
            return
        c.delete("all")
        cell, gap = self.CELL * s, self.GAP * s
        krok = cell + gap
        odtiene = self._odtiene()
        # Prah kazdeho odtiena je percentil TVOJICH dni, nie pevna minutaz -
        # hodinu denne ma niekto ako maximum a niekto ako rozcvicku.
        aktivne = sorted(d["seconds"] for d in self._days if d["seconds"] > 0)
        prahy = [aktivne[min(len(aktivne) - 1, int(len(aktivne) * (i + 1) / float(self.STEPS)))]
                 for i in range(self.STEPS)] if aktivne else []
        # Kolko tyzdnov sa zmesti - a orezava sa ZACIATOK, nie koniec:
        # dnesok musi byt v mriezke vzdy, aj keby sa historia nezmestila
        # cela. Volajuci preto moze pokojne poslat cely rok.
        stlpcov = max(1, int((w + gap) // krok))
        dni = self._days
        for _ in range(3):
            prebytok = len(dni) + dni[0]["date"].weekday() - stlpcov * 7
            if prebytok <= 0:
                break
            dni = dni[prebytok:]
        prvy_den = dni[0]["date"].weekday()
        for i, den in enumerate(dni):
            poradie = i + prvy_den
            x = (poradie // 7) * krok
            y = (poradie % 7) * krok
            if x + cell > w:
                break
            if den["seconds"] <= 0:
                farba = pal["line_soft"]
            else:
                stupen = sum(1 for p in prahy if den["seconds"] > p)
                farba = odtiene[min(stupen, self.STEPS - 1)]
            round_rect(c, x, y, x + cell, y + cell, 3 * s, fill=farba, outline="")
        legenda_y = 7 * krok - gap + (self.LEGEND_H - 6) * s
        menej, viac = self._legend
        c.create_text(0, legenda_y, text=menej, anchor="sw",
                      fill=pal["text_faint"], font=ui(10))
        x = 46 * s
        for farba in [pal["line_soft"]] + odtiene:
            round_rect(c, x, legenda_y - 10 * s, x + 10 * s, legenda_y, 2 * s,
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
        ctk.CTkFrame(self, fg_color=pal["line_soft"], height=1,
                     corner_radius=0).pack(fill="x")
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
        self.tag_label = ctk.CTkLabel(head, text=tag.upper(), font=ui(9, "bold"),
                                      text_color=pal["text_faint"], anchor="w")
        self.tag_label.pack(side="left")
        self._info_btn = ctk.CTkButton(
            head, text="ⓘ", width=16, height=16, corner_radius=8,
            fg_color="transparent", hover_color=pal["surface_alt"],
            text_color=pal["text_faint"], font=ui(9), command=self._toggle_info)
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
    """Rad kariet (chipov) nad obsahom - Spustace | Zvuk | V hre | ...

    Bocne menu ma po feedbacku len 3 hlavne polozky; vsetko ostatne su
    karty tu. Kazda karta ma kluc, ktory je zaroven kluc stranky, takze
    `app.navigate(key)` funguje pre karty rovnako ako pre hlavne polozky.
    Odznak (pocet spustacov, bodka senzora) sa pripaja k textu karty."""

    def __init__(self, master, pal, items, on_select):
        """items: [(key, label)]"""
        super().__init__(master, fg_color="transparent")
        self.pal = pal
        self.on_select = on_select
        self.buttons = {}
        self._labels = {}
        self._badges = {}
        self.active = None
        for key, label in items:
            btn = ctk.CTkButton(
                self, text=label, height=30, corner_radius=8, border_width=1,
                border_color=pal["border"], fg_color="transparent",
                hover_color=pal["surface_alt"], text_color=pal["text_dim"],
                font=ui(12), command=lambda k=key: self.select(k))
            btn.pack(side="left", padx=(0, 6))
            self.buttons[key] = btn
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
                btn.configure(fg_color=pal["accent2"] if active else "transparent",
                              border_color=pal["accent"] if active else pal["border"],
                              text_color=pal["text"] if active else pal["text_dim"])
            except Exception:
                pass

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

    def __init__(self, master, pal, short, more, more_label, less_label, wrap=420):
        super().__init__(master, fg_color="transparent")
        self.pal = pal
        self._more_label, self._less_label = more_label, less_label
        self._open = False
        ctk.CTkLabel(self, text=short, font=ui(11), text_color=pal["text_faint"],
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

        rule = ctk.CTkFrame(top, fg_color=pal["line_soft"], height=1, corner_radius=0)
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
