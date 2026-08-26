#!/usr/bin/env python3
"""Fail-closed isolated deterministic reader build for R011-B016.

The exact admitted B015 source manifest is the base.  Four bounded B016
components are applied: Section 4.3, EoCE 17-26, public answers
17/19/21/23/25, and the three binomialModel data appendix entries.  The two
figure R/PDF pairs are reused byte-exact because their visible content is
locale-neutral.  The separately licensed CC BY 2.0 dreidel photograph and its
visible attribution are also preserved byte-exact.  This script writes only
below qa/b016-build and never mutates the live repo, backend, controls, output,
release, Git, network, credentials, or upstream services.
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


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_b012_candidate as shared  # noqa: E402


BOUNDARY_ID = "R011-B016"
MODEL = "OpenAI Codex gpt-5.6-sol, Ultra"
AUTHORITY_COMMIT = "fee25091fb24e89c36296fd67c48c1fcf7a93b6e"
AUTHORITY_TREE = "d61cc601e7d97759ce805900520f784d02a0489e"

BASE_SNAPSHOT = ROOT / "qa/b015-build/source-snapshot-b015"
BASE_MANIFEST = ROOT / "qa/b015-build/R011-B015_SOURCE_MANIFEST.tsv"
BASE_SOURCE_QA = ROOT / "qa/b015-build/R011-B015_SOURCE_QA.json"
BASE_BUILD_RECEIPT = ROOT / "qa/b015-build/final/CANDIDATE_BUILD_QA_B015.json"
BASE_PDF = ROOT / "qa/b015-build/final/main.pdf"
BASE_TEXT = ROOT / "qa/b015-build/final/main-final.txt"
BASE_VISUAL_QA = ROOT / "qa/b015-visual/R011-B015_VISUAL_QA.json"
BASE_BOUNDARY_RECEIPT = ROOT / "qa/R011-B015_BOUNDARY_RECEIPT.json"
BASE_POST_ADMISSION = ROOT / "qa/b015-admission/R011-B015_POST_ADMISSION_VERIFICATION.json"
LIVE = ROOT / "repo"

CANDIDATE = ROOT / "scratch/b016-candidate"
MAIN_FRAGMENT = CANDIDATE / "ch_distributions_section_4_3_id.tex"
EOCE_FRAGMENT = CANDIDATE / "binomial_distribution_B016.tex"
ANSWER_FRAGMENT = CANDIDATE / "R011-B016_PUBLIC_ODD_ANSWERS.tex"
DATA_FRAGMENT = CANDIDATE / "data_binomialModel_B016.tex"
O001_GAPS = CANDIDATE / "R011-B016_O001_GAPS.json"
MAIN_RECEIPT = CANDIDATE / "R011-B016_MAIN_TRANSLATION_CANDIDATE_RECEIPT.json"
COMPANION_RECEIPT = CANDIDATE / "R011-B016_COMPANION_RECEIPT.json"
TERM_NOTES = CANDIDATE / "R011-B016_TERM_NOTES.md"
COMPANION_VERIFIER = CANDIDATE / "verify_b016_companion.py"

SOURCE_CLOSURE = ROOT / "qa/b016-source/R011-B016_SOURCE_CLOSURE.json"
ASSET_RIGHTS = ROOT / "qa/b016-assets/R011-B016_ASSET_RIGHTS_CLOSURE.json"
ASSET_MANIFEST = ROOT / "qa/b016-assets/R011-B016_ASSET_MANIFEST.csv"
CONTROLLED_TERMS = ROOT / "qa/b016-terminology/R011-B016_CONTROLLED_TERMS.tsv"
TRANSLATION_QA = ROOT / "qa/b016-translation/R011-B016_TRANSLATION_QA.json"

BUILD_ROOT = ROOT / "qa/b016-build"
SNAPSHOT = BUILD_ROOT / "source-snapshot-b016"
SOURCE_MANIFEST = BUILD_ROOT / "R011-B016_SOURCE_MANIFEST.tsv"
SOURCE_QA = BUILD_ROOT / "R011-B016_SOURCE_QA.json"
RUN_A = BUILD_ROOT / "replay-a"
RUN_B = BUILD_ROOT / "replay-b"
FINAL = BUILD_ROOT / "final"
FINAL_PDF = FINAL / "main.pdf"
FINAL_TEXT = FINAL / "main-final.txt"
BUILD_RECEIPT = FINAL / "CANDIDATE_BUILD_QA_B016.json"
REVIEW_RENDER = BUILD_ROOT / "review-render"
REVIEW_DPI = 180

MAIN_PATH = "ch_distributions/TeX/ch_distributions.tex"
EOCE_PATH = "ch_distributions/TeX/binomial_distribution.tex"
ANSWERS_PATH = "extraTeX/eoceSolutions/eoceSolutions.tex"
DATA_PATH = "extraTeX/data/data.tex"
FIGURE_ASSETS: dict[str, tuple[int, str]] = {
    "ch_distributions/figures/fourBinomialModelsShowingApproxToNormal/fourBinomialModelsShowingApproxToNormal.R":
        (728, "3c059f39a129735450b44215c52e31452ed30800a61f405f95701771499b110e"),
    "ch_distributions/figures/fourBinomialModelsShowingApproxToNormal/fourBinomialModelsShowingApproxToNormal.pdf":
        (5957, "a8224e53f7961fd869932d050902cbb081e03b74746f4f839af6b466912a9736"),
    "ch_distributions/figures/normApproxToBinomFail/normApproxToBinomFail.R":
        (761, "a846b551d5441d4f05d3c29971a3c4ab0318e9e80fde921a66c415ad63f7669b"),
    "ch_distributions/figures/normApproxToBinomFail/normApproxToBinomFail.pdf":
        (29317, "a9eb12774094b1e7e30a16ac69539b56af6d8a0bc803104637babf44b275af03"),
    "ch_distributions/figures/eoce/dreidel/dreidel.jpg":
        (377280, "4f86ab4609fa8e8e484095449da09fb344c88578de1ebc61b3e19e7eb3e30099"),
}
MODIFIED_PATHS = {MAIN_PATH, EOCE_PATH, ANSWERS_PATH, DATA_PATH}

BASE_FILES: dict[Path, tuple[int, str]] = {
    BASE_MANIFEST: (175582, "abd7c9df3fa41043a09c860c1b019cab279b85724f3430b14cacc5763636cf9f"),
    BASE_SOURCE_QA: (13521, "160b8ccac2c7fced4e936f11d7f42b5e4feeebd90119f54022c85f3d963e0fc6"),
    BASE_BUILD_RECEIPT: (18552, "037d367c2c431b898b81175feb248f5799e5011931ec508e062a2b58cee72809"),
    BASE_PDF: (22031786, "ea623a2b9139e28c7f3ba2604e48460b8e545f3324b4ea8b8a540ee9beeb8531"),
    BASE_TEXT: (1592709, "3ce3e11cf107bcd3902e1ea761bf10047d91c2a74bf5623f61f849c3c4377f16"),
    BASE_VISUAL_QA: (12153, "c690ced4b4e908e72f97b0bbb48393977a98bd062278a37b914b05088ee7caae"),
    BASE_BOUNDARY_RECEIPT: (14895, "e12ad9fa86c0614177c2fc1ea4257d5819d13a914f6c2b186d7ba85274f99dd0"),
    BASE_POST_ADMISSION: (2861, "2378271401afc768b89a1f5b60bc1fb77d05ea0248a23e5bbcae8c3e0c8cb684"),
}

TERMINAL_FILES: dict[Path, tuple[int, str]] = {
    MAIN_FRAGMENT: (25367, "8d99fee42d7f998cf7af6c3c7406457f503fdecd940b5985ca3aa63c4091d6ef"),
    EOCE_FRAGMENT: (9271, "e7030cb0c07cffb5881909e79edbfa2476e22abce5fb45e8e9cb62b869841768"),
    ANSWER_FRAGMENT: (1605, "d6b6ac7470d65fafdd7382004b43019f8f92029d717aa9f5a51b4327d173244c"),
    DATA_FRAGMENT: (956, "beddd03e4cca459911d425c17094eaea8aa8860b9ac922aa829337c109ec214c"),
    O001_GAPS: (1571, "293f1eead83affc4a0197a3a8838affdd8698da39e93be78be3513dcd3872266"),
    MAIN_RECEIPT: (6775, "39a6b26a67657db3b40b1eb1d8d9afecad66dc63fe7c1e04c3989f662cdb134d"),
    COMPANION_RECEIPT: (4999, "946da79575ad52f355d2e5db0795374df649e9d296a6016bd7a1b128f34ee0db"),
    TERM_NOTES: (3789, "2898e9cb72a3dc41fb4c8e89d90e2d6ff7524b7da3fc4d96fa2c25c2418c139f"),
    COMPANION_VERIFIER: (11333, "c59fea171067fd0cfef13b18c612df864212acee8ebecd754c016442a8b7f421"),
    SOURCE_CLOSURE: (11016, "a7da0fe79174fbbfe62f90f1bb7f17cdb5aad058c347adf23d3b0f61490fee8f"),
    ASSET_RIGHTS: (6800, "9c202cb46e9dba5cdc7de172c39654866d938d9f3db2d5e9f3cfd45716772fab"),
    ASSET_MANIFEST: (6109, "0055e1db8efaf6178097e09dde69040acb0f65514b7a3ce6f2aeaa505a86a811"),
    CONTROLLED_TERMS: (4525, "a24dbeb63cc74ec4e851a4eeb7e79ca04ca384aed6e2ec54cb5cb10cf8950ebc"),
    TRANSLATION_QA: (64573, "b372074c52cad8e3a730ad88320c66eee4e0fd7833f707cfeea45fb4d3a05c34"),
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


def load_manifest(path: Path = BASE_MANIFEST) -> dict[str, tuple[int, str]]:
    rows: dict[str, tuple[int, str]] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        parts = line.split("\t")
        require(len(parts) == 3, f"malformed source manifest line {line_number}")
        relative, size_text, digest = parts
        require(relative not in rows, f"duplicate source manifest path: {relative}")
        require(re.fullmatch(r"[0-9a-f]{64}", digest) is not None, f"invalid digest at line {line_number}")
        rows[relative] = (int(size_text), digest)
    require(len(rows) == 1206, f"B015 manifest row count changed: {len(rows)}")
    require(MODIFIED_PATHS <= rows.keys(), "one or more B016 overlay paths are outside B015 closure")
    return rows


def verify_base(rows: dict[str, tuple[int, str]]) -> dict[str, Any]:
    files = {rel(path): require_exact(path, size, digest) for path, (size, digest) in BASE_FILES.items()}
    require(BASE_SNAPSHOT.is_dir(), "B015 source snapshot absent")
    snapshot_inventory = shared.verify_manifest_snapshot(BASE_SNAPSHOT, rows)
    for relative, expected in rows.items():
        observed = shared.identity_under(LIVE / Path(relative), LIVE)
        require((observed["bytes"], observed["sha256"]) == expected, f"live admitted B015 drift: {relative}")
    live_paths = sorted(path.relative_to(LIVE).as_posix() for path in LIVE.rglob("*") if path.is_file())
    non_manifest = sorted(set(live_paths) - set(rows))
    require(non_manifest == EXPECTED_NON_MANIFEST_LIVE_FILES, "live non-manifest inventory changed")

    build = read_json(BASE_BUILD_RECEIPT)
    visual = read_json(BASE_VISUAL_QA)
    post = read_json(BASE_POST_ADMISSION)
    boundary = read_json(BASE_BOUNDARY_RECEIPT)
    require(build.get("status") == "PASS_ISOLATED_TWO_REPLAY_DETERMINISTIC_BUILD_ZERO_VISUAL_DEFECTS", "B015 build base not terminal PASS")
    require(visual.get("status") == "PASS_ZERO_VISUAL_DEFECTS_IN_BOUNDARY_ASSET_AND_TRANSITION_WINDOWS", "B015 visual base not terminal PASS")
    require(post.get("status") == "PASS_VERIFIED_ADMITTED_EXACT", "B015 is not exact admitted base")
    require(post.get("next_cursor", {}).get("label") == "binomialModel", "B015 next cursor changed")
    require(post.get("verification", {}).get("pages") == 427, "B015 reader page count changed")
    require(boundary.get("status") == "admitted_exact_pdf_source_assets_and_backend", "B015 boundary not admitted")
    return {
        "boundary_id": "R011-B015",
        "files": files,
        "snapshot": {"path": rel(BASE_SNAPSHOT), **snapshot_inventory},
        "live_manifest_paths_verified_exact": len(rows),
        "live_non_manifest_files_excluded": non_manifest,
        "build_status": build["status"],
        "visual_status": visual["status"],
        "post_admission_status": post["status"],
        "page_count": 427,
        "next_cursor": "binomialModel",
    }


def run_companion_verifier_twice(receipt: dict[str, Any]) -> dict[str, Any]:
    expected = receipt["verification"]["run_a_stdout_sha256"]
    runs: list[dict[str, Any]] = []
    stdout_values: list[bytes] = []
    stderr_values: list[bytes] = []
    for number in (1, 2):
        completed = subprocess.run([sys.executable, str(COMPANION_VERIFIER)], cwd=ROOT, capture_output=True)
        require(completed.returncode == 0, f"B016 companion verifier run {number} failed")
        require(hashlib.sha256(completed.stdout).hexdigest() == expected, f"B016 companion verifier stdout changed on run {number}")
        require(completed.stderr == b"", f"B016 companion verifier stderr nonempty on run {number}")
        parsed = json.loads(completed.stdout.decode("utf-8"))
        require(parsed.get("status") == "PASS" and len(parsed.get("checks", [])) == 30, "B016 companion verifier did not report 30/30 PASS")
        stdout_values.append(completed.stdout)
        stderr_values.append(completed.stderr)
        runs.append({
            "run": number,
            "returncode": completed.returncode,
            "stdout_bytes": len(completed.stdout),
            "stdout_sha256": hashlib.sha256(completed.stdout).hexdigest(),
            "stderr_bytes": len(completed.stderr),
            "stderr_sha256": hashlib.sha256(completed.stderr).hexdigest(),
        })
    require(stdout_values[0] == stdout_values[1], "B016 companion verifier stdout replays differ")
    require(stderr_values[0] == stderr_values[1] == b"", "B016 companion verifier stderr replay mismatch")
    return {"runs": runs, "stdout_byte_identical": True, "stderr_byte_identical_and_empty": True}


def verify_terminal() -> dict[str, Any]:
    exact = {rel(path): require_exact(path, size, digest) for path, (size, digest) in TERMINAL_FILES.items()}
    main_receipt = read_json(MAIN_RECEIPT)
    companion = read_json(COMPANION_RECEIPT)
    source = read_json(SOURCE_CLOSURE)
    assets = read_json(ASSET_RIGHTS)
    translation_qa = read_json(TRANSLATION_QA)
    require(main_receipt.get("boundary_id") == BOUNDARY_ID, "main candidate boundary mismatch")
    require(main_receipt.get("status") == "COMPLETE_MAIN_SECTION_TRANSLATION_CANDIDATE_READY_FOR_BOUNDED_ASSEMBLY", "main candidate not assembly-ready")
    require(main_receipt.get("candidate", {}).get("sha256") == TERMINAL_FILES[MAIN_FRAGMENT][1], "main receipt does not bind candidate")
    require(main_receipt.get("next_cursor", {}).get("label") == "negativeBinomial", "main next cursor changed")
    require(companion.get("status") == "PASS_CANDIDATE_COMPANION_SURFACES", "companion receipt not PASS")
    require(source.get("status") == "PASS_EXACT_SOURCE_RIGHTS_ASSET_AND_NEXT_CURSOR_CLOSURE", "source closure not PASS")
    require(assets.get("status") == "PASS_EXACT_ASSET_IDENTITY_RIGHTS_AND_REUSE_DECISIONS_CLOSED", "asset/rights closure not PASS")
    require(
        translation_qa.get("status") == "PASS_EXACT_PINNED_AUTHORITY_TRANSLATION_INTEGRATION"
        and translation_qa.get("check_summary") == {"total": 140, "passed": 140, "failed": 0},
        "translation integration QA not terminal PASS",
    )
    require(assets.get("dreidel_photo", {}).get("license") == "CC BY 2.0", "dreidel component license changed")
    require("include unchanged" in assets.get("dreidel_photo", {}).get("disposition", "").casefold(), "dreidel disposition changed")
    require(MODEL in json.dumps([main_receipt, source, assets], ensure_ascii=False), "exact model provenance absent")
    require(companion["coverage"]["o001_missing_public_answer_gaps"] == [18, 20, 22, 24, 26], "O001 gaps changed")

    asset_bindings: dict[str, Any] = {}
    for relative, (size, digest) in FIGURE_ASSETS.items():
        live = require_exact(LIVE / relative, size, digest)
        base = require_exact(BASE_SNAPSHOT / relative, size, digest)
        asset_bindings[relative] = {"live": live, "base_snapshot": base, "reused_byte_exact": True}
    return {
        "exact_inputs": exact,
        "companion_verifier": run_companion_verifier_twice(companion),
        "coverage": {
            "section": "4.3 Distribusi binomial / binomialModel",
            "subsections": 3,
            "worked_examples": 4,
            "guided_exercises": 10,
            "guided_inline_answers": 10,
            "eoce_ids": list(range(17, 27)),
            "public_answer_ids": [17, 19, 21, 23, 25],
            "o001_missing_public_answers": [18, 20, 22, 24, 26],
            "data_appendix_entries": 3,
            "direct_reader_assets": 3,
            "adjacent_r_producers": 2,
        },
        "asset_reuse": asset_bindings,
        "dreidel_rights": {
            "license": "CC BY 2.0",
            "creator": "Staccabees",
            "source_display": "http://flic.kr/p/7gLZTf",
            "preserved_byte_exact": True,
            "visible_attribution_required": True,
        },
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
        b"\\section{Binomial distribution}\n\\label{binomialModel}",
        b"\\section{Negative binomial distribution}\n\\label{negativeBinomial}",
        MAIN_FRAGMENT.read_bytes(),
        "Section 4.3",
    )


def assemble_answers(base: bytes) -> tuple[bytes, dict[str, Any]]:
    chapter = base.find(b"\\eocesolch{Distribusi variabel acak}")
    next_chapter = base.find(b"\\eocesolch", chapter + 1)
    require(chapter >= 0 and next_chapter > chapter, "Chapter 4 public-answer region absent")
    start = base.find(b"% 17", chapter, next_chapter)
    end = base.find(b"% 27", start, next_chapter)
    require(start >= 0 and end > start, "public-answer 17-25 anchors absent")
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
    start_marker = b"\\item[\\ref{binomialModel}]"
    end_marker = b"\\item[\\ref{negativeBinomial}]"
    start = base.find(start_marker)
    end = base.find(end_marker, start + len(start_marker))
    require(start >= 0 and end > start, "binomialModel data appendix splice markers absent")
    require(base[start:end].count(start_marker) == 3, "binomialModel data entry closure is not exactly three")
    removed = base[start:end]
    fragment = DATA_FRAGMENT.read_bytes()
    return base[:start] + fragment + base[end:], {
        "first_following_negative_binomial_item_selected": True,
        "base_prefix_bytes": start,
        "base_suffix_bytes": len(base) - end,
        "removed_entry_count": 3,
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
    require(main.count(r"\section{") == 1 and main.count(r"\subsection{") == 3, "Section structure changed")
    require(main.count(r"\begin{nexample}") == 4, "worked-example closure changed")
    require(main.count(r"\begin{nexercise}") == 10 and main.count(r"\footnotetext") == 10, "guided exercise/answer closure changed")
    require(main.count(r"\newcommand{") == 45, "newcommand closure changed")
    require(main.count(r"\begin{figure}") == 2, "figure closure changed")
    labels = re.findall(r"\\label\{([^}]+)\}", main)
    require(labels == [
        "binomialModel", "insureOneOfFourExceedsDeductible", "factorial_defined",
        "isItBinomialTipBox", "noMoreThanOneFriendWSevereLungCondition",
        "normalApproxBinomialDistSubsection", "exactBinomSmokerExSetup",
        "fourBinomialModelsShowingApproxToNormal", "approxNormalForSmokerBinomEx",
        "normApproxToBinomFail",
    ], "Section labels/order changed")
    eoce_ids = [int(value) for value in re.findall(r"^% (\d+)$", eoce, flags=re.MULTILINE)]
    eoce_labels = re.findall(r"\\label\{([^}]+)\}", eoce)
    require(eoce_ids == list(range(17, 27)) and eoce.count(r"\eoce{") == 10, "EoCE closure changed")
    require(eoce_labels == [
        "underage_drinking_intro", "chicken_pox_intro", "underage_drinking_normal_approx",
        "chicken_pox_normal_approx", "dreidel", "arachnophobia", "eye_color_binomial",
        "sickle_cell_anemia", "explore_combinations", "male_children",
    ], "EoCE labels/order changed")
    answer_ids = [int(value) for value in re.findall(r"^% (\d+)$", answers, flags=re.MULTILINE)]
    require(answer_ids == [17, 19, 21, 23, 25] and answers.count(r"\eocesol{") == 5, "public answer closure changed")
    require(data.count(r"\item[\ref{binomialModel}]") == 3 and data.count(r"\datawrap{") == 3, "data-entry closure changed")
    require("^{th}" not in eoce and "^{rd}" not in eoce, "English ordinal suffix remains")
    require("SAMSHA" not in eoce and "will the be" not in eoce, "known source defect remains")
    require("Foto oleh Staccabees" in eoce and "textbook-CC_BY_2" in eoce and "http://flic.kr/p/7gLZTf" in eoce, "dreidel attribution/license linkage changed")
    combined = main + eoce + answers + data
    for forbidden in (
        "The binomial distribution", "Underage drinking, Part I", "Chicken pox, Part I",
        "Underage drinking, Part II", "Chicken pox, Part II", "Dreidel game",
        "Eye color, Part II", "Sickle cell anemia", "Explore combinations", "Male children",
        "Exceeding insurance deductible", "Smoking friends", "US smoking rate",
    ):
        require(forbidden not in combined, f"reader-visible English remains: {forbidden}")
    asset_checks: dict[str, Any] = {}
    for relative, expected in FIGURE_ASSETS.items():
        observed = shared.identity_under(snapshot / relative, snapshot)
        require((observed["bytes"], observed["sha256"]) == expected, f"byte-exact B016 asset reuse changed: {relative}")
        asset_checks[relative] = {**observed, "reused_byte_exact": True}
    return {
        "splice_qa": splice_qa,
        "section": {
            "subsections": 3,
            "worked_examples": 4,
            "guided_exercises": 10,
            "guided_inline_answers": 10,
            "newcommands": 45,
            "figure_ids": ["fourBinomialModelsShowingApproxToNormal", "normApproxToBinomFail"],
        },
        "eoce": {"exercise_ids": eoce_ids, "labels": eoce_labels, "parts": 40},
        "public_answers": {"ids": answer_ids, "o001_gaps": [18, 20, 22, 24, 26]},
        "data_appendix_entries": 3,
        "locale_ordinal_adaptations": 2,
        "selected_reader_visible_english_count": 0,
        "asset_reuse": asset_checks,
        "dreidel_cc_by_2_attribution_preserved": True,
        "exercise_answer_closure_exact": True,
        "unrelated_manifest_paths_preserved_byte_exact": 1202,
    }


def prepare_snapshot(rows: dict[str, tuple[int, str]], base: dict[str, Any], terminal: dict[str, Any]) -> dict[str, tuple[int, str]]:
    for path in (SNAPSHOT, SOURCE_MANIFEST, SOURCE_QA, RUN_A, RUN_B, FINAL, REVIEW_RENDER):
        require(not path.exists(), f"refusing to overwrite existing B016 build output: {rel(path)}")
    BUILD_ROOT.mkdir(parents=True, exist_ok=True)
    shutil.copytree(BASE_SNAPSHOT, SNAPSHOT)
    base_main = (BASE_SNAPSHOT / MAIN_PATH).read_bytes()
    base_answers = (BASE_SNAPSHOT / ANSWERS_PATH).read_bytes()
    base_data = (BASE_SNAPSHOT / DATA_PATH).read_bytes()
    main, main_qa = assemble_main(base_main)
    answers, answer_qa = assemble_answers(base_answers)
    data, data_qa = assemble_data(base_data)
    assembled = {
        MAIN_PATH: main,
        EOCE_PATH: EOCE_FRAGMENT.read_bytes(),
        ANSWERS_PATH: answers,
        DATA_PATH: data,
    }
    base_rows = dict(rows)
    for relative, raw in assembled.items():
        destination = SNAPSHOT / relative
        destination.write_bytes(raw)
        rows[relative] = (len(raw), hashlib.sha256(raw).hexdigest())
    require(all(rows[path] == base_rows[path] for path in rows if path not in MODIFIED_PATHS), "an unrelated manifest identity changed")
    rows = dict(sorted(rows.items()))
    SOURCE_MANIFEST.write_text(
        "".join(f"{path}\t{size}\t{digest}\n" for path, (size, digest) in rows.items()),
        encoding="utf-8",
        newline="\n",
    )
    inventory = shared.verify_manifest_snapshot(SNAPSHOT, rows)
    checks = source_checks(SNAPSHOT, {"main": main_qa, "public_answers": answer_qa, "data": data_qa})
    overlays = {
        path: {"target": f"{rel(SNAPSHOT)}/{path}", **shared.identity_under(SNAPSHOT / path, SNAPSHOT)}
        for path in sorted(MODIFIED_PATHS)
    }
    source_qa = {
        "$schema": "interlanguage.r011-b016-source-qa/v1",
        "boundary_id": BOUNDARY_ID,
        "status": "PASS_EXACT_ADMITTED_B015_MANIFEST_PLUS_FOUR_B016_COMPONENTS_AND_BYTE_EXACT_ASSET_REUSE",
        "authority": {"commit": AUTHORITY_COMMIT, "tree": AUTHORITY_TREE},
        "base_boundary": "R011-B015",
        "base_evidence": base,
        "terminal_inputs": terminal,
        "builder": identity(Path(__file__)),
        "manifest": {**identity(SOURCE_MANIFEST), "files": len(rows)},
        "snapshot": {"path": rel(SNAPSHOT), **inventory},
        "translated_component_count": 4,
        "modified_manifest_path_count": 4,
        "reused_direct_asset_and_producer_count": len(FIGURE_ASSETS),
        "overlays": overlays,
        "checks": checks,
        "translation_scope": "Complete Section 4.3 Distribusi binomial; EoCE 17-26; public answers 17/19/21/23/25; three binomialModel data appendix entries; two locale-neutral figure R/PDF pairs and the dreidel photo reused byte-exact.",
        "o001_gaps": [18, 20, 22, 24, 26],
        "production_model": MODEL,
        "rights": {
            "book_and_generated_figures": "CC BY-SA 3.0 Unported",
            "dreidel_photo_component": "CC BY 2.0; creator/source/crop/license attribution preserved",
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
    return rows


def page_texts(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8", errors="replace").split("\f")


def first_page(pages: list[str], phrases: Iterable[str], minimum: int = 1, maximum: int | None = None) -> int | None:
    folded = [phrase.casefold() for phrase in phrases]
    limit = len(pages) if maximum is None else min(maximum, len(pages))
    for page in range(max(1, minimum), limit + 1):
        text = pages[page - 1].casefold()
        if all(phrase in text for phrase in folded):
            return page
    return None


def first_page_regex(pages: list[str], pattern: str, minimum: int = 1, maximum: int | None = None) -> int | None:
    limit = len(pages) if maximum is None else min(maximum, len(pages))
    compiled = re.compile(pattern, flags=re.IGNORECASE | re.MULTILINE)
    for page in range(max(1, minimum), limit + 1):
        if compiled.search(pages[page - 1]):
            return page
    return None


def locate_pages(text_path: Path) -> dict[str, Any]:
    pages = page_texts(text_path)
    section_start = first_page(pages, ["Distribusi binomial"], minimum=130, maximum=220)
    require(section_start is not None, "Section 4.3 start page absent")
    next_section = first_page(pages, ["Negative binomial distribution"], minimum=section_start + 1, maximum=240)
    require(next_section is not None, "Section 4.4 transition page absent")
    eoce_start = first_page(pages, ["Konsumsi alkohol di bawah umur, Bagian I"], minimum=section_start, maximum=next_section)
    eoce_end = first_page(pages, ["Anak laki-laki"], minimum=eoce_start or section_start, maximum=next_section)
    require(eoce_start is not None and eoce_end is not None and eoce_end >= eoce_start, "EoCE 17-26 page closure absent")
    answer_start = first_page_regex(pages, r"4\.17\s+\(a\)", minimum=350, maximum=420)
    answer_next = first_page_regex(pages, r"4\.27\s+", minimum=answer_start or 350, maximum=420)
    require(answer_start is not None and answer_next is not None and answer_next >= answer_start, "public answer 17-to-27 boundary absent")
    data_start = first_page(pages, ["4.3", "Melampaui batas risiko sendiri asuransi"], minimum=400)
    data_next = first_page(pages, ["4.4", "Football kicker"], minimum=data_start or 400)
    require(data_start is not None and data_next is not None and data_next >= data_start, "binomial data appendix boundary absent")
    return {
        "section_start_page": section_start,
        "eoce_start_page": eoce_start,
        "eoce_end_page": eoce_end,
        "next_section_page": next_section,
        "public_answer_start_page": answer_start,
        "public_answer_next_page": answer_next,
        "data_appendix_start_page": data_start,
        "data_appendix_next_page": data_next,
        "section_eoce_and_transition_window": [max(1, section_start - 1), min(len(pages), next_section + 1)],
        "public_answer_and_transition_window": [max(1, answer_start - 1), min(len(pages), answer_next + 1)],
        "data_appendix_and_transition_window": [max(1, data_start - 1), min(len(pages), data_next + 1)],
        "transition": "Section 4.3 / Distribusi binomial -> Section 4.4 / Negative binomial distribution",
    }


def reader_checks(text_path: Path, mapping: dict[str, Any]) -> dict[str, Any]:
    pages = page_texts(text_path)
    section_text = "\n".join(pages[mapping["section_start_page"] - 1 : mapping["next_section_page"] - 1])
    expected = [
        "Distribusi binomial",
        "Pendekatan normal terhadap distribusi binomial",
        "Pendekatan normal tidak akurat pada interval kecil",
        "Konsumsi alkohol di bawah umur, Bagian I",
        "Cacar air, Bagian I",
        "Permainan dreidel",
        "Araknofobia",
        "Anemia sel sabit",
        "Menjelajahi permutasi",
        "Anak laki-laki",
        "Foto oleh Staccabees",
        "lisensi CC BY 2.0",
    ]
    absent = [value for value in expected if value.casefold() not in section_text.casefold()]
    require(not absent, f"reader text lacks B016 terms/attribution: {absent}")
    forbidden = [
        "The binomial distribution", "Normal approximation to the binomial distribution",
        "The normal approximation breaks down on small intervals", "Underage drinking, Part I",
        "Chicken pox, Part I", "Underage drinking, Part II", "Chicken pox, Part II",
        "Dreidel game", "Eye color, Part II", "Sickle cell anemia", "Explore combinations",
        "Male children", "Photo by Staccabees",
    ]
    forbidden_counts = {value: section_text.casefold().count(value.casefold()) for value in forbidden}
    require(not any(forbidden_counts.values()), f"reader-visible boundary English remains: {forbidden_counts}")

    a0, a1 = mapping["public_answer_and_transition_window"]
    answer_window = "\n".join(pages[a0 - 1 : a1])
    # The answer appendix is two-column. pdftotext emits the left column
    # (4.19, 4.25, 4.27) before the right column (4.21, 4.23), so slicing at
    # the first textual 4.27 would incorrectly discard valid odd answers.
    # Bound by the already located answer pages instead.
    answer_text = "\n".join(
        pages[
            mapping["public_answer_start_page"] - 1 :
            mapping["public_answer_next_page"]
        ]
    )
    require(all(f"4.{value}" in answer_text for value in (17, 19, 21, 23, 25)), "public answer numbering incomplete")
    require(all(f"4.{value}" not in answer_text for value in (18, 20, 22, 24, 26)), "O001 gap answers unexpectedly present")
    answer_forbidden = ["The binomial conditions are met", "Using the normal approximation"]
    answer_counts = {value: answer_text.casefold().count(value.casefold()) for value in answer_forbidden}
    require(not any(answer_counts.values()), f"public-answer English remains: {answer_counts}")

    d0, d1 = mapping["data_appendix_and_transition_window"]
    data_window = "\n".join(pages[d0 - 1 : d1])
    data_start = data_window.find("4.3 Melampaui batas risiko sendiri asuransi")
    data_end = data_window.find("4.4 Football kicker", data_start + 1)
    require(data_start >= 0 and data_end > data_start, "binomial data-entry text boundary absent")
    data_text = data_window[data_start:data_end]
    for value in ("Melampaui batas risiko sendiri asuransi", "Teman-teman yang merokok", "Tingkat merokok di AS"):
        require(value in data_text, f"localized data entry absent: {value}")
    data_forbidden = ["Exceeding insurance deductible", "Smoking friends", "US smoking rate", "These statistics were made up"]
    data_counts = {value: data_text.casefold().count(value.casefold()) for value in data_forbidden}
    require(not any(data_counts.values()), f"data-entry English remains: {data_counts}")
    return {
        "status": "PASS_EXACT_READER_TEXT_RIGHTS_AND_BOUNDARY_CLOSURE",
        "expected_terms_and_attribution": expected,
        "absent": [],
        "translated_boundary_forbidden_phrase_counts": forbidden_counts,
        "localized_public_answer_forbidden_phrase_counts": answer_counts,
        "localized_data_forbidden_phrase_counts": data_counts,
        "exercise_ids": list(range(17, 27)),
        "public_answer_ids": [17, 19, 21, 23, 25],
        "o001_gaps": [18, 20, 22, 24, 26],
        "data_appendix_entries_localized": 3,
        "locale_neutral_figure_pairs_reused_byte_exact": 2,
        "dreidel_photo_and_visible_cc_by_2_attribution_preserved": True,
    }


def expected_review_pages(mapping: dict[str, Any]) -> set[int]:
    pages: set[int] = set()
    for key in ("section_eoce_and_transition_window", "public_answer_and_transition_window", "data_appendix_and_transition_window"):
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
        require((item["bytes"], item["sha256"]) == (base[name]["bytes"], base[name]["sha256"]), f"B015 toolchain identity changed: {name}")
    return observed


def execute_build() -> dict[str, Any]:
    rows = load_manifest()
    base = verify_base(rows)
    terminal = verify_terminal()
    rows = prepare_snapshot(rows, base, terminal)
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
        "$schema": "interlanguage.r011-b016-candidate-build-qa/v1",
        "boundary_id": BOUNDARY_ID,
        "status": "PASS_ISOLATED_TWO_REPLAY_DETERMINISTIC_BUILD_VISUAL_INSPECTION_PENDING",
        "authority": {"commit": AUTHORITY_COMMIT, "tree": AUTHORITY_TREE},
        "base_boundary": "R011-B015",
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
            "trailer_seed_source": "first 128 bits of SHA-256(R011-B016_SOURCE_MANIFEST.tsv)",
            "trailer_seed": trailer_seed.lower(),
            "established_b015_sequence": [
                "pdflatex pass 1", "bibtex", "makeindex 1", "pdflatex pass 2",
                "makeindex 2", "pdflatex pass 3", "makeindex 3", "pdflatex pass 4",
            ],
        },
        "page_count": run_a["page_count"],
        "affected_page_mapping": mapping,
        "reader_checks": text_qa,
        "exercise_answer_closure": {
            "eoce": list(range(17, 27)),
            "public": [17, 19, 21, 23, 25],
            "o001_gaps": [18, 20, 22, 24, 26],
            "exact": True,
        },
        "visual": {
            "status": "RENDERED_ONLY_NOT_YET_VISUALLY_INSPECTED",
            "render_dpi": REVIEW_DPI,
            "pages": [item["page"] for item in renders],
            "artifacts": renders,
        },
        "toolchain": toolchain,
        "translation_scope": "Complete Section 4.3 Distribusi binomial; EoCE 17-26; public answers 17/19/21/23/25; three binomialModel data appendix entries; byte-exact locale-neutral figures and CC BY 2.0 dreidel photo.",
        "o001_gaps": [18, 20, 22, 24, 26],
        "rights": {
            "book_and_generated_figures": "CC BY-SA 3.0 Unported",
            "dreidel_photo": "CC BY 2.0, Staccabees, cropped, source and license attribution visible",
            "openintro_r_package": "GPL-3 build dependency, not bundled as book content",
        },
        "next_cursor": {"section": "Negative binomial distribution", "label": "negativeBinomial", "authority_line": 1927},
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


def main() -> int:
    if sys.argv[1:] != ["--build"]:
        raise SystemExit("usage: build_b016_candidate.py --build")
    result = execute_build()
    print(json.dumps({
        "boundary_id": result["boundary_id"],
        "status": result["status"],
        "page_count": result["page_count"],
        "candidate_artifact": result["candidate_artifact"],
        "source_manifest": result["source_manifest"],
        "source_qa": result["source_qa"],
        "affected_page_mapping": result["affected_page_mapping"],
        "review_pages": result["visual"]["pages"],
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except GateError as exc:
        raise SystemExit(f"REFUSED: {exc}")
