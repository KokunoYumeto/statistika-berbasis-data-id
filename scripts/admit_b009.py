#!/usr/bin/env python3
"""Fail-closed admission transaction for the R011-B009 checkpoint.

This module is deliberately conservative.  Readiness and self-test modes are
read-only; only an explicit ``python scripts/admit_b009.py --promote`` can
write the canonical lane.  Every translated source, localized figure, reader
PDF, and QA receipt is bound to an exact byte identity.  The current B008
backend/PDF/source state is checked before admission and is copied to a
transaction-local preimage store before the first replacement.  An isolated
backend binding file is required; an unset or partial binding can never be
promoted.

No credentials, network calls, repository scans, or upstream communication are
performed by this script.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
import unicodedata
from pathlib import Path
from typing import Any


LANE = Path(__file__).resolve().parents[1]
BOUNDARY_ID = "R011-B009"
BASE_BOUNDARY_ID = "R011-B008"
MODEL = "OpenAI Codex gpt-5.6-sol, Ultra"
AUTHORITY_COMMIT = "fee25091fb24e89c36296fd67c48c1fcf7a93b6e"
AUTHORITY_TREE = "d61cc601e7d97759ce805900520f784d02a0489e"

LIVE_EXPORTS = LANE / "backend" / "exports"
BACKEND_BINDING_CONFIG = LANE / "qa" / "b009-backend-final" / "R011-B009_BACKEND_BINDING.json"
ADMISSION_ROOT = LANE / "qa" / "b009-admission"
PREIMAGE_ROOT = ADMISSION_ROOT / "preimages-R011-B009"
LOCK_PATH = ADMISSION_ROOT / ".R011-B009-admission.lock"
JOURNAL_PATH = ADMISSION_ROOT / "R011-B009_ADMISSION_TRANSACTION_JOURNAL.json"
BOUNDARY_RECEIPT_PATH = LANE / "qa" / "R011-B009_BOUNDARY_RECEIPT.json"
PROMOTED_PDF_PATH = LANE / "output" / "pdf" / "statistika-berbasis-data-batas-R011-B009.pdf"


class GateError(RuntimeError):
    """A missing or changed admission identity; never silently continue."""


def lane_path(relative: str) -> Path:
    """Resolve a portable lane-relative path, refusing traversal."""
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise ValueError(f"path must be portable and lane-relative: {relative!r}")
    item = Path(relative)
    if item.is_absolute() or ".." in item.parts or item.as_posix() != relative:
        raise ValueError(f"path escapes or is noncanonical: {relative!r}")
    root = LANE.resolve()
    resolved = (LANE / item).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"path resolves outside the R011 lane: {relative!r}") from exc
    return resolved


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_json(value: Any) -> bytes:
    text = unicodedata.normalize(
        "NFC", json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )
    return (text + "\n").encode("utf-8")


def identity(raw: bytes, path: str | None = None) -> dict[str, Any]:
    value: dict[str, Any] = {"bytes": len(raw), "sha256": digest(raw)}
    return {"path": path, **value} if path is not None else value


def file_identity(relative: str, expected: dict[str, Any] | None = None) -> tuple[Path, bytes, dict[str, Any]]:
    path = lane_path(relative)
    if not path.is_file():
        raise GateError(f"missing required file: {relative}")
    raw = path.read_bytes()
    actual = identity(raw, relative)
    if expected is not None:
        wanted = {"path": relative, "bytes": expected["bytes"], "sha256": expected["sha256"]}
        if actual != wanted:
            raise GateError(f"identity changed: {relative} (expected {wanted}, got {actual})")
    return path, raw, actual


def inventory(root: Path) -> tuple[str, int, int, dict[str, bytes]]:
    """Use the same full-path ordering as the backend validator."""
    payloads: dict[str, bytes] = {}
    lines: list[str] = []
    total = 0
    paths = sorted(item for item in root.rglob("*") if item.is_file()) if root.is_dir() else []
    for path in paths:
        relative = path.relative_to(root).as_posix()
        raw = path.read_bytes()
        payloads[relative] = raw
        total += len(raw)
        lines.append(f"{relative}\t{len(raw)}\t{digest(raw)}\n")
    return digest("".join(lines).encode("utf-8")), len(paths), total, payloads


# Exact candidate identities.  These are immutable admission inputs, not
# discovery hints.  The assembled answer is the full file made from the
# frozen B008 answer witness plus the translated public odd-answer slice.
CANDIDATE_FILES: dict[str, dict[str, Any]] = {
    "main_source": {
        "path": "scratch/b009-candidate/ch_probability_B009.tex",
        "bytes": 133742,
        "sha256": "5304291d9a89e1490d9c1d973cbce4cfe8e8000d412e004131f3e299bb0f8379",
    },
    "eoce_source": {
        "path": "scratch/b009-candidate/defining_probability_B009.tex",
        "bytes": 9638,
        "sha256": "bc2724a38cccc9d923d9756e72ae374c1fbe82dab4ade1cf8cbded016d6bd5b0",
    },
    "odd_answers": {
        "path": "scratch/b009-candidate/R011-B009_PUBLIC_ODD_ANSWERS.tex",
        "bytes": 3186,
        "sha256": "63bc7ebe8fea3d3100699af7e831ce89afe33aaceaca686fc9d1877a16114c73",
    },
    "assembled_answers": {
        "path": "qa/b009-build/source-snapshot-b009/extraTeX/eoceSolutions/eoceSolutions.tex",
        "bytes": 108263,
        "sha256": "30466c20b8e9b6fe2db9f13cec05e00e3a114b4148cd5af9d6125cea074e1612",
    },
    "candidate_pdf": {
        "path": "qa/b009-build/final/main.pdf",
        "bytes": 22026147,
        "sha256": "b4aea1920ede7e97b58775270f4b3f812358830c30f152e61a9cdca8a39fcfb6",
    },
    "build_receipt": {
        "path": "qa/b009-build/final/CANDIDATE_BUILD_QA_B009.json",
        "bytes": 12681,
        "sha256": "7cbe792aef59795de4904be690d76229ad88088848539d9d242c06b35cc83bcc",
    },
    "source_manifest": {
        "path": "qa/b009-build/R011-B009_SOURCE_MANIFEST.tsv",
        "bytes": 176788,
        "sha256": "55d7f966ef433649937ab19b48e4c0bd8ae907fd972833b0a6edc7da17bc5ae0",
    },
    "source_qa": {
        "path": "qa/b009-build/R011-B009_SOURCE_QA.json",
        "bytes": 5482,
        "sha256": "ccfcb9a482e16af06c1dd19ea1b4da2968dc3af26704d6cf23088c5c9ed13b42",
    },
    "visual_receipt": {
        "path": "qa/b009-build/R011-B009_VISUAL_AUDIT.json",
        "bytes": 5127,
        "sha256": "760a689b7d288abeb7575c9979820d27e07e5d4b7629ca41c5ce9a8b7aa27c59",
    },
}


FIGURE_NAMES = (
    "dieProp",
    "disjointSets",
    "cardsDiamondFaceVenn",
    "loans_app_type_home_venn",
    "usHouseholdIncomeDistBar",
    "diceSumDist",
    "complementOfD",
    "indepForRollingTwo1s",
)
FIGURE_CANDIDATES: dict[str, dict[str, Any]] = {
    "dieProp": {"path": "scratch/b009-assets/id-ID/dieProp.id-ID.pdf", "bytes": 9633, "sha256": "629a7ed0a032902291b9740957056468f63206b1120ab5957def8d842552ade2"},
    "disjointSets": {"path": "scratch/b009-assets/id-ID/disjointSets.id-ID.pdf", "bytes": 5743, "sha256": "ed2fb35fdfdf2a3932bb7d39b0308bffef5dfd251fe3eab59fd1a353b6369d2b"},
    "cardsDiamondFaceVenn": {"path": "scratch/b009-assets/id-ID/cardsDiamondFaceVenn.id-ID.pdf", "bytes": 12396, "sha256": "2a04b57a93830ba35031f8efd7f6cecb7e5dd6028fbeca3ef45fb87bd83473ec"},
    "loans_app_type_home_venn": {"path": "scratch/b009-assets/id-ID/loans_app_type_home_venn.id-ID.pdf", "bytes": 5467, "sha256": "44221c5d513cb7f7b1d8d017b2cd0c3351e7497c60357ee241ad50f27169225e"},
    "usHouseholdIncomeDistBar": {"path": "scratch/b009-assets/id-ID/usHouseholdIncomeDistBar.id-ID.pdf", "bytes": 4504, "sha256": "238b83b41fdf9b49ed05706f0407fade3ad6554c5be8b5b1f60b6d806057281f"},
    "diceSumDist": {"path": "scratch/b009-assets/id-ID/diceSumDist.id-ID.pdf", "bytes": 4610, "sha256": "ef2fd93c8d9f7f7e87087b156e18f082916ccb13b31bc9f361419f7703bae3f4"},
    "complementOfD": {"path": "scratch/b009-assets/id-ID/complementOfD.id-ID.pdf", "bytes": 5369, "sha256": "4da53190e9771de3a86c21943e64ce514d9e39471b54a015be4baba490af68f7"},
    "indepForRollingTwo1s": {"path": "scratch/b009-assets/id-ID/indepForRollingTwo1s.id-ID.pdf", "bytes": 4631, "sha256": "4d157c19e2fb6ac1f0d32e4eee117659164ccdf8ecc343718c22301ce6c7e4ef"},
    "swing_voters": {"path": "scratch/b009-assets/id-ID/swing_voters.id-ID.pdf", "bytes": 27747, "sha256": "59d14e7f2eea95028ee48d5d787847eb7bf43745b1d4b3bbbe6d88bea49b739d"},
}

ASSET_RECEIPTS: dict[str, dict[str, Any]] = {
    "figure_localization": {"path": "scratch/b009-assets/receipts/R011-B009_FIGURE_LOCALIZATION_RECEIPT.json", "bytes": 12418, "sha256": "45659aa448413e9dfe603c6e656c2af5d48018188584542ad01bf683cb0eaa1f"},
    "figure_inventory": {"path": "scratch/b009-assets/receipts/R011-B009_FIGURE_LOCALIZATION_INVENTORY.tsv", "bytes": 2027, "sha256": "e0949210b50e1c477ed2ba379f31add45c6947e54ff62287a3b8552e9ad2e9b7"},
    "figure_visual_qa": {"path": "scratch/b009-assets/receipts/R011-B009_FIGURE_VISUAL_QA.json", "bytes": 4250, "sha256": "c3f6fb0484a7a2b0ccb7535a1df4890ffb830bc849b35d27f109738ae274f851"},
    "swing_manifest": {"path": "scratch/b009-assets/receipts/R011-B009_SWING_VOTERS_ASSET_MANIFEST.tsv", "bytes": 1191, "sha256": "b9e6277324c1014094b94b5e1448f3874b32e34eecbba0a929452ef53720f9c0"},
    "swing_receipt": {"path": "scratch/b009-assets/receipts/R011-B009_SWING_VOTERS_LOCALIZATION_RECEIPT.json", "bytes": 3695, "sha256": "47f02c8800f00ca8114e25f95cb03d5f171aaf5aabfcaf2416a1baa1591a409a"},
}


# The targets below are the exact paths used by the isolated build overlay.
# Their current B008 identities are checked before any write and recorded in
# the rollback journal.  This retains upstream English source files elsewhere
# in the frozen closure while making the canonical reader overlay reproducible.
OVERLAY_TARGETS: dict[str, str] = {
    "main_source": "repo/ch_probability/TeX/ch_probability.tex",
    "eoce_source": "repo/ch_probability/TeX/defining_probability.tex",
    "assembled_answers": "repo/extraTeX/eoceSolutions/eoceSolutions.tex",
    "dieProp": "repo/ch_probability/figures/dieProp/dieProp.pdf",
    "disjointSets": "repo/ch_probability/figures/disjointSets/disjointSets.pdf",
    "cardsDiamondFaceVenn": "repo/ch_probability/figures/cardsDiamondFaceVenn/cardsDiamondFaceVenn.pdf",
    "loans_app_type_home_venn": "repo/ch_probability/figures/loans_app_type_home_venn/loans_app_type_home_venn.pdf",
    "usHouseholdIncomeDistBar": "repo/ch_probability/figures/usHouseholdIncomeDistBar/usHouseholdIncomeDistBar.pdf",
    "diceSumDist": "repo/ch_probability/figures/diceSumDist/diceSumDist.pdf",
    "complementOfD": "repo/ch_probability/figures/complementOfD/complementOfD.pdf",
    "indepForRollingTwo1s": "repo/ch_probability/figures/indepForRollingTwo1s/indepForRollingTwo1s.pdf",
    "swing_voters": "repo/ch_probability/figures/eoce/swing_voters/swing_voters.pdf",
}


# Exact B008 preimages.  These are intentionally hard-coded so an accidental
# lane drift cannot be mistaken for a safe continuation.
B008_PREIMAGE: dict[str, Any] = {
    "boundary_receipt": {"path": "qa/R011-B008_BOUNDARY_RECEIPT.json", "bytes": 6108, "sha256": "ddc00a2f4dc4a4a5307ea99d4e7f64faa9bb0aadeff4b104ee1a992ff95c7076"},
    "pdf": {"path": "output/pdf/statistika-berbasis-data-batas-R011-B008.pdf", "bytes": 22017328, "sha256": "8aa8e6ecc3edc2a33ee8d83a586c6208e49966582b2fc439c8b3007470f32800"},
    "main_source": {"path": "repo/ch_probability/TeX/ch_probability.tex", "bytes": 132799, "sha256": "4f07fcf0e71e52bc99657835d5cced47b10ce9fc66b23dce156d400840690361"},
    "eoce_source": {"path": "repo/ch_probability/TeX/defining_probability.tex", "bytes": 9353, "sha256": "e0ad00ef9795134900a96bb1304111126abf0531eb9a24f16fa96d6a20a5a95f"},
    "assembled_answers": {"path": "repo/extraTeX/eoceSolutions/eoceSolutions.tex", "bytes": 108110, "sha256": "2b2709d17fcca943dde69288726a669fd978f576957518142e24c5aa2e86c140"},
    "backend": {"root": "backend/exports", "file_count": 118, "bytes": 7712543, "sha256": "eb1e37d42c4bd97a720a1a60001b229e1fefed095635d67588c686713834726f"},
}

# B008 source PDF identities for the nine figure targets.  These come from
# the pinned B008 source manifest and protect against an unreviewed intervening
# edit before a B009 promotion.
B008_FIGURE_PREIMAGES: dict[str, dict[str, Any]] = {
    "dieProp": {"bytes": 9525, "sha256": "9510fbd1d17b95ecff3a03fd200ffd560a8684a21ff2072012536366e8032446"},
    "disjointSets": {"bytes": 5743, "sha256": "ed2fb35fdfdf2a3932bb7d39b0308bffef5dfd251fe3eab59fd1a353b6369d2b"},
    "cardsDiamondFaceVenn": {"bytes": 12304, "sha256": "387830a1801b8b128bfe1d744cdcc872ec83e2235422969a5402a5de952047b3"},
    "loans_app_type_home_venn": {"bytes": 5351, "sha256": "b582e4e7004abb403bf88f7e8ea7c8f03555abff07cb8e8c04357fe60dbc776d"},
    "usHouseholdIncomeDistBar": {"bytes": 4383, "sha256": "19adc8aa2b6e37eb767b143550d9d8885d31b6efdf083b31f00cccc0560926e7"},
    "diceSumDist": {"bytes": 4482, "sha256": "76ef9ac01c4865463e04ddf0e95568cc911d333e29b4e917ce72b8877d4eb48a"},
    "complementOfD": {"bytes": 5369, "sha256": "4da53190e9771de3a86c21943e64ce514d9e39471b54a015be4baba490af68f7"},
    "indepForRollingTwo1s": {"bytes": 4506, "sha256": "aae97a030da72e528ce4156469c27911e1db939a0829b80bffe8a297631953d5"},
    "swing_voters": {"bytes": 19688, "sha256": "fd2e8dd9131b3b2bd08654d53a1ed7e984edab8bfd30d4944f0c9d32d8472da2"},
}


def _candidate_expected(name: str) -> dict[str, Any]:
    return CANDIDATE_FILES[name]


def verify_candidate_files() -> dict[str, bytes]:
    raws: dict[str, bytes] = {}
    for name, expected in CANDIDATE_FILES.items():
        _path, raw, _actual = file_identity(expected["path"], expected)
        raws[name] = raw
    # Bind all eight ordinary localized figures plus the swing-voter EoCE
    # figure into the promotion context; these are intentionally separate from
    # the textual candidate file map above.
    for name, expected in FIGURE_CANDIDATES.items():
        _path, raw, _actual = file_identity(expected["path"], expected)
        raws[name] = raw
    for expected in ASSET_RECEIPTS.values():
        file_identity(expected["path"], expected)

    build = json.loads(raws["build_receipt"])
    pdf = _candidate_expected("candidate_pdf")
    source_qa = json.loads(raws["source_qa"])
    if (
        source_qa.get("$schema") != "r011-b009-source-qa/v1"
        or source_qa.get("boundary_id") != BOUNDARY_ID
        or source_qa.get("status") != "PASS_ISOLATED_OVERLAY_CLOSURE"
        or source_qa.get("checks", {}).get("main", {}).get("nexercise") != 18
        or source_qa.get("checks", {}).get("eoce", {}).get("exercise_count") != 12
        or source_qa.get("checks", {}).get("answers", {}).get("public_odd_answers") != [1, 3, 5, 7, 9, 11]
        or source_qa.get("checks", {}).get("main", {}).get("figures") != 8
        or source_qa.get("checks", {}).get("main", {}).get("footnotetext") != 18
    ):
        raise GateError("source QA receipt contract failed")
    if (
        build.get("$schema") != "r011-b009-candidate-build-qa/v1"
        or build.get("boundary_id") != BOUNDARY_ID
        or build.get("status") != "PASS_ISOLATED_DETERMINISTIC_BUILD"
        or build.get("canonical_mutation") is not False
        or build.get("candidate_artifact") != {"bytes": pdf["bytes"], "path": pdf["path"], "promoted": False, "sha256": pdf["sha256"]}
        or build.get("determinism", {}).get("byte_identical") is not True
        or build.get("determinism", {}).get("pass3", {}).get("sha256") != pdf["sha256"]
        or build.get("determinism", {}).get("pass4", {}).get("sha256") != pdf["sha256"]
        or build.get("production_model") != MODEL
        or build.get("page_count") != 426
    ):
        raise GateError("candidate build receipt contract failed")

    visual = json.loads(raws["visual_receipt"])
    visual_candidate = visual.get("candidate_pdf", {})
    if (
        visual.get("$schema") != "r011-b009-visual-audit/v1"
        or visual.get("boundary_id") != BOUNDARY_ID
        or visual.get("canonical_mutation") is not False
        or visual.get("production_model") != MODEL
        or visual.get("inspection", {}).get("result") != "PASS"
        or visual.get("inspection", {}).get("findings") != []
        or visual.get("status") != "PASS_HUMAN_REVIEWED_BOUNDARY_WINDOW"
        or visual_candidate.get("bytes") != pdf["bytes"]
        or visual_candidate.get("sha256") != pdf["sha256"]
        or visual_candidate.get("pages") != 426
    ):
        raise GateError("visual audit receipt contract failed")
    for item in visual.get("rendered_pages", []):
        path = item.get("path")
        if not isinstance(path, str) or Path(path).is_absolute() or "\\" in path:
            raise GateError("visual receipt contains a non-portable render path")
        _path, raw, actual = file_identity(path)
        if actual["bytes"] != item.get("bytes") or actual["sha256"] != item.get("sha256"):
            raise GateError(f"visual render identity changed: {path}")
    main_text = raws["main_source"].decode("utf-8")
    eoce_text = raws["eoce_source"].decode("utf-8")
    answer_text = raws["assembled_answers"].decode("utf-8")
    # The candidate deliberately retains the English witness after the B009
    # boundary, so count exercises only in the accepted first 684 source-order
    # lines rather than in the entire later chapter.
    main_boundary = "\n".join(main_text.splitlines()[:684])
    if main_boundary.count(r"\begin{nexercise}") != 18 or "Probabilitas" not in main_boundary:
        raise GateError("main translated boundary structure/term check failed")
    if eoce_text.count(r"\eoce{") != 12 or "peluang" not in eoce_text:
        raise GateError("EoCE translated boundary structure/term check failed")
    for marker in (r"\eocesolch{Probabilitas}", "% 1", "% 3", "% 5", "% 7", "% 9", "% 11"):
        if marker not in answer_text:
            raise GateError(f"assembled answer candidate lacks required public marker: {marker}")
    return raws


def verify_b008_preimage() -> tuple[dict[str, bytes], dict[str, Any]]:
    for key in ("boundary_receipt", "pdf", "main_source", "eoce_source", "assembled_answers"):
        expected = B008_PREIMAGE[key]
        file_identity(expected["path"], expected)
    boundary = json.loads(lane_path(B008_PREIMAGE["boundary_receipt"]["path"]).read_bytes())
    if boundary.get("boundary_id") != BASE_BOUNDARY_ID or boundary.get("status") != "admitted_exact_pdf_and_backend":
        raise GateError("B008 boundary receipt no longer proves exact admission")
    for name, expected in B008_FIGURE_PREIMAGES.items():
        target = OVERLAY_TARGETS[name]
        file_identity(target, {"bytes": expected["bytes"], "sha256": expected["sha256"]})
    root = lane_path(B008_PREIMAGE["backend"]["root"])
    sha, count, total, payloads = inventory(root)
    expected_backend = B008_PREIMAGE["backend"]
    if (sha, count, total) != (expected_backend["sha256"], expected_backend["file_count"], expected_backend["bytes"]):
        raise GateError("live backend is not the exact B008 preimage")
    return payloads, {"sha256": sha, "file_count": count, "bytes": total}


def load_backend_binding() -> tuple[dict[str, Any], dict[str, bytes]]:
    if not BACKEND_BINDING_CONFIG.is_file():
        raise GateError(
            "isolated backend binding config is absent/unset: "
            "qa/b009-backend-final/R011-B009_BACKEND_BINDING.json"
        )
    try:
        config = json.loads(BACKEND_BINDING_CONFIG.read_text(encoding="utf-8"))
    except Exception as exc:
        raise GateError(f"isolated backend binding config is not valid JSON: {exc}") from exc
    required = ("stage_root", "stage_manifest", "validation_receipt", "inventory", "record_count")
    missing = [key for key in required if config.get(key) in (None, "")]
    if missing:
        raise GateError("isolated backend binding is incomplete: " + ", ".join(missing))
    if config.get("stage_root") != "qa/b009-backend-final/exports":
        raise GateError("isolated backend stage root is not the bounded B009 stage")
    manifest = config["stage_manifest"]
    if not isinstance(manifest, dict) or manifest.get("path") != "qa/b009-backend-final/exports/manifest.json":
        raise GateError("backend binding manifest path is invalid")
    stage_root = lane_path(config["stage_root"])
    if not stage_root.is_dir():
        raise GateError("isolated backend stage directory is absent")
    stage_sha, stage_count, stage_bytes, staged = inventory(stage_root)
    inventory_expected = config["inventory"]
    if {
        "sha256": stage_sha,
        "file_count": stage_count,
        "bytes": stage_bytes,
    } != {
        "sha256": inventory_expected.get("sha256"),
        "file_count": inventory_expected.get("file_count"),
        "bytes": inventory_expected.get("bytes"),
    }:
        raise GateError("isolated backend stage inventory differs from binding")
    # Admission replaces bounded export files atomically and intentionally
    # does not perform implicit deletion.  Require the isolated stage to cover
    # every current live path, otherwise stale B008 evidence would remain in
    # the live tree and the post-admission byte replay could never pass.  New
    # B009-only stage paths are allowed and will be created atomically.
    live_root = LIVE_EXPORTS
    _live_sha, _live_count, _live_bytes, live_payloads = inventory(live_root)
    live_only = sorted(set(live_payloads) - set(staged))
    stage_only = sorted(set(staged) - set(live_payloads))
    if live_only:
        raise GateError(
            "isolated backend stage path coverage differs from live tree: "
            f"live_only={len(live_only)} stage_only={len(stage_only)} "
            f"live_only_sample={live_only[:5]} stage_only_sample={stage_only[:5]}"
        )
    manifest_expected = {"path": manifest["path"], "bytes": manifest.get("bytes"), "sha256": manifest.get("sha256")}
    if not isinstance(manifest_expected["bytes"], int) or not isinstance(manifest_expected["sha256"], str):
        raise GateError("isolated backend manifest identity is unset")
    _manifest_path, manifest_raw, _ = file_identity(manifest_expected["path"], manifest_expected)
    try:
        stage_manifest_json = json.loads(manifest_raw)
    except Exception as exc:
        raise GateError(f"isolated backend stage manifest is not JSON: {exc}") from exc
    if stage_manifest_json.get("admission_eligibility") != "ready_for_separate_guarded_admission_transaction":
        raise GateError("isolated backend stage is not marked ready for guarded admission")
    stage_state = stage_manifest_json.get("stage_state", {})
    for forbidden in ("boundary_admitted", "live_backend_mutated", "promotion_performed", "publication_performed"):
        if stage_state.get(forbidden) is True:
            raise GateError(f"isolated backend stage has forbidden mutated state: {forbidden}")
    validation = config["validation_receipt"]
    if not isinstance(validation, dict) or not isinstance(validation.get("path"), str):
        raise GateError("isolated backend validation receipt binding is unset")
    validation_expected = {"path": validation["path"], "bytes": validation.get("bytes"), "sha256": validation.get("sha256")}
    if not isinstance(validation_expected["bytes"], int) or not isinstance(validation_expected["sha256"], str):
        raise GateError("isolated backend validation receipt identity is unset")
    _vpath, vraw, _ = file_identity(validation_expected["path"], validation_expected)
    try:
        validation_json = json.loads(vraw)
    except Exception as exc:
        raise GateError(f"isolated backend validation receipt is not JSON: {exc}") from exc
    status = str(validation_json.get("status", ""))
    if "pass" not in status.lower() or "ready" not in status.lower():
        raise GateError("isolated backend validation receipt is not a passed ready state")
    if config.get("record_count") is None or not isinstance(config["record_count"], int) or config["record_count"] <= 0:
        raise GateError("isolated backend record_count is unset/invalid")
    return config, staged


def target_preimages() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for name, target_relative in OVERLAY_TARGETS.items():
        target = lane_path(target_relative)
        if not target.is_file():
            raise GateError(f"canonical overlay target is absent: {target_relative}")
        raw = target.read_bytes()
        result[target_relative] = {"state": "present_exact", "path": target_relative, **identity(raw)}
    if PROMOTED_PDF_PATH.exists():
        raw = PROMOTED_PDF_PATH.read_bytes()
        candidate = _candidate_expected("candidate_pdf")
        if identity(raw) != {"bytes": candidate["bytes"], "sha256": candidate["sha256"]}:
            raise GateError("existing B009 PDF is neither absent nor the exact candidate")
        result[PROMOTED_PDF_PATH.relative_to(LANE).as_posix()] = {"state": "present_exact", "path": PROMOTED_PDF_PATH.relative_to(LANE).as_posix(), **identity(raw)}
    else:
        result[PROMOTED_PDF_PATH.relative_to(LANE).as_posix()] = {"state": "absent", "path": PROMOTED_PDF_PATH.relative_to(LANE).as_posix()}
    return result


def _write_atomic(path: Path, raw: bytes, *, create_only: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        if temporary.read_bytes() != raw:
            raise GateError(f"temporary write readback failed: {path}")
        if create_only:
            try:
                os.link(temporary, path)
            except FileExistsError as exc:
                raise GateError(f"refusing to overwrite existing evidence: {path}") from exc
        else:
            os.replace(temporary, path)
        if path.read_bytes() != raw:
            raise GateError(f"post-write readback failed: {path}")
    finally:
        temporary.unlink(missing_ok=True)


def _preimage_backup(preimages: dict[str, dict[str, Any]], backend: dict[str, bytes]) -> dict[str, Any]:
    if PREIMAGE_ROOT.exists():
        raise GateError("B009 preimage directory already exists; manual transaction review required")
    PREIMAGE_ROOT.mkdir(parents=True, exist_ok=False)
    records: dict[str, Any] = {}
    for index, (relative, record) in enumerate(sorted(preimages.items())):
        if record["state"] == "absent":
            records[relative] = record
            continue
        raw = lane_path(relative).read_bytes()
        backup_relative = f"files/{index:03d}.bin"
        _write_atomic(PREIMAGE_ROOT / backup_relative, raw, create_only=True)
        records[relative] = {**record, "backup": backup_relative}
    for relative, raw in sorted(backend.items()):
        backup_relative = "backend/" + relative
        _write_atomic(PREIMAGE_ROOT / backup_relative, raw, create_only=True)
    manifest = {"$schema": "r011-b009-preimage-manifest/v1", "boundary_id": BOUNDARY_ID, "files": records, "backend_root": "backend/exports", "backend_file_count": len(backend), "backend_bytes": sum(len(raw) for raw in backend.values()), "backend_sha256": inventory(lane_path(B008_PREIMAGE["backend"]["root"]))[0]}
    manifest_raw = canonical_json(manifest)
    _write_atomic(PREIMAGE_ROOT / "PREIMAGE_MANIFEST.json", manifest_raw, create_only=True)
    return {"manifest": manifest, "manifest_sha256": digest(manifest_raw)}


def _lock() -> None:
    ADMISSION_ROOT.mkdir(parents=True, exist_ok=True)
    if LOCK_PATH.exists() or JOURNAL_PATH.exists() or PREIMAGE_ROOT.exists():
        raise GateError("B009 admission lock/journal already exists; manual recovery is required")
    lock_raw = canonical_json({"boundary_id": BOUNDARY_ID, "status": "authorized_cli_admission_in_progress"})
    try:
        descriptor = os.open(LOCK_PATH, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise GateError("another B009 admission transaction holds the lock") from exc
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(lock_raw)
        stream.flush()
        os.fsync(stream.fileno())


def _rollback_order(written: list[str]) -> list[str]:
    nonmanifest = sorted((item for item in written if item != "manifest.json"), reverse=True)
    return nonmanifest + (["manifest.json"] if "manifest.json" in written else [])


def compact_backend_binding(config: dict[str, Any]) -> dict[str, Any]:
    """Keep only lane-relative, release-safe backend binding fields."""
    return {
        "stage_root": config["stage_root"],
        "stage_manifest": config["stage_manifest"],
        "validation_receipt": config["validation_receipt"],
        "inventory": config["inventory"],
        "record_count": config["record_count"],
    }


def construct_receipt(config: dict[str, Any], candidate: dict[str, bytes], preimages: dict[str, dict[str, Any]], pdf_action: str) -> bytes:
    if pdf_action not in {"created_from_candidate", "verified_preexisting_exact"}:
        raise GateError("unsupported PDF admission action")
    receipt = {
        "$schema": "r011-b009-boundary-receipt/v1",
        "boundary_id": BOUNDARY_ID,
        "base_boundary": BASE_BOUNDARY_ID,
        "status": "admitted_exact_pdf_source_assets_and_backend",
        "authority": {"repo": "OpenIntroStat/openintro-statistics", "commit": AUTHORITY_COMMIT, "tree": AUTHORITY_TREE},
        "production_model": MODEL,
        "scope": "Bab 3 pembuka + Defining probability / Peluang; 18 guided exercises; 12 EoCE exercises; public answers 1/3/5/7/9/11; later content remains English witness.",
        "base_preimage": B008_PREIMAGE,
        "backend_binding": compact_backend_binding(config),
        "candidate_files": {
            **{name: identity(candidate[name], CANDIDATE_FILES[name]["path"]) for name in CANDIDATE_FILES},
            **{name: identity(candidate[name], FIGURE_CANDIDATES[name]["path"]) for name in FIGURE_CANDIDATES},
        },
        "localized_figures": {name: {"candidate": FIGURE_CANDIDATES[name], "target": OVERLAY_TARGETS[name]} for name in FIGURE_CANDIDATES},
        "asset_receipts": ASSET_RECEIPTS,
        "canonical_targets_prestate": preimages,
        "promoted_pdf": {"path": PROMOTED_PDF_PATH.relative_to(LANE).as_posix(), "bytes": CANDIDATE_FILES["candidate_pdf"]["bytes"], "sha256": CANDIDATE_FILES["candidate_pdf"]["sha256"], "pages": 426, "admission_action": pdf_action},
        "transaction": {"preflight_fail_closed": True, "preimage_manifest": (PREIMAGE_ROOT / "PREIMAGE_MANIFEST.json").relative_to(LANE).as_posix(), "journal": JOURNAL_PATH.relative_to(LANE).as_posix(), "lock": LOCK_PATH.relative_to(LANE).as_posix(), "backend_manifest_written_last": True, "exact_rollback_on_failure": True, "deleted_paths": []},
        "canonical_source_mutated": True,
        "upstream_contact": False,
    }
    raw = canonical_json(receipt)
    if b"c:\\users\\" in raw.lower() or b"/users/" in raw.lower():
        raise GateError("boundary receipt contains an absolute local profile path")
    return raw


def preflight(*, allow_transaction_markers: bool = False) -> dict[str, Any]:
    if JOURNAL_PATH.exists() or PREIMAGE_ROOT.exists() or (LOCK_PATH.exists() and not allow_transaction_markers):
        raise GateError("B009 admission marker already exists; manual recovery is required")
    if BOUNDARY_RECEIPT_PATH.exists():
        raise GateError("B009 boundary receipt already exists; refusing a duplicate admission")
    candidate = verify_candidate_files()
    backend_config, staged = load_backend_binding()
    live_before, backend_identity = verify_b008_preimage()
    preimages = target_preimages()
    pdf_action = "created_from_candidate" if preimages[PROMOTED_PDF_PATH.relative_to(LANE).as_posix()]["state"] == "absent" else "verified_preexisting_exact"
    receipt = construct_receipt(backend_config, candidate, preimages, pdf_action)
    return {"candidate": candidate, "staged": staged, "backend_config": backend_config, "live_before": live_before, "backend_identity": backend_identity, "preimages": preimages, "pdf_action": pdf_action, "receipt": receipt}


def promote(context: dict[str, Any], authorization: object | None = None) -> None:
    # This function is reachable only through the explicit CLI --promote path.
    if authorization is not _PROMOTION_SECRET:
        raise PermissionError("promotion refused: missing explicit CLI authorization")
    _lock()
    written_backend: list[str] = []
    pdf_written = False
    receipt_written = False
    backup: dict[str, Any] | None = None
    try:
        # Re-run every read-only gate immediately before the first write.
        # The narrow lock is intentionally held while the final read-only
        # replay runs; allow that lock marker, but never allow a journal marker
        # to be bypassed.
        fresh = preflight(allow_transaction_markers=True)
        if fresh["receipt"] != context["receipt"]:
            raise GateError("preflight receipt changed before admission")
        if fresh["staged"] != context["staged"] or fresh["live_before"] != context["live_before"]:
            raise GateError("backend changed after preflight")
        backup = _preimage_backup(context["preimages"], context["live_before"])
        journal = {"$schema": "r011-b009-admission-transaction-journal/v1", "boundary_id": BOUNDARY_ID, "status": "in_progress_fail_closed", "preimage": backup, "candidate_pdf": CANDIDATE_FILES["candidate_pdf"], "backend_stage": compact_backend_binding(context["backend_config"]), "receipt_sha256": digest(context["receipt"]), "planned_backend_order": "all non-manifest payloads sorted, then manifest.json"}
        _write_atomic(JOURNAL_PATH, canonical_json(journal), create_only=True)
        for relative in sorted(path for path in context["staged"] if path != "manifest.json") + ["manifest.json"]:
            _write_atomic(LIVE_EXPORTS / relative, context["staged"][relative])
            written_backend.append(relative)
        candidate_pdf = context["candidate"]["candidate_pdf"]
        if context["pdf_action"] == "created_from_candidate":
            _write_atomic(PROMOTED_PDF_PATH, candidate_pdf, create_only=True)
            pdf_written = True
        for name, target_relative in OVERLAY_TARGETS.items():
            raw = context["candidate"]["assembled_answers"] if name == "assembled_answers" else context["candidate"][name]
            _write_atomic(lane_path(target_relative), raw)
        _write_atomic(BOUNDARY_RECEIPT_PATH, context["receipt"], create_only=True)
        receipt_written = True
        # Exact post-write checks; any mismatch enters rollback below.
        post_sha, post_count, post_bytes, post_payloads = inventory(LIVE_EXPORTS)
        expected_inventory = context["backend_config"]["inventory"]
        if post_payloads != context["staged"] or (post_sha, post_count, post_bytes) != (expected_inventory["sha256"], expected_inventory["file_count"], expected_inventory["bytes"]):
            raise GateError("post-admission backend readback differs from isolated stage")
        if PROMOTED_PDF_PATH.read_bytes() != candidate_pdf:
            raise GateError("post-admission PDF readback differs from candidate")
        # Keep a committed journal as durable rollback evidence.
        committed = json.loads(JOURNAL_PATH.read_text(encoding="utf-8"))
        committed["status"] = "committed_exact_post_admission_replay"
        committed["boundary_receipt"] = identity(context["receipt"], BOUNDARY_RECEIPT_PATH.relative_to(LANE).as_posix())
        _write_atomic(JOURNAL_PATH, canonical_json(committed))
        LOCK_PATH.unlink(missing_ok=True)
    except Exception as exc:
        # Best-effort exact rollback from the durable preimage files.  A failed
        # rollback deliberately leaves the journal/lock for manual recovery.
        errors: list[str] = []
        try:
            if receipt_written:
                BOUNDARY_RECEIPT_PATH.unlink(missing_ok=True)
            for relative in _rollback_order(written_backend):
                backup_path = PREIMAGE_ROOT / "backend" / relative
                destination = LIVE_EXPORTS / relative
                if backup_path.is_file():
                    _write_atomic(destination, backup_path.read_bytes())
                else:
                    destination.unlink(missing_ok=True)
            if pdf_written:
                PROMOTED_PDF_PATH.unlink(missing_ok=True)
            backup_records = (backup or {}).get("manifest", {}).get("files", {})
            for relative, record in backup_records.items():
                if relative == PROMOTED_PDF_PATH.relative_to(LANE).as_posix() or record["state"] == "absent":
                    continue
                backup_file = PREIMAGE_ROOT / record.get("backup", "")
                if backup_file.is_file():
                    _write_atomic(lane_path(relative), backup_file.read_bytes())
                else:
                    errors.append(f"missing durable source preimage: {relative}")
            try:
                verify_b008_preimage()
            except Exception as verify_exc:
                errors.append(f"B008 preimage verification after rollback: {verify_exc}")
            if JOURNAL_PATH.exists():
                journal = json.loads(JOURNAL_PATH.read_text(encoding="utf-8"))
                journal["status"] = "rolled_back_exact_but_manual_review_required"
                journal["error"] = str(exc)
                _write_atomic(JOURNAL_PATH, canonical_json(journal))
            LOCK_PATH.unlink(missing_ok=True)
        except Exception as rollback_exc:
            errors.append(str(rollback_exc))
        if errors:
            raise GateError(f"admission failed ({exc}); rollback also failed: {errors}") from exc
        raise GateError(f"admission failed; exact rollback attempted: {exc}") from exc


def verify_admitted() -> dict[str, Any]:
    if not BOUNDARY_RECEIPT_PATH.is_file() or not PROMOTED_PDF_PATH.is_file():
        raise GateError("B009 has not been admitted")
    receipt = json.loads(BOUNDARY_RECEIPT_PATH.read_text(encoding="utf-8"))
    if receipt.get("boundary_id") != BOUNDARY_ID or receipt.get("status") != "admitted_exact_pdf_source_assets_and_backend":
        raise GateError("B009 boundary receipt status is invalid")
    candidate = verify_candidate_files()
    backend_config, staged = load_backend_binding()
    # After admission the twelve canonical overlay targets are intentionally
    # B009 bytes, so the B008 preimage gate (used before mutation) cannot be
    # rerun against those paths.  Verify the immutable B008 lineage artifacts,
    # then bind each live overlay to the exact frozen candidate instead.
    for key in ("boundary_receipt", "pdf"):
        file_identity(B008_PREIMAGE[key]["path"], B008_PREIMAGE[key])
    receipt_base = receipt.get("base_preimage", {})
    if receipt_base.get("backend") != B008_PREIMAGE["backend"]:
        raise GateError("admission receipt no longer binds the exact B008 backend preimage")
    for name, target_relative in OVERLAY_TARGETS.items():
        raw = candidate["assembled_answers"] if name == "assembled_answers" else candidate[name]
        expected = {"bytes": len(raw), "sha256": digest(raw)}
        file_identity(target_relative, expected)
    sha, count, total, live = inventory(LIVE_EXPORTS)
    expected = backend_config["inventory"]
    if live != staged or (sha, count, total) != (expected["sha256"], expected["file_count"], expected["bytes"]):
        raise GateError("admitted live backend differs from isolated stage")
    if PROMOTED_PDF_PATH.read_bytes() != candidate["candidate_pdf"]:
        raise GateError("admitted B009 PDF differs from candidate")
    return {"boundary_id": BOUNDARY_ID, "status": "verified_admitted_exact", "pdf": identity(candidate["candidate_pdf"], PROMOTED_PDF_PATH.relative_to(LANE).as_posix()), "backend_inventory": expected, "mutation_performed": False}


def readiness_gaps() -> list[str]:
    gaps: list[str] = []
    if LOCK_PATH.exists():
        gaps.append("transaction.lock_present")
    if JOURNAL_PATH.exists():
        gaps.append("transaction.journal_present")
    if PREIMAGE_ROOT.exists():
        gaps.append("transaction.preimage_store_present")
    if BOUNDARY_RECEIPT_PATH.exists():
        gaps.append("admission.boundary_receipt_already_present")
    try:
        verify_candidate_files()
    except Exception as exc:
        gaps.append(f"candidate:{exc}")
    try:
        verify_b008_preimage()
    except Exception as exc:
        gaps.append(f"b008_preimage:{exc}")
    try:
        load_backend_binding()
    except Exception as exc:
        gaps.append(f"backend_binding:{exc}")
    try:
        target_preimages()
    except Exception as exc:
        gaps.append(f"target_preimage:{exc}")
    return sorted(set(gaps))


_PROMOTION_SECRET = object()


def _authorize(promote_requested: bool) -> object:
    if __name__ != "__main__" or not promote_requested:
        raise PermissionError("promotion requires an explicit CLI --promote invocation")
    return _PROMOTION_SECRET


def self_test() -> list[str]:
    failures: list[str] = []
    for unsafe in ("../escape", str(LANE.resolve()), "qa\\escape"):
        try:
            lane_path(unsafe)
            failures.append(f"unsafe path accepted: {unsafe}")
        except ValueError:
            pass
    if canonical_json({"b": 1, "a": "é"}) != canonical_json({"a": "é", "b": 1}):
        failures.append("canonical JSON ordering is unstable")
    if _rollback_order(["a", "manifest.json", "b"]) != ["b", "a", "manifest.json"]:
        failures.append("manifest is not restored last")
    try:
        _authorize(False)
        failures.append("promotion authorization bypassed")
    except PermissionError:
        pass
    try:
        promote({}, authorization=None)
        failures.append("promotion function accepted missing authorization")
    except PermissionError:
        pass
    if len(FIGURE_CANDIDATES) != 9 or len(FIGURE_NAMES) != 8:
        failures.append("localized figure binding count is not eight plus swing")
    for name, expected in CANDIDATE_FILES.items():
        if not re.fullmatch(r"[0-9a-f]{64}", expected["sha256"]):
            failures.append(f"invalid candidate digest: {name}")
    return failures


def output(value: dict[str, Any]) -> None:
    print(canonical_json(value).decode("utf-8").rstrip("\n"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--check-readiness", action="store_true", help="read-only list of unresolved admission gates")
    modes.add_argument("--self-test", action="store_true", help="run pure helper tests")
    modes.add_argument("--verify-admitted", action="store_true", help="read-only post-admission verification")
    modes.add_argument("--promote", action="store_true", help="perform guarded admission; explicit mutation")
    args = parser.parse_args()
    if args.self_test:
        failures = self_test()
        output({"boundary_id": BOUNDARY_ID, "status": "passed" if not failures else "failed", "errors": failures, "mutation_performed": False})
        return 0 if not failures else 1
    if args.verify_admitted:
        try:
            output(verify_admitted())
            return 0
        except Exception as exc:
            output({"boundary_id": BOUNDARY_ID, "status": "not_verified", "errors": [str(exc)], "mutation_performed": False})
            return 1
    if not args.promote:
        gaps = readiness_gaps()
        output({"boundary_id": BOUNDARY_ID, "status": "ready_for_guarded_admission" if not gaps else "blocked_fail_closed", "errors": gaps, "backend_binding_config": BACKEND_BINDING_CONFIG.relative_to(LANE).as_posix(), "candidate_pdf": CANDIDATE_FILES["candidate_pdf"], "localized_figure_count": 9, "mutation_performed": False})
        return 0 if not gaps else 2
    try:
        authorization = _authorize(True)
        context = preflight()
        promote(context, authorization=authorization)
        output({"boundary_id": BOUNDARY_ID, "status": "admitted_exact_post_admission_replay", "boundary_receipt": BOUNDARY_RECEIPT_PATH.relative_to(LANE).as_posix(), "journal": JOURNAL_PATH.relative_to(LANE).as_posix(), "mutation_performed": True})
        return 0
    except Exception as exc:
        output({"boundary_id": BOUNDARY_ID, "status": "promotion_failed_closed", "errors": [str(exc)], "mutation_performed": False})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
