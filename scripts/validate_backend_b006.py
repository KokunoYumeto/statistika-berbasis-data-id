#!/usr/bin/env python3
"""Validate the isolated final-V4 R011-B006 backend stage without promoting it.

The exact revised source gate and final-V4 build/reviewed-PDF/render/visual
identities enter through the same final-input manifest consumed by the
generator.  This validator replays that generator twice, validates every
staged byte and typed record, and writes only a staging receipt under
``qa/b006-backend``.  The admission guard separately owns first promotion.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import io
import json
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

import jsonschema


LANE = Path(__file__).resolve().parents[1]
GENERATOR_PATH = LANE / "scripts" / "generate_backend_b006.py"
STAGING_ROOT = LANE / "qa" / "b006-backend"
STAGING_EXPORTS = STAGING_ROOT / "exports"
LIVE_EXPORTS = LANE / "backend" / "exports"
RECEIPT_PATH = STAGING_ROOT / "BACKEND_VALIDATION_RECEIPT_R011-B006_STAGE.json"
BOUNDARY_ID = "R011-B006"
EXPECTED_NEW_RECORD_COUNT = 351
EXPECTED_TOTAL_RECORD_COUNT = 1969


def load_generator():
    spec = importlib.util.spec_from_file_location("r011_backend_b006", GENERATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load generator: {GENERATOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


m = load_generator()
g = m.g


def check(name: str, condition: bool, detail: str) -> dict[str, str]:
    if not condition:
        raise AssertionError(f"{name}: {detail}")
    return {"name": name, "result": "passed", "detail": detail}


def load_records(root: Path) -> dict[str, list[dict[str, Any]]]:
    return {
        name: [json.loads(line) for line in (root / path).read_text(encoding="utf-8").splitlines()]
        for name, path in m.RECORD_PATHS.items()
    }


def replay_span(root: Path, path: str, span: dict[str, int]) -> bytes:
    raw = (root / path).read_bytes()
    return raw[span["byte_start"] : span["byte_end_exclusive"]]


def inventory_identity(root: Path) -> tuple[str, int, int]:
    lines: list[str] = []
    total_bytes = 0
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        raw = path.read_bytes()
        total_bytes += len(raw)
        lines.append(f"{relative}\t{len(raw)}\t{g.sha256_bytes(raw)}\n")
    inventory_raw = "".join(lines).encode("utf-8")
    return g.sha256_bytes(inventory_raw), len(lines), total_bytes


def exact_file(identity: dict[str, Any]) -> bool:
    path_text = identity.get("path")
    if not isinstance(path_text, str):
        return False
    path = LANE / path_text
    return (
        path.is_file()
        and path.stat().st_size == identity.get("bytes")
        and g.sha256_file(path) == identity.get("sha256")
    )


def validate(final_inputs_path: Path) -> tuple[dict[str, Any], dict[str, bytes]]:
    checks: list[dict[str, str]] = []
    first = m.build_payloads(final_inputs_path)
    second = m.build_payloads(final_inputs_path)
    checks.append(
        check(
            "deterministic_generator_replay",
            first == second,
            f"all {len(first)} payloads match byte-for-byte across two independent in-memory generations",
        )
    )

    staged_paths = {
        path.relative_to(STAGING_EXPORTS).as_posix()
        for path in STAGING_EXPORTS.rglob("*")
        if path.is_file()
    }
    expected_paths = set(first)
    disk_exact = all(
        (STAGING_EXPORTS / path).is_file()
        and (STAGING_EXPORTS / path).read_bytes() == raw
        for path, raw in first.items()
    )
    checks.append(
        check(
            "staged_payload_identity",
            disk_exact and staged_paths == expected_paths,
            f"all {len(first)} generated payloads are byte-exact on disk with no stale or missing staged file",
        )
    )

    live_manifest_raw = (LIVE_EXPORTS / "manifest.json").read_bytes()
    live_manifest = json.loads(live_manifest_raw)
    checks.append(
        check(
            "live_backend_immutability",
            g.sha256_bytes(live_manifest_raw) == m.BASE_MANIFEST_SHA256
            and sum(live_manifest["record_counts"].values()) == m.BASE_RECORD_COUNT,
            "the live backend remains the exact admitted 1,618-record R011-B005 base; validation performs no promotion",
        )
    )

    records = load_records(STAGING_EXPORTS)
    base_records = m.load_base_records()
    all_records = [row for collection in records.values() for row in collection]
    base_all = [row for collection in base_records.values() for row in collection]
    new_records = [row for row in all_records if row.get("boundary_id") == BOUNDARY_ID]
    ids = [row["id"] for row in all_records]
    stable_keys = [row["stable_key"] for row in all_records]
    checks.append(
        check(
            "record_inventory",
            len(all_records) == EXPECTED_TOTAL_RECORD_COUNT
            and len(new_records) == EXPECTED_NEW_RECORD_COUNT
            and len(set(ids)) == EXPECTED_TOTAL_RECORD_COUNT
            and len(set(stable_keys)) == EXPECTED_TOTAL_RECORD_COUNT,
            "1,969 typed records (1,618 admitted base + 351 B006) have unique IDs and stable keys",
        )
    )

    staged_by_id = {row["id"]: row for row in all_records}
    preserved_base_count = sum(staged_by_id.get(row["id"]) == row for row in base_all)
    checks.append(
        check(
            "admitted_b005_additive_preservation",
            len(base_all) == m.BASE_RECORD_COUNT and preserved_base_count == m.BASE_RECORD_COUNT,
            "all 1,618 admitted R011-B005 records are present byte-semantically unchanged",
        )
    )
    base_auxiliary = m.base_auxiliary_payloads()
    checks.append(
        check(
            "admitted_b005_evidence_preservation",
            all(first[path] == raw for path, raw in base_auxiliary.items()),
            f"all {len(base_auxiliary)} admitted B005 auxiliary evidence payloads remain byte-exact",
        )
    )

    schema = json.loads(
        (m.BASE_BACKEND / "schemas" / "backend-record-v0.1.0.schema.json").read_text(encoding="utf-8")
    )
    record_validator = jsonschema.Draft202012Validator(
        schema, format_checker=jsonschema.FormatChecker()
    )
    schema_ok = all(
        next(record_validator.iter_errors(row), None) is None
        and row["id"] == g.stable_id(row["stable_key"])
        for row in all_records
    )
    checks.append(
        check(
            "schema_envelope_and_stable_ids",
            schema_ok,
            "every record satisfies the common schema and the UUIDv5 stable-key mapping",
        )
    )

    canonical_ok = True
    for relative in m.RECORD_PATHS.values():
        raw = (STAGING_EXPORTS / relative).read_bytes()
        lines = raw.decode("utf-8").splitlines()
        rows = [json.loads(line) for line in lines]
        if (
            raw.startswith(b"\xef\xbb\xbf")
            or b"\r" in raw
            or [row["id"] for row in rows] != sorted(row["id"] for row in rows)
            or any(
                line != g.canonical_json(row)
                or unicodedata.normalize("NFC", line) != line
                for line, row in zip(lines, rows)
            )
        ):
            canonical_ok = False
            break
    checks.append(
        check(
            "canonical_jsonl_serialization",
            canonical_ok,
            "all typed JSONL is canonical UTF-8/NFC/LF and UUID-sorted",
        )
    )

    id_set = set(ids)
    unresolved: list[tuple[str, str, str]] = []
    resolved_reference_count = 0
    singular_exclusions = {"id", "backend_id", "workflow_id", "boundary_id"}
    plural_exclusions = {"source_local_ids", "data_ids", "target_locales"}
    for row in all_records:
        for key, value in row.items():
            if key in singular_exclusions or value is None:
                continue
            if key.endswith("_id") and isinstance(value, str):
                if value not in id_set:
                    unresolved.append((row["id"], key, value))
                else:
                    resolved_reference_count += 1
            elif key.endswith("_ids") and key not in plural_exclusions and isinstance(value, list):
                for item in value:
                    if not isinstance(item, str):
                        continue
                    if item not in id_set:
                        unresolved.append((row["id"], key, item))
                    else:
                        resolved_reference_count += 1
    checks.append(
        check(
            "referential_integrity",
            not unresolved,
            f"all typed relations, parents, concepts, source segments, witnesses, and rights references resolve; unresolved={unresolved[:3]}",
        )
    )

    _authority, source_root = g.read_authority()
    source_span_records = [
        row for row in new_records if row.get("source_path") and row.get("source_span")
    ]
    source_replay_ok = True
    for row in source_span_records:
        payload = replay_span(source_root, row["source_path"], row["source_span"])
        if g.sha256_bytes(payload) != row["source_sha256"] or (
            "source_text" in row and payload.decode("utf-8") != row["source_text"]
        ):
            source_replay_ok = False
            break
    checks.append(
        check(
            "authority_span_hash_replay",
            source_replay_ok,
            f"all {len(source_span_records)} B006 authority spans replay byte-exactly from the pinned source",
        )
    )

    localizations = [
        row for row in records["localizations"] if row.get("boundary_id") == BOUNDARY_ID
    ]
    target_replay_ok = True
    for row in localizations:
        relative = row["target_path"].removeprefix("repo/")
        payload = replay_span(m.TARGET_ROOT, relative, row["target_span"])
        if (
            g.sha256_bytes(payload) != row["target_sha256"]
            or payload.decode("utf-8") != row["target_text"]
            or g.sha256_file(m.TARGET_ROOT / relative) != row["target_file_sha256"]
            or row.get("target_identity_status") != "source_gate_passed"
        ):
            target_replay_ok = False
            break
    checks.append(
        check(
            "translation_overlay_round_trip",
            len(localizations) == 21 and target_replay_ok,
            "all 21 Section 2.2/exercise/public-answer id-ID segments replay against the revised source-gate bytes",
        )
    )

    manifest = json.loads(first["manifest.json"])
    source_qa_raw = first["evidence/R011-B006_SOURCE_QA.json"]
    target_manifest_raw = first["evidence/R011-B006_TARGET_MANIFEST.tsv"]
    source_qa = json.loads(source_qa_raw)
    target_manifest_lines = target_manifest_raw.decode("utf-8").splitlines()
    supplied = json.loads(first["evidence/R011-B006_FINAL_GATE_INPUTS.json"])
    supplied_inputs = supplied["inputs"]
    target_gate_ok = (
        source_qa.get("status") == "passed"
        and source_qa.get("boundary_id") == BOUNDARY_ID
        and source_qa.get("target_closure", {}).get("manifest")
        == supplied_inputs["target_manifest"]
        and len(target_manifest_lines) == m.EXPECTED_TARGET_CLOSURE["file_count"]
        and sum(int(line.split("\t")[1]) for line in target_manifest_lines)
        == m.EXPECTED_TARGET_CLOSURE["file_bytes"]
        and manifest["source_closure"]
        == {
            "status": "passed",
            "file_count": m.EXPECTED_TARGET_CLOSURE["file_count"],
            "file_bytes": m.EXPECTED_TARGET_CLOSURE["file_bytes"],
            "source_qa_sha256": supplied_inputs["source_qa"]["sha256"],
            "target_manifest_sha256": supplied_inputs["target_manifest"]["sha256"],
        }
    )
    checks.append(
        check(
            "revised_source_gate_identity_binding",
            target_gate_ok,
            f"the supplied revised receipt and exact {m.EXPECTED_TARGET_CLOSURE['file_count']:,}-file / {m.EXPECTED_TARGET_CLOSURE['file_bytes']:,}-byte target manifest are embedded and mutually hash-bound",
        )
    )
    target_manifest_replay = True
    for line in target_manifest_lines:
        relative, size_text, digest = line.split("\t")
        path = m.TARGET_ROOT / relative
        if (
            not path.is_file()
            or path.stat().st_size != int(size_text)
            or g.sha256_file(path) != digest
        ):
            target_manifest_replay = False
            break
    checks.append(
        check(
            "target_manifest_file_replay",
            target_manifest_replay,
            "every file in the repaired B006 source closure replays from the live bounded corpus repo",
        )
    )

    b006_units = [row for row in records["units"] if row.get("boundary_id") == BOUNDARY_ID]
    unit_types = Counter(row["unit_type"] for row in b006_units)
    checks.append(
        check(
            "unit_hierarchy_inventory",
            len(b006_units) == 20
            and unit_types
            == {
                "section": 1,
                "subsection": 6,
                "guided_exercise": 4,
                "section_review": 1,
                "exercise": 4,
                "solution": 2,
                "companion_gap": 2,
            },
            "20 stable units preserve Section 2.2, six subsections, four guided exercises, exercises 2.21–2.24, two public answers, and two O001 gaps",
        )
    )

    b006_segments = [
        row for row in records["segments"] if row.get("boundary_id") == BOUNDARY_ID
    ]
    segment_types = Counter(row["segment_kind"] for row in b006_segments)
    expected_segment_types = {
        "section_lead": 1,
        "subsection_prose": 10,
        "guided_exercise": 4,
        "exercise": 4,
        "public_appendix_solution": 2,
    }
    checks.append(
        check(
            "segment_inventory",
            len(b006_segments) == 21 and segment_types == expected_segment_types,
            "21 non-overlapping translation segments provide unit-level source/id-ID overlays",
        )
    )
    body_segments = sorted(
        (row for row in b006_segments if row["source_path"] == m.BODY_PATH),
        key=lambda row: row["source_span"]["line_start"],
    )
    body_localizations = {
        row["source_segment_id"]: row
        for row in localizations
        if row["source_path"] == m.BODY_PATH
    }
    source_cover: list[int] = []
    target_cover: list[int] = []
    for row in body_segments:
        source_cover.extend(
            range(row["source_span"]["line_start"], row["source_span"]["line_end"] + 1)
        )
        target_span = body_localizations[row["id"]]["target_span"]
        target_cover.extend(range(target_span["line_start"], target_span["line_end"] + 1))
    source_section = g.section_range_by_label(source_root, m.BODY_PATH, "categoricalData")
    target_section = g.section_range_by_label(m.TARGET_ROOT, m.BODY_PATH, "categoricalData")
    checks.append(
        check(
            "section_segment_nonoverlap_and_coverage",
            source_cover == list(range(source_section[0], source_section[1] + 1))
            and target_cover == list(range(target_section[0], target_section[1] + 1)),
            "Section 2.2 source and target lines are each covered exactly once in source order",
        )
    )

    b006_relations = [
        row for row in records["relations"] if row.get("boundary_id") == BOUNDARY_ID
    ]
    relation_types = Counter(row["relation_type"] for row in b006_relations)
    exercises = [row for row in b006_units if row["unit_type"] == "exercise"]
    solutions = [row for row in b006_units if row["unit_type"] == "solution"]
    gaps = [row for row in b006_units if row["unit_type"] == "companion_gap"]
    checks.append(
        check(
            "exercise_answer_o001_topology",
            sorted(row["order"] for row in exercises) == [21, 22, 23, 24]
            and len(solutions) == 2
            and len(gaps) == 2
            and relation_types["answers"] == 2
            and relation_types["requires_companion_answer"] == 2
            and all(row.get("source_solution_used") is False for row in gaps),
            "exercises 2.21–2.24 link only public answers 2.21/2.23 and explicit independently authored O001 gaps 2.22/2.24",
        )
    )

    b006_concepts = [
        row for row in records["concepts"] if row.get("boundary_id") == BOUNDARY_ID
    ]
    b006_terms = [row for row in records["terms"] if row.get("boundary_id") == BOUNDARY_ID]
    term_ids = sorted(
        local_id
        for row in b006_terms
        for local_id in row["source_local_ids"]
        if local_id.startswith("R011-TERM-")
    )
    checks.append(
        check(
            "terminology_concept_prerequisite_model",
            len(b006_concepts) == 20
            and len(b006_terms) == 20
            and term_ids == [f"R011-TERM-{number:04d}" for number in range(122, 142)]
            and {row["concept_id"] for row in b006_terms}
            == {row["id"] for row in b006_concepts}
            and relation_types["introduces"] == 20
            and relation_types["prerequisite"] == 16,
            "TERM-0122..0141 map one-to-one to locale-neutral concepts with introduction and prerequisite relations",
        )
    )

    b006_corrections = [
        row for row in records["corrections"] if row.get("boundary_id") == BOUNDARY_ID
    ]
    correction_ids = sorted(
        local_id
        for row in b006_corrections
        for local_id in row["source_local_ids"]
        if local_id.startswith("R011-ADV-")
    )
    upstream = [
        row for row in b006_corrections if row["upstream_report_disposition"] == "hold_until_corpus_complete_then_deduplicate"
    ]
    derivative = [
        row for row in b006_corrections if row["upstream_report_disposition"] == "not_upstream_derivative_only"
    ]
    checks.append(
        check(
            "correction_inventory_and_disposition",
            len(b006_corrections) == 15
            and correction_ids == [f"R011-ADV-{number:04d}" for number in range(65, 80)]
            and len(upstream) == 5
            and len(derivative) == 10,
            "ADV-0065..0069 are held for one deduplicated end-of-corpus upstream report; ADV-0070..0079 are derivative-only and excluded",
        )
    )

    term_evidence = list(
        csv.DictReader(
            io.StringIO(first["evidence/R011-B006_TERMINOLOGY.csv"].decode("utf-8"), newline="")
        )
    )
    adverse_evidence = [
        json.loads(line)
        for line in first["evidence/R011-B006_ADVERSE_LEDGER.jsonl"].decode("utf-8").splitlines()
    ]
    repair = json.loads(first["evidence/R011-B006_REPAIR_RECEIPT.json"])
    layout_repair = json.loads(first["evidence/R011-B006_LAYOUT_REPAIR_RECEIPT_V3.json"])
    layout_repair_v4 = json.loads(first["evidence/R011-B006_LAYOUT_REPAIR_RECEIPT_V4.json"])
    controls_ok = (
        len(term_evidence) == 141
        and term_evidence[-1]["term_id"] == "R011-TERM-0141"
        and len(adverse_evidence) == 79
        and adverse_evidence[-1]["id"] == "R011-ADV-0079"
        and repair["status"] == "repair_applied_and_reverse_verified"
        and repair["repairs"]["substitution_count"] == 17
        and repair["repairs"]["numeric_data_changed"] is False
        and repair["repairs"]["instructional_content_order_changed"] is False
        and repair["reverse_reconstruction"]["all_outputs_match_pre_repair_identities"] is True
        and layout_repair["status"] == "layout_repairs_applied_and_reverse_verified"
        and layout_repair["layout_repairs"]["substitution_count"] == 3
        and layout_repair["layout_repairs"]["repair_group_count"] == 2
        and layout_repair["layout_only_invariants"]["status"] == "passed"
        and layout_repair["reverse_reconstruction"]["all_outputs_match_source_snapshot_v2_identities"] is True
        and layout_repair_v4["status"] == "layout_repairs_applied_and_reverse_verified"
        and layout_repair_v4["layout_repairs"]["substitution_count"] == 1
        and layout_repair_v4["layout_repairs"]["repair_group_count"] == 1
        and layout_repair_v4["layout_only_invariants"]["status"] == "passed"
        and layout_repair_v4["reverse_reconstruction"]["all_outputs_match_source_snapshot_v3_identities"] is True
        and first["evidence/R011-B006_COMPONENT_RIGHTS.csv"] == m.RIGHTS_CONTROL.read_bytes()
    )
    checks.append(
        check(
            "bounded_controls_and_repair_evidence",
            controls_ok,
            "terminology through TERM-0141, adverse evidence through ADV-0079, exact component rights, and all three reverse-verified repair generations are embedded",
        )
    )

    b006_rights = [row for row in records["rights"] if row.get("boundary_id") == BOUNDARY_ID]
    b006_assets = [row for row in records["assets"] if row.get("boundary_id") == BOUNDARY_ID]
    asset_kinds = Counter(row["asset_kind"] for row in b006_assets)
    asset_files_ok = all(
        isinstance(row.get("target_bytes"), int)
        and isinstance(row.get("target_sha256"), str)
        and (LANE / row["target_path"]).is_file()
        and (LANE / row["target_path"]).stat().st_size == row["target_bytes"]
        and g.sha256_file(LANE / row["target_path"]) == row["target_sha256"]
        and row.get("rights_component_ids")
        for row in b006_assets
    )
    asset_model_ok = (
        len(b006_assets) == 35
        and asset_kinds
        == {
            "frozen_english_figure_witness": 13,
            "localized_vector_figure": 13,
            "authority_exact_figure_producer": 8,
            "deterministic_text_object_localizer": 1,
        }
        and len(b006_rights) == 2
        and asset_files_ok
        and relation_types["translates"] == 13
        and relation_types["produces"] == 26
        and relation_types["illustrates"] == 13
    )
    checks.append(
        check(
            "asset_code_data_rights_closure",
            asset_model_ok,
            "13 frozen English figure witnesses, 13 localized vectors, eight authority-exact R producers, the deterministic localizer, and smallest-component rights all replay",
        )
    )

    b006_artifacts = [
        row for row in records["artifacts"] if row.get("boundary_id") == BOUNDARY_ID
    ]
    artifact_files_ok = all(
        exact_file({"path": row["path"], "bytes": row["bytes"], "sha256": row["sha256"]})
        and row.get("status") == "passed"
        and row.get("placeholder") is not True
        for row in b006_artifacts
    )
    checks.append(
        check(
            "artifact_identity_replay",
            len(b006_artifacts) == 27 and artifact_files_ok,
            "all 27 B006 source/control/repair/rejection/asset/build/PDF/visual/backend artifacts match exact live or staged byte identities",
        )
    )

    final_gate_inputs_exact = all(exact_file(identity) for identity in supplied_inputs.values())
    candidate = json.loads(first["evidence/R011-B006_CANDIDATE_BUILD_QA_V4.json"])
    build = json.loads(first["evidence/R011-B006_BUILD_QA.json"])
    visual = json.loads(first["evidence/R011-B006_VISUAL_AUDIT.json"])
    render_lines = first["evidence/R011-B006_RENDER_MANIFEST.tsv"].decode("utf-8").splitlines()
    locator = json.loads(first["evidence/R011-B006_PAGE_LOCATOR.json"])
    zero = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
    copied_final_evidence_exact = (
        first["evidence/R011-B006_BUILD_GATE.py"] == (LANE / supplied_inputs["build_gate_script"]["path"]).read_bytes()
        and first["evidence/R011-B006_CANDIDATE_BUILD_QA_V4.json"] == (LANE / supplied_inputs["candidate_build_qa"]["path"]).read_bytes()
        and first["evidence/R011-B006_BUILD_QA.json"] == (LANE / supplied_inputs["build_qa"]["path"]).read_bytes()
        and first["evidence/R011-B006_RENDER_MANIFEST.tsv"] == (LANE / supplied_inputs["render_manifest"]["path"]).read_bytes()
        and first["evidence/R011-B006_PAGE_LOCATOR.json"] == (LANE / supplied_inputs["page_locator"]["path"]).read_bytes()
        and first["evidence/R011-B006_VISUAL_CONTACT_SHEET.png"] == (LANE / supplied_inputs["contact_sheet"]["path"]).read_bytes()
        and first["evidence/R011-B006_VISUAL_AUDIT.json"] == (LANE / supplied_inputs["visual_audit"]["path"]).read_bytes()
        and first["evidence/R011-B006_VISUAL_FINALIZER.py"] == (LANE / supplied_inputs["visual_finalizer"]["path"]).read_bytes()
    )
    final_gate_ok = (
        final_gate_inputs_exact
        and copied_final_evidence_exact
        and candidate.get("status") == "pending_visual_review"
        and candidate.get("candidate_artifact", {}).get("promoted") is False
        and candidate.get("candidate_artifact", {}).get("sha256") == supplied_inputs["pdf"]["sha256"]
        and build.get("status") in {"pass", "passed"}
        and build.get("errors") == []
        and build.get("pending") == []
        and build.get("determinism", {}).get("byte_identical") is True
        and build.get("candidate_artifact", {}).get("promoted") is False
        and build.get("candidate_artifact", {}).get("sha256") == supplied_inputs["pdf"]["sha256"]
        and build.get("build_visual_admission", {}).get("status") == "passed"
        and build.get("build_visual_admission", {}).get("visual_status") == "passed"
        and build.get("build_visual_admission", {}).get("candidate_pdf_promoted") is False
        and visual.get("status") in {"pass", "passed"}
        and visual.get("severity_counts") == zero
        and visual.get("parent_acceptance", {}).get("inspected_pages") == m.EXPECTED_VISUAL_PAGES
        and visual.get("promotion", {}).get("performed") is False
        and locator.get("all_candidate_pages") == m.EXPECTED_VISUAL_PAGES
        and len(render_lines) == supplied_inputs["render_manifest"]["page_count"]
        and manifest["final_gates"]["status"] == "passed_exact_v4_inputs_stage_only"
        and manifest["final_gates"]["build_gate_script"] == supplied_inputs["build_gate_script"]
        and manifest["final_gates"]["candidate_build_qa"] == supplied_inputs["candidate_build_qa"]
        and manifest["final_gates"]["build_qa"] == supplied_inputs["build_qa"]
        and manifest["final_gates"]["build_log"] == supplied_inputs["build_log"]
        and manifest["final_gates"]["build_text"] == supplied_inputs["build_text"]
        and manifest["final_gates"]["reviewed_candidate_pdf"] == supplied_inputs["pdf"]
        and manifest["final_gates"]["render_manifest"] == supplied_inputs["render_manifest"]
        and manifest["final_gates"]["page_locator"] == supplied_inputs["page_locator"]
        and manifest["final_gates"]["contact_sheet"] == supplied_inputs["contact_sheet"]
        and manifest["final_gates"]["visual_audit"] == supplied_inputs["visual_audit"]
        and manifest["final_gates"]["visual_finalizer"] == supplied_inputs["visual_finalizer"]
        and manifest["final_gates"]["severity_counts"] == zero
        and manifest["final_gates"]["inspected_pages"] == m.EXPECTED_VISUAL_PAGES
        and manifest["final_gates"]["candidate_pdf_promoted"] is False
    )
    checks.append(
        check(
            "final_build_pdf_visual_binding",
            final_gate_ok,
            "the exact final-V4 gate/candidate/final receipt, build log/text, reviewed id-ID PDF, 17-page render/locator/contact closure, zero-severity visual audit, and finalizer are mutually bound without falsely claiming PDF promotion",
        )
    )

    qa_events = [row for row in records["qa_events"] if row.get("boundary_id") == BOUNDARY_ID]
    checks.append(
        check(
            "typed_qa_state",
            len(qa_events) == 11
            and all(row.get("result") == "passed" and row.get("status") == "passed" for row in qa_events)
            and {row["qa_type"] for row in qa_events}
            >= {"topology", "language", "source", "visual", "rights", "build"},
            "all eleven B006 topology/language/source/repair/asset/rights/build/visual QA events are typed and passed",
        )
    )

    view_schema = json.loads(
        (m.BASE_BACKEND / "schemas" / "backend-view-columns-v0.1.0.json").read_text(encoding="utf-8")
    )
    expected_views = g.build_views(records, view_schema["views"])
    checks.append(
        check(
            "csv_projection_round_trip",
            len(expected_views) == 10 and all(first[path] == raw for path, raw in expected_views.items()),
            "all ten schema-fixed CSV views replay byte-for-byte from typed records",
        )
    )
    identity_rows = [
        json.loads(line) for line in first["identity_map.jsonl"].decode("utf-8").splitlines()
    ]
    checks.append(
        check(
            "identity_map_completeness",
            len(identity_rows) == EXPECTED_TOTAL_RECORD_COUNT
            and {row["id"] for row in identity_rows} == id_set,
            "the identity map covers all 1,969 records without language text as identity",
        )
    )

    manifest_schema = json.loads(
        (m.BASE_BACKEND / "schemas" / "backend-manifest-v0.1.0.schema.json").read_text(encoding="utf-8")
    )
    jsonschema.validate(manifest, manifest_schema, format_checker=jsonschema.FormatChecker())
    manifest_files_ok = True
    for entry in manifest["files"]:
        raw = (
            (m.BASE_BACKEND / entry["path"]).read_bytes()
            if entry["path"].startswith("schemas/")
            else first[entry["path"]]
        )
        if len(raw) != entry["bytes"] or g.sha256_bytes(raw) != entry["sha256"]:
            manifest_files_ok = False
            break
    checks.append(
        check(
            "manifest_schema_hashes_and_counts",
            manifest_files_ok
            and manifest["record_counts"]
            == {name: len(collection) for name, collection in sorted(records.items())},
            f"the manifest validates and binds all {len(manifest['files'])} payload/schema entries with reconciled counts",
        )
    )

    allowed_queued = {row["id"] for row in gaps}
    blocked_or_placeholder = [
        row["id"]
        for row in new_records
        if row.get("status") == "blocked"
        or row.get("result") in {"blocked", "pending"}
        or row.get("placeholder") is True
    ]
    unexpected_queued = [
        row["id"]
        for row in new_records
        if row.get("translation_state") == "queued" and row["id"] not in allowed_queued
    ]
    stage_state_ok = (
        not blocked_or_placeholder
        and not unexpected_queued
        and manifest["placeholder_count"] == 0
        and manifest["publication_blockers"] == []
        and manifest["publication_eligibility"] == "boundary_ready_for_separate_admission"
        and manifest["stage_state"]
        == {
            "status": "validated_candidate_not_promoted",
            "live_backend_mutated": False,
            "boundary_admitted": False,
            "promotion_performed": False,
        }
    )
    checks.append(
        check(
            "stage_only_no_placeholder_or_promotion",
            stage_state_ok,
            "the candidate has no placeholder/blocker, permits only the two explicit O001 queued gaps, and records that live promotion/admission did not occur",
        )
    )

    inventory_sha256, inventory_file_count, inventory_bytes = inventory_identity(STAGING_EXPORTS)
    final_inputs_raw = final_inputs_path.read_bytes()
    result = {
        "$schema": "r011-b006-backend-validation-receipt/v1",
        "base_boundary": m.BASE_BOUNDARY_ID,
        "boundary_id": BOUNDARY_ID,
        "status": "passed_stage_candidate_all_exact_gates",
        "manifest_sha256": g.sha256_bytes(first["manifest.json"]),
        "manifest_bytes": len(first["manifest.json"]),
        "record_count": len(all_records),
        "record_counts": manifest["record_counts"],
        "base_record_count": len(base_all),
        "preserved_base_record_count": preserved_base_count,
        "base_records_preserved_exact": preserved_base_count == len(base_all),
        "new_record_count": len(new_records),
        "payload_count": len(first),
        "payload_bytes": sum(len(raw) for raw in first.values()),
        "resolved_reference_count": resolved_reference_count,
        "authority_span_count": len(source_span_records),
        "localization_slice_count": len(localizations),
        "artifact_count": len(b006_artifacts),
        "stage_inventory_sha256": inventory_sha256,
        "stage_inventory_file_count": inventory_file_count,
        "stage_inventory_bytes": inventory_bytes,
        "final_input_manifest": {
            "path": final_inputs_path.relative_to(LANE).as_posix(),
            "bytes": len(final_inputs_raw),
            "sha256": g.sha256_bytes(final_inputs_raw),
        },
        "validator_checks_passed": len(checks),
        "validator_checks_total": len(checks),
        "validator_check_names": [item["name"] for item in checks],
        "placeholder_count": 0,
        "publication_blockers": [],
        "validation_target": STAGING_EXPORTS.relative_to(LANE).as_posix(),
        "live_backend_mutated": False,
        "boundary_admitted": False,
        "promotion_performed": False,
        "tooling": {
            "generator": {
                "path": GENERATOR_PATH.relative_to(LANE).as_posix(),
                "bytes": GENERATOR_PATH.stat().st_size,
                "sha256": g.sha256_file(GENERATOR_PATH),
            },
            "validator": {
                "path": Path(__file__).relative_to(LANE).as_posix(),
                "bytes": Path(__file__).stat().st_size,
                "sha256": g.sha256_file(Path(__file__)),
            },
        },
        "checks": checks,
    }
    return result, first


def result_bytes(result: dict[str, Any]) -> bytes:
    return (g.canonical_json(result) + "\n").encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--final-inputs",
        type=Path,
        required=True,
        help="the exact B006 final-gate input manifest used to generate the stage",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="perform an exact read-only replay and require the frozen receipt to match",
    )
    args = parser.parse_args()
    result, _payloads = validate(args.final_inputs.resolve())
    raw = result_bytes(result)
    if args.verify_only:
        if not RECEIPT_PATH.is_file() or RECEIPT_PATH.read_bytes() != raw:
            raise RuntimeError("read-only replay does not match the frozen stage receipt")
        print(f"checks={len(result['checks'])}")
        print(f"result={result['status']}")
        print(f"manifest_sha256={result['manifest_sha256']}")
        print(f"receipt_sha256={g.sha256_bytes(raw)}")
        print("read_only_replay=passed")
        print("live_backend_mutated=false")
        return 0
    RECEIPT_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = RECEIPT_PATH.with_name(RECEIPT_PATH.name + ".tmp")
    temporary.write_bytes(raw)
    if temporary.read_bytes() != raw:
        raise RuntimeError("temporary validation-receipt readback failed")
    temporary.replace(RECEIPT_PATH)
    if RECEIPT_PATH.read_bytes() != raw:
        raise RuntimeError("validation-receipt readback failed")
    print(f"checks={len(result['checks'])}")
    print(f"result={result['status']}")
    print(f"manifest_sha256={result['manifest_sha256']}")
    print(f"receipt_sha256={g.sha256_bytes(raw)}")
    print("live_backend_mutated=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
