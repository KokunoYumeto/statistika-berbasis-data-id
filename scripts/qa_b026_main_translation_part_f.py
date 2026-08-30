#!/usr/bin/env python3
"""Deterministically audit staged R011-B026 main translation Part F."""

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
TARGET_REL = Path("qa/b026-translation/staging/chapter-lines-897-1052.id.tex")
BLUEPRINT_REL = Path("qa/b026-source/R011-B026_BOUNDARY_BLUEPRINT.json")
RECEIPT_REL = Path("qa/b026-translation/R011-B026_MAIN_TRANSLATION_PART_F_QA.json")

SOURCE = LANE / SOURCE_REL
TARGET = LANE / TARGET_REL
BLUEPRINT = LANE / BLUEPRINT_REL
RECEIPT = LANE / RECEIPT_REL

FIRST_LINE = 897
LAST_LINE = 1052
NEXT_LINE = 1059
EXPECTED_SOURCE_FILE_SHA256 = "d818b24b8e8d0582f8e603972e87764082d8470d91ddcbeaa794c295a1d37bec"
EXPECTED_BLUEPRINT_SHA256 = "2340adb156e7dd6833a2421eed9b6b4e2f7045e347f4fe8639544028cd6ced34"
EXPECTED_SOURCE_BYTES = 6297
EXPECTED_SOURCE_SHA256 = "ee67646d201bf0538b364884b60e559ce68e6f67ee21ee0491f97fa70b37cfb5"
EXPECTED_TARGET_BYTES = 6463
EXPECTED_TARGET_SHA256 = "d4ad6b2b445259ed72dae2e301d2956a9f61e22d7c28fc63981ba403d8248ceb"

INDONESIAN_ANCHORS = [
    "waktu lari sampel",
    "pencilan yang sangat",
    "skor-T",
    "galat baku",
    "distribusi-$t$",
    "nilai-p",
    "Uji hipotesis untuk satu rata-rata",
    "interval kepercayaan dan uji hipotesis untuk satu rata-rata",
]

