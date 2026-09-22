# -*- coding: utf-8 -*-
"""Fotka na pozadi okna - jedno miesto, kde sa da vymenit.

AKO SA TO MENI
--------------
Chces INU FOTKU?     hod ju do `assets/images/` ako `dojo_noc.<cokolvek>`.
                     Pripona je jedno - .jpg, .jpeg, .png aj .webp.
Chces INY NAZOV?     zmen `IMAGE_NAME` nizsie. Je to jediny vyskyt v projekte.
Chces INU JEMNOST?   `background_opacity` v dandurf_settings.json, alebo
                     `DEFAULT_OPACITY` pre nove profily.
Chces to VYPNUT?     jemnost na 0, alebo subor jednoducho nedaj.

POZN: posuvnik v nastaveniach zatial NIE JE - hodnota sa meni v JSON alebo
tu v kode. Patri medzi tych pat jednoduchych ovladacov zo zadania §3.1 a
caka na rozhodnutie, ktore z nich to bude.

Ziadny volajuci nepozna nazov suboru ani cestu - vsetko ide cez `load()`.

KED SUBOR NIE JE, NIC SA NEDEJE
-------------------------------
`load()` vrati None a appka kresli ako doteraz. Je to zamerne: fotka je
ozdoba, nie sucast funkcie, a chybajuci subor nesmie zhodit okno. Zaloguje
sa to RAZ, nie pri kazdom prekresleni.

PRECO SA TO CACHUJE
-------------------
Zmensenie fotky cez LANCZOS stoji desiatky milisekund. Prekresluje sa pri
kazdej zmene velkosti a temy, takze bez cache by sa to pocitalo stale
dokola. Kluc je (sirka, vyska, jemnost) - ked sa niektore zmeni, spocita sa
nanovo.

POZN K HISTORII: vo verzii 2.0 tu bol "dojo pas" - fotka pevnej vysky NAD
titulkovou listou. Odstranil sa preto, ze to bolo 130 px mrtveho miesta,
ktore uberalo z pevnej vysky okna (app.py, `_build_ui`). Toto je nieco ine:
pozadie UZ EXISTUJUCEJ plochy, takze nezabera ani pixel navyse. Ta namietka
sa na to nevztahuje.
"""

import os

try:
    from PIL import Image, ImageChops, ImageDraw, ImageFilter
    PIL_AVAILABLE = True
except Exception:                       # pragma: no cover - bez Pillow
    Image = None
    ImageChops = None
    ImageDraw = None
    ImageFilter = None
    PIL_AVAILABLE = False

import paths

# --------------------------------------------------------------------------
# JEDINE DVE VECI, KTORE SA BEZNE MENIA
# --------------------------------------------------------------------------

# Nazov suboru v `assets/images/` BEZ PRIPONY. Jediny vyskyt v projekte.
IMAGE_NAME = "dojo_noc"

# Pripony, ktore skusame. Poradie rozhoduje, ked ich lezi vedla seba viac.
# Preco vobec zoznam: stiahnuta fotka nema vzdy priponu, ktoru cakas - prva,
# ktoru sme sem dali, prisla ako .webp a appka ju proste nenasla. Hladat
# presne jeden nazov je pasca, o ktorej sa clovek dozvie az tak, ze mu
# pozadie ostane stare a nikde nie je ziadna chyba.
EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")

# Jemnost pre nove profily, 0.0 - 1.0. Zamerne NIZKA: cely navrh appky stoji
# na tom, ze prstenec "natiahnute" zachytis kutikom oka, a periferne videnie
# reaguje na pohyb a kontrast v POKOJNOM poli. Vyrazna fotka za vsetkym je
# najucinnejsi sposob, ako to zabit.
DEFAULT_OPACITY = 0.10

# Nad tuto hodnotu sa uz neda ist ani cez nastavenia. Nie je to svojvola:
# pri vyssej hodnote prestava byt citatelny maly text v paneloch, a tych je
# devat jazykov vratane japonciny a cinstiny.
MAX_OPACITY = 0.35

# Stary pas z verzie 2.0. Nechany ako zaloha, keby si niekto pusti appku bez
# novej fotky - je to ta ista miestnost, len uzky vyrez.
FALLBACK_NAME = "dojo_band.jpg"


# --------------------------------------------------------------------------

_cache = {}
_warned = False


def image_path():
    """Cesta k fotke, alebo None ked ziadna nie je.

    Skusa `IMAGE_NAME` so vsetkymi `EXTENSIONS`, potom `FALLBACK_NAME`.
    Vsetko je v `assets/images/`, ktory oba `.spec` subory balia cely - do
    buildu netreba nic dopisovat.
    """
    try:
        base = paths.images_dir()
    except Exception:
        return None
    mena = [IMAGE_NAME + p for p in EXTENSIONS] + [FALLBACK_NAME]
    for meno in mena:
        cesta = os.path.join(base, meno)
        if os.path.exists(cesta):
            return cesta
    return None


def available():
    return PIL_AVAILABLE and image_path() is not None


