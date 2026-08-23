#!/usr/bin/env python3
"""Fail-closed exact admission transaction for R011-B008.

The default mode is read-only. ``--promote`` is the only mutating mode, and it
remains unavailable while any finalized B008 backend binding below is unset.
The transaction binds the terminal V3 source/build/visual chain, replays the
final isolated backend, preserves the exact admitted B007 preimages for
rollback, promotes the reviewed PDF and backend with narrow atomic writes, and
then performs an exact post-admission replay.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import tempfile
import unicodedata
from pathlib import Path
from typing import Any


LANE = Path(__file__).resolve().parents[1]
GENERATOR_PATH = LANE / "scripts" / "generate_backend_b008_v3.py"
FINALIZER_PATH = LANE / "scripts" / "finalize_backend_b008_v3.py"
VALIDATOR_PATH = LANE / "scripts" / "validate_backend_b008_v3.py"
BASE_STAGE_EXPORTS = LANE / "qa" / "b007-backend" / "exports"
LIVE_EXPORTS = LANE / "backend" / "exports"
STAGE_EXPORTS = LANE / "qa" / "b008-backend-final-v3" / "exports"
VALIDATION_RECEIPT_PATH = LANE / "qa" / "b008-backend-final-v3" / "BACKEND_VALIDATION_RECEIPT_R011-B008-FINAL-V3.json"
TRANSACTION_LOCK_PATH = LANE / "qa" / "b008-backend-final-v3" / ".R011-B008-admission.lock"
TRANSACTION_JOURNAL_PATH = LANE / "qa" / "b008-backend-final-v3" / "R011-B008_ADMISSION_TRANSACTION_JOURNAL.json"
BOUNDARY_RECEIPT_PATH = LANE / "qa" / "R011-B008_BOUNDARY_RECEIPT.json"
BASE_PDF_PATH = LANE / "output" / "pdf" / "statistika-berbasis-data-batas-R011-B007.pdf"
PROMOTED_PDF_PATH = LANE / "output" / "pdf" / "statistika-berbasis-data-batas-R011-B008.pdf"
BOUNDARY_ID = "R011-B008"
RECORDED_AT = "2026-08-23T12:00:00+02:00"


BASE_EXPECTED: dict[str, Any] = {
    "boundary_id": "R011-B007",
    "boundary_receipt": {
        "path": "qa/R011-B007_BOUNDARY_RECEIPT.json",
        "bytes": 3099,
        "sha256": "e6aac35e979af6dbf36ac2256ec7be3f73745dadaad2f84d29aa56c67f1f92ba",
    },
    "manifest": {
        "path": "backend/exports/manifest.json",
        "bytes": 33555,
        "sha256": "3f1d2c0ae5a6011f01e6fa0c6080ccadcfa1a651f131002058afd6e610e55d12",
    },
    "record_count": 2264,
    "inventory_file_count": 102,
    "inventory_bytes": 7018282,
    "inventory_sha256": "ffd32f5a6211b3c0a1513ee596dff769f3598fe6ff596f3d0af8f93a384e9133",
    "canonical_pdf": {
        "path": "output/pdf/statistika-berbasis-data-batas-R011-B007.pdf",
        "bytes": 22017185,
        "sha256": "ca872ddbc2fb1cab5f6cdb2fe745a0711a315fef68ab2e72c7a11d1c633a5c1a",
        "page_count": 425,
    },
}


# Terminal source/build/visual bindings. These are immutable admission inputs,
# not discovery hints. The exact root visual audit also binds every inspected
# 300-dpi page identity.
FIXED_GATE_EXPECTED: dict[str, dict[str, Any]] = {
    "source_gate_script": {
        "path": "scripts/qa_source_b008_v3.py",
        "bytes": 17988,
        "sha256": "d282684639300c409a2f36940ad3c0530e62261196bcb23e86d2d1951f8b6b80",
    },
    "source_manifest": {
        "path": "qa/b008-source/R011-B008_SOURCE_MANIFEST_V3.tsv",
        "bytes": 175582,
        "sha256": "743b4906fad27bad1adfcb331566517314a93602d6df3c3cc279aa56a88745f4",
    },
    "source_qa": {
        "path": "qa/b008-source/R011-B008_SOURCE_QA_V3.json",
        "bytes": 6896,
        "sha256": "8fd911d8ac4164a51c44d52ce62a3277ac4f63aa2aaca4437f244550f7223a8a",
    },
    "layout_repair_receipt": {
        "path": "qa/b008-source/R011-B008_V2_LAYOUT_REPAIR_RECEIPT.json",
        "bytes": 2506,
        "sha256": "c3c57c19067667e99f8db485274b3834ae56ce66930384f7a4430bfe86286a8f",
    },
    "build_gate_script": {
        "path": "scripts/qa_build_b008_v3.py",
        "bytes": 21820,
        "sha256": "b6e8d4f5505c32db9b81907c6e1a99221fe1e94c8d58ca64aa0f0ea217c628f7",
    },
    "candidate_pdf": {
        "path": "qa/b008-build/final-v3/main.pdf",
        "bytes": 22017328,
        "sha256": "8aa8e6ecc3edc2a33ee8d83a586c6208e49966582b2fc439c8b3007470f32800",
    },
    "build_receipt": {
        "path": "qa/b008-build/final-v3/CANDIDATE_BUILD_QA_V3.json",
        "bytes": 17044,
        "sha256": "5d176e4275dbc41951797a043bb9270a09357ae31418868904d903939ff5beca",
    },
    "independent_visual_record": {
        "path": "qa/b008-build/BUILD_ONLY_VISUAL_SANITY_V3.json",
        "bytes": 2405,
        "sha256": "09fca6423b19e1fd2014a982d687b06119a8203684dd8992c18a19edcd238d99",
    },
    "render_manifest": {
        "path": "qa/b008-build/render-final-v3/FINAL_MANIFEST.tsv",
        "bytes": 800,
        "sha256": "92957fb3e30b23f11393fc0df06e982c5a1864a322b5c01a7084a7be3e6dce68",
    },
    "page_locator": {
        "path": "qa/b008-build/render-final-v3/PAGE_LOCATOR.json",
        "bytes": 1136,
        "sha256": "30c75f8dcc54df0141f6351c6d910ae7ad36f25a2c94954996814a11f967e7e1",
    },
    "contact_sheet": {
        "path": "qa/b008-build/render-final-v3/CONTACT_SHEET.png",
        "bytes": 415203,
        "sha256": "700ae4ed79165e37b1fd6a61bf4feef8ea8bd7bc7bbcaa4e5bbdadf4fb3b14f9",
    },
    "root_visual_audit": {
        "path": "qa/b008-visual/R011-B008_VISUAL_AUDIT_V3.json",
        "bytes": 3085,
        "sha256": "f66bf2cceef66e2b83061fad87a6817719bf2feb9cc6ec6f06718750fb9bdbdc",
    },
}


# Exact terminal-V3 backend bindings supplied only after the isolated final
# generator/finalizer/validator gate passed independently.
ADMISSION_EXPECTED: dict[str, Any] = {
    "stage_manifest": {
        "path": "qa/b008-backend-final-v3/exports/manifest.json",
        "bytes": 28769,
        "sha256": "c87b6402e47b8d606d341c49131a70aea5468a521c9c1731bd4c67cf9c276d68",
    },
    "backend_validation_receipt": {
        "path": "qa/b008-backend-final-v3/BACKEND_VALIDATION_RECEIPT_R011-B008-FINAL-V3.json",
        "bytes": 7297,
        "sha256": "6b64fbaf30502a4744ad41ea443bcad3e51de21d9925f6eab8cc8c62b292bbda",
    },
    "stage_inventory": {
        "file_count": 118,
        "bytes": 7712543,
        "sha256": "eb1e37d42c4bd97a720a1a60001b229e1fefed095635d67588c686713834726f",
    },
    "record_count": 2503,
    "new_record_count": 239,
    "new_final_v3_record_count": 31,
    "validator_check_count": 20,
    "resolved_reference_count": 10844,
    "tooling": {
        "generator": {
            "path": "scripts/generate_backend_b008_v3.py",
            "bytes": 34032,
            "sha256": "1180a39aa74085d5cdb331ae65d3b36be6ac30fc53b5a5b6cd4f36b9b57ed6eb",
        },
        "finalizer": {
            "path": "scripts/finalize_backend_b008_v3.py",
            "bytes": 3076,
            "sha256": "2cb67df32e921860adf295c316f64792ff81dd8b197731ab287949fb8d0a2fde",
        },
        "validator": {
            "path": "scripts/validate_backend_b008_v3.py",
            "bytes": 28388,
            "sha256": "96a3e28f355a3b79435ab6654d19ba827f9303cf8e5e56da289a297cee7d33ab",
        },
    },
    "pdf": {
        "source_path": FIXED_GATE_EXPECTED["candidate_pdf"]["path"],
        "promoted_path": "output/pdf/statistika-berbasis-data-batas-R011-B008.pdf",
        "bytes": FIXED_GATE_EXPECTED["candidate_pdf"]["bytes"],
        "sha256": FIXED_GATE_EXPECTED["candidate_pdf"]["sha256"],
        "page_count": 425,
    },
}


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_json(value: Any) -> bytes:
    normalized = unicodedata.normalize("NFC", json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ))
    return (normalized + "\n").encode("utf-8")


def lane_path(relative: str) -> Path:
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise ValueError(f"path must be portable and lane-relative: {relative!r}")
    item = Path(relative)
    if item.is_absolute() or ".." in item.parts or item.as_posix() != relative:
        raise ValueError(f"path escapes or is noncanonical: {relative!r}")
    root = LANE.resolve()
    resolved = (LANE / item).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"path resolves outside the R011 lane: {relative!r}") from exc
    return resolved


def identity(raw: bytes, path: str | None = None) -> dict[str, Any]:
    value: dict[str, Any] = {"bytes": len(raw), "sha256": sha256(raw)}
    return {"path": path, **value} if path is not None else value


def exact_file(expected: dict[str, Any]) -> bytes:
    path = lane_path(expected["path"])
    if not path.is_file():
        raise RuntimeError(f"required exact file is missing: {expected['path']}")
    raw = path.read_bytes()
    if identity(raw, expected["path"]) != expected:
        raise RuntimeError(f"exact file identity changed: {expected['path']}")
    return raw


def inventory_identity(root: Path) -> tuple[str, int, int, dict[str, bytes]]:
    payloads: dict[str, bytes] = {}
    lines: list[str] = []
    total = 0
    if root.is_dir():
        paths = sorted(
            (item for item in root.rglob("*") if item.is_file()),
            key=lambda item: item.relative_to(root).as_posix(),
        )
        for path in paths:
            relative = path.relative_to(root).as_posix()
            raw = path.read_bytes()
            payloads[relative] = raw
            total += len(raw)
            lines.append(f"{relative}\t{len(raw)}\t{sha256(raw)}\n")
    return sha256("".join(lines).encode("utf-8")), len(lines), total, payloads


def final_v3_inventory_identity(root: Path) -> tuple[str, int, int, dict[str, bytes]]:
    """Replay the final-V3 validator's exact WindowsPath ordering."""
    payloads: dict[str, bytes] = {}
    lines: list[str] = []
    total = 0
    paths = sorted(item for item in root.rglob("*") if item.is_file()) if root.is_dir() else []
    for path in paths:
        relative = path.relative_to(root).as_posix()
        raw = path.read_bytes()
        payloads[relative] = raw
        total += len(raw)
        lines.append(f"{relative}\t{len(raw)}\t{sha256(raw)}\n")
    return sha256("".join(lines).encode("utf-8")), len(lines), total, payloads


