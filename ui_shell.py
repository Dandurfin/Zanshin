"""
ui_shell.py — stavebné prvky okna Zanshin: vlastná titulková
lišta bez OS rámu, sidebar navigácia, kontajner stránok, paleta príkazov
(Ctrl+K). Zámerne oddelené od app.py, ktoré ich skladá
dokopy v `DandurfApp._build_ui`.

Čo je tu:
  TitleBar       vlastná lišta (ťahanie, minimalizovať, zavrieť). Farby
                 berie z témy appky (`pal`), nie z modulového PAL, aby
                 ladila so zvyškom okna pri prepnutí Aizome/Sumi.
                 Maximalizáciu NEMÁ - appka je fixný dashboard.
  Sidebar        úzky ľavý pruh: kontrolka stavu, navigácia, lupa,
                 Nastavenia úplne dole.
  PageContainer  stránky naukladané na sebe, prepínané cez `show()`.
  CommandPalette Ctrl+K popup s fuzzy filtrom.
  _StateDot      bodka stavu v rade: počúva / nepočúva / odložená.

TENTO SÚBOR SA NESPÚŠŤA SÁM. Appka štartuje vždy cez `main.py` ->
`app.DandurfApp`. `python ui_shell.py` neurobí nič - kedysi tu bola
testovacia `main()` s placeholder UI, ktorá mýlila (viď POZN na konci).

Vyžaduje: customtkinter (už je v requirements.txt).
"""

import sys
import time
import tkinter as tk
import tkinter.font as tkfont

import customtkinter as ctk

import hud_paint
import ui_kit

IS_WINDOWS = sys.platform == "win32"

# ---------------------------------------------------------------------------
# farebné tokeny - "calm" paleta z mockupu v4 (jeden akcent, takmer neviditeľné
# hranice, sage len pre stav "zapnuté", terakotová len pre nebezpečné akcie)
# ---------------------------------------------------------------------------
PAL = {
    "bg": "#0b0f0d",
    "bg_elevated": "#121714",
    "bg_hover": "#171d19",
    "border": "#1c2521",
    "border_strong": "#2a3630",
    "text": "#ece7da",
    "text_2": "#9aa39b",
    "text_3": "#5c645d",
    "accent": "#c9a24d",
    "accent_hover": "#d9b25f",
    "ok": "#8fbf9f",
    "danger": "#c1553d",
}

ctk.set_appearance_mode("dark")


# ---------------------------------------------------------------------------
# Aktuálna paleta témy pre prvky BEZ vlastnej kópie
# ---------------------------------------------------------------------------
#
# `PAL` vyššie je pôvodná paleta z maketu v4 - zelenkavý atrament, ktorý
# redizajn (Aizome / Sumi) nahradil. Väčšina prvkov dostáva paletu zvonku,
# ale bubliny s popiskami si ju brali práve z tohto modulového `PAL` - a tak
# ostali jediné miesto v appke, kde svietila stará zelená. Nahlásené ako
# "popisy majú starý design".
#
# Odstrániť `PAL` sa nedá (drží predvolené hodnoty pre prvky stavané ešte
# pred prvým prepnutím témy), tak je tu jedna premenná s AKTUÁLNOU témou,
# ktorú appka nastaví pri štarte aj pri každom prepnutí.
_THEME_PAL = {}


def set_theme_pal(pal):
    """Zapamätá si aktuálnu paletu témy pre prvky, ktoré si ju nedržia."""
    _THEME_PAL.clear()
    _THEME_PAL.update(pal or {})


def theme_pal():
    """Aktuálna paleta témy; `PAL` len kým appka žiadnu nenastavila."""
    return _THEME_PAL or PAL


# ---------------------------------------------------------------------------
# Vlastná titulková lišta - nahrádza OS rám
# ---------------------------------------------------------------------------
# Piktogram tlacidla "O appke" v titulkovej liste. Kolecko s "i" je
# zauzivany symbol pre "o programe"; ako jeden znak sa kresli rovnakym
# `_make_btn` ako "–" a "×", takze sedi s nimi na pixel.
ABOUT_GLYPH = "ⓘ"        # ⓘ


class TitleBar(ctk.CTkFrame):
    """Ťahaním za lištu sa okno presúva; tlačidlá vpravo replikujú
    minimalizovať / zavrieť bez natívneho OS vzhľadu.

    Maximalizácia tu zámerne NIE JE - viď POZN nižšie pri `close()`."""

    def __init__(self, master, root_window=None, app_name="Zanshin", on_close=None,
                 version="", pal=None, on_about=None, about_tip="",
                 licence="", world_values=None, world_value=None, on_world=None,
                 world_tip=""):
        # POZN: lista brala farby z moduloveho PAL a jedine znak 残 z temy.
        # Vysledok bol pruh, ktory pri teme Sumi/Aizome nesedel so zvyskom
        # okna (ina cierna, iny odtien textu) a po odstraneni fotopasu nad
        # nou to bilo do oci este viac. Teraz ide vsetko cez `pal` s
        # modulovym PAL len ako zaloha, ked ju niekto postavi bez temy.
        self.pal = pal or {}

        # POZOR: cita `self.pal`, NIE lokalnu `pal`. Povodne to bola
        # closure nad lokalnou premennou, takze po `set_pal()` vracala
        # stare farby a lista sa pri zmene temy prefarbila spat na predoslu
        # temu (chytil to test "prefarbenie == prestavba" - 20 rozdielov).
        def c(key, fallback):
            return self.pal.get(key, PAL[fallback])

        self._c = c
        super().__init__(master, fg_color=c("surface", "bg"), height=32, corner_radius=0)
        # DÔLEŽITÉ: `master` je rodičovský widget na zabalenie (pack/grid) -
        # NEMUSÍ to byť skutočné top-level okno (napr. keď je titlebar
        # zabalený vo vnútornom CTkFrame). Na .geometry()/.iconify()/
        # .overrideredirect() potrebujeme referenciu na ozajstné okno, preto
        # je `root_window` samostatný, povinne odovzdaný parameter.
        self.master_root = root_window if root_window is not None else master
        self.on_close_cb = on_close
        self._drag_start = None
        self.pack_propagate(False)

        # Tenka linka dole oddeli listu od obsahu rovnako, ako su od seba
        # oddelene karty na strankach - bez nej sa lista po odstraneni
        # fotopasu zlievala s telom okna do jednej plochy.
        #
        # MUSI sa pakovat PRVA, este pred `left` a `controls`. Tk prideluje
        # parcely v poradi pack() volani: `left` so side="left" si vezme pas
        # cez CELU vysku dutiny, takze linka packnuta az po nom by dostala
        # fill="x" len cez ZVYSOK dutiny - zacala by az za nazvom appky
        # (odmerane: x=235 namiesto 0 pri sirke listy 1770 px) a pod znakom
        # 残 by chybala. Ako prva dostane celu sirku a zvysok sa deli az pod
        # nou.
        self.divider = ctk.CTkFrame(self, fg_color=c("line_soft", "border"), height=1,
                                    corner_radius=0)
        self.divider.pack(side="bottom", fill="x")

        # Logo/znacka (残 + nazov + verzia) sedi v liste ako v NVIDIA App,
        # nie v tele bocneho menu - to je po feedbacku uzke a len s ikonami.
        left = ctk.CTkFrame(self, fg_color="transparent")
        left.pack(side="left", padx=(14, 0))
        ctk.CTkLabel(left, text="残", text_color=c("washi", "accent"),
                     font=("Yu Mincho", 15)).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(left, text=app_name, text_color=c("text", "text"),
                     font=("Segoe UI", 10, "bold")).pack(side="left")
        if version:
            # Patnast klikov na cislo verzie otvori vyvojarsku vrstvu.
            # Je to LOKALNA Tk vazba na jeden widget, nie globalny hook -
            # funguje len ked ma okno appky fokus a mimo neho o klikoch nevie.
            self.version_label = ctk.CTkLabel(
                left, text=f"   {version}", text_color=c("text_faint", "text_3"),
                font=("Consolas", 9))
            self.version_label.pack(side="left")
            self._secret_clicks = 0
            self.version_label.bind("<Button-1>", self._on_version_click)

        if licence:
            # LICENCIA HNED VEDLA VERZIE a v tom istom fonte.
            #
            # Appka tvrdi, ze je slobodna - tak nech to stoji tam, kde to
            # vidno vzdy, nie az v Nastaveniach pod Datami. Je to to iste
            # tvrdenie ako "vsetko ostava u teba": bud je vidiet stale,
            # alebo mu netreba verit.
            #
            # VLASTNY LABEL, nie pripojenie k verzii: na cisle verzie visi
            # patnastklikova vazba na vyvojarsku vrstvu a tu by inak
            # spustalo aj klikanie na licenciu.
            self.licence_label = ctk.CTkLabel(
                left, text=f"  ·  {licence}",
                text_color=c("text_faint", "text_3"), font=("Consolas", 9))
            self.licence_label.pack(side="left")

        controls = ctk.CTkFrame(self, fg_color="transparent")
        controls.pack(side="right")
        # SVET (0.2, B3-worlds): male "Hra | Praca" vlavo od ⓘ.
        #
        # V liste, nie na stranke: je to jedina vec, ktora meni CELU appku
        # naraz (vzhlad, historiu, postrehy), takze patri tam, kde je vidno
        # na kazdej stranke - a s prepinacom HUD-u ani ⚙ na Dnes sa tu
        # nezrazi. Maly a tlmeny: znamenie v rohu oka, nie vykricnik.
        #
        # Bublina ide na KAZDY segment zvlast - CTkSegmentedButton.bind()
        # vyhodi NotImplementedError, a segmenty su jeho deti.
        self.world_switch = None
        if on_world is not None and world_values:
            self.world_switch = ctk.CTkSegmentedButton(
                controls, values=list(world_values), height=22,
                font=("Segoe UI", 10), fg_color=c("surface", "bg"),
                selected_color=c("accent2", "bg_hover"),
                selected_hover_color=c("accent2_hover", "bg_hover"),
                unselected_color=c("surface", "bg"),
                unselected_hover_color=c("surface_alt", "bg_hover"),
                text_color=c("text", "text"), command=on_world)
            if world_value:
                self.world_switch.set(world_value)
            self.world_switch.pack(side="left", padx=(0, 8), pady=5)
            for segment in getattr(self.world_switch, "_buttons_dict", {}).values():
                _HoverTip(segment, lambda: world_tip, below=True)
        # About VLAVO od minimalizacie a zatvorenia.
        #
        # Kto appku prvykrat otvori, hlada "kto to spravil" v titulkovej
        # liste - nie v Nastaveniach pod Datami, kde ta sekcia zije. Tlacidlo
        # ho tam odvedie, takze sekcia moze zostat tam, kam patri obsahom.
        #
        # PIKTOGRAM, nie pismeno "A": kolecko s "i" je to, co ludia v liste
        # poznaju. Samotne "A" medzi "–" a "×" vyzera skor ako ovladac
        # velkosti pisma - symbol ma byt cim, za co sa vydava.
        if on_about is not None:
            self.about_btn = self._make_btn(controls, ABOUT_GLYPH, on_about)
            _HoverTip(self.about_btn, lambda: about_tip)
        self._make_btn(controls, "–", self.minimize)
        self._make_btn(controls, "×", self.close, danger=True)

        # ťahanie za lištu (nie za tlačidlá) - ZIADNE dvojklik-maximalizuj:
        # appka je pevny dashboard s fixnym rozmerom (WINDOW_W/H v app.py),
        # maximalizacia by ho roztiahla na cely monitor a rozbila layouty
        # (HUD, paleta prikazov - viz komentar pri DandurfApp.WINDOW_W).
        # Tlacidlo maximalizacie preto uz nie je v ovladacoch vyssie a
        # dvojklik nic nerobi.
        for widget in (self, left):
            widget.bind("<ButtonPress-1>", self._drag_begin)
            widget.bind("<B1-Motion>", self._drag_move)

    def _on_version_click(self, _event=None):
        """Patnast klikov na verziu -> vyvojarska vrstva.

        Patnast a nie tri: na cislo verzie sa omylom klikne lahko, ale
        patnastkrat po sebe uz nie. Skryta ma byt preto, aby ju hrac
        nenasiel nahodou a nezacal si prestavovat prahy, ktorym nerozumie -
        nie preto, ze by bola tajna.
        """
        self._secret_clicks += 1
        if self._secret_clicks < 15:
            return
        self._secret_clicks = 0
        otvor = getattr(self, "on_dev_layer", None)
        if callable(otvor):
            otvor()

    def set_pal(self, pal):
        """Prepise vlastnu kopiu palety pri zmene temy.

        Samotne farby widgetov uz prefarbil `theme_recolor`, ale `self.pal`
        a pomocna `self._c` sa pouzivaju pri kazdom `_make_btn()` - keby tu
        ostala stara paleta, kazde neskor pridane tlacidlo listy by sa
        nakreslilo v predoslej teme."""
        self.pal = pal or {}
        try:
            self.configure(fg_color=self._c("surface", "bg"))
            self.divider.configure(fg_color=self._c("line_soft", "border"))
        except Exception:
            pass

    def set_world(self, label):
        """Oznaci segment sveta bez toho, aby sa zavolal `on_world` - svet
        mohlo prepnut aj nieco ine (Nastavenia, sprievodca)."""
        if self.world_switch is None:
            return
        try:
            self.world_switch.set(label)
        except Exception:
            pass

    def _make_btn(self, parent, symbol, cmd, danger=False):
        c = self._c
        btn = ctk.CTkButton(
            parent, text=symbol, width=38, height=32, corner_radius=0,
            fg_color="transparent",
            hover_color=(c("danger", "danger") if danger else c("surface_alt", "bg_hover")),
            text_color=c("text_dim", "text_3"), font=("Segoe UI", 11), command=cmd,
        )
        btn.pack(side="left")
        return btn

    def _drag_begin(self, event):
        self._drag_start = (event.x_root, event.y_root,
                            self.master_root.winfo_x(), self.master_root.winfo_y())

    def _drag_move(self, event):
        # POZN: bola tu aj podmienka `or self._maximized` - zostala po
        # odstraneni maximalizacie, ale atribut sa uz nikde nenastavoval,
        # takze KAZDE tahanie za listu hodilo AttributeError a okno sa
        # nedalo posunut vobec. Appka ma fixny rozmer, maximalizovana byt
        # nemoze - podmienka je tym padom zbytocna, nie len rozbita.
        if not self._drag_start:
            return
        sx, sy, wx, wy = self._drag_start
        dx, dy = event.x_root - sx, event.y_root - sy
        self.master_root.geometry(f"+{wx + dx}+{wy + dy}")

    def minimize(self):
        # overrideredirect okná nemajú natívny taskbar handshake - dočasne ho
        # vypneme, aby iconify/obnovenie fungovalo spoľahlivo (bežný Tk trik).
        self.master_root.overrideredirect(False)
        self.master_root.iconify()

    # POZN: `toggle_maximize`/`_maximized_geometry` tu boli - obchadzali
    # pevny rozmer okna (WINDOW_W/H v app.py, minsize==maxsize) priamym
    # volanim geometry(). Appka je fixny dashboard, nie okno na roztiahnutie
    # cez cely monitor - tlacidlo maximalizacie preto bolo odstranene
    # celkom (nie len skryte/zablokovane), namiesto opravovania spravania,
    # ktore appka ani nema mat.

    def close(self):
        if self.on_close_cb:
            self.on_close_cb()
        else:
            self.master_root.destroy()


