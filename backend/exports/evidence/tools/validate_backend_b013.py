#!/usr/bin/env python3
"""Validate an isolated terminal R011-B013 backend stage without mutating it."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
GENERATOR = HERE / "generate_backend_b013.py"


def load_generator():
    spec = importlib.util.spec_from_file_location("r011_b013_backend_final", GENERATOR)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load terminal B013 generator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", type=Path, required=True)
    args = parser.parse_args()
    module = load_generator()
    result = module.run(None, args.stage)
    result["status"] = "PASS_B013_FINAL_VALIDATED_ON_DISK"
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()






