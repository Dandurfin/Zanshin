"""Kreslenie in-game vizualov a HUD panela - cisto PIL, bez Tk.

Preco PIL a nie tk.Canvas
-------------------------
Tk Canvas nevie antialiasing ani polopriehladnost: kazda ciara je tvrdy
pixel a "ziara" sa neda urobit vobec. Povodne vizualy preto pouzivali
emoji (🥾) a schodovite ovaly - na 4K to vyzera ako nedorobok.

Tu sa vsetko kresli do RGBA bitmapy s 3x supersamplingom a jednym
gaussovskym priechodom na ziaru. Vysledok ide bud cez UpdateLayeredWindow
(plna alfa, viz layer_window.py), alebo ako PhotoImage na Canvas.

Vizualny jazyk
--------------
Tenke linky, sikmo zrezane rohove zatvorky, delenia ako na pristroji,
jedna akcentova farba + biele jadro, ziadne vyplne okrem 8 % nadychu.
Zamerne NEkopiruje HUD ziadnej konkretnej hry - je to vlastny "dojo"
styl (hexagon + tahy stetcom), ktory sedi vedla vojenskeho aj sci-fi
rozhrania, lebo si od oboch berie len geometricku disciplinu.

Vsetky rozmery su v "1080p pixeloch" - volajuci ich nasobi
`display.Monitor.scale`, takze na 4K je vsetko 2x vacsie a zabera
rovnaku cast obrazovky.
"""

import math
import os

try:
    # POZN: `ImageEnhance` tu bolo tiez - pouzival ho len `render_dojo_band()`
    # na stlmenie jasu fotopasu. S odstranenim pasu ostalo nepouzite.
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    PIL_AVAILABLE = True
except Exception:  # pragma: no cover - appka bez pillow kresli fallbackom
    PIL_AVAILABLE = False

SS = 3  # supersampling - 3x staci na hladke hrany a je 2x rychlejsi nez 4x


# --------------------------------------------------------------------------
# Fonty
# --------------------------------------------------------------------------

# Bahnschrift je DIN-ovsky uzky technicky font, ktory je sucastou Windows 10
# aj 11 - presne ten "pristrojovy" charakter, aky HUD potrebuje. Segoe UI je
# zaloha (je vsade), DejaVu/Liberation su pre vyvoj na Linuxe.
_FONT_CANDIDATES = {
    "display": ["bahnschrift.ttf", "segoeuisb.ttf", "segoeui.ttf",
                "DejaVuSansCondensed-Bold.ttf", "LiberationSans-Bold.ttf",
                "DejaVuSans-Bold.ttf"],
    "label": ["bahnschrift.ttf", "segoeui.ttf",
              "DejaVuSansCondensed.ttf", "LiberationSans-Regular.ttf",
              "DejaVuSans.ttf"],
    # CJK (znak 残 v enso tlacidle) - najprv stetcove (mincho), potom sans
    # (gothic) - rovnaka kombinovana rada ako make_icon.py, lebo nie kazda
    # Windows instalacia ma mincho (na vyvojovom stroji chyba, msgothic aj
    # YuGoth su ale takmer vzdy pritomne).
    "cjk": ["YuMinDB.ttf", "yumindb.ttf", "YuMincho.ttc", "msmincho.ttc",
            "YuGothB.ttc", "YuGothM.ttc", "meiryob.ttc", "meiryo.ttc",
            "msgothic.ttc", "msyh.ttc", "simhei.ttf",
            "NotoSerifCJK-Bold.ttc", "NotoSansCJK-Bold.ttc"],
}

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
                # Bahnschrift je variabilny font - bez tohto by sa nacital
                # v Regular reze a cisla by boli prilis tenke.
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
# Styl
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
    """Farby a hrubky prevzate z temy appky (theme.py tokeny).

    `hot` je zosvetlene jadro akcentu - tenka svetla ciara vnutri
    farebnej dava tahom ten "svieti to" dojem bez toho, aby sa musela
    zvysovat ziara (a s nou aj rozmazanie).
    """

    def __init__(self, pal=None):
        pal = pal or {}
        self.accent = _hex(pal.get("accent", "#00d2ff"))
        self.danger = _hex(pal.get("danger", "#ff5c73"))
        self.warn = _hex(pal.get("warn", "#f5a623"))
        self.success = _hex(pal.get("success", "#3ddc84"))
        self.bengara = _hex(pal.get("bengara", "#a6432e"))
        self.text = _hex(pal.get("text", "#f5f7fa"))
        self.dim = _hex(pal.get("text_dim", "#8d97ab"))
        self.hot = _mix(self.accent, (255, 255, 255), 0.55)
        self.backdrop = (5, 9, 14)
        # PASMA TEPU maju v kazdej teme vlastny rad (theme.ZONE_TOKENS).
        # Fallbacky su povodne tokeny, aby stara paleta (alebo Style()
        # bez palety v testoch) fungovala dalej.
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
    """Kresliaca plocha so supersamplingom a ziarou.

    Tri vrstvy: `bg` (podklad panela - nesmie ziarit, inak sa rozmaze do
    okolia), `core` (tahy) a z nej odvodena ziara. Vsetky suradnice sa
    zadavaju v logickych 1080p pixeloch, prepocet na supersample robi
    trieda sama.
    """

    def __init__(self, width, height, ss=SS):
        self.w, self.h, self.ss = int(width), int(height), ss
        size = (self.w * ss, self.h * ss)
        self.bg = Image.new("RGBA", size, (0, 0, 0, 0))
        self.core = Image.new("RGBA", size, (0, 0, 0, 0))
        self._dbg = ImageDraw.Draw(self.bg)
        self._d = ImageDraw.Draw(self.core)

    # ---- pomocne prepocty ----

    def _s(self, v):
        return v * self.ss

    def _box(self, x0, y0, x1, y1):
        return [self._s(x0), self._s(y0), self._s(x1), self._s(y1)]

    def _pts(self, points):
        return [(self._s(x), self._s(y)) for x, y in points]

    # ---- podklad (bez ziary) ----

    def panel(self, x0, y0, x1, y1, color, alpha, radius=6):
        self._dbg.rounded_rectangle(self._box(x0, y0, x1, y1),
                                    radius=self._s(radius), fill=_rgba(color, alpha))

    # ---- tahy ----

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
        """Vlozi uz hotovy RGBA obrazok (v logickych pixeloch, napr. z
        render_slot_icon) na poziciu (x, y) do vrstvy `core`.

        Obrazok sa dorata na supersampling tejto plochy, aby sa pri
        finálnom zmensení (`finish()`) nerozostril inak ako zvysok
        kreslenia - inak by ikonka posobila mekcia/ostrejsia nez okolie."""
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
        """Text s volitelnym prestrkanim (`tracking`) - kapitalky s medzerami
        medzi pismenami su to, co odlisi "HUD popisok" od beznej appky."""
        font = _load_font(kind, self._s(size))
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
        font = _load_font(kind, self._s(size))
        total = self._d.textlength(value, font=font)
        if tracking:
            total += self._s(tracking) * max(0, len(value) - 1)
        return total / float(self.ss)

    # ---- vysledok ----

    def finish(self, glow=2.2, gain=0.85):
        """Zlozi vrstvy a zmensi na cielovu velkost (tu vznika antialiasing)."""
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
# Spolocne prvky
# --------------------------------------------------------------------------

