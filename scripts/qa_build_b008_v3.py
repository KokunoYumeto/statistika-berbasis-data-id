#!/usr/bin/env python3
"""Build the R011-B008 V3 page-fill repair as an isolated candidate.

The exact rejected V2 closure is advanced only by the one postimage sealed in
``R011-B008_V2_LAYOUT_REPAIR_RECEIPT.json``.  An independent V3 source manifest
and QA must match that derivation before the established four-pass whole-book
build runs.  Passes 3 and 4 must be byte-identical.

V1/V2 evidence is immutable.  V3 writes only V3-specific paths below
``qa/b008-build`` and never promotes, admits, publishes, contacts upstream, or
mutates live source, backend, output, release, control, or Git state.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import qa_build_b006 as base
import qa_build_b008_v2 as v2
from pypdf import PdfReader


LANE = Path(__file__).resolve().parents[1]
QA = LANE / "qa"
REPO = LANE / "repo"

V2_SOURCE_MANIFEST = QA / "b008-source" / "R011-B008_SOURCE_MANIFEST_V2.tsv"
V2_SOURCE_QA = QA / "b008-source" / "R011-B008_SOURCE_QA_V2.json"
V2_LAYOUT_REPAIR_RECEIPT = (
    QA / "b008-source" / "R011-B008_V2_LAYOUT_REPAIR_RECEIPT.json"
)
V2_CANDIDATE_PDF = QA / "b008-build" / "final-v2" / "main.pdf"
V2_BUILD_RECEIPT = (
    QA / "b008-build" / "final-v2" / "CANDIDATE_BUILD_QA_V2.json"
)
V2_AGENT_VISUAL = QA / "b008-build" / "BUILD_ONLY_VISUAL_SANITY_V2.json"
V2_ROOT_VISUAL = QA / "b008-visual" / "ROOT_VISUAL_FINDINGS_V2.json"

V3_SOURCE_MANIFEST = QA / "b008-source" / "R011-B008_SOURCE_MANIFEST_V3.tsv"
V3_SOURCE_QA = QA / "b008-source" / "R011-B008_SOURCE_QA_V3.json"

BUILD_ROOT = QA / "b008-build"
DERIVED_MANIFEST = BUILD_ROOT / "R011-B008_SNAPSHOT_MANIFEST_V3.tsv"
SNAPSHOT = BUILD_ROOT / "source-snapshot-v3"
FINAL = BUILD_ROOT / "final-v3"
PDF = FINAL / "main.pdf"
PASS3_PDF = FINAL / "main-pass3.pdf"
TEXT = FINAL / "main-final.txt"
LOG = FINAL / "main.log"
FLS = FINAL / "main.fls"
CANDIDATE_RECEIPT = FINAL / "CANDIDATE_BUILD_QA_V3.json"

RENDER = BUILD_ROOT / "render-final-v3"
RENDER_MANIFEST = RENDER / "FINAL_MANIFEST.tsv"
PAGE_LOCATOR = RENDER / "PAGE_LOCATOR.json"
CONTACT_SHEET = RENDER / "CONTACT_SHEET.png"

BOUNDARY_ID = "R011-B008"
AUTHORITY_REPOSITORY = "https://github.com/OpenIntroStat/openintro-statistics"
AUTHORITY_COMMIT = "fee25091fb24e89c36296fd67c48c1fcf7a93b6e"
AUTHORITY_TREE = "d61cc601e7d97759ce805900520f784d02a0489e"

EXPECTED_V2: dict[Path, tuple[int, str]] = {
    V2_SOURCE_MANIFEST: (
        175582,
        "67aa27af504aa442cf4f80be20ba2c2c7c37530049125c40b00f627f9f8c7dc1",
    ),
    V2_SOURCE_QA: (
        6411,
        "8d7ff2dc438d27474ce6395bd354d6139bf983a4c360131a109165df421116d5",
    ),
    V2_LAYOUT_REPAIR_RECEIPT: (
        2506,
        "c3c57c19067667e99f8db485274b3834ae56ce66930384f7a4430bfe86286a8f",
    ),
    V2_CANDIDATE_PDF: (
        22017323,
        "8e6d91a813206f7672fbed1736bed97f7eb48e3adc56f690fb696b7daa0ea9ef",
    ),
    V2_BUILD_RECEIPT: (
        17149,
        "f79462b733817eb13b70616a5f8f347a599e959c4c532a0eca0aa9ca5f0d7a5b",
    ),
    V2_AGENT_VISUAL: (
        2257,
        "d395b51cb587048fdea11489e10c37095b2fedeb681757c850e78d58888bb092",
    ),
    V2_ROOT_VISUAL: (
        2231,
        "0975aeade7f4563cb32eec8865f9b08e3e7f6598bc92e15b20541ccf328971da",
    ),
}

EXPECTED_V3: dict[Path, tuple[int, str]] = {
    V3_SOURCE_MANIFEST: (
        175582,
        "743b4906fad27bad1adfcb331566517314a93602d6df3c3cc279aa56a88745f4",
    ),
    V3_SOURCE_QA: (
        6896,
        "8fd911d8ac4164a51c44d52ce62a3277ac4f63aa2aaca4437f244550f7223a8a",
    ),
}


def identity(path: Path) -> dict[str, object]:
    return v2.identity(path)


def require_identity(path: Path, expected: tuple[int, str], label: str) -> None:
    v2.require_identity(path, expected, label)


def parse_manifest(path: Path) -> dict[str, tuple[int, str]]:
    return v2.parse_manifest(path)


def manifest_bytes(rows: dict[str, tuple[int, str]]) -> bytes:
    return v2.manifest_bytes(rows)


def rejected_v2_and_repair() -> tuple[dict[str, tuple[int, str]], dict[str, Any]]:
    for path, expected in EXPECTED_V2.items():
        require_identity(path, expected, path.name)
    rows = parse_manifest(V2_SOURCE_MANIFEST)
    if len(rows) != 1206:
        raise RuntimeError(f"rejected V2 closure count differs: {len(rows)}")
    repair = json.loads(V2_LAYOUT_REPAIR_RECEIPT.read_text(encoding="utf-8"))
    if (
        repair.get("$schema") != "r011-b008-v2-layout-repair-receipt/v1"
        or repair.get("boundary_id") != BOUNDARY_ID
        or repair.get("status") != "APPLIED_BOUNDED_PAGE_FILL_REPAIR"
        or repair.get("scope", {}).get("files_changed") != 1
        or repair.get("scope", {}).get("reader_visible_translation_changed") is not False
        or repair.get("scope", {}).get("answers_changed") is not False
        or repair.get("scope", {}).get("canonical_pdf_or_backend_promoted") is not False
    ):
        raise RuntimeError("V2 layout-repair receipt is not the exact bounded PASS")

    rejected = repair.get("rejected_candidate", {})
    expected_rejected = {"path": base.rel(V2_CANDIDATE_PDF), **identity(V2_CANDIDATE_PDF)}
    for key in ("path", "bytes", "sha256"):
        if rejected.get(key) != expected_rejected[key]:
            raise RuntimeError("layout receipt does not bind the rejected V2 PDF")
    bindings = {
        "build_receipt": V2_BUILD_RECEIPT,
        "build_visual_findings": V2_AGENT_VISUAL,
        "root_visual_findings": V2_ROOT_VISUAL,
    }
    for key, path in bindings.items():
        if rejected.get(key) != {"path": base.rel(path), **identity(path)}:
            raise RuntimeError(f"layout receipt does not bind V2 {key}")
    if not str(rejected.get("blocking_finding", "")).startswith(
        "Page 80 remained top-heavy"
    ):
        raise RuntimeError("layout receipt does not bind the page-fill rejection")

    item = repair.get("repair", {})
    if (
        item.get("id") != "R011-B008-REPAIR-003"
        or item.get("target")
        != "repo/ch_summarizing_data/TeX/review_exercises.tex"
        or item.get("kind") != "page_fill_and_vertical_centering_only"
        or item.get(
            "instructional_content_order_mathematics_labels_alt_text_and_asset_paths_unchanged"
        )
        is not True
        or item.get("asset_bytes_changed") is not False
    ):
        raise RuntimeError("V3 repair semantics differ from the sealed one-file repair")
    relative = str(item["target"]).removeprefix("repo/")
    preimage = item.get("preimage", {})
    postimage = item.get("postimage", {})
    if rows.get(relative) != (
        int(preimage.get("bytes", -1)),
        str(preimage.get("sha256", "")),
    ):
        raise RuntimeError("V2 manifest does not contain the sealed repair preimage")
    value = (int(postimage.get("bytes", -1)), str(postimage.get("sha256", "")))
    if value[0] < 0 or not re.fullmatch(r"[0-9a-f]{64}", value[1]):
        raise RuntimeError("V3 repair postimage identity is invalid")
    live = REPO / Path(relative)
    if not live.is_file() or identity(live) != {
        "bytes": value[0],
        "sha256": value[1],
    }:
        raise RuntimeError("live V3 repaired source differs from the sealed postimage")
    rows[relative] = value
    rows = dict(sorted(rows.items()))
    if len(rows) != 1206:
        raise RuntimeError("V3 repair unexpectedly changed the source path set")
    return rows, repair


def independent_v3_source_gate(
    rows: dict[str, tuple[int, str]]
) -> tuple[dict[str, Any], dict[str, object]]:
    if not V3_SOURCE_MANIFEST.is_file() or not V3_SOURCE_QA.is_file():
        raise RuntimeError(
            "B008 V3 source gate is not yet available; waiting for the exact V3 "
            "source manifest and QA"
        )
    for path, expected in EXPECTED_V3.items():
        require_identity(path, expected, path.name)
    source_rows = parse_manifest(V3_SOURCE_MANIFEST)
    if source_rows != rows:
        raise RuntimeError("independent B008 V3 manifest differs from the repair derivation")
    qa = json.loads(V3_SOURCE_QA.read_text(encoding="utf-8"))
    if (
        qa.get("$schema") != "r011-b008-source-qa/v3"
        or qa.get("boundary_id") != BOUNDARY_ID
        or qa.get("status") != "PASS_PAGE_FILL_REPAIRED_SOURCE_CLOSURE"
        or qa.get("checks", {}).get("passed") != 30
        or qa.get("checks", {}).get("failed") != 0
        or qa.get("checks", {}).get("blockers") != []
        or qa.get("source_closure", {}).get("files") != 1206
        or qa.get("source_closure", {}).get("changed_files")
        != ["ch_summarizing_data/TeX/review_exercises.tex"]
        or qa.get("source_closure", {}).get("unchanged_files_exact") != 1205
        or qa.get("exact_reconstruction", {}).get(
            "v2_preimage_reconstructed_exactly"
        )
        is not True
        or qa.get("exact_reconstruction", {}).get(
            "v3_postimage_forward_replayed_exactly"
        )
        is not True
    ):
        raise RuntimeError("independent B008 V3 source QA is not a terminal PASS")
    authority = qa.get("authority", {})
    if (
        authority.get("repository") != AUTHORITY_REPOSITORY
        or authority.get("commit") != AUTHORITY_COMMIT
        or authority.get("tree") != AUTHORITY_TREE
    ):
        raise RuntimeError("independent B008 V3 source authority differs from the pin")
    expected_manifest = {
        "path": base.rel(V3_SOURCE_MANIFEST),
        **identity(V3_SOURCE_MANIFEST),
    }
    if qa.get("source_closure", {}).get("manifest") != expected_manifest:
        raise RuntimeError("B008 V3 source QA does not bind its exact manifest")
    expected_repair = {
        "path": base.rel(V2_LAYOUT_REPAIR_RECEIPT),
        **identity(V2_LAYOUT_REPAIR_RECEIPT),
    }
    repair_binding = (
        qa.get("repair_authority", {}).get("receipt")
        or qa.get("layout_repair_receipt")
    )
    if repair_binding != expected_repair:
        raise RuntimeError("B008 V3 source QA binds a different V2 repair receipt")
    return qa, {
        "status": "passed",
        "source_manifest": expected_manifest,
        "source_qa": {"path": base.rel(V3_SOURCE_QA), **identity(V3_SOURCE_QA)},
        "source_qa_schema": qa.get("$schema") or qa.get("schema"),
        "checks_passed": qa.get("checks", {}).get("passed"),
        "checks_failed": qa.get("checks", {}).get("failed"),
    }


def require_source_gate() -> tuple[dict[str, tuple[int, str]], dict[str, Any]]:
    rows, repair = rejected_v2_and_repair()
    _, independent = independent_v3_source_gate(rows)
    raw = manifest_bytes(rows)
    DERIVED_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    if DERIVED_MANIFEST.exists() and DERIVED_MANIFEST.read_bytes() != raw:
        raise RuntimeError("refusing to overwrite a differing B008 V3 manifest")
    if not DERIVED_MANIFEST.exists():
        DERIVED_MANIFEST.write_bytes(raw)
    if DERIVED_MANIFEST.read_bytes() != raw:
        raise RuntimeError("B008 V3 manifest write/readback failed")
    return rows, {
        "status": "passed",
        "rejected_v2": {
            "candidate_pdf": {"path": base.rel(V2_CANDIDATE_PDF), **identity(V2_CANDIDATE_PDF)},
            "build_receipt": {"path": base.rel(V2_BUILD_RECEIPT), **identity(V2_BUILD_RECEIPT)},
            "agent_visual_findings": {"path": base.rel(V2_AGENT_VISUAL), **identity(V2_AGENT_VISUAL)},
            "root_visual_findings": {"path": base.rel(V2_ROOT_VISUAL), **identity(V2_ROOT_VISUAL)},
            "source_manifest": {"path": base.rel(V2_SOURCE_MANIFEST), **identity(V2_SOURCE_MANIFEST)},
            "source_qa": {"path": base.rel(V2_SOURCE_QA), **identity(V2_SOURCE_QA)},
        },
        "v2_layout_repair_receipt": {
            "path": base.rel(V2_LAYOUT_REPAIR_RECEIPT),
            **identity(V2_LAYOUT_REPAIR_RECEIPT),
            "status": repair["status"],
            "repair_id": repair["repair"]["id"],
        },
        "independent_v3_source_gate": independent,
    }


def verify_snapshot(errors: list[str]) -> dict[str, object]:
    rows, source = require_source_gate()
    snapshot = base.verify_tree(SNAPSHOT, rows, errors)
    prohibited = bytes((70, 108, 111, 114, 105, 115)).lower()
    token_paths: list[str] = []
    absolute_profile_paths: list[str] = []
    for path in sorted(item for item in SNAPSHOT.rglob("*") if item.is_file()):
        raw = path.read_bytes()
        relative = str(path.relative_to(SNAPSHOT)).replace("\\", "/")
        if prohibited in raw.lower():
            token_paths.append(relative)
        if re.search(br"(?i)C:\\+Users\\+", raw):
            absolute_profile_paths.append(relative)
    if token_paths:
        errors.append(f"snapshot prohibited-token paths: {token_paths}")
    if absolute_profile_paths:
        errors.append(f"snapshot absolute-profile paths: {absolute_profile_paths}")
    return {
        **snapshot,
        "derived_snapshot_manifest": {
            "path": base.rel(DERIVED_MANIFEST),
            **identity(DERIVED_MANIFEST),
            "file_count": len(rows),
            "file_bytes": sum(size for size, _ in rows.values()),
            "derivation": (
                "exact rejected R011-B008 V2 closure plus the single page-fill "
                "postimage sealed in the V2 layout-repair receipt"
            ),
        },
        **source,
        "privacy_scan": {
            "prohibited_token_path_count": len(token_paths),
            "prohibited_token_paths": token_paths,
            "absolute_profile_path_count": len(absolute_profile_paths),
            "absolute_profile_paths": absolute_profile_paths,
            "result": "PASS_ZERO_ZERO"
            if not token_paths and not absolute_profile_paths
            else "FAIL",
        },
    }


def _page_texts(reader: PdfReader) -> list[str]:
    chunks = TEXT.read_text(encoding="utf-8", errors="replace").split("\f")
    return [base.normalized_text(text) for text in chunks[: len(reader.pages)]]


def candidate_pages(reader: PdfReader) -> tuple[list[int], dict[str, object]]:
    texts = _page_texts(reader)
    required_context = list(range(78, 83)) + list(range(388, 392))
    if max(required_context) > len(reader.pages):
        raise RuntimeError("required B008 V3 visual pages exceed the page count")
    exercise_titles = {
        27: "ujian susulan",
        28: "kematian bayi",
        29: "penonton televisi",
        30: "statistik baru",
        31: "pemenang oscar",
        32: "nilai ujian",
        33: "nilai statistika",
        34: "pemenang maraton",
    }
    exercise_hits: dict[str, list[int]] = {}
    for number, title in exercise_titles.items():
        hits = [
            page
            for page, text in enumerate(texts, 1)
            if 75 <= page <= 82 and f"2.{number} {title}" in text
        ]
        if not hits:
            raise RuntimeError(f"localized exercise 2.{number} is missing")
        exercise_hits[f"2.{number}"] = hits
    ordered = [min(exercise_hits[f"2.{number}"]) for number in exercise_titles]
    if ordered != sorted(ordered):
        raise RuntimeError("B008 V3 exercises are not in source order")

    answer_phrases = {27: "ujian susulan", 29: "menceng ke kanan", 31: "aktris terbaik", 33: "nilai"}
    answer_hits: dict[str, list[int]] = {}
    for number, phrase in answer_phrases.items():
        hits = [
            page
            for page, text in enumerate(texts, 1)
            if 385 <= page <= 392 and f"2.{number}" in text and phrase in text
        ]
        if not hits:
            raise RuntimeError(f"localized public answer 2.{number} is missing")
        answer_hits[f"2.{number}"] = hits

    english_markers = (
        "make-up exam",
        "infant mortality",
        "tv watchers",
        "best actor and actress winners",
        "exam scores",
        "marathon winners",
        "oscar winners from",
    )
    english_hits = {
        marker: [page for page, text in enumerate(texts, 1) if 78 <= page <= 80 and marker in text]
        for marker in english_markers
    }
    english_hits = {marker: hits for marker, hits in english_hits.items() if hits}
    if english_hits:
        raise RuntimeError(f"reader-visible B008 V3 English remains: {english_hits}")

    page_80 = texts[79]
    page_80_markers = {
        "part_c_instruction": "bandingkan distribusi waktu maraton pria dan wanita",
        "part_d_instruction": "grafik deret waktu di bawah ini",
        "localized_axis": "waktu maraton",
    }
    missing_page_80 = [name for name, marker in page_80_markers.items() if marker not in page_80]
    if missing_page_80:
        raise RuntimeError(f"V3 page 80 content markers are missing: {missing_page_80}")
    privacy_token = "".join(chr(value) for value in (70, 108, 111, 114, 105, 115)).lower()
    privacy_hits = [page for page, text in enumerate(texts, 1) if privacy_token in text]
    if privacy_hits:
        raise RuntimeError(f"prohibited reader-visible token on pages {privacy_hits}")
    pages = sorted(set(required_context))
    return pages, {
        "coverage_policy": (
            "fixed 300-dpi pages 78-82 and 388-391; V3 page-fill and vertical "
            "centering are verified visually after automated marker checks"
        ),
        "exercise_hits": exercise_hits,
        "public_answer_hits": answer_hits,
        "reader_visible_english_marker_hits": english_hits,
        "page_80_content_markers": page_80_markers,
        "page_80_content_markers_missing": missing_page_80,
        "prohibited_reader_visible_token_hits": privacy_hits,
        "required_visual_pages": required_context,
        "all_candidate_pages": pages,
    }


_original_structure_checks = base.structure_checks
_original_evaluate = base.evaluate
_original_tool_versions = base.tool_versions


def task_relative_tool_versions() -> dict[str, object]:
    versions = _original_tool_versions()
    for record in versions.values():
        if isinstance(record, dict) and "path" in record:
            record["executable"] = Path(str(record.pop("path"))).name
    return versions


def structure_checks(errors: list[str]) -> tuple[dict[str, object], PdfReader]:
    structure, reader = _original_structure_checks(errors)
    structure["b008_v3_boundary_pages"] = structure.pop("b006_boundary_pages", {})
    prohibited = bytes((70, 108, 111, 114, 105, 115)).lower()
    raw_pdf_hit = prohibited in PDF.read_bytes().lower()
    if raw_pdf_hit:
        errors.append("final V3 PDF raw bytes contain the prohibited token")
    structure["raw_pdf_prohibited_token_present"] = raw_pdf_hit
    return structure, reader


def evaluate() -> tuple[bytes, bytes, dict[str, object]]:
    render_manifest_raw, _, receipt = _original_evaluate()
    receipt["schema_version"] = "0.5.0"
    receipt["candidate_iteration"] = "V3"
    receipt["gate_script"] = {"path": base.rel(Path(__file__).resolve()), **identity(Path(__file__).resolve())}
    receipt["limitations"] = [
        "This V3 candidate is not promoted and no automated visual PASS is asserted.",
        "Chapter 3 and later instructional content deliberately remain upstream English.",
        "The PDF declares id-ID but the inherited source does not produce a structurally tagged PDF.",
        "One inherited unreferenced duplicate page-destination warning is permitted and counted exactly.",
        "TeX box-warning counts are retained for page-by-page visual review.",
        "The six exact English figure witnesses remain frozen but are not reader-linked.",
    ]
    model_line = "OpenAI Codex gpt-5.6-sol, Ultra"
    model_sources: list[dict[str, object]] = []
    for relative in ("README.md", "CITATION.cff"):
        path = LANE / relative
        count = path.read_text(encoding="utf-8").count(model_line)
        model_sources.append({"path": relative, **identity(path), "exact_model_line_occurrences": count})
        if count != 1:
            receipt["errors"].append(f"exact production-model line count differs in {relative}: {count}")
    receipt["edition_metadata"] = {
        "locale": "id-ID",
        "exact_model_identification": model_line,
        "exact_model_line_sources": model_sources,
        "localized_scope": "Bab 1, Bagian 2.1-2.3, dan latihan 2.27-2.34 beserta jawaban publik ganjil",
        "v3_repair": "full-width and vertically centered Exercise 2.34 continuation on page 80",
    }
    if receipt["errors"]:
        receipt["nonvisual_status"] = "failed"
        receipt["status"] = "failed"
    receipt["write_boundary"] = (
        "scripts/qa_build_b008_v3.py and V3-specific paths below qa/b008-build; "
        "V1/V2 evidence remains immutable and no source/output/backend/release/control/"
        "Git/network/admission/publication mutation is performed"
    )
    return render_manifest_raw, base.canonical_json(receipt), receipt


def configure_base() -> None:
    base.MANIFEST = DERIVED_MANIFEST
    base.SOURCE_RECEIPT = V3_SOURCE_QA
    base.BUILD_ROOT = BUILD_ROOT
    base.SNAPSHOT = SNAPSHOT
    base.FINAL = FINAL
    base.PDF = PDF
    base.PASS3_PDF = PASS3_PDF
    base.TEXT = TEXT
    base.LOG = LOG
    base.FLS = FLS
    base.BUILD_RECEIPT = CANDIDATE_RECEIPT
    base.RENDER = RENDER
    base.RENDER_MANIFEST = RENDER_MANIFEST
    base.PAGE_LOCATOR = PAGE_LOCATOR
    base.CONTACT_SHEET = CONTACT_SHEET
    base.BOUNDARY_ID = BOUNDARY_ID
    base.MINIMUM_PAGE_COUNT = 425
    base.RENDER_DPI = 300
    base.MANDATORY_VISUAL_PAGES = tuple(range(78, 83)) + tuple(range(388, 392))
    base.require_source_gate = require_source_gate
    base.verify_snapshot = verify_snapshot
    base.candidate_pages = candidate_pages
    base.structure_checks = structure_checks
    base.tool_versions = task_relative_tool_versions
    base.evaluate = evaluate


def main() -> int:
    configure_base()
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
