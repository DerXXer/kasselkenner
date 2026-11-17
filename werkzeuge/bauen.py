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
AUTOR_ID = DOMAIN + "/ueber-uns/#aaron"
AUTOR = {"@type": "Person", "@id": AUTOR_ID, "name": "Aaron Schiele", "url": DOMAIN + "/ueber-uns/",
         "jobTitle": "Gastgeber in Kassel-Bad Wilhelmshöhe", "image": DOMAIN + "/aaron.jpg",
         "worksFor": {"@type": "Organization", "name": "Wohnen am Bergpark", "url": "https://wohnenambergpark.de/"}}
INDEXNOW = "408dcd67b168f09d160b92ca4366c418"
# Besucherzähler Cloudflare Web Analytics (ohne Cookies), Entscheidung „Kasselkenner Besucherzähler Cloudflare“.
# Aktiv nur, wenn vorlage/zaehler.txt den Schlüssel (oder den ganzen Schnipsel aus dem Cloudflare-Dashboard) enthält.
# Dann kommt das Skript auf jede Seite, und in inhalt/*.md gelten Zeilen mit „?zaehler:“; ohne Schlüssel die mit „?ohne-zaehler:“.
_z = re.search(r"[0-9a-f]{32}", (WURZEL / "vorlage" / "zaehler.txt").read_text()) if (WURZEL / "vorlage" / "zaehler.txt").exists() else None
ZAEHLER = _z.group(0) if _z else None
ZAEHLER_JS = (f"<script defer src=\"https://static.cloudflareinsights.com/beacon.min.js\" "
              f"data-cf-beacon='{{\"token\": \"{ZAEHLER}\"}}'></script>") if ZAEHLER else ""


def zaehler_zeilen(rumpf):
    """Zeilen mit ?zaehler: / ?ohne-zaehler: je nach Schalter behalten (ohne Kennung) oder streichen."""
    aus = []
    for z in rumpf.splitlines():
        for kenn, an in (("?zaehler:", True), ("?ohne-zaehler:", False)):
            if z.startswith(kenn):
                z = z[len(kenn):].lstrip() if bool(ZAEHLER) == an else None
                break
        if z is not None:
            aus.append(z)
    return "\n".join(aus) + ("\n" if rumpf.endswith("\n") else "")
# Orte für strukturierte Daten (Entität + Wikipedia), je Seite
ORTE = {
    "herkules-kassel": ("Herkules (Kassel)", "https://de.wikipedia.org/wiki/Herkules_(Kassel)"),
    "loewenburg-kassel": ("Löwenburg", "https://de.wikipedia.org/wiki/L%C3%B6wenburg_(Kassel)"),
    "schloss-wilhelmshoehe": ("Schloss Wilhelmshöhe", "https://de.wikipedia.org/wiki/Schloss_Wilhelmsh%C3%B6he"),
    "bergpark-wilhelmshoehe": ("Bergpark Wilhelmshöhe", "https://de.wikipedia.org/wiki/Bergpark_Wilhelmsh%C3%B6he"),
    "wasserspiele-kassel": ("Bergpark Wilhelmshöhe", "https://de.wikipedia.org/wiki/Bergpark_Wilhelmsh%C3%B6he"),
    "beleuchtete-wasserspiele": ("Bergpark Wilhelmshöhe", "https://de.wikipedia.org/wiki/Bergpark_Wilhelmsh%C3%B6he"),
    "parken-bergpark-wilhelmshoehe": ("Bergpark Wilhelmshöhe", "https://de.wikipedia.org/wiki/Bergpark_Wilhelmsh%C3%B6he"),
    "grimmwelt-kassel": ("Grimmwelt Kassel", "https://de.wikipedia.org/wiki/Grimmwelt_Kassel"),
    "orangerie-karlsaue": ("Orangerie (Kassel)", "https://de.wikipedia.org/wiki/Orangerie_(Kassel)"),
}
# Veranstaltungen: Seite -> (Name, Beginn, Ende, Ort, frei?, Wikipedia)
EVENTS = {
    "documenta-2027": ("documenta 16", "2027-06-12", "2027-09-19", "Kassel, Welcome Center Friedrichsplatz", False,
                       "https://de.wikipedia.org/wiki/Documenta_16"),
    "weihnachtsmarkt-kassel": ("Märchenweihnachtsmarkt Kassel 2026", "2026-11-23", "2026-12-30", "Königsplatz und Friedrichsplatz, Kassel", True, None),
    "zissel-kassel": ("Zissel 2027", "2027-07-30", "2027-08-02", "Auedamm und Karlswiese, Kassel", True, "https://de.wikipedia.org/wiki/Zissel"),
}
# Veranstalter aus dem Faktenspeicher (DO-083, KS-595, KS-229); Google meldete sie am 04.11.2026 als fehlend
VERANSTALTER = {"documenta-2027": ("documenta und Museum Fridericianum gGmbH", "https://www.documenta.de/"),
                "weihnachtsmarkt-kassel": ("Kassel Marketing GmbH", "https://www.weihnachtsmarkt-kassel.de/"),
                "zissel-kassel": ("Zissel in Kassel e.V.", "https://www.zissel.de/")}
BUCHEN = "https://wohnenambergpark.de/de/alle-ferienwohnungen"
NAV = [("wasserspiele-kassel", "Wasserspiele"), ("bergpark-wilhelmshoehe", "Bergpark"),
       ("documenta-2027", "documenta 2027"), ("parken-bergpark-wilhelmshoehe", "Parken & Anreise"),
       ("uebernachten-kassel", "Übernachten")]
