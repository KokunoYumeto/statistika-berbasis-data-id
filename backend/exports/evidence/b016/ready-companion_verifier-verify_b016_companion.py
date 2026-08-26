from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE_MAIN = ROOT / "repo/ch_distributions/TeX/binomial_distribution.tex"
SOURCE_ANSWERS = ROOT / "repo/extraTeX/eoceSolutions/eoceSolutions.tex"
SOURCE_DATA = ROOT / "repo/extraTeX/data/data.tex"
TARGET_MAIN = HERE / "binomial_distribution_B016.tex"
TARGET_ANSWERS = HERE / "R011-B016_PUBLIC_ODD_ANSWERS.tex"
TARGET_DATA = HERE / "data_binomialModel_B016.tex"
TARGET_GAPS = HERE / "R011-B016_O001_GAPS.json"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def balanced_braces(value: str) -> bool:
    depth = 0
    escaped = False
    for char in value:
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def controls(value: str) -> list[str]:
    return re.findall(r"\\[A-Za-z@]+|\\\\", value)


def inline_math(value: str) -> list[str]:
    return re.findall(r"(?<!\\)\$(.*?)(?<!\\)\$", value, flags=re.S)


def numerics(value: str) -> list[str]:
    return re.findall(r"(?<![A-Za-z])\d+(?:\.\d+)?", value)


def answer_source_slice(value: str) -> str:
    answer_anchor = value.index("Binomial conditions are met")
    start = value.rindex("% 17", 0, answer_anchor)
    end = value.index("% 27", start)
    return value[start:end]


def data_source_slice(value: str) -> str:
    marker = r"\item[\ref{binomialModel}]"
    start = value.index(marker)
    end = value.index(r"\item[\ref{negativeBinomial}]", start)
    return value[start:end]


def check(name: str, condition: bool, detail: object) -> dict[str, object]:
    return {"name": name, "pass": bool(condition), "detail": detail}


source_main = text(SOURCE_MAIN)
source_answers = answer_source_slice(text(SOURCE_ANSWERS))
source_data = data_source_slice(text(SOURCE_DATA))
target_main = text(TARGET_MAIN)
target_answers = text(TARGET_ANSWERS)
target_data = text(TARGET_DATA)
gaps = json.loads(text(TARGET_GAPS))
source_main_reflow_normalized = source_main.replace(r"\D{\newpage}", "", 1)
target_main_reflow_normalized = target_main.replace(r"\D{\newpage}", "", 1).replace(r"\vfill", "")

