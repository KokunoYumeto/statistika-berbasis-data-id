#!/usr/bin/env python3
"""Validate the isolated terminal-V3 R011-B008 backend stage."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

import generate_backend_b008 as pre
import generate_backend_b008_v3 as m


LANE = Path(__file__).resolve().parents[1]
RECEIPT_PATH = m.FINAL_ROOT / "BACKEND_VALIDATION_RECEIPT_R011-B008-FINAL-V3.json"
EXPECTED_NEW_COUNTS = {
    "artifacts": 13,
    "assets": 0,
    "concepts": 0,
    "corrections": 0,
    "courses": 0,
    "editions": 0,
    "localizations": 0,
    "programs": 0,
    "qa_events": 5,
    "relations": 13,
    "resources": 0,
    "rights": 0,
    "segments": 0,
    "terms": 0,
    "units": 0,
}
EXPECTED_TOTAL_RECORDS = 2503
EXPECTED_RELATION_KEYS = {
    "r011/relation/b008-final-v3-prefinal-manifest-documents-edition",
    "r011/relation/b008-final-v3-prefinal-receipt-validates-manifest",
    "r011/relation/b008-final-v3-source-manifest-snapshots-edition",
    "r011/relation/b008-final-v3-review-source-in-manifest",
    "r011/relation/b008-final-v3-answer-source-in-manifest",
    "r011/relation/b008-final-v3-source-qa-validates-manifest",
    "r011/relation/b008-final-v3-pdf-renders-edition",
    "r011/relation/b008-final-v3-build-qa-validates-pdf",
    "r011/relation/b008-final-v3-build-visual-validates-pdf",
    "r011/relation/b008-final-v3-root-visual-validates-pdf",
    "r011/relation/b008-final-v3-source-event-validates-manifest",
    "r011/relation/b008-final-v3-build-event-validates-pdf",
    "r011/relation/b008-final-v3-terminal-event-validates-edition",
}
EXPECTED_QA_KEYS = {
    "r011/qa/b008-final-v3-source-closure",
    "r011/qa/b008-final-v3-deterministic-build",
    "r011/qa/b008-final-v3-build-visual-sanity",
    "r011/qa/b008-final-v3-root-visual-audit",
    "r011/qa/b008-final-v3-terminal-binding",
}


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def check(name: str, condition: bool, detail: str) -> dict[str, str]:
    if not condition:
        raise RuntimeError(f"validation failed: {name}: {detail}")
    return {"name": name, "result": "passed", "detail": detail}


def load_records_from_payloads(payloads: dict[str, bytes]) -> dict[str, list[dict[str, Any]]]:
    return {name: m.load_jsonl(payloads[relative]) for name, relative in m.RECORD_PATHS.items()}


def load_records_from_root(root: Path) -> dict[str, list[dict[str, Any]]]:
    return {name: m.load_jsonl((root / relative).read_bytes()) for name, relative in m.RECORD_PATHS.items()}


def all_rows(records: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    return [row for rows in records.values() for row in rows]


def inventory_identity(root: Path) -> tuple[str, int, int]:
    lines: list[str] = []
    total = 0
    count = 0
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        raw = path.read_bytes()
        relative = path.relative_to(root).as_posix()
        lines.append(f"{relative}\t{len(raw)}\t{sha256_bytes(raw)}\n")
        total += len(raw)
        count += 1
    return sha256_bytes("".join(lines).encode("utf-8")), count, total


def record_types_ok(records: dict[str, list[dict[str, Any]]]) -> bool:
    expected_types = {
        "programs": "program",
        "courses": "course",
        "resources": "resource",
        "editions": "edition",
        "units": "unit",
        "concepts": "concept",
        "segments": "segment",
        "assets": "asset",
        "relations": "relation",
        "rights": "rights",
        "corrections": "correction",
        "localizations": "localization",
        "terms": "term",
        "qa_events": "qa_event",
        "artifacts": "artifact",
    }
    seen_ids: set[str] = set()
    seen_keys: set[str] = set()
    for name, rows in records.items():
        for row in rows:
            if (
                row.get("$schema") != "schemas/backend-record-v0.1.0.schema.json"
                or row.get("schema_version") != m.SCHEMA_VERSION
                or row.get("record_type") != expected_types[name]
                or not isinstance(row.get("stable_key"), str)
                or row.get("id") != m.g.stable_id(row["stable_key"])
                or row["id"] in seen_ids
                or row["stable_key"] in seen_keys
            ):
                return False
            seen_ids.add(row["id"])
            seen_keys.add(row["stable_key"])
    return True


def canonical_jsonl_ok(records: dict[str, list[dict[str, Any]]], payloads: dict[str, bytes]) -> bool:
    for name, relative in m.RECORD_PATHS.items():
        rows = records[name]
        if payloads[relative] != m.g.jsonl_bytes(rows):
            return False
        if [row["id"] for row in rows] != sorted(row["id"] for row in rows):
            return False
    return True


def references_resolve(records: dict[str, list[dict[str, Any]]]) -> tuple[bool, int, list[str]]:
    rows = all_rows(records)
    ids = {row["id"] for row in rows}
    unresolved: list[str] = []
    resolved = 0
    scalar_fields = (
        "resource_id",
        "edition_id",
        "parent_id",
        "concept_id",
        "source_segment_id",
        "subject_id",
        "affected_id",
        "from_id",
        "to_id",
        "unit_id",
        "supersedes_id",
    )
    for row in rows:
        for field in scalar_fields:
            value = row.get(field)
            if value is None:
                continue
            if value in ids:
                resolved += 1
            else:
                unresolved.append(f"{row['stable_key']}:{field}:{value}")
        for field in ("rights_component_ids", "concept_ids", "prerequisite_ids"):
            for value in row.get(field, []):
                if value in ids:
                    resolved += 1
                else:
                    unresolved.append(f"{row['stable_key']}:{field}:{value}")
    return not unresolved, resolved, unresolved


def prefinal_records() -> dict[str, list[dict[str, Any]]]:
    payloads = pre.build_payloads(None)
    return {name: pre.load_jsonl(payloads[relative]) for name, relative in pre.RECORD_PATHS.items()}


def records_preserve_prefinal(records: dict[str, list[dict[str, Any]]], base: dict[str, list[dict[str, Any]]]) -> bool:
    final_by_id = {row["id"]: row for row in all_rows(records)}
    base_rows = all_rows(base)
    return len(base_rows) == m.PREFINAL_RECORD_COUNT and all(final_by_id.get(row["id"]) == row for row in base_rows)


def expected_artifacts() -> dict[str, dict[str, Any]]:
    result = {
        "r011/artifact/b008-final-v3-prefinal-backend-manifest": {
            "path": "qa/b008-backend-final-v3/exports/evidence/R011-B008_PREFINAL_BACKEND_MANIFEST.json",
            **m.PREFINAL_MANIFEST_IDENTITY,
        },
        "r011/artifact/b008-final-v3-prefinal-backend-receipt": {
            "path": "qa/b008-backend-final-v3/exports/evidence/R011-B008_PREFINAL_BACKEND_VALIDATION_RECEIPT.json",
            **m.PREFINAL_RECEIPT_IDENTITY,
        },
        "r011/artifact/b008-final-v3-review-source": {
            "path": "qa/b008-build/source-snapshot-v3/ch_summarizing_data/TeX/review_exercises.tex",
            **m.FINAL_SOURCE_MEMBERS["ch_summarizing_data/TeX/review_exercises.tex"],
        },
        "r011/artifact/b008-final-v3-answer-source": {
            "path": "qa/b008-build/source-snapshot-v3/extraTeX/eoceSolutions/eoceSolutions.tex",
            **m.FINAL_SOURCE_MEMBERS["extraTeX/eoceSolutions/eoceSolutions.tex"],
        },
    }
    slug_by_source = {
        "qa/b008-source/R011-B008_SOURCE_MANIFEST_V3.tsv": "source-manifest",
        "qa/b008-source/R011-B008_SOURCE_QA_V3.json": "source-qa",
        "qa/b008-build/final-v3/main.pdf": "pdf",
        "qa/b008-build/final-v3/CANDIDATE_BUILD_QA_V3.json": "build-qa",
        "qa/b008-build/BUILD_ONLY_VISUAL_SANITY_V3.json": "build-visual",
        "qa/b008-visual/R011-B008_VISUAL_AUDIT_V3.json": "root-visual",
    }
    for source, item in m.FINAL_V3_INPUTS.items():
        slug = slug_by_source[source]
        path = source if item["destination"] is None else f"qa/b008-backend-final-v3/exports/{item['destination']}"
        result[f"r011/artifact/b008-final-v3-{slug}"] = {
            "path": path,
            "bytes": item["bytes"],
            "sha256": item["sha256"],
        }
    for slug, path in {
        "generator": m.SCRIPT_PATH,
        "finalizer": m.FINALIZER_PATH,
        "validator": m.VALIDATOR_PATH,
    }.items():
        result[f"r011/artifact/b008-final-v3-{slug}"] = {
            "path": path.relative_to(LANE).as_posix(),
            **m.identity(path),
        }
    return result


def binding_artifacts_ok(records: dict[str, list[dict[str, Any]]]) -> bool:
    expected = expected_artifacts()
    actual = {
        row["stable_key"]: row
        for row in records["artifacts"]
        if row.get("workflow_id") == m.WORKFLOW_ID
    }
    if set(actual) != set(expected):
        return False
    for key, wanted in expected.items():
        row = actual[key]
        if any(row.get(field) != wanted[field] for field in ("path", "bytes", "sha256")):
            return False
        if row.get("boundary_id") != m.BOUNDARY_ID or row.get("status") != "passed":
            return False
        if row.get("provenance") != m.PROVENANCE:
            return False
    pdf = actual["r011/artifact/b008-final-v3-pdf"]
    rights = {
        m.g.stable_id("r011/rights/upstream-cc-by-sa-3.0"),
        m.g.stable_id("r011/rights/b008-localized-figure-derivatives"),
        m.g.stable_id("r011/rights/b008-factual-data-limits"),
    }
    return (
        pdf.get("page_count") == 425
        and pdf.get("document_language") == "id-ID"
        and pdf.get("promoted") is False
        and set(pdf.get("rights_component_ids", [])) == rights
    )


def qa_and_relations_ok(records: dict[str, list[dict[str, Any]]]) -> bool:
    qa = {
        row["stable_key"]: row
        for row in records["qa_events"]
        if row.get("workflow_id") == m.WORKFLOW_ID
    }
    if set(qa) != EXPECTED_QA_KEYS or not all(row.get("result") == "passed" and row.get("status") == "passed" for row in qa.values()):
        return False
    old_gate_id = m.g.stable_id("r011/qa/b008-final-v2-binding")
    terminal = qa["r011/qa/b008-final-v3-terminal-binding"]
    if terminal.get("supersedes_id") != old_gate_id or terminal.get("qa_type") != "finalization":
        return False
    old = [row for row in records["qa_events"] if row.get("id") == old_gate_id]
    if len(old) != 1 or old[0].get("status") != "blocked" or old[0].get("result") != "blocked":
        return False
    relation_keys = {
        row["stable_key"]
        for row in records["relations"]
        if row.get("workflow_id") == m.WORKFLOW_ID
    }
    return relation_keys == EXPECTED_RELATION_KEYS


def manifest_files_ok(payloads: dict[str, bytes], manifest: dict[str, Any]) -> bool:
    entries = manifest.get("files", [])
    if len(entries) != len(payloads) - 1:
        return False
    by_path = {entry.get("path"): entry for entry in entries}
    if len(by_path) != len(entries) or set(by_path) != set(payloads) - {"manifest.json"}:
        return False
    for relative, raw in payloads.items():
        if relative == "manifest.json":
            continue
        entry = by_path[relative]
        if entry.get("bytes") != len(raw) or entry.get("sha256") != sha256_bytes(raw):
            return False
        if entry.get("records") != m.payload_record_count(relative, raw):
            return False
    return True


def final_manifest_gate_ok(manifest: dict[str, Any]) -> bool:
    inputs = {
        path: {"bytes": item["bytes"], "sha256": item["sha256"]}
        for path, item in m.FINAL_V3_INPUTS.items()
    }
    state = manifest.get("stage_state", {})
    resolution = manifest.get("prefinal_gate_resolution", {})
    return (
        manifest.get("new_final_v3_record_counts") == EXPECTED_NEW_COUNTS
        and manifest.get("new_final_v3_record_count") == sum(EXPECTED_NEW_COUNTS.values())
        and manifest.get("cumulative_b008_added_over_b007") == EXPECTED_TOTAL_RECORDS - m.BASE_RECORD_COUNT
        and manifest.get("final_v3_binding", {}).get("status") == "complete_exact_terminal_v3"
        and manifest.get("final_v3_binding", {}).get("inputs") == inputs
        and manifest.get("final_v3_binding", {}).get("source_member_identities") == m.FINAL_SOURCE_MEMBERS
        and manifest.get("final_v3_binding", {}).get("deterministic_pdf_passes_identical") is True
        and manifest.get("final_v3_binding", {}).get("root_visual_verdict") == "PASS"
        and manifest.get("final_v3_binding", {}).get("records_emitted") is True
        and resolution.get("obsolete_gate_id") == m.g.stable_id("r011/qa/b008-final-v2-binding")
        and resolution.get("superseding_event_id") == m.g.stable_id("r011/qa/b008-final-v3-terminal-binding")
        and state.get("status") == "isolated_terminal_v3_backend_generated"
        and state.get("final_v3_bound") is True
        and state.get("prefinal_stage_mutated") is False
        and state.get("live_backend_mutated") is False
        and state.get("canonical_source_mutated_by_backend_tools") is False
        and state.get("output_or_release_mutated") is False
        and state.get("boundary_admitted") is False
        and state.get("promotion_performed") is False
        and state.get("publication_performed") is False
        and manifest.get("admission_eligibility") == "ready_for_separate_guarded_admission_transaction"
    )


def identity_map_ok(records: dict[str, list[dict[str, Any]]], payloads: dict[str, bytes]) -> bool:
    expected = m.g.jsonl_bytes(
        {
            "id": row["id"],
            "record_type": row["record_type"],
            "stable_key": row["stable_key"],
            "source_local_ids": row.get("source_local_ids", []),
        }
        for row in all_rows(records)
    )
    return payloads.get("identity_map.jsonl") == expected


def views_ok(records: dict[str, list[dict[str, Any]]], payloads: dict[str, bytes]) -> bool:
    schema = json.loads(payloads["schemas/backend-view-columns-v0.1.0.json"])
    expected = m.g.build_views(records, schema["views"])
    return all(payloads.get(path) == raw for path, raw in expected.items())


def adversarial_suite(
    records: dict[str, list[dict[str, Any]]],
    base: dict[str, list[dict[str, Any]]],
    payloads: dict[str, bytes],
    manifest: dict[str, Any],
) -> list[dict[str, Any]]:
    tests: list[dict[str, Any]] = []

    mutated = deepcopy(records)
    mutated["artifacts"][-1]["id"] = mutated["artifacts"][-2]["id"]
    tests.append({"name": "duplicate_id", "detected": not record_types_ok(mutated)})

    mutated = deepcopy(records)
    base_first = all_rows(base)[0]
    target = next(row for row in all_rows(mutated) if row["id"] == base_first["id"])
    target["status"] = "tampered"
    tests.append({"name": "prefinal_record_mutation", "detected": not records_preserve_prefinal(mutated, base)})

    for name, key, field in [
        ("missing_final_pdf", "r011/artifact/b008-final-v3-pdf", None),
        ("pdf_hash_tamper", "r011/artifact/b008-final-v3-pdf", "sha256"),
        ("source_manifest_hash_tamper", "r011/artifact/b008-final-v3-source-manifest", "sha256"),
        ("build_receipt_hash_tamper", "r011/artifact/b008-final-v3-build-qa", "sha256"),
        ("root_visual_hash_tamper", "r011/artifact/b008-final-v3-root-visual", "sha256"),
    ]:
        mutated = deepcopy(records)
        if field is None:
            mutated["artifacts"] = [row for row in mutated["artifacts"] if row["stable_key"] != key]
        else:
            next(row for row in mutated["artifacts"] if row["stable_key"] == key)[field] = "0" * 64
        tests.append({"name": name, "detected": not binding_artifacts_ok(mutated)})

    mutated = deepcopy(records)
    terminal = next(row for row in mutated["qa_events"] if row["stable_key"] == "r011/qa/b008-final-v3-terminal-binding")
    terminal["status"] = "blocked"
    tests.append({"name": "terminal_event_blocked", "detected": not qa_and_relations_ok(mutated)})

    mutated = deepcopy(records)
    terminal = next(row for row in mutated["qa_events"] if row["stable_key"] == "r011/qa/b008-final-v3-terminal-binding")
    terminal["supersedes_id"] = None
    tests.append({"name": "obsolete_gate_not_superseded", "detected": not qa_and_relations_ok(mutated)})

    mutated = deepcopy(records)
    mutated["relations"] = [row for row in mutated["relations"] if row["stable_key"] != "r011/relation/b008-final-v3-root-visual-validates-pdf"]
    tests.append({"name": "terminal_relation_omission", "detected": not qa_and_relations_ok(mutated)})

    mutated_manifest = deepcopy(manifest)
    mutated_manifest["stage_state"]["boundary_admitted"] = True
    tests.append({"name": "false_admission_claim", "detected": not final_manifest_gate_ok(mutated_manifest)})

    mutated_manifest = deepcopy(manifest)
    mutated_manifest["files"][0]["sha256"] = "0" * 64
    tests.append({"name": "manifest_payload_hash_tamper", "detected": not manifest_files_ok(payloads, mutated_manifest)})

    if len(tests) != 12 or not all(item["detected"] for item in tests):
        raise RuntimeError(f"adversarial suite failed: {tests}")
    return tests


def validate() -> tuple[dict[str, Any], dict[str, bytes]]:
    payloads_one = m.build_payloads()
    payloads_two = m.build_payloads()
    checks: list[dict[str, str]] = []
    checks.append(
        check(
            "deterministic_generator_replay",
            payloads_one == payloads_two,
            f"all {len(payloads_one)} payloads are byte-identical across two independent in-memory final-V3 generations",
        )
    )
    payloads = payloads_one
    manifest = json.loads(payloads["manifest.json"])
    records = load_records_from_payloads(payloads)
    base = prefinal_records()

    exact_stage = m.FINAL_EXPORTS.is_dir()
    existing_files: set[str] = set()
    if exact_stage:
        existing_files = {
            path.relative_to(m.FINAL_EXPORTS).as_posix()
            for path in m.FINAL_EXPORTS.rglob("*")
            if path.is_file()
        }
        exact_stage = existing_files == set(payloads) and all(
            (m.FINAL_EXPORTS / relative).read_bytes() == raw for relative, raw in payloads.items()
        )
    checks.append(
        check(
            "staged_payload_identity",
            exact_stage,
            f"all {len(payloads)} expected terminal-V3 payloads are exact with no stale file",
        )
    )

    disk_records = load_records_from_root(m.FINAL_EXPORTS)
    checks.append(
        check(
            "record_inventory",
            sum(len(rows) for rows in records.values()) == EXPECTED_TOTAL_RECORDS
            and records == disk_records
            and manifest["record_counts"] == {name: len(rows) for name, rows in sorted(records.items())}
            and manifest["new_final_v3_record_counts"] == EXPECTED_NEW_COUNTS,
            f"{EXPECTED_TOTAL_RECORDS} exact records preserve {m.PREFINAL_RECORD_COUNT} prefinal records and append {sum(EXPECTED_NEW_COUNTS.values())} final-V3 records",
        )
    )

    checks.append(
        check(
            "prefinal_stage_and_record_preservation",
            records_preserve_prefinal(records, base),
            "all 2,472 prefinal B008 records are byte-semantically preserved and the immutable prefinal stage replays exactly",
        )
    )
    b007_rows = [row for row in all_rows(base) if row.get("boundary_id") != m.BOUNDARY_ID]
    final_by_id = {row["id"]: row for row in all_rows(records)}
    checks.append(
        check(
            "admitted_b007_preservation",
            len(b007_rows) == m.BASE_RECORD_COUNT and all(final_by_id.get(row["id"]) == row for row in b007_rows),
            "all 2,264 admitted B007 records remain exact through both append-only B008 stages",
        )
    )

    checks.append(
        check(
            "schema_envelope_stable_ids",
            record_types_ok(records),
            "every record has the expected schema envelope, unique stable key, and deterministic UUIDv5 identity",
        )
    )
    checks.append(
        check(
            "canonical_jsonl_serialization",
            canonical_jsonl_ok(records, payloads),
            "all typed JSONL is canonical UTF-8/NFC/LF and ascending UUID order",
        )
    )
    refs_ok, resolved, unresolved = references_resolve(records)
    checks.append(
        check(
            "referential_integrity",
            refs_ok,
            f"all typed references, including the superseded prefinal gate, resolve; resolved={resolved}, unresolved={unresolved}",
        )
    )

    checks.append(
        check(
            "final_v3_external_identity_and_semantic_closure",
            all(m.identity(LANE / path) == {"bytes": item["bytes"], "sha256": item["sha256"]} for path, item in m.FINAL_V3_INPUTS.items()),
            "the exact six supplied V3 source/PDF/build/visual inputs replay and their internal cross-bindings pass",
        )
    )
    checks.append(
        check(
            "source_member_closure",
            all(
                m.identity(LANE / "qa" / "b008-build" / "source-snapshot-v3" / path) == expected
                for path, expected in m.FINAL_SOURCE_MEMBERS.items()
            ),
            "the final 9,363-byte review source and 108,110-byte public-answer source are exact members of the 1,206-file V3 manifest",
        )
    )
    checks.append(
        check(
            "binding_artifact_topology",
            binding_artifacts_ok(records),
            "thirteen final-V3 artifacts bind the prefinal stage, six terminal inputs, two source members, and three exact tools",
        )
    )
    checks.append(
        check(
            "typed_terminal_qa_and_relations",
            qa_and_relations_ok(records),
            "five passed terminal QA events and thirteen relations supersede—without rewriting—the historical blocked final-V2 event",
        )
    )
    checks.append(
        check(
            "rights_and_provenance",
            binding_artifacts_ok(records),
            "the final PDF retains upstream text, localized figure, and factual-data rights links and every new artifact records exact model provenance",
        )
    )
    checks.append(
        check(
            "manifest_final_v3_gate",
            final_manifest_gate_ok(manifest),
            "the obsolete external parameter is replaced by a complete exact final-V3 binding while admission/promotion/publication remain false",
        )
    )
    checks.append(
        check(
            "manifest_hashes_counts",
            manifest_files_ok(payloads, manifest),
            f"manifest binds all {len(payloads) - 1} nonmanifest payloads and reconciles every projection count",
        )
    )
    checks.append(
        check(
            "identity_map_completeness",
            identity_map_ok(records, payloads),
            f"identity map covers all {EXPECTED_TOTAL_RECORDS} records without localized wording as identity",
        )
    )
    checks.append(
        check(
            "csv_projection_round_trip",
            views_ok(records, payloads),
            "all ten schema-fixed CSV projections replay byte-for-byte from typed records",
        )
    )

    profile_pattern = re.compile(rb"(?i)[a-z]:[\\/]+users[\\/]+[^\\/\r\n\"]+[\\/]")
    privacy_hits = sorted(path for path, raw in payloads.items() if profile_pattern.search(raw))
    checks.append(
        check(
            "privacy_portability_gate",
            not privacy_hits,
            f"zero absolute local user-profile paths occur in emitted payloads; hits={privacy_hits}",
        )
    )

    checks.append(
        check(
            "nonmutation_and_nonpublication_gate",
            manifest["stage_state"]
            == {
                "status": "isolated_terminal_v3_backend_generated",
                "final_v3_bound": True,
                "prefinal_stage_mutated": False,
                "live_backend_mutated": False,
                "canonical_source_mutated_by_backend_tools": False,
                "output_or_release_mutated": False,
                "boundary_admitted": False,
                "promotion_performed": False,
                "publication_performed": False,
            },
            "only the new isolated final-V3 QA stage exists; no admission, promotion, output/release, Git, network, or upstream action is claimed",
        )
    )

    adversarial = adversarial_suite(records, base, payloads, manifest)
    checks.append(
        check(
            "adversarial_mutation_suite",
            len(adversarial) == 12 and all(item["detected"] for item in adversarial),
            "12/12 pure in-memory corruptions are detected",
        )
    )

    inventory_sha, inventory_count, inventory_bytes = inventory_identity(m.FINAL_EXPORTS)
    result = {
        "$schema": "r011-b008-backend-final-v3-validation-receipt/v1",
        "boundary_id": m.BOUNDARY_ID,
        "status": "passed_isolated_terminal_v3_backend_ready_for_guarded_admission",
        "validation_target": "qa/b008-backend-final-v3/exports",
        "validator_checks_total": len(checks),
        "validator_checks_passed": len(checks),
        "checks": checks,
        "adversarial_tests": adversarial,
        "record_count": EXPECTED_TOTAL_RECORDS,
        "record_counts": manifest["record_counts"],
        "prefinal_record_count": m.PREFINAL_RECORD_COUNT,
        "prefinal_records_preserved_exact": True,
        "admitted_b007_record_count": m.BASE_RECORD_COUNT,
        "admitted_b007_records_preserved_exact": True,
        "new_final_v3_record_count": manifest["new_final_v3_record_count"],
        "new_final_v3_record_counts": manifest["new_final_v3_record_counts"],
        "final_v3_binding": manifest["final_v3_binding"],
        "manifest_bytes": len(payloads["manifest.json"]),
        "manifest_sha256": sha256_bytes(payloads["manifest.json"]),
        "stage_inventory_file_count": inventory_count,
        "stage_inventory_bytes": inventory_bytes,
        "stage_inventory_sha256": inventory_sha,
        "resolved_reference_count": resolved,
        "admission_eligibility": manifest["admission_eligibility"],
        "prefinal_stage_mutated": False,
        "live_backend_mutated": False,
        "canonical_source_mutated": False,
        "output_or_release_mutated": False,
        "promotion_performed": False,
        "boundary_admitted": False,
        "publication_performed": False,
        "tooling": {
            "generator": {"path": "scripts/generate_backend_b008_v3.py", **m.identity(m.SCRIPT_PATH)},
            "finalizer": {"path": "scripts/finalize_backend_b008_v3.py", **m.identity(m.FINALIZER_PATH)},
            "validator": {"path": "scripts/validate_backend_b008_v3.py", **m.identity(m.VALIDATOR_PATH)},
        },
    }
    return result, payloads


def result_bytes(result: dict[str, Any]) -> bytes:
    return (m.g.canonical_json(result) + "\n").encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate without writing the receipt")
    args = parser.parse_args()
    result, _payloads = validate()
    raw = result_bytes(result)
    if not args.check:
        RECEIPT_PATH.parent.mkdir(parents=True, exist_ok=True)
        if RECEIPT_PATH.exists() and RECEIPT_PATH.read_bytes() != raw:
            raise RuntimeError("refusing to overwrite differing terminal-V3 validation receipt")
        RECEIPT_PATH.write_bytes(raw)
        if RECEIPT_PATH.read_bytes() != raw:
            raise RuntimeError("terminal-V3 validation receipt readback mismatch")
    print(
        m.g.canonical_json(
            {
                "boundary_id": m.BOUNDARY_ID,
                "result": result["status"],
                "checks": result["validator_checks_total"],
                "records": result["record_count"],
                "new_final_v3_records": result["new_final_v3_record_count"],
                "receipt_written": not args.check,
                "live_backend_mutated": False,
                "admission_or_promotion_performed": False,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
