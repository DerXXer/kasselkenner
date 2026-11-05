#!/usr/bin/env python3
"""Baut eine Vorschau der ganzen Website samt Entwürfen in einen Ordner (nicht docs/).

Aufruf: python3 werkzeuge/vorschau.py <zielordner>
"""
import sys, tempfile
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL / "werkzeuge"))
import bauen  # noqa: E402

ziel = Path(sys.argv[1]).resolve()
with tempfile.TemporaryDirectory() as tmp:
    for q in list((WURZEL / "inhalt").glob("*.md")) + [p for p in (WURZEL / "_entwuerfe").glob("*.md") if "." not in p.stem]:
        text = q.read_text()
        if not text.startswith("---"):  # Gastbeiträge und andere Texte ohne Seitenkopf sind keine Seiten
            continue
        (Path(tmp) / q.name).write_text(text)
    bauen.INHALT, bauen.AUS = Path(tmp), ziel
    bauen.main()
