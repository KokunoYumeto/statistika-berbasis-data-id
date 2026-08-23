#!/usr/bin/env python3
"""Shared, fail-closed helpers for the R011-B008 preservation release.

Importing this module performs no I/O, network access, credential access, Git
operation, packaging, or publication.  Every mutating entry point must first
call :func:`execution_preflight`.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


BOUNDARY_ID = "R011-B008"
RELEASE_ID = "R011-B008-v2026.08.23.2"
MODEL = "OpenAI Codex gpt-5.6-sol, Ultra"
REPO_ROOT = Path(__file__).resolve().parent.parent
RELEASE_DIR = REPO_ROOT / "release" / "b008" / RELEASE_ID
CONFIG_PATH = RELEASE_DIR / "RELEASE_INPUTS.json"
EXCLUDED_SOURCE_PATH = (
    "ch_intro_to_data/figures/eoce/migraine_and_acupuncture_intro/"
    "earacupuncture.pdf"
)
FIXED_ZIP_TIME = (2026, 8, 23, 0, 0, 0)


class ReleaseGateError(RuntimeError):
    """A release invariant is absent or false."""


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def identity(path: Path) -> dict[str, Any]:
    if not path.is_file():
        try:
            label = path.relative_to(REPO_ROOT).as_posix()
        except ValueError:
            label = path.name
        raise ReleaseGateError(f"required file is absent: {label}")
    try:
        label = path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        label = path.name
    return {
        "path": label,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReleaseGateError(f"invalid JSON {path}: {exc}") from exc


def load_config() -> dict[str, Any]:
    value = load_json(CONFIG_PATH)
    if not isinstance(value, dict):
        raise ReleaseGateError("release config must be a JSON object")
    return value


def repo_path(relative: str) -> Path:
    if not isinstance(relative, str) or not relative.strip():
        raise ReleaseGateError("relative path is empty")
    token = relative.replace("\\", "/")
    pure = PurePosixPath(token)
    if pure.is_absolute() or ".." in pure.parts or re.match(r"^[A-Za-z]:", token):
        raise ReleaseGateError(f"unsafe repository-relative path: {relative!r}")
    candidate = (REPO_ROOT / Path(*pure.parts)).resolve()
    try:
        candidate.relative_to(REPO_ROOT)
    except ValueError as exc:
        raise ReleaseGateError(f"path escapes repository: {relative!r}") from exc
    return candidate


def dotted_get(value: Any, dotted: str) -> Any:
    cursor = value
    for part in dotted.split("."):
        if not isinstance(cursor, dict) or part not in cursor:
            raise ReleaseGateError(f"missing required JSON field: {dotted}")
        cursor = cursor[part]
    return cursor


def verify_record(record: dict[str, Any], *, role: str) -> dict[str, Any]:
    required = ("path", "bytes", "sha256")
    if any(record.get(key) is None for key in required):
        raise ReleaseGateError(f"{role} identity is unresolved")
    path = repo_path(record["path"])
    actual = identity(path)
    for key in ("bytes", "sha256"):
        if actual[key] != record[key]:
            raise ReleaseGateError(
                f"{role} {key} mismatch: expected {record[key]!r}, got {actual[key]!r}"
            )
    required_fields = record.get("required_fields")
    if required_fields is not None:
        if not isinstance(required_fields, dict) or not required_fields:
            raise ReleaseGateError(f"{role} required_fields must be a nonempty object")
        payload = load_json(path)
        for field, expected in required_fields.items():
            actual_value = dotted_get(payload, field)
            if actual_value != expected:
                raise ReleaseGateError(
                    f"{role} field {field!r}: expected {expected!r}, got {actual_value!r}"
                )
    return actual


def verify_accepted_v3(config: dict[str, Any]) -> list[dict[str, Any]]:
    accepted = config.get("accepted_v3")
    if not isinstance(accepted, dict):
        raise ReleaseGateError("accepted_v3 object is absent")
    verified: list[dict[str, Any]] = []
    for key in (
        "source_manifest",
        "source_qa",
        "candidate_pdf",
        "build_receipt",
        "build_visual_sanity",
        "root_visual_audit",
    ):
        record = accepted.get(key)
        if not isinstance(record, dict):
            raise ReleaseGateError(f"accepted_v3.{key} is absent")
        verified.append(verify_record(record, role=f"accepted_v3.{key}"))

    snapshot = accepted.get("source_snapshot")
    if not isinstance(snapshot, dict):
        raise ReleaseGateError("accepted_v3.source_snapshot is absent")
    manifest_record = {
        "path": snapshot.get("manifest_path"),
        "bytes": snapshot.get("manifest_bytes"),
        "sha256": snapshot.get("manifest_sha256"),
    }
    verified.append(verify_record(manifest_record, role="accepted_v3.source_snapshot manifest"))
    if snapshot["manifest_sha256"] != accepted["source_manifest"]["sha256"]:
        raise ReleaseGateError("snapshot and source manifests do not have the same identity")
    if snapshot["manifest_bytes"] != accepted["source_manifest"]["bytes"]:
        raise ReleaseGateError("snapshot and source manifest byte counts differ")
    root = repo_path(snapshot["root"])
    if not root.is_dir():
        raise ReleaseGateError("accepted V3 source snapshot directory is absent")

    build = load_json(repo_path(accepted["build_receipt"]["path"]))
    candidate = accepted["candidate_pdf"]
    if dotted_get(build, "determinism.pass_3.sha256") != candidate["sha256"]:
        raise ReleaseGateError("build pass 3 does not bind the accepted PDF")
    if dotted_get(build, "determinism.pass_4.sha256") != candidate["sha256"]:
        raise ReleaseGateError("build pass 4 does not bind the accepted PDF")
    return verified


def validate_config_shape(config: dict[str, Any]) -> None:
    exact = {
        "$schema": "r011-b008-release-inputs/v1",
        "boundary_id": BOUNDARY_ID,
        "release_id": RELEASE_ID,
        "version_label": "v2026.08.23.2",
        "version": "2026.08.23.2-R011-B008",
        "model_identification": MODEL,
        "license": "CC BY-SA 3.0 Unported",
        "license_id": "cc-by-sa-3.0",
    }
    for field, expected in exact.items():
        if config.get(field) != expected:
            raise ReleaseGateError(f"config {field}: expected {expected!r}")
    if config.get("status") not in {"UNRESOLVED_ADMISSION_INPUTS", "READY_FOR_PACKAGING"}:
        raise ReleaseGateError("unrecognized release config status")
    rules = config.get("publication_rules", {})
    for key in (
        "reader_first",
        "no_upstream_contact",
        "no_user_first_name",
        "preserve_full_credits",
        "exact_model_string_required",
        "execute_requires_all_terminal_inputs",
        "remote_collision_check_required",
        "anonymous_byte_readback_required",
    ):
        if rules.get(key) is not True:
            raise ReleaseGateError(f"publication rule {key} must be true")

    destinations = config.get("destinations", {})
    if destinations.get("zenodo", {}).get("concept_doi") != "10.5281/zenodo.22059801":
        raise ReleaseGateError("wrong Zenodo concept")
    if destinations.get("figshare", {}).get("article_id") != 33314727:
        raise ReleaseGateError("wrong Figshare article")
    if destinations.get("figshare", {}).get("project_id") != 280296:
        raise ReleaseGateError("wrong Figshare project")
    if destinations.get("figshare", {}).get("collection_id") != 8668413:
        raise ReleaseGateError("wrong Figshare collection")
    github = destinations.get("github", {})
    if (github.get("owner"), github.get("repository")) != (
        "KokunoYumeto",
        "statistika-berbasis-data-id",
    ):
        raise ReleaseGateError("wrong GitHub repository")
    if github.get("tag") != "r011-b008-2026.08.23.2":
        raise ReleaseGateError("wrong GitHub tag")

    assets = config.get("ordered_release_assets")
    expected_assets = [
        "00_STATISTIKA_BERBASIS_DATA_ID_R011-B008_WORKING_READER.pdf",
        "01_STATISTIKA_BERBASIS_DATA_ID_R011-B008_EDITABLE_SOURCE.zip",
        "02_STATISTIKA_BERBASIS_DATA_ID_R011-B008_MODULAR_BACKEND.zip",
        "CITATION.cff",
        "LICENSES_AND_ATTRIBUTION.md",
        "README_RELEASE.md",
        "RELEASE_MANIFEST.json",
        "SHA256SUMS.txt",
        "ZENODO_METADATA.json",
    ]
    if assets != expected_assets:
        raise ReleaseGateError("ordered release assets or reader-first order changed")


def unresolved_terminal_inputs(config: dict[str, Any]) -> list[str]:
    terminal = config.get("terminal_inputs")
    if not isinstance(terminal, dict) or not terminal:
        raise ReleaseGateError("terminal_inputs object is absent")
    unresolved: list[str] = []
    for name, record in terminal.items():
        if not isinstance(record, dict) or record.get("required") is not True:
            raise ReleaseGateError(f"terminal input {name} must be an explicit required object")
        if any(record.get(key) is None for key in ("path", "bytes", "sha256")):
            unresolved.append(name)
    return sorted(unresolved)


def directory_inventory(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not path.is_dir():
        raise ReleaseGateError(f"required directory is absent: {path.relative_to(REPO_ROOT)}")
    rows: list[dict[str, Any]] = []
    lines: list[str] = []
    total = 0
    for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
        relative = item.relative_to(path).as_posix()
        size = item.stat().st_size
        digest = sha256_file(item)
        rows.append(
            {
                "path": item.relative_to(REPO_ROOT).as_posix(),
                "relative": relative,
                "bytes": size,
                "sha256": digest,
                "source": item,
            }
        )
        lines.append(f"{relative}\t{size}\t{digest}\n")
        total += size
    digest = hashlib.sha256("".join(lines).encode("utf-8")).hexdigest()
    return {"path": path.relative_to(REPO_ROOT).as_posix(), "file_count": len(rows), "bytes": total, "sha256": digest}, rows


def verify_terminal_record(name: str, record: dict[str, Any]) -> dict[str, Any]:
    if name != "backend_inventory":
        return verify_record(record, role=f"terminal_inputs.{name}")
    if record.get("identity_kind") != "directory-inventory-tsv-sha256/v1":
        raise ReleaseGateError("backend inventory lacks the exact directory identity algorithm")
    if any(record.get(key) is None for key in ("path", "file_count", "bytes", "sha256")):
        raise ReleaseGateError("backend inventory identity is unresolved")
    actual, _ = directory_inventory(repo_path(record["path"]))
    for key in ("file_count", "bytes", "sha256"):
        if actual[key] != record[key]:
            raise ReleaseGateError(
                f"terminal_inputs.backend_inventory {key} mismatch: expected {record[key]!r}, got {actual[key]!r}"
            )
    return actual


def assert_public_text_safe(text: str, *, role: str) -> None:
    forbidden = [
        "C:\\Users\\",
        "/Users/",
        str(Path.home()),
        Path.home().name,
    ]
    for token in forbidden:
        if token and token.casefold() in text.casefold():
            raise ReleaseGateError(f"{role} contains a local profile identifier")
    secret_patterns = (
        r"(?i)(?:github|zenodo|figshare)[_-]?token\s*[:=]\s*\S+",
        r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b",
        r"\b[a-f0-9]{64}\.[A-Za-z0-9_-]{20,}\b",
    )
    for pattern in secret_patterns:
        if re.search(pattern, text):
            raise ReleaseGateError(f"{role} resembles credential material")


def template_paths() -> list[Path]:
    return [
        RELEASE_DIR / "README_RELEASE.template.md",
        RELEASE_DIR / "LICENSES_AND_ATTRIBUTION.template.md",
        RELEASE_DIR / "CITATION.template.cff",
        RELEASE_DIR / "ZENODO_METADATA.template.json",
        RELEASE_DIR / "FIGSHARE_METADATA.template.json",
        RELEASE_DIR / "GITHUB_PUBLICATION_POLICY.json",
        RELEASE_DIR / "PUBLICATION_PLAN.md",
    ]


def validate_templates(config: dict[str, Any]) -> list[str]:
    checked: list[str] = []
    combined = ""
    for path in template_paths():
        if not path.is_file():
            raise ReleaseGateError(f"release template absent: {path.name}")
        text = path.read_text(encoding="utf-8")
        assert_public_text_safe(text, role=path.name)
        combined += "\n" + text
        checked.append(path.relative_to(REPO_ROOT).as_posix())
        if path.suffix == ".json":
            load_json(path)
    for needle in (
        MODEL,
        "CC BY-SA 3.0",
        "David M. Diez",
        "Mine Çetinkaya-Rundel",
        "Christopher D. Barr",
        "belum lengkap",
    ):
        if needle not in combined:
            raise ReleaseGateError(f"release templates omit required truth/credit: {needle}")
    if "no upstream contact" not in combined.casefold():
        raise ReleaseGateError("release plan does not expressly prohibit upstream contact")
    return checked


def static_self_check(*, component: str) -> dict[str, Any]:
    config = load_config()
    validate_config_shape(config)
    accepted = verify_accepted_v3(config)
    templates = validate_templates(config)
    unresolved = unresolved_terminal_inputs(config)
    verified_terminal: dict[str, dict[str, Any]] = {}
    if unresolved:
        if config.get("status") != "UNRESOLVED_ADMISSION_INPUTS":
            raise ReleaseGateError("config falsely claims readiness while terminal identities are unresolved")
        status = "PASS_INERT_FAIL_CLOSED"
    else:
        if config.get("status") != "READY_FOR_PACKAGING":
            raise ReleaseGateError("resolved terminal identities lack READY_FOR_PACKAGING status")
        for name, record in config["terminal_inputs"].items():
            verified_terminal[name] = verify_terminal_record(name, record)
        accepted_pdf = config["accepted_v3"]["candidate_pdf"]
        promoted = config["terminal_inputs"]["promoted_pdf"]
        if (promoted["bytes"], promoted["sha256"]) != (
            accepted_pdf["bytes"], accepted_pdf["sha256"]
        ):
            raise ReleaseGateError("promoted PDF is not byte-identical to accepted V3 PDF")
        status = "PASS_READY_NO_EXECUTION"
    return {
        "schema": "r011-b008-release-toolchain-self-check/v1",
        "component": component,
        "boundary_id": BOUNDARY_ID,
        "release_id": RELEASE_ID,
        "status": status,
        "accepted_v3_identities_verified": len(accepted),
        "templates_verified": templates,
        "terminal_inputs_unresolved": unresolved,
        "terminal_inputs_verified": sorted(verified_terminal),
        "network_used": False,
        "credentials_read": False,
        "git_used": False,
        "package_created": False,
        "publication_performed": False,
    }


def execution_preflight(*, component: str) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    config = load_config()
    validate_config_shape(config)
    verify_accepted_v3(config)
    validate_templates(config)
    unresolved = unresolved_terminal_inputs(config)
    if unresolved:
        raise ReleaseGateError(
            f"{component} refused: unresolved terminal inputs: {', '.join(unresolved)}"
        )
    if config.get("status") != "READY_FOR_PACKAGING":
        raise ReleaseGateError(f"{component} refused: status is not READY_FOR_PACKAGING")

    verified: dict[str, dict[str, Any]] = {}
    for name, record in config["terminal_inputs"].items():
        verified[name] = verify_terminal_record(name, record)
        if name in {
            "boundary_receipt",
            "backend_validation_receipt",
            "admission_receipt",
            "post_admission_verification",
        } and not record.get("required_fields"):
            raise ReleaseGateError(f"{name} lacks explicit semantic field assertions")

    accepted_pdf = config["accepted_v3"]["candidate_pdf"]
    promoted = config["terminal_inputs"]["promoted_pdf"]
    if (promoted["bytes"], promoted["sha256"]) != (
        accepted_pdf["bytes"],
        accepted_pdf["sha256"],
    ):
        raise ReleaseGateError("promoted PDF is not byte-identical to accepted V3 PDF")
    if component != "packager":
        manifest_path = RELEASE_DIR / "RELEASE_MANIFEST.json"
        if not manifest_path.is_file():
            raise ReleaseGateError(f"{component} refused: package manifest is absent")
        verify_release_package(config)
    return config, verified


def read_snapshot_manifest(config: dict[str, Any]) -> list[dict[str, Any]]:
    snapshot = config["accepted_v3"]["source_snapshot"]
    root = repo_path(snapshot["root"])
    manifest = repo_path(snapshot["manifest_path"])
    entries: list[dict[str, Any]] = []
    total = 0
    seen: set[str] = set()
    for line_number, line in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
        parts = line.split("\t")
        if len(parts) != 3:
            raise ReleaseGateError(f"invalid source manifest row {line_number}")
        rel, size_text, sha = parts
        safe = PurePosixPath(rel)
        if safe.is_absolute() or ".." in safe.parts or rel in seen:
            raise ReleaseGateError(f"unsafe/duplicate source manifest path: {rel}")
        seen.add(rel)
        source = (root / Path(*safe.parts)).resolve()
        try:
            source.relative_to(root.resolve())
        except ValueError as exc:
            raise ReleaseGateError(f"source snapshot path escapes root: {rel}") from exc
        expected_size = int(size_text)
        actual = identity(source)
        if actual["bytes"] != expected_size or actual["sha256"] != sha:
            raise ReleaseGateError(f"source snapshot identity mismatch: {rel}")
        entries.append({"path": rel, "bytes": expected_size, "sha256": sha, "source": source})
        total += expected_size
    if len(entries) != snapshot["expected_files"] or total != snapshot["expected_bytes"]:
        raise ReleaseGateError("source snapshot count/byte closure mismatch")
    return entries


def read_backend_inventory(config: dict[str, Any]) -> list[dict[str, Any]]:
    inventory_record = config["terminal_inputs"]["backend_inventory"]
    actual, rows = directory_inventory(repo_path(inventory_record["path"]))
    for key in ("file_count", "bytes", "sha256"):
        if actual[key] != inventory_record[key]:
            raise ReleaseGateError(f"live backend inventory changed at {key}")

    manifest_record = config["terminal_inputs"]["backend_manifest"]
    verify_record(manifest_record, role="terminal_inputs.backend_manifest")
    manifest = load_json(repo_path(manifest_record["path"]))
    declared = manifest.get("files")
    if not isinstance(declared, list) or not declared:
        raise ReleaseGateError("live backend manifest contains no exact file inventory")
    root_prefix = repo_path(inventory_record["path"])
    expected_by_relative = {row["relative"]: row for row in rows}
    if "manifest.json" not in expected_by_relative:
        raise ReleaseGateError("live backend inventory omits its manifest")
    declared_paths: set[str] = set()
    for record in declared:
        relative = record.get("path")
        if not isinstance(relative, str) or relative in declared_paths:
            raise ReleaseGateError("backend manifest has an unsafe/duplicate file path")
        declared_paths.add(relative)
        observed = expected_by_relative.get(relative)
        if observed is None:
            raise ReleaseGateError(f"backend manifest path is absent live: {relative}")
        if observed["bytes"] != record.get("bytes") or observed["sha256"] != record.get("sha256"):
            raise ReleaseGateError(f"backend manifest identity mismatch: {relative}")
    if declared_paths | {"manifest.json"} != set(expected_by_relative):
        raise ReleaseGateError("live backend has files outside its exact manifest closure")
    return sorted(rows, key=lambda row: row["relative"].encode("utf-8"))


def deterministic_zip(destination: Path, rows: Iterable[tuple[str, Path]]) -> dict[str, Any]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(rows, key=lambda item: item[0].encode("utf-8"))
    if destination.exists():
        destination.unlink()
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for archive_name, source in ordered:
            data = source.read_bytes()
            info = zipfile.ZipInfo(archive_name, FIXED_ZIP_TIME)
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    with zipfile.ZipFile(destination, "r") as archive:
        if archive.testzip() is not None:
            raise ReleaseGateError(f"ZIP CRC verification failed: {destination.name}")
        if archive.namelist() != [name for name, _ in ordered]:
            raise ReleaseGateError(f"ZIP inventory/order mismatch: {destination.name}")
    return identity(destination)


def render_template(path: Path, replacements: dict[str, str]) -> bytes:
    text = path.read_text(encoding="utf-8")
    for key, value in replacements.items():
        text = text.replace("{{" + key + "}}", value)
    remaining = sorted(set(re.findall(r"\{\{[A-Z0-9_]+\}\}", text)))
    if remaining:
        raise ReleaseGateError(f"unresolved template tokens in {path.name}: {remaining}")
    assert_public_text_safe(text, role=path.name)
    return text.encode("utf-8")


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        Path(temporary_name).replace(path)
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def release_assets(config: dict[str, Any]) -> list[Path]:
    return [RELEASE_DIR / name for name in config["ordered_release_assets"]]


def verify_release_package(config: dict[str, Any]) -> dict[str, Any]:
    paths = release_assets(config)
    for path in paths:
        if not path.is_file():
            raise ReleaseGateError(f"release asset absent: {path.name}")
    if paths[0].suffix.lower() != ".pdf" or not paths[0].name.startswith("00_"):
        raise ReleaseGateError("reader is not the first release asset")
    manifest = load_json(RELEASE_DIR / "RELEASE_MANIFEST.json")
    if manifest.get("boundary_id") != BOUNDARY_ID or manifest.get("status") != "PACKAGED_VERIFIED":
        raise ReleaseGateError("release manifest is not a verified B008 package")
    ordered = manifest.get("ordered_assets")
    if ordered != config["ordered_release_assets"]:
        raise ReleaseGateError("release manifest asset order mismatch")
    rows = manifest.get("files")
    expected_hashed_names = config["ordered_release_assets"][:6] + [config["ordered_release_assets"][8]]
    if not isinstance(rows, list) or [row.get("filename") for row in rows] != expected_hashed_names:
        raise ReleaseGateError("release manifest hashed-file inventory mismatch")
    hashed_paths = paths[:6] + [paths[8]]
    for row, path in zip(rows, hashed_paths):
        actual = identity(path)
        if actual["bytes"] != row.get("bytes") or actual["sha256"] != row.get("sha256"):
            raise ReleaseGateError(f"release asset identity mismatch: {path.name}")
    sums = (RELEASE_DIR / "SHA256SUMS.txt").read_text(encoding="utf-8")
    assert_public_text_safe(sums, role="SHA256SUMS.txt")
    expected_sums = "".join(f"{row['sha256']}  {row['filename']}\n" for row in rows)
    if sums != expected_sums:
        raise ReleaseGateError("SHA256SUMS does not match the manifest inventory")
    if sum(path.stat().st_size for path in paths) > config["destinations"]["figshare"]["max_item_bytes"]:
        raise ReleaseGateError("release payload exceeds the per-work Figshare cap")
    return manifest


def sanitized_receipt_path(destination: str) -> Path:
    table = {
        "zenodo": REPO_ROOT / "qa" / "b008-zenodo" / f"ZENODO_PUBLICATION_RECEIPT_{RELEASE_ID}.json",
        "figshare": RELEASE_DIR / "FIGSHARE_PUBLICATION_RECEIPT.json",
        "github": RELEASE_DIR / "GITHUB_PUBLICATION_RECEIPT.json",
    }
    try:
        return table[destination]
    except KeyError as exc:
        raise ReleaseGateError(f"unknown publication destination: {destination}") from exc


def token_from_file(path: Path, *, service: str) -> str:
    """Read a credential only in an authorized execute branch; never print it."""
    if not path.is_file():
        raise ReleaseGateError(f"{service} credential file is absent")
    text = path.read_text(encoding="utf-8", errors="strict")
    patterns = {
        "zenodo": r"\b[A-Za-z0-9._~-]{40,}\b",
        "figshare": r"\b[A-Za-z0-9._~-]{40,}\b",
        "github": r"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b",
    }
    candidates = sorted(set(re.findall(patterns[service], text, re.IGNORECASE)), key=len, reverse=True)
    if len(candidates) != 1:
        raise ReleaseGateError(f"no parseable {service} token found")
    return candidates[0]


def public_session():
    import requests

    session = requests.Session()
    session.trust_env = False
    session.headers.update({"User-Agent": "interlanguage-r011-b008-preservation/1"})
    return session


def emit_self_check(component: str) -> int:
    print(json.dumps(static_self_check(component=component), ensure_ascii=False, sort_keys=True))
    return 0
