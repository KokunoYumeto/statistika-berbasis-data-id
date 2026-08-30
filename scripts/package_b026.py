#!/usr/bin/env python3
"""Create or verify the reader-first deterministic R011-B026 package.

The package is deliberately compact: one learner PDF, one resumable editable
source closure, one modular-backend closure, and the small human-facing rights,
citation, scope, manifest, checksum, and Zenodo-metadata files.  Build renders,
caches, rejected candidates, and unrelated provenance dumps are excluded.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any

import b026_pipeline_contract as pipeline
from b026_release_contract import (
    BACKEND_ADMISSION_RECEIPT_PATH,
    BACKEND_REPLAY_RECEIPT_PATH,
    BOUNDARY_ID,
    CONFIG_PATH,
    MODEL,
    PROMOTION_RECEIPT_PATH,
    RELEASE_DATE,
    RELEASE_DIR,
    RELEASE_ID,
    ROOT,
    StageGateError,
    VERSION,
    canonical,
    identity,
    offline_release_self_check,
    release_ready,
    repo_path,
)
from prepare_b026_release import projection as release_input_projection


ASSETS = (
    "00_STATISTIKA_BERBASIS_DATA_ID_R011-B026_WORKING_READER.pdf",
    "01_STATISTIKA_BERBASIS_DATA_ID_R011-B026_EDITABLE_SOURCE.zip",
    "02_STATISTIKA_BERBASIS_DATA_ID_R011-B026_MODULAR_BACKEND.zip",
    "LICENSES_AND_ATTRIBUTION.md",
    "CITATION.cff",
    "README_RELEASE.md",
    "RELEASE_MANIFEST.json",
    "SHA256SUMS.txt",
    "ZENODO_METADATA.json",
)
HASHED_BEFORE_MANIFEST = (*ASSETS[:6], ASSETS[8])
FIXED_TIME = (2026, 8, 30, 0, 0, 0)
SOURCE_TOOLING = (
    "scripts/freeze_b026_source.py",
    "scripts/build_b026_boundary_clean_reader.py",
    "scripts/localize_b026_assets.py",
    "scripts/qa_b026_main_translation_part_a.py",
    "scripts/qa_b026_main_translation_part_b.py",
    "scripts/qa_b026_main_translation_part_c.py",
    "scripts/qa_b026_main_translation_parts_de.py",
    "scripts/qa_b026_main_translation_part_f.py",
    "scripts/qa_b026_exercises_answers.py",
    "scripts/qa_b026_boundary_clean_reader.py",
    "scripts/b026_pipeline_contract.py",
    "scripts/bind_b026_postbuild.py",
    "scripts/compile_backend_b026.py",
    "scripts/admit_backend_b026.py",
    "scripts/b026_release_contract.py",
    "scripts/promote_b026_reader.py",
    "scripts/prepare_b026_release.py",
    "scripts/package_b026.py",
)


def content_identity(path: Path) -> dict[str, int | str]:
    digest = hashlib.sha256()
    count = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            count += len(chunk)
            digest.update(chunk)
    return {"bytes": count, "sha256": digest.hexdigest()}


def config() -> dict[str, Any]:
    if not CONFIG_PATH.is_file():
        raise StageGateError("B026 RELEASE_INPUTS.json is absent")
    try:
        value = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StageGateError("B026 RELEASE_INPUTS.json is invalid") from exc
    expected = release_input_projection(require_complete=True)
    if value != expected or CONFIG_PATH.read_bytes() != canonical(expected):
        raise StageGateError("B026 release-input contract does not replay exactly")
    return value


def deterministic_zip(path: Path, rows: list[tuple[str, Path]]) -> None:
    ordered = sorted((name.replace("\\", "/"), source) for name, source in rows)
    if not ordered or len({name for name, _ in ordered}) != len(ordered):
        raise StageGateError("ZIP input is empty or contains an archive-name collision")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, source in ordered:
            if not source.is_file():
                raise StageGateError(f"ZIP source is absent: {source}")
            info = zipfile.ZipInfo(name, FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, source.read_bytes())
    with zipfile.ZipFile(path) as archive:
        if archive.namelist() != [name for name, _ in ordered]:
            raise StageGateError("deterministic ZIP inventory/order verification failed")
        if archive.testzip() is not None:
            raise StageGateError("deterministic ZIP CRC verification failed")


def _source_snapshot_rows(manifest_path: Path) -> tuple[list[tuple[str, Path]], int]:
    source_root = manifest_path.parent / "source-snapshot"
    rows: list[tuple[str, Path]] = []
    total = 0
    for number, line in enumerate(
        manifest_path.read_text(encoding="utf-8").splitlines(), 1
    ):
        parts = line.split("\t")
        if len(parts) != 3:
            raise StageGateError(f"malformed source manifest row {number}")
        rel, size_text, digest = parts
        source = source_root / Path(rel.replace("/", os.sep))
        observed = content_identity(source)
        if (observed["bytes"], observed["sha256"]) != (int(size_text), digest):
            raise StageGateError(f"source snapshot identity changed: {rel}")
        rows.append(("source-snapshot/" + rel, source))
        total += int(size_text)
    if not rows:
        raise StageGateError("source manifest is empty")
    return rows, total


def _checked_binding_file(row: dict[str, Any], role: str) -> Path:
    path = repo_path(row["path"])
    observed = identity(path)
    if (observed["bytes"], observed["sha256"]) != (
        row["bytes"], row["sha256"],
    ):
        raise StageGateError(f"bound file changed while packaging: {role}")
    return path


def _source_rows(ready: dict[str, Any]) -> list[tuple[str, Path]]:
    binding = ready["binding"]
    source_manifest_row = binding["post_build_outputs"]["source_manifest"]
    manifest_path = _checked_binding_file(source_manifest_row, "source_manifest")
    rows, _ = _source_snapshot_rows(manifest_path)
    by_name = {name: source for name, source in rows}

    def add_lane(path: str, *, prefix: str = "lane") -> None:
        source = repo_path(path)
        if not source.is_file():
            raise StageGateError(f"compact source dependency is absent: {path}")
        name = f"{prefix}/{path}"
        previous = by_name.get(name)
        if previous is not None and previous.read_bytes() != source.read_bytes():
            raise StageGateError(f"compact source archive collision: {name}")
        by_name[name] = source

    add_lane(source_manifest_row["path"], prefix="closure")
    for role, row in binding["sealed_text_inputs"].items():
        if role != "base_backend":
            _checked_binding_file(row, role)
            add_lane(row["path"])
    for role, row in binding["post_build_outputs"].items():
        if role != "candidate_pdf":
            _checked_binding_file(row, role)
            add_lane(row["path"])
    asset = binding["asset_closure"]
    add_lane(asset["receipt"]["path"])
    for artifact in asset["artifacts"]:
        for key in ("source", "producer", "output"):
            add_lane(artifact[key]["path"])
    add_lane(asset["dolphin_reuse"]["path"])
    add_lane(asset["dolphin_rights_witness"]["path"])
    for path in SOURCE_TOOLING:
        add_lane(path)
    return sorted(by_name.items())


def _backend_rows(ready: dict[str, Any]) -> list[tuple[str, Path]]:
    manifest_path = repo_path("backend/exports/manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("boundary_id") != BOUNDARY_ID:
        raise StageGateError("backend is not the admitted B026 graph")
    if identity(manifest_path) != ready["backend"]["manifest"]:
        raise StageGateError("backend manifest differs from release-ready gate")
    rows: list[tuple[str, Path]] = []
    for item in manifest.get("files", []):
        rel = item.get("path", "")
        if not rel.startswith(("core/", "locales/", "schemas/", "views/")):
            continue
        source = repo_path("backend/exports/" + rel)
        observed = identity(source)
        if (observed["bytes"], observed["sha256"]) != (
            item["bytes"], item["sha256"],
        ):
            raise StageGateError(f"backend export identity changed: {rel}")
        rows.append(("exports/" + rel, source))
    rows.extend(
        [
            ("exports/manifest.json", manifest_path),
            ("release/RELEASE_INPUTS.json", CONFIG_PATH),
            ("receipts/post-build-bindings.json", pipeline.BINDINGS_PATH),
            (
                "receipts/backend-admission.json",
                repo_path(BACKEND_ADMISSION_RECEIPT_PATH),
            ),
            ("receipts/backend-replay.json", repo_path(BACKEND_REPLAY_RECEIPT_PATH)),
            ("receipts/reader-promotion.json", repo_path(PROMOTION_RECEIPT_PATH)),
        ]
    )
    return rows


def metadata(cfg: dict[str, Any]) -> dict[str, Any]:
    pages = cfg["coverage"]["learner_reader_pages"]
    reader_sha = cfg["inputs"]["reader"]["sha256"]
    return {
        "metadata": {
            "title": (
                "Statistika Berbasis Data - Edisi Kerja Bahasa Indonesia "
                "(R011-B026: hingga Bagian 7.1)"
            ),
            "upload_type": "publication",
            "publication_type": "book",
            "publication_date": RELEASE_DATE,
            "version": VERSION,
            "description": (
                f"<p>Edisi kerja parsial Bahasa Indonesia dari OpenIntro "
                f"Statistics: pembaca bersih {pages} halaman hingga Bab 7, "
                "Bagian 7.1, dengan latihan Bab 7 nomor 1-14, jawaban publik "
                "ganjil 1-13, dan kesenjangan O001 genap 2-14. Cakupan yang "
                "diterima sebelumnya dipertahankan secara kumulatif. Tidak ada "
                "solusi instruktur terbatas. Ekor sumber hulu yang belum "
                "diterjemahkan hanya dipertahankan dalam arsip sumber untuk "
                "reproduksibilitas dan bukan keluaran pembelajar.</p>"
                "<p>Kredit karya asli: David M. Diez, Mine "
                "Çetinkaya-Rundel, dan Christopher D. Barr. Judul turunan: "
                "Statistika Berbasis Data. Bukan produk OpenIntro. Foto lumba-"
                "lumba Risso: Mike Baird, CC BY 2.0. Kontributor edisi: Codex, "
                f"atas permintaan pengguna. Model produksi: {MODEL}.</p>"
            ),
            "creators": [
                {"name": "Diez, David M."},
                {"name": "Çetinkaya-Rundel, Mine"},
                {"name": "Barr, Christopher D."},
            ],
            "contributors": [{"name": "Codex", "type": "Other"}],
            "license": "cc-by-sa-3.0",
            "language": "ind",
            "access_right": "open",
            "keywords": [
                "statistika",
                "Bahasa Indonesia",
                "OpenIntro Statistics",
                "pendidikan terbuka",
            ],
            "notes": (
                "Partial working edition; exact checkpoint R011-B026. "
                f"Reader SHA-256 {reader_sha}. {MODEL}. Public downloads must "
                "remain enabled. Component override: Mike Baird photograph, "
                "CC BY 2.0."
            ),
        }
    }


def _license_text() -> str:
    return f"""# Lisensi dan atribusi

