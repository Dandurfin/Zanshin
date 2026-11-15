"""Structure of the 'Guide / What's behind it' panel.

All displayed text (names, physiology, science, instructions, breathing
techniques) is translated and lives in i18n.py under the keys
"guide.<id>.*" - here is only the order of the cards, their IDs (also
used as the name of the temporary sketch and the PNG name in
assets/guides/) and the number of techniques for the breathing card.
"""

from i18n import tr

# Where to link from the "About" panel. These change independently of
# the code, so they are here as data and not hard-wired into the UI.
#
# DISCORD IS NOT HERE ON PURPOSE. Bug reports, ideas and collaboration go
# to GitHub: a discussion there stays public, searchable and tied to the
# code, while on Discord it sinks after a week. On top of that an invite
# has a limited validity and after it expired it would stop working for
# everyone who has already downloaded the app - and the author would not
# find out.
#
# THE REPOSITORY is the only place the official Zanshin comes from
# (LICENSE-DESIGN.md, point 4) - and also where the source code is, which
# the installer does not carry. That is why it is clickable in "About",
# not just mentioned in the licence text.
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
# THREE sources the app shows - in the Guide (the "philosophy" card) and
# in History (the "How it came about" panel), always under the author's
# text `origin.*`. They are exactly the ones the Guide cards cite "in the
# sources below": breath (Lehrer & Gevirtz 2014), box breathing (Zaccaro
# 2018) and the jaw (Ketelhut & Nigg 2024). The labels are the author's
# examples, not study titles.
#
# The full list - everything that was here up to 0.2, plus the research
# on cues under load - is in ZDROJE.md in the repository root. A long list
# in the app came across as "the science behind the app", although none of
# those works tests Zanshin (the author's decision, 0.2). check_sources.py
# checks these three; the links in ZDROJE.md it does not.
PHILOSOPHY_SOURCES = [
    ("guide.philosophy.source12", "https://doi.org/10.3389/fpsyg.2014.00756"),   # Lehrer & Gevirtz 2014
    ("guide.philosophy.source11", "https://doi.org/10.3389/fnhum.2018.00353"),   # Zaccaro 2018
    ("guide.philosophy.source10", "https://pubmed.ncbi.nlm.nih.gov/38638448/"),  # Ketelhut & Nigg 2024
]


def origin_sources():
    """[(label, url)] for the Guide and History - one list, one state,
    translated labels."""
    return [(tr(key), url) for key, url in PHILOSOPHY_SOURCES]


def guide_cards():
    """Reloads the translations for the current language - called on every
    opening/redraw of the Guide panel."""
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
