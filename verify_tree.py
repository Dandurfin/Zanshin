"""Overi, ze tento zdrojak sa sprava presne ako zbuildovany depot 2.0.

PRECO TO TU JE
--------------
Tento strom nie je povodny zdrojak - ten sa zmazal. Je to obnova (viz
OBNOVA.md). Jediny pevny bod, o ktory sa da opriet, je zbuildovany
ZanshinDojoSync.exe: v nom je bytecode vsetkych modulov appky tak, ako
realne bezia.

Skript kazdy modul skompiluje a porovna s tym, co je v .exe - instrukcie,
konstanty (vratane docstringov) aj mena. Ak sedia vsetky, obnova je
spravna. Komentare a formatovanie sa timto neoveruju, tie v bytecode nie su
- cize uprava komentara hlasi ZHODU dalej, uprava docstringu uz nie.

Ked sa zacne robit na 2.1, zhoda sa prirodzene zacne rozpadat - to je v
poriadku a ocakavane. Zmysel ma spustit to hned po obnove, alebo vtedy, ked
treba overit, ze sa nejaky modul nezmenil oproti poslednemu vydanemu buildu.

POUZITIE
--------
    python verify_tree.py
    python verify_tree.py --exe "C:\\cesta\\k\\ZanshinDojoSync.exe"
"""
import argparse
import marshal
import os
import struct
import sys
import zlib

DEFAULT_EXE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "<lokalny priecinok>", "ZanshinDojoSync", "ZanshinDojoSync.exe")

# PyInstaller CArchive cookie - posledna vec v .exe
COOKIE = b"MEI\014\013\012\013\016"


def depot_modules(exe_path):
    """{meno modulu: code object} pre moduly appky zabalene v .exe.

    Appka zije v PYZ archive vnutri CArchive; `main` je ulozeny priamo
    v CArchive ako typ 's'."""
    with open(exe_path, "rb") as fh:
        data = fh.read()

    pos = data.rfind(COOKIE)
    if pos < 0:
        raise SystemExit(f"{exe_path}: nevyzera ako PyInstaller build")
    _, pkg_len, toc_pos, toc_len, _ = struct.unpack("!8sIIII", data[pos:pos + 24])
    start = pos + 24 + 64 - pkg_len
    toc = data[start + toc_pos:start + toc_pos + toc_len]

    out = {}
    pyz = None
    off = 0
    while off < len(toc):
        (entry_len,) = struct.unpack("!i", toc[off:off + 4])
        if entry_len <= 0:
            break
        dpos, dlen, _ulen, flag, typecode = struct.unpack("!IIIBc", toc[off + 4:off + 18])
        name = toc[off + 18:off + entry_len].rstrip(b"\0").decode("utf-8", "replace")
        blob = data[start + dpos:start + dpos + dlen]
        if typecode == b"z":
            pyz = zlib.decompress(blob) if flag else blob
        elif typecode in (b"s", b"m", b"M") and name == "main":
            out["main"] = marshal.loads(zlib.decompress(blob) if flag else blob)
        off += entry_len

    if pyz is None:
        raise SystemExit(f"{exe_path}: PYZ archiv sa nenasiel")
    (pyz_toc_off,) = struct.unpack("!I", pyz[8:12])
    pyz_toc = marshal.loads(pyz[pyz_toc_off:])
    items = pyz_toc.items() if isinstance(pyz_toc, dict) else pyz_toc

    here = os.path.dirname(os.path.abspath(__file__))
    local = {f[:-3] for f in os.listdir(here) if f.endswith(".py")}
    for mod, (_ispkg, mpos, mlen) in items:
        if mod in local:
            out[mod] = marshal.loads(zlib.decompress(pyz[mpos:mpos + mlen]))
    return out


def norm(const):
    """Konstanta porovnatelna naprie roznymi co_filename."""
    if hasattr(const, "co_code"):
        return ("<code>", const.co_name, const.co_code,
                tuple(norm(c) for c in const.co_consts),
                const.co_names, const.co_varnames, const.co_argcount)
    return const


def signature(code):
    return (code.co_code, tuple(norm(c) for c in code.co_consts), code.co_names)


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--exe", default=DEFAULT_EXE, help="cesta k ZanshinDojoSync.exe")
    ap.add_argument("--tree", default=os.path.dirname(os.path.abspath(__file__)),
                    help="priecinok so zdrojakmi")
    args = ap.parse_args()

    if not os.path.exists(args.exe):
        raise SystemExit(f"depot sa nenasiel: {args.exe}\nZadaj cestu cez --exe.")

    depot = depot_modules(args.exe)
    print(f"depot: {args.exe}")
    print(f"strom: {args.tree}")
    print(f"modulov v depote: {len(depot)}")
    print()

    ok, bad = [], []
    for mod in sorted(depot):
        path = os.path.join(args.tree, f"{mod}.py")
        if not os.path.exists(path):
            bad.append((mod, "subor chyba"))
            continue
        with open(path, encoding="utf-8-sig") as fh:
            text = fh.read()
        try:
            got = compile(text, f"{mod}.py", "exec", dont_inherit=True)
        except SyntaxError as exc:
            bad.append((mod, f"neskompilovatelne: {exc}"))
            continue
        if signature(got) == signature(depot[mod]):
            ok.append(mod)
            print(f"  {mod:<20} ZHODA")
        else:
            bad.append((mod, "bytecode sa lisi"))
            print(f"  {mod:<20} LISI SA")

    print("-" * 46)
    print(f"{len(ok)}/{len(depot)} modulov sa zhoduje s depotom 2.0")
    for mod, why in bad:
        print(f"  !! {mod}: {why}")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
