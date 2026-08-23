"""Localize labels and replace non-portable ZapfDingbats point glyphs."""

from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path

import pikepdf


AUTHORITY_SHA256 = "b13478ff6bd0d1b93d56b7c38664f3c5d99e2e76eaddd568f8187afb47b1dea5"
REPLACEMENTS = (
    (
        b"154.57 4.32 Tm [(Gestation \\(da) 30 (ys\\))] TJ",
        b"131.30 4.32 Tm (Masa kehamilan \\(hari\\)) Tj",
    ),
    (
        b"14.40 108.32 Tm [(Lif) 30 (e Span \\(y) 20 (ears\\))] TJ",
        b"14.40 86.85 Tm (Rentang hidup \\(tahun\\)) Tj",
    ),
)

# The authority stores each observation as the ZapfDingbats character ``l``.
# Poppler on a system without a display ZapfDingbats/Symbol font silently drops
# every point.  The 62-row source dataset yields 55 plotted complete cases;
# replace those 55 text glyphs with explicit filled-and-stroked Bezier circles
# at the same visual centres.  A 1.77-pt path radius plus the inherited
# 0.75-pt stroke reproduces the authority glyph's approximately 2.15-pt
# rendered outer radius in both MuPDF and Poppler.
POINT_RUN = re.compile(
    rb"BT\s+/F1 1 Tf 2 Tr 4\.99 0 0 4\.99 "
    rb"(?P<x>-?\d+\.\d+) (?P<y>-?\d+\.\d+) Tm \(l\) Tj 0 Tr\s+ET"
)
POINT_CENTER_OFFSET_X = 1.96
POINT_CENTER_OFFSET_Y = 1.73
POINT_PATH_RADIUS = 1.77
KAPPA = 0.5522847498307936


def vector_circle(match: re.Match[bytes]) -> bytes:
    """Return one explicit circle in the authority point's graphics state."""
    cx = float(match.group("x")) + POINT_CENTER_OFFSET_X
    cy = float(match.group("y")) + POINT_CENTER_OFFSET_Y
    r = POINT_PATH_RADIUS
    k = r * KAPPA
    return (
        "% R011-B005 portable point\n"
        f"{cx + r:.5f} {cy:.5f} m\n"
        f"{cx + r:.5f} {cy + k:.5f} {cx + k:.5f} {cy + r:.5f} {cx:.5f} {cy + r:.5f} c\n"
        f"{cx - k:.5f} {cy + r:.5f} {cx - r:.5f} {cy + k:.5f} {cx - r:.5f} {cy:.5f} c\n"
        f"{cx - r:.5f} {cy - k:.5f} {cx - k:.5f} {cy - r:.5f} {cx:.5f} {cy - r:.5f} c\n"
        f"{cx + k:.5f} {cy - r:.5f} {cx + r:.5f} {cy - k:.5f} {cx + r:.5f} {cy:.5f} c\n"
        "B"
    ).encode("ascii")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("authority_pdf", type=Path)
    parser.add_argument("output_pdf", type=Path)
    args = parser.parse_args()

    if sha256(args.authority_pdf) != AUTHORITY_SHA256:
        raise SystemExit("authority PDF identity mismatch")

    with pikepdf.open(args.authority_pdf) as pdf:
        if len(pdf.pages) != 1:
            raise SystemExit("expected exactly one page")
        page = pdf.pages[0]
        if tuple(float(v) for v in page.MediaBox) != (0.0, 0.0, 396.0, 309.0):
            raise SystemExit("authority page box mismatch")
        stream = page.Contents
        before = stream.read_bytes()
        after = before
        for old, new in REPLACEMENTS:
            if after.count(old) != 1:
                raise SystemExit(f"expected one source label run: {old!r}")
            after = after.replace(old, new, 1)
        point_runs = list(POINT_RUN.finditer(after))
        if len(point_runs) != 55:
            raise SystemExit(f"expected 55 ZapfDingbats point runs, found {len(point_runs)}")
        after, replacement_count = POINT_RUN.subn(vector_circle, after)
        if replacement_count != 55 or b"/F1" in after:
            raise SystemExit("point-vectorization closure failed")
        stream.write(after)
        fonts = page.Resources["/Font"]
        if "/F1" not in fonts:
            raise SystemExit("expected the authority ZapfDingbats /F1 resource")
        del fonts["/F1"]
        args.output_pdf.parent.mkdir(parents=True, exist_ok=True)
        pdf.save(
            args.output_pdf,
            deterministic_id=True,
            compress_streams=True,
            recompress_flate=True,
            object_stream_mode=pikepdf.ObjectStreamMode.disable,
        )


if __name__ == "__main__":
    main()
