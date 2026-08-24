#!/usr/bin/env python3
"""Fail-closed isolated deterministic build harness for R011-B012.

The harness consumes the exact admitted B011 source snapshot, a terminal B012
translation QA receipt, the terminal terminology receipt, and the terminal
localized-asset closure.  It never edits ``repo``, ``backend``, ``output``,
``release``, control files, credentials, or Git state.  A build is allowed only
after every terminal byte is transitively hash-bound by the final translation
receipt.

Two complete LaTeX builds are executed into independent output directories.
Their pass-3/pass-4 PDFs and their final PDFs must all be byte-identical before
the conventional QA candidate is emitted.  Pages are rendered for a later
visual audit, but this script deliberately does not grant visual approval.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
BOUNDARY_ID = "R011-B012"
MODEL = "OpenAI Codex gpt-5.6-sol, Ultra"
AUTHORITY_COMMIT = "fee25091fb24e89c36296fd67c48c1fcf7a93b6e"
AUTHORITY_TREE = "d61cc601e7d97759ce805900520f784d02a0489e"

BASE_SNAPSHOT = ROOT / "qa" / "b011-build" / "source-snapshot-b011"
BASE_MANIFEST = ROOT / "qa" / "b011-build" / "R011-B011_SOURCE_MANIFEST.tsv"
BASE_SOURCE_QA = ROOT / "qa" / "b011-build" / "R011-B011_SOURCE_QA.json"
BASE_BUILD_RECEIPT = ROOT / "qa" / "b011-build" / "final" / "CANDIDATE_BUILD_QA_B011.json"
BASE_PDF = ROOT / "qa" / "b011-build" / "final" / "main.pdf"

CANDIDATE = ROOT / "scratch" / "b012-candidate"
ASSET_ROOT = ROOT / "scratch" / "b012-assets"
TERMINOLOGY_ROOT = ROOT / "qa" / "b012-terminology"
PRE_REVIEW = CANDIDATE / "R011-B012_TRANSLATION_CANDIDATE_RECEIPT.json"
FINAL_TRANSLATION_QA = CANDIDATE / "R011-B012_FINAL_TRANSLATION_QA.json"
ASSET_CLOSURE = ASSET_ROOT / "R011-B012_ASSET_CLOSURE.json"
LOCALIZED_FIGURE_RECEIPT = ASSET_ROOT / "localized" / "R011-B012_LOCALIZED_FIGURE_RECEIPT.json"
TERMINOLOGY_QA = TERMINOLOGY_ROOT / "R011-B012_TERMINOLOGY_QA.json"
TERMS_TSV = TERMINOLOGY_ROOT / "R011-B012_TERMS.tsv"
CONTROLLED_TERMS_TSV = TERMINOLOGY_ROOT / "R011-B012_CONTROLLED_TERMS.tsv"
REJECTED_PRE_REFLOW_VISUAL_QA = ROOT / "qa" / "b012-visual" / "R011-B012_VISUAL_QA_REJECTED_PRE_REFLOW.json"

MAIN_FRAGMENT = CANDIDATE / "ch_probability_section_3_4_id.tex"
EOCE_FRAGMENT = CANDIDATE / "random_variables_B012.tex"
ANSWER_FRAGMENT = CANDIDATE / "R011-B012_PUBLIC_ODD_ANSWERS.tex"
FULL_MAIN = CANDIDATE / "ch_probability_B012_source.tex"
FULL_ANSWERS = CANDIDATE / "eoceSolutions_B012_source.tex"
PREFACE_OVERLAY = CANDIDATE / "preface_B012_source.tex"
BOOK_R_OVERLAY = CANDIDATE / "assets" / "bookCostDist" / "bookCostDist_B012.R"
STOCK_R_OVERLAY = (
    CANDIDATE
    / "assets"
    / "changeInLeonardsStockPortfolioFor36Months"
    / "changeinleonardsstockportfoliofor36months_B012.R"
)
BOOK_PDF_OVERLAY = ASSET_ROOT / "localized" / "bookCostDist" / "bookCostDist.id-ID.pdf"
STOCK_PDF_OVERLAY = (
    ASSET_ROOT
    / "localized"
    / "changeInLeonardsStockPortfolioFor36Months"
    / "changeInLeonardsStockPortfolioFor36Months.id-ID.pdf"
)

BUILD_ROOT = ROOT / "qa" / "b012-build"
SNAPSHOT = BUILD_ROOT / "source-snapshot-b012"
SOURCE_MANIFEST = BUILD_ROOT / "R011-B012_SOURCE_MANIFEST.tsv"
SOURCE_QA = BUILD_ROOT / "R011-B012_SOURCE_QA.json"
RUN_A = BUILD_ROOT / "replay-a"
RUN_B = BUILD_ROOT / "replay-b"
FINAL = BUILD_ROOT / "final"
FINAL_PDF = FINAL / "main.pdf"
FINAL_TEXT = FINAL / "main-final.txt"
BUILD_RECEIPT = FINAL / "CANDIDATE_BUILD_QA_B012.json"
REVIEW_RENDER = BUILD_ROOT / "review-render"

MAIN_START = r"\section{Random variables}"
MAIN_END = r"\section{Continuous distributions}"
TARGET_MAIN_START = r"\section{Variabel acak}"
INPUT_TOKEN = r"{\input{ch_probability/TeX/random_variables.tex}}"
ANSWER_CONTEXT = "ch_probability/figures/eoce/tree_lupus/tree_lupus.pdf"
ANSWER_START = "% 29"
ANSWER_END = "% 37"
LAYOUT_BREAK = r"\D{\newpage}"
LAYOUT_COMMENT = "% Tata letak: pemisah halaman paksa yang usang dihapus."
EOCE_LAYOUT_INSERTION = "\n" + LAYOUT_BREAK + "\n\n% 33"
EOCE_LAYOUT_PREIMAGE = "\n% 33"
PRE_REFLOW_MAIN_FRAGMENT_SHA256 = "4222adfda1fd247b6ef6a01526565cce67f7731b5e713d579720f6d7239eb848"
PRE_REFLOW_FULL_MAIN_SHA256 = "26c34c2a5b4004be0b9205ceb132c29f312a8fce9bd59ef049528f7d34b38e73"
PRE_REFLOW_EOCE_SHA256 = "59431fdd5fc1d89638faa4bf9c0b336c44eee16e1c86b2eef29a3b8bf8f37566"
REJECTED_PRE_REFLOW_VISUAL_QA_IDENTITY = (
    3880,
    "ec44f577f92127dc46c28f111f526bcee55066b89a427111d9930d901b61d214",
)

REQUIRED_BASE_IDENTITIES: dict[str, tuple[int, str]] = {
    "qa/b011-build/R011-B011_SOURCE_MANIFEST.tsv": (
        175582,
        "e11d80dd7544a15ea1bb31194db22430bdb12faf260ad36d6996354e37264e08",
    ),
    "qa/b011-build/R011-B011_SOURCE_QA.json": (
        3934,
        "c6b2122950168bae7bbd4b8c0153c8cd3e1d695253656428b02c1e2abf8323b0",
    ),
    "qa/b011-build/final/CANDIDATE_BUILD_QA_B011.json": (
        12798,
        "73fc881994299d2ed08db553872e70e0c5da2b1044beadebb52320e40f378607",
    ),
    "qa/b011-build/final/main.pdf": (
        22026585,
        "f5842874239487faec2154324d61897cf2a411529e2a07fbb131e88399d92a4a",
    ),
}

REQUIRED_BASE_SNAPSHOT_IDENTITIES: dict[str, tuple[int, str]] = {
    "ch_probability/TeX/ch_probability.tex": (
        134438,
        "76a217d5f94f6bdc5ee56772a895b974cfd9cce56c1cf46b266ad9412931a61f",
    ),
    "ch_probability/TeX/random_variables.tex": (
        4804,
        "e6b7dd329d07781270b3545bc9ad641cc0d9c2972df274ea082119e9341ebc6c",
    ),
    "extraTeX/eoceSolutions/eoceSolutions.tex": (
        108990,
        "7e03cdd359c3415bcd5fa2b8932866456be981f6bd511118e917fe36c9a2e512",
    ),
    "extraTeX/preamble/preface.tex": (
        10078,
        "5c1c7811bb067ff7d3c0a3eb50c3a8d9e141c832ec7013220378159ce4a0561d",
    ),
    "ch_probability/figures/bookCostDist/bookCostDist.R": (
        1613,
        "e7ecc54537b58a1239f2f829685ab83c6896e273a8e0fd3781648394f70c97ea",
    ),
    "ch_probability/figures/bookCostDist/bookCostDist.pdf": (
        4373,
        "b6c2d6e56b3bd7ce1d8c03fd826bc0c610e6989b40227af8e548034b163d4d06",
    ),
    "ch_probability/figures/changeInLeonardsStockPortfolioFor36Months/changeinleonardsstockportfoliofor36months.R": (
        658,
        "e44624d3f9620550691fbd6f1e0ea3db73caaf95cd956cc2bbe4c35b992cfaa4",
    ),
    "ch_probability/figures/changeInLeonardsStockPortfolioFor36Months/changeInLeonardsStockPortfolioFor36Months.pdf": (
        6740,
        "b19b74aeb3153029221ce6cd5294704157d5e669044ad07054f6fac64b1e4363",
    ),
}

PRE_REVIEW_CANDIDATE_PATHS = (
    MAIN_FRAGMENT,
    EOCE_FRAGMENT,
    ANSWER_FRAGMENT,
    FULL_MAIN,
    FULL_ANSWERS,
    PREFACE_OVERLAY,
    BOOK_R_OVERLAY,
    STOCK_R_OVERLAY,
)

FINAL_DIRECT_BINDINGS = (
    MAIN_FRAGMENT,
    EOCE_FRAGMENT,
    ANSWER_FRAGMENT,
    FULL_MAIN,
    FULL_ANSWERS,
    PREFACE_OVERLAY,
    PRE_REVIEW,
    TERMINOLOGY_QA,
    TERMS_TSV,
    CONTROLLED_TERMS_TSV,
    ASSET_CLOSURE,
    BOOK_PDF_OVERLAY,
    STOCK_PDF_OVERLAY,
)

OVERLAYS: dict[str, Path] = {
    "ch_probability/TeX/ch_probability.tex": FULL_MAIN,
    "ch_probability/TeX/random_variables.tex": EOCE_FRAGMENT,
    "extraTeX/eoceSolutions/eoceSolutions.tex": FULL_ANSWERS,
    "extraTeX/preamble/preface.tex": PREFACE_OVERLAY,
    "ch_probability/figures/bookCostDist/bookCostDist.R": BOOK_R_OVERLAY,
    "ch_probability/figures/bookCostDist/bookCostDist.pdf": BOOK_PDF_OVERLAY,
    "ch_probability/figures/changeInLeonardsStockPortfolioFor36Months/changeinleonardsstockportfoliofor36months.R": STOCK_R_OVERLAY,
    "ch_probability/figures/changeInLeonardsStockPortfolioFor36Months/changeInLeonardsStockPortfolioFor36Months.pdf": STOCK_PDF_OVERLAY,
}


class GateError(RuntimeError):
    pass


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def identity(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise GateError(f"required file absent: {path}")
    raw = path.read_bytes()
    return {"path": rel(path), "bytes": len(raw), "sha256": sha256(raw)}


def tool_identity(name: str, path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise GateError(f"required build tool absent: {name}")
    raw = path.read_bytes()
    return {"name": name, "executable": path.name, "bytes": len(raw), "sha256": sha256(raw)}


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise GateError(f"required receipt absent: {path}") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GateError(f"invalid JSON receipt: {path}: {exc}") from exc


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GateError(message)


def require_exact(path: Path, expected_bytes: int, expected_sha256: str) -> dict[str, Any]:
    observed = identity(path)
    require(
        observed["bytes"] == expected_bytes and observed["sha256"] == expected_sha256,
        f"identity mismatch for {observed['path']}: {observed['bytes']} {observed['sha256']}",
    )
    return observed


def normalize_bound_path(value: str) -> str | None:
    candidate = value.replace("\\", "/")
    root = ROOT.as_posix().rstrip("/") + "/"
    if candidate.casefold().startswith(root.casefold()):
        candidate = candidate[len(root) :]
    candidate = candidate.lstrip("./")
    try:
        resolved = (ROOT / Path(candidate)).resolve()
        resolved.relative_to(ROOT.resolve())
    except (OSError, ValueError):
        return None
    return candidate


def identity_bindings(value: Any) -> dict[str, list[tuple[int, str]]]:
    bindings: dict[str, list[tuple[int, str]]] = {}

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            if isinstance(node.get("path"), str) and isinstance(node.get("bytes"), int) and isinstance(node.get("sha256"), str):
                path = normalize_bound_path(node["path"])
                digest = node["sha256"].lower()
                if path is not None and re.fullmatch(r"[0-9a-f]{64}", digest):
                    bindings.setdefault(path, []).append((node["bytes"], digest))
            for child in node.values():
                visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)

    visit(value)
    return bindings


def require_bound(receipt: Any, path: Path) -> dict[str, Any]:
    observed = identity(path)
    bound = identity_bindings(receipt).get(observed["path"], [])
    require(
        (observed["bytes"], observed["sha256"]) in bound,
        f"terminal receipt does not bind exact current identity: {observed['path']}",
    )
    return observed


def receipt_boundary(receipt: dict[str, Any]) -> str | None:
    return receipt.get("boundary_id") or receipt.get("boundary")


def verify_base() -> dict[str, Any]:
    require(BASE_SNAPSHOT.is_dir(), f"admitted B011 snapshot absent: {BASE_SNAPSHOT}")
    files = {
        relpath: require_exact(ROOT / Path(relpath), size, digest)
        for relpath, (size, digest) in REQUIRED_BASE_IDENTITIES.items()
    }
    snapshot = {
        relpath: require_exact(BASE_SNAPSHOT / Path(relpath), size, digest)
        for relpath, (size, digest) in REQUIRED_BASE_SNAPSHOT_IDENTITIES.items()
    }
    base_receipt = read_json(BASE_BUILD_RECEIPT)
    require(base_receipt.get("boundary_id") == "R011-B011", "B011 build receipt boundary changed")
    require(base_receipt.get("status") == "PASS_ISOLATED_DETERMINISTIC_BUILD", "B011 build receipt is not admitted-pass evidence")
    require(base_receipt.get("page_count") == 426, "B011 admitted base page count changed")
    return {"files": files, "snapshot_anchors": snapshot, "page_count": 426}


def load_manifest() -> dict[str, tuple[int, str]]:
    rows: dict[str, tuple[int, str]] = {}
    for line_number, line in enumerate(BASE_MANIFEST.read_text(encoding="utf-8").splitlines(), 1):
        parts = line.split("\t")
        require(len(parts) == 3, f"malformed B011 manifest line {line_number}")
        path, size_text, digest = parts
        require(path not in rows and re.fullmatch(r"[0-9a-f]{64}", digest) is not None, f"invalid B011 manifest line {line_number}")
        rows[path] = (int(size_text), digest)
    require(len(rows) == 1206, f"B011 source closure count changed: {len(rows)}")
    for path, expected in REQUIRED_BASE_SNAPSHOT_IDENTITIES.items():
        require(rows.get(path) == expected, f"B011 manifest anchor mismatch: {path}")
    return rows


def verify_manifest_snapshot(snapshot: Path, rows: dict[str, tuple[int, str]]) -> dict[str, Any]:
    total = 0
    digest_stream = hashlib.sha256()
    for path in sorted(rows):
        file = snapshot / Path(path)
        observed = identity_under(file, snapshot)
        expected = rows[path]
        require((observed["bytes"], observed["sha256"]) == expected, f"snapshot/manifest mismatch: {path}")
        total += observed["bytes"]
        digest_stream.update(f"{path}\t{observed['bytes']}\t{observed['sha256']}\n".encode("utf-8"))
    observed_paths = sorted(path.relative_to(snapshot).as_posix() for path in snapshot.rglob("*") if path.is_file())
    require(observed_paths == sorted(rows), "snapshot file inventory differs from manifest")
    return {"files": len(rows), "bytes": total, "inventory_sha256": digest_stream.hexdigest()}


def identity_under(path: Path, root: Path) -> dict[str, Any]:
    if not path.is_file():
        raise GateError(f"snapshot file absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(root).as_posix(), "bytes": len(raw), "sha256": sha256(raw)}


def verify_terminal() -> dict[str, Any]:
    if not FINAL_TRANSLATION_QA.is_file():
        raise GateError(f"terminal translation QA absent: {rel(FINAL_TRANSLATION_QA)}")
    final_receipt = read_json(FINAL_TRANSLATION_QA)
    require(isinstance(final_receipt, dict), "terminal translation QA is not a JSON object")
    require(receipt_boundary(final_receipt) == BOUNDARY_ID, "terminal translation QA boundary mismatch")
    require(final_receipt.get("status") == "PASS_FINAL_CANDIDATE", "terminal translation QA is not PASS_FINAL_CANDIDATE")
    require(MODEL in json.dumps(final_receipt, ensure_ascii=False), "terminal translation QA lacks exact model provenance")

    final_identities = {rel(path): require_bound(final_receipt, path) for path in FINAL_DIRECT_BINDINGS}
    rejected_visual = require_exact(REJECTED_PRE_REFLOW_VISUAL_QA, *REJECTED_PRE_REFLOW_VISUAL_QA_IDENTITY)
    rejected_visual_value = read_json(REJECTED_PRE_REFLOW_VISUAL_QA)
    require(rejected_visual_value.get("boundary_id") == BOUNDARY_ID, "rejected pre-reflow visual QA boundary mismatch")
    require("REJECT" in str(rejected_visual_value.get("status", "")).upper(), "pre-reflow visual QA is not explicitly rejected evidence")

    pre_review = read_json(PRE_REVIEW)
    require(isinstance(pre_review, dict), "pre-review receipt is not a JSON object")
    require(receipt_boundary(pre_review) == BOUNDARY_ID, "pre-review boundary mismatch")
    require(str(pre_review.get("status", "")).startswith(("COMPLETE_", "PASS_")), "pre-review receipt is not terminal/complete")
    for path in PRE_REVIEW_CANDIDATE_PATHS:
        require_bound(pre_review, path)

    terminology = read_json(TERMINOLOGY_QA)
    require(isinstance(terminology, dict), "terminology QA is not a JSON object")
    require(receipt_boundary(terminology) == BOUNDARY_ID, "terminology QA boundary mismatch")
    require(str(terminology.get("status", "")).startswith("PASS"), "terminology QA is not a PASS receipt")
    require_bound(terminology, CONTROLLED_TERMS_TSV)
    require(TERMS_TSV.read_bytes() == CONTROLLED_TERMS_TSV.read_bytes(), "controlled-terms alias is not byte-identical")
    require(MODEL in json.dumps(terminology, ensure_ascii=False), "terminology QA lacks exact model provenance")

    assets = read_json(ASSET_CLOSURE)
    require(isinstance(assets, dict), "asset closure is not a JSON object")
    require(receipt_boundary(assets) == BOUNDARY_ID, "asset-closure boundary mismatch")
    require(assets.get("status") == "PASS_BOUNDED_FOUR_FIGURE_CLOSURE_TWO_LOCALIZED_DERIVATIVES", "asset closure is not terminal-pass")
    require_bound(assets, BOOK_PDF_OVERLAY)
    require_bound(assets, STOCK_PDF_OVERLAY)
    require_bound(assets, LOCALIZED_FIGURE_RECEIPT)
    localized_receipt = read_json(LOCALIZED_FIGURE_RECEIPT)
    require(isinstance(localized_receipt, dict), "localized-figure receipt is not a JSON object")
    require(receipt_boundary(localized_receipt) == BOUNDARY_ID, "localized-figure receipt boundary mismatch")
    require(MODEL in json.dumps(assets, ensure_ascii=False), "asset closure lacks exact model provenance")

    return {
        "terminal_translation_qa": identity(FINAL_TRANSLATION_QA),
        "terminal_direct_bindings": final_identities,
        "pre_review": identity(PRE_REVIEW),
        "terminology_qa": identity(TERMINOLOGY_QA),
        "terms": identity(TERMS_TSV),
        "controlled_terms": identity(CONTROLLED_TERMS_TSV),
        "asset_closure": identity(ASSET_CLOSURE),
        "localized_figure_receipt": identity(LOCALIZED_FIGURE_RECEIPT),
        "localized_pdfs": [identity(BOOK_PDF_OVERLAY), identity(STOCK_PDF_OVERLAY)],
        "rejected_pre_reflow_visual_qa": rejected_visual,
    }


def splice_main(base: str, fragment: str) -> str:
    start = base.find(MAIN_START)
    input_at = base.find(INPUT_TOKEN, start)
    require(start >= 0 and input_at >= 0, "B012 main splice anchors absent")
    end = input_at + len(INPUT_TOKEN)
    require(fragment.count(INPUT_TOKEN) == 1, "B012 main fragment lost unique EoCE input")
    return base[:start] + fragment.rstrip() + base[end:]


def answer_bounds(value: str) -> tuple[int, int]:
    context = value.find(ANSWER_CONTEXT)
    require(context >= 0 and value.find(ANSWER_CONTEXT, context + 1) < 0, "Chapter 3 answer context absent/non-unique")
    start = value.find(ANSWER_START, context)
    end = value.find(ANSWER_END, start)
    require(start >= 0 and end >= 0, "B012 public-answer anchors absent")
    return start, end


def splice_answers(base: str, fragment: str) -> str:
    start, end = answer_bounds(base)
    return base[:start] + answer_body(fragment).rstrip() + "\n\n" + base[end:]


def answer_body(fragment: str) -> str:
    marker = re.search(r"(?m)^% 29\s*$", fragment)
    require(marker is not None, "B012 public-answer fragment lacks its exact % 29 body anchor")
    return fragment[marker.start() :]


def without_comments(value: str) -> str:
    return re.sub(r"(?m)(?<!\\)%.*$", "", value)


def macro_sequence(value: str) -> list[str]:
    return re.findall(r"\\([A-Za-z@]+|.)", value)


def environment_sequence(value: str) -> list[tuple[str, str]]:
    return re.findall(r"\\(begin|end)\{([^}]+)\}", value)


def numeric_sequence(value: str) -> list[str]:
    return re.findall(r"(?<![A-Za-z])\d+(?:\.\d+)?", value)


def source_main_slice(value: str) -> str:
    start = value.find(MAIN_START)
    input_at = value.find(INPUT_TOKEN, start)
    require(start >= 0 and input_at >= 0, "authority Section 3.4 anchors absent")
    return value[start : input_at + len(INPUT_TOKEN)]


def target_main_slice(value: str) -> str:
    start = value.find(TARGET_MAIN_START)
    input_at = value.find(INPUT_TOKEN, start)
    require(start >= 0 and input_at >= 0, "target Section 3.4 anchors absent")
    return value[start : input_at + len(INPUT_TOKEN)]


def topology(source: str, target: str, role: str) -> dict[str, Any]:
    topology_target = target
    authorized_layout_delta: dict[str, Any] | None = None
    if role == "Section 3.4":
        require(target.count(LAYOUT_COMMENT) == 1, "authorized main layout comment absent/non-unique")
        require(target.count("\n" + r"\end{onebox}" + "\n\n" + LAYOUT_COMMENT + "\n") == 1, "authorized main layout comment is not immediately after the expected-value onebox")
        topology_target = target.replace(LAYOUT_COMMENT, LAYOUT_BREAK, 1)
        reconstructed_sha = sha256(topology_target.encode("utf-8"))
        require(reconstructed_sha == PRE_REFLOW_MAIN_FRAGMENT_SHA256, "main layout reversal does not reconstruct the exact pre-reflow fragment")
        authorized_layout_delta = {
            "removed_exact": LAYOUT_BREAK,
            "replacement_exact": LAYOUT_COMMENT,
            "occurrences": 1,
            "pre_reflow_reconstruction_sha256": reconstructed_sha,
            "reader_visible_change": False,
        }
    elif role == "EoCE 29-36":
        require(target.count(EOCE_LAYOUT_INSERTION) == 1, "authorized EoCE page break before exercise 33 absent/non-unique")
        topology_target = target.replace(EOCE_LAYOUT_INSERTION, EOCE_LAYOUT_PREIMAGE, 1)
        reconstructed_sha = sha256(topology_target.encode("utf-8"))
        require(reconstructed_sha == PRE_REFLOW_EOCE_SHA256, "EoCE layout reversal does not reconstruct the exact pre-reflow input")
        authorized_layout_delta = {
            "inserted_exact": LAYOUT_BREAK,
            "location": "immediately before % 33 / exercise 33",
            "occurrences": 1,
            "pre_reflow_reconstruction_sha256": reconstructed_sha,
            "reader_visible_change": False,
        }
    source_semantic = without_comments(source)
    target_semantic = without_comments(topology_target)
    macro_target = target_semantic
    authorized_macro_delta: dict[str, Any] | None = None
    if role == "Section 3.4":
        replacements = {
            r"\resp{tanpa\us{}buku}": r"\resp{noBook}",
            r"\resp{buku\us{}teks}": r"\resp{textbook}",
            r"\resp{keduanya}": r"\resp{both}",
        }
        for localized, authority_value in replacements.items():
            require(target_semantic.count(localized) == 1, f"authorized localized response cell absent/non-unique: {localized}")
            require(target_semantic.count(authority_value) == 0, f"legacy English response cell remains: {authority_value}")
            macro_target = macro_target.replace(localized, authority_value, 1)
        authorized_macro_delta = {
            "scope": "three reader-visible chemistry-table response cells",
            "source": [r"\resp{noBook}", r"\resp{textbook}", r"\resp{both}"],
            "target": [r"\resp{tanpa\us{}buku}", r"\resp{buku\us{}teks}", r"\resp{keduanya}"],
            "added_us_tokens": 2,
            "macro_sequence_exact_after_normalization": macro_sequence(source_semantic) == macro_sequence(macro_target),
        }
    checks: dict[str, Any] = {
        "macro_sequence_exact_or_authorized_response_delta": macro_sequence(source_semantic) == macro_sequence(macro_target),
        "environment_sequence_exact": environment_sequence(source_semantic) == environment_sequence(target_semantic),
        "numeric_sequence_exact": numeric_sequence(source_semantic) == numeric_sequence(target_semantic),
        "labels_exact": re.findall(r"\\label\{([^}]+)\}", source_semantic) == re.findall(r"\\label\{([^}]+)\}", target_semantic),
        "refs_exact": re.findall(r"\\ref\{([^}]+)\}", source_semantic) == re.findall(r"\\ref\{([^}]+)\}", target_semantic),
        "pagerefs_exact": re.findall(r"\\pageref\{([^}]+)\}", source_semantic) == re.findall(r"\\pageref\{([^}]+)\}", target_semantic),
        "inputs_exact": re.findall(r"\\input\{([^}]+)\}", source_semantic) == re.findall(r"\\input\{([^}]+)\}", target_semantic),
        "figure_paths_exact": re.findall(r"\\(?:Figure|FigureFullPath)(?:\[[^\]]*\])?\{[^}]+\}\{([^}]+)\}", source_semantic, flags=re.DOTALL)
        == re.findall(r"\\(?:Figure|FigureFullPath)(?:\[[^\]]*\])?\{[^}]+\}\{([^}]+)\}", target_semantic, flags=re.DOTALL),
        "math_dollars_exact": source_semantic.count("$") == target_semantic.count("$"),
        "source_brace_delta": source_semantic.count("{") - source_semantic.count("}"),
        "target_brace_delta": target_semantic.count("{") - target_semantic.count("}"),
    }
    if authorized_macro_delta is not None:
        checks["authorized_macro_delta"] = authorized_macro_delta
    if authorized_layout_delta is not None:
        checks["authorized_layout_delta"] = authorized_layout_delta
    booleans = [value for key, value in checks.items() if not key.endswith("brace_delta") and not isinstance(value, dict)]
    require(all(value is True for value in booleans), f"{role} topology mismatch: {checks}")
    require(checks["source_brace_delta"] == checks["target_brace_delta"], f"{role} brace delta changed")
    return checks


def verify_sources() -> dict[str, Any]:
    base_main_path = BASE_SNAPSHOT / "ch_probability" / "TeX" / "ch_probability.tex"
    base_answers_path = BASE_SNAPSHOT / "extraTeX" / "eoceSolutions" / "eoceSolutions.tex"
    base_preface_path = BASE_SNAPSHOT / "extraTeX" / "preamble" / "preface.tex"
    authority = ROOT / "authority" / "upstream" / f"openintro-statistics-{AUTHORITY_COMMIT}"

    base_main = base_main_path.read_text(encoding="utf-8")
    base_answers = base_answers_path.read_text(encoding="utf-8")
    base_preface = base_preface_path.read_text(encoding="utf-8")
    fragment = MAIN_FRAGMENT.read_text(encoding="utf-8")
    eoce = EOCE_FRAGMENT.read_text(encoding="utf-8")
    answers = ANSWER_FRAGMENT.read_text(encoding="utf-8")

    require(FULL_MAIN.read_text(encoding="utf-8") == splice_main(base_main, fragment), "assembled B012 main source is stale or misassembled")
    require(FULL_ANSWERS.read_text(encoding="utf-8") == splice_answers(base_answers, answers), "assembled B012 public answers are stale or misassembled")
    require(base_preface.count("Distribusi peubah acak") == 1, "B011 preface terminology anchor changed")
    expected_preface = base_preface.replace("Distribusi peubah acak", "Distribusi variabel acak", 1)
    require(PREFACE_OVERLAY.read_text(encoding="utf-8") == expected_preface, "preface overlay is not the exact bounded terminology replacement")

    base_book_r = (BASE_SNAPSHOT / "ch_probability" / "figures" / "bookCostDist" / "bookCostDist.R").read_text(encoding="utf-8")
    expected_book_r = base_book_r.replace("xlab = 'Cost'", "xlab = 'Biaya'", 1).replace("mtext('Probability'", "mtext('Peluang'", 1)
    require(BOOK_R_OVERLAY.read_text(encoding="utf-8") == expected_book_r, "bookCostDist R overlay changed beyond two exact label replacements")
    base_stock_r = (
        BASE_SNAPSHOT
        / "ch_probability"
        / "figures"
        / "changeInLeonardsStockPortfolioFor36Months"
        / "changeinleonardsstockportfoliofor36months.R"
    ).read_text(encoding="utf-8")
    expected_stock_r = base_stock_r.replace(
        'xlab = "Monthly Returns Over 3 Years"',
        'xlab = "Imbal Hasil Bulanan Selama 3 Tahun"',
        1,
    )
    require(STOCK_R_OVERLAY.read_text(encoding="utf-8") == expected_stock_r, "stock-return R overlay changed beyond its exact label replacement")

    require(fragment.count(LAYOUT_COMMENT) == 1, "main fragment does not contain exactly one authorized layout comment")
    reconstructed_main = fragment.replace(LAYOUT_COMMENT, LAYOUT_BREAK, 1)
    require(sha256(reconstructed_main.encode("utf-8")) == PRE_REFLOW_MAIN_FRAGMENT_SHA256, "main fragment layout preimage identity mismatch")
    full_main_text = FULL_MAIN.read_text(encoding="utf-8")
    require(full_main_text.count(LAYOUT_COMMENT) == 1, "assembled main does not contain exactly one authorized layout comment")
    reconstructed_full_main = full_main_text.replace(LAYOUT_COMMENT, LAYOUT_BREAK, 1)
    require(sha256(reconstructed_full_main.encode("utf-8")) == PRE_REFLOW_FULL_MAIN_SHA256, "assembled main layout preimage identity mismatch")
    require(eoce.count(EOCE_LAYOUT_INSERTION) == 1, "EoCE does not contain exactly one authorized page break before exercise 33")
    reconstructed_eoce = eoce.replace(EOCE_LAYOUT_INSERTION, EOCE_LAYOUT_PREIMAGE, 1)
    require(sha256(reconstructed_eoce.encode("utf-8")) == PRE_REFLOW_EOCE_SHA256, "EoCE layout preimage identity mismatch")

    source_main = source_main_slice((authority / "ch_probability" / "TeX" / "ch_probability.tex").read_text(encoding="utf-8"))
    source_eoce = (authority / "ch_probability" / "TeX" / "random_variables.tex").read_text(encoding="utf-8")
    source_answer_file = (authority / "extraTeX" / "eoceSolutions" / "eoceSolutions.tex").read_text(encoding="utf-8")
    source_answer_start, source_answer_end = answer_bounds(source_answer_file)
    source_answers = source_answer_file[source_answer_start:source_answer_end]

    main_topology = topology(source_main, fragment, "Section 3.4")
    eoce_topology = topology(source_eoce, eoce, "EoCE 29-36")
    answer_topology = topology(source_answers.rstrip(), answer_body(answers).rstrip(), "public answers 29/31/33/35")

    main_counts = {
        "sections": fragment.count(r"\section{"),
        "subsections": fragment.count(r"\subsection{"),
        "worked_examples": fragment.count(r"\begin{nexample}"),
        "guided_exercises": fragment.count(r"\begin{nexercise}"),
        "guided_inline_answers": fragment.count(r"\footnotetext"),
        "figure_environments": fragment.count(r"\begin{figure}"),
        "inline_tables": fragment.count(r"\begin{tabular}"),
        "inputs": fragment.count(r"\input{"),
    }
    require(
        main_counts
        == {
            "sections": 1,
            "subsections": 4,
            "worked_examples": 8,
            "guided_exercises": 9,
            "guided_inline_answers": 9,
            "figure_environments": 6,
            "inline_tables": 5,
            "inputs": 1,
        },
        f"Section 3.4 structural counts changed: {main_counts}",
    )
    eoce_labels = re.findall(r"\\label\{([^}]+)\}", eoce)
    expected_eoce_labels = [
        "college_smokers",
        "ace_of_clubs",
        "hearts",
        "worth_it",
        "portfolio_return",
        "baggage_fees",
        "roulette_american",
        "roulette_european",
    ]
    require(eoce_labels == expected_eoce_labels, f"EoCE 29-36 label identity/order changed: {eoce_labels}")
    require(eoce.count(r"\eoce{") == 8 and eoce.count("\n}{}") == 8, "EoCE 29-36 closure/empty-answer arguments changed")
    answer_ids = [int(value) for value in re.findall(r"^% (\d+)$", answers, flags=re.MULTILINE)]
    require(answer_ids == [29, 31, 33, 35] and answers.count(r"\eocesol{") == 4, f"public-answer closure changed: {answer_ids}")

    return {
        "assembled_main_exact": True,
        "assembled_answers_exact": True,
        "preface_exact_single_replacement": True,
        "localized_R_overlays_exact": True,
        "authorized_layout_only_reflow": {
            "main_removed_break_reconstruction_sha256": PRE_REFLOW_MAIN_FRAGMENT_SHA256,
            "assembled_main_removed_break_reconstruction_sha256": PRE_REFLOW_FULL_MAIN_SHA256,
            "eoce_added_break_reconstruction_sha256": PRE_REFLOW_EOCE_SHA256,
            "rejected_pre_reflow_visual_qa": identity(REJECTED_PRE_REFLOW_VISUAL_QA),
            "semantic_change": False,
        },
        "main": {"counts": main_counts, "topology": main_topology},
        "eoce": {"exercise_count": 8, "labels": eoce_labels, "topology": eoce_topology},
        "answers": {"public_answers": answer_ids, "o001_gaps": [30, 32, 34, 36], "topology": answer_topology},
    }


def safe_remove(path: Path) -> None:
    resolved = path.resolve()
    resolved.relative_to(BUILD_ROOT.resolve())
    require(resolved != BUILD_ROOT.resolve(), "refusing to remove the entire B012 build root")
    if resolved.is_dir():
        shutil.rmtree(resolved)
    elif resolved.exists():
        resolved.unlink()


def prepare_snapshot(rows: dict[str, tuple[int, str]], terminal: dict[str, Any], base: dict[str, Any], *, replace: bool) -> tuple[dict[str, tuple[int, str]], dict[str, Any]]:
    if SNAPSHOT.exists():
        if not replace:
            raise GateError(f"refusing to overwrite existing B012 snapshot: {rel(SNAPSHOT)}")
        safe_remove(SNAPSHOT)
    shutil.copytree(BASE_SNAPSHOT, SNAPSHOT)
    for relative, source in OVERLAYS.items():
        require(relative in rows, f"B012 overlay path outside admitted B011 closure: {relative}")
        destination = SNAPSHOT / Path(relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        observed = identity_under(destination, SNAPSHOT)
        rows[relative] = (observed["bytes"], observed["sha256"])
    rows = dict(sorted(rows.items()))
    SOURCE_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    SOURCE_MANIFEST.write_text(
        "".join(f"{path}\t{size}\t{digest}\n" for path, (size, digest) in rows.items()),
        encoding="utf-8",
        newline="\n",
    )
    snapshot_inventory = verify_manifest_snapshot(SNAPSHOT, rows)
    checks = verify_sources()
    overlay_identities = {
        relative: {"source": rel(source), "target": f"{rel(SNAPSHOT)}/{relative}", **identity_under(SNAPSHOT / Path(relative), SNAPSHOT)}
        for relative, source in OVERLAYS.items()
    }
    source_qa = {
        "$schema": "interlanguage.r011-b012-source-qa/v1",
        "boundary_id": BOUNDARY_ID,
        "status": "PASS_ISOLATED_OVERLAY_CLOSURE",
        "authority": {
            "repository": "https://github.com/OpenIntroStat/openintro-statistics",
            "branch": "master",
            "commit": AUTHORITY_COMMIT,
            "tree": AUTHORITY_TREE,
        },
        "base_boundary": "R011-B011",
        "base_evidence": base,
        "base_manifest": identity(BASE_MANIFEST),
        "manifest": {**identity(SOURCE_MANIFEST), "files": len(rows)},
        "snapshot": {"path": rel(SNAPSHOT), **snapshot_inventory},
        "terminal_inputs": terminal,
        "overlays": overlay_identities,
        "checks": checks,
        "expected_visual_audit": {
            "base_section_start_page": 118,
            "base_next_section_start_page": 128,
            "preface_term_page": 5,
            "base_public_answer_page": 391,
            "provisional_review_pages": [5, *range(117, 131), 390, 391, 392],
            "approval": "NOT_PERFORMED_BY_BUILD_HARNESS",
        },
        "translation_scope": "Section 3.4 / Variabel acak, EoCE 29-36, public answers 29/31/33/35, one preface terminology correction, and two localized figure derivatives.",
        "o001_gaps": [30, 32, 34, 36],
        "translation_provenance": MODEL,
        "untranslated_suffix": "Content from Section 3.5 / contDist onward remains the inherited English witness.",
        "rights_note": "Text/translation retain CC BY-SA 3.0. Component-specific upstream rights remain controlling; the two localized PDFs are exact label-only derivatives bound by the asset-closure receipt.",
        "canonical_mutation": False,
        "git_used": False,
        "publication_performed": False,
        "upstream_contact": False,
    }
    SOURCE_QA.write_bytes(canonical_json(source_qa))
    return rows, source_qa


def tools() -> dict[str, str]:
    names = ["pdflatex", "bibtex", "makeindex", "pdfinfo", "pdftotext", "pdftoppm", "mutool"]
    result: dict[str, str] = {}
    missing: list[str] = []
    for name in names:
        found = shutil.which(name)
        if found:
            result[name] = str(Path(found).resolve())
        else:
            missing.append(name)
    require(not missing, "required build tools missing: " + ", ".join(missing))
    return result


def run_logged(command: list[str], cwd: Path, output: Path, env: dict[str, str] | None = None) -> None:
    completed = subprocess.run(command, cwd=cwd, env=env, capture_output=True)
    output.write_bytes(completed.stdout + completed.stderr)
    require(completed.returncode == 0, f"command failed ({completed.returncode}): {command[0]}; see {rel(output)}")


def build_once(label: str, directory: Path, toolchain: dict[str, str], trailer_seed: str, *, replace: bool) -> dict[str, Any]:
    if directory.exists() and any(directory.iterdir()):
        if not replace:
            raise GateError(f"refusing to overwrite non-empty build replay: {rel(directory)}")
        safe_remove(directory)
    directory.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.update({"SOURCE_DATE_EPOCH": "1787050800", "FORCE_SOURCE_DATE": "1", "TZ": "UTC", "MIKTEX_ENABLE_INSTALLER": "0"})
    env["BIBINPUTS"] = str(SNAPSHOT) + os.pathsep + env.get("BIBINPUTS", "")
    pdf_command = [
        toolchain["pdflatex"],
        "-interaction=nonstopmode",
        "-halt-on-error",
        "-file-line-error",
        "-recorder",
        "-no-shell-escape",
        "-synctex=0",
        "-jobname=main",
        f"-output-directory={directory}",
        rf"\pdftrailerid{{<{trailer_seed}><{trailer_seed}>}}\input{{main.tex}}",
    ]
    run_logged(pdf_command, SNAPSHOT, directory / "console-pass1.txt", env)
    run_logged([toolchain["bibtex"], "main"], directory, directory / "console-bibtex.txt", env)
    run_logged([toolchain["makeindex"], "main.idx"], directory, directory / "console-makeindex1.txt", env)
    run_logged(pdf_command, SNAPSHOT, directory / "console-pass2.txt", env)
    run_logged([toolchain["makeindex"], "main.idx"], directory, directory / "console-makeindex2.txt", env)
    run_logged(pdf_command, SNAPSHOT, directory / "console-pass3.txt", env)
    pdf = directory / "main.pdf"
    require(pdf.is_file(), f"{label} pass 3 produced no PDF")
    pass3 = directory / "main-pass3.pdf"
    shutil.copy2(pdf, pass3)
    pass3_identity = identity(pass3)
    run_logged([toolchain["makeindex"], "main.idx"], directory, directory / "console-makeindex3.txt", env)
    run_logged(pdf_command, SNAPSHOT, directory / "console-pass4.txt", env)
    pass4_identity = identity(pdf)
    require(
        (pass3_identity["bytes"], pass3_identity["sha256"]) == (pass4_identity["bytes"], pass4_identity["sha256"]),
        f"{label} pass 3 and pass 4 PDFs differ",
    )
    for filename, command in (
        ("console-pdfinfo.txt", [toolchain["pdfinfo"], str(pdf)]),
        ("console-mutool-info.txt", [toolchain["mutool"], "info", str(pdf)]),
        ("console-mutool-trailer.txt", [toolchain["mutool"], "show", str(pdf), "trailer"]),
    ):
        run_logged(command, directory, directory / filename)
    text = directory / "main-final.txt"
    run_logged([toolchain["pdftotext"], "-layout", str(pdf), str(text)], directory, directory / "console-pdftotext.txt")
    pdfinfo = (directory / "console-pdfinfo.txt").read_text(encoding="utf-8", errors="replace")
    page_match = re.search(r"^Pages:\s+(\d+)", pdfinfo, flags=re.MULTILINE)
    pages = int(page_match.group(1)) if page_match else 0
    require(425 <= pages <= 430, f"{label} page count outside bounded expectation: {pages}")
    pass4_log = (directory / "console-pass4.txt").read_text(encoding="utf-8", errors="replace")
    fatal_warning_patterns = {
        "undefined_references": r"There were undefined references|Reference .* undefined",
        "undefined_citations": r"There were undefined citations|Citation .* undefined",
        "multiply_defined_labels": r"multiply defined",
        "rerun_required": r"Rerun to get cross-references right|Label\(s\) may have changed",
    }
    fatal_warning_counts = {name: len(re.findall(pattern, pass4_log, flags=re.IGNORECASE)) for name, pattern in fatal_warning_patterns.items()}
    require(not any(fatal_warning_counts.values()), f"{label} terminal LaTeX warnings require another pass: {fatal_warning_counts}")
    warnings = {
        "fatal_terminal_counts": fatal_warning_counts,
        "overfull_hbox_count": len(re.findall(r"Overfull \\hbox", pass4_log)),
        "underfull_hbox_count": len(re.findall(r"Underfull \\hbox", pass4_log)),
        "font_warning_count": len(re.findall(r"font warning", pass4_log, flags=re.IGNORECASE)),
    }
    trailer_text = (directory / "console-mutool-trailer.txt").read_text(encoding="utf-8", errors="replace")
    trailer_match = re.search(r"/ID\s*\[\s*<([0-9A-Fa-f]{32})>\s*<([0-9A-Fa-f]{32})>\s*\]", trailer_text)
    require(trailer_match is not None, f"{label} PDF trailer ID is absent or malformed")
    trailer_ids = [trailer_match.group(1).lower(), trailer_match.group(2).lower()]
    require(trailer_ids[0] == trailer_ids[1], f"{label} PDF trailer ID pair differs")
    return {
        "label": label,
        "directory": rel(directory),
        "pdf": identity(pdf),
        "pass3": pass3_identity,
        "pass4": pass4_identity,
        "text": identity(text),
        "page_count": pages,
        "terminal_log": identity(directory / "console-pass4.txt"),
        "warnings": warnings,
        "trailer_seed": trailer_seed.lower(),
        "trailer_ids": trailer_ids,
    }


def page_texts(path: Path) -> list[str]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    return raw.split("\f")


def first_page(pages: list[str], phrases: Iterable[str], minimum: int = 1, maximum: int | None = None) -> int | None:
    folded = [phrase.casefold() for phrase in phrases]
    last = min(len(pages), maximum or len(pages))
    for page_number in range(max(1, minimum), last + 1):
        value = pages[page_number - 1].casefold()
        if any(phrase in value for phrase in folded):
            return page_number
    return None


def first_page_regex(pages: list[str], pattern: str, minimum: int = 1, maximum: int | None = None) -> int | None:
    compiled = re.compile(pattern, flags=re.IGNORECASE | re.MULTILINE)
    last = min(len(pages), maximum or len(pages))
    for page_number in range(max(1, minimum), last + 1):
        if compiled.search(pages[page_number - 1]):
            return page_number
    return None


def locate_pages(text_path: Path) -> dict[str, Any]:
    pages = page_texts(text_path)
    preface = first_page(pages, ["Distribusi variabel acak"], 1, 25)
    section = first_page_regex(pages, r"^\s*3\.4\s+Variabel acak\s*$", 100, 150)
    transition = first_page_regex(
        pages,
        r"^\s*3\.5\s+(?:Continuous distributions|Distribusi kontinu)\s*$",
        section or 100,
        160,
    )
    answers = first_page(pages, ["27 mahasiswa", "E(X) = 3.59", "0.0526"], 350, 420)
    require(preface is not None, "localized preface terminology not found in reader text")
    require(section is not None, "localized Section 3.4 heading not found in reader text")
    require(transition is not None and transition > section, "Section 3.4-to-3.5 transition not found")
    require(answers is not None, "localized public answers 29/31/33/35 not found in reader text")
    require(116 <= section <= 121, f"Section 3.4 start page drifted unexpectedly: {section}")
    require(126 <= transition <= 134, f"Section 3.5 transition page drifted unexpectedly: {transition}")
    return {
        "preface_term_page": preface,
        "section_start_page": section,
        "next_section_start_page": transition,
        "public_answer_page": answers,
        "affected_main_window": [max(1, section - 1), transition + 1],
        "transition": f"Section 3.4 / Variabel acak -> Section 3.5 / {('Distribusi kontinu' if first_page(pages, ['Distribusi kontinu'], transition, transition) else 'Continuous distributions')}",
    }


def reader_checks(text_path: Path) -> dict[str, Any]:
    value = text_path.read_text(encoding="utf-8", errors="replace")
    expected = [
        "Variabel acak",
        "nilai harapan",
        "varians",
        "simpangan baku",
        "Distribusi variabel acak",
        "Biaya",
        "Imbal Hasil Bulanan Selama 3 Tahun",
        "27 mahasiswa",
    ]
    absent = [term for term in expected if term.casefold() not in value.casefold()]
    require(not absent, f"reader text lacks expected B012 terms/labels: {absent}")
    return {"status": "PASS_TEXT_EXTRACTION_ONLY", "expected_terms": expected, "absent": []}


def render_review_pages(pdf: Path, mapping: dict[str, Any], toolchain: dict[str, str], *, replace: bool) -> list[dict[str, Any]]:
    if REVIEW_RENDER.exists() and any(REVIEW_RENDER.iterdir()):
        if not replace:
            raise GateError(f"refusing to overwrite review renders: {rel(REVIEW_RENDER)}")
        safe_remove(REVIEW_RENDER)
    REVIEW_RENDER.mkdir(parents=True, exist_ok=True)
    pages = {
        mapping["preface_term_page"],
        mapping["public_answer_page"] - 1,
        mapping["public_answer_page"],
        mapping["public_answer_page"] + 1,
        *range(mapping["affected_main_window"][0], mapping["affected_main_window"][1] + 1),
    }
    artifacts: list[dict[str, Any]] = []
    for page in sorted(value for value in pages if value > 0):
        prefix = REVIEW_RENDER / f"page-{page:04d}"
        completed = subprocess.run(
            [toolchain["pdftoppm"], "-f", str(page), "-l", str(page), "-png", "-r", "120", str(pdf), str(prefix)],
            capture_output=True,
        )
        require(completed.returncode == 0, f"bounded review render failed on page {page}")
        candidates = sorted(REVIEW_RENDER.glob(f"page-{page:04d}-*.png"))
        require(len(candidates) == 1, f"unexpected render inventory for page {page}: {len(candidates)}")
        artifacts.append({"page": page, **identity(candidates[0])})
    return artifacts


def readiness() -> dict[str, Any]:
    base = verify_base()
    rows = load_manifest()
    unresolved: list[str] = []
    terminal: dict[str, Any] | None = None
    if FINAL_TRANSLATION_QA.is_file():
        terminal = verify_terminal()
        source_checks = verify_sources()
    else:
        unresolved.append(rel(FINAL_TRANSLATION_QA))
        source_checks = None
    return {
        "$schema": "interlanguage.r011-b012-build-readiness/v1",
        "boundary_id": BOUNDARY_ID,
        "status": "READY_FOR_TWO_REPLAY_BUILD" if not unresolved else "WAITING_FOR_TERMINAL_TRANSLATION_QA",
        "ready": not unresolved,
        "unresolved_inputs": unresolved,
        "base": base,
        "base_manifest_rows": len(rows),
        "terminal": terminal,
        "source_checks": source_checks,
        "write_boundaries": [rel(SNAPSHOT), rel(SOURCE_MANIFEST), rel(SOURCE_QA), rel(RUN_A), rel(RUN_B), rel(FINAL), rel(REVIEW_RENDER)],
        "canonical_mutation": False,
        "visual_approval": "OUT_OF_SCOPE_REQUIRES_SEPARATE_AUDIT",
    }


def self_test() -> dict[str, Any]:
    state = readiness()
    sample = identity(BASE_MANIFEST)
    tampered = dict(sample)
    tampered["sha256"] = "0" * 64
    tamper_rejected = (sample["bytes"], sample["sha256"]) != (tampered["bytes"], tampered["sha256"])
    try:
        (ROOT / "repo").resolve().relative_to(BUILD_ROOT.resolve())
        path_guard = False
    except ValueError:
        path_guard = True
    require(tamper_rejected and path_guard, "inert fail-closed self-test failed")
    state.update(
        {
            "$schema": "interlanguage.r011-b012-build-harness-self-test/v1",
            "status": "PASS_INERT_FAIL_CLOSED_READY" if state["ready"] else "PASS_INERT_FAIL_CLOSED_WAITING",
            "checks": {
                "base_exact": True,
                "manifest_shape_exact": True,
                "tampered_identity_rejected_in_memory": tamper_rejected,
                "write_path_guard_rejects_repo": path_guard,
                "no_build_executed": True,
                "no_files_written": True,
            },
        }
    )
    return state


def summarize_existing_replay(label: str, directory: Path, trailer_seed: str) -> dict[str, Any]:
    pdf = directory / "main.pdf"
    pass3 = directory / "main-pass3.pdf"
    text_path = directory / "main-final.txt"
    pass4_log_path = directory / "console-pass4.txt"
    pdfinfo_path = directory / "console-pdfinfo.txt"
    trailer_path = directory / "console-mutool-trailer.txt"
    for path in (pdf, pass3, text_path, pass4_log_path, pdfinfo_path, trailer_path):
        require(path.is_file(), f"completed {label} artifact absent: {rel(path)}")
    pdf_id = identity(pdf)
    pass3_id = identity(pass3)
    require(
        (pdf_id["bytes"], pdf_id["sha256"]) == (pass3_id["bytes"], pass3_id["sha256"]),
        f"existing {label} pass 3 and pass 4 PDFs differ",
    )
    pdfinfo = pdfinfo_path.read_text(encoding="utf-8", errors="replace")
    page_match = re.search(r"^Pages:\s+(\d+)", pdfinfo, flags=re.MULTILINE)
    pages = int(page_match.group(1)) if page_match else 0
    require(425 <= pages <= 430, f"existing {label} page count outside bounded expectation: {pages}")
    pass4_log = pass4_log_path.read_text(encoding="utf-8", errors="replace")
    fatal_warning_patterns = {
        "undefined_references": r"There were undefined references|Reference .* undefined",
        "undefined_citations": r"There were undefined citations|Citation .* undefined",
        "multiply_defined_labels": r"multiply defined",
        "rerun_required": r"Rerun to get cross-references right|Label\(s\) may have changed",
    }
    fatal_counts = {
        name: len(re.findall(pattern, pass4_log, flags=re.IGNORECASE))
        for name, pattern in fatal_warning_patterns.items()
    }
    require(not any(fatal_counts.values()), f"existing {label} terminal warnings fail: {fatal_counts}")
    trailer_text = trailer_path.read_text(encoding="utf-8", errors="replace")
    trailer_match = re.search(r"/ID\s*\[\s*<([0-9A-Fa-f]{32})>\s*<([0-9A-Fa-f]{32})>\s*\]", trailer_text)
    require(trailer_match is not None, f"existing {label} trailer ID is absent or malformed")
    trailer_ids = [trailer_match.group(1).lower(), trailer_match.group(2).lower()]
    require(trailer_ids[0] == trailer_ids[1], f"existing {label} trailer ID pair differs")
    return {
        "label": label,
        "directory": rel(directory),
        "pdf": pdf_id,
        "pass3": pass3_id,
        "pass4": pdf_id,
        "text": identity(text_path),
        "page_count": pages,
        "terminal_log": identity(pass4_log_path),
        "warnings": {
            "fatal_terminal_counts": fatal_counts,
            "overfull_hbox_count": len(re.findall(r"Overfull \\hbox", pass4_log)),
            "underfull_hbox_count": len(re.findall(r"Underfull \\hbox", pass4_log)),
            "font_warning_count": len(re.findall(r"font warning", pass4_log, flags=re.IGNORECASE)),
        },
        "trailer_seed": trailer_seed.lower(),
        "trailer_ids": trailer_ids,
    }


def collect_existing_renders(mapping: dict[str, Any]) -> list[dict[str, Any]]:
    expected_pages = {
        mapping["preface_term_page"],
        mapping["public_answer_page"] - 1,
        mapping["public_answer_page"],
        mapping["public_answer_page"] + 1,
        *range(mapping["affected_main_window"][0], mapping["affected_main_window"][1] + 1),
    }
    artifacts: list[dict[str, Any]] = []
    expected_paths: set[Path] = set()
    for page in sorted(value for value in expected_pages if value > 0):
        candidates = sorted(REVIEW_RENDER.glob(f"page-{page:04d}-*.png"))
        require(len(candidates) == 1, f"existing render inventory for page {page} is {len(candidates)}, expected 1")
        expected_paths.add(candidates[0].resolve())
        artifacts.append({"page": page, **identity(candidates[0])})
    observed_paths = {path.resolve() for path in REVIEW_RENDER.glob("*.png")}
    require(observed_paths == expected_paths, "existing review-render inventory contains missing or extra PNGs")
    return artifacts


def finalize_existing() -> dict[str, Any]:
    base = verify_base()
    terminal = verify_terminal()
    rows = load_manifest()
    for relative, source in OVERLAYS.items():
        observed = identity(source)
        rows[relative] = (observed["bytes"], observed["sha256"])
    rows = dict(sorted(rows.items()))
    expected_manifest = "".join(f"{path}\t{size}\t{digest}\n" for path, (size, digest) in rows.items())
    require(SOURCE_MANIFEST.is_file(), "B012 source manifest absent")
    require(SOURCE_MANIFEST.read_text(encoding="utf-8") == expected_manifest, "B012 source manifest does not match current terminal overlays")
    source_qa_value = read_json(SOURCE_QA)
    require(source_qa_value.get("boundary_id") == BOUNDARY_ID, "B012 source QA boundary mismatch")
    require(source_qa_value.get("status") == "PASS_ISOLATED_OVERLAY_CLOSURE", "B012 source QA is not a PASS receipt")
    require_bound(source_qa_value, FINAL_TRANSLATION_QA)
    snapshot_inventory = verify_manifest_snapshot(SNAPSHOT, rows)
    toolchain = tools()
    trailer_seed = hashlib.sha256(SOURCE_MANIFEST.read_bytes()).hexdigest()[:32].upper()
    run_a = summarize_existing_replay("replay-a", RUN_A, trailer_seed)
    run_b = summarize_existing_replay("replay-b", RUN_B, trailer_seed)
    require(
        (run_a["pdf"]["bytes"], run_a["pdf"]["sha256"]) == (run_b["pdf"]["bytes"], run_b["pdf"]["sha256"]),
        "existing complete replay PDFs differ",
    )
    require(run_a["text"]["sha256"] == run_b["text"]["sha256"], "existing complete replay text extractions differ")
    require(run_a["page_count"] == run_b["page_count"], "existing complete replay page counts differ")
    require(run_a["trailer_ids"] == run_b["trailer_ids"], "existing complete replay trailer IDs differ")
    final_id = identity(FINAL_PDF)
    final_text_id = identity(FINAL_TEXT)
    require(
        (final_id["bytes"], final_id["sha256"]) == (run_a["pdf"]["bytes"], run_a["pdf"]["sha256"]),
        "existing conventional final PDF differs from replay A",
    )
    require(final_text_id["sha256"] == run_a["text"]["sha256"], "existing conventional final text differs from replay A")
    mapping = locate_pages(FINAL_TEXT)
    text_checks = reader_checks(FINAL_TEXT)
    renders = collect_existing_renders(mapping)
    receipt = {
        "$schema": "interlanguage.r011-b012-candidate-build-qa/v1",
        "boundary_id": BOUNDARY_ID,
        "status": "PASS_ISOLATED_TWO_REPLAY_DETERMINISTIC_BUILD_VISUAL_AUDIT_PENDING",
        "authority": {"commit": AUTHORITY_COMMIT, "tree": AUTHORITY_TREE},
        "base_boundary": "R011-B011",
        "base_evidence": base,
        "terminal_inputs": terminal,
        "source_qa": identity(SOURCE_QA),
        "source_manifest": {**identity(SOURCE_MANIFEST), "files": len(rows)},
        "snapshot": {"path": rel(SNAPSHOT), **snapshot_inventory},
        "candidate_artifact": {**final_id, "promoted": False},
        "candidate_text": final_text_id,
        "determinism": {
            "complete_build_replay_a": run_a,
            "complete_build_replay_b": run_b,
            "replay_pdfs_byte_identical": True,
            "each_replay_pass3_pass4_byte_identical": True,
            "trailer_seed_source": "first 128 bits of SHA-256(R011-B012_SOURCE_MANIFEST.tsv)",
            "trailer_seed": trailer_seed.lower(),
            "trailer_ids_equal": True,
        },
        "page_count": run_a["page_count"],
        "affected_page_mapping": mapping,
        "reader_checks": text_checks,
        "visual": {
            "status": "RENDERED_ONLY_NOT_VISUALLY_APPROVED",
            "required_next_gate": "Inspect every listed PNG and record a separate zero-defect visual QA receipt before admission.",
            "pages": [item["page"] for item in renders],
            "artifacts": renders,
        },
        "toolchain": {name: tool_identity(name, Path(path)) for name, path in toolchain.items()},
        "translation_scope": "Section 3.4 / Variabel acak complete in source order: eight worked examples, nine guided exercises with inline public answers, EoCE 29-36, public answers 29/31/33/35, one preface terminology correction, and two localized figure derivatives.",
        "o001_gaps": [30, 32, 34, 36],
        "next_untranslated_anchor": "ch_probability/TeX/ch_probability.tex#contDist",
        "production_model": MODEL,
        "canonical_mutation": False,
        "git_used": False,
        "publication_performed": False,
        "upstream_contact": False,
        "receipt_reconstructed_from_completed_guarded_transaction": True,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    if BUILD_RECEIPT.exists():
        raise GateError(f"refusing to overwrite existing terminal build receipt: {rel(BUILD_RECEIPT)}")
    BUILD_RECEIPT.write_bytes(canonical_json(receipt))
    return receipt


def execute_build(*, replace: bool) -> dict[str, Any]:
    base = verify_base()
    terminal = verify_terminal()
    rows = load_manifest()
    rows, source_qa = prepare_snapshot(rows, terminal, base, replace=replace)
    toolchain = tools()
    trailer_seed = hashlib.sha256(SOURCE_MANIFEST.read_bytes()).hexdigest()[:32].upper()
    run_a = build_once("replay-a", RUN_A, toolchain, trailer_seed, replace=replace)
    run_b = build_once("replay-b", RUN_B, toolchain, trailer_seed, replace=replace)
    require(
        (run_a["pdf"]["bytes"], run_a["pdf"]["sha256"]) == (run_b["pdf"]["bytes"], run_b["pdf"]["sha256"]),
        "the two independent complete builds produced different PDFs",
    )
    require(run_a["page_count"] == run_b["page_count"], "the two builds produced different page counts")
    require(run_a["trailer_ids"] == run_b["trailer_ids"], "the two builds produced different fixed trailer IDs")

    if FINAL.exists() and any(FINAL.iterdir()):
        if not replace:
            raise GateError(f"refusing to overwrite conventional final QA candidate: {rel(FINAL)}")
        safe_remove(FINAL)
    FINAL.mkdir(parents=True, exist_ok=True)
    shutil.copy2(RUN_A / "main.pdf", FINAL_PDF)
    shutil.copy2(RUN_A / "main-final.txt", FINAL_TEXT)
    mapping = locate_pages(FINAL_TEXT)
    text_checks = reader_checks(FINAL_TEXT)
    renders = render_review_pages(FINAL_PDF, mapping, toolchain, replace=replace)
    final_identity = identity(FINAL_PDF)
    require((final_identity["bytes"], final_identity["sha256"]) == (run_a["pdf"]["bytes"], run_a["pdf"]["sha256"]), "conventional QA PDF copy changed bytes")

    receipt = {
        "$schema": "interlanguage.r011-b012-candidate-build-qa/v1",
        "boundary_id": BOUNDARY_ID,
        "status": "PASS_ISOLATED_TWO_REPLAY_DETERMINISTIC_BUILD_VISUAL_AUDIT_PENDING",
        "authority": {"commit": AUTHORITY_COMMIT, "tree": AUTHORITY_TREE},
        "base_boundary": "R011-B011",
        "base_evidence": base,
        "terminal_inputs": terminal,
        "source_qa": identity(SOURCE_QA),
        "source_manifest": {**identity(SOURCE_MANIFEST), "files": len(rows)},
        "snapshot": {"path": rel(SNAPSHOT), **verify_manifest_snapshot(SNAPSHOT, rows)},
        "candidate_artifact": {**final_identity, "promoted": False},
        "candidate_text": identity(FINAL_TEXT),
        "determinism": {
            "complete_build_replay_a": run_a,
            "complete_build_replay_b": run_b,
            "replay_pdfs_byte_identical": True,
            "each_replay_pass3_pass4_byte_identical": True,
            "trailer_seed_source": "first 128 bits of SHA-256(R011-B012_SOURCE_MANIFEST.tsv)",
            "trailer_seed": trailer_seed.lower(),
            "trailer_ids_equal": True,
        },
        "page_count": run_a["page_count"],
        "affected_page_mapping": mapping,
        "reader_checks": text_checks,
        "visual": {
            "status": "RENDERED_ONLY_NOT_VISUALLY_APPROVED",
            "required_next_gate": "Inspect every listed PNG and record a separate zero-defect visual QA receipt before admission.",
            "pages": [item["page"] for item in renders],
            "artifacts": renders,
        },
        "toolchain": {name: tool_identity(name, Path(path)) for name, path in toolchain.items()},
        "translation_scope": "Section 3.4 / Variabel acak complete in source order: eight worked examples, nine guided exercises with inline public answers, EoCE 29-36, public answers 29/31/33/35, one preface terminology correction, and two localized figure derivatives.",
        "o001_gaps": [30, 32, 34, 36],
        "next_untranslated_anchor": "ch_probability/TeX/ch_probability.tex#contDist",
        "production_model": MODEL,
        "canonical_mutation": False,
        "git_used": False,
        "publication_performed": False,
        "upstream_contact": False,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    BUILD_RECEIPT.write_bytes(canonical_json(receipt))
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--self-test", action="store_true", help="Run read-only fail-closed harness checks.")
    action.add_argument("--check-readiness", action="store_true", help="Check exact terminal inputs without writing.")
    action.add_argument("--build", action="store_true", help="Execute two isolated deterministic builds after all gates pass.")
    action.add_argument("--finalize-existing", action="store_true", help="Verify completed guarded replays/renders and write only the missing terminal receipt.")
    parser.add_argument("--replace", action="store_true", help="Replace only exact B012 QA build outputs.")
    args = parser.parse_args()
    if args.replace and not args.build:
        parser.error("--replace is valid only with --build")
    if args.self_test:
        result = self_test()
    elif args.check_readiness:
        result = readiness()
    elif args.finalize_existing:
        result = finalize_existing()
    else:
        result = execute_build(replace=args.replace)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except GateError as exc:
        raise SystemExit(f"REFUSED: {exc}")
