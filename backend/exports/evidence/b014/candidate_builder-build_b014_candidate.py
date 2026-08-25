#!/usr/bin/env python3
"""Fail-closed isolated deterministic reader build for R011-B014.

The harness reuses only generic process primitives from the independently
validated B012 builder.  Its base is the exact admitted B013 source snapshot;
the only source mutations are B014's hash-bound Chapter 4 Section 4.1 source,
EoCE, public-answer, and unchanged preface overlays.  All directly referenced
figures remain byte-identical to the admitted base.  Two complete four-pass
LaTeX replays must agree at pass 3, pass 4, final PDF, extracted text, page
count, and trailer ID.

The conventional candidate and bounded high-resolution review renders are QA
artifacts only.  This script never grants visual approval and never writes to
``repo``, ``backend``, ``output``, ``release``, control files, Git, remotes, or
credentials.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import build_b012_candidate as shared


ROOT = Path(__file__).resolve().parents[1]
BOUNDARY_ID = "R011-B014"
MODEL = "OpenAI Codex gpt-5.6-sol, Ultra"
AUTHORITY_COMMIT = "fee25091fb24e89c36296fd67c48c1fcf7a93b6e"
AUTHORITY_TREE = "d61cc601e7d97759ce805900520f784d02a0489e"

BASE_SNAPSHOT = ROOT / "qa" / "b013-build" / "source-snapshot-b013"
BASE_MANIFEST = ROOT / "qa" / "b013-build" / "R011-B013_SOURCE_MANIFEST.tsv"
BASE_SOURCE_QA = ROOT / "qa" / "b013-build" / "R011-B013_SOURCE_QA.json"
BASE_BUILD_RECEIPT = (
    ROOT / "qa" / "b013-build" / "final" / "CANDIDATE_BUILD_QA_B013.json"
)
BASE_PDF = ROOT / "qa" / "b013-build" / "final" / "main.pdf"
BASE_TEXT = ROOT / "qa" / "b013-build" / "final" / "main-final.txt"
BASE_VISUAL_QA = ROOT / "qa" / "b013-visual" / "R011-B013_VISUAL_QA.json"

CANDIDATE = ROOT / "scratch" / "b014-candidate"
PRE_REVIEW = CANDIDATE / "R011-B014_TRANSLATION_CANDIDATE_RECEIPT.json"
FINAL_TRANSLATION_QA = (
    ROOT / "qa" / "b014-translation" / "R011-B014_FINAL_TRANSLATION_QA.json"
)
SOURCE_CLOSURE = ROOT / "qa" / "b014-source" / "R011-B014_SOURCE_CLOSURE.json"
ASSET_CLOSURE = ROOT / "qa" / "b014-assets" / "R011-B014_ASSET_CLOSURE.json"
SOURCE_ASSET_VISUAL_QA = (
    ROOT / "qa" / "b014-assets" / "R011-B014_SOURCE_ASSET_VISUAL_QA.json"
)
B014_TERMINOLOGY_QA = (
    ROOT / "qa" / "b014-terminology" / "R011-B014_TERMINOLOGY_QA.json"
)
B014_CONTROLLED_TERMS = (
    ROOT / "qa" / "b014-terminology" / "R011-B014_CONTROLLED_TERMS.tsv"
)
FINALIZER = ROOT / "qa" / "b014-translation" / "finalize_b014_candidate.py"
FINALIZER_REPLAY_QA = (
    ROOT / "qa" / "b014-translation" / "R011-B014_FINALIZER_REPLAY_QA.json"
)

CHAPTER_FRAGMENT = CANDIDATE / "ch_distributions_chapter_opening_id.tex"
MAIN_FRAGMENT = CANDIDATE / "ch_distributions_section_4_1_id.tex"
EOCE_FRAGMENT = CANDIDATE / "normal_distribution_B014.tex"
ANSWER_FRAGMENT = CANDIDATE / "R011-B014_PUBLIC_ODD_ANSWERS.tex"
FULL_MAIN = CANDIDATE / "ch_distributions_B014_source.tex"
FULL_ANSWERS = CANDIDATE / "eoceSolutions_B014_source.tex"
PREFACE_OVERLAY = CANDIDATE / "preface_B014_source.tex"

BUILD_ROOT = ROOT / "qa" / "b014-build"
SNAPSHOT = BUILD_ROOT / "source-snapshot-b014"
SOURCE_MANIFEST = BUILD_ROOT / "R011-B014_SOURCE_MANIFEST.tsv"
SOURCE_QA = BUILD_ROOT / "R011-B014_SOURCE_QA.json"
RUN_A = BUILD_ROOT / "replay-a"
RUN_B = BUILD_ROOT / "replay-b"
FINAL = BUILD_ROOT / "final"
FINAL_PDF = FINAL / "main.pdf"
FINAL_TEXT = FINAL / "main-final.txt"
BUILD_RECEIPT = FINAL / "CANDIDATE_BUILD_QA_B014.json"
REVIEW_RENDER = BUILD_ROOT / "review-render"
REVIEW_DPI = 180

OVERLAYS: dict[str, Path] = {
    "ch_distributions/TeX/ch_distributions.tex": FULL_MAIN,
    "ch_distributions/TeX/normal_distribution.tex": EOCE_FRAGMENT,
    "extraTeX/eoceSolutions/eoceSolutions.tex": FULL_ANSWERS,
    "extraTeX/preamble/preface.tex": PREFACE_OVERLAY,
}

REQUIRED_BASE_IDENTITIES: dict[str, tuple[int, str]] = {
    "qa/b013-build/R011-B013_SOURCE_MANIFEST.tsv": (
        175582,
        "6a02065e6c765294da8e1354685665042dbd9e8d4015505df89bd771c9ccc4cf",
    ),
    "qa/b013-build/R011-B013_SOURCE_QA.json": (
        20086,
        "f90db23f88166be13801f9f793dc2d647a084ac88a7d835586c1d4c85fe27caa",
    ),
    "qa/b013-build/final/CANDIDATE_BUILD_QA_B013.json": (
        19854,
        "e463ceb1dcbbbbb25e71c4d627741ca285a5532220197c55511f7b9ed18ad2e7",
    ),
    "qa/b013-build/final/main.pdf": (
        22030847,
        "b190e01e6356022a4abb67fc070f46558941191606a2fb908cd94f0c3578765d",
    ),
    "qa/b013-build/final/main-final.txt": (
        1589969,
        "05a8e0292597ed04ade8bd4502c077d6267eefab8c4a239db049a5f3256cce2d",
    ),
    "qa/b013-visual/R011-B013_VISUAL_QA.json": (
        9603,
        "3604af11745add719f2d8c0b3be131035436cfe47aec7a77fdcd78561f6f3f0d",
    ),
}

REQUIRED_BASE_SNAPSHOT_IDENTITIES: dict[str, tuple[int, str]] = {
    "ch_distributions/TeX/ch_distributions.tex": (
        91188,
        "71e4985a1bf31e9dd6897ec2bd246b3b2f8cd62ab55524a5b1bfe791e613a3a9",
    ),
    "ch_distributions/TeX/normal_distribution.tex": (
        7466,
        "c7d98aff4f421d290e4a6e117cdff4d4b7604ee9bbcc7a3e080928d3c963438e",
    ),
    "extraTeX/eoceSolutions/eoceSolutions.tex": (
        109045,
        "a7088158d60ac8dbf9e05720d081633ffad1b829611cf90c85029fc27ca72ed6",
    ),
    "extraTeX/preamble/preface.tex": (
        10080,
        "e2d3dc856591ed58a4a46e5573f694fe92f9b7f65ef428da5997fa1b7a336fb9",
    ),
}

REQUIRED_TERMINAL_IDENTITIES: dict[Path, tuple[int, str]] = {
    CHAPTER_FRAGMENT: (
        747,
        "2fecb1d383974f79b3d25dd80fbed3750fb71a128c013b4717acbec3c9353b2e",
    ),
    MAIN_FRAGMENT: (
        31178,
        "f9ee888b9e123f982ecdaa4163001b19f4b0b36d0fd80de22cc6f339c7ed928c",
    ),
    EOCE_FRAGMENT: (
        7672,
        "8734d288c518db0ac78425d749611f8aa8b24e2f6b9290647c8728d15c3f84e8",
    ),
    ANSWER_FRAGMENT: (
        3418,
        "de489f81695689cba7f58785e70c8506473b1eb1743edbd97c9d1a981b17b628",
    ),
    FULL_MAIN: (
        92782,
        "469f843a2713b0787a069d711d81e3bc72ed5bd49c95f03197e720c53a3e3448",
    ),
    FULL_ANSWERS: (
        109275,
        "2bc93b1bea5dfa79d5b1757a02874bfcb856b8b6ba1a71e66551e85c6a1f5672",
    ),
    PREFACE_OVERLAY: (
        10080,
        "e2d3dc856591ed58a4a46e5573f694fe92f9b7f65ef428da5997fa1b7a336fb9",
    ),
    PRE_REVIEW: (
        6814,
        "e4e920cc02203c021de2390ab0a08e32005babc8968521d0022aa450804fe5d8",
    ),
    FINAL_TRANSLATION_QA: (
        14895,
        "68101ba743e2cd68f62309b545fbed795cd060a898daeb3af6abcc820301025a",
    ),
    SOURCE_CLOSURE: (
        14083,
        "661e86d038696e24321f4db0de4b816d79893d9bb0df401acab48d9eaf67228b",
    ),
    ASSET_CLOSURE: (
        26340,
        "cbdf49edb7a528dcc56d8eadfcd14ac3a0056e756d503949bfdee1886cd364c4",
    ),
    SOURCE_ASSET_VISUAL_QA: (
        2532,
        "c9e05200caf9afe9b7c665463ad2e0f006fb45059ad32e16c7e5c55ca11c6614",
    ),
    B014_TERMINOLOGY_QA: (
        2782,
        "70fefa8a3ba23b45a63617139e911518807e4f98d0532b3dd19c9feca2802dab",
    ),
    B014_CONTROLLED_TERMS: (
        2887,
        "0b0a8fd99031106983ce0de8be7b3926defdc4e3cad31038ab9eefb38272397d",
    ),
    FINALIZER: (
        51514,
        "a9e40fa7e5ec49bcf4376b340bfd907bf3bc35bfcccfdbf245fcf805ae83da16",
    ),
    FINALIZER_REPLAY_QA: (
        1946,
        "6517322eea4daaa97e9c75491c32ad20c3603de51bd9873ccfd35594c0a1d45e",
    ),
}

GateError = shared.GateError
require = shared.require
identity = shared.identity
require_exact = shared.require_exact
require_bound = shared.require_bound
read_json = shared.read_json
canonical_json = shared.canonical_json
rel = shared.rel


def configure_shared() -> None:
    """Point generic B012 process primitives at the isolated B014 paths."""

    shared.ROOT = ROOT
    shared.BOUNDARY_ID = BOUNDARY_ID
    shared.MODEL = MODEL
    shared.AUTHORITY_COMMIT = AUTHORITY_COMMIT
    shared.AUTHORITY_TREE = AUTHORITY_TREE
    shared.BASE_SNAPSHOT = BASE_SNAPSHOT
    shared.BASE_MANIFEST = BASE_MANIFEST
    shared.BASE_SOURCE_QA = BASE_SOURCE_QA
    shared.BASE_BUILD_RECEIPT = BASE_BUILD_RECEIPT
    shared.BASE_PDF = BASE_PDF
    shared.BUILD_ROOT = BUILD_ROOT
    shared.SNAPSHOT = SNAPSHOT
    shared.SOURCE_MANIFEST = SOURCE_MANIFEST
    shared.SOURCE_QA = SOURCE_QA
    shared.RUN_A = RUN_A
    shared.RUN_B = RUN_B
    shared.FINAL = FINAL
    shared.FINAL_PDF = FINAL_PDF
    shared.FINAL_TEXT = FINAL_TEXT
    shared.BUILD_RECEIPT = BUILD_RECEIPT
    shared.REVIEW_RENDER = REVIEW_RENDER


configure_shared()


def verify_base() -> dict[str, Any]:
    require(BASE_SNAPSHOT.is_dir(), f"admitted B013 source snapshot absent: {BASE_SNAPSHOT}")
    files = {
        path: require_exact(ROOT / Path(path), size, digest)
        for path, (size, digest) in REQUIRED_BASE_IDENTITIES.items()
    }
    anchors = {
        path: require_exact(BASE_SNAPSHOT / Path(path), size, digest)
        for path, (size, digest) in REQUIRED_BASE_SNAPSHOT_IDENTITIES.items()
    }
    build = read_json(BASE_BUILD_RECEIPT)
    require(build.get("boundary_id") == "R011-B013", "B013 build receipt boundary changed")
    require(
        build.get("status")
        == "PASS_ISOLATED_TWO_REPLAY_DETERMINISTIC_BUILD_VISUAL_AUDIT_PENDING",
        "B013 build receipt is not its exact deterministic candidate",
    )
    require(build.get("page_count") == 427, "B013 terminal page count changed")
    visual = read_json(BASE_VISUAL_QA)
    require(
        visual.get("status")
        == "PASS_ZERO_VISUAL_DEFECTS_IN_BOUNDARY_AND_TRANSITION_WINDOWS",
        "B013 visual QA is not zero-defect PASS evidence",
    )
    require_bound(visual, BASE_BUILD_RECEIPT)
    require_bound(visual, BASE_PDF)
    return {
        "boundary_id": "R011-B013",
        "files": files,
        "snapshot_anchors": anchors,
        "page_count": 427,
        "visual_status": visual["status"],
    }


def load_manifest() -> dict[str, tuple[int, str]]:
    rows: dict[str, tuple[int, str]] = {}
    for line_number, line in enumerate(
        BASE_MANIFEST.read_text(encoding="utf-8").splitlines(), 1
    ):
        parts = line.split("\t")
        require(len(parts) == 3, f"malformed B013 manifest line {line_number}")
        path, size_text, digest = parts
        require(
            path not in rows and re.fullmatch(r"[0-9a-f]{64}", digest) is not None,
            f"invalid B013 manifest line {line_number}",
        )
        rows[path] = (int(size_text), digest)
    require(len(rows) == 1206, f"B013 source closure count changed: {len(rows)}")
    for path, expected in REQUIRED_BASE_SNAPSHOT_IDENTITIES.items():
        require(rows.get(path) == expected, f"B013 manifest anchor mismatch: {path}")
    return rows


def verify_terminal() -> dict[str, Any]:
    exact = {
        rel(path): require_exact(path, size, digest)
        for path, (size, digest) in REQUIRED_TERMINAL_IDENTITIES.items()
    }
    final_qa = read_json(FINAL_TRANSLATION_QA)
    candidate_receipt = read_json(PRE_REVIEW)
    source_closure = read_json(SOURCE_CLOSURE)
    asset_closure = read_json(ASSET_CLOSURE)
    source_asset_visual = read_json(SOURCE_ASSET_VISUAL_QA)
    terminology = read_json(B014_TERMINOLOGY_QA)
    finalizer_replay = read_json(FINALIZER_REPLAY_QA)

    require(final_qa.get("boundary_id") == BOUNDARY_ID, "translation QA boundary mismatch")
    require(
        final_qa.get("status")
        == "PASS_TERMINAL_SOURCE_CANDIDATE_READY_FOR_ISOLATED_BUILD",
        "translation QA is not terminal build-ready PASS evidence",
    )
    require(candidate_receipt.get("boundary_id") == BOUNDARY_ID, "candidate receipt boundary mismatch")
    require(
        candidate_receipt.get("status")
        == "COMPLETE_TERMINAL_SOURCE_CANDIDATE_READY_FOR_ISOLATED_BUILD",
        "candidate receipt is not terminal build-ready evidence",
    )
    require(
        source_closure.get("status")
        == "PASS_EXACT_SOURCE_EOCE_PUBLIC_ANSWER_ASSET_CODE_DATA_RIGHTS_CLOSURE",
        "source closure is not exact-boundary PASS evidence",
    )
    require(
        asset_closure.get("status")
        == "PASS_DIRECT_ASSET_CODE_DATA_RIGHTS_CLOSURE_NO_DERIVATIVES_REQUIRED",
        "asset closure is not terminal PASS evidence",
    )
    require(
        source_asset_visual.get("status")
        == "PASS_ALL_DIRECT_SOURCE_ASSETS_VISUALLY_READABLE_NO_LOCALIZED_PDF_DERIVATIVES_REQUIRED",
        "source-asset visual QA is not terminal PASS evidence",
    )
    require(
        terminology.get("status")
        == "PASS_REUSED_ESTABLISHED_FIELD_EVIDENCE_NO_NEW_RESEARCH",
        "terminology QA is not terminal PASS evidence",
    )
    require(
        finalizer_replay.get("status")
        == "PASS_TWO_CONSECUTIVE_FINALIZER_RUNS_BYTE_IDENTICAL"
        and finalizer_replay.get("outputs_byte_identical") is True,
        "translation finalizer replay evidence is not byte-identical PASS",
    )
    require(MODEL in json.dumps(final_qa, ensure_ascii=False), "exact model provenance absent")

    candidate_files = (
        CHAPTER_FRAGMENT,
        MAIN_FRAGMENT,
        EOCE_FRAGMENT,
        ANSWER_FRAGMENT,
        FULL_MAIN,
        FULL_ANSWERS,
        PREFACE_OVERLAY,
    )
    for path in candidate_files:
        require_bound(final_qa, path)
        require_bound(candidate_receipt, path)
    for path in (SOURCE_CLOSURE, ASSET_CLOSURE, B014_TERMINOLOGY_QA):
        require_bound(final_qa, path)
        require_bound(candidate_receipt, path)
    require_bound(candidate_receipt, FINAL_TRANSLATION_QA)
    require_bound(candidate_receipt, FINALIZER)
    require_bound(final_qa, B014_CONTROLLED_TERMS)
    require_bound(source_asset_visual, ASSET_CLOSURE)
    for replayed in (
        FULL_MAIN,
        FULL_ANSWERS,
        PREFACE_OVERLAY,
        ASSET_CLOSURE,
        SOURCE_CLOSURE,
        B014_TERMINOLOGY_QA,
        FINAL_TRANSLATION_QA,
        PRE_REVIEW,
    ):
        require_bound(finalizer_replay, replayed)

    topology = final_qa["topology"]
    require(topology["macro_counts_exact"], "terminal macro topology is not exact")
    require(
        topology["macro_counts_source"] == topology["macro_counts_target"],
        "terminal macro counts differ",
    )
    require(
        topology["forced_digital_page_breaks_source"] == 6
        and topology["forced_digital_page_breaks_target"] == 5
        and topology["localized_forced_page_breaks_removed"] == 1
        and topology["paragraph_looseness_overrides_source"] == 0
        and topology["paragraph_looseness_overrides_target"] == 1
        and topology["localized_paragraphs_reflowed"] == 1,
        "terminal localized reflow is absent or overbroad",
    )
    require(
        topology["labels_exact_and_ordered"]
        and topology["references_exact_and_ordered"]
        and topology["exercise_and_answer_ids_ordered"]
        and topology["newcommand_names_values_exact"],
        "terminal source topology ordering is not exact",
    )
    mathematics = final_qa["mathematics"]
    require(
        mathematics["display_numeric_operator_command_signatures_exact"]
        and mathematics["inline_math_exact_after_ordinal_suffix_normalization"]
        and mathematics["bracket_display_math_exact"]
        and mathematics["code_literals_exact"]
        and mathematics["formula_or_data_values_changed"]
        and mathematics[
            "formula_or_data_values_changed_only_by_documented_source_correction"
        ]
        and mathematics["documented_value_correction_ids"] == ["B014-SC011"],
        "terminal formula/data QA is not exact apart from the documented correction",
    )
    require(
        final_qa["residue"]["reader_visible_residue_zero"],
        "terminal translated-boundary residue is nonzero",
    )
    require(
        final_qa["accessibility"]["all_figure_macros_have_localized_alt_text"],
        "localized figure alt-text closure is incomplete",
    )
    require(
        not final_qa["restricted_instructor_solutions_accessed"]
        and not final_qa["restricted_solutions_invented"],
        "restricted-solution boundary violated",
    )

    component_rows: list[dict[str, Any]] = []
    for key in ("pdfs", "code"):
        for row in asset_closure[key]:
            source = ROOT / Path(row["path"])
            component_rows.append(
                require_exact(source, int(row["bytes"]), str(row["sha256"]))
            )
    require(
        len(component_rows) == 37
        and asset_closure["direct_pdf_count"] == 21
        and asset_closure["adjacent_r_source_count"] == 16,
        "direct asset/code closure count changed",
    )
    return {
        "terminal_translation_qa": identity(FINAL_TRANSLATION_QA),
        "candidate_receipt": identity(PRE_REVIEW),
        "source_closure": identity(SOURCE_CLOSURE),
        "asset_closure": identity(ASSET_CLOSURE),
        "source_asset_visual_qa": identity(SOURCE_ASSET_VISUAL_QA),
        "terminology_qa": identity(B014_TERMINOLOGY_QA),
        "controlled_terms": identity(B014_CONTROLLED_TERMS),
        "terminal_finalizer": identity(FINALIZER),
        "terminal_finalizer_replay_qa": identity(FINALIZER_REPLAY_QA),
        "verified_direct_component_rows": len(component_rows),
        "exact_inputs": exact,
    }


def assemble_expected_main(base: bytes, chapter: bytes, fragment: bytes) -> bytes:
    chapter_end_marker = b"  book.}"
    chapter_end = base.index(chapter_end_marker) + len(chapter_end_marker)
    anchor = b"%_________________\n\\section{Normal distribution}"
    end_marker = (
        b"\n\n\n\n%%_________________\n"
        b"%\\section{Evaluating the normal approximation}"
    )
    start = base.find(anchor)
    end = base.find(end_marker, start)
    require(start >= 0 and end >= 0, "B014 main anchors absent")
    require(base.find(anchor, start + 1) < 0, "B014 main start anchor is non-unique")
    return chapter.rstrip(b"\n") + base[chapter_end:start] + fragment + base[end:]


def assemble_expected_answers(base: bytes, answer: bytes) -> bytes:
    start_marker = (
        b"%_______________\n"
        b"\\eocesolch{Distributions of random variables}"
    )
    end_marker = b"\n% 11\n"
    start = base.find(start_marker)
    end = base.find(end_marker, start)
    require(start >= 0 and end >= 0, "B014 public-answer anchors absent")
    require(base.find(start_marker, start + 1) < 0, "B014 answer start is non-unique")
    return base[:start] + answer + base[end:]


def verify_sources() -> dict[str, Any]:
    base_main = (
        BASE_SNAPSHOT / "ch_distributions/TeX/ch_distributions.tex"
    ).read_bytes()
    base_answers = (
        BASE_SNAPSHOT / "extraTeX/eoceSolutions/eoceSolutions.tex"
    ).read_bytes()
    base_preface = (BASE_SNAPSHOT / "extraTeX/preamble/preface.tex").read_bytes()

    require(
        FULL_MAIN.read_bytes()
        == assemble_expected_main(
            base_main, CHAPTER_FRAGMENT.read_bytes(), MAIN_FRAGMENT.read_bytes()
        ),
        "assembled B014 main source is stale or misassembled",
    )
    require(
        FULL_ANSWERS.read_bytes()
        == assemble_expected_answers(base_answers, ANSWER_FRAGMENT.read_bytes()),
        "assembled B014 public answers are stale or misassembled",
    )
    require(PREFACE_OVERLAY.read_bytes() == base_preface, "B014 preface is not exact B013 carry-forward")

    chapter = CHAPTER_FRAGMENT.read_text(encoding="utf-8")
    fragment = MAIN_FRAGMENT.read_text(encoding="utf-8")
    eoce = EOCE_FRAGMENT.read_text(encoding="utf-8")
    answers = ANSWER_FRAGMENT.read_text(encoding="utf-8")
    main_counts = {
        "sections": fragment.count(r"\section{"),
        "subsections": fragment.count(r"\subsection{"),
        "worked_examples": fragment.count(r"\begin{nexample}"),
        "guided_exercises": fragment.count(r"\begin{nexercise}"),
        "guided_inline_answers": fragment.count(r"\footnotetext"),
        "figure_environments": fragment.count(r"\begin{figure}"),
        "inputs": fragment.count(r"\input{"),
    }
    require(
        main_counts
        == {
            "sections": 1,
            "subsections": 5,
            "worked_examples": 6,
            "guided_exercises": 15,
            "guided_inline_answers": 15,
            "figure_environments": 7,
            "inputs": 1,
        },
        f"Section 4.1 structural counts changed: {main_counts}",
    )
    require(
        re.findall(r"\\chaptersection\{([^}]+)\}", chapter)
        == [
            "normalDist",
            "assessingNormal",
            "geomDist",
            "binomialModel",
            "negativeBinomial",
            "poisson",
        ],
        "localized Chapter 4 chaptersection IDs/order changed",
    )
    require(
        "\\begin{chapterpage}{Distribusi variabel acak}" in chapter
        and "\\chaptertitle[30]{Distribusi \\titlebreak{} variabel acak}" in chapter
        and "\\chapterintro{Dalam bab ini," in chapter,
        "localized Chapter 4 hierarchy/intro absent",
    )
    eoce_labels = re.findall(r"\\label\{([^}]+)\}", eoce)
    expected_labels = [
        "area_under_curve_1",
        "area_under_curve_2",
        "GRE_intro",
        "triathlon_times_intro",
        "GRE_cutoffs",
        "triathlon_times_cutoffs",
        "la_weather_intro",
        "CAPM",
        "la_weather_unit_change",
        "find_sd_cholesterol",
    ]
    require(eoce_labels == expected_labels, "EoCE 1-10 labels/order changed")
    require(eoce.count(r"\eoce{") == 10, "EoCE 1-10 closure changed")
    answer_ids = re.findall(r"^% (\d+)$", answers, flags=re.MULTILINE)
    require(
        answer_ids == ["1", "3", "5", "7", "9"]
        and len(re.findall(r"\\eocesol\{", answers)) == 5,
        "public odd-answer closure changed",
    )
    require(
        "Carl Friedrich Gauss" in fragment
        and "Frederic Gauss" not in fragment
        and "Q1 = 23.1264\\degree C" in answers
        and "Q3 = 26.8736\\degree C" in answers
        and "IQR = 3.7472\\degree C" in answers
        and "sekitar 3.75\\degree C" in answers,
        "documented B014 source corrections are not bound into the build inputs",
    )
    require(
        [row["id"] for row in read_json(FINAL_TRANSLATION_QA)["source_corrections"]]
        == [f"B014-SC{number:03d}" for number in range(1, 12)],
        "B014 source-correction closure is incomplete",
    )
    layout_adaptations = read_json(FINAL_TRANSLATION_QA).get(
        "localized_layout_adaptations", []
    )
    require(
        [row.get("id") for row in layout_adaptations]
        == ["B014-LA001", "B014-LA002"]
        and all(row.get("upstream_report_candidate") is False for row in layout_adaptations)
        and fragment.count(r"\D{\newpage}") == 5
        and "\\D{\\newpage}\n\n\\subsection{Contoh peluang normal}" not in fragment
        and fragment.count(r"\looseness=-1") == 1
        and "\\begingroup\n\\looseness=-1\nContoh~\\ref{actSAT}" in fragment
        and "secara matematis kita mendefinisikan skor-Z sebagai\n\\par\n\\endgroup\n\\begin{align*}" in fragment,
        "B014 localized page-flow adaptation is not exactly bound into the build input",
    )

    final_qa = read_json(FINAL_TRANSLATION_QA)
    return {
        "assembled_main_exact": True,
        "assembled_answers_exact": True,
        "preface_exact_B013_carry_forward": True,
        "localized_chapter_hierarchy_and_intro": True,
        "main_counts": main_counts,
        "eoce": {"exercise_ids": list(range(1, 11)), "labels": expected_labels},
        "answers": {
            "public_answer_ids": [1, 3, 5, 7, 9],
            "o001_gaps": [2, 4, 6, 8, 10],
        },
        "formula_topology_exact": final_qa["mathematics"],
        "structural_topology_exact": final_qa["topology"],
        "source_corrections": final_qa["source_corrections"],
        "localized_layout_adaptations": final_qa["localized_layout_adaptations"],
        "direct_pdf_assets_reused_byte_identically": 21,
        "adjacent_r_sources_closed": 16,
    }


def safe_remove(path: Path) -> None:
    resolved = path.resolve()
    resolved.relative_to(BUILD_ROOT.resolve())
    require(resolved != BUILD_ROOT.resolve(), "refusing to remove the entire B014 build root")
    if resolved.is_dir():
        shutil.rmtree(resolved)
    elif resolved.exists():
        resolved.unlink()


def prepare_snapshot(
    rows: dict[str, tuple[int, str]],
    terminal: dict[str, Any],
    base: dict[str, Any],
    *,
    replace: bool,
) -> tuple[dict[str, tuple[int, str]], dict[str, Any]]:
    if SNAPSHOT.exists():
        if not replace:
            raise GateError(f"refusing to overwrite existing B014 snapshot: {rel(SNAPSHOT)}")
        safe_remove(SNAPSHOT)
    shutil.copytree(BASE_SNAPSHOT, SNAPSHOT)
    for relative, source in OVERLAYS.items():
        require(relative in rows, f"B014 overlay path outside B013 source closure: {relative}")
        destination = SNAPSHOT / Path(relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        observed = shared.identity_under(destination, SNAPSHOT)
        rows[relative] = (observed["bytes"], observed["sha256"])
    rows = dict(sorted(rows.items()))
    SOURCE_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    SOURCE_MANIFEST.write_text(
        "".join(f"{path}\t{size}\t{digest}\n" for path, (size, digest) in rows.items()),
        encoding="utf-8",
        newline="\n",
    )
    inventory = shared.verify_manifest_snapshot(SNAPSHOT, rows)
    checks = verify_sources()
    overlays = {
        relative: {
            "source": rel(source),
            "target": f"{rel(SNAPSHOT)}/{relative}",
            **shared.identity_under(SNAPSHOT / Path(relative), SNAPSHOT),
        }
        for relative, source in OVERLAYS.items()
    }
    source_qa = {
        "$schema": "interlanguage.r011-b014-source-qa/v1",
        "boundary_id": BOUNDARY_ID,
        "status": "PASS_ISOLATED_OVERLAY_CLOSURE",
        "authority": {
            "repository": "https://github.com/OpenIntroStat/openintro-statistics",
            "branch": "master",
            "commit": AUTHORITY_COMMIT,
            "tree": AUTHORITY_TREE,
        },
        "base_boundary": "R011-B013",
        "base_evidence": base,
        "base_manifest": identity(BASE_MANIFEST),
        "manifest": {**identity(SOURCE_MANIFEST), "files": len(rows)},
        "snapshot": {"path": rel(SNAPSHOT), **inventory},
        "builder": identity(Path(__file__)),
        "terminal_inputs": terminal,
        "overlays": overlays,
        "checks": checks,
        "expected_visual_audit": {
            "semantic_scope": [
                "title and rights context",
                "preface context",
                "localized Chapter 4 page title and chapter introduction",
                "complete Section 4.1 body including every figure, table, example, and guided exercise",
                "EoCE 4.1-4.10",
                "public answers 4.1, 4.3, 4.5, 4.7, and 4.9",
                "adjacent Section 4.2 transition",
            ],
            "render_dpi": REVIEW_DPI,
            "approval": "NOT_PERFORMED_BY_BUILD_HARNESS",
        },
        "translation_scope": (
            "Localized Chapter 4 page title / Distribusi variabel acak and complete "
            "chapter intro, followed by Section 4.1 / Distribusi normal in source order: five subsections, "
            "six worked examples, fifteen guided exercises with all inline public "
            "answers, EoCE 1-10, and public answers 1, 3, 5, 7, and 9."
        ),
        "o001_gaps": [2, 4, 6, 8, 10],
        "translation_provenance": MODEL,
        "untranslated_suffix": (
            "Section 4.2 Geometric distribution and later material remain inherited "
            "English witnesses beyond B014."
        ),
        "rights_note": (
            "Text/translation retain CC BY-SA 3.0. All twenty-one directly referenced "
            "PDFs are reused byte-identically because they contain no translatable "
            "graphical prose; Indonesian TeX supplies complete localized alt text."
        ),
        "canonical_mutation": False,
        "backend_mutation": False,
        "git_used": False,
        "publication_performed": False,
        "network_used": False,
        "upstream_contact": False,
    }
    SOURCE_QA.write_bytes(canonical_json(source_qa))
    return rows, source_qa


def page_texts(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8", errors="replace").split("\f")


def first_page(
    pages: list[str],
    phrases: Iterable[str],
    minimum: int = 1,
    maximum: int | None = None,
) -> int | None:
    folded = [phrase.casefold() for phrase in phrases]
    last = min(len(pages), maximum or len(pages))
    for number in range(max(1, minimum), last + 1):
        value = pages[number - 1].casefold()
        if any(phrase in value for phrase in folded):
            return number
    return None


def first_page_regex(
    pages: list[str], pattern: str, minimum: int = 1, maximum: int | None = None
) -> int | None:
    compiled = re.compile(pattern, flags=re.IGNORECASE | re.MULTILINE)
    last = min(len(pages), maximum or len(pages))
    for number in range(max(1, minimum), last + 1):
        if compiled.search(pages[number - 1]):
            return number
    return None


def locate_pages(text_path: Path) -> dict[str, Any]:
    pages = page_texts(text_path)
    title = first_page(pages, ["Statistika Berbasis Data"], 1, 3)
    rights = first_page(
        pages,
        ["karya ini bukan produk OpenIntro dan tidak berafiliasi"],
        1,
        4,
    )
    preface = first_page_regex(pages, r"^\s*Prakata\s*$", 3, 8)
    chapter_one = first_page_regex(pages, r"^\s*Bab 1\s*$", 5, 12)
    chapter_opener = first_page_regex(pages, r"^\s*Bab 4\s*$", 128, 145)
    section = first_page_regex(
        pages,
        r"^\s*4\.1\s+Distribusi normal\s*$",
        (chapter_opener or 132) + 1,
        155,
    )

    subsection_patterns = {
        "normal_model": r"4\.1\.1\s+Model distribusi normal",
        "z_scores": r"4\.1\.2\s+Standardisasi dengan skor-Z",
        "tail_areas": r"4\.1\.3\s+Mencari luas ekor",
        "normal_examples": r"4\.1\.4\s+Contoh peluang normal",
        "rule_68_95_997": r"4\.1\.5\s+Kaidah 68-95-99\.7",
    }
    subsection_pages = {
        key: first_page_regex(pages, pattern, section or 132, 175)
        for key, pattern in subsection_patterns.items()
    }
    eoce_first = first_page_regex(
        pages, r"4\.1\s+Luas di bawah kurva, Bagian I", section or 132, 180
    )
    eoce_last = first_page_regex(
        pages, r"4\.10\s+Cari simpangan baku", eoce_first or 132, 185
    )
    next_section = first_page_regex(
        pages, r"^\s*4\.2\s+Geometric distribution\s*$",
        eoce_first or section or 132,
        190,
    )

    public_header = first_page(
        pages, ["Distribusi variabel acak"], 380, 440
    )
    answer_pages = {
        "1": first_page(pages, ["8.85%"], public_header or 380, 440),
        "3": first_page(pages, ["4.3 (a) Verbal:"], public_header or 380, 440),
        "5": first_page(pages, ["Z = 0.84"], public_header or 380, 440),
        "7": first_page(pages, ["P (Z > 1.2) = 0.1151", "P(Z > 1.2) = 0.1151"], public_header or 380, 440),
        "9": first_page(pages, ["3.75"], public_header or 380, 440),
    }
    last_answer = answer_pages["9"]
    next_public_answer = first_page_regex(
        pages, r"\b4\.11\b", last_answer or public_header or 380, 445
    )

    require(title is not None, "localized title context not found")
    require(rights is not None, "localized rights context not found")
    require(preface is not None and chapter_one is not None, "preface context not found")
    require(chapter_opener is not None, "Chapter 4 opener not found")
    require(section is not None, "localized Section 4.1 heading not found")
    require(
        all(page is not None for page in subsection_pages.values()),
        f"one or more Section 4.1 subsection headings absent: {subsection_pages}",
    )
    require(
        eoce_first is not None and eoce_last is not None and eoce_last >= eoce_first,
        "localized EoCE 4.1-4.10 boundary not found",
    )
    require(
        next_section is not None and next_section >= eoce_last,
        "adjacent Section 4.2 transition not found after B014",
    )
    require(public_header is not None, "localized Chapter 4 public-answer heading not found")
    require(
        all(page is not None for page in answer_pages.values()),
        f"one or more public answers 1/3/5/7/9 absent: {answer_pages}",
    )
    require(
        list(answer_pages.values()) == sorted(answer_pages.values()),
        f"public-answer pages are not ordered: {answer_pages}",
    )
    require(next_public_answer is not None, "next inherited public answer 4.11 not found")
    require(134 <= section <= 155, f"Section 4.1 start page drifted: {section}")
    require(140 <= eoce_first <= 180, f"EoCE 4.1 start page drifted: {eoce_first}")
    require(385 <= public_header <= 440, f"public-answer heading drifted: {public_header}")

    return {
        "title_page": title,
        "rights_context_page": rights,
        "preface_start_page": preface,
        "preface_end_page": chapter_one - 1,
        "chapter_4_opener_page": chapter_opener,
        "section_start_page": section,
        "subsection_pages": subsection_pages,
        "eoce_start_page": eoce_first,
        "eoce_last_page": eoce_last,
        "next_section_page": next_section,
        "public_answer_heading_page": public_header,
        "public_answer_pages": answer_pages,
        "next_public_answer_page": next_public_answer,
        "section_body_window": [section, eoce_first - 1],
        "eoce_window": [eoce_first, next_section - 1],
        "affected_main_and_transition_window": [
            chapter_opener,
            min(len(pages), next_section + 1),
        ],
        "public_answer_and_transition_window": [
            public_header,
            min(len(pages), next_public_answer + 1),
        ],
        "transition": "Section 4.1 / Distribusi normal -> Section 4.2 / Geometric distribution",
    }


def reader_checks(text_path: Path, mapping: dict[str, Any]) -> dict[str, Any]:
    pages = page_texts(text_path)
    value = "\n".join(pages)
    expected = [
        "Statistika Berbasis Data",
        "Distribusi variabel acak",
        "Dalam bab ini, kita membahas berbagai distribusi",
        "Bagian-bagian lainnya sesekali akan dirujuk",
        "Distribusi normal",
        "Model distribusi normal",
        "Standardisasi dengan skor-Z",
        "Mencari luas ekor",
        "Contoh peluang normal",
        "Kaidah 68-95-99.7",
        "Luas di bawah kurva, Bagian I",
        "Cari simpangan baku",
        "Distribusi variabel acak",
        "3.75",
    ]
    absent = [term for term in expected if term.casefold() not in value.casefold()]
    require(not absent, f"reader text lacks expected B014 terms/labels: {absent}")
    chapter_context = "\n".join(
        pages[
            mapping["chapter_4_opener_page"] - 1 : mapping["section_start_page"] - 1
        ]
    )
    chapter_forbidden = [
        "Distributions of random variables",
        "In this chapter",
        "The remaining sections",
        "may be considered optional",
    ]
    chapter_remaining = {
        term: chapter_context.casefold().count(term.casefold())
        for term in chapter_forbidden
    }
    require(
        not any(chapter_remaining.values()),
        f"reader-visible Chapter 4 hierarchy/intro English residue remains: {chapter_remaining}",
    )
    boundary_pages = "\n".join(
        pages[
            mapping["section_start_page"] - 1 : mapping["next_section_page"] - 1
        ]
    )
    forbidden = [
        "Normal distribution facts",
        "Normal distribution model",
        "Standardizing with Z-scores",
        "Finding tail areas",
        "Normal probability examples",
        "Always draw a picture first",
        "Area under the curve, Part I",
        "GRE scores, Part I",
        "Triathlon times, Part I",
        "LA weather, Part I",
        "Find the SD",
    ]
    remaining = {
        term: boundary_pages.casefold().count(term.casefold()) for term in forbidden
    }
    require(
        not any(remaining.values()),
        f"reader-visible B014 English residue remains: {remaining}",
    )
    answer_start, answer_end = mapping["public_answer_and_transition_window"]
    answer_text = "\n".join(pages[answer_start - 1 : answer_end])
    answer_forbidden = [
        "Normal distribution centered at 0",
        "What percentile",
        "Answer to part",
        "would not change",
    ]
    answer_remaining = {
        term: answer_text.casefold().count(term.casefold())
        for term in answer_forbidden
    }
    require(
        not any(answer_remaining.values()),
        f"localized B014 public-answer English residue remains: {answer_remaining}",
    )
    return {
        "status": "PASS_TEXT_EXTRACTION_ONLY_VISUAL_PENDING",
        "expected_terms": expected,
        "absent": [],
        "chapter_hierarchy_intro_forbidden_phrase_counts": chapter_remaining,
        "translated_boundary_forbidden_phrase_counts": remaining,
        "localized_public_answer_forbidden_phrase_counts": answer_remaining,
        "source_declared_reader_visible_residue_zero": True,
    }


def expected_review_pages(mapping: dict[str, Any]) -> set[int]:
    pages = {
        mapping["title_page"],
        mapping["rights_context_page"],
    }
    pages.update(
        range(mapping["preface_start_page"], mapping["preface_end_page"] + 1)
    )
    start, end = mapping["affected_main_and_transition_window"]
    pages.update(range(start, end + 1))
    answer_start, answer_end = mapping["public_answer_and_transition_window"]
    pages.update(range(max(1, answer_start - 1), answer_end + 1))
    return {page for page in pages if page > 0}


def render_review_pages(
    pdf: Path,
    mapping: dict[str, Any],
    toolchain: dict[str, str],
    *,
    replace: bool,
) -> list[dict[str, Any]]:
    if REVIEW_RENDER.exists() and any(REVIEW_RENDER.iterdir()):
        if not replace:
            raise GateError(f"refusing to overwrite review renders: {rel(REVIEW_RENDER)}")
        safe_remove(REVIEW_RENDER)
    REVIEW_RENDER.mkdir(parents=True, exist_ok=True)
    artifacts: list[dict[str, Any]] = []
    for page in sorted(expected_review_pages(mapping)):
        prefix = REVIEW_RENDER / f"page-{page:04d}"
        completed = shared.subprocess.run(
            [
                toolchain["pdftoppm"],
                "-f",
                str(page),
                "-l",
                str(page),
                "-png",
                "-r",
                str(REVIEW_DPI),
                str(pdf),
                str(prefix),
            ],
            capture_output=True,
        )
        require(completed.returncode == 0, f"review render failed on page {page}")
        candidates = sorted(REVIEW_RENDER.glob(f"page-{page:04d}-*.png"))
        require(len(candidates) == 1, f"unexpected render inventory on page {page}")
        artifacts.append({"page": page, **identity(candidates[0])})
    require(
        {item["page"] for item in artifacts} == expected_review_pages(mapping),
        "review render inventory does not exactly cover the requested semantic pages",
    )
    return artifacts


def readiness() -> dict[str, Any]:
    base = verify_base()
    rows = load_manifest()
    terminal = verify_terminal()
    checks = verify_sources()
    return {
        "$schema": "interlanguage.r011-b014-build-readiness/v1",
        "boundary_id": BOUNDARY_ID,
        "status": "READY_FOR_TWO_REPLAY_BUILD",
        "ready": True,
        "base": base,
        "base_manifest_rows": len(rows),
        "terminal": terminal,
        "source_checks": checks,
        "write_boundaries": [
            rel(SNAPSHOT),
            rel(SOURCE_MANIFEST),
            rel(SOURCE_QA),
            rel(RUN_A),
            rel(RUN_B),
            rel(FINAL),
            rel(REVIEW_RENDER),
        ],
        "canonical_mutation": False,
        "visual_approval": "OUT_OF_SCOPE_REQUIRES_SEPARATE_AUDIT",
    }


def self_test() -> dict[str, Any]:
    state = readiness()
    try:
        (ROOT / "repo").resolve().relative_to(BUILD_ROOT.resolve())
        path_guard = False
    except ValueError:
        path_guard = True
    require(path_guard, "write-path guard failed")
    state.update(
        {
            "$schema": "interlanguage.r011-b014-build-harness-self-test/v1",
            "status": "PASS_INERT_FAIL_CLOSED_READY",
            "checks": {
                "base_exact": True,
                "terminal_inputs_exact_and_transitively_bound": True,
                "manifest_shape_exact": True,
                "write_path_guard_rejects_repo": True,
                "no_build_executed": True,
                "no_files_written": True,
            },
        }
    )
    return state


def execute_build(*, replace: bool) -> dict[str, Any]:
    base = verify_base()
    terminal = verify_terminal()
    rows = load_manifest()
    rows, _ = prepare_snapshot(rows, terminal, base, replace=replace)
    toolchain = shared.tools()
    trailer_seed = hashlib.sha256(SOURCE_MANIFEST.read_bytes()).hexdigest()[:32].upper()
    run_a = shared.build_once(
        "replay-a", RUN_A, toolchain, trailer_seed, replace=replace
    )
    run_b = shared.build_once(
        "replay-b", RUN_B, toolchain, trailer_seed, replace=replace
    )
    require(
        (run_a["pdf"]["bytes"], run_a["pdf"]["sha256"])
        == (run_b["pdf"]["bytes"], run_b["pdf"]["sha256"]),
        "independent complete replay PDFs differ",
    )
    require(
        (run_a["text"]["bytes"], run_a["text"]["sha256"])
        == (run_b["text"]["bytes"], run_b["text"]["sha256"]),
        "independent complete replay text extractions differ",
    )
    require(run_a["page_count"] == run_b["page_count"], "replay page counts differ")
    require(run_a["trailer_ids"] == run_b["trailer_ids"], "replay trailer IDs differ")

    if FINAL.exists() and any(FINAL.iterdir()):
        if not replace:
            raise GateError(f"refusing to overwrite conventional B014 candidate: {rel(FINAL)}")
        safe_remove(FINAL)
    FINAL.mkdir(parents=True, exist_ok=True)
    shutil.copy2(RUN_A / "main.pdf", FINAL_PDF)
    shutil.copy2(RUN_A / "main-final.txt", FINAL_TEXT)
    final_pdf = identity(FINAL_PDF)
    final_text = identity(FINAL_TEXT)
    require(
        (final_pdf["bytes"], final_pdf["sha256"])
        == (run_a["pdf"]["bytes"], run_a["pdf"]["sha256"]),
        "conventional PDF copy changed bytes",
    )
    require(
        (final_text["bytes"], final_text["sha256"])
        == (run_a["text"]["bytes"], run_a["text"]["sha256"]),
        "conventional text copy changed bytes",
    )
    mapping = locate_pages(FINAL_TEXT)
    text_checks = reader_checks(FINAL_TEXT, mapping)
    renders = render_review_pages(
        FINAL_PDF, mapping, toolchain, replace=replace
    )
    receipt = {
        "$schema": "interlanguage.r011-b014-candidate-build-qa/v1",
        "boundary_id": BOUNDARY_ID,
        "status": "PASS_ISOLATED_TWO_REPLAY_DETERMINISTIC_BUILD_VISUAL_AUDIT_PENDING",
        "authority": {"commit": AUTHORITY_COMMIT, "tree": AUTHORITY_TREE},
        "base_boundary": "R011-B013",
        "base_evidence": base,
        "terminal_inputs": terminal,
        "builder": identity(Path(__file__)),
        "source_qa": identity(SOURCE_QA),
        "source_manifest": {**identity(SOURCE_MANIFEST), "files": len(rows)},
        "snapshot": {
            "path": rel(SNAPSHOT),
            **shared.verify_manifest_snapshot(SNAPSHOT, rows),
        },
        "candidate_artifact": {**final_pdf, "promoted": False},
        "candidate_text": final_text,
        "determinism": {
            "complete_build_replay_a": run_a,
            "complete_build_replay_b": run_b,
            "replay_pdfs_byte_identical": True,
            "replay_text_extractions_byte_identical": True,
            "each_replay_pass3_pass4_byte_identical": True,
            "all_complete_pdf_instances_byte_identical": True,
            "trailer_seed_source": (
                "first 128 bits of SHA-256(R011-B014_SOURCE_MANIFEST.tsv)"
            ),
            "trailer_seed": trailer_seed.lower(),
            "trailer_ids_equal": True,
        },
        "page_count": run_a["page_count"],
        "affected_page_mapping": mapping,
        "reader_checks": text_checks,
        "visual": {
            "status": "RENDERED_ONLY_NOT_VISUALLY_APPROVED",
            "required_next_gate": (
                "Inspect every listed PNG at original detail and record a separate "
                "zero-defect visual QA receipt before admission."
            ),
            "render_dpi": REVIEW_DPI,
            "pages": [item["page"] for item in renders],
            "artifacts": renders,
        },
        "toolchain": {
            name: shared.tool_identity(name, Path(path))
            for name, path in toolchain.items()
        },
        "translation_scope": (
            "Localized Chapter 4 page title / Distribusi variabel acak and complete "
            "chapter intro, followed by Section 4.1 / Distribusi normal in source order: five subsections, "
            "six worked examples, fifteen guided exercises with all inline public "
            "answers, EoCE 1-10, and public answers 1, 3, 5, 7, and 9."
        ),
        "o001_gaps": [2, 4, 6, 8, 10],
        "next_untranslated_anchor": "ch_distributions/TeX/ch_distributions.tex#geomDist",
        "production_model": MODEL,
        "canonical_mutation": False,
        "backend_mutation": False,
        "git_used": False,
        "publication_performed": False,
        "network_used": False,
        "upstream_contact": False,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    if BUILD_RECEIPT.exists():
        raise GateError(f"refusing to overwrite build receipt: {rel(BUILD_RECEIPT)}")
    BUILD_RECEIPT.write_bytes(canonical_json(receipt))
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--self-test", action="store_true")
    action.add_argument("--check-readiness", action="store_true")
    action.add_argument("--build", action="store_true")
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Replace only the exact B014 QA build outputs.",
    )
    args = parser.parse_args()
    if args.replace and not args.build:
        parser.error("--replace is valid only with --build")
    if args.self_test:
        result = self_test()
    elif args.check_readiness:
        result = readiness()
    else:
        result = execute_build(replace=args.replace)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except GateError as exc:
        raise SystemExit(f"REFUSED: {exc}")