OpenIntro Statistics, Fourth Edition karya David M. Diez, Mine Çetinkaya-Rundel, dan Christopher D. Barr. Teks buku, gambar buatan hulu, kode, dan terjemahan ini mengikuti CC BY-SA 3.0 kecuali bila catatan hak komponen menyatakan lain. Judul turunan: Statistika Berbasis Data; bukan produk OpenIntro.

Foto `rissosDolphin.jpg` dipertahankan byte-identik dan tetap memakai CC BY 2.0. Atribusi yang diwajibkan oleh sumber: "Photo by Mike Baird (http://www.bairdphotos.com/). Image was licensed under Creative Commons Attribution 2.0 Generic."

Tidak ada solusi instruktur terbatas yang diakses, diciptakan, atau disertakan. Data dan fakta yang dikutip tidak diberi klaim lisensi mandiri yang lebih luas. Semua kredit penulis dan kontributor manusia dipertahankan. Terjemahan dan produksi: {MODEL}.
"""


def _citation_text() -> str:
    return f"""cff-version: 1.2.0
message: "Sitasikan karya asli dan edisi terjemahan ini."
title: "Statistika Berbasis Data - Edisi Kerja Bahasa Indonesia (R011-B026)"
type: book
version: "{VERSION}"
date-released: "{RELEASE_DATE}"
license: CC-BY-SA-3.0
authors:
  - family-names: Diez
    given-names: David M.
  - family-names: Çetinkaya-Rundel
    given-names: Mine
  - family-names: Barr
    given-names: Christopher D.
