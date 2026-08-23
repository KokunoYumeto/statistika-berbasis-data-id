#!/usr/bin/env python3
"""Publish R011-B008 to the existing GitHub repository and prerelease.

This publisher uses the bounded Git database API rather than a local Git scan.
It uploads only an exact allowlist reconstructed from the admitted source,
backend, receipts, package, and B008 release toolchain.  No upstream issue,
discussion, pull request, or message endpoint is used.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import time
from pathlib import Path, PurePosixPath
from urllib.parse import quote, urlparse

from release_b008_common import (
    BOUNDARY_ID,
    EXCLUDED_SOURCE_PATH,
    MODEL,
    RELEASE_DIR,
    RELEASE_ID,
    REPO_ROOT,
    ReleaseGateError,
    assert_public_text_safe,
    atomic_write,
    canonical_json_bytes,
    emit_self_check,
    execution_preflight,
    identity,
    load_json,
    public_session,
    read_backend_inventory,
    read_snapshot_manifest,
    release_assets,
    repo_path,
    sanitized_receipt_path,
    token_from_file,
)


API_HOST = "api.github.com"
UPLOAD_HOST = "uploads.github.com"


def _git_blob_sha(raw: bytes) -> str:
    return hashlib.sha1(f"blob {len(raw)}\0".encode("ascii") + raw).hexdigest()


def _safe_remote_path(value: str) -> str:
    pure = PurePosixPath(value)
    if pure.is_absolute() or ".." in pure.parts or not pure.parts:
        raise ReleaseGateError(f"unsafe GitHub tree path: {value!r}")
    return pure.as_posix()


class GitHubClient:
    def __init__(self, token: str | None, owner: str, repository: str):
        self.owner = owner
        self.repository = repository
        self.slug = f"{owner}/{repository}"
        self.session = public_session()
        self.session.headers.update({"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"})
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"

    def _url(self, endpoint: str, *, upload: bool = False) -> str:
        endpoint = endpoint.lstrip("/")
        if ".." in endpoint:
            raise ReleaseGateError("GitHub endpoint contains parent traversal")
        base = f"https://{UPLOAD_HOST if upload else API_HOST}/repos/{self.slug}"
        url = base if not endpoint else f"{base}/{endpoint}"
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in {API_HOST, UPLOAD_HOST}:
            raise ReleaseGateError("GitHub endpoint escaped the fixed HTTPS authorities")
        return url

    def request(self, method: str, endpoint: str, *, expected=(200,), payload=None, data=None, headers=None, upload=False):
        response = self.session.request(
            method,
            self._url(endpoint, upload=upload),
            timeout=300,
            allow_redirects=False,
            json=payload,
            data=data,
            headers=headers,
        )
        if response.status_code not in expected:
            raise ReleaseGateError(f"GitHub {method} {endpoint.split('?')[0]} returned HTTP {response.status_code}")
        return response

    def json(self, method: str, endpoint: str, *, expected=(200,), payload=None, data=None, headers=None, upload=False):
        response = self.request(
            method, endpoint, expected=expected, payload=payload, data=data, headers=headers, upload=upload
        )
        if response.status_code == 204:
            return None
        try:
            return response.json()
        except ValueError as exc:
            raise ReleaseGateError("GitHub returned malformed JSON") from exc

    def maybe_json(self, endpoint: str):
        response = self.session.get(self._url(endpoint), timeout=120, allow_redirects=False)
        if response.status_code == 404:
            return None
        if response.status_code != 200:
            raise ReleaseGateError(f"GitHub GET {endpoint} returned HTTP {response.status_code}")
        return response.json()


def _publication_receipt(kind: str, config: dict) -> dict:
    path = sanitized_receipt_path(kind)
    if not path.is_file():
        raise ReleaseGateError(f"GitHub requires the sanitized {kind} publication receipt")
    value = load_json(path)
    accepted_statuses = {
        "PUBLISHED_AND_ANONYMOUSLY_VERIFIED",
        "ALREADY_PUBLISHED_AND_ANONYMOUSLY_REVERIFIED",
    }
    if (
        value.get("status") not in accepted_statuses
        or value.get("boundary_id") != BOUNDARY_ID
        or value.get("release_id") != RELEASE_ID
    ):
        raise ReleaseGateError(f"{kind} receipt does not prove this B008 release")
    assert_public_text_safe(path.read_text(encoding="utf-8"), role=f"{kind} receipt")
    return value


def _generated_root_files(config: dict, zenodo: dict, figshare: dict) -> dict[str, bytes]:
    base_readme = (RELEASE_DIR / "README_RELEASE.md").read_text(encoding="utf-8")
    links = (
        "\n## Repositori publik\n\n"
        f"- Zenodo: <{zenodo['public_url']}>\n"
        f"- Figshare: <{figshare['public_url']}>\n"
        f"- Konsep Zenodo: <https://doi.org/{config['destinations']['zenodo']['concept_doi']}>\n"
    )
    readme = (base_readme + links).encode("utf-8")
    citation = (RELEASE_DIR / "CITATION.cff").read_bytes()
    license_bytes = (RELEASE_DIR / "LICENSES_AND_ATTRIBUTION.md").read_bytes()
    state = (
        "# Status publikasi R011-B008\n\n"
        "Status: edisi kerja Bahasa Indonesia yang belum lengkap, diterima secara tepat, dan dipertahankan sebagai prerelease.\n\n"
        f"Zenodo: {zenodo['public_url']}\n\nFigshare: {figshare['public_url']}\n\n"
        f"Model produksi: {MODEL}.\n\nNo upstream contact was performed.\n"
    ).encode("utf-8")
    cursor = canonical_json_bytes(
        {
            "$schema": "r011-b008-github-publication-cursor/v1",
            "boundary_id": BOUNDARY_ID,
            "release_id": RELEASE_ID,
            "status": "ready_for_bounded_github_transaction",
            "zenodo_public_url": zenodo["public_url"],
            "figshare_public_url": figshare["public_url"],
            "tag": config["destinations"]["github"]["tag"],
            "production_model": MODEL,
            "no_upstream_contact": True,
        }
    )
    values = {
        "README.md": readme,
        "CITATION.cff": citation,
        "LICENSE.md": license_bytes,
        "00_control/PUBLICATION_STATE_R011-B008.md": state,
        "00_control/PUBLICATION_CURSOR_R011-B008.json": cursor,
    }
    for path, raw in values.items():
        assert_public_text_safe(raw.decode("utf-8"), role=path)
    return values


def _tree_allowlist(config: dict, zenodo: dict, figshare: dict) -> dict[str, bytes]:
    values: dict[str, bytes] = {}

    def add(path: str, raw: bytes) -> None:
        safe = _safe_remote_path(path)
        if safe in values and values[safe] != raw:
            raise ReleaseGateError(f"conflicting GitHub tree sources for {safe}")
        values[safe] = raw

    for row in read_snapshot_manifest(config):
        if row["path"] in {EXCLUDED_SOURCE_PATH, "README.md", "LICENSE.md", "CITATION.cff"}:
            continue
        add(row["path"], row["source"].read_bytes())
    for row in read_backend_inventory(config):
        add(row["path"], row["source"].read_bytes())

    fixed_records = []
    for key, record in config["accepted_v3"].items():
        if isinstance(record, dict) and isinstance(record.get("path"), str):
            fixed_records.append(record["path"])
    fixed_records.append(config["accepted_v3"]["source_snapshot"]["manifest_path"])
    for record in config["terminal_inputs"].values():
        if isinstance(record.get("path"), str) and repo_path(record["path"]).is_file():
            fixed_records.append(record["path"])
    for relative in sorted(set(fixed_records)):
        add(relative, repo_path(relative).read_bytes())

    script_names = (
        "release_b008_common.py",
        "package_release_b008.py",
        "publish_zenodo_b008.py",
        "publish_figshare_b008.py",
        "publish_github_b008.py",
        "qa_source_b008_v3.py",
        "qa_build_b008_v3.py",
        "generate_backend_b008_v3.py",
        "finalize_backend_b008_v3.py",
        "validate_backend_b008_v3.py",
        "admit_b008.py",
    )
    for name in script_names:
        path = REPO_ROOT / "scripts" / name
        add(f"scripts/{name}", path.read_bytes())

    for path in sorted(RELEASE_DIR.iterdir(), key=lambda item: item.name):
        if path.is_file() and path.name != "GITHUB_PUBLICATION_RECEIPT.json":
            add(path.relative_to(REPO_ROOT).as_posix(), path.read_bytes())
    canonical_pdf = config["terminal_inputs"]["promoted_pdf"]["path"]
    add(canonical_pdf, repo_path(canonical_pdf).read_bytes())
    for path, raw in _generated_root_files(config, zenodo, figshare).items():
        add(path, raw)

    total = sum(len(raw) for raw in values.values())
    if total > 500_000_000:
        raise ReleaseGateError("bounded GitHub current-tree allowlist exceeds 500MB")
    for path, raw in values.items():
        if len(raw) > 100_000_000:
            raise ReleaseGateError(f"GitHub tree blob exceeds 100MB: {path}")
    return values


def _remote_head(client: GitHubClient, branch: str) -> tuple[str, str]:
    ref = client.json("GET", f"git/ref/heads/{quote(branch, safe='')}")
    commit_sha = ref.get("object", {}).get("sha")
    if not isinstance(commit_sha, str) or len(commit_sha) != 40:
        raise ReleaseGateError("GitHub default branch ref is malformed")
    commit = client.json("GET", f"git/commits/{commit_sha}")
    tree_sha = commit.get("tree", {}).get("sha")
    if not isinstance(tree_sha, str) or len(tree_sha) != 40:
        raise ReleaseGateError("GitHub default branch commit lacks a tree")
    return commit_sha, tree_sha


def _remote_tree(client: GitHubClient, tree_sha: str) -> dict[str, dict]:
    response = client.json("GET", f"git/trees/{tree_sha}?recursive=1")
    if response.get("truncated") is not False:
        raise ReleaseGateError("GitHub recursive tree was truncated")
    rows = response.get("tree")
    if not isinstance(rows, list):
        raise ReleaseGateError("GitHub recursive tree is malformed")
    return {row["path"]: row for row in rows if row.get("type") == "blob"}


def _upload_tree_transaction(client: GitHubClient, config: dict, values: dict[str, bytes]) -> tuple[str, str, dict[str, str]]:
    branch = config["destinations"]["github"]["default_branch"]
    parent_sha, base_tree = _remote_head(client, branch)
    remote = _remote_tree(client, base_tree)
    desired_sha = {path: _git_blob_sha(raw) for path, raw in values.items()}
    changes = []
    for path in sorted(values, key=lambda value: value.encode("utf-8")):
        if remote.get(path, {}).get("sha") == desired_sha[path]:
            continue
        blob = client.json(
            "POST",
            "git/blobs",
            expected=(201,),
            payload={"content": base64.b64encode(values[path]).decode("ascii"), "encoding": "base64"},
        )
        if blob.get("sha") != desired_sha[path]:
            raise ReleaseGateError(f"GitHub blob SHA mismatch after upload: {path}")
        changes.append({"path": path, "mode": "100644", "type": "blob", "sha": desired_sha[path]})
    if EXCLUDED_SOURCE_PATH in remote:
        changes.append({"path": EXCLUDED_SOURCE_PATH, "mode": "100644", "type": "blob", "sha": None})

    if changes:
        # GitHub can reject one very large tree request with a transient 5xx.
        # Commit bounded chunks so a retry resumes from the last accepted branch
        # head and never needs a repository-wide local Git operation.
        chunk_size = 200
        commit_sha = parent_sha
        current_parent = parent_sha
        current_tree = base_tree
        for offset in range(0, len(changes), chunk_size):
            chunk = changes[offset : offset + chunk_size]
            new_tree = client.json(
                "POST", "git/trees", expected=(201,), payload={"base_tree": current_tree, "tree": chunk}
            )["sha"]
            commit = client.json(
                "POST",
                "git/commits",
                expected=(201,),
                payload={
                    "message": "Preserve admitted Indonesian R011-B008 boundary",
                    "tree": new_tree,
                    "parents": [current_parent],
                    "author": {"name": "Codex, atas permintaan pengguna", "email": "codex@users.noreply.github.com"},
                    "committer": {"name": "Codex, atas permintaan pengguna", "email": "codex@users.noreply.github.com"},
                },
            )
            commit_sha = commit["sha"]
            guard_sha, _ = _remote_head(client, branch)
            if guard_sha != current_parent:
                raise ReleaseGateError("GitHub main advanced during the bounded transaction")
            client.json(
                "PATCH",
                f"git/refs/heads/{quote(branch, safe='')}" ,
                payload={"sha": commit_sha, "force": False},
            )
            current_parent = commit_sha
            current_tree = new_tree
    else:
        commit_sha = parent_sha

    observed_tree = _remote_tree(client, _remote_head(client, branch)[1])
    for path, sha in desired_sha.items():
        if observed_tree.get(path, {}).get("sha") != sha:
            raise ReleaseGateError(f"GitHub committed tree mismatch: {path}")
    if EXCLUDED_SOURCE_PATH in observed_tree:
        raise ReleaseGateError("GitHub committed tree retains the excluded rights component")
    return commit_sha, parent_sha, desired_sha


def _upload_release_assets(client: GitHubClient, config: dict, commit_sha: str) -> dict:
    github = config["destinations"]["github"]
    tag = github["tag"]
    if client.maybe_json(f"releases/tags/{quote(tag, safe='')}") is not None:
        raise ReleaseGateError("GitHub release/tag collision for the exact B008 label")
    release = client.json(
        "POST",
        "releases",
        expected=(201,),
        payload={
            "tag_name": tag,
            "target_commitish": commit_sha,
            "name": "Statistika Berbasis Data - R011-B008",
            "body": (
                "Partial Indonesian working edition through exercise 2.34, with public odd answers through 2.33 and O001 even-answer gaps. "
                "Text/translation: CC BY-SA 3.0; component rights remain controlling. "
                f"Production model: {MODEL}. No upstream contact was performed."
            ),
            "draft": False,
            "prerelease": True,
        },
    )
    release_id = int(release["id"])
    for path in release_assets(config):
        with path.open("rb") as source:
            client.request(
                "POST",
                f"releases/{release_id}/assets?name={quote(path.name, safe='')}",
                expected=(201,),
                data=source,
                headers={"Content-Type": "application/octet-stream"},
                upload=True,
            )
    return client.json("GET", f"releases/tags/{quote(tag, safe='')}")


def _anonymous_readback(
    config: dict,
    commit_sha: str,
    desired_sha: dict[str, str],
    selected: list[str],
    values: dict[str, bytes],
) -> dict:
    github = config["destinations"]["github"]
    client = GitHubClient(None, github["owner"], github["repository"])
    release = client.json("GET", f"releases/tags/{quote(github['tag'], safe='')}")
    if release.get("tag_name") != github["tag"] or release.get("draft") or not release.get("prerelease"):
        raise ReleaseGateError("anonymous GitHub release metadata mismatch")
    tree = _remote_tree(client, client.json("GET", f"git/commits/{commit_sha}")["tree"]["sha"])
    for path, sha in desired_sha.items():
        if tree.get(path, {}).get("sha") != sha:
            raise ReleaseGateError(f"anonymous GitHub tree mismatch: {path}")

    raw_verified = []
    raw_session = public_session()
    slug = f"{github['owner']}/{github['repository']}"
    for path in selected:
        encoded = "/".join(quote(part, safe="") for part in PurePosixPath(path).parts)
        url = f"https://raw.githubusercontent.com/{slug}/{commit_sha}/{encoded}"
        response = raw_session.get(url, timeout=300, allow_redirects=True)
        if response.status_code != 200:
            raise ReleaseGateError(f"anonymous GitHub raw readback failed: {path}")
        expected_raw_sha = hashlib.sha256(values[path]).hexdigest()
        if hashlib.sha256(response.content).hexdigest() != expected_raw_sha:
            raise ReleaseGateError(f"anonymous GitHub raw SHA mismatch: {path}")
        raw_verified.append({"path": path, "bytes": len(response.content), "sha256": expected_raw_sha})

    assets = release.get("assets") or []
    expected_paths = release_assets(config)
    if [item.get("name") for item in assets] != [path.name for path in expected_paths]:
        raise ReleaseGateError("anonymous GitHub release asset order mismatch")
    asset_verified = []
    for item, path in zip(assets, expected_paths):
        response = raw_session.get(item["browser_download_url"], timeout=300, stream=True, allow_redirects=True)
        if response.status_code != 200:
            raise ReleaseGateError(f"anonymous GitHub release asset readback failed: {path.name}")
        digest = hashlib.sha256()
        count = 0
        for chunk in response.iter_content(1024 * 1024):
            if chunk:
                digest.update(chunk)
                count += len(chunk)
        local = identity(path)
        if count != local["bytes"] or digest.hexdigest() != local["sha256"]:
            raise ReleaseGateError(f"anonymous GitHub asset mismatch: {path.name}")
        asset_verified.append({"filename": path.name, "bytes": count, "sha256": digest.hexdigest()})
    return {"release": release, "raw": raw_verified, "assets": asset_verified}


def publish() -> dict:
    config, _ = execution_preflight(component="github publisher")
    zenodo = _publication_receipt("zenodo", config)
    figshare = _publication_receipt("figshare", config)
    github = config["destinations"]["github"]

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        token = token_from_file(Path.home() / "Downloads" / "Github Tokens.md", service="github")
    client = GitHubClient(token, github["owner"], github["repository"])
    repository = client.json("GET", "")
    if repository.get("full_name") != f"{github['owner']}/{github['repository']}" or repository.get("default_branch") != github["default_branch"]:
        raise ReleaseGateError("authenticated GitHub repository identity/default branch mismatch")
    if client.maybe_json(f"git/ref/tags/{quote(github['tag'], safe='')}") is not None:
        raise ReleaseGateError("GitHub tag collision before publication")

    values = _tree_allowlist(config, zenodo, figshare)
    commit_sha, parent_sha, desired_sha = _upload_tree_transaction(client, config, values)
    release = _upload_release_assets(client, config, commit_sha)
    selected = [
        "README.md",
        "LICENSE.md",
        "CITATION.cff",
        config["terminal_inputs"]["promoted_pdf"]["path"],
        config["terminal_inputs"]["backend_manifest"]["path"],
        config["terminal_inputs"]["boundary_receipt"]["path"],
        "ch_summarizing_data/TeX/review_exercises.tex",
        f"release/b008/{RELEASE_ID}/RELEASE_MANIFEST.json",
    ]
    readback = _anonymous_readback(config, commit_sha, desired_sha, selected, values)
    receipt = {
        "$schema": "r011-b008-github-publication-receipt/v1",
        "boundary_id": BOUNDARY_ID,
        "release_id": RELEASE_ID,
        "status": "PUBLISHED_AND_ANONYMOUSLY_VERIFIED",
        "repository": f"{github['owner']}/{github['repository']}",
        "tag": github["tag"],
        "release_id_numeric": int(release["id"]),
        "release_url": release.get("html_url"),
        "parent_commit": parent_sha,
        "release_commit": commit_sha,
        "tree_path_count": len(desired_sha),
        "selected_raw_readback": readback["raw"],
        "ordered_assets": readback["assets"],
        "zenodo_public_url": zenodo["public_url"],
        "figshare_public_url": figshare["public_url"],
        "production_model": MODEL,
        "no_upstream_contact": True,
        "local_git_used": False,
        "anonymous_readback": True,
        "credentials_recorded": False,
    }
    receipt_path = sanitized_receipt_path("github")
    atomic_write(receipt_path, canonical_json_bytes(receipt))
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--self-check", action="store_true")
    mode.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        return emit_self_check("github-publisher")
    print(json.dumps(publish(), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ReleaseGateError as exc:
        raise SystemExit(f"REFUSED: {exc}")