def _unset(value: Any, prefix: str = "") -> list[str]:
    gaps: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            gaps.extend(_unset(item, f"{prefix}.{key}" if prefix else key))
    elif value is None:
        gaps.append(prefix)
    return gaps


def admission_binding_gaps() -> list[str]:
    gaps = _unset(ADMISSION_EXPECTED)
    for group in ("stage_manifest", "backend_validation_receipt"):
        item = ADMISSION_EXPECTED[group]
        if item.get("bytes") is not None and (not isinstance(item["bytes"], int) or item["bytes"] <= 0):
            gaps.append(f"{group}.bytes")
        digest = item.get("sha256")
        if digest is not None and (not isinstance(digest, str) or len(digest) != 64):
            gaps.append(f"{group}.sha256")
    for group in ("generator", "finalizer", "validator"):
        item = ADMISSION_EXPECTED["tooling"][group]
        if item.get("bytes") is not None and (not isinstance(item["bytes"], int) or item["bytes"] <= 0):
            gaps.append(f"tooling.{group}.bytes")
        digest = item.get("sha256")
        if digest is not None and (not isinstance(digest, str) or len(digest) != 64):
            gaps.append(f"tooling.{group}.sha256")
    return sorted(set(gaps))


def _contains_identity(value: Any, expected: dict[str, Any]) -> bool:
    if isinstance(value, dict):
        if all(value.get(key) == expected[key] for key in ("path", "bytes", "sha256")):
            return True
        return any(_contains_identity(item, expected) for item in value.values())
    if isinstance(value, list):
        return any(_contains_identity(item, expected) for item in value)
    return False


