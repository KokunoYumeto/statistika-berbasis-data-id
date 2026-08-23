"""Regenerate and canonicalize the seven localized R011-B003 vector figures."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pikepdf


PIN = "fee25091fb24e89c36296fd67c48c1fcf7a93b6e"
OPENINTRO_PIN = "48793d9645e0da033daaca1c1a19a051533d79d2"
FIGURE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = FIGURE_ROOT.parents[1]
LANE_ROOT = REPO_ROOT.parent
AUTHORITY_ROOT = (
    LANE_ROOT / "authority" / "upstream" / f"openintro-statistics-{PIN}"
)
FACTBOOK = FIGURE_ROOT / "eoce" / "internet_life_expectancy" / "factbook.rda"
PHOTO = FIGURE_ROOT / "mnWinter" / "mnWinter.JPG"
EXPECTED_INPUTS = {
    FACTBOOK: "4843576c765049344074a81f258e33fd79fe3107fee7f026cebe469210253918",
    PHOTO: "9d24c2bc4cef7b6240ecba5fc2b1b501521de8c6f6543405ee5cf8f41b7de728",
}
PRODUCERS = (
    ("popToSample", "popToSampleGraduates.R", "popToSampleGraduates.pdf"),
    ("popToSample", "popToSubSampleGraduates.R", "popToSubSampleGraduates.pdf"),
    ("popToSample", "surveySample.R", "surveySample.pdf"),
    ("variables", "sunCausesCancer.R", "sunCausesCancer.pdf"),
    ("samplingMethodsFigure", "samplingMethodsFigures.R", "simple_stratified.pdf"),
    ("samplingMethodsFigure", "samplingMethodsFigures.R", "cluster_multistage.pdf"),
    (
        "eoce/internet_life_expectancy",
        "internet_life_expectancy.R",
        "internet_life_expectancy.pdf",
    ),
)
AUTHORITY_RELATIVE_PATHS = tuple(
    sorted(
        {
            Path(directory) / script_name
            for directory, script_name, _ in PRODUCERS
        }
        | {
            Path(directory) / output_name
            for directory, _, output_name in PRODUCERS
        }
        | {
            Path("samplingMethodsFigure/SamplingMethodsFunctions.R"),
            Path("eoce/internet_life_expectancy/factbook.rda"),
            Path("mnWinter/mnWinter.JPG"),
        },
        key=lambda path: path.as_posix(),
    )
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def resolve_rscript(argument: str | None) -> Path:
    candidate = argument or os.environ.get("RSCRIPT") or shutil.which("Rscript")
    if not candidate:
        raise RuntimeError("Rscript not found; pass --rscript or set RSCRIPT")
    path = Path(candidate).resolve()
    if not path.is_file():
        raise RuntimeError(f"Rscript does not exist: {path}")
    return path


def canonicalize_pdf(path: Path) -> None:
    temporary = path.with_suffix(".canonical.tmp.pdf")
    with pikepdf.Pdf.open(path) as pdf:
        info = pdf.docinfo
        for key in ("/CreationDate", "/ModDate", "/Producer", "/Creator"):
            if key in info:
                del info[key]
        info["/Title"] = path.stem
        info["/Subject"] = "Gambar OpenIntro Statistics yang dilokalkan ke Bahasa Indonesia"
        pdf.save(
            temporary,
            deterministic_id=True,
            compress_streams=True,
            object_stream_mode=pikepdf.ObjectStreamMode.disable,
        )
    temporary.replace(path)


def run_producers(rscript: Path, selected_outputs: set[str] | None) -> None:
    scripts_run: set[Path] = set()
    for directory, script_name, output_name in PRODUCERS:
        output_key = (Path(directory) / output_name).as_posix()
        if selected_outputs is not None and output_key not in selected_outputs:
            continue
        workdir = FIGURE_ROOT / Path(directory)
        script = workdir / script_name
        if script in scripts_run:
            continue
        subprocess.run(
            [str(rscript), "--vanilla", script.name],
            cwd=workdir,
            check=True,
        )
        scripts_run.add(script)


def validate_inputs() -> None:
    for path, expected in EXPECTED_INPUTS.items():
        actual = sha256(path)
        if actual != expected:
            raise RuntimeError(f"Input hash mismatch for {path}: {actual}")


def validate_outputs(
    canonicalize_outputs: set[str] | None,
) -> list[dict[str, object]]:
    outputs: list[dict[str, object]] = []
    for directory, script_name, output_name in PRODUCERS:
        workdir = FIGURE_ROOT / Path(directory)
        output = workdir / output_name
        if not output.is_file() or output.stat().st_size == 0:
            raise RuntimeError(f"Missing or empty output: {output}")
        output_key = (Path(directory) / output_name).as_posix()
        if canonicalize_outputs is None or output_key in canonicalize_outputs:
            canonicalize_pdf(output)
        with pikepdf.Pdf.open(output) as pdf:
            if len(pdf.pages) != 1:
                raise RuntimeError(f"Expected one-page figure: {output}")
            media_box = [float(value) for value in pdf.pages[0].mediabox]
        authority_output = AUTHORITY_ROOT / output.relative_to(REPO_ROOT)
        with pikepdf.Pdf.open(authority_output) as authority_pdf:
            authority_media_box = [
                float(value) for value in authority_pdf.pages[0].mediabox
            ]
        if media_box != authority_media_box:
            raise RuntimeError(f"Media box differs from authority: {output}")
        outputs.append(
            {
                "path": output.relative_to(REPO_ROOT).as_posix(),
                "producer": (workdir / script_name).relative_to(REPO_ROOT).as_posix(),
                "bytes": output.stat().st_size,
                "media_box_points": media_box,
                "authority_media_box_equal": True,
                "sha256": sha256(output),
            }
        )
    return outputs


def write_receipt(rscript: Path, outputs: list[dict[str, object]]) -> None:
    producer_paths = sorted(
        {
            FIGURE_ROOT / Path(directory) / script
            for directory, script, _ in PRODUCERS
        }
        | {
            FIGURE_ROOT / "samplingMethodsFigure" / "SamplingMethodsFunctions.R",
            FIGURE_ROOT / "b003_replay_helpers.R",
            Path(__file__).resolve(),
        },
        key=lambda path: path.as_posix(),
    )
    receipt = {
        "schema_version": "1.0.0",
        "boundary_id": "R011-B003",
        "authority": {
            "repository_commit": PIN,
            "openintro_r_package_commit": OPENINTRO_PIN,
        },
        "runtime": {
            "rscript": rscript.name,
            "r_version": subprocess.run(
                [str(rscript), "--version"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip(),
        },
        "immutable_inputs": [
            {
                "path": path.relative_to(REPO_ROOT).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": expected,
            }
            for path, expected in EXPECTED_INPUTS.items()
        ],
        "authority_files": [
            {
                "path": (Path("ch_intro_to_data/figures") / relative).as_posix(),
                "bytes": (AUTHORITY_ROOT / "ch_intro_to_data" / "figures" / relative).stat().st_size,
                "sha256": sha256(
                    AUTHORITY_ROOT / "ch_intro_to_data" / "figures" / relative
                ),
            }
            for relative in AUTHORITY_RELATIVE_PATHS
        ],
        "producer_sources": [
            {
                "path": path.relative_to(REPO_ROOT).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
            for path in producer_paths
        ],
        "outputs": outputs,
        "component_rights": [
            {
                "scope": "localized producer sources and generated figure PDFs",
                "license": "CC BY-SA 3.0 Unported",
                "basis": "repo/LICENSE.md",
            },
            {
                "scope": "b003_replay_helpers.R palette and minimal helper implementations",
                "license": "GPL-3.0-only",
                "basis": (
                    "openintro R package DESCRIPTION at commit "
                    f"{OPENINTRO_PIN}"
                ),
            },
            {
                "scope": "factbook.rda factual source data",
                "license": "public domain unless marked otherwise",
                "basis": "https://www.cia.gov/site-policies/",
                "note": "The embedded RDA carries no separate machine-readable license notice.",
            },
            {
                "scope": "mnWinter.JPG",
                "license": "CC BY-SA 3.0",
                "credit": "David M. Diez",
                "note": "Byte-identical source photograph; the localized caption carries the credit.",
            },
        ],
        "invariants": {
            "output_count": 7,
            "output_pages_each": 1,
            "rng_compatibility": "R 3.5.3",
            "factbook_rows": 259,
            "complete_internet_life_expectancy_rows": 208,
            "photo_rewritten": False,
            "localization_method": "producer-level regeneration; no text overlay",
            "population_diagrams": {
                "candidate_coordinate_pairs": 350,
                "population_seed": 52,
                "sample_seed_unrestricted": 50,
                "sample_seed_restricted": 7,
                "displayed_sample_points": 5,
            },
            "sampling_method_diagrams": {
                "seed": 4,
                "simple_random_population": 108,
                "simple_random_sample": 18,
                "strata": 6,
                "sampled_per_stratum": 3,
                "clusters": 9,
                "selected_clusters": [3, 4, 8],
                "multistage_sample_per_selected_cluster": 6,
            },
        },
    }
    receipt_path = FIGURE_ROOT / "B003_FIGURE_REPLAY.json"
    receipt_path.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rscript", help="Absolute path to Rscript")
    parser.add_argument(
        "--only",
        nargs="+",
        metavar="FIGURE_PATH",
        help="Regenerate only these paths relative to ch_intro_to_data/figures",
    )
    args = parser.parse_args()
    rscript = resolve_rscript(args.rscript)
    allowed = {
        (Path(directory) / output_name).as_posix()
        for directory, _, output_name in PRODUCERS
    }
    selected = None if args.only is None else {Path(value).as_posix() for value in args.only}
    if selected is not None:
        unknown = selected - allowed
        if unknown:
            raise RuntimeError(f"Unknown --only figure paths: {sorted(unknown)}")
    validate_inputs()
    run_producers(rscript, selected)
    outputs = validate_outputs(selected)
    write_receipt(rscript, outputs)
    print(json.dumps(outputs, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
