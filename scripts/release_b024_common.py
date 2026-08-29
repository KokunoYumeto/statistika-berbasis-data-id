#!/usr/bin/env python3
"""Fail-closed, offline release primitives for the R011-B024 checkpoint.

This module is bounded to the OpenIntro Statistics Indonesian lane.  It never
reads credentials, invokes Git, performs network I/O, or mutates backend/control
state.  Publication scripts may import it, but authenticated work is reachable
only through their explicit ``--publish`` modes.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

sys.dont_write_bytecode = True


BOUNDARY_ID = "R011-B024"
RELEASE_ID = "R011-B024-v2026.08.29.3"
VERSION = "2026.08.29.3-R011-B024"
VERSION_LABEL = "v2026.08.29.3"
GITHUB_TAG = "r011-b024-2026.08.29.3"
RELEASE_DATE = "2026-08-29"
MODEL = "OpenAI Codex gpt-5.6-sol, Ultra"

REPO_ROOT = Path(__file__).resolve().parent.parent
RELEASE_DIR = REPO_ROOT / "release" / "b024" / RELEASE_ID
CONFIG_PATH = RELEASE_DIR / "RELEASE_INPUTS.json"

CANDIDATE_READER_PATH = "scratch/b024-boundary-clean-reader/final/main.pdf"
FINAL_READER_PATH = "output/pdf/statistika-berbasis-data-batas-R011-B024.pdf"
EXPECTED_READER_BYTES = 12_390_137
EXPECTED_READER_SHA256 = (
    "fcd78ff026131e4979c0ea282b4468101406527f16dc335ee6583ad220273b53"
)
EXPECTED_READER_PAGES = 253

SOURCE_MANIFEST_PATH = (
    "scratch/b024-boundary-clean-reader/R011-B024_BOUNDARY_CLEAN_SOURCE_MANIFEST.tsv"
)
SOURCE_SNAPSHOT_ROOT = "scratch/b024-boundary-clean-reader/source-snapshot"
EXPECTED_SOURCE_MANIFEST_BYTES = 176_975
EXPECTED_SOURCE_MANIFEST_SHA256 = (
    "985d662a7ae87efed9c6e4e9d9f9dd640edcc7037f936184e3590aa5b5be6410"
)
EXPECTED_SOURCE_MANIFEST_ENTRIES = 1_218
EXPECTED_SOURCE_MANIFEST_TOTAL_BYTES = 41_841_482
EXPECTED_RHISTORY_EXCLUSIONS = 15
EXCLUDED_SOURCE_COMPONENT = (
    "ch_intro_to_data/figures/eoce/migraine_and_acupuncture_intro/"
    "earacupuncture.pdf"
)

BACKEND_MANIFEST_PATH = "backend/exports/manifest.json"
FINAL_BINDINGS_PATH = "qa/b024-backend-admission/R011-B024_FINAL_QA_BINDINGS.json"
EXPECTED_FINAL_BINDINGS_BYTES = 4_646
EXPECTED_FINAL_BINDINGS_SHA256 = (
    "a9d3b56b8931317c23261069e98d7f545f8a4e1a04b30b4ca15cade4f94d6620"
)
VISUAL_FINAL_QA_PATH = "qa/b024-reader/R011-B024_ROOT_VISUAL_INSPECTION_QA.json"
EXPECTED_VISUAL_FINAL_BYTES = 13_331
EXPECTED_VISUAL_FINAL_SHA256 = (
    "fba110143a0598fbb6f6a0132cb1bd3c3a8ac12566b331b42964479c9fca6663"
)
PUBLIC_BACKEND_ROOTS = ("core/", "locales/", "schemas/", "views/")

PRIOR_ZENODO_RECEIPT_PATH = (
    "qa/b023-publication/ZENODO_PUBLICATION_RECEIPT_R011-B023-v2026.08.29.2.json"
)
PRIOR_GITHUB_RECEIPT_PATH = (
    "release/b023/R011-B023-v2026.08.29.2/GITHUB_PUBLICATION_RECEIPT.json"
)
PRIOR_ZENODO_RECORD_ID = 22_164_353
PRIOR_GITHUB_COMMIT = "c490562098391f39852a7a99b94cd20580ad13ef"

KNOWN_INPUTS = {
    "build_qa": {
        "path": (
            "scratch/b024-boundary-clean-reader/final/"
            "R011-B024_BOUNDARY_CLEAN_BUILD_QA.json"
        ),
        "bytes": 20_617,
        "sha256": "3c59658c913ae5071f489841c7d358b616666127a303d7888db489b47dd2fbf2",
        "status": "PASS_TWO_REPLAY_DETERMINISTIC_BOUNDARY_CLEAN_BUILD_LANGUAGE_QA_COMPLETE_READER_VISUAL_QA_PENDING",
    },
    "source_blueprint": {
        "path": "qa/b024-source/R011-B024_BOUNDARY_BLUEPRINT.json",
        "bytes": 40_830,
        "sha256": "66cf48d7f797aed42434a78d3e2e43c283cac594f3f4714136a022e1ac78127e",
        "status": "PASS_SOURCE_ASSET_DATA_RIGHTS_AND_BOUNDARY_DEPENDENCY_CLOSURE",
    },
    "main_translation_qa": {
        "path": "qa/b024-translation/R011-B024_MAIN_TRANSLATION_AUDIT.json",
        "bytes": 9_726,
        "sha256": "90eb218c6b87169521896f2f3af4d04a08c0f8e5fc61c26dfcb7be80b6d91d8c",
        "status": "PASS_COMPLETE_MAIN_SECTION_TRANSLATION_STRUCTURAL_MATH_LANGUAGE_AND_CORRECTION_QA",
    },
    "main_translation_independent_qa": {
        "path": "qa/b024-translation/R011-B024_MAIN_TRANSLATION_INDEPENDENT_AUDIT.json",
        "bytes": 8_247,
        "sha256": "3258e40dd5fecfa28fe58b04af3b2793b1c28cb8f66529536b4cb6e5e5a6c9de",
        "status": "PASS_INDEPENDENT_MAIN_TRANSLATION_MEANING_STRUCTURE_MATH_CORRECTIONS_CHARTS_RIGHTS_AND_LANGUAGE_QA",
    },
    "exercise_translation_qa": {
        "path": "qa/b024-translation/R011-B024_EXERCISES_ANSWERS_TRANSLATION_QA.json",
        "bytes": 4_896,
        "sha256": "3524bb239871e8c8f1b1177b12143bc544d3408e4aef898b68d418dd51ce43df",
        "status": "PASS_EXERCISES_31_34_AND_ALL_LINKED_PUBLIC_ODD_ANSWERS_TRANSLATED",
    },
    "exercise_chart_independent_qa": {
        "path": "qa/b024-translation/R011-B024_INDEPENDENT_EXERCISE_CHART_AUDIT.json",
        "bytes": 10_169,
        "sha256": "aa6a9bf9c2f45bf6961cd609e5c38409806ecaef12d43bde900d8bb5fa9210c2",
        "status": "PASS_INDEPENDENT_EXERCISE_ANSWER_O001_CHART_DATA_RIGHTS_AND_LANGUAGE_AUDIT",
    },
    "localized_charts_qa": {
        "path": "qa/b024-translation/R011-B024_LOCALIZED_CHARTS_QA.json",
        "bytes": 4_122,
        "sha256": "3c6a445e357337ea13bef2f358fab338730431976211b2c918817bbd59c4ab3c",
        "status": "PASS_THREE_LABEL_BEARING_CHARTS_LOCALIZED_AND_EXACTLY_REPLAYED",
    },
    "localized_charts_visual_qa": {
        "path": "qa/b024-translation/R011-B024_LOCALIZED_CHARTS_VISUAL_QA.json",
        "bytes": 2_411,
        "sha256": "42e746f9b439bf653f965fed64dd1d9aec16b2c9dd3f0209c720e8fb9dd3cc44",
        "status": "PASS_ALL_THREE_LOCALIZED_CHARTS_VISUALLY_INSPECTED_ZERO_DEFECTS",
    },
    "pagewise_language_qa": {
        "path": "qa/b024-reader/R011-B024_PAGEWISE_LANGUAGE_QA.json",
        "bytes": 86_185,
        "sha256": "eb59ed06717453bef6a6fb91b3d2629094e47e25f5e42b34914d15a2a6e0b43e",
        "status": "PASS_DETERMINISTIC_BUILD_PAGEWISE_LANGUAGE_STRUCTURE_AND_AUTOMATED_VISUAL_QA",
    },
    "pagewise_language_qa_tsv": {
        "path": "qa/b024-reader/R011-B024_PAGEWISE_LANGUAGE_QA.tsv",
        "bytes": 22_472,
        "sha256": "daf7c18c7def857de03a74f4f3243f46e41314391a724721ca138b9af16682e1",
        "status": None,
    },
    "automated_visual_qa": {
        "path": "qa/b024-reader/R011-B024_AUTOMATED_VISUAL_QA.json",
        "bytes": 82_980,
        "sha256": "543ea03db38a283c323f71e383687d1137564389ebd7ce429ed34f03f175f1af",
        "status": "PASS_ALL_PAGES_RENDERED_AUTOMATED_LAYOUT_SANITY",
    },
    "reader_qa_verifier": {
        "path": "scripts/qa_b024_boundary_clean_reader.py",
        "bytes": 14_868,
        "sha256": "b8942b2d2ed93de67fee0c880c95efd87ce73ba51d3c550ff16e0cc2e43be717",
        "status": None,
    },
}

ORDERED_RELEASE_ASSETS = (
    "00_STATISTIKA_BERBASIS_DATA_ID_R011-B024_WORKING_READER.pdf",
    "01_STATISTIKA_BERBASIS_DATA_ID_R011-B024_EDITABLE_SOURCE.zip",
    "02_STATISTIKA_BERBASIS_DATA_ID_R011-B024_MODULAR_BACKEND.zip",
    "LICENSES_AND_ATTRIBUTION.md",
    "CITATION.cff",
    "README_RELEASE.md",
    "RELEASE_MANIFEST.json",
    "SHA256SUMS.txt",
    "ZENODO_METADATA.json",
)
FIXED_ZIP_TIME = (2026, 8, 29, 0, 0, 0)
PUBLICATION_STATUSES = {
    "PUBLISHED_AND_ANONYMOUSLY_VERIFIED",
    "ALREADY_PUBLISHED_AND_ANONYMOUSLY_REVERIFIED",
}


class ReleaseGateError(RuntimeError):
    """A release invariant is absent, stale, unsafe, or false."""


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


def md5_file(path: Path) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def repo_path(relative: str) -> Path:
    if not isinstance(relative, str) or not relative.strip():
        raise ReleaseGateError("repository-relative path is empty")
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
    return {"path": label, "bytes": path.stat().st_size, "sha256": sha256_file(path)}


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReleaseGateError(f"invalid JSON {path}: {exc}") from exc


def atomic_write(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        Path(name).replace(path)
    except Exception:
        Path(name).unlink(missing_ok=True)
        raise


def pdf_page_count(path: Path) -> int:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ReleaseGateError("pypdf is required to verify the reader") from exc
    try:
        return len(PdfReader(str(path), strict=True).pages)
    except Exception as exc:
        raise ReleaseGateError(f"reader PDF is not parseable: {exc}") from exc


def verify_candidate_reader(path: Path | None = None) -> dict[str, Any]:
    chosen = path or repo_path(CANDIDATE_READER_PATH)
    record = identity(chosen)
    if (record["bytes"], record["sha256"]) != (
        EXPECTED_READER_BYTES,
        EXPECTED_READER_SHA256,
    ):
        raise ReleaseGateError("B024 reader identity differs from the admitted candidate")
    pages = pdf_page_count(chosen)
    if pages != EXPECTED_READER_PAGES:
        raise ReleaseGateError("B024 learner reader is not exactly 253 parseable pages")
    return {**record, "pages": pages}


def _scalar_values(value: Any) -> list[Any]:
    if isinstance(value, dict):
        return [item for child in value.values() for item in _scalar_values(child)]
    if isinstance(value, list):
        return [item for child in value for item in _scalar_values(child)]
    return [value]


def verify_known_input(role: str) -> dict[str, Any]:
    expected = KNOWN_INPUTS[role]
    record = identity(repo_path(expected["path"]))
    if (record["bytes"], record["sha256"]) != (
        expected["bytes"],
        expected["sha256"],
    ):
        raise ReleaseGateError(f"accepted B024 input identity changed: {role}")
    if expected["status"] is not None:
        value = load_json(repo_path(expected["path"]))
        if not isinstance(value, dict) or value.get("boundary_id") != BOUNDARY_ID:
            raise ReleaseGateError(f"{role} is not B024 evidence")
        if value.get("status") != expected["status"]:
            raise ReleaseGateError(f"{role} accepted PASS status changed")
        scalars = _scalar_values(value)
        if role in {"build_qa", "pagewise_language_qa", "automated_visual_qa"}:
            if EXPECTED_READER_SHA256 not in scalars or EXPECTED_READER_PAGES not in scalars:
                raise ReleaseGateError(f"{role} does not bind the exact 253-page reader")
    return record


def source_manifest_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    manifest = identity(repo_path(SOURCE_MANIFEST_PATH))
    if (manifest["bytes"], manifest["sha256"]) != (
        EXPECTED_SOURCE_MANIFEST_BYTES,
        EXPECTED_SOURCE_MANIFEST_SHA256,
    ):
        raise ReleaseGateError("B024 source manifest identity changed")
    root = repo_path(SOURCE_SNAPSHOT_ROOT)
    if not root.is_dir():
        raise ReleaseGateError("B024 source snapshot root is absent")
    lines = repo_path(SOURCE_MANIFEST_PATH).read_text(encoding="utf-8").splitlines()
    included: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    seen: set[str] = set()
    total_bytes = 0
    for line_number, line in enumerate(lines, 1):
        parts = line.split("\t")
        if len(parts) != 3:
            raise ReleaseGateError(f"invalid source manifest row {line_number}")
        relative, size_text, digest = parts
        pure = PurePosixPath(relative)
        if pure.is_absolute() or ".." in pure.parts or relative in seen:
            raise ReleaseGateError(f"unsafe or duplicate source path: {relative}")
        seen.add(relative)
        try:
            size = int(size_text)
        except ValueError as exc:
            raise ReleaseGateError(f"invalid source size row {line_number}") from exc
        source = (root / Path(*pure.parts)).resolve()
        try:
            source.relative_to(root.resolve())
        except ValueError as exc:
            raise ReleaseGateError(f"source row escapes snapshot: {relative}") from exc
        actual = identity(source)
        if actual["bytes"] != size or actual["sha256"] != digest:
            raise ReleaseGateError(f"source snapshot identity changed: {relative}")
        total_bytes += size
        row = {"path": relative, "bytes": size, "sha256": digest, "source": source}
        if relative.endswith("/.Rhistory"):
            excluded.append({**{k: row[k] for k in ("path", "bytes", "sha256")}, "category": "transient_session_history"})
        elif relative == EXCLUDED_SOURCE_COMPONENT:
            excluded.append({**{k: row[k] for k in ("path", "bytes", "sha256")}, "category": "component_rights"})
        else:
            included.append(row)
    if len(lines) != EXPECTED_SOURCE_MANIFEST_ENTRIES or total_bytes != EXPECTED_SOURCE_MANIFEST_TOTAL_BYTES:
        raise ReleaseGateError("B024 source manifest count/byte closure changed")
    if sum(row["category"] == "transient_session_history" for row in excluded) != EXPECTED_RHISTORY_EXCLUSIONS:
        raise ReleaseGateError("B024 transient source exclusion closure changed")
    if sum(row["category"] == "component_rights" for row in excluded) != 1:
        raise ReleaseGateError("B024 component-rights exclusion closure changed")
    return included, excluded


def backend_public_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    path = repo_path(BACKEND_MANIFEST_PATH)
    record = identity(path)
    bindings_record, _bindings = verified_final_bindings()
    raw = path.read_bytes()
    required_tokens = (
        BOUNDARY_ID,
        EXPECTED_READER_SHA256,
        bindings_record["sha256"],
        EXPECTED_VISUAL_FINAL_SHA256,
    )
    if any(token.encode("ascii") not in raw for token in required_tokens):
        raise ReleaseGateError("backend manifest has not admitted the exact B024 reader")
    value = load_json(path)
    files = value.get("files") if isinstance(value, dict) else None
    if not isinstance(files, list) or not files:
        raise ReleaseGateError("backend manifest file inventory is absent")
    public: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in files:
        relative = row.get("path") if isinstance(row, dict) else None
        if not isinstance(relative, str) or relative in seen:
            raise ReleaseGateError("backend manifest has unsafe or duplicate path")
        pure = PurePosixPath(relative)
        if pure.is_absolute() or ".." in pure.parts:
            raise ReleaseGateError(f"unsafe backend path: {relative}")
        seen.add(relative)
        source = repo_path("backend/exports/" + relative)
        actual = identity(source)
        if (actual["bytes"], actual["sha256"]) != (row.get("bytes"), row.get("sha256")):
            raise ReleaseGateError(f"backend file identity changed: {relative}")
        projected = {"path": relative, "bytes": actual["bytes"], "sha256": actual["sha256"], "source": source}
        if relative.startswith(PUBLIC_BACKEND_ROOTS):
            public.append(projected)
        else:
            excluded.append({k: projected[k] for k in ("path", "bytes", "sha256")})
    if not any(row["path"].startswith("locales/id-ID/") for row in public):
        raise ReleaseGateError("compact backend projection omits id-ID")
    return sorted(public, key=lambda row: row["path"]), sorted(excluded, key=lambda row: row["path"]), record


def verify_predecessor_receipts() -> tuple[dict[str, Any], dict[str, Any]]:
    zenodo_record = identity(repo_path(PRIOR_ZENODO_RECEIPT_PATH))
    if (zenodo_record["bytes"], zenodo_record["sha256"]) != (
        2_329,
        "f30be4f0092d72421fa9140c58fbad1b40c0a36b9fdd8c0a9e9626cfc3c83954",
    ):
        raise ReleaseGateError("B023 Zenodo predecessor receipt identity changed")
    zenodo = load_json(repo_path(PRIOR_ZENODO_RECEIPT_PATH))
    if (
        not isinstance(zenodo, dict)
        or zenodo.get("boundary_id") != "R011-B023"
        or zenodo.get("record_id") != PRIOR_ZENODO_RECORD_ID
        or zenodo.get("doi") != "10.5281/zenodo.22164353"
        or zenodo.get("concept_doi") != "10.5281/zenodo.22059801"
        or zenodo.get("anonymous_public_byte_readback") is not True
        or zenodo.get("status") not in PUBLICATION_STATUSES
    ):
        raise ReleaseGateError("B023 Zenodo predecessor receipt changed")
    github_record = identity(repo_path(PRIOR_GITHUB_RECEIPT_PATH))
    if (github_record["bytes"], github_record["sha256"]) != (
        2_313,
        "79d2d2cfb42d2657973023821344bef35236583d9b8083f84e77918a81164ee8",
    ):
        raise ReleaseGateError("B023 GitHub predecessor receipt identity changed")
    github = load_json(repo_path(PRIOR_GITHUB_RECEIPT_PATH))
    if (
        not isinstance(github, dict)
        or github.get("boundary_id") != "R011-B023"
        or github.get("tag") != "r011-b023-2026.08.29.2"
        or github.get("release_commit") != PRIOR_GITHUB_COMMIT
        or github.get("anonymous_public_byte_readback") is not True
        or github.get("status") not in PUBLICATION_STATUSES
    ):
        raise ReleaseGateError("B023 GitHub predecessor receipt changed")
    return zenodo_record, github_record


def verified_final_bindings() -> tuple[dict[str, Any], dict[str, Any]]:
    bindings_path = repo_path(FINAL_BINDINGS_PATH)
    if not bindings_path.is_file():
        raise ReleaseGateError(f"missing final input: {FINAL_BINDINGS_PATH}")
    bindings_record = identity(bindings_path)
    if (bindings_record["bytes"], bindings_record["sha256"]) != (
        EXPECTED_FINAL_BINDINGS_BYTES,
        EXPECTED_FINAL_BINDINGS_SHA256,
    ):
        raise ReleaseGateError("final QA bindings exact accepted identity changed")
    bindings = load_json(bindings_path)
    if not isinstance(bindings, dict) or bindings.get("boundary_id") != BOUNDARY_ID:
        raise ReleaseGateError("final QA bindings are not B024 evidence")
    if not str(bindings.get("status", "")).startswith("PASS"):
        raise ReleaseGateError("final QA bindings are not PASS")
    scalars = _scalar_values(bindings)
    required = [
        EXPECTED_READER_SHA256,
        EXPECTED_READER_PAGES,
        EXPECTED_VISUAL_FINAL_SHA256,
        KNOWN_INPUTS["build_qa"]["sha256"],
        *[
            KNOWN_INPUTS[role]["sha256"]
            for role in KNOWN_INPUTS
            if role != "pagewise_language_qa_tsv"
        ],
    ]
    missing = [item for item in required if item not in scalars]
    if missing:
        raise ReleaseGateError("final QA bindings omit exact accepted input identities")
    return bindings_record, bindings


def verify_dynamic_admission() -> dict[str, Any]:
    visual_path = repo_path(VISUAL_FINAL_QA_PATH)
    if not visual_path.is_file():
        raise ReleaseGateError(f"missing final input: {VISUAL_FINAL_QA_PATH}")
    visual_record = identity(visual_path)
    if (visual_record["bytes"], visual_record["sha256"]) != (
        EXPECTED_VISUAL_FINAL_BYTES,
        EXPECTED_VISUAL_FINAL_SHA256,
    ):
        raise ReleaseGateError("visual-final QA exact accepted identity changed")
    visual = load_json(visual_path)
    if not isinstance(visual, dict) or visual.get("boundary_id") != BOUNDARY_ID:
        raise ReleaseGateError("visual-final QA is not B024 evidence")
    if visual.get("status") != "PASS_ALL_253_PAGES_VISUALLY_INSPECTED_ZERO_DEFECTS":
        raise ReleaseGateError("visual-final QA accepted PASS status changed")
    visual_scalars = _scalar_values(visual)
    if EXPECTED_READER_SHA256 not in visual_scalars or EXPECTED_READER_PAGES not in visual_scalars:
        raise ReleaseGateError("visual-final QA does not bind the exact 253-page reader")
    bindings_record, _bindings = verified_final_bindings()
    backend_rows, backend_exclusions, backend_record = backend_public_rows()
    return {
        "visual_final_qa": visual_record,
        "final_qa_bindings": bindings_record,
        "backend_manifest": backend_record,
        "backend_public_rows": backend_rows,
        "backend_exclusions": backend_exclusions,
    }


def release_readiness() -> dict[str, Any]:
    candidate = verify_candidate_reader()
    source_rows, source_exclusions = source_manifest_rows()
    known = {role: verify_known_input(role) for role in KNOWN_INPUTS}
    prior_zenodo, prior_github = verify_predecessor_receipts()
    gaps: list[str] = []
    dynamic: dict[str, Any] | None = None
    for path in (VISUAL_FINAL_QA_PATH, FINAL_BINDINGS_PATH):
        if not repo_path(path).is_file():
            gaps.append(path)
    manifest = repo_path(BACKEND_MANIFEST_PATH)
    bindings_path = repo_path(FINAL_BINDINGS_PATH)
    backend_tokens = (BOUNDARY_ID, EXPECTED_READER_SHA256, EXPECTED_VISUAL_FINAL_SHA256)
    if bindings_path.is_file():
        try:
            backend_tokens = (*backend_tokens, verified_final_bindings()[0]["sha256"])
        except ReleaseGateError:
            gaps.append(FINAL_BINDINGS_PATH + " exact PASS semantics")
    if not manifest.is_file() or any(token.encode("ascii") not in manifest.read_bytes() for token in backend_tokens):
        gaps.append("backend/exports/manifest.json admitting exact R011-B024 reader")
    if not gaps:
        dynamic = verify_dynamic_admission()
    promoted = repo_path(FINAL_READER_PATH)
    promoted_record = None
    if promoted.is_file():
        promoted_record = verify_candidate_reader(promoted)
    else:
        gaps.append(FINAL_READER_PATH)
    return {
        "candidate_reader": candidate,
        "source_public_entries": len(source_rows),
        "source_excluded_entries": len(source_exclusions),
        "known_inputs": known,
        "dynamic_admission": dynamic,
        "promoted_reader": promoted_record,
        "prior_zenodo_receipt": prior_zenodo,
        "prior_github_receipt": prior_github,
        "gaps": gaps,
    }


def require_release_readiness() -> dict[str, Any]:
    result = release_readiness()
    if result["gaps"]:
        raise ReleaseGateError("B024 release admission is incomplete: " + "; ".join(result["gaps"]))
    return result


def deterministic_zip(destination: Path, rows: Iterable[tuple[str, Path]]) -> dict[str, Any]:
    ordered = sorted(rows, key=lambda row: row[0])
    names = [name for name, _path in ordered]
    if len(names) != len(set(names)):
        raise ReleaseGateError("ZIP archive-name collision")
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for archive_name, source in ordered:
            pure = PurePosixPath(archive_name)
            if pure.is_absolute() or ".." in pure.parts:
                raise ReleaseGateError(f"unsafe ZIP archive name: {archive_name}")
            info = zipfile.ZipInfo(pure.as_posix(), FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            with source.open("rb") as input_stream, archive.open(info, "w") as output_stream:
                for chunk in iter(lambda: input_stream.read(1024 * 1024), b""):
                    output_stream.write(chunk)
    with zipfile.ZipFile(destination, "r") as archive:
        if archive.namelist() != names or archive.testzip() is not None:
            raise ReleaseGateError("deterministic ZIP verification failed")
    return identity(destination)


def validate_config(config: dict[str, Any], *, package_required: bool = False) -> None:
    expected = {
        "$schema": "r011-b024-release-inputs/v1",
        "boundary_id": BOUNDARY_ID,
        "release_id": RELEASE_ID,
        "version": VERSION,
        "version_label": VERSION_LABEL,
        "release_date": RELEASE_DATE,
        "model_identification": MODEL,
        "license": "CC BY-SA 3.0 Unported",
        "license_id": "cc-by-sa-3.0",
        "status": "READY_FOR_PACKAGING",
    }
    for key, wanted in expected.items():
        if config.get(key) != wanted:
            raise ReleaseGateError(f"release config field changed: {key}")
    if config.get("ordered_release_assets") != list(ORDERED_RELEASE_ASSETS):
        raise ReleaseGateError("release asset order changed")
    coverage = config.get("coverage", {})
    wanted_coverage = {
        "completion_state": "partial",
        "complete_corpus": False,
        "learner_reader_pages": 253,
        "accepted_indonesian_reader_pages": 253,
        "untranslated_instructional_or_exercise_prose_pages": 0,
        "through": "Bab 6, Bagian 6.3 Uji kesesuaian menggunakan khi-kuadrat",
        "exercise_ids": list(range(1, 35)),
        "public_answer_ids": list(range(1, 34, 2)),
        "o001_gap_ids": list(range(2, 35, 2)),
        "restricted_solutions_used": False,
        "full_source_closure_contains_untranslated_source": True,
        "source_closure_counted_as_learner_output": False,
    }
    for key, wanted in wanted_coverage.items():
        if coverage.get(key) != wanted:
            raise ReleaseGateError(f"release coverage truth changed: {key}")
    if config.get("destinations", {}).get("zenodo") != {
        "concept_doi": "10.5281/zenodo.22059801",
        "concept_record_id": 22059801,
        "prior_record_id": PRIOR_ZENODO_RECORD_ID,
        "prior_doi": "10.5281/zenodo.22164353",
        "prior_version": "2026.08.29.2-R011-B023",
        "route": "existing_concept_new_version_only",
    }:
        raise ReleaseGateError("Zenodo lineage changed")
    if config.get("destinations", {}).get("github") != {
        "owner": "KokunoYumeto",
        "repository": "statistika-berbasis-data-id",
        "default_branch": "main",
        "tag": GITHUB_TAG,
        "prior_tag": "r011-b023-2026.08.29.2",
        "prior_release_commit": PRIOR_GITHUB_COMMIT,
        "prerelease": True,
        "tree_mode": "exact_fresh_tree_from_bounded_allowlist",
    }:
        raise ReleaseGateError("GitHub lineage changed")
    inputs = config.get("inputs")
    if not isinstance(inputs, dict):
        raise ReleaseGateError("release inputs object is absent")
    if inputs.get("reader", {}).get("path") != FINAL_READER_PATH:
        raise ReleaseGateError("release config does not bind the canonical promoted B024 reader path")
    for role, record in inputs.items():
        if role == "reader":
            actual = verify_candidate_reader(repo_path(record["path"]))
        else:
            actual = identity(repo_path(record["path"]))
        if any(actual[key] != record[key] for key in ("path", "bytes", "sha256")):
            raise ReleaseGateError(f"release input identity changed: {role}")
    ready = require_release_readiness()
    expected_roles = {
        "reader",
        "source_manifest",
        "backend_manifest",
        "visual_final_qa",
        "final_qa_bindings",
        "prior_zenodo_receipt",
        "prior_github_receipt",
        *KNOWN_INPUTS.keys(),
    }
    if set(inputs) != expected_roles:
        raise ReleaseGateError("release input role inventory changed")
    if inputs["backend_manifest"] != ready["dynamic_admission"]["backend_manifest"]:
        raise ReleaseGateError("bound backend manifest is not the admitted B024 manifest")
    if package_required:
        verify_release_package(config)


def load_config(*, package_required: bool = False) -> dict[str, Any]:
    if not CONFIG_PATH.is_file():
        raise ReleaseGateError("B024 RELEASE_INPUTS.json is absent; run prepare_b024_release.py --prepare after admission")
    config = load_json(CONFIG_PATH)
    if not isinstance(config, dict):
        raise ReleaseGateError("release config is not an object")
    validate_config(config, package_required=package_required)
    return config


def release_assets(config: dict[str, Any]) -> list[Path]:
    return [RELEASE_DIR / name for name in config["ordered_release_assets"]]


def verify_release_package(config: dict[str, Any]) -> dict[str, Any]:
    manifest_path = RELEASE_DIR / "RELEASE_MANIFEST.json"
    if not manifest_path.is_file():
        raise ReleaseGateError("B024 release package has not been materialized")
    manifest = load_json(manifest_path)
    if (
        not isinstance(manifest, dict)
        or manifest.get("$schema") != "r011-b024-release-manifest/v1"
        or manifest.get("boundary_id") != BOUNDARY_ID
        or manifest.get("release_id") != RELEASE_ID
        or manifest.get("status") != "PACKAGED_VERIFIED"
        or manifest.get("learner_reader_pages") != EXPECTED_READER_PAGES
        or manifest.get("untranslated_instructional_or_exercise_prose_pages") != 0
        or manifest.get("ordered_assets") != list(ORDERED_RELEASE_ASSETS)
    ):
        raise ReleaseGateError("B024 release manifest truth changed")
    for path in release_assets(config):
        if not path.is_file():
            raise ReleaseGateError(f"release asset is absent: {path.name}")
    declared = manifest.get("files")
    if not isinstance(declared, list) or len(declared) != 7:
        raise ReleaseGateError("B024 hashed-file inventory changed")
    for row in declared:
        actual = identity(RELEASE_DIR / row["filename"])
        if (actual["bytes"], actual["sha256"]) != (row["bytes"], row["sha256"]):
            raise ReleaseGateError(f"release file identity changed: {row['filename']}")
    sums = "".join(f"{row['sha256']}  {row['filename']}\n" for row in declared)
    if (RELEASE_DIR / "SHA256SUMS.txt").read_text(encoding="utf-8") != sums:
        raise ReleaseGateError("SHA256SUMS does not match the release manifest")
    if sha256_file(RELEASE_DIR / ORDERED_RELEASE_ASSETS[0]) != EXPECTED_READER_SHA256:
        raise ReleaseGateError("packaged reader differs from admitted B024 reader")
    return manifest


def static_self_check(component: str) -> dict[str, Any]:
    ready = release_readiness()
    config_present = CONFIG_PATH.is_file()
    package_present = (RELEASE_DIR / "RELEASE_MANIFEST.json").is_file()
    if config_present:
        load_config(package_required=package_present)
    return {
        "$schema": "r011-b024-release-tool-self-check/v1",
        "boundary_id": BOUNDARY_ID,
        "release_id": RELEASE_ID,
        "component": component,
        "status": (
            "PASS_STATIC_OFFLINE_FAIL_CLOSED_READY"
            if not ready["gaps"]
            else "PASS_STATIC_OFFLINE_FAIL_CLOSED_AWAITING_ADMISSION"
        ),
        "candidate_reader": ready["candidate_reader"],
        "known_inputs": ready["known_inputs"],
        "source_public_entries": ready["source_public_entries"],
        "source_excluded_entries": ready["source_excluded_entries"],
        "predecessor_zenodo_receipt": ready["prior_zenodo_receipt"],
        "predecessor_github_receipt": ready["prior_github_receipt"],
        "planned_version": VERSION,
        "planned_zenodo_concept_doi": "10.5281/zenodo.22059801",
        "planned_github_repository": "KokunoYumeto/statistika-berbasis-data-id",
        "planned_github_tag": GITHUB_TAG,
        "awaiting_before_prepare": ready["gaps"],
        "resolved_config_present": config_present,
        "verified_package_present": package_present,
        "network_used": False,
        "credentials_read": False,
        "publication_performed": False,
        "local_git_used": False,
        "upstream_contact": False,
    }
