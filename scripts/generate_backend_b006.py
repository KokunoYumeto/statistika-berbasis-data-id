#!/usr/bin/env python3
"""Generate the deterministic, isolated R011-B006 modular-backend stage.

The admitted R011-B005 live backend is immutable input.  This generator checks
and loads all 1,618 typed records byte-semantically, adds the complete Section
2.2 model, and writes only under ``qa/b006-backend/exports``.  Final source,
build, reviewed-candidate PDF, and visual identities must be supplied in an
external exact-input manifest; no placeholder or guessed artifact is emitted.
This script never promotes the live backend and never admits the boundary.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import io
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


LANE = Path(__file__).resolve().parents[1]
BASE_BACKEND = LANE / "backend"
BASE_EXPORTS = BASE_BACKEND / "exports"
STAGING_ROOT = LANE / "qa" / "b006-backend"
STAGING_EXPORTS = STAGING_ROOT / "exports"
TARGET_ROOT = LANE / "repo"
TERMINOLOGY_CONTROL = LANE / "00_control" / "TERMINOLOGY.csv"
ADVERSE_CONTROL = LANE / "00_control" / "ADVERSE_LEDGER.jsonl"
RIGHTS_CONTROL = LANE / "00_control" / "COMPONENT_RIGHTS.csv"
PREAPPLICATION_MANIFEST = LANE / "qa" / "R011-B006_PREAPPLICATION_MANIFEST.json"
SOURCE_APPLICATION_RECEIPT = LANE / "qa" / "R011-B006_SOURCE_APPLICATION_RECEIPT.json"
REPAIR_RECEIPT = LANE / "qa" / "R011-B006_REPAIR_RECEIPT.json"
LAYOUT_REPAIR_RECEIPT = LANE / "qa" / "R011-B006_LAYOUT_REPAIR_RECEIPT_V3.json"
LAYOUT_REPAIR_RECEIPT_V4 = LANE / "qa" / "R011-B006_LAYOUT_REPAIR_RECEIPT_V4.json"
REJECTED_BUILD_RECEIPT_V1 = LANE / "qa" / "R011-B006_BUILD_QA_V1_REJECTED.json"
REJECTED_VISUAL_FINDINGS_V1 = LANE / "qa" / "R011-B006_VISUAL_FINDINGS_V1.json"
REJECTED_BUILD_RECEIPT_V2 = LANE / "qa" / "R011-B006_BUILD_QA_V2_REJECTED.json"
REJECTED_VISUAL_FINDINGS_V2 = LANE / "qa" / "R011-B006_VISUAL_FINDINGS_V2.json"
REJECTED_BUILD_RECEIPT_V3 = LANE / "qa" / "R011-B006_BUILD_QA_V3_REJECTED.json"
REJECTED_VISUAL_FINDINGS_V3 = LANE / "qa" / "R011-B006_VISUAL_FINDINGS_V3.json"
ASSET_MANIFEST = LANE / "qa" / "b006-assets" / "ASSET_MANIFEST_R011-B006.json"
ASSET_RECEIPT = LANE / "qa" / "b006-assets" / "ASSET_VALIDATION_RECEIPT_R011-B006.json"
POPPLER_CONTACT_SHEET = LANE / "qa" / "b006-assets" / "B006_ASSET_POPPLER_SOURCE_TARGET_CONTACT_SHEET.png"
MUPDF_CONTACT_SHEET = LANE / "qa" / "b006-assets" / "B006_ASSET_MUPDF_SOURCE_TARGET_CONTACT_SHEET.png"
LOCALIZER = LANE / "scripts" / "localize_b006_figures.py"

BODY_PATH = "ch_summarizing_data/TeX/ch_summarizing_data.tex"
EXERCISE_PATH = "ch_summarizing_data/TeX/considering_categorical_data.tex"
ANSWER_PATH = "extraTeX/eoceSolutions/eoceSolutions.tex"

SCHEMA_VERSION = "0.1.0"
RECORDED_AT = "2026-08-22T00:00:00+02:00"
WORKFLOW_ID = "r011-openintro-statistics-id-b006"
BOUNDARY_ID = "R011-B006"
BASE_BOUNDARY_ID = "R011-B005"
BASE_MANIFEST_SHA256 = "ad872679e96a51f73c54f4b95ffdf122801e828e3193c4c43083beece7b8cfee"
BASE_RECORD_COUNT = 1618

EXPECTED_AUTHORITY = {
    "commit": "fee25091fb24e89c36296fd67c48c1fcf7a93b6e",
    "tree": "d61cc601e7d97759ce805900520f784d02a0489e",
}

EXPECTED_FIXED_EVIDENCE = {
    "preapplication": {
        "path": "qa/R011-B006_PREAPPLICATION_MANIFEST.json",
        "bytes": 3983,
        "sha256": "d6e832dc0519892bf29cb94672c7210b4886425666b36947f42883d355e73965",
    },
    "source_application": {
        "path": "qa/R011-B006_SOURCE_APPLICATION_RECEIPT.json",
        "bytes": 9586,
        "sha256": "56d69a600cf4ad1bb18ede91b588266fba4e1f10f8356ba67ec96103d3a84286",
    },
    "repair_receipt": {
        "path": "qa/R011-B006_REPAIR_RECEIPT.json",
        "bytes": 12510,
        "sha256": "145f3b47954a03999d3695e2dbd3206717dd89af76ea8aaad63974e431321492",
    },
    "layout_repair_receipt": {
        "path": "qa/R011-B006_LAYOUT_REPAIR_RECEIPT_V3.json",
        "bytes": 11120,
        "sha256": "fd3e6048d0e68b6e6287463f7d85f686a33f0770f59bb1c3d5cdd9445e6b59be",
    },
    "layout_repair_receipt_v4": {
        "path": "qa/R011-B006_LAYOUT_REPAIR_RECEIPT_V4.json",
        "bytes": 9800,
        "sha256": "e969de593a0504cdeba1ca5fa8e9c76e096b2c4a5d64d0d90f466845df12d3e9",
    },
    "rejected_build_receipt_v1": {
        "path": "qa/R011-B006_BUILD_QA_V1_REJECTED.json",
        "bytes": 15819,
        "sha256": "e649a2cbe71f4041b0684f8764b7297a5cbcbac4c8c78ed412a2e0b297806e16",
    },
    "rejected_visual_findings_v1": {
        "path": "qa/R011-B006_VISUAL_FINDINGS_V1.json",
        "bytes": 2013,
        "sha256": "cc4adb506a84b231d2d0988ee024dd673e2ae3b70cca9d7b9924333e8d923231",
    },
    "rejected_build_receipt_v2": {
        "path": "qa/R011-B006_BUILD_QA_V2_REJECTED.json",
        "bytes": 2066,
        "sha256": "9792c0fc177e652889575c7ffdfcbbe503fbabca08e53224a8c52f39c42c7188",
    },
    "rejected_visual_findings_v2": {
        "path": "qa/R011-B006_VISUAL_FINDINGS_V2.json",
        "bytes": 2396,
        "sha256": "6221077b007c1357e4524fdefc1719cd4beedeea4a363d5919e012a7ceea950c",
    },
    "rejected_build_receipt_v3": {
        "path": "qa/R011-B006_BUILD_QA_V3_REJECTED.json",
        "bytes": 2408,
        "sha256": "717e987c26fb76783ba612563790faed06f16791ba2edb369022eedb0ac7a5d9",
    },
    "rejected_visual_findings_v3": {
        "path": "qa/R011-B006_VISUAL_FINDINGS_V3.json",
        "bytes": 2150,
        "sha256": "4126d7612063aa9497bdaaa1d0526087160ed266398c223dffbf31042d3585b3",
    },
    "asset_manifest": {
        "path": "qa/b006-assets/ASSET_MANIFEST_R011-B006.json",
        "bytes": 20602,
        "sha256": "12df13ae4eeac43f492ec77efbe96d8470ffda0aeaf0c16265c879f4f1fb41ac",
    },
    "asset_receipt": {
        "path": "qa/b006-assets/ASSET_VALIDATION_RECEIPT_R011-B006.json",
        "bytes": 8001,
        "sha256": "3c9843944b53e7791fc0998f625dc31d6adcc63250fca4fe9d34f4cd1bcd4582",
    },
    "poppler_contact_sheet": {
        "path": "qa/b006-assets/B006_ASSET_POPPLER_SOURCE_TARGET_CONTACT_SHEET.png",
        "bytes": 1349643,
        "sha256": "56b55ada23a7516c04992ec3ff14a7599011569ffa028cae513be5f14cbc8047",
    },
    "mupdf_contact_sheet": {
        "path": "qa/b006-assets/B006_ASSET_MUPDF_SOURCE_TARGET_CONTACT_SHEET.png",
        "bytes": 1374921,
        "sha256": "221a3dd6513f7cb94a042d1240c7ec062247a1e0c5685f71be1eb4d1ed6b9063",
    },
    "localizer": {
        "path": "scripts/localize_b006_figures.py",
        "bytes": 20207,
        "sha256": "12071f770b73440a98722a430cc09d046465e2469d7956bfc08b4e618913f6b4",
    },
    "terminology": {
        "path": "00_control/TERMINOLOGY.csv",
        "bytes": 11279,
        "sha256": "622fa65372875784cb190619175750bcfbfa9600bcc4526f521019c39f093f7e",
    },
    "adverse": {
        "path": "00_control/ADVERSE_LEDGER.jsonl",
        "bytes": 36030,
        "sha256": "04032e0f4486268d99d809333779fd450d4062d376149ca0945f34e24f8af7c3",
    },
    "rights": {
        "path": "00_control/COMPONENT_RIGHTS.csv",
        "bytes": 9999,
        "sha256": "009feba8ff1f329ef742793f55f6b090dd08f3f761f9b9cc1edcbe03ecff58f0",
    },
}

SOURCE_GATE_PATHS = {
    "source_qa": "qa/R011-B006_SOURCE_QA.json",
    "target_manifest": "qa/R011-B006_TARGET_MANIFEST.tsv",
}

EXPECTED_SOURCE_GATE = {
    "source_qa": {
        "path": "qa/R011-B006_SOURCE_QA.json",
        "bytes": 51559,
        "sha256": "524852f1e21939d8a0ced8ab5d79f1a74d0bbf552ca06f0ce252082f30a4c918",
    },
    "target_manifest": {
        "path": "qa/R011-B006_TARGET_MANIFEST.tsv",
        "bytes": 173738,
        "sha256": "bdf80b178094d903305c8d5539d969db39502720bbe0e0d5e3735ca92e8a05f4",
    },
    "gate_script": {
        "path": "scripts/qa_boundary_b006.py",
        "bytes": 154974,
        "sha256": "3a6e168dd7bcbf47ef6203e06f251f52d6dee246161458e156e3d043e371efcb",
    },
}

# V4 is the final source closure: it retains the three receipt-proven V3
# substitutions and adds one receipt-proven exercise-flow repair over rejected
# V3.  The target path set remains unchanged.
EXPECTED_TARGET_CLOSURE = {"file_count": 1195, "file_bytes": 41205947}

EXPECTED_TARGET_SOURCE = {
    "body": {
        "path": f"repo/{BODY_PATH}",
        "bytes": 114091,
        "sha256": "3a087003f4bcb01268090fc2a04a8c40f9b46da7ff5a5f276a591a9d266e7a9c",
    },
    "exercises": {
        "path": f"repo/{EXERCISE_PATH}",
        "bytes": 6644,
        "sha256": "dd8f682d4188597869ec0e3bd873e04b0be3c6636de117788ff65101ba2241ab",
    },
    "answers": {
        "path": f"repo/{ANSWER_PATH}",
        "bytes": 107940,
        "sha256": "49ad90a6c041ec23cfb99ce5f0a1ece6bf45516cc82eabbe02474c1604749b43",
    },
    "translated_section": {
        "bytes": 40659,
        "sha256": "a10673b1f0be2e0421e52eeb170e46baa3538e96235409b56f0a1d23b0e936f4",
    },
    "translated_answers": {
        "bytes": 643,
        "sha256": "8b93b3193a9de524b9987570d29d1ee5330b328b54d7794883cd627b6a98dd57",
    },
}

EXPECTED_FINAL_INPUTS = {
    "source_qa": EXPECTED_SOURCE_GATE["source_qa"],
    "target_manifest": EXPECTED_SOURCE_GATE["target_manifest"],
    "build_gate_script": {
        "path": "scripts/qa_build_b006.py",
        "bytes": 49624,
        "sha256": "201e90f21fe17ee27e64e8f3a7ce79d5f50ddbe1124d6886f086c373d6fe3795",
    },
    "candidate_build_qa": {
        "path": "qa/b006-build/final-v4/CANDIDATE_BUILD_QA_V4.json",
        "bytes": 15252,
        "sha256": "a33e9c184697bfce38938d6ab52843d57f6de592cf42abd37f3effd75a0c1fbc",
    },
    "build_qa": {
        "path": "qa/R011-B006_BUILD_QA_V4.json",
        "bytes": 16346,
        "sha256": "6d7dd115518c3c3d080d48c05e9e52bd89b8b477498fed909b1041295f19d618",
    },
    "build_log": {
        "path": "qa/b006-build/final-v4/main.log",
        "bytes": 494501,
        "sha256": "9ca2696c1ab5995c26e48699db6bd25c7db46ad915b7ac3007249f4d25348cd8",
    },
    "build_text": {
        "path": "qa/b006-build/final-v4/main-final.txt",
        "bytes": 1588179,
        "sha256": "92521604fcf9d2102463eb6847a41fa3cb35f563c14f556cdbf3b6bcd1981539",
    },
    "pdf": {
        "path": "qa/b006-build/final-v4/main.pdf",
        "bytes": 21975722,
        "sha256": "d9a3df7d44a62babde04c355cb8dbb9edc74de947cc8162a3d30d872bea372b2",
        "page_count": 424,
    },
    "render_manifest": {
        "path": "qa/b006-render/final-v4/FINAL_MANIFEST.tsv",
        "bytes": 1500,
        "sha256": "dd0a15cb79c3e4e3b5d89944d1fc275716d72732d8824fd4d3fe6c96fd413588",
        "page_count": 17,
    },
    "page_locator": {
        "path": "qa/b006-render/final-v4/PAGE_LOCATOR.json",
        "bytes": 1599,
        "sha256": "4d6721fd2441371b609e1961ec9b0255b263b90e93b96253bc90253dd23f1492",
    },
    "contact_sheet": {
        "path": "qa/b006-render/final-v4/CONTACT_SHEET.png",
        "bytes": 859627,
        "sha256": "313d69ae077a3d53389cd5b4a9064abe731a2996f05f612b9b7e79044b880fd7",
    },
    "visual_audit": {
        "path": "qa/R011-B006_VISUAL_AUDIT_V4.json",
        "bytes": 7747,
        "sha256": "749f1210fa3c760abc18c984a2e1cb519c43b455d54bebc2cb3b173f67602e2c",
    },
    "visual_finalizer": {
        "path": "scripts/qa_finalize_b006_visual_v4.py",
        "bytes": 16228,
        "sha256": "15aed320dedf02d47b376e0b8be1860a8ff8221382bd976255b4a147fad442f1",
    },
}

EXPECTED_VISUAL_PAGES = list(range(61, 74)) + list(range(387, 391))


def load_b005_module():
    path = LANE / "scripts" / "generate_backend_b005.py"
    spec = importlib.util.spec_from_file_location("r011_backend_b005_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load B005 backend helpers: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


b005 = load_b005_module()
g = b005.g
RECORD_PATHS = b005.RECORD_PATHS

BASE_RECORD_PAYLOAD_IDENTITIES = {
    "core/programs.jsonl": {"bytes": 656, "sha256": "dd5b4eb45b3119f19978150224fb30cabc4c151a2f769724317c2ae2745d2571", "records": 1},
    "core/courses.jsonl": {"bytes": 904, "sha256": "14d8bf8fa7e12eeffe0ea500c0bee6a2b69d39c3e0b78771055ebe9e0878137b", "records": 1},
    "core/resources.jsonl": {"bytes": 1100, "sha256": "b75a21052d9cd5ee692b930fdef22839dc1c40a246dc28f412fcb8e6cfe98c75", "records": 1},
    "core/editions.jsonl": {"bytes": 2182, "sha256": "0aa35ab60d77843fde6639709cbb9a2d8cd49edd5c549527a4ec7e819657c544", "records": 1},
    "core/units.jsonl": {"bytes": 173988, "sha256": "b5ba3a130f1e01a711e2ef1fb620b10de6dd35991ff924a0b120bdbebcaa9c52", "records": 169},
    "core/concepts.jsonl": {"bytes": 84098, "sha256": "507cbd2d53de97a6269290cbb7d762e517a7046e9590f163008077b19c22e016", "records": 92},
    "core/segments.jsonl": {"bytes": 422270, "sha256": "ffe223d74eb10f4ffe7b706eea387d43a7e3aec00b1523d0c076027ece7fd74a", "records": 151},
    "core/assets.jsonl": {"bytes": 187614, "sha256": "0d92b22c63500b62b68a5a82fc153a8099c0b64929f11a7ec3074389c2ac49a5", "records": 142},
    "core/relations.jsonl": {"bytes": 494580, "sha256": "f7a1167a659eed78be2c0142262eed4979d6b9eb6bf242c254d846b299a4736b", "records": 608},
    "core/rights.jsonl": {"bytes": 25972, "sha256": "c8d28b2a92e4fb0fd8f632bad67f0145148fadf320890b5075741ea3e90f7df5", "records": 20},
    "core/corrections.jsonl": {"bytes": 99325, "sha256": "89680b2ab9e3ca5c41a0ba16d786cba24881c52ba01520113b02ade793fda62f", "records": 59},
    "locales/id-ID/localizations.jsonl": {"bytes": 648292, "sha256": "7e6175f40a4b921eb2a63e3709aca4f2592ea6775e0cc6cd7d8218b76f89bb9f", "records": 151},
    "locales/id-ID/terms.jsonl": {"bytes": 100708, "sha256": "f0d020b0f2a9c4a79d2c9e7a2cf80e3f214a0f0244c8f8791842075b6cc37673", "records": 92},
    "evidence/qa_events.jsonl": {"bytes": 72117, "sha256": "cc1ec80cbc4bcfeb4b91cfb1d2b9577d7715e9307a34fc95ff9595722ff11d84", "records": 60},
    "evidence/artifacts.jsonl": {"bytes": 81202, "sha256": "21e7a3562797ad4fb72866bab54074ba57d8e4a46b9f132c5377c0244116a72f", "records": 70},
}

SUBSECTION_SPECS = [
    ("contingency-tables-bar-plots", "Contingency tables and bar plots", []),
    ("row-column-proportions", "Row and column proportions", []),
    ("bar_plots_subsection", "Using a bar plot with two variables", ["bar_plots_subsection"]),
    ("mosaic_plots_subsection", "Mosaic plots", ["mosaic_plots_subsection"]),
    ("only-pie-chart", "The only pie chart you will see in this book", []),
    ("comparingAcrossGroups", "Comparing numerical data across groups", ["comparingAcrossGroups"]),
]

EXERCISE_SPECS = [
    (21, "antibiotic_use_children", "Antibiotic use in children"),
    (22, "immigration", "Views on immigration"),
    (23, "dream_act_mosaic", "Views on the DREAM Act"),
    (24, "raise_taxes_mosaic", "Raise taxes"),
]

TERM_DEFINITIONS = {
    "categorical data": "Data whose values identify groups or categories rather than numerical magnitudes.",
    "contingency table": "A table of counts or proportions for combinations of categorical-variable levels.",
    "row total": "The sum of all cell frequencies in one row of a contingency table.",
    "column total": "The sum of all cell frequencies in one column of a contingency table.",
    "bar plot": "A plot in which rectangular bar heights encode categorical counts or proportions.",
    "relative frequency": "A category count divided by the relevant total number of observations.",
    "row proportion": "A contingency-table cell frequency divided by its row total.",
    "column proportion": "A contingency-table cell frequency divided by its column total.",
    "stacked bar plot": "A bar plot whose bars are partitioned into stacked segments for a second categorical variable.",
    "segmented bar plot": "A source synonym for a stacked bar plot.",
    "side-by-side bar plot": "A bar plot placing category bars beside one another for direct comparison.",
    "standardized stacked bar plot": "A stacked bar plot in which every complete bar is scaled to total one.",
    "mosaic plot": "An area plot for a contingency table whose rectangle areas encode joint frequencies.",
    "pie chart": "A circle partitioned into sectors whose angles and areas encode category proportions.",
    "side-by-side box plot": "Box plots for multiple groups drawn on a common scale for comparison.",
    "hollow histogram": "An outline-only histogram overlaid with other group histograms on a common scale.",
    "homeownership": "The loan-data variable recording rent, mortgage, or outright ownership status.",
    "app_type": "The loan-data variable recording whether an application is individual or joint.",
    "independent": "Describing variables whose distributional proportions do not change with the other variable.",
    "dependent": "Describing variables whose distributional proportions vary with the other variable.",
}

INTRODUCING_SUBSECTION = {
    "categorical data": 0,
    "contingency table": 0,
    "row total": 0,
    "column total": 0,
    "bar plot": 0,
    "relative frequency": 0,
    "homeownership": 0,
    "app_type": 0,
    "row proportion": 1,
    "column proportion": 1,
    "stacked bar plot": 2,
    "segmented bar plot": 2,
    "side-by-side bar plot": 2,
    "standardized stacked bar plot": 2,
    "mosaic plot": 3,
    "pie chart": 4,
    "side-by-side box plot": 5,
    "hollow histogram": 5,
    "independent": 1,
    "dependent": 1,
}

PREREQUISITES = [
    ("categorical variable", "categorical data"),
    ("categorical data", "contingency table"),
    ("contingency table", "row total"),
    ("contingency table", "column total"),
    ("proportion", "relative frequency"),
    ("contingency table", "row proportion"),
    ("contingency table", "column proportion"),
    ("bar plot", "stacked bar plot"),
    ("stacked bar plot", "standardized stacked bar plot"),
    ("bar plot", "side-by-side bar plot"),
    ("contingency table", "mosaic plot"),
    ("box plot", "side-by-side box plot"),
    ("histogram", "hollow histogram"),
    ("row proportion", "independent"),
    ("column proportion", "independent"),
    ("independent", "dependent"),
]

EXERCISE_CONCEPTS = {
    21: ["bar plot", "pie chart", "relative frequency", "categorical data"],
    22: ["contingency table", "row proportion", "column proportion", "independent"],
    23: ["mosaic plot", "independent", "dependent"],
    24: ["mosaic plot", "independent", "dependent"],
}

ASSET_PARENT_MAP = {
    "loan_homeownership_bar_plot": ("subsection", 0),
    "loan_app_type_home_seg_bar": ("subsection", 2),
    "loan_app_type_home_sbs_bar": ("subsection", 2),
    "loan_app_type_home_seg_bar_standardized": ("subsection", 2),
    "loan_home_mosaic": ("subsection", 3),
    "loan_app_type_home_mosaic": ("subsection", 3),
    "loan_app_type_home_mosaic_rev": ("subsection", 3),
    "loan_homeownership_pie_chart": ("subsection", 4),
    "countyIncomeSplitByPopGain": ("subsection", 5),
    "antibiotic_use_children_bar": ("exercise", 21),
    "antibiotic_use_children_pie": ("exercise", 21),
    "dream_act_mosaic": ("exercise", 23),
    "raise_taxes_mosaic": ("exercise", 24),
}


def rrecord(record_type: str, stable_key: str, **fields: Any) -> dict[str, Any]:
    fields["recorded_at"] = RECORDED_AT
    fields["workflow_id"] = WORKFLOW_ID
    return g.record(record_type, stable_key, **fields)


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def load_base_records() -> dict[str, list[dict[str, Any]]]:
    manifest_raw = (BASE_EXPORTS / "manifest.json").read_bytes()
    if g.sha256_bytes(manifest_raw) != BASE_MANIFEST_SHA256:
        raise RuntimeError("live backend is not the admitted R011-B005 base")
    manifest = json.loads(manifest_raw)
    if sum(manifest["record_counts"].values()) != BASE_RECORD_COUNT:
        raise RuntimeError("admitted R011-B005 record count changed")
    records: dict[str, list[dict[str, Any]]] = {}
    for name, relative_path in RECORD_PATHS.items():
        raw = (BASE_EXPORTS / relative_path).read_bytes()
        expected = BASE_RECORD_PAYLOAD_IDENTITIES[relative_path]
        if len(raw) != expected["bytes"] or g.sha256_bytes(raw) != expected["sha256"]:
            raise RuntimeError(f"admitted R011-B005 record payload changed: {relative_path}")
        rows = [json.loads(line) for line in raw.decode("utf-8").splitlines()]
        if len(rows) != expected["records"] or g.jsonl_bytes(rows) != raw:
            raise RuntimeError(f"admitted R011-B005 record payload is not canonical: {relative_path}")
        records[name] = rows
    return records


def base_auxiliary_payloads() -> dict[str, bytes]:
    manifest = json.loads((BASE_EXPORTS / "manifest.json").read_text(encoding="utf-8"))
    excluded = set(RECORD_PATHS.values()) | {"identity_map.jsonl", "manifest.json"}
    excluded.update(path for path in (entry["path"] for entry in manifest["files"]) if path.startswith("views/") or path.startswith("schemas/"))
    payloads: dict[str, bytes] = {}
    for entry in manifest["files"]:
        path = entry["path"]
        if path in excluded:
            continue
        raw = (BASE_EXPORTS / path).read_bytes()
        if len(raw) != entry["bytes"] or g.sha256_bytes(raw) != entry["sha256"]:
            raise RuntimeError(f"admitted R011-B005 auxiliary payload changed: {path}")
        payloads[path] = raw
    return payloads


def source_meta(root: Path, path: str, span: tuple[int, int] | None = None) -> dict[str, Any]:
    value = g.file_source(root, path) if span is None else g.source_slice(root, path, *span)
    value.pop("source_text", None)
    return value


def line_starts(root: Path, path: str, prefix: str) -> list[int]:
    return [
        index
        for index, line in enumerate((root / path).read_text(encoding="utf-8").splitlines(), 1)
        if line.startswith(prefix)
    ]


def file_identity(path: Path, relative: str | None = None) -> dict[str, Any]:
    raw = path.read_bytes()
    value = {"bytes": len(raw), "sha256": g.sha256_bytes(raw)}
    if relative is not None:
        value["path"] = relative
    return value


def check_fixed_identity(label: str, path: Path, expected: dict[str, Any]) -> bytes:
    raw = path.read_bytes()
    if len(raw) != expected["bytes"] or g.sha256_bytes(raw) != expected["sha256"]:
        raise RuntimeError(f"fixed B006 evidence identity changed: {label}")
    return raw


def selected_terminology_bytes(maximum: int = 141) -> bytes:
    lines = TERMINOLOGY_CONTROL.read_bytes().splitlines(keepends=True)
    chosen = [lines[0]]
    observed: list[str] = []
    for line in lines[1:]:
        term_id = next(csv.reader([line.decode("utf-8")]))[0]
        number = int(term_id.rsplit("-", 1)[1])
        if number <= maximum:
            chosen.append(line)
            observed.append(term_id)
    expected = [f"R011-TERM-{number:04d}" for number in range(1, maximum + 1)]
    if observed != expected:
        raise RuntimeError("terminology control is not the exact TERM-0001..0141 sequence")
    return b"".join(chosen)


def selected_adverse_bytes(maximum: int = 79) -> bytes:
    chosen: list[bytes] = []
    observed: list[str] = []
    for line in ADVERSE_CONTROL.read_bytes().splitlines(keepends=True):
        row = json.loads(line)
        number = int(row["id"].rsplit("-", 1)[1])
        if number <= maximum:
            chosen.append(line)
            observed.append(row["id"])
    expected = [f"R011-ADV-{number:04d}" for number in range(1, maximum + 1)]
    if observed != expected:
        raise RuntimeError("adverse control is not the exact ADV-0001..0079 sequence")
    return b"".join(chosen)


def path_from_identity(identity: dict[str, Any]) -> Path:
    relative = identity.get("path")
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise RuntimeError(f"final input path must be a bounded lane-relative path: {relative!r}")
    path = LANE / Path(relative)
    if not path.is_file():
        raise RuntimeError(f"required final input is missing: {relative}")
    return path


def load_final_inputs(path: Path) -> tuple[dict[str, Any], bytes, dict[str, bytes]]:
    raw = path.read_bytes()
    supplied = json.loads(raw)
    if (
        supplied.get("schema_version") != "r011-b006-final-gate-inputs/1.0.0"
        or supplied.get("boundary_id") != BOUNDARY_ID
        or supplied.get("status") != "supplied_exact_final_inputs"
    ):
        raise RuntimeError("invalid B006 exact-final-input manifest envelope")
    required = list(EXPECTED_FINAL_INPUTS)
    identities = supplied.get("inputs", {})
    if list(identities) != required:
        raise RuntimeError(f"exact-final-input manifest must contain exactly {required}")
    payloads: dict[str, bytes] = {}
    for label in required:
        identity = identities[label]
        path_value = path_from_identity(identity)
        item_raw = path_value.read_bytes()
        if len(item_raw) != identity.get("bytes") or g.sha256_bytes(item_raw) != identity.get("sha256"):
            raise RuntimeError(f"supplied final input identity does not match disk: {label}")
        payloads[label] = item_raw
    for label, expected in EXPECTED_FINAL_INPUTS.items():
        identity = identities[label]
        if identity.get("path") != expected["path"]:
            raise RuntimeError(f"supplied {label} must use the canonical final B006 path")
        if not isinstance(identity.get("bytes"), int) or identity["bytes"] <= 0:
            raise RuntimeError(f"supplied {label} must include a positive exact byte count")
        if re.fullmatch(r"[0-9a-f]{64}", str(identity.get("sha256", ""))) is None:
            raise RuntimeError(f"supplied {label} must include a lowercase SHA-256 identity")
        if identity != expected:
            raise RuntimeError(f"supplied {label} is not the canonical final V4 identity")
    return supplied, raw, payloads


def target_identities(source_root: Path) -> dict[str, Any]:
    source_section = g.section_range_by_label(source_root, BODY_PATH, "categoricalData")
    target_section = g.section_range_by_label(TARGET_ROOT, BODY_PATH, "categoricalData")
    source_answers = b005.answer_ranges(source_root, "Summarizing data")[1]
    target_answers = b005.answer_ranges(TARGET_ROOT, "Merangkum data")[1]
    source_section_raw = g.source_slice(source_root, BODY_PATH, *source_section)["source_text"].encode("utf-8")
    target_section_raw = g.source_slice(TARGET_ROOT, BODY_PATH, *target_section)["source_text"].encode("utf-8")
    source_answer_parts = [g.source_slice(source_root, ANSWER_PATH, *source_answers[number])["source_text"] for number in (21, 23)]
    target_answer_parts = [g.source_slice(TARGET_ROOT, ANSWER_PATH, *target_answers[number])["source_text"] for number in (21, 23)]
    source_answer_raw = "".join(source_answer_parts).encode("utf-8")
    target_answer_raw = "".join(target_answer_parts).encode("utf-8")
    observed = {
        "body": file_identity(TARGET_ROOT / BODY_PATH, f"repo/{BODY_PATH}"),
        "exercises": file_identity(TARGET_ROOT / EXERCISE_PATH, f"repo/{EXERCISE_PATH}"),
        "answers": file_identity(TARGET_ROOT / ANSWER_PATH, f"repo/{ANSWER_PATH}"),
        "translated_section": {"bytes": len(target_section_raw), "sha256": g.sha256_bytes(target_section_raw)},
        "translated_answers": {"bytes": len(target_answer_raw), "sha256": g.sha256_bytes(target_answer_raw)},
        "authority_section": {"bytes": len(source_section_raw), "sha256": g.sha256_bytes(source_section_raw)},
        "authority_answers": {"bytes": len(source_answer_raw), "sha256": g.sha256_bytes(source_answer_raw)},
        "source_section_range": source_section,
        "target_section_range": target_section,
        "source_answer_ranges": source_answers,
        "target_answer_ranges": target_answers,
    }
    for label, expected in EXPECTED_TARGET_SOURCE.items():
        if any(observed[label].get(key) != value for key, value in expected.items()):
            raise RuntimeError(f"accepted B006 target identity changed: {label}")
    if observed["authority_section"] != {"bytes": 42904, "sha256": "8090875754f2e3d18f563081b0d12fc3efc6da2bca3bf1db13166b88a1b42767"}:
        raise RuntimeError("pinned authority Section 2.2 identity changed")
    if observed["authority_answers"] != {"bytes": 626, "sha256": "22ead9b6125ceb8cae5dcbb5d872476744fdcdb601223ccfb564f1647dea6d4d"}:
        raise RuntimeError("pinned authority public-answer identity changed")
    return observed


def add_relation(
    records: dict[str, list[dict[str, Any]]],
    name: str,
    relation_type: str,
    from_id: str,
    to_id: str,
    qualifier: str = "",
    order: int = 0,
) -> None:
    records["relations"].append(
        rrecord(
            "relation",
            f"r011/relation/{name}",
            relation_type=relation_type,
            from_id=from_id,
            to_id=to_id,
            qualifier=qualifier,
            resource_id=g.stable_id("r011/resource/openintro-statistics"),
            edition_id=g.stable_id("r011/edition/fee25091"),
            source_local_ids=[BOUNDARY_ID],
            parent_id=None,
            order=order,
            source_path=None,
            source_span=None,
            source_sha256=None,
            locale="zxx",
            translation_state=None,
            rights_component_ids=[],
            boundary_id=BOUNDARY_ID,
        )
    )


def contains_identity(value: Any, identity: dict[str, Any], require_path: bool = True) -> bool:
    if isinstance(value, dict):
        same = value.get("bytes") == identity.get("bytes") and value.get("sha256") == identity.get("sha256")
        if same and (not require_path or value.get("path") == identity.get("path")):
            return True
        return any(contains_identity(item, identity, require_path) for item in value.values())
    if isinstance(value, list):
        return any(contains_identity(item, identity, require_path) for item in value)
    return False


def validate_final_gates(supplied: dict[str, Any], raws: dict[str, bytes]) -> dict[str, Any]:
    identities = supplied["inputs"]
    candidate = json.loads(raws["candidate_build_qa"])
    build = json.loads(raws["build_qa"])
    visual = json.loads(raws["visual_audit"])
    locator = json.loads(raws["page_locator"])
    render_lines = raws["render_manifest"].decode("utf-8").splitlines()
    zero_severity = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
    pdf_identity = identities["pdf"]
    render_identity = identities["render_manifest"]
    visual_identity = identities["visual_audit"]

    def core(identity: dict[str, Any]) -> dict[str, Any]:
        return {key: identity[key] for key in ("path", "bytes", "sha256")}

    render_rows: list[dict[str, Any]] = []
    render_root = Path(render_identity["path"]).parent
    for line in render_lines:
        fields = line.split("\t")
        if len(fields) != 4 or re.fullmatch(r"[0-9a-f]{64}", fields[3]) is None:
            raise RuntimeError("final V4 render manifest is not canonical page/name/bytes/SHA-256 TSV")
        page = int(fields[0])
        filename = fields[1]
        row = {
            "page": page,
            "path": (render_root / filename).as_posix(),
            "bytes": int(fields[2]),
            "sha256": fields[3],
        }
        if filename != f"page-{page:03d}.png":
            raise RuntimeError("final V4 render manifest page/name mapping changed")
        page_path = path_from_identity(row)
        page_raw = page_path.read_bytes()
        if len(page_raw) != row["bytes"] or g.sha256_bytes(page_raw) != row["sha256"]:
            raise RuntimeError(f"final V4 rendered page identity changed: {filename}")
        render_rows.append(row)
    if (
        [row["page"] for row in render_rows] != EXPECTED_VISUAL_PAGES
        or len(render_rows) != render_identity["page_count"]
        or locator.get("all_candidate_pages") != EXPECTED_VISUAL_PAGES
        or locator.get("mandatory_v4_audit_pages") != list(range(61, 74)) + [388, 389, 390]
        or locator.get("section_2_2_content_span") != [62, 71]
        or locator.get("exercise_2_21_through_2_24_span") != [70, 71]
        or locator.get("section_2_3_transition_page") != 72
    ):
        raise RuntimeError("final V4 page locator/render inventory is not the admitted 17-page sweep")

    source_receipt_identity = core(identities["source_qa"])
    target_manifest_identity = core(identities["target_manifest"])
    candidate_ok = (
        candidate.get("boundary_id") == BOUNDARY_ID
        and candidate.get("schema") == "openintro-boundary-build-candidate-qa"
        and candidate.get("schema_version") == "0.1.0"
        and candidate.get("status") == "pending_visual_review"
        and candidate.get("nonvisual_status") == "passed"
        and candidate.get("errors") == []
        and candidate.get("pending") == ["operator inspection of every full-resolution candidate PNG"]
        and candidate.get("gate_script") == core(identities["build_gate_script"])
        and candidate.get("build_files", {}).get("main.log") == core(identities["build_log"])
        and candidate.get("build_files", {}).get("main-final.txt") == core(identities["build_text"])
        and core(candidate.get("candidate_artifact", {})) == core(pdf_identity)
        and candidate.get("candidate_artifact", {}).get("promoted") is False
        and candidate.get("determinism", {}).get("byte_identical") is True
        and core(candidate.get("determinism", {}).get("pass_3", {})) == {
            "path": "qa/b006-build/final-v4/main-pass3.pdf",
            "bytes": pdf_identity["bytes"],
            "sha256": pdf_identity["sha256"],
        }
        and core(candidate.get("determinism", {}).get("pass_4", {})) == core(pdf_identity)
        and candidate.get("links_and_structure", {}).get("page_count") == pdf_identity["page_count"]
        and candidate.get("links_and_structure", {}).get("document_language") == "id-ID"
        and candidate.get("links_and_structure", {}).get("missing_link_targets") == 0
        and candidate.get("source_closure", {}).get("source_receipt") == source_receipt_identity
        and candidate.get("source_closure", {}).get("target_manifest") == target_manifest_identity
        and candidate.get("source_closure", {}).get("file_count") == EXPECTED_TARGET_CLOSURE["file_count"]
        and candidate.get("source_closure", {}).get("file_bytes") == EXPECTED_TARGET_CLOSURE["file_bytes"]
        and candidate.get("visual_evidence", {}).get("candidate_page_count") == len(EXPECTED_VISUAL_PAGES)
        and candidate.get("visual_evidence", {}).get("candidate_pages") == EXPECTED_VISUAL_PAGES
        and candidate.get("visual_evidence", {}).get("contact_sheet") == core(identities["contact_sheet"])
        and candidate.get("visual_evidence", {}).get("page_locator") == core(identities["page_locator"])
        and candidate.get("visual_evidence", {}).get("render_manifest") == core(render_identity)
        and candidate.get("visual_evidence", {}).get("pdf") == core(pdf_identity)
    )
    if not candidate_ok:
        raise RuntimeError("supplied V4 candidate build receipt does not prove the exact deterministic nonvisual closure")

    build_ok = (
        build.get("boundary_id") == BOUNDARY_ID
        and build.get("schema") == "openintro-boundary-build-final-qa"
        and build.get("schema_version") == "0.2.0"
        and build.get("status") == "passed"
        and build.get("nonvisual_status") == "passed"
        and build.get("errors") == []
        and build.get("pending") == []
        and build.get("gate_script") == core(identities["build_gate_script"])
        and build.get("finalization_script") == core(identities["visual_finalizer"])
        and build.get("candidate_history", {}).get("path") == identities["candidate_build_qa"]["path"]
        and build.get("candidate_history", {}).get("bytes") == identities["candidate_build_qa"]["bytes"]
        and build.get("candidate_history", {}).get("sha256") == identities["candidate_build_qa"]["sha256"]
        and build.get("candidate_history", {}).get("preserved_unchanged") is True
        and build.get("determinism", {}).get("byte_identical") is True
        and build.get("build_files", {}).get("main.log") == core(identities["build_log"])
        and build.get("build_files", {}).get("main-final.txt") == core(identities["build_text"])
        and core(build.get("candidate_artifact", {})) == core(pdf_identity)
        and build.get("candidate_artifact", {}).get("promoted") is False
        and build.get("links_and_structure", {}).get("page_count") == pdf_identity["page_count"]
        and build.get("links_and_structure", {}).get("document_language") == "id-ID"
        and build.get("links_and_structure", {}).get("missing_link_targets") == 0
        and build.get("source_closure", {}).get("source_receipt") == source_receipt_identity
        and build.get("source_closure", {}).get("target_manifest") == target_manifest_identity
        and build.get("source_closure", {}).get("file_count") == EXPECTED_TARGET_CLOSURE["file_count"]
        and build.get("source_closure", {}).get("file_bytes") == EXPECTED_TARGET_CLOSURE["file_bytes"]
        and build.get("build_visual_admission", {}).get("status") == "passed"
        and build.get("build_visual_admission", {}).get("nonvisual_status") == "passed"
        and build.get("build_visual_admission", {}).get("visual_status") == "passed"
        and build.get("build_visual_admission", {}).get("candidate_pdf_promoted") is False
        and build.get("build_visual_admission", {}).get("source_or_backend_mutated") is False
        and build.get("visual_evidence", {}).get("status") == "passed_operator_inspection"
        and build.get("visual_evidence", {}).get("candidate_page_count") == len(EXPECTED_VISUAL_PAGES)
        and build.get("visual_evidence", {}).get("candidate_pages") == EXPECTED_VISUAL_PAGES
        and build.get("visual_evidence", {}).get("contact_sheet") == core(identities["contact_sheet"])
        and build.get("visual_evidence", {}).get("page_locator") == core(identities["page_locator"])
        and build.get("visual_evidence", {}).get("render_manifest") == core(render_identity)
        and build.get("visual_evidence", {}).get("pdf") == core(pdf_identity)
        and build.get("visual_evidence", {}).get("visual_audit") == core(visual_identity)
    )
    if not build_ok:
        raise RuntimeError("supplied V4 final build receipt does not prove the exact deterministic build/visual closure")

    visual_rows = visual.get("evidence", {}).get("individual_page_renders", [])
    visual_ok = (
        visual.get("boundary_id") == BOUNDARY_ID
        and visual.get("candidate") == "final-v4"
        and visual.get("schema") == "openintro-boundary-visual-audit"
        and visual.get("schema_version") == "0.2.0"
        and visual.get("status") == "passed"
        and visual.get("candidate_build_receipt") == core(identities["candidate_build_qa"])
        and visual.get("finalization_script") == core(identities["visual_finalizer"])
        and visual.get("severity_counts") == zero_severity
        and visual.get("findings") == []
        and set(visual.get("checks", {}).values()) == {"passed"}
        and visual.get("promotion", {}).get("performed") is False
        and visual.get("parent_acceptance", {}).get("all_required_pages_inspected") is True
        and visual.get("parent_acceptance", {}).get("inspected_page_count") == len(EXPECTED_VISUAL_PAGES)
        and visual.get("parent_acceptance", {}).get("inspected_pages") == EXPECTED_VISUAL_PAGES
        and core(visual.get("evidence", {}).get("candidate_pdf", {})) == core(pdf_identity)
        and visual.get("evidence", {}).get("candidate_pdf", {}).get("pages") == pdf_identity["page_count"]
        and visual.get("evidence", {}).get("contact_sheet") == core(identities["contact_sheet"])
        and visual.get("evidence", {}).get("page_locator") == core(identities["page_locator"])
        and visual.get("evidence", {}).get("render_manifest") == core(render_identity)
        and visual.get("evidence", {}).get("individual_page_render_count") == len(EXPECTED_VISUAL_PAGES)
        and visual.get("evidence", {}).get("individual_page_render_bytes") == sum(row["bytes"] for row in render_rows)
        and visual_rows == render_rows
    )
    if not visual_ok:
        raise RuntimeError("supplied V4 visual audit does not prove the exact zero-severity 17-page sweep")
    return {
        "candidate": candidate,
        "build": build,
        "visual": visual,
        "rendered_page_count": len(render_lines),
        "severity_counts": zero_severity,
        "inspected_pages": EXPECTED_VISUAL_PAGES,
        "candidate_pdf_promoted": False,
    }


def build_records(final_inputs_path: Path) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    records = load_base_records()
    authority, source_root = g.read_authority()
    if authority["commit"] != EXPECTED_AUTHORITY["commit"] or authority["calculated_git_tree_sha1"] != EXPECTED_AUTHORITY["tree"]:
        raise RuntimeError("pinned authority identity changed")
    with g.AUTHORITY_MANIFEST_PATH.open("r", encoding="utf-8", newline="") as handle:
        source_rows = list(csv.DictReader(handle))
    source_by_path = {row["path"]: row for row in source_rows}
    identities = target_identities(source_root)
    supplied, supplied_raw, final_raws = load_final_inputs(final_inputs_path)
    supplied_identities = supplied["inputs"]
    final_gate = validate_final_gates(supplied, final_raws)

    fixed_raws = {
        "preapplication": check_fixed_identity("preapplication", PREAPPLICATION_MANIFEST, EXPECTED_FIXED_EVIDENCE["preapplication"]),
        "source_application": check_fixed_identity("source_application", SOURCE_APPLICATION_RECEIPT, EXPECTED_FIXED_EVIDENCE["source_application"]),
        "repair_receipt": check_fixed_identity("repair_receipt", REPAIR_RECEIPT, EXPECTED_FIXED_EVIDENCE["repair_receipt"]),
        "layout_repair_receipt": check_fixed_identity("layout_repair_receipt", LAYOUT_REPAIR_RECEIPT, EXPECTED_FIXED_EVIDENCE["layout_repair_receipt"]),
        "layout_repair_receipt_v4": check_fixed_identity("layout_repair_receipt_v4", LAYOUT_REPAIR_RECEIPT_V4, EXPECTED_FIXED_EVIDENCE["layout_repair_receipt_v4"]),
        "rejected_build_receipt_v1": check_fixed_identity("rejected_build_receipt_v1", REJECTED_BUILD_RECEIPT_V1, EXPECTED_FIXED_EVIDENCE["rejected_build_receipt_v1"]),
        "rejected_visual_findings_v1": check_fixed_identity("rejected_visual_findings_v1", REJECTED_VISUAL_FINDINGS_V1, EXPECTED_FIXED_EVIDENCE["rejected_visual_findings_v1"]),
        "rejected_build_receipt_v2": check_fixed_identity("rejected_build_receipt_v2", REJECTED_BUILD_RECEIPT_V2, EXPECTED_FIXED_EVIDENCE["rejected_build_receipt_v2"]),
        "rejected_visual_findings_v2": check_fixed_identity("rejected_visual_findings_v2", REJECTED_VISUAL_FINDINGS_V2, EXPECTED_FIXED_EVIDENCE["rejected_visual_findings_v2"]),
        "rejected_build_receipt_v3": check_fixed_identity("rejected_build_receipt_v3", REJECTED_BUILD_RECEIPT_V3, EXPECTED_FIXED_EVIDENCE["rejected_build_receipt_v3"]),
        "rejected_visual_findings_v3": check_fixed_identity("rejected_visual_findings_v3", REJECTED_VISUAL_FINDINGS_V3, EXPECTED_FIXED_EVIDENCE["rejected_visual_findings_v3"]),
        "asset_manifest": check_fixed_identity("asset_manifest", ASSET_MANIFEST, EXPECTED_FIXED_EVIDENCE["asset_manifest"]),
        "asset_receipt": check_fixed_identity("asset_receipt", ASSET_RECEIPT, EXPECTED_FIXED_EVIDENCE["asset_receipt"]),
        "poppler_contact_sheet": check_fixed_identity("poppler_contact_sheet", POPPLER_CONTACT_SHEET, EXPECTED_FIXED_EVIDENCE["poppler_contact_sheet"]),
        "mupdf_contact_sheet": check_fixed_identity("mupdf_contact_sheet", MUPDF_CONTACT_SHEET, EXPECTED_FIXED_EVIDENCE["mupdf_contact_sheet"]),
        "localizer": check_fixed_identity("localizer", LOCALIZER, EXPECTED_FIXED_EVIDENCE["localizer"]),
        "terminology": check_fixed_identity("terminology", TERMINOLOGY_CONTROL, EXPECTED_FIXED_EVIDENCE["terminology"]),
        "adverse": check_fixed_identity("adverse", ADVERSE_CONTROL, EXPECTED_FIXED_EVIDENCE["adverse"]),
        "rights": check_fixed_identity("rights", RIGHTS_CONTROL, EXPECTED_FIXED_EVIDENCE["rights"]),
    }
    source_qa = json.loads(final_raws["source_qa"])
    source_manifest_lines = final_raws["target_manifest"].decode("utf-8").splitlines()
    source_manifest_rows: list[tuple[str, int, str]] = []
    for line in source_manifest_lines:
        fields = line.split("\t")
        if len(fields) != 3 or not fields[0] or re.fullmatch(r"[0-9a-f]{64}", fields[2]) is None:
            raise RuntimeError("supplied B006 target manifest is not a canonical path/bytes/SHA-256 TSV")
        source_manifest_rows.append((fields[0], int(fields[1]), fields[2]))
    source_manifest_bytes = sum(row[1] for row in source_manifest_rows)
    if [row[0] for row in source_manifest_rows] != sorted(row[0] for row in source_manifest_rows) or len({row[0] for row in source_manifest_rows}) != len(source_manifest_rows):
        raise RuntimeError("supplied B006 target manifest paths are not sorted and unique")
    manifest_identity = supplied_identities["target_manifest"]
    receipt_manifest_identity = source_qa.get("target_closure", {}).get("manifest", {})
    source_scope = source_qa.get("scope", {}).get("source", {})
    expected_source_files = {
        "body": EXPECTED_TARGET_SOURCE["body"],
        "exercises": EXPECTED_TARGET_SOURCE["exercises"],
        "public_answer_file": EXPECTED_TARGET_SOURCE["answers"],
    }
    repair_receipt = json.loads(fixed_raws["repair_receipt"])
    layout_repair_receipt = json.loads(fixed_raws["layout_repair_receipt"])
    layout_repair_receipt_v4 = json.loads(fixed_raws["layout_repair_receipt_v4"])
    final_layout_outputs = {
        item.get("path"): {"bytes": item.get("bytes"), "sha256": item.get("sha256")}
        for item in layout_repair_receipt_v4.get("final_canonical_outputs", [])
    }
    repair_handoff = source_scope.get("post_build_repair_handoff", {})
    reverse_operations = repair_handoff.get("reverse_operations", [])
    layout_handoff = source_scope.get("v3_layout_repair_handoff", {})
    layout_reverse_operations = layout_handoff.get("reverse_operations", [])
    layout_handoff_v4 = source_scope.get("v4_layout_repair_handoff", {})
    layout_reverse_operations_v4 = layout_handoff_v4.get("reverse_operations", [])
    if (
        source_qa.get("boundary_id") != BOUNDARY_ID
        or source_qa.get("status") != "passed"
        or source_qa.get("authority", {}).get("commit") != EXPECTED_AUTHORITY["commit"]
        or source_qa.get("authority", {}).get("tree") != EXPECTED_AUTHORITY["tree"]
        or source_qa.get("checks", {}).get("placeholders") != 0
        or source_qa.get("checks", {}).get("active_reader_visible_english") != 0
        or source_qa.get("checks", {}).get("manifest_delta_recomputed") is not True
        or source_qa.get("checks", {}).get("post_build_repairs_reverse_reconstructed") != "passed"
        or source_qa.get("checks", {}).get("post_build_repair_topology_and_display") != "passed"
        or source_qa.get("checks", {}).get("v3_layout_repairs_reverse_reconstructed") != "passed"
        or source_qa.get("checks", {}).get("v4_layout_repair_reverse_reconstructed") != "passed"
        or source_qa.get("checks", {}).get("prior_v3_layout_repair_receipt") != EXPECTED_FIXED_EVIDENCE["layout_repair_receipt"]
        or source_qa.get("checks", {}).get("v4_layout_repair_receipt") != EXPECTED_FIXED_EVIDENCE["layout_repair_receipt_v4"]
        or source_qa.get("checks", {}).get("rejected_v1_visual_findings_bound") != "passed"
        or source_qa.get("checks", {}).get("rejected_v2_visual_findings_bound") != "passed"
        or source_qa.get("checks", {}).get("rejected_v3_visual_findings_bound") != "passed"
        or source_qa.get("gate_script") != EXPECTED_SOURCE_GATE["gate_script"]
        or file_identity(LANE / EXPECTED_SOURCE_GATE["gate_script"]["path"], EXPECTED_SOURCE_GATE["gate_script"]["path"]) != EXPECTED_SOURCE_GATE["gate_script"]
        or receipt_manifest_identity != {
            "path": manifest_identity["path"],
            "bytes": manifest_identity["bytes"],
            "sha256": manifest_identity["sha256"],
        }
        or any(source_scope.get(key) != {"path": f"repo/{BODY_PATH if key == 'body' else EXERCISE_PATH if key == 'exercises' else ANSWER_PATH}", **value} for key, value in expected_source_files.items())
        or source_scope.get("o001", {}).get("exercise_numbers") != ["2.21", "2.22", "2.23", "2.24"]
        or source_scope.get("o001", {}).get("public_answers") != ["2.21", "2.23"]
        or source_scope.get("o001", {}).get("o001_gaps") != ["2.22", "2.24"]
        or source_scope.get("o001", {}).get("restricted_instructor_solutions_accessed_or_invented") is not False
        or repair_handoff.get("status") != "passed"
        or repair_handoff.get("repair_receipt") != EXPECTED_FIXED_EVIDENCE["repair_receipt"]
        or repair_handoff.get("rejected_build_v1_receipt") != EXPECTED_FIXED_EVIDENCE["rejected_build_receipt_v1"]
        or repair_handoff.get("visual_findings_v1_receipt") != EXPECTED_FIXED_EVIDENCE["rejected_visual_findings_v1"]
        or repair_handoff.get("exact_substitution_count") != 17
        or repair_handoff.get("repair_group_count") != 7
        or repair_handoff.get("all_pre_repair_outputs_reconstructed_byte_exact") is not True
        or len(reverse_operations) != 17
        or any(item.get("expected_occurrences") != 1 or item.get("observed_occurrences_during_reverse") != 1 for item in reverse_operations)
        or layout_handoff.get("status") != "passed"
        or layout_handoff.get("layout_repair_receipt_v3") != EXPECTED_FIXED_EVIDENCE["layout_repair_receipt"]
        or layout_handoff.get("rejected_build_v2_receipt") != EXPECTED_FIXED_EVIDENCE["rejected_build_receipt_v2"]
        or layout_handoff.get("visual_findings_v2_receipt") != EXPECTED_FIXED_EVIDENCE["rejected_visual_findings_v2"]
        or layout_handoff.get("exact_substitution_count") != 3
        or layout_handoff.get("adverse_ids") != ["R011-ADV-0077", "R011-ADV-0078"]
        or layout_handoff.get("all_v2_outputs_reconstructed_byte_exact") is not True
        or len(layout_reverse_operations) != 3
        or any(
            item.get("final_after_occurrences") != 1
            or item.get("final_before_occurrences") != 0
            or item.get("observed_occurrences_during_reverse") != 1
            or item.get("pre_after_occurrences") != 0
            or item.get("pre_before_occurrences") != 1
            for item in layout_reverse_operations
        )
        or layout_handoff_v4.get("status") != "passed"
        or layout_handoff_v4.get("layout_repair_receipt") != EXPECTED_FIXED_EVIDENCE["layout_repair_receipt_v4"]
        or layout_handoff_v4.get("prior_layout_repair_receipt_v3") != EXPECTED_FIXED_EVIDENCE["layout_repair_receipt"]
        or layout_handoff_v4.get("rejected_build_v3_receipt") != EXPECTED_FIXED_EVIDENCE["rejected_build_receipt_v3"]
        or layout_handoff_v4.get("visual_findings_v3_receipt") != EXPECTED_FIXED_EVIDENCE["rejected_visual_findings_v3"]
        or layout_handoff_v4.get("exact_substitution_count") != 1
        or layout_handoff_v4.get("adverse_ids") != ["R011-ADV-0079"]
        or layout_handoff_v4.get("all_v3_outputs_reconstructed_byte_exact") is not True
        or len(layout_reverse_operations_v4) != 1
        or any(
            item.get("final_after_occurrences") != 1
            or item.get("final_before_occurrences") != 0
            or item.get("observed_occurrences_during_reverse") != 1
            or item.get("pre_after_occurrences") != 0
            or item.get("pre_before_occurrences") != 1
            for item in layout_reverse_operations_v4
        )
        or len(source_manifest_lines) != EXPECTED_TARGET_CLOSURE["file_count"]
        or source_manifest_bytes != EXPECTED_TARGET_CLOSURE["file_bytes"]
        or source_qa.get("target_closure", {}).get("target_file_count") != EXPECTED_TARGET_CLOSURE["file_count"]
        or source_qa.get("target_closure", {}).get("target_file_bytes") != EXPECTED_TARGET_CLOSURE["file_bytes"]
        or repair_receipt.get("status") != "repair_applied_and_reverse_verified"
        or repair_receipt.get("reverse_reconstruction", {}).get("all_outputs_match_pre_repair_identities") is not True
        or layout_repair_receipt.get("status") != "layout_repairs_applied_and_reverse_verified"
        or layout_repair_receipt.get("reverse_reconstruction", {}).get("all_outputs_match_source_snapshot_v2_identities") is not True
        or layout_repair_receipt.get("layout_repairs", {}).get("substitution_count") != 3
        or layout_repair_receipt.get("layout_repairs", {}).get("repair_group_count") != 2
        or layout_repair_receipt.get("layout_only_invariants", {}).get("status") != "passed"
        or layout_repair_receipt_v4.get("status") != "layout_repairs_applied_and_reverse_verified"
        or layout_repair_receipt_v4.get("reverse_reconstruction", {}).get("all_outputs_match_source_snapshot_v3_identities") is not True
        or layout_repair_receipt_v4.get("layout_repairs", {}).get("substitution_count") != 1
        or layout_repair_receipt_v4.get("layout_repairs", {}).get("repair_group_count") != 1
        or layout_repair_receipt_v4.get("layout_only_invariants", {}).get("status") != "passed"
        or final_layout_outputs != {
            expected["path"]: {"bytes": expected["bytes"], "sha256": expected["sha256"]}
            for expected in EXPECTED_TARGET_SOURCE.values()
            if "path" in expected
        }
    ):
        raise RuntimeError("supplied B006 source gate does not prove the repaired exact closure")
    for relative, size, digest in source_manifest_rows:
        live = TARGET_ROOT / relative
        if not live.is_file() or live.stat().st_size != size or g.sha256_file(live) != digest:
            raise RuntimeError(f"supplied B006 target manifest does not replay the live repaired file: {relative}")

    asset_manifest = json.loads(fixed_raws["asset_manifest"])
    asset_receipt = json.loads(fixed_raws["asset_receipt"])
    if (
        asset_manifest.get("boundary_id") != BOUNDARY_ID
        or asset_manifest.get("status") != "pass"
        or len(asset_manifest.get("assets", [])) != 13
        or asset_receipt.get("boundary_id") != BOUNDARY_ID
        or asset_receipt.get("status") != "pass"
        or asset_receipt.get("errors") != []
        or asset_receipt.get("blockers") != []
        or asset_receipt.get("counts", {}).get("assets") != 13
        or asset_receipt.get("counts", {}).get("source_witnesses") != 13
        or asset_receipt.get("counts", {}).get("same_renderer_poppler_pairs") != 13
        or asset_receipt.get("counts", {}).get("same_renderer_mupdf_pairs") != 13
        or asset_receipt.get("counts", {}).get("replay_identical_assets") != 13
        or asset_receipt.get("asset_subgate_admission_ready") is not True
    ):
        raise RuntimeError("B006 asset manifest/receipt no longer prove the final 13-asset PASS")

    resource_id = g.stable_id("r011/resource/openintro-statistics")
    edition_id = g.stable_id("r011/edition/fee25091")
    chapter_id = g.stable_id("r011/unit/source-label/ch_summarizing_data")
    default_rights_id = g.stable_id("r011/rights/upstream-cc-by-sa-3.0")
    o001_rights_id = g.stable_id("r011/rights/o001-original-companion-planned")
    package_rights_id = g.stable_id("r011/rights/openintro-r-package-gpl-3")
    county_rights_id = g.stable_id("r011/rights/county-complete-gpl-3-and-us-federal-data")
    generated_rights_key = "r011/rights/b006-generated-figure-expression"
    generated_rights_id = g.stable_id(generated_rights_key)
    data_rights_key = "r011/rights/b006-factual-data-and-build-inputs"
    data_rights_id = g.stable_id(data_rights_key)

    source_section = identities["source_section_range"]
    target_section = identities["target_section_range"]
    source_substarts = [line for line in line_starts(source_root, BODY_PATH, r"\subsection{") if source_section[0] <= line <= source_section[1]]
    target_substarts = [line for line in line_starts(TARGET_ROOT, BODY_PATH, r"\subsection{") if target_section[0] <= line <= target_section[1]]
    if len(source_substarts) != 6 or len(target_substarts) != 6:
        raise RuntimeError("Section 2.2 subsection topology changed")
    source_subranges = [
        (start, source_substarts[index + 1] - 1 if index + 1 < 6 else source_section[1])
        for index, start in enumerate(source_substarts)
    ]
    target_subranges = [
        (start, target_substarts[index + 1] - 1 if index + 1 < 6 else target_section[1])
        for index, start in enumerate(target_substarts)
    ]

    section_key = "r011/unit/source-label/categoricalData"
    section_id = g.stable_id(section_key)
    records["units"].append(
        rrecord(
            "unit",
            section_key,
            unit_type="section",
            title="Considering categorical data",
            resource_id=resource_id,
            edition_id=edition_id,
            source_local_ids=["categoricalData", BOUNDARY_ID],
            parent_id=chapter_id,
            order=3,
            locale="en",
            translation_state="source_frozen",
            rights_component_ids=[default_rights_id],
            boundary_id=BOUNDARY_ID,
            **source_meta(source_root, BODY_PATH, source_section),
        )
    )

    subsection_ids: list[str] = []
    subsection_keys: list[str] = []
    for index, ((slug, title, labels), span) in enumerate(zip(SUBSECTION_SPECS, source_subranges), 1):
        key = f"r011/unit/source-label/{slug}" if labels else f"r011/unit/ch02/sec2.2/{slug}"
        subsection_keys.append(key)
        subsection_ids.append(g.stable_id(key))
        records["units"].append(
            rrecord(
                "unit",
                key,
                unit_type="subsection",
                title=title,
                resource_id=resource_id,
                edition_id=edition_id,
                source_local_ids=[*labels, f"sec2.2-subsection-{index}", BOUNDARY_ID],
                parent_id=section_id,
                order=index,
                locale="en",
                translation_state="source_frozen",
                rights_component_ids=[default_rights_id],
                boundary_id=BOUNDARY_ID,
                **source_meta(source_root, BODY_PATH, span),
            )
        )

    source_guided = [
        span for span in b005.block_ranges(source_root, BODY_PATH, r"\begin{nexercise}", r"\end{nexercise}")
        if source_section[0] <= span[0] <= source_section[1]
    ]
    target_guided = [
        span for span in b005.block_ranges(TARGET_ROOT, BODY_PATH, r"\begin{nexercise}", r"\end{nexercise}")
        if target_section[0] <= span[0] <= target_section[1]
    ]
    if len(source_guided) != 4 or len(target_guided) != 4:
        raise RuntimeError("Section 2.2 guided-exercise topology changed")
    guided_ids: list[str] = []
    guided_parent_indices: list[int] = []
    for number, span in enumerate(source_guided, 1):
        parent_index = next(index for index, subspan in enumerate(source_subranges) if subspan[0] <= span[0] <= subspan[1])
        guided_parent_indices.append(parent_index)
        key = f"r011/unit/guided-exercise/ch02-sec2.2-{number:02d}"
        guided_ids.append(g.stable_id(key))
        records["units"].append(
            rrecord(
                "unit",
                key,
                unit_type="guided_exercise",
                title=f"Section 2.2 guided exercise {number}",
                resource_id=resource_id,
                edition_id=edition_id,
                source_local_ids=[f"nexercise-2.2-{number:02d}", BOUNDARY_ID],
                parent_id=subsection_ids[parent_index],
                order=number,
                locale="en",
                translation_state="source_frozen",
                rights_component_ids=[default_rights_id],
                answer_availability="public_inline",
                boundary_id=BOUNDARY_ID,
                **source_meta(source_root, BODY_PATH, span),
            )
        )

    review_key = "r011/unit/ch02/sec2.2/exercises"
    review_id = g.stable_id(review_key)
    records["units"].append(
        rrecord(
            "unit",
            review_key,
            unit_type="section_review",
            title="Section 2.2 exercises",
            resource_id=resource_id,
            edition_id=edition_id,
            source_local_ids=["considering_categorical_data", BOUNDARY_ID],
            parent_id=section_id,
            order=7,
            locale="en",
            translation_state="source_frozen",
            rights_component_ids=[default_rights_id],
            boundary_id=BOUNDARY_ID,
            **source_meta(source_root, EXERCISE_PATH),
        )
    )
    source_exercises = b005.exercise_ranges(source_root, EXERCISE_PATH)
    target_exercises = b005.exercise_ranges(TARGET_ROOT, EXERCISE_PATH)
    if len(source_exercises) != 4 or len(target_exercises) != 4:
        raise RuntimeError("Section 2.2 end-of-section exercise topology changed")

    exercise_ids: dict[int, str] = {}
    answer_ids: dict[int, str] = {}
    gap_ids: dict[int, str] = {}
    for offset, (number, label, title) in enumerate(EXERCISE_SPECS):
        key = f"r011/unit/exercise/2.{number}/{label}"
        exercise_ids[number] = g.stable_id(key)
        has_answer = number in {21, 23}
        records["units"].append(
            rrecord(
                "unit",
                key,
                unit_type="exercise",
                title=f"Exercise 2.{number}: {title}",
                resource_id=resource_id,
                edition_id=edition_id,
                source_local_ids=[label, f"eoce_2_{number}", BOUNDARY_ID],
                parent_id=review_id,
                order=number,
                locale="en",
                translation_state="source_frozen",
                rights_component_ids=[default_rights_id],
                answer_availability="public_appendix" if has_answer else "none_public_upstream",
                boundary_id=BOUNDARY_ID,
                **source_meta(source_root, EXERCISE_PATH, source_exercises[offset]),
            )
        )
        if has_answer:
            answer_key = f"r011/unit/solution/2.{number}"
            answer_ids[number] = g.stable_id(answer_key)
            records["units"].append(
                rrecord(
                    "unit",
                    answer_key,
                    unit_type="solution",
                    title=f"Public solution to exercise 2.{number}",
                    resource_id=resource_id,
                    edition_id=edition_id,
                    source_local_ids=[f"% {number}", f"eoce_sol_2_{number}", BOUNDARY_ID],
                    parent_id=exercise_ids[number],
                    order=1,
                    locale="en",
                    translation_state="source_frozen",
                    rights_component_ids=[default_rights_id],
                    answer_role="public_appendix",
                    answer_availability="public_appendix",
                    boundary_id=BOUNDARY_ID,
                    **source_meta(source_root, ANSWER_PATH, identities["source_answer_ranges"][number]),
                )
            )
        else:
            gap_key = f"r011/unit/o001-gap/2.{number}"
            gap_ids[number] = g.stable_id(gap_key)
            records["units"].append(
                rrecord(
                    "unit",
                    gap_key,
                    unit_type="companion_gap",
                    title=f"O001 mastery-companion answer gap for exercise 2.{number}",
                    resource_id=resource_id,
                    edition_id=edition_id,
                    source_local_ids=["O001", f"R011-O001-B006-E{number}", f"eoce_2_{number}", BOUNDARY_ID],
                    parent_id=exercise_ids[number],
                    order=1,
                    source_path=None,
                    source_span=None,
                    source_sha256=None,
                    locale="en",
                    translation_state="queued",
                    rights_component_ids=[o001_rights_id],
                    answer_availability="none_public_upstream",
                    authoring_mode="independent_original_required",
                    source_solution_used=False,
                    gap_reason="no_public_answer_upstream",
                    boundary_id=BOUNDARY_ID,
                    status="planned",
                )
            )

    segment_specs: list[dict[str, Any]] = [
        {
            "unit_key": section_key,
            "kind": "section_lead",
            "path": BODY_PATH,
            "source": (source_section[0], source_subranges[0][0] - 1),
            "target": (target_section[0], target_subranges[0][0] - 1),
            "order": 1,
        }
    ]
    for sub_index, (source_subspan, target_subspan) in enumerate(zip(source_subranges, target_subranges)):
        source_blocks = [(span, idx) for idx, span in enumerate(source_guided) if source_subspan[0] <= span[0] <= source_subspan[1]]
        target_blocks = [(span, idx) for idx, span in enumerate(target_guided) if target_subspan[0] <= span[0] <= target_subspan[1]]
        if [idx for _, idx in source_blocks] != [idx for _, idx in target_blocks]:
            raise RuntimeError(f"guided-exercise alignment changed in Section 2.2 subsection {sub_index + 1}")
        source_cursor = source_subspan[0]
        target_cursor = target_subspan[0]
        prose_order = 1
        for (source_block, guided_index), (target_block, _) in zip(source_blocks, target_blocks):
            if source_cursor <= source_block[0] - 1 or target_cursor <= target_block[0] - 1:
                if not (source_cursor <= source_block[0] - 1 and target_cursor <= target_block[0] - 1):
                    raise RuntimeError("source/target Section 2.2 prose topology diverged")
                segment_specs.append(
                    {
                        "unit_key": subsection_keys[sub_index],
                        "kind": "subsection_prose",
                        "path": BODY_PATH,
                        "source": (source_cursor, source_block[0] - 1),
                        "target": (target_cursor, target_block[0] - 1),
                        "order": prose_order,
                    }
                )
                prose_order += 1
            segment_specs.append(
                {
                    "unit_key": f"r011/unit/guided-exercise/ch02-sec2.2-{guided_index + 1:02d}",
                    "kind": "guided_exercise",
                    "path": BODY_PATH,
                    "source": source_block,
                    "target": target_block,
                    "order": 1,
                }
            )
            source_cursor = source_block[1] + 1
            target_cursor = target_block[1] + 1
        if source_cursor <= source_subspan[1] or target_cursor <= target_subspan[1]:
            if not (source_cursor <= source_subspan[1] and target_cursor <= target_subspan[1]):
                raise RuntimeError("source/target Section 2.2 subsection tail diverged")
            segment_specs.append(
                {
                    "unit_key": subsection_keys[sub_index],
                    "kind": "subsection_prose",
                    "path": BODY_PATH,
                    "source": (source_cursor, source_subspan[1]),
                    "target": (target_cursor, target_subspan[1]),
                    "order": prose_order,
                }
            )
    for offset, (number, label, _title) in enumerate(EXERCISE_SPECS):
        segment_specs.append(
            {
                "unit_key": f"r011/unit/exercise/2.{number}/{label}",
                "kind": "exercise",
                "path": EXERCISE_PATH,
                "source": source_exercises[offset],
                "target": target_exercises[offset],
                "order": 1,
            }
        )
    for number in (21, 23):
        segment_specs.append(
            {
                "unit_key": f"r011/unit/solution/2.{number}",
                "kind": "public_appendix_solution",
                "path": ANSWER_PATH,
                "source": identities["source_answer_ranges"][number],
                "target": identities["target_answer_ranges"][number],
                "order": 1,
            }
        )

    target_file_hashes = {
        BODY_PATH: identities["body"]["sha256"],
        EXERCISE_PATH: identities["exercises"]["sha256"],
        ANSWER_PATH: identities["answers"]["sha256"],
    }
    segment_ids: list[str] = []
    for offset, spec in enumerate(segment_specs, 152):
        code = f"seg{offset:04d}"
        source = g.source_slice(source_root, spec["path"], *spec["source"])
        target = g.source_slice(TARGET_ROOT, spec["path"], *spec["target"])
        source_tokens = g.protected_tokens(source["source_text"])
        target_tokens = g.protected_tokens(target["source_text"])
        source_counts = Counter(source_tokens)
        target_counts = Counter(target_tokens)
        removed = list((source_counts - target_counts).elements())
        added = list((target_counts - source_counts).elements())
        segment_key = f"r011/segment/{code}"
        segment_id = g.stable_id(segment_key)
        segment_ids.append(segment_id)
        unit_id = g.stable_id(spec["unit_key"])
        records["segments"].append(
            rrecord(
                "segment",
                segment_key,
                segment_kind=spec["kind"],
                unit_id=unit_id,
                resource_id=resource_id,
                edition_id=edition_id,
                source_local_ids=[BOUNDARY_ID],
                parent_id=unit_id,
                order=spec["order"],
                locale="en",
                source_locale="en",
                target_locales=["id-ID"],
                translation_state="source_frozen",
                rights_component_ids=[default_rights_id],
                boundary_id=BOUNDARY_ID,
                source_path=spec["path"],
                source_span=source["source_span"],
                source_sha256=source["source_sha256"],
                source_text=source["source_text"],
                protected_tokens=source_tokens,
            )
        )
        records["localizations"].append(
            rrecord(
                "localization",
                f"r011/localization/id-ID/{code}",
                source_segment_id=segment_id,
                unit_id=unit_id,
                resource_id=resource_id,
                edition_id=edition_id,
                source_local_ids=[BOUNDARY_ID],
                parent_id=segment_id,
                order=1,
                source_path=spec["path"],
                target_path=f"repo/{spec['path']}",
                source_span=source["source_span"],
                source_sha256=source["source_sha256"],
                target_span=target["source_span"],
                target_sha256=target["source_sha256"],
                target_file_sha256=target_file_hashes[spec["path"]],
                target_identity_status="source_gate_passed",
                locale="id-ID",
                source_locale="en",
                target_locale="id-ID",
                translation_state="translated",
                rights_component_ids=[default_rights_id],
                target_text=target["source_text"],
                protected_tokens=source_tokens,
                source_protected_tokens=source_tokens,
                target_protected_tokens=target_tokens,
                protected_token_delta={
                    "removed": removed,
                    "added": added,
                    "authorized": bool(removed or added),
                    "reason": "R011-B006 translation, one of SC-B006-001..005, accessibility-label alignment, or reader-facing localization." if (removed or added) else None,
                },
                excluded_asset_ids=[],
                translation_provenance="Direct English-to-id-ID translation by Codex acting on Floris's request.",
                boundary_id=BOUNDARY_ID,
            )
        )

    term_bytes = selected_terminology_bytes()
    term_rows = list(csv.DictReader(io.StringIO(term_bytes.decode("utf-8"), newline="")))
    b006_terms = [row for row in term_rows if 122 <= int(row["term_id"].rsplit("-", 1)[1]) <= 141]
    if len(b006_terms) != 20 or [row["source_term"] for row in b006_terms] != list(TERM_DEFINITIONS):
        raise RuntimeError("B006 terminology selection/order changed")
    concept_ids: dict[str, str] = {}
    body_source_sha = source_by_path[BODY_PATH]["sha256"]
    for row in b006_terms:
        source_term = row["source_term"]
        slug = slugify(source_term)
        concept_key = f"r011/concept/{slug}"
        concept_id = g.stable_id(concept_key)
        concept_ids[source_term] = concept_id
        records["concepts"].append(
            rrecord(
                "concept",
                concept_key,
                preferred_source_term=source_term,
                definition=TERM_DEFINITIONS[source_term],
                resource_id=resource_id,
                edition_id=edition_id,
                source_local_ids=[row["term_id"], BOUNDARY_ID],
                parent_id=None,
                order=len(records["concepts"]) + 1,
                source_path=BODY_PATH,
                source_span=None,
                source_sha256=body_source_sha,
                locale="zxx",
                translation_state="source_frozen",
                rights_component_ids=[default_rights_id],
                boundary_id=BOUNDARY_ID,
            )
        )
        records["terms"].append(
            rrecord(
                "term",
                f"r011/term/id-ID/{slug}",
                concept_id=concept_id,
                source_term=source_term,
                target_term=row["id_ID"],
                locale="id-ID",
                variants=["diagram batang bertumpuk"] if source_term == "segmented bar plot" else [],
                rejected_forms=[],
                scope=row["scope"],
                register="academic",
                evidence=f"{row['term_id']} and R011-B006 source context" + (f"; {row['note']}" if row["note"] else ""),
                resource_id=resource_id,
                edition_id=edition_id,
                source_local_ids=[row["term_id"], BOUNDARY_ID],
                parent_id=concept_id,
                order=len(records["terms"]) + 1,
                source_path=BODY_PATH,
                source_span=None,
                source_sha256=body_source_sha,
                translation_state="translated",
                rights_component_ids=[default_rights_id],
                boundary_id=BOUNDARY_ID,
            )
        )

    new_units = [row for row in records["units"] if row.get("boundary_id") == BOUNDARY_ID]
    for row in new_units:
        if row.get("parent_id"):
            add_relation(records, f"b006-contains-{slugify(row['stable_key'])}", "contains", row["parent_id"], row["id"], order=row.get("order") or 0)
    add_relation(
        records,
        "b006-section-2-1-precedes-section-2-2",
        "precedes",
        g.stable_id("r011/unit/source-label/numericalData"),
        section_id,
        qualifier="source order",
        order=1,
    )
    for number, answer_id in answer_ids.items():
        add_relation(records, f"b006-answer-2-{number}", "answers", answer_id, exercise_ids[number], qualifier="public appendix", order=number)
    for number, gap_id in gap_ids.items():
        add_relation(records, f"b006-o001-gap-2-{number}", "requires_companion_answer", exercise_ids[number], gap_id, qualifier="O001 independent original", order=number)
    for source_term, concept_id in concept_ids.items():
        term_order = int(next(row["term_id"].rsplit("-", 1)[1] for row in b006_terms if row["source_term"] == source_term))
        add_relation(records, f"b006-introduces-{slugify(source_term)}", "introduces", subsection_ids[INTRODUCING_SUBSECTION[source_term]], concept_id, qualifier="Section 2.2", order=term_order)

    def any_concept_id(term: str) -> str:
        if term in concept_ids:
            return concept_ids[term]
        return g.stable_id(f"r011/concept/{slugify(term)}")

    for prior, later in PREREQUISITES:
        add_relation(records, f"b006-prerequisite-{slugify(prior)}-{slugify(later)}", "prerequisite", any_concept_id(prior), any_concept_id(later), qualifier="conceptual", order=1)
    add_relation(records, "b006-segmented-stacked-synonym", "equivalent_to", concept_ids["segmented bar plot"], concept_ids["stacked bar plot"], qualifier="source synonym", order=1)
    for number, terms in EXERCISE_CONCEPTS.items():
        for order, term in enumerate(terms, 1):
            add_relation(records, f"b006-exercise-2-{number}-{slugify(term)}", "exercises", exercise_ids[number], concept_ids[term], qualifier="concept index", order=order)
    guided_primary_terms = ["row proportion", "column proportion", "side-by-side box plot", "hollow histogram"]
    for index, (guided_id, term) in enumerate(zip(guided_ids, guided_primary_terms), 1):
        add_relation(records, f"b006-guided-{index}-{slugify(term)}", "exercises", guided_id, concept_ids[term], qualifier="guided concept practice", order=1)

    rights_rows = {row["component_id"]: row for row in csv.DictReader(io.StringIO(fixed_raws["rights"].decode("utf-8"), newline=""))}
    for required_id in ("R011-RIGHTS-B006-GENERATED", "R011-RIGHTS-B006-DATA", "R011-RIGHTS-RPKG", "R011-RIGHTS-COUNTY-COMPLETE"):
        if required_id not in rights_rows:
            raise RuntimeError(f"component-rights control is missing {required_id}")
    generated_row = rights_rows["R011-RIGHTS-B006-GENERATED"]
    data_row = rights_rows["R011-RIGHTS-B006-DATA"]
    records["rights"].append(
        rrecord(
            "rights",
            generated_rights_key,
            component_scope=generated_row["path_or_scope"],
            license_expression="CC-BY-SA-3.0",
            attribution=generated_row["attribution"],
            change_notice="Indonesian text-object overlays are identified and deterministically replayable; source witnesses remain adjacent.",
            non_endorsement="No OpenIntro, package-author, source-author, pollster, or data-provider endorsement implied.",
            publication_effect=generated_row["publication_disposition"],
            verification_status="verified_repository_license_and_asset_receipt",
            resource_id=resource_id,
            edition_id=edition_id,
            source_local_ids=["R011-RIGHTS-B006-GENERATED", BOUNDARY_ID],
            parent_id=resource_id,
            order=len(records["rights"]) + 1,
            source_path="00_control/COMPONENT_RIGHTS.csv",
            source_span=None,
            source_sha256=EXPECTED_FIXED_EVIDENCE["rights"]["sha256"],
            locale="zxx",
            translation_state="structurally_verified",
            rights_component_ids=[],
            boundary_id=BOUNDARY_ID,
        )
    )
    records["rights"].append(
        rrecord(
            "rights",
            data_rights_key,
            component_scope=data_row["path_or_scope"],
            license_expression="GPL-3.0-only AND LicenseRef-Factual-Data",
            attribution=data_row["attribution"],
            change_notice="Only factual aggregates and derived geometry are used; third-party article and poll-report expression is excluded.",
            non_endorsement="No OpenIntro, agency, article-author, pollster, or data-provider endorsement implied.",
            publication_effect=data_row["publication_disposition"],
            verification_status="verified_component_data_provenance",
            resource_id=resource_id,
            edition_id=edition_id,
            source_local_ids=["R011-RIGHTS-B006-DATA", BOUNDARY_ID],
            parent_id=resource_id,
            order=len(records["rights"]) + 1,
            source_path="00_control/COMPONENT_RIGHTS.csv",
            source_span=None,
            source_sha256=EXPECTED_FIXED_EVIDENCE["rights"]["sha256"],
            locale="zxx",
            translation_state="structurally_verified",
            rights_component_ids=[],
            boundary_id=BOUNDARY_ID,
        )
    )

    def parent_for_asset(asset_id: str) -> str:
        kind, value = ASSET_PARENT_MAP[asset_id]
        return subsection_ids[value] if kind == "subsection" else exercise_ids[value]

    def rights_for_asset(asset_id: str) -> list[str]:
        result = [generated_rights_id, data_rights_id]
        if asset_id.startswith("loan_") or asset_id == "countyIncomeSplitByPopGain":
            result.append(package_rights_id)
        if asset_id == "countyIncomeSplitByPopGain":
            result.append(county_rights_id)
        return result

    source_witness_ids: dict[str, str] = {}
    localized_asset_ids: dict[str, str] = {}
    producer_ids: dict[str, str] = {}
    producer_assets: dict[str, list[str]] = {}
    for item in asset_manifest["assets"]:
        asset_id = item["id"]
        if asset_id not in ASSET_PARENT_MAP:
            raise RuntimeError(f"unexpected B006 asset id: {asset_id}")
        source_target_path = item["source"]["path"]
        original_path = source_target_path.removeprefix("repo/").replace(".source-en.pdf", ".pdf")
        authority_row = source_by_path.get(original_path)
        if authority_row is None or int(authority_row["bytes"]) != item["source"]["bytes"] or authority_row["sha256"] != item["source"]["sha256"]:
            raise RuntimeError(f"English source witness is not authority-exact: {asset_id}")
        source_disk = LANE / source_target_path
        target_disk = LANE / item["target"]["path"]
        if file_identity(source_disk) != {"bytes": item["source"]["bytes"], "sha256": item["source"]["sha256"]}:
            raise RuntimeError(f"source-witness file identity changed: {asset_id}")
        if file_identity(target_disk) != {"bytes": item["target"]["bytes"], "sha256": item["target"]["sha256"]}:
            raise RuntimeError(f"localized asset file identity changed: {asset_id}")
        parent_id = parent_for_asset(asset_id)
        component_rights = rights_for_asset(asset_id)
        witness_key = f"r011/asset/b006/source-en/{asset_id}"
        witness_id = g.stable_id(witness_key)
        source_witness_ids[asset_id] = witness_id
        records["assets"].append(
            rrecord(
                "asset",
                witness_key,
                asset_kind="frozen_english_figure_witness",
                media_type="application/pdf",
                bytes=item["source"]["bytes"],
                sha256=item["source"]["sha256"],
                source_local_ids=[asset_id, "SOURCE-EN", BOUNDARY_ID],
                parent_id=parent_id,
                order=len(records["assets"]) + 1,
                source_path=original_path,
                source_span=None,
                source_sha256=item["source"]["sha256"],
                target_path=source_target_path,
                target_bytes=item["source"]["bytes"],
                target_sha256=item["source"]["sha256"],
                page_box_points=item["page_box_points"],
                vector_drawing_count=item["vector_drawing_count"],
                vector_drawing_semantic_sha256=item["vector_drawing_semantic_sha256"],
                numeric_tokens=item["numeric_tokens"],
                resource_id=resource_id,
                edition_id=edition_id,
                locale="en",
                translation_state="source_frozen",
                rights_component_ids=component_rights,
                boundary_id=BOUNDARY_ID,
            )
        )
        target_key = f"r011/asset/b006/localized/{asset_id}"
        target_id = g.stable_id(target_key)
        localized_asset_ids[asset_id] = target_id
        records["assets"].append(
            rrecord(
                "asset",
                target_key,
                asset_kind="localized_vector_figure",
                media_type="application/pdf",
                bytes=item["source"]["bytes"],
                sha256=item["source"]["sha256"],
                source_local_ids=[asset_id, "ID-ID", BOUNDARY_ID],
                parent_id=parent_id,
                order=len(records["assets"]) + 1,
                source_path=original_path,
                source_span=None,
                source_sha256=item["source"]["sha256"],
                source_witness_id=witness_id,
                target_path=item["target"]["path"],
                target_bytes=item["target"]["bytes"],
                target_sha256=item["target"]["sha256"],
                target_locale="id-ID",
                page_count=1,
                page_box_points=item["page_box_points"],
                vector_drawing_count=item["vector_drawing_count"],
                vector_drawing_semantic_sha256=item["vector_drawing_semantic_sha256"],
                numeric_tokens=item["numeric_tokens"],
                localized_span_count=item["localized_span_count"],
                deterministic_replays=2,
                source_geometry_preserved=True,
                poppler_visual_status="passed",
                mupdf_visual_status="passed",
                resource_id=resource_id,
                edition_id=edition_id,
                locale="id-ID",
                translation_state="visually_checked",
                rights_component_ids=component_rights,
                boundary_id=BOUNDARY_ID,
            )
        )
        producer_assets.setdefault(item["producer"], []).append(asset_id)

    manifest_producers = {item["path"]: item for item in asset_manifest["producers"]}
    if sorted(manifest_producers) != sorted(producer_assets):
        raise RuntimeError("B006 producer/asset closure changed")
    for path, producer in sorted(manifest_producers.items()):
        relative = path.removeprefix("repo/")
        authority_row = source_by_path.get(relative)
        if authority_row is None or int(authority_row["bytes"]) != producer["bytes"] or authority_row["sha256"] != producer["sha256"]:
            raise RuntimeError(f"B006 producer is not authority-exact: {relative}")
        if file_identity(LANE / path) != {"bytes": producer["bytes"], "sha256": producer["sha256"]}:
            raise RuntimeError(f"B006 producer disk identity changed: {relative}")
        producer_key = f"r011/asset/b006/producer/{relative}"
        producer_id = g.stable_id(producer_key)
        producer_ids[path] = producer_id
        component_rights = sorted({right for asset_id in producer_assets[path] for right in rights_for_asset(asset_id)})
        records["assets"].append(
            rrecord(
                "asset",
                producer_key,
                asset_kind="authority_exact_figure_producer",
                media_type="text/x-r-source",
                bytes=producer["bytes"],
                sha256=producer["sha256"],
                source_local_ids=[relative, BOUNDARY_ID],
                parent_id=section_id,
                order=len(records["assets"]) + 1,
                source_path=relative,
                source_span=None,
                source_sha256=producer["sha256"],
                target_path=path,
                target_bytes=producer["bytes"],
                target_sha256=producer["sha256"],
                resource_id=resource_id,
                edition_id=edition_id,
                locale="en",
                translation_state="source_frozen",
                rights_component_ids=component_rights,
                boundary_id=BOUNDARY_ID,
            )
        )

    localizer_key = "r011/asset/b006/localizer"
    localizer_id = g.stable_id(localizer_key)
    records["assets"].append(
        rrecord(
            "asset",
            localizer_key,
            asset_kind="deterministic_text_object_localizer",
            media_type="text/x-python",
            bytes=EXPECTED_FIXED_EVIDENCE["localizer"]["bytes"],
            sha256=EXPECTED_FIXED_EVIDENCE["localizer"]["sha256"],
            source_local_ids=["scripts/localize_b006_figures.py", BOUNDARY_ID],
            parent_id=section_id,
            order=len(records["assets"]) + 1,
            source_path=None,
            source_span=None,
            source_sha256=None,
            target_path=EXPECTED_FIXED_EVIDENCE["localizer"]["path"],
            target_bytes=EXPECTED_FIXED_EVIDENCE["localizer"]["bytes"],
            target_sha256=EXPECTED_FIXED_EVIDENCE["localizer"]["sha256"],
            resource_id=resource_id,
            edition_id=edition_id,
            locale="zxx",
            translation_state="structurally_verified",
            rights_component_ids=[generated_rights_id],
            boundary_id=BOUNDARY_ID,
        )
    )

    asset_receipt_artifact_id = g.stable_id("r011/artifact/b006-asset-receipt")
    for item in asset_manifest["assets"]:
        asset_id = item["id"]
        add_relation(records, f"b006-source-witness-localized-{slugify(asset_id)}", "translates", source_witness_ids[asset_id], localized_asset_ids[asset_id], qualifier="id-ID text-object overlay", order=1)
        add_relation(records, f"b006-localizer-localized-{slugify(asset_id)}", "produces", localizer_id, localized_asset_ids[asset_id], qualifier="two byte-identical replays", order=1)
        add_relation(records, f"b006-producer-localized-{slugify(asset_id)}", "produces", producer_ids[item["producer"]], localized_asset_ids[asset_id], qualifier="pinned source producer and unchanged data geometry", order=1)
        add_relation(records, f"b006-localized-illustrates-{slugify(asset_id)}", "illustrates", localized_asset_ids[asset_id], parent_for_asset(asset_id), qualifier="reader-visible Section 2.2 asset", order=1)
        add_relation(records, f"b006-asset-receipt-verifies-{slugify(asset_id)}", "verifies", asset_receipt_artifact_id, localized_asset_ids[asset_id], qualifier="Poppler and MuPDF same-renderer pairs; deterministic replay", order=1)

    adverse_rows = {row["id"]: row for row in (json.loads(line) for line in fixed_raws["adverse"].decode("utf-8").splitlines())}
    correction_targets = {
        65: subsection_ids[0],
        66: subsection_ids[2],
        67: guided_ids[2],
        68: answer_ids[23],
        69: exercise_ids[21],
    }
    correction_actions = {
        65: "Name homeownership, the variable actually summarized by the figure and surrounding prose.",
        66: "Restore blue as individual and yellow as joint for the rent bar while preserving every plotted count.",
        67: "Use the figure-supported medians of approximately USD 53,000 and USD 45,000.",
        68: "Align the answer categories with Support, Not support, and Not sure and their localized display labels.",
        69: "Correct Neuromascular to Neuromuscular and localize the intended medical category consistently.",
    }
    correction_paths = {65: BODY_PATH, 66: BODY_PATH, 67: BODY_PATH, 68: ANSWER_PATH, 69: EXERCISE_PATH}
    target_hashes = {BODY_PATH: identities["body"]["sha256"], EXERCISE_PATH: identities["exercises"]["sha256"], ANSWER_PATH: identities["answers"]["sha256"]}
    for number in range(65, 70):
        row = adverse_rows[f"R011-ADV-{number:04d}"]
        path = correction_paths[number]
        records["corrections"].append(
            rrecord(
                "correction",
                f"r011/correction/b006-adv-{number:04d}",
                correction_type="source_semantic_correction",
                category=row["kind"],
                affected_id=correction_targets[number],
                source_claim=row["finding"],
                evidence=f"00_control/ADVERSE_LEDGER.jsonl#R011-ADV-{number:04d}",
                proposed_correction=correction_actions[number],
                rationale="Preserve intended source meaning while making the Indonesian edition accurate and accessible.",
                confidence="high",
                upstream_report_disposition="hold_until_corpus_complete_then_deduplicate",
                target_path=f"repo/{path}",
                target_sha256=target_hashes[path],
                target_identity_status="source_gate_passed",
                resource_id=resource_id,
                edition_id=edition_id,
                source_local_ids=[f"R011-ADV-{number:04d}", row["source_correction_id"], BOUNDARY_ID],
                parent_id=correction_targets[number],
                order=number,
                source_path=path,
                source_span=None,
                source_sha256=source_by_path[path]["sha256"],
                locale="id-ID",
                translation_state="translated",
                rights_component_ids=[default_rights_id],
                boundary_id=BOUNDARY_ID,
            )
        )

    derivative_targets = {
        70: subsection_ids[0],
        71: subsection_ids[1],
        72: subsection_ids[3],
        73: subsection_ids[5],
        74: guided_ids[2],
        75: subsection_ids[2],
        76: answer_ids[23],
        77: section_id,
        78: edition_id,
        79: review_id,
    }
    derivative_actions = {
        70: "Localize the displayed category aliases in the contingency and email-format tables while preserving every value and source literal.",
        71: "Use the standard Indonesian spelling mengondisikan.",
        72: "Describe the mosaic association through horizontal dividing lines at different heights in each column.",
        73: "Render the reader-facing unit notation as dalam satuan $1000 in both heading and caption.",
        74: "Use the localized group label Bertambah in the guided feedback.",
        75: "Remove only the local forced break that stranded Example 2.26 while preserving content and source order.",
        76: "Remove only the explicit answer-boundary break after answer 2.23 while retaining the multicols boundary and answer order.",
        77: "Top-place Figure 2.28 and locally suppress clearpageforsection around only the Section 2.2 exercise header so the exercises can use the same sheet.",
        78: "Remove only the explicit break following public answer 3.7 while retaining both multicols boundaries and all answer order.",
        79: "Remove only the exact forced break between Exercises 2.22 and 2.23 so the source-ordered exercises can continue on the same sheet.",
    }
    derivative_paths = {number: BODY_PATH for number in range(70, 76)} | {76: ANSWER_PATH, 77: BODY_PATH, 78: ANSWER_PATH, 79: EXERCISE_PATH}
    for number in range(70, 80):
        row = adverse_rows[f"R011-ADV-{number:04d}"]
        path = derivative_paths[number]
        extra: dict[str, Any] = {}
        if number == 77:
            extra = {
                "affected_ids": [subsection_ids[5], review_id],
                "target_identities": [
                    identities["body"],
                    identities["exercises"],
                ],
            }
        elif number == 78:
            extra = {
                "affected_ids": [edition_id],
                "target_identities": [identities["answers"]],
            }
        elif number == 79:
            extra = {
                "affected_ids": [exercise_ids[22], exercise_ids[23]],
                "target_identities": [identities["exercises"]],
            }
        records["corrections"].append(
            rrecord(
                "correction",
                f"r011/correction/b006-adv-{number:04d}",
                correction_type="derivative_layout_correction" if row["kind"].startswith("layout_") else "derivative_language_correction",
                category=row["kind"],
                affected_id=derivative_targets[number],
                source_claim=row["finding"],
                evidence=f"00_control/ADVERSE_LEDGER.jsonl#R011-ADV-{number:04d}",
                proposed_correction=derivative_actions[number],
                rationale="Resolve independent semantic, language, or full-page QA without changing mathematical content or source order.",
                confidence="high",
                upstream_report_disposition="not_upstream_derivative_only",
                target_path=f"repo/{path}",
                target_sha256=target_hashes[path],
                target_identity_status="source_gate_passed",
                resource_id=resource_id,
                edition_id=edition_id,
                source_local_ids=[f"R011-ADV-{number:04d}", BOUNDARY_ID],
                parent_id=derivative_targets[number],
                order=number,
                source_path=path,
                source_span=None,
                source_sha256=source_by_path[path]["sha256"],
                locale="id-ID",
                translation_state="translated",
                rights_component_ids=[default_rights_id],
                boundary_id=BOUNDARY_ID,
                **extra,
            )
        )

    evidence_payloads = {
        "evidence/R011-B006_FINAL_GATE_INPUTS.json": supplied_raw,
        "evidence/R011-B006_PREAPPLICATION_MANIFEST.json": fixed_raws["preapplication"],
        "evidence/R011-B006_SOURCE_APPLICATION_RECEIPT.json": fixed_raws["source_application"],
        "evidence/R011-B006_REPAIR_RECEIPT.json": fixed_raws["repair_receipt"],
        "evidence/R011-B006_LAYOUT_REPAIR_RECEIPT_V3.json": fixed_raws["layout_repair_receipt"],
        "evidence/R011-B006_LAYOUT_REPAIR_RECEIPT_V4.json": fixed_raws["layout_repair_receipt_v4"],
        "evidence/R011-B006_BUILD_QA_V1_REJECTED.json": fixed_raws["rejected_build_receipt_v1"],
        "evidence/R011-B006_VISUAL_FINDINGS_V1.json": fixed_raws["rejected_visual_findings_v1"],
        "evidence/R011-B006_BUILD_QA_V2_REJECTED.json": fixed_raws["rejected_build_receipt_v2"],
        "evidence/R011-B006_VISUAL_FINDINGS_V2.json": fixed_raws["rejected_visual_findings_v2"],
        "evidence/R011-B006_BUILD_QA_V3_REJECTED.json": fixed_raws["rejected_build_receipt_v3"],
        "evidence/R011-B006_VISUAL_FINDINGS_V3.json": fixed_raws["rejected_visual_findings_v3"],
        "evidence/R011-B006_TERMINOLOGY.csv": term_bytes,
        "evidence/R011-B006_ADVERSE_LEDGER.jsonl": selected_adverse_bytes(),
        "evidence/R011-B006_COMPONENT_RIGHTS.csv": fixed_raws["rights"],
        "evidence/R011-B006_SOURCE_QA.json": final_raws["source_qa"],
        "evidence/R011-B006_TARGET_MANIFEST.tsv": final_raws["target_manifest"],
        "evidence/R011-B006_ASSET_MANIFEST.json": fixed_raws["asset_manifest"],
        "evidence/R011-B006_ASSET_VALIDATION_RECEIPT.json": fixed_raws["asset_receipt"],
        "evidence/R011-B006_BUILD_GATE.py": final_raws["build_gate_script"],
        "evidence/R011-B006_CANDIDATE_BUILD_QA_V4.json": final_raws["candidate_build_qa"],
        "evidence/R011-B006_BUILD_QA.json": final_raws["build_qa"],
        "evidence/R011-B006_RENDER_MANIFEST.tsv": final_raws["render_manifest"],
        "evidence/R011-B006_PAGE_LOCATOR.json": final_raws["page_locator"],
        "evidence/R011-B006_VISUAL_CONTACT_SHEET.png": final_raws["contact_sheet"],
        "evidence/R011-B006_VISUAL_AUDIT.json": final_raws["visual_audit"],
        "evidence/R011-B006_VISUAL_FINALIZER.py": final_raws["visual_finalizer"],
    }

    def add_artifact(
        slug: str,
        kind: str,
        path: str,
        identity: dict[str, Any],
        local_ids: list[str],
        *,
        locale: str = "zxx",
        translation_state: str = "structurally_verified",
        rights_ids: list[str] | None = None,
        result: str = "passed",
        extra: dict[str, Any] | None = None,
    ) -> str:
        key = f"r011/artifact/b006-{slug}"
        artifact_id = g.stable_id(key)
        records["artifacts"].append(
            rrecord(
                "artifact",
                key,
                artifact_kind=kind,
                path=path,
                bytes=identity["bytes"],
                sha256=identity["sha256"],
                result=result,
                toolchain="R011-B006 exact-input deterministic stage evidence",
                resource_id=resource_id,
                edition_id=edition_id,
                source_local_ids=local_ids,
                parent_id=edition_id,
                order=len(records["artifacts"]) + 1,
                source_path=None,
                source_span=None,
                source_sha256=None,
                locale=locale,
                translation_state=translation_state,
                rights_component_ids=rights_ids or [],
                boundary_id=BOUNDARY_ID,
                status="passed",
                **(extra or {}),
            )
        )
        return artifact_id

    copied_artifacts = [
        ("final-gate-inputs", "exact_final_input_manifest", "qa/b006-backend/exports/evidence/R011-B006_FINAL_GATE_INPUTS.json", supplied_raw, [BOUNDARY_ID, "EXACT-INPUTS"]),
        ("preapplication", "preapplication_manifest", "qa/b006-backend/exports/evidence/R011-B006_PREAPPLICATION_MANIFEST.json", fixed_raws["preapplication"], [BOUNDARY_ID]),
        ("source-application", "source_application_receipt", "qa/b006-backend/exports/evidence/R011-B006_SOURCE_APPLICATION_RECEIPT.json", fixed_raws["source_application"], [BOUNDARY_ID, "SOURCE-APPLICATION-PASS"]),
        ("repair-receipt", "post_build_repair_receipt", "qa/b006-backend/exports/evidence/R011-B006_REPAIR_RECEIPT.json", fixed_raws["repair_receipt"], [BOUNDARY_ID, "ADV-0070..0076", "REVERSE-VERIFIED"]),
        ("layout-repair-v3", "layout_repair_receipt", "qa/b006-backend/exports/evidence/R011-B006_LAYOUT_REPAIR_RECEIPT_V3.json", fixed_raws["layout_repair_receipt"], [BOUNDARY_ID, "ADV-0077..0078", "V2-REVERSE-VERIFIED"]),
        ("layout-repair-v4", "layout_repair_receipt", "qa/b006-backend/exports/evidence/R011-B006_LAYOUT_REPAIR_RECEIPT_V4.json", fixed_raws["layout_repair_receipt_v4"], [BOUNDARY_ID, "ADV-0079", "V3-REVERSE-VERIFIED"]),
        ("rejected-build-v1", "rejected_build_qa_receipt", "qa/b006-backend/exports/evidence/R011-B006_BUILD_QA_V1_REJECTED.json", fixed_raws["rejected_build_receipt_v1"], [BOUNDARY_ID, "V1", "REJECTED-NOT-PROMOTED"]),
        ("rejected-visual-v1", "rejected_visual_findings_receipt", "qa/b006-backend/exports/evidence/R011-B006_VISUAL_FINDINGS_V1.json", fixed_raws["rejected_visual_findings_v1"], [BOUNDARY_ID, "V1", "P2=2"]),
        ("rejected-build-v2", "rejected_build_qa_receipt", "qa/b006-backend/exports/evidence/R011-B006_BUILD_QA_V2_REJECTED.json", fixed_raws["rejected_build_receipt_v2"], [BOUNDARY_ID, "V2", "REJECTED-NOT-PROMOTED"]),
        ("rejected-visual-v2", "rejected_visual_findings_receipt", "qa/b006-backend/exports/evidence/R011-B006_VISUAL_FINDINGS_V2.json", fixed_raws["rejected_visual_findings_v2"], [BOUNDARY_ID, "V2", "P2=2"]),
        ("rejected-build-v3", "rejected_build_qa_receipt", "qa/b006-backend/exports/evidence/R011-B006_BUILD_QA_V3_REJECTED.json", fixed_raws["rejected_build_receipt_v3"], [BOUNDARY_ID, "V3", "REJECTED-NOT-PROMOTED"]),
        ("rejected-visual-v3", "rejected_visual_findings_receipt", "qa/b006-backend/exports/evidence/R011-B006_VISUAL_FINDINGS_V3.json", fixed_raws["rejected_visual_findings_v3"], [BOUNDARY_ID, "V3", "P2=1"]),
        ("terminology-control", "terminology_control", "qa/b006-backend/exports/evidence/R011-B006_TERMINOLOGY.csv", term_bytes, [BOUNDARY_ID, "R011-TERM-0141"]),
        ("adverse-control", "adverse_event_ledger", "qa/b006-backend/exports/evidence/R011-B006_ADVERSE_LEDGER.jsonl", evidence_payloads["evidence/R011-B006_ADVERSE_LEDGER.jsonl"], [BOUNDARY_ID, "R011-ADV-0079"]),
        ("component-rights", "component_rights_control", "qa/b006-backend/exports/evidence/R011-B006_COMPONENT_RIGHTS.csv", fixed_raws["rights"], [BOUNDARY_ID, "R011-RIGHTS-B006-GENERATED", "R011-RIGHTS-B006-DATA"]),
        ("source-qa", "source_qa_receipt", "qa/b006-backend/exports/evidence/R011-B006_SOURCE_QA.json", final_raws["source_qa"], [BOUNDARY_ID, "SOURCE-GATE-PASS"]),
        ("target-manifest", "target_tree_manifest", "qa/b006-backend/exports/evidence/R011-B006_TARGET_MANIFEST.tsv", final_raws["target_manifest"], [BOUNDARY_ID, f"{EXPECTED_TARGET_CLOSURE['file_count']}-FILES", f"{EXPECTED_TARGET_CLOSURE['file_bytes']}-BYTES"]),
        ("asset-manifest", "localized_asset_manifest", "qa/b006-backend/exports/evidence/R011-B006_ASSET_MANIFEST.json", fixed_raws["asset_manifest"], [BOUNDARY_ID, "13-ASSETS"]),
        ("asset-receipt", "localized_asset_validation_receipt", "qa/b006-backend/exports/evidence/R011-B006_ASSET_VALIDATION_RECEIPT.json", fixed_raws["asset_receipt"], [BOUNDARY_ID, "13-ASSETS", "POPPLER", "MUPDF"]),
        ("build-qa", "build_qa_receipt", "qa/b006-backend/exports/evidence/R011-B006_BUILD_QA.json", final_raws["build_qa"], [BOUNDARY_ID, "V4", "DETERMINISTIC-BUILD-PASS", "VISUAL-PASS", "CANDIDATE-NOT-PROMOTED"]),
        ("render-manifest", "visual_qa_manifest", "qa/b006-backend/exports/evidence/R011-B006_RENDER_MANIFEST.tsv", final_raws["render_manifest"], [BOUNDARY_ID, f"{final_gate['rendered_page_count']}-PAGES"]),
        ("visual-audit", "visual_audit_receipt", "qa/b006-backend/exports/evidence/R011-B006_VISUAL_AUDIT.json", final_raws["visual_audit"], [BOUNDARY_ID, "P1=0", "P2=0", "P3=0"]),
    ]
    artifact_ids: dict[str, str] = {}
    for slug, kind, path, raw, local_ids in copied_artifacts:
        artifact_ids[slug] = add_artifact(slug, kind, path, {"bytes": len(raw), "sha256": g.sha256_bytes(raw)}, local_ids)
    if artifact_ids["asset-receipt"] != asset_receipt_artifact_id:
        raise RuntimeError("asset-receipt stable identity changed")

    artifact_ids["poppler-contact-sheet"] = add_artifact(
        "poppler-contact-sheet",
        "same_renderer_source_target_contact_sheet",
        EXPECTED_FIXED_EVIDENCE["poppler_contact_sheet"]["path"],
        EXPECTED_FIXED_EVIDENCE["poppler_contact_sheet"],
        [BOUNDARY_ID, "POPPLER", "13-PAIRS"],
    )
    artifact_ids["mupdf-contact-sheet"] = add_artifact(
        "mupdf-contact-sheet",
        "same_renderer_source_target_contact_sheet",
        EXPECTED_FIXED_EVIDENCE["mupdf_contact_sheet"]["path"],
        EXPECTED_FIXED_EVIDENCE["mupdf_contact_sheet"],
        [BOUNDARY_ID, "MUPDF", "13-PAIRS"],
    )
    artifact_ids["build-log"] = add_artifact(
        "build-log",
        "build_log",
        supplied_identities["build_log"]["path"],
        supplied_identities["build_log"],
        [BOUNDARY_ID, "FINAL-BUILD"],
        locale="id-ID",
        translation_state="built",
        extra={
            "build_receipt": supplied_identities["build_qa"]["path"],
            "candidate_build_receipt": supplied_identities["candidate_build_qa"]["path"],
            "build_text": supplied_identities["build_text"],
            "fatal_error_count": 0,
            "latex_error_count": 0,
            "undefined_reference_count": 0,
            "missing_destination_count": 0,
        },
    )
    artifact_ids["pdf"] = add_artifact(
        "pdf",
        "localized_boundary_pdf",
        supplied_identities["pdf"]["path"],
        supplied_identities["pdf"],
        [BOUNDARY_ID, "FINAL-V4", "REVIEWED-CANDIDATE", "VISUAL-PASS", "NOT-PROMOTED"],
        locale="id-ID",
        translation_state="visually_checked",
        rights_ids=[default_rights_id, generated_rights_id, data_rights_id],
        result="built_verified",
        extra={
            "build_receipt": supplied_identities["build_qa"]["path"],
            "page_count": supplied_identities["pdf"]["page_count"],
            "document_language": "id-ID",
            "consecutive_pass_hashes_identical": True,
            "candidate_pdf_promoted": False,
            "visual_audit": supplied_identities["visual_audit"],
            "render_manifest": supplied_identities["render_manifest"],
            "page_locator": supplied_identities["page_locator"],
            "contact_sheet": supplied_identities["contact_sheet"],
        },
    )
    generator_identity = file_identity(Path(__file__), "scripts/generate_backend_b006.py")
    artifact_ids["generator"] = add_artifact(
        "generator",
        "deterministic_backend_generator",
        "scripts/generate_backend_b006.py",
        generator_identity,
        [BOUNDARY_ID, "STAGE-ONLY", "NO-PROMOTION"],
    )

    add_relation(records, "b006-source-qa-verifies-section", "verifies", artifact_ids["source-qa"], section_id, qualifier="exact 1,195-file target closure", order=1)
    add_relation(records, "b006-repair-receipt-verifies-section", "verifies", artifact_ids["repair-receipt"], section_id, qualifier="seven bounded derivative repairs and byte-exact reverse reconstruction", order=1)
    add_relation(records, "b006-rejected-build-supports-repair", "supports", artifact_ids["rejected-build-v1"], artifact_ids["repair-receipt"], qualifier="v1 deterministic build rejected before promotion", order=1)
    add_relation(records, "b006-rejected-visual-supports-repair", "supports", artifact_ids["rejected-visual-v1"], artifact_ids["repair-receipt"], qualifier="two P2 underfill findings motivate only ADV-0075 and ADV-0076", order=1)
    add_relation(records, "b006-layout-repair-v3-verifies-section", "verifies", artifact_ids["layout-repair-v3"], section_id, qualifier="three exact layout-only substitutions and byte-exact v2 reverse reconstruction", order=1)
    add_relation(records, "b006-rejected-build-v2-supports-layout-repair", "supports", artifact_ids["rejected-build-v2"], artifact_ids["layout-repair-v3"], qualifier="v2 deterministic build rejected before promotion", order=1)
    add_relation(records, "b006-rejected-visual-v2-supports-layout-repair", "supports", artifact_ids["rejected-visual-v2"], artifact_ids["layout-repair-v3"], qualifier="two P2 underfill findings motivate only ADV-0077 and ADV-0078", order=1)
    add_relation(records, "b006-layout-repair-v4-verifies-exercises", "verifies", artifact_ids["layout-repair-v4"], review_id, qualifier="one exact layout-only substitution and byte-exact v3 reverse reconstruction", order=1)
    add_relation(records, "b006-rejected-build-v3-supports-layout-repair", "supports", artifact_ids["rejected-build-v3"], artifact_ids["layout-repair-v4"], qualifier="v3 deterministic build rejected before promotion", order=1)
    add_relation(records, "b006-rejected-visual-v3-supports-layout-repair", "supports", artifact_ids["rejected-visual-v3"], artifact_ids["layout-repair-v4"], qualifier="one P2 underfill finding motivates only ADV-0079", order=1)
    add_relation(records, "b006-asset-manifest-inventories-receipt", "verifies", artifact_ids["asset-manifest"], artifact_ids["asset-receipt"], qualifier="13 source/target pairs", order=1)
    add_relation(records, "b006-build-qa-verifies-pdf", "verifies", artifact_ids["build-qa"], artifact_ids["pdf"], qualifier="deterministic V4 final passes and exact reviewed-candidate identity", order=1)
    add_relation(records, "b006-visual-audit-verifies-pdf", "verifies", artifact_ids["visual-audit"], artifact_ids["pdf"], qualifier="full-resolution zero-severity page sweep", order=1)
    add_relation(records, "b006-render-manifest-supports-visual", "supports", artifact_ids["render-manifest"], artifact_ids["visual-audit"], qualifier="exact rendered-page inventory", order=1)

    qa_specs = [
        (
            "translation-topology",
            "topology",
            section_id,
            "backend/exports/views/unit_hierarchy.csv; backend/exports/views/segments_locale.csv",
            f"One section, six subsections, four guided exercises, four end-of-section exercises, two public odd answers, two O001 even gaps, and {len(segment_specs)} non-overlapping translation segments are modeled.",
        ),
        (
            "terminology",
            "language",
            section_id,
            "qa/b006-backend/exports/evidence/R011-B006_TERMINOLOGY.csv",
            "All 20 B006 controlled terms R011-TERM-0122..0141 have stable concept and id-ID term identities, introduction relations, and prerequisite edges.",
        ),
        (
            "corrections",
            "source",
            section_id,
            "00_control/ADVERSE_LEDGER.jsonl#R011-ADV-0065-R011-ADV-0069",
            "Five high-confidence upstream source/accessibility corrections SC-B006-001..005 are held for one deduplicated end-of-corpus report; ten derivative-only language/layout corrections ADV-0070..0079 are explicitly excluded from upstream reporting.",
        ),
        (
            "post-build-repair",
            "language",
            artifact_ids["repair-receipt"],
            "qa/R011-B006_REPAIR_RECEIPT.json",
            "Seventeen exact substitutions implementing ADV-0070..0076 replay in reverse to the pre-repair source identities; instructional order and numeric data are unchanged, and the rejected v1 candidate was never promoted.",
        ),
        (
            "v3-layout-repair",
            "visual",
            artifact_ids["layout-repair-v3"],
            "qa/R011-B006_LAYOUT_REPAIR_RECEIPT_V3.json",
            "Three exact layout-only substitutions implementing ADV-0077..0078 replay to the full rejected-v2 source snapshot and manifest; instructional content, order, mathematics, numeric data, assets, and figure bytes are unchanged, and v2 was never promoted.",
        ),
        (
            "v4-layout-repair",
            "visual",
            artifact_ids["layout-repair-v4"],
            "qa/R011-B006_LAYOUT_REPAIR_RECEIPT_V4.json",
            "One exact layout-only substitution implementing ADV-0079 replays to the full rejected-v3 source snapshot and manifest; exercise text, order, mathematics, numeric data, and assets are unchanged, and v3 was never promoted.",
        ),
        (
            "source-gate",
            "source",
            section_id,
            "qa/R011-B006_SOURCE_QA.json; qa/R011-B006_TARGET_MANIFEST.tsv",
            f"The replayed post-repair B006 source gate admits exactly {EXPECTED_TARGET_CLOSURE['file_count']:,} files / {EXPECTED_TARGET_CLOSURE['file_bytes']:,} bytes with no active reader-visible English and no placeholders.",
        ),
        (
            "asset-gate",
            "visual",
            artifact_ids["asset-receipt"],
            "qa/b006-assets/ASSET_VALIDATION_RECEIPT_R011-B006.json",
            "All 13 localized figures and 13 exact English witnesses pass two deterministic replays, vector/numeric invariance, and complete Poppler/MuPDF same-renderer visual inspection.",
        ),
        (
            "component-rights",
            "rights",
            generated_rights_id,
            "00_control/COMPONENT_RIGHTS.csv",
            "Repository expression, separately governed OpenIntro package inputs, factual data, attribution, change notice, and non-endorsement boundaries are attached at component level.",
        ),
        (
            "build",
            "build",
            artifact_ids["pdf"],
            supplied_identities["build_qa"]["path"],
            f"The supplied final V4 build receipt proves byte-identical final passes, a {supplied_identities['pdf']['page_count']}-page id-ID reviewed candidate, zero missing link targets, and full visual acceptance; it truthfully records that candidate-PDF promotion was not performed.",
        ),
        (
            "visual",
            "visual",
            artifact_ids["visual-audit"],
            supplied_identities["visual_audit"]["path"],
            f"All {final_gate['rendered_page_count']} bound B006 candidate pages pass full-resolution visual inspection with P0/P1/P2/P3 all zero and no clipping, overlap, truncation, stranded continuation, underfill, centering, or localized-figure defect.",
        ),
    ]
    for slug, qa_type, subject_id, witness, detail in qa_specs:
        records["qa_events"].append(
            rrecord(
                "qa_event",
                f"r011/qa/b006-{slug}",
                qa_type=qa_type,
                result="passed",
                subject_id=subject_id,
                witness_path=witness,
                detail=detail,
                resource_id=resource_id,
                edition_id=edition_id,
                source_local_ids=[BOUNDARY_ID],
                parent_id=subject_id,
                order=len(records["qa_events"]) + 1,
                source_path=None,
                source_span=None,
                source_sha256=None,
                locale="zxx",
                translation_state="structurally_verified",
                rights_component_ids=[],
                boundary_id=BOUNDARY_ID,
                status="passed",
            )
        )

    context = {
        "authority": authority,
        "authority_sha256": g.sha256_file(g.AUTHORITY_PATH),
        "identities": identities,
        "supplied": supplied,
        "supplied_sha256": g.sha256_bytes(supplied_raw),
        "final_gate": final_gate,
        "fixed_raws": fixed_raws,
        "evidence_payloads": evidence_payloads,
        "segment_count": len(segment_specs),
        "source_manifest_file_count": len(source_manifest_lines),
        "source_manifest_file_bytes": source_manifest_bytes,
        "localized_asset_paths": sorted(item["target"]["path"] for item in asset_manifest["assets"]),
        "source_witness_paths": sorted(item["source"]["path"] for item in asset_manifest["assets"]),
        "producer_paths": sorted(manifest_producers),
        "artifact_ids": artifact_ids,
        "rights_ids": {"generated": generated_rights_id, "data": data_rights_id},
    }
    return records, context


def payload_record_count(path: str, raw: bytes) -> int | None:
    if path.endswith(".csv"):
        return max(0, sum(1 for _ in csv.reader(io.StringIO(raw.decode("utf-8"), newline=""))) - 1)
    if path.endswith(".jsonl") or path.endswith(".tsv"):
        return len(raw.decode("utf-8").splitlines())
    if path.endswith(".json"):
        return 1
    return None


def build_payloads(final_inputs_path: Path) -> dict[str, bytes]:
    records, context = build_records(final_inputs_path)
    payloads = {relative_path: g.jsonl_bytes(records[name]) for name, relative_path in RECORD_PATHS.items()}
    all_records = [item for collection in records.values() for item in collection]
    payloads["identity_map.jsonl"] = g.jsonl_bytes(
        {
            "id": item["id"],
            "record_type": item["record_type"],
            "stable_key": item["stable_key"],
            "source_local_ids": item.get("source_local_ids", []),
        }
        for item in all_records
    )
    view_schema = json.loads((BASE_BACKEND / "schemas" / "backend-view-columns-v0.1.0.json").read_text(encoding="utf-8"))
    payloads.update(g.build_views(records, view_schema["views"]))
    payloads.update(base_auxiliary_payloads())
    payloads.update(context["evidence_payloads"])

    file_entries = [
        {"path": path, "bytes": len(raw), "sha256": g.sha256_bytes(raw), "records": payload_record_count(path, raw)}
        for path, raw in sorted(payloads.items())
    ]
    schema_entries = []
    for schema_path in sorted((BASE_BACKEND / "schemas").glob("*")):
        if schema_path.is_file():
            raw = schema_path.read_bytes()
            schema_entries.append({"path": f"schemas/{schema_path.name}", "bytes": len(raw), "sha256": g.sha256_bytes(raw), "records": None})

    supplied = context["supplied"]
    supplied_identities = supplied["inputs"]
    manifest = {
        "$schema": "schemas/backend-manifest-v0.1.0.schema.json",
        "schema_version": SCHEMA_VERSION,
        "backend_id": g.stable_id("r011/backend/R011-B006/v0"),
        "namespace_uuid": str(g.NAMESPACE),
        "workflow_id": WORKFLOW_ID,
        "recorded_at": RECORDED_AT,
        "authority": {
            "repository": context["authority"]["repository"],
            "branch_observed": context["authority"]["branch_observed"],
            "commit": context["authority"]["commit"],
            "tree": context["authority"]["calculated_git_tree_sha1"],
            "authority_path": "authority/UPSTREAM_AUTHORITY.json",
            "authority_sha256": context["authority_sha256"],
            "source_file_manifest_sha256": context["authority"]["manifest_sha256"],
        },
        "canonicalization": {
            "encoding": "UTF-8 without BOM",
            "normalization": "Unicode NFC",
            "line_endings": "LF",
            "json": "RFC-8785-compatible integer/string subset; keys sorted; compact separators",
            "record_order": "ascending UUID string",
        },
        "scope": {
            "base_boundary": BASE_BOUNDARY_ID,
            "translated_boundaries": ["R011-B001", "R011-B002", "R011-B003", "R011-B004", "R011-B004R", "R011-B005", BOUNDARY_ID],
            "chapter": "ch_summarizing_data",
            "unit": "Complete Section 2.2 Considering categorical data",
            "subsection_count": 6,
            "guided_exercise_count": 4,
            "end_of_section_exercises": ["2.21", "2.22", "2.23", "2.24"],
            "public_answers": ["2.21", "2.23"],
            "o001_gaps": ["2.22", "2.24"],
            "terminology_control_range": ["R011-TERM-0122", "R011-TERM-0141"],
            "correction_range": ["R011-ADV-0065", "R011-ADV-0079"],
            "translation_segment_count": context["segment_count"],
            "localized_asset_count": 13,
            "source_witness_count": 13,
            "producer_count": 8,
            "localized_asset_paths": context["localized_asset_paths"],
            "source_witness_paths": context["source_witness_paths"],
            "producer_paths": context["producer_paths"],
            "target_locale": "id-ID",
        },
        "accepted_source_identity": {
            "status": "passed",
            "body": context["identities"]["body"],
            "exercises": context["identities"]["exercises"],
            "answers": context["identities"]["answers"],
            "translated_section": context["identities"]["translated_section"],
            "translated_answers": context["identities"]["translated_answers"],
            "source_qa": supplied_identities["source_qa"],
            "target_manifest": supplied_identities["target_manifest"],
            "preapplication_manifest": EXPECTED_FIXED_EVIDENCE["preapplication"],
            "source_application_receipt": EXPECTED_FIXED_EVIDENCE["source_application"],
            "post_build_repair_receipt": EXPECTED_FIXED_EVIDENCE["repair_receipt"],
            "v3_layout_repair_receipt": EXPECTED_FIXED_EVIDENCE["layout_repair_receipt"],
            "v4_layout_repair_receipt": EXPECTED_FIXED_EVIDENCE["layout_repair_receipt_v4"],
            "rejected_v1_build_receipt": EXPECTED_FIXED_EVIDENCE["rejected_build_receipt_v1"],
            "rejected_v1_visual_findings": EXPECTED_FIXED_EVIDENCE["rejected_visual_findings_v1"],
            "rejected_v2_build_receipt": EXPECTED_FIXED_EVIDENCE["rejected_build_receipt_v2"],
            "rejected_v2_visual_findings": EXPECTED_FIXED_EVIDENCE["rejected_visual_findings_v2"],
            "rejected_v3_build_receipt": EXPECTED_FIXED_EVIDENCE["rejected_build_receipt_v3"],
            "rejected_v3_visual_findings": EXPECTED_FIXED_EVIDENCE["rejected_visual_findings_v3"],
        },
        "source_closure": {
            "status": "passed",
            "file_count": context["source_manifest_file_count"],
            "file_bytes": context["source_manifest_file_bytes"],
            "source_qa_sha256": supplied_identities["source_qa"]["sha256"],
            "target_manifest_sha256": supplied_identities["target_manifest"]["sha256"],
        },
        "asset_closure": {
            "status": "passed",
            "localized_asset_count": 13,
            "source_witness_count": 13,
            "producer_count": 8,
            "localized_text_span_count": 80,
            "deterministic_replays": 2,
            "poppler_same_renderer_pair_count": 13,
            "mupdf_same_renderer_pair_count": 13,
            "manifest": EXPECTED_FIXED_EVIDENCE["asset_manifest"],
            "validation_receipt": EXPECTED_FIXED_EVIDENCE["asset_receipt"],
            "severity_counts": {"P1": 0, "P2": 0, "P3": 0},
        },
        "final_gates": {
            "status": "passed_exact_v4_inputs_stage_only",
            "input_manifest_sha256": context["supplied_sha256"],
            "build_gate_script": supplied_identities["build_gate_script"],
            "candidate_build_qa": supplied_identities["candidate_build_qa"],
            "build_qa": supplied_identities["build_qa"],
            "build_log": supplied_identities["build_log"],
            "build_text": supplied_identities["build_text"],
            "reviewed_candidate_pdf": supplied_identities["pdf"],
            "render_manifest": supplied_identities["render_manifest"],
            "page_locator": supplied_identities["page_locator"],
            "contact_sheet": supplied_identities["contact_sheet"],
            "visual_audit": supplied_identities["visual_audit"],
            "visual_finalizer": supplied_identities["visual_finalizer"],
            "severity_counts": context["final_gate"]["severity_counts"],
            "rendered_page_count": context["final_gate"]["rendered_page_count"],
            "inspected_pages": context["final_gate"]["inspected_pages"],
            "candidate_pdf_promoted": context["final_gate"]["candidate_pdf_promoted"],
        },
        "stage_state": {
            "status": "validated_candidate_not_promoted",
            "live_backend_mutated": False,
            "boundary_admitted": False,
            "promotion_performed": False,
        },
        "record_counts": {name: len(collection) for name, collection in sorted(records.items())},
        "publication_eligibility": "boundary_ready_for_separate_admission",
        "publication_blockers": [],
        "placeholder_count": 0,
        "known_limitations": [
            "Exercises 2.22 and 2.24 have no public upstream answer; explicit O001 independent-original gaps are modeled without accessing or inventing restricted solutions.",
            "Section 2.3 and later remain outside R011-B006 and continue at the next boundary.",
        ],
        "files": file_entries + schema_entries,
    }
    payloads["manifest.json"] = (g.canonical_json(manifest) + "\n").encode("utf-8")
    return payloads


def write_payloads(payloads: dict[str, bytes]) -> None:
    expected_paths = set(payloads)
    if STAGING_EXPORTS.exists():
        for existing in STAGING_EXPORTS.rglob("*"):
            if existing.is_file() and existing.relative_to(STAGING_EXPORTS).as_posix() not in expected_paths:
                existing.unlink()
    for relative_path, raw in sorted(payloads.items()):
        destination = STAGING_EXPORTS / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--final-inputs", type=Path, required=True, help="Exact B006 final-gate input manifest")
    args = parser.parse_args()
    first = build_payloads(args.final_inputs)
    second = build_payloads(args.final_inputs)
    if first != second:
        raise RuntimeError("B006 generator is not deterministic in memory")
    write_payloads(first)
    total_records = sum(json.loads(first["manifest.json"])["record_counts"].values())
    print(f"generated {len(first)} deterministic staged files")
    print(f"typed_records={total_records}")
    print(f"manifest_sha256={g.sha256_bytes(first['manifest.json'])}")
    print("live_backend_mutated=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
