#!/usr/bin/env python3
"""Read-only deterministic verifier for the R011-B015 translation candidate."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AUTHORITY = (
    ROOT
    / "authority/upstream/"
    "openintro-statistics-fee25091fb24e89c36296fd67c48c1fcf7a93b6e"
)


def read_bytes(relative: str) -> bytes:
    return (ROOT / relative).read_bytes()


def read_text(relative: str) -> str:
    return read_bytes(relative).decode("utf-8")


def identity(relative: str) -> dict[str, object]:
    payload = read_bytes(relative)
    return {
        "bytes": len(payload),
        "path": relative,
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def occurrences(text: str, pattern: str) -> int:
    return len(re.findall(pattern, text))


def macro_counts(text: str) -> dict[str, int]:
    patterns = {
        "align_blocks": r"\\begin\{align\*\}",
        "eoce": r"\\eoce\{",
        "figures": r"\\begin\{figure\}",
        "footnote_links": r"\\footnotemark\{\}",
        "forced_digital_page_breaks": re.escape(r"\D{\newpage}"),
        "guided_exercises": r"\\begin\{nexercise\}",
        "inline_answers": r"\\footnotetext\{",
        "inputs": r"\\input\{",
        "newcommands": r"\\newcommand\{",
        "oneboxes": r"\\begin\{onebox\}",
        "parts": r"\\begin\{parts\}",
        "public_answers": r"\\eocesol\{",
        "sections": r"\\section\{",
        "subsections": r"\\subsection\{",
        "worked_examples": r"\\begin\{nexample\}",
    }
    return {name: occurrences(text, pattern) for name, pattern in patterns.items()}


def values(text: str, pattern: str) -> list[str]:
    return re.findall(pattern, text)


def inline_math(text: str) -> list[str]:
    return re.findall(r"(?<!\\)\$(.*?)(?<!\\)\$", text, re.DOTALL)


def align_blocks(text: str) -> list[str]:
    return re.findall(
        r"\\begin\{align\*\}(.*?)\\end\{align\*\}", text, re.DOTALL
    )


def normalized_align(block: str) -> str:
    localized_text = re.sub(r"\\text\{[^{}]*\}", r"\\text{#}", block)
    return re.sub(r"\s+", "", localized_text)


def comments(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.lstrip().startswith("%")]


def term_index_keys(text: str) -> list[str]:
    keys: list[str] = []
    for match in re.finditer(
        r"\\(term|termsub)\{([^}]*)\}(?:\{([^}]*)\})?", text
    ):
        macro, display, explicit_key = match.groups()
        keys.append(explicit_key if macro == "termsub" else display)
    return keys


def brace_and_environment_check(text: str) -> dict[str, object]:
    brace_stack: list[tuple[int, int]] = []
    extra_closers: list[tuple[int, int]] = []
    for line_number, raw_line in enumerate(text.splitlines(), 1):
        comment_at = len(raw_line)
        for offset, char in enumerate(raw_line):
            if char == "%" and (offset == 0 or raw_line[offset - 1] != "\\"):
                comment_at = offset
                break
        line = raw_line[:comment_at]
        for column, char in enumerate(line, 1):
            if char not in "{}":
                continue
            if column > 1 and line[column - 2] == "\\":
                continue
            if char == "{":
                brace_stack.append((line_number, column))
            elif brace_stack:
                brace_stack.pop()
            else:
                extra_closers.append((line_number, column))

    environment_stack: list[str] = []
    environment_errors: list[dict[str, object]] = []
    for match in re.finditer(r"\\(begin|end)\{([^}]+)\}", text):
        kind, name = match.groups()
        if kind == "begin":
            environment_stack.append(name)
        elif environment_stack and environment_stack[-1] == name:
            environment_stack.pop()
        else:
            environment_errors.append(
                {
                    "encountered": name,
                    "expected": environment_stack[-1] if environment_stack else None,
                }
            )
    return {
        "balanced": not brace_stack
        and not extra_closers
        and not environment_stack
        and not environment_errors,
        "environment_errors": environment_errors,
        "extra_brace_closers": extra_closers,
        "unclosed_braces": brace_stack,
        "unclosed_environments": environment_stack,
    }


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    source_main_full = read_text(
        "authority/upstream/"
        "openintro-statistics-fee25091fb24e89c36296fd67c48c1fcf7a93b6e/"
        "ch_distributions/TeX/ch_distributions.tex"
    )
    source_main_start = source_main_full.index(r"\section{Geometric distribution}")
    source_main_end = source_main_full.index(
        r"\section{Binomial distribution}", source_main_start
    )
    source_main = source_main_full[source_main_start:source_main_end]
    target_main = read_text("scratch/b015-candidate/ch_distributions_section_4_2_id.tex")

    source_eoce = read_text(
        "authority/upstream/"
        "openintro-statistics-fee25091fb24e89c36296fd67c48c1fcf7a93b6e/"
        "ch_distributions/TeX/geometric_distribution.tex"
    )
    target_eoce = read_text("scratch/b015-candidate/geometric_distribution_B015.tex")

    source_solutions_full = read_text(
        "authority/upstream/"
        "openintro-statistics-fee25091fb24e89c36296fd67c48c1fcf7a93b6e/"
        "extraTeX/eoceSolutions/eoceSolutions.tex"
    )
    answer_anchor = source_solutions_full.index(
        r"\eocesol{(a)~No. The cards are not independent."
    )
    source_answers_start = source_solutions_full.rfind("% 11", 0, answer_anchor)
    source_answers_end = source_solutions_full.index("% 17", answer_anchor)
    source_answers = source_solutions_full[source_answers_start:source_answers_end]
    target_answers = read_text("scratch/b015-candidate/R011-B015_PUBLIC_ODD_ANSWERS.tex")

    source_data_full = read_text(
        "authority/upstream/"
        "openintro-statistics-fee25091fb24e89c36296fd67c48c1fcf7a93b6e/"
        "extraTeX/data/data.tex"
    )
    source_data_start = source_data_full.index(r"\item[\ref{geomDist}]")
    source_data_end = source_data_full.index(
        r"\item[\ref{binomialModel}]", source_data_start
    )
    source_data = source_data_full[source_data_start:source_data_end]
    target_data = read_text("scratch/b015-candidate/data_geomDist_B015.tex")

    live_main_full = read_text("repo/ch_distributions/TeX/ch_distributions.tex")
    live_start = live_main_full.index(r"\section{Geometric distribution}")
    live_end = live_main_full.index(r"\section{Binomial distribution}", live_start)
    require(
        live_main_full[live_start:live_end] == source_main,
        "live inherited geomDist slice no longer matches pinned authority",
    )
    require(
        read_bytes("repo/ch_distributions/TeX/geometric_distribution.tex")
        == read_bytes(
            "authority/upstream/"
            "openintro-statistics-fee25091fb24e89c36296fd67c48c1fcf7a93b6e/"
            "ch_distributions/TeX/geometric_distribution.tex"
        ),
        "live inherited geometric exercise insert no longer matches authority",
    )

    main_patterns = {
        "labels": r"\\label\{([^}]*)\}",
        "references": r"\\ref\{([^}]*)\}",
        "newcommand_names": r"\\newcommand\{\\([^}]*)\}",
        "index_keys": r"\\index\{([^}]*)\}",
        "inputs": r"\\input\{([^}]*)\}",
    }
    main_sequences: dict[str, dict[str, object]] = {}
    for name, pattern in main_patterns.items():
        source_values = values(source_main, pattern)
        target_values = values(target_main, pattern)
        require(source_values == target_values, f"main {name} differ")
        main_sequences[name] = {
            "count": len(source_values),
            "exact_and_ordered": True,
            "values": source_values,
        }

    eoce_patterns = {
        "labels": r"\\label\{([^}]*)\}",
        "references": r"\\ref\{([^}]*)\}",
    }
    eoce_sequences: dict[str, dict[str, object]] = {}
    for name, pattern in eoce_patterns.items():
        source_values = values(source_eoce, pattern)
        target_values = values(target_eoce, pattern)
        require(source_values == target_values, f"EoCE {name} differ")
        eoce_sequences[name] = {
            "count": len(source_values),
            "exact_and_ordered": True,
            "values": source_values,
        }

    newcommands_pattern = r"\\newcommand\{\\([^}]*)\}\{([^}]*)\}"
    source_newcommands = re.findall(newcommands_pattern, source_main)
    target_newcommands = re.findall(newcommands_pattern, target_main)
    require(source_newcommands == target_newcommands, "newcommand names or values differ")

    source_term_keys = term_index_keys(source_main)
    target_term_keys = term_index_keys(target_main)
    require(source_term_keys == target_term_keys, "term index keys differ")

    source_emphasis = values(source_main, r"\\emph\{([^}]*)\}")
    target_emphasis = values(target_main, r"\\emph\{([^}]*)\}")
    require(
        source_emphasis == ["independence", "identical"],
        "unexpected source emphasis sequence",
    )
    require(
        target_emphasis == ["deductible", "independensi", "identik"],
        "translated emphasis sequence differs",
    )

    source_main_counts = macro_counts(source_main)
    target_main_counts = macro_counts(target_main)
    source_eoce_counts = macro_counts(source_eoce)
    target_eoce_counts = macro_counts(target_eoce)
    source_answer_counts = macro_counts(source_answers)
    target_answer_counts = macro_counts(target_answers)
    require(source_main_counts == target_main_counts, "main macro topology differs")
    require(source_eoce_counts == target_eoce_counts, "EoCE macro topology differs")
    require(source_answer_counts == target_answer_counts, "answer macro topology differs")

    expected_inline_math_localizations = {
        "main": [
            {"source": "n^{th}", "span_1_based": 9, "target": "n"},
            {"source": "n^{th}", "span_1_based": 12, "target": "n"},
            {"source": "n^{th}", "span_1_based": 19, "target": "n"},
            {"source": "n^{th}", "span_1_based": 37, "target": "n"},
        ],
        "eoce": [
            {"source": "10^{th}", "span_1_based": 1, "target": "10"},
        ],
        "public_answers": [],
    }
    math_checks: dict[str, object] = {}
    for name, source, target in (
        ("main", source_main, target_main),
        ("eoce", source_eoce, target_eoce),
        ("public_answers", source_answers, target_answers),
    ):
        source_inline = inline_math(source)
        target_inline = inline_math(target)
        require(
            len(source_inline) == len(target_inline),
            f"{name} inline math span count differs",
        )
        observed_localizations = [
            {"source": source_value, "span_1_based": index + 1, "target": target_value}
            for index, (source_value, target_value) in enumerate(
                zip(source_inline, target_inline)
            )
            if source_value != target_value
        ]
        require(
            observed_localizations == expected_inline_math_localizations[name],
            f"{name} inline math differs beyond approved ordinal display localizations",
        )
        math_checks[name] = {
            "all_other_inline_math_exact_and_ordered": True,
            "approved_ordinal_display_localizations": observed_localizations,
            "inline_math_count": len(source_inline),
        }

    require("^{th}" not in target_main, "main retains reader-visible th ordinal")
    require("^{th}" not in target_eoce, "EoCE retains reader-visible th ordinal")

    source_align = [normalized_align(block) for block in align_blocks(source_main)]
    target_align = [normalized_align(block) for block in align_blocks(target_main)]
    require(source_align == target_align, "display math differs beyond localized text")
    math_checks["main"]["align_block_count"] = len(source_align)
    math_checks["main"]["align_math_exact_after_localized_text_normalization"] = True

    require(comments(source_main) == comments(target_main), "source comments differ")

    source_data_refs = values(source_data, r"\\ref\{([^}]*)\}")
    target_data_refs = values(target_data, r"\\ref\{([^}]*)\}")
    require(source_data_refs == target_data_refs == ["geomDist"], "data refs differ")
    require(source_data.count(r"\datawrap{") == 1, "source datawrap count differs")
    require(target_data.count(r"\datawrap{") == 1, "target datawrap count differs")

    syntax = {
        "main": brace_and_environment_check(target_main),
        "eoce": brace_and_environment_check(target_eoce),
        "public_answers": brace_and_environment_check(target_answers),
        "data_appendix": brace_and_environment_check(target_data),
    }
    require(all(item["balanced"] for item in syntax.values()), "candidate syntax unbalanced")

    expected_candidate_identities = {
        "figure_label_map": {
            "bytes": 167,
            "sha256": "ce45d9a5b529f599400e5230db999f70a7a2009a820eebf208e28565719027a3",
        },
        "data_appendix": {
            "bytes": 231,
            "sha256": "20acc17df7ee9dfe7f3b747aabc08cd5003a14f1ef126c479e7617fbd877a489",
        },
        "main": {
            "bytes": 12690,
            "sha256": "367dbd3a92deaa476231861fcf8dd266bd877278f7620f1967da1e672d6e0497",
        },
        "eoce": {
            "bytes": 3804,
            "sha256": "56b3f7e137755aa4d7187a82dd71f4c1b2dd6f6999bade9c4a96dfba98a0cc77",
        },
        "public_answers": {
            "bytes": 906,
            "sha256": "a7d672e808f66bfc57cfe70f52fe41b29486997b8eca09c99b2f2c4e63a04dd9",
        },
    }
    candidate_paths = {
        "data_appendix": "scratch/b015-candidate/data_geomDist_B015.tex",
        "figure_label_map": "scratch/b015-candidate/geometricDist70_id-ID_labels.tsv",
        "main": "scratch/b015-candidate/ch_distributions_section_4_2_id.tex",
        "eoce": "scratch/b015-candidate/geometric_distribution_B015.tex",
        "public_answers": "scratch/b015-candidate/R011-B015_PUBLIC_ODD_ANSWERS.tex",
    }
    candidate_identities: dict[str, dict[str, object]] = {}
    for name, relative in candidate_paths.items():
        observed = identity(relative)
        require(
            observed["bytes"] == expected_candidate_identities[name]["bytes"]
            and observed["sha256"] == expected_candidate_identities[name]["sha256"],
            f"candidate identity changed for {name}",
        )
        candidate_identities[name] = observed

    figure_authority_r = read_bytes(
        "authority/upstream/"
        "openintro-statistics-fee25091fb24e89c36296fd67c48c1fcf7a93b6e/"
        "ch_distributions/figures/geometricDist70/geometricDist70.R"
    )
    figure_live_r = read_bytes(
        "repo/ch_distributions/figures/geometricDist70/geometricDist70.R"
    )
    figure_authority_pdf = read_bytes(
        "authority/upstream/"
        "openintro-statistics-fee25091fb24e89c36296fd67c48c1fcf7a93b6e/"
        "ch_distributions/figures/geometricDist70/geometricDist70.pdf"
    )
    figure_live_pdf = read_bytes(
        "repo/ch_distributions/figures/geometricDist70/geometricDist70.pdf"
    )
    require(figure_authority_r == figure_live_r, "live figure R source differs")
    require(figure_authority_pdf == figure_live_pdf, "live figure PDF differs")

    result = {
        "$schema": "interlanguage.r011-b015-candidate-replay/v1",
        "authority": {
            "commit": "fee25091fb24e89c36296fd67c48c1fcf7a93b6e",
            "tree": "d61cc601e7d97759ce805900520f784d02a0489e",
        },
        "boundary_id": "R011-B015",
        "candidate_identities": candidate_identities,
        "comments_exact": True,
        "emphasis": {
            "source_semantic_emphasis_preserved": True,
            "source_values": source_emphasis,
            "target_values": target_emphasis,
        },
        "eoce_sequences": eoce_sequences,
        "figure_authority_live_byte_exact": True,
        "macro_counts": {
            "data_appendix": {
                "datawrap": 1,
                "references": 1,
                "source_target_exact": True,
            },
            "main": source_main_counts,
            "eoce": source_eoce_counts,
            "public_answers": source_answer_counts,
            "source_target_exact": True,
        },
        "main_sequences": main_sequences,
        "math": math_checks,
        "newcommand_names_values_exact": True,
        "o001_missing_public_answers": [12, 14, 16],
        "production_model": "OpenAI Codex gpt-5.6-sol, Ultra",
        "status": "PASS_READ_ONLY_DETERMINISTIC_REPLAY",
        "syntax": syntax,
        "term_index_keys": {
            "exact_and_ordered": True,
            "values": source_term_keys,
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
