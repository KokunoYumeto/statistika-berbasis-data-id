#!/usr/bin/env python3
"""Deterministically replay the B005 EoCE assets assigned to this lane.

Three pinned vector PDFs receive Indonesian label substitutions.  Seven
numeric/symbol-only PDFs are copied byte-for-byte.  The pinned PDFs remain the
geometry authority: for localized files, every non-target PDF instruction is
asserted unchanged and only the text-showing instruction plus its centering
matrix may change.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import pikepdf
from pikepdf import ContentStreamInstruction, Operator, parse_content_stream
from reportlab.pdfbase.pdfmetrics import stringWidth


AUTHORITY_COMMIT = "fee25091fb24e89c36296fd67c48c1fcf7a93b6e"
AUTHORITY_TREE = "d61cc601e7d97759ce805900520f784d02a0489e"


@dataclass(frozen=True)
class Replacement:
    old: str
    new: str


LOCALIZED: dict[str, tuple[Replacement, ...]] = {
    "eoce/county_hispanic_pop/county_hispanic_pop_hist.pdf": (
        Replacement("Percent Hispanic", "Persentase Hispanik"),
    ),
    "eoce/county_hispanic_pop/county_hispanic_pop_log_hist.pdf": (
        Replacement(
            "log(Percent Hispanic)", "log(Persentase Hispanik)"
        ),
    ),
    "eoce/reproducing_bacteria/reproducing_bacteria_sketch.pdf": (
        Replacement("time", "waktu"),
        Replacement("number of bacteria cells", "jumlah sel bakteri"),
    ),
}


COPY_ONLY = (
    "eoce/association_plots/association_plots.pdf",
    "eoce/hist_box_match/hist_box_match.pdf",
    "eoce/estimate_mean_median_simple/estimate_mean_median_simple.pdf",
    "eoce/hist_vs_box/hist_vs_box.pdf",
    "eoce/income_coffee_shop/income_coffee_shop.pdf",
    "eoce/county_commute_times/county_commute_times_map.pdf",
    "eoce/county_hispanic_pop/county_hispanic_pop_map.pdf",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def instruction_bytes(instruction: ContentStreamInstruction) -> bytes:
    return pikepdf.unparse_content_stream([instruction])


def text_value(instruction: ContentStreamInstruction) -> str | None:
    operator = str(instruction.operator)
    if operator == "Tj":
        return str(instruction.operands[0])
    if operator == "TJ":
        return "".join(
            str(item)
            for item in instruction.operands[0]
            if isinstance(item, pikepdf.String)
        )
    return None


def preceding_tm(
    operations: list[ContentStreamInstruction], text_index: int
) -> int:
    for index in range(text_index - 1, -1, -1):
        operator = str(operations[index].operator)
        if operator == "Tm":
            return index
        if operator == "BT":
            break
    raise ValueError(f"No text matrix precedes text instruction {text_index}")


def matrix_values(instruction: ContentStreamInstruction) -> list[float]:
    return [float(value) for value in instruction.operands]


def new_matrix(values: list[float]) -> ContentStreamInstruction:
    return ContentStreamInstruction(
        [Decimal(f"{value:.4f}") for value in values], Operator("Tm")
    )


def text_scale(
    operations: list[ContentStreamInstruction], text_index: int
) -> float:
    tm_index = preceding_tm(operations, text_index)
    a, b, _c, _d, _e, _f = matrix_values(operations[tm_index])
    return math.hypot(a, b)


def text_advance(
    operations: list[ContentStreamInstruction], text_index: int
) -> float:
    instruction = operations[text_index]
    scale = text_scale(operations, text_index)
    operator = str(instruction.operator)
    if operator == "Tj":
        return stringWidth(str(instruction.operands[0]), "Helvetica", scale)
    if operator == "TJ":
        advance = 0.0
        for item in instruction.operands[0]:
            if isinstance(item, pikepdf.String):
                advance += stringWidth(str(item), "Helvetica", scale)
            else:
                advance -= float(item) * scale / 1000.0
        return advance
    raise ValueError(f"Instruction {text_index} is not text-showing")


def find_unique_text(
    operations: list[ContentStreamInstruction], expected: str
) -> int:
    matches = [
        index
        for index, instruction in enumerate(operations)
        if text_value(instruction) == expected
    ]
    if len(matches) != 1:
        raise ValueError(
            f"Expected one occurrence of {expected!r}, found {len(matches)}"
        )
    return matches[0]


def center_replace(
    operations: list[ContentStreamInstruction],
    replacement: Replacement,
    changed: set[int],
) -> dict:
    text_index = find_unique_text(operations, replacement.old)
    tm_index = preceding_tm(operations, text_index)
    old_advance = text_advance(operations, text_index)
    scale = text_scale(operations, text_index)
    new_advance = stringWidth(replacement.new, "Helvetica", scale)
    matrix = matrix_values(operations[tm_index])
    shift = (old_advance - new_advance) / 2.0
    if abs(matrix[0]) >= abs(matrix[1]):
        matrix[4] += shift
    else:
        matrix[5] += shift
    operations[tm_index] = new_matrix(matrix)
    operations[text_index] = ContentStreamInstruction(
        [pikepdf.String(replacement.new)], Operator("Tj")
    )
    changed.update((tm_index, text_index))
    return {
        "old": replacement.old,
        "new": replacement.new,
        "text_instruction_index": text_index,
        "matrix_instruction_index": tm_index,
        "old_advance": round(old_advance, 6),
        "new_advance": round(new_advance, 6),
        "center_shift": round(shift, 6),
    }


def replay_localized(
    source: Path, destination: Path, relative_path: str
) -> dict:
    with pikepdf.Pdf.open(source) as pdf:
        if len(pdf.pages) != 1:
            raise ValueError(f"Expected one page: {source}")
        page = pdf.pages[0]
        operations = list(parse_content_stream(page))
        before = [instruction_bytes(operation) for operation in operations]
        changed: set[int] = set()
        replacement_records = [
            center_replace(operations, replacement, changed)
            for replacement in LOCALIZED[relative_path]
        ]
        for index, operation in enumerate(operations):
            if index not in changed and instruction_bytes(operation) != before[index]:
                raise AssertionError(
                    f"Non-target instruction changed at {index}: {relative_path}"
                )

        unchanged_hasher = hashlib.sha256()
        for index, raw_instruction in enumerate(before):
            if index in changed:
                continue
            unchanged_hasher.update(len(raw_instruction).to_bytes(8, "big"))
            unchanged_hasher.update(raw_instruction)

        page.Contents = pdf.make_stream(pikepdf.unparse_content_stream(operations))
        destination.parent.mkdir(parents=True, exist_ok=True)
        pdf.save(
            destination,
            deterministic_id=True,
            compress_streams=True,
            recompress_flate=False,
            normalize_content=False,
        )

    return {
        "relative_path": relative_path,
        "mode": "localized-vector-text",
        "authority_bytes": source.stat().st_size,
        "authority_sha256": sha256(source),
        "output_bytes": destination.stat().st_size,
        "output_sha256": sha256(destination),
        "instruction_count": len(before),
        "changed_instruction_count": len(changed),
        "unchanged_instruction_count": len(before) - len(changed),
        "unchanged_instruction_sha256": unchanged_hasher.hexdigest(),
        "replacements": replacement_records,
    }


def replay_copy(source: Path, destination: Path, relative_path: str) -> dict:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    source_hash = sha256(source)
    output_hash = sha256(destination)
    if source_hash != output_hash:
        raise AssertionError(f"Exact-copy replay failed: {relative_path}")
    return {
        "relative_path": relative_path,
        "mode": "exact-copy-no-reader-visible-words",
        "authority_bytes": source.stat().st_size,
        "authority_sha256": source_hash,
        "output_bytes": destination.stat().st_size,
        "output_sha256": output_hash,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authority-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()

    if len(LOCALIZED) != 3 or len(COPY_ONLY) != 7:
        raise AssertionError("Expected exact 3-localized/7-copy assigned closure")
    records = [
        replay_localized(
            args.authority_root / relative_path,
            args.output_root / relative_path,
            relative_path,
        )
        for relative_path in sorted(LOCALIZED)
    ]
    records.extend(
        replay_copy(
            args.authority_root / relative_path,
            args.output_root / relative_path,
            relative_path,
        )
        for relative_path in sorted(COPY_ONLY)
    )
    manifest = {
        "schema": "r011-b005-eoce-hispanic-bacteria-replay/v1",
        "authority_commit": AUTHORITY_COMMIT,
        "authority_tree": AUTHORITY_TREE,
        "localized_pdf_count": 3,
        "exact_copy_pdf_count": 7,
        "records": sorted(records, key=lambda record: record["relative_path"]),
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
