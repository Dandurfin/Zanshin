# -*- coding: utf-8 -*-
"""Vlastny vyber farby v style Zanshinu - namiesto systemoveho (Windows)
dialogu, ktory tmavym-zlatym rozhranim vobec nesadol.

Obsahuje:
  * SV plochu (sytost x jas) + zvislu listu odtienov,
  * hex / RGB pole,
  * vzorky z palety temy (rychla volba),
  * PIPETKU - vyber farby priamo z obrazovky (celoobrazovkovy nahlad s lupou),
  * tlacidlo "Predvolena" - vrati farbu spat na akcent temy (color=None).

`ask_color(app, current, title=None, allow_default=True)` vrati:
  * "#rrggbb"        - zvolena farba,
  * DEFAULT          - "vrat predvolenu" (volajuci nastavi color=None),
  * None             - zrusene, nemenit.
"""
import colorsys
import tkinter as tk

import customtkinter as ctk

import ui_kit
from i18n import tr

try:
    import numpy as np
    from PIL import Image, ImageTk, ImageGrab
    _PIL = True
except Exception:                       # pragma: no cover
    _PIL = False

DEFAULT = "__default__"                  # sentinel: vrat farbu temy


# --------------------------------------------------------------------------
# farebna matematika
# --------------------------------------------------------------------------
def hex_to_rgb(h):
    h = (h or "").strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        return (217, 184, 104)           # bezpecny zlaty fallback
    try:
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return (217, 184, 104)


def rgb_to_hex(rgb):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(round(c)))) for c in rgb)


def _sv_image(hue, w, h):
    """Plocha sytost(x) x jas(y) pre dany odtien - PIL RGB."""
    xs = np.linspace(0.0, 1.0, w, dtype=np.float32)          # sytost
    ys = np.linspace(1.0, 0.0, h, dtype=np.float32)          # jas (hore=1)
    S, V = np.meshgrid(xs, ys)
    H = np.full_like(S, hue, dtype=np.float32)
    i = np.floor(H * 6).astype(int) % 6
    f = H * 6 - np.floor(H * 6)
    p, q, t = V * (1 - S), V * (1 - f * S), V * (1 - (1 - f) * S)
    r = np.choose(i, [V, q, p, p, t, V])
    g = np.choose(i, [t, V, V, q, p, p])
    b = np.choose(i, [p, p, t, V, V, q])
    arr = (np.stack([r, g, b], axis=-1) * 255).astype(np.uint8)
    return Image.fromarray(arr, "RGB")


def _hue_image(w, h):
    """Zvisla lista odtienov 0..1 (hore->dole), plna sytost aj jas."""
    ys = np.linspace(0.0, 1.0, h, dtype=np.float32)
    rgb = np.array([colorsys.hsv_to_rgb(y, 1.0, 1.0) for y in ys], dtype=np.float32)
    arr = (rgb[:, None, :] * 255).astype(np.uint8).repeat(w, axis=1)
    return Image.fromarray(arr, "RGB")


