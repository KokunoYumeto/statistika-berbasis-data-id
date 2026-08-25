#!/usr/bin/env python3
"""Assemble and fail-closed verify the isolated R011-B014 source candidate."""

from __future__ import annotations

from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[2]
PIN = (
    ROOT
    / "authority"
    / "upstream"
    / "openintro-statistics-fee25091fb24e89c36296fd67c48c1fcf7a93b6e"
)
MODEL = "OpenAI Codex gpt-5.6-sol, Ultra"
DATE = "2026-08-25"
BOUNDARY_ID = "R011-B014"

BASE = ROOT / "qa" / "b013-build" / "source-snapshot-b013"
BASE_MAIN = BASE / "ch_distributions" / "TeX" / "ch_distributions.tex"
BASE_EOCE = BASE / "ch_distributions" / "TeX" / "normal_distribution.tex"
BASE_SOLUTIONS = BASE / "extraTeX" / "eoceSolutions" / "eoceSolutions.tex"
BASE_PREFACE = BASE / "extraTeX" / "preamble" / "preface.tex"

SOURCE_MAIN = PIN / "ch_distributions" / "TeX" / "ch_distributions.tex"
SOURCE_EOCE = PIN / "ch_distributions" / "TeX" / "normal_distribution.tex"
SOURCE_SOLUTIONS = PIN / "extraTeX" / "eoceSolutions" / "eoceSolutions.tex"
COMPONENT_CLOSURE = ROOT / "authority" / "CORPUS_COMPONENT_CLOSURE.csv"

BASE_MANIFEST = ROOT / "qa" / "b013-build" / "R011-B013_SOURCE_MANIFEST.tsv"
BASE_SOURCE_QA = ROOT / "qa" / "b013-build" / "R011-B013_SOURCE_QA.json"
BASE_BUILD_QA = (
    ROOT / "qa" / "b013-build" / "final" / "CANDIDATE_BUILD_QA_B013.json"
)
BASE_VISUAL_QA = ROOT / "qa" / "b013-visual" / "R011-B013_VISUAL_QA.json"
REUSED_TERMINOLOGY_QA = (
    ROOT / "qa" / "b012-terminology" / "R011-B012_TERMINOLOGY_QA.json"
)
REUSED_CONTROLLED_TERMS = (
    ROOT / "qa" / "b012-terminology" / "R011-B012_CONTROLLED_TERMS.tsv"
)
TERMINOLOGY_VIEW = ROOT / "backend" / "exports" / "views" / "terminology.csv"
FIELD_WITNESS_PROBABILITY = (
    ROOT / "scratch" / "b011-terminology"
    / "teori_peluang_ansori_fajriah_suryaningsih_2021.txt"
)
FIELD_WITNESS_STATISTICS = (
    ROOT / "qa" / "terminology" / "fallback-statistika-dasar-2017"
    / "Buku_Ajar_Statistika_Dasar_Cindy_Cahyaning_Astuti_2017.txt"
)

CANDIDATE = ROOT / "scratch" / "b014-candidate"
TARGET_CHAPTER_OPENING = CANDIDATE / "ch_distributions_chapter_opening_id.tex"
TARGET_MAIN = CANDIDATE / "ch_distributions_section_4_1_id.tex"
TARGET_EOCE = CANDIDATE / "normal_distribution_B014.tex"
TARGET_ANSWERS = CANDIDATE / "R011-B014_PUBLIC_ODD_ANSWERS.tex"
ASSEMBLED_MAIN = CANDIDATE / "ch_distributions_B014_source.tex"
ASSEMBLED_SOLUTIONS = CANDIDATE / "eoceSolutions_B014_source.tex"
ASSEMBLED_PREFACE = CANDIDATE / "preface_B014_source.tex"

CONTROLLED_TERMS = (
    ROOT / "qa" / "b014-terminology" / "R011-B014_CONTROLLED_TERMS.tsv"
)
TERMINOLOGY_QA = (
    ROOT / "qa" / "b014-terminology" / "R011-B014_TERMINOLOGY_QA.json"
)
SOURCE_QA = ROOT / "qa" / "b014-source" / "R011-B014_SOURCE_CLOSURE.json"
ASSET_QA = ROOT / "qa" / "b014-assets" / "R011-B014_ASSET_CLOSURE.json"
TRANSLATION_QA = (
    ROOT / "qa" / "b014-translation" / "R011-B014_FINAL_TRANSLATION_QA.json"
)
CANDIDATE_RECEIPT = CANDIDATE / "R011-B014_TRANSLATION_CANDIDATE_RECEIPT.json"

EXPECTED = {
    BASE_MAIN: (91188, "71e4985a1bf31e9dd6897ec2bd246b3b2f8cd62ab55524a5b1bfe791e613a3a9"),
    BASE_EOCE: (7466, "c7d98aff4f421d290e4a6e117cdff4d4b7604ee9bbcc7a3e080928d3c963438e"),
    BASE_SOLUTIONS: (109045, "a7088158d60ac8dbf9e05720d081633ffad1b829611cf90c85029fc27ca72ed6"),
    BASE_PREFACE: (10080, "e2d3dc856591ed58a4a46e5573f694fe92f9b7f65ef428da5997fa1b7a336fb9"),
    SOURCE_MAIN: (91188, "71e4985a1bf31e9dd6897ec2bd246b3b2f8cd62ab55524a5b1bfe791e613a3a9"),
    SOURCE_EOCE: (7466, "c7d98aff4f421d290e4a6e117cdff4d4b7604ee9bbcc7a3e080928d3c963438e"),
    SOURCE_SOLUTIONS: (106045, "6c4e01376db4c023cc7b3f9949490e57220ef1cb831c580da71efde6ce723268"),
    COMPONENT_CLOSURE: (452295, "e247016cd63f3ff04e82991298cd793e6cd42e7c1abcd1288e86f39c2aa8249e"),
    BASE_MANIFEST: (175582, "6a02065e6c765294da8e1354685665042dbd9e8d4015505df89bd771c9ccc4cf"),
    BASE_SOURCE_QA: (20086, "f90db23f88166be13801f9f793dc2d647a084ac88a7d835586c1d4c85fe27caa"),
    BASE_BUILD_QA: (19854, "e463ceb1dcbbbbb25e71c4d627741ca285a5532220197c55511f7b9ed18ad2e7"),
    BASE_VISUAL_QA: (9603, "3604af11745add719f2d8c0b3be131035436cfe47aec7a77fdcd78561f6f3f0d"),
    REUSED_TERMINOLOGY_QA: (6408, "6a209eedb8e01949a0d77b16b8af348c1216ee20f34782ec6b87fde2093f22f7"),
    REUSED_CONTROLLED_TERMS: (2343, "50574600ce8397a31e3be124e84d0e85565f2aa033c93ed9612ee1a57e05c713"),
    TERMINOLOGY_VIEW: (29727, "f3ea261c6ecabe9a56a90d61c8343661083720846097ed04ac4b0f746d09f4f9"),
    FIELD_WITNESS_PROBABILITY: (386031, "9b166a905c99a321eef25e2cc6932a5573037ae9441a866282d08154cd491707"),
    FIELD_WITNESS_STATISTICS: (201466, "f0e15d276e1e27c99d805ad8977dcf40d49165a76b970cfbce2897642dfe41af"),
}