def corner_brackets(p, x0, y0, x1, y1, st, length=14, width=1.6, alpha=0.85,
                    chamfer=5):
    """Styri rohove zatvorky so zrezanym rohom - lacnejsie na oko nez cely
    ram a hra spod nich ostane vidiet."""
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
# Ikony / vizualy slotov
# --------------------------------------------------------------------------
#
# Kazdy vizual dostane vlastnu plochu (BASE_SIZES v overlay.py) a kresli sa
# v jej suradniciach. `t` je 0..1 postup animacie, aby sa ten isty kod dal
# pouzit aj na staticku ikonu (t=1) aj na zivu animaciu.

def draw_grounding(p, w, h, st, t=1.0, label=None):
    """Tazisko: olovnica dopadne na zem a po podlahe sa rozbehne vlna.

    Emoji topanky nahradila kreslena olovnica - je to presne ta sprava,
    ktoru slot nesie ("pusti vahu dole"), a na rozdiel od emoji vyzera
    na kazdom Windows rovnako. Vlna sa kresli len ako SPODNA polovica
    elipsy; cela elipsa by citatelne vyzerala ako tanier, nie ako kruh
    po podlahe v perspektive.
    """
    cx = w / 2.0
    ground_y = h * 0.68
    ease = 1 - (1 - min(1.0, t / 0.35)) ** 3

    # zavesenie hore - kratka zatvorka namiesto "T" krizika
    top_y = h * 0.15
    p.line([(cx - 6, top_y), (cx - 6, top_y + 4)], st.accent, 1.3, 0.55)
    p.line([(cx + 6, top_y), (cx + 6, top_y + 4)], st.accent, 1.3, 0.55)
    p.line([(cx - 7, top_y), (cx + 7, top_y)], st.accent, 1.5, 0.7)

    # snura + zavazie
    r = h * 0.075
    bob_y = top_y + (ground_y - h * 0.115 - top_y) * ease
    p.line([(cx, top_y + 2), (cx, bob_y - r * 1.1)], st.accent, 1.2, 0.45)
    p.polygon([(cx, bob_y - r * 1.25), (cx + r * 0.70, bob_y - r * 0.15),
               (cx, bob_y + r * 1.40), (cx - r * 0.70, bob_y - r * 0.15)],
              color=st.accent, alpha=0.20, outline=st.hot,
              outline_alpha=0.95, width=1.8)
    p.line([(cx - r * 0.22, bob_y - r * 0.15), (cx + r * 0.22, bob_y - r * 0.15)],
           st.hot, 1.1, 0.55)

    # zem - najsirsi prvok obrazka, aby vlna ostala "vnutri" neho
    gx0, gx1 = w * 0.07, w * 0.93
    p.line([(gx0, ground_y), (gx1, ground_y)], st.accent, 2.0, 0.95)
    for edge in (gx0, gx1):
        p.line([(edge, ground_y), (edge, ground_y - 6)], st.accent, 1.4, 0.6)
    tick_row(p, cx - w * 0.16, cx + w * 0.16, ground_y - 1, st, count=9, height=3.5,
             alpha=0.28)

    # dopadova vlna - dva spodne oblúky s posunutou fazou; len spodna
    # polovica elipsy, inak by cely ovál vyzeral ako tanier, nie ako
    # kruh po podlahe v perspektive
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
    """Rada zubov ako zaoblene obdlzniky pozdlz plytkeho oblúka."""
    fill = fill if fill is not None else color
    for i in range(count):
        f = (i / (count - 1.0)) * 2.0 - 1.0          # -1 .. 1
        x = cx + f * half_w
        dy = curve * (f * f)                          # oblúk cez stred
        tw = depth * (0.62 if abs(f) > 0.72 else 0.78)
        y0 = y + dy
        y1 = y0 + depth if down else y0 - depth
        p.rect(x - tw / 2, min(y0, y1), x + tw / 2, max(y0, y1),
               color=fill, alpha=alpha * 0.22, outline=color,
               outline_alpha=alpha, width=1.4, radius=tw * 0.32)


