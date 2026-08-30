#!/usr/bin/env python3
"""Seal exact R011-B026 reader/build/whole-reader-QA identities.

The binder writes only the B026 post-build binding.  Its projection first runs
the independent whole-reader verifier in read-only replay mode, then requires
exact cross-links among the build, text, asset, pagewise, structural, automated
visual, and root visual receipts.  It is inert until every registered role is
present and final.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from typing import Any

from pypdf import PdfReader

from b026_pipeline_contract import (
    BINDINGS_PATH,
    BOUNDARY_ID,
    MODEL,
    POST_BUILD_ROLES,
    SEALED_TEXT_INPUTS,
    StageGateError,
    canonical,
    identity,
    load_asset_closure,
    load_bindings,
    offline_self_check,
    repo_path,
    verify_record,
    verify_text_inputs,
)


def exact_projection(value: object, expected: object, context: str) -> None:
    keys = ("path", "bytes", "sha256")
    if (
        not isinstance(value, dict)
        or not isinstance(expected, dict)
        or not all(key in expected for key in keys)
        or {key: value.get(key) for key in keys} != {key: expected[key] for key in keys}
    ):
        raise StageGateError(f"{context} does not bind the exact required identity")


def load_json(role: str) -> dict[str, Any]:
    try:
        value = json.loads(repo_path(POST_BUILD_ROLES[role]["path"]).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StageGateError(f"{role} is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise StageGateError(f"{role} JSON is not an object")
    return value


def run_reader_replay(expected_pages: int) -> dict[str, Any]:
    verifier = repo_path(POST_BUILD_ROLES["reader_qa_verifier"]["path"])
    completed = subprocess.run(
        [sys.executable, str(verifier), "--verify"],
        cwd=str(repo_path(".")),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout)[-4_000:]
        raise StageGateError(f"independent whole-reader replay failed: {detail}")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise StageGateError("whole-reader verifier did not emit JSON") from exc
    if payload.get("status") != "PASS_EXACT_B026_WHOLE_READER_QA_REPLAY" or payload.get("page_count") != expected_pages:
        raise StageGateError("whole-reader verifier replay status/page count changed")
    return payload


def projection() -> dict[str, Any]:
    if not POST_BUILD_ROLES:
        raise StageGateError("exact B026 reader/build/whole-reader-QA role contract is not registered")
    text_inputs = verify_text_inputs()
    asset = load_asset_closure(require_complete=True)
    pdf_path = repo_path(POST_BUILD_ROLES["candidate_pdf"]["path"])
    pages = len(PdfReader(str(pdf_path)).pages)
    if pages <= 260:
        raise StageGateError(f"B026 candidate page count changed: {pages}")
    replay = run_reader_replay(pages)
    outputs: dict[str, dict[str, Any]] = {}
    for role, spec in POST_BUILD_ROLES.items():
        row = verify_record(role, spec)
        if role == "candidate_pdf":
            row["pages"] = pages
        outputs[role] = row

    build = load_json("build_qa")
    exact_projection(build.get("candidate_artifact"), outputs["candidate_pdf"], "build candidate PDF")
    exact_projection(build.get("candidate_text"), outputs["candidate_text"], "build candidate text")
    if build.get("page_count") != pages:
        raise StageGateError("build receipt page count differs")
    determinism = build.get("determinism", {})
    if not all(determinism.get(key) is True for key in ("pdf_byte_identical", "text_byte_identical", "trailer_ids_equal", "pass3_pass4_stable_in_each_replay")):
        raise StageGateError("build receipt lacks exact two-replay determinism")
    manifest = build.get("source_manifest", {})
    if (
        manifest.get("path") != outputs["source_manifest"]["path"]
        or manifest.get("sha256") != outputs["source_manifest"]["sha256"]
        or manifest.get("inventory_sha256") != outputs["source_manifest"]["sha256"]
        or manifest.get("files") != 1_222
        or not isinstance(manifest.get("bytes"), int)
        or manifest.get("bytes") <= 41_931_754
    ):
        raise StageGateError("build source-manifest closure changed")
    if build.get("complete_corpus") is not False or build.get("restricted_solutions_accessed_or_invented") is not False:
        raise StageGateError("build receipt lost truthful partial/restricted-solution scope")

    source_blueprint = build.get("inputs", {}).get("source_blueprint", {}).get("blueprint")
    exact_projection(source_blueprint, text_inputs["source_blueprint"], "build source blueprint")
    translation = build.get("inputs", {}).get("translation_receipts", {})
    main_fragments = translation.get("main_fragments")
    if not isinstance(main_fragments, list) or len(main_fragments) != 6:
        raise StageGateError("build receipt does not bind six main translation fragments")
    for position, role in enumerate(("main_translation_a", "main_translation_b", "main_translation_c", "main_translation_d", "main_translation_e", "main_translation_f")):
        exact_projection(main_fragments[position], text_inputs[role], f"build {role}")
    for embedded, role in (
        (translation.get("exercises"), "exercise_translation"),
        (translation.get("public_answers"), "public_answer_translation"),
        (translation.get("o001_gap_ledger"), "o001_gap_ledger"),
        (translation.get("exercise_answer_receipt"), "exercise_answer_qa"),
    ):
        exact_projection(embedded, text_inputs[role], f"build {role}")
    main_receipts = translation.get("main_receipts")
    if not isinstance(main_receipts, list) or len(main_receipts) != 5:
        raise StageGateError("build receipt main QA receipt closure changed")
    for position, role in enumerate(("main_translation_a_qa", "main_translation_b_qa", "main_translation_c_qa", "main_translation_de_qa", "main_translation_f_qa")):
        exact_projection(main_receipts[position], text_inputs[role], f"build {role}")
    asset_gate = build.get("asset_gate", {})
    exact_projection(asset_gate.get("receipt"), asset["receipt"], "build asset closure")
    exact_projection(asset_gate.get("root_visual_receipt"), text_inputs["asset_root_visual_qa"], "build asset root visual QA")
    if asset_gate.get("output_inventory") != asset["output_inventory"]:
        raise StageGateError("build asset inventory differs")
    installed_assets = asset_gate.get("assets")
    if not isinstance(installed_assets, list) or len(installed_assets) != 8:
        raise StageGateError("build asset installation closure changed")
    expected_asset_outputs = {row["output"]["path"]: row["output"] for row in asset["artifacts"]}
    for row in installed_assets:
        wanted = expected_asset_outputs.get(row.get("path"))
        if wanted is None:
            raise StageGateError(f"build installed asset is not in the sealed closure: {row.get('path')}")
        exact_projection(row, wanted, f"build installed asset {row.get('path')}")

    automated_reader = load_json("automated_reader_qa")
    exact_projection(automated_reader.get("learner_pdf"), outputs["candidate_pdf"], "automated reader PDF")
    exact_projection(automated_reader.get("extracted_text"), outputs["candidate_text"], "automated reader text")
    if automated_reader.get("learner_reader_total_pages") != pages or automated_reader.get("complete_corpus") is not False:
        raise StageGateError("automated reader page/scope closure changed")
    exact_projection(automated_reader.get("build_binding", {}).get("build_receipt"), outputs["build_qa"], "automated reader build receipt")
    source_manifest_binding = automated_reader.get("build_binding", {}).get("source_manifest", {})
    if source_manifest_binding.get("path") != outputs["source_manifest"]["path"] or source_manifest_binding.get("sha256") != outputs["source_manifest"]["sha256"]:
        raise StageGateError("automated reader source-manifest binding changed")

    pagewise = load_json("pagewise_language_qa")
    if pagewise.get("page_count") != pages or pagewise.get("complete_corpus") is not False or pagewise.get("untranslated_instructional_or_exercise_prose_pages") != 0:
        raise StageGateError("pagewise language scope/count changed")
    visual = load_json("automated_visual_qa")
    exact_projection(visual.get("learner_pdf"), outputs["candidate_pdf"], "automated visual PDF")
    if visual.get("page_count") != pages or visual.get("defect_count") != 0 or visual.get("all_pages_rendered") is not True:
        raise StageGateError("automated visual closure changed")
    root_visual = load_json("root_visual_qa")
    exact_projection(root_visual.get("learner_pdf"), outputs["candidate_pdf"], "root visual PDF")
    if root_visual.get("page_count") != pages or root_visual.get("all_pages_visually_inspected") is not True or root_visual.get("defect_count") != 0 or root_visual.get("complete_corpus") is not False:
        raise StageGateError("root visual whole-reader closure changed")
    if root_visual.get("contact_sheet_coverage") != [1, pages]:
        raise StageGateError("root visual contact-sheet coverage changed")

    return {
        "$schema": "interlanguage.r011-b026-post-build-bindings/v1",
        "boundary_id": BOUNDARY_ID,
        "status": "PASS_EXACT_B026_POST_BUILD_IDENTITIES_BOUND",
        "model_identification": MODEL,
        "sealed_text_inputs": text_inputs,
        "asset_closure": asset,
        "post_build_outputs": outputs,
        "whole_reader_verifier_replay": replay,
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
        result = offline_self_check("b026-postbuild-binder")
    elif args.verify:
        bound = load_bindings(require_complete=True)
        result = {"status": "PASS_EXACT_B026_POST_BUILD_BINDING_REPLAY", "binding": identity(BINDINGS_PATH), "reader": bound["post_build_outputs"]["candidate_pdf"]}
    else:
        payload = projection()
        if args.probe:
            result = {**payload, "status": "PASS_B026_POST_BUILD_BINDING_PROBE_NO_WRITES", "writes_performed": False}
        else:
            raw = canonical(payload)
            BINDINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
            if BINDINGS_PATH.exists() and BINDINGS_PATH.read_bytes() != raw:
                raise StageGateError("refusing to replace a different B026 post-build binding")
            temporary = BINDINGS_PATH.with_suffix(".json.tmp")
            if temporary.exists():
                raise StageGateError(f"refusing stale binding temporary: {temporary}")
            temporary.write_bytes(raw)
            os.replace(temporary, BINDINGS_PATH)
            load_bindings(require_complete=True)
            result = {"status": payload["status"], "binding": identity(BINDINGS_PATH), "reader": payload["post_build_outputs"]["candidate_pdf"]}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except StageGateError as exc:
        raise SystemExit(f"REFUSED: {exc}")
