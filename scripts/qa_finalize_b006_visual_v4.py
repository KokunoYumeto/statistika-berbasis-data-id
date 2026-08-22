#!/usr/bin/env python3
"""Finalize the accepted R011-B006 v4 visual/build QA without promotion.

The immutable automated candidate remains ``pending_visual_review``.  This
separate deterministic gate binds the main agent's full-resolution inspection
of every required v4 page, writes the authoritative visual audit, and derives
the final build-QA receipt.  With no arguments it is a read-only exact replay.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from pypdf import PdfReader


LANE = Path(__file__).resolve().parents[1]
QA = LANE / "qa"
BUILD_DRIVER = LANE / "scripts" / "qa_build_b006.py"
CANDIDATE_RECEIPT = QA / "b006-build" / "final-v4" / "CANDIDATE_BUILD_QA_V4.json"
PDF = QA / "b006-build" / "final-v4" / "main.pdf"
PASS3_PDF = QA / "b006-build" / "final-v4" / "main-pass3.pdf"
RENDER = QA / "b006-render" / "final-v4"
RENDER_MANIFEST = RENDER / "FINAL_MANIFEST.tsv"
PAGE_LOCATOR = RENDER / "PAGE_LOCATOR.json"
CONTACT_SHEET = RENDER / "CONTACT_SHEET.png"
VISUAL_AUDIT = QA / "R011-B006_VISUAL_AUDIT_V4.json"
FINAL_BUILD_QA = QA / "R011-B006_BUILD_QA_V4.json"

BOUNDARY_ID = "R011-B006"
INSPECTED_PAGES = [
    61,
    62,
    63,
    64,
    65,
    66,
    67,
    68,
    69,
    70,
    71,
    72,
    73,
    387,
    388,
    389,
    390,
]
MANDATORY_V4_PAGES = [*range(61, 74), 388, 389, 390]
PARENT_ACCEPTANCE_STATEMENT = (
    "MAIN-AGENT V4 VISUAL ACCEPTANCE. I individually inspected at original/full "
    "resolution every rendered page [61,62,63,64,65,66,67,68,69,70,71,72,73,"
    "387,388,389,390]. All pass: no clipping, overlap, truncation, orphaned/"
    "stranded continuation, float-only/mostly-empty defect, broken figures/tables, "
    "unreadable text, or miscentering. Specific regressions closed: Figure 2.28 "
    "integrated on p69; Exercises 2.21-2.24 flow across pp70-71 with p71 "
    "substantively filled; Section 2.3 starts p72; answer continuation is compact "
    "across pp387-389 and p390 is full."
)

EXPECTED_IDENTITIES = {
    "build_driver": {
        "bytes": 49624,
        "sha256": "201e90f21fe17ee27e64e8f3a7ce79d5f50ddbe1124d6886f086c373d6fe3795",
    },
    "candidate_receipt": {
        "bytes": 15252,
        "sha256": "a33e9c184697bfce38938d6ab52843d57f6de592cf42abd37f3effd75a0c1fbc",
    },
    "pdf": {
        "bytes": 21975722,
        "sha256": "d9a3df7d44a62babde04c355cb8dbb9edc74de947cc8162a3d30d872bea372b2",
    },
    "render_manifest": {
        "bytes": 1500,
        "sha256": "dd0a15cb79c3e4e3b5d89944d1fc275716d72732d8824fd4d3fe6c96fd413588",
    },
    "page_locator": {
        "bytes": 1599,
        "sha256": "4d6721fd2441371b609e1961ec9b0255b263b90e93b96253bc90253dd23f1492",
    },
    "contact_sheet": {
        "bytes": 859627,
        "sha256": "313d69ae077a3d53389cd5b4a9064abe731a2996f05f612b9b7e79044b880fd7",
    },
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def identity_bytes(data: bytes) -> dict[str, object]:
    return {"bytes": len(data), "sha256": sha256_bytes(data)}


def identity(path: Path) -> dict[str, object]:
    return identity_bytes(path.read_bytes())


def rel(path: Path) -> str:
    return str(path.relative_to(LANE)).replace("\\", "/")


def canonical_json(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")


def require_identity(path: Path, expected: dict[str, object], label: str) -> None:
    if not path.is_file() or identity(path) != expected:
        raise RuntimeError(f"{label} identity differs from the accepted v4 evidence")


def parse_render_manifest() -> list[dict[str, object]]:
    require_identity(
        RENDER_MANIFEST,
        EXPECTED_IDENTITIES["render_manifest"],
        "render manifest",
    )
    images: list[dict[str, object]] = []
    pages: list[int] = []
    for number, line in enumerate(
        RENDER_MANIFEST.read_text(encoding="utf-8").splitlines(), 1
    ):
        parts = line.split("\t")
        if len(parts) != 4:
            raise RuntimeError(f"invalid render-manifest row {number}")
        page_text, name, size_text, digest = parts
        try:
            page = int(page_text)
            size = int(size_text)
        except ValueError as exc:
            raise RuntimeError(f"invalid numeric render-manifest row {number}") from exc
        if name != f"page-{page:03d}.png":
            raise RuntimeError(f"render filename/page mismatch at row {number}")
        expected = {"bytes": size, "sha256": digest}
        image = RENDER / name
        require_identity(image, expected, f"rendered page {page}")
        pages.append(page)
        images.append({"page": page, "path": rel(image), **expected})
    if pages != INSPECTED_PAGES or len(set(pages)) != len(pages):
        raise RuntimeError(f"render-manifest page set/order differs: {pages}")
    return images


def require_candidate() -> tuple[dict[str, Any], list[dict[str, object]]]:
    for key, path in (
        ("build_driver", BUILD_DRIVER),
        ("candidate_receipt", CANDIDATE_RECEIPT),
        ("pdf", PDF),
        ("pdf", PASS3_PDF),
        ("page_locator", PAGE_LOCATOR),
        ("contact_sheet", CONTACT_SHEET),
    ):
        require_identity(path, EXPECTED_IDENTITIES[key], key.replace("_", " "))

    candidate = json.loads(CANDIDATE_RECEIPT.read_text(encoding="utf-8"))
    if (
        candidate.get("schema") != "openintro-boundary-build-candidate-qa"
        or candidate.get("schema_version") != "0.1.0"
        or candidate.get("boundary_id") != BOUNDARY_ID
        or candidate.get("status") != "pending_visual_review"
        or candidate.get("nonvisual_status") != "passed"
        or candidate.get("errors") != []
        or candidate.get("pending")
        != ["operator inspection of every full-resolution candidate PNG"]
    ):
        raise RuntimeError("v4 candidate receipt is not the exact pending visual candidate")
    if candidate.get("gate_script") != {
        "path": rel(BUILD_DRIVER),
        **EXPECTED_IDENTITIES["build_driver"],
    }:
        raise RuntimeError("candidate does not bind the exact v4 build driver")
    expected_pdf = {"path": rel(PDF), **EXPECTED_IDENTITIES["pdf"]}
    determinism = candidate.get("determinism", {})
    if (
        candidate.get("candidate_artifact") != {**expected_pdf, "promoted": False}
        or determinism.get("byte_identical") is not True
        or determinism.get("pass_3")
        != {"path": rel(PASS3_PDF), **EXPECTED_IDENTITIES["pdf"]}
        or determinism.get("pass_4") != expected_pdf
    ):
        raise RuntimeError("candidate PDF/determinism binding differs")

    source = candidate.get("source_closure", {})
    if (
        source.get("path") != "qa/b006-build/source-snapshot-v4"
        or source.get("file_count") != 1195
        or source.get("file_bytes") != 41205947
        or source.get("path_set_and_all_file_identities_match_manifest") is not True
        or source.get("source_receipt")
        != {
            "path": "qa/R011-B006_SOURCE_QA.json",
            "bytes": 51559,
            "sha256": "524852f1e21939d8a0ced8ab5d79f1a74d0bbf552ca06f0ce252082f30a4c918",
        }
        or source.get("target_manifest")
        != {
            "path": "qa/R011-B006_TARGET_MANIFEST.tsv",
            "bytes": 173738,
            "sha256": "bdf80b178094d903305c8d5539d969db39502720bbe0e0d5e3735ca92e8a05f4",
        }
    ):
        raise RuntimeError("candidate source closure differs from the frozen v4 gate")

    visual = candidate.get("visual_evidence", {})
    if (
        visual.get("status") != "pending_operator_inspection"
        or visual.get("candidate_pages") != INSPECTED_PAGES
        or visual.get("candidate_page_count") != len(INSPECTED_PAGES)
        or visual.get("inspection_resolution_dpi") != 180
        or visual.get("render_manifest")
        != {"path": rel(RENDER_MANIFEST), **EXPECTED_IDENTITIES["render_manifest"]}
        or visual.get("page_locator")
        != {"path": rel(PAGE_LOCATOR), **EXPECTED_IDENTITIES["page_locator"]}
        or visual.get("contact_sheet")
        != {"path": rel(CONTACT_SHEET), **EXPECTED_IDENTITIES["contact_sheet"]}
        or visual.get("render_diagnostics", {}).get("unexpected_diagnostic_count") != 0
    ):
        raise RuntimeError("candidate visual-evidence binding differs")

    locator = json.loads(PAGE_LOCATOR.read_text(encoding="utf-8"))
    if (
        locator.get("all_candidate_pages") != INSPECTED_PAGES
        or locator.get("mandatory_v4_audit_pages") != MANDATORY_V4_PAGES
        or locator.get("section_2_2_content_span") != [62, 71]
        or locator.get("section_2_3_transition_page") != 72
        or locator.get("answer_context_span") != [387, 389]
    ):
        raise RuntimeError("page locator differs from the accepted v4 inspection scope")

    reader = PdfReader(PDF, strict=True)
    if len(reader.pages) != 424:
        raise RuntimeError("accepted v4 PDF page count differs from 424")
    images = parse_render_manifest()
    return candidate, images


def records() -> tuple[bytes, bytes, dict[str, Any], dict[str, Any]]:
    candidate, images = require_candidate()
    finalizer = {"path": rel(Path(__file__).resolve()), **identity(Path(__file__).resolve())}
    statement_id = identity_bytes(PARENT_ACCEPTANCE_STATEMENT.encode("utf-8"))
    candidate_id = {
        "path": rel(CANDIDATE_RECEIPT),
        **EXPECTED_IDENTITIES["candidate_receipt"],
    }

    visual_audit: dict[str, Any] = {
        "schema": "openintro-boundary-visual-audit",
        "schema_version": "0.2.0",
        "boundary_id": BOUNDARY_ID,
        "candidate": "final-v4",
        "status": "passed",
        "authority": candidate["authority"],
        "finalization_script": finalizer,
        "candidate_build_receipt": candidate_id,
        "parent_acceptance": {
            "actor": "main agent /root",
            "authority": "main-agent individual visual inspection supplied to the v4 build owner",
            "statement_verbatim": PARENT_ACCEPTANCE_STATEMENT,
            "statement_utf8": statement_id,
            "inspection_method": "each rendered page opened individually at original/full resolution",
            "inspection_resolution_dpi": 180,
            "inspected_pages": INSPECTED_PAGES,
            "inspected_page_count": len(INSPECTED_PAGES),
            "all_required_pages_inspected": True,
        },
        "evidence": {
            "candidate_pdf": {
                "path": rel(PDF),
                "pages": 424,
                **EXPECTED_IDENTITIES["pdf"],
            },
            "render_manifest": {
                "path": rel(RENDER_MANIFEST),
                **EXPECTED_IDENTITIES["render_manifest"],
            },
            "page_locator": {
                "path": rel(PAGE_LOCATOR),
                **EXPECTED_IDENTITIES["page_locator"],
            },
            "contact_sheet": {
                "path": rel(CONTACT_SHEET),
                **EXPECTED_IDENTITIES["contact_sheet"],
            },
            "individual_page_renders": images,
            "individual_page_render_count": len(images),
            "individual_page_render_bytes": sum(int(item["bytes"]) for item in images),
            "unexpected_renderer_diagnostic_count": 0,
        },
        "checks": {
            "clipping": "passed",
            "overlap": "passed",
            "truncation": "passed",
            "orphaned_or_stranded_continuation": "passed",
            "float_only_or_mostly_empty_page": "passed",
            "figures_and_tables": "passed",
            "text_legibility": "passed",
            "centering": "passed",
        },
        "severity_counts": {"P0": 0, "P1": 0, "P2": 0, "P3": 0},
        "findings": [],
        "regressions_closed": [
            {"page": 69, "check": "Figure 2.28 integrated into substantive page flow"},
            {
                "pages": [70, 71],
                "check": "Exercises 2.21-2.24 flow across both pages and page 71 is substantively filled",
            },
            {"page": 72, "check": "Section 2.3 begins on the expected transition page"},
            {
                "pages": [387, 388, 389],
                "check": "public-answer continuation remains compact across the answer span",
            },
            {"page": 390, "check": "post-answer context page is full"},
        ],
        "promotion": {
            "performed": False,
            "claim": "visual acceptance only; output/backend/publication promotion remains a separate guarded action",
        },
        "write_boundary": [
            rel(VISUAL_AUDIT),
            rel(FINAL_BUILD_QA),
        ],
    }
    visual_raw = canonical_json(visual_audit)

    final = copy.deepcopy(candidate)
    final["schema"] = "openintro-boundary-build-final-qa"
    final["schema_version"] = "0.2.0"
    final["status"] = "passed"
    final["pending"] = []
    final["candidate_history"] = {
        **candidate_id,
        "status": "pending_visual_review",
        "preserved_unchanged": True,
    }
    final["finalization_script"] = finalizer
    final["visual_evidence"]["status"] = "passed_operator_inspection"
    final["visual_evidence"]["claim"] = (
        "main agent inspected every bound PNG individually at original/full resolution; "
        "all visual checks passed"
    )
    final["visual_evidence"]["required_next_action"] = (
        "none for build/visual QA; admission guard owns any later promotion"
    )
    final["visual_evidence"]["visual_audit"] = {
        "path": rel(VISUAL_AUDIT),
        **identity_bytes(visual_raw),
    }
    final["visual_evidence"]["parent_acceptance_statement_utf8"] = statement_id
    final["build_visual_admission"] = {
        "status": "passed",
        "nonvisual_status": "passed",
        "visual_status": "passed",
        "candidate_pdf_promoted": False,
        "source_or_backend_mutated": False,
        "publication_performed": False,
        "required_next_gate": "boundary admission and guarded promotion",
    }
    final["write_boundary"] = (
        "qa/R011-B006_VISUAL_AUDIT_V4.json and qa/R011-B006_BUILD_QA_V4.json "
        "only; candidate history preserved; no PDF/output/backend/publication mutation"
    )
    final_raw = canonical_json(final)
    return visual_raw, final_raw, visual_audit, final


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--write",
        action="store_true",
        help="write canonical visual-audit and final build-QA records",
    )
    args = parser.parse_args()
    visual_raw, final_raw, visual, final = records()
    expected = ((VISUAL_AUDIT, visual_raw), (FINAL_BUILD_QA, final_raw))
    if args.write:
        for path, raw in expected:
            if path.exists() and path.read_bytes() != raw:
                raise SystemExit(f"refusing to overwrite non-canonical existing record: {rel(path)}")
            path.write_bytes(raw)
            if path.read_bytes() != raw:
                raise SystemExit(f"canonical write readback failed: {rel(path)}")
    else:
        for path, raw in expected:
            if not path.is_file() or path.read_bytes() != raw:
                raise SystemExit(f"read-only replay failed: {rel(path)} differs or is absent")

    print(
        json.dumps(
            {
                "status": final["status"],
                "nonvisual_status": final["nonvisual_status"],
                "visual_status": visual["status"],
                "candidate_receipt_preserved": identity(CANDIDATE_RECEIPT)
                == EXPECTED_IDENTITIES["candidate_receipt"],
                "candidate_pdf_promoted": final["candidate_artifact"]["promoted"],
                "inspected_pages": INSPECTED_PAGES,
                "visual_audit": {"path": rel(VISUAL_AUDIT), **identity_bytes(visual_raw)},
                "final_build_qa": {"path": rel(FINAL_BUILD_QA), **identity_bytes(final_raw)},
                "errors": final["errors"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
