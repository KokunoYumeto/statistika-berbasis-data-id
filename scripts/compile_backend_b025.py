#!/usr/bin/env python3
"""Deterministically append R011-B025 records to the exact admitted B024 backend.

The compiler has read-only ``--self-test`` and ``--probe`` modes.  ``--admit``
preserves exact B024 preimages, stages every payload, atomically advances the
backend, writes a sanitized receipt, and immediately replays it.  It never uses
Git, credentials, the network, controls, output, release files, or upstream.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import shutil
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

import jsonschema

import admit_backend_b024 as serializers
from b025_pipeline_contract import (
    BACKEND_ADMISSION_RECEIPT_PATH, BACKEND_REPLAY_RECEIPT_PATH, BASE_ADMISSION,
    BASE_BACKEND, BASE_REPLAY, BINDINGS_PATH, BOUNDARY_ID, MODEL,
    POST_BUILD_ROLES, SEALED_INPUTS, StageGateError, canonical, identity,
    load_bindings, repo_path, verify_record, verify_sealed_inputs,
)


ROOT = Path(__file__).resolve().parents[1]
EXPORTS = ROOT / "backend/exports"
PREIMAGES = ROOT / "qa/b025-backend-admission/preimages-R011-B025"
PREIMAGE_MANIFEST = PREIMAGES / "PREIMAGE_MANIFEST.json"
RECORDED_AT = "2026-08-29T23:59:00+02:00"
WORKFLOW = "r011-openintro-statistics-id-b025-backend-admission"
SCHEMA_VERSION = "0.1.0"
AUTHORITY = "authority/upstream/openintro-statistics-fee25091fb24e89c36296fd67c48c1fcf7a93b6e"
BASE_RECORD_COUNT = 8_911
BASE_RECORD_COUNTS = {"artifacts":756,"assets":419,"concepts":271,"corrections":182,"courses":1,"editions":1,"localizations":708,"programs":1,"qa_events":335,"relations":4430,"resources":1,"rights":53,"segments":708,"terms":304,"units":741}
RECORD_PATHS = copy.deepcopy(serializers.RECORD_PATHS)
REQUIRED_VIEWS = list(serializers.REQUIRED_VIEWS)
GENERATED = set(RECORD_PATHS.values()) | set(REQUIRED_VIEWS) | {"identity_map.jsonl"}


def raw_identity(raw: bytes) -> dict[str, Any]:
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def require(path: str, expected: dict[str, Any] | None = None) -> bytes:
    file = repo_path(path)
    raw = file.read_bytes()
    if expected and raw_identity(raw) != {k: expected[k] for k in ("bytes", "sha256")}:
        raise StageGateError(f"exact input changed: {path}")
    return raw


def load_base(base_root: Path) -> tuple[dict[str, list[dict]], dict]:
    manifest_raw = (base_root / "manifest.json").read_bytes()
    if raw_identity(manifest_raw) != {k: BASE_BACKEND[k] for k in ("bytes", "sha256")}:
        raise StageGateError("backend is not exact B024 preimage")
    manifest = json.loads(manifest_raw)
    if manifest.get("boundary_id") != "R011-B024" or manifest.get("record_count") != BASE_RECORD_COUNT or manifest.get("record_counts") != BASE_RECORD_COUNTS:
        raise StageGateError("B024 base manifest semantics changed")
    files = {row["path"]: row for row in manifest["files"]}
    records = {}
    for table, relative in RECORD_PATHS.items():
        raw = (base_root / relative).read_bytes()
        row = files[relative]
        if raw_identity(raw) != {k: row[k] for k in ("bytes", "sha256")}:
            raise StageGateError(f"B024 base record changed: {relative}")
        records[table] = serializers.load_jsonl(raw)
        if serializers.jsonl_bytes(records[table]) != raw:
            raise StageGateError(f"noncanonical B024 record table: {relative}")
    return records, manifest


def load_binding_against_frozen_preimage() -> dict[str, Any]:
    """Replay the binding after live backend promotion, using the frozen B024 base."""
    try:
        payload = json.loads(BINDINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StageGateError("post-build binding is absent or invalid during replay") from exc
    if payload.get("boundary_id") != BOUNDARY_ID or payload.get("status") != "PASS_EXACT_B025_POST_BUILD_IDENTITIES_BOUND":
        raise StageGateError("post-build binding boundary/status changed during replay")
    sealed = {"base_backend": {key: BASE_BACKEND[key] for key in ("path", "bytes", "sha256")}}
    sealed.update({role: verify_record(role, spec) for role, spec in SEALED_INPUTS.items()})
    if payload.get("sealed_inputs") != sealed:
        raise StageGateError("post-build binding sealed inputs changed during replay")
    outputs = payload.get("post_build_outputs")
    if not isinstance(outputs, dict) or set(outputs) != set(POST_BUILD_ROLES):
        raise StageGateError("post-build binding output roles changed during replay")
    for role, spec in POST_BUILD_ROLES.items():
        observed = identity(repo_path(spec["path"]))
        row = outputs[role]
        if {key: row.get(key) for key in observed} != observed:
            raise StageGateError(f"post-build output changed during replay: {role}")
    return payload


def index(records: dict[str, list[dict]]) -> dict[str, dict]:
    rows = {}
    for table in records.values():
        for row in table:
            if row["stable_key"] in rows:
                raise StageGateError("duplicate stable key in base")
            rows[row["stable_key"]] = row
    return rows


def record(record_type: str, key: str, **fields: Any) -> dict:
    row = {"$schema":"schemas/backend-record-v0.1.0.schema.json","schema_version":SCHEMA_VERSION,"record_type":record_type,"id":serializers.stable_id(key),"stable_key":key,"status":"active","recorded_at":RECORDED_AT,"workflow_id":WORKFLOW,"boundary_id":BOUNDARY_ID,"supersedes_id":None}
    row.update(fields)
    return serializers.normalize(row)


def common(idx: dict[str, dict], rights: list[str], **fields: Any) -> dict:
    row = {"resource_id":idx["r011/resource/openintro-statistics"]["id"],"edition_id":idx["r011/edition/fee25091"]["id"],"source_local_ids":[BOUNDARY_ID],"parent_id":None,"order":0,"source_path":None,"source_span":None,"source_sha256":None,"locale":"zxx","translation_state":"visually_checked","rights_component_ids":rights}
    row.update(fields)
    return row


def add(records: dict[str, list[dict]], idx: dict[str, dict], table: str, row: dict) -> dict:
    if row["stable_key"] in idx:
        raise StageGateError(f"B025 stable key collision: {row['stable_key']}")
    records[table].append(row); idx[row["stable_key"]] = row
    return row


def span(raw: bytes, first: int, last: int) -> tuple[dict, bytes]:
    return serializers.line_span(raw, first, last)


def evidence(binding: dict, base_root: Path) -> tuple[dict[str, bytes], dict[str, dict]]:
    specs: dict[str, dict] = {}
    for role, row in {**binding["sealed_inputs"], **binding["post_build_outputs"]}.items():
        specs[role] = row
    fixed = {
        "base_b024_manifest": BASE_BACKEND,
        "base_b024_admission": BASE_ADMISSION,
        "base_b024_replay": BASE_REPLAY,
        "source_chapter": {"path": f"{AUTHORITY}/ch_inference_for_props/TeX/ch_inference_for_props.tex", "bytes":103385,"sha256":"a2470ca3041209d1f1194b3ab27e8124405d8fdbd1ccece89a0319be13fae8a7"},
        "source_exercises": {"path": f"{AUTHORITY}/ch_inference_for_props/TeX/testing_for_independence_in_two-way_tables.tex", "bytes":4558,"sha256":"5f22aeaa256054748f626dad74a279e57d3a098f6060dc057a9625f7b2259e9a"},
        "source_answers": {"path": f"{AUTHORITY}/extraTeX/eoceSolutions/eoceSolutions.tex", "bytes":106045,"sha256":"6c4e01376db4c023cc7b3f9949490e57220ef1cb831c580da71efde6ce723268"},
        "source_figure": {"path": f"{AUTHORITY}/ch_inference_for_props/figures/iPodChiSqTail/iPodChiSqTail.pdf", "bytes":5719,"sha256":"789e9da58ef275f9996f2414cb53ed5edb134b9df2f3f194e7be42d7ce810403"},
        "source_figure_producer": {"path": f"{AUTHORITY}/ch_inference_for_props/figures/iPodChiSqTail/iPodChiSqTail.R", "bytes":368,"sha256":"16c6c2d5167308537e38b4120ece9e841f6d41d532d9dab32e744329d319d543"},
        "source_license": {"path": f"{AUTHORITY}/LICENSE.md", "bytes":2612,"sha256":"9bd77ff3e58e0b7f1331824b8195d4cf588851a6461cc3230d12410da7935223"},
    }
    specs.update(fixed)
    payloads, meta = {}, {}
    for role, row in sorted(specs.items()):
        if role in {"base_backend", "base_b024_manifest"}:
            raw = (base_root / "manifest.json").read_bytes()
            if raw_identity(raw) != {key: row[key] for key in ("bytes", "sha256")}:
                raise StageGateError("exact B024 manifest preimage changed")
        else:
            raw = require(row["path"], row)
        destination = f"evidence/b025/{role}--{Path(row['path']).name}"
        payloads[destination] = raw
        meta[role] = {**row, "destination": destination}
    return payloads, meta


def compile(base_root: Path) -> dict[str, Any]:
    binding = load_bindings(require_complete=True) if base_root.resolve() == EXPORTS.resolve() else load_binding_against_frozen_preimage()
    records, base_manifest = load_base(base_root)
    base_rows = {table: [canonical(row) for row in rows] for table, rows in records.items()}
    idx = index(records)
    evidence_payloads, ev = evidence(binding, base_root)
    upstream = idx["r011/rights/upstream-cc-by-sa-3.0"]["id"]
    prior_derivative = idx["r011/rights/b024-localized-chi-square-goodness-of-fit"]["id"]
    rights = [upstream, prior_derivative]
    chapter = idx["r011/unit/source-label/ch_inference_for_props"]
    preceding = idx["r011/unit/source-label/oneWayChiSquare"]
    source_chapter = require(ev["source_chapter"]["path"], ev["source_chapter"])
    source_exercises = require(ev["source_exercises"]["path"], ev["source_exercises"])
    source_answers = require(ev["source_answers"]["path"], ev["source_answers"])
    main_a = require(ev["section_a_translation"]["path"], ev["section_a_translation"])
    main_b = require(ev["section_b_translation"]["path"], ev["section_b_translation"])
    target_ex = require(ev["exercise_translation"]["path"], ev["exercise_translation"])
    target_ans = require(ev["public_answer_translation"]["path"], ev["public_answer_translation"])

    source_section_span, source_section = span(source_chapter, 2008, 2434)
    section = add(records, idx, "units", record("unit", "r011/unit/source-label/twoWayTablesAndChiSquare", **common(idx, rights, source_local_ids=[BOUNDARY_ID,"twoWayTablesAndChiSquare","6.4"], parent_id=chapter["id"], order=4, source_path="ch_inference_for_props/TeX/ch_inference_for_props.tex", source_span=source_section_span, source_sha256=hashlib.sha256(source_section).hexdigest(), locale="en", unit_type="section", title="Testing for independence in two-way tables", target_title="Uji independensi pada tabel dua arah")))
    unit_specs = [
        ("section-intro", "section_intro", "Testing for independence in two-way tables", "Uji independensi pada tabel dua arah", 2008,2118, main_a,1,111,0),
        ("expected-counts", "subsection", "Expected counts in two-way tables", "Cacah harapan pada tabel dua arah", 2119,2238, main_a,112,231,1),
        ("chi-square-two-way", "subsection", "The chi-square test for two-way tables", "Uji khi-kuadrat untuk tabel dua arah", 2239,2434, main_b,1,196,2),
    ]
    pairs=[]; main_units={}
    for slug, typ, title, target_title, first,last,target_raw,tfirst,tlast,order in unit_specs:
        sspan,sraw=span(source_chapter,first,last); _tspan,traw=span(target_raw,tfirst,tlast)
        unit=add(records,idx,"units",record("unit",f"r011/unit/b025/{slug}",**common(idx,rights,parent_id=section["id"],order=order,source_path="ch_inference_for_props/TeX/ch_inference_for_props.tex",source_span=sspan,source_sha256=hashlib.sha256(sraw).hexdigest(),locale="en",unit_type=typ,title=title,target_title=target_title)))
        main_units[slug]=unit
        seg=add(records,idx,"segments",record("segment",f"r011/segment/b025/{slug}",**common(idx,rights,parent_id=unit["id"],unit_id=unit["id"],order=1,source_path="ch_inference_for_props/TeX/ch_inference_for_props.tex",source_span=sspan,source_sha256=hashlib.sha256(sraw).hexdigest(),locale="en",source_text=sraw.decode("utf-8"),protected_tokens=[],translation_state="source_frozen")))
        loc=add(records,idx,"localizations",record("localization",f"r011/localization/id-ID/b025/{slug}",**common(idx,rights,parent_id=seg["id"],unit_id=unit["id"],order=1,source_path=ev["section_a_translation" if target_raw is main_a else "section_b_translation"]["path"],source_sha256=hashlib.sha256(traw).hexdigest(),locale="id-ID",source_locale="en",target_locale="id-ID",source_segment_id=seg["id"],target_text=traw.decode("utf-8"),translation_provenance=MODEL,translation_state="visually_checked")))
        pairs.append((unit,seg,loc))

    ex_starts={35:5,36:30,37:63,38:87}; ex_ends={35:29,36:62,37:86,38:127}
    exercises={}; answers={}; gaps={}
    for number in range(35,39):
        sspan,sraw=span(source_exercises,ex_starts[number],ex_ends[number]); _ts,traw=span(target_ex,ex_starts[number],ex_ends[number])
        unit=add(records,idx,"units",record("unit",f"r011/unit/b025/exercise-{number}",**common(idx,rights,parent_id=section["id"],order=number,source_path="ch_inference_for_props/TeX/testing_for_independence_in_two-way_tables.tex",source_span=sspan,source_sha256=hashlib.sha256(sraw).hexdigest(),locale="en",unit_type="exercise",exercise_id=number,title=f"Exercise 6.{number}",target_title=f"Latihan 6.{number}")))
        exercises[number]=unit
        seg=add(records,idx,"segments",record("segment",f"r011/segment/b025/exercise-{number}",**common(idx,rights,parent_id=unit["id"],unit_id=unit["id"],order=1,source_path=unit["source_path"],source_span=sspan,source_sha256=hashlib.sha256(sraw).hexdigest(),locale="en",source_text=sraw.decode("utf-8"),protected_tokens=[],translation_state="source_frozen")))
        loc=add(records,idx,"localizations",record("localization",f"r011/localization/id-ID/b025/exercise-{number}",**common(idx,rights,parent_id=seg["id"],unit_id=unit["id"],order=1,source_path=ev["exercise_translation"]["path"],source_sha256=hashlib.sha256(traw).hexdigest(),locale="id-ID",source_locale="en",target_locale="id-ID",source_segment_id=seg["id"],target_text=traw.decode("utf-8"),translation_provenance=MODEL,translation_state="visually_checked")))
        pairs.append((unit,seg,loc))
        if number in (36,38):
            gaps[number]=add(records,idx,"units",record("unit",f"r011/unit/o001/b025/exercise-{number}-answer-gap",**common(idx,rights,parent_id=unit["id"],order=1,source_path=ev["o001_gap_ledger"]["path"],source_sha256=ev["o001_gap_ledger"]["sha256"],locale="id-ID",unit_type="mastery_companion_gap",exercise_id=number,title=f"O001 public-answer gap for exercise {number}",target_title=f"Kesenjangan jawaban publik O001 untuk latihan {number}",translation_state="queued",restricted_solution_accessed=False)))
    for number, first,last,tfirst,tlast in ((35,1500,1519,1,20),(37,1521,1543,22,44)):
        sspan,sraw=span(source_answers,first,last); _ts,traw=span(target_ans,tfirst,tlast)
        unit=add(records,idx,"units",record("unit",f"r011/unit/b025/public-answer-{number}",**common(idx,rights,parent_id=exercises[number]["id"],order=number,source_path="extraTeX/eoceSolutions/eoceSolutions.tex",source_span=sspan,source_sha256=hashlib.sha256(sraw).hexdigest(),locale="en",unit_type="public_answer",exercise_id=number,title=f"Public answer 6.{number}",target_title=f"Jawaban publik 6.{number}")))
        answers[number]=unit
        seg=add(records,idx,"segments",record("segment",f"r011/segment/b025/public-answer-{number}",**common(idx,rights,parent_id=unit["id"],unit_id=unit["id"],order=1,source_path=unit["source_path"],source_span=sspan,source_sha256=hashlib.sha256(sraw).hexdigest(),locale="en",source_text=sraw.decode("utf-8"),protected_tokens=[],translation_state="source_frozen")))
        loc=add(records,idx,"localizations",record("localization",f"r011/localization/id-ID/b025/public-answer-{number}",**common(idx,rights,parent_id=seg["id"],unit_id=unit["id"],order=1,source_path=ev["public_answer_translation"]["path"],source_sha256=hashlib.sha256(traw).hexdigest(),locale="id-ID",source_locale="en",target_locale="id-ID",source_segment_id=seg["id"],target_text=traw.decode("utf-8"),translation_provenance=MODEL,translation_state="visually_checked")))
        pairs.append((unit,seg,loc))

    term_specs=[("two-way table","tabel dua arah","two-way-table",["tabel kontingensi"]),("independence","independensi","independence",["saling bebas"]),("chi-square test for two-way tables","uji khi-kuadrat untuk tabel dua arah","chi-square-two-way-test",["uji independensi khi-kuadrat"]),("row total","total baris","row-total",[]),("column total","total kolom","column-total",[]),("conditional proportion","proporsi bersyarat","conditional-proportion",[])]
    terms=[]
    for order,(source_term,target_term,slug,variants) in enumerate(term_specs,204):
        concept=add(records,idx,"concepts",record("concept",f"r011/concept/b025/{slug}",**common(idx,rights,parent_id=section["id"],order=order,source_path="ch_inference_for_props/TeX/ch_inference_for_props.tex",source_span=source_section_span,source_sha256=hashlib.sha256(source_section).hexdigest(),locale="zxx",name=source_term,concept_kind="statistical_concept")))
        term=add(records,idx,"terms",record("term",f"r011/term/id-ID/b025/{order:04d}",**common(idx,rights,parent_id=concept["id"],order=order,source_path=ev["independent_translation_qa"]["path"],source_sha256=ev["independent_translation_qa"]["sha256"],locale="id-ID",concept_id=concept["id"],source_term=source_term,target_term=target_term,variants=variants,register="academic",decision="admit exact B025 controlled term",evidence="Independent complete B025 translation and terminology audit.",translation_state="language_reviewed")))
        terms.append((concept,term))

    source_asset=add(records,idx,"assets",record("asset","r011/asset/b025/source/ipod-chi-square-tail",**common(idx,[upstream],parent_id=section["id"],order=1,source_path="ch_inference_for_props/figures/iPodChiSqTail/iPodChiSqTail.pdf",source_sha256=ev["source_figure"]["sha256"],locale="en",asset_kind="generated_vector_figure_source",media_type="application/pdf",bytes=ev["source_figure"]["bytes"],sha256=ev["source_figure"]["sha256"],localized=False,content_localization_required=True,translation_state="source_frozen")))
    producer=add(records,idx,"assets",record("asset","r011/asset/b025/producer/ipod-chi-square-tail",**common(idx,[upstream],parent_id=source_asset["id"],order=1,source_path="ch_inference_for_props/figures/iPodChiSqTail/iPodChiSqTail.R",source_sha256=ev["source_figure_producer"]["sha256"],locale="zxx",asset_kind="r_figure_producer",media_type="text/x-r-source",bytes=ev["source_figure_producer"]["bytes"],sha256=ev["source_figure_producer"]["sha256"],translated=False,translation_state="source_frozen")))
    localized=add(records,idx,"assets",record("asset","r011/asset/b025/figure/ipod-chi-square-tail-id",**common(idx,rights,parent_id=source_asset["id"],order=2,source_path=source_asset["source_path"],source_sha256=source_asset["sha256"],locale="id-ID",asset_kind="localized_vector_figure",media_type="application/pdf",bytes=ev["localized_chart"]["bytes"],sha256=ev["localized_chart"]["sha256"],target_path=ev["localized_chart"]["path"],target_sha256=ev["localized_chart"]["sha256"],localized=True,translation_provenance=MODEL,reader_visible_strings=["Luas ekor (1 dari 500 juta)","terlalu kecil untuk terlihat"],removed_reader_visible_strings=["Tail area (1 / 500 million)","is too small to see"])))

    correction_rows=[]
    blueprint=json.loads(require(ev["source_blueprint"]["path"],ev["source_blueprint"]))
    for order,candidate in enumerate(blueprint["correction_candidates"],1):
        location=candidate["location"]; first=int(location.rsplit(":",1)[1].split("-")[0]); last=int(location.rsplit(":",1)[1].split("-")[-1])
        source_raw=source_chapter if "ch_inference_for_props.tex" in location else (source_exercises if "testing_for_independence" in location else source_answers)
        sspan,sraw=span(source_raw,first,last)
        correction_rows.append(add(records,idx,"corrections",record("correction",f"r011/correction/b025-{order:02d}",**common(idx,rights,parent_id=section["id"],order=order,source_path=location.split(":")[0],source_span=sspan,source_sha256=hashlib.sha256(sraw).hexdigest(),locale="id-ID",affected_id=section["id"],correction_type="source_semantic_correction",correction_id=f"C{order:02d}",confidence=candidate["confidence"],source_claim=candidate["source_issue"],proposed_correction=candidate["translation_action"],rationale="Pinned blueprint and independent B025 audit confirm this bounded correction.",evidence=ev["independent_translation_qa"]["path"],upstream_report_disposition="hold_until_complete_corpus_then_single_deduplicated_high-confidence-report",authority_mutated=False))))

    artifact_by_role={}
    for order,(role,item) in enumerate(sorted(ev.items()),1):
        state="visually_checked" if role in {"candidate_pdf","candidate_text","pagewise_language_qa","automated_visual_qa","root_visual_qa","localized_chart","localized_chart_visual_qa"} else ("built" if role=="build_qa" else "structurally_verified")
        artifact_by_role[role]=add(records,idx,"artifacts",record("artifact",f"r011/artifact/b025/{role}",**common(idx,rights if role not in {"base_b024_manifest","base_b024_admission","base_b024_replay"} else [],parent_id=section["id"],order=order,source_path=item["path"],source_sha256=item["sha256"],locale="zxx",artifact_kind=role,path=item["path"],evidence_copy_path=item["destination"],bytes=item["bytes"],sha256=item["sha256"],result="exact B025 frozen input or deterministic evidence",provenance=MODEL,translation_state=state)))

    qa_specs=[("source","source_blueprint"),("translation_a","main_translation_a_qa"),("translation_b","main_translation_b_qa"),("exercise_answer","exercise_answer_qa"),("independent_translation","independent_translation_qa"),("chart_localization","localized_chart_qa"),("chart_visual","localized_chart_visual_qa"),("build","build_qa"),("language","pagewise_language_qa"),("automated_visual","automated_visual_qa"),("root_visual","root_visual_qa"),("interoperability","independent_translation_verifier")]
    qa_rows=[]
    for order,(kind,role) in enumerate(qa_specs,1):
        art=artifact_by_role[role]
        qa_rows.append(add(records,idx,"qa_events",record("qa_event",f"r011/qa/b025/{kind}-{order:02d}",**common(idx,[],parent_id=section["id"],order=order,locale="zxx",qa_type=kind,result="passed",subject_id=section["id"],witness_artifact_id=art["id"],witness_path=art["path"],detail=f"Exact B025 {kind} closure passed.",provenance=MODEL))))

    counters=Counter()
    def relation(kind:str,from_id:str,to_id:str,qualifier:str,order:int=0):
        counters[kind]+=1
        add(records,idx,"relations",record("relation",f"r011/relation/b025/{kind}/{counters[kind]:04d}",**common(idx,[],relation_type=kind,from_id=from_id,to_id=to_id,qualifier=qualifier,order=order)))
    relation("contains",chapter["id"],section["id"],"source hierarchy",4); relation("precedes",preceding["id"],section["id"],"source order",1)
    for order,(unit,seg,loc) in enumerate(pairs,1): relation("contains",section["id"],unit["id"],"B025 unit",order); relation("unit_contains_segment",unit["id"],seg["id"],"translatable segment",order); relation("localizes",seg["id"],loc["id"],"id-ID localization",order)
    for number in range(35,39):
        relation("exercises",exercises[number]["id"],section["id"],"Section 6.4 exercise",number)
        if number in answers: relation("answers",answers[number]["id"],exercises[number]["id"],"upstream-public answer",number)
        else: relation("requires_companion_answer",exercises[number]["id"],gaps[number]["id"],"O001 gap; no restricted solution",number)
    for concept,term in terms: relation("covers",section["id"],concept["id"],"B025 concept",term["order"]); relation("lexicalizes",concept["id"],term["id"],"id-ID controlled term",term["order"])
    relation("uses_asset",section["id"],localized["id"],"reader-visible localized figure",1); relation("produces",producer["id"],source_asset["id"],"frozen R producer",1); relation("localizes_asset",source_asset["id"],localized["id"],"Indonesian annotation localization",1)
    for order,row in enumerate(correction_rows,1): relation("corrects",row["id"],section["id"],"high-confidence source issue held for single post-corpus report",order)
    for order,row in enumerate(qa_rows,1): relation("validates",row["id"],section["id"],row["qa_type"],order)
    for order,row in enumerate(artifact_by_role.values(),1): relation("documents",row["id"],section["id"],row["artifact_kind"],order)
    relation("supersedes",artifact_by_role["candidate_pdf"]["id"],idx["r011/artifact/b024/candidate_reader_pdf"]["id"],"reader lineage; B024 records retained",1)

    schema=json.loads((EXPORTS/"schemas/backend-record-v0.1.0.schema.json").read_text(encoding="utf-8")); validator=jsonschema.Draft202012Validator(schema,format_checker=jsonschema.FormatChecker())
    all_rows=[row for rows in records.values() for row in rows]; ids={row["id"] for row in all_rows}
    if len(ids)!=len(all_rows): raise StageGateError("duplicate backend record ID")
    new_rows=[row for row in all_rows if row.get("boundary_id")==BOUNDARY_ID]
    for row in new_rows:
        errors=list(validator.iter_errors(row))
        if errors: raise StageGateError(f"record schema failure {row['stable_key']}: {errors[0].message}")
        for field in ("resource_id","edition_id","parent_id","unit_id","source_segment_id","concept_id","affected_id","subject_id","witness_artifact_id","from_id","to_id"):
            referenced=row.get(field)
            if referenced is not None and referenced not in ids:
                raise StageGateError(f"record reference failure {row['stable_key']}: {field}={referenced!r}")
        for referenced in row.get("rights_component_ids", []):
            if referenced not in ids:
                raise StageGateError(f"record rights reference failure {row['stable_key']}: {referenced!r}")
    for table,old in base_rows.items():
        after=[canonical(row) for row in records[table] if row.get("boundary_id")!=BOUNDARY_ID]
        if after!=old: raise StageGateError(f"B024 canonical record preservation failed: {table}")

    payloads={path:serializers.jsonl_bytes(records[table]) for table,path in RECORD_PATHS.items()}
    views,view_counts=serializers.build_views(records); payloads.update(views); payloads["identity_map.jsonl"]=serializers.identity_map_bytes(records); payloads.update(evidence_payloads)
    counts={table:len(rows) for table,rows in sorted(records.items())}; new_counts=Counter(row["record_type"] for row in all_rows if row.get("boundary_id")==BOUNDARY_ID)
    files={row["path"]:copy.deepcopy(row) for row in base_manifest["files"] if row["path"] not in payloads}
    for path,raw in payloads.items():
        table=next((t for t,p in RECORD_PATHS.items() if p==path),None); count=len(records[table]) if table else (view_counts.get(path) if path in view_counts else (len(all_rows) if path=="identity_map.jsonl" else None))
        files[path]={"path":path,**raw_identity(raw),"records":count}
    reader=binding["post_build_outputs"]["candidate_pdf"]
    manifest=copy.deepcopy(base_manifest); manifest.update({"boundary_id":BOUNDARY_ID,"workflow_id":WORKFLOW,"recorded_at":RECORDED_AT,"stage_state":"live_admitted_candidate","admission_eligibility":"admitted_pending_publication","base_preservation":{"boundary_id":"R011-B024","manifest":{k:BASE_BACKEND[k] for k in ("bytes","sha256")},"record_count":BASE_RECORD_COUNT,"record_counts":BASE_RECORD_COUNTS,"all_b024_and_earlier_records_preserved_canonical_bytes":True,"all_b024_jsonl_csv_identity_exports_replay_byte_identically_from_preserved_records":True},"base_record_counts":BASE_RECORD_COUNTS,"new_b025_record_count":sum(new_counts.values()),"new_b025_record_counts":dict(sorted(new_counts.items())),"record_count":len(all_rows),"record_counts":counts,"scope":{"included":"Indonesian front matter and Chapters 1-5 plus Chapter 6 Sections 6.1-6.4; exercises 1-38; public odd answers 1-37.","new_b025_scope":"Complete two-way chi-square independence section, exercises 35-38, public answers 35/37, O001 gaps 36/38, and one localized figure.","excluded":["Chapter 7 and later","non-public even answers 2-38","restricted instructor solutions"],"reader_pages":reader["pages"],"reader_bytes":reader["bytes"],"reader_sha256":reader["sha256"],"next_cursor":{"path":"ch_inference_for_means/TeX/ch_inference_for_means.tex","line":1,"first_section_line":29,"label_line":32,"boundary_id":"R011-B026"}},"topology":{"chapter":6,"section":"6.4","subsections":2,"exercise_numbers":[35,36,37,38],"public_answers":[35,37],"o001_companion_gaps":[36,38],"source_assets":1,"r_producers":1,"standalone_datasets":0,"localized_figure_content":1,"restricted_solutions_accessed_or_invented":False},"source_corrections":{"count":8,"high_confidence_upstream_candidates":8,"upstream_reporting":"hold_until_complete_corpus_then_single_deduplicated-high-confidence-report","authority_mutated":False},"build_binding":{"status":"exact_final_candidate_bound","candidate_identities_bound":True,"reader_pdf":reader,"reader_text":binding["post_build_outputs"]["candidate_text"],"build_receipt":binding["post_build_outputs"]["build_qa"],"deterministic_replays":2,"pdf_byte_identical":True,"text_byte_identical":True},"qa_closure":{"source":"passed","translation":"passed","independent_translation":"passed","exercise_answer":"passed","asset":"passed","rights":"passed","build":"passed","language":"passed","visual":"passed","language_receipt":binding["post_build_outputs"]["pagewise_language_qa"],"automated_visual_receipt":binding["post_build_outputs"]["automated_visual_qa"],"visual_receipt":binding["post_build_outputs"]["root_visual_qa"]},"interoperability":{"envelope_version":"v0","stable_locale_neutral_ids":True,"deterministic_json_jsonl_csv":True,"schema_validated":True,"schema_validation_scope":"all new B025 records; inherited B024-and-earlier rows proven canonical-byte identical","referential_integrity":True,"unit_selectable":True,"exercise_answer_gap_closure":True,"asset_code_data_rights_closure":True,"typed_correction_records":True,"final_state":"visually_checked"},"publication":{"status":"not_performed_by_backend_admission","prior_b024_publication":copy.deepcopy(base_manifest.get("publication")),"prior_b024_public_receipts_preserved":True},"files":[files[path] for path in sorted(files)]})
    manifest_raw=serializers.canonical_json(serializers.normalize(manifest)); jsonschema.validate(json.loads(manifest_raw),json.loads((EXPORTS/"schemas/backend-manifest-v0.1.0.schema.json").read_text(encoding="utf-8")))
    inventory=hashlib.sha256("".join(f"{p}\t{len(r)}\t{hashlib.sha256(r).hexdigest()}\n" for p,r in sorted({**payloads,"manifest.json":manifest_raw}.items())).encode()).hexdigest()
    return {"payloads":payloads,"manifest_raw":manifest_raw,"manifest":json.loads(manifest_raw),"inventory_sha256":inventory}


def twice(base_root: Path) -> dict[str, Any]:
    a=compile(base_root); b=compile(base_root)
    if a["manifest_raw"]!=b["manifest_raw"] or a["payloads"]!=b["payloads"]: raise StageGateError("two B025 backend compilations differ")
    return a


def save_preimages() -> None:
    if PREIMAGES.exists():
        if not PREIMAGE_MANIFEST.is_file(): raise StageGateError("foreign/incomplete B025 preimage directory exists")
        return
    PREIMAGES.mkdir(parents=True)
    base=json.loads((EXPORTS/"manifest.json").read_text(encoding="utf-8")); rows=[]
    for item in base["files"]:
        source=EXPORTS/item["path"]; target=PREIMAGES/item["path"]; target.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(source,target); rows.append({"path":item["path"],"bytes":item["bytes"],"sha256":item["sha256"]})
    shutil.copyfile(EXPORTS/"manifest.json",PREIMAGES/"manifest.json")
    PREIMAGE_MANIFEST.write_bytes(canonical({"boundary_id":"R011-B024","manifest":{k:BASE_BACKEND[k] for k in ("bytes","sha256")},"files":rows}))


def admit() -> dict:
    live_manifest=raw_identity((EXPORTS/"manifest.json").read_bytes())
    exact_base={key:BASE_BACKEND[key] for key in ("bytes","sha256")}
    if live_manifest==exact_base:
        verify_sealed_inputs(); load_bindings(require_complete=True); compiled=twice(EXPORTS); save_preimages()
        staged={}
        with tempfile.TemporaryDirectory(prefix="b025-backend-") as td:
            temp=Path(td)
            for rel,raw in {**compiled["payloads"],"manifest.json":compiled["manifest_raw"]}.items():
                path=temp/rel; path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(raw); staged[rel]=path
            for rel in sorted(compiled["payloads"]):
                target=EXPORTS/rel; target.parent.mkdir(parents=True,exist_ok=True); os.replace(staged[rel],target)
            os.replace(staged["manifest.json"],EXPORTS/"manifest.json")
    else:
        if not PREIMAGES.is_dir():
            raise StageGateError("live backend is not B024 and no exact B025 preimages exist")
        compiled=twice(PREIMAGES)
        if (EXPORTS/"manifest.json").read_bytes()!=compiled["manifest_raw"]:
            raise StageGateError("live backend is neither exact B024 nor exact interrupted B025 candidate")
        for rel,raw in compiled["payloads"].items():
            if not (EXPORTS/rel).is_file() or (EXPORTS/rel).read_bytes()!=raw:
                raise StageGateError(f"interrupted B025 candidate payload differs: {rel}")
    replay=verify(write_receipt=False)
    receipt={"$schema":"interlanguage.r011-b025-backend-admission/v1","boundary_id":BOUNDARY_ID,"status":"PASS_B025_BACKEND_ATOMIC_ADMISSION_AND_EXACT_REPLAY","base_manifest":{k:BASE_BACKEND[k] for k in ("bytes","sha256")},"live_manifest":identity(EXPORTS/"manifest.json"),"record_count":compiled["manifest"]["record_count"],"record_counts":compiled["manifest"]["record_counts"],"new_b025_record_count":compiled["manifest"]["new_b025_record_count"],"new_b025_record_counts":compiled["manifest"]["new_b025_record_counts"],"payload_inventory_sha256":compiled["inventory_sha256"],"post_build_binding":identity(repo_path("qa/b025-pipeline/R011-B025_POST_BUILD_BINDINGS.json")),"git_used":False,"credentials_accessed":False,"network_used":False,"publication_performed":False,"upstream_contact":False}
    out=repo_path(BACKEND_ADMISSION_RECEIPT_PATH); out.parent.mkdir(parents=True,exist_ok=True); out.write_bytes(canonical(receipt)); verify(write_receipt=True)
    return {**receipt,"receipt":identity(out),"replay":replay}


def verify(*, write_receipt: bool) -> dict:
    if not PREIMAGES.is_dir(): raise StageGateError("B025 backend preimages are absent")
    compiled=twice(PREIMAGES)
    if (EXPORTS/"manifest.json").read_bytes()!=compiled["manifest_raw"]: raise StageGateError("live B025 manifest differs from exact replay")
    for rel,raw in compiled["payloads"].items():
        if (EXPORTS/rel).read_bytes()!=raw: raise StageGateError(f"live B025 payload differs: {rel}")
    receipt={"$schema":"interlanguage.r011-b025-backend-replay/v1","boundary_id":BOUNDARY_ID,"status":"PASS_EXACT_B025_BACKEND_REPLAY_AND_REFERENTIAL_INTEGRITY","live_manifest":identity(EXPORTS/"manifest.json"),"record_count":compiled["manifest"]["record_count"],"record_counts":compiled["manifest"]["record_counts"],"new_b025_record_count":compiled["manifest"]["new_b025_record_count"],"new_b025_record_counts":compiled["manifest"]["new_b025_record_counts"],"payload_inventory_sha256":compiled["inventory_sha256"],"git_used":False,"credentials_accessed":False,"network_used":False,"publication_performed":False}
    if write_receipt:
        out=repo_path(BACKEND_REPLAY_RECEIPT_PATH); out.parent.mkdir(parents=True,exist_ok=True); out.write_bytes(canonical(receipt))
    return receipt


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__); mode=parser.add_mutually_exclusive_group(required=True); mode.add_argument("--self-test",action="store_true"); mode.add_argument("--probe",action="store_true"); mode.add_argument("--admit",action="store_true"); mode.add_argument("--verify",action="store_true"); args=parser.parse_args()
    if args.self_test:
        rows=verify_sealed_inputs(); result={"status":"PASS_B025_BACKEND_STATIC_INPUTS_EXACT_FINAL_BINDING_OPTIONAL","sealed_inputs":len(rows),"final_binding_present":repo_path("qa/b025-pipeline/R011-B025_POST_BUILD_BINDINGS.json").is_file(),"writes_performed":False}
    elif args.probe:
        compiled=twice(EXPORTS); result={"status":"PASS_B025_BACKEND_READ_ONLY_TWO_EXACT_REPLAYS","candidate_manifest":raw_identity(compiled["manifest_raw"]),"record_count":compiled["manifest"]["record_count"],"new_b025_record_count":compiled["manifest"]["new_b025_record_count"],"payload_inventory_sha256":compiled["inventory_sha256"],"writes_performed":False}
    elif args.admit: result=admit()
    else: result=verify(write_receipt=False)
    print(json.dumps(result,ensure_ascii=False,sort_keys=True)); return 0


if __name__=="__main__":
    try: raise SystemExit(main())
    except StageGateError as exc: raise SystemExit(f"REFUSED: {exc}")