RESIDUAL_ENGLISH_PATTERNS = [
    r"\bAre runners in the US\b",
    r"\baverage time for all runners\b",
    r"\bWhat are appropriate hypotheses\b",
    r"\bdata come from a simple random sample\b",
    r"\bhistogram of the differences\b",
    r"\bthere is are particularly extreme outliers\b",
    r"\bhistogram of time for the sample data\b",
    r"\bWhen conducting a hypothesis test\b",
    r"\bTo find the test statistic\b",
    r"\bwe reject the null hypothesis\b",
    r"\bHypothesis testing for a single mean\b",
    r"\bIdentify the parameter of interest\b",
    r"\bVerify conditions for\b",
    r"\bconfidence intervals? and hypothesis tests? for a single mean\b",
]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def identity(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    return {"path": path.relative_to(LANE).as_posix(), "bytes": len(data), "sha256": sha256(data)}


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


def align_segments(text: str) -> list[str]:
    return re.findall(r"\\begin\{align\*\}(.*?)\\end\{align\*\}", text, flags=re.S)


def protected_sequences(text: str) -> dict[str, object]:
    return {
        "labels": re.findall(r"\\label\{([^{}]+)\}", text),
        "refs": re.findall(r"\\(?:ref|pageref)\{([^{}]+)\}", text),
        "figure_bindings": re.findall(r"\\Figures\[.*?\]\{([^{}]+)\}\{([^{}]+)\}\{([^{}]+)\}", text, flags=re.S),
        "input_bindings": re.findall(r"\\input\{([^{}]+)\}", text),
        "numeric_tokens": re.findall(r"(?<![A-Za-z])\d+(?:\.\d+)?(?![A-Za-z])", text),
    }


def visible_for_language_scan(text: str) -> str:
    value = re.sub(r"(?<!\\)\$(?:\\.|[^$])*(?<!\\)\$", " ", text, flags=re.S)
    value = re.sub(r"\\(?:label|ref|pageref|input)\{[^{}]+\}", " ", value)
    value = re.sub(r"\\(?:[A-Za-z@]+|.)", " ", value)
    value = value.replace("{", " ").replace("}", " ")
    return re.sub(r"\s+", " ", value)


def line_has_visible_prose(line: str) -> bool:
    value = strip_tex_comment(line)
    value = re.sub(r"(?<!\\)\$(?:\\.|[^$])*(?<!\\)\$", " ", value)
    value = re.sub(r"\\(?:label|ref|pageref|input)\{[^{}]+\}", " ", value)
    value = re.sub(r"\\(?:[A-Za-z@]+|.)", " ", value)
    return len(re.findall(r"[A-Za-z]{2,}", value)) >= 3


def build_receipt() -> dict[str, object]:
    if sha256(SOURCE.read_bytes()) != EXPECTED_SOURCE_FILE_SHA256:
        raise AssertionError("pinned chapter source identity drift")
    if sha256(BLUEPRINT.read_bytes()) != EXPECTED_BLUEPRINT_SHA256:
        raise AssertionError("B026 blueprint identity drift")
    target_identity = identity(TARGET)
    if target_identity["bytes"] != EXPECTED_TARGET_BYTES or target_identity["sha256"] != EXPECTED_TARGET_SHA256:
        raise AssertionError("staged Part F target identity drift")

    blueprint = json.loads(BLUEPRINT.read_text("utf-8"))
    chunk = blueprint["translation_chunks"][6]
    if (chunk["first_line"], chunk["last_line"], chunk["bytes"], chunk["sha256"]) != (
        FIRST_LINE,
        LAST_LINE,
        EXPECTED_SOURCE_BYTES,
        EXPECTED_SOURCE_SHA256,
    ):
        raise AssertionError("blueprint Part F chunk identity drift")

    source_lines_bytes = exact_lines(SOURCE)[FIRST_LINE - 1 : LAST_LINE]
    target_lines_bytes = exact_lines(TARGET)
    expected_lines = LAST_LINE - FIRST_LINE + 1
    if len(source_lines_bytes) != expected_lines or len(target_lines_bytes) != expected_lines:
        raise AssertionError("line-count mismatch for exact staged mapping")
    source_slice = b"".join(source_lines_bytes)
    target_bytes = b"".join(target_lines_bytes)
    if len(source_slice) != EXPECTED_SOURCE_BYTES or sha256(source_slice) != EXPECTED_SOURCE_SHA256:
        raise AssertionError("Part F source slice identity drift")

    source_lines = [line.decode("utf-8").rstrip("\n") for line in source_lines_bytes]
    target_lines = [line.decode("utf-8").rstrip("\n") for line in target_lines_bytes]
    blank_source = [offset + FIRST_LINE for offset, line in enumerate(source_lines) if not line]
    blank_target = [offset + FIRST_LINE for offset, line in enumerate(target_lines) if not line]
    if blank_source != blank_target:
        raise AssertionError("blank-line topology drift")

    comment_line_numbers: list[int] = []
    for offset, (source_line, target_line) in enumerate(zip(source_lines, target_lines)):
        if source_line.lstrip().startswith("%"):
            line_number = offset + FIRST_LINE
            comment_line_numbers.append(line_number)
            if source_line != target_line:
                raise AssertionError(f"comment/source witness drift at line {line_number}")

    source_text = source_slice.decode("utf-8")
    target_text = target_bytes.decode("utf-8")
    if command_sequence(source_text) != command_sequence(target_text):
        raise AssertionError("TeX command sequence drift")
    if environment_sequence(source_text) != environment_sequence(target_text):
        raise AssertionError("TeX environment sequence drift")
    if math_segments(source_text) != math_segments(target_text):
        raise AssertionError("dollar mathematics drift")
    if align_segments(source_text) != align_segments(target_text):
        raise AssertionError("aligned mathematics drift")
    if protected_sequences(source_text) != protected_sequences(target_text):
        raise AssertionError("protected labels/refs/assets/inputs/numerics drift")

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
        raise AssertionError(f"unchanged learner-visible source prose: {unchanged_visible_source_lines}")

    visible = visible_for_language_scan(active_text(target_lines))
    residual_matches = [pattern for pattern in RESIDUAL_ENGLISH_PATTERNS if re.search(pattern, visible, flags=re.I)]
    if residual_matches:
        raise AssertionError(f"residual English patterns: {residual_matches}")
    missing_anchors = [anchor for anchor in INDONESIAN_ANCHORS if anchor not in target_text]
    if missing_anchors:
        raise AssertionError(f"missing Indonesian terminology anchors: {missing_anchors}")

    repairs = [
        {
            "source_lines": "921-923",
            "source_issue": "prompt calls the active run17 plot a histogram of differences rather than sampled run times",
            "target_evidence": target_lines[921 - FIRST_LINE : 923 - FIRST_LINE + 1],
            "assertion": "waktu lari sampel" in " ".join(target_lines[921 - FIRST_LINE : 923 - FIRST_LINE + 1]),
        },
        {
            "source_lines": "926-930",
            "source_issue": "source has the agreement error 'there is are particularly extreme outliers'",
            "target_evidence": target_lines[926 - FIRST_LINE : 930 - FIRST_LINE + 1],
            "assertion": "pencilan yang sangat" in " ".join(target_lines[926 - FIRST_LINE : 930 - FIRST_LINE + 1]),
        },
    ]
    if not all(item["assertion"] for item in repairs):
        raise AssertionError("approved derivative-repair assertion failed")
    for item in repairs:
        del item["assertion"]

    receipt: dict[str, object] = {
        "$schema": "interlanguage.r011-translation-qa/v1",
        "boundary_id": "R011-B026",
        "part": "main-part-f",
        "status": "PASS_COMPLETE_NATURAL_ID_ID_STRUCTURE_MATH_PROTECTED_TEX_REPAIR_LEDGER_AND_RESIDUAL_ENGLISH_QA",
        "provenance": {"production_model": "OpenAI Codex gpt-5.6-sol, Ultra", "role": "bounded id-ID translation and deterministic QA"},
        "blueprint": identity(BLUEPRINT),
        "source": {
            "path": SOURCE_REL.as_posix(),
            "full_file_sha256": EXPECTED_SOURCE_FILE_SHA256,
            "first_line": FIRST_LINE,
            "last_line": LAST_LINE,
            "logical_lines": len(source_lines_bytes),
            "bytes": len(source_slice),
            "sha256": sha256(source_slice),
            "blueprint_chunk": {key: chunk[key] for key in ["first_line", "last_line", "bytes", "sha256"]},
        },
        "target": {**target_identity, "locale": "id-ID", "logical_lines": len(target_lines_bytes), "mapping": "target line N maps to source line N for lines 897-1052"},
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
            "repairs_applied": repairs,
            "unrecorded_semantic_repairs_applied": False,
            "inactive_comment_policy": "All inactive source commentary is retained exactly as provenance and excluded from learner-visible residual-English accounting.",
        },
        "next_translation_cursor": {"path": SOURCE_REL.as_posix(), "line": NEXT_LINE, "section_label": "pairedData", "working_boundary_id": "R011-B027"},
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
    elif args.verify and (not RECEIPT.exists() or RECEIPT.read_bytes() != first):
        raise AssertionError("on-disk B026 Part F QA receipt differs from exact replay")

    result = {
        "status": "PASS_EXACT_REPLAY_R011_B026_MAIN_TRANSLATION_PART_F",
        "mode": "write" if args.write else "verify" if args.verify else "self-check",
        "source_lines": f"{FIRST_LINE}-{LAST_LINE} inclusive",
        "target": identity(TARGET),
        "receipt": {"path": RECEIPT.relative_to(LANE).as_posix(), "bytes": len(first), "sha256": sha256(first), "on_disk_exact": RECEIPT.exists() and RECEIPT.read_bytes() == first},
        "repairs": ["921-923", "926-930"],
        "residual_english_matches": [],
        "next_translation_cursor": NEXT_LINE,
        "scope": "staged translation plus its deterministic QA receipt only",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