def draw_jaw(p, w, h, st, t=1.0, label=None):
    """Celust: dva zubne oblúky a medzera medzi nimi, meraná ako na vykrese.

    Predosle pokusy (hlava s ocami, bocny profil sanky) sa na periferii
    citali ako smajlik - preto ziadna tvar hlavy. Ostali len zuby a
    kotovacia ciara, ktorej dlzka rastie: hrac vidi, ze sa CELUST OTVARA,
    a to je cela sprava slotu.
    """
    cx, cy = w / 2.0, h * 0.45
    r = min(w, h) * 0.30
    hex_frame(p, cx, cy, r * 1.78, st, width=1.3, alpha=0.28)

    ease = 1 - (1 - min(1.0, t / 0.6)) ** 3
    gap = r * (0.18 + 0.52 * ease)
    half_w = r * 0.95
    depth = r * 0.24

    # horny oblúk - staticky
    upper_y = cy - gap / 2.0
    p.line([(cx - half_w - 4, upper_y - r * 0.10), (cx + half_w + 4, upper_y - r * 0.10)],
           st.accent, 1.6, 0.75)
    _tooth_row(p, cx, upper_y, half_w, 6, depth, st.accent, 0.92, down=True,
               curve=-r * 0.22)

    # dolny oblúk - klesa
    lower_y = cy + gap / 2.0
    _tooth_row(p, cx, lower_y, half_w, 6, depth, st.hot, 0.95, down=False,
               curve=r * 0.22, fill=st.accent)
    p.line([(cx - half_w - 4, lower_y + r * 0.10), (cx + half_w + 4, lower_y + r * 0.10)],
           st.hot, 1.6, 0.8)

    # kotovacia ciara medzery (technicky vykres) - vlavo od zubov
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
    """Uvolnenie stisku mysi: obrys mysi a tlak, ktory z nej odchadza.

    Bodky su tlakove body pod prstami - odletia sikmo (nie rovno hore),
    aby sa nekrizili s kolieskom mysi, a cestou zhasnu.
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

    # oblúk stisku nad tlacidlami - zmizne prvy, to je to "pustenie"
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
    """Dychovy kruh: prstenec s deleniami, dychova gula a postupovy oblúk.

    `phase` je 0..1 v ramci polcyklu, `inhale` urcuje smer. Oblúk je jediny
    prvok, ktory povie KOLKO este ostava - samotna zmena polomeru to
    nepovie, a hrac potrebuje vediet, ci sa oplati zacat s nim dychat.
    """
    cx, cy = w / 2.0, h / 2.0
    outer = min(w, h) * 0.45
    r_min, r_max = outer * 0.30, outer * 0.76
    t = phase if inhale else (1.0 - phase)
    eased = 0.5 - 0.5 * math.cos(math.pi * t)   # dych nie je linearny
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

    # Oblúk sa pri NADYCHU navija (0 -> 360) a pri VYDYCHU sa odvija spat
    # (360 -> 0), takze ide v sympatii s gulou: obe rastu a obe klesaju.
    #
    # POZN: predtym bolo `sweep = 360 * phase` pre obe fazy, teda oblúk sa
    # naplnil DVAKRAT za jeden dych a na prelome skocil z pln0ho na
    # prazdny. Horsie: `N 1.00` a `V 0.00` maju rovnaky polomer gule
    # (obe `eased = 1.0`), takze sa lisili uz len textom v strede - a
    # overlay v hre sa cita PERIFERNE, kde text neprecitas. Presne v
    # momente obratu tak nebolo z coho poznat, ci uz mas vydychovat.
    # Smer pohybu oblúka to povie aj kutikom oka.
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
    """Jeden staticky/animovany snimok vizualu slotu ako RGBA obrazok."""
    p = Painter(width, height, ss=ss)
    fn = VISUAL_DRAW.get(name)
    if fn is None:
        return p.finish()
    fn(p, width, height, style, t=t, label=label)
    return p.finish(glow=2.4, gain=0.8)


def render_breath(width, height, style, phase=0.0, inhale=True, cycle_text=None,
                  ss=2):
    """Snimok dychoveho kruhu. ss=2 zamerne - kresli sa 30x za sekundu."""
    p = Painter(width, height, ss=ss)
    draw_breath_ring(p, width, height, style, phase=phase, inhale=inhale,
                     cycle_text=cycle_text)
    return p.finish(glow=2.6, gain=0.75)


# --------------------------------------------------------------------------
# HUD panel (tep / zataz / relacia)
# --------------------------------------------------------------------------

HUD_WIDTH = 252.0     # logicke 1080p pixely
HUD_HEIGHT = 106.0


def _heart_path(cx, cy, size):
    """Srdce ako polygon - emoji ❤️ sa na kazdom Windows vykresli inak
    (a v niektorych temach je hnede), vlastny tvar je konzistentny."""
    pts = []
    for i in range(41):
        a = math.pi * 2 * i / 40.0
        x = 16 * math.sin(a) ** 3
        y = -(13 * math.cos(a) - 5 * math.cos(2 * a)
              - 2 * math.cos(3 * a) - math.cos(4 * a))
        pts.append((cx + x * size / 16.0, cy + y * size / 16.0))
    return pts


def _zone(stress):
    """ZALOHA len pre staticke nahlady (prazdna Dnes, nastavenia HUD-u,
    dialogy), ktore ziadne `HeartStats` nemaju a pasmo si vyrobia z
    vymysleneho cisla zataze.

    Zivy HUD pasmo NEPOCITA - dostane ho hotove ako `zone=` z
    `HeartStats.zone` (tep voci pokoju). Keby si ho tu ratal zo zataze, slovo
    na HUD-e by sa rozislo s Dnes aj s kontrolkou tepu."""
    if stress >= 75:
        return "critical"
    if stress >= 50:
        return "high"
    if stress >= 25:
        return "raised"
    return "calm"


def zone_color(style, zone):
    """Farba pasma pre HUD a kontrolku tepu.

    Berie ju z toho isteho radu ako appka (`theme.ZONE_TOKENS`) - predtym
    tu bola vlastna dvojica success/accent, takze po tom, co kazda tema
    dostala vlastny rad, svietil HUD zelenou aj tam, kde okno appky uz
    kreslilo modru. Rovnaka farba musi znamenat to iste v hre aj v okne.
    """
    return style.zones.get(zone, style.zones["raised"])


def render_hud(style, bpm=None, stress=0.0, history=(), threshold=None,
               baseline=None, labels=None, pulse=0.0, session=None,
               connected=True, calibrating=False, zone=None, ss=SS):
    """HUD panel: velke BPM, krivka tepu za poslednu ~2 min, pruh zatazenia
    a riadok relacie.

    `history` je postupnost BPM hodnot (stara -> nova), `pulse` je 0..1 faza
    tepu (srdce sa nadychne presne v rytme, aky prave chodi z hodiniek -
    periferne vnimanie tak dostane informaciu aj bez citania cisla).

    `zone` je pasmo z `HeartStats.zone` - slovo, farba panelu aj farba
    plnych dielikov pruhu. Zivy HUD ho posiela vzdy; bez neho (staticke
    nahlady) sa pouzije zaloha `_zone(stress)`. Dlzka pruhu je dalej
    zataz (`stress`); slovo a farba su tep voci pokoju.

    `calibrating` (`HeartStats.is_calibrating`): tep a krivka sa ukazu,
    zataz nie. Pruh ostane prazdny, namiesto pasma je tlmene "kalibrujem…"
    a panel nema farbu pasma, ale neutralnu - `stress` ani `zone` sa vtedy
    vobec necitaju, aby sa do obrazka nedostali ani omylom.
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

    # podklad - tmavy, aby bolo cislo citatelne aj nad snehom aj nad nocou
    p.panel(0, 0, w, h, st.backdrop, 0.62, radius=8)
    p.rect(0.8, 0.8, w - 0.8, h - 0.8, outline=accent, outline_alpha=0.30,
           width=1.0, radius=8)
    p.rect(0, 0, 2.6, h, color=accent, alpha=0.55, radius=1.4)
    corner_brackets(p, 4, 4, w - 4, h - 4, st, length=11, width=1.3, alpha=0.55,
                    chamfer=3)

    # --- srdce + BPM ---
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

    # --- krivka tepu ---
    # Krivka zacina az za cislom - trojciferny tep (100+ BPM) je presne ten
    # pripad, ked hrac HUD najviac potrebuje, a prave vtedy by sa popisok
    # "BPM" prekryl s grafom.
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
        # vypln pod krivkou
        p.polygon(pts + [(gx1, gy1), (gx0, gy1)], color=accent, alpha=0.13)
        if threshold and lo <= threshold <= hi:
            # KRITICKA HRANICA: pasmo, ciara a cislo.
            #
            # Doteraz to bola bezmenna prerusovana ciara - hrac videl, ze
            # krivka nieco prekrocila, ale nie CO. Odkedy si hranicu appka
            # rata sama z jeho relacii (`hr_stats.dynamicky_kriticky`), je to
            # navyse cislo, ktore sa v case meni, takze sa oplati ukazat.
            #
            # Pasmo nad ciarou je zamerne takmer neviditelne (alpha 0,10).
            # HUD ma byt periferny: ked je hrac pod hranicou, nesmie mu to
            # tahat oko, a ked ju prekroci, staci ze krivka vojde do jemne
            # tmavsieho pasu.
            ty = gy1 - (threshold - lo) / span * (gy1 - gy0)
            if ty > gy0 + 1:
                p.rect(gx0, gy0, gx1, ty, color=style.danger, alpha=0.10)
            # Cislo sedi NA ciare vpravo a ciarkovanie sa pred nim zastavi.
            # Keby beželo az po okraj, cifry by lezali na ciarkach a v
            # osembodovom pisme sa to zlieva do skvrny.
            popis = "%d" % int(round(threshold))
            pw = p.measure(popis, 8, kind="label") + 4.0
            for x in range(int(gx0), int(gx1 - pw), 6):
                p.line([(x, ty), (x + 3, ty)], style.danger, 1.0, 0.55)
            p.text(gx1, ty, popis, style.danger, 8, kind="label",
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

    # --- pruh zatazenia ---
    bar_x0, bar_x1 = 14.0, w - 14.0
    bar_y = h - 30.0
    p.text(bar_x0, bar_y - 9, labels.get("load", "LOAD"), style.dim, 9,
           anchor="lb", alpha=0.85, tracking=1.8)
    # bez dat sa nesmie zobrazit "Pokoj" - to by tvrdilo nieco, co appka
    # nevie; pomlcka je jediny poctivy stav. Pocas kalibracie to iste:
    # tep uz chodi, ale zakladna este nie je, tak pasmo nema voci comu.
    if calibrating:
        # "…" je jeden znak a prestrkanie ho neroztiahne - v 9-bodovom
        # Bahnschrift sa tri bodky zlievaju do ciarky ("KALIBRUJEM_").
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
    # Plne dieliky maju farbu AKTUALNEHO pasma, nie kazdy vlastnu podla
    # toho, kde v pruhu lezi. Predtym tu boli stvrtiny pruhu a na Dnes
    # 35/60/80 % - tretia a stvrta definicia tych istych slov. Pri
    # zatazi 57 tak HUD koncil "vysokou", Dnes "zvysenou" a slovo nad
    # pruhom mohlo hovorit este nieco ine.
    for i in range(segments):
        x0 = bar_x0 + i * seg_w
        x1 = x0 + seg_w * 0.72
        if i < filled and connected:
            p.rect(x0, bar_y, x1, bar_y + 6, color=accent, alpha=0.92, radius=1.2)
        else:
            p.rect(x0, bar_y, x1, bar_y + 6, color=style.dim, alpha=0.18, radius=1.2)

    # --- riadok relacie ---
    if session:
        p.text(bar_x0, h - 7, session, style.dim, 8.5, anchor="lb", alpha=0.72,
               tracking=0.5)

    return p.finish(glow=1.8, gain=0.55)


# Ikonky funkcii pod HUD panelom - vysledny obrazok appka len skladá z uz
# hotovych casti (HUD panel z render_hud, riadok ikoniek tu), nie
# prekresluje HUD od znova - to by menilo aj jeho vlastny layout.
TRIGGER_ROW_HEIGHT = 44.0


def render_hud_trigger_row(width, style, triggers, icon_color=None):
    """Riadok so 4 (alebo menej) ikonkami spustacov pod HUD panelom.

    `triggers` je zoznam (visual_name, enabled) - `enabled=False`
    sa vykresli stlmene (hrac vidi, ze slot existuje, ale je vypnuty).
    `icon_color` je volitelna farba pre VSETKY ikonky v riadku (ina nez
    vlastna farba kazdeho vizualu v hre - tu ma byt jeden zjednoteny vzhlad
    male listy funkcii, nie 4 rozne farby vedla seba).
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
        # POZN: tu sa kreslil popisok s klavesom (C, R, F...). Klavesy od
        # fazy 3 nespustaju nic, takze to bol navod, ktory neplatil - a
        # riadok ma byt periferny, nie citany.
    return p.finish(glow=1.2, gain=0.4)


def render_hud_combined(hud_image, trigger_row_image=None):
    """Zlozi HUD panel a volitelny riadok ikoniek pod seba do jedneho
    obrazka (rovnaka sirka, vyssia strana - appka to potom kresli ako
    jedno vrstvene okno namiesto dvoch, co je jednoduchsie na umiestnenie
    aj klikatelnost)."""
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
# Ikony do rozhrania appky (nahrada emoji v zozname slotov)
# --------------------------------------------------------------------------

def render_slot_icon(name, size, style, ss=SS):
    """Mala stvorcova ikona do zoznamu/dialogu/Sprievodcu - rovnaka grafika
    ako in-game vizual, len bez animacie a bez popisku.

    Vacsina mien su vizualy slotov (grounding/jaw/release/breath), ale
    `heart` a `periphery` vizual v hre nemaju - su tu preto, aby kazdy
    obrazok v appke kreslil ten isty stetec a tá istá paleta.
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
        # MÄKKÝ POHĽAD (karta "Uvoľnenie & periféria" v Sprievodcovi).
        #
        # Nie je to vizual slotu - do hry sa nekresli. Je tu preto, lebo
        # Sprievodca mal na tejto karte tenky nacrt na Canvase a vedla
        # stetcovych piktogramov posobil ako obrazok z inej appky.
        #
        # Tri veci a nic viac, rovnaka disciplina ako zvysok sady:
        #   * oko ako DVA tahy (horne a dolne viecko), nie uzavreta
        #     elipsa - zatvoreny obrys vyzeral ako koliesko, nie oko;
        #   * duhovka rovnakym zapisom ako "breath" (mekka vypln +
        #     prstenec v `hot`), takze obe karty patria k sebe;
        #   * periferne pole = dva siroke tlmene oblúky po stranach.
        #     Su ZAMERNE bledé: to, co si clovek ma vsimnut, je stred,
        #     a okraj ma byt citelny aj ked sa nan nepozrie priamo -
        #     presne to, o com tá karta je.
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
        # ZNACKA QR, nie QR kod.
        #
        # Skutocny QR je biely stvorec - v tmavom paneli buchne do oci a
        # vytiahne pozornost na nieco, co vacsina ludi ani nepotrebuje
        # (kto uz appku v telefone ma, QR nechce). Preto je navonok len
        # tato znacka v akcente temy a biely kod sa ukaze az na klik.
        #
        # Tri rohove oci + par modulov - tolko, aby to oko precitalo ako
        # "QR", a nic viac; vypln modulov je zamerne redsia nez oci.
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
        # TABULKA (export relacii). Nie logo Excelu - to je cudzia znacka a
        # v tejto sade by trcalo ako nalepka. Hlavicka je plna, riadky su
        # len linky: tak vyzera tabulka na prvy pohlad, aj ked je mala.
        m = size * 0.14
        w = size - 2 * m
        hlavicka = size * 0.17
        p.rect(m, m, m + w, m + hlavicka, color=st.accent, alpha=0.85,
               radius=size * 0.03)
        p.rect(m, m, m + w, size - m, outline=st.accent, outline_alpha=0.9,
               width=size * 0.045, radius=size * 0.03)
        # dva zvisle deliace stlpce
        for podiel in (0.36, 0.68):
            p.line([(m + w * podiel, m + hlavicka), (m + w * podiel, size - m)],
                   st.accent, size * 0.035, 0.55)
        # vodorovne riadky; posledny je `hot` - to je ten, ktory prave pribudol
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
# Enso (円相) - hlavne tlacidlo spusti/zastavi pocuvanie, v strede sidebaru
# --------------------------------------------------------------------------

# Dychovy cyklus znacky: podiely z celku (spolu 1.0).
# 10 s cyklus = 6 dychov/min. Upokojujuce tempo je 4,5-6,5 dychu/min -
# okolo neho sa srdce, pluca a tlakove vlny zosynchronizuju. Enso predtym
# dychalo 4,3 s (~14 dychov/min), co je tempo pokojneho az mierne
# rozruseneho cloveka, nie upokojujuce.
#
# Nesumerne a s pauzou ZAMERNE: rovnaky nadych aj vydych bez zastavenia je
# metronom, nie dych. Dlhsi vydych je navyse parasympaticky smer (blúdivy
# nerv), a skutocny dych sa na obratke na chvilu zastavi - cisty sinus
# nikdy nezastane a prave to posobi mechanicky.
ENSO_INHALE = 0.42        # 4,2 s
ENSO_HOLD = 0.06          # 0,6 s pauza na vrchole
ENSO_EXHALE = 0.52        # 5,2 s
ENSO_CYCLE_MS = 10000


def enso_breath(phase):
    """Hodnota dychu 0..1 pre danu fazu 0..1 (0 = vydychnute, 1 = nadych).

    Kazda faza ma vlastne plynule nabehnutie (`0.5 - 0.5*cos`), takze
    krivka nema nikde zlom - len sa na vrchole na chvilu zastavi.
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
    """Naramkove hodinky nakreslene TVARMI, nie emoji.

    Rovnaky dovod ako pri `_heart_path`: znak ⌚ sa na kazdom Windows
    vykresli inak a vo fonte rozhrania casto chyba uplne - vtedy z neho
    ostane prazdny stvorcek. Vlastny tvar vyzera vsade rovnako.

    Cirferník + dva remienky: samotny kruzok by sa v prstenci stratil,
    prave remienky ho robia rozpoznatelnym aj pri 24 px.
    """
    r = size * 0.46
    sirka = r * 0.78
    # remienky hore a dole (mierne sa zuzuju smerom von)
    for smer in (-1, 1):
        y0 = cy + smer * r * 0.82
        y1 = cy + smer * r * 1.62
        p.polygon([(cx - sirka, y0), (cx + sirka, y0),
                   (cx + sirka * 0.66, y1), (cx - sirka * 0.66, y1)],
                  color=color, alpha=alpha * 0.75)
    # cirferník
    p.ellipse(cx, cy, r, r, outline=color, outline_alpha=alpha,
              width=max(1.0, size * 0.13))
    # rucicky - male, len aby to nebol prazdny kruzok
    p.line([(cx, cy), (cx, cy - r * 0.52)], color, size * 0.10, alpha * 0.95)
    p.line([(cx, cy), (cx + r * 0.40, cy)], color, size * 0.10, alpha * 0.8)


def heartbeat_envelope(phase):
    """0..1 obalka JEDNEHO tepu: prudky nabeh, pomalsi dobeh.

    Srdce nebije sinusovo - stiahne sa rychlo a uvolnuje sa dlhsie. Cisty
    sinus by citali oci ako dychanie, a enso vedla uz dycha; tento tvar ich
    od seba odlisi aj bez farby.
    """
    t = phase % 1.0
    nabeh = 0.16
    if t < nabeh:
        return t / nabeh
    u = (t - nabeh) / (1.0 - nabeh)
    return max(0.0, (1.0 - u) ** 2.2)


def render_pulse_ring(size, style, phase=0.0, zone=None, connected=False,
                      waiting=False, ss=SS):
    """Prstenec s hodinkami v strede - ziva kontrolka senzora tepu.

    Tri stavy:
      * NESPAROVANE (`connected=False`) - prstenec tlmeny a nehybny,
        hodinky sive. Nie je co odrazat.
      * SPAROVANE, CAKA (`waiting=True`) - prstenec svieti neutralne a
        pomaly dycha: "spojene, tep este nedosiel".
      * SPAROVANE + TEP - prstenec bije v REALNOM rytme hodiniek
        (`phase` z `HeartStats.beat_phase()`) a farbu berie zo `zone`.

    PRECO FARBA PODLA PASMA A NIE ZELENA/CERVENA: appka uz pasma ma
    (`HeartStats.zone`/`zone_color`) a kresli nimi HUD v hre - rovnaka farba
    tak znamena to iste v bocnom paneli aj nad hrou, jeden zdroj pravdy.
    Navyse ~12 % muzov nerozlisi cervenu od zelenej, takze farba nesmie
    byt jediny nosic: hlavnu informaciu tu nesie RYCHLOST tepania
    prstenca, ktora je citatelna bez ohladu na vnimanie farieb.
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
        # "neutral" = kalibracia (HeartStats.is_calibrating): rovnaka tlmena
        # farba ako HUD v tom stave, ziadne pasmo.
        barva = (style.dim if zone == "neutral"
                 else zone_color(style, zone or "calm"))
        tep = heartbeat_envelope(phase)
        # pokojny prstenec + druhy, ktory sa s kazdym tepom rozsiri a
        # zhasne - "vlna" von, ako ked sa tlak siri cievou
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
    """Kruh stetcom + znak 残 - znacka appky a zaroven spinac pocuvania.

    `color` prebije stavovu farbu. Je to pre miesta, kde znacka NIE JE
    spinac, ale len logo (Sprievodca) - tam by zelena/cervena tvrdila stav,
    ktory ten obrazok nesleduje, a cervene enso v prirucke by sa citalo
    ako chyba. S akcentom temy sadne medzi ostatne piktogramy, ktore su
    kreslene rovnako (`render_slot_icon`).

    FARBA nesie stav a ide podla zauzivanej konvencie nahravania:
      * ZELENA (`success`)  = appka pocuva, spustace su ziva
      * CERVENA (`danger`)  = nepocuva, nic sa nedeje
    POZN: bolo to naopak (zelena = pripravene, bengara = bezi). Cervena na
    beziacej appke ale citala ako chyba a zelena na zastavenej ako "vsetko
    v poriadku" - presny opak toho, co stav znamena. Cervena bodka =
    nenahrava sa, zelena = nahrava sa, to pozna kazdy.

    `phase` je 0..1 a robi z ikony ZIVY prvok - nie staticky obrazok.
    Rovnaka krivka ako dychovy kruh (`0.5 - 0.5*cos`), takze enso pomaly
    "dycha": tah sa zjemna a zosilnie, polomer sa nepatrne meni. Ked appka
    pocuva, po obvode navyse obieha svetly oblúk - "nacitava sa", teda
    bezi. Ked nepocuva, dycha len vemi jemne a oblúk nie je.

    `armed` = spustac je natiahnuty (`trigger.ARMED`): telo drzi nad prahom
    uz 90 s a appka caka na pauzu, aby sa ozvala. Kresli sa ako VNUTORNY
    prstenec, ktory sa s nadychom stahuje. Tri veci na nom su zamerne:

      * DOVNUTRA, nie von. Vonku uz prstenec je (nacitavaci, r*1.20) a
        znamena "bezi". Druhy prstenec v tom istom medzikruzi by sa citali
        ako jedna ozdoba, nie ako dva stavy. Vnutri je volne miesto medzi
        znakom (~0.17*size) a tahom (0.40*size).
      * ROVNAKA FARBA ako znacka. `theme.py` hovori, ze farba ensa ma v
        celom rozhrani jedinu ulohu - povedat, ci appka pocuva. Natiahnutie
        preto NIE JE tretia farba; nesie ho pohyb.
      * STAHUJE sa, kym nacitavaci prstenec sa PLNI. Opacny smer je to,
        co tie dva prstence od seba odlisi aj kutikom oka.

    POZN: polomer sa rata z NEDYCHAJUCEHO zakladu (`r_zaklad`), nie z `r`.
    Keby sa ratal z `r`, dychanie samotneho tahu (0.955 -> 1.045) by
    stahovanie takmer vyrusilo - vyslo by z 12 % rozkmitu 1,5 % a prstenec
    by stal.
    """
    size = int(size)
    p = Painter(size, size, ss=ss)
    # FARBA podla TEMY (accent) - zlate v Sumi, modre v Aizome. Stav uz nenesie
    # farba enso (nesie ho dychajuci pas + bodka v paneli), ale POHYB: v klude
    # enso stoji, pri pocuvani dycha a plni sa lesk. `color` prebije akcent
    # (logo v Sprievodcovi).
    base = color or style.accent
    cx, cy = size / 2.0, size / 2.0

    dych = enso_breath(phase) if live else 0.0

    r_zaklad = size * 0.40
    r = r_zaklad * (0.955 + 0.09 * dych)
    sila = (0.78 + 0.22 * dych) if live else 0.70

    # NACITAVACI PRSTENEC (za znackou) - plni sa s nadychom.
    if live and dych > 0.004:
        r_load = r * 1.20
        p.arc(cx, cy, r_load, r_load, -90.0, -90.0 + 360.0 * dych,
              base, size * 0.030, 0.40)

    # Samotne enso - TENKY otvoreny tah (minimalisticke), ku koncu jemne stenci.
    predlzenie = 24.0 * dych
    span = (188.0 + predlzenie) - (-78.0)
    p.arc(cx, cy, r, r, -78, 188 + predlzenie, base, size * 0.034, 0.95 * sila)
    p.arc(cx, cy, r, r, 150 + predlzenie, 188 + predlzenie, base,
          size * 0.046, 0.55 * sila)

    # NAPLNAJUCI SA LESK - svetle zlato sa plni pozdlz tahu s nadychom + jemny
    # sweep. VIAZANE na `live` a `sheen` (klud = ziadny lesk), nech testy ostanu
    # byte-identicke pri live=False.
    if live and sheen and dych > 0.004:
        p.arc(cx, cy, r, r, -78, -78 + span * dych, style.hot,
              size * 0.034, 0.14 + 0.72 * dych)
        stred = -78 + span * (phase % 1.0)
        p.arc(cx, cy, r, r, stred - 15, stred + 15, style.hot,
              size * 0.034, 0.28)

    # PROMOCIA - otvoreny prstenec sa uzavrie do plneho kruhu (close 0->1).
    if close > 0.0:
        koniec = (188.0 + predlzenie) + (282.0 - (188.0 + predlzenie)) * min(1.0, close)
        p.arc(cx, cy, r, r, 188 + predlzenie, koniec, base, size * 0.034, 0.95 * sila)

    # NATIAHNUTE - vnutorny prstenec (armed), stahuje sa s nadychom.
    if armed and live:
        r_arm = r_zaklad * 0.72 * (1.0 - 0.12 * dych)
        p.arc(cx, cy, r_arm, r_arm, -90.0, 270.0, base,
              size * 0.018, 0.45 + 0.30 * dych)

    # MESACNA ZIARA (halo) - po promocii enso ziari ako mesiac: mekke svetle
    # teleso vnutri prstenca + silnejsi bloom vo finish().
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


# POZN: tu bola sekcia "Dojo pas (horny band pozadia) a lampiony" -
# `_load_dojo_band_source()`, `render_dojo_band()`, `_radial_blob()`,
# `render_lamp_glow()` a tabulky `_LAMP_POSITIONS`/`_LAMP_COLORS`.
# Kreslili fotopas pevnej vysky nad titulkovou listou appky vratane
# pulzujucich lampionov. Pas bol z okna odstraneny (viz POZN v
# `ui_shell` a `DandurfApp._build_ui`), takze tieto funkcie uz nemal
# kto volat - pyflakes ich ako nepouzite moduloved funkcie nenahlasi,
# preto su zmazane rucne. S nimi sa prestal pouzivat aj obrazok
# `assets/images/dojo_band.jpg`.
