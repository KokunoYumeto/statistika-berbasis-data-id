#!/usr/bin/env python3
"""Bind root visual inspection of every page in the R011-B024 reader."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from PIL import Image
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "scratch/b024-boundary-clean-reader/final/main.pdf"
AUTOMATED = ROOT / "qa/b024-reader/R011-B024_AUTOMATED_VISUAL_QA.json"
LANGUAGE = ROOT / "qa/b024-reader/R011-B024_PAGEWISE_LANGUAGE_QA.json"
PAGES = ROOT / "qa/b024-reader/render-v1/pages"
CONTACTS = ROOT / "qa/b024-reader/render-v1/contacts"
RECEIPT = ROOT / "qa/b024-reader/R011-B024_ROOT_VISUAL_INSPECTION_QA.json"

EXPECTED_PDF = {
    "bytes": 12_390_137,
    "sha256": "fcd78ff026131e4979c0ea282b4468101406527f16dc335ee6583ad220273b53",
    "pages": 253,
}
EXPECTED_AUTOMATED = {
    "bytes": 82_980,
    "sha256": "543ea03db38a283c323f71e383687d1137564389ebd7ce429ed34f03f175f1af",
    "status": "PASS_ALL_PAGES_RENDERED_AUTOMATED_LAYOUT_SANITY",
}
EXPECTED_LANGUAGE = {
    "bytes": 86_185,
    "sha256": "eb59ed06717453bef6a6fb91b3d2629094e47e25f5e42b34914d15a2a6e0b43e",
    "status": "PASS_DETERMINISTIC_BUILD_PAGEWISE_LANGUAGE_STRUCTURE_AND_AUTOMATED_VISUAL_QA",
}
CONTACT_RANGES = [
    (1, 20), (21, 40), (41, 60), (61, 80), (81, 100), (101, 120),
    (121, 140), (141, 160), (161, 180), (181, 200), (201, 220),
    (221, 240), (241, 253),
]
FULL_PAGES = [232, 233, 234, 235, 236, 237, 238, 239, 240, 241, 251, 252, 253]


class GateError(RuntimeError):
    pass


def canonical(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)
        + "\n"
    ).encode("utf-8")


def canonical_compact(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def identity(path: Path) -> dict[str, object]:
    raw = path.read_bytes()
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GateError(message)


def image_identity(path: Path) -> dict[str, object]:
    record = identity(path)
    with Image.open(path) as image:
        record["dimensions"] = [image.width, image.height]
        record["mode"] = image.mode
    return record


def verify_json(path: Path, expected: dict[str, object]) -> dict[str, object]:
    record = identity(path)
    require(
        (record["bytes"], record["sha256"]) == (expected["bytes"], expected["sha256"]),
        f"receipt identity changed: {record['path']}",
    )
    value = json.loads(path.read_text(encoding="utf-8"))
    require(value.get("status") == expected["status"], f"receipt status changed: {record['path']}")
    return record


def inventory_digest(records: list[dict[str, object]]) -> str:
    rows = [
        {"path": row["path"], "bytes": row["bytes"], "sha256": row["sha256"]}
        for row in records
    ]
    return hashlib.sha256(canonical_compact(rows)).hexdigest()


def payload() -> dict[str, object]:
    pdf = identity(PDF)
    require(
        (pdf["bytes"], pdf["sha256"]) == (EXPECTED_PDF["bytes"], EXPECTED_PDF["sha256"]),
        "B024 reader identity changed",
    )
    page_count = len(PdfReader(str(PDF)).pages)
    require(page_count == EXPECTED_PDF["pages"], "B024 reader page count changed")
    pdf["pages"] = page_count
    automated = verify_json(AUTOMATED, EXPECTED_AUTOMATED)
    language = verify_json(LANGUAGE, EXPECTED_LANGUAGE)

    page_paths = sorted(PAGES.glob("page-*.png"))
    require(len(page_paths) == 253, "page raster count changed")
    require(
        [path.name for path in page_paths]
        == [f"page-{number:03d}.png" for number in range(1, 254)],
        "page raster ordering or closure changed",
    )
    page_rows = [image_identity(path) for path in page_paths]
    require(all(row["dimensions"] == [1020, 1320] and row["mode"] == "RGB" for row in page_rows), "page raster geometry changed")

    contact_names = [f"contact-{start:03d}-{end:03d}.png" for start, end in CONTACT_RANGES]
    contact_paths = sorted(CONTACTS.glob("contact-*.png"))
    require([path.name for path in contact_paths] == contact_names, "contact-sheet closure changed")
    contact_rows: list[dict[str, object]] = []
    for path, (start, end) in zip(contact_paths, CONTACT_RANGES):
        row = image_identity(path)
        require(row["dimensions"] == [1040, 1725] and row["mode"] == "RGB", "contact-sheet geometry changed")
        row.update({
            "page_range": [start, end],
            "disposition": "VISUALLY_INSPECTED_ZERO_DEFECTS",
        })
        contact_rows.append(row)

    full_rows: list[dict[str, object]] = []
    for number in FULL_PAGES:
        row = image_identity(PAGES / f"page-{number:03d}.png")
        row.update({
            "page": number,
            "inspection_scale": "FULL_120_DPI_PAGE_RASTER_1020_BY_1320",
            "disposition": "VISUALLY_INSPECTED_ZERO_DEFECTS",
        })
        full_rows.append(row)

    return {
        "$schema": "interlanguage.r011-b024-root-visual-inspection-qa/v1",
        "boundary_id": "R011-B024",
        "status": "PASS_ALL_253_PAGES_VISUALLY_INSPECTED_ZERO_DEFECTS",
        "all_pages_visually_inspected": True,
        "page_count": 253,
        "page_count_is_artifact_extent_not_translation_progress": True,
        "learner_pdf": pdf,
        "automated_visual_receipt": automated,
        "pagewise_language_receipt": language,
        "automated_receipts_preserved_unchanged": True,
        "inspected_contact_sheets": contact_rows,
        "inspected_individual_page_rasters": full_rows,
        "inspection_method": {
            "direct_visual_inspection_by_root_agent": True,
            "human_inspector_claimed": False,
            "contact_sheet_count": 13,
            "contact_sheet_coverage": [1, 253],
            "individual_full_page_rasters": FULL_PAGES,
            "checks": [
                "no clipping",
                "no overlap",
                "no unreadable figure",
                "no broken table",
                "no layout defect",
                "new Section 6.3 charts and answer pages readable at original scale",
            ],
            "root_confirmation": (
                "The root Codex agent directly inspected all 13 ordered contact sheets "
                "covering pages 1 through 253 and the full-page rasters for the complete "
                "new Section 6.3/exercise range 232-241 plus answer pages 251-253."
            ),
        },
        "root_confirmation": {
            "all_253_pages_covered_in_order": True,
            "all_thirteen_contact_sheets_inspected": True,
            "individual_pages_inspected": FULL_PAGES,
            "zero_defects_confirmed": True,
        },
        "defect_count": 0,
        "defects": [],
        "verified_render_inventory": {
            "every_page_covered_exactly_once": True,
            "page_geometry": [1020, 1320, "RGB"],
            "contact_sheet_geometry": [1040, 1725, "RGB"],
            "page_pngs": {
                "file_count": len(page_rows),
                "total_bytes": sum(int(row["bytes"]) for row in page_rows),
                "canonical_identity_inventory_sha256": inventory_digest(page_rows),
            },
            "contact_sheets": {
                "file_count": len(contact_rows),
                "total_bytes": sum(int(row["bytes"]) for row in contact_rows),
                "canonical_identity_inventory_sha256": inventory_digest(contact_rows),
            },
        },
        "inspection_model": "OpenAI Codex gpt-5.6-sol, Ultra",
        "production_model": "OpenAI Codex gpt-5.6-sol, Ultra",
        "complete_corpus": False,
        "upstream_contact": False,
        "git_used": False,
        "network_used": False,
        "credentials_accessed": False,
        "publication_performed": False,
    }


def finalize() -> dict[str, object]:
    value = payload()
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    temporary = RECEIPT.with_name(RECEIPT.name + ".tmp")
    require(not temporary.exists(), "stale root-visual receipt temporary exists")
    temporary.write_bytes(canonical(value))
    os.replace(temporary, RECEIPT)
    return {**value, "receipt": identity(RECEIPT)}


def verify() -> dict[str, object]:
    expected = payload()
    require(RECEIPT.is_file() and RECEIPT.read_bytes() == canonical(expected), "root visual receipt changed")
    return {**expected, "status": "PASS_EXACT_B024_ROOT_VISUAL_INSPECTION_REPLAY", "receipt": identity(RECEIPT)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--finalize", action="store_true")
    mode.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    result = finalize() if args.finalize else verify()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except GateError as exc:
        raise SystemExit(f"ERROR: {exc}")
