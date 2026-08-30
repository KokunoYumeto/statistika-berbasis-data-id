#!/usr/bin/env python3
"""Localize the sole label-bearing R011-B025 chart without changing geometry."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, NameObject
from reportlab.pdfbase.pdfmetrics import stringWidth


ROOT = Path(__file__).resolve().parents[1]
AUTHORITY = ROOT / (
    "authority/upstream/openintro-statistics-"
    "fee25091fb24e89c36296fd67c48c1fcf7a93b6e"
)
FIGURE_DIR = AUTHORITY / "ch_inference_for_props/figures/iPodChiSqTail"
SOURCE = FIGURE_DIR / "iPodChiSqTail.pdf"
PRODUCER = FIGURE_DIR / "iPodChiSqTail.R"
TRANSLATION = ROOT / "qa/b025-translation/staging/section-lines-2239-2434.id.tex"
OUTPUT = ROOT / "qa/b025-translation/staging/assets/iPodChiSqTail.id.pdf"
RECEIPT = ROOT / "qa/b025-translation/R011-B025_IPOD_CHISQ_TAIL_LOCALIZATION_QA.json"

SOURCE_IDENTITY = {
    "bytes": 5_719,
    "sha256": "789e9da58ef275f9996f2414cb53ed5edb134b9df2f3f194e7be42d7ce810403",
}
PRODUCER_IDENTITY = {
    "bytes": 368,
    "sha256": "16c6c2d5167308537e38b4120ece9e841f6d41d532d9dab32e744329d319d543",
}
TRANSLATION_IDENTITY = {
    "bytes": 7_107,
    "sha256": "bc16102ee8a445f2410a9d429b9831a58f2637a528776ca727eb07607d045d63",
}
SOURCE_CONTENT_IDENTITY = {
    "bytes": 6_890,
    "sha256": "6825b3a3dd597f1c78bcb22b8d93e7ca4839eee609d5cfa6e1f549692d59fa2d",
}

SOURCE_LINE_1 = (
    b"207.49 54.80 Tm [(T) 120 (ail area \\(1 / 500 million\\))] TJ"
)
SOURCE_LINE_2 = b"224.77 40.40 Tm (is too small to see) Tj"
TARGET_TEXT_1 = "Luas ekor (1 dari 500 juta)"
TARGET_TEXT_2 = "terlalu kecil untuk terlihat"
TAIL_THRESHOLD_DEVICE_X = 272.79
FONT_SIZE = 12.0
TARGET_X_1 = TAIL_THRESHOLD_DEVICE_X - stringWidth(TARGET_TEXT_1, "Helvetica", FONT_SIZE) / 2
TARGET_X_2 = TAIL_THRESHOLD_DEVICE_X - stringWidth(TARGET_TEXT_2, "Helvetica", FONT_SIZE) / 2
TARGET_LINE_1 = (
    f"{TARGET_X_1:.2f} 54.80 Tm (Luas ekor \\(1 dari 500 juta\\)) Tj".encode("ascii")
)
TARGET_LINE_2 = (
    f"{TARGET_X_2:.2f} 40.40 Tm (terlalu kecil untuk terlihat) Tj".encode("ascii")
)

TITLE = "Luas ekor khi-kuadrat untuk contoh iPod"
CAPTION_ID = "Visualisasi nilai-p untuk X^2 = 40.13 ketika df = 2."
ALT_TEXT_ID = (
    "Kurva khi-kuadrat dengan df = 2; luas ekor di sebelah kanan "
    "X^2 = 40.13, sekitar 1 dari 500 juta, terlalu kecil untuk terlihat."
)
LICENSE = {
    "name": "Creative Commons Attribution-ShareAlike 3.0 Unported",
    "spdx": "CC-BY-SA-3.0",
    "url": "https://creativecommons.org/licenses/by-sa/3.0/",
    "derivative_notice": (
        "Visible annotation translated to Bahasa Indonesia; all plotted geometry, "
        "axes, ticks, values, and colors are retained from the pinned upstream figure."
    ),
}


class GateError(RuntimeError):
    """Raised when a fail-closed localization invariant is not met."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GateError(message)


