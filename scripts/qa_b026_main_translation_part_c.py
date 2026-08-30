#!/usr/bin/env python3
"""Deterministically audit staged R011-B026 main translation Part C."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


LANE = Path(__file__).resolve().parents[1]
COMMIT = "fee25091fb24e89c36296fd67c48c1fcf7a93b6e"
AUTH_REL = Path("authority/upstream") / f"openintro-statistics-{COMMIT}"
SOURCE_REL = AUTH_REL / "ch_inference_for_means/TeX/ch_inference_for_means.tex"
TARGET_REL = Path("qa/b026-translation/staging/chapter-lines-401-633.id.tex")
BLUEPRINT_REL = Path("qa/b026-source/R011-B026_BOUNDARY_BLUEPRINT.json")
RECEIPT_REL = Path("qa/b026-translation/R011-B026_MAIN_TRANSLATION_PART_C_QA.json")

SOURCE = LANE / SOURCE_REL
TARGET = LANE / TARGET_REL
BLUEPRINT = LANE / BLUEPRINT_REL
RECEIPT = LANE / RECEIPT_REL

FIRST_LINE = 401
LAST_LINE = 633
NEXT_LINE = 634
EXPECTED_SOURCE_FILE_SHA256 = (
    "d818b24b8e8d0582f8e603972e87764082d8470d91ddcbeaa794c295a1d37bec"
)
EXPECTED_BLUEPRINT_SHA256 = (
    "2340adb156e7dd6833a2421eed9b6b4e2f7045e347f4fe8639544028cd6ced34"
)
EXPECTED_SOURCE_SLICE_BYTES = 10731
EXPECTED_SOURCE_SLICE_SHA256 = (
    "dce7cb73b918eb0c7585e979377bbfc1de427f6884c501b528e45c2c34049fde"
)
EXPECTED_TARGET_BYTES = 10675
EXPECTED_TARGET_SHA256 = (
    "d50a78f6fbbf52a5007cd42929ea1dd3737b9cc3b8bf0aec5bca3a9a861b44b3"
)

EXPECTED_REPAIR_LOCATIONS = [
    "ch_inference_for_means/TeX/ch_inference_for_means.tex:417-419",
    "ch_inference_for_means/TeX/ch_inference_for_means.tex:458",
    "ch_inference_for_means/TeX/ch_inference_for_means.tex:465-496",
    "ch_inference_for_means/TeX/ch_inference_for_means.tex:486",
]

INDONESIAN_ANCHORS = [
    "Memperkenalkan distribusi $t$",
    "menghitung galat baku",
    "simpangan baku sampel",
    "menggunakan suatu nilai",
    "sampel sebagai pengganti",
    "puncaknya lebih rendah dan lebih landai",
    "ekornya lebih tebal",
    "derajat kebebasan",
    "banyaknya derajat kebebasan sekitar 30 atau lebih",
    "puncak di pusat semakin tinggi",
    "ekor distribusinya tampak semakin tipis",
    "perangkat lunak statistik",
    "luas ekor bawah",
    "luas daerah atas",
]

RESIDUAL_ENGLISH_PATTERNS = [
    r"\bIn practice\b",
    r"\bwe cannot directly calculate\b",
    r"\bstandard error\b",
    r"\bpopulation standard deviation\b",
    r"\bsimilar issue\b",
    r"\bOur solution\b",
    r"\bsample value in place\b",
    r"\bWe'll employ\b",
    r"\bThis strategy tends\b",
    r"\buse a new distribution\b",
    r"\bbell shape\b",
    r"\bthicker than the normal\b",
    r"\bobservations are more likely\b",
    r"\bextra thick tails\b",
    r"\balways centered at zero\b",
    r"\bdegrees of freedom\b",
    r"\bprecise form\b",
    r"\bIn general\b",
    r"\bWhen modeling\b",
    r"\bgreater flexibility\b",
    r"\bstatistical software\b",
    r"\bgraphing calculator\b",
    r"\bworking understanding\b",
    r"\bWhat proportion\b",
    r"\bfalls below\b",
    r"\bdraw the picture\b",
    r"\bshade the area\b",
    r"\bEstimate the proportion\b",
    r"\bWith a normal distribution\b",
    r"\bfalling more than\b",
    r"\bboth tails\b",
    r"\bdramatically different\b",
    r"\bUse your preferred method\b",
    r"\bshaded area\b",
    r"\blower tail area\b",
    r"\bupper area\b",
]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def identity(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    return {
        "path": path.relative_to(LANE).as_posix(),
        "bytes": len(data),
        "sha256": sha256(data),
    }


def exact_lines(path: Path) -> list[bytes]:
    data = path.read_bytes()
    if b"\r" in data:
        raise AssertionError(f"file is not LF-normalized: {path}")
    return data.splitlines(keepends=True)


def canonical_bytes(payload: dict[str, object]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def strip_tex_comment(line: str) -> str:
    for index, char in enumerate(line):
        if char != "%":
            continue
        backslashes = 0
        cursor = index - 1
        while cursor >= 0 and line[cursor] == "\\":
            backslashes += 1
            cursor -= 1
        if backslashes % 2 == 0:
            return line[:index]
    return line


def active_text(lines: list[str]) -> str:
    return "\n".join(strip_tex_comment(line) for line in lines)


def command_sequence(text: str) -> list[str]:
    return re.findall(r"\\(?:[A-Za-z@]+|.)", text)


def environment_sequence(text: str) -> list[tuple[str, str]]:
    return re.findall(r"\\(begin|end)\{([^{}]+)\}", text)


def math_segments(text: str) -> list[str]:
    return re.findall(r"(?<!\\)\$(?:\\.|[^$])*(?<!\\)\$", text, flags=re.S)


def protected_sequences(text: str) -> dict[str, object]:
    return {
        "labels": re.findall(r"\\label\{([^{}]+)\}", text),
        "refs": re.findall(r"\\(?:ref|pageref)\{([^{}]+)\}", text),
        "figure_bindings": re.findall(
            r"\\Figure(?:\[(?:\\.|[^\]])*\])?\{([^{}]+)\}\{([^{}]+)\}",
            text,
            flags=re.S,
        ),
        "numeric_tokens": re.findall(
            r"(?<![A-Za-z])\d+(?:\.\d+)?(?![A-Za-z])", text
        ),
    }


def visible_for_language_scan(text: str) -> str:
    value = re.sub(r"(?<!\\)\$(?:\\.|[^$])*(?<!\\)\$", " ", text, flags=re.S)
    value = re.sub(r"\\(?:[A-Za-z@]+|.)", " ", value)
    value = value.replace("{", " ").replace("}", " ")
    return re.sub(r"\s+", " ", value)


def line_has_visible_prose(line: str) -> bool:
    value = strip_tex_comment(line)
    if re.fullmatch(r"\s*\\label\{[^{}]+\}\s*", value):
        return False
    value = re.sub(r"(?<!\\)\$(?:\\.|[^$])*(?<!\\)\$", " ", value)
    value = re.sub(r"\\(?:[A-Za-z@]+|.)", " ", value)
    words = re.findall(r"[A-Za-z]{2,}", value)
    return len(words) >= 3


def overlapping_blueprint_repairs(
    blueprint: dict[str, object],
) -> list[dict[str, object]]:
    matches: list[dict[str, object]] = []
    prefix = "ch_inference_for_means/TeX/ch_inference_for_means.tex:"
    for candidate in blueprint["correction_candidates"]:
        location = candidate["location"]
        if not location.startswith(prefix):
            continue
        line_match = re.search(r"\.tex:(\d+)(?:-(\d+))?", location)
        if not line_match:
            raise AssertionError(f"cannot parse correction location: {location}")
        first = int(line_match.group(1))
        last = int(line_match.group(2) or first)
        if first <= LAST_LINE and last >= FIRST_LINE:
            matches.append(candidate)
    return matches


def build_receipt() -> dict[str, object]:
    if sha256(SOURCE.read_bytes()) != EXPECTED_SOURCE_FILE_SHA256:
        raise AssertionError("pinned chapter source identity drift")
    if sha256(BLUEPRINT.read_bytes()) != EXPECTED_BLUEPRINT_SHA256:
        raise AssertionError("B026 blueprint identity drift")
    target_identity = identity(TARGET)
    if target_identity["bytes"] != EXPECTED_TARGET_BYTES:
        raise AssertionError("staged target byte-count drift")
    if target_identity["sha256"] != EXPECTED_TARGET_SHA256:
        raise AssertionError("staged target hash drift")

    blueprint = json.loads(BLUEPRINT.read_text("utf-8"))
    if blueprint["boundary_id"] != "R011-B026":
        raise AssertionError("wrong boundary blueprint")
    chunk = blueprint["translation_chunks"][3]
    if (chunk["first_line"], chunk["last_line"]) != (FIRST_LINE, LAST_LINE):
        raise AssertionError("blueprint Part C chunk boundary drift")
    if (
        chunk["bytes"] != EXPECTED_SOURCE_SLICE_BYTES
        or chunk["sha256"] != EXPECTED_SOURCE_SLICE_SHA256
    ):
        raise AssertionError("blueprint Part C chunk identity drift")

    repair_candidates = overlapping_blueprint_repairs(blueprint)
    repair_locations = [candidate["location"] for candidate in repair_candidates]
    if repair_locations != EXPECTED_REPAIR_LOCATIONS:
        raise AssertionError(
            f"approved repair-set drift: expected {EXPECTED_REPAIR_LOCATIONS}, got {repair_locations}"
        )

    source_all_lines = exact_lines(SOURCE)
    source_lines_bytes = source_all_lines[FIRST_LINE - 1 : LAST_LINE]
    target_lines_bytes = exact_lines(TARGET)
    expected_line_count = LAST_LINE - FIRST_LINE + 1
    if (
        len(source_lines_bytes) != expected_line_count
        or len(target_lines_bytes) != expected_line_count
    ):
        raise AssertionError("line-count mismatch for exact staged mapping")
    source_slice = b"".join(source_lines_bytes)
    target_bytes = b"".join(target_lines_bytes)
    if (
        len(source_slice) != EXPECTED_SOURCE_SLICE_BYTES
        or sha256(source_slice) != EXPECTED_SOURCE_SLICE_SHA256
    ):
        raise AssertionError("source slice identity drift")

    source_lines = [line.decode("utf-8").rstrip("\n") for line in source_lines_bytes]
    target_lines = [line.decode("utf-8").rstrip("\n") for line in target_lines_bytes]
    blank_source = [
        offset + FIRST_LINE for offset, line in enumerate(source_lines) if not line
    ]
    blank_target = [
        offset + FIRST_LINE for offset, line in enumerate(target_lines) if not line
    ]
    if blank_source != blank_target:
        raise AssertionError("blank-line topology drift")

    comment_line_numbers: list[int] = []
    for offset, (source_line, target_line) in enumerate(zip(source_lines, target_lines)):
        if source_line.lstrip().startswith("%"):
            number = offset + FIRST_LINE
            comment_line_numbers.append(number)
            if source_line != target_line:
                raise AssertionError(f"comment/source witness drift at line {number}")

    source_text = source_slice.decode("utf-8")
    target_text = target_bytes.decode("utf-8")
    if command_sequence(source_text) != command_sequence(target_text):
        raise AssertionError("TeX command sequence drift")
    if environment_sequence(source_text) != environment_sequence(target_text):
        raise AssertionError("TeX environment sequence drift")
    if math_segments(source_text) != math_segments(target_text):
        raise AssertionError("mathematics drift")
    if protected_sequences(source_text) != protected_sequences(target_text):
        raise AssertionError("protected labels/refs/figure/numeric sequence drift")

    control_counts: dict[str, dict[str, int]] = {}
    for token in ["{", "}", "$", "%", "~"]:
        source_count = source_text.count(token)
        target_count = target_text.count(token)
        if source_count != target_count:
            raise AssertionError(f"protected control-token count drift: {token}")
        control_counts[token] = {"source": source_count, "target": target_count}

    unchanged_visible_source_lines = [
        offset + FIRST_LINE
        for offset, (source_line, target_line) in enumerate(zip(source_lines, target_lines))
        if source_line == target_line and line_has_visible_prose(source_line)
    ]
    if unchanged_visible_source_lines:
        raise AssertionError(
            f"unchanged learner-visible source prose: {unchanged_visible_source_lines}"
        )

    target_active = active_text(target_lines)
    visible = visible_for_language_scan(target_active)
    residual_matches = [
        pattern
        for pattern in RESIDUAL_ENGLISH_PATTERNS
        if re.search(pattern, visible, flags=re.IGNORECASE)
    ]
    if residual_matches:
        raise AssertionError(f"residual English patterns: {residual_matches}")
    target_flat = re.sub(r"\s+", " ", target_text).casefold()
    missing_anchors = [
        anchor
        for anchor in INDONESIAN_ANCHORS
        if re.sub(r"\s+", " ", anchor).casefold() not in target_flat
    ]
    if missing_anchors:
        raise AssertionError(f"missing Indonesian terminology anchors: {missing_anchors}")

    repairs_applied = [
        {
            "source_location": EXPECTED_REPAIR_LOCATIONS[0],
            "source_issue": "The phrase 'use sample value' omits the article 'a'.",
            "target_evidence": {
                "lines": "417-419",
                "text": "menggunakan suatu nilai / sampel sebagai pengganti / nilai populasi",
            },
            "resolution": "Rendered the intended substitution naturally as 'suatu nilai sampel'.",
            "authority_mutated": False,
        },
        {
            "source_location": EXPECTED_REPAIR_LOCATIONS[1],
            "source_issue": (
                "The alt text has a grammar error and reverses the plotted center-height ordering."
            ),
            "target_evidence": {
                "line": 458,
                "text": "puncaknya lebih rendah dan lebih landai ... serta ekornya lebih tebal",
            },
            "resolution": (
                "Corrected the grammar and described the visible lower/flatter center and heavier tails."
            ),
            "authority_mutated": False,
        },
        {
            "source_location": EXPECTED_REPAIR_LOCATIONS[2],
            "source_issue": (
                "Plural 'degrees of freedom' is treated as singular in several English clauses."
            ),
            "target_evidence": {
                "lines": "465-496",
                "text": (
                    "Indonesian predicate forms remain grammatical; line 480 explicitly uses "
                    "'banyaknya derajat kebebasan'."
                ),
            },
            "resolution": "Preserved df=n-1 and every value while avoiding the source agreement errors.",
            "authority_mutated": False,
        },
        {
            "source_location": EXPECTED_REPAIR_LOCATIONS[3],
            "source_issue": (
                "The alt text has a malformed possessive and reverses the plotted peak/tail trend."
            ),
            "target_evidence": {
                "line": 486,
                "text": (
                    "puncak di pusat semakin tinggi dan mendekati puncak distribusi normal, "
                    "sedangkan ekor distribusinya tampak semakin tipis"
                ),
            },
            "resolution": (
                "Described convergence upward at zero and thinning tails as df increases."
            ),
            "authority_mutated": False,
        },
    ]

    receipt: dict[str, object] = {
        "$schema": "interlanguage.r011-translation-qa/v1",
        "boundary_id": "R011-B026",
        "part": "main-part-c",
        "status": (
            "PASS_COMPLETE_NATURAL_ID_ID_STRUCTURE_MATH_PROTECTED_TEX_"
            "APPROVED_REPAIR_AND_RESIDUAL_ENGLISH_QA"
        ),
        "provenance": {
            "production_model": "OpenAI Codex gpt-5.6-sol, Ultra",
            "role": "bounded id-ID translation and deterministic QA",
        },
        "blueprint": identity(BLUEPRINT),
        "source": {
            "path": SOURCE_REL.as_posix(),
            "full_file_sha256": EXPECTED_SOURCE_FILE_SHA256,
            "first_line": FIRST_LINE,
            "last_line": LAST_LINE,
            "logical_lines": len(source_lines_bytes),
            "bytes": len(source_slice),
            "sha256": sha256(source_slice),
            "blueprint_chunk": {
                key: chunk[key] for key in ["first_line", "last_line", "bytes", "sha256"]
            },
        },
        "target": {
            **target_identity,
            "locale": "id-ID",
            "logical_lines": len(target_lines_bytes),
            "mapping": (
                "target line 1 maps to source line 401; "
                "target line 233 maps to source line 633"
            ),
        },
        "qa": {
            "command_environment_math_and_protected_sequences_exact": True,
            "blank_line_topology_exact": True,
            "comment_source_witness_lines_exact": True,
            "comment_lines_checked": len(comment_line_numbers),
            "comment_line_numbers": comment_line_numbers,
            "control_token_counts": control_counts,
            "unchanged_learner_visible_source_lines": unchanged_visible_source_lines,
            "residual_english_patterns_checked": RESIDUAL_ENGLISH_PATTERNS,
            "residual_english_matches": residual_matches,
            "indonesian_terminology_anchors": INDONESIAN_ANCHORS,
            "approved_repairs_overlapping_part": repair_candidates,
            "repairs_applied": repairs_applied,
            "unrecorded_semantic_repairs_applied": False,
            "inactive_comment_policy": (
                "All inactive source commentary is retained exactly as provenance and excluded "
                "from learner-visible residual-English accounting."
            ),
        },
        "next_translation_cursor": {
            "path": SOURCE_REL.as_posix(),
            "line": NEXT_LINE,
            "blueprint_chunk": "634-796 inclusive",
            "context": (
                "One-sample t confidence intervals and the Risso's dolphin worked sequence."
            ),
        },
        "scope_guards": {
            "exercises_or_public_answers_translated": False,
            "assets_localized": False,
            "canonical_source_mutated": False,
            "live_backend_mutated": False,
            "control_or_output_mutated": False,
            "release_or_publication_mutated": False,
            "git_used": False,
            "network_used": False,
            "credentials_accessed": False,
            "upstream_contact": False,
        },
    }
    receipt["qa_script"] = identity(Path(__file__).resolve())
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--verify", action="store_true")
    mode.add_argument("--self-check", action="store_true")
    args = parser.parse_args()

    first = canonical_bytes(build_receipt())
    second = canonical_bytes(build_receipt())
    if first != second:
        raise AssertionError("in-process deterministic receipt replay mismatch")

    if args.write:
        RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        RECEIPT.write_bytes(first)
    elif args.verify:
        if not RECEIPT.exists() or RECEIPT.read_bytes() != first:
            raise AssertionError("on-disk B026 Part C QA receipt differs from exact replay")

    result = {
        "status": "PASS_EXACT_REPLAY_R011_B026_MAIN_TRANSLATION_PART_C",
        "mode": "write" if args.write else "verify" if args.verify else "self-check",
        "source_lines": f"{FIRST_LINE}-{LAST_LINE} inclusive",
        "target": identity(TARGET),
        "receipt": {
            "path": RECEIPT.relative_to(LANE).as_posix(),
            "bytes": len(first),
            "sha256": sha256(first),
            "on_disk_exact": RECEIPT.exists() and RECEIPT.read_bytes() == first,
        },
        "repairs": EXPECTED_REPAIR_LOCATIONS,
        "residual_english_matches": [],
        "next_translation_cursor": NEXT_LINE,
        "scope": "staged translation plus its deterministic QA receipt only",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