# --------------------------------------------------------------------------
# dialog
# --------------------------------------------------------------------------
class ColorPickerDialog:
    def __init__(self, app, current, title=None, allow_default=True):
        self.app = app
        self.result = None
        pal = app.pal
        self.pal = pal
        try:
            app.set_typing(True)
        except Exception:
            pass

        r, g, b = hex_to_rgb(current)
        self._h, self._s, self._v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        self._sv_photo = None
        self._grab_img = None            # snimok obrazovky pri pipetke

        s = 1.0
        try:
            s = float(ctk.ScalingTracker.get_widget_scaling(app.root)) or 1.0
        except Exception:
            pass
        self.SVW, self.SVH = int(216 * s), int(168 * s)
        self.HUEW = int(20 * s)

        self.top = ctk.CTkToplevel(app.root)
        self.top.title(title or tr("overlay.color_title"))
        self.top.configure(fg_color=pal["bg"])
        self.top.resizable(False, False)
        self.top.transient(app.root)
        self.top.grab_set()
        chrome = ui_kit.DialogChrome(self.top, pal, title or tr("overlay.color_title"),
                                     on_close=self.close)
        body = ctk.CTkFrame(chrome.body, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=18, pady=16)

        if not _PIL:
            ctk.CTkLabel(body, text=tr("colorpick.no_pil"), text_color=pal["text"],
                         wraplength=320).pack(pady=10)
            ctk.CTkButton(body, text=tr("common.close"), command=self.close,
                          fg_color=pal["accent"], text_color=pal["bg"]).pack()
            self.top.protocol("WM_DELETE_WINDOW", self.close)
            return

        # --- horny rad: SV plocha + lista odtienov ---------------------------
        top_row = ctk.CTkFrame(body, fg_color="transparent")
        top_row.pack(fill="x")
        self.sv_canvas = tk.Canvas(top_row, width=self.SVW, height=self.SVH,
                                   highlightthickness=1,
                                   highlightbackground=pal["border"], bd=0, cursor="tcross")
        self.sv_canvas.pack(side="left")
        self.sv_canvas.bind("<Button-1>", self._sv_drag)
        self.sv_canvas.bind("<B1-Motion>", self._sv_drag)

        self.hue_canvas = tk.Canvas(top_row, width=self.HUEW, height=self.SVH,
                                    highlightthickness=1,
                                    highlightbackground=pal["border"], bd=0, cursor="sb_v_double_arrow")
        self.hue_canvas.pack(side="left", padx=(10, 0))
        self.hue_canvas.bind("<Button-1>", self._hue_drag)
        self.hue_canvas.bind("<B1-Motion>", self._hue_drag)
        hue_img = _hue_image(self.HUEW, self.SVH)
        self._hue_photo = ImageTk.PhotoImage(hue_img)
        self.hue_canvas.create_image(0, 0, anchor="nw", image=self._hue_photo)
        self._hue_marker = self.hue_canvas.create_rectangle(
            0, 0, self.HUEW, 3, outline="#ffffff", width=2)

        # --- nahlad + hex + RGB ---------------------------------------------
        mid = ctk.CTkFrame(body, fg_color="transparent")
        mid.pack(fill="x", pady=(12, 0))
        self.preview = tk.Canvas(mid, width=int(56 * s), height=int(40 * s),
                                 highlightthickness=1, highlightbackground=pal["border"], bd=0)
        self.preview.pack(side="left")

        fields = ctk.CTkFrame(mid, fg_color="transparent")
        fields.pack(side="left", padx=(12, 0), fill="x", expand=True)
        hexrow = ctk.CTkFrame(fields, fg_color="transparent")
        hexrow.pack(fill="x")
        ctk.CTkLabel(hexrow, text=tr("colorpick.hex"), text_color=pal["text_dim"],
                     font=ui_kit.ui(11), width=int(40 * s), anchor="w").pack(side="left")
        self.hex_var = tk.StringVar()
        self.hex_entry = ctk.CTkEntry(hexrow, textvariable=self.hex_var, width=int(110 * s),
                                      fg_color=pal["entry_bg"], border_color=pal["border"],
                                      text_color=pal["text"])
        self.hex_entry.pack(side="left")
        self.hex_entry.bind("<Return>", self._hex_commit)
        self.hex_entry.bind("<FocusOut>", self._hex_commit)
        self.rgb_label = ctk.CTkLabel(fields, text="", text_color=pal["text_faint"],
                                      font=ui_kit.ui(10), anchor="w")
        self.rgb_label.pack(fill="x", pady=(6, 0))

        # --- vzorky z palety -------------------------------------------------
        ctk.CTkLabel(body, text=tr("colorpick.presets"), text_color=pal["text_dim"],
                     font=ui_kit.ui(11), anchor="w").pack(fill="x", pady=(12, 4))
        sw = ctk.CTkFrame(body, fg_color="transparent")
        sw.pack(fill="x")
        for hexc in self._preset_colors():
            b = tk.Frame(sw, width=int(24 * s), height=int(24 * s), bg=hexc,
                         highlightthickness=1, highlightbackground=pal["border"], cursor="hand2")
            b.pack(side="left", padx=(0, 6))
            b.pack_propagate(False)
            b.bind("<Button-1>", lambda _e, c=hexc: self._set_hex(c))

        # --- akcie: pipetka + predvolena ------------------------------------
        act = ctk.CTkFrame(body, fg_color="transparent")
        act.pack(fill="x", pady=(14, 0))
        ctk.CTkButton(act, text=tr("colorpick.eyedropper"), width=int(130 * s),
                      fg_color=pal["surface_alt"], hover_color=pal["border"],
                      text_color=pal["text"], command=self.pick_from_screen).pack(side="left")
        if allow_default:
            ctk.CTkButton(act, text=tr("colorpick.reset_default"), width=int(120 * s),
                          fg_color=pal["surface_alt"], hover_color=pal["border"],
                          text_color=pal["text"], command=self._use_default).pack(side="left",
                                                                                  padx=(8, 0))

        # --- OK / Zrusit -----------------------------------------------------
        btns = ctk.CTkFrame(body, fg_color="transparent")
        btns.pack(fill="x", pady=(16, 0))
        ctk.CTkButton(btns, text=tr("common.cancel"), width=90, fg_color=pal["surface_alt"],
                      hover_color=pal["border"], text_color=pal["text"],
                      command=self.close).pack(side="right")
        ctk.CTkButton(btns, text=tr("common.save"), width=90, fg_color=pal["accent"],
                      hover_color=pal["accent_hover"], text_color=pal["bg"],
                      command=self._ok).pack(side="right", padx=(0, 8))

        self.top.protocol("WM_DELETE_WINDOW", self.close)
        self._render_sv()
        self._sync_from_hsv()

    # ---- paleta vzoriek ----
    def _preset_colors(self):
        pal = self.pal
        out, seen = [], set()
        for key in ("accent", "accent_hover", "accent2", "success", "warn", "danger"):
            c = pal.get(key)
            if isinstance(c, str) and c.startswith("#") and c.lower() not in seen:
                out.append(c); seen.add(c.lower())
        for c in ("#ffffff", "#9fb2c9", "#7fdd8a", "#f2a65a", "#e5657b", "#8a7bd8"):
            if c.lower() not in seen:
                out.append(c); seen.add(c.lower())
        return out[:10]

    # ---- prekreslenie SV plochy + markerov ----
    def _render_sv(self):
        img = _sv_image(self._h, self.SVW, self.SVH)
        self._sv_photo = ImageTk.PhotoImage(img)
        self.sv_canvas.delete("svimg")
        self.sv_canvas.create_image(0, 0, anchor="nw", image=self._sv_photo, tags="svimg")
        self.sv_canvas.tag_lower("svimg")
        self._draw_sv_marker()

    def _draw_sv_marker(self):
        x = self._s * self.SVW
        y = (1 - self._v) * self.SVH
        rr = max(5, self.SVW // 36)
        ring = "#000000" if self._v > 0.5 else "#ffffff"
        self.sv_canvas.delete("svmark")
        self.sv_canvas.create_oval(x - rr, y - rr, x + rr, y + rr,
                                   outline=ring, width=2, tags="svmark")

    def _draw_hue_marker(self):
        y = self._h * self.SVH
        self.hue_canvas.coords(self._hue_marker, 0, y - 1, self.HUEW, y + 2)

    # ---- interakcie ----
    def _sv_drag(self, e):
        self._s = min(1.0, max(0.0, e.x / self.SVW))
        self._v = min(1.0, max(0.0, 1 - e.y / self.SVH))
        self._draw_sv_marker()
        self._sync_from_hsv(render_sv=False)

    def _hue_drag(self, e):
        self._h = min(1.0, max(0.0, e.y / self.SVH))
        self._render_sv()
        self._sync_from_hsv(render_sv=False)

    def _hex_commit(self, _e=None):
        self._set_hex(self.hex_var.get())

    def _set_hex(self, hexc):
        s = (hexc or "").strip().lstrip("#")
        ok = len(s) in (3, 6) and all(ch in "0123456789abcdefABCDEF" for ch in s)
        if not ok:
            # Neplatny/rozpisany vstup (napr. "#ab" pri FocusOut) NEnahradzame
            # zlatym fallbackom - to by ticho zahodilo zvolenu farbu. Len
            # vratime pole spat na aktualnu farbu.
            self._sync_from_hsv(render_sv=False)
            return
        r, g, b = hex_to_rgb(hexc)
        self._h, self._s, self._v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        self._render_sv()
        self._sync_from_hsv(render_sv=False)

    def _sync_from_hsv(self, render_sv=True):
        if render_sv:
            self._render_sv()
        self._draw_hue_marker()
        r, g, b = colorsys.hsv_to_rgb(self._h, self._s, self._v)
        rgb = (r * 255, g * 255, b * 255)
        hexc = rgb_to_hex(rgb)
        if self.hex_var.get().strip().lower() != hexc.lower():
            self.hex_var.set(hexc)
        self.rgb_label.configure(text=tr("colorpick.rgb", r=int(round(rgb[0])),
                                         g=int(round(rgb[1])), b=int(round(rgb[2]))))
        self.preview.configure(bg=hexc)
        self._cur_hex = hexc

    # ---- pipetka: vyber z obrazovky ----
    def pick_from_screen(self):
        try:
            import ctypes
            u = ctypes.windll.user32
            vx, vy = u.GetSystemMetrics(76), u.GetSystemMetrics(77)     # SM_X/YVIRTUALSCREEN
            vw, vh = u.GetSystemMetrics(78), u.GetSystemMetrics(79)     # SM_CX/CYVIRTUALSCREEN
        except Exception:
            vx = vy = 0
            vw = self.top.winfo_screenwidth(); vh = self.top.winfo_screenheight()
        try:
            self._grab_img = ImageGrab.grab(bbox=(vx, vy, vx + vw, vy + vh),
                                            all_screens=True).convert("RGB")
        except Exception:
            return

        self.top.withdraw()
        ov = None

        def finish(_e=None):
            # Zavri prekrytie a VZDY vrat hlavny dialog spat - inak by pri
            # zlyhani ostalo modalne prekrytie bez dialogu a appka by sa
            # zasekla (dialog je len schovany, wait_window by necakalo darmo).
            try:
                if ov is not None:
                    ov.grab_release(); ov.destroy()
            except Exception:
                pass
            self._grab_img = None     # nedrz plochu (desiatky MB) po zatvoreni
            self._eye_photo = None
            try:
                self.top.deiconify(); self.top.grab_set(); self.top.lift()
            except Exception:
                pass

        try:
            ov = tk.Toplevel(self.app.root)
            ui_kit.priprav_popup(ov)
            ov.overrideredirect(True)
            ov.geometry(f"{vw}x{vh}+{vx}+{vy}")
            ov.attributes("-topmost", True)
            # Escape HNED, este pred stavbou obrazka - keby nizsie nieco
            # zlyhalo (velka plocha, malo pamate), da sa prekrytie zavriet.
            ov.bind("<Escape>", finish)
            try:
                ov.grab_set()
            except Exception:
                pass
            cv = tk.Canvas(ov, width=vw, height=vh, highlightthickness=0, bd=0,
                           cursor="crosshair")
            cv.pack(fill="both", expand=True)
            self._eye_photo = ImageTk.PhotoImage(self._grab_img)
            cv.create_image(0, 0, anchor="nw", image=self._eye_photo)
            loupe = cv.create_rectangle(0, 0, 0, 0, outline="#ffffff", width=2, state="hidden")
            chip = cv.create_rectangle(0, 0, 0, 0, outline="#000000", width=1, state="hidden")
            txt = cv.create_text(0, 0, text="", fill="#ffffff", font=("Consolas", 11, "bold"),
                                 anchor="nw", state="hidden")

            def at(ex, ey):
                ix = min(vw - 1, max(0, ex)); iy = min(vh - 1, max(0, ey))
                return self._grab_img.getpixel((ix, iy))

            def motion(e):
                col = rgb_to_hex(at(e.x, e.y))
                box = 26
                cx = e.x + 18 if e.x < vw - 90 else e.x - 18 - box
                cy = e.y + 18 if e.y < vh - 60 else e.y - 18 - box
                cv.coords(chip, cx, cy, cx + box, cy + box)
                cv.itemconfigure(chip, fill=col, state="normal")
                cv.coords(txt, cx + box + 6, cy + 4)
                cv.itemconfigure(txt, text=col.upper(), state="normal")
                cv.coords(loupe, e.x - 10, e.y - 10, e.x + 10, e.y + 10)
                cv.itemconfigure(loupe, state="normal")

            def pick(e):
                col = rgb_to_hex(at(e.x, e.y))
                finish(); self._set_hex(col)

            cv.bind("<Motion>", motion)
            cv.bind("<Button-1>", pick)
            ov.focus_force()
        except Exception:
            finish()      # cokolvek pri stavbe zlyha -> nezasekni appku

    # ---- vysledky ----
    def _use_default(self):
        self.result = DEFAULT
        self._teardown()

    def _ok(self):
        self.result = getattr(self, "_cur_hex", None)
        self._teardown()

    def close(self):
        self.result = None
        self._teardown()

    def _teardown(self):
        try:
            self.app.set_typing(False)
        except Exception:
            pass
        try:
            self.top.grab_release()
        except Exception:
            pass
        self.top.destroy()


def ask_color(app, current, title=None, allow_default=True):
    """Otvori modalny vyber farby a vrati vysledok (hex / DEFAULT / None)."""
    dlg = ColorPickerDialog(app, current, title=title, allow_default=allow_default)
    app.root.wait_window(dlg.top)
    return dlg.result
