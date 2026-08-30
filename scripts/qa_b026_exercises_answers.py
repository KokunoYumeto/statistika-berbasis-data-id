#!/usr/bin/env python3
"""Deterministically audit the staged R011-B026 exercises and public answers.

The audit is deliberately bounded to the complete Section 7.1 exercise file,
the frozen public-answer slice, and the separate O001 even-answer gap ledger.
It writes/verifies one receipt and never mutates authority, live source/backend,
control/output/release state, Git, credentials, or network.
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
EXERCISE_SOURCE_REL = (
    AUTH_REL
    / "ch_inference_for_means/TeX/one-sample_means_with_the_t-distribution.tex"
)
ANSWER_SOURCE_REL = AUTH_REL / "extraTeX/eoceSolutions/eoceSolutions.tex"
EXERCISE_TARGET_REL = Path(
    "qa/b026-translation/staging/exercises-lines-1-280.id.tex"
)
ANSWER_TARGET_REL = Path(
    "qa/b026-translation/staging/public-answers-lines-1623-1721.id.tex"
)
O001_REL = Path(
    "qa/b026-translation/staging/R011-B026_O001_MASTERY_GAPS.json"
)
BLUEPRINT_REL = Path("qa/b026-source/R011-B026_BOUNDARY_BLUEPRINT.json")
RECEIPT_REL = Path(
    "qa/b026-translation/R011-B026_EXERCISES_ANSWERS_QA.json"
)

EXERCISE_SOURCE = LANE / EXERCISE_SOURCE_REL
ANSWER_SOURCE = LANE / ANSWER_SOURCE_REL
EXERCISE_TARGET = LANE / EXERCISE_TARGET_REL
ANSWER_TARGET = LANE / ANSWER_TARGET_REL
O001 = LANE / O001_REL
BLUEPRINT = LANE / BLUEPRINT_REL
RECEIPT = LANE / RECEIPT_REL

ANSWER_FIRST_LINE = 1623
ANSWER_LAST_LINE = 1721

EXPECTED_BLUEPRINT_SHA256 = (
    "2340adb156e7dd6833a2421eed9b6b4e2f7045e347f4fe8639544028cd6ced34"
)
EXPECTED_EXERCISE_SOURCE_BYTES = 10225
EXPECTED_EXERCISE_SOURCE_SHA256 = (
    "5d41cfe653f9da3e3b78885c23b3b2d30cd698a11087424fca1abc104de451ae"
)
EXPECTED_ANSWER_SOURCE_BYTES = 106045
EXPECTED_ANSWER_SOURCE_SHA256 = (
    "6c4e01376db4c023cc7b3f9949490e57220ef1cb831c580da71efde6ce723268"
)
EXPECTED_ANSWER_SLICE_BYTES = 3169
EXPECTED_ANSWER_SLICE_SHA256 = (
    "e2841a9784a3d2412f6da418f51d0afd40da1b17b11865a2121b46e386ea2f16"
)
EXPECTED_EXERCISE_TARGET_BYTES = 10409
EXPECTED_EXERCISE_TARGET_SHA256 = (
    "d84536e75f75f66d59a2021ea3a18dd3e51bf146a37445eebc67ed634c4c4b21"
)
EXPECTED_ANSWER_TARGET_BYTES = 3247
EXPECTED_ANSWER_TARGET_SHA256 = (
    "ba75f7b07e02b58f76ac25cfe3e0ef0b1c98a8eedc7a60b6d9d80faebc4ee73f"
)
EXPECTED_O001_BYTES = 5723
EXPECTED_O001_SHA256 = (
    "3664d3af33ea9c00fe50c45e83f977285f1c6446632eeaaf6821291f5102b78b"
)

EXERCISE_IDS = list(range(1, 15))
PUBLIC_ANSWER_IDS = [1, 3, 5, 7, 9, 11, 13]
O001_GAP_IDS = [2, 4, 6, 8, 10, 12, 14]
EXERCISE_LABELS = [
    "identify_critical_t",
    "t_distribution",
    "find_T_pval_1_2_sided",
    "find_T_pval_2_2_sided",
    "work_backwards_1",
    "work_backwards_2",
    "ny_sleep_habits_2_sided",
    "adult_heights",
    "find_mean_2_sided",
    "critical_t_vs_z",
    "play_piano_2_sided",
    "auto_exhaust_lead_exposure_2_sided",
    "auto_exhaust_lead_exposure_2_sided_cond",
    "car_insurance_savings",
    "sat_scores_CI",
]
O001_LABEL_BY_ID = {
    2: "t_distribution",
    4: "find_T_pval_2_2_sided",
    6: "work_backwards_2",
    8: "adult_heights",
    10: "critical_t_vs_z",
    12: "auto_exhaust_lead_exposure_2_sided",
    14: "sat_scores_CI",
}

INDONESIAN_ANCHORS = [
    "Tentukan nilai kritis",
    "Distribusi $t$",
    "Tentukan nilai-p",
    "tingkat kepercayaan",
    "simpangan baku",
    "Kebiasaan tidur warga New York",
    "Tinggi badan orang dewasa",
    "estimasi titik",
    "uji hipotesis",
    "gas buang kendaraan",
    "paparan timbal",
    "margin galat",
    "jangan tolak $H_0$",
    "derajat kebebasan",
]

RESIDUAL_ENGLISH_PATTERNS = [
    r"\bIdentify the critical\b",
    r"\bAn independent random sample\b",
    r"\bFind the degrees of freedom\b",
    r"\bconfidence level\b",
    r"\bstandard deviation\b",
    r"\bDetermine which is which\b",
    r"\bFind the p-value\b",
    r"\bnull hypothesis\b",
    r"\bWorking backwards\b",
    r"\bSleep habits\b",
    r"\bStatistical summaries\b",
    r"\bpoint estimate\b",
    r"\bhypothesis test\b",
    r"\bHeights of adults\b",
    r"\bResearchers studying\b",
    r"\bWhat is the point estimate\b",
    r"\bExplain your reasoning\b",
    r"\bFind the mean\b",
    r"\bPlay the piano\b",
    r"\bConstruct a 95\b",
    r"\bAuto exhaust\b",
    r"\bCar insurance savings\b",
    r"\bSAT scores\b",
    r"\bHow large (?:of )?a sample\b",
    r"\bcolumn with two tails\b",
    r"\bdo not reject\b",
    r"\bThe mean is the midpoint\b",
    r"\bNew Yorkers sleep\b",
    r"\bThe sample is random\b",
    r"\bThe test statistic is\b",
    r"\bthe confidence interval is\b",
    r"\bIf the sample is large\b",
    r"\bround up for sample size\b",
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


def normalize_approved_math_repairs(text: str) -> str:
    return text.replace("^{*}", "^{\\star}")


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
        "citations": re.findall(r"\\footfullcite\{([^{}]+)\}", text),
        "numeric_tokens": re.findall(r"\d+(?:\.\d+)?", text),
        "figure_assets": re.findall(
            r"\\FigureFullPath\[.*?\]\{[^{}]*\}\{([^{}]+)\}", text, flags=re.S
        ),
        "minipage_widths": re.findall(
            r"\\begin\{minipage\}\[c\]\{([^{}]+)\}", text
        ),
    }


def tabular_specs(text: str) -> list[str]:
    return re.findall(r"\\begin\{tabular\}\{([^{}]+)\}", text)


def visible_for_language_scan(text: str) -> str:
    value = text
    value = re.sub(r"\\label\{[^{}]+\}", " ", value)
    value = re.sub(r"\\(?:ref|pageref|footfullcite)\{[^{}]+\}", " ", value)
    value = re.sub(r"(?<!\\)\$(?:\\.|[^$])*(?<!\\)\$", " ", value, flags=re.S)
    value = re.sub(r"\\(?:[A-Za-z@]+|.)", " ", value)
    value = value.replace("{", " ").replace("}", " ")
    return re.sub(r"\s+", " ", value)


def line_has_visible_prose(line: str) -> bool:
    value = strip_tex_comment(line)
    value = re.sub(r"\\label\{[^{}]+\}", " ", value)
    value = re.sub(r"\\(?:ref|pageref|footfullcite)\{[^{}]+\}", " ", value)
    value = re.sub(r"(?<!\\)\$(?:\\.|[^$])*(?<!\\)\$", " ", value)
    value = re.sub(r"\\(?:[A-Za-z@]+|.)", " ", value)
    words = re.findall(r"[A-Za-z]{2,}", value)
    return len(words) >= 3


def source_four_gram_residue(source_visible: str, target_visible: str) -> list[str]:
    source_words = re.findall(r"[A-Za-z]+", source_visible.lower())
    target_normalized = " " + " ".join(
        re.findall(r"[A-Za-z]+", target_visible.lower())
    ) + " "
    english_function_words = {
        "a", "an", "and", "are", "as", "at", "be", "been", "but", "by",
        "do", "does", "for", "from", "had", "has", "have", "if", "in",
        "is", "it", "of", "on", "or", "that", "the", "their", "then",
        "there", "these", "this", "to", "was", "we", "were", "what",
        "when", "where", "which", "will", "with", "would", "you", "your",
    }
    residues: list[str] = []
    for index in range(len(source_words) - 3):
        words = source_words[index : index + 4]
        phrase = " ".join(words)
        if sum(word in english_function_words for word in words) < 2:
            continue
        if f" {phrase} " in target_normalized and phrase not in residues:
            residues.append(phrase)
    return residues


def assert_identity(path: Path, expected_bytes: int, expected_sha: str, role: str) -> None:
    actual = identity(path)
    if actual["bytes"] != expected_bytes or actual["sha256"] != expected_sha:
        raise AssertionError(f"{role} identity drift: {actual}")


def build_receipt() -> dict[str, object]:
    assert_identity(BLUEPRINT, 52663, EXPECTED_BLUEPRINT_SHA256, "B026 blueprint")
    assert_identity(
        EXERCISE_SOURCE,
        EXPECTED_EXERCISE_SOURCE_BYTES,
        EXPECTED_EXERCISE_SOURCE_SHA256,
        "pinned exercise authority",
    )
    assert_identity(
        ANSWER_SOURCE,
        EXPECTED_ANSWER_SOURCE_BYTES,
        EXPECTED_ANSWER_SOURCE_SHA256,
        "pinned answer authority",
    )
    assert_identity(
        EXERCISE_TARGET,
        EXPECTED_EXERCISE_TARGET_BYTES,
        EXPECTED_EXERCISE_TARGET_SHA256,
        "staged exercise translation",
    )
    assert_identity(
        ANSWER_TARGET,
        EXPECTED_ANSWER_TARGET_BYTES,
        EXPECTED_ANSWER_TARGET_SHA256,
        "staged public-answer translation",
    )
    assert_identity(O001, EXPECTED_O001_BYTES, EXPECTED_O001_SHA256, "O001 ledger")

    blueprint = json.loads(BLUEPRINT.read_text("utf-8"))
    closure = blueprint["exercise_answer_closure"]
    if blueprint["boundary_id"] != "R011-B026":
        raise AssertionError("wrong boundary blueprint")
    if closure["chapter_exercise_ids"] != EXERCISE_IDS:
        raise AssertionError("blueprint exercise-ID closure drift")
    if closure["public_answer_ids"] != PUBLIC_ANSWER_IDS:
        raise AssertionError("blueprint public-answer closure drift")
    if closure["o001_gap_ids"] != O001_GAP_IDS:
        raise AssertionError("blueprint O001 closure drift")
    if closure["restricted_solutions_accessed_or_invented"] is not False:
        raise AssertionError("blueprint restricted-solution scope guard drift")

    exercise_source_lines_b = exact_lines(EXERCISE_SOURCE)
    exercise_target_lines_b = exact_lines(EXERCISE_TARGET)
    answer_source_all_b = exact_lines(ANSWER_SOURCE)
    answer_source_lines_b = answer_source_all_b[
        ANSWER_FIRST_LINE - 1 : ANSWER_LAST_LINE
    ]
    answer_target_lines_b = exact_lines(ANSWER_TARGET)
    if len(exercise_source_lines_b) != 280 or len(exercise_target_lines_b) != 280:
        raise AssertionError("exercise line-count mapping drift")
    if len(answer_source_lines_b) != 99 or len(answer_target_lines_b) != 99:
        raise AssertionError("public-answer line-count mapping drift")

    answer_source_slice = b"".join(answer_source_lines_b)
    if len(answer_source_slice) != EXPECTED_ANSWER_SLICE_BYTES:
        raise AssertionError("public-answer source-slice byte-count drift")
    if sha256(answer_source_slice) != EXPECTED_ANSWER_SLICE_SHA256:
        raise AssertionError("public-answer source-slice hash drift")

    exercise_source_lines = [line.decode("utf-8").rstrip("\n") for line in exercise_source_lines_b]
    exercise_target_lines = [line.decode("utf-8").rstrip("\n") for line in exercise_target_lines_b]
    answer_source_lines = [line.decode("utf-8").rstrip("\n") for line in answer_source_lines_b]
    answer_target_lines = [line.decode("utf-8").rstrip("\n") for line in answer_target_lines_b]

    blank_topology: dict[str, bool] = {}
    for role, source_lines, target_lines in [
        ("exercises", exercise_source_lines, exercise_target_lines),
        ("public_answers", answer_source_lines, answer_target_lines),
    ]:
        source_blank = [i + 1 for i, line in enumerate(source_lines) if not line]
        target_blank = [i + 1 for i, line in enumerate(target_lines) if not line]
        if source_blank != target_blank:
            raise AssertionError(f"{role} blank-line topology drift")
        blank_topology[role] = True

    comment_lines: dict[str, list[int]] = {"exercises": [], "public_answers": []}
    for role, source_lines, target_lines, first_line in [
        ("exercises", exercise_source_lines, exercise_target_lines, 1),
        ("public_answers", answer_source_lines, answer_target_lines, ANSWER_FIRST_LINE),
    ]:
        for offset, (source_line, target_line) in enumerate(zip(source_lines, target_lines)):
            if source_line.lstrip().startswith("%"):
                line_number = first_line + offset
                comment_lines[role].append(line_number)
                if source_line != target_line:
                    raise AssertionError(f"{role} comment witness drift at {line_number}")

    exercise_source_text = b"".join(exercise_source_lines_b).decode("utf-8")
    exercise_target_text = b"".join(exercise_target_lines_b).decode("utf-8")
    answer_source_text = answer_source_slice.decode("utf-8")
    answer_target_text = b"".join(answer_target_lines_b).decode("utf-8")

    normalized_exercise_source = normalize_approved_math_repairs(exercise_source_text)
    if command_sequence(normalized_exercise_source) != command_sequence(exercise_target_text):
        raise AssertionError("exercise TeX command sequence drift outside approved notation repair")
    if command_sequence(answer_source_text) != command_sequence(answer_target_text):
        raise AssertionError("public-answer TeX command sequence drift")
    if environment_sequence(exercise_source_text) != environment_sequence(exercise_target_text):
        raise AssertionError("exercise environment sequence drift")
    if environment_sequence(answer_source_text) != environment_sequence(answer_target_text):
        raise AssertionError("public-answer environment sequence drift")
    if math_segments(normalized_exercise_source) != math_segments(exercise_target_text):
        raise AssertionError("exercise mathematics drift outside approved notation repair")
    if math_segments(answer_source_text) != math_segments(answer_target_text):
        raise AssertionError("public-answer mathematics drift")

    exercise_source_protected = protected_sequences(normalized_exercise_source)
    exercise_target_protected = protected_sequences(exercise_target_text)
    answer_source_protected = protected_sequences(answer_source_text)
    answer_target_protected = protected_sequences(answer_target_text)
    if exercise_source_protected != exercise_target_protected:
        raise AssertionError("exercise labels/refs/citations/assets/widths/numerics drift")
    if answer_source_protected != answer_target_protected:
        raise AssertionError("public-answer labels/refs/citations/assets/widths/numerics drift")
    if exercise_target_protected["labels"] != EXERCISE_LABELS:
        raise AssertionError("exercise label sequence drift")
    if exercise_target_protected["refs"] != ["auto_exhaust_lead_exposure_2_sided_cond"]:
        raise AssertionError("exercise reference sequence drift")
    if exercise_target_protected["citations"] != ["Heinz:2003", "Mortada:2000"]:
        raise AssertionError("exercise citation sequence drift")
    if exercise_target_protected["figure_assets"] != [
        "ch_inference_for_means/figures/eoce/t_distribution/t_distribution",
        "ch_inference_for_means/figures/eoce/adult_heights/adult_heights_hist",
    ]:
        raise AssertionError("exercise figure binding drift")

    source_specs = tabular_specs(exercise_source_text)
    target_specs = tabular_specs(exercise_target_text)
    if source_specs != ["rrrrrr", "l|r l"] or target_specs != ["rrrrrr", "l|r"]:
        raise AssertionError("tabular topology drift outside approved two-column repair")

    control_counts: dict[str, dict[str, dict[str, int]]] = {}
    for role, source_text, target_text in [
        ("exercises", normalized_exercise_source, exercise_target_text),
        ("public_answers", answer_source_text, answer_target_text),
    ]:
        control_counts[role] = {}
        for token in ["{", "}", "$", "%", "&", "~"]:
            source_count = source_text.count(token)
            target_count = target_text.count(token)
            if source_count != target_count:
                raise AssertionError(f"{role} protected control-token drift: {token}")
            control_counts[role][token] = {
                "source": source_count,
                "target": target_count,
            }

    exercise_ids = [
        int(value) for value in re.findall(r"(?m)^% (\d+)\s*$", exercise_target_text)
    ]
    public_answer_ids = [
        int(value) for value in re.findall(r"(?m)^% (\d+)\s*$", answer_target_text)
    ]
    if exercise_ids != EXERCISE_IDS or exercise_target_text.count("\\eoce{") != 14:
        raise AssertionError("complete exercise-ID/macro closure failed")
    if public_answer_ids != PUBLIC_ANSWER_IDS or answer_target_text.count("\\eocesol{") != 7:
        raise AssertionError("public odd-answer ID/macro closure failed")

    unchanged_visible: dict[str, list[int]] = {"exercises": [], "public_answers": []}
    for role, source_lines, target_lines, first_line in [
        ("exercises", exercise_source_lines, exercise_target_lines, 1),
        ("public_answers", answer_source_lines, answer_target_lines, ANSWER_FIRST_LINE),
    ]:
        unchanged_visible[role] = [
            first_line + offset
            for offset, (source_line, target_line) in enumerate(zip(source_lines, target_lines))
            if source_line == target_line and line_has_visible_prose(source_line)
        ]
        if unchanged_visible[role]:
            raise AssertionError(
                f"unchanged learner-visible English in {role}: {unchanged_visible[role]}"
            )

    combined_target_active = active_text(exercise_target_lines + answer_target_lines)
    combined_source_active = active_text(exercise_source_lines + answer_source_lines)
    target_visible = visible_for_language_scan(combined_target_active)
    source_visible = visible_for_language_scan(combined_source_active)
    residual_patterns = [
        pattern
        for pattern in RESIDUAL_ENGLISH_PATTERNS
        if re.search(pattern, target_visible, flags=re.IGNORECASE)
    ]
    if residual_patterns:
        raise AssertionError(f"learner-visible residual English patterns: {residual_patterns}")
    four_gram_residue = source_four_gram_residue(source_visible, target_visible)
    if four_gram_residue:
        raise AssertionError(f"unchanged four-word source phrases: {four_gram_residue}")
    missing_anchors = [anchor for anchor in INDONESIAN_ANCHORS if anchor not in combined_target_active]
    if missing_anchors:
        raise AssertionError(f"missing Indonesian terminology anchors: {missing_anchors}")

    repairs = [
        {
            "source_lines": "30",
            "source_issue": "agreement errors and reversed center-peak ordering in alt text",
            "target_evidence": exercise_target_lines[29],
            "assertion": (
                "garis utuh dan memiliki puncak tengah paling tinggi dan tajam" in exercise_target_lines[29]
                and "garis titik-titik dan memiliki puncak tengah paling rendah dan lebar" in exercise_target_lines[29]
                and "ekornya paling tebal dan masih tampak melampaui -4 dan 4" in exercise_target_lines[29]
            ),
        },
        {
            "source_lines": "92-96",
            "source_issue": "unbalanced source quotation marks",
            "target_evidence": exercise_target_lines[93],
            "assertion": exercise_target_lines[93] == "``kota yang tidak pernah tidur''.",
        },
        {
            "source_lines": "139-147",
            "source_issue": "three-column declaration for two-cell rows",
            "target_evidence": exercise_target_lines[138],
            "assertion": exercise_target_lines[138] == "\\begin{tabular}{l|r}",
        },
        {
            "source_lines": "189-191",
            "source_issue": "critical-value notation switches from \\star to plain *",
            "target_evidence": " | ".join(exercise_target_lines[188:191]),
            "assertion": (
                "^{*}" not in "\n".join(exercise_target_lines[188:191])
                and "\n".join(exercise_target_lines[188:191]).count("\\star") == 6
            ),
        },
    ]
    if not all(item["assertion"] for item in repairs):
        raise AssertionError("approved derivative-repair assertion failed")
    for item in repairs:
        del item["assertion"]

    o001 = json.loads(O001.read_text("utf-8"))
    if o001["$schema"] != "interlanguage.r011-b026-o001-mastery-gaps/v1":
        raise AssertionError("O001 schema drift")
    if o001["boundary_id"] != "R011-B026":
        raise AssertionError("O001 boundary drift")
    if o001["authority"]["commit"] != COMMIT:
        raise AssertionError("O001 pinned authority drift")
    if o001["public_answers_present"] != PUBLIC_ANSWER_IDS:
        raise AssertionError("O001 public-answer complement drift")
    if o001["o001_gap_ids"] != O001_GAP_IDS:
        raise AssertionError("O001 even-gap closure drift")
    if o001["restricted_solutions_accessed_or_invented"] is not False:
        raise AssertionError("O001 restricted-solution guard drift")
    if len(o001["records"]) != 7:
        raise AssertionError("O001 record-count drift")
    for record, gap_id in zip(o001["records"], O001_GAP_IDS):
        expected = {
            "stable_key": f"r011/unit/o001-gap/7.{gap_id}",
            "chapter_exercise_id": gap_id,
            "exercise_label": O001_LABEL_BY_ID[gap_id],
            "answer_availability": "no_public_answer_upstream",
            "gap_reason": "no_public_answer_in_frozen_upstream_answer_slice",
            "authoring_mode": "independent_original_required",
            "translation_state": "queued",
            "source_solution_used": False,
            "restricted_solution_accessed_or_invented": False,
            "target_answer_path": None,
        }
        if record != expected:
            raise AssertionError(f"O001 record drift for exercise {gap_id}")

    receipt: dict[str, object] = {
        "$schema": "interlanguage.r011-translation-qa/v1",
        "boundary_id": "R011-B026",
        "part": "exercises-public-answers-and-o001",
        "status": "PASS_COMPLETE_NATURAL_ID_ID_EXERCISE_ANSWER_CLOSURE_STRUCTURE_MATH_REPAIRS_AND_RESIDUAL_ENGLISH_QA",
        "provenance": {
            "production_model": "OpenAI Codex gpt-5.6-sol, Ultra",
            "role": "independent bounded id-ID exercise/public-answer audit and deterministic QA",
        },
        "blueprint": identity(BLUEPRINT),
        "authority": {
            "repository": "https://github.com/OpenIntroStat/openintro-statistics",
            "commit": COMMIT,
            "tree": "d61cc601e7d97759ce805900520f784d02a0489e",
            "exercise_source": identity(EXERCISE_SOURCE),
            "public_answer_source_file": identity(ANSWER_SOURCE),
            "public_answer_source_slice": {
                "first_line": ANSWER_FIRST_LINE,
                "last_line": ANSWER_LAST_LINE,
                "logical_lines": len(answer_source_lines_b),
                "bytes": len(answer_source_slice),
                "sha256": sha256(answer_source_slice),
            },
        },
        "targets": {
            "exercises": {
                **identity(EXERCISE_TARGET),
                "locale": "id-ID",
                "logical_lines": len(exercise_target_lines_b),
                "source_mapping": "authority lines 1-280 map one-to-one to target lines 1-280",
            },
            "public_answers": {
                **identity(ANSWER_TARGET),
                "locale": "id-ID",
                "logical_lines": len(answer_target_lines_b),
                "source_mapping": "authority lines 1623-1721 map one-to-one to target lines 1-99",
            },
            "o001_gap_ledger": identity(O001),
        },
        "closure": {
            "exercise_ids": exercise_ids,
            "exercise_labels": EXERCISE_LABELS,
            "public_answer_ids": public_answer_ids,
            "o001_even_gap_ids": O001_GAP_IDS,
            "restricted_solution_material_included": False,
            "restricted_solution_material_accessed_or_invented_per_staged_scope_guard": False,
        },
        "qa": {
            "exact_line_mapping": True,
            "blank_line_topology_exact": blank_topology,
            "comment_source_witness_lines_exact": True,
            "comment_line_numbers": comment_lines,
            "command_sequence_exact_after_approved_notation_normalization": True,
            "environment_sequence_exact": True,
            "mathematics_exact_after_approved_notation_normalization": True,
            "labels_refs_citations_asset_bindings_widths_and_numerics_exact": True,
            "layout_exact_except_approved_two_column_table_repair": True,
            "control_token_counts": control_counts,
            "unchanged_learner_visible_source_lines": unchanged_visible,
            "residual_english_patterns_checked": RESIDUAL_ENGLISH_PATTERNS,
            "residual_english_pattern_matches": residual_patterns,
            "unchanged_source_four_word_phrases": four_gram_residue,
            "indonesian_terminology_anchors": INDONESIAN_ANCHORS,
            "approved_repairs": repairs,
            "unrecorded_semantic_repairs_applied": False,
        },
        "next_integration_action": (
            "Admit these exact staged exercise/public-answer/O001 bytes with the completed "
            "B026 main-section translation and localized assets; do not add restricted solutions."
        ),
        "scope_guards": {
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
    args = parser.parse_args()

    first = canonical_bytes(build_receipt())
    second = canonical_bytes(build_receipt())
    if first != second:
        raise AssertionError("in-process deterministic receipt replay mismatch")

    if args.write:
        RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        RECEIPT.write_bytes(first)
    elif not RECEIPT.exists() or RECEIPT.read_bytes() != first:
        raise AssertionError("on-disk B026 exercise/answer QA receipt differs from replay")

    result = {
        "status": "PASS_EXACT_REPLAY_R011_B026_EXERCISES_ANSWERS",
        "mode": "write" if args.write else "verify",
        "exercise_ids": EXERCISE_IDS,
        "public_answer_ids": PUBLIC_ANSWER_IDS,
        "o001_gap_ids": O001_GAP_IDS,
        "targets": [identity(EXERCISE_TARGET), identity(ANSWER_TARGET), identity(O001)],
        "receipt": {
            "path": RECEIPT.relative_to(LANE).as_posix(),
            "bytes": len(first),
            "sha256": sha256(first),
            "on_disk_exact": RECEIPT.exists() and RECEIPT.read_bytes() == first,
        },
        "approved_repairs": ["30", "92-96", "139-147", "189-191"],
        "residual_english_matches": [],
        "scope": "three staged translation artifacts plus one deterministic QA receipt only",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
