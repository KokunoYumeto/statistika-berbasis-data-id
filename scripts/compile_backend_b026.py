#!/usr/bin/env python3
"""Compile or atomically admit the deterministic R011-B026 backend delta.

The compiler extends the exact admitted B025 backend.  ``--self-test`` is
read-only and validates all finished pre-build inputs.  ``--probe`` requires
the exact post-build binding and compiles twice without writes.  ``--admit``
preserves exact B025 preimages, advances every backend payload atomically, and
immediately replays it.  No mode uses Git, credentials, network, controls,
output, release files, or upstream contact.
"""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import io
import json
import os
import re
import shutil
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

import jsonschema

import admit_backend_b024 as serializers
from b026_pipeline_contract import (
    ASSET_CLOSURE_PATH,
    BACKEND_ADMISSION_RECEIPT_PATH,
    BACKEND_REPLAY_RECEIPT_PATH,
    BASE_ADMISSION,
    BASE_BACKEND,
    BASE_REPLAY,
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
    repo_path,
    verify_record,
    verify_text_inputs,
)


ROOT = Path(__file__).resolve().parents[1]
EXPORTS = ROOT / "backend/exports"
PREIMAGES = ROOT / "qa/b026-backend-admission/preimages-R011-B026"
PREIMAGE_MANIFEST = PREIMAGES / "PREIMAGE_MANIFEST.json"
RECORDED_AT = "2026-08-30T12:00:00+02:00"
WORKFLOW = "r011-openintro-statistics-id-b026-backend-admission"
SCHEMA_VERSION = "0.1.0"
AUTHORITY = "authority/upstream/openintro-statistics-fee25091fb24e89c36296fd67c48c1fcf7a93b6e"
BASE_RECORD_COUNT = 9_119
BASE_RECORD_COUNTS = {
    "artifacts": 791,
    "assets": 422,
    "concepts": 277,
    "corrections": 190,
    "courses": 1,
    "editions": 1,
    "localizations": 717,
    "programs": 1,
    "qa_events": 347,
    "relations": 4_538,
    "resources": 1,
    "rights": 53,
    "segments": 717,
    "terms": 310,
    "units": 753,
}
RECORD_PATHS = copy.deepcopy(serializers.RECORD_PATHS)
REQUIRED_VIEWS = list(serializers.REQUIRED_VIEWS)
GENERATED = set(RECORD_PATHS.values()) | set(REQUIRED_VIEWS) | {"identity_map.jsonl"}
BACKEND_TOOL_PATHS = {
    "backend_pipeline_contract": "scripts/b026_pipeline_contract.py",
    "backend_compiler": "scripts/compile_backend_b026.py",
    "backend_admitter": "scripts/admit_backend_b026.py",
    "backend_postbuild_binder": "scripts/bind_b026_postbuild.py",
}

SOURCE_MAIN = {
    "path": f"{AUTHORITY}/ch_inference_for_means/TeX/ch_inference_for_means.tex",
    "bytes": 141_389,
    "sha256": "d818b24b8e8d0582f8e603972e87764082d8470d91ddcbeaa794c295a1d37bec",
}
SOURCE_EXERCISES = {
    "path": f"{AUTHORITY}/ch_inference_for_means/TeX/one-sample_means_with_the_t-distribution.tex",
    "bytes": 10_225,
    "sha256": "5d41cfe653f9da3e3b78885c23b3b2d30cd698a11087424fca1abc104de451ae",
}
SOURCE_ANSWERS = {
    "path": f"{AUTHORITY}/extraTeX/eoceSolutions/eoceSolutions.tex",
    "bytes": 106_045,
    "sha256": "6c4e01376db4c023cc7b3f9949490e57220ef1cb831c580da71efde6ce723268",
}
SOURCE_LICENSE = {
    "path": f"{AUTHORITY}/LICENSE.md",
    "bytes": 2_612,
    "sha256": "9bd77ff3e58e0b7f1331824b8195d4cf588851a6461cc3230d12410da7935223",
}

MAIN_RANGES = [
    ("a", 1, 231, "main_translation_a", 1, 231, "Chapter opening through initial condition checks", "Pembukaan bab hingga pemeriksaan syarat awal"),
    ("b", 232, 400, "main_translation_b", 1, 169, "Population sanity check and CLT closure", "Pemeriksaan kewajaran populasi dan penutup TLT"),
    ("c", 401, 633, "main_translation_c", 1, 233, "The t distribution and tail tools", "Distribusi t dan perangkat luas ekor"),
    ("d", 634, 796, "main_translation_d", 1, 163, "One-sample t confidence intervals", "Interval kepercayaan t satu sampel"),
    ("e", 797, 896, "main_translation_e", 1, 100, "Guided confidence-interval sequence", "Rangkaian interval kepercayaan terpandu"),
    ("f", 897, 1052, "main_translation_f", 1, 156, "One-sample t test and section summary", "Uji t satu sampel dan ringkasan bagian"),
]

EXERCISES = {
    1: (1, 20, "Identify the critical t", "Tentukan t kritis"),
    2: (21, 35, "t-distribution", "Distribusi t"),
    3: (36, 53, "Find the p-value, Part I", "Tentukan nilai-p, Bagian I"),
    4: (54, 69, "Find the p-value, Part II", "Tentukan nilai-p, Bagian II"),
    5: (70, 79, "Working backwards, Part I", "Menelusuri balik, Bagian I"),
    6: (80, 91, "Working backwards, Part II", "Menelusuri balik, Bagian II"),
    7: (92, 125, "Sleep habits of New Yorkers", "Kebiasaan tidur warga New York"),
    8: (126, 172, "Heights of adults", "Tinggi badan orang dewasa"),
    9: (173, 188, "Find the mean", "Tentukan rata-rata"),
    10: (189, 195, "t-star versus z-star", "t-bintang versus z-bintang"),
    11: (196, 217, "Play the piano", "Bermain piano"),
    12: (218, 248, "Auto exhaust and lead exposure", "Gas buang kendaraan dan paparan timbal"),
    13: (249, 260, "Car insurance savings", "Penghematan asuransi mobil"),
    14: (261, 280, "SAT scores", "Skor SAT"),
}

ANSWER_RANGES = {
    1: (1636, 1644),
    3: (1645, 1651),
    5: (1652, 1657),
    7: (1658, 1677),
    9: (1683, 1691),
    11: (1692, 1715),
    13: (1716, 1721),
}
ANSWER_LAYOUT_RANGES = [("opening", 1623, 1635), ("page-transition", 1678, 1682)]

TERM_SPECS = [
    ("one-sample mean", "rata-rata satu sampel", "one-sample-mean", []),
    ("t-distribution", "distribusi t", "t-distribution", ["distribusi-$t$"]),
    ("degrees of freedom", "derajat kebebasan", "degrees-of-freedom", ["dk"]),
    ("standard error", "galat baku", "standard-error", ["SE"]),
    ("point estimate", "estimasi titik", "point-estimate", []),
    ("confidence interval", "interval kepercayaan", "confidence-interval", []),
    ("margin of error", "margin galat", "margin-of-error", ["ME"]),
    ("t statistic", "statistik t", "t-statistic", ["statistik-$t$"]),
    ("p-value", "nilai-p", "p-value", ["nilai-$p$"]),
    ("null hypothesis", "hipotesis nol", "null-hypothesis", ["H0"]),
    ("alternative hypothesis", "hipotesis alternatif", "alternative-hypothesis", ["HA"]),
    ("independent observations", "pengamatan independen", "independent-observations", []),
    ("nearly normal condition", "syarat hampir normal", "nearly-normal-condition", []),
    ("Central Limit Theorem", "Teorema Limit Pusat", "central-limit-theorem", ["TLT"]),
]

# Section 7.1 applies descriptive-statistics, distribution, and general
# inference concepts admitted at earlier boundaries.  These exact stable keys
# make the unit independently selectable without hiding its prerequisite
# closure in prose.
PREREQUISITE_KEYS = (
    "r011/concept/sample-mean",
    "r011/concept/standard-deviation",
    "r011/concept/b014/normal-curve",
    "r011/concept/b019/standard-error",
    "r011/concept/b019/central-limit-theorem",
    "r011/concept/point-estimate",
    "r011/concept/b020/confidence-interval",
    "r011/concept/b020/margin-of-error",
    "r011/concept/null-hypothesis",
    "r011/concept/alternative-hypothesis",
    "r011/concept/b021/p-value",
)

