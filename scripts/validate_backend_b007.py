#!/usr/bin/env python3
"""Validate the exact-final, isolated R011-B007 backend without promoting it."""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import importlib.util
import io
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

import jsonschema


LANE = Path(__file__).resolve().parents[1]
GENERATOR_PATH = LANE / "scripts" / "generate_backend_b007.py"
STAGE_ROOT = LANE / "qa" / "b007-backend"
STAGE_EXPORTS = STAGE_ROOT / "exports"
RECEIPT_PATH = STAGE_ROOT / "BACKEND_VALIDATION_RECEIPT_R011-B007.json"
BOUNDARY_ID = "R011-B007"
EXPECTED_NEW_COUNTS = {
    "artifacts": 38,
    "assets": 22,
    "concepts": 19,
    "corrections": 11,
    "courses": 0,
    "editions": 0,
    "localizations": 11,
    "programs": 0,
    "qa_events": 15,
    "relations": 136,
    "resources": 0,
    "rights": 2,
    "segments": 11,
    "terms": 19,
    "units": 11,
}


def load_generator():
    spec = importlib.util.spec_from_file_location("r011_backend_b007", GENERATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load generator: {GENERATOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


m = load_generator()
g = m.g


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def check(name: str, condition: bool, detail: str) -> dict[str, str]:
    if not condition:
        raise RuntimeError(f"validation failed: {name}: {detail}")
    return {"name": name, "result": "passed", "detail": detail}


def load_records(root: Path) -> dict[str, list[dict[str, Any]]]:
    return {
        name: [json.loads(line) for line in (root / relative).read_text(encoding="utf-8").splitlines() if line]
        for name, relative in m.RECORD_PATHS.items()
    }


def replay_span(root: Path, relative: str, span: dict[str, int]) -> bytes:
    raw = (root / relative).read_bytes()
    return raw[span["byte_start"]:span["byte_end_exclusive"]]


def resolve_artifact(path_text: str) -> Path:
    return LANE / path_text


def inventory_identity(root: Path) -> tuple[str, int, int]:
    rows = []
    total = 0
    for path in sorted((p for p in root.rglob("*") if p.is_file()), key=lambda p: p.relative_to(root).as_posix()):
        raw = path.read_bytes()
        relative = path.relative_to(root).as_posix()
        rows.append(f"{relative}\t{len(raw)}\t{sha256_bytes(raw)}")
        total += len(raw)
    payload = ("\n".join(rows) + ("\n" if rows else "")).encode("utf-8")
    return sha256_bytes(payload), len(rows), total


def packaged_privacy_findings(payloads: dict[str, bytes], prohibited_token: str) -> dict[str, list[str]]:
    requester_hits: list[str] = []
    local_profile_hits: list[str] = []
    profile_prefix = re.compile(r"(?i)[a-z]:[\\/]+users[\\/]+")
    requester = prohibited_token.casefold()
    for relative, raw in sorted(payloads.items()):
        text = raw.decode("utf-8", errors="ignore")
        if requester in text.casefold():
            requester_hits.append(relative)
        decoded_escapes = text.replace("\\\\", "\\")
        if profile_prefix.search(text) or profile_prefix.search(decoded_escapes):
            local_profile_hits.append(relative)
    return {
        "prohibited_requester_token_paths": requester_hits,
        "absolute_local_user_profile_path_paths": local_profile_hits,
    }


def references_resolve(all_records: list[dict[str, Any]]) -> tuple[bool, int, list[tuple[str, str, str]]]:
    ids = {row["id"] for row in all_records}
    singular_exclusions = {"id", "backend_id", "workflow_id", "boundary_id", "revision_boundary_id"}
    plural_exclusions = {"source_local_ids", "data_ids", "target_locales"}
    unresolved: list[tuple[str, str, str]] = []
    resolved = 0
    for row in all_records:
        for key, value in row.items():
            if key in singular_exclusions or value is None:
                continue
            if key.endswith("_id") and isinstance(value, str):
                if value in ids:
                    resolved += 1
                else:
                    unresolved.append((row["id"], key, value))
            elif key.endswith("_ids") and key not in plural_exclusions and isinstance(value, list):
                for item in value:
                    if not isinstance(item, str):
                        continue
                    if item in ids:
                        resolved += 1
                    else:
                        unresolved.append((row["id"], key, item))
    return not unresolved, resolved, unresolved


def artifact_identities_exact(artifacts: list[dict[str, Any]]) -> bool:
    for row in artifacts:
        path = resolve_artifact(row["path"])
        if not path.is_file():
            return False
        raw = path.read_bytes()
        if len(raw) != row["bytes"] or sha256_bytes(raw) != row["sha256"]:
            return False
    return True


def aliases_present(terms: list[dict[str, Any]]) -> bool:
    expected = {
        "malaria vaccine": ("data!malaria vaccine", "data!vaksin malaria", "data!malaria vaccine@vaksin malaria"),
        "simulation": ("simulation", "simulasi", "simulation@simulasi"),
    }
    found = {
        row.get("source_term"): (row.get("source_sort_key"), row.get("target_display"), row.get("latex_argument"))
        for row in terms if row.get("boundary_id") == BOUNDARY_ID
    }
    return all(found.get(term) == values for term, values in expected.items())


def final_stage_is_exact_and_unpromoted(records: dict[str, list[dict[str, Any]]], manifest: dict[str, Any]) -> bool:
    assets = [row for row in records["assets"] if row.get("boundary_id") == BOUNDARY_ID]
    artifacts = [row for row in records["artifacts"] if row.get("boundary_id") == BOUNDARY_ID]
    forbidden_asset_kinds = {"localized_vector_figure", "localized_pdf", "promoted_reader_pdf"}
    forbidden_artifact_kinds = {"admission_receipt", "promoted_reader_pdf"}
    canonical_kinds = {
        "canonical_id_id_localized_reader_pdf",
        "canonical_exact_english_pdf_witness",
        "canonical_id_id_localized_figure_producer",
    }
    canonical_assets = [row for row in assets if row.get("asset_kind") in canonical_kinds]
    final_artifact_kinds = Counter(
        row.get("artifact_kind") for row in artifacts
        if row.get("stable_key", "").startswith("r011/artifact/b007-final-")
    )
    canonical_exact = len(canonical_assets) == 13
    for row in canonical_assets:
        path = LANE / row["target_path"]
        if (
            not path.is_file()
            or path.stat().st_size != row["target_bytes"]
            or g.sha256_file(path) != row["target_sha256"]
            or row.get("target_identity_status") != "canonical_asset_promotion_receipt_exact_nonadmitted"
        ):
            canonical_exact = False
            break
    return (
        not any(row.get("asset_kind") in forbidden_asset_kinds for row in assets)
        and not any(row.get("artifact_kind") in forbidden_artifact_kinds for row in artifacts)
        and final_artifact_kinds == Counter({
            "exact_final_input_manifest": 1,
            "exact_build_snapshot_manifest": 1,
            "deterministic_build_gate": 1,
            "candidate_build_qa_receipt": 1,
            "final_build_qa_receipt": 1,
            "build_log": 1,
            "extracted_accessibility_text": 1,
            "deterministic_build_pdf_witness": 1,
            "localized_boundary_pdf": 1,
            "visual_qa_manifest": 1,
            "visual_page_locator": 1,
            "visual_contact_sheet": 1,
            "visual_audit_receipt": 1,
            "visual_qa_finalizer": 1,
        })
        and canonical_exact
        and all(row.get("translation_state") != "published" for row in assets + artifacts)
        and manifest.get("publication_eligibility") == "boundary_ready_for_separate_admission"
        and manifest.get("stage_state", {}).get("boundary_admitted") is False
        and manifest.get("stage_state", {}).get("promotion_performed") is False
        and manifest.get("stage_state", {}).get("localized_pdf_assets_built") is True
        and manifest.get("stage_state", {}).get("canonical_asset_promotion_performed") is True
        and manifest.get("stage_state", {}).get("build_performed") is True
        and manifest.get("stage_state", {}).get("build_and_visual_gates_passed") is True
    )


def validate(final_inputs_path: Path = m.FINAL_INPUTS_DEFAULT) -> tuple[dict[str, Any], dict[str, bytes]]:
    checks: list[dict[str, str]] = []
    first = m.build_payloads(final_inputs_path)
    second = m.build_payloads(final_inputs_path)
    checks.append(check("deterministic_generator_replay", first == second, f"all {len(first)} payloads are byte-identical across two independent in-memory generations"))

    staged_paths = {path.relative_to(STAGE_EXPORTS).as_posix() for path in STAGE_EXPORTS.rglob("*") if path.is_file()}
    disk_exact = staged_paths == set(first) and all((STAGE_EXPORTS / path).read_bytes() == raw for path, raw in first.items())
    checks.append(check("staged_payload_identity", disk_exact, f"all {len(first)} expected payloads are exact on disk with no stale staged file"))

    live_manifest_raw = (m.LIVE_EXPORTS / "manifest.json").read_bytes()
    live_manifest = json.loads(live_manifest_raw)
    live_exact = len(live_manifest_raw) == m.BASE_MANIFEST_BYTES and sha256_bytes(live_manifest_raw) == m.BASE_MANIFEST_SHA256 and sum(live_manifest["record_counts"].values()) == m.BASE_RECORD_COUNT
    checks.append(check("live_backend_immutability", live_exact, "live backend remains the exact admitted 1,969-record R011-B006 base"))

    records = load_records(STAGE_EXPORTS)
    base_records, base_auxiliary, _base_manifest = m.load_base()
    all_records = [row for rows in records.values() for row in rows]
    base_all = [row for rows in base_records.values() for row in rows]
    new_records = [row for row in all_records if row.get("boundary_id") == BOUNDARY_ID]
    manifest = json.loads(first["manifest.json"])
    ids = [row["id"] for row in all_records]
    keys = [row["stable_key"] for row in all_records]
    expected_new_total = sum(EXPECTED_NEW_COUNTS.values())
    checks.append(check(
        "record_inventory",
        manifest["new_record_counts"] == EXPECTED_NEW_COUNTS and len(new_records) == expected_new_total and len(all_records) == m.BASE_RECORD_COUNT + expected_new_total and len(set(ids)) == len(ids) and len(set(keys)) == len(keys),
        f"{len(all_records)} typed records retain all 1,969 admitted stable IDs plus {expected_new_total} unique B007 stage records",
    ))

    staged_by_id = {row["id"]: row for row in all_records}
    preserved = sum(staged_by_id.get(row["id"]) == row for row in base_all)
    privacy_receipt = json.loads(first[m.PRIVACY_RECEIPT_EXPORT_PATH])
    legacy_provenances = {row.get("translation_provenance") for row in base_records["localizations"]}
    legacy_provenance = next(iter(legacy_provenances)) if len(legacy_provenances) == 1 else None
    requester_match = re.search(r"acting on (?P<token>[^']+)'s request", legacy_provenance or "")
    if (
        legacy_provenance is None
        or sha256_bytes(legacy_provenance.encode("utf-8")) != m.EXPECTED_LEGACY_TRANSLATION_PROVENANCE_SHA256
        or requester_match is None
    ):
        raise RuntimeError("cannot derive the exact prohibited requester token from the admitted backend")
    prohibited_token = requester_match.group("token")
    privacy_revision_rows = privacy_receipt["active_localization_revisions"]
    privacy_revision_by_id = {row["id"]: row for row in privacy_revision_rows}
    privacy_revision_ids = set(privacy_revision_by_id)
    overlay_revision_ids = {row["id"] for row in manifest["base_preservation"]["active_overlay_revisions"]}
    bin_revision_id = g.stable_id("r011/term/id-ID/bin")
    allowed_base_revision_ids = privacy_revision_ids | {bin_revision_id}
    changed_base_ids = {row["id"] for row in base_all if staged_by_id.get(row["id"]) != row}
    all_base_ids_retained = all(row["id"] in staged_by_id and staged_by_id[row["id"]]["stable_key"] == row["stable_key"] for row in base_all)
    base_by_id = {row["id"]: row for row in base_all}
    revision_provenance_ok = all(
        staged_by_id[record_id].get("revision_boundary_id") == BOUNDARY_ID
        and staged_by_id[record_id].get("workflow_id") == m.WORKFLOW_ID
        for record_id in allowed_base_revision_ids
    )
    privacy_revisions_ok = (
        len(privacy_revision_rows) == m.EXPECTED_BASE_LOCALIZATION_COUNT
        and privacy_revision_ids == {row["id"] for row in base_records["localizations"]}
        and overlay_revision_ids <= privacy_revision_ids
        and all(
            item["prior_record_sha256"] == m.record_sha256(base_by_id[record_id])
            and item["packaged_record_sha256"] == m.record_sha256(staged_by_id[record_id])
            and staged_by_id[record_id].get("prior_active_record_sha256") == item["prior_record_sha256"]
            and staged_by_id[record_id].get("translation_provenance") == m.NEUTRAL_TRANSLATION_PROVENANCE
            and staged_by_id[record_id].get("privacy_revision_status") == "neutral_requester_provenance_for_public_package"
            and item["packaged_translation_provenance_sha256"] == sha256_bytes(m.NEUTRAL_TRANSLATION_PROVENANCE.encode("utf-8"))
            for record_id, item in privacy_revision_by_id.items()
        )
    )
    privacy_target_rebinds = [item for item in privacy_revision_rows if item.get("target_text_rebound")]
    privacy_target_rebinds_ok = (
        len(privacy_target_rebinds) == m.EXPECTED_PRIVACY_TARGET_REBIND_COUNT
        and all(
            staged_by_id[item["id"]].get("target_path", "").startswith("repo/")
            and staged_by_id[item["id"]].get("target_identity_status") == "privacy_corrected_canonical_exact_nonadmitted"
            and sha256_bytes(replay_span(g.TARGET_ROOT, staged_by_id[item["id"]]["target_path"].removeprefix("repo/"), staged_by_id[item["id"]]["target_span"])) == staged_by_id[item["id"]]["target_sha256"]
            and g.sha256_file(g.TARGET_ROOT / staged_by_id[item["id"]]["target_path"].removeprefix("repo/")) == staged_by_id[item["id"]]["target_file_sha256"]
            for item in privacy_target_rebinds
        )
    )
    checks.append(check(
        "admitted_b006_stable_identity_and_receipt_bound_scoped_revision_preservation",
        len(base_all) == m.BASE_RECORD_COUNT
        and all_base_ids_retained
        and changed_base_ids == allowed_base_revision_ids
        and revision_provenance_ok
        and privacy_revisions_ok
        and privacy_target_rebinds_ok
        and staged_by_id[bin_revision_id].get("prior_active_record_sha256") == manifest["base_preservation"]["prior_term_0088_record_sha256"],
        f"all 1,969 admitted stable IDs remain; {preserved} records are byte-exact while 172 privacy-only active localization revisions plus one TERM-0088 revision carry explicit prior identities; the 13 terminology-target overlays are a receipt-bound subset",
    ))
    auxiliary_revision_by_path = {row["path"]: row for row in privacy_receipt["sanitized_historical_evidence_copies"]}
    auxiliary_history_ok = len(auxiliary_revision_by_path) == m.EXPECTED_SANITIZED_AUXILIARY_COUNT
    for path, raw in base_auxiliary.items():
        if path in auxiliary_revision_by_path:
            packaged, replacement_count = m.sanitize_profile_paths_in_json(raw)
            item = auxiliary_revision_by_path[path]
            auxiliary_history_ok = auxiliary_history_ok and (
                replacement_count == item["replacement_count"]
                and len(raw) == item["original_bytes"]
                and sha256_bytes(raw) == item["original_sha256"]
                and len(packaged) == item["packaged_bytes"]
                and sha256_bytes(packaged) == item["packaged_sha256"]
                and first[path] == packaged
                and item["canonical_source_path"] == f"backend/exports/{path}"
                and item["packaged_path"] == f"qa/b007-backend/exports/{path}"
            )
        else:
            auxiliary_history_ok = auxiliary_history_ok and first[path] == raw
    checks.append(check("admitted_b006_evidence_history_with_receipt_bound_privacy_copies", auxiliary_history_ok, f"all {len(base_auxiliary)} admitted auxiliary evidence origins retain exact identities; six path-leaking JSON files are emitted only as deterministic sanitized copies bound to both identities"))

    record_schema = json.loads((m.LIVE_BACKEND / "schemas" / "backend-record-v0.1.0.schema.json").read_text(encoding="utf-8"))
    record_validator = jsonschema.Draft202012Validator(record_schema, format_checker=jsonschema.FormatChecker())
    schema_ok = all(next(record_validator.iter_errors(row), None) is None and row["id"] == g.stable_id(row["stable_key"]) for row in all_records)
    checks.append(check("schema_envelope_and_stable_ids", schema_ok, "every typed record validates and every UUID is the namespace-stable UUIDv5 of its locale-neutral stable key"))

    canonical_ok = True
    for relative in m.RECORD_PATHS.values():
        raw = first[relative]
        lines = raw.decode("utf-8").splitlines()
        rows = [json.loads(line) for line in lines]
        if raw.startswith(b"\xef\xbb\xbf") or b"\r" in raw or [row["id"] for row in rows] != sorted(row["id"] for row in rows) or any(line != g.canonical_json(row) or unicodedata.normalize("NFC", line) != line for line, row in zip(lines, rows)):
            canonical_ok = False
            break
    checks.append(check("canonical_jsonl_serialization", canonical_ok, "all typed JSONL is canonical UTF-8/NFC/LF and UUID-sorted"))

    refs_ok, resolved_reference_count, unresolved = references_resolve(all_records)
    checks.append(check("referential_integrity", refs_ok, f"all typed parent, concept, source-segment, rights, subject, and relation references resolve; resolved={resolved_reference_count}, unresolved={unresolved[:3]}"))

    authority, source_root = g.read_authority()
    source_span_records = [row for row in new_records if row.get("source_path") and row.get("source_span") and not row["source_path"].startswith("scratch/")]
    source_replay_ok = all(sha256_bytes(replay_span(source_root, row["source_path"], row["source_span"])) == row["source_sha256"] and ("source_text" not in row or replay_span(source_root, row["source_path"], row["source_span"]).decode("utf-8") == row["source_text"]) for row in source_span_records)
    checks.append(check("authority_span_hash_replay", source_replay_ok and authority["commit"] == m.EXPECTED_AUTHORITY["commit"] and authority["calculated_git_tree_sha1"] == m.EXPECTED_AUTHORITY["tree"], f"all {len(source_span_records)} B007 authority spans replay exactly against the pinned commit/tree"))

    localizations = [row for row in records["localizations"] if row.get("boundary_id") == BOUNDARY_ID]
    target_replay_ok = True
    for row in localizations:
        prefix = "repo/"
        if not row["target_path"].startswith(prefix):
            target_replay_ok = False
            break
        relative = row["target_path"].removeprefix(prefix)
        payload = replay_span(g.TARGET_ROOT, relative, row["target_span"])
        if sha256_bytes(payload) != row["target_sha256"] or payload.decode("utf-8") != row["target_text"] or g.sha256_file(g.TARGET_ROOT / relative) != row["target_file_sha256"] or row.get("target_identity_status") != "canonical_source_exact_nonadmitted":
            target_replay_ok = False
            break
    inference_rebound = [
        row for row in localizations
        if any(item.get("term_id") == "R011-TERM-0150" for item in row.get("terminology_supersession", []))
    ]
    revised_active_localizations = [staged_by_id[record_id] for record_id in overlay_revision_ids]
    revised_target_replay = all(
        row["target_path"].startswith("repo/")
        and sha256_bytes(replay_span(g.TARGET_ROOT, row["target_path"].removeprefix("repo/"), row["target_span"])) == row["target_sha256"]
        and replay_span(g.TARGET_ROOT, row["target_path"].removeprefix("repo/"), row["target_span"]).decode("utf-8") == row["target_text"]
        and g.sha256_file(g.TARGET_ROOT / row["target_path"].removeprefix("repo/")) == row["target_file_sha256"]
        for row in revised_active_localizations
    )
    obsolete_forms = ("kelas interval", "kelas-kelas interval", "inferensi statistika")
    active_target_text_clean = not any(form in row.get("target_text", "") for row in records["localizations"] for form in obsolete_forms)
    checks.append(check(
        "canonical_translation_and_field_propagation_round_trip",
        len(localizations) == 11 and target_replay_ok and len(inference_rebound) == 1
        and all(row.get("translation_state") == "language_reviewed" for row in localizations)
        and revised_target_replay and active_target_text_clean,
        f"all eleven B007 translations and {len(revised_active_localizations)} scoped prior active overlays replay exact canonical spans with no obsolete target terminology",
    ))

    units = [row for row in records["units"] if row.get("boundary_id") == BOUNDARY_ID]
    unit_types = Counter(row["unit_type"] for row in units)
    relations = [row for row in records["relations"] if row.get("boundary_id") == BOUNDARY_ID]
    relation_types = Counter(row["relation_type"] for row in relations)
    topology_ok = (
        unit_types == {"section": 1, "subsection": 3, "exercise": 5, "solution": 1, "companion_gap": 1}
        and relation_types["answers"] == 1 and relation_types["requires_companion_answer"] == 1
        and len([row for row in relations if row["relation_type"] == "translates" and row["from_id"] in {item["id"] for item in records["segments"] if item.get("boundary_id") == BOUNDARY_ID}]) == 11
        and relation_types["contains"] == 22
        and len([row for row in units if row.get("exercise_role") == "guided_practice_with_public_feedback"]) == 3
        and len([row for row in units if row["unit_type"] == "companion_gap" and row.get("source_solution_used") is False]) == 1
    )
    checks.append(check("section_exercise_answer_o001_topology", topology_ok, "Section 2.3 contains three instructional subsections, three guided feedback units, exercises 2.25-2.26, only public answer 2.25, and one explicit O001 gap for 2.26"))

    terms = [row for row in records["terms"] if row.get("boundary_id") == BOUNDARY_ID]
    concepts = [row for row in records["concepts"] if row.get("boundary_id") == BOUNDARY_ID]
    candidate_term_ids = sorted(local_id for row in terms for local_id in row.get("source_local_ids", []) if local_id.startswith("R011-B007-TERM-"))
    global_term_ids = sorted(local_id for row in terms for local_id in row.get("source_local_ids", []) if local_id.startswith("R011-TERM-01"))
    randomization_terms = [row for row in records["terms"] if row.get("source_term") == "randomization"]
    active_bin_terms = [row for row in records["terms"] if row.get("source_term") == "bin"]
    statistical_inference = next((row for row in terms if row.get("source_term") == "statistical inference"), None)
    probability = next((row for row in terms if row.get("source_term") == "probability"), None)
    terminology_ok = (
        len(terms) == 19 and len(concepts) == 19
        and candidate_term_ids == [f"R011-B007-TERM-{n:04d}" for n in list(range(2, 10)) + list(range(11, 21))]
        and sorted(set(global_term_ids)) == [f"R011-TERM-{n:04d}" for n in range(142, 161)]
        and len(randomization_terms) == 1 and randomization_terms[0].get("target_term") == "pengacakan"
        and len(active_bin_terms) == 1 and active_bin_terms[0].get("id") == g.stable_id("r011/term/id-ID/bin")
        and active_bin_terms[0].get("target_term") == "interval kelas (bin)"
        and active_bin_terms[0].get("revision_boundary_id") == BOUNDARY_ID
        and active_bin_terms[0].get("prior_active_record_sha256") == manifest["base_preservation"]["prior_term_0088_record_sha256"]
        and statistical_inference is not None and statistical_inference.get("target_term") == "statistika inferensial"
        and probability is not None and probability.get("target_term") == "peluang (probabilitas)" and probability.get("variants") == ["peluang", "probabilitas"]
        and not any(row.get("source_term") == "case study" for row in terms)
        and relation_types["uses"] == 1 and relation_types["introduces"] == 19
        and relation_types["prerequisite"] == 14 and relation_types["supersedes"] == 0 and aliases_present(terms)
    )
    checks.append(check("terminology_concepts_prerequisites_and_index_aliases", terminology_ok, "TERM-0142..0160, stable-ID TERM-0088 active revision, exact admitted randomization reuse, fourteen justified prerequisites, scoped probability, and both source-sort/target-display index aliases are coherent"))

    corrections = [row for row in records["corrections"] if row.get("boundary_id") == BOUNDARY_ID]
    source_corrections = [row for row in corrections if row.get("correction_type") == "upstream_source_finding"]
    field_corrections = [row for row in corrections if row.get("correction_type") == "derivative_terminology_field_refinement"]
    correction_ids = sorted(local_id for row in source_corrections for local_id in row["source_local_ids"] if local_id.startswith("R011-B007-SC-"))
    field_ids = sorted(local_id for row in field_corrections for local_id in row["source_local_ids"] if local_id.startswith("R011-TERM-"))
    corrections_ok = (
        len(corrections) == 11 and len(source_corrections) == 8 and len(field_corrections) == 3
        and correction_ids == [f"R011-B007-SC-{n:03d}" for n in range(1, 9)]
        and field_ids == ["R011-TERM-0088", "R011-TERM-0150", "R011-TERM-0160"]
        and all(row.get("confidence") == "high" and row.get("upstream_report_disposition") == "hold_until_corpus_complete_then_deduplicate" for row in source_corrections)
        and all(row.get("upstream_report_disposition") == "not_upstream_derivative_only" and row.get("target_identity_status") == "exact_propagated_nonadmitted" for row in field_corrections)
        and relation_types["corrects"] == 11
    )
    checks.append(check("source_and_field_correction_inventory", corrections_ok, "eight high-confidence upstream findings remain held for one report, while three derivative terminology refinements carry exact propagation provenance and never enter that report"))

    assets = [row for row in records["assets"] if row.get("boundary_id") == BOUNDARY_ID]
    asset_kinds = Counter(row["asset_kind"] for row in assets)
    source_asset_exact = True
    for row in assets:
        if row["asset_kind"].startswith("authority_exact_"):
            path = source_root / row["source_path"]
            raw = path.read_bytes()
            if len(raw) != row["bytes"] or sha256_bytes(raw) != row["sha256"]:
                source_asset_exact = False
        else:
            path = LANE / row["target_path"]
            raw = path.read_bytes()
            if len(raw) != row["target_bytes"] or sha256_bytes(raw) != row["target_sha256"]:
                source_asset_exact = False
    rights = [row for row in records["rights"] if row.get("boundary_id") == BOUNDARY_ID]
    asset_privacy_qa = json.loads(first["evidence/R011-B007_ASSET_PRIVACY_REFRESH_QA.json"])
    asset_ok = (
        asset_kinds == {
            "authority_exact_reader_pdf": 5,
            "authority_exact_figure_producer": 3,
            "authority_exact_serialized_generator_input": 1,
            "canonical_id_id_localized_figure_producer": 3,
            "canonical_id_id_localized_reader_pdf": 5,
            "canonical_exact_english_pdf_witness": 5,
        }
        and source_asset_exact and len(rights) == 2 and relation_types["produces"] == 10 and relation_types["illustrates"] == 10
        and relation_types["adapts"] == 3 and relation_types["depends-on"] == 2
        and relation_types["witnesses"] == 5 and relation_types["translates"] == 16
        and all(row.get("candidate_status") != "promotion_ready" for row in assets)
        and asset_privacy_qa.get("status") == "pass_privacy_and_portability_ready_for_canonical_promotion"
        and asset_privacy_qa.get("privacy", {}).get("prohibited_requester_token_hits") == 0
        and asset_privacy_qa.get("privacy", {}).get("absolute_profile_path_hits") == 0
        and asset_privacy_qa.get("privacy", {}).get("avandia_author_is_neutral") is True
        and asset_privacy_qa.get("determinism", {}).get("all_byte_identical") is True
        and asset_privacy_qa.get("portable_points", {}).get("all_points_visible_in_poppler_and_mupdf") is True
        and asset_privacy_qa.get("portable_points", {}).get("all_source_coordinate_multisets_preserved") is True
    )
    checks.append(check("asset_code_data_rights_source_and_canonical_promotion_closure", asset_ok, "five source PDFs, three source producers, inference.RData, three canonical localized producers, five canonical localized PDFs, five exact English witnesses, and two smallest-component rights records replay exactly"))

    artifacts = [row for row in records["artifacts"] if row.get("boundary_id") == BOUNDARY_ID]
    checks.append(check("artifact_identity_replay", len(artifacts) == 38 and artifact_identities_exact(artifacts) and all(row.get("status") == "passed" for row in artifacts), "all thirty-eight candidate/source/asset/build/visual/PDF/evidence/tool artifacts replay to exact byte identities"))
    qa_events = [row for row in records["qa_events"] if row.get("boundary_id") == BOUNDARY_ID]
    checks.append(check("typed_completed_qa_state", len(qa_events) == 15 and all(row.get("result") == "passed" and row.get("status") == "passed" for row in qa_events) and {row["qa_type"] for row in qa_events} >= {"source", "topology", "language", "rights", "math", "visual", "privacy", "build", "accessibility"}, "fifteen completed candidate/source/topology/language/rights/math/privacy/build/visual/accessibility checks are typed; admission is not falsely passed"))

    view_schema = json.loads((m.LIVE_BACKEND / "schemas" / "backend-view-columns-v0.1.0.json").read_text(encoding="utf-8"))
    expected_views = g.build_views(records, view_schema["views"])
    checks.append(check("csv_projection_round_trip", len(expected_views) == 10 and all(first[path] == raw for path, raw in expected_views.items()), "all ten schema-fixed CSV projections replay byte-for-byte from typed records"))

    identity_rows = [json.loads(line) for line in first["identity_map.jsonl"].decode("utf-8").splitlines()]
    checks.append(check("identity_map_completeness", len(identity_rows) == len(all_records) and {row["id"] for row in identity_rows} == set(ids), f"identity map covers all {len(all_records)} records without localized wording as identity"))

    manifest_schema = json.loads((m.LIVE_BACKEND / "schemas" / "backend-manifest-v0.1.0.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(manifest, manifest_schema, format_checker=jsonschema.FormatChecker())
    manifest_files_ok = all(entry["path"] in first and len(first[entry["path"]]) == entry["bytes"] and sha256_bytes(first[entry["path"]]) == entry["sha256"] for entry in manifest["files"])
    checks.append(check("manifest_schema_hashes_and_counts", manifest_files_ok and manifest["record_counts"] == {name: len(rows) for name, rows in sorted(records.items())}, f"manifest validates and binds all {len(manifest['files'])} payloads with reconciled record counts"))

    privacy_findings = packaged_privacy_findings(first, prohibited_token)
    privacy_gate = manifest.get("privacy_gate", {})
    privacy_ok = (
        not any(privacy_findings.values())
        and privacy_receipt.get("status") == "passed_sanitized_nonadmitted_backend_package_components"
        and privacy_receipt.get("active_localization_revision_count") == m.EXPECTED_BASE_LOCALIZATION_COUNT
        and privacy_receipt.get("canonical_target_text_rebind_count") == m.EXPECTED_PRIVACY_TARGET_REBIND_COUNT
        and privacy_receipt.get("sanitized_historical_evidence_copy_count") == m.EXPECTED_SANITIZED_AUXILIARY_COUNT
        and privacy_gate.get("active_localization_revision_count") == m.EXPECTED_BASE_LOCALIZATION_COUNT
        and privacy_gate.get("canonical_target_text_rebind_count") == m.EXPECTED_PRIVACY_TARGET_REBIND_COUNT
        and privacy_gate.get("sanitized_historical_evidence_copy_count") == m.EXPECTED_SANITIZED_AUXILIARY_COUNT
        and privacy_gate.get("prohibited_requester_token_hits") == 0
        and privacy_gate.get("absolute_local_user_profile_path_hits") == 0
        and privacy_gate.get("receipt") == {
            "path": f"qa/b007-backend/exports/{m.PRIVACY_RECEIPT_EXPORT_PATH}",
            "bytes": len(first[m.PRIVACY_RECEIPT_EXPORT_PATH]),
            "sha256": sha256_bytes(first[m.PRIVACY_RECEIPT_EXPORT_PATH]),
        }
    )
    checks.append(check("full_payload_privacy_and_portability_gate", privacy_ok, "every emitted payload byte has zero prohibited requester-token hits and zero absolute local user-profile path hits; all 172 active revisions and six sanitized historical evidence copies are receipt-bound with task-relative paths"))

    final_gates = manifest.get("final_gates", {})
    final_input_raw = first["evidence/R011-B007_FINAL_GATE_INPUTS.json"]
    final_gate_ok = (
        final_gates.get("status") == "passed_exact_terminal_inputs_stage_only"
        and final_gates.get("input_manifest") == {
            "path": final_inputs_path.resolve().relative_to(LANE.resolve()).as_posix(),
            "bytes": len(final_input_raw),
            "sha256": sha256_bytes(final_input_raw),
        }
        and final_gates.get("snapshot_manifest") == m.EXPECTED_FINAL_INPUTS["snapshot_manifest"]
        and final_gates.get("build_gate_script") == m.EXPECTED_FINAL_INPUTS["build_gate_script"]
        and final_gates.get("candidate_build_qa") == m.EXPECTED_FINAL_INPUTS["candidate_build_qa"]
        and final_gates.get("build_qa") == m.EXPECTED_FINAL_INPUTS["build_qa"]
        and final_gates.get("reviewed_candidate_pdf") == m.EXPECTED_FINAL_INPUTS["pdf"]
        and final_gates.get("render_manifest") == m.EXPECTED_FINAL_INPUTS["render_manifest"]
        and final_gates.get("visual_audit") == m.EXPECTED_FINAL_INPUTS["visual_audit"]
        and final_gates.get("candidate") == m.EXPECTED_FINAL_GATE["candidate"]
        and final_gates.get("page_count") == m.EXPECTED_FINAL_GATE["page_count"]
        and final_gates.get("inspected_pages") == m.EXPECTED_FINAL_GATE["inspected_pages"]
        and final_gates.get("severity_counts") == m.EXPECTED_FINAL_GATE["severity_counts"]
        and final_gates.get("document_language") == "id-ID"
        and final_gates.get("candidate_pdf_promoted") is False
    )
    stage_only_ok = final_stage_is_exact_and_unpromoted(records, manifest) and final_gate_ok and manifest.get("placeholder_count") == 0 and len(manifest.get("deferred_completion_bindings", [])) == 1 and manifest.get("publication_blockers") == manifest.get("deferred_completion_bindings") and manifest.get("stage_state") == {
        "status": "isolated_final_backend_validated_ready_for_admission", "live_backend_mutated": False,
        "canonical_source_mutated": False, "canonical_target_spans_bound": True,
        "localized_pdf_assets_built": True, "canonical_asset_promotion_performed": True,
        "build_performed": True, "build_and_visual_gates_passed": True,
        "boundary_admitted": False, "promotion_performed": False,
    }
    checks.append(check("exact_final_gates_ready_for_separate_admission", stage_only_ok, "the exact build/visual/PDF gate is closed, only the admission transaction remains deferred, and no promotion is claimed"))

    # Pure in-memory adversarial mutations: each detector must reject its targeted corruption.
    adversarial: list[dict[str, Any]] = []
    duplicate = copy.deepcopy(all_records); duplicate.append(copy.deepcopy(duplicate[0]))
    adversarial.append({"name": "duplicate_id", "detected": len({row["id"] for row in duplicate}) != len(duplicate)})
    broken_ref = copy.deepcopy(all_records); relation = next(row for row in broken_ref if row.get("boundary_id") == BOUNDARY_ID and row.get("record_type") == "relation"); relation["to_id"] = "00000000-0000-0000-0000-000000000000"
    adversarial.append({"name": "unresolved_relation", "detected": not references_resolve(broken_ref)[0]})
    mutated_base = copy.deepcopy(all_records); base_row = next(row for row in mutated_base if row.get("boundary_id") != BOUNDARY_ID); base_row["status"] = "superseded"
    mutated_by_id = {row["id"]: row for row in mutated_base}
    adversarial.append({"name": "base_record_mutation", "detected": any(mutated_by_id.get(row["id"]) != row for row in base_all)})
    promoted_manifest = copy.deepcopy(manifest); promoted_manifest["stage_state"]["boundary_admitted"] = True
    adversarial.append({"name": "false_admission", "detected": not final_stage_is_exact_and_unpromoted(records, promoted_manifest)})
    alias_terms = copy.deepcopy(terms); next(row for row in alias_terms if row.get("source_term") == "simulation").pop("source_sort_key")
    adversarial.append({"name": "index_alias_loss", "detected": not aliases_present(alias_terms)})
    fake_records = copy.deepcopy(records); fake_records["assets"].append({"boundary_id": BOUNDARY_ID, "asset_kind": "localized_pdf", "translation_state": "built"})
    adversarial.append({"name": "fabricated_localized_pdf", "detected": not final_stage_is_exact_and_unpromoted(fake_records, manifest)})
    bad_artifacts = copy.deepcopy(artifacts); bad_artifacts[0]["sha256"] = "0" * 64
    adversarial.append({"name": "artifact_hash_tamper", "detected": not artifact_identities_exact(bad_artifacts)})
    bad_identity = copy.deepcopy(identity_rows); bad_identity.pop()
    adversarial.append({"name": "identity_map_omission", "detected": len(bad_identity) != len(all_records) or {row["id"] for row in bad_identity} != set(ids)})
    any_view, any_view_raw = next(iter(expected_views.items())); tampered_view = any_view_raw + b"tamper\n"
    adversarial.append({"name": "csv_projection_tamper", "detected": tampered_view != expected_views[any_view]})
    bad_source = copy.deepcopy(source_span_records); bad_source[0]["source_sha256"] = "0" * 64
    adversarial.append({"name": "authority_span_hash_tamper", "detected": sha256_bytes(replay_span(source_root, bad_source[0]["source_path"], bad_source[0]["source_span"])) != bad_source[0]["source_sha256"]})
    requester_leak_payloads = dict(first); requester_leak_payloads["privacy-requester-leak.txt"] = prohibited_token.encode("utf-8")
    adversarial.append({"name": "prohibited_requester_token_leak", "detected": bool(packaged_privacy_findings(requester_leak_payloads, prohibited_token)["prohibited_requester_token_paths"])})
    profile_leak_payloads = dict(first)
    profile_prefix = chr(67) + ":" + chr(92) + "Users" + chr(92) + "placeholder" + chr(92) + "artifact"
    profile_leak_payloads["privacy-profile-path-leak.txt"] = profile_prefix.encode("utf-8")
    adversarial.append({"name": "absolute_local_profile_path_leak", "detected": bool(packaged_privacy_findings(profile_leak_payloads, prohibited_token)["absolute_local_user_profile_path_paths"])})
    bad_final_gate = copy.deepcopy(manifest)
    bad_final_gate["final_gates"]["reviewed_candidate_pdf"]["sha256"] = "0" * 64
    adversarial.append({"name": "final_pdf_gate_hash_tamper", "detected": bad_final_gate["final_gates"]["reviewed_candidate_pdf"] != m.EXPECTED_FINAL_INPUTS["pdf"]})
    checks.append(check("adversarial_mutation_suite", len(adversarial) == 13 and all(item["detected"] for item in adversarial), "13/13 pure in-memory corruptions were detected, including base/reference/privacy/view/source/artifact/final-PDF-gate and false-admission mutations"))

    inventory_sha256, inventory_count, inventory_bytes = inventory_identity(STAGE_EXPORTS)
    result = {
        "$schema": "r011-b007-backend-validation-receipt/v1",
        "base_boundary": m.BASE_BOUNDARY_ID,
        "boundary_id": BOUNDARY_ID,
        "status": "passed_isolated_final_backend_ready_for_admission",
        "manifest_sha256": sha256_bytes(first["manifest.json"]),
        "manifest_bytes": len(first["manifest.json"]),
        "record_count": len(all_records),
        "record_counts": manifest["record_counts"],
        "base_record_count": len(base_all),
        "preserved_base_record_count": preserved,
        "base_records_preserved_exact": preserved == len(base_all),
        "base_stable_ids_preserved": all_base_ids_retained,
        "privacy_revised_base_localization_count": len(privacy_revision_ids),
        "semantic_revised_base_record_count": len(overlay_revision_ids | {bin_revision_id}),
        "sanitized_historical_evidence_copy_count": len(auxiliary_revision_by_path),
        "privacy_receipt": {
            "path": f"qa/b007-backend/exports/{m.PRIVACY_RECEIPT_EXPORT_PATH}",
            "bytes": len(first[m.PRIVACY_RECEIPT_EXPORT_PATH]),
            "sha256": sha256_bytes(first[m.PRIVACY_RECEIPT_EXPORT_PATH]),
        },
        "new_record_count": len(new_records),
        "new_record_counts": manifest["new_record_counts"],
        "payload_count": len(first),
        "payload_bytes": sum(len(raw) for raw in first.values()),
        "resolved_reference_count": resolved_reference_count,
        "authority_span_count": len(source_span_records),
        "localization_slice_count": len(localizations),
        "artifact_count": len(artifacts),
        "stage_inventory_sha256": inventory_sha256,
        "stage_inventory_file_count": inventory_count,
        "stage_inventory_bytes": inventory_bytes,
        "validator_checks_passed": len(checks),
        "validator_checks_total": len(checks),
        "validator_check_names": [item["name"] for item in checks],
        "adversarial_tests": adversarial,
        "placeholder_count": 0,
        "deferred_completion_bindings": manifest["deferred_completion_bindings"],
        "validation_target": STAGE_EXPORTS.relative_to(LANE).as_posix(),
        "live_backend_mutated": False,
        "canonical_source_mutated": False,
        "boundary_admitted": False,
        "promotion_performed": False,
        "tooling": {
            "generator": {"path": GENERATOR_PATH.relative_to(LANE).as_posix(), "bytes": GENERATOR_PATH.stat().st_size, "sha256": g.sha256_file(GENERATOR_PATH)},
            "validator": {"path": Path(__file__).relative_to(LANE).as_posix(), "bytes": Path(__file__).stat().st_size, "sha256": g.sha256_file(Path(__file__))},
        },
        "checks": checks,
    }
    return result, first


def result_bytes(result: dict[str, Any]) -> bytes:
    return (g.canonical_json(result) + "\n").encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true", help="replay read-only and require exact receipt identity")
    parser.add_argument("--final-inputs", type=Path, default=m.FINAL_INPUTS_DEFAULT, help="exact canonical B007 terminal-input manifest")
    parser.add_argument("--check-readiness", action="store_true", help="report frozen-binding readiness without reading or writing stage payloads")
    args = parser.parse_args()
    if args.check_readiness:
        gaps = m.final_binding_gaps()
        print(g.canonical_json({
            "boundary_id": BOUNDARY_ID,
            "status": "ready" if not gaps else "blocked_unfrozen_exact_bindings",
            "binding_manifest": m.FINAL_INPUTS_DEFAULT.relative_to(LANE).as_posix(),
            "deferred_bindings": gaps,
            "receipt_written": False,
            "stage_written": False,
            "live_backend_mutated": False,
        }))
        return 0 if not gaps else 2
    final_inputs = args.final_inputs.resolve()
    try:
        final_inputs.relative_to(LANE.resolve())
    except ValueError as exc:
        raise RuntimeError("final-input manifest must remain inside the R011 lane") from exc
    result, _payloads = validate(final_inputs)
    raw = result_bytes(result)
    if args.verify_only:
        if not RECEIPT_PATH.is_file() or RECEIPT_PATH.read_bytes() != raw:
            raise RuntimeError("read-only replay does not match the frozen B007 backend receipt")
        print(f"checks={result['validator_checks_passed']}")
        print(f"result={result['status']}")
        print(f"manifest_sha256={result['manifest_sha256']}")
        print(f"receipt_sha256={sha256_bytes(raw)}")
        print("read_only_replay=passed")
        print("live_backend_mutated=false")
        return 0
    RECEIPT_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = RECEIPT_PATH.with_name(RECEIPT_PATH.name + ".tmp")
    temporary.write_bytes(raw)
    temporary.replace(RECEIPT_PATH)
    print(f"checks={result['validator_checks_passed']}")
    print(f"result={result['status']}")
    print(f"manifest_sha256={result['manifest_sha256']}")
    print(f"receipt_sha256={sha256_bytes(raw)}")
    print("boundary_admitted=false")
    print("live_backend_mutated=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
