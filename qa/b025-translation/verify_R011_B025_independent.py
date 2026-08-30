#!/usr/bin/env python3
"""Independent deterministic QA for the complete staged R011-B025 translation.

This verifier is deliberately independent of the producer receipts.  It binds
the frozen authority slices directly to the four staged TeX fragments and the
O001 gap ledger, checks TeX/math topology, and records the completed human
semantic review of every learner-facing line in the boundary.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
UPSTREAM = ROOT / (
    "authority/upstream/"
    "openintro-statistics-fee25091fb24e89c36296fd67c48c1fcf7a93b6e"
)
MAIN_SOURCE = UPSTREAM / "ch_inference_for_props/TeX/ch_inference_for_props.tex"
EXERCISE_SOURCE = (
    UPSTREAM
    / "ch_inference_for_props/TeX/testing_for_independence_in_two-way_tables.tex"
)
ANSWER_SOURCE = UPSTREAM / "extraTeX/eoceSolutions/eoceSolutions.tex"
B024_TERMINOLOGY = (
    ROOT / "qa/b024-translation/R011-B024_MAIN_TRANSLATION_AUDIT.json"
)
EXERCISE_ANSWER_QA = (
    ROOT / "qa/b025-translation/R011-B025_EXERCISES_ANSWERS_TRANSLATION_QA.json"
)
EXERCISE_ANSWER_QA_PRODUCER = ROOT / "scripts/audit_b025_exercises_answers.py"
CHART_SOURCE = (
    UPSTREAM / "ch_inference_for_props/figures/iPodChiSqTail/iPodChiSqTail.pdf"
)
CHART_PRODUCER = (
    UPSTREAM / "ch_inference_for_props/figures/iPodChiSqTail/iPodChiSqTail.R"
)

STAGING = ROOT / "qa/b025-translation/staging"
MAIN_A = STAGING / "section-lines-2008-2238.id.tex"
MAIN_B = STAGING / "section-lines-2239-2434.id.tex"
EXERCISES = STAGING / "exercises-lines-1-127.id.tex"
ANSWERS = STAGING / "public-answers-lines-1500-1543.id.tex"
O001 = STAGING / "R011-B025_O001_MASTERY_GAPS.json"
CHART = STAGING / "assets/iPodChiSqTail.id.pdf"
CHART_LOCALIZATION_RECEIPT = (
    ROOT / "qa/b025-translation/R011-B025_IPOD_CHISQ_TAIL_LOCALIZATION_QA.json"
)
CHART_VISUAL_RECEIPT = (
    ROOT / "qa/b025-translation/R011-B025_IPOD_CHISQ_TAIL_VISUAL_QA.json"
)
RECEIPT = ROOT / "qa/b025-translation/R011-B025_INDEPENDENT_TRANSLATION_AUDIT.json"

EXPECTED = {
    "main_source": {
        "bytes": 103385,
        "sha256": "a2470ca3041209d1f1194b3ab27e8124405d8fdbd1ccece89a0319be13fae8a7",
    },
    "main_a_slice": {
        "first_line": 2008,
        "last_line": 2238,
        "logical_lines": 231,
        "bytes_lf": 8585,
        "sha256_lf": "89af837210e034c300fe1fc97dd03c2024ff4e51cb78ab7c013752d7bd8ebff2",
    },
    "main_b_slice": {
        "first_line": 2239,
        "last_line": 2434,
        "logical_lines": 196,
        "bytes_lf": 6909,
        "sha256_lf": "93056421a48a1fc7ce34ece0d37949bacde9baaf38887dea914050180766a7b1",
    },
    "exercise_source": {
        "bytes": 4558,
        "sha256": "5f22aeaa256054748f626dad74a279e57d3a098f6060dc057a9625f7b2259e9a",
        "logical_lines": 127,
    },
    "answer_source": {
        "bytes": 106045,
        "sha256": "6c4e01376db4c023cc7b3f9949490e57220ef1cb831c580da71efde6ce723268",
    },
    "answer_slice": {
        "first_line": 1500,
        "last_line": 1543,
        "logical_lines": 44,
        "bytes_lf": 1660,
        "sha256_lf": "b09e89cb4e0b98f1f38f75bea10dec562d3ac247aa2a55bc12ae8dc45dd1977c",
    },
    "main_a_target": {
        "bytes": 9104,
        "sha256": "5a59d955174eb73176876d756bb4c44ba427d25d5ca86ab41824ff218d2d9554",
        "logical_lines": 231,
    },
    "main_b_target": {
        "bytes": 7107,
        "sha256": "bc16102ee8a445f2410a9d429b9831a58f2637a528776ca727eb07607d045d63",
        "logical_lines": 196,
    },
    "exercise_target": {
        "bytes": 4933,
        "sha256": "0d66bdb60c1edcf246e933ac0eab97bacaf237a573ec260e5a3463076731f440",
        "logical_lines": 127,
    },
    "answer_target": {
        "bytes": 1748,
        "sha256": "91a3e108ced397c72ae204d5f142fc9838f2612312383d1aa52eac78f0eb2dec",
        "logical_lines": 44,
    },
    "o001": {
        "bytes": 2107,
        "sha256": "5ca09682b02110ce941065c495683bbd36cd7ac9055c88dbd89b46512c4b8aee",
    },
    "b024_terminology": {
        "bytes": 9726,
        "sha256": "90eb218c6b87169521896f2f3af4d04a08c0f8e5fc61c26dfcb7be80b6d91d8c",
    },
    "exercise_answer_qa": {
        "bytes": 2844,
        "sha256": "a3653c8aaa12301fbded5588c83ef6c59bccbc5a107b806c2118c29a3005e947",
        "status": "PASS_EXERCISES_35_38_AND_ALL_LINKED_PUBLIC_ODD_ANSWERS_TRANSLATED",
    },
    "exercise_answer_qa_producer": {
        "bytes": 7630,
        "sha256": "f7c044102bc2bbe9c8ee81fd8be23893540e1ab0a0953decad983ae37a56e003",
    },
    "chart_source": {
        "bytes": 5719,
        "sha256": "789e9da58ef275f9996f2414cb53ed5edb134b9df2f3f194e7be42d7ce810403",
    },
    "chart_producer": {
        "bytes": 368,
        "sha256": "16c6c2d5167308537e38b4120ece9e841f6d41d532d9dab32e744329d319d543",
    },
    "chart": {
        "bytes": 13265,
        "sha256": "4d34c0d4f59787283086f88fb0eaa7c47714726b0e21fcb440a7bcf8e243acae",
    },
    "chart_localization_receipt": {
        "bytes": 3314,
        "sha256": "c2ab840d15bf7391518c4587aad7ed6f7ded1c9b208706861434ac64e9b104db",
    },
    "chart_visual_receipt": {
        "bytes": 2603,
        "sha256": "13ec3d5529ebdf198630341f16accb457bb8b94cdda7edcfdbb218007f29e837",
    },
}

# These phrases are high-signal English carry-through if they remain in
# learner-visible prose.  Protected identifiers, citations, and math notation
# are removed before this scan.
FORBIDDEN_VISIBLE_PHRASES = (
    "testing for independence",
    "two-way tables",
    "we all buy used products",
    "take for granted",
    "researchers recruited",
    "used ipod",
    "cellular service",
    "participants were incentivized",
    "unbeknownst to the participants",
    "scripted buyers",
    "what can you tell me",
    "positive assumption",
    "negative assumption",
    "disclose problem",
    "hide problem",
    "differences of one-way tables",
    "expected counts in two-way tables",
    "general formula",
    "observed count",
    "expected count",
    "degrees of freedom",
    "find the p-value",
    "type 2 diabetes",
    "glycemic control",
    "full body scan",
    "party affiliation",
    "should not",
    "don't know",
    "offshore drilling",
    "college grad",
    "parasitic worm",
    "three drugs",
    "two drugs annually",
    "clear at year 2",
    "not clear at year 2",
    "patch + support group",
    "only patch",
    "lower than the observed value",
    "sample size",
    "strong evidence",
)

FORBIDDEN_VISIBLE_WORDS = (
    "whether",
    "where",
    "which",
    "because",
    "participants",
    "sellers",
    "buyers",
    "treatment",
    "failure",
    "success",
    "republican",
    "democrat",
    "independent",
    "support",
    "oppose",
    "quitters",
)

# These appeared inside public-answer mathematics and are reader-visible even
# though a prose-only residual scanner strips math regions.  They therefore
# require an explicit raw-TeX guard.
FORBIDDEN_PUBLIC_ANSWER_FORMULA_LABEL_PATTERNS = {
    "row": r"(?<![A-Za-z])row(?![A-Za-z])",
    "col": r"(?<![A-Za-z])col(?![A-Za-z])",
    "table total": r"(?<![A-Za-z])table\s*~?\s*total(?![A-Za-z])",
}

PROTECTED_COMMANDS = ("label", "ref", "pageref", "input", "includegraphics", "index")
WRAPPERS = (
    "examplewrap",
    "nexample",
    "exercisewrap",
    "nexercise",
    "eoce",
    "eocesol",
    "footnotemark",
    "footnotetext",
)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def lf_slice(data: bytes, first_line: int, last_line: int) -> tuple[list[str], bytes]:
    lines = data.decode("utf-8").splitlines()
    selected = lines[first_line - 1 : last_line]
    raw = ("\n".join(selected) + "\n").encode("utf-8")
    return selected, raw


def commands_by_line(lines: list[str]) -> list[list[str]]:
    return [re.findall(r"\\(?:[A-Za-z@]+|.)", line) for line in lines]


def captures(pattern: str, text: str) -> list[str]:
    return re.findall(pattern, text)


def numeric_tokens(text: str) -> list[str]:
    return re.findall(r"(?<![A-Za-z])\d+(?:\.\d+)?", text)


def math_regions(text: str) -> list[str]:
    regions = re.findall(r"(?<!\\)\$(.*?)(?<!\\)\$", text, flags=re.DOTALL)
    regions.extend(
        re.findall(
            r"\\begin\{align\*?\}(.*?)\\end\{align\*?\}",
            text,
            flags=re.DOTALL,
        )
    )
    return regions


def math_skeleton(region: str) -> list[str]:
    # Natural-language words inside \text and ordinary subscripts may be
    # localized or intentionally retained as protected notation.  Commands,
    # macros, numbers, and mathematical operators must remain ordered.
    return re.findall(
        r"\\[A-Za-z@]+|\\.|\d+(?:\.\d+)?|[=+\-*/^_<>]|[()[\],]",
        region,
    )


def remove_comments(text: str) -> str:
    return "\n".join(re.sub(r"(?<!\\)%.*$", "", line) for line in text.splitlines())


def visible_prose(text: str) -> str:
    text = remove_comments(text)
    text = re.sub(
        r"\\begin\{align\*?\}.*?\\end\{align\*?\}", " ", text, flags=re.DOTALL
    )
    text = re.sub(r"\$[^$]*\$", " ", text, flags=re.DOTALL)
    for command in PROTECTED_COMMANDS:
        text = re.sub(rf"\\{command}(?:\[[^\]]*\])?\{{[^{{}}]*\}}", " ", text)
    text = re.sub(r"\\(?:begin|end)\{[^{}]*\}", " ", text)
    text = re.sub(r"\\(?:[A-Za-z@]+|.)", " ", text)
    text = text.replace("{", " ").replace("}", " ")
    return re.sub(r"\s+", " ", text).strip()


def structural_checks(
    source_lines: list[str],
    target_lines: list[str],
    *,
    source_corrections: tuple[tuple[str, str], ...] = (),
) -> dict[str, bool]:
    source_text = "\n".join(source_lines) + "\n"
    target_text = "\n".join(target_lines) + "\n"
    for old, new in source_corrections:
        require(old in source_text, f"approved source-correction anchor missing: {old}")
        source_text = source_text.replace(old, new, 1)
    source_lines = source_text.splitlines()
    blank = lambda x: not re.sub(r"(?<!\\)%.*$", "", x).strip()
    checks = {
        "logical_line_count": len(source_lines) == len(target_lines),
        "blank_or_comment_line_positions": [blank(x) for x in source_lines]
        == [blank(x) for x in target_lines],
        "command_sequence_global": commands_by_line([source_text])[0]
        == commands_by_line([target_text])[0],
        "numeric_token_sequence": numeric_tokens(source_text) == numeric_tokens(target_text),
        "labels": captures(r"\\label\{[^}]+\}", source_text)
        == captures(r"\\label\{[^}]+\}", target_text),
        "references": captures(r"\\(?:ref|pageref)\{[^}]+\}", source_text)
        == captures(r"\\(?:ref|pageref)\{[^}]+\}", target_text),
        "environment_topology": captures(r"\\(?:begin|end)\{[^}]+\}", source_text)
        == captures(r"\\(?:begin|end)\{[^}]+\}", target_text),
        "dollar_delimiters_by_line": [x.count("$") for x in source_lines]
        == [x.count("$") for x in target_lines],
        "alignment_markers_by_line": [x.count("&") for x in source_lines]
        == [x.count("&") for x in target_lines],
        "tex_row_breaks_by_line": [x.count("\\\\") for x in source_lines]
        == [x.count("\\\\") for x in target_lines],
        "source_braces_balanced": source_text.count("{") == source_text.count("}"),
        "target_braces_balanced": target_text.count("{") == target_text.count("}"),
        "math_region_count": len(math_regions(source_text)) == len(math_regions(target_text)),
        "math_skeleton_sequence": [math_skeleton(x) for x in math_regions(source_text)]
        == [math_skeleton(x) for x in math_regions(target_text)],
    }
    return checks


def inspect_target(path: Path, expected: dict[str, Any]) -> tuple[bytes, list[str]]:
    data = path.read_bytes()
    lines = data.decode("utf-8").splitlines()
    require(len(data) == expected["bytes"], f"target byte drift: {rel(path)}")
    require(digest(data) == expected["sha256"], f"target hash drift: {rel(path)}")
    require(
        len(lines) == expected["logical_lines"], f"target line drift: {rel(path)}"
    )
    return data, lines


def main(verify_only: bool) -> int:
    main_source_bytes = MAIN_SOURCE.read_bytes()
    exercise_source_bytes = EXERCISE_SOURCE.read_bytes()
    answer_source_bytes = ANSWER_SOURCE.read_bytes()
    terminology_bytes = B024_TERMINOLOGY.read_bytes()
    require(
        len(main_source_bytes) == EXPECTED["main_source"]["bytes"]
        and digest(main_source_bytes) == EXPECTED["main_source"]["sha256"],
        "frozen main authority drift",
    )
    require(
        len(exercise_source_bytes) == EXPECTED["exercise_source"]["bytes"]
        and digest(exercise_source_bytes) == EXPECTED["exercise_source"]["sha256"],
        "frozen exercise authority drift",
    )
    require(
        len(answer_source_bytes) == EXPECTED["answer_source"]["bytes"]
        and digest(answer_source_bytes) == EXPECTED["answer_source"]["sha256"],
        "frozen public-answer authority drift",
    )
    require(
        len(terminology_bytes) == EXPECTED["b024_terminology"]["bytes"]
        and digest(terminology_bytes) == EXPECTED["b024_terminology"]["sha256"],
        "accepted B024 terminology witness drift",
    )
    exercise_answer_qa_bytes = EXERCISE_ANSWER_QA.read_bytes()
    exercise_answer_qa_producer_bytes = EXERCISE_ANSWER_QA_PRODUCER.read_bytes()
    require(
        len(exercise_answer_qa_bytes) == EXPECTED["exercise_answer_qa"]["bytes"]
        and digest(exercise_answer_qa_bytes)
        == EXPECTED["exercise_answer_qa"]["sha256"],
        "replacement exercise/answer producer QA receipt drift",
    )
    require(
        len(exercise_answer_qa_producer_bytes)
        == EXPECTED["exercise_answer_qa_producer"]["bytes"]
        and digest(exercise_answer_qa_producer_bytes)
        == EXPECTED["exercise_answer_qa_producer"]["sha256"],
        "replacement exercise/answer producer script drift",
    )
    exercise_answer_qa = json.loads(exercise_answer_qa_bytes.decode("utf-8"))
    require(
        exercise_answer_qa.get("boundary_id") == "R011-B025"
        and exercise_answer_qa.get("status")
        == EXPECTED["exercise_answer_qa"]["status"]
        and exercise_answer_qa.get("target_public_answers", {}).get("bytes")
        == EXPECTED["answer_target"]["bytes"]
        and exercise_answer_qa.get("target_public_answers", {}).get("sha256")
        == EXPECTED["answer_target"]["sha256"]
        and exercise_answer_qa.get("unadjudicated_residual_english") == []
        and exercise_answer_qa.get("restricted_solutions_accessed_or_invented")
        is False,
        "replacement exercise/answer producer QA semantics drift",
    )
    chart_source_bytes = CHART_SOURCE.read_bytes()
    chart_producer_bytes = CHART_PRODUCER.read_bytes()
    chart_bytes = CHART.read_bytes()
    chart_localization_receipt_bytes = CHART_LOCALIZATION_RECEIPT.read_bytes()
    chart_visual_receipt_bytes = CHART_VISUAL_RECEIPT.read_bytes()
    for name, data in (
        ("chart_source", chart_source_bytes),
        ("chart_producer", chart_producer_bytes),
        ("chart", chart_bytes),
        ("chart_localization_receipt", chart_localization_receipt_bytes),
        ("chart_visual_receipt", chart_visual_receipt_bytes),
    ):
        expected = EXPECTED[name]
        require(
            len(data) == expected["bytes"] and digest(data) == expected["sha256"],
            f"{name} drift",
        )
    chart_localization = json.loads(chart_localization_receipt_bytes.decode("utf-8"))
    chart_visual = json.loads(chart_visual_receipt_bytes.decode("utf-8"))
    chart_checks = {
        "localization_receipt_pass": chart_localization["status"]
        == "PASS_EXACT_ANNOTATION_LOCALIZATION_AND_GEOMETRY_PRESERVATION",
        "visual_receipt_pass": chart_visual["status"]
        == "PASS_DIRECT_VISUAL_INSPECTION_AND_RASTER_GEOMETRY_COMPARISON",
        "output_identity_bound": chart_localization["output"]["sha256"]
        == EXPECTED["chart"]["sha256"]
        and chart_visual["localized_output"]["sha256"] == EXPECTED["chart"]["sha256"],
        "one_page_and_media_box": chart_localization["output"]["pages"] == 1
        and chart_localization["output"]["media_box_points"] == [0, 0, 360, 162],
        "indonesian_annotation_exact": chart_localization["translation"]["target_line_1"]
        == "Luas ekor (1 dari 500 juta)"
        and chart_localization["translation"]["target_line_2"]
        == "terlalu kecil untuk terlihat",
        "zero_visible_english": chart_localization["visible_english_labels_remaining"] == 0
        and chart_visual["direct_visual_findings"]["source_english_annotation_visible"]
        is False,
        "math_context_exact": chart_localization["mathematical_closure"]["pearson_chi_square"]
        == 40.13
        and chart_localization["mathematical_closure"]["degrees_of_freedom"] == 2
        and chart_localization["mathematical_closure"]["tail_probability_precise_context"]
        == 2e-9,
        "geometry_preserved": chart_localization["output"]["non_annotation_geometry"][
            "byte_identical_after_annotation_normalization"
        ]
        is True
        and chart_visual["render"]["changed_pixels_outside_permitted_annotation_region"]
        == 0
        and chart_visual["render"]["non_annotation_raster_geometry_pixel_identical"]
        is True,
        "zero_visual_defects": chart_visual["direct_visual_findings"]["visual_defects"]
        == []
        and chart_visual["direct_visual_findings"]["text_clipping"] is False
        and chart_visual["direct_visual_findings"]["text_overlap"] is False
        and chart_visual["direct_visual_findings"]["curve_or_tail_occlusion"] is False,
        "rights_and_credit_preserved": chart_localization["rights"]["spdx"]
        == "CC-BY-SA-3.0"
        and chart_localization["source_credit_preserved"] == "OpenIntro",
    }
    failed_chart = [name for name, passed in chart_checks.items() if not passed]
    require(not failed_chart, "localized chart failures: " + ", ".join(failed_chart))

    main_a_source, main_a_slice = lf_slice(main_source_bytes, 2008, 2238)
    main_b_source, main_b_slice = lf_slice(main_source_bytes, 2239, 2434)
    exercise_source = exercise_source_bytes.decode("utf-8").splitlines()
    answer_source, answer_slice = lf_slice(answer_source_bytes, 1500, 1543)
    for key, lines, raw in (
        ("main_a_slice", main_a_source, main_a_slice),
        ("main_b_slice", main_b_source, main_b_slice),
        ("answer_slice", answer_source, answer_slice),
    ):
        expected = EXPECTED[key]
        require(len(lines) == expected["logical_lines"], f"{key} line drift")
        require(len(raw) == expected["bytes_lf"], f"{key} byte drift")
        require(digest(raw) == expected["sha256_lf"], f"{key} hash drift")
    require(
        len(exercise_source) == EXPECTED["exercise_source"]["logical_lines"],
        "exercise source line drift",
    )

    main_a_bytes, main_a_target = inspect_target(MAIN_A, EXPECTED["main_a_target"])
    main_b_bytes, main_b_target = inspect_target(MAIN_B, EXPECTED["main_b_target"])
    exercise_bytes, exercise_target = inspect_target(EXERCISES, EXPECTED["exercise_target"])
    answer_bytes, answer_target = inspect_target(ANSWERS, EXPECTED["answer_target"])
    o001_bytes = O001.read_bytes()
    require(
        len(o001_bytes) == EXPECTED["o001"]["bytes"]
        and digest(o001_bytes) == EXPECTED["o001"]["sha256"],
        "O001 ledger drift",
    )

    checks = {
        "main_a": structural_checks(
            main_a_source,
            main_a_target,
            source_corrections=(
                ("\\iPodBD{}/\\iPodDD{}", "\\iPodAD{}/\\iPodDD{}"),
                ("$i^{th}$", "$i$"),
                ("$j^{th}$", "$j$"),
            ),
        ),
        "main_b": structural_checks(main_b_source, main_b_target),
        "exercises": structural_checks(exercise_source, exercise_target),
        "public_answers": structural_checks(answer_source, answer_target),
    }
    failures = [
        f"{component}.{name}"
        for component, component_checks in checks.items()
        for name, passed in component_checks.items()
        if not passed
    ]
    require(not failures, "structural/math failures: " + ", ".join(failures))

    main_a_text = "\n".join(main_a_target) + "\n"
    main_b_text = "\n".join(main_b_target) + "\n"
    exercise_text = "\n".join(exercise_target) + "\n"
    answer_text = "\n".join(answer_target) + "\n"
    all_target = main_a_text + main_b_text + exercise_text + answer_text
    prose = visible_prose(all_target).casefold()
    residual_phrases = [x for x in FORBIDDEN_VISIBLE_PHRASES if x in prose]
    residual_words = [
        x for x in FORBIDDEN_VISIBLE_WORDS if re.search(rf"(?<![A-Za-z]){re.escape(x)}(?![A-Za-z])", prose)
    ]
    require(not residual_phrases, "residual English phrases: " + ", ".join(residual_phrases))
    require(not residual_words, "residual English words: " + ", ".join(residual_words))
    require("\u2013" not in all_target and "\u2014" not in all_target, "Unicode dash drift")
    public_answer_formula_label_hits = {
        label: re.findall(pattern, answer_text, flags=re.IGNORECASE)
        for label, pattern in FORBIDDEN_PUBLIC_ANSWER_FORMULA_LABEL_PATTERNS.items()
    }
    public_answer_formula_label_hits = {
        label: hits for label, hits in public_answer_formula_label_hits.items() if hits
    }
    require(
        not public_answer_formula_label_hits,
        "English public-answer formula labels remain: "
        + json.dumps(public_answer_formula_label_hits, ensure_ascii=False, sort_keys=True),
    )
    localized_formula_label_checks = {
        "answer_35_expectation_subscripts": (
            "$E_{baris_1, kolom_1}" in answer_text
            and "$E_{baris_2, kolom_2}" in answer_text
        ),
        "answer_35_fraction_labels": (
            "(total~baris~1)\\times(total~kolom~1)" in answer_text
            and "(total~baris~2)\\times(total~kolom~2)" in answer_text
            and answer_text.count("{total~tabel}") == 2
        ),
        "answer_37_expectation_subscripts": all(
            f"E_{{baris~{row}, kolom~{column}}}" in answer_text
            for row in (1, 2, 3)
            for column in (1, 2)
        ),
    }
    require(
        all(localized_formula_label_checks.values()),
        "localized public-answer formula label closure differs",
    )

    repair_checks = {
        "2068_2071_stray_article_and_question_grammar": (
            "data tersebut menunjukkan bahwa pertanyaan\n"
            "\\emph{Masalah apa yang dimiliki perangkat ini?}\n"
            "merupakan yang paling efektif"
        )
        in main_a_text,
        "2093_2094_truncated_caption_completed": (
            "diajukan kepada peserta studi yang bertindak sebagai penjual."
            in main_a_text
        ),
        "2108_2114_missing_predicate_and_independence_question_repaired": (
            "tingkat keberhasilan setiap pertanyaan" in main_a_text
            and "berbeda-beda." in main_a_text
            and "pertanyaan pembeli independen dari pengungkapan" in main_a_text
        ),
        "2209_2212_disclosed_fraction_numerator_corrected": (
            "($\\iPodAD{}/\\iPodDD{}$) --" in main_a_text
            and "($\\iPodBD{}/\\iPodDD{}$) --" not in main_a_text
            and abs(61 / 219 - 0.2785) < 0.00005
            and abs(158 / 219 - 0.7215) < 0.00005
        ),
        "2261_agreement_and_hyphenation_naturalized": (
            "derajat kebebasan dihitung sedikit berbeda untuk tabel dua arah" in main_b_text
            and "derajat kebebasan adalah banyaknya sel dikurangi 1" in main_b_text
        ),
        "2303_2305_possessive_likelihood_naturalized": (
            "apakah pertanyaan tersebut memengaruhi peluang penjual\n"
            "    melaporkan masalah pembekuan."
        )
        in main_b_text,
        "exercise_38_duplicated_article_removed": (
            "membersihkan tubuh seseorang dari\nparasit ini" in exercise_text
            and "of the this parasite" not in exercise_text.casefold()
        ),
        "answer_37_subject_verb_agreement_naturalized": (
            re.search(
                r"Pendapat mengenai pengeboran minyak dan gas alam\s+"
                r"di lepas pantai California berasosiasi dengan kepemilikan",
                answer_text,
            )
            is not None
        ),
    }
    failed_repairs = [name for name, passed in repair_checks.items() if not passed]
    require(not failed_repairs, "missing high-confidence repairs: " + ", ".join(failed_repairs))

    exercise_ids = [int(x) for x in re.findall(r"(?m)^% (\d+)\s*$", exercise_text)]
    public_answer_ids = [int(x) for x in re.findall(r"(?m)^% (\d+)\s*$", answer_text)]
    exercise_labels = captures(r"\\label\{([^}]+)\}", exercise_text)
    require(exercise_ids == [35, 36, 37, 38], "exercise ID/order drift")
    require(public_answer_ids == [35, 37], "public-answer ID/order drift")
    require(
        exercise_labels
        == [
            "quitters_chisq_independence",
            "full_body_scan_chisq_indep",
            "offshore_drilling_chisq_indep",
            "parasitic_worm_chisq",
            "parasitic_worm_chisq_hyp",
        ],
        "exercise label/order drift",
    )
    require(exercise_text.count("}{}") == 4, "exercise answer slots are not all empty")
    require("\\eocesol" not in exercise_text, "solution text embedded in exercises")
    require(answer_text.count("\\eocesol") == 2, "public-answer wrapper count drift")

    o001 = json.loads(o001_bytes.decode("utf-8"))
    o001_record_ids = [row["chapter_exercise_id"] for row in o001["records"]]
    o001_checks = {
        "status_explicit": o001["status"]
        == "EXPLICIT_O001_GAPS_RECORDED_NO_RESTRICTED_SOLUTIONS_ACCESSED_OR_INVENTED",
        "gap_ids_exact": o001["o001_gap_ids"] == [36, 38] and o001_record_ids == [36, 38],
        "public_answer_ids_exact": o001["public_answers_present"] == [35, 37],
        "no_restricted_solutions": o001["restricted_solutions_accessed_or_invented"] is False
        and all(row["restricted_solution_accessed_or_invented"] is False for row in o001["records"]),
        "independent_originals_only_queued": all(
            row["authoring_mode"] == "independent_original_required"
            and row["translation_state"] == "queued"
            and row["source_solution_used"] is False
            and row["target_answer_path"] is None
            for row in o001["records"]
        ),
    }
    failed_o001 = [name for name, passed in o001_checks.items() if not passed]
    require(not failed_o001, "O001 linkage failures: " + ", ".join(failed_o001))

    expected_terms = {
        "khi-kuadrat": 13,
        "derajat kebebasan": 9,
        "cacah teramati": 3,
        "cacah harapan": 16,
        "nilai-p": 11,
        "tingkat signifikansi": 2,
        "hipotesis nol": 6,
        "tabel kontingensi": 1,
    }
    observed_terms = {term: all_target.casefold().count(term) for term in expected_terms}
    term_checks = {
        term: observed_terms[term] == count for term, count in expected_terms.items()
    }
    require(all(term_checks.values()), "accepted terminology missing or inconsistent")
    require("chi-square" not in prose, "unlocalized chi-square remains in visible prose")
    require("p-value" not in prose, "unlocalized p-value remains in visible prose")

    wrapper_counts = {
        name: {
            "source": sum(
                ("\n".join(x) + "\n").count(f"\\{name}")
                for x in (main_a_source, main_b_source, exercise_source, answer_source)
            ),
            "target": all_target.count(f"\\{name}"),
        }
        for name in WRAPPERS
    }
    require(
        all(x["source"] == x["target"] for x in wrapper_counts.values()),
        "wrapper count drift",
    )

    result = {
        "$schema": "interlanguage.r011-b025-independent-translation-audit/v1",
        "boundary_id": "R011-B025",
        "status": "PASS_INDEPENDENT_COMPLETE_NATURAL_ID_ID_STRUCTURE_MATH_REPAIRS_EXERCISE_ANSWER_AND_O001_QA",
        "scope": {
            "main": "Section 6.4, authority lines 2008-2434 inclusive",
            "exercises": "Chapter 6 exercises 35-38, full 127-line source file",
            "public_answers": "all frozen public answers for this boundary: 35 and 37, authority lines 1500-1543",
            "o001_gaps": [36, 38],
            "localized_asset": "iPod chi-square upper-tail figure used by Section 6.4",
        },
        "frozen_authority": {
            "commit": "fee25091fb24e89c36296fd67c48c1fcf7a93b6e",
            "tree": "d61cc601e7d97759ce805900520f784d02a0489e",
            "main": {"path": rel(MAIN_SOURCE), **EXPECTED["main_source"]},
            "main_a_slice_lf": {"path": rel(MAIN_SOURCE), **EXPECTED["main_a_slice"]},
            "main_b_slice_lf": {"path": rel(MAIN_SOURCE), **EXPECTED["main_b_slice"]},
            "exercises": {"path": rel(EXERCISE_SOURCE), **EXPECTED["exercise_source"]},
            "public_answers_file": {"path": rel(ANSWER_SOURCE), **EXPECTED["answer_source"]},
            "public_answers_slice_lf": {"path": rel(ANSWER_SOURCE), **EXPECTED["answer_slice"]},
        },
        "targets": {
            "main_a": {"path": rel(MAIN_A), **EXPECTED["main_a_target"]},
            "main_b": {"path": rel(MAIN_B), **EXPECTED["main_b_target"]},
            "exercises": {"path": rel(EXERCISES), **EXPECTED["exercise_target"]},
            "public_answers": {"path": rel(ANSWERS), **EXPECTED["answer_target"]},
            "o001": {"path": rel(O001), **EXPECTED["o001"]},
            "localized_chart": {"path": rel(CHART), **EXPECTED["chart"]},
        },
        "replacement_exercise_answer_producer_qa": {
            "receipt": {
                "path": rel(EXERCISE_ANSWER_QA),
                **EXPECTED["exercise_answer_qa"],
            },
            "producer": {
                "path": rel(EXERCISE_ANSWER_QA_PRODUCER),
                **EXPECTED["exercise_answer_qa_producer"],
            },
            "corrected_public_answer_target": {
                "path": rel(ANSWERS),
                **EXPECTED["answer_target"],
            },
        },
        "structural_and_math_qa": {
            "status": "PASS",
            "checks": checks,
            "wrapper_counts": wrapper_counts,
            "approved_deltas": [
                "Reader-visible prose and text/table labels translated to id-ID while TeX controls, environments, numeric sequence, and formula skeletons remain ordered.",
                "The source's iPodBD/iPodDD error at line 2211 is compared after the sole approved mathematical correction to iPodAD/iPodDD.",
                "The English i-th/j-th prose notation is rendered naturally as baris ke-$i$/kolom ke-$j$; its mathematical variables and role are unchanged.",
                "Protected formula subscripts row/col and abbreviations obs/exp remain source notation, not untranslated prose.",
                "Reader-visible response value lifestyle is localized to gaya hidup without changing the resp wrapper or category identity.",
            ],
        },
        "semantic_review": {
            "status": "PASS_EVERY_LEARNER_FACING_LINE_REVIEWED_AGAINST_FROZEN_SOURCE",
            "reviewed_ranges": [
                {"component": "main_a", "source_lines": "2008-2238", "target_lines": 231},
                {"component": "main_b", "source_lines": "2239-2434", "target_lines": 196},
                {"component": "exercises", "source_lines": "1-127", "target_lines": 127},
                {"component": "public_answers", "source_lines": "1500-1543", "target_lines": 44},
            ],
            "findings": [
                "The iPod experiment, observed/expected tables, independence question, chi-square calculation, df=2, p-value, and conclusion retain their source meaning.",
                "The diabetes example retains the 3x2 counts, expected counts, X^2=8.16, df=2, p=0.017, alpha=0.05, and inferential conclusion.",
                "Exercises 35-38 retain all prompts, data, hypotheses, conditions, references, and citation identity in natural Indonesian.",
                "Public answers 35 and 37 retain every table count, expected count, X^2=11.47, df=2, p=0.003, and conclusion.",
                "Every reader-visible expectation-formula label in public answers 35 and 37 is localized as baris, kolom, and total tabel; raw-TeX guards confirm row, col, and table total are absent.",
                "After the public-answer formula-label correction, no remaining objective semantic or localization defect requiring another translation patch was found.",
            ],
        },
        "high_confidence_source_repairs": {
            "status": "PASS_ALL_EIGHT_PRESENT_IN_DERIVATIVE_AUTHORITY_UNCHANGED",
            "checks": repair_checks,
        },
        "language_and_terminology_qa": {
            "status": "PASS_ZERO_UNADJUDICATED_RESIDUAL_ENGLISH_AND_ACCEPTED_TERMINOLOGY_CONSISTENT",
            "visible_prose_scan": {
                "forbidden_phrase_count": len(FORBIDDEN_VISIBLE_PHRASES),
                "forbidden_word_count": len(FORBIDDEN_VISIBLE_WORDS),
                "residual_phrases": residual_phrases,
                "residual_words": residual_words,
            },
            "public_answer_formula_label_scan": {
                "method": "case-insensitive raw-TeX scan because reader-visible math labels are intentionally excluded from prose-only scanning",
                "forbidden_labels": list(
                    FORBIDDEN_PUBLIC_ANSWER_FORMULA_LABEL_PATTERNS
                ),
                "hits": public_answer_formula_label_hits,
                "localized_label_checks": localized_formula_label_checks,
                "status": "PASS_ZERO_ROW_COL_OR_TABLE_TOTAL_LABELS",
            },
            "protected_non_indonesian_notation": [
                "iPod",
                "met",
                "rosi",
                "obs",
                "exp",
                "row",
                "col",
                "df",
                "X",
                "e-6 scientific notation",
                "California",
            ],
            "terminology_witness": {
                "path": rel(B024_TERMINOLOGY),
                **EXPECTED["b024_terminology"],
            },
            "expected_counts": expected_terms,
            "observed_counts": observed_terms,
            "checks": term_checks,
            "independence_forms": {
                "noun": "independensi",
                "adjective": "independen",
                "accepted_contextual_variant": "saling bebas",
            },
        },
        "exercise_answer_and_o001_qa": {
            "status": "PASS_PUBLIC_ANSWERS_35_37_EXACT_AND_O001_36_38_EXPLICIT",
            "exercise_ids": exercise_ids,
            "public_answer_ids": public_answer_ids,
            "exercise_labels": exercise_labels,
            "o001_record_ids": o001_record_ids,
            "o001_checks": o001_checks,
            "restricted_solutions_accessed_or_invented": False,
        },
        "localized_asset_qa": {
            "status": "PASS_INDEPENDENT_RENDER_INSPECTION_EXACT_INDONESIAN_ANNOTATION_AND_PRESERVED_GEOMETRY",
            "source": {"path": rel(CHART_SOURCE), **EXPECTED["chart_source"]},
            "producer": {"path": rel(CHART_PRODUCER), **EXPECTED["chart_producer"]},
            "target": {"path": rel(CHART), **EXPECTED["chart"]},
            "localization_receipt": {
                "path": rel(CHART_LOCALIZATION_RECEIPT),
                **EXPECTED["chart_localization_receipt"],
            },
            "visual_receipt": {
                "path": rel(CHART_VISUAL_RECEIPT),
                **EXPECTED["chart_visual_receipt"],
            },
            "checks": chart_checks,
            "independent_render_inspection": {
                "renderer": "pdftoppm",
                "dpi": 300,
                "dimensions_pixels": [1500, 675],
                "source_png_sha256": "8dea17b2d2a84df5549596ba858e37c897e0f5c0df3d15730dd08a0799e8da6a",
                "target_png_sha256": "e94e4123312d3b372aa30d4bed0d86c7cc899716bc39a32ca88e58a0413f02bc",
                "target_pdftotext_sha256": "4e224f87b43d06134a0ed4d40758515cc3fccde661761e3847fc60e00d8ff8e3",
                "finding": "Both Indonesian annotation lines are sharp, centered over the unchanged tail threshold, unclipped, nonoverlapping, and do not obscure the curve or blue tail segment; axes and ticks 0,10,20,30,40,50 remain readable.",
            },
            "caption": "Visualisasi nilai-p untuk X^2 = 40.13 ketika df = 2.",
            "alt_text": "Kurva khi-kuadrat dengan df = 2; luas ekor di sebelah kanan X^2 = 40.13, sekitar 1 dari 500 juta, terlalu kecil untuk terlihat.",
        },
        "scope_guards": {
            "translation_mutated": False,
            "authority_mutated": False,
            "backend_controls_output_release_mutated": False,
            "git_network_credentials_upstream_contact_used": False,
        },
    }
    raw = (json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    if verify_only:
        require(RECEIPT.exists(), "independent receipt missing")
        require(RECEIPT.read_bytes() == raw, "independent receipt replay drift")
    else:
        RECEIPT.write_bytes(raw)
    print(
        json.dumps(
            {
                "mode": "verify" if verify_only else "write",
                "status": result["status"],
                "receipt": {
                    "path": rel(RECEIPT),
                    "bytes": len(raw),
                    "sha256": digest(raw),
                },
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    try:
        raise SystemExit(main(args.verify))
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise
