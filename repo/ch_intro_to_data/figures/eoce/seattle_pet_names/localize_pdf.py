"""Deterministically localize the pinned Seattle pet-name PDF with MuPDF.

The authority PDF converts every visible glyph to vector outlines. MuPDF
therefore imports the valid pinned page intact and appends two opaque strips
with searchable id-ID axis labels. The clean, non-incremental save avoids the
invalid cloned page tree produced by the former pypdf implementation.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import pymupdf as fitz


PINNED_SHA256 = "2e9ab77181a51c38b40d024f149292f488d423328fdfd64240067f651feed975"
PINNED_COMMIT = "fee25091fb24e89c36296fd67c48c1fcf7a93b6e"
PINNED_TREE = "d61cc601e7d97759ce805900520f784d02a0489e"
MEDIA_BOX = (0.0, 0.0, 396.0, 309.0)
X_LABEL = "Proporsi kucing"
Y_LABEL = "Proporsi anjing"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def default_source() -> Path:
    lane = Path(__file__).resolve().parents[5]
    return (
        lane
        / "authority"
        / "upstream"
        / f"openintro-statistics-{PINNED_COMMIT}"
        / "ch_intro_to_data"
        / "figures"
        / "eoce"
        / "seattle_pet_names"
        / "seattle_pet_names.pdf"
    )


def localize(source: Path, output: Path) -> None:
    source_bytes = source.read_bytes()
    if sha256_bytes(source_bytes) != PINNED_SHA256:
        raise ValueError("authority PDF hash does not match the pinned source")

    document = fitz.open(source)
    if document.is_repaired:
        raise ValueError("authority PDF unexpectedly required structural repair")
    if document.page_count != 1:
        raise ValueError("expected exactly one page")
    page = document[0]
    media_box = tuple(float(value) for value in page.mediabox)
    if media_box != MEDIA_BOX:
        raise ValueError(f"unexpected MediaBox: {media_box}")

    # MuPDF coordinates originate at the top left. These two masks correspond
    # exactly to PDF-space x=0..19 and y=0..20 used by the localized overlay.
    page.draw_rect(
        fitz.Rect(0, 289, 396, 309),
        color=None,
        fill=(1, 1, 1),
        width=0,
        overlay=True,
    )
    page.draw_rect(
        fitz.Rect(0, 0, 19, 309),
        color=None,
        fill=(1, 1, 1),
        width=0,
        overlay=True,
    )
    x_spare = page.insert_textbox(
        fitz.Rect(45.63, 289, 390.52, 309),
        X_LABEL,
        fontname="helv",
        fontsize=11,
        color=(0, 0, 0),
        align=fitz.TEXT_ALIGN_CENTER,
        overlay=True,
    )
    y_spare = page.insert_textbox(
        fitz.Rect(0, 33.05, 19, 304.12),
        Y_LABEL,
        fontname="helv",
        fontsize=11,
        color=(0, 0, 0),
        align=fitz.TEXT_ALIGN_CENTER,
        rotate=90,
        overlay=True,
    )
    if x_spare < 0 or y_spare < 0:
        raise ValueError(f"localized label does not fit: x={x_spare}, y={y_spare}")

    output.parent.mkdir(parents=True, exist_ok=True)
    document.save(
        output,
        garbage=2,
        clean=True,
        deflate=True,
        incremental=False,
        no_new_id=True,
        preserve_metadata=True,
        use_objstms=0,
        compression_effort=9,
    )
    document.close()

    check = fitz.open(output)
    if check.is_repaired:
        raise ValueError("localized PDF required structural repair")
    if check.page_count != 1:
        raise ValueError("localized PDF lost its page")
    if tuple(float(value) for value in check[0].mediabox) != MEDIA_BOX:
        raise ValueError("localized PDF changed its MediaBox")
    text = check[0].get_text("text")
    if X_LABEL not in text or Y_LABEL not in text:
        raise ValueError("localized labels are not extractable")
    check.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=default_source())
    parser.add_argument(
        "--output", type=Path, default=Path(__file__).with_name("seattle_pet_names.pdf")
    )
    args = parser.parse_args()
    localize(args.source.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
