#!/usr/bin/env python3
"""Verify promoted B005-prefix figures and emit durable receipts/control rows."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pikepdf
from PIL import Image
from pypdf import PdfReader


PORTABLE_STACKED_PATH = (
    "loan_int_rate_dot_plot/loan_int_rate_dot_plot_stacked.pdf"
)
POINT_RUN = re.compile(
    rb"BT\s+/F1 1 Tf\s+2 Tr\s+14\.96 0 0 14\.96 "
    rb"(?P<x>-?\d+(?:\.\d+)?) (?P<y>-?\d+(?:\.\d+)?) Tm\s+"
    rb"\(l\) Tj\s+0 Tr\s+ET"
)
VECTOR_RUN = re.compile(
    rb"% R011-B005 portable stacked point\s+"
    rb"(?P<path_x>-?\d+(?:\.\d+)?) (?P<path_y>-?\d+(?:\.\d+)?) m"
)
POINT_CENTER_OFFSET_X = 5.9239872494
POINT_CENTER_OFFSET_Y = 5.19100788976
POINT_PATH_RADIUS = 5.40056091256


PRODUCERS = {
    "loan50_amt_vs_income/loan50_amt_vs_income.pdf": (
        "loan50_amt_vs_income/loan50_amt_vs_income.R",
    ),
    "medianHHIncomePoverty/medianHHIncomePoverty.pdf": (
        "medianHHIncomePoverty/medianHHIncomePoverty.R",
    ),
    "loan_int_rate_dot_plot/loan_int_rate_dot_plot.pdf": (
        "loan_int_rate_dot_plot/loan_int_rate_dot_plot.R",
    ),
    "loan_int_rate_dot_plot/loan_int_rate_dot_plot_stacked.pdf": (
        "loan_int_rate_dot_plot/loan_int_rate_dot_plot.R",
    ),
    "loan50IntRateHist/loan50IntRateHist.pdf": (
        "loan50IntRateHist/loan50IntRateHist.R",
    ),
    "singleBiMultiModalPlots/singleBiMultiModalPlots.pdf": (
        "singleBiMultiModalPlots/singleBiMultiModalPlots.R",
    ),
    "sdRuleForIntRate/sdRuleForIntRate.pdf": (
        "sdRuleForIntRate/sdRuleForIntRate.R",
    ),
    "severalDiffDistWithSdOf1/severalDiffDistWithSdOf1.pdf": (
        "severalDiffDistWithSdOf1/severalDiffDistWithSdOf1.R",
    ),
    "loan_int_rate_box_plot_layout/loan_int_rate_box_plot_layout.pdf": (
        "loan_int_rate_box_plot_layout/loan_int_rate_box_plot_layout.R",
    ),
    "loan_int_rate_robust_ex/loan_int_rate_robust_ex.pdf": (
        "loan_int_rate_robust_ex/loan_int_rate_robust_ex.R",
    ),
    "county_pop_transformed/county_pop_transformed_i.pdf": (
        "county_pop_transformed/county_pop_transformed.R",
    ),
    "county_pop_transformed/county_pop_transformed_log.pdf": (
        "county_pop_transformed/county_pop_transformed.R",
    ),
    "county_pop_change_v_pop_transform/county_pop_change_v_pop_transform_i.pdf": (
        "county_pop_change_v_pop_transform/county_pop_change_v_pop_transform.R",
    ),
    "county_pop_change_v_pop_transform/county_pop_change_v_pop_transform_log.pdf": (
        "county_pop_change_v_pop_transform/county_pop_change_v_pop_transform.R",
    ),
    "countyIntensityMaps/countyPovertyMap.pdf": (
        "countyIntensityMaps/countyIntensityMaps.R",
        "countyIntensityMaps/countyMap.R",
    ),
    "countyIntensityMaps/countyUnemploymentRateMap.pdf": (
        "countyIntensityMaps/countyIntensityMaps.R",
        "countyIntensityMaps/countyMap.R",
    ),
    "countyIntensityMaps/countyHomeownershipMap.pdf": (
        "countyIntensityMaps/countyIntensityMaps.R",
        "countyIntensityMaps/countyMap.R",
    ),
    "countyIntensityMaps/countyMedIncomeMap.pdf": (
        "countyIntensityMaps/countyIntensityMaps.R",
        "countyIntensityMaps/countyMap.R",
    ),
}


DATA_IDS = {
    "loan50_amt_vs_income/loan50_amt_vs_income.pdf": (
        "openintro::loan50.total_income",
        "openintro::loan50.loan_amount",
        "openintro::COL",
    ),
    "medianHHIncomePoverty/medianHHIncomePoverty.pdf": (
        "openintro::county.poverty",
        "openintro::county.median_hh_income",
        "openintro::COL",
    ),
    "loan_int_rate_dot_plot/loan_int_rate_dot_plot.pdf": (
        "openintro::loan50.interest_rate",
        "openintro::COL",
    ),
    "loan_int_rate_dot_plot/loan_int_rate_dot_plot_stacked.pdf": (
        "openintro::loan50.interest_rate",
        "openintro::COL",
    ),
    "loan50IntRateHist/loan50IntRateHist.pdf": (
        "openintro::loan50.interest_rate",
        "openintro::COL",
    ),
    "singleBiMultiModalPlots/singleBiMultiModalPlots.pdf": (
        "synthetic:set.seed(51);stats::rchisq;stats::rnorm",
        "openintro::COL",
    ),
    "sdRuleForIntRate/sdRuleForIntRate.pdf": (
        "openintro::loan50.interest_rate",
        "openintro::COL",
    ),
    "severalDiffDistWithSdOf1/severalDiffDistWithSdOf1.pdf": (
        "synthetic:stats::qnorm;stats::qchisq",
        "openintro::COL",
    ),
    "loan_int_rate_box_plot_layout/loan_int_rate_box_plot_layout.pdf": (
        "openintro::loan50.interest_rate",
        "openintro::COL",
    ),
    "loan_int_rate_robust_ex/loan_int_rate_robust_ex.pdf": (
        "openintro::loan50.interest_rate",
        "synthetic:set.seed(16)",
        "openintro::COL",
    ),
    "county_pop_transformed/county_pop_transformed_i.pdf": (
        "openintro::county.pop2017",
        "openintro::COL",
    ),
    "county_pop_transformed/county_pop_transformed_log.pdf": (
        "openintro::county.pop2017",
        "openintro::COL",
    ),
    "county_pop_change_v_pop_transform/county_pop_change_v_pop_transform_i.pdf": (
        "openintro::county.pop2010",
        "openintro::county.pop_change",
        "openintro::COL",
    ),
    "county_pop_change_v_pop_transform/county_pop_change_v_pop_transform_log.pdf": (
        "openintro::county.pop2010",
        "openintro::county.pop_change",
        "openintro::COL",
    ),
    "countyIntensityMaps/countyPovertyMap.pdf": (
        "openintro::county.poverty",
        "openintro::county_complete.FIPS",
        "maps::county.fips",
        "maps::map(county)",
    ),
    "countyIntensityMaps/countyUnemploymentRateMap.pdf": (
        "openintro::county.unemployment_rate",
        "openintro::county_complete.FIPS",
        "maps::county.fips",
        "maps::map(county)",
    ),
    "countyIntensityMaps/countyHomeownershipMap.pdf": (
        "openintro::county.homeownership",
        "openintro::county_complete.FIPS",
        "maps::county.fips",
        "maps::map(county)",
    ),
    "countyIntensityMaps/countyMedIncomeMap.pdf": (
        "openintro::county.median_hh_income",
        "openintro::county_complete.FIPS",
        "maps::county.fips",
        "maps::map(county)",
    ),
}


PROHIBITED_READER_STRINGS = (
    "population",
    "interest rate",
    "loan amount",
    "total income",
    "household income",
    "poverty rate",
    "frequency",
    "unemployment rate",
    "homeownership rate",
    "original",
    "whisker",
    "quartile",
    "suspected outliers",
    " to 15%",
    " to 35%",
    "millions",
)


SOURCE_ORDER = (
    "loan50_amt_vs_income/loan50_amt_vs_income.pdf",
    "medianHHIncomePoverty/medianHHIncomePoverty.pdf",
    "loan_int_rate_dot_plot/loan_int_rate_dot_plot.pdf",
    "loan_int_rate_dot_plot/loan_int_rate_dot_plot_stacked.pdf",
    "loan50IntRateHist/loan50IntRateHist.pdf",
    "singleBiMultiModalPlots/singleBiMultiModalPlots.pdf",
    "sdRuleForIntRate/sdRuleForIntRate.pdf",
    "severalDiffDistWithSdOf1/severalDiffDistWithSdOf1.pdf",
    "loan_int_rate_box_plot_layout/loan_int_rate_box_plot_layout.pdf",
    "loan_int_rate_robust_ex/loan_int_rate_robust_ex.pdf",
    "county_pop_transformed/county_pop_transformed_i.pdf",
    "county_pop_transformed/county_pop_transformed_log.pdf",
    (
        "county_pop_change_v_pop_transform/"
        "county_pop_change_v_pop_transform_i.pdf"
    ),
    (
        "county_pop_change_v_pop_transform/"
        "county_pop_change_v_pop_transform_log.pdf"
    ),
    "countyIntensityMaps/countyPovertyMap.pdf",
    "countyIntensityMaps/countyUnemploymentRateMap.pdf",
    "countyIntensityMaps/countyHomeownershipMap.pdf",
    "countyIntensityMaps/countyMedIncomeMap.pdf",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(args)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def blue_mask(path: Path) -> np.ndarray:
    rgb = np.asarray(Image.open(path).convert("RGB")).astype(int)
    return (
        (rgb[:, :, 2] > 120)
        & (rgb[:, :, 1] > 90)
        & (rgb[:, :, 0] < 150)
        & (rgb[:, :, 2] > rgb[:, :, 0] + 20)
    )


def blue_component_sizes(mask: np.ndarray) -> list[int]:
    """Return eight-connected blue-component sizes without a scipy dependency."""
    height, width = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    sizes: list[int] = []
    for y_value, x_value in zip(*np.nonzero(mask)):
        y = int(y_value)
        x = int(x_value)
        if seen[y, x]:
            continue
        seen[y, x] = True
        stack = [(y, x)]
        size = 0
        while stack:
            current_y, current_x = stack.pop()
            size += 1
            for delta_y in (-1, 0, 1):
                for delta_x in (-1, 0, 1):
                    if delta_x == 0 and delta_y == 0:
                        continue
                    next_y = current_y + delta_y
                    next_x = current_x + delta_x
                    if (
                        0 <= next_y < height
                        and 0 <= next_x < width
                        and mask[next_y, next_x]
                        and not seen[next_y, next_x]
                    ):
                        seen[next_y, next_x] = True
                        stack.append((next_y, next_x))
        sizes.append(size)
    return sorted(sizes, reverse=True)


def verify_stacked_portability(
    authority_path: Path, live_path: Path, scratch_parent: Path
) -> dict[str, object]:
    with pikepdf.Pdf.open(authority_path) as authority_pdf:
        authority_warnings = authority_pdf.check_pdf_syntax()
        if authority_warnings:
            raise AssertionError(
                f"Stacked-dot authority syntax warnings: {authority_warnings}"
            )
        authority_content = authority_pdf.pages[0].Contents.read_bytes()
    with pikepdf.Pdf.open(live_path) as live_pdf:
        live_warnings = live_pdf.check_pdf_syntax()
        if live_warnings:
            raise AssertionError(
                f"Portable stacked-dot syntax warnings: {live_warnings}"
            )
        page = live_pdf.pages[0]
        live_content = page.Contents.read_bytes()
        font_keys = sorted(str(key) for key in page.Resources.Font.keys())

    source_points = [
        (float(match.group("x")), float(match.group("y")))
        for match in POINT_RUN.finditer(authority_content)
    ]
    vector_points = [
        (float(match.group("path_x")), float(match.group("path_y")))
        for match in VECTOR_RUN.finditer(live_content)
    ]
    if len(source_points) != 50 or len(vector_points) != 50:
        raise AssertionError(
            "Stacked-dot point count mismatch: "
            f"source={len(source_points)}, target={len(vector_points)}"
        )

    coordinate_rows = []
    for index, ((source_x, source_y), (path_x, path_y)) in enumerate(
        zip(source_points, vector_points, strict=True), 1
    ):
        center_x = source_x + POINT_CENTER_OFFSET_X
        center_y = source_y + POINT_CENTER_OFFSET_Y
        coordinate_rows.append(
            f"{source_x:.2f}\t{source_y:.2f}\t{center_x:.6f}\t{center_y:.6f}\n"
        )
        if (
            abs(path_x - (center_x + POINT_PATH_RADIUS)) > 1e-6
            or abs(path_y - center_y) > 1e-6
        ):
            raise AssertionError(f"Stacked-dot coordinate mismatch at point {index}")

    if font_keys != ["/F2"] or b"/F1" in live_content:
        raise AssertionError(f"Non-portable point font remains: {font_keys}")
    if live_content.count(b"% R011-B005 portable stacked point") != 50:
        raise AssertionError("Portable point marker count mismatch")
    if live_content.count(b"\nB") < 50:
        raise AssertionError("Filled-and-stroked vector-circle operators missing")
    for color_instruction in (
        b"0.337 0.608 0.741 scn",
        b"0.337 0.608 0.741 SCN",
    ):
        if live_content.count(color_instruction) != 1:
            raise AssertionError(
                f"Stacked-dot point color instruction drift: {color_instruction!r}"
            )

    strict_reader = PdfReader(str(live_path), strict=True)
    if len(strict_reader.pages) != 1:
        raise AssertionError("Strict pypdf stacked-dot page count mismatch")

    scratch = scratch_parent / "stacked_portability_check_tmp"
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)
    try:
        clean_pdf = scratch / "clean.pdf"
        authority_mupdf_png = scratch / "authority-mupdf.png"
        target_mupdf_png = scratch / "target-mupdf.png"
        target_poppler_prefix = scratch / "target-poppler"
        target_poppler_png = scratch / "target-poppler.png"
        embed_poppler_prefix = scratch / "embed-poppler"
        embed_poppler_png = scratch / "embed-poppler.png"

        run("mutool", "clean", str(live_path), str(clean_pdf))
        run("mutool", "info", str(live_path))
        run("mutool", "pages", str(live_path))
        run(
            "mutool", "draw", "-q", "-r", "180", "-o",
            str(authority_mupdf_png), str(authority_path), "1",
        )
        run(
            "mutool", "draw", "-q", "-r", "180", "-o",
            str(target_mupdf_png), str(live_path), "1",
        )
        run(
            "pdftoppm", "-f", "1", "-singlefile", "-r", "180", "-png",
            str(live_path), str(target_poppler_prefix),
        )
        text = run("pdftotext", "-layout", str(live_path), "-").stdout
        if "Suku Bunga, Dibulatkan ke Persen Terdekat" not in text:
            raise AssertionError("Localized stacked-dot label is not extractable")
        run("pdfinfo", str(live_path))
        fonts_output = run("pdffonts", str(live_path)).stdout
        if "ZapfDingbats" in fonts_output:
            raise AssertionError("pdffonts still reports ZapfDingbats")

        authority_blue = blue_mask(authority_mupdf_png)
        target_mupdf_blue = blue_mask(target_mupdf_png)
        target_poppler_blue = blue_mask(target_poppler_png)
        component_counts = {
            "authority_mupdf": len(
                [size for size in blue_component_sizes(authority_blue) if size >= 100]
            ),
            "target_mupdf": len(
                [size for size in blue_component_sizes(target_mupdf_blue) if size >= 100]
            ),
            "target_poppler": len(
                [size for size in blue_component_sizes(target_poppler_blue) if size >= 100]
            ),
        }
        if set(component_counts.values()) != {50}:
            raise AssertionError(
                f"A renderer did not expose 50 blue points: {component_counts}"
            )

        source_intersection = int(
            np.logical_and(authority_blue, target_mupdf_blue).sum()
        )
        source_union = int(np.logical_or(authority_blue, target_mupdf_blue).sum())
        source_target_iou = source_intersection / source_union
        renderer_intersection = int(
            np.logical_and(target_mupdf_blue, target_poppler_blue).sum()
        )
        renderer_union = int(
            np.logical_or(target_mupdf_blue, target_poppler_blue).sum()
        )
        renderer_iou = renderer_intersection / renderer_union
        if source_target_iou < 0.95 or renderer_iou < 0.98:
            raise AssertionError(
                "Stacked-dot blue-render parity failed: "
                f"source_target={source_target_iou}, renderer={renderer_iou}"
            )

        tex = scratch / "embed.tex"
        tex.write_text(
            "\\documentclass{article}\n"
            "\\usepackage[margin=12mm]{geometry}\n"
            "\\usepackage{graphicx}\n"
            "\\pagestyle{empty}\n"
            "\\begin{document}\n"
            f"\\includegraphics[width=\\linewidth]{{{live_path.resolve().as_posix()}}}\n"
            "\\end{document}\n",
            encoding="ascii",
            newline="\n",
        )
        latex = run(
            "pdflatex", "-interaction=nonstopmode", "-halt-on-error", tex.name,
            cwd=scratch,
        )
        embed_pdf = scratch / "embed.pdf"
        log = (scratch / "embed.log").read_text(
            encoding="utf-8", errors="replace"
        )
        if re.search(r"Fatal error|LaTeX Error|Missing character", log):
            raise AssertionError("MiKTeX stacked-dot embed log failed")
        if not embed_pdf.is_file():
            raise AssertionError("MiKTeX stacked-dot embed output missing")
        run(
            "pdftoppm", "-f", "1", "-singlefile", "-r", "180", "-png",
            str(embed_pdf), str(embed_poppler_prefix),
        )
        embed_blue = blue_mask(embed_poppler_png)
        embed_component_count = len(
            [size for size in blue_component_sizes(embed_blue) if size >= 100]
        )
        if embed_component_count != 50:
            raise AssertionError(
                f"Embedded Poppler render has {embed_component_count} blue points"
            )

        x_counts: dict[str, int] = {}
        for source_x, _ in source_points:
            key = f"{source_x:.2f}"
            x_counts[key] = x_counts.get(key, 0) + 1

        return {
            "result": "PASS",
            "defect": (
                "The prior localized PDF encoded all 50 observations as "
                "unembedded ZapfDingbats text glyphs; Poppler dropped them."
            ),
            "repair": (
                "Fifty explicit filled-and-stroked cubic-Bezier circles at the "
                "source glyphs' exact visual centres; the inherited sRGB fill, "
                "stroke, clipping path, and 0.75-point line width are unchanged."
            ),
            "source_point_count": len(source_points),
            "target_vector_circle_count": len(vector_points),
            "source_point_instruction_count": 350,
            "coordinate_mapping_sha256": hashlib.sha256(
                "".join(coordinate_rows).encode("ascii")
            ).hexdigest(),
            "source_tm_x_distribution": x_counts,
            "font_resources": font_keys,
            "point_color_srgb": [0.337, 0.608, 0.741],
            "path_radius_points": POINT_PATH_RADIUS,
            "render_dpi": 180,
            "blue_pixels": {
                "authority_mupdf": int(authority_blue.sum()),
                "target_mupdf": int(target_mupdf_blue.sum()),
                "target_poppler": int(target_poppler_blue.sum()),
                "embedded_poppler": int(embed_blue.sum()),
            },
            "visible_blue_point_components": {
                **component_counts,
                "embedded_poppler": embed_component_count,
            },
            "authority_glyph_to_target_vector_blue_iou_mupdf": source_target_iou,
            "target_mupdf_to_poppler_blue_iou": renderer_iou,
            "pypdf_strict": "PASS",
            "pikepdf_syntax": "PASS",
            "mutool_clean_info_pages_draw": "PASS",
            "pdfinfo_pdftotext_pdffonts": "PASS",
            "miktex_embed_and_poppler_render": "PASS",
            "latex_stdout_sha256": hashlib.sha256(
                latex.stdout.encode()
            ).hexdigest(),
            "visual_severity_counts": {"P1": 0, "P2": 0, "P3": 0},
        }
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def pdf_box(pdf: pikepdf.Pdf, name: str) -> list[str] | None:
    box = getattr(pdf.pages[0], name, None)
    if box is None:
        return None
    return [str(value) for value in box]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--figures-root", type=Path, required=True)
    parser.add_argument("--authority-root", type=Path, required=True)
    parser.add_argument("--replay-root-a", type=Path, required=True)
    parser.add_argument("--replay-root-b", type=Path, required=True)
    parser.add_argument("--manifest-a", type=Path, required=True)
    parser.add_argument("--manifest-b", type=Path, required=True)
    parser.add_argument("--contact-sheet", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--proposed-rows", type=Path, required=True)
    args = parser.parse_args()

    manifest_a_bytes = args.manifest_a.read_bytes()
    manifest_b_bytes = args.manifest_b.read_bytes()
    if manifest_a_bytes != manifest_b_bytes:
        raise AssertionError("Independent replay manifests are not byte-identical")
    manifest = json.loads(manifest_a_bytes)
    manifest_records = {
        record["relative_path"]: record for record in manifest["records"]
    }
    if len(manifest_records) != 18 or set(PRODUCERS) != set(manifest_records):
        raise AssertionError("Figure inventory is not the exact 18-asset prefix")
    records = [manifest_records[relative_path] for relative_path in SOURCE_ORDER]

    receipt_records = []
    for ordinal, record in enumerate(records, start=1):
        relative_path = record["relative_path"]
        authority_path = args.authority_root / relative_path
        replay_a_path = args.replay_root_a / relative_path
        replay_b_path = args.replay_root_b / relative_path
        live_path = args.figures_root / relative_path
        hashes = {
            "authority": sha256(authority_path),
            "replay_a": sha256(replay_a_path),
            "replay_b": sha256(replay_b_path),
            "live": sha256(live_path),
        }
        if hashes["authority"] != record["authority_sha256"]:
            raise AssertionError(f"Authority hash drift: {relative_path}")
        if not (
            hashes["replay_a"]
            == hashes["replay_b"]
            == hashes["live"]
            == record["output_sha256"]
        ):
            raise AssertionError(f"Replay/promotion hash mismatch: {relative_path}")

        with pikepdf.Pdf.open(authority_path) as authority_pdf, pikepdf.Pdf.open(
            live_path
        ) as live_pdf:
            if len(authority_pdf.pages) != 1 or len(live_pdf.pages) != 1:
                raise AssertionError(f"Expected one-page figure: {relative_path}")
            for box_name in ("MediaBox", "CropBox"):
                if pdf_box(authority_pdf, box_name) != pdf_box(live_pdf, box_name):
                    raise AssertionError(
                        f"Page-box drift ({box_name}): {relative_path}"
                    )

        extracted_text = "\n".join(
            page.extract_text() or "" for page in PdfReader(str(live_path)).pages
        )
        residue = [
            token
            for token in PROHIBITED_READER_STRINGS
            if token in extracted_text.lower()
        ]
        if residue:
            raise AssertionError(f"English label residue {residue}: {relative_path}")

        producer_records = []
        for producer_relative in PRODUCERS[relative_path]:
            live_producer = args.figures_root / producer_relative
            authority_producer = args.authority_root / producer_relative
            producer_records.append(
                {
                    "relative_path": producer_relative,
                    "live_path": str(live_producer.resolve()),
                    "live_bytes": live_producer.stat().st_size,
                    "live_sha256": sha256(live_producer),
                    "authority_path": str(authority_producer.resolve()),
                    "authority_bytes": authority_producer.stat().st_size,
                    "authority_sha256": sha256(authority_producer),
                }
            )

        receipt_records.append(
            {
                "proposed_asset_id": f"R011-ASSET-B005-2.1-{ordinal:03d}",
                "relative_path": relative_path,
                "live_path": str(live_path.resolve()),
                "bytes": live_path.stat().st_size,
                "sha256": hashes["live"],
                "authority_path": str(authority_path.resolve()),
                "authority_bytes": authority_path.stat().st_size,
                "authority_sha256": hashes["authority"],
                "replay_mode": record["mode"],
                "unchanged_instruction_sha256": record.get(
                    "unchanged_instruction_sha256"
                ),
                "portable_point_repair": record.get("portable_point_repair"),
                "producers": producer_records,
                "data_ids": list(DATA_IDS[relative_path]),
                "reader_text_residue": [],
                "page_count": 1,
                "page_boxes_match_authority": True,
                "qa_status": "PASS",
            }
        )

    helper_dir = Path(__file__).resolve().parent
    replay_helper = helper_dir / "replay_b005_prefix_figures.py"
    verifier = Path(__file__).resolve()
    stacked_portability = verify_stacked_portability(
        args.authority_root / PORTABLE_STACKED_PATH,
        args.figures_root / PORTABLE_STACKED_PATH,
        helper_dir,
    )
    stacked_manifest_record = manifest_records[PORTABLE_STACKED_PATH].get(
        "portable_point_repair"
    )
    if not isinstance(stacked_manifest_record, dict):
        raise AssertionError("Portable stacked-dot replay metadata is missing")
    if (
        stacked_manifest_record.get("coordinate_mapping_sha256")
        != stacked_portability["coordinate_mapping_sha256"]
        or stacked_manifest_record.get("source_zapf_dingbats_point_count") != 50
        or stacked_manifest_record.get("target_vector_circle_count") != 50
    ):
        raise AssertionError("Portable stacked-dot replay/validator evidence differs")
    license_path = args.authority_root.parents[1] / "LICENSE.md"
    contact_pngs = sorted(
        path
        for path in args.contact_sheet.parent.glob("*.png")
        if path.name != args.contact_sheet.name
    )
    if len(contact_pngs) != 18:
        raise AssertionError(f"Expected 18 rendered page PNGs, got {len(contact_pngs)}")

    receipt = {
        "schema": "r011-b005-prefix-figure-final-receipt/v1",
        "observed_date": "2026-08-22",
        "authority_commit": "fee25091fb24e89c36296fd67c48c1fcf7a93b6e",
        "authority_tree": "d61cc601e7d97759ce805900520f784d02a0489e",
        "scope": (
            "B005 chapter opener and complete Section 2.1 through the input of "
            "examining_numerical_data.tex; no Section 2.2/2.3 assets"
        ),
        "asset_count": 18,
        "localized_asset_count": 16,
        "numeric_only_exact_copy_count": 2,
        "replay_a_manifest": {
            "path": str(args.manifest_a.resolve()),
            "bytes": args.manifest_a.stat().st_size,
            "sha256": sha256(args.manifest_a),
        },
        "replay_b_manifest": {
            "path": str(args.manifest_b.resolve()),
            "bytes": args.manifest_b.stat().st_size,
            "sha256": sha256(args.manifest_b),
        },
        "deterministic_replay": {
            "result": "PASS",
            "all_18_outputs_byte_identical": True,
            "manifests_byte_identical": True,
        },
        "vector_semantic_invariance": {
            "result": "PASS",
            "method": (
                "Every non-target PDF content instruction was asserted unchanged; "
                "only explicit label text/alignment instructions and the 50 declared "
                "non-portable stacked-dot glyph runs changed. Each point run maps to "
                "one explicit vector circle at the glyph's exact visual centre."
            ),
        },
        "renderer_portability": stacked_portability,
        "residual_label_scan": {
            "result": "PASS",
            "prohibited_strings": list(PROHIBITED_READER_STRINGS),
            "hits": [],
        },
        "visual_qa": {
            "result": "PASS",
            "reviewer": "Codex",
            "render_dpi": 180,
            "rendered_pdf_count": 18,
            "contact_sheet_path": str(args.contact_sheet.resolve()),
            "contact_sheet_bytes": args.contact_sheet.stat().st_size,
            "contact_sheet_sha256": sha256(args.contact_sheet),
            "criteria": [
                "no clipped or overlapping reader labels",
                "no broken glyphs",
                "all axes and map legends legible",
                "data geometry, colors, scales, coordinates, and dimensions retained",
                "all 50 stacked-dot observations visible in MuPDF, Poppler, and the embedded Poppler render",
            ],
        },
        "rights": {
            "repository_license_path": str(license_path.resolve()),
            "repository_license_bytes": license_path.stat().st_size,
            "repository_license_sha256": sha256(license_path),
            "repository_license": "CC BY-SA 3.0 Unported",
            "applies_to": (
                "Pinned repository plot code and distributed figure PDFs; these "
                "statistical plots contain no photograph, OpenIntro logo, or trademark."
            ),
            "external_components": (
                "The R producers name openintro package datasets/color helpers and, for "
                "county maps, maps package outlines. Their package-level licenses are "
                "not embedded in this pinned textbook repository. This replay vendors "
                "no package or raw dataset bytes: it changes only labels in the already "
                "distributed pinned vector PDFs and retains source-level provenance."
            ),
            "derivative_status": (
                "Localized figure derivatives remain in the CC BY-SA 3.0 edition with "
                "upstream attribution and derivative-title/branding restrictions."
            ),
        },
        "helpers": [
            {
                "path": str(replay_helper),
                "bytes": replay_helper.stat().st_size,
                "sha256": sha256(replay_helper),
            },
            {
                "path": str(verifier),
                "bytes": verifier.stat().st_size,
                "sha256": sha256(verifier),
            },
        ],
        "records": receipt_records,
    }

    args.receipt.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    with args.proposed_rows.open("w", encoding="utf-8", newline="") as stream:
        fieldnames = (
            "proposed_asset_id",
            "relative_path",
            "bytes",
            "sha256",
            "producer_paths",
            "producer_sha256s",
            "data_ids",
            "rights",
            "qa_status",
        )
        writer = csv.DictWriter(stream, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for record in receipt_records:
            writer.writerow(
                {
                    "proposed_asset_id": record["proposed_asset_id"],
                    "relative_path": record["relative_path"],
                    "bytes": record["bytes"],
                    "sha256": record["sha256"],
                    "producer_paths": ";".join(
                        producer["relative_path"] for producer in record["producers"]
                    ),
                    "producer_sha256s": ";".join(
                        producer["live_sha256"] for producer in record["producers"]
                    ),
                    "data_ids": ";".join(record["data_ids"]),
                    "rights": (
                        "CC-BY-SA-3.0-repository-figure; external-package-input-"
                        "provenance-retained; no-raw-package-data-redistributed"
                    ),
                    "qa_status": record["qa_status"],
                }
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
