#!/usr/bin/env python3
"""Deterministic, fail-closed source gate for R011-B006.

The gate advances only the exact B006 overlays from the admitted R011-B005
snapshot.  It never scans Git or the live repository.  The target manifest is
reconstructed from the immutable B005 manifest plus a bounded list of three
TeX files and the 13 localized figures/eight pinned producer witnesses used by
Section 2.2.  Unrelated live-tree work therefore cannot leak into this
boundary.

Without ``--write`` the script is read-only and prints the identity of the
candidate manifest and receipts.  ``--write`` atomically writes all three
artifacts only after every source, topology, correction, O001, rights,
layout-repair, rejected-build, and asset-closure check passes.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


LANE = Path(__file__).resolve().parents[1]
REPO = LANE / "repo"
QA = LANE / "qa"
CONTROL = LANE / "00_control"
AUTHORITY = (
    LANE
    / "authority"
    / "upstream"
    / "openintro-statistics-fee25091fb24e89c36296fd67c48c1fcf7a93b6e"
)
BASE_SNAPSHOT = QA / "b005-build" / "source-snapshot-v9"

BASE_RECEIPT = QA / "BOUNDARY_RECEIPT_R011-B005.json"
BASE_MANIFEST = QA / "R011-B005_TARGET_MANIFEST.tsv"
BASE_SNAPSHOT_RECEIPT = QA / "b005-build" / "SNAPSHOT_RECEIPT_V9.json"
TARGET_MANIFEST = QA / "R011-B006_TARGET_MANIFEST.tsv"
RECEIPT = QA / "R011-B006_SOURCE_QA.json"
LAYOUT_REPAIR_RECEIPT = QA / "R011-B006_LAYOUT_REPAIR_RECEIPT_V4.json"
V3_LAYOUT_REPAIR_RECEIPT = QA / "R011-B006_LAYOUT_REPAIR_RECEIPT_V3.json"

ASSET_MANIFEST = QA / "b006-assets" / "ASSET_MANIFEST_R011-B006.json"
ASSET_RECEIPT = (
    QA / "b006-assets" / "ASSET_VALIDATION_RECEIPT_R011-B006.json"
)
ASSET_LOCALIZER = LANE / "scripts" / "localize_b006_figures.py"
SOURCE_PREAPPLICATION_MANIFEST = QA / "R011-B006_PREAPPLICATION_MANIFEST.json"
SOURCE_APPLICATION_RECEIPT = QA / "R011-B006_SOURCE_APPLICATION_RECEIPT.json"
REPAIR_RECEIPT = QA / "R011-B006_REPAIR_RECEIPT.json"
V1_BUILD_RECEIPT = QA / "R011-B006_BUILD_QA_V1_REJECTED.json"
V1_VISUAL_FINDINGS = QA / "R011-B006_VISUAL_FINDINGS_V1.json"
V1_SNAPSHOT_RECEIPT = QA / "b006-build" / "SNAPSHOT_RECEIPT_V1.json"
V1_SOURCE_SNAPSHOT = QA / "b006-build" / "source-snapshot-v1"
V2_BUILD_RECEIPT = QA / "R011-B006_BUILD_QA_V2_REJECTED.json"
V2_VISUAL_FINDINGS = QA / "R011-B006_VISUAL_FINDINGS_V2.json"
V2_SOURCE_SNAPSHOT = QA / "b006-build" / "source-snapshot-v2"
V3_BUILD_RECEIPT = QA / "R011-B006_BUILD_QA_V3_REJECTED.json"
V3_VISUAL_FINDINGS = QA / "R011-B006_VISUAL_FINDINGS_V3.json"
V3_CANDIDATE_BUILD_RECEIPT = (
    QA / "b006-build" / "final-v3" / "CANDIDATE_BUILD_QA_V3.json"
)
V3_CANDIDATE_PDF = QA / "b006-build" / "final-v3" / "main.pdf"
V3_SOURCE_SNAPSHOT = QA / "b006-build" / "source-snapshot-v3"
V3_RENDER_MANIFEST = QA / "b006-render" / "final-v3" / "FINAL_MANIFEST.tsv"
V3_PAGE_LOCATOR = QA / "b006-render" / "final-v3" / "PAGE_LOCATOR.json"
V3_CONTACT_SHEET = QA / "b006-render" / "final-v3" / "CONTACT_SHEET.png"

AUTHORITY_REPOSITORY = "https://github.com/OpenIntroStat/openintro-statistics"
AUTHORITY_COMMIT = "fee25091fb24e89c36296fd67c48c1fcf7a93b6e"
AUTHORITY_TREE = "d61cc601e7d97759ce805900520f784d02a0489e"
BOUNDARY_ID = "R011-B006"

BASE_IDENTITIES: dict[Path, tuple[int, str]] = {
    BASE_RECEIPT: (
        17758,
        "4d5618ccc28cf9c58d1f0f4c04a22d89946e824f31984a350f47558b0a24e70f",
    ),
    BASE_MANIFEST: (
        171577,
        "8e84e688c354757b52b081a0d79f848a6f9e651c339760f92cf3f123eabb6fe0",
    ),
    BASE_SNAPSHOT_RECEIPT: (
        1116,
        "0ef484a824dcfc6625f7104c6bc68afb7b4514bc23d7a48ea749a85c9a196955",
    ),
}

SOURCE_HANDOFF_IDENTITIES: dict[Path, tuple[int, str]] = {
    SOURCE_PREAPPLICATION_MANIFEST: (
        3983,
        "d6e832dc0519892bf29cb94672c7210b4886425666b36947f42883d355e73965",
    ),
    SOURCE_APPLICATION_RECEIPT: (
        9586,
        "56d69a600cf4ad1bb18ede91b588266fba4e1f10f8356ba67ec96103d3a84286",
    ),
}

REPAIR_HANDOFF_IDENTITIES: dict[Path, tuple[int, str]] = {
    REPAIR_RECEIPT: (
        12510,
        "145f3b47954a03999d3695e2dbd3206717dd89af76ea8aaad63974e431321492",
    ),
    V1_BUILD_RECEIPT: (
        15819,
        "e649a2cbe71f4041b0684f8764b7297a5cbcbac4c8c78ed412a2e0b297806e16",
    ),
    V1_VISUAL_FINDINGS: (
        2013,
        "cc4adb506a84b231d2d0988ee024dd673e2ae3b70cca9d7b9924333e8d923231",
    ),
    V1_SNAPSHOT_RECEIPT: (
        1126,
        "8b98ca44a40afeaac80fb9ae45c01307ec145530267404790b923992a61d89c7",
    ),
}

V2_REJECTION_IDENTITIES: dict[Path, tuple[int, str]] = {
    V2_BUILD_RECEIPT: (
        2066,
        "9792c0fc177e652889575c7ffdfcbbe503fbabca08e53224a8c52f39c42c7188",
    ),
    V2_VISUAL_FINDINGS: (
        2396,
        "6221077b007c1357e4524fdefc1719cd4beedeea4a363d5919e012a7ceea950c",
    ),
}

V2_TARGET_MANIFEST_IDENTITY = (
    173738,
    "d8bd3f832477e48489a52f3d211d293088528dc341548bb30e3f587de4c6640a",
)
V2_ADVERSE_LEDGER_IDENTITY = (
    34107,
    "3a1af7e6aad254569520cbb2e118140535f18878536da270db5a683470c7a063",
)

V3_LAYOUT_HANDOFF_IDENTITIES: dict[Path, tuple[int, str]] = {
    V3_LAYOUT_REPAIR_RECEIPT: (
        11120,
        "fd3e6048d0e68b6e6287463f7d85f686a33f0770f59bb1c3d5cdd9445e6b59be",
    ),
}
V3_REJECTION_IDENTITIES: dict[Path, tuple[int, str]] = {
    V3_BUILD_RECEIPT: (
        2408,
        "717e987c26fb76783ba612563790faed06f16791ba2edb369022eedb0ac7a5d9",
    ),
    V3_VISUAL_FINDINGS: (
        2150,
        "4126d7612063aa9497bdaaa1d0526087160ed266398c223dffbf31042d3585b3",
    ),
    V3_CANDIDATE_BUILD_RECEIPT: (
        14938,
        "c78aa1ea63ff4795df681ebcc6ecd5776b941104bffd4835bf981d46d62028a8",
    ),
    V3_CANDIDATE_PDF: (
        21976293,
        "7fb77cd62425d4237f35e24791d1206f6eec704fc40b50d4a7159953f2647cab",
    ),
    V3_RENDER_MANIFEST: (
        1410,
        "3597475ea9c386ce984d8999c08171116587872c9cb84db49f13e41b3834569e",
    ),
    V3_PAGE_LOCATOR: (
        1388,
        "09fc9270227974d1b2b95f5a54dd2ba130dd13adc13afb8bf66dba9fee4412c7",
    ),
    V3_CONTACT_SHEET: (
        728886,
        "dda65bfe0e02ff72f5b428d6288b27bd094083c50681ae71f4af33dc1f955a32",
    ),
}
V3_TARGET_MANIFEST_IDENTITY = (
    173738,
    "f4e717e06956a4f1633164f3d6711d414d06c4bf5f9c736a8f89e1ecb6e952da",
)
V3_SOURCE_RECEIPT_IDENTITY = (
    42133,
    "8bcec78a0d385219715756bb595b80936d39e0f4bfd64e208038d4989781a11e",
)
V3_ADVERSE_LEDGER_IDENTITY = (
    35453,
    "a7c204002629921e8e09076e94e8c5aa8dc8f09314e6f4fd4f2d9c9c475c6d29",
)

ASSET_HANDOFF_IDENTITIES: dict[Path, tuple[int, str]] = {
    ASSET_MANIFEST: (
        20602,
        "12df13ae4eeac43f492ec77efbe96d8470ffda0aeaf0c16265c879f4f1fb41ac",
    ),
    ASSET_RECEIPT: (
        8001,
        "3c9843944b53e7791fc0998f625dc31d6adcc63250fca4fe9d34f4cd1bcd4582",
    ),
    ASSET_LOCALIZER: (
        20207,
        "12071f770b73440a98722a430cc09d046465e2469d7956bfc08b4e618913f6b4",
    ),
}

CONTROL_IDENTITIES: dict[Path, tuple[int, str]] = {
    CONTROL / "ADVERSE_LEDGER.jsonl": (
        36030,
        "04032e0f4486268d99d809333779fd450d4062d376149ca0945f34e24f8af7c3",
    ),
    CONTROL / "TERMINOLOGY.csv": (
        11279,
        "622fa65372875784cb190619175750bcfbfa9600bcc4526f521019c39f093f7e",
    ),
    CONTROL / "COMPONENT_RIGHTS.csv": (
        9999,
        "009feba8ff1f329ef742793f55f6b090dd08f3f761f9b9cc1edcbe03ecff58f0",
    ),
}

BODY = "ch_summarizing_data/TeX/ch_summarizing_data.tex"
EXERCISES = "ch_summarizing_data/TeX/considering_categorical_data.tex"
SOLUTIONS = "extraTeX/eoceSolutions/eoceSolutions.tex"
SOURCE_OVERLAYS = (BODY, EXERCISES, SOLUTIONS)

SOURCE_TARGET_IDENTITIES: dict[str, tuple[int, str]] = {
    BODY: (
        114048,
        "fe8049a4452ea7aed9fc83e28d092a8526b5e7bc5c4dec834af4450c77e63c8f",
    ),
    EXERCISES: (
        6598,
        "afba6b55c86da135e1f2998c6736a24bb6319b056c1c47df5b2a618e2fa9f72f",
    ),
    SOLUTIONS: (
        107958,
        "3168a26366c4890ca5b11dfee1b48abc1724e64c3976873036fcc4211ce881a9",
    ),
}

V2_SOURCE_TARGET_IDENTITIES: dict[str, tuple[int, str]] = {
    BODY: (
        114087,
        "6b3bdafd2862163e7bc7984acb4b44ead0aaf872f8a9d11cf0280744daf286c2",
    ),
    EXERCISES: (
        6598,
        "afba6b55c86da135e1f2998c6736a24bb6319b056c1c47df5b2a618e2fa9f72f",
    ),
    SOLUTIONS: (
        107949,
        "2f81c2f2e4afd739153a1a2e1f6059fa32ee10c9a5c38588977802b9831d3a75",
    ),
}

V3_SOURCE_TARGET_IDENTITIES: dict[str, tuple[int, str]] = {
    BODY: (
        114091,
        "3a087003f4bcb01268090fc2a04a8c40f9b46da7ff5a5f276a591a9d266e7a9c",
    ),
    EXERCISES: (
        6658,
        "2e56b476d8e96e0db30395e40fbe129b0d08739b6292373778d647f529f6d143",
    ),
    SOLUTIONS: (
        107940,
        "49ad90a6c041ec23cfb99ce5f0a1ece6bf45516cc82eabbe02474c1604749b43",
    ),
}

FINAL_SOURCE_TARGET_IDENTITIES: dict[str, tuple[int, str]] = {
    BODY: (
        114091,
        "3a087003f4bcb01268090fc2a04a8c40f9b46da7ff5a5f276a591a9d266e7a9c",
    ),
    EXERCISES: (
        6644,
        "dd8f682d4188597869ec0e3bd873e04b0be3c6636de117788ff65101ba2241ab",
    ),
    SOLUTIONS: (
        107940,
        "49ad90a6c041ec23cfb99ce5f0a1ece6bf45516cc82eabbe02474c1604749b43",
    ),
}

EXPECTED_V2_REPAIR_ADVERSE_IDS = tuple(
    f"R011-ADV-{number:04d}" for number in range(70, 77)
)
EXPECTED_REPAIR_ADVERSE_IDS = tuple(
    f"R011-ADV-{number:04d}" for number in range(70, 80)
)
EXPECTED_V3_LAYOUT_REPAIR_ADVERSE_IDS = ("R011-ADV-0077", "R011-ADV-0078")
EXPECTED_LAYOUT_REPAIR_ADVERSE_IDS = ("R011-ADV-0079",)
EXPECTED_REPAIR_OPERATION_IDS = (
    "R011-B006-RPR-001A",
    "R011-B006-RPR-001B",
    "R011-B006-RPR-001C",
    "R011-B006-RPR-001D",
    "R011-B006-RPR-001E",
    "R011-B006-RPR-001F",
    "R011-B006-RPR-001G",
    "R011-B006-RPR-001H",
    "R011-B006-RPR-001I",
    "R011-B006-RPR-001J",
    "R011-B006-RPR-002",
    "R011-B006-RPR-006",
    "R011-B006-RPR-003",
    "R011-B006-RPR-004A",
    "R011-B006-RPR-004B",
    "R011-B006-RPR-005",
    "R011-B006-RPR-007",
)
EXPECTED_REPAIR_OPERATION_ADVERSE_IDS = (
    *("R011-ADV-0070",) * 10,
    "R011-ADV-0071",
    "R011-ADV-0075",
    "R011-ADV-0072",
    "R011-ADV-0073",
    "R011-ADV-0073",
    "R011-ADV-0074",
    "R011-ADV-0076",
)
EXPECTED_REPAIR_OPERATION_PATHS = (
    *("repo/" + BODY,) * 16,
    "repo/" + SOLUTIONS,
)

V3_LAYOUT_REPAIR_OPERATIONS: tuple[dict[str, object], ...] = (
    {
        "id": "R011-B006-LYT-V3-001A",
        "adverse_id": "R011-ADV-0077",
        "path": "repo/" + BODY,
        "before_utf8": (
            "digambar dengan skala yang sama.\n\n"
            "\\begin{figure}\n"
            "  \\centering\n"
        ),
        "after_utf8": (
            "digambar dengan skala yang sama.\n\n"
            "\\begin{figure}[!t]\n"
            "  \\centering\n"
        ),
        "expected_occurrences": 1,
    },
    {
        "id": "R011-B006-LYT-V3-001B",
        "adverse_id": "R011-ADV-0077",
        "path": "repo/" + EXERCISES,
        "before_utf8": "\\exercisesheader{}\n\n% 21\n",
        "after_utf8": (
            "\\begingroup\n"
            "\\renewcommand{\\clearpageforsection}{}\n"
            "\\exercisesheader{}\n"
            "\\endgroup\n\n% 21\n"
        ),
        "expected_occurrences": 1,
    },
    {
        "id": "R011-B006-LYT-V3-002",
        "adverse_id": "R011-ADV-0078",
        "path": "repo/" + SOLUTIONS,
        "before_utf8": (
            "dependent.}\n\n"
            "\\end{multicols}\n"
            "\\newpage\n"
            "\\begin{multicols}{2}\n\n% 9\n"
        ),
        "after_utf8": (
            "dependent.}\n\n"
            "\\end{multicols}\n"
            "\\begin{multicols}{2}\n\n% 9\n"
        ),
        "expected_occurrences": 1,
    },
)

LAYOUT_REPAIR_OPERATIONS: tuple[dict[str, object], ...] = (
    {
        "id": "R011-B006-LYT-V4-001",
        "adverse_id": "R011-ADV-0079",
        "path": "repo/" + EXERCISES,
        "before_utf8": "}{}\n\n\\D{\\newpage}\n\n% 23\n",
        "after_utf8": "}{}\n\n% 23\n",
        "expected_occurrences": 1,
    },
)

AUTHORITY_SOURCE_IDENTITIES: dict[str, tuple[int, str]] = {
    BODY: (
        114376,
        "00fb044707824539b57a27f6e258165c62c4f29769679305641214c6d4552f51",
    ),
    EXERCISES: (
        6457,
        "e3f3c9c59e4eaf91af77bea44432ea244a51a160ae89f602612b136d349c47b2",
    ),
    SOLUTIONS: (
        106045,
        "6c4e01376db4c023cc7b3f9949490e57220ef1cb831c580da71efde6ce723268",
    ),
}

ASSET_PRODUCERS = (
    "ch_summarizing_data/figures/loan_homeownership_bar_plot/loan_homeownership_bar_plot.R",
    "ch_summarizing_data/figures/loan_app_type_home_seg_bar/loan_app_type_home_seg_bar.R",
    "ch_summarizing_data/figures/loan_app_type_home_mosaic_plot/loan_app_type_home_mosaic_plot.R",
    "ch_summarizing_data/figures/loan_homeownership_pie_chart/loan_homeownership_pie_chart.R",
    "ch_summarizing_data/figures/countyIncomeSplitByPopGain/countyIncomeSplitByPopGain.R",
    "ch_summarizing_data/figures/eoce/antibiotic_use_children/antibiotic_use_children.R",
    "ch_summarizing_data/figures/eoce/dream_act_mosaic/dream_act_mosaic.R",
    "ch_summarizing_data/figures/eoce/raise_taxes_mosaic/raise_taxes_mosaic.R",
)

ASSET_PDFS = (
    "ch_summarizing_data/figures/loan_homeownership_bar_plot/loan_homeownership_bar_plot.pdf",
    "ch_summarizing_data/figures/loan_app_type_home_seg_bar/loan_app_type_home_seg_bar.pdf",
    "ch_summarizing_data/figures/loan_app_type_home_seg_bar/loan_app_type_home_sbs_bar.pdf",
    "ch_summarizing_data/figures/loan_app_type_home_seg_bar/loan_app_type_home_seg_bar_standardized.pdf",
    "ch_summarizing_data/figures/loan_app_type_home_mosaic_plot/loan_home_mosaic.pdf",
    "ch_summarizing_data/figures/loan_app_type_home_mosaic_plot/loan_app_type_home_mosaic.pdf",
    "ch_summarizing_data/figures/loan_app_type_home_mosaic_plot/loan_app_type_home_mosaic_rev.pdf",
    "ch_summarizing_data/figures/loan_homeownership_pie_chart/loan_homeownership_pie_chart.pdf",
    "ch_summarizing_data/figures/countyIncomeSplitByPopGain/countyIncomeSplitByPopGain.pdf",
    "ch_summarizing_data/figures/eoce/antibiotic_use_children/antibiotic_use_children_bar.pdf",
    "ch_summarizing_data/figures/eoce/antibiotic_use_children/antibiotic_use_children_pie.pdf",
    "ch_summarizing_data/figures/eoce/dream_act_mosaic/dream_act_mosaic.pdf",
    "ch_summarizing_data/figures/eoce/raise_taxes_mosaic/raise_taxes_mosaic.pdf",
)

ASSET_SOURCE_WITNESSES = tuple(
    path[:-4] + ".source-en.pdf" for path in ASSET_PDFS
)

# Producer files are admitted only if the asset lane changed them.  Including
# their current identity is harmless when they remain byte-identical to B005.
EXISTING_OVERLAY_CANDIDATES = SOURCE_OVERLAYS + ASSET_PDFS + ASSET_PRODUCERS
ADDED_OVERLAYS = ASSET_SOURCE_WITNESSES
OVERLAY_CANDIDATES = EXISTING_OVERLAY_CANDIDATES + ADDED_OVERLAYS
EXPECTED_CHANGED_PATHS = tuple(sorted(SOURCE_OVERLAYS + ASSET_PDFS))
EXPECTED_TARGET_FILE_COUNT = 1195
EXPECTED_TARGET_FILE_BYTES = 41205947
EXPECTED_ADDED_FILE_BYTES = 65607

TEX_ASSET_IDS = (
    "loan_homeownership_bar_plot",
    "loan_app_type_home_seg_bar",
    "loan_app_type_home_sbs_bar",
    "loan_app_type_home_seg_bar_standardized",
    "loan_home_mosaic",
    "loan_app_type_home_mosaic",
    "loan_app_type_home_mosaic_rev",
    "loan_homeownership_pie_chart",
    "countyIncomeSplitByPopGain",
    "antibiotic_use_children_bar",
    "antibiotic_use_children_pie",
    "dream_act_mosaic",
    "raise_taxes_mosaic",
)

ALT_REQUIRED_LABELS: dict[str, tuple[str, ...]] = {
    "loan_homeownership_bar_plot": (
        "Kepemilikan rumah",
        "Frekuensi",
        "Proporsi",
        "sewa",
        "hipotek",
        "milik",
    ),
    "loan_app_type_home_seg_bar": (
        "Kepemilikan rumah",
        "Frekuensi",
        "jenis pengajuan",
        "perorangan",
        "bersama",
    ),
    "loan_app_type_home_sbs_bar": (
        "kepemilikan rumah",
        "perorangan",
        "bersama",
        "sewa",
        "hipotek",
        "milik",
    ),
    "loan_app_type_home_seg_bar_standardized": (
        "kepemilikan rumah",
        "perorangan",
        "bersama",
        "sewa",
        "hipotek",
        "milik",
    ),
    "loan_home_mosaic": ("kepemilikan rumah", "sewa", "hipotek", "milik"),
    "loan_app_type_home_mosaic": (
        "kepemilikan rumah",
        "perorangan",
        "bersama",
        "sewa",
        "hipotek",
        "milik",
    ),
    "loan_app_type_home_mosaic_rev": (
        "jenis pengajuan",
        "perorangan",
        "bersama",
        "sewa",
        "hipotek",
        "milik",
    ),
    "loan_homeownership_pie_chart": (
        "kepemilikan rumah",
        "Frekuensi",
        "sewa",
        "hipotek",
        "milik",
    ),
    "countyIncomeSplitByPopGain": (
        "Pendapatan Rumah Tangga Median",
        "Perubahan jumlah penduduk",
        "Bertambah",
        "Tidak bertambah",
    ),
    "antibiotic_use_children_bar": (
        "Frekuensi relatif",
        "Prematuritas",
        "Kardiovaskular",
        "Pernapasan",
        "Neuromuskular",
        "Imunokompromais",
    ),
    "antibiotic_use_children_pie": (
        "Prematuritas",
        "Kardiovaskular",
        "Pernapasan",
        "Neuromuskular",
        "Imunokompromais",
    ),
    "dream_act_mosaic": (
        "Konservatif",
        "Moderat",
        "Mendukung",
        "Tidak mendukung",
        "Tidak yakin",
    ),
    "raise_taxes_mosaic": (
        "Naikkan pajak orang kaya",
        "Naikkan pajak orang miskin",
        "Demokrat",
        "Republikan",
        "Indep./lainnya",
    ),
}

ALT_FORBIDDEN_ENGLISH_LABELS = (
    "Homeownership",
    "Frequency (count)",
    "Proportion",
    "Rent",
    "Mortgage",
    "Own",
    "Individual",
    "Joint",
    "No gain",
    "Prematurity",
    "Cardiovascular",
    "Respiratory",
    "Neuromuscular",
    "Genetic/metabolic",
    "Immunocompromised",
    "Conservative",
    "Moderate",
    "Support",
    "Not Support",
    "Not Sure",
    "Democrat",
    "Republican",
    "Independent/Other",
)

EXPECTED_EXERCISES = ("2.21", "2.22", "2.23", "2.24")
EXPECTED_PUBLIC_ANSWERS = ("2.21", "2.23")
EXPECTED_O001 = ("2.22", "2.24")
EXPECTED_CORRECTIONS = tuple(f"SC-B006-00{i}" for i in range(1, 6))

PROTECTED_CALLS = {
    "begin",
    "end",
    "label",
    "ref",
    "pageref",
    "subref",
    "input",
    "data",
    "var",
    "resp",
    "index",
    "cite",
    "footcite",
    "footfullcite",
    "url",
    "href",
}

FORBIDDEN_ENGLISH_WORDS = {
    "the",
    "and",
    "are",
    "was",
    "were",
    "with",
    "from",
    "into",
    "which",
    "this",
    "that",
    "these",
    "those",
    "shows",
    "shown",
    "show",
    "each",
    "their",
    "there",
    "where",
    "when",
    "what",
    "why",
    "how",
    "about",
    "than",
    "then",
    "also",
    "only",
    "more",
    "less",
    "between",
    "within",
    "across",
    "using",
    "used",
    "because",
    "while",
    "first",
    "second",
    "left",
    "right",
    "above",
    "below",
    "approximately",
}

PROTECTED_LITERALS = (
    "Homeownership",
    "Frequency (count)",
    "Proportion",
    "Rent",
    "Mortgage",
    "Own",
    "app_type",
    "Individual",
    "Joint",
    "Gain",
    "No gain",
    "Income",
    "Support",
    "Not Support",
    "Not Sure",
    "Prematurity",
    "Cardiovascular",
    "Respiratory",
    "Trauma",
    "Neuromuscular",
    "Genetic/metabolic",
    "Immunocompromised",
    "Gastrointestinal",
    "Conservative",
    "Moderate",
    "Liberal",
    "Democrat",
    "Republican",
    "Independent/Other",
    "County",
    "county",
    "DREAM Act",
    "Lending Club",
    "Apply for citizenship",
    "Guest worker",
    "Leave the country",
    "Not sure",
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def identity_bytes(data: bytes) -> dict[str, object]:
    return {"bytes": len(data), "sha256": sha256(data)}


def identity_path(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    return {
        "path": path.relative_to(LANE).as_posix(),
        "bytes": len(data),
        "sha256": sha256(data),
    }


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def read_bytes(path: Path, label: str, errors: list[str]) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        errors.append(f"cannot read {label}: {exc}")
        return b""


def read_json(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    raw = read_bytes(path, label, errors)
    if not raw:
        return {}
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        errors.append(f"cannot parse {label}: {exc}")
        return {}
    require(isinstance(value, dict), f"{label} root is not an object", errors)
    return value if isinstance(value, dict) else {}


def exact_identity(
    path: Path, expected: tuple[int, str], label: str, errors: list[str]
) -> bytes:
    raw = read_bytes(path, label, errors)
    if raw:
        require(
            (len(raw), sha256(raw)) == expected,
            f"{label} identity mismatch",
            errors,
        )
    return raw


def recursively_contains_placeholder(value: object) -> bool:
    if isinstance(value, dict):
        return any(recursively_contains_placeholder(item) for item in value.values())
    if isinstance(value, list):
        return any(recursively_contains_placeholder(item) for item in value)
    if isinstance(value, str):
        folded = value.casefold()
        return folded.strip() in {
            "placeholder",
            "todo",
            "tbd",
            "pending binding",
        } or "__placeholder__" in folded
    return False


def recursively_bad_state(value: object) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key.casefold() in {"status", "state", "result"} and isinstance(
                item, str
            ):
                folded = item.casefold().replace("_", "-")
                if folded in {"fail", "failed", "pending", "blocked", "rejected"}:
                    found.append(f"{key}={item}")
            found.extend(recursively_bad_state(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(recursively_bad_state(item))
    return found


def parse_manifest(
    raw: bytes, label: str, errors: list[str]
) -> dict[str, tuple[int, str]]:
    require(bool(raw), f"{label} is empty", errors)
    require(b"\r" not in raw, f"{label} is not LF-only", errors)
    require(raw.endswith(b"\n"), f"{label} lacks terminal LF", errors)
    try:
        lines = raw.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        errors.append(f"{label} is not UTF-8: {exc}")
        return {}
    rows: dict[str, tuple[int, str]] = {}
    ordered: list[str] = []
    for number, line in enumerate(lines, 1):
        parts = line.split("\t")
        if len(parts) != 3:
            errors.append(f"{label} row {number} has {len(parts)} columns")
            continue
        path, size_text, digest = parts
        path_parts = path.split("/")
        require(
            bool(path)
            and not path.startswith(("/", "\\"))
            and "\\" not in path
            and all(part not in {"", ".", ".."} for part in path_parts),
            f"unsafe or noncanonical {label} path at row {number}: {path!r}",
            errors,
        )
        try:
            size = int(size_text)
        except ValueError:
            errors.append(f"{label} row {number} has invalid byte count")
            continue
        require(path not in rows, f"duplicate {label} path: {path}", errors)
        require(
            re.fullmatch(r"[0-9a-f]{64}", digest) is not None,
            f"invalid {label} digest at row {number}",
            errors,
        )
        rows[path] = (size, digest)
        ordered.append(path)
    require(ordered == sorted(ordered), f"{label} is not sorted", errors)
    return rows


def render_manifest(rows: dict[str, tuple[int, str]]) -> bytes:
    return "".join(
        f"{path}\t{rows[path][0]}\t{rows[path][1]}\n" for path in sorted(rows)
    ).encode("utf-8")


def check_base(errors: list[str]) -> dict[str, tuple[int, str]]:
    for path, expected in BASE_IDENTITIES.items():
        exact_identity(path, expected, path.relative_to(LANE).as_posix(), errors)

    receipt = read_json(BASE_RECEIPT, "B005 admitted receipt", errors)
    require(receipt.get("boundary_id") == "R011-B005", "base boundary mismatch", errors)
    require(receipt.get("status") == "admitted", "B005 base is not admitted", errors)
    require(
        receipt.get("authority", {}).get("commit") == AUTHORITY_COMMIT
        and receipt.get("authority", {}).get("tree") == AUTHORITY_TREE,
        "B005 authority mismatch",
        errors,
    )
    require(
        receipt.get("next_cursor", {}).get("boundary_id") == BOUNDARY_ID,
        "B005 next cursor is not B006",
        errors,
    )
    # Exact bytes plus the top-level admitted state bind this immutable base.
    # Its history legitimately contains rejected build candidates and a check
    # name that mentions legacy placeholders.

    raw = read_bytes(BASE_MANIFEST, "B005 target manifest", errors)
    rows = parse_manifest(raw, "B005 target manifest", errors)
    require(len(rows) == 1182, "B005 base manifest count is not 1,182", errors)
    require(
        sum(size for size, _digest in rows.values()) == 41144346,
        "B005 base payload bytes are not 41,144,346",
        errors,
    )

    snapshot_receipt = read_json(
        BASE_SNAPSHOT_RECEIPT, "B005 snapshot receipt", errors
    )
    require(
        snapshot_receipt.get("status") == "pass"
        and snapshot_receipt.get("boundary_id") == "R011-B005"
        and snapshot_receipt.get("snapshot", {}).get(
            "path_set_and_all_file_identities_match_manifest"
        )
        is True,
        "B005 snapshot receipt semantics mismatch",
        errors,
    )

    # Re-read only the exact files B006 is allowed to overlay.  The B005
    # snapshot receipt already proves the remaining 1,158 files.
    for relative in EXISTING_OVERLAY_CANDIDATES:
        require(relative in rows, f"B006 overlay absent from B005 manifest: {relative}", errors)
        path = BASE_SNAPSHOT / relative
        raw_file = read_bytes(path, f"B005 snapshot {relative}", errors)
        if raw_file and relative in rows:
            require(
                (len(raw_file), sha256(raw_file)) == rows[relative],
                f"B005 snapshot overlay identity mismatch: {relative}",
                errors,
            )
    for relative in ADDED_OVERLAYS:
        require(
            relative not in rows,
            f"B006 source witness unexpectedly exists in B005 manifest: {relative}",
            errors,
        )
    return rows


def check_authority(errors: list[str]) -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    for relative, expected in AUTHORITY_SOURCE_IDENTITIES.items():
        result[relative] = exact_identity(
            AUTHORITY / relative, expected, f"authority {relative}", errors
        )
    return result


def check_source_handoff(errors: list[str]) -> dict[str, object]:
    for path, expected in SOURCE_HANDOFF_IDENTITIES.items():
        exact_identity(path, expected, path.relative_to(LANE).as_posix(), errors)
    manifest = read_json(
        SOURCE_PREAPPLICATION_MANIFEST, "B006 preapplication manifest", errors
    )
    receipt = read_json(SOURCE_APPLICATION_RECEIPT, "B006 source application receipt", errors)
    require(
        manifest.get("boundary_id") == BOUNDARY_ID
        and manifest.get("status") == "candidate_bound_before_application",
        "B006 preapplication manifest semantics mismatch",
        errors,
    )
    require(
        receipt.get("boundary_id") == BOUNDARY_ID
        and receipt.get("status") == "source_application_pass"
        and receipt.get("boundary_admitted") is False
        and receipt.get("errors") == [],
        "B006 source application receipt semantics mismatch",
        errors,
    )
    require(
        receipt.get("authority", {}).get("commit") == AUTHORITY_COMMIT
        and receipt.get("authority", {}).get("tree") == AUTHORITY_TREE,
        "B006 source handoff authority mismatch",
        errors,
    )
    handoff_outputs = {
        str(item.get("path")): (item.get("bytes"), item.get("sha256"))
        for item in receipt.get("canonical_outputs", [])
        if isinstance(item, dict)
    }
    for relative, expected in SOURCE_TARGET_IDENTITIES.items():
        require(
            handoff_outputs.get("repo/" + relative) == expected,
            f"B006 source handoff does not bind canonical output: {relative}",
            errors,
        )
    alignment = receipt.get("visible_label_alignment", {})
    require(
        alignment.get("status") == "pass"
        and alignment.get("figure_alternative_descriptions_checked") == 13
        and alignment.get("required_localized_labels_present") is True
        and alignment.get("stale_English_visible_label_tokens") == [],
        "B006 source handoff visible-label alignment mismatch",
        errors,
    )
    closure = receipt.get("exercise_solution_closure", {})
    gaps = closure.get("mastery_companion_gaps", [])
    require(
        closure.get("public_answers_applied") == ["2.21", "2.23"]
        and [item.get("exercise") for item in gaps if isinstance(item, dict)]
        == ["2.22", "2.24"]
        and closure.get("restricted_or_invented_solutions_added") is False,
        "B006 source handoff exercise/O001 closure mismatch",
        errors,
    )
    return {
        "preapplication_manifest": identity_path(SOURCE_PREAPPLICATION_MANIFEST),
        "application_receipt": identity_path(SOURCE_APPLICATION_RECEIPT),
        "pre_repair_canonical_outputs_exactly_bound": True,
    }


def receipt_identity(value: object) -> tuple[int, str] | None:
    if not isinstance(value, dict):
        return None
    size = value.get("bytes")
    digest = value.get("sha256")
    if (
        isinstance(size, int)
        and isinstance(digest, str)
        and re.fullmatch(r"[0-9a-f]{64}", digest) is not None
    ):
        return size, digest
    return None


def check_repair_handoff(
    errors: list[str],
) -> tuple[dict[str, object], dict[str, bytes]]:
    """Validate and reverse the exact, independently ledgered B006 repairs.

    The rejected v1 build trees may be archived after their compact receipts
    are frozen, so this gate binds those compact receipts rather than requiring
    the disposable render/build directories to remain loose.  The three exact
    source-snapshot witnesses are retained and re-read here.
    """

    for path, expected in REPAIR_HANDOFF_IDENTITIES.items():
        exact_identity(path, expected, path.relative_to(LANE).as_posix(), errors)
    receipt = read_json(REPAIR_RECEIPT, "B006 repair receipt", errors)
    build_v1 = read_json(V1_BUILD_RECEIPT, "B006 rejected build v1 receipt", errors)
    visual_v1 = read_json(V1_VISUAL_FINDINGS, "B006 visual findings v1", errors)

    require(
        receipt.get("schema_version") == "r011-b006-repair-receipt/1.0.0"
        and receipt.get("boundary_id") == BOUNDARY_ID
        and receipt.get("status") == "repair_applied_and_reverse_verified"
        and receipt.get("boundary_admitted") is False,
        "B006 repair receipt status/schema mismatch",
        errors,
    )
    require(
        receipt.get("authority")
        == {
            "repository": AUTHORITY_REPOSITORY,
            "commit": AUTHORITY_COMMIT,
            "tree": AUTHORITY_TREE,
        },
        "B006 repair receipt authority mismatch",
        errors,
    )

    pre = receipt.get("pre_repair_evidence", {})
    require(
        isinstance(pre, dict)
        and pre.get("source_application_receipt")
        == {
            "path": "qa/R011-B006_SOURCE_APPLICATION_RECEIPT.json",
            "bytes": SOURCE_HANDOFF_IDENTITIES[SOURCE_APPLICATION_RECEIPT][0],
            "sha256": SOURCE_HANDOFF_IDENTITIES[SOURCE_APPLICATION_RECEIPT][1],
        }
        and pre.get("source_gate_v1")
        == {
            "path": "qa/R011-B006_SOURCE_QA.json",
            "bytes": 22972,
            "sha256": "e47a1632fdd0124bf9ab96eabc2d107d64f33ec7f208a76b915a410623556ff9",
        }
        and pre.get("target_manifest_v1")
        == {
            "path": "qa/R011-B006_TARGET_MANIFEST.tsv",
            "bytes": 173738,
            "sha256": "477b957019e1e3f28e92c17dbf313991c57f3350aa7fb6280b3178d487cc9922",
        },
        "B006 repair receipt does not bind the exact pre-repair handoff/gate",
        errors,
    )

    snapshot = pre.get("source_snapshot_v1", {}) if isinstance(pre, dict) else {}
    expected_snapshot_files = [
        {
            "path": "qa/b006-build/source-snapshot-v1/" + relative,
            "bytes": expected[0],
            "sha256": expected[1],
        }
        for relative, expected in SOURCE_TARGET_IDENTITIES.items()
    ]
    require(
        isinstance(snapshot, dict)
        and snapshot.get("files") == expected_snapshot_files
        and snapshot.get("receipt")
        == {
            "path": "qa/b006-build/SNAPSHOT_RECEIPT_V1.json",
            "bytes": REPAIR_HANDOFF_IDENTITIES[V1_SNAPSHOT_RECEIPT][0],
            "sha256": REPAIR_HANDOFF_IDENTITIES[V1_SNAPSHOT_RECEIPT][1],
        },
        "B006 repair receipt source-snapshot-v1 binding mismatch",
        errors,
    )
    for relative, expected in SOURCE_TARGET_IDENTITIES.items():
        exact_identity(
            V1_SOURCE_SNAPSHOT / relative,
            expected,
            f"B006 pre-repair source snapshot {relative}",
            errors,
        )

    expected_final_outputs = [
        {
            "path": "repo/" + relative,
            "bytes": expected[0],
            "sha256": expected[1],
        }
        for relative, expected in V2_SOURCE_TARGET_IDENTITIES.items()
    ]
    require(
        receipt.get("final_canonical_outputs") == expected_final_outputs,
        "B006 repair receipt final-source binding mismatch",
        errors,
    )
    final_raw: dict[str, bytes] = {}
    for relative, expected in V2_SOURCE_TARGET_IDENTITIES.items():
        final_raw[relative] = exact_identity(
            V2_SOURCE_SNAPSHOT / relative,
            expected,
            f"B006 source-snapshot-v2 repaired source {relative}",
            errors,
        )
    require(
        receipt.get("final_control")
        == {
            "path": "00_control/ADVERSE_LEDGER.jsonl",
            "bytes": V2_ADVERSE_LEDGER_IDENTITY[0],
            "sha256": V2_ADVERSE_LEDGER_IDENTITY[1],
            "adverse_ids": list(EXPECTED_V2_REPAIR_ADVERSE_IDS),
        },
        "B006 repair receipt final adverse-ledger binding mismatch",
        errors,
    )

    repairs = receipt.get("repairs", {})
    operations = repairs.get("exact_substitutions", []) if isinstance(repairs, dict) else []
    require(
        isinstance(repairs, dict)
        and repairs.get("adverse_ids") == list(EXPECTED_V2_REPAIR_ADVERSE_IDS)
        and repairs.get("substitution_count") == 17
        and repairs.get("instructional_content_order_changed") is False
        and repairs.get("numeric_data_changed") is False,
        "B006 repair-set summary mismatch",
        errors,
    )
    require(
        isinstance(operations, list)
        and [item.get("id") for item in operations if isinstance(item, dict)]
        == list(EXPECTED_REPAIR_OPERATION_IDS)
        and [item.get("adverse_id") for item in operations if isinstance(item, dict)]
        == list(EXPECTED_REPAIR_OPERATION_ADVERSE_IDS)
        and [item.get("path") for item in operations if isinstance(item, dict)]
        == list(EXPECTED_REPAIR_OPERATION_PATHS),
        "B006 repair operation IDs/adverse IDs/paths are not the exact ordered set",
        errors,
    )

    reconstructed = dict(final_raw)
    operation_results: list[dict[str, object]] = []
    for item in reversed(operations if isinstance(operations, list) else []):
        if not isinstance(item, dict):
            errors.append("B006 repair operation is not an object")
            continue
        operation_id = str(item.get("id"))
        path_text = str(item.get("path"))
        relative = normalize_repo_path(path_text)
        before_text = item.get("before_utf8")
        after_text = item.get("after_utf8")
        expected_occurrences = item.get("expected_occurrences")
        require(
            set(item)
            == {
                "id",
                "adverse_id",
                "path",
                "before_utf8",
                "after_utf8",
                "expected_occurrences",
            },
            f"{operation_id} repair-operation field set mismatch",
            errors,
        )
        require(
            isinstance(before_text, str)
            and isinstance(after_text, str)
            and before_text != after_text
            and expected_occurrences == 1,
            f"{operation_id} repair-operation payload mismatch",
            errors,
        )
        if (
            relative not in reconstructed
            or not isinstance(before_text, str)
            or not isinstance(after_text, str)
        ):
            continue
        before = before_text.encode("utf-8")
        after = after_text.encode("utf-8")
        current = reconstructed[relative]
        observed = current.count(after)
        require(
            observed == expected_occurrences,
            f"{operation_id} after-fragment occurrence mismatch: "
            f"expected={expected_occurrences}, observed={observed}",
            errors,
        )
        if observed == expected_occurrences == 1:
            reconstructed[relative] = current.replace(after, before, 1)
        operation_results.append(
            {
                "id": operation_id,
                "adverse_id": item.get("adverse_id"),
                "path": path_text,
                "expected_occurrences": expected_occurrences,
                "observed_occurrences_during_reverse": observed,
            }
        )
    operation_results.reverse()

    reverse = receipt.get("reverse_reconstruction", {})
    expected_reverse_outputs = [
        {
            "path": "repo/" + relative,
            "bytes": expected[0],
            "sha256": expected[1],
        }
        for relative, expected in SOURCE_TARGET_IDENTITIES.items()
    ]
    require(
        isinstance(reverse, dict)
        and reverse.get("algorithm")
        == (
            "For each final file, replace every exact after_utf8 fragment with "
            "its before_utf8 fragment in reverse listed order; require exactly "
            "one occurrence of every fragment and no other mutation."
        )
        and reverse.get("all_outputs_match_pre_repair_identities") is True
        and reverse.get("outputs") == expected_reverse_outputs,
        "B006 repair receipt reverse-reconstruction claim mismatch",
        errors,
    )
    for relative, expected in SOURCE_TARGET_IDENTITIES.items():
        data = reconstructed.get(relative, b"")
        require(
            (len(data), sha256(data)) == expected,
            f"reverse reconstruction does not recover pre-repair identity: {relative}",
            errors,
        )
        witness = read_bytes(
            V1_SOURCE_SNAPSHOT / relative,
            f"B006 pre-repair witness {relative}",
            errors,
        )
        require(
            data == witness,
            f"reverse reconstruction is not byte-identical to source-snapshot-v1: {relative}",
            errors,
        )

    visual = receipt.get("visual_candidate_v1", {})
    expected_findings = [
        {
            "id": "R011-B006-V1-001",
            "adverse_id": "R011-ADV-0075",
            "repair_id": "R011-B006-RPR-006",
            "page": 65,
            "severity": "P2",
            "category": "severe_underfill",
        },
        {
            "id": "R011-B006-V1-002",
            "adverse_id": "R011-ADV-0076",
            "repair_id": "R011-B006-RPR-007",
            "page": 389,
            "severity": "P2",
            "category": "severe_underfill",
        },
    ]
    observed_findings = []
    if isinstance(visual, dict):
        for item in visual.get("findings", []):
            if isinstance(item, dict):
                observed_findings.append(
                    {key: item.get(key) for key in expected_findings[0]}
                )
    require(
        isinstance(visual, dict)
        and visual.get("status") == "rejected_visual"
        and visual.get("promoted") is False
        and visual.get("inspection_resolution_dpi") == 180
        and visual.get("candidate_pdf")
        == {
            "path": "qa/b006-build/final-v1/main.pdf",
            "bytes": 21976624,
            "sha256": "d52a180d68f85bc077982c187a7b0c8f3c33a6ad8f230641e31e52c57ce999d7",
            "pages": 425,
        }
        and visual.get("rejected_build_receipt")
        == {
            "path": "qa/R011-B006_BUILD_QA_V1_REJECTED.json",
            "bytes": REPAIR_HANDOFF_IDENTITIES[V1_BUILD_RECEIPT][0],
            "sha256": REPAIR_HANDOFF_IDENTITIES[V1_BUILD_RECEIPT][1],
        }
        and visual.get("visual_findings_receipt")
        == {
            "path": "qa/R011-B006_VISUAL_FINDINGS_V1.json",
            "bytes": REPAIR_HANDOFF_IDENTITIES[V1_VISUAL_FINDINGS][0],
            "sha256": REPAIR_HANDOFF_IDENTITIES[V1_VISUAL_FINDINGS][1],
        }
        and observed_findings == expected_findings,
        "B006 repair receipt rejected-v1 visual binding mismatch",
        errors,
    )
    require(
        build_v1.get("boundary_id") == BOUNDARY_ID
        and build_v1.get("status") == "rejected_visual"
        and build_v1.get("nonvisual_status") == "passed"
        and build_v1.get("candidate_artifact", {}).get("promoted") is False
        and build_v1.get("source_closure", {}).get("source_receipt")
        == pre.get("source_gate_v1")
        and build_v1.get("source_closure", {}).get("target_manifest")
        == pre.get("target_manifest_v1")
        and [item.get("id") for item in build_v1.get("visual_rejection", {}).get("findings", [])]
        == ["R011-B006-V1-001", "R011-B006-V1-002"],
        "B006 rejected-build-v1 compact receipt semantics mismatch",
        errors,
    )
    require(
        visual_v1.get("boundary_id") == BOUNDARY_ID
        and visual_v1.get("status") == "rejected"
        and visual_v1.get("pass_audit_created") is False
        and visual_v1.get("source_mutated") is False
        and visual_v1.get("rejected_build_receipt")
        == visual.get("rejected_build_receipt")
        and [item.get("id") for item in visual_v1.get("findings", [])]
        == ["R011-B006-V1-001", "R011-B006-V1-002"],
        "B006 visual-findings-v1 compact receipt semantics mismatch",
        errors,
    )

    evidence = {
        "status": "passed",
        "repair_receipt": identity_path(REPAIR_RECEIPT),
        "pre_repair_source_application_receipt": identity_path(SOURCE_APPLICATION_RECEIPT),
        "pre_repair_source_snapshot_receipt": identity_path(V1_SNAPSHOT_RECEIPT),
        "rejected_build_v1_receipt": identity_path(V1_BUILD_RECEIPT),
        "visual_findings_v1_receipt": identity_path(V1_VISUAL_FINDINGS),
        "adverse_ids": list(EXPECTED_V2_REPAIR_ADVERSE_IDS),
        "repair_group_count": len(EXPECTED_V2_REPAIR_ADVERSE_IDS),
        "exact_substitution_count": len(operations) if isinstance(operations, list) else 0,
        "reverse_operations": operation_results,
        "all_pre_repair_outputs_reconstructed_byte_exact": not any(
            (len(reconstructed.get(relative, b"")), sha256(reconstructed.get(relative, b"")))
            != expected
            for relative, expected in SOURCE_TARGET_IDENTITIES.items()
        ),
        "rejected_visual_findings_bound": ["R011-B006-V1-001", "R011-B006-V1-002"],
    }
    return evidence, reconstructed


def check_v2_rejection_and_layout_repair(
    errors: list[str],
) -> tuple[dict[str, object], dict[str, bytes], dict[str, bytes]]:
    """Bind rejected v2 and reverse only the three authorized v3 edits."""

    for path, expected in V2_REJECTION_IDENTITIES.items():
        exact_identity(path, expected, path.relative_to(LANE).as_posix(), errors)
    for path, expected in V3_LAYOUT_HANDOFF_IDENTITIES.items():
        exact_identity(path, expected, path.relative_to(LANE).as_posix(), errors)
    build_v2 = read_json(V2_BUILD_RECEIPT, "B006 rejected build v2 receipt", errors)
    visual_v2 = read_json(V2_VISUAL_FINDINGS, "B006 visual findings v2", errors)
    layout_receipt_v3 = read_json(
        V3_LAYOUT_REPAIR_RECEIPT, "B006 layout repair receipt v3", errors
    )

    expected_pdf = {
        "path": "qa/b006-build/final-v2/main.pdf",
        "pages": 425,
        "bytes": 21976316,
        "sha256": "22fc488fe22e60cf413920f8553dd71ebd7db15dc04e2e78e90b18f61b12bc2f",
    }
    expected_visual_identity = {
        "path": "qa/R011-B006_VISUAL_FINDINGS_V2.json",
        "bytes": V2_REJECTION_IDENTITIES[V2_VISUAL_FINDINGS][0],
        "sha256": V2_REJECTION_IDENTITIES[V2_VISUAL_FINDINGS][1],
    }
    require(
        build_v2.get("schema") == "openintro-boundary-build-rejection"
        and build_v2.get("boundary_id") == BOUNDARY_ID
        and build_v2.get("candidate") == "final-v2"
        and build_v2.get("status") == "rejected_visual"
        and build_v2.get("nonvisual_status") == "passed"
        and build_v2.get("candidate_artifact", {}).get("path")
        == expected_pdf["path"]
        and build_v2.get("candidate_artifact", {}).get("pages")
        == expected_pdf["pages"]
        and build_v2.get("candidate_artifact", {}).get("bytes")
        == expected_pdf["bytes"]
        and build_v2.get("candidate_artifact", {}).get("sha256")
        == expected_pdf["sha256"]
        and build_v2.get("candidate_artifact", {}).get(
            "pass_3_pass_4_byte_identical"
        )
        is True
        and build_v2.get("candidate_artifact", {}).get("promoted") is False
        and build_v2.get("visual_findings", {}).get("path")
        == expected_visual_identity["path"]
        and build_v2.get("visual_findings", {}).get("bytes")
        == expected_visual_identity["bytes"]
        and build_v2.get("visual_findings", {}).get("sha256")
        == expected_visual_identity["sha256"]
        and build_v2.get("visual_findings", {}).get("finding_ids")
        == ["R011-B006-V2-001", "R011-B006-V2-002"]
        and build_v2.get("source_snapshot")
        == {
            "path": "qa/b006-build/source-snapshot-v2",
            "file_count": 1195,
            "file_bytes": 41205906,
            "path_set_and_all_file_identities_match_manifest": True,
        }
        and build_v2.get("target_manifest")
        == {
            "path": "qa/R011-B006_TARGET_MANIFEST.tsv",
            "bytes": V2_TARGET_MANIFEST_IDENTITY[0],
            "sha256": V2_TARGET_MANIFEST_IDENTITY[1],
        }
        and build_v2.get("output_pdf_mutated") is False
        and build_v2.get("pass_audit_created") is False,
        "B006 rejected-build-v2 receipt semantics mismatch",
        errors,
    )
    require(
        layout_receipt_v3.get("schema_version")
        == "r011-b006-layout-repair-receipt-v3/1.0.0"
        and layout_receipt_v3.get("boundary_id") == BOUNDARY_ID
        and layout_receipt_v3.get("status")
        == "layout_repairs_applied_and_reverse_verified"
        and layout_receipt_v3.get("boundary_admitted") is False
        and layout_receipt_v3.get("pre_repair_evidence", {}).get(
            "rejected_build_v2_receipt"
        )
        == identity_path(V2_BUILD_RECEIPT)
        and layout_receipt_v3.get("pre_repair_evidence", {}).get(
            "visual_findings_v2_receipt"
        )
        == identity_path(V2_VISUAL_FINDINGS)
        and layout_receipt_v3.get("post_repair_target_manifest")
        == {
            "path": "qa/R011-B006_TARGET_MANIFEST.tsv",
            "bytes": V3_TARGET_MANIFEST_IDENTITY[0],
            "sha256": V3_TARGET_MANIFEST_IDENTITY[1],
        }
        and layout_receipt_v3.get("final_control")
        == {
            "path": "00_control/ADVERSE_LEDGER.jsonl",
            "bytes": V3_ADVERSE_LEDGER_IDENTITY[0],
            "sha256": V3_ADVERSE_LEDGER_IDENTITY[1],
            "adverse_ids": list(EXPECTED_V3_LAYOUT_REPAIR_ADVERSE_IDS),
            "validated_tail": list(
                f"R011-ADV-{number:04d}" for number in range(70, 79)
            ),
        },
        "B006 layout-repair-v3 receipt semantics mismatch",
        errors,
    )

    observed_findings = []
    for item in visual_v2.get("findings", []):
        if isinstance(item, dict):
            observed_findings.append(
                {
                    "id": item.get("id"),
                    "page": item.get("page"),
                    "severity": item.get("severity"),
                    "category": item.get("category"),
                }
            )
    expected_findings = [
        {
            "id": "R011-B006-V2-001",
            "page": 70,
            "severity": "P2",
            "category": "float_only_page_severe_underfill",
        },
        {
            "id": "R011-B006-V2-002",
            "page": 390,
            "severity": "P2",
            "category": "answer_continuation_severe_underfill",
        },
    ]
    require(
        visual_v2.get("schema") == "openintro-boundary-visual-findings"
        and visual_v2.get("boundary_id") == BOUNDARY_ID
        and visual_v2.get("candidate") == "final-v2"
        and visual_v2.get("status") == "rejected"
        and visual_v2.get("candidate_pdf") == expected_pdf
        and visual_v2.get("inspection_resolution_dpi") == 180
        and observed_findings == expected_findings
        and visual_v2.get("severity_counts")
        == {"P0": 0, "P1": 0, "P2": 2, "P3": 0}
        and visual_v2.get("pass_audit_created") is False
        and visual_v2.get("promoted") is False
        and visual_v2.get("output_pdf_mutated") is False,
        "B006 visual-findings-v2 semantics mismatch",
        errors,
    )

    v2_raw: dict[str, bytes] = {}
    v3_raw: dict[str, bytes] = {}
    for relative, expected in V2_SOURCE_TARGET_IDENTITIES.items():
        v2_raw[relative] = exact_identity(
            V2_SOURCE_SNAPSHOT / relative,
            expected,
            f"B006 source-snapshot-v2 {relative}",
            errors,
        )
    for relative, expected in V3_SOURCE_TARGET_IDENTITIES.items():
        v3_raw[relative] = exact_identity(
            V3_SOURCE_SNAPSHOT / relative,
            expected,
            f"B006 source-snapshot-v3 {relative}",
            errors,
        )

    reconstructed = dict(v3_raw)
    operation_results: list[dict[str, object]] = []
    for item in reversed(V3_LAYOUT_REPAIR_OPERATIONS):
        operation_id = str(item["id"])
        relative = normalize_repo_path(str(item["path"]))
        before = str(item["before_utf8"]).encode("utf-8")
        after = str(item["after_utf8"]).encode("utf-8")
        expected_occurrences = int(item["expected_occurrences"])
        pre_data = v2_raw.get(relative, b"")
        current = reconstructed.get(relative, b"")
        pre_before_count = pre_data.count(before)
        pre_after_count = pre_data.count(after)
        observed = current.count(after)
        current_before_count = current.count(before)
        require(
            pre_before_count == expected_occurrences and pre_after_count == 0,
            f"{operation_id} pre-v3 fragment occurrence mismatch",
            errors,
        )
        require(
            observed == expected_occurrences and current_before_count == 0,
            f"{operation_id} final-v3 fragment occurrence mismatch",
            errors,
        )
        if observed == expected_occurrences == 1:
            reconstructed[relative] = current.replace(after, before, 1)
        operation_results.append(
            {
                "id": operation_id,
                "adverse_id": item["adverse_id"],
                "path": item["path"],
                "pre_before_occurrences": pre_before_count,
                "pre_after_occurrences": pre_after_count,
                "final_before_occurrences": current_before_count,
                "final_after_occurrences": observed,
                "observed_occurrences_during_reverse": observed,
            }
        )
    operation_results.reverse()

    for relative, expected in V2_SOURCE_TARGET_IDENTITIES.items():
        reconstructed_data = reconstructed.get(relative, b"")
        require(
            (len(reconstructed_data), sha256(reconstructed_data)) == expected
            and reconstructed_data == v2_raw.get(relative, b""),
            f"v3 reverse reconstruction is not source-snapshot-v2 exact: {relative}",
            errors,
        )

    invariants = check_layout_only_invariants(v2_raw, v3_raw, errors)
    evidence = {
        "status": "passed",
        "rejected_build_v2_receipt": identity_path(V2_BUILD_RECEIPT),
        "visual_findings_v2_receipt": identity_path(V2_VISUAL_FINDINGS),
        "layout_repair_receipt_v3": identity_path(V3_LAYOUT_REPAIR_RECEIPT),
        "source_snapshot_v2": {
            "path": "qa/b006-build/source-snapshot-v2",
            "file_count": 1195,
            "file_bytes": 41205906,
            "path_set_and_all_file_identities_match_manifest": True,
            "source_files": [
                {
                    "path": "qa/b006-build/source-snapshot-v2/" + relative,
                    "bytes": expected[0],
                    "sha256": expected[1],
                }
                for relative, expected in V2_SOURCE_TARGET_IDENTITIES.items()
            ],
        },
        "v2_target_manifest": {
            "path": "qa/R011-B006_TARGET_MANIFEST.tsv",
            "bytes": V2_TARGET_MANIFEST_IDENTITY[0],
            "sha256": V2_TARGET_MANIFEST_IDENTITY[1],
        },
        "final_canonical_outputs": [
            {
                "path": "repo/" + relative,
                "bytes": expected[0],
                "sha256": expected[1],
            }
            for relative, expected in V3_SOURCE_TARGET_IDENTITIES.items()
        ],
        "adverse_ids": list(EXPECTED_V3_LAYOUT_REPAIR_ADVERSE_IDS),
        "exact_substitution_count": len(V3_LAYOUT_REPAIR_OPERATIONS),
        "reverse_operations": operation_results,
        "all_v2_outputs_reconstructed_byte_exact": all(
            reconstructed.get(relative, b"") == v2_raw.get(relative, b"")
            for relative in V2_SOURCE_TARGET_IDENTITIES
        ),
        "layout_only_invariants": invariants,
        "rejected_visual_findings_bound": [
            "R011-B006-V2-001",
            "R011-B006-V2-002",
        ],
    }
    return evidence, v2_raw, v3_raw


def check_v3_rejection_and_v4_layout_repair(
    v3_raw: dict[str, bytes], errors: list[str]
) -> dict[str, object]:
    """Bind rejected v3 and reverse only the authorized v4 edit."""

    for path, expected in V3_REJECTION_IDENTITIES.items():
        exact_identity(path, expected, path.relative_to(LANE).as_posix(), errors)
    build_v3 = read_json(V3_BUILD_RECEIPT, "B006 rejected build v3 receipt", errors)
    visual_v3 = read_json(V3_VISUAL_FINDINGS, "B006 visual findings v3", errors)
    candidate_v3 = read_json(
        V3_CANDIDATE_BUILD_RECEIPT, "B006 candidate build v3 receipt", errors
    )

    expected_pdf = {
        "path": "qa/b006-build/final-v3/main.pdf",
        "pages": 425,
        "bytes": V3_REJECTION_IDENTITIES[V3_CANDIDATE_PDF][0],
        "sha256": V3_REJECTION_IDENTITIES[V3_CANDIDATE_PDF][1],
    }
    expected_visual_identity = {
        "path": "qa/R011-B006_VISUAL_FINDINGS_V3.json",
        "bytes": V3_REJECTION_IDENTITIES[V3_VISUAL_FINDINGS][0],
        "sha256": V3_REJECTION_IDENTITIES[V3_VISUAL_FINDINGS][1],
    }
    require(
        build_v3.get("schema") == "openintro-boundary-build-rejection"
        and build_v3.get("boundary_id") == BOUNDARY_ID
        and build_v3.get("candidate") == "final-v3"
        and build_v3.get("status") == "rejected_visual"
        and build_v3.get("nonvisual_status") == "passed"
        and build_v3.get("candidate_artifact", {}).get("path")
        == expected_pdf["path"]
        and build_v3.get("candidate_artifact", {}).get("pages")
        == expected_pdf["pages"]
        and build_v3.get("candidate_artifact", {}).get("bytes")
        == expected_pdf["bytes"]
        and build_v3.get("candidate_artifact", {}).get("sha256")
        == expected_pdf["sha256"]
        and build_v3.get("candidate_artifact", {}).get(
            "pass_3_pass_4_byte_identical"
        )
        is True
        and build_v3.get("candidate_artifact", {}).get("promoted") is False
        and build_v3.get("visual_findings")
        == {
            **expected_visual_identity,
            "inspection_scope": "all 16 candidate locator pages at 180 dpi",
            "finding_ids": ["R011-B006-V3-001"],
            "severity_counts": {"P0": 0, "P1": 0, "P2": 1, "P3": 0},
        }
        and build_v3.get("source_snapshot")
        == {
            "path": "qa/b006-build/source-snapshot-v3",
            "file_count": 1195,
            "file_bytes": 41205961,
            "path_set_and_all_file_identities_match_manifest": True,
        }
        and build_v3.get("source_receipt")
        == {
            "path": "qa/R011-B006_SOURCE_QA.json",
            "bytes": V3_SOURCE_RECEIPT_IDENTITY[0],
            "sha256": V3_SOURCE_RECEIPT_IDENTITY[1],
        }
        and build_v3.get("target_manifest")
        == {
            "path": "qa/R011-B006_TARGET_MANIFEST.tsv",
            "bytes": V3_TARGET_MANIFEST_IDENTITY[0],
            "sha256": V3_TARGET_MANIFEST_IDENTITY[1],
        }
        and build_v3.get("layout_repair_receipt")
        == identity_path(V3_LAYOUT_REPAIR_RECEIPT)
        and build_v3.get("output_pdf_mutated") is False
        and build_v3.get("pass_audit_created") is False,
        "B006 rejected-build-v3 receipt semantics mismatch",
        errors,
    )

    require(
        visual_v3.get("schema") == "openintro-boundary-visual-findings"
        and visual_v3.get("boundary_id") == BOUNDARY_ID
        and visual_v3.get("candidate") == "final-v3"
        and visual_v3.get("status") == "rejected"
        and visual_v3.get("candidate_pdf") == expected_pdf
        and visual_v3.get("candidate_build_receipt")
        == {
            "path": "qa/b006-build/final-v3/CANDIDATE_BUILD_QA_V3.json",
            "bytes": V3_REJECTION_IDENTITIES[V3_CANDIDATE_BUILD_RECEIPT][0],
            "sha256": V3_REJECTION_IDENTITIES[V3_CANDIDATE_BUILD_RECEIPT][1],
        }
        and visual_v3.get("inspection_resolution_dpi") == 180
        and visual_v3.get("candidate_pages")
        == [61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 388, 389, 390]
        and visual_v3.get("passed_pages")
        == [61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 72, 73, 388, 389, 390]
        and [
            {
                "id": item.get("id"),
                "page": item.get("page"),
                "severity": item.get("severity"),
                "category": item.get("category"),
            }
            for item in visual_v3.get("findings", [])
            if isinstance(item, dict)
        ]
        == [
            {
                "id": "R011-B006-V3-001",
                "page": 71,
                "severity": "P2",
                "category": "exercise_continuation_severe_underfill",
            }
        ]
        and visual_v3.get("severity_counts")
        == {"P0": 0, "P1": 0, "P2": 1, "P3": 0}
        and visual_v3.get("render_manifest") == identity_path(V3_RENDER_MANIFEST)
        and visual_v3.get("page_locator") == identity_path(V3_PAGE_LOCATOR)
        and visual_v3.get("contact_sheet") == identity_path(V3_CONTACT_SHEET)
        and visual_v3.get("pass_audit_created") is False
        and visual_v3.get("promoted") is False
        and visual_v3.get("source_mutated") is False
        and visual_v3.get("output_pdf_mutated") is False,
        "B006 visual-findings-v3 semantics mismatch",
        errors,
    )

    require(
        candidate_v3.get("boundary_id") == BOUNDARY_ID
        and candidate_v3.get("status") == "pending_visual_review"
        and candidate_v3.get("nonvisual_status") == "passed"
        and candidate_v3.get("errors") == []
        and candidate_v3.get("candidate_artifact", {}).get("path")
        == expected_pdf["path"]
        and candidate_v3.get("candidate_artifact", {}).get("bytes")
        == expected_pdf["bytes"]
        and candidate_v3.get("candidate_artifact", {}).get("sha256")
        == expected_pdf["sha256"]
        and candidate_v3.get("determinism", {}).get("byte_identical") is True
        and candidate_v3.get("source_closure", {}).get("source_receipt")
        == build_v3.get("source_receipt")
        and candidate_v3.get("source_closure", {}).get("target_manifest")
        == build_v3.get("target_manifest")
        and candidate_v3.get("source_closure", {}).get("path")
        == "qa/b006-build/source-snapshot-v3"
        and candidate_v3.get("visual_evidence", {}).get("render_manifest")
        == identity_path(V3_RENDER_MANIFEST)
        and candidate_v3.get("visual_evidence", {}).get("page_locator")
        == identity_path(V3_PAGE_LOCATOR)
        and candidate_v3.get("visual_evidence", {}).get("contact_sheet")
        == identity_path(V3_CONTACT_SHEET),
        "B006 candidate-build-v3 receipt semantics mismatch",
        errors,
    )

    final_raw: dict[str, bytes] = {}
    for relative, expected in FINAL_SOURCE_TARGET_IDENTITIES.items():
        final_raw[relative] = exact_identity(
            REPO / relative,
            expected,
            f"final v4-layout B006 source {relative}",
            errors,
        )

    reconstructed = dict(final_raw)
    operation_results: list[dict[str, object]] = []
    for item in reversed(LAYOUT_REPAIR_OPERATIONS):
        operation_id = str(item["id"])
        relative = normalize_repo_path(str(item["path"]))
        before = str(item["before_utf8"]).encode("utf-8")
        after = str(item["after_utf8"]).encode("utf-8")
        expected_occurrences = int(item["expected_occurrences"])
        pre_data = v3_raw.get(relative, b"")
        current = reconstructed.get(relative, b"")
        pre_before_count = pre_data.count(before)
        pre_after_count = pre_data.count(after)
        observed = current.count(after)
        current_before_count = current.count(before)
        require(
            pre_before_count == expected_occurrences and pre_after_count == 0,
            f"{operation_id} pre-v4 fragment occurrence mismatch",
            errors,
        )
        require(
            observed == expected_occurrences and current_before_count == 0,
            f"{operation_id} final-v4 fragment occurrence mismatch",
            errors,
        )
        if observed == expected_occurrences == 1:
            reconstructed[relative] = current.replace(after, before, 1)
        operation_results.append(
            {
                "id": operation_id,
                "adverse_id": item["adverse_id"],
                "path": item["path"],
                "pre_before_occurrences": pre_before_count,
                "pre_after_occurrences": pre_after_count,
                "final_before_occurrences": current_before_count,
                "final_after_occurrences": observed,
                "observed_occurrences_during_reverse": observed,
            }
        )
    operation_results.reverse()

    for relative, expected in V3_SOURCE_TARGET_IDENTITIES.items():
        reconstructed_data = reconstructed.get(relative, b"")
        require(
            (len(reconstructed_data), sha256(reconstructed_data)) == expected
            and reconstructed_data == v3_raw.get(relative, b""),
            f"v4 reverse reconstruction is not source-snapshot-v3 exact: {relative}",
            errors,
        )

    invariants = check_layout_only_invariants(v3_raw, final_raw, errors)
    return {
        "status": "passed",
        "rejected_build_v3_receipt": identity_path(V3_BUILD_RECEIPT),
        "visual_findings_v3_receipt": identity_path(V3_VISUAL_FINDINGS),
        "candidate_build_v3_receipt": identity_path(V3_CANDIDATE_BUILD_RECEIPT),
        "prior_layout_repair_receipt_v3": identity_path(V3_LAYOUT_REPAIR_RECEIPT),
        "source_snapshot_v3": {
            "path": "qa/b006-build/source-snapshot-v3",
            "file_count": 1195,
            "file_bytes": 41205961,
            "path_set_and_all_file_identities_match_manifest": True,
            "source_files": [
                {
                    "path": "qa/b006-build/source-snapshot-v3/" + relative,
                    "bytes": expected[0],
                    "sha256": expected[1],
                }
                for relative, expected in V3_SOURCE_TARGET_IDENTITIES.items()
            ],
        },
        "v3_source_receipt": {
            "path": "qa/R011-B006_SOURCE_QA.json",
            "bytes": V3_SOURCE_RECEIPT_IDENTITY[0],
            "sha256": V3_SOURCE_RECEIPT_IDENTITY[1],
        },
        "v3_target_manifest": {
            "path": "qa/R011-B006_TARGET_MANIFEST.tsv",
            "bytes": V3_TARGET_MANIFEST_IDENTITY[0],
            "sha256": V3_TARGET_MANIFEST_IDENTITY[1],
        },
        "final_canonical_outputs": [
            {
                "path": "repo/" + relative,
                "bytes": expected[0],
                "sha256": expected[1],
            }
            for relative, expected in FINAL_SOURCE_TARGET_IDENTITIES.items()
        ],
        "adverse_ids": list(EXPECTED_LAYOUT_REPAIR_ADVERSE_IDS),
        "exact_substitution_count": len(LAYOUT_REPAIR_OPERATIONS),
        "reverse_operations": operation_results,
        "all_v3_outputs_reconstructed_byte_exact": all(
            reconstructed.get(relative, b"") == v3_raw.get(relative, b"")
            for relative in V3_SOURCE_TARGET_IDENTITIES
        ),
        "layout_only_invariants": invariants,
        "rejected_visual_findings_bound": ["R011-B006-V3-001"],
    }


def include_line_end(data: bytes, position: int) -> int:
    if data[position : position + 2] == b"\r\n":
        return position + 2
    if data[position : position + 1] == b"\n":
        return position + 1
    return position


def split_section_22(
    data: bytes, localized: bool, label: str, errors: list[str]
) -> tuple[bytes, bytes, bytes]:
    end_marker = b"{" + bytes([92]) + b"input{ch_summarizing_data/TeX/considering_categorical_data.tex}}"
    try:
        if localized:
            anchor = data.index(bytes([92]) + b"label{categoricalData}")
            start = data.rfind(bytes([92]) + b"section{", 0, anchor)
            if start < 0:
                raise ValueError("localized section opener not found")
        else:
            start = data.index(
                bytes([92]) + b"section{Considering categorical data}"
            )
        end = data.index(end_marker, start) + len(end_marker)
        end = include_line_end(data, end)
    except ValueError as exc:
        errors.append(f"cannot split {label}: {exc}")
        return b"", b"", b""
    return data[:start], data[start:end], data[end:]


def authority_answer_block(data: bytes, errors: list[str]) -> bytes:
    needle = b"We see the order of the categories and the relative frequencies"
    try:
        inside = data.index(needle)
        start = data.rfind(b"% 21", 0, inside)
        end_needle = b"may be dependent.}"
        end = data.index(end_needle, inside) + len(end_needle)
        end = include_line_end(data, end)
        if start < 0:
            raise ValueError("answer 21 marker not found")
    except ValueError as exc:
        errors.append(f"cannot extract authority answers 2.21/2.23: {exc}")
        return b""
    block = data[start:end]
    require(data.count(block) == 1, "authority answer block is not unique", errors)
    return block


def split_target_answer_block(
    base: bytes, target: bytes, old_block: bytes, errors: list[str]
) -> tuple[bytes, bytes, bytes]:
    if not old_block:
        return b"", b"", b""
    try:
        start = base.index(old_block)
    except ValueError:
        errors.append("B005 solution snapshot lacks authority answer block")
        return b"", b"", b""
    prefix = base[:start]
    suffix = base[start + len(old_block) :]
    require(target.startswith(prefix), "solution bytes changed before answer 2.21", errors)
    require(target.endswith(suffix), "solution bytes changed after answer 2.23", errors)
    if not target.startswith(prefix) or not target.endswith(suffix):
        return prefix, b"", suffix
    middle_end = len(target) - len(suffix) if suffix else len(target)
    return prefix, target[len(prefix) : middle_end], suffix


def balanced_bytes_argument(data: bytes, start: int) -> int | None:
    if start >= len(data) or data[start : start + 1] != b"{":
        return None
    depth = 0
    cursor = start
    while cursor < len(data):
        byte = data[cursor : cursor + 1]
        if byte == b"\\":
            cursor += 2
            continue
        if byte == b"{":
            depth += 1
        elif byte == b"}":
            depth -= 1
            if depth == 0:
                return cursor + 1
        cursor += 1
    return None


def target_answer_block_independent(data: bytes, errors: list[str]) -> bytes:
    """Extract answers 2.21/2.23 without depending on the removed page break."""

    needle = "Diagram batang memperlihatkan urutan kategori".encode("utf-8")
    try:
        inside = data.index(needle)
        start = data.rfind(b"% 21", 0, inside)
        if start < 0:
            raise ValueError("answer 2.21 marker not found")
        macro_21 = data.index(b"\\eocesol{", start, inside + len(needle))
        end_21 = balanced_bytes_argument(data, macro_21 + len(b"\\eocesol"))
        if end_21 is None:
            raise ValueError("answer 2.21 eocesol argument is unbalanced")
        marker_23 = data.index(b"% 23", end_21)
        macro_23 = data.index(b"\\eocesol{", marker_23)
        end_23 = balanced_bytes_argument(data, macro_23 + len(b"\\eocesol"))
        if end_23 is None:
            raise ValueError("answer 2.23 eocesol argument is unbalanced")
        end = include_line_end(data, end_23)
        marker_25 = data.index(b"% 25", end)
    except ValueError as exc:
        errors.append(f"cannot independently extract final answers 2.21/2.23: {exc}")
        return b""
    require(
        data[end:marker_25]
        == b"\n\\end{multicols}\n\\begin{multicols}{2}\n\n",
        "final answer 2.23-to-2.25 boundary differs beyond the authorized page-break removal",
        errors,
    )
    block = data[start:end]
    require(data.count(block) == 1, "final answer block is not unique", errors)
    require(
        block.count(b"\\eocesol{") == 2
        and block.count(b"% 21") == 1
        and block.count(b"% 23") == 1,
        "final answer block does not contain exactly answers 2.21 and 2.23",
        errors,
    )
    return block


def normalize_text(data: bytes, label: str, errors: list[str]) -> str:
    try:
        return data.decode("utf-8").replace("\r\n", "\n")
    except UnicodeDecodeError as exc:
        errors.append(f"{label} is not UTF-8: {exc}")
        return ""


def split_comment(line: str) -> tuple[str, str | None]:
    for index, char in enumerate(line):
        if char != "%":
            continue
        backslashes = 0
        cursor = index - 1
        while cursor >= 0 and line[cursor] == "\\":
            backslashes += 1
            cursor -= 1
        if backslashes % 2 == 0:
            return line[:index], line[index + 1 :]
    return line, None


def strip_comments(text: str) -> str:
    return "\n".join(split_comment(line)[0] for line in text.split("\n"))


def comments(text: str) -> list[str]:
    result: list[str] = []
    for line in text.split("\n"):
        _active, comment = split_comment(line)
        if comment is not None:
            result.append(comment)
    return result


def command_sequence(
    text: str, *, include_comments: bool = False, include_symbols: bool = False
) -> list[str]:
    surface = text if include_comments else strip_comments(text)
    tail = r"[A-Za-z@]+|." if include_symbols else r"[A-Za-z@]+"
    return re.findall(r"\\(" + tail + r")", surface, flags=re.DOTALL)


def environment_sequence(
    text: str, *, include_comments: bool = False
) -> list[tuple[str, str]]:
    surface = text if include_comments else strip_comments(text)
    return re.findall(r"\\(begin|end)\{([^{}]+)\}", surface)


def balanced_argument(text: str, start: int, opener: str, closer: str) -> tuple[str, int] | None:
    if start >= len(text) or text[start] != opener:
        return None
    depth = 0
    cursor = start
    while cursor < len(text):
        char = text[cursor]
        if char == "\\":
            cursor += 2
            continue
        if char == opener:
            depth += 1
        elif char == closer:
            depth -= 1
            if depth == 0:
                return text[start + 1 : cursor], cursor + 1
        cursor += 1
    return None


def macro_calls(
    text: str, names: set[str], *, include_comments: bool = False
) -> list[tuple[str, str]]:
    active = text if include_comments else strip_comments(text)
    pattern = re.compile(r"\\(" + "|".join(sorted(map(re.escape, names), key=len, reverse=True)) + r")\b")
    result: list[tuple[str, str]] = []
    for match in pattern.finditer(active):
        cursor = match.end()
        while cursor < len(active) and active[cursor].isspace():
            cursor += 1
        parsed = balanced_argument(active, cursor, "{", "}")
        if parsed is not None:
            result.append((match.group(1), parsed[0]))
    return result


def math_sequence(text: str, *, include_comments: bool = False) -> list[str]:
    active = text if include_comments else strip_comments(text)
    patterns = (
        r"(?<!\\)\$(?:\\.|[^$])*?(?<!\\)\$",
        r"\\\[(?:.|\n)*?\\\]",
        r"\\\((?:.|\n)*?\\\)",
    )
    spans: list[tuple[int, str]] = []
    for pattern in patterns:
        spans.extend((match.start(), match.group(0)) for match in re.finditer(pattern, active))
    return [value for _position, value in sorted(spans)]


def number_sequence(text: str, *, include_comments: bool = False) -> list[str]:
    surface = text if include_comments else strip_comments(text)
    return re.findall(r"(?<![A-Za-z])\d+(?:[.,]\d+)*(?![A-Za-z])", surface)


def tex_asset_calls(text: str) -> list[dict[str, str]]:
    active = strip_comments(text)
    pattern = re.compile(r"\\(?:Figure|Figures|Figuress)\b")
    result: list[dict[str, str]] = []
    for match in pattern.finditer(active):
        cursor = match.end()
        while cursor < len(active) and active[cursor].isspace():
            cursor += 1
        alternative_text = ""
        if cursor < len(active) and active[cursor] == "[":
            parsed_optional = balanced_argument(active, cursor, "[", "]")
            if parsed_optional is None:
                continue
            alternative_text = parsed_optional[0]
            cursor = parsed_optional[1]
        args: list[str] = []
        while True:
            while cursor < len(active) and active[cursor].isspace():
                cursor += 1
            parsed = balanced_argument(active, cursor, "{", "}")
            if parsed is None:
                break
            args.append(parsed[0])
            cursor = parsed[1]
        if args:
            result.append({"asset_id": args[-1], "alternative_text": alternative_text})
    return result


def tex_asset_sequence(text: str) -> list[str]:
    return [item["asset_id"] for item in tex_asset_calls(text)]


def check_alt_asset_label_mapping(
    calls: list[dict[str, str]], errors: list[str]
) -> dict[str, object]:
    ids = [item["asset_id"] for item in calls]
    require(ids == list(TEX_ASSET_IDS), "alternative-text asset order mismatch", errors)
    mapping: dict[str, object] = {}
    for item in calls:
        asset_id = item["asset_id"]
        alternative = item["alternative_text"]
        required = ALT_REQUIRED_LABELS.get(asset_id, ())
        missing = [label for label in required if label not in alternative]
        forbidden = [
            label
            for label in ALT_FORBIDDEN_ENGLISH_LABELS
            if re.search(r"(?<![A-Za-z])" + re.escape(label) + r"(?![A-Za-z])", alternative)
        ]
        require(not missing, f"{asset_id} alt text lacks localized labels: {missing}", errors)
        require(
            not forbidden,
            f"{asset_id} alt text retains English labels: {forbidden}",
            errors,
        )
        mapping[asset_id] = {
            "required_localized_labels": list(required),
            "missing": missing,
            "forbidden_english_labels_found": forbidden,
        }
    return {
        "status": "passed" if all(
            not value["missing"] and not value["forbidden_english_labels_found"]
            for value in mapping.values()
        ) else "failed",
        "asset_count": len(calls),
        "assets": mapping,
    }


def compare_topology(
    source: str, target: str, label: str, errors: list[str]
) -> dict[str, object]:
    source_commands = command_sequence(
        source, include_comments=True, include_symbols=True
    )
    target_commands = command_sequence(
        target, include_comments=True, include_symbols=True
    )
    require(source_commands == target_commands, f"{label} command order mismatch", errors)
    active_source_commands = command_sequence(source)
    active_target_commands = command_sequence(target)
    require(
        active_source_commands == active_target_commands,
        f"{label} active structural-command order mismatch",
        errors,
    )

    source_env = environment_sequence(source, include_comments=True)
    target_env = environment_sequence(target, include_comments=True)
    require(source_env == target_env, f"{label} environment topology mismatch", errors)
    active_source_env = environment_sequence(source)
    active_target_env = environment_sequence(target)
    require(
        active_source_env == active_target_env,
        f"{label} active environment topology mismatch",
        errors,
    )

    source_calls = macro_calls(source, PROTECTED_CALLS, include_comments=True)
    target_calls = macro_calls(target, PROTECTED_CALLS, include_comments=True)
    require(len(source_calls) == len(target_calls), f"{label} protected-call count mismatch", errors)
    mismatches: list[tuple[int, tuple[str, str], tuple[str, str]]] = []
    for index, pair in enumerate(zip(source_calls, target_calls)):
        if pair[0] != pair[1]:
            mismatches.append((index, pair[0], pair[1]))
    if label == "Section 2.2":
        require(
            len(mismatches) == 1
            and mismatches[0][1] == ("var", "number")
            and mismatches[0][2] == ("var", "homeownership"),
            "Section 2.2 protected literals differ beyond SC-B006-001",
            errors,
        )
    else:
        require(not mismatches, f"{label} protected literals changed", errors)

    label_source = macro_calls(source, {"label"}, include_comments=True)
    label_target = macro_calls(target, {"label"}, include_comments=True)
    ref_names = {"ref", "pageref", "subref"}
    ref_source = macro_calls(source, ref_names, include_comments=True)
    ref_target = macro_calls(target, ref_names, include_comments=True)
    input_source = macro_calls(source, {"input"}, include_comments=True)
    input_target = macro_calls(target, {"input"}, include_comments=True)
    require(label_source == label_target, f"{label} label order mismatch", errors)
    require(ref_source == ref_target, f"{label} reference order mismatch", errors)
    require(input_source == input_target, f"{label} input order mismatch", errors)
    macro_definition_source = [
        command
        for command in command_sequence(source, include_comments=True)
        if command in {"newcommand", "renewcommand"}
    ]
    macro_definition_target = [
        command
        for command in command_sequence(target, include_comments=True)
        if command in {"newcommand", "renewcommand"}
    ]
    require(
        macro_definition_source == macro_definition_target,
        f"{label} macro-definition order mismatch",
        errors,
    )

    source_math = math_sequence(source, include_comments=True)
    target_math = math_sequence(target, include_comments=True)
    require(source_math == target_math, f"{label} math sequence mismatch", errors)
    active_source_math = math_sequence(source)
    active_target_math = math_sequence(target)
    require(
        active_source_math == active_target_math,
        f"{label} active math sequence mismatch",
        errors,
    )

    source_comments = comments(source)
    target_comments = comments(target)
    require(source_comments == target_comments, f"{label} comments/code witness mismatch", errors)

    source_assets = tex_asset_sequence(source)
    target_assets = tex_asset_sequence(target)
    require(source_assets == target_assets, f"{label} TeX asset binding mismatch", errors)

    source_numbers = number_sequence(source, include_comments=True)
    target_numbers = number_sequence(target, include_comments=True)
    require(len(source_numbers) == len(target_numbers), f"{label} numeric-token count mismatch", errors)
    number_mismatches = [
        (index, old, new)
        for index, (old, new) in enumerate(zip(source_numbers, target_numbers))
        if old != new
    ]
    if label == "Section 2.2":
        require(
            [(old, new) for _index, old, new in number_mismatches]
            == [("45,000", "53,000"), ("40,000", "45,000")],
            "Section 2.2 numeric changes differ from SC-B006-003",
            errors,
        )
    else:
        require(not number_mismatches, f"{label} numeric tokens changed", errors)

    return {
        "commands": {"source": len(source_commands), "target": len(target_commands)},
        "active_structural_commands": {
            "source": len(active_source_commands),
            "target": len(active_target_commands),
        },
        "environments": {"source": len(source_env), "target": len(target_env)},
        "active_environments": {
            "source": len(active_source_env),
            "target": len(active_target_env),
        },
        "protected_calls": {"source": len(source_calls), "target": len(target_calls)},
        "labels": {"source": len(label_source), "target": len(label_target)},
        "references": {"source": len(ref_source), "target": len(ref_target)},
        "inputs": {"source": len(input_source), "target": len(input_target)},
        "macro_definitions": {
            "source": len(macro_definition_source),
            "target": len(macro_definition_target),
        },
        "math_tokens": {"source": len(source_math), "target": len(target_math)},
        "active_math_tokens": {
            "source": len(active_source_math),
            "target": len(active_target_math),
        },
        "comments": {"source": len(source_comments), "target": len(target_comments)},
        "asset_bindings": {"source": len(source_assets), "target": len(target_assets)},
        "numeric_tokens": {"source": len(source_numbers), "target": len(target_numbers)},
        "numeric_mismatches": [
            {"position": index, "source": old, "target": new}
            for index, old, new in number_mismatches
        ],
    }


def require_exact_command_removal(
    before: list[str],
    after: list[str],
    removed: list[str],
    label: str,
    errors: list[str],
) -> int | None:
    candidates = [
        index
        for index in range(len(before) - len(removed) + 1)
        if before[index : index + len(removed)] == removed
        and before[:index] + before[index + len(removed) :] == after
    ]
    require(
        len(candidates) == 1,
        f"{label} is not the unique exact authorized command removal",
        errors,
    )
    return candidates[0] if len(candidates) == 1 else None


def compare_repaired_topology(
    before: str,
    final: str,
    label: str,
    removed_commands: list[str],
    errors: list[str],
) -> dict[str, object]:
    """Prove that repairs retain topology except exact layout commands."""

    before_commands = command_sequence(before, include_comments=True, include_symbols=True)
    final_commands = command_sequence(final, include_comments=True, include_symbols=True)
    all_index = require_exact_command_removal(
        before_commands,
        final_commands,
        removed_commands,
        f"{label} all-command sequence",
        errors,
    )
    before_active_commands = command_sequence(before)
    final_active_commands = command_sequence(final)
    active_index = require_exact_command_removal(
        before_active_commands,
        final_active_commands,
        removed_commands,
        f"{label} active-command sequence",
        errors,
    )

    exact_invariants = {
        "environment_topology": (
            environment_sequence(before, include_comments=True),
            environment_sequence(final, include_comments=True),
        ),
        "active_environment_topology": (
            environment_sequence(before),
            environment_sequence(final),
        ),
        "protected_calls": (
            macro_calls(before, PROTECTED_CALLS, include_comments=True),
            macro_calls(final, PROTECTED_CALLS, include_comments=True),
        ),
        "labels": (
            macro_calls(before, {"label"}, include_comments=True),
            macro_calls(final, {"label"}, include_comments=True),
        ),
        "references": (
            macro_calls(before, {"ref", "pageref", "subref"}, include_comments=True),
            macro_calls(final, {"ref", "pageref", "subref"}, include_comments=True),
        ),
        "inputs": (
            macro_calls(before, {"input"}, include_comments=True),
            macro_calls(final, {"input"}, include_comments=True),
        ),
        "math": (
            math_sequence(before, include_comments=True),
            math_sequence(final, include_comments=True),
        ),
        "active_math": (math_sequence(before), math_sequence(final)),
        "comments": (comments(before), comments(final)),
        "asset_bindings": (tex_asset_sequence(before), tex_asset_sequence(final)),
    }
    for name, (old, new) in exact_invariants.items():
        require(old == new, f"{label} repair changed {name}", errors)
    normalized_numeric_before = before.replace(r"\$1000s", r"\$1000")
    before_numbers = number_sequence(normalized_numeric_before, include_comments=True)
    final_numbers = number_sequence(final, include_comments=True)
    require(
        before_numbers == final_numbers,
        f"{label} repair changed numeric values beyond the exact $1000s notation repair",
        errors,
    )
    return {
        "status": "passed",
        "authorized_removed_commands": removed_commands,
        "all_command_removal_index": all_index,
        "active_command_removal_index": active_index,
        "commands_before": len(before_commands),
        "commands_final": len(final_commands),
        "active_commands_before": len(before_active_commands),
        "active_commands_final": len(final_active_commands),
        "exact_invariants": {
            name: len(old) for name, (old, _new) in exact_invariants.items()
        },
        "numeric_tokens_after_unit_notation_normalization": len(before_numbers),
    }


def check_layout_only_invariants(
    before_files: dict[str, bytes],
    final_files: dict[str, bytes],
    errors: list[str],
) -> dict[str, object]:
    """Prove v3 changes no instructional/math/data/asset sequence."""

    reports: dict[str, object] = {}
    for relative in SOURCE_OVERLAYS:
        before = normalize_text(
            before_files.get(relative, b""), f"v2 layout source {relative}", errors
        )
        final = normalize_text(
            final_files.get(relative, b""), f"v3 layout source {relative}", errors
        )
        invariants = {
            "environment_topology": (
                environment_sequence(before, include_comments=True),
                environment_sequence(final, include_comments=True),
            ),
            "active_environment_topology": (
                environment_sequence(before),
                environment_sequence(final),
            ),
            "protected_calls": (
                macro_calls(before, PROTECTED_CALLS, include_comments=True),
                macro_calls(final, PROTECTED_CALLS, include_comments=True),
            ),
            "labels": (
                macro_calls(before, {"label"}, include_comments=True),
                macro_calls(final, {"label"}, include_comments=True),
            ),
            "references": (
                macro_calls(
                    before, {"ref", "pageref", "subref"}, include_comments=True
                ),
                macro_calls(
                    final, {"ref", "pageref", "subref"}, include_comments=True
                ),
            ),
            "inputs": (
                macro_calls(before, {"input"}, include_comments=True),
                macro_calls(final, {"input"}, include_comments=True),
            ),
            "math": (
                math_sequence(before, include_comments=True),
                math_sequence(final, include_comments=True),
            ),
            "active_math": (math_sequence(before), math_sequence(final)),
            "numeric_data": (
                number_sequence(before, include_comments=True),
                number_sequence(final, include_comments=True),
            ),
            "comments": (comments(before), comments(final)),
            "asset_bindings": (
                tex_asset_sequence(before),
                tex_asset_sequence(final),
            ),
        }
        for name, (old, new) in invariants.items():
            require(
                old == new,
                f"v3 layout repair changed {name}: {relative}",
                errors,
            )
        reports[relative] = {
            "status": "passed",
            "sequence_counts": {
                name: len(old) for name, (old, _new) in invariants.items()
            },
        }
    return {
        "status": "passed",
        "files": reports,
        "instructional_content_changed": False,
        "instructional_order_changed": False,
        "math_changed": False,
        "numeric_data_changed": False,
        "asset_bindings_changed": False,
        "reverse_reconstruction_byte_identical_to_source_snapshot_v2": True,
    }


def check_final_display_repairs(
    section: str,
    exercises_file: str,
    answers_file: str,
    errors: list[str],
) -> dict[str, object]:
    visible = strip_comments(section)
    visible = mask_first_arguments(visible, PROTECTED_CALLS)
    visible = re.sub(r"\\[A-Za-z@]+", " ", visible)
    forbidden = (
        "rent",
        "mortgage",
        "own",
        "individual",
        "joint",
        "text",
        "not spam",
        "gain",
        "1000s",
        "mengkondisikan",
    )
    hits: dict[str, int] = {}
    for literal in forbidden:
        count = len(
            re.findall(
                r"(?<![A-Za-z])" + re.escape(literal) + r"(?![A-Za-z])",
                visible,
                flags=re.IGNORECASE,
            )
        )
        if count:
            hits[literal] = count
    require(not hits, f"final repaired reader display retains stale tokens: {hits}", errors)
    required_fragments = {
        "localized_primary_table": "& & sewa & hipotek & milik & Total",
        "localized_email_table": "& teks & HTML & Total",
        "localized_not_spam": "bukan spam & 986 & 2568 & 3554",
        "standard_conditioning_spelling": 'paling berguna bila kita "mengondisikan"',
        "mosaic_direction": (
            "garis pembagi horizontal berada pada ketinggian yang berbeda\n"
            "di setiap kolom"
        ),
        "localized_gain_label": r"kelompok \emph{Bertambah}",
    }
    for name, fragment in required_fragments.items():
        require(fragment in section, f"final repaired display lacks {name}", errors)
    require(
        section.count(r"dalam satuan \$1000") == 2
        and r"\$1000s" not in section,
        "final repaired unit notation is not the exact two-span localization",
        errors,
    )
    require(
        "posisi pembagian vertikal tidak sama pada setiap kolom" not in section
        and r"\D{\newpage}\n\n\subsection{Menggunakan diagram batang" not in section,
        "final repaired Section 2.2 retains a superseded semantic/layout fragment",
        errors,
    )
    require(
        "mungkin saling dependen.}\n\n\\end{multicols}\n\\begin{multicols}{2}\n\n% 25"
        in answers_file
        and "mungkin saling dependen.}\n\n\\end{multicols}\n\\newpage\n\\begin{multicols}{2}\n\n% 25"
        not in answers_file,
        "final public-answer reflow is not the exact authorized boundary",
        errors,
    )
    body_before = str(V3_LAYOUT_REPAIR_OPERATIONS[0]["before_utf8"])
    body_after = str(V3_LAYOUT_REPAIR_OPERATIONS[0]["after_utf8"])
    exercises_before = str(V3_LAYOUT_REPAIR_OPERATIONS[1]["before_utf8"])
    exercises_after = str(V3_LAYOUT_REPAIR_OPERATIONS[1]["after_utf8"])
    chapter3_before = str(V3_LAYOUT_REPAIR_OPERATIONS[2]["before_utf8"])
    chapter3_after = str(V3_LAYOUT_REPAIR_OPERATIONS[2]["after_utf8"])
    exercise_break_before = str(LAYOUT_REPAIR_OPERATIONS[0]["before_utf8"])
    exercise_break_after = str(LAYOUT_REPAIR_OPERATIONS[0]["after_utf8"])
    require(
        section.count(body_after) == 1 and body_before not in section,
        "final county-income figure lacks the exact authorized top placement",
        errors,
    )
    require(
        exercises_file.startswith(exercises_after)
        and exercises_file.count(exercises_after) == 1
        and exercises_before not in exercises_file,
        "final exercise header lacks the exact local clearpage suppression",
        errors,
    )
    require(
        answers_file.count(chapter3_after) == 1
        and chapter3_before not in answers_file,
        "final Chapter 3 answer reflow is not the exact authorized boundary",
        errors,
    )
    require(
        exercises_file.count(exercise_break_after) == 1
        and exercise_break_before not in exercises_file,
        "final Exercise 2.22/2.23 reflow is not the exact authorized boundary",
        errors,
    )
    return {
        "status": "passed",
        "forbidden_reader_visible_token_hits": hits,
        "localized_display_invariants": sorted(required_fragments),
        "localized_unit_span_count": section.count(r"dalam satuan \$1000"),
        "section_forced_break_removed": True,
        "answer_forced_break_removed": True,
        "county_income_figure_top_placement": "[!t]",
        "exercise_header_clearpage_suppression_local_group": True,
        "chapter3_answer_7_forced_break_removed": True,
        "exercise_2_22_to_2_23_forced_break_removed": True,
    }


def mask_first_arguments(text: str, names: set[str]) -> str:
    chars = list(text)
    active = strip_comments(text)
    pattern = re.compile(r"\\(" + "|".join(sorted(map(re.escape, names), key=len, reverse=True)) + r")\b")
    for match in pattern.finditer(active):
        cursor = match.end()
        while cursor < len(active) and active[cursor].isspace():
            cursor += 1
        parsed = balanced_argument(active, cursor, "{", "}")
        if parsed is not None:
            for index in range(cursor, parsed[1]):
                if index < len(chars) and chars[index] != "\n":
                    chars[index] = " "
    return "".join(chars)


def english_hits(text: str) -> list[dict[str, object]]:
    visible = strip_comments(text)
    visible = mask_first_arguments(visible, PROTECTED_CALLS)
    for literal in sorted(PROTECTED_LITERALS, key=len, reverse=True):
        visible = re.sub(re.escape(literal), " ", visible, flags=re.IGNORECASE)
    visible = re.sub(r"(?<!\\)\$(?:\\.|[^$])*?(?<!\\)\$", " ", visible)
    visible = re.sub(r"\\[A-Za-z@]+", " ", visible)
    hits: list[dict[str, object]] = []
    for match in re.finditer(r"[A-Za-z]+(?:'[A-Za-z]+)?", visible):
        if match.group(0).casefold() in FORBIDDEN_ENGLISH_WORDS:
            start = max(0, match.start() - 35)
            end = min(len(visible), match.end() + 35)
            hits.append(
                {
                    "word": match.group(0),
                    "context": re.sub(r"\s+", " ", visible[start:end]).strip(),
                }
            )
    return hits


def check_placeholders(texts: Iterable[str], errors: list[str]) -> None:
    patterns = (
        r"\bTODO\b",
        r"\bTBD\b",
        r"\bPLACEHOLDER\b",
        r"lorem ipsum",
        r"belum diterjemahkan",
        r"\[translate",
    )
    for text in texts:
        active = strip_comments(text)
        for pattern in patterns:
            require(
                re.search(pattern, active, flags=re.IGNORECASE) is None,
                f"active placeholder matched {pattern!r}",
                errors,
            )


def check_corrections(
    source_section: str,
    target_section: str,
    source_exercises: str,
    target_exercises: str,
    source_answers: str,
    target_answers: str,
    errors: list[str],
) -> None:
    require(
        r"\caption{Two bar plots of \var{number}." in source_section
        and r"\caption{Dua diagram batang untuk \var{homeownership}." in target_section,
        "SC-B006-001 exact caption correction missing",
        errors,
    )
    require(
        'blue to represent the "joint" applications' in source_section
        and 'biru untuk "perorangan"' in target_section
        and 'kuning untuk "bersama"' in target_section
        and 'biru untuk "bersama"' not in target_section,
        "SC-B006-002 exact accessibility correction missing",
        errors,
    )
    require(
        "median of about \\$45,000" in source_section
        and "median sekitar \\$53,000" in target_section
        and "median sekitar \\$45,000" in target_section,
        "SC-B006-003 exact median correction missing",
        errors,
    )
    require(
        "Yes, No," in source_answers
        and "kategori Mendukung," in target_answers
        and "Tidak mendukung, dan Tidak yakin" in target_answers,
        "SC-B006-004 answer-category correction missing",
        errors,
    )
    require(
        "Neuromascular" in source_exercises
        and "Neuromuskular" in target_exercises
        and "Neuromascular" not in target_exercises,
        "SC-B006-005 spelling correction missing",
        errors,
    )


def check_o001(exercises: str, answers: str, errors: list[str]) -> dict[str, object]:
    labels = re.findall(r"\\label\{([^{}]+)\}", strip_comments(exercises))
    expected_labels = [
        "antibiotic_use_children",
        "immigration",
        "dream_act_mosaic",
        "raise_taxes_mosaic",
    ]
    require(labels == expected_labels, "B006 exercise labels/order mismatch", errors)
    require(exercises.count(r"\eoce{") == 4, "B006 does not contain four EOCE exercises", errors)
    require(answers.count(r"\eocesol{") == 2, "B006 does not contain two public answers", errors)
    require(
        "% 21" in answers
        and "% 23" in answers
        and "% 22" not in answers
        and "% 24" not in answers,
        "B006 public-answer/O001 partition mismatch",
        errors,
    )
    return {
        "exercise_numbers": list(EXPECTED_EXERCISES),
        "public_answers": list(EXPECTED_PUBLIC_ANSWERS),
        "o001_gaps": list(EXPECTED_O001),
        "restricted_instructor_solutions_accessed_or_invented": False,
    }


def check_control_ledgers(errors: list[str]) -> dict[str, object]:
    for path, expected in CONTROL_IDENTITIES.items():
        exact_identity(path, expected, path.relative_to(LANE).as_posix(), errors)
    adverse_raw = read_bytes(CONTROL / "ADVERSE_LEDGER.jsonl", "adverse ledger", errors)
    terminology_raw = read_bytes(CONTROL / "TERMINOLOGY.csv", "terminology ledger", errors)
    rights_path = CONTROL / "COMPONENT_RIGHTS.csv"
    rights_raw = read_bytes(rights_path, "component-rights ledger", errors)
    correction_rows: dict[str, dict[str, Any]] = {}
    adverse_rows: dict[str, dict[str, Any]] = {}
    adverse_order: list[str] = []
    if adverse_raw:
        try:
            lines = adverse_raw.decode("utf-8").splitlines()
        except UnicodeDecodeError as exc:
            errors.append(f"adverse ledger is not UTF-8: {exc}")
            lines = []
        for number, line in enumerate(lines, 1):
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"adverse ledger row {number} invalid: {exc}")
                continue
            if isinstance(row, dict):
                adverse_id = row.get("id")
                if isinstance(adverse_id, str):
                    require(
                        adverse_id not in adverse_rows,
                        f"duplicate adverse-ledger id: {adverse_id}",
                        errors,
                    )
                    adverse_rows[adverse_id] = row
                    adverse_order.append(adverse_id)
                if row.get("source_correction_id") in EXPECTED_CORRECTIONS:
                    correction_rows[str(row["source_correction_id"])] = row
    require(
        tuple(sorted(correction_rows)) == EXPECTED_CORRECTIONS,
        "adverse ledger lacks exact SC-B006-001..005 set",
        errors,
    )
    for correction_id in EXPECTED_CORRECTIONS:
        row = correction_rows.get(correction_id, {})
        require(
            row.get("status") == "corrected_in_derivative"
            and row.get("authority_commit") == AUTHORITY_COMMIT,
            f"{correction_id} ledger semantics mismatch",
            errors,
        )
    expected_repair_rows = {
        "R011-ADV-0070": (
            "translation_presentation_consistency",
            "medium",
            "ch_summarizing_data/TeX/ch_summarizing_data.tex#categorical_tables",
        ),
        "R011-ADV-0071": (
            "translation_spelling",
            "low",
            "ch_summarizing_data/TeX/ch_summarizing_data.tex#weighingRowColumnProportions",
        ),
        "R011-ADV-0072": (
            "translation_directionality",
            "medium",
            "ch_summarizing_data/TeX/ch_summarizing_data.tex#loan_app_type_home_mosaic_plot",
        ),
        "R011-ADV-0073": (
            "translation_unit_notation",
            "low",
            "ch_summarizing_data/TeX/ch_summarizing_data.tex#countyIncomeSplitByPopGainTable",
        ),
        "R011-ADV-0074": (
            "translation_label_consistency",
            "low",
            "ch_summarizing_data/TeX/ch_summarizing_data.tex#countyIncomeSplitByPopGain-guided-answer",
        ),
        "R011-ADV-0075": (
            "layout_reflow_section_break",
            "medium",
            "ch_summarizing_data/TeX/ch_summarizing_data.tex#bar_plots_subsection",
        ),
        "R011-ADV-0076": (
            "layout_reflow_answer_break",
            "medium",
            "extraTeX/eoceSolutions/eoceSolutions.tex#chapter2_answers_23_to_25",
        ),
        "R011-ADV-0077": (
            "layout_reflow_float_and_exercise_header",
            "medium",
            (
                "ch_summarizing_data/TeX/ch_summarizing_data.tex"
                "#countyIncomeSplitByPopGain;"
                "ch_summarizing_data/TeX/considering_categorical_data.tex"
                "#exercisesheader"
            ),
        ),
        "R011-ADV-0078": (
            "layout_reflow_answer_break",
            "medium",
            "extraTeX/eoceSolutions/eoceSolutions.tex#chapter3_answers_7_to_9",
        ),
        "R011-ADV-0079": (
            "layout_reflow_exercise_break",
            "medium",
            (
                "ch_summarizing_data/TeX/considering_categorical_data.tex"
                "#exercises_2_22_to_2_23"
            ),
        ),
    }
    require(
        adverse_order[-10:] == list(EXPECTED_REPAIR_ADVERSE_IDS),
        "ADV-0070..0079 are not the exact ordered adverse-ledger tail",
        errors,
    )
    for adverse_id, (kind, severity, source) in expected_repair_rows.items():
        row = adverse_rows.get(adverse_id, {})
        require(
            row.get("id") == adverse_id
            and row.get("kind") == kind
            and row.get("severity") == severity
            and row.get("status") == "corrected_in_derivative"
            and row.get("source") == source
            and isinstance(row.get("finding"), str)
            and len(row.get("finding", "")) >= 100,
            f"{adverse_id} repair-ledger semantics mismatch",
            errors,
        )
    terminology_text = terminology_raw.decode("utf-8", errors="replace")
    for source, target in (
        ("contingency table", "tabel kontingensi"),
        ("mosaic plot", "diagram mosaik"),
        ("pie chart", "diagram lingkaran"),
        ("hollow histogram", "histogram berongga"),
    ):
        require(
            source in terminology_text and target in terminology_text,
            f"terminology ledger lacks admitted mapping {source!r}",
            errors,
        )

    rights_rows: dict[str, dict[str, str]] = {}
    if rights_raw:
        try:
            reader = csv.DictReader(rights_raw.decode("utf-8").splitlines())
            require(
                reader.fieldnames
                == [
                    "component_id",
                    "path_or_scope",
                    "role",
                    "license_or_status",
                    "attribution",
                    "publication_disposition",
                    "evidence",
                ],
                "component-rights header mismatch",
                errors,
            )
            rights_rows = {
                str(row.get("component_id")): row
                for row in reader
                if row.get("component_id")
            }
        except UnicodeDecodeError as exc:
            errors.append(f"component-rights ledger is not UTF-8: {exc}")
    generated = rights_rows.get("R011-RIGHTS-B006-GENERATED", {})
    data_row = rights_rows.get("R011-RIGHTS-B006-DATA", {})
    r_package = rights_rows.get("R011-RIGHTS-RPKG", {})
    require(
        "13 repository-authored generated figures" in generated.get("role", "")
        and "eight adjacent R producers" in generated.get("role", "")
        and "frozen English source witnesses" in generated.get("role", "")
        and "CC BY-SA 3.0 Unported" in generated.get("license_or_status", "")
        and "GPL-3 dependency" in generated.get("license_or_status", "")
        and "OpenIntro Statistics source authors" in generated.get("attribution", "")
        and "ASSET_VALIDATION_RECEIPT_R011-B006.json" in generated.get("evidence", ""),
        "R011-RIGHTS-B006-GENERATED semantics mismatch",
        errors,
    )
    require(
        "factual data and build-input closure" == data_row.get("role")
        and "no third-party article or poll-report expression is copied"
        in data_row.get("license_or_status", "")
        and "eoce.bib#survey:immigFL:2012" in data_row.get("evidence", "")
        and "eoce.bib#survey:raiseTaxes:2015" in data_row.get("evidence", ""),
        "R011-RIGHTS-B006-DATA semantics mismatch",
        errors,
    )
    require(
        r_package.get("license_or_status") == "GPL-3",
        "separate OpenIntro R-package GPL-3 dependency row missing",
        errors,
    )
    return {
        "adverse_ledger": {
            **identity_path(CONTROL / "ADVERSE_LEDGER.jsonl"),
            "correction_ids": list(EXPECTED_CORRECTIONS),
            "repair_adverse_ids": list(EXPECTED_REPAIR_ADVERSE_IDS),
            "repair_adverse_rows_exactly_validated": True,
        },
        "terminology": identity_path(CONTROL / "TERMINOLOGY.csv"),
        "component_rights": {
            **identity_path(rights_path),
            "required_rows": [
                "R011-RIGHTS-B006-GENERATED",
                "R011-RIGHTS-B006-DATA",
                "R011-RIGHTS-RPKG",
            ],
        },
    }


def collect_identity_entries(value: object) -> dict[str, tuple[int, str]]:
    entries: dict[str, tuple[int, str]] = {}
    if isinstance(value, dict):
        path = value.get("path")
        size = value.get("bytes")
        digest = value.get("sha256")
        if (
            isinstance(path, str)
            and isinstance(size, int)
            and isinstance(digest, str)
            and re.fullmatch(r"[0-9a-f]{64}", digest)
        ):
            normalized = path.replace("\\", "/")
            entries[normalized] = (size, digest)
        for item in value.values():
            entries.update(collect_identity_entries(item))
    elif isinstance(value, list):
        for item in value:
            entries.update(collect_identity_entries(item))
    return entries


def normalize_repo_path(path: str) -> str:
    normalized = path.replace("\\", "/").lstrip("./")
    if normalized.startswith("repo/"):
        normalized = normalized[5:]
    return normalized


def check_asset_closure(errors: list[str]) -> dict[str, object]:
    for path, expected in ASSET_HANDOFF_IDENTITIES.items():
        exact_identity(path, expected, path.relative_to(LANE).as_posix(), errors)
    manifest = read_json(ASSET_MANIFEST, "B006 asset manifest", errors)
    receipt = read_json(ASSET_RECEIPT, "B006 asset validation receipt", errors)
    localizer_raw = read_bytes(ASSET_LOCALIZER, "B006 asset localizer", errors)
    if not manifest or not receipt or not localizer_raw:
        return {}

    require(
        not recursively_contains_placeholder(manifest)
        and not recursively_contains_placeholder(receipt),
        "B006 asset evidence contains a placeholder",
        errors,
    )
    require(
        not recursively_bad_state(manifest) and not recursively_bad_state(receipt),
        "B006 asset evidence contains a fail/pending/blocked state",
        errors,
    )
    require(
        manifest.get("boundary_id") == BOUNDARY_ID
        and receipt.get("boundary_id") == BOUNDARY_ID,
        "B006 asset boundary id mismatch",
        errors,
    )
    require(
        manifest.get("status") == "pass"
        and manifest.get("authority", {}).get("commit") == AUTHORITY_COMMIT
        and manifest.get("authority", {}).get("tree") == AUTHORITY_TREE,
        "B006 asset manifest authority/status mismatch",
        errors,
    )
    scope = manifest.get("scope", {})
    require(
        scope.get("source_pdf_count") == 13
        and scope.get("localized_pdf_count") == 13
        and scope.get("adjacent_r_producer_count") == 8
        and scope.get("reader_visible_english_source_count") == 13
        and scope.get("numeric_or_symbol_only_source_count") == 0,
        "B006 asset-manifest scope counts mismatch",
        errors,
    )
    policy = manifest.get("localization_policy", {})
    require(
        "immutable source literals" in policy.get("dataset_literals", "")
        and "do not mutate data values, counts, category order, or geometry"
        in policy.get("reader_labels", "")
        and "numbers, currency ticks, colors, shapes, paths, panel order"
        in policy.get("unchanged_nonlinguistic_content", ""),
        "B006 asset localization policy mismatch",
        errors,
    )
    production = manifest.get("production", {})
    localizer_identity = identity_path(ASSET_LOCALIZER)
    require(
        production.get("script")
        == {
            "path": localizer_identity["path"],
            "bytes": localizer_identity["bytes"],
            "sha256": localizer_identity["sha256"],
        }
        and production.get("deterministic_replays") == 2
        and production.get("replay_identity_count") == 13,
        "B006 asset producer/replay contract mismatch",
        errors,
    )

    rights = manifest.get("component_rights", {})
    live_rights = identity_path(CONTROL / "COMPONENT_RIGHTS.csv")
    require(
        rights.get("path") == live_rights["path"]
        and rights.get("observed_file_bytes") == live_rights["bytes"]
        and rights.get("observed_file_sha256") == live_rights["sha256"]
        and rights.get("generated_row", {}).get("component_id")
        == "R011-RIGHTS-B006-GENERATED"
        and rights.get("generated_row", {}).get("normalized_csv_row_sha256")
        == "7494beeda0089a905fb31a4989de5319c865e23dd0a6f3a879dae34c5de0fa36"
        and rights.get("data_dependency_row", {}).get("component_id")
        == "R011-RIGHTS-B006-DATA"
        and rights.get("data_dependency_row", {}).get("normalized_csv_row_sha256")
        == "612b9a943b4c7031d70c43ecf38d2ac97490461235d5a9eabb9bec26112e93c9"
        and rights.get("repository_expression") == "CC BY-SA 3.0 Unported",
        "asset manifest does not bind exact component-rights control",
        errors,
    )
    require(
        str(receipt.get("status", receipt.get("result", ""))).casefold()
        in {"pass", "passed"},
        "B006 asset receipt is not passed",
        errors,
    )
    require(
        receipt.get("authority", {}).get("commit") == AUTHORITY_COMMIT
        and receipt.get("authority", {}).get("tree") == AUTHORITY_TREE
        and receipt.get("errors") == []
        and receipt.get("blockers") == []
        and receipt.get("asset_subgate_admission_ready") is True,
        "B006 asset receipt authority/readiness mismatch",
        errors,
    )
    receipt_counts = receipt.get("counts", {})
    require(
        receipt_counts.get("assets") == 13
        and receipt_counts.get("source_witnesses") == 13
        and receipt_counts.get("adjacent_r_producers") == 8
        and receipt_counts.get("localized_text_spans") == 80
        and receipt_counts.get("deterministic_replays") == 2
        and receipt_counts.get("replay_identical_assets") == 13,
        "B006 asset receipt counts mismatch",
        errors,
    )
    receipt_checks = receipt.get("checks", [])
    require(
        isinstance(receipt_checks, list)
        and [item.get("id") for item in receipt_checks if isinstance(item, dict)]
        == [f"B006-ASSET-{number:03d}" for number in range(1, 15)]
        and all(
            item.get("status") == "pass"
            for item in receipt_checks
            if isinstance(item, dict)
        ),
        "B006 asset receipt does not contain 14 ordered PASS checks",
        errors,
    )

    combined_entries = collect_identity_entries(manifest)
    combined_entries.update(collect_identity_entries(receipt))
    normalized_entries = {
        normalize_repo_path(path): identity for path, identity in combined_entries.items()
    }

    for relative in ASSET_PDFS + ASSET_SOURCE_WITNESSES + ASSET_PRODUCERS:
        path = REPO / relative
        raw = read_bytes(path, f"B006 asset {relative}", errors)
        if not raw:
            continue
        require(
            normalized_entries.get(relative) == (len(raw), sha256(raw)),
            f"asset evidence does not bind live identity: {relative}",
            errors,
        )

    asset_rows = manifest.get("assets", [])
    require(
        isinstance(asset_rows, list)
        and [item.get("id") for item in asset_rows if isinstance(item, dict)]
        == list(TEX_ASSET_IDS),
        "asset manifest IDs/order mismatch",
        errors,
    )
    for index, asset_id in enumerate(TEX_ASSET_IDS):
        if not isinstance(asset_rows, list) or index >= len(asset_rows) or not isinstance(asset_rows[index], dict):
            continue
        row = asset_rows[index]
        target_relative = ASSET_PDFS[index]
        source_relative = ASSET_SOURCE_WITNESSES[index]
        require(
            normalize_repo_path(str(row.get("target", {}).get("path", "")))
            == target_relative
            and normalize_repo_path(str(row.get("source", {}).get("path", "")))
            == source_relative
            and normalize_repo_path(str(row.get("producer", "")))
            in ASSET_PRODUCERS,
            f"asset {asset_id} source/target/producer binding mismatch",
            errors,
        )
        require(
            isinstance(row.get("page_box_points"), list)
            and len(row.get("page_box_points", [])) == 4
            and isinstance(row.get("vector_drawing_count"), int)
            and row.get("vector_drawing_count", 0) > 0
            and re.fullmatch(r"[0-9a-f]{64}", str(row.get("vector_drawing_semantic_sha256", "")))
            is not None
            and isinstance(row.get("numeric_tokens"), list)
            and isinstance(row.get("localized_span_count"), int)
            and row.get("localized_span_count", 0) > 0,
            f"asset {asset_id} semantic replay fields incomplete",
            errors,
        )

    manifest_identity = identity_path(ASSET_MANIFEST)
    receipt_entries = collect_identity_entries(receipt)
    expected_manifest_identity = (
        int(manifest_identity["bytes"]),
        str(manifest_identity["sha256"]),
    )
    require(
        any(
            path.replace("\\", "/").endswith("qa/b006-assets/ASSET_MANIFEST_R011-B006.json")
            and identity == expected_manifest_identity
            for path, identity in receipt_entries.items()
        ),
        "asset receipt does not bind the asset manifest identity",
        errors,
    )

    for target_relative, source_relative in zip(ASSET_PDFS, ASSET_SOURCE_WITNESSES):
        base = read_bytes(BASE_SNAPSHOT / target_relative, f"B005 base asset {target_relative}", errors)
        source = read_bytes(REPO / source_relative, f"source witness {source_relative}", errors)
        target = read_bytes(REPO / target_relative, f"localized asset {target_relative}", errors)
        if base and source and target:
            require(
                base == source,
                f"source witness is not the exact B005 English asset: {source_relative}",
                errors,
            )
            require(
                source != target,
                f"localized PDF is byte-identical to its English witness: {target_relative}",
                errors,
            )
            require(
                source.startswith(b"%PDF-") and target.startswith(b"%PDF-"),
                f"asset is not a PDF: {target_relative}",
                errors,
            )

    require(
        len(ASSET_PDFS) == 13 and len(ASSET_PRODUCERS) == 8,
        "internal B006 asset inventory count mismatch",
        errors,
    )
    return {
        "status": "passed",
        "localized_pdf_count": 13,
        "producer_count": 8,
        "manifest": manifest_identity,
        "validation_receipt": identity_path(ASSET_RECEIPT),
        "localizer": localizer_identity,
        "pdf_paths": list(ASSET_PDFS),
        "source_witness_paths": list(ASSET_SOURCE_WITNESSES),
        "producer_paths": list(ASSET_PRODUCERS),
    }


def assemble_target_manifest(
    base_rows: dict[str, tuple[int, str]], errors: list[str]
) -> tuple[bytes, dict[str, object]]:
    # This is a deliberately bounded inventory of the 41 MB corpus repo, not a
    # Git/workspace scan.  It proves that no stray live file is silently omitted
    # from the frozen build closure.
    target: dict[str, tuple[int, str]] = {}
    try:
        paths = sorted(
            (path for path in REPO.rglob("*") if path.is_file()),
            key=lambda path: path.relative_to(REPO).as_posix(),
        )
    except OSError as exc:
        errors.append(f"cannot enumerate bounded corpus repo: {exc}")
        paths = []
    for path in paths:
        relative = path.relative_to(REPO).as_posix()
        if path.is_symlink():
            errors.append(f"repo closure contains symlink: {relative}")
            continue
        try:
            require(
                path.resolve().is_relative_to(REPO.resolve()),
                f"repo closure path escapes bounded root: {relative}",
                errors,
            )
        except OSError as exc:
            errors.append(f"cannot resolve repo closure path {relative}: {exc}")
            continue
        raw = read_bytes(path, f"repo closure {relative}", errors)
        target[relative] = (len(raw), sha256(raw))

    raw_manifest = render_manifest(target)
    base_paths = set(base_rows)
    target_paths = set(target)
    common = base_paths & target_paths
    changed = [path for path in sorted(common) if base_rows[path] != target[path]]
    added = sorted(target_paths - base_paths)
    removed = sorted(base_paths - target_paths)
    require(
        set(changed).issubset(set(EXISTING_OVERLAY_CANDIDATES)),
        "target manifest contains an undeclared B006 delta",
        errors,
    )
    unexpected_added = sorted(set(added) - set(ADDED_OVERLAYS))
    missing_added = sorted(set(ADDED_OVERLAYS) - set(added))
    require(
        not unexpected_added and not missing_added,
        "B006 added-path set mismatch: "
        f"unexpected_count={len(unexpected_added)}, "
        f"unexpected_sample={unexpected_added[:12]}, missing={missing_added}",
        errors,
    )
    require(not removed, f"B006 removed unexpected base paths: {removed}", errors)
    require(
        set(SOURCE_OVERLAYS).issubset(changed),
        "one or more canonical B006 source overlays did not change",
        errors,
    )
    require(
        set(ASSET_PDFS).issubset(changed),
        "one or more localized B006 PDFs did not change",
        errors,
    )
    require(
        changed == list(EXPECTED_CHANGED_PATHS),
        f"B006 changed-path set is not the exact 16-file closure: {changed}",
        errors,
    )
    unchanged_outside_overlay = common - set(EXISTING_OVERLAY_CANDIDATES)
    require(
        all(base_rows[path] == target[path] for path in unchanged_outside_overlay),
        "one or more non-overlay repo files differ from admitted B005",
        errors,
    )
    added_bytes = sum(target[path][0] for path in added)
    changed_before_bytes = sum(base_rows[path][0] for path in changed)
    changed_after_bytes = sum(target[path][0] for path in changed)
    require(
        len(target) == EXPECTED_TARGET_FILE_COUNT
        and sum(size for size, _digest in target.values())
        == EXPECTED_TARGET_FILE_BYTES
        and len(added) == 13
        and added_bytes == EXPECTED_ADDED_FILE_BYTES,
        "B006 actual repo inventory count/byte totals mismatch",
        errors,
    )
    delta = {
        "base_file_count": len(base_rows),
        "base_file_bytes": sum(size for size, _digest in base_rows.values()),
        "target_file_count": len(target),
        "target_file_bytes": sum(size for size, _digest in target.values()),
        "changed_file_count": len(changed),
        "changed_paths": changed,
        "changed_file_bytes_before": changed_before_bytes,
        "changed_file_bytes_after": changed_after_bytes,
        "changed_file_net_bytes": changed_after_bytes - changed_before_bytes,
        "added_file_count": len(added),
        "added_file_bytes": added_bytes,
        "added_paths": added,
        "removed_file_count": len(removed),
        "removed_paths": removed,
        "unchanged_file_count": len(common) - len(changed),
        "net_file_bytes": sum(size for size, _digest in target.values())
        - sum(size for size, _digest in base_rows.values()),
        "actual_repo_inventory_replayed": True,
    }
    return raw_manifest, delta


def check_v2_manifest_reconstruction(
    current_manifest_raw: bytes, errors: list[str]
) -> dict[str, object]:
    """Reverse the current source identities to the exact full v2 manifest."""

    current_rows = parse_manifest(current_manifest_raw, "candidate v4 manifest", errors)
    v2_rows = dict(current_rows)
    for relative, final_expected in FINAL_SOURCE_TARGET_IDENTITIES.items():
        require(
            current_rows.get(relative) == final_expected,
            f"candidate v4 manifest source identity mismatch: {relative}",
            errors,
        )
        v2_rows[relative] = V2_SOURCE_TARGET_IDENTITIES[relative]
    v2_raw = render_manifest(v2_rows)
    require(
        (len(v2_raw), sha256(v2_raw)) == V2_TARGET_MANIFEST_IDENTITY,
        "reverse-reconstructed v2 target manifest identity mismatch",
        errors,
    )
    require(
        len(v2_rows) == 1195
        and sum(size for size, _digest in v2_rows.values()) == 41205906,
        "reverse-reconstructed v2 target manifest count/byte mismatch",
        errors,
    )
    return {
        "status": "passed",
        "algorithm": (
            "Replace only the three v3 source-overlay rows with their exact "
            "source-snapshot-v2 identities; keep every path and all other rows "
            "byte-identical, sort canonically, and hash."
        ),
        "path": "qa/R011-B006_TARGET_MANIFEST.tsv",
        **identity_bytes(v2_raw),
        "file_count": len(v2_rows),
        "file_bytes": sum(size for size, _digest in v2_rows.values()),
        "replaced_paths": list(SOURCE_OVERLAYS),
        "matches_rejected_v2_manifest_identity": True,
    }


def check_v3_manifest_reconstruction(
    current_manifest_raw: bytes, errors: list[str]
) -> dict[str, object]:
    """Reverse only the v4 source row to the exact full v3 manifest."""

    current_rows = parse_manifest(current_manifest_raw, "candidate v4 manifest", errors)
    v3_rows = dict(current_rows)
    for relative, final_expected in FINAL_SOURCE_TARGET_IDENTITIES.items():
        require(
            current_rows.get(relative) == final_expected,
            f"candidate v4 manifest source identity mismatch: {relative}",
            errors,
        )
        v3_rows[relative] = V3_SOURCE_TARGET_IDENTITIES[relative]
    v3_raw = render_manifest(v3_rows)
    require(
        (len(v3_raw), sha256(v3_raw)) == V3_TARGET_MANIFEST_IDENTITY,
        "reverse-reconstructed v3 target manifest identity mismatch",
        errors,
    )
    require(
        len(v3_rows) == 1195
        and sum(size for size, _digest in v3_rows.values()) == 41205961,
        "reverse-reconstructed v3 target manifest count/byte mismatch",
        errors,
    )
    return {
        "status": "passed",
        "algorithm": (
            "Replace only the v4 exercise-overlay row with its exact "
            "source-snapshot-v3 identity; require the other source rows already "
            "equal v3, keep every path and all other rows byte-identical, sort "
            "canonically, and hash."
        ),
        "path": "qa/R011-B006_TARGET_MANIFEST.tsv",
        **identity_bytes(v3_raw),
        "file_count": len(v3_rows),
        "file_bytes": sum(size for size, _digest in v3_rows.values()),
        "replaced_paths": [EXERCISES],
        "matches_rejected_v3_manifest_identity": True,
    }


def validate_source(
    authority: dict[str, bytes],
    reconstructed_pre_repair: dict[str, bytes],
    reconstructed_v2: dict[str, bytes],
    reconstructed_v3: dict[str, bytes],
    errors: list[str],
) -> tuple[dict[str, object], dict[str, str]]:
    base_body = read_bytes(BASE_SNAPSHOT / BODY, "B005 body snapshot", errors)
    target_body = read_bytes(REPO / BODY, "B006 body", errors)
    pre_repair_body = reconstructed_pre_repair.get(BODY, b"")
    v2_body = reconstructed_v2.get(BODY, b"")
    v3_body = reconstructed_v3.get(BODY, b"")
    auth_body = authority.get(BODY, b"")
    base_prefix, base_section, base_suffix = split_section_22(
        base_body, False, "B005 Section 2.2", errors
    )
    auth_prefix, auth_section, auth_suffix = split_section_22(
        auth_body, False, "authority Section 2.2", errors
    )
    pre_repair_prefix, pre_repair_section, pre_repair_suffix = split_section_22(
        pre_repair_body, True, "pre-repair B006 Section 2.2", errors
    )
    v2_prefix, v2_section, v2_suffix = split_section_22(
        v2_body, True, "v2 B006 Section 2.2", errors
    )
    v3_prefix, v3_section, v3_suffix = split_section_22(
        v3_body, True, "v3 B006 Section 2.2", errors
    )
    target_prefix, target_section, target_suffix = split_section_22(
        target_body, True, "B006 Section 2.2", errors
    )
    require(base_section == auth_section, "B005 Section 2.2 is not authority-identical", errors)
    require(
        base_prefix == pre_repair_prefix == v2_prefix == v3_prefix == target_prefix,
        "bytes before Section 2.2 changed",
        errors,
    )
    require(
        base_suffix == pre_repair_suffix == v2_suffix == v3_suffix == target_suffix,
        "Section 2.3+ authority suffix changed",
        errors,
    )
    require(
        auth_section == auth_body[len(auth_prefix) : len(auth_body) - len(auth_suffix)],
        "authority Section 2.2 reconstruction failed",
        errors,
    )

    auth_exercises_raw = authority.get(EXERCISES, b"")
    target_exercises_raw = read_bytes(REPO / EXERCISES, "B006 exercises", errors)
    v2_exercises_raw = reconstructed_v2.get(EXERCISES, b"")
    v3_exercises_raw = reconstructed_v3.get(EXERCISES, b"")
    base_exercises_raw = read_bytes(BASE_SNAPSHOT / EXERCISES, "B005 exercises", errors)
    require(
        base_exercises_raw == auth_exercises_raw,
        "B005 Section 2.2 exercises are not authority-identical",
        errors,
    )

    auth_solutions = authority.get(SOLUTIONS, b"")
    base_solutions = read_bytes(BASE_SNAPSHOT / SOLUTIONS, "B005 public answers", errors)
    target_solutions = read_bytes(REPO / SOLUTIONS, "B006 public answers", errors)
    pre_repair_solutions = reconstructed_pre_repair.get(SOLUTIONS, b"")
    v2_solutions = reconstructed_v2.get(SOLUTIONS, b"")
    v3_solutions = reconstructed_v3.get(SOLUTIONS, b"")
    old_answer_block = authority_answer_block(auth_solutions, errors)
    _answer_prefix, pre_repair_answers_raw, _answer_suffix = split_target_answer_block(
        base_solutions, pre_repair_solutions, old_answer_block, errors
    )
    target_answers_raw = target_answer_block_independent(target_solutions, errors)
    require(
        target_answers_raw == pre_repair_answers_raw,
        "public-answer instructional bytes changed during the layout repair",
        errors,
    )

    auth_section_text = normalize_text(auth_section, "authority Section 2.2", errors)
    target_section_text = normalize_text(target_section, "B006 Section 2.2", errors)
    auth_exercises_text = normalize_text(auth_exercises_raw, "authority exercises", errors)
    target_exercises_text = normalize_text(target_exercises_raw, "B006 exercises", errors)
    auth_answers_text = normalize_text(old_answer_block, "authority answers", errors)
    target_answers_text = normalize_text(target_answers_raw, "B006 answers", errors)
    pre_repair_section_text = normalize_text(
        pre_repair_section, "pre-repair B006 Section 2.2", errors
    )
    v2_section_text = normalize_text(v2_section, "v2 B006 Section 2.2", errors)
    v3_section_text = normalize_text(v3_section, "v3 B006 Section 2.2", errors)
    v2_exercises_text = normalize_text(v2_exercises_raw, "v2 B006 exercises", errors)
    v3_exercises_text = normalize_text(v3_exercises_raw, "v3 B006 exercises", errors)
    pre_repair_solutions_text = normalize_text(
        pre_repair_solutions, "pre-repair B006 answer file", errors
    )
    v2_solutions_text = normalize_text(v2_solutions, "v2 B006 answer file", errors)
    v3_solutions_text = normalize_text(v3_solutions, "v3 B006 answer file", errors)
    target_solutions_text = normalize_text(target_solutions, "final B006 answer file", errors)

    topologies = {
        "section_2_2": compare_topology(
            auth_section_text, pre_repair_section_text, "Section 2.2", errors
        ),
        "exercises_2_21_2_24": compare_topology(
            auth_exercises_text, v2_exercises_text, "Exercises 2.21-2.24", errors
        ),
        "public_answers_2_21_2_23": compare_topology(
            auth_answers_text, target_answers_text, "Public answers 2.21/2.23", errors
        ),
    }
    repaired_topology = {
        "section_2_2": compare_repaired_topology(
            pre_repair_section_text,
            v2_section_text,
            "Section 2.2 post-build repair",
            ["D", "newpage"],
            errors,
        ),
        "public_answer_file": compare_repaired_topology(
            pre_repair_solutions_text,
            v2_solutions_text,
            "public-answer-file post-build repair",
            ["newpage"],
            errors,
        ),
    }

    check_corrections(
        auth_section_text,
        target_section_text,
        auth_exercises_text,
        target_exercises_text,
        auth_answers_text,
        target_answers_text,
        errors,
    )
    o001 = check_o001(target_exercises_text, target_answers_text, errors)
    check_placeholders(
        (target_section_text, target_exercises_text, target_answers_text), errors
    )
    final_display = check_final_display_repairs(
        target_section_text, target_exercises_text, target_solutions_text, errors
    )
    english = {
        "section_2_2": english_hits(target_section_text),
        "exercises_2_21_2_24": english_hits(target_exercises_text),
        "public_answers_2_21_2_23": english_hits(target_answers_text),
    }
    require(
        not any(english.values()),
        "active reader-visible English detected outside protected literals: "
        + json.dumps(english, ensure_ascii=False, sort_keys=True),
        errors,
    )

    combined_asset_calls = tex_asset_calls(target_section_text) + tex_asset_calls(
        target_exercises_text
    )
    combined_asset_ids = [item["asset_id"] for item in combined_asset_calls]
    require(
        combined_asset_ids == list(TEX_ASSET_IDS),
        "B006 TeX asset IDs/order are not the exact 13-item closure",
        errors,
    )
    alt_label_mapping = check_alt_asset_label_mapping(combined_asset_calls, errors)

    source_scope = {
        "body": identity_path(REPO / BODY),
        "translated_section_2_2": identity_bytes(target_section),
        "authority_section_2_2": identity_bytes(auth_section),
        "pre_repair_translated_section_2_2": identity_bytes(pre_repair_section),
        "v2_translated_section_2_2": identity_bytes(v2_section),
        "v3_translated_section_2_2": identity_bytes(v3_section),
        "unchanged_prefix": identity_bytes(base_prefix),
        "unchanged_section_2_3_plus_suffix": identity_bytes(base_suffix),
        "exercises": identity_path(REPO / EXERCISES),
        "public_answer_file": identity_path(REPO / SOLUTIONS),
        "translated_public_answer_slice": identity_bytes(target_answers_raw),
        "authority_public_answer_slice": identity_bytes(old_answer_block),
        "topology": topologies,
        "post_build_repair_topology": repaired_topology,
        "v3_layout_repair_invariants": check_layout_only_invariants(
            reconstructed_v2,
            reconstructed_v3,
            errors,
        ),
        "v4_layout_repair_invariants": check_layout_only_invariants(
            reconstructed_v3,
            {
                BODY: target_body,
                EXERCISES: target_exercises_raw,
                SOLUTIONS: target_solutions,
            },
            errors,
        ),
        "post_build_repair_display": final_display,
        "correction_ids": list(EXPECTED_CORRECTIONS),
        "o001": o001,
        "active_reader_visible_english": english,
        "active_reader_visible_english_count": sum(map(len, english.values())),
        "tex_asset_ids": combined_asset_ids,
        "asset_label_alt_text_mapping": alt_label_mapping,
    }
    target_texts = {
        "section": target_section_text,
        "exercises": target_exercises_text,
        "answers": target_answers_text,
    }
    return source_scope, target_texts


def construct_layout_repair_receipt(
    manifest_raw: bytes,
    layout_evidence: dict[str, object],
    v3_manifest_reconstruction: dict[str, object],
) -> bytes:
    script_raw = Path(__file__).read_bytes()
    return canonical_json(
        {
            "schema": "openintro-b006-layout-repair-receipt",
            "schema_version": "r011-b006-layout-repair-receipt-v4/1.0.0",
            "boundary_id": BOUNDARY_ID,
            "status": "layout_repairs_applied_and_reverse_verified",
            "boundary_admitted": False,
            "authority": {
                "repository": AUTHORITY_REPOSITORY,
                "commit": AUTHORITY_COMMIT,
                "tree": AUTHORITY_TREE,
            },
            "pre_repair_evidence": {
                "prior_layout_repair_receipt_v3": identity_path(
                    V3_LAYOUT_REPAIR_RECEIPT
                ),
                "rejected_build_v3_receipt": identity_path(V3_BUILD_RECEIPT),
                "visual_findings_v3_receipt": identity_path(V3_VISUAL_FINDINGS),
                "candidate_build_v3_receipt": identity_path(
                    V3_CANDIDATE_BUILD_RECEIPT
                ),
                "source_snapshot_v3": layout_evidence["source_snapshot_v3"],
                "source_receipt_v3": layout_evidence["v3_source_receipt"],
                "target_manifest_v3": layout_evidence["v3_target_manifest"],
                "target_manifest_v3_reverse_reconstruction": (
                    v3_manifest_reconstruction
                ),
            },
            "final_canonical_outputs": layout_evidence[
                "final_canonical_outputs"
            ],
            "post_repair_target_manifest": {
                "path": "qa/R011-B006_TARGET_MANIFEST.tsv",
                **identity_bytes(manifest_raw),
            },
            "final_control": {
                **identity_path(CONTROL / "ADVERSE_LEDGER.jsonl"),
                "adverse_ids": list(EXPECTED_LAYOUT_REPAIR_ADVERSE_IDS),
                "validated_tail": list(EXPECTED_REPAIR_ADVERSE_IDS),
            },
            "layout_repairs": {
                "adverse_ids": list(EXPECTED_LAYOUT_REPAIR_ADVERSE_IDS),
                "repair_group_count": len(EXPECTED_LAYOUT_REPAIR_ADVERSE_IDS),
                "substitution_count": len(LAYOUT_REPAIR_OPERATIONS),
                "exact_substitutions": [dict(item) for item in LAYOUT_REPAIR_OPERATIONS],
                "instructional_content_changed": False,
                "instructional_order_changed": False,
                "math_changed": False,
                "numeric_data_changed": False,
                "asset_bytes_or_bindings_changed": False,
            },
            "reverse_reconstruction": {
                "algorithm": (
                    "Starting from each final canonical source, process the exact "
                    "substitutions in reverse listed order; require one after_utf8 "
                    "occurrence and zero before_utf8 occurrences, replace after_utf8 "
                    "with before_utf8 once, then require byte identity with the "
                    "corresponding source-snapshot-v3 file."
                ),
                "operations": layout_evidence["reverse_operations"],
                "outputs": [
                    {
                        "path": "qa/b006-build/source-snapshot-v3/" + relative,
                        "bytes": expected[0],
                        "sha256": expected[1],
                    }
                    for relative, expected in V3_SOURCE_TARGET_IDENTITIES.items()
                ],
                "all_outputs_match_source_snapshot_v3_identities": True,
            },
            "layout_only_invariants": layout_evidence["layout_only_invariants"],
            "visual_candidate_v3": {
                "status": "rejected_visual",
                "promoted": False,
                "candidate_pdf": {
                    "path": "qa/b006-build/final-v3/main.pdf",
                    "pages": 425,
                    "bytes": 21976293,
                    "sha256": (
                        "7fb77cd62425d4237f35e24791d1206f6eec704fc40b50d4a7159953f2647cab"
                    ),
                },
                "findings": [
                    {
                        "id": "R011-B006-V3-001",
                        "adverse_id": "R011-ADV-0079",
                        "repair_ids": ["R011-B006-LYT-V4-001"],
                        "page": 71,
                        "severity": "P2",
                        "category": "exercise_continuation_severe_underfill",
                    },
                ],
            },
            "checks": {
                "prior_v1_v2_v3_rejection_chain_bound": "passed",
                "v3_rejection_bound": "passed",
                "source_snapshot_v3_files_exact": "passed",
                "target_manifest_v3_reverse_reconstructed": "passed",
                "one_exact_layout_substitution": "passed",
                "reverse_reconstruction_byte_exact": "passed",
                "instructional_content_order_math_data_assets_unchanged": "passed",
                "ADV_0079": "passed",
            },
            "gate_script": {
                "path": Path(__file__).relative_to(LANE).as_posix(),
                **identity_bytes(script_raw),
            },
            "write_boundary": (
                "qa/R011-B006_LAYOUT_REPAIR_RECEIPT_V4.json, "
                "qa/R011-B006_TARGET_MANIFEST.tsv, and "
                "qa/R011-B006_SOURCE_QA.json only"
            ),
        }
    )


def construct_receipt(
    manifest_raw: bytes,
    layout_receipt_raw: bytes,
    delta: dict[str, object],
    source_scope: dict[str, object],
    controls: dict[str, object],
    assets: dict[str, object],
) -> bytes:
    script_raw = Path(__file__).read_bytes()
    return canonical_json(
        {
            "schema": "openintro-id-source-boundary-qa",
            "schema_version": "0.9.0",
            "boundary_id": BOUNDARY_ID,
            "status": "passed",
            "authority": {
                "repository": AUTHORITY_REPOSITORY,
                "commit": AUTHORITY_COMMIT,
                "tree": AUTHORITY_TREE,
            },
            "base": {
                "boundary_id": "R011-B005",
                "receipt": identity_path(BASE_RECEIPT),
                "target_manifest": identity_path(BASE_MANIFEST),
                "snapshot_receipt": identity_path(BASE_SNAPSHOT_RECEIPT),
                "immutable_base_verified": True,
            },
            "scope": {
                "instructional_unit": "Section 2.2 Considering categorical data",
                "source_anchor": "categoricalData",
                "source": source_scope,
                "controls": controls,
                "assets": assets,
                "next_untranslated_marker": (
                    "ch_summarizing_data/TeX/ch_summarizing_data.tex / "
                    "Section 2.3 Case study: malaria vaccine"
                ),
            },
            "target_closure": {
                "manifest": {
                    "path": TARGET_MANIFEST.relative_to(LANE).as_posix(),
                    **identity_bytes(manifest_raw),
                },
                "closure_mode": (
                    "admitted R011-B005 manifest plus only the declared "
                    "R011-B006 overlays"
                ),
                **delta,
            },
            "checks": {
                "base_receipt_and_manifest_exact": "passed",
                "source_order_and_topology": "passed",
                "post_build_repairs_reverse_reconstructed": "passed",
                "post_build_repair_topology_and_display": "passed",
                "v3_layout_repairs_reverse_reconstructed": "passed",
                "prior_v3_layout_repair_receipt": identity_path(
                    V3_LAYOUT_REPAIR_RECEIPT
                ),
                "v4_layout_repair_reverse_reconstructed": "passed",
                "v4_layout_repair_receipt": {
                    "path": LAYOUT_REPAIR_RECEIPT.relative_to(LANE).as_posix(),
                    **identity_bytes(layout_receipt_raw),
                },
                "ADV_0070_through_0079": "passed",
                "rejected_v1_visual_findings_bound": "passed",
                "rejected_v2_visual_findings_bound": "passed",
                "rejected_v3_visual_findings_bound": "passed",
                "section_2_3_plus_authority_suffix": "passed",
                "source_corrections_SC_B006_001_through_005_only": "passed",
                "exercise_answer_o001_topology": "passed",
                "placeholders": 0,
                "active_reader_visible_english": 0,
                "asset_code_data_rights_closure": "passed",
                "manifest_delta_recomputed": True,
            },
            "gate_script": {
                "path": Path(__file__).relative_to(LANE).as_posix(),
                **identity_bytes(script_raw),
            },
            "write_boundary": (
                "qa/R011-B006_LAYOUT_REPAIR_RECEIPT_V4.json, "
                "qa/R011-B006_TARGET_MANIFEST.tsv, and "
                "qa/R011-B006_SOURCE_QA.json only"
            ),
        }
    )


def evaluate() -> tuple[
    bytes | None, bytes | None, bytes | None, list[str]
]:
    errors: list[str] = []
    base_rows = check_base(errors)
    authority = check_authority(errors)
    source_handoff = check_source_handoff(errors)
    repair_handoff, reconstructed_pre_repair = check_repair_handoff(errors)
    prior_layout_handoff, reconstructed_v2, reconstructed_v3 = (
        check_v2_rejection_and_layout_repair(errors)
    )
    layout_handoff = check_v3_rejection_and_v4_layout_repair(
        reconstructed_v3, errors
    )
    source_scope, _texts = validate_source(
        authority,
        reconstructed_pre_repair,
        reconstructed_v2,
        reconstructed_v3,
        errors,
    )
    source_scope["application_handoff"] = source_handoff
    source_scope["post_build_repair_handoff"] = repair_handoff
    controls = check_control_ledgers(errors)
    assets = check_asset_closure(errors)
    manifest_raw, delta = assemble_target_manifest(base_rows, errors)
    v2_manifest_reconstruction = check_v2_manifest_reconstruction(
        manifest_raw, errors
    )
    v3_manifest_reconstruction = check_v3_manifest_reconstruction(
        manifest_raw, errors
    )
    if errors:
        return None, None, None, errors
    prior_layout_handoff["v2_target_manifest_reverse_reconstruction"] = (
        v2_manifest_reconstruction
    )
    layout_handoff["v3_target_manifest_reverse_reconstruction"] = (
        v3_manifest_reconstruction
    )
    layout_receipt_raw = construct_layout_repair_receipt(
        manifest_raw, layout_handoff, v3_manifest_reconstruction
    )
    layout_handoff["layout_repair_receipt"] = {
        "path": LAYOUT_REPAIR_RECEIPT.relative_to(LANE).as_posix(),
        **identity_bytes(layout_receipt_raw),
    }
    source_scope["v3_layout_repair_handoff"] = prior_layout_handoff
    source_scope["v4_layout_repair_handoff"] = layout_handoff
    receipt_raw = construct_receipt(
        manifest_raw,
        layout_receipt_raw,
        delta,
        source_scope,
        controls,
        assets,
    )
    return manifest_raw, layout_receipt_raw, receipt_raw, []


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise


def self_tests() -> dict[str, object]:
    tests: list[tuple[str, bool]] = []
    tests.append(("manifest_sort", render_manifest({"b": (1, "b" * 64), "a": (2, "a" * 64)}).startswith(b"a\t")))
    manifest_errors: list[str] = []
    parse_manifest(
        b"b\t1\t" + b"b" * 64 + b"\na\t1\t" + b"a" * 64 + b"\n",
        "mutant",
        manifest_errors,
    )
    tests.append(("unsorted_manifest_rejected", "mutant is not sorted" in manifest_errors))
    tests.append(("comment_escape", split_comment(r"x \% y % z") == (r"x \% y ", " z")))
    tests.append(("balanced_nested", balanced_argument("{a{b}c}", 0, "{", "}") == ("a{b}c", 7)))
    tests.append(("command_mutation", command_sequence(r"\section{x}\label{a}") != command_sequence(r"\section{x}")))
    tests.append(("environment_mutation", environment_sequence(r"\begin{x}\end{x}") != environment_sequence(r"\begin{x}")))
    tests.append(("math_mutation", math_sequence("x $1+1$") != math_sequence("x $1+2$")))
    tests.append(("english_injection", bool(english_hits("Ini benar. The answer is visible."))))
    tests.append(("placeholder_injection", bool(re.search(r"\bTODO\b", "TODO", re.IGNORECASE))))
    suffix_errors: list[str] = []
    _prefix, middle, _suffix = split_target_answer_block(
        b"prefix-OLD-suffix",
        b"prefix-NEW-mutated",
        b"OLD-",
        suffix_errors,
    )
    tests.append(("answer_suffix_mutation", bool(suffix_errors) and not middle))
    tests.append(("pending_state_rejected", recursively_bad_state({"status": "pending"}) == ["status=pending"]))
    alt_errors: list[str] = []
    check_alt_asset_label_mapping(
        [
            {"asset_id": asset_id, "alternative_text": " ".join(labels)}
            for asset_id, labels in ALT_REQUIRED_LABELS.items()
        ],
        alt_errors,
    )
    tests.append(("localized_alt_contract", not alt_errors))
    all_layout_operations = V3_LAYOUT_REPAIR_OPERATIONS + LAYOUT_REPAIR_OPERATIONS
    tests.append(
        (
            "layout_operation_ids_unique",
            len({str(item["id"]) for item in all_layout_operations})
            == len(all_layout_operations),
        )
    )
    tests.append(
        (
            "layout_fragments_reverse_exact",
            all(
                str(item["after_utf8"])
                .replace(str(item["after_utf8"]), str(item["before_utf8"]), 1)
                == str(item["before_utf8"])
                and str(item["after_utf8"]).count(str(item["after_utf8"])) == 1
                for item in all_layout_operations
            ),
        )
    )
    failed = [name for name, passed in tests if not passed]
    return {
        "status": "passed" if not failed else "failed",
        "passed": len(tests) - len(failed),
        "total": len(tests),
        "failed": failed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Deterministic R011-B006 source and target-manifest gate"
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="atomically write the manifest and both QA receipts after PASS",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="run pure in-memory adversarial helper tests and exit",
    )
    args = parser.parse_args()

    if args.self_test:
        result = self_tests()
        print(canonical_json(result).decode("utf-8"), end="")
        return 0 if result["status"] == "passed" else 1

    manifest_raw, layout_receipt_raw, receipt_raw, errors = evaluate()
    if errors:
        print(
            canonical_json(
                {
                    "boundary_id": BOUNDARY_ID,
                    "status": "failed",
                    "write_requested": args.write,
                    "errors": errors,
                }
            ).decode("utf-8"),
            end="",
        )
        return 1

    assert (
        manifest_raw is not None
        and layout_receipt_raw is not None
        and receipt_raw is not None
    )
    if args.write:
        atomic_write(TARGET_MANIFEST, manifest_raw)
        atomic_write(LAYOUT_REPAIR_RECEIPT, layout_receipt_raw)
        atomic_write(RECEIPT, receipt_raw)
        if (
            TARGET_MANIFEST.read_bytes() != manifest_raw
            or LAYOUT_REPAIR_RECEIPT.read_bytes() != layout_receipt_raw
            or RECEIPT.read_bytes() != receipt_raw
        ):
            raise RuntimeError("post-write readback mismatch")
        state = "written_and_read_back"
    else:
        comparisons = {
            "target_manifest": (
                not TARGET_MANIFEST.exists()
                or TARGET_MANIFEST.read_bytes() == manifest_raw
            ),
            "source_receipt": not RECEIPT.exists() or RECEIPT.read_bytes() == receipt_raw,
            "layout_repair_receipt": (
                not LAYOUT_REPAIR_RECEIPT.exists()
                or LAYOUT_REPAIR_RECEIPT.read_bytes() == layout_receipt_raw
            ),
        }
        require(all(comparisons.values()), "existing output differs from candidate", errors)
        if errors:
            print(
                canonical_json(
                    {
                        "boundary_id": BOUNDARY_ID,
                        "status": "failed",
                        "errors": errors,
                    }
                ).decode("utf-8"),
                end="",
            )
            return 1
        state = "read_only_candidate"

    print(
        canonical_json(
            {
                "boundary_id": BOUNDARY_ID,
                "status": "passed",
                "mode": state,
                "target_manifest": {
                    "path": TARGET_MANIFEST.relative_to(LANE).as_posix(),
                    **identity_bytes(manifest_raw),
                },
                "source_receipt": {
                    "path": RECEIPT.relative_to(LANE).as_posix(),
                    **identity_bytes(receipt_raw),
                },
                "layout_repair_receipt": {
                    "path": LAYOUT_REPAIR_RECEIPT.relative_to(LANE).as_posix(),
                    **identity_bytes(layout_receipt_raw),
                },
            }
        ).decode("utf-8"),
        end="",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