def enable_frameless(root):
    """Zapne bezrámové okno a zaregistruje obnovenie overrideredirect po
    návrate z minimalizovanej lišty (viď TitleBar.minimize)."""
    root.overrideredirect(True)

    def _on_map(event):
        if root.state() == "normal":
            root.overrideredirect(True)
    root.bind("<Map>", _on_map)


# POZN: tu bol blok "Rucny resize bezramoveho okna" - `RESIZE_GRIP_PX`,
# `enable_resize_grips()` a `lift_resize_grips()`. Kreslili 4 hrany + 4 rohy
# ako tenke ramy nad obsahom (place), ktorymi sa dalo bezramove okno tahat
# za okraje.
#
# Odstranene: appka je FIXNY dashboard (DandurfApp.WINDOW_W/H, minsize ==
# maxsize, ziadna maximalizacia), takze rucny resize nema co robit -
# `enable_resize_grips()` uz nikto nevolal a `gui_harness_auto.py` dokonca
# kontroluje OPAK ("no manual resize grips (fixed window by design)").
# Zostaval tu ako ~80 riadkov mrtveho kodu s komentarom, ktory rucny resize
# popisoval ako zivu funkciu - presne to, co matie pri citani.


# ---------------------------------------------------------------------------
# Sidebar navigácia
# ---------------------------------------------------------------------------
class Sidebar(ctk.CTkFrame):
    """Bocna navigacia.

    Poradie zhora nadol kopiruje to, ako sa appka naozaj pouziva:
      1. KONTROLKA STAVU - svieti, ked appka pocuva (`_StateDot`)
      2. navigacia - Dnes (co sa prave deje), Historia, V hre
      3. KONTROLKA TEPU - zivy stav senzora + skratka na parovanie
      4. pruzna medzera
      5. UPLNE DOLE, v tomto poradi zhora nadol: rychly dok
         (stisit/snooze/profil), lupa (Ctrl+K), Nastavenia
    Hore su STRANKY, dole je OBSLUHA appky. Ozubene koliesko je zamerne
    poslednym prvkom - je to najzriedkavejsia vec a v lavom dolnom rohu
    sa hlada najlahsie.

    POZN: bod 1 tu do 2.1 bolo ENSO (znacka a zaroven spinac pocuvania).
    Znacka sa presunula do stredu stranky Dnes (`app.py`, `_build_dnes_page`)
    a spinac do dychajuceho pasu (`ui_kit.KamaeBar`); v rade po nej ostala
    len mala farebna bodka, aby bolo aj na ostatnych strankach vidno, ci
    appka pocuva.
    """

    # Po feedbacku z testu ("preplnene") len 4 hlavne polozky.
    # Spustace, Zvuk a Sprievodca su KARTY v Nastaveniach (ui_kit.SubNav);
    # `_select(kluc_karty)` funguje dalej - zvyrazni sa skupina a app
    # prepne kartu (GROUPS), takze paleta, onboarding a tour sa nerozbili.
    #
    # "nastavenia" MUSI ZOSTAT POSLEDNA POLOZKA a zaroven musi zostat v
    # `self.rows`. Dva rozne dovody, oba tiche:
    #   - `__init__` stavia horny blok ako PAGES[:-1] a poslednu polozku
    #     zvlast, uplne dole. Split je POZICNY, nie podla kluca: keby sa
    #     "nastavenia" zo zoznamu vyhodilo, spodnym prvkom by sa ticho
    #     stalo "V hre" - bez vynimky, len by odrazu sedelo dole.
    #   - `gui_harness_auto.py` indexuje rows["nastavenia"] natvrdo na
    #     siestich miestach a `_select` cezen zvyraznuje karty Nastaveni
    #     (GROUPS). Chybajuci kluc = KeyError uprostred kroku harnessu.
    PAGES = [
        ("dnes", "◗", "Dnes"),
        ("historia", "◷", "História"),
        ("vhre", "◳", "V hre"),
        # `︎` = textova (monochromaticka) prezentacia. Bez neho Windows
        # kresli ⚙ ako emoji - vacsie a tucnejsie nez tenke geometricke ikony
        # ◗ ◷ ◳ vedla, takze Nastavenia "trcali". Textovy variant ho zjednoti.
        ("nastavenia", "⚙︎", "Nastavenia"),
    ]
    GROUPS = {"spustace": "nastavenia", "zvuk": "nastavenia",
              "guide": "nastavenia", "vseobecne": "nastavenia"}
    # 76 -> 64: rad nesie uz len navigaciu a obsluhu, nie znacku. Zuzenie
    # blokoval rychly dok - mal dve ikony VEDLA SEBA a taky riadok si pyta
    # 70.7 px (CTkButton s corner_radius=8 si pyta 16 px "skrupiny" + sirku
    # glyfu, nie zadanych `width=24`). Dok je teraz na vysku, takze najsirsi
    # prvok dole je jedno tlacidlo ~34 px a 64 px ma rezervu.
    WIDTH = 78

    @staticmethod
    def _mapuj_paletu(pal):
        """Sidebar pouziva vlastne mena farieb (hover/active/text_2...) -
        tu sa temova paleta prelozi na ne. Vytiahnute zo `__init__`, aby
        sa to iste dalo spravit aj pri zmene temy (`set_pal`)."""
        return {
            "bg": pal.get("bg", PAL["bg"]),
            "hover": pal.get("surface", PAL["bg_hover"]),
            "active": pal.get("surface_alt", PAL["bg_hover"]),
            "text": pal.get("text", PAL["text"]),
            "text_2": pal.get("text_dim", PAL["text_2"]),
            "text_3": pal.get("text_faint", PAL["text_3"]),
            "border": pal.get("border", PAL["border"]),
            "accent": pal.get("accent_hover", PAL["accent"]),
            "washi": pal.get("washi", PAL["accent"]),
            "ok": pal.get("success", PAL["ok"]),
        }

    def set_pal(self, pal):
        """Prefarbi bocny panel pri zmene temy.

        Robi to, co mechanicke prefarbenie stromu spravit nevie: prepise
        vlastne kopie paliet (Sidebar, kazdy _NavRow, dok) a prekresli
        enso, ktore je OBRAZOK. Bez toho by sa stare farby vratili pri
        prvom hover/kliku."""
        self._theme_pal = pal
        self.pal = self._mapuj_paletu(pal)
        try:
            self.configure(fg_color=self.pal["bg"])
        except Exception:
            pass
        for row in self.rows.values():
            try:
                row.set_pal(self.pal)
            except Exception:
                pass
        cmdk = getattr(self, "cmdk_btn", None)
        if cmdk is not None:
            try:
                cmdk.configure(hover_color=self.pal["hover"],
                               text_color=self.pal["text_2"])
            except Exception:
                pass
        # kontrolka tepu je OBRAZOK - farby su do nej zapecene, musi sa
        # cela sada snimkov nakreslit znova
        pair = getattr(self, "pair_btn", None)
        if pair is not None:
            try:
                pair.set_pal(pal)
            except Exception:
                pass
        enso = getattr(self, "enso", None)
        if enso is not None:
            try:
                enso.set_pal(pal)
            except Exception:
                pass
        bodka = getattr(self, "state_dot", None)
        if bodka is not None:
            try:
                bodka.set_pal(pal)
            except Exception:
                pass

    def __init__(self, master, on_navigate, labels=None, pal=None, version="",
                 on_palette=None, on_enso_toggle=None, on_pair_watch=None):
        pal = pal or PAL
        self._theme_pal = pal
        self.pal = {
            "bg": pal.get("bg", PAL["bg"]),
            "hover": pal.get("surface", PAL["bg_hover"]),
            "active": pal.get("surface_alt", PAL["bg_hover"]),
            "text": pal.get("text", PAL["text"]),
            "text_2": pal.get("text_dim", PAL["text_2"]),
            "text_3": pal.get("text_faint", PAL["text_3"]),
            "border": pal.get("border", PAL["border"]),
            "accent": pal.get("accent_hover", PAL["accent"]),
            "washi": pal.get("washi", PAL["accent"]),
            "ok": pal.get("success", PAL["ok"]),
        }
        super().__init__(master, fg_color=self.pal["bg"], width=self.WIDTH,
                         corner_radius=0, border_width=0)
        self.pack_propagate(False)
        self.on_navigate = on_navigate
        self.on_palette = on_palette
        # key -> _NavRow (len ikona, cely nazov v tooltipe). `buttons`
        # ostava ako alias pre stary kod, ktory cakal tlacidla.
        self.rows = {}
        self.buttons = self.rows
        labels = labels or {}
        # logo (残 DojoSync / verzia) sa presunulo do TitleBar - tu je len
        # mala medzera hore
        ctk.CTkFrame(self, fg_color="transparent", height=10).pack(fill="x")

        # ZNACKA SA PRESUNULA DO STREDU STRANKY (2.1). V paneli mala 68 px a
        # prstenec "natiahnute" pri tej velkosti 1,4 px - v statickom obrazku
        # sa strácal. Stavia ju `DandurfApp._build_dnes_page` a priradi sem
        # `sidebar.enso` ako alias, aby sprievodca aj harnessy nasli to iste
        # meno; `set_pal` nizsie ju preto stale prefarbuje.
        #
        # `on_enso_toggle` uz nema kto volat - spinac je teraz tlacidlo v
        # dychajucom pase (`ui_kit.KamaeBar`). Parameter ostava kvoli
        # volajucim, ktori ho posielaju.
        self.enso = None

        # Kontrolka stavu. Znacka odisla do stredu stranky Dnes a s nou aj
        # jedina informacia o tom, ci appka pocuva - na ostatnych piatich
        # strankach by v okne nezostalo nic. Viz `_StateDot`.
        dot_wrap = ctk.CTkFrame(self, fg_color="transparent")
        dot_wrap.pack(fill="x", pady=(8, 8))
        self.state_dot = _StateDot(
            dot_wrap, pal, tip=labels.get("state_tip", ""))
        self.state_dot.pack()

        # navigacia pod znackou; posledna polozka ("nastavenia") ide dolu
        for key, icon, default_label in self.PAGES[:-1]:
            row = _NavRow(self, self.pal, key, icon, labels.get(key, default_label),
                          on_click=self._select, compact=True)
            row.pack(fill="x", padx=8, pady=2)
            self.rows[key] = row

        # KONTROLKA SENZORA TEPU - hned pod navigaciou, oddelena medzerou.
        # Je to zaroven skratka na parovanie hodiniek (karta "Hodinky a
        # tep" sedi az dole na stranke V hre).
        #
        # POZOR NA PRUZNE MEDZERY: povodne tu boli DVE (nad aj pod
        # kontrolkou), aby ju drzali presne v strede. Lenze kazda si vzala
        # ~300 px a na spodne polozky uz neostalo nic - dok aj lupa boli
        # vysoke 1 px a Tk ich vobec nevykreslil. Medzera smie byt len
        # JEDNA, a az POD kontrolkou: tlaci nadol Nastavenia, dok a lupu,
        # a kontrolka tym sedi vyssie, pri navigacii, kam patri.
        self.pair_btn = None
        if on_pair_watch is not None:
            self.pair_btn = _WatchPulse(
                self, pal, on_click=on_pair_watch,
                tip_fn=lambda: labels.get("pair_tip", "Spárovať hodinky"),
                tip_live_fn=lambda: labels.get("pair_live_tip", "Tep z hodiniek"))
            self.pair_btn.pack(pady=(12, 0))
        ctk.CTkFrame(self, fg_color="transparent").pack(fill="both", expand=True)

        # Nastavenia su UPLNE DOLE - pod dokom aj lupou, v samom rohu okna.
        # `side="bottom"` a poradie packovania: pri Tk ide PRVY packnuty
        # spodny prvok najnizsie, takze tato trojica sa musi packnut v
        # poradi Nastavenia -> lupa -> dok, a na obrazovke potom zhora
        # nadol vyjde dok, lupa, Nastavenia.
        last_key, last_icon, last_default = self.PAGES[-1]
        last_row = _NavRow(self, self.pal, last_key, last_icon,
                           labels.get(last_key, last_default),
                           on_click=self._select, compact=True)
        last_row.pack(side="bottom", fill="x", padx=8, pady=(2, 10))
        self.rows[last_key] = last_row

        # Ctrl+K: v uzkom paneli len ikona s tooltipom; popisok berie
        # z `labels` (app.py ho preklada cez nav.cmdk_hint)
        # POZN: lupa mala `border_width=1` a sirku 44 px - bola tak jedinym
        # oramovanym prvkom v celom bocnom paneli (navigacia, enso aj dok su
        # ploche, bez ramceka) a posobila ako vlozene vyhladavacie policko,
        # nie ako ikona. Teraz ma rovnaky plochy vzhlad aj rozmery ako
        # tlacidla doku pod nou.
        cmdk_hint = ctk.CTkButton(
            self, text="⌕", width=24, height=28,
            corner_radius=8, fg_color="transparent", border_width=0,
            hover_color=self.pal["hover"],
            text_color=self.pal["text_2"], font=("Segoe UI", 13),
            # Obycajny callback, nie virtualna udalost (CTkFrame.bind() ide
            # na vnutorne platno, event_generate() na ramec - nedorazilo by).
            command=lambda: self.on_palette() if self.on_palette else None,
        )
        self.cmdk_btn = cmdk_hint
        cmdk_hint.pack(side="bottom", pady=(0, 6))
        _HoverTip(cmdk_hint, lambda: f"{labels.get('cmdk', 'Hľadať a prepínať')}   Ctrl K")

        # POZN: tu bol `dock_slot` - prazdny ramec, do ktoreho `app.py`
        # vkladal `QuickDock`. Dok odisiel (dovod je pri jeho triede nizsie),
        # takze slot uz nema co drzat. Rad tym dole konci lupou a
        # Nastaveniami.

        self._select("dnes")

    def set_badge(self, key, text=""):
        """Male cislo alebo bodka vpravo pri polozke (pocet spustacov,
        beziaci senzor). Odznak je samostatny label v pravom stlpci -
        meni sa len jeho text, popisok polozky sa nedotyka."""
        row = self.rows.get(key)
        if row is not None:
            row.set_badge(text)

    def _select(self, key):
        active = self.GROUPS.get(key, key)
        for k, row in self.rows.items():
            row.set_active(k == active)
        self.on_navigate(key)