def clamp_opacity(value, default=DEFAULT_OPACITY):
    """0.0 - MAX_OPACITY. Nezmysel padne na predvolenu hodnotu."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return default
    if value != value:                  # NaN
        return default
    return max(0.0, min(MAX_OPACITY, value))


def load(width, height, opacity=DEFAULT_OPACITY, log=None):
    """Fotka orezana na `width` x `height` a stlmena na `opacity`.

    Vracia RGBA obrazok, alebo None - ked nie je Pillow, nie je subor, alebo
    je jemnost nulova. Volajuci sa nikdy nemusi pytat "existuje to?",
    staci `if img is not None`.

    Orezava sa STREDOM a zachovava pomer: fotka je sirsia (16:9) nez plocha,
    na ktoru ide, takze roztiahnut ju na vysku by z nej spravilo kasu.
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
                log("pozadie: %s%s ani %s nie su v assets/images - kresli sa bez"
                    % (IMAGE_NAME, "|".join(EXTENSIONS), FALLBACK_NAME))
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
        # Stlmenie ide do ALFY, nie do jasu: cez alfu sa fotka slucuje s tym,
        # co je pod nou (pozadie temy), takze v Sumi ostane teplá a v Aizome
        # chladna. Stmavenie jasu by ju v oboch temach spravilo len sivou.
        alfa = img.getchannel("A").point(lambda v: int(v * opacity))
        img.putalpha(alfa)
    except Exception as exc:
        if not _warned:
            _warned = True
            if callable(log):
                log("pozadie: %s sa nepodarilo nacitat (%s)" % (cesta, exc))
        return None

    # Strop cache: pri zmene velkosti okna by inak rastla donekonecna.
    if len(_cache) > 8:
        _cache.clear()
    _cache[kluc] = img
    return img


# --------------------------------------------------------------------------
# HERO: to iste dojo, ale VIDITELNE a so ziarou (prazdny stav na Dnes)
# --------------------------------------------------------------------------
#
# `load()` vyssie je faint pozadie celej stranky (opacity ~0.10). Toto je nieco
# ine: kym appka nepocuva, stred stranky Dnes ukaze dojo naplno ako "hero" a
# jemne DYCHA - jasne miesta (lampiony, mesiac, odlesk na podlahe) sa
# rozziaria a stlmia v tempe nadychu. Je to jediny pohyb v tom stave a mizne,
# len co sa spusti pocuvanie (vtedy dycha uz len pas) - dve veci sa nikdy
# nehybu naraz.

# Prah jasu pre bloom a dychacie medze jeho sily. Zadavatel vybral "jemny",
# takze sa dycha nizko: v pokoji 0.35, na vrchole nadychu 0.55.
_BLOOM_PRAH = 165
HERO_BLOOM_MIN = 0.35
HERO_BLOOM_MAX = 0.55
_hero_cache = {}


def _bloom(img_rgb, intensita):
    """Jasne miesta rozostri a pripocita spat = mäkka ziara.

    Threshold chyti prave lampiony, mesiac a svetlom zaliaty odlesk na
    podlahe - netreba ich hladat rucne. `intensita` (0..1) skaluje silu.
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

# Jemne rozostrenie fotky (zadanie: "nech vidno cele dojo, ale mierne
# rozmazane"). Polomer = sirka / toto - pri ~780 px to je ~2,3 px.
HERO_BLUR_DELIT = 340.0


def _hex_na_rgb(h):
    h = str(h).lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _scrim_maska(width, height, peak=255):
    """Alfa maska mäkkeho stredoveho oválu: `peak` v strede, plynulo 0 k
    okrajom. Nema TVRDU hranu, takze po nom neostane obdlznik - je to len
    jemne stmavenie pod ensom a textom. `peak` < 255 necha dojo PRESVITAT
    (polopriehladny zavoj), nie zakryt: enso a text tak plavaju na viditelnom
    dojo namiesto tmaveho boxu. Lampiony po stranach, mesiac hore aj odlesk
    dole ostavaju mimo.
    """
    peak = max(0, min(255, int(peak)))
    kluc = (width, height, peak)
    m = _scrim_cache.get(kluc)
    if m is not None:
        return m
    maska = Image.new("L", (width, height), 0)
    kresli = ImageDraw.Draw(maska)
    # Oval (nie obdlznik): meksi prechod, nula rohov, ktore by pri
    # polopriehladnom zavoji zacali pripominat box.
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
    """Prilepi mäkky stredovy zavoj vo farbe `scrim` (hex) - jemny podklad
    pod enso a text. `peak` riadi krytie: < 255 = dojo presvita (priehladne)."""
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
    """Dojo ako viditelny hero s bloomom. Vracia RGBA alebo None.

    `breath` 0..1 riadi silu ziary (0 = pokoj, 1 = vrchol nadychu). `blur`
    fotku jemne rozostri (aby nekonkurovala textu). `scrim` (hex farba) prilepi
    mäkky stredovy zavoj pod enso a text - `scrim_peak` < 255 ho necha
    PRESVITAT (dojo vidno, ziadny box). Vysledok sa cachuje podla (velkost,
    breath, scrim, peak, blur), takze dychanie striedaním par predratanych
    snimok nestoji takmer nic.
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

    if len(_hero_cache) > 24:            # par velkosti x par snimok dychu
        _hero_cache.clear()
    _hero_cache[kluc] = img
    return img


def _orez_na_pomer(img, width, height):
    """Stredovy orez na pomer `width:height`, bez zmeny mierky."""
    ciel = width / float(height)
    w, h = img.size
    ma = w / float(h)
    if abs(ma - ciel) < 1e-3:
        return img
    if ma > ciel:                       # zdroj je sirsi - orez po stranach
        nova_w = int(round(h * ciel))
        lavo = (w - nova_w) // 2
        return img.crop((lavo, 0, lavo + nova_w, h))
    nova_h = int(round(w / ciel))       # zdroj je vyssi - orez hore/dole
    hore = (h - nova_h) // 2
    return img.crop((0, hore, w, hore + nova_h))


def forget():
    """Zahodi cache. Volat pri zmene temy alebo po vymene suboru."""
    _cache.clear()
