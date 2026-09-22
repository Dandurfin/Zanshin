"""Struktura panelu 'Sprievodca / Veda za aplikáciou'.

Cely zobrazovany text (nazvy, fyziologia, veda, instrukcie, techniky
dychania) je prekladany a zije v i18n.py pod klucmi "guide.<id>.*" - tu
je len poradie kariet, ich ID (pouzivane aj ako nazov docasneho nacrtu
a nazov PNG v assets/guides/) a pocet technik pre kartu dychania.
"""

from i18n import tr

# Kam viesť z panela "O appke". Sú to odkazy na autora, nie na appku -
# menia sa nezávisle od kódu, preto sú tu ako dáta a nie zadrôtované v UI.
#
# DISCORD TU ZÁMERNE NIE JE. Na hlásenie chýb, nápady a spoluprácu je
# GitHub: diskusia tam ostáva verejná, dohľadateľná a viazaná na kód, kým
# na Discorde po týždni zapadne. Pozvánka má navyše obmedzenú platnosť a
# po expirácii by prestala fungovať všetkým, čo si appku už stiahli - a
# autor by sa to nedozvedel.
#
# TODO pred vydaním: sem pribudne odkaz na repozitár, keď bude existovať
# (viď interné poznámky). Zástupný odkaz tu byť nesmie - rozbitý odkaz v
# appke je horší než žiadny.
COMMUNITY_LINKS = [
    ("Twitch", "https://www.twitch.tv/dandurfin"),
    ("YouTube", "https://www.youtube.com/channel/UCzZyqQfTNpiGkt_SIOmKO2w"),
    ("Kick", "https://kick.com/dandurfin"),
]

GUIDE_CARD_IDS = ["grounding", "jaw", "periphery", "breath", "philosophy"]
BREATH_TECHNIQUE_COUNT = 2
PHILOSOPHY_BLOCK_COUNT = 3
# JEDEN zoznam recenzovanych studii pre Sprievodcu (karta "philosophy"),
# historiu relacii aj check_sources.py - studie nie su na dvoch miestach v
# roznom stave. Pravidlo: LEN realne, recenzovane, on-topic prace (ziadne
# komercne blogy, SEO clanky ani preprinty vydavane za dokaz). Zoradene po
# temach. HRV je len KONTEXT (veda o tepe a strese); appka HRV NEMERIA a
# nikde to netvrdi.
PHILOSOPHY_SOURCES = [
    # -- Pomaly dych a upokojenie (jadro appky: nadych/vydych -> vagus) --
    ("guide.philosophy.source11", "https://doi.org/10.3389/fnhum.2018.00353"),   # Zaccaro 2018
    ("guide.philosophy.source12", "https://doi.org/10.3389/fpsyg.2014.00756"),   # Lehrer & Gevirtz 2014
    # -- Ucinok: znizuje stres/uzkost --
    ("guide.philosophy.source13", "https://doi.org/10.1017/S0033291717001003"),  # Goessl 2017 (meta)
    ("guide.philosophy.source14", "https://doi.org/10.1001/jamainternmed.2013.13018"),  # Goyal 2014 (JAMA meta)
    ("guide.philosophy.source15", "https://doi.org/10.1007/s10484-015-9293-x"),  # van der Zwan 2015 (RCT)
    # -- Pozornost / bdelost ("zanshin") --
    ("guide.philosophy.source16", "https://doi.org/10.1177/0956797610371339"),   # MacLean 2010
    ("guide.philosophy.source17", "https://doi.org/10.1016/j.tics.2008.01.005"),  # Lutz 2008 (review)
    # -- Biofeedback dych v hrach (format appky) --
    ("guide.philosophy.source1", "https://ieeexplore.ieee.org/document/8319498/"),
    ("guide.philosophy.source2", "https://dl.acm.org/doi/10.1145/3706599.3720103"),
    # -- Esport a telo --
    ("guide.philosophy.source4", "https://pmc.ncbi.nlm.nih.gov/articles/PMC7272664/"),
    ("guide.philosophy.source10", "https://pubmed.ncbi.nlm.nih.gov/38638448/"),
    ("guide.philosophy.source5", "https://doi.org/10.1080/1750984X.2020.1723122"),  # Pedraza-Ramirez 2020
    # -- Tep: zotavenie a dlhodoby stres --
    ("guide.philosophy.source6", "https://doi.org/10.1056/NEJM199910283411804"),  # Cole 1999 (NEJM)
    ("guide.philosophy.source8", "https://doi.org/10.30773/pi.2017.08.17"),       # Kim 2018 (meta)
    ("guide.philosophy.source9", "https://doi.org/10.1016/j.jpsychores.2005.06.074"),  # Brosschot 2006
]

# Podmnozina zdrojov k tepu - panel "Preco to funguje" v historii relacii.
HEART_RATE_SOURCE_KEYS = ("guide.philosophy.source6", "guide.philosophy.source7",
                          "guide.philosophy.source8", "guide.philosophy.source9",
                          "guide.philosophy.source10")


def heart_rate_sources():
    """[(popisok, url)] pre historiu relacii - z toho isteho zoznamu ako
    Sprievodca (jeden zdroj pravdy, prelozene popisky)."""
    return [(tr(key), url) for key, url in PHILOSOPHY_SOURCES
            if key in HEART_RATE_SOURCE_KEYS]


def guide_cards():
    """Znovu nacita preklady pre aktualny jazyk - vola sa pri kazdom
    otvoreni/prekresleni panelu Sprievodca."""
    cards = []
    for card_id in GUIDE_CARD_IDS:
        card = {
            "id": card_id,
            "title": tr(f"guide.{card_id}.title"),
            "trigger": tr(f"guide.{card_id}.trigger"),
            "sketch": card_id,
            "techniques": None,
            "physiology": None,
            "science": None,
            "instruction": None,
            "custom_blocks": None,
            "sources": None,
        }
        if card_id == "breath":
            card["techniques"] = [
                {
                    "name": tr(f"guide.breath.tech{i}.name"),
                    "steps": tr(f"guide.breath.tech{i}.steps"),
                    "why": tr(f"guide.breath.tech{i}.why"),
                }
                for i in range(1, BREATH_TECHNIQUE_COUNT + 1)
            ]
        elif card_id == "philosophy":
            card["custom_blocks"] = [
                {
                    "title": tr(f"guide.philosophy.block{i}_title"),
                    "text": tr(f"guide.philosophy.block{i}_text"),
                }
                for i in range(1, PHILOSOPHY_BLOCK_COUNT + 1)
            ]
            card["sources"] = [
                {"label": tr(key), "url": url} for key, url in PHILOSOPHY_SOURCES
            ]
        else:
            card["physiology"] = tr(f"guide.{card_id}.physiology")
            card["science"] = tr(f"guide.{card_id}.science")
            card["instruction"] = tr(f"guide.{card_id}.instruction")
        cards.append(card)
    return cards
