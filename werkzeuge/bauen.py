#!/usr/bin/env python3
"""Baut kasselkenner.de aus inhalt/*.md nach docs/ (GitHub Pages).

Nur Standardbibliothek, damit der Nachtlauf ohne Installationen läuft.
Seitenformat: Kopf zwischen '---'-Zeilen (schluessel: wert), danach ein
kleines Markdown: # bis ###, Absätze, - Listen, 1. Listen, | Tabellen |,
**fett**, [Text](Link), > Hinweis. Ein Abschnitt '## Häufige Fragen' mit
'### Frage' + Antwort wird zusätzlich als FAQPage ausgegeben.
"""
import html, json, re, shutil, subprocess, sys
from datetime import date
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
INHALT, AUS, BILDER = WURZEL / "inhalt", WURZEL / "docs", WURZEL / "bilder"
DOMAIN = "https://kasselkenner.de"
NAME = "Kasselkenner"
UNTERZEILE = "Bergpark, Wasserspiele und documenta – von Gastgebern aus Bad Wilhelmshöhe"
AUTOR = {"@type": "Person", "name": "Aaron Schiele", "url": DOMAIN + "/ueber-uns/"}
BUCHEN = "https://wohnenambergpark.de/de/alle-ferienwohnungen"
NAV = [("wasserspiele-kassel", "Wasserspiele"), ("bergpark-wilhelmshoehe", "Bergpark"),
       ("documenta-2027", "documenta 2027"), ("parken-bergpark-wilhelmshoehe", "Parken & Anreise"),
       ("uebernachten-kassel", "Übernachten")]
FUSS = [("ueber-uns", "Über uns"), ("bildnachweise", "Bildnachweise"),
        ("impressum", "Impressum"), ("datenschutz", "Datenschutz")]


def kopf_lesen(text):
    if not text.startswith("---"):
        return {}, text
    _, kopf, rumpf = text.split("---", 2)
    meta = {}
    for zeile in kopf.strip().splitlines():
        if ":" in zeile:
            k, v = zeile.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, rumpf.lstrip("\n")


def inline(t):
    t = html.escape(t, quote=False)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)

    def link(m):
        text, ziel = m.group(1), m.group(2)
        extern = ziel.startswith("http") and not ziel.startswith(DOMAIN)
        attr = ' rel="noopener"' if extern else ""
        return f'<a href="{html.escape(ziel)}"{attr}>{text}</a>'
    return re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", link, t)


