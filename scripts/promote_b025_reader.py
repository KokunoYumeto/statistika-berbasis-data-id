#!/usr/bin/env python3
"""Atomically promote only the exact post-build-bound R011-B025 learner PDF."""

from __future__ import annotations

import argparse
import json
import os

from b025_pipeline_contract import (
    BOUNDARY_ID,
    BINDINGS_PATH,
    FINAL_READER_PATH,
    POST_BUILD_ROLES,
    PROMOTION_RECEIPT_PATH,
    StageGateError,
    canonical,
    identity,
    load_bindings,
    offline_self_check,
    repo_path,
)


def projection() -> dict:
    binding = load_bindings(require_complete=True)
    source = binding["post_build_outputs"]["candidate_pdf"]
    target_path = repo_path(FINAL_READER_PATH)
    target = identity(target_path) if target_path.is_file() else None
    if target is not None and {k: target[k] for k in ("bytes", "sha256")} != {k: source[k] for k in ("bytes", "sha256")}:
        raise StageGateError("existing B025 stable reader differs from bound candidate")
    return {
        "$schema": "interlanguage.r011-b025-reader-promotion/v1",
        "boundary_id": BOUNDARY_ID,
        "status": "PASS_EXACT_B025_READER_PROMOTION_READY",
        "post_build_binding": identity(BINDINGS_PATH),
        "source": source,
        "target": target,
        "byte_identical": target is not None,
        "complete_corpus": False,
        "publication_performed": False,
        "network_used": False,
        "credentials_accessed": False,
        "git_used": False,
    }


def promote() -> dict:
    result = projection()
    source_path = repo_path(POST_BUILD_ROLES["candidate_pdf"]["path"])
    target_path = repo_path(FINAL_READER_PATH)
    if result["target"] is None:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = target_path.with_name(target_path.name + ".b025.tmp")
        if temporary.exists():
            raise StageGateError(f"refusing stale promotion temporary: {temporary}")
        temporary.write_bytes(source_path.read_bytes())
        if identity(temporary)["sha256"] != result["source"]["sha256"]:
            temporary.unlink(missing_ok=True)
            raise StageGateError("promotion temporary did not preserve candidate bytes")
        os.replace(temporary, target_path)
    target = identity(target_path)
    if {k: target[k] for k in ("bytes", "sha256")} != {k: result["source"][k] for k in ("bytes", "sha256")}:
        raise StageGateError("promoted reader differs from bound candidate")
    payload = {**result, "status": "PASS_EXACT_B025_READER_ATOMICALLY_PROMOTED_AND_VERIFIED", "target": target, "byte_identical": True}
    receipt = repo_path(PROMOTION_RECEIPT_PATH)
    receipt.parent.mkdir(parents=True, exist_ok=True)
    raw = canonical(payload)
    if receipt.exists() and receipt.read_bytes() != raw:
        raise StageGateError("refusing to replace a different B025 promotion receipt")
    temporary = receipt.with_suffix(".json.tmp")
    if temporary.exists():
        raise StageGateError(f"refusing stale receipt temporary: {temporary}")
    temporary.write_bytes(raw)
    os.replace(temporary, receipt)
    return {**payload, "receipt": identity(receipt)}


def verify() -> dict:
    receipt = repo_path(PROMOTION_RECEIPT_PATH)
    if not receipt.is_file():
        raise StageGateError("B025 promotion receipt is absent")
    observed = json.loads(receipt.read_text(encoding="utf-8"))
    ready = projection()
    expected = {**ready, "status": "PASS_EXACT_B025_READER_ATOMICALLY_PROMOTED_AND_VERIFIED", "target": identity(repo_path(FINAL_READER_PATH)), "byte_identical": True}
    if receipt.read_bytes() != canonical(expected):
        raise StageGateError("B025 promotion receipt does not replay")
    return {**expected, "status": "PASS_EXACT_B025_READER_PROMOTION_REPLAY", "receipt": identity(receipt)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--self-check", action="store_true")
    mode.add_argument("--probe", action="store_true")
    mode.add_argument("--promote", action="store_true")
    mode.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    result = offline_self_check("b025-reader-promotion") if args.self_check else (projection() if args.probe else (promote() if args.promote else verify()))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except StageGateError as exc:
        raise SystemExit(f"REFUSED: {exc}")
