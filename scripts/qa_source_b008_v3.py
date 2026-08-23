from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


sys.dont_write_bytecode = True
import qa_source_b008_v2 as v2


LANE = Path(__file__).resolve().parents[1]
REPO = LANE / "repo"
OUT = LANE / "qa" / "b008-source"

V2_SCRIPT = LANE / "scripts" / "qa_source_b008_v2.py"
V2_MANIFEST = OUT / "R011-B008_SOURCE_MANIFEST_V2.tsv"
V2_QA = OUT / "R011-B008_SOURCE_QA_V2.json"
V2_PDF = LANE / "qa" / "b008-build" / "final-v2" / "main.pdf"
V2_BUILD_RECEIPT = (
    LANE / "qa" / "b008-build" / "final-v2" / "CANDIDATE_BUILD_QA_V2.json"
)
V2_BUILD_VISUAL = LANE / "qa" / "b008-build" / "BUILD_ONLY_VISUAL_SANITY_V2.json"
V2_ROOT_VISUAL = LANE / "qa" / "b008-visual" / "ROOT_VISUAL_FINDINGS_V2.json"
REPAIR_RECEIPT = OUT / "R011-B008_V2_LAYOUT_REPAIR_RECEIPT.json"

V3_MANIFEST = OUT / "R011-B008_SOURCE_MANIFEST_V3.tsv"
V3_QA = OUT / "R011-B008_SOURCE_QA_V3.json"

PINNED = {
    V2_SCRIPT: (
        27_969,
        "ec3423eefc3e5ae2c33123c7819291777b7cdb5de55dc0465faf21d446dc46f3",
    ),
    V2_MANIFEST: (
        175_582,
        "67aa27af504aa442cf4f80be20ba2c2c7c37530049125c40b00f627f9f8c7dc1",
    ),
    V2_QA: (
        6_411,
        "8d7ff2dc438d27474ce6395bd354d6139bf983a4c360131a109165df421116d5",
    ),
    V2_PDF: (
        22_017_323,
        "8e6d91a813206f7672fbed1736bed97f7eb48e3adc56f690fb696b7daa0ea9ef",
    ),
    V2_BUILD_RECEIPT: (
        17_149,
        "f79462b733817eb13b70616a5f8f347a599e959c4c532a0eca0aa9ca5f0d7a5b",
    ),
    V2_BUILD_VISUAL: (
        2_257,
        "d395b51cb587048fdea11489e10c37095b2fedeb681757c850e78d58888bb092",
    ),
    V2_ROOT_VISUAL: (
        2_231,
        "0975aeade7f4563cb32eec8865f9b08e3e7f6598bc92e15b20541ccf328971da",
    ),
    REPAIR_RECEIPT: (
        2_506,
        "c3c57c19067667e99f8db485274b3834ae56ce66930384f7a4430bfe86286a8f",
    ),
}

REVIEW_REL = "ch_summarizing_data/TeX/review_exercises.tex"
V2_REVIEW = (
    9_331,
    "b5a3d928255c6cc20010d2227eaffeb1a15e5f50cd35f689a69c2e633c423f06",
)
V3_REVIEW = (
    9_363,
    "91f393cf22afbace8f80626d50558809acc283417805e7aa814aecb2b0d32ae3",
)

TOP_V2 = (
    b"\\newpage\n"
    b"\\item Bandingkan distribusi waktu maraton pria dan wanita berdasarkan diagram\n"
)
TOP_V3 = (
    b"\\newpage\n"
    b"\\vspace*{\\fill}\n"
    b"\\item Bandingkan distribusi waktu maraton pria dan wanita berdasarkan diagram\n"
)
GENDER_V2 = (
    b"]{0.56}{eoce/marathon_winners}{marathon_winners_gender_box}"
)
GENDER_V3 = (
    b"]{0.90}{eoce/marathon_winners}{marathon_winners_gender_box}"
)
TIME_V2 = (
    b"]{0.75}{eoce/marathon_winners}{marathon_winners_time_series} \\\\"
)
TIME_V3 = (
    b"]{0.95}{eoce/marathon_winners}{marathon_winners_time_series} \\\\"
)
BOTTOM_V2_WITH_V3_WIDTH = (
    TIME_V3 + b"\n\\end{center}\n}{}\n"
)
BOTTOM_V3 = (
    TIME_V3 + b"\n\\end{center}\n\\vspace*{\\fill}\n}{}\n"
)


