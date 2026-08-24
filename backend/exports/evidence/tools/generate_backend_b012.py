#!/usr/bin/env python3
"""Generate the terminal deterministic R011-B012 backend append.

The admitted R011-B011 backend is an immutable, hash-bound preimage.  This
program writes only the explicit isolated ``qa/b012-backend-final`` stages; it
never mutates the live backend, canonical sources, reader output, Git, or a
remote service.  Run with Python ``-B``.
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
STAGE_ROOT = LANE / "qa" / "b012-backend-final"
sys.path.insert(0, str(SCRIPTS))
import generate_backend_b011 as b011  # noqa: E402

g = b011.g
RECORD_PATHS = b011.RECORD_PATHS

BOUNDARY_ID = "R011-B012"
BASE_BOUNDARY_ID = "R011-B011"
SCHEMA_VERSION = "0.1.0"
RECORDED_AT = "2026-08-24T20:00:00+02:00"
WORKFLOW_ID = "r011-openintro-statistics-id-b012-backend-final"
PROVENANCE = "OpenAI Codex gpt-5.6-sol, Ultra"
AUTHORITY_COMMIT = "fee25091fb24e89c36296fd67c48c1fcf7a93b6e"
AUTHORITY_TREE = "d61cc601e7d97759ce805900520f784d02a0489e"

BASE_EXPORTS = LANE / "backend" / "exports"
BASE_MANIFEST = BASE_EXPORTS / "manifest.json"
TERMINAL_CONTRACT = (
    LANE / "qa" / "b012-backend-prep" / "R011-B012_TERMINAL_INPUTS.json"
)
REQUIREMENTS = (
    LANE / "qa" / "b012-backend-prep" / "R011-B012_BACKEND_INPUT_REQUIREMENTS.json"
)
AUTHORITY_ROOT = LANE / "authority" / "upstream" / (
    "openintro-statistics-fee25091fb24e89c36296fd67c48c1fcf7a93b6e"
)
MAIN_AUTHORITY = AUTHORITY_ROOT / "ch_probability" / "TeX" / "ch_probability.tex"
EOCE_AUTHORITY = AUTHORITY_ROOT / "ch_probability" / "TeX" / "random_variables.tex"
ANSWER_AUTHORITY = AUTHORITY_ROOT / "extraTeX" / "eoceSolutions" / "eoceSolutions.tex"

RUN_A = STAGE_ROOT / "run-a"
RUN_B = STAGE_ROOT / "run-b"
VALIDATION_RECEIPT = STAGE_ROOT / "R011-B012_BACKEND_VALIDATION_RECEIPT.json"

BASE_MANIFEST_IDENTITY = {
    "bytes": 49827,
    "sha256": "fe5c6f7bf42ea05285b4dd3243547bb6877007077161bcf9882eaf98598fb689",
}
BASE_INVENTORY_IDENTITY = {
    "files": 256,
    "bytes": 80072989,
    "sha256": "50f2f14939bfdfaabab28a4a8cbddb2506444ad2ac751a932da16a11b5b4b79c",
}
BASE_RECORD_COUNT = 3828
TERMINAL_CONTRACT_IDENTITY = {
    "bytes": 5353,
    "sha256": "48a533ad50085eb3c24d24a1067adde8e71cc1689c993a108e699677237a8369",
}
REQUIREMENTS_IDENTITY = {
    "bytes": 14982,
    "sha256": "261d78f17c458d5b01cdd4fac0434a9c4eef346673a9e3c503196e4aeff6aa89",
}

PUBLIC_ANSWERS = [29, 31, 33, 35]
O001_GAPS = [30, 32, 34, 36]
EOCE_EXERCISES = list(range(29, 37))
GUIDED_EXERCISES = list(range(1, 10))
WORKED_EXAMPLES = list(range(1, 9))


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
    return {key: int(meta[key]) for key in ("line_start", "line_end", "byte_start", "byte_end_exclusive")}


def marker_spans(raw: bytes, numbers: Iterable[int]) -> dict[int, dict[str, Any]]:
    wanted = list(numbers)
    lines, starts = line_table(raw)
    found: list[tuple[int, int]] = []
    for index, line in enumerate(lines):
        match = re.fullmatch(rb"%\s*(\d+)\r?\n?", line)
        if match and int(match.group(1)) in set(wanted):
            found.append((int(match.group(1)), starts[index]))
    if [number for number, _ in found] != wanted:
        raise RuntimeError(f"marker topology changed: {[number for number, _ in found]} != {wanted}")
    result: dict[int, dict[str, Any]] = {}
    for index, (number, start) in enumerate(found):
        end = found[index + 1][1] if index + 1 < len(found) else len(raw)
        while end > start and raw[end - 1:end] in (b"\n", b"\r", b" ", b"\t"):
            end -= 1
        result[number] = span_meta(raw, start, end)
    return result


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
    return {"files": len(rows), "bytes": sum(row["bytes"] for row in rows), "sha256": digest, "inventory": rows}


def load_base() -> tuple[dict[str, list[dict[str, Any]]], dict[str, bytes], dict[str, Any]]:
    manifest_raw = require(BASE_MANIFEST, BASE_MANIFEST_IDENTITY)
    manifest = json.loads(manifest_raw)
    if manifest.get("backend_name") != "r011-openintro-statistics-id-b011-final-isolated":
        raise RuntimeError("live base is not exact admitted B011")
    if sum(int(value) for value in manifest["record_counts"].values()) != BASE_RECORD_COUNT:
        raise RuntimeError("B011 base record count changed")
    observed_inventory = inventory(BASE_EXPORTS)
    if {key: observed_inventory[key] for key in ("files", "bytes", "sha256")} != BASE_INVENTORY_IDENTITY:
        raise RuntimeError("B011 base export inventory changed")
    by_path = {entry["path"]: entry for entry in manifest["files"]}
    records: dict[str, list[dict[str, Any]]] = {}
    for name, relative in RECORD_PATHS.items():
        entry = by_path[relative]
        raw = require(BASE_EXPORTS / relative, {"bytes": entry["bytes"], "sha256": entry["sha256"]})
        rows = load_jsonl(raw)
        if len(rows) != int(entry["records"]) or g.jsonl_bytes(rows) != raw:
            raise RuntimeError(f"noncanonical B011 typed payload: {relative}")
        records[name] = rows
    auxiliary = {
        path.relative_to(BASE_EXPORTS).as_posix(): path.read_bytes()
        for path in sorted(BASE_EXPORTS.rglob("*")) if path.is_file()
    }
    return records, auxiliary, manifest


def load_terminal() -> tuple[dict[str, Any], dict[str, Any]]:
    contract = json.loads(require(TERMINAL_CONTRACT, TERMINAL_CONTRACT_IDENTITY))
    requirements = json.loads(require(REQUIREMENTS, REQUIREMENTS_IDENTITY))
    if contract.get("boundary_id") != BOUNDARY_ID or contract.get("status") != "READY_TERMINAL_INPUTS":
        raise RuntimeError("B012 terminal contract is not ready")
    closure = contract.get("closure", {})
    if (
        closure.get("worked_examples") != 8
        or closure.get("guided_exercises") != 9
        or closure.get("guided_inline_public_answers") != 9
        or closure.get("eoce_exercises") != EOCE_EXERCISES
        or closure.get("public_answers") != PUBLIC_ANSWERS
        or closure.get("o001_gaps") != O001_GAPS
        or closure.get("typed_corrections") != 3
        or closure.get("restricted_solutions_accessed_or_invented") is not False
    ):
        raise RuntimeError("B012 terminal closure changed")
    if set(contract.get("inputs", {})) != {
        item["key"] for item in requirements["required_terminal_inputs"]
    }:
        raise RuntimeError("B012 terminal role closure changed")
    for role, item in sorted(contract["inputs"].items()):
        path = LANE / item["path"]
        require(path, {"bytes": int(item["bytes"]), "sha256": item["sha256"]})
    return contract, requirements


def balanced_command_end(raw: bytes, start: int, command: bytes) -> int:
    open_at = raw.find(b"{", start + len(command))
    if open_at < 0:
        raise RuntimeError(f"missing argument for {command!r}")
    depth = 0
    for index in range(open_at, len(raw)):
        byte = raw[index:index + 1]
        if byte == b"{" and (index == 0 or raw[index - 1:index] != b"\\"):
            depth += 1
        elif byte == b"}" and (index == 0 or raw[index - 1:index] != b"\\"):
            depth -= 1
            if depth == 0:
                return index + 1
    raise RuntimeError(f"unterminated argument for {command!r}")


def structural_spans(raw: bytes) -> list[dict[str, Any]]:
    """Losslessly partition Section 3.4 around examples, guides and answers."""
    blocks: list[tuple[int, int, str, int]] = []
    for begin, end_token, kind, expected in (
        (b"\\begin{examplewrap}", b"\\end{examplewrap}", "worked_example", 8),
        (b"\\begin{exercisewrap}", b"\\end{exercisewrap}", "guided_exercise", 9),
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
            if raw[end:end + 2] == b"\r\n":
                end += 2
            elif raw[end:end + 1] == b"\n":
                end += 1
            count += 1
            blocks.append((start, end, kind, count))
            cursor = end
        if count != expected:
            raise RuntimeError(f"B012 {kind} topology changed: {count} != {expected}")
    cursor = count = 0
    command = b"\\footnotetext"
    while True:
        start = raw.find(command, cursor)
        if start < 0:
            break
        end = balanced_command_end(raw, start, command)
        if raw[end:end + 2] == b"\r\n":
            end += 2
        elif raw[end:end + 1] == b"\n":
            end += 1
        count += 1
        blocks.append((start, end, "guided_inline_answer", count))
        cursor = end
    if count != 9:
        raise RuntimeError(f"B012 inline-answer topology changed: {count} != 9")
    blocks.sort()
    for left, right in zip(blocks, blocks[1:]):
        if left[1] > right[0]:
            raise RuntimeError("overlapping B012 structural blocks")
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
    return result


def rebase(meta: dict[str, Any], full_raw: bytes, offset: int) -> dict[str, Any]:
    return span_meta(full_raw, offset + int(meta["byte_start"]), offset + int(meta["byte_end_exclusive"]))


def subsection_spans(raw: bytes) -> list[dict[str, Any]]:
    matches = list(re.finditer(rb"\\subsection\{([^}]+)\}", raw))
    if len(matches) != 4:
        raise RuntimeError(f"B012 subsection topology changed: {len(matches)} != 4")
    result = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(raw)
        result.append({
            "number": index + 1,
            "title": match.group(1).decode("utf-8"),
            "span": span_meta(raw, match.start(), end),
        })
    return result


def add_relation(
    records: dict[str, list[dict[str, Any]]], key: str, relation_type: str,
    from_id: str, to_id: str, order: int, qualifier: str,
    resource_id: str, edition_id: str,
) -> None:
    records["relations"].append(record(
        "relation", key, relation_type=relation_type, from_id=from_id,
        to_id=to_id, qualifier=qualifier, resource_id=resource_id,
        edition_id=edition_id, source_local_ids=[BOUNDARY_ID], parent_id=None,
        order=order, locale="zxx", translation_state="structurally_verified",
        rights_component_ids=[], boundary_id=BOUNDARY_ID, source_path=None,
        source_span=None, source_sha256=None, status="active",
    ))


def load_context() -> dict[str, Any]:
    contract, requirements = load_terminal()
    inputs = contract["inputs"]
    raw = {key: require(LANE / value["path"], {"bytes": value["bytes"], "sha256": value["sha256"]}) for key, value in inputs.items()}
    main_authority = require(MAIN_AUTHORITY, {"bytes": 132799, "sha256": "4f07fcf0e71e52bc99657835d5cced47b10ce9fc66b23dce156d400840690361"})
    eoce_authority = require(EOCE_AUTHORITY, {"bytes": 4804, "sha256": "e6b7dd329d07781270b3545bc9ad641cc0d9c2972df274ea082119e9341ebc6c"})
    answer_authority = require(ANSWER_AUTHORITY, {"bytes": 106045, "sha256": "6c4e01376db4c023cc7b3f9949490e57220ef1cb831c580da71efde6ce723268"})
    main_source = main_authority[98603:124925]
    answer_source = answer_authority[24101:24671]
    if {"bytes": len(main_source), "sha256": sha256_bytes(main_source)} != {"bytes": 26322, "sha256": "eaf09daf3d0e101261615bbae0fc897171173373d119435a2317514c98136283"}:
        raise RuntimeError("B012 authority Section 3.4 slice changed")
    if {"bytes": len(answer_source), "sha256": sha256_bytes(answer_source)} != {"bytes": 570, "sha256": "b05b301640ecfb6b84c623c9b8e26ab8b6eda9db4a6eebac4055512aa233b905"}:
        raise RuntimeError("B012 public answer authority slice changed")
    main_target = raw["main_fragment"]
    eoce_target = raw["eoce_fragment"]
    answer_target = raw["public_answers_fragment"]
    assembled_main = raw["assembled_main"]
    assembled_answers = raw["assembled_answers"]
    main_target_offset = assembled_main.find(main_target)
    answer_body_start = answer_target.find(b"% 29")
    if answer_body_start < 0:
        raise RuntimeError("terminal B012 answer body start disappeared")
    answer_body = answer_target[answer_body_start:].rstrip(b"\r\n")
    answer_target_offset = assembled_answers.find(answer_body)
    if main_target_offset < 0 or assembled_main.find(main_target, main_target_offset + 1) >= 0:
        raise RuntimeError("terminal B012 main fragment assembly binding changed")
    if answer_target_offset < 0 or assembled_answers.find(answer_body, answer_target_offset + 1) >= 0:
        raise RuntimeError("terminal B012 answer fragment assembly binding changed")
    source_spans = structural_spans(main_source)
    target_spans = structural_spans(main_target)
    if [(row["kind"], row["number"]) for row in source_spans] != [(row["kind"], row["number"]) for row in target_spans]:
        raise RuntimeError("B012 structural source/target segmentation changed")
    source_subsections = subsection_spans(main_source)
    target_subsections = subsection_spans(main_target)
    return {
        "contract": contract, "requirements": requirements, "inputs": inputs, "raw": raw,
        "main_authority": main_authority, "eoce_authority": eoce_authority,
        "answer_authority": answer_authority, "main_source": main_source,
        "answer_source": answer_source, "main_target": main_target,
        "eoce_target": eoce_target, "answer_target": answer_target,
        "answer_target_body": answer_body,
        "assembled_main": assembled_main, "assembled_answers": assembled_answers,
        "main_target_offset": main_target_offset, "answer_target_offset": answer_target_offset,
        "main_source_spans": source_spans, "main_target_spans": target_spans,
        "source_subsections": source_subsections, "target_subsections": target_subsections,
        "eoce_source_spans": marker_spans(eoce_authority, EOCE_EXERCISES),
        "eoce_target_spans": marker_spans(eoce_target, EOCE_EXERCISES),
        "answer_source_spans": marker_spans(answer_source, PUBLIC_ANSWERS),
        "answer_target_spans": marker_spans(answer_body, PUBLIC_ANSWERS),
        "translation_qa": json.loads(raw["final_translation_qa"]),
        "terminology_qa": json.loads(raw["terminology_qa"]),
        "asset_closure": json.loads(raw["asset_closure_qa"]),
        "build_receipt": json.loads(raw["build_receipt"]),
        "visual_qa": json.loads(raw["visual_qa"]),
    }


EXERCISE_LABELS = {
    29: "college_smokers", 30: "ace_of_clubs", 31: "hearts", 32: "worth_it",
    33: "portfolio_return", 34: "baggage_fees", 35: "roulette_american", 36: "roulette_european",
}

TERM_SPECS = [
    ("random variable", "variabel acak", ["peubah acak", "variabel random"]),
    ("probability distribution", "distribusi peluang", ["distribusi probabilitas"]),
    ("discrete random variable", "variabel acak diskret", []),
    ("continuous random variable", "variabel acak kontinu", []),
    ("expected value", "nilai harapan", ["ekspektasi"]),
    ("expectation", "nilai harapan", ["ekspektasi"]),
    ("variance", "varians", ["variansi"]),
    ("standard deviation", "simpangan baku", ["deviasi standar"]),
    ("linear combination", "kombinasi linear", []),
    ("independent", "saling independen", ["saling bebas"]),
]


def common_fields(resource_id: str, edition_id: str, parent_id: str | None, order: int | None, locale: str, state: str, rights: list[str]) -> dict[str, Any]:
    return {
        "resource_id": resource_id, "edition_id": edition_id,
        "source_local_ids": [BOUNDARY_ID], "parent_id": parent_id, "order": order,
        "locale": locale, "translation_state": state,
        "rights_component_ids": rights, "boundary_id": BOUNDARY_ID,
        "status": "active",
    }


def build_records() -> tuple[dict[str, list[dict[str, Any]]], dict[str, bytes], dict[str, Any]]:
    base_records, auxiliary, base_manifest = load_base()
    records = deepcopy(base_records)
    context = load_context()
    resource_id = one(records, "resources", "r011/resource/openintro-statistics")["id"]
    edition_id = one(records, "editions", "r011/edition/fee25091")["id"]
    upstream_rights = one(records, "rights", "r011/rights/upstream-cc-by-sa-3.0")["id"]
    o001_rights = one(records, "rights", "r011/rights/o001-original-companion-planned")["id"]
    package_rights = one(records, "rights", "r011/rights/openintro-r-package-gpl-3")["id"]
    previous_section = one(records, "units", "r011/unit/source-label/smallPop")["id"]
    chapter_id = one(records, "units", "r011/unit/source-label/ch_probability")["id"]

    text_rights_key = "r011/rights/b012-localized-section-text"
    asset_rights_key = "r011/rights/b012-localized-figure-derivatives"
    text_rights = g.stable_id(text_rights_key)
    asset_rights = g.stable_id(asset_rights_key)
    for key, scope in (
        (text_rights_key, "B012 Indonesian Section 3.4 text, EoCE 29--36, public answers 29/31/33/35, and bounded preface terminology overlay."),
        (asset_rights_key, "B012 Indonesian label-only PDF and deterministic R producer derivatives for bookCostDist and changeInLeonardsStockPortfolioFor36Months."),
    ):
        records["rights"].append(record(
            "rights", key, component_scope=scope, license_expression="CC-BY-SA-3.0",
            verification_status="verified against R011-B012_ASSET_CLOSURE.json",
            attribution="OpenIntro Statistics source authors; Indonesian derivative changes identified by R011-B012.",
            change_notice="Source and localized derivative bytes remain separately hash-bound.",
            non_endorsement="No author, institution, publisher, or tool-provider endorsement implied.",
            publication_effect="Isolated terminal B012 backend; admission and publication are separate transactions.",
            source_path="scratch/b012-assets/R011-B012_ASSET_CLOSURE.json", source_span=None,
            source_sha256=context["inputs"]["asset_closure_qa"]["sha256"],
            **common_fields(resource_id, edition_id, resource_id, len(records["rights"]) + 1, "zxx", "structurally_verified", []),
        ))

    section_key = "r011/unit/source-label/randomVariablesSection"
    unit_specs: list[dict[str, Any]] = [{
        "key": section_key, "type": "section", "title": "Random variables",
        "parent": chapter_id, "order": 4,
        "source_meta": span_meta(context["main_authority"], 98603, 124925),
        "target_meta": span_meta(context["assembled_main"], context["main_target_offset"], context["main_target_offset"] + len(context["main_target"])),
        "source_path": "ch_probability/TeX/ch_probability.tex", "target_path": "repo/ch_probability/TeX/ch_probability.tex",
    }]
    source_subs = context["source_subsections"]
    target_subs = context["target_subsections"]
    subsection_keys = []
    for source_sub, target_sub in zip(source_subs, target_subs):
        key = f"r011/unit/b012/subsection-{source_sub['number']:02d}-{slug(source_sub['title'])}"
        subsection_keys.append(key)
        unit_specs.append({
            "key": key, "type": "subsection", "title": source_sub["title"],
            "parent": section_key, "order": source_sub["number"] * 100,
            "source_meta": rebase(source_sub["span"], context["main_authority"], 98603),
            "target_meta": rebase(target_sub["span"], context["assembled_main"], context["main_target_offset"]),
            "source_path": "ch_probability/TeX/ch_probability.tex", "target_path": "repo/ch_probability/TeX/ch_probability.tex",
        })
    source_by_sig = {(row["kind"], row["number"]): row for row in context["main_source_spans"]}
    target_by_sig = {(row["kind"], row["number"]): row for row in context["main_target_spans"]}
    for number in WORKED_EXAMPLES:
        source_row, target_row = source_by_sig[("worked_example", number)], target_by_sig[("worked_example", number)]
        unit_specs.append({
            "key": f"r011/unit/worked-example/ch03-sec3.4-{number:02d}", "type": "worked_example",
            "title": f"Section 3.4 worked example {number}", "parent": section_key, "order": 1000 + number * 10,
            "source_meta": rebase(source_row["span"], context["main_authority"], 98603),
            "target_meta": rebase(target_row["span"], context["assembled_main"], context["main_target_offset"]),
            "source_path": "ch_probability/TeX/ch_probability.tex", "target_path": "repo/ch_probability/TeX/ch_probability.tex",
        })
    for number in GUIDED_EXERCISES:
        source_row, target_row = source_by_sig[("guided_exercise", number)], target_by_sig[("guided_exercise", number)]
        guide_key = f"r011/unit/guided-exercise/ch03-sec3.4-{number:02d}"
        unit_specs.append({
            "key": guide_key, "type": "guided_exercise", "title": f"Section 3.4 guided exercise {number}",
            "parent": section_key, "order": 2000 + number * 10,
            "source_meta": rebase(source_row["span"], context["main_authority"], 98603),
            "target_meta": rebase(target_row["span"], context["assembled_main"], context["main_target_offset"]),
            "source_path": "ch_probability/TeX/ch_probability.tex", "target_path": "repo/ch_probability/TeX/ch_probability.tex",
            "answer_availability": "inline_public_feedback",
        })
        source_answer, target_answer = source_by_sig[("guided_inline_answer", number)], target_by_sig[("guided_inline_answer", number)]
        unit_specs.append({
            "key": f"r011/unit/guided-solution/ch03-sec3.4-{number:02d}", "type": "solution",
            "title": f"Inline public answer to Section 3.4 guided exercise {number}",
            "parent": guide_key, "order": 1,
            "source_meta": rebase(source_answer["span"], context["main_authority"], 98603),
            "target_meta": rebase(target_answer["span"], context["assembled_main"], context["main_target_offset"]),
            "source_path": "ch_probability/TeX/ch_probability.tex", "target_path": "repo/ch_probability/TeX/ch_probability.tex",
            "answer_availability": "public_inline",
        })
    for number in EOCE_EXERCISES:
        exercise_key = f"r011/unit/exercise/3.{number}/{EXERCISE_LABELS[number]}"
        unit_specs.append({
            "key": exercise_key, "type": "exercise", "title": f"Exercise 3.{number}",
            "parent": section_key, "order": 3000 + number,
            "source_meta": context["eoce_source_spans"][number], "target_meta": context["eoce_target_spans"][number],
            "source_path": "ch_probability/TeX/random_variables.tex", "target_path": "repo/ch_probability/TeX/random_variables.tex",
            "answer_availability": "public_appendix" if number in PUBLIC_ANSWERS else "none_public_upstream",
        })
        if number in PUBLIC_ANSWERS:
            unit_specs.append({
                "key": f"r011/unit/solution/3.{number}", "type": "solution", "title": f"Public solution to exercise 3.{number}",
                "parent": exercise_key, "order": 1,
                "source_meta": rebase(context["answer_source_spans"][number], context["answer_authority"], 24101),
                "target_meta": rebase(context["answer_target_spans"][number], context["assembled_answers"], context["answer_target_offset"]),
                "source_path": "extraTeX/eoceSolutions/eoceSolutions.tex", "target_path": "repo/extraTeX/eoceSolutions/eoceSolutions.tex",
                "answer_availability": "public_upstream",
            })
        else:
            unit_specs.append({
                "key": f"r011/unit/o001-gap/3.{number}", "type": "companion_gap", "title": f"O001 mastery-companion answer gap for exercise 3.{number}",
                "parent": exercise_key, "order": 1, "source_meta": None, "target_meta": None,
                "source_path": None, "target_path": None, "answer_availability": "restricted_not_accessed",
            })

    unit_ids = {spec["key"]: g.stable_id(spec["key"]) for spec in unit_specs}
    for spec in unit_specs:
        is_gap = spec["type"] == "companion_gap"
        parent = spec["parent"] if isinstance(spec["parent"], str) and spec["parent"] in unit_ids.values() else unit_ids.get(spec["parent"], spec["parent"])
        source_meta, target_meta = spec.get("source_meta"), spec.get("target_meta")
        rights = [o001_rights] if is_gap else [upstream_rights, text_rights]
        records["units"].append(record(
            "unit", spec["key"], unit_type=spec["type"], title=spec["title"],
            prerequisite_ids=[previous_section] if spec["key"] == section_key else [],
            answer_availability=spec.get("answer_availability"),
            authoring_mode="independent_original_required" if is_gap else None,
            gap_reason="no_public_answer_upstream" if is_gap else None,
            source_solution_used=False if is_gap else None,
            source_path=spec.get("source_path"), source_span=schema_span(source_meta) if source_meta else None,
            source_sha256=source_meta["sha256"] if source_meta else None,
            target_path=spec.get("target_path"), target_span=target_meta,
            target_sha256=target_meta["sha256"] if target_meta else None,
            target_identity_status="terminal_contract_bound" if target_meta else "explicit_o001_gap",
            **common_fields(resource_id, edition_id, parent, spec["order"], "en", "queued" if is_gap else "language_reviewed", rights),
        ))

    segment_specs: list[dict[str, Any]] = []
    for index, (source_row, target_row) in enumerate(zip(context["main_source_spans"], context["main_target_spans"]), 1):
        kind, number = source_row["kind"], int(source_row["number"])
        if kind == "worked_example":
            unit_key = f"r011/unit/worked-example/ch03-sec3.4-{number:02d}"
        elif kind == "guided_exercise":
            unit_key = f"r011/unit/guided-exercise/ch03-sec3.4-{number:02d}"
        elif kind == "guided_inline_answer":
            unit_key = f"r011/unit/guided-solution/ch03-sec3.4-{number:02d}"
        else:
            unit_key = section_key
        segment_specs.append({
            "key": f"r011/segment/b012-main-{index:03d}", "kind": kind, "unit": unit_key, "order": index,
            "source_raw": context["main_source"], "source_local": source_row["span"],
            "source_meta": rebase(source_row["span"], context["main_authority"], 98603),
            "target_raw": context["main_target"], "target_local": target_row["span"],
            "target_meta": rebase(target_row["span"], context["assembled_main"], context["main_target_offset"]),
            "source_path": "ch_probability/TeX/ch_probability.tex", "target_path": "repo/ch_probability/TeX/ch_probability.tex",
        })
    for number in EOCE_EXERCISES:
        segment_specs.append({
            "key": f"r011/segment/b012-eoce-{number}", "kind": "end-of-section-exercise",
            "unit": f"r011/unit/exercise/3.{number}/{EXERCISE_LABELS[number]}", "order": 1,
            "source_raw": context["eoce_authority"], "source_local": context["eoce_source_spans"][number], "source_meta": context["eoce_source_spans"][number],
            "target_raw": context["eoce_target"], "target_local": context["eoce_target_spans"][number], "target_meta": context["eoce_target_spans"][number],
            "source_path": "ch_probability/TeX/random_variables.tex", "target_path": "repo/ch_probability/TeX/random_variables.tex",
        })
    for number in PUBLIC_ANSWERS:
        segment_specs.append({
            "key": f"r011/segment/b012-answer-{number}", "kind": "public_appendix_solution",
            "unit": f"r011/unit/solution/3.{number}", "order": 1,
            "source_raw": context["answer_source"], "source_local": context["answer_source_spans"][number],
            "source_meta": rebase(context["answer_source_spans"][number], context["answer_authority"], 24101),
            "target_raw": context["answer_target_body"], "target_local": context["answer_target_spans"][number],
            "target_meta": rebase(context["answer_target_spans"][number], context["assembled_answers"], context["answer_target_offset"]),
            "source_path": "extraTeX/eoceSolutions/eoceSolutions.tex", "target_path": "repo/extraTeX/eoceSolutions/eoceSolutions.tex",
        })
    segment_ids: dict[str, str] = {}
    localization_ids: dict[str, str] = {}
    for spec in segment_specs:
        source_text = spec["source_raw"][spec["source_local"]["byte_start"]:spec["source_local"]["byte_end_exclusive"]].decode("utf-8")
        target_text = spec["target_raw"][spec["target_local"]["byte_start"]:spec["target_local"]["byte_end_exclusive"]].decode("utf-8")
        unit_id = unit_ids[spec["unit"]]
        segment_id = g.stable_id(spec["key"])
        localization_key = f"r011/localization/id-ID/b012-{spec['key'].rsplit('/', 1)[-1]}"
        localization_id = g.stable_id(localization_key)
        segment_ids[spec["key"]] = segment_id
        localization_ids[spec["key"]] = localization_id
        records["segments"].append(record(
            "segment", spec["key"], unit_id=unit_id, segment_kind=spec["kind"],
            source_locale="en", source_text=source_text, protected_tokens=g.protected_tokens(source_text),
            target_locales=["id-ID"], source_path=spec["source_path"],
            source_span=schema_span(spec["source_meta"]), source_sha256=spec["source_meta"]["sha256"],
            **common_fields(resource_id, edition_id, unit_id, spec["order"], "en", "source_frozen", [upstream_rights]),
        ))
        records["localizations"].append(record(
            "localization", localization_key, source_segment_id=segment_id, unit_id=unit_id,
            source_locale="en", target_locale="id-ID", target_text=target_text,
            source_protected_tokens=g.protected_tokens(source_text), target_protected_tokens=g.protected_tokens(target_text),
            protected_tokens=g.protected_tokens(target_text), protected_token_delta={"authorized": True, "reason": "Terminal B012 translation QA proves structural, formula, numeric, label, reference, and authorized layout/localization deltas."},
            target_path=spec["target_path"], target_span=spec["target_meta"], target_sha256=spec["target_meta"]["sha256"],
            target_identity_status="terminal_contract_bound", translation_provenance=PROVENANCE,
            candidate_validation_receipt=context["inputs"]["final_translation_qa"]["path"],
            terminology_bindings=[source for source, _target, _variants in TERM_SPECS],
            source_path=spec["source_path"], source_span=schema_span(spec["source_meta"]), source_sha256=spec["source_meta"]["sha256"],
            **common_fields(resource_id, edition_id, segment_id, spec["order"], "id-ID", "language_reviewed", [upstream_rights, text_rights]),
        ))

    term_qa = context["terminology_qa"]
    concept_ids: dict[str, str] = {}
    for order, (source_term, target_term, variants) in enumerate(TERM_SPECS, 1):
        key = f"r011/concept/b012/{slug(source_term)}"
        concept_id = g.stable_id(key)
        concept_ids[source_term] = concept_id
        occurrence = context["main_source"].lower().find(source_term.encode("utf-8"))
        meta = rebase(span_meta(context["main_source"], occurrence, occurrence + len(source_term.encode("utf-8"))), context["main_authority"], 98603) if occurrence >= 0 else span_meta(context["main_authority"], 98603, 98604)
        records["concepts"].append(record(
            "concept", key, preferred_source_term=source_term,
            definition=f"Section 3.4 probability concept indexed as {source_term}.",
            source_path="ch_probability/TeX/ch_probability.tex", source_span=schema_span(meta), source_sha256=meta["sha256"],
            **common_fields(resource_id, edition_id, None, order, "zxx", "source_frozen", [upstream_rights]),
        ))
        records["terms"].append(record(
            "term", f"r011/term/id-ID/b012/{slug(source_term)}", source_term=source_term,
            target_term=target_term, concept_id=concept_id, scope="probability / Chapter 3 Section 3.4",
            register="academic", variants=variants, rejected_forms=[],
            decision="Controlled B012 field-usage decision propagated to terminal candidate.",
            decision_reason="Direct Indonesian probability and statistics field witnesses plus edition consistency.",
            evidence=f"{context['inputs']['terminology_qa']['path']}; {context['inputs']['controlled_terms']['path']}",
            field_source_metadata={"bibliographic_observations_retained": True, "internal_witness_bytes_bundled": False, "model": PROVENANCE},
            internal_witness_bytes_excluded=True, glossary_lock_status="propagated_to_terminal_b012_candidate",
            source_path="ch_probability/TeX/ch_probability.tex", source_span=schema_span(meta), source_sha256=meta["sha256"],
            **common_fields(resource_id, edition_id, concept_id, order, "id-ID", "language_reviewed", [upstream_rights, text_rights]),
        ))

    asset_ids: dict[str, str] = {}
    asset_closure = context["asset_closure"]
    for order, figure in enumerate(asset_closure["figures"], 1):
        figure_id = figure["id"]
        source_pdf_key = f"r011/asset/b012/source-pdf/{figure_id}"
        source_r_key = f"r011/asset/b012/source-producer/{figure_id}"
        for key, kind, item, media, rights in (
            (source_pdf_key, "source_figure_pdf", figure["source_pdf"], "application/pdf", [upstream_rights]),
            (source_r_key, "source_r_producer", figure["upstream_producer"], "text/x-r-source", [upstream_rights, package_rights]),
        ):
            asset_ids[key] = g.stable_id(key)
            records["assets"].append(record(
                "asset", key, asset_kind=kind, path=item["path"], bytes=item["bytes"], sha256=item["sha256"],
                media_type=media, dependencies=figure.get("upstream_producer", {}).get("dependencies", []),
                reader_visible_language=figure.get("reader_visible_language", []), source_path=item["path"], source_span=None,
                source_sha256=item["sha256"], **common_fields(resource_id, edition_id, section_key and unit_ids[section_key], order, "en", "source_frozen", rights),
            ))
        if "localized_pdf" in figure:
            for suffix, kind, item, media in (
                ("localized-pdf", "localized_figure_pdf", figure["localized_pdf"], "application/pdf"),
                ("localized-producer", "localized_r_producer", figure["localized_r_producer"], "text/x-r-source"),
            ):
                key = f"r011/asset/b012/{suffix}/{figure_id}"
                asset_ids[key] = g.stable_id(key)
                records["assets"].append(record(
                    "asset", key, asset_kind=kind, path=item["path"], bytes=item["bytes"], sha256=item["sha256"],
                    media_type=media, target_locale="id-ID", semantic_change=False,
                    source_asset_id=asset_ids[source_pdf_key if suffix == "localized-pdf" else source_r_key],
                    source_path=item["path"], source_span=None, source_sha256=item["sha256"],
                    **common_fields(resource_id, edition_id, asset_ids[source_pdf_key if suffix == "localized-pdf" else source_r_key], order, "id-ID", "visually_checked" if suffix == "localized-pdf" else "structurally_verified", [upstream_rights, asset_rights] + ([package_rights] if suffix == "localized-producer" else [])),
                ))
    dataset_key = "r011/asset/b012/package-dataset/openintro-stocks-18"
    asset_ids[dataset_key] = g.stable_id(dataset_key)
    records["assets"].append(record(
        "asset", dataset_key, asset_kind="package_dataset_dependency", path="openintro::stocks_18",
        bytes=None, sha256=None, media_type="application/x-r-data", redistributed=False,
        usage="Historical upstream producer dependency only; localized build consumes committed PDF bytes.",
        source_path=None, source_span=None, source_sha256=None,
        **common_fields(resource_id, edition_id, unit_ids[section_key], 99, "zxx", "source_frozen", [package_rights]),
    ))

    correction_ids: dict[str, str] = {}
    correction_rows = context["translation_qa"].get("source_grammar_and_accessibility_corrections")
    if correction_rows is None:
        candidate_binding = context["translation_qa"].get("candidate_receipt", {})
        candidate_path = LANE / candidate_binding["path"]
        candidate_raw = require(candidate_path, {"bytes": candidate_binding["bytes"], "sha256": candidate_binding["sha256"]})
        candidate_receipt = json.loads(candidate_raw)
        correction_rows = candidate_receipt["source_grammar_and_accessibility_corrections"]
    if len(correction_rows) != 3:
        raise RuntimeError("B012 typed source-correction count changed")
    for order, item in enumerate(correction_rows, 1):
        key = f"r011/correction/b012-source-accessibility-{order:02d}"
        correction_ids[key] = g.stable_id(key)
        records["corrections"].append(record(
            "correction", key, affected_id=unit_ids[section_key], category="source_accessibility",
            correction_type="localized_accessibility_correction", summary=item["source_issue"],
            source_claim=item["source_issue"], proposed_correction=item["candidate_rendering"],
            rationale="High-confidence source accessibility/grammar defect corrected only in the Indonesian derivative.",
            disposition="applied_in_terminal_b012_candidate", confidence="high",
            evidence=f"source line {item['source_line']}; {context['inputs']['final_translation_qa']['path']}",
            upstream_report_disposition="eligible_for_single_deduplicated_post-corpus_report",
            source_path="ch_probability/TeX/ch_probability.tex", source_span=None, source_sha256=None,
            **common_fields(resource_id, edition_id, unit_ids[section_key], order, "id-ID", "language_reviewed", [upstream_rights, text_rights]),
        ))

    evidence_sources: list[tuple[str, str, bytes, str, str, list[str]]] = []
    for role, item in sorted(context["inputs"].items()):
        evidence_sources.append((role, f"evidence/b012/{role}-{Path(item['path']).name}", context["raw"][role], role, "visually_checked" if role in {"reader_pdf", "visual_qa"} else "built" if role in {"build_receipt", "source_manifest", "source_qa"} else "language_reviewed", [upstream_rights, text_rights] if role in {"main_fragment", "eoce_fragment", "public_answers_fragment", "assembled_main", "assembled_answers", "reader_pdf"} else []))
    evidence_sources.extend([
        ("terminal-contract", "evidence/b012/R011-B012_TERMINAL_INPUTS.json", require(TERMINAL_CONTRACT, TERMINAL_CONTRACT_IDENTITY), "terminal_input_contract", "structurally_verified", []),
        ("requirements", "evidence/b012/R011-B012_BACKEND_INPUT_REQUIREMENTS.json", require(REQUIREMENTS, REQUIREMENTS_IDENTITY), "backend_requirements", "structurally_verified", []),
        ("backend-generator", "evidence/tools/generate_backend_b012.py", require(SCRIPT_PATH), "backend_generator", "structurally_verified", []),
    ])
    validator_path = SCRIPTS / "validate_backend_b012.py"
    if validator_path.is_file():
        evidence_sources.append(("backend-validator", "evidence/tools/validate_backend_b012.py", require(validator_path), "backend_validator", "structurally_verified", []))
    artifact_ids: dict[str, str] = {}
    for order, (role, relative, raw, kind, state, rights) in enumerate(evidence_sources, 1):
        auxiliary[relative] = raw
        key = f"r011/artifact/b012-{slug(role)}"
        artifact_ids[role] = g.stable_id(key)
        records["artifacts"].append(record(
            "artifact", key, artifact_kind=kind, path=f"qa/b012-backend-final/exports/{relative}",
            bytes=len(raw), sha256=sha256_bytes(raw), result="exact terminal B012 input or isolated backend evidence",
            toolchain=context["build_receipt"].get("toolchain") if role in {"build_receipt", "reader_pdf"} else None,
            build_receipt="qa/b012-backend-final/exports/evidence/b012/build_receipt-CANDIDATE_BUILD_QA_B012.json" if role == "reader_pdf" else None,
            source_path=None, source_span=None, source_sha256=None, provenance=PROVENANCE,
            **common_fields(resource_id, edition_id, edition_id, order, "id-ID" if role in {"main_fragment", "eoce_fragment", "public_answers_fragment", "assembled_main", "assembled_answers", "reader_pdf"} else "zxx", state, rights),
        ))

    qa_specs = [
        ("base-preservation", "topology", "terminal-contract", "All 3,828 admitted B011 records preserve exact canonical bytes and stable identities."),
        ("translation", "language", "final_translation_qa", "Complete Section 3.4, eight worked examples, nine guided exercises and answers, EoCE 29--36, and public odd answers are terminally bound."),
        ("terminology", "language", "terminology_qa", "Ten controlled terms and accepted synonyms are bound without bundling restricted field-witness bytes."),
        ("asset-closure", "asset", "asset_closure_qa", "Four source PDF/R pairs, two localized PDF/R pairs, accessibility descriptions, and code/data dependencies are explicit."),
        ("source-overlay", "source", "source_qa", "The isolated B012 source overlay and manifest are exact."),
        ("deterministic-build", "build", "build_receipt", "Two independent B012 PDF replays are byte-identical and bind the 427-page reader."),
        ("reader-visual", "visual", "visual_qa", "Terminal boundary visual QA reports zero remaining defects."),
        ("corrections", "correction", "final_translation_qa", "Three high-confidence source accessibility/grammar corrections are typed and derivative-scoped."),
        ("interoperability", "topology", "requirements", "All required entity classes, ten schema-bound views, and translation-state mappings are emitted."),
        ("isolation", "admission", "terminal-contract", "No live backend, canonical source, release, Git, publication, credential, or upstream state is mutated."),
    ]
    qa_ids: dict[str, str] = {}
    for order, (suffix, qa_type, witness, detail) in enumerate(qa_specs, 1):
        key = f"r011/qa/b012-{suffix}"
        qa_ids[suffix] = g.stable_id(key)
        records["qa_events"].append(record(
            "qa_event", key, qa_type=qa_type, result="passed", subject_id=edition_id if suffix in {"base-preservation", "interoperability", "isolation", "deterministic-build", "reader-visual"} else unit_ids[section_key],
            witness_path=f"qa/b012-backend-final/exports/" + next(relative for role, relative, *_rest in evidence_sources if role == witness),
            witness_artifact_id=artifact_ids[witness], detail=detail, provenance=PROVENANCE,
            source_path=None, source_span=None, source_sha256=None,
            **common_fields(resource_id, edition_id, edition_id, order, "zxx", "structurally_verified", []),
        ))

    relation_order = 1
    for spec in unit_specs:
        parent = unit_ids.get(spec["parent"], spec["parent"])
        add_relation(records, f"r011/relation/b012-contains-{slug(spec['key'])}", "contains", parent, unit_ids[spec["key"]], relation_order, "B012 hierarchy", resource_id, edition_id); relation_order += 1
    for spec in segment_specs:
        add_relation(records, f"r011/relation/b012-unit-segment-{slug(spec['key'])}", "contains", unit_ids[spec["unit"]], segment_ids[spec["key"]], relation_order, "unit contains exact source segment", resource_id, edition_id); relation_order += 1
        add_relation(records, f"r011/relation/b012-localizes-{slug(spec['key'])}", "localizes", localization_ids[spec["key"]], segment_ids[spec["key"]], relation_order, "terminal id-ID localization", resource_id, edition_id); relation_order += 1
    for number in GUIDED_EXERCISES:
        add_relation(records, f"r011/relation/b012-guided-answer-{number}", "answers", unit_ids[f"r011/unit/guided-solution/ch03-sec3.4-{number:02d}"], unit_ids[f"r011/unit/guided-exercise/ch03-sec3.4-{number:02d}"], relation_order, "public inline answer", resource_id, edition_id); relation_order += 1
    for number in EOCE_EXERCISES:
        exercise = unit_ids[f"r011/unit/exercise/3.{number}/{EXERCISE_LABELS[number]}"]
        linked = unit_ids[f"r011/unit/{'solution' if number in PUBLIC_ANSWERS else 'o001-gap'}/3.{number}"]
        add_relation(records, f"r011/relation/b012-exercise-answer-{number}", "answers" if number in PUBLIC_ANSWERS else "requires_companion_answer", linked if number in PUBLIC_ANSWERS else exercise, exercise if number in PUBLIC_ANSWERS else linked, relation_order, "public upstream answer" if number in PUBLIC_ANSWERS else "explicit O001 gap; restricted solution not accessed", resource_id, edition_id); relation_order += 1
    add_relation(records, "r011/relation/b012-section-follows-b011", "precedes", previous_section, unit_ids[section_key], relation_order, "source order Section 3.3 to 3.4", resource_id, edition_id); relation_order += 1
    for source_term, _target, _variants in TERM_SPECS:
        term_id = g.stable_id(f"r011/term/id-ID/b012/{slug(source_term)}")
        add_relation(records, f"r011/relation/b012-lexicalizes-{slug(source_term)}", "lexicalizes", term_id, concept_ids[source_term], relation_order, "terminal B012 terminology", resource_id, edition_id); relation_order += 1
        add_relation(records, f"r011/relation/b012-covers-{slug(source_term)}", "covers", unit_ids[section_key], concept_ids[source_term], relation_order, "Section 3.4 concept index", resource_id, edition_id); relation_order += 1
    for key, asset_id in asset_ids.items():
        add_relation(records, f"r011/relation/b012-asset-{slug(key)}", "uses_asset", unit_ids[section_key], asset_id, relation_order, "B012 figure/code/data closure", resource_id, edition_id); relation_order += 1
    for role, artifact_id in artifact_ids.items():
        add_relation(records, f"r011/relation/b012-artifact-{slug(role)}", "documents", artifact_id, edition_id, relation_order, "exact B012 evidence", resource_id, edition_id); relation_order += 1
    for suffix, qa_id in qa_ids.items():
        witness = next(item[2] for item in qa_specs if item[0] == suffix)
        add_relation(records, f"r011/relation/b012-qa-{slug(suffix)}", "validates", qa_id, artifact_ids[witness], relation_order, "typed B012 QA event", resource_id, edition_id); relation_order += 1
    for key, correction_id in correction_ids.items():
        add_relation(records, f"r011/relation/b012-correction-{slug(key)}", "corrects", correction_id, unit_ids[section_key], relation_order, "typed source accessibility correction", resource_id, edition_id); relation_order += 1
    add_relation(records, "r011/relation/b012-rights-text", "governs", text_rights, unit_ids[section_key], relation_order, "localized text rights", resource_id, edition_id); relation_order += 1
    add_relation(records, "r011/relation/b012-rights-assets", "governs", asset_rights, unit_ids[section_key], relation_order, "localized asset rights", resource_id, edition_id); relation_order += 1

    return records, auxiliary, {
        "base_records": base_records, "base_manifest": base_manifest, "context": context,
        "resource_id": resource_id, "edition_id": edition_id, "unit_ids": unit_ids,
        "segment_ids": segment_ids, "localization_ids": localization_ids,
        "artifact_ids": artifact_ids, "qa_ids": qa_ids, "asset_ids": asset_ids,
        "relation_count": relation_order - 1,
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
        "id": row["id"], "record_type": row["record_type"], "stable_key": row["stable_key"], "source_local_ids": row.get("source_local_ids", [])
    } for row in all_rows)
    view_contract = json.loads(auxiliary["schemas/backend-view-columns-v0.1.0.json"])["views"]
    payloads.update(g.build_views(records, view_contract))
    base_counts = {name: int(value) for name, value in context["base_manifest"]["record_counts"].items()}
    counts = {name: len(rows) for name, rows in sorted(records.items())}
    new_counts = {name: counts[name] - base_counts[name] for name in counts}
    manifest = deepcopy(context["base_manifest"])
    manifest.update({
        "backend_id": g.stable_id("r011/backend/b012-final-isolated"),
        "backend_name": "r011-openintro-statistics-id-b012-final-isolated",
        "boundary_id": BOUNDARY_ID,
        "workflow_id": WORKFLOW_ID, "recorded_at": RECORDED_AT,
        "scope": "Complete Section 3.4 Random variables / Variabel acak through EoCE 29--36 and public answers 29/31/33/35, ending before contDist.",
        "base_preservation": {
            "admitted_base_boundary": BASE_BOUNDARY_ID, "admitted_base_record_count": BASE_RECORD_COUNT,
            "base_manifest": {"path": "backend/exports/manifest.json", **BASE_MANIFEST_IDENTITY},
            "base_inventory": BASE_INVENTORY_IDENTITY, "base_records_preserved_exact": True,
            "policy": "Every admitted B011 typed record retains exact canonical record bytes and stable identity; live backend is read-only.",
        },
        "source_application": {
            "terminal_contract": {"path": TERMINAL_CONTRACT.relative_to(LANE).as_posix(), **TERMINAL_CONTRACT_IDENTITY},
            "terminal_inputs": context["context"]["inputs"], "canonical_source_mutated": False,
            "terminal_identity_fail_closed": True,
        },
        "record_count": sum(counts.values()), "record_counts": counts, "base_record_counts": base_counts,
        "new_b012_record_counts": new_counts, "new_b012_record_count": sum(new_counts.values()),
        "topology": {
            "units": new_counts["units"], "segments": new_counts["segments"], "localizations": new_counts["localizations"],
            "worked_examples": WORKED_EXAMPLES, "guided_exercises": GUIDED_EXERCISES,
            "guided_inline_public_answers": GUIDED_EXERCISES, "exercises": EOCE_EXERCISES,
            "public_answers": PUBLIC_ANSWERS, "o001_gaps": O001_GAPS,
            "assets": new_counts["assets"], "relations_emitted": context["relation_count"], "next_source_anchor": "contDist",
        },
        "asset_closure": {
            "source_figure_producer_pairs": 4, "localized_pdf_producer_pairs": 2,
            "package_dataset_dependencies": ["openintro::stocks_18"], "restricted_or_internal_witness_bytes_bundled": False,
            "receipt": {"path": context["context"]["inputs"]["asset_closure_qa"]["path"], "bytes": context["context"]["inputs"]["asset_closure_qa"]["bytes"], "sha256": context["context"]["inputs"]["asset_closure_qa"]["sha256"]},
        },
        "correction_closure": {"typed_corrections": 3, "silent_source_mutations": 0, "upstream_contact": False},
        "build_binding": {
            "source_manifest": context["context"]["inputs"]["source_manifest"], "source_qa": context["context"]["inputs"]["source_qa"],
            "build_receipt": context["context"]["inputs"]["build_receipt"], "pdf": context["context"]["inputs"]["reader_pdf"],
            "visual_receipt": context["context"]["inputs"]["visual_qa"], "promoted": False,
        },
        "terminology": {
            "decisions": {source: target for source, target, _variants in TERM_SPECS},
            "terminology_qa": context["context"]["inputs"]["terminology_qa"], "controlled_terms": context["context"]["inputs"]["controlled_terms"],
            "internal_witness_bytes_bundled": False, "model": PROVENANCE,
        },
        "stage_state": {
            "status": "isolated_b012_final_generated", "boundary_admitted": False,
            "live_backend_mutated": False, "canonical_source_mutated_by_backend_tools": False,
            "output_or_release_mutated": False, "promotion_performed": False,
            "publication_performed": False, "git_used": False, "upstream_contact": False,
        },
        "admission_eligibility": "ready_for_separate_guarded_admission_transaction",
        "provenance": PROVENANCE, "files": [],
    })
    manifest["interoperability"]["round_trip_checked"] = True
    for relative in sorted(payloads):
        raw = payloads[relative]
        manifest["files"].append({"path": relative, "bytes": len(raw), "sha256": sha256_bytes(raw), "records": payload_record_count(relative, raw)})
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
            raise RuntimeError(f"B011 base record bytes changed in {name}")
    ids = [row["id"] for row in all_rows]
    keys = [row["stable_key"] for row in all_rows]
    if len(ids) != len(set(ids)) or len(keys) != len(set(keys)):
        raise RuntimeError("duplicate record identity")
    id_set = set(ids)
    for row in all_rows:
        for field in ("resource_id", "edition_id", "parent_id", "concept_id", "source_segment_id", "subject_id", "affected_id", "from_id", "to_id", "unit_id", "witness_artifact_id", "source_asset_id"):
            value = row.get(field)
            if value is not None and value not in id_set:
                raise RuntimeError(f"unresolved {field}: {row['stable_key']} -> {value}")
        for field in ("rights_component_ids", "concept_ids", "prerequisite_ids"):
            for value in row.get(field, []):
                if value not in id_set:
                    raise RuntimeError(f"unresolved {field}: {row['stable_key']} -> {value}")
    schema_paths = ["schemas/backend-record-v0.1.0.schema.json", "schemas/backend-manifest-v0.1.0.schema.json", "schemas/backend-receipt-v0.1.0.schema.json"]
    schemas = {path: json.loads(payloads[path]) for path in schema_paths}
    for schema in schemas.values():
        jsonschema.Draft202012Validator.check_schema(schema)
    record_validator = jsonschema.Draft202012Validator(schemas[schema_paths[0]], format_checker=jsonschema.FormatChecker())
    new_rows = [row for row in all_rows if row.get("boundary_id") == BOUNDARY_ID]
    for row in new_rows:
        errors = sorted(record_validator.iter_errors(row), key=lambda item: list(item.path))
        if errors:
            raise RuntimeError(f"B012 record schema failure {row['stable_key']}: {errors[0].message}")
    jsonschema.Draft202012Validator(schemas[schema_paths[1]], format_checker=jsonschema.FormatChecker()).validate(json.loads(payloads["manifest.json"]))
    view_contract = json.loads(payloads["schemas/backend-view-columns-v0.1.0.json"])["views"]
    rebuilt = g.build_views(records, view_contract)
    if set(rebuilt) != set(context["manifest"]["interoperability"]["required_views"]):
        raise RuntimeError("required ten-view closure changed")
    for path, raw in rebuilt.items():
        if payloads[path] != raw or next(csv.reader(raw.decode("utf-8").splitlines()), []) != view_contract[path]:
            raise RuntimeError(f"view replay failure: {path}")
    exercise_view = {row["exercise_id"]: row for row in csv.DictReader(payloads["views/exercises_answers.csv"].decode("utf-8").splitlines())}
    by_key = {row["stable_key"]: row for row in records["units"]}
    for number in EOCE_EXERCISES:
        exercise = by_key[f"r011/unit/exercise/3.{number}/{EXERCISE_LABELS[number]}"]
        view = exercise_view[exercise["id"]]
        if number in PUBLIC_ANSWERS:
            if view["answer_id"] != by_key[f"r011/unit/solution/3.{number}"]["id"] or view["o001_gap_id"]:
                raise RuntimeError(f"public answer view mismatch for 3.{number}")
        else:
            if view["o001_gap_id"] != by_key[f"r011/unit/o001-gap/3.{number}"]["id"] or view["answer_id"]:
                raise RuntimeError(f"O001 gap view mismatch for 3.{number}")
    counts = {name: len(rows) for name, rows in records.items()}
    base_counts = context["base_manifest"]["record_counts"]
    deltas = {name: counts[name] - int(base_counts[name]) for name in counts}
    for name in ("programs", "courses", "resources", "editions"):
        if deltas[name] != 0:
            raise RuntimeError(f"unexpected singleton delta: {name}")
    if deltas["corrections"] != 3 or deltas["concepts"] != 10 or deltas["terms"] != 10 or deltas["assets"] != 13 or deltas["rights"] != 2:
        raise RuntimeError(f"B012 required class delta mismatch: {deltas}")
    gaps = [row for row in records["units"] if row.get("boundary_id") == BOUNDARY_ID and row.get("unit_type") == "companion_gap"]
    if len(gaps) != 4 or any(row.get("source_solution_used") is not False or row.get("source_path") is not None for row in gaps):
        raise RuntimeError("B012 explicit O001 gap closure failed")
    manifest_files = {entry["path"]: entry for entry in context["manifest"]["files"]}
    if set(manifest_files) != set(payloads) - {"manifest.json"}:
        raise RuntimeError("manifest path inventory closure failed")
    for relative, entry in manifest_files.items():
        raw = payloads[relative]
        if entry != {"path": relative, "bytes": len(raw), "sha256": sha256_bytes(raw), "records": payload_record_count(relative, raw)}:
            raise RuntimeError(f"manifest identity mismatch: {relative}")
    return {
        "record_count": len(all_rows), "record_counts": counts, "new_record_counts": deltas,
        "new_record_count": len(new_rows), "base_records_preserved_exact": True,
        "schema_validated_new_records": len(new_rows), "required_views": sorted(rebuilt),
        "entity_classes": sorted(set(row["record_type"] for row in all_rows)),
        "public_answers": PUBLIC_ANSWERS, "o001_gaps": O001_GAPS,
    }


def write_output(output: Path, payloads: dict[str, bytes]) -> dict[str, Any]:
    resolved = output.resolve()
    if resolved.parent != STAGE_ROOT.resolve() or resolved.name not in {"run-a", "run-b", "exports"}:
        raise RuntimeError(f"refusing output outside exact B012 final runs: {resolved}")
    if resolved.exists():
        existing = inventory(resolved)
        expected_paths = set(payloads)
        observed_paths = {item["path"] for item in existing["inventory"]}
        if observed_paths - expected_paths:
            raise RuntimeError(f"refusing to replace B012 final run with unexpected files: {sorted(observed_paths - expected_paths)[:3]}")
    for relative, raw in sorted(payloads.items()):
        destination = resolved / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() and destination.read_bytes() != raw:
            destination.write_bytes(raw)
        elif not destination.exists():
            destination.write_bytes(raw)
    observed = inventory(resolved)
    if observed["files"] != len(payloads):
        raise RuntimeError("written helper inventory file count mismatch")
    return observed


def compare_runs(left: Path, right: Path) -> dict[str, Any]:
    left_inventory, right_inventory = inventory(left), inventory(right)
    if left_inventory != right_inventory:
        raise RuntimeError("independent B012 final run inventories differ")
    for item in left_inventory["inventory"]:
        if (left / item["path"]).read_bytes() != (right / item["path"]).read_bytes():
            raise RuntimeError(f"independent helper payload differs: {item['path']}")
    return {key: left_inventory[key] for key in ("files", "bytes", "sha256")}


def run(output: Path | None, validate_only: Path | None) -> dict[str, Any]:
    first, context = build_payloads()
    second, _ = build_payloads()
    if first != second:
        raise RuntimeError("two complete in-memory builds differ")
    validation = validate_payloads(first, context)
    written = write_output(output, first) if output is not None else None
    if validate_only is not None:
        for relative, raw in first.items():
            if require(validate_only / relative) != raw:
                raise RuntimeError(f"on-disk validation mismatch: {relative}")
        written = inventory(validate_only)
    return {
        "boundary_id": BOUNDARY_ID, "status": "PASS_B012_FINAL_ISOLATED_BACKEND",
        **validation, "deterministic_in_memory": True, "output": str(output or validate_only),
        "inventory": {key: written[key] for key in ("files", "bytes", "sha256")} if written else None,
        "live_backend_mutated": False, "canonical_source_mutated": False,
        "git_used": False, "publication_performed": False,
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



