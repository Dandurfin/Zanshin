"""Drawing the in-game visuals and the HUD panel - pure PIL, no Tk.

Why PIL and not tk.Canvas
-------------------------
Tk Canvas can do neither antialiasing nor translucency: every line is a
hard pixel and a "glow" cannot be done at all. The original visuals
therefore used emoji (🥾) and jagged ovals - on 4K that looks unfinished.

Here everything is drawn into an RGBA bitmap with 3x supersampling and one
Gaussian pass for the glow. The result goes either through
UpdateLayeredWindow (full alpha, see layer_window.py), or as a PhotoImage
onto a Canvas.

Visual language
---------------
Thin lines, corner brackets with bevelled corners, tick marks like on an
instrument, one accent colour + a white core, no fills except an 8 % tint.
It deliberately does NOT copy the HUD of any particular game - it is its
own "dojo" style (hexagon + brush strokes), which fits next to both a
military and a sci-fi interface, because it takes only the geometric
discipline from both.

All sizes are in "1080p pixels" - the caller multiplies them by
`display.Monitor.scale`, so on 4K everything is 2x larger and takes up the
same part of the screen.
"""

import math
import os

try:
    # NOTE: `ImageEnhance` was here too - only `render_dojo_band()` used
    # it, to dim the brightness of the photo band. With the band removed it
    # was left unused.
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    PIL_AVAILABLE = True
except Exception:  # pragma: no cover - without pillow the app draws with a fallback
    PIL_AVAILABLE = False

SS = 3  # supersampling - 3x is enough for smooth edges and is 2x faster than 4x


# --------------------------------------------------------------------------
# Fonts
# --------------------------------------------------------------------------

# Bahnschrift is a narrow DIN-style technical font that ships with both
# Windows 10 and 11 - exactly the "instrument" character the HUD needs.
# Segoe UI is the fallback (it is everywhere), DejaVu/Liberation are for
# development on Linux.
_FONT_CANDIDATES = {
    "display": ["bahnschrift.ttf", "segoeuisb.ttf", "segoeui.ttf",
                "DejaVuSansCondensed-Bold.ttf", "LiberationSans-Bold.ttf",
                "DejaVuSans-Bold.ttf"],
    "label": ["bahnschrift.ttf", "segoeui.ttf",
              "DejaVuSansCondensed.ttf", "LiberationSans-Regular.ttf",
              "DejaVuSans.ttf"],
    # CJK (the 残 character in the enso button) - first brush-style
    # (mincho), then sans (gothic) - the same combined order as
    # make_icon.py, because not every Windows installation has mincho (it
    # is missing on the development machine, but msgothic and YuGoth are
    # almost always there).
    "cjk": ["YuMinDB.ttf", "yumindb.ttf", "YuMincho.ttc", "msmincho.ttc",
            "YuGothB.ttc", "YuGothM.ttc", "meiryob.ttc", "meiryo.ttc",
            "msgothic.ttc", "msyh.ttc", "simhei.ttf",
            "NotoSerifCJK-Bold.ttc", "NotoSansCJK-Bold.ttc"],
    # JAPANESE AND CHINESE LABELS (0.3, skeptic UX 4b). Neither
    # Bahnschrift nor Segoe UI has these characters: the HUD with in-game
    # language ja/zh and its preview in the introduction (step 3, app
    # language) drew empty squares instead of "負荷". Text with CJK
    # characters gets a gothic (sans) typeface - Japanese when its
    # characters can be written in JIS (cp932), otherwise Chinese: YaHei
    # also has simplified characters (负) that the Japanese typefaces lack
    # (`_druh_pisma`).
    "label_ja": ["YuGothM.ttc", "meiryo.ttc", "msgothic.ttc", "msyh.ttc",
                 "NotoSansCJK-Regular.ttc", "NotoSansCJK-Bold.ttc"],
    "display_ja": ["YuGothB.ttc", "meiryob.ttc", "msgothic.ttc", "msyhbd.ttc",
                   "NotoSansCJK-Bold.ttc"],
    "label_zh": ["msyh.ttc", "simhei.ttf", "YuGothM.ttc", "msgothic.ttc",
                 "NotoSansCJK-Regular.ttc", "NotoSansCJK-Bold.ttc"],
    "display_zh": ["msyhbd.ttc", "msyh.ttc", "simhei.ttf", "YuGothB.ttc",
                   "NotoSansCJK-Bold.ttc"],
}


def _cjk_znak(ch):
    """A character the HUD's Latin typeface (Bahnschrift/Segoe UI) lacks:
    kana, CJK punctuation, ideographs, full-width characters."""
    o = ord(ch)
    return (0x3000 <= o <= 0x30FF or 0x31F0 <= o <= 0x31FF or 0x3400 <= o <= 0x9FFF
            or 0xF900 <= o <= 0xFAFF or 0xFF00 <= o <= 0xFFEF)


def _druh_pisma(kind, value):
    """Typeface kind for the text `value`: Latin and Cyrillic stay in
    `kind`, text with CJK characters gets `kind_ja` / `kind_zh` (see
    `_FONT_CANDIDATES`). Only for "label" and "display" - the 残
    character has its own kind "cjk"."""
    if kind not in ("label", "display"):
        return kind
    cjk = "".join(ch for ch in str(value or "") if _cjk_znak(ch))
    if not cjk:
        return kind
    try:
        cjk.encode("cp932")
        return kind + "_ja"
    except UnicodeEncodeError:
        return kind + "_zh"


_FONT_DIRS = [
    os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts"),
    "/usr/share/fonts/truetype/dejavu",
    "/usr/share/fonts/truetype/liberation",
    "/usr/share/fonts/truetype/freefont",
    "/usr/share/fonts/opentype/noto",
]

_font_cache = {}


def _load_font(kind, size):
    size = max(6, int(round(size)))
    key = (kind, size)
    if key in _font_cache:
        return _font_cache[key]
    font = None
    for name in _FONT_CANDIDATES.get(kind, []):
        for folder in _FONT_DIRS:
            path = os.path.join(folder, name)
            if not os.path.exists(path):
                continue
            try:
                font = ImageFont.truetype(path, size)
            except Exception:
                continue
            if kind == "display":
                # Bahnschrift is a variable font - without this it would
                # load in the Regular style and the numbers would be too
                # thin.
                try:
                    font.set_variation_by_name("SemiBold")
                except Exception:
                    pass
            break
        if font is not None:
            break
    if font is None:
        try:
            font = ImageFont.load_default(size)
        except Exception:
            font = ImageFont.load_default()
    _font_cache[key] = font
    return font


# --------------------------------------------------------------------------
# Style
# --------------------------------------------------------------------------

def _hex(color):
    color = color.lstrip("#")
    return (int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16))


def _rgba(color, alpha):
    if isinstance(color, str):
        color = _hex(color)
    return (color[0], color[1], color[2], max(0, min(255, int(round(alpha * 255)))))


def _mix(c1, c2, t):
    if isinstance(c1, str):
        c1 = _hex(c1)
    if isinstance(c2, str):
        c2 = _hex(c2)
    return tuple(int(round(a + (b - a) * t)) for a, b in zip(c1, c2))


