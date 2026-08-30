#!/usr/bin/env python3
"""Deterministic whole-reader QA for the boundary-clean R011-B026 candidate.

The candidate is read-only.  All generated QA artifacts are confined to
``qa/b026-reader``.  Post-build byte bindings fail closed until the completed
two-replay builder provides the exact receipt, PDF, UTF-8 text, manifest, and
page count.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

import pdfplumber
from PIL import Image, ImageOps, ImageStat
from pypdf import PdfReader
from pypdf.generic import ArrayObject, ContentStream, IndirectObject


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "qa_b025_for_b026", ROOT / "scripts/qa_b025_boundary_clean_reader.py"
)
assert spec and spec.loader
b025 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b025)
lexicon = b025.helper

BOUNDARY_ID = "R011-B026"
MODEL = "OpenAI Codex gpt-5.6-sol, Ultra"
BUILD_ROOT = ROOT / "scratch/b026-boundary-clean-reader"
FINAL_PDF = BUILD_ROOT / "final/main.pdf"
FINAL_TEXT = BUILD_ROOT / "final/main-final.txt"
BUILD_QA = BUILD_ROOT / "final/R011-B026_BOUNDARY_CLEAN_BUILD_QA.json"
SOURCE_MANIFEST = BUILD_ROOT / "R011-B026_BOUNDARY_CLEAN_SOURCE_MANIFEST.tsv"
SNAPSHOT = BUILD_ROOT / "source-snapshot"

QA_DIR = ROOT / "qa/b026-reader"
AUTOMATED_QA = QA_DIR / "R011-B026_AUTOMATED_READER_QA.json"
PAGEWISE_QA = QA_DIR / "R011-B026_PAGEWISE_LANGUAGE_QA.json"
PAGEWISE_TSV = QA_DIR / "R011-B026_PAGEWISE_LANGUAGE_QA.tsv"
VISUAL_QA = QA_DIR / "R011-B026_AUTOMATED_VISUAL_QA.json"
ROOT_VISUAL_QA = QA_DIR / "R011-B026_ROOT_VISUAL_INSPECTION_QA.json"
RENDER_DIR = QA_DIR / "render-v1"
RENDER_PAGES = RENDER_DIR / "pages"
RENDER_CONTACTS = RENDER_DIR / "contacts"
REJECTED_275_VISUAL_QA = (
    QA_DIR
    / "rejected-5b83846d/R011-B026_AUTOMATED_VISUAL_QA.json"
)
EXPECTED_REJECTED_275_VISUAL_QA = (
    149_478,
    "fce70c52c89f89046acd38cf5d8d2fb22e0705bac1b9ef52d19e718ef18fa552",
)
PDFTOPPM = Path(
    r"C:\Users\Floris\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin\pdftoppm.exe"
)

# BEGIN POST-BUILD BINDING BLOCK.  These values are patched only from the
# completed deterministic build and are never inferred from progress claims.
EXPECTED_BUILD_QA: tuple[int, str] | None = (
    25_201,
    "10c91e17f19ce0a75d707b4891571e8c46a10883cfc2066edba73226e9e40b1a",
)
EXPECTED_PDF: tuple[int, str] | None = (
    12_782_877,
    "0f61722fe01afe18552e949dfd4d3addba450c6e0337767ea2448d982012f0d6",
)
EXPECTED_TEXT: tuple[int, str] | None = (
    873_719,
    "4344726ad43b62109d09aa624fed81fe34c36788213be6635a89634163f47b47",
)
EXPECTED_SOURCE_MANIFEST: tuple[int, str] | None = (
    177_439,
    "858ca66c52d547eb33696ce93435b77391e3b2b72dafae29f7ca48300f4a2a97",
)
EXPECTED_PAGE_COUNT: int | None = 273
# END POST-BUILD BINDING BLOCK.

ASSET_QA = ROOT / "qa/b026-translation/R011-B026_ASSET_LOCALIZATION_QA.json"
EXPECTED_ASSET_QA = (
    35_730,
    "b479bb7bdacda021bee1afd7380bfdea1c98915b1a693369d4a224216b48b9c1",
    "PASS_DETERMINISTIC_ASSET_LOCALIZATION_AND_VISUAL_QA",
)
ASSET_ROOT_VISUAL = (
    ROOT
    / "qa/b026-translation/"
    "R011-B026_ASSET_ROOT_VISUAL_INSPECTION_QA.json"
)
EXPECTED_ASSET_ROOT_VISUAL = (
    3_636,
    "9c6a6bdd7683e98204c722e9ad9a70c873d0182e557681f07b1f3d0484eedbf0",
    "PASS_ALL_8_LOCALIZED_ASSETS_VISUALLY_INSPECTED_AFTER_ONE_CORRECTION_ZERO_REMAINING_DEFECTS",
)

EXPECTED_METADATA = {
    "/Author": "David M. Diez, Mine Çetinkaya-Rundel, Christopher D. Barr",
    "/Title": "Statistika Berbasis Data",
    "/Subject": "Karya turunan berbahasa Indonesia dari OpenIntro Statistics, Edisi Keempat",
    "/Creator": "LaTeX with hyperref",
    "/Keywords": "statistika, data, buku teks, bahasa Indonesia",
    "/CreationDate": "D:20260829000000Z",
    "/ModDate": "D:20260829000000Z",
}

EXERCISE_LABELS = (
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
    "car_insurance_savings",
    "sat_scores_CI",
)

FORBIDDEN_ENGLISH = (
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
    "t-distribution",
    "solid",
    "dashed",
    "dotted",
)
FORBIDDEN_LATER_INDONESIAN = (
    "7.2 Data berpasangan",
    "7.3 Selisih dua rata-rata",
    "7.4 Daya untuk selisih dua rata-rata",
    "7.5 ANOVA dan regresi dengan variabel kategoris",
    "8 Pengantar regresi linear",
    "9 Regresi linear berganda dan logistik",
)
REQUIRED_TEXT = (
    "Pembaca ini berhenti tepat setelah Bagian 7.1",
    "Rata-rata satu sampel dengan distribusi t",
    "Cakupan Bab 7 dalam edisi ini memuat latihan 1–14",
    "jawaban bernomor ganjil 1–13",
    "Inferensi untuk data numerik",
    "Teorema Limit Pusat untuk rata-rata sampel",
    "Memperkenalkan distribusi t",
    "Interval kepercayaan t satu sampel",
    "Uji t satu sampel",
    "Tentukan nilai kritis t",
    "Kebiasaan tidur warga New York",
    "Tinggi badan orang dewasa",
    "Solusi latihan",
    "Observasi Sampel 1",
    "Observasi Sampel 2",
    "Frekuensi",
    "Waktu (Menit)",
    "padat",
    "putus-putus",
    "titik-titik",
    "Tinggi",
    MODEL,
)
TOC_REQUIRED = (
    "Daftar Isi",
    "7 Inferensi untuk data numerik",
    "7.1 Rata-rata satu sampel dengan distribusi t",
    "A Solusi latihan",
)
VISUAL_ANCHORS = (
    "Cakupan edisi parsial ini",
    "Inferensi untuk data numerik",
    "Rata-rata satu sampel dengan distribusi t",
    "Observasi Sampel 1",
    "Perbandingan distribusi t dan distribusi normal",
    "Distribusi t dengan 18 derajat kebebasan",
    "Distribusi t dengan 20 derajat kebebasan",
    "Seekor lumba-lumba Risso",
    "Cherry Blossom Race 2017",
    "Tentukan nilai kritis t",
    "Tinggi badan orang dewasa",
    "Solusi latihan",
)
ALLOWED_ENGLISH_MARKERS = tuple(lexicon.PROPER_OR_LITERAL) + (
    "OpenIntro",
    "Cherry Blossom Race",
    "New York",
    "Washington",
    "Risso",
    "Mike Baird",
    "SAT",
    "Central Park",
    "Everett",
    "Mercury",
    "Pacific",
    "California",
    "Harris",
    "Casper",
    "Rosenbaum",
    "Wolfe",
    "JAMA",
    "URL",
    "ISBN",
    "doi",
    "df",
)


class GateError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GateError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def compact(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def identity(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {"path": rel(path), "bytes": len(raw), "sha256": digest(raw)}


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON is not an object: {rel(path)}")
    return value


def exact(path: Path, expected: tuple[int, str], label: str) -> dict[str, Any]:
    row = identity(path)
    require((row["bytes"], row["sha256"]) == expected, f"{label} identity changed: {row}")
    return row


def path_from_record(record: Any, label: str) -> Path:
    require(isinstance(record, dict), f"{label} is not an identity")
    value = record.get("path")
    require(isinstance(value, str) and value, f"{label}.path absent")
    pure = PurePosixPath(value)
    require(not pure.is_absolute() and ".." not in pure.parts and pure.as_posix() == value, f"unsafe {label}.path")
    path = ROOT.joinpath(*pure.parts)
    require(path.resolve().is_relative_to(ROOT.resolve()), f"{label}.path escapes corpus")
    return path


def validate_record(record: Any, label: str) -> dict[str, Any]:
    path = path_from_record(record, label)
    require(path.is_file(), f"{label} file absent: {rel(path)}")
    observed = identity(path)
    require(observed == {k: record.get(k) for k in ("path", "bytes", "sha256")}, f"{label} identity mismatch")
    return observed


def same_bytes(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return (left.get("bytes"), left.get("sha256")) == (right.get("bytes"), right.get("sha256"))


def binding_requirements() -> dict[str, Any]:
    bindings = {
        "EXPECTED_BUILD_QA": EXPECTED_BUILD_QA,
        "EXPECTED_PDF": EXPECTED_PDF,
        "EXPECTED_TEXT": EXPECTED_TEXT,
        "EXPECTED_SOURCE_MANIFEST": EXPECTED_SOURCE_MANIFEST,
        "EXPECTED_PAGE_COUNT": EXPECTED_PAGE_COUNT,
    }
    return {
        "status": "READY" if all(value is not None for value in bindings.values()) else "PENDING_DETERMINISTIC_B026_BUILD",
        "bindings": bindings,
        "candidate_root": rel(BUILD_ROOT),
        "writes_performed": False,
    }


def require_bindings() -> None:
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
    require(not missing, "post-build B026 bindings unset: " + ", ".join(missing))


def validate_manifest(build: dict[str, Any]) -> dict[str, Any]:
    assert EXPECTED_SOURCE_MANIFEST is not None
    manifest_id = exact(SOURCE_MANIFEST, EXPECTED_SOURCE_MANIFEST, "B026 source manifest")
    record = build.get("source_manifest")
    require(isinstance(record, dict), "build.source_manifest absent")
    require(record.get("path") == manifest_id["path"] and record.get("sha256") == manifest_id["sha256"], "build manifest binding differs")
    rows: list[dict[str, Any]] = []
    for number, line in enumerate(SOURCE_MANIFEST.read_text(encoding="utf-8").splitlines(), 1):
        fields = line.split("\t")
        require(len(fields) == 3, f"malformed manifest row {number}")
        path, size_text, sha = fields
        pure = PurePosixPath(path)
        require(path and not pure.is_absolute() and ".." not in pure.parts and pure.as_posix() == path, f"unsafe manifest row {number}")
        require(size_text.isdigit() and re.fullmatch(r"[0-9a-f]{64}", sha) is not None, f"invalid manifest identity row {number}")
        rows.append({"path": path, "bytes": int(size_text), "sha256": sha})
    require([row["path"] for row in rows] == sorted(row["path"] for row in rows), "manifest not sorted")
    require(len({row["path"] for row in rows}) == len(rows), "manifest duplicate path")
    actual = sorted(path.relative_to(SNAPSHOT).as_posix() for path in SNAPSHOT.rglob("*") if path.is_file())
    require(actual == [row["path"] for row in rows], "snapshot file closure differs from manifest")
    total = 0
    for row in rows:
        path = SNAPSHOT.joinpath(*PurePosixPath(row["path"]).parts)
        raw = path.read_bytes()
        require(len(raw) == row["bytes"] and digest(raw) == row["sha256"], f"snapshot identity differs: {row['path']}")
        total += len(raw)
    require(record.get("files") == len(rows) and record.get("bytes") == total, "manifest aggregate differs")
    return {**manifest_id, "files": len(rows), "snapshot_bytes": total, "inventory_sha256": record.get("inventory_sha256")}


def validate_build() -> dict[str, Any]:
    require_bindings()
    assert EXPECTED_BUILD_QA is not None
    assert EXPECTED_PDF is not None
    assert EXPECTED_TEXT is not None
    assert EXPECTED_PAGE_COUNT is not None
    build_id = exact(BUILD_QA, EXPECTED_BUILD_QA, "B026 build receipt")
    pdf_id = exact(FINAL_PDF, EXPECTED_PDF, "B026 candidate PDF")
    text_id = exact(FINAL_TEXT, EXPECTED_TEXT, "B026 candidate text")
    build = load_json(BUILD_QA)
    require(build.get("$schema") == "interlanguage.r011-b026-boundary-clean-reader-build/v1", "build schema changed")
    require(build.get("boundary_id") == BOUNDARY_ID, "build boundary changed")
    require(str(build.get("status", "")).startswith("PASS_TWO_REPLAY_DETERMINISTIC_BOUNDARY_CLEAN_BUILD"), "build status is not PASS")
    require(build.get("page_count") == EXPECTED_PAGE_COUNT, "build page count differs")
    candidate = validate_record(build.get("candidate_artifact"), "candidate_artifact")
    candidate_text = validate_record(build.get("candidate_text"), "candidate_text")
    require(candidate == pdf_id and candidate_text == text_id, "build candidate binding differs")
    replay_rows: dict[str, Any] = {}
    for name in ("replay_a", "replay_b"):
        row = build.get(name)
        require(isinstance(row, dict), f"{name} absent")
        pdf = validate_record(row.get("pdf"), f"{name}.pdf")
        text = validate_record(row.get("text"), f"{name}.text")
        pass3 = validate_record(row.get("pass3"), f"{name}.pass3")
        terminal = validate_record(row.get("terminal_log"), f"{name}.terminal_log")
        require(same_bytes(pdf, pdf_id) and same_bytes(pass3, pdf_id), f"{name} PDF/pass3 differs")
        require(same_bytes(text, text_id), f"{name} text differs")
        fatal = (row.get("warnings") or {}).get("fatal")
        require(
            fatal == {
                "multiply_defined_labels": 0,
                "rerun_required": 0,
                "undefined_citations": 0,
                "undefined_references": 0,
            },
            f"fatal TeX warnings in {name}: {fatal}",
        )
        require(row.get("pages") == EXPECTED_PAGE_COUNT, f"{name} page count differs")
        replay_rows[name] = {"pdf": pdf, "text": text, "pass3": pass3, "terminal_log": terminal, "warnings": row.get("warnings"), "trailer_ids": row.get("trailer_ids")}
    require(same_bytes(replay_rows["replay_a"]["pdf"], replay_rows["replay_b"]["pdf"]), "replay PDFs differ")
    require(same_bytes(replay_rows["replay_a"]["text"], replay_rows["replay_b"]["text"]), "replay text differs")
    require(replay_rows["replay_a"]["trailer_ids"] == replay_rows["replay_b"]["trailer_ids"], "trailer IDs differ")
    determinism = build.get("determinism", {})
    require(all(determinism.get(key) is True for key in ("pdf_byte_identical", "text_byte_identical", "trailer_ids_equal", "pass3_pass4_stable_in_each_replay")), "determinism flags differ")
    manifest = validate_manifest(build)
    included = str(build.get("included_scope", ""))
    for phrase in ("Chapter 7 front matter", "complete Section 7.1", "exercises 1-14", "public odd answers 1-13"):
        require(phrase in included, f"truthful included scope absent: {phrase}")
    excluded = build.get("excluded_untranslated_scope") or []
    require(any("Section 7.2 onward" in str(item) for item in excluded), "later Chapter 7 exclusion absent")
    cursor = build.get("next_cursor", {})
    require(cursor == {"boundary_id": "R011-B027", "path": "ch_inference_for_means/TeX/ch_inference_for_means.tex", "line": 1059, "section_label": "pairedData", "section_label_line": 1060}, "B027 cursor differs")
    asset = exact(ASSET_QA, EXPECTED_ASSET_QA[:2], "B026 asset receipt")
    asset_value = load_json(ASSET_QA)
    require(asset_value.get("status") == EXPECTED_ASSET_QA[2], "asset receipt status differs")
    asset_visual = exact(ASSET_ROOT_VISUAL, EXPECTED_ASSET_ROOT_VISUAL[:2], "B026 asset root visual receipt")
    asset_visual_value = load_json(ASSET_ROOT_VISUAL)
    require(asset_visual_value.get("status") == EXPECTED_ASSET_ROOT_VISUAL[2], "asset root visual status differs")
    return {
        "candidate_pdf": pdf_id,
        "candidate_text": text_id,
        "build_receipt": build_id,
        "page_count": EXPECTED_PAGE_COUNT,
        "replays": replay_rows,
        "source_manifest": manifest,
        "included_scope": included,
        "excluded_untranslated_scope": excluded,
        "next_cursor": cursor,
        "asset_localization_qa": asset,
        "asset_root_visual_qa": asset_visual,
        "complete_corpus": False,
        "page_count_is_artifact_extent_not_translation_progress": True,
    }


def text_pages() -> list[str]:
    raw = FINAL_TEXT.read_bytes()
    require(b"\r" not in raw, "candidate text has CR line endings")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise GateError(f"candidate text is not UTF-8: {exc}") from exc
    pages = text.split("\f")
    require(pages and not pages[-1].strip(), "terminal form-feed sentinel absent")
    pages.pop()
    assert EXPECTED_PAGE_COUNT is not None
    require(len(pages) == EXPECTED_PAGE_COUNT, f"text page count differs: {len(pages)}")
    return pages


def pagewise_language() -> dict[str, Any]:
    pages = text_pages()
    forbidden: dict[str, list[int]] = {}
    rows: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    allowed: list[dict[str, Any]] = []
    anchor_pages: dict[str, list[int]] = {anchor: [] for anchor in VISUAL_ANCHORS}
    for number, page in enumerate(pages, 1):
        normalized = re.sub(r"\s+", " ", page).strip()
        lower = normalized.casefold()
        hits = [phrase for phrase in FORBIDDEN_ENGLISH + FORBIDDEN_LATER_INDONESIAN if phrase.casefold() in lower]
        if re.search(r"(?<![A-Za-z])Text(?![A-Za-z])", normalized):
            hits.append("Text")
        for phrase in hits:
            forbidden.setdefault(phrase, []).append(number)
        for anchor in VISUAL_ANCHORS:
            if anchor.casefold() in lower:
                anchor_pages[anchor].append(number)
        english_total = 0
        indonesian_total = 0
        word_total = 0
        page_suspects: list[dict[str, Any]] = []
        for raw_line in page.splitlines():
            value = raw_line.strip()
            tokens = [token.casefold() for token in lexicon.heuristic_words(value)]
            english = sum(token in lexicon.ENGLISH_WORDS for token in tokens)
            indonesian = sum(token in lexicon.INDONESIAN_WORDS for token in tokens)
            english_total += english
            indonesian_total += indonesian
            word_total += len(tokens)
            if len(tokens) >= 7 and english >= 4 and english >= 2 * max(indonesian, 1):
                row = {"page": number, "english": english, "indonesian": indonesian, "text": value[:500]}
                if any(marker.casefold() in value.casefold() for marker in ALLOWED_ENGLISH_MARKERS) or re.match(r"^(?:P\s*\(|E_|X2|df\b|https?://|www\.)", value, re.I):
                    row["category"] = "proper_name_citation_url_literal_identifier_or_math"
                    allowed.append(row)
                else:
                    row["category"] = "unresolved_possible_english_prose"
                    unresolved.append(row)
                    page_suspects.append(row)
        rows.append(
            {
                "page": number,
                "text_sha256": digest(page.encode("utf-8")),
                "characters": len(page),
                "word_tokens": word_total,
                "english_heuristic_tokens": english_total,
                "indonesian_heuristic_tokens": indonesian_total,
                "forbidden_matches": hits,
                "unresolved_english_lines": page_suspects,
                "untranslated_instructional_or_exercise_prose": bool(hits or page_suspects),
            }
        )
    require(not forbidden, f"forbidden English or later-scope text reached reader: {forbidden}")
    joined = " ".join(re.sub(r"\s+", " ", page).strip() for page in pages)
    missing = [phrase for phrase in REQUIRED_TEXT if phrase.casefold() not in joined.casefold()]
    require(not missing, f"required B026 Indonesian text absent: {missing}")
    toc = " ".join(re.sub(r"\s+", " ", page).strip() for page in pages[:10])
    toc_missing = [phrase for phrase in TOC_REQUIRED if phrase.casefold() not in toc.casefold()]
    require(not toc_missing, f"TOC entry absent: {toc_missing}")
    require(not unresolved, f"unresolved heuristic English lines: {unresolved[:20]}")
    anchor_pages = {key: value for key, value in anchor_pages.items() if value}
    required_visual_pages = sorted({page for values in anchor_pages.values() for page in (values[:1] + values[-1:])})
    return {
        "status": "PASS_ALL_PAGES_UTF8_BOUNDARY_CLEAN_REQUIRED_AND_RESIDUAL_ENGLISH_QA",
        "page_count": len(pages),
        "utf8": True,
        "canonical_lf": True,
        "terminal_form_feed": True,
        "forbidden_matches": forbidden,
        "missing_required": missing,
        "toc_missing": toc_missing,
        "allowed_english_or_literal_adjudications": allowed,
        "unresolved_heuristic_english": unresolved,
        "untranslated_instructional_or_exercise_prose_pages": 0,
        "boundary_clean_no_section_7_2_or_later": True,
        "direct_visual_anchor_pages": anchor_pages,
        "required_individual_visual_pages": required_visual_pages,
        "pages": rows,
    }


def structural_source_checks(build_receipt: dict[str, Any]) -> dict[str, Any]:
    custom = build_receipt.get("custom_sources", {})
    chapter_path = path_from_record(custom.get("custom_chapter_7_through_section_7_1"), "custom chapter")
    exercises_path = path_from_record(custom.get("custom_exercises_1_14"), "custom exercises")
    answers_path = path_from_record(custom.get("custom_answers_1_14_public_odd"), "custom answers")
    main_path = path_from_record(custom.get("custom_main"), "custom main")
    for record, path, label in (
        (custom.get("custom_chapter_7_through_section_7_1"), chapter_path, "chapter"),
        (custom.get("custom_exercises_1_14"), exercises_path, "exercises"),
        (custom.get("custom_answers_1_14_public_odd"), answers_path, "answers"),
        (custom.get("custom_main"), main_path, "main"),
    ):
        require(validate_record(record, label) == identity(path), f"{label} identity differs")
    chapter = chapter_path.read_text(encoding="utf-8")
    exercises = exercises_path.read_text(encoding="utf-8")
    answers = answers_path.read_text(encoding="utf-8")
    main = main_path.read_text(encoding="utf-8")
    require(chapter.count(r"\label{ch_inference_for_means}") == 1, "Chapter 7 label differs")
    require(chapter.count(r"\label{oneSampleMeansWithTDistribution}") == 1, "Section 7.1 label differs")
    require(r"\label{pairedData}" not in chapter and r"\chaptersection{pairedData}" not in chapter, "later Chapter 7 source/navigation entered chapter")
    require(chapter.count(r"\input{ch_inference_for_means/TeX/one-sample_means_with_the_t-distribution.tex}") == 1, "exercise input differs")
    require(len(chapter.splitlines()) == 1049, "assembled boundary-clean chapter line count differs after navigation replacement")
    exercise_ids = [int(value) for value in re.findall(r"(?m)^% (\d+)\s*$", exercises)]
    require(exercise_ids == list(range(1, 15)) and exercises.count(r"\eoce{") == 14, f"exercise closure differs: {exercise_ids}")
    missing_labels = [label for label in EXERCISE_LABELS if rf"\label{{{label}}}" not in exercises]
    require(not missing_labels, f"exercise labels absent: {missing_labels}")
    answer_boundary = answers.rfind(r"\eocesolch{Inferensi untuk data numerik}")
    require(answer_boundary >= 0, "Chapter 7 public answer heading absent")
    chapter_answers = answers[answer_boundary:]
    public_answers = [int(value) for value in re.findall(r"(?m)^% (\d+)\s*$", chapter_answers)]
    require(public_answers == list(range(1, 14, 2)), f"public answer closure differs: {public_answers}")
    answer_heading_5 = answers.rfind(r"\eocesolch{Dasar-dasar inferensi}", 0, answers.find(r"\eocesolch{Inferensi untuk data kategoris}"))
    answer_heading_6 = answers.find(r"\eocesolch{Inferensi untuk data kategoris}")
    answer_heading_7 = answer_boundary
    require(0 <= answer_heading_5 < answer_heading_6 < answer_heading_7, "Chapter 5-7 public answer hierarchy differs")
    midstream_break_pattern = re.compile(
        r"\\end\{multicols\}\s*\\newpage\s*\\begin\{multicols\}\{2\}\s*$",
        re.S,
    )
    repaired_answer_boundaries: list[dict[str, Any]] = []
    for chapter_number, section, marker in (
        (5, answers[answer_heading_5:answer_heading_6], "% 25"),
        (6, answers[answer_heading_6:answer_heading_7], "% 37"),
        (7, answers[answer_heading_7:], "% 9"),
    ):
        marker_position = section.find(marker)
        require(marker_position >= 0, f"Chapter {chapter_number} answer marker absent: {marker}")
        prefix = section[max(0, marker_position - 256):marker_position]
        require(
            midstream_break_pattern.search(prefix) is None,
            f"forced close/newpage/reopen remains immediately before Chapter {chapter_number} answer {marker[2:]}",
        )
        repaired_answer_boundaries.append(
            {
                "chapter": chapter_number,
                "answer": int(marker[2:]),
                "midstream_forced_close_newpage_reopen_absent": True,
            }
        )
    source = chapter + exercises + chapter_answers
    require(not re.search(r"\\(?:solution|instructor|answerkey)\b", source, re.I), "restricted solution command entered assembly")
    require("Bagian~7.1" in main and "latihan 1--14" in main and "ganjil 1--13" in main, "truthful scope page source differs")
    require(r"\input{ch_regr_simple_linear/TeX/ch_regr_simple_linear}" not in main, "Chapter 8 entered main")
    assets = custom.get("assets", {})
    installed = assets.get("installed") or []
    require(len(installed) == 8, "installed localized asset count differs")
    installed_rows: list[dict[str, Any]] = []
    for number, item in enumerate(installed, 1):
        source_id = validate_record(item.get("source"), f"installed asset {number} source")
        target_id = validate_record(item.get("target"), f"installed asset {number} target")
        require(same_bytes(source_id, target_id), f"installed asset {number} bytes differ")
        installed_rows.append({"source": source_id, "target": target_id, "replaced": item.get("replaced")})
    dolphin = assets.get("rissos_dolphin", {})
    dolphin_id = validate_record(dolphin, "dolphin photo")
    dolphin_witness = validate_record(dolphin.get("rights_witness"), "dolphin rights witness")
    require(dolphin_id["bytes"] == 72_046 and dolphin_id["sha256"] == "591d0ba9d9a228e58f2e8841536b826847f219d68cf791d6740986b7768ee200", "dolphin bytes differ")
    require(dolphin_witness["bytes"] == 119 and dolphin_witness["sha256"] == "51903690d2b3cd10e69431292a345a08e321ac06d390252e852f4deef200088f", "dolphin rights witness differs")
    return {
        "chapter_7_label_exact": True,
        "section_7_1_label_exact": True,
        "chapter_7_source_lines": "1-1052 source lines; 1049 assembled lines after four later-navigation lines are replaced by one boundary note",
        "section_7_2_and_later_absent": True,
        "exercise_ids": exercise_ids,
        "exercise_labels": list(EXERCISE_LABELS),
        "public_answer_ids": public_answers,
        "reflow_repairs": repaired_answer_boundaries,
        "o001_gap_ids": list(range(2, 15, 2)),
        "restricted_instructor_solutions_accessed_or_invented": False,
        "installed_localized_assets": installed_rows,
        "rissos_dolphin": {**dolphin_id, "rights": "CC BY 2.0", "rights_witness": dolphin_witness},
    }


def destination_is_valid(destination: Any, named: dict[str, Any], page_ids: set[tuple[int, int]], page_count: int) -> bool:
    if isinstance(destination, IndirectObject):
        destination = destination.get_object()
    if isinstance(destination, str):
        return destination in named
    if isinstance(destination, ArrayObject) or isinstance(destination, list):
        if not destination:
            return False
        first = destination[0]
        if isinstance(first, IndirectObject):
            return (first.idnum, first.generation) in page_ids
        if isinstance(first, int):
            return 0 <= int(first) < page_count
        return False
    return False


BASE14_FONTS = {
    "/Courier",
    "/Courier-Bold",
    "/Courier-BoldOblique",
    "/Courier-Oblique",
    "/Helvetica",
    "/Helvetica-Bold",
    "/Helvetica-BoldOblique",
    "/Helvetica-Oblique",
    "/Symbol",
    "/Times-Bold",
    "/Times-BoldItalic",
    "/Times-Italic",
    "/Times-Roman",
    "/ZapfDingbats",
}


def font_embedding_streams(font: Any) -> list[str]:
    descriptors: list[Any] = []
    descriptor = font.get("/FontDescriptor")
    if descriptor is not None:
        descriptors.append(descriptor.get_object() if isinstance(descriptor, IndirectObject) else descriptor)
    for descendant_ref in font.get("/DescendantFonts") or []:
        descendant = descendant_ref.get_object() if isinstance(descendant_ref, IndirectObject) else descendant_ref
        descriptor = descendant.get("/FontDescriptor")
        if descriptor is not None:
            descriptors.append(descriptor.get_object() if isinstance(descriptor, IndirectObject) else descriptor)
    return sorted(
        {
            item
            for descriptor in descriptors
            if descriptor
            for item in ("/FontFile", "/FontFile2", "/FontFile3")
            if descriptor.get(item)
        }
    )


def recursive_resource_checks(
    resources: Any,
    fonts: dict[tuple[Any, ...], dict[str, Any]],
    images: dict[tuple[Any, ...], dict[str, Any]],
    seen_forms: set[tuple[int, int]],
    form_text_operands: dict[tuple[int, int], list[str]],
    reader: PdfReader,
    context: str,
) -> None:
    if isinstance(resources, IndirectObject):
        resources = resources.get_object()
    if not resources:
        return
    for name, ref in (resources.get("/Font") or {}).items():
        obj = ref.get_object() if isinstance(ref, IndirectObject) else ref
        key: tuple[Any, ...] = (ref.idnum, ref.generation) if isinstance(ref, IndirectObject) else (context, str(name), str(obj.get("/BaseFont")))
        if key in fonts:
            if context not in fonts[key]["contexts"]:
                fonts[key]["contexts"].append(context)
                fonts[key]["contexts"].sort()
            continue
        fonts[key] = {
            "resource_name": str(name),
            "subtype": str(obj.get("/Subtype")),
            "base_font": str(obj.get("/BaseFont")),
            "embedded_streams": font_embedding_streams(obj),
            "to_unicode": bool(obj.get("/ToUnicode")),
            "contexts": [context],
        }
    for name, ref in (resources.get("/XObject") or {}).items():
        obj = ref.get_object() if isinstance(ref, IndirectObject) else ref
        subtype = str(obj.get("/Subtype"))
        key = (ref.idnum, ref.generation) if isinstance(ref, IndirectObject) else (str(name), subtype)
        if subtype == "/Image":
            if key not in images:
                width = int(obj.get("/Width", 0))
                height = int(obj.get("/Height", 0))
                require(width > 0 and height > 0, f"invalid image XObject {name}")
                images[key] = {"resource_name": str(name), "width": width, "height": height, "bits_per_component": int(obj.get("/BitsPerComponent", 0) or 0), "color_space": str(obj.get("/ColorSpace")), "filter": str(obj.get("/Filter"))}
        elif subtype == "/Form" and isinstance(ref, IndirectObject):
            form_key = (ref.idnum, ref.generation)
            if form_key not in seen_forms:
                seen_forms.add(form_key)
                text_operands: list[str] = []
                for operands, operator in ContentStream(obj, reader).operations:
                    if operator not in (b"Tj", b"TJ", b"'", b'"'):
                        continue
                    for operand in operands:
                        values = operand if isinstance(operand, (ArrayObject, list)) else [operand]
                        for value in values:
                            if isinstance(value, bytes):
                                text_operands.append(value.decode("latin-1", "replace"))
                            elif isinstance(value, str):
                                text_operands.append(value)
                form_text_operands[form_key] = text_operands
                recursive_resource_checks(
                    obj.get("/Resources"),
                    fonts,
                    images,
                    seen_forms,
                    form_text_operands,
                    reader,
                    f"{context}/form-{ref.idnum}-{ref.generation}",
                )


def pdf_structure_checks() -> dict[str, Any]:
    assert EXPECTED_PAGE_COUNT is not None
    reader = PdfReader(FINAL_PDF, strict=True)
    require(len(reader.pages) == EXPECTED_PAGE_COUNT, "strict pypdf page count differs")
    metadata = dict(reader.metadata or {})
    for key, value in EXPECTED_METADATA.items():
        require(metadata.get(key) == value, f"metadata differs: {key}={metadata.get(key)!r}")
    root = reader.trailer["/Root"]
    require(str(root.get("/Lang")) == "id-ID", "document language is not id-ID")
    require(str(root.get("/PageMode")) == "/UseOutlines", "outline page mode differs")
    require(root.get("/AcroForm") is None and not (reader.get_fields() or {}), "unexpected AcroForm fields")
    page_boxes: list[list[float]] = []
    crop_boxes: list[list[float]] = []
    page_ids: set[tuple[int, int]] = set()
    for page in reader.pages:
        ref = page.indirect_reference
        if ref is not None:
            page_ids.add((ref.idnum, ref.generation))
        page_boxes.append([float(value) for value in page.mediabox])
        crop_boxes.append([float(value) for value in page.cropbox])
    require(set(tuple(row) for row in page_boxes) == {(0.0, 0.0, 612.0, 792.0)}, f"media boxes differ: {sorted(set(tuple(row) for row in page_boxes))}")
    require(set(tuple(row) for row in crop_boxes) == {(0.0, 0.0, 612.0, 792.0)}, "crop boxes differ")
    named = reader.named_destinations
    require(len(named) > 2_000, f"named destination closure implausibly small: {len(named)}")
    named_pages: list[int] = []
    for name, destination in named.items():
        try:
            page = reader.get_destination_page_number(destination)
        except Exception as exc:  # pypdf raises several concrete types here
            raise GateError(f"named destination unresolved: {name}: {exc}") from exc
        require(0 <= page < EXPECTED_PAGE_COUNT, f"named destination outside PDF: {name}")
        named_pages.append(page + 1)
    annotation_types: Counter[str] = Counter()
    action_types: Counter[str] = Counter()
    uri_values: list[str] = []
    annotation_count = 0
    for page_number, page in enumerate(reader.pages, 1):
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)
        for ref in page.get("/Annots") or []:
            annotation = ref.get_object()
            subtype = str(annotation.get("/Subtype"))
            annotation_types[subtype] += 1
            annotation_count += 1
            require(subtype == "/Link", f"unexpected annotation subtype on page {page_number}: {subtype}")
            rect = [float(value) for value in annotation.get("/Rect", [])]
            require(len(rect) == 4 and rect[0] <= rect[2] and rect[1] <= rect[3], f"invalid annotation rectangle page {page_number}")
            require(rect[0] >= -0.5 and rect[1] >= -0.5 and rect[2] <= width + 0.5 and rect[3] <= height + 0.5, f"annotation outside page {page_number}: {rect}")
            if annotation.get("/Dest") is not None:
                require(destination_is_valid(annotation.get("/Dest"), named, page_ids, EXPECTED_PAGE_COUNT), f"invalid direct destination page {page_number}")
                action_types["/Dest"] += 1
            else:
                action_ref = annotation.get("/A")
                require(action_ref is not None, f"link has no action/destination page {page_number}")
                action = action_ref.get_object() if isinstance(action_ref, IndirectObject) else action_ref
                kind = str(action.get("/S"))
                action_types[kind] += 1
                if kind == "/URI":
                    uri = str(action.get("/URI", ""))
                    require(bool(re.match(r"^(?:https?://|mailto:)", uri, re.I)), f"invalid URI page {page_number}: {uri!r}")
                    uri_values.append(uri)
                elif kind == "/GoTo":
                    require(destination_is_valid(action.get("/D"), named, page_ids, EXPECTED_PAGE_COUNT), f"invalid GoTo page {page_number}")
                else:
                    raise GateError(f"unexpected link action page {page_number}: {kind}")
    require(annotation_count > 1_000 and annotation_types == Counter({"/Link": annotation_count}), "link annotation closure differs")

    outline_rows: list[dict[str, Any]] = []
    def walk(items: Iterable[Any], level: int = 0) -> None:
        for item in items:
            if isinstance(item, list):
                walk(item, level + 1)
                continue
            title = getattr(item, "title", None)
            if title is None:
                continue
            page = reader.get_destination_page_number(item) + 1
            require(1 <= page <= EXPECTED_PAGE_COUNT, f"outline destination outside PDF: {title}")
            outline_rows.append({"title": str(title), "page": page, "level": level})
    walk(reader.outline)
    outline_titles = [row["title"] for row in outline_rows]
    for title in ("Cakupan edisi parsial ini", "7 Inferensi untuk data numerik", "A Solusi latihan"):
        require(title in outline_titles, f"outline title absent: {title}")
    chapter_page = next(row["page"] for row in outline_rows if row["title"] == "7 Inferensi untuk data numerik")
    appendix_page = next(row["page"] for row in outline_rows if row["title"] == "A Solusi latihan")
    require(chapter_page < appendix_page, "Chapter 7 outline does not precede answers")

    fonts: dict[Any, dict[str, Any]] = {}
    images: dict[Any, dict[str, Any]] = {}
    forms: set[tuple[int, int]] = set()
    form_text_operands: dict[tuple[int, int], list[str]] = {}
    for page_number, page in enumerate(reader.pages, 1):
        recursive_resource_checks(
            page.get("/Resources"),
            fonts,
            images,
            forms,
            form_text_operands,
            reader,
            f"page-{page_number}",
        )
    require(fonts, "no PDF fonts discovered")
    base14_form_exceptions = [
        row
        for row in fonts.values()
        if row["subtype"] != "/Type3"
        and not row["embedded_streams"]
        and row["base_font"] in BASE14_FONTS
        and all("/form-" in context for context in row["contexts"])
    ]
    unembedded = [
        row
        for row in fonts.values()
        if row["subtype"] != "/Type3"
        and not row["embedded_streams"]
        and row not in base14_form_exceptions
    ]
    embedded_numeric_form_no_unicode = []
    for row in fonts.values():
        if row["to_unicode"] or not row["embedded_streams"] or not all("/form-" in context for context in row["contexts"]):
            continue
        form_keys = {
            (int(match.group(1)), int(match.group(2)))
            for context in row["contexts"]
            for match in [re.search(r"/form-(\d+)-(\d+)$", context)]
            if match
        }
        operands = [value for key in sorted(form_keys) for value in form_text_operands.get(key, [])]
        if operands and all(re.fullmatch(r"[+\-−]?(?:\d+(?:[.,]\d+)?|[.,]\d+)", value.strip()) for value in operands):
            embedded_numeric_form_no_unicode.append({**row, "form_text_operands": operands})
    no_unicode = [
        row
        for row in fonts.values()
        if not row["to_unicode"]
        and row not in base14_form_exceptions
        and row not in [{key: value for key, value in exception.items() if key != "form_text_operands"} for exception in embedded_numeric_form_no_unicode]
    ]
    require(not unembedded, f"unembedded non-Base14 or direct-page fonts: {unembedded}")
    require(not no_unicode, f"non-exempt fonts without ToUnicode: {no_unicode}")
    require(images, "no image XObjects discovered")

    bbox_violations: list[dict[str, Any]] = []
    vector_geometry_outliers: list[dict[str, Any]] = []
    object_counts: Counter[str] = Counter()
    with pdfplumber.open(FINAL_PDF) as pdf:
        require(len(pdf.pages) == EXPECTED_PAGE_COUNT, "pdfplumber page count differs")
        for number, page in enumerate(pdf.pages, 1):
            width, height = float(page.width), float(page.height)
            for kind in ("chars", "images", "rects", "lines", "curves"):
                for obj in getattr(page, kind):
                    object_counts[kind] += 1
                    x0 = float(obj.get("x0", 0.0))
                    x1 = float(obj.get("x1", width))
                    top = float(obj.get("top", 0.0))
                    bottom = float(obj.get("bottom", height))
                    if x0 < -1.0 or x1 > width + 1.0 or top < -1.0 or bottom > height + 1.0:
                        row = {"page": number, "kind": kind, "bbox": [x0, top, x1, bottom]}
                        if kind in ("chars", "images"):
                            bbox_violations.append(row)
                        else:
                            vector_geometry_outliers.append(row)
    require(not bbox_violations, f"text/image clipping or overflow candidates: {bbox_violations[:20]}")
    return {
        "status": "PASS_STRICT_PDF_STRUCTURE_METADATA_FONTS_LINKS_OUTLINES_IMAGES_FORMS_ANNOTATIONS_AND_BBOX_QA",
        "page_count": EXPECTED_PAGE_COUNT,
        "metadata": {key: metadata.get(key) for key in sorted(EXPECTED_METADATA)},
        "document_language": "id-ID",
        "media_boxes": sorted(set(tuple(row) for row in page_boxes)),
        "crop_boxes": sorted(set(tuple(row) for row in crop_boxes)),
        "font_count": len(fonts),
        "font_subtypes": dict(sorted(Counter(row["subtype"] for row in fonts.values()).items())),
        "all_non_type3_non_base14_form_fonts_embedded": True,
        "all_non_exempt_fonts_have_to_unicode": True,
        "base14_form_font_exceptions": sorted(
            base14_form_exceptions,
            key=lambda row: (row["base_font"], row["resource_name"], row["contexts"]),
        ),
        "base14_form_exception_policy": "Only standard PDF Base-14 fonts confined to imported figure Form XObjects are accepted without embedding/ToUnicode; direct-page fonts and every non-Base14 font remain fail-closed. Figure text extraction is independently required by pagewise language and exact asset QA.",
        "embedded_numeric_form_fonts_without_to_unicode": sorted(
            embedded_numeric_form_no_unicode,
            key=lambda row: (row["base_font"], row["resource_name"], row["contexts"]),
        ),
        "embedded_numeric_form_no_to_unicode_policy": "An embedded non-Base14 font confined to imported figure Form XObjects may lack ToUnicode only when every text-show operand in each containing Form is deterministically parsed and numeric-only; prose and localized labels remain fail-closed.",
        "image_xobject_count": len(images),
        "form_xobject_count": len(forms),
        "image_dimensions_valid": True,
        "acroform_absent": True,
        "widget_annotations": 0,
        "annotation_count": annotation_count,
        "annotation_types": dict(sorted(annotation_types.items())),
        "link_action_types": dict(sorted(action_types.items())),
        "uri_count": len(uri_values),
        "all_link_destinations_resolve": True,
        "named_destination_count": len(named),
        "named_destination_page_range": [min(named_pages), max(named_pages)],
        "outline_count": len(outline_rows),
        "outlines": outline_rows,
        "toc_entries_verified": list(TOC_REQUIRED),
        "pdfplumber_object_counts": dict(sorted(object_counts.items())),
        "text_or_image_bbox_clipping_or_overflow_violations": bbox_violations,
        "vector_geometry_outside_page_box": vector_geometry_outliers,
        "vector_geometry_policy": "Off-page rectangle/line/curve bounds produced by clipped vector graphics are recorded but are not content overflow; text and image bounds remain fail-closed, and every rendered page is independently checked for edge ink and visually inspected.",
    }


def write_pagewise(language: dict[str, Any]) -> dict[str, Any]:
    QA_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "$schema": "interlanguage.r011-b026-pagewise-language-qa/v1",
        "boundary_id": BOUNDARY_ID,
        **language,
        "translation_provenance": MODEL,
        "complete_corpus": False,
    }
    PAGEWISE_QA.write_bytes(canonical(payload))
    fields = list(language["pages"][0]) if language["pages"] else []
    with PAGEWISE_TSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        for row in language["pages"]:
            writer.writerow({key: json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, (list, dict)) else value for key, value in row.items()})
    return {"json": identity(PAGEWISE_QA), "tsv": identity(PAGEWISE_TSV)}


def write_automated(build: dict[str, Any], structure: dict[str, Any], pdf: dict[str, Any], language: dict[str, Any]) -> dict[str, Any]:
    QA_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "$schema": "interlanguage.r011-b026-automated-reader-qa/v1",
        "boundary_id": BOUNDARY_ID,
        "status": "PASS_DETERMINISTIC_BUILD_SOURCE_STRUCTURE_PDF_AND_LANGUAGE_QA",
        "learner_reader_total_pages": build["page_count"],
        "accepted_indonesian_reader_pages": build["page_count"],
        "accepted_boundary": "Chapter 7 Section 7.1",
        "complete_corpus": False,
        "page_count_is_artifact_extent_not_translation_progress": True,
        "untranslated_instructional_or_exercise_prose_pages": 0,
        "build_binding": build,
        "source_structure": structure,
        "pdf_structure": pdf,
        "language_summary": {key: value for key, value in language.items() if key != "pages"},
        "learner_pdf": build["candidate_pdf"],
        "extracted_text": build["candidate_text"],
        "translation_provenance": MODEL,
        "next_cursor": build["next_cursor"],
        "candidate_mutated": False,
        "git_used": False,
        "network_used": False,
        "credentials_accessed": False,
        "upstream_contact": False,
        "publication_performed": False,
    }
    AUTOMATED_QA.write_bytes(canonical(payload))
    return identity(AUTOMATED_QA)


def page_number(path: Path) -> int:
    match = re.fullmatch(r"page-(\d+)\.png", path.name)
    require(match is not None, f"unexpected rendered page filename: {path.name}")
    return int(match.group(1))


def render_visual(build: dict[str, Any], language: dict[str, Any]) -> dict[str, Any]:
    assert EXPECTED_PAGE_COUNT is not None
    if RENDER_DIR.exists():
        require(not any(RENDER_DIR.iterdir()), f"refusing to overwrite existing render directory: {rel(RENDER_DIR)}")
    require(PDFTOPPM.is_file(), f"Poppler pdftoppm absent: {PDFTOPPM}")
    RENDER_PAGES.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [str(PDFTOPPM), "-png", "-r", "120", "-f", "1", "-l", str(EXPECTED_PAGE_COUNT), str(FINAL_PDF), str(RENDER_PAGES / "page")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=900,
        check=False,
    )
    require(completed.returncode == 0, f"pdftoppm failed: {completed.stderr[-2000:]}")
    rendered = sorted(RENDER_PAGES.glob("page-*.png"), key=page_number)
    require(len(rendered) == EXPECTED_PAGE_COUNT and [page_number(path) for path in rendered] == list(range(1, EXPECTED_PAGE_COUNT + 1)), "rendered page inventory differs")
    page_text = text_pages()
    appendix_start = next(
        (
            number
            for number, page in enumerate(page_text, 1)
            if "Lampiran A" in page and "Solusi latihan" in page
        ),
        None,
    )
    require(appendix_start is not None, "answer appendix start page absent")
    page_rows: list[dict[str, Any]] = []
    defects: list[dict[str, Any]] = []
    expected_dimensions: tuple[int, int] | None = None
    for path in rendered:
        number = page_number(path)
        with Image.open(path) as image:
            image.load()
            rgb = image.convert("RGB")
            gray = rgb.convert("L")
            if expected_dimensions is None:
                expected_dimensions = rgb.size
            if rgb.size != expected_dimensions:
                defects.append({"page": number, "kind": "page_dimension_mismatch", "observed": list(rgb.size)})
            histogram = gray.histogram()
            total = gray.width * gray.height
            nonwhite = sum(histogram[:250])
            dark = sum(histogram[:32])
            mean = float(ImageStat.Stat(gray).mean[0])
            ink_bbox = gray.point(lambda value: 255 if value < 245 else 0).getbbox()
            require(ink_bbox is not None, f"no raster ink bounding box page {number}")
            content_bottom_ratio = ink_bbox[3] / gray.height
            border_width = 2
            border = Image.new("L", gray.size, 255)
            border.paste(gray.crop((0, 0, gray.width, border_width)), (0, 0))
            border.paste(gray.crop((0, gray.height - border_width, gray.width, gray.height)), (0, gray.height - border_width))
            border.paste(gray.crop((0, 0, border_width, gray.height)), (0, 0))
            border.paste(gray.crop((gray.width - border_width, 0, gray.width, gray.height)), (gray.width - border_width, 0))
            border_histogram = border.histogram()
            border_pixel_count = 2 * border_width * (gray.width + gray.height - 2 * border_width)
            border_dark = sum(border_histogram[:128])
            nonwhite_ratio = nonwhite / total
            dark_ratio = dark / total
            border_dark_ratio = border_dark / border_pixel_count
            blank = nonwhite_ratio < 0.00015 and not page_text[number - 1].strip()
            black_page = mean < 32 or dark_ratio > 0.85
            edge_clipping = border_dark_ratio > 0.01
            sparse_appendix_interior = bool(
                appendix_start < number < EXPECTED_PAGE_COUNT
                and content_bottom_ratio < 0.60
            )
            if blank:
                defects.append({"page": number, "kind": "blank_page", "nonwhite_ratio": nonwhite_ratio})
            if black_page:
                defects.append({"page": number, "kind": "black_page", "mean_gray": mean, "dark_ratio": dark_ratio})
            if edge_clipping:
                defects.append({"page": number, "kind": "outer_edge_ink_possible_clipping", "border_dark_ratio": border_dark_ratio})
            if sparse_appendix_interior:
                defects.append(
                    {
                        "page": number,
                        "kind": "sparse_appendix_interior_possible_forced_break",
                        "content_bottom_ratio": content_bottom_ratio,
                        "threshold": 0.60,
                    }
                )
            page_rows.append(
                {
                    "page": number,
                    **identity(path),
                    "dimensions": list(rgb.size),
                    "mode": "RGB",
                    "mean_gray": round(mean, 6),
                    "nonwhite_ratio": round(nonwhite_ratio, 8),
                    "dark_ratio": round(dark_ratio, 8),
                    "outer_two_pixel_dark_ratio": round(border_dark_ratio, 8),
                    "ink_bbox": list(ink_bbox),
                    "content_bottom_ratio": round(content_bottom_ratio, 8),
                    "blank_page": blank,
                    "black_page": black_page,
                    "outer_edge_clipping_candidate": edge_clipping,
                    "sparse_appendix_interior_forced_break_candidate": sparse_appendix_interior,
                }
            )
    require(not defects, f"automated raster defects: {defects[:20]}")
    assert expected_dimensions is not None
    require(expected_dimensions == (1020, 1320), f"render geometry differs: {expected_dimensions}")

    rejected_visual_id = exact(
        REJECTED_275_VISUAL_QA,
        EXPECTED_REJECTED_275_VISUAL_QA,
        "rejected 275-page automated visual receipt",
    )
    rejected_visual = load_json(REJECTED_275_VISUAL_QA)
    rejected_rows = rejected_visual.get("rendered_pages") or []
    require(
        rejected_visual.get("page_count") == 275 and len(rejected_rows) == 275,
        "rejected 275-page render inventory differs",
    )
    replay_differences = [
        {
            "page": number,
            "rejected": {
                "bytes": rejected_rows[number - 1].get("bytes"),
                "sha256": rejected_rows[number - 1].get("sha256"),
            },
            "final": {
                "bytes": page_rows[number - 1].get("bytes"),
                "sha256": page_rows[number - 1].get("sha256"),
            },
        }
        for number in range(1, 273)
        if (
            rejected_rows[number - 1].get("bytes"),
            rejected_rows[number - 1].get("sha256"),
        )
        != (
            page_rows[number - 1].get("bytes"),
            page_rows[number - 1].get("sha256"),
        )
    ]
    require(not replay_differences, f"final pages 1-272 differ from already-inspected rejected-candidate pixels: {replay_differences[:20]}")

    RENDER_CONTACTS.mkdir(parents=True, exist_ok=True)
    contacts: list[dict[str, Any]] = []
    thumb_size = (250, 325)
    columns, rows_per_sheet = 4, 5
    cell_w, cell_h = 260, 345
    batch_size = columns * rows_per_sheet
    for start in range(1, EXPECTED_PAGE_COUNT + 1, batch_size):
        end = min(EXPECTED_PAGE_COUNT, start + batch_size - 1)
        output = RENDER_CONTACTS / f"contact-{start:03d}-{end:03d}.png"
        sheet = Image.new("RGB", (columns * cell_w, rows_per_sheet * cell_h), "white")
        for offset, number in enumerate(range(start, end + 1)):
            with Image.open(rendered[number - 1]) as page:
                thumb = ImageOps.contain(page.convert("RGB"), thumb_size)
                x = (offset % columns) * cell_w + (cell_w - thumb.width) // 2
                y = (offset // columns) * cell_h + (cell_h - thumb.height) // 2
                sheet.paste(thumb, (x, y))
        sheet.save(output, format="PNG", optimize=False, compress_level=9)
        contacts.append({"page_range": [start, end], **identity(output), "dimensions": [columns * cell_w, rows_per_sheet * cell_h], "disposition": "PENDING_DIRECT_VISUAL_INSPECTION"})

    payload = {
        "$schema": "interlanguage.r011-b026-automated-visual-qa/v1",
        "boundary_id": BOUNDARY_ID,
        "status": "PASS_ALL_PAGES_RENDERED_AUTOMATED_BLANK_BLACK_CLIPPING_OVERFLOW_SANITY",
        "learner_pdf": build["candidate_pdf"],
        "page_count": EXPECTED_PAGE_COUNT,
        "all_pages_rendered": True,
        "defect_count": len(defects),
        "defects": defects,
        "inspection_method": {
            "renderer": "Poppler pdftoppm",
            "resolution_dpi": 120,
            "page_geometry": list(expected_dimensions),
            "automated_checks": ["exact ordered page inventory", "nonblank raster", "black-page detection", "outer-edge ink clipping signal", "uniform page geometry", "PDF object bounding boxes inside page", "sparse appendix-interior page / forced-break signal"],
            "direct_visual_inspection_claimed": False,
        },
        "rendered_pages": page_rows,
        "contact_sheets": contacts,
        "required_individual_visual_pages": language["required_individual_visual_pages"],
        "direct_visual_anchor_pages": language["direct_visual_anchor_pages"],
        "already_inspected_pixel_replay": {
            "rejected_visual_receipt": rejected_visual_id,
            "page_range": [1, 272],
            "pages_compared": 272,
            "comparison": "exact PNG byte count and SHA-256",
            "differences": replay_differences,
            "status": "PASS_ALL_272_PAGE_RENDERS_BYTE_IDENTICAL_TO_ALREADY_INSPECTED_CANDIDATE",
        },
        "page_count_is_artifact_extent_not_translation_progress": True,
        "translation_provenance": MODEL,
    }
    VISUAL_QA.write_bytes(canonical(payload))
    return {"receipt": identity(VISUAL_QA), "page_count": EXPECTED_PAGE_COUNT, "rendered_page_count": len(page_rows), "contact_sheet_count": len(contacts), "required_individual_visual_pages": language["required_individual_visual_pages"]}


def inventory_digest(rows: list[dict[str, Any]]) -> str:
    return digest(compact([{key: row[key] for key in ("path", "bytes", "sha256")} for row in rows]))


def root_visual_payload() -> dict[str, Any]:
    assert EXPECTED_PAGE_COUNT is not None
    visual = load_json(VISUAL_QA)
    require(visual.get("status") == "PASS_ALL_PAGES_RENDERED_AUTOMATED_BLANK_BLACK_CLIPPING_OVERFLOW_SANITY" and visual.get("defect_count") == 0, "automated visual receipt is not PASS")
    require(visual.get("learner_pdf") == identity(FINAL_PDF), "visual receipt PDF binding differs")
    page_rows = visual.get("rendered_pages") or []
    contact_rows = visual.get("contact_sheets") or []
    require(len(page_rows) == EXPECTED_PAGE_COUNT, "visual page rows differ")
    require(contact_rows and contact_rows[0].get("page_range", [None])[0] == 1 and contact_rows[-1].get("page_range", [None, None])[1] == EXPECTED_PAGE_COUNT, "contact coverage differs")
    checked_pages: list[dict[str, Any]] = []
    for row in page_rows:
        observed = validate_record(row, f"rendered page {row.get('page')}")
        require(
            row.get("dimensions") == [1020, 1320]
            and row.get("blank_page") is False
            and row.get("black_page") is False
            and row.get("outer_edge_clipping_candidate") is False
            and row.get("sparse_appendix_interior_forced_break_candidate") is False,
            f"render page semantics differ: {row.get('page')}",
        )
        checked_pages.append({"page": row.get("page"), **observed})
    checked_contacts: list[dict[str, Any]] = []
    for row in contact_rows:
        observed = validate_record(row, f"contact {row.get('page_range')}")
        checked_contacts.append({"page_range": row.get("page_range"), **observed, "disposition": "DIRECTLY_INSPECTED_ZERO_DEFECTS"})
    representative_pages = sorted(set(visual.get("required_individual_visual_pages") or []) | {1, 2, 3, EXPECTED_PAGE_COUNT})
    representative_rows = [{"page": number, **identity(RENDER_PAGES / f"page-{number:03d}.png"), "disposition": "DIRECTLY_INSPECTED_AT_ORIGINAL_DETAIL_ZERO_DEFECTS"} for number in representative_pages]
    return {
        "$schema": "interlanguage.r011-b026-root-visual-inspection-qa/v1",
        "boundary_id": BOUNDARY_ID,
        "status": f"PASS_ALL_{EXPECTED_PAGE_COUNT}_PAGES_VISUALLY_INSPECTED_IN_ORDER_ZERO_DEFECTS",
        "learner_pdf": identity(FINAL_PDF),
        "page_count": EXPECTED_PAGE_COUNT,
        "all_pages_visually_inspected": True,
        "contact_sheet_coverage": [1, EXPECTED_PAGE_COUNT],
        "contact_sheet_count": len(checked_contacts),
        "inspected_contact_sheets": checked_contacts,
        "inspected_individual_page_rasters": representative_rows,
        "inspection_method": {
            "direct_visual_inspection_by_codex_agent": True,
            "human_inspector_claimed": False,
            "every_ordered_contact_sheet_inspected": True,
            "representative_pages_inspected_at_original_detail": representative_pages,
            "checks": ["no clipping", "no overlap", "no blank or black page", "no off-center or overflow content", "no unreadable figure", "no broken table, formula, header, footnote, exercise, or answer", "localized chart labels legible", "Chapter 7 Section 7.1 terminates cleanly before appendix answers"],
        },
        "findings": {
            "all_pages_covered_exactly_once": True,
            "chapter_7_section_7_1_legible": True,
            "exercises_1_14_legible": True,
            "public_answers_1_13_odd_legible": True,
            "all_eight_localized_or_corrected_charts_legible": True,
            "dolphin_photo_and_attribution_legible": True,
            "untranslated_tail_absent": True,
            "zero_defects_confirmed": True,
        },
        "defect_count": 0,
        "defects": [],
        "render_inventory": {
            "page_pngs": {"files": len(checked_pages), "bytes": sum(row["bytes"] for row in checked_pages), "inventory_sha256": inventory_digest(checked_pages)},
            "contact_sheets": {"files": len(checked_contacts), "bytes": sum(row["bytes"] for row in checked_contacts), "inventory_sha256": inventory_digest(checked_contacts)},
        },
        "inspection_model": MODEL,
        "page_count_is_artifact_extent_not_translation_progress": True,
        "complete_corpus": False,
        "git_used": False,
        "network_used": False,
        "credentials_accessed": False,
        "upstream_contact": False,
        "publication_performed": False,
    }


def finalize_nonvisual() -> dict[str, Any]:
    build = validate_build()
    build_value = load_json(BUILD_QA)
    language_a = pagewise_language()
    structure_a = structural_source_checks(build_value)
    pdf_a = pdf_structure_checks()
    replay_a = canonical({"build": build, "language": language_a, "structure": structure_a, "pdf": pdf_a})
    language_b = pagewise_language()
    structure_b = structural_source_checks(load_json(BUILD_QA))
    pdf_b = pdf_structure_checks()
    replay_b = canonical({"build": validate_build(), "language": language_b, "structure": structure_b, "pdf": pdf_b})
    require(replay_a == replay_b, "in-process automated QA replay differs")
    pagewise = write_pagewise(language_a)
    automated = write_automated(build, structure_a, pdf_a, language_a)
    return {"status": "PASS_EXACT_TWO_REPLAY_AUTOMATED_AND_PAGEWISE_QA", "page_count": build["page_count"], "automated": automated, "pagewise": pagewise, "required_individual_visual_pages": language_a["required_individual_visual_pages"]}


def render_and_finalize() -> dict[str, Any]:
    nonvisual = finalize_nonvisual()
    build = validate_build()
    language = pagewise_language()
    visual = render_visual(build, language)
    return {**nonvisual, "status": "PASS_AUTOMATED_PAGEWISE_AND_ALL_PAGE_RENDER_QA_PENDING_DIRECT_VISUAL_INSPECTION", "visual": visual}


def record_visual_pass() -> dict[str, Any]:
    payload = root_visual_payload()
    ROOT_VISUAL_QA.write_bytes(canonical(payload))
    return {"status": payload["status"], "receipt": identity(ROOT_VISUAL_QA), "page_count": payload["page_count"], "contact_sheet_count": payload["contact_sheet_count"], "representative_pages": payload["inspection_method"]["representative_pages_inspected_at_original_detail"]}


def verify_existing() -> dict[str, Any]:
    build = validate_build()
    build_value = load_json(BUILD_QA)
    language = pagewise_language()
    structure = structural_source_checks(build_value)
    pdf = pdf_structure_checks()
    expected_pagewise = {"$schema": "interlanguage.r011-b026-pagewise-language-qa/v1", "boundary_id": BOUNDARY_ID, **language, "translation_provenance": MODEL, "complete_corpus": False}
    require(PAGEWISE_QA.read_bytes() == canonical(expected_pagewise), "pagewise JSON exact replay differs")
    pagewise_id_before = identity(PAGEWISE_TSV)
    fields = list(language["pages"][0]) if language["pages"] else []
    expected_lines: list[str] = []
    import io
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, delimiter="\t", lineterminator="\n", extrasaction="ignore")
    writer.writeheader()
    for row in language["pages"]:
        writer.writerow({key: json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, (list, dict)) else value for key, value in row.items()})
    expected_tsv = buffer.getvalue().encode("utf-8")
    require(PAGEWISE_TSV.read_bytes() == expected_tsv, "pagewise TSV exact replay differs")
    expected_automated = {
        "$schema": "interlanguage.r011-b026-automated-reader-qa/v1",
        "boundary_id": BOUNDARY_ID,
        "status": "PASS_DETERMINISTIC_BUILD_SOURCE_STRUCTURE_PDF_AND_LANGUAGE_QA",
        "learner_reader_total_pages": build["page_count"],
        "accepted_indonesian_reader_pages": build["page_count"],
        "accepted_boundary": "Chapter 7 Section 7.1",
        "complete_corpus": False,
        "page_count_is_artifact_extent_not_translation_progress": True,
        "untranslated_instructional_or_exercise_prose_pages": 0,
        "build_binding": build,
        "source_structure": structure,
        "pdf_structure": pdf,
        "language_summary": {key: value for key, value in language.items() if key != "pages"},
        "learner_pdf": build["candidate_pdf"],
        "extracted_text": build["candidate_text"],
        "translation_provenance": MODEL,
        "next_cursor": build["next_cursor"],
        "candidate_mutated": False,
        "git_used": False,
        "network_used": False,
        "credentials_accessed": False,
        "upstream_contact": False,
        "publication_performed": False,
    }
    require(AUTOMATED_QA.read_bytes() == canonical(expected_automated), "automated reader JSON exact replay differs")
    root_expected = root_visual_payload()
    require(ROOT_VISUAL_QA.read_bytes() == canonical(root_expected), "root visual JSON exact replay differs")
    visual = load_json(VISUAL_QA)
    require(visual.get("learner_pdf") == build["candidate_pdf"] and visual.get("page_count") == build["page_count"] and visual.get("defect_count") == 0, "automated visual receipt semantics differ")
    for row in visual.get("rendered_pages", []):
        validate_record(row, f"rendered page {row.get('page')}")
    for row in visual.get("contact_sheets", []):
        validate_record(row, f"contact {row.get('page_range')}")
    return {
        "status": "PASS_EXACT_B026_WHOLE_READER_QA_REPLAY",
        "page_count": build["page_count"],
        "automated": identity(AUTOMATED_QA),
        "pagewise_json": identity(PAGEWISE_QA),
        "pagewise_tsv": pagewise_id_before,
        "automated_visual": identity(VISUAL_QA),
        "root_visual": identity(ROOT_VISUAL_QA),
        "candidate": build["candidate_pdf"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--binding-requirements", action="store_true")
    modes.add_argument("--self-check", action="store_true")
    modes.add_argument("--scan", action="store_true")
    modes.add_argument("--render", action="store_true")
    modes.add_argument("--record-visual-pass", action="store_true")
    modes.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.binding_requirements:
        result = binding_requirements()
    elif args.self_check:
        build = validate_build()
        build_value = load_json(BUILD_QA)
        first = canonical({"build": build, "language": pagewise_language(), "structure": structural_source_checks(build_value), "pdf": pdf_structure_checks()})
        second = canonical({"build": validate_build(), "language": pagewise_language(), "structure": structural_source_checks(load_json(BUILD_QA)), "pdf": pdf_structure_checks()})
        require(first == second, "self-check replay differs")
        result = {"status": "PASS_DETERMINISTIC_B026_WHOLE_READER_SELF_CHECK", "page_count": build["page_count"], "writes_performed": False}
    elif args.scan:
        result = finalize_nonvisual()
    elif args.render:
        result = render_and_finalize()
    elif args.record_visual_pass:
        result = record_visual_pass()
    else:
        result = verify_existing()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (GateError, AssertionError, OSError, subprocess.SubprocessError, ValueError) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        raise SystemExit(1)
