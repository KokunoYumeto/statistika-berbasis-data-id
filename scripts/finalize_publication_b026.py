#!/usr/bin/env python3
"""Offline fail-closed B026 public-state and control finalizer.

The finalizer verifies the exact admitted backend, promoted reader, immutable
package, and sanitized Zenodo/GitHub public-byte receipts.  It then advances
only four bounded control targets from the exact B025 preimage.  It never uses
Git, the network, credentials, backend/output/release mutation, or upstream
contact.  The corpus goal remains active and advances to R011-B027.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any

from b026_release_contract import (
    BACKEND_ADMISSION_RECEIPT_PATH,
    BACKEND_REPLAY_RECEIPT_PATH,
    BOUNDARY_ID,
    CONFIG_PATH,
    FINAL_READER_PATH,
    FINALIZATION_RECEIPT_PATH,
    FINALIZATION_REPLAY_PATH,
    GITHUB_TAG,
    MODEL,
    NEXT_BOUNDARY_ID,
    PROMOTION_RECEIPT_PATH,
    RELEASE_DIR,
    RELEASE_ID,
    ROOT,
    StageGateError,
    VERSION,
    canonical,
    exact_json,
    identity,
    offline_release_self_check,
    release_ready,
    repo_path,
    verify_backend_receipts,
    verify_promoted_reader,
)
from package_b026 import ASSETS, config, verify_package
from publish_b026 import GITHUB_RECEIPT, STATUSES, ZENODO_RECEIPT


BASE_CONTROLS = {
    "00_control/CURRENT_CURSOR.json": {
        "bytes": 38_764,
        "sha256": "456c91953d41aad75b9254f7d94ec3000c7d37239808247cbfbdb78c57991dcb",
    },
    "00_control/CURRENT_STATE.md": {
        "bytes": 830,
        "sha256": "4c98ce7574dbd5086db071b86a6d392ba04be642b3cfcbd62c0b250c7ffd6781",
    },
}
QA_ROOT = ROOT / "qa/b026-publication-finalization"
PREIMAGES = QA_ROOT / "control-preimages"
PREIMAGE_MANIFEST = PREIMAGES / "PREIMAGE_MANIFEST.json"
CHECKPOINT = "00_control/R011-B026_PUBLICATION_CHECKPOINT.md"
SEMANTICS = "00_control/R011-B026_RELEASE_MANIFEST_SEMANTICS.md"
TARGETS = (
    "00_control/CURRENT_CURSOR.json",
    "00_control/CURRENT_STATE.md",
    CHECKPOINT,
    SEMANTICS,
)
FINAL_RECEIPT = repo_path(FINALIZATION_RECEIPT_PATH)
REPLAY_RECEIPT = repo_path(FINALIZATION_REPLAY_PATH)


def local_identity(path: Path, logical_path: str | None = None) -> dict[str, Any]:
    if not path.is_file():
        raise StageGateError(f"missing required file: {path}")
    raw = path.read_bytes()
    return {
        "path": logical_path if logical_path is not None else path.as_posix(),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def public_inputs() -> dict[str, Any]:
    ready = release_ready(require_complete=True)
    assert ready is not None
    binding = ready["binding"]
    candidate = binding["post_build_outputs"]["candidate_pdf"]
    reader = identity(repo_path(FINAL_READER_PATH))
    if (reader["bytes"], reader["sha256"]) != (
        candidate["bytes"], candidate["sha256"],
    ):
        raise StageGateError("stable B026 reader differs from bound candidate")
    backend_gate = verify_backend_receipts(require_complete=True)
    promotion_gate = verify_promoted_reader(require_complete=True)
    assert backend_gate is not None and promotion_gate is not None
    backend = exact_json(repo_path("backend/exports/manifest.json"))
    if (
        backend.get("boundary_id") != BOUNDARY_ID
        or backend.get("build_binding", {}).get("reader_pdf") != candidate
    ):
        raise StageGateError("backend does not admit the exact B026 reader")
    manifest = verify_package()
    cfg = config()
    zenodo = exact_json(ZENODO_RECEIPT)
    github = exact_json(GITHUB_RECEIPT)
    for name, row in (("zenodo", zenodo), ("github", github)):
        if (
            row.get("boundary_id") != BOUNDARY_ID
            or row.get("release_id") != RELEASE_ID
            or row.get("status") not in STATUSES
            or row.get("anonymous_public_byte_readback") is not True
        ):
            raise StageGateError(f"{name} public receipt is not final")
    if (
        zenodo.get("access_right") != "open"
        or github.get("repository_public") is not True
        or github.get("anonymous_exact_tree_readback") is not True
    ):
        raise StageGateError("public access/readback proof is incomplete")
    expected = {
        name: {
            key: identity(RELEASE_DIR / name)[key] for key in ("bytes", "sha256")
        }
        for name in ASSETS
    }
    for receipt, field in (
        (zenodo, "ordered_files"),
        (github, "ordered_assets"),
    ):
        rows = {
            row["filename"]: {key: row[key] for key in ("bytes", "sha256")}
            for row in receipt[field]
        }
        if rows != expected:
            raise StageGateError("public receipt asset inventory differs from package")
    return {
        "binding": binding,
        "binding_identity": ready["binding_identity"],
        "reader": reader,
        "backend": backend,
        "backend_identity": backend_gate["manifest"],
        "admission": backend_gate["admission"],
        "replay": backend_gate["replay"],
        "promotion": promotion_gate["receipt"],
        "manifest": manifest,
        "manifest_identity": identity(RELEASE_DIR / "RELEASE_MANIFEST.json"),
        "config": cfg,
        "zenodo": zenodo,
        "zenodo_identity": identity(ZENODO_RECEIPT),
        "github": github,
        "github_identity": identity(GITHUB_RECEIPT),
        "record_count": backend_gate["record_count"],
    }


def base_controls(root: Path) -> tuple[dict[str, Any], bytes]:
    for rel, expected in BASE_CONTROLS.items():
        path = root / rel
        observed = local_identity(path, rel)
        if (observed["bytes"], observed["sha256"]) != (
            expected["bytes"], expected["sha256"],
        ):
            raise StageGateError(f"control is not the exact B025 preimage: {rel}")
    try:
        cursor = json.loads(
            (root / "00_control/CURRENT_CURSOR.json").read_text(encoding="utf-8")
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StageGateError("B025 cursor preimage is invalid") from exc
    if (
        cursor.get("current_boundary", {}).get("id") != "R011-B025"
        or cursor.get("next_boundary") != BOUNDARY_ID
        or cursor.get("goal_active") is not True
        or cursor.get("complete_corpus") is not False
    ):
        raise StageGateError("B025 cursor preimage semantics changed")
    return cursor, (root / "00_control/CURRENT_STATE.md").read_bytes()


def projections(root: Path) -> tuple[dict[str, bytes], dict[str, Any]]:
    base, _state = base_controls(root)
    pub = public_inputs()
    pages = pub["binding"]["post_build_outputs"]["candidate_pdf"]["pages"]
    coverage = (
        "Indonesian front matter and Chapters 1-5, Chapter 6 Sections 6.1-6.4, "
        "and Chapter 7 Section 7.1; Chapter 7 exercises 1-14; public odd answers "
        "1-13; O001 even-answer gaps 2-14"
    )
    publication = {
        "boundary_id": BOUNDARY_ID,
        "state": "B026_Zenodo_GitHub_published",
        "accepted_indonesian_reader_pages": pages,
        "learner_reader_pages": pages,
        "complete_corpus": False,
        "current_chapter": 7,
        "current_chapter_exercise_ids": list(range(1, 15)),
        "current_chapter_public_answer_ids": list(range(1, 14, 2)),
        "current_chapter_o001_gap_ids": list(range(2, 15, 2)),
        "untranslated_instructional_or_exercise_prose_pages": 0,
        "source_closure_counted_as_learner_output": False,
        "public_asset_count": len(ASSETS),
        "zenodo_concept_doi": "10.5281/zenodo.22059801",
        "zenodo_doi": pub["zenodo"]["doi"],
        "zenodo_record_id": pub["zenodo"]["record_id"],
        "zenodo_url": pub["zenodo"]["public_url"],
        "zenodo_receipt": pub["zenodo_identity"],
        "github_repository": "KokunoYumeto/statistika-berbasis-data-id",
        "github_tag": GITHUB_TAG,
        "github_release_commit": pub["github"]["release_commit"],
        "github_tree_path_count": pub["github"]["tree_path_count"],
        "github_url": pub["github"]["release_url"],
        "github_receipt": pub["github_identity"],
        "release_manifest": pub["manifest_identity"],
        "backend_manifest_after_publication": pub["backend_identity"],
        "backend_publication_metadata_mutated": False,
        "anonymous_exact_tree_readback": True,
        "anonymous_public_byte_readback": True,
        "no_upstream_contact": True,
        "no_user_first_name": True,
    }
    boundary = {
        "id": BOUNDARY_ID,
        "artifact": FINAL_READER_PATH,
        "artifact_bytes": pub["reader"]["bytes"],
        "artifact_sha256": pub["reader"]["sha256"],
        "artifact_pages": pages,
        "coverage": coverage,
        "complete_corpus": False,
        "durable_goal_status": "active",
        "backend_manifest": "backend/exports/manifest.json",
        "backend_manifest_bytes": pub["backend_identity"]["bytes"],
        "backend_manifest_sha256": pub["backend_identity"]["sha256"],
        "backend_record_count": pub["record_count"],
        "backend_stage_state": "live_admitted_candidate",
        "boundary_receipt": pub["admission"]["path"],
        "boundary_receipt_bytes": pub["admission"]["bytes"],
        "boundary_receipt_sha256": pub["admission"]["sha256"],
        "backend_replay_receipt": pub["replay"]["path"],
        "backend_replay_receipt_bytes": pub["replay"]["bytes"],
        "backend_replay_receipt_sha256": pub["replay"]["sha256"],
        "learner_reader_semantics": {
            "accepted_indonesian_reader_pages": pages,
            "all_pages_adjudicated": True,
            "untranslated_instructional_or_exercise_prose_pages": 0,
            "visual_defect_count": 0,
            "page_count_is_artifact_extent_not_translation_progress": True,
            "source_closure_counted_as_learner_output": False,
        },
        "exercise_answer_closure": {
            "chapter": 7,
            "exercise_ids": list(range(1, 15)),
            "public_answer_ids": list(range(1, 14, 2)),
            "o001_gap_ids": list(range(2, 15, 2)),
            "restricted_solutions_accessed_or_invented": False,
        },
        "component_rights": {
            "upstream_and_translation": "CC BY-SA 3.0",
            "rissos_dolphin_photo": "Mike Baird, CC BY 2.0, byte-identical",
        },
        "publication": publication,
        "state": (
            "admitted_and_publicly_preserved_Zenodo_GitHub_"
            "backend_publication_metadata_unmutated"
        ),
        "next_action": (
            "translate R011-B027 from ch_inference_for_means.tex line 1059, "
            "label pairedData at line 1060; no later coverage claimed"
        ),
    }
    cursor = copy.deepcopy(base)
    cursor["prior_boundary"] = copy.deepcopy(base["current_boundary"])
    cursor["previous_detailed_boundary"] = copy.deepcopy(base["current_boundary"])
    cursor["current_boundary"] = boundary
    cursor["terminal_boundary"] = copy.deepcopy(boundary)
    cursor["publication"] = publication
    cursor["publication_state"] = "B026_Zenodo_GitHub_published"
    cursor["active_work"] = {
        "id": NEXT_BOUNDARY_ID,
        "boundary_id": NEXT_BOUNDARY_ID,
        "authority_path": (
            "authority/upstream/openintro-statistics-"
            "fee25091fb24e89c36296fd67c48c1fcf7a93b6e/"
            "ch_inference_for_means/TeX/ch_inference_for_means.tex"
        ),
        "live_path": "repo/ch_inference_for_means/TeX/ch_inference_for_means.tex",
        "line": 1059,
        "authority_line": 1059,
        "label": "pairedData",
        "label_line": 1060,
        "instructional_unit": "Chapter 7 paired data and the paired t procedure",
        "state": "ready_for_translation",
        "next_required_action": (
            "translate in source order from authority line 1059, label pairedData"
        ),
        "source_cursor_advanced": True,
    }
    cursor["next_boundary"] = NEXT_BOUNDARY_ID
    cursor["next_after_admission"] = NEXT_BOUNDARY_ID
    cursor["source_cursor_advanced"] = True
    cursor["status"] = (
        "R011-B001_through_B026_admitted_published_and_finalized_"
        "R011-B027_translation_next"
    )
    cursor["goal_active"] = True
    cursor["durable_goal_status"] = "active"
    cursor["complete_corpus"] = False
    cursor["latest_publication"] = publication
    cursor["latest_qa_receipt"] = pub["admission"]["path"]
    cursor["latest_qa_receipt_bytes"] = pub["admission"]["bytes"]
    cursor["latest_qa_receipt_sha256"] = pub["admission"]["sha256"]
    cursor["latest_checkpoint"] = CHECKPOINT
    cursor["latest_finalization_receipt"] = FINALIZATION_RECEIPT_PATH
    completed = copy.deepcopy(base.get("completed_boundaries", []))
    completed.append(
        {
            "id": BOUNDARY_ID,
            "state": boundary["state"],
            "artifact": FINAL_READER_PATH,
            "artifact_bytes": pub["reader"]["bytes"],
            "artifact_sha256": pub["reader"]["sha256"],
            "artifact_pages": pages,
            "receipt": pub["admission"]["path"],
            "receipt_bytes": pub["admission"]["bytes"],
            "receipt_sha256": pub["admission"]["sha256"],
            "zenodo_doi": pub["zenodo"]["doi"],
            "github_tag": GITHUB_TAG,
            "publication_checkpoint": CHECKPOINT,
        }
    )
    cursor["completed_boundaries"] = completed
    state = (
        "# R011 OpenIntro Statistics Bahasa Indonesia - keadaan kini\n\n"
        f"B026 diterima, diterbitkan, dan dibaca kembali secara anonim. Pembaca "
        f"kanonik berisi {pages} halaman hingga Bab 7 Bagian 7.1. Untuk Bab 7, "
        "latihan 1-14, jawaban publik ganjil 1-13, dan kesenjangan O001 genap "
        "2-14 telah dicatat. Korpus lengkap belum selesai.\n\n"
        f"- PDF: `{FINAL_READER_PATH}`\n"
        f"- SHA-256: `{pub['reader']['sha256']}`\n"
        f"- Zenodo: {pub['zenodo']['public_url']}\n"
        f"- GitHub: {pub['github']['release_url']}\n"
        f"- Backend: {pub['record_count']} rekaman\n"
        f"- Model: {MODEL}\n"
        "- Kontak hulu: tidak\n\n"
        "Kursor berikutnya: R011-B027, `ch_inference_for_means/TeX/"
        "ch_inference_for_means.tex` baris 1059, label `pairedData` baris 1060.\n"
    ).encode("utf-8")
    checkpoint = (
        "# Checkpoint publikasi R011-B026\n\n"
        "Status: diterima dan dipertahankan publik pada Zenodo dan GitHub.\n\n"
        f"- Pembaca: {pages} halaman, `{pub['reader']['sha256']}`\n"
        "- Cakupan baru: Bab 7 Bagian 7.1; latihan 1-14; jawaban publik ganjil "
        "1-13; O001 genap 2-14\n"
        f"- Zenodo: {pub['zenodo']['public_url']} ({pub['zenodo']['doi']})\n"
        f"- GitHub: {pub['github']['release_url']} ({GITHUB_TAG})\n"
        f"- Semua {len(ASSETS)} aset publik dibaca kembali dengan jumlah byte "
        "dan SHA-256 yang tepat.\n"
        "- Foto lumba-lumba Risso: Mike Baird, CC BY 2.0, byte-identik.\n"
        "- Korpus lengkap: tidak.\n"
        f"- Model: {MODEL}.\n"
        "- Kontak hulu: tidak.\n"
    ).encode("utf-8")
    semantics = (
        "# Semantik manifes rilis R011-B026\n\n"
        "`PACKAGED_VERIFIED` menyatakan paket prapublikasi deterministik; bukti "
        "publikasi berasal dari receipt Zenodo/GitHub dengan pembacaan balik "
        "anonim. Bidang `publication_performed: false` pada manifes paket tidak "
        "membatalkan receipt publik. Byte rilis tidak diubah setelah publikasi. "
        "Arsip sumber dapat memuat ekor hulu yang belum diterjemahkan untuk "
        "reproduksibilitas; ekor itu bukan keluaran pembelajar dan tidak dihitung "
        "sebagai kemajuan terjemahan. Foto `rissosDolphin.jpg` tetap CC BY 2.0 "
        "dan dipertahankan byte-identik.\n"
    ).encode("utf-8")
    checkpoint_sha = hashlib.sha256(checkpoint).hexdigest()
    cursor["latest_checkpoint_bytes"] = len(checkpoint)
    cursor["latest_checkpoint_sha256"] = checkpoint_sha
    cursor["latest_publication_checkpoint"] = CHECKPOINT
    cursor["latest_publication_checkpoint_bytes"] = len(checkpoint)
    cursor["latest_publication_checkpoint_sha256"] = checkpoint_sha
    cursor["completed_boundaries"][-1]["publication_checkpoint_bytes"] = len(
        checkpoint
    )
    cursor["completed_boundaries"][-1][
        "publication_checkpoint_sha256"
    ] = checkpoint_sha
    return {
        "00_control/CURRENT_CURSOR.json": canonical(cursor),
        "00_control/CURRENT_STATE.md": state,
        CHECKPOINT: checkpoint,
        SEMANTICS: semantics,
    }, pub


def save_preimages() -> None:
    if PREIMAGES.exists():
        if not PREIMAGE_MANIFEST.is_file():
            raise StageGateError("foreign or incomplete B026 control preimages")
        manifest = exact_json(PREIMAGE_MANIFEST)
        if manifest.get("boundary_id") != "R011-B025":
            raise StageGateError("B026 control-preimage boundary changed")
        base_controls(PREIMAGES)
        return
    PREIMAGES.mkdir(parents=True)
    rows = []
    for rel, expected in BASE_CONTROLS.items():
        target = PREIMAGES / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, target)
        rows.append({"path": rel, **expected})
    PREIMAGE_MANIFEST.write_bytes(
        canonical({"boundary_id": "R011-B025", "files": rows})
    )
    base_controls(PREIMAGES)


def finalize() -> dict[str, Any]:
    payloads, pub = projections(ROOT)
    save_preimages()
    staged: dict[str, Path] = {}
    for rel, raw in payloads.items():
        target = ROOT / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + ".b026.tmp")
        if temporary.exists():
            raise StageGateError(f"stale finalization temporary: {temporary}")
        temporary.write_bytes(raw)
        staged[rel] = temporary
    for rel in TARGETS:
        os.replace(staged[rel], ROOT / rel)
    receipt = {
        "$schema": "interlanguage.r011-b026-publication-finalization/v1",
        "boundary_id": BOUNDARY_ID,
        "status": "PASS_B026_PUBLICATION_FINALIZED_CONTROLS_ADVANCED_TO_B027",
        "release_id": RELEASE_ID,
        "version": VERSION,
        "reader": pub["reader"],
        "backend_manifest": pub["backend_identity"],
        "zenodo_receipt": pub["zenodo_identity"],
        "github_receipt": pub["github_identity"],
        "control_outputs": {rel: identity(ROOT / rel) for rel in TARGETS},
        "complete_corpus": False,
        "goal_active": True,
        "next_boundary": NEXT_BOUNDARY_ID,
        "git_used": False,
        "network_used": False,
        "credentials_accessed": False,
        "publication_performed_by_finalizer": False,
        "upstream_contact": False,
    }
    FINAL_RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    FINAL_RECEIPT.write_bytes(canonical(receipt))
    verify(write_replay=True)
    return {**receipt, "receipt": identity(FINAL_RECEIPT)}


def verify(*, write_replay: bool) -> dict[str, Any]:
    if not PREIMAGES.is_dir():
        raise StageGateError("B026 control preimages are absent")
    payloads, pub = projections(PREIMAGES)
    for rel, raw in payloads.items():
        if (ROOT / rel).read_bytes() != raw:
            raise StageGateError(f"live finalized control differs: {rel}")
    result = {
        "$schema": "interlanguage.r011-b026-publication-finalization-replay/v1",
        "boundary_id": BOUNDARY_ID,
        "status": "PASS_EXACT_B026_PUBLICATION_FINALIZATION_REPLAY",
        "control_outputs": {rel: identity(ROOT / rel) for rel in TARGETS},
        "reader": pub["reader"],
        "complete_corpus": False,
        "goal_active": True,
        "next_boundary": NEXT_BOUNDARY_ID,
        "git_used": False,
        "network_used": False,
        "credentials_accessed": False,
    }
    if write_replay:
        REPLAY_RECEIPT.write_bytes(canonical(result))
    return result


def static_state() -> dict[str, Any]:
    release_static = offline_release_self_check("b026-publication-finalizer")
    pending = list(release_static["pending"])
    if not CONFIG_PATH.is_file():
        pending.append("exact B026 release-input contract")
    if not (RELEASE_DIR / "RELEASE_MANIFEST.json").is_file():
        pending.append("exact verified B026 reader-first package")
    if not ZENODO_RECEIPT.is_file():
        pending.append("public Zenodo publication plus anonymous exact-byte readback")
    if not GITHUB_RECEIPT.is_file():
        pending.append("public GitHub publication plus anonymous tree/byte readback")
    controls = {
        rel: local_identity(ROOT / rel, rel) for rel in BASE_CONTROLS
    }
    for rel, expected in BASE_CONTROLS.items():
        if (controls[rel]["bytes"], controls[rel]["sha256"]) != (
            expected["bytes"], expected["sha256"],
        ):
            raise StageGateError(f"B025 control preimage changed: {rel}")
    return {
        "$schema": "interlanguage.r011-b026-finalizer-self-check/v1",
        "boundary_id": BOUNDARY_ID,
        "status": (
            "PASS_STATIC_B026_FINALIZER_ALL_INPUTS_READY"
            if not pending
            else "PASS_STATIC_B026_FINALIZER_FAIL_CLOSED_GATES_PENDING"
        ),
        "base_controls": controls,
        "pending": pending,
        "writes_performed": False,
        "network_used": False,
        "credentials_accessed": False,
        "git_used": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--self-check", action="store_true")
    mode.add_argument("--probe", action="store_true")
    mode.add_argument("--finalize", action="store_true")
    mode.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        result = static_state()
    elif args.probe:
        state = static_state()
        if state["pending"]:
            result = state
        else:
            payloads, pub = projections(ROOT)
            result = {
                "status": "PASS_B026_FINALIZATION_PROBE_NO_WRITES",
                "planned_outputs": {
                    rel: {
                        "bytes": len(raw),
                        "sha256": hashlib.sha256(raw).hexdigest(),
                    }
                    for rel, raw in payloads.items()
                },
                "reader": pub["reader"],
                "writes_performed": False,
            }
    elif args.finalize:
        result = finalize()
    else:
        result = verify(write_replay=False)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except StageGateError as exc:
        raise SystemExit(f"REFUSED: {exc}")