class Style:
    """Colours and widths taken from the app's theme (theme.py tokens).

    `hot` is the lightened core of the accent - a thin light line inside
    the coloured one gives the stroke that "it glows" impression without
    having to raise the glow (and with it the blur).
    """

    def __init__(self, pal=None):
        pal = pal or {}
        self.accent = _hex(pal.get("accent", "#00d2ff"))
        self.danger = _hex(pal.get("danger", "#ff5c73"))
        # small red text (the limit number in the graph) - `danger_text`
        # (>= 4.5:1), `danger` only for areas and lines (rule in theme.py)
        self.danger_text = _hex(pal.get("danger_text", pal.get("danger", "#ff5c73")))
        self.warn = _hex(pal.get("warn", "#f5a623"))
        self.success = _hex(pal.get("success", "#3ddc84"))
        self.bengara = _hex(pal.get("bengara", "#a6432e"))
        self.text = _hex(pal.get("text", "#f5f7fa"))
        self.dim = _hex(pal.get("text_dim", "#8d97ab"))
        self.hot = _mix(self.accent, (255, 255, 255), 0.55)
        self.backdrop = (5, 9, 14)
        # HEART-RATE ZONES have their own series in each theme
        # (theme.ZONE_TOKENS). The fallbacks are the original tokens, so
        # that an old palette (or Style() without a palette in tests) keeps
        # working.
        self.zones = {
            "calm": _hex(pal.get("zone_calm", pal.get("success", "#3ddc84"))),
            "raised": _hex(pal.get("zone_raised", pal.get("warn", "#f5a623"))),
            "high": _hex(pal.get("zone_high", pal.get("warn", "#f5a623"))),
            "critical": _hex(pal.get("zone_critical", pal.get("danger", "#ff5c73"))),
        }

    def tinted(self, color):
        out = Style()
        out.__dict__.update(self.__dict__)
        out.accent = color if not isinstance(color, str) else _hex(color)
        out.hot = _mix(out.accent, (255, 255, 255), 0.55)
        return out


# --------------------------------------------------------------------------
# Painter
# --------------------------------------------------------------------------

class Painter:
    """Drawing surface with supersampling and glow.

    Three layers: `bg` (the panel backdrop - must not glow, otherwise it
    smears into the surroundings), `core` (the strokes) and the glow
    derived from it. All coordinates are given in logical 1080p pixels;
    the class does the conversion to supersample itself.
    """

    def __init__(self, width, height, ss=SS):
        self.w, self.h, self.ss = int(width), int(height), ss
        size = (self.w * ss, self.h * ss)
        self.bg = Image.new("RGBA", size, (0, 0, 0, 0))
        self.core = Image.new("RGBA", size, (0, 0, 0, 0))
        self._dbg = ImageDraw.Draw(self.bg)
        self._d = ImageDraw.Draw(self.core)

    # ---- helper conversions ----

    def _s(self, v):
        return v * self.ss

    def _box(self, x0, y0, x1, y1):
        return [self._s(x0), self._s(y0), self._s(x1), self._s(y1)]

    def _pts(self, points):
        return [(self._s(x), self._s(y)) for x, y in points]

    # ---- backdrop (no glow) ----

    def panel(self, x0, y0, x1, y1, color, alpha, radius=6):
        self._dbg.rounded_rectangle(self._box(x0, y0, x1, y1),
                                    radius=self._s(radius), fill=_rgba(color, alpha))

    # ---- strokes ----

    def line(self, points, color, width, alpha=1.0, joint="curve"):
        if len(points) < 2:
            return
        self._d.line(self._pts(points), fill=_rgba(color, alpha),
                     width=max(1, int(round(self._s(width)))), joint=joint)

    def polygon(self, points, color=None, alpha=1.0, outline=None,
                outline_alpha=1.0, width=1.0):
        self._d.polygon(
            self._pts(points),
            fill=_rgba(color, alpha) if color else None,
            outline=_rgba(outline, outline_alpha) if outline else None,
            width=max(1, int(round(self._s(width)))) if outline else 0)

    def ellipse(self, cx, cy, rx, ry, color=None, alpha=1.0, outline=None,
                outline_alpha=1.0, width=1.0):
        self._d.ellipse(
            self._box(cx - rx, cy - ry, cx + rx, cy + ry),
            fill=_rgba(color, alpha) if color else None,
            outline=_rgba(outline, outline_alpha) if outline else None,
            width=max(1, int(round(self._s(width)))) if outline else 0)

    def arc(self, cx, cy, rx, ry, start, end, color, width, alpha=1.0):
        self._d.arc(self._box(cx - rx, cy - ry, cx + rx, cy + ry),
                    start, end, fill=_rgba(color, alpha),
                    width=max(1, int(round(self._s(width)))))

    def paste(self, image, x, y):
        """Pastes a ready-made RGBA image (in logical pixels, e.g. from
        render_slot_icon) at position (x, y) into the `core` layer.

        The image is scaled to this surface's supersampling, so that on
        the final downscale (`finish()`) it does not blur differently
        from the rest of the drawing - otherwise the icon would look
        softer/sharper than its surroundings."""
        target_w = max(1, int(round(image.width * self.ss)))
        target_h = max(1, int(round(image.height * self.ss)))
        scaled = image.resize((target_w, target_h), Image.LANCZOS)
        px, py = int(round(self._s(x))), int(round(self._s(y)))
        self.core.alpha_composite(scaled, (px, py))

    def rect(self, x0, y0, x1, y1, color=None, alpha=1.0, outline=None,
             outline_alpha=1.0, width=1.0, radius=0):
        args = dict(fill=_rgba(color, alpha) if color else None,
                    outline=_rgba(outline, outline_alpha) if outline else None,
                    width=max(1, int(round(self._s(width)))) if outline else 0)
        if radius:
            self._d.rounded_rectangle(self._box(x0, y0, x1, y1),
                                      radius=self._s(radius), **args)
        else:
            self._d.rectangle(self._box(x0, y0, x1, y1), **args)

    def text(self, x, y, value, color, size, kind="label", alpha=1.0,
             anchor="lt", tracking=0.0):
        """Text with optional letter-spacing (`tracking`) - small caps with
        spaces between letters are what sets a "HUD label" apart from an
        ordinary app."""
        font = _load_font(_druh_pisma(kind, value), self._s(size))
        fill = _rgba(color, alpha)
        if not tracking:
            self._d.text((self._s(x), self._s(y)), value, font=font,
                         fill=fill, anchor=anchor)
            return
        gap = self._s(tracking)
        widths = [self._d.textlength(ch, font=font) for ch in value]
        total = sum(widths) + gap * max(0, len(value) - 1)
        px, py = self._s(x), self._s(y)
        if anchor[0] == "m":
            px -= total / 2.0
        elif anchor[0] == "r":
            px -= total
        v_anchor = "l" + anchor[1]
        for ch, cw in zip(value, widths):
            self._d.text((px, py), ch, font=font, fill=fill, anchor=v_anchor)
            px += cw + gap

    def measure(self, value, size, kind="label", tracking=0.0):
        font = _load_font(_druh_pisma(kind, value), self._s(size))
        total = self._d.textlength(value, font=font)
        if tracking:
            total += self._s(tracking) * max(0, len(value) - 1)
        return total / float(self.ss)

    # ---- result ----

    def finish(self, glow=2.2, gain=0.85):
        """Merge layers, scale to target size (antialiasing happens here)."""
        out = self.bg
        if glow > 0 and gain > 0:
            blurred = self.core.filter(ImageFilter.GaussianBlur(self._s(glow)))
            if gain != 1.0:
                alpha = blurred.getchannel("A").point(
                    lambda v: min(255, int(v * gain)))
                blurred.putalpha(alpha)
            out = Image.alpha_composite(out, blurred)
        out = Image.alpha_composite(out, self.core)
        if self.ss != 1:
            out = out.resize((self.w, self.h), Image.LANCZOS)
        return out


# --------------------------------------------------------------------------
# Shared elements
# --------------------------------------------------------------------------

def corner_brackets(p, x0, y0, x1, y1, st, length=14, width=1.6, alpha=0.85,
                    chamfer=5):
    """Four corner brackets with a bevelled corner - lighter on the eye
    than a whole frame, and the game stays visible beneath them."""
    c, L, ch = st.accent, length, chamfer
    p.line([(x0 + L, y0), (x0 + ch, y0), (x0, y0 + ch), (x0, y0 + L)], c, width, alpha)
    p.line([(x1 - L, y0), (x1 - ch, y0), (x1, y0 + ch), (x1, y0 + L)], c, width, alpha)
    p.line([(x0, y1 - L), (x0, y1 - ch), (x0 + ch, y1), (x0 + L, y1)], c, width, alpha)
    p.line([(x1, y1 - L), (x1, y1 - ch), (x1 - ch, y1), (x1 - L, y1)], c, width, alpha)


