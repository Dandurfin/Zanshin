"""Spolocne mena hlavnej appky - pre app.py aj jej mixiny (app_*.py).

Mixin DandurfApp nesmie importovat app (kruhovy import), takze co na urovni
modulu potrebuje app.py aj niektory mixin, byva tu. app.py tieto mena
importuje, preto `app.app_log`, `app.LANG_NATIVE_LABELS`,
`app.DEFAULT_SNOOZE_HOTKEY` a pod. ostavaju platne.

Pozor v testoch: `monkeypatch.setattr(app, "app_log", ...)` zasiahne len
metody v app.py - mixin cita meno zo svojho modulu.
"""

from i18n import (LANG_BG, LANG_CS, LANG_DE, LANG_EN, LANG_ES, LANG_FR,
                  LANG_JA, LANG_PT, LANG_RU, LANG_SK, LANG_ZH)
from logging_setup import get_logger

app_log = get_logger("app")

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
