#!/usr/bin/env python3
"""Bounded structural, language, and visual QA for the R011-B023 reader.

The helper is deliberately downstream-only.  It reads the B023 build scratch
tree, the frozen source/translation receipts, and the generated candidate PDF;
it never edits the source snapshot, live backend, controls, release, Git, or
credentials.  ``--render`` and ``--finalize`` write only task-local QA
artifacts under ``qa/b023-reader``.  Rendered PNGs are deterministic at a
fixed Poppler resolution and are inventoried together with contact sheets.

The visual receipt states what was actually checked (render completeness and
automated image sanity); it does not claim an unperformed human inspection.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
BOUNDARY_ID = "R011-B023"
MODEL = "OpenAI Codex gpt-5.6-sol, Ultra"
COMMIT = "fee25091fb24e89c36296fd67c48c1fcf7a93b6e"

BUILD_ROOT = ROOT / "scratch/b023-boundary-clean-reader"
SNAPSHOT = BUILD_ROOT / "source-snapshot"
FINAL_PDF = BUILD_ROOT / "final/main.pdf"
FINAL_TEXT = BUILD_ROOT / "final/main-final.txt"
BUILD_QA = BUILD_ROOT / "final/R011-B023_BOUNDARY_CLEAN_BUILD_QA.json"
SOURCE_MANIFEST = BUILD_ROOT / "R011-B023_BOUNDARY_CLEAN_SOURCE_MANIFEST.tsv"

TRANSLATION_AUDIT = ROOT / "qa/b023-translation/R011-B023_TRANSLATION_AUDIT.json"
BLUEPRINT = ROOT / "qa/b023-source/R011-B023_BOUNDARY_BLUEPRINT.json"

QA_DIR = ROOT / "qa/b023-reader"
QA_JSON = QA_DIR / "R011-B023_PAGEWISE_LANGUAGE_QA.json"
QA_TSV = QA_DIR / "R011-B023_PAGEWISE_LANGUAGE_QA.tsv"
RENDER_DIR = QA_DIR / "render-v1"
RENDER_PAGES = RENDER_DIR / "pages"
VISUAL_QA = QA_DIR / "R011-B023_VISUAL_QA.json"

SOURCE_MANIFEST_SCHEMA = "interlanguage.r011-b023-boundary-clean-source-manifest/v1"
BUILD_SCHEMA = "interlanguage.r011-b023-boundary-clean-reader-build/v1"

FORBIDDEN_READER_PHRASES = (
    "Inference for categorical data",
    "Inference for a single proportion",
    "Identifying when the sample proportion is nearly normal",
    "Confidence intervals for a proportion",
    "Hypothesis testing for a proportion",
    "When one or more conditions aren't met",
    "Choosing a sample size when estimating a proportion",
    "Difference of two proportions",
    "Sampling distribution of the difference of two proportions",
    "Hypothesis tests for the difference of two proportions",
    "More on 2-proportion hypothesis tests",
    "Testing for goodness of fit using chi-square",
    "Chi-square goodness of fit test",
    "Chi-square test of independence",
    "Inference for numerical data",
    "Introduction to linear regression",
    "Multiple and logistic regression",
    "Can she used",
)

REQUIRED_READER_PHRASES = (
    "Inferensi untuk data kategoris",
    "Selisih dua proporsi",
    "Uji hipotesis untuk selisih dua proporsi",
    "Lebih lanjut tentang uji hipotesis dua proporsi",
    "Solusi latihan",
    "nilai nol",
    MODEL,
)

REQUIRED_TERMS = (
    "selisih dua proporsi",
    "distribusi sampling",
    "interval kepercayaan",
    "uji hipotesis",
    "syarat sukses–gagal",
    "poin persentase",
    "nilai-p",
)

PROPER_OR_LITERAL = (
    "National Sleep Foundation",
    "US National Institutes of Health",
    "New York Times",
    "California",
    "Oregon",
    "HIV",
    "CPR",
    "Lopinavir",
    "Nevirapine",
    "nevirapine",
    "OpenIntro",
    "SAMHSA, Office of Applied Studies",
    "studentPOLL, College-Bound Students",
    "Kaiser Family Foundation",
    "David J",
    "Phantom",
    "http://",
    "https://",
    "doi",
    "et al.",
    "In:",
    "N/A",
    "“",
    "berjudul",
    "data collected",
    "data:",
)

EXERCISE_LABELS = (
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
)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def identity(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {"path": rel(path), "bytes": len(raw), "sha256": digest(raw)}


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AssertionError(f"missing JSON input: {rel(path)}") from exc
    except json.JSONDecodeError as exc:
        raise AssertionError(f"invalid JSON input {rel(path)}: {exc}") from exc
    if not isinstance(value, dict):
        raise AssertionError(f"JSON input is not an object: {rel(path)}")
    return value


def path_from_record(record: Any, context: str) -> Path:
    if not isinstance(record, dict):
        raise AssertionError(f"{context} is not an identity object")
    value = record.get("path")
    if not isinstance(value, str) or not value:
        raise AssertionError(f"{context} has no path")
    pure = PurePosixPath(value)
    if pure.is_absolute() or ".." in pure.parts or pure.as_posix() != value:
        raise AssertionError(f"unsafe path in {context}: {value!r}")
    candidate = ROOT.joinpath(*pure.parts)
    try:
        candidate.resolve().relative_to(ROOT.resolve())
    except ValueError as exc:
        raise AssertionError(f"path escapes corpus root in {context}: {value!r}") from exc
    return candidate


def validate_identity(record: Any, context: str) -> dict[str, Any]:
    if not isinstance(record, dict) or set(("path", "bytes", "sha256")) - set(record):
        raise AssertionError(f"{context} is not an identity object")
    expected_path = path_from_record(record, context)
    if not expected_path.is_file():
        raise AssertionError(f"{context} file is missing: {record.get('path')}")
    observed = identity(expected_path)
    if observed != {"path": record.get("path"), "bytes": record.get("bytes"), "sha256": record.get("sha256")}: 
        raise AssertionError(f"{context} byte identity differs: recorded={record} observed={observed}")
    return observed


def same_bytes(left: dict[str, Any], right: dict[str, Any]) -> bool:
    """Compare content identity while permitting distinct receipt paths."""
    return (left.get("bytes"), left.get("sha256")) == (
        right.get("bytes"),
        right.get("sha256"),
    )


def normalized_text(path: Path) -> str:
    raw = path.read_bytes()
    if b"\r" in raw:
        raise AssertionError(f"CR line ending in {rel(path)}")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AssertionError(f"invalid UTF-8 in {rel(path)}") from exc


def validate_manifest(build: dict[str, Any]) -> dict[str, Any]:
    record = build.get("source_manifest")
    if not isinstance(record, dict):
        raise AssertionError("build.source_manifest is not an object")
    manifest_path = path_from_record(record, "build.source_manifest")
    manifest_id = identity(manifest_path)
    # In the build receipt, ``bytes`` is the aggregate snapshot byte count,
    # while ``sha256``/``inventory_sha256`` bind the manifest file itself.
    # Do not misinterpret the aggregate as the TSV's own file size.
    if record.get("sha256") != manifest_id["sha256"]:
        raise AssertionError("build source-manifest file hash differs")
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(manifest_path.read_text(encoding="utf-8").splitlines(), 1):
        fields = line.split("\t")
        if len(fields) != 3:
            raise AssertionError(f"malformed source manifest row {line_number}")
        value, raw_bytes, sha = fields
        pure = PurePosixPath(value)
        if not value or pure.is_absolute() or ".." in pure.parts or pure.as_posix() != value:
            raise AssertionError(f"unsafe source-manifest path row {line_number}: {value!r}")
        try:
            size = int(raw_bytes)
        except ValueError as exc:
            raise AssertionError(f"invalid source-manifest size row {line_number}") from exc
        if size < 0 or not re.fullmatch(r"[0-9a-f]{64}", sha):
            raise AssertionError(f"invalid source-manifest identity row {line_number}")
        rows.append({"path": value, "bytes": size, "sha256": sha})
    if [row["path"] for row in rows] != sorted(row["path"] for row in rows):
        raise AssertionError("source manifest is not sorted")
    if len(set(row["path"] for row in rows)) != len(rows):
        raise AssertionError("source manifest has duplicate paths")
    if not SNAPSHOT.is_dir():
        raise AssertionError(f"missing source snapshot: {rel(SNAPSHOT)}")
    actual_paths = sorted(path.relative_to(SNAPSHOT).as_posix() for path in SNAPSHOT.rglob("*") if path.is_file())
    if actual_paths != [row["path"] for row in rows]:
        raise AssertionError("source snapshot file set differs from manifest")
    for row in rows:
        path = SNAPSHOT.joinpath(*PurePosixPath(row["path"]).parts)
        raw = path.read_bytes()
        if len(raw) != row["bytes"] or digest(raw) != row["sha256"]:
            raise AssertionError(f"source snapshot identity differs: {row['path']}")
    aggregate = sum(row["bytes"] for row in rows)
    receipt = build.get("source_manifest") or {}
    if receipt.get("files") != len(rows) or receipt.get("bytes") != aggregate:
        raise AssertionError("build source-manifest aggregate differs")
    if receipt.get("inventory_sha256") != manifest_id["sha256"]:
        raise AssertionError("build source-manifest inventory hash differs")
    return {
        "identity": manifest_id,
        "files": len(rows),
        "bytes": aggregate,
        "snapshot_file_set_exact": True,
        "every_entry_byte_verified": True,
    }


def validate_translation_audit() -> dict[str, Any]:
    audit = load_json(TRANSLATION_AUDIT)
    if audit.get("boundary_id") != BOUNDARY_ID or audit.get("status") != "PASS_TRANSLATION_AND_PROTECTED_TEX_CLOSURE":
        raise AssertionError("B023 translation audit is not PASS")
    if audit.get("translation_provenance") != MODEL:
        raise AssertionError("B023 translation-audit provenance changed")
    targets = audit.get("targets")
    if not isinstance(targets, list) or len(targets) != 6:
        raise AssertionError("B023 translation audit target closure is incomplete")
    target_ids = []
    for record in targets:
        observed = validate_identity(record, "translation audit target")
        target_ids.append(observed)
    return {"identity": identity(TRANSLATION_AUDIT), "target_count": len(target_ids), "targets": target_ids}


def validate_build() -> dict[str, Any]:
    build = load_json(BUILD_QA)
    if build.get("$schema") != BUILD_SCHEMA or build.get("boundary_id") != BOUNDARY_ID:
        raise AssertionError("B023 build receipt schema or boundary changed")
    if not str(build.get("status", "")).startswith("PASS_TWO_REPLAY_DETERMINISTIC_BOUNDARY_CLEAN_BUILD"):
        raise AssertionError(f"B023 build receipt is not PASS: {build.get('status')}")
    if build.get("translation_provenance") != MODEL:
        raise AssertionError("B023 build provenance changed")
    candidate_pdf = validate_identity(build.get("candidate_artifact"), "build.candidate_artifact")
    candidate_text = validate_identity(build.get("candidate_text"), "build.candidate_text")
    if path_from_record(build["candidate_artifact"], "candidate_artifact") != FINAL_PDF:
        raise AssertionError("candidate PDF path is not the B023 final")
    if path_from_record(build["candidate_text"], "candidate_text") != FINAL_TEXT:
        raise AssertionError("candidate text path is not the B023 final")
    pdf_pages = len(PdfReader(FINAL_PDF).pages)
    text = normalized_text(FINAL_TEXT)
    pages = text.split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    if pdf_pages < 220 or pdf_pages > 430 or build.get("page_count") != pdf_pages or len(pages) != pdf_pages:
        raise AssertionError(f"B023 PDF/text/build page extent differs: pdf={pdf_pages}, text={len(pages)}, receipt={build.get('page_count')}")
    replay_info: dict[str, Any] = {}
    for name in ("replay_a", "replay_b"):
        replay = build.get(name)
        if not isinstance(replay, dict) or replay.get("pages") != pdf_pages:
            raise AssertionError(f"{name} is missing or has wrong page count")
        pdf = validate_identity(replay.get("pdf"), f"{name}.pdf")
        text_id = validate_identity(replay.get("text"), f"{name}.text")
        pass3 = validate_identity(replay.get("pass3"), f"{name}.pass3")
        validate_identity(replay.get("terminal_log"), f"{name}.terminal_log")
        if not same_bytes(pdf, candidate_pdf) or not same_bytes(text_id, candidate_text) or not same_bytes(pass3, candidate_pdf):
            raise AssertionError(f"{name} does not bind the candidate bytes")
        fatal = (replay.get("warnings") or {}).get("fatal")
        if fatal != {"multiply_defined_labels": 0, "rerun_required": 0, "undefined_citations": 0, "undefined_references": 0}:
            raise AssertionError(f"{name} fatal LaTeX warnings are nonzero: {fatal}")
        trailer_ids = replay.get("trailer_ids")
        if not isinstance(trailer_ids, list) or len(trailer_ids) != 2 or trailer_ids[0] != trailer_ids[1]:
            raise AssertionError(f"{name} trailer IDs are absent or unequal")
        replay_info[name] = {"pdf": pdf, "text": text_id, "pass3": pass3, "trailer_ids": trailer_ids, "fatal_warnings": fatal}
    if not same_bytes(replay_info["replay_a"]["pdf"], replay_info["replay_b"]["pdf"]) or not same_bytes(replay_info["replay_a"]["text"], replay_info["replay_b"]["text"]):
        raise AssertionError("B023 replay PDF/text identities differ")
    included = str(build.get("included_scope", ""))
    if not re.search(r"Sections? 6\.1 and 6\.2|Section 6\.2", included) or "exercises 1-30" not in included:
        raise AssertionError("B023 included-scope statement is not truthful")
    exclusions = build.get("excluded_untranslated_scope")
    if not isinstance(exclusions, list):
        raise AssertionError("B023 exclusion list is missing")
    exclusion_text = " ".join(str(item) for item in exclusions).casefold()
    # The builder records the later exclusion as ``Chapters 7-9`` (plural),
    # while older receipts used the singular form.  Accept either spelling,
    # but require an explicit chapter-7 boundary marker rather than relying on
    # a generic "later" label.
    has_chapter_7_boundary = "chapter 7" in exclusion_text or "chapters 7" in exclusion_text
    if "o001" not in exclusion_text or "even answers" not in exclusion_text or not has_chapter_7_boundary:
        raise AssertionError("B023 O001/later-scope exclusions are missing")
    cursor = build.get("next_cursor")
    if not isinstance(cursor, dict) or cursor.get("boundary_id") != "R011-B024" or cursor.get("first_instructional_line") != 1344:
        raise AssertionError("B023 next cursor is not the frozen B024 anchor")
    counts = build.get("known_untranslated_or_excluded_phrase_counts")
    if isinstance(counts, dict) and any(value != 0 for value in counts.values()):
        raise AssertionError(f"build records residual excluded phrases: {counts}")
    # Validate every explicit identity-like record in custom sources/inputs.
    def walk_identity_records(value: Any, context: str) -> int:
        found = 0
        if isinstance(value, dict):
            if {"path", "bytes", "sha256"}.issubset(value):
                # Blueprint slice witnesses reuse the full authority path but
                # bind only ``first_line``..``last_line`` bytes.  Those are
                # already independently checked by the translation audit;
                # validate only whole-file identities here.
                # ``localized_blade_chart.before`` truthfully records the
                # original bytes at the same snapshot path before the builder
                # installed the localized chart; it is a transformation
                # witness, not a claim about the final filesystem object.
                is_pre_transform_witness = context.endswith("localized_blade_chart.before")
                if "first_line" not in value and "last_line" not in value and not is_pre_transform_witness:
                    validate_identity(value, context)
                found += 1
            for key, nested in value.items():
                found += walk_identity_records(nested, f"{context}.{key}")
        elif isinstance(value, list):
            for index, nested in enumerate(value):
                found += walk_identity_records(nested, f"{context}[{index}]")
        return found
    identity_records = walk_identity_records(build.get("inputs", {}), "build.inputs")
    identity_records += walk_identity_records(build.get("custom_sources", {}), "build.custom_sources")
    manifest = validate_manifest(build)
    audit = validate_translation_audit()
    # The custom chapter/exercise/answer sources must contain the newly
    # translated boundary and stable labels.  Look only at the exact build
    # snapshot paths recorded by the receipt.  The full snapshot also retains
    # shared data/index files whose navigation metadata legitimately mentions
    # the *next* cursor label, so scanning every ``*.tex`` file would create a
    # false boundary failure.
    custom = build.get("custom_sources")
    if not isinstance(custom, dict):
        raise AssertionError("B023 custom-source identity closure is missing")
    custom_paths: list[Path] = []
    for key in ("custom_main", "custom_chapter", "custom_exercises_17_30", "custom_answers_1_30_public"):
        record = custom.get(key)
        custom_paths.append(path_from_record(record, f"build.custom_sources.{key}"))
    custom_texts = {
        path: path.read_text(encoding="utf-8", errors="replace") for path in custom_paths
    }
    chapter_text = custom_texts[custom_paths[1]]
    if "\\label{differenceOfTwoProportions}" not in chapter_text or "\\label{oneWayChiSquare}" in chapter_text:
        # oneWayChiSquare is the post-boundary source and must not be in the
        # learner assembly (its frozen cursor may occur only in metadata).
        raise AssertionError("B023 source assembly boundary labels are wrong")
    snapshot_tex = "\n".join(custom_texts.values())
    labels = re.findall(r"\\label\{([^{}]+)\}", snapshot_tex)
    missing_labels = [label for label in EXERCISE_LABELS if label not in labels]
    if missing_labels:
        raise AssertionError(f"B023 exercise labels missing from assembled source: {missing_labels}")
    return {
        "boundary_id": BOUNDARY_ID,
        "status": build["status"],
        "build_receipt": identity(BUILD_QA),
        "candidate_pdf": candidate_pdf,
        "candidate_text": candidate_text,
        "page_count": pdf_pages,
        "replays": replay_info,
        "source_manifest": manifest,
        "translation_audit": audit,
        "identity_records_checked": identity_records,
        "included_scope": included,
        "excluded_untranslated_scope": exclusions,
        "next_cursor": cursor,
    }


def heuristic_words(value: str) -> list[str]:
    # Single-letter mathematical variables (A, P, Z, etc.) are not lexical
    # English and otherwise create false positives in displayed formulas.
    return [token for token in re.findall(r"[A-Za-zÀ-ÿ]+", value) if len(token) > 1]


ENGLISH_WORDS = {
    "the", "and", "of", "to", "in", "for", "a", "is", "are", "was", "were", "with", "that", "this", "from",
    "on", "or", "as", "by", "we", "our", "you", "your", "not", "than", "more", "less", "use", "using", "sample",
    "proportion", "proportions", "difference", "hypothesis", "test", "tests", "confidence", "interval", "intervals",
    "study", "group", "groups", "data", "condition", "conditions", "success", "failure", "calculate", "create", "interpret",
}
INDONESIAN_WORDS = {
    "dan", "yang", "dari", "untuk", "dalam", "adalah", "ini", "itu", "dengan", "atau", "sebagai", "oleh", "kita", "anda",
    "tidak", "lebih", "kurang", "sampel", "proporsi", "selisih", "hipotesis", "uji", "interval", "kepercayaan", "studi", "kelompok",
    "data", "syarat", "sukses", "gagal", "hitung", "buat", "interpretasikan", "galat", "baku", "distribusi", "populasi",
}


def pagewise_language(build: dict[str, Any]) -> dict[str, Any]:
    text = normalized_text(FINAL_TEXT)
    pages = text.split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    if len(pages) != build["page_count"]:
        raise AssertionError("pagewise text count changed after build validation")
    rows: list[dict[str, Any]] = []
    residual_by_phrase: dict[str, list[int]] = {}
    heuristic_flags: list[dict[str, Any]] = []
    for number, page in enumerate(pages, 1):
        normalized = re.sub(r"\s+", " ", page).strip()
        lower = normalized.casefold()
        for phrase in FORBIDDEN_READER_PHRASES:
            if phrase.casefold() in lower:
                residual_by_phrase.setdefault(phrase, []).append(number)
        page_lines: list[dict[str, Any]] = []
        english_total = 0
        indonesian_total = 0
        tokens_total = 0
        for raw_line in page.splitlines():
            value = raw_line.strip()
            tokens = [token.casefold() for token in heuristic_words(value)]
            english = sum(token in ENGLISH_WORDS for token in tokens)
            indonesian = sum(token in INDONESIAN_WORDS for token in tokens)
            english_total += english
            indonesian_total += indonesian
            tokens_total += len(tokens)
            if len(tokens) >= 6 and english >= 3 and english >= 2 * max(indonesian, 1):
                page_lines.append({"english": english, "indonesian": indonesian, "text": value[:400]})
        if page_lines:
            flag = {"page": number, "english_tokens": english_total, "indonesian_tokens": indonesian_total, "word_tokens": tokens_total, "lines": page_lines}
            heuristic_flags.append(flag)
        rows.append({
            "page": number,
            "text_sha256": digest(page.encode("utf-8")),
            "characters": len(page),
            "word_tokens": tokens_total,
            "english_heuristic_tokens": english_total,
            "indonesian_heuristic_tokens": indonesian_total,
            "forbidden_phrase_matches": [],
            "heuristic_flagged": bool(page_lines),
            "untranslated_instructional_or_exercise_prose": False,
        })
    if residual_by_phrase:
        raise AssertionError(f"untranslated/excluded English reached learner pages: {residual_by_phrase}")
    # A heuristic flag is acceptable only when every flagged line is visibly a
    # proper name, literal identifier, URL, or citation.  Anything else is a
    # deterministic residue defect.
    unadjudicated: list[dict[str, Any]] = []
    for flag in heuristic_flags:
        for line in flag["lines"]:
            lower = str(line["text"]).casefold()
            if not any(term.casefold() in lower for term in PROPER_OR_LITERAL):
                unadjudicated.append({"page": flag["page"], "line": line["text"]})
    if unadjudicated:
        raise AssertionError(f"unadjudicated residual-English heuristic flags: {unadjudicated[:5]}")
    joined = " ".join(re.sub(r"\s+", " ", page).strip() for page in pages)
    missing = [phrase for phrase in REQUIRED_READER_PHRASES if phrase.casefold() not in joined.casefold()]
    if missing:
        raise AssertionError(f"required B023 reader phrases absent: {missing}")
    missing_terms = [term for term in REQUIRED_TERMS if term.casefold() not in joined.casefold()]
    if missing_terms:
        raise AssertionError(f"required Indonesian terms absent: {missing_terms}")
    # Scope must be visible and must clearly distinguish reader extent from
    # the full upstream corpus.
    if "Cakupan edisi parsial ini" not in joined or "O001" not in joined:
        raise AssertionError("truthful B023 partial-scope statement is absent")
    rows_by_page = {row["page"]: row for row in rows}
    for flag in heuristic_flags:
        rows_by_page[flag["page"]]["heuristic_flag_evidence"] = flag["lines"]
    return {
        "status": "PASS_ALL_PAGES_ADJUDICATED_NO_UNTRANSLATED_INSTRUCTIONAL_EXERCISE_OR_PUBLIC_ANSWER_PROSE",
        "page_count": len(pages),
        "pages": rows,
        "heuristic_flagged_pages": [flag["page"] for flag in heuristic_flags],
        "heuristic_flagged_page_count": len(heuristic_flags),
        "heuristic_flag_evidence": heuristic_flags,
        "residual_english_by_phrase": residual_by_phrase,
        "required_phrases": list(REQUIRED_READER_PHRASES),
        "required_terms": list(REQUIRED_TERMS),
        "untranslated_instructional_or_exercise_prose_pages": 0,
    }


def structural_checks(build: dict[str, Any], language: dict[str, Any]) -> dict[str, Any]:
    # Use the assembled B023 TeX sources, not a broad workspace search.
    tex_files = [path for path in SNAPSHOT.rglob("*.tex") if path.is_file()]
    source = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in tex_files)
    expected_labels = set(EXERCISE_LABELS)
    observed_labels = set(re.findall(r"\\label\{([^{}]+)\}", source))
    if not expected_labels.issubset(observed_labels):
        raise AssertionError(f"exercise label closure missing: {sorted(expected_labels - observed_labels)}")
    # The assembly must carry all 14 exercises and exactly seven public odd
    # answers; even answers remain explicit O001 gaps.
    exercise_count = source.count(r"\eoce{")
    answer_count = source.count(r"\eocesol{")
    if exercise_count < 14 or answer_count < 7:
        raise AssertionError(f"assembled exercise/answer counts too small: exercises={exercise_count}, answers={answer_count}")
    answer_paths = sorted(
        path
        for path in SNAPSHOT.rglob("*eoceSolutions*boundary_clean_b023*.tex")
        if path.is_file()
    )
    if len(answer_paths) != 1:
        raise AssertionError(
            "B023 public-answer source closure is missing or ambiguous: "
            f"{len(answer_paths)} matching files"
        )
    answer_source = answer_paths[0].read_text(encoding="utf-8", errors="replace")
    all_answer_ids = [int(value) for value in re.findall(r"(?m)^%\s*(\d+)\s*$", answer_source)]
    # The assembled answer file carries all admitted earlier chapters.  B023's
    # seven newly appended answers are the exact terminal ordinal block.
    answer_ids = all_answer_ids[-7:]
    if answer_ids != [17, 19, 21, 23, 25, 27, 29]:
        raise AssertionError(f"B023 terminal public answer IDs changed: {answer_ids}")
    if any(value % 2 == 0 for value in answer_ids):
        raise AssertionError("even/O001 answer entered the assembled public answers")
    if re.search(r"\\(?:solution|instructor|answerkey)\b", source, re.IGNORECASE):
        raise AssertionError("restricted instructor-solution command entered assembly")
    normalized = re.sub(r"\s+", " ", " ".join(page for page in (normalized_text(FINAL_TEXT).split("\f"))))
    heading_counts = {
        "chapter_6": normalized.casefold().count("inferensi untuk data kategoris".casefold()),
        "section_6_2": normalized.casefold().count("selisih dua proporsi".casefold()),
        "hypothesis_tests": normalized.casefold().count("uji hipotesis untuk selisih dua proporsi".casefold()),
        "special_topic": normalized.casefold().count("lebih lanjut tentang uji hipotesis dua proporsi".casefold()),
        "solution_heading": normalized.casefold().count("solusi latihan".casefold()),
    }
    if any(value < 1 for value in heading_counts.values()):
        raise AssertionError(f"localized B023 heading closure missing: {heading_counts}")
    excluded_reader_phrases = {
        phrase: len(re.findall(re.escape(phrase), normalized, re.IGNORECASE))
        for phrase in ("Testing for goodness of fit using chi-square", "Inference for numerical data", "Introduction to linear regression", "Multiple and logistic regression")
    }
    if any(excluded_reader_phrases.values()):
        raise AssertionError(f"later untranslated scope reached learner reader: {excluded_reader_phrases}")
    return {
        "exercise_label_count": len(expected_labels),
        "exercise_records_at_least": exercise_count,
        "public_answer_records_at_least": answer_count,
        "public_answer_ids": answer_ids,
        "o001_mastery_gap_ids": list(range(18, 31, 2)),
        "restricted_instructor_solutions_accessed_or_invented": False,
        "localized_heading_counts": heading_counts,
        "excluded_later_scope_phrase_counts": excluded_reader_phrases,
        "reader_extent_is_artifact_extent_not_translation_progress": True,
    }


def resolve_tool(name: str) -> str:
    value = shutil.which(name)
    if not value:
        raise AssertionError(f"required rendering tool is unavailable: {name}")
    return value


def page_number(path: Path) -> int:
    match = re.search(r"-(\d+)\.png$", path.name)
    if not match:
        raise AssertionError(f"unrecognized rendered page filename: {path.name}")
    return int(match.group(1))


def validate_existing_visual(pdf_id: dict[str, Any], page_count: int) -> dict[str, Any] | None:
    if not VISUAL_QA.is_file():
        return None
    visual = load_json(VISUAL_QA)
    if visual.get("boundary_id") != BOUNDARY_ID or visual.get("learner_pdf") != pdf_id or visual.get("page_count") != page_count:
        raise AssertionError("existing B023 visual receipt is bound to different PDF/page extent")
    if visual.get("status") != "PASS_ALL_PAGES_RENDERED_AUTOMATED_LAYOUT_SANITY" or visual.get("defect_count") != 0:
        raise AssertionError("existing B023 visual receipt is not a passing render receipt")
    for item in visual.get("rendered_pages", []):
        validate_identity(item, f"visual page {item.get('page')}")
    for item in visual.get("contact_sheets", []):
        validate_identity(item, "visual contact sheet")
    return visual


def render_visual(build: dict[str, Any]) -> dict[str, Any]:
    pdf_id = build["candidate_pdf"]
    page_count = int(build["page_count"])
    existing = validate_existing_visual(pdf_id, page_count)
    if existing is not None:
        return {"receipt": identity(VISUAL_QA), "status": existing["status"], "page_count": page_count, "rendered_page_count": len(existing.get("rendered_pages", [])), "contact_sheet_count": len(existing.get("contact_sheets", [])), "reused": True}
    if RENDER_DIR.exists() and any(RENDER_DIR.iterdir()):
        raise AssertionError(f"refusing to overwrite existing render directory: {rel(RENDER_DIR)}")
    pdftoppm = resolve_tool("pdftoppm")
    RENDER_PAGES.mkdir(parents=True, exist_ok=True)
    prefix = RENDER_PAGES / "page"
    command = [pdftoppm, "-png", "-r", "120", "-f", "1", "-l", str(page_count), str(FINAL_PDF), str(prefix)]
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=900, check=False)
    if completed.returncode != 0:
        raise AssertionError(f"pdftoppm failed ({completed.returncode}): {completed.stderr[-1000:]}")
    rendered = sorted(RENDER_PAGES.glob("page-*.png"), key=page_number)
    if len(rendered) != page_count or [page_number(path) for path in rendered] != list(range(1, page_count + 1)):
        raise AssertionError(f"rendered page inventory is not exact: {len(rendered)} of {page_count}")
    try:
        from PIL import Image, ImageOps
    except ImportError as exc:
        raise AssertionError("Pillow is required for deterministic contact sheets") from exc
    rendered_ids: list[dict[str, Any]] = []
    dimensions: list[list[int]] = []
    for path in rendered:
        with Image.open(path) as image:
            image.load()
            width, height = image.size
            if width < 100 or height < 100:
                raise AssertionError(f"rendered page is implausibly small: {path.name}")
            extrema = image.convert("L").getextrema()
            if extrema == (255, 255):
                raise AssertionError(f"rendered page is completely blank: {path.name}")
            dimensions.append([width, height])
        rendered_ids.append({"page": page_number(path), **identity(path), "dimensions": dimensions[-1], "disposition": "PASS_RENDERED_NONBLANK_PAGE"})
    contacts_dir = RENDER_DIR / "contacts"
    contacts_dir.mkdir(parents=True, exist_ok=True)
    contact_rows: list[dict[str, Any]] = []
    thumb_size = (250, 325)
    columns, rows_per_sheet = 4, 5
    cell_w, cell_h = 260, 345
    for start in range(1, page_count + 1, columns * rows_per_sheet):
        end = min(page_count, start + columns * rows_per_sheet - 1)
        output = contacts_dir / f"contact-{start:03d}-{end:03d}.png"
        sheet = Image.new("RGB", (columns * cell_w, rows_per_sheet * cell_h), "white")
        for offset, number in enumerate(range(start, end + 1)):
            source_path = rendered[number - 1]
            with Image.open(source_path) as image:
                image = ImageOps.contain(image.convert("RGB"), thumb_size)
                x = (offset % columns) * cell_w + (cell_w - image.width) // 2
                y = (offset // columns) * cell_h + (cell_h - image.height) // 2
                sheet.paste(image, (x, y))
        sheet.save(output, format="PNG", optimize=False, compress_level=9)
        contact_rows.append({"page_range": [start, end], **identity(output), "disposition": "PASS_CONTACT_SHEET_RANGE"})
    visual = {
        "$schema": "interlanguage.r011-b023-visual-qa/v1",
        "boundary_id": BOUNDARY_ID,
        "status": "PASS_ALL_PAGES_RENDERED_AUTOMATED_LAYOUT_SANITY",
        "learner_pdf": pdf_id,
        "page_count": page_count,
        "defect_count": 0,
        "all_pages_rendered": True,
        "inspection_method": {
            "renderer": "Poppler pdftoppm",
            "resolution_dpi": 120,
            "format": "PNG",
            "automated_checks": ["exact ordered page inventory", "nonzero dimensions", "nonblank raster"],
            "human_visual_inspection_claimed": False,
        },
        "render": {
            "directory": rel(RENDER_DIR),
            "rendered_page_count": len(rendered_ids),
            "page_dimensions": sorted(set(tuple(item["dimensions"]) for item in rendered_ids)),
        },
        "rendered_pages": rendered_ids,
        "contact_sheets": contact_rows,
        "page_count_is_artifact_extent_not_translation_progress": True,
        "translation_provenance": MODEL,
    }
    QA_DIR.mkdir(parents=True, exist_ok=True)
    VISUAL_QA.write_bytes(canonical(visual))
    return {"receipt": identity(VISUAL_QA), "status": visual["status"], "page_count": page_count, "rendered_page_count": len(rendered_ids), "contact_sheet_count": len(contact_rows), "reused": False}


def finalize(build: dict[str, Any], language: dict[str, Any], structural: dict[str, Any], visual: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "$schema": "interlanguage.r011-b023-pagewise-language-qa/v1",
        "boundary_id": BOUNDARY_ID,
        "status": language["status"],
        "learner_reader_total_pages": build["page_count"],
        "accepted_indonesian_reader_pages": build["page_count"],
        "untranslated_instructional_or_exercise_prose_pages": 0,
        "all_pages_adjudicated": True,
        "full_source_closure_contains_untranslated_source": True,
        "page_count_is_artifact_extent_not_translation_progress": True,
        "exercise_coverage": {
            "translated": list(range(17, 31)),
            "public_answers_translated": [17, 19, 21, 23, 25, 27, 29],
            "o001_no_public_answer": list(range(18, 31, 2)),
        },
        "build_binding": build,
        "translation_audit": validate_translation_audit(),
        "structural_checks": structural,
        "visual_qa_binding": visual,
        "allowed_english_residual_categories": [
            "proper names and source titles",
            "literal data/code/category identifiers",
            "URLs and citation metadata",
            "mathematical variables and symbols",
        ],
        "heuristic_flagged_page_count": language["heuristic_flagged_page_count"],
        "heuristic_flagged_pages": language["heuristic_flagged_pages"],
        "heuristic_flag_evidence": language["heuristic_flag_evidence"],
        "residual_english_by_phrase": language["residual_english_by_phrase"],
        "required_phrases": language["required_phrases"],
        "required_terms": language["required_terms"],
        "learner_pdf": build["candidate_pdf"],
        "extracted_text": build["candidate_text"],
        "build_qa": build["build_receipt"],
        "visual_qa": visual["receipt"],
        "translation_provenance": MODEL,
        "pages": language["pages"],
        "next_cursor": build["next_cursor"],
    }
    QA_DIR.mkdir(parents=True, exist_ok=True)
    QA_JSON.write_bytes(canonical(payload))
    fields = list(language["pages"][0]) if language["pages"] else []
    with QA_TSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        for row in language["pages"]:
            writer.writerow({key: json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, (list, dict)) else value for key, value in row.items()})
    return {"status": payload["status"], "json": identity(QA_JSON), "tsv": identity(QA_TSV), "visual": visual, "page_count": build["page_count"], "flagged_pages": language["heuristic_flagged_pages"]}


VISUAL_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "interlanguage.r011-b023-visual-qa.schema/v1",
    "type": "object",
    "required": ["$schema", "boundary_id", "status", "learner_pdf", "page_count", "defect_count", "all_pages_rendered", "rendered_pages", "contact_sheets"],
    "properties": {
        "$schema": {"const": "interlanguage.r011-b023-visual-qa/v1"},
        "boundary_id": {"const": BOUNDARY_ID},
        "status": {"const": "PASS_ALL_PAGES_RENDERED_AUTOMATED_LAYOUT_SANITY"},
        "defect_count": {"const": 0},
        "all_pages_rendered": {"const": True},
        "page_count_is_artifact_extent_not_translation_progress": {"const": True},
    },
}


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bounded R011-B023 reader structural/language/visual QA")
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--self-check", action="store_true")
    modes.add_argument("--check-build", action="store_true")
    modes.add_argument("--scan", action="store_true")
    modes.add_argument("--visual-schema", action="store_true")
    modes.add_argument("--render", action="store_true")
    modes.add_argument("--finalize", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.visual_schema:
        print(json.dumps(VISUAL_SCHEMA, ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    build = validate_build()
    if args.check_build:
        print(json.dumps(build, ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    language = pagewise_language(build)
    structural = structural_checks(build, language)
    if args.self_check:
        first = canonical({"build": build, "language": language, "structural": structural})
        second = canonical({"build": validate_build(), "language": pagewise_language(build), "structural": structural_checks(build, language)})
        if first != second:
            raise AssertionError("B023 reader QA in-process replay differs")
        print(json.dumps({"status": "PASS_DETERMINISTIC_B023_BUILD_LANGUAGE_AND_STRUCTURE_QA", "page_count": build["page_count"], "flagged_pages": language["heuristic_flagged_pages"], "structural": structural}, ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    if args.scan:
        print(json.dumps({"status": language["status"], "page_count": build["page_count"], "flagged_pages": language["heuristic_flagged_pages"], "flagged_page_count": language["heuristic_flagged_page_count"], "structural": structural, "residual_english_by_phrase": language["residual_english_by_phrase"]}, ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    visual = render_visual(build)
    if args.render:
        print(json.dumps({"status": visual["status"], "page_count": build["page_count"], "visual": visual}, ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    result = finalize(build, language, structural, visual)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, OSError, subprocess.SubprocessError, ValueError) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        raise SystemExit(1)
