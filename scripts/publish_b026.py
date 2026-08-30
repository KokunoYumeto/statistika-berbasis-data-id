#!/usr/bin/env python3
"""Bounded REST publication of the verified R011-B026 package.

Self-check and probe modes are strictly offline.  Only explicit ``--publish``
reads the credential for the selected destination.  Publication stays in the
existing Zenodo concept and GitHub repository, preflights exact-version/tag
collisions, and anonymously reads every released byte back.  The module has no
local-Git or upstream-contact operation.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import quote

import requests

import b026_pipeline_contract as pipeline
from b026_release_contract import (
    BOUNDARY_ID,
    CONFIG_PATH,
    GITHUB_RECEIPT_PATH,
    GITHUB_TAG,
    MODEL,
    PRIOR_GITHUB_RECEIPT,
    PRIOR_ZENODO_RECEIPT,
    PROMOTION_RECEIPT_PATH,
    RELEASE_DIR,
    RELEASE_ID,
    ROOT,
    StageGateError,
    VERSION,
    ZENODO_RECEIPT_PATH,
    canonical,
    identity,
    offline_release_self_check,
    repo_path,
)
from package_b026 import (
    ASSETS,
    SOURCE_TOOLING,
    _source_snapshot_rows,
    config,
    metadata,
    verify_package,
)
from publish_b018 import (
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


ZENODO_CONCEPT_RECORD_ID = 22_059_801
ZENODO_CONCEPT_DOI = "10.5281/zenodo.22059801"
GITHUB_OWNER = "KokunoYumeto"
GITHUB_REPOSITORY = "statistika-berbasis-data-id"
ZENODO_RECEIPT = repo_path(ZENODO_RECEIPT_PATH)
GITHUB_RECEIPT = repo_path(GITHUB_RECEIPT_PATH)
STATUSES = {
    "PUBLISHED_AND_ANONYMOUSLY_VERIFIED",
    "ALREADY_PUBLISHED_AND_ANONYMOUSLY_REVERIFIED",
}
GITHUB_TOOLING = (
    *SOURCE_TOOLING,
    "scripts/publish_b026.py",
    "scripts/publish_github_b026.py",
    "scripts/publish_zenodo_b026.py",
    "scripts/finalize_publication_b026.py",
)


def md5(path: Path) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def expected_assets() -> list[dict[str, Any]]:
    verify_package()
    rows = []
    for name in ASSETS:
        path = RELEASE_DIR / name
        row = identity(path)
        rows.append(
            {
                "filename": name,
                "bytes": row["bytes"],
                "sha256": row["sha256"],
                "md5": md5(path),
            }
        )
    return rows


def _public_stream(url: str, hosts: set[str]) -> tuple[int, str]:
    session = requests.Session()
    session.trust_env = False
    session.headers["User-Agent"] = "interlanguage-r011-b026-public-readback/1"
    response = _fixed_redirect_get(session, url, hosts=hosts, stream=True)
    if response.status_code != 200:
        raise StageGateError(
            f"anonymous public download returned HTTP {response.status_code}"
        )
    return _stream_sha(response)


def validate_metadata(value: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    actual = value.get("metadata") if isinstance(value.get("metadata"), dict) else value
    expected = metadata(cfg)["metadata"]
    if isinstance(actual.get("license"), dict):
        actual = dict(actual)
        actual["license"] = actual["license"].get("id")
    description = str(actual.get("description", ""))
    notes = str(actual.get("notes", ""))
    checks = {
        "title": actual.get("title") == expected["title"],
        "version": actual.get("version") == VERSION,
        "date": actual.get("publication_date") == cfg["release_date"],
        "license": actual.get("license") == "cc-by-sa-3.0",
        "language": actual.get("language") == "ind",
        "access": actual.get("access_right", "open") == "open",
        "model": MODEL in description and MODEL in notes,
        "partial": "parsial" in description.casefold(),
        "scope": "Bagian 7.1" in description,
        "chapter_exercises": "1-14" in description,
        "no_restricted": (
            "tidak ada solusi instruktur terbatas" in description.casefold()
        ),
        "component_rights": "Mike Baird" in description and "CC BY 2.0" in notes,
    }
    failed = [key for key, passed in checks.items() if not passed]
    if failed:
        raise StageGateError(f"Zenodo metadata mismatch: {failed}")
    return actual


def zenodo_readback(
    record_id: int, expected: list[dict[str, Any]], cfg: dict[str, Any]
) -> dict[str, Any]:
    record = _zenodo_public_json(f"{ZENODO_API}/records/{record_id}")
    if (
        int(record.get("conceptrecid", -1)) != ZENODO_CONCEPT_RECORD_ID
        or record.get("doi") != f"10.5281/zenodo.{record_id}"
    ):
        raise StageGateError("Zenodo record escaped the existing concept")
    validate_metadata(record, cfg)
    files = record.get("files") or []
    by_name = {row.get("key"): row for row in files}
    if set(by_name) != {row["filename"] for row in expected}:
        raise StageGateError("Zenodo public inventory mismatch")
    verified = []
    for wanted in expected:
        remote = by_name[wanted["filename"]]
        link = remote.get("links", {}).get("self") or remote.get("links", {}).get(
            "content"
        )
        response = _zenodo_public_request(link, preload_content=False)
        if response.status != 200:
            response.release_conn()
            raise StageGateError(
                f"Zenodo anonymous download failed: {wanted['filename']}"
            )
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
            raise StageGateError(f"Zenodo byte mismatch: {wanted['filename']}")
        verified.append(
            {
                "filename": wanted["filename"],
                "bytes": count,
                "sha256": digest.hexdigest(),
            }
        )
    return {"record": record, "files": verified}


def token(service: str) -> str:
    environment_file = os.environ.get(
        f"INTERLANGUAGE_{service.upper()}_TOKEN_FILE"
    )
    candidates = [Path(environment_file)] if environment_file else []
    if service == "zenodo":
        candidates.extend(
            [
                Path.home() / "Documents/Obsidian notes/New zenodo token.md",
                Path.home() / "Downloads/Zenodo token.md",
            ]
        )
    else:
        candidates.extend(
            [
                Path.home() / "Downloads/Github Tokens.md",
                Path.home() / "Documents/Obsidian notes/Github Tokens.md",
            ]
        )
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        raise StageGateError(f"{service} credential file is absent")
    return token_from_file(path, service=service)


def write_receipt(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = canonical(payload)
    temporary = path.with_name(path.name + ".b026.tmp")
    if temporary.exists():
        raise StageGateError(f"stale publication-receipt temporary: {temporary}")
    if path.exists() and path.read_bytes() != raw:
        try:
            previous = json.loads(path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise StageGateError(f"existing publication receipt is invalid: {path}") from exc
        previous_normalized = dict(previous)
        current_normalized = dict(payload)
        previous_status = previous_normalized.pop("status", None)
        current_status = current_normalized.pop("status", None)
        if (
            previous_status in STATUSES
            and current_status in STATUSES
            and previous_normalized == current_normalized
        ):
            # A second full anonymous verification changes only the transient
            # wording from "published" to "already published".  Preserve the
            # original immutable receipt after the re-verification succeeds.
            return previous
        raise StageGateError(f"refusing to replace a different receipt: {path}")
    temporary.write_bytes(raw)
    os.replace(temporary, path)
    return payload


def publish_zenodo() -> dict[str, Any]:
    cfg = config()
    expected = expected_assets()
    versions = _zenodo_public_versions(ZENODO_CONCEPT_RECORD_ID)
    matches = [
        row for row in versions if row.get("metadata", {}).get("version") == VERSION
    ]
    if len(matches) > 1:
        raise StageGateError("multiple public Zenodo B026 versions exist")
    if matches:
        record_id = int(matches[0]["id"])
        back = zenodo_readback(record_id, expected, cfg)
        status = "ALREADY_PUBLISHED_AND_ANONYMOUSLY_REVERIFIED"
    else:
        if (
            not versions
            or int(versions[0].get("id", -1))
            != PRIOR_ZENODO_RECEIPT["record_id"]
        ):
            raise StageGateError("Zenodo public head is not the pinned B025 version")
        client = ZenodoClient(token("zenodo"))
        prior_id = PRIOR_ZENODO_RECEIPT["record_id"]
        prior = client.json(
            "GET", f"{ZENODO_API}/deposit/depositions/{prior_id}"
        )
        if (
            int(prior.get("conceptrecid", -1)) != ZENODO_CONCEPT_RECORD_ID
            or prior.get("state") != "done"
        ):
            raise StageGateError("authenticated Zenodo predecessor changed")
        latest_draft = prior.get("links", {}).get("latest_draft")
        draft = None
        if isinstance(latest_draft, str):
            candidate = client.json("GET", latest_draft)
            if (
                int(candidate.get("id", prior_id)) != prior_id
                and candidate.get("submitted") is not True
            ):
                draft_version = candidate.get("metadata", {}).get("version")
                if draft_version not in (None, "", VERSION):
                    raise StageGateError(
                        "existing Zenodo draft belongs to a different version"
                    )
                draft = candidate
        if draft is None:
            created = client.json(
                "POST",
                f"{ZENODO_API}/deposit/depositions/{prior_id}/actions/newversion",
                expected=(201, 202),
            )
            latest_draft = created.get("links", {}).get("latest_draft")
            if not isinstance(latest_draft, str):
                raise StageGateError("Zenodo new version lacks a draft link")
            draft = client.json("GET", latest_draft)
        draft_id = int(draft.get("id", -1))
        bucket = draft.get("links", {}).get("bucket")
        if (
            int(draft.get("conceptrecid", -1)) != ZENODO_CONCEPT_RECORD_ID
            or not isinstance(bucket, str)
            or not bucket.startswith("https://zenodo.org/api/files/")
        ):
            raise StageGateError("Zenodo draft identity is malformed")
        current = {row.get("filename"): row for row in draft.get("files") or []}
        wanted_by_name = {row["filename"]: row for row in expected}
        for name, row in list(current.items()):
            wanted = wanted_by_name.get(name)
            checksum = str(row.get("checksum", "")).removeprefix("md5:")
            size = int(row.get("filesize", row.get("size", -1)))
            if wanted and (checksum, size) == (wanted["md5"], wanted["bytes"]):
                continue
            client.request(
                "DELETE",
                f"{ZENODO_API}/deposit/depositions/{draft_id}/files/{row['id']}",
                expected=(204,),
            )
            current.pop(name, None)
        for name in ASSETS:
            if name in current:
                continue
            with (RELEASE_DIR / name).open("rb") as source:
                client.request(
                    "PUT",
                    bucket.rstrip("/") + "/" + quote(name, safe=""),
                    expected=(200, 201),
                    data=source,
                    headers={"Content-Type": "application/octet-stream"},
                )
        exact_metadata = metadata(cfg)
        validate_metadata(exact_metadata, cfg)
        client.json(
            "PUT",
            f"{ZENODO_API}/deposit/depositions/{draft_id}",
            data=canonical(exact_metadata),
            headers={"Content-Type": "application/json"},
        )
        draft = client.json(
            "GET", f"{ZENODO_API}/deposit/depositions/{draft_id}"
        )
        validate_metadata(draft, cfg)
        remote = {row.get("filename"): row for row in draft.get("files") or []}
        if set(remote) != {row["filename"] for row in expected}:
            raise StageGateError("Zenodo draft inventory differs before publish")
        for wanted in expected:
            row = remote[wanted["filename"]]
            checksum = str(row.get("checksum", "")).removeprefix("md5:")
            size = int(row.get("filesize", row.get("size", -1)))
            if (checksum, size) != (wanted["md5"], wanted["bytes"]):
                raise StageGateError(
                    f"Zenodo draft identity mismatch: {wanted['filename']}"
                )
        if any(
            row.get("metadata", {}).get("version") == VERSION
            for row in _zenodo_public_versions(ZENODO_CONCEPT_RECORD_ID)
        ):
            raise StageGateError("Zenodo B026 appeared concurrently")
        published = client.json(
            "POST",
            f"{ZENODO_API}/deposit/depositions/{draft_id}/actions/publish",
            expected=(201, 202),
        )
        record_id = int(published.get("record_id", published.get("id", -1)))
        back = zenodo_readback(record_id, expected, cfg)
        status = "PUBLISHED_AND_ANONYMOUSLY_VERIFIED"
    coverage = cfg["coverage"]
    receipt = {
        "$schema": "r011-b026-zenodo-publication-receipt/v1",
        "boundary_id": BOUNDARY_ID,
        "release_id": RELEASE_ID,
        "status": status,
        "concept_doi": ZENODO_CONCEPT_DOI,
        "concept_record_id": ZENODO_CONCEPT_RECORD_ID,
        "record_id": record_id,
        "doi": f"10.5281/zenodo.{record_id}",
        "public_url": f"https://zenodo.org/records/{record_id}",
        "version": VERSION,
        "access_right": "open",
        "license_id": "cc-by-sa-3.0",
        "component_rights": {"rissos_dolphin_photo": "Mike Baird, CC BY 2.0"},
        "production_model": MODEL,
        "learner_reader_pages": coverage["learner_reader_pages"],
        "through": coverage["through"],
        "current_chapter_exercise_ids": list(range(1, 15)),
        "current_chapter_public_answer_ids": list(range(1, 14, 2)),
        "current_chapter_o001_gap_ids": list(range(2, 15, 2)),
        "untranslated_instructional_or_exercise_prose_pages": 0,
        "source_closure_counted_as_learner_output": False,
        "ordered_files": back["files"],
        "metadata_exactly_verified": True,
        "collision_preflight_before_mutation": True,
        "anonymous_public_byte_readback": True,
        "credentials_recorded": False,
        "local_git_used": False,
        "upstream_contact": False,
    }
    return write_receipt(ZENODO_RECEIPT, receipt)


def source_tree_values(
    cfg: dict[str, Any], zenodo: dict[str, Any]
) -> dict[str, bytes]:
    values: dict[str, bytes] = {}

    def add(path: str, raw: bytes) -> None:
        pure = PurePosixPath(path)
        if pure.is_absolute() or ".." in pure.parts:
            raise StageGateError(f"unsafe GitHub path: {path}")
        if path in values and values[path] != raw:
            raise StageGateError(f"GitHub tree collision: {path}")
        values[path] = raw

    binding = pipeline.load_bindings(require_complete=True)
    assert binding is not None
    manifest_row = binding["post_build_outputs"]["source_manifest"]
    manifest_path = repo_path(manifest_row["path"])
    if identity(manifest_path) != {
        key: manifest_row[key] for key in ("path", "bytes", "sha256")
    }:
        raise StageGateError("source manifest changed before GitHub publication")
    snapshot_rows, _ = _source_snapshot_rows(manifest_path)
    for archive_name, source in snapshot_rows:
        rel = archive_name.removeprefix("source-snapshot/")
        add("source/full-source-closure/" + rel, source.read_bytes())
    for path in GITHUB_TOOLING:
        add(path, repo_path(path).read_bytes())
    for role, row in binding["sealed_text_inputs"].items():
        if role != "base_backend":
            add(row["path"], repo_path(row["path"]).read_bytes())
    for role, row in binding["post_build_outputs"].items():
        if role != "candidate_pdf":
            add(row["path"], repo_path(row["path"]).read_bytes())
    asset = binding["asset_closure"]
    add(asset["receipt"]["path"], repo_path(asset["receipt"]["path"]).read_bytes())
    backend = json.loads(
        repo_path("backend/exports/manifest.json").read_text(encoding="utf-8")
    )
    if backend.get("boundary_id") != BOUNDARY_ID:
        raise StageGateError("GitHub backend is not admitted B026")
    projection = []
    for row in backend.get("files", []):
        if row["path"].startswith(("core/", "locales/", "schemas/", "views/")):
            path = repo_path("backend/exports/" + row["path"])
            observed = identity(path)
            if (observed["bytes"], observed["sha256"]) != (
                row["bytes"], row["sha256"],
            ):
                raise StageGateError(f"backend export changed: {row['path']}")
            add("backend/exports/" + row["path"], path.read_bytes())
            projection.append({key: row[key] for key in ("path", "bytes", "sha256")})
    add(
        "backend/exports/manifest.json",
        canonical(
            {
                "$schema": "r011-b026-github-public-backend-projection/v1",
                "boundary_id": BOUNDARY_ID,
                "release_id": RELEASE_ID,
                "reader": cfg["inputs"]["reader"],
                "scope": cfg["coverage"],
                "record_count": backend.get("record_count"),
                "files": projection,
                "source_closure_counted_as_learner_output": False,
            }
        ),
    )
    add(
        cfg["inputs"]["reader"]["path"],
        repo_path(cfg["inputs"]["reader"]["path"]).read_bytes(),
    )
    for path in (
        pipeline.BINDINGS_REL,
        PROMOTION_RECEIPT_PATH,
        pipeline.BACKEND_ADMISSION_RECEIPT_PATH,
        pipeline.BACKEND_REPLAY_RECEIPT_PATH,
    ):
        add(path, repo_path(path).read_bytes())
    for name in ("RELEASE_INPUTS.json", *ASSETS[3:]):
        source = RELEASE_DIR / name
        add(source.relative_to(ROOT).as_posix(), source.read_bytes())
    readme = (RELEASE_DIR / "README_RELEASE.md").read_text(encoding="utf-8")
    readme += f"\n## Repositori publik\n\n- Zenodo: <{zenodo['public_url']}>\n"
    add("README.md", readme.encode("utf-8"))
    add("LICENSE.md", (RELEASE_DIR / "LICENSES_AND_ATTRIBUTION.md").read_bytes())
    add("CITATION.cff", (RELEASE_DIR / "CITATION.cff").read_bytes())
    pages = cfg["coverage"]["learner_reader_pages"]
    add(
        "00_control/PUBLICATION_STATE_R011-B026.md",
        (
            "# Status publikasi R011-B026\n\n"
            f"Edisi kerja parsial hingga Bab 7 Bagian 7.1; {pages} halaman; "
            "latihan Bab 7 nomor 1-14; jawaban publik ganjil 1-13; kesenjangan "
            "O001 genap 2-14; nol halaman prosa pembelajar Inggris; korpus "
            f"lengkap: tidak.\n\nZenodo: {zenodo['public_url']}\n\n"
            f"Model: {MODEL}. Tidak ada kontak hulu.\n"
        ).encode("utf-8"),
    )
    total = sum(len(raw) for raw in values.values())
    if total > 100_000_000:
        raise StageGateError(
            f"GitHub exact tree exceeds bounded 100,000,000-byte limit: {total}"
        )
    return values


def release_contract(
    cfg: dict[str, Any], zenodo: dict[str, Any]
) -> dict[str, Any]:
    pages = cfg["coverage"]["learner_reader_pages"]
    return {
        "tag_name": GITHUB_TAG,
        "name": "R011-B026 - pembaca Bahasa Indonesia hingga Bagian 7.1",
        "body": (
            f"Rilis kerja parsial: pembaca bersih {pages} halaman hingga Bab 7 "
            "Bagian 7.1; latihan Bab 7 nomor 1-14; jawaban publik ganjil 1-13; "
            "kesenjangan O001 genap 2-14; nol halaman prosa pembelajar Inggris. "
            f"Korpus lengkap: tidak. Zenodo: {zenodo['public_url']}\n\n"
            "Foto lumba-lumba Risso: Mike Baird, CC BY 2.0. "
            f"Model: {MODEL}. Tidak ada kontak hulu."
        ),
        "draft": False,
        "prerelease": True,
    }


def github_readback(
    release: dict[str, Any],
    commit_sha: str,
    desired: dict[str, str],
    expected: list[dict[str, Any]],
    contract: dict[str, Any],
) -> dict[str, Any]:
    public = GitHubClient(None, GITHUB_OWNER, GITHUB_REPOSITORY)
    actual = public.json(
        "GET", f"releases/tags/{quote(GITHUB_TAG, safe='')}"
    )
    for key in ("tag_name", "name", "body", "draft", "prerelease"):
        if actual.get(key) != contract[key]:
            raise StageGateError(f"GitHub release metadata mismatch: {key}")
    tree_sha = public.json("GET", f"git/commits/{commit_sha}").get(
        "tree", {}
    ).get("sha")
    tree = _github_tree(public, tree_sha)
    if set(tree) != set(desired) or any(
        tree[path].get("sha") != digest for path, digest in desired.items()
    ):
        raise StageGateError("GitHub anonymous exact-tree readback mismatch")
    assets = {row.get("name"): row for row in actual.get("assets") or []}
    if set(assets) != {row["filename"] for row in expected}:
        raise StageGateError("GitHub release-asset inventory mismatch")
    verified = []
    for wanted in expected:
        row = assets[wanted["filename"]]
        count, digest = _public_stream(
            row["browser_download_url"],
            {
                "github.com",
                "objects.githubusercontent.com",
                "release-assets.githubusercontent.com",
            },
        )
        if (count, digest) != (wanted["bytes"], wanted["sha256"]):
            raise StageGateError(f"GitHub byte mismatch: {wanted['filename']}")
        verified.append(
            {"filename": wanted["filename"], "bytes": count, "sha256": digest}
        )
    return {"assets": verified, "tree_path_count": len(tree), "release": actual}


def publish_github() -> dict[str, Any]:
    cfg = config()
    expected = expected_assets()
    if not ZENODO_RECEIPT.is_file():
        raise StageGateError("verified B026 Zenodo receipt is absent")
    zenodo = json.loads(ZENODO_RECEIPT.read_text(encoding="utf-8"))
    if (
        zenodo.get("status") not in STATUSES
        or zenodo.get("access_right") != "open"
        or zenodo.get("anonymous_public_byte_readback") is not True
    ):
        raise StageGateError("Zenodo receipt is not publication-authorizing")
    values = source_tree_values(cfg, zenodo)
    desired = {path: _git_blob_sha(raw) for path, raw in values.items()}
    contract = release_contract(cfg, zenodo)
    public = GitHubClient(None, GITHUB_OWNER, GITHUB_REPOSITORY)
    tag = public.maybe_json(f"git/ref/tags/{quote(GITHUB_TAG, safe='')}")
    release = public.maybe_json(f"releases/tags/{quote(GITHUB_TAG, safe='')}")
    if tag is None and release is not None:
        raise StageGateError("GitHub release exists without its exact B026 tag")
    if tag is not None:
        commit_sha = tag.get("object", {}).get("sha")
        if not _is_sha1(commit_sha):
            raise StageGateError("existing GitHub tag does not resolve to a commit SHA")
        if release is not None:
            back = github_readback(release, commit_sha, desired, expected, contract)
            status = "ALREADY_PUBLISHED_AND_ANONYMOUSLY_REVERIFIED"
        else:
            # Recover only the exact interruption point after the immutable tag
            # was created but before the release transaction completed.
            tagged_commit = public.json("GET", f"git/commits/{commit_sha}")
            parents = tagged_commit.get("parents") or []
            tree_sha = tagged_commit.get("tree", {}).get("sha")
            observed = _github_tree(public, tree_sha)
            if (
                len(parents) != 1
                or parents[0].get("sha") != PRIOR_GITHUB_RECEIPT["commit"]
                or set(observed) != set(desired)
                or any(
                    observed[path].get("sha") != digest
                    for path, digest in desired.items()
                )
            ):
                raise StageGateError("partial GitHub tag is not the exact B026 tree")
            client = GitHubClient(
                token("github"), GITHUB_OWNER, GITHUB_REPOSITORY
            )
            create = dict(contract)
            create["target_commitish"] = commit_sha
            release = client.json(
                "POST", "releases", expected=(201,), payload=create
            )
            for wanted in expected:
                with (RELEASE_DIR / wanted["filename"]).open("rb") as source:
                    client.request(
                        "POST",
                        f"releases/{release['id']}/assets?name="
                        + quote(wanted["filename"], safe=""),
                        expected=(201,),
                        data=source,
                        headers={"Content-Type": "application/octet-stream"},
                        upload=True,
                    )
            back = github_readback(
                release, commit_sha, desired, expected, contract
            )
            status = "PUBLISHED_AND_ANONYMOUSLY_VERIFIED"
    else:
        client = GitHubClient(
            token("github"), GITHUB_OWNER, GITHUB_REPOSITORY
        )
        head, prior_tree = _github_head(client, "main")
        if head != PRIOR_GITHUB_RECEIPT["commit"]:
            interrupted = client.json("GET", f"git/commits/{head}")
            parents = interrupted.get("parents") or []
            tree_sha = interrupted.get("tree", {}).get("sha")
            observed = _github_tree(client, tree_sha)
            if (
                len(parents) != 1
                or parents[0].get("sha") != PRIOR_GITHUB_RECEIPT["commit"]
                or set(observed) != set(desired)
                or any(
                    observed[path].get("sha") != digest
                    for path, digest in desired.items()
                )
            ):
                raise StageGateError(
                    "GitHub main is neither pinned B025 nor exact interrupted B026"
                )
            commit_sha = head
        else:
            known = {row.get("sha") for row in _github_tree(client, prior_tree).values()}
            created: set[str] = set()
            for path, raw in values.items():
                digest = desired[path]
                if digest in known or digest in created:
                    continue
                result = client.json(
                    "POST",
                    "git/blobs",
                    expected=(201,),
                    payload={
                        "content": base64.b64encode(raw).decode("ascii"),
                        "encoding": "base64",
                    },
                )
                if result.get("sha") != digest:
                    raise StageGateError(f"GitHub blob mismatch: {path}")
                created.add(digest)
            tree_sha = _github_create_hierarchical_tree(client, desired)
            commit = client.json(
                "POST",
                "git/commits",
                expected=(201,),
                payload={
                    "message": (
                        "Preserve Indonesian R011-B026 reader through Section 7.1"
                    ),
                    "tree": tree_sha,
                    "parents": [head],
                    "author": {
                        "name": "Codex, atas permintaan pengguna",
                        "email": "codex@users.noreply.github.com",
                    },
                    "committer": {
                        "name": "Codex, atas permintaan pengguna",
                        "email": "codex@users.noreply.github.com",
                    },
                },
            )
            commit_sha = commit.get("sha")
            if not _is_sha1(commit_sha):
                raise StageGateError("GitHub commit lacks a valid SHA")
            client.json(
                "PATCH",
                "git/refs/heads/main",
                payload={"sha": commit_sha, "force": False},
            )
        client.json(
            "POST",
            "git/refs",
            expected=(201,),
            payload={"ref": f"refs/tags/{GITHUB_TAG}", "sha": commit_sha},
        )
        create = dict(contract)
        create["target_commitish"] = commit_sha
        release = client.json(
            "POST", "releases", expected=(201,), payload=create
        )
        for wanted in expected:
            with (RELEASE_DIR / wanted["filename"]).open("rb") as source:
                client.request(
                    "POST",
                    f"releases/{release['id']}/assets?name="
                    + quote(wanted["filename"], safe=""),
                    expected=(201,),
                    data=source,
                    headers={"Content-Type": "application/octet-stream"},
                    upload=True,
                )
        back = github_readback(release, commit_sha, desired, expected, contract)
        status = "PUBLISHED_AND_ANONYMOUSLY_VERIFIED"
    commit = public.json("GET", f"git/commits/{commit_sha}")
    parents = commit.get("parents") or []
    if len(parents) != 1 or parents[0].get("sha") != PRIOR_GITHUB_RECEIPT["commit"]:
        raise StageGateError("GitHub B026 commit parent changed")
    receipt = {
        "$schema": "r011-b026-github-publication-receipt/v1",
        "boundary_id": BOUNDARY_ID,
        "release_id": RELEASE_ID,
        "status": status,
        "repository": f"{GITHUB_OWNER}/{GITHUB_REPOSITORY}",
        "repository_public": True,
        "tag": GITHUB_TAG,
        "release_id_numeric": int(back["release"]["id"]),
        "release_url": back["release"].get("html_url"),
        "parent_commit": PRIOR_GITHUB_RECEIPT["commit"],
        "release_commit": commit_sha,
        "tree_path_count": back["tree_path_count"],
        "ordered_assets": back["assets"],
        "zenodo_public_url": zenodo["public_url"],
        "learner_reader_pages": cfg["coverage"]["learner_reader_pages"],
        "through": cfg["coverage"]["through"],
        "current_chapter_exercise_ids": list(range(1, 15)),
        "current_chapter_public_answer_ids": list(range(1, 14, 2)),
        "current_chapter_o001_gap_ids": list(range(2, 15, 2)),
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
    return write_receipt(GITHUB_RECEIPT, receipt)


def probe(destination: str) -> dict[str, Any]:
    static = offline_release_self_check(f"b026-{destination}-publisher")
    if static["pending"]:
        return static
    if not CONFIG_PATH.is_file():
        return {
            **static,
            "status": "PASS_STATIC_B026_PUBLICATION_FAIL_CLOSED_PREPARATION_PENDING",
            "pending": ["exact B026 RELEASE_INPUTS.json preparation"],
        }
    if not (RELEASE_DIR / "RELEASE_MANIFEST.json").is_file():
        return {
            **static,
            "status": "PASS_STATIC_B026_PUBLICATION_FAIL_CLOSED_PACKAGE_PENDING",
            "pending": ["exact verified B026 reader-first package"],
        }
    cfg = config()
    verify_package()
    return {
        "status": "PASS_B026_PUBLICATION_PROBE_OFFLINE_NO_WRITES",
        "destination": destination,
        "config": identity(CONFIG_PATH),
        "reader": cfg["inputs"]["reader"],
        "assets": expected_assets(),
        "network_used": False,
        "credentials_accessed": False,
        "writes_performed": False,
        "git_used": False,
    }


def main(destination: str | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "destination", nargs="?", choices=("zenodo", "github"), default=destination
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--self-check", action="store_true")
    mode.add_argument("--probe", action="store_true")
    mode.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    if args.destination is None:
        parser.error("destination is required")
    if args.self_check:
        result = offline_release_self_check(
            f"b026-{args.destination}-publisher"
        )
    elif args.probe:
        result = probe(args.destination)
    else:
        result = publish_zenodo() if args.destination == "zenodo" else publish_github()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except StageGateError as exc:
        raise SystemExit(f"REFUSED: {exc}")
