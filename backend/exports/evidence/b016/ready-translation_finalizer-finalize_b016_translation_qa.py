#!/usr/bin/env python3
"""Replay and atomically persist the deterministic R011-B016 translation QA."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
VERIFIER = HERE / "verify_b016_translation.py"
OUTPUT = HERE / "R011-B016_TRANSLATION_QA.json"


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def replay() -> bytes:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        [sys.executable, "-B", str(VERIFIER)],
        cwd=VERIFIER.parents[2],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "translation verifier failed: "
            + completed.stderr.decode("utf-8", errors="replace")
        )
    report = json.loads(completed.stdout.decode("utf-8"))
    if report.get("status") != "PASS_EXACT_PINNED_AUTHORITY_TRANSLATION_INTEGRATION":
        raise RuntimeError("unexpected translation QA status")
    if report.get("check_summary") != {"total": 140, "passed": 140, "failed": 0}:
        raise RuntimeError("unexpected translation QA check summary")
    return completed.stdout


def main() -> None:
    first = replay()
    second = replay()
    if first != second:
        raise RuntimeError("translation QA replay bytes differ")

    temporary = OUTPUT.with_suffix(".json.tmp")
    temporary.write_bytes(first)
    os.replace(temporary, OUTPUT)

    result = {
        "status": "PASS_REPLAY_IDENTICAL_TRANSLATION_QA_PERSISTED",
        "boundary_id": "R011-B016",
        "replays": 2,
        "output": {
            "path": OUTPUT.relative_to(VERIFIER.parents[2]).as_posix(),
            "bytes": len(first),
            "sha256": sha256(first),
        },
        "verifier": {
            "path": VERIFIER.relative_to(VERIFIER.parents[2]).as_posix(),
            "bytes": VERIFIER.stat().st_size,
            "sha256": sha256(VERIFIER.read_bytes()),
        },
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