PDF_PATHS = (
    "ch_distributions/figures/simpleNormal/simpleNormal.pdf",
    "ch_distributions/figures/twoSampleNormals/twoSampleNormals.pdf",
    "ch_distributions/figures/twoSampleNormalsStacked/twoSampleNormalsStacked.pdf",
    "ch_distributions/figures/satActNormals/satActNormals.pdf",
    "ch_distributions/figures/satBelow1300/satBelow1300.pdf",
    "ch_distributions/figures/satAbove1190/satAbove1190.pdf",
    "ch_distributions/figures/subtractingArea/subtractingArea.pdf",
    "ch_distributions/figures/subtractingArea/subtracted.pdf",
    "ch_distributions/figures/satBelow1030/satBelow1030.pdf",
    "ch_distributions/figures/satBelow1030/satAbove1030.pdf",
    "ch_distributions/figures/mikeAndJosePercentiles/mikeAndJosePercentiles.pdf",
    "ch_distributions/figures/height40Perc/height40Perc.pdf",
    "ch_distributions/figures/height82Perc/height82Perc.pdf",
    "ch_distributions/figures/between59And62/between59And62.pdf",
    "ch_distributions/figures/subtracting2Areas/subtracting2Areas.pdf",
    "ch_distributions/figures/6895997/6895997.pdf",
    "ch_distributions/figures/eoce/area_under_curve_1/zltNeg.pdf",
    "ch_distributions/figures/eoce/area_under_curve_1/zgtPos.pdf",
    "ch_distributions/figures/eoce/area_under_curve_1/zBet.pdf",
    "ch_distributions/figures/eoce/area_under_curve_1/zgtAbs.pdf",
    "ch_distributions/figures/eoce/GRE_intro/gre_intro.pdf",
)

R_PATHS = (
    "ch_distributions/figures/simpleNormal/simpleNormal.R",
    "ch_distributions/figures/twoSampleNormals/twoSampleNormals.R",
    "ch_distributions/figures/twoSampleNormalsStacked/twoSampleNormalsStacked.R",
    "ch_distributions/figures/satActNormals/satActNormals.R",
    "ch_distributions/figures/satBelow1300/satBelow1300.R",
    "ch_distributions/figures/satAbove1190/satAbove1190.R",
    "ch_distributions/figures/subtractingArea/subtractingArea.R",
    "ch_distributions/figures/satBelow1030/satBelow1030.R",
    "ch_distributions/figures/mikeAndJosePercentiles/mikeAndJosePercentiles.R",
    "ch_distributions/figures/height40Perc/height40Perc.R",
    "ch_distributions/figures/height82Perc/height82Perc.R",
    "ch_distributions/figures/between59And62/between59And62.R",
    "ch_distributions/figures/subtracting2Areas/subtracting2Areas.R",
    "ch_distributions/figures/6895997/6895997.R",
    "ch_distributions/figures/eoce/area_under_curve_1/area_under_curve_1.R",
    "ch_distributions/figures/eoce/GRE_intro/gre_intro.R",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def identity(path: Path) -> dict[str, object]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def require_identity(path: Path, expected: tuple[int, str]) -> None:
    require(path.is_file(), f"missing exact input: {path.relative_to(ROOT)}")
    observed = (path.stat().st_size, sha256(path))
    require(observed == expected, f"identity changed for {path.relative_to(ROOT)}: {observed}")


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def line_number(data: bytes, offset: int) -> int:
    return data[:offset].count(b"\n") + 1


def slice_record(path: Path, data: bytes, start: int, end: int) -> dict[str, object]:
    section = data[start:end]
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "byte_start_zero_based": start,
        "byte_end_exclusive": end,
        "bytes": len(section),
        "line_start_inclusive": line_number(data, start),
        "line_end_inclusive": line_number(data, end - 1),
        "sha256": hashlib.sha256(section).hexdigest(),
    }


def strip_tex_comments(text: str) -> str:
    output: list[str] = []
    for line in text.splitlines():
        match = re.search(r"(?<!\\)%", line)
        output.append(line[: match.start()] if match else line)
    return "\n".join(output)


def normalize_inline_math(value: str) -> str:
    value = re.sub(r"\^\{(?:st|nd|rd|th)\}", "", value)
    return re.sub(r"\s+", "", value)


def inline_math(text: str) -> list[str]:
    return [
        normalize_inline_math(value)
        for value in re.findall(r"(?<!\\)\$(.*?)(?<!\\)\$", text, flags=re.DOTALL)
    ]


def display_signatures(text: str) -> list[list[str]]:
    blocks = re.findall(r"\\begin\{align\*\}(.*?)\\end\{align\*\}", text, flags=re.DOTALL)
    token_pattern = re.compile(
        r"\\(?:frac|times|text|var|resp|mu|sigma|satmean|satsd|shannonsat|"
        r"shannonsatz|edwardsat|edwardsatz|stuartsat|stuarsatz)|"
        r"\d+(?:[.,]\d+)*|[+\-=/^()]"
    )
    return [token_pattern.findall(block) for block in blocks]


def labels(text: str) -> list[str]:
    return re.findall(r"\\label\{([^{}]*(?:\\[A-Za-z]+\{\})?[^{}]*)\}", text)


def references(text: str) -> list[str]:
    return re.findall(r"\\(?:v?ref)\{([^{}]*(?:\\[A-Za-z]+\{\})?[^{}]*)\}", text)