def assert_fixed_gate_chain() -> dict[str, bytes]:
    raw = {name: exact_file(expected) for name, expected in FIXED_GATE_EXPECTED.items()}
    source = json.loads(raw["source_qa"])
    if (
        source.get("$schema") != "r011-b008-source-qa/v3"
        or source.get("boundary_id") != BOUNDARY_ID
        or source.get("status") != "PASS_PAGE_FILL_REPAIRED_SOURCE_CLOSURE"
        or source.get("checks", {}).get("failed") != 0
        or source.get("checks", {}).get("passed") != 30
        or source.get("source_closure", {}).get("manifest") != FIXED_GATE_EXPECTED["source_manifest"]
    ):
        raise RuntimeError("terminal B008 V3 source gate contract changed")

    build = json.loads(raw["build_receipt"])
    pdf = FIXED_GATE_EXPECTED["candidate_pdf"]
    if (
        build.get("boundary_id") != BOUNDARY_ID
        or build.get("candidate_iteration") != "V3"
        or build.get("nonvisual_status") != "passed"
        or build.get("errors") != []
        or build.get("determinism", {}).get("byte_identical") is not True
        or build.get("determinism", {}).get("pass_3", {}).get("sha256") != pdf["sha256"]
        or build.get("determinism", {}).get("pass_4", {}).get("sha256") != pdf["sha256"]
        or build.get("candidate_artifact", {}).get("bytes") != pdf["bytes"]
        or build.get("candidate_artifact", {}).get("sha256") != pdf["sha256"]
        or build.get("candidate_artifact", {}).get("promoted") is not False
        or build.get("links_and_structure", {}).get("page_count") != 425
        or build.get("source_closure", {}).get("independent_v3_source_gate", {}).get("status") != "passed"
    ):
        raise RuntimeError("terminal B008 V3 deterministic build contract changed")

    independent = json.loads(raw["independent_visual_record"])
    if (
        independent.get("boundary_id") != BOUNDARY_ID
        or independent.get("candidate_iteration") != "V3"
        or independent.get("inspection", {}).get("result") != "PASS"
        or independent.get("inspection", {}).get("page_count") != 9
        or independent.get("visual_checks", {}).get("page_80_fill_and_centering") != "PASS"
        or independent.get("promotion_or_admission_performed") is not False
    ):
        raise RuntimeError("independent B008 V3 visual sanity contract changed")

    root = json.loads(raw["root_visual_audit"])
    if (
        root.get("$schema") != "r011-b008-final-visual-audit/v3"
        or root.get("boundary_id") != BOUNDARY_ID
        or root.get("verdict") != "PASS"
        or root.get("visual_gate_passed") is not True
        or root.get("promotion_authorized_by_visual_gate") is not True
        or any(root.get("severity_counts", {}).get(level) != 0 for level in ("P0", "P1", "P2", "P3"))
        or root.get("candidate", {}).get("path") != pdf["path"]
        or root.get("candidate", {}).get("bytes") != pdf["bytes"]
        or root.get("candidate", {}).get("sha256") != pdf["sha256"]
        or root.get("candidate", {}).get("pages") != 425
        or root.get("candidate", {}).get("build_receipt") != FIXED_GATE_EXPECTED["build_receipt"]
        or root.get("candidate", {}).get("independent_build_visual_record") != FIXED_GATE_EXPECTED["independent_visual_record"]
        or root.get("render_evidence", {}).get("manifest") != FIXED_GATE_EXPECTED["render_manifest"]
        or root.get("render_evidence", {}).get("dpi") != 300
        or root.get("render_evidence", {}).get("all_pages_inspected_individually") is not True
        or root.get("checks", {}).get("page_80_figures_fill_usable_width") != "PASS"
        or root.get("checks", {}).get("page_80_continuation_vertically_balanced_and_centered") != "PASS"
    ):
        raise RuntimeError("root B008 V3 visual audit contract changed")
    pages = root.get("render_evidence", {}).get("pages", [])
    if [item.get("page") for item in pages] != [78, 79, 80, 81, 82, 388, 389, 390, 391]:
        raise RuntimeError("root B008 V3 inspected-page inventory changed")
    for item in pages:
        expected_page = {
            "path": f"qa/b008-build/render-final-v3/page-{item['page']:03d}.png",
            "bytes": item["bytes"],
            "sha256": item["sha256"],
        }
        exact_file(expected_page)
    return raw


