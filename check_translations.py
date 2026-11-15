# -*- coding: utf-8 -*-
"""Translation check: missing keys, missing languages, mismatched
placeholders, literal \\uXXXX in the text, and how many strings remain
English only (still to translate)."""
import re, sys
sys.path.insert(0, ".")
import i18n

LANGS = list(i18n.LANGUAGES)
S = i18n.STRINGS

def placeholders(text):
    return set(re.findall(r"\{(\w+)\}", str(text)))

# A literal backslash + "u2019" in the VALUE instead of the character ’:
# the source had a doubled backslash, so the window showed "THIS PC" +
# backslash + "u2019S" (hr.pair_this_pc, fixed in 0.3).
# No other test caught it - the text is non-empty and the placeholders
# match.
_ESCAPE = re.compile(r"\\u[0-9a-fA-F]{4}")


def literal_escapes(text):
    """All literal `\\uXXXX` in the text (empty list = OK)."""
    return _ESCAPE.findall(str(text))


missing_lang = {}          # key -> [missing languages]
ph_mismatch = []           # (key, language, expected, found)
english_fallback = {}      # language -> number of strings equal to EN (likely untranslated)
empty = []
escapes = []               # (key, language, found) - literal \uXXXX instead of a char

for key, entry in S.items():
    if "sk" not in entry:
        missing_lang.setdefault(key, []).append("sk (zdroj!)")
    ref_ph = placeholders(entry.get("sk", entry.get("en", "")))
    for lang in LANGS:
        if lang not in entry:
            missing_lang.setdefault(key, []).append(lang)
            continue
        val = entry[lang]
        if not str(val).strip():
            empty.append((key, lang))
        if placeholders(val) != ref_ph:
            ph_mismatch.append((key, lang, ref_ph, placeholders(val)))
        if literal_escapes(val):
            escapes.append((key, lang, literal_escapes(val)))

# how many strings in the given language are literally the same as English
for lang in LANGS:
    if lang in ("en",):
        continue
    same = sum(1 for e in S.values()
               if lang in e and "en" in e and e[lang] == e["en"] and e[lang] != e.get("sk"))
    english_fallback[lang] = same

print(f"Prekladovych klucov spolu: {len(S)}")
print(f"Jazyky: {', '.join(LANGS)}\n")

print("== Chybajuce jazyky v kluci ==")
if missing_lang:
    for k, langs in list(missing_lang.items())[:40]:
        print(f"  {k}: chyba {', '.join(langs)}")
    print(f"  ... spolu {len(missing_lang)} klucov s chybajucim jazykom")
else:
    print(f"  ziadne - kazdy kluc ma vsetkych {len(LANGS)} jazykov")

print("\n== Nezhodne placeholdery ({meno}) ==")
if ph_mismatch:
    for k, lang, exp, got in ph_mismatch[:40]:
        print(f"  {k} [{lang}]: cakane {exp or '{}'}, najdene {got or '{}'}")
    print(f"  ... spolu {len(ph_mismatch)}")
else:
    print("  ziadne - vsetky {placeholdery} sedia napric jazykmi")

print("\n== Prazdne retazce ==")
print("  " + (", ".join(f"{k}[{l}]" for k,l in empty) if empty else "ziadne"))

print("\n== Doslovne \\uXXXX v texte (zdvojene lomitko v zdroji) ==")
if escapes:
    for k, lang, found in escapes[:40]:
        print(f"  {k} [{lang}]: {', '.join(found)}")
    print(f"  ... spolu {len(escapes)}")
else:
    print("  ziadne")

print("\n== Retazce zhodne s anglictinou (pravdepodobne na dopreklad) ==")
for lang, n in english_fallback.items():
    pct = round(100*n/len(S))
    print(f"  {lang}: {n} z {len(S)} ({pct}%)")

problems = len(missing_lang) + len(ph_mismatch) + len(empty) + len(escapes)
print(f"\n{'CHYBY: ' + str(problems) if problems else 'OK - ziadne strukturalne chyby v prekladoch'}")
sys.exit(1 if problems else 0)
