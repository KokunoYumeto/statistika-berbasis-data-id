#!/usr/bin/env python3
"""Create/verify the reader-first deterministic R011-B025 release package."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path

from b025_pipeline_contract import (
    BOUNDARY_ID, CONFIG_PATH, MODEL, RELEASE_DIR, RELEASE_ID, StageGateError,
    VERSION, canonical, identity, load_bindings, offline_self_check, repo_path,
)


ASSETS = (
    "00_STATISTIKA_BERBASIS_DATA_ID_R011-B025_WORKING_READER.pdf",
    "01_STATISTIKA_BERBASIS_DATA_ID_R011-B025_EDITABLE_SOURCE.zip",
    "02_STATISTIKA_BERBASIS_DATA_ID_R011-B025_MODULAR_BACKEND.zip",
    "LICENSES_AND_ATTRIBUTION.md", "CITATION.cff", "README_RELEASE.md",
    "RELEASE_MANIFEST.json", "SHA256SUMS.txt", "ZENODO_METADATA.json",
)
FIXED_TIME = (2026, 8, 29, 0, 0, 0)
SOURCE_TOOLING = (
    "scripts/freeze_b025_source.py", "scripts/build_b025_boundary_clean_reader.py",
    "scripts/localize_b025_ipod_chisq_tail.py", "scripts/qa_b025_boundary_clean_reader.py",
)


def config() -> dict:
    if not CONFIG_PATH.is_file():
        raise StageGateError("B025 RELEASE_INPUTS.json is absent")
    value = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if value.get("boundary_id") != BOUNDARY_ID or value.get("release_id") != RELEASE_ID or value.get("status") != "READY_FOR_PACKAGING":
        raise StageGateError("B025 release inputs truth changed")
    return value


def deterministic_zip(path: Path, rows: list[tuple[str, Path]]) -> None:
    rows = sorted(rows)
    if len({name for name, _ in rows}) != len(rows):
        raise StageGateError("ZIP archive-name collision")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, source in rows:
            info = zipfile.ZipInfo(name.replace("\\", "/"), FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, source.read_bytes())
    with zipfile.ZipFile(path) as archive:
        if archive.namelist() != [name for name, _ in rows] or archive.testzip() is not None:
            raise StageGateError("deterministic ZIP verification failed")


def content_identity(path: Path) -> dict[str, int | str]:
    digest = hashlib.sha256()
    count = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            count += len(chunk)
            digest.update(chunk)
    return {"bytes": count, "sha256": digest.hexdigest()}


def _source_rows(manifest_path: Path, root: Path) -> list[tuple[str, Path]]:
    rows = []
    lines = manifest_path.read_text(encoding="utf-8").splitlines()
    for line in lines:
        parts = line.split("\t")
        if len(parts) < 3:
            raise StageGateError("source manifest row is malformed")
        rel = parts[0]
        source = root / Path(rel.replace("/", os.sep))
        if not source.is_file() or source.stat().st_size != int(parts[1]) or hashlib.sha256(source.read_bytes()).hexdigest() != parts[2]:
            raise StageGateError(f"source snapshot identity changed: {rel}")
        rows.append((rel, source))
    return rows


def _backend_rows() -> list[tuple[str, Path]]:
    manifest = json.loads(repo_path("backend/exports/manifest.json").read_text(encoding="utf-8"))
    if manifest.get("boundary_id") != BOUNDARY_ID:
        raise StageGateError("backend is not admitted B025")
    rows = []
    for item in manifest.get("files", []):
        rel = item["path"]
        if not rel.startswith(("core/", "locales/", "schemas/", "views/")):
            continue
        source = repo_path("backend/exports/" + rel)
        observed = identity(source)
        if (observed["bytes"], observed["sha256"]) != (item["bytes"], item["sha256"]):
            raise StageGateError(f"backend file identity changed: {rel}")
        rows.append(("exports/" + rel, source))
    rows.append(("exports/manifest.json", repo_path("backend/exports/manifest.json")))
    rows.append(("release/RELEASE_INPUTS.json", CONFIG_PATH))
    return rows


def metadata(cfg: dict) -> dict:
    pages = cfg["coverage"]["learner_reader_pages"]
    return {"metadata": {"title": "Statistika Berbasis Data - Edisi Kerja Bahasa Indonesia (R011-B025: hingga Bagian 6.4)", "upload_type": "publication", "publication_type": "book", "publication_date": cfg["release_date"], "version": cfg["version"], "description": f"<p>Edisi kerja parsial Bahasa Indonesia dari OpenIntro Statistics: pembaca bersih {pages} halaman hingga Bab 6, Bagian 6.4, dengan latihan 1–38, jawaban publik ganjil 1–37, dan kesenjangan O001 genap 2–38. Tidak ada solusi instruktur terbatas. Ekor sumber hulu yang belum diterjemahkan hanya dipertahankan untuk reproduksibilitas dan bukan keluaran pembelajar.</p><p>Kredit karya asli: David M. Diez, Mine Çetinkaya-Rundel, dan Christopher D. Barr. Judul turunan: Statistika Berbasis Data. Bukan produk OpenIntro. Kontributor edisi: Codex, atas permintaan pengguna. Model produksi: {MODEL}.</p>", "creators": [{"name": "Diez, David M."}, {"name": "Çetinkaya-Rundel, Mine"}, {"name": "Barr, Christopher D."}], "contributors": [{"name": "Codex", "type": "Other"}], "license": "cc-by-sa-3.0", "language": "ind", "access_right": "open", "keywords": ["statistika", "Bahasa Indonesia", "OpenIntro Statistics", "pendidikan terbuka"], "notes": f"Partial working edition; exact checkpoint R011-B025. Reader SHA-256 {cfg['inputs']['reader']['sha256']}. {MODEL}. Public downloads must remain enabled."}}


def verify_package() -> dict:
    cfg = config()
    manifest_path = RELEASE_DIR / "RELEASE_MANIFEST.json"
    if not manifest_path.is_file():
        raise StageGateError("B025 release manifest is absent")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("boundary_id") != BOUNDARY_ID or manifest.get("status") != "PACKAGED_VERIFIED" or manifest.get("ordered_assets") != list(ASSETS):
        raise StageGateError("B025 release manifest truth changed")
    for row in manifest["files"]:
        observed = identity(RELEASE_DIR / row["filename"])
        if (observed["bytes"], observed["sha256"]) != (row["bytes"], row["sha256"]):
            raise StageGateError(f"release file identity changed: {row['filename']}")
    return manifest


def package() -> dict:
    cfg = config()
    binding = load_bindings(require_complete=True)
    source_manifest = repo_path(binding["post_build_outputs"]["source_manifest"]["path"])
    source_root = source_manifest.parent / "source-snapshot"
    source_rows = _source_rows(source_manifest, source_root)
    source_rows.extend((path, repo_path(path)) for path in SOURCE_TOOLING)
    backend_rows = _backend_rows()
    with tempfile.TemporaryDirectory(prefix="r011-b025-package-") as td:
        temp = Path(td)
        shutil.copyfile(repo_path(cfg["inputs"]["reader"]["path"]), temp / ASSETS[0])
        deterministic_zip(temp / ASSETS[1], source_rows)
        deterministic_zip(temp / ASSETS[2], backend_rows)
        (temp / "LICENSES_AND_ATTRIBUTION.md").write_text("# Lisensi dan atribusi\n\nOpenIntro Statistics, Fourth Edition karya David M. Diez, Mine Çetinkaya-Rundel, dan Christopher D. Barr. Teks buku, gambar buatan hulu, kode, dan terjemahan ini mengikuti CC BY-SA 3.0 kecuali bila catatan hak komponen menyatakan lain. Judul turunan: Statistika Berbasis Data; bukan produk OpenIntro.\n\nFoto quadcopter karya David J dan foto rusa kijang karya Shrikant Rao masing-masing tetap memakai CC BY 2.0; nama pembuat, tautan sumber Flickr, dan catatan perubahan hulu dipertahankan. `earacupuncture.pdf` tetap dikecualikan dari paket sumber publik sesuai penutupan hak komponen. Gambar `iPodChiSqTail` hanya menerjemahkan anotasi yang terlihat; geometri, nilai, asal OpenIntro, dan penghasil R yang dibekukan tetap dipertahankan. Data dan fakta yang dikutip tidak diberi klaim lisensi mandiri yang lebih luas.\n\nSemua kredit penulis dan kontributor manusia dipertahankan. Tidak ada solusi instruktur terbatas. Terjemahan dan produksi: OpenAI Codex gpt-5.6-sol, Ultra.\n", encoding="utf-8")
        (temp / "CITATION.cff").write_text(f"cff-version: 1.2.0\nmessage: \"Sitasikan karya asli dan edisi terjemahan ini.\"\ntitle: \"Statistika Berbasis Data - Edisi Kerja Bahasa Indonesia (R011-B025)\"\ntype: book\nversion: \"{VERSION}\"\ndate-released: \"2026-08-29\"\nlicense: CC-BY-SA-3.0\nauthors:\n  - family-names: Diez\n    given-names: David M.\n  - family-names: Çetinkaya-Rundel\n    given-names: Mine\n  - family-names: Barr\n    given-names: Christopher D.\ncontributors:\n  - name: Codex\n    contribution-type: translation\nrepository-code: \"https://github.com/KokunoYumeto/statistika-berbasis-data-id\"\n", encoding="utf-8")
        pages = cfg["coverage"]["learner_reader_pages"]
        (temp / "README_RELEASE.md").write_text(f"# Statistika Berbasis Data — R011-B025\n\nEdisi kerja Bahasa Indonesia ini masih **parsial**. Pembaca bersih berisi {pages} halaman hingga Bab 6, Bagian 6.4. Cakupan latihan adalah 1–38; jawaban publik tersedia untuk nomor ganjil 1–37 dan nomor genap 2–38 dicatat sebagai kesenjangan O001. Tidak ada solusi instruktur terbatas. Semua halaman telah melalui QA bahasa per halaman dan inspeksi visual. Arsip sumber mempertahankan ekor hulu yang belum diterjemahkan hanya untuk reproduksibilitas; ekor itu bukan keluaran pembelajar. Model produksi: {MODEL}.\n", encoding="utf-8")
        (temp / "ZENODO_METADATA.json").write_bytes(canonical(metadata(cfg)))
        hashed = list(ASSETS[:6]) + [ASSETS[8]]
        file_rows = [{"filename": name, **content_identity(temp / name)} for name in hashed]
        manifest = {"$schema": "r011-b025-release-manifest/v1", "boundary_id": BOUNDARY_ID, "release_id": RELEASE_ID, "version": VERSION, "status": "PACKAGED_VERIFIED", "completion_state": "partial", "complete_corpus": False, "learner_reader_pages": pages, "accepted_indonesian_reader_pages": pages, "untranslated_instructional_or_exercise_prose_pages": 0, "all_pages_language_adjudicated": True, "all_pages_visually_inspected": True, "through": cfg["coverage"]["through"], "exercise_ids": list(range(1,39)), "public_answer_ids": list(range(1,38,2)), "o001_gap_ids": list(range(2,39,2)), "restricted_solutions_used": False, "source_closure_counted_as_learner_output": False, "production_model": MODEL, "ordered_assets": list(ASSETS), "files": file_rows, "reader_first": True, "publication_performed": False, "no_upstream_contact": True}
        (temp / "RELEASE_MANIFEST.json").write_bytes(canonical(manifest))
        (temp / "SHA256SUMS.txt").write_text("".join(f"{row['sha256']}  {row['filename']}\n" for row in file_rows), encoding="utf-8")
        RELEASE_DIR.mkdir(parents=True, exist_ok=True)
        for name in ASSETS:
            target = RELEASE_DIR / name
            raw = (temp / name).read_bytes()
            if target.exists() and target.read_bytes() != raw:
                raise StageGateError(f"refusing to replace different B025 package asset: {name}")
            target.write_bytes(raw)
    return {"status": "PASS_B025_PACKAGED_VERIFIED", "manifest": verify_package(), "assets": [identity(RELEASE_DIR / name) for name in ASSETS]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--self-check", action="store_true")
    mode.add_argument("--probe", action="store_true")
    mode.add_argument("--package", action="store_true")
    mode.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        result = offline_self_check("b025-packager")
    elif args.probe:
        cfg = config(); result = {"status": "PASS_B025_PACKAGING_PROBE_NO_WRITES", "config": identity(CONFIG_PATH), "would_create": list(ASSETS), "writes_performed": False}
    elif args.verify:
        result = {"status": "PASS_B025_PACKAGE_REVERIFIED", "manifest": verify_package()}
    else:
        result = package()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try: raise SystemExit(main())
    except StageGateError as exc: raise SystemExit(f"REFUSED: {exc}")
