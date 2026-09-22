"""Ci hrac prave nieco robi - bez klavesoveho hooku.

PRECO NIE PYNPUT
----------------
Appka doteraz pocuvala klavesnicu globalnym hookom (`pynput`,
`WH_KEYBOARD_LL`), lebo klavesy boli spustacom hlasok. To je jedina cast
appky, ktora navonok vyzera ako keylogger - a na platforme, kde ludia
beziu Vanguard, EAC a BattlEye, je to zbytocne drahe.

`GetLastInputInfo` je Win32 funkcia, ktora vracia JEDINE cislo: kolko
milisekund uplynulo od posledneho vstupu. Neprezradi, ktora klavesa to
bola, ani ci to klavesa vobec bola. Ziadny hook sa neinstaluje, takze
appke nemoze pritiect ani jeden znak z toho, co hrac pise.

Z toho jedneho cisla sa da odvodit vsetko, co novy rezim potrebuje:
  * ci je hrac prave aktivny,
  * kedy nastala pauza (zlomovy bod na dorucenie hlasky),
  * hrube tempo aktivity ako tretí kanal k tepu.

GAMEPAD - ODMERANE, VIDI HO
---------------------------
Povodne tu stalo, ze GetLastInputInfo gamepad nesleduje (klasicky argument:
preto nabieha setric obrazovky, ked sa hra na ovladaci). Na tomto Windowse
11 to NEPLATI. Odmerane 14. 9. 2026, tri behy, viz interne poznamky:

  DualSense cez HID, G7 Pro cez XInput, Steam zapnuty aj vypnuty:
  idle pri pohybe ovladaca medianovo 15-16 ms, kym v kludovych usekoch
  vyskocilo na 50-65 sekund. Kurzor sa nepohol ani raz z 348 vzoriek,
  takze to nerobi ani Steam Input, ani gyroskop mapovany na mys.

Zasuvka `extra_idle_fn` napriek tomu ostava a NIE JE mrtva: je to jeden
pocitac. Keby sa na inom stroji ukazalo, ze tam gamepad videny nie je,
hrac by bol pre appku trvale necinny - a to je tiche zlyhanie, ktore sa
neprejavi ako chyba, len ako appka, ktora mlci alebo sa ozyva v najhorsej
chvili. Vysledne idle je MINIMUM zo vsetkych zdrojov, cize "od posledneho
vstupu ODKIALKOLVEK".

Modul nema Tk ani I/O. `idle_ms()` sa da v testoch nahradit, takze cela
logika sa da overit bez displeja a bez toho, aby test cakal v realnom case.
"""

import time

# Ako casto sa pyta Windowsu. 4x za sekundu staci na to, aby sa pauza
# dlha 2,5 s dala rozpoznat s presnostou na stvrtinu sekundy, a je to
# dost lacne na to, aby to mohlo bezat cele hranie.
POLL_S = 0.25

# Do zaznamu pre meracie okna staci 1x za sekundu - rovnaka hustota ako
# tep z hodiniek. 4 Hz by za styri hodiny narastlo na ~58k dvojic.
LOG_EVERY_S = 1.0

# Pod tolko ms od posledneho vstupu = hrac prave nieco robi.
ACTIVE_IDLE_MS = 1000

# Strop zaznamu. Pri 1 Hz je to ~16 hodin, cize dlhsie nez akakolvek
# relacia - ale zabrani tomu, aby appka nechana bezat cez vikend zrala
# pamat donekonecna. Pri zapnuti senzora sa zaznam aj tak vynuluje.
MAX_SAMPLES = 60000

# --------------------------------------------------------------------------
# Z COHO HRAC PRAVE HRA
# --------------------------------------------------------------------------
# Appka o vstupe vie dve veci naraz: `GetLastInputInfo` (vidi VSETKO vratane
# ovladaca, viz interne poznamky) a hlasenia z `gamepad.py` (vidi LEN
# ovladac). Z prieniku sa da odvodit trieda zariadenia:
#
#   ovladac hlasi cerstvy vstup            -> ovladac
#   ovladac mlci, ale system hlasi vstup   -> klavesnica/mys
#   gamepad listener vobec nebezi          -> NEVIEME (nie "klavesnica"!)
#
# Posledny riadok je dolezity: keby sa "neviem" hlasilo ako klavesnica, na
# stroji s vypnutym listenerom by appka hracovi s ovladacom tvrdila nieco
# nepravdive - a bolo by to napisane na obrazovke, cize by tomu veril.
#
# Zisti sa TRIEDA ZARIADENIA, nic viac. Ktore tlacidlo to bolo sa appka
# nedozvie ani tu (`note_external_input` meno nepreberá), ani z
# `GetLastInputInfo`, ktory vracia jedine pocet milisekund.
SRC_PAD = "pad"
SRC_KB = "kb"

