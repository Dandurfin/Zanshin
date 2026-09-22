# -*- coding: utf-8 -*-
"""Kontrola prekladov: chybajuce kluce, chybajuce jazyky, nezhodne
placeholdery, a kolko retazcov ostava len anglicky (na dopreklad)."""
import re, sys
sys.path.insert(0, ".")
import i18n

LANGS = list(i18n.LANGUAGES)
S = i18n.STRINGS

def placeholders(text):
    return set(re.findall(r"\{(\w+)\}", str(text)))

missing_lang = {}          # kluc -> [chybajuce jazyky]
ph_mismatch = []           # (kluc, jazyk, ocakavane, najdene)
english_fallback = {}      # jazyk -> pocet retazcov zhodnych s EN (pravdepodobne nepreloz.)
empty = []

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

# kolko retazcov je v danom jazyku doslovne rovnakych ako anglictina
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
    print("  ziadne - kazdy kluc ma vsetkych 9 jazykov")

print("\n== Nezhodne placeholdery ({meno}) ==")
if ph_mismatch:
    for k, lang, exp, got in ph_mismatch[:40]:
        print(f"  {k} [{lang}]: cakane {exp or '{}'}, najdene {got or '{}'}")
    print(f"  ... spolu {len(ph_mismatch)}")
else:
    print("  ziadne - vsetky {placeholdery} sedia napric jazykmi")

print("\n== Prazdne retazce ==")
print("  " + (", ".join(f"{k}[{l}]" for k,l in empty) if empty else "ziadne"))

print("\n== Retazce zhodne s anglictinou (pravdepodobne na dopreklad) ==")
for lang, n in english_fallback.items():
    pct = round(100*n/len(S))
    print(f"  {lang}: {n} z {len(S)} ({pct}%)")

problems = len(missing_lang) + len(ph_mismatch) + len(empty)
print(f"\n{'CHYBY: ' + str(problems) if problems else 'OK - ziadne strukturalne chyby v prekladoch'}")
sys.exit(1 if problems else 0)