def hex_frame(p, cx, cy, r, st, width=1.5, alpha=0.5, rotation=90.0):
    pts = []
    for i in range(6):
        a = math.radians(rotation + i * 60.0)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    pts.append(pts[0])
    p.line(pts, st.accent, width, alpha)


def tick_row(p, x0, x1, y, st, count=9, height=4, width=1.2, alpha=0.35):
    if count < 2:
        return
    for i in range(count):
        x = x0 + (x1 - x0) * i / (count - 1.0)
        long_tick = (i % 4 == 0)
        h = height * (1.6 if long_tick else 1.0)
        p.line([(x, y), (x, y - h)], st.accent, width,
               alpha * (1.0 if long_tick else 0.7))


def caption(p, cx, y, value, st, size=11, alpha=0.75):
    p.text(cx, y, value.upper(), st.text, size, kind="label",
           alpha=alpha, anchor="mt", tracking=2.2)


# --------------------------------------------------------------------------
# Slot icons / visuals
# --------------------------------------------------------------------------
#
# Each visual gets its own surface (BASE_SIZES in overlay.py) and is drawn
# in its coordinates. `t` is the 0..1 animation progress, so that the same
# code can be used both for a static icon (t=1) and for a live animation.

def draw_grounding(p, w, h, st, t=1.0, label=None):
    """Grounding: a plumb bob hits the ground and a wave runs over the floor.

    The boot emoji was replaced by a drawn plumb bob - it is exactly the
    message the slot carries ("let the weight drop"), and unlike an
    emoji it looks the same on every Windows. The wave is drawn only as
    the BOTTOM half of an ellipse; a whole ellipse would plainly look
    like a plate, not like a circle on the floor in perspective.
    """
    cx = w / 2.0
    ground_y = h * 0.68
    ease = 1 - (1 - min(1.0, t / 0.35)) ** 3

    # hanger at the top - a short bracket instead of a "T" cross
    top_y = h * 0.15
    p.line([(cx - 6, top_y), (cx - 6, top_y + 4)], st.accent, 1.3, 0.55)
    p.line([(cx + 6, top_y), (cx + 6, top_y + 4)], st.accent, 1.3, 0.55)
    p.line([(cx - 7, top_y), (cx + 7, top_y)], st.accent, 1.5, 0.7)

    # cord + weight
    r = h * 0.075
    bob_y = top_y + (ground_y - h * 0.115 - top_y) * ease
    p.line([(cx, top_y + 2), (cx, bob_y - r * 1.1)], st.accent, 1.2, 0.45)
    p.polygon([(cx, bob_y - r * 1.25), (cx + r * 0.70, bob_y - r * 0.15),
               (cx, bob_y + r * 1.40), (cx - r * 0.70, bob_y - r * 0.15)],
              color=st.accent, alpha=0.20, outline=st.hot,
              outline_alpha=0.95, width=1.8)
    p.line([(cx - r * 0.22, bob_y - r * 0.15), (cx + r * 0.22, bob_y - r * 0.15)],
           st.hot, 1.1, 0.55)

    # ground - widest element of the image, so the wave stays "inside" it
    gx0, gx1 = w * 0.07, w * 0.93
    p.line([(gx0, ground_y), (gx1, ground_y)], st.accent, 2.0, 0.95)
    for edge in (gx0, gx1):
        p.line([(edge, ground_y), (edge, ground_y - 6)], st.accent, 1.4, 0.6)
    tick_row(p, cx - w * 0.16, cx + w * 0.16, ground_y - 1, st, count=9, height=3.5,
             alpha=0.28)

    # impact wave - two lower arcs with a shifted phase; only the bottom
    # half of the ellipse, otherwise the whole oval would look like a
    # plate, not like a circle on the floor in perspective
    wave = (t - 0.28) / 0.72
    for delay in (0.0, 0.26):
        wt = wave - delay
        if wt <= 0 or wt > 1:
            continue
        rx = (w * 0.06) + (w * 0.27) * wt
        ry = rx * 0.26
        p.arc(cx, ground_y, rx, ry, 4, 176, st.hot,
              1.1 + 1.4 * (1 - wt), max(0.0, 0.95 * (1 - wt) ** 0.7))

    corner_brackets(p, 6, 6, w - 6, h - 6, st, length=w * 0.09, alpha=0.40)
    if label:
        caption(p, cx, h - 20, label, st)


def _tooth_row(p, cx, y, half_w, count, depth, color, alpha, down=True,
               curve=0.0, fill=None):
    """A row of teeth as rounded rectangles along a shallow arc."""
    fill = fill if fill is not None else color
    for i in range(count):
        f = (i / (count - 1.0)) * 2.0 - 1.0          # -1 .. 1
        x = cx + f * half_w
        dy = curve * (f * f)                          # arc through the centre
        tw = depth * (0.62 if abs(f) > 0.72 else 0.78)
        y0 = y + dy
        y1 = y0 + depth if down else y0 - depth
        p.rect(x - tw / 2, min(y0, y1), x + tw / 2, max(y0, y1),
               color=fill, alpha=alpha * 0.22, outline=color,
               outline_alpha=alpha, width=1.4, radius=tw * 0.32)


def draw_jaw(p, w, h, st, t=1.0, label=None):
    """Jaw: two tooth arcs and the gap between, dimensioned like a blueprint.

    Earlier attempts (a head with eyes, a side profile of the mandible)
    read as a smiley in the periphery - hence no head shape at all. Only
    the teeth remained, and a dimension line whose length grows: the
    player sees that the JAW IS OPENING, and that is the slot's whole
    message.
    """
    cx, cy = w / 2.0, h * 0.45
    r = min(w, h) * 0.30
    hex_frame(p, cx, cy, r * 1.78, st, width=1.3, alpha=0.28)

    ease = 1 - (1 - min(1.0, t / 0.6)) ** 3
    gap = r * (0.18 + 0.52 * ease)
    half_w = r * 0.95
    depth = r * 0.24

    # upper arc - static
    upper_y = cy - gap / 2.0
    p.line([(cx - half_w - 4, upper_y - r * 0.10), (cx + half_w + 4, upper_y - r * 0.10)],
           st.accent, 1.6, 0.75)
    _tooth_row(p, cx, upper_y, half_w, 6, depth, st.accent, 0.92, down=True,
               curve=-r * 0.22)

    # lower arc - drops
    lower_y = cy + gap / 2.0
    _tooth_row(p, cx, lower_y, half_w, 6, depth, st.hot, 0.95, down=False,
               curve=r * 0.22, fill=st.accent)
    p.line([(cx - half_w - 4, lower_y + r * 0.10), (cx + half_w + 4, lower_y + r * 0.10)],
           st.hot, 1.6, 0.8)

    # dimension line of the gap (technical drawing) - left of the teeth
    dx = cx - half_w - r * 0.42
    if gap > r * 0.26:
        p.line([(dx, upper_y + depth * 0.2), (dx, lower_y - depth * 0.2)],
               st.accent, 1.3, 0.7)
        for yy, sgn in ((upper_y + depth * 0.2, 1), (lower_y - depth * 0.2, -1)):
            p.line([(dx - 2.6, yy + sgn * 4.0), (dx, yy), (dx + 2.6, yy + sgn * 4.0)],
                   st.accent, 1.2, 0.7)
        p.line([(dx - 4, upper_y + depth * 0.2), (cx - half_w, upper_y + depth * 0.2)],
               st.accent, 1.0, 0.25)
        p.line([(dx - 4, lower_y - depth * 0.2), (cx - half_w, lower_y - depth * 0.2)],
               st.accent, 1.0, 0.25)

    corner_brackets(p, 5, 5, w - 5, h - 5, st, length=w * 0.14, alpha=0.40)
    if label:
        caption(p, cx, h - 18, label, st)


