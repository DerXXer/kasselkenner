#!/usr/bin/env python3
"""Freigabe-Weg für Kasselkenner.

  python3 werkzeuge/freigabe.py paket <slug> [...]
      Baut je Entwurf eine Vorschau (eigenständiges HTML mit eingebettetem Stil und kleinem
      Titelbild) samt Lektorats-Hinweisen als JSON nach _entwuerfe/.freigabe/<slug>.json.
      Diese Dateien schreibt Claude mit ArtifactData (batch, op set, file_path) in die
      Sammlung `entwuerfe` der Freigabeseite. Beginnt <slug>.hinweis.txt mit „Rang <n>: <warum>“,
      steht der Entwurf auf der Freigabeseite an Stelle n mit diesem Grund.

  python3 werkzeuge/freigabe.py uebernehmen <ordner-mit-db-export>
      Liest den Export der Sammlung (ArtifactData list mit out_dir) und verschiebt jeden
      Entwurf mit status "freigegeben" nach inhalt/, dazu jeden mit gültigem Prüfer-„frei“
      (Fingerabdruck passt, Lektorat ohne Fehler), außer Aaron hat ihn zurückgegeben oder
      verworfen. Gibt die übernommenen Slugs aus; danach bauen, committen, pushen und den
      Status auf "online" setzen. Jede Übernahme: Zeile in _entwuerfe/.pruefer/freigegeben.tsv.

  Prüfer (Aaron, 04.11.2026: ein unabhängiger Prüfer darf freigeben, Aaron bekommt eine Stichprobe):
  python3 werkzeuge/freigabe.py urteil <slug> frei|zurueck "<Gründe>"
      Urteil nach _entwuerfe/.pruefer/<slug>.json; gilt nur für diese Fassung von Entwurf und
      Belegdatei. „frei“ nie für Rechtliches und Nicht-Artikel, ohne Belege oder mit Lektoratsfehler.
  python3 werkzeuge/freigabe.py pruefer-stand [<ordner>]
      Je Entwurf: zu prüfen | frei | zurück: <Gründe> | ausgenommen.
  python3 werkzeuge/freigabe.py stichprobe [--tage 7] [--anzahl 3]
      Neueste vom Prüfer freigegebene Seiten als Adressen. „heute“ = KK_HEUTE, sonst Tagesdatum.
"""
import base64, hashlib, json, os, re, subprocess, sys, tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL / "werkzeuge"))
import bauen  # noqa: E402
import pruefen  # noqa: E402

ENTW = WURZEL / "_entwuerfe"
FREIGABE_URL = "https://claude.ai/artifact/EsxUgEhwNQ9RWDVVuGn67C"


def kleines_bild(name, breite=640):
    q = next((k for k in (WURZEL / "bilder" / name, WURZEL / "docs" / "bilder" / name, WURZEL / "vorlage" / name)
              if k.exists()), None)
    if q is None:
        return ""
    with tempfile.TemporaryDirectory() as t:
        z = Path(t) / "v.jpg"
        subprocess.run(["sips", "-Z", str(breite), "-s", "format", "jpeg", "-s", "formatOptions", "60", str(q), "--out", str(z)],
                       capture_output=True)
        return "data:image/jpeg;base64," + base64.b64encode(z.read_bytes()).decode()


