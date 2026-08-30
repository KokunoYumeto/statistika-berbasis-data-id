#!/usr/bin/env python3
"""Deterministically audit staged R011-B026 main translation Parts D and E."""

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
BLUEPRINT_REL = Path("qa/b026-source/R011-B026_BOUNDARY_BLUEPRINT.json")
TARGET_A_REL = Path("qa/b026-translation/staging/chapter-lines-634-796.id.tex")
TARGET_B_REL = Path("qa/b026-translation/staging/chapter-lines-797-896.id.tex")
RECEIPT_REL = Path("qa/b026-translation/R011-B026_MAIN_TRANSLATION_PARTS_DE_QA.json")

SOURCE = LANE / SOURCE_REL
BLUEPRINT = LANE / BLUEPRINT_REL
TARGET_A = LANE / TARGET_A_REL
TARGET_B = LANE / TARGET_B_REL
RECEIPT = LANE / RECEIPT_REL

EXPECTED_SOURCE_FILE_SHA256 = (
    "d818b24b8e8d0582f8e603972e87764082d8470d91ddcbeaa794c295a1d37bec"
)
EXPECTED_BLUEPRINT_SHA256 = (
    "2340adb156e7dd6833a2421eed9b6b4e2f7045e347f4fe8639544028cd6ced34"
)

PARTS = [
    {
        "part": "D",
        "first_line": 634,
        "last_line": 796,
        "source_bytes": 6099,
        "source_sha256": "e488a127faa7e527d516ab67c9125b2e24af932fef8e22de1c62a4b8404b2ce1",
        "target": TARGET_A,
        "target_bytes": 6278,
        "target_sha256": "bf908c142ee30f0b0e2a4d96b06c87d72ad941c7bba5af99d59786ee437c0613",
        "blueprint_index": 4,
    },
    {
        "part": "E",
        "first_line": 797,
        "last_line": 896,
        "source_bytes": 3642,
        "source_sha256": "2361cd6e2d4fe867200c0ebf2792001baa17c524347e66e3f09253862d47c44c",
        "target": TARGET_B,
        "target_bytes": 3804,
        "target_sha256": "c56ea68a482ed32479d4a9968f6bbac4d117a2f68b0c8774709a9e505884773d",
        "blueprint_index": 5,
    },
]

INDONESIAN_ANCHORS = [
    "Interval kepercayaan $t$ satu sampel",
    "rata-rata kandungan merkuri",
    "syarat independensi",
    "syarat normalitas",
    "nilai kritis",
    "derajat kebebasan",
    "galat baku",
    "Latihan Terarah",
    "interval kepercayaan bagi satu rata-rata",
    "observasi individual",
    "Uji $t$ satu sampel",
]

