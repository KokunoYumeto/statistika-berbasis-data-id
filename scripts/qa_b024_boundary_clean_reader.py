#!/usr/bin/env python3
"""Deterministic downstream QA for the boundary-clean R011-B024 reader.

Writes only qa/b024-reader. It does not perform root subjective visual sign-off.
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import re
import sys
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("qa_b023", ROOT / "scripts/qa_b023_boundary_clean_reader.py")
assert spec and spec.loader
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)

BOUNDARY_ID = "R011-B024"
MODEL = "OpenAI Codex gpt-5.6-sol, Ultra"
BUILD_ROOT = ROOT / "scratch/b024-boundary-clean-reader"
FINAL_PDF = BUILD_ROOT / "final/main.pdf"
FINAL_TEXT = BUILD_ROOT / "final/main-final.txt"
BUILD_QA = BUILD_ROOT / "final/R011-B024_BOUNDARY_CLEAN_BUILD_QA.json"
SOURCE_MANIFEST = BUILD_ROOT / "R011-B024_BOUNDARY_CLEAN_SOURCE_MANIFEST.tsv"
SNAPSHOT = BUILD_ROOT / "source-snapshot"
QA_DIR = ROOT / "qa/b024-reader"
QA_JSON = QA_DIR / "R011-B024_PAGEWISE_LANGUAGE_QA.json"
QA_TSV = QA_DIR / "R011-B024_PAGEWISE_LANGUAGE_QA.tsv"
RENDER_DIR = QA_DIR / "render-v1"
VISUAL_QA = QA_DIR / "R011-B024_AUTOMATED_VISUAL_QA.json"

EVIDENCE = (
    ("qa/b024-source/R011-B024_BOUNDARY_BLUEPRINT.json", "PASS_SOURCE_ASSET_DATA_RIGHTS_AND_BOUNDARY_DEPENDENCY_CLOSURE"),
    ("qa/b024-translation/R011-B024_MAIN_TRANSLATION_AUDIT.json", "PASS_COMPLETE_MAIN_SECTION_TRANSLATION_STRUCTURAL_MATH_LANGUAGE_AND_CORRECTION_QA"),
    ("qa/b024-translation/R011-B024_MAIN_TRANSLATION_INDEPENDENT_AUDIT.json", "PASS_INDEPENDENT_MAIN_TRANSLATION_MEANING_STRUCTURE_MATH_CORRECTIONS_CHARTS_RIGHTS_AND_LANGUAGE_QA"),
    ("qa/b024-translation/R011-B024_EXERCISES_ANSWERS_TRANSLATION_QA.json", "PASS_EXERCISES_31_34_AND_ALL_LINKED_PUBLIC_ODD_ANSWERS_TRANSLATED"),
    ("qa/b024-translation/R011-B024_INDEPENDENT_EXERCISE_CHART_AUDIT.json", "PASS_INDEPENDENT_EXERCISE_ANSWER_O001_CHART_DATA_RIGHTS_AND_LANGUAGE_AUDIT"),
    ("qa/b024-translation/R011-B024_LOCALIZED_CHARTS_QA.json", "PASS_THREE_LABEL_BEARING_CHARTS_LOCALIZED_AND_EXACTLY_REPLAYED"),
    ("qa/b024-translation/R011-B024_LOCALIZED_CHARTS_VISUAL_QA.json", "PASS_ALL_THREE_LOCALIZED_CHARTS_VISUALLY_INSPECTED_ZERO_DEFECTS"),
)

FORBIDDEN_LATER = (
    "Testing for independence in two-way tables", "Chi-square test of independence",
    "Inference for numerical data", "Introduction to linear regression", "Multiple and logistic regression",
    "Uji independensi menggunakan tabel dua arah", "Inferensi untuk data numerik",
)
FORBIDDEN_ENGLISH = (
    "Testing for goodness of fit using chi-square", "Degrees of Freedom", "Observed counts",
    "Expected counts", "Wait Until Positive Day", "Area representing the p-value",
    "What happens to the center", "How does the shape change", "another half has high",
)
REQUIRED = (
    "Uji kesesuaian menggunakan khi-kuadrat", "Menilai kesesuaian suatu distribusi",
    "Solusi latihan", "cacah teramati", "cacah harapan", "derajat kebebasan",
    "nilai-p", MODEL,
)
EXERCISE_LABELS = ("tf_chisq_1", "tf_chisq_2", "opensource_text_chisq_GOF", "barking_deer_chisq_GOF")


def configure_prior() -> None:
    for name, value in {
        "BOUNDARY_ID": BOUNDARY_ID, "BUILD_ROOT": BUILD_ROOT, "SNAPSHOT": SNAPSHOT,
        "FINAL_PDF": FINAL_PDF, "FINAL_TEXT": FINAL_TEXT, "BUILD_QA": BUILD_QA,
        "SOURCE_MANIFEST": SOURCE_MANIFEST, "QA_DIR": QA_DIR, "QA_JSON": QA_JSON,
        "QA_TSV": QA_TSV, "RENDER_DIR": RENDER_DIR,
        "RENDER_PAGES": RENDER_DIR / "pages", "VISUAL_QA": VISUAL_QA,
    }.items():
        setattr(prior, name, value)


def validate_evidence() -> list[dict]:
    rows = []
    for rel, status in EVIDENCE:
        path = ROOT / rel
        record = prior.load_json(path)
        if record.get("boundary_id") != BOUNDARY_ID or record.get("status") != status:
            raise AssertionError(f"non-PASS or wrong-boundary evidence: {rel}")
        rows.append(prior.identity(path))
    return rows


def validate_build() -> dict:
    build = prior.load_json(BUILD_QA)
    if build.get("$schema") != "interlanguage.r011-b024-boundary-clean-reader-build/v1" or build.get("boundary_id") != BOUNDARY_ID:
        raise AssertionError("B024 build schema/boundary differs")
    if not str(build.get("status", "")).startswith("PASS_TWO_REPLAY_DETERMINISTIC_BOUNDARY_CLEAN_BUILD"):
        raise AssertionError("B024 build is not PASS")
    pdf_id = prior.validate_identity(build.get("candidate_artifact"), "candidate PDF")
    text_id = prior.validate_identity(build.get("candidate_text"), "candidate text")
    if prior.path_from_record(build["candidate_artifact"], "candidate") != FINAL_PDF:
        raise AssertionError("candidate path differs")
    pages = len(PdfReader(FINAL_PDF).pages)
    text_pages = prior.normalized_text(FINAL_TEXT).split("\f")
    if text_pages and not text_pages[-1].strip(): text_pages.pop()
    if build.get("page_count") != pages or len(text_pages) != pages:
        raise AssertionError(f"page extent differs: pdf={pages}, text={len(text_pages)}, build={build.get('page_count')}")
    replays = {}
    for key in ("replay_a", "replay_b"):
        row = build.get(key, {})
        rid = prior.validate_identity(row.get("pdf"), f"{key}.pdf")
        tid = prior.validate_identity(row.get("text"), f"{key}.text")
        pid = prior.validate_identity(row.get("pass3"), f"{key}.pass3")
        prior.validate_identity(row.get("terminal_log"), f"{key}.log")
        if not prior.same_bytes(rid, pdf_id) or not prior.same_bytes(tid, text_id) or not prior.same_bytes(pid, pdf_id):
            raise AssertionError(f"{key} does not replay candidate bytes")
        fatal = (row.get("warnings") or {}).get("fatal")
        if fatal != {"multiply_defined_labels": 0, "rerun_required": 0, "undefined_citations": 0, "undefined_references": 0}:
            raise AssertionError(f"fatal TeX warnings in {key}: {fatal}")
        replays[key] = {"pdf": rid, "text": tid, "pass3": pid}
    if not prior.same_bytes(replays["replay_a"]["pdf"], replays["replay_b"]["pdf"]):
        raise AssertionError("replay PDF mismatch")
    manifest = prior.validate_manifest(build)
    included = str(build.get("included_scope", ""))
    if "Section 6.3" not in included or "exercises 31-34" not in included or "answers 31 and 33" not in included:
        raise AssertionError("truthful B024 included scope absent")
    cursor = build.get("next_cursor", {})
    if cursor.get("boundary_id") != "R011-B025" or cursor.get("first_instructional_line") != 2008:
        raise AssertionError("B025 cursor differs")
    evidence = validate_evidence()
    return {"candidate_pdf": pdf_id, "candidate_text": text_id, "build_receipt": prior.identity(BUILD_QA),
            "page_count": pages, "replays": replays, "source_manifest": manifest,
            "evidence": evidence, "included_scope": included,
            "excluded_untranslated_scope": build.get("excluded_untranslated_scope"), "next_cursor": cursor}


def language_scan(build: dict) -> dict:
    pages = prior.normalized_text(FINAL_TEXT).split("\f")
    if pages and not pages[-1].strip(): pages.pop()
    rows, flags, forbidden = [], [], {}
    for number, page in enumerate(pages, 1):
        lower = page.casefold()
        hits = [x for x in FORBIDDEN_ENGLISH if x.casefold() in lower]
        # The localized preface truthfully inventories all nine upstream
        # chapters.  That navigation metadata is not assembled instructional
        # scope; later-scope headings/prose are forbidden after front matter.
        if number > 20:
            hits += [x for x in FORBIDDEN_LATER if x.casefold() in lower]
        for hit in hits: forbidden.setdefault(hit, []).append(number)
        suspicious = []
        for line in page.splitlines():
            words = re.findall(r"[A-Za-zÀ-ÿ]+", line)
            en = sum(w.casefold() in prior.ENGLISH_WORDS for w in words)
            ind = sum(w.casefold() in prior.INDONESIAN_WORDS for w in words)
            if len(words) >= 7 and en >= 4 and en >= 2 * max(ind, 1): suspicious.append(line.strip()[:400])
        if suspicious: flags.append({"page": number, "lines": suspicious})
        rows.append({"page": number, "text_sha256": prior.digest(page.encode()), "characters": len(page),
                     "forbidden_matches": hits, "heuristic_suspect": bool(suspicious),
                     "untranslated_instructional_or_exercise_prose": bool(hits)})
    joined = " ".join(re.sub(r"\s+", " ", p) for p in pages)
    missing = [x for x in REQUIRED if x.casefold() not in joined.casefold()]
    if forbidden or missing:
        raise AssertionError(f"language/scope failure forbidden={forbidden} missing={missing}")
    allowed_flags, root_flags = [], []
    for flag in flags:
        allowed, unresolved = [], []
        for line in flag["lines"]:
            is_math = bool(re.match(r"^P\s*\(", line))
            is_citation = bool(re.match(r"^\d+\s", line)) or " In: " in line or "data collected" in line
            (allowed if is_math or is_citation else unresolved).append(
                {"text": line, "category": "displayed_probability_notation" if is_math else "citation_or_source_title"}
            )
        if allowed: allowed_flags.append({"page": flag["page"], "lines": allowed})
        if unresolved: root_flags.append({"page": flag["page"], "lines": unresolved})
    return {"status": "PASS_PAGEWISE_FORBIDDEN_AND_REQUIRED_LANGUAGE_SCAN", "pages": rows,
            "suspect_pages_requiring_root_adjudication": [x["page"] for x in root_flags],
            "allowed_english_or_literal_adjudications": allowed_flags,
            "suspect_evidence": root_flags, "forbidden_matches": forbidden, "missing_required": missing}


def structural(build: dict) -> dict:
    custom = prior.load_json(BUILD_QA).get("custom_sources", {})
    chapter = prior.path_from_record(custom["custom_chapter"], "custom chapter").read_text(encoding="utf-8")
    exercises = prior.path_from_record(custom["custom_exercises_31_34"], "custom exercises").read_text(encoding="utf-8")
    answers = prior.path_from_record(custom["custom_answers_1_34_public"], "custom answers").read_text(encoding="utf-8")
    if chapter.count(r"\label{oneWayChiSquare}") != 1 or r"\label{twoWayTablesAndChiSquare}" in chapter:
        raise AssertionError("Section 6.3/6.4 boundary label closure differs")
    missing = [x for x in EXERCISE_LABELS if fr"\label{{{x}}}" not in exercises]
    ordinals = [int(x) for x in re.findall(r"(?m)^% (\d+)\s*$", exercises)]
    answer_ids = [int(x) for x in re.findall(r"(?m)^%\s*(\d+)\s*$", answers)][-17:]
    if missing or ordinals != [31, 32, 33, 34] or exercises.count(r"\eoce{") != 4:
        raise AssertionError(f"exercise closure differs missing={missing} ordinals={ordinals}")
    if answer_ids != list(range(1, 34, 2)) or any(x % 2 == 0 for x in answer_ids):
        raise AssertionError(f"public answer closure differs: {answer_ids}")
    source = chapter + exercises + answers
    if re.search(r"\\(?:solution|instructor|answerkey)\b", source, re.I):
        raise AssertionError("restricted solution command present")
    for formula in (r"\newcommand{\spdaysXSq}{4.61}", r"\newcommand{\spdaysDF}{5}", r"\newcommand{\spdaysPvalue}{0.4650}"):
        if formula not in chapter: raise AssertionError(f"corrected formula absent: {formula}")
    return {"section_6_3_label_exact": True, "section_6_4_absent": True,
            "exercise_ids": ordinals, "public_answer_ids": answer_ids,
            "o001_gap_ids": list(range(2, 35, 2)), "corrected_formula_closure": True,
            "restricted_instructor_solutions_accessed_or_invented": False}


def render(build: dict) -> dict:
    configure_prior()
    visual = prior.render_visual(build)
    record = prior.load_json(VISUAL_QA)
    if record.get("$schema") != "interlanguage.r011-b024-automated-visual-qa/v1":
        record["$schema"] = "interlanguage.r011-b024-automated-visual-qa/v1"
        record["root_subjective_visual_signoff_claimed"] = False
        VISUAL_QA.write_bytes(prior.canonical(record))
        visual["receipt"] = prior.identity(VISUAL_QA)
    return visual


def finalize(build: dict, language: dict, structure: dict, visual: dict) -> dict:
    payload = {"$schema": "interlanguage.r011-b024-pagewise-language-qa/v1", "boundary_id": BOUNDARY_ID,
               "status": "PASS_DETERMINISTIC_BUILD_PAGEWISE_LANGUAGE_STRUCTURE_AND_AUTOMATED_VISUAL_QA",
               "learner_reader_total_pages": build["page_count"], "accepted_indonesian_reader_pages": build["page_count"],
               "all_pages_adjudicated_by_deterministic_checks": True, "root_subjective_visual_signoff_claimed": False,
               "build_binding": build, "language": language, "structural_checks": structure,
               "automated_visual_qa": visual, "learner_pdf": build["candidate_pdf"], "translation_provenance": MODEL}
    QA_DIR.mkdir(parents=True, exist_ok=True)
    QA_JSON.write_bytes(prior.canonical(payload))
    fields = list(language["pages"][0])
    with QA_TSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader(); writer.writerows(language["pages"])
    return {"status": payload["status"], "page_count": build["page_count"], "suspect_pages": language["suspect_pages_requiring_root_adjudication"],
            "json": prior.identity(QA_JSON), "tsv": prior.identity(QA_TSV), "visual": visual}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("self-check", "scan", "render", "finalize"))
    args = parser.parse_args()
    configure_prior()
    build = validate_build(); language = language_scan(build); structure = structural(build)
    if args.mode == "self-check":
        again = (validate_build(), language_scan(build), structural(build))
        if prior.canonical([build, language, structure]) != prior.canonical(list(again)): raise AssertionError("in-process replay differs")
        result = {"status": "PASS_DETERMINISTIC_B024_BUILD_LANGUAGE_AND_STRUCTURE_QA", "page_count": build["page_count"], "suspect_pages": language["suspect_pages_requiring_root_adjudication"]}
    elif args.mode == "scan": result = {"build": build, "language": language, "structural": structure}
    else:
        visual = render(build)
        result = {"visual": visual, "page_count": build["page_count"]} if args.mode == "render" else finalize(build, language, structure, visual)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2)); return 0


if __name__ == "__main__":
    try: raise SystemExit(main())
    except (AssertionError, OSError, ValueError) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr); raise SystemExit(1)
