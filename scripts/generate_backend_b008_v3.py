#!/usr/bin/env python3
"""Generate the isolated terminal-V3 R011-B008 backend stage.

This is an append-only finalization over ``qa/b008-backend``.  The prefinal
stage remains immutable and the admitted B007 backend is never written.  The
new stage binds the exact V3 source closure, deterministic PDF, build receipt,
and both visual judgments while leaving admission, promotion, publication,
Git, and upstream communication to separate transactions.
"""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

import generate_backend_b008 as pre


LANE = Path(__file__).resolve().parents[1]
SCRIPT_PATH = Path(__file__).resolve()
FINALIZER_PATH = LANE / "scripts" / "finalize_backend_b008_v3.py"
VALIDATOR_PATH = LANE / "scripts" / "validate_backend_b008_v3.py"
PREFINAL_EXPORTS = LANE / "qa" / "b008-backend" / "exports"
PREFINAL_RECEIPT_PATH = (
    LANE / "qa" / "b008-backend" / "BACKEND_VALIDATION_RECEIPT_R011-B008.json"
)
FINAL_ROOT = LANE / "qa" / "b008-backend-final-v3"
FINAL_EXPORTS = FINAL_ROOT / "exports"

BOUNDARY_ID = "R011-B008"
BASE_BOUNDARY_ID = "R011-B007"
SCHEMA_VERSION = "0.1.0"
RECORDED_AT = "2026-08-23T03:05:00+02:00"
WORKFLOW_ID = "r011-openintro-statistics-id-b008-backend-final-v3"
PREFINAL_RECORD_COUNT = 2472
BASE_RECORD_COUNT = 2264
PROVENANCE = (
    "Direct English-to-id-ID translation and modular indexing by "
    "OpenAI Codex gpt-5.6-sol, Ultra, at the user's request."
)

PREFINAL_MANIFEST_IDENTITY = {
    "bytes": 26449,
    "sha256": "414fff8f9aac0a9fac80cc4a3ead0a848d8322a15ac9920f677b6712c307b995",
}
PREFINAL_RECEIPT_IDENTITY = {
    "bytes": 6113,
    "sha256": "3701dcb70882227e1f3235557731eef847c3439d03e3616c92ef949b08491724",
}
PREFINAL_TOOL_IDENTITIES = {
    "scripts/generate_backend_b008.py": {
        "bytes": 59736,
        "sha256": "7b4a4bc3b3822e9e1ddc20873c2a812cfc8ab0c97b0275999e6720f8f585e80b",
    },
    "scripts/validate_backend_b008.py": {
        "bytes": 24674,
        "sha256": "b60cecfd9cf200e09941355dd01774020fdd094092da8b6d357a029070ae29d1",
    },
}

FINAL_V3_INPUTS: dict[str, dict[str, Any]] = {
    "qa/b008-source/R011-B008_SOURCE_MANIFEST_V3.tsv": {
        "bytes": 175582,
        "sha256": "743b4906fad27bad1adfcb331566517314a93602d6df3c3cc279aa56a88745f4",
        "destination": "evidence/R011-B008_SOURCE_MANIFEST_V3.tsv",
        "artifact_kind": "final_v3_source_manifest",
        "translation_state": "source_frozen",
    },
    "qa/b008-source/R011-B008_SOURCE_QA_V3.json": {
        "bytes": 6896,
        "sha256": "8fd911d8ac4164a51c44d52ce62a3277ac4f63aa2aaca4437f244550f7223a8a",
        "destination": "evidence/R011-B008_SOURCE_QA_V3.json",
        "artifact_kind": "final_v3_source_qa_receipt",
        "translation_state": "structurally_verified",
    },
    "qa/b008-build/final-v3/main.pdf": {
        "bytes": 22017328,
        "sha256": "8aa8e6ecc3edc2a33ee8d83a586c6208e49966582b2fc439c8b3007470f32800",
        "destination": None,
        "artifact_kind": "localized_boundary_pdf",
        "translation_state": "visually_checked",
    },
    "qa/b008-build/final-v3/CANDIDATE_BUILD_QA_V3.json": {
        "bytes": 17044,
        "sha256": "5d176e4275dbc41951797a043bb9270a09357ae31418868904d903939ff5beca",
        "destination": "evidence/R011-B008_CANDIDATE_BUILD_QA_V3.json",
        "artifact_kind": "final_v3_build_qa_receipt",
        "translation_state": "built",
    },
    "qa/b008-build/BUILD_ONLY_VISUAL_SANITY_V3.json": {
        "bytes": 2405,
        "sha256": "09fca6423b19e1fd2014a982d687b06119a8203684dd8992c18a19edcd238d99",
        "destination": "evidence/R011-B008_BUILD_ONLY_VISUAL_SANITY_V3.json",
        "artifact_kind": "final_v3_independent_build_visual_record",
        "translation_state": "visually_checked",
    },
    "qa/b008-visual/R011-B008_VISUAL_AUDIT_V3.json": {
        "bytes": 3085,
        "sha256": "f66bf2cceef66e2b83061fad87a6817719bf2feb9cc6ec6f06718750fb9bdbdc",
        "destination": "evidence/R011-B008_VISUAL_AUDIT_V3.json",
        "artifact_kind": "final_v3_root_visual_audit",
        "translation_state": "visually_checked",
    },
}

