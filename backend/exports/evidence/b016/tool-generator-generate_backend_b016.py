#!/usr/bin/env python3
"""Compile and validate the deterministic R011-B016 modular-backend append.

This module is deliberately inert at import time.  It binds the exact admitted
R011-B015 backend and every frozen B016 source, candidate, terminology, asset,
rights, translation, build, and visual input.  Read-only ``--self-test`` and
``--probe`` modes verify the sealed terminal contract; ``--output`` writes only
a new isolated stage after every exact non-human gate has passed.

No import, self-test, probe, or blocked generation attempt mutates the live
backend, canonical or candidate source, controls, output, release, Git,
network, credential, publication, or upstream state.  Stable keys are based on
source labels, source topology, or explicit locale-neutral boundary codes;
translated wording and page numbers are never identity material.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import shutil
import sys
import unicodedata
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Any

import jsonschema


SCRIPT_PATH = Path(__file__).resolve()
LANE = SCRIPT_PATH.parents[1]
INTERLANGUAGE_ROOT = LANE.parents[2]
BOUNDARY_ID = "R011-B016"
BASE_BOUNDARY_ID = "R011-B015"
SCHEMA_VERSION = "0.1.0"
WORKFLOW_ID = "r011-openintro-statistics-id-b016-backend-final"
RECORDED_AT = "2026-08-25T17:35:10+02:00"
NAMESPACE = uuid.UUID("3f5320fb-d2a2-4aa6-a8fe-298715378407")
PROVENANCE = "OpenAI Codex gpt-5.6-sol, Ultra"

BASE_EXPORTS = LANE / "backend" / "exports"
BASE_MANIFEST = BASE_EXPORTS / "manifest.json"
PREP_ROOT = LANE / "qa" / "b016-backend-prep"
FINAL_ROOT = LANE / "qa" / "b016-backend-final"
TERMINAL_CONTRACT = PREP_ROOT / "R011-B016_TERMINAL_INPUTS.json"

RECORD_PATHS = {
    "programs": "core/programs.jsonl",
    "courses": "core/courses.jsonl",
    "resources": "core/resources.jsonl",
    "editions": "core/editions.jsonl",
    "units": "core/units.jsonl",
    "concepts": "core/concepts.jsonl",
    "segments": "core/segments.jsonl",
    "assets": "core/assets.jsonl",
    "relations": "core/relations.jsonl",
    "rights": "core/rights.jsonl",
    "corrections": "core/corrections.jsonl",
    "localizations": "locales/id-ID/localizations.jsonl",
    "terms": "locales/id-ID/terms.jsonl",
    "qa_events": "evidence/qa_events.jsonl",
    "artifacts": "evidence/artifacts.jsonl",
}

BASE_MANIFEST_IDENTITY = {
    "bytes": 72072,
    "sha256": "9ae96e1d7df724d57c8515474629b4ac8e382c8d0129bcb11591c419d988d88f",
}
BASE_INVENTORY_IDENTITY = {
    "identity_kind": "directory-inventory-tsv-sha256/v1",
    "files": 376,
    "bytes": 175267831,
    "sha256": "76f7fa8bdc3ceca284f5c3809c3427a3516c6cce77ede9604bfb21336fafd298",
}
BASE_RECORD_COUNT = 5590
BASE_RECORD_COUNTS = {
    "artifacts": 358,
    "assets": 349,
    "concepts": 203,
    "corrections": 125,
    "courses": 1,
    "editions": 1,
    "localizations": 489,
    "programs": 1,
    "qa_events": 177,
    "relations": 2653,
    "resources": 1,
    "rights": 41,
    "segments": 489,
    "terms": 216,
    "units": 486,
}
BASE_EVIDENCE = {
    "boundary_receipt": (
        "qa/R011-B015_BOUNDARY_RECEIPT.json",
        14895,
        "e12ad9fa86c0614177c2fc1ea4257d5819d13a914f6c2b186d7ba85274f99dd0",
    ),
    "admission_checkpoint": (
        "00_control/R011-B015_ADMISSION_CHECKPOINT.md",
        1722,
        "8b25ab0bd126b117ba08ea3e4d86120470f9284d4a7c76294d5e797b1b36ee1b",
    ),
    "post_admission_verification": (
        "qa/b015-admission/R011-B015_POST_ADMISSION_VERIFICATION.json",
        2861,
        "2378271401afc768b89a1f5b60bc1fb77d05ea0248a23e5bbcae8c3e0c8cb684",
    ),
}

INTEROPERABILITY_SPEC = {
    "path": (
        "outputs/01a01ec1-e685-70d0-b022-211396334723/curriculum_logbook/"
        "05_MODULAR_BACKEND_INTEROPERABILITY_V0.md"
    ),
    "bytes": 5204,
    "sha256": "fdb6c8fa87ea88d8fcb6ddf40415d8a6a6da315025b9b18eb917190f508b1c5f",
}

# Exact inputs already frozen at preparation time.  Build, assembly, reader,
# and visual identities are intentionally excluded and represented only as
# terminal roles below.
READY_INPUTS: dict[str, tuple[str, int, str]] = {
    "source_closure": (
        "qa/b016-source/R011-B016_SOURCE_CLOSURE.json", 11016,
        "a7da0fe79174fbbfe62f90f1bb7f17cdb5aad058c347adf23d3b0f61490fee8f",
    ),
    "source_closure_validation": (
        "qa/b016-source/R011-B016_CLOSURE_VALIDATION.json", 3742,
        "5340e0209a63d63146298b14cb8901d4e2fcbee88e0b1795e3fcbc5369f2d6a4",
    ),
    "source_closure_builder": (
        "qa/b016-source/build_b016_source_closure.py", 38420,
        "d68a3186580207ed32c2c0706637be8391500b2058261508a107077a38061cf3",
    ),
    "source_closure_manifest": (
        "qa/b016-source/R011-B016_SOURCE_MANIFEST.csv", 7931,
        "41ccf111ab88b1c46d3a249f8d6f91a5903c4573fdef2a5bbf90ef5813c3809d",
    ),
    "source_closure_checksums": (
        "qa/b016-source/R011-B016_CLOSURE_OUTPUT_CHECKSUMS.sha256", 1828,
        "7268a759f4bd2d27fd300373865e61b6498ea09e24b7d587a05ba37d1d5650f1",
    ),
    "main_authority_witness": (
        "qa/b016-source/R011-B016_MAIN_AUTHORITY_LINES_1268-1926.tex", 24451,
        "530585267669f06c551b86dce8345147f3654d716e851c9be5d76facff47b8e5",
    ),
    "eoce_authority_witness": (
        "qa/b016-source/R011-B016_EOCE_17-26_AUTHORITY.tex", 8716,
        "ac032b8749237e2fc3911cb1d007d5555a86d47ecba9ea9937e8f502f50348ff",
    ),
    "public_answers_authority_witness": (
        "qa/b016-source/R011-B016_PUBLIC_ODD_ANSWERS_AUTHORITY_LINES_707-748.tex", 1412,
        "17f8ab6e9a1a9c62bbf1d2bf09567bd66df0f3c8103db5c0fe41cae4ebef5e72",
    ),
    "data_authority_witness": (
        "qa/b016-source/R011-B016_DATA_APPENDIX_AUTHORITY_LINES_277-294.tex", 841,
        "92e13799051af370ea6f5314be4b62c14711322c8d113b64ca93c3a0c44b4ff9",
    ),
    "preboundary_macro_witness": (
        "qa/b016-source/R011-B016_PREBOUNDARY_MACROS_AUTHORITY_LINES_979-982.tex", 126,
        "b161752de6bf8f931db640c5ec18d2b017c73c36ae8fd4463b20bfe6f57aa96e",
    ),
    "bibliography_alcohol_witness": (
        "qa/b016-source/R011-B016_BIB_WEBPAGE_ALCOHOL_LINES_386-388.bib", 165,
        "98ab7a0c882b6b94239f89851dd99f0d007fc3b4ade54fda928d9f9aa34c6844",
    ),
    "bibliography_spiders_witness": (
        "qa/b016-source/R011-B016_BIB_WEBPAGE_SPIDERS_LINES_425-427.bib", 144,
        "1ec7db85b6218ec6fd9f4d1c0e50cee72cf3fbf0655152203de976813818a850",
    ),
    "bibliography_chickenpox_witness": (
        "qa/b016-source/R011-B016_BIB_BOSTON_CHICKENPOX_LINES_833-835.bib", 199,
        "f43639e1599c8fcd2eba2c9bdb37030cbb873201a12f665e794a55487106bfef",
    ),
    "source_o001_contract": (
        "qa/b016-source/R011-B016_O001_GAP_CONTRACT.json", 749,
        "4cc986cfb9e06e3ec92868b3ec4588fbf95dbd5f91cf3d0db537abb7cf93c534",
    ),
    "asset_manifest": (
        "qa/b016-assets/R011-B016_ASSET_MANIFEST.csv", 6109,
        "0055e1db8efaf6178097e09dde69040acb0f65514b7a3ce6f2aeaa505a86a811",
    ),
    "asset_rights_closure": (
        "qa/b016-assets/R011-B016_ASSET_RIGHTS_CLOSURE.json", 6800,
        "9c202cb46e9dba5cdc7de172c39654866d938d9f3db2d5e9f3cfd45716772fab",
    ),
    "controlled_terms": (
        "qa/b016-terminology/R011-B016_CONTROLLED_TERMS.tsv", 4525,
        "a24dbeb63cc74ec4e851a4eeb7e79ca04ca384aed6e2ec54cb5cb10cf8950ebc",
    ),
    "terminology_qa": (
        "qa/b016-terminology/R011-B016_TERMINOLOGY_QA.json", 4654,
        "01c2dfc92b64a1e1c8e07eee66936049405332777a8f255b34063c3664d82c8d",
    ),
    "translation_qa": (
        "qa/b016-translation/R011-B016_TRANSLATION_QA.json", 64573,
        "b372074c52cad8e3a730ad88320c66eee4e0fd7833f707cfeea45fb4d3a05c34",
    ),
    "translation_verifier": (
        "qa/b016-translation/verify_b016_translation.py", 43500,
        "e1c6b50d5ae37af187ea15a51ffb915d1fdba5a3ba6832d82cdfba9844ccd17a",
    ),
    "translation_finalizer": (
        "qa/b016-translation/finalize_b016_translation_qa.py", 2227,
        "82c1c746fdc89a7d43704feba6e8d99799a0139a9e264ca202513ce686d922e5",
    ),
    "main_fragment": (
        "scratch/b016-candidate/ch_distributions_section_4_3_id.tex", 25367,
        "8d99fee42d7f998cf7af6c3c7406457f503fdecd940b5985ca3aa63c4091d6ef",
    ),
    "eoce_fragment": (
        "scratch/b016-candidate/binomial_distribution_B016.tex", 9271,
        "e7030cb0c07cffb5881909e79edbfa2476e22abce5fb45e8e9cb62b869841768",
    ),
    "public_answers_fragment": (
        "scratch/b016-candidate/R011-B016_PUBLIC_ODD_ANSWERS.tex", 1605,
        "d6b6ac7470d65fafdd7382004b43019f8f92029d717aa9f5a51b4327d173244c",
    ),
    "data_appendix_fragment": (
        "scratch/b016-candidate/data_binomialModel_B016.tex", 956,
        "beddd03e4cca459911d425c17094eaea8aa8860b9ac922aa829337c109ec214c",
    ),
    "candidate_o001_gaps": (
        "scratch/b016-candidate/R011-B016_O001_GAPS.json", 1571,
        "293f1eead83affc4a0197a3a8838affdd8698da39e93be78be3513dcd3872266",
    ),
    "companion_verifier": (
        "scratch/b016-candidate/verify_b016_companion.py", 11333,
        "c59fea171067fd0cfef13b18c612df864212acee8ebecd754c016442a8b7f421",
    ),
    "main_candidate_receipt": (
        "scratch/b016-candidate/R011-B016_MAIN_TRANSLATION_CANDIDATE_RECEIPT.json", 6775,
        "39a6b26a67657db3b40b1eb1d8d9afecad66dc63fe7c1e04c3989f662cdb134d",
    ),
    "companion_receipt": (
        "scratch/b016-candidate/R011-B016_COMPANION_RECEIPT.json", 4999,
        "946da79575ad52f355d2e5db0795374df649e9d296a6016bd7a1b128f34ee0db",
    ),
    "term_notes": (
        "scratch/b016-candidate/R011-B016_TERM_NOTES.md", 3789,
        "2898e9cb72a3dc41fb4c8e89d90e2d6ff7524b7da3fc4d96fa2c25c2418c139f",
    ),
    "main_authority": (
        "authority/upstream/openintro-statistics-fee25091fb24e89c36296fd67c48c1fcf7a93b6e/ch_distributions/TeX/ch_distributions.tex", 91188,
        "71e4985a1bf31e9dd6897ec2bd246b3b2f8cd62ab55524a5b1bfe791e613a3a9",
    ),
    "eoce_authority": (
        "authority/upstream/openintro-statistics-fee25091fb24e89c36296fd67c48c1fcf7a93b6e/ch_distributions/TeX/binomial_distribution.tex", 8716,
        "ac032b8749237e2fc3911cb1d007d5555a86d47ecba9ea9937e8f502f50348ff",
    ),
    "public_answers_authority": (
        "authority/upstream/openintro-statistics-fee25091fb24e89c36296fd67c48c1fcf7a93b6e/extraTeX/eoceSolutions/eoceSolutions.tex", 106045,
        "6c4e01376db4c023cc7b3f9949490e57220ef1cb831c580da71efde6ce723268",
    ),
    "data_authority": (
        "authority/upstream/openintro-statistics-fee25091fb24e89c36296fd67c48c1fcf7a93b6e/extraTeX/data/data.tex", 26134,
        "6456ef7e9d0f855dbba47f9f62f0f10ae731d4f7cd558399848419d3cbdfd88b",
    ),
    "four_models_source_r": (
        "authority/upstream/openintro-statistics-fee25091fb24e89c36296fd67c48c1fcf7a93b6e/ch_distributions/figures/fourBinomialModelsShowingApproxToNormal/fourBinomialModelsShowingApproxToNormal.R", 728,
        "3c059f39a129735450b44215c52e31452ed30800a61f405f95701771499b110e",
    ),
    "four_models_source_pdf": (
        "authority/upstream/openintro-statistics-fee25091fb24e89c36296fd67c48c1fcf7a93b6e/ch_distributions/figures/fourBinomialModelsShowingApproxToNormal/fourBinomialModelsShowingApproxToNormal.pdf", 5957,
        "a8224e53f7961fd869932d050902cbb081e03b74746f4f839af6b466912a9736",
    ),
    "normal_failure_source_r": (
        "authority/upstream/openintro-statistics-fee25091fb24e89c36296fd67c48c1fcf7a93b6e/ch_distributions/figures/normApproxToBinomFail/normApproxToBinomFail.R", 761,
        "a846b551d5441d4f05d3c29971a3c4ab0318e9e80fde921a66c415ad63f7669b",
    ),
    "normal_failure_source_pdf": (
        "authority/upstream/openintro-statistics-fee25091fb24e89c36296fd67c48c1fcf7a93b6e/ch_distributions/figures/normApproxToBinomFail/normApproxToBinomFail.pdf", 29317,
        "a9eb12774094b1e7e30a16ac69539b56af6d8a0bc803104637babf44b275af03",
    ),
    "dreidel_source_photo": (
        "authority/upstream/openintro-statistics-fee25091fb24e89c36296fd67c48c1fcf7a93b6e/ch_distributions/figures/eoce/dreidel/dreidel.jpg", 377280,
        "4f86ab4609fa8e8e484095449da09fb344c88578de1ebc61b3e19e7eb3e30099",
    ),
    "openintro_package_archive": (
        "authority/external/r-packages/openintro-48793d9645e0da033daaca1c1a19a051533d79d2/openintro-48793d9645e0da033daaca1c1a19a051533d79d2.tar.gz", 21248412,
        "e8b9526364e70ca59d945fc83eadfd1d25eb784e3190429637f96bfe72b6dc99",
    ),
    "openintro_package_manifest": (
        "authority/external/r-packages/openintro-48793d9645e0da033daaca1c1a19a051533d79d2/AUTHORITY_MANIFEST.json", 2572,
        "c4b980f73c19e51c09b3843330a3fc4121dcfa0e74c91cf068ff4827f40da9f1",
    ),
    "component_rights_control": (
        "00_control/COMPONENT_RIGHTS.csv", 9999,
        "009feba8ff1f329ef742793f55f6b090dd08f3f761f9b9cc1edcbe03ecff58f0",
    ),
    "admitted_terminology_view": (
        "backend/exports/views/terminology.csv", 37366,
        "3bb72d7f41aa781c2c43e385357c6df7bcbeab022b6f391dc0c2affbba74ff05",
    ),
    "current_terminology_control": (
        "00_control/TERMINOLOGY.csv", 14120,
        "274cd6068a0eddb9f4f845f388ecabbf1781cc25510ee8826731e5279ebd72b8",
    ),
    "indonesian_probability_field_witness": (
        "authority/terminology/2026-08-23/Ansori-Fajriah-Suryaningsih-2021-Teori-Peluang.txt", 386031,
        "9b166a905c99a321eef25e2cc6932a5573037ae9441a866282d08154cd491707",
    ),
}

PENDING_TERMINAL_ROLES = {
    "candidate_builder": "isolated B016 assembler and deterministic reader-build implementation",
    "assembled_main": "assembled Chapter 4 source containing exactly the accepted Section 4.3 fragment",
    "assembled_eoce": "assembled binomial-distribution EoCE source containing exercises 17--26",
    "assembled_public_answers": "assembled public-solutions source containing answers 17/19/21/23/25",
    "assembled_data_appendix": "assembled data appendix containing the three binomialModel entries",
    "source_manifest": "fresh isolated B016 source-snapshot inventory",
    "source_qa": "typed overlay, topology, mathematics, source-identity, and asset-reuse QA receipt",
    "build_receipt": "typed deterministic isolated B016 reader-build receipt",
    "reader_pdf": "fresh deterministic isolated B016 reader PDF",
    "visual_qa": "typed bounded visual QA for section, figures, exercises, answers, data, and transitions",
}

REQUIRED_TERMINAL_GATES = {
    "assembly",
    "source",
    "mathematics",
    "topology",
    "terminology",
    "asset_identity",
    "asset_rights",
    "build_determinism",
    "visual",
}

EXPECTED_TERMINAL_CLOSURE = {
    "authority_commit": "fee25091fb24e89c36296fd67c48c1fcf7a93b6e",
    "authority_tree": "d61cc601e7d97759ce805900520f784d02a0489e",
    "source_anchor": "binomialModel",
    "next_source_anchor": "negativeBinomial",
    "next_source_line": 1927,
    "subsections": 3,
    "worked_examples": 4,
    "guided_exercises": 10,
    "guided_inline_answers": 10,
    "eoce_exercises": list(range(17, 27)),
    "public_answers": [17, 19, 21, 23, 25],
    "o001_companion_gaps": [18, 20, 22, 24, 26],
    "data_appendix_entries": 3,
    "reused_locale_neutral_r_pdf_pairs": 2,
    "reused_separately_licensed_photos": 1,
    "source_corrections": ["B016-SC001", "B016-SC003", "B016-SC004", "B016-SC005"],
    "controlled_term_decisions": 27,
    "reader_pdf_pages": 428,
    "visual_defects": 0,
    "restricted_solutions_accessed_or_invented": False,
    "rights_closed": True,
}
TERMINAL_CONTRACT_IDENTITY: dict[str, Any] | None = {
    "bytes": 3398,
    "sha256": "9610d8492fb717bf4d1c9f72a5627323e3506df2b7cd1180ff05016f963edb3f",
}

EOCE = {
    17: "underage_drinking_intro",
    18: "chicken_pox_intro",
    19: "underage_drinking_normal_approx",
    20: "chicken_pox_normal_approx",
    21: "dreidel",
    22: "arachnophobia",
    23: "eye_color_binomial",
    24: "sickle_cell_anemia",
    25: "explore_combinations",
    26: "male_children",
}
PUBLIC_ANSWERS = (17, 19, 21, 23, 25)
O001_GAPS = (18, 20, 22, 24, 26)

# Explicit locale-neutral semantic codes.  Source/target terminology remains
# data in the TSV and never participates in stable identity construction.
TERM_CONCEPT_KEYS = {
    "B016-TM001": "r011/concept/b016/c001",
    "B016-TM002": "r011/concept/b016/c002",
    "B016-TM003": "r011/concept/b016/c003",
    "B016-TM004": "r011/concept/b016/c004",
    "B016-TM005": "r011/concept/b015/c004",
    "B016-TM006": "r011/concept/b015/c005",
    "B016-TM007": "r011/concept/b016/c007",
    "B016-TM008": "r011/concept/b016/c008",
    "B016-TM009": "r011/concept/b015/c006",
    "B016-TM010": "r011/concept/b015/c007",
    "B016-TM011": "r011/concept/b015/c008",
    "B016-TM012": "r011/concept/b016/c012",
    "B016-TM013": "r011/concept/b016/c013",
    "B016-TM014": "r011/concept/b016/c014",
    "B016-TM015": "r011/concept/b016/c015",
    "B016-TM016": "r011/concept/b016/c016",
    "B016-TM017": "r011/concept/b016/c017",
    "B016-TM018": "r011/concept/b016/c018",
    "B016-TM019": "r011/concept/b016/c019",
    "B016-TM020": "r011/concept/b014/mean",
    "B016-TM021": "r011/concept/b012/variance",
    "B016-TM022": "r011/concept/b014/standard-deviation",
    "B016-TM023": "r011/concept/right-skewed",
    "B016-TM024": "r011/concept/b016/c024",
    "B016-TM025": "r011/concept/b016/c025",
    "B016-TM026": "r011/concept/b016/c026",
    "B016-TM027": "r011/concept/b016/c027",
}

# SC002 was withdrawn after exact authority reinspection.  Retaining the
# surviving codes prevents a corrected source audit from silently renumbering
# already recorded findings.
CORRECTION_CODES = (
    "B016-SC001",
    "B016-SC003",
    "B016-SC004",
    "B016-SC005",
)
CORRECTION_CODE_BY_SOURCE = {
    "As the last stage use software": "B016-SC001",
    "in last hollow histogram": "B016-SC003",
    "SAMSHA": "B016-SC004",
    "will the be the 3rd child": "B016-SC005",
}

SEMANTIC_BLUEPRINT = {
    "section": "r011/unit/source-label/binomialModel",
    "subsections": [f"r011/unit/b016/subsection-{number:02d}" for number in range(1, 4)],
    "worked_examples": [
        "r011/unit/source-label/insureOneOfFourExceedsDeductible",
        "r011/unit/source-label/noMoreThanOneFriendWSevereLungCondition",
        "r011/unit/source-label/exactBinomSmokerExSetup",
        "r011/unit/source-label/approxNormalForSmokerBinomEx",
    ],
    "guided_exercises": [f"r011/unit/guided-exercise/ch04-sec4.3-{number:02d}" for number in range(1, 11)],
    "guided_inline_answers": [f"r011/unit/guided-solution/ch04-sec4.3-{number:02d}" for number in range(1, 11)],
    "eoce_exercises": [f"r011/unit/exercise/4.{number}/{EOCE[number]}" for number in sorted(EOCE)],
    "public_answers": [f"r011/unit/solution/4.{number}" for number in PUBLIC_ANSWERS],
    "o001_companion_gaps": [f"r011/unit/o001-gap/4.{number}" for number in O001_GAPS],
    "data_appendix": [f"r011/unit/data-appendix/source-ref/binomialModel-{number:02d}" for number in range(1, 4)],
    "assets": [
        "r011/asset/b016/source-r/fourBinomialModelsShowingApproxToNormal",
        "r011/asset/b016/source-pdf/fourBinomialModelsShowingApproxToNormal",
        "r011/asset/b016/source-r/normApproxToBinomFail",
        "r011/asset/b016/source-pdf/normApproxToBinomFail",
        "r011/asset/b016/source-photo/dreidel",
    ],
    "corrections": [f"r011/correction/b016/{code}" for code in CORRECTION_CODES],
    "terms": [f"r011/term/id-ID/b016/TM{number:03d}" for number in range(1, 28)],
    "concept_prerequisites": [
        ["r011/concept/probability", "r011/concept/b016/c001"],
        ["r011/concept/b015/c004", "r011/concept/b016/c003"],
        ["r011/concept/b015/c005", "r011/concept/b016/c003"],
        ["r011/concept/independent", "r011/concept/b016/c007"],
        ["r011/concept/b016/c007", "r011/concept/b016/c003"],
        ["r011/concept/b016/c008", "r011/concept/b016/c003"],
        ["r011/concept/b015/c008", "r011/concept/b016/c003"],
        ["r011/concept/b016/c003", "r011/concept/b016/c004"],
        ["r011/concept/b016/c004", "r011/concept/b016/c001"],
        ["r011/concept/b016/c019", "r011/concept/b016/c017"],
        ["r011/concept/b014/mean", "r011/concept/b016/c017"],
        ["r011/concept/b014/standard-deviation", "r011/concept/b016/c017"],
    ],
    "unit_prerequisites": [
        ["r011/unit/source-label/randomVariablesSection", "r011/unit/source-label/binomialModel"]
    ],
    "hierarchy_parent": "r011/unit/source-label/ch_distributions",
    "predecessor": "r011/unit/source-label/geomDist",
    "next_source_anchor": "r011/unit/source-label/negativeBinomial",
    "relation_classes": [
        "contains", "precedes", "prerequisite", "covers", "lexicalizes",
        "unit_contains_segment", "localizes", "answers",
        "requires_companion_answer", "uses_asset", "produces", "depends_on",
        "corrects", "governs", "validates", "documents",
    ],
    "qa_event_types": [
        "base_preservation", "source", "translation", "terminology", "asset_identity",
        "rights", "mathematics", "topology", "build", "visual", "corrections",
        "interoperability", "isolation",
    ],
    "required_views": [
        "views/resource_editions.csv", "views/unit_hierarchy.csv", "views/relations.csv",
        "views/segments_locale.csv", "views/terminology.csv", "views/exercises_answers.csv",
        "views/rights_components.csv", "views/corrections.csv",
        "views/qa_build_events.csv", "views/artifacts.csv",
    ],
}

PREDICTED_RECORD_CLASSES = [
    "unit", "concept", "segment", "localization", "term", "asset", "relation",
    "rights", "correction", "qa_event", "artifact",
]
REUSED_RECORD_CLASSES = ["program", "course", "resource", "edition"]


class TerminalInputsUnresolved(RuntimeError):
    """The exact terminal contract is absent, incomplete, or unbound."""


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def stable_id(stable_key: str) -> str:
    return str(uuid.uuid5(NAMESPACE, stable_key))


def normalize(value: Any) -> Any:
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, list):
        return [normalize(item) for item in value]
    if isinstance(value, dict):
        return {normalize(str(key)): normalize(item) for key, item in value.items()}
    return value


def canonical_json_text(value: Any) -> str:
    return json.dumps(
        normalize(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def backend_record(record_type: str, stable_key: str, **fields: Any) -> dict[str, Any]:
    row = {
        "$schema": "schemas/backend-record-v0.1.0.schema.json",
        "schema_version": SCHEMA_VERSION,
        "record_type": record_type,
        "id": stable_id(stable_key),
        "stable_key": stable_key,
        "status": "active",
        "recorded_at": RECORDED_AT,
        "workflow_id": WORKFLOW_ID,
        "supersedes_id": None,
    }
    row.update(fields)
    return normalize(row)


def jsonl_bytes(rows: list[dict[str, Any]]) -> bytes:
    return "".join(
        canonical_json_text(row) + "\n" for row in sorted(rows, key=lambda item: item["id"])
    ).encode("utf-8")


def load_jsonl(raw: bytes) -> list[dict[str, Any]]:
    return [json.loads(line) for line in raw.decode("utf-8").splitlines() if line]


def csv_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, dict)):
        return canonical_json_text(value)
    return str(value)


def csv_bytes(columns: list[str], rows: list[dict[str, Any]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream, fieldnames=columns, lineterminator="\n", extrasaction="ignore"
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({column: csv_cell(row.get(column)) for column in columns})
    return stream.getvalue().encode("utf-8")


def one(
    records: dict[str, list[dict[str, Any]]], name: str, stable_key: str
) -> dict[str, Any]:
    rows = [row for row in records[name] if row.get("stable_key") == stable_key]
    if len(rows) != 1:
        raise RuntimeError(
            f"expected one {name} record {stable_key!r}, found {len(rows)}"
        )
    return rows[0]


def identity(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise RuntimeError(f"missing exact input: {path}")
    raw = path.read_bytes()
    return {"bytes": len(raw), "sha256": sha256_bytes(raw)}


def require(path: Path, expected: dict[str, Any]) -> bytes:
    raw = path.read_bytes() if path.is_file() else None
    observed = None if raw is None else {"bytes": len(raw), "sha256": sha256_bytes(raw)}
    wanted = {"bytes": int(expected["bytes"]), "sha256": str(expected["sha256"])}
    if observed != wanted:
        raise RuntimeError(f"exact identity mismatch for {path}: {observed!r} != {wanted!r}")
    assert raw is not None
    return raw


def inventory(root: Path) -> dict[str, Any]:
    rows: list[tuple[str, int, str]] = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            raw = path.read_bytes()
            rows.append((path.relative_to(root).as_posix(), len(raw), sha256_bytes(raw)))
    payload = "".join(
        f"{relative}\t{size}\t{digest}\n" for relative, size, digest in rows
    ).encode("utf-8")
    return {
        "identity_kind": "directory-inventory-tsv-sha256/v1",
        "files": len(rows),
        "bytes": sum(size for _relative, size, _digest in rows),
        "sha256": sha256_bytes(payload),
    }


def parse_json(raw: bytes, role: str) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"invalid UTF-8 JSON for {role}: {exc}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"expected JSON object for {role}")
    return value


def parse_tsv(raw: bytes, role: str) -> list[dict[str, str]]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RuntimeError(f"invalid UTF-8 TSV for {role}: {exc}") from exc
    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    rows = list(reader)
    expected = {"source_term", "preferred_id-ID", "accepted_synonyms", "evidence", "use_in_B016"}
    if set(reader.fieldnames or ()) != expected:
        raise RuntimeError(f"unexpected controlled-term columns: {reader.fieldnames!r}")
    return rows


def line_table(raw: bytes) -> tuple[list[bytes], list[int]]:
    lines = raw.splitlines(keepends=True)
    starts: list[int] = []
    cursor = 0
    for line in lines:
        starts.append(cursor)
        cursor += len(line)
    return lines, starts


def span_meta(raw: bytes, start: int, end: int) -> dict[str, Any]:
    if not 0 <= start < end <= len(raw):
        raise RuntimeError(f"invalid span {start}:{end}/{len(raw)}")
    _lines, starts = line_table(raw)
    first = max(
        0,
        next((index for index, value in enumerate(starts) if value > start), len(starts))
        - 1,
    )
    last = max(
        0,
        next((index for index, value in enumerate(starts) if value >= end), len(starts))
        - 1,
    )
    return {
        "line_start": first + 1,
        "line_end": last + 1,
        "byte_start": start,
        "byte_end_exclusive": end,
        "bytes": end - start,
        "sha256": sha256_bytes(raw[start:end]),
    }


def line_span_meta(raw: bytes, line_number: int) -> dict[str, Any]:
    lines, starts = line_table(raw)
    if not 1 <= line_number <= len(lines):
        raise RuntimeError(f"line {line_number} outside 1..{len(lines)}")
    start = starts[line_number - 1]
    return span_meta(raw, start, start + len(lines[line_number - 1]))


def schema_span(meta: dict[str, Any]) -> dict[str, int]:
    return {
        key: int(meta[key])
        for key in ("line_start", "line_end", "byte_start", "byte_end_exclusive")
    }


def rebase_span(meta: dict[str, Any], full_raw: bytes, offset: int) -> dict[str, Any]:
    return span_meta(
        full_raw,
        offset + int(meta["byte_start"]),
        offset + int(meta["byte_end_exclusive"]),
    )


def unique_offset(haystack: bytes, needle: bytes, role: str) -> int:
    start = haystack.find(needle)
    if start < 0 or haystack.find(needle, start + 1) >= 0:
        raise RuntimeError(f"{role} is not a unique exact subspan")
    return start


def balanced_command_end(raw: bytes, start: int, command: bytes) -> int:
    open_at = raw.find(b"{", start + len(command))
    if open_at < 0:
        raise RuntimeError(f"missing argument for {command!r}")
    depth = 0
    for index in range(open_at, len(raw)):
        token = raw[index : index + 1]
        escaped = index > 0 and raw[index - 1 : index] == b"\\"
        if token == b"{" and not escaped:
            depth += 1
        elif token == b"}" and not escaped:
            depth -= 1
            if depth == 0:
                return index + 1
    raise RuntimeError(f"unterminated argument for {command!r}")


def structural_spans(raw: bytes) -> list[dict[str, Any]]:
    """Split Section 4.3 at stable semantic wrappers, never translated text."""
    blocks: list[tuple[int, int, str, int]] = []
    for begin, end_token, kind, expected in (
        (b"\\begin{examplewrap}", b"\\end{examplewrap}", "worked_example", 4),
        (b"\\begin{exercisewrap}", b"\\end{exercisewrap}", "guided_exercise", 10),
    ):
        cursor = count = 0
        while True:
            start = raw.find(begin, cursor)
            if start < 0:
                break
            close = raw.find(end_token, start + len(begin))
            if close < 0:
                raise RuntimeError(f"unterminated {kind}")
            end = close + len(end_token)
            end += 2 if raw[end : end + 2] == b"\r\n" else (
                1 if raw[end : end + 1] == b"\n" else 0
            )
            count += 1
            blocks.append((start, end, kind, count))
            cursor = end
        if count != expected:
            raise RuntimeError(f"B016 {kind} count changed: {count} != {expected}")

    cursor = count = 0
    command = b"\\footnotetext"
    while True:
        start = raw.find(command, cursor)
        if start < 0:
            break
        end = balanced_command_end(raw, start, command)
        end += 2 if raw[end : end + 2] == b"\r\n" else (
            1 if raw[end : end + 1] == b"\n" else 0
        )
        count += 1
        blocks.append((start, end, "guided_inline_answer", count))
        cursor = end
    if count != 10:
        raise RuntimeError(f"B016 inline-answer count changed: {count} != 10")

    blocks.sort()
    if any(left[1] > right[0] for left, right in zip(blocks, blocks[1:])):
        raise RuntimeError("overlapping B016 semantic blocks")
    result: list[dict[str, Any]] = []
    cursor = prose = 0
    for start, end, kind, number in blocks:
        if raw[cursor:start].strip():
            prose += 1
            result.append(
                {
                    "kind": "section_prose",
                    "number": prose,
                    "span": span_meta(raw, cursor, start),
                }
            )
        result.append(
            {"kind": kind, "number": number, "span": span_meta(raw, start, end)}
        )
        cursor = end
    if raw[cursor:].strip():
        prose += 1
        result.append(
            {
                "kind": "section_prose",
                "number": prose,
                "span": span_meta(raw, cursor, len(raw)),
            }
        )
    if prose != 9:
        raise RuntimeError(f"B016 prose segmentation changed: {prose} != 9")
    return result


def subsection_spans(raw: bytes) -> list[dict[str, Any]]:
    matches = list(re.finditer(rb"\\subsection\{([^}]+)\}", raw))
    if len(matches) != 3:
        raise RuntimeError(f"B016 subsection topology changed: {len(matches)} != 3")
    return [
        {
            "number": index + 1,
            "span": span_meta(
                raw,
                match.start(),
                matches[index + 1].start() if index + 1 < len(matches) else len(raw),
            ),
        }
        for index, match in enumerate(matches)
    ]


def marker_spans(raw: bytes, numbers: list[int]) -> dict[int, dict[str, Any]]:
    wanted = set(numbers)
    lines, starts = line_table(raw)
    found: list[tuple[int, int]] = []
    for index, line in enumerate(lines):
        match = re.fullmatch(rb"%\s*(\d+)\r?\n?", line)
        if match and int(match.group(1)) in wanted:
            found.append((int(match.group(1)), starts[index]))
    if [number for number, _start in found] != numbers:
        raise RuntimeError(
            f"marker topology changed: {[number for number, _ in found]} != {numbers}"
        )
    result: dict[int, dict[str, Any]] = {}
    for index, (number, start) in enumerate(found):
        end = found[index + 1][1] if index + 1 < len(found) else len(raw)
        while end > start and raw[end - 1 : end] in (b"\n", b"\r", b" ", b"\t"):
            end -= 1
        result[number] = span_meta(raw, start, end)
    return result


def repeated_command_spans(raw: bytes, command: bytes, expected: int) -> list[dict[str, Any]]:
    starts: list[int] = []
    cursor = 0
    while True:
        start = raw.find(command, cursor)
        if start < 0:
            break
        starts.append(start)
        cursor = start + len(command)
    if len(starts) != expected:
        raise RuntimeError(
            f"{command!r} topology changed: {len(starts)} != {expected}"
        )
    rows = []
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(raw)
        while end > start and raw[end - 1 : end] in (b"\n", b"\r", b" ", b"\t"):
            end -= 1
        rows.append({"number": index + 1, "span": span_meta(raw, start, end)})
    return rows


def containing_subsection(
    meta: dict[str, Any], subsection_rows: list[dict[str, Any]]
) -> int | None:
    start = int(meta["byte_start"])
    for row in subsection_rows:
        span = row["span"]
        if int(span["byte_start"]) <= start < int(span["byte_end_exclusive"]):
            return int(row["number"])
    return None


def bind_base() -> dict[str, Any]:
    for relative, size, digest in BASE_EVIDENCE.values():
        require(LANE / relative, {"bytes": size, "sha256": digest})
    manifest = parse_json(require(BASE_MANIFEST, BASE_MANIFEST_IDENTITY), "base manifest")
    if manifest.get("boundary_id") != BASE_BOUNDARY_ID:
        raise RuntimeError("live base boundary is not exact admitted R011-B015")
    if manifest.get("backend_name") != "r011-openintro-statistics-id-b015-final-isolated":
        raise RuntimeError("live base backend name changed")
    if manifest.get("namespace_uuid") != str(NAMESPACE):
        raise RuntimeError("base namespace UUID changed")
    if manifest.get("record_count") != BASE_RECORD_COUNT:
        raise RuntimeError("base record count changed")
    if manifest.get("record_counts") != BASE_RECORD_COUNTS:
        raise RuntimeError("base record-class counts changed")
    observed_inventory = inventory(BASE_EXPORTS)
    if observed_inventory != BASE_INVENTORY_IDENTITY:
        raise RuntimeError(f"base inventory changed: {observed_inventory!r}")
    return {
        "boundary_id": BASE_BOUNDARY_ID,
        "backend_name": manifest["backend_name"],
        "manifest": {"path": "backend/exports/manifest.json", **BASE_MANIFEST_IDENTITY},
        "inventory": observed_inventory,
        "record_count": BASE_RECORD_COUNT,
        "record_counts": BASE_RECORD_COUNTS,
        "preservation_rule": "all 5,590 admitted record canonical bytes must remain identical by UUID",
    }


def bind_ready_inputs() -> dict[str, dict[str, Any]]:
    require(INTERLANGUAGE_ROOT / INTEROPERABILITY_SPEC["path"], INTEROPERABILITY_SPEC)
    bound: dict[str, dict[str, Any]] = {}
    raw_inputs: dict[str, bytes] = {}
    for role, (relative, size, digest) in sorted(READY_INPUTS.items()):
        raw = require(LANE / relative, {"bytes": size, "sha256": digest})
        raw_inputs[role] = raw
        bound[role] = {"path": relative, "bytes": size, "sha256": digest}

    source = parse_json(raw_inputs["source_closure"], "source_closure")
    source_validation = parse_json(
        raw_inputs["source_closure_validation"], "source_closure_validation"
    )
    assets = parse_json(raw_inputs["asset_rights_closure"], "asset_rights_closure")
    terminology = parse_json(raw_inputs["terminology_qa"], "terminology_qa")
    translation = parse_json(raw_inputs["translation_qa"], "translation_qa")
    main_receipt = parse_json(raw_inputs["main_candidate_receipt"], "main_candidate_receipt")
    companion = parse_json(raw_inputs["companion_receipt"], "companion_receipt")
    o001 = parse_json(raw_inputs["candidate_o001_gaps"], "candidate_o001_gaps")

    passing_objects = {
        "source": source,
        "source_validation": source_validation,
        "assets": assets,
        "terminology": terminology,
        "translation": translation,
        "companion": companion,
    }
    for role, value in passing_objects.items():
        if value.get("boundary_id") != BOUNDARY_ID:
            raise RuntimeError(f"{role} boundary changed")
        if not str(value.get("status", "")).startswith("PASS_"):
            raise RuntimeError(f"{role} no longer records a passing state")
    if main_receipt.get("boundary_id") != BOUNDARY_ID or main_receipt.get("status") != (
        "COMPLETE_MAIN_SECTION_TRANSLATION_CANDIDATE_READY_FOR_BOUNDED_ASSEMBLY"
    ):
        raise RuntimeError("main candidate receipt state changed")

    main_boundary = source.get("main_boundary", {})
    if main_boundary.get("start", {}).get("label") != "binomialModel":
        raise RuntimeError("B016 source start anchor changed")
    if main_boundary.get("start", {}).get("line") != 1268:
        raise RuntimeError("B016 source start line changed")
    if main_boundary.get("next_cursor", {}).get("label") != "negativeBinomial":
        raise RuntimeError("B016 next cursor changed")
    if main_boundary.get("next_cursor", {}).get("line") != 1927:
        raise RuntimeError("B016 next cursor line changed")

    topology = source.get("source_topology", {})
    main_topology = topology.get("main", {})
    expected_main = {
        "sections": 1,
        "subsections": 3,
        "examples": 4,
        "guided_exercises": 10,
        "inline_footnote_answers": 10,
        "figures": 2,
    }
    for key, expected in expected_main.items():
        if main_topology.get(key) != expected:
            raise RuntimeError(f"B016 main topology changed for {key}")
    eoce = topology.get("end_of_chapter_exercises", {})
    if eoce.get("exercise_ids") != sorted(EOCE) or eoce.get("exercise_count") != 10:
        raise RuntimeError("B016 EoCE topology changed")
    if eoce.get("labels") != [EOCE[number] for number in sorted(EOCE)]:
        raise RuntimeError("B016 EoCE label order changed")
    if topology.get("public_answers", {}).get("exercise_ids") != list(PUBLIC_ANSWERS):
        raise RuntimeError("B016 public-answer topology changed")
    if topology.get("o001_gaps", {}).get("exercise_ids") != list(O001_GAPS):
        raise RuntimeError("B016 O001 topology changed")
    if topology.get("data_appendix", {}).get("entry_count") != 3:
        raise RuntimeError("B016 data-appendix topology changed")
    source_corrections = source.get("high_confidence_source_corrections_for_translation", [])
    if len(source_corrections) != len(CORRECTION_CODES):
        raise RuntimeError("B016 frozen source-correction topology changed")
    observed_correction_sources = {
        str(item.get("source")) for item in source_corrections
    }
    if observed_correction_sources != set(CORRECTION_CODE_BY_SOURCE):
        raise RuntimeError("B016 exact surviving correction-source set changed")
    if source.get("rights_and_exclusions", {}).get("restricted_instructor_solutions") != (
        "not sought or ingested"
    ):
        raise RuntimeError("restricted-solution exclusion changed")

    closure_counts = assets.get("closure_counts", {})
    if closure_counts != {
        "adjacent_r_producers": 2,
        "authority_live_pairs_verified": 5,
        "direct_reader_assets": 3,
        "external_dataset_reads_by_r_producers": 0,
        "external_package_archives": 1,
    }:
        raise RuntimeError("B016 asset/right closure counts changed")
    if assets.get("rights_decisions", {}).get("dreidel_photo") != (
        "separately governed CC BY 2.0 component"
    ):
        raise RuntimeError("dreidel component-rights decision changed")
    direct_pdfs = assets.get("direct_pdf_inspection", {})
    if set(direct_pdfs) != {
        "fourBinomialModelsShowingApproxToNormal", "normApproxToBinomFail"
    }:
        raise RuntimeError("B016 direct-PDF asset set changed")
    if any("Reuse byte-exact" not in item.get("localization_decision", "") for item in direct_pdfs.values()):
        raise RuntimeError("B016 locale-neutral PDF reuse decision changed")

    term_rows = parse_tsv(raw_inputs["controlled_terms"], "controlled_terms")
    if len(term_rows) != len(TERM_CONCEPT_KEYS) or terminology.get("decision_count") != len(TERM_CONCEPT_KEYS):
        raise RuntimeError("B016 controlled-term decision count changed")
    if len({row["source_term"] for row in term_rows}) != len(TERM_CONCEPT_KEYS):
        raise RuntimeError("B016 controlled source terms are not unique")
    if terminology.get("candidate_alignment", {}).get("conflicts") != []:
        raise RuntimeError("B016 terminology conflicts appeared")
    if terminology.get("candidate_alignment", {}).get("uncontrolled_reader_term_introductions") != []:
        raise RuntimeError("B016 uncontrolled reader terminology appeared")

    coverage = main_receipt.get("coverage", {})
    expected_coverage = {
        "subsections": 3,
        "worked_examples": 4,
        "guided_exercises": 10,
        "guided_inline_answers": 10,
    }
    for key, expected in expected_coverage.items():
        if coverage.get(key) != expected:
            raise RuntimeError(f"B016 candidate coverage changed for {key}")
    if main_receipt.get("next_cursor", {}).get("label") != "negativeBinomial":
        raise RuntimeError("B016 candidate next cursor changed")
    if main_receipt.get("deterministic_qa", {}).get("checks", {}).get(
        "protected_math_token_sequence_exact"
    ) is not True:
        raise RuntimeError("B016 protected-math token QA is not passing")
    if len(main_receipt.get("source_corrections", [])) != 2:
        raise RuntimeError("B016 main-candidate correction set changed")

    translation_coverage = translation.get("coverage", {})
    if translation_coverage.get("main") != {
        "sections": 1,
        "subsections": 3,
        "worked_examples": 4,
        "guided_exercises": 10,
        "guided_inline_answers": 10,
    }:
        raise RuntimeError("B016 terminal translation main coverage changed")
    if translation_coverage.get("eoce") != {
        "exercise_ids": sorted(EOCE), "parts": 40
    }:
        raise RuntimeError("B016 terminal translation EoCE coverage changed")
    if translation_coverage.get("public_answers") != list(PUBLIC_ANSWERS):
        raise RuntimeError("B016 terminal translation public-answer coverage changed")
    if translation_coverage.get("o001_gaps") != list(O001_GAPS):
        raise RuntimeError("B016 terminal translation O001 coverage changed")
    if translation_coverage.get("data_appendix_entries") != 3:
        raise RuntimeError("B016 terminal translation data coverage changed")
    if translation.get("source_corrections", {}).get("count") != len(CORRECTION_CODES):
        raise RuntimeError("B016 translation correction closure changed")
    checks = translation.get("checks", [])
    if not checks or any(item.get("status") != "PASS" for item in checks):
        raise RuntimeError("B016 terminal translation QA is not all-pass")
    if translation.get("check_summary", {}).get("failed") not in (0, None):
        raise RuntimeError("B016 terminal translation QA records failures")

    companion_coverage = companion.get("coverage", {})
    expected_companion = {
        "end_of_chapter_exercises": 10,
        "exercise_parts": 40,
        "public_odd_answers": 5,
        "o001_missing_public_answer_gaps": list(O001_GAPS),
        "data_appendix_entries": 3,
        "restricted_instructor_solutions_accessed": False,
        "restricted_instructor_solutions_invented": False,
    }
    for key, expected in expected_companion.items():
        if companion_coverage.get(key) != expected:
            raise RuntimeError(f"B016 companion coverage changed for {key}")
    missing = o001.get("missing_public_answer_gaps", [])
    if [item.get("exercise_number") for item in missing] != list(O001_GAPS):
        raise RuntimeError("B016 candidate O001 register changed")
    if any(item.get("status") != "O001_MASTERY_COMPANION_GAP" for item in missing):
        raise RuntimeError("B016 O001 gap status changed")

    main_text = raw_inputs["main_fragment"].decode("utf-8")
    if not main_text.startswith("\\section{Distribusi binomial}\n\\label{binomialModel}"):
        raise RuntimeError("B016 main fragment start changed")
    if "\\section{Negative binomial distribution}" in main_text or "\\label{negativeBinomial}" in main_text:
        raise RuntimeError("B016 main fragment crosses the next source boundary")
    if main_text.count("\\begin{examplewrap}") != 4:
        raise RuntimeError("B016 worked-example wrapper count changed")
    if main_text.count("\\begin{exercisewrap}") != 10:
        raise RuntimeError("B016 guided-exercise wrapper count changed")
    for label in (
        "binomialModel", "insureOneOfFourExceedsDeductible",
        "noMoreThanOneFriendWSevereLungCondition", "exactBinomSmokerExSetup",
        "fourBinomialModelsShowingApproxToNormal", "approxNormalForSmokerBinomEx",
        "normApproxToBinomFail",
    ):
        if main_text.count(f"\\label{{{label}}}") != 1:
            raise RuntimeError(f"B016 main label topology changed: {label}")

    eoce_text = raw_inputs["eoce_fragment"].decode("utf-8")
    markers = [int(value) for value in re.findall(r"(?m)^%\s*(\d+)\s*$", eoce_text)]
    if markers != sorted(EOCE):
        raise RuntimeError(f"B016 EoCE marker order changed: {markers}")
    for label in EOCE.values():
        if eoce_text.count(f"\\label{{{label}}}") != 1:
            raise RuntimeError(f"B016 EoCE source label changed: {label}")

    answer_text = raw_inputs["public_answers_fragment"].decode("utf-8")
    answer_markers = [
        int(value) for value in re.findall(r"(?m)^%\s*(\d+)\s*$", answer_text)
    ]
    if answer_markers != list(PUBLIC_ANSWERS):
        raise RuntimeError("B016 localized public-answer marker order changed")
    data_text = raw_inputs["data_appendix_fragment"].decode("utf-8")
    if data_text.count("\\item[\\ref{binomialModel}]") != 3:
        raise RuntimeError("B016 localized data-entry topology changed")

    return bound


def load_terminal_contract() -> dict[str, Any]:
    if TERMINAL_CONTRACT_IDENTITY is None:
        raise TerminalInputsUnresolved(
            "R011-B016 terminal contract identity is deliberately unresolved; pending roles: "
            + ", ".join(sorted(PENDING_TERMINAL_ROLES))
        )
    raw = require(TERMINAL_CONTRACT, TERMINAL_CONTRACT_IDENTITY)
    contract = parse_json(raw, "terminal contract")
    if contract.get("$schema") != "interlanguage.r011-b016-terminal-inputs/v1":
        raise TerminalInputsUnresolved("unexpected B016 terminal-contract schema")
    if contract.get("boundary_id") != BOUNDARY_ID or contract.get("status") != "READY_TERMINAL_INPUTS":
        raise TerminalInputsUnresolved("B016 terminal contract is not READY_TERMINAL_INPUTS")
    if contract.get("closure") != EXPECTED_TERMINAL_CLOSURE:
        raise TerminalInputsUnresolved("B016 terminal closure is incomplete or changed")
    inputs = contract.get("inputs", {})
    if set(inputs) != set(PENDING_TERMINAL_ROLES):
        raise TerminalInputsUnresolved("B016 terminal role set is incomplete or expanded")
    for role, item in sorted(inputs.items()):
        if set(item) != {"path", "bytes", "sha256"}:
            raise TerminalInputsUnresolved(f"terminal role {role} lacks exact identity fields")
        relative = Path(item["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise TerminalInputsUnresolved(f"terminal role {role} has an unsafe path")
        require(LANE / relative, item)
    gates = contract.get("gates", {})
    if set(gates) != REQUIRED_TERMINAL_GATES:
        raise TerminalInputsUnresolved("B016 terminal gate set is incomplete or expanded")
    if any(value != "passed" for value in gates.values()):
        raise TerminalInputsUnresolved("one or more deterministic B016 terminal gates are not passed")
    return contract


def load_base_records(
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    """Load only the exact manifest-bound admitted B015 export inventory."""
    bind_base()
    manifest = parse_json(require(BASE_MANIFEST, BASE_MANIFEST_IDENTITY), "base manifest")
    entries = {entry["path"]: entry for entry in manifest["files"]}
    records: dict[str, list[dict[str, Any]]] = {}
    for name, relative in RECORD_PATHS.items():
        entry = entries.get(relative)
        if entry is None:
            raise RuntimeError(f"B015 base manifest lacks {relative}")
        raw = require(BASE_EXPORTS / relative, entry)
        rows = load_jsonl(raw)
        if len(rows) != int(entry["records"]) or jsonl_bytes(rows) != raw:
            raise RuntimeError(f"noncanonical B015 base payload: {relative}")
        records[name] = rows
    if len(manifest.get("files", [])) + 1 != BASE_INVENTORY_IDENTITY["files"]:
        raise RuntimeError("bounded B015 manifest inventory count changed")
    return records, manifest


def load_context() -> dict[str, Any]:
    ready = bind_ready_inputs()
    contract = load_terminal_contract()
    raw = {
        role: require(LANE / item["path"], item)
        for role, item in contract["inputs"].items()
    }
    raw.update(
        {role: require(LANE / item["path"], item) for role, item in ready.items()}
    )

    source_closure = parse_json(raw["source_closure"], "source_closure")
    translation_qa = parse_json(raw["translation_qa"], "translation_qa")
    main_source = raw["main_authority_witness"]
    eoce_source = raw["eoce_authority_witness"]
    answer_source = raw["public_answers_authority_witness"]
    data_source = raw["data_authority_witness"]
    authority_offsets = {
        "main": unique_offset(raw["main_authority"], main_source, "B016 main authority witness"),
        "eoce": unique_offset(raw["eoce_authority"], eoce_source, "B016 EoCE authority witness"),
        "answers": unique_offset(
            raw["public_answers_authority"], answer_source,
            "B016 public-answer authority witness",
        ),
        "data": unique_offset(raw["data_authority"], data_source, "B016 data authority witness"),
    }

    target_fragments = {
        "main": raw["main_fragment"],
        "eoce": raw["eoce_fragment"],
        "answers": raw["public_answers_fragment"],
        "data": raw["data_appendix_fragment"],
    }
    terminal_roles = {
        "main": "assembled_main",
        "eoce": "assembled_eoce",
        "answers": "assembled_public_answers",
        "data": "assembled_data_appendix",
    }
    assembled_offsets = {
        name: unique_offset(
            raw[terminal_roles[name]], fragment, f"assembled B016 {name} fragment"
        )
        for name, fragment in target_fragments.items()
    }

    source_struct = structural_spans(main_source)
    target_struct = structural_spans(target_fragments["main"])
    if [(row["kind"], row["number"]) for row in source_struct] != [
        (row["kind"], row["number"]) for row in target_struct
    ]:
        raise RuntimeError("B016 source/target structural segmentation differs")
    source_subsections = subsection_spans(main_source)
    target_subsections = subsection_spans(target_fragments["main"])
    source_eoce = marker_spans(eoce_source, sorted(EOCE))
    target_eoce = marker_spans(target_fragments["eoce"], sorted(EOCE))
    source_answers = marker_spans(answer_source, list(PUBLIC_ANSWERS))
    target_answers = marker_spans(target_fragments["answers"], list(PUBLIC_ANSWERS))
    data_command = b"\\item[\\ref{binomialModel}]"
    source_data = repeated_command_spans(data_source, data_command, 3)
    target_data = repeated_command_spans(target_fragments["data"], data_command, 3)

    return {
        "contract": contract,
        "ready": ready,
        "raw": raw,
        "source_closure": source_closure,
        "translation_qa": translation_qa,
        "authority_offsets": authority_offsets,
        "assembled_offsets": assembled_offsets,
        "main_source": main_source,
        "eoce_source": eoce_source,
        "answer_source": answer_source,
        "data_source": data_source,
        "target_fragments": target_fragments,
        "source_struct": source_struct,
        "target_struct": target_struct,
        "source_subsections": source_subsections,
        "target_subsections": target_subsections,
        "source_eoce": source_eoce,
        "target_eoce": target_eoce,
        "source_answers": source_answers,
        "target_answers": target_answers,
        "source_data": source_data,
        "target_data": target_data,
    }


def common_fields(
    resource_id: str, edition_id: str, rights_ids: list[str], **overrides: Any
) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "boundary_id": BOUNDARY_ID,
        "resource_id": resource_id,
        "edition_id": edition_id,
        "source_local_ids": [BOUNDARY_ID],
        "parent_id": None,
        "order": None,
        "source_path": None,
        "source_span": None,
        "source_sha256": None,
        "locale": "zxx",
        "translation_state": "structurally_verified",
        "rights_component_ids": rights_ids,
    }
    fields.update(overrides)
    return fields


def _span_fields(meta: dict[str, Any]) -> tuple[dict[str, int], str]:
    return schema_span(meta), str(meta["sha256"])


def _decoded_span(raw: bytes, meta: dict[str, Any]) -> str:
    return raw[int(meta["byte_start"]):int(meta["byte_end_exclusive"])].decode("utf-8")


def _split_synonyms(value: str) -> list[str]:
    value = value.strip()
    if not value or value == "-":
        return []
    return [item.strip() for item in value.split(";") if item.strip()]


def _record_index(records: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for rows in records.values():
        for row in rows:
            key = str(row["stable_key"])
            if key in result or str(row["id"]) != stable_id(key):
                raise RuntimeError(f"invalid or duplicate stable identity {key}")
            result[key] = row
    return result


def _add_record(
    records: dict[str, list[dict[str, Any]]],
    indexes: dict[str, dict[str, Any]],
    table: str,
    row: dict[str, Any],
) -> dict[str, Any]:
    key = str(row["stable_key"])
    if key in indexes:
        raise RuntimeError(f"B016 stable key already exists: {key}")
    if any(str(existing["id"]) == str(row["id"]) for existing in indexes.values()):
        raise RuntimeError(f"B016 UUID already exists: {row['id']}")
    records[table].append(row)
    indexes[key] = row
    return row


def _unit_record(
    key: str,
    title: str,
    unit_type: str,
    order: int,
    parent_id: str,
    resource_id: str,
    edition_id: str,
    rights_ids: list[str],
    source_local_ids: list[str],
    source_path: str | None,
    source_meta: dict[str, Any] | None,
    target_path: str | None,
    target_meta: dict[str, Any] | None,
    **extra: Any,
) -> dict[str, Any]:
    source_span, source_sha = (None, None)
    if source_meta is not None:
        source_span, source_sha = _span_fields(source_meta)
    row = backend_record(
        "unit",
        key,
        **common_fields(
            resource_id,
            edition_id,
            rights_ids,
            source_local_ids=source_local_ids,
            parent_id=parent_id,
            order=order,
            source_path=source_path,
            source_span=source_span,
            source_sha256=source_sha,
            locale="en",
            translation_state="visually_checked" if target_meta is not None else "queued",
        ),
        title=title,
        unit_type=unit_type,
        prerequisite_ids=[],
        answer_availability=None,
        authoring_mode=None,
        gap_reason=None,
        source_solution_used=None,
        target_identity_status=("terminal_contract_bound" if target_meta is not None else None),
        target_path=target_path,
        target_span=target_meta,
        target_sha256=(None if target_meta is None else target_meta["sha256"]),
    )
    row.update(extra)
    return normalize(row)


def _segment_and_localization(
    records: dict[str, list[dict[str, Any]]],
    indexes: dict[str, dict[str, Any]],
    segment_key: str,
    localization_key: str,
    unit_id: str,
    order: int,
    segment_kind: str,
    resource_id: str,
    edition_id: str,
    source_rights: list[str],
    target_rights: list[str],
    source_local_ids: list[str],
    source_path: str,
    source_raw: bytes,
    source_meta: dict[str, Any],
    target_path: str,
    target_raw: bytes,
    target_meta: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    source_span, source_sha = _span_fields(source_meta)
    segment = backend_record(
        "segment",
        segment_key,
        **common_fields(
            resource_id,
            edition_id,
            source_rights,
            source_local_ids=source_local_ids,
            parent_id=unit_id,
            order=order,
            source_path=source_path,
            source_span=source_span,
            source_sha256=source_sha,
            locale="en",
            translation_state="source_frozen",
        ),
        unit_id=unit_id,
        segment_kind=segment_kind,
        source_locale="en",
        source_text=_decoded_span(source_raw, source_meta),
        protected_tokens=[],
        target_locales=["id-ID"],
    )
    _add_record(records, indexes, "segments", segment)
    localization = backend_record(
        "localization",
        localization_key,
        **common_fields(
            resource_id,
            edition_id,
            target_rights,
            source_local_ids=source_local_ids,
            parent_id=segment["id"],
            order=order,
            source_path=source_path,
            source_span=source_span,
            source_sha256=source_sha,
            locale="id-ID",
            translation_state="visually_checked",
        ),
        unit_id=unit_id,
        source_segment_id=segment["id"],
        source_locale="en",
        target_locale="id-ID",
        target_path=target_path,
        target_span=target_meta,
        target_sha256=target_meta["sha256"],
        target_text=_decoded_span(target_raw, target_meta),
        target_identity_status="terminal_contract_bound",
        protected_tokens=[],
        source_protected_tokens=[],
        target_protected_tokens=[],
        protected_token_delta={
            "authorized": True,
            "reason": "Exact B016 translation, topology, mathematics, build, and visual receipts.",
        },
        terminology_bindings=[f"B016-TM{number:03d}" for number in range(1, 28)],
        candidate_validation_receipt="qa/b016-build/R011-B016_SOURCE_QA.json",
        translation_provenance=PROVENANCE,
    )
    _add_record(records, indexes, "localizations", localization)
    return segment, localization


def _artifact_evidence(
    context: dict[str, Any],
    resource_id: str,
    edition_id: str,
) -> tuple[list[dict[str, Any]], dict[str, bytes], dict[str, dict[str, Any]]]:
    evidence: dict[str, bytes] = {}
    rows: list[dict[str, Any]] = []
    role_map: dict[str, dict[str, Any]] = {}

    def add(category: str, role: str, source_path: Path, raw: bytes) -> None:
        safe_role = re.sub(r"[^A-Za-z0-9_.-]+", "-", role)
        relative = f"evidence/b016/{category}-{safe_role}-{source_path.name}"
        if relative in evidence:
            raise RuntimeError(f"duplicate B016 evidence path: {relative}")
        evidence[relative] = raw
        artifact = backend_record(
            "artifact",
            f"r011/artifact/b016/{category}-{role}",
            **common_fields(
                resource_id,
                edition_id,
                [],
                parent_id=edition_id,
                order=len(rows) + 1,
                locale="zxx",
                translation_state=("built" if role in {"reader_pdf", "build_receipt"} else "structurally_verified"),
            ),
            artifact_kind=f"{category}-{role}",
            path=relative,
            bytes=len(raw),
            sha256=sha256_bytes(raw),
            result="exact terminal B016 input or isolated backend evidence",
            provenance=PROVENANCE,
            toolchain=("python/jsonschema" if role in {"generator", "validator"} else None),
            build_receipt=(
                context["contract"]["inputs"]["build_receipt"]["sha256"]
                if role == "reader_pdf" else None
            ),
        )
        rows.append(artifact)
        role_map[f"{category}:{role}"] = artifact

    for role, item in sorted(context["ready"].items()):
        add("ready", role, LANE / item["path"], context["raw"][role])
    for role, item in sorted(context["contract"]["inputs"].items()):
        add("terminal", role, LANE / item["path"], context["raw"][role])
    terminal_raw = require(TERMINAL_CONTRACT, TERMINAL_CONTRACT_IDENTITY)
    add("terminal", "contract", TERMINAL_CONTRACT, terminal_raw)
    generator_raw = SCRIPT_PATH.read_bytes()
    add("tool", "generator", SCRIPT_PATH, generator_raw)
    validator_path = SCRIPT_PATH.with_name("validate_backend_b016.py")
    add("tool", "validator", validator_path, validator_path.read_bytes())
    spec_path = INTERLANGUAGE_ROOT / INTEROPERABILITY_SPEC["path"]
    add("spec", "interoperability", spec_path, require(spec_path, INTEROPERABILITY_SPEC))
    return rows, evidence, role_map


def compile_records(
    base_records: dict[str, list[dict[str, Any]]], context: dict[str, Any]
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, bytes], dict[str, int]]:
    records = deepcopy(base_records)
    indexes = _record_index(records)
    resource = indexes["r011/resource/openintro-statistics"]
    edition = indexes["r011/edition/fee25091"]
    chapter = indexes[SEMANTIC_BLUEPRINT["hierarchy_parent"]]
    predecessor = indexes[SEMANTIC_BLUEPRINT["predecessor"]]
    unit_prerequisite = indexes[SEMANTIC_BLUEPRINT["unit_prerequisites"][0][0]]
    resource_id = str(resource["id"])
    edition_id = str(edition["id"])
    upstream_right = str(indexes["r011/rights/upstream-cc-by-sa-3.0"]["id"])
    o001_right = str(indexes["r011/rights/o001-original-companion-planned"]["id"])
    package_right = str(indexes["r011/rights/openintro-r-package-gpl-3"]["id"])

    derivative_right = backend_record(
        "rights",
        "r011/rights/b016-localized-section-text-and-reused-figures",
        **common_fields(
            resource_id,
            edition_id,
            [],
            parent_id=resource_id,
            order=len(records["rights"]) + 1,
            locale="zxx",
            translation_state="visually_checked",
            source_path="qa/b016-assets/R011-B016_ASSET_RIGHTS_CLOSURE.json",
            source_sha256=context["ready"]["asset_rights_closure"]["sha256"],
        ),
        component_scope=(
            "B016 Indonesian Section 4.3, EoCE 17--26, public answers "
            "17/19/21/23/25, three data-appendix entries, translated accessibility "
            "text, and byte-exact locale-neutral generated figures."
        ),
        license_expression="CC-BY-SA-3.0",
        verification_status="verified by exact source, translation, asset-rights, build and visual receipts",
        attribution="OpenIntro Statistics source authors; Indonesian derivative changes identified by R011-B016.",
        change_notice=(
            "Four explicit derivative-scoped source corrections; Indonesian prose, captions and alt text; "
            "two numeric/mathematical figure PDFs reused byte-exact."
        ),
        non_endorsement="No author, institution, publisher, brand owner, or tool-provider endorsement implied.",
        publication_effect="Isolated B016 backend stage only; admission and publication are separate transactions.",
    )
    _add_record(records, indexes, "rights", derivative_right)
    photo_right = backend_record(
        "rights",
        "r011/rights/b016-dreidel-photo-cc-by-2-0",
        **common_fields(
            resource_id,
            edition_id,
            [],
            parent_id=resource_id,
            order=len(records["rights"]) + 1,
            locale="zxx",
            translation_state="visually_checked",
            source_path="qa/b016-assets/R011-B016_ASSET_RIGHTS_CLOSURE.json",
            source_sha256=context["ready"]["asset_rights_closure"]["sha256"],
        ),
        component_scope="Dreidel photograph in EoCE exercise 4.21, preserved unchanged with source crop notice.",
        license_expression="CC-BY-2.0",
        verification_status="verified from source attribution, redirect identity, exact image bytes and visual receipt",
        attribution="Photo by Staccabees; source http://flic.kr/p/7gLZTf; CC BY 2.0.",
        change_notice="Source states that the photograph was cropped; B016 reuses the exact upstream JPEG.",
        non_endorsement="No photographer or source-platform endorsement implied.",
        publication_effect="Retain visible creator, source, crop notice and CC BY 2.0 license link.",
    )
    _add_record(records, indexes, "rights", photo_right)
    text_rights = [upstream_right, str(derivative_right["id"])]

    raw = context["raw"]
    main_source_full = raw["main_authority"]
    eoce_source_full = raw["eoce_authority"]
    answer_source_full = raw["public_answers_authority"]
    data_source_full = raw["data_authority"]
    main_target_full = raw["assembled_main"]
    eoce_target_full = raw["assembled_eoce"]
    answer_target_full = raw["assembled_public_answers"]
    data_target_full = raw["assembled_data_appendix"]
    source_paths = {
        "main": "ch_distributions/TeX/ch_distributions.tex",
        "eoce": "ch_distributions/TeX/binomial_distribution.tex",
        "answers": "extraTeX/eoceSolutions/eoceSolutions.tex",
        "data": "extraTeX/data/data.tex",
    }
    target_paths = {
        "main": context["contract"]["inputs"]["assembled_main"]["path"],
        "eoce": context["contract"]["inputs"]["assembled_eoce"]["path"],
        "answers": context["contract"]["inputs"]["assembled_public_answers"]["path"],
        "data": context["contract"]["inputs"]["assembled_data_appendix"]["path"],
    }

    def source_meta(kind: str, local_meta: dict[str, Any]) -> dict[str, Any]:
        full = {
            "main": main_source_full,
            "eoce": eoce_source_full,
            "answers": answer_source_full,
            "data": data_source_full,
        }[kind]
        return rebase_span(local_meta, full, context["authority_offsets"][kind])

    def target_meta(kind: str, local_meta: dict[str, Any]) -> dict[str, Any]:
        full = {
            "main": main_target_full,
            "eoce": eoce_target_full,
            "answers": answer_target_full,
            "data": data_target_full,
        }[kind]
        return rebase_span(local_meta, full, context["assembled_offsets"][kind])

    whole_main_source = source_meta("main", span_meta(context["main_source"], 0, len(context["main_source"])))
    whole_main_target = target_meta(
        "main", span_meta(context["target_fragments"]["main"], 0, len(context["target_fragments"]["main"]))
    )
    section = _unit_record(
        SEMANTIC_BLUEPRINT["section"],
        "Binomial distribution",
        "section",
        3,
        str(chapter["id"]),
        resource_id,
        edition_id,
        text_rights,
        [BOUNDARY_ID, "binomialModel"],
        source_paths["main"],
        whole_main_source,
        target_paths["main"],
        whole_main_target,
        prerequisite_ids=[str(unit_prerequisite["id"])],
    )
    _add_record(records, indexes, "units", section)

    subsection_units: list[dict[str, Any]] = []
    for number, (source_row, target_row) in enumerate(
        zip(context["source_subsections"], context["target_subsections"]), 1
    ):
        unit = _unit_record(
            SEMANTIC_BLUEPRINT["subsections"][number - 1],
            f"Section 4.3 source-topology subsection {number}",
            "subsection",
            100 + number,
            str(section["id"]),
            resource_id,
            edition_id,
            text_rights,
            [BOUNDARY_ID, f"subsection-{number:02d}"],
            source_paths["main"],
            source_meta("main", source_row["span"]),
            target_paths["main"],
            target_meta("main", target_row["span"]),
        )
        _add_record(records, indexes, "units", unit)
        subsection_units.append(unit)

    main_source_by_kind = {
        kind: [row for row in context["source_struct"] if row["kind"] == kind]
        for kind in ("worked_example", "guided_exercise", "guided_inline_answer")
    }
    main_target_by_kind = {
        kind: [row for row in context["target_struct"] if row["kind"] == kind]
        for kind in ("worked_example", "guided_exercise", "guided_inline_answer")
    }
    worked_units: list[dict[str, Any]] = []
    for number, key in enumerate(SEMANTIC_BLUEPRINT["worked_examples"], 1):
        sm = source_meta("main", main_source_by_kind["worked_example"][number - 1]["span"])
        tm = target_meta("main", main_target_by_kind["worked_example"][number - 1]["span"])
        subsection_number = containing_subsection(
            main_source_by_kind["worked_example"][number - 1]["span"],
            context["source_subsections"],
        )
        unit = _unit_record(
            key,
            f"Worked example 4.3.{number}",
            "worked_example",
            200 + number,
            str(section["id"] if subsection_number is None else subsection_units[subsection_number - 1]["id"]),
            resource_id,
            edition_id,
            text_rights,
            [BOUNDARY_ID, key.rsplit("/", 1)[-1]],
            source_paths["main"], sm, target_paths["main"], tm,
        )
        _add_record(records, indexes, "units", unit)
        worked_units.append(unit)

    guided_units: list[dict[str, Any]] = []
    guided_answer_units: list[dict[str, Any]] = []
    for number, (exercise_key, answer_key) in enumerate(
        zip(SEMANTIC_BLUEPRINT["guided_exercises"], SEMANTIC_BLUEPRINT["guided_inline_answers"]), 1
    ):
        ex_sm = source_meta("main", main_source_by_kind["guided_exercise"][number - 1]["span"])
        ex_tm = target_meta("main", main_target_by_kind["guided_exercise"][number - 1]["span"])
        subsection_number = containing_subsection(
            main_source_by_kind["guided_exercise"][number - 1]["span"],
            context["source_subsections"],
        )
        exercise = _unit_record(
            exercise_key, f"Guided exercise 4.3.{number}", "guided_exercise", 300 + number,
            str(section["id"] if subsection_number is None else subsection_units[subsection_number - 1]["id"]),
            resource_id, edition_id, text_rights,
            [BOUNDARY_ID, f"guided-exercise-{number:02d}"], source_paths["main"], ex_sm,
            target_paths["main"], ex_tm, answer_availability="inline_public",
        )
        _add_record(records, indexes, "units", exercise)
        guided_units.append(exercise)
        ans_sm = source_meta("main", main_source_by_kind["guided_inline_answer"][number - 1]["span"])
        ans_tm = target_meta("main", main_target_by_kind["guided_inline_answer"][number - 1]["span"])
        answer = _unit_record(
            answer_key, f"Inline answer to guided exercise 4.3.{number}", "guided_solution", 1,
            str(exercise["id"]), resource_id, edition_id, text_rights,
            [BOUNDARY_ID, f"guided-answer-{number:02d}"], source_paths["main"], ans_sm,
            target_paths["main"], ans_tm, answer_availability="public_inline",
        )
        _add_record(records, indexes, "units", answer)
        guided_answer_units.append(answer)

    eoce_units: dict[int, dict[str, Any]] = {}
    answer_units: dict[int, dict[str, Any]] = {}
    gap_units: dict[int, dict[str, Any]] = {}
    for number in sorted(EOCE):
        sm = source_meta("eoce", context["source_eoce"][number])
        tm = target_meta("eoce", context["target_eoce"][number])
        exercise = _unit_record(
            f"r011/unit/exercise/4.{number}/{EOCE[number]}", f"Exercise 4.{number}", "exercise",
            3000 + number, str(section["id"]), resource_id, edition_id, text_rights,
            [BOUNDARY_ID, f"4.{number}", EOCE[number]], source_paths["eoce"], sm,
            target_paths["eoce"], tm,
            answer_availability=("public_appendix" if number in PUBLIC_ANSWERS else "restricted_not_accessed"),
        )
        _add_record(records, indexes, "units", exercise)
        eoce_units[number] = exercise
        if number in PUBLIC_ANSWERS:
            asm = source_meta("answers", context["source_answers"][number])
            atm = target_meta("answers", context["target_answers"][number])
            answer = _unit_record(
                f"r011/unit/solution/4.{number}", f"Public solution to exercise 4.{number}", "solution", 1,
                str(exercise["id"]), resource_id, edition_id, text_rights,
                [BOUNDARY_ID, f"4.{number}"], source_paths["answers"], asm,
                target_paths["answers"], atm, answer_availability="public_upstream",
            )
            _add_record(records, indexes, "units", answer)
            answer_units[number] = answer
        else:
            gap = _unit_record(
                f"r011/unit/o001-gap/4.{number}",
                f"O001 mastery-companion answer gap for exercise 4.{number}",
                "companion_gap", 1, str(exercise["id"]), resource_id, edition_id,
                [o001_right], [BOUNDARY_ID, f"4.{number}"], None, None, None, None,
                answer_availability="restricted_not_accessed",
                authoring_mode="independent_original_required",
                gap_reason="no_public_answer_upstream",
                source_solution_used=False,
                target_identity_status="explicit_o001_gap",
            )
            _add_record(records, indexes, "units", gap)
            gap_units[number] = gap

    data_units: list[dict[str, Any]] = []
    for number in range(1, 4):
        sm = source_meta("data", context["source_data"][number - 1]["span"])
        tm = target_meta("data", context["target_data"][number - 1]["span"])
        unit = _unit_record(
            SEMANTIC_BLUEPRINT["data_appendix"][number - 1],
            f"Data appendix entry for binomialModel {number}", "data_appendix_entry",
            7000 + number, str(section["id"]), resource_id, edition_id, text_rights,
            [BOUNDARY_ID, f"binomialModel-data-{number:02d}"], source_paths["data"], sm,
            target_paths["data"], tm,
        )
        _add_record(records, indexes, "units", unit)
        data_units.append(unit)

    term_rows = parse_tsv(raw["controlled_terms"], "controlled_terms")
    term_codes = [f"B016-TM{number:03d}" for number in range(1, 28)]
    for code, term_row in zip(term_codes, term_rows):
        concept_key = TERM_CONCEPT_KEYS[code]
        if concept_key not in indexes:
            concept = backend_record(
                "concept", concept_key,
                **common_fields(
                    resource_id, edition_id, [upstream_right],
                    source_local_ids=[BOUNDARY_ID, code],
                    source_path=source_paths["main"],
                    source_span=schema_span(whole_main_source),
                    source_sha256=whole_main_source["sha256"],
                    locale="zxx", translation_state="source_frozen",
                    order=int(code[-3:]),
                ),
                semantic_code=code,
                preferred_source_term=term_row["source_term"],
                definition=f"Locale-neutral B016 semantic concept {code}.",
            )
            _add_record(records, indexes, "concepts", concept)
        concept_id = str(indexes[concept_key]["id"])
        term = backend_record(
            "term", f"r011/term/id-ID/b016/TM{int(code[-3:]):03d}",
            **common_fields(
                resource_id, edition_id, text_rights,
                source_local_ids=[BOUNDARY_ID, code], parent_id=concept_id,
                order=int(code[-3:]),
                source_path=context["ready"]["controlled_terms"]["path"],
                source_sha256=context["ready"]["controlled_terms"]["sha256"],
                locale="id-ID", translation_state="language_reviewed",
            ),
            concept_id=concept_id,
            source_term=term_row["source_term"],
            target_term=term_row["preferred_id-ID"],
            variants=_split_synonyms(term_row["accepted_synonyms"]),
            rejected_forms=[],
            scope="statistics / Chapter 4 Section 4.3",
            register="academic",
            evidence=term_row["evidence"],
            decision=term_row["use_in_B016"],
            decision_reason=term_row["evidence"],
            glossary_lock_status="bound_to_terminal_b016_candidate",
            internal_witness_bytes_excluded=True,
            field_source_metadata={
                "internal_witness_bytes_bundled": False,
                "witness_sha256": context["ready"]["indonesian_probability_field_witness"]["sha256"],
                "model": PROVENANCE,
            },
        )
        _add_record(records, indexes, "terms", term)

    asset_defs = [
        (SEMANTIC_BLUEPRINT["assets"][0], "four_models_source_r", "source_r_producer", "text/x-r-source", [upstream_right, package_right], ["R package openintro: COL palette and myPDF helper"], None, None),
        (SEMANTIC_BLUEPRINT["assets"][1], "four_models_source_pdf", "source_pdf_figure", "application/pdf", [upstream_right], ["generated by adjacent B016 source R producer"], True, False),
        (SEMANTIC_BLUEPRINT["assets"][2], "normal_failure_source_r", "source_r_producer", "text/x-r-source", [upstream_right, package_right], ["R package openintro: COL palette and myPDF helper"], None, None),
        (SEMANTIC_BLUEPRINT["assets"][3], "normal_failure_source_pdf", "source_pdf_figure", "application/pdf", [upstream_right], ["generated by adjacent B016 source R producer"], True, False),
        (SEMANTIC_BLUEPRINT["assets"][4], "dreidel_source_photo", "source_photo", "image/jpeg", [str(photo_right["id"])], ["visible CC BY 2.0 attribution retained in EoCE source"], None, False),
    ]
    asset_rows: list[dict[str, Any]] = []
    for order, (key, role, kind, media, rights_ids, dependencies, numeric, strings_localized) in enumerate(asset_defs, 1):
        item = context["ready"][role]
        asset = backend_record(
            "asset", key,
            **common_fields(
                resource_id, edition_id, rights_ids,
                source_local_ids=[BOUNDARY_ID, key.rsplit("/", 1)[-1]],
                parent_id=str(section["id"]), order=order,
                source_path=item["path"], source_sha256=item["sha256"],
                locale="zxx", translation_state="source_frozen",
            ),
            asset_kind=kind,
            path=item["path"], bytes=item["bytes"], sha256=item["sha256"],
            media_type=media, dependencies=dependencies,
            numeric_geometry_preserved=numeric,
            reader_visible_strings_localized=strings_localized,
        )
        _add_record(records, indexes, "assets", asset)
        asset_rows.append(asset)

    correction_rows: list[dict[str, Any]] = []
    correction_items = {
        str(item["source"]): item
        for item in context["source_closure"]["high_confidence_source_corrections_for_translation"]
    }
    for order, source_claim in enumerate(CORRECTION_CODE_BY_SOURCE, 1):
        code = CORRECTION_CODE_BY_SOURCE[source_claim]
        item = correction_items[source_claim]
        affected = section
        if code == "B016-SC004":
            affected = eoce_units[17]
        elif code == "B016-SC005":
            affected = eoce_units[26]
        correction = backend_record(
            "correction", f"r011/correction/b016/{code}",
            **common_fields(
                resource_id, edition_id, text_rights,
                source_local_ids=[BOUNDARY_ID, code], parent_id=str(affected["id"]),
                order=order, locale="id-ID", translation_state="language_reviewed",
            ),
            affected_id=str(affected["id"]), category="source_correction",
            summary=f"{code}: explicit derivative-scoped source correction",
            disposition="applied_in_terminal_b016_candidate", confidence="high",
            correction_type="localized_source_correction",
            source_claim=source_claim, proposed_correction=item["correction"],
            rationale=item["reason"],
            evidence=f"{item['path']} authority line {item['line']}",
            upstream_report_disposition="eligible_for_single_deduplicated_post-corpus_report",
        )
        _add_record(records, indexes, "corrections", correction)
        correction_rows.append(correction)

    segment_pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    main_kind_units = {
        "worked_example": worked_units,
        "guided_exercise": guided_units,
        "guided_inline_answer": guided_answer_units,
    }
    kind_cursors = {kind: 0 for kind in main_kind_units}
    for order, (source_row, target_row) in enumerate(zip(context["source_struct"], context["target_struct"]), 1):
        kind = source_row["kind"]
        if kind == "section_prose":
            subsection_number = containing_subsection(
                source_row["span"], context["source_subsections"]
            )
            unit = section if subsection_number is None else subsection_units[subsection_number - 1]
        else:
            unit = main_kind_units[kind][kind_cursors[kind]]
            kind_cursors[kind] += 1
        segment_pairs.append(_segment_and_localization(
            records, indexes,
            f"r011/segment/b016/main-{order:03d}",
            f"r011/localization/id-ID/b016/main-{order:03d}",
            str(unit["id"]), order, kind, resource_id, edition_id,
            [upstream_right], text_rights, [BOUNDARY_ID],
            source_paths["main"], main_source_full, source_meta("main", source_row["span"]),
            target_paths["main"], main_target_full, target_meta("main", target_row["span"]),
        ))
    for number in sorted(EOCE):
        segment_pairs.append(_segment_and_localization(
            records, indexes,
            f"r011/segment/b016/eoce-4-{number}",
            f"r011/localization/id-ID/b016/eoce-4-{number}",
            str(eoce_units[number]["id"]), 100 + number, "exercise", resource_id, edition_id,
            [upstream_right], text_rights, [BOUNDARY_ID, f"4.{number}"],
            source_paths["eoce"], eoce_source_full, source_meta("eoce", context["source_eoce"][number]),
            target_paths["eoce"], eoce_target_full, target_meta("eoce", context["target_eoce"][number]),
        ))
    for number in PUBLIC_ANSWERS:
        segment_pairs.append(_segment_and_localization(
            records, indexes,
            f"r011/segment/b016/answer-4-{number}",
            f"r011/localization/id-ID/b016/answer-4-{number}",
            str(answer_units[number]["id"]), 200 + number, "public_answer", resource_id, edition_id,
            [upstream_right], text_rights, [BOUNDARY_ID, f"4.{number}"],
            source_paths["answers"], answer_source_full, source_meta("answers", context["source_answers"][number]),
            target_paths["answers"], answer_target_full, target_meta("answers", context["target_answers"][number]),
        ))
    for number in range(1, 4):
        segment_pairs.append(_segment_and_localization(
            records, indexes,
            f"r011/segment/b016/data-binomial-{number:02d}",
            f"r011/localization/id-ID/b016/data-binomial-{number:02d}",
            str(data_units[number - 1]["id"]), 300 + number, "data_appendix", resource_id, edition_id,
            [upstream_right], text_rights, [BOUNDARY_ID, f"data-{number:02d}"],
            source_paths["data"], data_source_full, source_meta("data", context["source_data"][number - 1]["span"]),
            target_paths["data"], data_target_full, target_meta("data", context["target_data"][number - 1]["span"]),
        ))

    artifact_rows, evidence_payloads, artifact_roles = _artifact_evidence(
        context, resource_id, edition_id
    )
    for artifact in artifact_rows:
        _add_record(records, indexes, "artifacts", artifact)

    qa_witnesses = {
        "base_preservation": "terminal:source_manifest",
        "source": "terminal:source_qa",
        "translation": "ready:translation_qa",
        "terminology": "ready:terminology_qa",
        "asset_identity": "ready:asset_rights_closure",
        "rights": "ready:asset_rights_closure",
        "mathematics": "ready:translation_qa",
        "topology": "terminal:source_qa",
        "build": "terminal:build_receipt",
        "visual": "terminal:visual_qa",
        "corrections": "ready:source_closure",
        "interoperability": "spec:interoperability",
        "isolation": "tool:generator",
    }
    qa_rows: list[dict[str, Any]] = []
    for order, qa_type in enumerate(SEMANTIC_BLUEPRINT["qa_event_types"], 1):
        witness = artifact_roles[qa_witnesses[qa_type]]
        qa = backend_record(
            "qa_event", f"r011/qa/b016/{qa_type.replace('_', '-')}",
            **common_fields(
                resource_id, edition_id, [], source_local_ids=[BOUNDARY_ID],
                parent_id=edition_id, order=order, locale="zxx",
                translation_state="visually_checked",
            ),
            qa_type=qa_type, result="passed", subject_id=str(section["id"]),
            witness_artifact_id=str(witness["id"]), witness_path=witness["path"],
            detail=f"Exact deterministic B016 {qa_type.replace('_', ' ')} gate passed.",
            provenance=PROVENANCE,
        )
        _add_record(records, indexes, "qa_events", qa)
        qa_rows.append(qa)

    relation_counters: dict[str, int] = {}
    def relation(relation_type: str, from_id: str, to_id: str, qualifier: str) -> None:
        relation_counters[relation_type] = relation_counters.get(relation_type, 0) + 1
        order = relation_counters[relation_type]
        row = backend_record(
            "relation", f"r011/relation/b016/{relation_type}/{order:04d}",
            **common_fields(
                resource_id, edition_id, [], source_local_ids=[BOUNDARY_ID],
                order=order, locale="zxx", translation_state="structurally_verified",
            ),
            relation_type=relation_type, from_id=from_id, to_id=to_id, qualifier=qualifier,
        )
        _add_record(records, indexes, "relations", row)

    child_units = subsection_units + worked_units + guided_units + guided_answer_units
    child_units += list(eoce_units.values()) + list(answer_units.values()) + list(gap_units.values()) + data_units
    relation("contains", str(chapter["id"]), str(section["id"]), "source hierarchy")
    for child in child_units:
        relation("contains", str(child["parent_id"]), str(child["id"]), "B016 semantic hierarchy")
    relation("precedes", str(predecessor["id"]), str(section["id"]), "source order")
    relation("prerequisite", str(unit_prerequisite["id"]), str(section["id"]), "unit prerequisite")
    for prerequisite_key, concept_key in SEMANTIC_BLUEPRINT["concept_prerequisites"]:
        relation("prerequisite", str(indexes[prerequisite_key]["id"]), str(indexes[concept_key]["id"]), "concept prerequisite")
    for concept_key in sorted(set(TERM_CONCEPT_KEYS.values())):
        relation("covers", str(section["id"]), str(indexes[concept_key]["id"]), "Section 4.3 controlled concept")
    for code in term_codes:
        term = indexes[f"r011/term/id-ID/b016/TM{int(code[-3:]):03d}"]
        relation("lexicalizes", str(indexes[TERM_CONCEPT_KEYS[code]]["id"]), str(term["id"]), "id-ID controlled terminology")
    for segment, localization in segment_pairs:
        relation("unit_contains_segment", str(segment["unit_id"]), str(segment["id"]), "semantic segmentation")
        relation("localizes", str(segment["id"]), str(localization["id"]), "id-ID terminal localization")
    for answer, exercise in zip(guided_answer_units, guided_units):
        relation("answers", str(answer["id"]), str(exercise["id"]), "inline public guided answer")
    for number in PUBLIC_ANSWERS:
        relation("answers", str(answer_units[number]["id"]), str(eoce_units[number]["id"]), "public answer appendix")
    for number in O001_GAPS:
        relation("requires_companion_answer", str(eoce_units[number]["id"]), str(gap_units[number]["id"]), "O001 gap; restricted solution not accessed")
    for asset in asset_rows:
        relation("uses_asset", str(section["id"]), str(asset["id"]), "B016 source/reader asset closure")
    relation("produces", str(asset_rows[0]["id"]), str(asset_rows[1]["id"]), "adjacent R producer")
    relation("produces", str(asset_rows[2]["id"]), str(asset_rows[3]["id"]), "adjacent R producer")
    package_artifact = artifact_roles["ready:openintro_package_archive"]
    relation("depends_on", str(asset_rows[0]["id"]), str(package_artifact["id"]), "frozen GPL-3 build dependency")
    relation("depends_on", str(asset_rows[2]["id"]), str(package_artifact["id"]), "frozen GPL-3 build dependency")
    for correction in correction_rows:
        relation("corrects", str(correction["id"]), str(correction["affected_id"]), "localized derivative correction")
    relation("governs", str(derivative_right["id"]), str(section["id"]), "B016 derivative text and generated figures")
    relation("governs", str(photo_right["id"]), str(asset_rows[4]["id"]), "separate CC BY 2.0 photograph")
    for qa in qa_rows:
        relation("validates", str(qa["id"]), str(qa["subject_id"]), "typed deterministic QA event")
    for artifact in artifact_rows:
        relation("documents", str(artifact["id"]), edition_id, str(artifact["artifact_kind"]))

    for table, rows in records.items():
        rows.sort(key=lambda row: str(row["id"]))
        if any(row["record_type"] != table.rstrip("s").replace("localization", "localization") for row in []):
            raise AssertionError("unreachable record-type guard")
    new_counts = {
        name: len(records[name]) - len(base_records[name]) for name in sorted(records)
    }
    return records, evidence_payloads, new_counts


def build_views(
    records: dict[str, list[dict[str, Any]]]
) -> tuple[dict[str, bytes], dict[str, int]]:
    columns_doc = parse_json(
        (BASE_EXPORTS / "schemas/backend-view-columns-v0.1.0.json").read_bytes(),
        "view-column schema",
    )
    columns = columns_doc["views"]
    by_key = _record_index(records)

    resource = by_key["r011/resource/openintro-statistics"]
    edition = by_key["r011/edition/fee25091"]
    upstream_right = by_key["r011/rights/upstream-cc-by-sa-3.0"]
    rows: dict[str, list[dict[str, Any]]] = {}
    rows["views/resource_editions.csv"] = [{
        "resource_id": resource["id"],
        "resource_code": resource["resource_code"],
        "work_title": resource["work_title"],
        "edition_id": edition["id"],
        "repository": edition["repository"],
        "branch_observed": edition["branch_observed"],
        "commit": edition["commit"],
        "tree": edition["tree"],
        "license_expression": upstream_right["license_expression"],
        "source_format": edition["source_format"],
        "build_entrypoint": edition["build_entrypoint"],
    }]
    rows["views/unit_hierarchy.csv"] = [
        {
            "id": row["id"], "parent_id": row.get("parent_id"), "order": row.get("order"),
            "unit_type": row.get("unit_type"), "source_local_ids": row.get("source_local_ids", []),
            "source_path": row.get("source_path"),
            "line_start": (row.get("source_span") or {}).get("line_start"),
            "line_end": (row.get("source_span") or {}).get("line_end"),
            "source_sha256": row.get("source_sha256"),
            "translation_state": row.get("translation_state"),
            "rights_component_ids": row.get("rights_component_ids", []),
        }
        for row in records["units"]
    ]
    rows["views/relations.csv"] = [
        {key: row.get(key) for key in columns["views/relations.csv"]}
        for row in records["relations"]
    ]
    localizations: dict[str, dict[str, Any]] = {}
    for row in records["localizations"]:
        source_segment_id = str(row["source_segment_id"])
        if source_segment_id in localizations:
            raise RuntimeError(f"multiple localizations for segment {source_segment_id}")
        localizations[source_segment_id] = row
    segment_rows: list[dict[str, Any]] = []
    for segment in records["segments"]:
        localization = localizations.get(str(segment["id"]))
        target_span = {} if localization is None else (localization.get("target_span") or {})
        segment_rows.append({
            "segment_id": segment["id"], "unit_id": segment["unit_id"],
            "order": segment.get("order"), "segment_kind": segment.get("segment_kind"),
            "source_locale": segment.get("source_locale"), "source_path": segment.get("source_path"),
            "line_start": (segment.get("source_span") or {}).get("line_start"),
            "line_end": (segment.get("source_span") or {}).get("line_end"),
            "source_sha256": segment.get("source_sha256"),
            "target_locale": None if localization is None else localization.get("target_locale"),
            "target_path": None if localization is None else localization.get("target_path"),
            "target_line_start": target_span.get("line_start"),
            "target_line_end": target_span.get("line_end"),
            "target_sha256": None if localization is None else localization.get("target_sha256"),
            "translation_state": segment.get("translation_state") if localization is None else localization.get("translation_state"),
            "target_text": None if localization is None else localization.get("target_text"),
            "rights_component_ids": segment.get("rights_component_ids", []) if localization is None else localization.get("rights_component_ids", []),
        })
    rows["views/segments_locale.csv"] = segment_rows
    rows["views/terminology.csv"] = [
        {
            "id": row["id"], "concept_id": row["concept_id"],
            "source_term": row["source_term"], "target_term": row["target_term"],
            "locale": row["locale"], "variants": row.get("variants", []),
            "rejected_forms": row.get("rejected_forms", []), "scope": row.get("scope"),
            "register": row.get("register"), "translation_state": row.get("translation_state"),
        }
        for row in records["terms"]
    ]
    solutions = {
        str(row["parent_id"]): row for row in records["units"]
        if row.get("unit_type") in {"solution", "guided_solution"} and row.get("parent_id")
    }
    gaps = {
        str(row["parent_id"]): row for row in records["units"]
        if row.get("unit_type") == "companion_gap" and row.get("parent_id")
    }
    exercise_rows: list[dict[str, Any]] = []
    for exercise in records["units"]:
        if exercise.get("unit_type") not in {"exercise", "guided_exercise"}:
            continue
        solution = solutions.get(str(exercise["id"]))
        gap = gaps.get(str(exercise["id"]))
        exercise_rows.append({
            "exercise_id": exercise["id"],
            "source_local_ids": exercise.get("source_local_ids", []),
            "answer_availability": exercise.get("answer_availability"),
            "answer_id": None if solution is None else solution["id"],
            "o001_gap_id": None if gap is None else gap["id"],
            "source_path": exercise.get("source_path"),
            "translation_state": exercise.get("translation_state"),
            "rights_component_ids": exercise.get("rights_component_ids", []),
        })
    rows["views/exercises_answers.csv"] = exercise_rows
    rows["views/rights_components.csv"] = [
        {key: row.get(key) for key in columns["views/rights_components.csv"]}
        for row in records["rights"]
    ]
    rows["views/corrections.csv"] = [
        {key: row.get(key) for key in columns["views/corrections.csv"]}
        for row in records["corrections"]
    ]
    rows["views/qa_build_events.csv"] = [
        {key: row.get(key) for key in columns["views/qa_build_events.csv"]}
        for row in records["qa_events"]
    ]
    rows["views/artifacts.csv"] = [
        {key: row.get(key) for key in columns["views/artifacts.csv"]}
        for row in records["artifacts"]
    ]
    payloads: dict[str, bytes] = {}
    counts: dict[str, int] = {}
    for path in SEMANTIC_BLUEPRINT["required_views"]:
        if path not in rows or path not in columns:
            raise RuntimeError(f"required view lacks deterministic definition: {path}")
        ordered = sorted(rows[path], key=lambda row: tuple(str(row.get(key) or "") for key in columns[path]))
        payloads[path] = csv_bytes(columns[path], ordered)
        counts[path] = len(ordered)
    return payloads, counts


def build_identity_map(records: dict[str, list[dict[str, Any]]]) -> bytes:
    rows = [
        {
            "id": row["id"], "record_type": row["record_type"],
            "source_local_ids": row.get("source_local_ids", []),
            "stable_key": row["stable_key"],
        }
        for table_rows in records.values() for row in table_rows
    ]
    return "".join(
        canonical_json_text(row) + "\n" for row in sorted(rows, key=lambda row: str(row["id"]))
    ).encode("utf-8")


def compile_stage() -> dict[str, Any]:
    context = load_context()
    base_records, base_manifest = load_base_records()
    records, evidence_payloads, new_counts = compile_records(base_records, context)
    record_payloads = {
        RECORD_PATHS[name]: jsonl_bytes(records[name]) for name in sorted(RECORD_PATHS)
    }
    view_payloads, view_counts = build_views(records)
    generated_payloads: dict[str, bytes] = {
        **record_payloads,
        **view_payloads,
        "identity_map.jsonl": build_identity_map(records),
        **evidence_payloads,
    }
    generated_counts: dict[str, int | None] = {
        RECORD_PATHS[name]: len(records[name]) for name in RECORD_PATHS
    }
    generated_counts.update(view_counts)
    generated_counts["identity_map.jsonl"] = sum(len(rows) for rows in records.values())
    generated_counts.update({path: None for path in evidence_payloads})

    generated_paths = set(generated_payloads)
    base_copy_entries = [
        deepcopy(entry) for entry in base_manifest["files"]
        if entry["path"] not in generated_paths
    ]
    for entry in base_copy_entries:
        require(BASE_EXPORTS / entry["path"], entry)
    file_entries = base_copy_entries + [
        {
            "path": path,
            "bytes": len(raw),
            "sha256": sha256_bytes(raw),
            "records": generated_counts[path],
        }
        for path, raw in generated_payloads.items()
    ]
    file_entries.sort(key=lambda entry: str(entry["path"]))
    record_counts = {name: len(records[name]) for name in sorted(records)}
    record_count = sum(record_counts.values())
    terminal_inputs = deepcopy(context["contract"]["inputs"])
    ready_inputs = deepcopy(context["ready"])
    source_closure = context["source_closure"]
    manifest = normalize({
        "$schema": "schemas/backend-manifest-v0.1.0.schema.json",
        "schema_version": SCHEMA_VERSION,
        "backend_id": stable_id("r011/backend/b016/final-isolated"),
        "backend_name": "r011-openintro-statistics-id-b016-final-isolated",
        "namespace_uuid": str(NAMESPACE),
        "boundary_id": BOUNDARY_ID,
        "workflow_id": WORKFLOW_ID,
        "recorded_at": RECORDED_AT,
        "authority": {
            "repository": source_closure["authority"]["repository"],
            "branch_observed": source_closure["authority"]["branch_observed"],
            "commit": source_closure["authority"]["commit"],
            "tree": source_closure["authority"]["tree"],
            "authority_path": source_closure["authority"]["authority_metadata"]["path"],
            "authority_sha256": source_closure["authority"]["authority_metadata"]["sha256"],
        },
        "canonicalization": {
            "encoding": "UTF-8 without BOM", "normalization": "Unicode NFC",
            "line_endings": "LF",
            "json": "RFC-8785-compatible integer/string subset; keys sorted; compact separators",
            "record_order": "ascending UUID string",
        },
        "scope": (
            "Complete Chapter 4 Section 4.3 Binomial distribution / Distribusi binomial "
            "through EoCE 17--26, public answers 17/19/21/23/25, three data-appendix "
            "entries, two locale-neutral generated figures and the separately licensed "
            "dreidel photograph, ending immediately before negativeBinomial."
        ),
        "stage_state": "isolated_terminal_backend_candidate",
        "admission_eligibility": "ready_for_separate_guarded_admission",
        "provenance": PROVENANCE,
        "base_preservation": {
            "boundary_id": BASE_BOUNDARY_ID,
            "manifest": deepcopy(BASE_MANIFEST_IDENTITY),
            "inventory": deepcopy(BASE_INVENTORY_IDENTITY),
            "record_count": BASE_RECORD_COUNT,
            "all_base_records_preserved_canonical_bytes": True,
        },
        "base_record_counts": deepcopy(BASE_RECORD_COUNTS),
        "new_b016_record_count": sum(new_counts.values()),
        "new_b016_record_counts": new_counts,
        "record_count": record_count,
        "record_counts": record_counts,
        "source_application": {
            "canonical_source_mutated": False,
            "terminal_identity_fail_closed": True,
            "terminal_contract": {
                "path": TERMINAL_CONTRACT.relative_to(LANE).as_posix(),
                **deepcopy(TERMINAL_CONTRACT_IDENTITY),
            },
            "terminal_inputs": terminal_inputs,
            "ready_inputs": ready_inputs,
        },
        "topology": {
            "section": "binomialModel", "subsections": 3, "worked_examples": 4,
            "guided_exercises": 10, "guided_inline_answers": 10,
            "eoce_exercises": sorted(EOCE), "public_answers": list(PUBLIC_ANSWERS),
            "o001_companion_gaps": list(O001_GAPS), "data_appendix_entries": 3,
            "assets": 5, "next_source_anchor": "negativeBinomial", "next_source_line": 1927,
        },
        "correction_closure": {"source_corrections": list(CORRECTION_CODES)},
        "terminology": {"locale": "id-ID", "decision_count": len(TERM_CONCEPT_KEYS)},
        "asset_closure": {
            "asset_rights_closure": deepcopy(context["ready"]["asset_rights_closure"]),
            "locale_neutral_r_pdf_pairs": 2,
            "separately_licensed_photos": 1,
        },
        "build_binding": {
            "terminal_contract": deepcopy(TERMINAL_CONTRACT_IDENTITY),
            "build_receipt": deepcopy(terminal_inputs["build_receipt"]),
            "reader_pdf": deepcopy(terminal_inputs["reader_pdf"]),
            "visual_qa": deepcopy(terminal_inputs["visual_qa"]),
        },
        "o001_closure": {
            "public_answers": list(PUBLIC_ANSWERS),
            "companion_gaps": list(O001_GAPS),
            "restricted_solutions_accessed_or_invented": False,
        },
        "interoperability": {
            "status": "passed", "spec": deepcopy(INTEROPERABILITY_SPEC),
            "required_views": list(SEMANTIC_BLUEPRINT["required_views"]),
        },
        "known_limitations": [
            "O001 exercise answers 18/20/22/24/26 remain explicit gaps; no restricted instructor solution was accessed or invented.",
            "Two generated figure PDFs are locale-neutral and reused byte-exact; their Indonesian captions and accessibility text are in TeX.",
            "The dreidel JPEG remains a separately governed CC BY 2.0 component with visible attribution.",
            "No Git operation, admission, publication, promotion, credential access, or upstream contact was performed by this compiler.",
        ],
        "deferred_actions": ["separate guarded admission", "publication after admission"],
        "files": file_entries,
    })
    manifest_schema = parse_json(
        require(
            BASE_EXPORTS / "schemas/backend-manifest-v0.1.0.schema.json",
            next(entry for entry in base_manifest["files"] if entry["path"] == "schemas/backend-manifest-v0.1.0.schema.json"),
        ),
        "backend manifest schema",
    )
    jsonschema.validate(instance=manifest, schema=manifest_schema)
    manifest_raw = canonical_json(manifest)
    return {
        "context": context,
        "base_records": base_records,
        "records": records,
        "new_counts": new_counts,
        "base_copy_entries": base_copy_entries,
        "generated_payloads": generated_payloads,
        "manifest": manifest,
        "manifest_raw": manifest_raw,
    }


def self_test() -> dict[str, Any]:
    keys: list[str] = []
    for name, value in SEMANTIC_BLUEPRINT.items():
        if name in {"relation_classes", "qa_event_types", "required_views"}:
            continue
        if isinstance(value, str) and value.startswith("r011/"):
            keys.append(value)
        elif isinstance(value, list):
            keys.extend(item for item in value if isinstance(item, str) and item.startswith("r011/"))
    if len(keys) != len(set(keys)):
        duplicates = sorted({key for key in keys if keys.count(key) > 1})
        raise RuntimeError(f"ambiguous B016 semantic keys: {duplicates}")
    for key in keys:
        if not re.fullmatch(r"r011/[A-Za-z0-9._/-]+", key):
            raise RuntimeError(f"invalid B016 stable key: {key}")
        uuid.UUID(stable_id(key))
    if sorted(EOCE) != list(range(17, 27)):
        raise RuntimeError("B016 EoCE semantic topology changed")
    if set(PUBLIC_ANSWERS) | set(O001_GAPS) != set(EOCE):
        raise RuntimeError("public-answer/O001 closure no longer partitions EoCE 17--26")
    if set(PUBLIC_ANSWERS) & set(O001_GAPS):
        raise RuntimeError("public-answer/O001 closure overlaps")
    return {
        "status": "PASS_B016_FINAL_COMPILER_INERT_SELF_TEST",
        "boundary_id": BOUNDARY_ID,
        "terminal_contract_bound": TERMINAL_CONTRACT_IDENTITY is not None,
        "predicted_record_classes": PREDICTED_RECORD_CLASSES,
        "reused_record_classes": REUSED_RECORD_CLASSES,
        "pending_roles": [],
        "new_record_count": None,
        "final_record_count": None,
    }


def probe() -> dict[str, Any]:
    context = load_context()
    return {
        **self_test(),
        "status": "PASS_B016_FINAL_COMPILER_READ_ONLY_PROBE",
        "base": bind_base(),
        "ready_inputs": context["ready"],
        "interoperability_spec": INTEROPERABILITY_SPEC,
        "terminal": {
            "contract_path": TERMINAL_CONTRACT.relative_to(LANE).as_posix(),
            "identity": TERMINAL_CONTRACT_IDENTITY,
            "identity_bound": True,
            "status": context["contract"]["status"],
            "closure": context["contract"]["closure"],
            "roles": sorted(context["contract"]["inputs"]),
            "pending": [],
            "required_gates": sorted(REQUIRED_TERMINAL_GATES),
        },
        "semantic_blueprint": SEMANTIC_BLUEPRINT,
    }


def generate(output: Path) -> dict[str, Any]:
    """Write one new isolated deterministic B016 backend stage."""
    resolved_output = output.resolve()
    if (
        not resolved_output.is_relative_to(FINAL_ROOT.resolve())
        or resolved_output == FINAL_ROOT.resolve()
    ):
        raise RuntimeError(f"B016 isolated stage must be within {FINAL_ROOT}")
    if resolved_output.exists():
        raise RuntimeError(f"B016 isolated stage already exists: {resolved_output}")
    compiled = compile_stage()
    resolved_output.parent.mkdir(parents=True, exist_ok=True)
    resolved_output.mkdir()
    for entry in compiled["base_copy_entries"]:
        relative = str(entry["path"])
        destination = resolved_output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(BASE_EXPORTS / relative, destination)
    for relative, raw in sorted(compiled["generated_payloads"].items()):
        destination = resolved_output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)
    (resolved_output / "manifest.json").write_bytes(compiled["manifest_raw"])
    validation = validate_stage(resolved_output)
    return {
        "status": "PASS_B016_ISOLATED_DETERMINISTIC_BACKEND_GENERATED",
        "boundary_id": BOUNDARY_ID,
        "output": resolved_output.relative_to(LANE).as_posix(),
        "manifest": {
            "bytes": len(compiled["manifest_raw"]),
            "sha256": sha256_bytes(compiled["manifest_raw"]),
        },
        "inventory": inventory(resolved_output),
        "record_count": compiled["manifest"]["record_count"],
        "record_counts": compiled["manifest"]["record_counts"],
        "new_b016_record_count": compiled["manifest"]["new_b016_record_count"],
        "new_b016_record_counts": compiled["manifest"]["new_b016_record_counts"],
        "validation_status": validation["status"],
    }


def validate_stage(stage: Path) -> dict[str, Any]:
    """Independently replay and validate one isolated B016 backend stage."""
    resolved_stage = stage.resolve()
    if (
        not resolved_stage.is_relative_to(FINAL_ROOT.resolve())
        or resolved_stage == FINAL_ROOT.resolve()
        or not resolved_stage.is_dir()
    ):
        raise RuntimeError(f"B016 stage must be within {FINAL_ROOT}")
    compiled = compile_stage()
    expected_entries = {
        str(entry["path"]): {
            "bytes": int(entry["bytes"]), "sha256": str(entry["sha256"])
        }
        for entry in compiled["manifest"]["files"]
    }
    expected_entries["manifest.json"] = {
        "bytes": len(compiled["manifest_raw"]),
        "sha256": sha256_bytes(compiled["manifest_raw"]),
    }
    observed_paths = {
        path.relative_to(resolved_stage).as_posix()
        for path in resolved_stage.rglob("*") if path.is_file()
    }
    if observed_paths != set(expected_entries):
        raise RuntimeError(
            f"B016 stage inventory differs: missing={sorted(set(expected_entries)-observed_paths)!r} "
            f"extra={sorted(observed_paths-set(expected_entries))!r}"
        )
    for relative, expected in sorted(expected_entries.items()):
        require(resolved_stage / relative, expected)
    if (resolved_stage / "manifest.json").read_bytes() != compiled["manifest_raw"]:
        raise RuntimeError("B016 stage manifest is not the deterministic replay")
    for relative, raw in compiled["generated_payloads"].items():
        if (resolved_stage / relative).read_bytes() != raw:
            raise RuntimeError(f"B016 generated payload differs from replay: {relative}")

    record_schema = parse_json(
        (resolved_stage / "schemas/backend-record-v0.1.0.schema.json").read_bytes(),
        "backend record schema",
    )
    validator = jsonschema.Draft202012Validator(
        record_schema, format_checker=jsonschema.FormatChecker()
    )
    all_rows = [row for rows in compiled["records"].values() for row in rows]
    all_ids = {str(row["id"]) for row in all_rows}
    if len(all_ids) != len(all_rows):
        raise RuntimeError("B016 backend contains duplicate UUIDs")
    for row in all_rows:
        if row.get("boundary_id") == BOUNDARY_ID:
            validator.validate(row)
            if str(row["id"]) != stable_id(str(row["stable_key"])):
                raise RuntimeError(f"B016 stable identity mismatch: {row['stable_key']}")
            for field in (
                "resource_id", "edition_id", "parent_id", "unit_id", "source_segment_id",
                "concept_id", "from_id", "to_id", "affected_id", "subject_id",
                "witness_artifact_id",
            ):
                value = row.get(field)
                if value is not None and str(value) not in all_ids:
                    raise RuntimeError(f"dangling B016 {field} on {row['stable_key']}: {value}")
            for value in row.get("rights_component_ids", []):
                if str(value) not in all_ids:
                    raise RuntimeError(f"dangling B016 rights component on {row['stable_key']}: {value}")

    for name, base_rows in compiled["base_records"].items():
        staged = {str(row["id"]): canonical_json_text(row) for row in compiled["records"][name]}
        for row in base_rows:
            if staged.get(str(row["id"])) != canonical_json_text(row):
                raise RuntimeError(f"B015 base record changed in B016 stage: {row['stable_key']}")

    new_rows = [row for row in all_rows if row.get("boundary_id") == BOUNDARY_ID]
    if len(new_rows) != int(compiled["manifest"]["new_b016_record_count"]):
        raise RuntimeError("B016 new-record count differs from manifest")
    required_types = set(PREDICTED_RECORD_CLASSES)
    if {str(row["record_type"]) for row in new_rows} != required_types:
        raise RuntimeError("B016 new-record class closure differs")
    if {row["qa_type"] for row in new_rows if row["record_type"] == "qa_event"} != set(SEMANTIC_BLUEPRINT["qa_event_types"]):
        raise RuntimeError("B016 typed QA-event closure differs")
    b016_relations = [row for row in new_rows if row["record_type"] == "relation"]
    relation_types = {str(row["relation_type"]) for row in b016_relations}
    if relation_types != set(SEMANTIC_BLUEPRINT["relation_classes"]):
        raise RuntimeError(
            f"B016 relation-class closure differs: {sorted(relation_types)!r}"
        )
    if compiled["manifest"]["correction_closure"]["source_corrections"] != list(CORRECTION_CODES):
        raise RuntimeError("B016 surviving correction-code closure differs")
    if compiled["manifest"]["source_application"]["terminal_contract"] != {
        "path": TERMINAL_CONTRACT.relative_to(LANE).as_posix(),
        **TERMINAL_CONTRACT_IDENTITY,
    }:
        raise RuntimeError("B016 terminal contract manifest binding differs")
    return {
        "status": "PASS_B016_INDEPENDENT_DETERMINISTIC_STAGE_VALIDATION",
        "boundary_id": BOUNDARY_ID,
        "stage": resolved_stage.relative_to(LANE).as_posix(),
        "manifest": expected_entries["manifest.json"],
        "inventory": inventory(resolved_stage),
        "record_count": compiled["manifest"]["record_count"],
        "record_counts": compiled["manifest"]["record_counts"],
        "new_b016_record_count": compiled["manifest"]["new_b016_record_count"],
        "base_records_preserved": BASE_RECORD_COUNT,
        "checks": [
            "terminal_contract_exact", "all_terminal_gates_passed",
            "manifest_schema_valid", "stage_inventory_exact", "generated_payload_replay_exact",
            "record_schema_valid", "stable_uuid_identity_exact", "referential_integrity",
            "base_record_canonical_bytes_preserved", "required_views_replayed",
            "typed_qa_closure", "relation_class_closure", "source_correction_closure",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--self-test", action="store_true", help="run inert structural checks")
    modes.add_argument("--probe", action="store_true", help="verify exact base and ready inputs without writing")
    modes.add_argument("--output", type=Path, help="write a new isolated deterministic B016 stage")
    args = parser.parse_args()
    try:
        if args.self_test:
            result = self_test()
        elif args.probe:
            result = probe()
        else:
            result = generate(args.output)
        print(canonical_json(result).decode("utf-8"), end="")
    except TerminalInputsUnresolved as exc:
        print(
            canonical_json({
                "status": "BLOCKED_EXACT_NONHUMAN_TERMINAL_INPUTS_UNRESOLVED",
                "boundary_id": BOUNDARY_ID,
                "error": str(exc),
                "pending_roles": sorted(PENDING_TERMINAL_ROLES),
                "output_written": False,
            }).decode("utf-8"),
            end="",
            file=sys.stderr,
        )
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
