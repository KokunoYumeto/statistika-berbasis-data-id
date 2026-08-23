#!/usr/bin/env python3
"""Finalize accepted R011-B007 v8 build/visual QA without promotion.

The compiled candidate artifacts remain immutable. This deterministic gate
binds the completed full-resolution Poppler/MuPDF inspection, writes the visual
audit, and changes the immutable-build candidate receipt from pending to
accepted. With no arguments it is a read-only exact replay.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from pypdf import PdfReader


LANE = Path(__file__).resolve().parents[1]
QA = LANE / "qa"
BUILD_DRIVER = LANE / "scripts" / "qa_build_b007.py"
CANDIDATE_RECEIPT = QA / "b007-build" / "final-v8" / "CANDIDATE_BUILD_QA_V8.json"
PDF = QA / "b007-build" / "final-v8" / "main.pdf"
PASS3_PDF = QA / "b007-build" / "final-v8" / "main-pass3.pdf"
TEXT = QA / "b007-build" / "final-v8" / "main-final.txt"
RENDER = QA / "b007-render" / "final-v8"
RENDER_MANIFEST = RENDER / "FINAL_MANIFEST.tsv"
PAGE_LOCATOR = RENDER / "PAGE_LOCATOR.json"
CONTACT_SHEET = RENDER / "CONTACT_SHEET.png"
MUPDF_RENDER = QA / "b007-render" / "final-v8-mupdf"
VISUAL_AUDIT = QA / "R011-B007_VISUAL_AUDIT.json"

BOUNDARY_ID = "R011-B007"
INSPECTED_PAGES = [
    1, 2, 4, 5, 6, 46, 47, 53, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80,
    81, 82, 388, 389, 390,
]
MUPDF_PAGES = list(range(72, 83))
MODEL_LINE = "OpenAI Codex gpt-5.6-sol, Ultra"

EXPECTED = {
    "build_driver": {"bytes": 21307, "sha256": "43991ce4dcd0e45bf488645e4f5b1d7be32703a1966fdacf16df02316cef14c1"},
    "candidate_receipt": {"bytes": 18531, "sha256": "1f1aab5da5646adbc53aec9178266f8c59575634a4a1a9d9e1547fbb757bf403"},
    "pdf": {"bytes": 22017185, "sha256": "ca872ddbc2fb1cab5f6cdb2fe745a0711a315fef68ab2e72c7a11d1c633a5c1a"},
    "text": {"bytes": 1583120, "sha256": "c1b6d1d777b3b89d7a70afa00f0429ce4e7a0b8e9bfbdd8ec17c87d84a564336"},
    "render_manifest": {"bytes": 2019, "sha256": "895e6ff19e786153ae03cc9397f21bb3629beece560d727c35af29887d5c9748"},
    "page_locator": {"bytes": 1503, "sha256": "80ba13a304b6db2384aa4f60718f710677ab396aea5d24ba8a766fb91d628e4b"},
    "contact_sheet": {"bytes": 961888, "sha256": "a088b211a037684ba5cfab6eb237b0cdc6343d5ee646ca078b14c7c871d4a95a"},
    "source_manifest": {"bytes": 27428, "sha256": "7f8943fc8d02e4f9502f9235fcb0160b9326261e8faf0b8099d8138595277496"},
    "source_receipt": {"bytes": 26533, "sha256": "1b0429aa37617e021fb77d1ede777347dbb5df24cba79ebda60da521d3ee3187"},
    "source_gate": {"bytes": 3370, "sha256": "677921acb28e9da034c4c40fc78a7367162ceaf1d986a8bdb0f29977aa237294"},
    "snapshot_manifest": {"bytes": 174617, "sha256": "a09e47b52b7b8d5eada0d9086777dcfd57b71339897b9ff0769c6d43fbb0b4c4"},
    "readme": {"bytes": 3830, "sha256": "98e0df40bfd28aec008cc90d7f8da724cf7de3710e2ba1610221476f6fa6b8d2"},
    "citation": {"bytes": 1136, "sha256": "9d500aaffbe4039e34a02a3a3eb8246df25b1b80f9fad139294d1b30505df0f0"},
    "asset_machine": {"bytes": 36911, "sha256": "3342c3e07c38e75c8334ddba4e89357cb960987b3e8727f1374c04fe6c25ed72"},
    "asset_visual": {"bytes": 13578, "sha256": "2395920ffeaba82dcca96ec78b329be040ba7affb8991159e395e81cae0f3039"},
    "asset_promotion": {"bytes": 19032, "sha256": "5594452b1fca3bed7b8f4b97ee0c33af67dfd1f18aff7458c9512a66c85d6ae1"},
}

MUPDF_EXPECTED = {
    72: (262916, "2e94fe882526dde03708d796640b2031abae0dee4e8ef19dc06a0e82b124155b"),
    73: (376012, "eb30ce1aed5d623c172c443194d67c03e63ecd5499000f3dc54c3ac61ad48b9d"),
    74: (260930, "398083d60802699df7e8998339f16a7a2696d0d3f6710831d8c1a3b8815eedb9"),
    75: (313543, "ff7b9305f09a572d6c8a86d5520f21d273806f3afbb37c9d8728c1566de2df43"),
    76: (418011, "d2237ad6c44351ab9137bbbc6b5c7a0c7caaeacec31f4110ab3981fde995576c"),
    77: (336410, "f4616ce808934b5d17fcb566485ef455e566e1f1b432ab8dcfc861d95aa2324c"),
    78: (308089, "5f28b49b03010843f6cbf17c1f253d23d410d252aa588e5c92c76b0c2cf31cba"),
    79: (219613, "efe5b854d933e15ec4f96a07cb29eac08292558b4c9921ae088013734134060d"),
    80: (36544, "066d6b40d2a4a3f05dc901ede86d17fbcebff1f582d8511ecc1843b1a9647ce6"),
    81: (65536, "7812f2b1fb2fb79315802104a1d7c2106df98dc185280b1c7f098ba64af3e2db"),
    82: (102504, "780c04912d3bb8db120e81f9bab526190c998e20c76b0d9889b294388bf6668a"),
}

SOURCE_IDENTITIES = {
    "repo/main.tex": (5540, "dd47b5c534a2f7b88222b7070c96757f1558cd9529b09802d1fdd28222cc15a0"),
    "repo/extraTeX/preamble/preface.tex": (10078, "5c1c7811bb067ff7d3c0a3eb50c3a8d9e141c832ec7013220378159ce4a0561d"),
    "repo/ch_summarizing_data/TeX/ch_summarizing_data.tex": (114861, "d549dce194bb297bfd04ee506b16919f8b5e7f30752e0e06f0e0cca4a579c355"),
    "repo/ch_summarizing_data/TeX/case_study_malaria_vaccine.tex": (9638, "4e5fc10a9b8e95ef020ee4ac1b61fd818c2c3a7be172fe219c646fb1e9f3af03"),
    "repo/ch_summarizing_data/TeX/review_exercises.tex": (8339, "3686a42c9a0cfefe7ef02d3846fd66c0c67a54a2aa5602e850076e681c6b48b7"),
    "repo/extraTeX/eoceSolutions/eoceSolutions.tex": (108017, "e3592306335188d90603dd26ac52fa39c2f86ef32d4baf2db81c65c3f42f8c33"),
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def identity_bytes(data: bytes) -> dict[str, object]:
    return {"bytes": len(data), "sha256": sha256_bytes(data)}


def identity(path: Path) -> dict[str, object]:
    return identity_bytes(path.read_bytes())


def rel(path: Path) -> str:
    return str(path.relative_to(LANE)).replace("\\", "/")


def canonical_json(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def require_identity(path: Path, expected: dict[str, object], label: str) -> None:
    if not path.is_file() or identity(path) != expected:
        raise RuntimeError(f"{label} identity differs from accepted v8 evidence")


def bound(path: Path, key: str) -> dict[str, object]:
    require_identity(path, EXPECTED[key], key)
    return {"path": rel(path), **EXPECTED[key]}


def privacy_zero(data: bytes, label: str) -> None:
    folded = data.lower()
    prohibited = bytes([102, 108, 111, 114, 105, 115])
    profile_backslash = bytes([99, 58, 92, 117, 115, 101, 114, 115, 92])
    profile_slash = bytes([99, 58, 47, 117, 115, 101, 114, 115, 47])
    if prohibited in folded or profile_backslash in folded or profile_slash in folded:
        raise RuntimeError(f"privacy scan failed for {label}")


def parse_poppler_images() -> list[dict[str, object]]:
    bound(RENDER_MANIFEST, "render_manifest")
    records: list[dict[str, object]] = []
    pages: list[int] = []
    for line_number, line in enumerate(RENDER_MANIFEST.read_text(encoding="utf-8").splitlines(), 1):
        parts = line.split("\t")
        if len(parts) != 4:
            raise RuntimeError(f"invalid render manifest row {line_number}")
        page = int(parts[0])
        expected = {"bytes": int(parts[2]), "sha256": parts[3]}
        image = RENDER / parts[1]
        if parts[1] != f"page-{page:03d}.png":
            raise RuntimeError(f"render filename mismatch at row {line_number}")
        require_identity(image, expected, f"Poppler page {page}")
        pages.append(page)
        records.append({"page": page, "path": rel(image), **expected})
    if pages != INSPECTED_PAGES:
        raise RuntimeError("Poppler render page set/order differs")
    return records


def parse_mupdf_images() -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for page in MUPDF_PAGES:
        size, digest = MUPDF_EXPECTED[page]
        expected = {"bytes": size, "sha256": digest}
        image = MUPDF_RENDER / f"page-{page:03d}.png"
        require_identity(image, expected, f"MuPDF page {page}")
        records.append({"page": page, "path": rel(image), **expected})
    return records


def candidate_preimage(current: dict[str, Any]) -> dict[str, Any]:
    if current.get("status") == "pending_visual_review":
        return current
    if current.get("status") != "accepted":
        raise RuntimeError("candidate receipt has an unsupported status")
    base = copy.deepcopy(current)
    base["status"] = "pending_visual_review"
    base["pending"] = ["operator inspection of every full-resolution candidate PNG"]
    base.pop("candidate_history", None)
    base.pop("finalization_script", None)
    base.pop("build_visual_acceptance", None)
    base.pop("privacy_final", None)
    visual = base["visual_evidence"]
    visual["status"] = "pending_operator_inspection"
    visual["claim"] = "no visual PASS is asserted by this automated gate"
    visual["required_next_action"] = "inspect every individual candidate PNG at full resolution"
    visual.pop("visual_audit", None)
    visual.pop("operator_inspection", None)
    base["write_boundary"] = "qa/b007-build, qa/b007-render, and the B007 candidate receipt only; no repo/output/backend/publication mutation"
    return base


def require_candidate() -> tuple[dict[str, Any], list[dict[str, object]], list[dict[str, object]]]:
    bound(BUILD_DRIVER, "build_driver")
    bound(PDF, "pdf")
    bound(PASS3_PDF, "pdf")
    bound(TEXT, "text")
    bound(PAGE_LOCATOR, "page_locator")
    bound(CONTACT_SHEET, "contact_sheet")
    bound(QA / "R011-B007_SOURCE_APPLICATION_MANIFEST.json", "source_manifest")
    bound(QA / "R011-B007_SOURCE_APPLICATION_RECEIPT.json", "source_receipt")
    bound(QA / "R011-B007_SOURCE_GATE_QA.json", "source_gate")
    bound(QA / "b007-build" / "R011-B007_SNAPSHOT_MANIFEST_V8.tsv", "snapshot_manifest")
    bound(LANE / "README.md", "readme")
    bound(LANE / "CITATION.cff", "citation")
    bound(QA / "b007-assets" / "B007_ASSET_MACHINE_QA.json", "asset_machine")
    bound(QA / "b007-assets" / "B007_ASSET_VISUAL_QA.json", "asset_visual")
    bound(QA / "b007-assets" / "B007_CANONICAL_PROMOTION_RECEIPT.json", "asset_promotion")
    for path_text, (size, digest) in SOURCE_IDENTITIES.items():
        require_identity(LANE / path_text, {"bytes": size, "sha256": digest}, path_text)

    candidate_current_raw = CANDIDATE_RECEIPT.read_bytes()
    candidate_current = json.loads(candidate_current_raw.decode("utf-8"))
    candidate = candidate_preimage(candidate_current)
    if identity_bytes(canonical_json(candidate)) != EXPECTED["candidate_receipt"]:
        raise RuntimeError("candidate pending preimage cannot be reconstructed exactly")
    if (
        candidate.get("schema") != "openintro-boundary-build-candidate-qa"
        or candidate.get("schema_version") != "0.2.0"
        or candidate.get("boundary_id") != BOUNDARY_ID
        or candidate.get("status") != "pending_visual_review"
        or candidate.get("nonvisual_status") != "passed"
        or candidate.get("errors") != []
        or candidate.get("determinism", {}).get("byte_identical") is not True
        or candidate.get("links_and_structure", {}).get("page_count") != 425
        or candidate.get("links_and_structure", {}).get("missing_link_targets") != 0
        or candidate.get("links_and_structure", {}).get("document_language") != "id-ID"
        or candidate.get("visual_evidence", {}).get("candidate_pages") != INSPECTED_PAGES
        or candidate.get("visual_evidence", {}).get("render_diagnostics", {}).get("unexpected_diagnostic_count") != 0
        or candidate.get("source_closure", {}).get("status") != "passed"
    ):
        raise RuntimeError("candidate receipt is not the exact accepted pending v8 candidate")
    if candidate.get("candidate_artifact") != {"path": rel(PDF), **EXPECTED["pdf"], "promoted": False}:
        raise RuntimeError("candidate artifact binding differs")

    locator = json.loads(PAGE_LOCATOR.read_text(encoding="utf-8"))
    if (
        locator.get("all_candidate_pages") != INSPECTED_PAGES
        or locator.get("localized_edition_scope") != "Bab 1 dan Bagian 2.1–2.3"
        or locator.get("section_2_3_content_span") != [72, 80]
        or locator.get("exercise_2_25_hits") != [76]
        or locator.get("exercise_2_26_hits") != [77]
        or locator.get("public_answer_2_25_hits") != [389]
        or locator.get("prohibited_reader_visible_token_hits") != []
    ):
        raise RuntimeError("page locator differs from terminal v8 scope")

    reader = PdfReader(PDF, strict=True)
    if len(reader.pages) != 425 or reader.is_encrypted:
        raise RuntimeError("terminal v8 page count/encryption differs")
    if reader.metadata.get("/Title") != "Statistika Berbasis Data":
        raise RuntimeError("terminal v8 title differs")
    if reader.trailer["/Root"].get("/Lang") != "id-ID":
        raise RuntimeError("terminal v8 language differs")

    readme = (LANE / "README.md").read_text(encoding="utf-8")
    citation = (LANE / "CITATION.cff").read_text(encoding="utf-8")
    if readme.count(MODEL_LINE) != 1 or citation.count(MODEL_LINE) != 1:
        raise RuntimeError("exact model identification line count differs")
    main_tex = (LANE / "repo" / "main.tex").read_text(encoding="utf-8")
    if "% Chapter 2's closing exercises use the available page flow." not in main_tex:
        raise RuntimeError("terminal v8 localized Chapter 2 flow comment differs")

    text = TEXT.read_bytes()
    privacy_zero(PDF.read_bytes(), "candidate PDF")
    privacy_zero(text, "extracted PDF text")
    if "Bab 1 dan Bagian 2.1–2.3" not in text.decode("utf-8"):
        raise RuntimeError("exact localized scope missing from extracted PDF")

    machine = json.loads((QA / "b007-assets" / "B007_ASSET_MACHINE_QA.json").read_text(encoding="utf-8"))
    portable = {record["key"]: record["portable_points"] for record in machine["records"] if record.get("portable_points")}
    if set(portable) != {"malaria_rand_dot_plot", "randomization_heart_transplants_rando"}:
        raise RuntimeError("portable point asset set differs")
    expected_counts = {
        "malaria_rand_dot_plot": (100, 100, 100),
        "randomization_heart_transplants_rando": (1318, 100, 1318),
    }
    for key, (runs, centres, circles) in expected_counts.items():
        structural = portable[key]["structural"]
        visible = portable[key]["render_visibility"]
        if (
            structural.get("source_glyph_run_count") != runs
            or structural.get("source_unique_visual_centre_count") != centres
            or structural.get("target_vector_circle_count") != circles
            or visible.get("poppler_visible_component_count") != 100
            or visible.get("mupdf_visible_component_count") != 100
            or visible.get("poppler_all_points_visible") is not True
            or visible.get("mupdf_all_points_visible") is not True
        ):
            raise RuntimeError(f"portable point proof differs for {key}")

    return candidate, parse_poppler_images(), parse_mupdf_images()


def records() -> tuple[bytes, bytes, dict[str, Any], dict[str, Any]]:
    candidate, poppler_images, mupdf_images = require_candidate()
    finalizer = {"path": rel(Path(__file__).resolve()), **identity(Path(__file__).resolve())}
    candidate_id = {"path": rel(CANDIDATE_RECEIPT), **EXPECTED["candidate_receipt"]}

    visual: dict[str, Any] = {
        "schema": "openintro-boundary-visual-audit",
        "schema_version": "0.3.0",
        "boundary_id": BOUNDARY_ID,
        "candidate": "final-v8",
        "status": "passed",
        "finalization_script": finalizer,
        "candidate_build_receipt": candidate_id,
        "inspection": {
            "method": "every Poppler candidate render opened individually at original/full resolution; all B007 pages and localized figures cross-checked in MuPDF",
            "poppler_inspected_pages": INSPECTED_PAGES,
            "poppler_inspected_page_count": len(INSPECTED_PAGES),
            "mupdf_inspected_pages": MUPDF_PAGES,
            "mupdf_inspected_page_count": len(MUPDF_PAGES),
            "independent_main_agent_pages": [1, 75, 76, 77, 78, 79, 80, 81, 82],
            "all_required_b007_pages_inspected": True,
        },
        "evidence": {
            "candidate_pdf": {"path": rel(PDF), "pages": 425, **EXPECTED["pdf"]},
            "poppler": {
                "render_manifest": {"path": rel(RENDER_MANIFEST), **EXPECTED["render_manifest"]},
                "page_locator": {"path": rel(PAGE_LOCATOR), **EXPECTED["page_locator"]},
                "contact_sheet": {"path": rel(CONTACT_SHEET), **EXPECTED["contact_sheet"]},
                "page_renders": poppler_images,
                "page_render_bytes": sum(int(item["bytes"]) for item in poppler_images),
                "unexpected_diagnostic_count": 0,
            },
            "mupdf": {
                "page_renders": mupdf_images,
                "page_render_bytes": sum(int(item["bytes"]) for item in mupdf_images),
            },
            "localized_assets": {
                "asset_count": 5,
                "machine_qa": {"path": "qa/b007-assets/B007_ASSET_MACHINE_QA.json", **EXPECTED["asset_machine"]},
                "visual_qa": {"path": "qa/b007-assets/B007_ASSET_VISUAL_QA.json", **EXPECTED["asset_visual"]},
                "canonical_promotion": {"path": "qa/b007-assets/B007_CANONICAL_PROMOTION_RECEIPT.json", **EXPECTED["asset_promotion"]},
                "portable_point_assets": [
                    {"key": "malaria_rand_dot_plot", "source_glyph_runs": 100, "unique_centres": 100, "vector_circles": 100, "poppler_visible_points": 100, "mupdf_visible_points": 100},
                    {"key": "randomization_heart_transplants_rando", "source_glyph_runs": 1318, "unique_centres": 100, "vector_circles": 1318, "poppler_visible_points": 100, "mupdf_visible_points": 100},
                ],
            },
        },
        "checks": {
            "readable_centered_page_filling_reflow": "passed for B007 scope",
            "clipping": "passed",
            "overlap": "passed",
            "truncation": "passed",
            "localized_english_residue": "passed_zero",
            "section_2_3_and_exercises_2_25_2_26": "passed pages 72-78",
            "public_answer_2_25": "passed page 389 with pages 388 and 390 context",
            "front_matter_scope_and_neutral_provenance": "passed pages 1-6",
            "portable_localized_figures": "passed Poppler and MuPDF",
        },
        "page_findings": [
            {"pages": [72, 73, 74, 75], "result": "Section 2.3 is readable and well-filled; page 75 displays all 100 malaria randomization points"},
            {"pages": [76, 77, 78], "result": "exercise header and Exercises 2.25-2.26 flow in source order without forced underfill; page 78 displays all 100 heart-transplant randomization centres and begins the out-of-boundary review"},
            {"pages": [81, 82], "result": "Chapter 3 opener and following transition are intact"},
            {"pages": [388, 389, 390], "result": "answer 2.25 and adjacent answer context are readable; no answer 2.26 was invented"},
        ],
        "deferred_out_of_boundary": [
            {"page": 80, "owner": "R011-B008", "finding": "the untranslated Chapter 2 review suffix ends sparsely before the intentional Chapter 3 opener"},
            {"page": 80, "owner": "R011-B008", "finding": "an inherited unembedded point font makes the marathon men series renderer-dependent; the B007 localized figure set is unaffected"},
        ],
        "severity_counts_within_b007": {"P0": 0, "P1": 0, "P2": 0, "P3": 0},
        "findings_within_b007": [],
        "promotion": {"performed": False, "claim": "atomic admission guard owns output promotion"},
        "privacy": {"prohibited_token_hits": 0, "absolute_profile_path_hits": 0},
    }
    visual_raw = canonical_json(visual)

    final = copy.deepcopy(candidate)
    final["status"] = "accepted"
    final["pending"] = []
    final["candidate_history"] = {**candidate_id, "status": "pending_visual_review", "preserved_unchanged": True}
    final["finalization_script"] = finalizer
    final["visual_evidence"]["status"] = "passed_operator_inspection"
    final["visual_evidence"]["required_next_action"] = "none for B007 build/visual QA"
    final["visual_evidence"]["visual_audit"] = {"path": rel(VISUAL_AUDIT), **identity_bytes(visual_raw)}
    final["visual_evidence"]["operator_inspection"] = {
        "poppler_pages": INSPECTED_PAGES,
        "mupdf_pages": MUPDF_PAGES,
        "all_required_b007_pages_inspected": True,
    }
    final["build_visual_acceptance"] = {
        "status": "accepted_build_and_visual",
        "nonvisual_status": "passed",
        "visual_status": "passed",
        "source_snapshot": "qa/b007-build/source-snapshot-v8",
        "source_snapshot_manifest": {"path": "qa/b007-build/R011-B007_SNAPSHOT_MANIFEST_V8.tsv", **EXPECTED["snapshot_manifest"]},
        "source_or_layout_mutated_by_finalization": False,
        "output_mutated": False,
        "backend_or_control_mutated": False,
        "publication_performed": False,
        "next_cursor": "R011-B008",
    }
    final["privacy_final"] = {"prohibited_token_hits": 0, "absolute_profile_path_hits": 0, "result": "PASS_ZERO_ZERO"}
    final["write_boundary"] = [rel(VISUAL_AUDIT), rel(CANDIDATE_RECEIPT)]
    final_raw = canonical_json(final)
    privacy_zero(visual_raw, "visual receipt")
    privacy_zero(final_raw, "build receipt")
    return visual_raw, final_raw, visual, final


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    visual_raw, final_raw, visual, final = records()
    expected = ((VISUAL_AUDIT, visual_raw), (CANDIDATE_RECEIPT, final_raw))
    if args.write:
        for path, raw in expected:
            existing = path.read_bytes() if path.exists() else None
            permitted_candidate_preimage = (
                path == CANDIDATE_RECEIPT
                and existing is not None
                and (
                    identity_bytes(existing) == EXPECTED["candidate_receipt"]
                    or identity_bytes(canonical_json(candidate_preimage(json.loads(existing.decode("utf-8")))))
                    == EXPECTED["candidate_receipt"]
                )
            )
            permitted_partial_visual = False
            if path == VISUAL_AUDIT and existing is not None and existing != raw:
                prior_visual = json.loads(existing.decode("utf-8"))
                permitted_partial_visual = (
                    prior_visual.get("schema") == "openintro-boundary-visual-audit"
                    and prior_visual.get("boundary_id") == BOUNDARY_ID
                    and prior_visual.get("candidate") == "final-v8"
                    and prior_visual.get("status") == "passed"
                )
            if existing is not None and existing != raw and not (
                permitted_candidate_preimage or permitted_partial_visual
            ):
                raise RuntimeError(f"refusing to overwrite non-canonical record: {rel(path)}")
            path.write_bytes(raw)
            if path.read_bytes() != raw:
                raise RuntimeError(f"record readback failed: {rel(path)}")
    else:
        for path, raw in expected:
            if not path.is_file() or path.read_bytes() != raw:
                raise RuntimeError(f"read-only replay failed: {rel(path)} differs or is absent")

    print(json.dumps({
        "status": final["status"],
        "candidate": "final-v8",
        "page_count": 425,
        "inspected_pages": INSPECTED_PAGES,
        "candidate_pdf": {"path": rel(PDF), **EXPECTED["pdf"]},
        "visual_audit": {"path": rel(VISUAL_AUDIT), **identity_bytes(visual_raw)},
        "accepted_candidate_receipt": {"path": rel(CANDIDATE_RECEIPT), **identity_bytes(final_raw)},
        "next_cursor": "R011-B008",
        "errors": [],
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
