#!/usr/bin/env python3
"""Publish R011-B008 into the existing Zenodo concept, then read bytes back.

Only ``--publish`` enters the authenticated transaction.  The default static
path is offline and credential-free, and the transaction remains fail-closed
until the terminal B008 admission inputs and package are exact.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import quote, urlparse

from release_b008_common import (
    BOUNDARY_ID,
    RELEASE_DIR,
    RELEASE_ID,
    ReleaseGateError,
    atomic_write,
    canonical_json_bytes,
    emit_self_check,
    execution_preflight,
    identity,
    load_json,
    public_session,
    release_assets,
    sanitized_receipt_path,
    token_from_file,
)


API = "https://zenodo.org/api"
PUBLIC = "https://zenodo.org"


def _checked_url(url: str, *, authenticated: bool) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "zenodo.org" or parsed.username or parsed.password:
        raise ReleaseGateError("Zenodo returned a link outside the exact HTTPS authority")
    if authenticated and not (
        parsed.path == "/api/deposit/depositions"
        or parsed.path.startswith(("/api/deposit/depositions/", "/api/files/"))
    ):
        raise ReleaseGateError("authenticated Zenodo link escaped allowed API paths")
    return url


class ZenodoClient:
    def __init__(self, token: str | None):
        self.session = public_session()
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"

    def request(self, method: str, url: str, *, expected=(200,), **kwargs):
        _checked_url(url, authenticated="Authorization" in self.session.headers)
        response = self.session.request(method, url, timeout=300, allow_redirects=False, **kwargs)
        if response.status_code not in expected:
            raise ReleaseGateError(f"Zenodo {method} {urlparse(url).path} returned HTTP {response.status_code}")
        return response

    def json(self, method: str, url: str, *, expected=(200,), **kwargs):
        response = self.request(method, url, expected=expected, **kwargs)
        try:
            return response.json()
        except ValueError as exc:
            raise ReleaseGateError("Zenodo returned malformed JSON") from exc


def _public_versions(concept_id: int) -> list[dict]:
    client = ZenodoClient(None)
    result = client.json(
        "GET",
        f"{API}/records",
        params={"q": f"conceptrecid:{concept_id}", "all_versions": "true", "size": 25, "sort": "mostrecent"},
    )
    hits = result.get("hits", {}).get("hits")
    if not isinstance(hits, list):
        raise ReleaseGateError("Zenodo public concept query is malformed")
    return hits


def _exact_public_readback(record_id: int, expected_rows: list[dict]) -> dict:
    client = ZenodoClient(None)
    record = client.json("GET", f"{API}/records/{record_id}")
    remote = record.get("files")
    if not isinstance(remote, list):
        raise ReleaseGateError("Zenodo public inventory is malformed")
    by_name = {row.get("key"): row for row in remote if isinstance(row.get("key"), str)}
    if len(by_name) != len(remote) or set(by_name) != {row["filename"] for row in expected_rows}:
        raise ReleaseGateError("Zenodo public inventory mismatch")
    verified = []
    for expected in expected_rows:
        item = by_name[expected["filename"]]
        link = item.get("links", {}).get("self") or item.get("links", {}).get("content")
        if not isinstance(link, str):
            raise ReleaseGateError("Zenodo public file lacks a readback link")
        parsed = urlparse(link)
        if parsed.scheme != "https" or not parsed.hostname or not (
            parsed.hostname == "zenodo.org" or parsed.hostname.endswith(".zenodo.org")
        ):
            raise ReleaseGateError("Zenodo public file link escaped Zenodo")
        response = client.session.get(link, timeout=300, stream=True, allow_redirects=True)
        if response.status_code != 200:
            raise ReleaseGateError(f"anonymous Zenodo readback returned HTTP {response.status_code}")
        digest = hashlib.sha256()
        count = 0
        for chunk in response.iter_content(1024 * 1024):
            if chunk:
                digest.update(chunk)
                count += len(chunk)
        if count != expected["bytes"] or digest.hexdigest() != expected["sha256"]:
            raise ReleaseGateError(f"anonymous Zenodo byte mismatch: {expected['filename']}")
        verified.append({"filename": expected["filename"], "bytes": count, "sha256": digest.hexdigest()})
    return {"record": record, "files": verified}


def _md5(path: Path) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _publication_receipt(config: dict, destination: dict, record_id: int, readback: dict, status: str) -> dict:
    public_record = readback["record"]
    if int(public_record.get("conceptrecid", -1)) != destination["concept_record_id"]:
        raise ReleaseGateError("published Zenodo record escaped the existing concept")
    if public_record.get("metadata", {}).get("version") != config["version"]:
        raise ReleaseGateError("published Zenodo version mismatch")
    receipt = {
        "$schema": "r011-b008-zenodo-publication-receipt/v1",
        "boundary_id": BOUNDARY_ID,
        "release_id": RELEASE_ID,
        "status": status,
        "concept_doi": destination["concept_doi"],
        "concept_record_id": destination["concept_record_id"],
        "record_id": record_id,
        "doi": public_record.get("doi"),
        "public_url": f"{PUBLIC}/records/{record_id}",
        "version": config["version"],
        "ordered_files": readback["files"],
        "reader_first_by_zero_padded_filename": True,
        "credentials_recorded": False,
        "anonymous_readback": True,
    }
    atomic_write(sanitized_receipt_path("zenodo"), canonical_json_bytes(receipt))
    return receipt


def publish() -> dict:
    config, _ = execution_preflight(component="zenodo publisher")
    destination = config["destinations"]["zenodo"]
    assets = release_assets(config)
    expected_rows = []
    expected_by_name = {}
    for path in assets:
        row = identity(path)
        expected = {
            "filename": path.name,
            "bytes": row["bytes"],
            "sha256": row["sha256"],
            "md5": _md5(path),
        }
        expected_rows.append(expected)
        expected_by_name[path.name] = (path, expected)

    versions = _public_versions(destination["concept_record_id"])
    public_matches = [hit for hit in versions if hit.get("metadata", {}).get("version") == config["version"]]
    if len(public_matches) > 1:
        raise ReleaseGateError("multiple public Zenodo records claim the exact B008 version")
    if public_matches:
        record_id = int(public_matches[0]["id"])
        readback = _exact_public_readback(record_id, expected_rows)
        return _publication_receipt(
            config,
            destination,
            record_id,
            readback,
            "ALREADY_PUBLISHED_AND_ANONYMOUSLY_REVERIFIED",
        )
    if not versions:
        raise ReleaseGateError("existing Zenodo concept has no public version")
    latest = versions[0]
    if int(latest.get("conceptrecid", -1)) != destination["concept_record_id"]:
        raise ReleaseGateError("Zenodo public version escaped the existing concept")
    latest_id = int(latest["id"])

    token_path = Path.home() / "Documents" / "Obsidian notes" / "New zenodo token.md"
    token = token_from_file(token_path, service="zenodo")
    client = ZenodoClient(token)
    private_rows = client.json(
        "GET",
        f"{API}/deposit/depositions",
        params={"q": config["version"], "size": 25, "sort": "mostrecent"},
    )
    if not isinstance(private_rows, list):
        raise ReleaseGateError("Zenodo private deposition query is malformed")
    draft_matches = [
        row
        for row in private_rows
        if row.get("state") == "unsubmitted"
        and row.get("metadata", {}).get("version") == config["version"]
        and int(row.get("conceptrecid", -1)) == destination["concept_record_id"]
    ]
    if len(draft_matches) > 1:
        raise ReleaseGateError("multiple unsubmitted Zenodo drafts claim the exact B008 version")
    if draft_matches:
        draft_id = int(draft_matches[0]["id"])
        draft = client.json("GET", f"{API}/deposit/depositions/{draft_id}")
    else:
        prior = client.json("GET", f"{API}/deposit/depositions/{latest_id}")
        if int(prior.get("conceptrecid", -1)) != destination["concept_record_id"] or prior.get("state") != "done":
            raise ReleaseGateError("latest Zenodo deposition is not the published concept head")
        response = client.json(
            "POST",
            f"{API}/deposit/depositions/{latest_id}/actions/newversion",
            expected=(201, 202),
        )
        draft_link = response.get("links", {}).get("latest_draft")
        if not isinstance(draft_link, str):
            raise ReleaseGateError("Zenodo new-version response lacks latest_draft")
        draft = client.json("GET", _checked_url(draft_link, authenticated=True))
        draft_id = int(draft["id"])
    if int(draft.get("conceptrecid", -1)) != destination["concept_record_id"] or draft.get("state") != "unsubmitted":
        raise ReleaseGateError("Zenodo draft is not an unsubmitted version of the existing concept")

    bucket = draft.get("links", {}).get("bucket")
    if not isinstance(bucket, str):
        raise ReleaseGateError("Zenodo draft lacks an upload bucket")
    _checked_url(bucket, authenticated=True)
    remote_by_name = {item.get("filename"): item for item in draft.get("files", []) if item.get("filename")}
    for name, item in list(remote_by_name.items()):
        expected_pair = expected_by_name.get(name)
        checksum = str(item.get("checksum", "")).removeprefix("md5:")
        if expected_pair and item.get("filesize") == expected_pair[1]["bytes"] and checksum == expected_pair[1]["md5"]:
            continue
        file_id = item.get("id")
        if not file_id:
            raise ReleaseGateError("Zenodo draft file lacks an id")
        client.request("DELETE", f"{API}/deposit/depositions/{draft_id}/files/{file_id}", expected=(204,))
        remote_by_name.pop(name, None)

    for path in assets:
        if path.name in remote_by_name:
            continue
        with path.open("rb") as handle:
            client.request(
                "PUT",
                bucket.rstrip("/") + "/" + quote(path.name, safe=""),
                expected=(200, 201),
                data=handle,
                headers={"Content-Type": "application/octet-stream"},
            )

    metadata = load_json(RELEASE_DIR / "ZENODO_METADATA.json")
    if metadata.get("metadata", {}).get("version") != config["version"]:
        raise ReleaseGateError("packaged Zenodo metadata has the wrong version")
    client.json("PUT", f"{API}/deposit/depositions/{draft_id}", data=canonical_json_bytes(metadata), headers={"Content-Type": "application/json"})
    guarded = client.json("GET", f"{API}/deposit/depositions/{draft_id}")
    guarded_by_name = {item.get("filename"): item for item in guarded.get("files", []) if item.get("filename")}
    if set(guarded_by_name) != set(expected_by_name) or len(guarded_by_name) != len(guarded.get("files", [])):
        raise ReleaseGateError("Zenodo authenticated draft inventory mismatch")
    for name, (_, expected) in expected_by_name.items():
        item = guarded_by_name[name]
        checksum = str(item.get("checksum", "")).removeprefix("md5:")
        if item.get("filesize") != expected["bytes"] or checksum != expected["md5"]:
            raise ReleaseGateError(f"Zenodo authenticated draft byte identity mismatch: {name}")
    published = client.json(
        "POST", f"{API}/deposit/depositions/{draft_id}/actions/publish", expected=(201, 202)
    )
    record_id = int(published["record_id"] if "record_id" in published else published["id"])
    readback = _exact_public_readback(record_id, expected_rows)
    return _publication_receipt(
        config,
        destination,
        record_id,
        readback,
        "PUBLISHED_AND_ANONYMOUSLY_VERIFIED",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--self-check", action="store_true")
    mode.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        return emit_self_check("zenodo-publisher")
    print(json.dumps(publish(), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ReleaseGateError as exc:
        raise SystemExit(f"REFUSED: {exc}")