def vorschau(slug):
    datei = ENTW / f"{slug}.md"
    meta, rumpf = bauen.kopf_lesen(datei.read_text())
    meta.setdefault("slug", slug)
    bauen.nachweise_lesen()
    alle = {p.stem: bauen.kopf_lesen(p.read_text())[0] for p in list((WURZEL / "inhalt").glob("*.md")) + list(ENTW.glob("*.md"))
            if "." not in p.stem}
    for s, m in alle.items():
        m.setdefault("slug", s)
    h, faq, toc = bauen.markdown(rumpf)
    seite = bauen.seite(meta, h, faq, toc, alle)
    css = (WURZEL / "vorlage" / "stil.css").read_text()   # ohne lokale Schriften (Vorschau nutzt Ersatzschriften)
    seite = re.sub(r'<link rel="stylesheet"[^>]+>', f"<style>{css}</style>", seite)
    seite = re.sub(r'<link rel="preload"[^>]+>', "", seite)
    seite = re.sub(r'<script type="application/ld\+json">.*?</script>', "", seite, flags=re.S)
    seite = re.sub(r'<link rel="icon"[^>]+>', "", seite)
    # Platz sparen: Bilder in Karten, Eigenwerbung und Stapel weglassen, nur das Titelbild klein einbetten
    seite = re.sub(r'(<aside class="eigen"[^>]*>)\s*<img[^>]*>', r"\1", seite)
    seite = re.sub(r'(<figure class="polaroid">)<img[^>]*>', r"\1", seite)
    # leere Kartenrahmen weglassen statt sie leer zu zeigen (Aaron 05.11.2026)
    seite = re.sub(r'<figure class="polaroid"><figcaption>[^<]*</figcaption></figure>', "", seite)
    if meta.get("bild"):
        seite = re.sub(r'src="(\.\./)?bilder/[^"]+"', f'src="{kleines_bild(meta["bild"], 560)}"', seite, count=1)
    # Bilder im Text klein einbetten, damit die Vorschau zeigt, was online steht
    def im_text(m):
        quelle = kleines_bild(m.group(2) + ".jpg", 360)
        return f'{m.group(1)}<img src="{quelle}" alt="{m.group(3)}" loading="lazy">' if quelle else m.group(1)
    seite = re.sub(r'(<figure class="polaroid im-text[^"]*">)<img src="(?:\.\./)?bilder/([^"]+?)-600\.webp"[^>]*?alt="([^"]*)"[^>]*>',
                   im_text, seite)
    seite = re.sub(r'<img src="(\.\./)?bilder/[^"]+"[^>]*>', "", seite)
    seite = re.sub(r'src="(\.\./)?aaron-160\.webp"', lambda m: f'src="{kleines_bild("aaron-160.webp", 160)}"', seite)
    return meta, rumpf, seite


def paket(slugs):
    ziel = ENTW / ".freigabe"
    ziel.mkdir(exist_ok=True)
    for slug in slugs:
        meta, rumpf, seite = vorschau(slug)
        fehler, warn = pruefen.pruefe(ENTW / f"{slug}.md")
        if fehler:
            print(f"{slug}: {len(fehler)} Fehler – nicht eingestellt", file=sys.stderr)
            for f in fehler:
                print("  ", f, file=sys.stderr)
            continue
        hinweise, rang = [], {}
        notiz = ENTW / f"{slug}.hinweis.txt"
        if notiz.exists():
            text = notiz.read_text().strip()
            # erste Zeile „Rang <n>: <warum>“ ordnet die Freigabeseite nach Wichtigkeit (20.10.2026)
            m = re.match(r"Rang (\d+): (.*)\n?", text)
            if m:
                rang = {"rang": int(m.group(1)), "warum": m.group(2).strip()}
                text = text[m.end():].strip()
            if text:
                hinweise.append(text)
        hinweise += [w for w in warn if not w.startswith("Zahlen nicht")]
        doc = {"titel": meta.get("titel", slug), "beschreibung": meta.get("beschreibung", ""),
               "woerter": len(pruefen.norm(rumpf).split()), "vorschau": seite,
               "hinweise": "\n".join(hinweise), "status": "wartet", "kommentar": "",
               "eingestellt": datetime.now(timezone.utc).isoformat(timespec="seconds"), **rang}
        out = ziel / f"{slug}.json"
        out.write_text(json.dumps(doc, ensure_ascii=False))
        kb = out.stat().st_size // 1024
        print(f"{slug}: {out} ({kb} KB){'  ZU GROSS' if kb > 250 else ''}")


