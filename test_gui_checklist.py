#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Manualny testovaci protokol Zanshin DojoSync - pre overenie GUI nazivo.

Preco tento skript existuje
---------------------------
`check_before_run.py` overi vsetko STATICKE (kompilacia, volania, preklady) -
ale bezi bez okna. Cely rad zmien z posledneho kola sa vsak da overit LEN
nazivo, s otvorenou appkou na Windows:

  - drag & drop testu vizualu (stoji na docasnom vypnuti klik-through),
  - blokovanie kolieska na slideroch,
  - color picker piktogramu a ci sa farba ulozi,
  - Sprievodca ako stranka v lavom menu s realnymi piktogramami,
  - ci "Prehlad"/"Dnes" pri prepnuti neskace.

Tento skript NIC netestuje sam - je to VODIC. Spustis appku vedla neho,
skript ti postupne ukaze co naklikat a co ma nastat, a ty potvrdis
preslo/neprelo. Na konci vypise suhrn a zoznam toho, co padlo.

Preco to nie je automat: simulovat kliky a drag cez okno appky (napr.
pyautogui) je krehke, zavisle na rozliseni a rozbije sa pri kazdej zmene
layoutu. Rucne overenie s jasnym kontrolnym zoznamom je pri UI
spolahlivejsie a rychlejsie nez udrziavat fragilny automat.

Spustenie:
    1. v jednom okne:  python main.py
    2. v druhom:       python test_gui_checklist.py

