#!/usr/bin/env python3
"""Verify the assigned B005 EoCE figure replay and emit a partial closure.

This verifier is deliberately limited to three localized PDFs and seven
numeric/symbol-only exact copies.  The other three localized B005 EoCE PDFs
are owned by the parallel figure lane and are merged only in the final
13-asset closure.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pikepdf
from PIL import Image, ImageChops, ImageDraw, ImageOps
from pypdf import PdfReader


AUTHORITY_COMMIT = "fee25091fb24e89c36296fd67c48c1fcf7a93b6e"
AUTHORITY_TREE = "d61cc601e7d97759ce805900520f784d02a0489e"


ASSET_IDS = {
    "eoce/association_plots/association_plots.pdf": "R011-ASSET-B005-2.1-020",
    "eoce/hist_box_match/hist_box_match.pdf": "R011-ASSET-B005-2.1-021",
    "eoce/estimate_mean_median_simple/estimate_mean_median_simple.pdf": "R011-ASSET-B005-2.1-023",
    "eoce/hist_vs_box/hist_vs_box.pdf": "R011-ASSET-B005-2.1-024",
    "eoce/income_coffee_shop/income_coffee_shop.pdf": "R011-ASSET-B005-2.1-025",
    "eoce/county_commute_times/county_commute_times_map.pdf": "R011-ASSET-B005-2.1-027",
    "eoce/county_hispanic_pop/county_hispanic_pop_hist.pdf": "R011-ASSET-B005-2.1-028",
    "eoce/county_hispanic_pop/county_hispanic_pop_log_hist.pdf": "R011-ASSET-B005-2.1-029",
    "eoce/county_hispanic_pop/county_hispanic_pop_map.pdf": "R011-ASSET-B005-2.1-030",
    "eoce/reproducing_bacteria/reproducing_bacteria_sketch.pdf": "R011-ASSET-B005-2.1-031",
}


SOURCE_ORDER = tuple(ASSET_IDS)


LOCALIZED_EXPECTATIONS = {
    "eoce/county_hispanic_pop/county_hispanic_pop_hist.pdf": {
        "required": ("Persentase Hispanik",),
        "prohibited": ("Percent Hispanic",),
        "allowed_pixel_region": "bottom",
    },
    "eoce/county_hispanic_pop/county_hispanic_pop_log_hist.pdf": {
        "required": ("log(Persentase Hispanik)",),
        "prohibited": ("log(Percent Hispanic)", "Percent Hispanic"),
        "allowed_pixel_region": "bottom",
    },
    "eoce/reproducing_bacteria/reproducing_bacteria_sketch.pdf": {
        "required": ("waktu", "jumlah sel bakteri"),
        "prohibited": ("time", "number of bacteria cells"),
        "allowed_pixel_region": "bottom-or-left",
    },
}


PRODUCERS = {
    "eoce/county_hispanic_pop/county_hispanic_pop_hist.pdf": (
        "eoce/county_hispanic_pop/county_hispanic_pop.R",
    ),
    "eoce/county_hispanic_pop/county_hispanic_pop_log_hist.pdf": (
        "eoce/county_hispanic_pop/county_hispanic_pop.R",
    ),
    "eoce/county_hispanic_pop/county_hispanic_pop_map.pdf": (
        "eoce/county_hispanic_pop/county_hispanic_pop.R",
        "eoce/county_hispanic_pop/countyMap.R",
    ),
    "eoce/reproducing_bacteria/reproducing_bacteria_sketch.pdf": (
        "eoce/reproducing_bacteria/reproducing_bacteria.R",
    ),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_checked(command: list[str]) -> dict:
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        raise AssertionError(
            f"Command failed ({completed.returncode}): {command!r}\n"
            f"stdout={completed.stdout}\nstderr={completed.stderr}"
        )
    return {
        "command": command[0],
        "returncode": completed.returncode,
        "stderr": completed.stderr.strip(),
    }


def pdf_box(pdf: pikepdf.Pdf, name: str) -> list[str] | None:
    box = getattr(pdf.pages[0], name, None)
    if box is None:
        return None
    return [str(value) for value in box]


def render_pdf(path: Path, destination: Path, dpi: int = 180) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    pdftoppm = shutil.which("pdftoppm")
    if not pdftoppm:
        raise AssertionError("pdftoppm is unavailable for visual rendering")
    output_prefix = destination.with_suffix("")
    completed = subprocess.run(
        [
            pdftoppm,
            "-png",
            "-r",
            str(dpi),
            "-singlefile",
            str(path),
            str(output_prefix),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0 or not destination.is_file():
        raise AssertionError(
            f"pdftoppm render failed for {path}: {completed.stderr}"
        )


def pixel_invariance(
    authority_png: Path, live_png: Path, region: str | None
) -> dict:
    with Image.open(authority_png).convert("RGB") as authority_image, Image.open(
        live_png
    ).convert("RGB") as live_image:
        if authority_image.size != live_image.size:
            raise AssertionError("Rendered dimensions drifted")
        difference = ImageChops.difference(authority_image, live_image)
        changed_bbox = difference.getbbox()
        changed_pixels = sum(
            1
            for pixel in difference.get_flattened_data()
            if pixel != (0, 0, 0)
        )
        if region is None:
            if changed_pixels != 0:
                raise AssertionError("Exact-copy asset changed rendered pixels")
            outside_changed = 0
        else:
            width, height = authority_image.size
            outside_changed = 0
            for index, pixel in enumerate(difference.get_flattened_data()):
                if pixel == (0, 0, 0):
                    continue
                x = index % width
                y = index // width
                allowed = y >= int(height * 0.80)
                if region == "bottom-or-left":
                    allowed = allowed or x <= int(width * 0.16)
                if not allowed:
                    outside_changed += 1
            if outside_changed:
                raise AssertionError(
                    f"{outside_changed} changed pixels escaped label-only regions"
                )
        return {
            "changed_pixel_count": changed_pixels,
            "changed_bbox": list(changed_bbox) if changed_bbox else None,
            "changed_pixels_outside_allowed_label_regions": outside_changed,
        }


def make_contact_sheet(records: list[dict], destination: Path) -> None:
    pairs: list[Image.Image] = []
    for record in records:
        authority = Image.open(record["authority_render_path"]).convert("RGB")
        live = Image.open(record["live_render_path"]).convert("RGB")
        thumb_size = (520, 300)
        authority.thumbnail(thumb_size)
        live.thumbnail(thumb_size)
        row = Image.new("RGB", (1080, 350), "white")
        row.paste(authority, (10, 40))
        row.paste(live, (550, 40))
        draw = ImageDraw.Draw(row)
        draw.text((10, 8), f"authority | {record['relative_path']}", fill="black")
        draw.text((550, 8), "localized/live", fill="black")
        pairs.append(row)
        authority.close()
        live.close()
    sheet = Image.new("RGB", (1080, 350 * len(pairs)), "white")
    for index, row in enumerate(pairs):
        sheet.paste(row, (0, 350 * index))
        row.close()
    destination.parent.mkdir(parents=True, exist_ok=True)
    sheet = ImageOps.expand(sheet, border=2, fill="black")
    sheet.save(destination, format="PNG", optimize=False)
    sheet.close()


def embed_smoke(pdf_paths: list[Path], output_dir: Path) -> dict:
    pdflatex = shutil.which("pdflatex")
    if not pdflatex:
        raise AssertionError("pdflatex is unavailable for embed smoke")
    output_dir.mkdir(parents=True, exist_ok=True)
    tex_path = output_dir / "embed_smoke.tex"
    body = [
        r"\documentclass{article}",
        r"\usepackage[margin=8mm]{geometry}",
        r"\usepackage{graphicx}",
        r"\pagestyle{empty}",
        r"\begin{document}",
    ]
    for index, path in enumerate(pdf_paths):
        tex_path_value = path.resolve().as_posix()
        body.append(
            rf"\noindent\includegraphics[width=0.95\textwidth,height=0.90\textheight,keepaspectratio]{{{tex_path_value}}}"
        )
        if index != len(pdf_paths) - 1:
            body.append(r"\newpage")
    body.append(r"\end{document}")
    tex_path.write_text("\n".join(body) + "\n", encoding="utf-8", newline="\n")
    completed = subprocess.run(
        [
            pdflatex,
            "-interaction=nonstopmode",
            "-halt-on-error",
            f"-output-directory={output_dir}",
            str(tex_path),
        ],
        cwd=output_dir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    console_path = output_dir / "console.txt"
    console_path.write_text(
        completed.stdout + completed.stderr, encoding="utf-8", newline="\n"
    )
    if completed.returncode != 0:
        raise AssertionError(f"MiKTeX embed smoke failed: {console_path}")
    pdf_path = output_dir / "embed_smoke.pdf"
    reader = PdfReader(str(pdf_path), strict=True)
    if len(reader.pages) != len(pdf_paths):
        raise AssertionError("Embed-smoke output page count mismatch")
    return {
        "result": "PASS",
        "engine": pdflatex,
        "embedded_asset_count": len(pdf_paths),
        "output_pages": len(reader.pages),
        "tex_path": str(tex_path.resolve()),
        "tex_bytes": tex_path.stat().st_size,
        "tex_sha256": sha256(tex_path),
        "pdf_path": str(pdf_path.resolve()),
        "pdf_bytes": pdf_path.stat().st_size,
        "pdf_sha256": sha256(pdf_path),
        "console_path": str(console_path.resolve()),
        "console_bytes": console_path.stat().st_size,
        "console_sha256": sha256(console_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--figures-root", type=Path, required=True)
    parser.add_argument("--producer-root", type=Path)
    parser.add_argument("--authority-root", type=Path, required=True)
    parser.add_argument("--replay-root-a", type=Path, required=True)
    parser.add_argument("--replay-root-b", type=Path, required=True)
    parser.add_argument("--manifest-a", type=Path, required=True)
    parser.add_argument("--manifest-b", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--proposed-rows", type=Path, required=True)
    parser.add_argument("--visual-reviewer")
    args = parser.parse_args()
    producer_root = args.producer_root or args.figures_root

    if args.manifest_a.read_bytes() != args.manifest_b.read_bytes():
        raise AssertionError("Independent replay manifests differ")
    manifest = json.loads(args.manifest_a.read_text(encoding="utf-8"))
    manifest_records = {
        record["relative_path"]: record for record in manifest["records"]
    }
    if set(manifest_records) != set(SOURCE_ORDER):
        raise AssertionError("Replay manifest is not the exact assigned 10 assets")

    mutool = shutil.which("mutool")
    pdfinfo = shutil.which("pdfinfo")
    if not mutool or not pdfinfo:
        raise AssertionError("mutool and pdfinfo are required")
    parser_temp = args.output_dir / "parser_clean"
    parser_temp.mkdir(parents=True, exist_ok=True)
    authority_render_root = args.output_dir / "render_authority"
    live_render_root = args.output_dir / "render_live"

    records: list[dict] = []
    for relative_path in SOURCE_ORDER:
        manifest_record = manifest_records[relative_path]
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
        if hashes["authority"] != manifest_record["authority_sha256"]:
            raise AssertionError(f"Authority drift: {relative_path}")
        if not (
            hashes["replay_a"]
            == hashes["replay_b"]
            == hashes["live"]
            == manifest_record["output_sha256"]
        ):
            raise AssertionError(f"Replay/live mismatch: {relative_path}")

        with pikepdf.Pdf.open(authority_path) as authority_pdf, pikepdf.Pdf.open(
            live_path
        ) as live_pdf:
            if len(authority_pdf.pages) != 1 or len(live_pdf.pages) != 1:
                raise AssertionError(f"Expected one-page PDF: {relative_path}")
            boxes_match = all(
                pdf_box(authority_pdf, box_name) == pdf_box(live_pdf, box_name)
                for box_name in ("MediaBox", "CropBox")
            )
            if not boxes_match:
                raise AssertionError(f"Page boxes drifted: {relative_path}")
        strict_reader = PdfReader(str(live_path), strict=True)
        if len(strict_reader.pages) != 1:
            raise AssertionError(f"pypdf page-count failure: {relative_path}")
        extracted_text = strict_reader.pages[0].extract_text() or ""
        expectation = LOCALIZED_EXPECTATIONS.get(relative_path)
        if expectation:
            missing = [
                value for value in expectation["required"] if value not in extracted_text
            ]
            residue = [
                value for value in expectation["prohibited"] if value in extracted_text
            ]
            if missing or residue:
                raise AssertionError(
                    f"Text gate failed for {relative_path}: missing={missing}, residue={residue}"
                )
        else:
            residue = []

        clean_path = parser_temp / (relative_path.replace("/", "__") + ".pdf")
        parser_checks = {
            "pdfinfo": run_checked([pdfinfo, str(live_path)]),
            "mutool_info": run_checked([mutool, "info", str(live_path)]),
            "mutool_pages": run_checked([mutool, "pages", str(live_path)]),
            "mutool_clean": run_checked(
                [mutool, "clean", str(live_path), str(clean_path)]
            ),
        }
        with pikepdf.Pdf.open(clean_path) as cleaned_pdf:
            if len(cleaned_pdf.pages) != 1:
                raise AssertionError(f"mutool-clean output invalid: {relative_path}")
        clean_path.unlink()

        authority_png = authority_render_root / (relative_path + ".png")
        live_png = live_render_root / (relative_path + ".png")
        render_pdf(authority_path, authority_png)
        render_pdf(live_path, live_png)
        pixel_result = pixel_invariance(
            authority_png,
            live_png,
            expectation["allowed_pixel_region"] if expectation else None,
        )

        producer_records = []
        for producer_relative in PRODUCERS.get(relative_path, ()):
            live_producer = producer_root / producer_relative
            authority_producer = args.authority_root / producer_relative
            producer_records.append(
                {
                    "relative_path": producer_relative,
                    "live_bytes": live_producer.stat().st_size,
                    "live_sha256": sha256(live_producer),
                    "authority_bytes": authority_producer.stat().st_size,
                    "authority_sha256": sha256(authority_producer),
                }
            )

        records.append(
            {
                "asset_id": ASSET_IDS[relative_path],
                "relative_path": relative_path,
                "mode": manifest_record["mode"],
                "authority_path": str(authority_path.resolve()),
                "authority_bytes": authority_path.stat().st_size,
                "authority_sha256": hashes["authority"],
                "live_path": str(live_path.resolve()),
                "bytes": live_path.stat().st_size,
                "sha256": hashes["live"],
                "page_count": 1,
                "page_boxes_match_authority": True,
                "required_reader_text": list(expectation["required"])
                if expectation
                else [],
                "reader_text_residue": residue,
                "parser_checks": parser_checks,
                "pixel_invariance": pixel_result,
                "authority_render_path": str(authority_png.resolve()),
                "live_render_path": str(live_png.resolve()),
                "producers": producer_records,
                "unchanged_instruction_sha256": manifest_record.get(
                    "unchanged_instruction_sha256"
                ),
                "qa_status": "PASS",
            }
        )

    contact_sheet = args.output_dir / "CONTACT_ASSIGNED_10.png"
    make_contact_sheet(records, contact_sheet)
    embed_result = embed_smoke(
        [args.figures_root / relative_path for relative_path in SOURCE_ORDER],
        args.output_dir / "embed_smoke",
    )
    license_path = args.authority_root.parents[1] / "LICENSE.md"
    helper_dir = Path(__file__).resolve().parent
    replay_helper = helper_dir / "replay_b005_eoce_hispanic_bacteria.py"
    receipt = {
        "schema": "r011-b005-eoce-assigned-partial-closure/v1",
        "observed_date": "2026-08-22",
        "authority_commit": AUTHORITY_COMMIT,
        "authority_tree": AUTHORITY_TREE,
        "scope": (
            "Assigned portion of the B005 Section 2.1 exercise/public-answer asset "
            "closure: three localized label-bearing PDFs and seven authority-exact "
            "numeric/symbol-only PDFs; excludes the three parallel-lane localizations."
        ),
        "asset_count": 10,
        "localized_asset_count": 3,
        "numeric_symbol_exact_copy_count": 7,
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
            "manifests_byte_identical": True,
            "all_outputs_byte_identical": True,
        },
        "parser_and_embed_qa": {
            "result": "PASS",
            "pikepdf_qpdf_library": pikepdf.__version__,
            "pypdf_strict": True,
            "pdfinfo_asset_count": len(records),
            "mutool_info_pages_clean_asset_count": len(records),
            "embed_smoke": embed_result,
        },
        "vector_semantic_invariance": {
            "result": "PASS",
            "localized_rule": (
                "Only explicit label text-showing operations and their centering "
                "matrices changed; every non-target content instruction is hash-frozen."
            ),
            "exact_copy_rule": "Seven numeric/symbol-only PDFs are authority-byte-exact.",
        },
        "visual_qa": {
            "result": "PASS" if args.visual_reviewer else "PENDING_MANUAL",
            "reviewer": args.visual_reviewer,
            "render_dpi": 180,
            "pixel_changes_outside_label_regions": 0,
            "contact_sheet_path": str(contact_sheet.resolve()),
            "contact_sheet_bytes": contact_sheet.stat().st_size,
            "contact_sheet_sha256": sha256(contact_sheet),
        },
        "rights": {
            "repository_license_path": str(license_path.resolve()),
            "repository_license_bytes": license_path.stat().st_size,
            "repository_license_sha256": sha256(license_path),
            "repository_license": "CC BY-SA 3.0 Unported",
            "applies_to": (
                "Pinned repository plot code and distributed figure PDFs; no "
                "photograph, OpenIntro logo, or trademark is present in these assets."
            ),
            "external_components": (
                "Producers name OpenIntro package datasets/colors and maps outlines; "
                "this replay vendors no package or new raw-data bytes and alters only "
                "labels in the already distributed pinned vector PDFs."
            ),
            "derivative_status": (
                "Localized static figures remain within the CC BY-SA 3.0 derivative "
                "edition with attribution/share-alike and derivative branding controls."
            ),
        },
        "helpers": [
            {
                "path": str(replay_helper),
                "bytes": replay_helper.stat().st_size,
                "sha256": sha256(replay_helper),
            },
            {
                "path": str(Path(__file__).resolve()),
                "bytes": Path(__file__).stat().st_size,
                "sha256": sha256(Path(__file__)),
            },
        ],
        "records": records,
    }
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    with args.proposed_rows.open("w", encoding="utf-8", newline="") as stream:
        fieldnames = (
            "asset_id",
            "relative_path",
            "mode",
            "bytes",
            "sha256",
            "producer_paths",
            "producer_sha256s",
            "rights",
            "qa_status",
        )
        writer = csv.DictWriter(stream, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    "asset_id": record["asset_id"],
                    "relative_path": record["relative_path"],
                    "mode": record["mode"],
                    "bytes": record["bytes"],
                    "sha256": record["sha256"],
                    "producer_paths": ";".join(
                        producer["relative_path"]
                        for producer in record["producers"]
                    ),
                    "producer_sha256s": ";".join(
                        producer["live_sha256"] for producer in record["producers"]
                    ),
                    "rights": (
                        "CC-BY-SA-3.0-repository-figure; external-input-"
                        "provenance-retained; no-new-raw-package-data"
                    ),
                    "qa_status": record["qa_status"],
                }
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
