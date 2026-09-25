"""Sloty, profily hier a auto-profil - cast hlavnej appky (DandurfApp z app.py).

ProfilesMixin je mixin DandurfApp: app.py ho dedi a cely stav (sloty
aktivneho profilu, zoznam profilov a prepinac profilu, auto-profil a
citanie beziacich procesov) zije na DandurfApp. Tu su len metody, ktore s
nim pracuju cez `self` - mixin nema __init__ ani vlastne atributy.

Presunute z app.py bez zmeny:
  * sloty - prestavba kariet slotov aktivneho profilu,
  * profily hier - prepnutie, zalozenie a zmazanie profilu,
  * Auto-Profile Engine (rozpoznanie beziacej hry) - prva cast sekcie:
    najdena a skoncena hra, citanie mien procesov (`GameProcessWatcher`),
    prepinac auto-profilu a veta stavu "Zastavene", ktora o nom hovori.
    Zvysok tej sekcie (senzor tepu a meracia relacia) je v app_session.py.

Pozor v testoch: `_start_game_watcher` cita `GameProcessWatcher` a
`PSUTIL_AVAILABLE` z tohto modulu - falosny watcher treba podstrcit sem
(`app_profiles.GameProcessWatcher`), nie na modul app.
"""

from tkinter import messagebox

from game_profiles import PSUTIL_AVAILABLE, GameProcessWatcher, known_games
from i18n import tr
from paths import APP_NAME
from settings_model import default_slots, normalize_slot
from ui_dialogs import NewProfileDialog, SlotCard


