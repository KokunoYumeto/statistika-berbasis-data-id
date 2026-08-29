#!/usr/bin/env python3
"""Deterministic pagewise language, structure, and visual-QA binding for R011-B022.

The read-only modes (``--self-check``, ``--check-build``, ``--scan``, and
``--visual-schema``) never create or alter artifacts.  ``--finalize`` is the
only writing mode.  It refuses to run until an exact all-page visual receipt
for the frozen v3 reader exists and passes the embedded contract.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

import build_b022_boundary_clean_reader as builder
import qa_b021_boundary_clean_reader as prior


ROOT = Path(__file__).resolve().parents[1]
BOUNDARY_ID = "R011-B022"
MODEL_PROVENANCE = "OpenAI Codex gpt-5.6-sol, Ultra"
UPSTREAM_COMMIT = "fee25091fb24e89c36296fd67c48c1fcf7a93b6e"

BUILD_ROOT = ROOT / "scratch/b022-boundary-clean-reader"
SOURCE_SNAPSHOT = BUILD_ROOT / "source-snapshot"
CANDIDATE_PDF = BUILD_ROOT / "final/main.pdf"
TEXT = BUILD_ROOT / "final/main-final.txt"
BUILD_QA = BUILD_ROOT / "final/R011-B022_BOUNDARY_CLEAN_BUILD_QA.json"
SOURCE_MANIFEST = BUILD_ROOT / "R011-B022_BOUNDARY_CLEAN_SOURCE_MANIFEST.tsv"

QA_DIR = ROOT / "qa/b022-reader"
QA_JSON = QA_DIR / "R011-B022_PAGEWISE_LANGUAGE_QA.json"
QA_TSV = QA_DIR / "R011-B022_PAGEWISE_LANGUAGE_QA.tsv"
VISUAL_QA = QA_DIR / "R011-B022_VISUAL_QA.json"

BLUEPRINT = ROOT / "qa/b022-source/R011-B022_BOUNDARY_BLUEPRINT.json"
STAGING = ROOT / "qa/b022-translation/staging"
FRONT = STAGING / "ch_inference_for_props_1-28.id.tex"
SECTION_A = STAGING / "ch_inference_for_props_29-205.id.tex"
SECTION_B = STAGING / "ch_inference_for_props_206-324.id.tex"
SECTION_C = STAGING / "ch_inference_for_props_325-548.id.tex"
AUDIT_FRONT = STAGING / "ch_inference_for_props_1-28.id.audit.json"
AUDIT_A = STAGING / "ch_inference_for_props_29-205.id.audit.json"
AUDIT_B = STAGING / "ch_inference_for_props_206-324.id.audit.json"
AUDIT_C = STAGING / "ch_inference_for_props_325-548.id.audit.json"
EXERCISES = STAGING / "inference_for_a_single_proportion.id.tex"
ANSWERS = STAGING / "eoceSolutions_b022_public_odd.id.tex"
EXERCISE_AUDIT = STAGING / "R011-B022_EXERCISES_ANSWERS_TRANSLATION_AUDIT.json"

BUILDER_V1 = ROOT / "scripts/build_b022_boundary_clean_reader.py"
BUILDER_V2 = ROOT / "scripts/build_b022_boundary_clean_reader_v2.py"
BUILDER_V3 = ROOT / "scripts/build_b022_boundary_clean_reader_v3.py"
V1_DIAGNOSIS = QA_DIR / "R011-B022_V1_FAILED_BUILD_DIAGNOSIS.json"
V2_DIAGNOSIS = QA_DIR / "R011-B022_V2_VISUAL_DEFECT_DIAGNOSIS.json"

EXPECTED_BUILD_STATUS = (
    "PASS_TWO_REPLAY_DETERMINISTIC_BOUNDARY_CLEAN_BUILD_LANGUAGE_AND_VISUAL_QA_PENDING"
)
EXPECTED_SCOPE = (
    "Indonesian front matter and Chapters 1-5 through Section 5.3, plus the Chapter 6 front "
    "and Section 6.1 with exercises 1-16 and upstream-public odd answers 1-15."
)
EXPECTED_O001_EXCLUSION = (
    "Chapter 6 even answers 2-16 (not present in the public source; O001 gaps)"
)
EXPECTED_PUBLIC_ANSWERS = list(range(1, 16, 2))
EXPECTED_O001_GAPS = list(range(2, 17, 2))

# Exact accepted source, translation, builder, and adverse-evidence witnesses.
FROZEN_INPUT_IDENTITIES: dict[str, tuple[int, str]] = {
    "qa/b022-source/R011-B022_BOUNDARY_BLUEPRINT.json": (12_523, "998906deec9cfea6a36b6e202af674c1a381141402448706c6ba1988caf45db5"),
    "qa/b022-translation/staging/ch_inference_for_props_1-28.id.tex": (1_079, "0ba54437f034767168bc9ceb9abf7bcc99dc684dd78d328d19b13c9f1af6f774"),
    "qa/b022-translation/staging/ch_inference_for_props_1-28.id.audit.json": (1_175, "d00c90fee5eccef5cf072142ec7e7d2cecf06234f69fc7fc346fa685e67f4428"),
    "qa/b022-translation/staging/ch_inference_for_props_29-205.id.tex": (6_761, "ed854514ad0cccaf3dcf09e4aa3aeb3d45ff10305bd761ed14f97248858955cc"),
    "qa/b022-translation/staging/ch_inference_for_props_29-205.id.audit.json": (5_103, "a13c688bdad46beedf9ec970419c575ad6f8db5459ec5a35b8b8f1262396be57"),
    "qa/b022-translation/staging/ch_inference_for_props_206-324.id.tex": (4_649, "a54b3b69bc7ba8805f9d12756f692a4891f6dca2f71036cd663bd2868194065b"),
    "qa/b022-translation/staging/ch_inference_for_props_206-324.id.audit.json": (6_138, "ffd84f49a26c1fbc27c9743c80ccbb8f0677ae93e1117bf3f03d13b4d2add823"),
    "qa/b022-translation/staging/ch_inference_for_props_325-548.id.tex": (9_449, "424b7eb9f013b40cd4ca16aaf2113f95fbcd7912a1c37dcb5c766846cf4fb407"),
    "qa/b022-translation/staging/ch_inference_for_props_325-548.id.audit.json": (4_698, "4aceefadb84208bff1eb82e6a5d98129046c5ab68a32d8e6a5c88726a85b8dc3"),
    "qa/b022-translation/staging/inference_for_a_single_proportion.id.tex": (14_246, "20e72133e3111f175fd4bf7ceaad63dbb278723a796a8e5b8f16027bdd05309c"),
    "qa/b022-translation/staging/eoceSolutions_b022_public_odd.id.tex": (5_595, "3b03a246c771c66b17f4a8cd69168eb156d0799caaaa72d0ee24782318f720fa"),
    "qa/b022-translation/staging/R011-B022_EXERCISES_ANSWERS_TRANSLATION_AUDIT.json": (5_583, "9b6d172fb440a04593b431dcb51cd5447655e4218d665daf955624cf7767ac0c"),
    "scripts/build_b022_boundary_clean_reader.py": (31_512, "d7d7d9a785546fcb491ed2ae18ad473b6ca28001d4f559f733c811f4fb9b1460"),
    "scripts/build_b022_boundary_clean_reader_v2.py": (2_701, "5daef4d5d2869f97be7a0c61724713f41f351009af79e4cec996fe9f56cc0c22"),
    "scripts/build_b022_boundary_clean_reader_v3.py": (1_783, "59d4093d7228bc3c39607e9357d7d2d6838c58338c36fb022c938ce5ca06a4a8"),
    "qa/b022-reader/R011-B022_V1_FAILED_BUILD_DIAGNOSIS.json": (1_670, "5a036fbdb76762668544356d065d0578c52452462e08d6047fb849a2c360fd86"),
    "qa/b022-reader/R011-B022_V2_VISUAL_DEFECT_DIAGNOSIS.json": (1_062, "38c77e36d68623d0b137bdfbbbd4de7552f18e0626ade2217bb1cd60fa747e7c"),
}

EXPECTED_BUILD_IDENTITIES: dict[Path, tuple[int, str]] = {
    CANDIDATE_PDF: (10_460_483, "6e238f9c80d7789eab17341f743278ad3a69f3bf1dbd8c573cf4edb2d9733bc7"),
    TEXT: (735_168, "e8497958a8b1b7a24899cf6fab2e7589582e34ab92d8988e8836994daa2b55b2"),
    BUILD_QA: (10_815, "da11d204b3dd3b2142321934dfcae5ee8239d52088f40e6a92f1a9d2d88c4c97"),
    SOURCE_MANIFEST: (176_510, "56a0f05f56568f3ba4737cfc326f7ca1128777eeb1081c1110e057680a8e5619"),
}

REQUIRED_SOURCE_MANIFEST_PATHS = {
    ".gitignore",
    "LICENSE.md",
    "README.md",
    "main_boundary_clean_b022.tex",
    "ch_inference_for_props/TeX/ch_inference_for_props.tex",
    "ch_inference_for_props/TeX/inference_for_a_single_proportion.tex",
    "extraTeX/eoceSolutions/eoceSolutions_boundary_clean_b022.tex",
    "ch_inference_for_props/figures/paydayCC_norm_pvalue/paydayCC_norm_pvalue.pdf",
}

REQUIRED_HEADINGS = [
    "Inferensi untuk data kategoris",
    "Inferensi untuk satu proporsi",
    "Mengidentifikasi kapan proporsi sampel mendekati normal",
    "Interval kepercayaan untuk suatu proporsi",
    "Uji hipotesis untuk suatu proporsi",
    "Ketika satu atau beberapa syarat tidak terpenuhi",
    "Memilih ukuran sampel ketika mengestimasi suatu proporsi",
]

EXERCISE_TITLES = {
    1: "Mahasiswa vegetarian",
    2: "Kaum muda Amerika, Bagian I",
    3: "Kucing tabi jingga",
    4: "Kaum muda Amerika, Bagian II",
    5: "Kesetaraan gender",
    6: "Pengemudi lanjut usia",
    7: "Kembang api pada 4 Juli",
    8: "Penilaian kehidupan di Yunani",
    9: "Belajar di luar negeri",
    10: "Legalisasi ganja, Bagian I",
    11: "Rencana Kesehatan Nasional, Bagian I",
    12: "Apakah kuliah sepadan? Bagian I",
    13: "Uji rasa",
    14: "Apakah kuliah sepadan? Bagian II",
    15: "Rencana Kesehatan Nasional, Bagian II",
    16: "Legalisasi ganja, Bagian II",
}

# Exact flags in the frozen v3 text.  Every flagged page has an explicit
# disposition; any added or missing flag is a review event, not an auto-pass.
EXPECTED_HEURISTIC_FLAGGED_PAGES = [
    11, 19, 20, 31, 32, 36, 37, 38, 39, 56, 71, 76, 77, 85, 86, 97,
    107, 110, 111, 112, 113, 114, 115, 159, 206, 207, 216, 217, 218,
]
CITATION_OR_TITLE_PAGES = {
    11, 19, 31, 32, 36, 37, 38, 39, 56, 71, 76, 77, 97, 113, 114, 115,
    159, 216, 217, 218,
}
DATA_AND_CITATION_PAGES = {20}
MATH_SYMBOL_PAGES = {85, 86, 110, 111, 112}
DATA_IDENTIFIER_PAGES = {107}

FORBIDDEN_RESIDUALS = {
    name: pattern
    for name, pattern in prior.FORBIDDEN_RESIDUALS.items()
    if name != "excluded_chapter_6_indonesian"
}
FORBIDDEN_RESIDUALS.update({
    "english_section_6_1": re.compile(r"(?i)Inference\s+for\s+a\s+single\s+proportion"),
    "english_nearly_normal": re.compile(r"(?i)Identifying\s+when\s+the\s+sample\s+proportion\s+is\s+nearly\s+normal"),
    "english_conditions_not_met": re.compile(r"(?i)When\s+one\s+or\s+more\s+conditions\s+aren['’]t\s+met"),
    "english_sample_size": re.compile(r"(?i)Choosing\s+a\s+sample\s+size\s+when\s+estimating\s+a\s+proportion"),
    "english_independence_condition": re.compile(r"(?i)\bindependence\s+condition\b"),
    "english_success_failure_condition": re.compile(r"(?i)\bsuccess[-–— ]+failure\s+condition\b"),
    "english_sample_proportion": re.compile(r"(?i)\bsample\s+proportion\b"),
    "english_population_proportion": re.compile(r"(?i)\bpopulation\s+proportion\b"),
    "english_null_value": re.compile(r"(?i)\bnull\s+value\b"),
    "english_difference_two_proportions": re.compile(r"(?i)Difference\s+of\s+two\s+proportions"),
    "english_sampling_difference_two": re.compile(r"(?i)Sampling\s+distribution\s+of\s+the\s+difference\s+of\s+two\s+proportions"),
    "english_chi_square_gof": re.compile(r"(?i)Chi-square\s+goodness\s+of\s+fit\s+test"),
    "english_chi_square_independence": re.compile(r"(?i)Chi-square\s+test\s+of\s+independence"),
    "excluded_indonesian_section_6_2": re.compile(r"(?im)^\s*6\.2\s+Selisih\s+dua\s+proporsi\s*$"),
    "english_b022_exercise_1": re.compile(r"(?im)^\s*6\.1\s+Vegetarian\s+college\s+students\b"),
    "english_b022_exercise_2": re.compile(r"(?im)^\s*6\.2\s+Young\s+Americans,?\s+Part\s+I\b"),
    "english_b022_exercise_3": re.compile(r"(?im)^\s*6\.3\s+Orange\s+tabbies\b"),
    "english_b022_exercise_4": re.compile(r"(?im)^\s*6\.4\s+Young\s+Americans,?\s+Part\s+II\b"),
    "english_b022_exercise_5": re.compile(r"(?im)^\s*6\.5\s+Gender\s+equality\b"),
    "english_b022_exercise_6": re.compile(r"(?im)^\s*6\.6\s+Elderly\s+drivers\b"),
    "english_b022_exercise_7": re.compile(r"(?im)^\s*6\.7\s+Fireworks\s+on\s+July\b"),
    "english_b022_exercise_8": re.compile(r"(?im)^\s*6\.8\s+Life\s+rating\s+in\s+Greece\b"),
    "english_b022_exercise_9": re.compile(r"(?im)^\s*6\.9\s+Study\s+abroad\b"),
    "english_b022_exercise_10": re.compile(r"(?im)^\s*6\.10\s+Legalization\s+of\s+marijuana,?\s+Part\s+I\b"),
    "english_b022_exercise_11": re.compile(r"(?im)^\s*6\.11\s+National\s+Health\s+Plan,?\s+Part\s+I\b"),
    "english_b022_exercise_12": re.compile(r"(?im)^\s*6\.12\s+Is\s+college\s+worth\s+it\?\s+Part\s+I\b"),
    "english_b022_exercise_13": re.compile(r"(?im)^\s*6\.13\s+Taste\s+test\b"),
    "english_b022_exercise_14": re.compile(r"(?im)^\s*6\.14\s+Is\s+college\s+worth\s+it\?\s+Part\s+II\b"),
    "english_b022_exercise_15": re.compile(r"(?im)^\s*6\.15\s+National\s+Health\s+Plan,?\s+Part\s+II\b"),
    "english_b022_exercise_16": re.compile(r"(?im)^\s*6\.16\s+Legali[sz](?:e|ation\s+of)\s+Marijuana,?\s+Part\s+II\b"),
})

REQUIRED_LOCALIZED = dict(prior.REQUIRED_LOCALIZED)
REQUIRED_LOCALIZED.update({
    "chapter_6": re.compile(r"(?i)Inferensi\s+untuk\s+data\s+kategoris"),
    "section_6_1": re.compile(r"(?i)Inferensi\s+untuk\s+satu\s+proporsi"),
    "nearly_normal": re.compile(r"(?i)Mengidentifikasi\s+kapan\s+proporsi\s+sampel\s+mendekati\s+normal"),
    "conditions_not_met": re.compile(r"(?i)Ketika\s+satu\s+atau\s+beberapa\s+syarat\s+tidak\s+terpenuhi"),
    "choose_sample_size": re.compile(r"(?i)Memilih\s+ukuran\s+sampel\s+ketika\s+mengestimasi\s+suatu\s+proporsi"),
    "independence_condition": re.compile(r"(?i)syarat\s+independensi"),
    "sample_proportion": re.compile(r"(?i)proporsi\s+sampel"),
    "population_proportion": re.compile(r"(?i)proporsi\s+populasi"),
    "null_value": re.compile(r"(?i)nilai\s+nol"),
    "margin_of_error": re.compile(r"(?i)batas\s+galat"),
    "confidence_level": re.compile(r"(?i)tingkat\s+kepercayaan"),
    "normal_distribution": re.compile(r"(?i)distribusi\s+normal"),
    "o001_scope": re.compile(r"(?i)kesenjangan\s+pendamping\s+kemahiran\s+O001"),
})

WORD = prior.WORD
ENGLISH = prior.ENGLISH
INDONESIAN = prior.INDONESIAN
HEX256 = prior.HEX256

ALLOWED_NEW_FLAG_LINES = list(prior.ALLOWED_NEW_FLAG_LINES) + [
    re.compile(r"(?i)Demos\.org|Gallup\s+World|studentPOLL|Kaiser\s+Family\s+Foundation"),
]

IDENTITY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["path", "bytes", "sha256"],
    "additionalProperties": False,
    "properties": {
        "path": {"type": "string", "minLength": 1},
        "bytes": {"type": "integer", "minimum": 0},
        "sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
    },
}

VISUAL_QA_RECEIPT_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "interlanguage.r011-b022-visual-qa.schema/v1",
    "title": "R011-B022 all-page visual QA receipt",
    "type": "object",
    "required": [
        "$schema", "boundary_id", "status", "page_count", "defect_count",
        "all_pages_inspected", "inspection_method", "render", "learner_pdf",
        "specific_findings", "defects", "pagewise_dispositions", "contact_sheets",
        "original_scale_checks", "page_count_is_artifact_extent_not_translation_progress",
    ],
    "additionalProperties": True,
    "properties": {
        "$schema": {"const": "interlanguage.r011-b022-visual-qa/v1"},
        "boundary_id": {"const": BOUNDARY_ID},
        "status": {"const": "PASS_ALL_230_PAGES_VISUALLY_INSPECTED_ZERO_DEFECTS"},
        "page_count": {"const": 230},
        "defect_count": {"const": 0},
        "all_pages_inspected": {"const": True},
        "inspection_method": {"type": "object"},
        "render": {
            "type": "object", "required": ["rendered_page_count"],
            "properties": {"rendered_page_count": {"const": 230}},
        },
        "learner_pdf": IDENTITY_SCHEMA,
        "specific_findings": {
            "type": "object",
            "required": ["chapter_6_title_reflow", "section_6_1", "exercise_flow", "chapter_6_answers", "numeric_figure"],
        },
        "defects": {"type": "array", "maxItems": 0},
        "pagewise_dispositions": {"type": "array", "minItems": 230, "maxItems": 230},
        "contact_sheets": {"type": "array", "minItems": 1},
        "original_scale_checks": {"type": "array", "minItems": 7},
        "page_count_is_artifact_extent_not_translation_progress": {"const": True},
    },
}


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def identity(path: Path) -> dict[str, object]:
    value = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(value), "sha256": sha256_bytes(value)}


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"missing QA input: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"expected JSON object in {path}")
    return value


def require_exact(path: Path, expected: tuple[int, str]) -> dict[str, object]:
    if not path.is_file():
        raise RuntimeError(f"missing frozen input: {path}")
    observed = identity(path)
    if (observed["bytes"], observed["sha256"]) != expected:
        raise RuntimeError(f"frozen input identity changed: {observed}")
    return observed


def canonical_identity_record(value: Any, context: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != {"path", "bytes", "sha256"}:
        raise RuntimeError(f"{context} is not an exact identity object")
    path, byte_count, digest = value.get("path"), value.get("bytes"), value.get("sha256")
    if not isinstance(path, str) or not path:
        raise RuntimeError(f"{context} has invalid path")
    if not isinstance(byte_count, int) or byte_count < 0:
        raise RuntimeError(f"{context} has invalid byte count")
    if not isinstance(digest, str) or not HEX256.fullmatch(digest):
        raise RuntimeError(f"{context} has invalid SHA-256")
    return {"path": path, "bytes": byte_count, "sha256": digest}


def path_from_record(record: dict[str, object], context: str) -> Path:
    relative = PurePosixPath(str(record["path"]))
    if relative.is_absolute() or ".." in relative.parts:
        raise RuntimeError(f"unsafe path in {context}: {relative}")
    path = ROOT.joinpath(*relative.parts)
    try:
        path.resolve().relative_to(ROOT.resolve())
    except ValueError as exc:
        raise RuntimeError(f"path escapes corpus root in {context}: {relative}") from exc
    return path


def require_record_matches_file(record: Any, expected_path: Path, context: str) -> dict[str, object]:
    canonical = canonical_identity_record(record, context)
    observed = identity(expected_path)
    if canonical != observed:
        raise RuntimeError(f"{context} does not match on-disk bytes: {canonical} != {observed}")
    return canonical


def validate_artifact_record(record: Any, context: str) -> dict[str, object]:
    canonical = canonical_identity_record(record, context)
    path = path_from_record(canonical, context)
    if not path.is_file() or identity(path) != canonical:
        raise RuntimeError(f"{context} byte identity does not match its file: {canonical}")
    return canonical


def same_payload(left: Any, right: Any, context: str) -> None:
    left_id = canonical_identity_record(left, f"{context} left")
    right_id = canonical_identity_record(right, f"{context} right")
    if (left_id["bytes"], left_id["sha256"]) != (right_id["bytes"], right_id["sha256"]):
        raise RuntimeError(f"payload identity mismatch for {context}: {left_id} != {right_id}")


def frozen_records() -> list[dict[str, object]]:
    return [identity(ROOT / relative) for relative in FROZEN_INPUT_IDENTITIES]


def _audit_target_matches(audit_path: Path, target_path: Path) -> None:
    audit = load_json(audit_path)
    if audit.get("status") != "PASS_TRANSLATION_AND_PROTECTED_TEX_CLOSURE":
        raise RuntimeError(f"translation audit is not PASS: {audit_path}")
    if audit.get("boundary", audit.get("boundary_id")) != BOUNDARY_ID:
        raise RuntimeError(f"translation audit boundary changed: {audit_path}")
    target = audit.get("target")
    if not isinstance(target, dict):
        raise RuntimeError(f"translation audit target missing: {audit_path}")
    observed = identity(target_path)
    if target.get("path") != observed["path"] or target.get("sha256") != observed["sha256"]:
        raise RuntimeError(f"translation audit target identity is stale: {audit_path}")
    if target.get("bytes", target.get("bytes_utf8")) != observed["bytes"]:
        raise RuntimeError(f"translation audit target byte count is stale: {audit_path}")


def validate_frozen_inputs() -> dict[str, object]:
    records = [require_exact(ROOT / relative, expected) for relative, expected in FROZEN_INPUT_IDENTITIES.items()]

    # Reuse the builder's independent source-snapshot, source-slice, rights,
    # figure, exercise, answer, and audit closure.  Its own bytes are frozen
    # above, so this cannot silently change the contract.
    builder_closure = builder.verify_inputs()

    blueprint = load_json(BLUEPRINT)
    if blueprint.get("boundary_id") != BOUNDARY_ID:
        raise RuntimeError("B022 blueprint boundary changed")
    if blueprint.get("status") != "PASS_SOURCE_ASSET_RIGHTS_AND_BOUNDARY_DEPENDENCY_CLOSURE":
        raise RuntimeError("B022 blueprint closure is not PASS")
    if blueprint.get("authority", {}).get("commit") != UPSTREAM_COMMIT:
        raise RuntimeError("B022 blueprint authority commit changed")
    main_source = blueprint.get("main_source", {})
    if (main_source.get("start_line"), main_source.get("end_line"), main_source.get("start_label")) != (29, 548, "singleProportion"):
        raise RuntimeError("B022 main-source boundary changed")
    closure = blueprint.get("exercise_answer_closure", {})
    if closure.get("exercise_ids") != list(range(1, 17)):
        raise RuntimeError("B022 exercise closure changed")
    if closure.get("public_answer_ids") != EXPECTED_PUBLIC_ANSWERS:
        raise RuntimeError("B022 public-answer closure changed")
    if closure.get("o001_gap_ids") != EXPECTED_O001_GAPS:
        raise RuntimeError("B022 O001 closure changed")
    if closure.get("restricted_solutions_accessed_or_invented") is not False:
        raise RuntimeError("B022 restricted/invented solution boundary changed")
    post = blueprint.get("post_boundary_cursor", {})
    if (post.get("working_boundary_id"), post.get("line"), post.get("label")) != ("R011-B023", 555, "differenceOfTwoProportions"):
        raise RuntimeError("B022 post-boundary cursor changed")

    for audit_path, target_path in ((AUDIT_FRONT, FRONT), (AUDIT_A, SECTION_A), (AUDIT_B, SECTION_B), (AUDIT_C, SECTION_C)):
        _audit_target_matches(audit_path, target_path)

    exercise_audit = load_json(EXERCISE_AUDIT)
    if exercise_audit.get("boundary_id") != BOUNDARY_ID or exercise_audit.get("status") != "PASS_EXERCISES_1_16_AND_ALL_LINKED_PUBLIC_ODD_ANSWERS_TRANSLATED":
        raise RuntimeError("B022 exercise/public-answer translation audit is not PASS")
    targets = exercise_audit.get("targets")
    if not isinstance(targets, list):
        raise RuntimeError("B022 exercise/public-answer audit targets missing")
    target_records = {str(item.get("path")): item for item in targets if isinstance(item, dict)}
    for target_path in (EXERCISES, ANSWERS):
        observed = identity(target_path)
        recorded = target_records.get(str(observed["path"]))
        if not isinstance(recorded, dict) or recorded.get("bytes") != observed["bytes"] or recorded.get("sha256") != observed["sha256"]:
            raise RuntimeError(f"B022 exercise/public-answer target identity is stale: {target_path}")
    answer_closure = exercise_audit.get("answer_closure", {})
    if answer_closure.get("exercise_ordinals") != list(range(1, 17)):
        raise RuntimeError("audited B022 exercise sequence changed")
    if answer_closure.get("public_answer_ordinals") != EXPECTED_PUBLIC_ANSWERS:
        raise RuntimeError("audited B022 public-answer sequence changed")
    if answer_closure.get("o001_mastery_gaps") != EXPECTED_O001_GAPS:
        raise RuntimeError("audited B022 O001 sequence changed")
    if answer_closure.get("invented_answers_or_solutions") != 0 or answer_closure.get("restricted_instructor_solutions_used") != 0:
        raise RuntimeError("B022 audit records invented or restricted solutions")

    chapter_text = "\n".join(path.read_text(encoding="utf-8") for path in (FRONT, SECTION_A, SECTION_B, SECTION_C))
    tex_heading_counts = {
        heading: len(re.findall(rf"\\(?:begin\{{chapterpage\}}|section|subsection)\{{{re.escape(heading)}\}}", chapter_text))
        for heading in REQUIRED_HEADINGS
    }
    if any(count != 1 for count in tex_heading_counts.values()):
        raise RuntimeError(f"B022 accepted TeX heading closure changed: {tex_heading_counts}")

    exercise_text = EXERCISES.read_text(encoding="utf-8")
    answer_text = ANSWERS.read_text(encoding="utf-8")
    exercise_ids = [int(value) for value in re.findall(r"(?m)^%\s+(\d+)\s*$", exercise_text)]
    answer_ids = [int(value) for value in re.findall(r"(?m)^%\s+(\d+)\s*$", answer_text)]
    if exercise_ids != list(range(1, 17)) or exercise_text.count(r"\eoce{") != 16:
        raise RuntimeError(f"B022 exercise sequence changed: {exercise_ids}")
    if answer_ids != EXPECTED_PUBLIC_ANSWERS or answer_text.count(r"\eocesol{") != 8:
        raise RuntimeError(f"B022 public-answer sequence changed: {answer_ids}")

    v1 = load_json(V1_DIAGNOSIS)
    if v1.get("boundary_id") != BOUNDARY_ID or v1.get("status") != "REFUSED_TERMINAL_UNDEFINED_REFERENCES":
        raise RuntimeError("v1 adverse build diagnosis changed")
    if v1.get("builder") != identity(BUILDER_V1):
        raise RuntimeError("v1 adverse build diagnosis no longer binds the exact v1 builder")
    if v1.get("terminal_gate", {}).get("undefined_references") != 25:
        raise RuntimeError("v1 undefined-reference evidence changed")
    if "build_b022_boundary_clean_reader_v2.py" not in str(v1.get("remedy", "")):
        raise RuntimeError("v1 remedy no longer points to the v2 counter repair")

    v2 = load_json(V2_DIAGNOSIS)
    if v2.get("boundary_id") != BOUNDARY_ID or v2.get("status") != "REJECTED_VISUAL_TITLE_ORPHAN" or v2.get("page") != 208:
        raise RuntimeError("v2 visual-defect diagnosis changed")
    rejected = v2.get("candidate", {})
    if (rejected.get("bytes"), rejected.get("sha256"), rejected.get("pages")) != (
        10_460_495, "d265e429f296a85d88eeee0564b3c99e00e0f61e1463f9969f706142cfc53b0f", 230
    ):
        raise RuntimeError("v2 rejected-candidate identity changed")
    remedy = v2.get("remedy", {})
    if remedy.get("builder") != "scripts/build_b022_boundary_clean_reader_v3.py" or remedy.get("accepted_translation_staging_mutated") is not False:
        raise RuntimeError("v2 visual-defect remedy changed")

    json.dumps(VISUAL_QA_RECEIPT_SCHEMA, ensure_ascii=False, sort_keys=True)
    return {
        "status": "PASS_B022_FROZEN_INPUTS_BUILDERS_DIAGNOSES_AND_QA_CONTRACT",
        "boundary_id": BOUNDARY_ID,
        "frozen_input_count": len(records),
        "frozen_inputs": records,
        "builder_source_closure": builder_closure,
        "tex_heading_counts": tex_heading_counts,
        "exercise_ids": exercise_ids,
        "public_answer_ids": answer_ids,
        "o001_gap_ids": EXPECTED_O001_GAPS,
        "visual_receipt_schema_id": VISUAL_QA_RECEIPT_SCHEMA["$id"],
        "built_pdf_required": False,
    }


def parse_source_manifest() -> tuple[list[dict[str, object]], dict[str, object]]:
    require_exact(SOURCE_MANIFEST, EXPECTED_BUILD_IDENTITIES[SOURCE_MANIFEST])
    raw = SOURCE_MANIFEST.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RuntimeError("B022 source manifest is not UTF-8") from exc
    if "\r" in text:
        raise RuntimeError("B022 source manifest must use LF line endings")
    rows: list[dict[str, object]] = []
    seen: set[str] = set()
    for line_number, line in enumerate(text.splitlines(), 1):
        fields = line.split("\t")
        if len(fields) != 3:
            raise RuntimeError(f"malformed source-manifest row {line_number}: {line!r}")
        relative, raw_bytes, digest = fields
        pure = PurePosixPath(relative)
        if not relative or pure.is_absolute() or ".." in pure.parts or pure.as_posix() != relative:
            raise RuntimeError(f"unsafe/noncanonical source-manifest path on row {line_number}: {relative!r}")
        if relative in seen:
            raise RuntimeError(f"duplicate source-manifest path: {relative}")
        seen.add(relative)
        try:
            byte_count = int(raw_bytes)
        except ValueError as exc:
            raise RuntimeError(f"invalid source-manifest byte count on row {line_number}") from exc
        if byte_count < 0 or not HEX256.fullmatch(digest):
            raise RuntimeError(f"invalid source-manifest identity on row {line_number}")
        rows.append({"path": relative, "bytes": byte_count, "sha256": digest})
    paths = [str(row["path"]) for row in rows]
    if paths != sorted(paths):
        raise RuntimeError("B022 source manifest is not deterministically sorted")
    missing_required = sorted(REQUIRED_SOURCE_MANIFEST_PATHS - set(paths))
    if missing_required:
        raise RuntimeError(f"required B022 source-manifest entries missing: {missing_required}")
    return rows, identity(SOURCE_MANIFEST)


def validate_source_manifest(build: dict[str, Any]) -> dict[str, object]:
    rows, manifest_id = parse_source_manifest()
    record = build.get("source_manifest")
    if not isinstance(record, dict):
        raise RuntimeError("build receipt source_manifest is missing")
    if record.get("path") != manifest_id["path"] or record.get("sha256") != manifest_id["sha256"]:
        raise RuntimeError("build receipt binds the wrong B022 source manifest")
    if record.get("inventory_sha256") != manifest_id["sha256"]:
        raise RuntimeError("B022 inventory SHA-256 is not the manifest byte hash")
    if record.get("files") != len(rows) or record.get("files") != 1_214:
        raise RuntimeError("B022 source-manifest file count changed")
    aggregate = sum(int(row["bytes"]) for row in rows)
    if record.get("bytes") != aggregate or aggregate != 41_601_621:
        raise RuntimeError("B022 aggregate source byte count changed")

    actual_files = sorted(
        path.relative_to(SOURCE_SNAPSHOT).as_posix()
        for path in SOURCE_SNAPSHOT.rglob("*") if path.is_file()
    )
    manifest_paths = [str(row["path"]) for row in rows]
    if actual_files != manifest_paths:
        raise RuntimeError("B022 source snapshot/manifest file set differs")
    for row in rows:
        path = SOURCE_SNAPSHOT.joinpath(*PurePosixPath(str(row["path"])).parts)
        value = path.read_bytes()
        if len(value) != row["bytes"] or sha256_bytes(value) != row["sha256"]:
            raise RuntimeError(f"B022 source snapshot byte identity differs: {row['path']}")
    return {
        "manifest": manifest_id,
        "entry_count": len(rows),
        "aggregate_source_bytes": aggregate,
        "required_entry_count": len(REQUIRED_SOURCE_MANIFEST_PATHS),
        "required_entries_present": True,
        "snapshot_file_set_exact": True,
        "every_entry_byte_verified": True,
    }


def load_pages() -> list[str]:
    if not TEXT.is_file():
        raise RuntimeError(f"missing extracted reader text: {TEXT}")
    pages = TEXT.read_text(encoding="utf-8", errors="replace").split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    return pages


def _expected_input_records(paths: Iterable[Path]) -> list[dict[str, object]]:
    return sorted((identity(path) for path in paths), key=lambda item: str(item["path"]))


def _observed_input_records(value: Any, context: str) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise RuntimeError(f"build receipt missing {context}")
    return sorted((canonical_identity_record(item, context) for item in value), key=lambda item: str(item["path"]))


def validate_replay(build: dict[str, Any], key: str, candidate_pdf: dict[str, object], candidate_text: dict[str, object], page_count: int) -> dict[str, object]:
    replay = build.get(key)
    if not isinstance(replay, dict) or replay.get("pages") != page_count:
        raise RuntimeError(f"build receipt {key} page count changed")
    replay_pdf = validate_artifact_record(replay.get("pdf"), f"{key}.pdf")
    replay_text = validate_artifact_record(replay.get("text"), f"{key}.text")
    pass3 = validate_artifact_record(replay.get("pass3"), f"{key}.pass3")
    terminal_log = validate_artifact_record(replay.get("terminal_log"), f"{key}.terminal_log")
    same_payload(replay_pdf, candidate_pdf, f"{key} PDF/candidate")
    same_payload(replay_text, candidate_text, f"{key} text/candidate")
    same_payload(pass3, candidate_pdf, f"{key} pass3/candidate")
    trailer_ids = replay.get("trailer_ids")
    if not isinstance(trailer_ids, list) or len(trailer_ids) != 2 or trailer_ids[0] != trailer_ids[1]:
        raise RuntimeError(f"{key} trailer IDs are absent or unequal")
    fatal = replay.get("warnings", {}).get("fatal")
    expected_fatal = {"multiply_defined_labels": 0, "rerun_required": 0, "undefined_citations": 0, "undefined_references": 0}
    if fatal != expected_fatal:
        raise RuntimeError(f"{key} fatal-warning closure changed: {fatal}")
    return {
        "pages": page_count, "pdf": replay_pdf, "text": replay_text,
        "pass3": pass3, "terminal_log": terminal_log,
        "trailer_ids": trailer_ids, "fatal_warnings": fatal,
    }


def validate_build_binding() -> dict[str, object]:
    frozen = validate_frozen_inputs()
    for path, expected in EXPECTED_BUILD_IDENTITIES.items():
        require_exact(path, expected)
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("pypdf is required for built-reader validation") from exc

    build = load_json(BUILD_QA)
    if build.get("$schema") != "interlanguage.r011-b022-boundary-clean-reader-build/v1":
        raise RuntimeError("B022 build-receipt schema changed")
    if build.get("boundary_id") != BOUNDARY_ID or build.get("status") != EXPECTED_BUILD_STATUS:
        raise RuntimeError("B022 build receipt boundary/status changed")
    if build.get("translation_provenance") != MODEL_PROVENANCE:
        raise RuntimeError("B022 build receipt model provenance changed")
    if build.get("included_scope") != EXPECTED_SCOPE:
        raise RuntimeError("B022 build receipt included scope changed")
    exclusions = build.get("excluded_untranslated_scope")
    if not isinstance(exclusions, list) or EXPECTED_O001_EXCLUSION not in exclusions:
        raise RuntimeError("B022 build receipt O001 exclusion changed")
    if "Chapter 6 Sections 6.2-6.4" not in exclusions or "Chapters 7-9" not in exclusions:
        raise RuntimeError("B022 later-source exclusion changed")
    if build.get("publication_performed") is not False or build.get("git_used") is not False:
        raise RuntimeError("B022 pre-admission build receipt mutation guards changed")

    candidate_pdf = require_record_matches_file(build.get("candidate_artifact"), CANDIDATE_PDF, "candidate_artifact")
    candidate_text = require_record_matches_file(build.get("candidate_text"), TEXT, "candidate_text")
    page_count = len(PdfReader(CANDIDATE_PDF).pages)
    pages = load_pages()
    if page_count != 230 or len(pages) != 230 or build.get("page_count") != 230:
        raise RuntimeError(f"B022 PDF/text/build page counts disagree: pdf={page_count}, text={len(pages)}, receipt={build.get('page_count')}")

    inputs = build.get("inputs")
    if not isinstance(inputs, dict):
        raise RuntimeError("B022 build receipt inputs missing")
    if inputs.get("base_source") != {
        "bytes": 41_623_941, "files": 1_212,
        "inventory_sha256": "ab7db58a72d39b5a30e7625b4eaba9e34461bebadef12d542117ea76658fb331",
    }:
        raise RuntimeError("B022 build receipt base-source identity changed")
    expected_base = _expected_input_records(builder.EXPECTED_BASE_FILES)
    if _observed_input_records(inputs.get("base_files"), "inputs.base_files") != expected_base:
        raise RuntimeError("B022 build receipt base-file identity set changed")
    expected_stable = _expected_input_records(builder.EXPECTED_STABLE_B022_INPUTS)
    if _observed_input_records(inputs.get("stable_b022_inputs"), "inputs.stable_b022_inputs") != expected_stable:
        raise RuntimeError("B022 stable frozen-input identity set changed")
    expected_volatile = _expected_input_records(builder.EXPECTED_REVIEW_VOLATILE_B022_INPUTS)
    if _observed_input_records(inputs.get("review_volatile_b022_inputs"), "inputs.review_volatile_b022_inputs") != expected_volatile:
        raise RuntimeError("B022 reviewed exercise/answer identity set changed")

    custom = build.get("custom_sources")
    if not isinstance(custom, dict):
        raise RuntimeError("B022 custom-source binding missing")
    custom_records = {
        "custom_main": SOURCE_SNAPSHOT / "main_boundary_clean_b022.tex",
        "custom_chapter": SOURCE_SNAPSHOT / "ch_inference_for_props/TeX/ch_inference_for_props.tex",
        "custom_exercises_1_16": SOURCE_SNAPSHOT / "ch_inference_for_props/TeX/inference_for_a_single_proportion.tex",
        "custom_answers": SOURCE_SNAPSHOT / "extraTeX/eoceSolutions/eoceSolutions_boundary_clean_b022.tex",
    }
    validated_custom = {
        key: require_record_matches_file(custom.get(key), path, f"custom_sources.{key}")
        for key, path in custom_records.items()
    }
    transformations = custom.get("assembly_transformations")
    if not isinstance(transformations, dict):
        raise RuntimeError("B022 assembly transformation record missing")
    answer_transition = transformations.get("answer_chapter_transition")
    if not isinstance(answer_transition, dict) or answer_transition.get("counter_reset_required") is not True:
        raise RuntimeError("v2 answer-counter repair is not bound")
    if answer_transition.get("expected_answer_labels") != [f"eoce_sol_6_{number}" for number in EXPECTED_PUBLIC_ANSWERS]:
        raise RuntimeError("v2 expected public-answer labels changed")
    title_reflow = transformations.get("chapter_title_page_reflow")
    if not isinstance(title_reflow, dict):
        raise RuntimeError("v3 Chapter 6 title reflow is not bound")
    if title_reflow.get("semantic_title") != "Inferensi untuk data kategoris":
        raise RuntimeError("v3 semantic Chapter 6 title changed")
    if title_reflow.get("target_tex") != r"\chaptertitle{Inferensi untuk \titlebreak{} data kategoris}":
        raise RuntimeError("v3 titlebreak assembly changed")
    if title_reflow.get("translation_staging_mutated") is not False:
        raise RuntimeError("v3 receipt claims accepted staging was mutated")

    figure = custom.get("numeric_only_figure")
    if not isinstance(figure, dict) or figure.get("installed_byte_for_byte") is not True or figure.get("mathematics_or_data_changed") is not False:
        raise RuntimeError("B022 numeric-only figure disposition changed")
    source_figure = validate_artifact_record(figure.get("source"), "numeric figure source")
    installed = figure.get("installed")
    if not isinstance(installed, dict) or installed.get("page_count") != 1 or installed.get("content_localization_required") is not False:
        raise RuntimeError("B022 installed numeric-only figure metadata changed")
    installed_figure = validate_artifact_record(installed.get("identity"), "numeric figure installed")
    same_payload(source_figure, installed_figure, "numeric figure byte-for-byte install")
    if installed.get("visible_text") != ["0.45", "0.47", "0.48", "0.5", "0.52", "0.53", "0.55"]:
        raise RuntimeError("B022 numeric-only figure visible values changed")

    determinism = build.get("determinism")
    expected_determinism = {"pdf_byte_identical": True, "text_byte_identical": True, "trailer_ids_equal": True}
    if determinism != expected_determinism:
        raise RuntimeError(f"B022 deterministic replay evidence changed: {determinism}")
    replay_a = validate_replay(build, "replay_a", candidate_pdf, candidate_text, page_count)
    replay_b = validate_replay(build, "replay_b", candidate_pdf, candidate_text, page_count)
    if replay_a["trailer_ids"] != replay_b["trailer_ids"]:
        raise RuntimeError("B022 replay trailer IDs differ")

    known_counts = build.get("known_untranslated_or_excluded_phrase_counts")
    if not isinstance(known_counts, dict) or len(known_counts) != 14 or any(value != 0 for value in known_counts.values()):
        raise RuntimeError(f"B022 build receipt records untranslated/excluded phrase hits: {known_counts}")
    next_cursor = build.get("next_cursor")
    if next_cursor != {
        "boundary_id": "R011-B023",
        "path": "ch_inference_for_props/TeX/ch_inference_for_props.tex",
        "first_instructional_line": 555,
        "first_instructional_label": "differenceOfTwoProportions",
        "first_instructional_label_line": 556,
    }:
        raise RuntimeError("B022 build receipt next cursor changed")

    manifest = validate_source_manifest(build)
    return {
        "pdf_page_count": page_count,
        "candidate_artifact": candidate_pdf,
        "candidate_text": candidate_text,
        "build_qa": identity(BUILD_QA),
        "builders": [identity(BUILDER_V1), identity(BUILDER_V2), identity(BUILDER_V3)],
        "failure_diagnoses": [identity(V1_DIAGNOSIS), identity(V2_DIAGNOSIS)],
        "build_status": build["status"],
        "determinism": determinism,
        "replay_a": replay_a,
        "replay_b": replay_b,
        "included_scope": build["included_scope"],
        "excluded_untranslated_scope": exclusions,
        "custom_sources": validated_custom,
        "numeric_only_figure": {"source": source_figure, "installed": installed_figure},
        "source_manifest": manifest,
        "frozen_input_count": frozen["frozen_input_count"],
    }


def scan_pages() -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for number, page in enumerate(load_pages(), 1):
        lines: list[dict[str, object]] = []
        english_total = indonesian_total = word_total = 0
        for raw in page.splitlines():
            value = raw.strip()
            tokens = [token.casefold() for token in WORD.findall(value)]
            english = sum(token in ENGLISH for token in tokens)
            indonesian = sum(token in INDONESIAN for token in tokens)
            english_total += english
            indonesian_total += indonesian
            word_total += len(tokens)
            if len(tokens) >= 6 and english >= 3 and english >= 2 * max(indonesian, 1):
                lines.append({"english": english, "indonesian": indonesian, "text": value[:300]})
        if lines:
            result.append({
                "page": number,
                "english_tokens": english_total,
                "indonesian_tokens": indonesian_total,
                "word_tokens": word_total,
                "line_score": sum(int(line["english"]) - int(line["indonesian"]) for line in lines),
                "lines": lines,
            })
    return result


def page_disposition(page: int, flag: dict[str, object] | None) -> str:
    if flag is None:
        return "PASS_INDONESIAN_READER_PAGE"
    if page in CITATION_OR_TITLE_PAGES:
        return "PASS_PRESERVED_BIBLIOGRAPHIC_OR_SOURCE_TITLE"
    if page in DATA_AND_CITATION_PAGES:
        return "PASS_PRESERVED_LITERAL_DATA_CATEGORY_AND_BIBLIOGRAPHIC_TITLE"
    if page in MATH_SYMBOL_PAGES:
        return "PASS_MATHEMATICAL_SYMBOL_HEURISTIC_FALSE_POSITIVE"
    if page in DATA_IDENTIFIER_PAGES:
        return "PASS_PRESERVED_LITERAL_DATASET_OR_CATEGORY_IDENTIFIER"
    lines = flag.get("lines", [])
    if isinstance(lines, list) and lines and all(
        isinstance(line, dict) and any(pattern.search(str(line.get("text", ""))) for pattern in ALLOWED_NEW_FLAG_LINES)
        for line in lines
    ):
        return "PASS_PRESERVED_PROPER_NAME_CITATION_URL_OR_IDENTIFIER"
    raise RuntimeError(f"unadjudicated residual-English heuristic flag on page {page}: {lines}")


def structural_checks(full_text: str) -> dict[str, object]:
    normalized = re.sub(r"\s+", " ", full_text)
    heading_counts = {heading: normalized.count(heading) for heading in REQUIRED_HEADINGS}
    if any(count < 1 for count in heading_counts.values()):
        raise RuntimeError(f"B022 localized heading closure changed: {heading_counts}")

    exercise_counts = {
        str(number): normalized.count(f"6.{number} {title}.")
        for number, title in EXERCISE_TITLES.items()
    }
    if any(count != 1 for count in exercise_counts.values()):
        raise RuntimeError(f"B022 exercise title closure changed: {exercise_counts}")

    answer_markers = list(re.finditer(r"(?m)^\s*6 Inferensi untuk data kategoris\s*$", full_text))
    if len(answer_markers) != 1:
        raise RuntimeError(f"B022 Chapter 6 answer-section marker count changed: {len(answer_markers)}")
    answer_text = full_text[answer_markers[0].start():]
    answer_counts = {
        str(number): len(re.findall(rf"(?m)^\s*6\.{number}(?=\s)", answer_text))
        for number in range(1, 17)
    }
    expected_answer_counts = {
        str(number): 1 if number in EXPECTED_PUBLIC_ANSWERS else 0
        for number in range(1, 17)
    }
    if answer_counts != expected_answer_counts:
        raise RuntimeError(f"B022 public-answer/O001 closure changed: expected={expected_answer_counts}, observed={answer_counts}")

    scope_statement_count = full_text.count("Pembaca ini berhenti tepat setelah Bagian 6.1")
    if scope_statement_count != 1:
        raise RuntimeError(f"B022 scope statement count changed: {scope_statement_count}")
    solution_heading_count = len(re.findall(r"(?m)^Solusi latihan\s*$", full_text))
    if solution_heading_count != 1:
        raise RuntimeError(f"B022 solution-heading count changed: {solution_heading_count}")
    return {
        "scope_statement_count": scope_statement_count,
        "localized_heading_witness_counts": heading_counts,
        "exercise_title_counts": exercise_counts,
        "translated_exercise_numbers": list(range(1, 17)),
        "public_answer_label_counts_in_answer_section": answer_counts,
        "public_answers_translated": EXPECTED_PUBLIC_ANSWERS,
        "o001_no_public_answer": EXPECTED_O001_GAPS,
        "solution_heading_count": solution_heading_count,
        "section_6_2_tail_present": False,
        "chapter_7_plus_tail_present": False,
    }


def run_language_and_structure(build_binding: dict[str, object]) -> dict[str, object]:
    pages = load_pages()
    page_count = int(build_binding["pdf_page_count"])
    if len(pages) != page_count:
        raise RuntimeError("page count changed between B022 build validation and language scan")
    full_text = TEXT.read_text(encoding="utf-8", errors="replace")
    forbidden_counts = {name: len(pattern.findall(full_text)) for name, pattern in FORBIDDEN_RESIDUALS.items()}
    if any(forbidden_counts.values()):
        raise RuntimeError(f"avoidable residual-English or excluded later scope remains: {forbidden_counts}")
    required_counts = {name: len(pattern.findall(full_text)) for name, pattern in REQUIRED_LOCALIZED.items()}
    if any(value == 0 for value in required_counts.values()):
        raise RuntimeError(f"localized B022 witness missing: {required_counts}")
    if required_counts["provenance_model"] != 1:
        raise RuntimeError(f"model provenance count changed: {required_counts['provenance_model']}")
    structural = structural_checks(full_text)

    flagged = scan_pages()
    flagged_pages = [int(item["page"]) for item in flagged]
    if flagged_pages != EXPECTED_HEURISTIC_FLAGGED_PAGES:
        raise RuntimeError(f"B022 heuristic flag set changed: expected={EXPECTED_HEURISTIC_FLAGGED_PAGES}, observed={flagged_pages}")
    flagged_by_page = {int(item["page"]): item for item in flagged}
    dispositions = {number: page_disposition(number, flagged_by_page.get(number)) for number in range(1, page_count + 1)}
    return {
        "pages": pages,
        "flagged": flagged,
        "flagged_by_page": flagged_by_page,
        "dispositions": dispositions,
        "forbidden_counts": forbidden_counts,
        "required_counts": required_counts,
        "structural": structural,
    }


def validate_visual_qa(pdf_identity: dict[str, object], page_count: int) -> dict[str, object]:
    visual = load_json(VISUAL_QA)
    required = set(VISUAL_QA_RECEIPT_SCHEMA["required"])
    missing = sorted(required - set(visual))
    if missing:
        raise RuntimeError(f"B022 visual-QA required fields missing: {missing}")
    if visual.get("$schema") != "interlanguage.r011-b022-visual-qa/v1":
        raise RuntimeError("B022 visual-QA schema identifier changed")
    if visual.get("boundary_id") != BOUNDARY_ID or visual.get("status") != "PASS_ALL_230_PAGES_VISUALLY_INSPECTED_ZERO_DEFECTS":
        raise RuntimeError("B022 visual-QA boundary/status changed")
    if page_count != 230 or visual.get("page_count") != page_count or visual.get("defect_count") != 0:
        raise RuntimeError("B022 visual-QA page/defect counts changed")
    if visual.get("all_pages_inspected") is not True or visual.get("defects") != []:
        raise RuntimeError("B022 visual-QA does not prove all-page zero-defect inspection")
    if visual.get("page_count_is_artifact_extent_not_translation_progress") is not True:
        raise RuntimeError("B022 visual-QA confuses page extent with translation progress")
    if canonical_identity_record(visual.get("learner_pdf"), "visual learner_pdf") != pdf_identity:
        raise RuntimeError("B022 visual-QA is not bound to the current v3 PDF")
    render = visual.get("render")
    if not isinstance(render, dict) or render.get("rendered_page_count") != page_count:
        raise RuntimeError("B022 visual-QA rendered-page count changed")

    findings = visual.get("specific_findings")
    required_findings = {"chapter_6_title_reflow", "section_6_1", "exercise_flow", "chapter_6_answers", "numeric_figure"}
    if not isinstance(findings, dict) or not required_findings.issubset(findings):
        raise RuntimeError("B022 visual-QA specific findings are incomplete")
    for key in required_findings:
        finding = findings[key]
        if not isinstance(finding, dict) or finding.get("result") != "PASS_NO_VISUAL_DEFECT":
            raise RuntimeError(f"B022 visual-QA specific finding failed: {key}={finding}")

    pagewise = visual.get("pagewise_dispositions")
    if not isinstance(pagewise, list) or len(pagewise) != page_count:
        raise RuntimeError("B022 visual-QA pagewise-disposition count changed")
    if [item.get("page") for item in pagewise if isinstance(item, dict)] != list(range(1, page_count + 1)):
        raise RuntimeError("B022 visual-QA pagewise rows are not exact ordered pages 1..230")
    for item in pagewise:
        if not isinstance(item, dict) or item.get("disposition") != "PASS_NO_VISUAL_DEFECT":
            raise RuntimeError(f"B022 visual-QA page disposition failed: {item}")
        validate_artifact_record({key: item.get(key) for key in ("path", "bytes", "sha256")}, f"visual page {item.get('page')}")

    contacts = visual.get("contact_sheets")
    if not isinstance(contacts, list) or not contacts:
        raise RuntimeError("B022 visual-QA contact-sheet inventory missing")
    covered: list[int] = []
    for item in contacts:
        if not isinstance(item, dict) or item.get("disposition") != "ALL_PAGES_IN_RANGE_INSPECTED":
            raise RuntimeError(f"B022 visual-QA contact-sheet disposition failed: {item}")
        validate_artifact_record({key: item.get(key) for key in ("path", "bytes", "sha256")}, "visual contact sheet")
        page_range = item.get("page_range")
        if not isinstance(page_range, list) or len(page_range) != 2:
            raise RuntimeError(f"invalid B022 contact-sheet page range: {page_range}")
        covered.extend(range(int(page_range[0]), int(page_range[1]) + 1))
    if covered != list(range(1, page_count + 1)):
        raise RuntimeError("B022 contact sheets do not cover ordered pages 1..230 exactly once")

    originals = visual.get("original_scale_checks")
    if not isinstance(originals, list):
        raise RuntimeError("B022 visual-QA original-scale checks missing")
    required_original_pages = {1, 208, 210, 216, 220, 229, 230}
    original_pages = {item.get("page") for item in originals if isinstance(item, dict)}
    if not required_original_pages.issubset(original_pages):
        raise RuntimeError(f"B022 original-scale checks omit required transitions: {sorted(required_original_pages - original_pages)}")
    for item in originals:
        if not isinstance(item, dict) or item.get("result") != "PASS_NO_VISUAL_DEFECT":
            raise RuntimeError(f"B022 original-scale check failed: {item}")
        validate_artifact_record({key: item.get(key) for key in ("path", "bytes", "sha256")}, f"visual original page {item.get('page')}")
    return {
        "receipt": identity(VISUAL_QA),
        "status": visual["status"],
        "page_count": page_count,
        "pagewise_rows": len(pagewise),
        "contact_sheet_count": len(contacts),
        "original_scale_page_count": len(originals),
        "required_original_scale_pages": sorted(required_original_pages),
        "defect_count": 0,
    }


def finalize() -> dict[str, object]:
    build_binding = validate_build_binding()
    language = run_language_and_structure(build_binding)
    pages = language["pages"]
    page_count = int(build_binding["pdf_page_count"])
    visual_binding = validate_visual_qa(build_binding["candidate_artifact"], page_count)
    flagged_by_page = language["flagged_by_page"]
    dispositions = language["dispositions"]

    rows: list[dict[str, object]] = []
    flag_evidence: list[dict[str, object]] = []
    for page_number, page_text in enumerate(pages, 1):
        tokens = [token.casefold() for token in WORD.findall(page_text)]
        flag = flagged_by_page.get(page_number)
        rows.append({
            "page": page_number,
            "text_sha256": sha256_bytes(page_text.encode("utf-8")),
            "characters": len(page_text),
            "word_tokens": len(tokens),
            "english_heuristic_tokens": sum(token in ENGLISH for token in tokens),
            "indonesian_heuristic_tokens": sum(token in INDONESIAN for token in tokens),
            "heuristic_flagged": flag is not None,
            "flagged_line_count": len(flag["lines"]) if flag else 0,
            "disposition": dispositions[page_number],
            "untranslated_instructional_or_exercise_prose": False,
        })
        if flag:
            flag_evidence.append({**flag, "disposition": dispositions[page_number]})

    payload: dict[str, object] = {
        "$schema": "interlanguage.r011-b022-pagewise-language-qa/v1",
        "boundary_id": BOUNDARY_ID,
        "status": "PASS_ALL_230_PAGES_ADJUDICATED_NO_UNTRANSLATED_INSTRUCTIONAL_EXERCISE_OR_PUBLIC_ANSWER_PROSE",
        "learner_reader_total_pages": page_count,
        "accepted_indonesian_reader_pages": page_count,
        "untranslated_instructional_or_exercise_prose_pages": 0,
        "all_pages_adjudicated": True,
        "full_source_closure_contains_untranslated_source": True,
        "page_count_is_artifact_extent_not_translation_progress": True,
        "exercise_coverage": {
            "translated": list(range(1, 17)),
            "public_answers_translated": EXPECTED_PUBLIC_ANSWERS,
            "o001_no_public_answer": EXPECTED_O001_GAPS,
        },
        "structural_checks": language["structural"],
        "build_binding": build_binding,
        "visual_qa_binding": visual_binding,
        "allowed_english_residual_categories": [
            "exact bibliographic and source-work titles",
            "immutable literal dataset, code, and category identifiers",
            "proper names and URLs",
            "mathematical variables and symbols",
        ],
        "heuristic_flagged_page_count": len(language["flagged"]),
        "heuristic_flagged_pages": sorted(flagged_by_page),
        "heuristic_flag_evidence": flag_evidence,
        "avoidable_residual_and_excluded_scope_counts": language["forbidden_counts"],
        "localized_term_witness_counts": language["required_counts"],
        "learner_pdf": identity(CANDIDATE_PDF),
        "extracted_text": identity(TEXT),
        "build_qa": identity(BUILD_QA),
        "source_manifest": identity(SOURCE_MANIFEST),
        "visual_qa": identity(VISUAL_QA),
        "pages": rows,
    }
    QA_DIR.mkdir(parents=True, exist_ok=True)
    QA_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    with QA_TSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return {
        "status": payload["status"], "json": identity(QA_JSON), "tsv": identity(QA_TSV),
        "page_count": page_count, "flagged_pages": sorted(flagged_by_page),
        "exercise_coverage": payload["exercise_coverage"], "visual_qa": visual_binding,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deterministic B022 pagewise language/structure QA bound to the polished v3 reader.")
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--self-check", action="store_true", help="validate frozen B022 inputs, builders, diagnoses, and embedded contracts")
    modes.add_argument("--check-build", action="store_true", help="read-only validation of the exact deterministic v3 build and source manifest")
    modes.add_argument("--scan", action="store_true", help="read-only pagewise residual-language and structural scan")
    modes.add_argument("--visual-schema", action="store_true", help="print the required B022 all-page visual-QA receipt JSON Schema")
    modes.add_argument("--finalize", action="store_true", help="validate every gate and write the B022 pagewise language-QA JSON/TSV")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    if args.self_check:
        result: object = validate_frozen_inputs()
    elif args.visual_schema:
        result = VISUAL_QA_RECEIPT_SCHEMA
    elif args.check_build:
        result = validate_build_binding()
    elif args.scan:
        binding = validate_build_binding()
        language = run_language_and_structure(binding)
        result = {
            "boundary_id": BOUNDARY_ID,
            "page_count": binding["pdf_page_count"],
            "flagged_page_count": len(language["flagged"]),
            "pages": language["flagged"],
            "page_dispositions": {str(page): language["dispositions"][page] for page in sorted(language["flagged_by_page"])},
            "forbidden_counts": language["forbidden_counts"],
            "required_counts": language["required_counts"],
            "structural": language["structural"],
        }
    else:
        result = finalize()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
