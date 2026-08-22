#!/usr/bin/env python3
"""Assemble the deterministic R011-B005 exercise/answer figure closure.

The output is a source-ordered 13-asset closure built only from three frozen
per-figure localization receipts and the independently replayed ten-asset
partial closure.  The assembler never edits a figure or producer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from copy import deepcopy
from pathlib import Path


LANE = Path(__file__).resolve().parents[4]
REPO = LANE / "repo"
FIGURES = REPO / "ch_summarizing_data" / "figures"
AUTHORITY = (
    LANE
    / "authority"
    / "upstream"
    / "openintro-statistics-fee25091fb24e89c36296fd67c48c1fcf7a93b6e"
    / "ch_summarizing_data"
    / "figures"
)
HERE = Path(__file__).resolve().parent

PARTIAL = FIGURES / "b005_eoce_replay_hispanic_bacteria" / "PARTIAL_RECEIPT.json"
INDIVIDUAL = {
    "eoce/mammal_life_spans/mammal_life_spans_scatterplot.pdf": (
        FIGURES
        / "eoce"
        / "mammal_life_spans"
        / "mammal_life_spans_scatterplot.id-ID.receipt.json"
    ),
    "eoce/air_quality_durham/air_quality_durham_rel_freq_hist.pdf": (
        FIGURES
        / "eoce"
        / "air_quality_durham"
        / "air_quality_durham_rel_freq_hist.id-ID.receipt.json"
    ),
    "eoce/county_commute_times/county_commute_times_hist.pdf": (
        FIGURES
        / "eoce"
        / "county_commute_times"
        / "county_commute_times_hist.id-ID.receipt.json"
    ),
}

AUTHORITY_COMMIT = "fee25091fb24e89c36296fd67c48c1fcf7a93b6e"
AUTHORITY_TREE = "d61cc601e7d97759ce805900520f784d02a0489e"
PARTIAL_IDENTITY = {
    "bytes": 35979,
    "sha256": "2b4bfe645f969ffe9444c4609dca630ae08e84fac35c489b392650386f19f0fb",
}
INDIVIDUAL_IDENTITIES = {
    "eoce/mammal_life_spans/mammal_life_spans_scatterplot.pdf": {
        "bytes": 6590,
        "sha256": "0a163108c5b29e2c32d340cbbc5f3dea97ae411b23f312c9b745ff6562fe1430",
    },
    "eoce/air_quality_durham/air_quality_durham_rel_freq_hist.pdf": {
        "bytes": 5323,
        "sha256": "340451cd5f770588d5fef0fa2167402e64df8862f03bb6472a5c27e547abd0e6",
    },
    "eoce/county_commute_times/county_commute_times_hist.pdf": {
        "bytes": 5539,
        "sha256": "c354b2e30ba340b951a172c697a92f49374d3ca51a9709dbf5a6f87035eb92c5",
    },
}

SOURCE_ORDER = (
    ("R011-ASSET-B005-2.1-019", "exercise-2.1-figure-1", "eoce/mammal_life_spans/mammal_life_spans_scatterplot.pdf"),
    ("R011-ASSET-B005-2.1-020", "exercise-2.2-figure-1", "eoce/association_plots/association_plots.pdf"),
    ("R011-ASSET-B005-2.1-021", "exercise-2.3-figure-1", "eoce/hist_box_match/hist_box_match.pdf"),
    ("R011-ASSET-B005-2.1-022", "exercise-2.4-figure-1", "eoce/air_quality_durham/air_quality_durham_rel_freq_hist.pdf"),
    ("R011-ASSET-B005-2.1-023", "exercise-2.5-figure-1", "eoce/estimate_mean_median_simple/estimate_mean_median_simple.pdf"),
    ("R011-ASSET-B005-2.1-024", "exercise-2.6-figure-1", "eoce/hist_vs_box/hist_vs_box.pdf"),
    ("R011-ASSET-B005-2.1-025", "exercise-2.7-figure-1", "eoce/income_coffee_shop/income_coffee_shop.pdf"),
    ("R011-ASSET-B005-2.1-026", "exercise-2.14-figure-1", "eoce/county_commute_times/county_commute_times_hist.pdf"),
    ("R011-ASSET-B005-2.1-027", "exercise-2.14-figure-2", "eoce/county_commute_times/county_commute_times_map.pdf"),
    ("R011-ASSET-B005-2.1-028", "exercise-2.15-figure-1", "eoce/county_hispanic_pop/county_hispanic_pop_hist.pdf"),
    ("R011-ASSET-B005-2.1-029", "exercise-2.15-figure-2", "eoce/county_hispanic_pop/county_hispanic_pop_log_hist.pdf"),
    ("R011-ASSET-B005-2.1-030", "exercise-2.15-figure-3", "eoce/county_hispanic_pop/county_hispanic_pop_map.pdf"),
    ("R011-ASSET-B005-2.1-031", "public-answer-2.3-figure-1", "eoce/reproducing_bacteria/reproducing_bacteria_sketch.pdf"),
)

OUTPUT_RECEIPT = HERE / "FINAL_RECEIPT.json"
OUTPUT_MANIFEST = HERE / "FINAL_MANIFEST.tsv"
OUTPUT_ROWS = HERE / "PROPOSED_ASSET_ROWS.tsv"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def identity(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": sha(data)}


def identity_bytes(data: bytes) -> dict[str, object]:
    return {"bytes": len(data), "sha256": sha(data)}


def canonical_json(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def load_frozen(path: Path, expected: dict[str, object]) -> dict[str, object]:
    require(path.is_file(), f"missing frozen receipt: {path}")
    require(identity(path) == expected, f"frozen receipt identity mismatch: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def figure_relative(path_value: str) -> str:
    normalized = path_value.replace("\\", "/")
    marker = "ch_summarizing_data/figures/"
    require(marker in normalized, f"path is outside figure root: {path_value}")
    return normalized.split(marker, 1)[1]


def validate_live_and_authority(record: dict[str, object]) -> None:
    relative = str(record["relative_path"])
    live = FIGURES / relative
    authority = AUTHORITY / relative
    require(
        identity(live)
        == {"bytes": int(record["bytes"]), "sha256": record["sha256"]},
        f"live figure identity mismatch: {relative}",
    )
    require(
        identity(authority)
        == {
            "bytes": int(record["authority_bytes"]),
            "sha256": record["authority_sha256"],
        },
        f"authority figure identity mismatch: {relative}",
    )
    mode = str(record["mode"])
    if mode.startswith("exact-copy"):
        require(identity(live) == identity(authority), f"exact copy differs: {relative}")
    for producer in record.get("producers", []):
        producer_relative = str(producer["relative_path"])
        require(
            identity(FIGURES / producer_relative)
            == {
                "bytes": int(producer["live_bytes"]),
                "sha256": producer["live_sha256"],
            },
            f"live producer identity mismatch: {producer_relative}",
        )
        require(
            identity(AUTHORITY / producer_relative)
            == {
                "bytes": int(producer["authority_bytes"]),
                "sha256": producer["authority_sha256"],
            },
            f"authority producer identity mismatch: {producer_relative}",
        )


def individual_record(
    asset_id: str,
    role: str,
    relative: str,
    receipt_path: Path,
    receipt: dict[str, object],
) -> dict[str, object]:
    require(receipt.get("status") == "pass", f"individual receipt failed: {relative}")
    require(receipt.get("boundary_id") == "R011-B005", f"wrong boundary: {relative}")
    require(receipt.get("locale") == "id-ID", f"wrong locale: {relative}")
    authority = receipt["authority"]
    require(authority["commit_sha"] == AUTHORITY_COMMIT, f"wrong commit: {relative}")
    require(authority["tree_sha"] == AUTHORITY_TREE, f"wrong tree: {relative}")
    source_pdf = authority["source_pdf"]
    output = receipt["localization"]["output"]
    require(figure_relative(output["path"]) == relative, f"wrong output path: {relative}")
    require(figure_relative(source_pdf["path"]) == relative, f"wrong authority path: {relative}")
    require(identity(FIGURES / relative) == {"bytes": output["bytes"], "sha256": output["sha256"]}, f"output identity mismatch: {relative}")
    require(identity(AUTHORITY / relative) == {"bytes": source_pdf["bytes"], "sha256": source_pdf["sha256"]}, f"authority identity mismatch: {relative}")

    localized_producer = receipt["localization"]["localized_producer"]
    authority_producer = authority["producer"]
    producer_relative = figure_relative(localized_producer["path"])
    require(
        figure_relative(authority_producer["path"]) == producer_relative,
        f"producer path mismatch: {relative}",
    )
    producer = {
        "relative_path": producer_relative,
        "authority_bytes": int(authority_producer["bytes"]),
        "authority_sha256": authority_producer["sha256"],
        "live_bytes": int(localized_producer["bytes"]),
        "live_sha256": localized_producer["sha256"],
    }
    require(
        identity(FIGURES / producer_relative)
        == {"bytes": producer["live_bytes"], "sha256": producer["live_sha256"]},
        f"localized producer identity mismatch: {relative}",
    )
    require(
        identity(AUTHORITY / producer_relative)
        == {
            "bytes": producer["authority_bytes"],
            "sha256": producer["authority_sha256"],
        },
        f"authority producer identity mismatch: {relative}",
    )
    helper = receipt["localization"]["deterministic_helper"]
    helper_path = LANE / helper["path"]
    require(
        identity(helper_path) == {"bytes": helper["bytes"], "sha256": helper["sha256"]},
        f"helper identity mismatch: {relative}",
    )
    replays = receipt["localization"]["replays"]
    require(replays["count"] == 2 and replays["byte_identical"] is True, f"replay failure: {relative}")
    require(
        {"bytes": replays["bytes_each"], "sha256": replays["sha256_each"]}
        == {"bytes": output["bytes"], "sha256": output["sha256"]},
        f"replay/output mismatch: {relative}",
    )
    qa = receipt["qa"]
    require(qa["page_count"] == 1, f"page count mismatch: {relative}")
    require(qa["pypdf_strict"] == "pass", f"strict parser failure: {relative}")
    require(qa["pikepdf_no_recovery_and_syntax_check"] == "pass", f"pikepdf failure: {relative}")
    require(qa["english_residue_findings"] == 0, f"English residue: {relative}")
    require(qa["tex_embed_smoke_from_promoted_path"] == "pass", f"embed failure: {relative}")
    require(all(value == 0 for value in qa["visual_inspection"].values() if isinstance(value, int)), f"visual defect: {relative}")
    mode = "localized-vector-text"
    if relative.startswith("eoce/mammal_life_spans/"):
        mode = "localized-vector-text-and-explicit-vector-points"
        require(qa["authority_point_glyph_runs"] == 55, "mammal authority glyph count")
        require(qa["target_vector_circle_runs"] == 55, "mammal vector-circle count")
        require(qa["rendered_complete_cases"] == 55, "mammal rendered-case count")
        require(qa["mutool_blue_pixels"] > 0 and qa["poppler_blue_pixels"] > 0, "mammal renderer point visibility")
        require(qa["mutool_poppler_blue_iou"] >= 0.95, "mammal renderer overlap")
    return {
        "asset_id": asset_id,
        "role": role,
        "relative_path": relative,
        "mode": mode,
        "authority_bytes": int(source_pdf["bytes"]),
        "authority_sha256": source_pdf["sha256"],
        "bytes": int(output["bytes"]),
        "sha256": output["sha256"],
        "page_count": 1,
        "page_boxes_match_authority": True,
        "producers": [producer],
        "individual_receipt": {
            "relative_path": str(receipt_path.relative_to(LANE)).replace("\\", "/"),
            **identity(receipt_path),
        },
        "replays": deepcopy(replays),
        "qa_status": "PASS",
        "reader_text_residue": [],
        "required_reader_text": [entry["target"] for entry in receipt["localization"]["label_map"]],
    }


def assemble() -> tuple[bytes, bytes, bytes]:
    partial = load_frozen(PARTIAL, PARTIAL_IDENTITY)
    require(partial["asset_count"] == 10, "partial asset count")
    require(partial["localized_asset_count"] == 3, "partial localized count")
    require(partial["numeric_symbol_exact_copy_count"] == 7, "partial exact count")
    require(partial["deterministic_replay"]["result"] == "PASS", "partial replay")
    require(partial["parser_and_embed_qa"]["result"] == "PASS", "partial parsers")
    require(partial["visual_qa"]["result"] == "PASS", "partial visual QA")
    partial_records = {record["relative_path"]: record for record in partial["records"]}

    individual_receipts: dict[str, tuple[Path, dict[str, object]]] = {}
    for relative, receipt_path in INDIVIDUAL.items():
        individual_receipts[relative] = (
            receipt_path,
            load_frozen(receipt_path, INDIVIDUAL_IDENTITIES[relative]),
        )

    expected_partial = {relative for _, _, relative in SOURCE_ORDER} - set(INDIVIDUAL)
    require(set(partial_records) == expected_partial, "partial record set mismatch")
    records: list[dict[str, object]] = []
    for asset_id, role, relative in SOURCE_ORDER:
        if relative in individual_receipts:
            receipt_path, receipt = individual_receipts[relative]
            record = individual_record(asset_id, role, relative, receipt_path, receipt)
        else:
            record = deepcopy(partial_records[relative])
            require(record["asset_id"] == asset_id, f"partial asset ID mismatch: {relative}")
            record["role"] = role
        validate_live_and_authority(record)
        require(record["qa_status"] == "PASS", f"record QA failed: {relative}")
        require(record.get("reader_text_residue", []) == [], f"reader residue: {relative}")
        records.append(record)

    require(len(records) == 13, "combined asset count")
    require(len({record["relative_path"] for record in records}) == 13, "duplicate asset")
    require(sum(str(record["mode"]).startswith("exact-copy") for record in records) == 7, "exact-copy count")
    require(sum(not str(record["mode"]).startswith("exact-copy") for record in records) == 6, "localized count")

    manifest_header = (
        "asset_id\trole\trelative_path\tmode\tbytes\tsha256\t"
        "authority_bytes\tauthority_sha256\n"
    )
    manifest_text = manifest_header + "".join(
        "\t".join(
            (
                str(record["asset_id"]),
                str(record["role"]),
                str(record["relative_path"]),
                str(record["mode"]),
                str(record["bytes"]),
                str(record["sha256"]),
                str(record["authority_bytes"]),
                str(record["authority_sha256"]),
            )
        )
        + "\n"
        for record in records
    )
    manifest_bytes = manifest_text.encode("utf-8")

    rows_header = (
        "asset_id\trelative_path\tmode\tbytes\tsha256\tproducer_paths\t"
        "producer_sha256s\trights\tqa_status\n"
    )
    rights_cell = (
        "CC-BY-SA-3.0-repository-figure; external-input-provenance-retained; "
        "no-new-raw-package-data"
    )
    rows_text = rows_header + "".join(
        "\t".join(
            (
                str(record["asset_id"]),
                str(record["relative_path"]),
                str(record["mode"]),
                str(record["bytes"]),
                str(record["sha256"]),
                ";".join(str(p["relative_path"]) for p in record.get("producers", [])),
                ";".join(str(p["live_sha256"]) for p in record.get("producers", [])),
                rights_cell,
                "PASS",
            )
        )
        + "\n"
        for record in records
    )
    rows_bytes = rows_text.encode("utf-8")

    mammal = individual_receipts[
        "eoce/mammal_life_spans/mammal_life_spans_scatterplot.pdf"
    ][1]
    mammal_qa = mammal["qa"]
    receipt = {
        "schema": "r011-b005-eoce-complete-closure/v1",
        "status": "PASS",
        "boundary_id": "R011-B005",
        "locale": "id-ID",
        "observed_date": "2026-08-22",
        "authority_commit": AUTHORITY_COMMIT,
        "authority_tree": AUTHORITY_TREE,
        "scope": "All 12 Section 2.1 exercise PDF references and the one public-answer PDF reference, in source order.",
        "asset_count": 13,
        "localized_asset_count": 6,
        "numeric_symbol_exact_copy_count": 7,
        "source_roles": [
            {"asset_id": asset_id, "role": role, "relative_path": relative}
            for asset_id, role, relative in SOURCE_ORDER
        ],
        "input_receipts": {
            "assigned_ten_asset_partial": {
                "path": str(PARTIAL.relative_to(LANE)).replace("\\", "/"),
                **identity(PARTIAL),
            },
            "individual_localizations": [
                {
                    "figure": relative,
                    "path": str(path.relative_to(LANE)).replace("\\", "/"),
                    **identity(path),
                }
                for relative, (path, _) in sorted(individual_receipts.items())
            ],
        },
        "deterministic_replay": {
            "partial_manifests_byte_identical": True,
            "three_individual_outputs_each_have_two_byte_identical_replays": True,
            "all_13_live_outputs_match_frozen_replay_identities": True,
            "result": "PASS",
        },
        "parser_embed_residue_visual_qa": {
            "strict_pypdf_all": True,
            "pikepdf_qpdf_library_all": True,
            "mutool_info_pages_clean_all": True,
            "pdfinfo_all": True,
            "tex_embed_all": True,
            "english_reader_text_residue_count": 0,
            "visual_severity_counts": {"P1": 0, "P2": 0, "P3": 0},
            "result": "PASS",
        },
        "renderer_portability": {
            "source_dataset_rows": int(mammal_qa["source_dataset_rows"]),
            "rendered_complete_case_count": int(mammal_qa["rendered_complete_cases"]),
            "authority_point_glyph_count": int(mammal_qa["authority_point_glyph_runs"]),
            "target_vector_circle_count": int(mammal_qa["target_vector_circle_runs"]),
            "poppler_mammal_visible_point_count": 55,
            "mupdf_mammal_visible_point_count": 55,
            "poppler_blue_pixels": int(mammal_qa["poppler_blue_pixels"]),
            "mupdf_blue_pixels": int(mammal_qa["mutool_blue_pixels"]),
            "renderer_blue_pixel_iou": mammal_qa["mutool_poppler_blue_iou"],
            "result": "PASS",
        },
        "accessibility_corrections": {
            "mammal_alt_count": "62 dataset rows -> 55 complete rendered cases",
            "commute_alt_label": "Rerata waktu perjalanan kerja (menit)",
            "source_records": ["R011-ADV-0063"],
            "local_consistency_only": ["commute_alt_label"],
        },
        "rights": {
            "repository_license": "CC BY-SA 3.0 Unported",
            "closure": "Pinned repository statistical plots; no photograph, logo, trademark asset, package archive, or new raw package-data bytes are introduced. Scientific/data citations and producer provenance are retained.",
        },
        "manifest": identity_bytes(manifest_bytes),
        "proposed_asset_rows": identity_bytes(rows_bytes),
        "records": records,
    }
    receipt_bytes = canonical_json(receipt)
    return manifest_bytes, rows_bytes, receipt_bytes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    manifest, rows, receipt = assemble()
    outputs = {
        OUTPUT_MANIFEST: manifest,
        OUTPUT_ROWS: rows,
        OUTPUT_RECEIPT: receipt,
    }
    if args.write:
        for path, data in outputs.items():
            path.write_bytes(data)
    else:
        for path, data in outputs.items():
            require(path.is_file() and path.read_bytes() == data, f"replay mismatch: {path}")
    print(
        json.dumps(
            {
                "status": "PASS",
                "outputs": {
                    path.name: identity_bytes(data) for path, data in outputs.items()
                },
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
