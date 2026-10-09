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
THEMEN = ["herkules-kassel", "loewenburg-kassel", "schloss-wilhelmshoehe", "beleuchtete-wasserspiele",
          "kassel-sehenswuerdigkeiten", "kassel-mit-kindern", "kassel-bei-regen", "weihnachtsmarkt-kassel",
          "grimmwelt-kassel", "orangerie-karlsaue", "kassel-wochenende", "kassel-geheimtipps", "zissel-kassel"]
START_DIAS = [("wasserspiele-kassel", "Bergpark · Saison 1. Mai bis 3. Oktober", "Wann laufen die Wasserspiele?", "Termine und Ablauf"),
              ("documenta-2027", "documenta 16 · Sommer 2027", "Was du zur documenta wissen musst", "Zum documenta-Ratgeber"),
              ("weihnachtsmarkt-kassel", "Innenstadt · Märchenweihnachtsmarkt", "Weihnachtsmarkt in Kassel", "Zeiten, Orte, Anreise"),
              ("bergpark-wilhelmshoehe", "UNESCO-Welterbe", "Der Bergpark Wilhelmshöhe", "Den Bergpark entdecken")]
EIGEN_BILD = "blick-vom-herkules.jpg"
# Startseite „Was hast du vor?“: (Titel, Satz, Hauptseite, weitere Seiten)
VORHABEN = [
    ("Bergpark & Wasserspiele", "Herkules, Kaskaden, Löwenburg: Kassels großer Park am Berg.", "bergpark-wilhelmshoehe",
     ["wasserspiele-kassel", "herkules-kassel", "loewenburg-kassel", "schloss-wilhelmshoehe", "parken-bergpark-wilhelmshoehe"]),
    ("documenta 2027", "Hundert Tage Kunst mitten in der Stadt.", "documenta-2027", ["documenta-uebernachten"]),
    ("Mit Kindern & bei Regen", "Märchen, Museen und Ideen, wenn das Wetter nicht mitspielt.", "kassel-mit-kindern",
     ["kassel-bei-regen", "grimmwelt-kassel", "orangerie-karlsaue"]),
    ("Übernachten & Wochenende", "Welcher Stadtteil passt zu dir, und wie du zwei Tage füllst.", "uebernachten-kassel",
     ["kassel-wochenende", "kassel-sehenswuerdigkeiten", "kassel-geheimtipps"]),
]
# „Gerade aktuell“: (von MMTT, bis MMTT, Jahr oder None, Seite, Dachzeile, Satz) – erster Treffer zum Bautag gilt
AKTUELL = [
    ("0721", "0805", None, "zissel-kassel", "Gerade aktuell", "Sommerfest an der Fulda: Boote, Musik und lange Abende am Wasser."),
    ("0611", "0920", 2027, "documenta-2027", "Gerade aktuell", "Die documenta läuft: Kunst an vielen Orten der Stadt."),
    ("1001", "1223", None, "weihnachtsmarkt-kassel", "Bald ist es so weit", "Bald leuchtet die Innenstadt: Märchen, Lichter und Glühwein."),
    ("1224", "0331", None, "kassel-bei-regen", "Winter in Kassel", "Wenn es draußen grau ist: Museen, warmes Wasser und Märchen drinnen."),
    ("0401", "1003", None, "wasserspiele-kassel", "Die Saison läuft", "Mittwochs, sonntags und feiertags rauscht das Wasser den Herkules hinab."),
]
# Empfehlungskarte: Klebeabstand so wählen, dass die ganze Karte im Fenster bleibt
EIGEN_JS = """<script>(function(){var e=document.querySelector('.seite .eigen');if(!e)return;var k=document.querySelector('.kopf'),o=(k?k.offsetHeight:68)+12;function f(){e.classList.remove('knapp');e.style.position='';var t=innerHeight-e.offsetHeight-16;if(t<o){e.classList.add('knapp');t=innerHeight-e.offsetHeight-16}if(t<o){e.style.position='static';return}e.style.top=Math.min(110,t)+'px'}addEventListener('resize',f);addEventListener('load',f);f()})();</script>"""
# Linienplan: Wasser „fließt“ beim Scrollen die Strecke hinab, erreichte Stationen leuchten orange
STRECKE_JS = """<script>(function(){var s=[].slice.call(document.querySelectorAll('.strecke'));if(!s.length)return;s.forEach(function(o){o.classList.add('lebt')});var w=0;function f(){w=0;var m=innerHeight*0.6;s.forEach(function(o){var r=o.getBoundingClientRect(),p=Math.max(0,Math.min(1,(m-r.top)/r.height));o.style.setProperty('--f',p.toFixed(3));[].forEach.call(o.children,function(l){var q=l.getBoundingClientRect();l.classList.toggle('an',q.top+q.height/2<m)})})}addEventListener('scroll',function(){if(!w){w=1;requestAnimationFrame(f)}},{passive:true});addEventListener('resize',f);f()})();</script>"""
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
            if reihen[0][0].lower() == "uhrzeit" and len(reihen[0]) == 2:
                punkte = "".join(f'<li><time>{inline(r[0].replace(" Uhr", ""))}</time><i class="p"></i><span>{inline(r[1])}</span></li>' for r in reihen[1:])
                aus.append(f'<ol class="strecke" aria-label="Ablauf mit Uhrzeiten">{punkte}</ol>')
                continue
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
            aus.append(f'<aside class="hinweis zettel blau"><b class="marke">Gut zu wissen</b><p>{inline(" ".join(teile))}</p></aside>')
            continue
        absatz = []
        while i < len(zeilen) and zeilen[i].strip() and not re.match(r"(#|\||- |\d+\. |> )", zeilen[i]):
            absatz.append(zeilen[i].strip())
            i += 1
        aus.append(f"<p>{inline(' '.join(absatz))}</p>")
    return "\n".join(aus), faq, toc