def normalize_math(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


normalized_source_main_math = [
    normalize_math(value.replace("4^{th}", "4").replace("3^{rd}", "3"))
    for value in inline_math(source_main)
]
normalized_target_main_math = [normalize_math(value) for value in inline_math(target_main)]

labels_source = re.findall(r"\\label\{([^}]+)\}", source_main)
labels_target = re.findall(r"\\label\{([^}]+)\}", target_main)
refs_source = re.findall(r"\\ref\{([^}]+)\}", source_main)
refs_target = re.findall(r"\\ref\{([^}]+)\}", target_main)
cites_source = re.findall(r"\\footfullcite\{([^}]+)\}", source_main)
cites_target = re.findall(r"\\footfullcite\{([^}]+)\}", target_main)
redirect_ids_source = re.findall(r"\\oiRedirect\{([^}]+)\}", source_main)
redirect_ids_target = re.findall(r"\\oiRedirect\{([^}]+)\}", target_main)

forbidden_english = re.compile(
    r"\b(?:what|calculate|probability|distribution|randomly|sampled|exactly|"
    r"suppose|would|using|since|therefore|consumed|alcoholic|underage|"
    r"drinking|permutations|male children|"
    r"photo by|an image|license)\b",
    flags=re.I,
)
english_hits = {
    "main": sorted(set(forbidden_english.findall(target_main))),
    "answers": sorted(set(forbidden_english.findall(target_answers))),
    "data": sorted(set(forbidden_english.findall(target_data))),
}

gap_numbers = [row["exercise_number"] for row in gaps["missing_public_answer_gaps"]]
gap_labels = [row["source_label"] for row in gaps["missing_public_answer_gaps"]]
controlled_phrases = {
    "distribusi binomial": target_main + target_answers,
    "model binomial": target_main,
    "percobaan yang saling independen": target_answers,
    "jumlah percobaan yang tetap": target_answers,
    "peluang sukses": target_answers,
    "permutasi": target_main,
    "pendekatan normal terhadap distribusi binomial": target_answers,
    "simpangan baku": target_main + target_answers,
}

checks = [
    check("main_braces_balanced", balanced_braces(target_main), True),
    check("answers_braces_balanced", balanced_braces(target_answers), True),
    check("data_braces_balanced", balanced_braces(target_data), True),
    check("main_control_sequence_exact_after_one_relocated_reader_break", controls(source_main_reflow_normalized) == controls(target_main_reflow_normalized)
          and source_main.count(r"\D{\newpage}") == 1 and target_main.count(r"\D{\newpage}") == 1
          and source_main.count(r"\vfill") == 0 and target_main.count(r"\vfill") == 6, {
        "source_after_normalization": len(controls(source_main_reflow_normalized)),
        "target_after_normalization": len(controls(target_main_reflow_normalized)),
        "relocated_break": r"\D{\newpage}",
        "source_after_exercise": 21,
        "target_before_exercise": 24,
        "target_flexible_vertical_fills": 6,
        "reason": "balance and vertically distribute all three EoCE pages while preserving the display-only break count"
    }),
    check("main_labels_exact", labels_source == labels_target, labels_target),
    check("main_refs_exact", refs_source == refs_target, refs_target),
    check("main_citations_exact", cites_source == cites_target, cites_target),
    check("main_redirect_ids_exact", redirect_ids_source == redirect_ids_target, redirect_ids_target),
    check("main_asset_paths_retained", all(token in target_main for token in ("eoce/dreidel", "dreidel.jpg")), ["eoce/dreidel", "dreidel.jpg"]),
    check("main_inline_math_exact_after_two_locale_ordinals", normalized_source_main_math == normalized_target_main_math, {
        "source_math_count": len(normalized_source_main_math), "target_math_count": len(inline_math(target_main)),
        "allowed_mappings": ["4^{th}->4", "3^{rd}->3"]
    }),
    check("main_numeric_sequence_exact", numerics(source_main) == numerics(target_main), len(numerics(target_main))),
    check("exercise_count_exact", target_main.count(r"\eoce{") == 10, target_main.count(r"\eoce{")),
    check("part_item_count_exact", target_main.count(r"\item") == 40, target_main.count(r"\item")),
    check("answer_control_sequence_exact", controls(source_answers) == controls(target_answers), {
        "source": len(controls(source_answers)), "target": len(controls(target_answers))
    }),
    check("answer_inline_math_exact", inline_math(source_answers) == inline_math(target_answers), len(inline_math(target_answers))),
    check("answer_numeric_sequence_exact", numerics(source_answers) == numerics(target_answers), len(numerics(target_answers))),
    check("public_odd_answer_count_exact", target_answers.count(r"\eocesol{") == 5, target_answers.count(r"\eocesol{")),
    check("data_control_sequence_exact", controls(source_data) == controls(target_data), {
        "source": len(controls(source_data)), "target": len(controls(target_data))
    }),
    check("data_refs_exact", re.findall(r"\\ref\{([^}]+)\}", source_data) == re.findall(r"\\ref\{([^}]+)\}", target_data), re.findall(r"\\ref\{([^}]+)\}", target_data)),
    check("data_redirect_ids_exact", re.findall(r"\\oiRedirect\{([^}]+)\}", source_data) == re.findall(r"\\oiRedirect\{([^}]+)\}", target_data), re.findall(r"\\oiRedirect\{([^}]+)\}", target_data)),
    check("data_url_exact", "cdc.gov/tobacco/data\\_statistics/fact\\_sheets/adult\\_data/cig\\_smoking/index.htm" in target_data, True),
    check("data_numeric_sequence_exact", numerics(source_data) == numerics(target_data), len(numerics(target_data))),
    check("data_entry_count_exact", target_data.count(r"\item[\ref{binomialModel}]") == 3, target_data.count(r"\item[\ref{binomialModel}]")),
    check("o001_gap_numbers_exact", gap_numbers == [18, 20, 22, 24, 26], gap_numbers),
    check("o001_gap_labels_exact", gap_labels == ["chicken_pox_intro", "chicken_pox_normal_approx", "arachnophobia", "sickle_cell_anemia", "male_children"], gap_labels),
    check("no_restricted_solution_claim", "No restricted instructor solutions were accessed" in gaps["public_answer_policy"], gaps["public_answer_policy"]),
    check("no_untranslated_english_residue", not any(english_hits.values()), english_hits),
    check("controlled_terminology_exact", all(phrase.casefold() in value.casefold() for phrase, value in controlled_phrases.items()), sorted(controlled_phrases)),
    check("source_acronym_correction_applied", "(SAMSHA)" in source_main and "(SAMHSA)" in target_main and "(SAMSHA)" not in target_main, "SAMSHA -> SAMHSA"),
    check("source_grammar_correction_applied", "will the be" in source_main and "will the be" not in target_main, "will the be -> natural grammatical Indonesian"),
]

payload = {
    "schema_version": "r011.b016-companion-verifier.v1",
    "boundary_id": "R011-B016",
    "status": "PASS" if all(row["pass"] for row in checks) else "FAIL",
    "counts": {
        "exercises": 10,
        "exercise_parts": 40,
        "public_odd_answers": 5,
        "o001_missing_public_answer_gaps": 5,
        "data_appendix_entries": 3,
        "source_corrections": 2,
        "locale_math_adaptations": 2,
        "layout_reflows": 1,
    },
    "source_corrections": [
        {
            "exercise": 17,
            "source": "SAMSHA",
            "target": "SAMHSA",
            "reason": "Corrected the transposed letters in the agency acronym while retaining the agency's full proper name."
        },
        {
            "exercise": 24,
            "source": "will the be",
            "target": "merupakan",
            "reason": "Removed the duplicated English article/verb-order defect in a faithful natural Indonesian rendering."
        }
    ],
    "locale_adaptations": [
        {"exercise": 23, "source_math": "4^{th}", "target_math": "4", "rendering": "ke-$4$"},
        {"exercise": 24, "source_math": "3^{rd}", "target_math": "3", "rendering": "ke-$3$"}
    ],
    "layout_adaptations": [
        {
            "after_exercise": 21,
            "before_exercise": 24,
            "relocated_source_command": r"\D{\newpage}",
            "target_flexible_vertical_fills": 6,
            "reason": "reader reflow balances and vertically distributes all three EoCE pages while preserving exercise order, photo, attribution, mathematics, and all semantic links"
        }
    ],
    "checks": checks,
    "files": {
        str(path.relative_to(ROOT)).replace("\\", "/"): {
            "bytes": path.stat().st_size,
            "sha256": sha256(path)
        }
        for path in (
            SOURCE_MAIN, SOURCE_ANSWERS, SOURCE_DATA,
            TARGET_MAIN, TARGET_ANSWERS, TARGET_DATA, TARGET_GAPS
        )
    }
}

print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
sys.exit(0 if payload["status"] == "PASS" else 1)
