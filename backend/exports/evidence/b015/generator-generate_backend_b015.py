#!/usr/bin/env python3
"""Prepare the deterministic R011-B015 modular-backend append, fail closed.

This module is deliberately inert at import time.  It binds the exact admitted
R011-B014 backend and the refreshed B015 source/translation/terminology/asset
inputs, exposes read-only ``--self-test`` and ``--probe`` modes, and refuses to
write an isolated backend stage until a later terminal contract is itself
byte/hash-bound in ``TERMINAL_CONTRACT_IDENTITY``.  No live backend, source,
control, release, Git, network, credential, publication, or upstream state is
ever mutated by this preparation revision.

Stable keys below are assigned from source labels, source topology, boundary
codes, or explicit locale-neutral semantic codes.  Reader-visible source or
translated wording is never transformed into an identifier.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
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
BOUNDARY_ID = "R011-B015"
BASE_BOUNDARY_ID = "R011-B014"
SCHEMA_VERSION = "0.1.0"
WORKFLOW_ID = "r011-openintro-statistics-id-b015-backend-preparation"
RECORDED_AT = "2026-08-25T15:00:00+02:00"
NAMESPACE = uuid.UUID("3f5320fb-d2a2-4aa6-a8fe-298715378407")

BASE_EXPORTS = LANE / "backend" / "exports"
BASE_MANIFEST = BASE_EXPORTS / "manifest.json"
PREP_ROOT = LANE / "qa" / "b015-backend-prep"
FINAL_ROOT = LANE / "qa" / "b015-backend-final"
TERMINAL_CONTRACT = PREP_ROOT / "R011-B015_TERMINAL_INPUTS.json"

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
    "bytes": 68471,
    "sha256": "3167da0d4f06973d81f2f58c7885cfb7ceb70604631f1e95b7ddc48afa4d845b",
}
BASE_INVENTORY_IDENTITY = {
    "identity_kind": "directory-inventory-tsv-sha256/v1",
    "files": 339,
    "bytes": 151666115,
    "sha256": "cf9d03c0f0f08c5374ae8b24592b48e43689ebb926596e8552d9f80f7ac92d9d",
}
BASE_RECORD_COUNT = 5213
BASE_EVIDENCE = {
    "boundary_receipt": {
        "path": "qa/R011-B014_BOUNDARY_RECEIPT.json",
        "bytes": 17895,
        "sha256": "98921a7fb3263f6dfaff558896f3ae2bdd4ee87a75f500b2b6c99ba488208f10",
    },
    "admission_checkpoint": {
        "path": "00_control/R011-B014_ADMISSION_CHECKPOINT.md",
        "bytes": 1779,
        "sha256": "d1e6e30e33d6bdbc3899b8469b81b1aed7140c1c57cfea46fdf4c057fd994f72",
    },
    "post_admission_verification": {
        "path": "qa/b014-admission/R011-B014_POST_ADMISSION_VERIFICATION.json",
        "bytes": 9198,
        "sha256": "ed68a7648bdbb5b64064c70ee5679943ccb06a2619b3c97ce26b39f8183574e1",
    },
}

INTEROPERABILITY_SPEC = {
    "path": (
        "outputs/01a01ec1-e685-70d0-b022-211396334723/curriculum_logbook/"
        "05_MODULAR_BACKEND_INTEROPERABILITY_V0.md"
    ),
    "bytes": 5204,
    "sha256": "fdb6c8fa87ea88d8fcb6ddf40415d8a6a6da315025b9b18eb917190f508b1c5f",
}

# Exact refreshed inputs that exist now.  Pending build identities are never
# represented here by invented placeholders.
READY_INPUTS = {
    "source_closure": ("qa/b015-source/R011-B015_SOURCE_CLOSURE.json", 11801, "fc988653b86c637737d7430357959fbd2dfc06c931f1858ad53a47c2bb12e387"),
    "translation_qa": ("qa/b015-translation/R011-B015_TRANSLATION_QA.json", 8286, "dbdabe9756101a49ddd587e927444df0a594e718f13eb4ee5f8c2cc4fc5a78fb"),
    "translation_verifier": ("qa/b015-translation/verify_b015_candidate.py", 17163, "f55b6f5242f73eaa2a9aee30419167f8ac770bb1bd2db40df9d1ada667ae4f09"),
    "controlled_terms": ("qa/b015-terminology/R011-B015_CONTROLLED_TERMS.tsv", 3967, "1ee92465c0e419935fc635ef2cdbacf3924df49e26e5c0b42bc30ca954397446"),
    "terminology_qa": ("qa/b015-terminology/R011-B015_TERMINOLOGY_QA.json", 3398, "dcf597154887968b190ca00b63cd412866ada455486dbf70709ae66ee537e885"),
    "asset_rights_closure": ("qa/b015-assets/R011-B015_ASSET_RIGHTS_CLOSURE.json", 6295, "95322fc6876c5ea69abae60c7a221801f25903d225a6a24ddf9bd1dad751af3b"),
    "main_fragment": ("scratch/b015-candidate/ch_distributions_section_4_2_id.tex", 12690, "367dbd3a92deaa476231861fcf8dd266bd877278f7620f1967da1e672d6e0497"),
    "eoce_fragment": ("scratch/b015-candidate/geometric_distribution_B015.tex", 3804, "56b3f7e137755aa4d7187a82dd71f4c1b2dd6f6999bade9c4a96dfba98a0cc77"),
    "public_answers_fragment": ("scratch/b015-candidate/R011-B015_PUBLIC_ODD_ANSWERS.tex", 906, "a7d672e808f66bfc57cfe70f52fe41b29486997b8eca09c99b2f2c4e63a04dd9"),
    "data_appendix_fragment": ("scratch/b015-candidate/data_geomDist_B015.tex", 231, "20acc17df7ee9dfe7f3b747aabc08cd5003a14f1ef126c479e7617fbd877a489"),
    "figure_label_map": ("scratch/b015-candidate/geometricDist70_id-ID_labels.tsv", 167, "ce45d9a5b529f599400e5230db999f70a7a2009a820eebf208e28565719027a3"),
    "main_authority": ("authority/upstream/openintro-statistics-fee25091fb24e89c36296fd67c48c1fcf7a93b6e/ch_distributions/TeX/ch_distributions.tex", 91188, "71e4985a1bf31e9dd6897ec2bd246b3b2f8cd62ab55524a5b1bfe791e613a3a9"),
    "eoce_authority": ("authority/upstream/openintro-statistics-fee25091fb24e89c36296fd67c48c1fcf7a93b6e/ch_distributions/TeX/geometric_distribution.tex", 3658, "3835748279ccb79db81952e9be9fdae4d2ddb677da57f885cbe781af74b4e448"),
    "public_answers_authority": ("authority/upstream/openintro-statistics-fee25091fb24e89c36296fd67c48c1fcf7a93b6e/extraTeX/eoceSolutions/eoceSolutions.tex", 106045, "6c4e01376db4c023cc7b3f9949490e57220ef1cb831c580da71efde6ce723268"),
    "data_authority": ("authority/upstream/openintro-statistics-fee25091fb24e89c36296fd67c48c1fcf7a93b6e/extraTeX/data/data.tex", 26134, "6456ef7e9d0f855dbba47f9f62f0f10ae731d4f7cd558399848419d3cbdfd88b"),
    "source_figure_r": ("authority/upstream/openintro-statistics-fee25091fb24e89c36296fd67c48c1fcf7a93b6e/ch_distributions/figures/geometricDist70/geometricDist70.R", 663, "ba8886023f545cacb04c2eaccc8d2bfe3b83c79a0425df05b6c1266181384825"),
    "source_figure_pdf": ("authority/upstream/openintro-statistics-fee25091fb24e89c36296fd67c48c1fcf7a93b6e/ch_distributions/figures/geometricDist70/geometricDist70.pdf", 4578, "41fcdce79ef9b593c6c834b79d19099fee5c8d3a7ba5b6df259e1c3d73b3fd3e"),
    "component_rights_control": ("00_control/COMPONENT_RIGHTS.csv", 9999, "009feba8ff1f329ef742793f55f6b090dd08f3f761f9b9cc1edcbe03ecff58f0"),
    "admitted_terminology_view": ("backend/exports/views/terminology.csv", 32235, "23b1a66755943553dda63ae2f0cb1d39042a1e960c4fe2720e9ad4ee412415fc"),
}

# Exact roles, not guessed identities, which a non-human build/QA gate must
# supply.  The eventual contract must bind a concrete path, byte count and
# SHA-256 for every role and pass the typed gate assertions below.
PENDING_TERMINAL_ROLES = {
    "candidate_builder": "isolated B015 assembler/build implementation",
    "assembled_main": "assembled Chapter 4 source containing the exact Section 4.2 fragment",
    "assembled_eoce": "assembled geometric-distribution EoCE source containing 11--16",
    "assembled_public_answers": "assembled public-solutions source containing answers 11/13/15",
    "assembled_data_appendix": "assembled data appendix containing the geomDist entry",
    "localized_figure_r": "localized geometricDist70 R producer with only the approved strings changed",
    "localized_figure_pdf": "localized geometricDist70 PDF generated from that exact R producer",
    "localized_asset_qa": "typed two-run asset determinism, geometry, text-extraction and machine-QA receipt",
    "source_manifest": "fresh isolated B015 source snapshot inventory",
    "source_qa": "typed overlay/topology/math/source-identity QA receipt",
    "build_receipt": "typed deterministic isolated reader-build receipt",
    "reader_pdf": "fresh isolated B015 reader PDF",
    "visual_qa": "typed bounded visual QA for section, exercises, answers, figure and transitions",
}

# It would be unsafe to accept an unbound terminal-contract filename.  A later
# bounded finalization step must replace None with its exact bytes/SHA-256 only
# after every role above exists and passes deterministic QA.
TERMINAL_CONTRACT_IDENTITY: dict[str, Any] | None = {
    "bytes": 4434,
    "sha256": "63d08fe7bbc6184bc5f64b64ca0edda9af36db72dc09e202f949f03914da4f26",
}

EOCE = {
    11: "is_it_bernouilli",
    12: "with_without_replacement",
    13: "eye_color_geometric",
    14: "defective_rate",
    15: "bernoulli_mean_derivation",
    16: "bernoulli_sd_derivation",
}
PUBLIC_ANSWERS = (11, 13, 15)
O001_GAPS = (12, 14, 16)

# Explicit semantic codes prevent wording-derived identity.  The source and
# target strings remain data in the controlled TSV, never key material.
TERM_CONCEPT_KEYS = {
    "B015-TM001": "r011/concept/b015/c001",
    "B015-TM002": "r011/concept/b015/c002",
    "B015-TM003": "r011/concept/b015/c003",
    "B015-TM004": "r011/concept/b015/c004",
    "B015-TM005": "r011/concept/b015/c005",
    "B015-TM006": "r011/concept/b015/c006",
    "B015-TM007": "r011/concept/b015/c007",
    "B015-TM008": "r011/concept/b015/c008",
    "B015-TM009": "r011/concept/b012/probability-distribution",
    "B015-TM010": "r011/concept/b012/random-variable",
    "B015-TM011": "r011/concept/b015/c011",
    "B015-TM012": "r011/concept/b012/expected-value",
    "B015-TM013": "r011/concept/b014/mean",
    "B015-TM014": "r011/concept/b012/variance",
    "B015-TM015": "r011/concept/b014/standard-deviation",
    "B015-TM016": "r011/concept/independent",
    "B015-TM017": "r011/concept/b015/c017",
    "B015-TM018": "r011/concept/b009/disjoint",
    "B015-TM019": "r011/concept/b009/complement",
    "B015-TM020": "r011/concept/b009/random-process",
    "B015-TM021": "r011/concept/b015/c021",
    "B015-TM022": "r011/concept/b011/with-replacement",
    "B015-TM023": "r011/concept/b011/without-replacement",
    "B015-TM024": "r011/concept/right-skewed",
    "B015-TM025": "r011/concept/b015/c025",
    "B015-TM026": "r011/concept/b015/c026",
}

SEMANTIC_BLUEPRINT = {
    "section": "r011/unit/source-label/geomDist",
    "subsections": ["r011/unit/b015/subsection-01", "r011/unit/b015/subsection-02"],
    "worked_examples": [
        "r011/unit/source-label/waitForDeductible",
        "r011/unit/source-label/insureFirstSuccessInLT4",
        "r011/unit/source-label/carInsure08DrawOne",
    ],
    "guided_exercises": [f"r011/unit/guided-exercise/ch04-sec4.2-{n:02d}" for n in range(1, 4)],
    "guided_inline_answers": [f"r011/unit/guided-solution/ch04-sec4.2-{n:02d}" for n in range(1, 4)],
    "eoce_exercises": [f"r011/unit/exercise/4.{n}/{EOCE[n]}" for n in sorted(EOCE)],
    "public_answers": [f"r011/unit/solution/4.{n}" for n in PUBLIC_ANSWERS],
    "o001_companion_gaps": [f"r011/unit/o001-gap/4.{n}" for n in O001_GAPS],
    "data_appendix": "r011/unit/data-appendix/source-ref/geomDist",
    "assets": [
        "r011/asset/b015/source-r/geometricDist70",
        "r011/asset/b015/source-pdf/geometricDist70",
        "r011/asset/b015/localized-r/geometricDist70",
        "r011/asset/b015/localized-pdf/geometricDist70",
    ],
    "corrections": [f"r011/correction/b015/B015-SC{n:03d}" for n in range(1, 6)],
    "terms": [f"r011/term/id-ID/b015/TM{n:03d}" for n in range(1, 27)],
    "concept_prerequisites": [
        ["r011/concept/probability", "r011/concept/b015/c002"],
        ["r011/concept/b012/random-variable", "r011/concept/b015/c003"],
        ["r011/concept/b015/c002", "r011/concept/b015/c001"],
        ["r011/concept/b015/c004", "r011/concept/b015/c001"],
        ["r011/concept/independent", "r011/concept/b015/c017"],
        ["r011/concept/b015/c017", "r011/concept/b015/c001"],
        ["r011/concept/b012/expected-value", "r011/concept/b015/c001"],
    ],
    "unit_prerequisites": [
        ["r011/unit/source-label/randomVariablesSection", "r011/unit/source-label/geomDist"]
    ],
    "hierarchy_parent": "r011/unit/source-label/ch_distributions",
    "predecessor": "r011/unit/source-label/normalDist",
    "relation_classes": [
        "contains", "precedes", "prerequisite", "covers", "lexicalizes",
        "unit_contains_segment", "localizes", "answers",
        "requires_companion_answer", "uses_asset", "produces", "depends_on",
        "adapts", "corrects", "governs", "validates", "documents",
    ],
    "qa_event_types": [
        "base_preservation", "source", "translation", "terminology",
        "asset_localization", "rights", "mathematics", "topology", "build",
        "visual", "corrections", "interoperability", "isolation",
    ],
    "required_views": [
        "views/resource_editions.csv", "views/unit_hierarchy.csv",
        "views/relations.csv", "views/segments_locale.csv",
        "views/terminology.csv", "views/exercises_answers.csv",
        "views/rights_components.csv", "views/corrections.csv",
        "views/qa_build_events.csv", "views/artifacts.csv",
    ],
}

PREDICTED_RECORD_CLASSES = [
    "unit", "concept", "segment", "localization", "term", "asset",
    "relation", "rights", "qa_event", "artifact", "correction",
]
REUSED_RECORD_CLASSES = ["program", "course", "resource", "edition"]


class TerminalInputsUnresolved(RuntimeError):
    """The sealed terminal contract is absent or not exact."""


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def identity(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise RuntimeError(f"missing exact input: {path}")
    raw = path.read_bytes()
    return {"bytes": len(raw), "sha256": sha256_bytes(raw)}


def require(path: Path, expected: dict[str, Any]) -> bytes:
    raw = path.read_bytes() if path.is_file() else None
    observed = None if raw is None else {"bytes": len(raw), "sha256": sha256_bytes(raw)}
    wanted = {"bytes": int(expected["bytes"]), "sha256": str(expected["sha256"])}
    if observed != wanted:
        raise RuntimeError(f"exact identity mismatch for {path}: {observed!r} != {wanted!r}")
    assert raw is not None
    return raw


def inventory(root: Path) -> dict[str, Any]:
    rows: list[tuple[str, int, str]] = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            raw = path.read_bytes()
            rows.append((path.relative_to(root).as_posix(), len(raw), sha256_bytes(raw)))
    payload = "".join(f"{path}\t{size}\t{digest}\n" for path, size, digest in rows).encode("utf-8")
    return {
        "identity_kind": "directory-inventory-tsv-sha256/v1",
        "files": len(rows),
        "bytes": sum(size for _path, size, _digest in rows),
        "sha256": sha256_bytes(payload),
    }


def stable_id(stable_key: str) -> str:
    return str(uuid.uuid5(NAMESPACE, stable_key))


def normalize(value: Any) -> Any:
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, list):
        return [normalize(item) for item in value]
    if isinstance(value, dict):
        return {normalize(str(key)): normalize(item) for key, item in value.items()}
    return value


def canonical_json_text(value: Any) -> str:
    return json.dumps(normalize(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


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


def jsonl_bytes(rows: list[dict[str, Any]]) -> bytes:
    return "".join(canonical_json_text(row) + "\n" for row in sorted(rows, key=lambda item: item["id"])).encode("utf-8")


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
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n", extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({column: csv_cell(row.get(column)) for column in columns})
    return stream.getvalue().encode("utf-8")


def one(records: dict[str, list[dict[str, Any]]], name: str, stable_key: str) -> dict[str, Any]:
    rows = [row for row in records[name] if row.get("stable_key") == stable_key]
    if len(rows) != 1:
        raise RuntimeError(f"expected one {name} record {stable_key!r}, found {len(rows)}")
    return rows[0]


def line_table(raw: bytes) -> tuple[list[bytes], list[int]]:
    lines = raw.splitlines(keepends=True)
    starts: list[int] = []
    cursor = 0
    for line in lines:
        starts.append(cursor)
        cursor += len(line)
    return lines, starts


def span_meta(raw: bytes, start: int, end: int) -> dict[str, Any]:
    if not 0 <= start < end <= len(raw):
        raise RuntimeError(f"invalid span {start}:{end}/{len(raw)}")
    _lines, starts = line_table(raw)
    first = max(0, next((i for i, value in enumerate(starts) if value > start), len(starts)) - 1)
    last = max(0, next((i for i, value in enumerate(starts) if value >= end), len(starts)) - 1)
    return {
        "line_start": first + 1,
        "line_end": last + 1,
        "byte_start": start,
        "byte_end_exclusive": end,
        "bytes": end - start,
        "sha256": sha256_bytes(raw[start:end]),
    }


def schema_span(meta: dict[str, Any]) -> dict[str, int]:
    return {key: int(meta[key]) for key in ("line_start", "line_end", "byte_start", "byte_end_exclusive")}


def rebase_span(meta: dict[str, Any], full_raw: bytes, offset: int) -> dict[str, Any]:
    return span_meta(full_raw, offset + int(meta["byte_start"]), offset + int(meta["byte_end_exclusive"]))


def unique_offset(haystack: bytes, needle: bytes, role: str) -> int:
    start = haystack.find(needle)
    if start < 0 or haystack.find(needle, start + 1) >= 0:
        raise RuntimeError(f"{role} is not a unique exact subspan")
    return start


def balanced_command_end(raw: bytes, start: int, command: bytes) -> int:
    open_at = raw.find(b"{", start + len(command))
    if open_at < 0:
        raise RuntimeError(f"missing argument for {command!r}")
    depth = 0
    for index in range(open_at, len(raw)):
        token = raw[index:index + 1]
        escaped = index > 0 and raw[index - 1:index] == b"\\"
        if token == b"{" and not escaped:
            depth += 1
        elif token == b"}" and not escaped:
            depth -= 1
            if depth == 0:
                return index + 1
    raise RuntimeError(f"unterminated argument for {command!r}")


def structural_spans(raw: bytes) -> list[dict[str, Any]]:
    blocks: list[tuple[int, int, str, int]] = []
    for begin, end_token, kind, expected in (
        (b"\\begin{examplewrap}", b"\\end{examplewrap}", "worked_example", 3),
        (b"\\begin{exercisewrap}", b"\\end{exercisewrap}", "guided_exercise", 3),
    ):
        cursor = count = 0
        while True:
            start = raw.find(begin, cursor)
            if start < 0:
                break
            close = raw.find(end_token, start + len(begin))
            if close < 0:
                raise RuntimeError(f"unterminated {kind}")
            end = close + len(end_token)
            end += 2 if raw[end:end + 2] == b"\r\n" else (1 if raw[end:end + 1] == b"\n" else 0)
            count += 1
            blocks.append((start, end, kind, count))
            cursor = end
        if count != expected:
            raise RuntimeError(f"B015 {kind} count changed: {count} != {expected}")
    cursor = count = 0
    command = b"\\footnotetext"
    while True:
        start = raw.find(command, cursor)
        if start < 0:
            break
        end = balanced_command_end(raw, start, command)
        end += 2 if raw[end:end + 2] == b"\r\n" else (1 if raw[end:end + 1] == b"\n" else 0)
        count += 1
        blocks.append((start, end, "guided_inline_answer", count))
        cursor = end
    if count != 3:
        raise RuntimeError("B015 inline-answer count changed")
    blocks.sort()
    if any(left[1] > right[0] for left, right in zip(blocks, blocks[1:])):
        raise RuntimeError("overlapping B015 semantic blocks")
    result: list[dict[str, Any]] = []
    cursor = prose = 0
    for start, end, kind, number in blocks:
        if raw[cursor:start].strip():
            prose += 1
            result.append({"kind": "section_prose", "number": prose, "span": span_meta(raw, cursor, start)})
        result.append({"kind": kind, "number": number, "span": span_meta(raw, start, end)})
        cursor = end
    if raw[cursor:].strip():
        prose += 1
        result.append({"kind": "section_prose", "number": prose, "span": span_meta(raw, cursor, len(raw))})
    if prose != 4:
        raise RuntimeError(f"B015 prose segmentation changed: {prose} != 4")
    return result


def subsection_spans(raw: bytes) -> list[dict[str, Any]]:
    matches = list(re.finditer(rb"\\subsection\{([^}]+)\}", raw))
    if len(matches) != 2:
        raise RuntimeError("B015 subsection topology changed")
    return [
        {
            "number": index + 1,
            "span": span_meta(raw, match.start(), matches[index + 1].start() if index + 1 < len(matches) else len(raw)),
        }
        for index, match in enumerate(matches)
    ]


def marker_spans(raw: bytes, numbers: list[int]) -> dict[int, dict[str, Any]]:
    wanted = set(numbers)
    lines, starts = line_table(raw)
    found: list[tuple[int, int]] = []
    for index, line in enumerate(lines):
        match = re.fullmatch(rb"%\s*(\d+)\r?\n?", line)
        if match and int(match.group(1)) in wanted:
            found.append((int(match.group(1)), starts[index]))
    if [number for number, _start in found] != numbers:
        raise RuntimeError(f"marker topology changed: {[number for number, _ in found]} != {numbers}")
    result: dict[int, dict[str, Any]] = {}
    for index, (number, start) in enumerate(found):
        end = found[index + 1][1] if index + 1 < len(found) else len(raw)
        while end > start and raw[end - 1:end] in (b"\n", b"\r", b" ", b"\t"):
            end -= 1
        result[number] = span_meta(raw, start, end)
    return result


def bind_base() -> dict[str, Any]:
    for item in BASE_EVIDENCE.values():
        require(LANE / item["path"], item)
    manifest = json.loads(require(BASE_MANIFEST, BASE_MANIFEST_IDENTITY))
    if manifest.get("boundary_id") != BASE_BOUNDARY_ID:
        raise RuntimeError("live base boundary is not exact admitted R011-B014")
    if manifest.get("backend_name") != "r011-openintro-statistics-id-b014-final-isolated":
        raise RuntimeError("live base backend name changed")
    record_count = sum(int(value) for value in manifest.get("record_counts", {}).values())
    if record_count != BASE_RECORD_COUNT:
        raise RuntimeError(f"base record count changed: {record_count} != {BASE_RECORD_COUNT}")
    observed_inventory = inventory(BASE_EXPORTS)
    if observed_inventory != BASE_INVENTORY_IDENTITY:
        raise RuntimeError(f"base inventory changed: {observed_inventory!r}")
    return {
        "boundary_id": BASE_BOUNDARY_ID,
        "manifest": {"path": "backend/exports/manifest.json", **BASE_MANIFEST_IDENTITY},
        "inventory": observed_inventory,
        "record_count": record_count,
        "record_counts": manifest["record_counts"],
        "preservation_rule": "all admitted record canonical bytes must remain identical by UUID",
    }


def bind_ready_inputs() -> dict[str, dict[str, Any]]:
    bound: dict[str, dict[str, Any]] = {}
    require(INTERLANGUAGE_ROOT / INTEROPERABILITY_SPEC["path"], INTEROPERABILITY_SPEC)
    for role, (relative, size, digest) in sorted(READY_INPUTS.items()):
        require(LANE / relative, {"bytes": size, "sha256": digest})
        bound[role] = {"path": relative, "bytes": size, "sha256": digest}
    source = json.loads((LANE / READY_INPUTS["source_closure"][0]).read_text(encoding="utf-8"))
    translation = json.loads((LANE / READY_INPUTS["translation_qa"][0]).read_text(encoding="utf-8"))
    terminology = json.loads((LANE / READY_INPUTS["terminology_qa"][0]).read_text(encoding="utf-8"))
    assets = json.loads((LANE / READY_INPUTS["asset_rights_closure"][0]).read_text(encoding="utf-8"))
    if source.get("boundary_id") != BOUNDARY_ID or not str(source.get("status", "")).startswith("PASS_"):
        raise RuntimeError("B015 source closure is not a passing B015 record")
    if translation.get("boundary_id") != BOUNDARY_ID or not str(translation.get("status", "")).startswith("PASS_"):
        raise RuntimeError("B015 translation QA is not a passing B015 record")
    if terminology.get("boundary_id") != BOUNDARY_ID or terminology.get("decision_count") != len(TERM_CONCEPT_KEYS):
        raise RuntimeError("B015 terminology decision topology changed")
    if assets.get("boundary_id") != BOUNDARY_ID or not str(assets.get("status", "")).startswith("PASS_"):
        raise RuntimeError("B015 asset/right closure is not a passing B015 record")
    coverage = translation.get("coverage", {})
    expected = {
        "subsections": 2,
        "worked_examples": 3,
        "guided_exercises": 3,
        "guided_inline_answers": 3,
        "eoce_ids": sorted(EOCE),
        "public_answer_ids": list(PUBLIC_ANSWERS),
        "o001_missing_public_answers": list(O001_GAPS),
        "data_appendix_entries": 1,
        "direct_r_producers": 1,
        "direct_pdf_assets": 1,
    }
    for key, value in expected.items():
        if coverage.get(key) != value:
            raise RuntimeError(f"B015 coverage changed for {key}: {coverage.get(key)!r} != {value!r}")
    if translation.get("restricted_solutions_accessed") or translation.get("restricted_solutions_invented"):
        raise RuntimeError("restricted solution material entered B015 inputs")
    if len(source.get("source_corrections", [])) != 5:
        raise RuntimeError("B015 source-correction topology changed")
    return bound


def load_terminal_contract() -> dict[str, Any]:
    if TERMINAL_CONTRACT_IDENTITY is None:
        raise TerminalInputsUnresolved(
            "R011-B015 terminal contract identity is deliberately unresolved; "
            "pending roles: " + ", ".join(sorted(PENDING_TERMINAL_ROLES))
        )
    raw = require(TERMINAL_CONTRACT, TERMINAL_CONTRACT_IDENTITY)
    contract = json.loads(raw)
    if contract.get("$schema") != "interlanguage.r011-b015-terminal-inputs/v1":
        raise TerminalInputsUnresolved("unexpected B015 terminal-contract schema")
    if contract.get("boundary_id") != BOUNDARY_ID or contract.get("status") != "READY_TERMINAL_INPUTS":
        raise TerminalInputsUnresolved("B015 terminal contract is not READY_TERMINAL_INPUTS")
    inputs = contract.get("inputs", {})
    if set(inputs) != set(PENDING_TERMINAL_ROLES):
        raise TerminalInputsUnresolved("B015 terminal role set is incomplete or expanded")
    for role, item in sorted(inputs.items()):
        if set(item) != {"path", "bytes", "sha256"}:
            raise TerminalInputsUnresolved(f"terminal role {role} lacks exact identity fields")
        relative = Path(item["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise TerminalInputsUnresolved(f"terminal role {role} has unsafe path")
        require(LANE / relative, item)
    gates = contract.get("gates", {})
    required_gates = {
        "assembly", "source", "mathematics", "topology",
        "localized_asset_determinism", "localized_asset_text",
        "localized_asset_geometry", "build_determinism", "visual",
    }
    if set(gates) != required_gates or any(value != "passed" for value in gates.values()):
        raise TerminalInputsUnresolved("one or more deterministic B015 terminal gates are not passed")
    return contract


def load_base_records() -> tuple[dict[str, list[dict[str, Any]]], dict[str, bytes], dict[str, Any]]:
    bind_base()
    manifest = json.loads(require(BASE_MANIFEST, BASE_MANIFEST_IDENTITY))
    entries = {entry["path"]: entry for entry in manifest["files"]}
    records: dict[str, list[dict[str, Any]]] = {}
    for name, relative in RECORD_PATHS.items():
        entry = entries[relative]
        raw = require(BASE_EXPORTS / relative, entry)
        rows = load_jsonl(raw)
        if len(rows) != int(entry["records"]) or jsonl_bytes(rows) != raw:
            raise RuntimeError(f"noncanonical B014 base payload: {relative}")
        records[name] = rows
    auxiliary = {
        path.relative_to(BASE_EXPORTS).as_posix(): path.read_bytes()
        for path in sorted(BASE_EXPORTS.rglob("*"))
        if path.is_file()
    }
    return records, auxiliary, manifest


def load_context() -> dict[str, Any]:
    ready = bind_ready_inputs()
    contract = load_terminal_contract()
    raw = {role: require(LANE / item["path"], item) for role, item in contract["inputs"].items()}
    raw.update({role: require(LANE / item["path"], item) for role, item in ready.items()})
    source_closure = json.loads(raw["source_closure"])
    main_authority = raw["main_authority"]
    section_meta = source_closure["boundary"]["lexical_section_to_next_section"]
    section_start = int(section_meta["byte_start_zero_based"])
    section_end = int(section_meta["byte_end_exclusive"])
    section_source = main_authority[section_start:section_end]
    if {"bytes": len(section_source), "sha256": sha256_bytes(section_source)} != {
        "bytes": int(section_meta["bytes"]), "sha256": section_meta["sha256"]
    }:
        raise RuntimeError("B015 authority section slice changed")
    main_fragment = raw["main_fragment"]
    eoce_fragment = raw["eoce_fragment"]
    answer_fragment = raw["public_answers_fragment"]
    data_fragment = raw["data_appendix_fragment"]
    assembled_offsets = {
        "main": unique_offset(raw["assembled_main"], main_fragment, "assembled main fragment"),
        "eoce": unique_offset(raw["assembled_eoce"], eoce_fragment, "assembled EoCE fragment"),
        "answers": unique_offset(raw["assembled_public_answers"], answer_fragment, "assembled answer fragment"),
        "data": unique_offset(raw["assembled_data_appendix"], data_fragment, "assembled data fragment"),
    }
    answer_meta = source_closure["public_answer_closure"]["slice"]
    answer_source = raw["public_answers_authority"][int(answer_meta["byte_start_zero_based"]):int(answer_meta["byte_end_exclusive"])]
    if {"bytes": len(answer_source), "sha256": sha256_bytes(answer_source)} != {
        "bytes": int(answer_meta["bytes"]), "sha256": answer_meta["sha256"]
    }:
        raise RuntimeError("B015 public-answer authority slice changed")
    data_meta = source_closure["data_appendix_closure"]["source_slice"]
    data_source = raw["data_authority"][int(data_meta["byte_start_zero_based"]):int(data_meta["byte_end_exclusive"])]
    if {"bytes": len(data_source), "sha256": sha256_bytes(data_source)} != {
        "bytes": int(data_meta["bytes"]), "sha256": data_meta["sha256"]
    }:
        raise RuntimeError("B015 data authority slice changed")
    source_struct = structural_spans(section_source)
    target_struct = structural_spans(main_fragment)
    if [(row["kind"], row["number"]) for row in source_struct] != [(row["kind"], row["number"]) for row in target_struct]:
        raise RuntimeError("B015 source/target structural segmentation differs")
    source_subsections = subsection_spans(section_source)
    target_subsections = subsection_spans(main_fragment)
    source_eoce = marker_spans(raw["eoce_authority"], sorted(EOCE))
    target_eoce = marker_spans(eoce_fragment, sorted(EOCE))
    source_answers = marker_spans(answer_source, list(PUBLIC_ANSWERS))
    target_answers = marker_spans(answer_fragment, list(PUBLIC_ANSWERS))
    return {
        "contract": contract,
        "ready": ready,
        "raw": raw,
        "source_closure": source_closure,
        "section_start": section_start,
        "section_source": section_source,
        "answer_source_start": int(answer_meta["byte_start_zero_based"]),
        "answer_source": answer_source,
        "data_source_start": int(data_meta["byte_start_zero_based"]),
        "data_source": data_source,
        "assembled_offsets": assembled_offsets,
        "source_struct": source_struct,
        "target_struct": target_struct,
        "source_subsections": source_subsections,
        "target_subsections": target_subsections,
        "source_eoce": source_eoce,
        "target_eoce": target_eoce,
        "source_answers": source_answers,
        "target_answers": target_answers,
    }


def common_fields(resource_id: str, edition_id: str, rights_ids: list[str], **overrides: Any) -> dict[str, Any]:
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


def build_records() -> tuple[dict[str, list[dict[str, Any]]], dict[str, bytes], dict[str, Any]]:
    records, auxiliary, base_manifest = load_base_records()
    context = load_context()
    raw = context["raw"]
    contract = context["contract"]
    resource = one(records, "resources", "r011/resource/openintro-statistics")
    edition = one(records, "editions", "r011/edition/fee25091")
    resource_id, edition_id = resource["id"], edition["id"]
    upstream_rights = one(records, "rights", "r011/rights/upstream-cc-by-sa-3.0")["id"]
    o001_rights = one(records, "rights", "r011/rights/o001-original-companion-planned")["id"]
    package_rights = one(records, "rights", "r011/rights/openintro-r-package-gpl-3")["id"]
    chapter = one(records, "units", "r011/unit/source-label/ch_distributions")
    predecessor = one(records, "units", "r011/unit/source-label/normalDist")
    prerequisite_unit = one(records, "units", "r011/unit/source-label/randomVariablesSection")
    package_asset = one(records, "assets", "r011/asset/b014/virtual-openintro-package-dataset-COL")

    localized_rights = backend_record(
        "rights",
        "r011/rights/b015-localized-section-text-and-figure",
        **common_fields(
            resource_id, edition_id, [],
            parent_id=resource_id,
            order=len(records["rights"]) + 1,
            source_path="qa/b015-assets/R011-B015_ASSET_RIGHTS_CLOSURE.json",
            source_sha256=READY_INPUTS["asset_rights_closure"][2],
            locale="zxx",
            translation_state="visually_checked",
            component_scope="B015 Indonesian Section 4.2, EoCE 11--16, public answers 11/13/15, data appendix entry, and localized geometricDist70 R/PDF derivative.",
            license_expression="CC-BY-SA-3.0",
            verification_status="verified by exact source, translation, rights, build, asset and visual receipts",
            attribution="OpenIntro Statistics source authors; Indonesian derivative changes identified by R011-B015.",
            change_notice="Five explicit source corrections and two localized figure strings; formulas, numeric geometry and source topology preserved.",
            non_endorsement="No author, institution, publisher, brand owner, or tool-provider endorsement implied.",
            publication_effect="Isolated B015 backend stage only; admission and publication are separate transactions.",
        ),
    )
    records["rights"].append(localized_rights)
    localized_rights_ids = [upstream_rights, localized_rights["id"]]

    main_path = "ch_distributions/TeX/ch_distributions.tex"
    eoce_path = "ch_distributions/TeX/geometric_distribution.tex"
    answer_path = "extraTeX/eoceSolutions/eoceSolutions.tex"
    data_path = "extraTeX/data/data.tex"
    target_paths = {
        "main": contract["inputs"]["assembled_main"]["path"],
        "eoce": contract["inputs"]["assembled_eoce"]["path"],
        "answers": contract["inputs"]["assembled_public_answers"]["path"],
        "data": contract["inputs"]["assembled_data_appendix"]["path"],
    }

    section_source_meta = span_meta(
        raw["main_authority"],
        context["section_start"],
        context["section_start"] + len(context["section_source"]),
    )
    section_target_meta = span_meta(
        raw["assembled_main"],
        context["assembled_offsets"]["main"],
        context["assembled_offsets"]["main"] + len(raw["main_fragment"]),
    )
    section = backend_record(
        "unit", SEMANTIC_BLUEPRINT["section"],
        **common_fields(
            resource_id, edition_id, localized_rights_ids,
            parent_id=chapter["id"], order=2,
            source_local_ids=[BOUNDARY_ID, "geomDist"],
            source_path=main_path, source_span=schema_span(section_source_meta), source_sha256=section_source_meta["sha256"],
            locale="en", translation_state="visually_checked", unit_type="section",
            title="Geometric distribution", answer_availability=None, authoring_mode=None,
            gap_reason=None, source_solution_used=None,
            prerequisite_ids=[prerequisite_unit["id"]],
            target_identity_status="terminal_contract_bound",
            target_path=target_paths["main"], target_span=section_target_meta,
            target_sha256=section_target_meta["sha256"],
        ),
    )
    records["units"].append(section)

    subsection_units: list[dict[str, Any]] = []
    for index, (source_row, target_row, stable_key) in enumerate(zip(
        context["source_subsections"], context["target_subsections"], SEMANTIC_BLUEPRINT["subsections"]
    ), 1):
        source_meta = rebase_span(source_row["span"], raw["main_authority"], context["section_start"])
        target_meta = rebase_span(target_row["span"], raw["assembled_main"], context["assembled_offsets"]["main"])
        row = backend_record(
            "unit", stable_key,
            **common_fields(
                resource_id, edition_id, localized_rights_ids,
                parent_id=section["id"], order=index * 100,
                source_path=main_path, source_span=schema_span(source_meta), source_sha256=source_meta["sha256"],
                locale="en", translation_state="visually_checked", unit_type="subsection",
                title=f"Section 4.2 source-topology subsection {index}", prerequisite_ids=[],
                answer_availability=None, authoring_mode=None, gap_reason=None, source_solution_used=None,
                target_identity_status="terminal_contract_bound", target_path=target_paths["main"],
                target_span=target_meta, target_sha256=target_meta["sha256"],
            ),
        )
        records["units"].append(row)
        subsection_units.append(row)

    example_keys = SEMANTIC_BLUEPRINT["worked_examples"]
    example_labels = ["waitForDeductible", "insureFirstSuccessInLT4", "carInsure08DrawOne"]
    example_units: dict[int, dict[str, Any]] = {}
    guided_units: dict[int, dict[str, Any]] = {}
    guided_solutions: dict[int, dict[str, Any]] = {}
    source_by_kind = {(row["kind"], row["number"]): row for row in context["source_struct"]}
    target_by_kind = {(row["kind"], row["number"]): row for row in context["target_struct"]}
    for number in range(1, 4):
        for kind, stable_key, unit_type, order, title, availability in (
            ("worked_example", example_keys[number - 1], "worked_example", 1000 + number * 10, f"Section 4.2 worked example {number}", None),
            ("guided_exercise", SEMANTIC_BLUEPRINT["guided_exercises"][number - 1], "guided_exercise", 2000 + number * 10, f"Section 4.2 guided exercise {number}", "inline_public_feedback"),
            ("guided_inline_answer", SEMANTIC_BLUEPRINT["guided_inline_answers"][number - 1], "solution", 1, f"Inline public answer to Section 4.2 guided exercise {number}", "public_inline"),
        ):
            source_meta = rebase_span(source_by_kind[(kind, number)]["span"], raw["main_authority"], context["section_start"])
            target_meta = rebase_span(target_by_kind[(kind, number)]["span"], raw["assembled_main"], context["assembled_offsets"]["main"])
            parent_id = guided_units[number]["id"] if kind == "guided_inline_answer" else section["id"]
            local_ids = [BOUNDARY_ID]
            if kind == "worked_example":
                local_ids.append(example_labels[number - 1])
            row = backend_record(
                "unit", stable_key,
                **common_fields(
                    resource_id, edition_id, localized_rights_ids,
                    parent_id=parent_id, order=order, source_local_ids=local_ids,
                    source_path=main_path, source_span=schema_span(source_meta), source_sha256=source_meta["sha256"],
                    locale="en", translation_state="visually_checked", unit_type=unit_type,
                    title=title, prerequisite_ids=[], answer_availability=availability,
                    authoring_mode=None, gap_reason=None, source_solution_used=None,
                    target_identity_status="terminal_contract_bound", target_path=target_paths["main"],
                    target_span=target_meta, target_sha256=target_meta["sha256"],
                ),
            )
            records["units"].append(row)
            if kind == "worked_example": example_units[number] = row
            elif kind == "guided_exercise": guided_units[number] = row
            else: guided_solutions[number] = row

    exercise_units: dict[int, dict[str, Any]] = {}
    public_solution_units: dict[int, dict[str, Any]] = {}
    gap_units: dict[int, dict[str, Any]] = {}
    for number, label in EOCE.items():
        source_meta = context["source_eoce"][number]
        target_meta = rebase_span(context["target_eoce"][number], raw["assembled_eoce"], context["assembled_offsets"]["eoce"])
        row = backend_record(
            "unit", f"r011/unit/exercise/4.{number}/{label}",
            **common_fields(
                resource_id, edition_id, localized_rights_ids,
                parent_id=section["id"], order=3000 + number,
                source_local_ids=[BOUNDARY_ID, f"4.{number}", label],
                source_path=eoce_path, source_span=schema_span(source_meta), source_sha256=source_meta["sha256"],
                locale="en", translation_state="visually_checked", unit_type="exercise",
                title=f"Exercise 4.{number}", prerequisite_ids=[],
                answer_availability="public_appendix" if number in PUBLIC_ANSWERS else "restricted_not_accessed",
                authoring_mode=None if number in PUBLIC_ANSWERS else "independent_original_required",
                gap_reason=None if number in PUBLIC_ANSWERS else "no_public_answer_upstream",
                source_solution_used=False if number in O001_GAPS else None,
                target_identity_status="terminal_contract_bound", target_path=target_paths["eoce"],
                target_span=target_meta, target_sha256=target_meta["sha256"],
            ),
        )
        records["units"].append(row)
        exercise_units[number] = row
        if number in PUBLIC_ANSWERS:
            source_answer_meta = rebase_span(context["source_answers"][number], raw["public_answers_authority"], context["answer_source_start"])
            target_answer_meta = rebase_span(context["target_answers"][number], raw["assembled_public_answers"], context["assembled_offsets"]["answers"])
            solution = backend_record(
                "unit", f"r011/unit/solution/4.{number}",
                **common_fields(
                    resource_id, edition_id, localized_rights_ids,
                    parent_id=row["id"], order=1, source_local_ids=[BOUNDARY_ID, f"4.{number}"],
                    source_path=answer_path, source_span=schema_span(source_answer_meta), source_sha256=source_answer_meta["sha256"],
                    locale="en", translation_state="visually_checked", unit_type="solution",
                    title=f"Public solution to exercise 4.{number}", prerequisite_ids=[],
                    answer_availability="public_upstream", authoring_mode=None, gap_reason=None, source_solution_used=None,
                    target_identity_status="terminal_contract_bound", target_path=target_paths["answers"],
                    target_span=target_answer_meta, target_sha256=target_answer_meta["sha256"],
                ),
            )
            records["units"].append(solution)
            public_solution_units[number] = solution
        else:
            gap = backend_record(
                "unit", f"r011/unit/o001-gap/4.{number}",
                **common_fields(
                    resource_id, edition_id, [o001_rights], parent_id=row["id"], order=1,
                    locale="en", translation_state="queued", unit_type="companion_gap",
                    title=f"O001 mastery-companion answer gap for exercise 4.{number}", prerequisite_ids=[],
                    answer_availability="restricted_not_accessed", authoring_mode="independent_original_required",
                    gap_reason="no_public_answer_upstream", source_solution_used=False,
                    target_identity_status="explicit_o001_gap", target_path=None, target_span=None, target_sha256=None,
                ),
            )
            records["units"].append(gap)
            gap_units[number] = gap

    data_source_meta = span_meta(raw["data_authority"], context["data_source_start"], context["data_source_start"] + len(context["data_source"]))
    data_target_meta = span_meta(raw["assembled_data_appendix"], context["assembled_offsets"]["data"], context["assembled_offsets"]["data"] + len(raw["data_appendix_fragment"]))
    data_unit = backend_record(
        "unit", SEMANTIC_BLUEPRINT["data_appendix"],
        **common_fields(
            resource_id, edition_id, localized_rights_ids, parent_id=section["id"], order=4000,
            source_local_ids=[BOUNDARY_ID, "geomDist"], source_path=data_path,
            source_span=schema_span(data_source_meta), source_sha256=data_source_meta["sha256"],
            locale="en", translation_state="visually_checked", unit_type="data_appendix_entry",
            title="Section 4.2 data-provenance appendix entry", prerequisite_ids=[], answer_availability=None,
            authoring_mode=None, gap_reason=None, source_solution_used=None,
            target_identity_status="terminal_contract_bound", target_path=target_paths["data"],
            target_span=data_target_meta, target_sha256=data_target_meta["sha256"],
        ),
    )
    records["units"].append(data_unit)

    segment_pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []

    def add_segment_pair(
        stable_suffix: str,
        unit: dict[str, Any],
        order: int,
        kind: str,
        source_path: str,
        source_full: bytes,
        source_meta: dict[str, Any],
        target_path: str,
        target_full: bytes,
        target_meta: dict[str, Any],
    ) -> None:
        segment = backend_record(
            "segment", f"r011/segment/b015/{stable_suffix}",
            **common_fields(
                resource_id, edition_id, [upstream_rights], parent_id=unit["id"], order=order,
                source_path=source_path, source_span=schema_span(source_meta), source_sha256=source_meta["sha256"],
                locale="en", translation_state="source_frozen", unit_id=unit["id"],
                segment_kind=kind, source_locale="en",
                source_text=source_full[int(source_meta["byte_start"]):int(source_meta["byte_end_exclusive"])].decode("utf-8"),
                target_locales=["id-ID"], protected_tokens=[],
            ),
        )
        localization = backend_record(
            "localization", f"r011/localization/id-ID/b015/{stable_suffix}",
            **common_fields(
                resource_id, edition_id, localized_rights_ids, parent_id=segment["id"], order=order,
                source_path=source_path, source_span=schema_span(source_meta), source_sha256=source_meta["sha256"],
                locale="id-ID", translation_state="visually_checked", unit_id=unit["id"],
                source_segment_id=segment["id"], source_locale="en", target_locale="id-ID",
                target_path=target_path, target_span=target_meta, target_sha256=target_meta["sha256"],
                target_text=target_full[int(target_meta["byte_start"]):int(target_meta["byte_end_exclusive"])].decode("utf-8"),
                source_protected_tokens=[], target_protected_tokens=[], protected_tokens=[],
                protected_token_delta={"authorized": True, "reason": "Exact B015 topology/math/translation/build/visual receipts."},
                terminology_bindings=list(TERM_CONCEPT_KEYS), translation_provenance="OpenAI Codex gpt-5.6-sol, Ultra",
                candidate_validation_receipt="qa/b015-build/R011-B015_SOURCE_QA.json",
                target_identity_status="terminal_contract_bound",
            ),
        )
        records["segments"].append(segment)
        records["localizations"].append(localization)
        segment_pairs.append((segment, localization))

    for index, (source_row, target_row) in enumerate(zip(context["source_struct"], context["target_struct"]), 1):
        kind, number = source_row["kind"], int(source_row["number"])
        if kind == "section_prose": unit = section
        elif kind == "worked_example": unit = example_units[number]
        elif kind == "guided_exercise": unit = guided_units[number]
        elif kind == "guided_inline_answer": unit = guided_solutions[number]
        else: raise RuntimeError(f"unexpected B015 segment kind {kind}")
        source_meta = rebase_span(source_row["span"], raw["main_authority"], context["section_start"])
        target_meta = rebase_span(target_row["span"], raw["assembled_main"], context["assembled_offsets"]["main"])
        add_segment_pair(
            f"main-{index:03d}", unit, index, kind, main_path, raw["main_authority"], source_meta,
            target_paths["main"], raw["assembled_main"], target_meta,
        )

    for number in sorted(EOCE):
        source_meta = context["source_eoce"][number]
        target_meta = rebase_span(context["target_eoce"][number], raw["assembled_eoce"], context["assembled_offsets"]["eoce"])
        add_segment_pair(
            f"eoce-4-{number}", exercise_units[number], number, "exercise", eoce_path,
            raw["eoce_authority"], source_meta, target_paths["eoce"], raw["assembled_eoce"], target_meta,
        )
    for number in PUBLIC_ANSWERS:
        source_meta = rebase_span(context["source_answers"][number], raw["public_answers_authority"], context["answer_source_start"])
        target_meta = rebase_span(context["target_answers"][number], raw["assembled_public_answers"], context["assembled_offsets"]["answers"])
        add_segment_pair(
            f"answer-4-{number}", public_solution_units[number], number, "public_answer", answer_path,
            raw["public_answers_authority"], source_meta, target_paths["answers"], raw["assembled_public_answers"], target_meta,
        )
    add_segment_pair(
        "data-geomdist", data_unit, 1, "data_appendix_entry", data_path, raw["data_authority"], data_source_meta,
        target_paths["data"], raw["assembled_data_appendix"], data_target_meta,
    )

    term_rows = list(csv.DictReader(io.StringIO(raw["controlled_terms"].decode("utf-8"), newline=""), delimiter="\t"))
    if len(term_rows) != len(TERM_CONCEPT_KEYS):
        raise RuntimeError("controlled-term row count changed")
    concept_by_key = {row["stable_key"]: row for row in records["concepts"]}
    concept_rows_for_terms: dict[str, dict[str, Any]] = {}
    for index, (decision_code, concept_key) in enumerate(TERM_CONCEPT_KEYS.items(), 1):
        if concept_key not in concept_by_key:
            concept = backend_record(
                "concept", concept_key,
                **common_fields(
                    resource_id, edition_id, [upstream_rights], order=index,
                    source_local_ids=[BOUNDARY_ID, decision_code], source_path=main_path,
                    source_span=schema_span(section_source_meta), source_sha256=section_source_meta["sha256"],
                    locale="zxx", translation_state="source_frozen",
                    semantic_code=decision_code, definition=f"Locale-neutral B015 semantic concept {decision_code}.",
                    preferred_source_term=term_rows[index - 1]["source_term"],
                ),
            )
            records["concepts"].append(concept)
            concept_by_key[concept_key] = concept
        concept_rows_for_terms[decision_code] = concept_by_key[concept_key]
    term_records: dict[str, dict[str, Any]] = {}
    for index, ((decision_code, _concept_key), spec) in enumerate(zip(TERM_CONCEPT_KEYS.items(), term_rows), 1):
        variants = [] if spec["accepted_synonyms"] in ("", "-") else [item.strip() for item in spec["accepted_synonyms"].split(";") if item.strip()]
        term = backend_record(
            "term", f"r011/term/id-ID/b015/TM{index:03d}",
            **common_fields(
                resource_id, edition_id, localized_rights_ids,
                parent_id=concept_rows_for_terms[decision_code]["id"], order=index,
                source_local_ids=[BOUNDARY_ID, decision_code], source_path="qa/b015-terminology/R011-B015_CONTROLLED_TERMS.tsv",
                source_sha256=READY_INPUTS["controlled_terms"][2], locale="id-ID", translation_state="language_reviewed",
                concept_id=concept_rows_for_terms[decision_code]["id"], source_term=spec["source_term"],
                target_term=spec["preferred_id-ID"], variants=variants, rejected_forms=[],
                scope="statistics / Chapter 4 Section 4.2", register="academic",
                evidence=spec["evidence"], decision=spec["use_in_B015"], decision_reason=spec["evidence"],
                glossary_lock_status="bound_to_terminal_b015_candidate", internal_witness_bytes_excluded=True,
                field_source_metadata={"model": "OpenAI Codex gpt-5.6-sol, Ultra", "internal_witness_bytes_bundled": False},
            ),
        )
        records["terms"].append(term)
        term_records[decision_code] = term

    asset_specs = [
        (
            "r011/asset/b015/source-r/geometricDist70", "source_r_producer", "source_figure_r",
            "text/x-r-source", "zxx", [upstream_rights, package_rights], "source_frozen", section["id"], 1,
        ),
        (
            "r011/asset/b015/source-pdf/geometricDist70", "source_figure_pdf", "source_figure_pdf",
            "application/pdf", "en", [upstream_rights], "source_frozen", section["id"], 2,
        ),
        (
            "r011/asset/b015/localized-r/geometricDist70", "localized_r_producer", "localized_figure_r",
            "text/x-r-source", "id-ID", [upstream_rights, localized_rights["id"], package_rights], "structurally_verified", section["id"], 3,
        ),
        (
            "r011/asset/b015/localized-pdf/geometricDist70", "localized_figure_pdf", "localized_figure_pdf",
            "application/pdf", "id-ID", localized_rights_ids, "visually_checked", section["id"], 4,
        ),
    ]
    asset_records: dict[str, dict[str, Any]] = {}
    for stable_key, kind, role, media_type, locale, rights, state, parent_id, order in asset_specs:
        item = context["ready"].get(role) or contract["inputs"][role]
        asset = backend_record(
            "asset", stable_key,
            **common_fields(
                resource_id, edition_id, rights, parent_id=parent_id, order=order,
                source_local_ids=[BOUNDARY_ID, "geometricDist70"], source_path=item["path"], source_sha256=item["sha256"],
                locale=locale, translation_state=state, asset_kind=kind, path=item["path"],
                bytes=int(item["bytes"]), sha256=item["sha256"], media_type=media_type,
                dependencies=["R package openintro", "package dataset COL"] if role.endswith("_r") else [],
                numeric_geometry_preserved=True if role.startswith("localized_") else None,
                reader_visible_strings_localized=True if role.startswith("localized_") else None,
            ),
        )
        records["assets"].append(asset)
        asset_records[role] = asset

    corrections: dict[str, dict[str, Any]] = {}
    for index, spec in enumerate(context["source_closure"]["source_corrections"], 1):
        code = f"B015-SC{index:03d}"
        if spec["id"] != code:
            raise RuntimeError("B015 correction identity order changed")
        row = backend_record(
            "correction", f"r011/correction/b015/{code}",
            **common_fields(
                resource_id, edition_id, localized_rights_ids,
                parent_id=section["id"], order=index, source_local_ids=[BOUNDARY_ID, code],
                locale="id-ID", translation_state="language_reviewed",
                affected_id=section["id"], category="source_correction", correction_type="localized_source_correction",
                source_claim=spec["source_text"], proposed_correction=spec["correction"],
                summary=f"{code}: explicit derivative-scoped source correction",
                rationale=spec.get("evidence", spec["handling"]), evidence=spec["source_location"],
                disposition="applied_in_terminal_b015_candidate", confidence="high",
                upstream_report_disposition="eligible_for_single_deduplicated_post-corpus_report",
            ),
        )
        records["corrections"].append(row)
        corrections[code] = row

    evidence_inputs: dict[str, tuple[str, bytes]] = {}
    for role, item in sorted(context["ready"].items()):
        evidence_inputs[f"ready-{role}"] = (item["path"], raw[role])
    for role, item in sorted(contract["inputs"].items()):
        evidence_inputs[f"terminal-{role}"] = (item["path"], raw[role])
    spec_path = INTERLANGUAGE_ROOT / INTEROPERABILITY_SPEC["path"]
    evidence_inputs["interoperability-spec"] = (INTEROPERABILITY_SPEC["path"], require(spec_path, INTEROPERABILITY_SPEC))
    local_tool_paths = {
        "generator": SCRIPT_PATH,
        "validator": LANE / "scripts" / "validate_backend_b015.py",
        "terminal-contract": TERMINAL_CONTRACT,
        "preparation-receipt": PREP_ROOT / "R011-B015_BACKEND_PREPARATION_RECEIPT.json",
    }
    for role, path in local_tool_paths.items():
        evidence_inputs[role] = (path.relative_to(LANE).as_posix(), path.read_bytes())

    artifact_records: dict[str, dict[str, Any]] = {}
    for order, (role, (source_path_value, artifact_raw)) in enumerate(sorted(evidence_inputs.items()), 1):
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(source_path_value).name)
        evidence_path = f"evidence/b015/{role}-{safe_name}"
        if evidence_path in auxiliary:
            raise RuntimeError(f"duplicate B015 evidence path {evidence_path}")
        auxiliary[evidence_path] = artifact_raw
        artifact = backend_record(
            "artifact", f"r011/artifact/b015/{role}",
            **common_fields(
                resource_id, edition_id, [], parent_id=edition_id, order=order,
                locale="zxx", translation_state="built", artifact_kind=role,
                path=evidence_path, bytes=len(artifact_raw), sha256=sha256_bytes(artifact_raw),
                result="exact terminal B015 input or isolated backend evidence",
                toolchain=None, build_receipt=contract["inputs"]["build_receipt"]["sha256"] if role == "terminal-reader_pdf" else None,
                provenance="OpenAI Codex gpt-5.6-sol, Ultra",
            ),
        )
        records["artifacts"].append(artifact)
        artifact_records[role] = artifact

    qa_specs = [
        ("base-preservation", "base_preservation", "backend/exports/manifest.json", edition_id, "Exact B014 manifest, inventory and every canonical record byte are preserved."),
        ("source", "source", contract["inputs"]["source_qa"]["path"], section["id"], "Exact authority, overlay and source closure passed."),
        ("translation", "translation", context["ready"]["translation_qa"]["path"], section["id"], "Complete natural id-ID translation and coverage passed."),
        ("terminology", "terminology", context["ready"]["terminology_qa"]["path"], section["id"], "Controlled terminology decisions are exact and bound."),
        ("asset-localization", "asset_localization", contract["inputs"]["localized_asset_qa"]["path"], asset_records["localized_figure_pdf"]["id"], "Localized R/PDF determinism, text and geometry passed."),
        ("rights", "rights", context["ready"]["asset_rights_closure"]["path"], localized_rights["id"], "Book, derivative and package dependency rights closed."),
        ("mathematics", "mathematics", contract["inputs"]["source_qa"]["path"], section["id"], "Formula and numeric semantics passed exact normalization checks."),
        ("topology", "topology", contract["inputs"]["source_qa"]["path"], section["id"], "Hierarchy, labels, references, exercises and answer topology passed."),
        ("build", "build", contract["inputs"]["build_receipt"]["path"], section["id"], "Two deterministic reader replays passed."),
        ("visual", "visual", contract["inputs"]["visual_qa"]["path"], section["id"], "Bounded original-detail visual QA passed with zero defects."),
        ("corrections", "corrections", context["ready"]["source_closure"]["path"], section["id"], "Five explicit localized source corrections are recorded."),
        ("interoperability", "interoperability", INTEROPERABILITY_SPEC["path"], edition_id, "All required typed entities and deterministic views are emitted."),
        ("isolation", "isolation", TERMINAL_CONTRACT.relative_to(LANE).as_posix(), edition_id, "No live backend, source, control, release, Git, network or publication mutation."),
    ]
    qa_records: dict[str, dict[str, Any]] = {}
    artifact_by_source_path = {
        source_path_value: artifact_records[role]
        for role, (source_path_value, _raw_value) in evidence_inputs.items()
    }
    for order, (suffix, qa_type, witness_path, subject_id, detail) in enumerate(qa_specs, 1):
        witness_artifact = artifact_by_source_path.get(witness_path)
        qa = backend_record(
            "qa_event", f"r011/qa/b015/{suffix}",
            **common_fields(
                resource_id, edition_id, [], parent_id=edition_id, order=order,
                locale="zxx", translation_state="visually_checked", qa_type=qa_type,
                result="passed", subject_id=subject_id, witness_path=witness_path,
                witness_artifact_id=witness_artifact["id"] if witness_artifact else None,
                detail=detail, provenance="OpenAI Codex gpt-5.6-sol, Ultra",
            ),
        )
        records["qa_events"].append(qa)
        qa_records[suffix] = qa

    relation_counters: dict[str, int] = {}

    def add_relation(kind: str, from_id: str, to_id: str, qualifier: str, order: int | None = None) -> None:
        relation_counters[kind] = relation_counters.get(kind, 0) + 1
        serial = relation_counters[kind]
        records["relations"].append(backend_record(
            "relation", f"r011/relation/b015/{kind}/{serial:04d}",
            **common_fields(
                resource_id, edition_id, [], order=order if order is not None else serial,
                locale="zxx", translation_state="structurally_verified",
                relation_type=kind, from_id=from_id, to_id=to_id, qualifier=qualifier,
            ),
        ))

    new_units = [row for row in records["units"] if row.get("boundary_id") == BOUNDARY_ID]
    for row in new_units:
        if row.get("parent_id"):
            add_relation("contains", row["parent_id"], row["id"], "source hierarchy", row.get("order"))
    add_relation("precedes", predecessor["id"], section["id"], "source section order", 2)
    add_relation("prerequisite", prerequisite_unit["id"], section["id"], "reader-facing unit prerequisite", 1)
    for source_key, target_key in SEMANTIC_BLUEPRINT["concept_prerequisites"]:
        source_concept = concept_by_key.get(source_key)
        target_concept = concept_by_key.get(target_key)
        if source_concept is None or target_concept is None:
            raise RuntimeError(f"missing concept prerequisite endpoint {source_key} -> {target_key}")
        add_relation("prerequisite", source_concept["id"], target_concept["id"], "locale-neutral concept prerequisite")
    for concept in sorted(
        {row["id"]: row for row in concept_rows_for_terms.values()}.values(),
        key=lambda row: row["id"],
    ):
        add_relation("covers", section["id"], concept["id"], "B015 controlled concept coverage")
    for code, term in term_records.items():
        add_relation("lexicalizes", concept_rows_for_terms[code]["id"], term["id"], "id-ID controlled terminology")
    for segment, localization in segment_pairs:
        add_relation("unit_contains_segment", segment["unit_id"], segment["id"], "semantic segmentation", segment["order"])
        add_relation("localizes", segment["id"], localization["id"], "en to id-ID exact terminal mapping", localization["order"])
    for number in range(1, 4):
        add_relation("answers", guided_solutions[number]["id"], guided_units[number]["id"], "inline public guided answer", number)
    for number in PUBLIC_ANSWERS:
        add_relation("answers", public_solution_units[number]["id"], exercise_units[number]["id"], "public upstream answer", number)
    for number in O001_GAPS:
        add_relation("requires_companion_answer", exercise_units[number]["id"], gap_units[number]["id"], "no public upstream answer; restricted solution not accessed", number)
    for role, asset in asset_records.items():
        add_relation("uses_asset", section["id"], asset["id"], role)
    add_relation("produces", asset_records["source_figure_r"]["id"], asset_records["source_figure_pdf"]["id"], "adjacent source producer")
    add_relation("produces", asset_records["localized_figure_r"]["id"], asset_records["localized_figure_pdf"]["id"], "localized deterministic producer")
    add_relation("depends_on", asset_records["source_figure_r"]["id"], package_asset["id"], "openintro COL/myPDF dependency")
    add_relation("depends_on", asset_records["localized_figure_r"]["id"], package_asset["id"], "openintro COL/myPDF dependency")
    add_relation("adapts", asset_records["localized_figure_r"]["id"], asset_records["source_figure_r"]["id"], "only two approved reader-visible strings changed")
    add_relation("adapts", asset_records["localized_figure_pdf"]["id"], asset_records["source_figure_pdf"]["id"], "numeric vector geometry preserved")
    for correction in corrections.values():
        add_relation("corrects", correction["id"], section["id"], "explicit derivative-scoped correction")
    add_relation("governs", localized_rights["id"], section["id"], "localized B015 derivative rights")
    for qa in qa_records.values():
        add_relation("validates", qa["id"], qa["subject_id"], qa["qa_type"])
    for artifact in artifact_records.values():
        add_relation("documents", artifact["id"], edition_id, artifact["artifact_kind"])

    return records, auxiliary, {
        "base_manifest": base_manifest,
        "base_record_count": BASE_RECORD_COUNT,
        "section_id": section["id"],
        "localized_rights_id": localized_rights["id"],
        "new_record_counts": {
            name: sum(row.get("boundary_id") == BOUNDARY_ID for row in rows)
            for name, rows in sorted(records.items())
        },
        "relation_counts": dict(sorted(relation_counters.items())),
        "contract": contract,
    }


def build_views(records: dict[str, list[dict[str, Any]]], columns: dict[str, list[str]]) -> dict[str, bytes]:
    resources = {row["id"]: row for row in records["resources"]}
    localizations = {row["source_segment_id"]: row for row in records["localizations"]}
    resource_rows = []
    for edition in records["editions"]:
        resource = resources[edition["resource_id"]]
        resource_rows.append({
            "resource_id": resource["id"], "resource_code": resource["resource_code"],
            "work_title": resource["work_title"], "edition_id": edition["id"],
            "repository": edition["repository"], "branch_observed": edition["branch_observed"],
            "commit": edition["commit"], "tree": edition["tree"],
            "license_expression": "CC-BY-SA-3.0", "source_format": edition["source_format"],
            "build_entrypoint": edition["build_entrypoint"],
        })
    unit_rows = []
    for row in sorted(records["units"], key=lambda item: item["id"]):
        span = row.get("source_span") or {}
        unit_rows.append({
            "id": row["id"], "parent_id": row.get("parent_id"), "order": row.get("order"),
            "unit_type": row["unit_type"], "source_local_ids": row.get("source_local_ids", []),
            "source_path": row.get("source_path"), "line_start": span.get("line_start"),
            "line_end": span.get("line_end"), "source_sha256": row.get("source_sha256"),
            "translation_state": row.get("translation_state"), "rights_component_ids": row.get("rights_component_ids", []),
        })
    segment_rows = []
    for segment in sorted(records["segments"], key=lambda item: item["id"]):
        localization = localizations[segment["id"]]
        source_span, target_span = segment["source_span"], localization["target_span"]
        segment_rows.append({
            "segment_id": segment["id"], "unit_id": segment["unit_id"], "order": segment["order"],
            "segment_kind": segment["segment_kind"], "source_locale": segment["source_locale"],
            "source_path": segment["source_path"], "line_start": source_span["line_start"],
            "line_end": source_span["line_end"], "source_sha256": segment["source_sha256"],
            "target_locale": localization["target_locale"], "target_path": localization["target_path"],
            "target_line_start": target_span["line_start"], "target_line_end": target_span["line_end"],
            "target_sha256": localization["target_sha256"], "translation_state": localization["translation_state"],
            "target_text": localization["target_text"], "rights_component_ids": segment["rights_component_ids"],
        })
    answer_relations = {row["to_id"]: row["from_id"] for row in records["relations"] if row["relation_type"] == "answers"}
    gap_relations = {row["from_id"]: row["to_id"] for row in records["relations"] if row["relation_type"] == "requires_companion_answer"}
    exercise_rows = [{
        "exercise_id": row["id"], "source_local_ids": row["source_local_ids"],
        "answer_availability": row["answer_availability"], "answer_id": answer_relations.get(row["id"]),
        "o001_gap_id": gap_relations.get(row["id"]), "source_path": row["source_path"],
        "translation_state": row["translation_state"], "rights_component_ids": row["rights_component_ids"],
    } for row in sorted((item for item in records["units"] if item["unit_type"] == "exercise"), key=lambda item: item["id"])]
    rows_by_view: dict[str, list[dict[str, Any]]] = {
        "views/resource_editions.csv": resource_rows,
        "views/unit_hierarchy.csv": unit_rows,
        "views/relations.csv": [
            {key: row.get(key) for key in columns["views/relations.csv"]}
            for row in sorted(records["relations"], key=lambda item: item["id"])
        ],
        "views/segments_locale.csv": segment_rows,
        "views/terminology.csv": [
            {key: row.get(key) for key in columns["views/terminology.csv"]}
            for row in sorted(records["terms"], key=lambda item: item["id"])
        ],
        "views/exercises_answers.csv": exercise_rows,
        "views/rights_components.csv": [{
            "id": row["id"], "component_scope": row["component_scope"],
            "license_expression": row["license_expression"], "verification_status": row["verification_status"],
            "attribution": row["attribution"], "change_notice": row["change_notice"],
            "non_endorsement": row["non_endorsement"], "publication_effect": row["publication_effect"],
        } for row in sorted(records["rights"], key=lambda item: item["id"])],
        "views/corrections.csv": [{
            "id": row["id"], "affected_id": row["affected_id"], "category": row["category"],
            "summary": row["proposed_correction"], "disposition": row["upstream_report_disposition"],
            "confidence": row["confidence"], "status": row["status"],
        } for row in sorted(records["corrections"], key=lambda item: item["id"])],
        "views/qa_build_events.csv": [{
            "id": row["id"], "qa_type": row["qa_type"], "result": row["result"],
            "subject_id": row["subject_id"], "witness_path": row["witness_path"], "detail": row["detail"],
        } for row in sorted(records["qa_events"], key=lambda item: item["id"])],
        "views/artifacts.csv": [{
            "id": row["id"], "artifact_kind": row["artifact_kind"], "path": row["path"],
            "bytes": row["bytes"], "sha256": row["sha256"], "result": row["result"],
            "rights_component_ids": row["rights_component_ids"],
        } for row in sorted(records["artifacts"], key=lambda item: item["id"])],
    }
    return {path: csv_bytes(columns[path], rows_by_view[path]) for path in sorted(rows_by_view)}


def payload_record_count(path: str, raw: bytes, inherited: dict[str, Any] | None = None) -> int | None:
    if path.endswith(".jsonl"):
        return raw.count(b"\n")
    if path.endswith(".csv") or path.endswith(".tsv"):
        return max(0, len(raw.decode("utf-8").splitlines()) - 1)
    if path.endswith(".json"):
        return 1
    if inherited is not None:
        return inherited.get("records")
    return None


def build_payloads() -> tuple[dict[str, bytes], dict[str, Any]]:
    records, auxiliary, context = build_records()
    payloads = dict(auxiliary)
    payloads.pop("manifest.json", None)
    for name, relative in RECORD_PATHS.items():
        payloads[relative] = jsonl_bytes(records[name])
    all_records = [row for rows in records.values() for row in rows]
    identity_rows = [{
        "id": row["id"], "record_type": row["record_type"], "stable_key": row["stable_key"],
        "source_local_ids": row.get("source_local_ids", []),
    } for row in all_records]
    payloads["identity_map.jsonl"] = jsonl_bytes(identity_rows)
    view_schema = json.loads(payloads["schemas/backend-view-columns-v0.1.0.json"])
    payloads.update(build_views(records, view_schema["views"]))
    base_entries = {entry["path"]: entry for entry in context["base_manifest"]["files"]}
    file_entries = []
    for path, raw in sorted(payloads.items()):
        file_entries.append({
            "path": path, "bytes": len(raw), "sha256": sha256_bytes(raw),
            "records": payload_record_count(path, raw, base_entries.get(path)),
        })
    record_counts = {name: len(rows) for name, rows in sorted(records.items())}
    new_counts = context["new_record_counts"]
    manifest = deepcopy(context["base_manifest"])
    manifest.update({
        "backend_id": stable_id("r011/backend/R011-B015/final-isolated"),
        "backend_name": "r011-openintro-statistics-id-b015-final-isolated",
        "boundary_id": BOUNDARY_ID,
        "workflow_id": WORKFLOW_ID,
        "recorded_at": RECORDED_AT,
        "scope": "Complete Chapter 4 Section 4.2 Geometric distribution / Distribusi geometrik through EoCE 11--16, public answers 11/13/15, data appendix entry and localized geometricDist70, ending immediately before binomialModel.",
        "record_counts": record_counts,
        "record_count": sum(record_counts.values()),
        "base_record_counts": context["base_manifest"]["record_counts"],
        "new_b015_record_counts": new_counts,
        "new_b015_record_count": sum(new_counts.values()),
        "base_preservation": {
            "boundary_id": BASE_BOUNDARY_ID, "record_count": BASE_RECORD_COUNT,
            "manifest": BASE_MANIFEST_IDENTITY, "inventory": BASE_INVENTORY_IDENTITY,
            "all_base_records_preserved_canonical_bytes": True,
        },
        "build_binding": {
            "terminal_contract": TERMINAL_CONTRACT_IDENTITY,
            "build_receipt": context["contract"]["inputs"]["build_receipt"],
            "reader_pdf": context["contract"]["inputs"]["reader_pdf"],
            "visual_qa": context["contract"]["inputs"]["visual_qa"],
        },
        "asset_closure": {
            "localized_figure_r": context["contract"]["inputs"]["localized_figure_r"],
            "localized_figure_pdf": context["contract"]["inputs"]["localized_figure_pdf"],
            "localized_asset_qa": context["contract"]["inputs"]["localized_asset_qa"],
        },
        "topology": {
            "section": "geomDist", "subsections": 2, "worked_examples": 3,
            "guided_exercises": 3, "guided_inline_answers": 3,
            "eoce_exercises": sorted(EOCE), "public_answers": list(PUBLIC_ANSWERS),
            "o001_companion_gaps": list(O001_GAPS), "data_appendix_entries": 1,
            "next_source_anchor": "binomialModel", "next_source_line": 1268,
        },
        "correction_closure": {"source_corrections": [f"B015-SC{n:03d}" for n in range(1, 6)]},
        "terminology": {"decision_count": len(TERM_CONCEPT_KEYS), "locale": "id-ID"},
        "o001_closure": {"public_answers": list(PUBLIC_ANSWERS), "companion_gaps": list(O001_GAPS), "restricted_solutions_accessed_or_invented": False},
        "interoperability": {"spec": INTEROPERABILITY_SPEC, "required_views": SEMANTIC_BLUEPRINT["required_views"], "status": "passed"},
        "stage_state": "isolated_terminal_backend_candidate",
        "admission_eligibility": "ready_for_separate_guarded_admission",
        "files": file_entries,
    })
    payloads["manifest.json"] = canonical_json(manifest)
    context.update({"manifest": manifest, "record_counts": record_counts, "new_record_counts": new_counts})
    return payloads, context


def validate_payloads(payloads: dict[str, bytes]) -> dict[str, Any]:
    if "manifest.json" not in payloads:
        raise RuntimeError("stage lacks manifest")
    manifest = json.loads(payloads["manifest.json"])
    if manifest.get("boundary_id") != BOUNDARY_ID or manifest.get("backend_name") != "r011-openintro-statistics-id-b015-final-isolated":
        raise RuntimeError("not an exact B015 isolated backend manifest")
    entries = {entry["path"]: entry for entry in manifest["files"]}
    if set(entries) != set(payloads) - {"manifest.json"}:
        raise RuntimeError("manifest file inventory path set differs")
    for path, entry in entries.items():
        observed = {"bytes": len(payloads[path]), "sha256": sha256_bytes(payloads[path])}
        if observed != {"bytes": int(entry["bytes"]), "sha256": entry["sha256"]}:
            raise RuntimeError(f"manifest identity mismatch: {path}")

    records = {name: load_jsonl(payloads[relative]) for name, relative in RECORD_PATHS.items()}
    record_counts = {name: len(rows) for name, rows in sorted(records.items())}
    if record_counts != manifest["record_counts"] or sum(record_counts.values()) != int(manifest["record_count"]):
        raise RuntimeError("manifest record counts differ")
    ids: dict[str, dict[str, Any]] = {}
    keys: dict[str, dict[str, Any]] = {}
    schema = json.loads(payloads["schemas/backend-record-v0.1.0.schema.json"])
    validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
    for rows in records.values():
        for row in rows:
            # The admitted B014 rows are an immutable byte substrate and may
            # predate later schema tightening.  Validate only this append,
            # exactly as the admitted B014 compiler validated only its delta.
            if row.get("boundary_id") == BOUNDARY_ID:
                errors = sorted(validator.iter_errors(row), key=lambda error: list(error.path))
                if errors:
                    raise RuntimeError(f"record schema failure {row.get('stable_key')}: {errors[0].message}")
            if row["id"] != stable_id(row["stable_key"]):
                raise RuntimeError(f"stable UUID mismatch: {row['stable_key']}")
            if row["id"] in ids or row["stable_key"] in keys:
                raise RuntimeError(f"duplicate backend identity: {row['stable_key']}")
            ids[row["id"]] = row
            keys[row["stable_key"]] = row

    base_records, _base_aux, _base_manifest = load_base_records()
    preserved = 0
    for rows in base_records.values():
        for base_row in rows:
            staged = ids.get(base_row["id"])
            if staged is None or canonical_json_text(staged).encode("utf-8") != canonical_json_text(base_row).encode("utf-8"):
                raise RuntimeError(f"B014 base record changed: {base_row['stable_key']}")
            preserved += 1
    if preserved != BASE_RECORD_COUNT:
        raise RuntimeError("base preservation count changed")

    required_keys = [
        SEMANTIC_BLUEPRINT["section"], SEMANTIC_BLUEPRINT["data_appendix"],
        *SEMANTIC_BLUEPRINT["subsections"], *SEMANTIC_BLUEPRINT["worked_examples"],
        *SEMANTIC_BLUEPRINT["guided_exercises"], *SEMANTIC_BLUEPRINT["guided_inline_answers"],
        *SEMANTIC_BLUEPRINT["eoce_exercises"], *SEMANTIC_BLUEPRINT["public_answers"],
        *SEMANTIC_BLUEPRINT["o001_companion_gaps"], *SEMANTIC_BLUEPRINT["assets"],
        *SEMANTIC_BLUEPRINT["corrections"], *SEMANTIC_BLUEPRINT["terms"],
    ]
    missing = sorted(set(required_keys) - set(keys))
    if missing:
        raise RuntimeError(f"missing B015 semantic keys: {missing}")
    b015_rows = [row for row in ids.values() if row.get("boundary_id") == BOUNDARY_ID]
    observed_new_counts = {
        name: sum(row.get("boundary_id") == BOUNDARY_ID for row in rows)
        for name, rows in sorted(records.items())
    }
    if observed_new_counts != manifest["new_b015_record_counts"] or len(b015_rows) != int(manifest["new_b015_record_count"]):
        raise RuntimeError("B015 appended record counts differ")
    if any(row.get("stable_key", "").find("Distribusi") >= 0 for row in b015_rows):
        raise RuntimeError("reader-visible translated wording entered stable identity")

    identity_rows = [{
        "id": row["id"], "record_type": row["record_type"], "stable_key": row["stable_key"],
        "source_local_ids": row.get("source_local_ids", []),
    } for row in ids.values()]
    if payloads["identity_map.jsonl"] != jsonl_bytes(identity_rows):
        raise RuntimeError("identity-map replay differs")
    view_schema = json.loads(payloads["schemas/backend-view-columns-v0.1.0.json"])
    expected_views = build_views(records, view_schema["views"])
    for path, expected in expected_views.items():
        if payloads[path] != expected:
            raise RuntimeError(f"deterministic CSV view replay differs: {path}")
    manifest_schema = json.loads(payloads["schemas/backend-manifest-v0.1.0.schema.json"])
    jsonschema.Draft202012Validator(manifest_schema).validate(manifest)
    return {
        "status": "PASS_B015_FINAL_VALIDATED_IN_MEMORY",
        "base_records_preserved_canonical_bytes": preserved,
        "new_record_count": len(b015_rows),
        "new_record_counts": observed_new_counts,
        "record_count": len(ids),
        "record_counts": record_counts,
        "required_views": len(expected_views),
        "manifest": {"bytes": len(payloads["manifest.json"]), "sha256": sha256_bytes(payloads["manifest.json"])},
    }


def write_output(output: Path, payloads: dict[str, bytes]) -> dict[str, Any]:
    resolved_root = FINAL_ROOT.resolve()
    resolved_output = output.resolve()
    if not resolved_output.is_relative_to(resolved_root):
        raise RuntimeError(f"B015 output must be within {FINAL_ROOT}")
    if resolved_output.exists():
        raise RuntimeError(f"refusing to overwrite existing stage: {resolved_output}")
    for relative, raw in sorted(payloads.items()):
        path = resolved_output / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    observed = inventory(resolved_output)
    return {"path": resolved_output.relative_to(LANE).as_posix(), "inventory": observed}


def read_stage(stage: Path) -> dict[str, bytes]:
    resolved_root = FINAL_ROOT.resolve()
    resolved_stage = stage.resolve()
    if not resolved_stage.is_relative_to(resolved_root) or not resolved_stage.is_dir():
        raise RuntimeError("stage is absent or outside isolated B015 final root")
    return {
        path.relative_to(resolved_stage).as_posix(): path.read_bytes()
        for path in sorted(resolved_stage.rglob("*")) if path.is_file()
    }


def validate_stage(stage: Path) -> dict[str, Any]:
    bind_base()
    bind_ready_inputs()
    load_terminal_contract()
    payloads = read_stage(stage)
    result = validate_payloads(payloads)
    result["status"] = "PASS_B015_FINAL_VALIDATED_ON_DISK"
    result["stage"] = stage.resolve().relative_to(LANE).as_posix()
    result["inventory"] = inventory(stage.resolve())
    return result


def compare_stages(left: Path, right: Path) -> dict[str, Any]:
    left_payloads, right_payloads = read_stage(left), read_stage(right)
    if set(left_payloads) != set(right_payloads):
        raise RuntimeError("independent stage path sets differ")
    differences = [path for path in sorted(left_payloads) if left_payloads[path] != right_payloads[path]]
    if differences:
        raise RuntimeError(f"independent stage bytes differ: {differences[:5]}")
    left_inventory, right_inventory = inventory(left.resolve()), inventory(right.resolve())
    if left_inventory != right_inventory:
        raise RuntimeError("independent stage inventories differ")
    return {
        "status": "PASS_B015_INDEPENDENT_STAGES_BYTE_IDENTICAL",
        "files_compared": len(left_payloads), "inventory": left_inventory,
        "manifest": identity(left / "manifest.json"),
    }


def self_test() -> dict[str, Any]:
    keys: list[str] = []
    for name, value in SEMANTIC_BLUEPRINT.items():
        if name in {"relation_classes", "qa_event_types", "required_views", "concept_prerequisites", "unit_prerequisites"}:
            continue
        if isinstance(value, str) and value.startswith("r011/"):
            keys.append(value)
        elif isinstance(value, list):
            keys.extend(item for item in value if isinstance(item, str) and item.startswith("r011/"))
    keys.extend(TERM_CONCEPT_KEYS.values())
    if len(keys) != len(set(keys)):
        # Reused concept keys can occur once in TERM_CONCEPT_KEYS only; any
        # duplicate elsewhere would make the blueprint ambiguous.
        duplicates = sorted({key for key in keys if keys.count(key) > 1})
        allowed = set(TERM_CONCEPT_KEYS.values()) & set(SEMANTIC_BLUEPRINT.get("concept_prerequisites", ()))
        if duplicates and allowed:
            raise RuntimeError(f"ambiguous stable keys: {duplicates}")
    for key in keys:
        if not re.fullmatch(r"r011/[A-Za-z0-9._/-]+", key):
            raise RuntimeError(f"invalid stable key: {key}")
        uuid.UUID(stable_id(key))
    if sorted(EOCE) != list(range(11, 17)):
        raise RuntimeError("EoCE semantic topology changed")
    if set(PUBLIC_ANSWERS) | set(O001_GAPS) != set(EOCE):
        raise RuntimeError("public-answer/O001 closure no longer partitions EoCE 11--16")
    return {
        "status": "PASS_B015_PREPARATION_INERT_SELF_TEST",
        "boundary_id": BOUNDARY_ID,
        "terminal_contract_bound": TERMINAL_CONTRACT_IDENTITY is not None,
        "predicted_record_classes": PREDICTED_RECORD_CLASSES,
        "reused_record_classes": REUSED_RECORD_CLASSES,
        "pending_roles": sorted(PENDING_TERMINAL_ROLES),
    }


def probe() -> dict[str, Any]:
    return {
        **self_test(),
        "status": "PASS_B015_PREPARATION_PROBE_FAIL_CLOSED",
        "base": bind_base(),
        "ready_inputs": bind_ready_inputs(),
        "terminal": {
            "contract_path": TERMINAL_CONTRACT.relative_to(LANE).as_posix(),
            "identity_bound": TERMINAL_CONTRACT_IDENTITY is not None,
            "pending": [
                {"role": role, "purpose": PENDING_TERMINAL_ROLES[role]}
                for role in sorted(PENDING_TERMINAL_ROLES)
            ],
        },
        "semantic_blueprint": SEMANTIC_BLUEPRINT,
        "final_record_count": None,
        "new_record_count": None,
    }


def generate(output: Path) -> dict[str, Any]:
    """Generate one exact isolated stage; all gates precede every write."""
    payloads, context = build_payloads()
    in_memory = validate_payloads(payloads)
    written = write_output(output, payloads)
    on_disk = validate_stage(output)
    return {
        "status": "PASS_B015_FINAL_ISOLATED_BACKEND",
        "boundary_id": BOUNDARY_ID,
        "base_record_count": BASE_RECORD_COUNT,
        "new_record_count": in_memory["new_record_count"],
        "new_record_counts": in_memory["new_record_counts"],
        "record_count": in_memory["record_count"],
        "record_counts": in_memory["record_counts"],
        "manifest": in_memory["manifest"],
        "stage": written,
        "on_disk_validation": on_disk["status"],
        "relation_counts": context["relation_counts"],
        "base_records_preserved_canonical_bytes": in_memory["base_records_preserved_canonical_bytes"],
        "live_backend_mutated": False,
        "canonical_source_mutated": False,
        "controls_mutated": False,
        "release_mutated": False,
        "git_used": False,
        "network_used": False,
        "publication_performed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--self-test", action="store_true", help="run inert structural checks")
    modes.add_argument("--probe", action="store_true", help="verify exact base and ready inputs without writing")
    modes.add_argument("--output", type=Path, help="future isolated stage; currently fails closed before writes")
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
            "pending_roles": sorted(PENDING_TERMINAL_ROLES),
            "output_written": False,
        }).decode("utf-8"), end="", file=sys.stderr)
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