def macro_counts(text: str) -> dict[str, int]:
    patterns = {
        "sections": r"\\section\{",
        "subsections": r"\\subsection\{",
        "worked_examples": r"\\begin\{nexample\}",
        "guided_exercises": r"\\begin\{nexercise\}",
        "inline_public_answers": r"\\footnotetext\{",
        "footnote_links": r"\\footnotemark",
        "figure_environments": r"\\begin\{figure\}",
        "Figure": r"\\Figure(?!s|FullPath)",
        "Figures": r"\\Figures",
        "FigureFullPath": r"\\FigureFullPath",
        "eoce": r"\\eoce\{",
        "public_eoce_answers": r"\\eocesol\{",
        "inputs": r"\\input\{",
        "parts_environments": r"\\begin\{parts\}",
    }
    return {name: len(re.findall(pattern, text)) for name, pattern in patterns.items()}


def load_component_rows() -> dict[str, dict[str, str]]:
    with COMPONENT_CLOSURE.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    result = {row["path"]: row for row in rows}
    require(len(result) == len(rows), "component closure contains duplicate paths")
    return result


def inspect_assets(component_rows: dict[str, dict[str, str]]) -> dict[str, object]:
    pdftotext = shutil.which("pdftotext")
    require(pdftotext is not None, "pdftotext is required for deterministic asset text inspection")
    version_run = subprocess.run([pdftotext, "-v"], capture_output=True, text=True)
    version = (version_run.stderr or version_run.stdout).splitlines()[0]
    allowed_reader_tokens = {
        "X", "Y", "Z", "Ann", "Tom", "Mike", "Jose", "QR", "VR",
        "a", "b", "c", "d",
    }
    pdf_records: list[dict[str, object]] = []
    observed_letter_tokens: set[str] = set()
    for relative in PDF_PATHS:
        path = BASE / Path(relative)
        require(path.is_file(), f"direct PDF absent: {relative}")
        row = component_rows.get(relative)
        require(row is not None, f"direct PDF absent from component closure: {relative}")
        observed = identity(path)
        require(
            (observed["bytes"], observed["sha256"])
            == (int(row["bytes"]), row["sha256"]),
            f"direct PDF/component closure mismatch: {relative}",
        )
        run = subprocess.run(
            [pdftotext, "-layout", str(path), "-"],
            capture_output=True,
            check=False,
        )
        require(run.returncode == 0, f"pdftotext failed for {relative}")
        text = run.stdout.decode("utf-8", errors="replace")
        tokens = sorted(set(re.findall(r"[A-Za-z]+", text)))
        observed_letter_tokens.update(tokens)
        require(
            set(tokens) <= allowed_reader_tokens,
            f"unclassified translatable reader text in {relative}: {tokens}",
        )
        pdf_records.append(
            {
                **observed,
                "component_kind": row["component_kind"],
                "generation_evidence": row["generation_evidence"],
                "rights_resolution": row["rights_resolution"],
                "publication_disposition": row["publication_disposition"],
                "reader_letter_tokens": tokens,
                "localization_disposition": (
                    "reuse_byte_identical_no_translatable_prose; mathematical symbols, "
                    "proper names, and official GRE abbreviations remain unchanged; "
                    "Indonesian TeX alt text supplies the localized accessible description"
                ),
            }
        )

    code_records: list[dict[str, object]] = []
    data_calls = 0
    for relative in R_PATHS:
        path = BASE / Path(relative)
        require(path.is_file(), f"adjacent R source absent: {relative}")
        row = component_rows.get(relative)
        require(row is not None, f"adjacent R source absent from rights closure: {relative}")
        observed = identity(path)
        require(
            (observed["bytes"], observed["sha256"])
            == (int(row["bytes"]), row["sha256"]),
            f"R source/component closure mismatch: {relative}",
        )
        code = path.read_text(encoding="utf-8")
        require("library(openintro)" in code, f"unrecorded R dependency pattern: {relative}")
        require(
            re.search(r"read\.(?:csv|table|delim)|readRDS|load\(|source\(", code) is None,
            f"external local data/source dependency requires closure: {relative}",
        )
        data_calls += code.count("data(COL)")
        code_records.append(
            {
                **observed,
                "component_kind": row["component_kind"],
                "rights_resolution": row["rights_resolution"],
                "publication_disposition": row["publication_disposition"],
                "dependencies": ["R package openintro", *(["package dataset COL"] if "data(COL)" in code else [])],
                "external_local_data_files": [],
            }
        )

    require(observed_letter_tokens <= allowed_reader_tokens, "asset token classification failed")
    return {
        "$schema": "interlanguage.r011-b014-asset-rights-closure/v1",
        "boundary_id": BOUNDARY_ID,
        "status": "PASS_DIRECT_ASSET_CODE_DATA_RIGHTS_CLOSURE_NO_DERIVATIVES_REQUIRED",
        "source_base": "exact admitted B013 candidate source snapshot",
        "component_closure": identity(COMPONENT_CLOSURE),
        "direct_pdf_count": len(pdf_records),
        "adjacent_r_source_count": len(code_records),
        "pdfs": pdf_records,
        "code": code_records,
        "reader_text_classification": {
            "observed_ascii_letter_tokens": sorted(observed_letter_tokens),
            "translatable_prose_tokens": [],
            "unchanged_roles": {
                "Ann/Tom/Mike/Jose": "proper names",
                "X/Y/Z": "mathematical symbols",
                "QR/VR": "official GRE section abbreviations explained in localized prose and alt text",
            },
            "localized_tex_alt_text_complete": True,
            "localized_pdf_derivatives_required": 0,
        },
        "code_data_closure": {
            "runtime_dependency": "R package openintro (upstream generation dependency)",
            "package_dataset_COL_calls": data_calls,
            "local_data_files": [],
            "direct_external_read_load_source_calls": 0,
            "excluded_transient": "ch_distributions/figures/subtractingArea/.Rhistory; classified upstream as transient_not_build_input and not directly referenced",
        },
        "rights_summary": {
            "rights_resolution": "CC-BY-SA-3.0-repository-declaration",
            "publication_disposition": "include_subject_to_attribution_and_brand_exclusion",
            "all_direct_components_exactly_resolved": True,
        },
        "inspection_tool": {"name": "pdftotext", "version": version},
        "localized_asset_output": [],
        "network_used": False,
        "git_used": False,
    }