class _NavRow(ctk.CTkFrame):
    """Jedna polozka bocneho menu: ikona | text | odznak v PEVNYCH stlpcoch.

    Preco nie jedno tlacidlo s textom f"{icon}    {label}": glyfy ◗ ⌸ ♪ ◳
    ◈ ⚙ maju kazdy inu sirku, takze text kazdej polozky zacinal na inej
    zvislici a odznak (pocet spustacov, bodka senzora) plaval niekde v
    strede riadku. Tu ma ikona stlpec pevnej sirky (ICON_W, centrovana),
    text zacina hned za nim vzdy na tej istej x-suradnici a odznak je
    zarovnany doprava - ked je prazdny, nezabera miesto.

    Cely riadok je klikatelny (ikona, text, odznak aj prazdna plocha) a
    ma hover + aktivny stav ako povodne CTkButton.
    """

    HEIGHT = 34
    HEIGHT_COMPACT = 48
    ICON_W = 24

    def __init__(self, master, pal, key, icon, label, on_click, compact=False):
        self.compact = bool(compact)
        height = self.HEIGHT_COMPACT if self.compact else self.HEIGHT
        super().__init__(master, fg_color="transparent", height=height, corner_radius=0)
        self.pack_propagate(False)
        self.pal = pal
        self.key = key
        self.on_click = on_click
        self.active = False
        self.text = label

        # "tlacidlo" - zaobleny podklad, ktory nesie hover/aktivne pozadie
        self.box = ctk.CTkFrame(self, fg_color="transparent", corner_radius=8,
                                height=height - 2)
        self.box.pack(fill="both", expand=True, pady=1)
        self.box.pack_propagate(False)

        if self.compact:
            # Ikona + kratky popisok pod nou (Dnes/Historia/V hre/Nastavenia).
            # Popisok sa vratil v 2.1: v ~78 px paneli sa kratke sk/en nazvy
            # zmestia a hrac nemusi hadat, co ktora ikona znamena. Tooltip
            # ostava pre dlhsie preklady, ktore by sa orezali.
            self.icon = ctk.CTkLabel(self.box, text=icon, anchor="center",
                                     font=("Segoe UI", 18), text_color=pal["text_2"])
            self.icon.pack(side="top", pady=(5, 0))
            self.label = ctk.CTkLabel(self.box, text=label, anchor="center",
                                      font=("Segoe UI", 9), text_color=pal["text_2"])
            self.label.pack(side="top", pady=(0, 2))
            self.badge = ctk.CTkLabel(self.box, text="", anchor="e",
                                      font=("Segoe UI", 9, "bold"), text_color=pal["text_3"])
            _HoverTip(self.box, lambda: self.text)
        else:
            self.icon = ctk.CTkLabel(self.box, text=icon, width=self.ICON_W,
                                     anchor="center", font=("Segoe UI", 12),
                                     text_color=pal["text_2"])
            self.icon.pack(side="left", padx=(6, 6))
            self.badge = ctk.CTkLabel(self.box, text="", anchor="e",
                                      font=("Segoe UI", 11), text_color=pal["text_3"])
            # odznak sa pack-uje az v set_badge (prazdny nezabera miesto)
            self.label = ctk.CTkLabel(self.box, text=label, anchor="w",
                                      font=("Segoe UI", 12), text_color=pal["text_2"])
            self.label.pack(side="left", fill="x", expand=True)

        for widget in (self.box, self.icon, self.label, self.badge):
            widget.bind("<Button-1>", self._clicked)
            widget.bind("<Enter>", self._enter)
            widget.bind("<Leave>", self._leave)
            try:
                widget.configure(cursor="hand2")
            except Exception:
                pass

    # ---- verejne ----

    def set_badge(self, text=""):
        text = str(text or "")
        try:
            self.badge.configure(text=text)
            if self.compact:
                if text:
                    self.badge.place(relx=1.0, x=-6, y=3, anchor="ne")
                else:
                    self.badge.place_forget()
                return
            if text and not self.badge.winfo_ismapped():
                self.badge.pack(side="right", padx=(6, 10), before=self.label)
            elif not text and self.badge.winfo_ismapped():
                self.badge.pack_forget()
        except Exception:
            pass

    def set_active(self, active):
        self.active = bool(active)
        self._paint(hover=False)

    def set_pal(self, pal):
        """Prepise vlastnu kopiu palety a hned prekresli.

        Riadok si farby DRZI a znovu ich nanasa pri kazdom hover/aktivacii
        (`_paint`). Keby sa pri zmene temy prepisali len farby widgetov a
        nie tento slovnik, prvy prechod mysou by vratil stare farby.
        """
        self.pal = pal
        self._paint(hover=False)

    # ---- vnutro ----

    def _clicked(self, _event=None):
        if callable(self.on_click):
            self.on_click(self.key)

    def _enter(self, _event=None):
        self._paint(hover=True)

    def _leave(self, _event=None):
        # Leave pride aj pri prechode z podkladu na jeho vlastny label -
        # hover zhasneme len ked kurzor naozaj opustil riadok
        try:
            px, py = self.winfo_pointerxy()
            x0, y0 = self.box.winfo_rootx(), self.box.winfo_rooty()
            inside = (x0 <= px < x0 + self.box.winfo_width()
                      and y0 <= py < y0 + self.box.winfo_height())
        except Exception:
            inside = False
        self._paint(hover=inside)

    def _paint(self, hover):
        pal = self.pal
        if self.active:
            bg, fg = pal["active"], pal["text"]
        elif hover:
            bg, fg = pal["hover"], pal["text_2"]
        else:
            bg, fg = "transparent", pal["text_2"]
        try:
            self.box.configure(fg_color=bg)
            self.icon.configure(text_color=fg)
            self.label.configure(text_color=fg)
            self.badge.configure(text_color=pal["text_2"] if self.active else pal["text_3"])
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Enso (残) - znacka appky a zaroven spinac pocuvania, HORE v paneli
# ---------------------------------------------------------------------------
class _StateDot(ctk.CTkFrame):
    """Bodka v bocnom paneli: pocuva / nepocuva / odlozena.

    PRECO VOBEC EXISTUJE
    --------------------
    Do 2.1 niesla stav znacka hore v paneli a bola vidno na KAZDEJ stranke.
    Od prestavby zije znacka v strede stranky Dnes a dychajuci pas tiez -
    obe su deti tej stranky, takze na Historii, V hre, Zvuku a Nastaveniach
    nezostalo v okne NIC, co by povedalo, ci appka pocuva. To je strata
    schopnosti, nie zmena vzhladu.

    Bodka je najmensia vec, ktora tu schopnost vrati. Zamerne NIE je to
    druhe enso: dve znacky v jednom okne by si konkurovali a platilo by sa
    za druhu sadu snimok. Farba podla `theme.py` znamena to iste co na
    znacke - zelena pocuva, cervena nie.

    TRETI STAV: ODLOZENA
    --------------------
    Odlozenie ("teraz nie") sa zapina globalnou skratkou a malo svoju
    farbu na ikone 😴 v rychlom doku. Dok z panela odisiel (viz `app.py`,
    `_build_ui`), cize odlozenie by sa dalo zapnut skratkou a hrac by
    NIKDE nevidel, ze je appka odlozena - dozvedel by sa to az tym, ze
    mlci. To je ta ista trieda chyby, ako ked sa stratila kontrolka stavu
    z piatich stranok.

    Odlozena bodka je preto JANTAROVA (`warn`) a ma prstenec - farba sama
    by v periferii splynula s cervenou. Odlozenie ma prednost pred
    pocuvanim: ked appka pocuva, ale je odlozena, plati odlozena.

    Nie je to tlacidlo. Spinac je jeden a je v dychajucom pase.
    """

    SIZE = 10

    def __init__(self, master, pal, tip=""):
        super().__init__(master, fg_color="transparent",
                         width=self.SIZE + 8, height=self.SIZE + 8)
        self.pack_propagate(False)
        self._pal = pal
        self._live = False
        self._snoozed = False
        self.canvas = tk.Canvas(self, width=self.SIZE + 8, height=self.SIZE + 8,
                                bg=pal["bg"], highlightthickness=0, bd=0)
        self.canvas.pack()
        self._tip_text = tip
        self._tip = _HoverTip(self.canvas, lambda: self._tip_text)
        self._redraw()

    def set_live(self, live):
        live = bool(live)
        if live == self._live:
            return
        self._live = live
        self._redraw()

    def set_snoozed(self, snoozed, tip=None):
        """Odlozena appka. `tip` nesie aj zvysny cas - bez neho by bodka
        povedala len "nieco je inak", nie dokedy."""
        snoozed = bool(snoozed)
        if tip is not None:
            self._tip_text = tip
        if snoozed == self._snoozed:
            return
        self._snoozed = snoozed
        self._redraw()

    def set_pal(self, pal):
        self._pal = pal
        try:
            self.canvas.configure(bg=pal["bg"])
        except Exception:
            pass
        self._redraw()

    def _redraw(self):
        c, pal = self.canvas, self._pal
        try:
            c.delete("all")
        except Exception:
            return
        r = self.SIZE / 2.0
        stred = (self.SIZE + 8) / 2.0
        if self._snoozed:
            farba = pal.get("warn", pal["danger"])
            # Prstenec, nie len ina farba: jantarova a cervena su v
            # periferii takmer to iste, kym nemaju iny TVAR.
            c.create_oval(stred - r - 3, stred - r - 3, stred + r + 3, stred + r + 3,
                          outline=farba, width=1)
        else:
            farba = pal["success"] if self._live else pal["danger"]
        c.create_oval(stred - r, stred - r, stred + r, stred + r,
                      fill=farba, outline="")


