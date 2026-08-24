#!/usr/bin/env python3
"""Assemble and deterministically build the isolated R011-B011 candidate."""

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
BASE_SCRIPT = LANE / "scripts" / "build_b010_candidate.py"
SPEC = importlib.util.spec_from_file_location("r011_b010_build_base", BASE_SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import build base: {BASE_SCRIPT}")
B010 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = B010
SPEC.loader.exec_module(B010)
BASE = B010.BASE

BASE.BASE_SNAPSHOT = LANE / "qa" / "b010-build" / "source-snapshot-b010"
BASE.BASE_MANIFEST = LANE / "qa" / "b010-build" / "R011-B010_SOURCE_MANIFEST.tsv"
BASE.CANDIDATE = LANE / "scratch" / "b011-candidate"
BASE.ASSETS = LANE / "scratch" / "b011-assets"
BASE.BUILD_ROOT = LANE / "qa" / "b011-build"
BASE.SNAPSHOT = BASE.BUILD_ROOT / "source-snapshot-b011"
BASE.FINAL = BASE.BUILD_ROOT / "final"
BASE.RENDER = BASE.BUILD_ROOT / "render"
BASE.SOURCE_MANIFEST = BASE.BUILD_ROOT / "R011-B011_SOURCE_MANIFEST.tsv"
BASE.SOURCE_QA = BASE.BUILD_ROOT / "R011-B011_SOURCE_QA.json"
BASE.RECEIPT = BASE.FINAL / "CANDIDATE_BUILD_QA_B011.json"
BASE.PDF = BASE.FINAL / "main.pdf"
BASE.PASS3 = BASE.FINAL / "main-pass3.pdf"
BASE.TEXT = BASE.FINAL / "main-final.txt"
BASE.BOUNDARY_ID = "R011-B011"

SECTION_FRAGMENT = BASE.CANDIDATE / "ch_probability_section_3_3_id.tex"
EOCE_FRAGMENT = BASE.CANDIDATE / "sampling_from_a_small_population_B011.tex"
ANSWER_FRAGMENT = BASE.CANDIDATE / "R011-B011_PUBLIC_ODD_ANSWERS.tex"
FULL_MAIN = BASE.CANDIDATE / "ch_probability_B011_source.tex"
FULL_ANSWERS = BASE.CANDIDATE / "eoceSolutions_B011_source.tex"
TRANSLATION_QA = BASE.CANDIDATE / "R011-B011_FINAL_TRANSLATION_QA.json"

MAIN_START = r"\section{Sampling from a small population}"
MAIN_END = r"\section{Random variables}"
TARGET_MAIN_START = r"\section{Pengambilan sampel dari populasi kecil}"
INPUT_TOKEN = r"{\input{ch_probability/TeX/sampling_from_a_small_population.tex}}"
LAYOUT_INPUT_TOKEN = r"{\setlength{\eoceAfterSpace}{2mm}\input{ch_probability/TeX/sampling_from_a_small_population.tex}}"
ANSWER_CONTEXT = "ch_probability/figures/eoce/tree_lupus/tree_lupus.pdf"
ANSWER_START = "% 23"
ANSWER_END = "% 29"
EXPECTED_MAIN_COUNTS = {
    r"\section{": 1,
    r"\subsection{": 0,
    r"\begin{nexample}": 3,
    r"\begin{nexercise}": 4,
    r"\footnotetext": 4,
    r"\Figure[": 0,
    r"\input{": 1,
}
EXPECTED_EOCE_LABELS = [
    "marbles_in_urn",
    "socks_in_drawer",
    "chips_in_bag",
    "books_on_shelf",
    "student_outfits",
    "birthday_problem",
]


def splice_once(base: str, start: str, end: str, replacement: str, label: str) -> str:
    start_at = base.find(start)
    end_at = base.find(end, start_at + len(start))
    if start_at < 0 or end_at < 0 or base.find(start, start_at + 1) >= 0:
        raise BASE.GateError(f"{label} anchors are absent or non-unique")
    return base[:start_at] + replacement.rstrip() + "\n\n" + base[end_at:]


def answer_bounds(text: str) -> tuple[int, int]:
    context_at = text.find(ANSWER_CONTEXT)
    if context_at < 0 or text.find(ANSWER_CONTEXT, context_at + 1) >= 0:
        raise BASE.GateError("Chapter 3 answer context is absent or non-unique")
    start_at = text.find(ANSWER_START, context_at + len(ANSWER_CONTEXT))
    end_at = text.find(ANSWER_END, start_at + len(ANSWER_START))
    if start_at < 0 or end_at < 0:
        raise BASE.GateError("B011 public-answer anchors are absent")
    return start_at, end_at


def assemble_main() -> Path:
    if not SECTION_FRAGMENT.is_file():
        raise BASE.GateError(f"translated section fragment absent: {SECTION_FRAGMENT}")
    source = (BASE.BASE_SNAPSHOT / "ch_probability" / "TeX" / "ch_probability.tex").read_text(encoding="utf-8")
    replacement = SECTION_FRAGMENT.read_text(encoding="utf-8")
    start_at = source.find(MAIN_START)
    input_at = source.find(INPUT_TOKEN, start_at)
    if start_at < 0 or input_at < 0:
        raise BASE.GateError("B011 main/input splice anchors are absent")
    end_at = input_at + len(INPUT_TOKEN)
    translated = replacement.rstrip()
    if translated.count(INPUT_TOKEN) != 1:
        raise BASE.GateError("B011 translated fragment lost its unique EoCE input anchor")
    translated = translated.replace(INPUT_TOKEN, LAYOUT_INPUT_TOKEN, 1)
    FULL_MAIN.parent.mkdir(parents=True, exist_ok=True)
    FULL_MAIN.write_text(source[:start_at] + translated + source[end_at:], encoding="utf-8", newline="\n")
    return FULL_MAIN


def assemble_answers() -> Path:
    if not ANSWER_FRAGMENT.is_file():
        raise BASE.GateError(f"translated answer fragment absent: {ANSWER_FRAGMENT}")
    source = (BASE.BASE_SNAPSHOT / "extraTeX" / "eoceSolutions" / "eoceSolutions.tex").read_text(encoding="utf-8")
    start_at, end_at = answer_bounds(source)
    replacement = ANSWER_FRAGMENT.read_text(encoding="utf-8")
    FULL_ANSWERS.write_text(source[:start_at] + replacement.rstrip() + "\n\n" + source[end_at:], encoding="utf-8", newline="\n")
    return FULL_ANSWERS


def section_slice(text: str, *, translated: bool) -> str:
    start = TARGET_MAIN_START if translated else MAIN_START
    start_at = text.find(start)
    end_at = text.find(MAIN_END, start_at + len(start))
    if start_at < 0 or end_at < 0:
        raise BASE.GateError("B011 section slice anchors are absent")
    return text[start_at:end_at]


def verify_main(path: Path) -> dict[str, Any]:
    target = section_slice(path.read_text(encoding="utf-8"), translated=True)
    authority_path = (
        LANE
        / "authority"
        / "upstream"
        / "openintro-statistics-fee25091fb24e89c36296fd67c48c1fcf7a93b6e"
        / "ch_probability"
        / "TeX"
        / "ch_probability.tex"
    )
    source = section_slice(authority_path.read_text(encoding="utf-8"), translated=False)
    counts: dict[str, int] = {}
    for token, expected in EXPECTED_MAIN_COUNTS.items():
        observed = target.count(token)
        counts[token] = observed
        if observed != expected or source.count(token) != expected:
            raise BASE.GateError(f"B011 main structure changed for {token}: {observed}/{expected}")
    source_labels = re.findall(r"\\label\{([^}]+)\}", source)
    target_labels = re.findall(r"\\label\{([^}]+)\}", target)
    if target_labels != source_labels:
        raise BASE.GateError("B011 main label identity/order changed")
    if target.count("{") - target.count("}") != source.count("{") - source.count("}"):
        raise BASE.GateError("B011 main brace delta changed")
    if target.count("$") != source.count("$"):
        raise BASE.GateError("B011 main math delimiter count changed")
    if r"\input{ch_probability/TeX/sampling_from_a_small_population.tex}" not in target:
        raise BASE.GateError("B011 main lost its exact EoCE input")
    return {"counts": counts, "labels": target_labels, "math_delimiters": target.count("$"), "brace_delta": target.count("{") - target.count("}")}


def verify_eoce(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    labels = re.findall(r"\\label\{([^}]+)\}", text)
    if labels != EXPECTED_EOCE_LABELS:
        raise BASE.GateError(f"B011 EoCE label identity/order changed: {labels}")
    if text.count(r"\eoce{") != 6 or text.count(r"\item") != 20:
        raise BASE.GateError("B011 EoCE exercise/item count changed")
    if text.count("{") != text.count("}"):
        raise BASE.GateError("B011 EoCE braces are unbalanced")
    return {"exercise_count": 6, "item_count": 20, "labels": labels, "brace_balance": 0}


def verify_answers(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    start_at, end_at = answer_bounds(text)
    answer_slice = text[start_at:end_at]
    expected = [23, 25, 27]
    absent = [number for number in expected if f"% {number}" not in answer_slice]
    leaked = [number for number in (24, 26, 28) if f"% {number}" in answer_slice]
    if absent or leaked or answer_slice.count(r"\eocesol{") != 3:
        raise BASE.GateError(f"B011 public-answer closure changed; absent={absent}, leaked={leaked}")
    if answer_slice.count("{") != answer_slice.count("}"):
        raise BASE.GateError("B011 public-answer braces are unbalanced")
    return {"public_answers": expected, "o001_gaps": [24, 26, 28], "restricted_answers_accessed": False, "brace_balance": 0}


def prepare_snapshot(replace: bool) -> tuple[dict[str, tuple[int, str]], dict[str, Any]]:
    rows = BASE.load_rows()
    if not BASE.BASE_SNAPSHOT.is_dir():
        raise BASE.GateError("admitted B010 source snapshot is absent")
    if BASE.SNAPSHOT.exists():
        if not replace:
            raise BASE.GateError(f"refusing to overwrite existing B011 snapshot: {BASE.rel(BASE.SNAPSHOT)}")
        shutil.rmtree(BASE.SNAPSHOT)
    shutil.copytree(BASE.BASE_SNAPSHOT, BASE.SNAPSHOT)
    overlays = {
        "ch_probability/TeX/ch_probability.tex": assemble_main(),
        "ch_probability/TeX/sampling_from_a_small_population.tex": EOCE_FRAGMENT,
        "extraTeX/eoceSolutions/eoceSolutions.tex": assemble_answers(),
    }
    identities: dict[str, Any] = {}
    for relative, source in overlays.items():
        if relative not in rows:
            raise BASE.GateError(f"B011 overlay path outside admitted B010 closure: {relative}")
        destination = BASE.SNAPSHOT / Path(relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        observed = BASE.identity(destination)
        rows[relative] = (observed["bytes"], observed["sha256"])
        identities[relative] = {"source": BASE.rel(source), "target": BASE.rel(destination), **observed}
    rows = dict(sorted(rows.items()))
    BASE.SOURCE_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    BASE.SOURCE_MANIFEST.write_text("".join(f"{path}\t{size}\t{digest}\n" for path, (size, digest) in rows.items()), encoding="utf-8", newline="\n")
    translation_qa = {"path": BASE.rel(TRANSLATION_QA), **BASE.identity(TRANSLATION_QA)} if TRANSLATION_QA.is_file() else None
    qa = {
        "$schema": "r011-b011-source-qa/v1",
        "boundary_id": "R011-B011",
        "status": "PASS_ISOLATED_OVERLAY_CLOSURE",
        "authority": {"repository": "https://github.com/OpenIntroStat/openintro-statistics", "branch": "master", "commit": BASE.AUTHORITY_COMMIT, "tree": BASE.AUTHORITY_TREE},
        "base_boundary": "R011-B010",
        "base_manifest": {"path": BASE.rel(BASE.BASE_MANIFEST), **BASE.identity(BASE.BASE_MANIFEST)},
        "manifest": {"path": BASE.rel(BASE.SOURCE_MANIFEST), **BASE.identity(BASE.SOURCE_MANIFEST), "files": len(rows)},
        "base_snapshot": {"path": BASE.rel(BASE.BASE_SNAPSHOT), "files": len(rows)},
        "overlays": identities,
        "checks": {"main": verify_main(FULL_MAIN), "eoce": verify_eoce(EOCE_FRAGMENT), "answers": verify_answers(FULL_ANSWERS), "overlay_count": 3},
        "layout_override": {
            "scope": "Only the six EoCE items included for Section 3.3",
            "source_eoce_after_space": "4mm",
            "target_eoce_after_space": "2mm",
            "reason": "Keep EoCE 28(a)-(b) with its prompt and eliminate a two-line continuation page before Section 3.4.",
            "semantic_change": False,
            "reversible_token": INPUT_TOKEN,
        },
        "translation_qa": translation_qa,
        "translation_provenance": BASE.MODEL,
        "untranslated_suffix": "Content from Section 3.4 / randomVariablesSection onward remains the inherited English witness.",
        "rights_note": "Text/translation retain CC BY-SA 3.0; no new figure/code/data assets are introduced by this bounded section; component-specific upstream rights remain controlling.",
        "canonical_mutation": False,
    }
    BASE.SOURCE_QA.write_bytes(BASE.canonical_json(qa))
    return rows, qa


BASE_BUILD = BASE.build


def build(rows: dict[str, tuple[int, str]], source_qa: dict[str, Any], *, replace: bool) -> dict[str, Any]:
    result = BASE_BUILD(rows, source_qa, replace=replace)
    result["$schema"] = "r011-b011-candidate-build-qa/v1"
    result["translation_scope"] = "Section 3.3 complete in source order: three worked examples, four guided exercises with public inline answers, EoCE 23-28, and public answers 23/25/27."
    result["o001_gaps"] = [24, 26, 28]
    result["next_untranslated_anchor"] = "ch_probability/TeX/ch_probability.tex#randomVariablesSection"
    result["visual"]["status"] = "GENERIC_RENDER_PASS_B011_WINDOW_REQUIRES_SEPARATE_AUDIT"
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
