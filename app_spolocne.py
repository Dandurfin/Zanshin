"""Shared names of the main app - for app.py and its mixins (app_*.py).

A DandurfApp mixin must not import app (circular import), so whatever
both app.py and some mixin need at module level lives here. app.py
imports these names, so `app.app_log`, `app.LANG_NATIVE_LABELS`,
`app.DEFAULT_SNOOZE_HOTKEY` etc. stay valid.

Careful in tests: `monkeypatch.setattr(app, "app_log", ...)` only affects
the methods in app.py - a mixin reads the name from its own module.
"""

from i18n import (LANG_BG, LANG_CS, LANG_DE, LANG_EN, LANG_ES, LANG_FR,
                  LANG_JA, LANG_PT, LANG_RU, LANG_SK, LANG_ZH, STRINGS, tr)
from logging_setup import get_logger

# For drawing the centre of Today (app_today) and the window icon (app.py).
# The centre of the Today page is a tk.Canvas: the enso is a transparent
# PNG (`create_image`), hence `ImageTk` is needed here. PIL is not a hard
# dependency - without it the app keeps running (the canvas stays on the
# theme's single-colour background).
try:
    from PIL import ImageTk as _ImageTk
except Exception:               # pragma: no cover - PIL is normally present
    _ImageTk = None

app_log = get_logger("app")


def stranka_vhre(app):
    """Name of the "In-game" page as the player currently sees it in the
    side panel (0.3 batch 4b) - for texts with `{page}` that send the
    player to that page (port, pictures, empty History, the high heart
    rate limit).

    In the Work world the page is called "Screen"
    (`TodayMixin._nazov_vhre`). Test dummies do not have this method -
    then the name from Play applies."""
    nazov = getattr(app, "_nazov_vhre", None)
    if callable(nazov):
        try:
            return nazov()
        except Exception:
            app_log.exception("meno stranky V hre sa nepodarilo zistit")
    return tr("nav.vhre_short")


def zapamataj_text_stranky(app, widget, kluc):
    """A label with the text `kluc` that names the "In-game" page (`{page}`)
    and is built ONCE (a metric's explanation in History). The world is
    switched without rebuilding the window (`set_world`), so it would
    otherwise keep the page name from the other world -
    `obnov_texty_stranky` rewrites it after the switch.

    It remembers only texts that really contain `{page}` (otherwise the
    list would grow with every explanation). Dummies without `__dict__`
    are skipped."""
    zaznam = STRINGS.get(kluc) or {}
    if widget is None or "{page}" not in zaznam.get("en", ""):
        return
    try:
        app.__dict__.setdefault("_texty_so_strankou", []).append((widget, kluc))
    except AttributeError:
        pass


def obnov_texty_stranky(app):
    """Rewrites the remembered texts with `{page}` to the page name in the
    current world. A label that no longer exists (page rebuild) is
    dropped from the list. Never raises an exception."""
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


# Native language names for the switch (Settings) - ALWAYS in the language
# itself, regardless of the currently chosen UI language, so the user can
# find their language even when the displayed language is unintelligible
# to them.
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


# "Teraz nie" (Not now) (spec §1.9). Ctrl+Alt+Z on purpose: in games Z is
# hardly ever used with both modifiers at once, so the risk of a clash
# with a game binding is small. An empty string disables the hotkey.
DEFAULT_SNOOZE_HOTKEY = "ctrl+alt+z"
# Spec: one key mutes the app for 30 minutes.
SNOOZE_HOTKEY_MINUTES = 30
