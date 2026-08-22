#!/usr/bin/env python3
"""Deterministically localize the figures used by the admitted B005 prefix.

The pinned upstream PDFs are the geometry authority.  This replay changes the
explicit reader-visible label text and the text matrices needed to retain the
original alignment.  In the stacked dot plot it also replaces 50 unembedded
ZapfDingbats point glyphs, which Poppler drops, with explicit vector circles at
the same visual centres.  Every other PDF drawing/text instruction is asserted
to be semantically identical.  Two referenced plots contain numeric labels
only and are copied byte-for-byte.

This helper is intentionally independent of an R installation.  The matching
localized R producers remain beside the final PDFs for future native replay.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Callable, Iterable

import pikepdf
from pikepdf import ContentStreamInstruction, Operator, parse_content_stream
from reportlab.pdfbase.pdfmetrics import stringWidth


PORTABLE_STACKED_PATH = (
    "loan_int_rate_dot_plot/loan_int_rate_dot_plot_stacked.pdf"
)
POINT_RUN = re.compile(
    rb"BT\s+/F1 1 Tf\s+2 Tr\s+14\.96 0 0 14\.96 "
    rb"(?P<x>-?\d+(?:\.\d+)?) (?P<y>-?\d+(?:\.\d+)?) Tm\s+"
    rb"\(l\) Tj\s+0 Tr\s+ET"
)

# MuPDF resolves the Standard-14 ZapfDingbats ``a71`` glyph used by R's
# pch=19 to an almost circular outline with these exact em-space bounds:
# x=[0.034988405, 0.7569885], y=[-0.014007568, 0.70799258].  Preserve the
# midpoint and bounding radius at the source 14.96-point text scale.  The
# inherited fill, stroke, 0.75-point width, clipping path, and sRGB graphics
# state are intentionally left untouched.
POINT_CENTER_OFFSET_X = 5.9239872494
POINT_CENTER_OFFSET_Y = 5.19100788976
POINT_PATH_RADIUS = 5.40056091256
KAPPA = 0.5522847498307936


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


def preceding_tm(operations: list[ContentStreamInstruction], text_index: int) -> int:
    for index in range(text_index - 1, -1, -1):
        operator = str(operations[index].operator)
        if operator == "Tm":
            return index
        if operator == "BT":
            break
    raise ValueError(f"No text matrix precedes text instruction {text_index}")


def matrix_values(instruction: ContentStreamInstruction) -> list[float]:
    return [float(value) for value in instruction.operands]


def new_matrix(values: Iterable[float]) -> ContentStreamInstruction:
    operands = [Decimal(f"{value:.4f}") for value in values]
    return ContentStreamInstruction(operands, Operator("Tm"))


def text_scale(operations: list[ContentStreamInstruction], text_index: int) -> float:
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
    raise ValueError(f"Instruction {text_index} is not a text-showing operator")


def point_group_indices(
    operations: list[ContentStreamInstruction],
) -> set[int]:
    """Return the exact 50 seven-instruction ZapfDingbats point runs."""
    point_text_indices = [
        index
        for index, instruction in enumerate(operations)
        if str(instruction.operator) == "Tj"
        and str(instruction.operands[0]) == "l"
    ]
    if len(point_text_indices) != 50:
        raise ValueError(
            f"Expected 50 stacked-dot glyphs, found {len(point_text_indices)}"
        )
    changed: set[int] = set()
    for text_index in point_text_indices:
        start = text_index - 4
        stop = text_index + 2
        if start < 0 or stop >= len(operations):
            raise ValueError("A stacked-dot point run is truncated")
        group = b"\n".join(
            instruction_bytes(operation)
            for operation in operations[start : stop + 1]
        )
        if POINT_RUN.fullmatch(group) is None:
            raise ValueError(
                f"Unexpected stacked-dot point instruction group at {text_index}"
            )
        changed.update(range(start, stop + 1))
    if len(changed) != 350:
        raise ValueError(f"Expected 350 point instructions, found {len(changed)}")
    return changed


def vector_circle(match: re.Match[bytes]) -> bytes:
    """Replace one non-portable point glyph with an explicit Bezier circle."""
    source_x = float(match.group("x"))
    source_y = float(match.group("y"))
    center_x = source_x + POINT_CENTER_OFFSET_X
    center_y = source_y + POINT_CENTER_OFFSET_Y
    radius = POINT_PATH_RADIUS
    control = radius * KAPPA
    return (
        "% R011-B005 portable stacked point\n"
        f"{center_x + radius:.6f} {center_y:.6f} m\n"
        f"{center_x + radius:.6f} {center_y + control:.6f} "
        f"{center_x + control:.6f} {center_y + radius:.6f} "
        f"{center_x:.6f} {center_y + radius:.6f} c\n"
        f"{center_x - control:.6f} {center_y + radius:.6f} "
        f"{center_x - radius:.6f} {center_y + control:.6f} "
        f"{center_x - radius:.6f} {center_y:.6f} c\n"
        f"{center_x - radius:.6f} {center_y - control:.6f} "
        f"{center_x - control:.6f} {center_y - radius:.6f} "
        f"{center_x:.6f} {center_y - radius:.6f} c\n"
        f"{center_x + control:.6f} {center_y - radius:.6f} "
        f"{center_x + radius:.6f} {center_y - control:.6f} "
        f"{center_x + radius:.6f} {center_y:.6f} c\n"
        "B"
    ).encode("ascii")


@dataclass(frozen=True)
class Replacement:
    old: str
    new: str
    align: str = "center"  # center, left, or right
    scale_factor: float = 1.0


SINGLE_REPLACEMENTS: dict[str, tuple[Replacement, ...]] = {
    "loan50_amt_vs_income/loan50_amt_vs_income.pdf": (
        Replacement("Total Income", "Total Pendapatan"),
        Replacement("Loan Amount", "Jumlah Pinjaman"),
    ),
    "medianHHIncomePoverty/medianHHIncomePoverty.pdf": (
        Replacement("Poverty Rate (Percent)", "Tingkat Kemiskinan (Persen)"),
        Replacement(
            "Median Household Income", "Median Pendapatan Rumah Tangga"
        ),
    ),
    "loan_int_rate_dot_plot/loan_int_rate_dot_plot.pdf": (
        Replacement("Interest Rate", "Suku Bunga"),
    ),
    "loan_int_rate_dot_plot/loan_int_rate_dot_plot_stacked.pdf": (
        Replacement(
            "Interest Rate, Rounded to Nearest Percent",
            "Suku Bunga, Dibulatkan ke Persen Terdekat",
        ),
    ),
    "loan50IntRateHist/loan50IntRateHist.pdf": (
        Replacement("Interest Rate", "Suku Bunga"),
        Replacement("Frequency", "Frekuensi"),
    ),
    "loan_int_rate_box_plot_layout/loan_int_rate_box_plot_layout.pdf": (
        Replacement("Interest Rate", "Suku Bunga"),
        Replacement("lower whisker", "garis kumis bawah", "left"),
        Replacement("(first quartile)", "(kuartil pertama)", "left"),
        Replacement("(third quartile)", "(kuartil ketiga)", "left"),
        Replacement("upper whisker", "garis kumis atas", "left"),
        Replacement(
            "max whisker reach", "batas maksimum kumis", "left", 0.875
        ),
        Replacement(
            "suspected outliers", "pencilan yang dicurigai", "left", 0.875
        ),
    ),
    "loan_int_rate_robust_ex/loan_int_rate_robust_ex.pdf": (
        Replacement("Interest Rate", "Suku Bunga"),
        Replacement("Original", "Asli", "right"),
        Replacement("26.3% to 15%", "26.3% ke 15%", "right"),
        Replacement("26.3% to 35%", "26.3% ke 35%", "right"),
    ),
    "county_pop_transformed/county_pop_transformed_i.pdf": (
        Replacement("Population (m = millions)", "Populasi (m = juta)"),
        Replacement("Frequency", "Frekuensi"),
    ),
    "county_pop_change_v_pop_transform/county_pop_change_v_pop_transform_i.pdf": (
        Replacement("Population Change", "Perubahan Populasi"),
        Replacement(
            "Population Before Change (m = millions)",
            "Populasi Sebelum Perubahan (m = juta)",
        ),
    ),
    "countyIntensityMaps/countyPovertyMap.pdf": (
        Replacement("Poverty", "Kemiskinan"),
    ),
    "countyIntensityMaps/countyUnemploymentRateMap.pdf": (
        Replacement("Unemployment Rate", "Tingkat Pengangguran"),
    ),
    "countyIntensityMaps/countyHomeownershipMap.pdf": (
        Replacement("Homeownership Rate", "Tingkat Kepemilikan Rumah"),
    ),
    "countyIntensityMaps/countyMedIncomeMap.pdf": (
        Replacement(
            "Median Household Income", "Median Pendapatan Rumah Tangga"
        ),
    ),
}


COPY_ONLY = (
    "singleBiMultiModalPlots/singleBiMultiModalPlots.pdf",
    "severalDiffDistWithSdOf1/severalDiffDistWithSdOf1.pdf",
)


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


def shift_text_origin(
    operations: list[ContentStreamInstruction],
    text_index: int,
    amount: float,
    changed: set[int],
) -> None:
    tm_index = preceding_tm(operations, text_index)
    matrix = matrix_values(operations[tm_index])
    a, b = matrix[0], matrix[1]
    if abs(a) >= abs(b):
        matrix[4] += amount
    else:
        matrix[5] += amount
    operations[tm_index] = new_matrix(matrix)
    changed.add(tm_index)


def replace_single(
    operations: list[ContentStreamInstruction],
    replacement: Replacement,
    changed: set[int],
) -> None:
    text_index = find_unique_text(operations, replacement.old)
    old_advance = text_advance(operations, text_index)
    scale = text_scale(operations, text_index)
    new_scale = scale * replacement.scale_factor
    new_advance = stringWidth(replacement.new, "Helvetica", new_scale)
    if replacement.align == "center":
        shift_text_origin(
            operations, text_index, (old_advance - new_advance) / 2.0, changed
        )
    elif replacement.align == "right":
        shift_text_origin(
            operations, text_index, old_advance - new_advance, changed
        )
    elif replacement.align != "left":
        raise ValueError(f"Unsupported alignment: {replacement.align}")
    if replacement.scale_factor != 1.0:
        tm_index = preceding_tm(operations, text_index)
        matrix = matrix_values(operations[tm_index])
        for index in range(4):
            matrix[index] *= replacement.scale_factor
        operations[tm_index] = new_matrix(matrix)
        changed.add(tm_index)
    operations[text_index] = ContentStreamInstruction(
        [pikepdf.String(replacement.new)], Operator("Tj")
    )
    changed.add(text_index)


def cluster_bottom_label(
    operations: list[ContentStreamInstruction],
    old: str,
    new: str,
    predicate: Callable[[list[float]], bool],
    changed: set[int],
) -> None:
    """Replace one fragment while preserving the center of a split label."""
    target_index = find_unique_text(operations, old)
    old_advance = text_advance(operations, target_index)
    scale = text_scale(operations, target_index)
    new_advance = stringWidth(new, "Helvetica", scale)
    delta = new_advance - old_advance
    group_shift = -delta / 2.0

    cluster_text_indices: list[int] = []
    for index, instruction in enumerate(operations):
        if text_value(instruction) is None:
            continue
        tm_index = preceding_tm(operations, index)
        if predicate(matrix_values(operations[tm_index])):
            cluster_text_indices.append(index)
    if target_index not in cluster_text_indices:
        raise ValueError(f"Target {old!r} is not in its expected label cluster")

    for index in cluster_text_indices:
        offset = group_shift if index <= target_index else group_shift + delta
        shift_text_origin(operations, index, offset, changed)

    operations[target_index] = ContentStreamInstruction(
        [pikepdf.String(new)], Operator("Tj")
    )
    changed.add(target_index)


def localize_special_clusters(
    relative_path: str,
    operations: list[ContentStreamInstruction],
    changed: set[int],
) -> None:
    if relative_path == "sdRuleForIntRate/sdRuleForIntRate.pdf":
        cluster_bottom_label(
            operations,
            "Interest Rate, ",
            "Suku Bunga, ",
            lambda matrix: matrix[5] < 15 and 100 < matrix[4] < 350,
            changed,
        )
    elif relative_path == "county_pop_transformed/county_pop_transformed_log.pdf":
        cluster_bottom_label(
            operations,
            "(Population)",
            "(Populasi)",
            lambda matrix: matrix[5] < 12 and 100 < matrix[4] < 200,
            changed,
        )
        replace_single(
            operations, Replacement("Frequency", "Frekuensi"), changed
        )
    elif relative_path == (
        "county_pop_change_v_pop_transform/"
        "county_pop_change_v_pop_transform_log.pdf"
    ):
        cluster_bottom_label(
            operations,
            "(Population Before Change)",
            "(Populasi Sebelum Perubahan)",
            lambda matrix: matrix[5] < 12 and 80 < matrix[4] < 320,
            changed,
        )
        replace_single(
            operations,
            Replacement("Population Change", "Perubahan Populasi"),
            changed,
        )


SPECIAL_CLUSTER_PATHS = (
    "sdRuleForIntRate/sdRuleForIntRate.pdf",
    "county_pop_transformed/county_pop_transformed_log.pdf",
    (
        "county_pop_change_v_pop_transform/"
        "county_pop_change_v_pop_transform_log.pdf"
    ),
)


def replay_pdf(source: Path, destination: Path, relative_path: str) -> dict:
    with pikepdf.Pdf.open(source) as pdf:
        if len(pdf.pages) != 1:
            raise ValueError(f"Expected one page: {source}")
        page = pdf.pages[0]
        operations = list(parse_content_stream(page))
        before = [instruction_bytes(operation) for operation in operations]
        changed: set[int] = set()

        point_instruction_indices: set[int] = set()
        if relative_path == PORTABLE_STACKED_PATH:
            point_instruction_indices = point_group_indices(operations)
            changed.update(point_instruction_indices)

        for replacement in SINGLE_REPLACEMENTS.get(relative_path, ()):
            replace_single(operations, replacement, changed)
        localize_special_clusters(relative_path, operations, changed)

        if not changed:
            raise ValueError(f"No localization operation was applied to {relative_path}")
        for index, operation in enumerate(operations):
            if index not in changed and instruction_bytes(operation) != before[index]:
                raise AssertionError(
                    f"Non-target PDF instruction changed at index {index}: {relative_path}"
                )

        unchanged_hasher = hashlib.sha256()
        for index, raw_instruction in enumerate(before):
            if index in changed:
                continue
            unchanged_hasher.update(len(raw_instruction).to_bytes(8, "big"))
            unchanged_hasher.update(raw_instruction)

        output_content = pikepdf.unparse_content_stream(operations)
        point_coordinate_sha256 = None
        point_count = 0
        if relative_path == PORTABLE_STACKED_PATH:
            source_point_matches = list(POINT_RUN.finditer(output_content))
            if len(source_point_matches) != 50:
                raise AssertionError(
                    f"Expected 50 serialized point runs, got {len(source_point_matches)}"
                )
            coordinate_rows = []
            for match in source_point_matches:
                source_x = float(match.group("x"))
                source_y = float(match.group("y"))
                coordinate_rows.append(
                    f"{source_x:.2f}\t{source_y:.2f}\t"
                    f"{source_x + POINT_CENTER_OFFSET_X:.6f}\t"
                    f"{source_y + POINT_CENTER_OFFSET_Y:.6f}\n"
                )
            point_coordinate_sha256 = hashlib.sha256(
                "".join(coordinate_rows).encode("ascii")
            ).hexdigest()
            output_content, point_count = POINT_RUN.subn(
                vector_circle, output_content
            )
            if point_count != 50 or b"/F1" in output_content:
                raise AssertionError("Portable stacked-point closure failed")
            fonts = page.Resources["/Font"]
            if "/F1" not in fonts:
                raise AssertionError("Expected the ZapfDingbats /F1 resource")
            del fonts["/F1"]

        page.Contents = pdf.make_stream(output_content)
        destination.parent.mkdir(parents=True, exist_ok=True)
        pdf.save(
            destination,
            deterministic_id=True,
            compress_streams=True,
            recompress_flate=False,
            normalize_content=False,
        )

    record = {
        "relative_path": relative_path,
        "mode": (
            "localized-vector-text-plus-portable-vector-points"
            if relative_path == PORTABLE_STACKED_PATH
            else "localized-vector-text"
        ),
        "authority_bytes": source.stat().st_size,
        "authority_sha256": sha256(source),
        "output_bytes": destination.stat().st_size,
        "output_sha256": sha256(destination),
        "instruction_count": len(before),
        "changed_instruction_count": len(changed),
        "unchanged_instruction_count": len(before) - len(changed),
        "unchanged_instruction_sha256": unchanged_hasher.hexdigest(),
    }
    if relative_path == PORTABLE_STACKED_PATH:
        record["portable_point_repair"] = {
            "source_zapf_dingbats_point_count": point_count,
            "target_vector_circle_count": point_count,
            "source_point_instruction_count": len(point_instruction_indices),
            "center_offset": [
                POINT_CENTER_OFFSET_X,
                POINT_CENTER_OFFSET_Y,
            ],
            "path_radius": POINT_PATH_RADIUS,
            "fill_and_stroke_operator": "B",
            "coordinate_mapping_sha256": point_coordinate_sha256,
        }
    return record


def copy_pdf(source: Path, destination: Path, relative_path: str) -> dict:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    authority_hash = sha256(source)
    output_hash = sha256(destination)
    if authority_hash != output_hash:
        raise AssertionError(f"Exact-copy replay failed: {relative_path}")
    return {
        "relative_path": relative_path,
        "mode": "exact-copy-no-reader-visible-words",
        "authority_bytes": source.stat().st_size,
        "authority_sha256": authority_hash,
        "output_bytes": destination.stat().st_size,
        "output_sha256": output_hash,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authority-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()

    localized_paths = sorted(set(SINGLE_REPLACEMENTS) | set(SPECIAL_CLUSTER_PATHS))
    if len(localized_paths) != 16:
        raise AssertionError(f"Expected 16 localized PDFs, got {len(localized_paths)}")

    records: list[dict] = []
    for relative_path in localized_paths:
        records.append(
            replay_pdf(
                args.authority_root / relative_path,
                args.output_root / relative_path,
                relative_path,
            )
        )
    for relative_path in sorted(COPY_ONLY):
        records.append(
            copy_pdf(
                args.authority_root / relative_path,
                args.output_root / relative_path,
                relative_path,
            )
        )

    manifest = {
        "schema": "r011-b005-prefix-figure-replay/v1",
        "authority_commit": "fee25091fb24e89c36296fd67c48c1fcf7a93b6e",
        "authority_tree": "d61cc601e7d97759ce805900520f784d02a0489e",
        "localized_pdf_count": 16,
        "exact_copy_pdf_count": 2,
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