def canonical(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def identity(path: Path) -> dict[str, object]:
    raw = path.read_bytes()
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def require_identity(path: Path, expected: dict[str, object], role: str) -> dict[str, object]:
    actual = identity(path)
    require(
        (actual["bytes"], actual["sha256"])
        == (expected["bytes"], expected["sha256"]),
        f"{role} identity changed",
    )
    return actual


def page_content(path: Path) -> bytes:
    reader = PdfReader(str(path))
    require(len(reader.pages) == 1, f"expected one-page PDF: {path}")
    contents = reader.pages[0].get_contents()
    require(contents is not None, f"missing PDF content stream: {path}")
    return contents.get_data()


def verify_authority() -> dict[str, object]:
    source = require_identity(SOURCE, SOURCE_IDENTITY, "pinned source PDF")
    producer = require_identity(PRODUCER, PRODUCER_IDENTITY, "pinned R producer")
    translation = require_identity(
        TRANSLATION, TRANSLATION_IDENTITY, "accepted B025 translation part B"
    )
    source_content = page_content(SOURCE)
    require(
        (len(source_content), hashlib.sha256(source_content).hexdigest())
        == (SOURCE_CONTENT_IDENTITY["bytes"], SOURCE_CONTENT_IDENTITY["sha256"]),
        "pinned source content stream changed",
    )
    require(source_content.count(SOURCE_LINE_1) == 1, "source annotation line 1 not unique")
    require(source_content.count(SOURCE_LINE_2) == 1, "source annotation line 2 not unique")

    producer_text = PRODUCER.read_text(encoding="utf-8")
    for fragment in (
        "x <- print(chisq.test(table(ask[2:3])))$statistic",
        "ChiSquareTail(x, 2,",
        'text(x, 0, "Tail area (1 / 500 million)\\nis too small to see", pos = 3)',
        "lines(c(x, 1000 * x), rep(0, 2), col = COL[1], lwd = 3)",
    ):
        require(fragment in producer_text, f"R producer invariant missing: {fragment}")

    translated_text = TRANSLATION.read_text(encoding="utf-8")
    for fragment in (
        "X^2 = 16.53 + 0.35 + \\dots + 4.66 = 40.13",
        "df = (2-1)\\times (3-1) = 2",
        "ch_inference_for_props/figures/iPodChiSqTail/iPodChiSqTail",
        "\\caption{Visualisasi nilai-p untuk $X^2 = 40.13$",
        "ketika $df = 2$.",
    ):
        require(fragment in translated_text, f"B025 figure context missing: {fragment}")
    return {
        "source_pdf": source,
        "r_producer": producer,
        "accepted_translation_context": translation,
        "source_content_stream": {
            "bytes": len(source_content),
            "sha256": hashlib.sha256(source_content).hexdigest(),
        },
    }


def localized_content() -> bytes:
    source_content = page_content(SOURCE)
    localized = source_content.replace(SOURCE_LINE_1, TARGET_LINE_1)
    localized = localized.replace(SOURCE_LINE_2, TARGET_LINE_2)
    require(localized != source_content, "annotation localization made no change")
    require(SOURCE_LINE_1 not in localized and SOURCE_LINE_2 not in localized, "English annotation remains")
    require(localized.count(TARGET_LINE_1) == 1, "localized annotation line 1 not unique")
    require(localized.count(TARGET_LINE_2) == 1, "localized annotation line 2 not unique")
    return localized


def normalized_geometry(content: bytes, localized: bool) -> bytes:
    if localized:
        blocks = (TARGET_LINE_1, TARGET_LINE_2)
    else:
        blocks = (SOURCE_LINE_1, SOURCE_LINE_2)
    normalized = content
    for index, block in enumerate(blocks, start=1):
        require(normalized.count(block) == 1, f"annotation block {index} is not unique")
        normalized = normalized.replace(block, f"<ANNOTATION_LINE_{index}>".encode("ascii"))
    return normalized


def write_pdf(path: Path, content: bytes) -> None:
    reader = PdfReader(str(SOURCE))
    writer = PdfWriter()
    writer.clone_document_from_reader(reader)
    stream = DecodedStreamObject()
    stream.set_data(content)
    writer.pages[0][NameObject("/Contents")] = writer._add_object(stream)
    writer.add_metadata(
        {
            "/Title": TITLE,
            "/Author": "OpenIntro; localized derivative by OpenAI Codex gpt-5.6-sol, Ultra",
            "/Subject": f"{CAPTION_ID} {ALT_TEXT_ID} License: CC BY-SA 3.0.",
            "/Creator": "R 3.3.3 (upstream); OpenAI Codex gpt-5.6-sol, Ultra (localization)",
            "/Producer": "pypdf 6.12.2 deterministic content-stream localizer",
            "/CreationDate": "D:20000101000000Z",
            "/ModDate": "D:20000101000000Z",
        }
    )
    with path.open("wb") as handle:
        writer.write(handle)


def inspect_output(path: Path) -> dict[str, object]:
    reader = PdfReader(str(path))
    require(not reader.is_encrypted, "localized PDF must not be encrypted")
    require(len(reader.pages) == 1, "localized PDF must contain one page")
    page = reader.pages[0]
    require([float(value) for value in page.mediabox] == [0.0, 0.0, 360.0, 162.0], "page box changed")
    font = page["/Resources"]["/Font"]["/F2"].get_object()
    require(str(font["/BaseFont"]) == "/Helvetica", "source Helvetica resource changed")
    content = page.get_contents().get_data()
    expected = localized_content()
    require(content == expected, "localized content stream differs from exact surgery")
    source_content = page_content(SOURCE)
    source_geometry = normalized_geometry(source_content, localized=False)
    target_geometry = normalized_geometry(content, localized=True)
    require(target_geometry == source_geometry, "non-annotation geometry changed")
    for fragment in (
        b"26.67 28.80 m 333.33 28.80 l S",
        b"26.67 28.80 m 26.67 24.48 l S",
        b"333.33 28.80 m 333.33 24.48 l S",
        b"272.79 33.20 m\n360.00 33.20 l\nS",
    ):
        require(content.count(fragment) == 1, f"axis/tail geometry invariant missing: {fragment!r}")
    text = page.extract_text() or ""
    compact = " ".join(text.split())
    require(TARGET_TEXT_1 in compact, "localized annotation line 1 not extractable")
    require(TARGET_TEXT_2 in compact, "localized annotation line 2 not extractable")
    for forbidden in ("Tail area", "million", "too small to see"):
        require(forbidden.casefold() not in compact.casefold(), f"visible English remains: {forbidden}")
    numeric_tokens = re.findall(r"\d+(?:\.\d+)?", compact)
    require(
        numeric_tokens == ["0", "10", "20", "30", "40", "50", "1", "500"],
        "visible numeric inventory changed",
    )
    metadata = reader.metadata or {}
    require(metadata.get("/Title") == TITLE, "localized title metadata changed")
    require("CC BY-SA 3.0" in str(metadata.get("/Subject", "")), "license metadata missing")
    return {
        **identity(path),
        "pages": 1,
        "media_box_points": [0, 0, 360, 162],
        "content_stream": {
            "bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        },
        "non_annotation_geometry": {
            "byte_identical_after_annotation_normalization": True,
            "bytes": len(target_geometry),
            "sha256": hashlib.sha256(target_geometry).hexdigest(),
        },
        "font": "Helvetica 12 pt",
        "visible_text": text.splitlines(),
        "visible_numeric_tokens": numeric_tokens,
    }


def payload(authority: dict[str, object], output: dict[str, object]) -> dict[str, object]:
    return {
        "$schema": "interlanguage.r011-b025-ipod-chisq-tail-localization/v1",
        "boundary_id": "R011-B025",
        "status": "PASS_EXACT_ANNOTATION_LOCALIZATION_AND_GEOMETRY_PRESERVATION",
        "authority": authority,
        "output": output,
        "translation": {
            "source_line_1": "Tail area (1 / 500 million)",
            "source_line_2": "is too small to see",
            "target_line_1": TARGET_TEXT_1,
            "target_line_2": TARGET_TEXT_2,
            "tail_threshold_device_x_points": TAIL_THRESHOLD_DEVICE_X,
            "line_1_baseline_points": [round(TARGET_X_1, 2), 54.8],
            "line_2_baseline_points": [round(TARGET_X_2, 2), 40.4],
            "horizontal_alignment": "both lines centered on the unchanged tail threshold",
        },
        "mathematical_closure": {
            "pearson_chi_square": 40.13,
            "degrees_of_freedom": 2,
            "tail_probability_rounded_description": "1 dari 500 juta",
            "tail_probability_precise_context": 0.000000002,
            "curve_tail_axes_ticks_numeric_values_and_colors_preserved": True,
        },
        "accessibility_evidence": {
            "caption_id": CAPTION_ID,
            "alt_text_id": ALT_TEXT_ID,
            "caption_context_verified_in_accepted_translation": True,
            "pdf_tagged": False,
            "note": "The upstream figure is untagged; localized caption and alt text are prepared for reader integration.",
        },
        "rights": LICENSE,
        "deterministic_two_replay": True,
        "visible_english_labels_remaining": 0,
        "translation_provenance": "OpenAI Codex gpt-5.6-sol, Ultra",
        "source_credit_preserved": "OpenIntro",
        "upstream_contact": False,
        "git_used": False,
        "credentials_accessed": False,
        "publication_performed": False,
    }


def build() -> dict[str, object]:
    authority = verify_authority()
    content = localized_content()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    replay_a = OUTPUT.with_name(OUTPUT.name + ".replay-a.tmp.pdf")
    replay_b = OUTPUT.with_name(OUTPUT.name + ".replay-b.tmp.pdf")
    for temporary in (replay_a, replay_b):
        require(not temporary.exists(), f"refusing stale replay temporary: {temporary}")
    write_pdf(replay_a, content)
    write_pdf(replay_b, content)
    require(replay_a.read_bytes() == replay_b.read_bytes(), "localized PDF replay bytes differ")
    os.replace(replay_a, OUTPUT)
    replay_b.unlink()
    result = payload(authority, inspect_output(OUTPUT))
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    temporary_receipt = RECEIPT.with_name(RECEIPT.name + ".tmp")
    require(not temporary_receipt.exists(), f"refusing stale receipt temporary: {temporary_receipt}")
    temporary_receipt.write_bytes(canonical(result))
    os.replace(temporary_receipt, RECEIPT)
    return {**result, "receipt": identity(RECEIPT)}


def verify() -> dict[str, object]:
    authority = verify_authority()
    output = inspect_output(OUTPUT)
    expected = payload(authority, output)
    require(RECEIPT.is_file(), "localization receipt missing")
    require(RECEIPT.read_bytes() == canonical(expected), "localization receipt changed")
    return {**expected, "status": "PASS_EXACT_LOCALIZED_FIGURE_REPLAY", "receipt": identity(RECEIPT)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--build", action="store_true")
    mode.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    result = build() if args.build else verify()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except GateError as exc:
        raise SystemExit(f"ERROR: {exc}")