def draw_release(p, w, h, st, t=1.0, label=None):
    """Releasing the mouse grip: a mouse outline and the pressure leaving it.

    The dots are pressure points under the fingers - they fly off at an
    angle (not straight up), so they do not cross the mouse wheel, and
    fade out on the way.
    """
    cx, cy = w / 2.0, h * 0.47
    mw, mh = w * 0.30, h * 0.50

    p.rect(cx - mw / 2, cy - mh / 2, cx + mw / 2, cy + mh / 2,
           color=st.accent, alpha=0.10, outline=st.accent,
           outline_alpha=0.85, width=1.8, radius=mw * 0.48)
    p.line([(cx - mw / 2 + 1.5, cy - mh * 0.10), (cx + mw / 2 - 1.5, cy - mh * 0.10)],
           st.accent, 1.3, 0.55)
    p.line([(cx, cy - mh / 2 + 4), (cx, cy - mh * 0.10)], st.accent, 1.3, 0.55)
    p.rect(cx - 1.7, cy - mh * 0.35, cx + 1.7, cy - mh * 0.22,
           color=st.hot, alpha=0.9, radius=1.7)

    # grip arc above the buttons - it vanishes first, that is the "letting go"
    grip = max(0.0, 1.0 - min(1.0, t / 0.5))
    if grip > 0.03:
        p.arc(cx, cy - mh * 0.34, mw * 0.78, mh * 0.34, 196, 344,
              st.danger, 1.5, 0.55 * grip)

    travel = 0.20 + 0.80 * min(1.0, t / 0.75)
    fade = max(0.0, 1.0 - min(1.0, t / 0.85))
    for dx, dy in ((-1.25, -0.45), (1.25, -0.45), (-0.35, -1.55)):
        px = cx + dx * mw * 1.00 * travel
        py = cy + dy * mh * 0.62 * travel
        rad = (h * 0.028) * (0.45 + 0.55 * fade)
        if fade > 0.02:
            p.ellipse(px, py, rad, rad, color=st.danger, alpha=0.9 * fade)
            p.ellipse(px, py, rad * 2.6, rad * 2.6, outline=st.danger,
                      outline_alpha=0.28 * fade, width=1.1)

    corner_brackets(p, 5, 5, w - 5, h - 5, st, length=w * 0.13, alpha=0.40)
    if label:
        caption(p, cx, h - 16, label, st)


def draw_breath_ring(p, w, h, st, phase=0.0, inhale=True, cycle_text=None):
    """Breath ring: a ring with tick marks, a breath ball and a progress arc.

    `phase` is 0..1 within a half-cycle, `inhale` sets the direction. The
    arc is the only element that says HOW MUCH is still left - the change
    of radius alone does not say it, and the player needs to know whether
    it is worth starting to breathe along with it.
    """
    cx, cy = w / 2.0, h / 2.0
    outer = min(w, h) * 0.45
    r_min, r_max = outer * 0.30, outer * 0.76
    t = phase if inhale else (1.0 - phase)
    eased = 0.5 - 0.5 * math.cos(math.pi * t)   # breathing is not linear
    r = r_min + (r_max - r_min) * eased

    p.ellipse(cx, cy, outer, outer, outline=st.accent, outline_alpha=0.20, width=1.1)
    p.ellipse(cx, cy, outer * 0.86, outer * 0.86, outline=st.accent,
              outline_alpha=0.10, width=1.0)
    for i in range(24):
        a = math.radians(i * 15.0)
        major = (i % 6 == 0)
        r0 = outer * (0.90 if major else 0.935)
        p.line([(cx + r0 * math.cos(a), cy + r0 * math.sin(a)),
                (cx + outer * 0.985 * math.cos(a), cy + outer * 0.985 * math.sin(a))],
               st.accent, 1.2 if major else 1.0, 0.60 if major else 0.28)

    p.ellipse(cx, cy, r, r, color=st.accent, alpha=0.07)
    p.ellipse(cx, cy, r, r, outline=st.hot, outline_alpha=0.95, width=2.1)
    p.ellipse(cx, cy, r * 0.80, r * 0.80, outline=st.accent,
              outline_alpha=0.30, width=1.0)

    # The arc winds up on INHALE (0 -> 360) and unwinds back on EXHALE
    # (360 -> 0), so it moves in sympathy with the ball: both grow and
    # both shrink.
    #
    # NOTE: before, it was `sweep = 360 * phase` for both phases, i.e. the
    # arc filled up TWICE per breath and at the turn jumped from full to
    # empty. Worse: `N 1.00` and `V 0.00` have the same ball radius
    # (both `eased = 1.0`), so they differed only by the text in the
    # centre - and the in-game overlay is read PERIPHERALLY, where you
    # cannot read text. So exactly at the moment of the turn there was
    # nothing to tell you whether you should be breathing out yet. The
    # direction of the arc's motion tells you even out of the corner of
    # your eye.
    sweep = 360.0 * (phase if inhale else (1.0 - phase))
    p.arc(cx, cy, outer * 0.985, outer * 0.985, -90, -90 + max(1.0, sweep),
          st.hot, 2.3, 0.9)
    a = math.radians(-90 + sweep)
    px, py = cx + outer * 0.985 * math.cos(a), cy + outer * 0.985 * math.sin(a)
    p.ellipse(px, py, 3.4, 3.4, color=(255, 255, 255), alpha=0.95)

    if cycle_text:
        caption(p, cx, cy - 7, cycle_text, st, size=11, alpha=0.9)


VISUAL_DRAW = {
    "grounding": draw_grounding,
    "jaw": draw_jaw,
    "release": draw_release,
}


def render_visual(name, width, height, style, t=1.0, label=None, ss=SS):
    """One static/animated frame of a slot visual as an RGBA image."""
    p = Painter(width, height, ss=ss)
    fn = VISUAL_DRAW.get(name)
    if fn is None:
        return p.finish()
    fn(p, width, height, style, t=t, label=label)
    return p.finish(glow=2.4, gain=0.8)


def render_breath(width, height, style, phase=0.0, inhale=True, cycle_text=None,
                  ss=2):
    """Breath ring frame. ss=2 on purpose - it is drawn 30x per second."""
    p = Painter(width, height, ss=ss)
    draw_breath_ring(p, width, height, style, phase=phase, inhale=inhale,
                     cycle_text=cycle_text)
    return p.finish(glow=2.6, gain=0.75)


# --------------------------------------------------------------------------
# HUD panel (heart rate / load / session)
# --------------------------------------------------------------------------

HUD_WIDTH = 252.0     # logical 1080p pixels
HUD_HEIGHT = 106.0
SESSION_MIN = 7.0     # smallest font size of the session line (`render_hud`)


def _heart_path(cx, cy, size):
    """Heart as a polygon - the ❤️ emoji renders differently on every
    Windows (and in some themes it is brown); a custom shape is
    consistent."""
    pts = []
    for i in range(41):
        a = math.pi * 2 * i / 40.0
        x = 16 * math.sin(a) ** 3
        y = -(13 * math.cos(a) - 5 * math.cos(2 * a)
              - 2 * math.cos(3 * a) - math.cos(4 * a))
        pts.append((cx + x * size / 16.0, cy + y * size / 16.0))
    return pts


def _zone(stress):
    """FALLBACK only for static previews (empty Today, HUD settings,
    dialogs) that have no `HeartStats` and make up their zone from an
    invented load number.

    The live HUD does NOT COMPUTE the zone - it gets it ready-made as
    `zone=` from `HeartStats.zone` (heart rate relative to rest). If you
    computed it here from the load, the word on the HUD would drift
    apart from Today and from the heart-rate indicator."""
    if stress >= 75:
        return "critical"
    if stress >= 50:
        return "high"
    if stress >= 25:
        return "raised"
    return "calm"


def zone_color(style, zone):
    """Zone colour for the HUD and the heart-rate indicator.

    It takes it from the same series as the app (`theme.ZONE_TOKENS`) -
    before, there was a separate success/accent pair here, so after each
    theme got its own series, the HUD shone green even where the app
    window was already drawing blue. The same colour must mean the same
    thing in the game and in the window.
    """
    return style.zones.get(zone, style.zones["raised"])