class _EnsoButton(ctk.CTkFrame):
    """Znacka appky (残 v ense) a zaroven spinac pocuvania.

    Sedi HORE v bocnom paneli - je to prve, co v okne vidno, takze nesie
    logo appky a stav naraz. Predtym bolo v strede panela a mensie; ako
    znacka sa tam stratilo.

    Stav nesie FARBA, podla konvencie nahravania: zelena = pocuva sa,
    cervena = nepocuva sa. Ziadny textovy popisok (skusalo sa, text sa
    pretinal so znakom) - cely nazov akcie je v tooltipe.

    NIE JE to staticka ikona: pomaly dycha rovnakou krivkou ako dychovy
    kruh a pri pocuvani po nej obieha svetly oblúk.

    Snimky sa predratavaju DOPREDU (`_frames`), za behu sa uz len prepina
    obrazok. Vykreslenie jedneho snimku (68 px) stoji ~1,2 ms - pocitat ho pri
    kazdom tiku by znamenalo drzat CPU zbytocne hore celu dobu, co appka
    bezi. Cely cyklus (80 snimkov) sa predrata za ~125 ms, raz.

    NATIAHNUTE (`set_armed`) je tretí stav: telo drzi nad prahom uz 90 s a
    appka caka na pauzu. Kresli sa ako vnutorny prstenec (viz
    `hud_paint.render_enso`), farbu ma rovnaku - stav nesie pohyb.

    Sada snimkov pre natiahnutie sa renderuje AZ PRI PRVOM POUZITI, rovnako
    ako pasma v `_WatchPulse._sada`. Dopredu by to bolo dalsich 80 snimkov
    (~128 ms) pri kazdom starte AJ pri kazdej zmene temy - a vacsinu casu
    natiahnute nie je. Kluc je preto dvojica `(live, armed)`, nie holy bool.
    """

    # Predvolenych 68 px platilo, kym znacka sedela v bocnom rade a mala
    # zabrat takmer celu jeho sirku. Odkedy zije v strede stranky Dnes,
    # velkost jej urcuje volajuci (`app.DandurfApp.ENSO_SIZE`, teraz 150) a
    # tato hodnota je uz len zaloha pre volanie bez `size`.
    SIZE = 68
    FRAMES = 80
    # Nad tuto velkost sa kresli s dvojnasobnym prevzorkovanim namiesto
    # trojnasobneho. Odmerane pri 150 px: priemerny rozdiel jasu oproti ss=3
    # je 4/255 a okom sa nerozozna, ale cena klesne z 585 ms na 283 ms za
    # celu sadu. Pri ss=1 uz zubatost vidno.
    BIG_PX = 100
    # Kolko snimok sa dorobi v jednom tiku dokreslovania.
    BUILD_CHUNK = 8
    # 80 * 125 ms = 10 s = 6 dychov za minutu. Viz hud_paint.enso_breath.
    TICK_MS = hud_paint.ENSO_CYCLE_MS // FRAMES

    def __init__(self, master, pal, on_toggle=None, tip_start="", tip_stop="",
                 size=None):
        super().__init__(master, fg_color="transparent")
        # Velkost je parameter od 2.1: znacka sa presunula z bocneho panela
        # do stredu stranky a tam ma priestor. Pri 68 px mal prstenec
        # "natiahnute" 1,4 px a v statickom obrazku sa stracal.
        #
        # POZN: `SIZE` ostava triednou konstantou a je to stale PREDVOLENA
        # hodnota - `_build_frames` aj `_show` uz ale citaju `self.size`.
        self.size = int(size) if size else self.SIZE
        self._pal = pal
        self._on_toggle = on_toggle
        # `_live` ostava holy bool zamerne - gui_harness_auto.py sa pyta na
        # `enso._live is False/True`. Natiahnutie je samostatny priznak.
        self._live = False
        self._armed = False
        self._moon = False        # promocia: enso = zlaty mesiac (raz)
        self._moon_frames = None
        self._tip_start = tip_start
        self._tip_stop = tip_stop
        self._frames = {}      # (live, armed) -> [CTkImage, ...]
        self._i = 0
        self._after_id = None
        # Vlastny `after` retazec na dokreslovanie sady. Je ODDELENY od
        # `_after_id` (animacia) zamerne: `_WatchPulse` ma v hlavicke
        # zaznamenane, co sa stane, ked z jedneho tiku vzniknu dva retazce -
        # 5 -> 88 Tk uloh za 5 sekund a `destroy()` zrusi len jeden.
        self._build_after = None
        self._build_queue = []
        self._phase_fn = None
        self.btn = ctk.CTkLabel(self, text="", cursor="hand2")
        self.btn.pack()
        self.btn.bind("<Button-1>", self._clicked)
        self._tip = _HoverTip(self.btn, lambda: self._tip_stop if self._live else self._tip_start)
        self._build_frames()
        self._show()
        self._tick()

    def _clicked(self, _event=None):
        if callable(self._on_toggle):
            self._on_toggle()

    def set_live(self, live):
        live = bool(live)
        if live == self._live:
            return
        self._live = live
        if not live:
            # Ked appka prestane pocuvat, natiahnutie uz neplati - spustac
            # ho tiez zahodi (`CueTrigger.suspend`). Keby tu ostalo, pri
            # dalsom zapnuti by prstenec svietil hned od prvej sekundy.
            self._armed = False
        self._show()

    def set_armed(self, armed):
        """Spustac je natiahnuty - telo drzi hore a caka sa na pauzu."""
        armed = bool(armed)
        if armed == self._armed:
            return
        self._armed = armed
        self._show()

    def set_phase_source(self, fn):
        """`fn()` vrati fazu dychu 0..1, z ktorej sa ma znacka riadit.

        Appka sem posiela `KamaeBar.phase()` - dychovu linku v hlavicke.
        Znacka tak nedycha vlastnym tempom, ale PRESNE s nou: jedno okno,
        jeden rytmus. Bez toho by obe mali rovnaku periodu, ale kazda inu
        fazu a po chvili by sa hybali proti sebe.
        """
        self._phase_fn = fn

    def set_pal(self, pal):
        """Prekresli enso pri zmene temy.

        Enso je OBRAZOK - farby su do neho zapecene, takze sa `configure()`
        prefarbit neda a cela sada snimkov sa musi nakreslit znova."""
        self._pal = pal
        self._build_queue = []
        self._cancel_build()
        self._build_frames()
        if self._moon:
            self._build_moon()
        self._show()

    def graduate(self):
        """PROMOCIA: enso sa uzavrie do zlateho mesiaca a ostane takym (aj po
        restarte - appka to obnovi z flagu `zanshin_graduated`). Appka bezi
        dalej; je to len znacka dosiahnutia, nie zmena funkcie."""
        if self._moon:
            return
        self._moon = True
        self._build_moon()
        self._show()

    def _build_moon(self):
        """Sada snimkov "zlateho mesiaca" - uzavrety kruh (close=1) s mekkou
        ziarou (halo), ktora jemne dycha. Stavia sa raz pri promocii / pri
        starte uz promovanej appky."""
        try:
            style = hud_paint.Style(self._pal)
        except Exception:
            return
        ss = 2 if self.size > self.BIG_PX else hud_paint.SS
        frames = []
        pocet = 48
        for i in range(pocet):
            faza = i / float(pocet)
            dych = hud_paint.enso_breath(faza)
            img = hud_paint.render_enso(self.size, style, live=True, phase=faza,
                                        ss=ss, close=1.0, sheen=False,
                                        halo=0.55 + 0.45 * dych)
            frames.append(ctk.CTkImage(light_image=img, dark_image=img,
                                       size=(self.size, self.size)))
        self._moon_frames = frames

    def destroy(self):
        # Bez tohto by `after` retazec bezal dalej nad znicenym widgetom a
        # Tk by pri kazdom tiku hlasil "invalid command name". Retazce su
        # DVA - animacia aj dokreslovanie - a zrusit treba oba.
        self._build_queue = []
        self._cancel_build()
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        super().destroy()

    # ---- vnutro ----

    def _build_frames(self):
        try:
            style = hud_paint.Style(self._pal)
        except Exception:
            return
        self._frames = {}

        ss = 2 if self.size > self.BIG_PX else hud_paint.SS

        def snimok(live, phase, armed=False):
            img = hud_paint.render_enso(self.size, style, live=live,
                                        phase=phase, armed=armed, ss=ss,
                                        sheen=True)
            return ctk.CTkImage(light_image=img, dark_image=img,
                                size=(self.size, self.size))

        self._snimok = snimok

        # Zastavena appka sa NEHYBE a je na najmensom polomere - jediny
        # snimok. Nehybnost je tu nositelom informacie rovnako ako farba:
        # appka, ktora nepocuva, nema posobit ziva. (A 80 identickych
        # snimkov by bolo 96 ms prace navyse pri kazdom starte.)
        try:
            self._frames[(False, False)] = [snimok(False, 0.0)]
        except Exception:
            pass

        # ANIMACIA SA DOKRESLUJE NA POZADI. Pri 150 px stoji cela sada aj s
        # ss=2 okolo 283 ms - a plati sa za nu pri KAZDOM starte aj pri
        # KAZDEJ zmene temy, proti rozpoctu ~673 ms na prepnutie temy.
        # Preto sa hned nakresli len prva snimka (znacka je okamzite na
        # svojom mieste, len nehybna) a zvysok sa dorobi po kuskoch. Kym
        # nie je sada cela, `_phase_index` vracia 0, takze sa nic neseka.
        try:
            self._frames[(True, False)] = [snimok(True, 0.0)]
        except Exception:
            pass
        self._build_queue = [(True, False), (True, True)]
        self._schedule_build()

    def _schedule_build(self):
        """Naplanuje dalsi kusok dokreslovania. JEDINE miesto, kde vznika
        `_build_after` - aby nemohli vzniknut dva retazce naraz."""
        self._cancel_build()
        if not self._build_queue:
            return
        try:
            self._build_after = self.after(30, self._build_step)
        except Exception:
            self._build_after = None

    def _cancel_build(self):
        if self._build_after is not None:
            try:
                self.after_cancel(self._build_after)
            except Exception:
                pass
            self._build_after = None

    def _build_step(self):
        """Dorobi `BUILD_CHUNK` snimok a naplanuje sa znova.

        Sam sa NEVOLA odnikial ineho nez z `_schedule_build` - inak by z
        jedneho tiku vznikli dva retazce (viz `_WatchPulse._render_now`).
        """
        self._build_after = None
        tvorca = getattr(self, "_snimok", None)
        if tvorca is None or not self._build_queue:
            self._build_queue = []
            return
        kluc = self._build_queue[0]
        _live, armed = kluc
        sada = self._frames.get(kluc)
        if sada is None:
            sada = self._frames[kluc] = []
        hotovo = 0
        while len(sada) < self.FRAMES and hotovo < self.BUILD_CHUNK:
            try:
                sada.append(tvorca(True, len(sada) / float(self.FRAMES),
                                   armed=armed))
            except Exception:
                self._build_queue = []
                return
            hotovo += 1
        if len(sada) >= self.FRAMES:
            self._build_queue.pop(0)
            self._show()               # sada je cela, animacia sa rozbehne
        self._schedule_build()

    def _hotova(self, kluc):
        return len(self._frames.get(kluc) or ()) >= self.FRAMES

    def _sada(self, kluc):
        """Snimky pre dany stav; natiahnute sa dorenderuje az pri prvom
        pouziti - rovnaky dovod ako v `_WatchPulse._sada`.

        Dopredu by to bolo 80 snimkov navyse (~128 ms) pri starte aj pri
        kazdej zmene temy, a prstenec vacsinu casu nesvieti.
        """
        sada = self._frames.get(kluc)
        if sada is not None:
            return sada
        live, armed = kluc
        if not live:
            # Zastavene + natiahnute nemoze nastat (`set_live` priznak zhodi),
            # ale keby predsa, radsej nehybny snimok nez prazdno.
            return self._frames.get((False, False))
        # Sada sa uz NEDORENDERUJE synchronne - pri 150 px by to bolo cez
        # 280 ms zamrznuteho okna prave vo chvili, ked sa appka natiahla.
        # Zaradi sa na dokreslovanie a dovtedy sa ukazuje bezna beziaca sada.
        if kluc not in self._build_queue:
            self._build_queue.append(kluc)
            self._schedule_build()
        return self._frames.get((True, False))

    # Vrchol dychu ensa (koniec nadychu + pauza) je v useku 0.42-0.48,
    # teda v strede na 0.45; dychova linka KamaeBaru vrcholi na 0.50.
    # Enso teda cita `linka_faza + OFFSET` a aby jeho plato pripadlo na
    # 0.50, musi byt OFFSET zaporny: 0.45 - OFFSET = 0.50.
    # (Najprv som tu mal +0.05 a enso vrcholilo o skoro sekundu SKOR nez
    # linka - vidno to bolo az na meranom priebehu oboch kriviek vedla
    # seba, nie okom.)
    PHASE_OFFSET = -0.05

    def _phase_index(self):
        """Poradie snimku - z dychovej linky, ak ju appka poskytla."""
        if not self._hotova((True, False)):
            return 0                 # sada sa dokresluje - znacka stoji
        pocet = len(self._frames.get((True, False)) or ()) or self.FRAMES
        if callable(self._phase_fn):
            try:
                faza = float(self._phase_fn())
            except Exception:
                faza = None
            if faza is not None:
                return int(((faza + self.PHASE_OFFSET) % 1.0) * pocet) % pocet
        return self._i % pocet

    def _show(self):
        if self._moon and self._moon_frames:
            n = len(self._moon_frames)
            faza = 0.0
            if callable(self._phase_fn):
                try:
                    faza = float(self._phase_fn())
                except Exception:
                    faza = 0.0
            idx = int(((faza + self.PHASE_OFFSET) % 1.0) * n) % n
            try:
                self.btn.configure(image=self._moon_frames[idx])
            except Exception:
                pass
            return
        sada = self._sada((self._live, self._armed and self._live))
        if not sada:
            return
        index = self._phase_index() if self._live else 0
        try:
            self.btn.configure(image=sada[index % len(sada)])
        except Exception:
            pass

    def _tick(self):
        # Zastavena appka nema co animovat - snimok je jeden a nehybny.
        # Tikat dalej ale musime, aby sa animacia rozbehla hned, ako sa
        # pocuvanie zapne.
        if self._live or self._moon:
            self._i += 1
            self._show()
        # POZOR: tento zaver metody je to, co drzi animaciu nazive. Raz uz
        # sa mi ho podarilo pri uprave odrezat a enso tiklo len raz pri
        # starte - `_after_id` ostalo None a znacka stala. Indexy snimkov
        # sa pritom pocitali spravne, takze to bolo vidno az na tom, ze sa
        # OBRAZ na obrazovke vobec nemeni.
        try:
            interval = self.TICK_MS if self.winfo_viewable() else self.TICK_MS * 4
        except Exception:
            interval = self.TICK_MS * 4
        try:
            self._after_id = self.after(interval, self._tick)
        except Exception:
            self._after_id = None


class _EnsoHero:
    """Znacka (残 v ense) kreslena PRIAMO na Canvas stredu Dnes - nie widget.

    PRECO nie widget: CTk/tk widget nevie byt priehladny nad fotkou
    (`fg_color="transparent"` zdedi PLNU farbu rodica), takze enso aj text nad
    dojom vzdy sedeli na tmavom STVORCI. `_EnsoHero` nie je widget: `render()`
    vrati PRIEHLADNE PNG (PIL RGBA), ktore appka polozi na Canvas cez
    `create_image` - alfa splynie s dojom a kruh plava. Text sa na to iste
    platno kresli cez `create_text` (bez pozadia). Box tym zmizne.

    Stav (`_live`/`_armed`/`_moon`) aj API (`set_live`/`set_armed`/
    `set_phase_source`/`graduate`/`set_pal`/`phase`) su ZHODNE s `_EnsoButton`,
    takze coupling ostava bezo zmeny: `app.sidebar.enso` (alias), harness sa
    pyta na `enso._live`/`_armed`, `_apply_listening_visuals` vola `set_live/
    set_armed`, promocia `graduate()`. `_EnsoButton` v tomto subore zostava
    (pouzity nikde uz nie je, ale par testov a `theme_recolor` sa naň viažu).

    Miesto predratania 80 Tk snimok si drzi maly cache PIL snimok podla fazy -
    rovnaky napad (nulovy per-tick naklad pri opakovanej faze), len bez widgetu.
    """

    FRAMES = 60
    # Rovnaky posun aj prah prevzorkovania ako `_EnsoButton`, nech vyzera enso
    # v strede rovnako, ci uz ho kreslil widget alebo Canvas.
    PHASE_OFFSET = _EnsoButton.PHASE_OFFSET
    BIG_PX = _EnsoButton.BIG_PX

    def __init__(self, pal, size, on_change=None):
        self._pal = pal
        self.size = int(size)
        self._on_change = on_change
        # `_live` ostava holy bool zamerne - gui_harness_auto.py sa pyta na
        # `enso._live is False/True`. Natiahnutie je samostatny priznak.
        self._live = False
        self._armed = False
        self._moon = False         # promocia: enso = zlaty mesiac (raz)
        self._phase_fn = None
        self._cache = {}           # (live, armed, moon, faza_bucket, px) -> PIL RGBA

    def set_phase_source(self, fn):
        """`fn()` vrati fazu dychu 0..1 (appka posiela `KamaeBar.phase()`) -
        enso dycha PRESNE s dychovou linkou v hlavicke, nie vlastnym tempom."""
        self._phase_fn = fn

    def phase(self):
        if callable(self._phase_fn):
            try:
                return float(self._phase_fn()) % 1.0
            except Exception:
                return 0.0
        return 0.0

    def set_live(self, live):
        live = bool(live)
        if live == self._live:
            return
        self._live = live
        if not live:
            # Ked appka prestane pocuvat, natiahnutie uz neplati.
            self._armed = False
        self._emit()

    def set_armed(self, armed):
        """Spustac je natiahnuty - telo drzi hore a caka sa na pauzu."""
        armed = bool(armed)
        if armed == self._armed:
            return
        self._armed = armed
        self._emit()

    def graduate(self):
        """PROMOCIA: enso sa uzavrie do zlateho mesiaca a ostane takym. Appka
        bezi dalej; je to len znacka dosiahnutia, nie zmena funkcie."""
        if self._moon:
            return
        self._moon = True
        self._emit()

    def set_pal(self, pal):
        """Prekresli enso pri zmene temy. Enso je OBRAZOK - farba je zapecena,
        takze cache treba zahodit a nechat appku prekreslit canvas."""
        self._pal = pal
        self._cache.clear()
        self._emit()

    def _emit(self):
        if callable(self._on_change):
            try:
                self._on_change()
            except Exception:
                pass

    def render(self, px):
        """PIL RGBA enso pre aktualny stav; `px` = FYZICKA velkost na Canvase.

        Faza sa kvantuje na `FRAMES` krokov a snimka sa cachuje - opakovany
        tik v tej istej faze uz nekresli nic. Nastroj je `hud_paint.render_enso`
        s rovnakymi parametrami ako mal `_EnsoButton`."""
        px = max(8, int(px))
        live = self._live
        armed = self._armed and self._live
        moon = self._moon
        if live or moon:
            faza_raw = (self.phase() + self.PHASE_OFFSET) % 1.0
            bucket = int(faza_raw * self.FRAMES) % self.FRAMES
        else:
            bucket = 0        # zastavene enso stoji - jedina snimka
        kluc = (live, armed, moon, bucket, px)
        img = self._cache.get(kluc)
        if img is not None:
            return img
        try:
            style = hud_paint.Style(self._pal)
        except Exception:
            return None
        ss = 2 if px > self.BIG_PX else hud_paint.SS
        faza = bucket / float(self.FRAMES)
        try:
            if moon:
                dych = hud_paint.enso_breath(faza)
                img = hud_paint.render_enso(px, style, live=True, phase=faza,
                                            ss=ss, close=1.0, sheen=False,
                                            halo=0.55 + 0.45 * dych)
            else:
                img = hud_paint.render_enso(px, style, live=live, phase=faza,
                                            armed=armed, ss=ss, sheen=True)
        except Exception:
            return None
        if len(self._cache) > 240:
            self._cache.clear()
        self._cache[kluc] = img
        return img