THEMEN = ["herkules-kassel", "loewenburg-kassel", "schloss-wilhelmshoehe", "beleuchtete-wasserspiele",
          "kassel-sehenswuerdigkeiten", "kassel-mit-kindern", "kassel-bei-regen", "weihnachtsmarkt-kassel",
          "grimmwelt-kassel", "orangerie-karlsaue", "kassel-wochenende", "kassel-geheimtipps", "zissel-kassel", "documenta-uebernachten",
          "winterzauber-kassel", "kurhessen-therme", "habichtswald-wandern", "kliniken-angehoerige",
          "mit-bus-und-bahn-zum-bergpark", "parken-bahnhof-wilhelmshoehe", "steinhoefer-wasserfall", "kletterwald-kassel",
          "kassel-altstadt", "ahle-wurscht", "kassel-mit-hund"]
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
# Handy-Menü: eigene Gruppen, kleiner als „Weitere Themen“ (Aaron, 17.11.2026); Seiten, die noch nicht online sind, fallen weg
MENUE_GRUPPEN = [
    ("Bergpark & Wasserspiele", ["herkules-kassel", "loewenburg-kassel", "schloss-wilhelmshoehe", "beleuchtete-wasserspiele",
                                 "steinhoefer-wasserfall", "aussichtspunkte-kassel"]),
    ("Feste & Jahreszeiten", ["weihnachtsmarkt-kassel", "winterzauber-kassel", "kassel-im-winter", "kassel-im-fruehling",
                              "zissel-kassel", "termine-kassel-2027"]),
    ("Mit Kindern & bei Regen", ["kassel-mit-kindern", "kassel-bei-regen", "grimmwelt-kassel", "orangerie-karlsaue",
                                 "planetarium-kassel", "kletterwald-kassel"]),
    ("Stadt & Stadtteile", ["kassel-sehenswuerdigkeiten", "kassel-altstadt", "kassel-geheimtipps", "bad-wilhelmshoehe",
                            "kurhessen-therme"]),
    ("Wandern & Natur", ["habichtswald-wandern", "kassel-steig-bus-tram", "kassel-mit-hund"]),
    ("Anreise & Parken", ["mit-bus-und-bahn-zum-bergpark", "parken-bahnhof-wilhelmshoehe"]),
    ("Übernachten & Wochenende", ["documenta-uebernachten", "kassel-wochenende", "kliniken-angehoerige"]),
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
# Messen und Setzen je Durchgang gebündelt, nur einmal je Bild (requestAnimationFrame), 16.11.2026
FORTSCHRITT_JS = """<script>(function(){var b=document.querySelector('.lesefortschritt span');if(!b)return;var w=0,q=document.getElementById('haeufige-fragen')||document.querySelector('.quellen');function f(){w=0;var m=document.documentElement.scrollHeight-innerHeight,h=m;if(q){h=Math.min(m,q.getBoundingClientRect().top+scrollY-innerHeight*0.5)}b.style.transform='scaleX('+(h>0?Math.min(1,Math.max(0,scrollY/h)):0).toFixed(4)+')'}function g(){if(!w){w=1;requestAnimationFrame(f)}}addEventListener('scroll',g,{passive:true});addEventListener('resize',g);g()})();</script>"""
EIGEN_JS = """<script>(function(){var e=document.querySelector('.seite .eigen');if(!e)return;var k=document.querySelector('.kopf'),b=e.querySelector('.polaroid'),w=0;function u(){var r=e.getBoundingClientRect(),q=b?b.getBoundingClientRect():r;return (k?k.offsetHeight:68)+12+Math.max(0,r.top-q.top)}function p(){return innerHeight-e.offsetHeight-16}function f(){w=0;if(getComputedStyle(e).position!=='sticky'&&!e.style.position)return;e.classList.remove('knapp');e.style.position='';e.style.top='';var o=u(),t=p();if(t<o){e.classList.add('knapp');o=u();t=p()}if(t<o){e.style.position='static';return}e.style.top=Math.max(o,Math.min(140,t))+'px'}function g(){if(!w){w=1;requestAnimationFrame(f)}}addEventListener('resize',g);addEventListener('load',g);if(document.fonts)document.fonts.ready.then(g);g()})();</script>"""
# Handy-Menü (17.11.2026): öffnet mit Bewegung, Seite dahinter wird unbedienbar (inert), Escape, Linktipp,
# Zurück-Taste (bfcache) und Wechsel auf breite Fenster schließen. Ohne Skript bleibt details/summary bedienbar.
MENUE_JS = """<script>(function(){var d=document.querySelector('.menue');if(!d)return;var s=d.querySelector('summary'),t=d.querySelector('.menue-tafel'),k=document.querySelector('.kopf'),r=matchMedia('(prefers-reduced-motion:reduce)'),z=0;d.classList.add('lebt');function sperren(an){[].forEach.call(document.body.children,function(e){if(e!==k&&e.tagName!=='SCRIPT')e.inert=an})}function auf(){clearTimeout(z);d.style.setProperty('--menue-oben',Math.max(0,Math.round(k.getBoundingClientRect().bottom))+'px');d.open=true;sperren(true);void t.offsetWidth;d.classList.add('auf')}function zu(sofort){if(!d.open)return;clearTimeout(z);d.classList.remove('auf');sperren(false);if(sofort||r.matches){d.open=false;return}z=setTimeout(function(){d.open=false},180)}s.addEventListener('click',function(e){e.preventDefault();if(d.open&&d.classList.contains('auf'))zu();else auf()});d.addEventListener('toggle',function(){if(d.open&&!d.classList.contains('auf')&&!z){sperren(true);d.classList.add('auf')}if(!d.open){z=0;d.classList.remove('auf');sperren(false)}});document.addEventListener('keydown',function(e){if(e.key==='Escape'&&d.open){zu();s.focus()}});t.addEventListener('click',function(e){if(e.target.closest('a'))zu(true)});addEventListener('pageshow',function(e){if(e.persisted)zu(true)});var b=matchMedia('(max-width:760px)');if(b.addEventListener)b.addEventListener('change',function(e){if(!e.matches)zu(true)})})();</script>"""
# Linienplan: Wasser „fließt“ beim Scrollen die Strecke hinab, erreichte Stationen leuchten orange.
# Erst alle Maße lesen, dann alle Klassen und Werte schreiben (kein Wechsel von Lesen und Schreiben)
STRECKE_JS = """<script>(function(){var s=[].slice.call(document.querySelectorAll('.strecke'));if(!s.length)return;s.forEach(function(o){o.classList.add('lebt')});var w=0;function f(){w=0;var m=innerHeight*0.6,a=s.map(function(o){var r=o.getBoundingClientRect();return [o,Math.max(0,Math.min(1,(m-r.top)/r.height)),[].map.call(o.children,function(l){var q=l.getBoundingClientRect();return q.top+q.height/2<m})]});a.forEach(function(x){x[0].style.setProperty('--f',x[1].toFixed(3));[].forEach.call(x[0].children,function(l,i){l.classList.toggle('an',x[2][i])})})}function g(){if(!w){w=1;requestAnimationFrame(f)}}addEventListener('scroll',g,{passive:true});addEventListener('resize',g);g()})();</script>"""
# Google „bevorzugte Quelle“ (Aaron, 16.11.2026): im Fuß jeder Seite und auf Über uns
BEVORZUGT = ('<a href="https://www.google.com/preferences/source?q=kasselkenner.de" rel="noopener">'
             'Kasselkenner bei Google als bevorzugte Quelle wählen</a>')
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
    # Ziel darf eine Klammerebene enthalten (Wikipedia „Herkules_(Kassel)“), sonst endet der Link zu früh (04.11.2026)
    return re.sub(r"\[([^\]]+)\]\(((?:[^()\s]|\([^()\s]*\))+)\)", link, t)


def anker(t):
    t = t.lower().translate(str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}))
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def markdown(rumpf):
    """Gibt (html, faq-liste, inhaltsverzeichnis) zurück."""
    aus, faq, toc = [], [], []
    zeilen = rumpf.splitlines()
    i, in_faq, bilder_im_text = 0, False, 0
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
            namen = [html.escape(re.sub(r"[*_`]", "", c).strip()) for c in reihen[0]]
            koerper = "".join("<tr>" + "".join(f'<td data-k="{namen[i] if i < len(namen) else ""}">{inline(c)}</td>' for i, c in enumerate(r)) + "</tr>" for r in reihen[1:])
            aus.append(f'<div class="tabelle{" breit" if len(reihen[0]) >= 3 else ""}"><table><thead><tr>{kopf}</tr></thead><tbody>{koerper}</tbody></table></div>')
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
        m = re.match(r"!\[([^\]]*)\]\(([^)\s]+)\)\s*$", z)
        if m:  # Polaroid im Text, abwechselnd rechts und links (Aaron, 15.10.2026)
            unterschrift, datei = m.group(1), m.group(2)
            stem, alt = Path(datei).stem, BILDNACHWEIS.get(datei, {}).get("alt", "")
            # Wie viel Text folgt bis zur nächsten Sperre (## , Tabelle, Hinweis)? Danach richtet sich die Größe,
            # damit neben dem Bild kein leerer Platz bleibt (Aaron, 15.10.2026)
            folgt, j = 0, i + 1
            while j < len(zeilen) and not re.match(r"(## |\||> |!\[)", zeilen[j]):
                folgt += len(re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", zeilen[j])); j += 1
            if folgt < 260:
                seite_ = "mitte"
            else:
                seite_ = ("rechts" if bilder_im_text % 2 == 0 else "links") + (" klein" if folgt < 480 else "")
                bilder_im_text += 1
            aus.append(f'<figure class="polaroid im-text {seite_}"><img src="../bilder/{stem}-600.webp" '
                       f'srcset="../bilder/{stem}-600.webp 600w, ../bilder/{stem}.webp 1200w" sizes="(max-width:760px) 80vw, 420px" '
                       f'alt="{html.escape(alt)}" width="1200" height="900" loading="lazy"><figcaption>{html.escape(unterschrift)}</figcaption></figure>')
            i += 1
            continue
        if z.startswith("> "):
            teile = []
            while i < len(zeilen) and zeilen[i].startswith(">"):
                teile.append(zeilen[i][1:].strip())
                i += 1
            aus.append(f'<aside class="hinweis zettel blau"><b class="marke">Gut zu wissen</b><p>{inline(" ".join(teile))}</p></aside>')
            continue
        absatz = []
        while i < len(zeilen) and zeilen[i].strip() and not re.match(r"(#|\||- |\d+\. |> |!\[)", zeilen[i]):
            absatz.append(zeilen[i].strip())
            i += 1
        aus.append(f"<p>{inline(' '.join(absatz))}</p>")
    return "\n".join(aus), faq, toc


# Empfehlung in eigener Sache, je Thema passend (Fakten: Wissensspeicher Wohnen am Bergpark; Wortlaut Aaron, 16.11.2026)
WOHNUNG = {  # Kurzname (für /zu/-Zählseiten) -> (Wohnungsseite oder "" = Übersicht, Foto, Bildunterschrift)
    "loewenburg": ("lowenburg-2-schlafzimmer-fur-zwei-paare", "wohnung-loewenburg.jpg", "Wohnung Löwenburg"),
    "herkules": ("herkules-whirlpool-im-garten-100-m2-6-gaste", "wohnung-herkules.jpg", "Wohnung Herkules"),
    "romantisch": ("romantische-wohnung-dachbalkon-mit-herkulesblick", "wohnung-romantisch.jpg", "Romantische Wohnung"),
}
EMPFEHLUNG = {  # Titel, Satz, Tipp, Wohnung (Kurzname oder "" = Übersicht), Zeile (Einzeiler im Text)
    "wasser": ("Nach dem Finale zu Fuß nach Hause",
               "Von unserer Wohnung Löwenburg in der Lindenstraße gehst du 14 Minuten flach zum Schloss Wilhelmshöhe. Kein Parkplatzsuchen, kein Stau nach den Wasserspielen.",
               "Zwei Schlafzimmer, eigene Küche, für bis zu 4 Personen.", "loewenburg",
               "Unsere Wohnung Löwenburg liegt 14 Minuten zu Fuß vom Schloss Wilhelmshöhe."),
    "berg": ("Der Bergpark als Vorgarten",
             "Von unserer Wohnung Löwenburg sind es 14 Minuten zu Fuß zum Schloss und 18 Minuten zur Löwenburg. Morgens bist du im Park, bevor die Busse kommen.",
             "Zwei Schlafzimmer, eigene Küche, für bis zu 4 Personen.", "loewenburg",
             "Wir vermieten Ferienwohnungen in Bad Wilhelmshöhe, 14 Minuten zu Fuß vom Schloss."),
    "parken": ("Auto abstellen, Park zu Fuß",
               "An unseren Häusern in Bad Wilhelmshöhe parkst du kostenlos an der Straße. Zum Bergpark gehst du zu Fuß oder fährst mit der Linie 4, Parkgebühren am Park fallen weg.",
               "Unser Tipp: die Wohnung „Herkules“ mit Garten und Whirlpool für bis zu 6 Personen.", "herkules",
               "Bei uns parkst du kostenlos an der Straße und gehst zu Fuß in den Bergpark."),
    "bahn": ("Vom ICE direkt in die Wohnung",
             "Die Linie 4 fährt vom Bahnhof Wilhelmshöhe zur Haltestelle Brabanter Straße, direkt an unserem Haus. Der Check-in ist kontaktlos, auch wenn dein Zug spät ankommt.",
             "Unser Tipp: die Wohnung „Herkules“ mit Garten und Whirlpool für bis zu 6 Personen.", "herkules",
             "Mit der Linie 4 vom ICE-Bahnhof bis vor unsere Ferienwohnungen."),
    "kunst": ("Kunst am Tag, Ruhe am Abend",
              "Mit der Linie 4 bist du schnell in der Innenstadt und abends zurück im Grünen am Bergpark.",
              "Unser Tipp: die Romantische Wohnung mit Balkon und Blick auf den Herkules, für bis zu 4 Personen.", "romantisch",
              "Für die documenta: Ferienwohnungen am Bergpark, mit der Linie 4 in die Innenstadt."),
    "familie": ("Platz für die ganze Familie",
                "Mehr Raum als im Hotelzimmer, eine eigene Küche und der Bergpark gleich um die Ecke.",
                "Unser Tipp: die „Löwenburg“ mit zwei Schlafzimmern für bis zu 4 Personen.", "loewenburg",
                "Für Familien: Ferienwohnungen mit eigener Küche am Bergpark."),
    "winter": ("Nach dem Markt ins Warme",
               "Mit der Linie 4 bist du aus der Innenstadt schnell zurück in Bad Wilhelmshöhe. Die Wohnung „Herkules“ hat einen beheizten Whirlpool im Garten, das ganze Jahr.",
               "Für bis zu 6 Personen, mit eigener Küche.", "herkules",
               "Nach dem Weihnachtsmarkt zurück in die eigene Ferienwohnung am Bergpark."),
    "hund": ("Mit Hund am Bergpark wohnen",
             "Morgens die erste Runde im Park, abends zurück in die eigene Wohnung: Haustiere sind bei uns auf Anfrage möglich, gegen Aufpreis.",
             "Unser Tipp: vor der Buchung kurz nachfragen, dann klären wir die passende Wohnung.", "",
             "Mit Hund? Unsere Ferienwohnungen am Bergpark gibt es auf Anfrage auch für Vierbeiner."),
    "klinik": ("Nah bei den Kliniken",
               "Unsere Wohnungen liegen in Bad Wilhelmshöhe, im selben Stadtteil wie die Kliniken am Bergpark. Eigene Küche, kostenlos parken an der Straße, Check-in kontaktlos.",
               "Auch für längere Aufenthalte.", "",
               "Für Angehörige: Ferienwohnungen mit Küche in Bad Wilhelmshöhe."),
    "start": ("Dein Zuhause am Bergpark",
              "Zehn Ferienwohnungen in Bad Wilhelmshöhe, vom Apartment für zwei bis zur Wohnung mit Garten für sechs.",
              "Kostenlos parken an der Straße, die Linie 4 ganz in der Nähe.", "",
              "Wir vermieten zehn Ferienwohnungen in Bad Wilhelmshöhe, nah am Bergpark."),
}
# Foto und Unterschrift, wenn die Empfehlung auf die Übersicht zeigt (wie bisher)
UEBERSICHT_FOTO = {"hund": ("wohnung-herkules.jpg", "Wohnung Herkules"), "klinik": ("wohnung-schlossteich.jpg", "Wohnung Schlossteich"),
                   "start": ("wohnung-schlossteich.jpg", "Wohnung Schlossteich")}
EMPFEHLUNG_THEMA = {}
for _thema, _seiten in {
        "wasser": ["wasserspiele-kassel", "beleuchtete-wasserspiele", "steinhoefer-wasserfall"],
        "berg": ["herkules-kassel", "bergpark-wilhelmshoehe", "loewenburg-kassel", "schloss-wilhelmshoehe", "habichtswald-wandern",
                 "kurhessen-therme", "bad-wilhelmshoehe", "kassel-im-fruehling", "aussichtspunkte-kassel"],
        "parken": ["parken-bergpark-wilhelmshoehe", "parken-bahnhof-wilhelmshoehe"],
        "bahn": ["mit-bus-und-bahn-zum-bergpark"],
        "kunst": ["documenta-2027", "documenta-uebernachten"],
        "familie": ["kassel-mit-kindern", "kassel-bei-regen", "grimmwelt-kassel", "orangerie-karlsaue", "kletterwald-kassel",
                    "planetarium-kassel"],
        "winter": ["weihnachtsmarkt-kassel", "winterzauber-kassel", "kassel-im-winter"],
        "hund": ["kassel-mit-hund"],
        "klinik": ["kliniken-angehoerige"],
        "start": ["fruehlingsfest-kassel"]}.items():
    EMPFEHLUNG_THEMA.update({s: _thema for s in _seiten})
# Einzeiler je Seite, mit Bezug zum Artikel (Aaron, 17.11.2026); sonst gilt die Zeile des Themas
ZEILE_SEITE = {
    "wasserspiele-kassel": "Nach dem Finale gehst du vom Schloss in 14 Minuten zu Fuß in unsere Wohnung Löwenburg.",
    "beleuchtete-wasserspiele": "Nach den beleuchteten Wasserspielen spazierst du vom Schloss in 14 Minuten in unsere Wohnung Löwenburg.",
    "steinhoefer-wasserfall": "Schöne Ferienwohnungen am Bergpark, von unserer Wohnung Löwenburg sind es 14 Minuten zu Fuß zum Schloss.",
    "herkules-kassel": "Abends vom Herkules zurück in die eigene Ferienwohnung, 14 Minuten zu Fuß vom Schloss.",
    "bergpark-wilhelmshoehe": "Schöne Ferienwohnungen direkt um die Ecke. Von unserer Wohnung Löwenburg gehst du 14 Minuten zum Schloss.",
    "loewenburg-kassel": "Von unserer Wohnung Löwenburg sind es 18 Minuten zu Fuß bis zur echten Löwenburg.",
    "schloss-wilhelmshoehe": "Schöne Ferienwohnungen gleich um die Ecke, von unserer Wohnung Löwenburg sind es 14 Minuten zum Schloss.",
    "habichtswald-wandern": "Nach der Tour die Füße hochlegen, in unserer Ferienwohnung 14 Minuten zu Fuß vom Schloss.",
    "kurhessen-therme": "Nach der Therme ist es nicht weit, unsere Ferienwohnungen liegen im selben Stadtteil.",
    "bad-wilhelmshoehe": "Mittendrin wohnen, unsere Ferienwohnungen liegen hier in Bad Wilhelmshöhe.",
    "kassel-im-fruehling": "Für ein paar Frühlingstage am Bergpark, schöne Ferienwohnungen gleich um die Ecke vom Schloss.",
    "parken-bahnhof-wilhelmshoehe": "An unseren Ferienwohnungen parkst du kostenlos an der Straße, ganz ohne Parkhaus.",
    "documenta-2027": "Nach einem langen Tag auf der documenta zurück ins Grüne, in eine unserer Ferienwohnungen.",
    "documenta-uebernachten": "Ferienwohnungen für die documenta 2027, mit der Tram schnell in der Innenstadt.",
    "kassel-mit-kindern": "Mehr Platz als im Hotelzimmer, unsere Wohnung Löwenburg hat zwei Schlafzimmer und eine eigene Küche.",
    "kassel-bei-regen": "Regentag? Zurück in die eigene Ferienwohnung mit Küche am Bergpark.",
    "grimmwelt-kassel": "Nach der Grimmwelt zurück ins Grüne, in eine Ferienwohnung mit eigener Küche am Bergpark.",
    "orangerie-karlsaue": "Nach der Karlsaue zurück an den Bergpark, in eine Ferienwohnung mit eigener Küche.",
    "kletterwald-kassel": "Nach dem Klettern ausruhen, in unserer Wohnung Löwenburg mit zwei Schlafzimmern am Bergpark.",
    "planetarium-kassel": "Nach dem Sternenhimmel im Planetarium zurück in die eigene Ferienwohnung am Bergpark.",
    "weihnachtsmarkt-kassel": "Nach dem Glühwein in den warmen Whirlpool, im Garten unserer Wohnung Herkules.",
    "winterzauber-kassel": "Nach dem Winterzauber in den beheizten Whirlpool unserer Wohnung Herkules.",
    "kliniken-angehoerige": "Ferienwohnungen mit eigener Küche im selben Stadtteil wie die Kliniken, auch für längere Aufenthalte.",
    "kassel-altstadt": "Nach dem Stadtbummel zurück ins Grüne, unsere Ferienwohnungen liegen am Bergpark.",
    "kassel-geheimtipps": "Ruhig wohnen am Bergpark, in einer unserer Ferienwohnungen in Bad Wilhelmshöhe.",
    "kassel-sehenswuerdigkeiten": "Schöne Ferienwohnungen am Bergpark, mit der Linie 4 schnell in der Innenstadt.",
    "kassel-steig-bus-tram": "Mit der Linie 4 bis vor unsere Ferienwohnungen in Bad Wilhelmshöhe.",
    "kassel-wochenende": "Fürs Wochenende eine eigene Ferienwohnung am Bergpark, mit Küche und kostenlosem Parken an der Straße.",
    "termine-kassel-2027": "Für die großen Termine 2027 eine eigene Ferienwohnung am Bergpark, mit Küche und kostenlosem Parken.",
    "uebernachten-kassel": "Schöne Ferienwohnungen direkt am Bergpark, vom Apartment für zwei bis zur Wohnung mit Garten für sechs.",
    "zissel-kassel": "Nach dem Zissel an der Fulda mit der Tram zurück in die Ferienwohnung am Bergpark.",
    "aussichtspunkte-kassel": "Den Herkules jeden Tag im Blick, in unseren Ferienwohnungen am Bergpark.",
    "kassel-im-winter": "Nach dem Winterspaziergang in den beheizten Whirlpool im Garten unserer Wohnung Herkules.",
}
# Kein Einzeiler auf diesen Seiten
OHNE_ZEILE = {"impressum", "datenschutz", "bildnachweise", "ueber-uns", "404", "index"}


def empfehlung(slug):
    """(thema, titel, satz, tipp, zeile, kurzname, wohnungsseite, foto, unterschrift) zur Seite."""
    thema = EMPFEHLUNG_THEMA.get(slug, "start")
    titel, satz, tipp, kurz, zeile = EMPFEHLUNG[thema]
    if kurz:
        seite_, bild, unterschrift = WOHNUNG[kurz]
    else:
        seite_, (bild, unterschrift) = "", UEBERSICHT_FOTO.get(thema, UEBERSICHT_FOTO["start"])
    return thema, titel, satz, tipp, zeile, (kurz or "uebersicht"), seite_, bild, unterschrift


def wohnung_url(seite_, slug, ort):
    return (f"https://wohnenambergpark.de/de/{seite_}" if seite_ else BUCHEN) + \
        f"?utm_source=kasselkenner&utm_medium=referral&utm_campaign={slug}&utm_content={ort}"


# Zählseiten /zu/<wohnung>/<ort>/<seite>/: Cloudflare Web Analytics zählt nur Seitenaufrufe und schneidet die
# Abfrage (?…) ab, daher steckt alles im Pfad. Gesammelt beim Bauen, geschrieben in main().
ZAEHLSEITEN = {}


def eigen_link(slug, tiefe, ort):
    """Link für Kasten (ort=kasten) oder Einzeiler (ort=zeile): mit Zähler über /zu/…, sonst direkt."""
    _, _, _, _, _, kurz, seite_, _, _ = empfehlung(slug)
    ziel = wohnung_url(seite_, slug, ort)
    if not ZAEHLER:
        return ziel, ' rel="noopener"'
    von = "startseite" if slug == "index" else slug
    pfad = f"zu/{kurz}/{ort}/{von}/"
    ZAEHLSEITEN[pfad] = ziel
    return f"{tiefe}{pfad}", ' rel="nofollow"'


def zaehlseite(pfad, ziel):
    z = html.escape(ziel)
    return f"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<meta name="referrer" content="strict-origin-when-cross-origin">
<title>Weiter zu Wohnen am Bergpark</title>
<noscript><meta http-equiv="refresh" content="0;url={z}"></noscript>
<style>body{{font:18px/1.6 system-ui,sans-serif;margin:0;display:grid;place-items:center;min-height:100vh;color:#1D1A18}}a{{color:#5B1E2D;font-weight:700}}</style>
</head>
<body>
<p><a href="{z}" rel="noopener">Weiter zu Wohnen am Bergpark</a></p>
<script>(function(){{var z={json.dumps(ziel)},g=0;function w(){{if(g)return;g=1;location.replace(z)}}
/* Der Zähler sendet seinen Seitenaufruf kurz nach dem load-Ereignis (per sendBeacon); danach weiter, spätestens nach 600 ms */
addEventListener('load',function(){{setTimeout(w,120)}});setTimeout(w,600)}})();</script>
{ZAEHLER_JS}
</body>
</html>
"""


def eigen_zeile(slug, tiefe):
    """Schmaler Streifen „In eigener Sache“ früh im Text (Aaron, 16.11.2026)."""
    _, _, _, _, zeile, kurz, seite_, _, _ = empfehlung(slug)
    zeile = ZEILE_SEITE.get(slug, zeile)
    href, rel = eigen_link(slug, tiefe, "zeile")
    knopf = "Wohnung ansehen" if seite_ else "Wohnungen ansehen"
    return (f'<aside class="eigen-zeile" aria-label="In eigener Sache"><span class="etikett">In eigener Sache</span>'
            f'<p>{html.escape(zeile)}</p><a class="pille" href="{href}"{rel}>{knopf}</a></aside>')


def zeile_einfuegen(rest, slug, tiefe):
    """Einzeiler nach dem ersten Absatz hinter der zweiten Zwischenüberschrift; sonst nach etwa einem Drittel.
    Nur zwischen Blöcken der obersten Ebene, nie in Tabellen, FAQ oder Quellen."""
    bloecke = rest.split("\n")
    def ok(i):  # Einfügen hinter Block i?
        return bloecke[i].startswith(("<p>", "<ul>", "<ol>"))
    h2 = [i for i, b in enumerate(bloecke) if b.startswith("<h2 ")]
    stelle = None
    if len(h2) >= 2 and 'id="haeufige-fragen"' not in bloecke[h2[1]]:
        ende = h2[2] if len(h2) > 2 else len(bloecke)
        stelle = next((i for i in range(h2[1] + 1, ende) if ok(i)), None)
    if stelle is None:
        grenze = next((i for i, b in enumerate(bloecke) if 'id="haeufige-fragen"' in b or 'class="quellen"' in b), len(bloecke))
        kandidaten = [i for i in range(grenze) if ok(i)]
        if not kandidaten:
            return rest
        drittel = grenze // 3
        stelle = min(kandidaten, key=lambda i: (i < drittel, abs(i - drittel)))
    bloecke.insert(stelle + 1, eigen_zeile(slug, tiefe))
    return "\n".join(bloecke)


def eigenwerbung(slug, tiefe, quer=False):
    _, titel, satz, tipp, _, _, seite_, bild, unterschrift = empfehlung(slug)
    href, rel = eigen_link(slug, tiefe, "kasten")
    knopf = "Wohnung ansehen" if seite_ else "Wohnungen ansehen"
    return f"""<aside class="eigen{' quer' if quer else ''}" aria-label="In eigener Sache">
<figure class="polaroid"><img src="{tiefe}bilder/{Path(bild).stem}-600.webp" alt="{html.escape(BILDNACHWEIS.get(bild, {}).get("alt", ""))}" width="1000" height="667" decoding="async"><figcaption>{unterschrift}</figcaption></figure>
<div class="k"><p class="dach">In eigener Sache</p>
<h3>{titel}</h3>
<p>{satz}</p>
<p class="tipp">{tipp}</p>
<a class="knopf" href="{href}"{rel}>{knopf}</a></div>
</aside>"""


def karten(slugs, alle, tiefe):
    aus = []
    for s in slugs:
        m = alle.get(s)
        if not m or not m.get("bild"):
            continue
        n = BILDNACHWEIS.get(m["bild"], {})
        aus.append(f'<a class="karte" href="{tiefe}{s}/"><figure class="polaroid"><img src="{tiefe}bilder/{Path(m["bild"]).stem}-600.webp" '
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


def menue_tafel(slug, tiefe, alle):
    """Handy-Menü: „Planen“ oben, darunter die Themen nach den Vorhaben-Gruppen der Startseite, Rest unter „Weitere Themen“.
    Jede Seite steht genau einmal im Menü (17.11.2026)."""
    def zeile(s, text):
        aktuell = ' aria-current="page"' if s == slug else ""
        return f'<li><a href="{tiefe}{s}/"{aktuell}>{text}</a></li>'

    def gruppe(nr, titel, liste, eintraege):
        return (f'<div class="menue-gruppe"><p class="menue-titel" id="menue-g{nr}">{html.escape(titel)}</p>'
                f'<ul class="{liste}" aria-labelledby="menue-g{nr}">{"".join(eintraege)}</ul></div>')

    teile = [gruppe(0, "Planen", "menue-haupt", [zeile(s, t) for s, t in NAV if s in alle])]
    gesehen = {s for s, _ in NAV}
    for nr, (titel, liste) in enumerate(MENUE_GRUPPEN, 1):
        seiten = [s for s in liste if s in alle and s not in gesehen]
        gesehen.update(seiten)
        if seiten:
            teile.append(gruppe(nr, titel, "menue-liste", [zeile(s, html.escape(alle[s].get("kurz", s))) for s in seiten]))
    rest = [s for s in THEMEN if s in alle and s not in gesehen]
    if rest:
        teile.append(gruppe(len(MENUE_GRUPPEN) + 1, "Weitere Themen", "menue-liste", [zeile(s, html.escape(alle[s].get("kurz", s))) for s in rest]))
    return "".join(teile)


def kopf_und_fuss(slug, tiefe, alle):
    nav ="".join(f'<a href="{tiefe}{s}/"{" aria-current=\"page\"" if s == slug else ""}>{t}</a>' for s, t in NAV if s in alle)
    themen = "".join(f'<a href="{tiefe}{s}/"{" aria-current=\"page\"" if s == slug else ""}>{html.escape(alle[s].get("kurz", s))}</a>'
                     for s in THEMEN if s in alle)
    kopf = f"""<a class="sprung" href="#inhalt">Zum Inhalt</a>
<header class="kopf"><div class="breite">
<a class="wortmarke" href="{tiefe or './'}" aria-label="{NAME} – Startseite"><b>KASSEL</b><i>kenner.</i></a>
<nav class="haupt" aria-label="Hauptnavigation">{nav}</nav>
<details class="menue"><summary><span class="striche" aria-hidden="true"><i></i><i></i><i></i></span><span class="zu">Menü</span><span class="auf">Schließen</span></summary>
<nav class="menue-tafel" aria-label="Menü">{menue_tafel(slug, tiefe, alle)}</nav></details>
</div><div class="lesefortschritt" aria-hidden="true"><span></span></div></header>
<nav class="themen" aria-label="Themen"><div class="breite">{themen}</div></nav>"""
    fuss_links = " · ".join(f'<a href="{tiefe}{s}/">{t}</a>' for s, t in FUSS)
    fuss = f"""<footer class="fuss"><div class="breite">
<div class="wortmarke"><b>KASSEL</b><i>kenner.</i></div>
<p>Bergpark, Wasserspiele und documenta: Tipps für deinen Besuch in Kassel. Angaben ohne Gewähr; Termine und Preise ändern sich, im Zweifel gilt die Seite des Veranstalters.</p>
<p class="fuss-links">{fuss_links}</p>
<p class="bevorzugt">{BEVORZUGT}</p>
</div></footer>"""
    return kopf, fuss


def titelbild_tag(bild, tiefe, attr=""):
    n = BILDNACHWEIS.get(bild, {})
    s = Path(bild).stem
    return (f'<img src="{tiefe}bilder/{s}.webp" srcset="{tiefe}bilder/{s}-600.webp 600w, {tiefe}bilder/{s}.webp 1200w" sizes="100vw" '
            f'alt="{html.escape(n.get("alt", ""))}" width="1200" height="675"{attr}>')


def bild_objekt(bild):
    n = BILDNACHWEIS.get(bild, {})
    b, h = BILDMASSE.get(bild, (1200, 675))
    o = {"@type": "ImageObject", "url": f"{DOMAIN}/bilder/{bild}", "width": b, "height": h}
    if n.get("lizenz", "").startswith("eigen"):
        o.update({"creator": {"@type": "Organization", "name": "Wohnen am Bergpark"}, "creditText": "Wohnen am Bergpark, eigenes Foto",
                  "copyrightNotice": "Wohnen am Bergpark"})
    elif n.get("urheber"):
        o.update({"creator": {"@type": "Person", "name": n["urheber"]}, "creditText": f'{n["urheber"]}, {n.get("lizenz", "")}'.strip(", "),
                  "copyrightNotice": f'{n["urheber"]} / Wikimedia Commons', "acquireLicensePage": DOMAIN + "/bildnachweise/"})
        if n.get("lizenz_url", "").startswith("http"):
            o["license"] = n["lizenz_url"]
    return o



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
    tiefe = "" if slug == "index" else ("/" if slug == "404" else "../")
    stand = meta.get("stand", date.today().isoformat())
    bild = meta.get("bild")
    art_seite = meta.get("art", "artikel")
    schema = [{"@context": "https://schema.org", "@type": "Organization", "@id": DOMAIN + "/#org",
               "name": NAME, "url": DOMAIN + "/", "logo": DOMAIN + "/icon-512.png", "email": "kontakt@kasselkenner.de",
               "description": "Ratgeber für Besucher in Kassel: Bergpark, Wasserspiele, documenta und Ausflüge, mit Quellen und Prüfdatum.",
               "areaServed": {"@type": "City", "name": "Kassel"}, "founder": {"@id": AUTOR_ID},
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
            art["image"] = bild_objekt(bild)
        if slug in ORTE:
            name, wiki = ORTE[slug]
            art["about"] = {"@type": "TouristAttraction", "name": name, "sameAs": wiki,
                            "address": {"@type": "PostalAddress", "addressLocality": "Kassel", "addressRegion": "Hessen", "addressCountry": "DE"}}
        schema.append(art)
        if slug in EVENTS:
            name, von, bis, ort, frei, wiki = EVENTS[slug]
            ev = {"@context": "https://schema.org", "@type": "Event", "name": name, "startDate": von, "endDate": bis,
                  "eventStatus": "https://schema.org/EventScheduled", "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
                  "location": {"@type": "Place", "name": ort, "address": {"@type": "PostalAddress", "addressLocality": "Kassel", "addressCountry": "DE"}},
                  "isAccessibleForFree": frei, "url": url, "description": meta.get("beschreibung", "")}
            if wiki:
                ev["sameAs"] = wiki
            if slug in VERANSTALTER:
                ev["organizer"] = {"@type": "Organization", "name": VERANSTALTER[slug][0], "url": VERANSTALTER[slug][1]}
            if bild:
                ev["image"] = f"{DOMAIN}/bilder/{bild}"
            schema.append(ev)
        schema.append({"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": NAME, "item": DOMAIN + "/"},
            {"@type": "ListItem", "position": 2, "name": meta.get("kurz", meta["titel"]), "item": url}]})
    if slug == "ueber-uns":
        person = dict(AUTOR, **{"@context": "https://schema.org"})
        schema.append({"@context": "https://schema.org", "@type": "AboutPage", "url": url, "name": meta["titel"],
                       "mainEntity": {"@id": DOMAIN + "/#org"}, "author": {"@id": AUTOR_ID}})
        schema.append(person)
    if art_seite != "artikel" and slug not in ("index", "404"):
        schema.append({"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": NAME, "item": DOMAIN + "/"},
            {"@type": "ListItem", "position": 2, "name": meta.get("kurz", meta["titel"].split(" | ")[0]), "item": url}]})
    if faq:
        schema.append({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": f, "acceptedAnswer": {"@type": "Answer", "text": a}} for f, a in faq]})
    kopf, fuss = kopf_und_fuss(slug, tiefe, alle)

    # H1 und ersten Absatz herauslösen
    h1 = re.search(r"<h1>(.*?)</h1>", inhalt_html, re.S)
    h1_text = h1.group(1) if h1 else html.escape(meta["titel"])
    rest = inhalt_html[h1.end():] if h1 else inhalt_html
    if slug == "ueber-uns":
        rest = rest.replace('<h2 id="wer-hier-schreibt">Wer hier schreibt</h2>',
                            '<h2 id="wer-hier-schreibt">Wer hier schreibt</h2><figure class="polaroid portraet"><img src="../aaron-400.webp" '
                            'alt="Aaron Schiele, Gastgeber von Wohnen am Bergpark" width="480" height="360" loading="lazy"><figcaption>Aaron</figcaption></figure>', 1)
    erster = re.match(r"\s*<p>(.*?)</p>", rest, re.S)
    lede = erster.group(1) if erster else ""
    if erster:
        rest = rest[erster.end():]

    if slug == "ueber-uns":
        rest += f'\n<p class="bevorzugt-text">Dir helfen unsere Seiten? Dann kannst du {BEVORZUGT}.</p>'
    if slug == "index":
        koerper = startseite(meta, h1_text, lede, rest, alle)
    elif art_seite != "artikel":
        koerper = f"""<section class="held ohne-bild schlicht"><div class="text"><div class="breite"><h1 class="gross" style="font-size:clamp(38px,6vw,64px)">{h1_text}</h1></div></div></section>
<main id="inhalt" class="breite" style="max-width:820px;padding-top:36px">{'<p>' + lede + '</p>' if lede else ''}{rest}</main>"""
    else:
        lang = " lang" if len(re.sub("<.*?>", "", h1_text)) > 34 else ""
        groesse = ' style="font-size:clamp(36px,5.4vw,68px)"' if lang else ""
        if bild:
            held = f"""<section class="held">{titelbild_tag(bild, tiefe, ' fetchpriority="high"')}
<div class="text"><div class="breite"><div class="krumen"><a href="{tiefe or './'}">Start</a> / {html.escape(meta.get("kurz", ""))}</div><h1 class="gross"{groesse}>{h1_text}</h1></div></div>
</section>"""
        else:
            held = f'<section class="held ohne-bild"><div class="text"><div class="breite"><h1 class="gross"{groesse}>{h1_text}</h1></div></div></section>'
        blick = blick_lesen(meta.get("blick"))
        blick_html = ('<div class="blick"><b class="marke">Auf einen Blick</b><dl>' +
                      "".join(f"<dt>{html.escape(k)}</dt><dd>{inline(v)}</dd>" for k, v in blick) + "</dl></div>") if blick else ""
        # Gelber Zettel = Zusammenfassung ohne Zahlen, weiße Karte = harte Fakten (Aaron, 09.10.2026)
        # Im Quelltext stehen die harten Fakten vor dem Zettel (KIs und Suchmaschinen lesen sie zuerst),
        # angezeigt wird per CSS-Reihenfolge weiter der Zettel links bzw. oben (Aaron, 09.10.2026)
        anpinnen = f"""<section class="anpinnen"><div class="breite">
{blick_html}<div class="zettel"><b class="marke">Kurz gesagt</b><p>{lede}</p></div>
</div></section>""" if lede else ""
        autor = f"""<div class="autor"><img class="kreis" src="{tiefe}aaron-160.webp" alt="Aaron Schiele" width="42" height="42"><div><a href="{tiefe}ueber-uns/"><strong>Aaron Schiele</strong></a><br>geprüft am <time datetime="{stand}">{date.fromisoformat(stand).strftime("%d.%m.%Y")}</time></div></div>"""
        werbung_an = meta.get("eigenwerbung", "ja") == "ja"
        if werbung_an and slug not in OHNE_ZEILE:
            rest = zeile_einfuegen(rest, slug, tiefe)
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
    teil_bild = bild or EIGEN_BILD
    b, h_ = BILDMASSE.get(teil_bild, (1200, 675))
    og_bild = (f'<meta property="og:image" content="{DOMAIN}/bilder/{teil_bild}">\n<meta property="og:image:width" content="{b}">\n'
               f'<meta property="og:image:height" content="{h_}">\n<meta property="og:image:alt" content="{html.escape(BILDNACHWEIS.get(teil_bild, {}).get("alt", ""))}">\n'
               f'<meta name="twitter:card" content="summary_large_image">')
    return f"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(meta["titel"])}</title>
<meta name="description" content="{html.escape(meta.get("beschreibung", ""))}">
{'' if slug == "404" else f'<link rel="canonical" href="{url}">'}
{'<meta name="robots" content="noindex">' if meta.get("robots") == "noindex" or slug == "404" else ""}
<meta property="og:type" content="{'article' if art_seite == 'artikel' else 'website'}">
<meta property="og:title" content="{html.escape(meta["titel"])}">
<meta property="og:description" content="{html.escape(meta.get("beschreibung", ""))}">
<meta property="og:url" content="{url}">
<meta property="og:locale" content="de_DE">
<meta property="og:site_name" content="{NAME}">
{og_bild}
<meta name="theme-color" content="#5B1E2D">
<link rel="icon" href="{tiefe}logo.svg" type="image/svg+xml">
<link rel="icon" href="{tiefe}favicon-48.png" type="image/png" sizes="48x48">
<link rel="apple-touch-icon" href="{tiefe}apple-touch-icon.png">
<link rel="preload" href="{tiefe}schriften/Archivo-normal-600_900.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="{tiefe}schriften/InstrumentSans-normal-400.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="{tiefe}stil.css?v={STIL_VERSION}">
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
        reiter.append(f'<button type="button"{" class=\"an\"" if nr == 0 else ""} aria-label="{html.escape(m.get("kurz", s))}"><img src="bilder/{Path(m["bild"]).stem}-600.webp" alt="{html.escape(BILDNACHWEIS.get(m["bild"], {}).get("alt", ""))}" width="240" height="180" loading="lazy"><span class="cap">{html.escape(m.get("kurz", s))}</span><span class="balken"><i></i></span></button>')
    buehne = f"""<section class="buehne" aria-label="Aktuelle Themen">{"".join(dias)}
<div class="reiter"><div class="breite">{"".join(reiter)}</div></div></section>""" if dias else ""
    stapel = f"""<div class="stapel"><figure class="polaroid">{titelbild_tag(EIGEN_BILD, "", ' loading="lazy"')}<figcaption>Blick vom Herkules</figcaption></figure>
<div class="zettel notiz"><b class="marke">Mein Lieblingsmoment</b><p>Wenn um 15.45 Uhr die Große Fontäne hochgeht und alle, die sich zu nah ans Wasser gestellt haben, plötzlich nass werden.</p><span class="unterschrift">Aaron</span></div></div>"""
    alle_artikel = [s for s, m in alle.items() if m.get("art", "artikel") == "artikel" and s != "index"]
    vorhaben = []
    for titel, satz, haupt, mehr in VORHABEN:
        m = alle.get(haupt)
        if not m or not m.get("bild"):
            continue
        links = "".join(f'<li><a href="{s}/">{html.escape(alle[s].get("kurz", s))}</a></li>' for s in mehr if s in alle)
        vorhaben.append(f"""<div class="vorhaben"><a href="{haupt}/"><figure class="polaroid"><img src="bilder/{Path(m["bild"]).stem}-600.webp" alt="{html.escape(BILDNACHWEIS.get(m["bild"], {}).get("alt", ""))}" width="1200" height="900" loading="lazy"><figcaption>{html.escape(titel)}</figcaption></figure></a>
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
    skript = """<script>(function(){var d=[].slice.call(document.querySelectorAll('.dia')),b=[].slice.call(document.querySelectorAll('.reiter button')),i=0,t;if(d.length<2)return;function z(n){d[i].classList.remove('an');b[i].classList.remove('an');i=n;d[i].classList.add('an');b.forEach(function(x,k){x.classList.toggle('vorbei',k<i)});void b[i].offsetWidth;b[i].classList.add('an');clearTimeout(t);t=setTimeout(function(){z((i+1)%d.length)},matchMedia('(max-width:760px)').matches?4500:7000)}b.forEach(function(x,k){x.onclick=function(){z(k)}});var s=document.querySelector('.buehne'),x0=null;s.addEventListener('touchstart',function(e){x0=e.touches[0].clientX},{passive:true});s.addEventListener('touchend',function(e){if(x0===null)return;var dx=e.changedTouches[0].clientX-x0;x0=null;if(Math.abs(dx)>40)z((i+(dx<0?1:d.length-1))%d.length)},{passive:true});z(0)})();</script>"""
    return f"""{buehne}
<main id="inhalt">
<section class="breite start-intro"><div><h1>{h1_text}</h1><p class="lede">{lede}</p></div>{stapel}</section>
{vorhaben_html}
<section class="breite start-eigen">{eigenwerbung("index", "", quer=True)}</section>
{aktuell_html}
<section class="breite" style="padding-top:72px"><div class="mitte"><h2>Alle Ratgeber</h2></div>{karten(alle_artikel, alle, "")}</section>
</main>
{skript}"""


BILDNACHWEIS = {}
BILDMASSE = {}


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
        # WebP in zwei Breiten: 1200 für große Bildschirme, 600 für Handy und Polaroids (SEO-Prüfung 09.10.2026)
        # Zielgröße statt fester Qualität: 1200er höchstens ca. 110 KB, 600er ca. 40 KB
        for breite, endung, ziel_kb in ((1200, "", 110), (600, "-600", 40)):
            webp = ziel / (Path(name).stem + endung + ".webp")
            if not webp.exists() or webp.stat().st_mtime < q.stat().st_mtime:
                subprocess.run(["cwebp", "-quiet", "-size", str(ziel_kb * 1000), "-pass", "6", "-m", "6", "-resize", str(breite), "0",
                                str(q), "-o", str(webp)], capture_output=True)
        jpg = ziel / name
        if not jpg.exists() or jpg.stat().st_mtime < q.stat().st_mtime:
            subprocess.run(["sips", "-Z", "1200", "-s", "format", "jpeg", "-s", "formatOptions", "low", str(q),
                            "--out", str(jpg)], capture_output=True)
        if jpg.exists():
            r = subprocess.run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(jpg)], capture_output=True, text=True).stdout
            w, h = re.findall(r"pixel(?:Width|Height): (\d+)", r)[:2] or ("1200", "675")
            BILDMASSE[name] = (int(w), int(h))


def md_url(url):
    """Klammern kodieren, sonst bricht der Markdown-Link (Wikimedia-Dateinamen)."""
    return url.replace("(", "%28").replace(")", "%29")


# Fassung des Stylesheets im Link, damit Browser nach einer Änderung nicht die alte Fassung zeigen (15.10.2026)
import hashlib
STIL_VERSION = hashlib.sha1(((WURZEL / "vorlage" / "schriften.css").read_text() + (WURZEL / "vorlage" / "stil.css").read_text()).encode()).hexdigest()[:8]


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
            if n["lizenz"].startswith("eigen"):  # eigene Wohnungsfotos: kein Commons-Link (16.11.2026)
                zeilen.append(f"| {n['motiv']} | Wohnen am Bergpark | eigenes Foto | Wohnen am Bergpark, eigenes Foto |")
            else:
                zeilen.append(f"| {n['motiv']} | {n['urheber']} | [{n['lizenz']}]({md_url(n['lizenz_url'])}) | [Wikimedia Commons]({md_url(n['seite'])}) |")
        rumpf = ("# Bildnachweise\n\nDie Fotos auf Kasselkenner stehen unter freien Lizenzen. Danke an alle Fotografinnen und Fotografen. "
                 "Für die Seite haben wir die Fotos zugeschnitten, verkleinert und in ein anderes Dateiformat umgewandelt.\n\n"
                 + "\n".join(zeilen) + "\n")
        seiten["bildnachweise"] = ({"titel": "Bildnachweise | Kasselkenner", "beschreibung": "Urheber, Lizenzen und Quellen aller Fotos auf kasselkenner.de. Die Fotos sind zugeschnitten, verkleinert und umgewandelt.",
                                    "slug": "bildnachweise", "art": "rechtliches", "eigenwerbung": "nein", "sitemap": "nein"}, rumpf)
    alle = {s: m for s, (m, _) in seiten.items()}
    benutzt = {m["bild"] for m in alle.values() if m.get("bild")} | {EIGEN_BILD} | {w[1] for w in WOHNUNG.values()} | {u[0] for u in UEBERSICHT_FOTO.values()} | \
        {b for _, r in seiten.values() for b in re.findall(r"^!\[[^\]]*\]\(([^)\s]+)\)", r, re.M)}
    bilder_kopieren(benutzt)  # vorab, damit Bildmaße für og:image und JSON-LD bekannt sind
    for slug, (meta, rumpf) in seiten.items():
        rumpf = zaehler_zeilen(rumpf)
        rumpf, quellen = quellen_block(rumpf)
        h, faq, toc = markdown(rumpf)
        if quellen:
            h += "\n" + quellen
            toc.append(("quellen", "Quellen"))
        if meta.get("bild"):
            benutzt.add(meta["bild"])
        ziel = AUS / "index.html" if slug == "index" else (AUS / "404.html" if slug == "404" else AUS / slug / "index.html")
        ziel.parent.mkdir(parents=True, exist_ok=True)
        text = seite(meta, h, faq, toc, alle)
        if 'class="eigen"' in text:
            text = text.replace("</body>", EIGEN_JS + "\n</body>", 1)
        if 'class="lesefortschritt"' in text:
            text = text.replace("</body>", FORTSCHRITT_JS + "\n</body>", 1)
        if 'class="menue"' in text:
            text = text.replace("</body>", MENUE_JS + "\n</body>", 1)
        if 'class="strecke"' in text:
            text = text.replace("</body>", STRECKE_JS + "\n</body>", 1)
        if ZAEHLER and slug != "404":
            text = text.replace("</body>", ZAEHLER_JS + "\n</body>", 1)
        ziel.write_text(text)
    shutil.rmtree(AUS / "404", ignore_errors=True)
    for pfad, ziel in ZAEHLSEITEN.items():  # Zählseiten für Klicks auf Kasten und Einzeiler
        (AUS / pfad).mkdir(parents=True, exist_ok=True)
        (AUS / pfad / "index.html").write_text(zaehlseite(pfad, ziel))
    for f in ("logo.svg", "favicon-48.png", "apple-touch-icon.png", "icon-512.png", "aaron-160.webp", "aaron-400.webp", "aaron.jpg"):
        shutil.copy(WURZEL / "vorlage" / f, AUS / f)
    (AUS / f"{INDEXNOW}.txt").write_text(INDEXNOW)
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
    # KI- und Suchcrawler ausdrücklich willkommen (GEO)
    bots = ["Googlebot", "Bingbot", "GPTBot", "OAI-SearchBot", "ChatGPT-User", "PerplexityBot", "ClaudeBot", "Claude-SearchBot", "Google-Extended", "Applebot"]
    (AUS / "robots.txt").write_text("".join(f"User-agent: {b}\n" for b in bots) + "Allow: /\nDisallow: /zu/\n\nUser-agent: *\nAllow: /\nDisallow: /zu/\n\n"
                                    f"Sitemap: {DOMAIN}/sitemap.xml\n")
    stand_max = max(m.get("stand", heute) for m in alle.values())
    llms = [f"# {NAME}", "", f"> {UNTERZEILE}. Praktische, geprüfte Antworten für Besucher in Kassel; "
            "jede Angabe mit Quelle und Prüfdatum. Betrieben von den Gastgebern von Wohnen am Bergpark (Kassel-Bad Wilhelmshöhe).", "",
            f"Stand: {stand_max}", "", "## Seiten", "", f"- [Startseite]({DOMAIN}/): Überblick über alle Ratgeber"]
    for slug, (meta, _) in seiten.items():
        if meta.get("art", "artikel") == "artikel":
            llms.append(f"- [{meta['titel']}]({DOMAIN}/{slug}/): {meta.get('beschreibung', '')}")
    llms += ["", "## Kernfakten (je Seite, mit Prüfdatum)", ""]
    for slug, (meta, _) in seiten.items():
        paare = blick_lesen(meta.get("blick"))
        if meta.get("art", "artikel") == "artikel" and paare:
            llms.append(f"- {meta.get('kurz', slug)} (geprüft {meta.get('stand', heute)}): " + "; ".join(f"{k}: {v}" for k, v in paare))
    llms += ["", "## Über", "", f"- [Über uns]({DOMAIN}/ueber-uns/): wer schreibt und wie geprüft wird (Autor: Aaron Schiele)",
             f"- [Impressum]({DOMAIN}/impressum/), Kontakt: kontakt@kasselkenner.de",
             # gegen Verwechslung mit Namensvettern, die KI-Antworten am 15.10.2026 vermischten
             "- Betreiber: Wohnen am Bergpark UG, zehn Ferienwohnungen in Kassel (Lindenstraße 9 und Brabanter Straße 35 "
             "in Bad Wilhelmshöhe, eine Wohnung in Kirchditmold); einzige Website https://wohnenambergpark.de/. "
             "Ähnlich heißende Ferienwohnungen in Bad Wilhelmshöhe sind andere Betriebe."]
    (AUS / "llms.txt").write_text("\n".join(llms) + "\n")
    (AUS / "CNAME").write_text("kasselkenner.de")
    (AUS / ".nojekyll").write_text("")
    print(f"gebaut: {len(seiten)} Seiten, {len(benutzt)} Bilder → {AUS}")


if __name__ == "__main__":
    main()