# Empfehlung in eigener Sache, je Thema passend (Fakten: Wissensspeicher Wohnen am Bergpark)
EMPFEHLUNG = {
    "park": ("Übernachte da, wo das Wasser fließt",
             "Wer am Bergpark schläft, ist morgens als Erster an den Kaskaden und muss abends nicht mehr ins Auto.",
             "Unser Tipp: die Wohnung „Herkules“ mit eigenem Garten und Whirlpool für bis zu 6 Personen."),
    "kunst": ("Kunst am Tag, Ruhe am Abend",
              "Mit der Linie 4 bist du schnell in der Innenstadt und abends zurück im Grünen am Bergpark.",
              "Für zwei: die Romantische Wohnung mit Balkon und Blick auf den Herkules."),
    "familie": ("Platz für die ganze Familie",
                "Mehr Raum als im Hotelzimmer, eine eigene Küche und der Bergpark gleich um die Ecke.",
                "Unser Tipp: die „Löwenburg“ mit zwei Schlafzimmern für bis zu 4 Personen."),
    "start": ("Dein Zuhause am Bergpark",
              "Zehn Ferienwohnungen in Bad Wilhelmshöhe, vom Apartment für zwei bis zur Wohnung mit Garten für sechs.",
              "Kostenlos parken an der Straße, die Linie 4 ganz in der Nähe."),
}
EMPFEHLUNG_THEMA = {s: "park" for s in ["wasserspiele-kassel", "beleuchtete-wasserspiele", "herkules-kassel", "bergpark-wilhelmshoehe",
                                        "loewenburg-kassel", "schloss-wilhelmshoehe", "parken-bergpark-wilhelmshoehe"]}
EMPFEHLUNG_THEMA.update({s: "kunst" for s in ["documenta-2027", "documenta-uebernachten"]})
EMPFEHLUNG_THEMA.update({s: "familie" for s in ["kassel-mit-kindern", "kassel-bei-regen", "grimmwelt-kassel", "orangerie-karlsaue"]})


def eigenwerbung(slug, tiefe):
    ziel = f"{BUCHEN}?utm_source=kasselkenner&utm_medium=referral&utm_campaign={slug}"
    titel, satz, tipp = EMPFEHLUNG[EMPFEHLUNG_THEMA.get(slug, "start")]
    return f"""<aside class="eigen" aria-label="In eigener Sache">
<figure class="polaroid"><img src="{tiefe}bilder/{Path(EIGEN_BILD).stem}.webp" alt="" width="640" height="400" loading="lazy"><figcaption>Unsere Empfehlung</figcaption></figure>
<div class="k"><p class="dach">In eigener Sache · Wohnen am Bergpark</p>
<h3>{titel}</h3>
<p>{satz}</p>
<p class="tipp">{tipp}</p>
<a class="knopf" href="{ziel}" rel="noopener">Wohnungen ansehen</a></div>
</aside>"""


