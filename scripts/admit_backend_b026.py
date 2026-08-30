#!/usr/bin/env python3
"""Fail-closed R011-B026 backend-admission gate.

The wrapper remains read-only for ``--self-check`` and ``--probe``.  Admission
or replay is delegated only to the exact registered compiler and only after the
finished asset closure plus exact deterministic reader/build/whole-reader-QA
binding replay successfully.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

from b026_pipeline_contract import (
    BACKEND_ADMISSION_RECEIPT_PATH,
    BACKEND_REPLAY_RECEIPT_PATH,
    BASE_ADMISSION,
    BASE_BACKEND,
    BASE_REPLAY,
    BINDINGS_PATH,
    BOUNDARY_ID,
    StageGateError,
    identity,
    load_asset_closure,
    load_bindings,
    offline_self_check,
    repo_path,
    verify_record,
)


COMPILER = {
    "path": "scripts/compile_backend_b026.py",
    "bytes": 68_076,
    "sha256": "518dc7e72cbe3c7c25b034cee2fd642e98f125b408c423b7996fc53a290d017b",
}


def probe() -> dict:
    live_manifest = identity(repo_path(BASE_BACKEND["path"]))
    exact_base = {key: BASE_BACKEND[key] for key in ("path", "bytes", "sha256")}
    if live_manifest == exact_base:
        phase = "pre_admission"
        base_manifest = verify_record("base_backend", BASE_BACKEND)
        binding = load_bindings(require_complete=True)
    else:
        from compile_backend_b026 import load_binding_against_frozen_preimage

        phase = "interrupted_or_admitted_b026"
        binding = load_binding_against_frozen_preimage()
        base_manifest = identity(repo_path("qa/b026-backend-admission/preimages-R011-B026/manifest.json"))
        if (base_manifest["bytes"], base_manifest["sha256"]) != (BASE_BACKEND["bytes"], BASE_BACKEND["sha256"]):
            raise StageGateError("B026 backend resume lacks the exact B025 manifest preimage")
    asset = load_asset_closure(require_complete=True)
    base = {
        "manifest": base_manifest,
        "admission": verify_record("base_admission", BASE_ADMISSION),
        "replay": verify_record("base_replay", BASE_REPLAY),
    }
    compiler = identity(repo_path(COMPILER["path"]))
    if (compiler["bytes"], compiler["sha256"]) != (COMPILER["bytes"], COMPILER["sha256"]):
        raise StageGateError("registered B026 backend compiler identity changed")
    return {
        "$schema": "interlanguage.r011-b026-backend-admission-gate/v1",
        "boundary_id": BOUNDARY_ID,
        "status": "PASS_B026_BACKEND_ADMISSION_READY",
        "phase": phase,
        "live_manifest": live_manifest,
        "base": base,
        "asset_closure": asset["receipt"],
        "binding": identity(BINDINGS_PATH),
        "bound_reader": binding["post_build_outputs"]["candidate_pdf"],
        "compiler": compiler,
        "required_mutation_outputs": [BACKEND_ADMISSION_RECEIPT_PATH, BACKEND_REPLAY_RECEIPT_PATH],
        "writes_performed": False,
        "backend_mutated": False,
        "network_used": False,
        "credentials_accessed": False,
        "git_used": False,
    }


def dispatch(mode: str) -> int:
    probe()
    completed = subprocess.run(
        [sys.executable, str(repo_path(COMPILER["path"])), mode],
        cwd=str(repo_path(".")),
        check=False,
    )
    return completed.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--self-check", action="store_true")
    mode.add_argument("--probe", action="store_true")
    mode.add_argument("--admit", action="store_true")
    mode.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        result = offline_self_check("b026-backend-admission")
    elif args.probe:
        result = probe()
    else:
        return dispatch("--admit" if args.admit else "--verify")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except StageGateError as exc:
        raise SystemExit(f"REFUSED: {exc}")
