"""Panel 'Guide / What's behind it' - a slide-out window with cards.

Each card has a temporary vector sketch drawn with tk.Canvas (simple minimalist
geometry). If <id>.png exists in the assets/guides/ folder, it is used instead
of the sketch - this way it can later be replaced with finished illustrations
from an artist without changing the code.
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
                  fill=pal["text_faint"], font=ui_kit.ui(10), width=s - 8)


def _draw_jaw(c, pal, s):
    cx, cy = s / 2, s / 2 - 6
    c.create_oval(cx - 42, cy - 52, cx + 34, cy + 40, outline=pal["accent"], width=2)
    c.create_arc(cx - 38, cy - 6, cx + 30, cy + 54, start=200, extent=160,
                style="arc", outline=pal["accent2"], width=2)
    c.create_line(cx - 8, cy + 18, cx + 8, cy + 18, fill=pal["text_dim"], width=2)
    c.create_line(cx - 8, cy + 25, cx + 8, cy + 25, fill=pal["text_dim"], width=2)
    _arrow(c, cx, cy + 18, cx, cy + 25, pal["accent2"])
    c.create_text(cx + 26, cy + 21, text="2 mm", fill=pal["text_faint"],
                 font=ui_kit.ui(10), width=s - 8)
    c.create_oval(cx - 40, cy + 4, cx - 32, cy + 12, fill=pal["danger"], outline="")
    c.create_text(cx, s - 12, text=tr("guide.jaw.sketch_caption"), fill=pal["text_faint"],
                 font=ui_kit.ui(10), width=s - 8)


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
                 fill=pal["text_faint"], font=ui_kit.ui(10), width=s - 8)


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
                 fill=pal["text_faint"], font=ui_kit.ui(10), width=s - 8)


def _draw_philosophy(c, pal, s):
    # river
    for i, y in enumerate((s * 0.62, s * 0.68, s * 0.74)):
        c.create_line(10, y, s - 10, y, fill=pal["text_faint"], width=1, dash=(2, 4))
    # raft
    raft_y = s * 0.56
    for i in range(5):
        x = 22 + i * 22
        c.create_line(x, raft_y - 16, x, raft_y, fill=pal["accent2"], width=3)
    c.create_line(20, raft_y - 16, s - 20, raft_y - 16, fill=pal["accent"], width=2)
    # moon + a finger pointing at it
    c.create_oval(s - 40, 14, s - 16, 38, outline=pal["accent"], width=2)
    c.create_line(24, 44, s - 46, 22, fill=pal["text_dim"], width=2, arrow=tk.LAST)
    c.create_text(s / 2, s - 12, text=tr("guide.philosophy.sketch_caption"),
                 fill=pal["text_faint"], font=ui_kit.ui(10), width=s - 8)


SKETCHES = {
    "grounding": _draw_grounding,
    "jaw": _draw_jaw,
    "periphery": _draw_periphery,
    "breath": _draw_breath,
    "philosophy": _draw_philosophy,
}


def sketch_or_image(parent, pal, card_id, size=SKETCH_SIZE):
    """Picture for a Guide card.

    Order of sources:
      1. THE REAL PICTOGRAM from the in-game overlay
         (hud_paint.render_slot_icon) - for cards that match a slot's visual
         (centre of gravity/jaw/breath). This is what the player really sees in
         the game, so the Guide shows exactly that picture, not an illustrative
         sketch (user's request).
      2. PNG from assets/guides/<id>.png if it exists (a hand-supplied
         picture).
      3. vector sketch as the last fallback (cards without their own pictogram,
         e.g. "periphery", "philosophy").
    """
    # 1. real pictogram from the overlay
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
            label.image = photo   # keep a reference, otherwise GC deletes the image
            return label
        except Exception:
            pass

    # 1b. APP BADGE for the philosophy card
    #
    # A vector sketch of a raft, a river and a moon with an arrow ("a finger
    # pointing at the moon") used to be drawn here. Next to the brush
    # pictograms of the other cards it looked like a picture from another app:
    # thin lines on a Canvas, a different raster, a different language. The
    # badge (enso + 残) says the same thing more directly - the app is the
    # finger, not the moon - and is drawn the same way as the rest of the icons
    # (`hud_paint`, the same `Style`, the same brush).
    #
    # `color=style.accent`: the enso in the sidebar is a SWITCH and reports the
    # state by colour (green running / red stopped). Here it is a logo, it does
    # not watch any state - a red badge in the handbook would read as an error.
    if card_id == "philosophy":
        try:
            import hud_paint
            style = hud_paint.Style(pal)
            img = hud_paint.render_enso(size, style, color=style.accent)
            photo = ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))
            label = ctk.CTkLabel(parent, image=photo, text="")
            label.image = photo   # keep a reference, otherwise GC deletes the image
            return label
        except Exception:
            pass

    # 2. hand-supplied PNG
    png_path = os.path.join(guides_dir(), f"{card_id}.png")
    if os.path.exists(png_path):
        try:
            from PIL import Image as PILImage
            img = PILImage.open(png_path).convert("RGBA").resize((size, size))
            photo = ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))
            label = ctk.CTkLabel(parent, image=photo, text="")
            label.image = photo  # keep a reference, otherwise GC deletes the image
            return label
        except Exception:
            pass

    # 3. vector sketch (fallback)
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
    """Guide content (cards with pictograms and explanations) - it can be put
    into a separate window as well as into a page in the left menu.

    This content used to be tied to a CTkToplevel window. The user wanted the
    Guide as an item in the left navigation, not as a button/window - that is
    why the card logic is separated from the window and can be put anywhere.
    """

    def __init__(self, parent, pal, card_ids=None, expand_first=True,
                 wraplength=380, medical_note=True):
        """`card_ids` limits which cards are built.

        Since 18. 9. the explanation for each cue sits RIGHT IN its card
        (`ui_dialogs.SlotCard`), so only the philosophy is left at the bottom
        of the page. The separate `GuidePanel` window still wants all five,
        which is why this is a parameter and not a hard-coded list.
        """
        self.pal = pal
        self._wraplength = wraplength
        self._medical_note = medical_note
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
        populate_card_body(body, card, pal, wraplength=self._wraplength,
                           medical_note=self._medical_note)


def not_medical_note(parent, pal, wraplength=380):
    """Quiet sentence: general tips, not medical advice; not a medical device.

    Whisper, not shout - the same style as the note under the insights in
    History (ui 10, text_faint), no frame and no warning colour. At most once
    on each screen: in the header of the Guide window and under the breathing
    techniques in the breath cue card (box breathing has a breath hold). Never
    goes into the game.
    """
    label = ctk.CTkLabel(parent, text=tr("guide.not_medical_note"),
                         font=ui_kit.ui(10), text_color=pal["text_faint"],
                         anchor="w", justify="left", wraplength=wraplength)
    label.pack(fill="x", anchor="w", pady=(8, 0))
    return label


def populate_card_body(body, card, pal, wraplength=380, sketch_side="right",
                       sketch_size=SKETCH_SIZE, medical_note=True):
    """Draws the content of one Guide card into any frame.

    Pulled out of `_GuideContent`, because the cue card now draws the same
    content too. If it were copied, one of those two places would drift apart
    on the first text change - and nobody would notice which one.

    `sketch_side` is here because the cue card is as wide as the whole window.
    A sketch at the right edge would fly half a metre away from the text and
    stop forming one thing with it; in the narrow Guide panel it sits right on
    the right.
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
        # The breathing techniques have breath holds. The Guide window already
        # said so in the header above the scroll - a second time on the same
        # screen is not needed.
        if medical_note:
            not_medical_note(text_col, pal, wraplength)
    elif card.get("custom_blocks") is not None:
        for cb in card["custom_blocks"]:
            block(text_col, cb["title"], cb["text"])
        if card.get("sources"):
            ctk.CTkLabel(text_col, text=tr("guide.philosophy.sources_title"),
                        font=ui_kit.ui(11, "bold"), text_color=pal["accent"],
                        anchor="w", justify="left").pack(fill="x", pady=(9, 0))
            # Three examples + a sentence saying where the full list is
            # (ZDROJE.md) - the same text as the "How it came about" panel in
            # History (guide_content).
            if card.get("sources_intro"):
                ctk.CTkLabel(text_col, text=card["sources_intro"], font=ui_kit.ui(11),
                            text_color=pal["text_dim"], anchor="w", justify="left",
                            wraplength=wraplength).pack(fill="x", pady=(2, 0))
            for src in card["sources"]:
                link = ctk.CTkLabel(
                    text_col, text=f"↗ {src['label']}", font=ui_kit.ui(10, "underline"),
                    text_color=pal["accent"], anchor="w", justify="left",
                    cursor="hand2", wraplength=wraplength)
                link.pack(fill="x", pady=(2, 0))
                link.bind("<Button-1>", lambda _e, url=src["url"]: webbrowser.open(url))
            if card.get("sources_note"):
                ctk.CTkLabel(text_col, text=card["sources_note"], font=ui_kit.ui(10),
                            text_color=pal["text_faint"], anchor="w", justify="left",
                            wraplength=wraplength).pack(fill="x", pady=(6, 0))
    else:
        block(text_col, tr("guide.block.physiology"), card["physiology"])
        block(text_col, tr("guide.block.science"), card["science"])
        block(text_col, tr("guide.block.instruction"), card["instruction"])


PHILOSOPHY_ID = "philosophy"


def card_for_slot(index):
    """The Guide card that belongs to cue `index` - or None.

    The first four cards (`guide_content.GUIDE_CARD_IDS`) are exactly the four
    somatic visuals the app draws into the game, and they map to slots 0-3 in
    the same order (`measure.CATEGORIES`). The fifth card is the philosophy -
    it belongs to no cue and sits at the bottom of the page.

    A slot the user added (index 4+) has no explanation; None is returned and
    the card simply cannot be expanded.
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
    """Philosophy and the limits of the tool - the last block of the Cues page.

    NO OWN SCROLL. The predecessor (`build_guide_page`) made another
    `CTkScrollableFrame` inside itself, which was fine while it was a separate
    page - since it sits under the cues, that meant two scrollbars side by side
    and the content squeezed into a strip a few centimetres tall.

    The four explanations for the cues are NO LONGER here: each sits in its own
    cue card, because "what is happening in the body" is something you look for
    next to the sentence you hear, not half a page lower. What is left is the
    philosophy and the sources - the only part that belongs to no particular
    cue.

    It starts COLLAPSED. It is ten links to studies; whoever wants them expands
    them, and whoever does not should not have half a metre of text hanging
    under the cues.
    """
    # A wider wrap than in the narrow Guide window: this is a card across the
    # full page width and text wrapped at 380 px would leave half a metre of
    # empty space next to it.
    return _GuideContent(parent, pal, card_ids=[PHILOSOPHY_ID],
                         expand_first=False, wraplength=620)


class GuidePanel:
    """Non-modal window with 'Guide / What's behind it' - it can be kept
    open next to the main window to browse the mechanics of each trigger.

    The card content is in _GuideContent (shared with the page in the left
    menu)."""

    def __init__(self, app):
        self.app = app
        pal = app.pal

        self.top = ctk.CTkToplevel(app.root)
        self.top.title(tr("guide.window_title"))
        self.top.configure(fg_color=pal["bg"])
        # In the centre of the work area and fully on it (the OS does not place
        # a frameless window - it opened in the corner) - see
        # `ui_kit.umiestni_dialog`.
        ui_kit.umiestni_dialog(self.top, app.root, 720, 680,
                               min_width=560, min_height=420)
        self.top.transient(app.root)

        # Own title bar instead of the OS frame - the main app window has no OS
        # frame, so "Sprievodca" (Guide) should not have a Windows title on top
        # either (that was one of the reported bugs). The content goes into
        # chrome.body.
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
        # 500, not 650 like the subtitle: the window can be narrowed to 560
        # (minsize) and the header then has ~516 px - at 650 the sentence would
        # be cut off in the middle.
        not_medical_note(header, pal, wraplength=500)

        scroll = ctk.CTkScrollableFrame(
            root, fg_color="transparent", scrollbar_button_color=pal["surface_alt"],
            scrollbar_button_hover_color=pal["accent"])
        scroll.pack(fill="both", expand=True, padx=18, pady=10)

        _GuideContent(scroll, pal, medical_note=False)

        self.top.protocol("WM_DELETE_WINDOW", self.top.destroy)

    def _header_text(self, card, expanded):
        arrow = "▾" if expanded else "▸"
        return f"{arrow}   {card['title']}      {card['trigger']}"
