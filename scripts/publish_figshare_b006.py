from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

import requests


LANE = Path(__file__).resolve().parents[1]
TOKEN_PATH = Path(r"C:\Users\Floris\Documents\TOKENS\Figshare Token.md")
ZENODO_RECEIPT = (
    LANE
    / "release"
    / "zenodo"
    / "R011-B006-v2026.08.22.2"
    / "ZENODO_PUBLICATION_RECEIPT.json"
)
RELEASE = LANE / "release" / "figshare" / "R011-B006-v2026.08.22.2"
PAYLOAD_FILE = RELEASE / "FIGSHARE_ARTICLE_PAYLOAD.json"
LINK_PLAN_FILE = RELEASE / "FIGSHARE_LINK_PLAN.json"
RECEIPT_FILE = RELEASE / "FIGSHARE_PUBLICATION_RECEIPT.json"

API = "https://api.figshare.com/v2"
ARTICLE_ID = 33314727
PROJECT_ID = 280296
COLLECTION_ID = 8668413
CC0_LICENSE_ID = 2
PROJECT_HOSTED_LIMIT_BYTES = 20_000_000_000
PAYLOAD_LIMIT_BYTES = 500_000_000
EXPECTED_ZENODO_RECEIPT = {
    "bytes": 4546,
    "sha256": "534850058087dd84323017a0dceee40ea8f4943aa92a3a09c4c12ef312a433b8",
}
# These two static transaction inputs are pinned so a later local edit cannot
# silently change a public Figshare version.
EXPECTED_PAYLOAD = {
    "bytes": 3866,
    "sha256": "99046f6b56c8b92c029ef027be8c3e54a68126989aede3162329fad6352be085",
}
EXPECTED_LINK_PLAN = {
    "bytes": 3255,
    "sha256": "de236ba1af4bcddb0ad54b85490e5d1a82bd6eca9641b6e599966d4750155fc4",
}
READ_RETRY_STATUSES = {403, 408, 425, 429, 500, 502, 503, 504}


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")