def main() -> int:
    for path, expected in EXPECTED.items():
        require_identity(path, expected)
    for path in (
        TARGET_CHAPTER_OPENING,
        TARGET_MAIN,
        TARGET_EOCE,
        TARGET_ANSWERS,
        CONTROLLED_TERMS,
    ):
        require(path.is_file(), f"missing B014 authored input: {path.relative_to(ROOT)}")

    base_main = BASE_MAIN.read_bytes()
    authority_main = SOURCE_MAIN.read_bytes()
    require(base_main == authority_main, "B013 base Chapter 4 file is not the pinned authority bytes")
    base_eoce = BASE_EOCE.read_bytes()
    authority_eoce = SOURCE_EOCE.read_bytes()
    require(base_eoce == authority_eoce, "B013 base Section 4.1 EoCE is not pinned authority bytes")

    chapter_open_end_marker = b"  book.}"
    chapter_open_end = authority_main.index(chapter_open_end_marker) + len(
        chapter_open_end_marker
    )
    source_chapter_opening = authority_main[:chapter_open_end]
    target_chapter_opening = TARGET_CHAPTER_OPENING.read_bytes().rstrip(b"\n")
    require(
        target_chapter_opening.startswith(
            b"\\begin{chapterpage}{Distribusi variabel acak}"
        ),
        "target chapter opening start changed",
    )
    require(
        target_chapter_opening.endswith(
            b"tetapi dapat dianggap sebagai materi opsional dalam buku ini.}"
        ),
        "target chapter intro ending changed",
    )
    require(
        b"\\chaptertitle[30]{Distribusi \\titlebreak{} variabel acak}"
        in target_chapter_opening,
        "localized titlebreak splits the fixed noun phrase variabel acak",
    )

    main_start_marker = b"%_________________\n\\section{Normal distribution}\n\\label{normalDist}"
    main_end_marker = b"{\\input{ch_distributions/TeX/normal_distribution.tex}}"
    next_section_marker = b"%_________________\n\\section{Geometric distribution}\n\\label{geomDist}"
    main_start = authority_main.index(main_start_marker)
    main_active_end = authority_main.index(main_end_marker, main_start) + len(main_end_marker)
    lexical_end = authority_main.index(next_section_marker, main_active_end)
    dormant_start_marker = b"%%_________________\n%\\section{Evaluating the normal approximation}"
    dormant_start = authority_main.index(dormant_start_marker, main_active_end)
    index_start = authority_main.index(b"\\index{normal distribution|)}", dormant_start)
    index_end_marker = b"\\index{distribution!normal|)}"
    index_end = authority_main.index(index_end_marker, index_start) + len(index_end_marker)

    source_active_main = authority_main[main_start:main_active_end]
    target_main = TARGET_MAIN.read_bytes().rstrip(b"\n")
    require(target_main.startswith(b"%_________________\n\\section{Distribusi normal}"), "target main start changed")
    require(target_main.endswith(main_end_marker), "target main does not end at exact EoCE input")
    assembled_main = (
        target_chapter_opening
        + base_main[chapter_open_end:main_start]
        + target_main
        + base_main[main_active_end:]
    )
    ASSEMBLED_MAIN.write_bytes(assembled_main)

    answer_start_marker = b"%_______________\n\\eocesolch{Distributions of random variables}"
    answer_end_marker = b"\n\n% 11\n"
    authority_solutions = SOURCE_SOLUTIONS.read_bytes()
    base_solutions = BASE_SOLUTIONS.read_bytes()
    authority_answer_start = authority_solutions.index(answer_start_marker)
    authority_answer_end = authority_solutions.index(answer_end_marker, authority_answer_start)
    base_answer_start = base_solutions.index(answer_start_marker)
    base_answer_end = base_solutions.index(answer_end_marker, base_answer_start)
    source_answers = authority_solutions[authority_answer_start:authority_answer_end]
    require(
        base_solutions[base_answer_start:base_answer_end] == source_answers,
        "B013 base changed the B014 public-answer source slice",
    )
    target_answers = TARGET_ANSWERS.read_bytes().rstrip(b"\n")
    require(target_answers.startswith(b"%_______________\n\\eocesolch{Distribusi variabel acak}"), "target answer header changed")
    assembled_solutions = (
        base_solutions[:base_answer_start] + target_answers + base_solutions[base_answer_end:]
    )
    ASSEMBLED_SOLUTIONS.write_bytes(assembled_solutions)
    shutil.copyfile(BASE_PREFACE, ASSEMBLED_PREFACE)

    require(
        ASSEMBLED_MAIN.read_bytes()[len(target_chapter_opening):
                                   len(target_chapter_opening) + (main_start - chapter_open_end)]
        == base_main[chapter_open_end:main_start]
        and ASSEMBLED_MAIN.read_bytes()[
            len(target_chapter_opening) + (main_start - chapter_open_end) + len(target_main):
        ]
        == base_main[main_active_end:],
        "assembled main changed outside exact chapter-opening and Section 4.1 overlays",
    )
    require(
        ASSEMBLED_SOLUTIONS.read_bytes()[:base_answer_start]
        == base_solutions[:base_answer_start]
        and ASSEMBLED_SOLUTIONS.read_bytes()[base_answer_start + len(target_answers):]
        == base_solutions[base_answer_end:],
        "assembled public solutions changed outside exact overlay",
    )
    require(ASSEMBLED_PREFACE.read_bytes() == BASE_PREFACE.read_bytes(), "preface carry-forward changed")

    source_chapter_opening_text = source_chapter_opening.decode("utf-8")
    target_chapter_opening_text = TARGET_CHAPTER_OPENING.read_text(encoding="utf-8")
    source_main_text = source_active_main.decode("utf-8")
    source_eoce_text = authority_eoce.decode("utf-8")
    source_answer_text = source_answers.decode("utf-8")
    target_main_text = TARGET_MAIN.read_text(encoding="utf-8")
    target_eoce_text = TARGET_EOCE.read_text(encoding="utf-8")
    target_answer_text = TARGET_ANSWERS.read_text(encoding="utf-8")
    require(
        re.search(r"Frederic\s+Gauss", source_main_text) is not None
        and "Carl Friedrich Gauss" in target_main_text
        and "Frederic Gauss" not in target_main_text,
        "documented Gauss attribution correction is absent or ambiguous",
    )
    require(
        re.search(
            r"Q1 = 23\.13, Q3 = 26\.86, IQR = 26\.\s*86 - 23\.13 = 3\.73",
            source_answer_text,
        )
        is not None
        and "Q1 = 23.1264\\degree C" in target_answer_text
        and "Q3 = 26.8736\\degree C" in target_answer_text
        and "IQR = 3.7472\\degree C" in target_answer_text
        and "sekitar 3.75\\degree C" in target_answer_text,
        "documented Celsius quartile/IQR correction is absent or incomplete",
    )
    require(
        source_main_text.count(r"\D{\newpage}") == 6
        and target_main_text.count(r"\D{\newpage}") == 5
        and "\\D{\\newpage}\n\n\\subsection{Normal probability examples}" in source_main_text
        and "\\D{\\newpage}\n\n\\subsection{Contoh peluang normal}" not in target_main_text
        and "\\subsection{Contoh peluang normal}" in target_main_text,
        "the single documented localized forced-page-break reflow is absent or overbroad",
    )
    require(
        source_main_text.count(r"\looseness") == 0
        and target_main_text.count(r"\looseness=-1") == 1
        and "\\begingroup\n\\looseness=-1\nContoh~\\ref{actSAT}" in target_main_text
        and "secara matematis kita mendefinisikan skor-Z sebagai\n\\par\n\\endgroup\n\\begin{align*}" in target_main_text,
        "the single documented Z-score paragraph reflow is absent or overbroad",
    )
    source_bundle = (
        source_chapter_opening_text
        + "\n"
        + source_main_text
        + "\n"
        + source_eoce_text
        + "\n"
        + source_answer_text
    )
    target_bundle = (
        target_chapter_opening_text
        + "\n"
        + target_main_text
        + "\n"
        + target_eoce_text
        + "\n"
        + target_answer_text
    )

    source_counts = macro_counts(source_bundle)
    target_counts = macro_counts(target_bundle)
    require(source_counts == target_counts, f"macro topology changed: {source_counts} != {target_counts}")
    require(labels(source_bundle) == labels(target_bundle), "label identity/order changed")
    require(references(source_bundle) == references(target_bundle), "reference identity/order changed")
    chapter_sections = re.compile(r"\\chaptersection\{([^}]+)\}")
    require(
        chapter_sections.findall(source_chapter_opening_text)
        == chapter_sections.findall(target_chapter_opening_text)
        == [
            "normalDist",
            "assessingNormal",
            "geomDist",
            "binomialModel",
            "negativeBinomial",
            "poisson",
        ],
        "chaptersection identity/order changed",
    )
    require(
        source_chapter_opening_text.count(r"\begin{chapterpage}")
        == target_chapter_opening_text.count(r"\begin{chapterpage}")
        == 1
        and source_chapter_opening_text.count(r"\chapterintro{")
        == target_chapter_opening_text.count(r"\chapterintro{")
        == 1
        and source_chapter_opening_text.count(r"\titlebreak{}")
        == target_chapter_opening_text.count(r"\titlebreak{}")
        == 1,
        "chapter hierarchy macro topology changed",
    )

    source_inline = inline_math(source_bundle)
    target_inline = inline_math(target_bundle)
    require(source_inline == target_inline, "inline mathematical expressions changed beyond ordinal localization")
    source_display = display_signatures(source_bundle)
    target_display = display_signatures(target_bundle)
    require(source_display == target_display, "display-math numeric/operator/command signatures changed")
    bracket_pattern = re.compile(r"\\\[(.*?)\\\]", flags=re.DOTALL)
    bracket_source = [re.sub(r"\s+", "", item) for item in bracket_pattern.findall(source_bundle)]
    bracket_target = [re.sub(r"\s+", "", item) for item in bracket_pattern.findall(target_bundle)]
    require(bracket_source == bracket_target, "display bracket mathematics changed")

    newcommand_pattern = re.compile(r"\\newcommand\{(\\[A-Za-z]+)\}\{([^{}]*)\}")
    require(
        newcommand_pattern.findall(source_main_text)
        == newcommand_pattern.findall(target_main_text),
        "source newcommand names/values changed",
    )
    for code_literal, expected_count in (
        (r"\texttt{> pnorm(1)}", 1),
        (r"\texttt{[1] 0.8413447}", 2),
        (r"\texttt{> pnorm(1300, mean = 1100, sd = 200)}", 1),
    ):
        require(
            source_main_text.count(code_literal)
            == target_main_text.count(code_literal)
            == expected_count,
            f"code literal changed: {code_literal}",
        )

    source_eoce_ids = [int(value) for value in re.findall(r"(?m)^% (\d+)$", source_eoce_text)]
    target_eoce_ids = [int(value) for value in re.findall(r"(?m)^% (\d+)$", target_eoce_text)]
    source_answer_ids = [int(value) for value in re.findall(r"(?m)^% (\d+)$", source_answer_text)]
    target_answer_ids = [int(value) for value in re.findall(r"(?m)^% (\d+)$", target_answer_text)]
    require(source_eoce_ids == target_eoce_ids == list(range(1, 11)), "EoCE IDs/order changed")
    require(source_answer_ids == target_answer_ids == [1, 3, 5, 7, 9], "public answer IDs/order changed")

    active_target = strip_tex_comments(target_bundle)
    require("B014_CONTINUE" not in target_bundle, "translation continuation marker remains")
    require(active_target.count("{") == active_target.count("}"), "target brace count is unbalanced")
    require(re.search(r"\\Figures?\{", active_target) is None, "reader figure lacks localized alt text")
    require(
        "Distribusi variabel acak" in active_target
        and "Dalam bab ini" in active_target
        and "inferensi statistika" in active_target,
        "localized Chapter 4 hierarchy or intro is absent",
    )
    forbidden = (
        "Distributions of random variables",
        "In this chapter",
        "The remaining sections",
        "may be considered optional",
        "Normal distribution facts",
        "Normal distribution model",
        "Standardizing with Z-scores",
        "Finding tail areas",
        "Normal probability examples",
        "Always draw a picture first",
        "Finding areas to the right",
        "Area under the curve, Part I",
        "GRE scores, Part I",
        "Triathlon times, Part I",
        "LA weather, Part I",
        "Find the SD",
        "What percent of",
        "What is the probability",
        "Frederic Gauss",
    )
    residue = {phrase: active_target.casefold().count(phrase.casefold()) for phrase in forbidden}
    require(not any(residue.values()), f"reader-visible English residue remains: {residue}")

    component_rows = load_component_rows()
    asset_qa = inspect_assets(component_rows)
    write_json(ASSET_QA, asset_qa)

    for text_path in (
        "ch_distributions/TeX/ch_distributions.tex",
        "ch_distributions/TeX/normal_distribution.tex",
        "extraTeX/eoceSolutions/eoceSolutions.tex",
    ):
        require(text_path in component_rows, f"text source lacks component rights row: {text_path}")

    source_corrections = [
        {
            "id": "B014-SC001",
            "source_location": "ch_distributions.tex line 48, simpleNormal alt text",
            "source_text": "grad lifting",
            "correction": "gradually lifting",
            "handling": "translated naturally; internal upstream-report candidate only",
        },
        {
            "id": "B014-SC002",
            "source_location": "ch_distributions.tex line 48, simpleNormal alt text",
            "source_text": "an it is the shape",
            "correction": "and it is the shape",
            "handling": "translated naturally; internal upstream-report candidate only",
        },
        {
            "id": "B014-SC003",
            "source_location": "ch_distributions.tex line 90, twoSampleNormalsStacked alt text",
            "source_text": "much narrower and but also much taller",
            "correction": "much narrower but also much taller",
            "handling": "translated naturally; internal upstream-report candidate only",
        },
        {
            "id": "B014-SC004",
            "source_location": "ch_distributions.tex line 416, satAbove1190 alt text",
            "source_text": "shaded for horizontal values larger than 1300",
            "correction": "shaded for values larger than 1190",
            "evidence": "the worked example, macro shannonsat=1190, plotted R source U=1190, and PDF axis all identify 1190",
            "handling": "corrected in localized alt text; internal upstream-report candidate only",
        },
        {
            "id": "B014-SC005",
            "source_location": "ch_distributions.tex line 483, satBelow1030 alt text",
            "source_text": "This area is labeled as 40% (0.40)",
            "correction": "the actual satBelow1030 PDF contains no 40% label and the computed area is 0.3632",
            "handling": "removed the false label claim from localized alt text; internal upstream-report candidate only",
        },
        {
            "id": "B014-SC006",
            "source_location": "ch_distributions.tex lines 535-537",
            "source_text": "the heights of male adults in the US is nearly normal",
            "correction": "the heights ... are nearly normal",
            "handling": "translated naturally; internal upstream-report candidate only",
        },
        {
            "id": "B014-SC007",
            "source_location": "normal_distribution.tex lines 155-159",
            "source_text": "it can be assumed that they to follow a normal distribution",
            "correction": "the temperatures can be assumed to follow a normal distribution",
            "handling": "translated naturally; internal upstream-report candidate only",
        },
        {
            "id": "B014-SC008",
            "source_location": "eoceSolutions.tex answer 3(h), lines 658-661",
            "source_text": "Answer to part (b) would not change ... could not answer parts (d)-(f)",
            "correction": "answers to parts (b)-(c) do not change; parts (d)-(f) require the normal model",
            "evidence": "part (c) only interprets the unchanged Z-scores and does not itself require normality",
            "handling": "corrected in translated public answer; internal upstream-report candidate only",
        },
        {
            "id": "B014-SC009",
            "source_location": "eoceSolutions.tex line 646",
            "source_text": "ch_distributions/figures/eoce/GRE_intro/GRE_intro.pdf",
            "correction": "ch_distributions/figures/eoce/GRE_intro/gre_intro.pdf",
            "evidence": "the committed filename and component closure use lowercase gre_intro.pdf; case mismatch breaks case-sensitive builds",
            "handling": "corrected in translated answer path; internal upstream-report candidate only",
        },
        {
            "id": "B014-SC010",
            "source_location": "ch_distributions.tex lines 38-41",
            "source_text": "Frederic Gauss",
            "correction": "Carl Friedrich Gauss",
            "evidence": "the mathematician after whom the Gaussian distribution is named is Carl Friedrich Gauss",
            "handling": "corrected in localized prose; internal upstream-report candidate only",
        },
        {
            "id": "B014-SC011",
            "source_location": "eoceSolutions.tex answer 9(d), lines 728-731",
            "source_text": "Q1 = 23.13, Q3 = 26.86, IQR = 26.86 - 23.13 = 3.73",
            "correction": "Q1 = 23.1264 C, Q3 = 26.8736 C, IQR = 3.7472 C, approximately 3.75 C",
            "evidence": "under C=(F-32)*5/9, mu_C=25 and sigma_C=25/9; standard-normal quartiles +/-0.6744897502 give Q1=23.1264173606, Q3=26.8735826394, and IQR=3.7471652789",
            "handling": "corrected in translated public answer; internal upstream-report candidate only",
        },
    ]
    require(
        [row["id"] for row in source_corrections]
        == [f"B014-SC{number:03d}" for number in range(1, 12)],
        "source-correction IDs are incomplete or out of order",
    )
    layout_adaptations = [
        {
            "id": "B014-LA001",
            "source_location": "ch_distributions.tex line 393, immediately before Normal probability examples",
            "source_layout": r"\D{\newpage}",
            "localized_layout": "forced digital page break removed",
            "evidence": "the Indonesian deterministic review render placed only three prose lines on the preceding page and left the remainder blank; removing this one inherited break restores readable page flow",
            "scope": "id-ID reader pagination only; prose, mathematics, labels, references, examples, exercises, answers, assets, hierarchy, and source order are unchanged",
            "upstream_report_candidate": False,
        },
        {
            "id": "B014-LA002",
            "source_location": "ch_distributions.tex lines 183-197, paragraph following the satActNormals Figure 4.5 environment",
            "source_layout": "default paragraph line count allowed the final word 'sebagai' to cross the page after Figure 4.5 floated",
            "localized_layout": r"paragraph-local \looseness=-1, scoped with \begingroup/\endgroup",
            "evidence": "the first Indonesian deterministic review render split the sentence 'secara matematis kita mendefinisikan skor-Z sebagai' across pages 138-139 while Figure 4.5 floated between 'skor-Z' and the orphaned word 'sebagai'; shortening only this paragraph by one line is the narrow remedy",
            "scope": "id-ID reader paragraph line-breaking only; prose bytes, mathematics, labels, references, examples, exercises, answers, assets, hierarchy, float order, and source order are unchanged",
            "upstream_report_candidate": False,
        },
    ]

    source_qa = {
        "$schema": "interlanguage.r011-b014-source-closure/v1",
        "boundary_id": BOUNDARY_ID,
        "status": "PASS_EXACT_SOURCE_EOCE_PUBLIC_ANSWER_ASSET_CODE_DATA_RIGHTS_CLOSURE",
        "authority": {
            "repository": "https://github.com/OpenIntroStat/openintro-statistics",
            "branch": "master",
            "commit": "fee25091fb24e89c36296fd67c48c1fcf7a93b6e",
            "tree": "d61cc601e7d97759ce805900520f784d02a0489e",
        },
        "base": {
            "description": "exact visually passed B013 admitted-candidate source snapshot",
            "manifest": identity(BASE_MANIFEST),
            "source_qa": identity(BASE_SOURCE_QA),
            "build_qa": identity(BASE_BUILD_QA),
            "visual_qa": identity(BASE_VISUAL_QA),
            "visual_status": json.loads(BASE_VISUAL_QA.read_text(encoding="utf-8"))["status"],
        },
        "source_files": {
            "main": identity(SOURCE_MAIN),
            "eoce": identity(SOURCE_EOCE),
            "public_answers": identity(SOURCE_SOLUTIONS),
        },
        "boundary": {
            "chapter_hierarchy_and_intro": slice_record(
                SOURCE_MAIN, authority_main, 0, chapter_open_end
            ),
            "lexical_section_to_next_section": slice_record(SOURCE_MAIN, authority_main, main_start, lexical_end),
            "active_reader_body_and_eoce_input": slice_record(SOURCE_MAIN, authority_main, main_start, main_active_end),
            "disabled_legacy_assessing_normal_block": slice_record(SOURCE_MAIN, authority_main, dormant_start, index_start),
            "active_index_closure": slice_record(SOURCE_MAIN, authority_main, index_start, index_end),
            "start": "\\begin{chapterpage}{Distributions of random variables}",
            "end": "immediately before \\section{Geometric distribution} / \\label{geomDist}",
            "translated_reader_units": [
                "Chapter 4 chapterpage hierarchy and chapterintro, authority lines 1-22",
                "Section 4.1 active reader body and EoCE input",
            ],
            "chapter_hierarchy_handling": "localized; labels, chaptersection macros, titlebreak, and order preserved",
            "disabled_block_handling": "carried byte-identical from the B013 base; not reader-visible and not claimed as translated",
        },
        "eoce_closure": {
            "file": identity(SOURCE_EOCE),
            "exercise_ids": list(range(1, 11)),
            "labels": labels(source_eoce_text),
        },
        "public_answer_closure": {
            "slice": slice_record(SOURCE_SOLUTIONS, authority_solutions, authority_answer_start, authority_answer_end),
            "answer_ids": [1, 3, 5, 7, 9],
            "o001_missing_public_answers": [2, 4, 6, 8, 10],
            "restricted_instructor_solutions_accessed": False,
            "restricted_solutions_invented": False,
        },
        "direct_asset_closure": identity(ASSET_QA),
        "text_rights": {
            path: {
                "rights_resolution": component_rows[path]["rights_resolution"],
                "publication_disposition": component_rows[path]["publication_disposition"],
                "rights_evidence": component_rows[path]["rights_evidence"],
            }
            for path in (
                "ch_distributions/TeX/ch_distributions.tex",
                "ch_distributions/TeX/normal_distribution.tex",
                "extraTeX/eoceSolutions/eoceSolutions.tex",
            )
        },
        "source_corrections": source_corrections,
        "localized_layout_adaptations": layout_adaptations,
        "next_cursor": {
            "section": "Geometric distribution",
            "label": "geomDist",
            "line": line_number(authority_main, lexical_end + len(b"%_________________\n")),
            "path": SOURCE_MAIN.relative_to(ROOT).as_posix(),
            "source_identity": identity(SOURCE_MAIN),
        },
        "network_used": False,
        "git_used": False,
        "upstream_contact": False,
    }
    write_json(SOURCE_QA, source_qa)

    probability_witness = FIELD_WITNESS_PROBABILITY.read_text(encoding="utf-8", errors="replace")
    statistics_witness = FIELD_WITNESS_STATISTICS.read_text(encoding="utf-8", errors="replace")
    terminology_rows = CONTROLLED_TERMS.read_text(encoding="utf-8").splitlines()
    require(len(terminology_rows) == 14, "B014 controlled term inventory must contain 13 decisions")
    terminology_qa = {
        "$schema": "interlanguage.r011-b014-terminology-qa/v1",
        "boundary_id": BOUNDARY_ID,
        "status": "PASS_REUSED_ESTABLISHED_FIELD_EVIDENCE_NO_NEW_RESEARCH",
        "production_model": MODEL,
        "instruction_handling": "Reused the established same-field Indonesian witnesses and admitted controlled terminology; no web or arXiv research was repeated.",
        "reused_evidence": {
            "b012_terminology_qa": identity(REUSED_TERMINOLOGY_QA),
            "b012_controlled_terms": identity(REUSED_CONTROLLED_TERMS),
            "admitted_terminology_view": identity(TERMINOLOGY_VIEW),
            "probability_witness_text": identity(FIELD_WITNESS_PROBABILITY),
            "statistics_witness_text": identity(FIELD_WITNESS_STATISTICS),
        },
        "direct_reused_witness_counts": {
            "probability_witness": {
                "distribusi normal": probability_witness.casefold().count("distribusi normal"),
                "distribusi normal baku": probability_witness.casefold().count("distribusi normal baku"),
                "distribusi normal standar": probability_witness.casefold().count("distribusi normal standar"),
                "persentil": probability_witness.casefold().count("persentil"),
            },
            "statistics_witness": {
                "distribusi normal": statistics_witness.casefold().count("distribusi normal"),
                "distribusi normal baku": statistics_witness.casefold().count("distribusi normal baku"),
                "persentil": statistics_witness.casefold().count("persentil"),
            },
        },
        "decisions": identity(CONTROLLED_TERMS),
        "decision_count": 13,
        "key_controls": {
            "normal distribution": "distribusi normal",
            "standard normal distribution": "distribusi normal baku",
            "mean": "rata-rata",
            "standard deviation": "simpangan baku",
            "Z-score": "skor-Z",
            "percentile": "persentil",
            "tail area": "luas ekor",
            "probability table": "tabel peluang",
            "test statistic": "statistik uji",
            "distribution of random variables": "distribusi variabel acak",
        },
        "ordinal_style": "persentil ke-n; English ordinal suffixes inside math were removed without changing numeric values",
        "witness_rights": "Internal terminology evidence only; copyrighted witness bytes remain excluded from public release payloads.",
        "network_used": False,
    }
    write_json(TERMINOLOGY_QA, terminology_qa)

    inactive_english_comments = [
        line
        for line in target_main_text.splitlines()
        if line.lstrip().startswith("%")
        and any(
            phrase in line
            for phrase in (
                "More examples for using",
                "No matter the approach",
                "try the Guided Practice",
                "using your preferred method",
                "This is Shannon's",
                "which is the fraction",
                "of \\shannonsat",
            )
        )
    ]
    translation_qa = {
        "$schema": "interlanguage.r011-b014-final-translation-qa/v1",
        "boundary_id": BOUNDARY_ID,
        "status": "PASS_TERMINAL_SOURCE_CANDIDATE_READY_FOR_ISOLATED_BUILD",
        "production_model": MODEL,
        "authority": {
            "commit": "fee25091fb24e89c36296fd67c48c1fcf7a93b6e",
            "tree": "d61cc601e7d97759ce805900520f784d02a0489e",
        },
        "source_closure": identity(SOURCE_QA),
        "asset_rights_closure": identity(ASSET_QA),
        "terminology_qa": identity(TERMINOLOGY_QA),
        "controlled_terms": identity(CONTROLLED_TERMS),
        "candidate_fragments": {
            "chapter_opening": identity(TARGET_CHAPTER_OPENING),
            "main": identity(TARGET_MAIN),
            "eoce": identity(TARGET_EOCE),
            "public_answers": identity(TARGET_ANSWERS),
        },
        "assemblies": {
            "main": identity(ASSEMBLED_MAIN),
            "public_solutions": identity(ASSEMBLED_SOLUTIONS),
            "preface_carry_forward": identity(ASSEMBLED_PREFACE),
        },
        "coverage": {
            "chapter_hierarchy": "Bab 4 / Distribusi variabel acak",
            "chapter_intro_units": 1,
            "section": "4.1 Distribusi normal / normalDist",
            "subsections": 5,
            "worked_examples": 6,
            "guided_exercises": 15,
            "guided_inline_public_answers": 15,
            "eoce_ids": list(range(1, 11)),
            "public_answer_ids": [1, 3, 5, 7, 9],
            "o001_missing_public_answers": [2, 4, 6, 8, 10],
            "direct_pdf_assets": len(PDF_PATHS),
            "adjacent_r_sources": len(R_PATHS),
        },
        "topology": {
            "macro_counts_source": source_counts,
            "macro_counts_target": target_counts,
            "macro_counts_exact": True,
            "labels": labels(target_bundle),
            "labels_exact_and_ordered": True,
            "references": references(target_bundle),
            "references_exact_and_ordered": True,
            "newcommand_names_values_exact": True,
            "exercise_and_answer_ids_ordered": True,
            "chaptersection_ids": chapter_sections.findall(target_chapter_opening_text),
            "chaptersection_ids_exact_and_ordered": True,
            "chapter_hierarchy_macro_topology_exact": True,
            "forced_digital_page_breaks_source": 6,
            "forced_digital_page_breaks_target": 5,
            "localized_forced_page_breaks_removed": 1,
            "paragraph_looseness_overrides_source": 0,
            "paragraph_looseness_overrides_target": 1,
            "localized_paragraphs_reflowed": 1,
        },
        "mathematics": {
            "inline_math_segments": len(target_inline),
            "inline_math_exact_after_ordinal_suffix_normalization": True,
            "align_display_blocks": len(target_display),
            "display_numeric_operator_command_signatures_exact": True,
            "bracket_display_blocks": len(bracket_target),
            "bracket_display_math_exact": True,
            "code_literals_exact": True,
            "formula_or_data_values_changed": True,
            "formula_or_data_values_changed_only_by_documented_source_correction": True,
            "documented_value_correction_ids": ["B014-SC011"],
        },
        "accessibility": {
            "all_figure_macros_have_localized_alt_text": True,
            "source_figures_without_alt_text_enriched": ["satAbove1030", "height40Perc"],
            "source_alt_text_corrections": ["B014-SC001", "B014-SC002", "B014-SC003", "B014-SC004", "B014-SC005"],
            "reader_visible_asset_text_disposition": "all direct PDFs contain only math/numerals, proper names, or explained official abbreviations; byte-identical reuse is correct",
        },
        "residue": {
            "controlled_reader_visible_english_phrase_counts": residue,
            "reader_visible_residue_zero": True,
            "inactive_english_source_comments_preserved": inactive_english_comments,
            "disabled_legacy_section": "authority lines 755-963 carried byte-identical and not reader-visible",
            "chapter_hierarchy_and_intro_localized": True,
            "untranslated_suffix": "Section 4.2 Geometric distribution and later content remain inherited English beyond B014",
        },
        "source_corrections": source_corrections,
        "localized_layout_adaptations": layout_adaptations,
        "restricted_instructor_solutions_accessed": False,
        "restricted_solutions_invented": False,
        "canonical_mutation": False,
        "backend_mutation": False,
        "control_mutation": False,
        "build_performed": False,
        "admission_performed": False,
        "git_used": False,
        "network_used": False,
        "publication_performed": False,
        "upstream_contact": False,
    }
    write_json(TRANSLATION_QA, translation_qa)

    receipt = {
        "$schema": "interlanguage.r011-b014-translation-candidate-receipt/v1",
        "boundary_id": BOUNDARY_ID,
        "status": "COMPLETE_TERMINAL_SOURCE_CANDIDATE_READY_FOR_ISOLATED_BUILD",
        "recorded_date": DATE,
        "production_model": MODEL,
        "authority": {
            "repository": "https://github.com/OpenIntroStat/openintro-statistics",
            "branch": "master",
            "commit": "fee25091fb24e89c36296fd67c48c1fcf7a93b6e",
            "tree": "d61cc601e7d97759ce805900520f784d02a0489e",
        },
        "base_boundary": "R011-B013",
        "base_inputs": {
            "manifest": identity(BASE_MANIFEST),
            "source_qa": identity(BASE_SOURCE_QA),
            "build_qa": identity(BASE_BUILD_QA),
            "visual_qa": identity(BASE_VISUAL_QA),
        },
        "source_closure": identity(SOURCE_QA),
        "asset_rights_closure": identity(ASSET_QA),
        "terminology_qa": identity(TERMINOLOGY_QA),
        "translation_qa": identity(TRANSLATION_QA),
        "finalizer": identity(Path(__file__)),
        "fragments": [
            identity(TARGET_CHAPTER_OPENING),
            identity(TARGET_MAIN),
            identity(TARGET_EOCE),
            identity(TARGET_ANSWERS),
        ],
        "assemblies": [identity(ASSEMBLED_MAIN), identity(ASSEMBLED_SOLUTIONS), identity(ASSEMBLED_PREFACE)],
        "coverage": translation_qa["coverage"],
        "localized_layout_adaptations": layout_adaptations,
        "o001_missing_public_answers": [2, 4, 6, 8, 10],
        "next_cursor": source_qa["next_cursor"],
        "required_next_gate": "isolated deterministic build and bounded visual QA",
        "canonical_mutation": False,
        "backend_mutation": False,
        "control_mutation": False,
        "release_mutation": False,
        "git_used": False,
        "network_used": False,
        "publication_performed": False,
        "upstream_contact": False,
    }
    write_json(CANDIDATE_RECEIPT, receipt)
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
