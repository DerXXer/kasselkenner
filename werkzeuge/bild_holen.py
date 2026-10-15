#!/usr/bin/env python3
"""Holt ein Bild von Wikimedia Commons in bilder/ und trägt den Nachweis ein (15.10.2026).

    python3 werkzeuge/bild_holen.py <Commons-Dateiseite oder File:…> <datei.jpg> "<Motiv>" "<Alt-Text>"

Lizenz und Urheber kommen aus den Commons-Metadaten, nicht aus der Recherche; erlaubt sind nur gemeinfrei, CC0,
CC BY und CC BY-SA. Geholt wird die 1920er Vorschaufassung (wie bei allen Bildern, siehe Kopf von bilder/nachweise.md).
"""
import html, json, re, sys, urllib.parse, urllib.request
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
NACHWEISE = WURZEL / "bilder" / "nachweise.md"
UA = {"User-Agent": "kasselkenner.de Bildnachweis (kontakt@kasselkenner.de)"}
ERLAUBT = re.compile(r"^(cc0|pd|public domain|cc by(-sa)? [\d.]+( [a-z]{2})?)$", re.I)


def holen(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read()


def ohne_html(t):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", t or ""))).strip()


def main(quelle, datei, motiv, alt):
    titel = urllib.parse.unquote(quelle.split("/wiki/")[-1]).replace("_", " ")
    if not titel.startswith("File:"):
        titel = "File:" + titel
    if f"| {datei} |" in NACHWEISE.read_text():
        print(f"{datei}: schon eingetragen"); return 0
    api = ("https://commons.wikimedia.org/w/api.php?action=query&format=json&prop=imageinfo&iiprop=url|size|extmetadata"
           "&iiurlwidth=1920&titles=" + urllib.parse.quote(titel))
    seite = next(iter(json.loads(holen(api))["query"]["pages"].values()))
    info = seite["imageinfo"][0]
    meta = {k: v.get("value", "") for k, v in info["extmetadata"].items()}
    lizenz = ohne_html(meta.get("LicenseShortName"))
    if not ERLAUBT.match(lizenz):
        print(f"{datei}: Lizenz „{lizenz}“ nicht erlaubt", file=sys.stderr); return 1
    if info["width"] < 1600:
        print(f"{datei}: nur {info['width']} px breit", file=sys.stderr); return 1
    urheber = ohne_html(meta.get("Attribution") or meta.get("Artist")) or "unbekannt"
    lizenz_url = meta.get("LicenseUrl") or ("https://creativecommons.org/publicdomain/zero/1.0/" if "0" in lizenz else "")
    ziel = WURZEL / "bilder" / datei
    ziel.write_bytes(holen(info.get("thumburl") or info["url"]))
    dateiseite = "https://commons.wikimedia.org/wiki/" + urllib.parse.quote(titel.replace(" ", "_"), safe=":/(),")
    with NACHWEISE.open("a") as f:
        f.write(f"| {datei} | {motiv} | {urheber} | {lizenz} | {lizenz_url} | {dateiseite} | {alt} |\n")
    print(f"{datei}: {info['width']} px, {lizenz}, {urheber}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 5:
        sys.exit(__doc__)
    sys.exit(main(*sys.argv[1:]))