# Ako dlho sa zdroj pamata, ked hrac prestane hrat. Bez toho by piktogram
# pri kazdej prestavke zhasol a pri kazdom stlaceni sa rozsvietil - a to je
# presne ten "putujuci pohyb", ktory sa v periferii vsimne najhorsie.
SOURCE_MEMORY_S = 300.0


# --------------------------------------------------------------------------
# Win32 - jedina vec, ktora sa pyta operacneho systemu
# --------------------------------------------------------------------------

def _make_idle_reader():
    """Vrati funkciu idle_ms(), alebo None ked to na tomto systeme nejde.

    Oddelene od zvysku kvoli testom aj kvoli tomu, ze modul sa musi dat
    importovat aj tam, kde ziadny user32 nie je (CI, ine OS) - inak by
    padol import celej appky.
    """
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]

        user32.GetLastInputInfo.argtypes = [ctypes.POINTER(LASTINPUTINFO)]
        user32.GetLastInputInfo.restype = wintypes.BOOL
        kernel32.GetTickCount.restype = wintypes.DWORD

        info = LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(info)

        def idle_ms():
            if not user32.GetLastInputInfo(ctypes.byref(info)):
                return None
            # GetTickCount je 32-bitovy a pretoci sa po ~49 dnoch;
            # maskovanie do 32 bitov drzi rozdiel spravny aj cez pretocenie.
            return (kernel32.GetTickCount() - info.dwTime) & 0xFFFFFFFF

        idle_ms()          # over, ze to naozaj ide, nie az pocas hrania
        return idle_ms
    except Exception:
        return None


_SYSTEM_IDLE = _make_idle_reader()
AVAILABLE = _SYSTEM_IDLE is not None


def idle_ms():
    """Ms od posledneho vstupu, alebo None ked to system nevie povedat."""
    return _SYSTEM_IDLE() if _SYSTEM_IDLE else None


# --------------------------------------------------------------------------
# Sledovanie aktivity pocas relacie
# --------------------------------------------------------------------------

