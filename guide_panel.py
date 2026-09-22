"""Panel 'Sprievodca / Veda za aplikáciou' - vysuvne okno s kartami.

Kazda karta ma docasny vektorovy nacrt vykresleny cez tk.Canvas (jednoduha
minimalisticka geometria). Ak v priecinku assets/guides/ existuje
<id>.png, pouzije sa namiesto nacrtu - takto sa da neskor bez zmeny kodu
nahradit za hotove ilustracie od artistu.
"""

import math
import os
import tkinter as tk
import webbrowser

import customtkinter as ctk

import ui_kit

from guide_content import GUIDE_CARD_IDS, guide_cards
from i18n import tr
from paths import guides_dir

SKETCH_SIZE = 150


def _arrow(c, x1, y1, x2, y2, color):
    c.create_line(x1, y1, x2, y2, fill=color, width=1, arrow=tk.LAST)


def _draw_grounding(c, pal, s):
    cx = s / 2
    c.create_oval(cx - 14, 8, cx + 14, 36, outline=pal["accent"], width=2)
    c.create_line(cx, 36, cx, 76, fill=pal["accent"], width=2)
    c.create_line(cx - 20, 48, cx + 20, 48, fill=pal["accent"], width=2)
    c.create_oval(cx - 5, 73, cx + 5, 83, fill=pal["accent2"], outline="")
    c.create_line(18, 98, s - 18, 98, fill=pal["text_dim"], width=2)
    c.create_line(cx - 10, 98, cx - 10, 128, fill=pal["accent"], width=2)
    c.create_line(cx + 10, 98, cx + 10, 128, fill=pal["accent"], width=2)
    c.create_line(10, 128, s - 10, 128, fill=pal["text_dim"], width=2)
    _arrow(c, cx - 24, 58, cx - 24, 94, pal["text_faint"])
    _arrow(c, cx + 24, 58, cx + 24, 94, pal["text_faint"])
    _arrow(c, cx - 10, 103, cx - 10, 126, pal["text_faint"])
    _arrow(c, cx + 10, 103, cx + 10, 126, pal["text_faint"])
    c.create_text(cx, 140, text=tr("guide.grounding.sketch_caption"),
                  fill=pal["text_faint"], font=ui_kit.ui(8))


def _draw_jaw(c, pal, s):
    cx, cy = s / 2, s / 2 - 6
    c.create_oval(cx - 42, cy - 52, cx + 34, cy + 40, outline=pal["accent"], width=2)
    c.create_arc(cx - 38, cy - 6, cx + 30, cy + 54, start=200, extent=160,
                style="arc", outline=pal["accent2"], width=2)
    c.create_line(cx - 8, cy + 18, cx + 8, cy + 18, fill=pal["text_dim"], width=2)
    c.create_line(cx - 8, cy + 25, cx + 8, cy + 25, fill=pal["text_dim"], width=2)
    _arrow(c, cx, cy + 18, cx, cy + 25, pal["accent2"])
    c.create_text(cx + 26, cy + 21, text="2 mm", fill=pal["text_faint"],
                 font=ui_kit.ui(8))
    c.create_oval(cx - 40, cy + 4, cx - 32, cy + 12, fill=pal["danger"], outline="")
    c.create_text(cx, s - 12, text=tr("guide.jaw.sketch_caption"), fill=pal["text_faint"],
                 font=ui_kit.ui(8))


def _draw_periphery(c, pal, s):
    cx, cy = s * 0.32, s / 2 - 4
    c.create_arc(cx - 28, cy - 18, cx + 28, cy + 18, start=20, extent=140,
                style="arc", outline=pal["accent"], width=2)
    c.create_arc(cx - 28, cy - 18, cx + 28, cy + 18, start=200, extent=140,
                style="arc", outline=pal["accent"], width=2)
    c.create_oval(cx - 6, cy - 6, cx + 6, cy + 6, fill=pal["accent2"], outline="")
    for dy in (-42, -20, 0, 20, 42):
        c.create_line(cx + 16, cy, s - 8, cy + dy, fill=pal["text_faint"],
                     width=1, dash=(3, 3))
    c.create_line(cx + 16, cy - 3, s - 30, cy, fill=pal["danger"], width=1)
    c.create_line(cx + 16, cy + 3, s - 30, cy, fill=pal["danger"], width=1)
    c.create_text(s / 2, s - 12, text=tr("guide.periphery.sketch_caption"),
                 fill=pal["text_faint"], font=ui_kit.ui(8))


