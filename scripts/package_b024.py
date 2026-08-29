#!/usr/bin/env python3
"""Build a deterministic, reader-first R011-B024 release package offline."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True

from release_b024_common import (
    BOUNDARY_ID,
    CONFIG_PATH,
    EXPECTED_READER_PAGES,
    MODEL,
    ORDERED_RELEASE_ASSETS,
    RELEASE_DIR,
    RELEASE_ID,
    ReleaseGateError,
    atomic_write,
    backend_public_rows,
    canonical_json_bytes,
    deterministic_zip,
    identity,
    load_config,
    release_assets,
    repo_path,
    source_manifest_rows,
    static_self_check,
    verify_release_package,
)


SOURCE_TOOLING = (
    "scripts/freeze_b024_source.py",
    "scripts/build_b024_boundary_clean_reader.py",
    "scripts/localize_b024_charts.py",
    "scripts/qa_b024_boundary_clean_reader.py",
    "scripts/finalize_b024_visual_qa.py",
)


def _citation(config: dict) -> bytes:
    return (
        "cff-version: 1.2.0\n"
        "message: \"Jika Anda menggunakan edisi kerja ini, sitasikan karya asli dan edisi terjemahan ini.\"\n"
        "title: \"Statistika Berbasis Data - Edisi Kerja Bahasa Indonesia (R011-B024)\"\n"
        "type: book\n"
        f"version: \"{config['version']}\"\n"
        f"date-released: \"{config['release_date']}\"\n"
        "license: CC-BY-SA-3.0\n"
        "authors:\n"
        "  - family-names: Diez\n    given-names: David M.\n"
        "  - family-names: Çetinkaya-Rundel\n    given-names: Mine\n"
        "  - family-names: Barr\n    given-names: Christopher D.\n"
        "contributors:\n"
        "  - name: Codex\n    contribution-type: translation\n"
        "repository-code: \"https://github.com/KokunoYumeto/statistika-berbasis-data-id\"\n"
    ).encode("utf-8")


def _licenses(config: dict) -> bytes:
    return (
        "# Lisensi dan atribusi\n\n"
        "OpenIntro Statistics, Fourth Edition adalah karya David M. Diez, "
        "Mine Çetinkaya-Rundel, dan Christopher D. Barr. Sumber resmi dibekukan "
        f"pada commit `{config['authority']['commit']}` dari "
        "https://github.com/OpenIntroStat/openintro-statistics.\n\n"
        "Teks buku dan terjemahan ini menggunakan Creative Commons Attribution-"
        "ShareAlike 3.0 Unported (CC BY-SA 3.0). Atribusi, lisensi, merek, data, "
        "kode, dan hak komponen yang berbeda tetap mengikuti catatan hak pada "
        "sumber dan backend. Visibilitas repositori tidak dianggap sebagai bukti "
        "lisensi seragam.\n\n"
        "Gambar `earacupuncture.pdf` dikecualikan dari paket sumber publik karena "
        "penutupan hak komponen. Foto quadcopter karya David J tetap membawa "
        "atribusi CC BY 2.0 yang diwarisi. Ketiga bagan berlabel yang dilokalkan "
        "mempertahankan asal, data, dan skrip penghasil hulunya.\n\n"
        "Foto rusa kijang karya Shrikant Rao memakai CC BY 2.0; kredit, pengalihan "
        "sumber Flickr, dan identifikasi lisensinya dipertahankan dalam sumber.\n\n"
        f"Terjemahan dan produksi: {MODEL}. Semua kredit penulis dan kontributor "
        "manusia dipertahankan. Tidak ada solusi instruktur terbatas yang digunakan.\n"
    ).encode("utf-8")


def _readme(config: dict) -> bytes:
    return (
        "# Statistika Berbasis Data - R011-B024\n\n"
        "Edisi kerja Bahasa Indonesia ini masih **parsial**, tetapi pembaca saat "
        "ini merupakan satu batas yang koheren dan bersih: 253 halaman yang "
        "diterima sampai Bab 6, Bagian 6.3 (Uji kesesuaian menggunakan khi-kuadrat). Semua 253 "
        "halaman telah menjalani QA bahasa per halaman dan inspeksi visual. Tidak "
        "ada halaman dengan prosa instruksional, latihan, atau jawaban publik "
        "berbahasa Inggris yang belum diterjemahkan.\n\n"
        "Cakupan latihan Bagian 6.1-6.3 adalah nomor 1-34. Jawaban publik hulu "
        "tersedia untuk nomor ganjil 1-33; nomor genap 2-34 dicatat sebagai "
        "kesenjangan penguasaan O001. Tidak ada solusi instruktur terbatas.\n\n"
        "Urutan file dimulai dengan PDF pembaca, kemudian sumber yang dapat "
        "disunting dan backend modular. Arsip sumber lengkap mempertahankan ekor "
        "sumber hulu yang belum diterjemahkan demi reproduksibilitas; ekor itu "
        "bukan keluaran pembelajar Bahasa Indonesia dan tidak dihitung sebagai "
        "kemajuan terjemahan. Jumlah halaman adalah luas artefak saat ini, bukan "
        "klaim bahwa korpus lengkap telah selesai.\n\n"
        f"Sumber dibekukan pada `{config['authority']['commit']}`. Model produksi: "
        f"{MODEL}. Tidak ada kontak hulu yang dilakukan.\n"
    ).encode("utf-8")


def zenodo_metadata(config: dict) -> dict:
    description = (
        "<p>Edisi kerja parsial Bahasa Indonesia dari OpenIntro Statistics, "
        "dengan pembaca bersih 253 halaman hingga Bab 6, Bagian 6.3 (Uji "
        "kesesuaian menggunakan khi-kuadrat). Tiga puluh empat latihan Bagian "
        "6.1-6.3 disertakan; jawaban publik tersedia untuk nomor ganjil 1 sampai "
        "33 dan kesenjangan O001 dicatat untuk nomor genap 2 sampai 34. Tidak ada solusi instruktur "
        "terbatas. Semua halaman pembaca telah diadili untuk bahasa dan "
        "diperiksa secara visual; tidak ada prosa instruksional, latihan, atau "
        "jawaban publik berbahasa Inggris yang belum diterjemahkan.</p>"
        "<p>Arsip sumber lengkap mempertahankan ekor sumber hulu yang belum "
        "diterjemahkan untuk reproduksibilitas; ekor itu bukan keluaran "
        "pembelajar. Kredit karya asli: David M. Diez, Mine Çetinkaya-Rundel, "
        "dan Christopher D. Barr. Judul turunan: Statistika Berbasis Data. "
        "Bukan produk OpenIntro. Kontributor edisi: Codex, atas permintaan "
        f"pengguna. Model produksi: {MODEL}.</p>"
    )
    return {
        "metadata": {
            "title": "Statistika Berbasis Data - Edisi Kerja Bahasa Indonesia (R011-B024: hingga Bagian 6.3)",
            "upload_type": "publication",
            "publication_type": "book",
            "publication_date": config["release_date"],
            "version": config["version"],
            "description": description,
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
                "sumber terbuka",
                "pendidikan terbuka",
            ],
            "notes": (
                "Partial working edition; exact checkpoint R011-B024. Reader SHA-256 "
                "fcd78ff026131e4979c0ea282b4468101406527f16dc335ee6583ad220273b53. "
                f"{MODEL}. Public downloads must remain enabled."
            ),
            "related_identifiers": [
                {
                    "identifier": "https://github.com/OpenIntroStat/openintro-statistics/tree/fee25091fb24e89c36296fd67c48c1fcf7a93b6e",
                    "relation": "isDerivedFrom",
                    "resource_type": "software",
                },
                {
                    "identifier": "https://www.openintro.org/book/os/",
                    "relation": "isDerivedFrom",
                    "resource_type": "publication-book",
                },
            ],
        }
    }


def _public_backend_manifest(config: dict, public_rows: list[dict], exclusions: list[dict]) -> bytes:
    return canonical_json_bytes(
        {
            "$schema": "r011-b024-public-backend-projection-manifest/v1",
            "boundary_id": BOUNDARY_ID,
            "release_id": RELEASE_ID,
            "status": "PUBLIC_COMPACT_PROJECTION_VERIFIED",
            "production_model": MODEL,
            "upstream_backend_manifest": config["inputs"]["backend_manifest"],
            "reader": config["inputs"]["reader"],
            "scope": config["coverage"],
            "files": [
                {key: row[key] for key in ("path", "bytes", "sha256")}
                for row in public_rows
            ],
            "public_file_count": len(public_rows),
            "public_bytes": sum(row["bytes"] for row in public_rows),
            "excluded_internal_evidence_file_count": len(exclusions),
            "excluded_internal_evidence_bytes": sum(row["bytes"] for row in exclusions),
            "source_closure_counted_as_learner_output": False,
            "no_upstream_contact": True,
        }
    )


def _backend_evidence_rows(config: dict) -> list[tuple[str, Path]]:
    roles = (
        "source_manifest",
        "build_qa",
        "source_blueprint",
        "main_translation_qa",
        "main_translation_independent_qa",
        "exercise_translation_qa",
        "exercise_chart_independent_qa",
        "localized_charts_qa",
        "localized_charts_visual_qa",
        "pagewise_language_qa",
        "pagewise_language_qa_tsv",
        "automated_visual_qa",
        "visual_final_qa",
        "final_qa_bindings",
        "reader_qa_verifier",
    )
    rows = []
    for role in roles:
        record = config["inputs"][role]
        rows.append((f"evidence/{role}/{Path(record['path']).name}", repo_path(record["path"])))
    return rows


def package(*, replace: bool) -> dict:
    config = load_config(package_required=False)
    source_rows, source_exclusions = source_manifest_rows()
    backend_rows, backend_exclusions, _backend_manifest = backend_public_rows()
    with tempfile.TemporaryDirectory(prefix="r011-b024-package-") as temp_name:
        temp = Path(temp_name)
        reader_name, source_name, backend_name = ORDERED_RELEASE_ASSETS[:3]
        shutil.copyfile(repo_path(config["inputs"]["reader"]["path"]), temp / reader_name)
        if identity(temp / reader_name)["sha256"] != config["inputs"]["reader"]["sha256"]:
            raise ReleaseGateError("copied B024 reader differs from bound reader")

        source_zip_rows = [(row["path"], row["source"]) for row in source_rows]
        source_zip_rows.extend((path, repo_path(path)) for path in SOURCE_TOOLING)
        deterministic_zip(temp / source_name, source_zip_rows)

        projection = temp / "PUBLIC_BACKEND_MANIFEST.json"
        atomic_write(projection, _public_backend_manifest(config, backend_rows, backend_exclusions))
        backend_zip_rows = [("exports/" + row["path"], row["source"]) for row in backend_rows]
        backend_zip_rows.append(("exports/manifest.json", projection))
        backend_zip_rows.extend(_backend_evidence_rows(config))
        backend_zip_rows.append(("release/RELEASE_INPUTS.json", CONFIG_PATH))
        deterministic_zip(temp / backend_name, backend_zip_rows)

        atomic_write(temp / "CITATION.cff", _citation(config))
        atomic_write(temp / "LICENSES_AND_ATTRIBUTION.md", _licenses(config))
        atomic_write(temp / "README_RELEASE.md", _readme(config))
        atomic_write(temp / "ZENODO_METADATA.json", canonical_json_bytes(zenodo_metadata(config)))

        hashed_names = list(ORDERED_RELEASE_ASSETS[:6]) + [ORDERED_RELEASE_ASSETS[8]]
        file_rows = []
        for name in hashed_names:
            item = identity(temp / name)
            file_rows.append({"filename": name, "bytes": item["bytes"], "sha256": item["sha256"]})
        manifest = {
            "$schema": "r011-b024-release-manifest/v1",
            "boundary_id": BOUNDARY_ID,
            "release_id": RELEASE_ID,
            "version": config["version"],
            "status": "PACKAGED_VERIFIED",
            "completion_state": "partial",
            "complete_corpus": False,
            "learner_reader_pages": EXPECTED_READER_PAGES,
            "accepted_indonesian_reader_pages": EXPECTED_READER_PAGES,
            "untranslated_instructional_or_exercise_prose_pages": 0,
            "all_pages_language_adjudicated": True,
            "all_pages_visually_inspected": True,
            "through": config["coverage"]["through"],
            "exercise_ids": list(range(1, 35)),
            "public_answer_ids": list(range(1, 34, 2)),
            "o001_gap_ids": list(range(2, 35, 2)),
            "restricted_solutions_used": False,
            "full_source_closure_contains_untranslated_source": True,
            "source_closure_counted_as_learner_output": False,
            "page_count_is_artifact_extent_not_translation_progress": True,
            "production_model": MODEL,
            "authority": config["authority"],
            "coverage": config["coverage"],
            "next_cursor": config["next_cursor"],
            "inputs": config["inputs"],
            "source_package": {
                "snapshot_entries": config["source_package"]["manifest_entries"],
                "snapshot_public_entries": len(source_rows),
                "reproducibility_tool_entries": len(SOURCE_TOOLING),
                "packaged_entries": len(source_zip_rows),
                "packaged_bytes_uncompressed": sum(path.stat().st_size for _name, path in source_zip_rows),
                "exclusions": source_exclusions,
                "canonical_snapshot_mutated": False,
            },
            "backend_package": {
                "compact_projection_entries": len(backend_rows),
                "compact_projection_bytes": sum(row["bytes"] for row in backend_rows),
                "archive_entries": len(backend_zip_rows),
                "excluded_internal_evidence_file_count": len(backend_exclusions),
                "admitted_backend_mutated": False,
            },
            "ordered_assets": list(ORDERED_RELEASE_ASSETS),
            "files": file_rows,
            "reader_first": True,
            "publication_performed": False,
            "no_upstream_contact": True,
        }
        atomic_write(temp / "RELEASE_MANIFEST.json", canonical_json_bytes(manifest))
        atomic_write(
            temp / "SHA256SUMS.txt",
            "".join(f"{row['sha256']}  {row['filename']}\n" for row in file_rows).encode("utf-8"),
        )
        for name in ORDERED_RELEASE_ASSETS:
            if not (temp / name).is_file():
                raise ReleaseGateError(f"packager failed to create {name}")
        existing = [name for name in ORDERED_RELEASE_ASSETS if (RELEASE_DIR / name).exists()]
        if existing and not replace:
            raise ReleaseGateError("B024 package targets exist; inspect them before --replace: " + ", ".join(existing))
        RELEASE_DIR.mkdir(parents=True, exist_ok=True)
        for name in ORDERED_RELEASE_ASSETS:
            (temp / name).replace(RELEASE_DIR / name)
    verified = verify_release_package(config)
    return {
        "$schema": "r011-b024-package-receipt/v1",
        "boundary_id": BOUNDARY_ID,
        "release_id": RELEASE_ID,
        "status": "PASS_PACKAGED_VERIFIED",
        "ordered_assets": [identity(path) for path in release_assets(config)],
        "manifest": identity(RELEASE_DIR / "RELEASE_MANIFEST.json"),
        "source_exclusion_count": len(verified["source_package"]["exclusions"]),
        "learner_reader_pages": EXPECTED_READER_PAGES,
        "untranslated_instructional_or_exercise_prose_pages": 0,
        "publication_performed": False,
        "network_used": False,
        "credentials_read": False,
        "local_git_used": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--self-check", action="store_true")
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--package", action="store_true")
    mode.add_argument("--verify", action="store_true")
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        print(json.dumps(static_self_check("b024-packager"), ensure_ascii=False, sort_keys=True))
        return 0
    if args.dry_run:
        result = static_self_check("b024-packager-dry-run")
        result.update({"status": "PASS_DRY_RUN_NO_WRITES", "would_create_release_package": True, "ordered_assets": list(ORDERED_RELEASE_ASSETS)})
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    if args.verify:
        if args.replace:
            parser.error("--replace is valid only with --package")
        config = load_config(package_required=True)
        print(json.dumps({"status": "PASS_PACKAGE_REVERIFIED", "manifest": verify_release_package(config)}, ensure_ascii=False, sort_keys=True))
        return 0
    print(json.dumps(package(replace=args.replace), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ReleaseGateError as exc:
        raise SystemExit(f"REFUSED: {exc}")
