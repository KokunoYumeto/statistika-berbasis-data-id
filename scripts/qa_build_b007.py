#!/usr/bin/env python3
"""Build and non-visually qualify the exact R011-B007 whole-book PDF.

The admitted B006 source closure is updated only by the exact source and asset
deltas bound by the authoritative B007 source gate.  The resulting
path-sorted snapshot manifest is materialized under ``qa/b007-build`` and its
files are copied from ``repo`` into an isolated source snapshot before the
documented four-pass MiKTeX build is run.

The final two TeX passes must be byte-identical.  This gate then performs the
same structural, link, metadata, log, input-closure, and renderer checks used by
the admitted B006 build.  It deliberately stops at ``pending_visual_review``;
promotion is owned by the separate operator-inspection finalizer.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import qa_build_b006 as base
from pypdf import PdfReader


LANE = Path(__file__).resolve().parents[1]
QA = LANE / "qa"
REPO = LANE / "repo"

B006_MANIFEST = QA / "R011-B006_TARGET_MANIFEST.tsv"
SOURCE_MANIFEST = QA / "R011-B007_SOURCE_APPLICATION_MANIFEST.json"
SOURCE_RECEIPT = QA / "R011-B007_SOURCE_APPLICATION_RECEIPT.json"
SOURCE_QA = QA / "R011-B007_SOURCE_GATE_QA.json"

BUILD_ROOT = QA / "b007-build"
DERIVED_MANIFEST = BUILD_ROOT / "R011-B007_SNAPSHOT_MANIFEST_V8.tsv"
SNAPSHOT = BUILD_ROOT / "source-snapshot-v8"
FINAL = BUILD_ROOT / "final-v8"
PDF = FINAL / "main.pdf"
PASS3_PDF = FINAL / "main-pass3.pdf"
TEXT = FINAL / "main-final.txt"
LOG = FINAL / "main.log"
FLS = FINAL / "main.fls"
CANDIDATE_RECEIPT = FINAL / "CANDIDATE_BUILD_QA_V8.json"

RENDER = QA / "b007-render" / "final-v8"
RENDER_MANIFEST = RENDER / "FINAL_MANIFEST.tsv"
PAGE_LOCATOR = RENDER / "PAGE_LOCATOR.json"
CONTACT_SHEET = RENDER / "CONTACT_SHEET.png"

BOUNDARY_ID = "R011-B007"
AUTHORITY_REPOSITORY = "https://github.com/OpenIntroStat/openintro-statistics"
AUTHORITY_COMMIT = "fee25091fb24e89c36296fd67c48c1fcf7a93b6e"
AUTHORITY_TREE = "d61cc601e7d97759ce805900520f784d02a0489e"

EXPECTED = {
    SOURCE_MANIFEST: (
        27428,
        "7f8943fc8d02e4f9502f9235fcb0160b9326261e8faf0b8099d8138595277496",
    ),
    SOURCE_RECEIPT: (
        26533,
        "1b0429aa37617e021fb77d1ede777347dbb5df24cba79ebda60da521d3ee3187",
    ),
    SOURCE_QA: (
        3370,
        "677921acb28e9da034c4c40fc78a7367162ceaf1d986a8bdb0f29977aa237294",
    ),
    B006_MANIFEST: (
        173738,
        "bdf80b178094d903305c8d5539d969db39502720bbe0e0d5e3735ca92e8a05f4",
    ),
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def identity(path: Path) -> dict[str, object]:
    raw = path.read_bytes()
    return {"bytes": len(raw), "sha256": sha256(raw)}


def require_identity(path: Path, expected: tuple[int, str], label: str) -> None:
    if not path.is_file() or identity(path) != {
        "bytes": expected[0],
        "sha256": expected[1],
    }:
        raise RuntimeError(f"{label} identity differs from the accepted gate")


def parse_b006_manifest() -> dict[str, tuple[int, str]]:
    require_identity(B006_MANIFEST, EXPECTED[B006_MANIFEST], "B006 target manifest")
    rows: dict[str, tuple[int, str]] = {}
    for number, line in enumerate(
        B006_MANIFEST.read_text(encoding="utf-8").splitlines(), 1
    ):
        parts = line.split("\t")
        if len(parts) != 3:
            raise RuntimeError(f"invalid B006 manifest row {number}")
        path, size_text, digest = parts
        rows[path] = (int(size_text), digest)
    if len(rows) != 1195 or list(rows) != sorted(rows):
        raise RuntimeError("B006 manifest path set/order differs from admitted closure")
    return rows


def gate_records() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    for path, expected in EXPECTED.items():
        require_identity(path, expected, path.name)
    manifest = json.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))
    receipt = json.loads(SOURCE_RECEIPT.read_text(encoding="utf-8"))
    qa = json.loads(SOURCE_QA.read_text(encoding="utf-8"))
    authority = manifest.get("authority", {})
    if (
        manifest.get("schema_version")
        != "r011-b007-source-application-manifest/1.3.0"
        or manifest.get("boundary_id") != BOUNDARY_ID
        or manifest.get("locale") != "id-ID"
        or manifest.get("status") != "source_applied_assets_promoted"
        or authority.get("repository") != AUTHORITY_REPOSITORY
        or authority.get("commit") != AUTHORITY_COMMIT
        or authority.get("tree") != AUTHORITY_TREE
    ):
        raise RuntimeError("source application manifest is not the exact B007 authority")
    if (
        receipt.get("schema_version")
        != "r011-b007-source-application-receipt/1.3.0"
        or receipt.get("boundary_id") != BOUNDARY_ID
        or receipt.get("result") != "PASS_SOURCE_APPLICATION_AND_ASSET_BINDING"
        or receipt.get("remaining_source_or_asset_dependency") is not None
    ):
        raise RuntimeError("source application receipt is not an unblocked PASS")
    expected_manifest = {
        "path": "qa/R011-B007_SOURCE_APPLICATION_MANIFEST.json",
        **identity(SOURCE_MANIFEST),
    }
    if receipt.get("application_manifest") != expected_manifest:
        raise RuntimeError("source application receipt does not bind the exact manifest")
    if (
        qa.get("schema_version") != "r011-b007-source-gate-qa/1.3.0"
        or qa.get("boundary_id") != BOUNDARY_ID
        or qa.get("result") != "PASS_SOURCE_GATE_ASSETS_BOUND"
        or qa.get("remaining_source_or_asset_dependency") is not None
        or qa.get("checks", {}).get("count") != 14
        or qa.get("checks", {}).get("failure_count") != 0
        or qa.get("adversarial_self_tests", {}).get("count") != 14
        or qa.get("adversarial_self_tests", {}).get("failure_count") != 0
    ):
        raise RuntimeError("source-gate QA is not the exact passing 14/14 + 14/14 gate")
    if qa.get("application_manifest") != expected_manifest:
        raise RuntimeError("source-gate QA does not bind the exact manifest")
    expected_receipt = {
        "path": "qa/R011-B007_SOURCE_APPLICATION_RECEIPT.json",
        **identity(SOURCE_RECEIPT),
    }
    if qa.get("application_receipt") != expected_receipt:
        raise RuntimeError("source-gate QA does not bind the exact source receipt")
    return manifest, receipt, qa


def derived_rows(manifest: dict[str, Any]) -> dict[str, tuple[int, str]]:
    rows = parse_b006_manifest()
    deltas: dict[str, tuple[int, str]] = {}
    for item in manifest.get("final_files", []):
        path = str(item.get("path", ""))
        if path.startswith("repo/"):
            deltas[path.removeprefix("repo/")] = (
                int(item["bytes"]),
                str(item["sha256"]),
            )
    assets = manifest.get("asset_promotion", {}).get("destinations", [])
    if len(assets) != 13:
        raise RuntimeError(f"expected 13 bound asset destinations, found {len(assets)}")
    for item in assets:
        path = str(item.get("path", ""))
        if not path.startswith("repo/"):
            raise RuntimeError(f"asset destination escapes repo: {path!r}")
        relative = path.removeprefix("repo/")
        value = (int(item["bytes"]), str(item["sha256"]))
        if relative in deltas and deltas[relative] != value:
            raise RuntimeError(f"conflicting B007 delta identity: {relative}")
        deltas[relative] = value
    if len(deltas) != 24:
        raise RuntimeError(f"expected 24 unique repo deltas, found {len(deltas)}")
    additions = sorted(set(deltas) - set(rows))
    expected_additions = sorted(
        path for path in deltas if path.endswith(".source-en.pdf")
    )
    if additions != expected_additions or len(additions) != 5:
        raise RuntimeError(f"unexpected B007 snapshot additions: {additions}")
    rows.update(deltas)
    rows = dict(sorted(rows.items()))
    if len(rows) != 1200:
        raise RuntimeError(f"unexpected B007 source-closure count: {len(rows)}")
    for relative, (size, digest) in rows.items():
        path = REPO / Path(relative)
        if not path.is_file() or identity(path) != {"bytes": size, "sha256": digest}:
            raise RuntimeError(f"live repo differs from derived B007 closure: {relative}")
    return rows


def manifest_bytes(rows: dict[str, tuple[int, str]]) -> bytes:
    return "".join(
        f"{path}\t{size}\t{digest}\n" for path, (size, digest) in rows.items()
    ).encode("utf-8")


def require_source_gate() -> tuple[dict[str, tuple[int, str]], dict[str, Any]]:
    manifest, receipt, qa = gate_records()
    rows = derived_rows(manifest)
    raw = manifest_bytes(rows)
    DERIVED_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    if DERIVED_MANIFEST.exists() and DERIVED_MANIFEST.read_bytes() != raw:
        raise RuntimeError("refusing to overwrite a differing B007 snapshot manifest")
    if not DERIVED_MANIFEST.exists():
        DERIVED_MANIFEST.write_bytes(raw)
    if DERIVED_MANIFEST.read_bytes() != raw:
        raise RuntimeError("B007 snapshot-manifest write readback failed")
    return rows, {
        "status": "passed",
        "source_application_manifest": {
            "path": base.rel(SOURCE_MANIFEST),
            **identity(SOURCE_MANIFEST),
        },
        "source_application_receipt": {
            "path": base.rel(SOURCE_RECEIPT),
            **identity(SOURCE_RECEIPT),
        },
        "source_gate_qa": {"path": base.rel(SOURCE_QA), **identity(SOURCE_QA)},
        "checks": qa["checks"],
        "adversarial_self_tests": qa["adversarial_self_tests"],
        "source_receipt_result": receipt["result"],
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
                "admitted R011-B006 target manifest plus exactly 24 hash-bound "
                "B007 repo deltas, including five source-en witness additions"
            ),
        },
        **source,
        "assembly_evidence": {
            "policy": (
                "every path and file identity is recomputed against the admitted "
                "base closure and exact B007 deltas on every replay"
            ),
            "persisted_separately": True,
            "embedded_in_candidate_receipt": True,
        },
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
    section_23 = base.destination_page(reader, "section.2.3")
    chapter_3 = base.destination_page(reader, "chapter.3")
    if not 1 < section_23 < chapter_3 <= len(reader.pages):
        raise RuntimeError(
            f"unexpected B007 destination order: section.2.3={section_23}, "
            f"chapter.3={chapter_3}"
        )
    texts = _page_texts(reader)
    prohibited = "".join(chr(value) for value in (70, 108, 111, 114, 105, 115)).lower()
    prohibited_hits = [
        number for number, text in enumerate(texts, 1) if prohibited in text
    ]
    if prohibited_hits:
        raise RuntimeError(
            f"prohibited reader-visible token on PDF pages {prohibited_hits}"
        )

    heading_hits = [
        number
        for number, text in enumerate(texts, 1)
        if section_23 <= number < chapter_3
        and "2.3 studi kasus: vaksin malaria" in text
    ]
    exercise_25_hits = [
        number
        for number, text in enumerate(texts, 1)
        if section_23 <= number < chapter_3
        and "2.25 efek samping avandia" in text
    ]
    exercise_26_hits = [
        number
        for number, text in enumerate(texts, 1)
        if section_23 <= number < chapter_3
        and "2.26 transplantasi jantung" in text
    ]
    if section_23 not in heading_hits or not exercise_25_hits or not exercise_26_hits:
        raise RuntimeError(
            "B007 Section 2.3 or exercise markers missing: "
            f"heading={heading_hits}, ex25={exercise_25_hits}, ex26={exercise_26_hits}"
        )
    if max(exercise_25_hits) > min(exercise_26_hits):
        raise RuntimeError("Exercises 2.25 and 2.26 are out of source order")

    answer_hits = [
        number
        for number, text in enumerate(texts, 1)
        if number > 300
        and "2.25" in text
        and "rosiglitazon" in text
        and "masalah kardiovaskular" in text
    ]
    if not answer_hits:
        raise RuntimeError("public answer 2.25 marker is missing")

    preface_hits = [
        number
        for number, text in enumerate(texts, 1)
        if number <= 20 and "statistika inferensial dalam konteks" in text
    ]
    if not preface_hits:
        raise RuntimeError("preface statistika-inferensial marker is missing")

    scope_hits = [
        number
        for number, text in enumerate(texts, 1)
        if number <= 20 and "bab 1 dan bagian 2.1–2.3" in text
    ]
    if not scope_hits:
        raise RuntimeError("localized-edition scope marker through Section 2.3 is missing")

    title_privacy_hits = [
        number
        for number, text in enumerate(texts, 1)
        if number <= 20 and "atas permintaan pengguna" in text
    ]
    if not title_privacy_hits:
        raise RuntimeError("neutral derivative-title requester wording is missing")

    interval_hits = [
        number
        for number, text in enumerate(texts, 1)
        if number < section_23 and "interval kelas" in text
    ]

    section_context = list(
        range(max(1, section_23 - 1), min(len(reader.pages), chapter_3 + 1) + 1)
    )
    answer_context = list(
        range(max(1, min(answer_hits) - 1), min(len(reader.pages), max(answer_hits) + 1) + 1)
    )
    preface_context = sorted(
        {
            page
            for hit in preface_hits
            for page in range(max(1, hit - 1), min(len(reader.pages), hit + 1) + 1)
        }
    )
    title_privacy_context = sorted(
        {
            page
            for hit in title_privacy_hits
            for page in range(max(1, hit - 1), min(len(reader.pages), hit + 1) + 1)
        }
    )
    pages = sorted(
        set(
            section_context
            + answer_context
            + preface_context
            + scope_hits
            + title_privacy_context
            + interval_hits
        )
    )
    return pages, {
        "coverage_policy": (
            "all Section 2.3 pages, one preceding page, the Chapter 3 transition "
            "and one following page; public answer 2.25 plus adjacent pages; the "
            "preface terminology-correction page plus adjacent pages; and every "
            "earlier translated page whose extracted accessibility text contains "
            "the propagated term interval kelas; plus the neutral requester-credit "
            "title page and adjacent context"
        ),
        "section_2_3_page": section_23,
        "chapter_3_transition_page": chapter_3,
        "section_2_3_content_span": [section_23, chapter_3 - 1],
        "section_transition_context_pages": section_context,
        "heading_hits": heading_hits,
        "exercise_2_25_hits": exercise_25_hits,
        "exercise_2_26_hits": exercise_26_hits,
        "public_answer_2_25_hits": answer_hits,
        "public_answer_context_pages": answer_context,
        "preface_statistika_inferensial_hits": preface_hits,
        "preface_context_pages": preface_context,
        "localized_edition_scope": "Bab 1 dan Bagian 2.1–2.3",
        "localized_edition_scope_hits": scope_hits,
        "title_privacy_hits": title_privacy_hits,
        "title_privacy_context_pages": title_privacy_context,
        "interval_kelas_accessibility_hits": interval_hits,
        "prohibited_reader_visible_token_hits": prohibited_hits,
        "all_candidate_pages": pages,
    }


_original_structure_checks = base.structure_checks
_original_evaluate = base.evaluate
_original_tool_versions = base.tool_versions


def task_relative_tool_versions() -> dict[str, object]:
    """Retain reproducibility metadata without leaking host profile paths."""
    versions = _original_tool_versions()
    for record in versions.values():
        if isinstance(record, dict) and "path" in record:
            record["executable"] = Path(str(record.pop("path"))).name
    return versions


def structure_checks(errors: list[str]) -> tuple[dict[str, object], PdfReader]:
    structure, reader = _original_structure_checks(errors)
    structure["b007_boundary_pages"] = structure.pop("b006_boundary_pages", {})
    prohibited = bytes((70, 108, 111, 114, 105, 115)).lower()
    raw_pdf_hit = prohibited in PDF.read_bytes().lower()
    if raw_pdf_hit:
        errors.append("final PDF raw bytes contain the prohibited token")
    structure["raw_pdf_prohibited_token_present"] = raw_pdf_hit
    return structure, reader


def evaluate() -> tuple[bytes, bytes, dict[str, object]]:
    render_manifest_raw, _, receipt = _original_evaluate()
    receipt["schema_version"] = "0.2.0"
    receipt["gate_script"] = {
        "path": base.rel(Path(__file__).resolve()),
        **identity(Path(__file__).resolve()),
    }
    receipt["limitations"] = [
        "This candidate is not promoted and no automated visual PASS is asserted.",
        "Chapter 3 and later instructional content deliberately remain upstream English.",
        "The PDF declares id-ID but the inherited source does not produce a structurally tagged PDF.",
        "One inherited unreferenced duplicate page-destination warning is permitted and counted exactly.",
        "TeX box-warning counts are retained for page-by-page visual review.",
        "The five exact English figure witnesses are frozen in the source closure but are not reader-linked.",
    ]
    model_line = "OpenAI Codex gpt-5.6-sol, Ultra"
    model_sources: list[dict[str, object]] = []
    for relative in ("README.md", "CITATION.cff"):
        path = LANE / relative
        count = path.read_text(encoding="utf-8").count(model_line)
        model_sources.append(
            {"path": relative, **identity(path), "exact_model_line_occurrences": count}
        )
        if count != 1:
            receipt["errors"].append(
                f"exact production-model line count differs in {relative}: {count}"
            )
    receipt["edition_metadata"] = {
        "exact_model_identification": model_line,
        "exact_model_line_sources": model_sources,
        "localized_scope": "Bab 1 dan Bagian 2.1–2.3",
    }
    if receipt["errors"]:
        receipt["nonvisual_status"] = "failed"
        receipt["status"] = "failed"
    receipt["write_boundary"] = (
        "qa/b007-build, qa/b007-render, and the B007 candidate receipt only; "
        "no repo/output/backend/publication mutation"
    )
    return render_manifest_raw, base.canonical_json(receipt), receipt


def configure_base() -> None:
    base.MANIFEST = DERIVED_MANIFEST
    base.SOURCE_RECEIPT = SOURCE_RECEIPT
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
    base.MINIMUM_PAGE_COUNT = 419
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