def _draw_breath(c, pal, s):
    pts = []
    n = 60
    for i in range(n + 1):
        x = 12 + (s - 24) * i / n
        y = s / 2 - 12 + math.sin(i / n * 4 * math.pi) * (s * 0.18)
        pts += [x, y]
    c.create_line(*pts, fill=pal["accent"], width=2, smooth=True)
    for i in range(5):
        x = 12 + (s - 24) * i / 4
        c.create_line(x, s / 2 - 20, x, s / 2 - 4, fill=pal["text_faint"], width=1)
    c.create_oval(10, s - 34, 28, s - 8, outline=pal["accent2"], width=2)
    c.create_oval(22, s - 34, 40, s - 8, outline=pal["accent2"], width=2)
    c.create_text(s / 2, s - 44, text=tr("guide.breath.sketch_caption"),
                 fill=pal["text_faint"], font=ui_kit.ui(8))


def _draw_philosophy(c, pal, s):
    # rieka
    for i, y in enumerate((s * 0.62, s * 0.68, s * 0.74)):
        c.create_line(10, y, s - 10, y, fill=pal["text_faint"], width=1, dash=(2, 4))
    # plt
    raft_y = s * 0.56
    for i in range(5):
        x = 22 + i * 22
        c.create_line(x, raft_y - 16, x, raft_y, fill=pal["accent2"], width=3)
    c.create_line(20, raft_y - 16, s - 20, raft_y - 16, fill=pal["accent"], width=2)
    # mesiac + prst ukazujuci nan
    c.create_oval(s - 40, 14, s - 16, 38, outline=pal["accent"], width=2)
    c.create_line(24, 44, s - 46, 22, fill=pal["text_dim"], width=2, arrow=tk.LAST)
    c.create_text(s / 2, s - 12, text=tr("guide.philosophy.sketch_caption"),
                 fill=pal["text_faint"], font=ui_kit.ui(8))


SKETCHES = {
    "grounding": _draw_grounding,
    "jaw": _draw_jaw,
    "periphery": _draw_periphery,
    "breath": _draw_breath,
    "philosophy": _draw_philosophy,
}


