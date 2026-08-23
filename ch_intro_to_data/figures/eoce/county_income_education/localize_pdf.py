"""Deterministically localize text operands in the pinned county PDF."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, NameObject


PINNED_SHA256 = "7a640bebd64d0c716b6eba0bce8a7b4db5ad528229f90a9abf0c7214dac0b435"
PINNED_COMMIT = "fee25091fb24e89c36296fd67c48c1fcf7a93b6e"
PINNED_TREE = "d61cc601e7d97759ce805900520f784d02a0489e"
MEDIA_BOX = (0.0, 0.0, 360.0, 288.0)
REPLACEMENTS = (
    (
        b"[(P) 50 (ercent with Bachelor's Degree)] TJ",
        b"[-706.5 (P) 50 (ersentase bergelar sarjana)] TJ",
    ),
    (
        b"[(P) 50 (er Capita Income)] TJ",
        b"[890.5 (P) 50 (endapatan per kapita)] TJ",
    ),
)


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
        / "county_income_education"
        / "county_income_education_scatterplot.pdf"
    )


def localize(source: Path, output: Path) -> None:
    source_bytes = source.read_bytes()
    if sha256_bytes(source_bytes) != PINNED_SHA256:
        raise ValueError("authority PDF hash does not match the pinned source")

    reader = PdfReader(source, strict=True)
    if len(reader.pages) != 1:
        raise ValueError("expected exactly one page")
    page = reader.pages[0]
    media_box = tuple(float(value) for value in page.mediabox)
    if media_box != MEDIA_BOX:
        raise ValueError(f"unexpected MediaBox: {media_box}")
    authority_content = page.get_contents().get_data()
    localized_content = authority_content
    for old, new in REPLACEMENTS:
        if localized_content.count(old) != 1:
            raise ValueError(f"expected one authority text operand: {old!r}")
        localized_content = localized_content.replace(old, new, 1)

    restored = localized_content
    for old, new in REPLACEMENTS:
        if restored.count(new) != 1:
            raise ValueError(f"expected one localized text operand: {new!r}")
        restored = restored.replace(new, old, 1)
    if restored != authority_content:
        raise ValueError("a non-label content byte changed")

    writer = PdfWriter()
    writer.clone_document_from_reader(reader)
    writer.pdf_header = reader.pdf_header
    localized = DecodedStreamObject()
    localized.set_data(localized_content)
    localized_ref = writer._add_object(localized.flate_encode())
    writer.pages[0][NameObject("/Contents")] = localized_ref
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as stream:
        writer.write(stream)

    check = PdfReader(output, strict=True)
    if check.pages[0].get_contents().get_data() != localized_content:
        raise ValueError("localized content stream failed round-trip verification")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=default_source())
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).with_name("county_income_education_scatterplot.pdf"),
    )
    args = parser.parse_args()
    localize(args.source.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