def anker(t):
    t = t.lower().translate(str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}))
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def markdown(rumpf):
    """Gibt (html, faq-liste, inhaltsverzeichnis) zurück."""
    aus, faq, toc = [], [], []
    zeilen = rumpf.splitlines()
    i, in_faq = 0, False
    while i < len(zeilen):
        z = zeilen[i]
        if not z.strip():
            i += 1
            continue
        m = re.match(r"(#{1,3}) (.+)", z)
        if m:
            ebene, text = len(m.group(1)), m.group(2).strip()
            if ebene == 2:
                in_faq = text.lower().startswith("häufige fragen")
                toc.append((anker(text), text))
            if ebene == 3 and in_faq:
                antwort = []
                i += 1
                while i < len(zeilen) and not zeilen[i].startswith("#"):
                    if zeilen[i].strip():
                        antwort.append(zeilen[i].strip())
                    i += 1
                a = " ".join(antwort)
                faq.append((text, re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", a).replace("**", "")))
                aus.append(f'<details class="faq"><summary>{inline(text)}</summary><p>{inline(a)}</p></details>')
                continue
            if ebene == 1:
                aus.append(f"<h1>{inline(text)}</h1>")
            else:
                aus.append(f'<h{ebene} id="{anker(text)}">{inline(text)}</h{ebene}>')
            i += 1
            continue
        if z.startswith("|"):
            reihen = []
            while i < len(zeilen) and zeilen[i].startswith("|"):
                if not re.match(r"^\|[\s:|-]+\|$", zeilen[i]):
                    reihen.append([c.strip() for c in zeilen[i].strip("|").split("|")])
                i += 1
            kopf = "".join(f"<th>{inline(c)}</th>" for c in reihen[0])
            koerper = "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in reihen[1:])
            aus.append(f'<div class="tabelle"><table><thead><tr>{kopf}</tr></thead><tbody>{koerper}</tbody></table></div>')
            continue
        if re.match(r"(- |\d+\. )", z):
            geordnet = bool(re.match(r"\d+\. ", z))
            punkte = []
            while i < len(zeilen) and re.match(r"(- |\d+\. )", zeilen[i]):
                punkte.append(re.sub(r"^(- |\d+\. )", "", zeilen[i]))
                i += 1
            tag = "ol" if geordnet else "ul"
            aus.append(f"<{tag}>" + "".join(f"<li>{inline(p)}</li>" for p in punkte) + f"</{tag}>")
            continue
        if z.startswith("> "):
            teile = []
            while i < len(zeilen) and zeilen[i].startswith(">"):
                teile.append(zeilen[i][1:].strip())
                i += 1
            aus.append(f'<aside class="hinweis"><p>{inline(" ".join(teile))}</p></aside>')
            continue
        absatz = []
        while i < len(zeilen) and zeilen[i].strip() and not re.match(r"(#|\||- |\d+\. |> )", zeilen[i]):
            absatz.append(zeilen[i].strip())
            i += 1
        aus.append(f"<p>{inline(' '.join(absatz))}</p>")
    return "\n".join(aus), faq, toc


def eigenwerbung(slug):
    ziel = f"{BUCHEN}?utm_source=kasselkenner&utm_medium=referral&utm_campaign={slug}"
    return f"""<aside class="eigen" aria-label="In eigener Sache">
<p class="eigen-marke">In eigener Sache</p>
<p>Kasselkenner schreiben die Gastgeber von <strong>Wohnen am Bergpark</strong>. Unsere Ferienwohnungen liegen in Bad Wilhelmshöhe, ein paar Gehminuten vom Bergpark entfernt, die Straßenbahn Linie 4 hält vor der Tür.</p>
<p><a class="knopf" href="{ziel}" rel="noopener">Ferienwohnungen am Bergpark ansehen</a></p>
</aside>"""


def seite(meta, inhalt_html, faq, toc, alle):
    slug = meta["slug"]
    url = DOMAIN + ("/" if slug == "index" else f"/{slug}/")
    tiefe = "" if slug == "index" else "../"
    stand = meta.get("stand", date.today().isoformat())
    bild = meta.get("bild")
    schema = [{"@context": "https://schema.org", "@type": "Organization", "@id": DOMAIN + "/#org",
               "name": NAME, "url": DOMAIN + "/", "logo": DOMAIN + "/logo.svg",
               "parentOrganization": {"@type": "Organization", "name": "Wohnen am Bergpark UG (haftungsbeschränkt)",
                                      "url": "https://wohnenambergpark.de/"}}]
    if slug == "index":
        schema.append({"@context": "https://schema.org", "@type": "WebSite", "name": NAME, "url": DOMAIN + "/",
                       "inLanguage": "de", "publisher": {"@id": DOMAIN + "/#org"}})
    elif meta.get("art", "artikel") == "artikel":
        art = {"@context": "https://schema.org", "@type": "Article", "headline": meta["titel"],
               "description": meta.get("beschreibung", ""), "inLanguage": "de", "url": url,
               "datePublished": meta.get("veroeffentlicht", stand), "dateModified": stand,
               "author": AUTOR, "publisher": {"@id": DOMAIN + "/#org"}}
        if bild:
            art["image"] = f"{DOMAIN}/bilder/{bild}"
        schema.append(art)
        schema.append({"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": NAME, "item": DOMAIN + "/"},
            {"@type": "ListItem", "position": 2, "name": meta.get("kurz", meta["titel"]), "item": url}]})
    if faq:
        schema.append({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": f, "acceptedAnswer": {"@type": "Answer", "text": a}} for f, a in faq]})
    nav = "".join(f'<a href="{tiefe}{s}/"{" aria-current=\"page\"" if s == slug else ""}>{t}</a>' for s, t in NAV)
    fuss = " · ".join(f'<a href="{tiefe}{s}/">{t}</a>' for s, t in FUSS)
    titelbild = ""
    if bild:
        nachweis = BILDNACHWEIS.get(bild, {})
        titelbild = (f'<figure class="titelbild"><img src="{tiefe}bilder/{bild}" alt="{html.escape(nachweis.get("alt", ""))}" '
                     f'width="1600" height="900" fetchpriority="high"><figcaption>Foto: {html.escape(nachweis.get("urheber", ""))}, '
                     f'{html.escape(nachweis.get("lizenz", ""))} · <a href="{tiefe}bildnachweise/">Nachweis</a></figcaption></figure>')
    verzeichnis = ""
    if len(toc) >= 4:
        verzeichnis = '<nav class="toc" aria-label="Auf dieser Seite"><p>Auf dieser Seite</p><ol>' + \
            "".join(f'<li><a href="#{a}">{html.escape(t)}</a></li>' for a, t in toc) + "</ol></nav>"
    # Titelbild direkt nach der H1 einsetzen
    teile = inhalt_html.split("</h1>", 1)
    if len(teile) == 2:
        stand_zeile = f'<p class="stand">Stand: {date.fromisoformat(stand).strftime("%d.%m.%Y")} · von <a href="{tiefe}ueber-uns/">Aaron Schiele</a></p>' \
            if meta.get("art", "artikel") == "artikel" else ""
        inhalt_html = teile[0] + "</h1>" + stand_zeile + titelbild + verzeichnis + teile[1]
    werbung = eigenwerbung(slug) if meta.get("eigenwerbung", "ja") == "ja" else ""
    weiter = ""
    if meta.get("weiter"):
        links = []
        for s in [x.strip() for x in meta["weiter"].split(",")]:
            if s in alle:
                links.append(f'<li><a href="{tiefe}{s}/">{html.escape(alle[s].get("kurz", alle[s]["titel"]))}</a></li>')
        if links:
            weiter = '<nav class="weiter" aria-label="Weiterlesen"><h2>Weiterlesen</h2><ul>' + "".join(links) + "</ul></nav>"
    ld = "\n".join(f'<script type="application/ld+json">{json.dumps(s, ensure_ascii=False)}</script>' for s in schema)
    og_bild = f'<meta property="og:image" content="{DOMAIN}/bilder/{bild}">' if bild else ""
    return f"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(meta["titel"])}</title>
<meta name="description" content="{html.escape(meta.get("beschreibung", ""))}">
<link rel="canonical" href="{url}">
{'<meta name="robots" content="noindex">' if meta.get("robots") == "noindex" else ""}
<meta property="og:type" content="{'website' if slug == 'index' else 'article'}">
<meta property="og:title" content="{html.escape(meta["titel"])}">
<meta property="og:description" content="{html.escape(meta.get("beschreibung", ""))}">
<meta property="og:url" content="{url}">
<meta property="og:locale" content="de_DE">
<meta property="og:site_name" content="{NAME}">
{og_bild}
<link rel="icon" href="{tiefe}logo.svg" type="image/svg+xml">
<link rel="stylesheet" href="{tiefe}stil.css">
{ld}
</head>
<body>
<a class="sprung" href="#inhalt">Zum Inhalt</a>
<header class="kopf"><div class="breite">
<a class="marke" href="{tiefe or './'}"><img src="{tiefe}logo.svg" alt="" width="32" height="32"><span><b>{NAME}</b><small>{UNTERZEILE}</small></span></a>
<nav class="haupt" aria-label="Hauptnavigation">{nav}</nav>
</div></header>
<main id="inhalt" class="breite text">
{inhalt_html}
{werbung}
{weiter}
</main>
<footer class="fuss"><div class="breite">
<p><b>{NAME}</b> – unabhängige Tipps für deinen Besuch in Kassel. Angaben ohne Gewähr; Termine und Preise ändern sich, im Zweifel gilt die Seite des Veranstalters.</p>
<p>{fuss}</p>
</div></footer>
</body>
</html>
"""


BILDNACHWEIS = {}


def nachweise_lesen():
    datei = BILDER / "nachweise.md"
    if not datei.exists():
        return
    for z in datei.read_text().splitlines():
        if z.startswith("|") and not z.startswith("|---") and "Datei" not in z:
            c = [x.strip() for x in z.strip("|").split("|")]
            if len(c) >= 7:
                BILDNACHWEIS[c[0]] = {"motiv": c[1], "urheber": c[2], "lizenz": c[3],
                                      "lizenz_url": c[4], "seite": c[5], "alt": c[6]}


def bilder_kopieren(benutzt):
    ziel = AUS / "bilder"
    ziel.mkdir(parents=True, exist_ok=True)
    for name in benutzt:
        q = BILDER / name
        if not q.exists():
            print("FEHLT Bild:", name, file=sys.stderr)
            continue
        z = ziel / name
        if not z.exists() or z.stat().st_mtime < q.stat().st_mtime:
            shutil.copy(q, z)
            # auf 1600 px Breite begrenzen, JPEG-Qualität 72 (macOS sips)
            subprocess.run(["sips", "-Z", "1600", "-s", "formatOptions", "72", str(z)], capture_output=True)


def main():
    nachweise_lesen()
    seiten = {}
    for f in sorted(INHALT.glob("*.md")):
        meta, rumpf = kopf_lesen(f.read_text())
        meta.setdefault("slug", f.stem)
        seiten[meta["slug"]] = (meta, rumpf)
    if AUS.exists():
        for p in AUS.iterdir():
            if p.name != "bilder":
                shutil.rmtree(p) if p.is_dir() else p.unlink()
    AUS.mkdir(exist_ok=True)
    if BILDNACHWEIS:
        zeilen = ["| Bild | Urheber | Lizenz | Quelle |", "|---|---|---|---|"]
        for datei, n in sorted(BILDNACHWEIS.items()):
            zeilen.append(f"| {n['motiv']} | {n['urheber']} | [{n['lizenz']}]({n['lizenz_url']}) | [Wikimedia Commons]({n['seite']}) |")
        rumpf = ("# Bildnachweise\n\nDie Fotos auf Kasselkenner stehen unter freien Lizenzen. Danke an alle Fotografinnen und Fotografen.\n\n"
                 + "\n".join(zeilen) + "\n")
        seiten["bildnachweise"] = ({"titel": "Bildnachweise | Kasselkenner", "beschreibung": "Urheber und Lizenzen der Fotos auf kasselkenner.de.",
                                    "slug": "bildnachweise", "art": "rechtliches", "eigenwerbung": "nein", "sitemap": "nein"}, rumpf)
    alle = {s: m for s, (m, _) in seiten.items()}
    benutzt = set()
    for slug, (meta, rumpf) in seiten.items():
        h, faq, toc = markdown(rumpf)
        if meta.get("bild"):
            benutzt.add(meta["bild"])
        ziel = AUS / "index.html" if slug == "index" else AUS / slug / "index.html"
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_text(seite(meta, h, faq, toc, alle))
    bilder_kopieren(benutzt)
    for datei in ("stil.css", "logo.svg"):
        shutil.copy(WURZEL / "vorlage" / datei, AUS / datei)
    heute = date.today().isoformat()
    karte = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for slug, (meta, _) in seiten.items():
        if meta.get("sitemap", "ja") == "nein" or meta.get("robots") == "noindex":
            continue
        loc = DOMAIN + ("/" if slug == "index" else f"/{slug}/")
        karte.append(f"<url><loc>{loc}</loc><lastmod>{meta.get('stand', heute)}</lastmod></url>")
    karte.append("</urlset>")
    (AUS / "sitemap.xml").write_text("\n".join(karte))
    (AUS / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {DOMAIN}/sitemap.xml\n")
    llms = [f"# {NAME}", "", f"> {UNTERZEILE}. Praktische, geprüfte Antworten für Besucher in Kassel; "
            "jede Angabe mit Quelle und Prüfdatum. Betrieben von den Gastgebern von Wohnen am Bergpark (Kassel-Bad Wilhelmshöhe).", "", "## Seiten", ""]
    for slug, (meta, _) in seiten.items():
        if meta.get("art", "artikel") == "artikel":
            llms.append(f"- [{meta['titel']}]({DOMAIN}/{slug}/): {meta.get('beschreibung', '')}")
    (AUS / "llms.txt").write_text("\n".join(llms) + "\n")
    (AUS / "CNAME").write_text("kasselkenner.de\n")
    (AUS / ".nojekyll").write_text("")
    if "404" in seiten:
        shutil.copy(AUS / "404" / "index.html", AUS / "404.html")
    print(f"gebaut: {len(seiten)} Seiten, {len(benutzt)} Bilder → {AUS}")


if __name__ == "__main__":
    main()