def sketch_or_image(parent, pal, card_id, size=SKETCH_SIZE):
    """Obrazok ku karte Sprievodcu.

    Poradie zdrojov:
      1. REALNY PIKTOGRAM z in-game overlay (hud_paint.render_slot_icon) -
         pre karty, ktore zodpovedaju vizualu slotu (tazisko/celust/dych).
         Toto je to, co hrac reálne uvidi v hre, takze Sprievodca ukazuje
         presne ten obrazok, nie ilustracny nacrt (poziadavka pouzivatela).
      2. PNG z assets/guides/<id>.png ak existuje (rucne dodany obrazok).
      3. vektorovy nacrt ako posledna zaloha (karty bez vlastneho piktogramu,
         napr. "periphery", "philosophy").
    """
    # 1. realny piktogram z overlay
    icon_map = {"grounding": "grounding", "jaw": "jaw", "breath": "breath",
                "release": "release", "periphery": "periphery"}
    icon_name = icon_map.get(card_id)
    if icon_name is not None:
        try:
            import hud_paint
            style = hud_paint.Style(pal)
            img = hud_paint.render_slot_icon(icon_name, size, style)
            photo = ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))
            label = ctk.CTkLabel(parent, image=photo, text="")
            label.image = photo   # drz referenciu, inak GC zmaze obrazok
            return label
        except Exception:
            pass

    # 1b. ZNACKA APPKY pre kartu o filozofii
    #
    # Kreslil sa tu vektorovy nacrt plte, rieky a mesiaca so sipkou ("prst
    # ukazuje na mesiac"). Vedla stetcovych piktogramov ostatnych kariet
    # posobil ako obrazok z inej appky: tenke ciary na Canvase, iny raster,
    # iny jazyk. Znacka (enso + 残) povie to iste priamejsie - appka je ten
    # prst, nie mesiac - a kresli sa tou istou cestou ako zvysok ikon
    # (`hud_paint`, rovnaka `Style`, rovnaky stetec).
    #
    # `color=style.accent`: enso v bocnom paneli je SPINAC a farbou hlasi
    # stav (zelena bezi / cervena stoji). Tu je to logo, ziadny stav
    # nesleduje - cervena znacka v prirucke by sa citala ako chyba.
    if card_id == "philosophy":
        try:
            import hud_paint
            style = hud_paint.Style(pal)
            img = hud_paint.render_enso(size, style, color=style.accent)
            photo = ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))
            label = ctk.CTkLabel(parent, image=photo, text="")
            label.image = photo   # drz referenciu, inak GC zmaze obrazok
            return label
        except Exception:
            pass

    # 2. rucne dodane PNG
    png_path = os.path.join(guides_dir(), f"{card_id}.png")
    if os.path.exists(png_path):
        try:
            from PIL import Image as PILImage
            img = PILImage.open(png_path).convert("RGBA").resize((size, size))
            photo = ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))
            label = ctk.CTkLabel(parent, image=photo, text="")
            label.image = photo  # drz referenciu, inak GC zmaze obrazok
            return label
        except Exception:
            pass

    # 3. vektorovy nacrt (zaloha)
    canvas = tk.Canvas(parent, width=size, height=size, bg=pal["surface_alt"],
                       highlightthickness=1, highlightbackground=pal["card_border"])
    drawer = SKETCHES.get(card_id)
    if drawer:
        try:
            drawer(canvas, pal, size)
        except Exception:
            pass
    return canvas


class _GuideContent:
    """Obsah Sprievodcu (karty s piktogramami a vysvetleniami) - da sa
    vlozit do samostatneho okna aj do stranky v lavom menu.

    Predtym bol tento obsah zviazany na CTkToplevel okno. Pouzivatel chcel
    Sprievodcu ako polozku v lavej navigacii, nie ako tlacidlo/okno - preto
    je logika kariet oddelena od okna a da sa vlozit kamkolvek.
    """

    def __init__(self, parent, pal, card_ids=None, expand_first=True,
                 wraplength=380):
        """`card_ids` obmedzi, ktore karty sa postavia.

        Od 18. 9. stoji vysvetlivka ku kazdej hlaske PRIAMO v jej karte
        (`ui_dialogs.SlotCard`), takze na spodok stranky ostava uz len
        filozofia. Samostatne okno `GuidePanel` ich chce stale vsetkych pat,
        preto je to parameter a nie natvrdo zapisany zoznam.
        """
        self.pal = pal
        self._wraplength = wraplength
        self._bodies = {}
        karty = [c for c in guide_cards()
                 if card_ids is None or c["id"] in card_ids]
        for i, card in enumerate(karty):
            self._build_card(parent, card, pal,
                             expanded=(expand_first and i == 0))

    def _header_text(self, card, expanded):
        arrow = "▾" if expanded else "▸"
        return f"{arrow}   {card['title']}      {card['trigger']}"

    def _build_card(self, parent, card, pal, expanded):
        wrap = ctk.CTkFrame(parent, fg_color=pal["surface"], corner_radius=ui_kit.RADIUS_PANEL,
                            border_width=1, border_color=pal["card_border"])
        wrap.pack(fill="x", pady=6)

        header_btn = ctk.CTkButton(
            wrap, text=self._header_text(card, expanded), anchor="w",
            fg_color="transparent", hover_color=pal["surface_alt"],
            text_color=pal["accent"] if expanded else pal["text"],
            font=ui_kit.ui(13, "bold"),
            command=lambda cid=card["id"]: self._toggle(cid))
        header_btn.pack(fill="x", padx=6, pady=6)

        body = ctk.CTkFrame(wrap, fg_color="transparent")
        self._bodies[card["id"]] = (body, header_btn, card)
        self._populate_body(body, card, pal)
        if expanded:
            body.pack(fill="x", padx=14, pady=(0, 14))

    def _toggle(self, card_id):
        body, btn, card = self._bodies[card_id]
        showing = bool(body.winfo_ismapped())
        if showing:
            body.pack_forget()
        else:
            body.pack(fill="x", padx=14, pady=(0, 14))
        expanded = not showing
        btn.configure(text=self._header_text(card, expanded),
                      text_color=self.pal["accent"] if expanded else self.pal["text"])

    def _populate_body(self, body, card, pal):
        populate_card_body(body, card, pal, wraplength=self._wraplength)