def karten(slugs, alle, tiefe):
    aus = []
    for s in slugs:
        m = alle.get(s)
        if not m or not m.get("bild"):
            continue
        n = BILDNACHWEIS.get(m["bild"], {})
        aus.append(f'<a class="karte" href="{tiefe}{s}/"><figure class="polaroid"><img src="{tiefe}bilder/{Path(m["bild"]).stem}.webp" '
                   f'alt="{html.escape(n.get("alt", ""))}" width="1200" height="900" loading="lazy"><figcaption>{html.escape(m.get("kurz", ""))}</figcaption></figure>'
                   f'<h3>{html.escape(m["titel"].split(":")[0])}</h3><p>{html.escape(m.get("beschreibung", ""))}</p><span class="mehr">Weiterlesen</span></a>')
    return f'<div class="karten">{"".join(aus)}</div>' if aus else ""


def blick_lesen(text):
    paare = []
    for teil in (text or "").split("|"):
        if "=" in teil:
            k, v = teil.split("=", 1)
            paare.append((k.strip(), v.strip()))
    return paare


def kopf_und_fuss(slug, tiefe, alle):
    nav = "".join(f'<a href="{tiefe}{s}/"{" aria-current=\"page\"" if s == slug else ""}>{t}</a>' for s, t in NAV if s in alle)
    themen = "".join(f'<a href="{tiefe}{s}/"{" aria-current=\"page\"" if s == slug else ""}>{html.escape(alle[s].get("kurz", s))}</a>'
                     for s in THEMEN if s in alle)
    kopf = f"""<a class="sprung" href="#inhalt">Zum Inhalt</a>
<header class="kopf"><div class="breite">
<a class="wortmarke" href="{tiefe or './'}" aria-label="{NAME} – Startseite"><b>KASSEL</b><i>kenner.</i></a>
<nav class="haupt" aria-label="Hauptnavigation">{nav}</nav>
</div></header>
<nav class="themen" aria-label="Themen"><div class="breite">{themen}</div></nav>"""
    fuss_links = " · ".join(f'<a href="{tiefe}{s}/">{t}</a>' for s, t in FUSS)
    fuss = f"""<footer class="fuss"><div class="breite">
<div class="wortmarke"><b>KASSEL</b><i>kenner.</i></div>
<p>Bergpark, Wasserspiele und documenta: Tipps für deinen Besuch in Kassel. Angaben ohne Gewähr; Termine und Preise ändern sich, im Zweifel gilt die Seite des Veranstalters.</p>
<p>{fuss_links}</p>
</div></footer>"""
    return kopf, fuss


def titelbild_tag(bild, tiefe, attr=""):
    n = BILDNACHWEIS.get(bild, {})
    return f'<img src="{tiefe}bilder/{Path(bild).stem}.webp" alt="{html.escape(n.get("alt", ""))}" width="1200" height="675"{attr}>'



def quellen_block(rumpf):
    """Trennt „## Quellen“ ab und baut daraus einen kompakten Kasten: je Herausgeber eine Zeile,
    das Abrufdatum nur einmal (Aaron, 09.10.2026: Quellen kompakter und schöner)."""
    m = re.search(r"\n## Quellen\n(.*?)(?=\n## |\Z)", rumpf, re.S)
    if not m:
        return rumpf, ""
    gruppen, daten = {}, set()
    for z in re.finditer(r"^- \[([^\]]+)\]\(([^)]+)\)(?:,\s*abgerufen\s*([\d.]+))?", m.group(1), re.M):
        name, url, datum = z.groups()
        wer, _, was = name.partition(", ")
        gruppen.setdefault(wer, []).append((was or wer, url))
        if datum:
            daten.add(datum)
    if not gruppen:
        return rumpf, ""
    stand = f'<span class="q-stand">abgerufen am {max(daten, key=lambda d: d.split(".")[::-1])}</span>' if daten else ""
    zeilen = "".join(f'<li><b>{html.escape(w)}</b> ' + " · ".join(f'<a href="{html.escape(u)}" rel="noopener">{html.escape(x)}</a>' for x, u in l) + "</li>"
                     for w, l in gruppen.items())
    kasten = f'<section class="quellen" id="quellen"><h2 class="q-titel">Quellen {stand}</h2><ul>{zeilen}</ul></section>'
    return rumpf[:m.start()] + rumpf[m.end():], kasten

