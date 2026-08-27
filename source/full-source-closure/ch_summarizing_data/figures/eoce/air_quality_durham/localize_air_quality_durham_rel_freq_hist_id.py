"""Deterministically localize the reader-visible label in the pinned PDF."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import pikepdf


AUTHORITY_SHA256 = "4f13ab9e61d1368ceeaa28f9761db94384919cdfaeffb46c462d0aaaee1a30c1"
SOURCE = b"182.58 4.32 Tm [(Daily A) 30 (QI)] TJ"
TARGET = b"177.30 4.32 Tm (AQI harian) Tj"


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
