#!/usr/bin/env python3
"""Prepare a bounded B025 release-input contract without packaging/publishing."""

from __future__ import annotations

import argparse
import json
import os

from b025_pipeline_contract import (
    BASE_ADMISSION,
    BASE_BACKEND,
    BASE_REPLAY,
    BOUNDARY_ID,
    CONFIG_PATH,
    FINAL_READER_PATH,
    GITHUB_TAG,
    MODEL,
    NEXT_BOUNDARY_ID,
    PRIOR_GITHUB_RECEIPT,
    PRIOR_ZENODO_RECEIPT,
    PROMOTION_RECEIPT_PATH,
    RELEASE_DATE,
    RELEASE_ID,
    StageGateError,
    VERSION,
    VERSION_LABEL,
    canonical,
    identity,
    load_bindings,
    offline_self_check,
    repo_path,
    verify_record,
)


def projection() -> dict:
    binding = load_bindings(require_complete=True)
    reader = identity(repo_path(FINAL_READER_PATH))
    candidate = binding["post_build_outputs"]["candidate_pdf"]
    if (reader["bytes"], reader["sha256"]) != (candidate["bytes"], candidate["sha256"]):
        raise StageGateError("stable B025 reader differs from bound candidate")
    promotion = repo_path(PROMOTION_RECEIPT_PATH)
    if not promotion.is_file():
        raise StageGateError("B025 reader promotion receipt is absent")
    backend = identity(repo_path(BASE_BACKEND["path"]))
    backend_manifest = json.loads(repo_path(BASE_BACKEND["path"]).read_text(encoding="utf-8"))
    if backend_manifest.get("boundary_id") != BOUNDARY_ID:
        raise StageGateError("B025 backend is not admitted")
    for relative in ("qa/b025-backend-admission/R011-B025_BACKEND_ADMISSION_RECEIPT.json", "qa/b025-backend-admission/R011-B025_BACKEND_REPLAY.json"):
        if not repo_path(relative).is_file():
            raise StageGateError(f"B025 backend receipt absent: {relative}")
    pages = candidate["pages"]
    return {
        "$schema": "r011-b025-release-inputs/v1",
        "boundary_id": BOUNDARY_ID,
        "release_id": RELEASE_ID,
        "version": VERSION,
        "version_label": VERSION_LABEL,
        "release_date": RELEASE_DATE,
        "status": "READY_FOR_PACKAGING",
        "model_identification": MODEL,
        "license": "CC BY-SA 3.0 Unported",
        "license_id": "cc-by-sa-3.0",
        "authority": {"title": "OpenIntro Statistics, Fourth Edition", "derivative_title": "Statistika Berbasis Data", "repository": "https://github.com/OpenIntroStat/openintro-statistics", "reader": "https://www.openintro.org/book/os/", "commit": "fee25091fb24e89c36296fd67c48c1fcf7a93b6e", "tree": "d61cc601e7d97759ce805900520f784d02a0489e"},
        "coverage": {
            "completion_state": "partial", "complete_corpus": False,
            "learner_reader_pages": pages, "accepted_indonesian_reader_pages": pages,
            "untranslated_instructional_or_exercise_prose_pages": 0,
            "through": "Bab 6, Bagian 6.4 Uji independensi pada tabel dua arah",
            "exercise_ids": list(range(1, 39)), "public_answer_ids": list(range(1, 38, 2)),
            "o001_gap_ids": list(range(2, 39, 2)), "restricted_solutions_used": False,
            "source_closure_counted_as_learner_output": False,
            "page_count_is_artifact_extent_not_complete_corpus_progress": True,
        },
        "next_cursor": {"boundary_id": NEXT_BOUNDARY_ID, "authority_path": "ch_inference_for_means/TeX/ch_inference_for_means.tex", "authority_line": 1, "first_section_line": 29, "first_label_line": 32, "source_order": "Bab 7"},
        "inputs": {
            "post_build_binding": identity(repo_path("qa/b025-pipeline/R011-B025_POST_BUILD_BINDINGS.json")),
            "reader": reader, "reader_promotion": identity(promotion), "backend_manifest": backend,
            "backend_admission": identity(repo_path("qa/b025-backend-admission/R011-B025_BACKEND_ADMISSION_RECEIPT.json")),
            "backend_replay": identity(repo_path("qa/b025-backend-admission/R011-B025_BACKEND_REPLAY.json")),
            "prior_zenodo_receipt": verify_record("prior_zenodo_receipt", PRIOR_ZENODO_RECEIPT),
            "prior_github_receipt": verify_record("prior_github_receipt", PRIOR_GITHUB_RECEIPT),
            **binding["sealed_inputs"], **binding["post_build_outputs"],
        },
        "destinations": {
            "zenodo": {"concept_doi": "10.5281/zenodo.22059801", "concept_record_id": 22059801, "prior_record_id": PRIOR_ZENODO_RECEIPT["record_id"], "prior_doi": PRIOR_ZENODO_RECEIPT["doi"], "route": "existing_concept_new_version_only"},
            "github": {"owner": "KokunoYumeto", "repository": "statistika-berbasis-data-id", "default_branch": "main", "tag": GITHUB_TAG, "prior_tag": PRIOR_GITHUB_RECEIPT["tag"], "prior_release_commit": PRIOR_GITHUB_RECEIPT["commit"], "prerelease": True, "tree_mode": "exact_fresh_tree_from_bounded_allowlist"},
        },
        "publication_contract": {"reader_first": True, "access": "public_open_downloads_enabled", "collision_preflight_required": True, "anonymous_inventory_readback_required": True, "anonymous_every_file_sha256_readback_required": True, "credentials_runtime_only": True, "local_git_forbidden": True, "upstream_contact": False},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--self-check", action="store_true")
    mode.add_argument("--probe", action="store_true")
    mode.add_argument("--prepare", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        result = offline_self_check("b025-release-preparer")
    else:
        payload = projection()
        if args.probe:
            result = {**payload, "status": "PASS_B025_RELEASE_PREPARATION_PROBE_NO_WRITES", "writes_performed": False}
        else:
            raw = canonical(payload)
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            if CONFIG_PATH.exists() and CONFIG_PATH.read_bytes() != raw:
                raise StageGateError("refusing to replace different B025 release inputs")
            temporary = CONFIG_PATH.with_suffix(".json.tmp")
            if temporary.exists():
                raise StageGateError(f"refusing stale release-input temporary: {temporary}")
            temporary.write_bytes(raw)
            os.replace(temporary, CONFIG_PATH)
            result = {"status": "PASS_B025_RELEASE_INPUTS_EXACTLY_BOUND", "config": identity(CONFIG_PATH)}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except StageGateError as exc:
        raise SystemExit(f"REFUSED: {exc}")
