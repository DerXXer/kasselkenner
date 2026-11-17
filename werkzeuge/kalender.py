"""Kalender zum Abonnieren (Linkplan 17.11.2026): Wasserspiele 2027 und alle Termine Kassel 2027 als .ics.

Termine nur aus dem Faktenspeicher: BP-218 (49 Wasserspieltage), BP-004 (14.30 bis ca. 16 Uhr), BP-219
(Beleuchtete Wasserspiele 14./15. Mai, Uhrzeit offen), DO-001 (documenta 16), KS-060 (Zissel), KS-227
(Drachenboot-Cup). Ändert sich ein Termin: hier ändern und STAND hochsetzen; Abonnenten bekommen es beim
nächsten Abgleich (REFRESH-INTERVAL ein Tag). UIDs nie ändern, sonst doppeln sich Termine bei Abonnenten.
"""
from datetime import date, timedelta

STAND = "20261117T120000Z"   # DTSTAMP und LAST-MODIFIED; bei jeder Änderung hochsetzen
DOMAIN = "https://kasselkenner.de"

WASSERSPIELTAGE = {5: [1, 2, 5, 6, 9, 12, 16, 17, 19, 23, 26, 27, 30], 6: [2, 6, 9, 13, 16, 20, 23, 27, 30],
                   7: [4, 7, 11, 14, 18, 21, 25, 28], 8: [1, 4, 8, 11, 15, 18, 22, 25, 29],
                   9: [1, 5, 8, 12, 15, 19, 22, 26, 29], 10: [3]}

TZ = """BEGIN:VTIMEZONE
TZID:Europe/Berlin
BEGIN:DAYLIGHT
TZOFFSETFROM:+0100
TZOFFSETTO:+0200
TZNAME:CEST
DTSTART:19700329T020000
RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU
END:DAYLIGHT
BEGIN:STANDARD
TZOFFSETFROM:+0200
TZOFFSETTO:+0100
TZNAME:CET
DTSTART:19701025T030000
RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU
END:STANDARD
END:VTIMEZONE"""


def _esc(t):
    return t.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _falten(zeile):
    """Zeilen nach RFC 5545 auf 75 Byte falten."""
    roh, aus, teil = zeile.encode("utf-8"), [], b""
    for ch in zeile:
        b = ch.encode("utf-8")
        if len(teil) + len(b) > (75 if not aus else 74):
            aus.append(teil.decode("utf-8"))
            teil = b""
        teil += b
    aus.append(teil.decode("utf-8"))
    return "\r\n ".join(aus) if len(roh) > 75 else zeile


def wasserspiele():
    ev = []
    for monat, tage in WASSERSPIELTAGE.items():
        for tag in tage:
            d = date(2027, monat, tag)
            ev.append({"uid": f"wasserspiele-{d.isoformat()}@kasselkenner.de",
                       "start": f"TZID=Europe/Berlin:{d:%Y%m%d}T143000", "ende": f"TZID=Europe/Berlin:{d:%Y%m%d}T160000",
                       "titel": "Wasserspiele im Bergpark Wilhelmshöhe",
                       "ort": "Bergpark Wilhelmshöhe, Kassel (Beginn an den Kaskaden unterhalb des Herkules)",
                       "text": "14.30 Uhr Kaskaden am Herkules, 15.05 Steinhöfer Wasserfall, 15.20 Teufelsbrücke, "
                               "15.30 Aquädukt, 15.45 Große Fontäne. Ablauf, Parken und Anreise: "
                               f"{DOMAIN}/wasserspiele-kassel/ · Ohne Gewähr, Ausfälle (Wassermangel, Unwetter) möglich.",
                       "url": f"{DOMAIN}/wasserspiele-kassel/"})
    return ev


