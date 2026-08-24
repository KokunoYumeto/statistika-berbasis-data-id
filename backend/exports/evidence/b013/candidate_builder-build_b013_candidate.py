#!/usr/bin/env python3
"""Fail-closed isolated deterministic build harness for R011-B013.

The harness reuses only the generic process primitives from the independently
validated B012 builder.  Its base is the exact terminal B012 source snapshot;
the only source mutations are B013's hash-bound Section 3.5 assemblies and five
localized figure PDFs.  Two complete four-pass LaTeX replays must agree at
pass 3, pass 4, final PDF, extracted text, page count, and trailer ID.

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
BOUNDARY_ID = "R011-B013"
MODEL = "OpenAI Codex gpt-5.6-sol, Ultra"
AUTHORITY_COMMIT = "fee25091fb24e89c36296fd67c48c1fcf7a93b6e"
AUTHORITY_TREE = "d61cc601e7d97759ce805900520f784d02a0489e"

BASE_SNAPSHOT = ROOT / "qa" / "b012-build" / "source-snapshot-b012"
BASE_MANIFEST = ROOT / "qa" / "b012-build" / "R011-B012_SOURCE_MANIFEST.tsv"
BASE_SOURCE_QA = ROOT / "qa" / "b012-build" / "R011-B012_SOURCE_QA.json"
BASE_BUILD_RECEIPT = (
    ROOT / "qa" / "b012-build" / "final" / "CANDIDATE_BUILD_QA_B012.json"
)
BASE_PDF = ROOT / "qa" / "b012-build" / "final" / "main.pdf"
BASE_TEXT = ROOT / "qa" / "b012-build" / "final" / "main-final.txt"
BASE_VISUAL_QA = ROOT / "qa" / "b012-visual" / "R011-B012_VISUAL_QA.json"
BASE_ASSET_CLOSURE = (
    ROOT / "scratch" / "b012-assets" / "R011-B012_ASSET_CLOSURE.json"
)
BASE_TRANSLATION_QA = (
    ROOT / "scratch" / "b012-candidate" / "R011-B012_FINAL_TRANSLATION_QA.json"
)
BASE_CANDIDATE_RECEIPT = (
    ROOT
    / "scratch"
    / "b012-candidate"
    / "R011-B012_TRANSLATION_CANDIDATE_RECEIPT.json"
)

CANDIDATE = ROOT / "scratch" / "b013-candidate"
PRE_REVIEW = CANDIDATE / "R011-B013_TRANSLATION_CANDIDATE_RECEIPT.json"
FINAL_TRANSLATION_QA = (
    ROOT / "qa" / "b013-translation" / "R011-B013_FINAL_TRANSLATION_QA.json"
)
SOURCE_CLOSURE = ROOT / "qa" / "b013-source" / "R011-B013_SOURCE_CLOSURE.json"
ASSET_CLOSURE = ROOT / "qa" / "b013-assets" / "R011-B013_ASSET_CLOSURE.json"
LOCALIZED_FIGURE_RECEIPT = (
    ROOT / "qa" / "b013-assets" / "R011-B013_LOCALIZED_FIGURE_RECEIPT.json"
)
LOCALIZATION_PRODUCER = ROOT / "qa" / "b013-assets" / "localize_figures_b013.py"
B012_TERMINOLOGY_QA = (
    ROOT / "qa" / "b012-terminology" / "R011-B012_TERMINOLOGY_QA.json"
)
B012_CONTROLLED_TERMS = (
    ROOT / "qa" / "b012-terminology" / "R011-B012_CONTROLLED_TERMS.tsv"
)

MAIN_FRAGMENT = CANDIDATE / "ch_probability_section_3_5_id.tex"
EOCE_FRAGMENT = CANDIDATE / "continuous_distributions_B013.tex"
ANSWER_FRAGMENT = CANDIDATE / "R011-B013_PUBLIC_ODD_ANSWERS.tex"
FULL_MAIN = CANDIDATE / "ch_probability_B013_source.tex"
FULL_ANSWERS = CANDIDATE / "eoceSolutions_B013_source.tex"
PREFACE_OVERLAY = CANDIDATE / "preface_B013_source.tex"

LOCALIZED_PDFS: dict[str, Path] = {
    "ch_probability/figures/fdicHistograms/fdicHistograms.pdf": (
        CANDIDATE
        / "assets"
        / "ch_probability"
        / "figures"
        / "fdicHistograms"
        / "fdicHistograms.pdf"
    ),
    "ch_probability/figures/usHeightsHist180185/usHeightsHist180185.pdf": (
        CANDIDATE
        / "assets"
        / "ch_probability"
        / "figures"
        / "usHeightsHist180185"
        / "usHeightsHist180185.pdf"
    ),
    "ch_probability/figures/fdicHeightContDist/fdicHeightContDist.pdf": (
        CANDIDATE
        / "assets"
        / "ch_probability"
        / "figures"
        / "fdicHeightContDist"
        / "fdicHeightContDist.pdf"
    ),
    "ch_probability/figures/fdicHeightContDistFilled/fdicHeightContDistFilled.pdf": (
        CANDIDATE
        / "assets"
        / "ch_probability"
        / "figures"
        / "fdicHeightContDistFilled"
        / "fdicHeightContDistFilled.pdf"
    ),
    "ch_probability/figures/eoce/cat_weights/cat_weights.pdf": (
        CANDIDATE
        / "assets"
        / "ch_probability"
        / "figures"
        / "eoce"
        / "cat_weights"
        / "cat_weights.pdf"
    ),
}

BUILD_ROOT = ROOT / "qa" / "b013-build"
SNAPSHOT = BUILD_ROOT / "source-snapshot-b013"
SOURCE_MANIFEST = BUILD_ROOT / "R011-B013_SOURCE_MANIFEST.tsv"
SOURCE_QA = BUILD_ROOT / "R011-B013_SOURCE_QA.json"
RUN_A = BUILD_ROOT / "replay-a"
RUN_B = BUILD_ROOT / "replay-b"
FINAL = BUILD_ROOT / "final"
FINAL_PDF = FINAL / "main.pdf"
FINAL_TEXT = FINAL / "main-final.txt"
BUILD_RECEIPT = FINAL / "CANDIDATE_BUILD_QA_B013.json"
REVIEW_RENDER = BUILD_ROOT / "review-render"
REVIEW_DPI = 144

OVERLAYS: dict[str, Path] = {
    "ch_probability/TeX/ch_probability.tex": FULL_MAIN,
    "ch_probability/TeX/continuous_distributions.tex": EOCE_FRAGMENT,
    "extraTeX/eoceSolutions/eoceSolutions.tex": FULL_ANSWERS,
    "extraTeX/preamble/preface.tex": PREFACE_OVERLAY,
    **LOCALIZED_PDFS,
}

REQUIRED_BASE_IDENTITIES: dict[str, tuple[int, str]] = {
    "qa/b012-build/R011-B012_SOURCE_MANIFEST.tsv": (
        175582,
        "711c14901b07b385fd19d13bfafb04cf842d84d328ed60d5a770e7f67c9d62de",
    ),
    "qa/b012-build/R011-B012_SOURCE_QA.json": (
        15575,
        "95a8b83e97ef22f5f124ce8079ec764a66923ac3dfdabf8c21170e7d8d4047d2",
    ),
    "qa/b012-build/final/CANDIDATE_BUILD_QA_B012.json": (
        16590,
        "17704eaba27975ba3489e501a9b4e5169dc668feb357e675fd316cb324cd6355",
    ),
    "qa/b012-build/final/main.pdf": (
        22028312,
        "5f1efd0f201cdedc1802e6393b608a075f05b23c77bc61f9460fb5c1a3c42e82",
    ),
    "qa/b012-build/final/main-final.txt": (
        1589022,
        "d1f4fa2c6efde0db57424f291db0decadcf6ad0f2d4b6d9c351d7f6023f207c4",
    ),
    "qa/b012-visual/R011-B012_VISUAL_QA.json": (
        7206,
        "ebb6c77e09d2dbfa696d5f2045f42200db79604b5c87bde6a18c3800bbf7896b",
    ),
    "scratch/b012-assets/R011-B012_ASSET_CLOSURE.json": (
        7804,
        "1de02ff1c58a63c48f227e7208dd303003328b4bd3e2ad1988d3b74ae124c60f",
    ),
    "scratch/b012-candidate/R011-B012_FINAL_TRANSLATION_QA.json": (
        11161,
        "de0cd90ac9bec7185e212f4e56bc04329d3b9202340d7b6545095fa8750cb9e4",
    ),
    "scratch/b012-candidate/R011-B012_TRANSLATION_CANDIDATE_RECEIPT.json": (
        23788,
        "f2513dd8aa29eb4915ddbaf76005fc839e100939ad37b71a062d0823569aca6f",
    ),
}

REQUIRED_BASE_SNAPSHOT_IDENTITIES: dict[str, tuple[int, str]] = {
    "ch_probability/TeX/ch_probability.tex": (
        135478,
        "c294c872ea02e1a72e74e1daf623e3a405069ae01d5b4c0529c9853f5b7e7fb4",
    ),
    "ch_probability/TeX/continuous_distributions.tex": (
        2358,
        "42de1d525152bc5e5f85112963fdf7e9e5117b4148434046cde2b6fa17100cfe",
    ),
    "extraTeX/eoceSolutions/eoceSolutions.tex": (
        109040,
        "5eea635826351b4176eaaf73e3496e15402ca856933fa9b17f520726340aa56f",
    ),
    "extraTeX/preamble/preface.tex": (
        10080,
        "e2d3dc856591ed58a4a46e5573f694fe92f9b7f65ef428da5997fa1b7a336fb9",
    ),
    "ch_probability/figures/fdicHistograms/fdicHistograms.pdf": (
        10060,
        "71302f94a80df3afbc9a82deaf7b751b822c34b4e05c0527cb00c381d2083162",
    ),
    "ch_probability/figures/usHeightsHist180185/usHeightsHist180185.pdf": (
        5777,
        "3fc3fead04b32067b15e6863c6ad4776351e10e75955a1498dc1692141206c42",
    ),
    "ch_probability/figures/fdicHeightContDist/fdicHeightContDist.pdf": (
        8337,
        "fc6179b789afdeca709a6ce707cf5111c71a43a3ef43e5bb42ae6a3a778d4952",
    ),
    "ch_probability/figures/fdicHeightContDistFilled/fdicHeightContDistFilled.pdf": (
        8627,
        "10a87bce4c78fd6708770798f471e5c91c6093d758ac0e115d772ea7853a9149",
    ),
    "ch_probability/figures/eoce/cat_weights/cat_weights.pdf": (
        4416,
        "26dd765ba632563b41e40aee564dfc1eb456e34464ae318685140729c786d72e",
    ),
}

REQUIRED_TERMINAL_IDENTITIES: dict[Path, tuple[int, str]] = {
    MAIN_FRAGMENT: (
        8408,
        "bf83c6246adefe3991c829bbac95bcf8c84e0f41d8aa0971e0ac8cd00a9d2ac8",
    ),
    EOCE_FRAGMENT: (
        2560,
        "56b62ea8894708982731f0301e9c349bd39d8b78658567d9b115d0c5d7de42d4",
    ),
    ANSWER_FRAGMENT: (
        129,
        "3e46786830b0abee53fef55be9bbfd6ff3768c1fe27542406f9a2224cd733b32",
    ),
    FULL_MAIN: (
        135993,
        "808c3ff7245eb5f36561efff68f48f79511067b4e87e0819568bad21e642af8a",
    ),
    FULL_ANSWERS: (
        109045,
        "a7088158d60ac8dbf9e05720d081633ffad1b829611cf90c85029fc27ca72ed6",
    ),
    PREFACE_OVERLAY: (
        10080,
        "e2d3dc856591ed58a4a46e5573f694fe92f9b7f65ef428da5997fa1b7a336fb9",
    ),
    PRE_REVIEW: (
        4231,
        "3dbce6303273a1c119a3669054a5cd4950f5b3311c6ae546e00951134d89af88",
    ),
    FINAL_TRANSLATION_QA: (
        8207,
        "8a793373b170e5a5714269b86ee2fe2a2f1cd56f6aa73e73e9bfe04c1a9ece68",
    ),
    SOURCE_CLOSURE: (
        3562,
        "5bce21fee2d5aa4fcad43a225ce3435eb723596e10e41129c29f16da46ca0f46",
    ),
    ASSET_CLOSURE: (
        6455,
        "aee8e115d6fdf22ee8d04ba96dc8e0283596ec9279ce08c1bd6cd979c08b362e",
    ),
    LOCALIZED_FIGURE_RECEIPT: (
        4545,
        "7f4fe802268f8af97447fb0abb09825f84f86ae5179a2bc0fd86d11b2efca106",
    ),
    LOCALIZATION_PRODUCER: (
        8857,
        "525b643ad97e925f8397d07701cfdb552a196d55d86c4b5e19813f8788953ef4",
    ),
    B012_TERMINOLOGY_QA: (
        6408,
        "6a209eedb8e01949a0d77b16b8af348c1216ee20f34782ec6b87fde2093f22f7",
    ),
    B012_CONTROLLED_TERMS: (
        2343,
        "50574600ce8397a31e3be124e84d0e85565f2aa033c93ed9612ee1a57e05c713",
    ),
    LOCALIZED_PDFS[
        "ch_probability/figures/fdicHistograms/fdicHistograms.pdf"
    ]: (
        10608,
        "dd345af6e78837437855c6f8c4e3b6f1193f6165f52d9cb63aef092223781eb5",
    ),
    LOCALIZED_PDFS[
        "ch_probability/figures/usHeightsHist180185/usHeightsHist180185.pdf"
    ]: (
        6055,
        "70c184719b5d4f503efe5381db9d620631b0014946ea794a7714bd77de16f64b",
    ),
    LOCALIZED_PDFS[
        "ch_probability/figures/fdicHeightContDist/fdicHeightContDist.pdf"
    ]: (
        8599,
        "d06edc5d3aa0971882361aa55b95e3d8cdc7bcb0ec6fc6d0a6520748b0afbfe3",
    ),
    LOCALIZED_PDFS[
        "ch_probability/figures/fdicHeightContDistFilled/fdicHeightContDistFilled.pdf"
    ]: (
        8879,
        "6bec72771ef11af7184bd997f75b0537b5c355f66b3f95d0c77f10dec2f77932",
    ),
    LOCALIZED_PDFS[
        "ch_probability/figures/eoce/cat_weights/cat_weights.pdf"
    ]: (
        4687,
        "493295b9e642e54ee0eb09fc04f6114925ed0e929778b99fae770eab2d3f0635",
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
    """Point generic B012 process primitives at the isolated B013 paths."""

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
    require(BASE_SNAPSHOT.is_dir(), f"terminal B012 source snapshot absent: {BASE_SNAPSHOT}")
    files = {
        path: require_exact(ROOT / Path(path), size, digest)
        for path, (size, digest) in REQUIRED_BASE_IDENTITIES.items()
    }
    anchors = {
        path: require_exact(BASE_SNAPSHOT / Path(path), size, digest)
        for path, (size, digest) in REQUIRED_BASE_SNAPSHOT_IDENTITIES.items()
    }
    build = read_json(BASE_BUILD_RECEIPT)
    require(build.get("boundary_id") == "R011-B012", "B012 build receipt boundary changed")
    require(
        build.get("status")
        == "PASS_ISOLATED_TWO_REPLAY_DETERMINISTIC_BUILD_VISUAL_AUDIT_PENDING",
        "B012 build receipt is not its exact terminal deterministic candidate",
    )
    require(build.get("page_count") == 427, "B012 terminal page count changed")
    visual = read_json(BASE_VISUAL_QA)
    require(
        visual.get("status") == "PASS_ZERO_VISUAL_DEFECTS_IN_BOUNDARY_WINDOW",
        "B012 visual QA is not zero-defect PASS evidence",
    )
    require_bound(visual, BASE_BUILD_RECEIPT)
    require_bound(visual, BASE_PDF)
    assets = read_json(BASE_ASSET_CLOSURE)
    require(
        assets.get("status")
        == "PASS_BOUNDED_FOUR_FIGURE_CLOSURE_TWO_LOCALIZED_DERIVATIVES",
        "B012 asset closure is not terminal PASS evidence",
    )
    return {
        "boundary_id": "R011-B012",
        "files": files,
        "snapshot_anchors": anchors,
        "page_count": 427,
    }


def load_manifest() -> dict[str, tuple[int, str]]:
    rows: dict[str, tuple[int, str]] = {}
    for line_number, line in enumerate(
        BASE_MANIFEST.read_text(encoding="utf-8").splitlines(), 1
    ):
        parts = line.split("\t")
        require(len(parts) == 3, f"malformed B012 manifest line {line_number}")
        path, size_text, digest = parts
        require(
            path not in rows and re.fullmatch(r"[0-9a-f]{64}", digest) is not None,
            f"invalid B012 manifest line {line_number}",
        )
        rows[path] = (int(size_text), digest)
    require(len(rows) == 1206, f"B012 source closure count changed: {len(rows)}")
    for path, expected in REQUIRED_BASE_SNAPSHOT_IDENTITIES.items():
        require(rows.get(path) == expected, f"B012 manifest anchor mismatch: {path}")
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
    localized_receipt = read_json(LOCALIZED_FIGURE_RECEIPT)

    require(final_qa.get("boundary_id") == BOUNDARY_ID, "translation QA boundary mismatch")
    require(
        final_qa.get("status")
        == "PASS_COMPLETE_TERMINAL_SOURCE_CANDIDATE_READY_FOR_BUILD",
        "translation QA is not terminal build-ready PASS evidence",
    )
    require(candidate_receipt.get("boundary_id") == BOUNDARY_ID, "candidate receipt boundary mismatch")
    require(
        candidate_receipt.get("status")
        == "COMPLETE_TERMINAL_SOURCE_CANDIDATE_READY_FOR_BUILD",
        "candidate receipt is not terminal build-ready evidence",
    )
    require(
        source_closure.get("status") == "PASS_EXACT_PINNED_CLOSED_BOUNDARY",
        "source closure is not exact-boundary PASS evidence",
    )
    require(
        asset_closure.get("status")
        == "PASS_COMPLETE_DIRECT_ASSET_RIGHTS_AND_LOCALIZATION_CLOSURE",
        "asset closure is not terminal PASS evidence",
    )
    require(
        localized_receipt.get("status") == "PASS_EXACT_LABEL_ONLY_LOCALIZATION",
        "localized-figure receipt is not terminal PASS evidence",
    )
    require(MODEL in json.dumps(final_qa, ensure_ascii=False), "exact model provenance absent")

    candidate_files = (
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
    for path in (SOURCE_CLOSURE, ASSET_CLOSURE):
        require_bound(final_qa, path)
        require_bound(candidate_receipt, path)
    require_bound(candidate_receipt, FINAL_TRANSLATION_QA)
    require_bound(candidate_receipt, LOCALIZED_FIGURE_RECEIPT)
    require_bound(asset_closure, LOCALIZATION_PRODUCER)
    require_bound(asset_closure, LOCALIZED_FIGURE_RECEIPT)
    require_bound(final_qa, B012_TERMINOLOGY_QA)
    require_bound(final_qa, B012_CONTROLLED_TERMS)
    for path in LOCALIZED_PDFS.values():
        require_bound(asset_closure, path)
        require_bound(localized_receipt, path)

    require(
        final_qa["structural_topology"]["macro_counts_source"]
        == final_qa["structural_topology"]["macro_counts_target"],
        "terminal macro topology is not exact",
    )
    for key in ("labels", "refs", "citations", "data_variable_identifiers"):
        require(
            final_qa["structural_topology"][f"{key}_source"]
            == final_qa["structural_topology"][f"{key}_target"],
            f"terminal {key} topology is not exact",
        )
    require(
        final_qa["formula_qa"]["display_numeric_operator_command_signatures_exact"]
        and final_qa["formula_qa"]["inline_math_exact"],
        "terminal formula QA is not exact",
    )
    require(
        final_qa["residue_qa"]["reader_visible_english_sentence_residue"] == 0,
        "terminal translated-boundary residue is nonzero",
    )
    return {
        "terminal_translation_qa": identity(FINAL_TRANSLATION_QA),
        "candidate_receipt": identity(PRE_REVIEW),
        "source_closure": identity(SOURCE_CLOSURE),
        "asset_closure": identity(ASSET_CLOSURE),
        "localized_figure_receipt": identity(LOCALIZED_FIGURE_RECEIPT),
        "localization_producer": identity(LOCALIZATION_PRODUCER),
        "reused_terminology_qa": identity(B012_TERMINOLOGY_QA),
        "reused_controlled_terms": identity(B012_CONTROLLED_TERMS),
        "localized_pdfs": [identity(path) for path in LOCALIZED_PDFS.values()],
        "exact_inputs": exact,
    }


def assemble_expected_main(base: bytes, fragment: bytes) -> bytes:
    anchor = b"%_________________\n\\section{Continuous distributions}"
    start = base.find(anchor)
    require(start >= 0 and base.find(anchor, start + 1) < 0, "B013 main anchor absent/non-unique")
    value = base[:start] + fragment
    if not value.endswith(b"\n"):
        value += b"\n"
    return value


def assemble_expected_answers(base: bytes, answer: bytes) -> bytes:
    start_marker = b"% 37\n\n\\eocesol{Approximate answers are OK."
    end_marker = b"\n% 39\n"
    start = base.find(start_marker)
    end = base.find(end_marker, start)
    require(start >= 0 and end >= 0, "B013 public-answer anchors absent")
    require(base.find(start_marker, start + 1) < 0, "B013 public-answer start is non-unique")
    return base[:start] + answer.rstrip(b"\n") + base[end:]


def verify_sources() -> dict[str, Any]:
    base_main = (BASE_SNAPSHOT / "ch_probability/TeX/ch_probability.tex").read_bytes()
    base_answers = (
        BASE_SNAPSHOT / "extraTeX/eoceSolutions/eoceSolutions.tex"
    ).read_bytes()
    base_preface = (BASE_SNAPSHOT / "extraTeX/preamble/preface.tex").read_bytes()

    require(
        FULL_MAIN.read_bytes() == assemble_expected_main(base_main, MAIN_FRAGMENT.read_bytes()),
        "assembled B013 main source is stale or misassembled",
    )
    require(
        FULL_ANSWERS.read_bytes()
        == assemble_expected_answers(base_answers, ANSWER_FRAGMENT.read_bytes()),
        "assembled B013 public answers are stale or misassembled",
    )
    require(PREFACE_OVERLAY.read_bytes() == base_preface, "B013 preface is not exact B012 carry-forward")

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
            "subsections": 2,
            "worked_examples": 3,
            "guided_exercises": 2,
            "guided_inline_answers": 2,
            "figure_environments": 4,
            "inputs": 1,
        },
        f"Section 3.5 structural counts changed: {main_counts}",
    )
    require(
        re.findall(r"\\label\{([^}]+)\}", eoce)
        == ["cat_weights", "income_gender"],
        "EoCE 37-38 labels/order changed",
    )
    require(eoce.count(r"\eoce{") == 2 and eoce.count("\n}{}") == 2, "EoCE 37-38 closure changed")
    require(
        re.findall(r"^% (\d+)$", answers, flags=re.MULTILINE) == ["37"]
        and answers.count(r"\eocesol{") == 1,
        "public answer 37 closure changed",
    )
    require(r"\var{height}" in fragment and r"\var{tinggi}" not in fragment, "source data-variable ID changed")
    for relative, path in LOCALIZED_PDFS.items():
        require(path.is_file(), f"localized overlay absent: {relative}")

    final_qa = read_json(FINAL_TRANSLATION_QA)
    return {
        "assembled_main_exact": True,
        "assembled_answers_exact": True,
        "preface_exact_B012_carry_forward": True,
        "main_counts": main_counts,
        "eoce": {"exercise_ids": [37, 38], "labels": ["cat_weights", "income_gender"]},
        "answers": {"public_answer_ids": [37], "o001_gaps": [38]},
        "formula_topology_exact": final_qa["formula_qa"],
        "structural_topology_exact": final_qa["structural_topology"],
        "source_corrections": final_qa["source_corrections"],
        "localized_asset_paths": list(LOCALIZED_PDFS),
    }


def safe_remove(path: Path) -> None:
    resolved = path.resolve()
    resolved.relative_to(BUILD_ROOT.resolve())
    require(resolved != BUILD_ROOT.resolve(), "refusing to remove the entire B013 build root")
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
            raise GateError(f"refusing to overwrite existing B013 snapshot: {rel(SNAPSHOT)}")
        safe_remove(SNAPSHOT)
    shutil.copytree(BASE_SNAPSHOT, SNAPSHOT)
    for relative, source in OVERLAYS.items():
        require(relative in rows, f"B013 overlay path outside B012 source closure: {relative}")
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
        "$schema": "interlanguage.r011-b013-source-qa/v1",
        "boundary_id": BOUNDARY_ID,
        "status": "PASS_ISOLATED_OVERLAY_CLOSURE",
        "authority": {
            "repository": "https://github.com/OpenIntroStat/openintro-statistics",
            "branch": "master",
            "commit": AUTHORITY_COMMIT,
            "tree": AUTHORITY_TREE,
        },
        "base_boundary": "R011-B012",
        "base_evidence": base,
        "base_manifest": identity(BASE_MANIFEST),
        "manifest": {**identity(SOURCE_MANIFEST), "files": len(rows)},
        "snapshot": {"path": rel(SNAPSHOT), **inventory},
        "builder": identity(Path(__file__)),
        "terminal_inputs": terminal,
        "overlays": overlays,
        "checks": checks,
        "expected_visual_audit": {
            "preface_term_page": 5,
            "base_section_start_page": 129,
            "base_eoce_page": 132,
            "base_chapter_transition_page": 135,
            "base_public_answer_page": 392,
            "provisional_review_pages": [5, *range(128, 137), *range(391, 395)],
            "render_dpi": REVIEW_DPI,
            "approval": "NOT_PERFORMED_BY_BUILD_HARNESS",
        },
        "translation_scope": (
            "Section 3.5 / Distribusi kontinu complete in source order: three worked "
            "examples, two guided exercises with both inline public answers, EoCE "
            "37-38, public answer 37, and five localized figure derivatives."
        ),
        "o001_gaps": [38],
        "translation_provenance": MODEL,
        "untranslated_suffix": (
            "Chapter review exercise 3.39 onward and Chapter 4 remain inherited "
            "English witnesses beyond B013."
        ),
        "rights_note": (
            "Text/translation retain CC BY-SA 3.0. The five localized PDFs are "
            "reader-label-only derivatives and remain governed by the exact "
            "component closure bound in terminal inputs."
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
    preface = first_page(pages, ["Distribusi variabel acak"], 1, 25)
    section = first_page_regex(pages, r"^\s*3\.5\s+Distribusi kontinu\s*$", 120, 145)
    eoce = first_page_regex(pages, r"^\s*3\.37\s+Berat kucing", section or 120, 150)
    next_review = first_page_regex(
        pages, r"^\s*3\.39\s+Grade distributions", eoce or 120, 155
    )
    chapter_transition = first_page_regex(
        pages, r"^\s*Bab 4\s*$", next_review or 125, 165
    )
    public_answer = first_page(
        pages, ["Jawaban perkiraan dapat diterima", "(29+32)/144"], 350, 430
    )
    next_public_answer = first_page(
        pages, ["Invalid. Sum is greater than", "Valid. Probabilities are between"],
        public_answer or 350,
        430,
    )
    require(preface is not None, "localized preface term not found")
    require(section is not None, "localized Section 3.5 heading not found")
    require(eoce is not None and eoce >= section, "localized EoCE 3.37 not found")
    require(next_review is not None and next_review >= eoce, "inherited exercise 3.39 boundary not found")
    require(
        chapter_transition is not None and chapter_transition > next_review,
        "Chapter 4 transition not found after B013",
    )
    require(public_answer is not None, "localized public answer 37 not found")
    require(126 <= section <= 134, f"Section 3.5 start page drifted: {section}")
    require(130 <= eoce <= 138, f"EoCE 3.37 page drifted: {eoce}")
    require(132 <= chapter_transition <= 142, f"Chapter 4 transition page drifted: {chapter_transition}")
    return {
        "preface_term_page": preface,
        "section_start_page": section,
        "eoce_start_page": eoce,
        "next_untranslated_review_page": next_review,
        "chapter_transition_page": chapter_transition,
        "public_answer_37_page": public_answer,
        "next_public_answer_page": next_public_answer,
        "section_body_window": [section, max(section, eoce - 1)],
        "eoce_window": [eoce, max(eoce, next_review - 1)],
        "affected_main_and_transition_window": [
            max(1, section - 1),
            min(len(pages), chapter_transition + 1),
        ],
        "transition": "Section 3.5 / Distribusi kontinu -> inherited chapter review -> Chapter 4",
    }


def reader_checks(text_path: Path, mapping: dict[str, Any]) -> dict[str, Any]:
    pages = page_texts(text_path)
    value = "\n".join(pages)
    expected = [
        "Distribusi variabel acak",
        "Distribusi kontinu",
        "fungsi kepadatan peluang",
        "tinggi (cm)",
        "Berat badan (kg)",
        "Berat kucing",
        "Pendapatan dan gender",
        "American Community Survey",
        "Jawaban perkiraan dapat diterima",
    ]
    absent = [term for term in expected if term.casefold() not in value.casefold()]
    require(not absent, f"reader text lacks expected B013 terms/labels: {absent}")
    boundary_pages = "\n".join(
        pages[
            mapping["section_start_page"] - 1 : mapping["next_untranslated_review_page"] - 1
        ]
    )
    forbidden = [
        "Continuous distributions",
        "What proportion of the sample",
        "From histograms to continuous distributions",
        "Probabilities from continuous distributions",
        "Cat weights",
        "Income and gender",
        "Body weight",
        "height (cm)",
    ]
    remaining = {term: boundary_pages.casefold().count(term.casefold()) for term in forbidden}
    require(not any(remaining.values()), f"reader-visible B013 English residue remains: {remaining}")
    require(
        "Approximate answers are OK".casefold() not in value.casefold(),
        "public answer 37 remains English",
    )
    return {
        "status": "PASS_TEXT_EXTRACTION_ONLY_VISUAL_PENDING",
        "expected_terms": expected,
        "absent": [],
        "translated_boundary_forbidden_phrase_counts": remaining,
        "public_answer_37_english_residue": 0,
    }


def expected_review_pages(mapping: dict[str, Any]) -> set[int]:
    pages = {mapping["preface_term_page"]}
    start, end = mapping["affected_main_and_transition_window"]
    pages.update(range(start, end + 1))
    answer_pages = [mapping["public_answer_37_page"]]
    if mapping["next_public_answer_page"] is not None:
        answer_pages.append(mapping["next_public_answer_page"])
    pages.update(
        range(max(1, min(answer_pages) - 1), max(answer_pages) + 2)
    )
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
    return artifacts


def readiness() -> dict[str, Any]:
    base = verify_base()
    rows = load_manifest()
    terminal = verify_terminal()
    checks = verify_sources()
    return {
        "$schema": "interlanguage.r011-b013-build-readiness/v1",
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
            "$schema": "interlanguage.r011-b013-build-harness-self-test/v1",
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
            raise GateError(f"refusing to overwrite conventional B013 candidate: {rel(FINAL)}")
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
        "$schema": "interlanguage.r011-b013-candidate-build-qa/v1",
        "boundary_id": BOUNDARY_ID,
        "status": "PASS_ISOLATED_TWO_REPLAY_DETERMINISTIC_BUILD_VISUAL_AUDIT_PENDING",
        "authority": {"commit": AUTHORITY_COMMIT, "tree": AUTHORITY_TREE},
        "base_boundary": "R011-B012",
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
                "first 128 bits of SHA-256(R011-B013_SOURCE_MANIFEST.tsv)"
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
            "Section 3.5 / Distribusi kontinu complete in source order: three worked "
            "examples, two guided exercises with both inline public answers, EoCE "
            "37-38, public answer 37, and five localized figure derivatives."
        ),
        "o001_gaps": [38],
        "next_untranslated_anchor": "ch_distributions/TeX/ch_distributions.tex#normalDist",
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
        help="Replace only the exact B013 QA build outputs.",
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
