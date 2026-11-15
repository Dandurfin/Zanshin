# -*- coding: utf-8 -*-
"""Generates `preklad_TODO.csv` - a list of strings waiting to be translated.

Criterion (the same as in `check_before_run.py`, section 2): a string "needs
translating" if any of the NON-LATIN-SCRIPT languages (ja/zh/ru/bg) stayed
literally the same as `en` - that really cannot be a translation, only the
English fallback.

WATCH OUT FOR COMPARING WITH `de`: that was the original criterion, and after
the translations were finished it reported three strings forever, because
the German "Timing" and "normal" happen to be the same words as the English
ones. Latin-script languages legitimately coincide with English; Japanese,
Chinese, Russian and Bulgarian do not.

NOTE: until now the CSV was made by hand/ad hoc, so after every key was
deleted (e.g. after the minimalist mode was removed) it kept rows for keys
that no longer existed in i18n.py. This script is therefore the only correct
way to regenerate the file:

    python make_translation_todo.py
"""
import csv
import sys

sys.path.insert(0, ".")
import i18n

OUT = "preklad_TODO.csv"
TARGET_LANGS = ("ja", "zh", "ru", "es", "de", "fr", "pt", "cs", "bg")
# Languages that do not coincide with English by chance (a different
# script) - see the header.
SPOLAHLIVE = ("ja", "zh", "ru", "bg")

# Keys where matching English is DELIBERATE even in a language with a
# different script: Japanese and Chinese write a percentage without a space
# like English („{n}%“), Slovak with a space („{n} %“) - that is why sk and en
# differ.
ZAMERNA_ZHODA = {"dashboard.fmt.pct"}


def na_dopreklad(strings):
    """Keys where one of the SPOLAHLIVE languages stayed English."""
    return sorted(
        key for key, entry in strings.items()
        if key not in ZAMERNA_ZHODA
        and entry.get("en") != entry.get("sk")
        and any(entry.get(lang) == entry.get("en") for lang in SPOLAHLIVE)
    )


def main():
    strings = i18n.STRINGS
    todo = na_dopreklad(strings)

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
