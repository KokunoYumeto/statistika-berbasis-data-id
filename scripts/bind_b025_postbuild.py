#!/usr/bin/env python3
"""Seal exact B025 reader/build/whole-reader-QA identities without other mutation."""

from __future__ import annotations

import argparse
import json
import os

from pypdf import PdfReader

from b025_pipeline_contract import (
    BINDINGS_PATH,
    BOUNDARY_ID,
    MODEL,
    POST_BUILD_ROLES,
    StageGateError,
    canonical,
    identity,
    load_bindings,
    offline_self_check,
    repo_path,
    verify_sealed_inputs,
)


def _json_status(role: str, spec: dict, pages: int) -> str | None:
    required = spec.get("required_status")
    if role == "root_visual_qa":
        required = f"PASS_ALL_{pages}_PAGES_VISUALLY_INSPECTED_ZERO_DEFECTS"
    if required is None:
        return None
    payload = json.loads(repo_path(spec["path"]).read_text(encoding="utf-8"))
    if payload.get("boundary_id") != BOUNDARY_ID or payload.get("status") != required:
        raise StageGateError(f"{role} boundary/status mismatch")
    return required


def _require_embedded_identity(context: str, embedded: object, expected: dict) -> None:
    """Require a receipt's embedded identity to equal the already observed file."""
    keys = ("path", "bytes", "sha256")
    if not isinstance(embedded, dict) or {key: embedded.get(key) for key in keys} != {
        key: expected[key] for key in keys
    }:
        raise StageGateError(f"{context} does not bind the exact required identity")


