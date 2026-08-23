#!/usr/bin/env python3
"""Create the deterministic R011-B008 reader-first release package.

The package branch is intentionally unreachable until RELEASE_INPUTS.json binds
all terminal admission identities and marks the state READY_FOR_PACKAGING.
"""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path

from release_b008_common import (
    BOUNDARY_ID,
    EXCLUDED_SOURCE_PATH,
    MODEL,
    RELEASE_DIR,
    RELEASE_ID,
    ReleaseGateError,
    atomic_write,
    canonical_json_bytes,
    deterministic_zip,
    emit_self_check,
    execution_preflight,
    identity,
    read_backend_inventory,
    read_snapshot_manifest,
    render_template,
    verify_release_package,
)


def _replace_targets(temp_dir: Path, names: list[str], *, replace: bool) -> None:
    existing = [name for name in names if (RELEASE_DIR / name).exists()]
    if existing and not replace:
        raise ReleaseGateError(
            "package targets already exist; inspect them and pass --replace only for this exact B008 package: "
            + ", ".join(existing)
        )
    for name in names:
        source = temp_dir / name
        destination = RELEASE_DIR / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        source.replace(destination)


def package(*, replace: bool) -> dict:
    config, terminal_verified = execution_preflight(component="packager")
    source_rows = read_snapshot_manifest(config)
    excluded = [row for row in source_rows if row["path"] == EXCLUDED_SOURCE_PATH]
    if len(excluded) != 1:
        raise ReleaseGateError("source closure must contain exactly the recorded excluded component")
    included_source = [row for row in source_rows if row["path"] != EXCLUDED_SOURCE_PATH]
    backend_rows = read_backend_inventory(config)

    names = config["ordered_release_assets"]
    with tempfile.TemporaryDirectory(prefix="r011-b008-package-") as temp_name:
        temp_dir = Path(temp_name)
        reader_name, source_name, backend_name = names[:3]

        promoted_pdf = Path(terminal_verified["promoted_pdf"]["path"])
        # terminal_verified paths are repository-relative strings; execution_preflight
        # already verified the source, and the config gives the authoritative path.
        from release_b008_common import repo_path

        promoted_pdf = repo_path(config["terminal_inputs"]["promoted_pdf"]["path"])
        shutil.copyfile(promoted_pdf, temp_dir / reader_name)
        if identity(temp_dir / reader_name)["sha256"] != config["accepted_v3"]["candidate_pdf"]["sha256"]:
            raise ReleaseGateError("copied reader differs from accepted V3 PDF")

        deterministic_zip(
            temp_dir / source_name,
            [(row["path"], row["source"]) for row in included_source],
        )

        backend_zip_rows: list[tuple[str, Path]] = [
            ("admitted/" + row["path"], row["source"]) for row in backend_rows
        ]
        evidence_names = (
            "source_manifest",
            "source_qa",
            "build_receipt",
            "build_visual_sanity",
            "root_visual_audit",
        )
        for key in evidence_names:
            record = config["accepted_v3"][key]
            backend_zip_rows.append(("evidence/accepted/" + record["path"], repo_path(record["path"])))
        for key, record in config["terminal_inputs"].items():
            if key in {"promoted_pdf", "backend_inventory"}:
                continue
            backend_zip_rows.append(
                (
                    "evidence/terminal/" + key + "/" + Path(record["path"]).name,
                    repo_path(record["path"]),
                )
            )
        backend_zip_rows.append(("release/RELEASE_INPUTS.json", RELEASE_DIR / "RELEASE_INPUTS.json"))
        archive_names = [name for name, _ in backend_zip_rows]
        if len(archive_names) != len(set(archive_names)):
            raise ReleaseGateError("backend ZIP archive-name collision")
        deterministic_zip(temp_dir / backend_name, backend_zip_rows)

        template_map = {
            "CITATION.cff": "CITATION.template.cff",
            "LICENSES_AND_ATTRIBUTION.md": "LICENSES_AND_ATTRIBUTION.template.md",
            "README_RELEASE.md": "README_RELEASE.template.md",
            "ZENODO_METADATA.json": "ZENODO_METADATA.template.json",
        }
        for destination, template in template_map.items():
            atomic_write(temp_dir / destination, render_template(RELEASE_DIR / template, {}))

        hashed_names = names[:6] + [names[8]]
        file_rows = []
        for name in hashed_names:
            item = identity(temp_dir / name)
            file_rows.append({"filename": name, "bytes": item["bytes"], "sha256": item["sha256"]})

        manifest = {
            "$schema": "r011-b008-release-manifest/v1",
            "boundary_id": BOUNDARY_ID,
            "release_id": RELEASE_ID,
            "version": config["version"],
            "status": "PACKAGED_VERIFIED",
            "complete_corpus": False,
            "completion_state": "partial",
            "production_model": MODEL,
            "license": {
                "text_and_translation": "CC BY-SA 3.0 Unported",
                "component_rights_override": True,
            },
            "coverage": config["coverage"],
            "authority": config["authority"],
            "accepted_v3": config["accepted_v3"],
            "terminal_inputs": {
                key: {
                    "role": record["role"],
                    "path": record["path"],
                    "bytes": record["bytes"],
                    "sha256": record["sha256"],
                }
                for key, record in config["terminal_inputs"].items()
            },
            "source_package": {
                "snapshot_entries": len(source_rows),
                "packaged_entries": len(included_source),
                "excluded": {
                    "path": excluded[0]["path"],
                    "bytes": excluded[0]["bytes"],
                    "sha256": excluded[0]["sha256"],
                    "reason": "component-specific rights do not support public redistribution",
                },
            },
            "backend_package": {
                "admitted_inventory_entries": len(backend_rows),
                "archive_entries": len(backend_zip_rows),
            },
            "ordered_assets": names,
            "files": file_rows,
            "reader_first": True,
            "no_upstream_contact": True,
        }
        atomic_write(temp_dir / "RELEASE_MANIFEST.json", canonical_json_bytes(manifest))
        sums = "".join(f"{row['sha256']}  {row['filename']}\n" for row in file_rows)
        atomic_write(temp_dir / "SHA256SUMS.txt", sums.encode("utf-8"))

        # Verify all expected names exist before the bounded replace.
        for name in names:
            if not (temp_dir / name).is_file():
                raise ReleaseGateError(f"packager failed to create {name}")
        _replace_targets(temp_dir, names, replace=replace)

    verified_manifest = verify_release_package(config)
    return {
        "schema": "r011-b008-package-receipt/v1",
        "boundary_id": BOUNDARY_ID,
        "release_id": RELEASE_ID,
        "status": "PASS_PACKAGED_VERIFIED",
        "ordered_assets": [identity(RELEASE_DIR / name) for name in names],
        "manifest_sha256": identity(RELEASE_DIR / "RELEASE_MANIFEST.json")["sha256"],
        "source_exclusion": verified_manifest["source_package"]["excluded"],
        "publication_performed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--self-check", action="store_true", help="offline, read-only static gate")
    mode.add_argument("--package", action="store_true", help="create package after terminal admission")
    parser.add_argument("--replace", action="store_true", help="replace only exact B008 package targets")
    args = parser.parse_args()
    if args.self_check:
        if args.replace:
            parser.error("--replace is valid only with --package")
        return emit_self_check("packager")
    receipt = package(replace=args.replace)
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ReleaseGateError as exc:
        raise SystemExit(f"REFUSED: {exc}")