def weitere():
    def ganztag(uid, von, bis_einschl, titel, ort, text, url):
        return {"uid": f"{uid}@kasselkenner.de", "start": f"VALUE=DATE:{von:%Y%m%d}",
                "ende": f"VALUE=DATE:{bis_einschl + timedelta(days=1):%Y%m%d}", "titel": titel, "ort": ort,
                "text": text, "url": url}
    return [
        ganztag("beleuchtete-wasserspiele-2027-05-14", date(2027, 5, 14), date(2027, 5, 14),
                "Beleuchtete Wasserspiele im Bergpark", "Bergpark Wilhelmshöhe, Kassel",
                f"Uhrzeit steht noch nicht fest. Stand und Ablauf: {DOMAIN}/beleuchtete-wasserspiele/", f"{DOMAIN}/beleuchtete-wasserspiele/"),
        ganztag("beleuchtete-wasserspiele-2027-05-15", date(2027, 5, 15), date(2027, 5, 15),
                "Beleuchtete Wasserspiele im Bergpark", "Bergpark Wilhelmshöhe, Kassel",
                f"Uhrzeit steht noch nicht fest. Stand und Ablauf: {DOMAIN}/beleuchtete-wasserspiele/", f"{DOMAIN}/beleuchtete-wasserspiele/"),
        ganztag("documenta-16-2027", date(2027, 6, 12), date(2027, 9, 19), "documenta 16 in Kassel", "Kassel",
                f"12. Juni bis 19. September 2027. Was du jetzt schon wissen kannst: {DOMAIN}/documenta-2027/", f"{DOMAIN}/documenta-2027/"),
        ganztag("zissel-2027", date(2027, 7, 30), date(2027, 8, 2), "Zissel an der Fulda", "Fulda-Ufer, Kassel",
                f"Volks- und Wasserfest. Anreise und Programm: {DOMAIN}/zissel-kassel/", f"{DOMAIN}/zissel-kassel/"),
        {"uid": "zissel-drachenboot-2027@kasselkenner.de", "start": "TZID=Europe/Berlin:20270731T093000",
         "ende": "TZID=Europe/Berlin:20270731T170000", "titel": "Zissel Drachenboot-Cup", "ort": "Gelände des CKS98, Kassel",
         "text": f"9.30 bis etwa 17 Uhr. Mehr zum Zissel: {DOMAIN}/zissel-kassel/", "url": f"{DOMAIN}/zissel-kassel/"},
    ]


def ics(name, beschreibung, ereignisse):
    z = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//kasselkenner.de//Termine 2027//DE", "CALSCALE:GREGORIAN",
         "METHOD:PUBLISH", f"X-WR-CALNAME:{_esc(name)}", f"X-WR-CALDESC:{_esc(beschreibung)}",
         "X-WR-TIMEZONE:Europe/Berlin", "REFRESH-INTERVAL;VALUE=DURATION:P1D", "X-PUBLISHED-TTL:P1D", TZ]
    for e in ereignisse:
        z += ["BEGIN:VEVENT", f"UID:{e['uid']}", f"DTSTAMP:{STAND}", f"LAST-MODIFIED:{STAND}",
              f"DTSTART;{e['start']}", f"DTEND;{e['ende']}", f"SUMMARY:{_esc(e['titel'])}",
              f"LOCATION:{_esc(e['ort'])}", f"DESCRIPTION:{_esc(e['text'])}", f"URL:{e['url']}",
              "TRANSP:TRANSPARENT", "END:VEVENT"]
    z.append("END:VCALENDAR")
    return "\r\n".join(_falten(x) if "\n" not in x else x.replace("\n", "\r\n") for x in z) + "\r\n"


DATEIEN = {
    "wasserspiele-2027.ics": ("Wasserspiele Kassel 2027", "Alle 49 Wasserspieltage im Bergpark Wilhelmshöhe 2027, "
                              "gepflegt von kasselkenner.de", wasserspiele),
    "kassel-2027.ics": ("Termine Kassel 2027", "Wasserspiele, Beleuchtete Wasserspiele, documenta 16 und Zissel 2027, "
                        "gepflegt von kasselkenner.de", lambda: wasserspiele() + weitere()),
}

# Kasten auf diesen Seiten (Datei, Satz)
KASTEN = {
    "wasserspiele-kassel": ("wasserspiele-2027.ics", "Hol dir alle 49 Wasserspieltage 2027 in deinen Kalender. Ändert sich ein Termin, ändert er sich bei dir mit."),
    "termine-kassel-2027": ("kassel-2027.ics", "Hol dir alle Termine 2027 in deinen Kalender: Wasserspiele, beleuchtete Wasserspiele, documenta und Zissel. Ändert sich ein Termin, ändert er sich bei dir mit."),
}


def kasten(slug, tiefe):
    datei, satz = KASTEN[slug]
    abo = f"webcal://kasselkenner.de/kalender/{datei}"
    return (f'<aside class="kalender-abo" aria-label="Kalender zum Abonnieren"><p class="dach">Kalender zum Abonnieren</p>'
            f'<p>{satz}</p><p class="knoepfe"><a class="knopf" href="{abo}">Kalender abonnieren</a> '
            f'<a href="{tiefe}kalender/{datei}" download>als Datei laden</a></p>'
            f'<p class="klein">Für Vereine und Websites: Die Kalenderadresse {DOMAIN}/kalender/{datei} darfst du gern '
            f'weitergeben und verlinken.</p></aside>')


def schreiben(aus):
    ordner = aus / "kalender"
    ordner.mkdir(exist_ok=True)
    for datei, (name, beschreibung, quelle) in DATEIEN.items():
        (ordner / datei).write_bytes(ics(name, beschreibung, quelle()).encode("utf-8"))
    return len(DATEIEN)
