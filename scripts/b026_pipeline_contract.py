#!/usr/bin/env python3
"""Fail-closed identity contract for the R011-B026 backend/build pipeline.

The exact B025 backend and every completed B026 text input are sealed here.
Localized-asset and post-build registrations are populated only from finished
primary receipts.  Until both registrations are present and their complete
identity graphs replay, backend admission is impossible.  Importing this module
never writes, uses Git, reads credentials, performs network I/O, or contacts
upstream.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BOUNDARY_ID = "R011-B026"
BASE_BOUNDARY_ID = "R011-B025"
NEXT_BOUNDARY_ID = "R011-B027"
MODEL = "OpenAI Codex gpt-5.6-sol, Ultra"
UPSTREAM_COMMIT = "fee25091fb24e89c36296fd67c48c1fcf7a93b6e"
UPSTREAM_TREE = "d61cc601e7d97759ce805900520f784d02a0489e"

BINDINGS_REL = "qa/b026-pipeline/R011-B026_POST_BUILD_BINDINGS.json"
BINDINGS_PATH = ROOT / BINDINGS_REL
ASSET_CLOSURE_REL = "qa/b026-translation/R011-B026_ASSET_LOCALIZATION_QA.json"
ASSET_CLOSURE_PATH = ROOT / ASSET_CLOSURE_REL

BACKEND_ADMISSION_RECEIPT_PATH = "qa/b026-backend-admission/R011-B026_BACKEND_ADMISSION_RECEIPT.json"
BACKEND_REPLAY_RECEIPT_PATH = "qa/b026-backend-admission/R011-B026_BACKEND_REPLAY.json"

BASE_BACKEND = {
    "path": "backend/exports/manifest.json",
    "bytes": 159_526,
    "sha256": "851350f813aca15d10692884f0df7265915029a13b330e0d18bb6dd379b128a8",
}
BASE_ADMISSION = {
    "path": "qa/b025-backend-admission/R011-B025_BACKEND_ADMISSION_RECEIPT.json",
    "bytes": 1_233,
    "sha256": "d833d0b15c6a87fcb4fdd835115d6a1a72d611e40de7af8cf1e62a4bcd23759e",
}
BASE_REPLAY = {
    "path": "qa/b025-backend-admission/R011-B025_BACKEND_REPLAY.json",
    "bytes": 928,
    "sha256": "12e00208d31e788bad7954f9b9840181d1781358ba0f327dfe81e8b6de912193",
}


def sealed(
    path: str,
    size: int,
    digest: str,
    status: str | None = None,
    *,
    boundary_required: bool = True,
) -> dict[str, Any]:
    row: dict[str, Any] = {"path": path, "bytes": size, "sha256": digest}
    if status is not None:
        row["required_status"] = status
        row["boundary_required"] = boundary_required
    return row


SEALED_TEXT_INPUTS: dict[str, dict[str, Any]] = {
    "source_blueprint": sealed(
        "qa/b026-source/R011-B026_BOUNDARY_BLUEPRINT.json",
        52_663,
        "2340adb156e7dd6833a2421eed9b6b4e2f7045e347f4fe8639544028cd6ced34",
        "PASS_SOURCE_ASSET_DATA_RIGHTS_AND_BOOK_ORDER_DEPENDENCY_CLOSURE",
    ),
    "text_checkpoint": sealed(
        "qa/b026-translation/R011-B026_TEXT_TRANSLATION_CHECKPOINT.json",
        4_729,
        "58d7a55cc7a90ca86950e1e28ee31f2ba9e7aa43b5a363ef4af9f55d61853a2f",
        "PASS_ALL_B026_TEXT_TRANSLATED_AND_EXACTLY_REPLAYED_ASSETS_BUILD_BACKEND_AND_PUBLICATION_PENDING",
    ),
    "main_translation_a": sealed(
        "qa/b026-translation/staging/chapter-lines-1-231.id.tex",
        9_551,
        "f7ee09a6df0667faa82ac86cf032f4eb0477a29ca94c7f1bc676dad38fc96d34",
    ),
    "main_translation_b": sealed(
        "qa/b026-translation/staging/chapter-lines-232-400.id.tex",
        7_094,
        "660ea8e51126b378c5b5ada70a365dc8111e0fa771de0bd979f8c017b2bcc7e4",
    ),
    "main_translation_c": sealed(
        "qa/b026-translation/staging/chapter-lines-401-633.id.tex",
        10_675,
        "d50a78f6fbbf52a5007cd42929ea1dd3737b9cc3b8bf0aec5bca3a9a861b44b3",
    ),
    "main_translation_d": sealed(
        "qa/b026-translation/staging/chapter-lines-634-796.id.tex",
        6_278,
        "bf908c142ee30f0b0e2a4d96b06c87d72ad941c7bba5af99d59786ee437c0613",
    ),
    "main_translation_e": sealed(
        "qa/b026-translation/staging/chapter-lines-797-896.id.tex",
        3_804,
        "c56ea68a482ed32479d4a9968f6bbac4d117a2f68b0c8774709a9e505884773d",
    ),
    "main_translation_f": sealed(
        "qa/b026-translation/staging/chapter-lines-897-1052.id.tex",
        6_463,
        "d4ad6b2b445259ed72dae2e301d2956a9f61e22d7c28fc63981ba403d8248ceb",
    ),
    "exercise_translation": sealed(
        "qa/b026-translation/staging/exercises-lines-1-280.id.tex",
        10_409,
        "d84536e75f75f66d59a2021ea3a18dd3e51bf146a37445eebc67ed634c4c4b21",
    ),
    "public_answer_translation": sealed(
        "qa/b026-translation/staging/public-answers-lines-1623-1721.id.tex",
        3_247,
        "ba75f7b07e02b58f76ac25cfe3e0ef0b1c98a8eedc7a60b6d9d80faebc4ee73f",
    ),
    "o001_gap_ledger": sealed(
        "qa/b026-translation/staging/R011-B026_O001_MASTERY_GAPS.json",
        5_723,
        "3664d3af33ea9c00fe50c45e83f977285f1c6446632eeaaf6821291f5102b78b",
        "EXPLICIT_O001_GAPS_RECORDED_NO_RESTRICTED_SOLUTIONS_ACCESSED_OR_INVENTED",
    ),
    "main_translation_a_qa": sealed(
        "qa/b026-translation/R011-B026_MAIN_TRANSLATION_PART_A_QA.json",
        5_830,
        "23a11d485ceb9aa651dfb80b09871591b9727438f1212401a66b388939c9da1e",
        "PASS_COMPLETE_NATURAL_ID_ID_STRUCTURE_MATH_PROTECTED_TEX_AND_RESIDUAL_ENGLISH_QA",
    ),
    "main_translation_b_qa": sealed(
        "qa/b026-translation/R011-B026_MAIN_TRANSLATION_PART_B_QA.json",
        5_876,
        "e3ab079281be7693ab892063ee8b1af48e931894dfe93ff44fdb2fbf8043fd16",
        "PASS_COMPLETE_NATURAL_ID_ID_STRUCTURE_MATH_PROTECTED_TEX_REPAIR_LEDGER_AND_RESIDUAL_ENGLISH_QA",
    ),
    "main_translation_c_qa": sealed(
        "qa/b026-translation/R011-B026_MAIN_TRANSLATION_PART_C_QA.json",
        9_483,
        "743d912b1c24d4435f52cad1bbb4443aa0ba35158a757f63ca9fb1e43bf91bb3",
        "PASS_COMPLETE_NATURAL_ID_ID_STRUCTURE_MATH_PROTECTED_TEX_APPROVED_REPAIR_AND_RESIDUAL_ENGLISH_QA",
    ),
    "main_translation_de_qa": sealed(
        "qa/b026-translation/R011-B026_MAIN_TRANSLATION_PARTS_DE_QA.json",
        11_421,
        "0cef972d46c4fbd6b07139e583e12d4bef0b57791773f6bdbbe2be6d9f17599d",
        "PASS_COMPLETE_NATURAL_ID_ID_STRUCTURE_MATH_PROTECTED_TEX_APPROVED_REPAIR_AND_RESIDUAL_ENGLISH_QA",
    ),
    "main_translation_f_qa": sealed(
        "qa/b026-translation/R011-B026_MAIN_TRANSLATION_PART_F_QA.json",
        5_464,
        "2bfb273cc3f53337f3a19dccf03a1079faed6119ef6ccbb7b0c570ba404df507",
        "PASS_COMPLETE_NATURAL_ID_ID_STRUCTURE_MATH_PROTECTED_TEX_REPAIR_LEDGER_AND_RESIDUAL_ENGLISH_QA",
    ),
    "exercise_answer_qa": sealed(
        "qa/b026-translation/R011-B026_EXERCISES_ANSWERS_QA.json",
        9_694,
        "263e1fbf5edb6f039614708ca896120d67e3c80fba3e97fbe8e272c0485a19ec",
        "PASS_COMPLETE_NATURAL_ID_ID_EXERCISE_ANSWER_CLOSURE_STRUCTURE_MATH_REPAIRS_AND_RESIDUAL_ENGLISH_QA",
    ),
    "source_freezer": sealed(
        "scripts/freeze_b026_source.py",
        49_386,
        "92c8d803cf1a271941f193d0d45695b227b747762021f37e2cdf5167357ce397",
    ),
    "exercise_answer_verifier": sealed(
        "scripts/qa_b026_exercises_answers.py",
        28_440,
        "df2cb9339f9048f5c6ea254b8da757d29a3f2043df3d87b4935ec87ce6c35384",
    ),
    "asset_root_visual_qa": sealed(
        "qa/b026-translation/R011-B026_ASSET_ROOT_VISUAL_INSPECTION_QA.json",
        3_636,
        "9c6a6bdd7683e98204c722e9ad9a70c873d0182e557681f07b1f3d0484eedbf0",
        "PASS_ALL_8_LOCALIZED_ASSETS_VISUALLY_INSPECTED_AFTER_ONE_CORRECTION_ZERO_REMAINING_DEFECTS",
    ),
    "rejected_candidate_9adb2d37_qa": sealed(
        "qa/b026-reader/R011-B026_REJECTED_CANDIDATE_9ADB2D37_QA.json",
        2_399,
        "ed80a20039d22b550cb02a34d2312947296711846c31321fdb790f66bbc10c74",
        "REJECTED_PAGE_271_FORCED_BREAK_REFLOW_DEFECT",
        boundary_required=False,
    ),
    "rejected_candidate_5b83846d_qa": sealed(
        "qa/b026-reader/R011-B026_REJECTED_CANDIDATE_5B83846D_QA.json",
        5_357,
        "868e61393b4a18c14e8cee4efdfc10f539af5c6422a0dd97cef83afda96895b6",
        "REJECTED_PAGES_273_275_FORCED_BREAK_REFLOW_DEFECTS",
        boundary_required=False,
    ),
}

# Finished independent asset closure.  The receipt itself binds all source,
# producer, localized output, visual, rights-witness, and replay identities.
REGISTERED_ASSET_CLOSURE: dict[str, Any] | None = sealed(
    ASSET_CLOSURE_REL,
    35_730,
    "b479bb7bdacda021bee1afd7380bfdea1c98915b1a693369d4a224216b48b9c1",
    "PASS_DETERMINISTIC_ASSET_LOCALIZATION_AND_VISUAL_QA",
)

# Exact final 273-page candidate and independently replayed whole-reader QA.
# These identities were registered only after both rejected candidates were
# replaced and the final all-page visual inspection replayed with zero defects.
POST_BUILD_ROLES: dict[str, dict[str, Any]] = {
    "candidate_pdf": sealed(
        "scratch/b026-boundary-clean-reader/final/main.pdf",
        12_782_877,
        "0f61722fe01afe18552e949dfd4d3addba450c6e0337767ea2448d982012f0d6",
    ),
    "candidate_text": sealed(
        "scratch/b026-boundary-clean-reader/final/main-final.txt",
        873_719,
        "4344726ad43b62109d09aa624fed81fe34c36788213be6635a89634163f47b47",
    ),
    "build_qa": sealed(
        "scratch/b026-boundary-clean-reader/final/R011-B026_BOUNDARY_CLEAN_BUILD_QA.json",
        25_201,
        "10c91e17f19ce0a75d707b4891571e8c46a10883cfc2066edba73226e9e40b1a",
        "PASS_TWO_REPLAY_DETERMINISTIC_BOUNDARY_CLEAN_BUILD_LANGUAGE_QA_COMPLETE_READER_VISUAL_QA_PENDING",
    ),
    "source_manifest": sealed(
        "scratch/b026-boundary-clean-reader/R011-B026_BOUNDARY_CLEAN_SOURCE_MANIFEST.tsv",
        177_439,
        "858ca66c52d547eb33696ce93435b77391e3b2b72dafae29f7ca48300f4a2a97",
    ),
    "automated_reader_qa": sealed(
        "qa/b026-reader/R011-B026_AUTOMATED_READER_QA.json",
        73_670,
        "225df75fbe0b4d2c6299ee06fdf7994d56c4a6c840c264eae9a62620327ed642",
        "PASS_DETERMINISTIC_BUILD_SOURCE_STRUCTURE_PDF_AND_LANGUAGE_QA",
    ),
    "pagewise_language_qa": sealed(
        "qa/b026-reader/R011-B026_PAGEWISE_LANGUAGE_QA.json",
        110_949,
        "baaa55fe4c0ba7a4afc958487636f7e58cb5bf42c897bd585ec3c988f761d920",
        "PASS_ALL_PAGES_UTF8_BOUNDARY_CLEAN_REQUIRED_AND_RESIDUAL_ENGLISH_QA",
    ),
    "pagewise_language_qa_tsv": sealed(
        "qa/b026-reader/R011-B026_PAGEWISE_LANGUAGE_QA.tsv",
        26_042,
        "0eef616a3fe9d1bc51230a3a73314128f01dc93dffe9133f34d86b788702e290",
    ),
    "automated_visual_qa": sealed(
        "qa/b026-reader/R011-B026_AUTOMATED_VISUAL_QA.json",
        199_310,
        "299eea1e84e0062a49019c4e766d985e0ad8b49df8387b3410505fc74cdb6d5e",
        "PASS_ALL_PAGES_RENDERED_AUTOMATED_BLANK_BLACK_CLIPPING_OVERFLOW_SANITY",
    ),
    "root_visual_qa": sealed(
        "qa/b026-reader/R011-B026_ROOT_VISUAL_INSPECTION_QA.json",
        10_721,
        "75db5f3d7045059503a4d44e4306b3483c8ebc8b239c8254774a03dec26503f8",
        "PASS_ALL_273_PAGES_VISUALLY_INSPECTED_IN_ORDER_ZERO_DEFECTS",
    ),
    "reader_qa_verifier": sealed(
        "scripts/qa_b026_boundary_clean_reader.py",
        69_603,
        "2e1f7c566154dfdeb5f1d4aa4fc827c1b43fb398475a9dfaf73e8e808d90f8ee",
    ),
}


class StageGateError(RuntimeError):
    """An exact identity, lineage, status, or safety gate is unsatisfied."""


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def repo_path(relative: str) -> Path:
    token = relative.replace("\\", "/")
    pure = PurePosixPath(token)
    if not token or pure.is_absolute() or ".." in pure.parts or re.match(r"^[A-Za-z]:", token):
        raise StageGateError(f"unsafe lane-relative path: {relative!r}")
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
    size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            size += len(chunk)
            digest.update(chunk)
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": size, "sha256": digest.hexdigest()}


def verify_record(role: str, expected: dict[str, Any]) -> dict[str, Any]:
    observed = identity(repo_path(expected["path"]))
    if (observed["bytes"], observed["sha256"]) != (expected["bytes"], expected["sha256"]):
        raise StageGateError(f"{role} identity changed: {observed!r}")
    required = expected.get("required_status")
    if required is not None:
        try:
            payload = json.loads(repo_path(expected["path"]).read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise StageGateError(f"{role} is not valid UTF-8 JSON") from exc
        if payload.get("status") != required:
            raise StageGateError(f"{role} status changed")
        if expected.get("boundary_required", True) and payload.get("boundary_id") != BOUNDARY_ID:
            raise StageGateError(f"{role} boundary changed")
        observed["required_status"] = required
    return observed


def verify_base_backend() -> dict[str, Any]:
    live = identity(repo_path(BASE_BACKEND["path"]))
    exact = {key: BASE_BACKEND[key] for key in ("path", "bytes", "sha256")}
    if live == exact:
        manifest = json.loads(repo_path(BASE_BACKEND["path"]).read_text(encoding="utf-8"))
        if manifest.get("boundary_id") != BASE_BOUNDARY_ID or manifest.get("record_count") != 9_119:
            raise StageGateError("base backend is not the exact admitted B025 boundary")
        return live
    preimage = repo_path("qa/b026-backend-admission/preimages-R011-B026/manifest.json")
    frozen = identity(preimage)
    if (frozen["bytes"], frozen["sha256"]) != (BASE_BACKEND["bytes"], BASE_BACKEND["sha256"]):
        raise StageGateError("live backend advanced without the exact B025 preimage")
    try:
        manifest = json.loads(repo_path(BASE_BACKEND["path"]).read_text(encoding="utf-8"))
        receipt = json.loads(repo_path(BACKEND_ADMISSION_RECEIPT_PATH).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StageGateError("live backend is neither exact B025 nor receipted B026") from exc
    if (
        manifest.get("boundary_id") != BOUNDARY_ID
        or receipt.get("boundary_id") != BOUNDARY_ID
        or receipt.get("status") != "PASS_B026_BACKEND_ATOMIC_ADMISSION_AND_EXACT_REPLAY"
        or receipt.get("live_manifest") != live
    ):
        raise StageGateError("advanced live backend lacks an exact B026 admission receipt")
    return exact


def verify_text_inputs() -> dict[str, dict[str, Any]]:
    rows = {"base_backend": verify_base_backend()}
    rows.update({role: verify_record(role, spec) for role, spec in SEALED_TEXT_INPUTS.items()})
    checkpoint = json.loads(repo_path(SEALED_TEXT_INPUTS["text_checkpoint"]["path"]).read_text(encoding="utf-8"))
    if checkpoint.get("complete_corpus") is not False or checkpoint.get("scope", {}).get("restricted_solutions_accessed_or_invented") is not False:
        raise StageGateError("B026 text checkpoint has lost truthful partial/restricted-solution scope")
    return rows


def load_asset_closure(*, require_complete: bool = True) -> dict[str, Any] | None:
    if REGISTERED_ASSET_CLOSURE is None:
        if require_complete:
            raise StageGateError("finished B026 asset closure is not registered")
        return None
    receipt = verify_record("asset_closure", REGISTERED_ASSET_CLOSURE)
    payload = json.loads(repo_path(REGISTERED_ASSET_CLOSURE["path"]).read_text(encoding="utf-8"))
    if payload.get("boundary_id") != BOUNDARY_ID or payload.get("status") != REGISTERED_ASSET_CLOSURE.get("required_status"):
        raise StageGateError("registered B026 asset closure boundary/status changed")
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) != 8:
        raise StageGateError("asset closure must bind exactly eight localized/corrected generated PDFs")
    observed_artifacts = []
    for position, row in enumerate(artifacts, 1):
        if not isinstance(row, dict) or not isinstance(row.get("output"), dict):
            raise StageGateError(f"asset closure output {position} lacks an exact identity")
        output = row["output"]
        observed = identity(repo_path(output["path"]))
        if observed != {key: output[key] for key in ("path", "bytes", "sha256")}:
            raise StageGateError(f"localized asset output {position} changed")
        source = row.get("source")
        producer = row.get("producer")
        for label, embedded in (("source", source), ("producer", producer)):
            if not isinstance(embedded, dict) or not {"path", "bytes", "sha256"}.issubset(embedded):
                raise StageGateError(f"asset closure {position} lacks exact {label} identity")
            if identity(repo_path(embedded["path"])) != {key: embedded[key] for key in ("path", "bytes", "sha256")}:
                raise StageGateError(f"asset closure {position} {label} changed")
        observed_artifacts.append({
            "key": row.get("key"),
            "method": row.get("method"),
            "source": {key: source[key] for key in ("path", "bytes", "sha256")},
            "producer": {key: producer[key] for key in ("path", "bytes", "sha256")},
            "output": observed,
            "correction": row.get("correction"),
            "required_localized_strings": row.get("required_localized_strings", []),
            "removed_reader_visible_english_strings": row.get("removed_reader_visible_english_strings", []),
        })
    inventory = payload.get("output_inventory")
    if inventory != {
        "bytes": 243_405,
        "files": 8,
        "inventory_sha256": "d8da29bb513ba4d30ceb2d0aab4504bea8c1b8b1a766a41a74e658446c186558",
    }:
        raise StageGateError("asset output inventory changed")
    rights = payload.get("rights", {}).get("rissos_dolphin", {})
    dolphin = rights.get("source")
    if not isinstance(dolphin, dict) or not {"path", "bytes", "sha256"}.issubset(dolphin):
        raise StageGateError("asset closure lacks the exact byte-identical dolphin identity")
    observed_dolphin = identity(repo_path(dolphin["path"]))
    if observed_dolphin != {key: dolphin[key] for key in ("path", "bytes", "sha256")}:
        raise StageGateError("dolphin bytes changed")
    if dolphin["bytes"] != 72_046 or dolphin["sha256"] != "591d0ba9d9a228e58f2e8841536b826847f219d68cf791d6740986b7768ee200":
        raise StageGateError("dolphin reuse is not the exact upstream CC BY 2.0 photograph")
    witness = rights.get("rights_witness")
    if not isinstance(witness, dict) or identity(repo_path(witness["path"])) != {key: witness[key] for key in ("path", "bytes", "sha256")}:
        raise StageGateError("Mike Baird rights witness changed")
    if rights.get("source_preserved_byte_identical") is not True or rights.get("rights_resolution") != "CC-BY-2.0":
        raise StageGateError("dolphin byte-preservation or rights resolution changed")
    montage = payload.get("render_qa", {}).get("montage")
    if not isinstance(montage, dict) or identity(repo_path(montage["path"])) != {key: montage[key] for key in ("path", "bytes", "sha256")}:
        raise StageGateError("asset visual-QA montage changed")
    if montage.get("sha256") != "acdbf630b8bd3c3facd1aada13779b8f3daf374408afac424d237d6e900e6618":
        raise StageGateError("asset visual-QA montage identity is not registered")
    script = payload.get("provenance", {}).get("script")
    if not isinstance(script, dict) or identity(repo_path(script["path"])) != {key: script[key] for key in ("path", "bytes", "sha256")}:
        raise StageGateError("asset localization script changed")
    return {
        "receipt": receipt,
        "artifacts": observed_artifacts,
        "output_inventory": inventory,
        "dolphin_reuse": observed_dolphin,
        "dolphin_rights_witness": {key: witness[key] for key in ("path", "bytes", "sha256")},
        "dolphin_attribution": rights.get("required_attribution_verbatim"),
        "visual_montage": {key: montage[key] for key in ("path", "bytes", "sha256")},
        "localizer": {key: script[key] for key in ("path", "bytes", "sha256")},
    }


def load_bindings(*, require_complete: bool = True) -> dict[str, Any] | None:
    if not BINDINGS_PATH.is_file():
        if require_complete:
            raise StageGateError(f"post-build binding is absent: {BINDINGS_REL}")
        return None
    if not POST_BUILD_ROLES:
        raise StageGateError("post-build role contract is not registered")
    try:
        payload = json.loads(BINDINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StageGateError("post-build binding is not valid UTF-8 JSON") from exc
    if payload.get("boundary_id") != BOUNDARY_ID or payload.get("status") != "PASS_EXACT_B026_POST_BUILD_IDENTITIES_BOUND":
        raise StageGateError("post-build binding boundary/status changed")
    if payload.get("sealed_text_inputs") != verify_text_inputs():
        raise StageGateError("post-build binding no longer matches sealed text inputs")
    asset = load_asset_closure(require_complete=True)
    if payload.get("asset_closure") != asset:
        raise StageGateError("post-build binding no longer matches the exact asset closure")
    outputs = payload.get("post_build_outputs")
    if not isinstance(outputs, dict) or set(outputs) != set(POST_BUILD_ROLES):
        raise StageGateError("post-build output roles changed")
    for role, spec in POST_BUILD_ROLES.items():
        row = outputs[role]
        observed = verify_record(role, spec)
        observed_identity = {key: observed[key] for key in ("path", "bytes", "sha256")}
        expected_identity = {key: spec[key] for key in ("path", "bytes", "sha256")}
        if observed_identity != expected_identity:
            raise StageGateError(f"registered post-build identity changed: {role}")
        if observed_identity != {key: row[key] for key in ("path", "bytes", "sha256")}:
            raise StageGateError(f"bound post-build output changed: {role}")
        required = spec.get("required_status")
        if required is not None and row.get("required_status") != required:
            raise StageGateError(f"bound post-build status contract changed: {role}")
    pages = outputs["candidate_pdf"].get("pages")
    if not isinstance(pages, int) or pages <= 260:
        raise StageGateError("B026 reader does not extend the 260-page B025 artifact")
    expected_visual = POST_BUILD_ROLES["root_visual_qa"].get("required_status")
    if (
        outputs["root_visual_qa"].get("required_status") != expected_visual
        or not re.fullmatch(rf"PASS_ALL_{pages}_PAGES_VISUALLY_INSPECTED(?:_IN_ORDER)?_ZERO_DEFECTS", str(expected_visual))
    ):
        raise StageGateError("root visual status is not bound to every reader page")
    return payload


def offline_self_check(component: str) -> dict[str, Any]:
    text_rows = verify_text_inputs()
    asset = load_asset_closure(require_complete=False)
    binding = load_bindings(require_complete=False) if POST_BUILD_ROLES else None
    pending = []
    if asset is None:
        pending.append("finished eight-figure localization/correction closure plus exact dolphin reuse")
    if not POST_BUILD_ROLES:
        pending.append("exact B026 reader/build/whole-reader-QA role registration")
    elif binding is None:
        pending.append("exact B026 post-build identity binding")
    return {
        "$schema": "interlanguage.r011-b026-pipeline-self-check/v1",
        "boundary_id": BOUNDARY_ID,
        "component": component,
        "status": "PASS_STATIC_B026_INPUTS_ALL_BINDINGS_PRESENT" if not pending else "PASS_STATIC_B026_TEXT_INPUTS_FAIL_CLOSED_BINDINGS_PENDING",
        "sealed_text_input_count": len(text_rows),
        "asset_closure": asset["receipt"] if asset else None,
        "post_build_binding": identity(BINDINGS_PATH) if binding else None,
        "pending": pending,
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
