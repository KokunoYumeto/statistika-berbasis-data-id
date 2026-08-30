#!/usr/bin/env python3
"""Freeze and replay-verify the bounded R011-B026 source closure.

Reads only the pinned OpenIntro Statistics authority and the existing
component-rights inventory. Writes/verifies only the task-local B026 source
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
CHAPTER_REL = Path("ch_inference_for_means/TeX/ch_inference_for_means.tex")
EXERCISE_REL = Path(
    "ch_inference_for_means/TeX/one-sample_means_with_the_t-distribution.tex"
)
NEXT_EXERCISE_REL = Path("ch_inference_for_means/TeX/paired_data.tex")
ANSWER_REL = Path("extraTeX/eoceSolutions/eoceSolutions.tex")
BIB_REL = Path("eoce.bib")
STYLE_REL = Path("extraTeX/style/style.tex")
HEADERS_REL = Path("extraTeX/style/headers.tex")
T_TABLE_REL = Path("extraTeX/tables/TeX/tTable.tex")
FOUNDATIONS_REL = Path("ch_foundations_for_inf/TeX/ch_foundations_for_inf.tex")

OUTLIERS_PDF_REL = Path(
    "ch_inference_for_means/figures/outliers_and_ss_condition/"
    "outliers_and_ss_condition.pdf"
)
OUTLIERS_R_REL = Path(
    "ch_inference_for_means/figures/outliers_and_ss_condition/"
    "outliers_and_ss_condition.R"
)
T_COMPARE_PDF_REL = Path(
    "ch_inference_for_means/figures/tDistCompareToNormalDist/"
    "tDistCompareToNormalDist.pdf"
)
T_COMPARE_R_REL = Path(
    "ch_inference_for_means/figures/tDistCompareToNormalDist/"
    "tDistCompareToNormalDist.R"
)
T_CONVERGE_PDF_REL = Path(
    "ch_inference_for_means/figures/tDistConvergeToNormalDist/"
    "tDistConvergeToNormalDist.pdf"
)
T_CONVERGE_R_REL = Path(
    "ch_inference_for_means/figures/tDistConvergeToNormalDist/"
    "tDistConvergeToNormalDist.R"
)
T_DF18_PDF_REL = Path(
    "ch_inference_for_means/figures/tDistDF18LeftTail2Point10/"
    "tDistDF18LeftTail2Point10.pdf"
)
T_DF18_R_REL = Path(
    "ch_inference_for_means/figures/tDistDF18LeftTail2Point10/"
    "tDistDF18LeftTail2Point10.R"
)
T_DF20_PDF_REL = Path(
    "ch_inference_for_means/figures/tDistDF20RightTail1Point65/"
    "tDistDF20RightTail1Point65.pdf"
)
T_DF20_R_REL = Path(
    "ch_inference_for_means/figures/tDistDF20RightTail1Point65/"
    "tDistDF20RightTail1Point65.R"
)
DOLPHIN_JPG_REL = Path(
    "ch_inference_for_means/figures/rissosDolphin/rissosDolphin.jpg"
)
DOLPHIN_README_REL = Path(
    "ch_inference_for_means/figures/rissosDolphin/ReadMe.txt"
)
RUN17_PDF_REL = Path(
    "ch_inference_for_means/figures/run10SampTimeHistogram/"
    "run17SampTimeHistogram.pdf"
)
RUN10_PDF_REL = Path(
    "ch_inference_for_means/figures/run10SampTimeHistogram/"
    "run10SampTimeHistogram.pdf"
)
RUN_HIST_R_REL = Path(
    "ch_inference_for_means/figures/run10SampTimeHistogram/"
    "run10SampTimeHistogram.R"
)
EOCE_T_PDF_REL = Path(
    "ch_inference_for_means/figures/eoce/t_distribution/t_distribution.pdf"
)
EOCE_T_R_REL = Path(
    "ch_inference_for_means/figures/eoce/t_distribution/t_distribution.R"
)
ADULT_HEIGHT_PDF_REL = Path(
    "ch_inference_for_means/figures/eoce/adult_heights/adult_heights_hist.pdf"
)
ADULT_HEIGHT_R_REL = Path(
    "ch_inference_for_means/figures/eoce/adult_heights/adult_heights.R"
)

BLUEPRINT = LANE / "qa/b026-source/R011-B026_BOUNDARY_BLUEPRINT.json"

EXERCISES = [
    (1, 5, "identify_critical_t"),
    (2, 21, "t_distribution"),
    (3, 36, "find_T_pval_1_2_sided"),
    (4, 54, "find_T_pval_2_2_sided"),
    (5, 70, "work_backwards_1"),
    (6, 80, "work_backwards_2"),
    (7, 92, "ny_sleep_habits_2_sided"),
    (8, 126, "adult_heights"),
    (9, 173, "find_mean_2_sided"),
    (10, 189, "critical_t_vs_z"),
    (11, 196, "play_piano_2_sided"),
    (12, 218, "auto_exhaust_lead_exposure_2_sided"),
    (13, 249, "car_insurance_savings"),
    (14, 261, "sat_scores_CI"),
]

LOCAL_LABELS = [
    "inferenceForNumericalData",
    "ch_inference_for_means",
    "oneSampleMeansWithTDistribution",
    "x_bar_conditions",
    "outliers_and_ss_condition_ex",
    "introducingTheTDistribution",
    "tDistCompareToNormalDist",
    "tDistConvergeToNormalDist",
    "tDistDF18LeftTail2Point10",
    "tDistDF20RightTail1Point65",
    "oneSampleTConfidenceIntervals",
    "rissosDolphin",
    "summaryStatsOfHgInMuscleOfRissosDolphins",
    "croakerWhiteFishPacificExerConditions",
    "croakerWhiteFishPacificExerSEDFTStar",
    "croakerWhiteFish90ci",
    "oneSampleTTests",
    "run10SampTimeHistogram",
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
    "auto_exhaust_lead_exposure_2_sided_cond",
    "car_insurance_savings",
    "sat_scores_CI",
]

CHAPTER_NAVIGATION_TARGETS = [
    ("oneSampleMeansWithTDistribution", 32, True),
    ("pairedData", 1060, False),
    ("differenceOfTwoMeans", 1336, False),
    ("PowerForDifferenceOfTwoMeans", 2063, False),
    ("anovaAndRegrWithCategoricalVariables", 2583, False),
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


def producer(
    rel: Path,
    rows: dict[str, dict[str, str]],
    *,
    runtime_dependency: str,
    deterministic_note: str,
) -> dict[str, object]:
    return {
        **component(rel, rows),
        "runtime_dependency": runtime_dependency,
        "deterministic_note": deterministic_note,
    }


def build_blueprint() -> dict[str, object]:
    authority = json.loads((LANE / "authority/UPSTREAM_AUTHORITY.json").read_text("utf-8"))
    if authority["commit"] != COMMIT or authority["calculated_git_tree_sha1"] != TREE:
        raise AssertionError("pinned authority identity drift")

    rows = manifest_rows()
    main = AUTH / MAIN_REL
    chapter = AUTH / CHAPTER_REL
    exercises = AUTH / EXERCISE_REL
    answers = AUTH / ANSWER_REL
    main_lines = exact_lines(main)
    chapter_lines = exact_lines(chapter)
    exercise_lines = exact_lines(exercises)
    answer_lines = exact_lines(answers)

    if len(chapter_lines) != 3410:
        raise AssertionError("chapter source line-count drift")
    if len(exercise_lines) != 280:
        raise AssertionError("B026 exercise source line-count drift")

    chapter_sentinels = {
        1: r"\begin{chapterpage}{Inference for numerical data}",
        4: r"\label{ch_inference_for_means}",
        28: r"%__________________",
        29: r"\section[One-sample means with the $t$-distribution]",
        32: r"\label{oneSampleMeansWithTDistribution}",
        655: (
            r"\Figures[A Risso's dolphin is shown surfacing in water. The area forward "
            r"of its face is mostly white, and then its body is gray and white streaked "
            r"together.]{0.8}{rissosDolphin}{rissosDolphin.jpg}  \\" 
        ),
        934: (
            r'\Figures[A histogram of "time" for the sample Cherry Blossom Race data '
            r"is shown. The data are nearly symmetric with a center at about 100 minutes "
            r"and a standard deviation of roughly 15 to 20 minutes. All times lie between "
            r"50 and 140 minutes.]{0.65}{run10SampTimeHistogram}{run17SampTimeHistogram}"
        ),
        1049: r"\CalculatorVideos{confidence intervals and hypothesis tests for a single mean}",
        1052: (
            r"{\input{ch_inference_for_means/TeX/"
            r"one-sample_means_with_the_t-distribution.tex}}"
        ),
        1058: r"%__________________",
        1059: r"\section{Paired data}",
        1060: r"\label{pairedData}",
    }
    for number, expected in chapter_sentinels.items():
        actual = chapter_lines[number - 1].decode("utf-8").strip()
        if actual != expected:
            raise AssertionError(f"chapter sentinel drift at line {number}: {actual!r}")

    main_sentinels = {
        104: r"\includechapter{6}{ch_inference_for_props}",
        105: r"\includechapter{7}{ch_inference_for_means}",
        106: r"\includechapter{8}{ch_regr_simple_linear}",
    }
    for number, expected in main_sentinels.items():
        actual = main_lines[number - 1].decode("utf-8").strip()
        if actual != expected:
            raise AssertionError(f"book-order sentinel drift at main.tex:{number}")

    exercise_sentinels = {
        1: r"\exercisesheader{}",
        5: r"\eoce{\qt{Identify the critical $t$\label{identify_critical_t}} An independent random",
        261: r"\eoce{\qt{SAT scores\label{sat_scores_CI}}",
        280: r"}{}",
    }
    for number, expected in exercise_sentinels.items():
        actual = exercise_lines[number - 1].decode("utf-8").rstrip()
        if actual != expected:
            raise AssertionError(f"exercise sentinel drift at line {number}: {actual!r}")

    exercise_text = b"".join(exercise_lines).decode("utf-8")
    if exercise_text.count(r"\eoce{") != 14:
        raise AssertionError("expected exactly fourteen B026 end-of-section exercises")
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

    answer_slice_text = b"".join(answer_lines[1622:1721]).decode("utf-8")
    public_ids = [
        int(value) for value in re.findall(r"(?m)^% (\d+)\s*$", answer_slice_text)
    ]
    if public_ids != [1, 3, 5, 7, 9, 11, 13]:
        raise AssertionError(f"public-answer IDs drift: {public_ids}")
    if answer_slice_text.count(r"\eocesol{") != 7:
        raise AssertionError("expected exactly seven public odd answers")
    answer_sentinels = {
        1623: r"%_______________",
        1624: r"\end{multicols}",
        1629: r"\eocesolch{Inference for numerical data}",
        1634: r"\begin{multicols}{2}",
        1636: r"% 1",
        1716: r"% 13",
        1723: r"% 15",
    }
    for number, expected in answer_sentinels.items():
        actual = answer_lines[number - 1].decode("utf-8").strip()
        if actual != expected:
            raise AssertionError(f"public-answer sentinel drift at line {number}: {actual!r}")

    body_active = active_text(chapter_lines, 1, 1052)
    exercise_active = active_text(exercise_lines, 1, 280)
    combined_active = body_active + exercise_active
    actual_labels = re.findall(r"\\label\{([^{}]+)\}", combined_active)
    if actual_labels != LOCAL_LABELS:
        raise AssertionError(f"local-label sequence drift: {actual_labels}")

    refs = re.findall(r"\\(?:ref|pageref)\{([^{}]+)\}", combined_active)
    external_ref_targets = [
        target for target in ["ch_foundations_for_inf", "tDistributionTable"] if target in refs
    ]
    if external_ref_targets != ["ch_foundations_for_inf", "tDistributionTable"]:
        raise AssertionError(f"external-reference closure drift: {external_ref_targets}")
    chapter_navigation = re.findall(r"\\chaptersection\{([^{}]+)\}", body_active)
    if chapter_navigation != [item[0] for item in CHAPTER_NAVIGATION_TARGETS]:
        raise AssertionError(f"chapter-navigation target drift: {chapter_navigation}")
    citations = re.findall(r"\\footfullcite\{([^{}]+)\}", exercise_active)
    if citations != ["Heinz:2003", "Mortada:2000"]:
        raise AssertionError(f"citation sequence drift: {citations}")

    expected_calls = [
        "outliers_and_ss_condition",
        "tDistCompareToNormalDist",
        "tDistConvergeToNormalDist",
        "tDistDF18LeftTail2Point10",
        "tDistDF20RightTail1Point65",
        "rissosDolphin.jpg",
        "run17SampTimeHistogram",
        "ch_inference_for_means/figures/eoce/t_distribution/t_distribution",
        "ch_inference_for_means/figures/eoce/adult_heights/adult_heights_hist",
    ]
    for call in expected_calls:
        if call not in combined_active:
            raise AssertionError(f"active asset call absent: {call}")
    if len(re.findall(r"\\(?:Figure|Figures|FigureFullPath)(?:\[|\{)", combined_active)) != 9:
        raise AssertionError("active figure-call count drift")

    producer_sentinels = {
        OUTLIERS_R_REL: ["set.seed(2)", 'xlab = "Sample 1 Observations (n = 15)"'],
        T_COMPARE_R_REL: ['"Normal"', '"t-distribution"', "Y <- dt(X, 2)"],
        T_CONVERGE_R_REL: ["DF   <- c('normal', 8, 4, 2, 1)", "paste('t, df = '"] ,
        T_DF18_R_REL: ["L = -2.10", "df = 10"],
        T_DF20_R_REL: ["U = 1.65", "df = 12", "df = 2.3"],
        RUN_HIST_R_REL: ["data(run10Samp)", "set.seed(1)", 'xlab = "Time (Minutes)"'],
        EOCE_T_R_REL: ["Y <- dt(X, 1)", "Z <- dt(X, 5)", 'c("solid","dashed","dotted")'],
        ADULT_HEIGHT_R_REL: ["data(bdims)", 'xlab = "Height"'],
    }
    for rel, sentinels in producer_sentinels.items():
        text = (AUTH / rel).read_text("utf-8")
        for sentinel in sentinels:
            if sentinel not in text:
                raise AssertionError(f"producer sentinel drift in {rel}: {sentinel}")

    dolphin_readme = (AUTH / DOLPHIN_README_REL).read_text("utf-8")
    for sentinel in [
        "Photo by Mike Baird",
        "http://www.bairdphotos.com/",
        "Creative Commons Attribution 2.0 Generic",
    ]:
        if sentinel not in dolphin_readme:
            raise AssertionError(f"dolphin attribution drift: {sentinel}")

    local_macro_definitions = re.findall(r"\\newcommand\{\\([^{}]+)\}", body_active)
    if local_macro_definitions != [
        "cherryblossomn",
        "cherryblossommean",
        "cherryblossomnull",
        "cherryblossomsd",
        "cherryblossomse",
        "cherryblossomz",
    ]:
        raise AssertionError(f"local macro sequence drift: {local_macro_definitions}")

    chunks = [
        (1, 28, "Chapter page, navigation, and Chapter 7 inference introduction."),
        (29, 231, "Section opening, sampling distribution, conditions, and first worked check."),
        (232, 400, "Population sanity check, retained source comments, and closure of CLT indexing."),
        (401, 633, "Introduction to the t-distribution, degrees of freedom, tools, and tail examples."),
        (634, 796, "One-sample t confidence intervals and the Risso's dolphin worked sequence."),
        (797, 896, "White-fish guided confidence-interval sequence and transition to t tests."),
        (897, 1052, "Cherry Blossom one-sample t test, summary box, video marker, and exercise input."),
    ]

    corrections = [
        {
            "location": "ch_inference_for_means/TeX/ch_inference_for_means.tex:110-114",
            "confidence": "high",
            "source_issue": (
                "The independence item joins two complete sentences with a comma after "
                "'independent'."
            ),
            "translation_action": "Use a sentence boundary; leave authority unchanged.",
        },
        {
            "location": "ch_inference_for_means/TeX/ch_inference_for_means.tex:203",
            "confidence": "high",
            "source_issue": "The alt text says 'There is only non-zero bin beyond 5', omitting 'one'.",
            "translation_action": "Describe exactly one non-zero bin beyond 5 in localized alt text.",
        },
        {
            "location": "ch_inference_for_means/TeX/ch_inference_for_means.tex:208-210",
            "confidence": "high",
            "source_issue": "The worked answer begins 'Each samples is', a number-agreement error.",
            "translation_action": "Use the singular meaning 'each sample'; leave authority unchanged.",
        },
        {
            "location": "ch_inference_for_means/TeX/ch_inference_for_means.tex:417-419",
            "confidence": "high",
            "source_issue": "The phrase 'use sample value' is missing the article 'a'.",
            "translation_action": "Render the intended sample-value substitution naturally.",
        },
        {
            "location": "ch_inference_for_means/TeX/ch_inference_for_means.tex:458",
            "confidence": "high",
            "source_issue": (
                "The alt text says 'the is a sizable fraction' and describes the plotted df=2 "
                "t density as more sharply peaked than the normal density; at zero the plotted "
                "t density is lower/flatter, while its tails are heavier."
            ),
            "translation_action": (
                "Correct the grammar and describe the visible center/tail relationship without "
                "reversing the peak-height ordering."
            ),
        },
        {
            "location": "ch_inference_for_means/TeX/ch_inference_for_means.tex:465-496",
            "confidence": "high",
            "source_issue": (
                "Several clauses treat plural 'degrees of freedom' as singular ('describes', "
                "'is about 30')."
            ),
            "translation_action": "Use grammatical number while preserving df=n-1 and all values.",
        },
        {
            "location": "ch_inference_for_means/TeX/ch_inference_for_means.tex:486",
            "confidence": "high",
            "source_issue": (
                "The alt text has a malformed possessive ('distributions tails') and says the "
                "peak becomes less sharp as df grows; the plotted densities instead converge "
                "upward at zero toward the normal density while their tails thin."
            ),
            "translation_action": "Correct both grammar and the plotted peak/tail trend in localized alt text.",
        },
        {
            "location": (
                "ch_inference_for_means/figures/tDistDF18LeftTail2Point10/"
                "tDistDF18LeftTail2Point10.R:7-12 and committed PDF"
            ),
            "confidence": "high",
            "source_issue": (
                "The section and caption specify df=18, but the producer uses df=10. A direct "
                "PDF text probe also exposes the stray placeholder word 'Text'."
            ),
            "translation_action": (
                "Regenerate the localized figure with df=18 and no placeholder while preserving "
                "the -2.10 cutoff and tail geometry."
            ),
        },
        {
            "location": (
                "ch_inference_for_means/figures/tDistDF20RightTail1Point65/"
                "tDistDF20RightTail1Point65.R:8-19"
            ),
            "confidence": "high",
            "source_issue": (
                "The source describes df=20 in the left panel and df=2 in the right panel, but "
                "the producer uses df=12 and df=2.3, respectively."
            ),
            "translation_action": "Regenerate the two panels with df=20 and df=2; preserve cutoffs and shading.",
        },
        {
            "location": "ch_inference_for_means/TeX/ch_inference_for_means.tex:737-740",
            "confidence": "high",
            "source_issue": (
                "The worked prompt says 'this degrees of freedom' and the response says 'The "
                "degrees of freedom is easy to calculate'."
            ),
            "translation_action": "Render the intended number of degrees of freedom grammatically.",
        },
        {
            "location": "ch_inference_for_means/TeX/ch_inference_for_means.tex:921-923",
            "confidence": "high",
            "source_issue": (
                "The guided question calls the displayed plot a histogram 'of the differences', "
                "but the active run17 asset is a histogram of sampled 10-mile run times."
            ),
            "translation_action": "Refer to the sampled run times, consistent with the figure and producer.",
        },
        {
            "location": "ch_inference_for_means/TeX/ch_inference_for_means.tex:926-930",
            "confidence": "high",
            "source_issue": "The answer says 'there is are particularly extreme outliers'.",
            "translation_action": "Use grammatical plural agreement without changing the conclusion.",
        },
        {
            "location": (
                "ch_inference_for_means/TeX/"
                "one-sample_means_with_the_t-distribution.tex:30"
            ),
            "confidence": "high",
            "source_issue": (
                "The exercise alt text contains repeated agreement errors and reverses the "
                "center-peak ordering of the plotted normal, t(df=5), and t(df=1) curves."
            ),
            "translation_action": (
                "Describe the line styles and visible center/tail ordering accurately while "
                "leaving the identification task itself unsolved."
            ),
        },
        {
            "location": (
                "ch_inference_for_means/TeX/"
                "one-sample_means_with_the_t-distribution.tex:92-96"
            ),
            "confidence": "high",
            "source_issue": "The quoted nickname opens with TeX quotes but closes with a straight double quote.",
            "translation_action": "Use a balanced localized quotation; leave authority unchanged.",
        },
        {
            "location": (
                "ch_inference_for_means/TeX/"
                "one-sample_means_with_the_t-distribution.tex:139-147"
            ),
            "confidence": "high",
            "source_issue": (
                "The summary table declares three columns ('l|r l') but every row contains only "
                "two cells, leaving an unintended empty third column."
            ),
            "translation_action": "Use a two-column specification while preserving every statistic and value.",
        },
        {
            "location": (
                "ch_inference_for_means/TeX/"
                "one-sample_means_with_the_t-distribution.tex:189-191"
            ),
            "confidence": "high",
            "source_issue": "The exercise switches from \\star to plain * for the same critical-value notation.",
            "translation_action": "Normalize the learner-visible notation to t^\\star and z^\\star.",
        },
    ]

    figure_asset_closure = [
        {
            **component(OUTLIERS_PDF_REL, rows),
            "active_call": {"source": authority_path(CHAPTER_REL), "line": 203, "macro": "Figure"},
            "producer": producer(
                OUTLIERS_R_REL,
                rows,
                runtime_dependency="openintro: myPDF, histPlot, COL; base R RNG",
                deterministic_note="synthetic samples are frozen by set.seed(2); no dataset input",
            ),
            "reader_visible_strings": [
                "Frequency",
                "Sample 1 Observations (n = 15)",
                "Sample 2 Observations (n = 50)",
            ],
            "content_localization_required": True,
            "alt_caption_localization_required": True,
        },
        {
            **component(T_COMPARE_PDF_REL, rows),
            "active_call": {"source": authority_path(CHAPTER_REL), "line": 458, "macro": "Figure"},
            "producer": producer(
                T_COMPARE_R_REL,
                rows,
                runtime_dependency="openintro: myPDF and COL; base R normal/t densities",
                deterministic_note="formula-only plot; t density uses df=2",
            ),
            "reader_visible_strings": ["Normal", "t-distribution"],
            "content_localization_required": True,
            "alt_caption_localization_required": True,
        },
        {
            **component(T_CONVERGE_PDF_REL, rows),
            "active_call": {"source": authority_path(CHAPTER_REL), "line": 486, "macro": "Figure"},
            "producer": producer(
                T_CONVERGE_R_REL,
                rows,
                runtime_dependency="openintro: myPDF, COL, fadeColor; base R normal/t densities",
                deterministic_note="formula-only plot with normal and t densities at df=8,4,2,1",
            ),
            "reader_visible_strings": ["normal", "t, df = 8", "t, df = 4", "t, df = 2", "t, df = 1"],
            "content_localization_required": True,
            "alt_caption_localization_required": True,
        },
        {
            **component(T_DF18_PDF_REL, rows),
            "active_call": {"source": authority_path(CHAPTER_REL), "line": 542, "macro": "Figure"},
            "producer": producer(
                T_DF18_R_REL,
                rows,
                runtime_dependency="openintro: myPDF, normTail, COL",
                deterministic_note="formula-only plot; source producer currently has the recorded df mismatch",
            ),
            "reader_visible_strings_from_pdf_text_probe": ["Text", "-4", "-2", "0", "2", "4"],
            "content_localization_required": False,
            "content_correction_and_regeneration_required": True,
            "alt_caption_localization_required": True,
        },
        {
            **component(T_DF20_PDF_REL, rows),
            "active_call": {"source": authority_path(CHAPTER_REL), "line": 563, "macro": "Figure"},
            "producer": producer(
                T_DF20_R_REL,
                rows,
                runtime_dependency="openintro: myPDF, normTail, COL",
                deterministic_note="formula-only panels; source producer currently has the recorded df mismatches",
            ),
            "reader_visible_strings": ["numeric axis ticks only"],
            "content_localization_required": False,
            "content_correction_and_regeneration_required": True,
            "alt_caption_localization_required": True,
        },
        {
            **component(DOLPHIN_JPG_REL, rows),
            "active_call": {"source": authority_path(CHAPTER_REL), "line": 655, "macro": "Figures"},
            "rights_witness": {**component(DOLPHIN_README_REL, rows)},
            "required_attribution": (
                "Photo by Mike Baird (http://www.bairdphotos.com/); "
                "Creative Commons Attribution 2.0 Generic"
            ),
            "content_localization_required": False,
            "alt_caption_localization_required": True,
        },
        {
            **component(RUN17_PDF_REL, rows),
            "active_call": {"source": authority_path(CHAPTER_REL), "line": 934, "macro": "Figures"},
            "producer": producer(
                RUN_HIST_R_REL,
                rows,
                runtime_dependency=(
                    "openintro: run10Samp and run17 runtime data objects, myPDF, histPlot, COL; "
                    "base R subset/sample/t.test"
                ),
                deterministic_note="active run17 sample is frozen by set.seed(1)",
            ),
            "producer_sibling_output_not_called_by_b026": {**component(RUN10_PDF_REL, rows)},
            "reader_visible_strings": ["Frequency", "Time (Minutes)"],
            "content_localization_required": True,
            "alt_caption_localization_required": True,
        },
        {
            **component(EOCE_T_PDF_REL, rows),
            "active_call": {"source": authority_path(EXERCISE_REL), "line": 30, "macro": "FigureFullPath"},
            "producer": producer(
                EOCE_T_R_REL,
                rows,
                runtime_dependency="base R normal/t densities only",
                deterministic_note="formula-only plot; line styles map to normal, t(df=5), t(df=1)",
            ),
            "reader_visible_strings": ["solid", "dashed", "dotted"],
            "content_localization_required": True,
            "alt_caption_localization_required": True,
        },
        {
            **component(ADULT_HEIGHT_PDF_REL, rows),
            "active_call": {"source": authority_path(EXERCISE_REL), "line": 134, "macro": "FigureFullPath"},
            "producer": producer(
                ADULT_HEIGHT_R_REL,
                rows,
                runtime_dependency="openintro: bdims runtime data object, histPlot, COL",
                deterministic_note="full bdims height vector; no random sampling",
            ),
            "reader_visible_strings": ["Height"],
            "content_localization_required": True,
            "alt_caption_localization_required": True,
        },
    ]

    payload: dict[str, object] = {
        "$schema": "interlanguage.r011-boundary-blueprint/v1",
        "boundary_id": "R011-B026",
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
            "previous_chapter_include": {
                "line": 104,
                "text": r"\includechapter{6}{ch_inference_for_props}",
                "slice": slice_identity(main, 104, 104),
            },
            "current_chapter_include": {
                "line": 105,
                "text": r"\includechapter{7}{ch_inference_for_means}",
                "slice": slice_identity(main, 105, 105),
            },
            "next_chapter_include": {
                "line": 106,
                "text": r"\includechapter{8}{ch_regr_simple_linear}",
                "slice": slice_identity(main, 106, 106),
            },
        },
        "main_source": {
            **component(CHAPTER_REL, rows),
            "file_line_count": len(chapter_lines),
            "boundary_start_line": 1,
            "chapter_opening_lines": "1-28 inclusive",
            "instructional_start_line": 29,
            "start_label": "oneSampleMeansWithTDistribution",
            "start_label_line": 32,
            "end_line": 1052,
            "title": "One-sample means with the t-distribution",
            "slice": slice_identity(chapter, 1, 1052),
            "chapter_opening_slice": slice_identity(chapter, 1, 28),
            "instructional_section_slice": slice_identity(chapter, 29, 1052),
            "source_file_ends_at_boundary": False,
            "post_section_spacer": {
                "lines": "1053-1058 inclusive",
                "slice": slice_identity(chapter, 1053, 1058),
                "last_line_is_next_section_separator": True,
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
            "chapter_exercise_ids": list(range(1, 15)),
            "exercise_records": [
                {"chapter_id": chapter_id, "start_line": start, "label": label}
                for chapter_id, start, label in EXERCISES
            ],
            "exercise_source": {
                **component(EXERCISE_REL, rows),
                "lines": "1-280 inclusive (full file)",
                "slice": slice_identity(exercises, 1, 280),
            },
            "exercise_translation_chunks": [
                {
                    "path": authority_path(EXERCISE_REL),
                    **slice_identity(exercises, 1, 86),
                    "chapter_ids": [1, 2, 3, 4, 5, 6],
                },
                {
                    "path": authority_path(EXERCISE_REL),
                    **slice_identity(exercises, 87, 169),
                    "chapter_ids": [7, 8],
                },
                {
                    "path": authority_path(EXERCISE_REL),
                    **slice_identity(exercises, 170, 245),
                    "chapter_ids": [9, 10, 11, 12],
                },
                {
                    "path": authority_path(EXERCISE_REL),
                    **slice_identity(exercises, 246, 280),
                    "chapter_ids": [13, 14],
                },
            ],
            "public_answer_ids": public_ids,
            "public_answer_source": {
                **component(ANSWER_REL, rows),
                "lines": "1623-1721 inclusive",
                "slice": slice_identity(answers, 1623, 1721),
                "layout_lines_inside_slice": (
                    "1623-1634 close the preceding columns, introduce the Chapter 7 answer "
                    "heading, and open two columns; 1679-1681 perform the page/column transition"
                ),
            },
            "public_answer_translation_chunks": [
                {
                    "path": authority_path(ANSWER_REL),
                    **slice_identity(answers, 1623, 1677),
                    "chapter_ids": [1, 3, 5, 7],
                    "includes_chapter_heading_and_layout_lines": True,
                },
                {
                    "path": authority_path(ANSWER_REL),
                    **slice_identity(answers, 1678, 1721),
                    "chapter_ids": [9, 11, 13],
                    "includes_page_and_column_transition": True,
                },
            ],
            "o001_gap_ids": [2, 4, 6, 8, 10, 12, 14],
            "restricted_solutions_accessed_or_invented": False,
        },
        "figure_asset_closure": figure_asset_closure,
        "inline_tex_visuals": {
            "main_source_tabular_count": body_active.count(r"\begin{tabular}"),
            "main_source_figure_environment_count": body_active.count(r"\begin{figure}"),
            "main_source_external_asset_count": len(
                re.findall(r"\\(?:Figure|Figures)(?:\[|\{)", body_active)
            ),
            "exercise_source_tabular_count": exercise_active.count(r"\begin{tabular}"),
            "exercise_source_external_asset_count": len(
                re.findall(r"\\FigureFullPath(?:\[|\{)", exercise_active)
            ),
            "public_answer_slice_tabular_count": answer_slice_text.count(r"\begin{tabular}"),
            "localization_policy": (
                "Translate TeX captions, headers, cells, annotations, axis/legend text, and "
                "alt text while preserving counts, formulas, table structure, labels, "
                "cross-references, study/photo attribution, and numerical meaning."
            ),
        },
        "data_code_closure": {
            "standalone_dataset_input": False,
            "producer_scripts": 8,
            "committed_generated_pdfs_called_by_boundary": 8,
            "photographic_assets_called_by_boundary": 1,
            "producer_sibling_outputs_not_called_by_boundary": 1,
            "runtime_package_data": [
                {
                    "objects": ["COL"],
                    "package": "openintro",
                    "usage": "palette and plotting helpers across generated figures",
                },
                {
                    "objects": ["run10Samp", "run17"],
                    "package": "openintro",
                    "usage": (
                        "the shared producer emits a run10 sibling and the active deterministic "
                        "run17 10-mile sample histogram"
                    ),
                },
                {
                    "objects": ["bdims"],
                    "package": "openintro",
                    "usage": "adult-height exercise histogram; linked to Heinz:2003",
                },
            ],
            "synthetic_formula_only_producers": [
                "outliers_and_ss_condition (set.seed(2))",
                "tDistCompareToNormalDist",
                "tDistConvergeToNormalDist",
                "tDistDF18LeftTail2Point10",
                "tDistDF20RightTail1Point65",
                "eoce/t_distribution",
            ],
            "embedded_values": (
                "Dolphin mercury, croaker white-fish mercury, Cherry Blossom summaries, all "
                "worked t calculations, and exercise statistics are embedded in TeX."
            ),
            "frozen_standalone_runtime_data_bytes_in_authority": False,
            "reader_reproduction_note": (
                "The committed PDFs are frozen reader byte witnesses. Producer replay additionally "
                "requires the named openintro package objects; no raw dataset file enters B026."
            ),
            "external_report_or_article_bytes_required": False,
        },
        "citations": {
            "full_bibliography": {**component(BIB_REL, rows)},
            "unique_keys": ["Heinz:2003", "Mortada:2000"],
            "slices": [
                citation_slice("Heinz:2003", 448, 455),
                citation_slice("Mortada:2000", 741, 749),
            ],
            "required_external_bytes": False,
            "policy": (
                "Retain each study's authors, title, journal, volume/issue/pages/year where "
                "present, and redirect provenance; do not claim independent relicensing of "
                "article wording or raw study data."
            ),
        },
        "cross_reference_dependency_closure": {
            "local_labels": LOCAL_LABELS,
            "external_targets": [
                {
                    **component(FOUNDATIONS_REL, rows),
                    "label": "ch_foundations_for_inf",
                    "label_line": 4,
                    "label_slice": slice_identity(AUTH / FOUNDATIONS_REL, 4, 4),
                },
                {
                    **component(T_TABLE_REL, rows),
                    "label": "tDistributionTable",
                    "label_line": 2,
                    "label_slice": slice_identity(AUTH / T_TABLE_REL, 2, 2),
                },
            ],
            "chapter_navigation_targets": [
                {
                    **component(CHAPTER_REL, rows),
                    "label": label,
                    "label_line": line,
                    "inside_boundary": inside,
                    "label_slice": slice_identity(chapter, line, line),
                }
                for label, line, inside in CHAPTER_NAVIGATION_TARGETS
            ],
            "internal_reference_targets": [
                "x_bar_conditions",
                "introducingTheTDistribution",
                "tDistCompareToNormalDist",
                "tDistConvergeToNormalDist",
                "tDistDF18LeftTail2Point10",
                "tDistDF20RightTail1Point65",
                "summaryStatsOfHgInMuscleOfRissosDolphins",
                "croakerWhiteFishPacificExerConditions",
                "croakerWhiteFishPacificExerSEDFTStar",
                "croakerWhiteFish90ci",
                "run10SampTimeHistogram",
                "auto_exhaust_lead_exposure_2_sided_cond",
            ],
        },
        "macro_dependency_closure": [
            {
                **component(STYLE_REL, rows),
                "role": (
                    "D, term/index, response, example/guided-practice, exercise/solution, "
                    "Figure/Figures/FigureFullPath, redirect, CalculatorVideos, and layout macros"
                ),
            },
            {
                **component(HEADERS_REL, rows),
                "role": (
                    "chapterpage, chaptertitle, chaptersection, chapterintro, section headers, "
                    "and end-of-section exercise heading"
                ),
            },
        ],
        "local_macro_definitions": local_macro_definitions,
        "rights": {
            "repository_text_generated_figures_and_code": (
                "CC BY-SA 3.0 repository declaration with source attribution, share-alike "
                "derivative notice, novel derivative title, and no OpenIntro branding/logo."
            ),
            "rissos_dolphin_photo": (
                "CC BY 2.0; retain Mike Baird attribution, http://www.bairdphotos.com/, and "
                "the Creative Commons Attribution 2.0 Generic license notice."
            ),
            "cited_studies": (
                "Bibliographic facts and attributed study descriptions are retained; no external "
                "article bytes are incorporated and no independent relicensing is claimed."
            ),
            "runtime_openintro_package_data": (
                "The producers reference run10Samp, run17, bdims, and COL at runtime; no standalone "
                "package-data file enters this boundary. Preserve the runtime provenance."
            ),
            "component_rights_override": True,
            "external_facts_and_quotations": "retain explicit attribution; do not claim independent relicensing",
            "branding_excluded": True,
            "new_unresolved_binary_dependency": False,
        },
        "correction_candidates": corrections,
        "production_closure": {
            "main_source_lines": 1052,
            "chapter_opening_lines": 28,
            "instructional_section_lines": 1024,
            "exercise_source_lines": 280,
            "public_answer_source_lines": 99,
            "subsections": len(re.findall(r"(?m)^\\subsection", body_active)),
            "worked_examples": body_active.count(r"\begin{nexample}"),
            "guided_exercises": body_active.count(r"\begin{nexercise}"),
            "end_of_section_exercises": 14,
            "public_answers": 7,
            "o001_gaps": 7,
            "external_asset_calls": 9,
            "distinct_reader_binary_assets": 9,
            "committed_generated_reader_pdfs": 8,
            "photographic_reader_assets": 1,
            "figure_producer_scripts": 8,
            "standalone_data_files": 0,
            "bibliography_keys": 2,
            "high_confidence_source_corrections": len(corrections),
        },
        "post_boundary_cursor": {
            "book_order_source": authority_path(MAIN_REL),
            "book_order_current_include_line": 105,
            "book_order_next_chapter_include_line": 106,
            "path": authority_path(CHAPTER_REL),
            "line": 1059,
            "section_title": "Paired data",
            "section_label": "pairedData",
            "section_label_line": 1060,
            "working_boundary_id": "R011-B027",
            "source_component": {**component(CHAPTER_REL, rows)},
            "section_opening_slice": slice_identity(chapter, 1058, 1060),
            "next_exercise_component": {**component(NEXT_EXERCISE_REL, rows)},
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
        "worked_examples": 10,
        "guided_exercises": 6,
    }
    for key, expected in expected_counts.items():
        actual = payload["production_closure"][key]
        if actual != expected:
            raise AssertionError(f"production count drift for {key}: {actual}")
    if payload["inline_tex_visuals"] != {
        "main_source_tabular_count": 1,
        "main_source_figure_environment_count": 7,
        "main_source_external_asset_count": 7,
        "exercise_source_tabular_count": 2,
        "exercise_source_external_asset_count": 2,
        "public_answer_slice_tabular_count": 0,
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
            raise AssertionError("frozen B026 blueprint differs from exact replay")

    output = {
        "status": "PASS_EXACT_REPLAY_R011_B026_SOURCE_CLOSURE",
        "mode": "write" if args.write else "verify" if args.verify else "self-check",
        "blueprint": {
            "path": str(BLUEPRINT),
            "bytes": len(first),
            "sha256": sha256(first),
            "on_disk_exact": BLUEPRINT.exists() and BLUEPRINT.read_bytes() == first,
        },
        "boundary": {
            "start_line": 1,
            "chapter_opening_end_line": 28,
            "instructional_start_line": 29,
            "end_line": 1052,
            "source_file_end": 3410,
        },
        "exercise_ids": list(range(1, 15)),
        "public_answer_ids": [1, 3, 5, 7, 9, 11, 13],
        "o001_gap_ids": [2, 4, 6, 8, 10, 12, 14],
        "reader_binary_assets": 9,
        "producer_scripts": 8,
        "standalone_data_files": 0,
        "high_confidence_source_corrections": 16,
        "post_boundary_cursor": {
            "path": authority_path(CHAPTER_REL),
            "line": 1059,
            "section_label_line": 1060,
            "working_boundary_id": "R011-B027",
        },
        "scope": "read-only pinned authority plus qa/b026-source blueprint only",
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
