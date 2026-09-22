# -*- coding: utf-8 -*-
"""Vyrobi Dandurf.ico - ZLATE ENSO (znacka appky) na tmavom zaoblenom podklade.

Preco enso a nie stary stvorec so znakom
----------------------------------------
Do 2.1 to bol znak 残 na INDIGOVOM stvorci (stara tema Aizome). Appka je uz
ZLATA (Zen) a jej identita je ENSO - kruh stetcom + 残 - presne to, co pláva
na hlavnej obrazovke. Aby ikona v listi, ikona na ploche a znacka v okne boli
JEDNA vec, ikona teraz kresli to iste enso cez `hud_paint.render_enso` (jediny
zdroj pravdy pre enso v celej appke).

Farba enso nesie STAV (v systemovej listi cez `tray_mark`):
  * ZELENA (success) = appka pocuva, spustace su ziva
  * CERVENA (danger) = nepocuva, nic sa nedeje
Staticka .ico (ikona suboru/exe) je v akcente temy = ZLATA, neutralna znacka.

Preco tmavy zaobleny podklad
----------------------------
Enso je TENKY tah - na svetlej listi by na priehladnom pozadi zaniklo. Tmavy
zaobleny stvorec mu da citatelnost a zaroven odlisi ikonu od kruhovych ikon
ostatnych appiek. Kazda velkost sa uklada zvlast (`append_images`), takze si
Windows vezme spravnu kresbu pre dany kontext.

Spustenie:  python make_icon.py
"""
import os
import sys

from PIL import Image, ImageDraw

import hud_paint
import theme

OUT = "Dandurf.ico"          # nazov ponechany - odkazuje nan Dandurf.spec,
                             # Dandurf.iss aj build_all.ps1
SS = 4                       # supersampling podkladu

# Velkosti v .ico (kazda vlastna kresba pri downscale z SS).
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
    """Tmavy zaobleny stvorec s jemnym zvislym prechodom + tenky zlaty ram."""
    pal = _pal()
    s = px * SS
    bg = _rgb(pal.get("bg"), (13, 14, 19))
    top = tuple(min(255, c + 12) for c in bg)      # hore o kus svetlejsie
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
    """Ikona danej velkosti: tmavy podklad + enso (zlate, alebo `color`).

    `color` (#rrggbb) prebije akcent - pouziva `tray_mark` na farbu stavu.
    """
    back = _backdrop(px)
    try:
        style = hud_paint.Style(_pal())
        enso = hud_paint.render_enso(px, style, live=False, phase=0.0, color=color)
        back.alpha_composite(enso, (0, 0))
    except Exception:
        sys.stderr.write("VAROVANIE: enso sa nepodarilo vykreslit (pismo/PIL).\n")
    return back


def tray_mark(px=64, ring_color=None):
    """Znacka do systemovej listy - enso vo farbe STAVU.

    `ring_color` je RGB n-tica (zelena = pocuvam / cervena = nepocuvam), ako
    ju posiela `app.make_tray_image`. Nazov aj podpis su zachovane kvoli
    spatnej kompatibilite volajucich.
    """
    color = "#%02x%02x%02x" % tuple(ring_color[:3]) if ring_color else None
    return render(px, color=color)


def main():
    frames = {px: render(px) for px in LAYOUT}
    base = frames[256]
    base.save(OUT, format="ICO", sizes=[(px, px) for px in LAYOUT],
              append_images=[frames[px] for px in LAYOUT if px != 256])
    print(f"{OUT} hotovo - {len(LAYOUT)} velkosti (zlate enso)")

    # nahlad: velka verzia + realne velkosti vedla seba, aj stavove varianty
    pal = _pal()
    prev = Image.new("RGBA", (620, 320), (13, 14, 19, 255))
    prev.alpha_composite(frames[256], (16, 24))
    x = 300
    for px in (64, 48, 32, 16):
        prev.alpha_composite(frames[px], (x, 40))
        ImageDraw.Draw(prev).text((x + px / 2, 40 + px + 8), f"{px}", anchor="mt",
                                  fill=(120, 130, 150))
        x += px + 20
    # stav: pocuvam (zelena) / nepocuvam (cervena)
    prev.alpha_composite(tray_mark(64, _rgb(pal.get("success"), (127, 179, 154))), (300, 200))
    prev.alpha_composite(tray_mark(64, _rgb(pal.get("danger"), (192, 74, 62))), (380, 200))
    ImageDraw.Draw(prev).text((300, 270), "pocuvam        nepocuvam", fill=(150, 150, 160))
    prev.convert("RGB").save("icon_preview.png")
    print("icon_preview.png hotovo")


if __name__ == "__main__":
    main()
