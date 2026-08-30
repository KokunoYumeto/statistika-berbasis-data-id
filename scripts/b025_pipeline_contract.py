#!/usr/bin/env python3
"""Read-only, fail-closed identity contract for the R011-B025 post-build pipeline.

The source/translation/chart inputs are sealed here.  Reader/build identities are
bound once, after the deterministic build and whole-reader QA, in
``qa/b025-pipeline/R011-B025_POST_BUILD_BINDINGS.json``.  Importing this module
never writes, reads credentials, uses Git, or performs network I/O.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BOUNDARY_ID = "R011-B025"
BASE_BOUNDARY_ID = "R011-B024"
NEXT_BOUNDARY_ID = "R011-B026"
RELEASE_ID = "R011-B025-v2026.08.29.4"
VERSION = "2026.08.29.4-R011-B025"
VERSION_LABEL = "v2026.08.29.4"
GITHUB_TAG = "r011-b025-2026.08.29.4"
RELEASE_DATE = "2026-08-29"
MODEL = "OpenAI Codex gpt-5.6-sol, Ultra"
UPSTREAM_COMMIT = "fee25091fb24e89c36296fd67c48c1fcf7a93b6e"
UPSTREAM_TREE = "d61cc601e7d97759ce805900520f784d02a0489e"

BINDINGS_REL = "qa/b025-pipeline/R011-B025_POST_BUILD_BINDINGS.json"
BINDINGS_PATH = ROOT / BINDINGS_REL
RELEASE_DIR = ROOT / "release/b025" / RELEASE_ID
CONFIG_PATH = RELEASE_DIR / "RELEASE_INPUTS.json"

BASE_BACKEND = {
    "path": "backend/exports/manifest.json",
    "bytes": 153_691,
    "sha256": "efef659953d2a82fdce0072aa814b77d790729607041527b6cf80124626d3b28",
}
BASE_ADMISSION = {
    "path": "qa/b024-backend-admission/R011-B024_BACKEND_ADMISSION_RECEIPT.json",
    "bytes": 3_167,
    "sha256": "18d4cb3c08c1928966d435123f189ebeb99aaac0ada24a1e23cbdac9291ad289",
}
BASE_REPLAY = {
    "path": "qa/b024-backend-admission/R011-B024_BACKEND_REPLAY.json",
    "bytes": 3_384,
    "sha256": "e4bae5ce47aa85be78f9fe5e37982beb938ae05891533996df26a21918c1757d",
}
PRIOR_ZENODO_RECEIPT = {
    "path": "qa/b024-publication/ZENODO_PUBLICATION_RECEIPT_R011-B024-v2026.08.29.3.json",
    "bytes": 2_372,
    "sha256": "7eb6c5e78d6db08dcb46d5c3ab08480c7fae0cfd128247234e5a66907b198d9c",
    "record_id": 22_166_152,
    "doi": "10.5281/zenodo.22166152",
}
PRIOR_GITHUB_RECEIPT = {
    "path": "release/b024/R011-B024-v2026.08.29.3/GITHUB_PUBLICATION_RECEIPT.json",
    "bytes": 2_332,
    "sha256": "0feae29aa61c63f995fcbf16e5d4c13d8ad242c8402148077a16459428b5d5f2",
    "commit": "91790977cf86eaf3f0ee8f038d097684100fc773",
    "tag": "r011-b024-2026.08.29.3",
}


def sealed(path: str, size: int, digest: str, status: str | None = None, *, boundary_required: bool = True) -> dict[str, Any]:
    row: dict[str, Any] = {"path": path, "bytes": size, "sha256": digest}
    if status is not None:
        row["required_status"] = status
        row["boundary_required"] = boundary_required
    return row


SEALED_INPUTS: dict[str, dict[str, Any]] = {
    "source_blueprint": sealed(
        "qa/b025-source/R011-B025_BOUNDARY_BLUEPRINT.json", 24_634,
        "529f46e13cabc1db76a65e8a1281f99e51251cc08753e8c217871d52eb296d7e",
        "PASS_SOURCE_ASSET_DATA_RIGHTS_AND_BOOK_ORDER_DEPENDENCY_CLOSURE",
    ),
    "main_translation_a_qa": sealed(
        "qa/b025-translation/R011-B025_MAIN_A_TRANSLATION_AUDIT.json", 3_914,
        "06742809fcd4984788b9790a9ecba4fbc9c70eb14acd026936b32100a6ac7fed",
        "PASS_COMPLETE_NATURAL_ID_ID_STRUCTURE_MATH_LANGUAGE_AND_HIGH_CONFIDENCE_FORMULA_CORRECTION_QA",
    ),
    "main_translation_b_qa": sealed(
        "qa/b025-translation/R011-B025_MAIN_TRANSLATION_PART_B_AUDIT.json", 7_712,
        "b0dfee1a269bb541d3b6d941dc4c400c33e1b774fb0d30e8d1b6f80ba365a776",
        "PASS_DETERMINISTIC_STRUCTURE_MATH_AND_RESIDUAL_ENGLISH", boundary_required=False,
    ),
    "exercise_answer_qa": sealed(
        "qa/b025-translation/R011-B025_EXERCISES_ANSWERS_TRANSLATION_QA.json", 2_844,
        "a3653c8aaa12301fbded5588c83ef6c59bccbc5a107b806c2118c29a3005e947",
        "PASS_EXERCISES_35_38_AND_ALL_LINKED_PUBLIC_ODD_ANSWERS_TRANSLATED",
    ),
    "independent_translation_qa": sealed(
        "qa/b025-translation/R011-B025_INDEPENDENT_TRANSLATION_AUDIT.json", 16_509,
        "737f485b49f80e26269e282b227221d7eb3826005c5dd8d1b6066ae8cbd5c215",
        "PASS_INDEPENDENT_COMPLETE_NATURAL_ID_ID_STRUCTURE_MATH_REPAIRS_EXERCISE_ANSWER_AND_O001_QA",
    ),
    "independent_translation_verifier": sealed(
        "qa/b025-translation/verify_R011_B025_independent.py", 38_379,
        "214e6977f6d9b1e32e97b3b3012ca8df73a78fd4796c1370ca185216a7d5270f",
    ),
    "localized_chart": sealed(
        "qa/b025-translation/staging/assets/iPodChiSqTail.id.pdf", 13_265,
        "4d34c0d4f59787283086f88fb0eaa7c47714726b0e21fcb440a7bcf8e243acae",
    ),
    "localized_chart_qa": sealed(
        "qa/b025-translation/R011-B025_IPOD_CHISQ_TAIL_LOCALIZATION_QA.json", 3_314,
        "c2ab840d15bf7391518c4587aad7ed6f7ded1c9b208706861434ac64e9b104db",
        "PASS_EXACT_ANNOTATION_LOCALIZATION_AND_GEOMETRY_PRESERVATION",
    ),
    "localized_chart_visual_qa": sealed(
        "qa/b025-translation/R011-B025_IPOD_CHISQ_TAIL_VISUAL_QA.json", 2_603,
        "13ec3d5529ebdf198630341f16accb457bb8b94cdda7edcfdbb218007f29e837",
        "PASS_DIRECT_VISUAL_INSPECTION_AND_RASTER_GEOMETRY_COMPARISON",
    ),
    "section_a_translation": sealed(
        "qa/b025-translation/staging/section-lines-2008-2238.id.tex", 9_104,
        "5a59d955174eb73176876d756bb4c44ba427d25d5ca86ab41824ff218d2d9554",
    ),
    "section_b_translation": sealed(
        "qa/b025-translation/staging/section-lines-2239-2434.id.tex", 7_107,
        "bc16102ee8a445f2410a9d429b9831a58f2637a528776ca727eb07607d045d63",
    ),
    "exercise_translation": sealed(
        "qa/b025-translation/staging/exercises-lines-1-127.id.tex", 4_933,
        "0d66bdb60c1edcf246e933ac0eab97bacaf237a573ec260e5a3463076731f440",
    ),
    "public_answer_translation": sealed(
        "qa/b025-translation/staging/public-answers-lines-1500-1543.id.tex", 1_748,
        "91a3e108ced397c72ae204d5f142fc9838f2612312383d1aa52eac78f0eb2dec",
    ),
    "o001_gap_ledger": sealed(
        "qa/b025-translation/staging/R011-B025_O001_MASTERY_GAPS.json", 2_107,
        "5ca09682b02110ce941065c495683bbd36cd7ac9055c88dbd89b46512c4b8aee",
    ),
    "source_freezer": sealed(
        "scripts/freeze_b025_source.py", 31_234,
        "7ff437b16356848443fb6ec3787178e532052c644168ba04a464b8c326d077d7",
    ),
    "chart_localizer": sealed(
        "scripts/localize_b025_ipod_chisq_tail.py", 14_532,
        "1691ba9f2a7c5dd7b3f94b2f5acbfcb5b8f328861773804a4e12b9225fd81903",
    ),
}

POST_BUILD_ROLES: dict[str, dict[str, Any]] = {
    "candidate_pdf": {"path": "scratch/b025-boundary-clean-reader-r2/final/main.pdf", "pdf": True},
    "candidate_text": {"path": "scratch/b025-boundary-clean-reader-r2/final/main-final.txt"},
    "build_qa": {
        "path": "scratch/b025-boundary-clean-reader-r2/final/R011-B025_BOUNDARY_CLEAN_BUILD_QA.json",
        "required_status": "PASS_TWO_REPLAY_DETERMINISTIC_BOUNDARY_CLEAN_BUILD_LANGUAGE_QA_COMPLETE_READER_VISUAL_QA_PENDING",
    },
    "source_manifest": {"path": "scratch/b025-boundary-clean-reader-r2/R011-B025_BOUNDARY_CLEAN_SOURCE_MANIFEST.tsv"},
    "pagewise_language_qa": {
        "path": "qa/b025-reader/R011-B025_PAGEWISE_LANGUAGE_QA.json",
        "required_status": "PASS_DETERMINISTIC_BUILD_PAGEWISE_LANGUAGE_STRUCTURE_AND_AUTOMATED_VISUAL_QA",
    },
    "pagewise_language_qa_tsv": {"path": "qa/b025-reader/R011-B025_PAGEWISE_LANGUAGE_QA.tsv"},
    "automated_visual_qa": {
        "path": "qa/b025-reader/R011-B025_AUTOMATED_VISUAL_QA.json",
        "required_status": "PASS_ALL_PAGES_RENDERED_AUTOMATED_LAYOUT_SANITY",
    },
    "root_visual_qa": {
        "path": "qa/b025-reader/R011-B025_ROOT_VISUAL_INSPECTION_QA.json",
        "status_pattern": r"PASS_ALL_[1-9][0-9]*_PAGES_VISUALLY_INSPECTED_ZERO_DEFECTS",
    },
    "reader_qa_verifier": {"path": "scripts/qa_b025_boundary_clean_reader.py"},
}

FINAL_READER_PATH = "output/pdf/statistika-berbasis-data-batas-R011-B025.pdf"
PROMOTION_RECEIPT_PATH = "qa/b025-reader/R011-B025_READER_PROMOTION_RECEIPT.json"
BACKEND_ADMISSION_RECEIPT_PATH = "qa/b025-backend-admission/R011-B025_BACKEND_ADMISSION_RECEIPT.json"
BACKEND_REPLAY_RECEIPT_PATH = "qa/b025-backend-admission/R011-B025_BACKEND_REPLAY.json"


class StageGateError(RuntimeError):
    """An exact identity, status, lineage, or safety gate is not satisfied."""


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def repo_path(relative: str) -> Path:
    token = relative.replace("\\", "/")
    pure = PurePosixPath(token)
    if not token or pure.is_absolute() or ".." in pure.parts or re.match(r"^[A-Za-z]:", token):
        raise StageGateError(f"unsafe repository-relative path: {relative!r}")
    candidate = (ROOT / Path(*pure.parts)).resolve()
    try:
        candidate.relative_to(ROOT)
    except ValueError as exc:
        raise StageGateError(f"path escapes lane: {relative!r}") from exc
    return candidate


def identity(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise StageGateError(f"missing required file: {path}")
    digest = hashlib.sha256()
    count = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            count += len(chunk)
            digest.update(chunk)
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": count, "sha256": digest.hexdigest()}


def verify_record(role: str, expected: dict[str, Any]) -> dict[str, Any]:
    observed = identity(repo_path(expected["path"]))
    if (observed["bytes"], observed["sha256"]) != (expected["bytes"], expected["sha256"]):
        raise StageGateError(f"{role} identity changed: {observed!r}")
    required = expected.get("required_status")
    if required is not None:
        try:
            payload = json.loads(repo_path(expected["path"]).read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise StageGateError(f"{role} is not valid UTF-8 JSON") from exc
        if payload.get("status") != required or (expected.get("boundary_required", True) and payload.get("boundary_id") != BOUNDARY_ID):
            raise StageGateError(f"{role} boundary/status changed")
    return {**observed, **({"required_status": required} if required is not None else {})}


def verify_sealed_inputs() -> dict[str, dict[str, Any]]:
    live = identity(repo_path(BASE_BACKEND["path"]))
    exact_base = {key: BASE_BACKEND[key] for key in ("path", "bytes", "sha256")}
    if live == exact_base:
        manifest = json.loads(repo_path(BASE_BACKEND["path"]).read_text(encoding="utf-8"))
        if manifest.get("boundary_id") != BASE_BOUNDARY_ID or manifest.get("record_count") != 8_911:
            raise StageGateError("base backend is not exact admitted B024")
        base = live
    else:
        preimage_path = repo_path("qa/b025-backend-admission/preimages-R011-B025/manifest.json")
        preimage = identity(preimage_path)
        if (preimage["bytes"], preimage["sha256"]) != (BASE_BACKEND["bytes"], BASE_BACKEND["sha256"]):
            raise StageGateError("exact B024 backend preimage is absent after B025 admission")
        try:
            manifest = json.loads(repo_path(BASE_BACKEND["path"]).read_text(encoding="utf-8"))
            receipt_path = repo_path(BACKEND_ADMISSION_RECEIPT_PATH)
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise StageGateError("live backend advanced without a valid B025 admission receipt") from exc
        if (
            manifest.get("boundary_id") != BOUNDARY_ID
            or manifest.get("record_count") != 9_119
            or receipt.get("boundary_id") != BOUNDARY_ID
            or receipt.get("status") != "PASS_B025_BACKEND_ATOMIC_ADMISSION_AND_EXACT_REPLAY"
            or receipt.get("live_manifest") != live
            or receipt.get("base_manifest") != {key: BASE_BACKEND[key] for key in ("bytes", "sha256")}
        ):
            raise StageGateError("live backend is neither exact B024 nor receipted B025")
        base = exact_base
    rows = {"base_backend": base}
    rows.update({role: verify_record(role, expected) for role, expected in SEALED_INPUTS.items()})
    return rows


def load_bindings(*, require_complete: bool = True) -> dict[str, Any] | None:
    if not BINDINGS_PATH.is_file():
        if require_complete:
            raise StageGateError(f"post-build binding is absent: {BINDINGS_REL}")
        return None
    raw = BINDINGS_PATH.read_bytes()
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StageGateError("post-build binding is not valid UTF-8 JSON") from exc
    if payload.get("boundary_id") != BOUNDARY_ID or payload.get("status") != "PASS_EXACT_B025_POST_BUILD_IDENTITIES_BOUND":
        raise StageGateError("post-build binding boundary/status changed")
    if payload.get("sealed_inputs") != verify_sealed_inputs():
        raise StageGateError("post-build binding no longer matches sealed production inputs")
    outputs = payload.get("post_build_outputs")
    if not isinstance(outputs, dict) or set(outputs) != set(POST_BUILD_ROLES):
        raise StageGateError("post-build binding output roles changed")
    pages = outputs["candidate_pdf"].get("pages")
    if not isinstance(pages, int) or pages <= 253:
        raise StageGateError("B025 reader page extent is not greater than B024")
    for role, spec in POST_BUILD_ROLES.items():
        row = outputs[role]
        observed = identity(repo_path(spec["path"]))
        exact = {key: row[key] for key in ("path", "bytes", "sha256")}
        if observed != exact:
            raise StageGateError(f"bound post-build output changed: {role}")
        if row.get("required_status") != spec.get("required_status") and "required_status" in spec:
            raise StageGateError(f"bound status contract changed: {role}")
        if role == "root_visual_qa" and not re.fullmatch(spec["status_pattern"], str(row.get("required_status", ""))):
            raise StageGateError("root visual status is not page-count bound")
    if outputs["root_visual_qa"]["required_status"] != f"PASS_ALL_{pages}_PAGES_VISUALLY_INSPECTED_ZERO_DEFECTS":
        raise StageGateError("root visual status page count differs from reader")
    return payload


def offline_self_check(component: str) -> dict[str, Any]:
    sealed_rows = verify_sealed_inputs()
    bindings = load_bindings(require_complete=False)
    return {
        "$schema": "interlanguage.r011-b025-post-build-pipeline-self-check/v1",
        "boundary_id": BOUNDARY_ID,
        "component": component,
        "status": "PASS_STATIC_B025_PIPELINE_INPUTS_POST_BUILD_BINDING_PRESENT" if bindings else "PASS_STATIC_B025_PIPELINE_INPUTS_POST_BUILD_BINDING_PENDING",
        "sealed_input_count": len(sealed_rows),
        "post_build_binding": identity(BINDINGS_PATH) if bindings else None,
        "pending_final_reader_values": [] if bindings else [
            "candidate PDF bytes/SHA-256/pages",
            "candidate extracted-text bytes/SHA-256",
            "build-receipt bytes/SHA-256",
            "source-manifest bytes/SHA-256/entry count/total bytes",
            "pagewise-language JSON and TSV bytes/SHA-256",
            "automated whole-reader visual-QA bytes/SHA-256",
            "root visual-QA bytes/SHA-256/page-bound status",
            "reader verifier bytes/SHA-256",
        ],
        "writes_performed": False,
        "backend_mutated": False,
        "controls_mutated": False,
        "output_mutated": False,
        "release_mutated": False,
        "network_used": False,
        "credentials_accessed": False,
        "git_used": False,
        "upstream_contact": False,
    }
