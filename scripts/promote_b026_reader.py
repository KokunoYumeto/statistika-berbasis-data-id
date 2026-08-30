#!/usr/bin/env python3
"""Atomically promote only the exact fully bound R011-B026 learner PDF."""

from __future__ import annotations

import argparse
import json
import os

import b026_pipeline_contract as pipeline
from b026_release_contract import (
    BOUNDARY_ID,
    FINAL_READER_PATH,
    PROMOTION_RECEIPT_PATH,
    PROMOTION_SCHEMA,
    PROMOTION_STATUS,
    StageGateError,
    canonical,
    identity,
    offline_release_self_check,
    repo_path,
    verify_backend_receipts,
)


READY_STATUS = "PASS_EXACT_B026_READER_PROMOTION_READY"


def projection(*, require_complete: bool) -> dict:
    binding = pipeline.load_bindings(require_complete=require_complete)
    if binding is None:
        return offline_release_self_check("b026-reader-promotion")
    backend = verify_backend_receipts(require_complete=require_complete)
    if backend is None:
        return offline_release_self_check("b026-reader-promotion")
    source = binding["post_build_outputs"]["candidate_pdf"]
    target_path = repo_path(FINAL_READER_PATH)
    target = identity(target_path) if target_path.is_file() else None
    if target is not None and {
        key: target[key] for key in ("bytes", "sha256")
    } != {key: source[key] for key in ("bytes", "sha256")}:
        raise StageGateError("existing B026 stable reader differs from bound candidate")
    return {
        "$schema": PROMOTION_SCHEMA,
        "boundary_id": BOUNDARY_ID,
        "status": READY_STATUS,
        "post_build_binding": identity(pipeline.BINDINGS_PATH),
        "backend_admission": backend["admission"],
        "backend_replay": backend["replay"],
        "source": source,
        "target": target,
        "byte_identical": target is not None,
        "complete_corpus": False,
        "publication_performed": False,
        "network_used": False,
        "credentials_accessed": False,
        "git_used": False,
        "upstream_contact": False,
    }


def promote() -> dict:
    result = projection(require_complete=True)
    source_path = repo_path(result["source"]["path"])
    target_path = repo_path(FINAL_READER_PATH)
    if result["target"] is None:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = target_path.with_name(target_path.name + ".b026.tmp")
        if temporary.exists():
            raise StageGateError(f"refusing stale promotion temporary: {temporary}")
        temporary.write_bytes(source_path.read_bytes())
        if identity(temporary)["sha256"] != result["source"]["sha256"]:
            temporary.unlink(missing_ok=True)
            raise StageGateError("promotion temporary did not preserve candidate bytes")
        os.replace(temporary, target_path)
    target = identity(target_path)
    if {key: target[key] for key in ("bytes", "sha256")} != {
        key: result["source"][key] for key in ("bytes", "sha256")
    }:
        raise StageGateError("promoted reader differs from bound candidate")
    payload = {
        **result,
        "status": PROMOTION_STATUS,
        "target": target,
        "byte_identical": True,
    }
    receipt = repo_path(PROMOTION_RECEIPT_PATH)
    receipt.parent.mkdir(parents=True, exist_ok=True)
    raw = canonical(payload)
    if receipt.exists() and receipt.read_bytes() != raw:
        raise StageGateError("refusing to replace a different B026 promotion receipt")
    temporary = receipt.with_name(receipt.name + ".tmp")
    if temporary.exists():
        raise StageGateError(f"refusing stale promotion-receipt temporary: {temporary}")
    temporary.write_bytes(raw)
    os.replace(temporary, receipt)
    return {**payload, "receipt": identity(receipt)}


def verify() -> dict:
    receipt = repo_path(PROMOTION_RECEIPT_PATH)
    if not receipt.is_file():
        raise StageGateError("B026 promotion receipt is absent")
    ready = projection(require_complete=True)
    expected = {
        **ready,
        "status": PROMOTION_STATUS,
        "target": identity(repo_path(FINAL_READER_PATH)),
        "byte_identical": True,
    }
    if receipt.read_bytes() != canonical(expected):
        raise StageGateError("B026 promotion receipt does not replay")
    return {
        **expected,
        "status": "PASS_EXACT_B026_READER_PROMOTION_REPLAY",
        "receipt": identity(receipt),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--self-check", action="store_true")
    mode.add_argument("--probe", action="store_true")
    mode.add_argument("--promote", action="store_true")
    mode.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        result = offline_release_self_check("b026-reader-promotion")
    elif args.probe:
        result = projection(require_complete=False)
    elif args.promote:
        result = promote()
    else:
        result = verify()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except StageGateError as exc:
        raise SystemExit(f"REFUSED: {exc}")
