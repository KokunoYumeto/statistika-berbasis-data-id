#!/usr/bin/env python3
"""Generate the terminal deterministic R011-B014 modular-backend append.

The admitted R011-B013 backend is an immutable, hash-bound preimage.  This
program writes only explicit isolated ``qa/b014-backend-final`` stages and
never mutates the live backend, canonical source, controls, releases, Git, or
network state.  Run with Python ``-B``.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable

import jsonschema


SCRIPT_PATH = Path(__file__).resolve()
LANE = SCRIPT_PATH.parents[1]
SCRIPTS = LANE / "scripts"
STAGE_ROOT = LANE / "qa" / "b014-backend-final"
sys.path.insert(0, str(SCRIPTS))
import generate_backend_b013 as b013  # noqa: E402

g = b013.g
RECORD_PATHS = b013.RECORD_PATHS

BOUNDARY_ID = "R011-B014"
BASE_BOUNDARY_ID = "R011-B013"
SCHEMA_VERSION = "0.1.0"
RECORDED_AT = "2026-08-25T04:20:00+02:00"
WORKFLOW_ID = "r011-openintro-statistics-id-b014-backend-final"
PROVENANCE = "OpenAI Codex gpt-5.6-sol, Ultra"
AUTHORITY_COMMIT = "fee25091fb24e89c36296fd67c48c1fcf7a93b6e"
AUTHORITY_TREE = "d61cc601e7d97759ce805900520f784d02a0489e"

BASE_EXPORTS = LANE / "backend" / "exports"
BASE_MANIFEST = BASE_EXPORTS / "manifest.json"
TERMINAL_CONTRACT = LANE / "qa" / "b014-backend-prep" / "R011-B014_TERMINAL_INPUTS.json"
PREP_AUDIT = LANE / "qa" / "b014-backend-prep" / "R011-B014_BACKEND_INPUT_REQUIREMENTS_AND_INDEPENDENT_AUDIT.json"
AUTHORITY_ROOT = LANE / "authority" / "upstream" / (
    "openintro-statistics-fee25091fb24e89c36296fd67c48c1fcf7a93b6e"
)
MAIN_AUTHORITY = AUTHORITY_ROOT / "ch_distributions" / "TeX" / "ch_distributions.tex"
EOCE_AUTHORITY = AUTHORITY_ROOT / "ch_distributions" / "TeX" / "normal_distribution.tex"
ANSWER_AUTHORITY = AUTHORITY_ROOT / "extraTeX" / "eoceSolutions" / "eoceSolutions.tex"

BASE_MANIFEST_IDENTITY = {
    "bytes": 63730,
    "sha256": "f95aedf74e7d05be53a92e6f779e9bf2578ef4f11a619349ccd53ee50ca4cb8a",
}
BASE_INVENTORY_IDENTITY = {
    "files": 312,
    "bytes": 127211548,
    "sha256": "a968f410bfabbcae2a7d34ac75f63fff14db1438cc4496fcfbe3b6d3d131b59d",
}
BASE_RECORD_COUNT = 4516
BASE_ADMISSION_RECEIPT = LANE / "qa" / "R011-B013_BOUNDARY_RECEIPT.json"
BASE_ADMISSION_RECEIPT_IDENTITY = {
    "bytes": 21058,
    "sha256": "4465e858d23e5b2ed55b6b95ebb419617e1a17f3bffc4e89c574fa4b022630d1",
}
BASE_ADMISSION_CHECKPOINT = LANE / "00_control" / "R011-B013_ADMISSION_CHECKPOINT.md"
BASE_ADMISSION_CHECKPOINT_IDENTITY = {
    "bytes": 1884,
    "sha256": "42fb2eb65def9f4a493c56db9154585f49beefa37f58014519b2a8a9d4409a8d",
}
BASE_POST_ADMISSION = LANE / "qa" / "b013-admission" / "R011-B013_POST_ADMISSION_VERIFICATION.json"
BASE_POST_ADMISSION_IDENTITY = {
    "bytes": 4225,
    "sha256": "e4d0b1b5b011a34138e1abcb9a035872d15e7a5809dcad0aaa78943dd87c50c5",
}
TERMINAL_CONTRACT_IDENTITY = {
    "bytes": 6269,
    "sha256": "1fda12518c026d9d45ae126ebe77de16c3bea701fdfd0d647bb6605b1340e1ac",
}
PREP_AUDIT_IDENTITY = {
    "bytes": 24411,
    "sha256": "4ad3b735388e6ad6e3112a19c9c0a2f6ae10f6b14feb33e9d2c76f93d0827965",
}
MAIN_AUTHORITY_IDENTITY = {
    "bytes": 91188,
    "sha256": "71e4985a1bf31e9dd6897ec2bd246b3b2f8cd62ab55524a5b1bfe791e613a3a9",
}
EOCE_AUTHORITY_IDENTITY = {
    "bytes": 7466,
    "sha256": "c7d98aff4f421d290e4a6e117cdff4d4b7604ee9bbcc7a3e080928d3c963438e",
}
ANSWER_AUTHORITY_IDENTITY = {
    "bytes": 106045,
    "sha256": "6c4e01376db4c023cc7b3f9949490e57220ef1cb831c580da71efde6ce723268",
}

PUBLIC_ANSWERS = [1, 3, 5, 7, 9]
O001_GAPS = [2, 4, 6, 8, 10]
EOCE_EXERCISES = list(range(1, 11))
GUIDED_EXERCISES = list(range(1, 16))
WORKED_EXAMPLES = list(range(1, 7))
EXERCISE_LABELS = {
    1: "area_under_curve_1",
    2: "area_under_curve_2",
    3: "GRE_intro",
    4: "triathlon_times_intro",
    5: "GRE_cutoffs",
    6: "triathlon_times_cutoffs",
    7: "la_weather_intro",
    8: "CAPM",
    9: "la_weather_unit_change",
    10: "find_sd_cholesterol",
}


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def identity(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise RuntimeError(f"missing exact input: {path}")
    raw = path.read_bytes()
    return {"bytes": len(raw), "sha256": sha256_bytes(raw)}


def require(path: Path, expected: dict[str, Any] | None = None) -> bytes:
    if not path.is_file():
        raise RuntimeError(f"missing exact input: {path}")
    raw = path.read_bytes()
    observed = {"bytes": len(raw), "sha256": sha256_bytes(raw)}
    if expected is not None and observed != expected:
        raise RuntimeError(f"identity changed for {path}: {observed} != {expected}")
    return raw


def canonical_json(value: Any) -> bytes:
    return (g.canonical_json(value) + "\n").encode("utf-8")


def record(record_type: str, stable_key: str, **fields: Any) -> dict[str, Any]:
    fields["recorded_at"] = RECORDED_AT
    fields["workflow_id"] = WORKFLOW_ID
    return g.record(record_type, stable_key, **fields)


def load_jsonl(raw: bytes) -> list[dict[str, Any]]:
    return [json.loads(line) for line in raw.decode("utf-8").splitlines() if line]


def one(records: dict[str, list[dict[str, Any]]], name: str, key: str) -> dict[str, Any]:
    matches = [row for row in records[name] if row.get("stable_key") == key]
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one {name} record {key!r}, got {len(matches)}")
    return matches[0]


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


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
        raise RuntimeError(f"invalid byte span {start}:{end}/{len(raw)}")
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
    return {
        key: int(meta[key])
        for key in ("line_start", "line_end", "byte_start", "byte_end_exclusive")
    }


def rebase(meta: dict[str, Any], full_raw: bytes, offset: int) -> dict[str, Any]:
    return span_meta(
        full_raw,
        offset + int(meta["byte_start"]),
        offset + int(meta["byte_end_exclusive"]),
    )


def marker_spans(raw: bytes, numbers: Iterable[int]) -> dict[int, dict[str, Any]]:
    wanted = list(numbers)
    wanted_set = set(wanted)
    lines, starts = line_table(raw)
    found: list[tuple[int, int]] = []
    for index, line in enumerate(lines):
        match = re.fullmatch(rb"%\s*(\d+)\r?\n?", line)
        if match and int(match.group(1)) in wanted_set:
            found.append((int(match.group(1)), starts[index]))
    if [number for number, _ in found] != wanted:
        raise RuntimeError(f"marker topology changed: {[number for number, _ in found]} != {wanted}")
    result: dict[int, dict[str, Any]] = {}
    for index, (number, start) in enumerate(found):
        end = found[index + 1][1] if index + 1 < len(found) else len(raw)
        while end > start and raw[end - 1 : end] in (b"\n", b"\r", b" ", b"\t"):
            end -= 1
        result[number] = span_meta(raw, start, end)
    return result


def balanced_command_end(raw: bytes, start: int, command: bytes) -> int:
    open_at = raw.find(b"{", start + len(command))
    if open_at < 0:
        raise RuntimeError(f"missing argument for {command!r}")
    depth = 0
    for index in range(open_at, len(raw)):
        byte = raw[index : index + 1]
        if byte == b"{" and (index == 0 or raw[index - 1 : index] != b"\\"):
            depth += 1
        elif byte == b"}" and (index == 0 or raw[index - 1 : index] != b"\\"):
            depth -= 1
            if depth == 0:
                return index + 1
    raise RuntimeError(f"unterminated argument for {command!r}")


def structural_spans(raw: bytes) -> list[dict[str, Any]]:
    """Losslessly partition active Section 4.1 around semantic blocks."""
    blocks: list[tuple[int, int, str, int]] = []
    for begin, end_token, kind, expected in (
        (b"\\begin{examplewrap}", b"\\end{examplewrap}", "worked_example", 6),
        (b"\\begin{exercisewrap}", b"\\end{exercisewrap}", "guided_exercise", 15),
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
            if raw[end : end + 2] == b"\r\n":
                end += 2
            elif raw[end : end + 1] == b"\n":
                end += 1
            count += 1
            blocks.append((start, end, kind, count))
            cursor = end
        if count != expected:
            raise RuntimeError(f"B014 {kind} topology changed: {count} != {expected}")
    cursor = count = 0
    command = b"\\footnotetext"
    while True:
        start = raw.find(command, cursor)
        if start < 0:
            break
        end = balanced_command_end(raw, start, command)
        if raw[end : end + 2] == b"\r\n":
            end += 2
        elif raw[end : end + 1] == b"\n":
            end += 1
        count += 1
        blocks.append((start, end, "guided_inline_answer", count))
        cursor = end
    if count != 15:
        raise RuntimeError(f"B014 inline-answer topology changed: {count} != 15")
    blocks.sort()
    for left, right in zip(blocks, blocks[1:]):
        if left[1] > right[0]:
            raise RuntimeError("overlapping B014 semantic blocks")
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
    counts = {kind: sum(row["kind"] == kind for row in result) for kind in {
        "section_prose", "worked_example", "guided_exercise", "guided_inline_answer"
    }}
    if counts != {
        "section_prose": 15,
        "worked_example": 6,
        "guided_exercise": 15,
        "guided_inline_answer": 15,
    }:
        raise RuntimeError(f"B014 structural segmentation changed: {counts}")
    return result


def subsection_spans(raw: bytes) -> list[dict[str, Any]]:
    matches = list(re.finditer(rb"\\subsection\{([^}]+)\}", raw))
    if len(matches) != 5:
        raise RuntimeError(f"B014 subsection topology changed: {len(matches)} != 5")
    result = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(raw)
        result.append({
            "number": index + 1,
            "title": match.group(1).decode("utf-8"),
            "span": span_meta(raw, match.start(), end),
        })
    return result


def chapter_segments(raw: bytes) -> list[dict[str, Any]]:
    end_token = b"\\end{chapterpage}"
    title_end = raw.find(end_token)
    intro_start = raw.find(b"\\chapterintro{")
    if title_end < 0 or intro_start < 0:
        raise RuntimeError("chapter opening topology changed")
    title_end += len(end_token)
    return [
        {"kind": "chapter_title_hierarchy", "number": 1, "span": span_meta(raw, 0, title_end)},
        {"kind": "chapter_intro", "number": 1, "span": span_meta(raw, intro_start, len(raw))},
    ]


def inventory(root: Path) -> dict[str, Any]:
    rows = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            raw = path.read_bytes()
            rows.append({
                "path": path.relative_to(root).as_posix(),
                "bytes": len(raw),
                "sha256": sha256_bytes(raw),
            })
    digest = sha256_bytes("".join(
        f"{row['path']}\t{row['bytes']}\t{row['sha256']}\n" for row in rows
    ).encode("utf-8"))
    return {
        "files": len(rows),
        "bytes": sum(row["bytes"] for row in rows),
        "sha256": digest,
        "inventory": rows,
    }


def load_base() -> tuple[dict[str, list[dict[str, Any]]], dict[str, bytes], dict[str, Any]]:
    require(BASE_ADMISSION_RECEIPT, BASE_ADMISSION_RECEIPT_IDENTITY)
    require(BASE_ADMISSION_CHECKPOINT, BASE_ADMISSION_CHECKPOINT_IDENTITY)
    require(BASE_POST_ADMISSION, BASE_POST_ADMISSION_IDENTITY)
    manifest = json.loads(require(BASE_MANIFEST, BASE_MANIFEST_IDENTITY))
    if manifest.get("backend_name") != "r011-openintro-statistics-id-b013-final-isolated" or manifest.get("boundary_id") != BASE_BOUNDARY_ID:
        raise RuntimeError("live base is not the exact admitted B013 backend")
    if sum(int(value) for value in manifest["record_counts"].values()) != BASE_RECORD_COUNT:
        raise RuntimeError("B013 base record count changed")
    observed_inventory = inventory(BASE_EXPORTS)
    if {key: observed_inventory[key] for key in ("files", "bytes", "sha256")} != BASE_INVENTORY_IDENTITY:
        raise RuntimeError("B013 base export inventory changed")
    by_path = {entry["path"]: entry for entry in manifest["files"]}
    records: dict[str, list[dict[str, Any]]] = {}
    for name, relative in RECORD_PATHS.items():
        entry = by_path[relative]
        raw = require(BASE_EXPORTS / relative, {"bytes": entry["bytes"], "sha256": entry["sha256"]})
        rows = load_jsonl(raw)
        if len(rows) != int(entry["records"]) or g.jsonl_bytes(rows) != raw:
            raise RuntimeError(f"noncanonical B013 typed payload: {relative}")
        records[name] = rows
    auxiliary = {
        path.relative_to(BASE_EXPORTS).as_posix(): path.read_bytes()
        for path in sorted(BASE_EXPORTS.rglob("*"))
        if path.is_file()
    }
    return records, auxiliary, manifest


def load_terminal() -> dict[str, Any]:
    contract = json.loads(require(TERMINAL_CONTRACT, TERMINAL_CONTRACT_IDENTITY))
    if contract.get("boundary_id") != BOUNDARY_ID or contract.get("status") != "READY_TERMINAL_INPUTS":
        raise RuntimeError("B014 terminal contract is not ready")
    closure = contract.get("closure", {})
    expected = {
        "chapter_title_hierarchy_segments": 1,
        "chapter_intro_segments": 1,
        "section_prose_segments": 15,
        "subsections": 5,
        "worked_examples": 6,
        "guided_exercises": 15,
        "guided_inline_public_answers": 15,
        "eoce_exercises": EOCE_EXERCISES,
        "public_answers": PUBLIC_ANSWERS,
        "o001_gaps": O001_GAPS,
        "source_corrections": [f"B014-SC{number:03d}" for number in range(1, 12)],
        "localized_layout_adaptations": ["B014-LA001", "B014-LA002"],
        "direct_pdf_assets": 21,
        "adjacent_r_sources": 16,
        "controlled_terms": 13,
        "reader_pdf_pages": 427,
        "restricted_solutions_accessed_or_invented": False,
        "next_source_anchor": "geomDist",
    }
    if closure != expected:
        raise RuntimeError("B014 terminal closure changed")
    if len(contract.get("inputs", {})) != 23:
        raise RuntimeError("B014 terminal role count changed")
    for role, item in sorted(contract["inputs"].items()):
        require(LANE / item["path"], {"bytes": int(item["bytes"]), "sha256": item["sha256"]})
    return contract


def load_context() -> dict[str, Any]:
    contract = load_terminal()
    inputs = contract["inputs"]
    raw = {
        key: require(LANE / value["path"], {"bytes": value["bytes"], "sha256": value["sha256"]})
        for key, value in inputs.items()
    }
    main_authority = require(MAIN_AUTHORITY, MAIN_AUTHORITY_IDENTITY)
    eoce_authority = require(EOCE_AUTHORITY, EOCE_AUTHORITY_IDENTITY)
    answer_authority = require(ANSWER_AUTHORITY, ANSWER_AUTHORITY_IDENTITY)
    chapter_source = main_authority[0:806]
    main_source = main_authority[808:30331]
    answer_source = answer_authority[26871:30058]
    if {"bytes": len(chapter_source), "sha256": sha256_bytes(chapter_source)} != {
        "bytes": 806, "sha256": "c1c89a3236b94c450db773aa1b0a0bb33a3039896d76140665d74614c386d28e"
    }:
        raise RuntimeError("B014 authority chapter-opening slice changed")
    if {"bytes": len(main_source), "sha256": sha256_bytes(main_source)} != {
        "bytes": 29523, "sha256": "b07486f9e8ffe894df64165274db12f5e1a26f4e8ba27d39d79eff858f6702aa"
    }:
        raise RuntimeError("B014 authority Section 4.1 slice changed")
    if {"bytes": len(answer_source), "sha256": sha256_bytes(answer_source)} != {
        "bytes": 3187, "sha256": "4a08aa141719519a8dac3fe2ea96abe1b45127bf1579fcf99bc2b8e56171b01b"
    }:
        raise RuntimeError("B014 authority public-answer slice changed")

    chapter_target = raw["chapter_opening_fragment"]
    main_target = raw["section_fragment"]
    eoce_target = raw["eoce_fragment"]
    answer_target = raw["public_answers_fragment"]
    assembled_main = raw["assembled_main"]
    assembled_answers = raw["assembled_answers"]
    chapter_target_offset = assembled_main.find(chapter_target)
    main_target_offset = assembled_main.find(main_target)
    answer_body_start = answer_target.find(b"% 1")
    if answer_body_start < 0:
        raise RuntimeError("terminal B014 answer body start disappeared")
    answer_target_body = answer_target[answer_body_start:].rstrip(b"\r\n")
    answer_target_offset = assembled_answers.find(answer_target_body)
    for label, haystack, needle, offset in (
        ("chapter", assembled_main, chapter_target, chapter_target_offset),
        ("section", assembled_main, main_target, main_target_offset),
        ("answers", assembled_answers, answer_target_body, answer_target_offset),
    ):
        if offset < 0 or haystack.find(needle, offset + 1) >= 0:
            raise RuntimeError(f"terminal B014 {label} assembly binding changed")

    source_struct = structural_spans(main_source)
    target_struct = structural_spans(main_target)
    if [(row["kind"], row["number"]) for row in source_struct] != [
        (row["kind"], row["number"]) for row in target_struct
    ]:
        raise RuntimeError("B014 structural source/target segmentation changed")
    source_chapter_segments = chapter_segments(chapter_source)
    target_chapter_segments = chapter_segments(chapter_target.rstrip(b"\r\n"))
    source_gap = chapter_source[
        source_chapter_segments[0]["span"]["byte_end_exclusive"] :
        source_chapter_segments[1]["span"]["byte_start"]
    ]
    target_chapter_raw = chapter_target.rstrip(b"\r\n")
    target_gap = target_chapter_raw[
        target_chapter_segments[0]["span"]["byte_end_exclusive"] :
        target_chapter_segments[1]["span"]["byte_start"]
    ]
    if source_gap != target_gap:
        raise RuntimeError("chapter structural gap changed")

    return {
        "contract": contract,
        "inputs": inputs,
        "raw": raw,
        "main_authority": main_authority,
        "eoce_authority": eoce_authority,
        "answer_authority": answer_authority,
        "chapter_source": chapter_source,
        "main_source": main_source,
        "answer_source": answer_source,
        "chapter_target": chapter_target.rstrip(b"\r\n"),
        "main_target": main_target,
        "eoce_target": eoce_target,
        "answer_target": answer_target,
        "answer_target_body": answer_target_body,
        "assembled_main": assembled_main,
        "assembled_answers": assembled_answers,
        "chapter_target_offset": chapter_target_offset,
        "main_target_offset": main_target_offset,
        "answer_target_offset": answer_target_offset,
        "source_chapter_segments": source_chapter_segments,
        "target_chapter_segments": target_chapter_segments,
        "main_source_spans": source_struct,
        "main_target_spans": target_struct,
        "source_subsections": subsection_spans(main_source),
        "target_subsections": subsection_spans(main_target),
        "eoce_source_spans": marker_spans(eoce_authority, EOCE_EXERCISES),
        "eoce_target_spans": marker_spans(eoce_target, EOCE_EXERCISES),
        "answer_source_spans": marker_spans(answer_source, PUBLIC_ANSWERS),
        "answer_target_spans": marker_spans(answer_target_body, PUBLIC_ANSWERS),
        "translation_qa": json.loads(raw["final_translation_qa"]),
        "terminology_qa": json.loads(raw["terminology_qa"]),
        "asset_closure": json.loads(raw["asset_closure_qa"]),
        "build_receipt": json.loads(raw["build_receipt"]),
        "visual_qa": json.loads(raw["visual_qa"]),
    }


def common_fields(
    resource_id: str,
    edition_id: str,
    parent_id: str | None,
    order: int | None,
    locale: str,
    state: str,
    rights: list[str],
) -> dict[str, Any]:
    return {
        "resource_id": resource_id,
        "edition_id": edition_id,
        "source_local_ids": [BOUNDARY_ID],
        "parent_id": parent_id,
        "order": order,
        "locale": locale,
        "translation_state": state,
        "rights_component_ids": rights,
        "boundary_id": BOUNDARY_ID,
        "status": "active",
    }


def add_relation(
    records: dict[str, list[dict[str, Any]]],
    key: str,
    relation_type: str,
    from_id: str,
    to_id: str,
    order: int,
    qualifier: str,
    resource_id: str,
    edition_id: str,
) -> None:
    records["relations"].append(record(
        "relation",
        key,
        relation_type=relation_type,
        from_id=from_id,
        to_id=to_id,
        qualifier=qualifier,
        resource_id=resource_id,
        edition_id=edition_id,
        source_local_ids=[BOUNDARY_ID],
        parent_id=None,
        order=order,
        locale="zxx",
        translation_state="structurally_verified",
        rights_component_ids=[],
        boundary_id=BOUNDARY_ID,
        source_path=None,
        source_span=None,
        source_sha256=None,
        status="active",
    ))


def load_term_specs(raw: bytes) -> list[dict[str, Any]]:
    rows = list(csv.DictReader(raw.decode("utf-8").splitlines(), delimiter="\t"))
    if len(rows) != 13:
        raise RuntimeError(f"controlled-term count changed: {len(rows)} != 13")
    result = []
    for row in rows:
        synonyms = [] if row["accepted_synonyms"] == "-" else [
            item.strip() for item in row["accepted_synonyms"].split(";") if item.strip()
        ]
        result.append({
            "source": row["source_term"],
            "target": row["controlled_id_ID"],
            "variants": synonyms,
            "evidence": row["established_evidence"],
            "decision": row["decision"],
        })
    return result


def build_records() -> tuple[dict[str, list[dict[str, Any]]], dict[str, bytes], dict[str, Any]]:
    base_records, auxiliary, base_manifest = load_base()
    records = deepcopy(base_records)
    context = load_context()
    resource_id = one(records, "resources", "r011/resource/openintro-statistics")["id"]
    edition_id = one(records, "editions", "r011/edition/fee25091")["id"]
    upstream_rights = one(records, "rights", "r011/rights/upstream-cc-by-sa-3.0")["id"]
    o001_rights = one(records, "rights", "r011/rights/o001-original-companion-planned")["id"]
    package_rights = one(records, "rights", "r011/rights/openintro-r-package-gpl-3")["id"]
    book_id = one(records, "units", "r011/unit/book")["id"]
    previous_section = one(records, "units", "r011/unit/source-label/contDist")["id"]

    text_rights_key = "r011/rights/b014-localized-chapter-and-section-text"
    text_rights = g.stable_id(text_rights_key)
    records["rights"].append(record(
        "rights",
        text_rights_key,
        component_scope="B014 Indonesian Chapter 4 title/introduction, complete Section 4.1, EoCE 1--10, public answers 1/3/5/7/9, localized accessibility descriptions, and explicitly identified derivative corrections/layout adaptations.",
        license_expression="CC-BY-SA-3.0",
        verification_status="verified against exact R011-B014 source and component-rights closures",
        attribution="OpenIntro Statistics source authors; Indonesian derivative changes identified by R011-B014.",
        change_notice="SC001--SC011 and LA001--LA002 are explicit, hash-bound derivative deltas; reused assets remain byte-identical.",
        non_endorsement="No author, institution, publisher, brand owner, or tool-provider endorsement implied.",
        publication_effect="Isolated B014 backend candidate only; guarded admission and publication are separate transactions.",
        source_path=context["inputs"]["component_rights_closure"]["path"],
        source_span=None,
        source_sha256=context["inputs"]["component_rights_closure"]["sha256"],
        **common_fields(resource_id, edition_id, resource_id, len(records["rights"]) + 1, "zxx", "structurally_verified", []),
    ))

    chapter_key = "r011/unit/source-label/ch_distributions"
    section_key = "r011/unit/source-label/normalDist"
    chapter_source_meta = span_meta(context["main_authority"], 0, 806)
    chapter_target_meta = span_meta(
        context["assembled_main"],
        context["chapter_target_offset"],
        context["chapter_target_offset"] + len(context["chapter_target"]),
    )
    section_source_meta = span_meta(context["main_authority"], 808, 30331)
    section_target_meta = span_meta(
        context["assembled_main"],
        context["main_target_offset"],
        context["main_target_offset"] + len(context["main_target"]),
    )
    unit_specs: list[dict[str, Any]] = [
        {
            "key": chapter_key,
            "type": "chapter",
            "title": "Distributions of random variables",
            "parent": book_id,
            "order": 7,
            "source_meta": chapter_source_meta,
            "target_meta": chapter_target_meta,
            "source_path": "ch_distributions/TeX/ch_distributions.tex",
            "target_path": "repo/ch_distributions/TeX/ch_distributions.tex",
        },
        {
            "key": section_key,
            "type": "section",
            "title": "Normal distribution",
            "parent": chapter_key,
            "order": 1,
            "source_meta": section_source_meta,
            "target_meta": section_target_meta,
            "source_path": "ch_distributions/TeX/ch_distributions.tex",
            "target_path": "repo/ch_distributions/TeX/ch_distributions.tex",
        },
    ]
    subsection_keys: list[str] = []
    for source_sub, target_sub in zip(context["source_subsections"], context["target_subsections"]):
        key = f"r011/unit/b014/subsection-{source_sub['number']:02d}-{slug(source_sub['title'])}"
        subsection_keys.append(key)
        unit_specs.append({
            "key": key,
            "type": "subsection",
            "title": source_sub["title"],
            "parent": section_key,
            "order": source_sub["number"] * 100,
            "source_meta": rebase(source_sub["span"], context["main_authority"], 808),
            "target_meta": rebase(target_sub["span"], context["assembled_main"], context["main_target_offset"]),
            "source_path": "ch_distributions/TeX/ch_distributions.tex",
            "target_path": "repo/ch_distributions/TeX/ch_distributions.tex",
        })
    source_by_sig = {(row["kind"], row["number"]): row for row in context["main_source_spans"]}
    target_by_sig = {(row["kind"], row["number"]): row for row in context["main_target_spans"]}
    for number in WORKED_EXAMPLES:
        source_row = source_by_sig[("worked_example", number)]
        target_row = target_by_sig[("worked_example", number)]
        unit_specs.append({
            "key": f"r011/unit/worked-example/ch04-sec4.1-{number:02d}",
            "type": "worked_example",
            "title": f"Section 4.1 worked example {number}",
            "parent": section_key,
            "order": 1000 + number * 10,
            "source_meta": rebase(source_row["span"], context["main_authority"], 808),
            "target_meta": rebase(target_row["span"], context["assembled_main"], context["main_target_offset"]),
            "source_path": "ch_distributions/TeX/ch_distributions.tex",
            "target_path": "repo/ch_distributions/TeX/ch_distributions.tex",
        })
    for number in GUIDED_EXERCISES:
        source_row = source_by_sig[("guided_exercise", number)]
        target_row = target_by_sig[("guided_exercise", number)]
        guide_key = f"r011/unit/guided-exercise/ch04-sec4.1-{number:02d}"
        unit_specs.append({
            "key": guide_key,
            "type": "guided_exercise",
            "title": f"Section 4.1 guided exercise {number}",
            "parent": section_key,
            "order": 2000 + number * 10,
            "source_meta": rebase(source_row["span"], context["main_authority"], 808),
            "target_meta": rebase(target_row["span"], context["assembled_main"], context["main_target_offset"]),
            "source_path": "ch_distributions/TeX/ch_distributions.tex",
            "target_path": "repo/ch_distributions/TeX/ch_distributions.tex",
            "answer_availability": "inline_public_feedback",
        })
        source_answer = source_by_sig[("guided_inline_answer", number)]
        target_answer = target_by_sig[("guided_inline_answer", number)]
        unit_specs.append({
            "key": f"r011/unit/guided-solution/ch04-sec4.1-{number:02d}",
            "type": "solution",
            "title": f"Inline public answer to Section 4.1 guided exercise {number}",
            "parent": guide_key,
            "order": 1,
            "source_meta": rebase(source_answer["span"], context["main_authority"], 808),
            "target_meta": rebase(target_answer["span"], context["assembled_main"], context["main_target_offset"]),
            "source_path": "ch_distributions/TeX/ch_distributions.tex",
            "target_path": "repo/ch_distributions/TeX/ch_distributions.tex",
            "answer_availability": "public_inline",
        })
    for number in EOCE_EXERCISES:
        exercise_key = f"r011/unit/exercise/4.{number}/{EXERCISE_LABELS[number]}"
        unit_specs.append({
            "key": exercise_key,
            "type": "exercise",
            "title": f"Exercise 4.{number}",
            "parent": section_key,
            "order": 3000 + number,
            "source_meta": context["eoce_source_spans"][number],
            "target_meta": context["eoce_target_spans"][number],
            "source_path": "ch_distributions/TeX/normal_distribution.tex",
            "target_path": "repo/ch_distributions/TeX/normal_distribution.tex",
            "answer_availability": "public_appendix" if number in PUBLIC_ANSWERS else "none_public_upstream",
        })
        if number in PUBLIC_ANSWERS:
            unit_specs.append({
                "key": f"r011/unit/solution/4.{number}",
                "type": "solution",
                "title": f"Public solution to exercise 4.{number}",
                "parent": exercise_key,
                "order": 1,
                "source_meta": rebase(context["answer_source_spans"][number], context["answer_authority"], 26871),
                "target_meta": rebase(context["answer_target_spans"][number], context["assembled_answers"], context["answer_target_offset"]),
                "source_path": "extraTeX/eoceSolutions/eoceSolutions.tex",
                "target_path": "repo/extraTeX/eoceSolutions/eoceSolutions.tex",
                "answer_availability": "public_upstream",
            })
        else:
            unit_specs.append({
                "key": f"r011/unit/o001-gap/4.{number}",
                "type": "companion_gap",
                "title": f"O001 mastery-companion answer gap for exercise 4.{number}",
                "parent": exercise_key,
                "order": 1,
                "source_meta": None,
                "target_meta": None,
                "source_path": None,
                "target_path": None,
                "answer_availability": "restricted_not_accessed",
            })
    if len(unit_specs) != 63:
        raise RuntimeError(f"B014 semantic unit count changed: {len(unit_specs)} != 63")

    unit_ids = {spec["key"]: g.stable_id(spec["key"]) for spec in unit_specs}
    for spec in unit_specs:
        is_gap = spec["type"] == "companion_gap"
        parent = unit_ids.get(spec["parent"], spec["parent"])
        source_meta = spec.get("source_meta")
        target_meta = spec.get("target_meta")
        rights = [o001_rights] if is_gap else [upstream_rights, text_rights]
        records["units"].append(record(
            "unit",
            spec["key"],
            unit_type=spec["type"],
            title=spec["title"],
            prerequisite_ids=[previous_section] if spec["key"] == section_key else [],
            answer_availability=spec.get("answer_availability"),
            authoring_mode="independent_original_required" if is_gap else None,
            gap_reason="no_public_answer_upstream" if is_gap else None,
            source_solution_used=False if is_gap else None,
            source_path=spec.get("source_path"),
            source_span=schema_span(source_meta) if source_meta else None,
            source_sha256=source_meta["sha256"] if source_meta else None,
            target_path=spec.get("target_path"),
            target_span=target_meta,
            target_sha256=target_meta["sha256"] if target_meta else None,
            target_identity_status="terminal_contract_bound" if target_meta else "explicit_o001_gap",
            **common_fields(resource_id, edition_id, parent, spec["order"], "en", "queued" if is_gap else "language_reviewed", rights),
        ))

    segment_specs: list[dict[str, Any]] = []
    for source_row, target_row in zip(context["source_chapter_segments"], context["target_chapter_segments"]):
        kind = source_row["kind"]
        segment_specs.append({
            "key": f"r011/segment/b014-{kind}",
            "kind": kind,
            "unit": chapter_key,
            "order": 1 if kind == "chapter_title_hierarchy" else 2,
            "source_raw": context["chapter_source"],
            "source_local": source_row["span"],
            "source_meta": rebase(source_row["span"], context["main_authority"], 0),
            "target_raw": context["chapter_target"],
            "target_local": target_row["span"],
            "target_meta": rebase(target_row["span"], context["assembled_main"], context["chapter_target_offset"]),
            "source_path": "ch_distributions/TeX/ch_distributions.tex",
            "target_path": "repo/ch_distributions/TeX/ch_distributions.tex",
        })
    for index, (source_row, target_row) in enumerate(zip(context["main_source_spans"], context["main_target_spans"]), 1):
        kind, number = source_row["kind"], int(source_row["number"])
        if kind == "worked_example":
            unit_key = f"r011/unit/worked-example/ch04-sec4.1-{number:02d}"
        elif kind == "guided_exercise":
            unit_key = f"r011/unit/guided-exercise/ch04-sec4.1-{number:02d}"
        elif kind == "guided_inline_answer":
            unit_key = f"r011/unit/guided-solution/ch04-sec4.1-{number:02d}"
        else:
            unit_key = section_key
        segment_specs.append({
            "key": f"r011/segment/b014-main-{index:03d}",
            "kind": kind,
            "unit": unit_key,
            "order": index,
            "source_raw": context["main_source"],
            "source_local": source_row["span"],
            "source_meta": rebase(source_row["span"], context["main_authority"], 808),
            "target_raw": context["main_target"],
            "target_local": target_row["span"],
            "target_meta": rebase(target_row["span"], context["assembled_main"], context["main_target_offset"]),
            "source_path": "ch_distributions/TeX/ch_distributions.tex",
            "target_path": "repo/ch_distributions/TeX/ch_distributions.tex",
        })
    for number in EOCE_EXERCISES:
        segment_specs.append({
            "key": f"r011/segment/b014-eoce-{number}",
            "kind": "end-of-section-exercise",
            "unit": f"r011/unit/exercise/4.{number}/{EXERCISE_LABELS[number]}",
            "order": 1,
            "source_raw": context["eoce_authority"],
            "source_local": context["eoce_source_spans"][number],
            "source_meta": context["eoce_source_spans"][number],
            "target_raw": context["eoce_target"],
            "target_local": context["eoce_target_spans"][number],
            "target_meta": context["eoce_target_spans"][number],
            "source_path": "ch_distributions/TeX/normal_distribution.tex",
            "target_path": "repo/ch_distributions/TeX/normal_distribution.tex",
        })
    for number in PUBLIC_ANSWERS:
        segment_specs.append({
            "key": f"r011/segment/b014-answer-{number}",
            "kind": "public_appendix_solution",
            "unit": f"r011/unit/solution/4.{number}",
            "order": 1,
            "source_raw": context["answer_source"],
            "source_local": context["answer_source_spans"][number],
            "source_meta": rebase(context["answer_source_spans"][number], context["answer_authority"], 26871),
            "target_raw": context["answer_target_body"],
            "target_local": context["answer_target_spans"][number],
            "target_meta": rebase(context["answer_target_spans"][number], context["assembled_answers"], context["answer_target_offset"]),
            "source_path": "extraTeX/eoceSolutions/eoceSolutions.tex",
            "target_path": "repo/extraTeX/eoceSolutions/eoceSolutions.tex",
        })
    if len(segment_specs) != 68:
        raise RuntimeError(f"B014 segment count changed: {len(segment_specs)} != 68")

    term_specs = load_term_specs(context["raw"]["controlled_terms"])
    segment_ids: dict[str, str] = {}
    localization_ids: dict[str, str] = {}
    for spec in segment_specs:
        source_text = spec["source_raw"][spec["source_local"]["byte_start"] : spec["source_local"]["byte_end_exclusive"]].decode("utf-8")
        target_text = spec["target_raw"][spec["target_local"]["byte_start"] : spec["target_local"]["byte_end_exclusive"]].decode("utf-8")
        unit_id = unit_ids[spec["unit"]]
        segment_id = g.stable_id(spec["key"])
        localization_key = f"r011/localization/id-ID/b014-{spec['key'].rsplit('/', 1)[-1]}"
        localization_id = g.stable_id(localization_key)
        segment_ids[spec["key"]] = segment_id
        localization_ids[spec["key"]] = localization_id
        records["segments"].append(record(
            "segment",
            spec["key"],
            unit_id=unit_id,
            segment_kind=spec["kind"],
            source_locale="en",
            source_text=source_text,
            protected_tokens=g.protected_tokens(source_text),
            target_locales=["id-ID"],
            source_path=spec["source_path"],
            source_span=schema_span(spec["source_meta"]),
            source_sha256=spec["source_meta"]["sha256"],
            **common_fields(resource_id, edition_id, unit_id, spec["order"], "en", "source_frozen", [upstream_rights]),
        ))
        records["localizations"].append(record(
            "localization",
            localization_key,
            source_segment_id=segment_id,
            unit_id=unit_id,
            source_locale="en",
            target_locale="id-ID",
            target_text=target_text,
            source_protected_tokens=g.protected_tokens(source_text),
            target_protected_tokens=g.protected_tokens(target_text),
            protected_tokens=g.protected_tokens(target_text),
            protected_token_delta={
                "authorized": True,
                "reason": "Terminal B014 QA proves formula, identifier, reference, topology, correction, and localized reflow closure.",
            },
            target_path=spec["target_path"],
            target_span=spec["target_meta"],
            target_sha256=spec["target_meta"]["sha256"],
            target_identity_status="terminal_contract_bound",
            translation_provenance=PROVENANCE,
            candidate_validation_receipt=context["inputs"]["final_translation_qa"]["path"],
            terminology_bindings=[item["source"] for item in term_specs],
            source_path=spec["source_path"],
            source_span=schema_span(spec["source_meta"]),
            source_sha256=spec["source_meta"]["sha256"],
            **common_fields(resource_id, edition_id, segment_id, spec["order"], "id-ID", "language_reviewed", [upstream_rights, text_rights]),
        ))

    concept_ids: dict[str, str] = {}
    for order, item in enumerate(term_specs, 1):
        source_term = item["source"]
        key = f"r011/concept/b014/{slug(source_term)}"
        concept_id = g.stable_id(key)
        concept_ids[source_term] = concept_id
        search_raw = context["chapter_source"] if source_term == "distribution of random variables" else context["main_source"]
        source_offset = 0 if search_raw is context["chapter_source"] else 808
        occurrence = search_raw.lower().find(source_term.encode("utf-8").lower())
        if occurrence >= 0:
            meta = rebase(span_meta(search_raw, occurrence, occurrence + len(source_term.encode("utf-8"))), context["main_authority"], source_offset)
        else:
            meta = span_meta(context["main_authority"], source_offset, source_offset + 1)
        source_path = "ch_distributions/TeX/ch_distributions.tex"
        records["concepts"].append(record(
            "concept",
            key,
            preferred_source_term=source_term,
            definition=f"Chapter 4 Section 4.1 concept indexed as {source_term}.",
            source_path=source_path,
            source_span=schema_span(meta),
            source_sha256=meta["sha256"],
            **common_fields(resource_id, edition_id, None, order, "zxx", "source_frozen", [upstream_rights]),
        ))
        records["terms"].append(record(
            "term",
            f"r011/term/id-ID/b014/{slug(source_term)}",
            source_term=source_term,
            target_term=item["target"],
            concept_id=concept_id,
            scope="statistics / Chapter 4 Section 4.1",
            register="academic",
            variants=item["variants"],
            rejected_forms=[],
            decision=item["decision"],
            decision_reason=item["evidence"],
            evidence=f"{context['inputs']['terminology_qa']['path']}; {context['inputs']['controlled_terms']['path']}",
            field_source_metadata={
                "bibliographic_observations_retained": True,
                "internal_witness_bytes_bundled": False,
                "model": PROVENANCE,
            },
            internal_witness_bytes_excluded=True,
            glossary_lock_status="propagated_to_terminal_b014_candidate",
            source_path=source_path,
            source_span=schema_span(meta),
            source_sha256=meta["sha256"],
            **common_fields(resource_id, edition_id, concept_id, order, "id-ID", "language_reviewed", [upstream_rights, text_rights]),
        ))

    asset_closure = context["asset_closure"]
    if len(asset_closure["pdfs"]) != 21 or len(asset_closure["code"]) != 16:
        raise RuntimeError("B014 asset closure changed")
    asset_ids: dict[str, str] = {}
    producer_by_name: dict[str, str] = {}
    code_rows_by_id: dict[str, dict[str, Any]] = {}
    for order, item in enumerate(asset_closure["code"], 1):
        require(LANE / item["path"], {"bytes": int(item["bytes"]), "sha256": item["sha256"]})
        key = f"r011/asset/b014/source-r/{slug(item['path'].split('ch_distributions/figures/', 1)[-1])}"
        asset_id = g.stable_id(key)
        if Path(item["path"]).name in producer_by_name:
            raise RuntimeError(f"duplicate B014 producer basename: {Path(item['path']).name}")
        producer_by_name[Path(item["path"]).name] = asset_id
        asset_ids[key] = asset_id
        code_rows_by_id[asset_id] = item
        rights = [upstream_rights] + ([package_rights] if item.get("dependencies") else [])
        records["assets"].append(record(
            "asset",
            key,
            asset_kind="source_r_producer",
            path=item["path"],
            bytes=item["bytes"],
            sha256=item["sha256"],
            media_type="text/x-r-source",
            dependencies=item.get("dependencies", []),
            external_local_data_files=item.get("external_local_data_files", []),
            source_path=item["path"],
            source_span=None,
            source_sha256=item["sha256"],
            **common_fields(resource_id, edition_id, unit_ids[section_key], order, "zxx", "source_frozen", rights),
        ))
    pdf_producer_pairs: list[tuple[str, str]] = []
    for order, item in enumerate(asset_closure["pdfs"], 1):
        require(LANE / item["path"], {"bytes": int(item["bytes"]), "sha256": item["sha256"]})
        key = f"r011/asset/b014/source-pdf/{slug(item['path'].split('ch_distributions/figures/', 1)[-1])}"
        asset_id = g.stable_id(key)
        producer_id = producer_by_name.get(item["generation_evidence"])
        if producer_id is None:
            raise RuntimeError(f"missing B014 producer for {item['path']}")
        asset_ids[key] = asset_id
        pdf_producer_pairs.append((producer_id, asset_id))
        records["assets"].append(record(
            "asset",
            key,
            asset_kind="source_figure_pdf_reused_byte_identical",
            path=item["path"],
            bytes=item["bytes"],
            sha256=item["sha256"],
            media_type="application/pdf",
            generation_evidence=item["generation_evidence"],
            source_generator_asset_id=producer_id,
            reader_letter_tokens=item.get("reader_letter_tokens", []),
            localization_disposition=item.get("localization_disposition"),
            semantic_change=False,
            target_locale="zxx",
            source_path=item["path"],
            source_span=None,
            source_sha256=item["sha256"],
            **common_fields(resource_id, edition_id, unit_ids[section_key], order, "zxx", "visually_checked", [upstream_rights]),
        ))
    col_key = "r011/asset/b014/virtual-openintro-package-dataset-COL"
    col_id = g.stable_id(col_key)
    col_descriptor = b"R package openintro; package dataset COL; virtual deterministic runtime dependency\n"
    asset_ids[col_key] = col_id
    records["assets"].append(record(
        "asset",
        col_key,
        asset_kind="virtual_package_dataset_dependency",
        path="R-package:openintro/COL",
        bytes=len(col_descriptor),
        sha256=sha256_bytes(col_descriptor),
        media_type="application/x-r-data",
        package="openintro",
        dataset="COL",
        virtual_dependency=True,
        source_path=None,
        source_span=None,
        source_sha256=sha256_bytes(col_descriptor),
        **common_fields(resource_id, edition_id, unit_ids[section_key], 38, "zxx", "source_frozen", [package_rights]),
    ))
    if len(asset_ids) != 38:
        raise RuntimeError(f"B014 asset record count changed: {len(asset_ids)} != 38")

    correction_ids: dict[str, str] = {}
    correction_rows = list(context["translation_qa"].get("source_corrections", []))
    correction_rows.extend(context["translation_qa"].get("localized_layout_adaptations", []))
    if [row["id"] for row in correction_rows] != [
        *[f"B014-SC{number:03d}" for number in range(1, 12)],
        "B014-LA001",
        "B014-LA002",
    ]:
        raise RuntimeError("B014 typed correction/layout-adaptation closure changed")
    for order, item in enumerate(correction_rows, 1):
        is_layout = item["id"].startswith("B014-LA")
        key = f"r011/correction/b014-{item['id'].lower()}"
        correction_ids[key] = g.stable_id(key)
        records["corrections"].append(record(
            "correction",
            key,
            affected_id=unit_ids[section_key],
            category="localized_layout_adaptation" if is_layout else "source_correction",
            correction_type="reader_reflow_without_content_change" if is_layout else "localized_source_correction",
            summary=f"{item['id']}: {item.get('source_text', item.get('source_layout'))}",
            source_claim=item.get("source_text", item.get("source_layout")),
            proposed_correction=item.get("correction", item.get("localized_layout")),
            rationale=item.get("evidence", item.get("scope", "Explicit derivative-scoped correction.")),
            disposition="applied_in_terminal_b014_candidate",
            confidence="high",
            evidence=f"{item.get('source_location')}; {context['inputs']['final_translation_qa']['path']}",
            upstream_report_disposition="not_upstream_report_candidate" if is_layout else "eligible_for_single_deduplicated_post-corpus_report",
            source_path=None,
            source_span=None,
            source_sha256=None,
            **common_fields(resource_id, edition_id, unit_ids[section_key], order, "id-ID", "language_reviewed", [upstream_rights, text_rights]),
        ))

    evidence_sources: list[tuple[str, str, bytes, str, str, list[str]]] = []
    text_roles = {
        "assembled_answers", "assembled_main", "chapter_opening_fragment", "eoce_fragment",
        "preface", "public_answers_fragment", "section_fragment", "reader_pdf",
    }
    for role, item in sorted(context["inputs"].items()):
        state = "visually_checked" if role in {"reader_pdf", "visual_qa", "source_asset_visual_qa"} else "built" if role in {"build_receipt", "source_manifest", "source_qa", "candidate_builder"} else "language_reviewed"
        rights = [upstream_rights, text_rights] if role in text_roles else []
        evidence_sources.append((
            role,
            f"evidence/b014/{role}-{Path(item['path']).name}",
            context["raw"][role],
            role,
            state,
            rights,
        ))
    evidence_sources.extend([
        ("terminal-contract", "evidence/b014/R011-B014_TERMINAL_INPUTS.json", require(TERMINAL_CONTRACT, TERMINAL_CONTRACT_IDENTITY), "terminal_input_contract", "structurally_verified", []),
        ("backend-prep-audit", "evidence/b014/R011-B014_BACKEND_INPUT_REQUIREMENTS_AND_INDEPENDENT_AUDIT.json", require(PREP_AUDIT, PREP_AUDIT_IDENTITY), "historical_backend_design_audit", "structurally_verified", []),
        ("backend-generator", "evidence/tools/generate_backend_b014.py", require(SCRIPT_PATH), "backend_generator", "structurally_verified", []),
        ("backend-validator", "evidence/tools/validate_backend_b014.py", require(SCRIPTS / "validate_backend_b014.py"), "backend_validator", "structurally_verified", []),
    ])
    if len(evidence_sources) != 27:
        raise RuntimeError(f"B014 evidence artifact count changed: {len(evidence_sources)} != 27")
    artifact_ids: dict[str, str] = {}
    for order, (role, relative, raw_bytes, kind, state, rights) in enumerate(evidence_sources, 1):
        auxiliary[relative] = raw_bytes
        key = f"r011/artifact/b014-{slug(role)}"
        artifact_ids[role] = g.stable_id(key)
        records["artifacts"].append(record(
            "artifact",
            key,
            artifact_kind=kind,
            path=f"qa/b014-backend-final/exports/{relative}",
            bytes=len(raw_bytes),
            sha256=sha256_bytes(raw_bytes),
            result="exact terminal B014 input or isolated backend evidence",
            toolchain=context["build_receipt"].get("toolchain") if role in {"build_receipt", "reader_pdf"} else None,
            build_receipt="qa/b014-backend-final/exports/evidence/b014/build_receipt-CANDIDATE_BUILD_QA_B014.json" if role == "reader_pdf" else None,
            source_path=None,
            source_span=None,
            source_sha256=None,
            provenance=PROVENANCE,
            **common_fields(resource_id, edition_id, edition_id, order, "id-ID" if role in text_roles else "zxx", state, rights),
        ))

    qa_specs = [
        ("base-preservation", "topology", "terminal-contract", "All 4,516 admitted B013 records preserve exact canonical bytes and stable identities."),
        ("translation", "language", "final_translation_qa", "Chapter 4 title/introduction, complete Section 4.1, 6 worked examples, 15 guided exercises and inline answers, EoCE 1--10, five public answers, and five explicit O001 gaps are terminally bound."),
        ("terminology", "language", "terminology_qa", "Thirteen controlled B014 terms are bound to the established Indonesian field-source evidence and glossary."),
        ("asset-code-data-rights-closure", "asset", "asset_closure_qa", "Twenty-one byte-identical source PDFs, sixteen adjacent R producers, the virtual openintro COL dependency, and component rights are explicit."),
        ("source-overlay", "source", "source_qa", "The isolated B014 source overlay and manifest are exact."),
        ("deterministic-build", "build", "build_receipt", "Two independent B014 PDF replays are byte-identical and bind the 427-page reader."),
        ("reader-visual", "visual", "visual_qa", "All 22 required original-detail pages passed primary and independent visual review with zero defects."),
        ("corrections", "correction", "final_translation_qa", "SC001--SC011 and LA001--LA002 are typed, derivative-scoped, and non-silent."),
        ("interoperability", "topology", "backend-prep-audit", "All entity classes, ten schema-bound views, stable locale-neutral identities, and translation-state mappings are emitted; stale arithmetic is superseded by generated semantic counts."),
        ("isolation", "admission", "terminal-contract", "No live backend, canonical source, control, release, Git, publication, credential, network, or upstream state is mutated."),
    ]
    qa_ids: dict[str, str] = {}
    for order, (suffix, qa_type, witness, detail) in enumerate(qa_specs, 1):
        key = f"r011/qa/b014-{suffix}"
        qa_ids[suffix] = g.stable_id(key)
        records["qa_events"].append(record(
            "qa_event",
            key,
            qa_type=qa_type,
            result="passed",
            subject_id=edition_id if suffix in {"base-preservation", "interoperability", "isolation", "deterministic-build", "reader-visual"} else unit_ids[section_key],
            witness_path=f"qa/b014-backend-final/exports/" + next(relative for role, relative, *_ in evidence_sources if role == witness),
            witness_artifact_id=artifact_ids[witness],
            detail=detail,
            provenance=PROVENANCE,
            source_path=None,
            source_span=None,
            source_sha256=None,
            **common_fields(resource_id, edition_id, edition_id, order, "zxx", "structurally_verified", []),
        ))

    relation_order = 1
    for spec in unit_specs:
        parent = unit_ids.get(spec["parent"], spec["parent"])
        add_relation(records, f"r011/relation/b014-contains-{slug(spec['key'])}", "contains", parent, unit_ids[spec["key"]], relation_order, "B014 hierarchy", resource_id, edition_id)
        relation_order += 1
    for spec in segment_specs:
        add_relation(records, f"r011/relation/b014-unit-segment-{slug(spec['key'])}", "contains", unit_ids[spec["unit"]], segment_ids[spec["key"]], relation_order, "unit contains exact source segment", resource_id, edition_id)
        relation_order += 1
        add_relation(records, f"r011/relation/b014-localizes-{slug(spec['key'])}", "localizes", localization_ids[spec["key"]], segment_ids[spec["key"]], relation_order, "terminal id-ID localization", resource_id, edition_id)
        relation_order += 1
    for number in GUIDED_EXERCISES:
        add_relation(records, f"r011/relation/b014-guided-answer-{number}", "answers", unit_ids[f"r011/unit/guided-solution/ch04-sec4.1-{number:02d}"], unit_ids[f"r011/unit/guided-exercise/ch04-sec4.1-{number:02d}"], relation_order, "public inline answer", resource_id, edition_id)
        relation_order += 1
    for number in EOCE_EXERCISES:
        exercise = unit_ids[f"r011/unit/exercise/4.{number}/{EXERCISE_LABELS[number]}"]
        linked = unit_ids[f"r011/unit/{'solution' if number in PUBLIC_ANSWERS else 'o001-gap'}/4.{number}"]
        add_relation(
            records,
            f"r011/relation/b014-exercise-answer-{number}",
            "answers" if number in PUBLIC_ANSWERS else "requires_companion_answer",
            linked if number in PUBLIC_ANSWERS else exercise,
            exercise if number in PUBLIC_ANSWERS else linked,
            relation_order,
            "public upstream answer" if number in PUBLIC_ANSWERS else "explicit O001 gap; restricted solution not accessed",
            resource_id,
            edition_id,
        )
        relation_order += 1
    add_relation(records, "r011/relation/b014-section-follows-b013", "precedes", previous_section, unit_ids[section_key], relation_order, "source order Chapter 3 Section 3.5 to Chapter 4 Section 4.1", resource_id, edition_id)
    relation_order += 1
    add_relation(records, "r011/relation/b014-section-prerequisite-b013", "prerequisite", previous_section, unit_ids[section_key], relation_order, "continuous distributions precede the normal-distribution model", resource_id, edition_id)
    relation_order += 1
    for item in term_specs:
        source_term = item["source"]
        term_id = g.stable_id(f"r011/term/id-ID/b014/{slug(source_term)}")
        add_relation(records, f"r011/relation/b014-lexicalizes-{slug(source_term)}", "lexicalizes", term_id, concept_ids[source_term], relation_order, "terminal B014 terminology", resource_id, edition_id)
        relation_order += 1
        add_relation(records, f"r011/relation/b014-covers-{slug(source_term)}", "covers", unit_ids[section_key] if source_term != "distribution of random variables" else unit_ids[chapter_key], concept_ids[source_term], relation_order, "Chapter 4 / Section 4.1 concept index", resource_id, edition_id)
        relation_order += 1
    probability_id = one(records, "concepts", "r011/concept/probability")["id"]
    continuous_id = one(records, "concepts", "r011/concept/b013/continuous-distribution")["id"]
    prerequisite_edges = [
        (continuous_id, concept_ids["normal distribution"]),
        (concept_ids["normal distribution"], concept_ids["standard normal distribution"]),
        (concept_ids["mean"], concept_ids["Z-score"]),
        (concept_ids["standard deviation"], concept_ids["Z-score"]),
        (probability_id, concept_ids["percentile"]),
        (concept_ids["tail"], concept_ids["tail area"]),
        (concept_ids["standard normal distribution"], concept_ids["tail area"]),
        (concept_ids["standard normal distribution"], concept_ids["probability table"]),
    ]
    for index, (prerequisite_id, dependent_id) in enumerate(prerequisite_edges, 1):
        add_relation(records, f"r011/relation/b014-concept-prerequisite-{index:02d}", "prerequisite", prerequisite_id, dependent_id, relation_order, "locale-neutral mathematical prerequisite", resource_id, edition_id)
        relation_order += 1
    for key, asset_id in asset_ids.items():
        add_relation(records, f"r011/relation/b014-asset-{slug(key)}", "uses_asset", unit_ids[section_key], asset_id, relation_order, "B014 figure/code/data/runtime closure", resource_id, edition_id)
        relation_order += 1
    for producer_id, pdf_id in pdf_producer_pairs:
        add_relation(records, f"r011/relation/b014-produces-{slug(pdf_id)}", "produces", producer_id, pdf_id, relation_order, "upstream R producer generates reused byte-identical PDF", resource_id, edition_id)
        relation_order += 1
    for producer_id, item in code_rows_by_id.items():
        if "package dataset COL" in item.get("dependencies", []):
            add_relation(records, f"r011/relation/b014-col-dependency-{slug(producer_id)}", "depends-on", producer_id, col_id, relation_order, "R producer uses package dataset COL", resource_id, edition_id)
            relation_order += 1
    for role, artifact_id in artifact_ids.items():
        add_relation(records, f"r011/relation/b014-artifact-{slug(role)}", "documents", artifact_id, edition_id, relation_order, "exact B014 evidence", resource_id, edition_id)
        relation_order += 1
    for suffix, qa_id in qa_ids.items():
        witness = next(item[2] for item in qa_specs if item[0] == suffix)
        add_relation(records, f"r011/relation/b014-qa-{slug(suffix)}", "validates", qa_id, artifact_ids[witness], relation_order, "typed B014 QA event", resource_id, edition_id)
        relation_order += 1
    for key, correction_id in correction_ids.items():
        add_relation(records, f"r011/relation/b014-correction-{slug(key)}", "corrects", correction_id, unit_ids[section_key], relation_order, "typed source/layout correction", resource_id, edition_id)
        relation_order += 1
    add_relation(records, "r011/relation/b014-rights-text", "governs", text_rights, unit_ids[chapter_key], relation_order, "localized chapter and section text rights", resource_id, edition_id)
    relation_order += 1
    emitted_relations = relation_order - 1
    if emitted_relations != 383:
        raise RuntimeError(f"B014 relation count changed: {emitted_relations} != 383")

    return records, auxiliary, {
        "base_records": base_records,
        "base_manifest": base_manifest,
        "context": context,
        "resource_id": resource_id,
        "edition_id": edition_id,
        "unit_ids": unit_ids,
        "segment_ids": segment_ids,
        "localization_ids": localization_ids,
        "concept_ids": concept_ids,
        "asset_ids": asset_ids,
        "artifact_ids": artifact_ids,
        "qa_ids": qa_ids,
        "correction_ids": correction_ids,
        "relation_count": emitted_relations,
    }


def payload_record_count(path: str, raw: bytes) -> int | None:
    if path.endswith(".jsonl"):
        return len([line for line in raw.splitlines() if line])
    if path.endswith((".csv", ".tsv")):
        return max(0, len(raw.splitlines()) - 1)
    if path.endswith(".json"):
        return 1
    return None


def build_payloads() -> tuple[dict[str, bytes], dict[str, Any]]:
    records, auxiliary, context = build_records()
    payloads = {relative: raw for relative, raw in auxiliary.items() if relative != "manifest.json"}
    payloads.update({relative: g.jsonl_bytes(records[name]) for name, relative in RECORD_PATHS.items()})
    all_rows = [row for rows in records.values() for row in rows]
    payloads["identity_map.jsonl"] = g.jsonl_bytes({
        "id": row["id"],
        "record_type": row["record_type"],
        "stable_key": row["stable_key"],
        "source_local_ids": row.get("source_local_ids", []),
    } for row in all_rows)
    view_contract = json.loads(auxiliary["schemas/backend-view-columns-v0.1.0.json"])["views"]
    payloads.update(g.build_views(records, view_contract))
    base_counts = {name: int(value) for name, value in context["base_manifest"]["record_counts"].items()}
    counts = {name: len(rows) for name, rows in sorted(records.items())}
    new_counts = {name: counts[name] - base_counts[name] for name in counts}
    manifest = deepcopy(context["base_manifest"])
    manifest.update({
        "backend_id": g.stable_id("r011/backend/b014-final-isolated"),
        "backend_name": "r011-openintro-statistics-id-b014-final-isolated",
        "boundary_id": BOUNDARY_ID,
        "workflow_id": WORKFLOW_ID,
        "recorded_at": RECORDED_AT,
        "scope": "Localized Chapter 4 title/introduction and complete Section 4.1 Normal distribution / Distribusi normal through EoCE 1--10 and public answers 1/3/5/7/9, ending immediately before geomDist.",
        "base_preservation": {
            "admitted_base_boundary": BASE_BOUNDARY_ID,
            "admitted_base_record_count": BASE_RECORD_COUNT,
            "base_manifest": {"path": "backend/exports/manifest.json", **BASE_MANIFEST_IDENTITY},
            "base_inventory": BASE_INVENTORY_IDENTITY,
            "base_records_preserved_exact": True,
            "policy": "Every admitted B013 typed record retains exact canonical record bytes and stable identity; live backend is read-only.",
        },
        "source_application": {
            "terminal_contract": {"path": TERMINAL_CONTRACT.relative_to(LANE).as_posix(), **TERMINAL_CONTRACT_IDENTITY},
            "terminal_inputs": context["context"]["inputs"],
            "canonical_source_mutated": False,
            "terminal_identity_fail_closed": True,
        },
        "record_count": sum(counts.values()),
        "record_counts": counts,
        "base_record_counts": base_counts,
        "new_b014_record_counts": new_counts,
        "new_b014_record_count": sum(new_counts.values()),
        "topology": {
            "units": new_counts["units"],
            "segments": new_counts["segments"],
            "localizations": new_counts["localizations"],
            "chapter_title_hierarchy_segments": 1,
            "chapter_intro_segments": 1,
            "section_prose_segments": 15,
            "subsections": 5,
            "worked_examples": WORKED_EXAMPLES,
            "guided_exercises": GUIDED_EXERCISES,
            "guided_inline_public_answers": GUIDED_EXERCISES,
            "exercises": EOCE_EXERCISES,
            "public_answers": PUBLIC_ANSWERS,
            "o001_gaps": O001_GAPS,
            "assets": new_counts["assets"],
            "relations_emitted": context["relation_count"],
            "next_source_anchor": "geomDist",
        },
        "asset_closure": {
            "source_figure_pdfs_reused_byte_identical": 21,
            "source_r_producers": 16,
            "virtual_openintro_COL_dependency": 1,
            "localized_pdf_derivatives_required": 0,
            "component_rights_closure": context["context"]["inputs"]["component_rights_closure"],
            "receipt": context["context"]["inputs"]["asset_closure_qa"],
            "restricted_or_internal_witness_bytes_bundled": False,
        },
        "correction_closure": {
            "source_corrections": 11,
            "localized_layout_adaptations": 2,
            "typed_correction_records": 13,
            "silent_source_mutations": 0,
            "upstream_contact": False,
        },
        "o001_closure": {
            "companion_gap_units": O001_GAPS,
            "source_solutions_used": False,
            "restricted_solutions_accessed_or_invented": False,
        },
        "build_binding": {
            "source_manifest": context["context"]["inputs"]["source_manifest"],
            "source_qa": context["context"]["inputs"]["source_qa"],
            "build_receipt": context["context"]["inputs"]["build_receipt"],
            "pdf": context["context"]["inputs"]["reader_pdf"],
            "visual_receipt": context["context"]["inputs"]["visual_qa"],
            "promoted": False,
        },
        "terminology": {
            "decisions": {item["source"]: item["target"] for item in load_term_specs(context["context"]["raw"]["controlled_terms"])},
            "terminology_qa": context["context"]["inputs"]["terminology_qa"],
            "controlled_terms": context["context"]["inputs"]["controlled_terms"],
            "internal_witness_bytes_bundled": False,
            "model": PROVENANCE,
        },
        "stage_state": {
            "status": "isolated_b014_final_generated",
            "boundary_admitted": False,
            "live_backend_mutated": False,
            "canonical_source_mutated_by_backend_tools": False,
            "controls_mutated": False,
            "output_or_release_mutated": False,
            "promotion_performed": False,
            "publication_performed": False,
            "git_used": False,
            "network_used": False,
            "upstream_contact": False,
        },
        "admission_eligibility": "ready_for_separate_guarded_admission_transaction",
        "provenance": PROVENANCE,
        "files": [],
    })
    manifest["interoperability"]["round_trip_checked"] = True
    for relative in sorted(payloads):
        raw = payloads[relative]
        manifest["files"].append({
            "path": relative,
            "bytes": len(raw),
            "sha256": sha256_bytes(raw),
            "records": payload_record_count(relative, raw),
        })
    payloads["manifest.json"] = canonical_json(manifest)
    context["records"] = records
    context["manifest"] = manifest
    return payloads, context


def validate_payloads(payloads: dict[str, bytes], context: dict[str, Any]) -> dict[str, Any]:
    records = context["records"]
    base_records = context["base_records"]
    all_rows = [row for rows in records.values() for row in rows]
    if sum(len(rows) for rows in base_records.values()) != BASE_RECORD_COUNT:
        raise RuntimeError("base record count changed during append")
    for name in RECORD_PATHS:
        before = {row["id"]: g.canonical_json(row).encode("utf-8") for row in base_records[name]}
        after = {row["id"]: g.canonical_json(row).encode("utf-8") for row in records[name]}
        if any(after.get(record_id) != raw for record_id, raw in before.items()):
            raise RuntimeError(f"B013 base record bytes changed in {name}")
    ids = [row["id"] for row in all_rows]
    keys = [row["stable_key"] for row in all_rows]
    if len(ids) != len(set(ids)) or len(keys) != len(set(keys)):
        raise RuntimeError("duplicate record identity")
    id_set = set(ids)
    for row in all_rows:
        for field in (
            "resource_id", "edition_id", "parent_id", "concept_id", "source_segment_id",
            "subject_id", "affected_id", "from_id", "to_id", "unit_id",
            "witness_artifact_id", "source_asset_id", "source_generator_asset_id",
            "localization_producer_id",
        ):
            value = row.get(field)
            if value is not None and value not in id_set:
                raise RuntimeError(f"unresolved {field}: {row['stable_key']} -> {value}")
        for field in ("rights_component_ids", "concept_ids", "prerequisite_ids"):
            for value in row.get(field, []):
                if value not in id_set:
                    raise RuntimeError(f"unresolved {field}: {row['stable_key']} -> {value}")
    schema_paths = [
        "schemas/backend-record-v0.1.0.schema.json",
        "schemas/backend-manifest-v0.1.0.schema.json",
        "schemas/backend-receipt-v0.1.0.schema.json",
    ]
    schemas = {path: json.loads(payloads[path]) for path in schema_paths}
    for schema in schemas.values():
        jsonschema.Draft202012Validator.check_schema(schema)
    record_validator = jsonschema.Draft202012Validator(
        schemas[schema_paths[0]], format_checker=jsonschema.FormatChecker()
    )
    new_rows = [row for row in all_rows if row.get("boundary_id") == BOUNDARY_ID]
    for row in new_rows:
        errors = sorted(record_validator.iter_errors(row), key=lambda item: list(item.path))
        if errors:
            raise RuntimeError(f"B014 record schema failure {row['stable_key']}: {errors[0].message}")
    jsonschema.Draft202012Validator(
        schemas[schema_paths[1]], format_checker=jsonschema.FormatChecker()
    ).validate(json.loads(payloads["manifest.json"]))
    view_contract = json.loads(payloads["schemas/backend-view-columns-v0.1.0.json"])["views"]
    rebuilt = g.build_views(records, view_contract)
    if set(rebuilt) != set(context["manifest"]["interoperability"]["required_views"]):
        raise RuntimeError("required ten-view closure changed")
    for path, raw in rebuilt.items():
        if payloads[path] != raw or next(csv.reader(raw.decode("utf-8").splitlines()), []) != view_contract[path]:
            raise RuntimeError(f"view replay failure: {path}")
    exercise_view = {
        row["exercise_id"]: row
        for row in csv.DictReader(payloads["views/exercises_answers.csv"].decode("utf-8").splitlines())
    }
    by_key = {row["stable_key"]: row for row in records["units"]}
    for number in EOCE_EXERCISES:
        exercise = by_key[f"r011/unit/exercise/4.{number}/{EXERCISE_LABELS[number]}"]
        view = exercise_view[exercise["id"]]
        if number in PUBLIC_ANSWERS:
            if view["answer_id"] != by_key[f"r011/unit/solution/4.{number}"]["id"] or view["o001_gap_id"]:
                raise RuntimeError(f"public answer view mismatch for 4.{number}")
        else:
            if view["o001_gap_id"] != by_key[f"r011/unit/o001-gap/4.{number}"]["id"] or view["answer_id"]:
                raise RuntimeError(f"O001 gap view mismatch for 4.{number}")
    counts = {name: len(rows) for name, rows in records.items()}
    base_counts = context["base_manifest"]["record_counts"]
    deltas = {name: counts[name] - int(base_counts[name]) for name in counts}
    required_deltas = {
        "artifacts": 27,
        "assets": 38,
        "concepts": 13,
        "corrections": 13,
        "courses": 0,
        "editions": 0,
        "localizations": 68,
        "programs": 0,
        "qa_events": 10,
        "relations": 383,
        "resources": 0,
        "rights": 1,
        "segments": 68,
        "terms": 13,
        "units": 63,
    }
    if deltas != required_deltas:
        raise RuntimeError(f"B014 required class delta mismatch: {deltas} != {required_deltas}")
    if sum(deltas.values()) != 697 or len(all_rows) != 5213 or len(new_rows) != 697:
        raise RuntimeError("B014 recomputed total record closure failed")
    gaps = [
        row for row in records["units"]
        if row.get("boundary_id") == BOUNDARY_ID and row.get("unit_type") == "companion_gap"
    ]
    if len(gaps) != 5 or any(
        row.get("source_solution_used") is not False or row.get("source_path") is not None
        for row in gaps
    ):
        raise RuntimeError("B014 explicit O001 gap closure failed")
    if sum(row.get("boundary_id") == BOUNDARY_ID for row in records["segments"]) != 68:
        raise RuntimeError("B014 segment closure failed")
    if sum(row.get("boundary_id") == BOUNDARY_ID for row in records["localizations"]) != 68:
        raise RuntimeError("B014 localization closure failed")
    if sum(row.get("boundary_id") == BOUNDARY_ID for row in records["assets"]) != 38:
        raise RuntimeError("B014 asset closure failed")
    correction_keys = {
        row["stable_key"] for row in records["corrections"] if row.get("boundary_id") == BOUNDARY_ID
    }
    if correction_keys != {
        *{f"r011/correction/b014-b014-sc{number:03d}" for number in range(1, 12)},
        "r011/correction/b014-b014-la001",
        "r011/correction/b014-b014-la002",
    }:
        raise RuntimeError("B014 correction ID closure failed")
    manifest_files = {entry["path"]: entry for entry in context["manifest"]["files"]}
    if set(manifest_files) != set(payloads) - {"manifest.json"}:
        raise RuntimeError("manifest path inventory closure failed")
    for relative, entry in manifest_files.items():
        raw = payloads[relative]
        expected = {
            "path": relative,
            "bytes": len(raw),
            "sha256": sha256_bytes(raw),
            "records": payload_record_count(relative, raw),
        }
        if entry != expected:
            raise RuntimeError(f"manifest identity mismatch: {relative}")
    return {
        "record_count": len(all_rows),
        "record_counts": counts,
        "new_record_counts": deltas,
        "new_record_count": len(new_rows),
        "base_records_preserved_exact": True,
        "schema_validated_new_records": len(new_rows),
        "required_views": sorted(rebuilt),
        "entity_classes": sorted(set(row["record_type"] for row in all_rows)),
        "semantic_units": 63,
        "segments": 68,
        "localizations": 68,
        "assets": 38,
        "concepts": 13,
        "terms": 13,
        "typed_corrections_and_layout_adaptations": 13,
        "public_answers": PUBLIC_ANSWERS,
        "o001_gaps": O001_GAPS,
        "next_source_anchor": "geomDist",
    }


def write_output(output: Path, payloads: dict[str, bytes]) -> dict[str, Any]:
    resolved = output.resolve()
    if resolved.parent != STAGE_ROOT.resolve() or resolved.name not in {"run-a", "run-b", "exports"}:
        raise RuntimeError(f"refusing output outside exact B014 final runs: {resolved}")
    if resolved.exists():
        existing = inventory(resolved)
        expected_paths = set(payloads)
        observed_paths = {item["path"] for item in existing["inventory"]}
        if observed_paths - expected_paths:
            raise RuntimeError(
                f"refusing to replace B014 final run with unexpected files: {sorted(observed_paths - expected_paths)[:3]}"
            )
    for relative, raw in sorted(payloads.items()):
        destination = resolved / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() and destination.read_bytes() != raw:
            destination.write_bytes(raw)
        elif not destination.exists():
            destination.write_bytes(raw)
    observed = inventory(resolved)
    if observed["files"] != len(payloads):
        raise RuntimeError("written B014 inventory file count mismatch")
    return observed


def compare_runs(left: Path, right: Path) -> dict[str, Any]:
    left_inventory = inventory(left)
    right_inventory = inventory(right)
    if left_inventory != right_inventory:
        raise RuntimeError("independent B014 final run inventories differ")
    for item in left_inventory["inventory"]:
        if (left / item["path"]).read_bytes() != (right / item["path"]).read_bytes():
            raise RuntimeError(f"independent B014 payload differs: {item['path']}")
    return {key: left_inventory[key] for key in ("files", "bytes", "sha256")}


def run(output: Path | None, validate_only: Path | None) -> dict[str, Any]:
    payloads, context = build_payloads()
    validation = validate_payloads(payloads, context)
    written = write_output(output, payloads) if output is not None else None
    if validate_only is not None:
        expected_paths = set(payloads)
        observed = inventory(validate_only)
        if {row["path"] for row in observed["inventory"]} != expected_paths:
            raise RuntimeError("on-disk B014 path inventory mismatch")
        for relative, raw in payloads.items():
            if require(validate_only / relative) != raw:
                raise RuntimeError(f"on-disk B014 validation mismatch: {relative}")
        written = observed
    return {
        "boundary_id": BOUNDARY_ID,
        "status": "PASS_B014_FINAL_ISOLATED_BACKEND",
        **validation,
        "deterministic_source_of_truth": True,
        "output": str(output or validate_only),
        "inventory": {key: written[key] for key in ("files", "bytes", "sha256")} if written else None,
        "live_backend_mutated": False,
        "canonical_source_mutated": False,
        "controls_mutated": False,
        "release_mutated": False,
        "git_used": False,
        "network_used": False,
        "publication_performed": False,
        "upstream_contact": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--validate-only", type=Path)
    args = parser.parse_args()
    if args.output is None and args.validate_only is None:
        raise SystemExit("use --output PATH or --validate-only PATH")
    if args.output is not None and args.validate_only is not None:
        raise SystemExit("choose exactly one mode")
    print(json.dumps(run(args.output, args.validate_only), ensure_ascii=False, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
