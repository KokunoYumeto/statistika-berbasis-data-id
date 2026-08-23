#!/usr/bin/env python3
"""Fail-closed exact admission transaction for R011-B007.

The default mode is read-only.  ``--promote`` is the only mutating mode and is
unavailable until every exact binding below has been frozen after terminal
build, visual, backend-generation, and backend-validation receipts exist.  The
transaction promotes the reviewed candidate PDF and isolated backend, verifies
their public-lane byte readback, and only then writes the deterministic boundary
receipt.  Any failure attempts an exact rollback to the admitted R011-B006
pre-state.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import tempfile
from pathlib import Path
from typing import Any


LANE = Path(__file__).resolve().parents[1]
GENERATOR_PATH = LANE / "scripts" / "generate_backend_b007.py"
VALIDATOR_PATH = LANE / "scripts" / "validate_backend_b007.py"
LIVE_EXPORTS = LANE / "backend" / "exports"
STAGE_EXPORTS = LANE / "qa" / "b007-backend" / "exports"
FINAL_INPUTS_PATH = LANE / "qa" / "b007-backend" / "R011-B007_FINAL_GATE_INPUTS.json"
VALIDATION_RECEIPT_PATH = LANE / "qa" / "b007-backend" / "BACKEND_VALIDATION_RECEIPT_R011-B007.json"
TRANSACTION_LOCK_PATH = LANE / "qa" / "b007-backend" / ".R011-B007-admission.lock"
TRANSACTION_JOURNAL_PATH = LANE / "qa" / "b007-backend" / "R011-B007_ADMISSION_TRANSACTION_JOURNAL.json"
BOUNDARY_RECEIPT_PATH = LANE / "qa" / "R011-B007_BOUNDARY_RECEIPT.json"
PROMOTED_PDF_PATH = LANE / "output" / "pdf" / "statistika-berbasis-data-batas-R011-B007.pdf"
BOUNDARY_ID = "R011-B007"
RECORDED_AT = "2026-08-22T23:30:00+02:00"

BASE_EXPECTED = {
    "boundary_id": "R011-B006",
    "manifest": {
        "path": "backend/exports/manifest.json",
        "bytes": 23151,
        "sha256": "d2324e74bff4aa8c985c82a89317828150910f6369b821898a9b1bca33083d0b",
    },
    "record_count": 1969,
    "inventory_file_count": 75,
    "inventory_bytes": 5932043,
    "inventory_sha256": "a4b929d4786677469580beb80207037d082819ca3feaac44bbd8d25c5e30f2e2",
}

# Exact bindings independently frozen from the terminal v8 build and resulting
# isolated backend validation receipt. They are never discovery hints.
ADMISSION_EXPECTED: dict[str, Any] = {
    "final_inputs_manifest": {
        "path": "qa/b007-backend/R011-B007_FINAL_GATE_INPUTS.json",
        "bytes": 2357,
        "sha256": "88079f52ecb077ea38791c379e904ddc6cd5f5dcce26f90a3703ea2e8957fe00",
    },
    "stage_manifest": {
        "path": "qa/b007-backend/exports/manifest.json",
        "bytes": 33555,
        "sha256": "3f1d2c0ae5a6011f01e6fa0c6080ccadcfa1a651f131002058afd6e610e55d12",
    },
    "backend_validation_receipt": {
        "path": "qa/b007-backend/BACKEND_VALIDATION_RECEIPT_R011-B007.json",
        "bytes": 8547,
        "sha256": "c851eb0fab875ef07e9f9e0125581674b595eee92e8b01780a93e1946247973f",
    },
    "stage_inventory": {
        "file_count": 102,
        "bytes": 7018282,
        "sha256": "ffd32f5a6211b3c0a1513ee596dff769f3598fe6ff596f3d0af8f93a384e9133",
    },
    "record_count": 2264,
    "new_record_count": 295,
    "validator_check_count": 23,
    "resolved_reference_count": 9883,
    "pdf": {
        "source_path": "qa/b007-build/final-v8/main.pdf",
        "promoted_path": "output/pdf/statistika-berbasis-data-batas-R011-B007.pdf",
        "bytes": 22017185,
        "sha256": "ca872ddbc2fb1cab5f6cdb2fe745a0711a315fef68ab2e72c7a11d1c633a5c1a",
        "page_count": 425,
    },
}


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load required B007 tool: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


m = load_module("r011_backend_b007_admission_generator", GENERATOR_PATH)
v = load_module("r011_backend_b007_admission_validator", VALIDATOR_PATH)
g = m.g


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_json(value: Any) -> bytes:
    return (g.canonical_json(value) + "\n").encode("utf-8")


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
    if path is not None:
        value = {"path": path, **value}
    return value


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
        for path in sorted((item for item in root.rglob("*") if item.is_file()), key=lambda item: item.relative_to(root).as_posix()):
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
    for group in ("final_inputs_manifest", "stage_manifest", "backend_validation_receipt"):
        item = ADMISSION_EXPECTED[group]
        if item.get("bytes") is not None and (not isinstance(item["bytes"], int) or item["bytes"] <= 0):
            gaps.append(f"{group}.bytes")
        if item.get("sha256") is not None and not isinstance(item["sha256"], str):
            gaps.append(f"{group}.sha256")
        elif item.get("sha256") is not None and len(item["sha256"]) != 64:
            gaps.append(f"{group}.sha256")
    pdf = ADMISSION_EXPECTED["pdf"]
    if pdf.get("bytes") is not None and (not isinstance(pdf["bytes"], int) or pdf["bytes"] <= 0):
        gaps.append("pdf.bytes")
    if pdf.get("page_count") is not None and (not isinstance(pdf["page_count"], int) or pdf["page_count"] <= 0):
        gaps.append("pdf.page_count")
    return sorted(set(gaps))


def verify_base_live() -> dict[str, bytes]:
    digest, count, total, payloads = inventory_identity(LIVE_EXPORTS)
    manifest_raw = payloads.get("manifest.json", b"")
    if (
        digest != BASE_EXPECTED["inventory_sha256"]
        or count != BASE_EXPECTED["inventory_file_count"]
        or total != BASE_EXPECTED["inventory_bytes"]
        or identity(manifest_raw, BASE_EXPECTED["manifest"]["path"]) != BASE_EXPECTED["manifest"]
    ):
        raise RuntimeError("live backend is not the exact admitted 1,969-record R011-B006 pre-state")
    manifest = json.loads(manifest_raw)
    if sum(manifest["record_counts"].values()) != BASE_EXPECTED["record_count"]:
        raise RuntimeError("live B006 manifest record count changed")
    return payloads


def construct_receipt(pdf_admission_action: str) -> bytes:
    if pdf_admission_action not in {"created_from_terminal_candidate", "verified_preexisting_exact"}:
        raise RuntimeError("unsupported canonical-PDF admission action")
    pdf_created = pdf_admission_action == "created_from_terminal_candidate"
    expected = ADMISSION_EXPECTED
    tool_identities = {
        "generator": identity(GENERATOR_PATH.read_bytes(), GENERATOR_PATH.relative_to(LANE).as_posix()),
        "validator": identity(VALIDATOR_PATH.read_bytes(), VALIDATOR_PATH.relative_to(LANE).as_posix()),
        "admitter": identity(Path(__file__).read_bytes(), Path(__file__).relative_to(LANE).as_posix()),
    }
    receipt = {
        "$schema": "r011-b007-boundary-receipt/v1",
        "boundary_id": BOUNDARY_ID,
        "base_boundary": BASE_EXPECTED["boundary_id"],
        "status": "admitted_exact_pdf_and_backend",
        "recorded_at": RECORDED_AT,
        "authority": "exact terminal build, zero-severity visual audit, isolated backend validation, and guarded atomic admission",
        "base_prestate": BASE_EXPECTED,
        "final_gate_inputs": expected["final_inputs_manifest"],
        "backend_validation_receipt": expected["backend_validation_receipt"],
        "admitted_backend": {
            "manifest": expected["stage_manifest"],
            "record_count": expected["record_count"],
            "new_record_count": expected["new_record_count"],
            "inventory": expected["stage_inventory"],
            "validator_check_count": expected["validator_check_count"],
            "resolved_reference_count": expected["resolved_reference_count"],
            "all_1969_b006_stable_records_retained": True,
        },
        "promoted_pdf": {
            "path": expected["pdf"]["promoted_path"],
            "bytes": expected["pdf"]["bytes"],
            "sha256": expected["pdf"]["sha256"],
            "page_count": expected["pdf"]["page_count"],
            "source_candidate_path": expected["pdf"]["source_path"],
            "admission_action": pdf_admission_action,
            "created_by_transaction": pdf_created,
            "readback_exact": True,
        },
        "transaction": {
            "preflight_fail_closed": True,
            "exclusive_narrow_lock": TRANSACTION_LOCK_PATH.relative_to(LANE).as_posix(),
            "crash_detecting_journal": TRANSACTION_JOURNAL_PATH.relative_to(LANE).as_posix(),
            "journal_removed_only_after_receipt_readback": True,
            "same_directory_atomic_file_replaces": True,
            "backend_manifest_written_last": True,
            "backend_manifest_restored_last_on_rollback": True,
            "exact_rollback_on_failure": True,
            "newly_created_directories_removed_on_rollback": True,
            "boundary_receipt_written_only_after_backend_and_pdf_readback": True,
            "deleted_paths": [],
        },
        "privacy": {
            "prohibited_requester_token_hits": 0,
            "absolute_local_user_profile_path_hits": 0,
            "absolute_local_profile_paths_in_receipt": False,
            "paths_are_lane_relative": True,
        },
        "live_backend_mutated": True,
        "canonical_pdf_promoted": True,
        "canonical_pdf_created_by_transaction": pdf_created,
        "canonical_source_mutated": False,
        "tooling": tool_identities,
    }
    return canonical_json(receipt)


def preflight() -> dict[str, Any]:
    gaps = admission_binding_gaps()
    if gaps:
        raise RuntimeError("B007 admission bindings are not frozen: " + ", ".join(gaps))
    if m.final_binding_gaps():
        raise RuntimeError("B007 generator final bindings are not frozen: " + ", ".join(m.final_binding_gaps()))
    if TRANSACTION_LOCK_PATH.exists() or TRANSACTION_JOURNAL_PATH.exists():
        raise RuntimeError("a B007 admission lock or journal already exists; manual transaction-state review is required")

    final_inputs_raw = exact_file(ADMISSION_EXPECTED["final_inputs_manifest"])
    supplied, supplied_raw, _final_raws = m.load_final_inputs(FINAL_INPUTS_PATH)
    if supplied_raw != final_inputs_raw:
        raise RuntimeError("generator and admission final-input manifest reads differ")
    expected_pdf = ADMISSION_EXPECTED["pdf"]
    if m.EXPECTED_FINAL_INPUTS["pdf"] != {
        "path": expected_pdf["source_path"],
        "bytes": expected_pdf["bytes"],
        "sha256": expected_pdf["sha256"],
        "page_count": expected_pdf["page_count"],
    }:
        raise RuntimeError("admission PDF binding differs from the generator final-PDF binding")

    generated_first = m.build_payloads(FINAL_INPUTS_PATH)
    generated_second = m.build_payloads(FINAL_INPUTS_PATH)
    if generated_first != generated_second:
        raise RuntimeError("B007 final backend is not deterministic in memory")
    stage_digest, stage_count, stage_bytes, staged = inventory_identity(STAGE_EXPORTS)
    if staged != generated_first:
        raise RuntimeError("isolated B007 stage differs from deterministic generator output")
    expected_inventory = ADMISSION_EXPECTED["stage_inventory"]
    if {
        "file_count": stage_count,
        "bytes": stage_bytes,
        "sha256": stage_digest,
    } != expected_inventory:
        raise RuntimeError("isolated B007 stage inventory differs from the frozen admission binding")
    stage_manifest_raw = staged.get("manifest.json", b"")
    if identity(stage_manifest_raw, ADMISSION_EXPECTED["stage_manifest"]["path"]) != ADMISSION_EXPECTED["stage_manifest"]:
        raise RuntimeError("isolated B007 stage manifest differs from the frozen admission binding")
    stage_manifest = json.loads(stage_manifest_raw)
    if (
        stage_manifest.get("publication_eligibility") != "boundary_ready_for_separate_admission"
        or stage_manifest.get("stage_state", {}).get("build_and_visual_gates_passed") is not True
        or stage_manifest.get("stage_state", {}).get("boundary_admitted") is not False
        or stage_manifest.get("stage_state", {}).get("promotion_performed") is not False
        or sum(stage_manifest.get("record_counts", {}).values()) != ADMISSION_EXPECTED["record_count"]
        or sum(stage_manifest.get("new_record_counts", {}).values()) != ADMISSION_EXPECTED["new_record_count"]
    ):
        raise RuntimeError("isolated B007 stage state/count contract changed")

    validation_raw = exact_file(ADMISSION_EXPECTED["backend_validation_receipt"])
    replay, _payloads = v.validate(FINAL_INPUTS_PATH)
    replay_raw = v.result_bytes(replay)
    if replay_raw != validation_raw:
        raise RuntimeError("B007 backend validator replay differs from the frozen receipt")
    if (
        replay.get("status") != "passed_isolated_final_backend_ready_for_admission"
        or replay.get("record_count") != ADMISSION_EXPECTED["record_count"]
        or replay.get("new_record_count") != ADMISSION_EXPECTED["new_record_count"]
        or replay.get("validator_checks_passed") != ADMISSION_EXPECTED["validator_check_count"]
        or replay.get("validator_checks_total") != ADMISSION_EXPECTED["validator_check_count"]
        or replay.get("resolved_reference_count") != ADMISSION_EXPECTED["resolved_reference_count"]
        or replay.get("base_stable_ids_preserved") is not True
        or replay.get("live_backend_mutated") is not False
        or replay.get("boundary_admitted") is not False
    ):
        raise RuntimeError("B007 backend validation receipt does not satisfy admission invariants")

    live_before = verify_base_live()
    if not set(live_before) <= set(staged):
        raise RuntimeError("isolated B007 backend does not retain every B006 live payload path")
    candidate_path = lane_path(expected_pdf["source_path"])
    candidate_raw = candidate_path.read_bytes()
    if identity(candidate_raw) != {"bytes": expected_pdf["bytes"], "sha256": expected_pdf["sha256"]}:
        raise RuntimeError("terminal candidate PDF differs from the frozen admission binding")
    output_before = PROMOTED_PDF_PATH.read_bytes() if PROMOTED_PDF_PATH.is_file() else None
    if output_before is not None and output_before != candidate_raw:
        raise RuntimeError("refusing to overwrite a nonmatching canonical B007 PDF")
    if BOUNDARY_RECEIPT_PATH.exists():
        raise RuntimeError("B007 boundary receipt already exists; use --verify-admitted instead of re-admitting")
    pdf_admission_action = "created_from_terminal_candidate" if output_before is None else "verified_preexisting_exact"
    receipt_raw = construct_receipt(pdf_admission_action)
    if m.payload_privacy_findings({"receipt.json": receipt_raw}, m.build_records()[1]["prohibited_token"])["prohibited_requester_token_paths"]:
        raise RuntimeError("deterministic B007 boundary receipt failed the requester-token privacy scan")
    if m.payload_privacy_findings({"receipt.json": receipt_raw}, m.build_records()[1]["prohibited_token"])["absolute_local_user_profile_path_paths"]:
        raise RuntimeError("deterministic B007 boundary receipt contains an absolute local profile path")
    return {
        "staged": staged,
        "live_before": live_before,
        "candidate_raw": candidate_raw,
        "output_before": output_before,
        "pdf_admission_action": pdf_admission_action,
        "receipt_raw": receipt_raw,
    }


def atomic_write(path: Path, raw: bytes) -> None:
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
    return {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_dir()
    }


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


def acquire_transaction_lock() -> bytes:
    if TRANSACTION_JOURNAL_PATH.exists():
        raise RuntimeError("a prior B007 admission journal exists; manual recovery is required")
    lock_raw = canonical_json({
        "boundary_id": BOUNDARY_ID,
        "recorded_at": RECORDED_AT,
        "status": "authorized_cli_admission_in_progress",
    })
    try:
        descriptor = os.open(TRANSACTION_LOCK_PATH, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise RuntimeError("another B007 admission transaction holds the narrow lock") from exc
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(lock_raw)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        if TRANSACTION_LOCK_PATH.exists():
            TRANSACTION_LOCK_PATH.unlink()
        raise
    if TRANSACTION_LOCK_PATH.read_bytes() != lock_raw:
        TRANSACTION_LOCK_PATH.unlink(missing_ok=True)
        raise RuntimeError("B007 admission lock readback failed")
    return lock_raw


def construct_transaction_journal(context: dict[str, Any]) -> bytes:
    output_before: bytes | None = context["output_before"]
    pdf_prestate: dict[str, Any]
    if output_before is None:
        pdf_prestate = {"path": PROMOTED_PDF_PATH.relative_to(LANE).as_posix(), "state": "absent"}
    else:
        pdf_prestate = {
            "path": PROMOTED_PDF_PATH.relative_to(LANE).as_posix(),
            "state": "present_exact",
            **identity(output_before),
        }
    return canonical_json({
        "$schema": "r011-b007-admission-transaction-journal/v1",
        "base_prestate_inventory": {
            "bytes": BASE_EXPECTED["inventory_bytes"],
            "file_count": BASE_EXPECTED["inventory_file_count"],
            "sha256": BASE_EXPECTED["inventory_sha256"],
        },
        "boundary_id": BOUNDARY_ID,
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
        _stage_digest, _stage_count, _stage_bytes, stage_now = inventory_identity(STAGE_EXPORTS)
        output_now = PROMOTED_PDF_PATH.read_bytes() if PROMOTED_PDF_PATH.is_file() else None
        if live_now != live_before:
            raise RuntimeError("live backend changed after preflight and before the first admission write")
        if stage_now != staged:
            raise RuntimeError("isolated B007 stage changed after preflight and before admission")
        if lane_path(ADMISSION_EXPECTED["pdf"]["source_path"]).read_bytes() != candidate_raw:
            raise RuntimeError("terminal candidate PDF changed after preflight and before admission")
        if output_now != output_before:
            raise RuntimeError("canonical B007 PDF state changed after preflight and before admission")
        if BOUNDARY_RECEIPT_PATH.exists():
            raise RuntimeError("B007 boundary receipt appeared after preflight; refusing admission race")

        journal_raw = construct_transaction_journal(context)
        journal_written = True
        atomic_write(TRANSACTION_JOURNAL_PATH, journal_raw)
        if TRANSACTION_JOURNAL_PATH.read_bytes() != journal_raw:
            raise RuntimeError("B007 admission journal readback failed")

        order = sorted(path for path in staged if path != "manifest.json") + ["manifest.json"]
        for relative in order:
            written.append(relative)
            atomic_write(LIVE_EXPORTS / relative, staged[relative])
        if expected_pdf_action == "created_from_terminal_candidate":
            pdf_written = True
            atomic_write(PROMOTED_PDF_PATH, candidate_raw)

        digest, count, total, live_after = inventory_identity(LIVE_EXPORTS)
        if live_after != staged or {
            "file_count": count,
            "bytes": total,
            "sha256": digest,
        } != ADMISSION_EXPECTED["stage_inventory"]:
            raise RuntimeError("post-promotion live backend readback differs from the exact stage")
        if not PROMOTED_PDF_PATH.is_file() or PROMOTED_PDF_PATH.read_bytes() != candidate_raw:
            raise RuntimeError("post-promotion canonical PDF readback differs from the terminal candidate")
        receipt_written = True
        atomic_write(BOUNDARY_RECEIPT_PATH, receipt_raw)
        if BOUNDARY_RECEIPT_PATH.read_bytes() != receipt_raw:
            raise RuntimeError("post-promotion boundary receipt readback differs")
        TRANSACTION_JOURNAL_PATH.unlink()
        journal_written = False
        TRANSACTION_LOCK_PATH.unlink()
    except Exception as promotion_error:
        rollback_errors: list[str] = []
        if BOUNDARY_RECEIPT_PATH.exists():
            try:
                BOUNDARY_RECEIPT_PATH.unlink()
            except Exception as exc:
                rollback_errors.append(f"boundary receipt: {exc}")
        for relative in rollback_write_order(written):
            destination = LIVE_EXPORTS / relative
            before = live_before.get(relative)
            try:
                if before is None:
                    if destination.exists():
                        destination.unlink()
                else:
                    atomic_write(destination, before)
            except Exception as exc:
                rollback_errors.append(f"backend/{relative}: {exc}")
        if pdf_written:
            try:
                if PROMOTED_PDF_PATH.exists():
                    PROMOTED_PDF_PATH.unlink()
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
            rollback_errors.append("live backend did not return to the exact B006 pre-state")
        if (PROMOTED_PDF_PATH.read_bytes() if PROMOTED_PDF_PATH.is_file() else None) != output_before:
            rollback_errors.append("canonical PDF did not return to its exact pre-state")
        if BOUNDARY_RECEIPT_PATH.exists():
            rollback_errors.append("boundary receipt remains after rollback")
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


def verify_admitted() -> bytes:
    gaps = admission_binding_gaps()
    if gaps:
        raise RuntimeError("B007 admission bindings are not frozen: " + ", ".join(gaps))
    if TRANSACTION_LOCK_PATH.exists() or TRANSACTION_JOURNAL_PATH.exists():
        raise RuntimeError("B007 admission lock or journal remains after claimed admission")
    digest, count, total, live = inventory_identity(LIVE_EXPORTS)
    stage_digest, stage_count, stage_total, staged = inventory_identity(STAGE_EXPORTS)
    if live != staged or (digest, count, total) != (stage_digest, stage_count, stage_total):
        raise RuntimeError("live B007 backend is not byte-identical to the frozen isolated stage")
    if {"file_count": count, "bytes": total, "sha256": digest} != ADMISSION_EXPECTED["stage_inventory"]:
        raise RuntimeError("live B007 backend inventory differs from the frozen admission binding")
    pdf = ADMISSION_EXPECTED["pdf"]
    if not PROMOTED_PDF_PATH.is_file() or identity(PROMOTED_PDF_PATH.read_bytes()) != {"bytes": pdf["bytes"], "sha256": pdf["sha256"]}:
        raise RuntimeError("promoted B007 PDF differs from the frozen admission binding")
    if not BOUNDARY_RECEIPT_PATH.is_file():
        raise RuntimeError("B007 boundary receipt is absent")
    actual_receipt = BOUNDARY_RECEIPT_PATH.read_bytes()
    parsed_receipt = json.loads(actual_receipt)
    pdf_admission_action = parsed_receipt.get("promoted_pdf", {}).get("admission_action")
    expected_receipt = construct_receipt(pdf_admission_action)
    if actual_receipt != expected_receipt:
        raise RuntimeError("B007 boundary receipt differs from its deterministic replay")
    return expected_receipt


def readiness_gaps() -> list[str]:
    gaps = [f"admission.{item}" for item in admission_binding_gaps()]
    gaps.extend(f"generator.{item}" for item in m.final_binding_gaps())
    if TRANSACTION_LOCK_PATH.exists():
        gaps.append("transaction.lock_present")
    if TRANSACTION_JOURNAL_PATH.exists():
        gaps.append("transaction.journal_present")
    if BOUNDARY_RECEIPT_PATH.exists():
        gaps.append("admission.boundary_receipt_already_present")
    try:
        verify_base_live()
    except Exception:
        gaps.append("live_backend.not_exact_admitted_b006_prestate")
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
    if admission_binding_gaps():
        failures.append("frozen admission bindings are incomplete or malformed")
    if m.final_binding_gaps():
        failures.append("frozen generator bindings are incomplete or do not match disk")
    if canonical_json({"b": 1, "a": "é"}) != canonical_json({"a": "é", "b": 1}):
        failures.append("canonical JSON is not stable across insertion order")
    if rollback_write_order(["a.jsonl", "b.jsonl", "manifest.json"])[-1] != "manifest.json":
        failures.append("rollback does not restore the backend manifest last")
    try:
        promote({}, authorization=None)
        failures.append("promotion accepted a missing internal authorization")
    except PermissionError:
        pass
    if (
        TRANSACTION_LOCK_PATH.parent != STAGE_EXPORTS.parent
        or TRANSACTION_JOURNAL_PATH.parent != STAGE_EXPORTS.parent
        or TRANSACTION_LOCK_PATH.exists()
        or TRANSACTION_JOURNAL_PATH.exists()
    ):
        failures.append("narrow transaction marker paths are invalid or unexpectedly occupied")
    digest, count, total, _payloads = inventory_identity(LIVE_EXPORTS)
    if (digest, count, total) != (
        BASE_EXPECTED["inventory_sha256"],
        BASE_EXPECTED["inventory_file_count"],
        BASE_EXPECTED["inventory_bytes"],
    ):
        failures.append("live backend is not the exact B006 pre-state during self-test")
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
    return g.canonical_json(value)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--promote", action="store_true", help="perform the exact guarded PDF/backend admission transaction")
    modes.add_argument("--verify-admitted", action="store_true", help="read-only exact post-admission verification")
    modes.add_argument("--check-readiness", action="store_true", help="list all still-unfrozen exact admission bindings")
    modes.add_argument("--self-test", action="store_true", help="run pure fail-closed helper checks")
    args = parser.parse_args()

    if args.self_test:
        failures = self_test()
        print(result("passed" if not failures else "failed", failures, self_test_count=9))
        return 0 if not failures else 1
    if args.check_readiness:
        gaps = readiness_gaps()
        print(result(
            "ready" if not gaps else "blocked_unfrozen_exact_bindings",
            [],
            deferred_bindings=gaps,
            exact_binding_manifest=FINAL_INPUTS_PATH.relative_to(LANE).as_posix(),
        ))
        return 0 if not gaps else 2
    if args.verify_admitted:
        try:
            receipt_raw = verify_admitted()
        except Exception as exc:
            print(result("refused", [str(exc)]))
            return 2
        print(result("passed_exact_admission_readback", [], receipt=identity(receipt_raw, BOUNDARY_RECEIPT_PATH.relative_to(LANE).as_posix())))
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
    except Exception as exc:
        print(result("failed", [str(exc)]))
        return 1
    print(result("admitted_exact_pdf_and_backend", [], mutation_performed=True, receipt=receipt_identity))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