def replace_once(data: bytes, old: bytes, new: bytes, label: str) -> bytes:
    count = data.count(old)
    if count != 1:
        raise RuntimeError(f"{label} exact occurrence count is {count}, expected 1")
    return data.replace(old, new, 1)


def reverse_review(live: bytes) -> bytes:
    value = replace_once(live, TOP_V3, TOP_V2, "top page-fill insertion")
    value = replace_once(value, GENDER_V3, GENDER_V2, "gender-box width repair")
    value = replace_once(value, BOTTOM_V3, BOTTOM_V2_WITH_V3_WIDTH, "bottom page-fill insertion")
    return replace_once(value, TIME_V3, TIME_V2, "time-series width repair")


def forward_review(v2_bytes: bytes) -> bytes:
    value = replace_once(v2_bytes, TOP_V2, TOP_V3, "top page-fill forward replay")
    value = replace_once(value, GENDER_V2, GENDER_V3, "gender-box width forward replay")
    value = replace_once(value, TIME_V2, TIME_V3, "time-series width forward replay")
    return replace_once(
        value,
        BOTTOM_V2_WITH_V3_WIDTH,
        BOTTOM_V3,
        "bottom page-fill forward replay",
    )


def validate_v2_evidence(v2_rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if len(v2_rows) != 1_206:
        raise RuntimeError("V2 source manifest is not the exact 1,206-file closure")
    if v2_rows.get(REVIEW_REL) != {
        "bytes": V2_REVIEW[0],
        "sha256": V2_REVIEW[1],
    }:
        raise RuntimeError("V2 review identity is not exact")

    qa = v2.load_json(V2_QA)
    closure = qa.get("source_closure") or {}
    checks = qa.get("checks") or {}
    immutable_v1 = qa.get("immutable_v1_evidence") or {}
    exact_reconstruction = qa.get("exact_reconstruction") or {}
    if (
        qa.get("$schema") != "r011-b008-source-qa/v2"
        or qa.get("boundary_id") != "R011-B008"
        or qa.get("status") != "PASS_REPAIRED_SOURCE_CLOSURE"
        or checks.get("failed") != 0
        or checks.get("blockers") != []
        or closure.get("files") != 1_206
        or closure.get("changed_files")
        != ["ch_summarizing_data/TeX/review_exercises.tex", "eoce.bib"]
        or (closure.get("manifest") or {}).get("sha256") != PINNED[V2_MANIFEST][1]
        or immutable_v1.get("verified_terminal_pass") is not True
        or exact_reconstruction.get("both_v1_preimages_reconstructed_exactly") is not True
        or exact_reconstruction.get("both_v2_postimages_forward_replayed_exactly") is not True
    ):
        raise RuntimeError("V2 source QA is not the exact terminal PASS evidence")
    return qa


def validate_rejected_v2_evidence() -> dict[str, Any]:
    build = v2.load_json(V2_BUILD_RECEIPT)
    build_visual = v2.load_json(V2_BUILD_VISUAL)
    root_visual = v2.load_json(V2_ROOT_VISUAL)
    pdf_record = {
        "path": "qa/b008-build/final-v2/main.pdf",
        "bytes": PINNED[V2_PDF][0],
        "sha256": PINNED[V2_PDF][1],
    }
    build_receipt_record = {
        "path": "qa/b008-build/final-v2/CANDIDATE_BUILD_QA_V2.json",
        "bytes": PINNED[V2_BUILD_RECEIPT][0],
        "sha256": PINNED[V2_BUILD_RECEIPT][1],
    }
    if (
        build.get("schema") != "openintro-boundary-build-candidate-qa"
        or build.get("schema_version") != "0.4.0"
        or build.get("boundary_id") != "R011-B008"
        or build.get("candidate_iteration") != "V2"
        or build.get("status") != "pending_visual_review"
        or build.get("nonvisual_status") != "passed"
        or build.get("errors") != []
        or build.get("candidate_artifact")
        != {**pdf_record, "promoted": False}
        or (build.get("determinism") or {}).get("byte_identical") is not True
    ):
        raise RuntimeError("V2 build receipt is not the exact rejected candidate evidence")
    source_gate = (
        ((build.get("source_closure") or {}).get("independent_v2_source_gate"))
        or {}
    )
    if (
        source_gate.get("source_manifest")
        != {
            "path": "qa/b008-source/R011-B008_SOURCE_MANIFEST_V2.tsv",
            "bytes": PINNED[V2_MANIFEST][0],
            "sha256": PINNED[V2_MANIFEST][1],
        }
        or source_gate.get("source_qa")
        != {
            "path": "qa/b008-source/R011-B008_SOURCE_QA_V2.json",
            "bytes": PINNED[V2_QA][0],
            "sha256": PINNED[V2_QA][1],
        }
    ):
        raise RuntimeError("V2 build does not bind the exact V2 source gate")
    if (
        build_visual.get("$schema") != "r011-b008-build-only-visual-sanity/v2"
        or build_visual.get("candidate_pdf") != pdf_record
        or build_visual.get("candidate_build_receipt") != build_receipt_record
        or build_visual.get("promotion_or_admission_performed") is not False
        or build_visual.get("repo_or_output_mutated") is not False
        or ((build_visual.get("remaining_judgment") or {}).get("page")) != 80
    ):
        raise RuntimeError("build-only V2 visual finding is not exact")
    if (
        root_visual.get("$schema") != "r011-b008-root-visual-findings/v2"
        or root_visual.get("boundary_id") != "R011-B008"
        or (root_visual.get("candidate") or {}).get("sha256") != pdf_record["sha256"]
        or (root_visual.get("severity_counts") or {}).get("P2") != 1
        or root_visual.get("verdict") != "REJECTED_LAYOUT_ONLY"
        or root_visual.get("promotion_authorized") is not False
        or root_visual.get("admission_authorized") is not False
    ):
        raise RuntimeError("root V2 visual rejection is not exact")
    return {
        "candidate_pdf": v2.identity(V2_PDF),
        "build_receipt": v2.identity(V2_BUILD_RECEIPT),
        "build_visual_findings": v2.identity(V2_BUILD_VISUAL),
        "root_visual_findings": v2.identity(V2_ROOT_VISUAL),
        "nonvisual_build_passed": True,
        "visual_verdict": "REJECTED_LAYOUT_ONLY",
        "remaining_finding": "R011-B008-V2-P2-001",
    }


def validate_repair_receipt() -> dict[str, Any]:
    repair = v2.load_json(REPAIR_RECEIPT)
    item = repair.get("repair") or {}
    scope = repair.get("scope") or {}
    rejected = repair.get("rejected_candidate") or {}
    if (
        repair.get("$schema") != "r011-b008-v2-layout-repair-receipt/v1"
        or repair.get("boundary_id") != "R011-B008"
        or repair.get("status") != "APPLIED_BOUNDED_PAGE_FILL_REPAIR"
        or item.get("id") != "R011-B008-REPAIR-003"
        or item.get("target") != "repo/" + REVIEW_REL
        or item.get("kind") != "page_fill_and_vertical_centering_only"
        or item.get("preimage")
        != {"bytes": V2_REVIEW[0], "sha256": V2_REVIEW[1]}
        or item.get("postimage")
        != {"bytes": V3_REVIEW[0], "sha256": V3_REVIEW[1]}
        or len(item.get("exact_changes") or []) != 4
        or item.get(
            "instructional_content_order_mathematics_labels_alt_text_and_asset_paths_unchanged"
        )
        is not True
        or item.get("asset_bytes_changed") is not False
        or scope.get("files_changed") != 1
        or scope.get("reader_visible_translation_changed") is not False
        or scope.get("answers_changed") is not False
        or scope.get("exercise_or_answer_relations_changed") is not False
        or scope.get("restricted_solution_content_added") is not False
        or scope.get("canonical_pdf_or_backend_promoted") is not False
        or (rejected.get("sha256")) != PINNED[V2_PDF][1]
    ):
        raise RuntimeError("V2-to-V3 repair receipt assertions failed")
    return repair


def validate_live_review(v2_bytes: bytes, live: bytes) -> dict[str, Any]:
    v2.require_identity(REPO / REVIEW_REL, V3_REVIEW)
    reconstructed = reverse_review(live)
    if (len(reconstructed), v2.sha256_bytes(reconstructed)) != V2_REVIEW:
        raise RuntimeError("V3 review does not reverse to the exact V2 identity")
    if reconstructed != v2_bytes:
        raise RuntimeError("V3 reverse bytes differ from the exact V2 manifest witness")
    if forward_review(v2_bytes) != live:
        raise RuntimeError("V2 review does not forward-replay to the exact V3 bytes")

    text = live.decode("utf-8")
    labels = re.findall(r"\\label\{([^}]+)\}", text)
    markers = [int(value) for value in re.findall(r"(?m)^% (\d+)$", text)]
    if (
        labels != v2.EXPECTED_LABELS
        or markers != list(range(27, 35))
        or text.count("\\eoce{") != 8
        or text.count("}{}") != 8
        or text.splitlines()[0] != v2.HEADER.decode("ascii")
    ):
        raise RuntimeError("V3 exercise topology or B007 header guard changed")
    if text.count("\\vspace*{\\fill}") != 2:
        raise RuntimeError("V3 review does not contain exactly two page-fill commands")
    if GENDER_V3.decode("ascii") not in text or TIME_V3.decode("ascii") not in text:
        raise RuntimeError("V3 reader-visible figure widths are not exact")
    if GENDER_V2.decode("ascii") in text or TIME_V2.decode("ascii") in text:
        raise RuntimeError("superseded V2 reader-visible figure widths remain")
    return {
        "v2_preimage": {
            "bytes": len(v2_bytes),
            "sha256": v2.sha256_bytes(v2_bytes),
        },
        "v3_postimage": {
            "bytes": len(live),
            "sha256": v2.sha256_bytes(live),
        },
        "reverse_exact": True,
        "forward_replay_exact": True,
        "exact_changes": [
            "top vspace fill inserted around the page-80 block",
            "gender-box width 0.56 to 0.90",
            "time-series width 0.75 to 0.95",
            "bottom vspace fill inserted around the page-80 block",
        ],
        "instructional_content_order_mathematics_labels_alt_text_and_asset_paths_unchanged": True,
    }


def build_evidence() -> tuple[bytes, bytes, dict[str, Any]]:
    inputs = [v2.require_identity(path, expected) for path, expected in PINNED.items()]
    v2_rows = v2.parse_manifest(V2_MANIFEST)
    v2_qa = validate_v2_evidence(v2_rows)
    rejected_v2 = validate_rejected_v2_evidence()
    validate_repair_receipt()

    actual = v2.scan_repo()
    if set(actual) != set(v2_rows):
        missing = sorted(set(v2_rows) - set(actual))[:10]
        extra = sorted(set(actual) - set(v2_rows))[:10]
        raise RuntimeError(
            f"V3 repository path set differs from V2; missing={missing}, extra={extra}"
        )
    changed = [path for path in sorted(v2_rows) if actual[path] != v2_rows[path]]
    if changed != [REVIEW_REL]:
        raise RuntimeError(f"live V3 delta is not exactly review_exercises.tex: {changed}")
    if actual[REVIEW_REL] != {"bytes": V3_REVIEW[0], "sha256": V3_REVIEW[1]}:
        raise RuntimeError("live V3 review postimage identity differs")

    v2_review = (
        LANE
        / "qa"
        / "b008-build"
        / "source-snapshot-v2"
        / REVIEW_REL
    ).read_bytes()
    if (len(v2_review), v2.sha256_bytes(v2_review)) != V2_REVIEW:
        raise RuntimeError("V2 build snapshot review witness is not exact")
    review = validate_live_review(v2_review, (REPO / REVIEW_REL).read_bytes())
    inherited = v2.validate_inherited_semantics(v2_rows, actual)

    manifest = v2.manifest_bytes(actual)
    manifest_record = {
        "path": V3_MANIFEST.relative_to(LANE).as_posix(),
        "bytes": len(manifest),
        "sha256": v2.sha256_bytes(manifest),
    }
    qa_value = {
        "$schema": "r011-b008-source-qa/v3",
        "boundary_id": "R011-B008",
        "status": "PASS_PAGE_FILL_REPAIRED_SOURCE_CLOSURE",
        "authority": v2_qa["authority"],
        "gate_script": v2.identity(Path(__file__).resolve()),
        "immutable_v2_evidence": {
            "manifest": v2.identity(V2_MANIFEST),
            "source_qa": v2.identity(V2_QA),
            "verified_terminal_pass": True,
            "files": 1_206,
        },
        "rejected_v2_candidate": rejected_v2,
        "repair_authority": {
            "receipt": v2.identity(REPAIR_RECEIPT),
            "repair_id": "R011-B008-REPAIR-003",
            "scope_exact": True,
        },
        "source_closure": {
            "base": "R011-B008 source QA V2",
            "files": 1_206,
            "changed_files": [REVIEW_REL],
            "added_files": 0,
            "removed_files": 0,
            "unexpected_files": 0,
            "unchanged_files_exact": 1_205,
            "manifest": manifest_record,
        },
        "exact_reconstruction": {
            REVIEW_REL: review,
            "v2_preimage_reconstructed_exactly": True,
            "v3_postimage_forward_replayed_exactly": True,
        },
        "inherited_checks_reperformed": inherited,
        "scope": {
            "exercises": list(range(27, 35)),
            "public_answers": v2.EXPECTED_ANSWER_MARKERS,
            "o001_gaps": v2.EXPECTED_O001_GAPS,
            "reader_visible_translation_changed": False,
            "assets_changed": 0,
            "answers_changed": 0,
            "exercise_or_answer_relations_changed": 0,
            "restricted_solution_content_added": False,
            "canonical_pdf_backend_output_release_mutated": False,
        },
        "input_identities": inputs,
        "checks": {"passed": 30, "failed": 0, "blockers": []},
        "pending": [
            "deterministic V3 whole-book build",
            "full-resolution inspection of pages 78-82 and 388-391",
        ],
        "write_boundary": [
            "scripts/qa_source_b008_v3.py",
            "qa/b008-source/R011-B008_SOURCE_MANIFEST_V3.tsv",
            "qa/b008-source/R011-B008_SOURCE_QA_V3.json",
        ],
    }
    qa_bytes = v2.canonical_json(qa_value)
    summary = {
        "status": qa_value["status"],
        "manifest_files": len(actual),
        "manifest_bytes": len(manifest),
        "manifest_sha256": v2.sha256_bytes(manifest),
        "receipt_bytes": len(qa_bytes),
        "receipt_sha256": v2.sha256_bytes(qa_bytes),
        "live_delta_files": 1,
        "v2_preimages_reconstructed": 1,
        "blockers": [],
    }
    return manifest, qa_bytes, summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Deterministic R011-B008 V3 page-fill source closure gate"
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="write only absent or already byte-identical V3 evidence",
    )
    args = parser.parse_args()
    manifest, receipt, summary = build_evidence()
    if args.write:
        v2.atomic_write_exact(V3_MANIFEST, manifest)
        v2.atomic_write_exact(V3_QA, receipt)
        if V3_MANIFEST.read_bytes() != manifest or V3_QA.read_bytes() != receipt:
            raise RuntimeError("V3 evidence write readback failed")
        summary["mode"] = "write_and_readback"
    else:
        if not V3_MANIFEST.is_file() or not V3_QA.is_file():
            raise RuntimeError("read-only replay requires existing V3 evidence")
        if V3_MANIFEST.read_bytes() != manifest or V3_QA.read_bytes() != receipt:
            raise RuntimeError("V3 source evidence replay is not byte-identical")
        summary["mode"] = "read_only_replay"
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