FINAL_SOURCE_MEMBERS = {
    "ch_summarizing_data/TeX/review_exercises.tex": {
        "bytes": 9363,
        "sha256": "91f393cf22afbace8f80626d50558809acc283417805e7aa814aecb2b0d32ae3",
    },
    "extraTeX/eoceSolutions/eoceSolutions.tex": {
        "bytes": 108110,
        "sha256": "2b2709d17fcca943dde69288726a669fd978f576957518142e24c5aa2e86c140",
    },
}

PREFINAL_EVIDENCE_DESTINATIONS = {
    "manifest.json": "evidence/R011-B008_PREFINAL_BACKEND_MANIFEST.json",
    "receipt": "evidence/R011-B008_PREFINAL_BACKEND_VALIDATION_RECEIPT.json",
}

g = pre.g
RECORD_PATHS = pre.RECORD_PATHS


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def identity(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {"bytes": len(raw), "sha256": sha256_bytes(raw)}


def require_identity(relative: str, expected: dict[str, Any]) -> bytes:
    path = LANE / relative
    if not path.is_file():
        raise RuntimeError(f"missing exact final-V3 input: {relative}")
    raw = path.read_bytes()
    observed = {"bytes": len(raw), "sha256": sha256_bytes(raw)}
    wanted = {"bytes": expected["bytes"], "sha256": expected["sha256"]}
    if observed != wanted:
        raise RuntimeError(f"final-V3 input changed: {relative}: {observed}")
    return raw


def frecord(record_type: str, stable_key: str, **fields: Any) -> dict[str, Any]:
    fields["recorded_at"] = RECORDED_AT
    fields["workflow_id"] = WORKFLOW_ID
    return g.record(record_type, stable_key, **fields)


def load_jsonl(raw: bytes) -> list[dict[str, Any]]:
    return [json.loads(line) for line in raw.decode("utf-8").splitlines() if line]


def one_by_key(records: dict[str, list[dict[str, Any]]], name: str, key: str) -> dict[str, Any]:
    matches = [row for row in records[name] if row["stable_key"] == key]
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one {name} record: {key}")
    return matches[0]


def parse_source_manifest(raw: bytes) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for line_number, line in enumerate(raw.decode("utf-8").splitlines(), 1):
        parts = line.split("\t")
        if len(parts) != 3:
            raise RuntimeError(f"malformed V3 source manifest line {line_number}")
        path, byte_text, digest = parts
        if path in rows or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise RuntimeError(f"invalid V3 source manifest identity at line {line_number}")
        rows[path] = {"bytes": int(byte_text), "sha256": digest}
    if len(rows) != 1206:
        raise RuntimeError(f"V3 source manifest count changed: {len(rows)}")
    for path, expected in FINAL_SOURCE_MEMBERS.items():
        if rows.get(path) != expected:
            raise RuntimeError(f"final source member changed in V3 manifest: {path}")
        snapshot_path = LANE / "qa" / "b008-build" / "source-snapshot-v3" / path
        if identity(snapshot_path) != expected:
            raise RuntimeError(f"final source snapshot member changed: {path}")
    return rows


def validate_final_inputs(raws: dict[str, bytes]) -> dict[str, Any]:
    manifest_rows = parse_source_manifest(
        raws["qa/b008-source/R011-B008_SOURCE_MANIFEST_V3.tsv"]
    )
    source_qa = json.loads(raws["qa/b008-source/R011-B008_SOURCE_QA_V3.json"])
    build_qa = json.loads(raws["qa/b008-build/final-v3/CANDIDATE_BUILD_QA_V3.json"])
    build_visual = json.loads(raws["qa/b008-build/BUILD_ONLY_VISUAL_SANITY_V3.json"])
    root_visual = json.loads(raws["qa/b008-visual/R011-B008_VISUAL_AUDIT_V3.json"])

    source_manifest_identity = {
        "path": "qa/b008-source/R011-B008_SOURCE_MANIFEST_V3.tsv",
        "bytes": FINAL_V3_INPUTS["qa/b008-source/R011-B008_SOURCE_MANIFEST_V3.tsv"]["bytes"],
        "sha256": FINAL_V3_INPUTS["qa/b008-source/R011-B008_SOURCE_MANIFEST_V3.tsv"]["sha256"],
    }
    source_qa_identity = {
        "path": "qa/b008-source/R011-B008_SOURCE_QA_V3.json",
        "bytes": FINAL_V3_INPUTS["qa/b008-source/R011-B008_SOURCE_QA_V3.json"]["bytes"],
        "sha256": FINAL_V3_INPUTS["qa/b008-source/R011-B008_SOURCE_QA_V3.json"]["sha256"],
    }
    pdf_identity = {
        "path": "qa/b008-build/final-v3/main.pdf",
        "bytes": FINAL_V3_INPUTS["qa/b008-build/final-v3/main.pdf"]["bytes"],
        "sha256": FINAL_V3_INPUTS["qa/b008-build/final-v3/main.pdf"]["sha256"],
    }

    if (
        source_qa.get("boundary_id") != BOUNDARY_ID
        or source_qa.get("status") != "PASS_PAGE_FILL_REPAIRED_SOURCE_CLOSURE"
        or source_qa.get("checks") != {"blockers": [], "failed": 0, "passed": 30}
        or source_qa.get("source_closure", {}).get("manifest") != source_manifest_identity
        or source_qa.get("source_closure", {}).get("files") != 1206
        or source_qa.get("source_closure", {}).get("unchanged_files_exact") != 1205
        or source_qa.get("source_closure", {}).get("changed_files")
        != ["ch_summarizing_data/TeX/review_exercises.tex"]
    ):
        raise RuntimeError("V3 source QA is not the accepted exact source closure")

    if (
        build_qa.get("boundary_id") != BOUNDARY_ID
        or build_qa.get("candidate_artifact")
        != {**pdf_identity, "promoted": False}
        or build_qa.get("determinism", {}).get("byte_identical") is not True
        or build_qa.get("determinism", {}).get("pass_3", {}).get("sha256")
        != pdf_identity["sha256"]
        or build_qa.get("determinism", {}).get("pass_4", {}).get("sha256")
        != pdf_identity["sha256"]
        or build_qa.get("nonvisual_status") != "passed"
        or build_qa.get("source_closure", {}).get("independent_v3_source_gate", {}).get("source_manifest")
        != source_manifest_identity
        or build_qa.get("source_closure", {}).get("independent_v3_source_gate", {}).get("source_qa")
        != source_qa_identity
    ):
        raise RuntimeError("V3 deterministic build receipt does not bind the accepted source/PDF")

    if (
        build_visual.get("boundary_id") != BOUNDARY_ID
        or build_visual.get("candidate_pdf") != pdf_identity
        or build_visual.get("inspection", {}).get("result") != "PASS"
        or build_visual.get("inspection", {}).get("pages") != [78, 79, 80, 81, 82, 388, 389, 390, 391]
        or build_visual.get("promotion_or_admission_performed") is not False
        or build_visual.get("repo_or_output_mutated") is not False
    ):
        raise RuntimeError("V3 independent build visual record is not an exact nonpromoting pass")

    build_receipt_identity = {
        "path": "qa/b008-build/final-v3/CANDIDATE_BUILD_QA_V3.json",
        "bytes": FINAL_V3_INPUTS["qa/b008-build/final-v3/CANDIDATE_BUILD_QA_V3.json"]["bytes"],
        "sha256": FINAL_V3_INPUTS["qa/b008-build/final-v3/CANDIDATE_BUILD_QA_V3.json"]["sha256"],
    }
    build_visual_identity = {
        "path": "qa/b008-build/BUILD_ONLY_VISUAL_SANITY_V3.json",
        "bytes": FINAL_V3_INPUTS["qa/b008-build/BUILD_ONLY_VISUAL_SANITY_V3.json"]["bytes"],
        "sha256": FINAL_V3_INPUTS["qa/b008-build/BUILD_ONLY_VISUAL_SANITY_V3.json"]["sha256"],
    }
    if (
        root_visual.get("boundary_id") != BOUNDARY_ID
        or root_visual.get("verdict") != "PASS"
        or root_visual.get("visual_gate_passed") is not True
        or root_visual.get("promotion_authorized_by_visual_gate") is not True
        or root_visual.get("severity_counts") != {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
        or root_visual.get("candidate")
        != {
            **pdf_identity,
            "pages": 425,
            "build_receipt": build_receipt_identity,
            "independent_build_visual_record": build_visual_identity,
        }
    ):
        raise RuntimeError("V3 root visual audit does not close the exact PDF/build identities")

    return {
        "manifest_rows": manifest_rows,
        "source_qa": source_qa,
        "build_qa": build_qa,
        "build_visual": build_visual,
        "root_visual": root_visual,
        "source_manifest_identity": source_manifest_identity,
        "source_qa_identity": source_qa_identity,
        "pdf_identity": pdf_identity,
        "build_receipt_identity": build_receipt_identity,
        "build_visual_identity": build_visual_identity,
    }


def load_prefinal() -> tuple[dict[str, list[dict[str, Any]]], dict[str, bytes], dict[str, Any], bytes, bytes]:
    for relative, expected in PREFINAL_TOOL_IDENTITIES.items():
        require_identity(relative, expected)

    expected_payloads = pre.build_payloads(None)
    manifest_raw = expected_payloads["manifest.json"]
    if {"bytes": len(manifest_raw), "sha256": sha256_bytes(manifest_raw)} != PREFINAL_MANIFEST_IDENTITY:
        raise RuntimeError("prefinal B008 manifest identity changed in deterministic regeneration")
    for relative, raw in expected_payloads.items():
        path = PREFINAL_EXPORTS / relative
        if not path.is_file() or path.read_bytes() != raw:
            raise RuntimeError(f"prefinal B008 stage changed: {relative}")
    stage_files = sorted(path.relative_to(PREFINAL_EXPORTS).as_posix() for path in PREFINAL_EXPORTS.rglob("*") if path.is_file())
    if stage_files != sorted(expected_payloads):
        raise RuntimeError("prefinal B008 stage contains a missing or stale payload")

    receipt_raw = PREFINAL_RECEIPT_PATH.read_bytes()
    if {"bytes": len(receipt_raw), "sha256": sha256_bytes(receipt_raw)} != PREFINAL_RECEIPT_IDENTITY:
        raise RuntimeError("prefinal B008 validator receipt identity changed")
    receipt = json.loads(receipt_raw)
    if (
        receipt.get("status") != "passed_isolated_source_backend_awaiting_final_v2"
        or receipt.get("record_count") != PREFINAL_RECORD_COUNT
        or receipt.get("base_records_preserved_exact") is not True
    ):
        raise RuntimeError("prefinal B008 receipt semantics changed")

    records = {name: load_jsonl(expected_payloads[relative]) for name, relative in RECORD_PATHS.items()}
    if sum(len(rows) for rows in records.values()) != PREFINAL_RECORD_COUNT:
        raise RuntimeError("prefinal B008 record count changed")

    derived = set(RECORD_PATHS.values()) | {"identity_map.jsonl", "manifest.json"}
    derived.update(path for path in expected_payloads if path.startswith("views/"))
    auxiliary = {path: raw for path, raw in expected_payloads.items() if path not in derived}
    return records, auxiliary, json.loads(manifest_raw), manifest_raw, receipt_raw


def add_relation(
    records: dict[str, list[dict[str, Any]]],
    suffix: str,
    relation_type: str,
    from_id: str,
    to_id: str,
    order: int,
    qualifier: str,
) -> str:
    key = f"r011/relation/b008-final-v3-{suffix}"
    row = frecord(
        "relation",
        key,
        relation_type=relation_type,
        from_id=from_id,
        to_id=to_id,
        qualifier=qualifier,
        order=order,
        resource_id=g.stable_id("r011/resource/openintro-statistics"),
        edition_id=g.stable_id("r011/edition/fee25091"),
        source_local_ids=[BOUNDARY_ID, "FINAL-V3"],
        parent_id=None,
        locale="zxx",
        translation_state="structurally_verified",
        rights_component_ids=[],
        boundary_id=BOUNDARY_ID,
        source_path=None,
        source_span=None,
        source_sha256=None,
    )
    records["relations"].append(row)
    return row["id"]


def build_records() -> tuple[dict[str, list[dict[str, Any]]], dict[str, bytes], dict[str, Any]]:
    records, auxiliary, prefinal_manifest, prefinal_manifest_raw, prefinal_receipt_raw = load_prefinal()
    records = deepcopy(records)
    auxiliary = dict(auxiliary)
    raws = {path: require_identity(path, expected) for path, expected in FINAL_V3_INPUTS.items()}
    final_context = validate_final_inputs(raws)

    auxiliary[PREFINAL_EVIDENCE_DESTINATIONS["manifest.json"]] = prefinal_manifest_raw
    auxiliary[PREFINAL_EVIDENCE_DESTINATIONS["receipt"]] = prefinal_receipt_raw
    for source, expected in FINAL_V3_INPUTS.items():
        destination = expected["destination"]
        if destination is not None:
            auxiliary[destination] = raws[source]

    resource_id = g.stable_id("r011/resource/openintro-statistics")
    edition_id = g.stable_id("r011/edition/fee25091")
    chapter_id = one_by_key(records, "units", "r011/unit/source-label/ch_summarizing_data")["id"]
    upstream_rights_id = one_by_key(records, "rights", "r011/rights/upstream-cc-by-sa-3.0")["id"]
    figure_rights_id = one_by_key(records, "rights", "r011/rights/b008-localized-figure-derivatives")["id"]
    data_rights_id = one_by_key(records, "rights", "r011/rights/b008-factual-data-limits")["id"]
    old_gate = one_by_key(records, "qa_events", "r011/qa/b008-final-v2-binding")

    artifact_order = max(int(row.get("order") or 0) for row in records["artifacts"])
    artifact_ids: dict[str, str] = {}

    artifact_specs = [
        (
            "prefinal-backend-manifest",
            "prefinal_backend_manifest",
            f"qa/b008-backend-final-v3/exports/{PREFINAL_EVIDENCE_DESTINATIONS['manifest.json']}",
            PREFINAL_MANIFEST_IDENTITY,
            "structurally_verified",
            [],
            "Exact immutable source-stage manifest extended by this final-V3 stage.",
        ),
        (
            "prefinal-backend-receipt",
            "prefinal_backend_validation_receipt",
            f"qa/b008-backend-final-v3/exports/{PREFINAL_EVIDENCE_DESTINATIONS['receipt']}",
            PREFINAL_RECEIPT_IDENTITY,
            "structurally_verified",
            [],
            "Exact immutable source-stage validation receipt.",
        ),
    ]
    for source, expected in FINAL_V3_INPUTS.items():
        slug = {
            "qa/b008-source/R011-B008_SOURCE_MANIFEST_V3.tsv": "source-manifest",
            "qa/b008-source/R011-B008_SOURCE_QA_V3.json": "source-qa",
            "qa/b008-build/final-v3/main.pdf": "pdf",
            "qa/b008-build/final-v3/CANDIDATE_BUILD_QA_V3.json": "build-qa",
            "qa/b008-build/BUILD_ONLY_VISUAL_SANITY_V3.json": "build-visual",
            "qa/b008-visual/R011-B008_VISUAL_AUDIT_V3.json": "root-visual",
        }[source]
        path = source if expected["destination"] is None else f"qa/b008-backend-final-v3/exports/{expected['destination']}"
        rights = [upstream_rights_id, figure_rights_id, data_rights_id] if slug == "pdf" else []
        artifact_specs.append(
            (
                slug,
                expected["artifact_kind"],
                path,
                {"bytes": expected["bytes"], "sha256": expected["sha256"]},
                expected["translation_state"],
                rights,
                "Exact terminal-V3 source/build/visual binding; no admission or promotion performed.",
            )
        )

    for slug, source_member in [("review-source", "ch_summarizing_data/TeX/review_exercises.tex"), ("answer-source", "extraTeX/eoceSolutions/eoceSolutions.tex")]:
        artifact_specs.append(
            (
                slug,
                "final_v3_localized_source_member",
                f"qa/b008-build/source-snapshot-v3/{source_member}",
                FINAL_SOURCE_MEMBERS[source_member],
                "source_frozen",
                [upstream_rights_id],
                "Exact member of the 1,206-file V3 source closure.",
            )
        )

    for slug, path, kind in [
        ("generator", SCRIPT_PATH, "backend_final_v3_generator"),
        ("finalizer", FINALIZER_PATH, "backend_final_v3_writer"),
        ("validator", VALIDATOR_PATH, "backend_final_v3_validator"),
    ]:
        if not path.is_file():
            raise RuntimeError(f"terminal-V3 backend tooling missing: {path.name}")
        artifact_specs.append(
            (
                slug,
                kind,
                path.relative_to(LANE).as_posix(),
                identity(path),
                "structurally_verified",
                [],
                "Exact deterministic Python 3 standard-library tool identity.",
            )
        )

    for index, (slug, kind, path, item_identity, state, rights, result) in enumerate(artifact_specs, 1):
        key = f"r011/artifact/b008-final-v3-{slug}"
        row = frecord(
            "artifact",
            key,
            artifact_kind=kind,
            path=path,
            bytes=item_identity["bytes"],
            sha256=item_identity["sha256"],
            result=result,
            resource_id=resource_id,
            edition_id=edition_id,
            source_local_ids=[BOUNDARY_ID, "FINAL-V3"],
            parent_id=edition_id,
            order=artifact_order + index,
            locale="id-ID" if slug in {"pdf", "review-source", "answer-source"} else "zxx",
            translation_state=state,
            rights_component_ids=rights,
            boundary_id=BOUNDARY_ID,
            source_path=None,
            source_span=None,
            source_sha256=None,
            status="passed",
            page_count=425 if slug == "pdf" else None,
            document_language="id-ID" if slug == "pdf" else None,
            provenance=PROVENANCE,
            promoted=False if slug == "pdf" else None,
        )
        records["artifacts"].append(row)
        artifact_ids[slug] = row["id"]

    qa_order = max(int(row.get("order") or 0) for row in records["qa_events"])
    qa_specs = [
        (
            "source-closure",
            "source",
            chapter_id,
            f"qa/b008-backend-final-v3/exports/{FINAL_V3_INPUTS['qa/b008-source/R011-B008_SOURCE_QA_V3.json']['destination']}",
            "The 1,206-file V3 source manifest passes 30/30 checks; only the review-exercise layout member changed from V2.",
            "source-qa",
        ),
        (
            "deterministic-build",
            "build",
            artifact_ids["pdf"],
            f"qa/b008-backend-final-v3/exports/{FINAL_V3_INPUTS['qa/b008-build/final-v3/CANDIDATE_BUILD_QA_V3.json']['destination']}",
            "Passes 3 and 4 are byte-identical at the exact 22,017,328-byte V3 PDF identity; its historical pending visual item is closed by the root audit.",
            "build-qa",
        ),
        (
            "build-visual-sanity",
            "visual",
            artifact_ids["pdf"],
            f"qa/b008-backend-final-v3/exports/{FINAL_V3_INPUTS['qa/b008-build/BUILD_ONLY_VISUAL_SANITY_V3.json']['destination']}",
            "All nine full-resolution scope pages pass the independent build-lane visual inspection with no clipping, overlap, or unreadable glyphs.",
            "build-visual",
        ),
        (
            "root-visual-audit",
            "visual",
            artifact_ids["pdf"],
            f"qa/b008-backend-final-v3/exports/{FINAL_V3_INPUTS['qa/b008-visual/R011-B008_VISUAL_AUDIT_V3.json']['destination']}",
            "The independent root audit records PASS, zero findings at every severity, and exact PDF/build/visual identities.",
            "root-visual",
        ),
        (
            "terminal-binding",
            "finalization",
            edition_id,
            f"qa/b008-backend-final-v3/exports/{FINAL_V3_INPUTS['qa/b008-visual/R011-B008_VISUAL_AUDIT_V3.json']['destination']}",
            "The obsolete unsupplied final-V2 parameter is superseded by the exact complete final-V3 source/PDF/build/visual closure; admission remains a separate transaction.",
            "root-visual",
        ),
    ]
    qa_ids: dict[str, str] = {}
    for index, (suffix, qa_type, subject_id, witness, detail, _artifact_slug) in enumerate(qa_specs, 1):
        key = f"r011/qa/b008-final-v3-{suffix}"
        row = frecord(
            "qa_event",
            key,
            qa_type=qa_type,
            result="passed",
            subject_id=subject_id,
            witness_path=witness,
            detail=detail,
            resource_id=resource_id,
            edition_id=edition_id,
            source_local_ids=[BOUNDARY_ID, "FINAL-V3"],
            parent_id=chapter_id if suffix == "source-closure" else edition_id,
            order=qa_order + index,
            locale="zxx",
            translation_state="visually_checked" if "visual" in suffix or suffix == "terminal-binding" else "structurally_verified",
            rights_component_ids=[],
            boundary_id=BOUNDARY_ID,
            source_path=None,
            source_span=None,
            source_sha256=None,
            status="passed",
            supersedes_id=old_gate["id"] if suffix == "terminal-binding" else None,
        )
        records["qa_events"].append(row)
        qa_ids[suffix] = row["id"]

    relation_specs = [
        ("prefinal-manifest-documents-edition", "documents", artifact_ids["prefinal-backend-manifest"], edition_id, "Preserves the exact immutable B008 source-stage manifest."),
        ("prefinal-receipt-validates-manifest", "validates", artifact_ids["prefinal-backend-receipt"], artifact_ids["prefinal-backend-manifest"], "Preserves the 22/22 source-stage validation receipt."),
        ("source-manifest-snapshots-edition", "snapshots", artifact_ids["source-manifest"], edition_id, "Exact 1,206-file terminal-V3 source closure."),
        ("review-source-in-manifest", "included_in", artifact_ids["review-source"], artifact_ids["source-manifest"], "Final page-fill review source member."),
        ("answer-source-in-manifest", "included_in", artifact_ids["answer-source"], artifact_ids["source-manifest"], "Exact public-answer source member."),
        ("source-qa-validates-manifest", "validates", artifact_ids["source-qa"], artifact_ids["source-manifest"], "Thirty source checks pass."),
        ("pdf-renders-edition", "renders", artifact_ids["pdf"], edition_id, "Deterministic 425-page id-ID candidate, not promoted."),
        ("build-qa-validates-pdf", "validates", artifact_ids["build-qa"], artifact_ids["pdf"], "Byte-identical pass-3/pass-4 build closure."),
        ("build-visual-validates-pdf", "validates", artifact_ids["build-visual"], artifact_ids["pdf"], "Independent nine-page full-resolution inspection."),
        ("root-visual-validates-pdf", "validates", artifact_ids["root-visual"], artifact_ids["pdf"], "Terminal independent visual PASS."),
        ("source-event-validates-manifest", "validates", qa_ids["source-closure"], artifact_ids["source-manifest"], "Typed terminal source QA event."),
        ("build-event-validates-pdf", "validates", qa_ids["deterministic-build"], artifact_ids["pdf"], "Typed deterministic build QA event."),
        ("terminal-event-validates-edition", "validates", qa_ids["terminal-binding"], edition_id, "Complete final-V3 binding without admission."),
    ]
    for index, (suffix, relation_type, from_id, to_id, qualifier) in enumerate(relation_specs, 1):
        add_relation(records, suffix, relation_type, from_id, to_id, index, qualifier)

    return records, auxiliary, {
        "prefinal_manifest": prefinal_manifest,
        "final_context": final_context,
        "artifact_ids": artifact_ids,
        "qa_ids": qa_ids,
        "old_gate_id": old_gate["id"],
        "resource_id": resource_id,
        "edition_id": edition_id,
        "chapter_id": chapter_id,
    }


def payload_record_count(path: str, raw: bytes) -> int | None:
    if path.endswith(".jsonl"):
        return len([line for line in raw.splitlines() if line])
    if path.endswith(".csv") or path.endswith(".tsv"):
        return max(0, len(raw.splitlines()) - 1)
    if path.endswith(".json"):
        return 1
    return None


def build_payloads() -> dict[str, bytes]:
    records, auxiliary, context = build_records()
    payloads = {relative: g.jsonl_bytes(records[name]) for name, relative in RECORD_PATHS.items()}
    all_records = [row for rows in records.values() for row in rows]
    payloads["identity_map.jsonl"] = g.jsonl_bytes(
        {
            "id": row["id"],
            "record_type": row["record_type"],
            "stable_key": row["stable_key"],
            "source_local_ids": row.get("source_local_ids", []),
        }
        for row in all_records
    )
    view_schema = json.loads(auxiliary["schemas/backend-view-columns-v0.1.0.json"])
    payloads.update(g.build_views(records, view_schema["views"]))
    payloads.update(auxiliary)

    prefinal_counts = context["prefinal_manifest"]["record_counts"]
    record_counts = {name: len(rows) for name, rows in sorted(records.items())}
    new_counts = {name: record_counts[name] - prefinal_counts[name] for name in sorted(record_counts)}
    final_v3_inputs = {
        path: {"bytes": item["bytes"], "sha256": item["sha256"]}
        for path, item in FINAL_V3_INPUTS.items()
    }
    manifest = {
        "$schema": "r011-backend-manifest/v0.1.0",
        "schema_version": SCHEMA_VERSION,
        "namespace_uuid": str(g.NAMESPACE),
        "backend_id": "r011-openintro-statistics-id-b008-final-v3-isolated",
        "workflow_id": WORKFLOW_ID,
        "recorded_at": RECORDED_AT,
        "scope": "Terminal V3 closure for R011-B008 over the immutable 2,472-record prefinal B008 source stage; no live admission, promotion, or publication.",
        "authority": context["prefinal_manifest"]["authority"],
        "asset_authority": context["prefinal_manifest"]["asset_authority"],
        "canonicalization": context["prefinal_manifest"]["canonicalization"],
        "base_preservation": {
            "admitted_base_boundary": BASE_BOUNDARY_ID,
            "admitted_base_record_count": BASE_RECORD_COUNT,
            "prefinal_boundary": BOUNDARY_ID,
            "prefinal_record_count": PREFINAL_RECORD_COUNT,
            "prefinal_stage_path": "qa/b008-backend/exports",
            "prefinal_manifest": {"path": "qa/b008-backend/exports/manifest.json", **PREFINAL_MANIFEST_IDENTITY},
            "prefinal_validation_receipt": {"path": "qa/b008-backend/BACKEND_VALIDATION_RECEIPT_R011-B008.json", **PREFINAL_RECEIPT_IDENTITY},
            "policy": "All 2,472 prefinal records are preserved byte-semantically; the earlier B008 stage and all B007 live backend/evidence remain untouched.",
        },
        "source_application": context["prefinal_manifest"]["source_application"],
        "terminology": context["prefinal_manifest"]["terminology"],
        "record_counts": record_counts,
        "prefinal_record_counts": prefinal_counts,
        "new_final_v3_record_counts": new_counts,
        "new_final_v3_record_count": sum(new_counts.values()),
        "cumulative_b008_added_over_b007": sum(record_counts.values()) - BASE_RECORD_COUNT,
        "final_v3_binding": {
            "status": "complete_exact_terminal_v3",
            "inputs": final_v3_inputs,
            "source_member_identities": FINAL_SOURCE_MEMBERS,
            "source_file_count": 1206,
            "pdf_page_count": 425,
            "deterministic_pdf_passes_identical": True,
            "root_visual_verdict": "PASS",
            "root_visual_severity_counts": {"P0": 0, "P1": 0, "P2": 0, "P3": 0},
            "records_emitted": True,
        },
        "prefinal_gate_resolution": {
            "obsolete_gate_stable_key": "r011/qa/b008-final-v2-binding",
            "obsolete_gate_id": context["old_gate_id"],
            "superseding_event_stable_key": "r011/qa/b008-final-v3-terminal-binding",
            "superseding_event_id": context["qa_ids"]["terminal-binding"],
            "resolution": "exact final-V3 source/PDF/build/visual closure supplied and validated",
        },
        "stage_state": {
            "status": "isolated_terminal_v3_backend_generated",
            "final_v3_bound": True,
            "prefinal_stage_mutated": False,
            "live_backend_mutated": False,
            "canonical_source_mutated_by_backend_tools": False,
            "output_or_release_mutated": False,
            "boundary_admitted": False,
            "promotion_performed": False,
            "publication_performed": False,
        },
        "admission_eligibility": "ready_for_separate_guarded_admission_transaction",
        "deferred_actions": [
            "guarded admission into the live backend",
            "canonical artifact promotion",
            "publication and anonymous public-byte readback",
        ],
        "placeholder_count": 0,
        "known_limitations": [
            "The historical prefinal blocked final-V2 event is retained immutably and superseded rather than rewritten.",
            "The V3 build receipt truthfully records that visual review was pending at build time; the later exact root visual audit closes that item with PASS.",
            "No restricted instructor solution was accessed or reconstructed; O001 gaps 2.28, 2.30, 2.32, and 2.34 remain explicit.",
            "No admission, promotion, publication, Git operation, or upstream contact is represented or claimed.",
        ],
        "provenance": PROVENANCE,
        "files": [],
    }
    for relative in sorted(payloads):
        raw = payloads[relative]
        manifest["files"].append(
            {
                "path": relative,
                "bytes": len(raw),
                "sha256": sha256_bytes(raw),
                "records": payload_record_count(relative, raw),
            }
        )
    payloads["manifest.json"] = (g.canonical_json(manifest) + "\n").encode("utf-8")
    return payloads


if __name__ == "__main__":
    payloads = build_payloads()
    manifest = json.loads(payloads["manifest.json"])
    print(
        g.canonical_json(
            {
                "boundary_id": BOUNDARY_ID,
                "result": "PASS_FINAL_V3_PAYLOADS_GENERATED_IN_MEMORY",
                "payload_count": len(payloads),
                "record_count": sum(manifest["record_counts"].values()),
                "new_final_v3_record_count": manifest["new_final_v3_record_count"],
                "stage_written": False,
                "live_backend_mutated": False,
            }
        )
    )