# B026 records the terms in their Section 7.1 context while explicitly linking
# semantically identical locale-neutral concepts already present in the corpus.
EQUIVALENT_CONCEPT_KEYS = {
    "degrees-of-freedom": "r011/concept/b024/degrees-of-freedom",
    "standard-error": "r011/concept/b019/standard-error",
    "point-estimate": "r011/concept/point-estimate",
    "confidence-interval": "r011/concept/b020/confidence-interval",
    "margin-of-error": "r011/concept/b020/margin-of-error",
    "p-value": "r011/concept/b021/p-value",
    "null-hypothesis": "r011/concept/null-hypothesis",
    "alternative-hypothesis": "r011/concept/alternative-hypothesis",
    "central-limit-theorem": "r011/concept/b019/central-limit-theorem",
}

ASSET_SLUGS = {
    "outliers_and_ss_condition": "outliers-and-ss-condition",
    "tDistCompareToNormalDist": "t-dist-compare-normal",
    "tDistConvergeToNormalDist": "t-dist-converge-normal",
    "tDistDF18LeftTail2Point10": "t-dist-df18-left-tail-2-10",
    "tDistDF20RightTail1Point65": "t-dist-df20-right-tail-1-65",
    "run17SampTimeHistogram": "run17-sample-time-histogram",
    "t_distribution": "exercise-t-distribution",
    "adult_heights_hist": "adult-heights-histogram",
}


def raw_identity(raw: bytes) -> dict[str, Any]:
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def require(path: str, expected: dict[str, Any] | None = None) -> bytes:
    file = repo_path(path)
    raw = file.read_bytes()
    if expected and raw_identity(raw) != {key: expected[key] for key in ("bytes", "sha256")}:
        raise StageGateError(f"exact input changed: {path}")
    return raw


def load_base(base_root: Path) -> tuple[dict[str, list[dict]], dict]:
    manifest_raw = (base_root / "manifest.json").read_bytes()
    if raw_identity(manifest_raw) != {key: BASE_BACKEND[key] for key in ("bytes", "sha256")}:
        raise StageGateError("backend is not the exact B025 preimage")
    manifest = json.loads(manifest_raw)
    if (
        manifest.get("boundary_id") != "R011-B025"
        or manifest.get("record_count") != BASE_RECORD_COUNT
        or manifest.get("record_counts") != BASE_RECORD_COUNTS
    ):
        raise StageGateError("B025 base manifest semantics changed")
    files = {row["path"]: row for row in manifest["files"]}
    records: dict[str, list[dict]] = {}
    for table, relative in RECORD_PATHS.items():
        raw = (base_root / relative).read_bytes()
        row = files[relative]
        if raw_identity(raw) != {key: row[key] for key in ("bytes", "sha256")}:
            raise StageGateError(f"B025 base record changed: {relative}")
        records[table] = serializers.load_jsonl(raw)
        if serializers.jsonl_bytes(records[table]) != raw:
            raise StageGateError(f"noncanonical B025 record table: {relative}")
    return records, manifest