Vysledky sa daju ulozit do gui_test_report.txt (spytam sa na konci).
"""

import sys
import time

# ---- ANSI farby (na Windows termináli funguju v modernom Terminale/PowerShell) ----
class C:
    R = "\033[0m"
    B = "\033[1m"
    GREEN = "\033[32m"
    RED = "\033[31m"
    YELLOW = "\033[33m"
    CYAN = "\033[36m"
    DIM = "\033[2m"


def _supports_color():
    return sys.stdout.isatty()


def col(text, code):
    return f"{code}{text}{C.R}" if _supports_color() else text


# --------------------------------------------------------------------------
# Definicia testov: (sekcia, [ (co_urobit, co_ma_nastat), ... ])
# Kazdy krok je jedna overitelna vec. Formulacie su konkretne, aby sa dalo
# jednoznacne povedat preslo/neprelo.
# --------------------------------------------------------------------------

SECTIONS = [
    ("Spustenie a zakladna navigacia", [
        ("Spusti `python main.py`. Okno appky sa otvori.",
         "Okno nabehne bez chybovej hlasky v termine, ma VLASTNU listku "
         "(nie Windows ram) a vlavo je 6 poloziek: Dnes, Spustace, Zvuk, "
         "V hre, Sprievodca, Nastavenia."),
        ("Preklikaj vsetkych 6 poloziek v lavom menu.",
         "Kazda stranka sa zobrazi, nic nespadne, obsah sa nacita."),
    ]),

    ("UX feedback: menu, resize, dok, zarovnanie, ton", [
        ("Pozri lave menu.",
         "Len 3 polozky (Dnes, Historia, Nastavenia) - ikona nad kratkym "
         "popiskom, po najazdeni tooltip. Logo 残 + verzia su hore v liste."),
        ("Nastavenia -> karty hore (Spustace | Zvuk | V hre | Sprievodca | Vseobecne).",
         "Kazda karta otvori svoju stranku; Ctrl+K polozky aj 'Sparovat teraz' "
         "z onboardingu skocia na spravnu kartu."),
        ("Chyt okno za pravy dolny roh (kurzor sa zmeni na sipky) a potiahni; "
         "potom za lavy horny roh.",
         "Okno sa zvacsi/zmensi a ostava bez Windows ramu. Pod 860x600 sa nezmensi. "
         "Po starte je kompaktne (1000x680), nie cez celu obrazovku."),
        ("Dole v menu klikni '▶ Spustit'.",
         "Tlacidlo sa zmeni na cervene '■ Zastavit'. Tooltip hovori, co klik spravi. "
         "Pod nim 3 male ikony (stisit, 20 min ticho, spustace)."),
        ("Dnes bez hodiniek.",
         "V paneli Tep a zataz je tlmeny nahlad HUD-u, veta a tlacidlo 'Sparovat "
         "hodinky' - nie prazdna krivka."),
        ("Nastavenia -> V hre: IP / port / tep a 4 riadky vizualov.",
         "Policka aj popisky v jednej osi; 'Uvolnenie (mys)' zacina na rovnakej x "
         "ako ostatne (emoji v pevnom stlpci), prepinace zarovnane vpravo."),
        ("Precitaj texty v Zvuk, Vseobecne a Sprievodcovi.",
         "Priatelske tykanie bez skratiek (ziadny 'Striktny globalny zamok', "
         "'Motor TTS', 'SAPI5') - 'Naraz len jedna pripomienka', 'Hlas generuje', "
         "'Co sa deje v tele / Co na to veda / Co spravit ty'."),
        ("Spusti installer\\ZanshinDojoSync-1.0-setup.exe.",
         "ZIADNE UAC. Instaluje do %LOCALAPPDATA%\\Programs\\Zanshin DojoSync, "
         "appka bezi bez admin prav a spustace aj vizualy v hre funguju."),
    ]),

    ("Historia relacii tepu + metriky + Preco to funguje", [
        ("Lave menu -> Historia (bez ulozenych relacii).",
         "Stranka sa otvori, ukaze text 'Zatial ziadna relacia', prazdny graf a "
         "postreh 'Zatial 0 z 3 relacii'. Nic nespadne."),
        ("Zapni senzor tepu (V hre), nechaj bezat aspon minutu, vypni ho.",
         "V Historii pribudne riadok: datum, dlzka, priemer, min/max, cas nad "
         "hranicou, pocet dychani, spicka zataze, HRR, HRPI. Graf vyvoja "
         "(pokojova zakladna) dostane bod."),
        ("Pri kazdej metrike klikni 'i co to znamena' (Dnes: tep, zataz; "
         "Historia: zakladna, HRR, pasma, HRPI).",
         "Rozbali sa 2-3 vety pre hraca, presne znenie zo zadania. Nikde slovo "
         "'HRV' ako nieco, co appka meria; nikde diagnoza."),
        ("Historia -> rozbal 'Preco to funguje' a klikni na '↗ zdroj'.",
         "Uvodna veta 'Zanshin nemeria tvoj tep pre zdravie...' + 5 odkazov. "
         "Klik otvori studiu v prehliadaci (rovnaky mechanizmus ako Sprievodca)."),
        ("Historia -> 'Prepocitat' a hned prepni stranku / hybaj oknom.",
         "Appka reaguje, analyza bezi na pozadi; potom sa v 'Co si appka vsimla' "
         "ukazu postrehy (nie diagnozy) a cas analyzy vpravo."),
        ("V hre -> 'Ako sparovat hodinky'.",
         "Velkym pismom REALNA IP tohto PC (nie 127.x, nie prazdno) + port; ak ma "
         "PC viac sieti (Wi-Fi + Ethernet + VPN), pod tym 'Dalsie adresy'. "
         "Poznamka hovori, ze v nastaveniach ostava 0.0.0.0 = vsetky siete."),
    ]),

    ("Onboarding (prvy start) + guided tour", [
        ("Zmaz dandurf_settings.json a spusti appku.",
         "Otvori sa 4-krokovy onboarding (piktogramy -> nahlad hry -> hodinky "
         "-> vzhlad) vycentrovany na obrazovke."),
        ("Pozri vrch onboarding okna a skus ho potiahnut za listu.",
         "Navrchu je TMAVA lista ako v zvysku appky (ziadny Windows titulok "
         "'- [] X'), bez krizika. Za listu sa da okno tahat. Escape ho nezavrie."),
        ("Krok 3 (hodinky): precitaj oba texty.",
         "Pod hlavnym odsekom je mensi, tlmeny riadok 'A este: appka si pamata "
         "kazdu relaciu...' - druhy dovod pre hodinky (historia). Krok sa zmesti "
         "bez preplnenia, 'Sparovat teraz / Neskor' funguju."),
        ("Klikaj Dalej/Spat; v kroku 1 klikni 'Preskocit uvod'.",
         "Dalej/Spat funguju vsade, 'Preskocit uvod' skoci rovno na krok 4 a "
         "tam uz tlacidlo Preskocit nie je."),
        ("Krok 4: pozri popisy tem Sumi / Aizome.",
         "Kazdy popis je na DVA riadky, nikde nie je doslovne '\\n'."),
        ("Krok 4 -> 'Vstupit do hry'.",
         "Hlavne okno sa ZOBRAZI (nie len plocha!) a po ~1 s sa spusti tour: "
         "bublina 'Krok 1 z 8' v strede okna."),
        ("Klikaj Dalej cez vsetkych 8 krokov.",
         "Bublina je vzdy PRI svojom prvku (pas, polozky menu, dok) a tenky "
         "ram sedi presne na widgete - aj na 4K so skalovanim."),
        ("Po 'Rozumiem' restartuj appku.",
         "Tour sa uz sam nespusti. Nastavenia -> Sprievodca -> 'Spustit "
         "prehliadku' ho spusti znova."),
        ("V tour klikni rychlo 2x Dalej a potom Preskocit.",
         "Ziadna bublina ani ram neostanu visiet."),
        ("Znova zmaz nastavenia, v kroku 3 klikni 'Sparovat hodinky teraz'.",
         "Onboarding sa dokonci, okno sa zobrazi na stranke V hre a otvori sa "
         "parovaci dialog; tour sa NEspusti."),
    ]),

    ("Bocne menu - zarovnanie (ikona | text | odznak)", [
        ("Pozri vsetkych 6 poloziek v lavom menu (Dnes ... Nastavenia).",
         "Text KAZDEJ polozky zacina na tej istej zvislici - ikony maju "
         "vlastny stlpec pevnej sirky, takze sirsi glyf (⌸, ⚙) text neposuva."),
        ("Pozri odznak '4' pri Spustacoch; zapni senzor tepu (V hre), aby sa "
         "pri 'V hre' ukazala bodka.",
         "Odznak aj bodka sedia pri PRAVOM okraji riadku na rovnakej zvislici, "
         "nie v strede za textom. Polozky bez odznaku nemaju vpravo prazdne miesto."),
        ("Klikni presne na IKONU polozky, potom presne na jej TEXT.",
         "Oba kliky prepnu stranku a riadok dostane aktivne pozadie; pri "
         "prejdeni mysou riadok zosvetlie (hover)."),
        ("Nastavenia -> prepni temu Aizome <-> Sumi a pozri menu znova.",
         "Zarovnanie textov aj odznakov ostava rovnake, farby su z novej temy."),
    ]),

    ("Bod 2b - Prehlad/Dnes NESKACE", [
        ("Prepni na 'Dnes', potom na 'Spustace' a spat na 'Dnes'. Sleduj "
         "hornu cast (dychajuci pas) a rozlozenie.",
         "Pri navrate na 'Dnes' layout NESKACE - pas ani panely nemenia "
         "vysku/poziciu. (Ak skace, sledovat KamaeBar - viz poznamky.)"),
        ("Nechaj 'Dnes' otvorenu ~15 s a sleduj dychajuci pas.",
         "Pas plynulo dycha (svetla ciara dole rastie/klesa), nehybe sa "
         "trhane a NEmeni vysku okna."),
    ]),

    ("Bod 2c - koliesko NEmeni slidery", [
        ("Chod na 'V hre'. Podrz kurzor nad sliderom (napr. velkost HUD) a "
         "toc kolieskom mysi.",
         "Hodnota slidera sa NEMENI. Stranka sa scrolluje nahor/nadol."),
        ("To iste na 'Zvuk' - kurzor nad sliderom hlasitosti, toc kolieskom.",
         "Hodnota sa NEMENI, stranka scrolluje."),
        ("Teraz slider CHYT a tahaj (klik + tah).",
         "Tahanim sa hodnota MENI normalne (blokovanie plati len na koliesko)."),
    ]),

    ("Bod 3 - Test vizualu = drag & drop", [
        ("Na 'V hre' klikni pri niektorom vizuali (napr. Tazisko) na 'Test'.",
         "Piktogram sa zobrazi na obrazovke a OSTANE tam (nezmizne po 3 s). "
         "Tlacidlo sa zmeni na 'Hotovo'."),
        ("Prejdi mysou nad piktogram.",
         "Kurzor sa zmeni na kriz so sipkami (fleur) - da sa chytit."),
        ("Chyt piktogram mysou a potiahni ho inam.",
         "Piktogram sa hybe za mysou, da sa umiestnit kamkolvek."),
        ("Klikni 'Hotovo'.",
         "Piktogram zmizne, tlacidlo je zas 'Test'."),
        ("Spusti Test znova.",
         "Piktogram sa objavi na NOVEJ pozicii (tam, kam si ho potiahol) - "
         "poloha sa ulozila."),
        ("Kym bezi Test jedneho vizualu, klikni 'Test' na inom.",
         "Prvy test sa vypne, zobrazi sa druhy - nikdy nie dva naraz."),
        ("Restartuj appku, chod na 'V hre', spusti Test.",
         "Piktogram je na ulozenej pozicii aj po restarte."),
    ]),

    ("Bod 3b - farba piktogramu", [
        ("Na 'V hre' klikni na farebny stvorcek pri niektorom vizuali.",
         "Otvori sa systemovy vyber farby."),
        ("Vyber vyraznu farbu (napr. cervenu) a potvrd.",
         "Stvorcek zmeni farbu. Spusti Test - piktogram je v novej farbe."),
        ("Otvor vyber farby znova a daj 'Zrusit'.",
         "Farba sa NEZMENI (Zrusit necha povodnu)."),
        ("Restartuj appku a spusti Test daneho vizualu.",
         "Farba ostala ulozena aj po restarte."),
    ]),

    ("Bod 1 - auto-spustac podla tepu (ak mas senzor)", [
        ("Ak mas hodinky: sparuj ich (V hre -> Ako sparovat hodinky) a "
         "nastav nizku kriticku hranicu, aby sa dala prekrocit.",
         "Ked tep vydrzi nad hranicou ~5 s, dychaci kruh sa spusti SAM "
         "aj so zvukom, bez stlacenia klavesu."),
        ("(Bez senzora tento bod preskoc - oznac ako N/A cez 's'.)", ""),
    ]),

    ("Bod 4 - Sprievodca v menu s realnymi piktogramami", [
        ("Klikni v lavom menu na 'Sprievodca'.",
         "Otvori sa ako STRANKA (nie samostatne okno), s kartami "
         "Tazisko/Celust/.../Filozofia."),
        ("Pozri piktogram pri karte Tazisko, Celust a Dych.",
         "Su to REALNE piktogramy z overlay (rovnake ako pri Teste vizualu) "
         "- nie ilustracne nacrty."),
        ("Rozbal a zabal niektoru kartu klikom na jej nadpis.",
         "Karta sa rozbali/zabali, obsah je citatelny."),
        ("Ak menis farbu piktogramu (bod 3b), vrat sa do Sprievodcu.",
         "Piktogram v Sprievodcovi ma farbu temy (nezavisly od per-slot "
         "farby vizualu) - to je v poriadku."),
    ]),

    ("Dialogy - vlastna listka namiesto Windows ramu", [
        ("Otvor 'Ako sparovat hodinky' (V hre) a niektory dialog nastaveni.",
         "Dialog ma VLASTNU tmavu listku s nazvom a krizikom - NIE Windows "
         "titulok navrchu."),
        ("Skus dialog tahat za jeho listku a zavriet ho klavesom Escape.",
         "Da sa tahat aj zavriet Escapom. (Ak nie, viz DialogChrome._FRAMELESS "
         "v ui_kit.py - da sa prepnut na OS ram.)"),
    ]),

    ("Temy a jazyky", [
        ("Nastavenia -> prepni temu Aizome <-> Sumi.",
         "Cela appka vratane docku a piktogramov zmeni farby, nic neostane "
         "'napoly stare'."),
        ("Nastavenia -> prepni jazyk na English.",
         "Texty sa prepnu. (ja/zh/ru/... maju cast len anglicky - to je "
         "znama vec, na dopreklad, nie chyba.)"),
    ]),

    ("Spustace - hromadne odstranenie a rebind", [
        ("Spustace -> zaskrtni checkbox pri 2-3 slotoch.",
         "Hore sa objavi lista 'Oznacene: N' s tlacidlom odstranit."),
        ("Klikni odstranit oznacene, potvrd.",
         "Sloty zmiznu naraz. Skus oznacit VSETKY - musi to odmietnut "
         "(aspon jeden ostane)."),
        ("Klikni na keycap niektoreho slotu (rebind), stlac iny klaves.",
         "Popisok klavesu sa zmeni na novy a ulozi sa (over reklikom/restartom)."),
    ]),
]


def run():
    total = passed = failed = skipped = 0
    failures = []

    print(col("\n" + "=" * 70, C.CYAN))
    print(col("  MANUALNY TEST GUI - Zanshin DojoSync", C.B))
    print(col("=" * 70, C.CYAN))
    print(col("\nAppka MA BYT SPUSTENA vedla (python main.py).", C.YELLOW))
    print("Pri kazdom kroku: sprav akciu, over vysledok, a stlac:")
    print(f"  {col('p', C.GREEN)} = preslo    "
          f"{col('n', C.RED)} = NEpreslo    "
          f"{col('s', C.DIM)} = preskocit/N/A    "
          f"{col('q', C.YELLOW)} = koniec\n")
    try:
        input(col("Enter pre zaciatok...", C.DIM))
    except (EOFError, KeyboardInterrupt):
        print("\nZruseno.")
        return

    for section, steps in SECTIONS:
        print(col(f"\n{'-' * 70}", C.CYAN))
        print(col(f"  {section}", C.B + C.CYAN))
        print(col("-" * 70, C.CYAN))
        for i, (action, expect) in enumerate(steps, 1):
            total += 1
            print(f"\n{col(f'[{i}] AKCIA:', C.B)} {action}")
            if expect:
                print(f"    {col('OCAKAVANE:', C.DIM)} {expect}")
            while True:
                try:
                    ans = input(col("    > ", C.YELLOW)).strip().lower()
                except (EOFError, KeyboardInterrupt):
                    ans = "q"
                if ans in ("p", "n", "s", "q"):
                    break
                print(col("    (napis p / n / s / q)", C.DIM))
            if ans == "p":
                passed += 1
                print(col("    ✓ preslo", C.GREEN))
            elif ans == "n":
                failed += 1
                failures.append(f"{section} -> krok {i}: {action}")
                print(col("    ✗ NEPRESLO", C.RED))
                note = input(col("    poznamka (nepovinne): ", C.DIM)).strip()
                if note:
                    failures[-1] += f"  [{note}]"
            elif ans == "s":
                skipped += 1
                print(col("    - preskocene", C.DIM))
            elif ans == "q":
                print(col("\nUkoncene predcasne.", C.YELLOW))
                _summary(passed, failed, skipped, total, failures)
                return

    _summary(passed, failed, skipped, total, failures)


def _summary(passed, failed, skipped, total, failures):
    print(col(f"\n{'=' * 70}", C.CYAN))
    print(col("  SUHRN", C.B))
    print(col("=" * 70, C.CYAN))
    print(f"  {col('preslo:', C.GREEN)}     {passed}")
    print(f"  {col('NEPRESLO:', C.RED)}   {failed}")
    print(f"  {col('preskocene:', C.DIM)} {skipped}")
    print(f"  spolu overenych: {passed + failed} z {total}")

    if failures:
        print(col(f"\n  Co padlo ({len(failures)}):", C.RED))
        for f in failures:
            print(col(f"   ✗ {f}", C.RED))
    else:
        if failed == 0 and passed > 0:
            print(col("\n  Vsetko overene preslo.", C.GREEN))

    # ponuka ulozit report
    try:
        save = input(col("\nUlozit vysledok do gui_test_report.txt? (a/n): ", C.DIM)).strip().lower()
    except (EOFError, KeyboardInterrupt):
        save = "n"
    if save == "a":
        try:
            with open("gui_test_report.txt", "w", encoding="utf-8") as fh:
                fh.write("Zanshin DojoSync - manualny test GUI\n")
                fh.write(f"cas: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                fh.write(f"preslo: {passed}\nNEPRESLO: {failed}\npreskocene: {skipped}\n")
                fh.write(f"spolu overenych: {passed + failed} z {total}\n")
                if failures:
                    fh.write("\nCo padlo:\n")
                    for f in failures:
                        fh.write(f"  - {f}\n")
            print(col("Ulozene do gui_test_report.txt", C.GREEN))
        except Exception as exc:
            print(col(f"Ulozenie zlyhalo: {exc}", C.RED))


if __name__ == "__main__":
    run()
