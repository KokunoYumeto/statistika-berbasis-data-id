#!/usr/bin/env python3
"""Freeze and replay-verify the bounded R011-B025 source closure.

Reads only the pinned OpenIntro Statistics authority and the existing
component-rights inventory. Writes/verifies only the task-local B025 source
blueprint. It never translates or mutates the authority, live backend,
controls, reader outputs, releases, Git state, credentials, or network state.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path


LANE = Path(__file__).resolve().parents[1]
COMMIT = "fee25091fb24e89c36296fd67c48c1fcf7a93b6e"
TREE = "d61cc601e7d97759ce805900520f784d02a0489e"
AUTH_REL = Path("authority/upstream") / f"openintro-statistics-{COMMIT}"
AUTH = LANE / AUTH_REL

MAIN_REL = Path("main.tex")
CHAPTER_REL = Path("ch_inference_for_props/TeX/ch_inference_for_props.tex")
EXERCISE_REL = Path(
    "ch_inference_for_props/TeX/testing_for_independence_in_two-way_tables.tex"
)
ANSWER_REL = Path("extraTeX/eoceSolutions/eoceSolutions.tex")
BIB_REL = Path("eoce.bib")
STYLE_REL = Path("extraTeX/style/style.tex")
HEADERS_REL = Path("extraTeX/style/headers.tex")
CHI_TABLE_REL = Path("extraTeX/tables/TeX/chiSquareTable.tex")
DIFF_PROPS_REL = Path("ch_inference_for_props/TeX/difference_of_two_proportions.tex")
NEXT_CHAPTER_REL = Path("ch_inference_for_means/TeX/ch_inference_for_means.tex")
FIGURE_PDF_REL = Path(
    "ch_inference_for_props/figures/iPodChiSqTail/iPodChiSqTail.pdf"
)
FIGURE_R_REL = Path(
    "ch_inference_for_props/figures/iPodChiSqTail/iPodChiSqTail.R"
)

BLUEPRINT = LANE / "qa/b025-source/R011-B025_BOUNDARY_BLUEPRINT.json"

EXERCISES = [
    (35, 5, "quitters_chisq_independence"),
    (36, 30, "full_body_scan_chisq_indep"),
    (37, 63, "offshore_drilling_chisq_indep"),
    (38, 87, "parasitic_worm_chisq"),
]

LOCAL_LABELS = [
    "twoWayTablesAndChiSquare",
    "ipod_ask_data_summary",
    "iPodExComputeExpAA",
    "iPodExComputeExpBB",
    "ipod_ask_data_summary_expected",
    "iPodChiSqTail",
    "diabetes2ExpMetRosiLifestyleIntroExample",
    "diabetes2ExpMetRosiLifestyleSummary",
    "quitters_chisq_independence",
    "full_body_scan_chisq_indep",
    "offshore_drilling_chisq_indep",
    "parasitic_worm_chisq",
    "parasitic_worm_chisq_hyp",
]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def identity(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": sha256(data)}


def authority_path(rel: Path) -> str:
    return (AUTH_REL / rel).as_posix()


def exact_lines(path: Path) -> list[bytes]:
    data = path.read_bytes()
    if b"\r" in data:
        raise AssertionError(f"authority is not LF-normalized: {path}")
    return data.splitlines(keepends=True)


def slice_identity(path: Path, first: int, last: int) -> dict[str, object]:
    lines = exact_lines(path)
    if not (1 <= first <= last <= len(lines)):
        raise AssertionError((path, first, last, len(lines)))
    data = b"".join(lines[first - 1 : last])
    return {
        "first_line": first,
        "last_line": last,
        "logical_lines": last - first + 1,
        "bytes": len(data),
        "sha256": sha256(data),
    }


def manifest_rows() -> dict[str, dict[str, str]]:
    path = LANE / "authority/CORPUS_COMPONENT_CLOSURE.csv"
    with path.open("r", encoding="utf-8", newline="") as handle:
        return {row["path"]: row for row in csv.DictReader(handle)}


def component(rel: Path, rows: dict[str, dict[str, str]]) -> dict[str, object]:
    key = rel.as_posix()
    if key not in rows:
        raise AssertionError(f"component absent from rights closure: {key}")
    row = rows[key]
    disk = identity(AUTH / rel)
    if int(row["bytes"]) != disk["bytes"] or row["sha256"] != disk["sha256"]:
        raise AssertionError(f"component manifest drift: {key}")
    return {
        "path": authority_path(rel),
        "bytes": disk["bytes"],
        "sha256": disk["sha256"],
        "component_kind": row["component_kind"],
        "authored_generated_boundary": row["authored_generated_boundary"],
        "rights_resolution": row["rights_resolution"],
        "publication_disposition": row["publication_disposition"],
    }


def active_text(lines: list[bytes], first: int, last: int) -> str:
    selected = (line.decode("utf-8") for line in lines[first - 1 : last])
    return "".join(line for line in selected if not line.lstrip().startswith("%"))


def citation_slice(key: str, first: int, last: int) -> dict[str, object]:
    path = AUTH / BIB_REL
    result = slice_identity(path, first, last)
    text = b"".join(exact_lines(path)[first - 1 : last]).decode("utf-8")
    if "{" + key + "," not in text:
        raise AssertionError(f"citation key absent from declared slice: {key}")
    return {"key": key, "lines": f"{first}-{last} inclusive", **result}


def canonical_bytes(payload: dict[str, object]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def build_blueprint() -> dict[str, object]:
    authority = json.loads((LANE / "authority/UPSTREAM_AUTHORITY.json").read_text("utf-8"))
    if authority["commit"] != COMMIT or authority["calculated_git_tree_sha1"] != TREE:
        raise AssertionError("pinned authority identity drift")

    rows = manifest_rows()
    main = AUTH / MAIN_REL
    chapter = AUTH / CHAPTER_REL
    exercises = AUTH / EXERCISE_REL
    answers = AUTH / ANSWER_REL
    next_chapter = AUTH / NEXT_CHAPTER_REL
    main_lines = exact_lines(main)
    chapter_lines = exact_lines(chapter)
    exercise_lines = exact_lines(exercises)
    answer_lines = exact_lines(answers)
    next_lines = exact_lines(next_chapter)

    chapter_sentinels = {
        2007: r"%__________________",
        2008: r"\section{Testing for independence in two-way tables}",
        2009: r"\label{twoWayTablesAndChiSquare}",
        2296: (
            r"\includegraphics[width=0.65\textwidth]"
            r"{ch_inference_for_props/figures/iPodChiSqTail/iPodChiSqTail}"
        ),
        2431: r"\CalculatorVideos{the chi-square test for independence}",
        2434: (
            r"{\input{ch_inference_for_props/TeX/"
            r"testing_for_independence_in_two-way_tables.tex}}"
        ),
    }
    for number, expected in chapter_sentinels.items():
        actual = chapter_lines[number - 1].decode("utf-8").strip()
        if actual != expected:
            raise AssertionError(f"chapter sentinel drift at line {number}: {actual!r}")
    if len(chapter_lines) != 2434:
        raise AssertionError("chapter source line-count drift")
    if len(exercise_lines) != 127:
        raise AssertionError("B025 exercise source line-count drift")

    main_sentinels = {
        104: r"\includechapter{6}{ch_inference_for_props}",
        105: r"\includechapter{7}{ch_inference_for_means}",
    }
    for number, expected in main_sentinels.items():
        actual = main_lines[number - 1].decode("utf-8").strip()
        if actual != expected:
            raise AssertionError(f"book-order sentinel drift at main.tex:{number}")
    next_sentinels = {
        1: r"\begin{chapterpage}{Inference for numerical data}",
        2: r"\chaptertitle{Inference for numerical data}",
        3: r"\label{inferenceForNumericalData}",
        4: r"\label{ch_inference_for_means}",
        29: r"\section[One-sample means with the $t$-distribution]",
        32: r"\label{oneSampleMeansWithTDistribution}",
    }
    for number, expected in next_sentinels.items():
        actual = next_lines[number - 1].decode("utf-8").strip()
        if actual != expected:
            raise AssertionError(f"next-chapter sentinel drift at line {number}: {actual!r}")

    exercise_text = b"".join(exercise_lines).decode("utf-8")
    if exercise_text.count(r"\eoce{") != 4:
        raise AssertionError("expected exactly four B025 end-of-section exercises")
    for chapter_id, start_line, label in EXERCISES:
        if not exercise_lines[start_line - 1].decode("utf-8").lstrip().startswith(r"\eoce{"):
            raise AssertionError(f"exercise start drift for chapter ID {chapter_id}")
        window = b"".join(
            exercise_lines[start_line - 1 : min(start_line + 5, len(exercise_lines))]
        ).decode("utf-8")
        if rf"\label{{{label}}}" not in window:
            raise AssertionError(f"exercise label drift for chapter ID {chapter_id}")
        if exercise_lines[start_line - 3].decode("utf-8").strip() != f"% {chapter_id}":
            raise AssertionError(f"exercise chapter-ID comment drift: {chapter_id}")

    answer_slice_text = b"".join(answer_lines[1499:1543]).decode("utf-8")
    public_ids = [
        int(value) for value in re.findall(r"(?m)^% (\d+)\s*$", answer_slice_text)
    ]
    if public_ids != [35, 37]:
        raise AssertionError(f"public-answer IDs drift: {public_ids}")
    if answer_slice_text.count(r"\eocesol{") != 2:
        raise AssertionError("expected exactly two public odd answers")
    if answer_lines[1544].decode("utf-8").strip() != "% 39":
        raise AssertionError("post-B025 answer sentinel drift")

    body_active = active_text(chapter_lines, 2008, 2434)
    exercise_active = active_text(exercise_lines, 1, 127)
    actual_labels = re.findall(r"\\label\{([^{}]+)\}", body_active + exercise_active)
    if actual_labels != LOCAL_LABELS:
        raise AssertionError(f"local-label sequence drift: {actual_labels}")
    if re.findall(r"\\footfullcite\{([^{}]+)\}", exercise_active) != [
        "King_Suamani_2018"
    ]:
        raise AssertionError("B025 citation sequence drift")
    if re.findall(r"\\includegraphics(?:\[[^]]*\])?\{([^{}]+)\}", body_active) != [
        "ch_inference_for_props/figures/iPodChiSqTail/iPodChiSqTail"
    ]:
        raise AssertionError("B025 external-asset call sequence drift")

    refs = re.findall(r"\\(?:ref|pageref)\{([^{}]+)\}", body_active + exercise_active)
    external_ref_targets = [
        target
        for target in [
            "differenceOfTwoProportions",
            "chiSquareProbabilityTable",
            "full_body_scan_HT_Error",
            "offshore_drill_edu_dontknow_HT",
        ]
        if target in refs
    ]
    if external_ref_targets != [
        "differenceOfTwoProportions",
        "chiSquareProbabilityTable",
        "full_body_scan_HT_Error",
        "offshore_drill_edu_dontknow_HT",
    ]:
        raise AssertionError(f"external-reference closure drift: {external_ref_targets}")

    producer = (AUTH / FIGURE_R_REL).read_text("utf-8")
    for required in [
        "chisq.test(table(ask[2:3]))",
        "ChiSquareTail(x, 2",
        "Tail area (1 / 500 million)\\nis too small to see",
    ]:
        if required not in producer:
            raise AssertionError(f"iPod producer sentinel drift: {required}")
    if "read.csv" in producer or "read.table" in producer:
        raise AssertionError("unexpected standalone-data dependency in iPod producer")

    if "\\iPodBD{}/\\iPodDD{}" not in chapter_lines[2210].decode("utf-8"):
        raise AssertionError("known expected-fraction numerator issue drift")
    row3_first = 233 * 319 / 699
    row3_second = 233 * 380 / 699
    if round(row3_first, 1) != 106.3 or round(row3_second, 1) != 126.7:
        raise AssertionError("diabetes expected-value recomputation drift")

    chunks = [
        (
            2008,
            2116,
            "Section opening, iPod experiment, observed table, and independence question.",
        ),
        (
            2117,
            2238,
            "Expected counts for two-way tables, worked example, guided practice, and formula.",
        ),
        (
            2239,
            2329,
            "Two-way chi-square statistic, degrees of freedom, p-value, and iPod conclusion.",
        ),
        (
            2330,
            2434,
            "Diabetes example and guided exercises, calculator-video marker, and exercise input.",
        ),
    ]

    corrections = [
        {
            "location": "ch_inference_for_props/TeX/ch_inference_for_props.tex:2068-2071",
            "confidence": "high",
            "source_issue": (
                "The sentence contains a stray article/comma ('asking the, What problems...') "
                "and an ungrammatical construction around the quoted question."
            ),
            "translation_action": (
                "State directly that asking 'What problems does it have?' was most effective; "
                "leave authority unchanged."
            ),
        },
        {
            "location": "ch_inference_for_props/TeX/ch_inference_for_props.tex:2093-2094",
            "confidence": "high",
            "source_issue": (
                "The figure caption ends mid-clause: 'where a question was posed to the study "
                "participant who acted'."
            ),
            "translation_action": (
                "Complete the evidenced role as the participant acting as the seller; leave "
                "authority unchanged."
            ),
        },
        {
            "location": "ch_inference_for_props/TeX/ch_inference_for_props.tex:2108-2114",
            "confidence": "high",
            "source_issue": (
                "The hypothesis-test sentence lacks the predicate that says whether question "
                "success differed and is not grammatically complete."
            ),
            "translation_action": (
                "Express the intended independence question: whether disclosure depends on the "
                "buyer question; leave authority unchanged."
            ),
        },
        {
            "location": "ch_inference_for_props/TeX/ch_inference_for_props.tex:2209-2212",
            "confidence": "high",
            "source_issue": (
                "The disclosed-seller fraction 0.2785 is described as iPodBD/iPodDD = 158/219, "
                "which equals 0.7215. The correct numerator is iPodAD = 61."
            ),
            "translation_action": (
                "Use iPodAD/iPodDD = 61/219 for the disclosed fraction while preserving all "
                "stable macro and cross-reference identities."
            ),
        },
        {
            "location": "ch_inference_for_props/TeX/ch_inference_for_props.tex:2261",
            "confidence": "high",
            "source_issue": (
                "The prose has number agreement and hyphenation errors ('degrees of freedom "
                "was'; 'two way tables')."
            ),
            "translation_action": "Render the intended statements grammatically in Indonesian.",
        },
        {
            "location": "ch_inference_for_props/TeX/ch_inference_for_props.tex:2303-2305",
            "confidence": "high",
            "source_issue": "The possessive apostrophe is missing in 'the sellers likelihood'.",
            "translation_action": "Render the intended seller-likelihood phrase naturally.",
        },
        {
            "location": (
                "ch_inference_for_props/TeX/"
                "testing_for_independence_in_two-way_tables.tex:92-94"
            ),
            "confidence": "high",
            "source_issue": "The phrase 'clear people of the this parasite' has a duplicated article.",
            "translation_action": "Render the intended parasite-clearance statement grammatically.",
        },
        {
            "location": "extraTeX/eoceSolutions/eoceSolutions.tex:1527-1531",
            "confidence": "high",
            "source_issue": (
                "The public answer has subject-verb disagreement: plural 'Opinions' is paired "
                "with 'has an association'."
            ),
            "translation_action": "Render the alternative hypothesis grammatically without changing it.",
        },
    ]

    payload: dict[str, object] = {
        "$schema": "interlanguage.r011-boundary-blueprint/v1",
        "boundary_id": "R011-B025",
        "status": "PASS_SOURCE_ASSET_DATA_RIGHTS_AND_BOOK_ORDER_DEPENDENCY_CLOSURE",
        "provenance": {
            "production_model": "OpenAI Codex gpt-5.6-sol, Ultra",
            "role": "bounded source-closure analysis; no translation or publication performed",
        },
        "authority": {
            "repository": "https://github.com/OpenIntroStat/openintro-statistics",
            "branch_observed": "master",
            "commit": COMMIT,
            "tree": TREE,
            "observed": "2026-08-20",
            "reader_witness": "https://www.openintro.org/book/os/",
        },
        "book_order_witness": {
            "main_source": {**component(MAIN_REL, rows)},
            "current_chapter_include": {
                "line": 104,
                "text": r"\includechapter{6}{ch_inference_for_props}",
                "slice": slice_identity(main, 104, 104),
            },
            "next_chapter_include": {
                "line": 105,
                "text": r"\includechapter{7}{ch_inference_for_means}",
                "slice": slice_identity(main, 105, 105),
            },
        },
        "main_source": {
            **component(CHAPTER_REL, rows),
            "file_line_count": len(chapter_lines),
            "start_line": 2008,
            "start_label": "twoWayTablesAndChiSquare",
            "start_label_line": 2009,
            "end_line": 2434,
            "title": "Testing for independence in two-way tables",
            "slice": slice_identity(chapter, 2008, 2434),
            "source_file_ends_at_boundary": True,
            "post_section_spacer": None,
        },
        "translation_chunks": [
            {
                "path": authority_path(CHAPTER_REL),
                **slice_identity(chapter, first, last),
                "coverage": coverage,
            }
            for first, last, coverage in chunks
        ],
        "exercise_answer_closure": {
            "chapter_exercise_ids": [35, 36, 37, 38],
            "exercise_records": [
                {"chapter_id": chapter_id, "start_line": start, "label": label}
                for chapter_id, start, label in EXERCISES
            ],
            "exercise_source": {
                **component(EXERCISE_REL, rows),
                "lines": "1-127 inclusive (full file)",
                "slice": slice_identity(exercises, 1, 127),
            },
            "exercise_translation_chunks": [
                {
                    "path": authority_path(EXERCISE_REL),
                    **slice_identity(exercises, 1, 59),
                    "chapter_ids": [35, 36],
                },
                {
                    "path": authority_path(EXERCISE_REL),
                    **slice_identity(exercises, 60, 127),
                    "chapter_ids": [37, 38],
                },
            ],
            "public_answer_ids": public_ids,
            "public_answer_source": {
                **component(ANSWER_REL, rows),
                "lines": "1500-1543 inclusive",
                "slice": slice_identity(answers, 1500, 1543),
                "layout_lines_inside_slice": "1521-1523 close/reopen the two-column environment",
            },
            "public_answer_translation_chunks": [
                {
                    "path": authority_path(ANSWER_REL),
                    **slice_identity(answers, 1500, 1519),
                    "chapter_ids": [35],
                },
                {
                    "path": authority_path(ANSWER_REL),
                    **slice_identity(answers, 1521, 1543),
                    "chapter_ids": [37],
                    "includes_layout_lines": True,
                },
            ],
            "o001_gap_ids": [36, 38],
            "restricted_solutions_accessed_or_invented": False,
        },
        "figure_asset_closure": [
            {
                **component(FIGURE_PDF_REL, rows),
                "active_call_line": 2296,
                "producer": {
                    **component(FIGURE_R_REL, rows),
                    "runtime_dependency": (
                        "openintro R package: ask data object, COL palette, myPDF, and "
                        "ChiSquareTail; no standalone data file is loaded"
                    ),
                    "analysis_expression": "chisq.test(table(ask[2:3]))$statistic",
                },
                "reader_visible_strings_from_producer": [
                    "Tail area (1 / 500 million)",
                    "is too small to see",
                    "0",
                    "10",
                    "20",
                    "30",
                    "40",
                    "50",
                ],
                "content_localization_required": True,
                "required_localization": (
                    "Regenerate or safely relabel the two-line tail-area annotation in "
                    "Indonesian while preserving X^2=40.13, df=2, the tail geometry, and axes."
                ),
                "alt_caption_localization_required": True,
            }
        ],
        "inline_tex_visuals": {
            "main_source_tabular_count": body_active.count(r"\begin{tabular}"),
            "main_source_figure_environment_count": body_active.count(r"\begin{figure}"),
            "exercise_source_tabular_count": exercise_active.count(r"\begin{tabular}"),
            "exercise_source_external_asset_count": len(
                re.findall(r"\\includegraphics|\\Figures?\[", exercise_active)
            ),
            "public_answer_slice_tabular_count": answer_slice_text.count(r"\begin{tabular}"),
            "localization_policy": (
                "Translate TeX captions, headers, cells, annotations, and alt text while "
                "preserving counts, formulas, table structure, labels, cross-references, "
                "study attribution, and numerical meaning."
            ),
        },
        "data_code_closure": {
            "standalone_dataset_input": False,
            "producer_scripts": 1,
            "committed_generated_pdfs": 1,
            "runtime_package_data": {
                "object": "ask",
                "package": "openintro",
                "usage": "table(ask[2:3]) supplies the iPod chi-square statistic",
                "frozen_standalone_bytes_in_authority": False,
                "reader_reproduction_note": (
                    "The committed figure PDF is the frozen reader byte witness; the main "
                    "TeX independently freezes the 2x3 iPod counts and X^2=40.13."
                ),
            },
            "embedded_values": (
                "The iPod 2x3 observed and expected counts, diabetes 3x2 counts, chi-square "
                "statistics, degrees of freedom, and p-values are embedded in TeX."
            ),
            "external_report_bytes_required": False,
        },
        "citations": {
            "full_bibliography": {**component(BIB_REL, rows)},
            "unique_keys": ["King_Suamani_2018"],
            "slices": [citation_slice("King_Suamani_2018", 824, 831)],
            "required_external_bytes": False,
            "policy": (
                "Retain the cited study's authors, title, journal, volume, pages, year, and "
                "redirect provenance; do not claim independent relicensing of study wording."
            ),
        },
        "cross_reference_dependency_closure": {
            "local_labels": LOCAL_LABELS,
            "external_targets": [
                {
                    **component(CHAPTER_REL, rows),
                    "label": "differenceOfTwoProportions",
                    "label_line": 556,
                    "label_slice": slice_identity(chapter, 556, 556),
                },
                {
                    **component(CHI_TABLE_REL, rows),
                    "label": "chiSquareProbabilityTable",
                    "label_line": 2,
                    "label_slice": slice_identity(AUTH / CHI_TABLE_REL, 2, 2),
                },
                {
                    **component(DIFF_PROPS_REL, rows),
                    "label": "full_body_scan_HT_Error",
                    "label_line": 262,
                    "label_slice": slice_identity(AUTH / DIFF_PROPS_REL, 262, 262),
                },
                {
                    **component(DIFF_PROPS_REL, rows),
                    "label": "offshore_drill_edu_dontknow_HT",
                    "label_line": 176,
                    "label_slice": slice_identity(AUTH / DIFF_PROPS_REL, 176, 176),
                },
            ],
            "internal_reference_targets": [
                "ipod_ask_data_summary",
                "iPodExComputeExpAA",
                "iPodExComputeExpBB",
                "ipod_ask_data_summary_expected",
                "iPodChiSqTail",
                "diabetes2ExpMetRosiLifestyleIntroExample",
                "diabetes2ExpMetRosiLifestyleSummary",
                "parasitic_worm_chisq_hyp",
            ],
        },
        "macro_dependency_closure": [
            {
                **component(STYLE_REL, rows),
                "role": (
                    "D, response, onebox, example, guided-practice, exercise/solution, "
                    "CalculatorVideos, includegraphics, redirect, and layout macros"
                ),
            },
            {
                **component(HEADERS_REL, rows),
                "role": "end-of-section exercise heading macro",
            },
        ],
        "rights": {
            "repository_text_generated_figures_and_code": (
                "CC BY-SA 3.0 repository declaration with source attribution, share-alike "
                "derivative notice, novel derivative title, and no OpenIntro branding/logo."
            ),
            "cited_medical_study": (
                "Bibliographic facts and attributed study description are retained; no "
                "external article bytes are incorporated and no independent relicensing is claimed."
            ),
            "runtime_openintro_package_data": (
                "The producer references the openintro package's ask object; no standalone "
                "data file enters this boundary. Preserve this runtime provenance."
            ),
            "component_rights_override": True,
            "external_facts_and_quotations": "retain explicit attribution; do not claim independent relicensing",
            "branding_excluded": True,
            "new_unresolved_binary_dependency": False,
        },
        "correction_candidates": corrections,
        "production_closure": {
            "main_source_lines": 427,
            "exercise_source_lines": 127,
            "public_answer_source_lines": 44,
            "subsections": len(re.findall(r"(?m)^\\subsection", body_active)),
            "worked_examples": body_active.count(r"\begin{nexample}"),
            "guided_exercises": body_active.count(r"\begin{nexercise}"),
            "end_of_section_exercises": 4,
            "public_answers": 2,
            "o001_gaps": 2,
            "external_asset_calls": 1,
            "distinct_binary_assets": 1,
            "figure_producer_scripts": 1,
            "standalone_data_files": 0,
            "bibliography_keys": 1,
            "high_confidence_source_corrections": len(corrections),
        },
        "post_boundary_cursor": {
            "book_order_source": authority_path(MAIN_REL),
            "book_order_current_include_line": 104,
            "book_order_next_include_line": 105,
            "path": authority_path(NEXT_CHAPTER_REL),
            "line": 1,
            "chapter_title": "Inference for numerical data",
            "chapter_label": "ch_inference_for_means",
            "chapter_label_line": 4,
            "first_section_line": 29,
            "first_section_title": "One-sample means with the t-distribution",
            "first_section_label": "oneSampleMeansWithTDistribution",
            "first_section_label_line": 32,
            "working_boundary_id": "R011-B026",
            "next_source_component": {**component(NEXT_CHAPTER_REL, rows)},
            "chapter_opening_slice": slice_identity(next_chapter, 1, 32),
        },
        "scope_guards": {
            "translation_performed": False,
            "canonical_source_mutated": False,
            "live_backend_mutated": False,
            "output_or_control_mutated": False,
            "release_or_publication_mutated": False,
            "cursor_advanced": False,
            "network_used": False,
            "git_used": False,
            "credentials_accessed": False,
            "upstream_contact": False,
        },
    }

    expected_counts = {
        "subsections": 2,
        "worked_examples": 3,
        "guided_exercises": 4,
    }
    for key, expected in expected_counts.items():
        actual = payload["production_closure"][key]
        if actual != expected:
            raise AssertionError(f"production count drift for {key}: {actual}")
    if payload["inline_tex_visuals"] != {
        "main_source_tabular_count": 3,
        "main_source_figure_environment_count": 4,
        "exercise_source_tabular_count": 3,
        "exercise_source_external_asset_count": 0,
        "public_answer_slice_tabular_count": 1,
        "localization_policy": payload["inline_tex_visuals"]["localization_policy"],
    }:
        raise AssertionError("inline-visual topology drift")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--verify", action="store_true")
    mode.add_argument("--self-check", action="store_true")
    args = parser.parse_args()

    first = canonical_bytes(build_blueprint())
    second = canonical_bytes(build_blueprint())
    if first != second:
        raise AssertionError("in-process deterministic replay mismatch")

    if args.write:
        BLUEPRINT.parent.mkdir(parents=True, exist_ok=True)
        BLUEPRINT.write_bytes(first)
    elif args.verify:
        if not BLUEPRINT.exists() or BLUEPRINT.read_bytes() != first:
            raise AssertionError("frozen B025 blueprint differs from exact replay")

    output = {
        "status": "PASS_EXACT_REPLAY_R011_B025_SOURCE_CLOSURE",
        "mode": "write" if args.write else "verify" if args.verify else "self-check",
        "blueprint": {
            "path": str(BLUEPRINT),
            "bytes": len(first),
            "sha256": sha256(first),
            "on_disk_exact": BLUEPRINT.exists() and BLUEPRINT.read_bytes() == first,
        },
        "boundary": {"start_line": 2008, "end_line": 2434, "source_file_end": 2434},
        "exercise_ids": [35, 36, 37, 38],
        "public_answer_ids": [35, 37],
        "o001_gap_ids": [36, 38],
        "binary_assets": 1,
        "producer_scripts": 1,
        "data_files": 0,
        "post_boundary_cursor": {
            "path": authority_path(NEXT_CHAPTER_REL),
            "line": 1,
            "first_section_line": 29,
            "first_section_label_line": 32,
        },
        "scope": "read-only pinned authority plus qa/b025-source blueprint only",
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
