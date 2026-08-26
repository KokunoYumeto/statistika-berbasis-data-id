#!/usr/bin/env python3
"""Compile and validate the deterministic R011-B017 modular-backend append.

The module is inert at import time.  ``--self-test`` and ``--probe`` perform
read-only checks.  ``--output`` writes only an isolated stage beneath one of
the explicitly bounded B017 stage roots, and only after a terminal contract
binds the deterministic build, reader, source snapshot, and zero-defect visual
receipt.  The live backend, canonical source, controls, release state, Git,
network, credentials, publication, and upstream state are never mutated here.

Stable identities use source labels or locale-neutral topology codes.  Neither
Indonesian wording nor reader page numbers are identity material.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import shutil
import sys
import unicodedata
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Any

import jsonschema


SCRIPT_PATH = Path(__file__).resolve()
LANE = SCRIPT_PATH.parents[1]
INTERLANGUAGE_ROOT = LANE.parents[2]
BOUNDARY_ID = "R011-B017"
BASE_BOUNDARY_ID = "R011-B016"
SCHEMA_VERSION = "0.1.0"
WORKFLOW_ID = "r011-openintro-statistics-id-b017-backend-final"
RECORDED_AT = "2026-08-26T04:40:00+02:00"
NAMESPACE = uuid.UUID("3f5320fb-d2a2-4aa6-a8fe-298715378407")
PROVENANCE = "OpenAI Codex gpt-5.6-sol, Ultra"

BASE_EXPORTS = LANE / "backend/exports"
BASE_MANIFEST = BASE_EXPORTS / "manifest.json"
PREP_ROOT = LANE / "qa/b017-backend-prep"
FINAL_ROOT = LANE / "qa/b017-backend-final"
SCRATCH_ROOT = LANE / "scratch/b017-backend-candidate"
TERMINAL_CONTRACT = PREP_ROOT / "R011-B017_TERMINAL_INPUTS.json"

RECORD_PATHS = {
    "programs": "core/programs.jsonl",
    "courses": "core/courses.jsonl",
    "resources": "core/resources.jsonl",
    "editions": "core/editions.jsonl",
    "units": "core/units.jsonl",
    "concepts": "core/concepts.jsonl",
    "segments": "core/segments.jsonl",
    "assets": "core/assets.jsonl",
    "relations": "core/relations.jsonl",
    "rights": "core/rights.jsonl",
    "corrections": "core/corrections.jsonl",
    "localizations": "locales/id-ID/localizations.jsonl",
    "terms": "locales/id-ID/terms.jsonl",
    "qa_events": "evidence/qa_events.jsonl",
    "artifacts": "evidence/artifacts.jsonl",
}

BASE_MANIFEST_IDENTITY = {
    "bytes": 88685,
    "sha256": "377450795cbbb3342ed66e176589ccf313c8e38be74e1470b4d2d48e5683500a",
}
BASE_INVENTORY_IDENTITY = {
    "identity_kind": "directory-inventory-tsv-sha256/v1",
    "files": 435,
    "bytes": 221639847,
    "sha256": "507be7a86cc525ebc630e941616ec6fbda99e54f5d951a40f8e96cc83fcb6a98",
}
BASE_RECORD_COUNT = 6199
BASE_RECORD_COUNTS = {
    "artifacts": 417,
    "assets": 354,
    "concepts": 221,
    "corrections": 129,
    "courses": 1,
    "editions": 1,
    "localizations": 540,
    "programs": 1,
    "qa_events": 190,
    "relations": 2981,
    "resources": 1,
    "rights": 43,
    "segments": 540,
    "terms": 243,
    "units": 537,
}

INTEROPERABILITY_SPEC = {
    "path": (
        "outputs/01a01ec1-e685-70d0-b022-211396334723/curriculum_logbook/"
        "05_MODULAR_BACKEND_INTEROPERABILITY_V0.md"
    ),
    "bytes": 5204,
    "sha256": "fdb6c8fa87ea88d8fcb6ddf40415d8a6a6da315025b9b18eb917190f508b1c5f",
}

READY_INPUTS: dict[str, tuple[str, int, str]] = {
    "boundary_blueprint": (
        "scratch/b017-source/R011-B017_BOUNDARY_BLUEPRINT.json",
        12381,
        "27f4b8d560e57af1fffb2fddb5974382ffbe8ec515a9a2209cde4dc3dfa6a0bf",
    ),
    "candidate_receipt": (
        "scratch/b017-candidate/R011-B017_CANDIDATE_RECEIPT.json",
        8066,
        "094dea75910939cce90287bb0a547260dcd385413759cece40bed36b5fc1ef22",
    ),
    "candidate_qa": (
        "scratch/b017-candidate/R011-B017_CANDIDATE_QA.json",
        8163,
        "93b2b3e038020c48a6ed5e0afaf4ef433d9f7b00093945fe4c5e50699447b1fe",
    ),
    "terminology_qa_json": (
        "scratch/r011-terminology-qa/R011_TERMINOLOGY_QA_2026-08-26.json",
        11353,
        "2fb64887ed8d5a4800aff4a0fec9116441f60d6e6c8f19b2a2496eefa2838737",
    ),
    "terminology_qa_markdown": (
        "scratch/r011-terminology-qa/R011_TERMINOLOGY_QA_2026-08-26.md",
        3340,
        "d094bb96c17e199043dcdd21541ad45cf5b1093fdbe122311213b86b85be7c47",
    ),
    "main_fragment": (
        "scratch/b017-candidate/R011-B017_ch_distributions_1927-2110_CANDIDATE.tex",
        11506,
        "ab47c5a5523385ad139330369a6c55fda872d4eececda05f95f02a29d40300a9",
    ),
    "eoce_fragment": (
        "scratch/b017-candidate/R011-B017_negative_binomial_distribution_CANDIDATE.tex",
        2960,
        "328f2299f3a62823f5d3aa3f4381a04c1d54dc1e03ef0443567f63e47a0455e7",
    ),
    "public_answers_fragment": (
        "scratch/b017-candidate/R011-B017_eoceSolutions_750-761_CANDIDATE.tex",
        646,
        "77bb219a207b4a1918a7343e3aec09d6851e10f50e6054eb87289c781b456696",
    ),
    "residual_english_review": (
        "scratch/b017-candidate/R011-B017_RESIDUAL_ENGLISH_REVIEW.tsv",
        1798,
        "90bdc66f3d8c7f3a727f3bb1ba6af49eada746d4bd44e20f77334687a03163fb",
    ),
    "correction_candidates": (
        "scratch/b017-candidate/R011-B017_UPSTREAM_CORRECTION_CANDIDATES.json",
        5178,
        "b2def77d1d2f4a9328590c4570e3a3ed34a0d2241e5a444f8ab51fb952b9d714",
    ),
    "main_authority": (
        "authority/upstream/openintro-statistics-fee25091fb24e89c36296fd67c48c1fcf7a93b6e/"
        "ch_distributions/TeX/ch_distributions.tex",
        91188,
        "71e4985a1bf31e9dd6897ec2bd246b3b2f8cd62ab55524a5b1bfe791e613a3a9",
    ),
    "eoce_authority": (
        "authority/upstream/openintro-statistics-fee25091fb24e89c36296fd67c48c1fcf7a93b6e/"
        "ch_distributions/TeX/negative_binomial_distribution.tex",
        2860,
        "4d6bf067db161507dbe9555a1d31ae0c220152d00ff8d1ac62800adafa7571a1",
    ),
    "public_answers_authority": (
        "authority/upstream/openintro-statistics-fee25091fb24e89c36296fd67c48c1fcf7a93b6e/"
        "extraTeX/eoceSolutions/eoceSolutions.tex",
        106045,
        "6c4e01376db4c023cc7b3f9949490e57220ef1cb831c580da71efde6ce723268",
    ),
    "integrated_main": (
        "repo/ch_distributions/TeX/ch_distributions.tex",
        94846,
        "acf988ea324d21fa0872a9ac6fc1b128c5f6d9c67095bd37d0ea4ba3ee813cbe",
    ),
    "integrated_eoce": (
        "repo/ch_distributions/TeX/negative_binomial_distribution.tex",
        2960,
        "328f2299f3a62823f5d3aa3f4381a04c1d54dc1e03ef0443567f63e47a0455e7",
    ),
    "integrated_public_answers": (
        "repo/extraTeX/eoceSolutions/eoceSolutions.tex",
        109538,
        "7a9d2bff6f6e1cd87c56a4e325316a4dd9f3fa4814311ecbab5026758087d0ba",
    ),
    "base_manifest": (
        "backend/exports/manifest.json",
        88685,
        "377450795cbbb3342ed66e176589ccf313c8e38be74e1470b4d2d48e5683500a",
    ),
}

TERMINOLOGY_EVIDENCE_DESTINATIONS = {
    "terminology_qa_json": "qa/b017-terminology/R011_TERMINOLOGY_QA_2026-08-26.json",
    "terminology_qa_markdown": "qa/b017-terminology/R011_TERMINOLOGY_QA_2026-08-26.md",
}

TERMINAL_ROLE_PATHS = {
    "candidate_builder": "scripts/build_b017_candidate.py",
    "assembled_main": (
        "scratch/b017-build-candidate/source-snapshot-b017/"
        "ch_distributions/TeX/ch_distributions.tex"
    ),
    "assembled_eoce": (
        "scratch/b017-build-candidate/source-snapshot-b017/"
        "ch_distributions/TeX/negative_binomial_distribution.tex"
    ),
    "assembled_public_answers": (
        "scratch/b017-build-candidate/source-snapshot-b017/"
        "extraTeX/eoceSolutions/eoceSolutions.tex"
    ),
    "source_manifest": "scratch/b017-build-candidate/R011-B017_SOURCE_MANIFEST.tsv",
    "source_qa": "scratch/b017-build-candidate/R011-B017_SOURCE_QA.json",
    "build_receipt": "scratch/b017-build-candidate/final/CANDIDATE_BUILD_QA_B017_FINAL.json",
    "reader_pdf": "scratch/b017-build-candidate/final/main.pdf",
    "visual_qa": "scratch/b017-build-candidate/R011-B017_VISUAL_QA.json",
}

REQUIRED_TERMINAL_GATES = {
    "source_identity",
    "translation",
    "topology",
    "mathematics",
    "exercise_answer_o001",
    "component_rights",
    "deterministic_build",
    "deterministic_replay",
    "visual_zero_defects",
    "next_cursor",
}

EXPECTED_TERMINAL_CLOSURE = {
    "section": "negativeBinomial",
    "section_number": "4.4",
    "source_authority_lines": "1927-2110",
    "subsections": 0,
    "worked_examples": 3,
    "guided_exercises": 5,
    "guided_inline_public_answers": 5,
    "onebox_blocks": 3,
    "inline_tex_figures": 1,
    "eoce_exercises": [27, 28, 29, 30],
    "eoce_parts": 13,
    "public_answers": [27, 29],
    "public_answer_parts": 7,
    "o001_companion_gaps": [28, 30],
    "o001_gap_parts": 6,
    "external_assets": 0,
    "data_files": 0,
    "code_files": 0,
    "source_corrections": [f"B017-C{number:03d}" for number in range(1, 9)],
    "restricted_solutions_accessed_or_invented": False,
    "next_source_anchor": "poisson",
    "next_source_line": 2111,
    "next_section_label_line": 2112,
    "production_model": PROVENANCE,
}

EOCE = {
    27: "roll_die",
    28: "play_darts",
    29: "sampling_at_school",
    30: "serving_volleyball",
}
PUBLIC_ANSWERS = (27, 29)
O001_GAPS = (28, 30)

TERM_DEFINITIONS = [
    {
        "code": "B017-TM001",
        "concept_key": "r011/concept/b017/negative-binomial-distribution",
        "source": "negative binomial distribution",
        "target": "distribusi binomial negatif",
        "variants": [],
        "definition": "Distribution of the trial count on which a fixed-numbered success occurs.",
    },
    {
        "code": "B017-TM002",
        "concept_key": "r011/concept/b016/c007",
        "source": "independent trials",
        "target": "percobaan yang saling independen",
        "variants": ["percobaan saling bebas"],
    },
    {
        "code": "B017-TM003",
        "concept_key": "r011/concept/b015/c006",
        "source": "success",
        "target": "sukses",
        "variants": ["berhasil", "keberhasilan"],
    },
    {
        "code": "B017-TM004",
        "concept_key": "r011/concept/b015/c007",
        "source": "failure",
        "target": "gagal",
        "variants": ["kegagalan"],
    },
    {
        "code": "B017-TM005",
        "concept_key": "r011/concept/b017/binomial-coefficient",
        "source": "binomial coefficient",
        "target": "koefisien binomial",
        "variants": ["n pilih k"],
        "definition": "Combinatorial coefficient counting selections or orderings without replacement of positions.",
    },
    {
        "code": "B017-TM006",
        "concept_key": "r011/concept/b017/fixed-number-of-successes",
        "source": "fixed number of successes",
        "target": "jumlah sukses yang tetap",
        "variants": ["banyak sukses tetap"],
        "definition": "A success count fixed in advance while the required number of trials varies.",
    },
    {
        "code": "B017-TM007",
        "concept_key": "r011/concept/b016/c008",
        "source": "fixed number of trials",
        "target": "jumlah percobaan yang tetap",
        "variants": ["banyak percobaan tetap"],
    },
    {
        "code": "B017-TM008",
        "concept_key": "r011/concept/b015/c001",
        "source": "geometric distribution",
        "target": "distribusi geometrik",
        "variants": ["distribusi geometri"],
    },
]

QA_EVENT_TYPES = [
    "base_preservation",
    "source",
    "translation",
    "terminology",
    "asset_identity",
    "rights",
    "mathematics",
    "topology",
    "build",
    "visual",
    "corrections",
    "interoperability",
    "isolation",
]

RELATION_CLASSES = {
    "contains",
    "precedes",
    "prerequisite",
    "covers",
    "lexicalizes",
    "unit_contains_segment",
    "localizes",
    "answers",
    "requires_companion_answer",
    "uses_asset",
    "corrects",
    "governs",
    "validates",
    "documents",
}

REQUIRED_VIEWS = [
    "views/resource_editions.csv",
    "views/unit_hierarchy.csv",
    "views/relations.csv",
    "views/segments_locale.csv",
    "views/terminology.csv",
    "views/exercises_answers.csv",
    "views/rights_components.csv",
    "views/corrections.csv",
    "views/qa_build_events.csv",
    "views/artifacts.csv",
]

NEW_RECORD_TYPES = {
    "artifact",
    "asset",
    "concept",
    "correction",
    "localization",
    "qa_event",
    "relation",
    "rights",
    "segment",
    "term",
    "unit",
}


class TerminalInputsUnresolved(RuntimeError):
    """The exact terminal contract is absent, incomplete, or failing."""


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def normalize(value: Any) -> Any:
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, list):
        return [normalize(item) for item in value]
    if isinstance(value, dict):
        return {normalize(str(key)): normalize(item) for key, item in value.items()}
    return value


def canonical_json_text(value: Any) -> str:
    return json.dumps(
        normalize(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def canonical_json(value: Any) -> bytes:
    return (canonical_json_text(value) + "\n").encode("utf-8")


def pretty_json(value: Any) -> bytes:
    return (json.dumps(normalize(value), ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def stable_id(stable_key: str) -> str:
    return str(uuid.uuid5(NAMESPACE, stable_key))


def identity_raw(raw: bytes) -> dict[str, Any]:
    return {"bytes": len(raw), "sha256": sha256_bytes(raw)}


def identity(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise RuntimeError(f"missing exact B017 input: {path}")
    return identity_raw(path.read_bytes())


def require(path: Path, expected: dict[str, Any]) -> bytes:
    raw = path.read_bytes() if path.is_file() else None
    observed = None if raw is None else identity_raw(raw)
    wanted = {"bytes": int(expected["bytes"]), "sha256": str(expected["sha256"])}
    if observed != wanted:
        raise RuntimeError(f"exact identity mismatch for {path}: {observed!r} != {wanted!r}")
    assert raw is not None
    return raw


def parse_json(raw: bytes, role: str) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"invalid UTF-8 JSON for {role}: {exc}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"expected JSON object for {role}")
    return value


def jsonl_bytes(rows: list[dict[str, Any]]) -> bytes:
    return "".join(
        canonical_json_text(row) + "\n" for row in sorted(rows, key=lambda item: item["id"])
    ).encode("utf-8")


def load_jsonl(raw: bytes) -> list[dict[str, Any]]:
    return [json.loads(line) for line in raw.decode("utf-8").splitlines() if line]


def csv_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, dict)):
        return canonical_json_text(value)
    return str(value)


def csv_bytes(columns: list[str], rows: list[dict[str, Any]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream, fieldnames=columns, lineterminator="\n", extrasaction="ignore"
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({column: csv_cell(row.get(column)) for column in columns})
    return stream.getvalue().encode("utf-8")


def inventory(root: Path) -> dict[str, Any]:
    if not root.is_dir():
        raise RuntimeError(f"missing exact backend directory: {root}")
    entries: list[tuple[str, int, str]] = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            raw = path.read_bytes()
            entries.append((path.relative_to(root).as_posix(), len(raw), sha256_bytes(raw)))
    payload = "".join(f"{path}\t{size}\t{digest}\n" for path, size, digest in entries).encode()
    return {
        "identity_kind": "directory-inventory-tsv-sha256/v1",
        "files": len(entries),
        "bytes": sum(size for _, size, _ in entries),
        "sha256": sha256_bytes(payload),
    }


def relative_path(path: Path) -> str:
    resolved = path.resolve()
    if not resolved.is_relative_to(LANE.resolve()):
        raise RuntimeError(f"B017 input escapes the corpus lane: {path}")
    return resolved.relative_to(LANE.resolve()).as_posix()


def input_tuple(role: str) -> tuple[Path, dict[str, Any]]:
    relative, size, digest = READY_INPUTS[role]
    return LANE / relative, {"path": relative, "bytes": size, "sha256": digest}


def bind_base(*, verify_inventory: bool) -> dict[str, Any]:
    raw = require(BASE_MANIFEST, BASE_MANIFEST_IDENTITY)
    manifest = parse_json(raw, "B016 base backend manifest")
    if (
        manifest.get("boundary_id") != BASE_BOUNDARY_ID
        or manifest.get("record_count") != BASE_RECORD_COUNT
        or manifest.get("record_counts") != BASE_RECORD_COUNTS
    ):
        raise RuntimeError("live backend is not the exact admitted R011-B016 base")
    entries = manifest.get("files")
    if not isinstance(entries, list) or len(entries) != BASE_INVENTORY_IDENTITY["files"] - 1:
        raise RuntimeError("B016 base manifest inventory cardinality changed")
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            raise RuntimeError("malformed B016 base file entry")
        require(BASE_EXPORTS / entry["path"], entry)
    observed_inventory = inventory(BASE_EXPORTS) if verify_inventory else None
    if verify_inventory and observed_inventory != BASE_INVENTORY_IDENTITY:
        raise RuntimeError("live B016 backend inventory identity changed")
    return {
        "manifest": {"path": "backend/exports/manifest.json", **BASE_MANIFEST_IDENTITY},
        "inventory": deepcopy(BASE_INVENTORY_IDENTITY),
        "record_count": BASE_RECORD_COUNT,
        "record_counts": deepcopy(BASE_RECORD_COUNTS),
        "inventory_verified": verify_inventory,
    }


def bind_ready_inputs() -> tuple[dict[str, dict[str, Any]], dict[str, bytes]]:
    bound: dict[str, dict[str, Any]] = {}
    raw: dict[str, bytes] = {}
    for role in sorted(READY_INPUTS):
        path, expected = input_tuple(role)
        raw[role] = require(path, expected)
        bound[role] = expected

    blueprint = parse_json(raw["boundary_blueprint"], "B017 boundary blueprint")
    receipt = parse_json(raw["candidate_receipt"], "B017 candidate receipt")
    qa = parse_json(raw["candidate_qa"], "B017 candidate QA")
    corrections = parse_json(raw["correction_candidates"], "B017 corrections")
    terminology_qa = parse_json(raw["terminology_qa_json"], "B017 terminology QA")
    if (
        blueprint.get("status") != "READY_FOR_TRANSLATION"
        or blueprint.get("boundary", {}).get("id") != BOUNDARY_ID
        or blueprint.get("boundary", {}).get("section_label") != "negativeBinomial"
        or blueprint.get("boundary", {}).get("next_cursor", {}).get("label") != "poisson"
        or blueprint.get("boundary", {}).get("next_cursor", {}).get("line") != 2111
    ):
        raise RuntimeError("B017 boundary blueprint topology changed")
    if (
        receipt.get("status") != "COMPLETE_BOUNDED_CANDIDATE_NOT_ADMITTED"
        or receipt.get("boundary_id") != BOUNDARY_ID
        or receipt.get("unresolved_issues") != []
    ):
        raise RuntimeError("B017 candidate receipt is not terminal bounded PASS")
    if (
        qa.get("status") != "PASS_BOUNDED_TRANSLATION_CANDIDATE"
        or qa.get("boundary_id") != BOUNDARY_ID
        or qa.get("unresolved_issues") != []
        or qa.get("structural_closure", {}).get("o001", {}).get("gap_exercises") != [28, 30]
    ):
        raise RuntimeError("B017 candidate QA closure changed")
    if (
        corrections.get("status") != "RECORDED_NOT_APPLIED_TO_AUTHORITY"
        or corrections.get("candidate_count") != 8
        or corrections.get("high_confidence_count") != 8
        or corrections.get("semantic_correction_count") != 0
    ):
        raise RuntimeError("B017 correction-candidate closure changed")
    if (
        terminology_qa.get("$schema")
        != "interlanguage.r011-terminology-field-usage-qa/v1"
        or terminology_qa.get("boundary_context") != BOUNDARY_ID
        or terminology_qa.get("status")
        != "PASS_NO_TERMINOLOGY_PROPAGATION_REQUIRED"
        or terminology_qa.get("production_model") != PROVENANCE
        or terminology_qa.get("arxiv_search", {}).get("outcome")
        != "no_suitable_same_field_indonesian_tex_source_found_in_bounded_search"
        or terminology_qa.get("arxiv_search", {}).get("fallback_required") is not True
        or len(terminology_qa.get("term_decisions", [])) != 11
        or terminology_qa.get("propagation", {}).get("canonical_changes_recommended") != 0
        or terminology_qa.get("propagation", {}).get("glossary_changes_recommended") != 0
        or terminology_qa.get("propagation", {}).get("action")
        != "No propagation is justified. Admit this record as QA evidence only."
        or terminology_qa.get("provenance_note_check", {}).get("status")
        != "PASS_ALREADY_PRESENT"
        or terminology_qa.get("write_boundary", {}).get("canonical_files_modified")
        is not False
        or terminology_qa.get("write_boundary", {}).get("backend_files_modified")
        is not False
        or terminology_qa.get("blockers") != []
    ):
        raise RuntimeError("B017 terminology field-usage QA closure changed")

    candidate_role_map = {
        "main_section_fragment": "main_fragment",
        "eoce_27_30_fragment": "eoce_fragment",
        "public_answers_27_29_fragment": "public_answers_fragment",
    }
    receipt_candidates = receipt.get("candidates", [])
    if {item.get("role") for item in receipt_candidates} != set(candidate_role_map):
        raise RuntimeError("B017 candidate role set changed")
    for item in receipt_candidates:
        expected = bound[candidate_role_map[str(item["role"])]]
        if {key: item.get(key) for key in ("path", "bytes", "sha256")} != expected:
            raise RuntimeError(f"B017 candidate receipt identity changed for {item.get('role')}")

    if raw["integrated_eoce"] != raw["eoce_fragment"]:
        raise RuntimeError("canonical B017 EoCE overlay differs from candidate")
    for integrated, fragment in (
        ("integrated_main", "main_fragment"),
        ("integrated_public_answers", "public_answers_fragment"),
    ):
        if raw[integrated].count(raw[fragment]) != 1:
            raise RuntimeError(f"canonical B017 overlay is not unique and exact: {integrated}")
    if b"\\section{Poisson distribution}" not in raw["integrated_main"]:
        raise RuntimeError("B017 canonical next Poisson cursor is absent")
    return bound, raw


def load_terminal_contract() -> tuple[dict[str, Any], dict[str, Any], dict[str, bytes]]:
    if not TERMINAL_CONTRACT.is_file():
        raise TerminalInputsUnresolved(
            "R011-B017 terminal contract is absent; deterministic build and visual closure remain pending"
        )
    contract_raw = TERMINAL_CONTRACT.read_bytes()
    contract = parse_json(contract_raw, "B017 terminal contract")
    if (
        contract.get("$schema") != "interlanguage.r011-b017-terminal-inputs/v1"
        or contract.get("boundary_id") != BOUNDARY_ID
        or contract.get("status") != "READY_TERMINAL_INPUTS"
        or contract.get("closure") != EXPECTED_TERMINAL_CLOSURE
    ):
        raise TerminalInputsUnresolved("B017 terminal contract closure changed or is not READY")
    inputs = contract.get("inputs")
    gates = contract.get("gates")
    if not isinstance(inputs, dict) or set(inputs) != set(TERMINAL_ROLE_PATHS):
        raise TerminalInputsUnresolved("B017 terminal role set is incomplete or expanded")
    if not isinstance(gates, dict) or set(gates) != REQUIRED_TERMINAL_GATES:
        raise TerminalInputsUnresolved("B017 terminal gate set is incomplete or expanded")
    if set(gates.values()) != {"passed"}:
        raise TerminalInputsUnresolved("one or more deterministic B017 terminal gates did not pass")
    raw: dict[str, bytes] = {}
    for role, expected_path in TERMINAL_ROLE_PATHS.items():
        item = inputs.get(role)
        if not isinstance(item, dict) or item.get("path") != expected_path:
            raise TerminalInputsUnresolved(f"B017 terminal path changed for {role}")
        expected = {"bytes": item.get("bytes"), "sha256": item.get("sha256")}
        if not isinstance(expected["bytes"], int) or not re.fullmatch(
            r"[0-9a-f]{64}", str(expected["sha256"])
        ):
            raise TerminalInputsUnresolved(f"B017 terminal identity unresolved for {role}")
        raw[role] = require(LANE / expected_path, expected)
    contract_identity = {
        "path": TERMINAL_CONTRACT.relative_to(LANE).as_posix(),
        **identity_raw(contract_raw),
    }
    return contract, contract_identity, raw


def line_span_meta(raw: bytes, start_line: int, end_line: int) -> dict[str, Any]:
    lines = raw.splitlines(keepends=True)
    if start_line < 1 or end_line < start_line or end_line > len(lines):
        raise RuntimeError(f"invalid inclusive line span {start_line}-{end_line}")
    start = sum(len(line) for line in lines[: start_line - 1])
    end = sum(len(line) for line in lines[:end_line])
    return span_meta(raw, start, end)


def span_meta(raw: bytes, start: int, end: int) -> dict[str, Any]:
    if start < 0 or end <= start or end > len(raw):
        raise RuntimeError(f"invalid byte span {start}:{end} of {len(raw)}")
    chunk = raw[start:end]
    return {
        "byte_start": start,
        "byte_end_exclusive": end,
        "bytes": len(chunk),
        "line_start": raw[:start].count(b"\n") + 1,
        "line_end": raw[: max(start, end - 1)].count(b"\n") + 1,
        "sha256": sha256_bytes(chunk),
    }


def schema_span(meta: dict[str, Any]) -> dict[str, int]:
    return {
        key: int(meta[key])
        for key in ("line_start", "line_end", "byte_start", "byte_end_exclusive")
    }


def rebase_span(local: dict[str, Any], full: bytes, offset: int) -> dict[str, Any]:
    return span_meta(
        full,
        offset + int(local["byte_start"]),
        offset + int(local["byte_end_exclusive"]),
    )


def unique_offset(haystack: bytes, needle: bytes, role: str) -> int:
    if not needle or haystack.count(needle) != 1:
        raise RuntimeError(f"B017 {role} is not unique and exact")
    return haystack.index(needle)


def environment_spans(raw: bytes, environment: bytes, kind: str) -> list[dict[str, Any]]:
    begin = b"\\begin{" + environment + b"}"
    end_marker = b"\\end{" + environment + b"}"
    result: list[dict[str, Any]] = []
    cursor = 0
    while True:
        start = raw.find(begin, cursor)
        if start < 0:
            break
        end_start = raw.find(end_marker, start + len(begin))
        if end_start < 0:
            raise RuntimeError(f"unclosed B017 environment {environment.decode()}")
        end = end_start + len(end_marker)
        result.append({"kind": kind, "span": span_meta(raw, start, end)})
        cursor = end
    return result


def balanced_command_spans(raw: bytes, command: bytes, kind: str) -> list[dict[str, Any]]:
    prefix = b"\\" + command + b"{"
    result: list[dict[str, Any]] = []
    cursor = 0
    while True:
        start = raw.find(prefix, cursor)
        if start < 0:
            break
        depth = 1
        pos = start + len(prefix)
        while pos < len(raw) and depth:
            byte = raw[pos]
            escaped = pos > 0 and raw[pos - 1] == 92
            if byte == 123 and not escaped:
                depth += 1
            elif byte == 125 and not escaped:
                depth -= 1
            pos += 1
        if depth:
            raise RuntimeError(f"unclosed B017 command {command.decode()}")
        result.append({"kind": kind, "span": span_meta(raw, start, pos)})
        cursor = pos
    return result


def structural_spans(raw: bytes) -> list[dict[str, Any]]:
    blocks = (
        environment_spans(raw, b"examplewrap", "worked_example")
        + environment_spans(raw, b"exercisewrap", "guided_exercise")
        + balanced_command_spans(raw, b"footnotetext", "guided_inline_answer")
    )
    expected = {"worked_example": 3, "guided_exercise": 5, "guided_inline_answer": 5}
    for kind, count in expected.items():
        if sum(row["kind"] == kind for row in blocks) != count:
            raise RuntimeError(f"B017 {kind} topology changed")
    blocks.sort(key=lambda row: int(row["span"]["byte_start"]))
    previous = 0
    result: list[dict[str, Any]] = []
    for row in blocks:
        start = int(row["span"]["byte_start"])
        if start < previous:
            raise RuntimeError("overlapping B017 structural spans")
        if raw[previous:start].strip():
            result.append({"kind": "section_prose", "span": span_meta(raw, previous, start)})
        result.append(row)
        previous = int(row["span"]["byte_end_exclusive"])
    if raw[previous:].strip():
        result.append({"kind": "section_prose", "span": span_meta(raw, previous, len(raw))})
    if sum(row["kind"] == "section_prose" for row in result) != 6:
        raise RuntimeError("B017 section-prose segmentation changed")
    return result


def marker_spans(raw: bytes, numbers: list[int]) -> dict[int, dict[str, Any]]:
    starts: list[tuple[int, int]] = []
    for number in numbers:
        match = re.search(rb"(?m)^% " + str(number).encode() + rb"\r?$", raw)
        if match is None:
            raise RuntimeError(f"missing B017 marker % {number}")
        starts.append((number, match.start()))
    if [number for number, _ in sorted(starts, key=lambda item: item[1])] != numbers:
        raise RuntimeError("B017 marker order changed")
    starts.sort(key=lambda item: item[1])
    result: dict[int, dict[str, Any]] = {}
    for index, (number, start) in enumerate(starts):
        end = starts[index + 1][1] if index + 1 < len(starts) else len(raw)
        result[number] = span_meta(raw, start, end)
    return result


def backend_record(record_type: str, stable_key: str, **fields: Any) -> dict[str, Any]:
    row = {
        "$schema": "schemas/backend-record-v0.1.0.schema.json",
        "schema_version": SCHEMA_VERSION,
        "record_type": record_type,
        "id": stable_id(stable_key),
        "stable_key": stable_key,
        "status": "active",
        "recorded_at": RECORDED_AT,
        "workflow_id": WORKFLOW_ID,
        "supersedes_id": None,
    }
    row.update(fields)
    return normalize(row)


def common_fields(
    resource_id: str, edition_id: str, rights_ids: list[str], **overrides: Any
) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "boundary_id": BOUNDARY_ID,
        "resource_id": resource_id,
        "edition_id": edition_id,
        "source_local_ids": [BOUNDARY_ID],
        "parent_id": None,
        "order": None,
        "source_path": None,
        "source_span": None,
        "source_sha256": None,
        "locale": "zxx",
        "translation_state": "structurally_verified",
        "rights_component_ids": rights_ids,
    }
    fields.update(overrides)
    return fields


def record_index(records: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for rows in records.values():
        for row in rows:
            key = str(row["stable_key"])
            if key in result or str(row["id"]) != stable_id(key):
                raise RuntimeError(f"invalid or duplicate backend stable identity: {key}")
            result[key] = row
    return result


def add_record(
    records: dict[str, list[dict[str, Any]]],
    indexes: dict[str, dict[str, Any]],
    table: str,
    row: dict[str, Any],
) -> dict[str, Any]:
    key = str(row["stable_key"])
    if key in indexes:
        raise RuntimeError(f"B017 stable key already exists: {key}")
    if any(str(existing["id"]) == str(row["id"]) for existing in indexes.values()):
        raise RuntimeError(f"B017 UUID already exists: {row['id']}")
    records[table].append(row)
    indexes[key] = row
    return row


def unit_record(
    key: str,
    title: str,
    unit_type: str,
    order: int,
    parent_id: str,
    resource_id: str,
    edition_id: str,
    rights_ids: list[str],
    source_local_ids: list[str],
    source_path: str | None,
    source_meta: dict[str, Any] | None,
    target_path: str | None,
    target_meta: dict[str, Any] | None,
    **extra: Any,
) -> dict[str, Any]:
    row = backend_record(
        "unit",
        key,
        **common_fields(
            resource_id,
            edition_id,
            rights_ids,
            source_local_ids=source_local_ids,
            parent_id=parent_id,
            order=order,
            source_path=source_path,
            source_span=None if source_meta is None else schema_span(source_meta),
            source_sha256=None if source_meta is None else source_meta["sha256"],
            locale="en",
            translation_state="visually_checked" if target_meta is not None else "queued",
        ),
        title=title,
        unit_type=unit_type,
        prerequisite_ids=[],
        answer_availability=None,
        authoring_mode=None,
        gap_reason=None,
        source_solution_used=None,
        target_identity_status="terminal_contract_bound" if target_meta is not None else None,
        target_path=target_path,
        target_span=target_meta,
        target_sha256=None if target_meta is None else target_meta["sha256"],
    )
    row.update(extra)
    return normalize(row)


def segment_and_localization(
    records: dict[str, list[dict[str, Any]]],
    indexes: dict[str, dict[str, Any]],
    segment_key: str,
    localization_key: str,
    unit_id: str,
    order: int,
    segment_kind: str,
    resource_id: str,
    edition_id: str,
    source_rights: list[str],
    target_rights: list[str],
    source_local_ids: list[str],
    source_path: str,
    source_raw: bytes,
    source_meta: dict[str, Any],
    target_path: str,
    target_raw: bytes,
    target_meta: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    source_text = source_raw[
        int(source_meta["byte_start"]): int(source_meta["byte_end_exclusive"])
    ].decode("utf-8")
    target_text = target_raw[
        int(target_meta["byte_start"]): int(target_meta["byte_end_exclusive"])
    ].decode("utf-8")
    segment = backend_record(
        "segment",
        segment_key,
        **common_fields(
            resource_id,
            edition_id,
            source_rights,
            source_local_ids=source_local_ids,
            parent_id=unit_id,
            order=order,
            source_path=source_path,
            source_span=schema_span(source_meta),
            source_sha256=source_meta["sha256"],
            locale="en",
            translation_state="source_frozen",
        ),
        unit_id=unit_id,
        segment_kind=segment_kind,
        source_locale="en",
        source_text=source_text,
        protected_tokens=[],
        target_locales=["id-ID"],
    )
    add_record(records, indexes, "segments", segment)
    localization = backend_record(
        "localization",
        localization_key,
        **common_fields(
            resource_id,
            edition_id,
            target_rights,
            source_local_ids=source_local_ids,
            parent_id=segment["id"],
            order=order,
            source_path=source_path,
            source_span=schema_span(source_meta),
            source_sha256=source_meta["sha256"],
            locale="id-ID",
            translation_state="visually_checked",
        ),
        unit_id=unit_id,
        source_segment_id=segment["id"],
        source_locale="en",
        target_locale="id-ID",
        target_path=target_path,
        target_span=target_meta,
        target_sha256=target_meta["sha256"],
        target_text=target_text,
        target_identity_status="terminal_contract_bound",
        protected_tokens=[],
        source_protected_tokens=[],
        target_protected_tokens=[],
        protected_token_delta={
            "authorized": True,
            "reason": "Exact B017 topology, formula, answer, build, and visual receipts.",
        },
        terminology_bindings=[row["code"] for row in TERM_DEFINITIONS],
        candidate_validation_receipt="scratch/b017-candidate/R011-B017_CANDIDATE_QA.json",
        translation_provenance=PROVENANCE,
    )
    add_record(records, indexes, "localizations", localization)
    return segment, localization


def load_base_records() -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    manifest_raw = require(BASE_MANIFEST, BASE_MANIFEST_IDENTITY)
    manifest = parse_json(manifest_raw, "B016 base manifest")
    entries = {str(entry["path"]): entry for entry in manifest["files"]}
    records: dict[str, list[dict[str, Any]]] = {}
    for name, relative in RECORD_PATHS.items():
        entry = entries.get(relative)
        if entry is None:
            raise RuntimeError(f"B016 base manifest lacks typed record path {relative}")
        raw = require(BASE_EXPORTS / relative, entry)
        records[name] = load_jsonl(raw)
        if entry.get("records") != len(records[name]):
            raise RuntimeError(f"B016 base record count changed for {relative}")
    if sum(len(rows) for rows in records.values()) != BASE_RECORD_COUNT:
        raise RuntimeError("B016 base typed record count changed")
    if {name: len(rows) for name, rows in sorted(records.items())} != BASE_RECORD_COUNTS:
        raise RuntimeError("B016 base typed record cardinalities changed")
    return records, manifest


def load_context() -> dict[str, Any]:
    ready, ready_raw = bind_ready_inputs()
    contract, contract_identity, terminal_raw = load_terminal_contract()

    main_source_full = ready_raw["main_authority"]
    eoce_source_full = ready_raw["eoce_authority"]
    answers_source_full = ready_raw["public_answers_authority"]
    main_source_meta = line_span_meta(main_source_full, 1927, 2110)
    answers_source_meta = line_span_meta(answers_source_full, 750, 761)
    main_source = main_source_full[
        main_source_meta["byte_start"]: main_source_meta["byte_end_exclusive"]
    ]
    eoce_source = eoce_source_full
    answers_source = answers_source_full[
        answers_source_meta["byte_start"]: answers_source_meta["byte_end_exclusive"]
    ]
    if (
        len(main_source.splitlines()) != 184
        or len(eoce_source.splitlines()) != 70
        or len(answers_source.splitlines()) != 12
    ):
        raise RuntimeError("B017 frozen authority span line counts changed")

    main_target_full = terminal_raw["assembled_main"]
    eoce_target_full = terminal_raw["assembled_eoce"]
    answers_target_full = terminal_raw["assembled_public_answers"]
    main_target = ready_raw["main_fragment"]
    eoce_target = ready_raw["eoce_fragment"]
    answers_target = ready_raw["public_answers_fragment"]
    offsets = {
        "main_source": int(main_source_meta["byte_start"]),
        "eoce_source": 0,
        "answers_source": int(answers_source_meta["byte_start"]),
        "main_target": unique_offset(main_target_full, main_target, "assembled main fragment"),
        "eoce_target": unique_offset(eoce_target_full, eoce_target, "assembled EoCE fragment"),
        "answers_target": unique_offset(
            answers_target_full, answers_target, "assembled public-answer fragment"
        ),
    }
    source_struct = structural_spans(main_source)
    target_struct = structural_spans(main_target)
    if [row["kind"] for row in source_struct] != [row["kind"] for row in target_struct]:
        raise RuntimeError("B017 source/target structural topology differs")

    source_eoce = marker_spans(eoce_source, sorted(EOCE))
    target_eoce = marker_spans(eoce_target, sorted(EOCE))
    source_answers = marker_spans(answers_source, list(PUBLIC_ANSWERS))
    target_answers = marker_spans(answers_target, list(PUBLIC_ANSWERS))
    source_figure = environment_spans(main_source, b"figure", "inline_tex_figure")
    target_figure = environment_spans(main_target, b"figure", "inline_tex_figure")
    if len(source_figure) != 1 or len(target_figure) != 1:
        raise RuntimeError("B017 inline TeX figure topology changed")
    return {
        "ready": ready,
        "ready_raw": ready_raw,
        "contract": contract,
        "contract_identity": contract_identity,
        "terminal_raw": terminal_raw,
        "main_source_full": main_source_full,
        "eoce_source_full": eoce_source_full,
        "answers_source_full": answers_source_full,
        "main_source": main_source,
        "eoce_source": eoce_source,
        "answers_source": answers_source,
        "main_target_full": main_target_full,
        "eoce_target_full": eoce_target_full,
        "answers_target_full": answers_target_full,
        "main_target": main_target,
        "eoce_target": eoce_target,
        "answers_target": answers_target,
        "offsets": offsets,
        "source_struct": source_struct,
        "target_struct": target_struct,
        "source_eoce": source_eoce,
        "target_eoce": target_eoce,
        "source_answers": source_answers,
        "target_answers": target_answers,
        "source_figure": source_figure[0]["span"],
        "target_figure": target_figure[0]["span"],
    }


def build_views(
    records: dict[str, list[dict[str, Any]]]
) -> tuple[dict[str, bytes], dict[str, int]]:
    columns_doc = parse_json(
        (BASE_EXPORTS / "schemas/backend-view-columns-v0.1.0.json").read_bytes(),
        "view-column schema",
    )
    columns = columns_doc["views"]
    by_key = record_index(records)
    resource = by_key["r011/resource/openintro-statistics"]
    edition = by_key["r011/edition/fee25091"]
    upstream_right = by_key["r011/rights/upstream-cc-by-sa-3.0"]
    rows: dict[str, list[dict[str, Any]]] = {}
    rows["views/resource_editions.csv"] = [{
        "resource_id": resource["id"],
        "resource_code": resource["resource_code"],
        "work_title": resource["work_title"],
        "edition_id": edition["id"],
        "repository": edition["repository"],
        "branch_observed": edition["branch_observed"],
        "commit": edition["commit"],
        "tree": edition["tree"],
        "license_expression": upstream_right["license_expression"],
        "source_format": edition["source_format"],
        "build_entrypoint": edition["build_entrypoint"],
    }]
    rows["views/unit_hierarchy.csv"] = [{
        "id": row["id"],
        "parent_id": row.get("parent_id"),
        "order": row.get("order"),
        "unit_type": row.get("unit_type"),
        "source_local_ids": row.get("source_local_ids", []),
        "source_path": row.get("source_path"),
        "line_start": (row.get("source_span") or {}).get("line_start"),
        "line_end": (row.get("source_span") or {}).get("line_end"),
        "source_sha256": row.get("source_sha256"),
        "translation_state": row.get("translation_state"),
        "rights_component_ids": row.get("rights_component_ids", []),
    } for row in records["units"]]
    rows["views/relations.csv"] = [
        {key: row.get(key) for key in columns["views/relations.csv"]}
        for row in records["relations"]
    ]
    localizations: dict[str, dict[str, Any]] = {}
    for row in records["localizations"]:
        key = str(row["source_segment_id"])
        if key in localizations:
            raise RuntimeError(f"multiple localizations for segment {key}")
        localizations[key] = row
    rows["views/segments_locale.csv"] = []
    for segment in records["segments"]:
        localization = localizations.get(str(segment["id"]))
        target_span = {} if localization is None else (localization.get("target_span") or {})
        rows["views/segments_locale.csv"].append({
            "segment_id": segment["id"],
            "unit_id": segment["unit_id"],
            "order": segment.get("order"),
            "segment_kind": segment.get("segment_kind"),
            "source_locale": segment.get("source_locale"),
            "source_path": segment.get("source_path"),
            "line_start": (segment.get("source_span") or {}).get("line_start"),
            "line_end": (segment.get("source_span") or {}).get("line_end"),
            "source_sha256": segment.get("source_sha256"),
            "target_locale": None if localization is None else localization.get("target_locale"),
            "target_path": None if localization is None else localization.get("target_path"),
            "target_line_start": target_span.get("line_start"),
            "target_line_end": target_span.get("line_end"),
            "target_sha256": None if localization is None else localization.get("target_sha256"),
            "translation_state": segment.get("translation_state") if localization is None else localization.get("translation_state"),
            "target_text": None if localization is None else localization.get("target_text"),
            "rights_component_ids": segment.get("rights_component_ids", []) if localization is None else localization.get("rights_component_ids", []),
        })
    rows["views/terminology.csv"] = [{
        "id": row["id"],
        "concept_id": row["concept_id"],
        "source_term": row["source_term"],
        "target_term": row["target_term"],
        "locale": row["locale"],
        "variants": row.get("variants", []),
        "rejected_forms": row.get("rejected_forms", []),
        "scope": row.get("scope"),
        "register": row.get("register"),
        "translation_state": row.get("translation_state"),
    } for row in records["terms"]]
    solutions = {
        str(row["parent_id"]): row for row in records["units"]
        if row.get("unit_type") in {"solution", "guided_solution"} and row.get("parent_id")
    }
    gaps = {
        str(row["parent_id"]): row for row in records["units"]
        if row.get("unit_type") == "companion_gap" and row.get("parent_id")
    }
    rows["views/exercises_answers.csv"] = []
    for exercise in records["units"]:
        if exercise.get("unit_type") not in {"exercise", "guided_exercise"}:
            continue
        solution = solutions.get(str(exercise["id"]))
        gap = gaps.get(str(exercise["id"]))
        rows["views/exercises_answers.csv"].append({
            "exercise_id": exercise["id"],
            "source_local_ids": exercise.get("source_local_ids", []),
            "answer_availability": exercise.get("answer_availability"),
            "answer_id": None if solution is None else solution["id"],
            "o001_gap_id": None if gap is None else gap["id"],
            "source_path": exercise.get("source_path"),
            "translation_state": exercise.get("translation_state"),
            "rights_component_ids": exercise.get("rights_component_ids", []),
        })
    rows["views/rights_components.csv"] = [
        {key: row.get(key) for key in columns["views/rights_components.csv"]}
        for row in records["rights"]
    ]
    rows["views/corrections.csv"] = [
        {key: row.get(key) for key in columns["views/corrections.csv"]}
        for row in records["corrections"]
    ]
    rows["views/qa_build_events.csv"] = [
        {key: row.get(key) for key in columns["views/qa_build_events.csv"]}
        for row in records["qa_events"]
    ]
    rows["views/artifacts.csv"] = [
        {key: row.get(key) for key in columns["views/artifacts.csv"]}
        for row in records["artifacts"]
    ]
    payloads: dict[str, bytes] = {}
    counts: dict[str, int] = {}
    for path in REQUIRED_VIEWS:
        ordered = sorted(
            rows[path], key=lambda row: tuple(str(row.get(key) or "") for key in columns[path])
        )
        payloads[path] = csv_bytes(columns[path], ordered)
        counts[path] = len(ordered)
    return payloads, counts


def build_identity_map(records: dict[str, list[dict[str, Any]]]) -> bytes:
    rows = [{
        "id": row["id"],
        "record_type": row["record_type"],
        "source_local_ids": row.get("source_local_ids", []),
        "stable_key": row["stable_key"],
    } for table_rows in records.values() for row in table_rows]
    return "".join(
        canonical_json_text(row) + "\n" for row in sorted(rows, key=lambda item: item["id"])
    ).encode("utf-8")


def compile_records(
    base_records: dict[str, list[dict[str, Any]]], context: dict[str, Any]
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, bytes], dict[str, int]]:
    records = deepcopy(base_records)
    indexes = record_index(records)
    resource = indexes["r011/resource/openintro-statistics"]
    edition = indexes["r011/edition/fee25091"]
    chapter = indexes["r011/unit/source-label/ch_distributions"]
    predecessor = indexes["r011/unit/source-label/binomialModel"]
    upstream_right = str(indexes["r011/rights/upstream-cc-by-sa-3.0"]["id"])
    o001_right = str(indexes["r011/rights/o001-original-companion-planned"]["id"])
    resource_id = str(resource["id"])
    edition_id = str(edition["id"])

    derivative_right = backend_record(
        "rights",
        "r011/rights/b017-localized-negative-binomial-section",
        **common_fields(
            resource_id,
            edition_id,
            [],
            parent_id=resource_id,
            order=len(records["rights"]) + 1,
            source_path=context["ready"]["boundary_blueprint"]["path"],
            source_sha256=context["ready"]["boundary_blueprint"]["sha256"],
            locale="zxx",
            translation_state="visually_checked",
        ),
        component_scope=(
            "B017 Indonesian Section 4.4, its three worked examples, five guided exercises "
            "and inline public answers, EoCE 27--30, public answers 27/29, and the inline "
            "TeX success/failure table; no external assets, data, or code."
        ),
        license_expression="CC-BY-SA-3.0",
        verification_status="verified by exact authority, candidate, build, rights, and visual receipts",
        attribution="OpenIntro Statistics source authors; Indonesian derivative changes identified by R011-B017.",
        change_notice="Reader-facing prose was translated to id-ID; stable mathematics and source identifiers were preserved.",
        non_endorsement="No author, institution, publisher, brand owner, or tool-provider endorsement implied.",
        publication_effect="B017 isolated backend stage only; guarded admission and publication are separate transactions.",
    )
    add_record(records, indexes, "rights", derivative_right)
    text_rights = [upstream_right, str(derivative_right["id"])]

    source_paths = {
        "main": "ch_distributions/TeX/ch_distributions.tex",
        "eoce": "ch_distributions/TeX/negative_binomial_distribution.tex",
        "answers": "extraTeX/eoceSolutions/eoceSolutions.tex",
    }
    target_paths = {
        "main": context["contract"]["inputs"]["assembled_main"]["path"],
        "eoce": context["contract"]["inputs"]["assembled_eoce"]["path"],
        "answers": context["contract"]["inputs"]["assembled_public_answers"]["path"],
    }

    def smeta(kind: str, local: dict[str, Any]) -> dict[str, Any]:
        full = context[f"{kind}_source_full"]
        return rebase_span(local, full, context["offsets"][f"{kind}_source"])

    def tmeta(kind: str, local: dict[str, Any]) -> dict[str, Any]:
        full = context[f"{kind}_target_full"]
        return rebase_span(local, full, context["offsets"][f"{kind}_target"])

    whole_source = smeta("main", span_meta(context["main_source"], 0, len(context["main_source"])))
    whole_target = tmeta("main", span_meta(context["main_target"], 0, len(context["main_target"])))
    section = unit_record(
        "r011/unit/source-label/negativeBinomial",
        "Negative binomial distribution",
        "section",
        4,
        str(chapter["id"]),
        resource_id,
        edition_id,
        text_rights,
        [BOUNDARY_ID, "negativeBinomial"],
        source_paths["main"],
        whole_source,
        target_paths["main"],
        whole_target,
        prerequisite_ids=[str(predecessor["id"])],
    )
    add_record(records, indexes, "units", section)

    source_by_kind = {
        kind: [row for row in context["source_struct"] if row["kind"] == kind]
        for kind in ("worked_example", "guided_exercise", "guided_inline_answer")
    }
    target_by_kind = {
        kind: [row for row in context["target_struct"] if row["kind"] == kind]
        for kind in ("worked_example", "guided_exercise", "guided_inline_answer")
    }
    worked_keys = [
        "r011/unit/b017/worked-example-01",
        "r011/unit/source-label/eachSeqOfSixTriesToGetFourSuccesses",
        "r011/unit/b017/worked-example-03",
    ]
    worked_units: list[dict[str, Any]] = []
    for number, key in enumerate(worked_keys, 1):
        unit = unit_record(
            key,
            f"Worked example 4.4.{number}",
            "worked_example",
            200 + number,
            str(section["id"]),
            resource_id,
            edition_id,
            text_rights,
            [BOUNDARY_ID, f"worked-example-{number:02d}"],
            source_paths["main"],
            smeta("main", source_by_kind["worked_example"][number - 1]["span"]),
            target_paths["main"],
            tmeta("main", target_by_kind["worked_example"][number - 1]["span"]),
        )
        add_record(records, indexes, "units", unit)
        worked_units.append(unit)

    guided_units: list[dict[str, Any]] = []
    guided_answer_units: list[dict[str, Any]] = []
    for number in range(1, 6):
        exercise_key = (
            "r011/unit/source-label/probOfEachSeqOfSixTriesToGetFourSuccesses"
            if number == 2
            else f"r011/unit/guided-exercise/ch04-sec4.4-{number:02d}"
        )
        exercise = unit_record(
            exercise_key,
            f"Guided exercise 4.4.{number}",
            "guided_exercise",
            300 + number,
            str(section["id"]),
            resource_id,
            edition_id,
            text_rights,
            [BOUNDARY_ID, f"guided-exercise-{number:02d}"],
            source_paths["main"],
            smeta("main", source_by_kind["guided_exercise"][number - 1]["span"]),
            target_paths["main"],
            tmeta("main", target_by_kind["guided_exercise"][number - 1]["span"]),
            answer_availability="inline_public",
        )
        add_record(records, indexes, "units", exercise)
        guided_units.append(exercise)
        answer = unit_record(
            f"r011/unit/guided-solution/ch04-sec4.4-{number:02d}",
            f"Inline answer to guided exercise 4.4.{number}",
            "guided_solution",
            1,
            str(exercise["id"]),
            resource_id,
            edition_id,
            text_rights,
            [BOUNDARY_ID, f"guided-answer-{number:02d}"],
            source_paths["main"],
            smeta("main", source_by_kind["guided_inline_answer"][number - 1]["span"]),
            target_paths["main"],
            tmeta("main", target_by_kind["guided_inline_answer"][number - 1]["span"]),
            answer_availability="public_inline",
        )
        add_record(records, indexes, "units", answer)
        guided_answer_units.append(answer)

    eoce_units: dict[int, dict[str, Any]] = {}
    answer_units: dict[int, dict[str, Any]] = {}
    gap_units: dict[int, dict[str, Any]] = {}
    for number in sorted(EOCE):
        exercise = unit_record(
            f"r011/unit/exercise/4.{number}/{EOCE[number]}",
            f"Exercise 4.{number}",
            "exercise",
            3000 + number,
            str(section["id"]),
            resource_id,
            edition_id,
            text_rights,
            [BOUNDARY_ID, f"4.{number}", EOCE[number]],
            source_paths["eoce"],
            smeta("eoce", context["source_eoce"][number]),
            target_paths["eoce"],
            tmeta("eoce", context["target_eoce"][number]),
            answer_availability="public_appendix" if number in PUBLIC_ANSWERS else "restricted_not_accessed",
        )
        add_record(records, indexes, "units", exercise)
        eoce_units[number] = exercise
        if number in PUBLIC_ANSWERS:
            answer = unit_record(
                f"r011/unit/solution/4.{number}",
                f"Public solution to exercise 4.{number}",
                "solution",
                1,
                str(exercise["id"]),
                resource_id,
                edition_id,
                text_rights,
                [BOUNDARY_ID, f"4.{number}"],
                source_paths["answers"],
                smeta("answers", context["source_answers"][number]),
                target_paths["answers"],
                tmeta("answers", context["target_answers"][number]),
                answer_availability="public_upstream",
            )
            add_record(records, indexes, "units", answer)
            answer_units[number] = answer
        else:
            gap = unit_record(
                f"r011/unit/o001-gap/4.{number}",
                f"O001 mastery-companion answer gap for exercise 4.{number}",
                "companion_gap",
                1,
                str(exercise["id"]),
                resource_id,
                edition_id,
                [o001_right],
                [BOUNDARY_ID, f"4.{number}"],
                None,
                None,
                None,
                None,
                answer_availability="restricted_not_accessed",
                authoring_mode="independent_original_required",
                gap_reason="no_public_answer_upstream",
                source_solution_used=False,
                target_identity_status="explicit_o001_gap",
            )
            add_record(records, indexes, "units", gap)
            gap_units[number] = gap

    new_concepts: list[dict[str, Any]] = []
    term_rows: list[dict[str, Any]] = []
    for order, definition in enumerate(TERM_DEFINITIONS, 1):
        concept_key = str(definition["concept_key"])
        if concept_key not in indexes:
            concept = backend_record(
                "concept",
                concept_key,
                **common_fields(
                    resource_id,
                    edition_id,
                    [upstream_right],
                    source_local_ids=[BOUNDARY_ID, str(definition["code"])],
                    order=order,
                    source_path=source_paths["main"],
                    source_span=schema_span(whole_source),
                    source_sha256=whole_source["sha256"],
                    locale="zxx",
                    translation_state="source_frozen",
                ),
                semantic_code=definition["code"],
                preferred_source_term=definition["source"],
                definition=definition["definition"],
            )
            add_record(records, indexes, "concepts", concept)
            new_concepts.append(concept)
        concept = indexes[concept_key]
        term = backend_record(
            "term",
            f"r011/term/id-ID/b017/TM{order:03d}",
            **common_fields(
                resource_id,
                edition_id,
                text_rights,
                source_local_ids=[BOUNDARY_ID, str(definition["code"])],
                parent_id=str(concept["id"]),
                order=order,
                source_path=context["ready"]["terminology_qa_json"]["path"],
                source_sha256=context["ready"]["terminology_qa_json"]["sha256"],
                locale="id-ID",
                translation_state="language_reviewed",
            ),
            concept_id=str(concept["id"]),
            source_term=definition["source"],
            target_term=definition["target"],
            variants=definition["variants"],
            rejected_forms=[],
            scope="statistics / Chapter 4 Section 4.4",
            register="academic",
            evidence=(
                "Independent B017 Indonesian field-usage QA, supported by a peer-reviewed "
                "MATHunesa PDF fallback and an official Universitas Jember module, plus "
                "admitted B015/B016 terminology controls."
            ),
            decision=f"Use {definition['target']} consistently in reader-facing id-ID prose.",
            decision_reason=(
                "All 11 checked terms were supported or uncontested; no glossary or "
                "canonical-text propagation was justified."
            ),
            glossary_lock_status="bound_to_terminal_b017_candidate",
            field_source_metadata={
                "qa_status": "PASS_NO_TERMINOLOGY_PROPAGATION_REQUIRED",
                "checked_term_count": 11,
                "canonical_changes_recommended": 0,
                "glossary_changes_recommended": 0,
                "external_witness_bytes_bundled": False,
                "model": PROVENANCE,
            },
        )
        add_record(records, indexes, "terms", term)
        term_rows.append(term)

    asset = backend_record(
        "asset",
        "r011/asset/b017/inline-tex/successFailureOrdersForBriansFieldGoals",
        **common_fields(
            resource_id,
            edition_id,
            text_rights,
            source_local_ids=[BOUNDARY_ID, "successFailureOrdersForBriansFieldGoals"],
            parent_id=str(section["id"]),
            order=1,
            source_path=source_paths["main"],
            source_span=schema_span(smeta("main", context["source_figure"])),
            source_sha256=smeta("main", context["source_figure"])["sha256"],
            locale="zxx",
            translation_state="visually_checked",
        ),
        asset_kind="inline_tex_table_figure",
        path=source_paths["main"],
        bytes=context["source_figure"]["bytes"],
        sha256=context["source_figure"]["sha256"],
        media_type="application/x-tex-inline",
        dependencies=[],
        target_path=target_paths["main"],
        target_span=tmeta("main", context["target_figure"]),
        target_sha256=tmeta("main", context["target_figure"])["sha256"],
        external_asset=False,
        data_dependency=False,
        code_dependency=False,
        reader_visible_strings_localized=True,
    )
    add_record(records, indexes, "assets", asset)

    correction_doc = parse_json(
        context["ready_raw"]["correction_candidates"], "B017 correction candidates"
    )
    correction_rows: list[dict[str, Any]] = []
    for order, item in enumerate(correction_doc["candidates"], 1):
        code = str(item["id"])
        affected = section
        if code == "B017-C006":
            affected = eoce_units[29]
        elif code == "B017-C007":
            affected = answer_units[29]
        source_path = str(item["path"]).split(
            "openintro-statistics-fee25091fb24e89c36296fd67c48c1fcf7a93b6e/", 1
        )[-1]
        full_role = {
            "ch_distributions/TeX/ch_distributions.tex": "main_authority",
            "ch_distributions/TeX/negative_binomial_distribution.tex": "eoce_authority",
            "extraTeX/eoceSolutions/eoceSolutions.tex": "public_answers_authority",
        }[source_path]
        correction = backend_record(
            "correction",
            f"r011/correction/b017/{code}",
            **common_fields(
                resource_id,
                edition_id,
                text_rights,
                source_local_ids=[BOUNDARY_ID, code],
                parent_id=str(affected["id"]),
                order=order,
                source_path=source_path,
                source_sha256=context["ready"][full_role]["sha256"],
                locale="id-ID",
                translation_state="language_reviewed",
            ),
            affected_id=str(affected["id"]),
            category=str(item["category"]),
            summary=f"{code}: high-confidence upstream copyedit candidate",
            disposition="recorded_not_applied_to_authority",
            confidence="high",
            source_claim=item["source_fragment"],
            proposed_correction=item["suggested_correction"],
            meaning_change=False,
            evidence={"path": source_path, "line": item.get("line"), "lines": item.get("lines")},
            upstream_report_disposition="defer_to_single_deduplicated_post-corpus_report_only",
        )
        add_record(records, indexes, "corrections", correction)
        correction_rows.append(correction)

    segment_pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    kind_units = {
        "worked_example": worked_units,
        "guided_exercise": guided_units,
        "guided_inline_answer": guided_answer_units,
    }
    cursors = {key: 0 for key in kind_units}
    for order, (source_row, target_row) in enumerate(
        zip(context["source_struct"], context["target_struct"]), 1
    ):
        kind = source_row["kind"]
        if kind == "section_prose":
            unit = section
        else:
            unit = kind_units[kind][cursors[kind]]
            cursors[kind] += 1
        segment_pairs.append(segment_and_localization(
            records,
            indexes,
            f"r011/segment/b017/main-{order:03d}",
            f"r011/localization/id-ID/b017/main-{order:03d}",
            str(unit["id"]),
            order,
            kind,
            resource_id,
            edition_id,
            [upstream_right],
            text_rights,
            [BOUNDARY_ID],
            source_paths["main"],
            context["main_source_full"],
            smeta("main", source_row["span"]),
            target_paths["main"],
            context["main_target_full"],
            tmeta("main", target_row["span"]),
        ))
    for number in sorted(EOCE):
        segment_pairs.append(segment_and_localization(
            records,
            indexes,
            f"r011/segment/b017/eoce-4-{number}",
            f"r011/localization/id-ID/b017/eoce-4-{number}",
            str(eoce_units[number]["id"]),
            100 + number,
            "exercise",
            resource_id,
            edition_id,
            [upstream_right],
            text_rights,
            [BOUNDARY_ID, f"4.{number}"],
            source_paths["eoce"],
            context["eoce_source_full"],
            smeta("eoce", context["source_eoce"][number]),
            target_paths["eoce"],
            context["eoce_target_full"],
            tmeta("eoce", context["target_eoce"][number]),
        ))
    for number in PUBLIC_ANSWERS:
        segment_pairs.append(segment_and_localization(
            records,
            indexes,
            f"r011/segment/b017/answer-4-{number}",
            f"r011/localization/id-ID/b017/answer-4-{number}",
            str(answer_units[number]["id"]),
            200 + number,
            "public_answer",
            resource_id,
            edition_id,
            [upstream_right],
            text_rights,
            [BOUNDARY_ID, f"4.{number}"],
            source_paths["answers"],
            context["answers_source_full"],
            smeta("answers", context["source_answers"][number]),
            target_paths["answers"],
            context["answers_target_full"],
            tmeta("answers", context["target_answers"][number]),
        ))

    evidence_payloads: dict[str, bytes] = {}
    artifact_roles: dict[str, dict[str, Any]] = {}

    def artifact(kind: str, role: str, path: Path, raw: bytes) -> dict[str, Any]:
        resolved_path = path.resolve()
        if resolved_path.is_relative_to(LANE.resolve()):
            original = resolved_path.relative_to(LANE.resolve()).as_posix()
        elif resolved_path.is_relative_to(INTERLANGUAGE_ROOT.resolve()):
            original = resolved_path.relative_to(INTERLANGUAGE_ROOT.resolve()).as_posix()
        else:
            original = path.as_posix()
        evidence_name = re.sub(r"[^A-Za-z0-9._-]+", "_", path.name)
        evidence_path = f"evidence/b017/{kind}-{role}-{evidence_name}"
        if evidence_path in evidence_payloads:
            raise RuntimeError(f"duplicate B017 evidence path: {evidence_path}")
        evidence_payloads[evidence_path] = raw
        row = backend_record(
            "artifact",
            f"r011/artifact/b017/{kind}/{role}",
            **common_fields(
                resource_id,
                edition_id,
                text_rights,
                source_local_ids=[BOUNDARY_ID, role],
                order=len(artifact_roles) + 1,
                source_path=original,
                source_sha256=sha256_bytes(raw),
                locale="zxx",
                translation_state="visually_checked",
            ),
            artifact_kind=f"{kind}_{role}",
            path=original,
            evidence_copy_path=evidence_path,
            bytes=len(raw),
            sha256=sha256_bytes(raw),
            result="exact B017 input or deterministic evidence",
            provenance=PROVENANCE,
        )
        add_record(records, indexes, "artifacts", row)
        artifact_roles[f"{kind}:{role}"] = row
        return row

    for role in sorted(context["ready"]):
        artifact("ready", role, LANE / context["ready"][role]["path"], context["ready_raw"][role])
    artifact("terminal", "contract", TERMINAL_CONTRACT, TERMINAL_CONTRACT.read_bytes())
    for role in sorted(context["contract"]["inputs"]):
        artifact(
            "terminal",
            role,
            LANE / context["contract"]["inputs"][role]["path"],
            context["terminal_raw"][role],
        )
    artifact("tool", "generator", SCRIPT_PATH, SCRIPT_PATH.read_bytes())
    validator_path = SCRIPT_PATH.with_name("validate_backend_b017.py")
    artifact("tool", "validator", validator_path, validator_path.read_bytes())
    spec_path = INTERLANGUAGE_ROOT / INTEROPERABILITY_SPEC["path"]
    artifact("spec", "interoperability", spec_path, require(spec_path, INTEROPERABILITY_SPEC))

    qa_witnesses = {
        "base_preservation": "ready:base_manifest",
        "source": "terminal:source_qa",
        "translation": "ready:candidate_qa",
        "terminology": "ready:terminology_qa_json",
        "asset_identity": "ready:boundary_blueprint",
        "rights": "ready:boundary_blueprint",
        "mathematics": "ready:candidate_qa",
        "topology": "terminal:source_qa",
        "build": "terminal:build_receipt",
        "visual": "terminal:visual_qa",
        "corrections": "ready:correction_candidates",
        "interoperability": "spec:interoperability",
        "isolation": "tool:generator",
    }
    qa_rows: list[dict[str, Any]] = []
    for order, qa_type in enumerate(QA_EVENT_TYPES, 1):
        witness = artifact_roles[qa_witnesses[qa_type]]
        qa = backend_record(
            "qa_event",
            f"r011/qa/b017/{qa_type.replace('_', '-')}",
            **common_fields(
                resource_id,
                edition_id,
                [],
                source_local_ids=[BOUNDARY_ID],
                parent_id=edition_id,
                order=order,
                locale="zxx",
                translation_state="visually_checked",
            ),
            qa_type=qa_type,
            result="passed",
            subject_id=str(section["id"]),
            witness_artifact_id=str(witness["id"]),
            witness_path=witness["path"],
            detail=f"Exact deterministic B017 {qa_type.replace('_', ' ')} gate passed.",
            provenance=PROVENANCE,
        )
        add_record(records, indexes, "qa_events", qa)
        qa_rows.append(qa)

    relation_counters: dict[str, int] = {}

    def relation(relation_type: str, from_id: str, to_id: str, qualifier: str) -> None:
        relation_counters[relation_type] = relation_counters.get(relation_type, 0) + 1
        order = relation_counters[relation_type]
        row = backend_record(
            "relation",
            f"r011/relation/b017/{relation_type}/{order:04d}",
            **common_fields(
                resource_id,
                edition_id,
                [],
                source_local_ids=[BOUNDARY_ID],
                order=order,
                locale="zxx",
                translation_state="structurally_verified",
            ),
            relation_type=relation_type,
            from_id=from_id,
            to_id=to_id,
            qualifier=qualifier,
        )
        add_record(records, indexes, "relations", row)

    children = worked_units + guided_units + guided_answer_units
    children += list(eoce_units.values()) + list(answer_units.values()) + list(gap_units.values())
    relation("contains", str(chapter["id"]), str(section["id"]), "source hierarchy")
    for child in children:
        relation("contains", str(child["parent_id"]), str(child["id"]), "B017 semantic hierarchy")
    relation("precedes", str(predecessor["id"]), str(section["id"]), "source order")
    relation("prerequisite", str(predecessor["id"]), str(section["id"]), "unit prerequisite")
    negative_binomial_concept = indexes["r011/concept/b017/negative-binomial-distribution"]
    for prerequisite_key in (
        "r011/concept/probability",
        "r011/concept/b016/c007",
        "r011/concept/b017/binomial-coefficient",
        "r011/concept/b017/fixed-number-of-successes",
        "r011/concept/b015/c008",
        "r011/concept/b015/c001",
    ):
        relation(
            "prerequisite",
            str(indexes[prerequisite_key]["id"]),
            str(negative_binomial_concept["id"]),
            "negative-binomial concept prerequisite",
        )
    for definition in TERM_DEFINITIONS:
        concept = indexes[str(definition["concept_key"])]
        term = indexes[f"r011/term/id-ID/b017/TM{int(str(definition['code'])[-3:]):03d}"]
        relation("covers", str(section["id"]), str(concept["id"]), "Section 4.4 concept")
        relation("lexicalizes", str(concept["id"]), str(term["id"]), "id-ID controlled term")
    for segment, localization in segment_pairs:
        relation("unit_contains_segment", str(segment["unit_id"]), str(segment["id"]), "semantic segmentation")
        relation("localizes", str(segment["id"]), str(localization["id"]), "id-ID localization")
    for answer, exercise in zip(guided_answer_units, guided_units):
        relation("answers", str(answer["id"]), str(exercise["id"]), "inline public guided answer")
    for number in PUBLIC_ANSWERS:
        relation("answers", str(answer_units[number]["id"]), str(eoce_units[number]["id"]), "public answer appendix")
    for number in O001_GAPS:
        relation("requires_companion_answer", str(eoce_units[number]["id"]), str(gap_units[number]["id"]), "O001 gap; restricted solution not accessed")
    relation("uses_asset", str(section["id"]), str(asset["id"]), "inline TeX table figure")
    for correction in correction_rows:
        relation("corrects", str(correction["id"]), str(correction["affected_id"]), "recorded upstream copyedit candidate")
    relation("governs", str(derivative_right["id"]), str(section["id"]), "B017 derivative text")
    relation("governs", str(derivative_right["id"]), str(asset["id"]), "B017 inline authored table")
    for qa in qa_rows:
        relation("validates", str(qa["id"]), str(qa["subject_id"]), "typed deterministic QA event")
    for artifact_row in artifact_roles.values():
        relation("documents", str(artifact_row["id"]), edition_id, str(artifact_row["artifact_kind"]))

    for rows in records.values():
        rows.sort(key=lambda row: str(row["id"]))
    new_counts = {
        name: len(records[name]) - len(base_records[name]) for name in sorted(records)
    }
    return records, evidence_payloads, new_counts


def compile_stage() -> dict[str, Any]:
    context = load_context()
    base_records, base_manifest = load_base_records()
    records, evidence_payloads, new_counts = compile_records(base_records, context)
    record_payloads = {
        RECORD_PATHS[name]: jsonl_bytes(records[name]) for name in sorted(RECORD_PATHS)
    }
    view_payloads, view_counts = build_views(records)
    generated_payloads: dict[str, bytes] = {
        **record_payloads,
        **view_payloads,
        "identity_map.jsonl": build_identity_map(records),
        **evidence_payloads,
    }
    generated_counts: dict[str, int | None] = {
        RECORD_PATHS[name]: len(records[name]) for name in RECORD_PATHS
    }
    generated_counts.update(view_counts)
    generated_counts["identity_map.jsonl"] = sum(len(rows) for rows in records.values())
    generated_counts.update({path: None for path in evidence_payloads})
    generated_paths = set(generated_payloads)
    base_copy_entries = [
        deepcopy(entry) for entry in base_manifest["files"] if entry["path"] not in generated_paths
    ]
    for entry in base_copy_entries:
        require(BASE_EXPORTS / entry["path"], entry)
    file_entries = base_copy_entries + [{
        "path": path,
        "bytes": len(raw),
        "sha256": sha256_bytes(raw),
        "records": generated_counts[path],
    } for path, raw in generated_payloads.items()]
    file_entries.sort(key=lambda entry: str(entry["path"]))
    record_counts = {name: len(records[name]) for name in sorted(records)}
    record_count = sum(record_counts.values())
    manifest = normalize({
        "$schema": "schemas/backend-manifest-v0.1.0.schema.json",
        "schema_version": SCHEMA_VERSION,
        "backend_id": stable_id("r011/backend/b017/final-isolated"),
        "backend_name": "r011-openintro-statistics-id-b017-final-isolated",
        "namespace_uuid": str(NAMESPACE),
        "boundary_id": BOUNDARY_ID,
        "workflow_id": WORKFLOW_ID,
        "recorded_at": RECORDED_AT,
        "authority": {
            **deepcopy(base_manifest["authority"]),
            "boundary_source_path": context["ready"]["main_authority"]["path"],
            "boundary_source_sha256": context["ready"]["main_authority"]["sha256"],
        },
        "canonicalization": deepcopy(base_manifest["canonicalization"]),
        "scope": (
            "Complete Chapter 4 Section 4.4 Negative binomial distribution / "
            "Distribusi binomial negatif, EoCE 27--30, public answers 27/29, "
            "O001 gaps 28/30, and one inline TeX table, ending before poisson."
        ),
        "stage_state": "isolated_terminal_backend_candidate",
        "admission_eligibility": "ready_for_separate_guarded_admission",
        "provenance": PROVENANCE,
        "base_preservation": {
            "boundary_id": BASE_BOUNDARY_ID,
            "manifest": deepcopy(BASE_MANIFEST_IDENTITY),
            "inventory": deepcopy(BASE_INVENTORY_IDENTITY),
            "record_count": BASE_RECORD_COUNT,
            "all_base_records_preserved_canonical_bytes": True,
        },
        "base_record_counts": deepcopy(BASE_RECORD_COUNTS),
        "new_b017_record_count": sum(new_counts.values()),
        "new_b017_record_counts": new_counts,
        "record_count": record_count,
        "record_counts": record_counts,
        "source_application": {
            "canonical_source_mutated_by_compiler": False,
            "terminal_identity_fail_closed": True,
            "terminal_contract": deepcopy(context["contract_identity"]),
            "terminal_inputs": deepcopy(context["contract"]["inputs"]),
            "ready_inputs": deepcopy(context["ready"]),
        },
        "topology": deepcopy(EXPECTED_TERMINAL_CLOSURE),
        "correction_closure": {
            "source_corrections": EXPECTED_TERMINAL_CLOSURE["source_corrections"],
            "authority_mutated": False,
            "post_corpus_single_report_only": True,
        },
        "terminology": {
            "locale": "id-ID",
            "backend_decision_count": len(TERM_DEFINITIONS),
            "field_usage_terms_checked": 11,
            "status": "PASS_NO_TERMINOLOGY_PROPAGATION_REQUIRED",
            "canonical_changes_recommended": 0,
            "glossary_changes_recommended": 0,
            "qa_json": deepcopy(context["ready"]["terminology_qa_json"]),
            "qa_markdown": deepcopy(context["ready"]["terminology_qa_markdown"]),
            "admission_evidence_promotions": [
                {
                    "role": role,
                    "source": deepcopy(context["ready"][role]),
                    "stage_evidence_path": (
                        f"evidence/b017/ready-{role}-"
                        f"{re.sub(r'[^A-Za-z0-9._-]+', '_', Path(context['ready'][role]['path']).name)}"
                    ),
                    "destination_path": destination,
                }
                for role, destination in sorted(TERMINOLOGY_EVIDENCE_DESTINATIONS.items())
            ],
        },
        "component_closure": {
            "inline_tex_assets": 1,
            "external_assets": 0,
            "data_files": 0,
            "code_files": 0,
            "rights_resolution": "CC-BY-SA-3.0-repository-declaration",
        },
        "build_binding": {
            "terminal_contract": deepcopy(context["contract_identity"]),
            "build_receipt": deepcopy(context["contract"]["inputs"]["build_receipt"]),
            "reader_pdf": deepcopy(context["contract"]["inputs"]["reader_pdf"]),
            "visual_qa": deepcopy(context["contract"]["inputs"]["visual_qa"]),
        },
        "o001_closure": {
            "public_answers": list(PUBLIC_ANSWERS),
            "companion_gaps": list(O001_GAPS),
            "restricted_solutions_accessed_or_invented": False,
        },
        "interoperability": {
            "status": "passed",
            "spec": deepcopy(INTEROPERABILITY_SPEC),
            "required_views": list(REQUIRED_VIEWS),
        },
        "known_limitations": [
            "O001 answers 28/30 remain explicit gaps; no restricted instructor solution was accessed or invented.",
            "The success/failure table is inline authored TeX, not an external asset.",
            "No Git operation, live admission, publication, credential access, or upstream contact was performed by this compiler.",
        ],
        "deferred_actions": ["separate guarded admission", "publication after admission"],
        "files": file_entries,
    })
    manifest_schema = parse_json(
        (BASE_EXPORTS / "schemas/backend-manifest-v0.1.0.schema.json").read_bytes(),
        "backend manifest schema",
    )
    jsonschema.validate(instance=manifest, schema=manifest_schema)
    return {
        "context": context,
        "base_records": base_records,
        "records": records,
        "new_counts": new_counts,
        "base_copy_entries": base_copy_entries,
        "generated_payloads": generated_payloads,
        "manifest": manifest,
        "manifest_raw": canonical_json(manifest),
    }


def self_test() -> dict[str, Any]:
    if sorted(EOCE) != [27, 28, 29, 30]:
        raise RuntimeError("B017 EoCE topology changed")
    if set(PUBLIC_ANSWERS) | set(O001_GAPS) != set(EOCE):
        raise RuntimeError("B017 public-answer/O001 closure no longer partitions EoCE")
    if set(PUBLIC_ANSWERS) & set(O001_GAPS):
        raise RuntimeError("B017 public-answer/O001 closure overlaps")
    if len(TERM_DEFINITIONS) != 8 or len({row["code"] for row in TERM_DEFINITIONS}) != 8:
        raise RuntimeError("B017 terminology topology changed")
    for key in [
        "r011/unit/source-label/negativeBinomial",
        "r011/asset/b017/inline-tex/successFailureOrdersForBriansFieldGoals",
        *[f"r011/term/id-ID/b017/TM{number:03d}" for number in range(1, 9)],
    ]:
        if not re.fullmatch(r"r011/[A-Za-z0-9._/-]+", key):
            raise RuntimeError(f"invalid B017 stable key: {key}")
        uuid.UUID(stable_id(key))
    ready, _ = bind_ready_inputs()
    bind_base(verify_inventory=False)
    return {
        "status": "PASS_B017_COMPILER_INERT_SELF_TEST",
        "boundary_id": BOUNDARY_ID,
        "base_record_count": BASE_RECORD_COUNT,
        "ready_input_count": len(ready),
        "terminal_contract_present": TERMINAL_CONTRACT.is_file(),
        "terminal_roles": sorted(TERMINAL_ROLE_PATHS),
        "predicted_record_types": sorted(NEW_RECORD_TYPES),
        "output_written": False,
    }


def probe() -> dict[str, Any]:
    base = bind_base(verify_inventory=True)
    ready, _ = bind_ready_inputs()
    result = {
        **self_test(),
        "status": "PASS_B017_READ_ONLY_PROBE_TERMINAL_PENDING",
        "base": base,
        "ready_inputs": ready,
        "terminal": {
            "path": TERMINAL_CONTRACT.relative_to(LANE).as_posix(),
            "present": TERMINAL_CONTRACT.is_file(),
            "pending_roles": sorted(TERMINAL_ROLE_PATHS),
            "required_gates": sorted(REQUIRED_TERMINAL_GATES),
        },
        "semantic_closure": deepcopy(EXPECTED_TERMINAL_CLOSURE),
    }
    if TERMINAL_CONTRACT.is_file():
        contract, contract_identity, _ = load_terminal_contract()
        result["status"] = "PASS_B017_READ_ONLY_PROBE_TERMINAL_BOUND"
        result["terminal"] = {
            "path": contract_identity["path"],
            "present": True,
            "identity": contract_identity,
            "status": contract["status"],
            "roles": sorted(contract["inputs"]),
            "required_gates": sorted(REQUIRED_TERMINAL_GATES),
        }
    return result


def allowed_stage(path: Path) -> bool:
    resolved = path.resolve()
    return any(
        resolved != root.resolve() and resolved.is_relative_to(root.resolve())
        for root in (SCRATCH_ROOT, FINAL_ROOT)
    )


def generate(output: Path) -> dict[str, Any]:
    resolved_output = output.resolve()
    if not allowed_stage(resolved_output):
        raise RuntimeError("B017 stage must be beneath the exact scratch or final backend stage root")
    if resolved_output.exists():
        raise RuntimeError(f"B017 isolated stage already exists: {resolved_output}")
    compiled = compile_stage()
    resolved_output.parent.mkdir(parents=True, exist_ok=True)
    resolved_output.mkdir()
    for entry in compiled["base_copy_entries"]:
        destination = resolved_output / entry["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(BASE_EXPORTS / entry["path"], destination)
    for relative, raw in sorted(compiled["generated_payloads"].items()):
        destination = resolved_output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)
    (resolved_output / "manifest.json").write_bytes(compiled["manifest_raw"])
    validation = validate_stage(resolved_output)
    return {
        "status": "PASS_B017_ISOLATED_DETERMINISTIC_BACKEND_GENERATED",
        "boundary_id": BOUNDARY_ID,
        "output": relative_path(resolved_output),
        "manifest": identity_raw(compiled["manifest_raw"]),
        "inventory": inventory(resolved_output),
        "record_count": compiled["manifest"]["record_count"],
        "record_counts": compiled["manifest"]["record_counts"],
        "new_b017_record_count": compiled["manifest"]["new_b017_record_count"],
        "new_b017_record_counts": compiled["manifest"]["new_b017_record_counts"],
        "validation_status": validation["status"],
    }


def validate_stage(stage: Path) -> dict[str, Any]:
    resolved_stage = stage.resolve()
    if not allowed_stage(resolved_stage) or not resolved_stage.is_dir():
        raise RuntimeError("B017 stage is outside the exact allowed roots or absent")
    compiled = compile_stage()
    expected_entries = {
        str(entry["path"]): {"bytes": int(entry["bytes"]), "sha256": str(entry["sha256"])}
        for entry in compiled["manifest"]["files"]
    }
    expected_entries["manifest.json"] = identity_raw(compiled["manifest_raw"])
    observed_paths = {
        path.relative_to(resolved_stage).as_posix()
        for path in resolved_stage.rglob("*") if path.is_file()
    }
    if observed_paths != set(expected_entries):
        raise RuntimeError(
            f"B017 stage inventory differs: missing={sorted(set(expected_entries)-observed_paths)!r} "
            f"extra={sorted(observed_paths-set(expected_entries))!r}"
        )
    for relative, expected in sorted(expected_entries.items()):
        require(resolved_stage / relative, expected)
    if (resolved_stage / "manifest.json").read_bytes() != compiled["manifest_raw"]:
        raise RuntimeError("B017 stage manifest differs from deterministic replay")
    for relative, raw in compiled["generated_payloads"].items():
        if (resolved_stage / relative).read_bytes() != raw:
            raise RuntimeError(f"B017 generated payload differs from replay: {relative}")

    record_schema = parse_json(
        (resolved_stage / "schemas/backend-record-v0.1.0.schema.json").read_bytes(),
        "backend record schema",
    )
    validator = jsonschema.Draft202012Validator(
        record_schema, format_checker=jsonschema.FormatChecker()
    )
    all_rows = [row for rows in compiled["records"].values() for row in rows]
    all_ids = {str(row["id"]) for row in all_rows}
    if len(all_ids) != len(all_rows):
        raise RuntimeError("B017 backend contains duplicate UUIDs")
    for row in all_rows:
        if row.get("boundary_id") != BOUNDARY_ID:
            continue
        validator.validate(row)
        if str(row["id"]) != stable_id(str(row["stable_key"])):
            raise RuntimeError(f"B017 stable identity mismatch: {row['stable_key']}")
        for field in (
            "resource_id", "edition_id", "parent_id", "unit_id", "source_segment_id",
            "concept_id", "from_id", "to_id", "affected_id", "subject_id",
            "witness_artifact_id",
        ):
            value = row.get(field)
            if value is not None and str(value) not in all_ids:
                raise RuntimeError(f"dangling B017 {field} on {row['stable_key']}: {value}")
        for value in row.get("rights_component_ids", []):
            if str(value) not in all_ids:
                raise RuntimeError(f"dangling B017 rights component on {row['stable_key']}: {value}")

    for name, base_rows in compiled["base_records"].items():
        staged = {str(row["id"]): canonical_json_text(row) for row in compiled["records"][name]}
        for row in base_rows:
            if staged.get(str(row["id"])) != canonical_json_text(row):
                raise RuntimeError(f"B016 base record changed in B017 stage: {row['stable_key']}")
    new_rows = [row for row in all_rows if row.get("boundary_id") == BOUNDARY_ID]
    if len(new_rows) != compiled["manifest"]["new_b017_record_count"]:
        raise RuntimeError("B017 new-record count differs from manifest")
    if {str(row["record_type"]) for row in new_rows} != NEW_RECORD_TYPES:
        raise RuntimeError("B017 new-record type closure differs")
    if {row["qa_type"] for row in new_rows if row["record_type"] == "qa_event"} != set(QA_EVENT_TYPES):
        raise RuntimeError("B017 typed QA-event closure differs")
    relation_types = {
        str(row["relation_type"]) for row in new_rows if row["record_type"] == "relation"
    }
    if relation_types != RELATION_CLASSES:
        raise RuntimeError(f"B017 relation-class closure differs: {sorted(relation_types)!r}")
    if compiled["manifest"]["topology"] != EXPECTED_TERMINAL_CLOSURE:
        raise RuntimeError("B017 manifest semantic closure differs")
    return {
        "status": "PASS_B017_INDEPENDENT_DETERMINISTIC_STAGE_VALIDATION",
        "boundary_id": BOUNDARY_ID,
        "stage": relative_path(resolved_stage),
        "manifest": expected_entries["manifest.json"],
        "inventory": inventory(resolved_stage),
        "record_count": compiled["manifest"]["record_count"],
        "record_counts": compiled["manifest"]["record_counts"],
        "new_b017_record_count": compiled["manifest"]["new_b017_record_count"],
        "new_b017_record_counts": compiled["manifest"]["new_b017_record_counts"],
        "base_records_preserved": BASE_RECORD_COUNT,
        "checks": [
            "terminal_contract_exact",
            "all_terminal_gates_passed",
            "manifest_schema_valid",
            "stage_inventory_exact",
            "generated_payload_replay_exact",
            "record_schema_valid",
            "stable_uuid_identity_exact",
            "referential_integrity",
            "base_record_canonical_bytes_preserved",
            "required_views_replayed",
            "typed_qa_closure",
            "relation_class_closure",
            "exercise_answer_o001_closure",
            "component_rights_closure",
            "source_correction_closure",
            "next_cursor_closure",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--self-test", action="store_true")
    modes.add_argument("--probe", action="store_true")
    modes.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        if args.self_test:
            result = self_test()
        elif args.probe:
            result = probe()
        else:
            result = generate(args.output)
        print(canonical_json(result).decode("utf-8"), end="")
    except TerminalInputsUnresolved as exc:
        print(canonical_json({
            "status": "BLOCKED_EXACT_NONHUMAN_TERMINAL_INPUTS_UNRESOLVED",
            "boundary_id": BOUNDARY_ID,
            "error": str(exc),
            "pending_roles": sorted(TERMINAL_ROLE_PATHS),
            "output_written": False,
        }).decode("utf-8"), end="", file=sys.stderr)
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
