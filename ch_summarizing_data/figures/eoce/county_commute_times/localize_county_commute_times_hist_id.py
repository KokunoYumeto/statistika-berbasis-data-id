"""Deterministically localize the reader-visible label in the pinned PDF."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import pikepdf


AUTHORITY_SHA256 = "30ac80e05848769d7db67966b2b5e36f39bed7d12f9def0c8e66b4f563749013"
SOURCE = b"191.03 7.20 Tm [(Mean w) 10 (or) -15 (k tr) 10 (a) 20 (v) 25 (el \\(in min\\))] TJ"
TARGET = b"141.55 7.20 Tm (Rerata waktu perjalanan kerja \\(menit\\)) Tj"


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
        if tuple(float(v) for v in page.MediaBox) != (0.0, 0.0, 540.0, 288.0):
            raise SystemExit("authority page box mismatch")
        stream = page.Contents
        before = stream.read_bytes()
        if before.count(SOURCE) != 1:
            raise SystemExit("expected exactly one source label run")
        stream.write(before.replace(SOURCE, TARGET, 1))
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
