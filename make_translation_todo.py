# -*- coding: utf-8 -*-
"""Vygeneruje `preklad_TODO.csv` - zoznam retazcov, ktore cakaju na dopreklad.

Kriterium (rovnake ako v `check_before_run.py`, sekcia 2): retazec je "na
dopreklad", ak niektory z NELATINKOVYCH jazykov (ja/zh/ru) ostal doslovne
rovnaky ako `en` - to uz naozaj nemoze byt preklad, len anglicky fallback.

POZOR NA PORUVNANIE S `de`: to bolo povodne kriterium a po doprelozeni
hlasilo tri retazce navzdy, lebo nemecke "Timing" a "normal" su zhodou
okolnosti rovnake slova ako anglicke. Latinkove jazyky sa s anglictinou
legitimne trafia; japoncina, cinstina ani rustina nie.

POZN: doteraz sa CSV robilo rucne/ad hoc, takze po kazdom zmazani kluca
(napr. po odstraneni minimalistickeho rezimu) v nom ostavali riadky pre
kluce, ktore uz v i18n.py neexistovali. Tento skript je preto jediny
spravny sposob, ako subor obnovit:

    python make_translation_todo.py
"""
import csv
import sys

sys.path.insert(0, ".")
import i18n

OUT = "preklad_TODO.csv"
TARGET_LANGS = ("ja", "zh", "ru", "es", "de", "fr", "pt")
# Jazyky, ktore sa s anglictinou nahodou netrafia (ine pismo) - viz hlavicka.
SPOLAHLIVE = ("ja", "zh", "ru")


def main():
    strings = i18n.STRINGS
    todo = sorted(
        key for key, entry in strings.items()
        if entry.get("en") != entry.get("sk")
        and any(entry.get(lang) == entry.get("en") for lang in SPOLAHLIVE)
    )

    header = ["kluc", "slovensky (zdroj)", "anglicky (zdroj)"]
    header += [f"{lang} (DOPLNIT)" for lang in TARGET_LANGS]

    with open(OUT, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(header)
        for key in todo:
            entry = strings[key]
            row = [key, entry.get("sk", ""), entry.get("en", "")]
            row += [entry.get(lang, "") for lang in TARGET_LANGS]
            writer.writerow(row)

    print(f"{OUT}: {len(todo)} retazcov na dopreklad "
          f"(z {len(strings)} klucov spolu), jazyky: {', '.join(TARGET_LANGS)}")


if __name__ == "__main__":
    main()
