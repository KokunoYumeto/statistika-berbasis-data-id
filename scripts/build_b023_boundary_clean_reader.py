#!/usr/bin/env python3
"""Build the deterministic R011-B023 Indonesian learner reader.

B023 extends the admitted B022 reader through Chapter 6, Section 6.2
(difference of two proportions).  This builder is intentionally a closed
operation: it verifies the pinned B022 source snapshot, the B023 source
blueprint, the independently audited translation fragments, and the
localized blade chart before making an isolated scratch build.  It never
mutates the live repository, backend, controls, or release directories.
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

import build_b021_boundary_clean_reader as prior
import build_b022_boundary_clean_reader as b022


common = prior.common
ROOT = Path(__file__).resolve().parents[1]
BOUNDARY_ID = "R011-B023"
MODEL = "OpenAI Codex gpt-5.6-sol, Ultra"

SOURCE = ROOT / "scratch/b022-boundary-clean-reader/source-snapshot"
BUILD = ROOT / "scratch/b023-boundary-clean-reader"
SNAPSHOT = BUILD / "source-snapshot"
RUN_A = BUILD / "replay-a"
RUN_B = BUILD / "replay-b"
FINAL = BUILD / "final"
FINAL_PDF = FINAL / "main.pdf"
FINAL_TEXT = FINAL / "main-final.txt"
MANIFEST = BUILD / "R011-B023_BOUNDARY_CLEAN_SOURCE_MANIFEST.tsv"
RECEIPT = FINAL / "R011-B023_BOUNDARY_CLEAN_BUILD_QA.json"

SOURCE_MAIN = SOURCE / "main_boundary_clean_b022.tex"
SOURCE_ANSWERS = SOURCE / "extraTeX/eoceSolutions/eoceSolutions_boundary_clean_b022.tex"
SOURCE_CHAPTER = SOURCE / "ch_inference_for_props/TeX/ch_inference_for_props.tex"
SOURCE_EXERCISES_OLD = SOURCE / "ch_inference_for_props/TeX/inference_for_a_single_proportion.tex"
SOURCE_EXERCISES_NEW = SOURCE / "ch_inference_for_props/TeX/difference_of_two_proportions.tex"

FIGURE_BLADE_REL = Path(
    "ch_inference_for_props/figures/bladesTwoSampleHTPValueQC/"
    "bladesTwoSampleHTPValueQC.pdf"
)
FIGURE_MAMMOGRAM_REL = Path(
    "ch_inference_for_props/figures/mammograms/mammogramPValue.pdf"
)
FIGURE_QUADCOPTER_REL = Path(
    "ch_inference_for_props/figures/quadcopter/quadcopter_david_j.jpg"
)
FIGURE_BLADE_R_REL = Path(
    "ch_inference_for_props/figures/bladesTwoSampleHTPValueQC/"
    "bladesTwoSampleHTPValueQC.R"
)
SOURCE_FIGURE_BLADE = SOURCE / FIGURE_BLADE_REL
SOURCE_FIGURE_MAMMOGRAM = SOURCE / FIGURE_MAMMOGRAM_REL
SOURCE_FIGURE_QUADCOPTER = SOURCE / FIGURE_QUADCOPTER_REL
SOURCE_FIGURE_BLADE_R = SOURCE / FIGURE_BLADE_R_REL

CUSTOM_MAIN = SNAPSHOT / "main_boundary_clean_b023.tex"
CUSTOM_ANSWERS = SNAPSHOT / "extraTeX/eoceSolutions/eoceSolutions_boundary_clean_b023.tex"
CUSTOM_CHAPTER = SNAPSHOT / "ch_inference_for_props/TeX/ch_inference_for_props.tex"
CUSTOM_EXERCISES_OLD = SNAPSHOT / "ch_inference_for_props/TeX/inference_for_a_single_proportion.tex"
CUSTOM_EXERCISES_NEW = SNAPSHOT / "ch_inference_for_props/TeX/difference_of_two_proportions.tex"
CUSTOM_FIGURE_BLADE = SNAPSHOT / FIGURE_BLADE_REL

STAGING = ROOT / "qa/b023-translation/staging"
SECTION_A = STAGING / "section-lines-555-866.id.tex"
SECTION_B = STAGING / "section-lines-867-1130.id.tex"
SECTION_C = STAGING / "section-lines-1131-1336.id.tex"
EXERCISES_A = STAGING / "exercises-lines-1-212.id.tex"
EXERCISES_B = STAGING / "exercises-lines-213-406.id.tex"
ANSWERS_ID = STAGING / "public-answers-lines-1363-1472.id.tex"
LOCALIZED_BLADE = STAGING / "assets/bladesTwoSampleHTPValueQC.id.pdf"
TRANSLATION_AUDIT = ROOT / "qa/b023-translation/R011-B023_TRANSLATION_AUDIT.json"
BLUEPRINT = ROOT / "qa/b023-source/R011-B023_BOUNDARY_BLUEPRINT.json"

EXPECTED_SOURCE_FILE_COUNT = 1214
EXPECTED_SOURCE_BYTES = 41_601_621
EXPECTED_SOURCE_INVENTORY_SHA256 = (
    "56a0f05f56568f3ba4737cfc326f7ca1128777eeb1081c1110e057680a8e5619"
)

# These are the exact bytes in the admitted B022 snapshot.  The inventory
# gate above covers all other files; these high-value anchors make accidental
# source substitution conspicuous.
EXPECTED_SOURCE_FILES = {
    SOURCE_MAIN: (6971, "2c5a323c81c51a96741a91105568ce28e94376070f431e2545c73673d3eb8024"),
    SOURCE_ANSWERS: (50812, "06fcffca1f403765df6606e98c12a342e942190e2c5157126050f34f553b1f93"),
    SOURCE_CHAPTER: (22094, "7c07f42115d499c50ad1560fffed3d2e569da9a62e2113865fed3dd216d77e34"),
    SOURCE_EXERCISES_OLD: (14353, "75e17c52954b82604090f09a8131ba5bf9b97494d76f4b34d8c4448ccc426655"),
    SOURCE_EXERCISES_NEW: (16786, "443eb8835af956fea62293b2ea6bb2e928ec311ac1981b0e2266fc092f3f8397"),
    SOURCE_FIGURE_BLADE: (7951, "c55e8a93fb1bf0557257ae8b0baf5a1e57f521816411913ef9d658ec51876500"),
    SOURCE_FIGURE_MAMMOGRAM: (7879, "afb58f46da385a6cde4f434aa46a1329ac8113753fbd79d1b3b6e5b023f719cd"),
    SOURCE_FIGURE_QUADCOPTER: (1493656, "1db88d4694e0dbefe6187ea3f671000bf90928466d0fb8268524b2172cb0d260"),
    SOURCE_FIGURE_BLADE_R: (519, "b2b32950303284f2b2da7248e449100a9d87c29d4e3efc1bcd3fe2fb3465004c"),
}

EXPECTED_AUTHORITY_MAIN = (
    103385,
    "a2470ca3041209d1f1194b3ab27e8124405d8fdbd1ccece89a0319be13fae8a7",
)
EXPECTED_AUTHORITY_EXERCISES = (
    16786,
    "443eb8835af956fea62293b2ea6bb2e928ec311ac1981b0e2266fc092f3f8397",
)
EXPECTED_AUTHORITY_ANSWERS = (
    106045,
    "6c4e01376db4c023cc7b3f9949490e57220ef1cb831c580da71efde6ce723268",
)

SCOPE_B023 = r"""\chapter*{Cakupan edisi parsial ini}
\addcontentsline{toc}{chapter}{Cakupan edisi parsial ini}
Pembaca ini berhenti tepat setelah Bagian~6.2,
\emph{Selisih dua proporsi}. Cakupan Bab~6 dalam edisi ini
memuat seluruh empat belas latihan pada bagian ini, yaitu latihan 17--30,
serta latihan 1--16 dari Bagian~6.1. Semua jawaban publik yang tersedia
dari sumber disertakan: jawaban untuk latihan 1, 3, 5, 7, 9, 11, 13, 15,
17, 19, 21, 23, 25, 27, dan 29. Jawaban untuk latihan 2, 4, 6, 8, 10,
12, 14, 16, 18, 20, 22, 24, 26, 28, dan 30 memang tidak tersedia dalam
sumber publik; jawaban-jawaban itu dicatat sebagai kesenjangan pendamping
kemahiran O001 dan tidak direka."""

OLD_B022_NOTE = "% Boundary-clean learner reader through Chapter 6, Section 6.1."
NEW_B023_NOTE = "% Boundary-clean learner reader through Chapter 6, Section 6.2."
OLD_ANSWER_INCLUDE = r"\include{extraTeX/eoceSolutions/eoceSolutions_boundary_clean_b022}"
NEW_ANSWER_INCLUDE = r"\include{extraTeX/eoceSolutions/eoceSolutions_boundary_clean_b023}"
OLD_NAV = (
    r"  \chaptersection{singleProportion}" + "\n"
    "% Boundary-clean reader omits navigation to excluded later Chapter 6 sections."
)
NEW_NAV = (
    r"  \chaptersection{singleProportion}" + "\n"
    r"  \chaptersection{differenceOfTwoProportions}" + "\n"
    "% Boundary-clean reader omits navigation to excluded later Chapter 6 sections."
)
FORCED_BREAK = r"\D{\newpage}"
REFLOW_NOTE = "% Boundary-clean reader removes a legacy forced page break."

FORBIDDEN_STAGED_ENGLISH = (
    "Difference of two proportions",
    "Hypothesis tests for the difference of two proportions",
    "More on 2-proportion hypothesis tests",
    "Testing for goodness of fit using chi-square",
    "Can she used",
)
FORBIDDEN_READER_ENGLISH = (
    "Inference for categorical data",
    "Difference of two proportions",
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


def normalized_lf(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")


def memory_identity(name: str, value: str) -> dict[str, Any]:
    raw = value.encode("utf-8")
    return {"name": name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def source_slice(path: Path, first_line: int, last_line: int) -> bytes:
    lines = path.read_bytes().splitlines(keepends=True)
    common.require(len(lines) >= last_line, f"authority source too short: {common.rel(path)}")
    return b"".join(lines[first_line - 1:last_line])


def require_slice(path: Path, first_line: int, last_line: int, expected: tuple[int, str]) -> None:
    raw = source_slice(path, first_line, last_line)
    common.require(
        (len(raw), hashlib.sha256(raw).hexdigest()) == expected,
        f"authority slice identity changed: {common.rel(path)}:{first_line}-{last_line}",
    )


def audit_target_rows(audit: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if isinstance(audit.get("target"), dict):
        rows.append(audit["target"])
    if isinstance(audit.get("targets"), list):
        rows.extend(row for row in audit["targets"] if isinstance(row, dict))
    return rows


def require_audit_target(audit: dict[str, Any], path: Path) -> None:
    rel = common.rel(path)
    matches = [row for row in audit_target_rows(audit) if row.get("path") == rel]
    common.require(len(matches) == 1, f"audit target binding absent or ambiguous: {rel}")
    observed = common.identity(path)
    row = matches[0]
    audited_bytes = row.get("bytes", row.get("bytes_utf8"))
    common.require(audited_bytes == observed["bytes"], f"audit bytes changed: {rel}")
    common.require(
        str(row.get("sha256", "")).casefold() == observed["sha256"],
        f"audit hash changed: {rel}",
    )


def require_protected_sequences(source: str, target: str, label: str) -> None:
    """Check source/target structures that translation must not alter."""
    patterns = {
        "labels": r"\\label\{([^{}]*)\}",
        "refs": r"\\(?:pageref|ref)\{([^{}]*)\}",
        "cites": r"\\(?:footfullcite|citeauthor|citeyear|cite)\{([^{}]*)\}",
        "begins": r"\\begin\{([^{}]*)\}",
        "ends": r"\\end\{([^{}]*)\}",
    }
    for kind, pattern in patterns.items():
        left = re.findall(pattern, source)
        right = re.findall(pattern, target)
        common.require(left == right, f"{label} protected {kind} sequence changed")
    # Every translated span must remain syntactically brace-balanced.  This
    # intentionally ignores escaped braces and comments, which are validated
    # by the independent translation audit.
    def brace_delta(value: str) -> int:
        # Remove full-line and inline comments while retaining escaped
        # percentage signs used in mathematical prose.
        stripped = re.sub(r"(?m)(?<!\\)%.*$", "", value)
        stripped = re.sub(r"\\.", "", stripped)
        return stripped.count("{") - stripped.count("}")
    common.require(brace_delta(target) == 0, f"{label} braces are unbalanced")


def verify_blueprint() -> dict[str, Any]:
    common.require(BLUEPRINT.is_file(), "B023 source blueprint absent")
    blueprint = json.loads(BLUEPRINT.read_text(encoding="utf-8"))
    common.require(blueprint.get("boundary_id") == BOUNDARY_ID, "B023 boundary id changed")
    common.require(
        blueprint.get("status") == "PASS_SOURCE_ASSET_RIGHTS_AND_BOUNDARY_DEPENDENCY_CLOSURE",
        "B023 source/asset closure did not pass",
    )
    authority = blueprint.get("authority", {})
    common.require(
        authority.get("commit") == "fee25091fb24e89c36296fd67c48c1fcf7a93b6e"
        and authority.get("branch_observed") == "master",
        "B023 authority pin changed",
    )
    main = blueprint.get("main_source", {})
    common.require(
        main.get("start_line") == 555
        and main.get("end_line") == 1336
        and main.get("start_label") == "differenceOfTwoProportions",
        "B023 main boundary changed",
    )
    common.require(main.get("slice", {}).get("bytes") == 31718, "B023 main slice bytes changed")
    common.require(
        main.get("slice", {}).get("sha256")
        == "f910f7af7dc61358de56a7eea91336bd89816780941324aa4da585246965c6ef",
        "B023 main slice hash changed",
    )
    closure = blueprint.get("exercise_answer_closure", {})
    common.require(
        closure.get("chapter_exercise_ids") == list(range(17, 31)),
        "B023 exercise closure changed",
    )
    common.require(
        closure.get("public_answer_ids") == [17, 19, 21, 23, 25, 27, 29],
        "B023 public-answer closure changed",
    )
    common.require(
        closure.get("o001_gap_ids") == [18, 20, 22, 24, 26, 28, 30],
        "B023 O001 gap closure changed",
    )
    common.require(
        closure.get("restricted_solutions_accessed_or_invented") is False,
        "B023 restricted-solution boundary changed",
    )
    post = blueprint.get("post_boundary_cursor", {})
    common.require(
        post.get("working_boundary_id") == "R011-B024"
        and post.get("line") == 1344
        and post.get("label") == "oneWayChiSquare",
        "B023 next cursor changed",
    )
    return {
        "boundary_id": blueprint["boundary_id"],
        "authority": authority,
        "main_source": main,
        "exercise_answer_closure": closure,
        "production_closure": blueprint.get("production_closure", {}),
    }


def verify_inputs() -> dict[str, Any]:
    common.require(SOURCE.is_dir(), "admitted B022 source snapshot absent")
    inventory = common.source_inventory(SOURCE)
    common.require(inventory["files"] == EXPECTED_SOURCE_FILE_COUNT, "B022 source file count changed")
    common.require(inventory["bytes"] == EXPECTED_SOURCE_BYTES, "B022 source byte count changed")
    common.require(
        inventory["inventory_sha256"] == EXPECTED_SOURCE_INVENTORY_SHA256,
        "B022 source inventory changed",
    )
    for path, expected in EXPECTED_SOURCE_FILES.items():
        common.require_exact(path, expected)
    authority_root = ROOT / "authority/upstream/openintro-statistics-fee25091fb24e89c36296fd67c48c1fcf7a93b6e"
    authority_main = authority_root / "ch_inference_for_props/TeX/ch_inference_for_props.tex"
    authority_exercises = authority_root / "ch_inference_for_props/TeX/difference_of_two_proportions.tex"
    authority_answers = authority_root / "extraTeX/eoceSolutions/eoceSolutions.tex"
    common.require_exact(authority_main, EXPECTED_AUTHORITY_MAIN)
    common.require_exact(authority_exercises, EXPECTED_AUTHORITY_EXERCISES)
    common.require_exact(authority_answers, EXPECTED_AUTHORITY_ANSWERS)
    require_slice(authority_main, 555, 1336, (31718, "f910f7af7dc61358de56a7eea91336bd89816780941324aa4da585246965c6ef"))
    require_slice(authority_exercises, 1, 406, EXPECTED_AUTHORITY_EXERCISES)
    require_slice(authority_answers, 1363, 1472, (4811, "a5e216d508f48d3421669683186dfbf451cba585ab3099c404f72c9a87f6e121"))
    blueprint = verify_blueprint()
    common.require(TRANSLATION_AUDIT.is_file(), "B023 translation audit absent")
    audit = json.loads(TRANSLATION_AUDIT.read_text(encoding="utf-8"))
    common.require(audit.get("boundary_id") == BOUNDARY_ID, "B023 translation audit boundary changed")
    status = str(audit.get("status", ""))
    common.require(status.startswith("PASS"), "B023 translation audit did not pass")
    # The composite audit predates a dedicated contact field; absence is the
    # truthful value here.  Reject an explicit positive contact assertion.
    common.require(
        audit.get("upstream_contacted", audit.get("upstream_contact", False)) is not True,
        "B023 upstream contact was recorded",
    )
    for target in (SECTION_A, SECTION_B, SECTION_C, EXERCISES_A, EXERCISES_B, ANSWERS_ID):
        require_audit_target(audit, target)
    return {
        "base_source": {key: inventory[key] for key in ("files", "bytes", "inventory_sha256")},
        "source_anchors": [common.identity(path) for path in EXPECTED_SOURCE_FILES],
        "authority_slices": {
            "main_555_1336": {"bytes": 31718, "sha256": "f910f7af7dc61358de56a7eea91336bd89816780941324aa4da585246965c6ef"},
            "exercises_1_406": {"bytes": 16786, "sha256": EXPECTED_AUTHORITY_EXERCISES[1]},
            "answers_1363_1472": {"bytes": 4811, "sha256": "a5e216d508f48d3421669683186dfbf451cba585ab3099c404f72c9a87f6e121"},
        },
        "blueprint": blueprint,
        "translation_audit": common.identity(TRANSLATION_AUDIT),
        "translation_targets": [common.identity(path) for path in (SECTION_A, SECTION_B, SECTION_C, EXERCISES_A, EXERCISES_B, ANSWERS_ID)],
    }


def verify_staged_fragments() -> dict[str, Any]:
    fragments = ((SECTION_A, 555, 866), (SECTION_B, 867, 1130), (SECTION_C, 1131, 1336))
    authority = ROOT / "authority/upstream/openintro-statistics-fee25091fb24e89c36296fd67c48c1fcf7a93b6e/ch_inference_for_props/TeX/ch_inference_for_props.tex"
    for path, first, last in fragments:
        target = normalized_lf(path)
        common.require(target.endswith("\n"), f"fragment lacks terminal LF: {common.rel(path)}")
        common.require(target.count(FORCED_BREAK) > 0, f"fragment has no source-order page-break marker: {common.rel(path)}")
        source = source_slice(authority, first, last).decode("utf-8")
        require_protected_sequences(source, target, common.rel(path))
        stripped = re.sub(r"(?m)^%.*$", "", target)
        for phrase in FORBIDDEN_STAGED_ENGLISH:
            common.require(phrase.casefold() not in stripped.casefold(), f"English staged phrase remains ({phrase}): {common.rel(path)}")
    exercise_a = normalized_lf(EXERCISES_A)
    exercise_b = normalized_lf(EXERCISES_B)
    common.require(exercise_a.startswith(r"\exercisesheader{}"), "B023 exercise chunk header changed")
    exercise_body = exercise_a.split("\n", 1)[1] + exercise_b
    numbers = [int(v) for v in re.findall(r"(?m)^% (\d+)\s*$", exercise_body)]
    common.require(numbers == list(range(17, 31)), f"B023 exercise sequence changed: {numbers}")
    common.require(exercise_body.count(r"\eoce{") == 14, "B023 exercise block count changed")
    answers = normalized_lf(ANSWERS_ID)
    answer_numbers = [int(v) for v in re.findall(r"(?m)^% (\d+)\s*$", answers)]
    common.require(answer_numbers == [17, 19, 21, 23, 25, 27, 29], "B023 public-answer sequence changed")
    common.require(answers.count(r"\eocesol{") == 7, "B023 public-answer count changed")
    # The independently generated chart must have no selectable English label.
    common.require(LOCALIZED_BLADE.is_file(), "B023 localized blade chart absent")
    localized_reader = PdfReader(LOCALIZED_BLADE)
    common.require(len(localized_reader.pages) == 1, "B023 localized blade chart page count changed")
    original_reader = PdfReader(SOURCE_FIGURE_BLADE)
    common.require(
        [float(v) for v in localized_reader.pages[0].mediabox]
        == [float(v) for v in original_reader.pages[0].mediabox],
        "B023 localized blade chart page box changed",
    )
    chart_text = localized_reader.pages[0].extract_text() or ""
    for token in ("0.006", "0.03", "0.059", "nilai", "nol"):
        common.require(token in chart_text, f"B023 localized chart token absent: {token}")
    common.require("null" not in chart_text.casefold() and "value" not in chart_text.casefold(), "English chart label remains")
    return {
        "chapter_fragments": [common.identity(path) for path, _, _ in fragments],
        "exercise_fragments": [common.identity(EXERCISES_A), common.identity(EXERCISES_B)],
        "public_answers": common.identity(ANSWERS_ID),
        "localized_blade_chart": common.identity(LOCALIZED_BLADE),
        "exercise_ordinals": numbers,
        "public_answer_ordinals": answer_numbers,
    }


def prepare_custom_texts() -> tuple[dict[Path, str], dict[str, Any]]:
    main = normalized_lf(SOURCE_MAIN)
    common.require(main.count(b022.SCOPE_B022) == 1, "B022 scope block changed")
    main = main.replace(b022.SCOPE_B022, SCOPE_B023)
    # Section 6.2 retains a cross-reference to the later numerical-inference
    # chapter.  Keep the same truthful ``belum dimuat`` forward-reference
    # policy used by the admitted B022 main, without exposing that chapter.
    stub_anchor = r"\label{ch_regr_mult_and_log}" + "\n"
    common.require(stub_anchor in main, "B022 forward-reference stub anchor changed")
    main = main.replace(
        stub_anchor,
        r"\label{ch_regr_mult_and_log}" + "\n"
        r"\label{ch_inference_for_means}" + "\n",
        1,
    )
    common.require(main.count(OLD_B022_NOTE) == 1, "B022 boundary note changed")
    main = main.replace(OLD_B022_NOTE, NEW_B023_NOTE)
    common.require(main.count(OLD_ANSWER_INCLUDE) == 1, "B022 answer include changed")
    main = main.replace(OLD_ANSWER_INCLUDE, NEW_ANSWER_INCLUDE)
    common.require(main.count(r"\input{ch_inference_for_props/TeX/ch_inference_for_props}") == 1, "B023 Chapter 6 input count changed")

    chapter = normalized_lf(SOURCE_CHAPTER)
    common.require(chapter.count(OLD_NAV) == 1, "B022 chapter navigation block changed")
    chapter = chapter.replace(OLD_NAV, NEW_NAV)
    a = normalized_lf(SECTION_A)
    b = normalized_lf(SECTION_B)
    c = normalized_lf(SECTION_C)
    expected_breaks = {"A": 1, "B": 3, "C": 2}
    for name, value in (("A", a), ("B", b), ("C", c)):
        common.require(value.endswith("\n"), f"B023 section {name} lacks terminal LF")
        common.require(value.count(FORCED_BREAK) == expected_breaks[name], f"B023 section {name} break topology changed")
    a = a.replace(FORCED_BREAK, REFLOW_NOTE)
    b = b.replace(FORCED_BREAK, REFLOW_NOTE)
    c = c.replace(FORCED_BREAK, REFLOW_NOTE)
    input_single = r"{\input{ch_inference_for_props/TeX/inference_for_a_single_proportion.tex}}"
    common.require(chapter.count(input_single) == 1, "B022 Section 6.1 input anchor changed")
    chapter = chapter.replace(input_single, input_single + "\n\n" + a + b + c)
    actual_sections = re.findall(r"(?m)^\s*(?!%)\\section\{", chapter)
    common.require(len(actual_sections) == 2, "assembled Chapter 6 section count changed")
    common.require(chapter.count(r"\label{singleProportion}") == 1, "single-proportion label count changed")
    common.require(chapter.count(r"\label{differenceOfTwoProportions}") == 1, "difference label count changed")
    common.require(chapter.count(r"\input{ch_inference_for_props/TeX/difference_of_two_proportions.tex}") == 1, "B023 exercise input count changed")
    common.require(FORCED_BREAK not in chapter, "legacy Chapter 6 forced break remained")

    old_exercises = normalized_lf(SOURCE_EXERCISES_OLD)
    old_numbers = [int(v) for v in re.findall(r"(?m)^% (\d+)\s*$", old_exercises)]
    common.require(old_numbers == list(range(1, 17)), "carried B022 exercise sequence changed")
    new_a = normalized_lf(EXERCISES_A)
    new_b = normalized_lf(EXERCISES_B)
    common.require(new_a.startswith(r"\exercisesheader{}" + "\n"), "B023 exercise header anchor changed")
    appended = new_a.split("\n", 1)[1] + new_b
    common.require(appended.count(FORCED_BREAK) == 3, "B023 exercise break topology changed")
    appended = appended.replace(FORCED_BREAK, REFLOW_NOTE)
    flowing_header = "\n".join([
        r"\begingroup",
        r"\renewcommand{\clearpageforsection}{}",
        r"\exercisesheader{}",
        r"\endgroup",
    ])
    # Keep the 6.1 exercise file as the admitted B022 bytes.  Section 6.2's
    # source has its own exercise input, so placing 1--16 in that file would
    # duplicate labels and produce multiply-defined cross-references.
    new_exercises = flowing_header + "\n\n" + appended
    new_numbers = [int(v) for v in re.findall(r"(?m)^% (\d+)\s*$", new_exercises)]
    common.require(new_numbers == list(range(17, 31)), f"B023 exercise sequence changed: {new_numbers}")
    common.require(new_exercises.count(r"\eoce{") == 14, "B023 exercise block count changed")
    common.require(FORCED_BREAK not in new_exercises, "legacy Section 6.2 exercise break remained")

    old_answers = normalized_lf(SOURCE_ANSWERS)
    closing = "\n\\end{multicols}\n"
    common.require(old_answers.endswith(closing), "B022 answer close anchor changed")
    new_answers = normalized_lf(ANSWERS_ID)
    answers = old_answers[:-len(closing)].rstrip("\n") + "\n\n" + new_answers.rstrip("\n") + closing
    common.require(answers.count(r"\begin{multicols}{2}") == answers.count(r"\end{multicols}"), "answer columns unbalanced")
    common.require(answers.rstrip().endswith(r"\end{multicols}"), "B023 answer close absent")
    answer_numbers = [int(v) for v in re.findall(r"(?m)^% (\d+)\s*$", new_answers)]
    common.require(answer_numbers == [17, 19, 21, 23, 25, 27, 29], "B023 answer sequence changed")

    custom = {
        CUSTOM_MAIN: main,
        CUSTOM_CHAPTER: chapter,
        CUSTOM_EXERCISES_NEW: new_exercises,
        CUSTOM_ANSWERS: answers,
    }
    transforms = {
        "scope_updated": "through Chapter 6, Section 6.2",
        "chapter_navigation_added": "differenceOfTwoProportions",
        "section_6_2_fragments_appended": ["555-866", "867-1130", "1131-1336"],
        "exercise_closure": list(range(1, 31)),
        "public_answer_closure": [1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23, 25, 27, 29],
        "o001_gap_closure": [2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30],
        "legacy_forced_page_breaks_removed": {"section_main": 6, "section_exercises": 3, "total": 9},
        "translation_staging_mutated": False,
        "localized_chart_installed": True,
    }
    return custom, transforms


def install_localized_figure() -> dict[str, Any]:
    before = common.identity(CUSTOM_FIGURE_BLADE)
    shutil.copy2(LOCALIZED_BLADE, CUSTOM_FIGURE_BLADE)
    after = common.identity(CUSTOM_FIGURE_BLADE)
    expected = common.identity(LOCALIZED_BLADE)
    common.require(
        (after["bytes"], after["sha256"]) == (expected["bytes"], expected["sha256"]),
        "localized blade chart copy differs",
    )
    return {"before": before, "installed": after, "source": common.identity(SOURCE_FIGURE_BLADE), "page_boxes_preserved": True}


def make_custom_sources() -> dict[str, Any]:
    texts, transforms = prepare_custom_texts()
    for path, text in texts.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    localized = install_localized_figure()
    return {
        "custom_main": common.identity(CUSTOM_MAIN),
        "custom_chapter": common.identity(CUSTOM_CHAPTER),
        "custom_exercises_1_16_carried": common.identity(CUSTOM_EXERCISES_OLD),
        "custom_exercises_17_30": common.identity(CUSTOM_EXERCISES_NEW),
        "custom_answers_1_30_public": common.identity(CUSTOM_ANSWERS),
        "localized_blade_chart": localized,
        "assembly_transformations": transforms,
    }


def page_boxes(page: Any) -> list[float]:
    return [float(v) for v in page.mediabox]


def build_once(label: str, directory: Path, tools: dict[str, str], seed: str) -> dict[str, Any]:
    common.require(not directory.exists(), f"refusing to overwrite replay: {common.rel(directory)}")
    directory.mkdir(parents=True)
    env = dict(os.environ)
    env.update({
        "SOURCE_DATE_EPOCH": "1787961600",
        "FORCE_SOURCE_DATE": "1",
        "TZ": "UTC",
        "MIKTEX_ENABLE_INSTALLER": "0",
    })
    env["BIBINPUTS"] = str(SNAPSHOT) + os.pathsep + env.get("BIBINPUTS", "")
    latex = [
        tools["pdflatex"], "-interaction=nonstopmode", "-halt-on-error",
        "-file-line-error", "-recorder", "-no-shell-escape", "-synctex=0",
        "-jobname=main", f"-output-directory={directory}",
        rf"\pdftrailerid{{<{seed}><{seed}>}}\input{{main_boundary_clean_b023.tex}}",
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
    common.require(common.identity(pdf)["sha256"] == common.identity(pass3)["sha256"], f"{label} pass 3/4 differ")
    common.run_logged([tools["pdfinfo"], str(pdf)], directory, directory / "console-pdfinfo.txt")
    common.run_logged([tools["mutool"], "show", str(pdf), "trailer"], directory, directory / "console-mutool-trailer.txt")
    text = directory / "main-final.txt"
    common.run_logged([tools["pdftotext"], "-layout", "-enc", "UTF-8", str(pdf), str(text)], directory, directory / "console-pdftotext.txt")
    # Poppler on Windows emits CRLF.  Canonicalize the extracted reader text
    # immediately so both deterministic replays, QA consumers, and the final
    # receipt bind platform-neutral LF bytes.
    extracted = text.read_bytes()
    try:
        extracted_text = extracted.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise common.GateError(f"{label} pdftotext output is not UTF-8: {exc}") from exc
    canonical_text = extracted_text.replace("\r\n", "\n").replace("\r", "\n")
    text.write_bytes(canonical_text.encode("utf-8"))
    common.require(b"\r" not in text.read_bytes(), f"{label} canonical text still contains CR")
    info = (directory / "console-pdfinfo.txt").read_text(encoding="utf-8", errors="replace")
    match = re.search(r"^Pages:\s+(\d+)", info, re.MULTILINE)
    pages = int(match.group(1)) if match else 0
    common.require(220 <= pages <= 430, f"{label} page count outside B023 expectation: {pages}")
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
        "warnings": {"fatal": warnings, "overfull_hbox": len(re.findall(r"Overfull \\hbox", log))},
    }


def write_manifest() -> dict[str, Any]:
    inventory = common.source_inventory(SNAPSHOT)
    raw = "".join(f"{name}\t{size}\t{sha}\n" for name, size, sha in inventory.pop("rows")).encode("utf-8")
    MANIFEST.write_bytes(raw)
    return {**common.identity(MANIFEST), **inventory}


def reader_language_qa(text_path: Path, expected_pages: int) -> dict[str, Any]:
    raw_bytes = text_path.read_bytes()
    common.require(b"\r" not in raw_bytes, "reader-language QA received noncanonical CR text")
    raw = raw_bytes.decode("utf-8")
    pages = raw.split("\f")
    # pdftotext terminates every document with a form feed, creating one
    # structural empty tail after split.  Remove exactly that sentinel, never
    # a substantive page, and bind the remaining count to the PDF inventory.
    common.require(pages and pages[-1].strip() == "", "pdftotext terminal form-feed sentinel absent")
    pages.pop()
    common.require(
        len(pages) == expected_pages,
        f"pagewise text count differs from PDF pages: {len(pages)} != {expected_pages}",
    )
    normalized_pages = [re.sub(r"\s+", " ", page).strip() for page in pages]
    residual: dict[str, list[int]] = {}
    for phrase in FORBIDDEN_READER_ENGLISH:
        hits = [i + 1 for i, page in enumerate(normalized_pages) if phrase.casefold() in page.casefold()]
        if hits:
            residual[phrase] = hits
    common.require(not residual, f"untranslated/excluded English reached learner pages: {residual}")
    joined = " ".join(normalized_pages)
    required = (
        "Inferensi untuk data kategoris",
        "Selisih dua proporsi",
        "Uji hipotesis untuk selisih dua proporsi",
        "Lebih lanjut tentang uji hipotesis dua proporsi",
        "Solusi latihan",
        "nilai nol",
        "OpenAI Codex gpt-5.6-sol, Ultra",
    )
    missing = [phrase for phrase in required if phrase.casefold() not in joined.casefold()]
    common.require(not missing, f"accepted Indonesian B023 content absent: {missing}")
    return {
        "pages_checked": len(normalized_pages),
        "residual_english_by_phrase": residual,
        "required_phrases": list(required),
        "required_phrases_absent": missing,
        "pagewise_residual_pass": True,
    }


def self_test() -> dict[str, Any]:
    inputs = verify_inputs()
    common.require(not BUILD.exists(), "B023 build root already exists")
    staged = verify_staged_fragments()
    texts, transforms = prepare_custom_texts()
    tools = common.find_tools()
    # Do not write the candidate during self-test.
    previews = [memory_identity(common.rel(path), value) for path, value in texts.items()]
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
    common.require(not BUILD.exists(), "refusing to overwrite B023 build root")
    BUILD.mkdir(parents=True)
    shutil.copytree(SOURCE, SNAPSHOT)
    custom = make_custom_sources()
    manifest = write_manifest()
    tools = common.find_tools()
    seed = manifest["sha256"][:32].upper()
    run_a = build_once("replay-a", RUN_A, tools, seed)
    run_b = build_once("replay-b", RUN_B, tools, seed)
    common.require(run_a["pages"] == run_b["pages"], "B023 replay page counts differ")
    common.require(run_a["pdf"]["sha256"] == run_b["pdf"]["sha256"], "B023 replay PDFs differ")
    common.require(run_a["text"]["sha256"] == run_b["text"]["sha256"], "B023 replay text differs")
    common.require(run_a["trailer_ids"] == run_b["trailer_ids"], "B023 replay trailer IDs differ")
    FINAL.mkdir()
    shutil.copy2(RUN_A / "main.pdf", FINAL_PDF)
    shutil.copy2(RUN_A / "main-final.txt", FINAL_TEXT)
    language = reader_language_qa(FINAL_TEXT, run_a["pages"])
    receipt = {
        "$schema": "interlanguage.r011-b023-boundary-clean-reader-build/v1",
        "boundary_id": BOUNDARY_ID,
        "status": "PASS_TWO_REPLAY_DETERMINISTIC_BOUNDARY_CLEAN_BUILD_LANGUAGE_QA_VISUAL_QA_PENDING",
        "included_scope": (
            "Indonesian front matter and Chapters 1-5 through the admitted B022 boundary, "
            "plus Chapter 6 Sections 6.1 and 6.2; exercises 1-30; public answers 1,3,5,7,9,11,13,15,17,19,21,23,25,27,29."
        ),
        "excluded_untranslated_scope": [
            "Chapter 6 even answers 2,4,6,8,10,12,14,16,18,20,22,24,26,28,30 (O001 gaps)",
            "Chapter 6 Sections 6.3 onward and Chapters 7-9",
            "untranslated data/table/index appendices not visible in the admitted reader",
        ],
        "inputs": inputs,
        "staged": staged,
        "custom_sources": custom,
        "source_manifest": manifest,
        "replay_a": run_a,
        "replay_b": run_b,
        "determinism": {"pdf_byte_identical": True, "text_byte_identical": True, "trailer_ids_equal": True},
        "candidate_artifact": common.identity(FINAL_PDF),
        "candidate_text": common.identity(FINAL_TEXT),
        "page_count": run_a["pages"],
        "language_qa": language,
        "translation_provenance": MODEL,
        "next_cursor": {
            "boundary_id": "R011-B024",
            "path": "ch_inference_for_props/TeX/ch_inference_for_props.tex",
            "first_instructional_line": 1344,
            "first_instructional_label": "oneWayChiSquare",
        },
        "publication_performed": False,
        "git_used": False,
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
        raise SystemExit("usage: build_b023_boundary_clean_reader.py --self-test | --build")
    print(json.dumps({
        key: result[key]
        for key in ("boundary_id", "status", "page_count", "candidate_artifact", "source_manifest", "assembly_preview", "tools", "writes_performed")
        if key in result
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except common.GateError as exc:
        raise SystemExit(f"REFUSED: {exc}")
