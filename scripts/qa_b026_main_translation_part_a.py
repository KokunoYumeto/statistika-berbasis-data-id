#!/usr/bin/env python3
"""Deterministically audit the staged R011-B026 main translation, Part A.

The audit is deliberately bounded to authority lines 1-231 and the matching
staged id-ID TeX. It writes/verifies one QA receipt and never mutates authority,
live source/backend/control/output/release state, Git, credentials, or network.
"""

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
TARGET_REL = Path(
    "qa/b026-translation/staging/chapter-lines-1-231.id.tex"
)
BLUEPRINT_REL = Path("qa/b026-source/R011-B026_BOUNDARY_BLUEPRINT.json")
RECEIPT_REL = Path("qa/b026-translation/R011-B026_MAIN_TRANSLATION_PART_A_QA.json")

SOURCE = LANE / SOURCE_REL
TARGET = LANE / TARGET_REL
BLUEPRINT = LANE / BLUEPRINT_REL
RECEIPT = LANE / RECEIPT_REL

FIRST_LINE = 1
LAST_LINE = 231
NEXT_LINE = 232
EXPECTED_SOURCE_FILE_SHA256 = (
    "d818b24b8e8d0582f8e603972e87764082d8470d91ddcbeaa794c295a1d37bec"
)
EXPECTED_BLUEPRINT_SHA256 = (
    "2340adb156e7dd6833a2421eed9b6b4e2f7045e347f4fe8639544028cd6ced34"
)
EXPECTED_TARGET_BYTES = 9551
EXPECTED_TARGET_SHA256 = (
    "f7ee09a6df0667faa82ac86cf032f4eb0477a29ca94c7f1bc676dad38fc96d34"
)

EXPECTED_LABELS = [
    "inferenceForNumericalData",
    "ch_inference_for_means",
    "oneSampleMeansWithTDistribution",
    "x_bar_conditions",
    "outliers_and_ss_condition_ex",
]
EXPECTED_REFS = [
    "ch_foundations_for_inf",
    "x_bar_conditions",
    "introducingTheTDistribution",
]
EXPECTED_CHAPTER_SECTIONS = [
    "oneSampleMeansWithTDistribution",
    "pairedData",
    "differenceOfTwoMeans",
    "PowerForDifferenceOfTwoMeans",
    "anovaAndRegrWithCategoricalVariables",
]

INDONESIAN_ANCHORS = [
    "Inferensi untuk data numerik",
    "Teorema Limit Pusat untuk rata-rata sampel",
    "galat baku",
    "Independensi.",
    "Normalitas.",
    "pedoman praktis",
    "pencilan yang sangat ekstrem",
    "sampel acak sederhana",
]

