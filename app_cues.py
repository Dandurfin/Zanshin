"""Spustac hlasky a styl hlasky - cast hlavnej appky (DandurfApp z app.py).

CuesMixin je mixin DandurfApp: app.py ho dedi a cely stav (automat
`trigger.CueTrigger`, stupen rebrika a styl hlasky relacie, texty na Dnes)
zije na DandurfApp. Tu su len metody, ktore s nim pracuju cez `self` -
mixin nema __init__ ani vlastne atributy.

Presunute z app.py bez zmeny:
  * automaticky spustac hlasky (faza 2) - zrusenie natiahnutia, stav v
    dychajucom pase a v strede Dnes, riadok "naposledy sa ozvala", podiel
    tichych hlasok a stupen rebrika pre novu relaciu,
  * styl hlasky (onboarding krok 5, Nastavenia -> Zvuk) - prva cast
    sekcie: popisky a volba stylu. Kreslenie stredu Dnes, ktore v app.py
    stalo pod tou istou znackou, je v app_today.py.

Dorucenie hlasky (`_tick_cue_trigger`, `_on_cue_event`,
`_fire_somatic_cue`) je v app_today.py.

Pozor v testoch: `_refresh_last_cue` cita `time` z tohto modulu - falosne
hodiny treba podstrcit aj tu (`app_cues.time`), nie len na module app.
"""

import time

import data_io
import hr_stats
import rebrik
import trigger
from i18n import tr
from ui_dialogs import CUE_STYLE_LABELS

from app_spolocne import app_log


