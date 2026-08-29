#!/usr/bin/env python3
"""Deterministic bounded audit for the R011-B023 id-ID translation staging.

The audit reads only the pinned B023 authority, its frozen blueprint, and the
six task-local translation fragments.  It does not mutate the live source,
backend, controls, reader, release, Git state, credentials, or network.  A
small number of source/target differences are intentional and are represented
as named, checked exceptions below: the 17 frozen source corrections, two
lexical number localisations, and two documented prose reflow variants.

Modes:
  --self-check  replay the in-memory audit twice and require byte-identical
                canonical projections (no filesystem write)
  --probe       run once and print the canonical projection (no write)
  --write       write qa/b023-translation/R011-B023_TRANSLATION_AUDIT.json
  --verify      replay the audit and require the on-disk receipt to match
                exactly
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable


LANE = Path(__file__).resolve().parents[1]
COMMIT = "fee25091fb24e89c36296fd67c48c1fcf7a93b6e"
TREE = "d61cc601e7d97759ce805900520f784d02a0489e"
AUTH_REL = Path("authority/upstream") / f"openintro-statistics-{COMMIT}"
AUTH = LANE / AUTH_REL
BLUEPRINT = LANE / "qa/b023-source/R011-B023_BOUNDARY_BLUEPRINT.json"
RECEIPT = LANE / "qa/b023-translation/R011-B023_TRANSLATION_AUDIT.json"
MODEL = "OpenAI Codex gpt-5.6-sol, Ultra"

# This identity is the frozen source-control witness produced by
# freeze_b023_source.py.  Refuse a silently edited blueprint.
BLUEPRINT_ID = {
    "path": "qa/b023-source/R011-B023_BOUNDARY_BLUEPRINT.json",
    "bytes": 33090,
    "sha256": "96c8a0f4f02f6344244007efa433dcfc75d1804498ea92fce5570d826045d0b4",
}


CHUNKS: tuple[dict[str, Any], ...] = (
    {
        "id": "section-555-866",
        "target": Path("qa/b023-translation/staging/section-lines-555-866.id.tex"),
        "source": Path("ch_inference_for_props/TeX/ch_inference_for_props.tex"),
        "first": 555,
        "last": 866,
        "source_bytes": 10808,
        "source_sha256": "e2dc88e7b2b7d534cd3b6dd2edab235fa946da916be82738cf8fbb32578f00e7",
        "role": "section_6_2_opening_confidence_intervals_and_cpr_fish_oil",
    },
    {
        "id": "section-867-1130",
        "target": Path("qa/b023-translation/staging/section-lines-867-1130.id.tex"),
        "source": Path("ch_inference_for_props/TeX/ch_inference_for_props.tex"),
        "first": 867,
        "last": 1130,
        "source_bytes": 11171,
        "source_sha256": "96cb0a1d997eaee40f446477df0ebda3c7c6b27edd61dca572dfe637a169d8b1",
        "role": "two_proportion_hypothesis_tests_and_mammography",
    },
    {
        "id": "section-1131-1336",
        "target": Path("qa/b023-translation/staging/section-lines-1131-1336.id.tex"),
        "source": Path("ch_inference_for_props/TeX/ch_inference_for_props.tex"),
        "first": 1131,
        "last": 1336,
        "source_bytes": 9739,
        "source_sha256": "a2d5b2dd936c88f3b4696d92a04bc20beed9a5bba01a9ab217b61d2d670029b9",
        "role": "nonzero_null_quadcopter_blade_quality_and_se_derivation",
    },
    {
        "id": "exercises-1-212",
        "target": Path("qa/b023-translation/staging/exercises-lines-1-212.id.tex"),
        "source": Path("ch_inference_for_props/TeX/difference_of_two_proportions.tex"),
        "first": 1,
        "last": 212,
        "source_bytes": 8571,
        "source_sha256": "6b302801b86e930cd90915cb993183e332644db35bfc64cb69bfe7eeddfd937b",
        "role": "exercises_17_23",
    },
    {
        "id": "exercises-213-406",
        "target": Path("qa/b023-translation/staging/exercises-lines-213-406.id.tex"),
        "source": Path("ch_inference_for_props/TeX/difference_of_two_proportions.tex"),
        "first": 213,
        "last": 406,
        "source_bytes": 8215,
        "source_sha256": "61b48768924c02bc3acd81de08646a66756c7a96af43fbccfe143e75e9530884",
        "role": "exercises_24_30",
    },
    {
        "id": "public-answers-1363-1472",
        "target": Path(
            "qa/b023-translation/staging/public-answers-lines-1363-1472.id.tex"
        ),
        "source": Path("extraTeX/eoceSolutions/eoceSolutions.tex"),
        "first": 1363,
        "last": 1472,
        "source_bytes": 4811,
        "source_sha256": "a5e216d508f48d3421669683186dfbf451cba585ab3099c404f72c9a87f6e121",
        "role": "linked_public_odd_answers",
    },
)


FULL_SOURCE_WITNESSES: tuple[dict[str, Any], ...] = (
    {
        "path": Path("ch_inference_for_props/TeX/ch_inference_for_props.tex"),
        "bytes": 103385,
        "sha256": "a2470ca3041209d1f1194b3ab27e8124405d8fdbd1ccece89a0319be13fae8a7",
        "role": "main_source",
    },
    {
        "path": Path("ch_inference_for_props/TeX/difference_of_two_proportions.tex"),
        "bytes": 16786,
        "sha256": "443eb8835af956fea62293b2ea6bb2e928ec311ac1981b0e2266fc092f3f8397",
        "role": "exercise_source",
    },
    {
        "path": Path("extraTeX/eoceSolutions/eoceSolutions.tex"),
        "bytes": 106045,
        "sha256": "6c4e01376db4c023cc7b3f9949490e57220ef1cb831c580da71efde6ce723268",
        "role": "public_answer_source",
    },
)


# The blueprint has exactly these 17 high-confidence candidates.  Text itself
# is translated freely; these identities constrain only the semantic/content
# corrections that are allowed to affect protected token checks.
FROZEN_CORRECTIONS: tuple[dict[str, Any], ...] = (
    {
        "id": "C01",
        "location": "ch_inference_for_props/TeX/ch_inference_for_props.tex:680",
        "kind": "grammar",
        "evidence": ("pendekatan umumnya tetap sama",),
    },
    {
        "id": "C02",
        "location": "ch_inference_for_props/TeX/ch_inference_for_props.tex:765-768",
        "kind": "percentage_point_language",
        "evidence": ("-2.6 hingga +28.6", "poin persentase"),
    },
    {
        "id": "C03",
        "location": "ch_inference_for_props/TeX/ch_inference_for_props.tex:855",
        "kind": "grammar",
        "evidence": ("minyak ikan menurunkan",),
    },
    {
        "id": "C04",
        "location": "ch_inference_for_props/TeX/ch_inference_for_props.tex:931",
        "kind": "grammar",
        "evidence": ("rincian interval kepercayaan",),
    },
    {
        "id": "C05",
        "location": "ch_inference_for_props/TeX/ch_inference_for_props.tex:1024-1030",
        "kind": "percentage_point_language",
        "evidence": ("0.012 poin persentase",),
    },
    {
        "id": "C06",
        "location": "ch_inference_for_props/TeX/ch_inference_for_props.tex:1056",
        "kind": "statistical_wording",
        "evidence": ("tidak mendeteksi secara statistik",),
    },
    {
        "id": "C07",
        "location": "ch_inference_for_props/TeX/ch_inference_for_props.tex:1239-1243",
        "kind": "percentage_point_estimand",
        "evidence": ("lebih dari 3 poin persentase", "\\emph{lebih dari}"),
    },
    {
        "id": "C08",
        "location": "ch_inference_for_props/TeX/ch_inference_for_props.tex:1249-1252",
        "kind": "figure_caption",
        "evidence": ("distribusi normal yang berpusat di 0.03",),
    },
    {
        "id": "C09",
        "location": "ch_inference_for_props/TeX/ch_inference_for_props.tex:1275-1280",
        "kind": "grammar",
        "evidence": ("galat baku",),
    },
    {
        "id": "C10",
        "location": "ch_inference_for_props/TeX/ch_inference_for_props.tex:1292-1295",
        "kind": "stable_label_alias",
        "evidence": ("derivingSEForDiffOfTwoMeansExercise",),
    },
    {
        "id": "C11",
        "location": "ch_inference_for_props/TeX/ch_inference_for_props.tex:1306-1311",
        "kind": "independence_condition",
        "evidence": ("independen",),
    },
    {
        "id": "C12",
        "location": "ch_inference_for_props/TeX/difference_of_two_proportions.tex:109-112",
        "kind": "boundary_value",
        "evidence": ("40,000 atau lebih",),
    },
    {
        "id": "C13",
        "location": "ch_inference_for_props/TeX/difference_of_two_proportions.tex:365,369,375; extraTeX/eoceSolutions/eoceSolutions.tex:1452,1458-1460,1470-1471",
        "kind": "nevirapine_spelling",
        "evidence": ("nevirapine",),
    },
    {
        "id": "C14",
        "location": "ch_inference_for_props/TeX/difference_of_two_proportions.tex:403",
        "kind": "grammar",
        "evidence": ("Dapatkah ia menggunakan",),
    },
    {
        "id": "C15",
        "location": "extraTeX/eoceSolutions/eoceSolutions.tex:1396-1399",
        "kind": "percentage_point_language",
        "evidence": ("poin persentase",),
    },
    {
        "id": "C16",
        "location": "extraTeX/eoceSolutions/eoceSolutions.tex:1404-1411",
        "kind": "corrected_public_answer_values",
        "evidence": ("-3.16", "0.0016"),
    },
    {
        "id": "C17",
        "location": "extraTeX/eoceSolutions/eoceSolutions.tex:1420-1429",
        "kind": "corrected_public_answer_values",
        "evidence": ("0.37", "0.7113"),
    },
)


# Exact source positions where a prose percent sign is intentionally replaced
# by the explicit Indonesian absolute-difference unit.  All other \% controls
# must remain present and in order.
ALLOWED_PERCENT_REMOVALS: dict[str, dict[int, int]] = {
    "section-555-866": {766: 2, 769: 1},
    "section-867-1130": {1030: 1},
    "section-1131-1336": {1158: 1, 1164: 1, 1167: 1, 1239: 1, 1242: 1},
    "public-answers-1363-1472": {1397: 1, 1398: 1},
}

# Term-QA made one high-confidence semantic clarification after the initial
# composite audit: answer 27 states the decision rule explicitly as
# "nilai-p lebih besar daripada $\\alpha = 0.05$".  The added \\alpha command
# and math wrapper are equivalent to the authority's prose "(0.05)" and are
# admitted only at this exact source/target line pair.  This is named C18 and
# is recorded separately from the 17 frozen source-correction candidates so
# the exception set cannot grow silently.
TERM_QA_C18: dict[str, Any] = {
    "id": "C18",
    "chunk": "public-answers-1363-1472",
    "source_line": 1439,
    "target_line": 77,
    "token": r"\alpha",
    "source_anchor": "Since the p-value is high (default to alpha = 0.05),",
    "target_anchor": r"Karena nilai-p lebih besar daripada $\alpha = 0.05$,",
    "target_wrapper": r"$\alpha = 0.05$",
    "kind": "semantic_threshold_clarification",
    "reason": (
        "Make the p-value decision rule explicit in Indonesian while preserving "
        "the authority's alpha=0.05 threshold and numerical result."
    ),
}
ALLOWED_TERM_QA_CONTROL_ADDITIONS: dict[str, dict[int, dict[str, int]]] = {
    TERM_QA_C18["chunk"]: {TERM_QA_C18["target_line"]: {TERM_QA_C18["token"]: 1}},
}

# Two prose ``2-proportion`` tokens are naturally rendered as ``dua
# proporsi``.  Their numeric literal is lexical, not mathematical.
ALLOWED_LEXICAL_NUMBER_REMOVALS: dict[str, dict[int, int]] = {
    "section-1131-1336": {1131: 1, 1133: 1},
}

# The accepted staging currently has two deterministic line-reflow variants.
# Each variant is fully pinned by target line count, blank/comment masks, and
# content anchors.  The exact-line variant is also accepted for future repair.
LAYOUT_VARIANTS: dict[str, tuple[dict[str, Any], ...]] = {
    "exercises-213-406": (
        {
            "name": "exact_source_line_layout",
            "target_lines": 194,
            "blank_positions": [16, 18, 20, 47, 49, 83, 85, 110, 112, 114, 145, 147, 174, 176],
            "comment_positions": [19, 48, 84, 113, 146, 175],
            "anchors": (),
        },
        {
            "name": "accepted_prose_reflow_v1",
            "target_lines": 193,
            "blank_positions": [7, 16, 18, 20, 47, 49, 83, 85, 110, 112, 114, 145, 147, 173, 175],
            "comment_positions": [19, 48, 84, 113, 146, 174],
            "anchors": (
                (6, "penduduk Oregon."),
                (150, "hasil yang tidak terduga."),
            ),
        },
    ),
    "public-answers-1363-1472": (
        {
            "name": "exact_source_line_layout",
            "target_lines": 110,
            "blank_positions": [2, 11, 13, 19, 21, 39, 41, 55, 57, 70, 72, 80, 82],
            "comment_positions": [1, 12, 20, 40, 56, 71, 81],
            "anchors": (),
        },
        {
            "name": "accepted_answer_prose_reflow_v1",
            "target_lines": 109,
            "blank_positions": [2, 11, 13, 19, 21, 39, 41, 55, 57, 70, 72, 80, 82],
            "comment_positions": [1, 12, 20, 40, 56, 71, 81],
            "anchors": ((98, "kelompok nevirapine dan lopinavir."),),
        },
    ),
}


CONTROL_RE = re.compile(r"\\(?:[A-Za-z@]+|.)")
ENV_RE = re.compile(r"\\(?:begin|end)\{[^{}]+\}")
NUMBER_RE = re.compile(r"(?<![A-Za-z])\d+(?:[.,]\d+)?")
ORDINAL_RE = re.compile(r"(?m)^%\s*(\d+)\s*$")
FORBIDDEN_COMMAND_RE = re.compile(
    r"\\(?:sol|solution|solutions|instructor|instructorsolution|answerkey|answerKey)\b",
    re.IGNORECASE,
)
MATH_SPAN_RE = re.compile(r"(?<!\\)\$(?!\$)(.*?)(?<!\\)\$", re.DOTALL)
DISPLAY_RE = re.compile(
    r"\\begin\{(align\*?|eqnarray\*?|equation\*?|displaymath|gather\*?)\}(.*?)"
    r"\\end\{\1\}",
    re.DOTALL,
)
IDENT_NAMES = {
    "label",
    "ref",
    "vref",
    "pageref",
    "cite",
    "footfullcite",
    "oiRedirect",
    "input",
}
FIGURE_NAMES = {"Figure", "Figures"}


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(
        "utf-8"
    )


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(LANE).as_posix()


def identity(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {"path": rel(path), "bytes": len(raw), "sha256": sha256_bytes(raw)}


def read_utf8_lf(path: Path) -> tuple[bytes, str]:
    raw = path.read_bytes()
    if b"\r" in raw:
        raise AssertionError(f"CR line ending in {rel(path)}")
    if not raw.endswith(b"\n"):
        raise AssertionError(f"missing terminal LF in {rel(path)}")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AssertionError(f"invalid UTF-8 in {rel(path)}: {exc}") from exc
    if text.startswith("\ufeff"):
        raise AssertionError(f"unexpected UTF-8 BOM in {rel(path)}")
    return raw, text


def source_slice(pair: dict[str, Any]) -> tuple[bytes, str, list[str]]:
    source_path = AUTH / pair["source"]
    raw = source_path.read_bytes()
    if b"\r" in raw:
        raise AssertionError(f"CR line ending in authority {rel(source_path)}")
    all_lines = raw.splitlines(keepends=True)
    expected_total = pair["last"] - pair["first"] + 1
    if len(all_lines) < pair["last"]:
        raise AssertionError(f"authority file too short for {pair['id']}")
    selected = all_lines[pair["first"] - 1 : pair["last"]]
    if len(selected) != expected_total:
        raise AssertionError(f"source line slice count drift for {pair['id']}")
    sliced = b"".join(selected)
    if len(sliced) != pair["source_bytes"] or sha256_bytes(sliced) != pair["source_sha256"]:
        raise AssertionError(f"source slice identity drift for {pair['id']}")
    text = sliced.decode("utf-8")
    return sliced, text, [line.decode("utf-8").rstrip("\n") for line in selected]


def lines(text: str) -> list[str]:
    return text.splitlines()


def line_position(text: str, offset: int, first: int = 1) -> int:
    return first + text[:offset].count("\n")


def command_entries(text: str, first_line: int = 1) -> list[tuple[str, int]]:
    return [(m.group(), line_position(text, m.start(), first_line)) for m in CONTROL_RE.finditer(text)]


def number_entries(text: str, first_line: int = 1) -> list[tuple[str, int]]:
    return [(m.group(), line_position(text, m.start(), first_line)) for m in NUMBER_RE.finditer(text)]


def parse_balanced(text: str, start: int, opening: str, closing: str) -> tuple[str, int]:
    if start >= len(text) or text[start] != opening:
        raise AssertionError(f"expected {opening!r} at offset {start}")
    depth = 0
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == opening:
            depth += 1
        elif char == closing:
            depth -= 1
            if depth == 0:
                return text[start + 1 : index], index + 1
    raise AssertionError(f"unclosed {opening!r} group")


def macro_invocations(text: str, names: set[str]) -> list[tuple[str, tuple[str, ...]]]:
    result: list[tuple[str, tuple[str, ...]]] = []
    for match in re.finditer(r"\\([A-Za-z@]+)", text):
        name = match.group(1)
        if name not in names:
            continue
        position = match.end()
        args: list[str] = []
        while position < len(text):
            while position < len(text) and text[position].isspace():
                position += 1
            if position < len(text) and text[position] == "[":
                value, position = parse_balanced(text, position, "[", "]")
                args.append("[" + value + "]")
            elif position < len(text) and text[position] == "{":
                value, position = parse_balanced(text, position, "{", "}")
                args.append("{" + value + "}")
            else:
                break
        result.append((name, tuple(args)))
    return result


def figure_calls(text: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for match in re.finditer(r"\\(Figure|Figures)\b", text):
        name = match.group(1)
        position = match.end()
        while position < len(text) and text[position].isspace():
            position += 1
        alt = None
        if position < len(text) and text[position] == "[":
            alt, position = parse_balanced(text, position, "[", "]")
        args: list[str] = []
        while position < len(text):
            while position < len(text) and text[position].isspace():
                position += 1
            if position >= len(text) or text[position] != "{":
                break
            value, position = parse_balanced(text, position, "{", "}")
            args.append(value)
        expected = 3 if name == "Figures" else 2
        if len(args) != expected:
            raise AssertionError(f"malformed {name} call with {len(args)} arguments")
        result.append(
            {
                "macro": name,
                "alt": alt or "",
                "args": args,
                "line": line_position(text, match.start()),
            }
        )
    return result


def env_tokens(text: str) -> list[str]:
    return ENV_RE.findall(text)


def strip_math_text_nodes(value: str) -> str:
    # Textual nodes inside formulas are translated prose, not mathematical
    # identity.  Keep every command, delimiter, operator, identifier, and
    # numeric literal outside these nodes.
    previous = None
    while previous != value:
        previous = value
        value = re.sub(
            r"\\(?:text|textit|textrm|mathrm|mbox)\{[^{}]*\}",
            r"\\TEXT{}",
            value,
        )
    return re.sub(r"\s+", "", value)


def corrected_answer_math_view(text: str) -> tuple[str, list[dict[str, str]]]:
    """Undo only the four frozen answer-value edits for structural comparison."""
    edits: list[dict[str, str]] = []
    result = text
    patterns = (
        (r"(?<![0-9.])-3\.16(?![0-9.])", "-3.18", "C16_Z"),
        (r"(?<![0-9.])0\.0016(?![0-9.])", "0.0014", "C16_p"),
        (r"(?<![0-9.])0\.37(?![0-9.])", "0.39", "C17_Z"),
        (r"(?<![0-9.])0\.7113(?![0-9.])", "0.6966", "C17_p"),
    )
    for pattern, replacement, label in patterns:
        count = len(re.findall(pattern, result))
        if count != 1:
            raise AssertionError(f"expected exactly one {label} target value, found {count}")
        result = re.sub(pattern, replacement, result, count=1)
        edits.append({"id": label, "replacement": replacement})
    # The target deliberately puts the corrected p-value equality in an inline
    # math span; the authority has it as ordinary prose.  Remove only that
    # exact wrapper after the numeric inverse above.
    wrapped = re.findall(r"\$=\s*0\.0014\$", result)
    if len(wrapped) != 1:
        raise AssertionError(f"expected one corrected p-value math wrapper, found {len(wrapped)}")
    result = result.replace("$= 0.0014$", "= 0.0014", 1)
    edits.append({"id": "C16_math_wrapper", "replacement": "plain-equality"})
    # Term-QA's answer-27 clarification makes the comparison threshold
    # explicit in math.  For structural comparison only, normalize this one
    # wrapper back to the authority's prose threshold; the raw target remains
    # unchanged and the edit is recorded.
    alpha_wrapper = TERM_QA_C18["target_wrapper"]
    alpha_lines = [
        index
        for index, line in enumerate(lines(result), 1)
        if alpha_wrapper in line
    ]
    expected_alpha_line = TERM_QA_C18["target_line"]
    if alpha_lines != [expected_alpha_line]:
        raise AssertionError(
            "expected one C18 alpha math wrapper at target line "
            f"{expected_alpha_line}, found {alpha_lines}"
        )
    if TERM_QA_C18["target_anchor"] not in lines(result)[expected_alpha_line - 1]:
        raise AssertionError("C18 target anchor drifted")
    result = result.replace(alpha_wrapper, "alpha = 0.05", 1)
    edits.append({"id": "C18_alpha_math_wrapper", "replacement": "plain-threshold-prose"})
    return result, edits


def math_skeletons(text: str) -> dict[str, list[str]]:
    inline = [strip_math_text_nodes(value) for value in MATH_SPAN_RE.findall(text)]
    display = [strip_math_text_nodes(value) for _, value in DISPLAY_RE.findall(text)]
    return {"inline": inline, "display": display}


def delimiter_counts(text: str) -> dict[str, int]:
    counts = {"{": 0, "}": 0, "[": 0, "]": 0}
    stack: list[str] = []
    escaped = False
    for char in text:
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char not in counts:
            continue
        counts[char] += 1
        if char in "{[":
            stack.append(char)
        elif char == "}" or char == "]":
            expected = "{" if char == "}" else "["
            if not stack or stack[-1] != expected:
                raise AssertionError(f"unbalanced delimiter {char} in translation")
            stack.pop()
    if stack:
        raise AssertionError(f"unclosed delimiters {stack}")
    return counts


def comments_mask(values: Iterable[str]) -> list[int]:
    return [index for index, value in enumerate(values, 1) if value.lstrip().startswith("%")]


def blanks_mask(values: Iterable[str]) -> list[int]:
    return [index for index, value in enumerate(values, 1) if not value.strip()]


def compare_numbers(
    pair: dict[str, Any], source: str, target: str
) -> dict[str, Any]:
    source_entries = number_entries(source, pair["first"])
    target_entries = number_entries(target, 1)
    source_values = [value for value, _ in source_entries]
    target_values = [value for value, _ in target_entries]
    # Copy the per-pair counters: self-check deliberately replays the entire
    # projection, so an audit pass must never consume global exception state.
    lexical = dict(ALLOWED_LEXICAL_NUMBER_REMOVALS.get(pair["id"], {}))
    removed: list[dict[str, Any]] = []
    filtered_source: list[str] = []
    for value, line in source_entries:
        if value == "2" and lexical.get(line, 0) > 0:
            lexical[line] -= 1
            removed.append({"value": value, "source_line": line, "reason": "2-proportion -> dua proporsi"})
        else:
            filtered_source.append(value)
    if any(count != 0 for count in lexical.values()):
        raise AssertionError(f"lexical numeric exception anchor missing for {pair['id']}")
    replacements: list[dict[str, str]] = []
    if pair["id"] == "public-answers-1363-1472":
        expected = (("3.16", "3.18", "C16_Z"), ("0.0016", "0.0014", "C16_p"), ("0.37", "0.39", "C17_Z"), ("0.7113", "0.6966", "C17_p"))
        for new, old, label in expected:
            if target_values.count(new) != 1:
                raise AssertionError(f"expected one corrected numeric value {new} ({label})")
            target_values[target_values.index(new)] = old
            replacements.append({"id": label, "target": new, "authority": old})
    if filtered_source != target_values:
        raise AssertionError(
            f"numeric skeleton mismatch for {pair['id']}: "
            f"authority={len(filtered_source)} target={len(target_values)}"
        )
    return {
        "source_count": len(source_values),
        "target_count": len(number_entries(target, 1)),
        "equal_after_explicit_exceptions": True,
        "lexical_number_removals": removed,
        "corrected_numeric_replacements": replacements,
    }


def compare_controls(pair: dict[str, Any], source: str, target: str) -> dict[str, Any]:
    source_entries = command_entries(source, pair["first"])
    target_entries = command_entries(target, 1)
    if pair["id"] == TERM_QA_C18["chunk"]:
        source_lines = lines(source)
        target_lines = lines(target)
        source_index = TERM_QA_C18["source_line"] - pair["first"]
        target_index = TERM_QA_C18["target_line"] - 1
        if source_index < 0 or source_index >= len(source_lines):
            raise AssertionError("C18 source anchor is outside the audited source slice")
        if target_index < 0 or target_index >= len(target_lines):
            raise AssertionError("C18 target anchor is outside the audited target")
        if TERM_QA_C18["source_anchor"] not in source_lines[source_index]:
            raise AssertionError("C18 source anchor drifted")
        if TERM_QA_C18["target_anchor"] not in target_lines[target_index]:
            raise AssertionError("C18 target anchor drifted")
    allowed = dict(ALLOWED_PERCENT_REMOVALS.get(pair["id"], {}))
    removed: list[dict[str, Any]] = []
    filtered_source: list[str] = []
    for value, line in source_entries:
        if value == r"\%" and allowed.get(line, 0) > 0:
            allowed[line] -= 1
            removed.append({"token": value, "source_line": line})
        else:
            filtered_source.append(value)
    if any(count != 0 for count in allowed.values()):
        raise AssertionError(f"percentage exception anchor missing for {pair['id']}")
    target_values = [value for value, _ in target_entries]
    # Consume only the explicitly documented term-QA control addition.  Keep
    # the raw target count in the receipt while comparing the normalized
    # stream against the authority.
    allowed_additions = {
        line: dict(tokens)
        for line, tokens in ALLOWED_TERM_QA_CONTROL_ADDITIONS.get(pair["id"], {}).items()
    }
    additions_removed: list[dict[str, Any]] = []
    if allowed_additions:
        kept_entries: list[tuple[str, int]] = []
        for value, line in target_entries:
            line_tokens = allowed_additions.get(line, {})
            if value in line_tokens and line_tokens[value] > 0:
                line_tokens[value] -= 1
                additions_removed.append(
                    {
                        "id": TERM_QA_C18["id"],
                        "token": value,
                        "source_line": TERM_QA_C18["source_line"],
                        "target_line": line,
                        "reason": TERM_QA_C18["reason"],
                    }
                )
            else:
                kept_entries.append((value, line))
        if any(count for tokens in allowed_additions.values() for count in tokens.values()):
            raise AssertionError(f"term-QA control addition anchor missing for {pair['id']}")
        target_values = [value for value, _ in kept_entries]
    if filtered_source != target_values:
        raise AssertionError(
            f"TeX control stream mismatch for {pair['id']}: "
            f"authority={len(filtered_source)} target={len(target_values)}"
        )
    return {
        "source_count": len(source_entries),
        "target_count": len(target_entries),
        "equal_after_explicit_exceptions": True,
        "allowed_percent_removals": removed,
        "allowed_term_qa_control_additions": additions_removed,
    }


def validate_layout(pair: dict[str, Any], target_lines: list[str], source_lines: list[str]) -> dict[str, Any]:
    source_count = len(source_lines)
    target_count = len(target_lines)
    if pair["id"] not in LAYOUT_VARIANTS:
        if target_count != source_count:
            raise AssertionError(f"line count mismatch for {pair['id']}: {target_count} != {source_count}")
        variant = {
            "name": "exact_source_line_layout",
            "target_lines": target_count,
            "blank_positions": blanks_mask(source_lines),
            "comment_positions": comments_mask(source_lines),
            "anchors": (),
        }
    else:
        variants = LAYOUT_VARIANTS[pair["id"]]
        variant = next((item for item in variants if item["target_lines"] == target_count), None)
        if variant is None:
            raise AssertionError(f"unapproved target line count {target_count} for {pair['id']}")
        if blanks_mask(target_lines) != variant["blank_positions"]:
            raise AssertionError(f"blank-line mask drift for {pair['id']} ({variant['name']})")
        if comments_mask(target_lines) != variant["comment_positions"]:
            raise AssertionError(f"comment-line mask drift for {pair['id']} ({variant['name']})")
        for line_number, anchor in variant["anchors"]:
            if line_number > len(target_lines) or anchor not in target_lines[line_number - 1]:
                raise AssertionError(f"missing reflow anchor {anchor!r} at target line {line_number}")
    return {
        "source_lines": source_count,
        "target_lines": target_count,
        "line_count_exact": source_count == target_count,
        "approved_variant": variant["name"],
        "blank_positions_source": blanks_mask(source_lines),
        "blank_positions_target": blanks_mask(target_lines),
        "comment_positions_source": comments_mask(source_lines),
        "comment_positions_target": comments_mask(target_lines),
        "explicit_reflow_exception": source_count != target_count,
    }


def validate_corrections(targets: dict[str, str]) -> list[dict[str, Any]]:
    # The blueprint itself is the source of the frozen candidate list; require
    # both its count and exact location order to prevent exception creep.
    blueprint = json.loads(BLUEPRINT.read_text(encoding="utf-8"))
    candidates = blueprint.get("correction_candidates")
    if not isinstance(candidates, list) or len(candidates) != len(FROZEN_CORRECTIONS):
        raise AssertionError("blueprint correction-candidate count is not 17")
    if [entry.get("location") for entry in candidates] != [entry["location"] for entry in FROZEN_CORRECTIONS]:
        raise AssertionError("blueprint correction locations drifted from frozen set")
    joined = "\n".join(targets.values())
    # Evidence is intentionally scoped to the target fragments and checked as
    # a set.  This catches a dropped correction without constraining ordinary
    # Indonesian wording beyond the recorded high-confidence meaning.
    evidence: list[dict[str, Any]] = []
    for correction in FROZEN_CORRECTIONS:
        found = [needle for needle in correction["evidence"] if needle.lower() in joined.lower()]
        if correction["id"] == "C13" and "Nevaripine" in joined:
            raise AssertionError("old Nevaripine spelling remains in target")
        if not found:
            raise AssertionError(f"missing evidence for frozen correction {correction['id']}")
        evidence.append(
            {
                "id": correction["id"],
                "location": correction["location"],
                "kind": correction["kind"],
                "evidence_found": found,
            }
        )
    # Exact old answer values may not survive the corrected public answers.
    answer = targets["public-answers-1363-1472"]
    for old in ("-3.18", "0.0014", "0.39", "0.6966"):
        if old in answer:
            raise AssertionError(f"old corrected public-answer value remains: {old}")
    return evidence


def validate_figure_calls(source: str, target: str) -> dict[str, Any]:
    src = figure_calls(source)
    dst = figure_calls(target)
    if len(src) != len(dst):
        raise AssertionError(f"figure-call count mismatch: {len(src)} != {len(dst)}")
    rows: list[dict[str, Any]] = []
    for index, (left, right) in enumerate(zip(src, dst), 1):
        if left["macro"] != right["macro"] or left["args"] != right["args"]:
            raise AssertionError(f"figure identity/geometry drift at call {index}")
        if not right["alt"] or right["alt"] == left["alt"]:
            raise AssertionError(f"figure alt text not localized at call {index}")
        rows.append(
            {
                "ordinal": index,
                "macro": right["macro"],
                "args": right["args"],
                "source_alt": left["alt"],
                "target_alt": right["alt"],
                "target_line": right["line"],
            }
        )
    return {"count": len(rows), "calls": rows}


def validate_identifiers(source: str, target: str) -> dict[str, Any]:
    src = macro_invocations(source, IDENT_NAMES)
    dst = macro_invocations(target, IDENT_NAMES)
    def protected(invocations: list[tuple[str, tuple[str, ...]]]) -> list[tuple[str, tuple[str, ...]]]:
        normalized: list[tuple[str, tuple[str, ...]]] = []
        for name, args in invocations:
            if name != "oiRedirect":
                normalized.append((name, args))
                continue
            # The first oiRedirect argument is the stable redirect key.  A
            # second argument is either a URL (protected) or reader-visible
            # link text (translated freely).
            kept = list(args[:1])
            if len(args) > 1 and re.search(r"https?://", args[1], re.IGNORECASE):
                kept.append(args[1])
            normalized.append((name, tuple(kept)))
        return normalized

    if protected(src) != protected(dst):
        raise AssertionError("label/reference/citation/redirect/input invocation drift")
    return {
        "count": len(src),
        "sequence_equal": True,
        "names": [name for name, _ in src],
    }


def target_language_checks(targets: dict[str, str]) -> dict[str, Any]:
    joined_active = "\n".join(
        line
        for text in targets.values()
        for line in lines(text)
        if not line.lstrip().startswith("%")
    )
    banned = (
        "Difference of two proportions",
        "Sampling distribution of the difference",
        "Confidence intervals for",
        "Hypothesis tests for the difference",
        "More on 2-proportion hypothesis tests",
        "A mammogram is an X-ray procedure",
        "We are 90% confident",
        "Create and interpret a 90% confidence interval",
        "The quality control engineer from",
        "Since we observed a larger-than-3",
        "Conduct a hypothesis test to evaluate",
        "Can she used a two-proportion",
        "This is not a randomized experiment",
    )
    residue = [phrase for phrase in banned if phrase.lower() in joined_active.lower()]
    if residue:
        raise AssertionError(f"active English residue: {residue}")
    required = (
        "selisih dua proporsi",
        "distribusi sampling",
        "interval kepercayaan",
        "uji hipotesis",
        "syarat sukses--gagal",
        "poin persentase",
        "nilai-p",
    )
    missing = [phrase for phrase in required if phrase.lower() not in joined_active.lower()]
    if missing:
        raise AssertionError(f"required Indonesian terminology missing: {missing}")
    for phrase in (
        "A normal distribution is shown",
        "A photo of a Phantom quadcopter drone",
        "A normal distribution is shown that is centered",
    ):
        if phrase.lower() in joined_active.lower():
            raise AssertionError(f"untranslated figure alt phrase remains: {phrase}")
    return {
        "status": "PASS",
        "banned_active_source_phrases": list(banned),
        "residue": [],
        "required_terms": list(required),
    }


def validate_exercise_answer_closure(targets: dict[str, str]) -> dict[str, Any]:
    exercises = targets["exercises-1-212"] + targets["exercises-213-406"]
    labels = [value for _, value in re.findall(r"(\\label)\{([^{}]+)\}", exercises)]
    expected_labels = [
        "social_experiment_conditions",
        "heart_transplant_conditions",
        "gender_color_preference_CI_concept",
        "government_shutdown_CI_concept",
        "national_health_plan_CI_replaced",
        "sleep_OR_CA_CI",
        "offshore_drill_edu_dontknow_HT",
        "sleep_OR_CA_HT",
        "offshore_drill_edu_support_HT",
        "full_body_scan_HT_Error",
        "sleep_deprived_driver_HT",
        "prenatal_vitamin_autism_HT",
        "hiv_africa_HT",
        "apple_doctor_HT_concept",
    ]
    if labels != expected_labels:
        raise AssertionError(f"exercise label closure drift: {labels}")
    if exercises.count(r"\eoce{") != 14:
        raise AssertionError("expected exactly 14 public exercise records")
    if r"\eocesol{" in exercises or r"\solution" in exercises.lower():
        raise AssertionError("restricted/invented solution material in exercise targets")
    answers = targets["public-answers-1363-1472"]
    public_ids = [int(value) for value in ORDINAL_RE.findall(answers)]
    expected_public = [17, 19, 21, 23, 25, 27, 29]
    if public_ids != expected_public:
        raise AssertionError(f"public answer ordinal closure drift: {public_ids}")
    if answers.count(r"\eocesol{") != len(expected_public):
        raise AssertionError("public answer macro count drift")
    if any(value % 2 == 0 for value in public_ids):
        raise AssertionError("even/O001 answer accidentally included")
    if FORBIDDEN_COMMAND_RE.search("\n".join(targets.values())):
        raise AssertionError("restricted instructor-solution command detected")
    return {
        "exercise_ids": list(range(17, 31)),
        "exercise_labels": labels,
        "public_answer_ids": expected_public,
        "o001_mastery_gap_ids": list(range(18, 31, 2)),
        "exercise_records": 14,
        "public_answer_records": 7,
        "restricted_instructor_solutions_accessed_or_invented": False,
    }


def audit_projection() -> dict[str, Any]:
    if not BLUEPRINT.exists():
        raise AssertionError(f"missing blueprint {rel(BLUEPRINT)}")
    blueprint_id = identity(BLUEPRINT)
    if blueprint_id != BLUEPRINT_ID:
        raise AssertionError(f"blueprint identity drift: {blueprint_id}")
    blueprint = json.loads(BLUEPRINT.read_text(encoding="utf-8"))
    if blueprint.get("authority", {}).get("commit") != COMMIT or blueprint.get("authority", {}).get("tree") != TREE:
        raise AssertionError("blueprint authority pin drift")
    if blueprint.get("boundary_id") != "R011-B023":
        raise AssertionError("wrong blueprint boundary")

    full_sources = []
    for witness in FULL_SOURCE_WITNESSES:
        path = AUTH / witness["path"]
        actual = identity(path)
        expected = {"path": (AUTH_REL / witness["path"]).as_posix(), "bytes": witness["bytes"], "sha256": witness["sha256"]}
        if actual != expected:
            raise AssertionError(f"full source identity drift: {actual} != {expected}")
        full_sources.append({**actual, "role": witness["role"]})

    targets: dict[str, str] = {}
    source_records: list[dict[str, Any]] = []
    target_records: list[dict[str, Any]] = []
    checks: dict[str, Any] = {}
    figure_records: list[dict[str, Any]] = []
    for pair in CHUNKS:
        source_raw, source_text, source_lines = source_slice(pair)
        target_path = LANE / pair["target"]
        target_raw, target_text = read_utf8_lf(target_path)
        targets[pair["id"]] = target_text
        target_lines = lines(target_text)
        source_id = {
            "path": (AUTH_REL / pair["source"]).as_posix(),
            "line_range_inclusive": f"{pair['first']}-{pair['last']}",
            "lines": len(source_lines),
            "bytes": len(source_raw),
            "sha256": sha256_bytes(source_raw),
        }
        target_id = identity(target_path)
        source_records.append({**source_id, "role": pair["role"]})
        target_records.append({**target_id, "lines": len(target_lines), "role": pair["role"]})

        layout = validate_layout(pair, target_lines, source_lines)
        controls = compare_controls(pair, source_text, target_text)
        environments = env_tokens(source_text) == env_tokens(target_text)
        if not environments:
            raise AssertionError(f"environment stream mismatch for {pair['id']}")
        identifiers = validate_identifiers(source_text, target_text)
        if pair["id"] == "public-answers-1363-1472":
            math_target, math_edits = corrected_answer_math_view(target_text)
        else:
            math_target, math_edits = target_text, []
        source_math = math_skeletons(source_text)
        target_math = math_skeletons(math_target)
        if source_math != target_math:
            raise AssertionError(f"math skeleton mismatch for {pair['id']}")
        numbers = compare_numbers(pair, source_text, target_text)
        source_delimiters = delimiter_counts(source_text)
        target_delimiters = delimiter_counts(target_text)
        if source_delimiters != target_delimiters:
            raise AssertionError(f"brace/bracket count drift for {pair['id']}")
        figures = validate_figure_calls(source_text, target_text)
        if figures["count"]:
            figure_records.extend([{**row, "chunk": pair["id"]} for row in figures["calls"]])
        checks[pair["id"]] = {
            "layout": layout,
            "tex_controls": controls,
            "environments": {
                "source_count": len(env_tokens(source_text)),
                "target_count": len(env_tokens(target_text)),
                "sequence_equal": True,
            },
            "identifiers": identifiers,
            "math": {
                "source_inline_count": len(source_math["inline"]),
                "target_inline_count": len(target_math["inline"]),
                "source_display_count": len(source_math["display"]),
                "target_display_count": len(target_math["display"]),
                "skeleton_equal_after_text_and_frozen_value_normalization": True,
                "frozen_math_normalization_edits": math_edits,
            },
            "numbers": numbers,
            "delimiters": {
                "source": source_delimiters,
                "target": target_delimiters,
                "equal": True,
            },
            "figures": figures,
        }

    corrections = validate_corrections(targets)
    closure = validate_exercise_answer_closure(targets)
    language = target_language_checks(targets)
    return {
        "$schema": "interlanguage.r011-b023-translation-audit/v1",
        "boundary_id": "R011-B023",
        "status": "PASS_TRANSLATION_AND_PROTECTED_TEX_CLOSURE",
        "translation_provenance": MODEL,
        "authority": {
            "repository": "https://github.com/OpenIntroStat/openintro-statistics",
            "branch": "master",
            "commit": COMMIT,
            "tree": TREE,
            "observed": "2026-08-20",
            "reader_witness": "https://www.openintro.org/book/os/",
            "blueprint": blueprint_id,
            "full_sources": full_sources,
        },
        "source_slices": source_records,
        "targets": target_records,
        "checks": checks,
        "figure_call_closure": figure_records,
        "frozen_source_corrections": {
            "count": len(corrections),
            "allowed_count": 17,
            "applied": corrections,
            "unauthorized_exception_count": 0,
        },
        "exercise_answer_closure": closure,
        "language": language,
        "rights_and_scope": {
            "text_source_starting_license": "CC BY-SA 3.0; ancillary rights remain component-specific per B023 blueprint",
            "quadcopter_photo": "CC BY 2.0 David J; attribution/crop-border notice retained by source closure",
            "restricted_solutions_accessed_or_invented": False,
            "canonical_source_mutated": False,
            "live_backend_or_controls_mutated": False,
            "release_or_publication_mutated": False,
            "git_used": False,
            "network_used": False,
            "credentials_accessed": False,
            "upstream_contacted": False,
        },
        "next_cursor": {
            "path": "authority/upstream/openintro-statistics-fee25091fb24e89c36296fd67c48c1fcf7a93b6e/ch_inference_for_props/TeX/ch_inference_for_props.tex",
            "line": 1344,
            "label": "oneWayChiSquare",
            "label_line": 1345,
            "next_boundary": "R011-B024",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--self-check", action="store_true")
    mode.add_argument("--probe", action="store_true")
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--verify", action="store_true")
    args = parser.parse_args()

    first = canonical_bytes(audit_projection())
    if args.self_check:
        second = canonical_bytes(audit_projection())
        if first != second:
            raise AssertionError("in-process deterministic replay mismatch")
    if args.write:
        RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        RECEIPT.write_bytes(first)
    elif args.verify:
        if not RECEIPT.exists() or RECEIPT.read_bytes() != first:
            raise AssertionError("on-disk B023 translation audit receipt differs from exact replay")
    payload = json.loads(first.decode("utf-8"))
    output: dict[str, Any] = {
        "status": "PASS",
        "mode": "self-check" if args.self_check else "probe" if args.probe else "write" if args.write else "verify",
        "boundary_id": "R011-B023",
        "translation_provenance": MODEL,
        "target_count": len(CHUNKS),
        "source_slice_count": len(payload["source_slices"]),
        "line_count_exceptions": [],
    }
    # Keep the CLI summary simple and deterministic; the canonical receipt is
    # the detailed evidence surface.  Compute reflow rows directly instead of
    # retaining a dynamic comprehension artifact.
    output["line_count_exceptions"] = []
    for chunk_id, chunk_checks in payload["checks"].items():
        layout = chunk_checks["layout"]
        if layout["explicit_reflow_exception"]:
            target = next(item for item in payload["targets"] if item["role"] == next(pair["role"] for pair in CHUNKS if pair["id"] == chunk_id))
            output["line_count_exceptions"].append(
                {
                    "target": target["path"],
                    "variant": layout["approved_variant"],
                    "source_lines": layout["source_lines"],
                    "target_lines": layout["target_lines"],
                }
            )
    if args.write or args.verify:
        output["receipt"] = identity(RECEIPT)
    print(json.dumps(output, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, OSError, json.JSONDecodeError) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        raise SystemExit(1)
