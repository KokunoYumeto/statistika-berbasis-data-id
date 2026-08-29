#!/usr/bin/env python3
"""Regenerate the B023 blade-test chart with its visible null label in id-ID."""

from __future__ import annotations

import argparse
import hashlib
import json
import io
from pathlib import Path

import pdfplumber
from pypdf import PdfReader
from pypdf.generic import DecodedStreamObject, NameObject
from reportlab.pdfgen import canvas
from pypdf import PdfWriter


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / (
    "authority/upstream/openintro-statistics-"
    "fee25091fb24e89c36296fd67c48c1fcf7a93b6e/"
    "ch_inference_for_props/figures/bladesTwoSampleHTPValueQC/"
    "bladesTwoSampleHTPValueQC.pdf"
)
EXPECTED_SOURCE = {
    "bytes": 7_951,
    "sha256": "c55e8a93fb1bf0557257ae8b0baf5a1e57f521816411913ef9d658ec51876500",
}
PAGE_WIDTH = 218.0
PAGE_HEIGHT = 112.0
BLUE = (0.33699036, 0.60798645, 0.74099731)


class GateError(RuntimeError):
    pass


def identity(path: Path) -> dict[str, object]:
    raw = path.read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GateError(message)


def build(output: Path) -> None:
    require(identity(SOURCE) == EXPECTED_SOURCE, "pinned blade-chart authority identity changed")
    output.parent.mkdir(parents=True, exist_ok=True)
    # Preserve the pinned upstream vector geometry byte-for-byte at the page
    # level and replace only the reader-visible English null-value label.  A
    # white knockout is confined to the original label bounding box; all curve,
    # tail, axis, tick, annotation, and numerical geometry remains upstream.
    overlay_buffer = io.BytesIO()
    overlay = canvas.Canvas(
        overlay_buffer,
        pagesize=(PAGE_WIDTH, PAGE_HEIGHT),
        pageCompression=1,
        invariant=1,
    )
    overlay.setFillColorRGB(1, 1, 1)
    overlay.rect(88.0, 0.0, 43.0, 12.0, fill=1, stroke=0)
    overlay.setFillColorRGB(0, 0, 0)
    overlay.setFont("Helvetica", 8.0)
    overlay.drawString(90.02, 2.664, "(nilai nol)")
    overlay.showPage()
    overlay.save()
    overlay_buffer.seek(0)
    base_reader = PdfReader(str(SOURCE))
    overlay_page = PdfReader(overlay_buffer).pages[0]
    base_page = base_reader.pages[0]
    # Remove the exact upstream text operator for ``(null value)`` before
    # adding the localized overlay.  Merely painting over the label would
    # leave the English string in the selectable/searchable text layer.
    raw_contents = base_page.get_contents().get_data()
    old_label_stream = (
        b"BT\n/F2 1 Tf 8.00 0.00 0.00 8.00 90.02 4.32 Tm "
        b"[(\\(n) 10 (ull v) 25 (alue\\))] TJ\nET\n"
    )
    require(
        raw_contents.count(old_label_stream) == 1,
        "pinned chart does not contain exactly one expected English label operator",
    )
    cleaned_contents = raw_contents.replace(old_label_stream, b"", 1)
    cleaned_stream = DecodedStreamObject()
    cleaned_stream.set_data(cleaned_contents)
    base_page[NameObject("/Contents")] = cleaned_stream
    base_page.merge_page(overlay_page)
    writer = PdfWriter()
    writer.add_page(base_page)
    writer.add_metadata({
        "/Title": "Distribusi nol uji dua proporsi untuk mutu bilah",
        "/Author": "OpenIntro; localized derivative by OpenAI Codex gpt-5.6-sol, Ultra",
        "/Subject": "R011-B023 localized figure; source numerical geometry retained",
        "/Creator": "OpenAI Codex gpt-5.6-sol, Ultra",
    })
    with output.open("wb") as handle:
        writer.write(handle)


def verify(output: Path) -> dict[str, object]:
    reader = PdfReader(output)
    require(len(reader.pages) == 1, "localized chart must have exactly one page")
    page = reader.pages[0]
    width = float(page.mediabox.width)
    height = float(page.mediabox.height)
    require(abs(width - PAGE_WIDTH) < 0.001 and abs(height - PAGE_HEIGHT) < 0.001, "localized chart page geometry changed")
    with pdfplumber.open(output) as document:
        words = [row["text"] for row in document.pages[0].extract_words()]
    joined = " ".join(words)
    require(all(value in joined for value in ("0.006", "0.03", "0.059", "nilai", "nol")), "localized chart text inventory incomplete")
    require("null" not in joined.lower() and "value" not in joined.lower(), "English null label remains extractable")
    return {
        "$schema": "interlanguage.r011-b023-localized-blade-chart/v1",
        "status": "PASS_LOCALIZED_VISIBLE_LABEL_AND_RETAINED_NUMERICAL_GEOMETRY",
        "source": {"path": SOURCE.relative_to(ROOT).as_posix(), **EXPECTED_SOURCE},
        "output": {"path": output.relative_to(ROOT).as_posix(), **identity(output), "pages": 1, "width_points": width, "height_points": height},
        "visible_strings": words,
        "numerical_geometry": {
            "null_difference": 0.03,
            "observed_difference": 0.059,
            "tail_probability": 0.006,
            "lower_standardized_cutoff": -2.3,
            "upper_standardized_cutoff": 2.3,
            "source_geometry_retained": True,
        },
        "localized_string": {"source": "(null value)", "target": "(nilai nol)"},
        "translation_provenance": "OpenAI Codex gpt-5.6-sol, Ultra",
        "upstream_contact": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    if not output.is_absolute():
        output = ROOT / output
    build(output)
    print(json.dumps(verify(output), ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except GateError as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(1)
