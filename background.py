# -*- coding: utf-8 -*-
"""Photo in the window background - one place where it can be swapped.

HOW TO CHANGE IT
----------------
Want ANOTHER PHOTO?   put it in `assets/images/` as `dojo_noc.<anything>`.
                      Extension does not matter - .jpg, .jpeg, .png or .webp.
Want ANOTHER NAME?    change `IMAGE_NAME` below. It is the only occurrence in
                      the project.
Want ANOTHER OPACITY? `background_opacity` in dandurf_settings.json, or
                      `DEFAULT_OPACITY` for new profiles.
Want it OFF?          opacity to 0, or simply leave the file out.

NOTE: there is NO slider in Settings yet - the value is changed in the JSON or
here in the code. It is one of the five simple controls from spec §3.1 and is
waiting for a decision on which of them it will be.

No caller knows the file name or the path - everything goes through `load()`.

IF THE FILE IS MISSING, NOTHING HAPPENS
---------------------------------------
`load()` returns None and the app draws as before. This is deliberate: the
photo is decoration, not part of the functionality, and a missing file must not
bring the window down. It is logged ONCE, not on every redraw.

WHY IT IS CACHED
----------------
Scaling the photo down with LANCZOS costs tens of milliseconds. A redraw
happens on every size and theme change, so without a cache it would be
computed over and over. The key is (width, height, opacity) - when any of
them changes, it is computed again.

NOTE ON HISTORY: in version 2.0 there was a "dojo band" here - a fixed-height
photo ABOVE the title bar. It was removed because it was 130 px of dead space
that took away from the fixed window height (app.py, `_build_ui`). This is
something else: the background of an ALREADY EXISTING area, so it does not
take up a single extra pixel. That objection does not apply to it.
"""

import os

try:
    from PIL import Image, ImageChops, ImageDraw, ImageFilter
    PIL_AVAILABLE = True
except Exception:                       # pragma: no cover - without Pillow
    Image = None
    ImageChops = None
    ImageDraw = None
    ImageFilter = None
    PIL_AVAILABLE = False

import paths

# --------------------------------------------------------------------------
# THE ONLY TWO THINGS THAT USUALLY CHANGE
# --------------------------------------------------------------------------

# File name in `assets/images/` WITHOUT THE EXTENSION. The only occurrence in
# the project.
IMAGE_NAME = "dojo_noc"

# Extensions we try. The order decides when several of them lie side by side.
# Why a list at all: a downloaded photo does not always have the extension you
# expect - the first one we put here came as .webp and the app simply did not
# find it. Looking for exactly one name is a trap you only find out about when
# the background stays the old one and there is no error anywhere.
EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")

# Opacity for new profiles, 0.0 - 1.0. Deliberately LOW: the whole design of
# the app rests on catching the "Armed" ring out of the corner of your eye,
# and peripheral vision reacts to motion and contrast in a CALM field. A
# striking photo behind everything is the most effective way to kill that.
DEFAULT_OPACITY = 0.10

# You cannot go above this value even through the settings. It is not
# arbitrary: at a higher value the small text in the panels stops being
# readable, and it comes in eleven languages, including Japanese and
# Chinese.
MAX_OPACITY = 0.35

# NOTE (0.2): there used to be a fallback here - the old narrow band
# `dojo_band.jpg` from version 2.0. It was never loaded at runtime
# (`dojo_noc.webp` is in the repo and in the build, both in the same folder),
# so it goes to _archiv. Without the photo the app keeps drawing - `load`
# returns None and the caller draws nothing.


# --------------------------------------------------------------------------

_cache = {}
_warned = False


def image_path():
    """Path to the photo, or None when there is none.

    Tries `IMAGE_NAME` with all `EXTENSIONS`. Everything is in
    `assets/images/`, which `Dandurf.spec` packs whole - nothing needs to be
    added to the build.
    """
    try:
        base = paths.images_dir()
    except Exception:
        return None
    mena = [IMAGE_NAME + p for p in EXTENSIONS]
    for meno in mena:
        cesta = os.path.join(base, meno)
        if os.path.exists(cesta):
            return cesta
    return None


def available():
    return PIL_AVAILABLE and image_path() is not None