def render_hud(style, bpm=None, stress=0.0, history=(), threshold=None,
               baseline=None, labels=None, pulse=0.0, session=None,
               connected=True, calibrating=False, zone=None, ss=SS):
    """HUD panel: big BPM, heart-rate curve for the last ~2 min, load bar
    and session line.

    `history` is a sequence of BPM values (old -> new), `pulse` is the
    0..1 phase of the heartbeat (the heart swells exactly in the rhythm
    currently coming from the watch - so peripheral perception gets the
    information even without reading the number).

    `zone` is the zone from `HeartStats.zone` - the word, the panel
    colour and the colour of the filled bar segments. The live HUD always
    sends it; without it (static previews) the fallback `_zone(stress)`
    is used. The bar length is still the load (`stress`); the word and
    the colour are heart rate relative to rest.

    `calibrating` (`HeartStats.is_calibrating`): heart rate and the curve
    are shown, the load is not. The bar stays empty, instead of the zone
    there is a muted "calibrating…" and the panel has no zone colour but
    a neutral one - neither `stress` nor `zone` is read at all then, so
    they cannot get into the image even by mistake.
    """
    labels = labels or {}
    w, h = HUD_WIDTH, HUD_HEIGHT
    p = Painter(w, h, ss=ss)

    calibrating = bool(calibrating and connected)
    if calibrating:
        stress = 0.0
        zone = None
    if not connected:
        zone = "calm"
    elif zone is None:
        zone = _zone(stress)
    accent = (zone_color(style, zone) if connected and not calibrating
              else style.dim)
    st = style.tinted(accent)

    # backdrop - dark, so the number reads over snow and night alike
    p.panel(0, 0, w, h, st.backdrop, 0.62, radius=8)
    p.rect(0.8, 0.8, w - 0.8, h - 0.8, outline=accent, outline_alpha=0.30,
           width=1.0, radius=8)
    p.rect(0, 0, 2.6, h, color=accent, alpha=0.55, radius=1.4)
    corner_brackets(p, 4, 4, w - 4, h - 4, st, length=11, width=1.3, alpha=0.55,
                    chamfer=3)

    # --- heart + BPM ---
    beat = 1.0 + 0.16 * max(0.0, math.sin(math.pi * min(1.0, pulse * 2.2)))
    hx, hy = 23.0, 32.0
    if connected:
        p.polygon(_heart_path(hx, hy, 15 * beat), color=accent, alpha=0.85)
        p.polygon(_heart_path(hx, hy, 15 * beat), outline=_mix(accent, (255, 255, 255), 0.6),
                  outline_alpha=0.9, width=1.2)
    else:
        p.polygon(_heart_path(hx, hy, 14), outline=style.dim, outline_alpha=0.55,
                  width=1.4)

    value = str(int(bpm)) if (bpm and connected) else "--"
    p.text(42, 32, value, st.text if connected else style.dim, 32,
           kind="display", anchor="lm")
    num_w = p.measure(value, 32, kind="display")
    p.text(45 + num_w, 39, "BPM", style.dim, 10, kind="label",
           anchor="lm", alpha=0.8, tracking=1.4)

    # --- heart-rate curve ---
    # The curve starts only after the number - a three-digit heart rate
    # (100+ BPM) is exactly the case when the player needs the HUD most,
    # and that is exactly when the "BPM" label would overlap the graph.
    gx0 = max(120.0, 48 + num_w + 30)
    gx1 = w - 13.0
    gy0, gy1 = 13.0, 53.0
    values = [v for v in history if v]
    if len(values) >= 2:
        lo, hi = min(values), max(values)
        if threshold:
            lo, hi = min(lo, threshold - 4), max(hi, threshold + 4)
        if hi - lo < 12:
            mid = (hi + lo) / 2.0
            lo, hi = mid - 6, mid + 6
        span = float(hi - lo)
        step = (gx1 - gx0) / float(len(values) - 1)
        pts = [(gx0 + i * step, gy1 - (v - lo) / span * (gy1 - gy0))
               for i, v in enumerate(values)]
        # fill under the curve
        p.polygon(pts + [(gx1, gy1), (gx0, gy1)], color=accent, alpha=0.13)
        if threshold and lo <= threshold <= hi:
            # CRITICAL LIMIT: band, line and number.
            #
            # Until now it was a nameless dashed line - the player saw that
            # the curve crossed something, but not WHAT. Since the app
            # computes the limit itself from their sessions
            # (`hr_stats.dynamicky_kriticky`), it is also a number that
            # changes over time, so it is worth showing.
            #
            # The band above the line is deliberately almost invisible
            # (alpha 0.10). The HUD is meant to be peripheral: when the
            # player is below the limit it must not draw their eye, and when
            # they cross it, it is enough that the curve enters a slightly
            # darker band.
            ty = gy1 - (threshold - lo) / span * (gy1 - gy0)
            if ty > gy0 + 1:
                p.rect(gx0, gy0, gx1, ty, color=style.danger, alpha=0.10)
            # The number sits ON the line at the right and the dashes stop
            # before it. If they ran all the way to the edge, the digits
            # would lie on the dashes, and in an eight-point font that blurs
            # into a blot.
            popis = "%d" % int(round(threshold))
            pw = p.measure(popis, 8, kind="label") + 4.0
            for x in range(int(gx0), int(gx1 - pw), 6):
                p.line([(x, ty), (x + 3, ty)], style.danger, 1.0, 0.55)
            p.text(gx1, ty, popis, style.danger_text, 8, kind="label",
                   anchor="rm", alpha=0.8, tracking=0.4)
        p.line(pts, _mix(accent, (255, 255, 255), 0.35), 1.6, 0.95)
        p.ellipse(pts[-1][0], pts[-1][1], 2.4, 2.4, color=(255, 255, 255), alpha=0.95)
        if baseline and lo <= baseline <= hi:
            by = gy1 - (baseline - lo) / span * (gy1 - gy0)
            p.line([(gx0, by), (gx1, by)], style.dim, 1.0, 0.30)
    else:
        p.line([(gx0, gy1 - 2), (gx1, gy1 - 2)], style.dim, 1.0, 0.25)
        p.text((gx0 + gx1) / 2, (gy0 + gy1) / 2,
               labels.get("waiting", "---"), style.dim, 9,
               anchor="mm", alpha=0.7, tracking=1.6)

    # --- load bar ---
    bar_x0, bar_x1 = 14.0, w - 14.0
    bar_y = h - 30.0
    p.text(bar_x0, bar_y - 9, labels.get("load", "LOAD"), style.dim, 9,
           anchor="lb", alpha=0.85, tracking=1.8)
    # without data "Calm" must not be shown - that would claim something
    # the app does not know; a dash is the only honest state. Same during
    # calibration: heart rate is already coming in, but the baseline is
    # not yet, so the zone has nothing to be measured against.
    if calibrating:
        # "…" is one character and letter-spacing does not stretch it -
        # in 9-point Bahnschrift the three dots merge into a dash
        # ("KALIBRUJEM_").
        text = labels.get("calibrating", "…").upper().replace("…", "...")
        p.text(bar_x1, bar_y - 9, text, style.dim, 9,
               anchor="rb", alpha=0.8, tracking=1.8)
    else:
        zone_text = labels.get(zone, zone).upper() if connected else "—"
        p.text(bar_x1, bar_y - 9, zone_text, accent, 9,
               anchor="rb", alpha=0.95, tracking=1.8)

    segments = 20
    seg_w = (bar_x1 - bar_x0) / segments
    filled = int(round(segments * max(0.0, min(100.0, stress)) / 100.0))
    # The filled segments have the colour of the CURRENT zone, not each
    # its own by where it lies in the bar. Before, there were quarters of
    # the bar here and 35/60/80 % on Today - a third and fourth
    # definition of the same words. At a load of 57 the HUD thus ended
    # up "High", Today "Raised", and the word above the bar could say
    # something else again.
    for i in range(segments):
        x0 = bar_x0 + i * seg_w
        x1 = x0 + seg_w * 0.72
        if i < filled and connected:
            p.rect(x0, bar_y, x1, bar_y + 6, color=accent, alpha=0.92, radius=1.2)
        else:
            p.rect(x0, bar_y, x1, bar_y + 6, color=style.dim, alpha=0.18, radius=1.2)

    # --- session line ---
    if session:
        # The line must fit into the bar width (0.3, skeptic UX 4b): from
        # one hour on, the time over the limit is "1 h 15 min"
        # (`ui_kit.cas_text`) and with a longer word ("ÜBER DER GRENZE",
        # "AU-DESSUS DU SEUIL", "1 ч 15 мин") it ran past the right edge of
        # the panel. Letter-spacing is reduced first, only then the font
        # size (at most down to SESSION_MIN) - the text is not cut off.
        velkost, prestrk = 8.5, 0.5
        sirka = bar_x1 - bar_x0
        if p.measure(session, velkost, tracking=prestrk) > sirka:
            prestrk = 0.0
        while velkost > SESSION_MIN and p.measure(session, velkost) > sirka:
            velkost = max(SESSION_MIN, velkost - 0.25)
        p.text(bar_x0, h - 7, session, style.dim, velkost, anchor="lb", alpha=0.72,
               tracking=prestrk)

    return p.finish(glow=1.8, gain=0.55)


