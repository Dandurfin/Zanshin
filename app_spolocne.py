"""Spolocne mena hlavnej appky - pre app.py aj jej mixiny (app_*.py).

Mixin DandurfApp nesmie importovat app (kruhovy import), takze co na urovni
modulu potrebuje app.py aj niektory mixin, byva tu. app.py tieto mena
importuje, preto `app.app_log`, `app.LANG_NATIVE_LABELS`,
`app.DEFAULT_SNOOZE_HOTKEY` a pod. ostavaju platne.

Pozor v testoch: `monkeypatch.setattr(app, "app_log", ...)` zasiahne len
metody v app.py - mixin cita meno zo svojho modulu.
"""

from i18n import (LANG_BG, LANG_CS, LANG_DE, LANG_EN, LANG_ES, LANG_FR,
                  LANG_JA, LANG_PT, LANG_RU, LANG_SK, LANG_ZH, STRINGS, tr)
from logging_setup import get_logger

# Pre kreslenie stredu Dnes (app_today) aj ikonu okna (app.py).
# Stred stranky Dnes je tk.Canvas: enso je priehladne PNG (`create_image`),
# preto tu treba `ImageTk`. PIL nie je tvrda zavislost - bez neho appka bezi
# dalej (canvas ostane v jednofarebnom pozadi temy).
try:
    from PIL import ImageTk as _ImageTk
except Exception:               # pragma: no cover - PIL je bezne pritomny
    _ImageTk = None

app_log = get_logger("app")


def stranka_vhre(app):
    """Meno stranky "V hre" tak, ako ho hrac prave vidi v bocnom paneli
    (0.2.2 davka 4b) - pre texty s `{page}`, ktore na tu stranku posielaju
    (port, obrazky, prazdna Historia, hranica vysokeho tepu).

    Vo svete Praca sa stranka vola "Obrazovka" (`TodayMixin._nazov_vhre`).
    Atrapy v testoch tu metodu nemaju - vtedy plati meno z Hry."""
    nazov = getattr(app, "_nazov_vhre", None)
    if callable(nazov):
        try:
            return nazov()
        except Exception:
            app_log.exception("meno stranky V hre sa nepodarilo zistit")
    return tr("nav.vhre_short")


def zapamataj_text_stranky(app, widget, kluc):
    """Stitok s textom `kluc`, ktory menuje stranku "V hre" (`{page}`) a
    stavia sa RAZ (vysvetlivka metriky v Historii). Svet sa prepina bez
    prestavby okna (`set_world`), takze by inak ostal s menom stranky z
    druheho sveta - `obnov_texty_stranky` ho po prepnuti prepise.

    Pamata si len texty, ktore `{page}` naozaj maju (inak by zoznam rastol
    s kazdou vysvetlivkou). Atrapy bez `__dict__` sa preskocia."""
    zaznam = STRINGS.get(kluc) or {}
    if widget is None or "{page}" not in zaznam.get("en", ""):
        return
    try:
        app.__dict__.setdefault("_texty_so_strankou", []).append((widget, kluc))
    except AttributeError:
        pass


def obnov_texty_stranky(app):
    """Prepise zapamatane texty s `{page}` menom stranky v aktualnom svete.
    Stitok, ktory uz neexistuje (prestavba stranky), sa zo zoznamu zahodi.
    Nikdy nevyhodi vynimku."""
    stranka = stranka_vhre(app)
    zive = []
    for widget, kluc in list(getattr(app, "_texty_so_strankou", None) or ()):
        try:
            if not widget.winfo_exists():
                continue
            widget.configure(text=tr(kluc, page=stranka))
            zive.append((widget, kluc))
        except Exception:
            pass
    try:
        app._texty_so_strankou = zive
    except AttributeError:
        pass


# Natívne nazvy jazykov pre prepinac (Nastavenia) - VZDY vo vlastnom
# jazyku, bez ohladu na aktualne zvoleny jazyk rozhrania, aby si
# pouzivatel svoj jazyk nasiel aj vtedy, ked mu je zobrazeny jazyk
# nezrozumitelny.
LANG_NATIVE_LABELS = {
    LANG_SK: "Slovenčina",
    LANG_EN: "English",
    LANG_JA: "日本語",
    LANG_ZH: "简体中文",
    LANG_RU: "Русский",
    LANG_ES: "Español",
    LANG_DE: "Deutsch",
    LANG_FR: "Français",
    LANG_PT: "Português (BR)",
    LANG_CS: "Čeština",
    LANG_BG: "Български",
}
LABEL_TO_LANG = {v: k for k, v in LANG_NATIVE_LABELS.items()}


# "Teraz nie" (zadanie §1.9). Ctrl+Alt+Z zamerne: Z sa v hrach takmer
# nepouziva s obidvoma modifikatormi naraz, takze riziko zrazky s hernou
# vazbou je male. Prazdny retazec hotkey vypina.
DEFAULT_SNOOZE_HOTKEY = "ctrl+alt+z"
# Zadanie: jeden klaves stisi appku na 30 minut.
SNOOZE_HOTKEY_MINUTES = 30