def populate_card_body(body, card, pal, wraplength=380, sketch_side="right",
                       sketch_size=SKETCH_SIZE):
    """Vykresli obsah jednej karty Sprievodcu do lubovolneho ramca.

    Vytiahnute z `_GuideContent`, lebo ten isty obsah teraz kresli aj karta
    hlasky. Keby sa to kopirovalo, jedno z tych dvoch miest by sa pri prvej
    zmene textu rozislo - a nikto by si nevsimol ktore.

    `sketch_side` je tu preto, ze karta hlasky je siroka cez cele okno.
    Nacrt pri pravom okraji by od textu odletel o pol metra a prestal by s
    nim tvorit jednu vec; v uzkom paneli Sprievodcu vpravo sedi spravne.
    """
    row = ctk.CTkFrame(body, fg_color="transparent")
    row.pack(fill="x")
    sketch_col = ctk.CTkFrame(row, fg_color="transparent")
    if sketch_side == "left":
        sketch_col.pack(side="left", padx=(0, 18), anchor="n")
    else:
        sketch_col.pack(side="right", padx=(14, 0), anchor="n")
    sketch_or_image(sketch_col, pal, card["id"], size=sketch_size).pack()
    text_col = ctk.CTkFrame(row, fg_color="transparent")
    text_col.pack(side="left", fill="both", expand=True)

    def block(parent, title, text, dim=False):
        ctk.CTkLabel(parent, text=title, font=ui_kit.ui(11, "bold"),
                    text_color=pal["accent"], anchor="w",
                    justify="left").pack(fill="x", pady=(9, 0))
        ctk.CTkLabel(parent, text=text, font=ui_kit.ui(11),
                    text_color=pal["text_dim"] if dim else pal["text"],
                    anchor="w", justify="left", wraplength=wraplength).pack(fill="x")

    if card.get("techniques") is not None:
        for tech in card["techniques"]:
            ctk.CTkLabel(text_col, text=tech["name"], font=ui_kit.ui(11, "bold"),
                        text_color=pal["accent"], anchor="w",
                        justify="left", wraplength=wraplength).pack(fill="x", pady=(9, 0))
            block(text_col, tr("guide.block.steps_title"), tech["steps"])
            block(text_col, tr("guide.block.why_title"), tech["why"], dim=True)
    elif card.get("custom_blocks") is not None:
        for cb in card["custom_blocks"]:
            block(text_col, cb["title"], cb["text"])
        if card.get("sources"):
            ctk.CTkLabel(text_col, text=tr("guide.philosophy.sources_title"),
                        font=ui_kit.ui(11, "bold"), text_color=pal["accent"],
                        anchor="w", justify="left").pack(fill="x", pady=(9, 0))
            for src in card["sources"]:
                link = ctk.CTkLabel(
                    text_col, text=f"↗ {src['label']}", font=ui_kit.ui(10, "underline"),
                    text_color=pal["accent"], anchor="w", justify="left",
                    cursor="hand2", wraplength=wraplength)
                link.pack(fill="x", pady=(2, 0))
                link.bind("<Button-1>", lambda _e, url=src["url"]: webbrowser.open(url))
    else:
        block(text_col, tr("guide.block.physiology"), card["physiology"])
        block(text_col, tr("guide.block.science"), card["science"])
        block(text_col, tr("guide.block.instruction"), card["instruction"])


PHILOSOPHY_ID = "philosophy"


