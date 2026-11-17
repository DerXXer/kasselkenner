#!/usr/bin/env python3
"""Termin-Wache kasselkenner.de (Aaron, 05.11.2026: bei neuen Terminen die Ersten sein).

Liest die offiziellen Seiten der Veranstalter und meldet jeden Satz mit einer Jahreszahl ab 2027, der seit dem letzten
Lauf neu ist. Der Nachtlauf ruft sie täglich auf; meldet sie etwas, wird der Termin noch am selben Tag geprüft,
in den Faktenspeicher eingetragen, die Seiten werden angepasst und an IndexNow gemeldet.

    python3 werkzeuge/terminwache.py          # prüfen; Rückgabe 1, wenn Neues da ist
    python3 werkzeuge/terminwache.py --alle   # alle gefundenen Sätze zeigen (ohne Stand zu ändern)

Erster Lauf je Quelle legt nur den Stand an. Stand: werkzeuge/.terminwache.json.
"""
import gzip, hashlib, html, json, os, re, ssl, sys, time, urllib.request

HIER = os.path.dirname(os.path.abspath(__file__))
STAND = os.path.join(HIER, ".terminwache.json")
JAHRE = ("2027", "2028")

# Thema → offizielle Quellen (Veranstalter zuerst). Seite, die bei Neuem angepasst wird, in Klammern.
QUELLEN = {
    "Wasserspiele (wasserspiele-kassel, bergpark-wilhelmshoehe)": [
        "https://www.heritage-kassel.de/besuch/wasserspiele",
        "https://www.kassel.de/buerger/kunst_und_kultur/parks_und_gaerten/wilhelmshoehe/wasserspiele.php",
    ],
    "Beleuchtete Wasserspiele (beleuchtete-wasserspiele)": [
        "https://www.kassel.de/beleuchtete-wasserspiele/index.php",
        "https://www.beleuchtete-wasserspiele.de",
    ],
    "Zissel (zissel-kassel)": [
        "https://www.zissel.de/",
        "https://www.zissel.de/programm",
    ],
    "documenta 16 (documenta-2027, documenta-uebernachten)": [
        "https://documentasixteen.com/de/besuch/faq",
        "https://documenta.de/de/news",
    ],
    "Weihnachtsmarkt (weihnachtsmarkt-kassel)": [
        "https://www.weihnachtsmarkt-kassel.de/",
    ],
}


def laden(url):
    """Seite holen: Browser-Kennung, gzip, drei Versuche mit Pause; Fehlertext nennt Art und Versuch."""
    kopf = {"User-Agent": "Mozilla/5.0 (compatible; kasselkenner-terminwache/1.1; +https://kasselkenner.de)",
            "Accept": "text/html,application/xhtml+xml", "Accept-Language": "de-DE,de;q=0.9",
            "Accept-Encoding": "gzip"}
    letzter = None
    for versuch in (1, 2, 3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=kopf), timeout=45,
                                        context=ssl.create_default_context()) as r:
                daten = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    daten = gzip.decompress(daten)
                return daten.decode(r.headers.get_content_charset() or "utf-8", "replace")
        except Exception as e:
            letzter = "%s: %s (Versuch %d)" % (type(e).__name__, str(e)[:120], versuch)
            if versuch < 3:
                time.sleep(5 * versuch)
    raise RuntimeError(letzter)


def text(url):
    roh = laden(url)
    roh = re.sub(r"(?is)<(script|style|noscript|svg)\b.*?</\1>", " ", roh)
    roh = re.sub(r"(?i)<br\s*/?>|</(p|li|h\d|div|tr|td|section|article)>", "\n", roh)
    t = html.unescape(re.sub(r"<[^>]+>", " ", roh))
    return [re.sub(r"\s+", " ", z).strip() for z in t.split("\n")]


def saetze(url):
    out = []
    for zeile in text(url):
        for s in re.split(r"(?<=[^\d\s][.!?])\s+(?=[A-ZÄÖÜ])", zeile):
            if any(j in s for j in JAHRE) and 12 <= len(s) <= 400:
                out.append(s)
    return list(dict.fromkeys(out))


def kennung(s):
    return hashlib.sha1(s.lower().encode()).hexdigest()[:16]


def main():
    alle = "--alle" in sys.argv
    stand = json.load(open(STAND)) if os.path.exists(STAND) else {}
    neu_gesamt, fehler = [], []
    for thema, urls in QUELLEN.items():
        for url in urls:
            try:
                gefunden = saetze(url)
            except Exception as e:
                fehler.append("%s: %s" % (url, str(e)[:200]))
                continue
            alt = stand.get(url)
            if alle:
                for s in gefunden:
                    print("%s | %s | %s" % (thema, url, s))
                continue
            if alt is None:
                stand[url] = [kennung(s) for s in gefunden]
                print("Stand angelegt: %s (%d Sätze mit %s)" % (url, len(gefunden), "/".join(JAHRE)))
                continue
            neu = [s for s in gefunden if kennung(s) not in alt]
            if neu:
                neu_gesamt += [(thema, url, s) for s in neu]
                stand[url] = sorted(set(alt) | {kennung(s) for s in gefunden})
    if not alle:
        json.dump(stand, open(STAND, "w"), indent=1)
    for thema, url, s in neu_gesamt:
        print("NEU | %s | %s\n      %s" % (thema, url, s))
    for f in fehler:
        print("NICHT ERREICHBAR | " + f)
    if not neu_gesamt and not alle:
        print("Keine neuen Termine (%d Quellen, %d nicht erreichbar)." % (sum(map(len, QUELLEN.values())), len(fehler)))
    return 1 if neu_gesamt else 0


if __name__ == "__main__":
    sys.exit(main())
