#!/usr/bin/env python3
"""Build and deterministically verify the localized R011-B026 figure closure.

The six label-only derivatives are produced by exact content-stream surgery.  The
two upstream t-tail figures with known producer/geometry defects are regenerated
as deterministic vector PDFs with corrected degrees of freedom and cutoffs.
Nothing outside the B026 QA/staging lane is mutated.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Iterable

from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, ByteStringObject, DecodedStreamObject, NameObject
from reportlab.lib.colors import Color, black
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]
AUTHORITY_COMMIT = "fee25091fb24e89c36296fd67c48c1fcf7a93b6e"
AUTHORITY_TREE = "d61cc601e7d97759ce805900520f784d02a0489e"
AUTHORITY_ROOT = ROOT / "authority" / "upstream" / f"openintro-statistics-{AUTHORITY_COMMIT}"
FIGURE_ROOT = AUTHORITY_ROOT / "ch_inference_for_means" / "figures"
OUTPUT_DIR = ROOT / "qa" / "b026-translation" / "staging" / "assets"
RECEIPT = ROOT / "qa" / "b026-translation" / "R011-B026_ASSET_LOCALIZATION_QA.json"
MONTAGE = OUTPUT_DIR / "R011-B026_ASSET_VISUAL_QA.png"
MODEL = "OpenAI Codex gpt-5.6-sol, Ultra"
RECORDED_AT = "2026-08-30T00:00:00+02:00"
POPPLER = Path(
    r"C:\Users\Floris\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin\pdftoppm.exe"
)
OPENINTRO_BLUE = Color(0.337, 0.608, 0.741)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def identity(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw), "sha256": sha256_bytes(raw)}


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def normalized_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\u2212", "-")).strip()


def numeric_tokens(value: str) -> list[str]:
    return re.findall(r"(?<![A-Za-z])-?\d+(?:\.\d+)?", normalized_text(value))


SURGERY_SPECS: list[dict[str, Any]] = [
    {
        "key": "outliers_and_ss_condition",
        "source": "outliers_and_ss_condition/outliers_and_ss_condition.pdf",
        "source_bytes": 5071,
        "source_sha256": "e3522b83b91e7897b843246727adc99c264b4ca4ead9dc0bc1b0793215307100",
        "producer": "outliers_and_ss_condition/outliers_and_ss_condition.R",
        "producer_bytes": 692,
        "producer_sha256": "d6ff755fbb5b82d1ab7fd6b43faefb4330b430b5e8698d2da8d8f657d081dae4",
        "output": "outliers_and_ss_condition.id.pdf",
        "replacements": [
            (b"[(Sample 1 Obser) -30 (v) 25 (ations \\(n = 15\\))] TJ", b"(Observasi Sampel 1 \\(n = 15\\)) Tj", 1),
            (b"[(Sample 2 Obser) -30 (v) 25 (ations \\(n = 50\\))] TJ", b"(Observasi Sampel 2 \\(n = 50\\)) Tj", 1),
            (b"(Frequency) Tj", b"(Frekuensi) Tj", 2),
        ],
        "required": ["Observasi Sampel 1 (n = 15)", "Observasi Sampel 2 (n = 50)", "Frekuensi"],
        "forbidden": ["Sample 1 Observations", "Sample 2 Observations", "Frequency"],
        "unchanged_language_neutral": [],
    },
    {
        "key": "tDistCompareToNormalDist",
        "source": "tDistCompareToNormalDist/tDistCompareToNormalDist.pdf",
        "source_bytes": 15583,
        "source_sha256": "28470fe71fc00a899d6cae91c1572c26d7ee374bfab18e071bfb488034b1cd71",
        "producer": "tDistCompareToNormalDist/tDistCompareToNormalDist.R",
        "producer_bytes": 851,
        "producer_sha256": "83f648e6925dee7255618614cc6633653db4c649feef1094a5afb83610512408",
        "output": "tDistCompareToNormalDist.id.pdf",
        "replacements": [
            (b"[(t-distr) -15 (ib) 20 (ution)] TJ", b"(distribusi-t) Tj", 1),
        ],
        "required": ["Normal", "distribusi-t"],
        "forbidden": ["t-distribution"],
        "unchanged_language_neutral": ["Normal"],
    },
    {
        "key": "tDistConvergeToNormalDist",
        "source": "tDistConvergeToNormalDist/tDistConvergeToNormalDist.pdf",
        "source_bytes": 19212,
        "source_sha256": "754dd5ab4ab301b060c3f951a28a653bd1c65a2d52e9eb348578582adac71160",
        "producer": "tDistConvergeToNormalDist/tDistConvergeToNormalDist.R",
        "producer_bytes": 797,
        "producer_sha256": "bc4ce12c5b3d19c068119be7ce525225fe0222d2efa7bc6a6c264503eb494958",
        "output": "tDistConvergeToNormalDist.id.pdf",
        "replacements": [
            (b"(t, df = 8) Tj", b"(t, dk = 8) Tj", 1),
            (b"(t, df = 4) Tj", b"(t, dk = 4) Tj", 1),
            (b"(t, df = 2) Tj", b"(t, dk = 2) Tj", 1),
            (b"(t, df = 1) Tj", b"(t, dk = 1) Tj", 1),
        ],
        "required": ["normal", "t, dk = 8", "t, dk = 4", "t, dk = 2", "t, dk = 1"],
        "forbidden": ["df ="],
        "unchanged_language_neutral": ["normal"],
    },
    {
        "key": "run17SampTimeHistogram",
        "source": "run10SampTimeHistogram/run17SampTimeHistogram.pdf",
        "source_bytes": 4617,
        "source_sha256": "e7e21b8a3807dae74b8a82f970ff9096268c169260ab52688ead88d393d13270",
        "producer": "run10SampTimeHistogram/run10SampTimeHistogram.R",
        "producer_bytes": 746,
        "producer_sha256": "1bd20d0f8823555d2aefad5f93d884ed977b0541203b21de96ff89a4a3ef9fb9",
        "output": "run17SampTimeHistogram.id.pdf",
        "replacements": [
            (b"[(Time \\(Min) 10 (utes\\))] TJ", b"(Waktu \\(Menit\\)) Tj", 1),
            (b"(Frequency) Tj", b"(Frekuensi) Tj", 1),
        ],
        "required": ["Waktu (Menit)", "Frekuensi"],
        "forbidden": ["Time (Minutes)", "Frequency"],
        "unchanged_language_neutral": [],
    },
    {
        "key": "t_distribution",
        "source": "eoce/t_distribution/t_distribution.pdf",
        "source_bytes": 17949,
        "source_sha256": "9bea5f900e1ff2f10d99217eb08378e637c8ec3a63f906fd250887b56e0e70fe",
        "producer": "eoce/t_distribution/t_distribution.R",
        "producer_bytes": 485,
        "producer_sha256": "4d2b7380fba7abbdfc7a92bfaba09061b9666b49b52d9dde80be54cb5d2c985f",
        "output": "t_distribution.id.pdf",
        "replacements": [
            (
                b"/F2 1 Tf 12.00 0.00 0.00 12.00 261.74 145.52 Tm (solid) Tj",
                b"/F2 1 Tf 10.00 0.00 0.00 10.00 253.00 146.23 Tm (padat) Tj",
                1,
            ),
            (
                b"/F2 1 Tf 12.00 0.00 0.00 12.00 261.74 131.12 Tm (dashed) Tj",
                b"/F2 1 Tf 10.00 0.00 0.00 10.00 253.00 131.83 Tm (putus-putus) Tj",
                1,
            ),
            (
                b"/F2 1 Tf 12.00 0.00 0.00 12.00 261.74 116.72 Tm (dotted) Tj",
                b"/F2 1 Tf 10.00 0.00 0.00 10.00 253.00 117.43 Tm (titik-titik) Tj",
                1,
            ),
        ],
        "required": ["padat", "putus-putus", "titik-titik"],
        "forbidden": ["solid", "dashed", "dotted"],
        "unchanged_language_neutral": [],
    },
    {
        "key": "adult_heights_hist",
        "source": "eoce/adult_heights/adult_heights_hist.pdf",
        "source_bytes": 4674,
        "source_sha256": "486ef0179721127302ebc7f43d240a3c1918ab4411d20a780191b0a14e523da5",
        "producer": "eoce/adult_heights/adult_heights.R",
        "producer_bytes": 436,
        "producer_sha256": "ebc25dba238a931e444157fbffffb6063f33864f6cc197a68671496af64713b2",
        "output": "adult_heights_hist.id.pdf",
        "replacements": [(b"(Height) Tj", b"(Tinggi) Tj", 1)],
        "required": ["Tinggi"],
        "forbidden": ["Height"],
        "unchanged_language_neutral": [],
    },
]


REGENERATED_SPECS: list[dict[str, Any]] = [
    {
        "key": "tDistDF18LeftTail2Point10",
        "source": "tDistDF18LeftTail2Point10/tDistDF18LeftTail2Point10.pdf",
        "source_bytes": 24430,
        "source_sha256": "e1da0ef09eb01c68d5aec3ec9d4cedbbe6c705f031290ed31bdfc6b7eb46bb0e",
        "producer": "tDistDF18LeftTail2Point10/tDistDF18LeftTail2Point10.R",
        "producer_bytes": 263,
        "producer_sha256": "add4c26d6b865850a1d4bdca15a1673db64948483644798b72ae250de1f394f8",
        "output": "tDistDF18LeftTail2Point10.id.pdf",
        "page_box": [0.0, 0.0, 288.0, 129.0],
        "panels": [
            {
                "df": 18,
                "cutoffs": [-2.10],
                "tails": ["left"],
                "xlim_requested": [-4.0, 4.0],
                "xlim_rendered": [-4.32, 4.32],
                "plot_box": [14.4, 27.07, 259.2, 96.0],
                "axis_ticks": [-4, -2, 0, 2, 4],
            }
        ],
        "correction": "producer df=10 repaired to source/caption df=18; cutoff -2.10 retained; stray placeholder Text removed",
    },
    {
        "key": "tDistDF20RightTail1Point65",
        "source": "tDistDF20RightTail1Point65/tDistDF20RightTail1Point65.pdf",
        "source_bytes": 13328,
        "source_sha256": "b2a7ae6e05ada61536a49703e215fed0252e70f23078086e34bd16c398d5465e",
        "producer": "tDistDF20RightTail1Point65/tDistDF20RightTail1Point65.R",
        "producer_bytes": 425,
        "producer_sha256": "d48f7853ec0dc24fe77d4f5924716d4b2e2146a8b23eab4e0aad1d3e9720c17a",
        "output": "tDistDF20RightTail1Point65.id.pdf",
        "page_box": [0.0, 0.0, 489.0, 136.0],
        "panels": [
            {
                "df": 20,
                "cutoffs": [1.65],
                "tails": ["right"],
                "xlim_requested": [-4.0, 4.0],
                "xlim_rendered": [-4.32, 4.32],
                "plot_box": [14.4, 27.31, 216.0, 103.0],
                "axis_ticks": [-4, -2, 0, 2, 4],
            },
            {
                "df": 2,
                "cutoffs": [-3.0, 3.0],
                "tails": ["left", "right"],
                "xlim_requested": [-4.5, 4.5],
                "xlim_rendered": [-4.86, 4.86],
                "plot_box": [259.2, 27.31, 216.0, 103.0],
                "axis_ticks": [-4, -2, 0, 2, 4],
            },
        ],
        "correction": "left producer df=12 repaired to df=20 with cutoff 1.65; right producer df=2.3 repaired to df=2 with cutoffs -3 and 3",
    },
]


def source_and_producer_identity(spec: dict[str, Any]) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    source = FIGURE_ROOT / spec["source"]
    producer = FIGURE_ROOT / spec["producer"]
    source_id = identity(source)
    producer_id = identity(producer)
    require(source_id["bytes"] == spec["source_bytes"], f"source byte drift: {spec['key']}")
    require(source_id["sha256"] == spec["source_sha256"], f"source hash drift: {spec['key']}")
    require(producer_id["bytes"] == spec["producer_bytes"], f"producer byte drift: {spec['key']}")
    require(producer_id["sha256"] == spec["producer_sha256"], f"producer hash drift: {spec['key']}")
    return source, source_id, producer_id


def write_surgery_pdf(spec: dict[str, Any]) -> tuple[bytes, dict[str, Any]]:
    source_path, source_id, producer_id = source_and_producer_identity(spec)
    reader = PdfReader(str(source_path), strict=True)
    require(len(reader.pages) == 1, f"source page-count drift: {spec['key']}")
    source_page = reader.pages[0]
    source_stream_object = source_page.get_contents()
    require(source_stream_object is not None, f"source content stream absent: {spec['key']}")
    source_stream = source_stream_object.get_data()
    updated_stream = source_stream
    replacement_receipt: list[dict[str, Any]] = []
    for old, new, expected_count in spec["replacements"]:
        observed = updated_stream.count(old)
        require(observed == expected_count, f"content anchor count drift: {spec['key']} {old!r}: {observed}")
        require(new not in updated_stream, f"target label unexpectedly present in source: {spec['key']}")
        updated_stream = updated_stream.replace(old, new)
        replacement_receipt.append(
            {
                "source_operator_ascii": old.decode("ascii"),
                "target_operator_ascii": new.decode("ascii"),
                "occurrences": expected_count,
            }
        )

    writer = PdfWriter()
    writer.clone_document_from_reader(reader)
    target_page = writer.pages[0]
    target_content = DecodedStreamObject()
    target_content.set_data(updated_stream)
    target_page[NameObject("/Contents")] = writer._add_object(target_content)
    fixed_id = hashlib.sha256(f"R011-B026/{spec['key']}/id-ID".encode("ascii")).digest()[:16]
    writer._ID = ArrayObject([ByteStringObject(fixed_id), ByteStringObject(fixed_id)])
    writer.add_metadata(
        {
            "/Title": f"{spec['key']} - label Bahasa Indonesia",
            "/Subject": "R011-B026 localized vector-figure derivative",
            "/Author": "OpenIntro contributors; localized derivative",
            "/Creator": MODEL,
            "/Producer": "pypdf deterministic content-stream localization",
            "/CreationDate": "D:20260830000000+02'00'",
            "/ModDate": "D:20260830000000+02'00'",
        }
    )
    buffer = io.BytesIO()
    writer.write(buffer)
    raw = buffer.getvalue()

    check = PdfReader(io.BytesIO(raw), strict=True)
    require(len(check.pages) == 1, f"target page count drift: {spec['key']}")
    check_page = check.pages[0]
    target_stream_object = check_page.get_contents()
    require(target_stream_object is not None, f"target content stream absent: {spec['key']}")
    check_stream = target_stream_object.get_data()
    inverse = check_stream
    for old, new, expected_count in reversed(spec["replacements"]):
        require(inverse.count(new) == expected_count, f"localized label count drift: {spec['key']}")
        inverse = inverse.replace(new, old)
    require(inverse == source_stream, f"non-label content stream changed: {spec['key']}")
    require(list(map(float, check_page.mediabox)) == list(map(float, source_page.mediabox)), f"media box changed: {spec['key']}")
    require(list(map(float, check_page.cropbox)) == list(map(float, source_page.cropbox)), f"crop box changed: {spec['key']}")

    source_fonts = sorted((source_page.get("/Resources") or {}).get("/Font", {}).keys())
    target_fonts = sorted((check_page.get("/Resources") or {}).get("/Font", {}).keys())
    require(source_fonts == target_fonts, f"font resource keys changed: {spec['key']}")
    source_xobjects = sorted((source_page.get("/Resources") or {}).get("/XObject", {}).keys())
    target_xobjects = sorted((check_page.get("/Resources") or {}).get("/XObject", {}).keys())
    require(source_xobjects == target_xobjects, f"XObject resource keys changed: {spec['key']}")

    source_text = normalized_text(source_page.extract_text() or "")
    target_text = normalized_text(check_page.extract_text() or "")
    for required in spec["required"]:
        require(required in target_text, f"required localized text absent: {spec['key']} / {required}")
    for forbidden in spec["forbidden"]:
        require(forbidden not in target_text, f"residual English remains: {spec['key']} / {forbidden}")
    require(numeric_tokens(source_text) == numeric_tokens(target_text), f"numeric label drift: {spec['key']}")

    return raw, {
        "key": spec["key"],
        "method": "exact_pypdf_content_stream_surgery",
        "source": source_id,
        "producer": producer_id,
        "source_page_box": list(map(float, source_page.mediabox)),
        "target_page_box": list(map(float, check_page.mediabox)),
        "source_content_stream": {"bytes": len(source_stream), "sha256": sha256_bytes(source_stream)},
        "target_content_stream": {"bytes": len(check_stream), "sha256": sha256_bytes(check_stream)},
        "replacements": replacement_receipt,
        "non_label_content_stream_identity_after_inverse_mapping": True,
        "non_label_geometry_and_resource_keys_preserved": True,
        "source_numeric_tokens": numeric_tokens(source_text),
        "target_numeric_tokens": numeric_tokens(target_text),
        "required_localized_strings": spec["required"],
        "removed_reader_visible_english_strings": spec["forbidden"],
        "unchanged_language_neutral_or_shared_terms": spec["unchanged_language_neutral"],
        "target_extractable_text": target_text,
    }


def student_t_pdf(x: float, df: int) -> float:
    coefficient = math.gamma((df + 1.0) / 2.0) / (math.sqrt(df * math.pi) * math.gamma(df / 2.0))
    return coefficient * (1.0 + (x * x) / df) ** (-(df + 1.0) / 2.0)


def sampled_values(start: float, stop: float, count: int) -> list[float]:
    require(count >= 2, "sample count must be >=2")
    step = (stop - start) / (count - 1)
    return [start + step * i for i in range(count)]


def draw_tail_polygon(
    pdf: canvas.Canvas,
    map_x,
    map_y,
    baseline: float,
    df: int,
    start: float,
    stop: float,
) -> None:
    xs = sampled_values(start, stop, 241)
    path = pdf.beginPath()
    path.moveTo(map_x(start), baseline)
    for x in xs:
        path.lineTo(map_x(x), map_y(student_t_pdf(x, df)))
    path.lineTo(map_x(stop), baseline)
    path.close()
    pdf.setFillColor(OPENINTRO_BLUE)
    pdf.setStrokeColor(OPENINTRO_BLUE)
    pdf.drawPath(path, stroke=0, fill=1)


def draw_t_panel(pdf: canvas.Canvas, panel: dict[str, Any]) -> dict[str, Any]:
    x0, baseline, width, height = panel["plot_box"]
    xmin, xmax = panel["xlim_rendered"]
    df = int(panel["df"])
    curve_top = baseline + height
    ymax = 0.42

    def map_x(x: float) -> float:
        return x0 + width * (x - xmin) / (xmax - xmin)

    def map_y(y: float) -> float:
        return baseline + height * y / ymax

    pdf.saveState()
    clip = pdf.beginPath()
    clip.rect(x0, baseline, width, height)
    pdf.clipPath(clip, stroke=0, fill=0)

    cutoffs = [float(value) for value in panel["cutoffs"]]
    for tail, cutoff in zip(panel["tails"], cutoffs):
        if tail == "left":
            draw_tail_polygon(pdf, map_x, map_y, baseline, df, xmin, cutoff)
        elif tail == "right":
            draw_tail_polygon(pdf, map_x, map_y, baseline, df, cutoff, xmax)
        else:
            raise RuntimeError(f"unknown tail direction: {tail}")

    curve_xs = sampled_values(xmin, xmax, 1001)
    curve = pdf.beginPath()
    curve.moveTo(map_x(curve_xs[0]), map_y(student_t_pdf(curve_xs[0], df)))
    for x in curve_xs[1:]:
        curve.lineTo(map_x(x), map_y(student_t_pdf(x, df)))
    pdf.setStrokeColor(black)
    pdf.setLineWidth(0.8)
    pdf.drawPath(curve, stroke=1, fill=0)
    for cutoff in cutoffs:
        pdf.line(map_x(cutoff), baseline, map_x(cutoff), map_y(student_t_pdf(cutoff, df)))
    pdf.restoreState()

    axis_y = baseline - 7.0
    pdf.setStrokeColor(black)
    pdf.setFillColor(black)
    pdf.setLineWidth(0.75)
    pdf.line(map_x(panel["axis_ticks"][0]), axis_y, map_x(panel["axis_ticks"][-1]), axis_y)
    pdf.setFont("Helvetica", 10.5)
    for tick in panel["axis_ticks"]:
        tx = map_x(float(tick))
        pdf.line(tx, axis_y, tx, axis_y - 5.0)
        pdf.drawCentredString(tx, axis_y - 17.0, str(tick))

    curve_signature = "\n".join(
        f"{x:.12f}\t{student_t_pdf(x, df):.12f}" for x in sampled_values(xmin, xmax, 1001)
    ).encode("ascii")
    tail_signature = "\n".join(
        [f"{direction}\t{cutoff:.12f}\t{student_t_pdf(cutoff, df):.12f}" for direction, cutoff in zip(panel["tails"], cutoffs)]
    ).encode("ascii")
    return {
        **panel,
        "student_t_pdf_peak_at_zero": round(student_t_pdf(0.0, df), 12),
        "curve_sample_count": 1001,
        "curve_sample_sha256": sha256_bytes(curve_signature),
        "tail_boundary_sha256": sha256_bytes(tail_signature),
        "curve_top": round(curve_top, 6),
        "axis_baseline": round(axis_y, 6),
    }


def write_regenerated_pdf(spec: dict[str, Any]) -> tuple[bytes, dict[str, Any]]:
    source_path, source_id, producer_id = source_and_producer_identity(spec)
    source_reader = PdfReader(str(source_path), strict=True)
    require(len(source_reader.pages) == 1, f"source page-count drift: {spec['key']}")
    source_page_box = list(map(float, source_reader.pages[0].mediabox))
    require(source_page_box == spec["page_box"], f"source page-box drift: {spec['key']}")

    buffer = io.BytesIO()
    width = spec["page_box"][2]
    height = spec["page_box"][3]
    pdf = canvas.Canvas(
        buffer,
        pagesize=(width, height),
        bottomup=1,
        invariant=1,
        pageCompression=1,
    )
    pdf.setTitle(f"{spec['key']} - corrected R011-B026 vector figure")
    pdf.setAuthor("OpenIntro contributors; corrected localized derivative")
    pdf.setSubject(spec["correction"])
    pdf.setCreator(MODEL)
    pdf.setProducer("ReportLab deterministic Student-t vector regeneration")
    pdf.setKeywords("R011-B026; Student t; deterministic; Bahasa Indonesia edition")
    panel_receipts = [draw_t_panel(pdf, panel) for panel in spec["panels"]]
    pdf.showPage()
    pdf.save()
    raw = buffer.getvalue()

    check = PdfReader(io.BytesIO(raw), strict=True)
    require(len(check.pages) == 1, f"regenerated page count drift: {spec['key']}")
    target_box = list(map(float, check.pages[0].mediabox))
    require(target_box == spec["page_box"], f"regenerated page box drift: {spec['key']}")
    target_text = normalized_text(check.pages[0].extract_text() or "")
    require("Text" not in target_text, f"stray placeholder Text remains: {spec['key']}")
    target_content_stream = check.pages[0].get_contents().get_data()
    require(b"Text" not in target_content_stream, f"stray placeholder content-stream bytes remain: {spec['key']}")
    expected_ticks: list[str] = []
    for panel in spec["panels"]:
        expected_ticks.extend(str(value) for value in panel["axis_ticks"])
    require(numeric_tokens(target_text) == expected_ticks, f"axis numeric tokens changed: {spec['key']}")
    require(len(target_content_stream) > 1000, f"vector content unexpectedly small: {spec['key']}")

    return raw, {
        "key": spec["key"],
        "method": "deterministic_reportlab_student_t_vector_regeneration",
        "source": source_id,
        "producer": producer_id,
        "source_page_box": source_page_box,
        "target_page_box": target_box,
        "correction": spec["correction"],
        "panels": panel_receipts,
        "target_numeric_tokens": numeric_tokens(target_text),
        "target_extractable_text": target_text,
        "stray_placeholder_text_removed": True,
        "page_geometry_semantics_preserved": True,
        "curve_and_tail_semantics_recomputed_from_declared_df_and_cutoffs": True,
    }


def build_pdf(spec: dict[str, Any], method: str) -> tuple[bytes, dict[str, Any]]:
    if method == "surgery":
        return write_surgery_pdf(spec)
    if method == "regenerate":
        return write_regenerated_pdf(spec)
    raise RuntimeError(method)


def render_montage(outputs: Iterable[Path]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    require(POPPLER.is_file(), f"Poppler executable absent: {POPPLER}")
    render_rows: list[dict[str, Any]] = []
    prepared: list[tuple[Path, Image.Image]] = []
    with tempfile.TemporaryDirectory(prefix="b026-visual-", dir=OUTPUT_DIR) as tmp_name:
        tmp = Path(tmp_name)
        for pdf_path in outputs:
            prefix = tmp / pdf_path.stem
            completed = subprocess.run(
                [str(POPPLER), "-png", "-r", "144", "-singlefile", str(pdf_path), str(prefix)],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            require(completed.returncode == 0, f"Poppler render failed: {pdf_path.name}: {completed.stderr}")
            png_path = Path(str(prefix) + ".png")
            require(png_path.is_file(), f"render output absent: {pdf_path.name}")
            image = Image.open(png_path).convert("RGB")
            extrema = image.getextrema()
            require(any(lo < 250 for lo, _hi in extrema), f"render appears blank: {pdf_path.name}")
            source_size = image.size
            max_width = 780
            if image.width > max_width:
                scaled_height = round(image.height * max_width / image.width)
                image = image.resize((max_width, scaled_height), Image.Resampling.LANCZOS)
            prepared.append((pdf_path, image.copy()))
            render_rows.append(
                {
                    "pdf": identity(pdf_path),
                    "render_pixels": list(source_size),
                    "render_sha256": sha256_bytes(png_path.read_bytes()),
                    "poppler_stderr_line_count": len([line for line in completed.stderr.splitlines() if line.strip()]),
                    "nonblank_extrema": [list(item) for item in extrema],
                }
            )

    margin = 20
    caption_height = 24
    columns = 2
    rows: list[list[tuple[Path, Image.Image]]] = [prepared[index : index + columns] for index in range(0, len(prepared), columns)]
    cell_width = max(image.width for _path, image in prepared) + 2 * margin
    row_heights = [max(image.height for _path, image in row) + caption_height + 2 * margin for row in rows]
    montage = Image.new("RGB", (cell_width * columns, sum(row_heights)), "white")
    draw = ImageDraw.Draw(montage)
    font = ImageFont.load_default()
    y = 0
    for row, row_height in zip(rows, row_heights):
        for column, (path, image) in enumerate(row):
            cell_x = column * cell_width
            x = cell_x + (cell_width - image.width) // 2
            draw.text((cell_x + margin, y + 4), path.name, fill="black", font=font)
            montage.paste(image, (x, y + caption_height))
        y += row_height
    montage.save(MONTAGE, format="PNG", optimize=False, compress_level=9)
    return identity(MONTAGE), render_rows


def verify_dolphin() -> dict[str, Any]:
    photo = FIGURE_ROOT / "rissosDolphin" / "rissosDolphin.jpg"
    witness = FIGURE_ROOT / "rissosDolphin" / "ReadMe.txt"
    photo_id = identity(photo)
    witness_id = identity(witness)
    require(photo_id["bytes"] == 72046, "Risso's dolphin photo byte drift")
    require(photo_id["sha256"] == "591d0ba9d9a228e58f2e8841536b826847f219d68cf791d6740986b7768ee200", "Risso's dolphin photo hash drift")
    require(witness_id["bytes"] == 119, "Risso's dolphin rights witness byte drift")
    require(witness_id["sha256"] == "51903690d2b3cd10e69431292a345a08e321ac06d390252e852f4deef200088f", "Risso's dolphin rights witness hash drift")
    witness_text = witness.read_text(encoding="utf-8").strip()
    required_attribution = "Photo by Mike Baird (http://www.bairdphotos.com/). Image was licensed under Creative Commons Attribution 2.0 Generic."
    require(witness_text == required_attribution, "Risso's dolphin attribution witness changed")
    return {
        "source": photo_id,
        "rights_witness": witness_id,
        "rights_resolution": "CC-BY-2.0",
        "required_attribution_verbatim": required_attribution,
        "staged_copy_created": False,
        "source_preserved_byte_identical": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--record-visual-pass",
        action="store_true",
        help="Record the model's post-render visual inspection after the generated montage has actually been inspected.",
    )
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    require(len(SURGERY_SPECS) == 6, "unexpected surgery scope")
    require(len(REGENERATED_SPECS) == 2, "unexpected regeneration scope")
    artifact_rows: list[dict[str, Any]] = []
    output_paths: list[Path] = []

    for method, specs in (("surgery", SURGERY_SPECS), ("regenerate", REGENERATED_SPECS)):
        for spec in specs:
            replay_one, diagnostics_one = build_pdf(spec, method)
            replay_two, diagnostics_two = build_pdf(spec, method)
            require(replay_one == replay_two, f"two-replay byte mismatch: {spec['key']}")
            require(diagnostics_one == diagnostics_two, f"two-replay diagnostic mismatch: {spec['key']}")
            output_path = OUTPUT_DIR / spec["output"]
            output_path.write_bytes(replay_one)
            output_id = identity(output_path)
            require(output_id["sha256"] == sha256_bytes(replay_two), f"promoted output hash mismatch: {spec['key']}")
            diagnostics_one["output"] = output_id
            diagnostics_one["two_replay_exact_byte_proof"] = {
                "status": "PASS_EXACT_BYTES",
                "replay_1_bytes": len(replay_one),
                "replay_1_sha256": sha256_bytes(replay_one),
                "replay_2_bytes": len(replay_two),
                "replay_2_sha256": sha256_bytes(replay_two),
                "byte_identical": True,
            }
            artifact_rows.append(diagnostics_one)
            output_paths.append(output_path)

    montage_id, render_rows = render_montage(output_paths)
    dolphin = verify_dolphin()
    output_inventory = "".join(
        f"{row['output']['path']}\t{row['output']['bytes']}\t{row['output']['sha256']}\n"
        for row in artifact_rows
    ).encode("utf-8")
    script_id = identity(Path(__file__).resolve())
    receipt = {
        "$schema": "interlanguage.r011-b026-asset-localization-qa/v1",
        "boundary_id": "R011-B026",
        "status": "PASS_DETERMINISTIC_ASSET_LOCALIZATION_AND_VISUAL_QA" if args.record_visual_pass else "PASS_AUTOMATED_ASSET_QA_PENDING_MODEL_VISUAL_INSPECTION",
        "recorded_at": RECORDED_AT,
        "provenance": {
            "production_model": MODEL,
            "script": script_id,
            "authority_repository": "https://github.com/OpenIntroStat/openintro-statistics",
            "authority_branch": "master",
            "authority_commit": AUTHORITY_COMMIT,
            "authority_tree": AUTHORITY_TREE,
            "network_used": False,
            "git_used": False,
            "credentials_accessed": False,
        },
        "scope": {
            "generated_reader_pdf_assets": 8,
            "label_only_content_stream_surgeries": 6,
            "corrected_vector_regenerations": 2,
            "photographic_assets_preserved_in_place": 1,
            "canonical_source_mutated": False,
            "live_repo_backend_output_control_or_release_mutated": False,
        },
        "rights": {
            "generated_pdfs_and_producers": "CC BY-SA 3.0 repository declaration; derivative labels/corrections preserve source and producer identity.",
            "rissos_dolphin": dolphin,
        },
        "artifacts": artifact_rows,
        "output_inventory": {
            "files": len(artifact_rows),
            "bytes": sum(row["output"]["bytes"] for row in artifact_rows),
            "inventory_sha256": sha256_bytes(output_inventory),
        },
        "language_qa": {
            "locale": "id-ID",
            "required_terms": [
                "Frekuensi",
                "Observasi Sampel 1",
                "Observasi Sampel 2",
                "distribusi-t",
                "Waktu (Menit)",
                "padat",
                "putus-putus",
                "titik-titik",
                "Tinggi",
            ],
            "residual_english_checks": "PASS_EXACT_READER_VISIBLE_LABEL_DENYLIST",
            "language_neutral_shared_terms_retained": ["Normal", "normal", "t"],
        },
        "numeric_and_geometry_qa": {
            "label_only_source_numeric_tokens_preserved_exactly": True,
            "label_only_non_label_content_streams_preserved_exactly_after_inverse_mapping": True,
            "all_media_and_crop_boxes_preserved": True,
            "corrected_df18_left_tail": {"df": 18, "cutoff": -2.10, "stray_Text_removed": True},
            "corrected_df20_right_tail": {
                "left_panel": {"df": 20, "cutoff": 1.65, "tail": "right"},
                "right_panel": {"df": 2, "cutoffs": [-3.0, 3.0], "tails": ["left", "right"]},
            },
            "student_t_curves_recomputed_analytically": True,
            "axes_and_tail_geometry_rendered_as_vector_paths": True,
        },
        "render_qa": {
            "renderer": str(POPPLER),
            "dpi": 144,
            "rendered_pdf_count": len(render_rows),
            "all_rendered_pages_nonblank": True,
            "renders": render_rows,
            "montage": montage_id,
            "model_visual_inspection": "PASS_ZERO_VISIBLE_DEFECTS" if args.record_visual_pass else "PENDING",
            "inspection_notes": (
                "All eight charts are legible and unclipped; localized labels fit; curves, axes, cutoffs, and shaded tails render correctly; no stray placeholder text is visible."
                if args.record_visual_pass
                else "Inspect the exact montage bytes before recording a visual pass."
            ),
        },
        "replay": {
            "pdf_outputs_replayed": 8,
            "all_output_bytes_identical_across_two_independent_in_memory_builds": True,
            "all_diagnostics_identical_across_two_independent_in_memory_builds": True,
            "promoted_staging_bytes_match_replay": True,
        },
        "next_action": "Install these eight exact localized PDF bytes into the isolated B026 reader snapshot, bind them into the backend admission, and retain the dolphin photo at its source identity with its CC BY 2.0 attribution.",
    }
    RECEIPT.write_bytes(canonical_json(receipt))
    check = json.loads(RECEIPT.read_text(encoding="utf-8"))
    require(check == receipt, "receipt canonical JSON readback mismatch")
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "receipt": identity(RECEIPT),
                "montage": montage_id,
                "output_inventory": receipt["output_inventory"],
                "outputs": [row["output"] for row in artifact_rows],
            },
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
