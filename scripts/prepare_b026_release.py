#!/usr/bin/env python3
"""Prepare the exact R011-B026 release-input contract without packaging."""

from __future__ import annotations

import argparse
import json
import os

from b026_release_contract import (
    BOUNDARY_ID,
    CONFIG_PATH,
    FINAL_READER_PATH,
    GITHUB_TAG,
    MODEL,
    NEXT_BOUNDARY_ID,
    PRIOR_GITHUB_RECEIPT,
    PRIOR_ZENODO_RECEIPT,
    RELEASE_DATE,
    RELEASE_ID,
    StageGateError,
    UPSTREAM_COMMIT,
    UPSTREAM_TREE,
    VERSION,
    VERSION_LABEL,
    canonical,
    identity,
    offline_release_self_check,
    release_ready,
    repo_path,
)


def projection(*, require_complete: bool) -> dict:
    ready = release_ready(require_complete=require_complete)
    if ready is None:
        return offline_release_self_check("b026-release-preparer")
    binding = ready["binding"]
    candidate = binding["post_build_outputs"]["candidate_pdf"]
    pages = candidate["pages"]
    if pages <= 260:
        raise StageGateError("B026 reader does not extend B025")
    reader = identity(repo_path(FINAL_READER_PATH))
    if (reader["bytes"], reader["sha256"]) != (
        candidate["bytes"], candidate["sha256"],
    ):
        raise StageGateError("stable B026 reader differs from bound candidate")
    return {
        "$schema": "r011-b026-release-inputs/v1",
        "boundary_id": BOUNDARY_ID,
        "release_id": RELEASE_ID,
        "version": VERSION,
        "version_label": VERSION_LABEL,
        "release_date": RELEASE_DATE,
        "status": "READY_FOR_PACKAGING",
        "model_identification": MODEL,
        "license": "CC BY-SA 3.0 Unported with component overrides",
        "license_id": "cc-by-sa-3.0",
        "authority": {
            "title": "OpenIntro Statistics, Fourth Edition",
            "derivative_title": "Statistika Berbasis Data",
            "repository": "https://github.com/OpenIntroStat/openintro-statistics",
            "reader": "https://www.openintro.org/book/os/",
            "commit": UPSTREAM_COMMIT,
            "tree": UPSTREAM_TREE,
        },
        "coverage": {
            "completion_state": "partial",
            "complete_corpus": False,
            "learner_reader_pages": pages,
            "accepted_indonesian_reader_pages": pages,
            "untranslated_instructional_or_exercise_prose_pages": 0,
            "through": (
                "Bab 7, Bagian 7.1 Rata-rata satu sampel dengan distribusi t"
            ),
            "cumulative_prior_coverage": (
                "Materi Bahasa Indonesia yang diterima sebelumnya melalui Bab 6 "
                "Bagian 6.4, termasuk seluruh cakupan latihan/jawaban/O001 pada "
                "setiap batas yang telah diterbitkan."
            ),
            "current_chapter": 7,
            "current_section": "7.1",
            "current_chapter_exercise_ids": list(range(1, 15)),
            "current_chapter_public_answer_ids": list(range(1, 14, 2)),
            "current_chapter_o001_gap_ids": list(range(2, 15, 2)),
            "restricted_solutions_used": False,
            "source_closure_counted_as_learner_output": False,
            "page_count_is_artifact_extent_not_complete_corpus_progress": True,
        },
        "next_cursor": {
            "boundary_id": NEXT_BOUNDARY_ID,
            "authority_path": (
                "ch_inference_for_means/TeX/ch_inference_for_means.tex"
            ),
            "authority_line": 1059,
            "section": "7.2",
            "label": "pairedData",
            "label_line": 1060,
            "source_order": "Bab 7",
        },
        "inputs": {
            "post_build_binding": ready["binding_identity"],
            "reader": reader,
            "reader_promotion": ready["promotion"]["receipt"],
            "backend_manifest": ready["backend"]["manifest"],
            "backend_admission": ready["backend"]["admission"],
            "backend_replay": ready["backend"]["replay"],
            "asset_closure": ready["asset_closure"]["receipt"],
            "prior_zenodo_receipt": ready["prior_lineages"]["zenodo"],
            "prior_github_receipt": ready["prior_lineages"]["github"],
            "sealed_text_inputs": binding["sealed_text_inputs"],
            "post_build_outputs": binding["post_build_outputs"],
        },
        "component_rights": {
            "upstream_text_generated_figures_code_and_translation": "CC BY-SA 3.0",
            "rissos_dolphin_photo": {
                "license": "CC BY 2.0",
                "creator": "Mike Baird",
                "source": "http://www.bairdphotos.com/",
                "preserved_byte_identical": True,
                "identity": ready["asset_closure"]["dolphin_reuse"],
                "rights_witness": ready["asset_closure"]["dolphin_rights_witness"],
            },
            "branding_excluded": True,
        },
        "destinations": {
            "zenodo": {
                "concept_doi": "10.5281/zenodo.22059801",
                "concept_record_id": 22_059_801,
                "prior_record_id": PRIOR_ZENODO_RECEIPT["record_id"],
                "prior_doi": PRIOR_ZENODO_RECEIPT["doi"],
                "route": "existing_concept_new_version_only",
            },
            "github": {
                "owner": "KokunoYumeto",
                "repository": "statistika-berbasis-data-id",
                "default_branch": "main",
                "tag": GITHUB_TAG,
                "prior_tag": PRIOR_GITHUB_RECEIPT["tag"],
                "prior_release_commit": PRIOR_GITHUB_RECEIPT["commit"],
                "prerelease": True,
                "tree_mode": "exact_fresh_tree_from_bounded_allowlist",
            },
        },
        "publication_contract": {
            "reader_first": True,
            "access": "public_open_downloads_enabled",
            "collision_preflight_required": True,
            "anonymous_inventory_readback_required": True,
            "anonymous_every_file_sha256_readback_required": True,
            "credentials_runtime_only": True,
            "local_git_forbidden": True,
            "upstream_contact": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--self-check", action="store_true")
    mode.add_argument("--probe", action="store_true")
    mode.add_argument("--prepare", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        result = offline_release_self_check("b026-release-preparer")
    else:
        payload = projection(require_complete=args.prepare)
        if not args.prepare or payload.get("status") != "READY_FOR_PACKAGING":
            if payload.get("status") == "READY_FOR_PACKAGING":
                payload = {
                    **payload,
                    "status": "PASS_B026_RELEASE_PREPARATION_PROBE_NO_WRITES",
                    "writes_performed": False,
                }
            result = payload
        else:
            raw = canonical(payload)
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            if CONFIG_PATH.exists() and CONFIG_PATH.read_bytes() != raw:
                raise StageGateError("refusing to replace different B026 release inputs")
            temporary = CONFIG_PATH.with_suffix(".json.tmp")
            if temporary.exists():
                raise StageGateError(f"refusing stale release-input temporary: {temporary}")
            temporary.write_bytes(raw)
            os.replace(temporary, CONFIG_PATH)
            result = {
                "status": "PASS_B026_RELEASE_INPUTS_EXACTLY_BOUND",
                "config": identity(CONFIG_PATH),
            }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except StageGateError as exc:
        raise SystemExit(f"REFUSED: {exc}")
