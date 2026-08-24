#!/usr/bin/env python3
"""Assemble and build the isolated R011-B010 candidate.

The B009 admitted source snapshot is immutable input.  This script splices the
translated Section 3.2 and its public-answer slice, overlays the localized R/PDF
figure pairs, and writes only to ``scratch/b010-candidate`` and
``qa/b010-build``.  It never mutates the live ``repo``, ``backend``, ``output``,
``release``, or control files.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any


LANE = Path(__file__).resolve().parents[1]
BASE_SCRIPT = LANE / "scripts" / "build_b009_candidate.py"
SPEC = importlib.util.spec_from_file_location("r011_b009_build_base", BASE_SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import build base: {BASE_SCRIPT}")
BASE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = BASE
SPEC.loader.exec_module(BASE)

BASE.BASE_SNAPSHOT = LANE / "qa" / "b009-build" / "source-snapshot-b009"
BASE.BASE_MANIFEST = LANE / "qa" / "b009-build" / "R011-B009_SOURCE_MANIFEST.tsv"
BASE.CANDIDATE = LANE / "scratch" / "b010-candidate"
BASE.ASSETS = LANE / "scratch" / "b010-assets"
BASE.BUILD_ROOT = LANE / "qa" / "b010-build"
BASE.SNAPSHOT = BASE.BUILD_ROOT / "source-snapshot-b010"
BASE.FINAL = BASE.BUILD_ROOT / "final"
BASE.RENDER = BASE.BUILD_ROOT / "render"
BASE.SOURCE_MANIFEST = BASE.BUILD_ROOT / "R011-B010_SOURCE_MANIFEST.tsv"
BASE.SOURCE_QA = BASE.BUILD_ROOT / "R011-B010_SOURCE_QA.json"
BASE.RECEIPT = BASE.FINAL / "CANDIDATE_BUILD_QA_B010.json"
BASE.PDF = BASE.FINAL / "main.pdf"
BASE.PASS3 = BASE.FINAL / "main-pass3.pdf"
BASE.TEXT = BASE.FINAL / "main-final.txt"
BASE.BOUNDARY_ID = "R011-B010"

SECTION_FRAGMENT = BASE.CANDIDATE / "ch_probability_section_3_2_id.tex"
EOCE_FRAGMENT = BASE.CANDIDATE / "conditional_probability_B010.tex"
ANSWER_FRAGMENT = BASE.CANDIDATE / "R011-B010_PUBLIC_ODD_ANSWERS.tex"
FULL_MAIN = BASE.CANDIDATE / "ch_probability_B010_source.tex"
FULL_ANSWERS = BASE.CANDIDATE / "eoceSolutions_B010_source.tex"
TERMINOLOGY_QA = LANE / "qa" / "b010-terminology" / "R011-B010_PROBABILITY_TERMINOLOGY_QA.json"

MAIN_START = r"\section{Conditional probability}"
MAIN_END = r"\section{Sampling from a small population}"
ANSWER_START = "% 13"
ANSWER_END = "% 23"
ANSWER_CONTEXT = r"$0.16 + 0.09 = 0.25$"

EXPECTED_MAIN_COUNTS = {
    r"\section{": 1,
    r"\subsection{": 8,
    r"\begin{nexample}": 6,
    r"\begin{nexercise}": 15,
    r"\footnotetext": 15,
    r"\Figure[": 6,
    r"\input{": 1,
}
EXPECTED_EOCE_LABELS = [
    "joint_cond",
    "pbj",
    "global_warming",
    "health_coverage_rel_freqs",
    "burger_preferences",
    "assortative_mating",
    "tree_drawing_box_plots",
    "tree_thrombosis",
    "tree_lupus",
    "tree_exit_poll",
]


def splice_once(base: str, start: str, end: str, replacement: str, label: str) -> str:
    start_at = base.find(start)
    end_at = base.find(end, start_at + len(start))
    if start_at < 0 or end_at < 0 or base.find(start, start_at + 1) >= 0:
        raise BASE.GateError(f"{label} anchors are absent or non-unique")
    return base[:start_at] + replacement.rstrip() + "\n\n" + base[end_at:]


def main_candidate() -> Path:
    if not SECTION_FRAGMENT.is_file():
        raise BASE.GateError(f"translated section fragment absent: {SECTION_FRAGMENT}")
    source = (BASE.BASE_SNAPSHOT / "ch_probability" / "TeX" / "ch_probability.tex").read_text(
        encoding="utf-8"
    )
    replacement = SECTION_FRAGMENT.read_text(encoding="utf-8")
    FULL_MAIN.write_text(
        splice_once(source, MAIN_START, MAIN_END, replacement, "main section"),
        encoding="utf-8",
        newline="\n",
    )
    return FULL_MAIN


def answer_candidate() -> Path:
    if not ANSWER_FRAGMENT.is_file():
        raise BASE.GateError(f"translated answer fragment absent: {ANSWER_FRAGMENT}")
    source = (BASE.BASE_SNAPSHOT / "extraTeX" / "eoceSolutions" / "eoceSolutions.tex").read_text(
        encoding="utf-8"
    )
    replacement = ANSWER_FRAGMENT.read_text(encoding="utf-8")
    start_at, end_at = probability_answer_bounds(source)
    FULL_ANSWERS.write_text(
        source[:start_at] + replacement.rstrip() + "\n\n" + source[end_at:],
        encoding="utf-8",
        newline="\n",
    )
    return FULL_ANSWERS


def probability_answer_bounds(text: str) -> tuple[int, int]:
    """Return the unique Chapter 3 answer-13 through answer-21 span.

    Exercise numbers repeat in every chapter, so bare ``% 13``/``% 23``
    anchors are not globally unique.  The already admitted answer 11 directly
    before this slice provides a chapter-local, byte-stable context anchor.
    """

    context_at = text.find(ANSWER_CONTEXT)
    if context_at < 0 or text.find(ANSWER_CONTEXT, context_at + 1) >= 0:
        raise BASE.GateError("probability answer context anchor is absent or non-unique")
    start_at = text.find(ANSWER_START, context_at + len(ANSWER_CONTEXT))
    end_at = text.find(ANSWER_END, start_at + len(ANSWER_START))
    if start_at < 0 or end_at < 0:
        raise BASE.GateError("probability answer slice anchors are absent after context")
    return start_at, end_at


def main_section(text: str) -> str:
    start_at = text.find(r"\section{Peluang bersyarat}")
    end_at = text.find(MAIN_END, start_at + 1)
    if start_at < 0:
        raise BASE.GateError("translated Section 3.2 heading is absent")
    if end_at < 0:
        end_at = len(text)
    return text[start_at:end_at]


def verify_main(path: Path) -> dict[str, Any]:
    target = main_section(path.read_text(encoding="utf-8"))
    authority = (
        LANE
        / "authority"
        / "upstream"
        / "openintro-statistics-fee25091fb24e89c36296fd67c48c1fcf7a93b6e"
        / "ch_probability"
        / "TeX"
        / "ch_probability.tex"
    ).read_text(encoding="utf-8")
    source_start = authority.find(MAIN_START)
    source_end = authority.find(MAIN_END, source_start + 1)
    if source_start < 0 or source_end < 0:
        raise BASE.GateError("pinned authority section anchors are absent")
    source = authority[source_start:source_end]
    checks: dict[str, Any] = {}
    for token, expected in EXPECTED_MAIN_COUNTS.items():
        observed = target.count(token)
        checks[token] = observed
        if observed != expected or source.count(token) != expected:
            raise BASE.GateError(f"main structure count changed for {token}: {observed}/{expected}")
    source_labels = re.findall(r"\\label\{([^}]+)\}", source)
    target_labels = re.findall(r"\\label\{([^}]+)\}", target)
    if target_labels != source_labels:
        raise BASE.GateError("main label identity/order changed")
    if target.count("{") - target.count("}") != source.count("{") - source.count("}"):
        raise BASE.GateError("main raw brace-count delta differs from authority")
    if target.count("$") != source.count("$"):
        raise BASE.GateError("main math-delimiter count differs from authority")
    if r"\input{ch_probability/TeX/conditional_probability.tex}" not in target:
        raise BASE.GateError("translated section lost its EoCE input")
    checks.update(
        {
            "labels": target_labels,
            "label_count": len(target_labels),
            "brace_delta": target.count("{") - target.count("}"),
            "math_delimiters": target.count("$"),
        }
    )
    return checks


def verify_eoce(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    labels = re.findall(r"\\label\{([^}]+)\}", text)
    if labels != EXPECTED_EOCE_LABELS:
        raise BASE.GateError(f"EoCE label identity/order changed: {labels}")
    if text.count(r"\eoce{") != 10 or text.count(r"\item") != 29:
        raise BASE.GateError("EoCE exercise/item count changed")
    if text.count("{") != text.count("}"):
        raise BASE.GateError("EoCE braces are unbalanced")
    return {"exercise_count": 10, "item_count": 29, "labels": labels, "brace_balance": 0}


def verify_answers(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    start_at, end_at = probability_answer_bounds(text)
    answer_slice = text[start_at:end_at]
    expected = [13, 15, 17, 19, 21]
    absent = [n for n in expected if f"% {n}" not in answer_slice]
    leaked = [n for n in (14, 16, 18, 20, 22) if f"% {n}" in answer_slice]
    if absent or leaked or answer_slice.count(r"\eocesol{") != 5:
        raise BASE.GateError(f"public-answer closure changed; absent={absent}, leaked={leaked}")
    if answer_slice.count("{") != answer_slice.count("}"):
        raise BASE.GateError("public-answer braces are unbalanced")
    return {"public_answers": expected, "restricted_even_answers": [], "brace_balance": 0}


def asset_overlays() -> dict[str, Path]:
    stems = [
        "BreastCancerTreeDiagram",
        "photoClassifyVenn",
        "smallpoxTreeDiagram",
        "testTree",
        "treeDiagramAndPass",
        "treeDiagramGarage",
    ]
    result: dict[str, Path] = {}
    for stem in stems:
        for suffix in ("R", "pdf"):
            source = BASE.ASSETS / "id-ID" / stem / f"{stem}.{suffix}"
            if not source.is_file():
                raise BASE.GateError(f"localized asset absent: {source}")
            result[f"ch_probability/figures/{stem}/{stem}.{suffix}"] = source
    for stem in ("tree_drawing_box_plots", "tree_lupus"):
        for suffix in ("R", "pdf"):
            source = BASE.ASSETS / "id-ID" / "eoce" / stem / f"{stem}.{suffix}"
            if not source.is_file():
                raise BASE.GateError(f"localized EoCE asset absent: {source}")
            result[f"ch_probability/figures/eoce/{stem}/{stem}.{suffix}"] = source
    return result


def prepare_snapshot(replace: bool) -> tuple[dict[str, tuple[int, str]], dict[str, Any]]:
    rows = BASE.load_rows()
    if not BASE.BASE_SNAPSHOT.is_dir():
        raise BASE.GateError("admitted B009 source snapshot is absent")
    if BASE.SNAPSHOT.exists():
        if not replace:
            raise BASE.GateError(f"refusing to overwrite existing B010 snapshot: {BASE.rel(BASE.SNAPSHOT)}")
        shutil.rmtree(BASE.SNAPSHOT)
    shutil.copytree(BASE.BASE_SNAPSHOT, BASE.SNAPSHOT)

    overlays: dict[str, Path] = {
        "ch_probability/TeX/ch_probability.tex": main_candidate(),
        "ch_probability/TeX/conditional_probability.tex": EOCE_FRAGMENT,
        "extraTeX/eoceSolutions/eoceSolutions.tex": answer_candidate(),
    }
    overlays.update(asset_overlays())
    identities: dict[str, Any] = {}
    for relative, source in overlays.items():
        if relative not in rows:
            raise BASE.GateError(f"overlay path outside admitted B009 closure: {relative}")
        destination = BASE.SNAPSHOT / Path(relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        observed = BASE.identity(destination)
        rows[relative] = (observed["bytes"], observed["sha256"])
        identities[relative] = {
            "source": BASE.rel(source),
            "target": BASE.rel(destination),
            "bytes": observed["bytes"],
            "sha256": observed["sha256"],
        }

    rows = dict(sorted(rows.items()))
    BASE.SOURCE_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    BASE.SOURCE_MANIFEST.write_text(
        "".join(f"{path}\t{size}\t{digest}\n" for path, (size, digest) in rows.items()),
        encoding="utf-8",
        newline="\n",
    )
    checks = {
        "main": verify_main(FULL_MAIN),
        "eoce": verify_eoce(EOCE_FRAGMENT),
        "answers": verify_answers(FULL_ANSWERS),
        "overlay_count": len(overlays),
    }
    qa = {
        "$schema": "r011-b010-source-qa/v1",
        "boundary_id": "R011-B010",
        "status": "PASS_ISOLATED_OVERLAY_CLOSURE",
        "authority": {
            "repository": "https://github.com/OpenIntroStat/openintro-statistics",
            "branch": "master",
            "commit": BASE.AUTHORITY_COMMIT,
            "tree": BASE.AUTHORITY_TREE,
        },
        "base_boundary": "R011-B009",
        "base_manifest": {"path": BASE.rel(BASE.BASE_MANIFEST), **BASE.identity(BASE.BASE_MANIFEST)},
        "manifest": {"path": BASE.rel(BASE.SOURCE_MANIFEST), **BASE.identity(BASE.SOURCE_MANIFEST), "files": len(rows)},
        "base_snapshot": {"path": BASE.rel(BASE.BASE_SNAPSHOT), "files": len(rows)},
        "overlays": identities,
        "checks": checks,
        "terminology_qa": {"path": BASE.rel(TERMINOLOGY_QA), **BASE.identity(TERMINOLOGY_QA)},
        "translation_provenance": BASE.MODEL,
        "untranslated_suffix": "Content from Section 3.3 / smallPop onward remains the inherited English witness.",
        "rights_note": "Text/translation retain CC BY-SA 3.0; component-specific upstream rights and external data citations remain controlling.",
        "canonical_mutation": False,
    }
    BASE.SOURCE_QA.write_bytes(BASE.canonical_json(qa))
    return rows, qa


BASE_BUILD = BASE.build


def build(rows: dict[str, tuple[int, str]], source_qa: dict[str, Any], *, replace: bool) -> dict[str, Any]:
    result = BASE_BUILD(rows, source_qa, replace=replace)
    result["$schema"] = "r011-b010-candidate-build-qa/v1"
    result["translation_scope"] = (
        "Section 3.2 / Peluang bersyarat complete in source order: eight subsections, six worked examples, "
        "15 guided exercises with public inline answers, EoCE 13-22, and public answers 13/15/17/19/21."
    )
    result["o001_gaps"] = [14, 16, 18, 20, 22]
    result["next_untranslated_anchor"] = "ch_probability/TeX/ch_probability.tex#smallPop"
    result["terminology_qa"] = {"path": BASE.rel(TERMINOLOGY_QA), **BASE.identity(TERMINOLOGY_QA)}
    result["visual"]["status"] = "GENERIC_RENDER_PASS_B010_WINDOW_REQUIRES_SEPARATE_AUDIT"
    BASE.RECEIPT.write_bytes(BASE.canonical_json(result))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    if not args.build:
        parser.error("pass --build")
    rows, source_qa = prepare_snapshot(args.replace)
    result = build(rows, source_qa, replace=args.replace)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
