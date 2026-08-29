#!/usr/bin/env python3
"""Build the deterministic R011-B024 Indonesian learner reader.

B024 extends the admitted B023 reader through complete Chapter 6, Section
6.3 (goodness-of-fit testing with chi-square), exercises 31-34, and the
upstream-public answers 31 and 33.  The operation is isolated under the B024
scratch root and never mutates the live repository, backend, controls, output,
release, Git, network, or credentials.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any

from pypdf import PdfReader

import build_b023_boundary_clean_reader as prior


common = prior.common
ROOT = Path(__file__).resolve().parents[1]
BOUNDARY_ID = "R011-B024"
MODEL = "OpenAI Codex gpt-5.6-sol, Ultra"

SOURCE = ROOT / "scratch/b023-boundary-clean-reader/source-snapshot"
BUILD = ROOT / "scratch/b024-boundary-clean-reader"
SNAPSHOT = BUILD / "source-snapshot"
RUN_A = BUILD / "replay-a"
RUN_B = BUILD / "replay-b"
FINAL = BUILD / "final"
FINAL_PDF = FINAL / "main.pdf"
FINAL_TEXT = FINAL / "main-final.txt"
MANIFEST = BUILD / "R011-B024_BOUNDARY_CLEAN_SOURCE_MANIFEST.tsv"
RECEIPT = FINAL / "R011-B024_BOUNDARY_CLEAN_BUILD_QA.json"

SOURCE_MAIN = SOURCE / "main_boundary_clean_b023.tex"
SOURCE_ANSWERS = (
    SOURCE / "extraTeX/eoceSolutions/eoceSolutions_boundary_clean_b023.tex"
)
SOURCE_CHAPTER = SOURCE / "ch_inference_for_props/TeX/ch_inference_for_props.tex"
SOURCE_EXERCISES_1_16 = (
    SOURCE / "ch_inference_for_props/TeX/inference_for_a_single_proportion.tex"
)
SOURCE_EXERCISES_17_30 = (
    SOURCE / "ch_inference_for_props/TeX/difference_of_two_proportions.tex"
)
SOURCE_EXERCISES_31_34 = (
    SOURCE
    / "ch_inference_for_props/TeX/testing_for_goodness_of_fit_using_chi-square.tex"
)

CUSTOM_MAIN = SNAPSHOT / "main_boundary_clean_b024.tex"
CUSTOM_ANSWERS = (
    SNAPSHOT / "extraTeX/eoceSolutions/eoceSolutions_boundary_clean_b024.tex"
)
CUSTOM_CHAPTER = (
    SNAPSHOT / "ch_inference_for_props/TeX/ch_inference_for_props.tex"
)
CUSTOM_EXERCISES_31_34 = (
    SNAPSHOT
    / "ch_inference_for_props/TeX/testing_for_goodness_of_fit_using_chi-square.tex"
)

STAGING = ROOT / "qa/b024-translation/staging"
SECTION_A = STAGING / "section-lines-1344-1471.id.tex"
SECTION_B = STAGING / "section-lines-1472-1633.id.tex"
SECTION_C = STAGING / "section-lines-1634-1763.id.tex"
SECTION_D = STAGING / "section-lines-1764-2001.id.tex"
EXERCISES_ID = STAGING / "exercises-lines-1-99.id.tex"
ANSWERS_ID = STAGING / "public-answers-lines-1474-1498.id.tex"
O001_GAPS = STAGING / "R011-B024_O001_MASTERY_GAPS.json"
BLUEPRINT = ROOT / "qa/b024-source/R011-B024_BOUNDARY_BLUEPRINT.json"
EXERCISE_ANSWER_QA = (
    ROOT / "qa/b024-translation/R011-B024_EXERCISES_ANSWERS_TRANSLATION_QA.json"
)
CHART_QA = ROOT / "qa/b024-translation/R011-B024_LOCALIZED_CHARTS_QA.json"
CHART_VISUAL_QA = (
    ROOT / "qa/b024-translation/R011-B024_LOCALIZED_CHARTS_VISUAL_QA.json"
)
MAIN_TRANSLATION_AUDIT = (
    ROOT / "qa/b024-translation/R011-B024_MAIN_TRANSLATION_AUDIT.json"
)
MAIN_TRANSLATION_INDEPENDENT_AUDIT = (
    ROOT
    / "qa/b024-translation/R011-B024_MAIN_TRANSLATION_INDEPENDENT_AUDIT.json"
)
INDEPENDENT_EXERCISE_CHART_AUDIT = (
    ROOT
    / "qa/b024-translation/R011-B024_INDEPENDENT_EXERCISE_CHART_AUDIT.json"
)

AUTHORITY_ROOT = (
    ROOT
    / "authority/upstream/"
    "openintro-statistics-fee25091fb24e89c36296fd67c48c1fcf7a93b6e"
)
AUTHORITY_MAIN = AUTHORITY_ROOT / "ch_inference_for_props/TeX/ch_inference_for_props.tex"
AUTHORITY_EXERCISES = (
    AUTHORITY_ROOT
    / "ch_inference_for_props/TeX/testing_for_goodness_of_fit_using_chi-square.tex"
)
AUTHORITY_ANSWERS = AUTHORITY_ROOT / "extraTeX/eoceSolutions/eoceSolutions.tex"

EXPECTED_SOURCE_FILE_COUNT = 1_216
EXPECTED_SOURCE_BYTES = 41_710_911
EXPECTED_SOURCE_INVENTORY_SHA256 = (
    "58e5263490f06d7e4036759f0c6c130b9c61d4a0e24f80769302fbab00b79376"
)

EXPECTED_SOURCE_FILES = {
    SOURCE_MAIN: (
        7_105,
        "ba3cdef14264ec8fc49a53d27fc05774dae996ca63b23ca0d8046f321a19451f",
    ),
    SOURCE_ANSWERS: (
        55_857,
        "045b4d06f36099145a5dd34d15305c356a07482e7bd01fee98437d4471a69045",
    ),
    SOURCE_CHAPTER: (
        55_056,
        "5b82c351cea11ee9777068558e8449f08b71b200b705b9eee855bf1870739ac1",
    ),
    SOURCE_EXERCISES_1_16: (
        14_353,
        "75e17c52954b82604090f09a8131ba5bf9b97494d76f4b34d8c4448ccc426655",
    ),
    SOURCE_EXERCISES_17_30: (
        18_123,
        "d4c845fcd4b06270750f13292ad20d0df1900b3c80883bf745aacfd35e983873",
    ),
    SOURCE_EXERCISES_31_34: (
        4_151,
        "5a57a04b123035c5b5762a98f2c94d4b27745b093ec1e7b0291edff75e995d4e",
    ),
    SOURCE
    / "ch_inference_for_props/figures/bladesTwoSampleHTPValueQC/"
    "bladesTwoSampleHTPValueQC.pdf": (
        19_980,
        "92c3af57f160b5b1788be6610fb574c4a2cd70cd02aa7a21330da8e916238968",
    ),
    SOURCE / "extraTeX/tables/TeX/chiSquareTable.tex": (
        12_800,
        "4be0620c156d3062d2694bf25cb1da73cecdbcde329529ea9fa2af7968f255a4",
    ),
    SOURCE
    / "ch_inference_for_props/figures/eoce/barking_deer_chisq_GOF/"
    "barking_deer.jpg": (
        154_665,
        "45a8a8ad1f2ed33250329ac2c4846d16c2ad49e67d7a442f29584c83a2b4ee22",
    ),
}

EXPECTED_AUTHORITY = {
    AUTHORITY_MAIN: (
        103_385,
        "a2470ca3041209d1f1194b3ab27e8124405d8fdbd1ccece89a0319be13fae8a7",
    ),
    AUTHORITY_EXERCISES: (
        4_151,
        "5a57a04b123035c5b5762a98f2c94d4b27745b093ec1e7b0291edff75e995d4e",
    ),
    AUTHORITY_ANSWERS: (
        106_045,
        "6c4e01376db4c023cc7b3f9949490e57220ef1cb831c580da71efde6ce723268",
    ),
}

EXPECTED_STAGING = {
    SECTION_A: (
        9_094,
        "2c807758f04f5d38e8feaedfe8fcd28dca592c022a10232ccc89ac2e71e7f6a2",
    ),
    SECTION_B: (
        9_227,
        "7230f23e35b9e5d19e86b585e473f9c71f0c6dd000b9e6173a7df34dd75015da",
    ),
    SECTION_C: (
        6_280,
        "ca2b62effbd474bdba83a7a778d6eae2f166b57c0b398e611d3204d6ce771ee7",
    ),
    SECTION_D: (
        11_932,
        "426f235d8fc496bcaec34da3313ef1fb2c18e6b57384abbb46dbb8dc8c66a6a3",
    ),
    EXERCISES_ID: (
        4_270,
        "19f1ce42b5898b5b977f4194c689c1b0510410218c447a6d771449727385cbbc",
    ),
    ANSWERS_ID: (
        1_263,
        "52031886e8ad59bb3b4b18fe758e2301eac2976c6616005ad0e3f88a250854fb",
    ),
    O001_GAPS: (
        2_094,
        "315fd17936d7103ad11f6c9e89c928f9a909edea5b401622f2d075b5c2a5e043",
    ),
    BLUEPRINT: (
        40_830,
        "66cf48d7f797aed42434a78d3e2e43c283cac594f3f4714136a022e1ac78127e",
    ),
    EXERCISE_ANSWER_QA: (
        4_896,
        "3524bb239871e8c8f1b1177b12143bc544d3408e4aef898b68d418dd51ce43df",
    ),
    CHART_QA: (
        4_122,
        "3c6a445e357337ea13bef2f358fab338730431976211b2c918817bbd59c4ab3c",
    ),
    CHART_VISUAL_QA: (
        2_411,
        "42e746f9b439bf653f965fed64dd1d9aec16b2c9dd3f0209c720e8fb9dd3cc44",
    ),
    MAIN_TRANSLATION_AUDIT: (
        9_726,
        "90eb218c6b87169521896f2f3af4d04a08c0f8e5fc61c26dfcb7be80b6d91d8c",
    ),
    MAIN_TRANSLATION_INDEPENDENT_AUDIT: (
        8_247,
        "3258e40dd5fecfa28fe58b04af3b2793b1c28cb8f66529536b4cb6e5e5a6c9de",
    ),
    INDEPENDENT_EXERCISE_CHART_AUDIT: (
        10_169,
        "aa6a9bf9c2f45bf6961cd609e5c38409806ecaef12d43bde900d8bb5fa9210c2",
    ),
}

CHARTS = (
    {
        "role": "chi_square_df",
        "staged": STAGING / "assets/chiSquareDistributionWithInceasingDF.id.pdf",
        "target_rel": Path(
            "ch_inference_for_props/figures/chiSquareDistributionWithInceasingDF/"
            "chiSquareDistributionWithInceasingDF.pdf"
        ),
        "bytes": 10_271,
        "sha256": "feb324a8bf54f25817455997634ebc8d63909ae68a66ed6144a9c4452e0d0420",
        "required_text": ("Derajat kebebasan", "2", "4", "9"),
    },
    {
        "role": "sp500_fit",
        "staged": STAGING / "assets/geomFitEvaluationForSP500.id.pdf",
        "target_rel": Path(
            "ch_inference_for_props/figures/geomFitEvaluationForSP500/"
            "geomFitEvaluationForSP500.pdf"
        ),
        "bytes": 10_898,
        "sha256": "9e9d60d2ba4a0de959c694ef97b6f4d153f3582c67a350f76d8964fcacf06b18",
        "required_text": (
            "Frekuensi",
            "Teramati",
            "Harapan",
            "Waktu tunggu hingga hari kenaikan",
        ),
    },
    {
        "role": "sp500_pvalue",
        "staged": STAGING / "assets/geomFitPValueForSP500.id.pdf",
        "target_rel": Path(
            "ch_inference_for_props/figures/geomFitPValueForSP500/"
            "geomFitPValueForSP500.pdf"
        ),
        "bytes": 32_003,
        "sha256": "7f7d5b0a39a3307bb13892d734628423450ec710e83f9ac715e7e00aa1adcaf8",
        "required_text": ("Luas yang menyatakan", "nilai-p"),
    },
)

SCOPE_B024 = r"""\chapter*{Cakupan edisi parsial ini}
\addcontentsline{toc}{chapter}{Cakupan edisi parsial ini}
Pembaca ini berhenti tepat setelah Bagian~6.3,
\emph{Uji kesesuaian menggunakan khi-kuadrat}. Cakupan Bab~6 dalam edisi
ini memuat latihan 1--34. Semua jawaban publik yang tersedia dari sumber
disertakan, yaitu jawaban bernomor ganjil 1--33. Jawaban bernomor genap
2--34 memang tidak tersedia dalam sumber publik; jawaban-jawaban itu
dicatat sebagai kesenjangan pendamping kemahiran O001 dan tidak direka."""

OLD_B023_NOTE = "% Boundary-clean learner reader through Chapter 6, Section 6.2."
NEW_B024_NOTE = "% Boundary-clean learner reader through Chapter 6, Section 6.3."
OLD_ANSWER_INCLUDE = (
    r"\include{extraTeX/eoceSolutions/eoceSolutions_boundary_clean_b023}"
)
NEW_ANSWER_INCLUDE = (
    r"\include{extraTeX/eoceSolutions/eoceSolutions_boundary_clean_b024}"
)
OLD_NAV = (
    r"  \chaptersection{singleProportion}" + "\n"
    r"  \chaptersection{differenceOfTwoProportions}" + "\n"
    "% Boundary-clean reader omits navigation to excluded later Chapter 6 sections."
)
NEW_NAV = (
    r"  \chaptersection{singleProportion}" + "\n"
    r"  \chaptersection{differenceOfTwoProportions}" + "\n"
    r"  \chaptersection{oneWayChiSquare}" + "\n"
    "% Boundary-clean reader omits navigation to excluded later Chapter 6 sections."
)
FORCED_BREAK = r"\D{\newpage}"
REFLOW_NOTE = "% Boundary-clean reader removes a legacy forced page break."

FORBIDDEN_STAGED_ENGLISH = (
    "Testing for goodness of fit using chi-square",
    "Wait Until Positive Day",
    "Area representing the p-value",
)
FORBIDDEN_READER_ENGLISH = (
    "Testing for goodness of fit using chi-square",
    "Testing for independence in two-way tables",
    "Chi-square test of independence",
    "Inference for numerical data",
    "Introduction to linear regression",
    "Multiple and logistic regression",
    "Degrees of Freedom",
    "Wait Until Positive Day",
    "Area representing the p-value",
)


def normalized_lf(path: Path) -> str:
    return prior.normalized_lf(path)


def memory_identity(name: str, value: str) -> dict[str, Any]:
    return prior.memory_identity(name, value)


def source_slice(path: Path, first_line: int, last_line: int) -> bytes:
    return prior.source_slice(path, first_line, last_line)


def require_slice(
    path: Path,
    first_line: int,
    last_line: int,
    expected: tuple[int, str],
) -> None:
    prior.require_slice(path, first_line, last_line, expected)


def verify_blueprint() -> dict[str, Any]:
    common.require_exact(BLUEPRINT, EXPECTED_STAGING[BLUEPRINT])
    blueprint = json.loads(BLUEPRINT.read_text(encoding="utf-8"))
    common.require(blueprint.get("boundary_id") == BOUNDARY_ID, "B024 blueprint boundary changed")
    common.require(
        blueprint.get("status")
        == "PASS_SOURCE_ASSET_DATA_RIGHTS_AND_BOUNDARY_DEPENDENCY_CLOSURE",
        "B024 source/asset/data closure did not pass",
    )
    authority = blueprint.get("authority", {})
    common.require(
        authority.get("commit") == "fee25091fb24e89c36296fd67c48c1fcf7a93b6e"
        and authority.get("branch_observed") == "master",
        "B024 authority pin changed",
    )
    main = blueprint.get("main_source", {})
    common.require(
        main.get("start_line") == 1344
        and main.get("end_line") == 2001
        and main.get("start_label") == "oneWayChiSquare"
        and main.get("slice", {}).get("bytes") == 35_242
        and main.get("slice", {}).get("sha256")
        == "c8f9a8299a08be463fa869321de05db2cfeaf5e1a8abb0d65a035cb4a09d5ec2",
        "B024 main boundary changed",
    )
    closure = blueprint.get("exercise_answer_closure", {})
    common.require(
        closure.get("chapter_exercise_ids") == [31, 32, 33, 34]
        and closure.get("public_answer_ids") == [31, 33]
        and closure.get("o001_gap_ids") == [32, 34]
        and closure.get("restricted_solutions_accessed_or_invented") is False,
        "B024 exercise/answer closure changed",
    )
    figures = blueprint.get("figure_asset_closure", [])
    common.require(
        isinstance(figures, list)
        and len(figures) == 11
        and sum(bool(row.get("content_localization_required")) for row in figures) == 3,
        "B024 figure closure changed",
    )
    rights = blueprint.get("rights", {})
    common.require(
        rights.get("branding_excluded") is True
        and rights.get("new_unresolved_binary_dependency") is False
        and "CC BY 2.0" in str(rights.get("barking_deer_photo", "")),
        "B024 component-rights closure changed",
    )
    post = blueprint.get("post_boundary_cursor", {})
    common.require(
        post.get("working_boundary_id") == "R011-B025"
        and post.get("line") == 2008
        and post.get("label") == "twoWayTablesAndChiSquare"
        and post.get("label_line") == 2009,
        "B024 next cursor changed",
    )
    return {
        "boundary_id": blueprint["boundary_id"],
        "authority": authority,
        "main_source": main,
        "exercise_answer_closure": closure,
        "figure_asset_count": len(figures),
        "production_closure": blueprint.get("production_closure", {}),
        "rights": rights,
        "post_boundary_cursor": post,
    }


def verify_external_qa() -> dict[str, Any]:
    for path in (
        EXERCISE_ANSWER_QA,
        CHART_QA,
        CHART_VISUAL_QA,
        MAIN_TRANSLATION_AUDIT,
        MAIN_TRANSLATION_INDEPENDENT_AUDIT,
        INDEPENDENT_EXERCISE_CHART_AUDIT,
    ):
        common.require_exact(path, EXPECTED_STAGING[path])
    exercise = json.loads(EXERCISE_ANSWER_QA.read_text(encoding="utf-8"))
    charts = json.loads(CHART_QA.read_text(encoding="utf-8"))
    visual = json.loads(CHART_VISUAL_QA.read_text(encoding="utf-8"))
    main = json.loads(MAIN_TRANSLATION_AUDIT.read_text(encoding="utf-8"))
    main_independent = json.loads(
        MAIN_TRANSLATION_INDEPENDENT_AUDIT.read_text(encoding="utf-8")
    )
    exercise_independent = json.loads(
        INDEPENDENT_EXERCISE_CHART_AUDIT.read_text(encoding="utf-8")
    )
    common.require(
        exercise.get("status")
        == "PASS_EXERCISES_31_34_AND_ALL_LINKED_PUBLIC_ODD_ANSWERS_TRANSLATED"
        and exercise.get("scope", {}).get("exercise_ids") == [31, 32, 33, 34]
        and exercise.get("scope", {}).get("public_answer_ids") == [31, 33]
        and exercise.get("scope", {}).get("o001_mastery_gap_ids") == [32, 34]
        and exercise.get("scope", {}).get("restricted_solutions_accessed_or_invented")
        is False,
        "B024 exercise/answer QA changed",
    )
    common.require(
        charts.get("status")
        == "PASS_THREE_LABEL_BEARING_CHARTS_LOCALIZED_AND_EXACTLY_REPLAYED"
        and charts.get("deterministic_two_replay") is True
        and charts.get("visible_english_labels_remaining") == 0,
        "B024 chart QA changed",
    )
    common.require(
        visual.get("status")
        == "PASS_ALL_THREE_LOCALIZED_CHARTS_VISUALLY_INSPECTED_ZERO_DEFECTS"
        and visual.get("inspection", {}).get("chart_count") == 3
        and not any(visual.get("inspection", {}).get("defects", {}).values()),
        "B024 chart visual QA changed",
    )
    common.require(
        main.get("status")
        == "PASS_COMPLETE_MAIN_SECTION_TRANSLATION_STRUCTURAL_MATH_LANGUAGE_AND_CORRECTION_QA"
        and main.get("coverage", {}).get("main_instructional_source_complete")
        is True
        and main.get("coverage", {}).get("source_first_line") == 1344
        and main.get("coverage", {}).get("source_last_line") == 2001
        and main.get("aggregate_target", {}).get("bytes") == 36_533
        and main.get("aggregate_target", {}).get("sha256")
        == "11d7d6cce5dcf73da985da249feec4e993102e3a741ab5c6e3d75b9e957f5e7b",
        "B024 main translation audit changed",
    )
    common.require(
        main_independent.get("status")
        == (
            "PASS_INDEPENDENT_MAIN_TRANSLATION_MEANING_STRUCTURE_MATH_"
            "CORRECTIONS_CHARTS_RIGHTS_AND_LANGUAGE_QA"
        )
        and main_independent.get("independent_findings", {})
        .get("residual_english", {})
        .get("status")
        == "PASS_ZERO_READER_PROSE_PHRASES",
        "B024 independent main translation audit changed",
    )
    common.require(
        exercise_independent.get("status")
        == (
            "PASS_INDEPENDENT_EXERCISE_ANSWER_O001_CHART_DATA_RIGHTS_"
            "AND_LANGUAGE_AUDIT"
        )
        and exercise_independent.get("scope_guards", {}).get(
            "restricted_solution_source_opened"
        )
        is False,
        "B024 independent exercise/chart audit changed",
    )
    return {
        "exercise_answer_qa": common.identity(EXERCISE_ANSWER_QA),
        "chart_qa": common.identity(CHART_QA),
        "chart_visual_qa": common.identity(CHART_VISUAL_QA),
        "main_translation_audit": common.identity(MAIN_TRANSLATION_AUDIT),
        "main_translation_independent_audit": common.identity(
            MAIN_TRANSLATION_INDEPENDENT_AUDIT
        ),
        "independent_exercise_chart_audit": common.identity(
            INDEPENDENT_EXERCISE_CHART_AUDIT
        ),
    }


def verify_inputs() -> dict[str, Any]:
    common.require(SOURCE.is_dir(), "admitted B023 source snapshot absent")
    inventory = common.source_inventory(SOURCE)
    common.require(
        inventory["files"] == EXPECTED_SOURCE_FILE_COUNT,
        "B023 source file count changed",
    )
    common.require(
        inventory["bytes"] == EXPECTED_SOURCE_BYTES,
        "B023 source byte count changed",
    )
    common.require(
        inventory["inventory_sha256"] == EXPECTED_SOURCE_INVENTORY_SHA256,
        "B023 source inventory changed",
    )
    for path, expected in EXPECTED_SOURCE_FILES.items():
        common.require_exact(path, expected)
    for path, expected in EXPECTED_AUTHORITY.items():
        common.require_exact(path, expected)
    require_slice(
        AUTHORITY_MAIN,
        1344,
        2001,
        (
            35_242,
            "c8f9a8299a08be463fa869321de05db2cfeaf5e1a8abb0d65a035cb4a09d5ec2",
        ),
    )
    require_slice(
        AUTHORITY_EXERCISES,
        1,
        99,
        EXPECTED_AUTHORITY[AUTHORITY_EXERCISES],
    )
    require_slice(
        AUTHORITY_ANSWERS,
        1474,
        1498,
        (
            1_122,
            "20755031c3c19a24995a6be26d85885e6974e5125c69bdafeaf603a2cf613e1a",
        ),
    )
    for path, expected in EXPECTED_STAGING.items():
        common.require_exact(path, expected)
    return {
        "base_source": {
            key: inventory[key]
            for key in ("files", "bytes", "inventory_sha256")
        },
        "source_anchors": [
            common.identity(path) for path in EXPECTED_SOURCE_FILES
        ],
        "authority_slices": {
            "main_1344_2001": {
                "bytes": 35_242,
                "sha256": (
                    "c8f9a8299a08be463fa869321de05db2cfeaf5e1a8abb0d65a035cb4a09d5ec2"
                ),
            },
            "exercises_1_99": {
                "bytes": 4_151,
                "sha256": EXPECTED_AUTHORITY[AUTHORITY_EXERCISES][1],
            },
            "answers_1474_1498": {
                "bytes": 1_122,
                "sha256": (
                    "20755031c3c19a24995a6be26d85885e6974e5125c69bdafeaf603a2cf613e1a"
                ),
            },
        },
        "blueprint": verify_blueprint(),
        "external_qa": verify_external_qa(),
    }


def verify_staged_fragments() -> dict[str, Any]:
    fragments = (
        (SECTION_A, 1344, 1471, 0),
        (SECTION_B, 1472, 1633, 1),
        (SECTION_C, 1634, 1763, 1),
        (SECTION_D, 1764, 2001, 1),
    )
    for path, first, last, expected_breaks in fragments:
        target = normalized_lf(path)
        common.require(target.endswith("\n"), f"fragment lacks terminal LF: {common.rel(path)}")
        common.require(
            target.count(FORCED_BREAK) == expected_breaks,
            f"fragment break topology changed: {common.rel(path)}",
        )
        source = source_slice(AUTHORITY_MAIN, first, last).decode("utf-8")
        prior.require_protected_sequences(source, target, common.rel(path))
        stripped = re.sub(r"(?m)^%.*$", "", target)
        for phrase in FORBIDDEN_STAGED_ENGLISH:
            common.require(
                phrase.casefold() not in stripped.casefold(),
                f"English staged phrase remains ({phrase}): {common.rel(path)}",
            )

    exercises = normalized_lf(EXERCISES_ID)
    common.require(
        exercises.startswith(r"\exercisesheader{}" + "\n"),
        "B024 exercise header changed",
    )
    exercise_numbers = [
        int(value) for value in re.findall(r"(?m)^% (\d+)\s*$", exercises)
    ]
    common.require(
        exercise_numbers == [31, 32, 33, 34],
        f"B024 exercise sequence changed: {exercise_numbers}",
    )
    common.require(exercises.count(r"\eoce{") == 4, "B024 exercise count changed")
    source_exercises = source_slice(AUTHORITY_EXERCISES, 1, 99).decode("utf-8")
    prior.require_protected_sequences(
        source_exercises,
        exercises,
        common.rel(EXERCISES_ID),
    )

    answers = normalized_lf(ANSWERS_ID)
    answer_numbers = [
        int(value) for value in re.findall(r"(?m)^% (\d+)\s*$", answers)
    ]
    common.require(
        answer_numbers == [31, 33],
        f"B024 public-answer sequence changed: {answer_numbers}",
    )
    common.require(answers.count(r"\eocesol{") == 2, "B024 answer count changed")
    source_answers = source_slice(AUTHORITY_ANSWERS, 1474, 1498).decode("utf-8")
    prior.require_protected_sequences(
        source_answers,
        answers,
        common.rel(ANSWERS_ID),
    )

    gaps = json.loads(O001_GAPS.read_text(encoding="utf-8"))
    common.require(
        gaps.get("boundary_id") == BOUNDARY_ID
        and gaps.get("o001_gap_ids") == [32, 34]
        and gaps.get("public_answers_present") == [31, 33]
        and gaps.get("restricted_solutions_accessed_or_invented") is False,
        "B024 O001 gap ledger changed",
    )

    chart_rows: list[dict[str, Any]] = []
    for chart in CHARTS:
        path = chart["staged"]
        common.require_exact(path, (chart["bytes"], chart["sha256"]))
        reader = PdfReader(path)
        common.require(len(reader.pages) == 1, f"localized chart page count changed: {chart['role']}")
        text = reader.pages[0].extract_text() or ""
        compact_text = re.sub(r"\s+", "", text).casefold()
        for token in chart["required_text"]:
            common.require(
                re.sub(r"\s+", "", token).casefold() in compact_text,
                f"localized chart token absent ({token}): {chart['role']}",
            )
        for phrase in (
            "Degrees of Freedom",
            "Observed",
            "Expected",
            "Frequency",
            "Wait Until Positive Day",
            "Area representing the p-value",
        ):
            common.require(
                phrase.casefold() not in text.casefold(),
                f"English chart label remains ({phrase}): {chart['role']}",
            )
        chart_rows.append(
            {
                **common.identity(path),
                "role": chart["role"],
                "pages": 1,
                "visible_text_checked": list(chart["required_text"]),
            }
        )
    return {
        "chapter_fragments": [
            common.identity(path) for path, _, _, _ in fragments
        ],
        "exercises": common.identity(EXERCISES_ID),
        "public_answers": common.identity(ANSWERS_ID),
        "o001_gaps": common.identity(O001_GAPS),
        "localized_charts": chart_rows,
        "exercise_ordinals": exercise_numbers,
        "public_answer_ordinals": answer_numbers,
        "o001_gap_ordinals": [32, 34],
        "restricted_solutions_accessed_or_invented": False,
    }


def prepare_custom_texts() -> tuple[dict[Path, str], dict[str, Any]]:
    main = normalized_lf(SOURCE_MAIN)
    common.require(main.count(prior.SCOPE_B023) == 1, "B023 scope block changed")
    main = main.replace(prior.SCOPE_B023, SCOPE_B024)
    common.require(main.count(OLD_B023_NOTE) == 1, "B023 boundary note changed")
    main = main.replace(OLD_B023_NOTE, NEW_B024_NOTE)
    common.require(main.count(OLD_ANSWER_INCLUDE) == 1, "B023 answer include changed")
    main = main.replace(OLD_ANSWER_INCLUDE, NEW_ANSWER_INCLUDE)
    table_stub = r"\label{normalProbabilityTable}" + "\n"
    common.require(main.count(table_stub) == 1, "B023 appendix-stub anchor changed")
    main = main.replace(
        table_stub,
        table_stub + r"\label{chiSquareProbabilityTable}" + "\n",
        1,
    )

    chapter = normalized_lf(SOURCE_CHAPTER)
    common.require(chapter.count(OLD_NAV) == 1, "B023 chapter navigation changed")
    chapter = chapter.replace(OLD_NAV, NEW_NAV)
    values = [
        normalized_lf(SECTION_A),
        normalized_lf(SECTION_B),
        normalized_lf(SECTION_C),
        normalized_lf(SECTION_D),
    ]
    expected_breaks = [0, 1, 1, 1]
    for index, (value, count) in enumerate(zip(values, expected_breaks), start=1):
        common.require(value.endswith("\n"), f"B024 section fragment {index} lacks LF")
        common.require(
            value.count(FORCED_BREAK) == count,
            f"B024 section fragment {index} break topology changed",
        )
    values = [value.replace(FORCED_BREAK, REFLOW_NOTE) for value in values]
    input_previous = (
        r"{\input{ch_inference_for_props/TeX/difference_of_two_proportions.tex}}"
    )
    common.require(
        chapter.count(input_previous) == 1,
        "B023 Section 6.2 input anchor changed",
    )
    chapter = chapter.replace(
        input_previous,
        input_previous + "\n\n" + "".join(values),
        1,
    )
    active_sections = re.findall(r"(?m)^\s*(?!%)\\section\{", chapter)
    common.require(len(active_sections) == 3, "assembled Chapter 6 section count changed")
    for label in ("singleProportion", "differenceOfTwoProportions", "oneWayChiSquare"):
        common.require(
            chapter.count(rf"\label{{{label}}}") == 1,
            f"assembled section label count changed: {label}",
        )
    exercise_input = (
        r"\input{ch_inference_for_props/TeX/"
        r"testing_for_goodness_of_fit_using_chi-square.tex}"
    )
    common.require(
        chapter.count(exercise_input) == 1,
        "B024 exercise input count changed",
    )
    common.require(FORCED_BREAK not in chapter, "legacy Section 6.3 break remained")

    staged_exercises = normalized_lf(EXERCISES_ID)
    common.require(
        staged_exercises.startswith(r"\exercisesheader{}" + "\n"),
        "B024 exercise header anchor changed",
    )
    exercise_body = staged_exercises.split("\n", 1)[1]
    flowing_header = "\n".join(
        [
            r"\begingroup",
            r"\renewcommand{\clearpageforsection}{}",
            r"\exercisesheader{}",
            r"\endgroup",
        ]
    )
    new_exercises = flowing_header + "\n\n" + exercise_body
    numbers = [
        int(value) for value in re.findall(r"(?m)^% (\d+)\s*$", new_exercises)
    ]
    common.require(numbers == [31, 32, 33, 34], "B024 exercise sequence changed")
    common.require(new_exercises.count(r"\eoce{") == 4, "B024 exercise count changed")

    old_answers = normalized_lf(SOURCE_ANSWERS)
    closing = "\n\\end{multicols}\n"
    common.require(old_answers.endswith(closing), "B023 answer close anchor changed")
    new_answers = normalized_lf(ANSWERS_ID)
    answers = (
        old_answers[: -len(closing)].rstrip("\n")
        + "\n\n"
        + new_answers.rstrip("\n")
        + closing
    )
    common.require(
        answers.count(r"\begin{multicols}{2}") == answers.count(r"\end{multicols}"),
        "answer columns unbalanced",
    )
    common.require(
        answers.rstrip().endswith(r"\end{multicols}"),
        "B024 answer close absent",
    )
    answer_numbers = [
        int(value) for value in re.findall(r"(?m)^% (\d+)\s*$", new_answers)
    ]
    common.require(answer_numbers == [31, 33], "B024 answer sequence changed")

    custom = {
        CUSTOM_MAIN: main,
        CUSTOM_CHAPTER: chapter,
        CUSTOM_EXERCISES_31_34: new_exercises,
        CUSTOM_ANSWERS: answers,
    }
    transforms = {
        "scope_updated": "through Chapter 6, Section 6.3",
        "chapter_navigation_added": "oneWayChiSquare",
        "section_6_3_fragments_appended": [
            "1344-1471",
            "1472-1633",
            "1634-1763",
            "1764-2001",
        ],
        "exercise_closure": list(range(1, 35)),
        "public_answer_closure": list(range(1, 34, 2)),
        "o001_gap_closure": list(range(2, 35, 2)),
        "legacy_forced_page_breaks_removed": {
            "section_main": 3,
            "section_exercises": 0,
            "total": 3,
        },
        "translation_staging_mutated": False,
        "localized_charts_installed": 3,
        "later_source_counted_as_learner_output": False,
        "restricted_solutions_accessed_or_invented": False,
    }
    return custom, transforms


def install_localized_charts() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for chart in CHARTS:
        target = SNAPSHOT / chart["target_rel"]
        before = common.identity(target)
        shutil.copy2(chart["staged"], target)
        after = common.identity(target)
        common.require(
            (after["bytes"], after["sha256"])
            == (chart["bytes"], chart["sha256"]),
            f"localized chart copy differs: {chart['role']}",
        )
        rows.append(
            {
                "role": chart["role"],
                "source_staging": common.identity(chart["staged"]),
                "before": before,
                "installed": after,
            }
        )
    return rows


def make_custom_sources() -> dict[str, Any]:
    texts, transforms = prepare_custom_texts()
    for path, text in texts.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    charts = install_localized_charts()
    return {
        "custom_main": common.identity(CUSTOM_MAIN),
        "custom_chapter": common.identity(CUSTOM_CHAPTER),
        "custom_exercises_1_16_carried": common.identity(
            SNAPSHOT
            / "ch_inference_for_props/TeX/inference_for_a_single_proportion.tex"
        ),
        "custom_exercises_17_30_carried": common.identity(
            SNAPSHOT / "ch_inference_for_props/TeX/difference_of_two_proportions.tex"
        ),
        "custom_exercises_31_34": common.identity(CUSTOM_EXERCISES_31_34),
        "custom_answers_1_34_public": common.identity(CUSTOM_ANSWERS),
        "localized_charts": charts,
        "assembly_transformations": transforms,
    }


def build_once(
    label: str,
    directory: Path,
    tools: dict[str, str],
    seed: str,
) -> dict[str, Any]:
    common.require(
        not directory.exists(),
        f"refusing to overwrite replay: {common.rel(directory)}",
    )
    directory.mkdir(parents=True)
    env = dict(os.environ)
    env.update(
        {
            "SOURCE_DATE_EPOCH": "1787961600",
            "FORCE_SOURCE_DATE": "1",
            "TZ": "UTC",
            "MIKTEX_ENABLE_INSTALLER": "0",
        }
    )
    env["BIBINPUTS"] = str(SNAPSHOT) + os.pathsep + env.get("BIBINPUTS", "")
    latex = [
        tools["pdflatex"],
        "-interaction=nonstopmode",
        "-halt-on-error",
        "-file-line-error",
        "-recorder",
        "-no-shell-escape",
        "-synctex=0",
        "-jobname=main",
        f"-output-directory={directory}",
        rf"\pdftrailerid{{<{seed}><{seed}>}}\input{{main_boundary_clean_b024.tex}}",
    ]
    common.run_logged(latex, SNAPSHOT, directory / "console-pass1.txt", env)
    common.run_logged(
        [tools["bibtex"], "main"],
        directory,
        directory / "console-bibtex.txt",
        env,
    )
    common.run_logged(
        [tools["makeindex"], "main.idx"],
        directory,
        directory / "console-makeindex1.txt",
        env,
    )
    common.run_logged(latex, SNAPSHOT, directory / "console-pass2.txt", env)
    common.run_logged(
        [tools["makeindex"], "main.idx"],
        directory,
        directory / "console-makeindex2.txt",
        env,
    )
    common.run_logged(latex, SNAPSHOT, directory / "console-pass3.txt", env)
    pdf = directory / "main.pdf"
    common.require(pdf.is_file(), f"{label} produced no PDF")
    pass3 = directory / "main-pass3.pdf"
    shutil.copy2(pdf, pass3)
    common.run_logged(
        [tools["makeindex"], "main.idx"],
        directory,
        directory / "console-makeindex3.txt",
        env,
    )
    common.run_logged(latex, SNAPSHOT, directory / "console-pass4.txt", env)
    common.require(
        common.identity(pdf)["sha256"] == common.identity(pass3)["sha256"],
        f"{label} pass 3/4 differ",
    )
    common.run_logged(
        [tools["pdfinfo"], str(pdf)],
        directory,
        directory / "console-pdfinfo.txt",
    )
    common.run_logged(
        [tools["mutool"], "show", str(pdf), "trailer"],
        directory,
        directory / "console-mutool-trailer.txt",
    )
    text = directory / "main-final.txt"
    common.run_logged(
        [
            tools["pdftotext"],
            "-layout",
            "-enc",
            "UTF-8",
            str(pdf),
            str(text),
        ],
        directory,
        directory / "console-pdftotext.txt",
    )
    extracted = text.read_bytes()
    try:
        extracted_text = extracted.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise common.GateError(
            f"{label} pdftotext output is not UTF-8: {exc}"
        ) from exc
    canonical_text = extracted_text.replace("\r\n", "\n").replace("\r", "\n")
    text.write_bytes(canonical_text.encode("utf-8"))
    common.require(
        b"\r" not in text.read_bytes(),
        f"{label} canonical text still contains CR",
    )
    info = (directory / "console-pdfinfo.txt").read_text(
        encoding="utf-8",
        errors="replace",
    )
    match = re.search(r"^Pages:\s+(\d+)", info, re.MULTILINE)
    pages = int(match.group(1)) if match else 0
    common.require(
        240 <= pages <= 430,
        f"{label} page count outside B024 expectation: {pages}",
    )
    log = (directory / "console-pass4.txt").read_text(
        encoding="utf-8",
        errors="replace",
    )
    warnings = {
        "undefined_references": len(
            re.findall(
                r"There were undefined references|Reference .* undefined",
                log,
                re.I,
            )
        ),
        "undefined_citations": len(
            re.findall(
                r"There were undefined citations|Citation .* undefined",
                log,
                re.I,
            )
        ),
        "multiply_defined_labels": len(
            re.findall(r"multiply defined", log, re.I)
        ),
        "rerun_required": len(
            re.findall(
                r"Rerun to get cross-references right|Label\(s\) may have changed",
                log,
                re.I,
            )
        ),
    }
    common.require(
        not any(warnings.values()),
        f"{label} terminal LaTeX warnings: {warnings}",
    )
    return {
        "label": label,
        "pdf": common.identity(pdf),
        "pass3": common.identity(pass3),
        "text": common.identity(text),
        "pages": pages,
        "trailer_ids": common.trailer_ids(
            directory / "console-mutool-trailer.txt"
        ),
        "terminal_log": common.identity(directory / "console-pass4.txt"),
        "warnings": {
            "fatal": warnings,
            "overfull_hbox": len(re.findall(r"Overfull \\hbox", log)),
        },
    }


def write_manifest() -> dict[str, Any]:
    inventory = common.source_inventory(SNAPSHOT)
    raw = "".join(
        f"{name}\t{size}\t{digest}\n"
        for name, size, digest in inventory.pop("rows")
    ).encode("utf-8")
    MANIFEST.write_bytes(raw)
    result = {**common.identity(MANIFEST), **inventory}
    common.require(result["files"] == 1_218, "B024 source snapshot file count changed")
    return result


def reader_language_qa(text_path: Path, expected_pages: int) -> dict[str, Any]:
    raw_bytes = text_path.read_bytes()
    common.require(
        b"\r" not in raw_bytes,
        "reader-language QA received noncanonical CR text",
    )
    raw = raw_bytes.decode("utf-8")
    pages = raw.split("\f")
    common.require(
        pages and pages[-1].strip() == "",
        "pdftotext terminal form-feed sentinel absent",
    )
    pages.pop()
    common.require(
        len(pages) == expected_pages,
        f"pagewise text count differs from PDF pages: {len(pages)} != {expected_pages}",
    )
    normalized_pages = [re.sub(r"\s+", " ", page).strip() for page in pages]
    residual: dict[str, list[int]] = {}
    for phrase in FORBIDDEN_READER_ENGLISH:
        hits = [
            index + 1
            for index, page in enumerate(normalized_pages)
            if phrase.casefold() in page.casefold()
        ]
        if hits:
            residual[phrase] = hits
    common.require(
        not residual,
        f"untranslated or excluded English reached learner pages: {residual}",
    )
    joined = " ".join(normalized_pages)
    required = (
        "Inferensi untuk data kategoris",
        "Uji kesesuaian menggunakan khi-kuadrat",
        "Distribusi khi-kuadrat",
        "Derajat kebebasan",
        "Menentukan nilai-p untuk distribusi khi-kuadrat",
        "Menilai kesesuaian suatu distribusi",
        "Waktu tunggu hingga hari kenaikan",
        "Luas yang menyatakan nilai-p",
        "Benar atau salah, Bagian I",
        "Buku teks sumber terbuka",
        "Solusi latihan",
        MODEL,
    )
    missing = [
        phrase for phrase in required if phrase.casefold() not in joined.casefold()
    ]
    common.require(
        not missing,
        f"accepted Indonesian B024 content absent: {missing}",
    )
    return {
        "pages_checked": len(normalized_pages),
        "residual_english_by_phrase": residual,
        "required_phrases": list(required),
        "required_phrases_absent": missing,
        "pagewise_residual_pass": True,
        "later_section_counted_as_learner_output": False,
    }


def self_test() -> dict[str, Any]:
    inputs = verify_inputs()
    common.require(not BUILD.exists(), "B024 build root already exists")
    staged = verify_staged_fragments()
    texts, transforms = prepare_custom_texts()
    tools = common.find_tools()
    previews = [
        memory_identity(common.rel(path), value) for path, value in texts.items()
    ]
    return {
        "boundary_id": BOUNDARY_ID,
        "status": "PASS_INERT_EXACT_INPUTS_STAGING_ASSEMBLY_AND_TOOLCHAIN_BOUND",
        "inputs": inputs,
        "staged": staged,
        "assembly_preview": previews,
        "assembly_transformations": transforms,
        "tools": sorted(tools),
        "writes_performed": False,
    }


def execute() -> dict[str, Any]:
    inputs = verify_inputs()
    staged = verify_staged_fragments()
    common.require(not BUILD.exists(), "refusing to overwrite B024 build root")
    BUILD.mkdir(parents=True)
    shutil.copytree(SOURCE, SNAPSHOT)
    custom = make_custom_sources()
    manifest = write_manifest()
    tools = common.find_tools()
    seed = manifest["sha256"][:32].upper()
    run_a = build_once("replay-a", RUN_A, tools, seed)
    run_b = build_once("replay-b", RUN_B, tools, seed)
    common.require(
        run_a["pages"] == run_b["pages"],
        "B024 replay page counts differ",
    )
    common.require(
        run_a["pdf"]["sha256"] == run_b["pdf"]["sha256"],
        "B024 replay PDFs differ",
    )
    common.require(
        run_a["text"]["sha256"] == run_b["text"]["sha256"],
        "B024 replay text differs",
    )
    common.require(
        run_a["trailer_ids"] == run_b["trailer_ids"],
        "B024 replay trailer IDs differ",
    )
    FINAL.mkdir()
    shutil.copy2(RUN_A / "main.pdf", FINAL_PDF)
    shutil.copy2(RUN_A / "main-final.txt", FINAL_TEXT)
    language = reader_language_qa(FINAL_TEXT, run_a["pages"])
    receipt = {
        "$schema": "interlanguage.r011-b024-boundary-clean-reader-build/v1",
        "boundary_id": BOUNDARY_ID,
        "status": (
            "PASS_TWO_REPLAY_DETERMINISTIC_BOUNDARY_CLEAN_BUILD_"
            "LANGUAGE_QA_COMPLETE_READER_VISUAL_QA_PENDING"
        ),
        "included_scope": (
            "All admitted B023 Indonesian learner work, plus complete Chapter 6 "
            "Section 6.3; exercises 31-34; public answers 31 and 33. Aggregate "
            "closure is exercises 1-34 and public odd answers 1-33."
        ),
        "excluded_untranslated_scope": [
            "Chapter 6 even answers 2-34, recorded as explicit O001 gaps",
            "Chapter 6 Section 6.4 onward and Chapters 7-9",
            "untranslated data, table, and index appendices not visible in the learner reader",
            "restricted instructor solutions",
        ],
        "inputs": inputs,
        "staged": staged,
        "custom_sources": custom,
        "source_manifest": manifest,
        "replay_a": run_a,
        "replay_b": run_b,
        "determinism": {
            "pdf_byte_identical": True,
            "text_byte_identical": True,
            "trailer_ids_equal": True,
            "pass3_pass4_stable_in_each_replay": True,
        },
        "candidate_artifact": common.identity(FINAL_PDF),
        "candidate_text": common.identity(FINAL_TEXT),
        "page_count": run_a["pages"],
        "language_qa": language,
        "chart_qa": inputs["external_qa"]["chart_qa"],
        "chart_visual_qa": inputs["external_qa"]["chart_visual_qa"],
        "translation_provenance": MODEL,
        "complete_corpus": False,
        "source_closure_counted_as_learner_output": False,
        "restricted_solutions_accessed_or_invented": False,
        "next_cursor": {
            "boundary_id": "R011-B025",
            "path": "ch_inference_for_props/TeX/ch_inference_for_props.tex",
            "first_instructional_line": 2008,
            "first_instructional_label": "twoWayTablesAndChiSquare",
            "label_line": 2009,
        },
        "backend_mutated": False,
        "controls_mutated": False,
        "output_mutated": False,
        "release_mutated": False,
        "publication_performed": False,
        "git_used": False,
        "network_used": False,
        "credentials_accessed": False,
        "upstream_contact": False,
    }
    RECEIPT.write_bytes(common.canonical_json(receipt))
    return receipt


def main() -> int:
    args = sys.argv[1:]
    if args == ["--self-test"]:
        result = self_test()
    elif args == ["--build"]:
        result = execute()
    else:
        raise SystemExit(
            "usage: build_b024_boundary_clean_reader.py --self-test | --build"
        )
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "boundary_id",
                    "status",
                    "page_count",
                    "candidate_artifact",
                    "source_manifest",
                    "assembly_preview",
                    "tools",
                    "writes_performed",
                )
                if key in result
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except common.GateError as exc:
        raise SystemExit(f"REFUSED: {exc}")