def card_for_slot(index):
    """Karta Sprievodcu, ktora patri k hlaske `index` - alebo None.

    Prve styri karty (`guide_content.GUIDE_CARD_IDS`) su presne tie styri
    somaticke vizualy, ktore appka kresli do hry, a sedia na sloty 0-3 v
    tom istom poradi (`measure.CATEGORIES`). Piata karta je filozofia -
    tá nepatri ziadnej hlaske a sedi na spodku stranky.

    Slot, ktory si pridal pouzivatel (index 4+), vysvetlivku nema; vracia
    sa None a karta sa jednoducho neda rozbalit.
    """
    try:
        index = int(index)
    except (TypeError, ValueError):
        return None
    if not 0 <= index < len(GUIDE_CARD_IDS) - 1:
        return None
    card_id = GUIDE_CARD_IDS[index]
    return next((c for c in guide_cards() if c["id"] == card_id), None)


def build_guide_into(parent, pal):
    """Filozofia a hranice nastroja - posledny blok stranky Hlasky.

    ZIADNY VLASTNY SCROLL. Predchodca (`build_guide_page`) si vnutri robil
    dalsi `CTkScrollableFrame`, co bolo v poriadku, kym bol samostatnou
    strankou - odkedy sedi pod hlaskami, znamenalo to dva posuvniky vedla
    seba a obsah zovraty do pasu vysokeho par centimetrov.

    Styri vysvetlivky k hlaskam tu uz NIE SU: kazda sedi vo svojej karte
    hlasky, lebo "co sa deje v tele" clovek hlada pri tej vete, ktoru pocuje,
    nie o pol stranky nizsie. Ostala filozofia a zdroje - jedina cast, ktora
    nepatri ziadnej konkretnej hlaske.

    Zacina ZABALENA. Je to desat odkazov na studie; kto ich chce, rozbali si
    ich, a kto nie, nema pod hlaskami vysiet pol metra textu.
    """
    # Sirsie zalomenie nez v uzkom okne Sprievodcu: tu ide o kartu cez celu
    # sirku stranky a text zalomeny na 380 px by nechal vedla seba pol metra
    # prazdna.
    return _GuideContent(parent, pal, card_ids=[PHILOSOPHY_ID],
                         expand_first=False, wraplength=620)


class GuidePanel:
    """Nemodalne okno so 'Sprievodca / Veda za aplikáciou' - da sa drzat
    otvorene popri hlavnom okne a prezerat si mechaniku ku kazdemu triggeru.

    Obsah kariet je v _GuideContent (zdielany so strankou v lavom menu)."""

    def __init__(self, app):
        self.app = app
        pal = app.pal

        self.top = ctk.CTkToplevel(app.root)
        self.top.title(tr("guide.window_title"))
        self.top.configure(fg_color=pal["bg"])
        self.top.geometry("720x680")
        self.top.minsize(560, 420)
        self.top.transient(app.root)

        # Vlastna listka namiesto OS ramu - hlavne okno appky OS ram nema,
        # tak ani "Sprievodca" nema mat navrchu Windows titulok (to bola
        # jedna z nahlasenych chyb). Obsah ide do chrome.body.
        chrome = ui_kit.DialogChrome(self.top, pal, tr("guide.window_title"),
                                     on_close=self.top.destroy)
        root = chrome.body

        header = ctk.CTkFrame(root, fg_color="transparent")
        header.pack(fill="x", padx=22, pady=(18, 6))
        ctk.CTkLabel(header, text=tr("guide.panel_title"),
                    font=ui_kit.ui(17, "bold"), text_color=pal["text"]).pack(
            anchor="w")
        ctk.CTkLabel(header, text=tr("guide.panel_subtitle"),
                    font=ui_kit.ui(11), text_color=pal["text_dim"],
                    wraplength=650, justify="left").pack(anchor="w", pady=(4, 0))

        scroll = ctk.CTkScrollableFrame(
            root, fg_color="transparent", scrollbar_button_color=pal["surface_alt"],
            scrollbar_button_hover_color=pal["accent"])
        scroll.pack(fill="both", expand=True, padx=18, pady=10)

        _GuideContent(scroll, pal)

        self.top.protocol("WM_DELETE_WINDOW", self.top.destroy)

    def _header_text(self, card, expanded):
        arrow = "▾" if expanded else "▸"
        return f"{arrow}   {card['title']}      {card['trigger']}"