def load_binding_against_frozen_preimage() -> dict[str, Any]:
    """Validate the binding while replaying after live backend promotion."""
    if not POST_BUILD_ROLES:
        raise StageGateError("B026 post-build role contract is not registered")
    try:
        payload = json.loads(BINDINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StageGateError("post-build binding is absent or invalid during replay") from exc
    if payload.get("boundary_id") != BOUNDARY_ID or payload.get("status") != "PASS_EXACT_B026_POST_BUILD_IDENTITIES_BOUND":
        raise StageGateError("post-build binding boundary/status changed during replay")
    sealed = {"base_backend": {key: BASE_BACKEND[key] for key in ("path", "bytes", "sha256")}}
    sealed.update({role: verify_record(role, spec) for role, spec in SEALED_TEXT_INPUTS.items()})
    if payload.get("sealed_text_inputs") != sealed:
        raise StageGateError("post-build binding sealed text inputs changed during replay")
    asset = load_asset_closure(require_complete=True)
    if payload.get("asset_closure") != asset:
        raise StageGateError("post-build binding asset closure changed during replay")
    outputs = payload.get("post_build_outputs")
    if not isinstance(outputs, dict) or set(outputs) != set(POST_BUILD_ROLES):
        raise StageGateError("post-build output roles changed during replay")
    for role, spec in POST_BUILD_ROLES.items():
        observed = verify_record(role, spec)
        observed_identity = {key: observed[key] for key in ("path", "bytes", "sha256")}
        exact = {key: spec[key] for key in ("path", "bytes", "sha256")}
        if observed_identity != exact:
            raise StageGateError(f"registered post-build identity changed during replay: {role}")
        if observed_identity != {key: outputs[role][key] for key in ("path", "bytes", "sha256")}:
            raise StageGateError(f"post-build output changed during replay: {role}")
        required = spec.get("required_status")
        if required is not None:
            if outputs[role].get("required_status") != required:
                raise StageGateError(f"post-build status binding changed during replay: {role}")
            receipt_payload = json.loads(repo_path(spec["path"]).read_text(encoding="utf-8"))
            if receipt_payload.get("boundary_id") != BOUNDARY_ID or receipt_payload.get("status") != required:
                raise StageGateError(f"post-build receipt status changed during replay: {role}")
    pages = outputs["candidate_pdf"].get("pages")
    if not isinstance(pages, int) or pages <= 260:
        raise StageGateError("bound B026 reader does not extend B025")
    root_status = outputs["root_visual_qa"].get("required_status")
    if root_status != POST_BUILD_ROLES["root_visual_qa"].get("required_status") or not re.fullmatch(
        rf"PASS_ALL_{pages}_PAGES_VISUALLY_INSPECTED(?:_IN_ORDER)?_ZERO_DEFECTS", str(root_status)
    ):
        raise StageGateError("bound B026 root visual status is not page-count exact")
    return payload


def index(records: dict[str, list[dict]]) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    for table in records.values():
        for row in table:
            if row["stable_key"] in rows:
                raise StageGateError("duplicate stable key in base")
            rows[row["stable_key"]] = row
    return rows


def record(record_type: str, key: str, **fields: Any) -> dict:
    row = {
        "$schema": "schemas/backend-record-v0.1.0.schema.json",
        "schema_version": SCHEMA_VERSION,
        "record_type": record_type,
        "id": serializers.stable_id(key),
        "stable_key": key,
        "status": "active",
        "recorded_at": RECORDED_AT,
        "workflow_id": WORKFLOW,
        "boundary_id": BOUNDARY_ID,
        "supersedes_id": None,
    }
    row.update(fields)
    return serializers.normalize(row)


def common(idx: dict[str, dict], rights: list[str], **fields: Any) -> dict:
    row = {
        "resource_id": idx["r011/resource/openintro-statistics"]["id"],
        "edition_id": idx["r011/edition/fee25091"]["id"],
        "source_local_ids": [BOUNDARY_ID],
        "parent_id": None,
        "order": 0,
        "source_path": None,
        "source_span": None,
        "source_sha256": None,
        "locale": "zxx",
        "translation_state": "visually_checked",
        "rights_component_ids": rights,
    }
    row.update(fields)
    return row


def add(records: dict[str, list[dict]], idx: dict[str, dict], table: str, row: dict) -> dict:
    if row["stable_key"] in idx:
        raise StageGateError(f"B026 stable key collision: {row['stable_key']}")
    records[table].append(row)
    idx[row["stable_key"]] = row
    return row


def span(raw: bytes, first: int, last: int) -> tuple[dict, bytes]:
    return serializers.line_span(raw, first, last)


def validate_serializations(
    records: dict[str, list[dict]],
    payloads: dict[str, bytes],
    view_counts: dict[str, int],
    all_row_count: int,
) -> None:
    """Parse and replay every generated JSONL/CSV interoperability surface."""
    for table, relative in RECORD_PATHS.items():
        raw = payloads[relative]
        parsed = serializers.load_jsonl(raw)
        expected_rows = sorted(records[table], key=lambda item: item["id"])
        if parsed != expected_rows or serializers.jsonl_bytes(parsed) != raw:
            raise StageGateError(f"generated JSONL is not an exact canonical replay: {relative}")
    for relative in REQUIRED_VIEWS:
        raw = payloads[relative]
        try:
            text = raw.decode("utf-8")
            reader = csv.DictReader(io.StringIO(text, newline=""))
            rows = list(reader)
        except (UnicodeDecodeError, csv.Error) as exc:
            raise StageGateError(f"generated CSV is not valid UTF-8 CSV: {relative}") from exc
        if not reader.fieldnames or len(rows) != view_counts[relative]:
            raise StageGateError(f"generated CSV row count/header changed: {relative}")
        if any(None in row for row in rows):
            raise StageGateError(f"generated CSV contains overflow columns: {relative}")
    identity_raw = payloads["identity_map.jsonl"]
    identity_rows = serializers.load_jsonl(identity_raw)
    if len(identity_rows) != all_row_count or serializers.jsonl_bytes(identity_rows) != identity_raw:
        raise StageGateError("generated identity-map JSONL is not an exact canonical replay")


def evidence(binding: dict, base_root: Path) -> tuple[dict[str, bytes], dict[str, dict]]:
    specs: dict[str, dict] = {}
    for role, row in binding["sealed_text_inputs"].items():
        if role != "base_backend":
            specs[role] = row
    specs["post_build_binding"] = identity(BINDINGS_PATH)
    asset = binding["asset_closure"]
    specs["asset_closure"] = asset["receipt"]
    specs["asset_visual_montage"] = asset["visual_montage"]
    specs["asset_localizer"] = asset["localizer"]
    specs["dolphin_source"] = asset["dolphin_reuse"]
    specs["dolphin_rights_witness"] = asset["dolphin_rights_witness"]
    for row in asset["artifacts"]:
        slug = ASSET_SLUGS[row["key"]]
        specs[f"asset_source_{slug}"] = row["source"]
        specs[f"asset_producer_{slug}"] = row["producer"]
        specs[f"asset_localized_{slug}"] = row["output"]
    specs.update(binding["post_build_outputs"])
    specs.update({
        "base_b025_admission": BASE_ADMISSION,
        "base_b025_replay": BASE_REPLAY,
        "source_main": SOURCE_MAIN,
        "source_exercises": SOURCE_EXERCISES,
        "source_answers": SOURCE_ANSWERS,
        "source_license": SOURCE_LICENSE,
    })
    for role, path in BACKEND_TOOL_PATHS.items():
        specs[role] = identity(repo_path(path))
    payloads: dict[str, bytes] = {}
    meta: dict[str, dict] = {}
    base_raw = (base_root / "manifest.json").read_bytes()
    if raw_identity(base_raw) != {key: BASE_BACKEND[key] for key in ("bytes", "sha256")}:
        raise StageGateError("exact B025 manifest preimage changed")
    destination = "evidence/b026/base_b025_manifest--manifest.json"
    payloads[destination] = base_raw
    meta["base_b025_manifest"] = {**BASE_BACKEND, "destination": destination}
    for role, row in sorted(specs.items()):
        raw = require(row["path"], row)
        destination = f"evidence/b026/{role}--{Path(row['path']).name}"
        if destination in payloads:
            raise StageGateError(f"duplicate evidence destination: {destination}")
        payloads[destination] = raw
        meta[role] = {**row, "destination": destination}
    return payloads, meta


def compile(base_root: Path) -> dict[str, Any]:
    binding = load_bindings(require_complete=True) if base_root.resolve() == EXPORTS.resolve() else load_binding_against_frozen_preimage()
    records, base_manifest = load_base(base_root)
    base_rows = {table: [canonical(row) for row in rows] for table, rows in records.items()}
    idx = index(records)
    evidence_payloads, ev = evidence(binding, base_root)
    upstream_right = idx["r011/rights/upstream-cc-by-sa-3.0"]["id"]
    book = idx["r011/unit/book"]

    derivative_right = add(records, idx, "rights", record(
        "rights",
        "r011/rights/b026-id-derivative-cc-by-sa-3.0",
        **common(
            idx,
            [],
            parent_id=idx["r011/resource/openintro-statistics"]["id"],
            order=54,
            source_path=ev["source_blueprint"]["path"],
            source_sha256=ev["source_blueprint"]["sha256"],
            locale="zxx",
            license_expression="CC-BY-SA-3.0",
            license_url="https://creativecommons.org/licenses/by-sa/3.0/",
            component_scope="B026 Indonesian Chapter 7 opening and Section 7.1; exercises 1-14; public odd answers 1-13; eight localized/corrected generated figures and their producers.",
            attribution="OpenIntro Statistics, Fourth Edition; David M Diez, Mine Çetinkaya-Rundel, Christopher D Barr; Indonesian derivative identified as R011-B026.",
            change_notice="Learner prose, captions, alt text, labels, and eight generated figures were localized; sixteen high-confidence source corrections were applied without changing authority bytes.",
            share_alike_required=True,
            non_endorsement="No OpenIntro, author, institution, photographer, data-provider, package, brand, or tool-provider endorsement implied.",
            publication_effect="Include source attribution, derivative notice, share-alike license, novel title, and no OpenIntro branding/logo.",
            verification_status="exact source/text/asset/producer/build/language/visual closure bound",
        ),
    ))
    dolphin_right = add(records, idx, "rights", record(
        "rights",
        "r011/rights/b026-rissos-dolphin-photo-cc-by-2-0",
        **common(
            idx,
            [],
            parent_id=idx["r011/resource/openintro-statistics"]["id"],
            order=55,
            source_path=ev["dolphin_rights_witness"]["path"],
            source_sha256=ev["dolphin_rights_witness"]["sha256"],
            locale="zxx",
            license_expression="CC-BY-2.0",
            license_url="https://creativecommons.org/licenses/by/2.0/",
            component_scope="Byte-identical Risso's dolphin photograph used in Chapter 7 Section 7.1.",
            attribution=binding["asset_closure"]["dolphin_attribution"],
            change_notice="Photograph bytes are unchanged; surrounding Indonesian alt text and caption are derivative text.",
            non_endorsement="No photographer or source-site endorsement implied.",
            publication_effect="Retain Mike Baird attribution, source URL, and CC BY 2.0 license notice.",
            verification_status="exact photograph and rights-witness bytes verified",
        ),
    ))
    text_rights = [upstream_right, derivative_right["id"]]

    source_main = require(SOURCE_MAIN["path"], SOURCE_MAIN)
    source_exercises = require(SOURCE_EXERCISES["path"], SOURCE_EXERCISES)
    source_answers = require(SOURCE_ANSWERS["path"], SOURCE_ANSWERS)
    chapter_span, chapter_raw = span(source_main, 1, 1052)
    section_span, section_raw = span(source_main, 29, 1052)
    preceding = idx["r011/unit/source-label/twoWayTablesAndChiSquare"]
    prerequisites = [idx[key] for key in PREREQUISITE_KEYS]
    chapter = add(records, idx, "units", record(
        "unit",
        "r011/unit/source-label/ch_inference_for_means",
        **common(
            idx,
            text_rights,
            source_local_ids=[BOUNDARY_ID, "ch_inference_for_means", "chapter-7"],
            parent_id=book["id"],
            order=10,
            source_path="ch_inference_for_means/TeX/ch_inference_for_means.tex",
            source_span=chapter_span,
            source_sha256=hashlib.sha256(chapter_raw).hexdigest(),
            locale="en",
            unit_type="chapter",
            title="Inference for numerical data",
            target_title="Inferensi untuk data numerik",
            admitted_source_scope="lines 1-1052; later Chapter 7 sections remain outside B026",
        ),
    ))
    section = add(records, idx, "units", record(
        "unit",
        "r011/unit/source-label/oneSampleMeansWithTDistribution",
        **common(
            idx,
            text_rights,
            source_local_ids=[BOUNDARY_ID, "oneSampleMeansWithTDistribution", "7.1"],
            parent_id=chapter["id"],
            order=1,
            source_path="ch_inference_for_means/TeX/ch_inference_for_means.tex",
            source_span=section_span,
            source_sha256=hashlib.sha256(section_raw).hexdigest(),
            locale="en",
            unit_type="section",
            title="One-sample means with the t-distribution",
            target_title="Rata-rata satu sampel dengan distribusi t",
            prerequisite_ids=[row["id"] for row in prerequisites],
        ),
    ))

    pairs: list[tuple[dict, dict, dict]] = []
    main_units: list[dict] = []
    for order, (slug, first, last, target_role, tfirst, tlast, title, target_title) in enumerate(MAIN_RANGES, 1):
        source_span, source_raw = span(source_main, first, last)
        target_file = require(ev[target_role]["path"], ev[target_role])
        target_span, target_raw = span(target_file, tfirst, tlast)
        parent = chapter if slug == "a" else section
        unit = add(records, idx, "units", record(
            "unit",
            f"r011/unit/b026/main-range-{slug}",
            **common(
                idx,
                text_rights,
                parent_id=parent["id"],
                order=order,
                source_path="ch_inference_for_means/TeX/ch_inference_for_means.tex",
                source_span=source_span,
                source_sha256=hashlib.sha256(source_raw).hexdigest(),
                locale="en",
                unit_type="translation_range",
                title=title,
                target_title=target_title,
            ),
        ))
        segment = add(records, idx, "segments", record(
            "segment",
            f"r011/segment/b026/main-range-{slug}",
            **common(
                idx,
                text_rights,
                parent_id=unit["id"],
                unit_id=unit["id"],
                order=1,
                source_path=unit["source_path"],
                source_span=source_span,
                source_sha256=hashlib.sha256(source_raw).hexdigest(),
                locale="en",
                source_text=source_raw.decode("utf-8"),
                protected_tokens=[],
                translation_state="source_frozen",
            ),
        ))
        localization = add(records, idx, "localizations", record(
            "localization",
            f"r011/localization/id-ID/b026/main-range-{slug}",
            **common(
                idx,
                text_rights,
                parent_id=segment["id"],
                unit_id=unit["id"],
                order=1,
                source_path=ev[target_role]["path"],
                source_span=target_span,
                source_sha256=hashlib.sha256(target_raw).hexdigest(),
                locale="id-ID",
                source_locale="en",
                target_locale="id-ID",
                source_segment_id=segment["id"],
                target_text=target_raw.decode("utf-8"),
                translation_provenance=MODEL,
            ),
        ))
        main_units.append(unit)
        pairs.append((unit, segment, localization))

    target_exercises = require(ev["exercise_translation"]["path"], ev["exercise_translation"])
    exercises: dict[int, dict] = {}
    answers: dict[int, dict] = {}
    gaps: dict[int, dict] = {}
    for number, (first, last, title, target_title) in EXERCISES.items():
        source_span, source_raw = span(source_exercises, first, last)
        target_span, target_raw = span(target_exercises, first, last)
        unit = add(records, idx, "units", record(
            "unit",
            f"r011/unit/b026/exercise-{number}",
            **common(
                idx,
                text_rights,
                parent_id=section["id"],
                order=100 + number,
                source_path="ch_inference_for_means/TeX/one-sample_means_with_the_t-distribution.tex",
                source_span=source_span,
                source_sha256=hashlib.sha256(source_raw).hexdigest(),
                locale="en",
                unit_type="exercise",
                exercise_id=number,
                title=f"Exercise 7.{number}: {title}",
                target_title=f"Latihan 7.{number}: {target_title}",
            ),
        ))
        exercises[number] = unit
        segment = add(records, idx, "segments", record(
            "segment",
            f"r011/segment/b026/exercise-{number}",
            **common(idx, text_rights, parent_id=unit["id"], unit_id=unit["id"], order=1, source_path=unit["source_path"], source_span=source_span, source_sha256=hashlib.sha256(source_raw).hexdigest(), locale="en", source_text=source_raw.decode("utf-8"), protected_tokens=[], translation_state="source_frozen"),
        ))
        localization = add(records, idx, "localizations", record(
            "localization",
            f"r011/localization/id-ID/b026/exercise-{number}",
            **common(idx, text_rights, parent_id=segment["id"], unit_id=unit["id"], order=1, source_path=ev["exercise_translation"]["path"], source_span=target_span, source_sha256=hashlib.sha256(target_raw).hexdigest(), locale="id-ID", source_locale="en", target_locale="id-ID", source_segment_id=segment["id"], target_text=target_raw.decode("utf-8"), translation_provenance=MODEL),
        ))
        pairs.append((unit, segment, localization))
        if number % 2 == 0:
            gaps[number] = add(records, idx, "units", record(
                "unit",
                f"r011/unit/o001-gap/7.{number}",
                **common(
                    idx,
                    text_rights,
                    parent_id=unit["id"],
                    order=1,
                    source_path=ev["o001_gap_ledger"]["path"],
                    source_sha256=ev["o001_gap_ledger"]["sha256"],
                    locale="id-ID",
                    unit_type="mastery_companion_gap",
                    exercise_id=number,
                    title=f"O001 public-answer gap for exercise 7.{number}",
                    target_title=f"Kesenjangan jawaban publik O001 untuk latihan 7.{number}",
                    translation_state="queued",
                    answer_availability="no_public_answer_upstream",
                    authoring_mode="independent_original_required",
                    restricted_solution_accessed=False,
                ),
            ))

    target_answers = require(ev["public_answer_translation"]["path"], ev["public_answer_translation"])
    for layout_order, (layout_slug, first, last) in enumerate(ANSWER_LAYOUT_RANGES, 1):
        source_span, source_raw = span(source_answers, first, last)
        target_first, target_last = first - 1622, last - 1622
        target_span, target_raw = span(target_answers, target_first, target_last)
        unit = add(records, idx, "units", record(
            "unit",
            f"r011/unit/b026/public-answer-layout-{layout_slug}",
            **common(idx, text_rights, parent_id=section["id"], order=200 + layout_order, source_path="extraTeX/eoceSolutions/eoceSolutions.tex", source_span=source_span, source_sha256=hashlib.sha256(source_raw).hexdigest(), locale="en", unit_type="answer_layout", title=f"Chapter 7 public-answer layout: {layout_slug}", target_title=f"Tata letak jawaban publik Bab 7: {layout_slug}"),
        ))
        segment = add(records, idx, "segments", record(
            "segment",
            f"r011/segment/b026/public-answer-layout-{layout_slug}",
            **common(idx, text_rights, parent_id=unit["id"], unit_id=unit["id"], order=1, source_path=unit["source_path"], source_span=source_span, source_sha256=hashlib.sha256(source_raw).hexdigest(), locale="en", source_text=source_raw.decode("utf-8"), protected_tokens=[], translation_state="source_frozen"),
        ))
        localization = add(records, idx, "localizations", record(
            "localization",
            f"r011/localization/id-ID/b026/public-answer-layout-{layout_slug}",
            **common(idx, text_rights, parent_id=segment["id"], unit_id=unit["id"], order=1, source_path=ev["public_answer_translation"]["path"], source_span=target_span, source_sha256=hashlib.sha256(target_raw).hexdigest(), locale="id-ID", source_locale="en", target_locale="id-ID", source_segment_id=segment["id"], target_text=target_raw.decode("utf-8"), translation_provenance=MODEL),
        ))
        pairs.append((unit, segment, localization))

    for number, (first, last) in ANSWER_RANGES.items():
        source_span, source_raw = span(source_answers, first, last)
        target_first, target_last = first - 1622, last - 1622
        target_span, target_raw = span(target_answers, target_first, target_last)
        unit = add(records, idx, "units", record(
            "unit",
            f"r011/unit/b026/public-answer-{number}",
            **common(idx, text_rights, parent_id=exercises[number]["id"], order=number, source_path="extraTeX/eoceSolutions/eoceSolutions.tex", source_span=source_span, source_sha256=hashlib.sha256(source_raw).hexdigest(), locale="en", unit_type="public_answer", exercise_id=number, title=f"Public answer 7.{number}", target_title=f"Jawaban publik 7.{number}"),
        ))
        answers[number] = unit
        segment = add(records, idx, "segments", record(
            "segment",
            f"r011/segment/b026/public-answer-{number}",
            **common(idx, text_rights, parent_id=unit["id"], unit_id=unit["id"], order=1, source_path=unit["source_path"], source_span=source_span, source_sha256=hashlib.sha256(source_raw).hexdigest(), locale="en", source_text=source_raw.decode("utf-8"), protected_tokens=[], translation_state="source_frozen"),
        ))
        localization = add(records, idx, "localizations", record(
            "localization",
            f"r011/localization/id-ID/b026/public-answer-{number}",
            **common(idx, text_rights, parent_id=segment["id"], unit_id=unit["id"], order=1, source_path=ev["public_answer_translation"]["path"], source_span=target_span, source_sha256=hashlib.sha256(target_raw).hexdigest(), locale="id-ID", source_locale="en", target_locale="id-ID", source_segment_id=segment["id"], target_text=target_raw.decode("utf-8"), translation_provenance=MODEL),
        ))
        pairs.append((unit, segment, localization))

    terms: list[tuple[dict, dict]] = []
    for order, (source_term, target_term, slug, variants) in enumerate(TERM_SPECS, 311):
        concept = add(records, idx, "concepts", record(
            "concept",
            f"r011/concept/b026/{slug}",
            **common(idx, text_rights, parent_id=section["id"], order=order, source_path="ch_inference_for_means/TeX/ch_inference_for_means.tex", source_span=section_span, source_sha256=hashlib.sha256(section_raw).hexdigest(), locale="zxx", name=source_term, concept_kind="statistical_concept"),
        ))
        term = add(records, idx, "terms", record(
            "term",
            f"r011/term/id-ID/b026/{order:04d}",
            **common(idx, text_rights, parent_id=concept["id"], order=order, source_path=ev["text_checkpoint"]["path"], source_sha256=ev["text_checkpoint"]["sha256"], locale="id-ID", concept_id=concept["id"], source_term=source_term, target_term=target_term, variants=variants, register="academic", decision="admit exact B026 controlled term", evidence="Complete B026 text checkpoint and deterministic translation QA.", translation_state="language_reviewed"),
        ))
        terms.append((concept, term))

    source_assets: dict[str, dict] = {}
    producers: dict[str, dict] = {}
    localized_assets: dict[str, dict] = {}
    asset_rows = {row["key"]: row for row in binding["asset_closure"]["artifacts"]}
    for order, key in enumerate(ASSET_SLUGS, 1):
        row = asset_rows[key]
        slug = ASSET_SLUGS[key]
        source = row["source"]
        producer = row["producer"]
        output = row["output"]
        source_assets[key] = add(records, idx, "assets", record(
            "asset",
            f"r011/asset/b026/source/{slug}",
            **common(idx, [upstream_right], parent_id=section["id"], order=order, source_path=source["path"].split(f"{AUTHORITY}/", 1)[-1], source_sha256=source["sha256"], locale="en", asset_kind="generated_vector_figure_source", media_type="application/pdf", bytes=source["bytes"], sha256=source["sha256"], localized=False, content_localization_required=True, translation_state="source_frozen"),
        ))
        producers[key] = add(records, idx, "assets", record(
            "asset",
            f"r011/asset/b026/producer/{slug}",
            **common(idx, [upstream_right], parent_id=source_assets[key]["id"], order=1, source_path=producer["path"].split(f"{AUTHORITY}/", 1)[-1], source_sha256=producer["sha256"], locale="zxx", asset_kind="r_figure_producer", media_type="text/x-r-source", bytes=producer["bytes"], sha256=producer["sha256"], translated=False, runtime_data_dependencies="openintro package plotting helpers or named runtime objects as frozen in the B026 blueprint", translation_state="source_frozen"),
        ))
        localized_assets[key] = add(records, idx, "assets", record(
            "asset",
            f"r011/asset/b026/figure/{slug}-id",
            **common(idx, text_rights, parent_id=source_assets[key]["id"], order=2, source_path=source_assets[key]["source_path"], source_sha256=source["sha256"], locale="id-ID", asset_kind="localized_or_corrected_vector_figure", media_type="application/pdf", bytes=output["bytes"], sha256=output["sha256"], target_path=output["path"], target_sha256=output["sha256"], localized=True, localization_method=row["method"], semantic_correction=row.get("correction"), reader_visible_strings=row.get("required_localized_strings", []), removed_reader_visible_strings=row.get("removed_reader_visible_english_strings", []), translation_provenance=MODEL),
        ))

    dolphin_source = binding["asset_closure"]["dolphin_reuse"]
    dolphin = add(records, idx, "assets", record(
        "asset",
        "r011/asset/b026/figure/rissos-dolphin-byte-identical",
        **common(idx, [dolphin_right["id"]], parent_id=section["id"], order=9, source_path=dolphin_source["path"].split(f"{AUTHORITY}/", 1)[-1], source_sha256=dolphin_source["sha256"], locale="zxx", asset_kind="third_party_photo_byte_identical", media_type="image/jpeg", bytes=dolphin_source["bytes"], sha256=dolphin_source["sha256"], localized=False, content_localization_required=False, attribution=binding["asset_closure"]["dolphin_attribution"], translation_state="source_frozen"),
    ))
    witness = binding["asset_closure"]["dolphin_rights_witness"]
    dolphin_witness = add(records, idx, "assets", record(
        "asset",
        "r011/asset/b026/rights-witness/rissos-dolphin",
        **common(idx, [dolphin_right["id"]], parent_id=dolphin["id"], order=1, source_path=witness["path"].split(f"{AUTHORITY}/", 1)[-1], source_sha256=witness["sha256"], locale="en", asset_kind="rights_attribution_witness", media_type="text/plain", bytes=witness["bytes"], sha256=witness["sha256"], translated=False, translation_state="source_frozen"),
    ))
    runtime_dependencies: dict[str, dict] = {}
    for order, (slug, objects, usage) in enumerate((
        ("openintro-col", ["COL"], "palette and plotting helpers used by generated figures"),
        ("openintro-run-samples", ["run10Samp", "run17"], "deterministic run17 sample-time histogram producer; sibling run10 output excluded"),
        ("openintro-bdims", ["bdims"], "adult-height exercise histogram producer"),
    ), 1):
        runtime_dependencies[slug] = add(records, idx, "assets", record(
            "asset",
            f"r011/asset/b026/runtime-data/{slug}",
            **common(
                idx,
                [upstream_right],
                parent_id=section["id"],
                order=order,
                locale="zxx",
                asset_kind="runtime_package_object_reference",
                media_type="application/x-r-data-object-reference",
                package="openintro",
                objects=objects,
                usage=usage,
                standalone_file_in_boundary=False,
                publication_disposition="provenance reference only; no standalone package-data bytes bundled",
                translation_state="source_frozen",
            ),
        ))

    blueprint = json.loads(require(ev["source_blueprint"]["path"], ev["source_blueprint"]))
    correction_rows: list[dict] = []
    for order, candidate in enumerate(blueprint["correction_candidates"], 1):
        location = candidate["location"]
        relative = location.split(":", 1)[0]
        match = re.search(r":(\d+)(?:-(\d+))?", location)
        if match is None:
            raise StageGateError(f"correction location lacks line span: {location}")
        first = int(match.group(1))
        last = int(match.group(2) or first)
        raw = require(f"{AUTHORITY}/{relative}")
        source_span, source_raw = span(raw, first, last)
        affected = section
        for asset_key, slug in ASSET_SLUGS.items():
            if slug.replace("-", "").lower() in relative.replace("_", "").replace("/", "").lower() or asset_key.lower() in relative.lower():
                affected = localized_assets.get(asset_key, section)
                break
        correction_rows.append(add(records, idx, "corrections", record(
            "correction",
            f"r011/correction/b026-{order:02d}",
            **common(idx, text_rights, parent_id=section["id"], order=order, source_path=relative, source_span=source_span, source_sha256=hashlib.sha256(source_raw).hexdigest(), locale="id-ID", affected_id=affected["id"], correction_type="source_semantic_or_producer_correction", correction_id=f"C{order:02d}", confidence=candidate["confidence"], source_claim=candidate["source_issue"], proposed_correction=candidate["translation_action"], rationale="Pinned B026 blueprint plus deterministic text/asset QA confirm this bounded correction.", evidence=ev["text_checkpoint"]["path"], upstream_report_disposition="hold_until_complete_corpus_then_single_deduplicated_high-confidence-report", authority_mutated=False),
        )))

    artifact_by_role: dict[str, dict] = {}
    for order, (role, item) in enumerate(sorted(ev.items()), 1):
        state = "visually_checked" if role in {"candidate_pdf", "candidate_text", "pagewise_language_qa", "automated_visual_qa", "root_visual_qa", "asset_closure", "asset_visual_montage"} or role.startswith("asset_localized_") or role.startswith("rejected_candidate_") else ("built" if role == "build_qa" else "structurally_verified")
        artifact_by_role[role] = add(records, idx, "artifacts", record(
            "artifact",
            f"r011/artifact/b026/{role}",
            **common(idx, text_rights if not role.startswith("base_b025") else [], parent_id=section["id"], order=order, source_path=item["path"], source_sha256=item["sha256"], locale="zxx", artifact_kind=role, path=item["path"], evidence_copy_path=item["destination"], bytes=item["bytes"], sha256=item["sha256"], result="exact B026 frozen input, component witness, or deterministic evidence", provenance=MODEL, translation_state=state),
        ))

    qa_specs = [
        ("source", "source_blueprint"),
        ("text_closure", "text_checkpoint"),
        ("translation_a", "main_translation_a_qa"),
        ("translation_b", "main_translation_b_qa"),
        ("translation_c", "main_translation_c_qa"),
        ("translation_de", "main_translation_de_qa"),
        ("translation_f", "main_translation_f_qa"),
        ("exercise_answer", "exercise_answer_qa"),
        ("asset", "asset_closure"),
        ("asset_visual", "asset_root_visual_qa"),
        ("build", "build_qa"),
        ("reader_structure", "automated_reader_qa"),
        ("language", "pagewise_language_qa"),
        ("automated_visual", "automated_visual_qa"),
        ("root_visual", "root_visual_qa"),
        ("reader_replay", "reader_qa_verifier"),
        ("backend_interoperability", "backend_compiler"),
        ("backend_binding", "backend_postbuild_binder"),
    ]
    qa_rows: list[dict] = []
    for order, (kind, role) in enumerate(qa_specs, 1):
        if role not in artifact_by_role:
            raise StageGateError(f"required QA artifact role is not bound: {role}")
        artifact = artifact_by_role[role]
        qa_rows.append(add(records, idx, "qa_events", record(
            "qa_event",
            f"r011/qa/b026/{kind}-{order:02d}",
            **common(idx, [], parent_id=section["id"], order=order, locale="zxx", qa_type=kind, result="passed", subject_id=section["id"], witness_artifact_id=artifact["id"], witness_path=artifact["path"], detail=f"Exact B026 {kind} closure passed.", provenance=MODEL),
        )))
    rejected_candidate_event = add(records, idx, "qa_events", record(
        "qa_event",
        "r011/qa/b026/rejected-candidate-9adb2d37",
        **common(
            idx,
            [],
            parent_id=section["id"],
            order=len(qa_specs) + 1,
            locale="zxx",
            qa_type="visual_reflow_rejection",
            result="rejected",
            subject_id=section["id"],
            witness_artifact_id=artifact_by_role["rejected_candidate_9adb2d37_qa"]["id"],
            witness_path=artifact_by_role["rejected_candidate_9adb2d37_qa"]["path"],
            detail="The superseded 9adb2d37 candidate was rejected for a page-271 forced-break reflow defect and is never an admitted or reader-lineage artifact.",
            provenance=MODEL,
        ),
    ))
    rejected_candidate_5b83846d_event = add(records, idx, "qa_events", record(
        "qa_event",
        "r011/qa/b026/rejected-candidate-5b83846d",
        **common(
            idx,
            [],
            parent_id=section["id"],
            order=len(qa_specs) + 2,
            locale="zxx",
            qa_type="visual_reflow_rejection",
            result="rejected",
            subject_id=section["id"],
            witness_artifact_id=artifact_by_role["rejected_candidate_5b83846d_qa"]["id"],
            witness_path=artifact_by_role["rejected_candidate_5b83846d_qa"]["path"],
            detail="The superseded 5b83846d candidate was rejected after full contact-sheet inspection for forced-break underfill defects on pages 273 and 275 and is never an admitted or reader-lineage artifact.",
            provenance=MODEL,
        ),
    ))

    counters: Counter[str] = Counter()

    def relation(kind: str, from_id: str, to_id: str, qualifier: str, order: int = 0) -> None:
        counters[kind] += 1
        add(records, idx, "relations", record(
            "relation",
            f"r011/relation/b026/{kind}/{counters[kind]:04d}",
            **common(idx, [], relation_type=kind, from_id=from_id, to_id=to_id, qualifier=qualifier, order=order),
        ))

    relation("contains", book["id"], chapter["id"], "book hierarchy", 10)
    relation("contains", chapter["id"], section["id"], "source hierarchy", 1)
    relation("precedes", preceding["id"], chapter["id"], "book source order", 1)
    for order, (unit, segment, localization) in enumerate(pairs, 1):
        relation("contains", unit["parent_id"], unit["id"], "B026 unit", order)
        relation("unit_contains_segment", unit["id"], segment["id"], "translatable segment", order)
        relation("localizes", segment["id"], localization["id"], "id-ID localization", order)
    relation("range_intersects", main_units[0]["id"], section["id"], "main range A contains chapter opening and Section 7.1 opening", 1)
    for number in EXERCISES:
        relation("exercises", exercises[number]["id"], section["id"], "Section 7.1 exercise", number)
        if number in answers:
            relation("answers", answers[number]["id"], exercises[number]["id"], "upstream-public answer", number)
        else:
            relation("contains", exercises[number]["id"], gaps[number]["id"], "O001 companion-answer gap", 1)
            relation("requires_companion_answer", exercises[number]["id"], gaps[number]["id"], "O001 gap; no restricted solution", number)
    for concept, term in terms:
        relation("covers", section["id"], concept["id"], "B026 concept", term["order"])
        relation("lexicalizes", concept["id"], term["id"], "id-ID controlled term", term["order"])
    for order, prerequisite in enumerate(prerequisites, 1):
        relation("requires_concept", section["id"], prerequisite["id"], "Section 7.1 prerequisite", order)
    for order, (slug, prior_key) in enumerate(EQUIVALENT_CONCEPT_KEYS.items(), 1):
        relation(
            "same_concept_as",
            idx[f"r011/concept/b026/{slug}"]["id"],
            idx[prior_key]["id"],
            "locale-neutral concept continuity across corpus boundaries",
            order,
        )
    for order, key in enumerate(ASSET_SLUGS, 1):
        relation("produces", producers[key]["id"], source_assets[key]["id"], "frozen adjacent R producer", order)
        relation("localizes_asset", source_assets[key]["id"], localized_assets[key]["id"], "Indonesian localization or high-confidence corrected regeneration", order)
        relation("uses_asset", section["id"], localized_assets[key]["id"], "reader-visible localized/corrected generated figure", order)
    for key in ASSET_SLUGS:
        if key != "t_distribution":
            relation("uses_runtime_data", producers[key]["id"], runtime_dependencies["openintro-col"]["id"], "openintro plotting palette/helper dependency", 1)
    relation("uses_runtime_data", producers["run17SampTimeHistogram"]["id"], runtime_dependencies["openintro-run-samples"]["id"], "run17/run10Samp runtime objects", 2)
    relation("uses_runtime_data", producers["adult_heights_hist"]["id"], runtime_dependencies["openintro-bdims"]["id"], "bdims runtime object", 3)
    relation("uses_asset", section["id"], dolphin["id"], "byte-identical reader-visible Risso's dolphin photograph", 9)
    relation("documents_rights", dolphin_witness["id"], dolphin["id"], "Mike Baird CC BY 2.0 attribution witness", 1)
    for order, row in enumerate(correction_rows, 1):
        relation("corrects", row["id"], row["affected_id"], "high-confidence source issue held for one post-corpus report", order)
    for order, row in enumerate(qa_rows, 1):
        relation("validates", row["id"], section["id"], row["qa_type"], order)
    relation("rejects", rejected_candidate_event["id"], artifact_by_role["rejected_candidate_9adb2d37_qa"]["id"], "superseded candidate held only as adverse QA evidence", 1)
    relation("rejects", rejected_candidate_5b83846d_event["id"], artifact_by_role["rejected_candidate_5b83846d_qa"]["id"], "superseded candidate held only as adverse QA evidence", 2)
    for order, row in enumerate(artifact_by_role.values(), 1):
        relation("documents", row["id"], section["id"], row["artifact_kind"], order)
    relation("supersedes", artifact_by_role["candidate_pdf"]["id"], idx["r011/artifact/b025/candidate_pdf"]["id"], "reader lineage; all B025 records retained", 1)

    schema = json.loads((EXPORTS / "schemas/backend-record-v0.1.0.schema.json").read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
    all_rows = [row for rows in records.values() for row in rows]
    ids = {row["id"] for row in all_rows}
    if len(ids) != len(all_rows):
        raise StageGateError("duplicate backend record ID")
    new_rows = [row for row in all_rows if row.get("boundary_id") == BOUNDARY_ID]
    for row in new_rows:
        errors = list(validator.iter_errors(row))
        if errors:
            raise StageGateError(f"record schema failure {row['stable_key']}: {errors[0].message}")
        for field in ("resource_id", "edition_id", "parent_id", "unit_id", "source_segment_id", "concept_id", "affected_id", "subject_id", "witness_artifact_id", "from_id", "to_id"):
            referenced = row.get(field)
            if referenced is not None and referenced not in ids:
                raise StageGateError(f"record reference failure {row['stable_key']}: {field}={referenced!r}")
        for list_field in ("rights_component_ids", "prerequisite_ids"):
            values = row.get(list_field, [])
            if not isinstance(values, list):
                raise StageGateError(f"record reference-list failure {row['stable_key']}: {list_field} is not a list")
            for referenced in values:
                if referenced not in ids:
                    raise StageGateError(f"record reference failure {row['stable_key']}: {list_field}={referenced!r}")
    for table, old in base_rows.items():
        after = [canonical(row) for row in records[table] if row.get("boundary_id") != BOUNDARY_ID]
        if after != old:
            raise StageGateError(f"B025-and-earlier canonical record preservation failed: {table}")

    payloads = {path: serializers.jsonl_bytes(records[table]) for table, path in RECORD_PATHS.items()}
    views, view_counts = serializers.build_views(records)
    payloads.update(views)
    payloads["identity_map.jsonl"] = serializers.identity_map_bytes(records)
    validate_serializations(records, payloads, view_counts, len(all_rows))
    payloads.update(evidence_payloads)
    counts = {table: len(rows) for table, rows in sorted(records.items())}
    new_counts = Counter(row["record_type"] for row in new_rows)
    files = {row["path"]: copy.deepcopy(row) for row in base_manifest["files"] if row["path"] not in payloads}
    for path, raw in payloads.items():
        table = next((table for table, table_path in RECORD_PATHS.items() if table_path == path), None)
        count = len(records[table]) if table else (view_counts.get(path) if path in view_counts else (len(all_rows) if path == "identity_map.jsonl" else None))
        files[path] = {"path": path, **raw_identity(raw), "records": count}
    reader = binding["post_build_outputs"]["candidate_pdf"]
    manifest = copy.deepcopy(base_manifest)
    manifest.update({
        "boundary_id": BOUNDARY_ID,
        "workflow_id": WORKFLOW,
        "recorded_at": RECORDED_AT,
        "stage_state": "live_admitted_candidate",
        "admission_eligibility": "admitted_pending_publication",
        "base_preservation": {
            "boundary_id": "R011-B025",
            "manifest": {key: BASE_BACKEND[key] for key in ("bytes", "sha256")},
            "record_count": BASE_RECORD_COUNT,
            "record_counts": BASE_RECORD_COUNTS,
            "all_b025_and_earlier_records_preserved_canonical_bytes": True,
            "all_b025_jsonl_csv_identity_exports_replay_byte_identically_from_preserved_records": True,
        },
        "base_record_counts": BASE_RECORD_COUNTS,
        "new_b026_record_count": sum(new_counts.values()),
        "new_b026_record_counts": dict(sorted(new_counts.items())),
        "record_count": len(all_rows),
        "record_counts": counts,
        "scope": {
            "included": "Indonesian front matter and Chapters 1-6 plus Chapter 7 opening and Section 7.1; Chapter 7 exercises 1-14; public odd answers 1-13.",
            "new_b026_scope": "Chapter 7 opening and complete Section 7.1, six source-ordered main localization ranges, exercises 1-14, public answers 1/3/5/7/9/11/13, O001 gaps 2/4/6/8/10/12/14, eight localized/corrected generated figures, and one byte-identical CC BY 2.0 photograph.",
            "excluded": ["Chapter 7 Section 7.2 and later", "non-public even answers 2-14", "restricted instructor solutions"],
            "reader_pages": reader["pages"],
            "reader_bytes": reader["bytes"],
            "reader_sha256": reader["sha256"],
            "next_cursor": {"path": "ch_inference_for_means/TeX/ch_inference_for_means.tex", "line": 1059, "label_line": 1060, "label": "pairedData", "boundary_id": "R011-B027"},
        },
        "topology": {
            "chapter": 7,
            "section": "7.1",
            "main_localization_ranges": 6,
            "exercise_numbers": list(EXERCISES),
            "public_answers": list(ANSWER_RANGES),
            "o001_companion_gaps": [2, 4, 6, 8, 10, 12, 14],
            "reader_visible_assets": 9,
            "localized_or_corrected_generated_figures": 8,
            "source_generated_figures": 8,
            "r_producers": 8,
            "runtime_package_object_records": 3,
            "runtime_package_objects": ["COL", "run10Samp", "run17", "bdims"],
            "byte_identical_photos": 1,
            "standalone_datasets": 0,
            "restricted_solutions_accessed_or_invented": False,
        },
        "source_corrections": {
            "count": 16,
            "high_confidence_upstream_candidates": 16,
            "upstream_reporting": "hold_until_complete_corpus_then_single_deduplicated-high-confidence-report",
            "authority_mutated": False,
        },
        "build_binding": {
            "status": "exact_final_candidate_bound",
            "candidate_identities_bound": True,
            "reader_pdf": reader,
            "reader_text": binding["post_build_outputs"]["candidate_text"],
            "build_receipt": binding["post_build_outputs"]["build_qa"],
            "deterministic_replays": 2,
            "pdf_byte_identical": True,
            "text_byte_identical": True,
        },
        "qa_closure": {
            "source": "passed",
            "translation": "passed",
            "exercise_answer": "passed",
            "asset": "passed",
            "asset_visual": "passed",
            "rights": "passed",
            "build": "passed",
            "language": "passed",
            "visual": "passed",
            "language_receipt": binding["post_build_outputs"]["pagewise_language_qa"],
            "automated_visual_receipt": binding["post_build_outputs"]["automated_visual_qa"],
            "visual_receipt": binding["post_build_outputs"]["root_visual_qa"],
        },
        "interoperability": {
            "envelope_version": "v0",
            "stable_locale_neutral_ids": True,
            "deterministic_json_jsonl_csv": True,
            "schema_validated": True,
            "schema_validation_scope": "all new B026 records; inherited B025-and-earlier rows proven canonical-byte identical",
            "referential_integrity": True,
            "unit_selectable": True,
            "exercise_answer_gap_closure": True,
            "asset_code_data_rights_closure": True,
            "typed_correction_records": True,
            "final_state": "visually_checked",
        },
        "publication": {
            "status": "not_performed_by_backend_admission",
            "prior_b025_publication": copy.deepcopy(base_manifest.get("publication")),
            "prior_b025_public_receipts_preserved": True,
        },
        "files": [files[path] for path in sorted(files)],
    })
    manifest_raw = serializers.canonical_json(serializers.normalize(manifest))
    if serializers.canonical_json(json.loads(manifest_raw)) != manifest_raw:
        raise StageGateError("generated manifest JSON is not an exact canonical replay")
    manifest_schema = json.loads((EXPORTS / "schemas/backend-manifest-v0.1.0.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(json.loads(manifest_raw), manifest_schema)
    inventory = hashlib.sha256(
        "".join(f"{path}\t{len(raw)}\t{hashlib.sha256(raw).hexdigest()}\n" for path, raw in sorted({**payloads, "manifest.json": manifest_raw}.items())).encode()
    ).hexdigest()
    return {"payloads": payloads, "manifest_raw": manifest_raw, "manifest": json.loads(manifest_raw), "inventory_sha256": inventory}


def twice(base_root: Path) -> dict[str, Any]:
    first = compile(base_root)
    second = compile(base_root)
    if first["manifest_raw"] != second["manifest_raw"] or first["payloads"] != second["payloads"]:
        raise StageGateError("two B026 backend compilations differ")
    return first


def verify_preimages() -> dict[str, Any]:
    if not PREIMAGE_MANIFEST.is_file() or not (PREIMAGES / "manifest.json").is_file():
        raise StageGateError("B026 backend preimage set is absent or incomplete")
    try:
        payload = json.loads(PREIMAGE_MANIFEST.read_text(encoding="utf-8"))
        base_manifest = json.loads((PREIMAGES / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StageGateError("B026 backend preimage metadata is not valid UTF-8 JSON") from exc
    expected_manifest = {key: BASE_BACKEND[key] for key in ("bytes", "sha256")}
    if payload.get("boundary_id") != "R011-B025" or payload.get("manifest") != expected_manifest:
        raise StageGateError("B026 backend preimage metadata does not bind exact B025")
    manifest_observed = identity(PREIMAGES / "manifest.json")
    manifest_identity = {key: manifest_observed[key] for key in ("bytes", "sha256")}
    if manifest_identity != expected_manifest:
        raise StageGateError("B026 backend manifest preimage changed")
    expected_rows = [
        {"path": item["path"], "bytes": item["bytes"], "sha256": item["sha256"]}
        for item in base_manifest.get("files", [])
    ]
    if payload.get("files") != expected_rows:
        raise StageGateError("B026 backend preimage inventory differs from the exact B025 manifest")
    for row in expected_rows:
        observed = identity(PREIMAGES / row["path"])
        if {key: observed[key] for key in ("bytes", "sha256")} != {key: row[key] for key in ("bytes", "sha256")}:
            raise StageGateError(f"B026 backend preimage changed: {row['path']}")
    return {"manifest": manifest_identity, "files": len(expected_rows)}


def save_preimages() -> None:
    if PREIMAGES.exists():
        verify_preimages()
        return
    PREIMAGES.mkdir(parents=True)
    base = json.loads((EXPORTS / "manifest.json").read_text(encoding="utf-8"))
    rows = []
    for item in base["files"]:
        source = EXPORTS / item["path"]
        target = PREIMAGES / item["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        rows.append({"path": item["path"], "bytes": item["bytes"], "sha256": item["sha256"]})
    shutil.copyfile(EXPORTS / "manifest.json", PREIMAGES / "manifest.json")
    PREIMAGE_MANIFEST.write_bytes(canonical({"boundary_id": "R011-B025", "manifest": {key: BASE_BACKEND[key] for key in ("bytes", "sha256")}, "files": rows}))
    verify_preimages()


def admit() -> dict[str, Any]:
    live_manifest = raw_identity((EXPORTS / "manifest.json").read_bytes())
    exact_base = {key: BASE_BACKEND[key] for key in ("bytes", "sha256")}
    if live_manifest == exact_base:
        verify_text_inputs()
        load_asset_closure(require_complete=True)
        load_bindings(require_complete=True)
        if PREIMAGES.exists():
            verify_preimages()
            compiled = twice(PREIMAGES)
        else:
            compiled = twice(EXPORTS)
            save_preimages()
        staged: dict[str, Path] = {}
        with tempfile.TemporaryDirectory(prefix="b026-backend-") as temporary_directory:
            temporary = Path(temporary_directory)
            for relative, raw in {**compiled["payloads"], "manifest.json": compiled["manifest_raw"]}.items():
                path = temporary / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
                staged[relative] = path
            for relative in sorted(compiled["payloads"]):
                target = EXPORTS / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                os.replace(staged[relative], target)
            os.replace(staged["manifest.json"], EXPORTS / "manifest.json")
    else:
        verify_preimages()
        compiled = twice(PREIMAGES)
        if (EXPORTS / "manifest.json").read_bytes() != compiled["manifest_raw"]:
            raise StageGateError("live backend is neither exact B025 nor exact interrupted B026 candidate")
        for relative, raw in compiled["payloads"].items():
            if not (EXPORTS / relative).is_file() or (EXPORTS / relative).read_bytes() != raw:
                raise StageGateError(f"interrupted B026 candidate payload differs: {relative}")
    replay = verify(write_receipt=False)
    receipt = {
        "$schema": "interlanguage.r011-b026-backend-admission/v1",
        "boundary_id": BOUNDARY_ID,
        "status": "PASS_B026_BACKEND_ATOMIC_ADMISSION_AND_EXACT_REPLAY",
        "base_manifest": {key: BASE_BACKEND[key] for key in ("bytes", "sha256")},
        "live_manifest": identity(EXPORTS / "manifest.json"),
        "record_count": compiled["manifest"]["record_count"],
        "record_counts": compiled["manifest"]["record_counts"],
        "new_b026_record_count": compiled["manifest"]["new_b026_record_count"],
        "new_b026_record_counts": compiled["manifest"]["new_b026_record_counts"],
        "payload_inventory_sha256": compiled["inventory_sha256"],
        "post_build_binding": identity(BINDINGS_PATH),
        "git_used": False,
        "credentials_accessed": False,
        "network_used": False,
        "publication_performed": False,
        "upstream_contact": False,
    }
    output = repo_path(BACKEND_ADMISSION_RECEIPT_PATH)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(canonical(receipt))
    verify(write_receipt=True)
    return {**receipt, "receipt": identity(output), "replay": replay}


def verify(*, write_receipt: bool) -> dict[str, Any]:
    verify_preimages()
    compiled = twice(PREIMAGES)
    if (EXPORTS / "manifest.json").read_bytes() != compiled["manifest_raw"]:
        raise StageGateError("live B026 manifest differs from exact replay")
    for relative, raw in compiled["payloads"].items():
        if (EXPORTS / relative).read_bytes() != raw:
            raise StageGateError(f"live B026 payload differs: {relative}")
    receipt = {
        "$schema": "interlanguage.r011-b026-backend-replay/v1",
        "boundary_id": BOUNDARY_ID,
        "status": "PASS_EXACT_B026_BACKEND_REPLAY_AND_REFERENTIAL_INTEGRITY",
        "live_manifest": identity(EXPORTS / "manifest.json"),
        "record_count": compiled["manifest"]["record_count"],
        "record_counts": compiled["manifest"]["record_counts"],
        "new_b026_record_count": compiled["manifest"]["new_b026_record_count"],
        "new_b026_record_counts": compiled["manifest"]["new_b026_record_counts"],
        "payload_inventory_sha256": compiled["inventory_sha256"],
        "git_used": False,
        "credentials_accessed": False,
        "network_used": False,
        "publication_performed": False,
    }
    if write_receipt:
        output = repo_path(BACKEND_REPLAY_RECEIPT_PATH)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(canonical(receipt))
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--self-test", action="store_true")
    mode.add_argument("--probe", action="store_true")
    mode.add_argument("--admit", action="store_true")
    mode.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        text = verify_text_inputs()
        asset = load_asset_closure(require_complete=True)
        result = {
            "status": "PASS_B026_BACKEND_STATIC_TEXT_ASSET_RIGHTS_INPUTS_EXACT_POST_BUILD_BINDING_OPTIONAL",
            "sealed_text_inputs": len(text),
            "asset_outputs": len(asset["artifacts"]),
            "asset_inventory": asset["output_inventory"],
            "final_binding_present": BINDINGS_PATH.is_file(),
            "writes_performed": False,
        }
    elif args.probe:
        compiled = twice(EXPORTS)
        result = {
            "status": "PASS_B026_BACKEND_READ_ONLY_TWO_EXACT_REPLAYS",
            "candidate_manifest": raw_identity(compiled["manifest_raw"]),
            "record_count": compiled["manifest"]["record_count"],
            "new_b026_record_count": compiled["manifest"]["new_b026_record_count"],
            "new_b026_record_counts": compiled["manifest"]["new_b026_record_counts"],
            "payload_inventory_sha256": compiled["inventory_sha256"],
            "writes_performed": False,
        }
    elif args.admit:
        result = admit()
    else:
        result = verify(write_receipt=False)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except StageGateError as exc:
        raise SystemExit(f"REFUSED: {exc}")