RESIDUAL_ENGLISH_PATTERNS = [
    r"\bLet's get our first taste\b",
    r"\bmercury content\b",
    r"\bdolphin muscle\b",
    r"\bElevated mercury concentrations\b",
    r"\bshown surfacing in water\b",
    r"\bPhoto by\b",
    r"\bSummary of mercury\b",
    r"\bMeasurements are in\b",
    r"\bconditions satisfied\b",
    r"\bsimple random sample\b",
    r"\bstandard deviations of the mean\b",
    r"\bBased on this evidence\b",
    r"\bcompute the standard error\b",
    r"\bWe plug in\b",
    r"\bconfidence level\b",
    r"\bupper tail\b",
    r"\barea below\b",
    r"\bCompute and interpret\b",
    r"\bWe are 95\b",
    r"\bpopulation mean\b",
    r"\bFDA's webpage\b",
    r"\bparts per million\b",
    r"\bsummary statistics of the data\b",
    r"\bGuided Practice\b",
    r"\bactual mean\b",
    r"\bOnce you've determined\b",
    r"\bfour steps to constructing\b",
    r"\bVerify the conditions\b",
    r"\bIf the conditions hold\b",
    r"\bInterpret the confidence interval\b",
    r"\bplausible values\b",
    r"\bindividual observations\b",
    r"\bOne sample\b",
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
    if not data.endswith(b"\n"):
        raise AssertionError(f"file lacks a final LF: {path}")
    return data.splitlines(keepends=True)


def canonical_bytes(payload: dict[str, object]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def comment_start(line: str) -> int | None:
    for index, char in enumerate(line):
        if char != "%":
            continue
        backslashes = 0
        cursor = index - 1
        while cursor >= 0 and line[cursor] == "\\":
            backslashes += 1
            cursor -= 1
        if backslashes % 2 == 0:
            return index
    return None


def strip_tex_comment(line: str) -> str:
    start = comment_start(line)
    return line if start is None else line[:start]


def comment_suffix(line: str) -> str:
    start = comment_start(line)
    return "" if start is None else line[start:]


def active_text(lines: list[str]) -> str:
    return "\n".join(strip_tex_comment(line) for line in lines)


def command_sequence(text: str) -> list[str]:
    return re.findall(r"\\(?:[A-Za-z@]+|.)", text)


def environment_sequence(text: str) -> list[tuple[str, str]]:
    return re.findall(r"\\(begin|end)\{([^{}]+)\}", text)


def normalize_localizable_math_text(text: str) -> str:
    value = re.sub(r"\\text\{[^{}]*\}", r"\\text{<localized-prose>}", text)
    return re.sub(r"\s+", "", value)


def inline_math_segments(text: str) -> list[str]:
    raw = re.findall(r"(?<!\\)\$(?:\\.|[^$])*(?<!\\)\$", text, flags=re.S)
    return [normalize_localizable_math_text(value) for value in raw]


def math_environment_segments(text: str) -> list[str]:
    raw = re.findall(
        r"\\begin\{(align\*?|equation\*?)\}(.*?)\\end\{\1\}",
        text,
        flags=re.S,
    )
    return [f"{name}:{normalize_localizable_math_text(body)}" for name, body in raw]


def protected_sequences(text: str) -> dict[str, object]:
    active = "\n".join(strip_tex_comment(line) for line in text.splitlines())
    return {
        "labels": re.findall(r"\\label\{([^{}]+)\}", active),
        "refs": re.findall(r"\\(?:ref|pageref)\{([^{}]+)\}", active),
        "figure_bindings": re.findall(
            r"\\Figures\[(?:\\.|[^]])*\]\{([^{}]+)\}\{([^{}]+)\}\{([^{}]+)\}",
            active,
            flags=re.S,
        ),
        "redirect_keys": re.findall(r"\\oiRedirect\{([^{}]+)\}", active),
        "caption_short_labels": re.findall(r"\\caption\[([^]]+)\]", active),
        "numeric_tokens": re.findall(r"(?<![A-Za-z])\d+(?:\.\d+)?(?![A-Za-z])", active),
    }


def visible_for_language_scan(text: str) -> str:
    value = re.sub(r"(?<!\\)\$(?:\\.|[^$])*(?<!\\)\$", " ", text, flags=re.S)
    value = re.sub(r"\\(?:[A-Za-z@]+|.)", " ", value)
    value = value.replace("{", " ").replace("}", " ")
    return re.sub(r"\s+", " ", value)


def line_has_english_prose(line: str) -> bool:
    value = strip_tex_comment(line)
    value = re.sub(r"(?<!\\)\$(?:\\.|[^$])*(?<!\\)\$", " ", value)
    return bool(
        re.search(
            r"\b(?:the|and|are|is|we|of|for|with|where|using|based|compute|"
            r"confidence|mean|sample|observations|distribution|degrees)\b",
            value,
            flags=re.IGNORECASE,
        )
    )


def overlapping_blueprint_repairs(
    blueprint: dict[str, object], first_line: int, last_line: int
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
        repair_first = int(line_match.group(1))
        repair_last = int(line_match.group(2) or repair_first)
        if repair_first <= last_line and repair_last >= first_line:
            matches.append(candidate)
    return matches


def audit_part(
    part: dict[str, object], source_all_lines: list[bytes], blueprint: dict[str, object]
) -> dict[str, object]:
    first_line = int(part["first_line"])
    last_line = int(part["last_line"])
    target = part["target"]
    assert isinstance(target, Path)
    target_identity = identity(target)
    if target_identity["bytes"] != part["target_bytes"]:
        raise AssertionError(f"Part {part['part']} target byte-count drift")
    if target_identity["sha256"] != part["target_sha256"]:
        raise AssertionError(f"Part {part['part']} target hash drift")

    chunk = blueprint["translation_chunks"][int(part["blueprint_index"])]
    for key in ["first_line", "last_line", "bytes", "sha256"]:
        expected = part[f"source_{key}"] if key in {"bytes", "sha256"} else part[key]
        if chunk[key] != expected:
            raise AssertionError(f"Part {part['part']} blueprint chunk drift: {key}")

    source_lines_bytes = source_all_lines[first_line - 1 : last_line]
    target_lines_bytes = exact_lines(target)
    expected_line_count = last_line - first_line + 1
    if len(source_lines_bytes) != expected_line_count:
        raise AssertionError(f"Part {part['part']} source line-count drift")
    if len(target_lines_bytes) != expected_line_count:
        raise AssertionError(f"Part {part['part']} target line-count drift")
    source_slice = b"".join(source_lines_bytes)
    target_bytes = b"".join(target_lines_bytes)
    if len(source_slice) != part["source_bytes"] or sha256(source_slice) != part["source_sha256"]:
        raise AssertionError(f"Part {part['part']} source-slice identity drift")

    source_lines = [line.decode("utf-8").rstrip("\n") for line in source_lines_bytes]
    target_lines = [line.decode("utf-8").rstrip("\n") for line in target_lines_bytes]
    blank_source = [
        offset + first_line for offset, line in enumerate(source_lines) if not line.strip()
    ]
    blank_target = [
        offset + first_line for offset, line in enumerate(target_lines) if not line.strip()
    ]
    if blank_source != blank_target:
        raise AssertionError(f"Part {part['part']} blank-line topology drift")

    comment_lines: list[int] = []
    for offset, (source_line, target_line) in enumerate(zip(source_lines, target_lines)):
        if comment_suffix(source_line) or comment_suffix(target_line):
            line_number = first_line + offset
            comment_lines.append(line_number)
            if comment_suffix(source_line) != comment_suffix(target_line):
                raise AssertionError(f"comment witness drift at source line {line_number}")

    source_text = source_slice.decode("utf-8")
    target_text = target_bytes.decode("utf-8")
    if command_sequence(source_text) != command_sequence(target_text):
        raise AssertionError(f"Part {part['part']} TeX command-sequence drift")
    if environment_sequence(source_text) != environment_sequence(target_text):
        raise AssertionError(f"Part {part['part']} environment-sequence drift")
    if inline_math_segments(source_text) != inline_math_segments(target_text):
        raise AssertionError(f"Part {part['part']} inline-mathematics drift")
    if math_environment_segments(source_text) != math_environment_segments(target_text):
        raise AssertionError(f"Part {part['part']} display-mathematics drift")
    if protected_sequences(source_text) != protected_sequences(target_text):
        raise AssertionError(f"Part {part['part']} protected-sequence drift")

    control_counts: dict[str, dict[str, int]] = {}
    for token in ["{", "}", "$", "%", "~", "&", "\\"]:
        source_count = source_text.count(token)
        target_count = target_text.count(token)
        if source_count != target_count:
            raise AssertionError(f"Part {part['part']} protected-token drift: {token}")
        control_counts[token] = {"source": source_count, "target": target_count}

    unchanged_visible_source_lines = [
        offset + first_line
        for offset, (source_line, target_line) in enumerate(zip(source_lines, target_lines))
        if source_line == target_line and line_has_english_prose(source_line)
    ]
    if unchanged_visible_source_lines:
        raise AssertionError(
            f"Part {part['part']} unchanged learner-visible English: "
            f"{unchanged_visible_source_lines}"
        )

    visible = visible_for_language_scan(active_text(target_lines))
    residual_matches = [
        pattern
        for pattern in RESIDUAL_ENGLISH_PATTERNS
        if re.search(pattern, visible, flags=re.IGNORECASE)
    ]
    if residual_matches:
        raise AssertionError(f"Part {part['part']} residual English: {residual_matches}")

    repairs = overlapping_blueprint_repairs(blueprint, first_line, last_line)
    return {
        "part": part["part"],
        "source": {
            "path": SOURCE_REL.as_posix(),
            "first_line": first_line,
            "last_line": last_line,
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
            "mapping": f"target line 1 maps to source line {first_line}",
        },
        "qa": {
            "command_and_environment_sequences_exact": True,
            "inline_and_display_mathematics_exact_except_localized_text_wrappers": True,
            "labels_refs_assets_redirects_caption_bindings_and_numerics_exact": True,
            "blank_line_topology_exact": True,
            "comment_suffixes_exact": True,
            "comment_line_numbers": comment_lines,
            "control_token_counts": control_counts,
            "unchanged_learner_visible_source_lines": unchanged_visible_source_lines,
            "residual_english_patterns_checked": RESIDUAL_ENGLISH_PATTERNS,
            "residual_english_matches": residual_matches,
            "approved_blueprint_repairs_overlapping_part": repairs,
        },
    }


def build_receipt() -> dict[str, object]:
    if sha256(SOURCE.read_bytes()) != EXPECTED_SOURCE_FILE_SHA256:
        raise AssertionError("pinned chapter source identity drift")
    if sha256(BLUEPRINT.read_bytes()) != EXPECTED_BLUEPRINT_SHA256:
        raise AssertionError("B026 blueprint identity drift")
    blueprint = json.loads(BLUEPRINT.read_text("utf-8"))
    if blueprint["boundary_id"] != "R011-B026":
        raise AssertionError("wrong boundary blueprint")

    source_all_lines = exact_lines(SOURCE)
    audits = [audit_part(part, source_all_lines, blueprint) for part in PARTS]
    combined_target_text = TARGET_A.read_text("utf-8") + TARGET_B.read_text("utf-8")
    missing_anchors = [anchor for anchor in INDONESIAN_ANCHORS if anchor not in combined_target_text]
    if missing_anchors:
        raise AssertionError(f"missing Indonesian terminology anchors: {missing_anchors}")

    part_d_repairs = audits[0]["qa"]["approved_blueprint_repairs_overlapping_part"]
    part_e_repairs = audits[1]["qa"]["approved_blueprint_repairs_overlapping_part"]
    if len(part_d_repairs) != 1 or part_d_repairs[0]["location"] != (
        "ch_inference_for_means/TeX/ch_inference_for_means.tex:737-740"
    ):
        raise AssertionError("expected 737-740 source correction is not uniquely bound to Part D")
    if part_e_repairs:
        raise AssertionError("unexpected approved source correction overlaps Part E")

    target_a_lines = [line.decode("utf-8").rstrip("\n") for line in exact_lines(TARGET_A)]
    repair_evidence = {
        "source_lines": "737-740",
        "source_issue": part_d_repairs[0]["source_issue"],
        "translation_action": part_d_repairs[0]["translation_action"],
        "target_line_737": target_a_lines[737 - 634],
        "target_line_739": target_a_lines[739 - 634],
        "target_line_740": target_a_lines[740 - 634],
    }
    if repair_evidence["target_line_737"] != (
        "    Cari $t^{\\star}_{df}$ untuk banyaknya derajat kebebasan ini"
    ):
        raise AssertionError("line 737 repair evidence drift")
    if repair_evidence["target_line_739"] != "  Banyaknya derajat kebebasan mudah dihitung:":
        raise AssertionError("line 739 repair evidence drift")
    if repair_evidence["target_line_740"] != "  $df = n - 1 = 18$.":
        raise AssertionError("line 740 repair evidence drift")

    receipt: dict[str, object] = {
        "$schema": "interlanguage.r011-translation-qa/v1",
        "boundary_id": "R011-B026",
        "part": "main-parts-d-e",
        "status": (
            "PASS_COMPLETE_NATURAL_ID_ID_STRUCTURE_MATH_PROTECTED_TEX_"
            "APPROVED_REPAIR_AND_RESIDUAL_ENGLISH_QA"
        ),
        "provenance": {
            "production_model": "OpenAI Codex gpt-5.6-sol, Ultra",
            "role": "independent bounded id-ID translation audit and deterministic QA",
        },
        "authority": {
            "commit": COMMIT,
            "full_source": {
                "path": SOURCE_REL.as_posix(),
                "sha256": EXPECTED_SOURCE_FILE_SHA256,
            },
            "blueprint": identity(BLUEPRINT),
        },
        "audits": audits,
        "qa": {
            "source_order_and_one_to_one_line_mapping_exact": True,
            "combined_source_range": "634-896 inclusive",
            "combined_logical_lines": 263,
            "indonesian_terminology_anchors": INDONESIAN_ANCHORS,
            "learner_visible_residual_english_matches": [],
            "approved_source_repair": repair_evidence,
            "unrecorded_semantic_repairs_applied": False,
            "translation_quality_refinements": [
                "Aligned rata-rata kandungan merkuri word order with natural id-ID usage.",
                "Aligned the normality term to normalitas across the audited slices.",
                "Aligned cutoff terminology to nilai kritis used by the B026 exercises.",
                "Removed a literal English-style hyphen from interval kepercayaan t.",
                "Recast the literal objections question as a natural reason-to-doubt question.",
                "Removed an unnecessary second-person pronoun from the four-step summary.",
                "Used rata-rata kandungan merkuri and 90% dari consistently in the fish sequence.",
            ],
            "inactive_comment_policy": (
                "Every full-line or trailing inactive source comment suffix is retained exactly "
                "and excluded from learner-visible residual-English accounting."
            ),
        },
        "next_translation_cursor": {
            "path": SOURCE_REL.as_posix(),
            "line": 897,
            "blueprint_chunk": "897-1052 inclusive",
            "context": (
                "Cherry Blossom one-sample t test, summary box, video marker, and exercise input."
            ),
        },
        "scope_guards": {
            "other_staged_translation_files_mutated": False,
            "exercises_or_public_answers_mutated": False,
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
            raise AssertionError("on-disk B026 Parts D/E QA receipt differs from exact replay")

    result = {
        "status": "PASS_EXACT_REPLAY_R011_B026_MAIN_TRANSLATION_PARTS_DE",
        "mode": "write" if args.write else "verify" if args.verify else "self-check",
        "source_lines": "634-896 inclusive",
        "targets": [identity(TARGET_A), identity(TARGET_B)],
        "receipt": {
            "path": RECEIPT.relative_to(LANE).as_posix(),
            "bytes": len(first),
            "sha256": sha256(first),
            "on_disk_exact": RECEIPT.exists() and RECEIPT.read_bytes() == first,
        },
        "approved_repair": "source lines 737-740",
        "residual_english_matches": [],
        "next_translation_cursor": 897,
        "scope": "two staged translation slices plus deterministic QA script/receipt only",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
