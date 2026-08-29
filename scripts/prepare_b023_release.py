#!/usr/bin/env python3
"""Resolve exact R011-B023 release inputs without publishing anything."""

from __future__ import annotations

import argparse
import json
import sys

sys.dont_write_bytecode = True

from release_b023_common import (
    BACKEND_MANIFEST_PATH,
    BOUNDARY_ID,
    CONFIG_PATH,
    EXPECTED_READER_PAGES,
    FINAL_BINDINGS_PATH,
    MODEL,
    ORDERED_RELEASE_ASSETS,
    RELEASE_DATE,
    RELEASE_ID,
    SOURCE_MANIFEST_PATH,
    VERSION,
    VERSION_LABEL,
    VISUAL_FINAL_QA_PATH,
    ReleaseGateError,
    atomic_write,
    canonical_json_bytes,
    identity,
    repo_path,
    require_release_readiness,
    source_manifest_rows,
    static_self_check,
    validate_config,
)


def build_config() -> dict:
    ready = require_release_readiness()
    source_rows, source_exclusions = source_manifest_rows()
    dynamic = ready["dynamic_admission"]
    assert dynamic is not None
    inputs = {
        "reader": ready["promoted_reader"],
        "source_manifest": identity(repo_path(SOURCE_MANIFEST_PATH)),
        "backend_manifest": dynamic["backend_manifest"],
        "visual_final_qa": dynamic["visual_final_qa"],
        "final_qa_bindings": dynamic["final_qa_bindings"],
        "prior_zenodo_receipt": ready["prior_zenodo_receipt"],
        "prior_github_receipt": ready["prior_github_receipt"],
        **ready["known_inputs"],
    }
    config = {
        "$schema": "r011-b023-release-inputs/v1",
        "boundary_id": BOUNDARY_ID,
        "release_id": RELEASE_ID,
        "version": VERSION,
        "version_label": VERSION_LABEL,
        "release_date": RELEASE_DATE,
        "status": "READY_FOR_PACKAGING",
        "model_identification": MODEL,
        "license": "CC BY-SA 3.0 Unported",
        "license_id": "cc-by-sa-3.0",
        "authority": {
            "title": "OpenIntro Statistics, Fourth Edition",
            "derivative_title": "Statistika Berbasis Data",
            "authors": [
                "David M. Diez",
                "Mine Çetinkaya-Rundel",
                "Christopher D. Barr",
            ],
            "repository": "https://github.com/OpenIntroStat/openintro-statistics",
            "reader": "https://www.openintro.org/book/os/",
            "commit": "fee25091fb24e89c36296fd67c48c1fcf7a93b6e",
            "tree": "d61cc601e7d97759ce805900520f784d02a0489e",
        },
        "coverage": {
            "completion_state": "partial",
            "complete_corpus": False,
            "learner_reader_pages": EXPECTED_READER_PAGES,
            "accepted_indonesian_reader_pages": EXPECTED_READER_PAGES,
            "untranslated_instructional_or_exercise_prose_pages": 0,
            "through": "Bab 6, Bagian 6.2 Selisih dua proporsi",
            "exercise_ids": list(range(1, 31)),
            "public_answer_ids": list(range(1, 30, 2)),
            "o001_gap_ids": list(range(2, 31, 2)),
            "restricted_solutions_used": False,
            "full_source_closure_contains_untranslated_source": True,
            "source_closure_counted_as_learner_output": False,
            "page_count_is_artifact_extent_not_complete_corpus_progress": True,
        },
        "next_cursor": {
            "boundary_id": "R011-B024",
            "authority_path": "ch_inference_for_props/TeX/ch_inference_for_props.tex",
            "authority_line": 1344,
            "source_label": "oneWayChiSquare",
            "source_order": "Bab 6, Bagian 6.3",
        },
        "source_package": {
            "manifest_entries": len(source_rows) + len(source_exclusions),
            "public_entries": len(source_rows),
            "excluded_entries": len(source_exclusions),
            "public_bytes": sum(row["bytes"] for row in source_rows),
            "contains_untranslated_source": True,
            "counts_as_learner_output": False,
        },
        "backend_package": {
            "included_roots": ["core/", "locales/", "schemas/", "views/"],
            "public_file_count": len(dynamic["backend_public_rows"]),
            "public_bytes": sum(row["bytes"] for row in dynamic["backend_public_rows"]),
            "excluded_internal_evidence_file_count": len(dynamic["backend_exclusions"]),
        },
        "inputs": inputs,
        "ordered_release_assets": list(ORDERED_RELEASE_ASSETS),
        "destinations": {
            "zenodo": {
                "concept_doi": "10.5281/zenodo.22059801",
                "concept_record_id": 22059801,
                "prior_record_id": 22161105,
                "prior_doi": "10.5281/zenodo.22161105",
                "prior_version": "2026.08.29.1-R011-B022",
                "route": "existing_concept_new_version_only",
            },
            "github": {
                "owner": "KokunoYumeto",
                "repository": "statistika-berbasis-data-id",
                "default_branch": "main",
                "tag": "r011-b023-2026.08.29.2",
                "prior_tag": "r011-b022-2026.08.29.1",
                "prior_release_commit": "850471ea1f6f3991533523c8d71a343d04b4b1b2",
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
    validate_config(config, package_required=False)
    return config


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--self-check", action="store_true")
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--prepare", action="store_true")
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        if args.replace:
            parser.error("--replace is valid only with --prepare")
        print(json.dumps(static_self_check("b023-release-preparer"), ensure_ascii=False, sort_keys=True))
        return 0
    if args.dry_run:
        if args.replace:
            parser.error("--replace is valid only with --prepare")
        result = static_self_check("b023-release-preparer-dry-run")
        result.update(
            {
                "status": "PASS_DRY_RUN_NO_WRITES",
                "would_write": CONFIG_PATH.relative_to(CONFIG_PATH.parents[3]).as_posix(),
                "requires_exact_visual_final": VISUAL_FINAL_QA_PATH,
                "requires_exact_final_bindings": FINAL_BINDINGS_PATH,
                "requires_backend_manifest": BACKEND_MANIFEST_PATH,
                "ordered_assets": list(ORDERED_RELEASE_ASSETS),
            }
        )
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    if CONFIG_PATH.exists() and not args.replace:
        raise ReleaseGateError("B023 RELEASE_INPUTS.json already exists; inspect it before --replace")
    config = build_config()
    atomic_write(CONFIG_PATH, canonical_json_bytes(config))
    validate_config(config, package_required=False)
    print(
        json.dumps(
            {
                "$schema": "r011-b023-release-preparation-receipt/v1",
                "boundary_id": BOUNDARY_ID,
                "release_id": RELEASE_ID,
                "status": "PASS_RELEASE_INPUTS_EXACTLY_BOUND",
                "config": identity(CONFIG_PATH),
                "publication_performed": False,
                "network_used": False,
                "credentials_read": False,
                "local_git_used": False,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ReleaseGateError as exc:
        raise SystemExit(f"REFUSED: {exc}")