# ---------------------------------------------------------------- Prüfer (Aaron, 04.11.2026)
PRUEFER = ENTW / ".pruefer"
LISTE = PRUEFER / "freigegeben.tsv"
AUSGENOMMEN = {"datenschutz", "impressum", "ueber-uns", "index", "404"}   # rechtlich oder Sonderseite: nur Aaron
DOMAIN = "https://kasselkenner.de"


def heute():
    return date.fromisoformat(os.environ["KK_HEUTE"]) if os.environ.get("KK_HEUTE") else date.today()


def entwuerfe():
    """Slugs der Entwürfe; Beleg-, Hinweis- und Offen-Dateien zählen nicht."""
    return sorted(p.stem for p in ENTW.glob("*.md") if "." not in p.stem)


def fingerabdruck(slug):
    h = hashlib.sha256()
    for p in (ENTW / f"{slug}.md", ENTW / f"{slug}.belege.md"):
        h.update(p.read_bytes() if p.exists() else b"")
        h.update(b"\0")
    return h.hexdigest()


def ausgenommen(slug):
    meta, _ = bauen.kopf_lesen((ENTW / f"{slug}.md").read_text(encoding="utf-8"))
    return slug in AUSGENOMMEN or (meta.get("art") or "artikel") != "artikel"


def gegen_frei(slug):
    """Warum der Prüfer diesen Entwurf nicht freigeben darf (leer = darf)."""
    if ausgenommen(slug):
        return ["rechtliche oder Sonderseite (keine Artikelseite): gibt nur Aaron frei"]
    b = ENTW / f"{slug}.belege.md"
    if not b.exists() or not b.read_text(encoding="utf-8").strip():
        return ["Belegdatei fehlt oder ist leer"]
    fehler, _ = pruefen.pruefe(ENTW / f"{slug}.md")
    return ["Lektorat: " + f for f in fehler]


def urteil_lesen(slug):
    """Gültiges Urteil für die jetzige Fassung, sonst None (fehlt oder Entwurf seither geändert)."""
    p = PRUEFER / f"{slug}.json"
    if not p.exists() or not (ENTW / f"{slug}.md").exists():
        return None
    u = json.loads(p.read_text(encoding="utf-8"))
    return u if u.get("fingerabdruck") == fingerabdruck(slug) else None


def urteil(a):
    if len(a) < 2:
        sys.exit('urteil <slug> frei|zurueck "<Gründe>"')
    slug, wort, gruende = a[0], a[1], " ".join(a[2:]).strip()
    if not (ENTW / f"{slug}.md").exists():
        sys.exit(f"{slug}: Entwurf fehlt")
    if wort not in ("frei", "zurueck"):
        sys.exit(f"{slug}: Urteil „{wort}“ unbekannt — frei oder zurueck")
    if wort == "zurueck" and not gruende:
        sys.exit(f"{slug}: zurueck braucht Gründe")
    if wort == "frei":
        nein = gegen_frei(slug)
        if nein:
            sys.exit(f"{slug}: frei abgelehnt\n  " + "\n  ".join(nein))
    PRUEFER.mkdir(parents=True, exist_ok=True)
    doc = {"urteil": wort, "gruende": gruende, "fingerabdruck": fingerabdruck(slug), "datum": heute().isoformat()}
    (PRUEFER / f"{slug}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{slug}: {wort}")


