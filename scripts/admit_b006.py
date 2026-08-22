#!/usr/bin/env python3
"""Fail-closed admission and promotion guard for R011-B006.

The fixed source/repair/asset closure is frozen below.  Final-v4-or-later build,
operator-approved visual, and generated-backend identities intentionally remain
unset until the main agent supplies their exact byte identities.  In that
state this program performs every available read-only check and refuses both
promotion and admission.

Modes are deliberately separate:

* the default is read-only and never changes a file;
* ``--promote`` may copy an already validated final PDF and staged backend to
  their canonical live destinations, but never writes the boundary receipt;
* ``--write`` may write the deterministic boundary receipt, but only after the
  canonical PDF and live backend already read back byte-for-byte exact;
* ``--self-test`` exercises pure fail-closed/adversarial helpers without
  touching corpus state.

This program never builds, mutates source/control/backend records, invokes Git,
publishes, contacts upstream, deletes files, or accepts the rejected v1/v2/v3
builds.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import tempfile
import unicodedata
import uuid
from pathlib import Path
from typing import Any, Iterable


LANE = Path(__file__).resolve().parents[1]
REPO = LANE / "repo"
QA = LANE / "qa"
STAGE_EXPORTS = QA / "b006-backend" / "exports"
LIVE_EXPORTS = LANE / "backend" / "exports"
BACKEND_SCHEMAS = LANE / "backend" / "schemas"
OUTPUT = QA / "BOUNDARY_RECEIPT_R011-B006.json"
ADMISSION_DATE = "2026-08-22"

AUTHORITY_REPOSITORY = "https://github.com/OpenIntroStat/openintro-statistics"
AUTHORITY_COMMIT = "fee25091fb24e89c36296fd67c48c1fcf7a93b6e"
AUTHORITY_TREE = "d61cc601e7d97759ce805900520f784d02a0489e"
BACKEND_NAMESPACE = uuid.UUID("3f5320fb-d2a2-4aa6-a8fe-298715378407")

BASE_RECORD_COUNT = 1618
B005_LIVE_INVENTORY_SHA256 = (
    "506a2fded15cbb36e919f3610d6dd6706471246866aa9aca53122b3362d68438"
)
B005_LIVE_INVENTORY_FILE_COUNT = 48
B005_LIVE_INVENTORY_BYTES = 3868354
EXPECTED_EXERCISES = ["2.21", "2.22", "2.23", "2.24"]
EXPECTED_PUBLIC_ANSWERS = ["2.21", "2.23"]
EXPECTED_O001_GAPS = ["2.22", "2.24"]
ZERO_SEVERITY = {"P1": 0, "P2": 0, "P3": 0}
ZERO_VISUAL_SEVERITY = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
REJECTED_V1_PDF_SHA256 = (
    "d52a180d68f85bc077982c187a7b0c8f3c33a6ad8f230641e31e52c57ce999d7"
)
REJECTED_V2_PDF_SHA256 = (
    "22fc488fe22e60cf413920f8553dd71ebd7db15dc04e2e78e90b18f61b12bc2f"
)
REJECTED_V3_PDF_SHA256 = (
    "7fb77cd62425d4237f35e24791d1206f6eec704fc40b50d4a7159953f2647cab"
)

V3_SOURCE_QA_IDENTITY = {
    "path": "qa/R011-B006_SOURCE_QA.json",
    "bytes": 42133,
    "sha256": "8bcec78a0d385219715756bb595b80936d39e0f4bfd64e208038d4989781a11e",
}
V3_TARGET_MANIFEST_IDENTITY = {
    "path": "qa/R011-B006_TARGET_MANIFEST.tsv",
    "bytes": 173738,
    "sha256": "f4e717e06956a4f1633164f3d6711d414d06c4bf5f9c736a8f89e1ecb6e952da",
}
V3_CANONICAL_OUTPUTS = [
    {
        "path": "repo/ch_summarizing_data/TeX/ch_summarizing_data.tex",
        "bytes": 114091,
        "sha256": "3a087003f4bcb01268090fc2a04a8c40f9b46da7ff5a5f276a591a9d266e7a9c",
    },
    {
        "path": "repo/ch_summarizing_data/TeX/considering_categorical_data.tex",
        "bytes": 6658,
        "sha256": "2e56b476d8e96e0db30395e40fbe129b0d08739b6292373778d647f529f6d143",
    },
    {
        "path": "repo/extraTeX/eoceSolutions/eoceSolutions.tex",
        "bytes": 107940,
        "sha256": "49ad90a6c041ec23cfb99ce5f0a1ece6bf45516cc82eabbe02474c1604749b43",
    },
]
V3_CANDIDATE_BUILD_IDENTITY = {
    "path": "qa/b006-build/final-v3/CANDIDATE_BUILD_QA_V3.json",
    "bytes": 14938,
    "sha256": "c78aa1ea63ff4795df681ebcc6ecd5776b941104bffd4835bf981d46d62028a8",
}


FIXED_EXPECTED: dict[str, tuple[str, int, str]] = {
    "prior_boundary_receipt": (
        "qa/BOUNDARY_RECEIPT_R011-B005.json",
        17758,
        "4d5618ccc28cf9c58d1f0f4c04a22d89946e824f31984a350f47558b0a24e70f",
    ),
    "prior_target_manifest": (
        "qa/R011-B005_TARGET_MANIFEST.tsv",
        171577,
        "8e84e688c354757b52b081a0d79f848a6f9e651c339760f92cf3f123eabb6fe0",
    ),
    "source_qa": (
        "qa/R011-B006_SOURCE_QA.json",
        51559,
        "524852f1e21939d8a0ced8ab5d79f1a74d0bbf552ca06f0ce252082f30a4c918",
    ),
    "target_manifest": (
        "qa/R011-B006_TARGET_MANIFEST.tsv",
        173738,
        "bdf80b178094d903305c8d5539d969db39502720bbe0e0d5e3735ca92e8a05f4",
    ),
    "source_gate_script": (
        "scripts/qa_boundary_b006.py",
        154974,
        "3a6e168dd7bcbf47ef6203e06f251f52d6dee246161458e156e3d043e371efcb",
    ),
    "preapplication": (
        "qa/R011-B006_PREAPPLICATION_MANIFEST.json",
        3983,
        "d6e832dc0519892bf29cb94672c7210b4886425666b36947f42883d355e73965",
    ),
    "source_application": (
        "qa/R011-B006_SOURCE_APPLICATION_RECEIPT.json",
        9586,
        "56d69a600cf4ad1bb18ede91b588266fba4e1f10f8356ba67ec96103d3a84286",
    ),
    "repair_receipt": (
        "qa/R011-B006_REPAIR_RECEIPT.json",
        12510,
        "145f3b47954a03999d3695e2dbd3206717dd89af76ea8aaad63974e431321492",
    ),
    "layout_repair_receipt_v3": (
        "qa/R011-B006_LAYOUT_REPAIR_RECEIPT_V3.json",
        11120,
        "fd3e6048d0e68b6e6287463f7d85f686a33f0770f59bb1c3d5cdd9445e6b59be",
    ),
    "layout_repair_receipt_v4": (
        "qa/R011-B006_LAYOUT_REPAIR_RECEIPT_V4.json",
        9800,
        "e969de593a0504cdeba1ca5fa8e9c76e096b2c4a5d64d0d90f466845df12d3e9",
    ),
    "rejected_build_v1": (
        "qa/R011-B006_BUILD_QA_V1_REJECTED.json",
        15819,
        "e649a2cbe71f4041b0684f8764b7297a5cbcbac4c8c78ed412a2e0b297806e16",
    ),
    "rejected_visual_v1": (
        "qa/R011-B006_VISUAL_FINDINGS_V1.json",
        2013,
        "cc4adb506a84b231d2d0988ee024dd673e2ae3b70cca9d7b9924333e8d923231",
    ),
    "rejected_build_v2": (
        "qa/R011-B006_BUILD_QA_V2_REJECTED.json",
        2066,
        "9792c0fc177e652889575c7ffdfcbbe503fbabca08e53224a8c52f39c42c7188",
    ),
    "rejected_visual_v2": (
        "qa/R011-B006_VISUAL_FINDINGS_V2.json",
        2396,
        "6221077b007c1357e4524fdefc1719cd4beedeea4a363d5919e012a7ceea950c",
    ),
    "rejected_build_v3": (
        "qa/R011-B006_BUILD_QA_V3_REJECTED.json",
        2408,
        "717e987c26fb76783ba612563790faed06f16791ba2edb369022eedb0ac7a5d9",
    ),
    "rejected_visual_v3": (
        "qa/R011-B006_VISUAL_FINDINGS_V3.json",
        2150,
        "4126d7612063aa9497bdaaa1d0526087160ed266398c223dffbf31042d3585b3",
    ),
    "source_snapshot_v1": (
        "qa/b006-build/SNAPSHOT_RECEIPT_V1.json",
        1126,
        "8b98ca44a40afeaac80fb9ae45c01307ec145530267404790b923992a61d89c7",
    ),
    "asset_manifest": (
        "qa/b006-assets/ASSET_MANIFEST_R011-B006.json",
        20602,
        "12df13ae4eeac43f492ec77efbe96d8470ffda0aeaf0c16265c879f4f1fb41ac",
    ),
    "asset_receipt": (
        "qa/b006-assets/ASSET_VALIDATION_RECEIPT_R011-B006.json",
        8001,
        "3c9843944b53e7791fc0998f625dc31d6adcc63250fca4fe9d34f4cd1bcd4582",
    ),
    "asset_poppler_contact": (
        "qa/b006-assets/B006_ASSET_POPPLER_SOURCE_TARGET_CONTACT_SHEET.png",
        1349643,
        "56b55ada23a7516c04992ec3ff14a7599011569ffa028cae513be5f14cbc8047",
    ),
    "asset_mupdf_contact": (
        "qa/b006-assets/B006_ASSET_MUPDF_SOURCE_TARGET_CONTACT_SHEET.png",
        1374921,
        "221a3dd6513f7cb94a042d1240c7ec062247a1e0c5685f71be1eb4d1ed6b9063",
    ),
    "asset_localizer": (
        "scripts/localize_b006_figures.py",
        20207,
        "12071f770b73440a98722a430cc09d046465e2469d7956bfc08b4e618913f6b4",
    ),
    "component_rights": (
        "00_control/COMPONENT_RIGHTS.csv",
        9999,
        "009feba8ff1f329ef742793f55f6b090dd08f3f761f9b9cc1edcbe03ecff58f0",
    ),
    "terminology": (
        "00_control/TERMINOLOGY.csv",
        11279,
        "622fa65372875784cb190619175750bcfbfa9600bcc4526f521019c39f093f7e",
    ),
    "adverse": (
        "00_control/ADVERSE_LEDGER.jsonl",
        36030,
        "04032e0f4486268d99d809333779fd450d4062d376149ca0945f34e24f8af7c3",
    ),
    "body": (
        "repo/ch_summarizing_data/TeX/ch_summarizing_data.tex",
        114091,
        "3a087003f4bcb01268090fc2a04a8c40f9b46da7ff5a5f276a591a9d266e7a9c",
    ),
    "exercises": (
        "repo/ch_summarizing_data/TeX/considering_categorical_data.tex",
        6644,
        "dd8f682d4188597869ec0e3bd873e04b0be3c6636de117788ff65101ba2241ab",
    ),
    "answers": (
        "repo/extraTeX/eoceSolutions/eoceSolutions.tex",
        107940,
        "49ad90a6c041ec23cfb99ce5f0a1ece6bf45516cc82eabbe02474c1604749b43",
    ),
    "backend_generator": (
        "scripts/generate_backend_b006.py",
        127899,
        "9ce44ac25138c868ece4a561b1c98d917bb6a702c3a0373cdc96ef536851395f",
    ),
    "backend_validator": (
        "scripts/validate_backend_b006.py",
        35688,
        "2875fe62f1437f3bc64edda1ee258f32a73c2461f75de75bae21689b817ec106",
    ),
    "visual_finalizer": (
        "scripts/qa_finalize_b006_visual_v4.py",
        16228,
        "15aed320dedf02d47b376e0b8be1860a8ff8221382bd976255b4a147fad442f1",
    ),
}


# FINAL_BINDINGS_REQUIRED: fill every ``None`` only from exact final-v4-or-later and
# backend handoffs after the main agent's visual approval.  No command in this
# script discovers and silently blesses these values.
FINAL_EXPECTED: dict[str, Any] = {
    "build_gate_script": {
        "path": "scripts/qa_build_b006.py",
        "bytes": 49624,
        "sha256": "201e90f21fe17ee27e64e8f3a7ce79d5f50ddbe1124d6886f086c373d6fe3795",
    },
    "candidate_build_qa": {
        "path": "qa/b006-build/final-v4/CANDIDATE_BUILD_QA_V4.json",
        "bytes": 15252,
        "sha256": "a33e9c184697bfce38938d6ab52843d57f6de592cf42abd37f3effd75a0c1fbc",
    },
    "build_qa": {
        "path": "qa/R011-B006_BUILD_QA_V4.json",
        "bytes": 16346,
        "sha256": "6d7dd115518c3c3d080d48c05e9e52bd89b8b477498fed909b1041295f19d618",
    },
    "build_log": {
        "path": "qa/b006-build/final-v4/main.log",
        "bytes": 494501,
        "sha256": "9ca2696c1ab5995c26e48699db6bd25c7db46ad915b7ac3007249f4d25348cd8",
    },
    "build_text": {
        "path": "qa/b006-build/final-v4/main-final.txt",
        "bytes": 1588179,
        "sha256": "92521604fcf9d2102463eb6847a41fa3cb35f563c14f556cdbf3b6bcd1981539",
    },
    "build_recorder": {
        "path": "qa/b006-build/final-v4/main.fls",
        "bytes": 280259,
        "sha256": "863a70b179c9e73646ea0b499ba3caf0bc2d197da8fdb56152133f722ed8d05a",
    },
    "pass3_pdf": {
        "path": "qa/b006-build/final-v4/main-pass3.pdf",
        "bytes": 21975722,
        "sha256": "d9a3df7d44a62babde04c355cb8dbb9edc74de947cc8162a3d30d872bea372b2",
    },
    "final_pdf": {
        "path": "qa/b006-build/final-v4/main.pdf",
        "bytes": 21975722,
        "sha256": "d9a3df7d44a62babde04c355cb8dbb9edc74de947cc8162a3d30d872bea372b2",
    },
    "render_manifest": {
        "path": "qa/b006-render/final-v4/FINAL_MANIFEST.tsv",
        "bytes": 1500,
        "sha256": "dd0a15cb79c3e4e3b5d89944d1fc275716d72732d8824fd4d3fe6c96fd413588",
    },
    "render_page_locator": {
        "path": "qa/b006-render/final-v4/PAGE_LOCATOR.json",
        "bytes": 1599,
        "sha256": "4d6721fd2441371b609e1961ec9b0255b263b90e93b96253bc90253dd23f1492",
    },
    "render_contact_sheet": {
        "path": "qa/b006-render/final-v4/CONTACT_SHEET.png",
        "bytes": 859627,
        "sha256": "313d69ae077a3d53389cd5b4a9064abe731a2996f05f612b9b7e79044b880fd7",
    },
    "visual_audit": {
        "path": "qa/R011-B006_VISUAL_AUDIT_V4.json",
        "bytes": 7747,
        "sha256": "749f1210fa3c760abc18c984a2e1cb519c43b455d54bebc2cb3b173f67602e2c",
    },
    "promoted_pdf": {
        "path": "output/pdf/statistika-berbasis-data-batas-R011-B006.pdf",
        "bytes": 21975722,
        "sha256": "d9a3df7d44a62babde04c355cb8dbb9edc74de947cc8162a3d30d872bea372b2",
    },
    "final_inputs": {
        "path": "qa/b006-backend/R011-B006_FINAL_GATE_INPUTS.json",
        "bytes": 2636,
        "sha256": "d5ada1fe959740672a0e83957579b08f39be62a44e61843bd11bf89ef27bc6db",
    },
    "backend_stage_receipt": {
        "path": "qa/b006-backend/BACKEND_VALIDATION_RECEIPT_R011-B006_STAGE.json",
        "bytes": 7452,
        "sha256": "b618f5883d0eae436b036b8a4342469203df4b354a8872721ac5a02946c42801",
    },
    "backend_stage_manifest": {
        "path": "qa/b006-backend/exports/manifest.json",
        "bytes": 23151,
        "sha256": "d2324e74bff4aa8c985c82a89317828150910f6369b821898a9b1bca33083d0b",
    },
    "page_count": 424,
    "rendered_page_count": 17,
    "backend_payload_count": 75,
    "backend_payload_bytes": 5932043,
    "backend_manifest_file_entry_count": 78,
    "backend_stage_inventory_sha256": "75a029c2892d0aba59f729e4c74f787938655025e3e9433bf5f6b50b1bbec78b",
    "backend_stage_inventory_file_count": 75,
    "backend_stage_inventory_bytes": 5932043,
    "backend_resolved_reference_count": 8647,
    "backend_authority_span_count": 60,
    "backend_localization_slice_count": 21,
    "backend_artifact_count": 27,
    "backend_validator_check_count": 28,
    "backend_record_count": 1969,
    "backend_added_record_count": 351,
    "backend_record_counts": {
        "artifacts": 97,
        "assets": 177,
        "concepts": 112,
        "corrections": 74,
        "courses": 1,
        "editions": 1,
        "localizations": 172,
        "programs": 1,
        "qa_events": 71,
        "relations": 767,
        "resources": 1,
        "rights": 22,
        "segments": 172,
        "terms": 112,
        "units": 189,
    },
    "backend_check_names": [
        "deterministic_generator_replay",
        "staged_payload_identity",
        "live_backend_immutability",
        "record_inventory",
        "admitted_b005_additive_preservation",
        "admitted_b005_evidence_preservation",
        "schema_envelope_and_stable_ids",
        "canonical_jsonl_serialization",
        "referential_integrity",
        "authority_span_hash_replay",
        "translation_overlay_round_trip",
        "revised_source_gate_identity_binding",
        "target_manifest_file_replay",
        "unit_hierarchy_inventory",
        "segment_inventory",
        "section_segment_nonoverlap_and_coverage",
        "exercise_answer_o001_topology",
        "terminology_concept_prerequisite_model",
        "correction_inventory_and_disposition",
        "bounded_controls_and_repair_evidence",
        "asset_code_data_rights_closure",
        "artifact_identity_replay",
        "final_build_pdf_visual_binding",
        "typed_qa_state",
        "csv_projection_round_trip",
        "identity_map_completeness",
        "manifest_schema_hashes_and_counts",
        "stage_only_no_placeholder_or_promotion",
    ],
}


BACKEND_RECORD_PATHS = {
    "programs": "core/programs.jsonl",
    "courses": "core/courses.jsonl",
    "resources": "core/resources.jsonl",
    "editions": "core/editions.jsonl",
    "units": "core/units.jsonl",
    "concepts": "core/concepts.jsonl",
    "segments": "core/segments.jsonl",
    "assets": "core/assets.jsonl",
    "relations": "core/relations.jsonl",
    "rights": "core/rights.jsonl",
    "corrections": "core/corrections.jsonl",
    "localizations": "locales/id-ID/localizations.jsonl",
    "terms": "locales/id-ID/terms.jsonl",
    "qa_events": "evidence/qa_events.jsonl",
    "artifacts": "evidence/artifacts.jsonl",
}

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def identity_bytes(data: bytes) -> dict[str, object]:
    return {"bytes": len(data), "sha256": sha256(data)}


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def lane_path(relative: str) -> Path:
    candidate = Path(relative)
    if not relative or candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"unsafe lane-relative path: {relative!r}")
    resolved = (LANE / candidate).resolve()
    if not resolved.is_relative_to(LANE.resolve()):
        raise ValueError(f"path escapes lane: {relative!r}")
    return resolved


def artifact_fixed(name: str) -> dict[str, object]:
    path, size, digest = FIXED_EXPECTED[name]
    return {"path": path, "bytes": size, "sha256": digest}


def expected_identity(name: str) -> dict[str, object]:
    value = FINAL_EXPECTED[name]
    if not isinstance(value, dict):
        raise TypeError(f"{name} is not an identity binding")
    return {
        "path": value["path"],
        "bytes": value["bytes"],
        "sha256": value["sha256"],
    }


def is_identity_binding(value: object) -> bool:
    return isinstance(value, dict) and set(value) == {"path", "bytes", "sha256"}


def check_identity(identity: dict[str, Any], label: str, errors: list[str]) -> bytes:
    try:
        path = lane_path(str(identity.get("path", "")))
    except ValueError as exc:
        errors.append(f"{label}: {exc}")
        return b""
    if not path.is_file():
        errors.append(f"missing exact artifact {label}: {identity.get('path')}")
        return b""
    raw = path.read_bytes()
    require(
        isinstance(identity.get("bytes"), int)
        and len(raw) == identity["bytes"]
        and isinstance(identity.get("sha256"), str)
        and sha256(raw) == identity["sha256"],
        f"identity mismatch for {label}: {identity.get('path')}",
        errors,
    )
    return raw


def check_fixed(name: str, errors: list[str]) -> bytes:
    return check_identity(artifact_fixed(name), name, errors)


def load_json_bytes(raw: bytes, label: str, errors: list[str]) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        errors.append(f"cannot parse {label}: {exc}")
        return {}
    require(isinstance(value, dict), f"{label} root is not an object", errors)
    return value if isinstance(value, dict) else {}


def parse_manifest(
    raw: bytes,
    label: str,
    expected_count: int,
    expected_bytes: int,
    errors: list[str],
) -> dict[str, tuple[int, str]]:
    require(not raw.startswith(b"\xef\xbb\xbf"), f"{label} has a BOM", errors)
    require(b"\r" not in raw, f"{label} is not LF-only", errors)
    require(raw.endswith(b"\n"), f"{label} lacks terminal LF", errors)
    try:
        lines = raw.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        errors.append(f"{label} is not UTF-8: {exc}")
        return {}
    rows: dict[str, tuple[int, str]] = {}
    order: list[str] = []
    for number, line in enumerate(lines, 1):
        parts = line.split("\t")
        if len(parts) != 3:
            errors.append(f"{label} row {number} has {len(parts)} columns")
            continue
        path, size_text, digest = parts
        try:
            size = int(size_text)
        except ValueError:
            errors.append(f"{label} row {number} has invalid size")
            continue
        try:
            lane_path(f"repo/{path}")
        except ValueError as exc:
            errors.append(f"{label} row {number}: {exc}")
        require(path not in rows, f"duplicate {label} path: {path}", errors)
        require(size >= 0, f"negative {label} size at row {number}", errors)
        require(
            re.fullmatch(r"[0-9a-f]{64}", digest) is not None,
            f"invalid {label} SHA-256 at row {number}",
            errors,
        )
        rows[path] = (size, digest)
        order.append(path)
    require(order == sorted(order), f"{label} rows are not sorted", errors)
    require(len(rows) == expected_count, f"{label} count is not {expected_count}", errors)
    require(
        sum(size for size, _digest in rows.values()) == expected_bytes,
        f"{label} payload bytes are not {expected_bytes:,}",
        errors,
    )
    return rows


def source_delta(
    base: dict[str, tuple[int, str]], target: dict[str, tuple[int, str]]
) -> dict[str, Any]:
    base_paths = set(base)
    target_paths = set(target)
    added = sorted(target_paths - base_paths)
    removed = sorted(base_paths - target_paths)
    changed = sorted(path for path in base_paths & target_paths if base[path] != target[path])
    return {
        "base_file_count": len(base),
        "base_file_bytes": sum(value[0] for value in base.values()),
        "target_file_count": len(target),
        "target_file_bytes": sum(value[0] for value in target.values()),
        "added_paths": added,
        "added_file_count": len(added),
        "added_file_bytes": sum(target[path][0] for path in added),
        "removed_paths": removed,
        "removed_file_count": len(removed),
        "changed_paths": changed,
        "changed_file_count": len(changed),
        "changed_file_bytes_before": sum(base[path][0] for path in changed),
        "changed_file_bytes_after": sum(target[path][0] for path in changed),
        "changed_file_net_bytes": sum(target[path][0] - base[path][0] for path in changed),
        "unchanged_file_count": sum(
            base[path] == target[path] for path in base_paths & target_paths
        ),
        "net_file_bytes": sum(value[0] for value in target.values())
        - sum(value[0] for value in base.values()),
    }


def replay_repo_manifest(
    rows: dict[str, tuple[int, str]], errors: list[str]
) -> None:
    actual_paths = {
        path.relative_to(REPO).as_posix()
        for path in REPO.rglob("*")
        if path.is_file()
    }
    require(
        actual_paths == set(rows),
        "live repo path inventory is not the exact 1,195-file B006 closure",
        errors,
    )
    for relative, (size, digest) in rows.items():
        path = REPO / relative
        if not path.is_file():
            errors.append(f"target manifest file missing: {relative}")
            continue
        raw = path.read_bytes()
        require(
            len(raw) == size and sha256(raw) == digest,
            f"target manifest replay mismatch: {relative}",
            errors,
        )


def recursively_find_unset(value: object, prefix: str = "") -> list[str]:
    if value is None:
        return [prefix or "<root>"]
    if isinstance(value, dict):
        found: list[str] = []
        for key, item in value.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            found.extend(recursively_find_unset(item, child))
        return found
    if isinstance(value, list):
        found = []
        for index, item in enumerate(value):
            found.extend(recursively_find_unset(item, f"{prefix}[{index}]"))
        return found
    return []


def recursively_has_marker(value: object) -> bool:
    if isinstance(value, dict):
        return any(recursively_has_marker(item) for item in value.values())
    if isinstance(value, list):
        return any(recursively_has_marker(item) for item in value)
    if isinstance(value, str):
        return re.search(r"\b(?:TODO|TBD|UNSET)\b", value, re.I) is not None
    return False


def contains_identity(value: object, identity: dict[str, Any], require_path: bool = True) -> bool:
    if isinstance(value, dict):
        same = (
            value.get("bytes") == identity.get("bytes")
            and value.get("sha256") == identity.get("sha256")
        )
        if same and (not require_path or value.get("path") == identity.get("path")):
            return True
        return any(contains_identity(item, identity, require_path) for item in value.values())
    if isinstance(value, list):
        return any(contains_identity(item, identity, require_path) for item in value)
    return False


def inventory_identity(root: Path) -> tuple[str, int, int, dict[str, bytes]]:
    payloads: dict[str, bytes] = {}
    lines: list[str] = []
    total = 0
    if root.is_dir():
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            relative = path.relative_to(root).as_posix()
            raw = path.read_bytes()
            payloads[relative] = raw
            total += len(raw)
            lines.append(f"{relative}\t{len(raw)}\t{sha256(raw)}\n")
    return sha256("".join(lines).encode("utf-8")), len(lines), total, payloads


def validate_controls(errors: list[str]) -> None:
    terminology_path = lane_path(FIXED_EXPECTED["terminology"][0])
    with terminology_path.open("r", encoding="utf-8", newline="") as stream:
        term_rows = list(csv.DictReader(stream))
    term_ids = [row.get("term_id") for row in term_rows]
    require(
        term_ids == [f"R011-TERM-{number:04d}" for number in range(1, 142)],
        "terminology control is not exactly TERM-0001..0141",
        errors,
    )

    adverse_rows: list[dict[str, Any]] = []
    for number, line in enumerate(
        lane_path(FIXED_EXPECTED["adverse"][0]).read_text(encoding="utf-8").splitlines(),
        1,
    ):
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"adverse row {number} is invalid JSON: {exc}")
            continue
        if isinstance(value, dict):
            adverse_rows.append(value)
    require(
        [row.get("id") for row in adverse_rows]
        == [f"R011-ADV-{number:04d}" for number in range(1, 80)],
        "adverse control is not exactly ADV-0001..0079",
        errors,
    )

    with lane_path(FIXED_EXPECTED["component_rights"][0]).open(
        "r", encoding="utf-8", newline=""
    ) as stream:
        rights_rows = list(csv.DictReader(stream))
    rights_ids = {row.get("component_id") for row in rights_rows}
    require(
        {
            "R011-RIGHTS-B006-GENERATED",
            "R011-RIGHTS-B006-DATA",
            "R011-RIGHTS-RPKG",
        }
        <= rights_ids,
        "component-rights control omits a required B006 or R-package row",
        errors,
    )


def validate_fixed_evidence(errors: list[str]) -> dict[str, Any]:
    raw: dict[str, bytes] = {
        name: check_fixed(name, errors) for name in FIXED_EXPECTED
    }
    prior = load_json_bytes(raw["prior_boundary_receipt"], "prior receipt", errors)
    require(
        prior.get("schema") == "openintro-id-boundary-receipt"
        and prior.get("boundary_id") == "R011-B005"
        and prior.get("status") == "admitted",
        "prior R011-B005 receipt is not the exact admitted state",
        errors,
    )
    require(
        prior.get("authority", {}).get("commit") == AUTHORITY_COMMIT
        and prior.get("authority", {}).get("tree") == AUTHORITY_TREE,
        "prior receipt authority mismatch",
        errors,
    )
    require(
        prior.get("target_closure", {}).get("file_count") == 1182
        and prior.get("target_closure", {}).get("bytes") == 41144346
        and prior.get("backend", {}).get("record_count") == BASE_RECORD_COUNT
        and prior.get("backend", {}).get("status") == "passed"
        and prior.get("backend", {}).get("placeholder_count") == 0
        and prior.get("backend", {}).get("pending_count") == 0
        and prior.get("backend", {}).get("publication_blocker_count") == 0,
        "prior source/backend admission closure mismatch",
        errors,
    )

    base_rows = parse_manifest(
        raw["prior_target_manifest"],
        "R011-B005 target manifest",
        1182,
        41144346,
        errors,
    )
    target_rows = parse_manifest(
        raw["target_manifest"],
        "R011-B006 target manifest",
        1195,
        41205947,
        errors,
    )
    delta = source_delta(base_rows, target_rows)
    expected_delta = {
        "base_file_count": 1182,
        "base_file_bytes": 41144346,
        "target_file_count": 1195,
        "target_file_bytes": 41205947,
        "added_file_count": 13,
        "added_file_bytes": 65607,
        "removed_file_count": 0,
        "changed_file_count": 16,
        "changed_file_bytes_before": 296332,
        "changed_file_bytes_after": 292326,
        "changed_file_net_bytes": -4006,
        "unchanged_file_count": 1166,
        "net_file_bytes": 61601,
    }
    for key, expected in expected_delta.items():
        require(delta.get(key) == expected, f"source delta field {key} is not exact", errors)
    replay_repo_manifest(target_rows, errors)

    source = load_json_bytes(raw["source_qa"], "source QA", errors)
    require(
        source.get("schema") == "openintro-id-source-boundary-qa"
        and source.get("schema_version") == "0.9.0"
        and source.get("boundary_id") == "R011-B006"
        and source.get("status") == "passed",
        "revised source receipt schema/status mismatch",
        errors,
    )
    require(
        source.get("authority", {}).get("repository") == AUTHORITY_REPOSITORY
        and source.get("authority", {}).get("commit") == AUTHORITY_COMMIT
        and source.get("authority", {}).get("tree") == AUTHORITY_TREE,
        "revised source receipt authority mismatch",
        errors,
    )
    target_closure = source.get("target_closure", {})
    require(
        target_closure.get("target_file_count") == 1195
        and target_closure.get("target_file_bytes") == 41205947
        and target_closure.get("manifest") == artifact_fixed("target_manifest")
        and target_closure.get("actual_repo_inventory_replayed") is True
        and target_closure.get("added_paths") == delta["added_paths"]
        and target_closure.get("changed_paths") == delta["changed_paths"]
        and target_closure.get("removed_paths") == [],
        "source receipt does not bind the recomputed exact target closure",
        errors,
    )
    checks = source.get("checks", {})
    require(
        checks.get("active_reader_visible_english") == 0
        and checks.get("placeholders") == 0
        and checks.get("source_order_and_topology") == "passed"
        and checks.get("exercise_answer_o001_topology") == "passed"
        and checks.get("asset_code_data_rights_closure") == "passed"
        and checks.get("post_build_repairs_reverse_reconstructed") == "passed"
        and checks.get("rejected_v1_visual_findings_bound") == "passed",
        "source QA contains a failed or incomplete B006 check",
        errors,
    )
    require(
        checks.get("v3_layout_repairs_reverse_reconstructed") == "passed"
        and checks.get("prior_v3_layout_repair_receipt")
        == artifact_fixed("layout_repair_receipt_v3")
        and checks.get("rejected_v2_visual_findings_bound") == "passed"
        and checks.get("v4_layout_repair_reverse_reconstructed") == "passed"
        and checks.get("v4_layout_repair_receipt")
        == artifact_fixed("layout_repair_receipt_v4")
        and checks.get("rejected_v3_visual_findings_bound") == "passed"
        and checks.get("ADV_0070_through_0079") == "passed",
        "source QA does not bind the v2/v3 rejection and v3/v4 layout repairs",
        errors,
    )
    scope_source = source.get("scope", {}).get("source", {})
    require(
        scope_source.get("body") == artifact_fixed("body")
        and scope_source.get("exercises") == artifact_fixed("exercises")
        and scope_source.get("public_answer_file") == artifact_fixed("answers"),
        "source receipt canonical TeX identities mismatch",
        errors,
    )
    o001 = scope_source.get("o001", {})
    require(
        o001.get("exercise_numbers") == EXPECTED_EXERCISES
        and o001.get("public_answers") == EXPECTED_PUBLIC_ANSWERS
        and o001.get("o001_gaps") == EXPECTED_O001_GAPS
        and o001.get("restricted_instructor_solutions_accessed_or_invented") is False,
        "exercise/public-answer/O001 partition mismatch",
        errors,
    )
    repair_handoff = scope_source.get("post_build_repair_handoff", {})
    require(
        repair_handoff.get("status") == "passed"
        and repair_handoff.get("exact_substitution_count") == 17
        and repair_handoff.get("all_pre_repair_outputs_reconstructed_byte_exact") is True
        and repair_handoff.get("repair_receipt") == artifact_fixed("repair_receipt")
        and repair_handoff.get("rejected_build_v1_receipt")
        == artifact_fixed("rejected_build_v1")
        and repair_handoff.get("visual_findings_v1_receipt")
        == artifact_fixed("rejected_visual_v1"),
        "post-build repair handoff mismatch",
        errors,
    )
    layout_handoff = scope_source.get("v3_layout_repair_handoff", {})
    require(
        layout_handoff.get("status") == "passed"
        and layout_handoff.get("adverse_ids") == ["R011-ADV-0077", "R011-ADV-0078"]
        and layout_handoff.get("exact_substitution_count") == 3
        and layout_handoff.get("all_v2_outputs_reconstructed_byte_exact") is True
        and layout_handoff.get("final_canonical_outputs") == V3_CANONICAL_OUTPUTS
        and layout_handoff.get("layout_repair_receipt_v3")
        == artifact_fixed("layout_repair_receipt_v3")
        and layout_handoff.get("rejected_build_v2_receipt")
        == artifact_fixed("rejected_build_v2")
        and layout_handoff.get("visual_findings_v2_receipt")
        == artifact_fixed("rejected_visual_v2")
        and layout_handoff.get("layout_only_invariants", {}).get("status") == "passed"
        and layout_handoff.get("layout_only_invariants", {}).get("instructional_content_changed")
        is False
        and layout_handoff.get("layout_only_invariants", {}).get("math_changed") is False
        and layout_handoff.get("layout_only_invariants", {}).get("numeric_data_changed")
        is False,
        "v3 layout-repair handoff is not exact/reversible/layout-only",
        errors,
    )
    v4_layout_handoff = scope_source.get("v4_layout_repair_handoff", {})
    require(
        v4_layout_handoff.get("status") == "passed"
        and v4_layout_handoff.get("adverse_ids") == ["R011-ADV-0079"]
        and v4_layout_handoff.get("exact_substitution_count") == 1
        and v4_layout_handoff.get("all_v3_outputs_reconstructed_byte_exact") is True
        and v4_layout_handoff.get("final_canonical_outputs")
        == [artifact_fixed("body"), artifact_fixed("exercises"), artifact_fixed("answers")]
        and v4_layout_handoff.get("layout_repair_receipt")
        == artifact_fixed("layout_repair_receipt_v4")
        and v4_layout_handoff.get("prior_layout_repair_receipt_v3")
        == artifact_fixed("layout_repair_receipt_v3")
        and v4_layout_handoff.get("candidate_build_v3_receipt")
        == V3_CANDIDATE_BUILD_IDENTITY
        and v4_layout_handoff.get("rejected_build_v3_receipt")
        == artifact_fixed("rejected_build_v3")
        and v4_layout_handoff.get("visual_findings_v3_receipt")
        == artifact_fixed("rejected_visual_v3")
        and v4_layout_handoff.get("rejected_visual_findings_bound")
        == ["R011-B006-V3-001"]
        and v4_layout_handoff.get("v3_source_receipt") == V3_SOURCE_QA_IDENTITY
        and v4_layout_handoff.get("v3_target_manifest") == V3_TARGET_MANIFEST_IDENTITY
        and v4_layout_handoff.get("layout_only_invariants", {}).get("status") == "passed"
        and v4_layout_handoff.get("layout_only_invariants", {}).get(
            "instructional_content_changed"
        )
        is False
        and v4_layout_handoff.get("layout_only_invariants", {}).get("math_changed") is False
        and v4_layout_handoff.get("layout_only_invariants", {}).get("numeric_data_changed")
        is False,
        "v4 layout-repair handoff is not exact/reversible/layout-only",
        errors,
    )
    require(
        source.get("scope", {}).get("next_untranslated_marker")
        == "ch_summarizing_data/TeX/ch_summarizing_data.tex / Section 2.3 Case study: malaria vaccine",
        "next source cursor is not exact",
        errors,
    )

    repair = load_json_bytes(raw["repair_receipt"], "repair receipt", errors)
    require(
        repair.get("schema_version") == "r011-b006-repair-receipt/1.0.0"
        and repair.get("boundary_id") == "R011-B006"
        and repair.get("status") == "repair_applied_and_reverse_verified"
        and repair.get("repairs", {}).get("substitution_count") == 17
        and repair.get("repairs", {}).get("numeric_data_changed") is False
        and repair.get("repairs", {}).get("instructional_content_order_changed") is False
        and repair.get("reverse_reconstruction", {}).get(
            "all_outputs_match_pre_repair_identities"
        )
        is True,
        "repair receipt is not exact/reversible/noninstructional",
        errors,
    )
    layout_repair = load_json_bytes(
        raw["layout_repair_receipt_v3"], "layout repair receipt v3", errors
    )
    require(
        layout_repair.get("schema") == "openintro-b006-layout-repair-receipt"
        and layout_repair.get("schema_version")
        == "r011-b006-layout-repair-receipt-v3/1.0.0"
        and layout_repair.get("boundary_id") == "R011-B006"
        and layout_repair.get("status")
        == "layout_repairs_applied_and_reverse_verified"
        and layout_repair.get("boundary_admitted") is False
        and layout_repair.get("layout_repairs", {}).get("substitution_count") == 3
        and layout_repair.get("layout_repairs", {}).get("adverse_ids")
        == ["R011-ADV-0077", "R011-ADV-0078"]
        and layout_repair.get("layout_repairs", {}).get("instructional_content_changed")
        is False
        and layout_repair.get("layout_repairs", {}).get("math_changed") is False
        and layout_repair.get("layout_repairs", {}).get("numeric_data_changed") is False
        and layout_repair.get("reverse_reconstruction", {}).get(
            "all_outputs_match_source_snapshot_v2_identities"
        )
        is True
        and layout_repair.get("post_repair_target_manifest") == V3_TARGET_MANIFEST_IDENTITY,
        "v3 layout repair receipt mismatch",
        errors,
    )

    layout_repair_v4 = load_json_bytes(
        raw["layout_repair_receipt_v4"], "layout repair receipt v4", errors
    )
    require(
        layout_repair_v4.get("schema") == "openintro-b006-layout-repair-receipt"
        and layout_repair_v4.get("schema_version")
        == "r011-b006-layout-repair-receipt-v4/1.0.0"
        and layout_repair_v4.get("boundary_id") == "R011-B006"
        and layout_repair_v4.get("status")
        == "layout_repairs_applied_and_reverse_verified"
        and layout_repair_v4.get("boundary_admitted") is False
        and layout_repair_v4.get("layout_repairs", {}).get("substitution_count") == 1
        and layout_repair_v4.get("layout_repairs", {}).get("adverse_ids")
        == ["R011-ADV-0079"]
        and layout_repair_v4.get("layout_repairs", {}).get("instructional_content_changed")
        is False
        and layout_repair_v4.get("layout_repairs", {}).get("instructional_order_changed")
        is False
        and layout_repair_v4.get("layout_repairs", {}).get("math_changed") is False
        and layout_repair_v4.get("layout_repairs", {}).get("numeric_data_changed") is False
        and layout_repair_v4.get("layout_repairs", {}).get("asset_bytes_or_bindings_changed")
        is False
        and layout_repair_v4.get("reverse_reconstruction", {}).get(
            "all_outputs_match_source_snapshot_v3_identities"
        )
        is True
        and layout_repair_v4.get("post_repair_target_manifest")
        == artifact_fixed("target_manifest")
        and layout_repair_v4.get("final_canonical_outputs")
        == [artifact_fixed("body"), artifact_fixed("exercises"), artifact_fixed("answers")]
        and layout_repair_v4.get("final_control")
        == {
            **artifact_fixed("adverse"),
            "adverse_ids": ["R011-ADV-0079"],
            "validated_tail": [f"R011-ADV-{number:04d}" for number in range(70, 80)],
        },
        "v4 layout repair receipt mismatch",
        errors,
    )
    v4_pre = layout_repair_v4.get("pre_repair_evidence", {})
    require(
        v4_pre.get("candidate_build_v3_receipt") == V3_CANDIDATE_BUILD_IDENTITY
        and v4_pre.get("prior_layout_repair_receipt_v3")
        == artifact_fixed("layout_repair_receipt_v3")
        and v4_pre.get("rejected_build_v3_receipt")
        == artifact_fixed("rejected_build_v3")
        and v4_pre.get("visual_findings_v3_receipt")
        == artifact_fixed("rejected_visual_v3")
        and v4_pre.get("source_receipt_v3") == V3_SOURCE_QA_IDENTITY
        and v4_pre.get("target_manifest_v3") == V3_TARGET_MANIFEST_IDENTITY
        and v4_pre.get("target_manifest_v3_reverse_reconstruction", {}).get(
            "matches_rejected_v3_manifest_identity"
        )
        is True,
        "v4 layout receipt does not bind the complete rejected-v3 predecessor",
        errors,
    )
    require(
        layout_repair_v4.get("visual_candidate_v3", {}).get("status")
        == "rejected_visual"
        and layout_repair_v4.get("visual_candidate_v3", {}).get("promoted") is False
        and layout_repair_v4.get("visual_candidate_v3", {}).get("candidate_pdf", {}).get(
            "sha256"
        )
        == REJECTED_V3_PDF_SHA256
        and [
            item.get("id")
            for item in layout_repair_v4.get("visual_candidate_v3", {}).get("findings", [])
        ]
        == ["R011-B006-V3-001"],
        "v4 layout receipt rejected-v3 visual binding mismatch",
        errors,
    )

    rejected_build = load_json_bytes(raw["rejected_build_v1"], "rejected build v1", errors)
    rejected_visual = load_json_bytes(
        raw["rejected_visual_v1"], "rejected visual v1", errors
    )
    rejected_build_v2 = load_json_bytes(
        raw["rejected_build_v2"], "rejected build v2", errors
    )
    rejected_visual_v2 = load_json_bytes(
        raw["rejected_visual_v2"], "rejected visual v2", errors
    )
    rejected_build_v3 = load_json_bytes(
        raw["rejected_build_v3"], "rejected build v3", errors
    )
    rejected_visual_v3 = load_json_bytes(
        raw["rejected_visual_v3"], "rejected visual v3", errors
    )
    require(
        rejected_build.get("schema") == "openintro-boundary-build-candidate-qa"
        and rejected_build.get("boundary_id") == "R011-B006"
        and rejected_build.get("status") == "rejected_visual",
        "v1 build is not preserved as rejected",
        errors,
    )
    require(
        rejected_visual.get("schema") == "openintro-boundary-visual-findings"
        and rejected_visual.get("boundary_id") == "R011-B006"
        and rejected_visual.get("candidate") == "final-v1"
        and rejected_visual.get("status") == "rejected"
        and rejected_visual.get("candidate_pdf", {}).get("sha256")
        == REJECTED_V1_PDF_SHA256
        and rejected_visual.get("severity_counts")
        == {"P0": 0, "P1": 0, "P2": 2, "P3": 0}
        and [item.get("id") for item in rejected_visual.get("findings", [])]
        == ["R011-B006-V1-001", "R011-B006-V1-002"],
        "v1 visual rejection evidence mismatch",
        errors,
    )
    require(
        rejected_build_v2.get("schema") == "openintro-boundary-build-rejection"
        and rejected_build_v2.get("boundary_id") == "R011-B006"
        and rejected_build_v2.get("candidate") == "final-v2"
        and rejected_build_v2.get("status") == "rejected_visual"
        and rejected_build_v2.get("nonvisual_status") == "passed"
        and rejected_build_v2.get("candidate_artifact", {}).get("sha256")
        == REJECTED_V2_PDF_SHA256
        and rejected_build_v2.get("candidate_artifact", {}).get("promoted") is False
        and rejected_build_v2.get("output_pdf_mutated") is False
        and rejected_build_v2.get("pass_audit_created") is False,
        "v2 build is not preserved as a nonpromoted visual rejection",
        errors,
    )
    require(
        rejected_visual_v2.get("schema") == "openintro-boundary-visual-findings"
        and rejected_visual_v2.get("boundary_id") == "R011-B006"
        and rejected_visual_v2.get("candidate") == "final-v2"
        and rejected_visual_v2.get("status") == "rejected"
        and rejected_visual_v2.get("candidate_pdf", {}).get("sha256")
        == REJECTED_V2_PDF_SHA256
        and rejected_visual_v2.get("severity_counts")
        == {"P0": 0, "P1": 0, "P2": 2, "P3": 0}
        and [item.get("id") for item in rejected_visual_v2.get("findings", [])]
        == ["R011-B006-V2-001", "R011-B006-V2-002"]
        and rejected_visual_v2.get("promoted") is False
        and rejected_visual_v2.get("output_pdf_mutated") is False
        and rejected_visual_v2.get("pass_audit_created") is False,
        "v2 visual rejection evidence mismatch",
        errors,
    )
    require(
        rejected_build_v3.get("schema") == "openintro-boundary-build-rejection"
        and rejected_build_v3.get("boundary_id") == "R011-B006"
        and rejected_build_v3.get("candidate") == "final-v3"
        and rejected_build_v3.get("status") == "rejected_visual"
        and rejected_build_v3.get("nonvisual_status") == "passed"
        and rejected_build_v3.get("candidate_artifact", {}).get("sha256")
        == REJECTED_V3_PDF_SHA256
        and rejected_build_v3.get("candidate_artifact", {}).get("promoted") is False
        and rejected_build_v3.get("output_pdf_mutated") is False
        and rejected_build_v3.get("pass_audit_created") is False,
        "v3 build is not preserved as a nonpromoted visual rejection",
        errors,
    )
    require(
        rejected_visual_v3.get("schema") == "openintro-boundary-visual-findings"
        and rejected_visual_v3.get("boundary_id") == "R011-B006"
        and rejected_visual_v3.get("candidate") == "final-v3"
        and rejected_visual_v3.get("status") == "rejected"
        and rejected_visual_v3.get("candidate_pdf", {}).get("sha256")
        == REJECTED_V3_PDF_SHA256
        and rejected_visual_v3.get("severity_counts")
        == {"P0": 0, "P1": 0, "P2": 1, "P3": 0}
        and [item.get("id") for item in rejected_visual_v3.get("findings", [])]
        == ["R011-B006-V3-001"]
        and rejected_visual_v3.get("promoted") is False
        and rejected_visual_v3.get("output_pdf_mutated") is False
        and rejected_visual_v3.get("pass_audit_created") is False,
        "v3 visual rejection evidence mismatch",
        errors,
    )

    asset_manifest = load_json_bytes(raw["asset_manifest"], "asset manifest", errors)
    asset_receipt = load_json_bytes(raw["asset_receipt"], "asset receipt", errors)
    require(
        asset_manifest.get("schema_version") == "r011.asset-manifest.v1"
        and asset_manifest.get("boundary_id") == "R011-B006"
        and asset_manifest.get("status") == "pass"
        and len(asset_manifest.get("assets", [])) == 13
        and len(asset_manifest.get("producers", [])) == 8,
        "asset manifest schema/count/status mismatch",
        errors,
    )
    require(
        asset_receipt.get("schema_version") == "r011.asset-validation-receipt.v1"
        and asset_receipt.get("boundary_id") == "R011-B006"
        and asset_receipt.get("status") == "pass"
        and asset_receipt.get("manifest") == artifact_fixed("asset_manifest")
        and asset_receipt.get("counts", {}).get("assets") == 13
        and asset_receipt.get("counts", {}).get("source_witnesses") == 13
        and asset_receipt.get("counts", {}).get("adjacent_r_producers") == 8
        and asset_receipt.get("counts", {}).get("deterministic_replays") == 2
        and asset_receipt.get("counts", {}).get("replay_identical_assets") == 13
        and asset_receipt.get("errors") == []
        and asset_receipt.get("blockers") == []
        and asset_receipt.get("asset_subgate_admission_ready") is True,
        "asset validation receipt is not an exact passing closure",
        errors,
    )
    for item in asset_manifest.get("assets", []):
        if not isinstance(item, dict):
            errors.append("asset manifest contains a non-object asset")
            continue
        for role in ("source", "target"):
            identity = item.get(role)
            if isinstance(identity, dict):
                check_identity(identity, f"asset {item.get('id')} {role}", errors)
            else:
                errors.append(f"asset {item.get('id')} omits {role} identity")
    for item in asset_manifest.get("producers", []):
        if isinstance(item, dict):
            check_identity(item, f"asset producer {item.get('path')}", errors)
        else:
            errors.append("asset manifest contains a non-object producer")

    validate_controls(errors)
    return {
        "prior": prior,
        "source": source,
        "repair": repair,
        "layout_repair_v3": layout_repair,
        "layout_repair_v4": layout_repair_v4,
        "rejected_visual": rejected_visual,
        "rejected_visual_v2": rejected_visual_v2,
        "rejected_visual_v3": rejected_visual_v3,
        "asset_manifest": asset_manifest,
        "asset_receipt": asset_receipt,
        "target_rows": target_rows,
        "delta": delta,
    }


def final_bindings_ready(errors: list[str]) -> bool:
    unset = recursively_find_unset(FINAL_EXPECTED)
    if unset:
        errors.append(
            "final-v4-or-later/backend bindings unset; admission deliberately refused: "
            + ", ".join(unset)
        )
        return False
    for name, value in FINAL_EXPECTED.items():
        if is_identity_binding(value):
            require(
                isinstance(value.get("path"), str)
                and bool(value.get("path"))
                and isinstance(value.get("bytes"), int)
                and value["bytes"] > 0
                and re.fullmatch(r"[0-9a-f]{64}", str(value.get("sha256")))
                is not None,
                f"final binding {name} is malformed",
                errors,
            )
    scalar_keys = [
        "page_count",
        "rendered_page_count",
        "backend_payload_count",
        "backend_payload_bytes",
        "backend_manifest_file_entry_count",
        "backend_stage_inventory_file_count",
        "backend_stage_inventory_bytes",
        "backend_resolved_reference_count",
        "backend_authority_span_count",
        "backend_localization_slice_count",
        "backend_artifact_count",
        "backend_validator_check_count",
        "backend_record_count",
        "backend_added_record_count",
    ]
    for key in scalar_keys:
        require(
            isinstance(FINAL_EXPECTED.get(key), int)
            and not isinstance(FINAL_EXPECTED.get(key), bool)
            and int(FINAL_EXPECTED[key]) > 0,
            f"final scalar binding {key} is not a positive integer",
            errors,
        )
    counts = FINAL_EXPECTED.get("backend_record_counts")
    require(
        isinstance(counts, dict)
        and set(counts) == set(BACKEND_RECORD_PATHS)
        and all(isinstance(value, int) and not isinstance(value, bool) and value > 0 for value in counts.values()),
        "backend record-count binding is malformed",
        errors,
    )
    if isinstance(counts, dict) and all(isinstance(value, int) for value in counts.values()):
        require(
            sum(counts.values()) == FINAL_EXPECTED.get("backend_record_count")
            and FINAL_EXPECTED.get("backend_record_count")
            == BASE_RECORD_COUNT + FINAL_EXPECTED.get("backend_added_record_count", -1),
            "backend total/base/additive record bindings do not reconcile",
            errors,
        )
    check_names = FINAL_EXPECTED.get("backend_check_names")
    require(
        isinstance(check_names, list)
        and len(check_names) == FINAL_EXPECTED.get("backend_validator_check_count")
        and len(check_names) == len(set(check_names))
        and all(isinstance(name, str) and bool(name) for name in check_names),
        "backend validator-check binding is malformed",
        errors,
    )
    require(
        re.fullmatch(
            r"[0-9a-f]{64}",
            str(FINAL_EXPECTED.get("backend_stage_inventory_sha256", "")),
        )
        is not None,
        "backend stage-inventory SHA binding is malformed",
        errors,
    )
    return not unset


def validate_render_manifest(
    raw: bytes, visual: dict[str, Any], errors: list[str]
) -> list[int]:
    require(b"\r" not in raw and raw.endswith(b"\n"), "render manifest is not LF-canonical", errors)
    pages: list[int] = []
    render_root = lane_path(str(FINAL_EXPECTED["render_manifest"]["path"])).parent
    for number, line in enumerate(raw.decode("utf-8").splitlines(), 1):
        parts = line.split("\t")
        if len(parts) != 4:
            errors.append(f"render manifest row {number} has {len(parts)} columns")
            continue
        page_text, name, size_text, digest = parts
        try:
            page = int(page_text)
            size = int(size_text)
        except ValueError:
            errors.append(f"render manifest row {number} has invalid numeric data")
            continue
        require(
            name == f"page-{page:03d}.png" and Path(name).name == name,
            f"render manifest row {number} has unsafe/noncanonical name",
            errors,
        )
        require(
            re.fullmatch(r"[0-9a-f]{64}", digest) is not None,
            f"render manifest row {number} has invalid SHA-256",
            errors,
        )
        path = render_root / name
        if not path.is_file():
            errors.append(f"rendered page missing: {path.relative_to(LANE).as_posix()}")
        else:
            payload = path.read_bytes()
            require(
                len(payload) == size and sha256(payload) == digest,
                f"rendered page identity mismatch: {name}",
                errors,
            )
        pages.append(page)
    require(pages == sorted(set(pages)), "render page list is not sorted/unique", errors)
    require(
        len(pages) == FINAL_EXPECTED["rendered_page_count"],
        "rendered page count is not exact",
        errors,
    )
    require(
        visual.get("parent_acceptance", {}).get("inspected_pages") == pages
        and visual.get("parent_acceptance", {}).get("inspected_page_count") == len(pages)
        and visual.get("parent_acceptance", {}).get("all_required_pages_inspected") is True,
        "visual audit does not cover every rendered candidate page in order",
        errors,
    )
    return pages


def validate_final_evidence(
    errors: list[str], require_promoted: bool
) -> dict[str, Any]:
    raws: dict[str, bytes] = {}
    for name, value in FINAL_EXPECTED.items():
        if is_identity_binding(value):
            # The canonical PDF is a post-transaction artifact.  Pre-promotion
            # evaluation must validate the reviewed candidate and every input
            # needed to create it, without requiring the destination to exist.
            if name == "promoted_pdf" and not require_promoted:
                continue
            raws[name] = check_identity(value, name, errors)

    final_inputs = load_json_bytes(raws.get("final_inputs", b""), "final inputs", errors)
    required_inputs = [
        "source_qa",
        "target_manifest",
        "build_gate_script",
        "candidate_build_qa",
        "build_qa",
        "build_log",
        "build_text",
        "pdf",
        "render_manifest",
        "page_locator",
        "contact_sheet",
        "visual_audit",
        "visual_finalizer",
    ]
    require(
        final_inputs.get("schema_version") == "r011-b006-final-gate-inputs/1.0.0"
        and final_inputs.get("boundary_id") == "R011-B006"
        and final_inputs.get("status") == "supplied_exact_final_inputs"
        and sorted(final_inputs.get("inputs", {})) == sorted(required_inputs),
        "final-input manifest envelope/key inventory mismatch",
        errors,
    )
    expected_inputs = {
        "source_qa": artifact_fixed("source_qa"),
        "target_manifest": artifact_fixed("target_manifest"),
        "build_gate_script": expected_identity("build_gate_script"),
        "candidate_build_qa": expected_identity("candidate_build_qa"),
        "build_qa": expected_identity("build_qa"),
        "build_log": expected_identity("build_log"),
        "build_text": expected_identity("build_text"),
        "pdf": {
            **expected_identity("final_pdf"),
            "page_count": FINAL_EXPECTED["page_count"],
        },
        "render_manifest": {
            **expected_identity("render_manifest"),
            "page_count": FINAL_EXPECTED["rendered_page_count"],
        },
        "page_locator": expected_identity("render_page_locator"),
        "contact_sheet": expected_identity("render_contact_sheet"),
        "visual_audit": expected_identity("visual_audit"),
        "visual_finalizer": artifact_fixed("visual_finalizer"),
    }
    require(
        final_inputs.get("inputs") == expected_inputs,
        "final-input manifest does not contain only the reviewed exact identities",
        errors,
    )

    candidate_build = load_json_bytes(
        raws.get("candidate_build_qa", b""), "final-v4 candidate build QA", errors
    )
    require(
        candidate_build.get("boundary_id") == "R011-B006"
        and candidate_build.get("status") == "pending_visual_review"
        and candidate_build.get("nonvisual_status") == "passed"
        and candidate_build.get("errors") == []
        and candidate_build.get("pending")
        == ["operator inspection of every full-resolution candidate PNG"]
        and candidate_build.get("candidate_artifact", {}).get("promoted") is False
        and candidate_build.get("visual_evidence", {}).get("status")
        == "pending_operator_inspection",
        "final-v4 candidate receipt is not the exact nonpromoted inspection candidate",
        errors,
    )
    candidate_source = candidate_build.get("source_closure", {})
    require(
        candidate_source.get("file_count") == 1195
        and candidate_source.get("file_bytes") == 41205947
        and candidate_source.get("path_set_and_all_file_identities_match_manifest") is True
        and contains_identity(candidate_source, artifact_fixed("source_qa"))
        and contains_identity(candidate_source, artifact_fixed("target_manifest")),
        "final-v4 candidate source-snapshot closure mismatch",
        errors,
    )

    build = load_json_bytes(raws.get("build_qa", b""), "final-v4-or-later build QA", errors)
    require(
        build.get("boundary_id") == "R011-B006"
        and build.get("schema") == "openintro-boundary-build-final-qa"
        and build.get("schema_version") == "0.2.0"
        and str(build.get("status", "")).lower() in {"pass", "passed"}
        and build.get("nonvisual_status") == "passed"
        and build.get("errors") == []
        and build.get("pending") == [],
        "final-v4-or-later build receipt is not passing/final",
        errors,
    )
    require(
        not contains_identity(build, {"bytes": 21976624, "sha256": REJECTED_V1_PDF_SHA256}, False)
        and not contains_identity(build, {"bytes": 21976316, "sha256": REJECTED_V2_PDF_SHA256}, False)
        and not contains_identity(build, {"bytes": 21976293, "sha256": REJECTED_V3_PDF_SHA256}, False)
        and FINAL_EXPECTED["final_pdf"]["sha256"]
        not in {REJECTED_V1_PDF_SHA256, REJECTED_V2_PDF_SHA256, REJECTED_V3_PDF_SHA256}
        and "/final-v4/" in str(FINAL_EXPECTED["final_pdf"]["path"]).replace("\\", "/"),
        "a rejected v1/v2/v3 or pre-v4 candidate was supplied as the final build",
        errors,
    )
    source_closure = build.get("source_closure", {})
    require(
        source_closure.get("file_count") == 1195
        and source_closure.get("file_bytes") == 41205947
        and source_closure.get("path_set_and_all_file_identities_match_manifest") is True
        and source_closure.get("source_receipt_status") in {"pass", "passed"}
        and contains_identity(source_closure, artifact_fixed("source_qa"))
        and contains_identity(source_closure, artifact_fixed("target_manifest")),
        "final build does not bind the revised 1,195-file source gate",
        errors,
    )
    require(
        contains_identity(build, expected_identity("candidate_build_qa"))
        and build.get("candidate_history", {}).get("preserved_unchanged") is True
        and contains_identity(candidate_build, expected_identity("build_gate_script"))
        and contains_identity(candidate_build, expected_identity("build_text"))
        and contains_identity(candidate_build, expected_identity("build_recorder"))
        and contains_identity(candidate_build, expected_identity("render_page_locator"))
        and contains_identity(candidate_build, expected_identity("render_contact_sheet")),
        "final/candidate build omits an exact candidate/gate/text/recorder/visual-evidence binding",
        errors,
    )
    require(
        build.get("determinism", {}).get("byte_identical") is True
        and contains_identity(build.get("determinism", {}), expected_identity("pass3_pdf"), False)
        and contains_identity(build.get("determinism", {}), expected_identity("final_pdf"), False)
        and FINAL_EXPECTED["pass3_pdf"]["bytes"] == FINAL_EXPECTED["final_pdf"]["bytes"]
        and FINAL_EXPECTED["pass3_pdf"]["sha256"] == FINAL_EXPECTED["final_pdf"]["sha256"],
        "final-v4-or-later build passes are not byte-identical",
        errors,
    )
    final_log = build.get("final_log", {})
    require(
        final_log.get("fatal_errors") == 0
        and final_log.get("latex_errors") == 0
        and final_log.get("missing_characters") == 0
        and final_log.get("missing_destinations") == 0
        and final_log.get("undefined_references_or_citations") == 0
        and final_log.get("rerun_requests") == 0,
        "final-v4-or-later build log contains an admission-fatal finding",
        errors,
    )
    build_admission = build.get("build_visual_admission", {})
    require(
        build.get("candidate_artifact")
        == {**expected_identity("final_pdf"), "promoted": False}
        and build_admission.get("status") == "passed"
        and build_admission.get("nonvisual_status") == "passed"
        and build_admission.get("visual_status") == "passed"
        and build_admission.get("candidate_pdf_promoted") is False
        and build_admission.get("publication_performed") is False
        and build_admission.get("source_or_backend_mutated") is False
        and build_admission.get("required_next_gate")
        == "boundary admission and guarded promotion"
        and build.get("links_and_structure", {}).get("page_count")
        == FINAL_EXPECTED["page_count"]
        and build.get("links_and_structure", {}).get("document_language") == "id-ID"
        and build.get("links_and_structure", {}).get("missing_link_targets") == 0,
        "final pre-promotion PDF/build/visual admission state or structure mismatch",
        errors,
    )
    require(
        contains_identity(build, expected_identity("build_log"))
        and contains_identity(build, expected_identity("render_manifest"))
        and contains_identity(build, expected_identity("visual_audit"))
        and build.get("finalization_script") == artifact_fixed("visual_finalizer")
        and build.get("gate_script") == expected_identity("build_gate_script"),
        "build receipt omits an exact log/render/visual binding",
        errors,
    )

    visual = load_json_bytes(raws.get("visual_audit", b""), "visual audit", errors)
    require(
        visual.get("boundary_id") == "R011-B006"
        and visual.get("schema") == "openintro-boundary-visual-audit"
        and visual.get("schema_version") == "0.2.0"
        and visual.get("candidate") == "final-v4"
        and str(visual.get("status", "")).lower() in {"pass", "passed"}
        and visual.get("severity_counts") == ZERO_VISUAL_SEVERITY
        and visual.get("findings") == []
        and set(visual.get("checks", {}))
        == {
            "centering",
            "clipping",
            "figures_and_tables",
            "float_only_or_mostly_empty_page",
            "orphaned_or_stranded_continuation",
            "overlap",
            "text_legibility",
            "truncation",
        }
        and set(visual.get("checks", {}).values()) == {"passed"}
        and visual.get("promotion", {}).get("performed") is False
        and visual.get("candidate_build_receipt") == expected_identity("candidate_build_qa")
        and visual.get("finalization_script") == artifact_fixed("visual_finalizer")
        and contains_identity(visual, expected_identity("final_pdf"), False)
        and contains_identity(visual, expected_identity("render_manifest")),
        "parent-approved visual audit is not zero-severity or not PDF-bound",
        errors,
    )
    pages = validate_render_manifest(raws.get("render_manifest", b""), visual, errors)
    require(
        visual.get("parent_acceptance", {}).get("inspection_resolution_dpi") == 180
        and visual.get("parent_acceptance", {}).get("actor") == "main agent /root"
        and visual.get("evidence", {}).get("individual_page_render_count")
        == FINAL_EXPECTED["rendered_page_count"]
        and visual.get("evidence", {}).get("unexpected_renderer_diagnostic_count") == 0,
        "visual audit was not performed at the required 180 dpi",
        errors,
    )

    forbidden_log = re.compile(
        rb"(?:! LaTeX Error|Emergency stop|Fatal error occurred|undefined references|undefined citations)",
        re.I,
    )
    require(
        forbidden_log.search(raws.get("build_log", b"")) is None,
        "final build log contains a forbidden fatal/undefined marker",
        errors,
    )
    require(
        not recursively_has_marker(final_inputs)
        and not recursively_has_marker(build)
        and not recursively_has_marker(visual),
        "final gate contains TODO/TBD/UNSET markers",
        errors,
    )
    return {
        "raws": raws,
        "final_inputs": final_inputs,
        "candidate_build": candidate_build,
        "build": build,
        "visual": visual,
        "pages": pages,
    }


def backend_entry_path(root: Path, relative: str) -> Path | None:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        return None
    base = BACKEND_SCHEMAS.parent if relative.startswith("schemas/") else root
    resolved = (base / candidate).resolve()
    if not resolved.is_relative_to(base.resolve()):
        return None
    return resolved


def load_canonical_jsonl(path: Path, label: str, errors: list[str]) -> tuple[list[dict[str, Any]], list[str]]:
    if not path.is_file():
        errors.append(f"missing backend JSONL: {label}")
        return [], []
    raw = path.read_bytes()
    require(not raw.startswith(b"\xef\xbb\xbf") and b"\r" not in raw, f"{label} is not UTF-8/LF canonical", errors)
    require(raw.endswith(b"\n"), f"{label} lacks terminal LF", errors)
    try:
        lines = raw.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        errors.append(f"{label} is not UTF-8: {exc}")
        return [], []
    rows: list[dict[str, Any]] = []
    for number, line in enumerate(lines, 1):
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"{label} row {number} is invalid JSON: {exc}")
            continue
        require(isinstance(value, dict), f"{label} row {number} is not an object", errors)
        if not isinstance(value, dict):
            continue
        require(
            line == json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            and unicodedata.normalize("NFC", line) == line,
            f"{label} row {number} is not canonical JSON/NFC",
            errors,
        )
        rows.append(value)
    return rows, lines


def validate_backend_stage(
    final: dict[str, Any], errors: list[str]
) -> dict[str, Any]:
    stage_receipt_raw = final["raws"].get("backend_stage_receipt", b"")
    stage_manifest_raw = final["raws"].get("backend_stage_manifest", b"")
    receipt = load_json_bytes(stage_receipt_raw, "backend stage receipt", errors)
    manifest = load_json_bytes(stage_manifest_raw, "backend stage manifest", errors)

    expected_receipt_keys = {
        "$schema",
        "artifact_count",
        "authority_span_count",
        "base_boundary",
        "base_record_count",
        "base_records_preserved_exact",
        "boundary_admitted",
        "boundary_id",
        "checks",
        "final_input_manifest",
        "live_backend_mutated",
        "localization_slice_count",
        "manifest_bytes",
        "manifest_sha256",
        "new_record_count",
        "payload_bytes",
        "payload_count",
        "placeholder_count",
        "preserved_base_record_count",
        "promotion_performed",
        "publication_blockers",
        "record_count",
        "record_counts",
        "resolved_reference_count",
        "stage_inventory_bytes",
        "stage_inventory_file_count",
        "stage_inventory_sha256",
        "status",
        "tooling",
        "validation_target",
        "validator_checks_passed",
        "validator_checks_total",
        "validator_check_names",
    }
    require(
        set(receipt) == expected_receipt_keys,
        "backend stage receipt top-level schema is not exact",
        errors,
    )
    required_receipt = {
        "$schema": "r011-b006-backend-validation-receipt/v1",
        "base_boundary": "R011-B005",
        "boundary_id": "R011-B006",
        "status": "passed_stage_candidate_all_exact_gates",
        "manifest_sha256": FINAL_EXPECTED["backend_stage_manifest"]["sha256"],
        "manifest_bytes": FINAL_EXPECTED["backend_stage_manifest"]["bytes"],
        "record_count": FINAL_EXPECTED["backend_record_count"],
        "record_counts": FINAL_EXPECTED["backend_record_counts"],
        "base_record_count": BASE_RECORD_COUNT,
        "preserved_base_record_count": BASE_RECORD_COUNT,
        "base_records_preserved_exact": True,
        "new_record_count": FINAL_EXPECTED["backend_added_record_count"],
        "payload_count": FINAL_EXPECTED["backend_payload_count"],
        "payload_bytes": FINAL_EXPECTED["backend_payload_bytes"],
        "resolved_reference_count": FINAL_EXPECTED["backend_resolved_reference_count"],
        "authority_span_count": FINAL_EXPECTED["backend_authority_span_count"],
        "localization_slice_count": 21,
        "artifact_count": FINAL_EXPECTED["backend_artifact_count"],
        "stage_inventory_sha256": FINAL_EXPECTED["backend_stage_inventory_sha256"],
        "stage_inventory_file_count": FINAL_EXPECTED["backend_stage_inventory_file_count"],
        "stage_inventory_bytes": FINAL_EXPECTED["backend_stage_inventory_bytes"],
        "validator_checks_passed": FINAL_EXPECTED["backend_validator_check_count"],
        "validator_checks_total": FINAL_EXPECTED["backend_validator_check_count"],
        "validator_check_names": FINAL_EXPECTED["backend_check_names"],
        "placeholder_count": 0,
        "publication_blockers": [],
        "validation_target": "qa/b006-backend/exports",
        "live_backend_mutated": False,
        "boundary_admitted": False,
        "promotion_performed": False,
    }
    for key, expected in required_receipt.items():
        require(receipt.get(key) == expected, f"backend stage receipt field {key} mismatch", errors)
    require(
        receipt.get("final_input_manifest") == expected_identity("final_inputs"),
        "backend stage receipt final-input identity mismatch",
        errors,
    )
    tooling = receipt.get("tooling", {})
    require(
        tooling.get("generator") == artifact_fixed("backend_generator")
        and tooling.get("validator") == artifact_fixed("backend_validator"),
        "backend stage tooling identity mismatch",
        errors,
    )
    checks = receipt.get("checks", [])
    require(
        isinstance(checks, list)
        and [item.get("name") for item in checks if isinstance(item, dict)]
        == FINAL_EXPECTED["backend_check_names"]
        and all(
            isinstance(item, dict)
            and set(item) == {"name", "result", "detail"}
            and item.get("result") == "passed"
            and isinstance(item.get("detail"), str)
            and bool(item.get("detail"))
            for item in checks
        ),
        "backend stage did not pass the exact ordered 28-check inventory",
        errors,
    )

    stage_inventory = inventory_identity(STAGE_EXPORTS)
    require(
        stage_inventory[0] == FINAL_EXPECTED["backend_stage_inventory_sha256"]
        and stage_inventory[1] == FINAL_EXPECTED["backend_stage_inventory_file_count"]
        and stage_inventory[2] == FINAL_EXPECTED["backend_stage_inventory_bytes"]
        and stage_inventory[1] == FINAL_EXPECTED["backend_payload_count"]
        and stage_inventory[2] == FINAL_EXPECTED["backend_payload_bytes"],
        "backend staged inventory identity/count/bytes mismatch",
        errors,
    )
    stage_payloads = stage_inventory[3]
    require(
        stage_payloads.get("manifest.json") == stage_manifest_raw,
        "backend staged manifest is not the bound manifest byte stream",
        errors,
    )

    require(
        manifest.get("$schema") == "schemas/backend-manifest-v0.1.0.schema.json"
        and manifest.get("schema_version") == "0.1.0"
        and manifest.get("namespace_uuid") == str(BACKEND_NAMESPACE)
        and manifest.get("authority", {}).get("repository") == AUTHORITY_REPOSITORY
        and manifest.get("authority", {}).get("commit") == AUTHORITY_COMMIT
        and manifest.get("authority", {}).get("tree") == AUTHORITY_TREE,
        "backend manifest schema/authority/namespace mismatch",
        errors,
    )
    require(
        manifest.get("record_counts") == FINAL_EXPECTED["backend_record_counts"]
        and sum(FINAL_EXPECTED["backend_record_counts"].values())
        == FINAL_EXPECTED["backend_record_count"],
        "backend manifest record inventory is not the exact bound final inventory",
        errors,
    )
    require(
        manifest.get("source_closure")
        == {
            "status": "passed",
            "file_count": 1195,
            "file_bytes": 41205947,
            "source_qa_sha256": FIXED_EXPECTED["source_qa"][2],
            "target_manifest_sha256": FIXED_EXPECTED["target_manifest"][2],
        }
        and manifest.get("publication_eligibility")
        == "boundary_ready_for_separate_admission"
        and manifest.get("publication_blockers") == []
        and manifest.get("placeholder_count") == 0,
        "backend manifest source/publication state is incomplete or blocked",
        errors,
    )
    scope = manifest.get("scope", {})
    require(
        scope.get("base_boundary") == "R011-B005"
        and scope.get("unit") == "Complete Section 2.2 Considering categorical data"
        and scope.get("end_of_section_exercises") == EXPECTED_EXERCISES
        and scope.get("public_answers") == EXPECTED_PUBLIC_ANSWERS
        and scope.get("o001_gaps") == EXPECTED_O001_GAPS
        and scope.get("translation_segment_count") == 21
        and scope.get("localized_asset_count") == 13
        and scope.get("source_witness_count") == 13
        and scope.get("producer_count") == 8
        and scope.get("target_locale") == "id-ID",
        "backend semantic scope mismatch",
        errors,
    )
    final_gates = manifest.get("final_gates", {})
    require(
        manifest.get("accepted_source_identity", {}).get("source_qa")
        == artifact_fixed("source_qa")
        and manifest.get("accepted_source_identity", {}).get("target_manifest")
        == artifact_fixed("target_manifest")
        and manifest.get("accepted_source_identity", {}).get("body")
        == artifact_fixed("body")
        and manifest.get("accepted_source_identity", {}).get("exercises")
        == artifact_fixed("exercises")
        and manifest.get("accepted_source_identity", {}).get("answers")
        == artifact_fixed("answers")
        and manifest.get("asset_closure", {}).get("status") == "passed"
        and manifest.get("asset_closure", {}).get("severity_counts") == ZERO_SEVERITY
        and final_gates.get("status") == "passed_exact_v4_inputs_stage_only"
        and final_gates.get("candidate_pdf_promoted") is False
        and final_gates.get("build_gate_script") == expected_identity("build_gate_script")
        and final_gates.get("candidate_build_qa") == expected_identity("candidate_build_qa")
        and final_gates.get("build_qa") == expected_identity("build_qa")
        and final_gates.get("build_log") == expected_identity("build_log")
        and final_gates.get("build_text") == expected_identity("build_text")
        and final_gates.get("reviewed_candidate_pdf")
        == {
            **expected_identity("final_pdf"),
            "page_count": FINAL_EXPECTED["page_count"],
        }
        and final_gates.get("render_manifest")
        == {
            **expected_identity("render_manifest"),
            "page_count": FINAL_EXPECTED["rendered_page_count"],
        }
        and final_gates.get("page_locator") == expected_identity("render_page_locator")
        and final_gates.get("contact_sheet") == expected_identity("render_contact_sheet")
        and final_gates.get("visual_audit") == expected_identity("visual_audit")
        and final_gates.get("visual_finalizer") == artifact_fixed("visual_finalizer")
        and final_gates.get("severity_counts") == ZERO_VISUAL_SEVERITY,
        "backend manifest does not bind the final source/asset/build/visual gates",
        errors,
    )
    require(
        final_gates.get("input_manifest_sha256")
        == FINAL_EXPECTED["final_inputs"]["sha256"]
        and final_gates.get("rendered_page_count") == FINAL_EXPECTED["rendered_page_count"]
        and final_gates.get("inspected_pages") == final["pages"],
        "backend manifest final-input/render-count binding mismatch",
        errors,
    )
    require(
        manifest.get("stage_state")
        == {
            "status": "validated_candidate_not_promoted",
            "live_backend_mutated": False,
            "boundary_admitted": False,
            "promotion_performed": False,
        },
        "backend manifest stage state is not the validated nonpromoted state",
        errors,
    )

    entries = manifest.get("files", [])
    require(
        isinstance(entries, list)
        and len(entries) == FINAL_EXPECTED["backend_manifest_file_entry_count"],
        "backend manifest file-entry count mismatch",
        errors,
    )
    entry_paths: list[str] = []
    if isinstance(entries, list):
        for number, entry in enumerate(entries, 1):
            if not isinstance(entry, dict):
                errors.append(f"backend manifest entry {number} is not an object")
                continue
            require(
                set(entry) == {"path", "bytes", "sha256", "records"},
                f"backend manifest entry {number} schema mismatch",
                errors,
            )
            relative = entry.get("path")
            if not isinstance(relative, str):
                errors.append(f"backend manifest entry {number} path missing")
                continue
            entry_paths.append(relative)
            path = backend_entry_path(STAGE_EXPORTS, relative)
            if path is None or not path.is_file():
                errors.append(f"backend manifest payload missing/unsafe: {relative}")
                continue
            payload = path.read_bytes()
            require(
                len(payload) == entry.get("bytes") and sha256(payload) == entry.get("sha256"),
                f"backend manifest payload identity mismatch: {relative}",
                errors,
            )
    require(len(entry_paths) == len(set(entry_paths)), "duplicate backend manifest path", errors)
    payload_entry_paths = {path for path in entry_paths if not path.startswith("schemas/")}
    require(
        payload_entry_paths == set(stage_payloads) - {"manifest.json"}
        and set(BACKEND_RECORD_PATHS.values()) <= payload_entry_paths
        and "identity_map.jsonl" in payload_entry_paths,
        "backend manifest does not cover the exact staged payload set",
        errors,
    )

    all_records: list[dict[str, Any]] = []
    base_record_count = 0
    new_record_count = 0
    record_ids: list[object] = []
    stable_keys: list[object] = []
    for collection, relative in BACKEND_RECORD_PATHS.items():
        rows, lines = load_canonical_jsonl(STAGE_EXPORTS / relative, relative, errors)
        require(
            len(rows) == FINAL_EXPECTED["backend_record_counts"][collection],
            f"backend {collection} record count mismatch",
            errors,
        )
        require(
            [row.get("id") for row in rows] == sorted(row.get("id") for row in rows),
            f"backend {relative} is not UUID-sorted",
            errors,
        )
        base_lines: list[str] = []
        for row, line in zip(rows, lines):
            record_ids.append(row.get("id"))
            stable_keys.append(row.get("stable_key"))
            require(
                row.get("id") == str(uuid.uuid5(BACKEND_NAMESPACE, str(row.get("stable_key")))),
                f"backend stable ID mismatch in {relative}",
                errors,
            )
            if row.get("boundary_id") == "R011-B006":
                new_record_count += 1
                require(
                    row.get("status") not in {"blocked", "pending"}
                    and row.get("result") not in {"blocked", "pending"}
                    and row.get("placeholder") is not True,
                    f"B006 backend record is blocked/pending/placeholder: {row.get('id')}",
                    errors,
                )
            else:
                base_record_count += 1
                base_lines.append(line)
        # The generator freezes each admitted B005 collection.  Importing its
        # constants is unnecessary: the B006 stage validator's exact receipt,
        # validator hash, and additive-preservation check bind these bytes.
        require(bool(base_lines), f"backend {relative} lost all admitted base rows", errors)
        all_records.extend(rows)
    require(
        len(all_records) == FINAL_EXPECTED["backend_record_count"]
        and base_record_count == BASE_RECORD_COUNT
        and new_record_count == FINAL_EXPECTED["backend_added_record_count"]
        and len(set(record_ids)) == FINAL_EXPECTED["backend_record_count"]
        and len(set(stable_keys)) == FINAL_EXPECTED["backend_record_count"],
        "backend typed inventory is not the exact preserved-plus-additive unique record set",
        errors,
    )
    gap_ids = {
        row.get("id")
        for row in all_records
        if row.get("boundary_id") == "R011-B006"
        and row.get("unit_type") == "companion_gap"
    }
    queued_ids = {
        row.get("id")
        for row in all_records
        if row.get("boundary_id") == "R011-B006"
        and row.get("translation_state") == "queued"
    }
    require(
        len(gap_ids) == 2 and queued_ids == gap_ids,
        "backend has queued state outside the two explicit O001 companion gaps",
        errors,
    )

    identity_rows, _identity_lines = load_canonical_jsonl(
        STAGE_EXPORTS / "identity_map.jsonl", "identity_map.jsonl", errors
    )
    expected_identity_rows = sorted(
        (
            {
                "id": row["id"],
                "record_type": row["record_type"],
                "source_local_ids": row.get("source_local_ids", []),
                "stable_key": row["stable_key"],
            }
            for row in all_records
        ),
        key=lambda row: row["id"],
    )
    require(
        identity_rows == expected_identity_rows,
        "backend identity map is not the exact bound final-record projection",
        errors,
    )

    ids = set(record_ids)
    unresolved: list[tuple[object, str, object]] = []
    resolved = 0
    singular_exclusions = {"id", "backend_id", "workflow_id", "boundary_id"}
    plural_exclusions = {"source_local_ids", "data_ids", "target_locales"}
    for row in all_records:
        for key, value in row.items():
            if key in singular_exclusions or value is None:
                continue
            if key.endswith("_id") and isinstance(value, str):
                if value in ids:
                    resolved += 1
                else:
                    unresolved.append((row.get("id"), key, value))
            elif key.endswith("_ids") and key not in plural_exclusions and isinstance(value, list):
                for item in value:
                    if isinstance(item, str) and item in ids:
                        resolved += 1
                    elif isinstance(item, str):
                        unresolved.append((row.get("id"), key, item))
    require(not unresolved, f"backend has unresolved references: {unresolved[:3]}", errors)
    require(
        resolved == FINAL_EXPECTED["backend_resolved_reference_count"],
        "backend resolved-reference count mismatch",
        errors,
    )
    require(
        not recursively_has_marker(manifest) and not recursively_has_marker(receipt),
        "backend manifest/receipt contains TODO/TBD/UNSET markers",
        errors,
    )
    return {
        "receipt": receipt,
        "manifest": manifest,
        "payloads": stage_payloads,
        "record_count": len(all_records),
        "resolved_reference_count": resolved,
    }


def live_backend_state(
    stage: dict[str, Any], require_promoted: bool, errors: list[str]
) -> dict[str, Any]:
    _digest, live_count, live_bytes, live_payloads = inventory_identity(LIVE_EXPORTS)
    staged = stage["payloads"]
    exact = live_payloads == staged
    if require_promoted:
        require(exact, "live backend is not the exact promoted B006 stage", errors)
    return {
        "exact": exact,
        "file_count": live_count,
        "bytes": live_bytes,
        "manifest": (
            identity_bytes(live_payloads["manifest.json"])
            if "manifest.json" in live_payloads
            else None
        ),
    }


def construct_receipt(
    fixed: dict[str, Any], final: dict[str, Any], backend: dict[str, Any]
) -> dict[str, Any]:
    build = final["build"]
    visual = final["visual"]
    delta_raw = canonical_json(fixed["delta"])
    return {
        "schema": "openintro-id-boundary-receipt",
        "schema_version": "0.6.0",
        "boundary_id": "R011-B006",
        "status": "admitted",
        "admitted_at": ADMISSION_DATE,
        "authority": {
            "repository": AUTHORITY_REPOSITORY,
            "commit": AUTHORITY_COMMIT,
            "tree": AUTHORITY_TREE,
            "repository_license": "CC BY-SA 3.0 Unported",
            "derivative_requirements": [
                "attribution",
                "share-alike",
                "title and branding separation",
                "component-level provenance",
            ],
        },
        "prior_boundary": {
            "boundary_id": "R011-B005",
            "receipt": artifact_fixed("prior_boundary_receipt"),
            "target_manifest": artifact_fixed("prior_target_manifest"),
            "record_count": BASE_RECORD_COUNT,
            "preserved_exact": True,
        },
        "scope": {
            "instructional_unit": "Complete Section 2.2 Considering categorical data",
            "body": artifact_fixed("body"),
            "exercises_source": artifact_fixed("exercises"),
            "public_answers_source": artifact_fixed("answers"),
            "exercise_numbers": EXPECTED_EXERCISES,
            "translated_public_answers": EXPECTED_PUBLIC_ANSWERS,
            "no_public_answer_o001_gaps": EXPECTED_O001_GAPS,
            "restricted_instructor_solutions_accessed_or_invented": False,
            "localized_figure_count": 13,
            "english_figure_witness_count": 13,
            "authority_exact_figure_producer_count": 8,
            "next_untranslated_marker": "ch_summarizing_data/TeX/ch_summarizing_data.tex / Section 2.3 Case study: malaria vaccine",
        },
        "target_closure": {
            "file_count": 1195,
            "bytes": 41205947,
            "manifest": artifact_fixed("target_manifest"),
            "base_boundary": "R011-B005",
            "base_file_count": 1182,
            "base_bytes": 41144346,
            "added_file_count": 13,
            "added_file_bytes": 65607,
            "changed_file_count": 16,
            "changed_file_net_bytes": -4006,
            "unchanged_file_count": 1166,
            "removed_file_count": 0,
            "net_added_bytes": 61601,
            "actual_repo_inventory_replayed": True,
            "delta": {"bytes": len(delta_raw), "sha256": sha256(delta_raw)},
        },
        "source_qa": {
            "result": "passed",
            "receipt": artifact_fixed("source_qa"),
            "gate_script": artifact_fixed("source_gate_script"),
            "preapplication": artifact_fixed("preapplication"),
            "source_application": artifact_fixed("source_application"),
            "post_build_repair": artifact_fixed("repair_receipt"),
            "layout_repair_v3": artifact_fixed("layout_repair_receipt_v3"),
            "layout_repair_v4": artifact_fixed("layout_repair_receipt_v4"),
            "active_reader_visible_english": 0,
            "placeholders": 0,
            "reverse_reconstruction": "passed",
        },
        "rejected_candidate_history": {
            "accepted_as_final": False,
            "candidates": [
                {
                    "candidate": "final-v1",
                    "status": "rejected_visual",
                    "build_receipt": artifact_fixed("rejected_build_v1"),
                    "visual_findings": artifact_fixed("rejected_visual_v1"),
                    "candidate_pdf_sha256": REJECTED_V1_PDF_SHA256,
                    "severity_counts": {"P1": 0, "P2": 2, "P3": 0},
                },
                {
                    "candidate": "final-v2",
                    "status": "rejected_visual",
                    "build_receipt": artifact_fixed("rejected_build_v2"),
                    "visual_findings": artifact_fixed("rejected_visual_v2"),
                    "candidate_pdf_sha256": REJECTED_V2_PDF_SHA256,
                    "severity_counts": {"P1": 0, "P2": 2, "P3": 0},
                },
                {
                    "candidate": "final-v3",
                    "status": "rejected_visual",
                    "build_receipt": artifact_fixed("rejected_build_v3"),
                    "visual_findings": artifact_fixed("rejected_visual_v3"),
                    "candidate_pdf_sha256": REJECTED_V3_PDF_SHA256,
                    "severity_counts": {"P1": 0, "P2": 1, "P3": 0},
                },
            ],
        },
        "controls_and_rights": {
            "component_rights": artifact_fixed("component_rights"),
            "terminology": {**artifact_fixed("terminology"), "rows": 141},
            "adverse_ledger": {**artifact_fixed("adverse"), "rows": 79},
            "rights_summary": (
                "Text/localized derivatives remain CC BY-SA 3.0; data and generated "
                "figure closure is recorded by smallest component, with the OpenIntro "
                "R package retained as a separate GPL-3 build dependency."
            ),
        },
        "figures": {
            "result": "passed",
            "asset_manifest": artifact_fixed("asset_manifest"),
            "asset_validation_receipt": artifact_fixed("asset_receipt"),
            "localizer": artifact_fixed("asset_localizer"),
            "localized_pdf_count": 13,
            "source_witness_count": 13,
            "producer_count": 8,
            "deterministic_replays": 2,
            "same_renderer_visual_pairs": {"Poppler": 13, "MuPDF": 13},
            "severity_counts": ZERO_SEVERITY,
        },
        "build": {
            "result": "passed",
            "receipt": expected_identity("build_qa"),
            "gate_script": expected_identity("build_gate_script"),
            "candidate_receipt": expected_identity("candidate_build_qa"),
            "log": expected_identity("build_log"),
            "text": expected_identity("build_text"),
            "recorder": expected_identity("build_recorder"),
            "pass3_pdf": expected_identity("pass3_pdf"),
            "final_pdf": expected_identity("final_pdf"),
            "two_final_pass_hashes_equal": True,
            "page_count": FINAL_EXPECTED["page_count"],
            "fatal_errors": 0,
            "latex_errors": 0,
            "undefined_references_or_citations": 0,
            "missing_destinations": 0,
            "missing_characters": 0,
            "warning_counts": {
                key: value
                for key, value in build.get("final_log", {}).items()
                if key.endswith("warnings")
            },
        },
        "artifact": {
            **expected_identity("promoted_pdf"),
            "promoted_and_read_back": True,
            "pages": FINAL_EXPECTED["page_count"],
            "title": "Statistika Berbasis Data",
            "lang": "id-ID",
            "tagged": False,
            "encrypted": False,
            "missing_link_targets": 0,
        },
        "visual_qa": {
            "result": "passed",
            "parent_review_binding": "exact identity assigned only after main-agent full-resolution review",
            "audit": expected_identity("visual_audit"),
            "render_manifest": expected_identity("render_manifest"),
            "page_locator": expected_identity("render_page_locator"),
            "contact_sheet": expected_identity("render_contact_sheet"),
            "page_locator": expected_identity("render_page_locator"),
            "contact_sheet": expected_identity("render_contact_sheet"),
            "severity_counts": ZERO_VISUAL_SEVERITY,
            "inspected_pages": final["pages"],
            "inspection_resolution_dpi": visual.get("parent_acceptance", {}).get(
                "inspection_resolution_dpi"
            ),
            "clipping_overlap_underfill_or_centering_defects": 0,
            "localized_figure_defects": 0,
        },
        "backend": {
            "status": "passed",
            "base_boundary": "R011-B005",
            "base_record_count": BASE_RECORD_COUNT,
            "preserved_base_record_count": BASE_RECORD_COUNT,
            "base_records_preserved_exact": True,
            "record_count": FINAL_EXPECTED["backend_record_count"],
            "added_record_count": FINAL_EXPECTED["backend_added_record_count"],
            "resolved_reference_count": FINAL_EXPECTED["backend_resolved_reference_count"],
            "authority_span_count": FINAL_EXPECTED["backend_authority_span_count"],
            "localization_slice_count": 21,
            "artifact_count": FINAL_EXPECTED["backend_artifact_count"],
            "placeholder_count": 0,
            "pending_count": 0,
            "publication_blocker_count": 0,
            "stage_manifest": expected_identity("backend_stage_manifest"),
            "live_manifest": {
                "path": "backend/exports/manifest.json",
                "bytes": FINAL_EXPECTED["backend_stage_manifest"]["bytes"],
                "sha256": FINAL_EXPECTED["backend_stage_manifest"]["sha256"],
            },
            "stage_validation_receipt": expected_identity("backend_stage_receipt"),
            "final_input_manifest": expected_identity("final_inputs"),
            "generator": artifact_fixed("backend_generator"),
            "validator": artifact_fixed("backend_validator"),
            "validator_checks_passed": FINAL_EXPECTED["backend_validator_check_count"],
            "validator_checks_total": FINAL_EXPECTED["backend_validator_check_count"],
            "stage_live_exact": True,
            "promotion": {
                "mode": "explicit --promote",
                "file_count": FINAL_EXPECTED["backend_stage_inventory_file_count"],
                "payload_bytes": FINAL_EXPECTED["backend_stage_inventory_bytes"],
                "inventory_sha256": FINAL_EXPECTED["backend_stage_inventory_sha256"],
                "deleted_paths": [],
                "readback_exact": True,
            },
        },
        "admission_script": {
            "path": Path(__file__).relative_to(LANE).as_posix(),
            **identity_bytes(Path(__file__).read_bytes()),
        },
        "limitations": [
            "Section 2.3 and later instructional content remains upstream English after this admitted boundary.",
            "Exercises 2.22 and 2.24 have no public upstream answer and remain explicit O001 gaps.",
            "The PDF declares id-ID but is not structurally tagged; a final accessible reader remains required.",
            "The visual audit is boundary-specific and binds every candidate page selected by the deterministic locator, not all pages in the whole-book working PDF.",
        ],
        "publication_state": "not_published_by_admission_guard",
        "next_cursor": {
            "boundary_id": "R011-B007",
            "source_path": "ch_summarizing_data/TeX/ch_summarizing_data.tex",
            "source_anchor": "malariaVaccine",
            "instructional_unit": "Section 2.3 Case study: malaria vaccine",
        },
    }


def evaluate(require_promoted: bool = True) -> tuple[bytes | None, list[str], dict[str, Any]]:
    errors: list[str] = []
    fixed = validate_fixed_evidence(errors)
    ready = final_bindings_ready(errors)
    context: dict[str, Any] = {"fixed_evidence_passed": not errors and ready}
    if not ready:
        context["fixed_evidence_passed"] = not any(
            not item.startswith("final-v4-or-later/backend bindings unset") for item in errors
        )
        return None, errors, context
    final = validate_final_evidence(errors, require_promoted)
    backend = validate_backend_stage(final, errors)
    live = live_backend_state(backend, require_promoted, errors)
    promoted_pdf = lane_path(str(FINAL_EXPECTED["promoted_pdf"]["path"]))
    candidate_pdf = lane_path(str(FINAL_EXPECTED["final_pdf"]["path"]))
    if require_promoted:
        require(
            promoted_pdf.is_file()
            and candidate_pdf.is_file()
            and promoted_pdf.read_bytes() == candidate_pdf.read_bytes(),
            "canonical B006 PDF is not the exact promoted final-v4-or-later byte stream",
            errors,
        )
    context.update({"fixed": fixed, "final": final, "backend": backend, "live": live})
    if errors:
        return None, errors, context
    receipt = construct_receipt(fixed, final, backend)
    return canonical_json(receipt), errors, context


def atomic_write(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        if temporary.read_bytes() != raw:
            raise RuntimeError(f"temporary readback mismatch: {path}")
        os.replace(temporary, path)
        if path.read_bytes() != raw:
            raise RuntimeError(f"post-write readback mismatch: {path}")
    finally:
        if temporary.exists():
            temporary.unlink()


def promote(context: dict[str, Any]) -> dict[str, Any]:
    backend = context["backend"]
    staged: dict[str, bytes] = backend["payloads"]
    live_digest, live_count_before, live_bytes_before, live = inventory_identity(LIVE_EXPORTS)
    backend_already_exact = live == staged
    if not backend_already_exact:
        if (
            live_digest != B005_LIVE_INVENTORY_SHA256
            or live_count_before != B005_LIVE_INVENTORY_FILE_COUNT
            or live_bytes_before != B005_LIVE_INVENTORY_BYTES
        ):
            raise RuntimeError(
                "refusing backend promotion: live backend is neither the exact admitted "
                "B005 inventory nor the exact reviewed B006 stage"
            )
        if not set(live) <= set(staged):
            raise RuntimeError(
                "refusing backend promotion because the exact B005 inventory is not an "
                "additive subset of the reviewed B006 stage"
            )

    # Complete every destructive/conflict preflight before the first write.  The
    # explicit promotion transaction then uses same-directory atomic replaces,
    # writes the backend manifest last, and rolls every exact target back if any
    # write or readback fails.
    candidate_pdf = lane_path(str(FINAL_EXPECTED["final_pdf"]["path"]))
    promoted_pdf = lane_path(str(FINAL_EXPECTED["promoted_pdf"]["path"]))
    candidate_raw = candidate_pdf.read_bytes()
    pdf_before = promoted_pdf.read_bytes() if promoted_pdf.is_file() else None
    if promoted_pdf.exists() and pdf_before != candidate_raw:
        raise RuntimeError("refusing to overwrite a nonmatching canonical B006 PDF")

    backend_order = (
        []
        if backend_already_exact
        else sorted(path for path in staged if path != "manifest.json") + ["manifest.json"]
    )
    backend_before = {relative: live.get(relative) for relative in backend_order}
    pdf_written = pdf_before is None
    try:
        for relative in backend_order:
            atomic_write(LIVE_EXPORTS / relative, staged[relative])
        if pdf_before is None:
            atomic_write(promoted_pdf, candidate_raw)

        live_digest_after, live_count, live_bytes, live_after = inventory_identity(LIVE_EXPORTS)
        if (
            live_after != staged
            or live_digest_after != FINAL_EXPECTED["backend_stage_inventory_sha256"]
            or live_count != FINAL_EXPECTED["backend_stage_inventory_file_count"]
            or live_bytes != FINAL_EXPECTED["backend_stage_inventory_bytes"]
        ):
            raise RuntimeError("post-promotion live backend readback differs from stage")
        if promoted_pdf.read_bytes() != candidate_raw:
            raise RuntimeError(
                "post-promotion PDF readback differs from final-v4-or-later candidate"
            )
    except Exception as promotion_error:
        rollback_errors: list[str] = []
        for relative in reversed(backend_order):
            destination = LIVE_EXPORTS / relative
            before = backend_before[relative]
            try:
                if before is None:
                    if destination.exists():
                        destination.unlink()
                else:
                    atomic_write(destination, before)
            except Exception as exc:
                rollback_errors.append(f"backend/{relative}: {exc}")
        try:
            if pdf_before is None:
                if promoted_pdf.exists():
                    promoted_pdf.unlink()
            else:
                atomic_write(promoted_pdf, pdf_before)
        except Exception as exc:
            rollback_errors.append(f"PDF: {exc}")
        rollback_digest, rollback_count, rollback_bytes, rollback_live = inventory_identity(
            LIVE_EXPORTS
        )
        if (
            rollback_live != live
            or rollback_digest != live_digest
            or rollback_count != live_count_before
            or rollback_bytes != live_bytes_before
        ):
            rollback_errors.append("backend inventory did not return to its exact pre-state")
        if (promoted_pdf.read_bytes() if promoted_pdf.is_file() else None) != pdf_before:
            rollback_errors.append("PDF did not return to its exact pre-state")
        if rollback_errors:
            raise RuntimeError(
                f"promotion failed ({promotion_error}); rollback also failed: {rollback_errors}"
            ) from promotion_error
        raise RuntimeError(f"promotion failed and exact rollback passed: {promotion_error}") from promotion_error

    return {
        "status": "passed",
        "backend_files_written": len(backend_order),
        "backend_file_count": live_count,
        "backend_payload_bytes": live_bytes,
        "backend_inventory_sha256": FINAL_EXPECTED["backend_stage_inventory_sha256"],
        "pdf_written": pdf_written,
        "pdf": expected_identity("promoted_pdf"),
        "deleted_paths": [],
        "readback_exact": True,
    }


def self_test() -> list[str]:
    failures: list[str] = []
    try:
        lane_path("../escape")
        failures.append("unsafe parent path was accepted")
    except ValueError:
        pass
    try:
        lane_path(str(LANE.resolve()))
        failures.append("absolute path was accepted")
    except ValueError:
        pass
    if not recursively_has_marker({"x": "TBD"}):
        failures.append("TBD marker was not detected")
    if recursively_has_marker({"x": "validated candidate"}):
        failures.append("ordinary status text produced a false marker")
    if not recursively_find_unset({"x": {"y": None}}) == ["x.y"]:
        failures.append("nested unset binding was not located")
    sample = {"b": 1, "a": "é"}
    if canonical_json(sample) != canonical_json(sample):
        failures.append("canonical JSON is not deterministic")
    malformed_errors: list[str] = []
    parse_manifest(
        b"a\t1\t" + b"0" * 64 + b"\r\n",
        "adversarial",
        1,
        1,
        malformed_errors,
    )
    if not malformed_errors:
        failures.append("CRLF manifest was not rejected")
    if not contains_identity(
        {"nested": {"bytes": 7, "sha256": "0" * 64}},
        {"bytes": 7, "sha256": "0" * 64},
        require_path=False,
    ):
        failures.append("nested exact identity was not found")
    return failures


def result_payload(
    status: str,
    errors: Iterable[str],
    wrote: bool = False,
    promoted: bool = False,
    candidate: dict[str, object] | None = None,
    extra: dict[str, Any] | None = None,
) -> str:
    value: dict[str, Any] = {
        "boundary_id": "R011-B006",
        "status": status,
        "errors": list(errors),
        "output": OUTPUT.relative_to(LANE).as_posix(),
        "output_exists": OUTPUT.exists(),
        "wrote": wrote,
        "promoted": promoted,
    }
    if candidate is not None:
        value["candidate"] = candidate
    if extra:
        value.update(extra)
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Guarded deterministic R011-B006 admission and exact promotion"
    )
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument(
        "--promote",
        action="store_true",
        help="promote exact final-v4-or-later PDF/backend only after every stage gate passes",
    )
    modes.add_argument(
        "--write",
        action="store_true",
        help="write the receipt only after canonical PDF/backend read back exact",
    )
    modes.add_argument(
        "--self-test",
        action="store_true",
        help="run pure fail-closed helper tests without changing corpus state",
    )
    args = parser.parse_args()

    if args.self_test:
        failures = self_test()
        print(
            result_payload(
                "pass" if not failures else "failed",
                failures,
                extra={"self_test_count": 8, "mutation_performed": False},
            )
        )
        return 0 if not failures else 1

    if args.promote:
        _receipt, errors, context = evaluate(require_promoted=False)
        # A missing canonical PDF is expected before this explicit mode; remove
        # only that one promotion-state diagnostic after every other gate passed.
        promotion_only = "canonical B006 PDF is not the exact promoted final-v4-or-later byte stream"
        errors = [item for item in errors if item != promotion_only]
        if errors:
            print(result_payload("refused", errors))
            return 2
        try:
            promotion = promote(context)
        except Exception as exc:
            print(result_payload("failed", [str(exc)]))
            return 1
        receipt_raw, post_errors, _post_context = evaluate(require_promoted=True)
        if post_errors or receipt_raw is None:
            print(result_payload("failed", post_errors, promoted=True, extra={"promotion": promotion}))
            return 1
        print(
            result_payload(
                "pass",
                [],
                promoted=True,
                candidate=identity_bytes(receipt_raw),
                extra={"promotion": promotion},
            )
        )
        return 0

    receipt_raw, errors, context = evaluate(require_promoted=True)
    if errors or receipt_raw is None:
        print(
            result_payload(
                "refused",
                errors,
                extra={"fixed_evidence_passed": context.get("fixed_evidence_passed", False)},
            )
        )
        return 2

    candidate = identity_bytes(receipt_raw)
    if args.write:
        if OUTPUT.exists() and OUTPUT.read_bytes() != receipt_raw:
            print(
                result_payload(
                    "refused",
                    ["existing B006 boundary receipt differs; refusing overwrite"],
                    candidate=candidate,
                )
            )
            return 2
        if not OUTPUT.exists():
            atomic_write(OUTPUT, receipt_raw)
        if OUTPUT.read_bytes() != receipt_raw:
            print(result_payload("failed", ["boundary receipt readback mismatch"]))
            return 1
        wrote = True
    else:
        if OUTPUT.exists() and OUTPUT.read_bytes() != receipt_raw:
            print(
                result_payload(
                    "refused",
                    ["read-only replay differs from existing B006 boundary receipt"],
                    candidate=candidate,
                )
            )
            return 2
        wrote = False
    print(result_payload("pass", [], wrote=wrote, candidate=candidate))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