# Feature icons under the HUD panel - the app only assembles the final
# image from ready-made parts (HUD panel from render_hud, icon row
# here), it does not redraw the HUD from scratch - that would also
# change its own layout.
TRIGGER_ROW_HEIGHT = 44.0


def render_hud_trigger_row(width, style, triggers, icon_color=None):
    """A row with 4 (or fewer) trigger icons under the HUD panel.

    `triggers` is a list of (visual_name, enabled) - `enabled=False` is
    drawn dimmed (the player sees that the slot exists but is off).
    `icon_color` is an optional colour for ALL icons in the row (other
    than each visual's own in-game colour - here it should be one
    unified look of a small feature bar, not 4 different colours side
    by side).
    """
    w, h = float(width), TRIGGER_ROW_HEIGHT
    p = Painter(w, h, ss=SS)
    st = style.tinted(icon_color) if icon_color else style
    p.panel(0, 0, w, h, st.backdrop, 0.55, radius=8)

    n = max(1, len(triggers))
    slot_w = w / n
    icon_size = min(26.0, slot_w - 14.0)
    for i, (visual_name, enabled) in enumerate(triggers):
        cx = slot_w * i + slot_w / 2.0
        icon = render_slot_icon(visual_name, int(icon_size * SS), st, ss=1)
        icon = icon.resize((int(icon_size), int(icon_size)))
        if not enabled:
            alpha = icon.getchannel("A").point(lambda v: int(v * 0.35))
            icon.putalpha(alpha)
        p.paste(icon, int(cx - icon_size / 2.0), int(h / 2.0 - icon_size / 2.0 - 4))
        # NOTE: a label with the key (C, R, F...) used to be drawn here.
        # Since phase 3 the keys trigger nothing, so it was instructions
        # that no longer held - and the row is meant to be peripheral, not
        # read.
    return p.finish(glow=1.2, gain=0.4)


def render_hud_combined(hud_image, trigger_row_image=None):
    """Stacks the HUD panel and the optional icon row into one image (same
    width, taller - the app then draws it as one layered window instead
    of two, which is simpler for both positioning and clickability)."""
    if trigger_row_image is None:
        return hud_image
    w = hud_image.width
    gap = 4
    out = Image.new("RGBA", (w, hud_image.height + gap + trigger_row_image.height),
                    (0, 0, 0, 0))
    out.paste(hud_image, (0, 0), hud_image)
    out.paste(trigger_row_image, (0, hud_image.height + gap), trigger_row_image)
    return out


# --------------------------------------------------------------------------
# Icons for the app's interface (a replacement for emoji in the slot list)
# --------------------------------------------------------------------------

def render_slot_icon(name, size, style, ss=SS):
    """Small square icon for the list/dialog/Guide - the same graphics as
    the in-game visual, just without animation and without a label.

    Most names are slot visuals (grounding/jaw/release/breath), but
    `heart` and `periphery` have no in-game visual - they are here so
    that every picture in the app is drawn with the same brush and the
    same palette.
    """
    p = Painter(size, size, ss=ss)
    st = style
    if name == "grounding":
        cx, gy = size / 2.0, size * 0.72
        p.line([(cx, size * 0.18), (cx, size * 0.50)], st.accent, size * 0.035, 0.6)
        r = size * 0.13
        p.polygon([(cx, size * 0.44), (cx + r, size * 0.58),
                   (cx, size * 0.72), (cx - r, size * 0.58)],
                  color=st.accent, alpha=0.25, outline=st.hot,
                  outline_alpha=1.0, width=size * 0.045)
        p.line([(size * 0.18, gy + size * 0.06), (size * 0.82, gy + size * 0.06)],
               st.accent, size * 0.05, 0.9)
    elif name == "jaw":
        cx, cy, r = size / 2.0, size * 0.44, size * 0.28
        p.arc(cx, cy, r, r, 170, 10, st.accent, size * 0.05, 0.9)
        p.arc(cx, cy + r * 0.65, r * 0.85, r * 0.6, 5, 175, st.hot, size * 0.055, 0.95)
        p.ellipse(cx + r * 0.9, cy + r * 0.2, size * 0.045, size * 0.045,
                  color=st.hot, alpha=1.0)
    elif name == "release":
        cx, cy = size / 2.0, size * 0.52
        mw, mh = size * 0.34, size * 0.56
        p.rect(cx - mw / 2, cy - mh / 2, cx + mw / 2, cy + mh / 2,
               outline=st.accent, outline_alpha=0.9, width=size * 0.05,
               radius=mw * 0.48)
        p.line([(cx, cy - mh / 2 + size * 0.04), (cx, cy - mh * 0.08)],
               st.accent, size * 0.04, 0.7)
        for dx, dy in ((-1, -0.2), (1, -0.2)):
            p.ellipse(cx + dx * mw * 0.95, cy + dy * mh * 0.5,
                      size * 0.045, size * 0.045, color=st.danger, alpha=0.9)
    elif name == "breath":
        cx, cy = size / 2.0, size / 2.0
        p.ellipse(cx, cy, size * 0.40, size * 0.40, outline=st.accent,
                  outline_alpha=0.30, width=size * 0.035)
        p.ellipse(cx, cy, size * 0.26, size * 0.26, color=st.accent, alpha=0.18)
        p.ellipse(cx, cy, size * 0.26, size * 0.26, outline=st.hot,
                  outline_alpha=0.95, width=size * 0.05)
    elif name == "periphery":
        # SOFT GAZE (the "Release & periphery" card in the Guide).
        #
        # It is not a slot visual - it is not drawn into the game. It is
        # here because the Guide had a thin sketch on a Canvas on this
        # card, and next to the brush pictograms it looked like a picture
        # from another app.
        #
        # Three things and nothing more, the same discipline as the rest
        # of the set:
        #   * the eye as TWO strokes (upper and lower eyelid), not a
        #     closed ellipse - a closed outline looked like a wheel, not
        #     an eye;
        #   * the iris drawn the same way as "breath" (soft fill + a
        #     ring in `hot`), so both cards belong together;
        #   * the peripheral field = two wide muted arcs at the sides.
        #     They are DELIBERATELY pale: what you are meant to notice is
        #     the centre, and the edge should be perceptible even when
        #     you do not look at it directly - exactly what that card is
        #     about.
        cx, cy = size / 2.0, size * 0.50
        ex, ey = size * 0.30, size * 0.20
        p.arc(cx, cy, ex, ey, 185, 355, st.accent, size * 0.045, 0.90)
        p.arc(cx, cy, ex, ey, 5, 175, st.accent, size * 0.045, 0.90)
        r_iris = size * 0.105
        p.ellipse(cx, cy, r_iris, r_iris, color=st.accent, alpha=0.20)
        p.ellipse(cx, cy, r_iris, r_iris, outline=st.hot,
                  outline_alpha=0.95, width=size * 0.042)
        for start, end in ((118, 242), (-62, 62)):
            p.arc(cx, cy, size * 0.45, size * 0.40, start, end, st.accent,
                  size * 0.030, 0.30)
    elif name == "qr":
        # A QR MARK, not a QR code.
        #
        # A real QR is a white square - in a dark panel it hits you in the
        # eye and pulls attention to something most people do not even
        # need (anyone who already has the app on their phone does not
        # want the QR). That is why outwardly there is only this mark in
        # the theme accent, and the white code appears only on click.
        #
        # Three corner eyes + a few modules - just enough for the eye to
        # read it as "QR", and nothing more; the module fill is
        # deliberately sparser than the eyes.
        m, f = size * 0.13, size * 0.26
        for x, y in ((m, m), (size - m - f, m), (m, size - m - f)):
            p.rect(x, y, x + f, y + f, outline=st.accent, outline_alpha=0.95,
                   width=size * 0.055, radius=size * 0.03)
            vn = f * 0.30
            p.rect(x + (f - vn) / 2, y + (f - vn) / 2, x + (f + vn) / 2,
                   y + (f + vn) / 2, color=st.accent, alpha=0.95)
        modul = size * 0.085
        for mx, my in ((0.58, 0.52), (0.72, 0.52), (0.58, 0.66), (0.86, 0.66),
                       (0.72, 0.80), (0.86, 0.52), (0.44, 0.80), (0.86, 0.86)):
            p.rect(size * mx, size * my, size * mx + modul, size * my + modul,
                   color=st.accent, alpha=0.55)
    elif name == "table":
        # TABLE (session export). Not the Excel logo - that is someone
        # else's brand and would stick out in this set like a sticker. The
        # header is filled, the rows are just lines: that is how a table
        # looks at first glance, even when it is small.
        m = size * 0.14
        w = size - 2 * m
        hlavicka = size * 0.17
        p.rect(m, m, m + w, m + hlavicka, color=st.accent, alpha=0.85,
               radius=size * 0.03)
        p.rect(m, m, m + w, size - m, outline=st.accent, outline_alpha=0.9,
               width=size * 0.045, radius=size * 0.03)
        # two vertical dividing columns
        for podiel in (0.36, 0.68):
            p.line([(m + w * podiel, m + hlavicka), (m + w * podiel, size - m)],
                   st.accent, size * 0.035, 0.55)
        # horizontal rows; the last one is `hot` - the one that was just added
        riadkov = 3
        for i in range(1, riadkov + 1):
            y = m + hlavicka + (size - m - m - hlavicka) * i / (riadkov + 1.0)
            posledny = i == riadkov
            p.line([(m, y), (m + w, y)], st.hot if posledny else st.accent,
                   size * 0.035, 0.95 if posledny else 0.5)
    elif name == "heart":
        p.polygon(_heart_path(size / 2.0, size * 0.52, size * 0.38),
                  color=st.accent, alpha=0.85)
    return p.finish(glow=1.6, gain=0.7)


