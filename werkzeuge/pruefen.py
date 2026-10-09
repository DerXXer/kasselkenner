#!/usr/bin/env python3
"""Lektorats-Prüfung für Kasselkenner-Entwürfe.

Aufruf: python3 werkzeuge/pruefen.py _entwuerfe/<slug>.md [...]
Ausgabe: FEHLER (muss behoben werden) und WARNUNG (begründen oder beheben).
Exit-Code 1, wenn ein Fehler auftritt.
"""
import re, sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL / "werkzeuge"))
from bauen import kopf_lesen  # noqa: E402

EIGENE_TEXTE = [Path.home() / "Claude/Projects/Vermietung/seo" / n for n in
                ("texte-lodgify.md", "seiten/bergpark-gaesteguide.md", "seiten/documenta-2027.md",
                 "portaltexte-2026-10-08.md")]
WERBEWORTE = ["perfekt", "traumhaft", "ultimativ", "einzigartig", "unvergesslich", "atemberaubend",
              "unschlagbar", "paradies", "must-see", "muss man gesehen", "geheimtipp"]
ANREDE_SIE = re.compile(r"(?<![.!?:]\s)(?<!^)\b(Sie|Ihnen|Ihr|Ihre|Ihren|Ihrem|Ihrer)\b")
INTERN = ["_entwuerfe", "nachtlauf", "claude", "faktenspeicher", "BP-", "DO-", "KS-", "/Users/"]


def norm(t):
    t = t.lower().replace(" ", " ").replace("\xa0", " ")
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)
    return re.sub(r"[^a-z0-9äöüß ]+", " ", t)


def schindeln(t, n=8):
    w = norm(t).split()
    return {" ".join(w[i:i + n]) for i in range(len(w) - n + 1)}


def zahlen_im_speicher():
    text = " ".join(p.read_text() for p in (WURZEL / "fakten").glob("*.md"))
    text = text.replace(" ", " ")
    roh = set(re.findall(r"\d+(?:[.,:]\d+)*", text))
    # 14.30 und 14:30 gleich behandeln
    return roh | {z.replace(".", ":") for z in roh} | {z.replace(":", ".") for z in roh}


def pruefe(datei):
    fehler, warn = [], []
    meta, rumpf = kopf_lesen(datei.read_text())
    for feld in ("titel", "beschreibung", "slug", "stand"):
        if not meta.get(feld):
            fehler.append(f"Kopf: Feld '{feld}' fehlt")
    if len(meta.get("titel", "")) > 60:
        fehler.append(f"Titel {len(meta['titel'])} Zeichen (max. 60)")
    b = len(meta.get("beschreibung", ""))
    if b and not 110 <= b <= 160:
        warn.append(f"Beschreibung {b} Zeichen (Ziel 120–155)")
    if meta.get("bild") and not (WURZEL / "bilder" / meta["bild"]).exists():
        fehler.append(f"Bild fehlt: {meta['bild']}")
    h1 = re.findall(r"^# ", rumpf, re.M)
    if len(h1) != 1:
        fehler.append(f"{len(h1)} H1-Überschriften (genau 1)")
    worte = len(norm(rumpf).split())
    if worte < 450 and meta.get("art", "artikel") == "artikel":
        warn.append(f"nur {worte} Wörter (Ziel 500–1.200)")
    if worte > 1600:
        warn.append(f"{worte} Wörter – zu lang für eine Frage?")
    if "## Quellen" not in rumpf and meta.get("art", "artikel") == "artikel":
        fehler.append("Abschnitt '## Quellen' fehlt")
    if "## Häufige Fragen" not in rumpf and meta.get("art", "artikel") == "artikel":
        warn.append("kein Abschnitt '## Häufige Fragen'")
    klein = rumpf.lower()
    for w in WERBEWORTE:
        if w in klein:
            warn.append(f"Werbewort: '{w}'")
    for z in rumpf.splitlines():
        if z.startswith(("#", "|", "- [")) or "](" in z and z.startswith("- "):
            continue
        for m in ANREDE_SIE.finditer(z):
            warn.append(f"Sie-Anrede? '{m.group(0)}' in: {z.strip()[:70]}")
            break
    for w in INTERN:
        if w.lower() in klein:
            fehler.append(f"interner Begriff im Text: '{w}'")
    # Zahlen gegen Faktenspeicher (ohne Quellenabschnitt und Kopf)
    text = rumpf.split("## Quellen")[0]
    text = re.sub(r"\]\([^)]+\)", "]", text)
    speicher = zahlen_im_speicher()
    unbekannt = sorted({z for z in re.findall(r"\d+(?:[.,:]\d+)*", text.replace(" ", " "))
                        if z not in speicher and not re.fullmatch(r"20(2[6-9]|3\d)|[1-9]", z)})
    if unbekannt:
        warn.append("Zahlen nicht im Faktenspeicher: " + ", ".join(unbekannt[:25]))
    # Übernahme von der eigenen Website
    eigene = set()
    for p in EIGENE_TEXTE:
        if p.exists():
            eigene |= schindeln(p.read_text())
    gleich = schindeln(rumpf) & eigene
    if gleich:
        fehler.append(f"{len(gleich)} gleiche 8-Wort-Folgen wie auf wohnenambergpark.de, z. B. „{sorted(gleich)[0]}“")
    # interne Links
    vorhanden = {p.stem for p in (WURZEL / "inhalt").glob("*.md")} | \
                {p.stem for p in (WURZEL / "_entwuerfe").glob("*.md") if "." not in p.stem}
    geplant = set()
    plan = WURZEL / "planung" / "seitenplan.md"
    if plan.exists():
        geplant = set(re.findall(r"`([a-z0-9-]+)`", plan.read_text()))
    for ziel in re.findall(r"\]\(/([a-z0-9-]+)/?\)", rumpf):
        if ziel not in vorhanden | geplant:
            fehler.append(f"interner Link ins Leere: /{ziel}/")
    return fehler, warn


def main():
    gesamt = 0
    for arg in sys.argv[1:]:
        f, w = pruefe(Path(arg))
        print(f"== {arg}: {len(f)} Fehler, {len(w)} Warnungen")
        for x in f:
            print("  FEHLER ", x)
        for x in w:
            print("  WARNUNG", x)
        gesamt += len(f)
    sys.exit(1 if gesamt else 0)


if __name__ == "__main__":
    main()
