"""Spolocne mena hlavnej appky - pre app.py aj jej mixiny (app_*.py).

Mixin DandurfApp nesmie importovat app (kruhovy import), takze co na urovni
modulu potrebuje app.py aj niektory mixin, byva tu. app.py tieto mena
importuje, preto `app.app_log` a pod. ostavaju platne.

Pozor v testoch: `monkeypatch.setattr(app, "app_log", ...)` zasiahne len
metody v app.py - mixin cita meno zo svojho modulu.
"""

from logging_setup import get_logger

app_log = get_logger("app")