def verify_base_b007() -> dict[str, bytes]:
    boundary_raw = exact_file(BASE_EXPECTED["boundary_receipt"])
    boundary = json.loads(boundary_raw)
    if boundary.get("boundary_id") != "R011-B007" or boundary.get("status") != "admitted_exact_pdf_and_backend":
        raise RuntimeError("B007 boundary receipt no longer proves exact admission")
    if identity(BASE_PDF_PATH.read_bytes(), BASE_EXPECTED["canonical_pdf"]["path"]) != {
        key: value for key, value in BASE_EXPECTED["canonical_pdf"].items() if key != "page_count"
    }:
        raise RuntimeError("canonical B007 PDF is not the exact admitted preimage")
    digest, count, total, live = inventory_identity(LIVE_EXPORTS)
    stage_digest, stage_count, stage_total, stage = inventory_identity(BASE_STAGE_EXPORTS)
    expected_tuple = (
        BASE_EXPECTED["inventory_sha256"],
        BASE_EXPECTED["inventory_file_count"],
        BASE_EXPECTED["inventory_bytes"],
    )
    if (digest, count, total) != expected_tuple or (stage_digest, stage_count, stage_total) != expected_tuple or live != stage:
        raise RuntimeError("live backend is not the exact admitted B007 preimage")
    manifest_raw = live.get("manifest.json", b"")
    if identity(manifest_raw, BASE_EXPECTED["manifest"]["path"]) != BASE_EXPECTED["manifest"]:
        raise RuntimeError("live B007 backend manifest identity changed")
    manifest = json.loads(manifest_raw)
    if sum(manifest.get("record_counts", {}).values()) != BASE_EXPECTED["record_count"]:
        raise RuntimeError("live B007 backend record count changed")
    return live


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load required B008 tool: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_final_tools():
    exact_file(ADMISSION_EXPECTED["tooling"]["generator"])
    exact_file(ADMISSION_EXPECTED["tooling"]["finalizer"])
    exact_file(ADMISSION_EXPECTED["tooling"]["validator"])
    generator = load_module("r011_backend_b008_admission_generator", GENERATOR_PATH)
    validator = load_module("r011_backend_b008_admission_validator", VALIDATOR_PATH)
    if not callable(getattr(generator, "build_payloads", None)):
        raise RuntimeError("final B008 generator lacks required admission interface: build_payloads")
    for name in ("validate", "result_bytes"):
        if not callable(getattr(validator, name, None)):
            raise RuntimeError(f"final B008 validator lacks required admission interface: {name}")
    return generator, validator


def verify_final_stage() -> dict[str, Any]:
    expected = ADMISSION_EXPECTED
    generator, validator = load_final_tools()
    generated_first = generator.build_payloads()
    generated_second = generator.build_payloads()
    if generated_first != generated_second:
        raise RuntimeError("B008 final backend is not deterministic in memory")
    stage_digest, stage_count, stage_bytes, staged = final_v3_inventory_identity(STAGE_EXPORTS)
    if staged != generated_first:
        raise RuntimeError("isolated finalized B008 stage differs from deterministic generator output")
    if {
        "file_count": stage_count,
        "bytes": stage_bytes,
        "sha256": stage_digest,
    } != expected["stage_inventory"]:
        raise RuntimeError("isolated finalized B008 stage inventory differs from the frozen admission binding")
    stage_manifest_raw = staged.get("manifest.json", b"")
    if identity(stage_manifest_raw, expected["stage_manifest"]["path"]) != expected["stage_manifest"]:
        raise RuntimeError("isolated finalized B008 stage manifest differs from the frozen admission binding")
    manifest = json.loads(stage_manifest_raw)
    state = manifest.get("stage_state", {})
    if (
        manifest.get("admission_eligibility") != "ready_for_separate_guarded_admission_transaction"
        or manifest.get("final_v3_binding", {}).get("status") != "complete_exact_terminal_v3"
        or state.get("final_v3_bound") is not True
        or state.get("live_backend_mutated") is not False
        or state.get("boundary_admitted") is not False
        or state.get("promotion_performed") is not False
        or sum(manifest.get("record_counts", {}).values()) != expected["record_count"]
        or manifest.get("cumulative_b008_added_over_b007") != expected["new_record_count"]
        or manifest.get("new_final_v3_record_count") != expected["new_final_v3_record_count"]
    ):
        raise RuntimeError("isolated finalized B008 stage state/count contract changed")
    final_inputs = manifest.get("final_v3_binding", {}).get("inputs", {})
    for key in ("source_manifest", "source_qa", "candidate_pdf", "build_receipt", "independent_visual_record", "root_visual_audit"):
        fixed = FIXED_GATE_EXPECTED[key]
        supplied = final_inputs.get(fixed["path"])
        if supplied != {"bytes": fixed["bytes"], "sha256": fixed["sha256"]}:
            raise RuntimeError(f"final B008 backend manifest omits exact terminal gate identity: {key}")

    validation_raw = exact_file(expected["backend_validation_receipt"])
    replay = validator.validate()
    if not isinstance(replay, tuple) or len(replay) < 2:
        raise RuntimeError("final B008 validator returned an unsupported admission result")
    replay_result, replay_payloads = replay[0], replay[1]
    replay_raw = validator.result_bytes(replay_result)
    if replay_raw != validation_raw or replay_payloads != staged:
        raise RuntimeError("B008 backend validator replay differs from the frozen receipt or stage")
    if (
        replay_result.get("status") != "passed_isolated_terminal_v3_backend_ready_for_guarded_admission"
        or replay_result.get("admission_eligibility") != "ready_for_separate_guarded_admission_transaction"
        or replay_result.get("record_count") != expected["record_count"]
        or replay_result.get("new_final_v3_record_count") != expected["new_final_v3_record_count"]
        or replay_result.get("validator_checks_passed") != expected["validator_check_count"]
        or replay_result.get("validator_checks_total") != expected["validator_check_count"]
        or replay_result.get("resolved_reference_count") != expected["resolved_reference_count"]
        or replay_result.get("admitted_b007_records_preserved_exact") is not True
        or replay_result.get("prefinal_records_preserved_exact") is not True
        or replay_result.get("live_backend_mutated") is not False
        or replay_result.get("boundary_admitted") is not False
    ):
        raise RuntimeError("B008 final backend validation receipt does not satisfy admission invariants")
    return {
        "staged": staged,
        "manifest": manifest,
        "validation": replay_result,
    }


