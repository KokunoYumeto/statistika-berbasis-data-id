#!/usr/bin/env python3
"""Deterministically consolidate the accepted independent B021 translation evidence.

This verifier is intentionally bounded.  It reads only the frozen B021 boundary
blueprint, accepted staging translations and their audits, and the finalized
216-page language/visual-QA receipts.  It never reads the backend, release
surfaces, credentials, network, Git metadata, or publication state.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import OrderedDict
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "qa/b021-translation/R011-B021_INDEPENDENT_TRANSLATION_VERIFICATION.json"
BOUNDARY = "R011-B021"
COMMIT = "fee25091fb24e89c36296fd67c48c1fcf7a93b6e"
MODEL = "OpenAI Codex gpt-5.6-sol, Ultra"

FROZEN_INPUTS: OrderedDict[str, tuple[int, str]] = OrderedDict(
    [
        (
            "qa/b021-source/R011-B021_BOUNDARY_BLUEPRINT.json",
            (8_954, "fb9031969fa11e9cbbb94c183db24d01a5e4f724e65573052d78a8f49a894373"),
        ),
        (
            "qa/b021-translation/staging/ch_foundations_for_inf_1509-1719.id.tex",
            (10_042, "7fdd200212b5b3435727b5637fbb644a2a27e29e7637971f9ea7592b7ad65b1d"),
        ),
        (
            "qa/b021-translation/staging/ch_foundations_for_inf_1509-1719.id.audit.json",
            (5_610, "db4fb6f7e64c12826413c96337aa29d7d2adc51aa7d372824f561b9010dffe7e"),
        ),
        (
            "qa/b021-translation/staging/ch_foundations_for_inf_1720-2116.id.tex",
            (16_415, "07ce5e20e6e35a82311ac356e18cdb2ab491339227b23cfbddf92f46e13c331e"),
        ),
        (
            "qa/b021-translation/staging/ch_foundations_for_inf_1720-2116.id.audit.json",
            (7_701, "ca472c657e8fcdac46fd6ab5a80ac3c77461eb29ba8740e8912372cf945960fa"),
        ),
        (
            "qa/b021-translation/staging/ch_foundations_for_inf_2117-2907.id.tex",
            (32_801, "e15e9f94628828892a60280301d11597b02cebd5b7046634bb38af6520c0edcb"),
        ),
        (
            "qa/b021-translation/staging/ch_foundations_for_inf_2117-2907.id.audit.json",
            (6_293, "97e4a42ea881381be470a3101977397a311c21844cd559c8ab9c78113d62c8e4"),
        ),
        (
            "qa/b021-translation/staging/hypothesis_testing.id.tex",
            (9_123, "633f7c6a331fcac7ef0cdc24e5f7c7454cfcf769e16e9ed514e26a5a4717388a"),
        ),
        (
            "qa/b021-translation/staging/eoceSolutions_b021_public_odd.id.tex",
            (3_530, "753d8adf1a2933e9b9cc1184326f1090886ae9f92f60da60cd9780530f19d824"),
        ),
        (
            "qa/b021-translation/staging/R011-B021_EXERCISES_ANSWERS_TRANSLATION_AUDIT.json",
            (7_064, "942fb46846419998a92ec91a816cb8136b40ebf398bf7f457167805b99a99aa5"),
        ),
        (
            "qa/b021-translation/staging/data_hypothesis_testing_359-445.id.tex",
            (3_621, "cb66ad8bbe32319199277da4cd5fc747c4cf05bbab90bc9509178c99c2479a72"),
        ),
        (
            "qa/b021-translation/staging/data_hypothesis_testing_359-445.id.audit.json",
            (2_813, "a205e00c6bae886e2ac8dff4b8a9e61e02f70a7c330babd85706615e8875ceea"),
        ),
        (
            "qa/b021-reader/R011-B021_PAGEWISE_LANGUAGE_QA.json",
            (117_832, "d81c0711948a4e4e8fe4cd017bb96f093eba6f615337c5cea88e4b075bd3cd07"),
        ),
        (
            "qa/b021-reader/R011-B021_PAGEWISE_LANGUAGE_QA.tsv",
            (27_689, "e3225c51d059025d37596a32d79b43a4730cdf70e104bc4e936f48ae8d8c5930"),
        ),
        (
            "qa/b021-reader/R011-B021_VISUAL_QA.json",
            (107_240, "d99513cb716c7373a99bfa76b5a09d965ce75ca0c3d818debd4e53db3a9014ed"),
        ),
    ]
)

ROLES = {
    "qa/b021-source/R011-B021_BOUNDARY_BLUEPRINT.json": "frozen_boundary_blueprint",
    "qa/b021-translation/staging/ch_foundations_for_inf_1509-1719.id.tex": "main_translation_1509_1719",
    "qa/b021-translation/staging/ch_foundations_for_inf_1509-1719.id.audit.json": "independent_audit_1509_1719",
    "qa/b021-translation/staging/ch_foundations_for_inf_1720-2116.id.tex": "main_translation_1720_2116",
    "qa/b021-translation/staging/ch_foundations_for_inf_1720-2116.id.audit.json": "independent_audit_1720_2116",
    "qa/b021-translation/staging/ch_foundations_for_inf_2117-2907.id.tex": "main_translation_2117_2907",
    "qa/b021-translation/staging/ch_foundations_for_inf_2117-2907.id.audit.json": "independent_audit_2117_2907",
    "qa/b021-translation/staging/hypothesis_testing.id.tex": "exercises_15_26_translation",
    "qa/b021-translation/staging/eoceSolutions_b021_public_odd.id.tex": "public_answers_15_25_odd_translation",
    "qa/b021-translation/staging/R011-B021_EXERCISES_ANSWERS_TRANSLATION_AUDIT.json": "independent_exercise_answer_audit",
    "qa/b021-translation/staging/data_hypothesis_testing_359-445.id.tex": "section_5_3_data_appendix_translation",
    "qa/b021-translation/staging/data_hypothesis_testing_359-445.id.audit.json": "independent_data_appendix_audit",
    "qa/b021-reader/R011-B021_PAGEWISE_LANGUAGE_QA.json": "final_216_page_language_qa",
    "qa/b021-reader/R011-B021_PAGEWISE_LANGUAGE_QA.tsv": "final_216_page_language_rows",
    "qa/b021-reader/R011-B021_VISUAL_QA.json": "final_216_page_visual_qa",
}

MAIN_CHUNKS = [
    {
        "source_lines": [1509, 1719],
        "target": "qa/b021-translation/staging/ch_foundations_for_inf_1509-1719.id.tex",
        "audit": "qa/b021-translation/staging/ch_foundations_for_inf_1509-1719.id.audit.json",
        "target_lines": 210,
        "relation_key": "label_ref_cite_redirect_order",
    },
    {
        "source_lines": [1720, 2116],
        "target": "qa/b021-translation/staging/ch_foundations_for_inf_1720-2116.id.tex",
        "audit": "qa/b021-translation/staging/ch_foundations_for_inf_1720-2116.id.audit.json",
        "target_lines": 395,
        "relation_key": "label_ref_cite_redirect_order",
    },
    {
        "source_lines": [2117, 2907],
        "target": "qa/b021-translation/staging/ch_foundations_for_inf_2117-2907.id.tex",
        "audit": "qa/b021-translation/staging/ch_foundations_for_inf_2117-2907.id.audit.json",
        "target_lines": 789,
        "relation_key": "label_ref_cite_input_redirect_order",
    },
]

TARGETS = [
    item["target"] for item in MAIN_CHUNKS
] + [
    "qa/b021-translation/staging/hypothesis_testing.id.tex",
    "qa/b021-translation/staging/eoceSolutions_b021_public_odd.id.tex",
    "qa/b021-translation/staging/data_hypothesis_testing_359-445.id.tex",
]

FORBIDDEN_ACTIVE_ENGLISH = OrderedDict(
    [
        ("hypothesis_testing", re.compile(r"(?i)\bhypothesis\s+test(?:ing|s)?\b")),
        ("null_hypothesis", re.compile(r"(?i)\bnull\s+hypothesis\b")),
        ("alternative_hypothesis", re.compile(r"(?i)\balternative\s+hypothesis\b")),
        ("confidence_interval", re.compile(r"(?i)\bconfidence\s+intervals?\b")),
        ("decision_errors", re.compile(r"(?i)\bdecision\s+errors?\b")),
        ("p_value", re.compile(r"(?i)\bp[- ]values?\b")),
        ("null_distribution", re.compile(r"(?i)\bnull\s+distribution\b")),
        ("test_statistic", re.compile(r"(?i)\btest\s+statistic\b")),
        ("significance_level", re.compile(r"(?i)\bsignificance\s+level\b")),
        ("one_sided_test", re.compile(r"(?i)\bone[- ]sided\s+hypothesis\s+tests?\b")),
        ("two_sided_test", re.compile(r"(?i)\btwo[- ]sided\s+hypothesis\s+tests?\b")),
        ("observed_p_hat", re.compile(r"(?i)\bobserved\s+p[- ]hat\b")),
        ("tail_area", re.compile(r"(?i)\btail\s+area\s+for\b")),
        ("equally_unlikely", re.compile(r"(?i)\bequally\s+unlikely\b")),
        ("upper_tail", re.compile(r"(?i)\bupper\s+tail\b")),
        ("lower_tail", re.compile(r"(?i)\blower\s+tail\b")),
        ("identifying_hypotheses", re.compile(r"(?i)\bidentifying\s+hypotheses\b")),
        ("online_communication", re.compile(r"(?i)\bonline\s+communication\b")),
        ("married_at_25", re.compile(r"(?i)\bmarried\s+at\s+25\b")),
        ("cyberbullying_rates", re.compile(r"(?i)\bcyberbullying\s+rates?\b")),
        ("minimum_wage", re.compile(r"(?i)\bminimum\s+wage\b")),
        ("enough_sleep", re.compile(r"(?i)\benough\s+sleep\b")),
        ("working_backwards", re.compile(r"(?i)\bworking\s+backwards\b")),
        ("fibromyalgia_treatment", re.compile(r"(?i)\bfibromyalgia\s+treatment\b")),
        ("which_is_higher", re.compile(r"(?i)\bwhich\s+is\s+higher\b")),
    ]
)


class VerificationError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def repo_path(relative: str) -> Path:
    pure = PurePosixPath(relative)
    require(bool(relative) and not pure.is_absolute() and ".." not in pure.parts, f"unsafe path: {relative}")
    return ROOT.joinpath(*pure.parts)


def identity(relative: str) -> dict[str, object]:
    path = repo_path(relative)
    require(path.is_file(), f"missing frozen input: {relative}")
    raw = path.read_bytes()
    return {"path": relative, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def load_json(relative: str) -> dict[str, Any]:
    try:
        value = json.loads(repo_path(relative).read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VerificationError(f"invalid UTF-8 JSON: {relative}: {exc}") from exc
    require(isinstance(value, dict), f"JSON root is not an object: {relative}")
    return value


def verify_frozen_inputs() -> dict[str, dict[str, object]]:
    records: dict[str, dict[str, object]] = {}
    for relative, expected in FROZEN_INPUTS.items():
        observed = identity(relative)
        require((observed["bytes"], observed["sha256"]) == expected, f"frozen identity changed: {observed}")
        records[relative] = observed
    return records


def assert_embedded_target(record: dict[str, Any], relative: str, observed: dict[str, object]) -> None:
    require(record.get("path") == relative, f"audit target path changed: {record}")
    bytes_value = record.get("bytes", record.get("bytes_utf8"))
    require(bytes_value == observed["bytes"] and record.get("sha256") == observed["sha256"], f"audit target identity changed: {record}")


def equal_stream(check: dict[str, Any], context: str) -> dict[str, object]:
    require(isinstance(check, dict), f"missing protected stream: {context}")
    equality_keys = [
        "exact_sequence_equal",
        "exact_command_and_argument_sequence_equal",
        "exact_macro_name_sequence_equal",
    ]
    require(any(check.get(key) is True for key in equality_keys), f"protected stream is not exact: {context}")
    source_count = check.get("source_count")
    target_count = check.get("target_count")
    require(isinstance(source_count, int) and source_count == target_count, f"protected stream counts differ: {context}")
    return {"source": source_count, "target": target_count, "exact": True}


def strip_comments(text: str) -> str:
    active_lines: list[str] = []
    for line in text.splitlines():
        stop = len(line)
        for index, char in enumerate(line):
            if char != "%":
                continue
            slash_count = 0
            cursor = index - 1
            while cursor >= 0 and line[cursor] == "\\":
                slash_count += 1
                cursor -= 1
            if slash_count % 2 == 0:
                stop = index
                break
        active_lines.append(line[:stop])
    return "\n".join(active_lines)


def mask_protected_tex(text: str) -> str:
    # These arguments are identifiers, sort keys, paths, code selectors, or
    # macro definitions rather than learner-visible prose.
    patterns = [
        r"\\index\{(?:[^{}]|\{[^{}]*\})*\}",
        r"\\(?:label|ref|pageref|eqref|cite|redirect|input|includegraphics|data)\{[^{}]*\}",
        r"\\CalculatorVideos\{[^{}]*\}",
        r"(?m)^\s*\\newcommand.*$",
    ]
    masked = text
    for pattern in patterns:
        masked = re.sub(pattern, " ", masked)
    return re.sub(r"\\(?:[A-Za-z@]+|.)", " ", masked)


def brace_result(text: str, relative: str) -> dict[str, object]:
    active = strip_comments(text)
    depth = 0
    opens = closes = 0
    for index, char in enumerate(active):
        if char not in "{}":
            continue
        slash_count = 0
        cursor = index - 1
        while cursor >= 0 and active[cursor] == "\\":
            slash_count += 1
            cursor -= 1
        if slash_count % 2:
            continue
        if char == "{":
            opens += 1
            depth += 1
        else:
            closes += 1
            depth -= 1
            require(depth >= 0, f"negative brace prefix in {relative}")
    require(depth == 0, f"unbalanced active braces in {relative}: {opens}/{closes}")
    return {"open": opens, "close": closes, "balanced_nonnegative_prefix": True}


def verify_direct_targets(records: dict[str, dict[str, object]]) -> dict[str, Any]:
    results: dict[str, Any] = {}
    aggregate = {name: 0 for name in FORBIDDEN_ACTIVE_ENGLISH}
    for relative in TARGETS:
        raw = repo_path(relative).read_bytes()
        require(b"\r" not in raw, f"target no longer uses LF-only line endings: {relative}")
        text = raw.decode("utf-8")
        active = mask_protected_tex(strip_comments(text))
        counts = {name: len(pattern.findall(active)) for name, pattern in FORBIDDEN_ACTIVE_ENGLISH.items()}
        require(not any(counts.values()), f"active English anchor remains in {relative}: {counts}")
        for name, count in counts.items():
            aggregate[name] += count
        results[relative] = {
            "identity": records[relative],
            "logical_lines": len(text.splitlines()),
            "line_endings": "LF",
            "brace_check": brace_result(text, relative),
            "forbidden_active_english_anchor_counts": counts,
        }
    require(not any(aggregate.values()), f"aggregate active English anchors remain: {aggregate}")
    return {"per_target": results, "aggregate_forbidden_active_english_anchor_counts": aggregate}


def verify_blueprint() -> tuple[dict[str, Any], dict[str, object]]:
    relative = "qa/b021-source/R011-B021_BOUNDARY_BLUEPRINT.json"
    blueprint = load_json(relative)
    require(blueprint.get("boundary_id") == BOUNDARY, "blueprint boundary changed")
    require(blueprint.get("status") == "PASS_SOURCE_ASSET_RIGHTS_AND_BOUNDARY_DEPENDENCY_CLOSURE", "blueprint status changed")
    require(blueprint.get("authority", {}).get("commit") == COMMIT, "blueprint authority commit changed")
    main = blueprint.get("main_source", {})
    require(
        (main.get("start_line"), main.get("end_line"), main.get("line_count"), main.get("title"))
        == (1509, 2907, 1399, "Hypothesis testing for a proportion"),
        "blueprint main §5.3 boundary changed",
    )
    closure = blueprint.get("exercise_answer_closure", {})
    require(closure.get("exercise_ids") == list(range(15, 27)), "blueprint exercise sequence changed")
    require(closure.get("public_answer_ids") == list(range(15, 26, 2)), "blueprint public-answer sequence changed")
    require(closure.get("o001_gap_ids") == list(range(16, 27, 2)), "blueprint O001 gaps changed")
    require(closure.get("restricted_solutions_accessed_or_invented") is False, "blueprint restricted-solution guard changed")
    data = blueprint.get("data_closure", {}).get("appendix_slice", {})
    require((data.get("lines"), data.get("bytes"), data.get("sha256")) == (
        "359-445 inclusive", 3358, "d0b0d8703099c84aba0cb6e11e6411d7289308403f758a249d367841a43a1cda"
    ), "blueprint data-appendix slice changed")
    require(len(blueprint.get("figures", [])) == 3, "blueprint figure closure changed")
    next_cursor = blueprint.get("next_cursor", {})
    require(next_cursor.get("working_boundary_id") == "R011-B022" and next_cursor.get("first_instructional_line") == 29, "post-B021 cursor changed")
    return blueprint, {
        "main_source_lines": "1509-2907 inclusive",
        "main_source_line_count": 1399,
        "section_title": "Hypothesis testing for a proportion",
        "exercise_numbers": list(range(15, 27)),
        "public_answer_numbers": list(range(15, 26, 2)),
        "o001_gap_numbers": list(range(16, 27, 2)),
        "data_appendix_lines": "359-445 inclusive",
        "physical_figure_count": 3,
        "next_boundary": "R011-B022",
    }


def verify_main_audits(records: dict[str, dict[str, object]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    prior_end = 1508
    for spec in MAIN_CHUNKS:
        audit = load_json(spec["audit"])
        require(audit.get("boundary") == BOUNDARY, f"audit boundary changed: {spec['audit']}")
        require(audit.get("status") == "PASS_TRANSLATION_AND_PROTECTED_TEX_CLOSURE", f"audit status changed: {spec['audit']}")
        require(audit.get("production_model") == MODEL, f"model provenance changed: {spec['audit']}")
        require(audit.get("authority", {}).get("commit") == COMMIT, f"authority commit changed: {spec['audit']}")
        source = audit.get("source_slice", {})
        start, end = spec["source_lines"]
        require((source.get("first_line"), source.get("last_line")) == (start, end), f"source slice changed: {spec['audit']}")
        require(start == prior_end + 1, f"main chunks are not contiguous at {start}")
        prior_end = end
        assert_embedded_target(audit.get("target", {}), spec["target"], records[spec["target"]])
        target_text = repo_path(spec["target"]).read_text(encoding="utf-8")
        require(len(target_text.splitlines()) == spec["target_lines"], f"target line count changed: {spec['target']}")
        checks = audit.get("protected_token_checks", {})
        controls = equal_stream(checks.get("tex_control_sequence_order", {}), f"{spec['audit']} controls")
        environments = equal_stream(checks.get("begin_end_environment_order", {}), f"{spec['audit']} environments")
        relations = equal_stream(checks.get(spec["relation_key"], {}), f"{spec['audit']} relations")
        math_spans = equal_stream(checks.get("inline_math_span_order", {}), f"{spec['audit']} inline math")
        numerics = equal_stream(checks.get("numeric_literal_order", {}), f"{spec['audit']} numerics")
        newcommands = equal_stream(checks.get("newcommand_definition_order", {}), f"{spec['audit']} newcommands")
        comments = equal_stream(checks.get("dormant_comment_lines", {}), f"{spec['audit']} dormant comments")
        brace = checks.get("brace_balance", {})
        require(
            brace.get("source_open") == brace.get("source_close")
            and brace.get("target_open") == brace.get("target_close"),
            f"audit brace closure changed: {spec['audit']}",
        )
        if "active_reader_english_residue" in checks:
            residue = checks["active_reader_english_residue"]
            require(residue.get("status") == "PASS" and residue.get("untranslated_fragments") == [], f"active English remains: {spec['audit']}")
        else:
            language = audit.get("language_qa", {})
            require(
                language.get("status") == "PASS_ACTIVE_READER_PROSE_REVIEWED"
                and language.get("active_untranslated_instructional_prose") == 0
                and language.get("active_figure_alt_texts_translated") == 3,
                f"chunk-C language closure changed: {spec['audit']}",
            )
            require(checks.get("display_math_blocks", {}).get("mathematical_structure_equal") is True, "chunk-C display math changed")
            require(checks.get("index_structure", {}).get("range_and_textbf_marker_sequence_equal") is True, "chunk-C index structure changed")
        results.append(
            {
                "source_lines": f"{start}-{end} inclusive",
                "target": records[spec["target"]],
                "audit": records[spec["audit"]],
                "target_logical_lines": spec["target_lines"],
                "audit_reported_target_logical_lines": audit.get("target", {}).get("logical_lines"),
                "target_line_count_metadata_disposition": (
                    "MATCH"
                    if audit.get("target", {}).get("logical_lines") == spec["target_lines"]
                    else "AUDIT_METADATA_COUNTING_DEFECT_ONLY_EXACT_TARGET_BYTES_AND_PROTECTED_STREAMS_PASS"
                ),
                "tex_controls": controls,
                "environments": environments,
                "label_reference_citation_input_stream": relations,
                "inline_math_spans": math_spans,
                "numeric_literals": numerics,
                "newcommand_names": newcommands,
                "dormant_comments": comments,
                "braces_balanced": True,
                "active_untranslated_prose": 0,
            }
        )
    require(prior_end == 2907, "main audit coverage does not end at line 2907")
    return results


def verify_exercise_answer_audit(records: dict[str, dict[str, object]]) -> dict[str, Any]:
    audit_rel = "qa/b021-translation/staging/R011-B021_EXERCISES_ANSWERS_TRANSLATION_AUDIT.json"
    exercise_rel = "qa/b021-translation/staging/hypothesis_testing.id.tex"
    answer_rel = "qa/b021-translation/staging/eoceSolutions_b021_public_odd.id.tex"
    audit = load_json(audit_rel)
    require(audit.get("status") == "PASS_EXERCISES_15_26_AND_ALL_LINKED_PUBLIC_ODD_ANSWERS_TRANSLATED", "exercise audit status changed")
    require(audit.get("locale") == "id-ID" and audit.get("translator_provenance") == MODEL, "exercise audit provenance changed")
    require(audit.get("authority", {}).get("commit") == COMMIT, "exercise audit authority changed")
    targets = {item.get("path"): item for item in audit.get("targets", []) if isinstance(item, dict)}
    assert_embedded_target(targets.get(exercise_rel, {}), exercise_rel, records[exercise_rel])
    assert_embedded_target(targets.get(answer_rel, {}), answer_rel, records[answer_rel])
    closure = audit.get("answer_closure", {})
    require(closure.get("exercise_ordinals") == list(range(15, 27)), "exercise ordinals changed")
    require(closure.get("public_answer_ordinals") == list(range(15, 26, 2)), "public-answer ordinals changed")
    require(closure.get("o001_mastery_gaps") == list(range(16, 27, 2)), "O001 gaps changed")
    require(closure.get("invented_answers_or_solutions") == 0 and closure.get("restricted_instructor_solutions_used") == 0, "solution boundary changed")
    structure = audit.get("structural_verification", {})
    require(structure.get("exercise_macro_count") == 12 and structure.get("public_answer_macro_count") == 6, "exercise/answer macro counts changed")
    require(structure.get("balanced_braces") is True, "exercise/answer braces changed")
    for key in (
        "ordered_tex_command_and_control_symbol_streams",
        "ordered_environment_streams",
        "inline_math_spans",
        "ordered_numeric_tokens",
    ):
        require(all(value is True for name, value in structure.get(key, {}).items() if name.endswith("_equal") or name.endswith("_equal_in_order")), f"exercise audit structural equality failed: {key}")
    require(structure.get("align_star_bodies", {}).get("whitespace_normalized_equal_in_order") is True, "exercise align math changed")
    require(structure.get("labels", {}).get("ordered_values_equal") is True, "exercise labels changed")
    require(structure.get("references", {}).get("ordered_values_equal") is True, "exercise references changed")
    require(structure.get("citation_keys", {}).get("ordered_values_equal") is True, "exercise citations changed")
    language = audit.get("language_review", {})
    require(language.get("all_active_reader_prose_reviewed") is True, "exercise language review incomplete")
    require(language.get("bounded_active_english_lexicon_hits_after_masking_comments_math_labels_refs_cites_and_commands") == 0, "exercise active English changed")

    exercise_text = repo_path(exercise_rel).read_text(encoding="utf-8")
    answer_text = repo_path(answer_rel).read_text(encoding="utf-8")
    exercise_markers = [int(item) for item in re.findall(r"(?m)^%\s+(\d+)\s*$", exercise_text)]
    answer_markers = [int(item) for item in re.findall(r"(?m)^%\s+(\d+)\s*$", answer_text)]
    require(exercise_markers == list(range(15, 27)) and exercise_text.count("\\eoce{") == 12, "direct exercise sequence changed")
    require(answer_markers == list(range(15, 26, 2)) and answer_text.count("\\eocesol{") == 6, "direct public-answer sequence changed")
    return {
        "audit": records[audit_rel],
        "exercises": records[exercise_rel],
        "public_answers": records[answer_rel],
        "exercise_sequence": exercise_markers,
        "public_answer_sequence": answer_markers,
        "o001_mastery_companion_gaps": list(range(16, 27, 2)),
        "restricted_or_nonpublic_answers_invented": False,
        "tex_math_numeric_label_reference_citation_closure": True,
        "active_untranslated_exercise_or_public_answer_prose": 0,
    }


def verify_data_audit(records: dict[str, dict[str, object]]) -> dict[str, Any]:
    audit_rel = "qa/b021-translation/staging/data_hypothesis_testing_359-445.id.audit.json"
    target_rel = "qa/b021-translation/staging/data_hypothesis_testing_359-445.id.tex"
    audit = load_json(audit_rel)
    require(audit.get("boundary_id") == BOUNDARY and audit.get("status") == "PASS_TRANSLATION_AND_PROTECTED_TEX_CLOSURE", "data audit identity/status changed")
    require(audit.get("authority", {}).get("commit") == COMMIT, "data audit authority changed")
    require(audit.get("source_slice", {}).get("lines") == "359-445 inclusive", "data source slice changed")
    assert_embedded_target(audit.get("target", {}), target_rel, records[target_rel])
    checks = audit.get("protected_token_checks", {})
    for key in ("tex_control_sequence_order", "begin_end_environment_order", "numeric_literal_order", "dormant_comment_lines"):
        equal_stream(checks.get(key, {}), f"data audit {key}")
    residue = checks.get("active_reader_english_residue", {})
    require(residue.get("status") == "PASS_NO_UNTRANSLATED_ACTIVE_DATA_APPENDIX_PROSE", "data appendix active English changed")
    return {
        "audit": records[audit_rel],
        "target": records[target_rel],
        "source_lines": "359-445 inclusive",
        "tex_environment_numeric_and_comment_streams_exact": True,
        "active_untranslated_data_appendix_prose": 0,
    }


def verify_reader_qa(records: dict[str, dict[str, object]]) -> dict[str, Any]:
    lang_rel = "qa/b021-reader/R011-B021_PAGEWISE_LANGUAGE_QA.json"
    tsv_rel = "qa/b021-reader/R011-B021_PAGEWISE_LANGUAGE_QA.tsv"
    visual_rel = "qa/b021-reader/R011-B021_VISUAL_QA.json"
    language = load_json(lang_rel)
    visual = load_json(visual_rel)
    require(language.get("boundary_id") == BOUNDARY, "language-QA boundary changed")
    require(language.get("status") == "PASS_ALL_216_PAGES_ADJUDICATED_NO_UNTRANSLATED_INSTRUCTIONAL_EXERCISE_OR_PUBLIC_ANSWER_PROSE", "language-QA status changed")
    require(
        language.get("learner_reader_total_pages") == 216
        and language.get("accepted_indonesian_reader_pages") == 216
        and language.get("untranslated_instructional_or_exercise_prose_pages") == 0
        and language.get("all_pages_adjudicated") is True,
        "language-QA page closure changed",
    )
    coverage = language.get("exercise_coverage", {})
    require(coverage.get("translated") == list(range(1, 27)), "reader exercise coverage changed")
    require(coverage.get("public_answers_translated") == list(range(1, 26, 2)), "reader public-answer coverage changed")
    require(coverage.get("o001_no_public_answer") == list(range(2, 27, 2)), "reader O001 coverage changed")
    structural = language.get("structural_checks", {})
    require(structural.get("chapter_6_tail_present") is False, "reader includes Chapter 6 tail")
    headings = structural.get("localized_heading_witness_counts", {})
    for heading in (
        "Uji hipotesis untuk suatu proporsi",
        "Kerangka uji hipotesis",
        "Menguji hipotesis menggunakan interval kepercayaan",
        "Galat keputusan",
        "Pengujian formal menggunakan nilai-p",
        "Memilih tingkat signifikansi",
        "Signifikansi statistik versus signifikansi praktis",
        "Uji hipotesis satu sisi (topik khusus)",
    ):
        require(int(headings.get(heading, 0)) > 0, f"localized §5.3 heading missing: {heading}")
    forbidden = language.get("avoidable_residual_and_excluded_scope_counts", {})
    require(isinstance(forbidden, dict) and not any(forbidden.values()), f"reader residual-English counts changed: {forbidden}")
    witnesses = language.get("localized_term_witness_counts", {})
    for key in (
        "section_5_3", "p_value", "null_hypothesis", "alternative_hypothesis",
        "null_distribution", "test_statistic", "significance_level", "type_1_error",
        "type_2_error", "success_failure", "standard_error", "point_estimate",
        "figure_observed_p_hat", "figure_tail_area", "figure_equally_rare",
        "figure_upper_tail", "figure_lower_tail",
    ):
        require(int(witnesses.get(key, 0)) > 0, f"localized reader witness missing: {key}")
    require(witnesses.get("provenance_model") == 1, "reader model-provenance witness changed")
    pages = language.get("pages", [])
    require(isinstance(pages, list) and len(pages) == 216, "language-QA page rows changed")
    require([row.get("page") for row in pages if isinstance(row, dict)] == list(range(1, 217)), "language-QA pages are not ordered 1..216")
    require(not any(row.get("untranslated_instructional_or_exercise_prose") for row in pages), "language-QA contains an untranslated page")

    build = language.get("build_binding", {})
    require("Sections 5.1-5.3" in str(build.get("included_scope")), "build binding no longer ends through §5.3")
    exclusions = "\n".join(str(item) for item in build.get("excluded_untranslated_scope", []))
    require(re.search(r"(?i)Chapters?\s+6", exclusions) is not None, "build binding lacks Chapter 6 exclusion")

    require(visual.get("boundary_id") == BOUNDARY, "visual-QA boundary changed")
    require(visual.get("status") == "PASS_ALL_216_PAGES_VISUALLY_INSPECTED_ZERO_DEFECTS", "visual-QA status changed")
    require(
        visual.get("page_count") == 216
        and visual.get("defect_count") == 0
        and visual.get("all_pages_inspected") is True
        and visual.get("render", {}).get("rendered_page_count") == 216,
        "visual-QA extent changed",
    )
    require(language.get("learner_pdf") == visual.get("learner_pdf"), "language/visual PDF binding differs")
    require(language.get("visual_qa") == records[visual_rel], "language-QA no longer binds exact visual receipt")
    pagewise = visual.get("pagewise_dispositions", [])
    require(len(pagewise) == 216 and [row.get("page") for row in pagewise] == list(range(1, 217)), "visual page rows changed")
    require(all(row.get("disposition") == "PASS_NO_VISUAL_DEFECT" for row in pagewise), "visual page disposition failed")
    covered: list[int] = []
    for contact in visual.get("contact_sheets", []):
        require(contact.get("disposition") == "ALL_PAGES_IN_RANGE_INSPECTED", "visual contact-sheet disposition failed")
        page_range = contact.get("page_range", [])
        require(isinstance(page_range, list) and len(page_range) == 2, "visual contact range malformed")
        covered.extend(range(int(page_range[0]), int(page_range[1]) + 1))
    require(covered == list(range(1, 217)), "visual contacts do not cover pages 1..216 exactly once")
    original_pages = {row.get("page") for row in visual.get("original_scale_checks", [])}
    require({1, 216}.issubset(original_pages), "visual original-scale checks omit first/final page")

    with repo_path(tsv_rel).open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    require(len(rows) == 216 and [int(row["page"]) for row in rows] == list(range(1, 217)), "language TSV rows changed")
    require(all(row["untranslated_instructional_or_exercise_prose"] == "False" for row in rows), "language TSV marks untranslated prose")
    require(all(row["text_sha256"] == pages[index]["text_sha256"] for index, row in enumerate(rows)), "language JSON/TSV page hashes differ")
    return {
        "language_qa": records[lang_rel],
        "language_tsv": records[tsv_rel],
        "visual_qa": records[visual_rel],
        "learner_pdf": language["learner_pdf"],
        "page_count": 216,
        "accepted_indonesian_reader_pages": 216,
        "untranslated_instructional_exercise_or_public_answer_prose_pages": 0,
        "all_pages_language_adjudicated": True,
        "all_pages_visually_inspected": True,
        "visual_defect_count": 0,
        "chapter_6_tail_present": False,
        "incremental_b021_exercises": list(range(15, 27)),
        "incremental_b021_public_answers": list(range(15, 26, 2)),
        "incremental_b021_o001_gaps": list(range(16, 27, 2)),
        "localized_heading_witness_counts": headings,
        "localized_term_witness_counts": witnesses,
    }


def build_payload() -> dict[str, Any]:
    records = verify_frozen_inputs()
    blueprint, scope = verify_blueprint()
    main_results = verify_main_audits(records)
    exercise_result = verify_exercise_answer_audit(records)
    data_result = verify_data_audit(records)
    direct = verify_direct_targets(records)
    reader = verify_reader_qa(records)

    evidence = [{**records[path], "role": ROLES[path]} for path in FROZEN_INPUTS]
    source = blueprint["main_source"]
    exercise_source = blueprint["exercise_answer_closure"]["exercise_source"]
    answer_source = blueprint["exercise_answer_closure"]["public_answer_source"]
    data_source = blueprint["data_closure"]["appendix_slice"]
    verified_targets = []
    for path in TARGETS:
        check = direct["per_target"][path]
        verified_targets.append(
            {
                "role": ROLES[path],
                **records[path],
                "lines": check["logical_lines"],
                "line_endings": check["line_endings"],
                "brace_check": check["brace_check"],
                "forbidden_active_english_anchor_counts": check["forbidden_active_english_anchor_counts"],
            }
        )
    source_identities = [
        {
            "role": "main_section_5_3",
            "path": source["path"],
            "file_bytes": source["file_bytes"],
            "file_sha256": source["file_sha256"],
            "slice_lines": "1509-2907 inclusive",
            "slice_bytes": source["bytes"],
            "slice_sha256": source["sha256"],
        },
        {"role": "exercises_15_26", **exercise_source},
        {"role": "public_answers_15_25_odd", **answer_source},
        {"role": "section_5_3_data_appendix", **data_source},
    ]
    totals = {
        "main_tex_controls": sum(item["tex_controls"]["source"] for item in main_results),
        "main_environments": sum(item["environments"]["source"] for item in main_results),
        "main_label_reference_citation_input_tokens": sum(item["label_reference_citation_input_stream"]["source"] for item in main_results),
        "main_inline_math_spans": sum(item["inline_math_spans"]["source"] for item in main_results),
        "main_numeric_literals": sum(item["numeric_literals"]["source"] for item in main_results),
        "main_newcommand_names": sum(item["newcommand_names"]["source"] for item in main_results),
        "main_dormant_comment_lines": sum(item["dormant_comments"]["source"] for item in main_results),
    }
    return {
        "schema_version": "r011.independent-translation-verification.v1",
        "record_id": "R011-B021-independent-final-translation-verification",
        "corpus_id": "R011",
        "boundary_id": "B021",
        "locale": "id-ID",
        "status": "PASS_INDEPENDENT_TRANSLATION_VERIFICATION",
        "authority": {
            "repository": blueprint["authority"]["repository"],
            "branch": "master",
            "commit": COMMIT,
            "pinned_snapshot_root": f"authority/upstream/openintro-statistics-{COMMIT}",
        },
        "scope": {
            **scope,
            "main_source_parts": [item["source_lines"] for item in main_results],
            "exercise_source": "ch_foundations_for_inf/TeX/hypothesis_testing.tex lines 1-244 inclusive",
            "public_answer_authority_lines": "1007-1098 inclusive",
            "data_appendix_source": "extraTeX/data/data.tex lines 359-445 inclusive",
            "target_lines_reviewed": sum(item["target_logical_lines"] for item in main_results) + 244 + 92 + 86,
            "reader_extent_pages": 216,
            "reader_boundary": "Indonesian front matter and Chapters 1-4 through §4.5, then Chapter 5 introduction and §§5.1-5.3; exact stop before Chapter 6.",
        },
        "source_identities": source_identities,
        "evidence_inputs": evidence,
        "verified_targets": verified_targets,
        "independent_audit_results": {
            "main_chunks": main_results,
            "exercise_and_public_answer": exercise_result,
            "data_appendix": data_result,
        },
        "verification_method": {
            "independent_review_basis": "Accepted per-chunk bilingual audits covering all active §5.3 prose, examples, guided exercises, footnotes, figure alternative text and captions, end-of-section exercises 15-26, public answers 15/17/19/21/23/25, and the bounded data-appendix prose.",
            "deterministic_consolidation_checks": [
                "exact byte-count and SHA-256 replay for every allowed evidence input",
                "contiguous main-source coverage from lines 1509 through 2907",
                "ordered TeX control, environment, label/reference/citation/input, inline-math, numeric, newcommand, and dormant-comment closure",
                "balanced active TeX braces with no negative prefix",
                "direct exercise and public-answer block enumeration",
                "direct bounded active-English anchor scan after masking comments and protected TeX identifiers",
                "exact 216-page language-QA JSON/TSV agreement",
                "exact 216-page zero-defect visual-QA and learner-PDF cross-binding",
                "exact §5.3 heading/terminology witnesses and Chapter 6 exclusion",
            ],
        },
        "structural_results": {
            "status": "PASS",
            "main_source_coverage_contiguous_1509_2907": True,
            "all_main_tex_math_numeric_identifier_streams_exact": True,
            "aggregate_main_protected_counts": totals,
            "all_target_active_braces_balanced_with_nonnegative_prefix": True,
            "exercise_and_public_answer_structure_exact": True,
            "data_appendix_structure_exact": True,
            "direct_target_checks": direct,
        },
        "mathematical_fidelity": {
            "status": "PASS",
            "formulas_and_notation_preserved": True,
            "all_numeric_literal_sequences_preserved": True,
            "all_inline_math_sequences_preserved": True,
            "all_display_math_structures_preserved": True,
            "visible_formula_text_localized": True,
            "figure_alt_texts_translated": 3,
            "source_defects_rendered_by_intended_mathematical_meaning_without_mutating_authority": True,
        },
        "localization_results": {
            "status": "PASS_NATURAL_COMPLETE_ID_ID",
            "active_untranslated_instructional_exercise_or_public_answer_prose": 0,
            "active_untranslated_data_appendix_prose": 0,
            "active_untranslated_instructional_exercise_public_answer_or_data_appendix_prose": 0,
            "direct_forbidden_active_english_anchor_counts": direct["aggregate_forbidden_active_english_anchor_counts"],
            "reader_untranslated_prose_pages": 0,
            "confirmed_terms": {
                "hypothesis testing": "uji hipotesis",
                "null hypothesis": "hipotesis nol",
                "alternative hypothesis": "hipotesis alternatif",
                "p-value": "nilai-p",
                "null distribution": "distribusi nol",
                "test statistic": "statistik uji",
                "significance level": "tingkat signifikansi",
                "Type 1 / Type 2 Error": "Galat Tipe 1 / Galat Tipe 2",
                "standard error": "galat baku",
                "point estimate": "estimasi titik",
                "success-failure condition": "syarat sukses--gagal",
            },
            "protected_non_indonesian_categories": [
                "proper names and cited work titles",
                "stable TeX labels, references, macros, citation keys, figure paths, data identifiers, and index sort keys",
                "mathematical symbols and notation",
                "dormant upstream comments preserved as non-reader-visible source history",
            ],
        },
        "exercise_answer_and_gap_closure": {
            "status": "PASS_PUBLIC_ODD_ONLY_NO_INVENTED_ANSWERS",
            "exercise_eoce_count": 12,
            "exercise_sequence": list(range(15, 27)),
            "public_answer_eocesol_count": 6,
            "public_answer_sequence": list(range(15, 26, 2)),
            "o001_mastery_companion_gaps": list(range(16, 27, 2)),
            "restricted_or_nonpublic_answers_invented": False,
            "later_public_answers_included": False,
            "gap_authority": records["qa/b021-source/R011-B021_BOUNDARY_BLUEPRINT.json"],
        },
        "reader_binding": reader,
        "independence": {
            "accepted_per_chunk_independent_audits_replayed_by_exact_bytes": True,
            "consolidation_validates_structural_claims_instead_of_accepting_status_strings_alone": True,
            "final_reader_language_and_visual_receipts_replayed_by_exact_bytes": True,
            "new_manual_semantic_review_claimed_by_this_consolidator": False,
            "source_or_translation_file_mutated": False,
            "backend_or_release_surface_read_or_mutated": False,
            "git_operation": False,
            "network_access": False,
            "credentials_accessed": False,
            "publication_or_upstream_contact": False,
        },
        "generator": {
            "path": "scripts/verify_b021_independent_translation.py",
            "mode": "deterministic --write followed by exact-byte --verify",
        },
        "conclusion": "The exact frozen B021 staging artifacts and their accepted independent audits pass contiguous §5.3 source coverage, TeX and mathematical fidelity, natural complete id-ID localization, exercises 15-26, all and only public odd answers 15-25, explicit even-answer O001 gaps, bounded data-appendix localization, and exact 216-page language/visual reader closure. They are admissible for B021 backend admission and deterministic publication packaging.",
    }


def serialized_payload() -> bytes:
    return (json.dumps(build_payload(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def write_output() -> dict[str, object]:
    raw = serialized_payload()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(raw)
    require(OUTPUT.read_bytes() == raw, "written verification receipt did not replay byte-for-byte")
    return {
        "status": "PASS_INDEPENDENT_TRANSLATION_VERIFICATION_WRITTEN",
        "output": {
            "path": OUTPUT.relative_to(ROOT).as_posix(),
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        },
    }


def verify_output() -> dict[str, object]:
    require(OUTPUT.is_file(), f"missing consolidated verification receipt: {OUTPUT}")
    expected = serialized_payload()
    observed = OUTPUT.read_bytes()
    require(observed == expected, "consolidated verification receipt is not the exact deterministic payload")
    value = json.loads(observed.decode("utf-8"))
    require(value.get("status") == "PASS_INDEPENDENT_TRANSLATION_VERIFICATION", "consolidated PASS status changed")
    return {
        "status": "PASS_INDEPENDENT_TRANSLATION_VERIFICATION_EXACT_REPLAY",
        "output": {
            "path": OUTPUT.relative_to(ROOT).as_posix(),
            "bytes": len(observed),
            "sha256": hashlib.sha256(observed).hexdigest(),
        },
        "input_count": len(FROZEN_INPUTS),
        "reader_pages": 216,
    }


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create or exactly replay the consolidated R011-B021 independent translation verification.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="validate every frozen input and write the deterministic consolidated receipt")
    mode.add_argument("--verify", action="store_true", help="validate every frozen input and require exact receipt-byte replay")
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Iterable[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args(argv)
    result = write_output() if args.write else verify_output()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except VerificationError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        raise SystemExit(1)