def clamp_opacity(value, default=DEFAULT_OPACITY):
    """0.0 - MAX_OPACITY. Nonsense falls back to the default value."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return default
    if value != value:                  # NaN
        return default
    return max(0.0, min(MAX_OPACITY, value))


def load(width, height, opacity=DEFAULT_OPACITY, log=None):
    """The photo cropped to `width` x `height` and dimmed to `opacity`.

    Returns an RGBA image, or None - when there is no Pillow, no file, or the
    opacity is zero. The caller never has to ask "does it exist?",
    `if img is not None` is enough.

    It is cropped at the CENTRE and keeps the aspect ratio: the photo is wider
    (16:9) than the area it goes on, so stretching it to the height would
    turn it into mush.
    """
    global _warned
    if not PIL_AVAILABLE:
        return None
    try:
        width, height = int(width), int(height)
    except (TypeError, ValueError):
        return None
    if width < 2 or height < 2:
        return None
    opacity = clamp_opacity(opacity)
    if opacity <= 0.0:
        return None

    cesta = image_path()
    if cesta is None:
        if not _warned:
            _warned = True
            if callable(log):
                log("pozadie: %s%s nie je v assets/images - kresli sa bez"
                    % (IMAGE_NAME, "|".join(EXTENSIONS)))
        return None

    kluc = (cesta, width, height, round(opacity, 3),
            os.path.getmtime(cesta) if os.path.exists(cesta) else 0)
    hotove = _cache.get(kluc)
    if hotove is not None:
        return hotove

    try:
        with Image.open(cesta) as zdroj:
            img = zdroj.convert("RGB")
            img = _orez_na_pomer(img, width, height)
            img = img.resize((width, height), Image.LANCZOS)
        img = img.convert("RGBA")
        # The dimming goes into the ALPHA, not the brightness: through alpha
        # the photo blends with what is under it (the theme background), so in
        # Sumi it stays warm and in Aizome cool. Darkening the brightness would
        # just make it grey in both themes.
        alfa = img.getchannel("A").point(lambda v: int(v * opacity))
        img.putalpha(alfa)
    except Exception as exc:
        if not _warned:
            _warned = True
            if callable(log):
                log("pozadie: %s sa nepodarilo nacitat (%s)" % (cesta, exc))
        return None

    # Cache cap: otherwise it would grow forever as the window is resized.
    if len(_cache) > 8:
        _cache.clear()
    _cache[kluc] = img
    return img


# --------------------------------------------------------------------------
# HERO: the same dojo, but VISIBLE and with a glow (empty state on Today)
# --------------------------------------------------------------------------
#
# `load()` above is the faint background of the whole page (opacity ~0.10).
# This is something else: while the app is not listening, the centre of the
# Today page shows the dojo fully as a "hero" and it gently BREATHES - the
# bright spots (lanterns, moon, the reflection on the floor) glow up and dim
# at the pace of an inhale. It is the only motion in that state and it goes
# away as soon as listening starts (then only the bar breathes) - two things
# never move at once.

# Brightness threshold for the bloom and the breathing limits of its
# strength. The author chose "subtle", so it breathes low: 0.35 at rest,
# 0.55 at the peak of the inhale.
_BLOOM_PRAH = 165
HERO_BLOOM_MIN = 0.35
HERO_BLOOM_MAX = 0.55
_hero_cache = {}


def _bloom(img_rgb, intensita):
    """Blurs the bright spots and adds them back = a soft glow.

    The threshold catches exactly the lanterns, the moon and the lit-up
    reflection on the floor - no need to look for them by hand. `intensita`
    (0..1) scales the strength.
    """
    polomer = max(3, img_rgb.width // 55)
    sedy = img_rgb.convert("L")
    maska = sedy.point(lambda v: 255 if v > _BLOOM_PRAH else 0)
    jasne = Image.composite(img_rgb, Image.new("RGB", img_rgb.size, (0, 0, 0)),
                            maska)
    ziara = jasne.filter(ImageFilter.GaussianBlur(polomer))
    if intensita != 1.0:
        ziara = ziara.point(lambda v: int(v * max(0.0, min(1.0, intensita))))
    return ImageChops.add(img_rgb, ziara)


_scrim_cache = {}

# Gentle blur of the photo (spec: "let the whole dojo be visible, but
# slightly blurred"). Radius = width / this - at ~780 px that is ~2.3 px.
HERO_BLUR_DELIT = 340.0


def _hex_na_rgb(h):
    h = str(h).lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _scrim_maska(width, height, peak=255):
    """Alpha mask of a soft central oval: `peak` in the centre, smoothly 0
    towards the edges. It has no HARD edge, so it leaves no rectangle behind -
    it is just a gentle darkening under the enso and the text. `peak` < 255
    lets the dojo SHOW THROUGH (a semi-transparent veil) instead of covering
    it: the enso and the text then float on the visible dojo instead of a dark
    box. The lanterns on the sides, the moon at the top and the reflection at
    the bottom stay outside it.
    """
    peak = max(0, min(255, int(peak)))
    kluc = (width, height, peak)
    m = _scrim_cache.get(kluc)
    if m is not None:
        return m
    maska = Image.new("L", (width, height), 0)
    kresli = ImageDraw.Draw(maska)
    # Oval (not a rectangle): a softer transition, zero corners, which with a
    # semi-transparent veil would start to look like a box.
    pw = min(int(width * 0.60), 520)
    ph = min(int(height * 0.66), 440)
    x0 = (width - pw) // 2
    y0 = (height - ph) // 2
    kresli.ellipse([x0, y0, x0 + pw, y0 + ph], fill=255)
    feather = max(30, int(min(width, height) * 0.11))
    maska = maska.filter(ImageFilter.GaussianBlur(feather))
    if peak < 255:
        maska = maska.point(lambda a: (a * peak) // 255)
    if len(_scrim_cache) > 16:
        _scrim_cache.clear()
    _scrim_cache[kluc] = maska
    return maska


def _pridaj_scrim(img_rgba, scrim, peak=255):
    """Pastes a soft central veil in the colour `scrim` (hex) - a gentle base
    under the enso and the text. `peak` controls the coverage: < 255 = the
    dojo shows through (transparent)."""
    try:
        rgb = _hex_na_rgb(scrim)
    except Exception:
        return img_rgba
    w, h = img_rgba.size
    vrstva = Image.new("RGBA", (w, h), rgb + (255,))
    vrstva.putalpha(_scrim_maska(w, h, peak))
    return Image.alpha_composite(img_rgba, vrstva)


def hero(width, height, breath=0.0, scrim=None, scrim_peak=255, blur=True,
         log=None):
    """The dojo as a visible hero with bloom. Returns RGBA or None.

    `breath` 0..1 controls the strength of the glow (0 = rest, 1 = peak of the
    inhale). `blur` gently blurs the photo (so it does not compete with the
    text). `scrim` (hex colour) pastes a soft central veil under the enso and
    the text - `scrim_peak` < 255 makes it SEE-THROUGH (the dojo is visible,
    no box). The result is cached by (size, breath, scrim, peak, blur), so
    breathing by alternating a few precomputed frames costs almost nothing.
    """
    if not PIL_AVAILABLE:
        return None
    try:
        width, height = int(width), int(height)
    except (TypeError, ValueError):
        return None
    if width < 2 or height < 2:
        return None
    cesta = image_path()
    if cesta is None:
        return None

    intensita = HERO_BLOOM_MIN + (HERO_BLOOM_MAX - HERO_BLOOM_MIN) * max(
        0.0, min(1.0, breath))
    kluc = (cesta, width, height, round(intensita, 2), scrim, int(scrim_peak),
            bool(blur),
            os.path.getmtime(cesta) if os.path.exists(cesta) else 0)
    hotove = _hero_cache.get(kluc)
    if hotove is not None:
        return hotove
    try:
        with Image.open(cesta) as zdroj:
            base = _orez_na_pomer(zdroj.convert("RGB"), width, height)
            base = base.resize((width, height), Image.LANCZOS)
        if blur:
            base = base.filter(ImageFilter.GaussianBlur(
                max(1.0, width / HERO_BLUR_DELIT)))
        img = _bloom(base, intensita).convert("RGBA")
        if scrim:
            img = _pridaj_scrim(img, scrim, scrim_peak)
    except Exception as exc:
        if callable(log):
            log("hero dojo: %s sa nepodarilo nacitat (%s)" % (cesta, exc))
        return None

    if len(_hero_cache) > 24:            # a few sizes x a few breath frames
        _hero_cache.clear()
    _hero_cache[kluc] = img
    return img


def _orez_na_pomer(img, width, height):
    """Centre crop to the `width:height` ratio, without changing the scale."""
    ciel = width / float(height)
    w, h = img.size
    ma = w / float(h)
    if abs(ma - ciel) < 1e-3:
        return img
    if ma > ciel:                       # source is wider - crop the sides
        nova_w = int(round(h * ciel))
        lavo = (w - nova_w) // 2
        return img.crop((lavo, 0, lavo + nova_w, h))
    nova_h = int(round(w / ciel))       # source is taller - crop top/bottom
    hore = (h - nova_h) // 2
    return img.crop((0, hore, w, hore + nova_h))


def forget():
    """Drops the cache. Call on a theme change or after swapping the file."""
    _cache.clear()