class _WatchPulse(ctk.CTkFrame):
    """Kontrolka senzora tepu - prstenec s hodinkami, medzi "V hre" a
    "Nastaveniami". Klik otvara sprievodcu parovanim.

    LOGIKA STAVOV (v tomto poradi):
      1. NESPAROVANE - prstenec tlmeny a NEHYBNY, hodinky sive.
         Nie je co odrazat, tak sa nic nehybe.
      2. SPAROVANE, TEP ESTE NEDOSIEL - prstenec svieti neutralne a pomaly
         dycha: "spojene, cakam".
      3. TEP BEZI - prstenec bije v REALNOM rytme hodiniek a farbu berie
         z pasma zataze.

    Rytmus berie z `HeartStats.beat_phase()` - z toho isteho zdroja ako
    srdce na HUD-e v hre, takze oba bijú naraz. Fixna animacia (napr. raz
    za sekundu) je bezna chyba: kontrolka potom UKAZUJE iny tep, nez aky
    hodinky naozaj hlasia.

    Farba ide z pasiem, ktore appka uz ma (`hud_paint.zone_color`), takze
    rovnaka farba znamena to iste tu aj nad hrou. Farba ale NIE JE jediny
    nosic - hlavnu informaciu nesie RYCHLOST tepania, citatelna aj pre
    ~12 % muzov, ktori nerozlisia cervenu od zelenej.
    """

    # Medzi polozkou navigacie (48) a ensom/znackou (68) - kontrolka je
    # dolezitejsia nez polozka menu, ale znacka ostava najvacsia.
    SIZE = 56
    FRAMES = 20
    TICK_MS = 60           # dost husto, aby tep nesekal aj pri 180 BPM
    WAIT_CYCLE_MS = 2600   # "cakam na tep" dycha pomaly

    def __init__(self, master, pal, on_click=None, tip_fn=None,
                 tip_live_fn=None):
        super().__init__(master, fg_color="transparent")
        self._pal = pal
        self._on_click = on_click
        self._state_fn = None
        self._frames = {}
        self._after_id = None
        self._last_key = None
        self._snimok = None
        self.btn = ctk.CTkLabel(self, text="", cursor="hand2")
        self.btn.pack()
        self.btn.bind("<Button-1>", self._clicked)

        # Bublina hovorila "Sparovat hodinky" aj vtedy, ked uz boli
        # sparovane a prstenec bil - vtedy je to matuce, lebo klik vtedy
        # otvara navod na parovanie nie preto, ze treba parovat.
        def popis():
            if self._je_zive() and callable(tip_live_fn):
                try:
                    return tip_live_fn()
                except Exception:
                    pass
            return tip_fn() if callable(tip_fn) else "Spárovať hodinky"

        self._tip = _HoverTip(self.btn, popis)
        self._build_frames()
        self._tick()

    def set_state_source(self, fn):
        """`fn()` vrati (connected, waiting, zone, phase). Widget si ju
        vola sam pri kazdom tiku - tak je animacia plynula bez ohladu na
        to, ako casto chodia data z hodiniek."""
        self._state_fn = fn

    def set_pal(self, pal):
        self._pal = pal
        self._build_frames()
        self._last_key = None

    def destroy(self):
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        super().destroy()

    # ---- vnutro ----

    def _clicked(self, _event=None):
        if callable(self._on_click):
            self._on_click()

    def _je_zive(self):
        """Bezi prave tep? (pre popisok bubliny)"""
        if not callable(self._state_fn):
            return False
        try:
            connected, waiting, _, _ = self._state_fn()
        except Exception:
            return False
        return bool(connected) and not waiting

    def _build_frames(self):
        try:
            style = hud_paint.Style(self._pal)
        except Exception:
            return

        def snimok(**kw):
            img = hud_paint.render_pulse_ring(self.SIZE, style, **kw)
            return ctk.CTkImage(light_image=img, dark_image=img,
                                size=(self.SIZE, self.SIZE))

        self._frames = {}
        self._snimok = snimok
        try:
            # Nesparovane = jediny nehybny snimok. Sady pre jednotlive
            # pasma tepu sa NErenderuju dopredu - viz `_sada`.
            self._frames[("off",)] = [snimok(connected=False)]
        except Exception:
            pass

    def _sada(self, kluc):
        """Sada snimkov pre dany stav - dorenderuje sa az pri prvom pouziti.

        Dopredu sa robil aj "wait" a vsetky STYRI pasma tepu, teda 101
        snimkov. Vacsinu z nich hrac nikdy neuvidi (kto necvici, do pasma
        'critical' sa nedostane) a platilo sa za ne pri KAZDOM starte aj
        pri KAZDEJ zmene temy - odmerane ~210 ms navyse k prepnutiu temy,
        ktore bolo predtym optimalizovane na ~700 ms.
        """
        sada = self._frames.get(kluc)
        if sada is not None:
            return sada
        tvorca = getattr(self, "_snimok", None)
        if tvorca is None:
            return None
        try:
            if kluc == ("wait",):
                sada = [tvorca(connected=True, waiting=True,
                               phase=i / float(self.FRAMES))
                        for i in range(self.FRAMES)]
            elif kluc and kluc[0] == "beat":
                sada = [tvorca(connected=True, zone=kluc[1],
                               phase=i / float(self.FRAMES))
                        for i in range(self.FRAMES)]
            else:
                return None
        except Exception:
            return None
        self._frames[kluc] = sada
        return sada

    def _tick(self):
        try:
            self._render_now()
        except Exception:
            pass
        try:
            viditelne = self.winfo_viewable()
        except Exception:
            viditelne = False
        try:
            self._after_id = self.after(
                self.TICK_MS if viditelne else self.TICK_MS * 8, self._tick)
        except Exception:
            self._after_id = None

    def _render_now(self):
        connected, waiting, zone, phase = False, False, None, 0.0
        if callable(self._state_fn):
            try:
                connected, waiting, zone, phase = self._state_fn()
            except Exception:
                pass

        if not connected:
            kluc, index = ("off",), 0
        elif waiting:
            kluc = ("wait",)
            # vlastny pomaly dych - nezavisly od tepu, lebo ziadny nie je
            index = int((time.monotonic() * 1000.0 / self.WAIT_CYCLE_MS
                         * self.FRAMES)) % self.FRAMES
        else:
            kluc = ("beat", zone or "calm")
            index = int(phase * self.FRAMES) % self.FRAMES

        sada = self._sada(kluc)
        if not sada:
            return
        index = index % len(sada)
        if (kluc, index) == self._last_key:
            return          # ten isty snimok - netreba nic prekreslovat
        self._last_key = (kluc, index)
        try:
            self.btn.configure(image=sada[index])
        except Exception:
            pass
        # POZN: TU NESMIE BYT ZIADNE `self.after(...)`. Raz tu uz zabludil
        # planovaci blok z `_EnsoButton` a kedze `_render_now` sa vola z
        # `_tick`, ktory si dalsi tik planuje sam, vznikali z jedneho tiku
        # DVA nezavisle retazce. Odmerane: pri beziacom tepe 5 -> 88 uloh
        # za 5 sekund a ~3600 volani tejto metody, pricom `self._after_id`
        # drzi vzdy len to posledne - `destroy()` teda zrusi jeden retazec
        # z mnohych. Pri VYPNUTOM senzore sa to neprejavi (snimok sa
        # nemeni, metoda skonci uz na `_last_key` vyssie), preto to ani
        # bezny beh appky ani GUI harness nechytili.
        # Planovanie patri VYHRADNE do `_tick`.