def seite(meta, inhalt_html, faq, toc, alle):
    slug = meta["slug"]
    url = DOMAIN + ("/" if slug == "index" else f"/{slug}/")
    tiefe = "" if slug == "index" else "../"
    stand = meta.get("stand", date.today().isoformat())
    bild = meta.get("bild")
    art_seite = meta.get("art", "artikel")
    schema = [{"@context": "https://schema.org", "@type": "Organization", "@id": DOMAIN + "/#org",
               "name": NAME, "url": DOMAIN + "/", "logo": DOMAIN + "/logo.svg",
               "parentOrganization": {"@type": "Organization", "name": "Wohnen am Bergpark UG (haftungsbeschränkt)",
                                      "url": "https://wohnenambergpark.de/"}}]
    if slug == "index":
        schema.append({"@context": "https://schema.org", "@type": "WebSite", "name": NAME, "url": DOMAIN + "/",
                       "inLanguage": "de", "publisher": {"@id": DOMAIN + "/#org"}})
    elif art_seite == "artikel":
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
    kopf, fuss = kopf_und_fuss(slug, tiefe, alle)

    # H1 und ersten Absatz herauslösen
    h1 = re.search(r"<h1>(.*?)</h1>", inhalt_html, re.S)
    h1_text = h1.group(1) if h1 else html.escape(meta["titel"])
    rest = inhalt_html[h1.end():] if h1 else inhalt_html
    erster = re.match(r"\s*<p>(.*?)</p>", rest, re.S)
    lede = erster.group(1) if erster else ""
    if erster:
        rest = rest[erster.end():]

    if slug == "index":
        koerper = startseite(meta, h1_text, lede, rest, alle)
    elif art_seite != "artikel":
        koerper = f"""<section class="held ohne-bild schlicht"><div class="text"><div class="breite"><h1 class="gross" style="font-size:clamp(38px,6vw,64px)">{h1_text}</h1></div></div></section>
<main id="inhalt" class="breite" style="max-width:820px;padding-top:36px">{'<p>' + lede + '</p>' if lede else ''}{rest}</main>"""
    else:
        lang = " lang" if len(re.sub("<.*?>", "", h1_text)) > 34 else ""
        groesse = ' style="font-size:clamp(36px,5.4vw,68px)"' if lang else ""
        if bild:
            n = BILDNACHWEIS.get(bild, {})
            held = f"""<section class="held">{titelbild_tag(bild, tiefe, ' fetchpriority="high"')}
<div class="text"><div class="breite"><div class="krumen"><a href="{tiefe or './'}">Start</a> / {html.escape(meta.get("kurz", ""))}</div><h1 class="gross"{groesse}>{h1_text}</h1></div></div>
<div class="foto">Foto: {html.escape(n.get("urheber", ""))}, {html.escape(n.get("lizenz", ""))} · <a href="{tiefe}bildnachweise/">Nachweis</a></div></section>"""
        else:
            held = f'<section class="held ohne-bild"><div class="text"><div class="breite"><h1 class="gross"{groesse}>{h1_text}</h1></div></div></section>'
        blick = blick_lesen(meta.get("blick"))
        blick_html = ('<div class="blick"><b class="marke">Auf einen Blick</b><dl>' +
                      "".join(f"<dt>{html.escape(k)}</dt><dd>{inline(v)}</dd>" for k, v in blick) + "</dl></div>") if blick else ""
        # Gelber Zettel = Zusammenfassung ohne Zahlen, weiße Karte = harte Fakten (Aaron, 09.10.2026)
        anpinnen = f"""<section class="anpinnen"><div class="breite">
<div class="zettel"><b class="marke">Kurz gesagt</b><p>{lede}</p></div>{blick_html}
</div></section>""" if lede else ""
        autor = f"""<div class="autor"><span class="kreis" aria-hidden="true">AS</span><div><a href="{tiefe}ueber-uns/"><strong>Aaron Schiele</strong></a><br>geprüft am {date.fromisoformat(stand).strftime("%d.%m.%Y")}</div></div>"""
        werbung_an = meta.get("eigenwerbung", "ja") == "ja"
        offen = ""  # Kennzeichnung über die Karte „In eigener Sache“ (Aaron, 09.10.2026: nicht auf jeder Seite)
        verzeichnis = ""
        if len(toc) >= 4:
            verzeichnis = '<nav class="toc" aria-label="Auf dieser Seite"><p class="dach">Auf dieser Seite</p><ol>' + \
                "".join(f'<li><a href="#{a}">{html.escape(t)}</a></li>' for a, t in toc) + "</ol></nav>"
        weiter = ""
        if meta.get("weiter"):
            k = karten([x.strip() for x in meta["weiter"].split(",")], alle, tiefe)
            if k:
                weiter = f'<section class="weiter"><h2>Weiterlesen</h2>{k}</section>'
        koerper = f"""{held}
{anpinnen}
<div class="breite raster">
<main id="inhalt">
{autor}
{offen}
{rest}
{weiter}
</main>
<div class="seite">{verzeichnis}{eigenwerbung(slug, tiefe) if werbung_an else ""}</div>
</div>"""
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
<meta name="theme-color" content="#5B1E2D">
<link rel="icon" href="{tiefe}logo.svg" type="image/svg+xml">
<link rel="preload" href="{tiefe}schriften/Archivo-normal-600_900.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="{tiefe}stil.css">
{ld}
</head>
<body>
{kopf}
{koerper}
{fuss}
</body>
</html>
"""


def startseite(meta, h1_text, lede, rest, alle):
    dias, reiter = [], []
    for nr, (s, dach, frage, knopf) in enumerate([d for d in START_DIAS if d[0] in alle and alle[d[0]].get("bild")]):
        m = alle[s]
        titel = html.escape(frage)
        dias.append(f"""<div class="dia{' an' if nr == 0 else ''}">{titelbild_tag(m["bild"], "", ' fetchpriority="high"' if nr == 0 else ' loading="lazy"')}
