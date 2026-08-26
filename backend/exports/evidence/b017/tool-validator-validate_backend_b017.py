#!/usr/bin/env python3
"""Independent read-only validator for an isolated R011-B017 backend stage."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
GENERATOR = HERE / "generate_backend_b017.py"


def load_generator():
    spec = importlib.util.spec_from_file_location("r011_b017_backend_generator", GENERATOR)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load B017 backend generator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--self-test", action="store_true")
    modes.add_argument("--probe", action="store_true")
    modes.add_argument("--stage", type=Path)
    args = parser.parse_args()
    module = load_generator()
    if args.self_test:
        result = module.self_test()
        result["validator_status"] = "PASS_B017_VALIDATOR_INERT_SELF_TEST"
    elif args.probe:
        result = module.probe()
        result["validator_status"] = "PASS_B017_VALIDATOR_READ_ONLY_PROBE"
    else:
        result = module.validate_stage(args.stage)
        result["validator_status"] = "PASS_B017_INDEPENDENT_STAGE_VALIDATOR"
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
