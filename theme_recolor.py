# -*- coding: utf-8 -*-
"""Recolouring an already built window on a theme change - WITHOUT a rebuild.

WHY THIS EXISTS
---------------
Switching the theme called `DandurfApp._build_ui()`, which destroyed and
rebuilt the whole window from scratch. Measured: 1374 widgets, 101 878 Tk
calls, **2.97 s** of blocking (the same in both directions) - and the
player watched for those three seconds as the window was assembled piece
by piece (29 different intermediate states). There is no single slow
spot in it, it is sheer volume: every CustomTkinter widget draws itself
onto its own canvas with rounded shapes.

Instead, here we walk the already existing widget tree and rewrite their
colours. No `destroy()`, no building - just `configure()`.

HOW THE MAPPING WORKS
---------------------
We do not need to know which token a colour came from: a map "old value
-> new value" built from the two palettes is enough. A widget whose
`fg_color` equals `zen['surface']` gets `modern['surface']`.

Colours that are NOT in the old palette (e.g. a visual's own colour the
player picked with the colour picker, or CustomTkinter's default colours)
are deliberately left alone - they are not driven by the theme.

AMBIGUITY
---------
Some tokens have the same value within a theme. Most are harmless
(`surface` == `card` and map to the same thing), but e.g. in Sumi both
`accent` and `keycap_text` have the value #d9b868, while in Modern they
differ. For such cases there is `_PREFERENCIA`: the semantically dominant
token wins, and widgets for which that would not fit are sorted out by
their own `set_pal()` (see `IMAGE_HOOKS` and `ui_kit.Keycap`).

IMAGES
------
What is drawn as an image (the enso, the heart-rate indicator, the HUD
preview) cannot be recoloured - it has to be redrawn. Each such element
has its own `set_pal()`, which `DandurfApp._recolor_ui` calls after
walking the tree. The same holds for elements that keep their OWN copy of
the palette (Sidebar, _NavRow, TitleBar) - otherwise they would bring
back the old colours on the first hover/click.
"""

# Which token wins when several tokens have the same value. Everything
# not listed has a lower priority than the listed ones, in the order they
# are here.
_PREFERENCIA = (
    "bg", "surface", "surface_alt", "text", "text_dim", "text_faint",
    "border", "line_soft", "accent", "accent_hover", "accent2",
    "accent2_hover", "danger", "success", "warn",
)

# Options that carry a colour. `bg`/`background` and `fg`/`foreground`
# are aliases of the same thing in Tk - setting one is enough, so the
# other is not in the list.
COLOR_OPTIONS = (
    # `bg_color` is a derived background colour that CustomTkinter finds
    # out from the parent and STORES. When the parent's `fg_color` changes,
    # this copy stays old and shows through in the widget's rounded corners.
    # Only the "recolouring == rebuild" test revealed it, on the inner
    # canvas of the segmented theme switch - by eye you would notice at
    # most a lighter rim around the corners.
    "bg_color",
    "fg_color", "text_color", "hover_color", "border_color",
    "button_color", "button_hover_color", "progress_color",
    "selected_color", "selected_hover_color",
    "unselected_color", "unselected_hover_color",
    "scrollbar_button_color", "scrollbar_button_hover_color",
    "dropdown_fg_color", "dropdown_text_color", "dropdown_hover_color",
    "placeholder_text_color",
    "bg", "fg", "selectbackground", "selectforeground",
    "highlightbackground", "insertbackground",
)


def build_color_map(old_pal, new_pal):
    """Map 'old value (lowercase) -> new value'.

    Takes `_PREFERENCIA` into account when several tokens have the same
    old value but different new ones.
    """
    poradie = {meno: i for i, meno in enumerate(_PREFERENCIA)}
    kandidati = {}
    for token, stara in old_pal.items():
        nova = new_pal.get(token)
        if not isinstance(stara, str) or not isinstance(nova, str):
            continue
        if not stara.startswith("#") or not nova.startswith("#"):
            continue
        kluc = stara.lower()
        vaha = poradie.get(token, len(poradie) + 1)
        if kluc not in kandidati or vaha < kandidati[kluc][0]:
            kandidati[kluc] = (vaha, nova)
    return {k: v for k, (_, v) in kandidati.items()}


