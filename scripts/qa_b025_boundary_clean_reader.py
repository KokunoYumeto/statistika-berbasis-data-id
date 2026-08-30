#!/usr/bin/env python3
"""Deterministic whole-reader QA for the boundary-clean R011-B025 reader.

The post-build identity block is intentionally unset until the deterministic
B025 build exists.  Before it is bound, every mode that could accept or render
a candidate fails closed.  ``--binding-requirements`` and ``--visual-schema``
remain inert and may be used to inspect the required post-build values.

Writes, when explicitly run after binding, are limited to qa/b025-reader.
This script never mutates backend, controls, output, release, Git, network,
credentials, publication state, or upstream sources.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "qa_b024", ROOT / "scripts/qa_b024_boundary_clean_reader.py"
)
assert spec and spec.loader
b024 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b024)
helper = b024.prior

BOUNDARY_ID = "R011-B025"
MODEL = "OpenAI Codex gpt-5.6-sol, Ultra"
BUILD_ROOT = ROOT / "scratch/b025-boundary-clean-reader-r2"
FINAL_PDF = BUILD_ROOT / "final/main.pdf"
FINAL_TEXT = BUILD_ROOT / "final/main-final.txt"
BUILD_QA = BUILD_ROOT / "final/R011-B025_BOUNDARY_CLEAN_BUILD_QA.json"
SOURCE_MANIFEST = BUILD_ROOT / "R011-B025_BOUNDARY_CLEAN_SOURCE_MANIFEST.tsv"
SNAPSHOT = BUILD_ROOT / "source-snapshot"
QA_DIR = ROOT / "qa/b025-reader"
QA_JSON = QA_DIR / "R011-B025_PAGEWISE_LANGUAGE_QA.json"
QA_TSV = QA_DIR / "R011-B025_PAGEWISE_LANGUAGE_QA.tsv"
RENDER_DIR = QA_DIR / "render-r2"
RENDER_PAGES = RENDER_DIR / "pages"
VISUAL_QA = QA_DIR / "R011-B025_AUTOMATED_VISUAL_QA.json"

# BEGIN POST-BUILD BINDING BLOCK.
# Bind these five values from the completed deterministic build before running
# --check-build, --self-check, --scan, --render, or --finalize.  Do not infer
# page count from translation progress: it is the exact artifact extent.
EXPECTED_BUILD_QA: tuple[int, str] | None = (
    21_393,
    "36f64b5447a9a87e03148b650d4cbec610e380393003b9c9860d46674eef01f0",
)
EXPECTED_PDF: tuple[int, str] | None = (
    12_440_420,
    "b154484d2d2ddf0a49f0ee9925854f45e86b6e0fb17d241607db9fc27051e99d",
)
EXPECTED_TEXT: tuple[int, str] | None = (
    831_809,
    "028d1fa9db21004563c3678ed648345ffb734762c715b9b34d515be74e68eaf3",
)
EXPECTED_SOURCE_MANIFEST: tuple[int, str] | None = (
    177_208,
    "5bc7b2ab909843e7d145248572bdf5e92a56e6cf39f777ec0784b638e9a97b3e",
)
EXPECTED_PAGE_COUNT: int | None = 260
# END POST-BUILD BINDING BLOCK.

LOCALIZED_CHART = ROOT / "qa/b025-translation/staging/assets/iPodChiSqTail.id.pdf"
EXPECTED_LOCALIZED_CHART = (
    13_265,
    "4d34c0d4f59787283086f88fb0eaa7c47714726b0e21fcb440a7bcf8e243acae",
)

INDEPENDENT_AUDIT = (
    ROOT / "qa/b025-translation/R011-B025_INDEPENDENT_TRANSLATION_AUDIT.json"
)
EXPECTED_INDEPENDENT_AUDIT = (
    16_509,
    "737f485b49f80e26269e282b227221d7eb3826005c5dd8d1b6066ae8cbd5c215",
    "PASS_INDEPENDENT_COMPLETE_NATURAL_ID_ID_STRUCTURE_MATH_REPAIRS_EXERCISE_ANSWER_AND_O001_QA",
)

EVIDENCE = (
    (
        "qa/b025-source/R011-B025_BOUNDARY_BLUEPRINT.json",
        24_634,
        "529f46e13cabc1db76a65e8a1281f99e51251cc08753e8c217871d52eb296d7e",
        "PASS_SOURCE_ASSET_DATA_RIGHTS_AND_BOOK_ORDER_DEPENDENCY_CLOSURE",
    ),
    (
        "qa/b025-translation/R011-B025_MAIN_A_TRANSLATION_AUDIT.json",
        3_914,
        "06742809fcd4984788b9790a9ecba4fbc9c70eb14acd026936b32100a6ac7fed",
        "PASS_COMPLETE_NATURAL_ID_ID_STRUCTURE_MATH_LANGUAGE_AND_HIGH_CONFIDENCE_FORMULA_CORRECTION_QA",
    ),
    (
        "qa/b025-translation/R011-B025_MAIN_TRANSLATION_PART_B_AUDIT.json",
        7_712,
        "b0dfee1a269bb541d3b6d941dc4c400c33e1b774fb0d30e8d1b6f80ba365a776",
        "PASS_DETERMINISTIC_STRUCTURE_MATH_AND_RESIDUAL_ENGLISH",
    ),
    (
        "qa/b025-translation/R011-B025_EXERCISES_ANSWERS_TRANSLATION_QA.json",
        2_844,
        "a3653c8aaa12301fbded5588c83ef6c59bccbc5a107b806c2118c29a3005e947",
        "PASS_EXERCISES_35_38_AND_ALL_LINKED_PUBLIC_ODD_ANSWERS_TRANSLATED",
    ),
    (
        "qa/b025-translation/R011-B025_INDEPENDENT_TRANSLATION_AUDIT.json",
        EXPECTED_INDEPENDENT_AUDIT[0],
        EXPECTED_INDEPENDENT_AUDIT[1],
        EXPECTED_INDEPENDENT_AUDIT[2],
    ),
    (
        "qa/b025-translation/R011-B025_IPOD_CHISQ_TAIL_LOCALIZATION_QA.json",
        3_314,
        "c2ab840d15bf7391518c4587aad7ed6f7ded1c9b208706861434ac64e9b104db",
        "PASS_EXACT_ANNOTATION_LOCALIZATION_AND_GEOMETRY_PRESERVATION",
    ),
    (
        "qa/b025-translation/R011-B025_IPOD_CHISQ_TAIL_VISUAL_QA.json",
        2_603,
        "13ec3d5529ebdf198630341f16accb457bb8b94cdda7edcfdbb218007f29e837",
        "PASS_DIRECT_VISUAL_INSPECTION_AND_RASTER_GEOMETRY_COMPARISON",
    ),
)

FORBIDDEN_LATER = (
    "Inference for numerical data",
    "One-sample means with the t-distribution",
    "Introduction to linear regression",
    "Multiple and logistic regression",
    "Inferensi untuk data numerik",
    "Rataan satu sampel dengan distribusi t",
)
FORBIDDEN_ENGLISH = (
    "Testing for independence in two-way tables",
    "The chi-square test for two-way tables",
    "Expected counts in two-way tables",
    "Computing expected counts in a two-way table",
    "Tail area (1 / 500 million)",
    "is too small to see",
    "What problems does it have?",
    "Disclose Problem",
    "Hide Problem",
    "Positive Assumption",
    "Negative Assumption",
    "Full body scan, Part II",
    "Offshore drilling, Part III",
    "Parasitic worm",
    "Clear at Year 2",
    "Not Clear at Year 2",
)
# Formula-label residue may be attached to mathematical tokens (for example,
# ``Erow1,col1``), so use letter-boundary-aware patterns instead of the prose
# substring scanner.  This avoids false positives in names such as Brown and
# words such as college while rejecting the exact visible English labels.
FORBIDDEN_VISIBLE_ENGLISH_LABELS = (
    (
        "row",
        re.compile(
            r"(?:(?<![A-Za-z])|(?<=E))row(?=[^A-Za-z]|$)",
            re.IGNORECASE,
        ),
    ),
    (
        "col",
        re.compile(
            r"(?:(?<![A-Za-z])|(?<=E))col(?=[^A-Za-z]|$)",
            re.IGNORECASE,
        ),
    ),
    (
        "table total",
        re.compile(r"(?<![A-Za-z])table\s+total(?![A-Za-z])", re.IGNORECASE),
    ),
)
REQUIRED = (
    "Cakupan edisi parsial ini",
    "Inferensi untuk data kategoris",
    "Uji kesesuaian menggunakan khi-kuadrat",
    "Menguji independensi dalam tabel dua arah",
    "Cacah harapan dalam tabel dua arah",
    "Uji khi-kuadrat untuk tabel dua arah",
    "Solusi latihan",
    "cacah teramati",
    "cacah harapan",
    "derajat kebebasan",
    "nilai-p",
    "O001",
    MODEL,
)
DIRECT_VISUAL_ANCHORS = (
    "Menguji independensi dalam tabel dua arah",
    "Cacah harapan dalam tabel dua arah",
    "Uji khi-kuadrat untuk tabel dua arah",
    "Visualisasi nilai-p untuk X2 = 40.13",
    "Berhenti merokok",
    "Pemindaian seluruh tubuh, Bagian II",
    "Pengeboran lepas pantai, Bagian III",
    "Cacing parasit",
    "Koyo + kelompok dukungan",
    "Pendapat lulusan dan bukan lulusan perguruan tinggi",
)
EXERCISE_LABELS = (
    "quitters_chisq_independence",
    "full_body_scan_chisq_indep",
    "offshore_drilling_chisq_indep",
    "parasitic_worm_chisq",
    "parasitic_worm_chisq_hyp",
)
ALLOWED_FLAG_MARKERS = tuple(helper.PROPER_OR_LITERAL) + (
    "iPod",
    "metformin",
    "rosiglitazone",
    "King",
    "Suamani",
    "California",
    "OpenIntro",
    "X2",
    "df",
)


def configure_helper() -> None:
    for name, value in {
        "BOUNDARY_ID": BOUNDARY_ID,
        "MODEL": MODEL,
        "BUILD_ROOT": BUILD_ROOT,
        "SNAPSHOT": SNAPSHOT,
        "FINAL_PDF": FINAL_PDF,
        "FINAL_TEXT": FINAL_TEXT,
        "BUILD_QA": BUILD_QA,
        "SOURCE_MANIFEST": SOURCE_MANIFEST,
        "QA_DIR": QA_DIR,
        "QA_JSON": QA_JSON,
        "QA_TSV": QA_TSV,
        "RENDER_DIR": RENDER_DIR,
        "RENDER_PAGES": RENDER_PAGES,
        "VISUAL_QA": VISUAL_QA,
    }.items():
        setattr(helper, name, value)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def expected_bindings() -> dict[str, Any]:
    return {
        "status": (
            "READY" if all(
                value is not None
                for value in (
                    EXPECTED_BUILD_QA,
                    EXPECTED_PDF,
                    EXPECTED_TEXT,
                    EXPECTED_SOURCE_MANIFEST,
                    EXPECTED_PAGE_COUNT,
                )
            ) else "PENDING_DETERMINISTIC_B025_BUILD"
        ),
        "bind_in_script_block": {
            "EXPECTED_BUILD_QA": "(bytes, sha256)",
            "EXPECTED_PDF": "(bytes, sha256)",
            "EXPECTED_TEXT": "(bytes, sha256)",
            "EXPECTED_SOURCE_MANIFEST": "(bytes, sha256)",
            "EXPECTED_PAGE_COUNT": "exact PDF artifact page count",
        },
        "already_bound_independent_audit": {
            "path": helper.rel(INDEPENDENT_AUDIT),
            "bytes": EXPECTED_INDEPENDENT_AUDIT[0],
            "sha256": EXPECTED_INDEPENDENT_AUDIT[1],
            "status": EXPECTED_INDEPENDENT_AUDIT[2],
        },
        "artifact_extent_semantics": (
            "EXPECTED_PAGE_COUNT is the exact boundary-clean PDF extent, not a full-corpus translation-progress claim."
        ),
    }


def require_post_build_bindings() -> None:
    missing = [
        name
        for name, value in (
            ("EXPECTED_BUILD_QA", EXPECTED_BUILD_QA),
            ("EXPECTED_PDF", EXPECTED_PDF),
            ("EXPECTED_TEXT", EXPECTED_TEXT),
            ("EXPECTED_SOURCE_MANIFEST", EXPECTED_SOURCE_MANIFEST),
            ("EXPECTED_PAGE_COUNT", EXPECTED_PAGE_COUNT),
        )
        if value is None
    ]
    require(
        not missing,
        "post-build B025 QA bindings are intentionally unset: " + ", ".join(missing),
    )


def exact(path: Path, expected: tuple[int, str], label: str) -> dict[str, Any]:
    record = helper.identity(path)
    require(
        (record["bytes"], record["sha256"]) == expected,
        f"{label} identity changed: {record['path']}",
    )
    return record


def validate_evidence() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for relative, size, sha256, status in EVIDENCE:
        path = ROOT / relative
        row = exact(path, (size, sha256), relative)
        value = helper.load_json(path)
        observed_boundary = value.get("boundary_id")
        if observed_boundary is None and isinstance(value.get("scope"), dict):
            observed_boundary = value["scope"].get("boundary")
        require(
            observed_boundary in (BOUNDARY_ID, "B025"),
            f"wrong evidence boundary: {relative}",
        )
        require(value.get("status") == status, f"non-PASS evidence status: {relative}")
        rows.append(row)
    return rows


def validate_build() -> dict[str, Any]:
    require_post_build_bindings()
    assert EXPECTED_BUILD_QA is not None
    assert EXPECTED_PDF is not None
    assert EXPECTED_TEXT is not None
    assert EXPECTED_SOURCE_MANIFEST is not None
    assert EXPECTED_PAGE_COUNT is not None
    build_receipt = exact(BUILD_QA, EXPECTED_BUILD_QA, "B025 build receipt")
    exact(FINAL_PDF, EXPECTED_PDF, "B025 candidate PDF")
    exact(FINAL_TEXT, EXPECTED_TEXT, "B025 candidate text")
    exact(SOURCE_MANIFEST, EXPECTED_SOURCE_MANIFEST, "B025 source manifest")
    build = helper.load_json(BUILD_QA)
    require(
        build.get("$schema") == "interlanguage.r011-b025-boundary-clean-reader-build/v1"
        and build.get("boundary_id") == BOUNDARY_ID,
        "B025 build schema/boundary differs",
    )
    require(
        str(build.get("status", "")).startswith(
            "PASS_TWO_REPLAY_DETERMINISTIC_BOUNDARY_CLEAN_BUILD"
        ),
        "B025 build is not a deterministic PASS",
    )
    pdf_id = helper.validate_identity(build.get("candidate_artifact"), "candidate PDF")
    text_id = helper.validate_identity(build.get("candidate_text"), "candidate text")
    require(
        helper.path_from_record(build["candidate_artifact"], "candidate PDF") == FINAL_PDF,
        "candidate PDF path differs",
    )
    require(
        helper.path_from_record(build["candidate_text"], "candidate text") == FINAL_TEXT,
        "candidate text path differs",
    )
    require((pdf_id["bytes"], pdf_id["sha256"]) == EXPECTED_PDF, "candidate PDF binding differs")
    require((text_id["bytes"], text_id["sha256"]) == EXPECTED_TEXT, "candidate text binding differs")
    page_count = len(PdfReader(FINAL_PDF).pages)
    text_pages = helper.normalized_text(FINAL_TEXT).split("\f")
    if text_pages and not text_pages[-1].strip():
        text_pages.pop()
    require(
        build.get("page_count") == page_count == EXPECTED_PAGE_COUNT
        and len(text_pages) == EXPECTED_PAGE_COUNT,
        (
            "page extent differs: "
            f"pdf={page_count}, text={len(text_pages)}, build={build.get('page_count')}, "
            f"binding={EXPECTED_PAGE_COUNT}"
        ),
    )
    replays: dict[str, Any] = {}
    for key in ("replay_a", "replay_b"):
        row = build.get(key, {})
        rid = helper.validate_identity(row.get("pdf"), f"{key}.pdf")
        tid = helper.validate_identity(row.get("text"), f"{key}.text")
        pid = helper.validate_identity(row.get("pass3"), f"{key}.pass3")
        helper.validate_identity(row.get("terminal_log"), f"{key}.terminal_log")
        require(helper.same_bytes(rid, pdf_id), f"{key} PDF differs from candidate")
        require(helper.same_bytes(tid, text_id), f"{key} text differs from candidate")
        require(helper.same_bytes(pid, pdf_id), f"{key} pass3/pass4 differs")
        fatal = (row.get("warnings") or {}).get("fatal")
        require(
            fatal
            == {
                "multiply_defined_labels": 0,
                "rerun_required": 0,
                "undefined_citations": 0,
                "undefined_references": 0,
            },
            f"fatal TeX warning in {key}: {fatal}",
        )
        replays[key] = {"pdf": rid, "text": tid, "pass3": pid}
    require(
        helper.same_bytes(replays["replay_a"]["pdf"], replays["replay_b"]["pdf"])
        and helper.same_bytes(replays["replay_a"]["text"], replays["replay_b"]["text"]),
        "B025 replay closure differs",
    )
    manifest = helper.validate_manifest(build)
    require(
        (
            manifest["identity"]["bytes"],
            manifest["identity"]["sha256"],
        )
        == EXPECTED_SOURCE_MANIFEST,
        "source manifest binding differs",
    )
    included = str(build.get("included_scope", ""))
    for token in ("Section 6.4", "exercises 35-38", "answers 35 and 37"):
        require(token in included, f"truthful B025 included scope absent: {token}")
    cursor = build.get("next_cursor", {})
    require(
        cursor.get("boundary_id") == "R011-B026"
        and cursor.get("path") == "ch_inference_for_means/TeX/ch_inference_for_means.tex"
        and cursor.get("first_instructional_line") == 1
        and cursor.get("first_section_line") == 29
        and cursor.get("first_section_label") == "oneSampleMeansWithTDistribution",
        "B026 cursor differs",
    )
    evidence = validate_evidence()
    exact(LOCALIZED_CHART, EXPECTED_LOCALIZED_CHART, "localized iPod chart")
    return {
        "candidate_pdf": pdf_id,
        "candidate_text": text_id,
        "build_receipt": build_receipt,
        "page_count": page_count,
        "page_count_is_artifact_extent_not_translation_progress": True,
        "complete_corpus": False,
        "replays": replays,
        "source_manifest": manifest,
        "evidence": evidence,
        "independent_translation_audit": helper.identity(INDEPENDENT_AUDIT),
        "included_scope": included,
        "excluded_untranslated_scope": build.get("excluded_untranslated_scope"),
        "next_cursor": cursor,
    }


def pagewise_language(build: dict[str, Any]) -> dict[str, Any]:
    label_patterns = dict(FORBIDDEN_VISIBLE_ENGLISH_LABELS)
    positive_examples = {
        "row": ("row", "Row", "Erow1"),
        "col": ("col", "Col", "Ecol_2"),
        "table total": ("table total", "TABLE   TOTAL"),
    }
    for label, examples in positive_examples.items():
        require(
            all(label_patterns[label].search(example) for example in examples),
            f"forbidden visible-label guard is inert for {label}",
        )
    require(
        not label_patterns["row"].search("Brown")
        and not label_patterns["row"].search("growth")
        and not label_patterns["col"].search("college"),
        "visible-label guards overmatch ordinary prose",
    )
    pages = helper.normalized_text(FINAL_TEXT).split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    require(len(pages) == build["page_count"], "pagewise text count changed")
    rows: list[dict[str, Any]] = []
    forbidden: dict[str, list[int]] = {}
    heuristic_flags: list[dict[str, Any]] = []
    anchor_pages: dict[str, list[int]] = {anchor: [] for anchor in DIRECT_VISUAL_ANCHORS}
    for number, page in enumerate(pages, 1):
        normalized = re.sub(r"\s+", " ", page).strip()
        lower = normalized.casefold()
        hits = [phrase for phrase in FORBIDDEN_ENGLISH if phrase.casefold() in lower]
        hits += [
            label
            for label, pattern in FORBIDDEN_VISIBLE_ENGLISH_LABELS
            if pattern.search(normalized)
        ]
        if number > 20:
            hits += [phrase for phrase in FORBIDDEN_LATER if phrase.casefold() in lower]
        for phrase in hits:
            forbidden.setdefault(phrase, []).append(number)
        for anchor in DIRECT_VISUAL_ANCHORS:
            if anchor.casefold() in lower:
                anchor_pages[anchor].append(number)
        suspicious: list[dict[str, Any]] = []
        english_total = 0
        indonesian_total = 0
        words_total = 0
        for raw_line in page.splitlines():
            value = raw_line.strip()
            tokens = [token.casefold() for token in helper.heuristic_words(value)]
            english = sum(token in helper.ENGLISH_WORDS for token in tokens)
            indonesian = sum(token in helper.INDONESIAN_WORDS for token in tokens)
            english_total += english
            indonesian_total += indonesian
            words_total += len(tokens)
            if len(tokens) >= 7 and english >= 4 and english >= 2 * max(indonesian, 1):
                suspicious.append(
                    {
                        "english": english,
                        "indonesian": indonesian,
                        "text": value[:400],
                    }
                )
        allowed: list[dict[str, Any]] = []
        unresolved: list[dict[str, Any]] = []
        for line in suspicious:
            text = str(line["text"])
            is_math = bool(re.match(r"^(?:P\s*\(|E_|X2|df\b)", text))
            is_known = any(marker.casefold() in text.casefold() for marker in ALLOWED_FLAG_MARKERS)
            target = allowed if is_math or is_known else unresolved
            target.append(
                {
                    **line,
                    "category": (
                        "displayed_mathematical_notation"
                        if is_math
                        else "proper_name_citation_url_or_literal_identifier"
                        if is_known
                        else "requires_root_full_page_adjudication"
                    ),
                }
            )
        if suspicious:
            heuristic_flags.append(
                {
                    "page": number,
                    "allowed": allowed,
                    "requires_root_adjudication": unresolved,
                }
            )
        rows.append(
            {
                "page": number,
                "text_sha256": helper.digest(page.encode("utf-8")),
                "characters": len(page),
                "word_tokens": words_total,
                "english_heuristic_tokens": english_total,
                "indonesian_heuristic_tokens": indonesian_total,
                "forbidden_matches": hits,
                "heuristic_suspect": bool(unresolved),
                "untranslated_instructional_or_exercise_prose": bool(hits),
            }
        )
    require(not forbidden, f"untranslated/excluded English reached learner pages: {forbidden}")
    joined = " ".join(re.sub(r"\s+", " ", page).strip() for page in pages)
    missing = [phrase for phrase in REQUIRED if phrase.casefold() not in joined.casefold()]
    require(not missing, f"required Indonesian B025 reader content absent: {missing}")
    root_flags = [
        {"page": row["page"], "lines": row["requires_root_adjudication"]}
        for row in heuristic_flags
        if row["requires_root_adjudication"]
    ]
    allowed_flags = [
        {"page": row["page"], "lines": row["allowed"]}
        for row in heuristic_flags
        if row["allowed"]
    ]
    anchor_pages = {key: value for key, value in anchor_pages.items() if value}
    required_anchor_pages = sorted({page for values in anchor_pages.values() for page in values})
    return {
        "status": "PASS_PAGEWISE_FORBIDDEN_REQUIRED_AND_HEURISTIC_LANGUAGE_SCAN",
        "page_count": len(pages),
        "pages": rows,
        "forbidden_matches": forbidden,
        "missing_required": missing,
        "visible_english_formula_label_checks": {
            "labels": [label for label, _ in FORBIDDEN_VISIBLE_ENGLISH_LABELS],
            "matches": {
                label: forbidden.get(label, [])
                for label, _ in FORBIDDEN_VISIBLE_ENGLISH_LABELS
            },
            "status": "PASS_ZERO_VISIBLE_ROW_COL_OR_TABLE_TOTAL_LABELS",
        },
        "allowed_english_or_literal_adjudications": allowed_flags,
        "suspect_pages_requiring_root_adjudication": [row["page"] for row in root_flags],
        "suspect_evidence": root_flags,
        "direct_visual_anchor_pages": anchor_pages,
        "required_individual_visual_pages": required_anchor_pages,
        "all_page_forbidden_phrase_scan_complete": True,
        "untranslated_instructional_or_exercise_prose_pages": 0,
    }


def structural(build: dict[str, Any]) -> dict[str, Any]:
    receipt = helper.load_json(BUILD_QA)
    custom = receipt.get("custom_sources", {})
    chapter_path = helper.path_from_record(custom["custom_chapter"], "custom chapter")
    exercises_path = helper.path_from_record(
        custom["custom_exercises_35_38"], "custom exercises 35-38"
    )
    answers_path = helper.path_from_record(
        custom["custom_answers_1_38_public"], "custom public answers 1-37"
    )
    chapter = chapter_path.read_text(encoding="utf-8")
    exercises = exercises_path.read_text(encoding="utf-8")
    answers = answers_path.read_text(encoding="utf-8")
    require(chapter.count(r"\label{oneWayChiSquare}") == 1, "Section 6.3 label differs")
    require(
        chapter.count(r"\label{twoWayTablesAndChiSquare}") == 1,
        "Section 6.4 label differs",
    )
    require(
        r"\label{oneSampleMeansWithTDistribution}" not in chapter
        and "Inference for numerical data" not in chapter,
        "Chapter 7 source entered B025 chapter",
    )
    missing_labels = [label for label in EXERCISE_LABELS if rf"\label{{{label}}}" not in exercises]
    ordinals = [int(value) for value in re.findall(r"(?m)^% (\d+)\s*$", exercises)]
    require(
        not missing_labels and ordinals == [35, 36, 37, 38] and exercises.count(r"\eoce{") == 4,
        f"exercise closure differs: labels={missing_labels}, ordinals={ordinals}",
    )
    all_answer_ids = [
        int(value) for value in re.findall(r"(?m)^%\s*(\d+)\s*$", answers)
    ]
    answer_ids = all_answer_ids[-19:]
    require(answer_ids == list(range(1, 38, 2)), f"public answer closure differs: {answer_ids}")
    source = chapter + exercises + answers
    require(
        not re.search(r"\\(?:solution|instructor|answerkey)\b", source, re.I),
        "restricted solution command entered B025 assembly",
    )
    require(
        r"($\iPodAD{}/\iPodDD{}$) --" in chapter
        and r"($\iPodBD{}/\iPodDD{}$) --" not in chapter,
        "approved iPod disclosed-fraction correction differs",
    )
    normalized_answers = answers.replace("~", " ")
    answer_label_hits = [
        label
        for label, pattern in FORBIDDEN_VISIBLE_ENGLISH_LABELS
        if pattern.search(normalized_answers)
    ]
    require(
        not answer_label_hits,
        f"English row/col/table total labels remain in public answers: {answer_label_hits}",
    )
    for localized in (
        r"E_{baris_1, kolom_1}",
        r"E_{baris_2, kolom_2}",
        r"E_{baris~3, kolom~2}",
        r"total~tabel",
    ):
        require(localized in answers, f"localized public-answer label absent: {localized}")
    require("X^2 = 40.13" in chapter and "df = (2-1)" in chapter, "iPod math closure differs")
    installed = custom.get("localized_ipod_chart", {}).get("installed")
    chart_id = helper.validate_identity(installed, "installed localized iPod chart")
    require(
        (chart_id["bytes"], chart_id["sha256"]) == EXPECTED_LOCALIZED_CHART,
        "installed localized chart differs",
    )
    chart_path = helper.path_from_record(installed, "installed localized iPod chart")
    chart_reader = PdfReader(chart_path)
    require(len(chart_reader.pages) == 1, "localized chart is not one page")
    chart_text = chart_reader.pages[0].extract_text() or ""
    chart_compact = re.sub(r"\s+", "", chart_text).casefold()
    for token in ("Luas ekor (1 dari 500 juta)", "terlalu kecil untuk terlihat"):
        require(
            re.sub(r"\s+", "", token).casefold() in chart_compact,
            f"localized chart text absent: {token}",
        )
    require(
        "tailarea" not in chart_compact and "toosmalltosee" not in chart_compact,
        "English annotation remains in localized chart",
    )
    return {
        "section_6_3_label_exact": True,
        "section_6_4_label_exact": True,
        "chapter_7_absent": True,
        "exercise_ids": ordinals,
        "exercise_labels": list(EXERCISE_LABELS),
        "aggregate_public_answer_ids": answer_ids,
        "o001_gap_ids": list(range(2, 39, 2)),
        "all_eight_repairs_bound_by_independent_audit": helper.identity(INDEPENDENT_AUDIT),
        "corrected_ipod_fraction_formula": "iPodAD/iPodDD = 61/219",
        "public_answer_formula_labels": {
            "forbidden_english_labels": [
                label for label, _ in FORBIDDEN_VISIBLE_ENGLISH_LABELS
            ],
            "forbidden_hits": answer_label_hits,
            "required_localized_labels_present": True,
            "status": "PASS_ZERO_ROW_COL_OR_TABLE_TOTAL_AND_REQUIRED_BARIS_KOLOM_LABELS",
        },
        "localized_chart": {**chart_id, "pages": 1},
        "localized_chart_visible_text": [
            "Luas ekor (1 dari 500 juta)",
            "terlalu kecil untuk terlihat",
        ],
        "restricted_instructor_solutions_accessed_or_invented": False,
        "reader_extent_is_artifact_extent_not_translation_progress": True,
    }


def chart_candidate_pages() -> list[int]:
    pages = helper.normalized_text(FINAL_TEXT).split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    tokens = (
        "Visualisasi nilai-p untuk X2 = 40.13",
        "Luas ekor (1 dari 500 juta)",
        "terlalu kecil untuk terlihat",
    )
    return [
        number
        for number, page in enumerate(pages, 1)
        if any(token.casefold() in re.sub(r"\s+", " ", page).casefold() for token in tokens)
    ]


def render(build: dict[str, Any]) -> dict[str, Any]:
    configure_helper()
    visual = helper.render_visual(build)
    record = helper.load_json(VISUAL_QA)
    record["$schema"] = "interlanguage.r011-b025-automated-visual-qa/v1"
    record["boundary_id"] = BOUNDARY_ID
    record["root_subjective_visual_signoff_claimed"] = False
    record["chart_appearance_requires_direct_root_inspection"] = True
    record["chart_candidate_pages"] = chart_candidate_pages()
    record["localized_chart_source"] = helper.identity(LOCALIZED_CHART)
    record["page_count_is_artifact_extent_not_translation_progress"] = True
    VISUAL_QA.write_bytes(helper.canonical(record))
    return {
        "receipt": helper.identity(VISUAL_QA),
        "status": record["status"],
        "page_count": build["page_count"],
        "rendered_page_count": len(record.get("rendered_pages", [])),
        "contact_sheet_count": len(record.get("contact_sheets", [])),
        "chart_candidate_pages": record["chart_candidate_pages"],
        "reused": bool(visual.get("reused")),
    }


def finalize(
    build: dict[str, Any],
    language: dict[str, Any],
    structure: dict[str, Any],
    visual: dict[str, Any],
) -> dict[str, Any]:
    payload = {
        "$schema": "interlanguage.r011-b025-pagewise-language-qa/v1",
        "boundary_id": BOUNDARY_ID,
        "status": "PASS_DETERMINISTIC_BUILD_PAGEWISE_LANGUAGE_STRUCTURE_AND_AUTOMATED_VISUAL_QA",
        "learner_reader_total_pages": build["page_count"],
        "accepted_indonesian_reader_pages": build["page_count"],
        "page_count_is_artifact_extent_not_translation_progress": True,
        "complete_corpus": False,
        "accepted_boundary": "Chapter 6 Section 6.4",
        "untranslated_instructional_or_exercise_prose_pages": 0,
        "all_page_forbidden_phrase_scan_complete": True,
        "root_subjective_visual_signoff_claimed": False,
        "full_source_closure_contains_untranslated_source": True,
        "exercise_coverage": {
            "aggregate_translated": list(range(1, 39)),
            "b025_added": [35, 36, 37, 38],
            "aggregate_public_answers": list(range(1, 38, 2)),
            "b025_public_answers_added": [35, 37],
            "aggregate_o001_no_public_answer": list(range(2, 39, 2)),
            "b025_o001_gaps": [36, 38],
        },
        "build_binding": build,
        "independent_translation_audit": helper.identity(INDEPENDENT_AUDIT),
        "language": language,
        "structural_checks": structure,
        "automated_visual_qa": visual,
        "allowed_english_residual_categories": [
            "proper names and source titles",
            "literal data/code/category identifiers",
            "URLs and citation metadata",
            "mathematical variables, formula subscripts, and symbols",
        ],
        "direct_visual_review_protocol": {
            "inspect_every_ordered_contact_sheet": True,
            "inspect_individual_pages": sorted(
                set(language["required_individual_visual_pages"])
                | set(language["suspect_pages_requiring_root_adjudication"])
                | set(visual["chart_candidate_pages"])
            ),
            "inspect_localized_chart_appearance": True,
            "checks": [
                "no clipping",
                "no overlap",
                "no unreadable figure",
                "no broken table",
                "no layout defect",
                "localized iPod chart annotation is legible and does not obscure curve or tail",
                "new Section 6.4 exercises and public answers are readable at full-page scale",
            ],
        },
        "learner_pdf": build["candidate_pdf"],
        "extracted_text": build["candidate_text"],
        "build_qa": build["build_receipt"],
        "visual_qa": visual["receipt"],
        "translation_provenance": MODEL,
        "pages": language["pages"],
        "next_cursor": build["next_cursor"],
    }
    QA_DIR.mkdir(parents=True, exist_ok=True)
    QA_JSON.write_bytes(helper.canonical(payload))
    fields = list(language["pages"][0]) if language["pages"] else []
    with QA_TSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fields,
            delimiter="\t",
            lineterminator="\n",
            extrasaction="ignore",
        )
        writer.writeheader()
        for row in language["pages"]:
            writer.writerow(
                {
                    key: json.dumps(value, ensure_ascii=False, sort_keys=True)
                    if isinstance(value, (list, dict))
                    else value
                    for key, value in row.items()
                }
            )
    return {
        "status": payload["status"],
        "page_count": build["page_count"],
        "json": helper.identity(QA_JSON),
        "tsv": helper.identity(QA_TSV),
        "visual": visual,
        "root_visual_pages": payload["direct_visual_review_protocol"]["inspect_individual_pages"],
    }


VISUAL_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "interlanguage.r011-b025-automated-visual-qa.schema/v1",
    "type": "object",
    "required": [
        "$schema",
        "boundary_id",
        "status",
        "learner_pdf",
        "page_count",
        "defect_count",
        "all_pages_rendered",
        "rendered_pages",
        "contact_sheets",
        "chart_candidate_pages",
    ],
    "properties": {
        "$schema": {"const": "interlanguage.r011-b025-automated-visual-qa/v1"},
        "boundary_id": {"const": BOUNDARY_ID},
        "status": {"const": "PASS_ALL_PAGES_RENDERED_AUTOMATED_LAYOUT_SANITY"},
        "defect_count": {"const": 0},
        "all_pages_rendered": {"const": True},
        "page_count_is_artifact_extent_not_translation_progress": {"const": True},
        "root_subjective_visual_signoff_claimed": {"const": False},
    },
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--binding-requirements", action="store_true")
    modes.add_argument("--visual-schema", action="store_true")
    modes.add_argument("--check-build", action="store_true")
    modes.add_argument("--self-check", action="store_true")
    modes.add_argument("--scan", action="store_true")
    modes.add_argument("--render", action="store_true")
    modes.add_argument("--finalize", action="store_true")
    args = parser.parse_args()
    if args.binding_requirements:
        print(json.dumps(expected_bindings(), ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    if args.visual_schema:
        print(json.dumps(VISUAL_SCHEMA, ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    configure_helper()
    build = validate_build()
    if args.check_build:
        print(json.dumps(build, ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    language = pagewise_language(build)
    structure = structural(build)
    if args.self_check:
        first = helper.canonical({"build": build, "language": language, "structural": structure})
        second = helper.canonical(
            {
                "build": validate_build(),
                "language": pagewise_language(build),
                "structural": structural(build),
            }
        )
        require(first == second, "B025 whole-reader QA in-process replay differs")
        result: dict[str, Any] = {
            "status": "PASS_DETERMINISTIC_B025_BUILD_LANGUAGE_STRUCTURE_AND_BINDING_QA",
            "page_count": build["page_count"],
            "suspect_pages": language["suspect_pages_requiring_root_adjudication"],
            "required_visual_pages": language["required_individual_visual_pages"],
        }
    elif args.scan:
        result = {
            "status": language["status"],
            "page_count": build["page_count"],
            "language": language,
            "structural": structure,
        }
    else:
        visual = render(build)
        result = (
            {"status": visual["status"], "page_count": build["page_count"], "visual": visual}
            if args.render
            else finalize(build, language, structure, visual)
        )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, OSError, subprocess.SubprocessError, ValueError) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        raise SystemExit(1)
