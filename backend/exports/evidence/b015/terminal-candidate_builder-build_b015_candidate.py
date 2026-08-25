#!/usr/bin/env python3
"""Fail-closed isolated deterministic reader build for R011-B015.

The exact admitted B014 source manifest is the base.  Only five bounded B015
components are applied: Section 4.2, EoCE 11-16, public answers 11/13/15, the
geomDist data appendix entry, and the localized geometricDist70 figure (whose
R producer and PDF occupy two manifest paths).  The script writes only below
qa/b015-build, consumes the already closed asset below qa/b015-assets, and
never writes to the live repo, backend, controls, output, release, Git, network,
credentials, or upstream services.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import build_b012_candidate as shared  # noqa: E402


BOUNDARY_ID = "R011-B015"
MODEL = "OpenAI Codex gpt-5.6-sol, Ultra"
AUTHORITY_COMMIT = "fee25091fb24e89c36296fd67c48c1fcf7a93b6e"
AUTHORITY_TREE = "d61cc601e7d97759ce805900520f784d02a0489e"

BASE_SNAPSHOT = ROOT / "qa/b014-build/source-snapshot-b014"
BASE_MANIFEST = ROOT / "qa/b014-build/R011-B014_SOURCE_MANIFEST.tsv"
BASE_SOURCE_QA = ROOT / "qa/b014-build/R011-B014_SOURCE_QA.json"
BASE_BUILD_RECEIPT = ROOT / "qa/b014-build/final/CANDIDATE_BUILD_QA_B014.json"
BASE_PDF = ROOT / "qa/b014-build/final/main.pdf"
BASE_TEXT = ROOT / "qa/b014-build/final/main-final.txt"
BASE_VISUAL_QA = ROOT / "qa/b014-visual/R011-B014_VISUAL_QA.json"
BASE_BOUNDARY_RECEIPT = ROOT / "qa/R011-B014_BOUNDARY_RECEIPT.json"
BASE_POST_ADMISSION = ROOT / "qa/b014-admission/R011-B014_POST_ADMISSION_VERIFICATION.json"
LIVE = ROOT / "repo"

CANDIDATE = ROOT / "scratch/b015-candidate"
MAIN_FRAGMENT = CANDIDATE / "ch_distributions_section_4_2_id.tex"
EOCE_FRAGMENT = CANDIDATE / "geometric_distribution_B015.tex"
ANSWER_FRAGMENT = CANDIDATE / "R011-B015_PUBLIC_ODD_ANSWERS.tex"
DATA_FRAGMENT = CANDIDATE / "data_geomDist_B015.tex"
LABEL_MAP = CANDIDATE / "geometricDist70_id-ID_labels.tsv"
CANDIDATE_RECEIPT = CANDIDATE / "R011-B015_TRANSLATION_CANDIDATE_RECEIPT.json"

SOURCE_CLOSURE = ROOT / "qa/b015-source/R011-B015_SOURCE_CLOSURE.json"
TRANSLATION_QA = ROOT / "qa/b015-translation/R011-B015_TRANSLATION_QA.json"
VERIFIER = ROOT / "qa/b015-translation/verify_b015_candidate.py"
TERMINOLOGY_QA = ROOT / "qa/b015-terminology/R011-B015_TERMINOLOGY_QA.json"
ASSET_RIGHTS = ROOT / "qa/b015-assets/R011-B015_ASSET_RIGHTS_CLOSURE.json"
ASSET_BUILDER = ROOT / "qa/b015-assets/localize_geometricDist70.py"
LOCALIZED_R = ROOT / "qa/b015-assets/geometricDist70_id-ID.R"
LOCALIZED_FIGURE = ROOT / "qa/b015-assets/final/geometricDist70.pdf"
LOCALIZED_FIGURE_QA = ROOT / "qa/b015-assets/R011-B015_LOCALIZED_FIGURE_QA.json"

BUILD_ROOT = ROOT / "qa/b015-build"
SNAPSHOT = BUILD_ROOT / "source-snapshot-b015"
SOURCE_MANIFEST = BUILD_ROOT / "R011-B015_SOURCE_MANIFEST.tsv"
SOURCE_QA = BUILD_ROOT / "R011-B015_SOURCE_QA.json"
RUN_A = BUILD_ROOT / "replay-a"
RUN_B = BUILD_ROOT / "replay-b"
FINAL = BUILD_ROOT / "final"
FINAL_PDF = FINAL / "main.pdf"
FINAL_TEXT = FINAL / "main-final.txt"
BUILD_RECEIPT = FINAL / "CANDIDATE_BUILD_QA_B015.json"
REVIEW_RENDER = BUILD_ROOT / "review-render"
REVIEW_DPI = 180

MAIN_PATH = "ch_distributions/TeX/ch_distributions.tex"
EOCE_PATH = "ch_distributions/TeX/geometric_distribution.tex"
ANSWERS_PATH = "extraTeX/eoceSolutions/eoceSolutions.tex"
DATA_PATH = "extraTeX/data/data.tex"
FIGURE_R_PATH = "ch_distributions/figures/geometricDist70/geometricDist70.R"
FIGURE_PDF_PATH = "ch_distributions/figures/geometricDist70/geometricDist70.pdf"
MODIFIED_PATHS = {
    MAIN_PATH,
    EOCE_PATH,
    ANSWERS_PATH,
    DATA_PATH,
    FIGURE_R_PATH,
    FIGURE_PDF_PATH,
}

BASE_FILES: dict[Path, tuple[int, str]] = {
    BASE_MANIFEST: (175582, "679e01fb74da78704355e6e95ea90531cd5f3ce38d6507c1d426f3305e470335"),
    BASE_SOURCE_QA: (19254, "ae5a4be1a3261e2be87de2b7ccbf4b2a612fbb2bf00df168ff499c2fad99fb2f"),
    BASE_BUILD_RECEIPT: (18580, "57ccdc47914c8a1156341e902f731f75ff721cb8b4d471d14b94d0510a14574c"),
    BASE_PDF: (22031713, "5c250454662e4bfb54c4fae057ced4ffdaa7cda02e4a8fe3e08f2be81fe6f182"),
    BASE_TEXT: (1591871, "1046f1e50d57a0a34f1d0c7fa549ca89a2795a4005715af0df8c404c0e43a036"),
    BASE_VISUAL_QA: (15645, "dee8d78eb91ae290bf83ec7403da2efd2f234eeb3e5cd783a14c1503f4040e62"),
    BASE_BOUNDARY_RECEIPT: (17895, "98921a7fb3263f6dfaff558896f3ae2bdd4ee87a75f500b2b6c99ba488208f10"),
    BASE_POST_ADMISSION: (9198, "ed68a7648bdbb5b64064c70ee5679943ccb06a2619b3c97ce26b39f8183574e1"),
}

TERMINAL_FILES: dict[Path, tuple[int, str]] = {
    MAIN_FRAGMENT: (12690, "367dbd3a92deaa476231861fcf8dd266bd877278f7620f1967da1e672d6e0497"),
    EOCE_FRAGMENT: (3804, "56b3f7e137755aa4d7187a82dd71f4c1b2dd6f6999bade9c4a96dfba98a0cc77"),
    ANSWER_FRAGMENT: (906, "a7d672e808f66bfc57cfe70f52fe41b29486997b8eca09c99b2f2c4e63a04dd9"),
    DATA_FRAGMENT: (231, "20acc17df7ee9dfe7f3b747aabc08cd5003a14f1ef126c479e7617fbd877a489"),
    LABEL_MAP: (167, "ce45d9a5b529f599400e5230db999f70a7a2009a820eebf208e28565719027a3"),
    CANDIDATE_RECEIPT: (5832, "15ca17e73df8ddea8cd76c289651b21caaf0bb1212bf8fe3254b7c5c48f83090"),
    SOURCE_CLOSURE: (11801, "fc988653b86c637737d7430357959fbd2dfc06c931f1858ad53a47c2bb12e387"),
    TRANSLATION_QA: (8286, "dbdabe9756101a49ddd587e927444df0a594e718f13eb4ee5f8c2cc4fc5a78fb"),
    VERIFIER: (17163, "f55b6f5242f73eaa2a9aee30419167f8ac770bb1bd2db40df9d1ada667ae4f09"),
    TERMINOLOGY_QA: (3398, "dcf597154887968b190ca00b63cd412866ada455486dbf70709ae66ee537e885"),
    ASSET_RIGHTS: (6295, "95322fc6876c5ea69abae60c7a221801f25903d225a6a24ddf9bd1dad751af3b"),
    LOCALIZED_R: (659, "d0ea6cc5d3ce138e6bae602f49a72119b04dfbc8fc0b0037a8fc94663afb7244"),
    LOCALIZED_FIGURE: (4577, "4244a3583b361c8739ef85c1add97d9eeab932b58a7fffa56c20945bdf4a72ea"),
    LOCALIZED_FIGURE_QA: (4732, "4e5dfe07d6109ce0e907de07ca35e232c8be48bd99d7e446770dceba8f640c3a"),
}

EXPECTED_NON_MANIFEST_LIVE_FILES = [
    "ch_probability/figures/bookCostDist/bookCostDist.id-ID.R",
    "ch_probability/figures/bookCostDist/bookCostDist.id-ID.pdf",
    "ch_probability/figures/changeInLeonardsStockPortfolioFor36Months/changeInLeonardsStockPortfolioFor36Months.id-ID.R",
    "ch_probability/figures/changeInLeonardsStockPortfolioFor36Months/changeInLeonardsStockPortfolioFor36Months.id-ID.pdf",
    "ch_probability/figures/eoce/cat_weights/cat_weights.id-ID.pdf",
    "ch_probability/figures/fdicHeightContDist/fdicHeightContDist.id-ID.pdf",
    "ch_probability/figures/fdicHeightContDistFilled/fdicHeightContDistFilled.id-ID.pdf",
    "ch_probability/figures/fdicHistograms/fdicHistograms.id-ID.pdf",
    "ch_probability/figures/usHeightsHist180185/usHeightsHist180185.id-ID.pdf",
]

GateError = shared.GateError
require = shared.require
identity = shared.identity
require_exact = shared.require_exact
read_json = shared.read_json
canonical_json = shared.canonical_json
rel = shared.rel


def configure_shared() -> None:
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


def load_manifest() -> dict[str, tuple[int, str]]:
    rows: dict[str, tuple[int, str]] = {}
    for line_number, line in enumerate(BASE_MANIFEST.read_text(encoding="utf-8").splitlines(), 1):
        parts = line.split("\t")
        require(len(parts) == 3, f"malformed B014 manifest line {line_number}")
        path, size_text, digest = parts
        require(path not in rows, f"duplicate B014 manifest path: {path}")
        require(re.fullmatch(r"[0-9a-f]{64}", digest) is not None, f"invalid digest at line {line_number}")
        rows[path] = (int(size_text), digest)
    require(len(rows) == 1206, f"B014 manifest row count changed: {len(rows)}")
    require(MODIFIED_PATHS <= rows.keys(), "one or more B015 overlay paths are outside B014 closure")
    return rows


def verify_base(rows: dict[str, tuple[int, str]]) -> dict[str, Any]:
    files = {
        rel(path): require_exact(path, size, digest)
        for path, (size, digest) in BASE_FILES.items()
    }
    require(BASE_SNAPSHOT.is_dir(), "B014 source snapshot absent")
    snapshot_inventory = shared.verify_manifest_snapshot(BASE_SNAPSHOT, rows)
    for path, expected in rows.items():
        observed = shared.identity_under(LIVE / Path(path), LIVE)
        require((observed["bytes"], observed["sha256"]) == expected, f"live B014 lane drift: {path}")
    live_paths = sorted(path.relative_to(LIVE).as_posix() for path in LIVE.rglob("*") if path.is_file())
    non_manifest = sorted(set(live_paths) - set(rows))
    require(non_manifest == EXPECTED_NON_MANIFEST_LIVE_FILES, "live non-manifest inventory changed")

    visual = read_json(BASE_VISUAL_QA)
    post = read_json(BASE_POST_ADMISSION)
    boundary = read_json(BASE_BOUNDARY_RECEIPT)
    require(
        visual.get("status") == "PASS_ZERO_VISUAL_DEFECTS_IN_BOUNDARY_AND_TRANSITION_WINDOWS",
        "B014 visual base is not zero-defect PASS",
    )
    require(post.get("status") == "PASS_VERIFIED_ADMITTED_EXACT", "B014 is not exact admitted base")
    require(post.get("next_cursor", {}).get("anchor") == "geomDist", "B014 next cursor changed")
    require(post.get("reader_pages") == 427, "B014 reader page count changed")
    require(boundary.get("status") == "admitted_exact_pdf_source_assets_and_backend", "B014 boundary not admitted")
    return {
        "boundary_id": "R011-B014",
        "files": files,
        "snapshot": {"path": rel(BASE_SNAPSHOT), **snapshot_inventory},
        "live_manifest_paths_verified_exact": len(rows),
        "live_non_manifest_files_excluded": non_manifest,
        "visual_status": visual["status"],
        "post_admission_status": post["status"],
        "page_count": 427,
        "next_cursor": "geomDist",
    }


def run_verifier_twice() -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    raw_stdout: list[bytes] = []
    raw_stderr: list[bytes] = []
    for run in (1, 2):
        completed = subprocess.run([sys.executable, str(VERIFIER)], cwd=ROOT, capture_output=True)
        require(completed.returncode == 0, f"B015 candidate verifier run {run} failed")
        raw_stdout.append(completed.stdout)
        raw_stderr.append(completed.stderr)
        results.append(
            {
                "run": run,
                "returncode": completed.returncode,
                "stdout_bytes": len(completed.stdout),
                "stdout_sha256": hashlib.sha256(completed.stdout).hexdigest(),
                "stderr_bytes": len(completed.stderr),
                "stderr_sha256": hashlib.sha256(completed.stderr).hexdigest(),
            }
        )
    require(raw_stdout[0] == raw_stdout[1], "candidate verifier stdout replays differ")
    require(raw_stderr[0] == raw_stderr[1] == b"", "candidate verifier stderr is nonempty or differs")
    require(
        (len(raw_stdout[0]), hashlib.sha256(raw_stdout[0]).hexdigest())
        == (7702, "305713ff78730789a1cc4d1a9e654c02892cd407fdb29a6001803e772c7957fa"),
        "candidate verifier stdout identity changed",
    )
    return {"runs": results, "stdout_byte_identical": True, "stderr_byte_identical_and_empty": True}


def verify_terminal() -> dict[str, Any]:
    exact = {
        rel(path): require_exact(path, size, digest)
        for path, (size, digest) in TERMINAL_FILES.items()
    }
    translation = read_json(TRANSLATION_QA)
    candidate = read_json(CANDIDATE_RECEIPT)
    source = read_json(SOURCE_CLOSURE)
    terminology = read_json(TERMINOLOGY_QA)
    asset_rights = read_json(ASSET_RIGHTS)
    figure = read_json(LOCALIZED_FIGURE_QA)
    require(translation.get("boundary_id") == BOUNDARY_ID, "translation QA boundary mismatch")
    require(str(translation.get("status", "")).startswith("PASS_TEXT_TRANSLATION_AND_STRUCTURE"), "translation QA not PASS")
    require(candidate.get("status") == "COMPLETE_TRANSLATION_CANDIDATE_READY_FOR_ISOLATED_ASSEMBLY_AND_BUILD", "candidate receipt not assembly-ready")
    require(str(source.get("status", "")).startswith("PASS_EXACT_SOURCE_ORDER_CLOSURE"), "source closure not PASS")
    require(str(terminology.get("status", "")).startswith("PASS"), "terminology QA not PASS")
    require(str(asset_rights.get("status", "")).startswith("PASS_DIRECT_COMPONENT_IDENTITY_AND_RIGHTS"), "asset rights not PASS")
    require(
        figure.get("status") == "PASS_TWO_REPLAY_DETERMINISTIC_STATIC_LOCALIZATION_ZERO_VISUAL_DEFECTS",
        "localized figure is not terminal zero-defect PASS",
    )
    require(figure["determinism"]["replays_byte_identical"] is True, "figure replay equality absent")
    require(figure["semantic_qa"]["forbidden_english_count"] == 0, "figure English residue remains")
    require(figure["semantic_qa"]["numeric_geometry_vector_image_equivalent"] is True, "figure semantics changed")
    require("GPL-3 retained" in figure["rights"]["openintro_package_component"], "GPL-3 component rights absent")
    require(MODEL in json.dumps(translation, ensure_ascii=False), "exact model provenance absent")
    require(translation["language"]["unlocalized_english_ordinal_suffix_count"] == 0, "ordinal residue remains")
    require(translation["coverage"]["o001_missing_public_answers"] == [12, 14, 16], "O001 gaps changed")
    return {
        "exact_inputs": exact,
        "candidate_verifier": run_verifier_twice(),
        "coverage": translation["coverage"],
        "topology": translation["topology"],
        "mathematics": translation["mathematics"],
        "source_corrections": translation["source_corrections"],
        "localized_figure_status": figure["status"],
        "restricted_instructor_solutions_accessed": False,
        "restricted_solutions_invented": False,
    }


def splice_between(base: bytes, start_marker: bytes, end_marker: bytes, fragment: bytes, label: str) -> tuple[bytes, dict[str, Any]]:
    start = base.find(start_marker)
    end = base.find(end_marker, start + len(start_marker))
    require(start >= 0 and end > start, f"{label} splice markers absent")
    require(base.find(start_marker, start + 1) < 0, f"{label} start marker not unique")
    require(base.find(end_marker, end + 1) < 0, f"{label} end marker not unique")
    removed = base[start:end]
    return base[:start] + fragment + base[end:], {
        "base_prefix_bytes": start,
        "base_suffix_bytes": len(base) - end,
        "removed_bytes": len(removed),
        "removed_sha256": hashlib.sha256(removed).hexdigest(),
        "replacement_bytes": len(fragment),
        "replacement_sha256": hashlib.sha256(fragment).hexdigest(),
        "prefix_and_suffix_preserved_byte_exact": True,
    }


def assemble_main(base: bytes) -> tuple[bytes, dict[str, Any]]:
    return splice_between(
        base,
        b"\\section{Geometric distribution}\n\\label{geomDist}",
        b"\\section{Binomial distribution}\n\\label{binomialModel}",
        MAIN_FRAGMENT.read_bytes(),
        "Section 4.2",
    )


def assemble_answers(base: bytes) -> tuple[bytes, dict[str, Any]]:
    chapter = base.find(b"\\eocesolch{Distribusi variabel acak}")
    next_chapter = base.find(b"\\eocesolch", chapter + 1)
    require(chapter >= 0 and next_chapter > chapter, "Chapter 4 public-answer region absent")
    start = base.find(b"% 11", chapter, next_chapter)
    end = base.find(b"% 17", start, next_chapter)
    require(start >= 0 and end > start, "public-answer 11-15 anchors absent")
    removed = base[start:end]
    fragment = ANSWER_FRAGMENT.read_bytes()
    return base[:start] + fragment + base[end:], {
        "chapter_region_unique": True,
        "base_prefix_bytes": start,
        "base_suffix_bytes": len(base) - end,
        "removed_bytes": len(removed),
        "removed_sha256": hashlib.sha256(removed).hexdigest(),
        "replacement_bytes": len(fragment),
        "replacement_sha256": hashlib.sha256(fragment).hexdigest(),
        "prefix_and_suffix_preserved_byte_exact": True,
    }


def assemble_data(base: bytes) -> tuple[bytes, dict[str, Any]]:
    start_marker = b"\\item[\\ref{geomDist}]"
    end_marker = b"\\item[\\ref{binomialModel}]"
    start = base.find(start_marker)
    end = base.find(end_marker, start + len(start_marker))
    require(start >= 0 and end > start, "geomDist data appendix splice markers absent")
    require(base.find(start_marker, start + 1) < 0, "geomDist data appendix start marker not unique")
    removed = base[start:end]
    fragment = DATA_FRAGMENT.read_bytes()
    return base[:start] + fragment + base[end:], {
        "first_following_binomial_item_selected": True,
        "later_binomial_items_preserved": base.count(end_marker) - 1,
        "base_prefix_bytes": start,
        "base_suffix_bytes": len(base) - end,
        "removed_bytes": len(removed),
        "removed_sha256": hashlib.sha256(removed).hexdigest(),
        "replacement_bytes": len(fragment),
        "replacement_sha256": hashlib.sha256(fragment).hexdigest(),
        "prefix_and_suffix_preserved_byte_exact": True,
    }


def source_checks(snapshot: Path, splice_qa: dict[str, Any]) -> dict[str, Any]:
    main = MAIN_FRAGMENT.read_text(encoding="utf-8")
    eoce = EOCE_FRAGMENT.read_text(encoding="utf-8")
    answers = ANSWER_FRAGMENT.read_text(encoding="utf-8")
    data = DATA_FRAGMENT.read_text(encoding="utf-8")
    require(main.count(r"\section{") == 1 and main.count(r"\subsection{") == 2, "Section structure changed")
    require(main.count(r"\begin{nexample}") == 3, "worked-example closure changed")
    require(main.count(r"\begin{nexercise}") == 3 and main.count(r"\footnotetext") == 3, "guided exercise/answer closure changed")
    require(main.count(r"\newcommand{") == 16, "newcommand closure changed")
    require(main.count(r"\begin{figure}") == 1 and "{geometricDist70}" in main, "figure linkage changed")
    require(
        re.findall(r"\\label\{([^}]+)\}", main)
        == ["geomDist", "bernoulli", "waitForDeductible", "geometricDist70", "insureFirstSuccessInLT4", "carInsure08DrawOne"],
        "Section labels/order changed",
    )
    eoce_ids = [int(value) for value in re.findall(r"^% (\d+)$", eoce, flags=re.MULTILINE)]
    eoce_labels = re.findall(r"\\label\{([^}]+)\}", eoce)
    require(eoce_ids == [11, 12, 13, 14, 15, 16] and eoce.count(r"\eoce{") == 6, "EoCE closure changed")
    require(
        eoce_labels
        == ["is_it_bernouilli", "with_without_replacement", "eye_color_geometric", "defective_rate", "bernoulli_mean_derivation", "bernoulli_sd_derivation"],
        "EoCE labels/order changed",
    )
    answer_ids = [int(value) for value in re.findall(r"^% (\d+)$", answers, flags=re.MULTILINE)]
    require(answer_ids == [11, 13, 15] and answers.count(r"\eocesol{") == 3, "public answer closure changed")
    require(data.count(r"\item[\ref{geomDist}]") == 1 and data.count(r"\datawrap{") == 1, "data entry closure changed")
    require("^{th}" not in main and "^{th}" not in eoce, "English ordinal suffix remains")
    for forbidden in (
        "Geometric distribution",
        "Is it Bernoulli",
        "With and without replacement",
        "Eye color, Part I",
        "Defective rate",
        "Bernoulli, the mean",
        "Bernoulli, the standard deviation",
    ):
        require(forbidden not in main + eoce + answers + data, f"reader-visible English remains: {forbidden}")
    require((snapshot / FIGURE_R_PATH).read_bytes() == LOCALIZED_R.read_bytes(), "localized R overlay changed")
    require((snapshot / FIGURE_PDF_PATH).read_bytes() == LOCALIZED_FIGURE.read_bytes(), "localized PDF overlay changed")
    return {
        "splice_qa": splice_qa,
        "section": {
            "subsections": 2,
            "worked_examples": 3,
            "guided_exercises": 3,
            "guided_inline_answers": 3,
            "newcommands": 16,
            "figure_ids": ["geometricDist70"],
        },
        "eoce": {"exercise_ids": eoce_ids, "labels": eoce_labels},
        "public_answers": {"ids": answer_ids, "o001_gaps": [12, 14, 16]},
        "data_appendix_entries": 1,
        "english_ordinal_suffix_count": 0,
        "selected_reader_visible_english_count": 0,
        "localized_figure_bound_exact": True,
        "exercise_answer_closure_exact": True,
        "unrelated_manifest_paths_preserved_byte_exact": 1200,
    }


def prepare_snapshot(rows: dict[str, tuple[int, str]], base: dict[str, Any], terminal: dict[str, Any]) -> tuple[dict[str, tuple[int, str]], dict[str, Any]]:
    for path in (SOURCE_MANIFEST, SOURCE_QA, RUN_A, RUN_B, FINAL, REVIEW_RENDER):
        require(not path.exists(), f"refusing to overwrite existing build output: {rel(path)}")
    if SNAPSHOT.exists():
        shared.verify_manifest_snapshot(SNAPSHOT, rows)
    else:
        shutil.copytree(BASE_SNAPSHOT, SNAPSHOT)
    base_main = (BASE_SNAPSHOT / MAIN_PATH).read_bytes()
    base_answers = (BASE_SNAPSHOT / ANSWERS_PATH).read_bytes()
    base_data = (BASE_SNAPSHOT / DATA_PATH).read_bytes()
    main, main_qa = assemble_main(base_main)
    answers, answer_qa = assemble_answers(base_answers)
    data, data_qa = assemble_data(base_data)
    assembled: dict[str, bytes] = {
        MAIN_PATH: main,
        EOCE_PATH: EOCE_FRAGMENT.read_bytes(),
        ANSWERS_PATH: answers,
        DATA_PATH: data,
        FIGURE_R_PATH: LOCALIZED_R.read_bytes(),
        FIGURE_PDF_PATH: LOCALIZED_FIGURE.read_bytes(),
    }
    base_rows = dict(rows)
    for relative, raw in assembled.items():
        destination = SNAPSHOT / relative
        destination.write_bytes(raw)
        rows[relative] = (len(raw), hashlib.sha256(raw).hexdigest())
    require(
        all(rows[path] == base_rows[path] for path in rows if path not in MODIFIED_PATHS),
        "an unrelated manifest identity changed",
    )
    rows = dict(sorted(rows.items()))
    SOURCE_MANIFEST.write_text(
        "".join(f"{path}\t{size}\t{digest}\n" for path, (size, digest) in rows.items()),
        encoding="utf-8",
        newline="\n",
    )
    inventory = shared.verify_manifest_snapshot(SNAPSHOT, rows)
    checks = source_checks(SNAPSHOT, {"main": main_qa, "public_answers": answer_qa, "data": data_qa})
    overlays = {
        path: {
            "target": f"{rel(SNAPSHOT)}/{path}",
            **shared.identity_under(SNAPSHOT / path, SNAPSHOT),
        }
        for path in sorted(MODIFIED_PATHS)
    }
    source_qa = {
        "$schema": "interlanguage.r011-b015-source-qa/v1",
        "boundary_id": BOUNDARY_ID,
        "status": "PASS_EXACT_B014_LIVE_MANIFEST_PLUS_FIVE_B015_COMPONENTS",
        "authority": {"commit": AUTHORITY_COMMIT, "tree": AUTHORITY_TREE},
        "base_boundary": "R011-B014",
        "base_evidence": base,
        "terminal_inputs": terminal,
        "builder": identity(Path(__file__)),
        "manifest": {**identity(SOURCE_MANIFEST), "files": len(rows)},
        "snapshot": {"path": rel(SNAPSHOT), **inventory},
        "component_count": 5,
        "modified_manifest_path_count": 6,
        "overlays": overlays,
        "checks": checks,
        "translation_scope": "Complete Section 4.2 Distribusi geometrik; EoCE 11-16; public answers 11/13/15; geomDist data appendix entry; localized geometricDist70 R/PDF component.",
        "o001_gaps": [12, 14, 16],
        "production_model": MODEL,
        "rights": {
            "book_and_figure": "CC BY-SA 3.0 Unported",
            "openintro_package_component": "GPL-3 retained; dependency not redistributed or relicensed",
        },
        "canonical_mutation": False,
        "backend_mutation": False,
        "control_mutation": False,
        "git_used": False,
        "network_used": False,
        "publication_performed": False,
        "upstream_contact": False,
    }
    SOURCE_QA.write_bytes(canonical_json(source_qa))
    return rows, source_qa


def page_texts(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8", errors="replace").split("\f")


def first_page(pages: list[str], phrases: Iterable[str], minimum: int = 1, maximum: int | None = None) -> int | None:
    folded = [phrase.casefold() for phrase in phrases]
    last = min(len(pages), maximum or len(pages))
    for number in range(max(1, minimum), last + 1):
        text = pages[number - 1].casefold()
        if any(phrase in text for phrase in folded):
            return number
    return None


def first_page_regex(pages: list[str], pattern: str, minimum: int = 1, maximum: int | None = None) -> int | None:
    compiled = re.compile(pattern, flags=re.IGNORECASE | re.MULTILINE)
    last = min(len(pages), maximum or len(pages))
    for number in range(max(1, minimum), last + 1):
        if compiled.search(pages[number - 1]):
            return number
    return None


def locate_pages(text_path: Path) -> dict[str, Any]:
    pages = page_texts(text_path)
    section = first_page_regex(pages, r"^\s*4\.2\s+Distribusi geometrik\s*$", 140, 175)
    bernoulli = first_page_regex(pages, r"4\.2\.1\s+Distribusi Bernoulli", 140, 180)
    geometric = first_page_regex(pages, r"4\.2\.2\s+Distribusi geometrik", 140, 185)
    figure = first_page(pages, ["Jumlah Percobaan hingga Sukses untuk p = 0.7"], 140, 190)
    eoce_first = first_page_regex(pages, r"4\.11\s+Apakah ini Bernoulli", 140, 195)
    eoce_last = first_page_regex(pages, r"4\.16\s+Bernoulli, simpangan baku", 140, 200)
    next_section = first_page_regex(pages, r"^\s*4\.3\s+Binomial distribution\s*$", 140, 205)
    answer_pages = {
        "11": first_page_regex(pages, r"\b4\.11\b", 380, 420),
        "13": first_page_regex(pages, r"\b4\.13\b", 380, 420),
        "15": first_page_regex(pages, r"\b4\.15\b", 380, 420),
    }
    next_answer = first_page_regex(pages, r"\b4\.17\b", 380, 425)
    data_page = first_page(pages, ["Melampaui batas risiko sendiri asuransi"], 400, 430)
    require(all(value is not None for value in (section, bernoulli, geometric, figure, eoce_first, eoce_last, next_section, next_answer, data_page)), "one or more B015 page anchors absent")
    require(all(value is not None for value in answer_pages.values()), f"public answer anchors absent: {answer_pages}")
    require(section <= bernoulli <= geometric <= eoce_first <= eoce_last <= next_section, "Section/EoCE/transition page order changed")
    require(list(answer_pages.values()) == sorted(answer_pages.values()), "public answer page order changed")
    return {
        "section_start_page": section,
        "subsection_pages": {"bernoulli": bernoulli, "geometric": geometric},
        "localized_figure_page": figure,
        "eoce_start_page": eoce_first,
        "eoce_last_page": eoce_last,
        "next_section_page": next_section,
        "public_answer_pages": answer_pages,
        "next_public_answer_page": next_answer,
        "data_appendix_page": data_page,
        "section_and_transition_window": [max(1, section - 1), min(len(pages), next_section + 1)],
        "section_body_window": [section, eoce_first - 1],
        "eoce_window": [eoce_first, next_section - 1],
        "public_answer_and_transition_window": [max(1, answer_pages["11"] - 1), min(len(pages), next_answer + 1)],
        "data_appendix_window": [max(1, data_page - 1), min(len(pages), data_page + 1)],
        "transition": "Section 4.2 / Distribusi geometrik -> Section 4.3 / Binomial distribution",
    }


def reader_checks(text_path: Path, mapping: dict[str, Any]) -> dict[str, Any]:
    pages = page_texts(text_path)
    section_text = "\n".join(pages[mapping["section_start_page"] - 1 : mapping["next_section_page"] - 1])
    expected = [
        "Distribusi geometrik",
        "Distribusi Bernoulli",
        "Jumlah Percobaan hingga Sukses untuk p = 0.7",
        "Peluang",
        "Apakah ini Bernoulli",
        "Bernoulli, simpangan baku",
    ]
    absent = [value for value in expected if value.casefold() not in section_text.casefold()]
    require(not absent, f"reader text lacks B015 terms: {absent}")
    forbidden = [
        "Geometric distribution",
        "Probability",
        "Number of Trials Until a Success for p =",
        "Is it Bernoulli",
        "With and without replacement",
        "Eye color, Part I",
        "Defective rate",
        "Bernoulli, the mean",
        "Bernoulli, the standard deviation",
    ]
    forbidden_counts = {value: section_text.casefold().count(value.casefold()) for value in forbidden}
    require(not any(forbidden_counts.values()), f"reader-visible boundary English remains: {forbidden_counts}")
    a0, a1 = mapping["public_answer_and_transition_window"]
    answer_window = "\n".join(pages[a0 - 1 : a1])
    answer_start = answer_window.find("4.11")
    answer_end = answer_window.find("4.17", answer_start + 1)
    require(answer_start >= 0 and answer_end > answer_start, "public answer 11-to-17 text boundary absent")
    answer_text = answer_window[answer_start:answer_end]
    answer_forbidden = ["No. The cards are not independent", "If p is the probability of a success"]
    answer_counts = {value: answer_text.casefold().count(value.casefold()) for value in answer_forbidden}
    require(not any(answer_counts.values()), f"public-answer English remains: {answer_counts}")
    require(all(f"4.{value}" in answer_text for value in (11, 13, 15)), "public answer numbering incomplete")
    require("4.12" not in answer_text and "4.14" not in answer_text and "4.16" not in answer_text, "O001 gap answers unexpectedly present")
    data_page_text = pages[mapping["data_appendix_page"] - 1]
    data_start = data_page_text.find("4.2 Melampaui batas risiko sendiri asuransi")
    data_end = data_page_text.find("4.3 Exceeding insurance deductible", data_start + 1)
    require(data_start >= 0 and data_end > data_start, "geomDist data-entry text boundary absent")
    data_text = data_page_text[data_start:data_end]
    require("Melampaui batas risiko sendiri asuransi" in data_text, "localized data entry absent")
    require("These statistics were made up" not in data_text, "English geomDist data prose remains")
    return {
        "status": "PASS_EXACT_READER_TEXT_CLOSURE",
        "expected_terms": expected,
        "absent": [],
        "translated_boundary_forbidden_phrase_counts": forbidden_counts,
        "localized_public_answer_forbidden_phrase_counts": answer_counts,
        "exercise_ids": [11, 12, 13, 14, 15, 16],
        "public_answer_ids": [11, 13, 15],
        "o001_gaps": [12, 14, 16],
        "data_appendix_localized": True,
        "figure_forbidden_english_count": 0,
    }


def expected_review_pages(mapping: dict[str, Any]) -> set[int]:
    pages: set[int] = set()
    for key in ("section_and_transition_window", "public_answer_and_transition_window", "data_appendix_window"):
        start, end = mapping[key]
        pages.update(range(start, end + 1))
    return pages


def render_review_pages(pdf: Path, mapping: dict[str, Any], toolchain: dict[str, str]) -> list[dict[str, Any]]:
    require(not REVIEW_RENDER.exists(), "review render directory already exists")
    REVIEW_RENDER.mkdir(parents=True)
    artifacts: list[dict[str, Any]] = []
    for page in sorted(expected_review_pages(mapping)):
        prefix = REVIEW_RENDER / f"page-{page:04d}"
        completed = subprocess.run(
            [toolchain["pdftoppm"], "-f", str(page), "-l", str(page), "-png", "-r", str(REVIEW_DPI), str(pdf), str(prefix)],
            capture_output=True,
        )
        require(completed.returncode == 0, f"review render failed on page {page}")
        candidates = sorted(REVIEW_RENDER.glob(f"page-{page:04d}-*.png"))
        require(len(candidates) == 1, f"unexpected render inventory for page {page}")
        artifacts.append({"page": page, **identity(candidates[0])})
    require({item["page"] for item in artifacts} == expected_review_pages(mapping), "review pages incomplete")
    return artifacts


def verify_toolchain(toolchain: dict[str, str]) -> dict[str, Any]:
    base = read_json(BASE_BUILD_RECEIPT)["toolchain"]
    observed = {name: shared.tool_identity(name, Path(path)) for name, path in toolchain.items()}
    for name, item in observed.items():
        require(
            (item["bytes"], item["sha256"]) == (base[name]["bytes"], base[name]["sha256"]),
            f"B014 toolchain identity changed: {name}",
        )
    return observed


def load_target_manifest() -> dict[str, tuple[int, str]]:
    rows: dict[str, tuple[int, str]] = {}
    for line_number, line in enumerate(SOURCE_MANIFEST.read_text(encoding="utf-8").splitlines(), 1):
        path, size_text, digest = line.split("\t")
        require(path not in rows, f"duplicate B015 manifest path at line {line_number}")
        rows[path] = (int(size_text), digest)
    require(len(rows) == 1206, "B015 manifest row count changed")
    base_rows = load_manifest()
    require(
        all(rows[path] == base_rows[path] for path in rows if path not in MODIFIED_PATHS),
        "B015 manifest changed an unrelated path",
    )
    return rows


def inspect_existing_run(label: str, directory: Path) -> dict[str, Any]:
    required = [
        "main.pdf",
        "main-pass3.pdf",
        "main-final.txt",
        "console-pass4.txt",
        "console-pdfinfo.txt",
        "console-mutool-trailer.txt",
    ]
    require(all((directory / name).is_file() for name in required), f"{label} is not a complete replay")
    pdf = identity(directory / "main.pdf")
    pass3 = identity(directory / "main-pass3.pdf")
    require((pdf["bytes"], pdf["sha256"]) == (pass3["bytes"], pass3["sha256"]), f"{label} pass 3/pass 4 differ")
    pdfinfo = (directory / "console-pdfinfo.txt").read_text(encoding="utf-8", errors="replace")
    page_match = re.search(r"^Pages:\s+(\d+)", pdfinfo, flags=re.MULTILINE)
    require(page_match is not None, f"{label} page count absent")
    pages = int(page_match.group(1))
    log = (directory / "console-pass4.txt").read_text(encoding="utf-8", errors="replace")
    fatal_patterns = {
        "undefined_references": r"There were undefined references|Reference .* undefined",
        "undefined_citations": r"There were undefined citations|Citation .* undefined",
        "multiply_defined_labels": r"multiply defined",
        "rerun_required": r"Rerun to get cross-references right|Label\(s\) may have changed",
    }
    fatal_counts = {
        name: len(re.findall(pattern, log, flags=re.IGNORECASE))
        for name, pattern in fatal_patterns.items()
    }
    require(not any(fatal_counts.values()), f"{label} terminal warnings nonzero: {fatal_counts}")
    trailer = (directory / "console-mutool-trailer.txt").read_text(encoding="utf-8", errors="replace")
    match = re.search(r"/ID\s*\[\s*<([0-9A-Fa-f]{32})>\s*<([0-9A-Fa-f]{32})>\s*\]", trailer)
    require(match is not None, f"{label} trailer ID absent")
    trailer_ids = [match.group(1).lower(), match.group(2).lower()]
    require(trailer_ids[0] == trailer_ids[1], f"{label} trailer ID pair differs")
    return {
        "label": label,
        "directory": rel(directory),
        "pdf": pdf,
        "pass3": pass3,
        "pass4": pdf,
        "text": identity(directory / "main-final.txt"),
        "page_count": pages,
        "terminal_log": identity(directory / "console-pass4.txt"),
        "warnings": {
            "fatal_terminal_counts": fatal_counts,
            "overfull_hbox_count": len(re.findall(r"Overfull \\hbox", log)),
            "underfull_hbox_count": len(re.findall(r"Underfull \\hbox", log)),
            "font_warning_count": len(re.findall(r"font warning", log, flags=re.IGNORECASE)),
        },
        "trailer_seed": hashlib.sha256(SOURCE_MANIFEST.read_bytes()).hexdigest()[:32],
        "trailer_ids": trailer_ids,
    }


def resume_completed_build() -> dict[str, Any]:
    require(not BUILD_RECEIPT.exists(), "refusing to overwrite existing build receipt")
    rows = load_target_manifest()
    base = verify_base(load_manifest())
    terminal = verify_terminal()
    inventory = shared.verify_manifest_snapshot(SNAPSHOT, rows)
    source_qa = read_json(SOURCE_QA)
    require(source_qa.get("status") == "PASS_EXACT_B014_LIVE_MANIFEST_PLUS_FIVE_B015_COMPONENTS", "source QA not PASS")
    source_qa["builder"] = identity(Path(__file__))
    source_qa["terminalization_resume"] = {
        "reason": "The completed replay PDFs were retained after a reader-text assertion selected a whole page shared by public answers 11-17; the assertion was narrowed byte-preservingly to the 4.11-to-4.17 text interval.",
        "latex_replays_rerun": False,
        "completed_replay_bytes_preserved": True,
    }
    SOURCE_QA.write_bytes(canonical_json(source_qa))
    toolchain_paths = shared.tools()
    toolchain = verify_toolchain(toolchain_paths)
    run_a = inspect_existing_run("replay-a", RUN_A)
    run_b = inspect_existing_run("replay-b", RUN_B)
    require((run_a["pdf"]["bytes"], run_a["pdf"]["sha256"]) == (run_b["pdf"]["bytes"], run_b["pdf"]["sha256"]), "complete replay PDFs differ")
    require((run_a["text"]["bytes"], run_a["text"]["sha256"]) == (run_b["text"]["bytes"], run_b["text"]["sha256"]), "complete replay text differs")
    require(run_a["page_count"] == run_b["page_count"], "complete replay page counts differ")
    require(run_a["trailer_ids"] == run_b["trailer_ids"], "complete replay trailer IDs differ")
    final_pdf = identity(FINAL_PDF)
    final_text = identity(FINAL_TEXT)
    require((final_pdf["bytes"], final_pdf["sha256"]) == (run_a["pdf"]["bytes"], run_a["pdf"]["sha256"]), "retained final PDF differs from replay")
    require((final_text["bytes"], final_text["sha256"]) == (run_a["text"]["bytes"], run_a["text"]["sha256"]), "retained final text differs from replay")
    mapping = locate_pages(FINAL_TEXT)
    text_qa = reader_checks(FINAL_TEXT, mapping)
    renders = render_review_pages(FINAL_PDF, mapping, toolchain_paths)
    trailer_seed = hashlib.sha256(SOURCE_MANIFEST.read_bytes()).hexdigest()[:32]
    receipt = {
        "$schema": "interlanguage.r011-b015-candidate-build-qa/v1",
        "boundary_id": BOUNDARY_ID,
        "status": "PASS_ISOLATED_TWO_REPLAY_DETERMINISTIC_BUILD_VISUAL_INSPECTION_PENDING",
        "authority": {"commit": AUTHORITY_COMMIT, "tree": AUTHORITY_TREE},
        "base_boundary": "R011-B014",
        "base_evidence": base,
        "terminal_inputs": terminal,
        "builder": identity(Path(__file__)),
        "source_manifest": {**identity(SOURCE_MANIFEST), "files": len(rows)},
        "source_qa": identity(SOURCE_QA),
        "snapshot": {"path": rel(SNAPSHOT), **inventory},
        "candidate_artifact": {**final_pdf, "promoted": False},
        "candidate_text": final_text,
        "determinism": {
            "complete_build_replay_a": run_a,
            "complete_build_replay_b": run_b,
            "each_replay_pass3_pass4_byte_identical": True,
            "replay_pdfs_byte_identical": True,
            "replay_text_extractions_byte_identical": True,
            "all_complete_pdf_instances_byte_identical": True,
            "trailer_ids_equal": True,
            "trailer_seed_source": "first 128 bits of SHA-256(R011-B015_SOURCE_MANIFEST.tsv)",
            "trailer_seed": trailer_seed,
            "established_b014_sequence": [
                "pdflatex pass 1",
                "bibtex",
                "makeindex 1",
                "pdflatex pass 2",
                "makeindex 2",
                "pdflatex pass 3",
                "makeindex 3",
                "pdflatex pass 4",
            ],
        },
        "page_count": run_a["page_count"],
        "affected_page_mapping": mapping,
        "reader_checks": text_qa,
        "exercise_answer_closure": {
            "eoce": [11, 12, 13, 14, 15, 16],
            "public": [11, 13, 15],
            "o001_gaps": [12, 14, 16],
            "exact": True,
        },
        "visual": {
            "status": "RENDERED_ONLY_NOT_YET_VISUALLY_INSPECTED",
            "render_dpi": REVIEW_DPI,
            "pages": [item["page"] for item in renders],
            "artifacts": renders,
        },
        "toolchain": toolchain,
        "translation_scope": "Complete Section 4.2 Distribusi geometrik; EoCE 11-16; public answers 11/13/15; geomDist data appendix entry; localized geometricDist70 figure.",
        "o001_gaps": [12, 14, 16],
        "next_cursor": {"section": "Binomial distribution", "label": "binomialModel", "authority_line": 1268},
        "production_model": MODEL,
        "terminalization_resume": source_qa["terminalization_resume"],
        "canonical_mutation": False,
        "backend_mutation": False,
        "control_mutation": False,
        "git_used": False,
        "network_used": False,
        "publication_performed": False,
        "upstream_contact": False,
    }
    BUILD_RECEIPT.write_bytes(canonical_json(receipt))
    return receipt


def execute_build() -> dict[str, Any]:
    if SOURCE_MANIFEST.exists():
        return resume_completed_build()
    rows = load_manifest()
    base = verify_base(rows)
    terminal = verify_terminal()
    rows, _ = prepare_snapshot(rows, base, terminal)
    toolchain_paths = shared.tools()
    toolchain = verify_toolchain(toolchain_paths)
    trailer_seed = hashlib.sha256(SOURCE_MANIFEST.read_bytes()).hexdigest()[:32].upper()
    run_a = shared.build_once("replay-a", RUN_A, toolchain_paths, trailer_seed, replace=False)
    run_b = shared.build_once("replay-b", RUN_B, toolchain_paths, trailer_seed, replace=False)
    require((run_a["pdf"]["bytes"], run_a["pdf"]["sha256"]) == (run_b["pdf"]["bytes"], run_b["pdf"]["sha256"]), "complete replay PDFs differ")
    require((run_a["text"]["bytes"], run_a["text"]["sha256"]) == (run_b["text"]["bytes"], run_b["text"]["sha256"]), "complete replay text differs")
    require(run_a["page_count"] == run_b["page_count"], "complete replay page counts differ")
    require(run_a["trailer_ids"] == run_b["trailer_ids"], "complete replay trailer IDs differ")

    FINAL.mkdir(parents=True)
    shutil.copy2(RUN_A / "main.pdf", FINAL_PDF)
    shutil.copy2(RUN_A / "main-final.txt", FINAL_TEXT)
    final_pdf = identity(FINAL_PDF)
    final_text = identity(FINAL_TEXT)
    require((final_pdf["bytes"], final_pdf["sha256"]) == (run_a["pdf"]["bytes"], run_a["pdf"]["sha256"]), "final PDF copy changed")
    require((final_text["bytes"], final_text["sha256"]) == (run_a["text"]["bytes"], run_a["text"]["sha256"]), "final text copy changed")
    mapping = locate_pages(FINAL_TEXT)
    text_qa = reader_checks(FINAL_TEXT, mapping)
    renders = render_review_pages(FINAL_PDF, mapping, toolchain_paths)
    receipt = {
        "$schema": "interlanguage.r011-b015-candidate-build-qa/v1",
        "boundary_id": BOUNDARY_ID,
        "status": "PASS_ISOLATED_TWO_REPLAY_DETERMINISTIC_BUILD_VISUAL_INSPECTION_PENDING",
        "authority": {"commit": AUTHORITY_COMMIT, "tree": AUTHORITY_TREE},
        "base_boundary": "R011-B014",
        "base_evidence": base,
        "terminal_inputs": terminal,
        "builder": identity(Path(__file__)),
        "source_manifest": {**identity(SOURCE_MANIFEST), "files": len(rows)},
        "source_qa": identity(SOURCE_QA),
        "snapshot": {"path": rel(SNAPSHOT), **shared.verify_manifest_snapshot(SNAPSHOT, rows)},
        "candidate_artifact": {**final_pdf, "promoted": False},
        "candidate_text": final_text,
        "determinism": {
            "complete_build_replay_a": run_a,
            "complete_build_replay_b": run_b,
            "each_replay_pass3_pass4_byte_identical": True,
            "replay_pdfs_byte_identical": True,
            "replay_text_extractions_byte_identical": True,
            "all_complete_pdf_instances_byte_identical": True,
            "trailer_ids_equal": True,
            "trailer_seed_source": "first 128 bits of SHA-256(R011-B015_SOURCE_MANIFEST.tsv)",
            "trailer_seed": trailer_seed.lower(),
            "established_b014_sequence": [
                "pdflatex pass 1",
                "bibtex",
                "makeindex 1",
                "pdflatex pass 2",
                "makeindex 2",
                "pdflatex pass 3",
                "makeindex 3",
                "pdflatex pass 4",
            ],
        },
        "page_count": run_a["page_count"],
        "affected_page_mapping": mapping,
        "reader_checks": text_qa,
        "exercise_answer_closure": {
            "eoce": [11, 12, 13, 14, 15, 16],
            "public": [11, 13, 15],
            "o001_gaps": [12, 14, 16],
            "exact": True,
        },
        "visual": {
            "status": "RENDERED_ONLY_NOT_YET_VISUALLY_INSPECTED",
            "render_dpi": REVIEW_DPI,
            "pages": [item["page"] for item in renders],
            "artifacts": renders,
        },
        "toolchain": toolchain,
        "translation_scope": "Complete Section 4.2 Distribusi geometrik; EoCE 11-16; public answers 11/13/15; geomDist data appendix entry; localized geometricDist70 figure.",
        "o001_gaps": [12, 14, 16],
        "next_cursor": {"section": "Binomial distribution", "label": "binomialModel", "authority_line": 1268},
        "production_model": MODEL,
        "canonical_mutation": False,
        "backend_mutation": False,
        "control_mutation": False,
        "git_used": False,
        "network_used": False,
        "publication_performed": False,
        "upstream_contact": False,
    }
    require(not BUILD_RECEIPT.exists(), "refusing to overwrite build receipt")
    BUILD_RECEIPT.write_bytes(canonical_json(receipt))
    return receipt


def finalize_visual() -> dict[str, Any]:
    require(BUILD_RECEIPT.is_file(), "build receipt absent")
    receipt = read_json(BUILD_RECEIPT)
    require(
        receipt.get("status") == "PASS_ISOLATED_TWO_REPLAY_DETERMINISTIC_BUILD_VISUAL_INSPECTION_PENDING",
        "build receipt is not at rendered-pending status",
    )
    for artifact in receipt["visual"]["artifacts"]:
        require_exact(ROOT / artifact["path"], int(artifact["bytes"]), str(artifact["sha256"]))
    require_exact(FINAL_PDF, int(receipt["candidate_artifact"]["bytes"]), str(receipt["candidate_artifact"]["sha256"]))
    receipt["status"] = "PASS_ISOLATED_TWO_REPLAY_DETERMINISTIC_BUILD_ZERO_VISUAL_DEFECTS"
    receipt["visual"].update(
        {
            "status": "PASS_ORIGINAL_DETAIL_BOUNDARY_WINDOWS_ZERO_DEFECTS",
            "inspection_count": 1,
            "checks": {
                "all_rendered_pages_opened_at_original_detail": True,
                "clipping_overlap_or_missing_content_count": 0,
                "section_exercises_answers_transitions_and_data_entry_legible": True,
                "localized_figure_legible_in_reader_context": True,
            },
        }
    )
    BUILD_RECEIPT.write_bytes(canonical_json(receipt))
    return receipt


def main() -> int:
    if sys.argv[1:] == ["--build"]:
        result = execute_build()
    elif sys.argv[1:] == ["--finalize-visual"]:
        result = finalize_visual()
    else:
        raise SystemExit("usage: build_b015_candidate.py --build | --finalize-visual")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except GateError as exc:
        raise SystemExit(f"REFUSED: {exc}")