def construct_receipt(pdf_admission_action: str) -> bytes:
    if pdf_admission_action not in {"created_from_terminal_candidate", "verified_preexisting_exact"}:
        raise RuntimeError("unsupported canonical-PDF admission action")
    expected = ADMISSION_EXPECTED
    receipt = {
        "$schema": "r011-b008-boundary-receipt/v1",
        "boundary_id": BOUNDARY_ID,
        "base_boundary": BASE_EXPECTED["boundary_id"],
        "status": "admitted_exact_pdf_and_backend",
        "recorded_at": RECORDED_AT,
        "authority": "exact terminal V3 source/build/visual gates, finalized isolated backend validation, and guarded atomic admission",
        "base_prestate": BASE_EXPECTED,
        "terminal_v3_gates": FIXED_GATE_EXPECTED,
        "final_backend_toolchain": expected["tooling"],
        "backend_validation_receipt": expected["backend_validation_receipt"],
        "admitted_backend": {
            "manifest": expected["stage_manifest"],
            "record_count": expected["record_count"],
            "new_record_count": expected["new_record_count"],
            "new_final_v3_record_count": expected["new_final_v3_record_count"],
            "inventory": expected["stage_inventory"],
            "validator_check_count": expected["validator_check_count"],
            "resolved_reference_count": expected["resolved_reference_count"],
            "all_2264_b007_stable_records_retained": True,
        },
        "promoted_pdf": {
            "path": expected["pdf"]["promoted_path"],
            "bytes": expected["pdf"]["bytes"],
            "sha256": expected["pdf"]["sha256"],
            "page_count": expected["pdf"]["page_count"],
            "source_candidate_path": expected["pdf"]["source_path"],
            "admission_action": pdf_admission_action,
            "created_by_transaction": pdf_admission_action == "created_from_terminal_candidate",
            "readback_exact": True,
        },
        "b007_preservation": {
            "canonical_pdf_retained_exact": True,
            "canonical_pdf": BASE_EXPECTED["canonical_pdf"],
            "backend_preimage_held_for_exact_rollback_until_commit": True,
            "boundary_receipt_retained_exact": True,
        },
        "transaction": {
            "preflight_fail_closed": True,
            "exclusive_narrow_lock": TRANSACTION_LOCK_PATH.relative_to(LANE).as_posix(),
            "crash_detecting_journal": TRANSACTION_JOURNAL_PATH.relative_to(LANE).as_posix(),
            "same_directory_atomic_file_replaces": True,
            "backend_manifest_written_last": True,
            "backend_manifest_restored_last_on_rollback": True,
            "exact_rollback_on_failure": True,
            "boundary_receipt_created_without_overwrite": True,
            "post_admission_exact_replay": True,
            "deleted_paths": [],
        },
        "privacy": {
            "absolute_local_profile_paths_in_receipt": False,
            "paths_are_lane_relative": True,
        },
        "live_backend_mutated": True,
        "canonical_pdf_promoted": True,
        "canonical_source_mutated": False,
        "tooling": {
            **expected["tooling"],
            "admitter": identity(Path(__file__).read_bytes(), Path(__file__).relative_to(LANE).as_posix()),
        },
    }
    raw = canonical_json(receipt)
    lowered = raw.lower()
    if b"c:\\users\\" in lowered or b"/users/" in lowered:
        raise RuntimeError("deterministic B008 boundary receipt contains an absolute local profile path")
    return raw


def preflight() -> dict[str, Any]:
    gaps = admission_binding_gaps()
    if gaps:
        raise RuntimeError("B008 admission bindings are not frozen: " + ", ".join(gaps))
    if TRANSACTION_LOCK_PATH.exists() or TRANSACTION_JOURNAL_PATH.exists():
        raise RuntimeError("a B008 admission lock or journal already exists; manual transaction-state review is required")
    if BOUNDARY_RECEIPT_PATH.exists():
        raise RuntimeError("B008 boundary receipt already exists; use --verify-admitted instead of re-admitting")

    assert_fixed_gate_chain()
    final = verify_final_stage()
    live_before = verify_base_b007()
    staged: dict[str, bytes] = final["staged"]
    if not set(live_before) <= set(staged):
        raise RuntimeError("isolated B008 backend does not retain every B007 live payload path")
    candidate_raw = exact_file(FIXED_GATE_EXPECTED["candidate_pdf"])
    output_before = PROMOTED_PDF_PATH.read_bytes() if PROMOTED_PDF_PATH.is_file() else None
    if output_before is not None and output_before != candidate_raw:
        raise RuntimeError("refusing to overwrite a nonmatching canonical B008 PDF")
    pdf_action = "created_from_terminal_candidate" if output_before is None else "verified_preexisting_exact"
    receipt_raw = construct_receipt(pdf_action)
    return {
        **final,
        "live_before": live_before,
        "candidate_raw": candidate_raw,
        "output_before": output_before,
        "pdf_admission_action": pdf_action,
        "receipt_raw": receipt_raw,
    }


