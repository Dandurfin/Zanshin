# -*- coding: utf-8 -*-
"""Makes Dandurf.ico - a GOLDEN ENSO (the app's mark) on a dark rounded base.

Why the enso and not the old square with the character
------------------------------------------------------
Up to 2.1 it was the character 残 on an INDIGO square (the old Aizome
theme). The app is GOLDEN (Zen) now and its identity is the ENSO - a brush
circle + 残 - exactly what floats on the main screen. So that the tray
icon, the desktop icon and the mark in the window are ONE thing, the icon
now draws the same enso via `hud_paint.render_enso` (the single source of
truth for the enso in the whole app).

The enso colour carries the STATE (in the system tray via `tray_mark`):
  * GREEN (success) = the app is listening, the triggers are live
  * RED (danger) = not listening, nothing is happening
The static .ico (file/exe icon) is in the theme accent = GOLD, a neutral
mark.

Why a dark rounded base
-----------------------
The enso is a THIN stroke - on a light taskbar it would vanish on a
transparent background. A dark rounded square gives it legibility and at
the same time sets the icon apart from the round icons of other apps. Each
size is stored separately (`append_images`), so Windows takes the right
drawing for the given context.

Running:  python make_icon.py
"""
import sys

from PIL import Image, ImageDraw

import hud_paint
import theme

OUT = "Dandurf.ico"          # name kept - referenced by Dandurf.spec,
                             # Dandurf.iss and build_all.ps1
SS = 4                       # base supersampling

# Sizes in the .ico (each its own drawing when downscaling from SS).
LAYOUT = [256, 128, 64, 48, 32, 16]


def _pal():
    return theme.THEMES[theme.DEFAULT_THEME]


def _rgb(hex_or_none, fallback=(217, 184, 104)):
    if not hex_or_none:
        return fallback
    h = hex_or_none.lstrip("#")
    try:
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    except (ValueError, IndexError):
        return fallback


def _backdrop(px):
    """Dark rounded square, soft vertical gradient + a thin gold border."""
    pal = _pal()
    s = px * SS
    bg = _rgb(pal.get("bg"), (13, 14, 19))
    top = tuple(min(255, c + 12) for c in bg)      # a bit lighter at the top
    col = Image.new("RGB", (1, s))
    for y in range(s):
        t = y / max(1, s - 1)
        col.putpixel((0, y), tuple(round(top[i] + (bg[i] - top[i]) * t) for i in range(3)))
    grad = col.resize((s, s), Image.BILINEAR).convert("RGBA")

    pad = s * 0.045
    radius = s * 0.22
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle((pad, pad, s - pad, s - pad),
                                           radius=radius, fill=255)
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    img.paste(grad, (0, 0), mask)
    rim = _rgb(pal.get("accent"))
    ImageDraw.Draw(img).rounded_rectangle((pad, pad, s - pad, s - pad), radius=radius,
                                          outline=rim + (70,), width=max(1, int(s * 0.012)))
    return img.resize((px, px), Image.LANCZOS)


def render(px, color=None):
    """Icon of the given size: dark base + enso (gold, or `color`).

    `color` (#rrggbb) overrides the accent - `tray_mark` uses it for the
    state colour.
    """
    back = _backdrop(px)
    try:
        style = hud_paint.Style(_pal())
        enso = hud_paint.render_enso(px, style, live=False, phase=0.0, color=color)
        back.alpha_composite(enso, (0, 0))
    except Exception:
        sys.stderr.write("WARNING: couldn't draw the enso (font/PIL).\n")
    return back


def tray_mark(px=64, ring_color=None):
    """Mark for the system tray - the enso in the colour of the STATE.

    `ring_color` is an RGB tuple (green = listening / red = not listening),
    as `app.make_tray_image` sends it. The name and the signature are kept
    for backward compatibility of the callers.
    """
    color = "#%02x%02x%02x" % tuple(ring_color[:3]) if ring_color else None
    return render(px, color=color)


def main():
    frames = {px: render(px) for px in LAYOUT}
    base = frames[256]
    base.save(OUT, format="ICO", sizes=[(px, px) for px in LAYOUT],
              append_images=[frames[px] for px in LAYOUT if px != 256])
    print(f"{OUT} done - {len(LAYOUT)} sizes (golden enso)")

    # preview: big version + real sizes side by side, the state variants too
    pal = _pal()
    prev = Image.new("RGBA", (620, 320), (13, 14, 19, 255))
    prev.alpha_composite(frames[256], (16, 24))
    x = 300
    for px in (64, 48, 32, 16):
        prev.alpha_composite(frames[px], (x, 40))
        ImageDraw.Draw(prev).text((x + px / 2, 40 + px + 8), f"{px}", anchor="mt",
                                  fill=(120, 130, 150))
        x += px + 20
    # state: listening (green) / not listening (red)
    prev.alpha_composite(tray_mark(64, _rgb(pal.get("success"), (127, 179, 154))), (300, 200))
    prev.alpha_composite(tray_mark(64, _rgb(pal.get("danger"), (192, 74, 62))), (380, 200))
    ImageDraw.Draw(prev).text((300, 270), "listening      not listening", fill=(150, 150, 160))
    prev.convert("RGB").save("icon_preview.png")
    print("icon_preview.png done")


if __name__ == "__main__":
    main()
