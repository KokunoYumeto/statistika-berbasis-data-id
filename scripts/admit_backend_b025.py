#!/usr/bin/env python3
"""Fail-closed B025 backend-admission gate and handoff to the deterministic compiler.

This wrapper is deliberately inert until the exact whole-reader binding exists.
The bounded B025 compiler writes exact B024 preimages before ``--admit`` and is
registered by exact byte/hash identity below.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

from b025_pipeline_contract import (
    BACKEND_ADMISSION_RECEIPT_PATH,
    BACKEND_REPLAY_RECEIPT_PATH,
    BASE_ADMISSION,
    BASE_BACKEND,
    BASE_REPLAY,
    BOUNDARY_ID,
    BINDINGS_PATH,
    PROMOTION_RECEIPT_PATH,
    StageGateError,
    identity,
    load_bindings,
    offline_self_check,
    repo_path,
    verify_record,
)


COMPILER = {"path": "scripts/compile_backend_b025.py", "bytes": 37_168, "sha256": "006290f5233a94a3426db0a3470d0e612dd80bbd5b5a55989603c20ece0a7993"}


def probe() -> dict:
    live_manifest = identity(repo_path(BASE_BACKEND["path"]))
    exact_base = {key: BASE_BACKEND[key] for key in ("path", "bytes", "sha256")}
    if live_manifest == exact_base:
        binding = load_bindings(require_complete=True)
        base_manifest = verify_record("base_backend", BASE_BACKEND)
        phase = "pre_admission"
    else:
        from compile_backend_b025 import load_binding_against_frozen_preimage

        binding = load_binding_against_frozen_preimage()
        preimage_path = repo_path("qa/b025-backend-admission/preimages-R011-B025/manifest.json")
        base_manifest = identity(preimage_path)
        if (base_manifest["bytes"], base_manifest["sha256"]) != (BASE_BACKEND["bytes"], BASE_BACKEND["sha256"]):
            raise StageGateError("B025 backend resume lacks the exact B024 manifest preimage")
        phase = "interrupted_or_admitted_b025"
    base = {
        "manifest": base_manifest,
        "admission": verify_record("base_admission", BASE_ADMISSION),
        "replay": verify_record("base_replay", BASE_REPLAY),
    }
    compiler_path = repo_path(COMPILER["path"])
    compiler_registered = isinstance(COMPILER["bytes"], int) and isinstance(COMPILER["sha256"], str)
    compiler = identity(compiler_path) if compiler_path.is_file() else None
    if compiler_registered and (compiler["bytes"], compiler["sha256"]) != (COMPILER["bytes"], COMPILER["sha256"]):
        raise StageGateError("registered B025 backend compiler identity changed")
    return {
        "$schema": "interlanguage.r011-b025-backend-admission-gate/v1",
        "boundary_id": BOUNDARY_ID,
        "status": "PASS_B025_BACKEND_ADMISSION_READY" if compiler_registered else "PASS_B025_BACKEND_ADMISSION_INPUTS_BOUND_COMPILER_REGISTRATION_PENDING",
        "binding": identity(BINDINGS_PATH),
        "phase": phase,
        "live_manifest": live_manifest,
        "base": base,
        "compiler": compiler,
        "compiler_registered": compiler_registered,
        "required_mutation_outputs": [BACKEND_ADMISSION_RECEIPT_PATH, BACKEND_REPLAY_RECEIPT_PATH],
        "writes_performed": False,
        "backend_mutated": False,
        "network_used": False,
        "credentials_accessed": False,
        "git_used": False,
    }


def dispatch(mode: str) -> int:
    state = probe()
    if not state["compiler_registered"]:
        raise StageGateError("B025 backend compiler is not registered; refusing backend mutation or replay")
    completed = subprocess.run([sys.executable, str(repo_path(COMPILER["path"])), mode], cwd=str(repo_path(".")), check=False)
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
        result = offline_self_check("b025-backend-admission")
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
