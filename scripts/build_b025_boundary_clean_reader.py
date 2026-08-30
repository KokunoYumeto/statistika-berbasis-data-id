#!/usr/bin/env python3
"""Build the deterministic R011-B025 Indonesian learner reader.

B025 extends the admitted and publicly verified B024 reader through complete
Chapter 6, Section 6.4 (testing independence in two-way tables), exercises
35-38, and the upstream-public answers 35 and 37.  The build is fail-closed
until the localized iPod tail chart and both of its QA receipts have exact
identities configured below.  All writes are isolated under the B025 scratch
root; this script never mutates the backend, controls, output, release, Git,
network, credentials, or upstream.
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

import build_b024_boundary_clean_reader as prior


common = prior.common
ROOT = Path(__file__).resolve().parents[1]
BOUNDARY_ID = "R011-B025"
MODEL = "OpenAI Codex gpt-5.6-sol, Ultra"

SOURCE = ROOT / "scratch/b024-boundary-clean-reader/source-snapshot"
BASE_READER = ROOT / "output/pdf/statistika-berbasis-data-batas-R011-B024.pdf"
BUILD = ROOT / "scratch/b025-boundary-clean-reader-r2"
SNAPSHOT = BUILD / "source-snapshot"
RUN_A = BUILD / "replay-a"
RUN_B = BUILD / "replay-b"
FINAL = BUILD / "final"
FINAL_PDF = FINAL / "main.pdf"
FINAL_TEXT = FINAL / "main-final.txt"
MANIFEST = BUILD / "R011-B025_BOUNDARY_CLEAN_SOURCE_MANIFEST.tsv"
RECEIPT = FINAL / "R011-B025_BOUNDARY_CLEAN_BUILD_QA.json"

SOURCE_MAIN = SOURCE / "main_boundary_clean_b024.tex"
SOURCE_ANSWERS = (
    SOURCE / "extraTeX/eoceSolutions/eoceSolutions_boundary_clean_b024.tex"
)
SOURCE_CHAPTER = SOURCE / "ch_inference_for_props/TeX/ch_inference_for_props.tex"
SOURCE_EXERCISES_35_38 = (
    SOURCE
    / "ch_inference_for_props/TeX/testing_for_independence_in_two-way_tables.tex"
)

CUSTOM_MAIN = SNAPSHOT / "main_boundary_clean_b025.tex"
CUSTOM_ANSWERS = (
    SNAPSHOT / "extraTeX/eoceSolutions/eoceSolutions_boundary_clean_b025.tex"
)
CUSTOM_CHAPTER = (
    SNAPSHOT / "ch_inference_for_props/TeX/ch_inference_for_props.tex"
)
CUSTOM_EXERCISES_35_38 = (
    SNAPSHOT
    / "ch_inference_for_props/TeX/testing_for_independence_in_two-way_tables.tex"
)

STAGING = ROOT / "qa/b025-translation/staging"
SECTION_A = STAGING / "section-lines-2008-2238.id.tex"
SECTION_B = STAGING / "section-lines-2239-2434.id.tex"
EXERCISES_ID = STAGING / "exercises-lines-1-127.id.tex"
ANSWERS_ID = STAGING / "public-answers-lines-1500-1543.id.tex"
O001_GAPS = STAGING / "R011-B025_O001_MASTERY_GAPS.json"
BLUEPRINT = ROOT / "qa/b025-source/R011-B025_BOUNDARY_BLUEPRINT.json"
MAIN_A_AUDIT = ROOT / "qa/b025-translation/R011-B025_MAIN_A_TRANSLATION_AUDIT.json"
MAIN_B_AUDIT = (
    ROOT / "qa/b025-translation/R011-B025_MAIN_TRANSLATION_PART_B_AUDIT.json"
)
EXERCISE_ANSWER_QA = (
    ROOT / "qa/b025-translation/R011-B025_EXERCISES_ANSWERS_TRANSLATION_QA.json"
)
INDEPENDENT_TRANSLATION_AUDIT = (
    ROOT / "qa/b025-translation/R011-B025_INDEPENDENT_TRANSLATION_AUDIT.json"
)
INDEPENDENT_TRANSLATION_VERIFIER = (
    ROOT / "qa/b025-translation/verify_R011_B025_independent.py"
)

AUTHORITY_ROOT = (
    ROOT
    / "authority/upstream/"
    "openintro-statistics-fee25091fb24e89c36296fd67c48c1fcf7a93b6e"
)
AUTHORITY_MAIN = AUTHORITY_ROOT / "ch_inference_for_props/TeX/ch_inference_for_props.tex"
AUTHORITY_EXERCISES = (
    AUTHORITY_ROOT
    / "ch_inference_for_props/TeX/testing_for_independence_in_two-way_tables.tex"
)
AUTHORITY_ANSWERS = AUTHORITY_ROOT / "extraTeX/eoceSolutions/eoceSolutions.tex"
AUTHORITY_BOOK = AUTHORITY_ROOT / "main.tex"
AUTHORITY_CHAPTER_7 = (
    AUTHORITY_ROOT / "ch_inference_for_means/TeX/ch_inference_for_means.tex"
)
AUTHORITY_CHART = (
    AUTHORITY_ROOT
    / "ch_inference_for_props/figures/iPodChiSqTail/iPodChiSqTail.pdf"
)
AUTHORITY_CHART_PRODUCER = (
    AUTHORITY_ROOT
    / "ch_inference_for_props/figures/iPodChiSqTail/iPodChiSqTail.R"
)
AUTHORITY_BIBLIOGRAPHY = AUTHORITY_ROOT / "eoce.bib"

BASE_BUILD_QA = (
    ROOT
    / "scratch/b024-boundary-clean-reader/final/"
    "R011-B024_BOUNDARY_CLEAN_BUILD_QA.json"
)
BASE_ROOT_VISUAL_QA = (
    ROOT / "qa/b024-reader/R011-B024_ROOT_VISUAL_INSPECTION_QA.json"
)
BASE_PAGEWISE_QA = ROOT / "qa/b024-reader/R011-B024_PAGEWISE_LANGUAGE_QA.json"
BASE_PROMOTION = (
    ROOT / "qa/b024-reader/R011-B024_READER_PROMOTION_RECEIPT.json"
)
BASE_FINAL_QA_BINDINGS = (
    ROOT / "qa/b024-backend-admission/R011-B024_FINAL_QA_BINDINGS.json"
)
BASE_BACKEND_ADMISSION = (
    ROOT / "qa/b024-backend-admission/R011-B024_BACKEND_ADMISSION_RECEIPT.json"
)
BASE_PUBLIC_FINALIZATION = (
    ROOT
    / "qa/b024-publication-finalization/"
    "R011-B024_PUBLICATION_FINALIZATION_RECEIPT.json"
)
BASE_GITHUB_RECEIPT = (
    ROOT
    / "release/b024/R011-B024-v2026.08.29.3/"
    "GITHUB_PUBLICATION_RECEIPT.json"
)
BASE_ZENODO_RECEIPT = (
    ROOT
    / "qa/b024-publication/"
    "ZENODO_PUBLICATION_RECEIPT_R011-B024-v2026.08.29.3.json"
)

EXPECTED_BASE_SOURCE_FILE_COUNT = 1_218
EXPECTED_BASE_SOURCE_BYTES = 41_841_482
EXPECTED_BASE_SOURCE_INVENTORY_SHA256 = (
    "985d662a7ae87efed9c6e4e9d9f9dd640edcc7037f936184e3590aa5b5be6410"
)

EXPECTED_BASE_FILES = {
    SOURCE_MAIN: (
        6_972,
        "ac6b480c39d6f652992e2b0b07221a846b37810da69e8adf6eef150fad8e027e",
    ),
    SOURCE_ANSWERS: (
        57_121,
        "35bd3617503f850871131577a9efe99e27459f5d79ab48375262d7236c135c92",
    ),
    SOURCE_CHAPTER: (
        91_767,
        "6bade559625442667e353489d66e777ea38b524a21aabb0e9ac6e6347a349d35",
    ),
    SOURCE_EXERCISES_35_38: (
        4_558,
        "5f22aeaa256054748f626dad74a279e57d3a098f6060dc057a9625f7b2259e9a",
    ),
    SOURCE
    / "ch_inference_for_props/figures/iPodChiSqTail/iPodChiSqTail.pdf": (
        5_719,
        "789e9da58ef275f9996f2414cb53ed5edb134b9df2f3f194e7be42d7ce810403",
    ),
}

EXPECTED_BASE_EVIDENCE = {
    BASE_READER: (
        12_390_137,
        "fcd78ff026131e4979c0ea282b4468101406527f16dc335ee6583ad220273b53",
    ),
    BASE_BUILD_QA: (
        20_617,
        "3c59658c913ae5071f489841c7d358b616666127a303d7888db489b47dd2fbf2",
    ),
    BASE_ROOT_VISUAL_QA: (
        13_331,
        "fba110143a0598fbb6f6a0132cb1bd3c3a8ac12566b331b42964479c9fca6663",
    ),
    BASE_PAGEWISE_QA: (
        86_185,
        "eb59ed06717453bef6a6fb91b3d2629094e47e25f5e42b34914d15a2a6e0b43e",
    ),
    BASE_PROMOTION: (
        1_342,
        "ac4b0d636e653343aa6212fd4f7b8a9527b5b172da934ddf8bb47f51333b902d",
    ),
    BASE_FINAL_QA_BINDINGS: (
        4_646,
        "a9d3b56b8931317c23261069e98d7f545f8a4e1a04b30b4ca15cade4f94d6620",
    ),
    BASE_BACKEND_ADMISSION: (
        3_167,
        "18d4cb3c08c1928966d435123f189ebeb99aaac0ada24a1e23cbdac9291ad289",
    ),
    BASE_PUBLIC_FINALIZATION: (
        6_641,
        "7ee96691625bbaaa41b8874c3a7c758415ffd4298757dc10cb67002f7bb14b80",
    ),
    BASE_GITHUB_RECEIPT: (
        2_332,
        "0feae29aa61c63f995fcbf16e5d4c13d8ad242c8402148077a16459428b5d5f2",
    ),
    BASE_ZENODO_RECEIPT: (
        2_372,
        "7eb6c5e78d6db08dcb46d5c3ab08480c7fae0cfd128247234e5a66907b198d9c",
    ),
}

EXPECTED_AUTHORITY = {
    AUTHORITY_MAIN: (
        103_385,
        "a2470ca3041209d1f1194b3ab27e8124405d8fdbd1ccece89a0319be13fae8a7",
    ),
    AUTHORITY_EXERCISES: (
        4_558,
        "5f22aeaa256054748f626dad74a279e57d3a098f6060dc057a9625f7b2259e9a",
    ),
    AUTHORITY_ANSWERS: (
        106_045,
        "6c4e01376db4c023cc7b3f9949490e57220ef1cb831c580da71efde6ce723268",
    ),
    AUTHORITY_BOOK: (
        4_155,
        "1ed8952651f4b21e7175d82b4c1fda780aee5ec78f88143b97c692477ee2750b",
    ),
    AUTHORITY_CHAPTER_7: (
        141_389,
        "d818b24b8e8d0582f8e603972e87764082d8470d91ddcbeaa794c295a1d37bec",
    ),
    AUTHORITY_CHART: (
        5_719,
        "789e9da58ef275f9996f2414cb53ed5edb134b9df2f3f194e7be42d7ce810403",
    ),
    AUTHORITY_CHART_PRODUCER: (
        368,
        "16c6c2d5167308537e38b4120ece9e841f6d41d532d9dab32e744329d319d543",
    ),
    AUTHORITY_BIBLIOGRAPHY: (
        30_361,
        "42191d6cb80b562e3bb769388759cba25b1798ae416536ebfdcf73de0770217a",
    ),
}

EXPECTED_STAGING = {
    BLUEPRINT: (
        24_634,
        "529f46e13cabc1db76a65e8a1281f99e51251cc08753e8c217871d52eb296d7e",
    ),
    SECTION_A: (
        9_104,
        "5a59d955174eb73176876d756bb4c44ba427d25d5ca86ab41824ff218d2d9554",
    ),
    SECTION_B: (
        7_107,
        "bc16102ee8a445f2410a9d429b9831a58f2637a528776ca727eb07607d045d63",
    ),
    EXERCISES_ID: (
        4_933,
        "0d66bdb60c1edcf246e933ac0eab97bacaf237a573ec260e5a3463076731f440",
    ),
    ANSWERS_ID: (
        1_748,
        "91a3e108ced397c72ae204d5f142fc9838f2612312383d1aa52eac78f0eb2dec",
    ),
    O001_GAPS: (
        2_107,
        "5ca09682b02110ce941065c495683bbd36cd7ac9055c88dbd89b46512c4b8aee",
    ),
    MAIN_A_AUDIT: (
        3_914,
        "06742809fcd4984788b9790a9ecba4fbc9c70eb14acd026936b32100a6ac7fed",
    ),
    MAIN_B_AUDIT: (
        7_712,
        "b0dfee1a269bb541d3b6d941dc4c400c33e1b774fb0d30e8d1b6f80ba365a776",
    ),
    EXERCISE_ANSWER_QA: (
        2_844,
        "a3653c8aaa12301fbded5588c83ef6c59bccbc5a107b806c2118c29a3005e947",
    ),
    INDEPENDENT_TRANSLATION_AUDIT: (
        16_509,
        "737f485b49f80e26269e282b227221d7eb3826005c5dd8d1b6066ae8cbd5c215",
    ),
    INDEPENDENT_TRANSLATION_VERIFIER: (
        38_379,
        "214e6977f6d9b1e32e97b3b3012ca8df73a78fd4796c1370ca185216a7d5270f",
    ),
}

# The chart producer must supply all four exact values before any self-test or
# build can pass.  Keeping them unset is the intentional fail-closed state.
LOCALIZED_CHART = STAGING / "assets/iPodChiSqTail.id.pdf"
CHART_QA = (
    ROOT / "qa/b025-translation/R011-B025_IPOD_CHISQ_TAIL_LOCALIZATION_QA.json"
)
CHART_VISUAL_QA = (
    ROOT / "qa/b025-translation/R011-B025_IPOD_CHISQ_TAIL_VISUAL_QA.json"
)
EXPECTED_LOCALIZED_CHART: tuple[int, str] | None = (
    13_265,
    "4d34c0d4f59787283086f88fb0eaa7c47714726b0e21fcb440a7bcf8e243acae",
)
EXPECTED_CHART_QA: tuple[int, str] | None = (
    3_314,
    "c2ab840d15bf7391518c4587aad7ed6f7ded1c9b208706861434ac64e9b104db",
)
EXPECTED_CHART_VISUAL_QA: tuple[int, str] | None = (
    2_603,
    "13ec3d5529ebdf198630341f16accb457bb8b94cdda7edcfdbb218007f29e837",
)
EXPECTED_LOCALIZED_CHART_TEXT: tuple[str, ...] = (
    "Luas ekor (1 dari 500 juta)",
    "terlalu kecil untuk terlihat",
)

CHART_TARGET_REL = Path(
    "ch_inference_for_props/figures/iPodChiSqTail/iPodChiSqTail.pdf"
)

SCOPE_B025 = r"""\chapter*{Cakupan edisi parsial ini}
\addcontentsline{toc}{chapter}{Cakupan edisi parsial ini}
Pembaca ini berhenti tepat setelah Bagian~6.4,
\emph{Menguji independensi dalam tabel dua arah}. Cakupan Bab~6 dalam
edisi ini memuat latihan 1--38. Semua jawaban publik yang tersedia dari
sumber disertakan, yaitu jawaban bernomor ganjil 1--37. Jawaban bernomor
genap 2--38 memang tidak tersedia dalam sumber publik; jawaban-jawaban itu
dicatat sebagai kesenjangan pendamping kemahiran O001 dan tidak direka."""

OLD_B024_NOTE = "% Boundary-clean learner reader through Chapter 6, Section 6.3."
NEW_B025_NOTE = "% Boundary-clean learner reader through Chapter 6, Section 6.4."
OLD_ANSWER_INCLUDE = (
    r"\include{extraTeX/eoceSolutions/eoceSolutions_boundary_clean_b024}"
)
NEW_ANSWER_INCLUDE = (
    r"\include{extraTeX/eoceSolutions/eoceSolutions_boundary_clean_b025}"
)
OLD_NAV = (
    r"  \chaptersection{singleProportion}" + "\n"
    r"  \chaptersection{differenceOfTwoProportions}" + "\n"
    r"  \chaptersection{oneWayChiSquare}" + "\n"
    "% Boundary-clean reader omits navigation to excluded later Chapter 6 sections."
)
NEW_NAV = (
    r"  \chaptersection{singleProportion}" + "\n"
    r"  \chaptersection{differenceOfTwoProportions}" + "\n"
    r"  \chaptersection{oneWayChiSquare}" + "\n"
    r"  \chaptersection{twoWayTablesAndChiSquare}" + "\n"
    "% Boundary-clean reader omits navigation to excluded later Chapter 6 sections."
)
PREVIOUS_EXERCISE_INPUT = (
    r"{\input{ch_inference_for_props/TeX/"
    r"testing_for_goodness_of_fit_using_chi-square.tex}}"
)
CURRENT_EXERCISE_INPUT = (
    r"\input{ch_inference_for_props/TeX/"
    r"testing_for_independence_in_two-way_tables.tex}"
)
FORCED_BREAK = r"\D{\newpage}"
REFLOW_NOTE = "% Boundary-clean reader removes a legacy forced page break."

FORBIDDEN_STAGED_ENGLISH = (
    "Testing for independence in two-way tables",
    "Chi-square test for two-way tables",
    "Expected counts in two-way tables",
    "Tail area (1 / 500 million)",
    "is too small to see",
)
FORBIDDEN_READER_ENGLISH = (
    "Testing for independence in two-way tables",
    "Chi-square test for two-way tables",
    "Inference for numerical data",
    "One-sample means with the t-distribution",
    "Introduction to linear regression",
    "Multiple and logistic regression",
    "Tail area (1 / 500 million)",
    "is too small to see",
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


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    common.require(isinstance(value, dict), f"JSON root is not an object: {common.rel(path)}")
    return value


def verify_public_b024_base() -> dict[str, Any]:
    common.require(SOURCE.is_dir(), "publicly admitted B024 source snapshot absent")
    inventory = common.source_inventory(SOURCE)
    common.require(
        inventory["files"] == EXPECTED_BASE_SOURCE_FILE_COUNT,
        "B024 source snapshot file count changed",
    )
    common.require(
        inventory["bytes"] == EXPECTED_BASE_SOURCE_BYTES,
        "B024 source snapshot byte count changed",
    )
    common.require(
        inventory["inventory_sha256"] == EXPECTED_BASE_SOURCE_INVENTORY_SHA256,
        "B024 source snapshot inventory changed",
    )
    for path, expected in EXPECTED_BASE_FILES.items():
        common.require_exact(path, expected)
    for path, expected in EXPECTED_BASE_EVIDENCE.items():
        common.require_exact(path, expected)

    reader = PdfReader(BASE_READER)
    common.require(len(reader.pages) == 253, "promoted B024 base reader page count changed")

    build = _json(BASE_BUILD_QA)
    visual = _json(BASE_ROOT_VISUAL_QA)
    pagewise = _json(BASE_PAGEWISE_QA)
    promotion = _json(BASE_PROMOTION)
    final_bindings = _json(BASE_FINAL_QA_BINDINGS)
    admission = _json(BASE_BACKEND_ADMISSION)
    finalization = _json(BASE_PUBLIC_FINALIZATION)
    github = _json(BASE_GITHUB_RECEIPT)
    zenodo = _json(BASE_ZENODO_RECEIPT)

    common.require(
        build.get("boundary_id") == "R011-B024"
        and build.get("page_count") == 253
        and build.get("candidate_artifact", {}).get("sha256")
        == EXPECTED_BASE_EVIDENCE[BASE_READER][1],
        "B024 deterministic build receipt changed",
    )
    common.require(
        visual.get("status") == "PASS_ALL_253_PAGES_VISUALLY_INSPECTED_ZERO_DEFECTS"
        and visual.get("page_count") == 253,
        "B024 root visual QA changed",
    )
    common.require(
        pagewise.get("status")
        == "PASS_DETERMINISTIC_BUILD_PAGEWISE_LANGUAGE_STRUCTURE_AND_AUTOMATED_VISUAL_QA",
        "B024 pagewise QA changed",
    )
    common.require(
        promotion.get("status")
        == "PASS_EXACT_B024_READER_ATOMICALLY_PROMOTED_AND_VERIFIED",
        "B024 promotion receipt changed",
    )
    common.require(
        final_bindings.get("status")
        == "PASS_FINAL_QA_CONFIRMED_FOR_BACKEND_ADMISSION",
        "B024 final QA binding changed",
    )
    common.require(
        admission.get("status") == "PASS_B024_BACKEND_ADMITTED_WITH_EXACT_REPLAY",
        "B024 backend admission changed",
    )
    common.require(
        finalization.get("status") == "PASS_B024_PUBLICATION_FINALIZATION_APPLIED"
        and finalization.get("reader", {}).get("pages") == 253
        and finalization.get("reader", {}).get("sha256")
        == EXPECTED_BASE_EVIDENCE[BASE_READER][1]
        and finalization.get("durable_goal_status") == "active",
        "B024 public finalization changed",
    )
    common.require(
        github.get("status") == "PUBLISHED_AND_ANONYMOUSLY_VERIFIED"
        and github.get("repository_public") is True
        and github.get("anonymous_public_byte_readback") is True
        and github.get("tag") == "r011-b024-2026.08.29.3"
        and github.get("learner_reader_pages") == 253,
        "B024 GitHub public readback changed",
    )
    common.require(
        zenodo.get("status") == "PUBLISHED_AND_ANONYMOUSLY_VERIFIED"
        and zenodo.get("access_right") == "open"
        and zenodo.get("anonymous_public_byte_readback") is True
        and zenodo.get("doi") == "10.5281/zenodo.22166152"
        and zenodo.get("concept_doi") == "10.5281/zenodo.22059801"
        and zenodo.get("learner_reader_pages") == 253,
        "B024 Zenodo public readback changed",
    )
    return {
        "source_snapshot": {
            key: inventory[key]
            for key in ("files", "bytes", "inventory_sha256")
        },
        "promoted_reader": {
            **common.identity(BASE_READER),
            "pages": len(reader.pages),
        },
        "build_qa": common.identity(BASE_BUILD_QA),
        "root_visual_qa": common.identity(BASE_ROOT_VISUAL_QA),
        "pagewise_qa": common.identity(BASE_PAGEWISE_QA),
        "promotion": common.identity(BASE_PROMOTION),
        "backend_admission": common.identity(BASE_BACKEND_ADMISSION),
        "public_finalization": common.identity(BASE_PUBLIC_FINALIZATION),
        "github_public_readback": {
            **common.identity(BASE_GITHUB_RECEIPT),
            "release_url": github["release_url"],
            "tag": github["tag"],
        },
        "zenodo_public_readback": {
            **common.identity(BASE_ZENODO_RECEIPT),
            "doi": zenodo["doi"],
            "concept_doi": zenodo["concept_doi"],
            "public_url": zenodo["public_url"],
        },
    }


def verify_blueprint() -> dict[str, Any]:
    common.require_exact(BLUEPRINT, EXPECTED_STAGING[BLUEPRINT])
    blueprint = _json(BLUEPRINT)
    common.require(blueprint.get("boundary_id") == BOUNDARY_ID, "B025 blueprint boundary changed")
    common.require(
        blueprint.get("status")
        == "PASS_SOURCE_ASSET_DATA_RIGHTS_AND_BOOK_ORDER_DEPENDENCY_CLOSURE",
        "B025 source/asset/data closure did not pass",
    )
    authority = blueprint.get("authority", {})
    common.require(
        authority.get("commit") == "fee25091fb24e89c36296fd67c48c1fcf7a93b6e"
        and authority.get("tree") == "d61cc601e7d97759ce805900520f784d02a0489e"
        and authority.get("branch_observed") == "master",
        "B025 authority pin changed",
    )
    main = blueprint.get("main_source", {})
    common.require(
        main.get("start_line") == 2008
        and main.get("end_line") == 2434
        and main.get("start_label") == "twoWayTablesAndChiSquare"
        and main.get("source_file_ends_at_boundary") is True
        and main.get("slice", {}).get("bytes") == 15_494
        and main.get("slice", {}).get("sha256")
        == "a82717a6c093e0d5a3c08744aa84a97046af0ce0f0a4ff42f3d6201a77e64ca4",
        "B025 main boundary changed",
    )
    closure = blueprint.get("exercise_answer_closure", {})
    common.require(
        closure.get("chapter_exercise_ids") == [35, 36, 37, 38]
        and closure.get("public_answer_ids") == [35, 37]
        and closure.get("o001_gap_ids") == [36, 38]
        and closure.get("restricted_solutions_accessed_or_invented") is False,
        "B025 exercise/answer closure changed",
    )
    figures = blueprint.get("figure_asset_closure", [])
    common.require(
        isinstance(figures, list)
        and len(figures) == 1
        and figures[0].get("content_localization_required") is True
        and figures[0].get("sha256") == EXPECTED_AUTHORITY[AUTHORITY_CHART][1],
        "B025 chart closure changed",
    )
    rights = blueprint.get("rights", {})
    common.require(
        rights.get("branding_excluded") is True
        and rights.get("new_unresolved_binary_dependency") is False
        and rights.get("component_rights_override") is True,
        "B025 component-rights closure changed",
    )
    post = blueprint.get("post_boundary_cursor", {})
    common.require(
        post.get("working_boundary_id") == "R011-B026"
        and post.get("line") == 1
        and post.get("chapter_label") == "ch_inference_for_means"
        and post.get("first_section_line") == 29
        and post.get("first_section_label") == "oneSampleMeansWithTDistribution",
        "B025 next cursor changed",
    )
    return {
        "boundary_id": blueprint["boundary_id"],
        "authority": authority,
        "main_source": main,
        "exercise_answer_closure": closure,
        "figure_asset_closure": figures,
        "production_closure": blueprint.get("production_closure", {}),
        "rights": rights,
        "post_boundary_cursor": post,
    }


def verify_translation_qa() -> dict[str, Any]:
    for path in (
        MAIN_A_AUDIT,
        MAIN_B_AUDIT,
        EXERCISE_ANSWER_QA,
        INDEPENDENT_TRANSLATION_AUDIT,
        INDEPENDENT_TRANSLATION_VERIFIER,
    ):
        common.require_exact(path, EXPECTED_STAGING[path])
    main_a = _json(MAIN_A_AUDIT)
    main_b = _json(MAIN_B_AUDIT)
    exercise = _json(EXERCISE_ANSWER_QA)
    independent = _json(INDEPENDENT_TRANSLATION_AUDIT)
    common.require(
        main_a.get("status")
        == "PASS_COMPLETE_NATURAL_ID_ID_STRUCTURE_MATH_LANGUAGE_AND_HIGH_CONFIDENCE_FORMULA_CORRECTION_QA"
        and main_a.get("target", {}).get("sha256") == EXPECTED_STAGING[SECTION_A][1]
        and main_a.get("applied_authority_correction", {}).get("target_formula")
        == "iPodAD/iPodDD = 61/219",
        "B025 main part A audit changed",
    )
    common.require(
        main_b.get("status") == "PASS_DETERMINISTIC_STRUCTURE_MATH_AND_RESIDUAL_ENGLISH"
        and main_b.get("target", {}).get("sha256") == EXPECTED_STAGING[SECTION_B][1]
        and not main_b.get("failed_checks"),
        "B025 main part B audit changed",
    )
    common.require(
        exercise.get("status")
        == "PASS_EXERCISES_35_38_AND_ALL_LINKED_PUBLIC_ODD_ANSWERS_TRANSLATED"
        and exercise.get("exercise_ids") == [35, 36, 37, 38]
        and exercise.get("public_answer_ids") == [35, 37]
        and exercise.get("o001_gap_ids") == [36, 38]
        and exercise.get("restricted_solutions_accessed_or_invented") is False,
        "B025 exercise/answer QA changed",
    )
    common.require(
        independent.get("status")
        == "PASS_INDEPENDENT_COMPLETE_NATURAL_ID_ID_STRUCTURE_MATH_REPAIRS_EXERCISE_ANSWER_AND_O001_QA"
        and independent.get("boundary_id") == BOUNDARY_ID
        and independent.get("semantic_review", {}).get("status")
        == "PASS_EVERY_LEARNER_FACING_LINE_REVIEWED_AGAINST_FROZEN_SOURCE"
        and independent.get("structural_and_math_qa", {}).get("status") == "PASS"
        and independent.get("exercise_answer_and_o001_qa", {}).get(
            "restricted_solutions_accessed_or_invented"
        )
        is False
        and independent.get("localized_asset_qa", {}).get("target", {}).get("sha256")
        == EXPECTED_LOCALIZED_CHART[1],
        "B025 independent translation audit changed",
    )
    return {
        "main_a": common.identity(MAIN_A_AUDIT),
        "main_b": common.identity(MAIN_B_AUDIT),
        "exercise_answers": common.identity(EXERCISE_ANSWER_QA),
        "independent_audit": common.identity(INDEPENDENT_TRANSLATION_AUDIT),
        "independent_verifier": common.identity(INDEPENDENT_TRANSLATION_VERIFIER),
    }


def verify_nonchart_inputs() -> dict[str, Any]:
    base = verify_public_b024_base()
    for path, expected in EXPECTED_AUTHORITY.items():
        common.require_exact(path, expected)
    require_slice(
        AUTHORITY_MAIN,
        2008,
        2434,
        (
            15_494,
            "a82717a6c093e0d5a3c08744aa84a97046af0ce0f0a4ff42f3d6201a77e64ca4",
        ),
    )
    require_slice(AUTHORITY_EXERCISES, 1, 127, EXPECTED_AUTHORITY[AUTHORITY_EXERCISES])
    require_slice(
        AUTHORITY_ANSWERS,
        1500,
        1543,
        (
            1_660,
            "b09e89cb4e0b98f1f38f75bea10dec562d3ac247aa2a55bc12ae8dc45dd1977c",
        ),
    )
    require_slice(
        AUTHORITY_BIBLIOGRAPHY,
        824,
        831,
        (
            464,
            "7c6d9f6b03796c9349b58ee05581aac8e34a2cd4efed469d33bc6cd415056e7a",
        ),
    )
    for path, expected in EXPECTED_STAGING.items():
        common.require_exact(path, expected)
    return {
        "public_b024_base": base,
        "authority_slices": {
            "main_2008_2434": {
                "bytes": 15_494,
                "sha256": "a82717a6c093e0d5a3c08744aa84a97046af0ce0f0a4ff42f3d6201a77e64ca4",
            },
            "exercises_1_127": {
                "bytes": 4_558,
                "sha256": EXPECTED_AUTHORITY[AUTHORITY_EXERCISES][1],
            },
            "answers_1500_1543": {
                "bytes": 1_660,
                "sha256": "b09e89cb4e0b98f1f38f75bea10dec562d3ac247aa2a55bc12ae8dc45dd1977c",
            },
            "bibliography_824_831": {
                "bytes": 464,
                "sha256": "7c6d9f6b03796c9349b58ee05581aac8e34a2cd4efed469d33bc6cd415056e7a",
            },
        },
        "blueprint": verify_blueprint(),
        "translation_qa": verify_translation_qa(),
    }


def verify_staged_fragments() -> dict[str, Any]:
    fragments = (
        (SECTION_A, 2008, 2238, 2),
        (SECTION_B, 2239, 2434, 2),
    )
    for path, first, last, expected_breaks in fragments:
        target = normalized_lf(path)
        common.require(target.endswith("\n"), f"fragment lacks terminal LF: {common.rel(path)}")
        common.require(
            target.count(FORCED_BREAK) == expected_breaks,
            f"fragment break topology changed: {common.rel(path)}",
        )
        source = source_slice(AUTHORITY_MAIN, first, last).decode("utf-8")
        prior.prior.require_protected_sequences(source, target, common.rel(path))
        stripped = re.sub(r"(?m)^%.*$", "", target)
        for phrase in FORBIDDEN_STAGED_ENGLISH:
            common.require(
                phrase.casefold() not in stripped.casefold(),
                f"English staged phrase remains ({phrase}): {common.rel(path)}",
            )

    exercises = normalized_lf(EXERCISES_ID)
    common.require(
        exercises.startswith(r"\exercisesheader{}" + "\n"),
        "B025 exercise header changed",
    )
    exercise_numbers = [
        int(value) for value in re.findall(r"(?m)^% (\d+)\s*$", exercises)
    ]
    common.require(
        exercise_numbers == [35, 36, 37, 38],
        f"B025 exercise sequence changed: {exercise_numbers}",
    )
    common.require(exercises.count(r"\eoce{") == 4, "B025 exercise count changed")
    source_exercises = source_slice(AUTHORITY_EXERCISES, 1, 127).decode("utf-8")
    prior.prior.require_protected_sequences(
        source_exercises,
        exercises,
        common.rel(EXERCISES_ID),
    )

    answers = normalized_lf(ANSWERS_ID)
    answer_numbers = [
        int(value) for value in re.findall(r"(?m)^% (\d+)\s*$", answers)
    ]
    common.require(
        answer_numbers == [35, 37],
        f"B025 public-answer sequence changed: {answer_numbers}",
    )
    common.require(answers.count(r"\eocesol{") == 2, "B025 answer count changed")
    common.require(
        answers.count(r"\end{multicols}") == 1
        and answers.count(r"\begin{multicols}{2}") == 1,
        "B025 public-answer internal column transition changed",
    )
    source_answers = source_slice(AUTHORITY_ANSWERS, 1500, 1543).decode("utf-8")
    prior.prior.require_protected_sequences(
        source_answers,
        answers,
        common.rel(ANSWERS_ID),
    )

    gaps = _json(O001_GAPS)
    common.require(
        gaps.get("boundary_id") == BOUNDARY_ID
        and gaps.get("o001_gap_ids") == [36, 38]
        and gaps.get("public_answers_present") == [35, 37]
        and gaps.get("restricted_solutions_accessed_or_invented") is False,
        "B025 O001 gap ledger changed",
    )
    return {
        "chapter_fragments": [
            common.identity(path) for path, _, _, _ in fragments
        ],
        "exercises": common.identity(EXERCISES_ID),
        "public_answers": common.identity(ANSWERS_ID),
        "o001_gaps": common.identity(O001_GAPS),
        "exercise_ordinals": exercise_numbers,
        "public_answer_ordinals": answer_numbers,
        "o001_gap_ordinals": [36, 38],
        "restricted_solutions_accessed_or_invented": False,
    }


def chart_gate_probe() -> dict[str, Any]:
    configured = {
        "localized_chart": EXPECTED_LOCALIZED_CHART is not None,
        "chart_qa": EXPECTED_CHART_QA is not None,
        "chart_visual_qa": EXPECTED_CHART_VISUAL_QA is not None,
        "required_visible_text": bool(EXPECTED_LOCALIZED_CHART_TEXT),
    }
    return {
        "ready": all(configured.values()),
        "configured": configured,
        "expected_paths": [
            common.rel(LOCALIZED_CHART),
            common.rel(CHART_QA),
            common.rel(CHART_VISUAL_QA),
        ],
        "authority_chart": common.identity(AUTHORITY_CHART),
        "required_semantics": {
            "chi_square_statistic": 40.13,
            "degrees_of_freedom": 2,
            "tail_geometry_preserved": True,
            "english_annotation_absent": [
                "Tail area (1 / 500 million)",
                "is too small to see",
            ],
        },
    }


def verify_chart_gate() -> dict[str, Any]:
    probe = chart_gate_probe()
    common.require(
        probe["ready"],
        "B025 localized iPod chart exact PDF/QA/visual-QA identities and visible-text tokens have not been supplied",
    )
    assert EXPECTED_LOCALIZED_CHART is not None
    assert EXPECTED_CHART_QA is not None
    assert EXPECTED_CHART_VISUAL_QA is not None
    common.require_exact(LOCALIZED_CHART, EXPECTED_LOCALIZED_CHART)
    common.require_exact(CHART_QA, EXPECTED_CHART_QA)
    common.require_exact(CHART_VISUAL_QA, EXPECTED_CHART_VISUAL_QA)
    chart_qa = _json(CHART_QA)
    visual_qa = _json(CHART_VISUAL_QA)
    common.require(
        chart_qa.get("boundary_id") == BOUNDARY_ID
        and chart_qa.get("status")
        == "PASS_EXACT_ANNOTATION_LOCALIZATION_AND_GEOMETRY_PRESERVATION"
        and chart_qa.get("deterministic_two_replay") is True
        and chart_qa.get("visible_english_labels_remaining") == 0
        and chart_qa.get("mathematical_closure", {}).get("pearson_chi_square")
        == 40.13
        and chart_qa.get("mathematical_closure", {}).get("degrees_of_freedom") == 2
        and chart_qa.get("output", {}).get("sha256")
        == EXPECTED_LOCALIZED_CHART[1],
        "B025 localized chart QA did not pass",
    )
    common.require(
        visual_qa.get("boundary_id") == BOUNDARY_ID
        and visual_qa.get("status")
        == "PASS_DIRECT_VISUAL_INSPECTION_AND_RASTER_GEOMETRY_COMPARISON"
        and visual_qa.get("localized_output", {}).get("sha256")
        == EXPECTED_LOCALIZED_CHART[1]
        and visual_qa.get("render", {}).get("changed_pixels_outside_permitted_annotation_region")
        == 0
        and visual_qa.get("render", {}).get("non_annotation_raster_geometry_pixel_identical")
        is True
        and not visual_qa.get("direct_visual_findings", {}).get("visual_defects"),
        "B025 localized chart visual QA did not pass",
    )
    reader = PdfReader(LOCALIZED_CHART)
    common.require(len(reader.pages) == 1, "B025 localized iPod chart is not one page")
    text = reader.pages[0].extract_text() or ""
    compact = re.sub(r"\s+", "", text).casefold()
    for token in EXPECTED_LOCALIZED_CHART_TEXT:
        common.require(
            re.sub(r"\s+", "", token).casefold() in compact,
            f"B025 localized chart required text absent: {token}",
        )
    for phrase in ("Tail area (1 / 500 million)", "is too small to see"):
        common.require(
            phrase.casefold() not in text.casefold(),
            f"B025 localized chart retains English annotation: {phrase}",
        )
    return {
        "localized_chart": {**common.identity(LOCALIZED_CHART), "pages": 1},
        "chart_qa": common.identity(CHART_QA),
        "chart_visual_qa": common.identity(CHART_VISUAL_QA),
        "visible_text_checked": list(EXPECTED_LOCALIZED_CHART_TEXT),
        "visible_english_labels_remaining": 0,
    }


def prepare_custom_texts() -> tuple[dict[Path, str], dict[str, Any]]:
    main = normalized_lf(SOURCE_MAIN)
    common.require(main.count(prior.SCOPE_B024) == 1, "B024 scope block changed")
    main = main.replace(prior.SCOPE_B024, SCOPE_B025)
    common.require(main.count(OLD_B024_NOTE) == 1, "B024 boundary note changed")
    main = main.replace(OLD_B024_NOTE, NEW_B025_NOTE)
    common.require(main.count(OLD_ANSWER_INCLUDE) == 1, "B024 answer include changed")
    main = main.replace(OLD_ANSWER_INCLUDE, NEW_ANSWER_INCLUDE)
    common.require(
        r"\input{ch_inference_for_props/TeX/ch_inference_for_props}" in main,
        "B024 Chapter 6 input changed",
    )
    for forbidden in (
        r"\input{ch_inference_for_means/TeX/ch_inference_for_means}",
        r"\includechapter{7}{ch_inference_for_means}",
    ):
        common.require(forbidden not in main, "Chapter 7 source carry-through entered B025 main")

    chapter = normalized_lf(SOURCE_CHAPTER)
    common.require(chapter.count(OLD_NAV) == 1, "B024 chapter navigation changed")
    chapter = chapter.replace(OLD_NAV, NEW_NAV)
    values = [normalized_lf(SECTION_A), normalized_lf(SECTION_B)]
    expected_breaks = [2, 2]
    for index, (value, count) in enumerate(zip(values, expected_breaks), start=1):
        common.require(value.endswith("\n"), f"B025 section fragment {index} lacks LF")
        common.require(
            value.count(FORCED_BREAK) == count,
            f"B025 section fragment {index} break topology changed",
        )
    values = [value.replace(FORCED_BREAK, REFLOW_NOTE) for value in values]
    common.require(
        chapter.count(PREVIOUS_EXERCISE_INPUT) == 1,
        "B024 Section 6.3 closing exercise input changed",
    )
    chapter = chapter.replace(
        PREVIOUS_EXERCISE_INPUT,
        PREVIOUS_EXERCISE_INPUT + "\n\n" + "".join(values),
        1,
    )
    active_sections = re.findall(r"(?m)^\s*(?!%)\\section\{", chapter)
    common.require(len(active_sections) == 4, "assembled Chapter 6 section count changed")
    for label in (
        "singleProportion",
        "differenceOfTwoProportions",
        "oneWayChiSquare",
        "twoWayTablesAndChiSquare",
    ):
        common.require(
            chapter.count(rf"\label{{{label}}}") == 1,
            f"assembled section label count changed: {label}",
        )
    common.require(
        chapter.count(CURRENT_EXERCISE_INPUT) == 1,
        "B025 exercise input count changed",
    )
    common.require(FORCED_BREAK not in chapter, "legacy Section 6.4 break remained")
    common.require(
        "\\chapter{" not in "\n".join(values),
        "Chapter 7 source carry-through entered B025 fragments",
    )

    staged_exercises = normalized_lf(EXERCISES_ID)
    common.require(
        staged_exercises.startswith(r"\exercisesheader{}" + "\n"),
        "B025 exercise header anchor changed",
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
    common.require(numbers == [35, 36, 37, 38], "B025 exercise sequence changed")
    common.require(new_exercises.count(r"\eoce{") == 4, "B025 exercise count changed")

    old_answers = normalized_lf(SOURCE_ANSWERS)
    closing = "\n\\end{multicols}\n"
    common.require(old_answers.endswith(closing), "B024 answer close anchor changed")
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
        "B025 answer close absent",
    )
    answer_numbers = [
        int(value) for value in re.findall(r"(?m)^% (\d+)\s*$", new_answers)
    ]
    common.require(answer_numbers == [35, 37], "B025 answer sequence changed")

    custom = {
        CUSTOM_MAIN: main,
        CUSTOM_CHAPTER: chapter,
        CUSTOM_EXERCISES_35_38: new_exercises,
        CUSTOM_ANSWERS: answers,
    }
    transforms = {
        "scope_updated": "through Chapter 6, Section 6.4",
        "chapter_navigation_added": "twoWayTablesAndChiSquare",
        "section_6_4_fragments_appended": ["2008-2238", "2239-2434"],
        "exercise_closure": list(range(1, 39)),
        "public_answer_closure": list(range(1, 38, 2)),
        "o001_gap_closure": list(range(2, 39, 2)),
        "legacy_forced_page_breaks_removed": {
            "section_main": 4,
            "section_exercises": 0,
            "total": 4,
        },
        "translation_staging_mutated": False,
        "localized_charts_installed": 1,
        "chapter_7_source_included": False,
        "later_source_counted_as_learner_output": False,
        "restricted_solutions_accessed_or_invented": False,
    }
    return custom, transforms


def install_localized_chart() -> dict[str, Any]:
    chart_gate = verify_chart_gate()
    target = SNAPSHOT / CHART_TARGET_REL
    before = common.identity(target)
    shutil.copy2(LOCALIZED_CHART, target)
    after = common.identity(target)
    assert EXPECTED_LOCALIZED_CHART is not None
    common.require(
        (after["bytes"], after["sha256"]) == EXPECTED_LOCALIZED_CHART,
        "localized iPod chart copy differs",
    )
    return {
        **chart_gate,
        "before": before,
        "installed": after,
    }


def make_custom_sources() -> dict[str, Any]:
    texts, transforms = prepare_custom_texts()
    for path, value in texts.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding="utf-8", newline="\n")
    chart = install_localized_chart()
    return {
        "custom_main": common.identity(CUSTOM_MAIN),
        "custom_chapter": common.identity(CUSTOM_CHAPTER),
        "custom_exercises_35_38": common.identity(CUSTOM_EXERCISES_35_38),
        "custom_answers_1_38_public": common.identity(CUSTOM_ANSWERS),
        "localized_ipod_chart": chart,
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
        rf"\pdftrailerid{{<{seed}><{seed}>}}\input{{main_boundary_clean_b025.tex}}",
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
    common.require(b"\r" not in text.read_bytes(), f"{label} canonical text still contains CR")
    info = (directory / "console-pdfinfo.txt").read_text(
        encoding="utf-8",
        errors="replace",
    )
    match = re.search(r"^Pages:\s+(\d+)", info, re.MULTILINE)
    pages = int(match.group(1)) if match else 0
    common.require(
        253 <= pages <= 440,
        f"{label} page count outside B025 expectation: {pages}",
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
        "multiply_defined_labels": len(re.findall(r"multiply defined", log, re.I)),
        "rerun_required": len(
            re.findall(
                r"Rerun to get cross-references right|Label\(s\) may have changed",
                log,
                re.I,
            )
        ),
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


def write_manifest() -> dict[str, Any]:
    inventory = common.source_inventory(SNAPSHOT)
    raw = "".join(
        f"{name}\t{size}\t{digest}\n"
        for name, size, digest in inventory.pop("rows")
    ).encode("utf-8")
    MANIFEST.write_bytes(raw)
    result = {**common.identity(MANIFEST), **inventory}
    common.require(result["files"] == 1_220, "B025 source snapshot file count changed")
    return result


def reader_language_qa(text_path: Path, expected_pages: int) -> dict[str, Any]:
    raw_bytes = text_path.read_bytes()
    common.require(b"\r" not in raw_bytes, "reader-language QA received noncanonical CR text")
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
        "Menguji independensi dalam tabel dua arah",
        "Cacah harapan dalam tabel dua arah",
        "Uji khi-kuadrat untuk tabel dua arah",
        "Buku teks sumber terbuka",
        "Solusi latihan",
        MODEL,
    )
    missing = [phrase for phrase in required if phrase.casefold() not in joined.casefold()]
    common.require(not missing, f"accepted Indonesian B025 content absent: {missing}")
    return {
        "pages_checked": len(normalized_pages),
        "residual_english_by_phrase": residual,
        "required_phrases": list(required),
        "required_phrases_absent": missing,
        "pagewise_residual_pass": True,
        "chapter_7_source_included": False,
        "later_section_counted_as_learner_output": False,
    }


def probe() -> dict[str, Any]:
    inputs = verify_nonchart_inputs()
    common.require(not BUILD.exists(), "B025 build root already exists")
    staged = verify_staged_fragments()
    texts, transforms = prepare_custom_texts()
    tools = common.find_tools()
    previews = [
        memory_identity(common.rel(path), value) for path, value in texts.items()
    ]
    chart = chart_gate_probe()
    return {
        "boundary_id": BOUNDARY_ID,
        "status": (
            "PASS_STATIC_B025_ASSEMBLY_PREVIEW_EXACT_PUBLIC_B024_BASE_CHART_GATE_READY"
            if chart["ready"]
            else "PASS_STATIC_B025_ASSEMBLY_PREVIEW_EXACT_PUBLIC_B024_BASE_CHART_GATE_PENDING"
        ),
        "inputs": inputs,
        "staged": staged,
        "assembly_preview": previews,
        "assembly_transformations": transforms,
        "chart_gate": chart,
        "tools": sorted(tools),
        "writes_performed": False,
    }


def self_test() -> dict[str, Any]:
    inputs = verify_nonchart_inputs()
    common.require(not BUILD.exists(), "B025 build root already exists")
    staged = verify_staged_fragments()
    chart = verify_chart_gate()
    texts, transforms = prepare_custom_texts()
    tools = common.find_tools()
    previews = [
        memory_identity(common.rel(path), value) for path, value in texts.items()
    ]
    return {
        "boundary_id": BOUNDARY_ID,
        "status": "PASS_INERT_EXACT_INPUTS_STAGING_CHART_ASSEMBLY_AND_TOOLCHAIN_BOUND",
        "inputs": inputs,
        "staged": {**staged, "localized_ipod_chart": chart},
        "assembly_preview": previews,
        "assembly_transformations": transforms,
        "tools": sorted(tools),
        "writes_performed": False,
    }


def execute() -> dict[str, Any]:
    inputs = verify_nonchart_inputs()
    staged = verify_staged_fragments()
    chart = verify_chart_gate()
    common.require(not BUILD.exists(), "refusing to overwrite B025 build root")
    BUILD.mkdir(parents=True)
    shutil.copytree(SOURCE, SNAPSHOT)
    custom = make_custom_sources()
    manifest = write_manifest()
    tools = common.find_tools()
    seed = manifest["sha256"][:32].upper()
    run_a = build_once("replay-a", RUN_A, tools, seed)
    run_b = build_once("replay-b", RUN_B, tools, seed)
    common.require(run_a["pages"] == run_b["pages"], "B025 replay page counts differ")
    common.require(
        run_a["pdf"]["sha256"] == run_b["pdf"]["sha256"],
        "B025 replay PDFs differ",
    )
    common.require(
        run_a["text"]["sha256"] == run_b["text"]["sha256"],
        "B025 replay text differs",
    )
    common.require(
        run_a["trailer_ids"] == run_b["trailer_ids"],
        "B025 replay trailer IDs differ",
    )
    FINAL.mkdir()
    shutil.copy2(RUN_A / "main.pdf", FINAL_PDF)
    shutil.copy2(RUN_A / "main-final.txt", FINAL_TEXT)
    language = reader_language_qa(FINAL_TEXT, run_a["pages"])
    receipt = {
        "$schema": "interlanguage.r011-b025-boundary-clean-reader-build/v1",
        "boundary_id": BOUNDARY_ID,
        "status": (
            "PASS_TWO_REPLAY_DETERMINISTIC_BOUNDARY_CLEAN_BUILD_"
            "LANGUAGE_QA_COMPLETE_READER_VISUAL_QA_PENDING"
        ),
        "included_scope": (
            "All admitted and publicly verified B024 Indonesian learner work, "
            "plus complete Chapter 6 Section 6.4; exercises 35-38; public "
            "answers 35 and 37. Aggregate closure is exercises 1-38 and public "
            "odd answers 1-37."
        ),
        "excluded_untranslated_scope": [
            "Chapter 6 even answers 2-38, recorded as explicit O001 gaps",
            "Chapter 7 onward",
            "untranslated data, table, and index appendices not visible in the learner reader",
            "restricted instructor solutions",
        ],
        "inputs": inputs,
        "staged": {**staged, "localized_ipod_chart": chart},
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
        "chart_qa": common.identity(CHART_QA),
        "chart_visual_qa": common.identity(CHART_VISUAL_QA),
        "translation_provenance": MODEL,
        "complete_corpus": False,
        "source_closure_counted_as_learner_output": False,
        "restricted_solutions_accessed_or_invented": False,
        "next_cursor": {
            "boundary_id": "R011-B026",
            "path": "ch_inference_for_means/TeX/ch_inference_for_means.tex",
            "first_instructional_line": 1,
            "chapter_label": "ch_inference_for_means",
            "chapter_label_line": 4,
            "first_section_line": 29,
            "first_section_label": "oneSampleMeansWithTDistribution",
            "first_section_label_line": 32,
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
            "usage: build_b025_boundary_clean_reader.py --probe | --self-test | --build"
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
                    "chart_gate",
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