def projection() -> dict:
    sealed_rows = verify_sealed_inputs()
    pdf_path = repo_path(POST_BUILD_ROLES["candidate_pdf"]["path"])
    pdf = identity(pdf_path)
    pages = len(PdfReader(str(pdf_path)).pages)
    if pages <= 253:
        raise StageGateError(f"B025 candidate did not extend B024 page extent: {pages}")
    outputs = {}
    for role, spec in POST_BUILD_ROLES.items():
        row = identity(repo_path(spec["path"]))
        status = _json_status(role, spec, pages)
        if status is not None:
            row["required_status"] = status
        if role == "candidate_pdf":
            row["pages"] = pages
        outputs[role] = row
    build = json.loads(repo_path(POST_BUILD_ROLES["build_qa"]["path"]).read_text(encoding="utf-8"))
    for key, role in (("candidate_artifact", "candidate_pdf"), ("candidate_text", "candidate_text")):
        embedded = build.get(key)
        wanted = {k: outputs[role][k] for k in ("path", "bytes", "sha256")}
        if embedded != wanted:
            raise StageGateError(f"build receipt does not bind exact {role}")
    if build.get("page_count") != pages or build.get("determinism", {}).get("pdf_byte_identical") is not True or build.get("determinism", {}).get("text_byte_identical") is not True:
        raise StageGateError("build receipt lacks exact two-replay/page closure")
    build_manifest = build.get("source_manifest", {})
    if (
        not isinstance(build_manifest, dict)
        or build_manifest.get("path") != outputs["source_manifest"]["path"]
        or build_manifest.get("sha256") != outputs["source_manifest"]["sha256"]
        or build_manifest.get("inventory_sha256") != outputs["source_manifest"]["sha256"]
        or build_manifest.get("files") != 1_220
        or build_manifest.get("bytes") != 41_931_754
    ):
        raise StageGateError("build receipt source manifest closure changed")
    staged = build.get("staged", {})
    exact_staging = {
        "section_a_translation": staged.get("chapter_fragments", [None, None])[0],
        "section_b_translation": staged.get("chapter_fragments", [None, None])[1],
        "exercise_translation": staged.get("exercises"),
        "public_answer_translation": staged.get("public_answers"),
        "o001_gap_ledger": staged.get("o001_gaps"),
        "localized_chart": staged.get("localized_ipod_chart", {}).get("localized_chart"),
        "localized_chart_qa": staged.get("localized_ipod_chart", {}).get("chart_qa"),
        "localized_chart_visual_qa": staged.get("localized_ipod_chart", {}).get("chart_visual_qa"),
    }
    for role, embedded in exact_staging.items():
        wanted = {key: sealed_rows[role][key] for key in ("path", "bytes", "sha256")}
        if not isinstance(embedded, dict) or {key: embedded.get(key) for key in wanted} != wanted:
            raise StageGateError(f"build receipt does not bind the final sealed {role}")
    translation_qa = build.get("inputs", {}).get("translation_qa", {})
    for role, embedded_role in (
        ("main_translation_a_qa", "main_a"),
        ("main_translation_b_qa", "main_b"),
        ("exercise_answer_qa", "exercise_answers"),
        ("independent_translation_qa", "independent_audit"),
        ("independent_translation_verifier", "independent_verifier"),
    ):
        wanted = {key: sealed_rows[role][key] for key in ("path", "bytes", "sha256")}
        embedded = translation_qa.get(embedded_role)
        if not isinstance(embedded, dict) or {key: embedded.get(key) for key in wanted} != wanted:
            raise StageGateError(f"build receipt does not bind final translation QA: {role}")
    receipt_payloads = {
        role: json.loads(repo_path(POST_BUILD_ROLES[role]["path"]).read_text(encoding="utf-8"))
        for role in ("pagewise_language_qa", "automated_visual_qa", "root_visual_qa")
    }
    for role, payload in receipt_payloads.items():
        learner = payload.get("learner_pdf") or payload.get("build_binding") or {}
        if learner.get("sha256") != pdf["sha256"] or learner.get("bytes") != pdf["bytes"]:
            raise StageGateError(f"{role} does not bind the exact candidate reader")
        observed_pages = payload.get("page_count", payload.get("learner_reader_total_pages"))
        if observed_pages != pages:
            raise StageGateError(f"{role} page count differs from candidate")
        if role in {"pagewise_language_qa", "root_visual_qa"} and payload.get("complete_corpus") is not False:
            raise StageGateError(f"{role} does not preserve truthful partial-corpus status")

    pagewise = receipt_payloads["pagewise_language_qa"]
    _require_embedded_identity("pagewise receipt build QA", pagewise.get("build_qa"), outputs["build_qa"])
    _require_embedded_identity("pagewise receipt extracted text", pagewise.get("extracted_text"), outputs["candidate_text"])
    _require_embedded_identity(
        "pagewise receipt source manifest",
        pagewise.get("build_binding", {}).get("source_manifest", {}).get("identity"),
        outputs["source_manifest"],
    )
    _require_embedded_identity(
        "pagewise receipt independent audit",
        pagewise.get("independent_translation_audit"),
        sealed_rows["independent_translation_qa"],
    )
    _require_embedded_identity(
        "pagewise receipt automated visual QA",
        pagewise.get("automated_visual_qa", {}).get("receipt"),
        outputs["automated_visual_qa"],
    )

    automated = receipt_payloads["automated_visual_qa"]
    _require_embedded_identity(
        "automated visual receipt localized chart",
        automated.get("localized_chart_source"),
        sealed_rows["localized_chart"],
    )

    root_visual = receipt_payloads["root_visual_qa"]
    _require_embedded_identity(
        "root visual receipt pagewise QA",
        root_visual.get("pagewise_language_receipt"),
        outputs["pagewise_language_qa"],
    )
    _require_embedded_identity(
        "root visual receipt automated QA",
        root_visual.get("automated_visual_receipt"),
        outputs["automated_visual_qa"],
    )
    _require_embedded_identity(
        "root visual receipt independent audit",
        root_visual.get("independent_translation_audit"),
        sealed_rows["independent_translation_qa"],
    )
    for role, payload in receipt_payloads.items():
        provenance = payload.get("translation_provenance", payload.get("production_model"))
        if provenance != MODEL:
            raise StageGateError(f"{role} has changed production-model provenance")
    return {
        "$schema": "interlanguage.r011-b025-post-build-bindings/v1",
        "boundary_id": BOUNDARY_ID,
        "status": "PASS_EXACT_B025_POST_BUILD_IDENTITIES_BOUND",
        "model_identification": MODEL,
        "sealed_inputs": sealed_rows,
        "post_build_outputs": outputs,
        "reader_page_count_is_artifact_extent_not_complete_corpus_progress": True,
        "complete_corpus": False,
        "restricted_solutions_accessed_or_invented": False,
        "publication_performed": False,
        "network_used": False,
        "credentials_accessed": False,
        "git_used": False,
        "upstream_contact": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--self-check", action="store_true")
    mode.add_argument("--probe", action="store_true")
    mode.add_argument("--bind", action="store_true")
    mode.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        print(json.dumps(offline_self_check("b025-postbuild-binder"), ensure_ascii=False, sort_keys=True))
        return 0
    if args.verify:
        bound = load_bindings(require_complete=True)
        print(json.dumps({"status": "PASS_EXACT_B025_POST_BUILD_BINDING_REPLAY", "binding": identity(BINDINGS_PATH), "reader": bound["post_build_outputs"]["candidate_pdf"]}, ensure_ascii=False, sort_keys=True))
        return 0
    payload = projection()
    if args.probe:
        print(json.dumps({**payload, "status": "PASS_B025_POST_BUILD_BINDING_PROBE_NO_WRITES", "writes_performed": False}, ensure_ascii=False, sort_keys=True))
        return 0
    raw = canonical(payload)
    BINDINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if BINDINGS_PATH.exists() and BINDINGS_PATH.read_bytes() != raw:
        raise StageGateError("refusing to replace a different B025 post-build binding")
    temporary = BINDINGS_PATH.with_suffix(".json.tmp")
    if temporary.exists():
        raise StageGateError(f"refusing stale binding temporary: {temporary}")
    temporary.write_bytes(raw)
    os.replace(temporary, BINDINGS_PATH)
    load_bindings(require_complete=True)
    print(json.dumps({"status": payload["status"], "binding": identity(BINDINGS_PATH)}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except StageGateError as exc:
        raise SystemExit(f"REFUSED: {exc}")