class CuesMixin:
    """Spustac hlasky, rebrik a styl hlasky (mixin DandurfApp)."""

    # ---------- automaticky spustac hlasky (faza 2) ----------

    def _suspend_cue_trigger(self, reason):
        """Zrusi natiahnutie. Volat pri vypadku tepu aj pri snooze -
        polovicne natiahnuty stav neexistuje, 90 s sa pocita odznova."""
        try:
            udalost = self.cue_trigger.suspend(reason)
        except Exception:
            app_log.exception("spustac hlasky: suspend zlyhal")
            return
        if udalost is not None:
            self._on_cue_event(udalost)
        # `suspend` vrati udalost LEN ked bol automat natiahnuty; ked nebol,
        # vrati None a `_on_cue_event` sa nezavola. Prstenec sa preto zhadzuje
        # tu, nie tam - inak by po snooze v nenatiahnutom stave ostal svietit.
        self._set_enso_armed(False)

    def _kamae_state_text(self):
        """(nadpis, podtitulok) pre dychajuci pas - TRI stavy, nie dva.

        Zadanie posuva tazisko stranky Dnes z cisel na stav, a "natiahnute"
        je stav, ktory sa doteraz nedal precitat nikde inak nez z prstenca na
        ense - a ten ma 68 px. Pas je najvacsi prvok okna, takze vetu, ktora
        povie PRECO sa nic nedeje, unesie prave on.

        Zamerne bez odpoctu ("zostava 47 s"). Merat hracovi vlastny stav pred
        ocami je presne to, co ma appka nerobit; veta hovori, ze sa caka, a
        to staci.
        """
        if not self.listening:
            return self._kamae_zastavene()
        # STVRTY STAV: pocuvam, ale nemam z coho.
        #
        # Bez zdroja tepu `start_listening` prijem vobec nespusti a
        # `_tick_cue_trigger` sa hned vracia - appka teda naozaj nesleduje
        # nic. Pas pritom hlasil "Sledujem tep a cakam na spravnu chvilu",
        # cize vetu, ktora nebola pravdiva. Hrac isiel hrat s tym, ze appka
        # bezi, a cely vecer cakal na hlasku, ktora nemala odkial prist.
        if not self.hr_monitoring_enabled:
            return tr("kamae.no_watch"), tr("kamae.no_watch_sub")
        # POCUVAM, ALE TEP NECHODI.
        #
        # Doteraz sa tu vratilo "Sledujem tep a cakam..." len na zaklade
        # prepinaca - aj ked hodinky vypadli, port bol obsadeny alebo sa este
        # nic nepripojilo. Pas je najvacsi prvok okna; tvrdit na nom
        # "sledujem", ked appka nema z coho, je presne ten bug, co sa uz raz
        # opravoval pre vypnuty senzor. Pravda podla STAVU SPOJENIA, nie
        # prepinaca: naozaj sledujeme, len ked chodi tep.
        if self._hr_state != "connected" or self._hr_last_bpm is None:
            # Nadpis "Cakam na tep" plati aj pri vypadku. Veta pod nim nie:
            # "z hodiniek zatial nic nechodi" patri pred prvu vzorku, nie
            # doprostred vecera, ked tep chodil a prestal.
            if getattr(self, "_hr_lost", False):
                return tr("kamae.no_hr"), tr("kamae.lost_sub")
            return tr("kamae.no_hr"), tr("kamae.no_hr_sub")
        # "TERAZ NIE" (24. 9.): pocuva a meria sa dalej, ale hlaska neprijde.
        # "Cakam na spravnu chvilu" by slubovalo presne to, co hrac vypol.
        if getattr(self, "_snooze_job", None) is not None:
            return tr("kamae.snoozed"), tr("kamae.snoozed_sub",
                                           until=self._snooze_do())
        if self._cue_armed:
            return tr("kamae.armed"), tr("kamae.armed_sub")
        # Rebrik hlasky je na pauze (`rebrik.py`): "cakam na spravnu chvilu"
        # by slubovalo hlasku, ktora v tejto relacii neprijde.
        if (getattr(self, "_hr_session_open", False)
                and getattr(self, "_cue_rung", None) == rebrik.PAUZA):
            return tr("kamae.running"), tr("kamae.paused_sub")
        return tr("kamae.running"), tr("kamae.running_sub")

    def _refresh_kamae_state_text(self):
        """Prepise pas, ked sa stav zmenil. Vola sa zo `_set_enso_armed`,
        cize z tej istej cesty ako prstenec - aby sa text a znacka nemohli
        rozist."""
        bar = getattr(self, "kamae", None)
        if bar is None:
            return
        try:
            # Pas nesie stav POHYBOM (dycha/stoji), nie textom - preto staticka
            # napoveda o vypinaci; samotny stav (Zastavene/Pocuvam/...) je v strede
            # stranky (hero), aby sa neduplikoval. Viz KamaeBar docstring.
            bar.set_texts(tr("kamae.bar_title"), tr("kamae.bar_sub"))
        except Exception:
            app_log.exception("dychajuci pas: prepis textu zlyhal")
        self._refresh_dnes_state_text()

    def _refresh_last_cue(self):
        """Riadok "naposledy sa ozvala pred X min".

        Kym v relacii nic nebolo, riadok sa NEZOBRAZI. Prazdny riadok s
        nulou by bol pocitadlo a appka ma ukazovat stav, nie skore.
        """
        if not hasattr(self, "dnes_canvas"):
            return
        cues = getattr(self.hr_stats, "cues", None) or []
        if not cues or not self.listening:
            if getattr(self, "_dnes_lastcue_text", ""):
                self._dnes_lastcue_text = ""
                self._refresh_dnes_backdrop(force=False)
            return
        posledna = cues[-1]
        # Popisok berieme z toho isteho slotu, z akeho ho berie
        # `_fire_somatic_cue` - podla atributu, nie podla poradia v zozname.
        slot = next((sl for sl in self.slots if sl.index == self.CUE_SLOT_INDEX), None)
        label = ((slot.text_value if slot is not None else "") or "").strip()
        minut = int(max(0.0, time.time() - float(posledna["ts"])) // 60)
        text = (tr("dnes.lastcue_now", label=label) if minut < 1
                else tr("dnes.lastcue", min=minut, label=label))
        if text != getattr(self, "_dnes_lastcue_text", ""):
            self._dnes_lastcue_text = text
            self._refresh_dnes_backdrop(force=False)

    def _silent_share_for_next_session(self):
        """Podiel tichych hlasok pre najblizsiu relaciu.

        Tiche rameno je JEDINY pevny bod merania - bez neho vyjde "funguje"
        vzdy, aj keby appka mlcala, lebo tep sa vracia dole aj sam. Preto sa
        nula neberie ako hodnota, ale ako nedopatrenie, a prepise sa.

        Presne to sa aj dialo: dialog ladenia sa predvyplnal zo
        `cue_trigger.silent_share`, co je pred prvou relaciou 0.0. Kto ho
        otvoril a dal Ulozit bez toho, aby na to pole siahol, vypol tiche
        rameno na cely beh appky a nikde o tom nebolo ani slovo.

        Kto ho naozaj chce vypnut, ma na to vyvojarsku vrstvu a uvidi tam
        varovanie - ale musi to urobit vedome.
        """
        podiel = getattr(self, "_dev_silent_share", None)
        try:
            podiel = float(podiel) if podiel is not None else None
        except (TypeError, ValueError):
            podiel = None
        if not podiel:                  # None aj 0.0
            # Len VLASTNE relacie: importovane (cudzie telo) by inak posunuli
            # pocitadlo - import 15 relacii by ukoncil fazu, v ktorej tiche
            # rameno mlci castejsie (1/4), skor nez sa tvoje telo porovnalo.
            podiel = trigger.silent_share_for(
                len(data_io.vlastne(self._history_sessions())))
        return podiel

    def _urci_stupen_hlasky(self):
        """REBRIK HLASKY (0.2, `rebrik.py`): stupen pre relaciu, ktora sa
        prave otvara. Vola ju `_open_hr_session`, az ked je svet opecateny.

        Vrchol dava svet (praca = len obraz, B3-worlds - svet sa tu nepocita
        znova, berie sa opecateny `_session_world`) a styl, ktory si hrac
        vybral (`cue_style`); rebrik ide len pod neho. Styl aj stupen platia
        pre celu relaciu, rovnako ako svet.

        Ked vyhodnotenie zlyha, relacia ide len obrazom: radsej tichsie nez
        hlas, ktory mal byt stiseny.
        """
        self._cue_style_rel = rebrik.normalize_cue_style(
            getattr(self, "cue_style", None))
        svet = getattr(self, "_session_world", hr_stats.WORLD_DEFAULT)
        try:
            stav = rebrik.stupen(
                hr_stats.sessions_in_world(self._history_sessions(), svet),
                svet=svet, styl=self._cue_style_rel)
        except Exception:
            app_log.exception("rebrik hlasky: vyhodnotenie zlyhalo")
            stav = {"stupen": rebrik.OBRAZ, "dovod": None}
        self._cue_rung = stav["stupen"]
        app_log.info("rebrik hlasky: %s (styl %s, dovod %s)",
                     self._cue_rung, self._cue_style_rel, stav.get("dovod"))
        return stav

    # ---------- styl hlasky (onboarding krok 5, Nastavenia -> Zvuk) ----------

    @staticmethod
    def _cue_style_label(styl):
        """'voice'/'sound'/'visual' -> veta z onboardingu v jazyku rozhrania."""
        return tr(dict(CUE_STYLE_LABELS)[rebrik.normalize_cue_style(styl)])

    def _cue_style_labels(self):
        return [tr(kluc) for _styl, kluc in CUE_STYLE_LABELS]

    def _on_cue_style_label(self, label):
        """Vyber v riadku "Ako sa ozyvam" (Nastavenia -> Zvuk)."""
        styl = next((s for s, kluc in CUE_STYLE_LABELS if tr(kluc) == label), None)
        if styl is None:
            return
        self._nastav_styl_hlasky(styl)
        self.save_settings()
        # Styl rozhoduje, ci sa texty hlasok posielaju na syntezu
        # (`_hlasky_hovoria`) - hlas sa pripravi hned, ked ho hrac zapne.
        self.schedule_pregenerate(200)

    def _prevezmi_styl_z_onboardingu(self, wizard):
        """Styl z 5. kroku onboardingu. None = hrac nevybral nic a ostava
        mu, co mal (novemu hracovi hlas - to iste ako odpoved "neviem")."""
        styl = getattr(wizard, "cue_style", None)
        if styl is not None:
            self._nastav_styl_hlasky(styl)

    def _nastav_styl_hlasky(self, styl):
        """Hrac vybral styl hlasky (onboarding alebo Nastavenia -> Zvuk).

        Novy styl je vrchol rebrika od dalsej relacie (`_urci_stupen_hlasky`).
        TICHSI styl navyse plati HNED, aj v beziacej relacii: veta pri volbe
        slubuje "nikdy nie hlasnejsie, nez tu vyberies", a hlas, ktory by
        dohral vecer po tom, co si hrac vybral len obrazok, by ju porusil.
        Hlasnejsi styl pocka na dalsiu relaciu - stupen sa uprostred relacie
        neprepocitava (ako svet) a byt tichsie, nez hrac dovolil, smie.
        Relacia si do suhrnu zapise styl a stupen, s ktorymi naozaj dobehla.
        """
        styl = rebrik.normalize_cue_style(styl)
        self.cue_style = styl
        app_log.info("styl hlasky: %s", styl)
        # Veta pod ukazkou v Nastaveniach -> Zvuk ide za stylom HNED - aj
        # hlasnejsim, lebo ukazka hra styl, nie stupen beziacej relacie.
        veta = getattr(self, "preview_sub_label", None)
        if veta is not None:
            try:
                veta.configure(text=self._preview_sub_text())
            except Exception:
                app_log.exception("ukazka: vetu sa nepodarilo prepisat")
        if not rebrik.je_tichsi(styl, getattr(self, "_cue_style_rel", None)):
            return
        self._cue_style_rel = styl
        svet = getattr(self, "_session_world", hr_stats.WORLD_DEFAULT)
        if (rebrik.vrchol(svet, styl) == rebrik.OBRAZ
                and getattr(self, "_cue_rung", rebrik.HLAS) == rebrik.HLAS):
            # Len obrazok: automat uz hlas neohlasi (`hlas` v udalosti hovori
            # pravdu) a `_fire_somatic_cue` pod stupnom hlasu nic neprehra.
            self._cue_rung = rebrik.OBRAZ
            automat = getattr(self, "cue_trigger", None)
            if automat is not None:
                automat.voice = False
