#!/usr/bin/env python3
"""Baut die ganze Website samt Entwürfen als Vollvorschau für ein Artifact (relative Links, Startseite als
startseite.html, Übersicht vorschau.html mit Sprung per #slug). Danach mit dem Artifact-Werkzeug
vorschau.html veröffentlichen, alle übrigen Dateien als files (URL in planung/freigabe.html).

Aufruf: python3 werkzeuge/vollvorschau.py <zielordner>
"""
import html, json, re, shutil, subprocess, sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
ziel = Path(sys.argv[1]).resolve()
shutil.rmtree(ziel, ignore_errors=True)
subprocess.run([sys.executable, str(WURZEL / "werkzeuge" / "vorschau.py"), str(ziel)], check=True, capture_output=True)
for n in ["CNAME", "robots.txt", "sitemap.xml", "llms.txt", "404.html", ".nojekyll"]:
    (ziel / n).unlink(missing_ok=True)
shutil.rmtree(ziel / "404", ignore_errors=True)
(ziel / "index.html").rename(ziel / "startseite.html")

for f in ziel.rglob("*.html"):
    tiefe = len(f.relative_to(ziel).parts) - 1
    pre = "../" * tiefe or "./"
    t = f.read_text()
    t = re.sub(r'((?:href|src)=")/(?!/)([^"]*)"', lambda m: m.group(1) + pre + m.group(2) + '"', t)

    def fix(m):
        v = m.group(2)
        if ":" in v or v.startswith("#") or not (v.endswith("/") or v in ("", ".", "..")):
            return m.group(0)
        v = v if v.endswith("/") else v + "/"
        z = v + "index.html"
        if z.replace("../", "").replace("./", "") == "index.html":
            z = v + "startseite.html"
        return m.group(1) + z + '"'
    t = re.sub(r'(href=")([^"]*)"', fix, t)
    f.write_text(t)

reihen = [("index", "Startseite", "startseite.html")]
for d in sorted(p for p in ziel.iterdir() if p.is_dir() and (p / "index.html").exists()):
    t = re.search(r"<title>([^<]*)", (d / "index.html").read_text()).group(1).split(" | ")[0]
    reihen.append((d.name, t, f"{d.name}/index.html"))
li = "\n".join(f'<li><a href="{h}"><b>{html.escape(t)}</b><span>kasselkenner.de/{"" if s == "index" else s + "/"}</span></a></li>' for s, t, h in reihen)
ziele = json.dumps({s: h for s, _, h in reihen})
dunkel = "--bg:#1B1416;--fg:#F3EEEA;--leise:#B9AFA9;--linie:#3A2E31;--wein:#E9A9B6;--orange:#FF9A4D;color-scheme:dark"
(ziel / "vorschau.html").write_text(f"""<title>Kasselkenner Vorschau</title>
<style>
:root{{--bg:#fff;--fg:#1D1A18;--leise:#5F5853;--linie:#E4DFD8;--wein:#5B1E2D;--orange:#C25200}}
@media (prefers-color-scheme: dark){{:root:not([data-theme="light"]){{{dunkel}}}}}
:root[data-theme="dark"]{{{dunkel}}}
body{{background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,sans-serif}}
.w{{max-width:760px;margin:0 auto;padding:32px 16px 48px}}
h1{{font:800 30px/1.1 system-ui,sans-serif;color:var(--wein);margin:0 0 6px;text-wrap:balance}}
p{{color:var(--leise);margin:0 0 20px}}
ul{{list-style:none;margin:0;padding:0;display:grid;gap:8px}}
a{{display:flex;flex-wrap:wrap;justify-content:space-between;gap:4px 12px;padding:12px 14px;border:1px solid var(--linie);border-radius:6px;color:var(--fg);text-decoration:none}}
a:hover{{border-color:var(--orange)}} a span{{color:var(--leise);font-size:14px}}
</style>
<script>(function(){{var z={ziele};var h=(location.hash||"").slice(1);if(z[h])location.replace(z[h]);}})();</script>
<div class="w"><h1>Kasselkenner – ganze Seiten</h1>
<p>So sehen die Seiten nach der Freigabe aus: echte Schriften, alle Fotos, volle Breite. Freigeben kannst du weiter auf der Freigabeseite.</p>
<ul>
{li}
</ul></div>
""")
print(json.dumps({str(p.relative_to(ziel)): str(p.relative_to(ziel)) for p in sorted(ziel.rglob("*")) if p.is_file() and p.name != "vorschau.html"}))