def aarons_status(ordner):
    """Aarons Status je Slug aus den Karten (<slug>.json) oder dem Export ({"id", "data"})."""
    status = {}
    for f in sorted(Path(ordner).rglob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            print(f"{f}: nicht lesbar ({e})", file=sys.stderr)
            continue
        body = d.get("data", d)
        status[d.get("id") or d.get("doc_id") or f.stem] = body.get("status")
    return status


def liste_eintragen(slug, wer):
    PRUEFER.mkdir(parents=True, exist_ok=True)
    zeile = f"{heute().isoformat()}\t{slug}\t{wer}\n"
    alt = LISTE.read_text(encoding="utf-8") if LISTE.exists() else ""
    if zeile not in alt.splitlines(keepends=True):
        with LISTE.open("a", encoding="utf-8") as f:
            f.write(zeile)


def uebernehmen(ordner):
    status = aarons_status(ordner)
    fertig, vom_pruefer = [], []

    def online_stellen(slug, wer):
        (ENTW / f"{slug}.md").rename(WURZEL / "inhalt" / f"{slug}.md")
        liste_eintragen(slug, wer)
        fertig.append(slug)

    for slug, st in status.items():
        if st != "freigegeben":
            continue
        if not (ENTW / f"{slug}.md").exists():
            print(f"{slug}: Entwurf fehlt", file=sys.stderr)
            continue
        online_stellen(slug, "aaron")
    for slug in entwuerfe():
        if status.get(slug) in ("zurueck", "verworfen"):
            continue
        u = urteil_lesen(slug)
        if not u:
            continue
        if u["urteil"] == "zurueck":
            print(f"vom Prüfer zurück: {slug}: {u['gruende']}", file=sys.stderr)
        elif u["urteil"] == "frei":
            nein = gegen_frei(slug)
            if nein:
                print(f"{slug}: Prüfer-frei ungültig — " + "; ".join(nein), file=sys.stderr)
                continue
            online_stellen(slug, "pruefer")
            vom_pruefer.append(slug)
    if vom_pruefer:
        print("vom Prüfer freigegeben: " + ", ".join(vom_pruefer), file=sys.stderr)
    print(" ".join(fertig))


def pruefer_stand(a):
    status = aarons_status(a[0] if a else ENTW / ".paperclip")
    for slug in entwuerfe():
        if status.get(slug) in ("freigegeben", "verworfen"):
            continue
        u = urteil_lesen(slug)
        if ausgenommen(slug):
            stand = "ausgenommen"
        elif not u:
            stand = "zu prüfen"
        else:
            stand = "frei" if u["urteil"] == "frei" else f"zurück: {u['gruende']}"
        print(f"{slug}  {stand}")


def stichprobe(a):
    import argparse
    p = argparse.ArgumentParser(prog="freigabe.py stichprobe")
    p.add_argument("--tage", type=int, default=7)
    p.add_argument("--anzahl", type=int, default=3)
    arg = p.parse_args(a)
    ab = heute() - timedelta(days=arg.tage)       # die letzten <tage> Tage bis heute, ohne Überschneidung zur Vorwoche
    zeilen = []
    for i, z in enumerate(LISTE.read_text(encoding="utf-8").splitlines() if LISTE.exists() else []):
        teile = z.split("\t")
        if len(teile) < 3 or teile[2].strip() != "pruefer":
            continue
        try:
            tag = date.fromisoformat(teile[0].strip())
        except ValueError:
            continue
        if ab < tag <= heute():
            zeilen.append((tag, i, teile[1].strip()))
    gesehen = []
    for _, _, slug in sorted(zeilen, reverse=True):
        if slug not in gesehen:
            gesehen.append(slug)
    for slug in gesehen[:arg.anzahl]:
        print(f"{DOMAIN}/{slug}/")


BEFEHLE = {   # Befehl: (mindestens Argumente, Ausführung)
    "paket": (1, paket),
    "uebernehmen": (1, lambda a: uebernehmen(a[0])),
    "urteil": (2, urteil),
    "pruefer-stand": (0, pruefer_stand),
    "stichprobe": (0, stichprobe),
}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in BEFEHLE or len(sys.argv) - 2 < BEFEHLE[sys.argv[1]][0]:
        print(__doc__, file=sys.stderr)
        sys.exit(1)
    BEFEHLE[sys.argv[1]][1](sys.argv[2:])