class ActivityTracker:
    """Drzi, ci je hrac aktivny, ako dlho trva pauza a zaznam pre okna.

    Vola sa VYHRADNE z GUI vlakna (z `_tick_activity`), rovnako ako
    `HeartStats` - preto tu nie je ziadny zamok.
    """

    def __init__(self, idle_fn=None, extra_idle_fn=None, clock=time.time):
        self._idle_fn = idle_fn if idle_fn is not None else idle_ms
        self._extra_idle_fn = extra_idle_fn
        self._clock = clock
        # Bezi gamepad listener? Kym nebezi, trieda zariadenia sa urcit
        # NEDA - viz hlavicka modulu. Zapina to appka pri `gamepad.start()`.
        self._gamepad_watched = False
        self.reset_session()

    def set_gamepad_watched(self, watched):
        """Appka hlasi, ci gamepad listener naozaj bezi.

        Bez toho by sa "ziadne hlasenie z ovladaca" nedalo odlisit od
        "ovladac nikto nesleduje" a appka by hracovi s ovladacom napisala,
        ze hra na klavesnici.
        """
        self._gamepad_watched = bool(watched)
        if not self._gamepad_watched:
            self._source = None
            self._source_at = None

    # ---------- relacia ----------

    def reset_session(self):
        self.samples = []           # [(timestamp, idle_ms)] ~1x za sekundu
        self.last_idle = None
        self.active_since = None
        self.pause_since = None
        self._last_log_ts = None
        self._external_at = None    # kedy naposledy hlasil vstup iny zdroj
        # Trieda zariadenia, nie konkretny vstup. Viz hlavicka modulu.
        self._source = None
        self._source_at = None

    def note_external_input(self, now=None):
        """Iny zdroj hlasi vstup PRAVE TERAZ (napr. tlacidlo na ovladaci).

        Nezapisuje sa CO to bolo - len ze sa nieco stalo. `gamepad.py` sem
        posiela stlacenia tlacidiel od fazy 3, kedy prestal byt spustacom
        hlasok a stal sa druhym zdrojom informacie o aktivite.
        """
        now = self._clock() if now is None else now
        self._external_at = now

    def set_extra_source(self, fn):
        """Pripoji druhy zdroj aktivity (napr. gamepad).

        `fn()` vracia ms od posledneho vstupu z toho zdroja, alebo None.
        Vysledne idle je minimum zo vsetkych zdrojov.
        """
        self._extra_idle_fn = fn

    # ---------- zber ----------

    def poll(self, now=None):
        """Jedno odmeranie. Vracia aktualne idle v ms (alebo None).

        Zaznam do `samples` sa robi len raz za `LOG_EVERY_S`, hoci sa
        pyta 4x castejsie - castejsie vzorkovanie treba na rozpoznanie
        pauzy, nie do suboru.
        """
        now = self._clock() if now is None else now
        idle = self._idle_fn()
        if self._extra_idle_fn is not None:
            try:
                extra = self._extra_idle_fn()
            except Exception:
                extra = None
            if extra is not None:
                idle = extra if idle is None else min(idle, extra)

        # Vstup ohlaseny inym zdrojom (gamepad) sa zapocita ako "prave
        # teraz nieco bolo" - berie sa to najcerstvejsie z oboch.
        if self._external_at is not None:
            vonkajsie = max(0.0, (now - self._external_at) * 1000.0)
            idle = vonkajsie if idle is None else min(idle, vonkajsie)

        self.last_idle = idle
        self._urci_zdroj(now, idle)

        if idle is not None:
            if idle < ACTIVE_IDLE_MS:
                # hrac prave nieco robi
                if self.active_since is None:
                    self.active_since = now
                self.pause_since = None
            else:
                # pauza zacala v momente posledneho vstupu, nie teraz
                if self.pause_since is None:
                    self.pause_since = now - idle / 1000.0
                self.active_since = None

        if self._last_log_ts is None or now - self._last_log_ts >= LOG_EVERY_S:
            self.samples.append((now, idle))
            self._last_log_ts = now
            if len(self.samples) > MAX_SAMPLES:
                del self.samples[:len(self.samples) - MAX_SAMPLES]
        return idle

    # ---------- z coho hrac hra ----------

    def _urci_zdroj(self, now, idle):
        """Trieda zariadenia z prieniku dvoch zdrojov. Viz hlavicka modulu."""
        if not self._gamepad_watched:
            return
        if idle is None or idle >= ACTIVE_IDLE_MS:
            return                  # prave sa nic nedeje, zdroj sa nemeni
        cerstvy_pad = (self._external_at is not None
                       and (now - self._external_at) * 1000.0 < ACTIVE_IDLE_MS)
        self._source = SRC_PAD if cerstvy_pad else SRC_KB
        self._source_at = now

    def source(self, now=None):
        """SRC_PAD / SRC_KB, alebo None ked sa to povedat neda.

        None znamena NEVIEME, nie "ziadny vstup": gamepad listener nemusi
        bezat, alebo hrac este nic nestlacil. Volajuci ma vtedy mlcat, nie
        hadat - je to udaj, ktory ide na obrazovku a hrac mu bude verit.
        """
        if self._source is None or self._source_at is None:
            return None
        now = self._clock() if now is None else now
        if now - self._source_at > SOURCE_MEMORY_S:
            return None
        return self._source

    # ---------- odvodene ----------

    @property
    def is_active(self):
        return self.last_idle is not None and self.last_idle < ACTIVE_IDLE_MS

    def pause_s(self, now=None):
        """Ako dlho uz trva sucasna pauza.

        0.0 = hrac prave nieco robi.
        None = NEVIEME - system idle nehlasi (iny OS, zlyhane user32).

        Rozdiel medzi nulou a None je podstatny. Faza 2 odklada hlasku na
        pauzu; keby sa "neviem" tvarilo ako "ziadna pauza", tak by na
        stroji bez idle nikdy nenastala a VSETKY hlasky by spadli do vetvy
        "pauza neprisla" - cize by sa doruceli ticho a tiche kontrolne
        rameno by sa zmiesalo s nimi. Meranie by vyslo bez jedinej hlasnej
        hlasky a nikto by nevedel preco.
        """
        if self.last_idle is None:
            return None
        if self.pause_since is None:
            return 0.0
        now = self._clock() if now is None else now
        return max(0.0, now - self.pause_since)

    def active_share(self, t0, t1):
        """Podiel casu <t0,t1>, v ktorom bol hrac aktivny (0.0-1.0).

        To iste, co `measure.active_share` - tu ako pohodlie nad vlastnym
        zaznamom, aby volajuci nemusel siahat na `samples`.
        """
        inside = [idle for ts, idle in self.samples if t0 <= ts <= t1]
        if not inside:
            return None
        active = sum(1 for idle in inside if idle is not None and idle < ACTIVE_IDLE_MS)
        return active / float(len(inside))
