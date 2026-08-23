#!/usr/bin/env python3
"""Write the isolated terminal-V3 B008 backend stage, never the live backend."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import generate_backend_b008_v3 as generator


def inspect_existing(payloads: dict[str, bytes]) -> str:
    root = generator.FINAL_EXPORTS
    if not root.exists():
        return "absent"
    if not root.is_dir():
        raise RuntimeError(f"terminal-V3 stage path is not a directory: {root}")
    existing = {
        path.relative_to(root).as_posix(): path
        for path in root.rglob("*")
        if path.is_file()
    }
    stale = sorted(set(existing) - set(payloads))
    if stale:
        raise RuntimeError(f"refusing terminal-V3 stage with stale files: {stale}")
    for relative, path in existing.items():
        if path.read_bytes() != payloads[relative]:
            raise RuntimeError(f"refusing to overwrite differing terminal-V3 payload: {relative}")
    return "exact" if set(existing) == set(payloads) else "partial_exact"


def write_payloads(payloads: dict[str, bytes]) -> str:
    state = inspect_existing(payloads)
    if state == "exact":
        return "already_exact"
    generator.FINAL_EXPORTS.mkdir(parents=True, exist_ok=True)
    for relative in sorted(payloads):
        destination = generator.FINAL_EXPORTS / relative
        if destination.exists():
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payloads[relative])
        if destination.read_bytes() != payloads[relative]:
            raise RuntimeError(f"terminal-V3 payload readback mismatch: {relative}")
    if inspect_existing(payloads) != "exact":
        raise RuntimeError("terminal-V3 stage did not reach exact complete state")
    return "written_new" if state == "absent" else "resumed_exact"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="generate in memory and inspect any stage without writing")
    args = parser.parse_args()
    payloads = generator.build_payloads()
    state = inspect_existing(payloads)
    if not args.check:
        state = write_payloads(payloads)
    manifest = json.loads(payloads["manifest.json"])
    print(
        generator.g.canonical_json(
            {
                "boundary_id": generator.BOUNDARY_ID,
                "result": "PASS_TERMINAL_V3_STAGE_READY",
                "write_state": "read_only_" + state if args.check else state,
                "payload_count": len(payloads),
                "record_count": sum(manifest["record_counts"].values()),
                "new_final_v3_record_count": manifest["new_final_v3_record_count"],
                "final_v3_binding": manifest["final_v3_binding"]["status"],
                "prefinal_stage_mutated": False,
                "live_backend_mutated": False,
                "admission_or_promotion_performed": False,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
