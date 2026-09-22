"""Guided tour - sprievodna prehliadka appky po prvom spusteni.

Co to je
--------
Po zavreti onboardingu (alebo na poziadanie z Nastaveni) sa spusti kratka
prehliadka: postupne sa pri jednotlivych castiach rozhrania objavi bublina
s popisom "co tu je a na co to sluzi". Hrac klika Dalej, alebo kedykolvek
Preskocit.

Preco samostatny modul
----------------------
Onboarding vysvetli PRECO appka existuje (pred jej otvorenim). Guided tour
vysvetli KDE CO je (uz v otvorenej appke). Su to dve rozne veci a nemaju sa
miesat - preto samostatny subor.

Ako to funguje
--------------
Kazdy krok ukazuje na konkretny widget (napr. polozka menu, dychajuci pas).
Bublina sa umiestni vedla neho a cielovy widget sa jemne zvyrazni ramom.
Pred krokom sa v pripade potreby prepne na spravnu stranku, aby bol cielovy
prvok viditelny.

Bublina je samostatne overrideredirect okno (`tk.Toplevel`) - takze sa da
umiestnit kamkolvek nad appku a nema vlastny OS ram. Zvyraznenie ciela je
tenky farebny ram nakresleny do prekryvneho okna nad nim.

Ziadna zavislost na obsahu appky - dostane referenciu na app a zo zoznamu
krokov si berie cielove widgety cez lambda (aby sa vyhodnotili az v case
kroku, ked uz existuju).
"""

import tkinter as tk

import customtkinter as ctk

import ui_kit
from i18n import tr


# Kroky prehliadky na JEDNOM mieste: (kluc i18n, stranka, ciel, strana).
#
# Ciel je popis, nie widget - vyhodnocuje sa az v case kroku, ked uz
# existuje (`_target`). Tabulka je staticka zamerne: appka z nej vie
# povedat, kolko krokov prehliadka ma, bez toho, aby ju musela postavit
# (riadok "Prehliadka appky" v Nastaveniach ukazuje "krok 4 z 11").
#
#   None            - bublina v strede okna, bez ukazovania
#   ("nav", kluc)   - polozka bocneho menu / karta v Nastaveniach
#   ("attr", meno)  - atribut appky (panel, pas, karta)
#   ("enso",)       - znacka v bocnom paneli (spusti/zastav)
_STEPS = (
    ("welcome", "dnes", None, "center"),
    ("kamae", "dnes", ("attr", "kamae"), "below"),
    ("triggers", "spustace", ("nav", "spustace"), "below"),
    ("sound", "zvuk", ("nav", "zvuk"), "below"),
    ("ingame", "vhre", ("nav", "vhre"), "below"),
    # tepova polovica appky - v prehliadke dlho chybala uplne
    ("sensor", "vhre", ("attr", "hr_card"), "left"),
    ("today", "dnes", ("attr", "dnes_zone_panel"), "left"),
    ("history", "historia", ("nav", "historia"), "right"),
    # POZN: tu bol samostatny krok "guide", ktory ukazoval na polozku menu
    # ("nav", "guide"). Tá uz neexistuje - vysvetlivky sedia priamo v karte
    # kazdej hlasky a filozofia na spodku tej istej stranky. Krok teda
    # ukazoval na prvok, ktory sa nenajde, a prehliadka o jeden klik dlhsia
    # nepovedala nic navyse. Sprievodcu spomina krok "triggers".
    ("dock", "dnes", ("enso",), "right"),
    ("done", "dnes", None, "center"),
)


class TourStep:
    """Jeden krok prehliadky.

    target_fn : callable -> widget (vyhodnoti sa az pri kroku; None = bublina
                v strede okna, bez ukazovania na prvok)
    page      : na ktoru stranku prepnut pred krokom (None = nemenit)
    title/body: texty (klucky do i18n sa prekladaju v tour, sem uz text)
    side      : kam od cielu umiestnit bublinu ('right'/'left'/'above'/'below'/'center')
    """

    __slots__ = ("target_fn", "page", "title", "body", "side")

    def __init__(self, target_fn=None, page=None, title="", body="", side="right"):
        self.target_fn = target_fn
        self.page = page
        self.title = title
        self.body = body
        self.side = side


