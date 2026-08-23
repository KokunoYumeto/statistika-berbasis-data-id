#!/usr/bin/env python3
"""Update the existing R011 Figshare work and Indonesian collection.

The authenticated branch queries the account's real license inventory.  It
mirrors the exact reader-first package only when CC BY-SA 3.0 is offered;
otherwise it publishes CC0 metadata plus one external reader link to the exact
Zenodo version and never assigns a false edition license.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from urllib.parse import quote, urlparse

from release_b008_common import (
    BOUNDARY_ID,
    MODEL,
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


API = "https://api.figshare.com/v2"


def _api_url(endpoint: str) -> str:
    endpoint = endpoint.lstrip("/")
    allowed = (
        "account/licenses",
        "account/articles/",
        "account/projects/",
        "account/collections/",
        "articles/",
        "projects/",
        "collections/",
    )
    if not endpoint.startswith(allowed) or ".." in endpoint:
        raise ReleaseGateError("Figshare endpoint escaped the bounded API paths")
    return f"{API}/{endpoint}"


class FigshareClient:
    def __init__(self, token: str | None):
        self.session = public_session()
        if token:
            self.session.headers["Authorization"] = f"token {token}"

    def request(self, method: str, endpoint: str, *, expected=(200,), payload=None):
        response = self.session.request(
            method,
            _api_url(endpoint),
            timeout=300,
            allow_redirects=False,
            json=payload,
        )
        if response.status_code not in expected:
            raise ReleaseGateError(
                f"Figshare {method} {endpoint.split('?')[0]} returned HTTP {response.status_code}"
            )
        return response

    def json(self, method: str, endpoint: str, *, expected=(200,), payload=None):
        response = self.request(method, endpoint, expected=expected, payload=payload)
        try:
            return response.json()
        except ValueError as exc:
            raise ReleaseGateError("Figshare returned malformed JSON") from exc


def _license_kind(item: dict) -> str | None:
    surface = " ".join(str(item.get(key, "")) for key in ("name", "url")).casefold()
    normalized = "".join(ch for ch in surface if ch.isalnum())
    if "creativecommonsorglicensesbysa30" in normalized or "ccby-sa3.0" in surface or "ccbysa30" in normalized:
        return "cc-by-sa-3.0"
    if "creativecommonsorgpublicdomainzero10" in normalized or "cc0" in normalized:
        return "cc0"
    return None


def _choose_license(items: list[dict]) -> tuple[str, dict]:
    exact = [item for item in items if _license_kind(item) == "cc-by-sa-3.0"]
    if len(exact) == 1:
        return "exact_cc_by_sa_3_0_hosted_mirror", exact[0]
    if len(exact) > 1:
        raise ReleaseGateError("Figshare exposes ambiguous exact CC BY-SA 3.0 licenses")
    cc0 = [item for item in items if _license_kind(item) == "cc0"]
    if len(cc0) != 1:
        raise ReleaseGateError("Figshare lacks one unambiguous CC0 metadata fallback license")
    return "cc0_metadata_link_only", cc0[0]


def _license_value(item: dict) -> int:
    value = item.get("value", item.get("id"))
    if value is None:
        raise ReleaseGateError("Figshare license entry lacks both value and id")
    return int(value)


def _zenodo_receipt(config: dict) -> tuple[dict, list[dict]]:
    path = sanitized_receipt_path("zenodo")
    if not path.is_file():
        raise ReleaseGateError("Figshare requires the sanitized public Zenodo receipt")
    receipt = load_json(path)
    if (
        receipt.get("status") != "PUBLISHED_AND_ANONYMOUSLY_VERIFIED"
        or receipt.get("boundary_id") != BOUNDARY_ID
        or receipt.get("release_id") != RELEASE_ID
        or receipt.get("concept_doi") != config["destinations"]["zenodo"]["concept_doi"]
    ):
        raise ReleaseGateError("Zenodo receipt does not prove this B008 release")
    rows = receipt.get("ordered_files")
    expected = []
    for path in release_assets(config):
        item = identity(path)
        expected.append({"filename": path.name, "bytes": item["bytes"], "sha256": item["sha256"]})
    if rows != expected:
        raise ReleaseGateError("Zenodo public-byte receipt differs from local release package")
    return receipt, expected


def _md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _upload_hosted(client: FigshareClient, article_id: int, path: Path) -> None:
    initiated = client.request(
        "POST",
        f"account/articles/{article_id}/files",
        expected=(201,),
        payload={"name": path.name, "size": path.stat().st_size, "md5": _md5(path)},
    )
    location = initiated.headers.get("Location")
    if not location:
        raise ReleaseGateError("Figshare upload initiation lacks Location")
    parsed = urlparse(location)
    prefix = f"/v2/account/articles/{article_id}/files/"
    if parsed.scheme != "https" or parsed.hostname != "api.figshare.com" or not parsed.path.startswith(prefix):
        raise ReleaseGateError("Figshare upload Location escaped the fixed article")
    file_id = int(parsed.path.rstrip("/").split("/")[-1])
    info = client.json("GET", f"account/articles/{article_id}/files/{file_id}")
    upload_url = info.get("upload_url")
    parsed_upload = urlparse(str(upload_url))
    if parsed_upload.scheme != "https" or parsed_upload.hostname != "uploads.figshare.com":
        raise ReleaseGateError("Figshare upload URL escaped uploads.figshare.com")

    upload_session = public_session()
    manifest_response = upload_session.get(upload_url, timeout=300, allow_redirects=False)
    if manifest_response.status_code != 200:
        raise ReleaseGateError("Figshare upload manifest request failed")
    parts = manifest_response.json().get("parts")
    if not isinstance(parts, list) or not parts:
        raise ReleaseGateError("Figshare upload manifest has no parts")
    normalized = sorted(
        (int(part["startOffset"]), int(part["endOffset"]), int(part["partNo"])) for part in parts
    )
    cursor = 0
    with path.open("rb") as source:
        for start, end, number in normalized:
            if start != cursor or end < start:
                raise ReleaseGateError("Figshare upload parts are discontinuous")
            source.seek(start)
            data = source.read(end - start + 1)
            if len(data) != end - start + 1:
                raise ReleaseGateError("short read while preparing Figshare part")
            part_url = str(upload_url).rstrip("/") + f"/{number}"
            if not part_url.startswith(str(upload_url).rstrip("/") + "/"):
                raise ReleaseGateError("unsafe Figshare part URL")
            response = upload_session.put(part_url, data=data, timeout=300, allow_redirects=False)
            if not 200 <= response.status_code < 300:
                raise ReleaseGateError(f"Figshare upload part {number} failed")
            cursor = end + 1
    if cursor != path.stat().st_size:
        raise ReleaseGateError("Figshare upload parts did not cover the exact file")
    client.request("POST", f"account/articles/{article_id}/files/{file_id}", expected=(202,))


def _delete_files(client: FigshareClient, article_id: int) -> None:
    rows = client.json("GET", f"account/articles/{article_id}/files")
    if not isinstance(rows, list):
        raise ReleaseGateError("Figshare account file inventory is malformed")
    for row in rows:
        client.request("DELETE", f"account/articles/{article_id}/files/{int(row['id'])}", expected=(204,))


def _project_hosted_bytes(anonymous: FigshareClient, project_id: int, target_id: int) -> tuple[int, bool]:
    articles = anonymous.json("GET", f"projects/{project_id}/articles?page_size=1000")
    if not isinstance(articles, list):
        raise ReleaseGateError("Figshare project inventory is malformed")
    total = 0
    contains = False
    for row in articles:
        article_id = int(row["id"])
        contains |= article_id == target_id
        detail = anonymous.json("GET", f"articles/{article_id}")
        for item in detail.get("files", []) or []:
            if not item.get("is_link_only"):
                total += int(item.get("size", 0))
    return total, contains


def _anonymous_readback(config: dict, route: str, expected: list[dict], zenodo: dict) -> dict:
    destination = config["destinations"]["figshare"]
    client = FigshareClient(None)
    article = client.json("GET", f"articles/{destination['article_id']}")
    if int(article.get("id", -1)) != destination["article_id"] or "R011-B008" not in str(article.get("title")):
        raise ReleaseGateError("anonymous Figshare article is not the B008 target")
    files = article.get("files") or []
    verified = []
    if route == "exact_cc_by_sa_3_0_hosted_mirror":
        if [item.get("name") for item in files] != [row["filename"] for row in expected]:
            raise ReleaseGateError("Figshare hosted reader-first inventory mismatch")
        for item, wanted in zip(files, expected):
            response = client.session.get(item["download_url"], timeout=300, stream=True, allow_redirects=True)
            if response.status_code != 200:
                raise ReleaseGateError("anonymous Figshare hosted-file readback failed")
            digest = hashlib.sha256()
            count = 0
            for chunk in response.iter_content(1024 * 1024):
                if chunk:
                    digest.update(chunk)
                    count += len(chunk)
            if count != wanted["bytes"] or digest.hexdigest() != wanted["sha256"]:
                raise ReleaseGateError(f"Figshare byte mismatch: {wanted['filename']}")
            verified.append(wanted)
    else:
        accepted_names = {expected[0]["filename"], expected[0]["filename"] + "?download=1"}
        if len(files) != 1 or not files[0].get("is_link_only") or files[0].get("name") not in accepted_names:
            raise ReleaseGateError("Figshare CC0 fallback is not one reader-first external link")
        if str(zenodo["record_id"]) not in str(files[0].get("download_url")):
            raise ReleaseGateError("Figshare external reader does not point to the exact Zenodo version")
        response = client.session.get(files[0]["download_url"], timeout=300, stream=True, allow_redirects=True)
        if response.status_code != 200:
            raise ReleaseGateError("anonymous Figshare external-reader readback failed")
        digest = hashlib.sha256()
        count = 0
        for chunk in response.iter_content(1024 * 1024):
            if chunk:
                digest.update(chunk)
                count += len(chunk)
        if count != expected[0]["bytes"] or digest.hexdigest() != expected[0]["sha256"]:
            raise ReleaseGateError("Figshare external reader byte identity mismatch")
        verified.append(
            {
                "filename": expected[0]["filename"],
                "bytes": count,
                "sha256": digest.hexdigest(),
                "route": "external_zenodo_link",
            }
        )

    project = client.json("GET", f"projects/{destination['project_id']}/articles?page_size=1000")
    collection = client.json("GET", f"collections/{destination['collection_id']}/articles?page_size=1000")
    if destination["article_id"] not in {int(row["id"]) for row in project}:
        raise ReleaseGateError("public Figshare project lacks the target article")
    if destination["article_id"] not in {int(row["id"]) for row in collection}:
        raise ReleaseGateError("public Indonesian collection lacks the target article")
    return {"article": article, "files": verified}


def publish() -> dict:
    config, _ = execution_preflight(component="figshare publisher")
    zenodo, expected = _zenodo_receipt(config)
    destination = config["destinations"]["figshare"]
    logical_bytes = sum(row["bytes"] for row in expected)
    if logical_bytes > destination["max_item_bytes"]:
        raise ReleaseGateError("B008 payload exceeds the 500,000,000-byte cap")

    anonymous = FigshareClient(None)
    hosted_before, project_contains = _project_hosted_bytes(
        anonymous, destination["project_id"], destination["article_id"]
    )
    if not project_contains:
        raise ReleaseGateError("existing Figshare article is not in the fixed project")
    current_public = anonymous.json("GET", f"articles/{destination['article_id']}")
    prior_version = int(current_public.get("version", 0))
    current_target_bytes = sum(
        int(row.get("size", 0)) for row in current_public.get("files", []) if not row.get("is_link_only")
    )

    current_files = current_public.get("files") or []
    current_license = current_public.get("license") or {}
    if (
        "R011-B008" in str(current_public.get("title"))
        and len(current_files) == 1
        and bool(current_files[0].get("is_link_only"))
        and str(zenodo["record_id"]) in str(current_files[0].get("download_url"))
        and _license_kind(current_license) == "cc0"
        and MODEL in str(current_public.get("description"))
    ):
        route = "cc0_metadata_link_only"
        readback = _anonymous_readback(config, route, expected, zenodo)
        receipt = {
            "$schema": "r011-b008-figshare-publication-receipt/v1",
            "boundary_id": BOUNDARY_ID,
            "release_id": RELEASE_ID,
            "status": "ALREADY_PUBLISHED_AND_ANONYMOUSLY_REVERIFIED",
            "article_id": destination["article_id"],
            "article_version": int(current_public["version"]),
            "article_doi": current_public.get("doi"),
            "public_url": current_public.get("url_public_html"),
            "project_id": destination["project_id"],
            "collection_id": destination["collection_id"],
            "route": route,
            "license_id": _license_value(current_license),
            "license_name": current_license.get("name"),
            "ordered_files": readback["files"],
            "logical_payload_bytes": logical_bytes,
            "projected_hosted_bytes": hosted_before - current_target_bytes,
            "production_model": MODEL,
            "anonymous_readback": True,
            "credentials_recorded": False,
        }
        atomic_write(sanitized_receipt_path("figshare"), canonical_json_bytes(receipt))
        return receipt

    token = token_from_file(Path.home() / "Documents" / "TOKENS" / "Figshare Token.md", service="figshare")
    client = FigshareClient(token)
    licenses = client.json("GET", "account/licenses")
    if not isinstance(licenses, list):
        raise ReleaseGateError("Figshare account license inventory is malformed")
    route, license_item = _choose_license(licenses)
    projected = hosted_before - current_target_bytes + (logical_bytes if route.startswith("exact_") else 0)
    if projected >= destination["max_project_bytes"]:
        raise ReleaseGateError("projected Figshare project storage reaches the 20GB cap")

    project = client.json("GET", f"account/projects/{destination['project_id']}")
    collection = client.json("GET", f"account/collections/{destination['collection_id']}")
    article = client.json("GET", f"account/articles/{destination['article_id']}")
    if int(project.get("id", -1)) != destination["project_id"] or int(collection.get("id", -1)) != destination["collection_id"]:
        raise ReleaseGateError("authenticated Figshare project/collection mismatch")
    if int(article.get("id", -1)) != destination["article_id"] or not article.get("is_public"):
        raise ReleaseGateError("fixed Figshare article is not an aligned public head")
    if int(article.get("version", 0)) != prior_version:
        raise ReleaseGateError("authenticated/public Figshare article versions diverge")

    route_text = (
        "Figshare menghosting sembilan berkas rilis secara byte-for-byte di bawah CC BY-SA 3.0 yang tersedia tepat di akun."
        if route.startswith("exact_")
        else "Figshare tidak menyediakan CC BY-SA 3.0 secara tepat; item ini memakai CC0 hanya untuk metadata dan satu tautan pembaca eksternal ke versi Zenodo. Figshare tidak melisensikan ulang byte edisi."
    )
    description = (
        "<p><strong>Edisi kerja parsial/belum lengkap.</strong> Materi pendahuluan, Bab 1, Bagian 2.1-2.3, latihan sampai 2.34, jawaban publik ganjil sampai 2.33, dan O001 untuk celah genap.</p>"
        f"<p>{route_text}</p><p>Zenodo: <a href=\"{zenodo['public_url']}\">{zenodo.get('doi') or zenodo['public_url']}</a>.</p>"
        "<p>Karya turunan dari <em>OpenIntro Statistics</em> oleh David M. Diez, Mine Çetinkaya-Rundel, dan Christopher D. Barr. Teks/terjemahan: CC BY-SA 3.0 Unported; hak komponen yang lebih khusus tetap berlaku. Kontributor edisi: Codex, atas permintaan pengguna. Model produksi: <strong>OpenAI Codex gpt-5.6-sol, Ultra</strong>.</p>"
    )
    payload = {
        "title": "Statistika Berbasis Data - Edisi Kerja Bahasa Indonesia (R011-B008: sampai latihan 2.34)",
        "description": description,
        "tags": ["Bahasa Indonesia", "statistika", "open educational resources", "partial edition", "R011"],
        "categories": [26095],
        "defined_type": "online resource",
        "license": _license_value(license_item),
        "references": [
            zenodo["public_url"],
            "https://github.com/OpenIntroStat/openintro-statistics/tree/fee25091fb24e89c36296fd67c48c1fcf7a93b6e",
            "https://www.openintro.org/book/os/",
        ],
    }
    client.request("PUT", f"account/articles/{destination['article_id']}", expected=(200, 205), payload=payload)
    _delete_files(client, destination["article_id"])
    if route.startswith("exact_"):
        for path in release_assets(config):
            _upload_hosted(client, destination["article_id"], path)
    else:
        reader_url = (
            f"https://zenodo.org/records/{int(zenodo['record_id'])}/files/"
            + quote(expected[0]["filename"], safe="")
            + "?download=1"
        )
        client.request(
            "POST",
            f"account/articles/{destination['article_id']}/files",
            expected=(201,),
            payload={"link": reader_url},
        )
    client.request("POST", f"account/articles/{destination['article_id']}/publish", expected=(201,))

    private_collection = client.json(
        "GET", f"account/collections/{destination['collection_id']}/articles?page_size=1000"
    )
    if destination["article_id"] not in {int(row["id"]) for row in private_collection}:
        client.request(
            "POST",
            f"account/collections/{destination['collection_id']}/articles",
            expected=(201,),
            payload={"articles": [destination["article_id"]]},
        )
        client.request(
            "POST", f"account/collections/{destination['collection_id']}/publish", expected=(201,)
        )

    readback = None
    for attempt in range(30):
        try:
            readback = _anonymous_readback(config, route, expected, zenodo)
            if int(readback["article"].get("version", 0)) > prior_version:
                break
        except ReleaseGateError:
            readback = None
        if attempt < 29:
            time.sleep(2)
    if readback is None or int(readback["article"].get("version", 0)) <= prior_version:
        raise ReleaseGateError("Figshare public B008 version/readback did not converge")

    article_public = readback["article"]
    receipt = {
        "$schema": "r011-b008-figshare-publication-receipt/v1",
        "boundary_id": BOUNDARY_ID,
        "release_id": RELEASE_ID,
        "status": "PUBLISHED_AND_ANONYMOUSLY_VERIFIED",
        "article_id": destination["article_id"],
        "article_version": int(article_public["version"]),
        "article_doi": article_public.get("doi"),
        "public_url": article_public.get("url_public_html"),
        "project_id": destination["project_id"],
        "collection_id": destination["collection_id"],
        "route": route,
        "license_id": _license_value(license_item),
        "license_name": license_item.get("name"),
        "ordered_files": readback["files"],
        "logical_payload_bytes": logical_bytes,
        "projected_hosted_bytes": projected,
        "production_model": MODEL,
        "anonymous_readback": True,
        "credentials_recorded": False,
    }
    atomic_write(sanitized_receipt_path("figshare"), canonical_json_bytes(receipt))
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--self-check", action="store_true")
    mode.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        return emit_self_check("figshare-publisher")
    print(json.dumps(publish(), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ReleaseGateError as exc:
        raise SystemExit(f"REFUSED: {exc}")
