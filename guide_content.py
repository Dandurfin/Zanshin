"""Struktura panelu 'Sprievodca / Čo je za tým'.

Cely zobrazovany text (nazvy, fyziologia, veda, instrukcie, techniky
dychania) je prekladany a zije v i18n.py pod klucmi "guide.<id>.*" - tu
je len poradie kariet, ich ID (pouzivane aj ako nazov docasneho nacrtu
a nazov PNG v assets/guides/) a pocet technik pre kartu dychania.
"""

from i18n import tr

# Kam viesť z panela "O appke". Menia sa nezávisle od kódu, preto sú tu ako
# dáta a nie zadrôtované v UI.
#
# DISCORD TU ZÁMERNE NIE JE. Na hlásenie chýb, nápady a spoluprácu je
# GitHub: diskusia tam ostáva verejná, dohľadateľná a viazaná na kód, kým
# na Discorde po týždni zapadne. Pozvánka má navyše obmedzenú platnosť a
# po expirácii by prestala fungovať všetkým, čo si appku už stiahli - a
# autor by sa to nedozvedel.
#
# REPOZITÁR je jediné miesto, odkiaľ je oficiálny Zanshin (LICENSE-DESIGN.md,
# bod 4) - a zároveň to, kde je zdrojový kód, ktorý inštalátor nenesie.
# Preto je v "O appke" klikací, nie len spomenutý v texte licencie.
REPO_URL = "https://github.com/Dandurfin/Zanshin"

COMMUNITY_LINKS = [
    ("GitHub", REPO_URL),
    ("Twitch", "https://www.twitch.tv/dandurfin"),
    ("YouTube", "https://www.youtube.com/channel/UCzZyqQfTNpiGkt_SIOmKO2w"),
    ("Kick", "https://kick.com/dandurfin"),
]

GUIDE_CARD_IDS = ["grounding", "jaw", "periphery", "breath", "philosophy"]
BREATH_TECHNIQUE_COUNT = 2
PHILOSOPHY_BLOCK_COUNT = 3
# TRI zdroje, ktore appka ukazuje - v Sprievodcovi (karta "philosophy") aj v
# Historii (panel "Ako to vzniklo"), vzdy pod textom autora `origin.*`.
# Su to presne tie, ktore karty Sprievodcu cituju "v zdrojoch nizsie":
# dych (Lehrer & Gevirtz 2014), krabicove dychanie (Zaccaro 2018) a celust
# (Ketelhut & Nigg 2024). Popisky su autorove priklady, nie nazvy studii.
#
# Cely zoznam - vsetko, co tu bolo do 0.2, aj vyskum k hlaskam pod zatazou -
# je v ZDROJE.md v koreni repozitara. Dlhy zoznam v appke posobil ako "veda
# za appkou", hoci ziadna z tych prac Zanshin netestuje (rozhodnutie autora,
# 0.2). check_sources.py kontroluje tieto tri; odkazy v ZDROJE.md nie.
PHILOSOPHY_SOURCES = [
    ("guide.philosophy.source12", "https://doi.org/10.3389/fpsyg.2014.00756"),   # Lehrer & Gevirtz 2014
    ("guide.philosophy.source11", "https://doi.org/10.3389/fnhum.2018.00353"),   # Zaccaro 2018
    ("guide.philosophy.source10", "https://pubmed.ncbi.nlm.nih.gov/38638448/"),  # Ketelhut & Nigg 2024
]


def origin_sources():
    """[(popisok, url)] pre Sprievodcu aj Historiu - jeden zoznam, jeden
    stav, prelozene popisky."""
    return [(tr(key), url) for key, url in PHILOSOPHY_SOURCES]


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
            "sources_intro": None,
            "sources_note": None,
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
            ] + [{"title": tr("origin.title"), "text": tr("origin.text")}]
            card["sources_intro"] = tr("origin.examples")
            card["sources"] = [
                {"label": label, "url": url} for label, url in origin_sources()
            ]
            card["sources_note"] = tr("origin.full_list")
        else:
            card["physiology"] = tr(f"guide.{card_id}.physiology")
            card["science"] = tr(f"guide.{card_id}.science")
            card["instruction"] = tr(f"guide.{card_id}.instruction")
        cards.append(card)
    return cards