class ProfilesMixin:
    """Sloty, profily hier a auto-profil (mixin DandurfApp)."""

    # ---------- sloty ----------

    def rebuild_slots(self, data_list):
        """Prestava sloty aktivneho profilu, zosuladi odznak v navigacii aj
        listu hromadneho vyberu (po prestavbe uz nic nie je oznacene)."""
        for child in self.slots_container.winfo_children():
            child.destroy()
        self.slots = [SlotCard(self, i, data) for i, data in enumerate(data_list)]
        self._on_slot_selection_change()
        self._refresh_nav_badges()

    def slot_dicts(self):
        return [s.to_dict() for s in self.slots]

    # ---------- profily hier ----------

    def _sync_active_profile_slots(self):
        profile = next((p for p in self.profiles if p["name"] == self.active_profile_name),
                       None)
        if profile is not None:
            profile["slots"] = self.slot_dicts()

    def refresh_profile_switch(self):
        names = [p["name"] for p in self.profiles]
        self.profile_switch.configure(values=names)
        self.profile_var.set(self.active_profile_name)

    def on_profile_switch(self, name):
        self.switch_profile(name)

    def switch_profile(self, name):
        if name == self.active_profile_name:
            return
        profile = next((p for p in self.profiles if p["name"] == name), None)
        if profile is None:
            return
        self._sync_active_profile_slots()
        self.active_profile_name = name
        self.rebuild_slots(profile["slots"])
        self.profile_var.set(name)
        self.save_settings()
        self.schedule_pregenerate(200)
        self.log(tr("log.profile_switched", name=name))

    def new_profile_dialog(self):
        NewProfileDialog(self)

    def create_profile(self, name):
        name = name.strip()
        if not name:
            return
        if any(p["name"] == name for p in self.profiles):
            messagebox.showinfo(APP_NAME, tr("profile.duplicate_name"))
            return
        self._sync_active_profile_slots()
        # Novy profil dostane VSETKY STYRI kategorie, rovnako ako profil
        # zalozeny automaticky pre hru (`_handle_game_found`). Doteraz mal
        # jeden slot a zvysne si hrac "pridal" tlacidlom - to je prec, takze
        # by profil ostal navzdy len s Taziskom.
        new_slots = [normalize_slot(s) for s in default_slots()]
        self.profiles.append({"name": name, "slots": new_slots})
        self.active_profile_name = name
        self.rebuild_slots(new_slots)
        self.refresh_profile_switch()
        self.save_settings()
        self.log(tr("log.profile_created", name=name))

    def delete_current_profile(self):
        if len(self.profiles) <= 1:
            messagebox.showinfo(APP_NAME, tr("profile.cannot_delete_last"))
            return
        if not messagebox.askyesno(APP_NAME,
                                   tr("profile.confirm_delete", name=self.active_profile_name)):
            return
        self.profiles = [p for p in self.profiles if p["name"] != self.active_profile_name]
        new_active = self.profiles[0]
        self.active_profile_name = new_active["name"]
        self.rebuild_slots(new_active["slots"])
        self.refresh_profile_switch()
        self.save_settings()
        self.schedule_pregenerate(200)
        self.log(tr("log.profile_deleted"))

    # ---------- Auto-Profile Engine (rozpoznanie beziacej hry) ----------

    def on_game_process_found(self, profile_name):
        self.ui_call(lambda: self._handle_game_found(profile_name))

    def on_game_process_gone(self):
        self.ui_call(self._handle_game_gone)

    def _handle_game_found(self, profile_name):
        if not self.auto_profile_enabled:
            return
        if not any(p["name"] == profile_name for p in self.profiles):
            self._sync_active_profile_slots()
            new_slots = [normalize_slot(s) for s in default_slots()]
            self.profiles.append({"name": profile_name, "slots": new_slots})
            self.refresh_profile_switch()
            self.log(tr("log.auto_profile_created", name=profile_name))
        if profile_name != self.active_profile_name:
            self.switch_profile(profile_name)
        self.log(tr("log.auto_profile_detected", name=profile_name))
        if not self.listening:
            self._auto_started_listening = True
            self.start_listening()

    def _handle_game_gone(self):
        if not self.auto_profile_enabled:
            return
        # "Odpocuvanie pozastavene" sa pise LEN ked sa naozaj zastavilo.
        # Doteraz sa zapisalo vzdy - aj ked pocuvanie spustil hrac sam a
        # bezalo dalej (port aj meranie), takze dennik tvrdil opak.
        if self.listening and self._auto_started_listening:
            self.stop_listening()
            self.log(tr("log.auto_profile_ended"))
        self._auto_started_listening = False

    @staticmethod
    def _zname_hry():
        """Hry, ktore auto-profil pozna, do viet v appke. Z mapy
        (`game_profiles.GAME_PROCESS_MAP`), aby veta nemohla slubovat start
        pri hre, ktoru appka nepozna."""
        return " / ".join(known_games())

    def _start_game_watcher(self):
        """Spusti citanie mien procesov (auto-profil). Vlakno sa neda
        spustit dvakrat, preto pri kazdom zapnuti nove."""
        if not PSUTIL_AVAILABLE or getattr(self, "game_watcher", None) is not None:
            return
        self.game_watcher = GameProcessWatcher(self.on_game_process_found,
                                               self.on_game_process_gone)
        self.game_watcher.start()

    def _stop_game_watcher(self):
        """Zastavi citanie procesov - vypnuty auto-profil necita nic."""
        watcher, self.game_watcher = getattr(self, "game_watcher", None), None
        if watcher is not None:
            watcher.stop()

    def _kamae_zastavene(self):
        """Dvojica textov pre stav "Zastavene".

        Appka sa vie spustit sama, ked najde beziacu hru - lenze len pri
        zapnutom automatickom prepinani profilov (`_handle_game_found`), a
        to sa da vypnut. Preto sa veta pyta na skutocny stav namiesto toho,
        aby slubovala nieco, co pri vypnutom prepinani nepride.
        """
        kluc = ("kamae.stopped_sub_auto" if self.auto_profile_enabled
                else "kamae.stopped_sub")
        return tr("kamae.stopped"), tr(kluc, games=self._zname_hry())

    def on_auto_profile_toggle(self):
        self.auto_profile_enabled = bool(self.auto_profile_var.get())
        if self.auto_profile_enabled:
            self._start_game_watcher()
        else:
            # Vypnute = mena procesov sa necitaju vobec. Pocuvanie, ktore
            # spustila hra, bezi dalej - odteraz ho riadi hrac, nie detekcia.
            self._stop_game_watcher()
            self._auto_started_listening = False
        self.save_settings()
        # Veta v pase hovori o tomto nastaveni, takze sa musi prepisat hned -
        # inak by po vypnuti este stale slubovala start pri hre.
        if not self.listening and getattr(self, "kamae", None) is not None:
            self.kamae.set_texts(tr("kamae.bar_title"), tr("kamae.bar_sub"))
        self.log(tr("log.auto_profile_on") if self.auto_profile_enabled
                else tr("log.auto_profile_off"))