def atomic_replace(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        if temporary.read_bytes() != raw:
            raise RuntimeError(f"temporary readback mismatch: {path}")
        os.replace(temporary, path)
        if path.read_bytes() != raw:
            raise RuntimeError(f"post-replace readback mismatch: {path}")
    finally:
        if temporary.exists():
            temporary.unlink()


def atomic_create(path: Path, raw: bytes) -> None:
    """Create a complete file without ever overwriting an existing target."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        if temporary.read_bytes() != raw:
            raise RuntimeError(f"temporary readback mismatch: {path}")
        try:
            os.link(temporary, path)
        except FileExistsError as exc:
            raise RuntimeError(f"refusing to overwrite existing evidence: {path}") from exc
        if path.read_bytes() != raw:
            raise RuntimeError(f"post-create readback mismatch: {path}")
    finally:
        if temporary.exists():
            temporary.unlink()


_PROMOTION_SECRET = object()


class _PromotionAuthorization:
    __slots__ = ("_secret",)

    def __init__(self, secret: object) -> None:
        if secret is not _PROMOTION_SECRET:
            raise PermissionError("promotion authorization can only be minted by the CLI entry point")
        self._secret = secret


def _authorize_cli_promotion(promote_requested: bool) -> _PromotionAuthorization:
    if __name__ != "__main__" or not promote_requested:
        raise PermissionError("internal promotion authorization requires an explicit CLI --promote invocation")
    return _PromotionAuthorization(_PROMOTION_SECRET)


def directory_inventory(root: Path) -> set[str]:
    if not root.is_dir():
        return set()
    return {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_dir()}


def missing_parent_directories(path: Path, stop: Path) -> list[Path]:
    path = path.resolve()
    stop = stop.resolve()
    result: list[Path] = []
    current = path.parent
    while current != stop:
        try:
            current.relative_to(stop)
        except ValueError as exc:
            raise RuntimeError("transaction output path escapes the R011 lane") from exc
        if not current.exists():
            result.append(current)
        current = current.parent
    return result


def remove_new_empty_directories(root: Path, before: set[str]) -> list[str]:
    errors: list[str] = []
    after = directory_inventory(root)
    for relative in sorted(after - before, key=lambda item: (item.count("/"), item), reverse=True):
        directory = root / relative
        try:
            directory.rmdir()
        except Exception as exc:
            errors.append(f"directory {relative}: {exc}")
    if directory_inventory(root) != before:
        errors.append("backend directory inventory did not return to its exact pre-state")
    return errors


def rollback_write_order(written: list[str]) -> list[str]:
    nonmanifest = [relative for relative in reversed(written) if relative != "manifest.json"]
    return nonmanifest + (["manifest.json"] if "manifest.json" in written else [])


def acquire_transaction_lock() -> None:
    if TRANSACTION_JOURNAL_PATH.exists():
        raise RuntimeError("a prior B008 admission journal exists; manual recovery is required")
    lock_raw = canonical_json({
        "boundary_id": BOUNDARY_ID,
        "recorded_at": RECORDED_AT,
        "status": "authorized_cli_admission_in_progress",
    })
    try:
        descriptor = os.open(TRANSACTION_LOCK_PATH, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise RuntimeError("another B008 admission transaction holds the narrow lock") from exc
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(lock_raw)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        TRANSACTION_LOCK_PATH.unlink(missing_ok=True)
        raise
    if TRANSACTION_LOCK_PATH.read_bytes() != lock_raw:
        TRANSACTION_LOCK_PATH.unlink(missing_ok=True)
        raise RuntimeError("B008 admission lock readback failed")


def construct_transaction_journal(context: dict[str, Any]) -> bytes:
    output_before: bytes | None = context["output_before"]
    pdf_prestate: dict[str, Any] = {
        "path": PROMOTED_PDF_PATH.relative_to(LANE).as_posix(),
        "state": "absent",
    }
    if output_before is not None:
        pdf_prestate = {
            "path": PROMOTED_PDF_PATH.relative_to(LANE).as_posix(),
            "state": "present_exact",
            **identity(output_before),
        }
    return canonical_json({
        "$schema": "r011-b008-admission-transaction-journal/v1",
        "boundary_id": BOUNDARY_ID,
        "base_prestate_inventory": {
            "bytes": BASE_EXPECTED["inventory_bytes"],
            "file_count": BASE_EXPECTED["inventory_file_count"],
            "sha256": BASE_EXPECTED["inventory_sha256"],
        },
        "base_canonical_pdf": BASE_EXPECTED["canonical_pdf"],
        "boundary_receipt": BOUNDARY_RECEIPT_PATH.relative_to(LANE).as_posix(),
        "candidate_pdf": ADMISSION_EXPECTED["pdf"],
        "canonical_pdf_prestate": pdf_prestate,
        "pdf_admission_action": context["pdf_admission_action"],
        "planned_backend_order": "all non-manifest payloads, then manifest.json",
        "planned_rollback_order": "all written non-manifest payloads in reverse, then manifest.json",
        "receipt_sha256": sha256(context["receipt_raw"]),
        "stage_inventory": ADMISSION_EXPECTED["stage_inventory"],
        "status": "in_progress_fail_closed",
    })


def promote(context: dict[str, Any], authorization: _PromotionAuthorization | None = None) -> None:
    if not isinstance(authorization, _PromotionAuthorization) or authorization._secret is not _PROMOTION_SECRET:
        raise PermissionError("promotion refused: missing explicit internal CLI authorization")
    staged: dict[str, bytes] = context["staged"]
    live_before: dict[str, bytes] = context["live_before"]
    candidate_raw: bytes = context["candidate_raw"]
    output_before: bytes | None = context["output_before"]
    receipt_raw: bytes = context["receipt_raw"]
    expected_pdf_action = "created_from_terminal_candidate" if output_before is None else "verified_preexisting_exact"
    if context.get("pdf_admission_action") != expected_pdf_action:
        raise RuntimeError("preflight canonical-PDF action changed before admission")

    acquire_transaction_lock()
    live_directories_before = directory_inventory(LIVE_EXPORTS)
    output_missing_directories = missing_parent_directories(PROMOTED_PDF_PATH, LANE)
    written: list[str] = []
    pdf_written = False
    receipt_written = False
    journal_written = False
    try:
        _live_digest, _live_count, _live_bytes, live_now = inventory_identity(LIVE_EXPORTS)
        output_now = PROMOTED_PDF_PATH.read_bytes() if PROMOTED_PDF_PATH.is_file() else None
        if live_now != live_before:
            raise RuntimeError("live backend changed after preflight and before the first admission write")
        assert_fixed_gate_chain()
        final_now = verify_final_stage()
        if final_now["staged"] != staged:
            raise RuntimeError("isolated B008 stage changed after preflight and before admission")
        if exact_file(FIXED_GATE_EXPECTED["candidate_pdf"]) != candidate_raw:
            raise RuntimeError("terminal candidate PDF changed after preflight and before admission")
        if output_now != output_before:
            raise RuntimeError("canonical B008 PDF state changed after preflight and before admission")
        verify_base_b007()
        if construct_receipt(expected_pdf_action) != receipt_raw:
            raise RuntimeError("deterministic B008 boundary receipt changed after preflight")
        if BOUNDARY_RECEIPT_PATH.exists():
            raise RuntimeError("B008 boundary receipt appeared after preflight; refusing admission race")

        journal_raw = construct_transaction_journal(context)
        atomic_create(TRANSACTION_JOURNAL_PATH, journal_raw)
        journal_written = True

        order = sorted(path for path in staged if path != "manifest.json") + ["manifest.json"]
        for relative in order:
            written.append(relative)
            atomic_replace(LIVE_EXPORTS / relative, staged[relative])
        if expected_pdf_action == "created_from_terminal_candidate":
            atomic_create(PROMOTED_PDF_PATH, candidate_raw)
            pdf_written = True

        digest, count, total, live_after = final_v3_inventory_identity(LIVE_EXPORTS)
        if live_after != staged or {
            "file_count": count,
            "bytes": total,
            "sha256": digest,
        } != ADMISSION_EXPECTED["stage_inventory"]:
            raise RuntimeError("post-promotion live backend readback differs from the exact stage")
        if PROMOTED_PDF_PATH.read_bytes() != candidate_raw:
            raise RuntimeError("post-promotion canonical B008 PDF readback differs from the terminal candidate")
        if identity(BASE_PDF_PATH.read_bytes(), BASE_EXPECTED["canonical_pdf"]["path"]) != {
            key: value for key, value in BASE_EXPECTED["canonical_pdf"].items() if key != "page_count"
        }:
            raise RuntimeError("canonical B007 PDF changed during B008 admission")
        exact_file(BASE_EXPECTED["boundary_receipt"])
        atomic_create(BOUNDARY_RECEIPT_PATH, receipt_raw)
        receipt_written = True
        if BOUNDARY_RECEIPT_PATH.read_bytes() != receipt_raw:
            raise RuntimeError("post-promotion B008 boundary receipt readback differs")

        # Exact replay while the crash journal still protects the transaction.
        replay_raw = verify_admitted(allow_transaction_markers=True)
        if replay_raw != receipt_raw:
            raise RuntimeError("post-admission exact replay differs before commit")
        TRANSACTION_JOURNAL_PATH.unlink()
        journal_written = False
        TRANSACTION_LOCK_PATH.unlink()
    except Exception as promotion_error:
        rollback_errors: list[str] = []
        if receipt_written and BOUNDARY_RECEIPT_PATH.exists():
            try:
                BOUNDARY_RECEIPT_PATH.unlink()
            except Exception as exc:
                rollback_errors.append(f"boundary receipt: {exc}")
        for relative in rollback_write_order(written):
            destination = LIVE_EXPORTS / relative
            before = live_before.get(relative)
            try:
                if before is None:
                    destination.unlink(missing_ok=True)
                else:
                    atomic_replace(destination, before)
            except Exception as exc:
                rollback_errors.append(f"backend/{relative}: {exc}")
        if pdf_written:
            try:
                PROMOTED_PDF_PATH.unlink(missing_ok=True)
            except Exception as exc:
                rollback_errors.append(f"PDF: {exc}")
        rollback_errors.extend(remove_new_empty_directories(LIVE_EXPORTS, live_directories_before))
        for directory in sorted(output_missing_directories, key=lambda path: len(path.parts), reverse=True):
            if directory.exists():
                try:
                    directory.rmdir()
                except Exception as exc:
                    rollback_errors.append(f"output directory {directory.relative_to(LANE).as_posix()}: {exc}")
        rollback_digest, rollback_count, rollback_bytes, rollback_live = inventory_identity(LIVE_EXPORTS)
        if rollback_live != live_before or (
            rollback_digest != BASE_EXPECTED["inventory_sha256"]
            or rollback_count != BASE_EXPECTED["inventory_file_count"]
            or rollback_bytes != BASE_EXPECTED["inventory_bytes"]
        ):
            rollback_errors.append("live backend did not return to the exact B007 preimage")
        if (PROMOTED_PDF_PATH.read_bytes() if PROMOTED_PDF_PATH.is_file() else None) != output_before:
            rollback_errors.append("canonical B008 PDF did not return to its exact pre-state")
        try:
            verify_base_b007()
        except Exception as exc:
            rollback_errors.append(f"B007 preservation: {exc}")
        if BOUNDARY_RECEIPT_PATH.exists():
            rollback_errors.append("B008 boundary receipt remains after rollback")
        if not rollback_errors:
            for marker, label in (
                (TRANSACTION_JOURNAL_PATH, "transaction journal"),
                (TRANSACTION_LOCK_PATH, "transaction lock"),
            ):
                if marker.exists():
                    try:
                        marker.unlink()
                    except Exception as exc:
                        rollback_errors.append(f"{label}: {exc}")
        if rollback_errors:
            raise RuntimeError(f"admission failed ({promotion_error}); rollback also failed: {rollback_errors}") from promotion_error
        raise RuntimeError(f"admission failed and exact rollback passed: {promotion_error}") from promotion_error


def verify_admitted(allow_transaction_markers: bool = False) -> bytes:
    gaps = admission_binding_gaps()
    if gaps:
        raise RuntimeError("B008 admission bindings are not frozen: " + ", ".join(gaps))
    if not allow_transaction_markers and (TRANSACTION_LOCK_PATH.exists() or TRANSACTION_JOURNAL_PATH.exists()):
        raise RuntimeError("B008 admission lock or journal remains after claimed admission")
    assert_fixed_gate_chain()
    final = verify_final_stage()
    staged: dict[str, bytes] = final["staged"]
    digest, count, total, live = final_v3_inventory_identity(LIVE_EXPORTS)
    if live != staged or {
        "file_count": count,
        "bytes": total,
        "sha256": digest,
    } != ADMISSION_EXPECTED["stage_inventory"]:
        raise RuntimeError("live B008 backend is not byte-identical to the finalized isolated stage")
    pdf = ADMISSION_EXPECTED["pdf"]
    if not PROMOTED_PDF_PATH.is_file() or identity(PROMOTED_PDF_PATH.read_bytes()) != {
        "bytes": pdf["bytes"],
        "sha256": pdf["sha256"],
    }:
        raise RuntimeError("promoted B008 PDF differs from the frozen admission binding")
    if identity(BASE_PDF_PATH.read_bytes(), BASE_EXPECTED["canonical_pdf"]["path"]) != {
        key: value for key, value in BASE_EXPECTED["canonical_pdf"].items() if key != "page_count"
    }:
        raise RuntimeError("canonical B007 PDF is not preserved after B008 admission")
    exact_file(BASE_EXPECTED["boundary_receipt"])
    if not BOUNDARY_RECEIPT_PATH.is_file():
        raise RuntimeError("B008 boundary receipt is absent")
    actual_receipt = BOUNDARY_RECEIPT_PATH.read_bytes()
    parsed = json.loads(actual_receipt)
    action = parsed.get("promoted_pdf", {}).get("admission_action")
    expected_receipt = construct_receipt(action)
    if actual_receipt != expected_receipt:
        raise RuntimeError("B008 boundary receipt differs from its deterministic replay")
    return expected_receipt


def readiness_gaps() -> list[str]:
    gaps = [f"admission.{item}" for item in admission_binding_gaps()]
    if TRANSACTION_LOCK_PATH.exists():
        gaps.append("transaction.lock_present")
    if TRANSACTION_JOURNAL_PATH.exists():
        gaps.append("transaction.journal_present")
    if BOUNDARY_RECEIPT_PATH.exists():
        gaps.append("admission.boundary_receipt_already_present")
    try:
        assert_fixed_gate_chain()
    except Exception:
        gaps.append("terminal_v3.source_build_visual_chain_failed")
    try:
        verify_base_b007()
    except Exception:
        gaps.append("base.not_exact_admitted_b007_prestate")
    if not gaps:
        try:
            preflight()
        except Exception:
            gaps.append("preflight.exact_stage_pdf_and_receipt_replay_failed")
    return sorted(set(gaps))


def self_test() -> list[str]:
    failures: list[str] = []
    for unsafe in ("../escape", str(LANE.resolve()), "qa\\escape"):
        try:
            lane_path(unsafe)
            failures.append(f"unsafe path accepted: {unsafe}")
        except ValueError:
            pass
    if _unset({"outer": {"required": None}}) != ["outer.required"]:
        failures.append("deliberately unset test binding was not detected")
    if canonical_json({"b": 1, "a": "é"}) != canonical_json({"a": "é", "b": 1}):
        failures.append("canonical JSON is not stable across insertion order")
    if rollback_write_order(["a.jsonl", "b.jsonl", "manifest.json"])[-1] != "manifest.json":
        failures.append("rollback does not restore the backend manifest last")
    try:
        promote({}, authorization=None)
        failures.append("promotion accepted a missing internal authorization")
    except PermissionError:
        pass
    try:
        assert_fixed_gate_chain()
    except Exception as exc:
        failures.append(f"terminal V3 fixed gate chain failed: {exc}")
    try:
        verify_base_b007()
    except Exception as exc:
        failures.append(f"exact B007 prestate failed: {exc}")
    gaps = admission_binding_gaps()
    if gaps:
        if any(not gap.startswith(("stage_manifest", "backend_validation_receipt", "stage_inventory", "record_count", "new_record_count", "new_final_v3_record_count", "validator_check_count", "resolved_reference_count", "tooling")) for gap in gaps):
            failures.append("an unexpected non-backend admission binding is unset")
        try:
            preflight()
            failures.append("preflight accepted deliberately unfrozen backend bindings")
        except RuntimeError as exc:
            if "admission bindings are not frozen" not in str(exc):
                failures.append("unfrozen backend bindings did not fail at the first guard")
    if (
        TRANSACTION_LOCK_PATH.parent != STAGE_EXPORTS.parent
        or TRANSACTION_JOURNAL_PATH.parent != STAGE_EXPORTS.parent
        or TRANSACTION_LOCK_PATH.exists()
        or TRANSACTION_JOURNAL_PATH.exists()
    ):
        failures.append("narrow transaction marker paths are invalid or unexpectedly occupied")
    if BOUNDARY_RECEIPT_PATH.exists():
        failures.append("B008 boundary receipt unexpectedly exists before admission")
    return failures


def result(status: str, errors: list[str], **extra: Any) -> str:
    value: dict[str, Any] = {
        "boundary_id": BOUNDARY_ID,
        "status": status,
        "errors": errors,
        "boundary_receipt": BOUNDARY_RECEIPT_PATH.relative_to(LANE).as_posix(),
        "promoted_pdf": PROMOTED_PDF_PATH.relative_to(LANE).as_posix(),
        "mutation_performed": False,
    }
    value.update(extra)
    return canonical_json(value).decode("utf-8").rstrip("\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--promote", action="store_true", help="perform the exact guarded PDF/backend admission transaction")
    modes.add_argument("--verify-admitted", action="store_true", help="read-only exact post-admission verification")
    modes.add_argument("--check-readiness", action="store_true", help="list every still-unfrozen exact admission binding")
    modes.add_argument("--self-test", action="store_true", help="run pure fail-closed helper checks")
    args = parser.parse_args()

    if args.self_test:
        failures = self_test()
        print(result(
            "passed" if not failures else "failed",
            failures,
            self_test_count=10,
            admission_binding_state="intentionally_unfrozen" if admission_binding_gaps() else "frozen",
        ))
        return 0 if not failures else 1
    if args.check_readiness:
        gaps = readiness_gaps()
        print(result(
            "ready" if not gaps else "blocked_unfrozen_exact_bindings",
            [],
            deferred_bindings=gaps,
            exact_binding_manifest=ADMISSION_EXPECTED["stage_manifest"]["path"],
        ))
        return 0 if not gaps else 2
    if args.verify_admitted:
        try:
            receipt_raw = verify_admitted()
        except Exception as exc:
            print(result("refused", [str(exc)]))
            return 2
        print(result(
            "passed_exact_admission_readback",
            [],
            receipt=identity(receipt_raw, BOUNDARY_RECEIPT_PATH.relative_to(LANE).as_posix()),
        ))
        return 0

    try:
        context = preflight()
    except Exception as exc:
        print(result("refused", [str(exc)]))
        return 2
    receipt_identity = identity(context["receipt_raw"], BOUNDARY_RECEIPT_PATH.relative_to(LANE).as_posix())
    if not args.promote:
        print(result("passed_read_only_preflight", [], candidate_receipt=receipt_identity))
        return 0
    try:
        authorization = _authorize_cli_promotion(args.promote)
        promote(context, authorization=authorization)
        replay_raw = verify_admitted()
    except Exception as exc:
        print(result("failed", [str(exc)]))
        return 1
    if replay_raw != context["receipt_raw"]:
        print(result("failed", ["post-commit exact receipt replay changed"]))
        return 1
    print(result(
        "admitted_exact_pdf_and_backend",
        [],
        mutation_performed=True,
        receipt=receipt_identity,
        post_admission_exact_replay=True,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