<div class="text"><div class="breite"><div class="dach">{html.escape(dach)}</div><p class="gross">{titel}</p><a class="knopf" href="{s}/">{html.escape(knopf)}</a></div></div></div>""")
        reiter.append(f'<button type="button"{" class=\"an\"" if nr == 0 else ""} aria-label="{html.escape(m.get("kurz", s))}"><img src="bilder/{Path(m["bild"]).stem}.webp" alt="" width="240" height="180" loading="lazy"><span class="cap">{html.escape(m.get("kurz", s))}</span><span class="balken"><i></i></span></button>')
    buehne = f"""<section class="buehne" aria-label="Aktuelle Themen">{"".join(dias)}
<div class="reiter"><div class="breite">{"".join(reiter)}</div></div></section>""" if dias else ""
    stapel = f"""<div class="stapel"><figure class="polaroid">{titelbild_tag(EIGEN_BILD, "", ' loading="lazy"')}<figcaption>Blick vom Herkules</figcaption></figure>
<div class="zettel notiz"><i class="pin" aria-hidden="true"></i><b class="marke">Nicht vergessen!</b><p>Über 500 Stufen, kein Geländer: Feste Schuhe an, Puste mitbringen. Und oben einmal umdrehen, der Blick lohnt jede Stufe.</p><span class="unterschrift">Aaron</span></div></div>"""
    alle_artikel = [s for s, m in alle.items() if m.get("art", "artikel") == "artikel" and s != "index"]
    vorhaben = []
    for titel, satz, haupt, mehr in VORHABEN:
        m = alle.get(haupt)
        if not m or not m.get("bild"):
            continue
        links = "".join(f'<li><a href="{s}/">{html.escape(alle[s].get("kurz", s))}</a></li>' for s in mehr if s in alle)
        vorhaben.append(f"""<div class="vorhaben"><a href="{haupt}/"><figure class="polaroid"><img src="bilder/{Path(m["bild"]).stem}.webp" alt="" width="1200" height="900" loading="lazy"><figcaption>{html.escape(titel)}</figcaption></figure></a>
<p>{html.escape(satz)}</p><ul>{links}</ul></div>""")
    vorhaben_html = f"""<section class="breite" style="padding-top:24px"><div class="mitte"><h2>Was hast du vor?</h2></div><div class="vorhaben-raster">{"".join(vorhaben)}</div></section>""" if vorhaben else ""
    heute = date.today()
    md = heute.strftime("%m%d")
    aktuell_html = ""
    for von, bis, jahr, s, dach, satz in AKTUELL:
        drin = (von <= md <= bis) if von <= bis else (md >= von or md <= bis)
        if drin and (jahr is None or jahr == heute.year) and s in alle and alle[s].get("bild"):
            m = alle[s]
            aktuell_html = f"""<section class="breite aktuell"><figure class="polaroid">{titelbild_tag(m["bild"], "", ' loading="lazy"')}<figcaption>{html.escape(m.get("kurz", ""))}</figcaption></figure>
