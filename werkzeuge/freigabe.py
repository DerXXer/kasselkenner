#!/usr/bin/env python3
"""Freigabe-Weg für Kasselkenner.

  python3 werkzeuge/freigabe.py paket <slug> [...]
      Baut je Entwurf eine Vorschau (eigenständiges HTML mit eingebettetem Stil und kleinem
      Titelbild) samt Lektorats-Hinweisen als JSON nach _entwuerfe/.freigabe/<slug>.json.
      Diese Dateien schreibt Claude mit ArtifactData (batch, op set, file_path) in die
      Sammlung `entwuerfe` der Freigabeseite.

  python3 werkzeuge/freigabe.py uebernehmen <ordner-mit-db-export>
      Liest den Export der Sammlung (ArtifactData list mit out_dir) und verschiebt jeden
      Entwurf mit status "freigegeben" nach inhalt/. Gibt die übernommenen Slugs aus;
      danach bauen, committen, pushen und den Status auf "online" setzen.
"""
import base64, json, re, subprocess, sys, tempfile
from datetime import datetime, timezone
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL / "werkzeuge"))
import bauen  # noqa: E402
import pruefen  # noqa: E402

ENTW = WURZEL / "_entwuerfe"
FREIGABE_URL = "https://claude.ai/artifact/EsxUgEhwNQ9RWDVVuGn67C"


def kleines_bild(name):
    q = WURZEL / "bilder" / name
    if not q.exists():
        return ""
    with tempfile.TemporaryDirectory() as t:
        z = Path(t) / "v.jpg"
        subprocess.run(["sips", "-Z", "640", "-s", "format", "jpeg", "-s", "formatOptions", "60", str(q), "--out", str(z)],
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
    if meta.get("bild"):
        seite = re.sub(r'src="(\.\./)?bilder/[^"]+"', f'src="{kleines_bild(meta["bild"])}"', seite, count=1)
    seite = re.sub(r'<img src="(\.\./)?bilder/[^"]+"[^>]*>', "", seite)
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
        hinweise = []
        notiz = ENTW / f"{slug}.hinweis.txt"
        if notiz.exists():
            hinweise.append(notiz.read_text().strip())
        hinweise += [w for w in warn if not w.startswith("Zahlen nicht")]
        doc = {"titel": meta.get("titel", slug), "beschreibung": meta.get("beschreibung", ""),
               "woerter": len(pruefen.norm(rumpf).split()), "vorschau": seite,
               "hinweise": "\n".join(hinweise), "status": "wartet", "kommentar": "",
               "eingestellt": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        out = ziel / f"{slug}.json"
        out.write_text(json.dumps(doc, ensure_ascii=False))
        kb = out.stat().st_size // 1024
        print(f"{slug}: {out} ({kb} KB){'  ZU GROSS' if kb > 250 else ''}")


def uebernehmen(ordner):
    fertig = []
    for f in sorted(Path(ordner).rglob("*.json")):
        d = json.loads(f.read_text())
        body = d.get("data", d)
        slug = d.get("id") or d.get("doc_id") or f.stem
        if body.get("status") != "freigegeben":
            continue
        q = ENTW / f"{slug}.md"
        if not q.exists():
            print(f"{slug}: Entwurf fehlt", file=sys.stderr)
            continue
        q.rename(WURZEL / "inhalt" / f"{slug}.md")
        fertig.append(slug)
    print(" ".join(fertig))


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    {"paket": lambda a: paket(a), "uebernehmen": lambda a: uebernehmen(a[0])}[sys.argv[1]](sys.argv[2:])
