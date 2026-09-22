"""Volitelna Steamworks vrstva - appka bezi rovnako aj bez nej.

Preco takto
-----------
Zanshin sa da vydat na Steam BEZ Steamworks SDK: hru staci spustit a Steam
si herny cas zrata sam. SDK je potrebne az na achievementy alebo Rich
Presence, co alpha nepotrebuje. Tento modul preto NIC nevyzaduje - ak
`steamworks` (alebo iny binding) chyba, cely modul sa ticho prepne do
"vypnuteho" rezimu a appka o nom ani nevie.

Vsetky verejne funkcie su preto bezpecne volat vzdy: ked SDK nie je,
jednoducho nic neurobia a vratia rozumnu predvolenu hodnotu. Ziadny import
Steamu na urovni modulu, ziadna vynimka smerom von - presne ako pri
volitelnych zavislostiach uz v appke (pystray/PIL v app.py).

Ako to zapnut
-------------
1. `pip install steamworks` (alebo iny binding, ktory ma metody nizsie)
2. vedla .exe daj `steam_appid.txt` s App ID (len pocas vyvoja)
3. appka pri starte zavola `steam.init()` - ak sa podari, `steam.enabled`
   je True; ak nie, bezi dalej bez neho

Toto je zamerne TENKA vrstva. Nerobi nic, co by menilo spravanie appky -
len sprostredkuje herny stav Steamu, ak je pritomny.
"""

import os
import sys

from logging_setup import get_logger

log = get_logger("steam")


class _SteamState:
    """Drzi jedinu instanciu klienta a stav. Cez modul-level `steam`
    sa k nej pristupuje z celej appky."""

    def __init__(self):
        self.enabled = False
        self.app_id = None
        self._client = None
        self._init_tried = False

    # ---------- inicializacia ----------

    def init(self):
        """Skusi nadviazat spojenie so Steamom. Bezpecne volat vzdy -
        ak SDK/Steam nie je, len nastavi enabled=False a vrati False.

        Vola sa raz pri starte appky (z DandurfApp.__init__ pod ochranou
        try/except, rovnako ako setup_tray)."""
        if self._init_tried:
            return self.enabled
        self._init_tried = True

        # bez App ID nema zmysel skusat - ani vyvojovy steam_appid.txt,
        # ani env premenna. Ticho vypneme.
        self.app_id = self._discover_app_id()
        if not self.app_id:
            log.info("Steam: bez App ID (steam_appid.txt ani SteamAppId) - vypnute")
            return False

        try:
            client = self._load_client()
        except Exception as exc:
            log.info("Steam: SDK sa nepodarilo nacitat (%s) - appka bezi bez neho", exc)
            return False
        if client is None:
            log.info("Steam: ziadny podporovany binding - appka bezi bez neho")
            return False

        try:
            if not client.initialize():
                log.info("Steam: klient sa neinicializoval (Steam nebezi?) - vypnute")
                return False
        except Exception as exc:
            log.info("Steam: init zlyhal (%s) - appka bezi bez neho", exc)
            return False

        self._client = client
        self.enabled = True
        log.info("Steam: pripojene (App ID %s)", self.app_id)
        return True

    def _discover_app_id(self):
        # 1) vyvojovy subor vedla .exe / main.py
        for base in (os.path.dirname(sys.executable) if getattr(sys, "frozen", False)
                     else os.path.dirname(os.path.abspath(__file__)),):
            path = os.path.join(base, "steam_appid.txt")
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as fh:
                        value = fh.read().strip()
                    if value.isdigit():
                        return value
                except Exception:
                    pass
        # 2) env premenna (Steam ju nastavuje pri spusteni z kniznice)
        env = os.environ.get("SteamAppId") or os.environ.get("STEAM_APPID")
        if env and env.isdigit():
            return env
        return None

    def _load_client(self):
        """Vrati objekt s .initialize()/.shutdown()/... alebo None.

        Podporovane su bindingy s beznym rozhranim; ak pouzivas iny, staci
        sem pridat vetvu, ktora ho obali do rovnakych metod. Zamerne
        nedovazujeme ziadny konkretny balik natvrdo."""
        try:
            from steamworks import STEAMWORKS
        except Exception:
            return None

        class _Adapter:
            def __init__(self):
                self._sw = STEAMWORKS()

            def initialize(self):
                self._sw.initialize()
                return True

            def shutdown(self):
                try:
                    self._sw.unload()
                except Exception:
                    pass

            def run_callbacks(self):
                try:
                    self._sw.run_callbacks()
                except Exception:
                    pass

            def set_rich_presence(self, key, value):
                try:
                    self._sw.Friends.SetRichPresence(key, value)
                except Exception:
                    pass

        return _Adapter()

    # ---------- verejne API (bezpecne volat vzdy) ----------

    def run_callbacks(self):
        """Steam callbacky treba pumpovat periodicky. Ked je vypnute,
        nerobi nic. Vola sa z rovnakeho sekundoveho tiku ako session
        v DandurfApp."""
        if self.enabled and self._client is not None:
            self._client.run_callbacks()

    def set_status(self, listening):
        """Rich Presence: 'pocuva' / 'zastavene'. Bez SDK ticho nic.

        Text sa NEBERIE z i18n zamerne - Rich Presence je v Steam UI a
        Steam si spravuje vlastnu lokalizaciu cez klucove tokeny; sem
        posielame len stabilny stavovy retazec."""
        if not self.enabled or self._client is None:
            return
        self._client.set_rich_presence(
            "steam_display", "#Status_Listening" if listening else "#Status_Idle")

    def shutdown(self):
        if self.enabled and self._client is not None:
            self._client.shutdown()
        self.enabled = False


# Jedina instancia pre celu appku.
steam = _SteamState()
