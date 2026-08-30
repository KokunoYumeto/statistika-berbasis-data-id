#!/usr/bin/env python3
"""Build the deterministic R011-B026 Indonesian learner reader.

B026 extends the exact admitted and publicly verified B025 boundary through
Chapter 7 Section 7.1, its exercises 1-14, and upstream-public odd answers
1-13.  The source base is the sealed B025 build snapshot.  The build is
fail-closed until all six main-translation receipts, exercise/answer/O001
receipt, and localized-asset receipt and bytes match the constants below.

All writes are isolated under ``scratch/b026-boundary-clean-reader``.  This
script never mutates the live backend, controls, output, release, Git,
network, credentials, or upstream authority.
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

import build_b025_boundary_clean_reader as prior


common = prior.common
ROOT = Path(__file__).resolve().parents[1]
BOUNDARY_ID = "R011-B026"
MODEL = "OpenAI Codex gpt-5.6-sol, Ultra"

SOURCE = ROOT / "scratch/b025-boundary-clean-reader-r2/source-snapshot"
BASE_READER = ROOT / "output/pdf/statistika-berbasis-data-batas-R011-B025.pdf"
BUILD = ROOT / "scratch/b026-boundary-clean-reader"
SNAPSHOT = BUILD / "source-snapshot"
RUN_A = BUILD / "replay-a"
RUN_B = BUILD / "replay-b"
FINAL = BUILD / "final"
FINAL_PDF = FINAL / "main.pdf"
FINAL_TEXT = FINAL / "main-final.txt"
MANIFEST = BUILD / "R011-B026_BOUNDARY_CLEAN_SOURCE_MANIFEST.tsv"
RECEIPT = FINAL / "R011-B026_BOUNDARY_CLEAN_BUILD_QA.json"

SOURCE_MAIN = SOURCE / "main_boundary_clean_b025.tex"
SOURCE_ANSWERS = (
    SOURCE / "extraTeX/eoceSolutions/eoceSolutions_boundary_clean_b025.tex"
)
SOURCE_CHAPTER = SOURCE / "ch_inference_for_means/TeX/ch_inference_for_means.tex"
SOURCE_EXERCISES = (
    SOURCE
    / "ch_inference_for_means/TeX/one-sample_means_with_the_t-distribution.tex"
)
SOURCE_DOLPHIN = (
    SOURCE / "ch_inference_for_means/figures/rissosDolphin/rissosDolphin.jpg"
)
SOURCE_DOLPHIN_RIGHTS = (
    SOURCE / "ch_inference_for_means/figures/rissosDolphin/ReadMe.txt"
)

CUSTOM_MAIN = SNAPSHOT / "main_boundary_clean_b026.tex"
CUSTOM_ANSWERS = (
    SNAPSHOT / "extraTeX/eoceSolutions/eoceSolutions_boundary_clean_b026.tex"
)
CUSTOM_CHAPTER = (
    SNAPSHOT / "ch_inference_for_means/TeX/ch_inference_for_means.tex"
)
CUSTOM_EXERCISES = (
    SNAPSHOT
    / "ch_inference_for_means/TeX/one-sample_means_with_the_t-distribution.tex"
)

STAGING = ROOT / "qa/b026-translation/staging"
CHAPTER_PARTS = (
    STAGING / "chapter-lines-1-231.id.tex",
    STAGING / "chapter-lines-232-400.id.tex",
    STAGING / "chapter-lines-401-633.id.tex",
    STAGING / "chapter-lines-634-796.id.tex",
    STAGING / "chapter-lines-797-896.id.tex",
    STAGING / "chapter-lines-897-1052.id.tex",
)
EXERCISES_ID = STAGING / "exercises-lines-1-280.id.tex"
ANSWERS_ID = STAGING / "public-answers-lines-1623-1721.id.tex"
O001_GAPS = STAGING / "R011-B026_O001_MASTERY_GAPS.json"
ASSET_STAGING = STAGING / "assets"

BLUEPRINT = ROOT / "qa/b026-source/R011-B026_BOUNDARY_BLUEPRINT.json"
MAIN_RECEIPTS = (
    ROOT / "qa/b026-translation/R011-B026_MAIN_TRANSLATION_PART_A_QA.json",
    ROOT / "qa/b026-translation/R011-B026_MAIN_TRANSLATION_PART_B_QA.json",
    ROOT / "qa/b026-translation/R011-B026_MAIN_TRANSLATION_PART_C_QA.json",
    ROOT / "qa/b026-translation/R011-B026_MAIN_TRANSLATION_PARTS_DE_QA.json",
    ROOT / "qa/b026-translation/R011-B026_MAIN_TRANSLATION_PART_F_QA.json",
)
EXERCISE_ANSWER_QA = (
    ROOT / "qa/b026-translation/R011-B026_EXERCISES_ANSWERS_QA.json"
)
ASSET_QA = ROOT / "qa/b026-translation/R011-B026_ASSET_LOCALIZATION_QA.json"
ASSET_ROOT_VISUAL_QA = (
    ROOT
    / "qa/b026-translation/"
    "R011-B026_ASSET_ROOT_VISUAL_INSPECTION_QA.json"
)

BASE_BUILD_QA = (
    ROOT
    / "scratch/b025-boundary-clean-reader-r2/final/"
    "R011-B025_BOUNDARY_CLEAN_BUILD_QA.json"
)
BASE_BACKEND_ADMISSION = (
    ROOT / "qa/b025-backend-admission/R011-B025_BACKEND_ADMISSION_RECEIPT.json"
)
BASE_PUBLIC_FINALIZATION = (
    ROOT
    / "qa/b025-publication-finalization/"
    "R011-B025_PUBLICATION_FINALIZATION_RECEIPT.json"
)
BASE_ZENODO_RECEIPT = (
    ROOT
    / "qa/b025-publication/"
    "ZENODO_PUBLICATION_RECEIPT_R011-B025-v2026.08.29.4.json"
)
BASE_GITHUB_RECEIPT = (
    ROOT
    / "release/b025/R011-B025-v2026.08.29.4/"
    "GITHUB_PUBLICATION_RECEIPT.json"
)

AUTHORITY_ROOT = (
    ROOT
    / "authority/upstream/"
    "openintro-statistics-fee25091fb24e89c36296fd67c48c1fcf7a93b6e"
)
AUTHORITY_MAIN = AUTHORITY_ROOT / "main.tex"
AUTHORITY_CHAPTER = (
    AUTHORITY_ROOT / "ch_inference_for_means/TeX/ch_inference_for_means.tex"
)
AUTHORITY_EXERCISES = (
    AUTHORITY_ROOT
    / "ch_inference_for_means/TeX/one-sample_means_with_the_t-distribution.tex"
)
AUTHORITY_ANSWERS = AUTHORITY_ROOT / "extraTeX/eoceSolutions/eoceSolutions.tex"

EXPECTED_BASE_SOURCE_FILE_COUNT = 1_220
EXPECTED_BASE_SOURCE_BYTES = 41_931_754
EXPECTED_BASE_SOURCE_INVENTORY_SHA256 = (
    "5bc7b2ab909843e7d145248572bdf5e92a56e6cf39f777ec0784b638e9a97b3e"
)

EXPECTED_BASE_FILES: dict[Path, tuple[int, str]] = {
    SOURCE_MAIN: (
        6_975,
        "b78062e3c52b583d8fbc2f313d9306019c11a87571003f85427ee22001138163",
    ),
    SOURCE_ANSWERS: (
        58_870,
        "cfa880914fec172b0359d74df3b60295f64531f13f10b752a115b7b42ffe6515",
    ),
    SOURCE_CHAPTER: (
        141_389,
        "d818b24b8e8d0582f8e603972e87764082d8470d91ddcbeaa794c295a1d37bec",
    ),
    SOURCE_EXERCISES: (
        10_225,
        "5d41cfe653f9da3e3b78885c23b3b2d30cd698a11087424fca1abc104de451ae",
    ),
    SOURCE_DOLPHIN: (
        72_046,
        "591d0ba9d9a228e58f2e8841536b826847f219d68cf791d6740986b7768ee200",
    ),
    SOURCE_DOLPHIN_RIGHTS: (
        119,
        "51903690d2b3cd10e69431292a345a08e321ac06d390252e852f4deef200088f",
    ),
}

EXPECTED_BASE_EVIDENCE: dict[Path, tuple[int, str]] = {
    BASE_READER: (
        12_440_420,
        "b154484d2d2ddf0a49f0ee9925854f45e86b6e0fb17d241607db9fc27051e99d",
    ),
    BASE_BUILD_QA: (
        21_393,
        "36f64b5447a9a87e03148b650d4cbec610e380393003b9c9860d46674eef01f0",
    ),
    BASE_BACKEND_ADMISSION: (
        1_233,
        "d833d0b15c6a87fcb4fdd835115d6a1a72d611e40de7af8cf1e62a4bcd23759e",
    ),
    BASE_PUBLIC_FINALIZATION: (
        1_880,
        "f71762d42425cda930cc2f8e5fb7e4b77c9296be24104dbe5817beb7a9ed4cde",
    ),
    BASE_ZENODO_RECEIPT: (
        2_392,
        "4e5a5c13bf9c611f0f2d7ad65d0b089f4e5eace1ac8237c5a8e3ad5dae7331f3",
    ),
    BASE_GITHUB_RECEIPT: (
        2_328,
        "16ffda0ce44adc6961e13611c9858aa60b2afdca021014bae1c9ba2c8264f2ee",
    ),
}

EXPECTED_AUTHORITY: dict[Path, tuple[int, str]] = {
    AUTHORITY_MAIN: (
        4_155,
        "1ed8952651f4b21e7175d82b4c1fda780aee5ec78f88143b97c692477ee2750b",
    ),
    AUTHORITY_CHAPTER: (
        141_389,
        "d818b24b8e8d0582f8e603972e87764082d8470d91ddcbeaa794c295a1d37bec",
    ),
    AUTHORITY_EXERCISES: (
        10_225,
        "5d41cfe653f9da3e3b78885c23b3b2d30cd698a11087424fca1abc104de451ae",
    ),
    AUTHORITY_ANSWERS: (
        106_045,
        "6c4e01376db4c023cc7b3f9949490e57220ef1cb831c580da71efde6ce723268",
    ),
}

EXPECTED_STAGING: dict[Path, tuple[int, str]] = {
    BLUEPRINT: (
        52_663,
        "2340adb156e7dd6833a2421eed9b6b4e2f7045e347f4fe8639544028cd6ced34",
    ),
    MAIN_RECEIPTS[0]: (
        5_830,
        "23a11d485ceb9aa651dfb80b09871591b9727438f1212401a66b388939c9da1e",
    ),
    MAIN_RECEIPTS[1]: (
        5_876,
        "e3ab079281be7693ab892063ee8b1af48e931894dfe93ff44fdb2fbf8043fd16",
    ),
    MAIN_RECEIPTS[2]: (
        9_483,
        "743d912b1c24d4435f52cad1bbb4443aa0ba35158a757f63ca9fb1e43bf91bb3",
    ),
    MAIN_RECEIPTS[3]: (
        11_421,
        "0cef972d46c4fbd6b07139e583e12d4bef0b57791773f6bdbbe2be6d9f17599d",
    ),
    MAIN_RECEIPTS[4]: (
        5_464,
        "2bfb273cc3f53337f3a19dccf03a1079faed6119ef6ccbb7b0c570ba404df507",
    ),
    EXERCISE_ANSWER_QA: (
        9_694,
        "263e1fbf5edb6f039614708ca896120d67e3c80fba3e97fbe8e272c0485a19ec",
    ),
    CHAPTER_PARTS[0]: (
        9_551,
        "f7ee09a6df0667faa82ac86cf032f4eb0477a29ca94c7f1bc676dad38fc96d34",
    ),
    CHAPTER_PARTS[1]: (
        7_094,
        "660ea8e51126b378c5b5ada70a365dc8111e0fa771de0bd979f8c017b2bcc7e4",
    ),
    CHAPTER_PARTS[2]: (
        10_675,
        "d50a78f6fbbf52a5007cd42929ea1dd3737b9cc3b8bf0aec5bca3a9a861b44b3",
    ),
    CHAPTER_PARTS[3]: (
        6_278,
        "bf908c142ee30f0b0e2a4d96b06c87d72ad941c7bba5af99d59786ee437c0613",
    ),
    CHAPTER_PARTS[4]: (
        3_804,
        "c56ea68a482ed32479d4a9968f6bbac4d117a2f68b0c8774709a9e505884773d",
    ),
    CHAPTER_PARTS[5]: (
        6_463,
        "d4ad6b2b445259ed72dae2e301d2956a9f61e22d7c28fc63981ba403d8248ceb",
    ),
    EXERCISES_ID: (
        10_409,
        "d84536e75f75f66d59a2021ea3a18dd3e51bf146a37445eebc67ed634c4c4b21",
    ),
    ANSWERS_ID: (
        3_247,
        "ba75f7b07e02b58f76ac25cfe3e0ef0b1c98a8eedc7a60b6d9d80faebc4ee73f",
    ),
    O001_GAPS: (
        5_723,
        "3664d3af33ea9c00fe50c45e83f977285f1c6446632eeaaf6821291f5102b78b",
    ),
}

EXPECTED_ASSET_QA: tuple[int, str] | None = (
    35_730,
    "b479bb7bdacda021bee1afd7380bfdea1c98915b1a693369d4a224216b48b9c1",
)
EXPECTED_ASSET_ROOT_VISUAL_QA = (
    3_636,
    "9c6a6bdd7683e98204c722e9ad9a70c873d0182e557681f07b1f3d0484eedbf0",
)
EXPECTED_ASSETS: dict[Path, tuple[int, str]] = {
    ASSET_STAGING / "outliers_and_ss_condition.id.pdf": (
        11_338,
        "5efbf4b8f972c938df3b27e0fb281f7b00269e178dceb0673d09bdf61e0fbcdf",
    ),
    ASSET_STAGING / "tDistCompareToNormalDist.id.pdf": (
        52_105,
        "09ba1c4a8edbebcb4d7108810244f9442aba69e0fd0ce9d8a0528c544d37e186",
    ),
    ASSET_STAGING / "tDistConvergeToNormalDist.id.pdf": (
        65_026,
        "b0e9bfcbcf886b710d1960c1005859429f174728c1384633afd572a22be1a0e0",
    ),
    ASSET_STAGING / "tDistDF18LeftTail2Point10.id.pdf": (
        13_307,
        "7ad8aa77c0e94a6ddfd375c35ab4cd0ececcb7c5f917a3c96d731243191f15ba",
    ),
    ASSET_STAGING / "tDistDF20RightTail1Point65.id.pdf": (
        25_786,
        "11ce38a736c383f883a355f79fe1aeabcaa26e3feee540e740c266b31f95b3db",
    ),
    ASSET_STAGING / "run17SampTimeHistogram.id.pdf": (
        7_629,
        "7ce6972438b8a32f504bcb14a0c90111460a1e47e9dc1d2b991aa1ce02229f1a",
    ),
    ASSET_STAGING / "t_distribution.id.pdf": (
        60_191,
        "52ecac753c4b469c93ac6eff52563d417db86eebd6aa20d9087b1146c203fe92",
    ),
    ASSET_STAGING / "adult_heights_hist.id.pdf": (
        8_023,
        "9fe6bfbcee89f0415ead39e800e9f2979b6f96f435e58681cb4bd1bdb537abd1",
    ),
}

ASSET_TARGETS: dict[Path, Path] = {
    ASSET_STAGING / "outliers_and_ss_condition.id.pdf": Path(
        "ch_inference_for_means/figures/outliers_and_ss_condition/"
        "outliers_and_ss_condition.pdf"
    ),
    ASSET_STAGING / "tDistCompareToNormalDist.id.pdf": Path(
        "ch_inference_for_means/figures/tDistCompareToNormalDist/"
        "tDistCompareToNormalDist.pdf"
    ),
    ASSET_STAGING / "tDistConvergeToNormalDist.id.pdf": Path(
        "ch_inference_for_means/figures/tDistConvergeToNormalDist/"
        "tDistConvergeToNormalDist.pdf"
    ),
    ASSET_STAGING / "tDistDF18LeftTail2Point10.id.pdf": Path(
        "ch_inference_for_means/figures/tDistDF18LeftTail2Point10/"
        "tDistDF18LeftTail2Point10.pdf"
    ),
    ASSET_STAGING / "tDistDF20RightTail1Point65.id.pdf": Path(
        "ch_inference_for_means/figures/tDistDF20RightTail1Point65/"
        "tDistDF20RightTail1Point65.pdf"
    ),
    ASSET_STAGING / "run17SampTimeHistogram.id.pdf": Path(
        "ch_inference_for_means/figures/run10SampTimeHistogram/"
        "run17SampTimeHistogram.pdf"
    ),
    ASSET_STAGING / "t_distribution.id.pdf": Path(
        "ch_inference_for_means/figures/eoce/t_distribution/"
        "t_distribution.pdf"
    ),
    ASSET_STAGING / "adult_heights_hist.id.pdf": Path(
        "ch_inference_for_means/figures/eoce/adult_heights/"
        "adult_heights_hist.pdf"
    ),
}

MAIN_PART_STATUSES = (
    "PASS_COMPLETE_NATURAL_ID_ID_STRUCTURE_MATH_PROTECTED_TEX_AND_RESIDUAL_ENGLISH_QA",
    "PASS_COMPLETE_NATURAL_ID_ID_STRUCTURE_MATH_PROTECTED_TEX_REPAIR_LEDGER_AND_RESIDUAL_ENGLISH_QA",
    "PASS_COMPLETE_NATURAL_ID_ID_STRUCTURE_MATH_PROTECTED_TEX_APPROVED_REPAIR_AND_RESIDUAL_ENGLISH_QA",
    "PASS_COMPLETE_NATURAL_ID_ID_STRUCTURE_MATH_PROTECTED_TEX_APPROVED_REPAIR_AND_RESIDUAL_ENGLISH_QA",
    "PASS_COMPLETE_NATURAL_ID_ID_STRUCTURE_MATH_PROTECTED_TEX_REPAIR_LEDGER_AND_RESIDUAL_ENGLISH_QA",
)
EXERCISE_ANSWER_STATUS = (
    "PASS_COMPLETE_NATURAL_ID_ID_EXERCISE_ANSWER_CLOSURE_STRUCTURE_MATH_"
    "REPAIRS_AND_RESIDUAL_ENGLISH_QA"
)

SCOPE_B025 = r"""\chapter*{Cakupan edisi parsial ini}
\addcontentsline{toc}{chapter}{Cakupan edisi parsial ini}
Pembaca ini berhenti tepat setelah Bagian~6.4,
\emph{Menguji independensi dalam tabel dua arah}. Cakupan Bab~6 dalam
edisi ini memuat latihan 1--38. Semua jawaban publik yang tersedia dari
sumber disertakan, yaitu jawaban bernomor ganjil 1--37. Jawaban bernomor
genap 2--38 memang tidak tersedia dalam sumber publik; jawaban-jawaban itu
dicatat sebagai kesenjangan pendamping kemahiran O001 dan tidak direka."""

SCOPE_B026 = r"""\chapter*{Cakupan edisi parsial ini}
\addcontentsline{toc}{chapter}{Cakupan edisi parsial ini}
Pembaca ini berhenti tepat setelah Bagian~7.1,
\emph{Rata-rata satu sampel dengan distribusi t}. Cakupan Bab~7 dalam
edisi ini memuat latihan 1--14. Semua jawaban publik yang tersedia dari
sumber disertakan, yaitu jawaban bernomor ganjil 1--13. Jawaban bernomor
genap 2--14 memang tidak tersedia dalam sumber publik; jawaban-jawaban itu
dicatat sebagai kesenjangan pendamping kemahiran O001 dan tidak direka."""

OLD_BOUNDARY_NOTE = "% Boundary-clean learner reader through Chapter 6, Section 6.4."
NEW_BOUNDARY_NOTE = "% Boundary-clean learner reader through Chapter 7, Section 7.1."
OLD_ANSWER_INCLUDE = (
    r"\include{extraTeX/eoceSolutions/eoceSolutions_boundary_clean_b025}"
)
NEW_ANSWER_INCLUDE = (
    r"\include{extraTeX/eoceSolutions/eoceSolutions_boundary_clean_b026}"
)
OLD_CHAPTER_6_INPUT = r"\input{ch_inference_for_props/TeX/ch_inference_for_props}"
CHAPTER_7_BLOCK = "\n".join(
    (
        r"\setcounter{chapter}{7}",
        r"\addtocounter{chapter}{-1}",
        r"\normalsize",
        r"\input{ch_inference_for_means/TeX/ch_inference_for_means}",
    )
)
OLD_STUBS = "\n".join(
    (
        r"\label{ch_inference_for_means}",
        r"\label{oneSampleMeansWithTDistribution}",
    )
)
APPENDIX_STUB_ANCHOR = r"\label{chiSquareProbabilityTable}"
NEW_APPENDIX_STUBS = "\n".join(
    (
        APPENDIX_STUB_ANCHOR,
        r"\label{tDistributionTable}",
    )
)
LATER_NAV = "\n".join(
    (
        r"  \chaptersection{pairedData}",
        r"  \chaptersection{differenceOfTwoMeans}",
        r"  \chaptersection{PowerForDifferenceOfTwoMeans}",
        r"  \chaptersection{anovaAndRegrWithCategoricalVariables}",
    )
)
BOUNDARY_NAV_NOTE = (
    "% Boundary-clean reader omits navigation to excluded later Chapter 7 sections."
)
ANSWER_525_FORCED_TRANSITION = "\n".join(
    (
        r"\end{multicols}",
        r"\newpage",
        r"\begin{multicols}{2}",
        "",
        r"% 25",
        "",
        r"\eocesol{(a)~$H_0$: Antidepresan",
    )
)
ANSWER_525_REFLOW = "\n".join(
    (
        "% Boundary-clean reflow: keep the short public answer 5.25 in the",
        "% existing two-column stream instead of forcing a mostly blank page.",
        r"% 25",
        "",
        r"\eocesol{(a)~$H_0$: Antidepresan",
    )
)
ANSWER_637_FORCED_TRANSITION = "\n".join(
    (
        r"\end{multicols}",
        r"\newpage",
        r"\begin{multicols}{2}",
        "",
        r"% 37",
        "",
        r"\eocesol{$H_0$: Pendapat lulusan dan bukan lulusan perguruan tinggi tidak berbeda mengenai ",
    )
)
ANSWER_637_REFLOW = "\n".join(
    (
        "% Boundary-clean reflow: keep public answer 6.37 in the already-open",
        "% Chapter 6 two-column stream; the later Chapter 6 close is retained.",
        r"% 37",
        "",
        r"\eocesol{$H_0$: Pendapat lulusan dan bukan lulusan perguruan tinggi tidak berbeda mengenai ",
    )
)
ANSWER_79_FORCED_TRANSITION = "\n".join(
    (
        r"\end{multicols}",
        r"\newpage",
        r"\begin{multicols}{2}",
        "",
        r"% 9",
        "",
        r"\eocesol{$T$ adalah -2.09 atau 2.09.",
    )
)
ANSWER_79_REFLOW = "\n".join(
    (
        "% Boundary-clean reflow: keep public answers 7.9-7.13 in the",
        "% already-open Chapter 7 two-column stream; the final close is retained.",
        r"% 9",
        "",
        r"\eocesol{$T$ adalah -2.09 atau 2.09.",
    )
)

FORBIDDEN_READER_ENGLISH = (
    "Inference for numerical data",
    "One-sample means with the t-distribution",
    "Paired data",
    "Difference of two means",
    "Power for the difference of two means",
    "ANOVA and regression with categorical variables",
    "Introducing the t distribution",
    "Central Limit Theorem for sample means",
    "A first look at inference for the mean",
    "Conditions for the t distribution",
    "One sample t confidence intervals",
    "One sample t hypothesis tests",
    "Identify the critical t",
    "An independent random sample",
    "Find the p-value",
    "Working backwards",
    "Sleep habits of New Yorkers",
    "Heights of adults",
    "Car insurance savings",
    "SAT scores",
    "Frequency",
    "Sample 1 Observations",
    "Sample 2 Observations",
    "Time (Minutes)",
    "solid",
    "dashed",
    "dotted",
)


def normalized_lf(path: Path) -> str:
    return prior.normalized_lf(path)


def memory_identity(name: str, value: str) -> dict[str, Any]:
    return prior.memory_identity(name, value)


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    common.require(
        isinstance(value, dict),
        f"JSON root is not an object: {common.rel(path)}",
    )
    return value


def verify_b025_base() -> dict[str, Any]:
    common.require(SOURCE.is_dir(), "sealed B025 source snapshot absent")
    inventory = common.source_inventory(SOURCE)
    common.require(
        inventory["files"] == EXPECTED_BASE_SOURCE_FILE_COUNT,
        "B025 source snapshot file count changed",
    )
    common.require(
        inventory["bytes"] == EXPECTED_BASE_SOURCE_BYTES,
        "B025 source snapshot byte count changed",
    )
    common.require(
        inventory["inventory_sha256"] == EXPECTED_BASE_SOURCE_INVENTORY_SHA256,
        "B025 source snapshot inventory changed",
    )
    for path, expected in EXPECTED_BASE_FILES.items():
        common.require_exact(path, expected)
    for path, expected in EXPECTED_BASE_EVIDENCE.items():
        common.require_exact(path, expected)

    reader = PdfReader(BASE_READER)
    common.require(len(reader.pages) == 260, "stable B025 reader page count changed")

    build = _json(BASE_BUILD_QA)
    admission = _json(BASE_BACKEND_ADMISSION)
    finalization = _json(BASE_PUBLIC_FINALIZATION)
    zenodo = _json(BASE_ZENODO_RECEIPT)
    github = _json(BASE_GITHUB_RECEIPT)
    common.require(
        build.get("boundary_id") == "R011-B025"
        and build.get("status")
        == "PASS_TWO_REPLAY_DETERMINISTIC_BOUNDARY_CLEAN_BUILD_LANGUAGE_QA_COMPLETE_READER_VISUAL_QA_PENDING"
        and build.get("page_count") == 260
        and build.get("candidate_artifact", {}).get("sha256")
        == EXPECTED_BASE_EVIDENCE[BASE_READER][1],
        "B025 deterministic build receipt changed",
    )
    common.require(
        admission.get("boundary_id") == "R011-B025"
        and admission.get("status")
        == "PASS_B025_BACKEND_ATOMIC_ADMISSION_AND_EXACT_REPLAY",
        "B025 backend admission changed",
    )
    common.require(
        finalization.get("boundary_id") == "R011-B025"
        and finalization.get("status")
        == "PASS_B025_PUBLICATION_FINALIZED_CONTROLS_ADVANCED_TO_B026",
        "B025 publication finalization changed",
    )
    common.require(
        zenodo.get("status") == "PUBLISHED_AND_ANONYMOUSLY_VERIFIED"
        and zenodo.get("doi") == "10.5281/zenodo.22166545"
        and zenodo.get("concept_doi") == "10.5281/zenodo.22059801"
        and zenodo.get("access_right") == "open"
        and zenodo.get("anonymous_public_byte_readback") is True,
        "B025 Zenodo public readback changed",
    )
    common.require(
        github.get("status") == "PUBLISHED_AND_ANONYMOUSLY_VERIFIED"
        and github.get("tag") == "r011-b025-2026.08.29.4"
        and github.get("repository_public") is True
        and github.get("anonymous_public_byte_readback") is True,
        "B025 GitHub public readback changed",
    )
    return {
        "source_snapshot": {
            key: inventory[key]
            for key in ("files", "bytes", "inventory_sha256")
        },
        "stable_reader": {**common.identity(BASE_READER), "pages": 260},
        "build_qa": common.identity(BASE_BUILD_QA),
        "backend_admission": common.identity(BASE_BACKEND_ADMISSION),
        "public_finalization": common.identity(BASE_PUBLIC_FINALIZATION),
        "zenodo_public_readback": {
            **common.identity(BASE_ZENODO_RECEIPT),
            "doi": zenodo["doi"],
            "concept_doi": zenodo["concept_doi"],
        },
        "github_public_readback": {
            **common.identity(BASE_GITHUB_RECEIPT),
            "tag": github["tag"],
        },
    }


def verify_blueprint() -> dict[str, Any]:
    common.require_exact(BLUEPRINT, EXPECTED_STAGING[BLUEPRINT])
    blueprint = _json(BLUEPRINT)
    common.require(blueprint.get("boundary_id") == BOUNDARY_ID, "B026 blueprint boundary changed")
    common.require(
        blueprint.get("status")
        == "PASS_SOURCE_ASSET_DATA_RIGHTS_AND_BOOK_ORDER_DEPENDENCY_CLOSURE",
        "B026 source/assets/data/rights closure did not pass",
    )
    authority = blueprint.get("authority", {})
    common.require(
        authority.get("commit") == "fee25091fb24e89c36296fd67c48c1fcf7a93b6e"
        and authority.get("tree") == "d61cc601e7d97759ce805900520f784d02a0489e"
        and authority.get("branch_observed") == "master",
        "B026 authority pin changed",
    )
    main = blueprint.get("main_source", {})
    common.require(
        main.get("boundary_start_line") == 1
        and main.get("end_line") == 1052
        and main.get("start_label") == "oneSampleMeansWithTDistribution"
        and main.get("source_file_ends_at_boundary") is False
        and main.get("slice", {}).get("logical_lines") == 1052
        and main.get("slice", {}).get("bytes") == 43_121
        and main.get("slice", {}).get("sha256")
        == "bf59f75713c353c0ae167547cbbd3cef5ebcdbf1a21a15d8e26b0f5be1844dc2",
        "B026 main boundary changed",
    )
    closure = blueprint.get("exercise_answer_closure", {})
    common.require(
        closure.get("chapter_exercise_ids") == list(range(1, 15))
        and closure.get("public_answer_ids") == list(range(1, 14, 2))
        and closure.get("o001_gap_ids") == list(range(2, 15, 2))
        and closure.get("restricted_solutions_accessed_or_invented") is False,
        "B026 exercise/answer/O001 closure changed",
    )
    production = blueprint.get("production_closure", {})
    common.require(
        production.get("main_source_lines") == 1052
        and production.get("end_of_section_exercises") == 14
        and production.get("public_answers") == 7
        and production.get("o001_gaps") == 7
        and production.get("distinct_reader_binary_assets") == 9
        and production.get("committed_generated_reader_pdfs") == 8
        and production.get("photographic_reader_assets") == 1,
        "B026 production closure changed",
    )
    cursor = blueprint.get("post_boundary_cursor", {})
    common.require(
        cursor.get("line") == 1059
        and cursor.get("section_label") == "pairedData"
        and cursor.get("working_boundary_id") == "R011-B027",
        "B026 post-boundary cursor changed",
    )
    figures = blueprint.get("figure_asset_closure", [])
    common.require(len(figures) == 9, "B026 figure closure count changed")
    dolphin = [item for item in figures if item.get("path", "").endswith("rissosDolphin.jpg")]
    common.require(
        len(dolphin) == 1
        and dolphin[0].get("rights_resolution") == "CC-BY-2.0"
        and "Mike Baird" in dolphin[0].get("required_attribution", ""),
        "B026 dolphin rights closure changed",
    )
    for path, expected in EXPECTED_AUTHORITY.items():
        common.require_exact(path, expected)
    return {
        "blueprint": common.identity(BLUEPRINT),
        "authority_commit": authority["commit"],
        "authority_tree": authority["tree"],
        "main_source_slice": main["slice"],
        "exercise_ids": closure["chapter_exercise_ids"],
        "public_answer_ids": closure["public_answer_ids"],
        "o001_gap_ids": closure["o001_gap_ids"],
        "figure_asset_count": len(figures),
        "post_boundary_cursor": cursor,
    }


def verify_translation_receipts() -> dict[str, Any]:
    for path, expected in EXPECTED_STAGING.items():
        common.require_exact(path, expected)
    receipt_rows: list[dict[str, Any]] = []
    for path, expected_status in zip(MAIN_RECEIPTS, MAIN_PART_STATUSES):
        value = _json(path)
        common.require(
            value.get("boundary_id") == BOUNDARY_ID
            and value.get("status") == expected_status,
            f"B026 main translation receipt changed: {common.rel(path)}",
        )
        guards = value.get("scope_guards", {})
        common.require(
            guards.get("canonical_source_mutated") is False
            and guards.get("live_backend_mutated") is False
            and guards.get("git_used") is False
            and guards.get("network_used") is False
            and guards.get("upstream_contact") is False,
            f"B026 main receipt scope guard changed: {common.rel(path)}",
        )
        receipt_rows.append({**common.identity(path), "status": value["status"]})

    exercise_receipt = _json(EXERCISE_ANSWER_QA)
    common.require(
        exercise_receipt.get("boundary_id") == BOUNDARY_ID
        and exercise_receipt.get("status") == EXERCISE_ANSWER_STATUS,
        "B026 exercise/answer QA receipt changed",
    )
    closure = exercise_receipt.get("closure", {})
    common.require(
        closure.get("exercise_ids") == list(range(1, 15))
        and closure.get("public_answer_ids") == list(range(1, 14, 2))
        and closure.get("o001_even_gap_ids") == list(range(2, 15, 2))
        and closure.get("restricted_solution_material_included") is False,
        "B026 exercise/answer receipt closure changed",
    )
    o001 = _json(O001_GAPS)
    common.require(
        o001.get("boundary_id") == BOUNDARY_ID
        and o001.get("status")
        == "EXPLICIT_O001_GAPS_RECORDED_NO_RESTRICTED_SOLUTIONS_ACCESSED_OR_INVENTED"
        and o001.get("public_answers_present") == list(range(1, 14, 2))
        and o001.get("o001_gap_ids") == list(range(2, 15, 2))
        and o001.get("restricted_solutions_accessed_or_invented") is False,
        "B026 O001 gap ledger changed",
    )

    expected_lines = (231, 169, 233, 163, 100, 156)
    for path, count in zip(CHAPTER_PARTS, expected_lines):
        common.require(
            len(normalized_lf(path).splitlines()) == count,
            f"B026 staged main line count changed: {common.rel(path)}",
        )
    common.require(
        sum(expected_lines) == 1052,
        "internal B026 main chunk accounting changed",
    )
    common.require(
        len(normalized_lf(EXERCISES_ID).splitlines()) == 280,
        "B026 exercise line count changed",
    )
    common.require(
        len(normalized_lf(ANSWERS_ID).splitlines()) == 99,
        "B026 public-answer line count changed",
    )
    return {
        "main_receipts": receipt_rows,
        "exercise_answer_receipt": {
            **common.identity(EXERCISE_ANSWER_QA),
            "status": exercise_receipt["status"],
        },
        "main_fragments": [common.identity(path) for path in CHAPTER_PARTS],
        "exercises": common.identity(EXERCISES_ID),
        "public_answers": common.identity(ANSWERS_ID),
        "o001_gap_ledger": common.identity(O001_GAPS),
    }


def asset_gate_probe() -> dict[str, Any]:
    present = [path for path in ASSET_TARGETS if path.is_file()]
    ready = (
        EXPECTED_ASSET_QA is not None
        and len(EXPECTED_ASSETS) == len(ASSET_TARGETS) == 8
        and ASSET_QA.is_file()
        and len(present) == 8
    )
    return {
        "ready": ready,
        "receipt_present": ASSET_QA.is_file(),
        "expected_identities_configured": (
            EXPECTED_ASSET_QA is not None and len(EXPECTED_ASSETS) == 8
        ),
        "present_asset_count": len(present),
        "required_asset_count": 8,
        "present_assets": [common.rel(path) for path in present],
        "missing_assets": [
            common.rel(path) for path in ASSET_TARGETS if not path.is_file()
        ],
    }


def verify_asset_gate() -> dict[str, Any]:
    common.require(
        EXPECTED_ASSET_QA is not None,
        "B026 asset receipt identity is not configured",
    )
    common.require(
        len(EXPECTED_ASSETS) == len(ASSET_TARGETS) == 8,
        "B026 localized asset identity map is incomplete",
    )
    common.require_exact(ASSET_QA, EXPECTED_ASSET_QA)
    common.require_exact(ASSET_ROOT_VISUAL_QA, EXPECTED_ASSET_ROOT_VISUAL_QA)
    for path, expected in EXPECTED_ASSETS.items():
        common.require(path in ASSET_TARGETS, "unexpected B026 staged asset configured")
        common.require_exact(path, expected)
        common.require(len(PdfReader(path).pages) == 1, f"localized asset is not one-page PDF: {common.rel(path)}")
    receipt = _json(ASSET_QA)
    common.require(receipt.get("boundary_id") == BOUNDARY_ID, "B026 asset receipt boundary changed")
    status = str(receipt.get("status", ""))
    common.require(
        status == "PASS_DETERMINISTIC_ASSET_LOCALIZATION_AND_VISUAL_QA",
        "B026 asset localization QA did not pass",
    )
    inventory = receipt.get("output_inventory", {})
    common.require(
        inventory.get("files") == 8
        and inventory.get("bytes") == 243_405
        and inventory.get("inventory_sha256")
        == "d8da29bb513ba4d30ceb2d0aab4504bea8c1b8b1a766a41a74e658446c186558",
        "B026 asset output inventory changed",
    )
    receipt_outputs = {
        str(item.get("output", {}).get("path")): (
            item.get("output", {}).get("bytes"),
            item.get("output", {}).get("sha256"),
        )
        for item in receipt.get("artifacts", [])
    }
    common.require(len(receipt_outputs) == 8, "B026 asset receipt artifact count changed")
    for path, expected in EXPECTED_ASSETS.items():
        common.require(
            receipt_outputs.get(common.rel(path)) == expected,
            f"B026 asset receipt output binding changed: {common.rel(path)}",
        )
    visual = _json(ASSET_ROOT_VISUAL_QA)
    common.require(
        visual.get("boundary_id") == BOUNDARY_ID
        and visual.get("status")
        == "PASS_ALL_8_LOCALIZED_ASSETS_VISUALLY_INSPECTED_AFTER_ONE_CORRECTION_ZERO_REMAINING_DEFECTS"
        and visual.get("asset_localization_receipt", {}).get("sha256")
        == EXPECTED_ASSET_QA[1]
        and visual.get("checks", {}).get("clipping_or_overlap") is False
        and visual.get("checks", {}).get("remaining_visible_english_label_defects") is False
        and visual.get("dolphin_photo", {}).get("source_sha256")
        == EXPECTED_BASE_FILES[SOURCE_DOLPHIN][1],
        "B026 independent root asset visual receipt changed",
    )
    return {
        "receipt": {**common.identity(ASSET_QA), "status": status},
        "root_visual_receipt": {
            **common.identity(ASSET_ROOT_VISUAL_QA),
            "status": visual["status"],
        },
        "output_inventory": inventory,
        "assets": [
            {
                **common.identity(path),
                "install_target": target.as_posix(),
            }
            for path, target in ASSET_TARGETS.items()
        ],
    }


def prepare_custom_texts() -> tuple[dict[Path, str], dict[str, Any]]:
    main = normalized_lf(SOURCE_MAIN)
    common.require(main.count(SCOPE_B025) == 1, "B025 scope block changed")
    main = main.replace(SCOPE_B025, SCOPE_B026)
    common.require(main.count(OLD_BOUNDARY_NOTE) == 1, "B025 boundary note changed")
    main = main.replace(OLD_BOUNDARY_NOTE, NEW_BOUNDARY_NOTE)
    common.require(main.count(OLD_ANSWER_INCLUDE) == 1, "B025 answer include changed")
    main = main.replace(OLD_ANSWER_INCLUDE, NEW_ANSWER_INCLUDE)
    common.require(main.count(OLD_STUBS) == 1, "B025 Chapter 7 stubs changed")
    main = main.replace(OLD_STUBS, "")
    common.require(
        main.count(APPENDIX_STUB_ANCHOR) == 1,
        "B025 appendix stub anchor changed",
    )
    main = main.replace(APPENDIX_STUB_ANCHOR, NEW_APPENDIX_STUBS, 1)
    common.require(main.count(OLD_CHAPTER_6_INPUT) == 1, "B025 Chapter 6 input changed")
    main = main.replace(
        OLD_CHAPTER_6_INPUT,
        OLD_CHAPTER_6_INPUT + "\n" + CHAPTER_7_BLOCK,
        1,
    )
    common.require(main.count(CHAPTER_7_BLOCK) == 1, "B026 Chapter 7 input insertion failed")
    common.require(
        r"\input{ch_regr_simple_linear/TeX/ch_regr_simple_linear}" not in main
        and r"\includechapter{8}{ch_regr_simple_linear}" not in main,
        "Chapter 8 source carry-through entered B026 main",
    )

    chapter_fragments = [normalized_lf(path) for path in CHAPTER_PARTS]
    common.require(
        all(fragment.endswith("\n") for fragment in chapter_fragments),
        "B026 main fragment lacks terminal LF",
    )
    chapter = "".join(chapter_fragments)
    common.require(
        len(chapter.splitlines()) == 1052,
        "assembled B026 main does not contain exact source-order line closure",
    )
    common.require(chapter.count(LATER_NAV) == 1, "B026 later-section navigation changed")
    chapter = chapter.replace(LATER_NAV, BOUNDARY_NAV_NOTE, 1)
    common.require(
        chapter.count(r"\chaptersection{oneSampleMeansWithTDistribution}") == 1,
        "B026 retained Chapter 7 navigation changed",
    )
    common.require(
        all(
            marker not in chapter
            for marker in (
                r"\chaptersection{pairedData}",
                r"\chaptersection{differenceOfTwoMeans}",
                r"\chaptersection{PowerForDifferenceOfTwoMeans}",
                r"\chaptersection{anovaAndRegrWithCategoricalVariables}",
                r"\label{pairedData}",
            )
        ),
        "excluded later Chapter 7 navigation or source entered assembled chapter",
    )
    common.require(
        chapter.count(r"\label{ch_inference_for_means}") == 1
        and chapter.count(r"\label{oneSampleMeansWithTDistribution}") == 1
        and chapter.count(
            r"\input{ch_inference_for_means/TeX/one-sample_means_with_the_t-distribution.tex}"
        )
        == 1,
        "B026 chapter labels or exercise input changed",
    )
    common.require("\n\\section" not in chapter[chapter.rfind(r"\CalculatorVideos") :], "untranslated post-boundary section entered B026 chapter")

    exercises = normalized_lf(EXERCISES_ID)
    exercise_numbers = [
        int(value) for value in re.findall(r"(?m)^% (\d+)\s*$", exercises)
    ]
    common.require(exercise_numbers == list(range(1, 15)), "B026 exercise sequence changed")
    common.require(exercises.count(r"\eoce{") == 14, "B026 exercise count changed")

    old_answers = normalized_lf(SOURCE_ANSWERS)
    final_close = "\\end{multicols}\n"
    common.require(old_answers.endswith(final_close), "B025 answer close anchor changed")
    staged_answers = normalized_lf(ANSWERS_ID)
    common.require(staged_answers.startswith("%_______________\n\\end{multicols}\n"), "B026 public-answer opening transition changed")
    answers = (
        old_answers[: -len(final_close)]
        + staged_answers
        + "\n"
        + final_close
    )
    common.require(
        answers.count(ANSWER_525_FORCED_TRANSITION) == 1,
        "legacy forced transition before public answer 5.25 changed",
    )
    answers = answers.replace(
        ANSWER_525_FORCED_TRANSITION,
        ANSWER_525_REFLOW,
        1,
    )
    common.require(
        answers.count(ANSWER_637_FORCED_TRANSITION) == 1,
        "legacy forced transition before public answer 6.37 changed",
    )
    answers = answers.replace(
        ANSWER_637_FORCED_TRANSITION,
        ANSWER_637_REFLOW,
        1,
    )
    common.require(
        answers.count(ANSWER_79_FORCED_TRANSITION) == 1,
        "legacy forced transition before public answer 7.9 changed",
    )
    answers = answers.replace(
        ANSWER_79_FORCED_TRANSITION,
        ANSWER_79_REFLOW,
        1,
    )
    common.require(
        answers.count(r"\begin{multicols}{2}")
        == answers.count(r"\end{multicols}"),
        "assembled B026 answer columns unbalanced",
    )
    answer_numbers = [
        int(value) for value in re.findall(r"(?m)^% (\d+)\s*$", staged_answers)
    ]
    common.require(answer_numbers == list(range(1, 14, 2)), "B026 answer sequence changed")

    custom = {
        CUSTOM_MAIN: main,
        CUSTOM_CHAPTER: chapter,
        CUSTOM_EXERCISES: exercises,
        CUSTOM_ANSWERS: answers,
    }
    transforms = {
        "scope_updated": "through Chapter 7, Section 7.1",
        "chapter_7_inserted_after_chapter_6": True,
        "chapter_7_source_lines_admitted": "1-1052 inclusive",
        "later_chapter_7_navigation_removed": [
            "pairedData",
            "differenceOfTwoMeans",
            "PowerForDifferenceOfTwoMeans",
            "anovaAndRegrWithCategoricalVariables",
        ],
        "old_chapter_7_stub_labels_removed": [
            "ch_inference_for_means",
            "oneSampleMeansWithTDistribution",
        ],
        "excluded_appendix_reference_stub_added": "tDistributionTable",
        "exercise_closure": list(range(1, 15)),
        "public_answer_closure": list(range(1, 14, 2)),
        "o001_gap_closure": list(range(2, 15, 2)),
        "legacy_answer_5_25_forced_page_and_column_restart_removed": True,
        "legacy_answer_6_37_forced_page_and_column_restart_removed": True,
        "legacy_answer_7_9_forced_page_and_column_restart_removed": True,
        "localized_or_corrected_pdf_assets_installed": 8,
        "rissos_dolphin_retained_byte_identical": True,
        "rissos_dolphin_attribution": (
            "Photo by Mike Baird (http://www.bairdphotos.com/); "
            "Creative Commons Attribution 2.0 Generic"
        ),
        "translation_staging_mutated": False,
        "later_source_counted_as_learner_output": False,
        "restricted_solutions_accessed_or_invented": False,
    }
    return custom, transforms


def install_assets() -> dict[str, Any]:
    gate = verify_asset_gate()
    installed: list[dict[str, Any]] = []
    for staged, relative_target in ASSET_TARGETS.items():
        target = SNAPSHOT / relative_target
        before = common.identity(target)
        shutil.copy2(staged, target)
        after = common.identity(target)
        common.require(
            (after["bytes"], after["sha256"]) == EXPECTED_ASSETS[staged],
            f"localized B026 asset copy differs: {common.rel(staged)}",
        )
        installed.append({
            "source": common.identity(staged),
            "target": after,
            "replaced": before,
        })
    common.require_exact(SNAPSHOT / SOURCE_DOLPHIN.relative_to(SOURCE), EXPECTED_BASE_FILES[SOURCE_DOLPHIN])
    common.require_exact(
        SNAPSHOT / SOURCE_DOLPHIN_RIGHTS.relative_to(SOURCE),
        EXPECTED_BASE_FILES[SOURCE_DOLPHIN_RIGHTS],
    )
    return {
        **gate,
        "installed": installed,
        "rissos_dolphin": {
            **common.identity(SNAPSHOT / SOURCE_DOLPHIN.relative_to(SOURCE)),
            "byte_identical_to_b025_and_upstream": True,
            "rights": "CC BY 2.0",
            "attribution": (
                "Photo by Mike Baird (http://www.bairdphotos.com/); "
                "Creative Commons Attribution 2.0 Generic"
            ),
            "rights_witness": common.identity(
                SNAPSHOT / SOURCE_DOLPHIN_RIGHTS.relative_to(SOURCE)
            ),
        },
    }


def make_custom_sources() -> dict[str, Any]:
    texts, transforms = prepare_custom_texts()
    for path, value in texts.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding="utf-8", newline="\n")
    assets = install_assets()
    return {
        "custom_main": common.identity(CUSTOM_MAIN),
        "custom_chapter_7_through_section_7_1": common.identity(CUSTOM_CHAPTER),
        "custom_exercises_1_14": common.identity(CUSTOM_EXERCISES),
        "custom_answers_1_14_public_odd": common.identity(CUSTOM_ANSWERS),
        "assets": assets,
        "assembly_transformations": transforms,
    }


def write_manifest() -> dict[str, Any]:
    inventory = common.source_inventory(SNAPSHOT)
    raw = "".join(
        f"{name}\t{size}\t{digest}\n"
        for name, size, digest in inventory.pop("rows")
    ).encode("utf-8")
    MANIFEST.write_bytes(raw)
    result = {**common.identity(MANIFEST), **inventory}
    common.require(result["files"] == 1_222, "B026 source snapshot file count changed")
    return result


def build_once(
    label: str,
    directory: Path,
    tools: dict[str, str],
    seed: str,
) -> dict[str, Any]:
    common.require(not directory.exists(), f"refusing to overwrite replay: {common.rel(directory)}")
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
        rf"\pdftrailerid{{<{seed}><{seed}>}}\input{{main_boundary_clean_b026.tex}}",
    ]
    common.run_logged(latex, SNAPSHOT, directory / "console-pass1.txt", env)
    common.run_logged([tools["bibtex"], "main"], directory, directory / "console-bibtex.txt", env)
    common.run_logged([tools["makeindex"], "main.idx"], directory, directory / "console-makeindex1.txt", env)
    common.run_logged(latex, SNAPSHOT, directory / "console-pass2.txt", env)
    common.run_logged([tools["makeindex"], "main.idx"], directory, directory / "console-makeindex2.txt", env)
    common.run_logged(latex, SNAPSHOT, directory / "console-pass3.txt", env)
    pdf = directory / "main.pdf"
    common.require(pdf.is_file(), f"{label} produced no PDF")
    pass3 = directory / "main-pass3.pdf"
    shutil.copy2(pdf, pass3)
    common.run_logged([tools["makeindex"], "main.idx"], directory, directory / "console-makeindex3.txt", env)
    common.run_logged(latex, SNAPSHOT, directory / "console-pass4.txt", env)
    common.require(
        common.identity(pdf)["sha256"] == common.identity(pass3)["sha256"],
        f"{label} pass 3/4 differ",
    )
    common.run_logged([tools["pdfinfo"], str(pdf)], directory, directory / "console-pdfinfo.txt")
    common.run_logged([tools["mutool"], "show", str(pdf), "trailer"], directory, directory / "console-mutool-trailer.txt")
    text = directory / "main-final.txt"
    common.run_logged(
        [tools["pdftotext"], "-layout", "-enc", "UTF-8", str(pdf), str(text)],
        directory,
        directory / "console-pdftotext.txt",
    )
    try:
        extracted_text = text.read_bytes().decode("utf-8")
    except UnicodeDecodeError as exc:
        raise common.GateError(f"{label} pdftotext output is not UTF-8: {exc}") from exc
    canonical_text = extracted_text.replace("\r\n", "\n").replace("\r", "\n")
    text.write_bytes(canonical_text.encode("utf-8"))
    common.require(b"\r" not in text.read_bytes(), f"{label} canonical text still contains CR")
    info = (directory / "console-pdfinfo.txt").read_text(encoding="utf-8", errors="replace")
    match = re.search(r"^Pages:\s+(\d+)", info, re.MULTILINE)
    pages = int(match.group(1)) if match else 0
    common.require(261 <= pages <= 320, f"{label} page count outside B026 expectation: {pages}")
    log = (directory / "console-pass4.txt").read_text(encoding="utf-8", errors="replace")
    warnings = {
        "undefined_references": len(re.findall(r"There were undefined references|Reference .* undefined", log, re.I)),
        "undefined_citations": len(re.findall(r"There were undefined citations|Citation .* undefined", log, re.I)),
        "multiply_defined_labels": len(re.findall(r"multiply defined", log, re.I)),
        "rerun_required": len(re.findall(r"Rerun to get cross-references right|Label\(s\) may have changed", log, re.I)),
    }
    common.require(not any(warnings.values()), f"{label} terminal LaTeX warnings: {warnings}")
    return {
        "label": label,
        "pdf": common.identity(pdf),
        "pass3": common.identity(pass3),
        "text": common.identity(text),
        "pages": pages,
        "trailer_ids": common.trailer_ids(directory / "console-mutool-trailer.txt"),
        "terminal_log": common.identity(directory / "console-pass4.txt"),
        "warnings": {
            "fatal": warnings,
            "overfull_hbox": len(re.findall(r"Overfull \\hbox", log)),
        },
    }


def reader_language_qa(text_path: Path, expected_pages: int) -> dict[str, Any]:
    raw_bytes = text_path.read_bytes()
    common.require(b"\r" not in raw_bytes, "reader-language QA received noncanonical CR text")
    raw = raw_bytes.decode("utf-8")
    pages = raw.split("\f")
    common.require(pages and pages[-1].strip() == "", "pdftotext terminal form-feed sentinel absent")
    pages.pop()
    common.require(len(pages) == expected_pages, f"pagewise text count differs from PDF pages: {len(pages)} != {expected_pages}")
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
    common.require(not residual, f"untranslated or excluded English reached learner pages: {residual}")
    joined = " ".join(normalized_pages)
    required = (
        "Inferensi untuk data numerik",
        "Rata-rata satu sampel dengan distribusi t",
        "Teorema Limit Pusat untuk rata-rata sampel",
        "Memperkenalkan distribusi t",
        "Interval kepercayaan t satu sampel",
        "Uji t satu sampel",
        "Tentukan nilai kritis t",
        "Kebiasaan tidur warga New York",
        "Tinggi badan orang dewasa",
        "Solusi latihan",
        MODEL,
    )
    missing = [phrase for phrase in required if phrase.casefold() not in joined.casefold()]
    common.require(not missing, f"accepted Indonesian B026 content absent: {missing}")
    return {
        "pages_checked": len(normalized_pages),
        "residual_english_by_phrase": residual,
        "required_phrases": list(required),
        "required_phrases_absent": missing,
        "pagewise_residual_pass": True,
        "chapter_7_source_lines_included": "1-1052 inclusive",
        "later_chapter_7_source_included": False,
        "later_source_counted_as_learner_output": False,
    }


def verify_nonasset_inputs() -> dict[str, Any]:
    return {
        "exact_public_b025_base": verify_b025_base(),
        "source_blueprint": verify_blueprint(),
        "translation_receipts": verify_translation_receipts(),
    }


def probe() -> dict[str, Any]:
    inputs = verify_nonasset_inputs()
    common.require(not BUILD.exists(), "B026 build root already exists")
    texts, transforms = prepare_custom_texts()
    tools = common.find_tools()
    assets = asset_gate_probe()
    return {
        "boundary_id": BOUNDARY_ID,
        "status": (
            "PASS_STATIC_B026_ASSEMBLY_PREVIEW_EXACT_PUBLIC_B025_BASE_ASSET_GATE_READY"
            if assets["ready"]
            else "PASS_STATIC_B026_ASSEMBLY_PREVIEW_EXACT_PUBLIC_B025_BASE_ASSET_GATE_PENDING"
        ),
        "inputs": inputs,
        "assembly_preview": [memory_identity(common.rel(path), value) for path, value in texts.items()],
        "assembly_transformations": transforms,
        "asset_gate": assets,
        "tools": sorted(tools),
        "writes_performed": False,
    }


def self_test() -> dict[str, Any]:
    inputs = verify_nonasset_inputs()
    common.require(not BUILD.exists(), "B026 build root already exists")
    assets = verify_asset_gate()
    texts, transforms = prepare_custom_texts()
    tools = common.find_tools()
    return {
        "boundary_id": BOUNDARY_ID,
        "status": "PASS_INERT_EXACT_INPUTS_STAGING_ASSETS_ASSEMBLY_AND_TOOLCHAIN_BOUND",
        "inputs": inputs,
        "assembly_preview": [memory_identity(common.rel(path), value) for path, value in texts.items()],
        "assembly_transformations": transforms,
        "asset_gate": assets,
        "tools": sorted(tools),
        "writes_performed": False,
    }


def execute() -> dict[str, Any]:
    inputs = verify_nonasset_inputs()
    assets = verify_asset_gate()
    common.require(not BUILD.exists(), "refusing to overwrite B026 build root")
    BUILD.mkdir(parents=True)
    shutil.copytree(SOURCE, SNAPSHOT)
    custom = make_custom_sources()
    manifest = write_manifest()
    tools = common.find_tools()
    seed = manifest["sha256"][:32].upper()
    run_a = build_once("replay-a", RUN_A, tools, seed)
    run_b = build_once("replay-b", RUN_B, tools, seed)
    common.require(run_a["pages"] == run_b["pages"], "B026 replay page counts differ")
    common.require(run_a["pdf"]["sha256"] == run_b["pdf"]["sha256"], "B026 replay PDFs differ")
    common.require(run_a["text"]["sha256"] == run_b["text"]["sha256"], "B026 replay text differs")
    common.require(run_a["trailer_ids"] == run_b["trailer_ids"], "B026 replay trailer IDs differ")
    FINAL.mkdir()
    shutil.copy2(RUN_A / "main.pdf", FINAL_PDF)
    shutil.copy2(RUN_A / "main-final.txt", FINAL_TEXT)
    language = reader_language_qa(FINAL_TEXT, run_a["pages"])
    receipt = {
        "$schema": "interlanguage.r011-b026-boundary-clean-reader-build/v1",
        "boundary_id": BOUNDARY_ID,
        "status": (
            "PASS_TWO_REPLAY_DETERMINISTIC_BOUNDARY_CLEAN_BUILD_"
            "LANGUAGE_QA_COMPLETE_READER_VISUAL_QA_PENDING"
        ),
        "included_scope": (
            "All admitted and publicly verified B025 Indonesian learner work, "
            "plus Chapter 7 front matter and complete Section 7.1; exercises "
            "1-14; public odd answers 1-13."
        ),
        "excluded_untranslated_scope": [
            "Chapter 7 even answers 2-14, recorded as explicit O001 gaps",
            "Chapter 7 Section 7.2 onward",
            "Chapter 8 onward",
            "untranslated data, table, and index appendices not visible in the learner reader",
            "restricted instructor solutions",
        ],
        "inputs": inputs,
        "asset_gate": assets,
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
        "translation_provenance": MODEL,
        "rights": {
            "text_and_generated_figures": "CC BY-SA 3.0",
            "rissos_dolphin": "CC BY 2.0, Mike Baird attribution retained",
            "branding_excluded": True,
        },
        "complete_corpus": False,
        "source_closure_counted_as_learner_output": False,
        "restricted_solutions_accessed_or_invented": False,
        "next_cursor": {
            "boundary_id": "R011-B027",
            "path": "ch_inference_for_means/TeX/ch_inference_for_means.tex",
            "line": 1059,
            "section_label": "pairedData",
            "section_label_line": 1060,
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
    if args == ["--probe"]:
        result = probe()
    elif args == ["--self-test"]:
        result = self_test()
    elif args == ["--build"]:
        result = execute()
    else:
        raise SystemExit(
            "usage: build_b026_boundary_clean_reader.py --probe | --self-test | --build"
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
                    "asset_gate",
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