def _preloz(hodnota, mapa):
    """Returns the new value, or None when it should not change."""
    if isinstance(hodnota, (list, tuple)):
        nove = [_preloz(h, mapa) for h in hodnota]
        if all(n is None for n in nove):
            return None
        return tuple(n if n is not None else s for n, s in zip(nove, hodnota))
    if not isinstance(hodnota, str):
        return None
    s = hodnota.lower()
    if not s.startswith("#"):
        return None          # we leave "transparent" and colour names alone
    return mapa.get(s)


def recolor_widget(widget, mapa):
    """Recolours ONE widget. Returns the number of changed options.

    All changes go in ONE `configure()` call. That matters: every
    `configure()` on a CustomTkinter widget triggers a full redraw onto
    the canvas, so calling it once per colour meant up to 4 redraws of
    the same button. Merging them sped the recolouring up by almost
    half.
    """
    zmeny = {}
    for opt in COLOR_OPTIONS:
        try:
            stara = widget.cget(opt)
        except Exception:
            continue
        nova = _preloz(stara, mapa)
        if nova is None or nova == stara:
            continue
        zmeny[opt] = nova
    if not zmeny:
        return 0
    try:
        widget.configure(**zmeny)
        return len(zmeny)
    except Exception:
        pass
    # The batch did not go through (e.g. one option can no longer be set) -
    # we try one by one, so the rest is not lost because of one bad one.
    zmen = 0
    for opt, nova in zmeny.items():
        try:
            widget.configure(**{opt: nova})
            zmen += 1
        except Exception:
            pass
    return zmen


def recolor_tree(widget, mapa, skip=()):
    """Walks the tree and recolours it all. Returns (widgets, changed options).

    `skip` are classes to be skipped together with their descendants -
    typically separate Toplevel windows (HUD, in-game visuals) that have
    their own path for a theme change.
    """
    widgetov = 0
    zmien = 0
    zasobnik = [widget]
    while zasobnik:
        w = zasobnik.pop()
        if skip and isinstance(w, skip):
            continue
        widgetov += 1
        zmien += recolor_widget(w, mapa)
        try:
            zasobnik.extend(w.winfo_children())
        except Exception:
            pass
    return widgetov, zmien


def find_theme_colored(widget, old_pal, new_pal=None, skip=()):
    """Finds widgets that still hold a colour from the OLD palette.

    Used after recolouring as a safeguard: whatever is found is a
    forgotten widget. Returns a list of (widget_path, option, value).

    `new_pal` is important to pass: tokens that have THE SAME value in
    both themes (`warn`, `washi`, `font_family`) correctly do not change -
    without it they would be reported as forgotten, although they are
    fine.
    """
    nemenne = set()
    if new_pal:
        nemenne = {str(v).lower() for k, v in old_pal.items()
                   if isinstance(v, str) and str(new_pal.get(k, "")).lower() == str(v).lower()}
    hodnoty = {str(v).lower() for v in old_pal.values()
               if isinstance(v, str) and v.startswith("#")} - nemenne
    najdene = []
    zasobnik = [widget]
    while zasobnik:
        w = zasobnik.pop()
        if skip and isinstance(w, skip):
            continue
        for opt in COLOR_OPTIONS:
            try:
                val = w.cget(opt)
            except Exception:
                continue
            vals = val if isinstance(val, (list, tuple)) else [val]
            for v in vals:
                if isinstance(v, str) and v.lower() in hodnoty:
                    najdene.append((str(w), opt, str(v)))
        try:
            zasobnik.extend(w.winfo_children())
        except Exception:
            pass
    return najdene
