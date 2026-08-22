#!/usr/bin/env python3
"""Build the exact R011-B006 whole-book candidate from its frozen manifest.

``--build`` requires the authoritative B006 source receipt and target manifest,
copies only manifest-exact bytes into a clean source snapshot, runs the complete
TeX toolchain, proves that the last two PDF passes are byte-identical, performs
non-visual PDF checks, and renders every B006 page plus transition context.

This gate deliberately has no promotion mode and never writes to ``repo`` or
``output/pdf``.  Its successful terminal state is ``pending_visual_review``;
an operator must inspect every rendered page before any later promotion gate.
With no arguments, the script performs an exact read-only replay of the build
receipt and render manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw
from pypdf import PdfReader
from pypdf.generic import ArrayObject, IndirectObject


LANE = Path(__file__).resolve().parents[1]
REPO = LANE / "repo"
QA = LANE / "qa"
MANIFEST = QA / "R011-B006_TARGET_MANIFEST.tsv"
SOURCE_RECEIPT = QA / "R011-B006_SOURCE_QA.json"
LAYOUT_REPAIR_RECEIPT_V3 = QA / "R011-B006_LAYOUT_REPAIR_RECEIPT_V3.json"
LAYOUT_REPAIR_RECEIPT_V4 = QA / "R011-B006_LAYOUT_REPAIR_RECEIPT_V4.json"

BUILD_ROOT = QA / "b006-build"
SNAPSHOT = BUILD_ROOT / "source-snapshot-v4"
FINAL = BUILD_ROOT / "final-v4"
PDF = FINAL / "main.pdf"
PASS3_PDF = FINAL / "main-pass3.pdf"
TEXT = FINAL / "main-final.txt"
LOG = FINAL / "main.log"
FLS = FINAL / "main.fls"
BUILD_RECEIPT = FINAL / "CANDIDATE_BUILD_QA_V4.json"

RENDER = QA / "b006-render" / "final-v4"
RENDER_MANIFEST = RENDER / "FINAL_MANIFEST.tsv"
PAGE_LOCATOR = RENDER / "PAGE_LOCATOR.json"
CONTACT_SHEET = RENDER / "CONTACT_SHEET.png"

BOUNDARY_ID = "R011-B006"
AUTHORITY_REPOSITORY = "https://github.com/OpenIntroStat/openintro-statistics"
AUTHORITY_COMMIT = "fee25091fb24e89c36296fd67c48c1fcf7a93b6e"
AUTHORITY_TREE = "d61cc601e7d97759ce805900520f784d02a0489e"
SOURCE_DATE_EPOCH = "1787184000"
MINIMUM_PAGE_COUNT = 424
RENDER_DPI = 180
MANDATORY_VISUAL_PAGES = tuple(range(61, 74)) + (388, 389, 390)

PASS_NAMES = ("pass1", "pass2", "pass3", "pass4")
BUILD_FILE_NAMES = (
    "console-pass1.txt",
    "console-bibtex.txt",
    "console-makeindex1.txt",
    "console-pass2.txt",
    "console-makeindex2.txt",
    "console-pass3.txt",
    "console-makeindex3.txt",
    "console-pass4.txt",
    "main.log",
    "main.fls",
    "main-final.txt",
    "console-mutool-info.txt",
    "console-pdfinfo.txt",
    "console-pdftotext.txt",
)
REQUIRED_TOOLS = (
    "pdflatex",
    "bibtex",
    "makeindex",
    "pdfinfo",
    "pdftotext",
    "pdftoppm",
    "mutool",
)
ALLOWED_POPPLER_DISPLAY_FONT_WARNINGS = {
    f"Syntax Error: No display font for '{name}'"
    for name in (
        "Symbol",
        "ArialNarrow",
        "ArialNarrow,Bold",
        "ArialNarrow,Italic",
        "ArialNarrow,BoldItalic",
        "ArialNarrow-Bold",
        "ArialNarrow-Italic",
        "ArialNarrow-BoldItalic",
        "HelveticaNarrow",
        "HelveticaNarrow,Bold",
        "HelveticaNarrow,Italic",
        "HelveticaNarrow,BoldItalic",
        "HelveticaNarrow-Bold",
        "HelveticaNarrow-Italic",
        "HelveticaNarrow-BoldItalic",
        "ArialUnicode",
    )
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def identity_bytes(data: bytes) -> dict[str, object]:
    return {"bytes": len(data), "sha256": sha256_bytes(data)}


def identity(path: Path) -> dict[str, object]:
    return identity_bytes(path.read_bytes())


def canonical_json(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(LANE)).replace("\\", "/")


def is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def parse_manifest() -> dict[str, tuple[int, str]]:
    if not MANIFEST.is_file():
        raise RuntimeError("R011-B006 target manifest is absent")
    rows: dict[str, tuple[int, str]] = {}
    lines = MANIFEST.read_text(encoding="utf-8").splitlines()
    for number, line in enumerate(lines, 1):
        parts = line.split("\t")
        if len(parts) != 3:
            raise RuntimeError(f"invalid manifest row {number}: {line!r}")
        relative_path, size_text, digest = parts
        candidate = Path(relative_path)
        if (
            not relative_path
            or candidate.is_absolute()
            or ".." in candidate.parts
            or relative_path.startswith(("/", "\\"))
        ):
            raise RuntimeError(f"unsafe manifest path at row {number}: {relative_path!r}")
        if relative_path in rows:
            raise RuntimeError(f"duplicate manifest path: {relative_path}")
        try:
            size = int(size_text)
        except ValueError as exc:
            raise RuntimeError(f"invalid byte count at row {number}: {size_text!r}") from exc
        if size < 0 or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise RuntimeError(f"invalid identity at manifest row {number}")
        rows[relative_path] = (size, digest)
    if not rows:
        raise RuntimeError("R011-B006 target manifest is empty")
    if list(rows) != sorted(rows):
        raise RuntimeError("R011-B006 target manifest is not path-sorted")
    return rows


def require_source_gate() -> tuple[dict[str, tuple[int, str]], dict[str, Any]]:
    if not SOURCE_RECEIPT.is_file() or not MANIFEST.is_file():
        raise RuntimeError(
            "R011-B006 source gate is absent; refusing to assemble or build"
        )
    source = json.loads(SOURCE_RECEIPT.read_text(encoding="utf-8"))
    authority = source.get("authority", {})
    if (
        source.get("schema") != "openintro-id-source-boundary-qa"
        or source.get("schema_version") != "0.9.0"
        or source.get("boundary_id") != BOUNDARY_ID
        or source.get("status") != "passed"
        or authority.get("repository") != AUTHORITY_REPOSITORY
        or authority.get("commit") != AUTHORITY_COMMIT
        or authority.get("tree") != AUTHORITY_TREE
    ):
        raise RuntimeError("R011-B006 source receipt is not the exact PASS authority")
    if source.get("checks", {}).get("active_reader_visible_english") != 0:
        raise RuntimeError("R011-B006 source receipt reports reader-visible English")
    if source.get("checks", {}).get("placeholders") != 0:
        raise RuntimeError("R011-B006 source receipt reports placeholders")

    rows = parse_manifest()
    manifest_id = identity(MANIFEST)
    manifest_record = source.get("target_closure", {}).get("manifest", {})
    if manifest_record != {"path": rel(MANIFEST), **manifest_id}:
        raise RuntimeError("source receipt does not bind the exact live B006 manifest")
    closure = source.get("target_closure", {})
    if closure.get("target_file_count") != len(rows) or closure.get(
        "target_file_bytes"
    ) != sum(size for size, _ in rows.values()):
        raise RuntimeError("source receipt target counts do not match the manifest")

    required_checks = (
        "base_receipt_and_manifest_exact",
        "source_order_and_topology",
        "section_2_3_plus_authority_suffix",
        "source_corrections_SC_B006_001_through_005_only",
        "exercise_answer_o001_topology",
        "asset_code_data_rights_closure",
        "ADV_0070_through_0079",
        "post_build_repair_topology_and_display",
        "post_build_repairs_reverse_reconstructed",
        "rejected_v1_visual_findings_bound",
        "rejected_v2_visual_findings_bound",
        "rejected_v3_visual_findings_bound",
        "v3_layout_repairs_reverse_reconstructed",
        "v4_layout_repair_reverse_reconstructed",
    )
    bad = [name for name in required_checks if source.get("checks", {}).get(name) != "passed"]
    if bad:
        raise RuntimeError(f"source receipt has non-passing checks: {bad}")
    expected_layout_receipt = {
        "path": rel(LAYOUT_REPAIR_RECEIPT_V3),
        **identity(LAYOUT_REPAIR_RECEIPT_V3),
    }
    if source.get("checks", {}).get("prior_v3_layout_repair_receipt") != expected_layout_receipt:
        raise RuntimeError(
            "source receipt does not bind the exact prior v3 layout-repair receipt"
        )
    expected_layout_receipt_v4 = {
        "path": rel(LAYOUT_REPAIR_RECEIPT_V4),
        **identity(LAYOUT_REPAIR_RECEIPT_V4),
    }
    if source.get("checks", {}).get("v4_layout_repair_receipt") != expected_layout_receipt_v4:
        raise RuntimeError(
            "source receipt does not bind the exact v4 layout-repair receipt"
        )
    if source.get("checks", {}).get("manifest_delta_recomputed") is not True:
        raise RuntimeError("source receipt did not recompute its target closure")
    return rows, source


def verify_tree(
    root: Path, rows: dict[str, tuple[int, str]], errors: list[str] | None = None
) -> dict[str, object]:
    local: list[str] = []
    if not root.is_dir():
        local.append(f"snapshot directory missing: {rel(root)}")
        actual: set[str] = set()
    else:
        actual = {
            str(path.relative_to(root)).replace("\\", "/")
            for path in root.rglob("*")
            if path.is_file()
        }
        if actual != set(rows):
            local.append(
                "snapshot path-set mismatch; "
                f"missing={sorted(set(rows) - actual)[:10]}, "
                f"extra={sorted(actual - set(rows))[:10]}"
            )
    mismatches: list[str] = []
    for relative_path, (size, digest) in rows.items():
        candidate = root / Path(relative_path)
        if not candidate.is_file() or identity(candidate) != {
            "bytes": size,
            "sha256": digest,
        }:
            mismatches.append(relative_path)
    if mismatches:
        local.append(f"snapshot identity mismatches: {mismatches[:10]}")
    if errors is not None:
        errors.extend(local)
    return {
        "path": rel(root),
        "file_count": len(actual),
        "file_bytes": sum((root / Path(item)).stat().st_size for item in actual),
        "path_set_and_all_file_identities_match_manifest": not local,
    }


def assemble_snapshot(
    rows: dict[str, tuple[int, str]], source: dict[str, Any]
) -> dict[str, object]:
    if SNAPSHOT.exists() and any(SNAPSHOT.rglob("*")):
        errors: list[str] = []
        verify_tree(SNAPSHOT, rows, errors)
        if errors:
            raise RuntimeError(
                "refusing to overwrite non-exact B006 snapshot: " + "; ".join(errors)
            )
        return {
            "schema": "openintro-frozen-snapshot-receipt",
            "schema_version": "0.3.0",
            "boundary_id": BOUNDARY_ID,
            "status": "passed",
            "authority_commit": AUTHORITY_COMMIT,
            "authority_tree": AUTHORITY_TREE,
            "target_manifest": {
                "path": rel(MANIFEST),
                **identity(MANIFEST),
                "file_count": len(rows),
                "file_bytes": sum(size for size, _ in rows.values()),
            },
            "source_gate": {"path": rel(SOURCE_RECEIPT), **identity(SOURCE_RECEIPT)},
            "snapshot": verify_tree(SNAPSHOT, rows),
            "assembly_source": {
                "path": rel(REPO),
                "policy": (
                    "each live file required to match its target-manifest identity "
                    "before copy"
                ),
                "file_count": len(rows),
                "file_bytes": sum(size for size, _ in rows.values()),
            },
            "write_boundary": (
                "manifest-exact files copied only into "
                "qa/b006-build/source-snapshot-v4"
            ),
        }

    SNAPSHOT.mkdir(parents=True, exist_ok=True)
    copied_bytes = 0
    for relative_path, (size, digest) in rows.items():
        expected = {"bytes": size, "sha256": digest}
        source_path = REPO / Path(relative_path)
        destination = SNAPSHOT / Path(relative_path)
        if not source_path.is_file() or identity(source_path) != expected:
            raise RuntimeError(f"live repo does not match manifest: {relative_path}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination)
        if identity(destination) != expected:
            raise RuntimeError(f"snapshot copy readback mismatch: {relative_path}")
        copied_bytes += size

    errors: list[str] = []
    snapshot = verify_tree(SNAPSHOT, rows, errors)
    if errors:
        raise RuntimeError("assembled snapshot verification failed: " + "; ".join(errors))
    receipt = {
        "schema": "openintro-frozen-snapshot-receipt",
        "schema_version": "0.3.0",
        "boundary_id": BOUNDARY_ID,
        "status": "passed",
        "authority_commit": AUTHORITY_COMMIT,
        "authority_tree": AUTHORITY_TREE,
        "target_manifest": {
            "path": rel(MANIFEST),
            **identity(MANIFEST),
            "file_count": len(rows),
            "file_bytes": copied_bytes,
        },
        "source_gate": {"path": rel(SOURCE_RECEIPT), **identity(SOURCE_RECEIPT)},
        "snapshot": snapshot,
        "assembly_source": {
            "path": rel(REPO),
            "policy": "each live file required to match its target-manifest identity before copy",
            "file_count": len(rows),
            "file_bytes": copied_bytes,
        },
        "write_boundary": "manifest-exact files copied only into qa/b006-build/source-snapshot-v4",
    }
    return receipt


def build_environment() -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        {
            "SOURCE_DATE_EPOCH": SOURCE_DATE_EPOCH,
            "FORCE_SOURCE_DATE": "1",
            "TZ": "UTC",
            "MIKTEX_ENABLE_INSTALLER": "0",
        }
    )
    env["BIBINPUTS"] = str(SNAPSHOT) + os.pathsep + env.get("BIBINPUTS", "")
    return env


def tool_paths() -> dict[str, str]:
    found: dict[str, str] = {}
    missing: list[str] = []
    for name in REQUIRED_TOOLS:
        location = shutil.which(name)
        if location is None:
            missing.append(name)
        else:
            found[name] = str(Path(location).resolve())
    if missing:
        raise RuntimeError(f"required build tools missing: {missing}")
    return found


def run_logged(
    command: list[str], cwd: Path, output: Path, env: dict[str, str]
) -> subprocess.CompletedProcess[bytes]:
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True)
    output.write_bytes(result.stdout + result.stderr)
    if result.returncode != 0:
        raise RuntimeError(
            f"command failed ({result.returncode}); see {rel(output)}: {command[0]}"
        )
    return result


def run_build() -> None:
    rows, source = require_source_gate()
    assemble_snapshot(rows, source)
    if FINAL.exists() and any(FINAL.rglob("*")):
        raise RuntimeError(f"refusing to overwrite non-empty build directory: {rel(FINAL)}")
    if RENDER.exists() and any(RENDER.rglob("*")):
        raise RuntimeError(f"refusing to overwrite non-empty render directory: {rel(RENDER)}")
    FINAL.mkdir(parents=True, exist_ok=True)
    RENDER.mkdir(parents=True, exist_ok=True)
    tools = tool_paths()
    env = build_environment()

    pdflatex = [
        tools["pdflatex"],
        "-interaction=nonstopmode",
        "-halt-on-error",
        "-file-line-error",
        "-recorder",
        "-no-shell-escape",
        "-synctex=0",
        f"-output-directory={FINAL}",
        "main.tex",
    ]
    run_logged(pdflatex, SNAPSHOT, FINAL / "console-pass1.txt", env)
    run_logged([tools["bibtex"], "main"], FINAL, FINAL / "console-bibtex.txt", env)
    run_logged(
        [tools["makeindex"], "main.idx"],
        FINAL,
        FINAL / "console-makeindex1.txt",
        env,
    )
    run_logged(pdflatex, SNAPSHOT, FINAL / "console-pass2.txt", env)
    run_logged(
        [tools["makeindex"], "main.idx"],
        FINAL,
        FINAL / "console-makeindex2.txt",
        env,
    )
    run_logged(pdflatex, SNAPSHOT, FINAL / "console-pass3.txt", env)
    if not PDF.is_file():
        raise RuntimeError("pdflatex pass 3 did not create main.pdf")
    shutil.copy2(PDF, PASS3_PDF)
    if identity(PASS3_PDF) != identity(PDF):
        raise RuntimeError("pass-3 freeze copy failed readback")
    run_logged(
        [tools["makeindex"], "main.idx"],
        FINAL,
        FINAL / "console-makeindex3.txt",
        env,
    )
    run_logged(pdflatex, SNAPSHOT, FINAL / "console-pass4.txt", env)
    if not PDF.is_file() or identity(PDF) != identity(PASS3_PDF):
        raise RuntimeError("pass 3 and pass 4 PDFs are not byte-identical")

    mutool = subprocess.run([tools["mutool"], "info", str(PDF)], capture_output=True)
    (FINAL / "console-mutool-info.txt").write_bytes(mutool.stdout + mutool.stderr)
    if mutool.returncode != 0:
        raise RuntimeError("mutool info failed")
    pdfinfo = subprocess.run([tools["pdfinfo"], str(PDF)], capture_output=True)
    (FINAL / "console-pdfinfo.txt").write_bytes(pdfinfo.stdout + pdfinfo.stderr)
    if pdfinfo.returncode != 0:
        raise RuntimeError("pdfinfo failed")
    pdftotext = subprocess.run(
        [tools["pdftotext"], "-layout", str(PDF), str(TEXT)], capture_output=True
    )
    (FINAL / "console-pdftotext.txt").write_bytes(pdftotext.stderr)
    if pdftotext.returncode != 0 or not TEXT.is_file():
        raise RuntimeError("pdftotext failed")

    render_pages(tools["pdftoppm"])
    _, receipt_bytes, _ = evaluate()
    BUILD_RECEIPT.write_bytes(receipt_bytes)


def destination_page(reader: PdfReader, name: str) -> int:
    destination = reader.named_destinations.get(name)
    if destination is None:
        raise RuntimeError(f"required named destination missing: {name}")
    page = reader.get_destination_page_number(destination)
    if page is None or page < 0:
        raise RuntimeError(f"named destination has no valid page: {name}")
    return int(page) + 1


def normalized_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def find_hits(
    normalized_pages: list[str], marker: str, lower: int, upper: int
) -> list[int]:
    return [
        page_number
        for page_number, page_text in enumerate(normalized_pages, 1)
        if lower <= page_number <= upper and marker in page_text
    ]


def candidate_pages(reader: PdfReader) -> tuple[list[int], dict[str, object]]:
    section_22 = destination_page(reader, "section.2.2")
    section_23 = destination_page(reader, "section.2.3")
    if not 1 < section_22 < section_23 <= len(reader.pages):
        raise RuntimeError(
            f"unexpected B006 destination order: section.2.2={section_22}, "
            f"section.2.3={section_23}"
        )
    text_pages = TEXT.read_text(encoding="utf-8", errors="replace").split("\f")
    normalized_pages = [
        normalized_text(page_text) for page_text in text_pages[: len(reader.pages)]
    ]

    primary_markers = {
        "section_2_2": "2.2 menelaah data kategoris",
        "exercise_2_21": "2.21 penggunaan antibiotik pada anak",
        "exercise_2_22": "2.22 pandangan tentang imigrasi",
        "exercise_2_23": "2.23 pandangan tentang dream act",
        "exercise_2_24": "2.24 menaikkan pajak",
        "section_2_3_transition": "2.3 case study: malaria vaccine",
    }
    primary_hits = {
        role: find_hits(normalized_pages, marker, section_22, section_23)
        for role, marker in primary_markers.items()
    }
    missing_primary = [role for role, hits in primary_hits.items() if not hits]
    if missing_primary:
        raise RuntimeError(f"B006 primary coverage markers missing: {missing_primary}")
    if section_22 not in primary_hits["section_2_2"]:
        raise RuntimeError("Section 2.2 heading is not on its named-destination page")
    if section_23 not in primary_hits["section_2_3_transition"]:
        raise RuntimeError("Section 2.3 transition is not on its named-destination page")
    exercise_first = min(primary_hits["exercise_2_21"])
    exercise_last = max(primary_hits["exercise_2_24"])
    if not section_22 <= exercise_first <= exercise_last < section_23:
        raise RuntimeError("Exercises 2.21-2.24 are not ordered inside Section 2.2")

    answer_markers = {
        "public_answer_2_21": (
            "2.21 (a) diagram batang memperlihatkan",
            "2.21",
        ),
        "public_answer_2_23": (
            "2.23 posisi vertikal tempat setiap kelompok ideologi",
            "2.23",
        ),
    }
    answer_hits: dict[str, list[int]] = {}
    lower_answer = max(300, section_23 + 1)
    for role, (content_marker, number_marker) in answer_markers.items():
        answer_hits[role] = [
            page_number
            for page_number, page_text in enumerate(normalized_pages, 1)
            if page_number >= lower_answer
            and content_marker in page_text
            and number_marker in page_text
        ]
    missing_answers = [role for role, hits in answer_hits.items() if not hits]
    if missing_answers:
        raise RuntimeError(f"B006 public-answer markers missing: {missing_answers}")

    primary_content = list(range(section_22, section_23))
    primary_context = list(range(max(1, section_22 - 1), section_23 + 1))
    answer_hit_pages = sorted({page for hits in answer_hits.values() for page in hits})
    answer_context_start = max(1, min(answer_hit_pages) - 1)
    answer_context_stop = min(len(reader.pages), max(answer_hit_pages) + 1)
    answer_context = list(range(answer_context_start, answer_context_stop + 1))
    mandatory_pages = list(MANDATORY_VISUAL_PAGES)
    if any(page < 1 or page > len(reader.pages) for page in mandatory_pages):
        raise RuntimeError(
            "mandatory B006 visual-audit page is outside the candidate PDF"
        )
    pages = sorted(set(primary_context + answer_context + mandatory_pages))
    return pages, {
        "coverage_policy": (
            "every page from section.2.2 through the page before section.2.3; "
            "one adjacent page before Section 2.2; the Section 2.3 transition page; "
            "one adjacent page before and after the public-answer 2.21/2.23 span; "
            "and every fixed audit page required by the v4 handoff"
        ),
        "mandatory_v4_audit_pages": mandatory_pages,
        "section_2_2_page": section_22,
        "section_2_3_transition_page": section_23,
        "section_2_2_content_span": [section_22, section_23 - 1],
        "section_2_2_content_pages": primary_content,
        "primary_context_span": [max(1, section_22 - 1), section_23],
        "primary_context_pages": primary_context,
        "primary_marker_hits": primary_hits,
        "exercise_2_21_through_2_24_span": [exercise_first, exercise_last],
        "public_answer_marker_hits": answer_hits,
        "answer_context_span": [answer_context_start, answer_context_stop],
        "answer_context_pages": answer_context,
        "all_candidate_pages": pages,
    }


def render_manifest_bytes(pages: list[int]) -> bytes:
    rows: list[str] = []
    for page in pages:
        name = f"page-{page:03d}.png"
        path = RENDER / name
        if not path.is_file():
            raise RuntimeError(f"rendered page missing: {name}")
        item = identity(path)
        rows.append(f"{page}\t{name}\t{item['bytes']}\t{item['sha256']}\n")
    return "".join(rows).encode("utf-8")


def make_contact_sheet(pages: list[int]) -> None:
    thumbs: list[tuple[int, Image.Image]] = []
    width = 280
    label_height = 28
    for page in pages:
        with Image.open(RENDER / f"page-{page:03d}.png") as source:
            ratio = width / source.width
            height = max(1, round(source.height * ratio))
            thumbs.append((page, source.convert("RGB").resize((width, height))))
    columns = 4
    rows = (len(thumbs) + columns - 1) // columns
    cell_height = max(image.height for _, image in thumbs) + label_height
    sheet = Image.new("RGB", (columns * width, rows * cell_height), "white")
    draw = ImageDraw.Draw(sheet)
    for index, (page, thumb) in enumerate(thumbs):
        x = (index % columns) * width
        y = (index // columns) * cell_height
        draw.text((x + 8, y + 7), f"PDF page {page}", fill="black")
        sheet.paste(thumb, (x, y + label_height))
    sheet.save(CONTACT_SHEET, format="PNG", optimize=False)


def render_pages(pdftoppm: str) -> None:
    reader = PdfReader(PDF, strict=True)
    pages, locator = candidate_pages(reader)
    for page in pages:
        name = f"page-{page:03d}"
        result = subprocess.run(
            [
                pdftoppm,
                "-f",
                str(page),
                "-l",
                str(page),
                "-r",
                str(RENDER_DPI),
                "-png",
                "-singlefile",
                str(PDF),
                str(RENDER / name),
            ],
            capture_output=True,
        )
        (RENDER / f"console-{name}.txt").write_bytes(result.stderr)
        if result.returncode != 0:
            raise RuntimeError(f"pdftoppm failed on page {page}")
    RENDER_MANIFEST.write_bytes(render_manifest_bytes(pages))
    PAGE_LOCATOR.write_bytes(canonical_json(locator))
    make_contact_sheet(pages)


def verify_snapshot(errors: list[str]) -> dict[str, object]:
    rows, source = require_source_gate()
    manifest_id = identity(MANIFEST)
    source_id = identity(SOURCE_RECEIPT)
    snapshot = verify_tree(SNAPSHOT, rows, errors)
    return {
        **snapshot,
        "target_manifest": {"path": rel(MANIFEST), **manifest_id},
        "source_receipt": {"path": rel(SOURCE_RECEIPT), **source_id},
        "assembly_evidence": {
            "policy": (
                "the snapshot path set and every file identity are recomputed against "
                "the revised target manifest on every replay"
            ),
            "persisted_separately": False,
            "embedded_in_candidate_receipt": True,
        },
        "source_receipt_status": source.get("status"),
    }


def log_counts(errors: list[str]) -> dict[str, int]:
    text = LOG.read_text(encoding="utf-8", errors="replace")
    patterns = {
        "fatal_errors": r"(?m)(?:Fatal error occurred|Emergency stop|!  ==> Fatal error|^! )",
        "latex_errors": r"LaTeX Error:",
        "undefined_references_or_citations": (
            r"LaTeX Warning: (?:Reference|Citation).*undefined|"
            r"There were undefined (?:references|citations)"
        ),
        "rerun_requests": r"Rerun to get cross-references right|Please \(re\)run|rerunfilecheck Warning",
        "missing_characters": r"Missing character:",
        "missing_destinations": r"has been referenced but does not exist",
        "duplicate_destination_warnings": r"destination with the same identifier",
        "overfull_hbox_warnings": r"Overfull \\hbox",
        "overfull_vbox_warnings": r"Overfull \\vbox",
        "underfull_hbox_warnings": r"Underfull \\hbox",
        "underfull_vbox_warnings": r"Underfull \\vbox",
    }
    counts = {name: len(re.findall(pattern, text)) for name, pattern in patterns.items()}
    for name in (
        "fatal_errors",
        "latex_errors",
        "undefined_references_or_citations",
        "rerun_requests",
        "missing_characters",
        "missing_destinations",
    ):
        if counts[name] != 0:
            errors.append(f"nonzero final-log gate: {name}={counts[name]}")
    if counts["duplicate_destination_warnings"] != 1:
        errors.append(
            "inherited duplicate-destination warning count is not exactly one: "
            f"{counts['duplicate_destination_warnings']}"
        )
    return counts


def normalized_named_destinations(reader: PdfReader) -> set[str]:
    values: set[str] = set()
    for name in reader.named_destinations:
        text = str(name)
        values.add(text)
        values.add(text.lstrip("/"))
        values.add("/" + text.lstrip("/"))
    return values


def validate_destination(
    value: object,
    page_refs: set[tuple[int, int]],
    named: set[str],
    page_count: int,
) -> bool:
    if isinstance(value, IndirectObject):
        return (value.idnum, value.generation) in page_refs
    if isinstance(value, (ArrayObject, list)):
        if not value:
            return False
        first = value[0]
        if isinstance(first, IndirectObject):
            return (first.idnum, first.generation) in page_refs
        if isinstance(first, int):
            return 0 <= first < page_count
        return False
    text = str(value)
    return text in named or text.lstrip("/") in named or ("/" + text.lstrip("/")) in named


def structure_checks(errors: list[str]) -> tuple[dict[str, object], PdfReader]:
    reader = PdfReader(PDF, strict=True)
    page_count = len(reader.pages)
    if page_count < MINIMUM_PAGE_COUNT:
        errors.append(f"unexpectedly short whole-book PDF: {page_count} pages")
    page_refs = {
        (page.indirect_reference.idnum, page.indirect_reference.generation)
        for page in reader.pages
        if page.indirect_reference is not None
    }
    named = normalized_named_destinations(reader)
    goto = uri = other = links = missing = without_action = 0
    file_attachments = 0
    other_types: dict[str, int] = {}
    non_letter_pages: list[int] = []
    for page_number, page in enumerate(reader.pages, 1):
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)
        if abs(width - 612.0) > 0.01 or abs(height - 792.0) > 0.01:
            non_letter_pages.append(page_number)
        for annotation_ref in page.get("/Annots", []):
            annotation = annotation_ref.get_object()
            subtype = str(annotation.get("/Subtype", ""))
            if subtype == "/FileAttachment":
                file_attachments += 1
            if subtype != "/Link":
                continue
            links += 1
            if "/Dest" in annotation:
                goto += 1
                if not validate_destination(annotation["/Dest"], page_refs, named, page_count):
                    missing += 1
                continue
            action_ref = annotation.get("/A")
            if action_ref is None:
                without_action += 1
                continue
            action = action_ref.get_object() if hasattr(action_ref, "get_object") else action_ref
            action_type = str(action.get("/S", ""))
            if action_type == "/URI":
                uri += 1
            elif action_type == "/GoTo":
                goto += 1
                if "/D" not in action or not validate_destination(
                    action["/D"], page_refs, named, page_count
                ):
                    missing += 1
            else:
                other += 1
                other_types[action_type] = other_types.get(action_type, 0) + 1

    root = reader.trailer["/Root"]
    names = root.get("/Names")
    names_obj = names.get_object() if names is not None else None
    embedded = bool(names_obj and names_obj.get("/EmbeddedFiles"))
    javascript = bool(names_obj and names_obj.get("/JavaScript"))
    open_ref = root.get("/OpenAction")
    open_action = (
        open_ref.get_object()
        if open_ref is not None and hasattr(open_ref, "get_object")
        else open_ref
    )
    open_type = str(open_action.get("/S", "")) if hasattr(open_action, "get") else ""
    if missing or without_action or other:
        errors.append(
            f"link validation failed: missing={missing}, without_action={without_action}, "
            f"other={other_types}"
        )
    if file_attachments or embedded:
        errors.append("PDF contains an attachment surface")
    if javascript or root.get("/AA") or open_type not in {"", "/GoTo"}:
        errors.append("PDF contains a JavaScript or executable action surface")
    if open_type == "/GoTo" and (
        "/D" not in open_action
        or not validate_destination(open_action["/D"], page_refs, named, page_count)
    ):
        errors.append("PDF opening-view GoTo action has an invalid destination")
    if non_letter_pages:
        errors.append(f"non-letter media boxes: {non_letter_pages[:10]}")
    if reader.is_encrypted:
        errors.append("PDF is encrypted")
    if str(root.get("/Lang", "")) != "id-ID":
        errors.append(f"document language is not id-ID: {root.get('/Lang')!r}")

    try:
        pages, boundary = candidate_pages(reader)
    except Exception as exc:
        errors.append(f"B006 page-span discovery failed: {exc}")
        pages, boundary = [], {}
    return {
        "page_count": page_count,
        "all_pages_letter_612_by_792_points": not non_letter_pages,
        "annotation_links": links,
        "goto_links": goto,
        "uri_links": uri,
        "other_action_links": other,
        "other_action_types": other_types,
        "links_without_action_or_destination": without_action,
        "missing_link_targets": missing,
        "named_destinations": len(reader.named_destinations),
        "file_attachment_annotations": file_attachments,
        "embedded_file_name_tree_present": embedded,
        "javascript_name_tree_present": javascript,
        "open_action_type": open_type,
        "opening_view_goto_valid": open_type == "/GoTo",
        "additional_action_present": bool(root.get("/AA")),
        "encrypted": reader.is_encrypted,
        "tagged": "/MarkInfo" in root and bool(root["/MarkInfo"].get_object().get("/Marked")),
        "document_language": str(root.get("/Lang", "")),
        "form_present": "/AcroForm" in root,
        "b006_boundary_pages": boundary,
        "visual_candidate_pages": pages,
    }, reader


def pdfinfo_checks(errors: list[str]) -> dict[str, str]:
    raw = (FINAL / "console-pdfinfo.txt").read_text(encoding="utf-8", errors="replace")
    info: dict[str, str] = {}
    for line in raw.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            info[key.strip()] = value.strip()
    expected = {
        "Title": "Statistika Berbasis Data",
        "Encrypted": "no",
        "Page size": "612 x 792 pts (letter)",
        "PDF version": "1.5",
        "Form": "none",
        "JavaScript": "no",
    }
    for key, value in expected.items():
        if info.get(key) != value:
            errors.append(f"pdfinfo mismatch for {key}: {info.get(key)!r}")
    try:
        pages = int(info.get("Pages", ""))
    except ValueError:
        pages = -1
    if pages < MINIMUM_PAGE_COUNT:
        errors.append(f"pdfinfo page count is invalid: {info.get('Pages')!r}")
    return info


def metadata_checks(reader: PdfReader, errors: list[str]) -> dict[str, str]:
    metadata = reader.metadata or {}
    expected = {
        "/Title": "Statistika Berbasis Data",
        "/Author": "David M. Diez, Mine Çetinkaya-Rundel, Christopher D. Barr",
        "/Subject": "Karya turunan berbahasa Indonesia dari OpenIntro Statistics, Edisi Keempat",
        "/Keywords": "statistika, data, buku teks, bahasa Indonesia",
    }
    values = {key: str(metadata.get(key, "")) for key in expected}
    for key, value in expected.items():
        if values[key] != value:
            errors.append(f"PDF metadata mismatch for {key}: {values[key]!r}")
    values["/CreationDate"] = str(metadata.get("/CreationDate", ""))
    values["/ModDate"] = str(metadata.get("/ModDate", ""))
    if not values["/CreationDate"].startswith("D:20260820"):
        errors.append(f"unexpected deterministic creation date: {values['/CreationDate']!r}")
    if values["/ModDate"] != values["/CreationDate"]:
        errors.append("PDF modification date differs from deterministic creation date")
    return values


def input_closure_checks(errors: list[str]) -> dict[str, object]:
    lines = FLS.read_text(encoding="utf-8", errors="replace").splitlines()
    inputs = [line[6:] for line in lines if line.startswith("INPUT ")]
    lane_inputs: set[str] = set()
    forbidden: set[str] = set()
    snapshot_inputs = 0
    run_inputs = 0
    for raw in inputs:
        candidate = Path(raw)
        if not candidate.is_absolute():
            snapshot_candidate = (SNAPSHOT / candidate).resolve()
            run_candidate = (FINAL / candidate).resolve()
            if snapshot_candidate.exists():
                candidate = snapshot_candidate
            elif run_candidate.exists():
                candidate = run_candidate
            else:
                continue
        else:
            candidate = candidate.resolve()
        if is_within(candidate, LANE):
            lane_inputs.add(str(candidate))
            if is_within(candidate, SNAPSHOT):
                snapshot_inputs += 1
            elif is_within(candidate, FINAL):
                run_inputs += 1
            else:
                forbidden.add(str(candidate))
    if forbidden:
        errors.append(f"build read lane files outside snapshot/run: {sorted(forbidden)[:10]}")
    if snapshot_inputs == 0:
        errors.append("FLS records no source-snapshot inputs")
    return {
        "fls_input_records": len(inputs),
        "unique_lane_inputs": len(lane_inputs),
        "snapshot_input_records": snapshot_inputs,
        "run_input_records": run_inputs,
        "forbidden_lane_inputs": sorted(forbidden),
        "live_repo_input_count": sum(1 for item in lane_inputs if is_within(Path(item), REPO)),
    }


def build_file_identities(errors: list[str]) -> dict[str, object]:
    result: dict[str, object] = {}
    for name in BUILD_FILE_NAMES:
        path = FINAL / name
        if not path.is_file():
            errors.append(f"required build evidence missing: {name}")
            result[name] = {"path": rel(path), "missing": True}
        else:
            result[name] = {"path": rel(path), **identity(path)}
    return result


def tool_versions() -> dict[str, object]:
    versions: dict[str, object] = {}
    for name in REQUIRED_TOOLS:
        path = shutil.which(name)
        if path is None:
            versions[name] = {"missing": True}
            continue
        flag = "-v" if name in {"pdftoppm", "pdftotext", "pdfinfo"} else "--version"
        result = subprocess.run([path, flag], capture_output=True, text=True, errors="replace")
        lines = (result.stdout + result.stderr).splitlines()
        versions[name] = {
            "path": str(Path(path).resolve()),
            "version_first_line": lines[0] if lines else "",
        }
    versions["python"] = {"version": sys.version.splitlines()[0]}
    versions["pypdf"] = {"version": __import__("pypdf").__version__}
    versions["pillow"] = {"version": __import__("PIL").__version__}
    return versions


def visual_evidence(
    errors: list[str], pages: list[int], pdf_id: dict[str, object]
) -> tuple[bytes, dict[str, object]]:
    try:
        manifest_raw = render_manifest_bytes(pages)
    except Exception as exc:
        errors.append(f"render manifest reconstruction failed: {exc}")
        return b"", {"status": "failed", "error": str(exc)}
    if not RENDER_MANIFEST.is_file() or RENDER_MANIFEST.read_bytes() != manifest_raw:
        errors.append("render manifest differs from candidate PNGs")
    locator_raw = canonical_json(candidate_pages(PdfReader(PDF, strict=True))[1])
    if not PAGE_LOCATOR.is_file() or PAGE_LOCATOR.read_bytes() != locator_raw:
        errors.append("page locator differs from PDF-derived candidate coverage")
    warning_pages: list[int] = []
    warning_count = 0
    warning_names: set[str] = set()
    for page in pages:
        console = RENDER / f"console-page-{page:03d}.txt"
        if not console.is_file():
            errors.append(f"render diagnostics are absent for page {page}")
            continue
        lines = [
            line.strip()
            for line in console.read_text(encoding="utf-8", errors="replace").splitlines()
            if line.strip()
        ]
        unexpected = [
            line for line in lines if line not in ALLOWED_POPPLER_DISPLAY_FONT_WARNINGS
        ]
        if unexpected:
            errors.append(f"unexpected render diagnostics on page {page}: {unexpected[:3]}")
        if lines:
            warning_pages.append(page)
            warning_count += len(lines)
            warning_names.update(lines)
    if not CONTACT_SHEET.is_file():
        errors.append("render contact sheet is absent")
    return manifest_raw, {
        "status": "pending_operator_inspection",
        "claim": "no visual PASS is asserted by this automated gate",
        "candidate_pages": pages,
        "candidate_page_count": len(pages),
        "inspection_resolution_dpi": RENDER_DPI,
        "pdf": {"path": rel(PDF), **pdf_id},
        "render_manifest": {"path": rel(RENDER_MANIFEST), **identity_bytes(manifest_raw)},
        "page_locator": {"path": rel(PAGE_LOCATOR), **identity_bytes(locator_raw)},
        "contact_sheet": (
            {"path": rel(CONTACT_SHEET), **identity(CONTACT_SHEET)}
            if CONTACT_SHEET.is_file()
            else {"path": rel(CONTACT_SHEET), "missing": True}
        ),
        "individual_png_bytes": sum(
            (RENDER / f"page-{page:03d}.png").stat().st_size for page in pages
        ),
        "render_diagnostics": {
            "policy": (
                "only the inherited Poppler no-display-font diagnostics enumerated by "
                "the gate are accepted; all other diagnostics fail"
            ),
            "pages_with_allowed_diagnostics": warning_pages,
            "allowed_diagnostic_count": warning_count,
            "unique_allowed_diagnostics": sorted(warning_names),
            "unexpected_diagnostic_count": 0,
        },
        "required_next_action": "inspect every individual candidate PNG at full resolution",
    }


def evaluate() -> tuple[bytes, bytes, dict[str, object]]:
    errors: list[str] = []
    source_closure = verify_snapshot(errors)
    if not PDF.is_file() or not PASS3_PDF.is_file():
        raise RuntimeError("B006 build PDF/pass-3 freeze is absent")
    pdf_id = identity(PDF)
    pass3_id = identity(PASS3_PDF)
    if pdf_id != pass3_id:
        errors.append("pass 3 and pass 4 PDFs are not byte-identical")

    build_files = build_file_identities(errors)
    logs = log_counts(errors) if LOG.is_file() else {}
    structure, reader = structure_checks(errors)
    info = pdfinfo_checks(errors)
    metadata = metadata_checks(reader, errors)
    closure = input_closure_checks(errors) if FLS.is_file() else {}
    mutool_text = (FINAL / "console-mutool-info.txt").read_text(
        encoding="utf-8", errors="replace"
    )
    if re.search(r"(?im)^(?:warning|error):", mutool_text):
        errors.append("mutool info emitted a warning or error")
    if (FINAL / "console-pdftotext.txt").read_bytes():
        errors.append("pdftotext emitted diagnostics")

    pages = list(structure.get("visual_candidate_pages", []))
    manifest_raw, visual = visual_evidence(errors, pages, pdf_id)
    nonvisual_status = "failed" if errors else "passed"
    status = "failed" if errors else "pending_visual_review"
    receipt = {
        "schema": "openintro-boundary-build-candidate-qa",
        "schema_version": "0.1.0",
        "boundary_id": BOUNDARY_ID,
        "status": status,
        "nonvisual_status": nonvisual_status,
        "authority": {
            "repository": AUTHORITY_REPOSITORY,
            "commit": AUTHORITY_COMMIT,
            "tree": AUTHORITY_TREE,
        },
        "gate_script": {"path": rel(Path(__file__).resolve()), **identity(Path(__file__).resolve())},
        "source_closure": source_closure,
        "toolchain": {
            "source_date_epoch": int(SOURCE_DATE_EPOCH),
            "force_source_date": True,
            "timezone": "UTC",
            "sequence": [
                "pdflatex-1",
                "bibtex",
                "makeindex-1",
                "pdflatex-2",
                "makeindex-2",
                "pdflatex-3",
                "makeindex-3",
                "pdflatex-4",
            ],
            "stable_final_passes": [3, 4],
            "versions": tool_versions(),
        },
        "determinism": {
            "pass_3": {"path": rel(PASS3_PDF), **pass3_id},
            "pass_4": {"path": rel(PDF), **pdf_id},
            "byte_identical": pass3_id == pdf_id,
        },
        "candidate_artifact": {
            "path": rel(PDF),
            **pdf_id,
            "promoted": False,
        },
        "pdfinfo": info,
        "metadata": metadata,
        "final_log": logs,
        "links_and_structure": structure,
        "build_input_closure": closure,
        "visual_evidence": visual,
        "build_files": build_files,
        "limitations": [
            "This candidate is not promoted and no automated visual PASS is asserted.",
            "Section 2.3 and later instructional content deliberately remain upstream English.",
            "The PDF declares id-ID but the inherited source does not produce a structurally tagged PDF.",
            "One inherited unreferenced duplicate page-destination warning is permitted and counted exactly.",
            "TeX box-warning counts are retained for page-by-page visual review.",
        ],
        "pending": ["operator inspection of every full-resolution candidate PNG"],
        "errors": errors,
        "write_boundary": (
            "qa/b006-build/source-snapshot-v4, qa/b006-build/final-v4, and "
            "qa/b006-render/final-v4 only; no repo or output/pdf mutation"
        ),
    }
    return manifest_raw, canonical_json(receipt), receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--build",
        action="store_true",
        help="assemble exact snapshot, compile, run non-visual QA, and render all candidates",
    )
    parser.add_argument(
        "--finish-existing",
        action="store_true",
        help=(
            "after a locator-only interruption, verify the exact converged build, "
            "then render and write its candidate receipt"
        ),
    )
    args = parser.parse_args()

    if sum((args.build, args.finish_existing)) > 1:
        raise SystemExit("choose only one operation")
    if args.build:
        run_build()
        manifest_raw, receipt_raw, receipt = evaluate()
        BUILD_RECEIPT.write_bytes(receipt_raw)
    elif args.finish_existing:
        rows, _ = require_source_gate()
        snapshot_errors: list[str] = []
        verify_tree(SNAPSHOT, rows, snapshot_errors)
        if snapshot_errors:
            raise SystemExit("snapshot gate failed: " + "; ".join(snapshot_errors))
        if not PDF.is_file() or not PASS3_PDF.is_file() or identity(PDF) != identity(PASS3_PDF):
            raise SystemExit("existing build is absent or final passes did not converge")
        missing = [name for name in BUILD_FILE_NAMES if not (FINAL / name).is_file()]
        if missing:
            raise SystemExit(f"existing build evidence is incomplete: {missing}")
        reader = PdfReader(PDF, strict=True)
        pages, _ = candidate_pages(reader)
        expected_render_paths = {
            "FINAL_MANIFEST.tsv",
            "PAGE_LOCATOR.json",
            "CONTACT_SHEET.png",
            *(f"page-{page:03d}.png" for page in pages),
            *(f"console-page-{page:03d}.txt" for page in pages),
        }
        if RENDER.exists() and any(RENDER.rglob("*")):
            actual_render_paths = {
                str(path.relative_to(RENDER)).replace("\\", "/")
                for path in RENDER.rglob("*")
                if path.is_file()
            }
            extra_render_paths = actual_render_paths - expected_render_paths
            if extra_render_paths:
                raise SystemExit(
                    "refusing existing render evidence with unexpected files; "
                    f"extra={sorted(extra_render_paths)}"
                )
        else:
            RENDER.mkdir(parents=True, exist_ok=True)
        render_pages(tool_paths()["pdftoppm"])
        manifest_raw, receipt_raw, receipt = evaluate()
        BUILD_RECEIPT.write_bytes(receipt_raw)
    else:
        manifest_raw, receipt_raw, receipt = evaluate()
        if not RENDER_MANIFEST.is_file() or RENDER_MANIFEST.read_bytes() != manifest_raw:
            raise SystemExit("read-only replay failed: render manifest differs")
        if not BUILD_RECEIPT.is_file() or BUILD_RECEIPT.read_bytes() != receipt_raw:
            raise SystemExit("read-only replay failed: build receipt differs or is absent")

    print(
        json.dumps(
            {
                "status": receipt["status"],
                "nonvisual_status": receipt["nonvisual_status"],
                "errors": receipt["errors"],
                "pending": receipt["pending"],
                "candidate_artifact": receipt["candidate_artifact"],
                "determinism": receipt["determinism"],
                "visual_evidence": receipt["visual_evidence"],
                "receipt": {
                    "path": rel(BUILD_RECEIPT),
                    **identity_bytes(receipt_raw),
                },
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 1 if receipt["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