contributors:
  - name: Codex
    contribution-type: translation
repository-code: "https://github.com/KokunoYumeto/statistika-berbasis-data-id"
"""


def _readme_text(cfg: dict[str, Any]) -> str:
    pages = cfg["coverage"]["learner_reader_pages"]
    return f"""# Statistika Berbasis Data - R011-B026

Edisi kerja Bahasa Indonesia ini masih **parsial**. Pembaca bersih berisi {pages} halaman hingga Bab 7, Bagian 7.1. Untuk Bab 7, cakupan latihan adalah 1-14; jawaban publik tersedia untuk nomor ganjil 1-13 dan nomor genap 2-14 dicatat sebagai kesenjangan O001. Cakupan yang diterima sebelumnya melalui Bab 6 Bagian 6.4 tetap tersedia secara kumulatif. Tidak ada solusi instruktur terbatas.

Semua halaman pembelajar telah melalui QA bahasa per halaman dan inspeksi visual lengkap. Arsip sumber mempertahankan ekor hulu yang belum diterjemahkan hanya untuk reproduksibilitas; ekor itu bukan keluaran pembelajar dan tidak dihitung sebagai kemajuan terjemahan. Foto lumba-lumba Risso karya Mike Baird tetap CC BY 2.0 dan dipertahankan byte-identik. Model produksi: {MODEL}.
"""


def verify_package() -> dict[str, Any]:
    cfg = config()
    manifest_path = RELEASE_DIR / "RELEASE_MANIFEST.json"
    if not manifest_path.is_file():
        raise StageGateError("B026 release manifest is absent")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StageGateError("B026 release manifest is invalid") from exc
    if (
        manifest.get("$schema") != "r011-b026-release-manifest/v1"
        or manifest.get("boundary_id") != BOUNDARY_ID
        or manifest.get("release_id") != RELEASE_ID
        or manifest.get("status") != "PACKAGED_VERIFIED"
        or manifest.get("ordered_assets") != list(ASSETS)
    ):
        raise StageGateError("B026 release manifest truth changed")
    expected_rows = [
        {"filename": name, **content_identity(RELEASE_DIR / name)}
        for name in HASHED_BEFORE_MANIFEST
    ]
    if manifest.get("files") != expected_rows:
        raise StageGateError("B026 release-manifest file identities changed")
    expected_sums = "".join(
        f"{row['sha256']}  {row['filename']}\n" for row in expected_rows
    )
    if (RELEASE_DIR / "SHA256SUMS.txt").read_text(encoding="utf-8") != expected_sums:
        raise StageGateError("B026 checksum inventory changed")
    if (RELEASE_DIR / "ZENODO_METADATA.json").read_bytes() != canonical(metadata(cfg)):
        raise StageGateError("B026 Zenodo metadata file changed")
    for name in ASSETS:
        if not (RELEASE_DIR / name).is_file():
            raise StageGateError(f"B026 release asset is absent: {name}")
    return manifest


def package() -> dict[str, Any]:
    cfg = config()
    ready = release_ready(require_complete=True)
    assert ready is not None
    source_rows = _source_rows(ready)
    backend_rows = _backend_rows(ready)
    with tempfile.TemporaryDirectory(prefix="r011-b026-package-") as td:
        temp = Path(td)
        shutil.copyfile(repo_path(cfg["inputs"]["reader"]["path"]), temp / ASSETS[0])
        deterministic_zip(temp / ASSETS[1], source_rows)
        deterministic_zip(temp / ASSETS[2], backend_rows)
        (temp / ASSETS[3]).write_text(_license_text(), encoding="utf-8")
        (temp / ASSETS[4]).write_text(_citation_text(), encoding="utf-8")
        (temp / ASSETS[5]).write_text(_readme_text(cfg), encoding="utf-8")
        (temp / ASSETS[8]).write_bytes(canonical(metadata(cfg)))
        file_rows = [
            {"filename": name, **content_identity(temp / name)}
            for name in HASHED_BEFORE_MANIFEST
        ]
        coverage = cfg["coverage"]
        manifest = {
            "$schema": "r011-b026-release-manifest/v1",
            "boundary_id": BOUNDARY_ID,
            "release_id": RELEASE_ID,
            "version": VERSION,
            "status": "PACKAGED_VERIFIED",
            "completion_state": "partial",
            "complete_corpus": False,
            "learner_reader_pages": coverage["learner_reader_pages"],
            "accepted_indonesian_reader_pages": coverage[
                "accepted_indonesian_reader_pages"
            ],
            "untranslated_instructional_or_exercise_prose_pages": 0,
            "all_pages_language_adjudicated": True,
            "all_pages_visually_inspected": True,
            "through": coverage["through"],
            "cumulative_prior_coverage": coverage["cumulative_prior_coverage"],
            "current_chapter": 7,
            "current_chapter_exercise_ids": list(range(1, 15)),
            "current_chapter_public_answer_ids": list(range(1, 14, 2)),
            "current_chapter_o001_gap_ids": list(range(2, 15, 2)),
            "restricted_solutions_used": False,
            "source_closure_counted_as_learner_output": False,
            "component_rights": {
                "upstream_and_translation": "CC BY-SA 3.0",
                "rissos_dolphin_photo": "Mike Baird, CC BY 2.0, byte-identical",
            },
            "production_model": MODEL,
            "ordered_assets": list(ASSETS),
            "files": file_rows,
            "reader_first": True,
            "publication_performed": False,
            "no_upstream_contact": True,
        }
        (temp / ASSETS[6]).write_bytes(canonical(manifest))
        (temp / ASSETS[7]).write_text(
            "".join(
                f"{row['sha256']}  {row['filename']}\n" for row in file_rows
            ),
            encoding="utf-8",
        )
        RELEASE_DIR.mkdir(parents=True, exist_ok=True)
        for name in ASSETS:
            source = temp / name
            target = RELEASE_DIR / name
            raw = source.read_bytes()
            if target.exists() and target.read_bytes() != raw:
                raise StageGateError(
                    f"refusing to replace a different B026 package asset: {name}"
                )
            temporary = target.with_name(target.name + ".b026.tmp")
            if temporary.exists():
                raise StageGateError(f"stale package temporary: {temporary}")
            temporary.write_bytes(raw)
            os.replace(temporary, target)
    verified = verify_package()
    return {
        "status": "PASS_B026_PACKAGED_VERIFIED",
        "manifest": verified,
        "assets": [identity(RELEASE_DIR / name) for name in ASSETS],
        "writes_performed": True,
        "network_used": False,
        "credentials_accessed": False,
        "git_used": False,
    }


def probe() -> dict[str, Any]:
    static = offline_release_self_check("b026-packager")
    if static["pending"]:
        return static
    if not CONFIG_PATH.is_file():
        return {
            **static,
            "status": "PASS_STATIC_B026_PACKAGE_FAIL_CLOSED_PREPARATION_PENDING",
            "pending": ["exact B026 RELEASE_INPUTS.json preparation"],
        }
    cfg = config()
    return {
        "status": "PASS_B026_PACKAGING_PROBE_NO_WRITES",
        "config": identity(CONFIG_PATH),
        "reader": cfg["inputs"]["reader"],
        "would_create": list(ASSETS),
        "writes_performed": False,
        "network_used": False,
        "credentials_accessed": False,
        "git_used": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--self-check", action="store_true")
    mode.add_argument("--probe", action="store_true")
    mode.add_argument("--package", action="store_true")
    mode.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        result = offline_release_self_check("b026-packager")
    elif args.probe:
        result = probe()
    elif args.package:
        result = package()
    else:
        result = {"status": "PASS_B026_PACKAGE_REVERIFIED", "manifest": verify_package()}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except StageGateError as exc:
        raise SystemExit(f"REFUSED: {exc}")
