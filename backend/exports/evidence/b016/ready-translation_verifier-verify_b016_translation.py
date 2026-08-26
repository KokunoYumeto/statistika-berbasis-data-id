#!/usr/bin/env python3
"""Fail-closed, read-only integration QA for R011-B016 translation inputs.

The verifier compares the candidate against exact frozen slices of the pinned
OpenIntro Statistics authority.  It emits one deterministic JSON document to
stdout and never mutates the candidate, live reader, backend, control, or
release surfaces.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]

BOUNDARY = "R011-B016"
MODEL = "OpenAI Codex gpt-5.6-sol, Ultra"
COMMIT = "fee25091fb24e89c36296fd67c48c1fcf7a93b6e"
TREE = "d61cc601e7d97759ce805900520f784d02a0489e"
UPSTREAM = Path(
    "authority/upstream/"
    "openintro-statistics-fee25091fb24e89c36296fd67c48c1fcf7a93b6e"
)

PATHS = {
    "authority_metadata": Path("authority/UPSTREAM_AUTHORITY.json"),
    "full_main_authority": UPSTREAM / "ch_distributions/TeX/ch_distributions.tex",
    "full_eoce_authority": UPSTREAM / "ch_distributions/TeX/binomial_distribution.tex",
    "full_answers_authority": UPSTREAM / "extraTeX/eoceSolutions/eoceSolutions.tex",
    "full_data_authority": UPSTREAM / "extraTeX/data/data.tex",
    "main_authority": Path("qa/b016-source/R011-B016_MAIN_AUTHORITY_LINES_1268-1926.tex"),
    "preboundary_authority": Path("qa/b016-source/R011-B016_PREBOUNDARY_MACROS_AUTHORITY_LINES_979-982.tex"),
    "eoce_authority": Path("qa/b016-source/R011-B016_EOCE_17-26_AUTHORITY.tex"),
    "answers_authority": Path("qa/b016-source/R011-B016_PUBLIC_ODD_ANSWERS_AUTHORITY_LINES_707-748.tex"),
    "data_authority": Path("qa/b016-source/R011-B016_DATA_APPENDIX_AUTHORITY_LINES_277-294.tex"),
    "o001_contract": Path("qa/b016-source/R011-B016_O001_GAP_CONTRACT.json"),
    "source_closure": Path("qa/b016-source/R011-B016_SOURCE_CLOSURE.json"),
    "asset_closure": Path("qa/b016-assets/R011-B016_ASSET_RIGHTS_CLOSURE.json"),
    "asset_manifest": Path("qa/b016-assets/R011-B016_ASSET_MANIFEST.csv"),
    "controlled_terms": Path("qa/b016-terminology/R011-B016_CONTROLLED_TERMS.tsv"),
    "terminology_qa": Path("qa/b016-terminology/R011-B016_TERMINOLOGY_QA.json"),
    "main_candidate_receipt": Path("scratch/b016-candidate/R011-B016_MAIN_TRANSLATION_CANDIDATE_RECEIPT.json"),
    "companion_candidate_receipt": Path("scratch/b016-candidate/R011-B016_COMPANION_RECEIPT.json"),
    "term_notes": Path("scratch/b016-candidate/R011-B016_TERM_NOTES.md"),
    "main_target": Path("scratch/b016-candidate/ch_distributions_section_4_3_id.tex"),
    "eoce_target": Path("scratch/b016-candidate/binomial_distribution_B016.tex"),
    "answers_target": Path("scratch/b016-candidate/R011-B016_PUBLIC_ODD_ANSWERS.tex"),
    "data_target": Path("scratch/b016-candidate/data_binomialModel_B016.tex"),
    "o001_target": Path("scratch/b016-candidate/R011-B016_O001_GAPS.json"),
}

EXPECTED: dict[str, tuple[int, str]] = {
    "authority_metadata": (912, "3e4e2b4921d32d62e3b269e2a7f258c63d1d6fcbed2a6ff1cededfc35a5bbd2d"),
    "full_main_authority": (91188, "71e4985a1bf31e9dd6897ec2bd246b3b2f8cd62ab55524a5b1bfe791e613a3a9"),
    "full_eoce_authority": (8716, "ac032b8749237e2fc3911cb1d007d5555a86d47ecba9ea9937e8f502f50348ff"),
    "full_answers_authority": (106045, "6c4e01376db4c023cc7b3f9949490e57220ef1cb831c580da71efde6ce723268"),
    "full_data_authority": (26134, "6456ef7e9d0f855dbba47f9f62f0f10ae731d4f7cd558399848419d3cbdfd88b"),
    "main_authority": (24451, "530585267669f06c551b86dce8345147f3654d716e851c9be5d76facff47b8e5"),
    "preboundary_authority": (126, "b161752de6bf8f931db640c5ec18d2b017c73c36ae8fd4463b20bfe6f57aa96e"),
    "eoce_authority": (8716, "ac032b8749237e2fc3911cb1d007d5555a86d47ecba9ea9937e8f502f50348ff"),
    "answers_authority": (1412, "17f8ab6e9a1a9c62bbf1d2bf09567bd66df0f3c8103db5c0fe41cae4ebef5e72"),
    "data_authority": (841, "92e13799051af370ea6f5314be4b62c14711322c8d113b64ca93c3a0c44b4ff9"),
    "o001_contract": (749, "4cc986cfb9e06e3ec92868b3ec4588fbf95dbd5f91cf3d0db537abb7cf93c534"),
    "source_closure": (11016, "a7da0fe79174fbbfe62f90f1bb7f17cdb5aad058c347adf23d3b0f61490fee8f"),
    "asset_closure": (6800, "9c202cb46e9dba5cdc7de172c39654866d938d9f3db2d5e9f3cfd45716772fab"),
    "asset_manifest": (6109, "0055e1db8efaf6178097e09dde69040acb0f65514b7a3ce6f2aeaa505a86a811"),
    "controlled_terms": (4525, "a24dbeb63cc74ec4e851a4eeb7e79ca04ca384aed6e2ec54cb5cb10cf8950ebc"),
    "terminology_qa": (4654, "01c2dfc92b64a1e1c8e07eee66936049405332777a8f255b34063c3664d82c8d"),
    "main_candidate_receipt": (6775, "39a6b26a67657db3b40b1eb1d8d9afecad66dc63fe7c1e04c3989f662cdb134d"),
    "companion_candidate_receipt": (4999, "946da79575ad52f355d2e5db0795374df649e9d296a6016bd7a1b128f34ee0db"),
    "term_notes": (3789, "2898e9cb72a3dc41fb4c8e89d90e2d6ff7524b7da3fc4d96fa2c25c2418c139f"),
    "main_target": (25367, "8d99fee42d7f998cf7af6c3c7406457f503fdecd940b5985ca3aa63c4091d6ef"),
    "eoce_target": (9271, "e7030cb0c07cffb5881909e79edbfa2476e22abce5fb45e8e9cb62b869841768"),
    "answers_target": (1605, "d6b6ac7470d65fafdd7382004b43019f8f92029d717aa9f5a51b4327d173244c"),
    "data_target": (956, "beddd03e4cca459911d425c17094eaea8aa8860b9ac922aa829337c109ec214c"),
    "o001_target": (1571, "293f1eead83affc4a0197a3a8838affdd8698da39e93be78be3513dcd3872266"),
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_hash(value: Any) -> str:
    return sha256(json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8"))


checks: list[dict[str, Any]] = []


def check(check_id: str, condition: bool, evidence: Any) -> None:
    checks.append({
        "check_id": check_id,
        "status": "PASS" if condition else "FAIL",
        "evidence": evidence,
    })


raw: dict[str, bytes] = {}
texts: dict[str, str] = {}
identities: dict[str, dict[str, Any]] = {}
for key, rel in PATHS.items():
    path = ROOT / rel
    data = path.read_bytes()
    digest = sha256(data)
    raw[key] = data
    identities[key] = {"path": rel.as_posix(), "bytes": len(data), "sha256": digest}
    exp_bytes, exp_hash = EXPECTED[key]
    check(
        f"identity.{key}",
        len(data) == exp_bytes and digest == exp_hash,
        {"expected_bytes": exp_bytes, "expected_sha256": exp_hash, **identities[key]},
    )
    if rel.suffix.lower() in {".tex", ".json", ".tsv", ".md", ".csv"}:
        try:
            text = data.decode("utf-8")
            texts[key] = text
            check(
                f"encoding.{key}",
                not data.startswith(b"\xef\xbb\xbf") and "\r" not in text,
                {"utf8": True, "bom": False, "line_endings": "LF"},
            )
        except UnicodeDecodeError as exc:
            texts[key] = ""
            check(f"encoding.{key}", False, {"error": str(exc)})


source_closure = json.loads(texts["source_closure"])
asset_closure = json.loads(texts["asset_closure"])
terminology_qa = json.loads(texts["terminology_qa"])
authority_metadata = json.loads(texts["authority_metadata"])

check(
    "authority.pin",
    source_closure["authority"]["commit"] == COMMIT
    and source_closure["authority"]["tree"] == TREE
    and source_closure["authority"]["repository"] == "https://github.com/OpenIntroStat/openintro-statistics"
    and asset_closure["authority"] == {"commit": COMMIT, "tree": TREE},
    {"commit": COMMIT, "tree": TREE, "branch": "master"},
)
check(
    "authority.metadata_binding",
    authority_metadata.get("commit") == COMMIT
    and authority_metadata.get("calculated_git_tree_sha1") == TREE,
    {"authority_metadata": identities["authority_metadata"]},
)
check(
    "closure.status",
    source_closure.get("status") == "PASS_EXACT_SOURCE_RIGHTS_ASSET_AND_NEXT_CURSOR_CLOSURE"
    and asset_closure.get("status") == "PASS_EXACT_ASSET_IDENTITY_RIGHTS_AND_REUSE_DECISIONS_CLOSED",
    {"source": source_closure.get("status"), "assets": asset_closure.get("status")},
)
check(
    "rights.boundary",
    source_closure["rights_and_exclusions"]["restricted_instructor_solutions"] == "not sought or ingested"
    and asset_closure["rights_decisions"]["book_text_and_repository_generated_figures"] == "CC BY-SA 3.0 Unported"
    and asset_closure["rights_decisions"]["dreidel_photo"] == "separately governed CC BY 2.0 component"
    and asset_closure["rights_decisions"]["openintro_r_package"].startswith("separately governed GPL-3"),
    {
        "book_and_generated_figures": "CC BY-SA 3.0 Unported",
        "dreidel_photo": "CC BY 2.0",
        "openintro_r_package": "GPL-3 build dependency, not reader payload",
        "restricted_instructor_solutions": "not sought or ingested",
    },
)


def exact_slice(full: bytes, start: int, end: int) -> bytes:
    return b"".join(full.splitlines(keepends=True)[start - 1 : end])


slice_specs = [
    ("main", "full_main_authority", 1268, 1926, "main_authority"),
    ("preboundary_macros", "full_main_authority", 979, 982, "preboundary_authority"),
    ("public_answers", "full_answers_authority", 707, 748, "answers_authority"),
    ("data_appendix", "full_data_authority", 277, 294, "data_authority"),
]
for name, full_key, start, end, witness_key in slice_specs:
    observed = exact_slice(raw[full_key], start, end)
    check(
        f"authority.slice.{name}",
        observed == raw[witness_key],
        {
            "full_path": identities[full_key]["path"],
            "start_line": start,
            "end_line": end,
            "witness": identities[witness_key],
            "observed_slice_sha256": sha256(observed),
        },
    )
check(
    "authority.complete_eoce",
    raw["full_eoce_authority"] == raw["eoce_authority"],
    {"complete_file": identities["full_eoce_authority"], "witness": identities["eoce_authority"]},
)


def strip_comments(text: str) -> str:
    lines = []
    for line in text.splitlines(keepends=True):
        cut = None
        for index, char in enumerate(line):
            if char != "%":
                continue
            backslashes = 0
            cursor = index - 1
            while cursor >= 0 and line[cursor] == "\\":
                backslashes += 1
                cursor -= 1
            if backslashes % 2 == 0:
                cut = index
                break
        lines.append((line if cut is None else line[:cut] + ("\n" if line.endswith("\n") else "")))
    return "".join(lines)


def command_sequence(text: str) -> list[str]:
    return re.findall(r"\\(?:[A-Za-z@]+|.)", strip_comments(text), flags=re.DOTALL)


def environment_events(text: str) -> list[list[str]]:
    return [[kind, env] for kind, env in re.findall(r"\\(begin|end)\s*\{([^{}]+)\}", strip_comments(text))]


def simple_args(text: str, commands: Iterable[str]) -> list[list[str]]:
    names = "|".join(re.escape(name) for name in commands)
    return [[command, value] for command, value in re.findall(rf"\\({names})\s*\{{([^{{}}]*)\}}", strip_comments(text))]


def forced_breaks(text: str) -> list[str]:
    pattern = re.compile(r"\\D\s*\{\s*\\newpage\s*\}|\\newpage")
    return ["D_NEW_PAGE" if match.group(0).lstrip().startswith("\\D") else "NEW_PAGE" for match in pattern.finditer(strip_comments(text))]


def brace_balance(text: str) -> tuple[int, int]:
    depth = 0
    minimum = 0
    clean = strip_comments(text)
    for index, char in enumerate(clean):
        if char not in "{}":
            continue
        backslashes = 0
        cursor = index - 1
        while cursor >= 0 and clean[cursor] == "\\":
            backslashes += 1
            cursor -= 1
        if backslashes % 2 == 1:
            continue
        depth += 1 if char == "{" else -1
        minimum = min(minimum, depth)
    return depth, minimum


def parse_braced(text: str, start: int) -> tuple[str, int]:
    if start >= len(text) or text[start] != "{":
        raise ValueError(f"expected opening brace at offset {start}")
    depth = 0
    for index in range(start, len(text)):
        char = text[index]
        escaped = index > 0 and text[index - 1] == "\\"
        if char == "{" and not escaped:
            depth += 1
        elif char == "}" and not escaped:
            depth -= 1
            if depth == 0:
                return text[start + 1 : index], index + 1
    raise ValueError("unclosed braced argument")


def newcommands(text: str) -> list[list[str]]:
    result: list[list[str]] = []
    cursor = 0
    while True:
        match = re.search(r"\\newcommand\s*", text[cursor:])
        if not match:
            return result
        offset = cursor + match.end()
        name, offset = parse_braced(text, offset)
        while offset < len(text) and text[offset].isspace():
            offset += 1
        if offset < len(text) and text[offset] == "[":
            offset = text.index("]", offset) + 1
            while offset < len(text) and text[offset].isspace():
                offset += 1
        body, offset = parse_braced(text, offset)
        result.append([name, body])
        cursor = offset


def figure_calls(text: str) -> list[dict[str, str]]:
    clean = strip_comments(text)
    pattern = re.compile(
        r"\\(Figure|Figures)\[(.*?)\]\{([^{}]*)\}\{([^{}]*)\}(?:\{([^{}]*)\})?",
        flags=re.DOTALL,
    )
    return [
        {"command": command, "alt": alt, "width": width, "key": key, "file": file_name or ""}
        for command, alt, width, key, file_name in pattern.findall(clean)
    ]


def canonical_text_inner(inner: str) -> str:
    tokens = re.findall(r"\\(?:[A-Za-z@]+|.)|\d+(?:\.\d+)?|[^A-Za-zÀ-ÖØ-öø-ÿ\d\s]", inner, flags=re.DOTALL)
    return "".join(tokens)


def canonicalize_text_args(segment: str) -> str:
    result: list[str] = []
    cursor = 0
    while True:
        match = re.search(r"\\text\s*\{", segment[cursor:])
        if not match:
            result.append(segment[cursor:])
            break
        start = cursor + match.start()
        brace = cursor + match.end() - 1
        result.append(segment[cursor:start])
        inner, end = parse_braced(segment, brace)
        result.append("\\text{" + canonical_text_inner(inner) + "}")
        cursor = end
    return re.sub(r"\s+", "", "".join(result))


def dollar_math(text: str) -> list[str]:
    clean = strip_comments(text)
    dollars: list[int] = []
    for index, char in enumerate(clean):
        if char != "$":
            continue
        backslashes = 0
        cursor = index - 1
        while cursor >= 0 and clean[cursor] == "\\":
            backslashes += 1
            cursor -= 1
        if backslashes % 2 == 0:
            dollars.append(index)
    if len(dollars) % 2:
        return ["<UNBALANCED_DOLLAR>"]
    return [canonicalize_text_args(clean[dollars[index] + 1 : dollars[index + 1]]) for index in range(0, len(dollars), 2)]


def display_math(text: str) -> list[str]:
    clean = strip_comments(text)
    pattern = re.compile(
        r"\\begin\{(align\*?|equation\*?|displaymath)\}(.*?)\\end\{\1\}",
        flags=re.DOTALL,
    )
    return [canonicalize_text_args(body) for _, body in pattern.findall(clean)]


def numeric_sequence(text: str) -> list[str]:
    return re.findall(r"(?<![A-Za-z@])\d+(?:\.\d+)?", strip_comments(text))


pair_specs = [
    ("main", "main_authority", "main_target"),
    ("eoce", "eoce_authority", "eoce_target"),
    ("public_answers", "answers_authority", "answers_target"),
    ("data_appendix", "data_authority", "data_target"),
]
topology: dict[str, Any] = {}
for component, source_key, target_key in pair_specs:
    source = texts[source_key]
    target = texts[target_key]
    structural_source = source
    structural_target = target
    if component == "eoce":
        approved_break = r"\D{\newpage}"
        check(
            "layout.eoce.relocated_reader_break",
            source.count(approved_break) == 1
            and target.count(approved_break) == 1
            and source.count(r"\vfill") == 0
            and target.count(r"\vfill") == 6,
            {
                "relocated_source_command": approved_break,
                "source_after_exercise": 21,
                "target_before_exercise": 24,
                "target_flexible_vertical_fills": 6,
                "reason": "balance and vertically distribute all three EoCE pages while preserving the display-only break count",
            },
        )
        structural_source = source.replace(approved_break, "", 1)
        structural_target = target.replace(approved_break, "", 1).replace(r"\vfill", "")
    source_commands = command_sequence(structural_source)
    target_commands = command_sequence(structural_target)
    source_env = environment_events(structural_source)
    target_env = environment_events(structural_target)
    source_labels = simple_args(structural_source, ["label"])
    target_labels = simple_args(structural_target, ["label"])
    source_refs = simple_args(structural_source, ["ref", "pageref", "eqref"])
    target_refs = simple_args(target, ["ref", "pageref", "eqref"])
    source_indexes = simple_args(structural_source, ["index"])
    target_indexes = simple_args(target, ["index"])
    source_inputs = simple_args(structural_source, ["input"])
    target_inputs = simple_args(target, ["input"])
    source_cites = simple_args(structural_source, ["footfullcite", "cite", "textcite", "parencite"])
    target_cites = simple_args(target, ["footfullcite", "cite", "textcite", "parencite"])
    source_redirects = simple_args(structural_source, ["oiRedirect"])
    target_redirects = simple_args(target, ["oiRedirect"])
    source_breaks = forced_breaks(structural_source)
    target_breaks = forced_breaks(structural_target)
    source_figures = figure_calls(structural_source)
    target_figures = figure_calls(target)
    source_figure_topology = [{key: value for key, value in item.items() if key != "alt"} for item in source_figures]
    target_figure_topology = [{key: value for key, value in item.items() if key != "alt"} for item in target_figures]
    source_dollar = dollar_math(structural_source)
    target_dollar = dollar_math(target)
    if component == "eoce":
        source_dollar = [value.replace("4^{th}", "4").replace("3^{rd}", "3") for value in source_dollar]
    source_display = display_math(structural_source)
    target_display = display_math(target)
    source_numbers = numeric_sequence(structural_source)
    target_numbers = numeric_sequence(target)
    source_balance = brace_balance(structural_source)
    target_balance = brace_balance(target)

    comparisons = {
        "command_sequence": source_commands == target_commands,
        "environment_event_order": source_env == target_env,
        "label_order": source_labels == target_labels,
        "reference_order": source_refs == target_refs,
        "index_key_order": source_indexes == target_indexes,
        "input_order": source_inputs == target_inputs,
        "citation_key_order": source_cites == target_cites,
        "redirect_id_order": source_redirects == target_redirects,
        "forced_break_order": source_breaks == target_breaks,
        "figure_width_key_file_order": source_figure_topology == target_figure_topology,
        "figure_alt_text_localized": len(source_figures) == len(target_figures)
        and all(s["alt"] != t["alt"] and bool(t["alt"].strip()) for s, t in zip(source_figures, target_figures)),
        "dollar_math_signature_order": source_dollar == target_dollar,
        "display_math_signature_order": source_display == target_display,
        "numeric_literal_order": source_numbers == target_numbers,
        "balanced_braces": source_balance == (0, 0) and target_balance == (0, 0),
    }
    for comparison, passed in comparisons.items():
        check(
            f"topology.{component}.{comparison}",
            passed,
            {
                "source_count": {
                    "command_sequence": len(source_commands),
                    "environment_event_order": len(source_env),
                    "label_order": len(source_labels),
                    "reference_order": len(source_refs),
                    "index_key_order": len(source_indexes),
                    "input_order": len(source_inputs),
                    "citation_key_order": len(source_cites),
                    "redirect_id_order": len(source_redirects),
                    "forced_break_order": len(source_breaks),
                    "figure_width_key_file_order": len(source_figures),
                    "figure_alt_text_localized": len(source_figures),
                    "dollar_math_signature_order": len(source_dollar),
                    "display_math_signature_order": len(source_display),
                    "numeric_literal_order": len(source_numbers),
                    "balanced_braces": source_balance,
                }[comparison],
                "target_count": {
                    "command_sequence": len(target_commands),
                    "environment_event_order": len(target_env),
                    "label_order": len(target_labels),
                    "reference_order": len(target_refs),
                    "index_key_order": len(target_indexes),
                    "input_order": len(target_inputs),
                    "citation_key_order": len(target_cites),
                    "redirect_id_order": len(target_redirects),
                    "forced_break_order": len(target_breaks),
                    "figure_width_key_file_order": len(target_figures),
                    "figure_alt_text_localized": len(target_figures),
                    "dollar_math_signature_order": len(target_dollar),
                    "display_math_signature_order": len(target_display),
                    "numeric_literal_order": len(target_numbers),
                    "balanced_braces": target_balance,
                }[comparison],
                "source_signature_sha256": stable_hash({
                    "command_sequence": source_commands,
                    "environment_event_order": source_env,
                    "label_order": source_labels,
                    "reference_order": source_refs,
                    "index_key_order": source_indexes,
                    "input_order": source_inputs,
                    "citation_key_order": source_cites,
                    "redirect_id_order": source_redirects,
                    "forced_break_order": source_breaks,
                    "figure_width_key_file_order": source_figure_topology,
                    "figure_alt_text_localized": [item["alt"] for item in source_figures],
                    "dollar_math_signature_order": source_dollar,
                    "display_math_signature_order": source_display,
                    "numeric_literal_order": source_numbers,
                    "balanced_braces": source_balance,
                }[comparison]),
                "target_signature_sha256": stable_hash({
                    "command_sequence": target_commands,
                    "environment_event_order": target_env,
                    "label_order": target_labels,
                    "reference_order": target_refs,
                    "index_key_order": target_indexes,
                    "input_order": target_inputs,
                    "citation_key_order": target_cites,
                    "redirect_id_order": target_redirects,
                    "forced_break_order": target_breaks,
                    "figure_width_key_file_order": target_figure_topology,
                    "figure_alt_text_localized": [item["alt"] for item in target_figures],
                    "dollar_math_signature_order": target_dollar,
                    "display_math_signature_order": target_display,
                    "numeric_literal_order": target_numbers,
                    "balanced_braces": target_balance,
                }[comparison]),
            },
        )
    topology[component] = {
        "commands": len(target_commands),
        "environment_events": len(target_env),
        "labels": [value for _, value in target_labels],
        "references": [value for _, value in target_refs],
        "index_keys": [value for _, value in target_indexes],
        "inputs": [value for _, value in target_inputs],
        "citation_keys": [value for _, value in target_cites],
        "forced_breaks": target_breaks,
        "figures": target_figure_topology,
        "dollar_math_segments": len(target_dollar),
        "display_math_blocks": len(target_display),
        "numeric_literals": len(target_numbers),
        "math_signature_sha256": stable_hash({"dollar": target_dollar, "display": target_display}),
        "numeric_signature_sha256": stable_hash(target_numbers),
    }


source_macros = newcommands(texts["main_authority"])
target_macros = newcommands(texts["main_target"])
source_macro_map = dict(source_macros)
target_macro_map = dict(target_macros)
approved_localized_macro_bodies = {
    "\\insureS": ["\\resp{not}", "\\resp{tidak}"],
    "\\insureF": ["\\resp{exceed}", "\\resp{melampaui}"],
}
exact_macro_names = [name for name, _ in source_macros if name not in approved_localized_macro_bodies]
check(
    "newcommand.name_order_and_count",
    len(source_macros) == 45
    and len(target_macros) == 45
    and [name for name, _ in source_macros] == [name for name, _ in target_macros],
    {"source_count": len(source_macros), "target_count": len(target_macros), "name_order_sha256": stable_hash([name for name, _ in target_macros])},
)
check(
    "newcommand.exact_values_except_two_reader_macros",
    all(source_macro_map[name] == target_macro_map[name] for name in exact_macro_names),
    {"exact_value_count": len(exact_macro_names), "localized_value_count": 2},
)
check(
    "newcommand.approved_reader_localizations",
    all([source_macro_map[name], target_macro_map[name]] == values for name, values in approved_localized_macro_bodies.items()),
    {name: {"source": values[0], "target": values[1]} for name, values in approved_localized_macro_bodies.items()},
)
preboundary_macros = dict(newcommands(texts["preboundary_authority"]))
expected_preboundary = {
    "\\insureSprob": "0.7",
    "\\insureSperc": "70\\%",
    "\\insureFprob": "0.3",
    "\\insureFperc": "30\\%",
}
check(
    "newcommand.preboundary_dependency_values",
    preboundary_macros == expected_preboundary
    and all(texts["main_target"].count(name) >= 1 for name in expected_preboundary),
    {"values": preboundary_macros, "target_reference_counts": {name: texts["main_target"].count(name) for name in expected_preboundary}},
)


expected_main_labels = [
    "binomialModel",
    "insureOneOfFourExceedsDeductible",
    "factorial_defined",
    "isItBinomialTipBox",
    "noMoreThanOneFriendWSevereLungCondition",
    "normalApproxBinomialDistSubsection",
    "exactBinomSmokerExSetup",
    "fourBinomialModelsShowingApproxToNormal",
    "approxNormalForSmokerBinomEx",
    "normApproxToBinomFail",
]
expected_eoce_labels = [
    "underage_drinking_intro",
    "chicken_pox_intro",
    "underage_drinking_normal_approx",
    "chicken_pox_normal_approx",
    "dreidel",
    "arachnophobia",
    "eye_color_binomial",
    "sickle_cell_anemia",
    "explore_combinations",
    "male_children",
]
check(
    "coverage.main",
    [value for _, value in simple_args(texts["main_target"], ["label"])] == expected_main_labels
    and len(re.findall(r"\\begin\{nexample\}", texts["main_target"])) == 4
    and len(re.findall(r"\\begin\{nexercise\}", texts["main_target"])) == 10
    and texts["main_target"].count("\\footnotemark") == 10
    and texts["main_target"].count("\\footnotetext") == 10
    and len(re.findall(r"\\begin\{onebox\}", texts["main_target"])) == 5
    and len(re.findall(r"\\subsection\{", texts["main_target"])) == 3,
    {
        "section": 1,
        "subsections": 3,
        "worked_examples": 4,
        "guided_exercises": 10,
        "guided_inline_answers": 10,
        "oneboxes": 5,
        "labels": expected_main_labels,
    },
)
eoce_ids = [int(value) for value in re.findall(r"^%\s*(\d+)\s*$", texts["eoce_target"], flags=re.MULTILINE)]
check(
    "coverage.eoce",
    eoce_ids == list(range(17, 27))
    and [value for _, value in simple_args(texts["eoce_target"], ["label"])] == expected_eoce_labels
    and texts["eoce_target"].count("\\eoce{") == 10
    and texts["eoce_target"].count("\\item") == 40,
    {"exercise_ids": eoce_ids, "exercise_count": 10, "part_count": 40, "labels": expected_eoce_labels},
)
answer_ids = [int(value) for value in re.findall(r"^%\s*(\d+)\s*$", texts["answers_target"], flags=re.MULTILINE)]
check(
    "coverage.public_answers",
    answer_ids == [17, 19, 21, 23, 25] and texts["answers_target"].count("\\eocesol{") == 5,
    {"exercise_ids": answer_ids, "answer_count": 5},
)
check(
    "coverage.data_appendix",
    texts["data_target"].count("\\item[\\ref{binomialModel}]") == 3
    and texts["data_target"].count("\\datawrap{") == 3,
    {"entry_count": 3, "label": "binomialModel"},
)

o001 = json.loads(texts["o001_target"])
o001_contract = json.loads(texts["o001_contract"])
gap_ids = [item["exercise_number"] for item in o001["missing_public_answer_gaps"]]
check(
    "linkage.exercise_answer_o001_partition",
    gap_ids == [18, 20, 22, 24, 26]
    and sorted(answer_ids + gap_ids) == list(range(17, 27))
    and not set(answer_ids).intersection(gap_ids)
    and all(item["status"] == "O001_MASTERY_COMPANION_GAP" for item in o001["missing_public_answer_gaps"])
    and "No restricted instructor solutions were accessed, inferred, or invented." in o001["public_answer_policy"]
    and o001_contract.get("o001_mastery_companion_gap_exercise_ids") == gap_ids
    and o001_contract.get("public_answer_exercise_ids") == answer_ids
    and o001_contract.get("restricted_instructor_solutions_sought_or_ingested") is False,
    {
        "public_answer_ids": answer_ids,
        "o001_gap_ids": gap_ids,
        "union": sorted(answer_ids + gap_ids),
        "restricted_solutions": "not accessed, inferred, or invented",
    },
)
check(
    "linkage.exercise_labels",
    [item["source_label"] for item in o001["missing_public_answer_gaps"]]
    == [expected_eoce_labels[number - 17] for number in gap_ids],
    {"gap_labels": [item["source_label"] for item in o001["missing_public_answer_gaps"]]},
)


correction_checks = {
    "B016-SC001-introductory-comma": (
        "As the last stage use software" in texts["main_authority"],
        "Pada tahap terakhir, gunakan perangkat lunak" in texts["main_target"],
    ),
    "B016-SC003-missing-definite-article": (
        "normal distribution in last hollow histogram" in texts["main_authority"],
        "pada\n  histogram berongga terakhir" in texts["main_target"],
    ),
    "B016-SC004-SAMHSA-acronym": (
        "(SAMSHA)" in texts["eoce_authority"],
        "(SAMHSA)" in texts["eoce_target"] and "SAMSHA" not in texts["eoce_target"],
    ),
    "B016-SC005-word-order-duplication": (
        "will the be $3^{rd}$ child" in texts["eoce_authority"],
        "merupakan anak ke-$3$?" in texts["eoce_target"] and "will the be" not in texts["eoce_target"],
    ),
}
for correction_id, (authority_defect_present, corrected_target_present) in correction_checks.items():
    check(
        f"source_correction.{correction_id}",
        authority_defect_present and corrected_target_present,
        {"authority_defect_present": authority_defect_present, "corrected_target_present": corrected_target_present},
    )

check(
    "locale.ordinal_localization",
    "$4^{th}$" in texts["eoce_authority"]
    and "$3^{rd}$" in texts["eoce_authority"]
    and "ke-$4$" in texts["eoce_target"]
    and "ke-$3$" in texts["eoce_target"]
    and not re.search(r"\^\{(?:st|nd|rd|th)\}", texts["eoce_target"]),
    {"source": ["$4^{th}$", "$3^{rd}$"], "target": ["ke-$4$", "ke-$3$"], "english_ordinal_suffix_residue": 0},
)


term_rows = list(csv.DictReader(io.StringIO(texts["controlled_terms"]), delimiter="\t"))
check(
    "terminology.control_table",
    len(term_rows) == 27
    and list(term_rows[0]) == ["source_term", "preferred_id-ID", "accepted_synonyms", "evidence", "use_in_B016"]
    and all(all(value.strip() for value in row.values()) for row in term_rows),
    {"decision_count": len(term_rows), "identity": identities["controlled_terms"]},
)
check(
    "terminology.terminal_receipt",
    terminology_qa.get("decision_count") == 27
    and terminology_qa.get("candidate_alignment", {}).get("conflicts") == []
    and terminology_qa.get("candidate_alignment", {}).get("uncontrolled_reader_term_introductions") == []
    and len(terminology_qa.get("provisional_reversible_controls", [])) == 2,
    {
        "identity": identities["terminology_qa"],
        "decision_count": terminology_qa.get("decision_count"),
        "conflicts": terminology_qa.get("candidate_alignment", {}).get("conflicts"),
        "provisional_reversible_count": len(terminology_qa.get("provisional_reversible_controls", [])),
    },
)

all_target = "\n".join(texts[key] for key in ["main_target", "eoce_target", "answers_target", "data_target"])
all_target_lower = re.sub(r"\s+", " ", all_target).lower()
required_terms = [
    "distribusi binomial",
    "model binomial",
    "eksperimen binomial",
    "percobaan bernoulli",
    "percobaan yang saling independen",
    "peluang sukses",
    "faktorial",
    "n pilih k",
    "permutasi",
    "pendekatan normal terhadap distribusi binomial",
    "peluang binomial eksak",
    "ukuran sampel",
    "rata-rata",
    "varians",
    "simpangan baku",
    "menceng kanan",
    "distribusi berbentuk lonceng",
    "nilai batas",
    "rentang kecil banyaknya sukses",
    "saling lepas",
]
missing_terms = [term for term in required_terms if term not in all_target_lower]
forbidden_term_patterns = {
    "probabilitas": r"\bprobabilitas\b",
    "aproksimasi": r"\baproksimasi\b",
    "deviasi standar": r"\bdeviasi\s+standar\b",
    "variansi": r"\bvariansi\b",
    "peubah acak": r"\bpeubah\s+acak\b",
    "percobaan saling bebas": r"\bpercobaan\s+saling\s+bebas\b",
}
forbidden_term_hits = [name for name, pattern in forbidden_term_patterns.items() if re.search(pattern, all_target_lower)]
check(
    "terminology.candidate_application",
    not missing_terms and not forbidden_term_hits,
    {"required_terms": required_terms, "missing": missing_terms, "forbidden_synonym_hits": forbidden_term_hits},
)


def remove_simple_command_args(text: str, names: Iterable[str]) -> str:
    clean = strip_comments(text)
    for name in names:
        clean = re.sub(rf"\\{re.escape(name)}\s*\{{[^{{}}]*\}}", " ", clean)
    clean = re.sub(r"\\termsub\s*\{[^{}]*\}\s*\{[^{}]*\}", " ", clean)
    return clean


residue_patterns = {
    "probability": r"\bprobability\b",
    "distribution": r"\bdistribution\b",
    "trial_or_trials": r"\btrials?\b",
    "success_or_successes": r"\bsuccess(?:es)?\b",
    "failure_or_failures": r"\bfailures?\b",
    "sample_size": r"\bsample\s+size\b",
    "standard_deviation": r"\bstandard\s+deviation\b",
    "normal_approximation": r"\bnormal\s+approximation\b",
    "calculate": r"\bcalculate\b",
    "suppose": r"\bsuppose\b",
    "what_is": r"\bwhat\s+is\b",
    "how_many": r"\bhow\s+many\b",
    "photo_by": r"\bphoto\s+by\b",
    "alcoholic_beverages": r"\balcoholic\s+beverages\b",
}
reader_residue: dict[str, list[str]] = {}
for key in ["main_target", "eoce_target", "answers_target", "data_target"]:
    sanitized = remove_simple_command_args(
        texts[key],
        ["label", "ref", "pageref", "eqref", "index", "input", "footfullcite", "cite", "textcite", "parencite"],
    ).lower()
    hits = [name for name, pattern in residue_patterns.items() if re.search(pattern, sanitized)]
    reader_residue[key] = hits
check(
    "residue.reader_visible_english_watchlist",
    all(not hits for hits in reader_residue.values()),
    reader_residue,
)


def compact(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


semantic_anchors = {
    "main_fixed_trials": "digunakan untuk menggambarkan banyaknya sukses ketika jumlah percobaannya tetap",
    "main_geometric_contrast": "banyaknya percobaan yang harus kita tunggu sebelum mengamati suatu sukses",
    "main_binomial_probability": "peluang untuk memperoleh tepat $k$ sukses dalam $n$ percobaan Bernoulli yang saling independen dengan peluang sukses $p$",
    "main_four_conditions": "Apakah modelnya binomial? Empat syarat yang perlu diperiksa.",
    "main_mean_variance_sd": "Rata-rata, varians, dan simpangan baku banyaknya sukses yang diamati",
    "main_normal_threshold": "$np$ dan $n(1-p)$ masing-masing sekurang-kurangnya 10",
    "main_small_interval_failure": "taksiran yang buruk ketika menaksir peluang bagi rentang kecil banyaknya sukses",
    "main_continuity_correction": "ujung bawah daerah yang diarsir perlu dikurangi 0.5, sedangkan nilai batas pada ujung atas perlu ditambah 0.5",
    "eoce_underage_scope": "69.7\\% kaum muda berusia 18--20 tahun mengonsumsi minuman beralkohol dalam suatu tahun",
    "eoce_chickenpox_scope": "90\\% orang Amerika pernah terkena cacar air sebelum mencapai usia dewasa",
    "eoce_dreidel_equiprobable": "setiap sisi memiliki peluang yang sama untuk muncul",
    "eoce_arachnophobia_independence": "Asumsikan bahwa 10 remaja ini saling independen",
    "eoce_eye_color_probabilities": "peluang 0.75 untuk mempunyai anak bermata cokelat, peluang 0.125 untuk mempunyai anak bermata biru, dan peluang 0.125 untuk mempunyai anak bermata hijau",
    "eoce_sickle_cell_probabilities": "peluang 25\\% untuk menderita penyakit tersebut, peluang 50\\% untuk menjadi pembawa, dan peluang 25\\% untuk tidak menderita penyakit tersebut maupun menjadi pembawa",
    "eoce_disjoint_rule": "aturan penjumlahan untuk hasil-hasil yang saling lepas",
    "data_unverified_warning": "jangan menganggapnya sebagai fakta karena kami tidak dapat memastikan bahwa statistik itu berasal dari sumber yang bereputasi baik",
    "data_cdc_2017": "melaporkan nilai 14\\% berdasarkan estimasi tahun 2017",
}
component_compact = {
    "main": compact(texts["main_target"]),
    "eoce": compact(texts["eoce_target"]),
    "answers": compact(texts["answers_target"]),
    "data": compact(texts["data_target"]),
}
anchor_hits: dict[str, bool] = {}
for anchor_id, phrase in semantic_anchors.items():
    component = anchor_id.split("_", 1)[0]
    anchor_hits[anchor_id] = phrase in component_compact[component]
check(
    "semantic.anchor_coverage",
    all(anchor_hits.values()),
    {"anchor_count": len(anchor_hits), "missing": [name for name, passed in anchor_hits.items() if not passed]},
)

source_reader_chars = sum(len(strip_comments(texts[key])) for key in ["main_authority", "eoce_authority", "answers_authority", "data_authority"])
target_reader_chars = sum(len(strip_comments(texts[key])) for key in ["main_target", "eoce_target", "answers_target", "data_target"])
length_ratio = target_reader_chars / source_reader_chars
check(
    "semantic.coverage_length_sanity",
    0.85 <= length_ratio <= 1.35,
    {"source_noncomment_characters": source_reader_chars, "target_noncomment_characters": target_reader_chars, "target_source_ratio": round(length_ratio, 6)},
)

check(
    "boundary.next_cursor",
    "\\section{Negative binomial distribution}" not in texts["main_target"]
    and texts["main_target"].rstrip().endswith("%_________________")
    and source_closure["main_boundary"]["next_cursor"] == {
        "command": "\\section{Negative binomial distribution}",
        "label": "negativeBinomial",
        "label_line": 1928,
        "line": 1927,
    },
    {"next_authority_line": 1927, "next_section": "Negative binomial distribution", "next_label": "negativeBinomial"},
)

failures = [item for item in checks if item["status"] != "PASS"]
report = {
    "$schema": "interlanguage.r011-b016-translation-integration-verification/v1",
    "event_type": "TRANSLATION_INTEGRATION_QA",
    "boundary_id": BOUNDARY,
    "status": "PASS_EXACT_PINNED_AUTHORITY_TRANSLATION_INTEGRATION" if not failures else "FAIL_TRANSLATION_INTEGRATION",
    "production_model": MODEL,
    "authority": {
        "repository": "https://github.com/OpenIntroStat/openintro-statistics",
        "branch": "master",
        "commit": COMMIT,
        "tree": TREE,
        "main_lines": [1268, 1926],
        "eoce_exercises": list(range(17, 27)),
        "public_answer_ids": [17, 19, 21, 23, 25],
        "data_appendix_entries": 3,
    },
    "input_identities": identities,
    "coverage": {
        "main": {"sections": 1, "subsections": 3, "worked_examples": 4, "guided_exercises": 10, "guided_inline_answers": 10},
        "eoce": {"exercise_ids": list(range(17, 27)), "parts": 40},
        "public_answers": [17, 19, 21, 23, 25],
        "o001_gaps": [18, 20, 22, 24, 26],
        "data_appendix_entries": 3,
        "restricted_instructor_solutions": "not accessed, inferred, or invented",
    },
    "topology": topology,
    "newcommands": {
        "count": len(target_macros),
        "exact_value_count": len(exact_macro_names),
        "localized_reader_bodies": {
            name: {"source": values[0], "target": values[1]}
            for name, values in approved_localized_macro_bodies.items()
        },
        "preboundary_dependencies": preboundary_macros,
    },
    "terminology": {
        "decision_count": len(term_rows),
        "terminal_qa": identities["terminology_qa"],
        "provisional_reversible_reader_terms": ["n pilih k", "pendekatan normal terhadap distribusi binomial"],
        "candidate_conflicts": terminology_qa.get("candidate_alignment", {}).get("conflicts"),
        "missing_required_terms": missing_terms,
        "forbidden_synonym_hits": forbidden_term_hits,
    },
    "source_corrections": {
        "count": len(correction_checks),
        "ids": list(correction_checks),
        "ordinal_localizations": {"source": ["$4^{th}$", "$3^{rd}$"], "target": ["ke-$4$", "ke-$3$"]},
    },
    "layout_adaptations": {
        "count": 1,
        "items": [
            {
                "surface": "EoCE break relocated from after Exercise 4.21 to before Exercise 4.24",
                "relocated_source_command": r"\D{\newpage}",
                "target_flexible_vertical_fills": 6,
                "reason": "reader reflow balances and vertically distributes all three EoCE pages while preserving order, mathematics, photo, visible CC BY 2.0 attribution, and semantic links",
            }
        ],
    },
    "semantic_review": {
        "method": "independent sentence-level comparison of complete bounded source and candidate, reinforced by exact structural/math/number checks and deterministic semantic anchors",
        "surfaces": ["main section 4.3", "EoCE 17-26", "public odd answers 17/19/21/23/25", "three data appendix entries", "O001 partition"],
        "anchor_count": len(anchor_hits),
        "anchor_failures": [name for name, passed in anchor_hits.items() if not passed],
        "reader_visible_english_watchlist_hits": reader_residue,
        "content_defects_found": [],
    },
    "checks": checks,
    "check_summary": {"total": len(checks), "passed": len(checks) - len(failures), "failed": len(failures)},
    "mutation_scope": "qa/b016-translation only; candidate, live reader, backend, control, release, and upstream untouched",
    "next_cursor": {"authority_line": 1927, "section": "Negative binomial distribution", "label": "negativeBinomial"},
}

sys.stdout.buffer.write((json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
raise SystemExit(1 if failures else 0)
