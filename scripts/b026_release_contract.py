#!/usr/bin/env python3
"""Read-only, fail-closed contract for the R011-B026 release pipeline.

This module extends :mod:`b026_pipeline_contract` without editing the backend
agent's contract.  It adds the stable-reader, package, existing-lineage, and
publication-finalization gates.  Missing whole-reader QA, post-build binding,
backend admission/replay, promotion, package, or public receipts are reported
as pending in self-check mode and are hard failures for mutating stages.
Importing this module never writes, uses Git, reads credentials, or performs
network I/O.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import b026_pipeline_contract as pipeline


ROOT = pipeline.ROOT
BOUNDARY_ID = pipeline.BOUNDARY_ID
BASE_BOUNDARY_ID = pipeline.BASE_BOUNDARY_ID
NEXT_BOUNDARY_ID = pipeline.NEXT_BOUNDARY_ID
MODEL = pipeline.MODEL
UPSTREAM_COMMIT = pipeline.UPSTREAM_COMMIT
UPSTREAM_TREE = pipeline.UPSTREAM_TREE
StageGateError = pipeline.StageGateError
canonical = pipeline.canonical
identity = pipeline.identity
repo_path = pipeline.repo_path

RELEASE_ID = "R011-B026-v2026.08.30.1"
VERSION = "2026.08.30.1-R011-B026"
VERSION_LABEL = "v2026.08.30.1"
RELEASE_DATE = "2026-08-30"
GITHUB_TAG = "r011-b026-2026.08.30.1"
RELEASE_DIR = ROOT / "release/b026" / RELEASE_ID
CONFIG_PATH = RELEASE_DIR / "RELEASE_INPUTS.json"
FINAL_READER_PATH = "output/pdf/statistika-berbasis-data-batas-R011-B026.pdf"
PROMOTION_RECEIPT_PATH = "qa/b026-reader/R011-B026_READER_PROMOTION_RECEIPT.json"
ZENODO_RECEIPT_PATH = (
    f"qa/b026-publication/ZENODO_PUBLICATION_RECEIPT_{RELEASE_ID}.json"
)
GITHUB_RECEIPT_PATH = (
    f"release/b026/{RELEASE_ID}/GITHUB_PUBLICATION_RECEIPT.json"
)
FINALIZATION_ROOT = ROOT / "qa/b026-publication-finalization"
FINALIZATION_RECEIPT_PATH = (
    "qa/b026-publication-finalization/"
    "R011-B026_PUBLICATION_FINALIZATION_RECEIPT.json"
)
FINALIZATION_REPLAY_PATH = (
    "qa/b026-publication-finalization/"
    "R011-B026_PUBLICATION_FINALIZATION_REPLAY.json"
)

PRIOR_ZENODO_RECEIPT = {
    "path": "qa/b025-publication/"
    "ZENODO_PUBLICATION_RECEIPT_R011-B025-v2026.08.29.4.json",
    "bytes": 2_392,
    "sha256": "4e5a5c13bf9c611f0f2d7ad65d0b089f4e5eace1ac8237c5a8e3ad5dae7331f3",
    "record_id": 22_166_545,
    "doi": "10.5281/zenodo.22166545",
}
PRIOR_GITHUB_RECEIPT = {
    "path": "release/b025/R011-B025-v2026.08.29.4/"
    "GITHUB_PUBLICATION_RECEIPT.json",
    "bytes": 2_328,
    "sha256": "16ffda0ce44adc6961e13611c9858aa60b2afdca021014bae1c9ba2c8264f2ee",
    "commit": "a8d13b8e90129ee56272736019acc363755a5682",
    "tag": "r011-b025-2026.08.29.4",
}

BACKEND_ADMISSION_RECEIPT_PATH = pipeline.BACKEND_ADMISSION_RECEIPT_PATH
BACKEND_REPLAY_RECEIPT_PATH = pipeline.BACKEND_REPLAY_RECEIPT_PATH
BINDINGS_PATH = pipeline.BINDINGS_PATH

BACKEND_ADMISSION_SCHEMA = "interlanguage.r011-b026-backend-admission/v1"
BACKEND_ADMISSION_STATUS = "PASS_B026_BACKEND_ATOMIC_ADMISSION_AND_EXACT_REPLAY"
BACKEND_REPLAY_SCHEMA = "interlanguage.r011-b026-backend-replay/v1"
BACKEND_REPLAY_STATUS = "PASS_EXACT_B026_BACKEND_REPLAY_AND_REFERENTIAL_INTEGRITY"
PROMOTION_SCHEMA = "interlanguage.r011-b026-reader-promotion/v1"
PROMOTION_STATUS = "PASS_EXACT_B026_READER_ATOMICALLY_PROMOTED_AND_VERIFIED"
PUBLIC_STATUSES = {
    "PUBLISHED_AND_ANONYMOUSLY_VERIFIED",
    "ALREADY_PUBLISHED_AND_ANONYMOUSLY_REVERIFIED",
}


def exact_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StageGateError(f"invalid UTF-8 JSON: {path}") from exc
    if not isinstance(value, dict):
        raise StageGateError(f"JSON object required: {path}")
    return value


def verify_exact(role: str, spec: dict[str, Any]) -> dict[str, Any]:
    observed = identity(repo_path(spec["path"]))
    if (observed["bytes"], observed["sha256"]) != (
        spec["bytes"],
        spec["sha256"],
    ):
        raise StageGateError(f"{role} identity changed: {observed!r}")
    return observed


def verify_prior_lineages() -> dict[str, Any]:
    zenodo_id = verify_exact("prior Zenodo receipt", PRIOR_ZENODO_RECEIPT)
    github_id = verify_exact("prior GitHub receipt", PRIOR_GITHUB_RECEIPT)
    zenodo = exact_json(repo_path(PRIOR_ZENODO_RECEIPT["path"]))
    github = exact_json(repo_path(PRIOR_GITHUB_RECEIPT["path"]))
    if (
        zenodo.get("boundary_id") != BASE_BOUNDARY_ID
        or zenodo.get("status") not in PUBLIC_STATUSES
        or zenodo.get("record_id") != PRIOR_ZENODO_RECEIPT["record_id"]
        or zenodo.get("doi") != PRIOR_ZENODO_RECEIPT["doi"]
        or zenodo.get("concept_doi") != "10.5281/zenodo.22059801"
        or zenodo.get("access_right") != "open"
        or zenodo.get("anonymous_public_byte_readback") is not True
    ):
        raise StageGateError("prior Zenodo lineage receipt changed")
    if (
        github.get("boundary_id") != BASE_BOUNDARY_ID
        or github.get("status") not in PUBLIC_STATUSES
        or github.get("tag") != PRIOR_GITHUB_RECEIPT["tag"]
        or github.get("release_commit") != PRIOR_GITHUB_RECEIPT["commit"]
        or github.get("repository_public") is not True
        or github.get("anonymous_public_byte_readback") is not True
        or github.get("anonymous_exact_tree_readback") is not True
    ):
        raise StageGateError("prior GitHub lineage receipt changed")
    return {
        "zenodo": {**zenodo_id, "record_id": zenodo["record_id"], "doi": zenodo["doi"]},
        "github": {**github_id, "tag": github["tag"], "commit": github["release_commit"]},
    }


def verify_backend_receipts(*, require_complete: bool = True) -> dict[str, Any] | None:
    admission_path = repo_path(BACKEND_ADMISSION_RECEIPT_PATH)
    replay_path = repo_path(BACKEND_REPLAY_RECEIPT_PATH)
    if not admission_path.is_file() or not replay_path.is_file():
        if require_complete:
            raise StageGateError("B026 backend admission/replay receipts are pending")
        return None
    binding = pipeline.load_bindings(require_complete=True)
    binding_id = identity(BINDINGS_PATH)
    admission = exact_json(admission_path)
    replay = exact_json(replay_path)
    if (
        admission.get("$schema") != BACKEND_ADMISSION_SCHEMA
        or admission.get("boundary_id") != BOUNDARY_ID
        or admission.get("status") != BACKEND_ADMISSION_STATUS
        or admission.get("post_build_binding") != binding_id
        or admission.get("git_used") is not False
        or admission.get("credentials_accessed") is not False
        or admission.get("network_used") is not False
    ):
        raise StageGateError("B026 backend admission receipt changed")
    if (
        replay.get("$schema") != BACKEND_REPLAY_SCHEMA
        or replay.get("boundary_id") != BOUNDARY_ID
        or replay.get("status") != BACKEND_REPLAY_STATUS
        or replay.get("git_used") is not False
        or replay.get("credentials_accessed") is not False
        or replay.get("network_used") is not False
    ):
        raise StageGateError("B026 backend replay receipt changed")
    live_manifest = identity(repo_path("backend/exports/manifest.json"))
    if (
        admission.get("live_manifest") != live_manifest
        or replay.get("live_manifest") != live_manifest
        or admission.get("record_count") != replay.get("record_count")
        or admission.get("record_counts") != replay.get("record_counts")
        or admission.get("new_b026_record_count") != replay.get("new_b026_record_count")
        or admission.get("new_b026_record_counts") != replay.get("new_b026_record_counts")
        or admission.get("payload_inventory_sha256")
        != replay.get("payload_inventory_sha256")
    ):
        raise StageGateError("B026 backend admission/replay exact graph differs")
    manifest = exact_json(repo_path("backend/exports/manifest.json"))
    if (
        manifest.get("boundary_id") != BOUNDARY_ID
        or manifest.get("record_count") != admission.get("record_count")
        or manifest.get("build_binding", {}).get("reader_pdf")
        != binding["post_build_outputs"]["candidate_pdf"]
    ):
        raise StageGateError("live backend does not admit the exact bound B026 reader")
    return {
        "manifest": live_manifest,
        "admission": identity(admission_path),
        "replay": identity(replay_path),
        "record_count": admission["record_count"],
        "payload_inventory_sha256": admission["payload_inventory_sha256"],
    }


def verify_promoted_reader(*, require_complete: bool = True) -> dict[str, Any] | None:
    target = repo_path(FINAL_READER_PATH)
    receipt_path = repo_path(PROMOTION_RECEIPT_PATH)
    if not target.is_file() or not receipt_path.is_file():
        if require_complete:
            raise StageGateError("B026 stable reader promotion is pending")
        return None
    binding = pipeline.load_bindings(require_complete=True)
    candidate = binding["post_build_outputs"]["candidate_pdf"]
    reader = identity(target)
    if (reader["bytes"], reader["sha256"]) != (
        candidate["bytes"], candidate["sha256"],
    ):
        raise StageGateError("stable B026 reader differs from bound candidate")
    receipt = exact_json(receipt_path)
    if (
        receipt.get("$schema") != PROMOTION_SCHEMA
        or receipt.get("boundary_id") != BOUNDARY_ID
        or receipt.get("status") != PROMOTION_STATUS
        or receipt.get("source") != candidate
        or receipt.get("target") != reader
        or receipt.get("byte_identical") is not True
    ):
        raise StageGateError("B026 reader promotion receipt changed")
    return {"reader": reader, "receipt": identity(receipt_path)}


def release_ready(*, require_complete: bool = True) -> dict[str, Any] | None:
    prior = verify_prior_lineages()
    binding = pipeline.load_bindings(require_complete=require_complete)
    if binding is None:
        return None
    backend = verify_backend_receipts(require_complete=require_complete)
    promoted = verify_promoted_reader(require_complete=require_complete)
    if backend is None or promoted is None:
        return None
    return {
        "binding": binding,
        "binding_identity": identity(BINDINGS_PATH),
        "asset_closure": pipeline.load_asset_closure(require_complete=True),
        "backend": backend,
        "promotion": promoted,
        "prior_lineages": prior,
    }


def offline_release_self_check(component: str) -> dict[str, Any]:
    base = pipeline.offline_self_check(component)
    prior = verify_prior_lineages()
    pending = list(base.get("pending", []))
    ready = None
    if not pending:
        backend = verify_backend_receipts(require_complete=False)
        promoted = verify_promoted_reader(require_complete=False)
        if backend is None:
            pending.append("exact B026 backend admission and replay receipts")
        if promoted is None:
            pending.append("exact B026 stable-reader promotion and receipt")
        if not pending:
            ready = release_ready(require_complete=True)
    return {
        "$schema": "interlanguage.r011-b026-release-pipeline-self-check/v1",
        "boundary_id": BOUNDARY_ID,
        "release_id": RELEASE_ID,
        "component": component,
        "status": (
            "PASS_STATIC_B026_RELEASE_GATES_READY"
            if not pending
            else "PASS_STATIC_B026_RELEASE_PIPELINE_FAIL_CLOSED_GATES_PENDING"
        ),
        "prior_lineages": prior,
        "post_build_binding": identity(BINDINGS_PATH) if BINDINGS_PATH.is_file() else None,
        "release_ready": ready is not None,
        "pending": pending,
        "writes_performed": False,
        "output_mutated": False,
        "release_mutated": False,
        "backend_mutated": False,
        "controls_mutated": False,
        "network_used": False,
        "credentials_accessed": False,
        "git_used": False,
        "upstream_contact": False,
    }