# --------------------------------------------------------------------------
# Enso (円相) - main start/stop listening button, in the middle of the sidebar
# --------------------------------------------------------------------------

# The mark's breathing cycle: shares of the whole (1.0 in total).
# A 10 s cycle = 6 breaths/min. A calming pace is 4.5-6.5 breaths/min -
# around it the heart, lungs and pressure waves synchronise. The enso
# used to breathe 4.3 s (~14 breaths/min), which is the pace of a calm
# to slightly agitated person, not a calming one.
#
# Asymmetric and with a pause ON PURPOSE: an equal inhale and exhale
# without a stop is a metronome, not a breath. A longer exhale is also
# the parasympathetic direction (vagus nerve), and a real breath pauses
# for a moment at the turn - a pure sine never stops, and that is
# exactly what feels mechanical.
ENSO_INHALE = 0.42        # 4.2 s
ENSO_HOLD = 0.06          # 0.6 s pause at the top
ENSO_EXHALE = 0.52        # 5.2 s
ENSO_CYCLE_MS = 10000


def enso_breath(phase):
    """Breath value 0..1 for a phase 0..1 (0 = breathed out, 1 = inhaled).

    Each phase has its own smooth ease-in (`0.5 - 0.5*cos`), so the curve
    has no kink anywhere - it only pauses for a moment at the top.
    """
    t = phase % 1.0
    if t < ENSO_INHALE:
        u = t / ENSO_INHALE
        return 0.5 - 0.5 * math.cos(math.pi * u)
    if t < ENSO_INHALE + ENSO_HOLD:
        return 1.0
    u = (t - ENSO_INHALE - ENSO_HOLD) / ENSO_EXHALE
    return 0.5 + 0.5 * math.cos(math.pi * min(1.0, u))


def _draw_watch(p, cx, cy, size, color, alpha=1.0):
    """A wristwatch drawn with SHAPES, not an emoji.

    Same reason as for `_heart_path`: the ⌚ character renders differently
    on every Windows and is often missing entirely from the UI font -
    then all that is left of it is an empty square. A custom shape looks
    the same everywhere.

    Dial + two straps: the little circle alone would get lost in the
    ring; it is the straps that make it recognisable even at 24 px.
    """
    r = size * 0.46
    sirka = r * 0.78
    # straps at the top and bottom (slightly narrowing outwards)
    for smer in (-1, 1):
        y0 = cy + smer * r * 0.82
        y1 = cy + smer * r * 1.62
        p.polygon([(cx - sirka, y0), (cx + sirka, y0),
                   (cx + sirka * 0.66, y1), (cx - sirka * 0.66, y1)],
                  color=color, alpha=alpha * 0.75)
    # dial
    p.ellipse(cx, cy, r, r, outline=color, outline_alpha=alpha,
              width=max(1.0, size * 0.13))
    # hands - small, just so it is not an empty circle
    p.line([(cx, cy), (cx, cy - r * 0.52)], color, size * 0.10, alpha * 0.95)
    p.line([(cx, cy), (cx + r * 0.40, cy)], color, size * 0.10, alpha * 0.8)


def heartbeat_envelope(phase):
    """0..1 envelope of ONE heartbeat: a sharp rise, a slower fall.

    The heart does not beat as a sine - it contracts fast and relaxes for
    longer. The eyes would read a pure sine as breathing, and the enso
    next to it already breathes; this shape tells them apart even without
    colour.
    """
    t = phase % 1.0
    nabeh = 0.16
    if t < nabeh:
        return t / nabeh
    u = (t - nabeh) / (1.0 - nabeh)
    return max(0.0, (1.0 - u) ** 2.2)


def render_pulse_ring(size, style, phase=0.0, zone=None, connected=False,
                      waiting=False, ss=SS):
    """Ring with a watch in the middle - live heart-rate sensor indicator.

    Three states:
      * NOT PAIRED (`connected=False`) - the ring is dimmed and still,
        the watch grey. There is nothing to reflect.
      * PAIRED, WAITING (`waiting=True`) - the ring glows neutrally and
        breathes slowly: "connected, heart rate has not arrived yet".
      * PAIRED + HEART RATE - the ring beats in the REAL rhythm of the
        watch (`phase` from `HeartStats.beat_phase()`) and takes its
        colour from `zone`.

    WHY COLOUR BY ZONE AND NOT GREEN/RED: the app already has zones
    (`HeartStats.zone`/`zone_color`) and draws the in-game HUD with them
    - so the same colour means the same thing in the side panel and over
    the game, one source of truth. Besides, ~12 % of men cannot tell red
    from green, so colour must not be the only carrier: the main
    information here is carried by the SPEED of the ring's beating, which
    is readable regardless of colour perception.
    """
    size = int(size)
    p = Painter(size, size, ss=ss)
    cx, cy = size / 2.0, size / 2.0
    outer = size * 0.40

    if not connected:
        barva = style.dim
        p.ellipse(cx, cy, outer, outer, outline=barva, outline_alpha=0.35,
                  width=size * 0.045)
        tep = 0.0
    elif waiting:
        barva = style.accent
        dych = 0.5 - 0.5 * math.cos(2.0 * math.pi * (phase % 1.0))
        p.ellipse(cx, cy, outer, outer, outline=barva,
                  outline_alpha=0.30 + 0.25 * dych, width=size * 0.05)
        tep = 0.0
    else:
        # "neutral" = calibration (HeartStats.is_calibrating): the same muted
        # colour as the HUD in that state, no zone.
        barva = (style.dim if zone == "neutral"
                 else zone_color(style, zone or "calm"))
        tep = heartbeat_envelope(phase)
        # a calm ring + a second one that widens and fades with each beat -
        # a "wave" outwards, like pressure spreading through a blood vessel
        p.ellipse(cx, cy, outer, outer, outline=barva, outline_alpha=0.42,
                  width=size * 0.05)
        r_vlna = outer * (1.0 + 0.16 * tep)
        p.ellipse(cx, cy, r_vlna, r_vlna, outline=barva,
                  outline_alpha=0.62 * (1.0 - tep * 0.45),
                  width=size * 0.038 * (1.0 + 0.5 * tep))

    _draw_watch(p, cx, cy, size * 0.30,
                barva if connected else style.dim,
                0.95 if connected else 0.55)
    return p.finish(glow=1.6 + 0.8 * tep, gain=0.35 + 0.25 * tep)