# POZN: tu bola trieda `DojoBand` - fotopas pevnej vysky 130 px, ktory
# sa pakoval NAD titulkovu listu (kreslil `hud_paint.render_dojo_band` +
# `render_lamp_glow`, pulzujuce lampiony cez vlastny `.after()` retazec,
# intenzitu menil posuvnik "Pozadie dojo" v Nastaveniach).
#
# Odstranena cela: titulkova lista patri na samy vrch okna a pas nad nou
# bol 130 px mrtveho miesta, ktore uberalo z fixnej vysky okna. S triedou
# odisiel aj posuvnik, hodnota `dojo_intensity` v nastaveniach a
# `suspend_briefly()`, ktore len tlmilo mihnutie sposobene tymto pasom.
# V `hud_paint` uz `render_dojo_band`/`render_lamp_glow` nema kto volat.


# ---------------------------------------------------------------------------
# Kontajner stránok (Dashboard / Profily / Zvuk / Nastavenia)
# ---------------------------------------------------------------------------
class PageContainer(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=PAL["bg"])
        self.pages = {}
        # Co je prave navrchu. Bez toho sa zvonka nedalo overit, ci
        # navigacia naozaj prepla stranku - vsetky ramce su `place`nute,
        # takze `winfo_ismapped()` je True pre vsetky naraz.
        self.current = None

    def add_page(self, key, frame):
        frame.place(in_=self, x=0, y=0, relwidth=1, relheight=1)
        self.pages[key] = frame

    def show(self, key):
        if key in self.pages:
            self.pages[key].tkraise()
            self.current = key


# ---------------------------------------------------------------------------
# Command palette (Ctrl+K) - Toplevel popup, šípky + Enter, fuzzy substring
# ---------------------------------------------------------------------------
class CommandPalette:
    # Sirka okna a rezervovany priestor pre pravy stlpec (kategoria) - pri
    # povodnych 480px sa dlhsie popisky (napr. "Ukaz mi appku znova
    # (onboarding tour)") zrazili s kategoriou a tá zmizla mimo okna.
    WIDTH = 600
    HEIGHT = 340
    _CATEGORY_COL_PX = 130

    def __init__(self, root, commands, pal=None, placeholder=""):
        """commands: list of (label:str, tag:str, action:callable)

        `placeholder` je veta v prazdnom poli hladania. Prichadza z app.py
        uz prelozena (tento modul i18n nepozna) - predtym tu bola natvrdo
        po slovensky aj v anglickom okne.

        `pal` je paleta aktivnej temy appky. POZN: predtym ju paleta
        prikazov vobec nedostavala a farbila sa CELA z moduloveho PAL -
        ten je ladeny dozelena (#121714 karta, #2a3630 ramik, #9aa39b
        text), kym tema Sumi je neutralna (#191A22 / #2A2B36 / #9A9488).
        Po otvoreni tak nad appkou vyskocilo okno z inej farebnej rodiny.
        Rovnaka chyba ako mala TitleBar - modulovy PAL tu zostava uz len
        ako zaloha, ked sa paleta postavi bez temy.
        """
        self.root = root
        self.commands = commands
        self.placeholder = placeholder
        self.pal = pal or {}
        self.top = None
        self.listbox = None
        self.entry = None
        self.filtered = commands
        self._row_font = None

    def _c(self, key, fallback):
        return self.pal.get(key, PAL[fallback])

    def open(self):
        if self.top is not None:
            return
        c = self._c
        self.top = ui_kit.priprav_popup(tk.Toplevel(self.root))
        self.top.overrideredirect(True)
        self.top.configure(bg=c("border", "border_strong"))
        self.top.attributes("-topmost", True)

        # DPI: `self.top` je OBYCAJNY tk.Toplevel, nie CTk okno - jeho
        # `geometry()` berie FYZICKE pixely a nic neskaluje. Pisma vnutri
        # sa ale skaluju (Tk scaling), takze na 150 % displeji bola paleta
        # fyzicky 600x340 px so 150 % velkym pismom: zo 16 prikazov bolo
        # vidno 7 a posledny riadok orezany v polovici, bez posuvnika.
        # Rozmer preto nasobime rovnakym skalovanim, ake pouzivaju CTk okna
        # (rovnaky vzor ako ui_dialogs._centered_geometry).
        scaling = 1.0
        try:
            from customtkinter.windows.widgets.scaling.scaling_tracker \
                import ScalingTracker
            scaling = ScalingTracker.get_window_scaling(self.root) or 1.0
        except Exception:
            pass
        w = int(round(self.WIDTH * scaling))
        h = int(round(self.HEIGHT * scaling))
        x = self.root.winfo_x() + (self.root.winfo_width() - w) // 2
        y = self.root.winfo_y() + int(round(90 * scaling))
        self.top.geometry(f"{w}x{h}+{x}+{y}")

        card = ctk.CTkFrame(self.top, fg_color=c("surface", "bg_elevated"),
                            corner_radius=10)
        card.pack(fill="both", expand=True, padx=1, pady=1)

        # Riadok hladania: lupa + textove pole. Lupa tu nebola a horny pas
        # palety tak posobil ako prazdna diera - CTkEntry po zameraní
        # (`focus_set()` nizsie) skryje svoj placeholder, takze kym hrac
        # nezacne pisat, nie je v nom vidno vobec nic. Ikona drzi kontext
        # aj pri prazdnom poli a je to ta ista lupa, akou sa paleta otvara
        # z bocneho panela.
        search = ctk.CTkFrame(card, fg_color="transparent")
        search.pack(fill="x", padx=12, pady=(8, 0))
        ctk.CTkLabel(search, text="⌕", width=22, anchor="w",
                     text_color=c("text_faint", "text_3"),
                     font=("Segoe UI", 16)).pack(side="left")

        self.entry_var = tk.StringVar()
        self.entry = ctk.CTkEntry(
            search, textvariable=self.entry_var, placeholder_text=self.placeholder,
            fg_color="transparent", border_width=0, text_color=c("text", "text"),
            placeholder_text_color=c("text_faint", "text_3"), height=40,
            font=("Segoe UI", 13),
        )
        self.entry.pack(side="left", fill="x", expand=True)
        self.entry_var.trace_add("write", lambda *a: self._refresh())

        # Deliaca linka pod vyhladavanim - rovnaky vzor ako hlavicka karty
        # (`ui_kit.Panel`) a titulkova lista, aby paleta vyzerala ako kus
        # tej istej appky, nie ako cudzie okno.
        ctk.CTkFrame(card, fg_color=c("line_soft", "border"), height=1,
                     corner_radius=0).pack(fill="x", padx=1, pady=(8, 0))

        # Zoznam + posuvnik v jednom riadku. Posuvnik tu predtym NEBOL:
        # prikazov je 16 a aj po oprave DPI sa ich zmesti ~13, takze zvysok
        # bol pod okrajom bez akehokolvek naznaku, ze sa da scrollovat
        # (tk.Listbox sam ziadny posuvnik nekresli). CTkScrollbar je ten
        # isty prvok, aky pouzivaju scrollovatelne stranky appky.
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="both", expand=True, padx=10, pady=10)

        self._row_font = tkfont.Font(family="Segoe UI", size=11)
        self.listbox = tk.Listbox(
            row, bg=c("surface", "bg_elevated"), fg=c("text_dim", "text_2"),
            bd=0, highlightthickness=0,
            selectbackground=c("accent2", "bg_hover"),
            selectforeground=c("accent_hover", "accent"),
            font=self._row_font, activestyle="none",
        )
        self.listbox.pack(side="left", fill="both", expand=True)

        self.scrollbar = ctk.CTkScrollbar(
            row, command=self.listbox.yview, width=12,
            fg_color="transparent", button_color=c("surface_alt", "bg_hover"),
            button_hover_color=c("accent", "accent"))
        self.scrollbar.pack(side="right", fill="y", padx=(6, 0))
        self.listbox.configure(yscrollcommand=self.scrollbar.set)

        self.entry.bind("<Down>", self._move_down)
        self.entry.bind("<Up>", self._move_up)
        self.entry.bind("<Return>", self._activate)
        self.listbox.bind("<Return>", self._activate)
        # Jeden klik ROVNO spusti prikaz (ako paleta v editoroch) - predtym
        # klik iba oznacil a hrac cakal, ze sa nieco stane ("neda sa kliknut").
        self.listbox.bind("<ButtonRelease-1>", self._activate_from_click)
        self.listbox.bind("<Double-Button-1>", self._activate_from_click)
        # Escape na `entry` samotnom nestacilo: ked hrac klikol na zoznam
        # (napr. sipkami/mysou presunul fokus mimo textoveho pola), Escape
        # prestal reagovat. Viazeme ho aj na `self.top` (bind_all na urovni
        # okna), takze funguje bez ohladu na to, ktory prvok ma fokus.
        self.entry.bind("<Escape>", lambda e: self.close())
        self.listbox.bind("<Escape>", lambda e: self.close())
        self.top.bind("<Escape>", lambda e: self.close())
        self.top.bind("<FocusOut>", lambda e: self.root.after(120, self._maybe_close))

        self._refresh()
        self.entry.focus_set()

    def _maybe_close(self):
        try:
            if self.top and self.root.focus_get() is None:
                self.close()
        except Exception:
            pass

    def _refresh(self):
        query = self.entry_var.get().strip().lower()
        self.filtered = ([c for c in self.commands if query in c[0].lower()]
                         if query else self.commands)
        self.listbox.delete(0, "end")
        # Zarovnanie kategorie (pravy stlpec) sa pocita v pixeloch, nie v
        # poctu znakov - "Segoe UI" nie je monospace, takze fixny pocet
        # medzier (povodny `:<45`) pri dlhsom popisku kategoriu vytlacil
        # mimo viditelnu sirku okna. Prilis dlhy popisok sa radsej skrati
        # s "…", nez aby zrazil kategoriu von.
        font = self._row_font
        space_w = max(1, font.measure(" "))
        prefix = "  "
        text_col_px = max(120, self.WIDTH - self._CATEGORY_COL_PX - font.measure(prefix))
        for label, tag, _ in self.filtered:
            trimmed = label
            if font.measure(trimmed) > text_col_px:
                while trimmed and font.measure(trimmed + "…") > text_col_px:
                    trimmed = trimmed[:-1]
                trimmed = (trimmed + "…") if trimmed else label[:1]
            pad_px = max(space_w, text_col_px - font.measure(trimmed))
            pad = " " * max(1, int(round(pad_px / space_w)))
            self.listbox.insert("end", f"{prefix}{trimmed}{pad}{tag}")
        if self.filtered:
            self.listbox.selection_set(0)

    def _move_down(self, event):
        self._move(1)
        return "break"

    def _move_up(self, event):
        self._move(-1)
        return "break"

    def _move(self, delta):
        if not self.filtered:
            return
        sel = self.listbox.curselection()
        idx = (sel[0] + delta) % len(self.filtered) if sel else 0
        self.listbox.selection_clear(0, "end")
        self.listbox.selection_set(idx)
        self.listbox.see(idx)

    def _activate(self, event):
        sel = self.listbox.curselection()
        if sel and self.filtered:
            _, _, action = self.filtered[sel[0]]
            self.close()
            action()
        return "break"

    def _activate_from_click(self, event):
        if self.top is None:
            return "break"
        """Klik na riadok - `curselection()` uz je v tomto momente
        aktualizovana (Tk nastavi vyber PRED vyvolanim <Double-Button-1>),
        ale radsej pouzime priamo index pod kurzorom, aby klik fungoval aj
        vtedy, ked by poradie udalosti bolo ine."""
        index = self.listbox.nearest(event.y)
        if 0 <= index < len(self.filtered):
            self.listbox.selection_clear(0, "end")
            self.listbox.selection_set(index)
            _, _, action = self.filtered[index]
            self.close()
            action()
        return "break"

    def close(self):
        if self.top is not None:
            self.top.destroy()
            self.top = None