<div class="zettel"><b class="marke">{html.escape(dach)}</b><p class="gross-zettel">{html.escape(m["titel"].split(":")[0])}</p><p>{html.escape(satz)}</p><a class="mehr" href="{s}/">Alles dazu lesen</a></div></section>"""
            break
    skript = """<script>(function(){var d=[].slice.call(document.querySelectorAll('.dia')),b=[].slice.call(document.querySelectorAll('.reiter button')),i=0,t;if(d.length<2)return;function z(n){d[i].classList.remove('an');b[i].classList.remove('an');i=n;d[i].classList.add('an');void b[i].offsetWidth;b[i].classList.add('an');clearTimeout(t);t=setTimeout(function(){z((i+1)%d.length)},7000)}b.forEach(function(x,k){x.onclick=function(){z(k)}});z(0)})();</script>"""
    return f"""{buehne}
<main id="inhalt">
<section class="breite start-intro"><div><h1>{h1_text}</h1><p class="lede">{lede}</p></div>{stapel}</section>
{vorhaben_html}
{aktuell_html}
<section class="breite" style="padding-top:72px"><div class="mitte"><h2>Alle Ratgeber</h2></div>{karten(alle_artikel, alle, "")}</section>
</main>
{skript}"""


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
    """Je Bild eine WebP-Fassung (Seite) und eine kleine JPEG-Fassung (Vorschaubild für Teilen)."""
    ziel = AUS / "bilder"
    ziel.mkdir(parents=True, exist_ok=True)
    for name in benutzt:
        q = BILDER / name
        if not q.exists():
            print("FEHLT Bild:", name, file=sys.stderr)
            continue
        webp = ziel / (Path(name).stem + ".webp")
        if not webp.exists() or webp.stat().st_mtime < q.stat().st_mtime:
            for breite, qual in ((1200, 55), (1000, 45)):
                subprocess.run(["cwebp", "-quiet", "-q", str(qual), "-resize", str(breite), "0", "-sharp_yuv",
                                str(q), "-o", str(webp)], capture_output=True)
                if webp.exists() and webp.stat().st_size < 250_000:
                    break
        jpg = ziel / name
        if not jpg.exists() or jpg.stat().st_mtime < q.stat().st_mtime:
            subprocess.run(["sips", "-Z", "1200", "-s", "format", "jpeg", "-s", "formatOptions", "low", str(q),
                            "--out", str(jpg)], capture_output=True)


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
        rumpf, quellen = quellen_block(rumpf)
        h, faq, toc = markdown(rumpf)
        if quellen:
            h += "\n" + quellen
            toc.append(("quellen", "Quellen"))
        if meta.get("bild"):
            benutzt.add(meta["bild"])
        ziel = AUS / "index.html" if slug == "index" else AUS / slug / "index.html"
        ziel.parent.mkdir(parents=True, exist_ok=True)
        text = seite(meta, h, faq, toc, alle)
        if 'class="eigen"' in text:
            text = text.replace("</body>", EIGEN_JS + "\n</body>", 1)
        if 'class="strecke"' in text:
            text = text.replace("</body>", STRECKE_JS + "\n</body>", 1)
        ziel.write_text(text)
    benutzt.add(EIGEN_BILD)
    bilder_kopieren(benutzt)
    shutil.copy(WURZEL / "vorlage" / "logo.svg", AUS / "logo.svg")
    (AUS / "stil.css").write_text((WURZEL / "vorlage" / "schriften.css").read_text() + (WURZEL / "vorlage" / "stil.css").read_text())
    shutil.copytree(WURZEL / "vorlage" / "schriften", AUS / "schriften", dirs_exist_ok=True)
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
    (AUS / "CNAME").write_text("kasselkenner.de")
    (AUS / ".nojekyll").write_text("")
    if "404" in seiten:
        shutil.copy(AUS / "404" / "index.html", AUS / "404.html")
    print(f"gebaut: {len(seiten)} Seiten, {len(benutzt)} Bilder → {AUS}")


if __name__ == "__main__":
    main()
