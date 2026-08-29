#!/usr/bin/env python3
"""Freeze and replay-verify the bounded R011-B024 source closure.

This helper reads only the pinned OpenIntro Statistics authority and the
component-rights inventory, and writes/verifies only the task-local B024
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

CHAPTER_REL = Path("ch_inference_for_props/TeX/ch_inference_for_props.tex")
EXERCISE_REL = Path(
    "ch_inference_for_props/TeX/testing_for_goodness_of_fit_using_chi-square.tex"
)
ANSWER_REL = Path("extraTeX/eoceSolutions/eoceSolutions.tex")
BIB_REL = Path("eoce.bib")
STYLE_REL = Path("extraTeX/style/style.tex")
HEADERS_REL = Path("extraTeX/style/headers.tex")
CHI_TABLE_REL = Path("extraTeX/tables/TeX/chiSquareTable.tex")
DISTRIBUTIONS_REL = Path("ch_distributions/TeX/ch_distributions.tex")

FIGURE_ROOT = Path("ch_inference_for_props/figures")
CHI_DF_PDF_REL = FIGURE_ROOT / (
    "chiSquareDistributionWithInceasingDF/chiSquareDistributionWithInceasingDF.pdf"
)
CHI_DF_R_REL = FIGURE_ROOT / (
    "chiSquareDistributionWithInceasingDF/chiSquareDistributionWithInceasingDF.R"
)

TAIL_FIGURES = [
    (
        "chiSquareAreaAbove6Point25WithDF3",
        "chiSquareAreaAbove6Point25WithDF3.R",
        1540,
        ["0", "5", "10", "15"],
    ),
    (
        "chiSquareAreaAbove4Point3WithDF2",
        "chiSquareAreaAbove4WithDF2.R",
        1544,
        ["0", "5", "10", "15"],
    ),
    (
        "chiSquareAreaAbove5Point1WithDF5",
        "chiSquareAreaAbove5Point1WithDF5.R",
        1548,
        ["0", "5", "10", "15", "20", "25"],
    ),
    (
        "chiSquareAreaAbove11Point7WithDF7",
        "chiSquareAreaAbove11Point7WithDF7.R",
        1552,
        ["0", "5", "10", "15", "20", "25"],
    ),
    (
        "chiSquareAreaAbove10WithDF4",
        "chiSquareAreaAbove10WithDF4.R",
        1556,
        ["0", "5", "10", "15"],
    ),
    (
        "chiSquareAreaAbove9Point21WithDF3",
        "chiSquareAreaAbove9Point21WithDF3.R",
        1560,
        ["0", "5", "10", "15"],
    ),
]

JUROR_PDF_REL = FIGURE_ROOT / "jurorHTPValueShown/jurorHTPValueShown.pdf"
JUROR_R_REL = FIGURE_ROOT / "jurorHTPValueShown/jurorHTPValueShown.R"
GEOM_PLOT_PDF_REL = FIGURE_ROOT / (
    "geomFitEvaluationForSP500/geomFitEvaluationForSP500.pdf"
)
GEOM_PLOT_R_REL = FIGURE_ROOT / (
    "geomFitEvaluationForSP500/geomFitEvaluationForSP500.R"
)
SP500_DATA_REL = FIGURE_ROOT / "geomFitEvaluationForSP500/sp500_1950_2018.csv"
GEOM_P_PDF_REL = FIGURE_ROOT / "geomFitPValueForSP500/geomFitPValueForSP500.pdf"
GEOM_P_R_REL = FIGURE_ROOT / "geomFitPValueForSP500/geomFitPValueForSP500.R"
BARKING_DEER_REL = FIGURE_ROOT / "eoce/barking_deer_chisq_GOF/barking_deer.jpg"

BLUEPRINT = LANE / "qa/b024-source/R011-B024_BOUNDARY_BLUEPRINT.json"

EXERCISES = [
    (31, 5, "tf_chisq_1"),
    (32, 21, "tf_chisq_2"),
    (33, 38, "opensource_text_chisq_GOF"),
    (34, 61, "barking_deer_chisq_GOF"),
]

LOCAL_LABELS = [
    "oneWayChiSquare",
    "juryRepresentationAndCityRepresentationForRace",
    "expectedJuryRepresentationIfNoBias",
    "chiSquareTestStatistic",
    "exerChiSquareDistributionDescriptionWithMoreDOF",
    "chiSquareDistributionWithInceasingDF",
    "chiSquareAreaAbove6Point25WithDF3",
    "chiSquareAreaAbove4Point3WithDF2",
    "chiSquareAreaAbove5Point1WithDF5",
    "chiSquareAreaAbove11Point7WithDF7",
    "chiSquareAreaAbove10WithDF4",
    "chiSquareAreaAbove9Point21WithDF3",
    "arrayOfFigureAreasForChiSquareDistribution",
    "pValueForAChiSquareTest",
    "jurorHTPValueShown",
    "sAndP500TimeToPosTrade",
    "sAndP500TimeToPosTrade2",
    "geomFitEvaluationForSP500",
    "DNRejectGeomModelForSP500",
    "geomFitPValueForSP500",
    *[label for _, _, label in EXERCISES],
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


def citation_slice(key: str, first: int, last: int) -> dict[str, object]:
    path = AUTH / BIB_REL
    result = slice_identity(path, first, last)
    text = b"".join(exact_lines(path)[first - 1 : last]).decode("utf-8")
    if "{" + key + "," not in text:
        raise AssertionError(f"citation key absent from declared slice: {key}")
    return {"key": key, "lines": f"{first}-{last} inclusive", **result}


def canonical_bytes(payload: dict[str, object]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def active_text(lines: list[bytes], first: int, last: int) -> str:
    selected = (line.decode("utf-8") for line in lines[first - 1 : last])
    return "".join(line for line in selected if not line.lstrip().startswith("%"))


def tail_asset(
    stem: str,
    producer_name: str,
    call_line: int,
    visible_strings: list[str],
    rows: dict[str, dict[str, str]],
) -> dict[str, object]:
    directory = FIGURE_ROOT / "arrayOfFigureAreasForChiSquareDistribution" / stem
    pdf_rel = directory / f"{stem}.pdf"
    r_rel = directory / producer_name
    return {
        **component(pdf_rel, rows),
        "active_call_line": call_line,
        "producer": {
            **component(r_rel, rows),
            "runtime_dependency": (
                "openintro R package (COL palette, myPDF, and ChiSquareTail); "
                "no standalone data file is loaded"
            ),
        },
        "reader_visible_strings": visible_strings,
        "content_localization_required": False,
        "alt_caption_localization_required": True,
    }


def build_blueprint() -> dict[str, object]:
    authority = json.loads((LANE / "authority/UPSTREAM_AUTHORITY.json").read_text("utf-8"))
    if authority["commit"] != COMMIT or authority["calculated_git_tree_sha1"] != TREE:
        raise AssertionError("pinned authority identity drift")

    rows = manifest_rows()
    chapter = AUTH / CHAPTER_REL
    exercises = AUTH / EXERCISE_REL
    answers = AUTH / ANSWER_REL
    chapter_lines = exact_lines(chapter)
    exercise_lines = exact_lines(exercises)
    answer_lines = exact_lines(answers)

    sentinels = {
        1343: r"%__________________",
        1344: r"\section{Testing for goodness of fit using chi-square}",
        1345: r"\label{oneWayChiSquare}",
        2001: r"{\input{ch_inference_for_props/TeX/testing_for_goodness_of_fit_using_chi-square.tex}}",
        2007: r"%__________________",
        2008: r"\section{Testing for independence in two-way tables}",
        2009: r"\label{twoWayTablesAndChiSquare}",
    }
    for number, expected in sentinels.items():
        actual = chapter_lines[number - 1].decode("utf-8").strip()
        if actual != expected:
            raise AssertionError(f"chapter sentinel drift at line {number}: {actual!r}")

    if len(chapter_lines) != 2434:
        raise AssertionError("chapter source line-count drift")
    if len(exercise_lines) != 99:
        raise AssertionError("B024 exercise source line-count drift")
    exercise_text = b"".join(exercise_lines).decode("utf-8")
    if exercise_text.count(r"\eoce{") != 4:
        raise AssertionError("expected exactly four B024 exercises")
    for chapter_id, start_line, label in EXERCISES:
        if not exercise_lines[start_line - 1].decode("utf-8").lstrip().startswith(r"\eoce{"):
            raise AssertionError(f"exercise start drift for chapter ID {chapter_id}")
        window = b"".join(
            exercise_lines[start_line - 1 : min(start_line + 4, len(exercise_lines))]
        ).decode("utf-8")
        if rf"\label{{{label}}}" not in window:
            raise AssertionError(f"exercise label drift for chapter ID {chapter_id}")
        if exercise_lines[start_line - 3].decode("utf-8").strip() != f"% {chapter_id}":
            raise AssertionError(f"exercise chapter-ID comment drift: {chapter_id}")

    public_answer_text = b"".join(answer_lines[1473:1498]).decode("utf-8")
    public_ids = [
        int(value) for value in re.findall(r"(?m)^% (\d+)\s*$", public_answer_text)
    ]
    if public_ids != [31, 33]:
        raise AssertionError(f"public-answer IDs drift: {public_ids}")
    if public_answer_text.count(r"\eocesol{") != 2:
        raise AssertionError("expected exactly two public odd answers")
    if answer_lines[1499].decode("utf-8").strip() != "% 35":
        raise AssertionError("post-B024 answer sentinel drift")

    body_active = active_text(chapter_lines, 1344, 2001)
    exercise_active = active_text(exercise_lines, 1, 99)
    actual_labels = re.findall(r"\\label\{([^{}]+)\}", body_active + exercise_active)
    if actual_labels != LOCAL_LABELS:
        raise AssertionError(f"local-label sequence drift: {actual_labels}")
    if re.findall(r"\\footfullcite\{([^{}]+)\}", exercise_active) != ["Teng:2004"]:
        raise AssertionError("B024 citation sequence drift")

    expected_asset_calls = {
        1497: "chiSquareDistributionWithInceasingDF",
        1540: "chiSquareAreaAbove6Point25WithDF3",
        1544: "chiSquareAreaAbove4Point3WithDF2",
        1548: "chiSquareAreaAbove5Point1WithDF5",
        1552: "chiSquareAreaAbove11Point7WithDF7",
        1556: "chiSquareAreaAbove10WithDF4",
        1560: "chiSquareAreaAbove9Point21WithDF3",
        1683: "jurorHTPValueShown",
        1882: "geomFitEvaluationForSP500",
        1972: "geomFitPValueForSP500",
    }
    for number, stem in expected_asset_calls.items():
        line = chapter_lines[number - 1].decode("utf-8").strip()
        if not line.startswith((r"\Figure[", r"\Figures[")) or stem not in line:
            raise AssertionError(f"asset-call drift at chapter line {number}")
    exercise_asset_line = exercise_lines[94].decode("utf-8").strip()
    if not exercise_asset_line.startswith(r"\Figures[") or "barking_deer" not in exercise_asset_line:
        raise AssertionError("barking-deer asset-call drift at exercise line 95")
    if len(re.findall(r"\\Figures?\[", body_active)) != 10:
        raise AssertionError("active chapter external-asset count drift")
    if len(re.findall(r"\\Figures?\[", exercise_active)) != 1:
        raise AssertionError("active exercise external-asset count drift")

    chi_df_r = (AUTH / CHI_DF_R_REL).read_text("utf-8")
    geom_plot_r = (AUTH / GEOM_PLOT_R_REL).read_text("utf-8")
    geom_p_r = (AUTH / GEOM_P_R_REL).read_text("utf-8")
    for text, required in [
        (chi_df_r, "Degrees of Freedom"),
        (geom_plot_r, "Wait Until Positive Day"),
        (geom_plot_r, "Frequency"),
        (geom_plot_r, "Observed"),
        (geom_plot_r, "Expected"),
        (geom_p_r, "Area representing\\nthe p-value"),
    ]:
        if required not in text:
            raise AssertionError(f"producer-visible-string drift: {required}")
    for required in [
        '"2009-01-01" <= as.Date(Date)',
        'as.Date(Date) <= "2018-12-31"',
        "EE <- round(pr * sum(CC))",
        "pchisq(X2, length(CC) - 1, lower.tail = FALSE)",
    ]:
        if required not in geom_plot_r:
            raise AssertionError(f"S&P producer sentinel drift: {required}")
    for required in ("Photo by Shrikant Rao", "CC~BY~2.0~license"):
        if required not in exercise_active:
            raise AssertionError("barking-deer attribution drift")

    chunks = [
        (
            1344,
            1471,
            "Section opening, juror-representation setup, and construction of the chi-square test statistic.",
        ),
        (
            1472,
            1633,
            "Chi-square distribution, degrees of freedom, tail areas, examples, and guided practice.",
        ),
        (
            1634,
            1763,
            "Juror-test p-value, one-way chi-square framework, conditions, and two-bin guidance.",
        ),
        (
            1764,
            1887,
            "Goodness-of-fit setup for the geometric model of S&P 500 waiting times.",
        ),
        (
            1888,
            2001,
            "S&P 500 chi-square calculation, conclusion, figures, and Section 6.3 exercise input.",
        ),
    ]

    figure_assets: list[dict[str, object]] = [
        {
            **component(CHI_DF_PDF_REL, rows),
            "active_call_line": 1497,
            "producer": {
                **component(CHI_DF_R_REL, rows),
                "runtime_dependency": (
                    "openintro R package (COL palette and myPDF) plus base-R dchisq; "
                    "no standalone data file is loaded"
                ),
            },
            "reader_visible_strings_from_producer": ["Degrees of Freedom", "2", "4", "9"],
            "content_localization_required": True,
            "required_localization": (
                "Regenerate or safely relabel 'Degrees of Freedom' as 'Derajat kebebasan' "
                "while preserving curves, line encodings, and numerical axes."
            ),
            "alt_caption_localization_required": True,
        },
        *[
            tail_asset(stem, producer, call_line, strings, rows)
            for stem, producer, call_line, strings in TAIL_FIGURES
        ],
        {
            **component(JUROR_PDF_REL, rows),
            "active_call_line": 1683,
            "producer": {
                **component(JUROR_R_REL, rows),
                "runtime_dependency": (
                    "openintro R package (COL palette, myPDF, and ChiSquareTail); "
                    "no standalone data file is loaded"
                ),
            },
            "reader_visible_strings": ["0", "5", "10", "15"],
            "content_localization_required": False,
            "alt_caption_localization_required": True,
        },
        {
            **component(GEOM_PLOT_PDF_REL, rows),
            "active_call_line": 1882,
            "producer": {
                **component(GEOM_PLOT_R_REL, rows),
                "runtime_dependency": (
                    "openintro R package (sp500_1950_2018 object, COL palette, myPDF, and "
                    "histPlot); adjacent CSV is the frozen data witness"
                ),
                "data": component(SP500_DATA_REL, rows),
            },
            "reader_visible_strings": [
                "Observed",
                "Expected",
                "Frequency",
                "Wait Until Positive Day",
                "1",
                "2",
                "3",
                "4",
                "5",
                "6",
                "7+",
            ],
            "content_localization_required": True,
            "required_localization": (
                "Regenerate with Indonesian axis and legend labels while retaining exact "
                "observed/expected values and geometry."
            ),
            "alt_caption_localization_required": True,
        },
        {
            **component(GEOM_P_PDF_REL, rows),
            "active_call_line": 1972,
            "producer": {
                **component(GEOM_P_R_REL, rows),
                "runtime_dependency": (
                    "openintro R package (COL palette, myPDF, and ChiSquareTail); "
                    "no standalone data file is loaded"
                ),
            },
            "reader_visible_strings": ["Area representing the p-value", "0", "5", "10", "15", "20", "25"],
            "content_localization_required": True,
            "required_localization": (
                "Regenerate or safely relabel the p-value annotation in Indonesian while "
                "retaining the cutoff, shaded area, and axes."
            ),
            "alt_caption_localization_required": True,
        },
        {
            **component(BARKING_DEER_REL, rows),
            "active_exercise_call_line": 95,
            "photographer": "Shrikant Rao",
            "source_redirect_key": "textbook-flickr_shrikant_rao_barking_deer",
            "source_url_in_authority": "http://flic.kr/p/4Xjdkk",
            "license": "CC BY 2.0",
            "content_localization_required": False,
            "alt_caption_and_attribution_localization_required": True,
            "attribution_must_be_preserved": True,
        },
    ]

    corrections = [
        {
            "location": "ch_inference_for_props/TeX/ch_inference_for_props.tex:1376",
            "confidence": "high",
            "source_issue": (
                "The opening says the S&P 500 analysis covers 25 years, but the section "
                "defines spyears=10 and the producer selects 2009-01-01 through 2018-12-31."
            ),
            "translation_action": "State the evidenced ten-year interval; leave authority unchanged.",
        },
        {
            "location": "ch_inference_for_props/TeX/ch_inference_for_props.tex:1435",
            "confidence": "high",
            "source_issue": (
                "The footnote calls np(1-p) a standard error; it is the binomial variance. "
                "The corresponding standard error is sqrt(np(1-p))."
            ),
            "translation_action": (
                "Name np(1-p) as the variance or write sqrt(np(1-p)) for the standard error; "
                "preserve the intended Pearson-statistic explanation."
            ),
        },
        {
            "location": "ch_inference_for_props/TeX/ch_inference_for_props.tex:1478",
            "confidence": "high",
            "source_issue": "Tense error: 'Recall a normal distribution had two parameters'.",
            "translation_action": "Use the intended present-tense statement; leave authority unchanged.",
        },
        {
            "location": "ch_inference_for_props/TeX/ch_inference_for_props.tex:1488-1493",
            "confidence": "high",
            "source_issue": (
                "The guided-practice wording has number agreement and two answer typos: "
                "'degrees of freedom is', 'If took a careful look', and 'more larger'."
            ),
            "translation_action": "Render the intended grammatical questions and answer without changing meaning.",
        },
        {
            "location": "ch_inference_for_props/TeX/ch_inference_for_props.tex:1497-1500",
            "confidence": "high",
            "source_issue": (
                "The stable asset/label identifier misspells 'Increasing' as 'Inceasing'; "
                "the alt text also says 'between at around 15'."
            ),
            "translation_action": (
                "Preserve the stable identifier for compatibility, record its semantic alias, "
                "and render the alt text grammatically."
            ),
        },
        {
            "location": "ch_inference_for_props/TeX/ch_inference_for_props.tex:1505",
            "confidence": "high",
            "source_issue": "Number disagreement: 'as the degrees of freedom increases'.",
            "translation_action": "Use a grammatical Indonesian construction; leave authority unchanged.",
        },
        {
            "location": "ch_inference_for_props/TeX/ch_inference_for_props.tex:1580-1582",
            "confidence": "high",
            "source_issue": "The construction 'find that the tail area ... to be' is ungrammatical.",
            "translation_action": "Render the intended statement that the shaded tail area is 0.1165.",
        },
        {
            "location": "ch_inference_for_props/TeX/ch_inference_for_props.tex:1882",
            "confidence": "high",
            "source_issue": "The figure alt text says 'another half has high' instead of 'half as high'.",
            "translation_action": "Render grammatical localized alt text while retaining all values and comparisons.",
        },
        {
            "location": (
                "ch_inference_for_props/TeX/testing_for_goodness_of_fit_using_chi-square.tex:13; "
                "extraTeX/eoceSolutions/eoceSolutions.tex:1479"
            ),
            "confidence": "high",
            "source_issue": (
                "The exercise says the chi-square statistic is always positive and the public "
                "answer marks it true. A chi-square statistic can equal zero when observed and "
                "expected counts match; it is nonnegative, not strictly positive."
            ),
            "translation_action": (
                "Mark the statement false and explain that the statistic is always nonnegative; "
                "retain the stable exercise and answer IDs."
            ),
        },
        {
            "location": (
                "ch_inference_for_props/TeX/ch_inference_for_props.tex:1859-1876,1920-1935; "
                "ch_inference_for_props/figures/geomFitEvaluationForSP500/"
                "geomFitEvaluationForSP500.R:12-23"
            ),
            "confidence": "high",
            "source_issue": (
                "The producer rounds all seven expected counts separately, producing displayed "
                "counts totaling 1363 for 1362 observed waiting times, then computes X^2 from "
                "those rounded values. Pearson calculations should use unrounded expectations, "
                "which sum exactly to 1362."
            ),
            "translation_action": (
                "Display rounded values only as approximations and compute from the unrounded "
                "expected counts; X^2 remains approximately 4.61."
            ),
        },
        {
            "location": (
                "ch_inference_for_props/TeX/ch_inference_for_props.tex:1941-1966; "
                "ch_inference_for_props/figures/geomFitEvaluationForSP500/"
                "geomFitEvaluationForSP500.R:12,23"
            ),
            "confidence": "high",
            "source_issue": (
                "The geometric cell probabilities use p estimated from the same market series, "
                "but the reference distribution uses k-1=6 degrees of freedom. A Pearson "
                "goodness-of-fit test with one fitted parameter uses k-1-1=5 degrees of freedom."
            ),
            "translation_action": (
                "Use df=5 and, with unrounded expectations, p approximately 0.4650; the "
                "failure-to-reject conclusion is unchanged."
            ),
        },
    ]

    payload: dict[str, object] = {
        "$schema": "interlanguage.r011-boundary-blueprint/v1",
        "boundary_id": "R011-B024",
        "status": "PASS_SOURCE_ASSET_DATA_RIGHTS_AND_BOUNDARY_DEPENDENCY_CLOSURE",
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
        "main_source": {
            **component(CHAPTER_REL, rows),
            "file_line_count": len(chapter_lines),
            "start_line": 1344,
            "start_label": "oneWayChiSquare",
            "start_label_line": 1345,
            "end_line": 2001,
            "title": "Testing for goodness of fit using chi-square",
            "slice": slice_identity(chapter, 1344, 2001),
            "excluded_post_section_spacer": {
                "first_line": 2002,
                "last_line": 2007,
                "reason": "Blank separator lines and the next-section divider; no Section 6.3 reader content.",
                "slice": slice_identity(chapter, 2002, 2007),
            },
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
            "chapter_exercise_ids": [31, 32, 33, 34],
            "exercise_records": [
                {"chapter_id": chapter_id, "start_line": start, "label": label}
                for chapter_id, start, label in EXERCISES
            ],
            "exercise_source": {
                **component(EXERCISE_REL, rows),
                "lines": "1-99 inclusive (full file)",
                "slice": slice_identity(exercises, 1, 99),
            },
            "exercise_translation_chunks": [
                {
                    "path": authority_path(EXERCISE_REL),
                    **slice_identity(exercises, 1, 57),
                    "chapter_ids": [31, 32, 33],
                },
                {
                    "path": authority_path(EXERCISE_REL),
                    **slice_identity(exercises, 58, 99),
                    "chapter_ids": [34],
                },
            ],
            "public_answer_ids": public_ids,
            "public_answer_source": {
                **component(ANSWER_REL, rows),
                "lines": "1474-1498 inclusive",
                "slice": slice_identity(answers, 1474, 1498),
            },
            "public_answer_translation_chunk": {
                "path": authority_path(ANSWER_REL),
                **slice_identity(answers, 1474, 1498),
                "chapter_ids": public_ids,
            },
            "o001_gap_ids": [32, 34],
            "restricted_solutions_accessed_or_invented": False,
        },
        "figure_asset_closure": figure_assets,
        "inline_tex_visuals": {
            "main_source_tabular_count": 5,
            "main_source_figure_environment_count": 9,
            "exercise_source_tabular_count": 1,
            "exercise_source_external_photo_count": 1,
            "public_answer_slice_tabular_count": 0,
            "localization_policy": (
                "Translate TeX captions, alt text, headers, cells, and annotations while "
                "preserving counts, values, table structure, labels, cross-references, and attribution."
            ),
        },
        "data_code_closure": {
            "standalone_dataset_input": True,
            "dataset": {
                **component(SP500_DATA_REL, rows),
                "rows_including_header": 17347,
                "date_extent": "1950-01-03 through 2018-12-07",
                "active_analysis_subset": "2009-01-01 through 2018-12-31",
                "active_code_note": (
                    "The producer currently loads the openintro package object and retains "
                    "read.csv('sp500_1950_2018.csv') as a source comment; the adjacent CSV is "
                    "the frozen byte witness."
                ),
            },
            "producer_scripts": 10,
            "committed_generated_pdfs": 10,
            "embedded_values": (
                "Juror counts/proportions, chi-square cutoffs/tail areas, and S&P summary "
                "macros are embedded in TeX; the stock plot producer derives its values from "
                "the frozen market-data file/package object."
            ),
            "external_report_bytes_required": False,
        },
        "citations": {
            "full_bibliography": {**component(BIB_REL, rows)},
            "unique_keys": ["Teng:2004"],
            "slices": [citation_slice("Teng:2004", 642, 651)],
            "required_external_bytes": False,
            "policy": "Retain source attribution and do not claim independent relicensing of study wording.",
        },
        "cross_reference_dependency_closure": {
            "local_labels": LOCAL_LABELS,
            "external_targets": [
                {
                    **component(CHI_TABLE_REL, rows),
                    "label": "chiSquareProbabilityTable",
                    "label_line": 2,
                    "label_slice": slice_identity(AUTH / CHI_TABLE_REL, 2, 2),
                },
                {
                    **component(CHAPTER_REL, rows),
                    "label": "singleProportion",
                    "label_line": 30,
                    "label_slice": slice_identity(chapter, 30, 30),
                },
                {
                    **component(DISTRIBUTIONS_REL, rows),
                    "label": "geomDist",
                    "label_line": 972,
                    "label_slice": slice_identity(AUTH / DISTRIBUTIONS_REL, 972, 972),
                },
            ],
            "internal_reference_targets": [
                label
                for label in LOCAL_LABELS
                if label
                not in {"oneWayChiSquare", *[exercise[2] for exercise in EXERCISES]}
            ],
        },
        "macro_dependency_closure": [
            {
                **component(STYLE_REL, rows),
                "role": (
                    "D, term/termsub, Figure/Figures, oiRedirect, CalculatorVideos, "
                    "exercise/solution, response, example, guided-practice, onebox, and layout macros"
                ),
            },
            {
                **component(HEADERS_REL, rows),
                "role": "end-of-section exercise heading macro",
            },
        ],
        "rights": {
            "repository_text_generated_figures_code_and_data": (
                "CC BY-SA 3.0 repository declaration with source attribution, share-alike "
                "derivative notice, novel derivative title, and no OpenIntro branding/logo."
            ),
            "barking_deer_photo": (
                "CC BY 2.0; preserve Shrikant Rao attribution, Flickr source redirect, and "
                "license identification."
            ),
            "sp500_data": (
                "The component inventory resolves the adjacent CSV under the repository "
                "CC BY-SA 3.0 declaration; preserve provenance and do not assert a broader "
                "standalone market-data license."
            ),
            "component_rights_override": True,
            "external_facts_and_quotations": "retain explicit attribution; do not claim independent relicensing",
            "branding_excluded": True,
            "new_unresolved_binary_dependency": False,
        },
        "correction_candidates": corrections,
        "production_closure": {
            "main_source_lines": 658,
            "exercise_source_lines": 99,
            "public_answer_source_lines": 25,
            "subsections": len(re.findall(r"(?m)^\\subsection", body_active)),
            "worked_examples": body_active.count(r"\begin{nexample}"),
            "guided_exercises": body_active.count(r"\begin{nexercise}"),
            "end_of_section_exercises": 4,
            "public_answers": 2,
            "o001_gaps": 2,
            "external_asset_calls": 11,
            "distinct_binary_assets": 11,
            "figure_producer_scripts": 10,
            "standalone_data_files": 1,
            "bibliography_keys": 1,
            "high_confidence_source_corrections": len(corrections),
        },
        "post_boundary_cursor": {
            "path": authority_path(CHAPTER_REL),
            "line": 2008,
            "title": "Testing for independence in two-way tables",
            "label": "twoWayTablesAndChiSquare",
            "label_line": 2009,
            "working_boundary_id": "R011-B025",
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
        "subsections": 5,
        "worked_examples": 9,
        "guided_exercises": 7,
    }
    for key, expected in expected_counts.items():
        actual = payload["production_closure"][key]
        if actual != expected:
            raise AssertionError(f"production count drift for {key}: {actual}")
    if len(figure_assets) != 11:
        raise AssertionError("binary-asset closure count drift")
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
        if BLUEPRINT.read_bytes() != first:
            raise AssertionError("frozen B024 blueprint differs from exact replay")

    output = {
        "status": "PASS_EXACT_REPLAY_R011_B024_SOURCE_CLOSURE",
        "mode": "write" if args.write else "verify" if args.verify else "self-check",
        "blueprint": {
            "path": str(BLUEPRINT),
            "bytes": len(first),
            "sha256": sha256(first),
            "on_disk_exact": BLUEPRINT.exists() and BLUEPRINT.read_bytes() == first,
        },
        "boundary": {"start_line": 1344, "end_line": 2001},
        "exercise_ids": [31, 32, 33, 34],
        "public_answer_ids": [31, 33],
        "o001_gap_ids": [32, 34],
        "binary_assets": 11,
        "producer_scripts": 10,
        "data_files": 1,
        "post_boundary_cursor": {"line": 2008, "label_line": 2009},
        "scope": "read-only pinned authority plus qa/b024-source blueprint only",
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