# ---------------------------------------------------------------------------
# Rýchly dock (mute / snooze / profil / stop) - plávajúci vpravo dole
# ---------------------------------------------------------------------------
class _HoverTip:
    """Jednoduchy tooltip pripojeny na widget - text sa vytvara volanim
    `text_fn()` az pri kazdom zobrazeni (nie raz pri vytvoreni), aby mohol
    odzrkadlovat aktualny stav (napr. "Zastavit" / "Spustit")."""

    WATCHDOG_MS = 250

    def __init__(self, widget, text_fn, below=False):
        self.widget = widget
        self.text_fn = text_fn
        # `below=True`: bublina POD widgetom. Pre prvky v titulkovej liste -
        # nad nimi uz je okraj okna, a viacriadkova bublina nad malym
        # prvkom by prekryla kurzor a blikala (Leave -> skry -> Enter).
        self.below = below
        self.tip = None
        self._watchdog = None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)
        # Klik na tlacidlo casto otvori popup (snooze menu, color picker) -
        # bublina by nad nim ostala visiet, lebo je topmost.
        try:
            widget.bind("<Button-1>", self._hide, add="+")
        except Exception:
            pass

    def _show(self, _event=None):
        if self.tip is not None:
            return
        x = self.widget.winfo_rootx()
        if self.below:
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        else:
            y = self.widget.winfo_rooty() - 30
        self.tip = ui_kit.priprav_popup(tk.Toplevel(self.widget))
        self.tip.overrideredirect(True)
        self.tip.attributes("-topmost", True)
        self.tip.geometry(f"+{x}+{y}")
        # `_dock_pal` si nastavuje dok (ma paletu po ruke), vsetko ostatne
        # berie aktualnu temu - nie modulovy PAL, ktory je este z maketu v4.
        pal = getattr(self.widget, "_dock_pal", None) or theme_pal()
        # Ram + rovnake zaoblenie ako panely: bublina je povrch appky, nie
        # systemovy tooltip. Bez ramu splyvala s tmavym pozadim okna.
        frame = ctk.CTkFrame(self.tip, fg_color=pal.get("surface_alt", PAL["bg_elevated"]),
                             corner_radius=8, border_width=1,
                             border_color=pal.get("border", PAL["border"]))
        frame.pack()
        ctk.CTkLabel(frame, text=self.text_fn(), fg_color="transparent",
                     text_color=pal.get("text", PAL["text"]),
                     font=("Segoe UI", 10), padx=10, pady=5).pack()
        self._arm_watchdog()

    def _arm_watchdog(self):
        """Kym je bublina vidno, kontroluj, ci ma naozaj preco byt.

        Samotne <Leave> nestaci. Bublina je `topmost` Toplevel, takze ked
        sa to raz pokazi, visi nad celou appkou az do jej zavretia - a
        <Leave> sa naozaj stratit MOZE:
          * widget zanikne pri prestavbe okna (zmena temy/jazyka volá
            `_build_ui`) - vtedy uz nema kto poslat <Leave>,
          * okno sa presunie/objavi POD kurzorom, takze Tk posle <Enter>
            bez toho, aby myš vobec pohla, a <Leave> uz nepride,
          * klik otvori popup, ktory prevezme vstup.
        Preto kazdych 250 ms overime tvrdu podmienku: widget existuje a
        kurzor je naozaj nad nim. Inak bublinu zhasneme.
        """
        try:
            self._watchdog = self.widget.after(self.WATCHDOG_MS, self._tick)
        except Exception:
            self._watchdog = None

    def _pointer_inside(self):
        try:
            w = self.widget
            if not w.winfo_exists() or not w.winfo_ismapped():
                return False
            px, py = w.winfo_pointerxy()
            x, y = w.winfo_rootx(), w.winfo_rooty()
            return (x <= px < x + w.winfo_width()
                    and y <= py < y + w.winfo_height())
        except Exception:
            return False

    def _tick(self):
        self._watchdog = None
        if self.tip is None:
            return
        if not self._pointer_inside():
            self._hide()
            return
        self._arm_watchdog()

    def _hide(self, _event=None):
        if self._watchdog is not None:
            try:
                self.widget.after_cancel(self._watchdog)
            except Exception:
                pass
            self._watchdog = None
        if self.tip is not None:
            try:
                self.tip.destroy()
            except Exception:
                pass
            self.tip = None


# POZN: MinimalPanel (BPM + 4 ikonky + enso v samostatnom malom okne
# appky) tu bola - odstranena. Rovnaka funkcia je teraz sucastou HUD
# panela v hre (hud_paint.render_hud_trigger_row + hud.StatsHud.
# configure_triggers), nie samostatny rezim celej appky. Viz
# DandurfApp._hud_trigger_info / _refresh_hud_trigger_row v app.py.


# POZN: tu bola trieda `QuickDock` - tri ikony dole v bocnom paneli
# (🔊 stisit, 😴 odlozit, ⌘ rychly profil). Odstranena vedome; dovod je
# v `app.py` pri `_build_ui`, kde sa stavala. V skratke: jednoklikove
# stisenie sa pouzije prave vtedy, ked je hlaska najopravnenejsia, a
# tym appku porazi. Odlozenie ostalo, ale ma globalnu skratku - tam ho
# hrac potrebuje, nie v okne.


# ---------------------------------------------------------------------------
# Demo stránok - v FÁZE 2 sem príde skutočný obsah zo settings_model/audio_engine
# ---------------------------------------------------------------------------
# Poznamka: tento subor kedysi mal na konci vlastnu testovaciu `main()`
# funkciu so starym, placeholder-ovym UI (nefunkcne tlacidla s
# `print("TODO...")`, samostatny dashboard bez napojenia na realnu appku).
# Realna appka sa VZDY spusta cez `main.py` -> `app.DandurfApp`, tento
# skript sa nikdy nevolal. Bola to mrtva vetva, ktoru niekto omylom spustil
# priamo (`python ui_shell.py`) a videl tak staru grafiku a nefunkcne
# tlacidla - preto bola odstranena, aby sa to uz nedalo zopakovat.