class GuidedTour:
    """Prehliadka appky. Vytvor s referenciou na app a zavolaj start()."""

    BUBBLE_W = 300
    # Kolko krokov prehliadka ma - appka to potrebuje vediet aj bez toho,
    # aby ju postavila (riadok "Prehliadka appky" v Nastaveniach).
    STEP_COUNT = len(_STEPS)

    def __init__(self, app, start_index=0):
        self.app = app
        self.pal = app.pal
        self.steps = self._build_steps()
        # Prehliadka sa da opustit uprostred a neskor v nej POKRACOVAT -
        # jedenast krokov nikto nepreklika naraz a zacinat vzdy od zaciatku
        # znamena, ze ju druhykrat uz nikto nepozrie.
        self._index = max(0, min(int(start_index or 0), len(self.steps) - 1))
        self._bubble = None
        self._highlight = None
        # _show() kresli bublinu s odkladom (after 60 ms). Ak medzitym pride
        # dalsie Dalej alebo Preskocit, stary odlozeny _place() by nakreslil
        # bublinu, na ktoru uz nic neukazuje - a ta by ostala visiet navzdy
        # (odchytene nazivo: dvojklik na Dalej = dve bubliny). Preto sa
        # cakajuci job rusi a kazdy _place nesie generaciu kroku.
        self._place_job = None
        self._gen = 0
        self._finished = False

    # ---- definicia krokov ----

    def _nav_row(self, key):
        """Cielovy widget navigacie: hlavna polozka v bocnom menu, alebo
        karta v Nastaveniach (Spustace/Zvuk/V hre/Sprievodca su po
        feedbacku karty, nie polozky menu). None -> bublina v strede."""
        app = self.app
        sb = getattr(app, "sidebar", None)
        if sb is not None and key in getattr(sb, "rows", {}):
            return sb.rows[key]
        nav = getattr(app, "settings_nav", None)
        if nav is not None:
            return nav.buttons.get(key)
        return None

    def _target(self, spec):
        """Widget podla popisu z `_STEPS` - az v case kroku, nie pri stavbe."""
        if spec is None:
            return None
        if spec[0] == "nav":
            return self._nav_row(spec[1])
        if spec[0] == "attr":
            return getattr(self.app, spec[1], None)
        if spec[0] == "enso":
            # Znacka uz nie je widget, ale kresba na strede Dnes
            # (`_EnsoHero` na `app.dnes_canvas`). Bublina ukazuje na canvas -
            # `app.sidebar.enso` je len stav bez `winfo_*`, nedal by sa zamerat.
            return getattr(self.app, "dnes_canvas", None)
        return None

    def _build_steps(self):
        return [
            TourStep(target_fn=(lambda s=spec: self._target(s)), page=page,
                     title=tr(f"tour.{key}.title"), body=tr(f"tour.{key}.body"),
                     side=side)
            for key, page, spec, side in _STEPS
        ]

    # ---- zivotny cyklus ----

    def start(self):
        if not self.steps:
            return
        self._show()

    def _save_progress(self, index):
        """Kde prehliadka skoncila - aby sa dalo nadviazat, nie zacinat odznova."""
        try:
            self.app.save_tour_progress(index)
        except Exception:
            pass

    def skip(self):
        """Preskocit = "teraz nie", nie "uz nikdy". Pozicia sa zapamata a
        v Nastaveniach sa ponuka Pokracovat."""
        self._finished = True
        self._cleanup()
        self._save_progress(self._index)
        try:
            self.app.mark_tour_seen()
        except Exception:
            pass

    def _cleanup(self):
        self._gen += 1                      # zneplatni odlozeny _place()
        if self._place_job is not None:
            try:
                self.app.root.after_cancel(self._place_job)
            except Exception:
                pass
            self._place_job = None
        for attr in ("_bubble", "_highlight"):
            w = getattr(self, attr)
            if w is not None:
                try:
                    w.destroy()
                except Exception:
                    pass
                setattr(self, attr, None)

    def finish(self):
        """Prehliadka dobehla do konca - pozicia sa vynuluje, takze dalsie
        spustenie z Nastaveni zacne od zaciatku."""
        self._finished = True
        self._cleanup()
        self._save_progress(0)
        # zapamataj, ze tour uz videl (app to ulozi do nastaveni)
        try:
            self.app.mark_tour_seen()
        except Exception:
            pass

    def _next(self):
        if self._finished:
            return
        self._index += 1
        if self._index >= len(self.steps):
            self.finish()
        else:
            self._save_progress(self._index)
            self._show()

    # ---- vykreslenie kroku ----

    def _show(self):
        self._cleanup()
        step = self.steps[self._index]
        if step.page:
            try:
                self.app.sidebar._select(step.page)
            except Exception:
                pass
        # nechaj UI prekreslit, potom umiestni bublinu (widget musi mat rozmery)
        gen = self._gen
        self._place_job = self.app.root.after(60, lambda: self._place(step, gen))

    def _place(self, step, gen=None):
        self._place_job = None
        if self._finished or (gen is not None and gen != self._gen):
            return                          # krok medzitym zmenili / tour skoncil
        target = None
        if step.target_fn is not None:
            try:
                target = step.target_fn()
            except Exception:
                target = None

        # zvyrazni cielovy widget
        rect = self._widget_rect(target) if target is not None else None
        if rect is not None:
            self._draw_highlight(rect)

        # postav bublinu
        self._draw_bubble(step, rect)

    def _widget_rect(self, widget):
        """(x, y, w, h) widgetu v suradniciach obrazovky, alebo None."""
        try:
            widget.update_idletasks()
            x = widget.winfo_rootx()
            y = widget.winfo_rooty()
            w = widget.winfo_width()
            h = widget.winfo_height()
            if w <= 1 or h <= 1:
                return None
            return (x, y, w, h)
        except Exception:
            return None

    def _draw_highlight(self, rect):
        x, y, w, h = rect
        pad = 4
        hl = ui_kit.priprav_popup(tk.Toplevel(self.app.root))
        hl.overrideredirect(True)
        hl.attributes("-topmost", True)
        try:
            hl.attributes("-transparentcolor", "#010101")
        except Exception:
            pass
        hl.geometry(f"{w + pad * 2}x{h + pad * 2}+{x - pad}+{y - pad}")
        canvas = tk.Canvas(hl, width=w + pad * 2, height=h + pad * 2,
                           bg="#010101", highlightthickness=0, bd=0)
        canvas.pack()
        canvas.create_rectangle(2, 2, w + pad * 2 - 2, h + pad * 2 - 2,
                                outline=self.pal["accent"], width=2)
        self._highlight = hl

    def _draw_bubble(self, step, rect):
        pal = self.pal
        # Bublina drzi CTk widgety v obycajnom tk.Toplevel, takze si ju
        # ScalingTracker zaregistruje - bez priprav_popup by spadla na
        # `block_update_dimensions_event` pri kazdej zmene DPI (crash.log).
        bubble = ui_kit.priprav_popup(tk.Toplevel(self.app.root))
        bubble.overrideredirect(True)
        bubble.attributes("-topmost", True)
        bubble.configure(bg=pal["accent2"])

        frame = ctk.CTkFrame(bubble, fg_color=pal["surface"], corner_radius=10,
                             border_width=2, border_color=pal["accent"])
        frame.pack(fill="both", expand=True, padx=2, pady=2)

        inner = ctk.CTkFrame(frame, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=18, pady=16)

        # krok X zo Y
        ctk.CTkLabel(inner, text=tr("tour.step_of", n=self._index + 1,
                                    total=len(self.steps)),
                     font=("Segoe UI", 9, "bold"),
                     text_color=pal["accent"]).pack(anchor="w")
        ctk.CTkLabel(inner, text=step.title, font=("Segoe UI", 14, "bold"),
                     text_color=pal["text"], anchor="w", justify="left",
                     wraplength=self.BUBBLE_W - 40).pack(anchor="w", pady=(4, 6))
        ctk.CTkLabel(inner, text=step.body, font=("Segoe UI", 11),
                     text_color=pal["text_dim"], anchor="w", justify="left",
                     wraplength=self.BUBBLE_W - 40).pack(anchor="w")

        # tlacidla
        btns = ctk.CTkFrame(inner, fg_color="transparent")
        btns.pack(fill="x", pady=(14, 0))
        ctk.CTkButton(btns, text=tr("tour.skip"), width=90, height=30,
                      corner_radius=8, fg_color="transparent",
                      hover_color=pal["surface_alt"], text_color=pal["text_faint"],
                      font=("Segoe UI", 11), command=self.skip).pack(side="left")
        last = self._index == len(self.steps) - 1
        ctk.CTkButton(btns, text=tr("tour.done_btn") if last else tr("tour.next"),
                      width=110, height=30, corner_radius=8,
                      fg_color=pal["accent"], hover_color=pal["accent_hover"],
                      text_color=pal["bg"], font=("Segoe UI", 11, "bold"),
                      command=self._next).pack(side="right")

        bubble.update_idletasks()
        bw = bubble.winfo_reqwidth()
        bh = bubble.winfo_reqheight()
        x, y = self._bubble_position(step, rect, bw, bh)
        bubble.geometry(f"+{x}+{y}")
        self._bubble = bubble

    def _bubble_position(self, step, rect, bw, bh):
        """Kam umiestnit bublinu - vedla cielu, alebo do stredu okna."""
        root = self.app.root
        root.update_idletasks()
        rx, ry = root.winfo_rootx(), root.winfo_rooty()
        rw, rh = root.winfo_width(), root.winfo_height()
        gap = 14

        if rect is None or step.side == "center":
            return (rx + (rw - bw) // 2, ry + (rh - bh) // 2)

        tx, ty, tw, th = rect
        if step.side == "right":
            x, y = tx + tw + gap, ty + th // 2 - bh // 2
        elif step.side == "left":
            x, y = tx - bw - gap, ty + th // 2 - bh // 2
        elif step.side == "above":
            x, y = tx + tw // 2 - bw // 2, ty - bh - gap
        else:  # below
            x, y = tx + tw // 2 - bw // 2, ty + th + gap

        # udrz bublinu na monitore, kde je okno appky. winfo_screenwidth()
        # je VZDY primarna obrazovka - na druhom monitore (napr. x < 0) by
        # bublinu pritiahol na ten prvy, prec od appky.
        left = top = 0
        right, bottom = root.winfo_screenwidth(), root.winfo_screenheight()
        try:
            import display
            cx, cy = rx + rw // 2, ry + rh // 2
            mon = next((m for m in display.monitors(root) if m.contains(cx, cy)), None)
            if mon is not None:
                left, top = mon.x, mon.y
                right, bottom = mon.x + mon.width, mon.y + mon.height
        except Exception:
            pass
        x = max(left + 8, min(right - bw - 8, x))
        y = max(top + 8, min(bottom - bh - 8, y))
        return (x, y)