def identity(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {
        "path": path.relative_to(LANE).as_posix(),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def require_identity(path: Path, expected: dict[str, Any]) -> None:
    observed = identity(path)
    if observed["bytes"] != expected.get("bytes") or observed["sha256"] != expected.get(
        "sha256"
    ):
        raise RuntimeError(
            f"refusing changed local input {observed['path']}: "
            f"observed {observed['bytes']} bytes {observed['sha256']}"
        )


def read_token() -> str:
    token = TOKEN_PATH.read_text(encoding="utf-8").strip()
    if not token or any(character.isspace() for character in token):
        raise RuntimeError("Figshare token file is empty or is not one token")
    if len(token) < 40:
        raise RuntimeError("Figshare token is unexpectedly short")
    return token


class Http:
    def __init__(self, token: str | None = None) -> None:
        self.session = requests.Session()
        # Figshare's load balancer intermittently rejects the default Python
        # requests fingerprint. This ordinary curl user-agent is accepted by
        # the same public and authenticated API routes.
        self.session.headers.update(
            {"Accept": "application/json", "User-Agent": "curl/8.7.1"}
        )
        if token is not None:
            self.session.headers["Authorization"] = f"token {token}"

    def request(
        self,
        method: str,
        endpoint_or_url: str,
        *,
        payload: Any | None = None,
        expected: tuple[int, ...] = (200,),
    ) -> requests.Response:
        url = (
            endpoint_or_url
            if endpoint_or_url.startswith("https://")
            else f"{API}/{endpoint_or_url.lstrip('/')}"
        )
        attempts = 7 if method.upper() in {"GET", "HEAD"} else 1
        last_response: requests.Response | None = None
        for attempt in range(attempts):
            try:
                response = self.session.request(
                    method, url, json=payload, timeout=120, allow_redirects=True
                )
            except requests.RequestException:
                if attempt + 1 == attempts:
                    raise
                time.sleep(min(2**attempt, 12))
                continue
            last_response = response
            if response.status_code in expected:
                return response
            if (
                method.upper() in {"GET", "HEAD"}
                and response.status_code in READ_RETRY_STATUSES
                and attempt + 1 < attempts
            ):
                time.sleep(min(2**attempt, 12))
                continue
            message = ""
            try:
                body = response.json()
                if isinstance(body, dict):
                    message = str(body.get("message", ""))
            except ValueError:
                pass
            raise RuntimeError(
                f"Figshare API {method} {urlparse(url).path} returned "
                f"HTTP {response.status_code}: {message[:300]}"
            )
        assert last_response is not None
        raise RuntimeError(
            f"Figshare API {method} {urlparse(url).path} remained at "
            f"HTTP {last_response.status_code} after bounded retries"
        )

    def json(
        self,
        method: str,
        endpoint_or_url: str,
        *,
        payload: Any | None = None,
        expected: tuple[int, ...] = (200,),
    ) -> Any:
        response = self.request(
            method, endpoint_or_url, payload=payload, expected=expected
        )
        if not response.content:
            return None
        return response.json()


def response_location(response: requests.Response) -> str:
    location = response.headers.get("Location")
    if location:
        return location
    if response.content:
        body = response.json()
        if isinstance(body, dict) and isinstance(body.get("location"), str):
            return body["location"]
    raise RuntimeError("Figshare response did not provide a resource location")


def exact_by_sa_30(licenses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for license_item in licenses:
        name = str(license_item.get("name", "")).lower().replace("-", " ")
        url = str(license_item.get("url", "")).lower()
        if "/by-sa/3.0" in url or (
            "by" in name and "sa" in name and "3.0" in name
        ):
            matches.append(license_item)
    return matches


def validate_inputs() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    require_identity(ZENODO_RECEIPT, EXPECTED_ZENODO_RECEIPT)
    require_identity(PAYLOAD_FILE, EXPECTED_PAYLOAD)
    require_identity(LINK_PLAN_FILE, EXPECTED_LINK_PLAN)
    zenodo = json.loads(ZENODO_RECEIPT.read_text(encoding="utf-8"))
    payload = json.loads(PAYLOAD_FILE.read_text(encoding="utf-8"))
    plan = json.loads(LINK_PLAN_FILE.read_text(encoding="utf-8"))
    if (
        zenodo.get("status") != "published_and_anonymously_verified"
        or zenodo.get("boundary_id") != "R011-B006"
        or int(zenodo.get("record_id", -1)) != 22061163
        or zenodo.get("doi") != "10.5281/zenodo.22061163"
        or zenodo.get("concept_doi") != "10.5281/zenodo.22059801"
    ):
        raise RuntimeError("Zenodo receipt is not the admitted B006 public version")
    if (
        int(plan.get("article_id", -1)) != ARTICLE_ID
        or int(plan.get("project_id", -1)) != PROJECT_ID
        or int(plan.get("collection_id", -1)) != COLLECTION_ID
        or plan.get("boundary_id") != "R011-B006"
    ):
        raise RuntimeError("Figshare link plan has the wrong fixed identities")
    if int(payload.get("license", -1)) != CC0_LICENSE_ID:
        raise RuntimeError("Figshare metadata payload is not pinned to CC0")
    expected_files = plan.get("ordered_external_files")
    if not isinstance(expected_files, list) or len(expected_files) != 6:
        raise RuntimeError("Figshare link plan must contain exactly six files")
    receipt_files = {item["filename"]: item for item in zenodo.get("files", [])}
    for position, item in enumerate(expected_files, start=1):
        if int(item.get("position", -1)) != position:
            raise RuntimeError("Figshare link positions are not contiguous")
        source = receipt_files.get(item.get("filename"))
        if source is None:
            raise RuntimeError(f"planned file is absent from Zenodo: {item.get('filename')}")
        for field, source_field in (("bytes", "bytes"), ("sha256", "sha256")):
            if item.get(field) != source.get(source_field):
                raise RuntimeError(
                    f"planned {field} does not match Zenodo for {item.get('filename')}"
                )
        immutable_file_url = (
            f"https://zenodo.org/records/{int(zenodo['record_id'])}/files/"
            f"{quote(str(item['filename']))}"
        )
        if item.get("url") != immutable_file_url:
            raise RuntimeError(
                f"planned immutable URL is wrong for {item.get('filename')}"
            )
    logical_bytes = sum(int(item["bytes"]) for item in expected_files)
    if logical_bytes != int(plan.get("logical_payload_bytes", -1)):
        raise RuntimeError("Figshare logical payload total is inconsistent")
    if logical_bytes > PAYLOAD_LIMIT_BYTES:
        raise RuntimeError("Figshare logical payload exceeds 500,000,000 bytes")
    if expected_files[0].get("role") != "reader_pdf" or not str(
        expected_files[0].get("filename", "")
    ).lower().endswith(".pdf"):
        raise RuntimeError("Figshare first external file is not the PDF reader")
    if (
        int(plan.get("figshare_external_file_object_count", -1)) != 1
        or int(plan.get("figshare_metadata_link_count", -1)) != 5
    ):
        raise RuntimeError("Figshare one-file/five-metadata-link split is not pinned")
    description = str(payload.get("description", ""))
    references = list(payload.get("references") or [])
    for item in expected_files:
        if item["url"] not in description or item["url"] not in references:
            raise RuntimeError(
                f"visible Figshare metadata omits the exact link for {item['filename']}"
            )
    return zenodo, payload, plan


def files_match(files: list[dict[str, Any]], expected: list[dict[str, Any]]) -> bool:
    if len(files) != len(expected):
        return False
    for observed, planned in zip(files, expected, strict=True):
        if (
            observed.get("name") != planned.get("filename")
            or observed.get("download_url") != planned.get("url")
            or not bool(observed.get("is_link_only"))
        ):
            return False
    return True


def public_article_matches(
    article: dict[str, Any], payload: dict[str, Any], expected: list[dict[str, Any]]
) -> bool:
    license_item = article.get("license") or {}
    return (
        int(article.get("id", -1)) == ARTICLE_ID
        and article.get("title") == payload.get("title")
        and article.get("description") == payload.get("description")
        # Figshare normalizes reference ordering on publication. The visible
        # description retains the controlling six-link order, while references
        # are verified as an exact set.
        and set(article.get("references") or []) == set(payload.get("references") or [])
        and int(license_item.get("value", -1)) == CC0_LICENSE_ID
        and str(license_item.get("name", "")).upper() == "CC0"
        and files_match(list(article.get("files") or []), expected[:1])
    )


def project_storage(client: Http, project: dict[str, Any] | None = None) -> dict[str, Any]:
    if project is None:
        project = client.json("GET", f"account/projects/{PROJECT_ID}")
    if not isinstance(project, dict) or int(project.get("id", -1)) != PROJECT_ID:
        raise RuntimeError("authenticated Figshare project quota identity mismatch")
    articles = client.json(
        "GET", f"account/projects/{PROJECT_ID}/articles?page_size=1000"
    )
    if not isinstance(articles, list):
        raise RuntimeError("Figshare project article inventory is not a list")
    used_quota = int(project.get("used_quota") or 0)
    used_quota_public = int(project.get("used_quota_public") or 0)
    used_quota_private = int(project.get("used_quota_private") or 0)
    hosted_bytes = max(used_quota, used_quota_public, used_quota_private)
    return {
        "article_count": len(articles),
        "used_quota": used_quota,
        "used_quota_public": used_quota_public,
        "used_quota_private": used_quota_private,
        "hosted_bytes": hosted_bytes,
        "limit_bytes": PROJECT_HOSTED_LIMIT_BYTES,
        "below_limit": hosted_bytes < PROJECT_HOSTED_LIMIT_BYTES,
        "contains_article": ARTICLE_ID in {int(item["id"]) for item in articles},
    }


def wait_for_public_article(
    anonymous: Http, payload: dict[str, Any], expected: list[dict[str, Any]]
) -> dict[str, Any]:
    last: dict[str, Any] | None = None
    for _ in range(12):
        candidate = anonymous.json("GET", f"articles/{ARTICLE_ID}")
        if isinstance(candidate, dict):
            last = candidate
            if public_article_matches(candidate, payload, expected):
                return candidate
        time.sleep(2)
    version = None if last is None else last.get("version")
    raise RuntimeError(
        f"public Figshare article did not converge to B006; last version={version}"
    )


def anonymous_link_readback(
    anonymous: Http,
    public_article: dict[str, Any],
    public_files: list[dict[str, Any]],
    expected: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not files_match(public_files, expected[:1]):
        raise RuntimeError("public Figshare primary file is not the planned PDF")
    description = str(public_article.get("description", ""))
    references = list(public_article.get("references") or [])
    verified: list[dict[str, Any]] = []
    for index, planned in enumerate(expected):
        if planned["url"] not in description or planned["url"] not in references:
            raise RuntimeError(
                f"public Figshare metadata omits the link for {planned['filename']}"
            )
        observed = public_files[0] if index == 0 else None
        download_url = planned["url"] if observed is None else observed["download_url"]
        digest = hashlib.sha256()
        byte_count = 0
        with anonymous.session.get(
            str(download_url), stream=True, timeout=180
        ) as response:
            response.raise_for_status()
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    digest.update(chunk)
                    byte_count += len(chunk)
        if byte_count != int(planned["bytes"]) or digest.hexdigest() != planned["sha256"]:
            raise RuntimeError(
                f"anonymous linked-file byte/SHA readback failed for {planned['filename']}"
            )
        verified.append(
            {
                "position": int(planned["position"]),
                "role": planned["role"],
                "figshare_surface": (
                    "primary_external_file" if observed is not None else "metadata_link"
                ),
                "file_id": None if observed is None else int(observed["id"]),
                "filename": planned["filename"],
                "bytes": byte_count,
                "sha256": digest.hexdigest(),
                "download_url": download_url,
                "figshare_reported_bytes": (
                    None if observed is None else observed.get("size")
                ),
                "is_link_only": None if observed is None else True,
                "visible_description_link_readback": "passed",
                "references_link_readback": "passed",
                "anonymous_size_sha256_readback": "passed",
            }
        )
    return verified


def main() -> int:
    zenodo, payload, plan = validate_inputs()
    expected_files = list(plan["ordered_external_files"])
    token = read_token()
    client = Http(token)
    token = ""
    anonymous = Http()

    licenses = client.json("GET", "account/licenses")
    if not isinstance(licenses, list):
        raise RuntimeError("Figshare account license inventory is not a list")
    if exact_by_sa_30(licenses):
        raise RuntimeError(
            "Figshare now offers exact CC BY-SA 3.0; refusing the CC0 external-link "
            "route so exact-license byte mirroring can be evaluated instead"
        )
    cc0 = [item for item in licenses if int(item.get("value", -1)) == CC0_LICENSE_ID]
    if len(cc0) != 1 or str(cc0[0].get("name", "")).upper() != "CC0":
        raise RuntimeError("Figshare CC0 license identity is unavailable or ambiguous")

    project = client.json("GET", f"account/projects/{PROJECT_ID}")
    collection_before = client.json("GET", f"account/collections/{COLLECTION_ID}")
    if not isinstance(project, dict) or int(project.get("id", -1)) != PROJECT_ID:
        raise RuntimeError("authenticated Figshare project identity mismatch")
    if not isinstance(collection_before, dict) or int(
        collection_before.get("id", -1)
    ) != COLLECTION_ID:
        raise RuntimeError("authenticated Figshare collection identity mismatch")

    storage_before = project_storage(client, project)
    if not storage_before["contains_article"]:
        raise RuntimeError(
            "existing Figshare article 33314727 is not associated with project 280296"
        )
    if not storage_before["below_limit"]:
        raise RuntimeError("Figshare project is not below the 20,000,000,000-byte cap")

    public_before = anonymous.json("GET", f"articles/{ARTICLE_ID}")
    if not isinstance(public_before, dict) or int(public_before.get("id", -1)) != ARTICLE_ID:
        raise RuntimeError("anonymous existing Figshare article identity mismatch")
    prior_version = int(public_before.get("version", 0))
    article_mutated = not public_article_matches(public_before, payload, expected_files)
    article_publish_location: str | None = None

    if article_mutated:
        client.request(
            "PUT",
            f"account/articles/{ARTICLE_ID}",
            payload=payload,
            expected=(200, 205),
        )
        private_files = client.json("GET", f"account/articles/{ARTICLE_ID}/files")
        if not isinstance(private_files, list):
            raise RuntimeError("Figshare private file inventory is not a list")
        for file_item in private_files:
            client.request(
                "DELETE",
                f"account/articles/{ARTICLE_ID}/files/{int(file_item['id'])}",
                expected=(204,),
            )
        for planned in expected_files[:1]:
            response = client.request(
                "POST",
                f"account/articles/{ARTICLE_ID}/files",
                payload={"link": planned["url"]},
                expected=(201,),
            )
            location = response_location(response)
            created = client.json("GET", location)
            if (
                not isinstance(created, dict)
                or created.get("name") != planned["filename"]
                or created.get("download_url") != planned["url"]
                or not bool(created.get("is_link_only"))
            ):
                raise RuntimeError(
                    f"Figshare linked-file creation mismatch for {planned['filename']}"
                )
        private_files_after = client.json(
            "GET", f"account/articles/{ARTICLE_ID}/files"
        )
        if not isinstance(private_files_after, list) or not files_match(
            private_files_after, expected_files[:1]
        ):
            raise RuntimeError("Figshare private primary linked-file mismatch")
        publish_response = client.request(
            "POST", f"account/articles/{ARTICLE_ID}/publish", expected=(201,)
        )
        article_publish_location = response_location(publish_response)

    public_article = wait_for_public_article(anonymous, payload, expected_files)

    collection_articles = client.json(
        "GET", f"account/collections/{COLLECTION_ID}/articles?page_size=1000"
    )
    if not isinstance(collection_articles, list):
        raise RuntimeError("Figshare collection article inventory is not a list")
    collection_association_added = ARTICLE_ID not in {
        int(item["id"]) for item in collection_articles
    }
    collection_publish_location: str | None = None
    if collection_association_added:
        client.request(
            "POST",
            f"account/collections/{COLLECTION_ID}/articles",
            payload={"articles": [ARTICLE_ID]},
            expected=(201,),
        )
        collection_publish_response = client.request(
            "POST", f"account/collections/{COLLECTION_ID}/publish", expected=(201,)
        )
        collection_publish_location = response_location(collection_publish_response)

    public_project_articles = anonymous.json(
        "GET", f"projects/{PROJECT_ID}/articles?page_size=1000"
    )
    if ARTICLE_ID not in {int(item["id"]) for item in public_project_articles}:
        raise RuntimeError("anonymous project readback does not include article 33314727")

    public_collection_articles: list[dict[str, Any]] | None = None
    for _ in range(12):
        candidate = anonymous.json(
            "GET", f"collections/{COLLECTION_ID}/articles?page_size=1000"
        )
        if isinstance(candidate, list):
            public_collection_articles = candidate
            if ARTICLE_ID in {int(item["id"]) for item in candidate}:
                break
        time.sleep(2)
    if public_collection_articles is None or ARTICLE_ID not in {
        int(item["id"]) for item in public_collection_articles
    }:
        raise RuntimeError("anonymous collection readback does not include article 33314727")

    public_collection = anonymous.json("GET", f"collections/{COLLECTION_ID}")
    if not isinstance(public_collection, dict) or int(
        public_collection.get("id", -1)
    ) != COLLECTION_ID:
        raise RuntimeError("anonymous collection identity readback mismatch")

    verified_files = anonymous_link_readback(
        anonymous,
        public_article,
        list(public_article.get("files") or []),
        expected_files,
    )
    storage_after = project_storage(client)
    if not storage_after["below_limit"]:
        raise RuntimeError("Figshare project exceeded its hosted-byte cap after update")

    receipt = {
        "schema": "interlanguage.figshare-publication-receipt",
        "schema_version": "1.1.0",
        "status": "published_and_anonymously_verified",
        "boundary_id": "R011-B006",
        "complete_corpus": False,
        "publication_route": (
            "cc0_metadata_record_with_one_primary_external_file_and_five_metadata_links"
        ),
        "platform_constraint": plan["platform_constraint"],
        "license_boundary": (
            "CC0 applies only to Figshare metadata and link pointers. Linked work "
            "bytes remain under CC BY-SA 3.0 and component-specific rights recorded "
            "in the linked Zenodo LICENSES_AND_ATTRIBUTION.md; Figshare does not host "
            "or relicense those bytes."
        ),
        "article": {
            "id": ARTICLE_ID,
            "title": public_article.get("title"),
            "doi": public_article.get("doi"),
            "url": public_article.get("url_public_html"),
            "api_url": public_article.get("url_public_api"),
            "license": public_article.get("license"),
            "defined_type": public_article.get("defined_type_name"),
            "prior_public_version": prior_version,
            "public_version": public_article.get("version"),
            "mutated_in_this_run": article_mutated,
            "publish_location": article_publish_location,
            "reader_first": True,
        },
        "project": {
            "id": PROJECT_ID,
            "url": (
                "https://figshare.com/projects/"
                "Open_and_Share-Alike_Educational_Materials_Translations/280296"
            ),
            "anonymous_membership_readback": "passed",
            "storage_before": storage_before,
            "storage_after": storage_after,
        },
        "collection": {
            "id": COLLECTION_ID,
            "title": public_collection.get("title"),
            "doi": public_collection.get("doi"),
            "url": public_collection.get("url_public_html"),
            "version": public_collection.get("version"),
            "association_added_in_this_run": collection_association_added,
            "publish_location": collection_publish_location,
            "anonymous_membership_readback": "passed",
        },
        "zenodo_target": {
            "record_id": int(zenodo["record_id"]),
            "record_url": zenodo["record_url"],
            "doi": zenodo["doi"],
            "concept_doi": zenodo["concept_doi"],
            "receipt": identity(ZENODO_RECEIPT),
        },
        "logical_payload": {
            "bytes": int(plan["logical_payload_bytes"]),
            "limit_bytes": PAYLOAD_LIMIT_BYTES,
            "below_limit": int(plan["logical_payload_bytes"]) <= PAYLOAD_LIMIT_BYTES,
            "file_count": len(verified_files),
        },
        "ordered_external_files": verified_files,
        "local_inputs": {
            "article_payload": identity(PAYLOAD_FILE),
            "link_plan": identity(LINK_PLAN_FILE),
        },
        "anonymous_article_metadata_readback": "passed",
        "anonymous_reader_first_link_order_readback": "passed",
        "anonymous_linked_file_size_sha256_readback": "passed",
        "credentials_persisted": False,
    }
    preserve_existing_receipt = False
    if RECEIPT_FILE.exists():
        existing_receipt = json.loads(RECEIPT_FILE.read_text(encoding="utf-8"))
        existing_files = list(existing_receipt.get("ordered_external_files") or [])
        preserve_existing_receipt = (
            existing_receipt.get("status") == "published_and_anonymously_verified"
            and existing_receipt.get("boundary_id") == "R011-B006"
            and int((existing_receipt.get("article") or {}).get("id", -1)) == ARTICLE_ID
            and (existing_receipt.get("article") or {}).get("doi")
            == public_article.get("doi")
            and (existing_receipt.get("zenodo_target") or {}).get("doi")
            == zenodo.get("doi")
            and int((existing_receipt.get("logical_payload") or {}).get("bytes", -1))
            == int(plan["logical_payload_bytes"])
            and [
                (item.get("position"), item.get("download_url"), item.get("sha256"))
                for item in existing_files
            ]
            == [
                (item.get("position"), item.get("download_url"), item.get("sha256"))
                for item in verified_files
            ]
        )
        if preserve_existing_receipt:
            receipt = existing_receipt
    if not preserve_existing_receipt:
        raw_receipt = canonical_json(receipt)
        RECEIPT_FILE.write_bytes(raw_receipt)
        if RECEIPT_FILE.read_bytes() != raw_receipt:
            raise RuntimeError("Figshare receipt write/readback mismatch")
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "article_id": ARTICLE_ID,
                "article_doi": receipt["article"]["doi"],
                "article_url": receipt["article"]["url"],
                "article_version": receipt["article"]["public_version"],
                "collection_doi": receipt["collection"]["doi"],
                "collection_version": receipt["collection"]["version"],
                "ordered_external_file_count": len(verified_files),
                "logical_payload_bytes": receipt["logical_payload"]["bytes"],
                "project_hosted_bytes": storage_after["hosted_bytes"],
                "receipt": identity(RECEIPT_FILE),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