def render_enso(size, style, live=False, phase=0.0, ss=SS, color=None,
                armed=False, sheen=False, close=0.0, halo=0.0):
    """Brush circle + the 残 character - app mark and listening switch in one.

    `color` overrides the state colour. It is for places where the mark
    is NOT a switch but just a logo (Guide) - there green/red would claim
    a state that the picture does not track, and a red enso in a manual
    would read as an error. With the theme accent it fits among the other
    pictograms, which are drawn the same way (`render_slot_icon`).

    COLOUR carries the state and follows the usual recording convention:
      * GREEN (`success`)  = the app is listening, the triggers are live
      * RED (`danger`)     = not listening, nothing is happening
    NOTE: it used to be the other way round (green = ready, bengara =
    running). But red on a running app read as an error, and green on a
    stopped one as "all is well" - the exact opposite of what the state
    means. Red dot = not recording, green = recording, everyone knows
    that.

    `phase` is 0..1 and turns the icon into a LIVE element - not a static
    picture. The same curve as the breath ring (`0.5 - 0.5*cos`), so the
    enso slowly "breathes": the stroke thins and thickens, the radius
    changes slightly. When the app is listening, a light arc also orbits
    the circumference - "loading", i.e. running. When it is not
    listening, it breathes only very gently and there is no arc.

    `armed` = the trigger is armed (`trigger.ARMED`): the body has stayed
    above the threshold for 90 s and the app is waiting for a pause to
    speak up. It is drawn as an INNER ring that contracts with the
    inhale. Three things about it are deliberate:

      * INWARDS, not outwards. There is already a ring outside (the
        loading one, r*1.20) and it means "running". A second ring in
        the same annulus would read as one ornament, not as two states.
        Inside there is free space between the character (~0.17*size)
        and the stroke (0.40*size).
      * THE SAME COLOUR as the mark. `theme.py` says that the enso
        colour has a single job in the whole interface - to say whether
        the app is listening. Arming is therefore NOT a third colour;
        motion carries it.
      * It CONTRACTS while the loading ring FILLS. The opposite
        direction is what tells the two rings apart even out of the
        corner of the eye.

    NOTE: the radius is computed from the NON-BREATHING base
    (`r_zaklad`), not from `r`. If it were computed from `r`, the
    breathing of the stroke itself (0.955 -> 1.045) would almost cancel
    out the contraction - a 12 % swing would come out as 1.5 % and the
    ring would stand still.
    """
    size = int(size)
    p = Painter(size, size, ss=ss)
    # COLOUR by THEME (accent) - gold in Sumi, blue in Aizome. The enso's
    # colour no longer carries the state (the breathing bar + the dot in
    # the panel do), MOTION does: at rest the enso stands still, while
    # listening it breathes and the sheen fills. `color` overrides the
    # accent (the logo in the Guide).
    base = color or style.accent
    cx, cy = size / 2.0, size / 2.0

    dych = enso_breath(phase) if live else 0.0

    r_zaklad = size * 0.40
    r = r_zaklad * (0.955 + 0.09 * dych)
    sila = (0.78 + 0.22 * dych) if live else 0.70

    # LOADING RING (behind the mark) - fills with the inhale.
    if live and dych > 0.004:
        r_load = r * 1.20
        p.arc(cx, cy, r_load, r_load, -90.0, -90.0 + 360.0 * dych,
              base, size * 0.030, 0.40)

    # The enso itself - a THIN open stroke (minimalist), tapering at the end.
    predlzenie = 24.0 * dych
    span = (188.0 + predlzenie) - (-78.0)
    p.arc(cx, cy, r, r, -78, 188 + predlzenie, base, size * 0.034, 0.95 * sila)
    p.arc(cx, cy, r, r, 150 + predlzenie, 188 + predlzenie, base,
          size * 0.046, 0.55 * sila)

    # FILLING SHEEN - light gold fills along the stroke with the inhale + a
    # gentle sweep. TIED to `live` and `sheen` (rest = no sheen), so that
    # the tests stay byte-identical with live=False.
    if live and sheen and dych > 0.004:
        p.arc(cx, cy, r, r, -78, -78 + span * dych, style.hot,
              size * 0.034, 0.14 + 0.72 * dych)
        stred = -78 + span * (phase % 1.0)
        p.arc(cx, cy, r, r, stred - 15, stred + 15, style.hot,
              size * 0.034, 0.28)

    # GRADUATION - the open ring closes into a full circle (close 0->1).
    if close > 0.0:
        koniec = (188.0 + predlzenie) + (282.0 - (188.0 + predlzenie)) * min(1.0, close)
        p.arc(cx, cy, r, r, 188 + predlzenie, koniec, base, size * 0.034, 0.95 * sila)

    # ARMED - inner ring (armed), contracts with the inhale.
    if armed and live:
        r_arm = r_zaklad * 0.72 * (1.0 - 0.12 * dych)
        p.arc(cx, cy, r_arm, r_arm, -90.0, 270.0, base,
              size * 0.018, 0.45 + 0.30 * dych)

    # MOON GLOW (halo) - after graduation the enso glows like the moon: a
    # soft light body inside the ring + a stronger bloom in finish().
    if halo > 0.0:
        hh = min(1.0, halo)
        telo = _mix(base, (255, 255, 255), 0.32)
        p.ellipse(cx, cy, r * 0.92, r * 0.92, color=telo, alpha=0.10 * hh)
        p.ellipse(cx, cy, r * 0.60, r * 0.60, color=telo, alpha=0.12 * hh)

    font = _load_font("cjk", p._s(size * 0.34))
    fill = _rgba(base, 0.95 if (live or halo > 0.0) else 0.88)
    p._d.text((p._s(cx), p._s(cy) + p._s(size) * 0.02), "残", font=font,
              fill=fill, anchor="mm")
    ziara = (1.9 + 0.7 * dych) if live else 1.3
    zisk = (0.52 + 0.18 * dych) if live else 0.32
    if halo > 0.0:
        ziara = 1.9 + 2.4 * min(1.0, halo)
        zisk = 0.52 + 0.30 * min(1.0, halo)
    return p.finish(glow=ziara, gain=zisk)


# NOTE: there was a section here "Dojo band (top background band) and
# lanterns" - `_load_dojo_band_source()`, `render_dojo_band()`,
# `_radial_blob()`, `render_lamp_glow()` and the tables
# `_LAMP_POSITIONS`/`_LAMP_COLORS`. They drew a fixed-height photo band
# above the app's title bar, including pulsing lanterns. The band was
# removed from the window (see the NOTE in `ui_shell` and
# `DandurfApp._build_ui`), so nobody was left to call these functions -
# pyflakes does not report them as unused module-level functions, so
# they were deleted by hand. With them, the image
# `assets/images/dojo_band.jpg` also went out of use.