RESIDUAL_ENGLISH_PATTERNS = [
    r"\bInference for numerical data\b",
    r"\bintroduced a framework\b",
    r"\bconfidence intervals?\b",
    r"\bhypothesis tests?\b",
    r"\bpoint estimates?\b",
    r"\btest statistics?\b",
    r"\bsample proportions?\b",
    r"\bsample means?\b",
    r"\bnormal distributions?\b",
    r"\bCentral Limit Theorem\b",
    r"\bStandard Error\b",
    r"\bpopulation standard deviation\b",
    r"\bBefore diving\b",
    r"\bcertain conditions\b",
    r"\bIndependence\.\b",
    r"\bNormality\.\b",
    r"\bsample observations\b",
    r"\bnormally distributed population\b",
    r"\brules? of thumb\b",
    r"\bclear outliers?\b",
    r"\bfirst course in statistics\b",
    r"\bdifferent populations\b",
    r"\bSample 1 Observations\b",
    r"\bSample 2 Observations\b",
    r"\bnormality condition\b",
    r"\bEach samples is\b",
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


def normalized_align_segments(text: str) -> list[str]:
    segments = re.findall(
        r"\\begin\{align\*\}(.*?)\\end\{align\*\}", text, flags=re.S
    )
    return [re.sub(r"\\text\{[^{}]*\}", r"\\text{<localized>}", item) for item in segments]


def protected_sequences(text: str) -> dict[str, object]:
    return {
        "labels": re.findall(r"\\label\{([^{}]+)\}", text),
        "refs": re.findall(r"\\(?:ref|pageref)\{([^{}]+)\}", text),
        "chapter_sections": re.findall(r"\\chaptersection\{([^{}]+)\}", text),
        "chapter_folder": re.findall(
            r"\\renewcommand\{\\chapterfolder\}\{([^{}]+)\}", text
        ),
        "figure_bindings": re.findall(
            r"\\Figure\[.*?\]\{([^{}]+)\}\{([^{}]+)\}", text, flags=re.S
        ),
        "numeric_tokens": re.findall(r"(?<![A-Za-z])\d+(?:\.\d+)?(?![A-Za-z])", text),
    }


def visible_for_language_scan(text: str) -> str:
    value = text
    value = re.sub(r"\\label\{[^{}]+\}", " ", value)
    value = re.sub(r"\\(?:ref|pageref)\{[^{}]+\}", " ", value)
    value = re.sub(r"\\chaptersection\{[^{}]+\}", " ", value)
    value = re.sub(
        r"\\renewcommand\{\\chapterfolder\}\{[^{}]+\}", " ", value
    )
    value = value.replace("outliers_and_ss_condition", " ")
    value = re.sub(r"(?<!\\)\$(?:\\.|[^$])*(?<!\\)\$", " ", value, flags=re.S)
    value = re.sub(r"\\(?:[A-Za-z@]+|.)", " ", value)
    value = value.replace("{", " ").replace("}", " ")
    return re.sub(r"\s+", " ", value)


def line_has_visible_prose(line: str) -> bool:
    value = strip_tex_comment(line)
    value = re.sub(
        r"\\renewcommand\{\\chapterfolder\}\{[^{}]+\}", " ", value
    )
    value = re.sub(r"\\label\{[^{}]+\}", " ", value)
    value = re.sub(r"\\(?:ref|pageref|chaptersection)\{[^{}]+\}", " ", value)
    value = re.sub(r"(?<!\\)\$(?:\\.|[^$])*(?<!\\)\$", " ", value)
    value = re.sub(r"\\(?:[A-Za-z@]+|.)", " ", value)
    words = re.findall(r"[A-Za-z]{2,}", value)
    return len(words) >= 3


def build_receipt() -> dict[str, object]:
    if sha256(SOURCE.read_bytes()) != EXPECTED_SOURCE_FILE_SHA256:
        raise AssertionError("pinned chapter source identity drift")
    if sha256(BLUEPRINT.read_bytes()) != EXPECTED_BLUEPRINT_SHA256:
        raise AssertionError("B026 blueprint identity drift")
    if identity(TARGET)["bytes"] != EXPECTED_TARGET_BYTES:
        raise AssertionError("staged target byte-count drift")
    if identity(TARGET)["sha256"] != EXPECTED_TARGET_SHA256:
        raise AssertionError("staged target hash drift")

    blueprint = json.loads(BLUEPRINT.read_text("utf-8"))
    if blueprint["boundary_id"] != "R011-B026":
        raise AssertionError("wrong boundary blueprint")
    chunks = blueprint["translation_chunks"]
    if [(item["first_line"], item["last_line"]) for item in chunks[:2]] != [
        (1, 28),
        (29, 231),
    ]:
        raise AssertionError("blueprint Part A chunk boundary drift")

    source_all_lines = exact_lines(SOURCE)
    target_lines_bytes = exact_lines(TARGET)
    source_lines_bytes = source_all_lines[FIRST_LINE - 1 : LAST_LINE]
    if len(source_lines_bytes) != 231 or len(target_lines_bytes) != 231:
        raise AssertionError("line-count mismatch for exact 1:1 staged mapping")
    source_slice = b"".join(source_lines_bytes)
    target_bytes = b"".join(target_lines_bytes)
    source_lines = [line.decode("utf-8").rstrip("\n") for line in source_lines_bytes]
    target_lines = [line.decode("utf-8").rstrip("\n") for line in target_lines_bytes]

    if sha256(b"".join(source_lines_bytes[:28])) != chunks[0]["sha256"]:
        raise AssertionError("chapter-opening source chunk drift")
    if sha256(b"".join(source_lines_bytes[28:])) != chunks[1]["sha256"]:
        raise AssertionError("instructional source chunk drift")

    blank_source = [index + FIRST_LINE for index, line in enumerate(source_lines) if not line]
    blank_target = [index + FIRST_LINE for index, line in enumerate(target_lines) if not line]
    if blank_source != blank_target:
        raise AssertionError("blank-line topology drift")

    comment_lines_checked: list[int] = []
    for offset, (source_line, target_line) in enumerate(zip(source_lines, target_lines)):
        if source_line.lstrip().startswith("%"):
            line_number = offset + FIRST_LINE
            comment_lines_checked.append(line_number)
            if source_line != target_line:
                raise AssertionError(f"comment/source witness drift at line {line_number}")

    source_text = source_slice.decode("utf-8")
    target_text = target_bytes.decode("utf-8")
    if command_sequence(source_text) != command_sequence(target_text):
        raise AssertionError("TeX command sequence drift")
    if environment_sequence(source_text) != environment_sequence(target_text):
        raise AssertionError("TeX environment sequence drift")
    if math_segments(source_text) != math_segments(target_text):
        raise AssertionError("inline/display-dollar mathematics drift")
    if normalized_align_segments(source_text) != normalized_align_segments(target_text):
        raise AssertionError("aligned mathematics drift outside localized text")
    source_protected = protected_sequences(source_text)
    target_protected = protected_sequences(target_text)
    if source_protected != target_protected:
        raise AssertionError("protected labels/refs/assets/numerics drift")
    if source_protected["labels"] != EXPECTED_LABELS:
        raise AssertionError("expected label sequence drift")
    if source_protected["refs"] != EXPECTED_REFS:
        raise AssertionError("expected reference sequence drift")
    if source_protected["chapter_sections"] != EXPECTED_CHAPTER_SECTIONS:
        raise AssertionError("expected chapter-navigation sequence drift")
    if source_protected["figure_bindings"] != [("0.85", "outliers_and_ss_condition")]:
        raise AssertionError("figure binding drift")

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
    missing_anchors = [anchor for anchor in INDONESIAN_ANCHORS if anchor not in target_text]
    if missing_anchors:
        raise AssertionError(f"missing Indonesian terminology anchors: {missing_anchors}")

    repairs = [
        {
            "source_line": 111,
            "source_issue": "comma joins two complete sentences",
            "target_evidence": target_lines[110],
            "assertion": target_lines[110] == "    Observasi sampel harus saling independen.",
        },
        {
            "source_line": 203,
            "source_issue": "alt text omits 'one' before non-zero bin",
            "target_evidence": "Hanya ada satu bin tak nol di atas 5",
            "assertion": "Hanya ada satu bin tak nol di atas 5" in target_lines[202],
        },
        {
            "source_line": 208,
            "source_issue": "'Each samples is' number-agreement error",
            "target_evidence": target_lines[207],
            "assertion": target_lines[207] == "  Setiap sampel merupakan sampel acak sederhana dari",
        },
    ]
    if not all(item["assertion"] for item in repairs):
        raise AssertionError("approved derivative-repair assertion failed")
    for item in repairs:
        del item["assertion"]

    receipt: dict[str, object] = {
        "$schema": "interlanguage.r011-translation-qa/v1",
        "boundary_id": "R011-B026",
        "part": "main-part-a",
        "status": "PASS_COMPLETE_NATURAL_ID_ID_STRUCTURE_MATH_PROTECTED_TEX_AND_RESIDUAL_ENGLISH_QA",
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
            "blueprint_chunks_consumed": [
                {key: chunks[index][key] for key in ["first_line", "last_line", "bytes", "sha256"]}
                for index in [0, 1]
            ],
        },
        "target": {
            **identity(TARGET),
            "locale": "id-ID",
            "logical_lines": len(target_lines_bytes),
            "mapping": "source line N maps to target line N for lines 1-231",
        },
        "qa": {
            "command_sequence_exact": True,
            "environment_sequence_exact": True,
            "labels_refs_chapter_navigation_figure_bindings_and_numerics_exact": True,
            "inline_and_aligned_mathematics_exact_outside_localized_text": True,
            "blank_line_topology_exact": True,
            "comment_source_witness_lines_exact": True,
            "comment_lines_checked": len(comment_lines_checked),
            "comment_line_numbers": comment_lines_checked,
            "control_token_counts": control_counts,
            "unchanged_learner_visible_source_lines": unchanged_visible_source_lines,
            "residual_english_patterns_checked": RESIDUAL_ENGLISH_PATTERNS,
            "residual_english_matches": residual_matches,
            "indonesian_terminology_anchors": INDONESIAN_ANCHORS,
            "repairs_applied": repairs,
            "unrecorded_semantic_repairs_applied": False,
        },
        "next_translation_cursor": {
            "path": SOURCE_REL.as_posix(),
            "line": NEXT_LINE,
            "blueprint_chunk": "232-400 inclusive",
            "context": (
                "Population-level sanity check for skew/extreme outliers, retained source "
                "comments, and closure of Central Limit Theorem indexing."
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
            raise AssertionError("on-disk B026 Part A QA receipt differs from exact replay")

    result = {
        "status": "PASS_EXACT_REPLAY_R011_B026_MAIN_TRANSLATION_PART_A",
        "mode": "write" if args.write else "verify" if args.verify else "self-check",
        "source_lines": f"{FIRST_LINE}-{LAST_LINE} inclusive",
        "target": identity(TARGET),
        "receipt": {
            "path": RECEIPT.relative_to(LANE).as_posix(),
            "bytes": len(first),
            "sha256": sha256(first),
            "on_disk_exact": RECEIPT.exists() and RECEIPT.read_bytes() == first,
        },
        "repairs": [111, 203, 208],
        "residual_english_matches": [],
        "next_translation_cursor": NEXT_LINE,
        "scope": "staged translation plus its deterministic QA receipt only",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
