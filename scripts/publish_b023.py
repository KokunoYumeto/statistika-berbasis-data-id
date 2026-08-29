#!/usr/bin/env python3
"""Publish verified R011-B023 bytes to the existing Zenodo/GitHub lineages.

``--self-check`` and ``--dry-run`` are strictly offline.  Only ``--publish``
may read a credential and enter a remote transaction.  Publication uses REST
APIs, collision preflights, exact content-addressed GitHub trees, and anonymous
readback of every public file; no local Git command or upstream-contact route is
present in this module.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import sys
from pathlib import Path, PurePosixPath
from urllib.parse import quote

import requests

sys.dont_write_bytecode = True

from package_b023 import SOURCE_TOOLING, zenodo_metadata
from release_b023_common import (
    BOUNDARY_ID,
    MODEL,
    ORDERED_RELEASE_ASSETS,
    PUBLICATION_STATUSES,
    RELEASE_DIR,
    RELEASE_ID,
    REPO_ROOT,
    VERSION,
    ReleaseGateError,
    atomic_write,
    backend_public_rows,
    canonical_json_bytes,
    identity,
    load_config,
    load_json,
    md5_file,
    release_assets,
    repo_path,
    source_manifest_rows,
    static_self_check,
    verify_release_package,
)
from publish_b018 import (  # proven bounded HTTP/content-addressed primitives
    B017GateError as TransportGateError,
    GitHubClient,
    ZenodoClient,
    ZENODO_API,
    _fixed_redirect_get,
    _git_blob_sha,
    _github_create_hierarchical_tree,
    _github_head,
    _github_tree,
    _is_sha1,
    _stream_sha,
    _zenodo_public_json,
    _zenodo_public_request,
    _zenodo_public_versions,
    token_from_file,
)


ZENODO_RECEIPT_PATH = (
    REPO_ROOT / "qa" / "b023-publication" / f"ZENODO_PUBLICATION_RECEIPT_{RELEASE_ID}.json"
)
GITHUB_RECEIPT_PATH = RELEASE_DIR / "GITHUB_PUBLICATION_RECEIPT.json"
ZENODO_CREATORS = (
    "Diez, David M.",
    "Çetinkaya-Rundel, Mine",
    "Barr, Christopher D.",
)


def _expected_assets(config: dict) -> list[dict]:
    rows = []
    for path in release_assets(config):
        item = identity(path)
        rows.append(
            {
                "filename": path.name,
                "bytes": item["bytes"],
                "sha256": item["sha256"],
                "md5": md5_file(path),
            }
        )
    if [row["filename"] for row in rows] != list(ORDERED_RELEASE_ASSETS):
        raise ReleaseGateError("public asset order changed")
    return rows


def _normalized_zenodo_metadata(value: dict) -> dict:
    metadata = value.get("metadata") if isinstance(value.get("metadata"), dict) else value
    if not isinstance(metadata, dict):
        raise ReleaseGateError("Zenodo metadata is malformed")
    metadata = dict(metadata)
    if isinstance(metadata.get("license"), dict):
        metadata["license"] = metadata["license"].get("id")
    resource_type = metadata.get("resource_type")
    if isinstance(resource_type, dict):
        if resource_type.get("type") == "publication":
            metadata.setdefault("upload_type", "publication")
        if resource_type.get("subtype") == "book":
            metadata.setdefault("publication_type", "book")
    return metadata


def _validate_zenodo_metadata(config: dict, value: dict) -> dict:
    metadata = _normalized_zenodo_metadata(value)
    expected = zenodo_metadata(config)["metadata"]
    creators = tuple(row.get("name") for row in metadata.get("creators", []) if isinstance(row, dict))
    contributors = tuple(row.get("name") for row in metadata.get("contributors", []) if isinstance(row, dict))
    description = str(metadata.get("description", ""))
    notes = str(metadata.get("notes", ""))
    folded = description.casefold()
    checks = {
        "title": metadata.get("title") == expected["title"],
        "version": metadata.get("version") == VERSION,
        "publication_date": metadata.get("publication_date") == config["release_date"],
        "upload_type": metadata.get("upload_type") == "publication",
        "publication_type": metadata.get("publication_type") == "book",
        "license": metadata.get("license") == "cc-by-sa-3.0",
        "language": metadata.get("language") == "ind",
        "access": metadata.get("access_right", "open") == "open",
        "creators": creators == ZENODO_CREATORS,
        "contributor": contributors == ("Codex",),
        "model": MODEL in description and MODEL in notes,
        "partial": "parsial" in folded and "partial" in notes.casefold(),
        "reader_pages": "241 halaman" in description,
        "scope": "Bagian 6.2" in description,
        "exercise_closure": "nomor ganjil 1 sampai 29" in description and "nomor genap 2 sampai 30" in description,
        "no_restricted_solutions": "tidak ada solusi instruktur terbatas" in folded,
        "source_not_output": "bukan keluaran pembelajar" in folded,
        "credits": all(name.split(",")[0] in description for name in ZENODO_CREATORS),
    }
    failed = [key for key, passed in checks.items() if not passed]
    if failed:
        raise ReleaseGateError(f"Zenodo metadata truth mismatch: {failed}")
    return metadata


def _public_zenodo_readback(record_id: int, expected: list[dict], config: dict) -> dict:
    record = _zenodo_public_json(f"{ZENODO_API}/records/{record_id}")
    if int(record.get("conceptrecid", -1)) != 22059801 or record.get("doi") != f"10.5281/zenodo.{record_id}":
        raise ReleaseGateError("Zenodo public record escaped the existing concept")
    metadata = _validate_zenodo_metadata(config, record)
    files = record.get("files") or []
    by_name = {row.get("key"): row for row in files if isinstance(row, dict) and isinstance(row.get("key"), str)}
    if len(by_name) != len(files) or set(by_name) != {row["filename"] for row in expected}:
        raise ReleaseGateError("Zenodo public file inventory mismatch")
    verified = []
    for wanted in expected:
        remote = by_name[wanted["filename"]]
        link = remote.get("links", {}).get("self") or remote.get("links", {}).get("content")
        if not isinstance(link, str):
            raise ReleaseGateError(f"Zenodo public file lacks content link: {wanted['filename']}")
        response = _zenodo_public_request(link, preload_content=False)
        if response.status != 200:
            response.release_conn()
            raise ReleaseGateError(f"Zenodo anonymous readback failed: {wanted['filename']}")
        digest = hashlib.sha256()
        count = 0
        try:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                count += len(chunk)
                digest.update(chunk)
        finally:
            response.release_conn()
        if (count, digest.hexdigest()) != (wanted["bytes"], wanted["sha256"]):
            raise ReleaseGateError(f"Zenodo anonymous byte mismatch: {wanted['filename']}")
        verified.append({"filename": wanted["filename"], "bytes": count, "sha256": digest.hexdigest()})
    return {"record": record, "metadata": metadata, "files": verified}


def _zenodo_versions(client: ZenodoClient) -> list[dict]:
    result = client.json(
        "GET",
        f"{ZENODO_API}/records",
        params={"q": "conceptrecid:22059801", "all_versions": "true", "size": 100, "sort": "mostrecent"},
    )
    versions = result.get("hits", {}).get("hits")
    if not isinstance(versions, list):
        raise ReleaseGateError("Zenodo concept inventory is malformed")
    return versions


def _verify_zenodo_prior(config: dict, versions: list[dict]) -> None:
    if not versions:
        raise ReleaseGateError("Zenodo concept has no public predecessor")
    head = versions[0]
    destination = config["destinations"]["zenodo"]
    if (
        int(head.get("id", -1)) != destination["prior_record_id"]
        or int(head.get("conceptrecid", -1)) != destination["concept_record_id"]
        or head.get("metadata", {}).get("version") != destination["prior_version"]
    ):
        raise ReleaseGateError("Zenodo public head no longer matches pinned B022")


def _zenodo_draft_id(url: str) -> int:
    prefix = f"{ZENODO_API}/deposit/depositions/"
    if not url.startswith(prefix):
        raise ReleaseGateError("Zenodo draft link escaped fixed deposition route")
    tail = url[len(prefix):].strip("/")
    if not tail.isdigit():
        raise ReleaseGateError("Zenodo draft link is malformed")
    return int(tail)


def _discover_zenodo_draft(client: ZenodoClient, prior: dict, config: dict) -> dict | None:
    link = prior.get("links", {}).get("latest_draft")
    if not isinstance(link, str):
        return None
    draft_id = _zenodo_draft_id(link)
    if draft_id == config["destinations"]["zenodo"]["prior_record_id"]:
        return None
    draft = client.json("GET", link)
    if (
        int(draft.get("conceptrecid", -1)) != 22059801
        or str(draft.get("state", "")).casefold() not in {"unsubmitted", "draft"}
        or draft.get("submitted") is True
    ):
        raise ReleaseGateError("Zenodo latest draft is foreign or submitted")
    return draft


def _verify_zenodo_draft_files(client: ZenodoClient, draft: dict, expected: list[dict]) -> list[dict]:
    files = draft.get("files") or []
    by_name = {row.get("filename"): row for row in files if isinstance(row, dict) and isinstance(row.get("filename"), str)}
    if len(by_name) != len(files) or set(by_name) != {row["filename"] for row in expected}:
        raise ReleaseGateError("Zenodo draft exact file inventory mismatch")
    verified = []
    for wanted in expected:
        remote = by_name[wanted["filename"]]
        checksum = str(remote.get("checksum", "")).removeprefix("md5:")
        size = int(remote.get("filesize", remote.get("size", -1)))
        if (checksum, size) != (wanted["md5"], wanted["bytes"]):
            raise ReleaseGateError(f"Zenodo draft file mismatch: {wanted['filename']}")
        link = remote.get("links", {}).get("download")
        if not isinstance(link, str):
            raise ReleaseGateError(f"Zenodo draft file lacks download link: {wanted['filename']}")
        response = _fixed_redirect_get(client.session, link, hosts={"zenodo.org", "files.zenodo.org"}, stream=True)
        if response.status_code != 200:
            raise ReleaseGateError(f"Zenodo draft readback failed: {wanted['filename']}")
        count, digest = _stream_sha(response)
        if (count, digest) != (wanted["bytes"], wanted["sha256"]):
            raise ReleaseGateError(f"Zenodo draft byte mismatch: {wanted['filename']}")
        verified.append({"filename": wanted["filename"], "bytes": count, "sha256": digest})
    return verified


def _zenodo_receipt(config: dict, record_id: int, readback: dict, status: str) -> dict:
    receipt = {
        "$schema": "r011-b023-zenodo-publication-receipt/v1",
        "boundary_id": BOUNDARY_ID,
        "release_id": RELEASE_ID,
        "status": status,
        "concept_doi": "10.5281/zenodo.22059801",
        "concept_record_id": 22059801,
        "record_id": record_id,
        "doi": f"10.5281/zenodo.{record_id}",
        "public_url": f"https://zenodo.org/records/{record_id}",
        "version": VERSION,
        "access_right": "open",
        "license_id": "cc-by-sa-3.0",
        "production_model": MODEL,
        "learner_reader_pages": 241,
        "through": "Bab 6, Bagian 6.2 Selisih dua proporsi",
        "exercise_ids": list(range(1, 31)),
        "public_answer_ids": list(range(1, 30, 2)),
        "o001_gap_ids": list(range(2, 31, 2)),
        "untranslated_instructional_or_exercise_prose_pages": 0,
        "source_closure_counted_as_learner_output": False,
        "ordered_files": readback["files"],
        "metadata_exactly_verified": True,
        "collision_preflight_before_mutation": True,
        "anonymous_public_byte_readback": True,
        "credentials_recorded": False,
        "local_git_used": False,
        "upstream_contact": False,
    }
    atomic_write(ZENODO_RECEIPT_PATH, canonical_json_bytes(receipt))
    return receipt


def _zenodo_token() -> str:
    override = os.environ.get("INTERLANGUAGE_ZENODO_TOKEN_FILE")
    candidates = ([Path(override)] if override else []) + [
        Path.home() / "Documents" / "Obsidian notes" / "New zenodo token.md",
        Path.home() / "Downloads" / "Zenodo token.md",
    ]
    path = next((item for item in candidates if item.is_file()), None)
    if path is None:
        raise ReleaseGateError("Zenodo credential file is absent")
    return token_from_file(path, service="zenodo")


def publish_zenodo(config: dict) -> dict:
    expected = _expected_assets(config)
    public_versions = _zenodo_public_versions(22059801)
    matches = [row for row in public_versions if row.get("metadata", {}).get("version") == VERSION]
    if len(matches) > 1:
        raise ReleaseGateError("multiple Zenodo records claim the B023 version")
    if matches:
        record_id = int(matches[0]["id"])
        return _zenodo_receipt(config, record_id, _public_zenodo_readback(record_id, expected, config), "ALREADY_PUBLISHED_AND_ANONYMOUSLY_REVERIFIED")
    _verify_zenodo_prior(config, public_versions)

    client = ZenodoClient(_zenodo_token())
    versions = _zenodo_versions(client)
    matches = [row for row in versions if row.get("metadata", {}).get("version") == VERSION]
    if matches:
        record_id = int(matches[0]["id"])
        return _zenodo_receipt(config, record_id, _public_zenodo_readback(record_id, expected, config), "ALREADY_PUBLISHED_AND_ANONYMOUSLY_REVERIFIED")
    _verify_zenodo_prior(config, versions)
    prior_id = config["destinations"]["zenodo"]["prior_record_id"]
    prior = client.json("GET", f"{ZENODO_API}/deposit/depositions/{prior_id}")
    if int(prior.get("id", prior.get("record_id", -1))) != prior_id or int(prior.get("conceptrecid", -1)) != 22059801 or prior.get("state") != "done":
        raise ReleaseGateError("Zenodo authenticated B022 predecessor changed")
    draft = _discover_zenodo_draft(client, prior, config)
    if draft is None:
        try:
            created = client.json("POST", f"{ZENODO_API}/deposit/depositions/{prior_id}/actions/newversion", expected=(201, 202))
            link = created.get("links", {}).get("latest_draft")
            if not isinstance(link, str):
                raise ReleaseGateError("Zenodo new-version response lacks latest_draft")
            draft = client.json("GET", link)
        except (ReleaseGateError, TransportGateError):
            prior = client.json("GET", f"{ZENODO_API}/deposit/depositions/{prior_id}")
            draft = _discover_zenodo_draft(client, prior, config)
            if draft is None:
                raise
    draft_id = int(draft.get("id", -1))
    if draft_id < 0 or int(draft.get("conceptrecid", -1)) != 22059801:
        raise ReleaseGateError("Zenodo B023 draft identity is malformed")
    bucket = draft.get("links", {}).get("bucket")
    if not isinstance(bucket, str) or not bucket.startswith("https://zenodo.org/api/files/"):
        raise ReleaseGateError("Zenodo B023 draft lacks fixed upload bucket")
    expected_by_name = {row["filename"]: row for row in expected}
    remote = {row.get("filename"): row for row in draft.get("files") or [] if isinstance(row, dict) and isinstance(row.get("filename"), str)}
    for name, item in list(remote.items()):
        wanted = expected_by_name.get(name)
        checksum = str(item.get("checksum", "")).removeprefix("md5:")
        size = int(item.get("filesize", item.get("size", -1)))
        if wanted and (checksum, size) == (wanted["md5"], wanted["bytes"]):
            continue
        file_id = item.get("id")
        if not file_id:
            raise ReleaseGateError("Zenodo draft file lacks deletion identity")
        client.request("DELETE", f"{ZENODO_API}/deposit/depositions/{draft_id}/files/{file_id}", expected=(204,))
        remote.pop(name, None)
    for path, wanted in zip(release_assets(config), expected):
        if path.name in remote:
            continue
        with path.open("rb") as source:
            client.request("PUT", bucket.rstrip("/") + "/" + quote(path.name, safe=""), expected=(200, 201), data=source, headers={"Content-Type": "application/octet-stream"})
    metadata = load_json(RELEASE_DIR / "ZENODO_METADATA.json")
    _validate_zenodo_metadata(config, metadata)
    client.json("PUT", f"{ZENODO_API}/deposit/depositions/{draft_id}", data=canonical_json_bytes(metadata), headers={"Content-Type": "application/json"})
    draft = client.json("GET", f"{ZENODO_API}/deposit/depositions/{draft_id}")
    _validate_zenodo_metadata(config, draft)
    _verify_zenodo_draft_files(client, draft, expected)
    guard = _zenodo_versions(client)
    if any(row.get("metadata", {}).get("version") == VERSION for row in guard):
        raise ReleaseGateError("B023 Zenodo version appeared concurrently before publish")
    _verify_zenodo_prior(config, guard)
    published = client.json("POST", f"{ZENODO_API}/deposit/depositions/{draft_id}/actions/publish", expected=(201, 202))
    record_id = int(published.get("record_id", published.get("id", -1)))
    if record_id < 0:
        raise ReleaseGateError("Zenodo publish response lacks record id")
    return _zenodo_receipt(config, record_id, _public_zenodo_readback(record_id, expected, config), "PUBLISHED_AND_ANONYMOUSLY_VERIFIED")


def _safe_tree_path(value: str) -> str:
    pure = PurePosixPath(value)
    if pure.is_absolute() or ".." in pure.parts or not pure.parts:
        raise ReleaseGateError(f"unsafe GitHub tree path: {value!r}")
    return pure.as_posix()


def _github_values(config: dict, zenodo: dict) -> dict[str, bytes]:
    values: dict[str, bytes] = {}

    def add(path: str, raw: bytes) -> None:
        safe = _safe_tree_path(path)
        if safe in values and values[safe] != raw:
            raise ReleaseGateError(f"conflicting GitHub tree bytes: {safe}")
        values[safe] = raw

    source_rows, _source_exclusions = source_manifest_rows()
    for row in source_rows:
        if row["path"] not in {"README.md", "LICENSE.md", "CITATION.cff"}:
            add("source/full-source-closure/" + row["path"], row["source"].read_bytes())
    for path in SOURCE_TOOLING + (
        "scripts/release_b023_common.py",
        "scripts/prepare_b023_release.py",
        "scripts/package_b023.py",
        "scripts/publish_b023.py",
    ):
        add(path, repo_path(path).read_bytes())
    backend_rows, backend_exclusions, _backend_manifest = backend_public_rows()
    for row in backend_rows:
        add("backend/exports/" + row["path"], row["source"].read_bytes())
    projection = {
        "$schema": "r011-b023-github-public-backend-projection/v1",
        "boundary_id": BOUNDARY_ID,
        "release_id": RELEASE_ID,
        "upstream_backend_manifest": config["inputs"]["backend_manifest"],
        "reader": config["inputs"]["reader"],
        "scope": config["coverage"],
        "files": [{key: row[key] for key in ("path", "bytes", "sha256")} for row in backend_rows],
        "excluded_internal_evidence_file_count": len(backend_exclusions),
        "source_closure_counted_as_learner_output": False,
    }
    add("backend/exports/manifest.json", canonical_json_bytes(projection))
    for role, record in config["inputs"].items():
        if role not in {
            "backend_manifest",
            "prior_zenodo_receipt",
            "prior_github_receipt",
        }:
            add(record["path"], repo_path(record["path"]).read_bytes())
    for name in ("RELEASE_INPUTS.json", *ORDERED_RELEASE_ASSETS[3:]):
        path = RELEASE_DIR / name
        add(path.relative_to(REPO_ROOT).as_posix(), path.read_bytes())
    readme = (RELEASE_DIR / "README_RELEASE.md").read_text(encoding="utf-8")
    add("README.md", (readme + f"\n## Repositori publik\n\n- Zenodo: <{zenodo['public_url']}>\n").encode("utf-8"))
    add("CITATION.cff", (RELEASE_DIR / "CITATION.cff").read_bytes())
    add("LICENSE.md", (RELEASE_DIR / "LICENSES_AND_ATTRIBUTION.md").read_bytes())
    add(
        "00_control/PUBLICATION_STATE_R011-B023.md",
        (
            "# Status publikasi R011-B023\n\n"
            "Edisi kerja parsial: pembaca bersih 241 halaman hingga Bab 6 Bagian 6.2; "
            "nol halaman prosa instruksional/latihan/jawaban publik berbahasa Inggris. "
            "Latihan 1-30; jawaban publik ganjil 1-29; kesenjangan O001 genap 2-30. "
            "Korpus lengkap: tidak. Arsip sumber lengkap memuat ekor sumber yang belum "
            "diterjemahkan dan bukan keluaran pembelajar.\n\n"
            f"Zenodo: {zenodo['public_url']}\n\nModel produksi: {MODEL}.\n\n"
            "Tidak ada kontak hulu yang dilakukan.\n"
        ).encode("utf-8"),
    )
    add(
        "00_control/PUBLICATION_CURSOR_R011-B023.json",
        canonical_json_bytes(
            {
                "$schema": "r011-b023-github-publication-cursor/v1",
                "boundary_id": BOUNDARY_ID,
                "release_id": RELEASE_ID,
                "status": "ready_for_bounded_github_transaction",
                "zenodo_public_url": zenodo["public_url"],
                "tag": config["destinations"]["github"]["tag"],
                "learner_reader_pages": 241,
                "through": config["coverage"]["through"],
                "untranslated_instructional_or_exercise_prose_pages": 0,
                "source_closure_counted_as_learner_output": False,
                "next_cursor": config["next_cursor"],
                "production_model": MODEL,
                "no_upstream_contact": True,
            }
        ),
    )
    if sum(len(raw) for raw in values.values()) > 100_000_000:
        raise ReleaseGateError("bounded GitHub tree allowlist exceeds 100MB")
    return values


def _github_release_contract(config: dict, zenodo: dict) -> dict:
    return {
        "tag_name": config["destinations"]["github"]["tag"],
        "name": "R011-B023 - pembaca Bahasa Indonesia hingga Bagian 6.2",
        "body": (
            "Rilis kerja parsial dengan pembaca bersih 241 halaman hingga Bab 6, "
            "Bagian 6.2. Latihan 1-30 disertakan; jawaban publik ganjil 1-29; "
            "kesenjangan O001 genap 2-30. Korpus lengkap: tidak. Nol halaman prosa "
            "instruksional/latihan/jawaban publik berbahasa Inggris. Arsip sumber "
            "lengkap memuat ekor sumber yang belum diterjemahkan untuk reproduksibilitas "
            f"dan bukan keluaran pembelajar. Zenodo: {zenodo['public_url']}\n\n"
            f"Model: {MODEL}. Tidak ada kontak hulu yang dilakukan."
        ),
        "draft": False,
        "prerelease": True,
    }


def _validate_github_release_metadata(release: dict, contract: dict) -> None:
    checks = {
        "tag": release.get("tag_name") == contract["tag_name"],
        "name": release.get("name") == contract["name"],
        "body": release.get("body") == contract["body"],
        "draft": release.get("draft") is False,
        "prerelease": release.get("prerelease") is True,
    }
    failed = [key for key, passed in checks.items() if not passed]
    if failed:
        raise ReleaseGateError(f"GitHub release metadata mismatch: {failed}")


def _github_public_download(url: str, wanted: dict) -> dict:
    session = requests.Session()
    session.trust_env = False
    session.headers["User-Agent"] = "interlanguage-r011-b023-public-readback/1"
    response = _fixed_redirect_get(
        session,
        url,
        hosts={"github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com"},
        stream=True,
    )
    if response.status_code != 200:
        raise ReleaseGateError(f"GitHub anonymous asset readback returned HTTP {response.status_code}")
    count, digest = _stream_sha(response)
    if (count, digest) != (wanted["bytes"], wanted["sha256"]):
        raise ReleaseGateError(f"GitHub anonymous asset mismatch: {wanted['filename']}")
    return {"filename": wanted["filename"], "bytes": count, "sha256": digest}


def _github_readback(config: dict, release: dict, commit_sha: str, desired: dict[str, str], expected: list[dict], contract: dict) -> dict:
    gh = config["destinations"]["github"]
    public = GitHubClient(None, gh["owner"], gh["repository"])
    public_release = public.json("GET", f"releases/tags/{quote(gh['tag'], safe='')}")
    if int(public_release.get("id", -1)) != int(release.get("id", -2)):
        raise ReleaseGateError("GitHub anonymous release identity mismatch")
    _validate_github_release_metadata(public_release, contract)
    public_commit = public.json("GET", f"git/commits/{commit_sha}")
    tree_sha = public_commit.get("tree", {}).get("sha")
    tree = _github_tree(public, tree_sha)
    if set(tree) != set(desired) or any(tree[path].get("sha") != digest for path, digest in desired.items()):
        raise ReleaseGateError("GitHub anonymous exact-tree readback mismatch")
    assets = public_release.get("assets") or []
    by_name = {row.get("name"): row for row in assets if isinstance(row, dict) and isinstance(row.get("name"), str)}
    if len(by_name) != len(assets) or set(by_name) != {row["filename"] for row in expected}:
        raise ReleaseGateError("GitHub release asset inventory mismatch")
    verified = []
    for wanted in expected:
        remote = by_name[wanted["filename"]]
        if int(remote.get("size", -1)) != wanted["bytes"]:
            raise ReleaseGateError(f"GitHub release asset size mismatch: {wanted['filename']}")
        url = remote.get("browser_download_url")
        if not isinstance(url, str):
            raise ReleaseGateError("GitHub release asset lacks public URL")
        verified.append(_github_public_download(url, wanted))
    return {"assets": verified, "tree_path_count": len(tree)}


def _github_token() -> str:
    if os.environ.get("GITHUB_TOKEN"):
        return os.environ["GITHUB_TOKEN"]
    override = os.environ.get("INTERLANGUAGE_GITHUB_TOKEN_FILE")
    candidates = ([Path(override)] if override else []) + [
        Path.home() / "Downloads" / "Github Tokens.md",
        Path.home() / "Documents" / "Obsidian notes" / "Github Tokens.md",
    ]
    path = next((item for item in candidates if item.is_file()), None)
    if path is None:
        raise ReleaseGateError("GitHub credential file is absent")
    return token_from_file(path, service="github")


def _create_github_tree_commit(client: GitHubClient, config: dict, values: dict[str, bytes]) -> tuple[str, dict[str, str]]:
    gh = config["destinations"]["github"]
    head, prior_tree_sha = _github_head(client, gh["default_branch"])
    desired = {path: _git_blob_sha(raw) for path, raw in values.items()}
    if head != gh["prior_release_commit"]:
        commit = client.json("GET", f"git/commits/{head}")
        parents = commit.get("parents") or []
        tree_sha = commit.get("tree", {}).get("sha")
        if len(parents) != 1 or parents[0].get("sha") != gh["prior_release_commit"] or not _is_sha1(tree_sha):
            raise ReleaseGateError("GitHub main no longer has pinned B022 parent")
        observed = _github_tree(client, tree_sha)
        if set(observed) != set(desired) or any(observed[path].get("sha") != digest for path, digest in desired.items()):
            raise ReleaseGateError("GitHub interrupted commit tree differs from desired B023 tree")
        return head, desired
    prior_blobs = _github_tree(client, prior_tree_sha)
    known = {row.get("sha") for row in prior_blobs.values() if _is_sha1(row.get("sha"))}
    created = {digest for digest in set(desired.values()) if digest in known}
    for path, raw in values.items():
        digest = desired[path]
        if digest in created:
            continue
        result = client.json("POST", "git/blobs", expected=(201,), payload={"content": base64.b64encode(raw).decode("ascii"), "encoding": "base64"})
        if result.get("sha") != digest:
            raise ReleaseGateError(f"GitHub blob identity mismatch: {path}")
        created.add(digest)
    tree_sha = _github_create_hierarchical_tree(client, desired)
    current, _ = _github_head(client, gh["default_branch"])
    if current != head:
        raise ReleaseGateError("GitHub main advanced during B023 tree construction")
    commit = client.json(
        "POST",
        "git/commits",
        expected=(201,),
        payload={
            "message": "Preserve Indonesian R011-B023 reader through Section 6.2",
            "tree": tree_sha,
            "parents": [head],
            "author": {"name": "Codex, atas permintaan pengguna", "email": "codex@users.noreply.github.com"},
            "committer": {"name": "Codex, atas permintaan pengguna", "email": "codex@users.noreply.github.com"},
        },
    )
    commit_sha = commit.get("sha")
    if not _is_sha1(commit_sha):
        raise ReleaseGateError("GitHub commit creation returned no SHA")
    client.json("PATCH", f"git/refs/heads/{quote(gh['default_branch'], safe='')}", payload={"sha": commit_sha, "force": False})
    return commit_sha, desired


def publish_github(config: dict) -> dict:
    if not ZENODO_RECEIPT_PATH.is_file():
        raise ReleaseGateError("verified B023 Zenodo publication receipt is absent")
    zenodo = load_json(ZENODO_RECEIPT_PATH)
    if (
        zenodo.get("boundary_id") != BOUNDARY_ID
        or zenodo.get("release_id") != RELEASE_ID
        or zenodo.get("status") not in PUBLICATION_STATUSES
        or zenodo.get("anonymous_public_byte_readback") is not True
        or zenodo.get("access_right") != "open"
    ):
        raise ReleaseGateError("Zenodo receipt does not authorize GitHub publication")
    gh = config["destinations"]["github"]
    values = _github_values(config, zenodo)
    desired = {path: _git_blob_sha(raw) for path, raw in values.items()}
    expected = _expected_assets(config)
    contract = _github_release_contract(config, zenodo)

    public = GitHubClient(None, gh["owner"], gh["repository"])
    repository = public.json("GET", "")
    if repository.get("full_name") != f"{gh['owner']}/{gh['repository']}" or repository.get("default_branch") != gh["default_branch"] or repository.get("private") is not False:
        raise ReleaseGateError("GitHub public repository identity/visibility changed")
    tag_endpoint = f"git/ref/tags/{quote(gh['tag'], safe='')}"
    release_endpoint = f"releases/tags/{quote(gh['tag'], safe='')}"
    tag = public.maybe_json(tag_endpoint)
    release = public.maybe_json(release_endpoint)
    if (tag is None) != (release is None):
        raise ReleaseGateError("GitHub tag/release collision is partial")
    if tag is not None:
        commit_sha = tag.get("object", {}).get("sha")
        if not _is_sha1(commit_sha):
            raise ReleaseGateError("GitHub existing B023 tag is malformed")
        result = _github_readback(config, release, commit_sha, desired, expected, contract)
        status = "ALREADY_PUBLISHED_AND_ANONYMOUSLY_REVERIFIED"
    else:
        client = GitHubClient(_github_token(), gh["owner"], gh["repository"])
        authenticated_repo = client.json("GET", "")
        if authenticated_repo.get("full_name") != f"{gh['owner']}/{gh['repository']}" or authenticated_repo.get("private") is not False:
            raise ReleaseGateError("GitHub authenticated repository identity/visibility changed")
        commit_sha, observed_desired = _create_github_tree_commit(client, config, values)
        if observed_desired != desired:
            raise ReleaseGateError("GitHub desired tree changed during transaction")
        client.json("POST", "git/refs", expected=(201,), payload={"ref": f"refs/tags/{gh['tag']}", "sha": commit_sha})
        create_contract = dict(contract)
        create_contract["target_commitish"] = commit_sha
        release = client.json("POST", "releases", expected=(201,), payload=create_contract)
        _validate_github_release_metadata(release, contract)
        assets = release.get("assets") or []
        by_name = {row.get("name"): row for row in assets if isinstance(row, dict) and isinstance(row.get("name"), str)}
        for path, wanted in zip(release_assets(config), expected):
            remote = by_name.get(path.name)
            if remote is not None:
                if int(remote.get("size", -1)) != wanted["bytes"]:
                    raise ReleaseGateError(f"GitHub existing asset size collision: {path.name}")
                continue
            with path.open("rb") as source:
                client.request("POST", f"releases/{release['id']}/assets?name={quote(path.name, safe='')}", expected=(201,), data=source, headers={"Content-Type": "application/octet-stream"}, upload=True)
        release = client.json("GET", release_endpoint)
        result = _github_readback(config, release, commit_sha, desired, expected, contract)
        status = "PUBLISHED_AND_ANONYMOUSLY_VERIFIED"
    commit = public.json("GET", f"git/commits/{commit_sha}")
    parents = commit.get("parents") or []
    if len(parents) != 1 or parents[0].get("sha") != gh["prior_release_commit"]:
        raise ReleaseGateError("GitHub B023 release commit parent changed")
    receipt = {
        "$schema": "r011-b023-github-publication-receipt/v1",
        "boundary_id": BOUNDARY_ID,
        "release_id": RELEASE_ID,
        "status": status,
        "repository": f"{gh['owner']}/{gh['repository']}",
        "repository_public": True,
        "tag": gh["tag"],
        "release_id_numeric": int(release["id"]),
        "release_url": release.get("html_url"),
        "parent_commit": gh["prior_release_commit"],
        "release_commit": commit_sha,
        "tree_path_count": result["tree_path_count"],
        "ordered_assets": result["assets"],
        "zenodo_public_url": zenodo["public_url"],
        "learner_reader_pages": 241,
        "through": config["coverage"]["through"],
        "untranslated_instructional_or_exercise_prose_pages": 0,
        "source_closure_counted_as_learner_output": False,
        "production_model": MODEL,
        "collision_preflight_before_mutation": True,
        "anonymous_exact_tree_readback": True,
        "anonymous_public_byte_readback": True,
        "credentials_recorded": False,
        "local_git_used": False,
        "upstream_contact": False,
    }
    atomic_write(GITHUB_RECEIPT_PATH, canonical_json_bytes(receipt))
    return receipt


def main(destination: str) -> int:
    parser = argparse.ArgumentParser(description=f"Bounded R011-B023 {destination} publisher")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--self-check", action="store_true")
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        print(json.dumps(static_self_check(f"b023-{destination}-publisher"), ensure_ascii=False, sort_keys=True))
        return 0
    if args.dry_run:
        result = static_self_check(f"b023-{destination}-publisher-dry-run")
        result.update(
            {
                "status": "PASS_DRY_RUN_NO_MUTATION",
                "destination": destination,
                "existing_zenodo_concept_doi": "10.5281/zenodo.22059801",
                "github_repository": "KokunoYumeto/statistika-berbasis-data-id",
                "planned_tag": "r011-b023-2026.08.29.2",
                "would_require_verified_package": True,
                "would_require_anonymous_collision_preflight": True,
                "would_require_anonymous_every_file_sha256_readback": True,
                "network_used": False,
                "credentials_read": False,
                "publication_performed": False,
                "local_git_used": False,
            }
        )
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    config = load_config(package_required=True)
    verify_release_package(config)
    result = publish_zenodo(config) if destination == "zenodo" else publish_github(config)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", choices=("zenodo", "github"))
    direct = parser.add_mutually_exclusive_group(required=True)
    direct.add_argument("--self-check", action="store_true")
    direct.add_argument("--dry-run", action="store_true")
    direct.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    selected = "--self-check" if args.self_check else "--dry-run" if args.dry_run else "--publish"
    sys.argv = [sys.argv[0], selected]
    try:
        raise SystemExit(main(args.destination))
    except (ReleaseGateError, TransportGateError) as exc:
        raise SystemExit(f"REFUSED: {exc}")
