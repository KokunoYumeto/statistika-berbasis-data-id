#!/usr/bin/env python3
"""Generate the isolated, final-gated, nonadmitted R011-B007 backend stage.

The generator extends the exact admitted R011-B006 backend into an isolated
stage using pinned authority, candidate, terminology, source-gate, asset, build,
visual, PDF, and accessibility receipts.  It never mutates ``repo``,
``backend/exports``, or ``output``.  The exact final-input bindings below are
deliberately unset until a terminal build is accepted; no stage write is
possible while any binding remains unset.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import io
import json
import re
from pathlib import Path
from typing import Any, Iterable

from pypdf import PdfReader


SCHEMA_VERSION = "0.1.0"
RECORDED_AT = "2026-08-22T22:00:00+02:00"
WORKFLOW_ID = "r011-openintro-statistics-id-b007-backend-stage"
BOUNDARY_ID = "R011-B007"
BASE_BOUNDARY_ID = "R011-B006"
BASE_MANIFEST_BYTES = 23151
BASE_MANIFEST_SHA256 = "d2324e74bff4aa8c985c82a89317828150910f6369b821898a9b1bca33083d0b"
BASE_RECORD_COUNT = 1969
EXPECTED_AUTHORITY = {
    "commit": "fee25091fb24e89c36296fd67c48c1fcf7a93b6e",
    "tree": "d61cc601e7d97759ce805900520f784d02a0489e",
}
EXPECTED_CANDIDATE_MANIFEST = {
    "bytes": 5484,
    "sha256": "ede9a93032d6f3c702ad4bb5add099508de508aba84be22ca0455f0172504e66",
}
EXPECTED_VALIDATION_RECEIPT = {
    "bytes": 6354,
    "sha256": "f0048c1e2dba146dd4b1f9767050f8a58e7db548c03b4ff8d66cd5ef628f9df9",
}
NEUTRAL_TRANSLATION_PROVENANCE = "Direct English-to-id-ID translation by OpenAI Codex gpt-5.6-sol, Ultra, at the user's request; exact canonical target span, backend admission pending."
EXPECTED_BASE_LOCALIZATION_COUNT = 172
EXPECTED_PRIVACY_TARGET_REBIND_COUNT = 1
EXPECTED_LEGACY_TRANSLATION_PROVENANCE_SHA256 = "96dd0536ac11d49852b609113d181f740e46fff728d8c4f72e90eb986ac8907a"
EXPECTED_SANITIZED_AUXILIARY_COUNT = 6
PRIVACY_RECEIPT_EXPORT_PATH = "evidence/R011-B007_PRIVACY_SANITIZATION_RECEIPT.json"

# Release bindings, never discovery hints. Rejected build candidates must never
# be bound here; these identities are the independently verified terminal v8
# build and visual evidence.
EXPECTED_FINAL_INPUTS: dict[str, dict[str, Any]] = {
    "snapshot_manifest": {"path": "qa/b007-build/R011-B007_SNAPSHOT_MANIFEST_V8.tsv", "bytes": 174617, "sha256": "a09e47b52b7b8d5eada0d9086777dcfd57b71339897b9ff0769c6d43fbb0b4c4"},
    "build_gate_script": {"path": "scripts/qa_build_b007.py", "bytes": 21307, "sha256": "43991ce4dcd0e45bf488645e4f5b1d7be32703a1966fdacf16df02316cef14c1"},
    "candidate_build_qa": {"path": "qa/b007-build/final-v8/CANDIDATE_BUILD_QA_V8.json", "bytes": 20331, "sha256": "64a3c433a4a6bce3ea335fb1ec51f952851929e9230ea084bfa758a0dd5f8151"},
    "build_qa": {"path": "qa/R011-B007_BUILD_QA.json", "bytes": 1941, "sha256": "7e113f6f7bf083265fb67843ecd7458ac945b54be88a3eb8eadee66397d3854d"},
    "build_log": {"path": "qa/b007-build/final-v8/main.log", "bytes": 495076, "sha256": "66fc93d9953425f9dd24c435c7f3fe3bf5f38655431aad647573f53fba5b0261"},
    "build_text": {"path": "qa/b007-build/final-v8/main-final.txt", "bytes": 1583120, "sha256": "c1b6d1d777b3b89d7a70afa00f0429ce4e7a0b8e9bfbdd8ec17c87d84a564336"},
    "pass3_pdf": {"path": "qa/b007-build/final-v8/main-pass3.pdf", "bytes": 22017185, "sha256": "ca872ddbc2fb1cab5f6cdb2fe745a0711a315fef68ab2e72c7a11d1c633a5c1a"},
    "pdf": {"path": "qa/b007-build/final-v8/main.pdf", "bytes": 22017185, "sha256": "ca872ddbc2fb1cab5f6cdb2fe745a0711a315fef68ab2e72c7a11d1c633a5c1a", "page_count": 425},
    "render_manifest": {"path": "qa/b007-render/final-v8/FINAL_MANIFEST.tsv", "bytes": 2019, "sha256": "895e6ff19e786153ae03cc9397f21bb3629beece560d727c35af29887d5c9748", "page_count": 23},
    "page_locator": {"path": "qa/b007-render/final-v8/PAGE_LOCATOR.json", "bytes": 1503, "sha256": "80ba13a304b6db2384aa4f60718f710677ab396aea5d24ba8a766fb91d628e4b"},
    "contact_sheet": {"path": "qa/b007-render/final-v8/CONTACT_SHEET.png", "bytes": 961888, "sha256": "a088b211a037684ba5cfab6eb237b0cdc6343d5ee646ca078b14c7c871d4a95a"},
    "visual_audit": {"path": "qa/R011-B007_VISUAL_AUDIT.json", "bytes": 13083, "sha256": "67395e5c8b13d9373952e42c26733d32b94c97bde7162f25500b4dc492f8c6b2"},
    "visual_finalizer": {"path": "scripts/qa_finalize_b007_visual_v8.py", "bytes": 23751, "sha256": "c98dc40b05b77892f07e653a1f8162b2d3628830497bda6f3f7bf9e550b4ff9b"},
}
EXPECTED_FINAL_GATE: dict[str, Any] = {
    "candidate": "final-v8",
    "page_count": 425,
    "inspected_pages": [1, 2, 4, 5, 6, 46, 47, 53, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 388, 389, 390],
    "severity_counts": {"P0": 0, "P1": 0, "P2": 0, "P3": 0},
}
EXPECTED_PENDING_CANDIDATE_HISTORY = {
    "path": "qa/b007-build/final-v8/CANDIDATE_BUILD_QA_V8.json",
    "bytes": 18531,
    "sha256": "1f1aab5da5646adbc53aec9178266f8c59575634a4a1a9d9e1547fbb757bf403",
    "preserved_unchanged": True,
    "status": "pending_visual_review",
}

LANE = Path(__file__).resolve().parents[1]
LIVE_BACKEND = LANE / "backend"
LIVE_EXPORTS = LIVE_BACKEND / "exports"
STAGE_ROOT = LANE / "qa" / "b007-backend"
STAGE_EXPORTS = STAGE_ROOT / "exports"
FINAL_INPUTS_DEFAULT = STAGE_ROOT / "R011-B007_FINAL_GATE_INPUTS.json"
CANDIDATE_ROOT = LANE / "scratch" / "R011-B007-candidate"
CANDIDATE_MANIFEST_PATH = CANDIDATE_ROOT / "CANDIDATE_MANIFEST.json"
VALIDATION_RECEIPT_PATH = CANDIDATE_ROOT / "VALIDATION_RECEIPT.json"
ASSET_TSV_PATH = CANDIDATE_ROOT / "ASSET_LOCALIZATION_MANIFEST.tsv"
TERM_TSV_PATH = CANDIDATE_ROOT / "TERMINOLOGY_PROPOSALS.tsv"
CORRECTION_TSV_PATH = CANDIDATE_ROOT / "SOURCE_CORRECTIONS.tsv"
O001_TSV_PATH = CANDIDATE_ROOT / "O001_MASTERY_GAPS.tsv"
FIELD_QA_PATH = LANE / "qa" / "terminology" / "R011_TERMINOLOGY_FIELD_USAGE_QA.json"
FIELD_QA_NOTE_PATH = LANE / "qa" / "terminology" / "R011_TERMINOLOGY_FIELD_USAGE_QA.md"
EXPECTED_FIELD_QA = {
    "bytes": 9629,
    "sha256": "e52e69e6bd64dd5078adbd63a82f7923a4d4ba1e5f14ceecec5a3d0a8108a9d0",
}
EXPECTED_FIELD_QA_NOTE = {
    "bytes": 2312,
    "sha256": "2b1de3fbd1681532e45c0d47e72a779a9f6a55bb75e257b9e7c9e83dc094f4af",
}
SOURCE_APPLICATION_MANIFEST_PATH = LANE / "qa" / "R011-B007_SOURCE_APPLICATION_MANIFEST.json"
SOURCE_APPLICATION_RECEIPT_PATH = LANE / "qa" / "R011-B007_SOURCE_APPLICATION_RECEIPT.json"
SOURCE_GATE_QA_PATH = LANE / "qa" / "R011-B007_SOURCE_GATE_QA.json"
EXPECTED_SOURCE_APPLICATION_MANIFEST = {
    "bytes": 27428,
    "sha256": "7f8943fc8d02e4f9502f9235fcb0160b9326261e8faf0b8099d8138595277496",
}
EXPECTED_SOURCE_APPLICATION_RECEIPT = {
    "bytes": 26533,
    "sha256": "1b0429aa37617e021fb77d1ede777347dbb5df24cba79ebda60da521d3ee3187",
}
EXPECTED_SOURCE_GATE_QA = {
    "bytes": 3370,
    "sha256": "677921acb28e9da034c4c40fc78a7367162ceaf1d986a8bdb0f29977aa237294",
}
ASSET_QA_ROOT = LANE / "qa" / "b007-assets"
ASSET_PROMOTION_RECEIPT_PATH = ASSET_QA_ROOT / "B007_CANONICAL_PROMOTION_RECEIPT.json"
ASSET_LOCALIZATION_RECEIPT_PATH = ASSET_QA_ROOT / "B007_ASSET_LOCALIZATION_RECEIPT.json"
ASSET_OUTPUT_MANIFEST_PATH = ASSET_QA_ROOT / "B007_ASSET_OUTPUT_MANIFEST.json"
ASSET_PRIVACY_QA_PATH = ASSET_QA_ROOT / "B007_ASSET_PRIVACY_REFRESH_QA.json"
EXPECTED_ASSET_PROMOTION_RECEIPT = {
    "bytes": 19032,
    "sha256": "5594452b1fca3bed7b8f4b97ee0c33af67dfd1f18aff7458c9512a66c85d6ae1",
}
EXPECTED_ASSET_LOCALIZATION_RECEIPT = {
    "bytes": 8207,
    "sha256": "5021a0591cbea58e302b8962b89186b170a6830e953ddae7360abec58e919941",
}
EXPECTED_ASSET_OUTPUT_MANIFEST = {
    "bytes": 8696,
    "sha256": "8682e2ff4a761f55abc260915cfec59881f04ef61d76a60c983699d5e09fd524",
}
EXPECTED_ASSET_PRIVACY_QA = {
    "bytes": 13841,
    "sha256": "58358d23440cb8d632a9efa800ae3236c275ba425ed5b3e8c580c30bba15db81",
}
MAIN_PATH = "ch_summarizing_data/TeX/ch_summarizing_data.tex"
EXERCISE_PATH = "ch_summarizing_data/TeX/case_study_malaria_vaccine.tex"
ANSWER_PATH = "extraTeX/eoceSolutions/eoceSolutions.tex"
TARGET_MAIN_PATH = "ch_summarizing_data/TeX/ch_summarizing_data.section-2.3.tex"
TARGET_EXERCISE_PATH = "ch_summarizing_data/TeX/case_study_malaria_vaccine.tex"
TARGET_ANSWER_PATH = "extraTeX/eoceSolutions/solution-25.tex"
GENERATOR_PATH = Path(__file__).resolve()
VALIDATOR_PATH = LANE / "scripts" / "validate_backend_b007.py"


def load_b006_module():
    path = LANE / "scripts" / "generate_backend_b006.py"
    spec = importlib.util.spec_from_file_location("r011_backend_b006_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load B006 backend helpers: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


b006 = load_b006_module()
g = b006.g
RECORD_PATHS = b006.RECORD_PATHS


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def exact_identity(path: Path, expected: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.is_file():
        raise RuntimeError(f"required exact input missing: {path}")
    raw = path.read_bytes()
    identity = {"bytes": len(raw), "sha256": sha256_bytes(raw)}
    if expected is not None and identity != expected:
        raise RuntimeError(f"exact input identity changed: {path}: {identity}")
    return identity


def rrecord(record_type: str, stable_key: str, **fields: Any) -> dict[str, Any]:
    fields["recorded_at"] = RECORDED_AT
    fields["workflow_id"] = WORKFLOW_ID
    return g.record(record_type, stable_key, **fields)


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def load_jsonl(raw: bytes) -> list[dict[str, Any]]:
    return [json.loads(line) for line in raw.decode("utf-8").splitlines() if line]


def load_base() -> tuple[dict[str, list[dict[str, Any]]], dict[str, bytes], dict[str, Any]]:
    manifest_raw = (LIVE_EXPORTS / "manifest.json").read_bytes()
    if len(manifest_raw) != BASE_MANIFEST_BYTES or sha256_bytes(manifest_raw) != BASE_MANIFEST_SHA256:
        raise RuntimeError("live backend is not the exact admitted R011-B006 base")
    manifest = json.loads(manifest_raw)
    if sum(manifest["record_counts"].values()) != BASE_RECORD_COUNT:
        raise RuntimeError("admitted R011-B006 record count changed")
    by_path = {entry["path"]: entry for entry in manifest["files"]}
    records: dict[str, list[dict[str, Any]]] = {}
    for name, relative in RECORD_PATHS.items():
        raw = (LIVE_EXPORTS / relative).read_bytes()
        entry = by_path[relative]
        if len(raw) != entry["bytes"] or sha256_bytes(raw) != entry["sha256"]:
            raise RuntimeError(f"admitted record payload changed: {relative}")
        rows = load_jsonl(raw)
        if len(rows) != entry["records"] or g.jsonl_bytes(rows) != raw:
            raise RuntimeError(f"admitted record payload is not canonical: {relative}")
        records[name] = rows
    excluded = set(RECORD_PATHS.values()) | {"manifest.json", "identity_map.jsonl"}
    excluded.update(path for path in by_path if path.startswith("views/") or path.startswith("schemas/"))
    auxiliary: dict[str, bytes] = {}
    for relative, entry in by_path.items():
        if relative in excluded:
            continue
        raw = (LIVE_EXPORTS / relative).read_bytes()
        if len(raw) != entry["bytes"] or sha256_bytes(raw) != entry["sha256"]:
            raise RuntimeError(f"admitted auxiliary payload changed: {relative}")
        auxiliary[relative] = raw
    return records, auxiliary, manifest


def record_sha256(row: dict[str, Any]) -> str:
    return sha256_bytes((g.canonical_json(row) + "\n").encode("utf-8"))


def sanitize_profile_paths_in_json(raw: bytes) -> tuple[bytes, int]:
    """Return a deterministic public copy with local user-profile prefixes removed."""

    profile_path = re.compile(r"(?i)[a-z]:[\\/]+users[\\/]+[^\\/\r\n\"]+[\\/]+")
    value = json.loads(raw)

    def rewrite(item: Any) -> tuple[Any, int]:
        if isinstance(item, str):
            updated, count = profile_path.subn(lambda _match: "<local-user-profile>/", item)
            return updated, count
        if isinstance(item, list):
            result: list[Any] = []
            count = 0
            for child in item:
                updated, child_count = rewrite(child)
                result.append(updated)
                count += child_count
            return result, count
        if isinstance(item, dict):
            result: dict[str, Any] = {}
            count = 0
            for key, child in item.items():
                updated, child_count = rewrite(child)
                result[key] = updated
                count += child_count
            return result, count
        return item, 0

    sanitized, replacements = rewrite(value)
    if replacements == 0:
        return raw, 0
    return (json.dumps(sanitized, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"), replacements


def apply_privacy_packaging_revisions(
    records: dict[str, list[dict[str, Any]]], auxiliary: dict[str, bytes], base_manifest: dict[str, Any]
) -> tuple[dict[str, bytes], str, dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """Neutralize active provenance and emit sanitized copies of path-leaking evidence."""

    localizations = records["localizations"]
    if len(localizations) != EXPECTED_BASE_LOCALIZATION_COUNT or base_manifest["record_counts"]["localizations"] != EXPECTED_BASE_LOCALIZATION_COUNT:
        raise RuntimeError("admitted localization inventory changed before privacy packaging")
    provenances = {row.get("translation_provenance") for row in localizations}
    if len(provenances) != 1 or None in provenances:
        raise RuntimeError("admitted translation-provenance inventory changed before privacy packaging")
    legacy_provenance = next(iter(provenances))
    if sha256_bytes(legacy_provenance.encode("utf-8")) != EXPECTED_LEGACY_TRANSLATION_PROVENANCE_SHA256:
        raise RuntimeError("admitted legacy translation-provenance identity changed")
    requester = re.search(r"acting on (?P<token>[^']+)'s request", legacy_provenance)
    if requester is None or not requester.group("token"):
        raise RuntimeError("could not derive the prohibited requester token from the admitted provenance")
    prohibited_token = requester.group("token")

    prior_records: dict[str, dict[str, Any]] = {}
    prior_provenance_sha256 = sha256_bytes(legacy_provenance.encode("utf-8"))
    target_rebind_count = 0
    for row in localizations:
        prior_sha256 = record_sha256(row)
        target_text_rebound = prohibited_token.casefold() in row.get("target_text", "").casefold()
        prior_records[row["id"]] = {
            "id": row["id"],
            "stable_key": row["stable_key"],
            "origin_boundary_id": row.get("boundary_id"),
            "prior_record_sha256": prior_sha256,
            "prior_translation_provenance_sha256": prior_provenance_sha256,
            "target_text_rebound": target_text_rebound,
        }
        if target_text_rebound:
            target_path = row.get("target_path", "")
            if not target_path.startswith("repo/"):
                raise RuntimeError("privacy target-text revision is not rooted in the live canonical source")
            relative = target_path.removeprefix("repo/")
            prior_target_identity = {
                "target_sha256": row.get("target_sha256"),
                "target_file_sha256": row.get("target_file_sha256"),
                "target_span": row.get("target_span"),
            }
            live = g.source_slice(
                g.TARGET_ROOT,
                relative,
                row["target_span"]["line_start"],
                row["target_span"]["line_end"],
            )
            if prohibited_token.casefold() in live["source_text"].casefold():
                raise RuntimeError("live canonical target still contains prohibited requester provenance")
            row["target_span"] = live["source_span"]
            row["target_sha256"] = live["source_sha256"]
            row["target_text"] = live["source_text"]
            row["target_file_sha256"] = g.sha256_file(g.TARGET_ROOT / relative)
            row["target_identity_status"] = "privacy_corrected_canonical_exact_nonadmitted"
            row["privacy_target_supersedes"] = prior_target_identity
            target_rebind_count += 1
        row["translation_provenance"] = NEUTRAL_TRANSLATION_PROVENANCE
        row["prior_active_record_sha256"] = prior_sha256
        row["prior_translation_provenance_sha256"] = prior_provenance_sha256
        row["privacy_revision_status"] = "neutral_requester_provenance_for_public_package"
        row["revision_reason"] = "release_privacy_provenance_neutralization"
        row["revision_boundary_id"] = BOUNDARY_ID
        row["recorded_at"] = RECORDED_AT
        row["workflow_id"] = WORKFLOW_ID
    if target_rebind_count != EXPECTED_PRIVACY_TARGET_REBIND_COUNT:
        raise RuntimeError(f"privacy target-text rebind inventory changed: rebound={target_rebind_count}")

    packaged_auxiliary: dict[str, bytes] = {}
    auxiliary_revisions: list[dict[str, Any]] = []
    for relative, raw in sorted(auxiliary.items()):
        sanitized, replacement_count = sanitize_profile_paths_in_json(raw) if relative.endswith(".json") else (raw, 0)
        packaged_auxiliary[relative] = sanitized
        if replacement_count:
            auxiliary_revisions.append(
                {
                    "path": relative,
                    "replacement_count": replacement_count,
                    "original_bytes": len(raw),
                    "original_sha256": sha256_bytes(raw),
                    "packaged_bytes": len(sanitized),
                    "packaged_sha256": sha256_bytes(sanitized),
                    "sanitization": "absolute local user-profile prefix replaced by task-independent placeholder",
                }
            )
    if len(auxiliary_revisions) != EXPECTED_SANITIZED_AUXILIARY_COUNT:
        raise RuntimeError(f"historical evidence privacy inventory changed: sanitized={len(auxiliary_revisions)}")
    return packaged_auxiliary, prohibited_token, prior_records, auxiliary_revisions


def read_candidate() -> tuple[dict[str, Any], dict[str, Any], dict[str, bytes]]:
    exact_identity(CANDIDATE_MANIFEST_PATH, EXPECTED_CANDIDATE_MANIFEST)
    exact_identity(VALIDATION_RECEIPT_PATH, EXPECTED_VALIDATION_RECEIPT)
    manifest = json.loads(CANDIDATE_MANIFEST_PATH.read_text(encoding="utf-8"))
    receipt = json.loads(VALIDATION_RECEIPT_PATH.read_text(encoding="utf-8"))
    if (
        manifest.get("boundary_id") != BOUNDARY_ID
        or manifest.get("canonical_mutation") is not False
        or manifest.get("authority", {}).get("commit") != EXPECTED_AUTHORITY["commit"]
        or manifest.get("authority", {}).get("tree") != EXPECTED_AUTHORITY["tree"]
        or receipt.get("boundary_id") != BOUNDARY_ID
        or receipt.get("canonical_admission") is not False
        or receipt.get("result") != "PASS_FOR_REVISED_ISOLATED_APPLICATION_REVIEW"
        or receipt.get("deterministic_validation_replay", {}).get("replays") != 2
        or receipt.get("deterministic_validation_replay", {}).get("failure_count") != 0
        or receipt.get("asset_checks", {}).get("promotion_ready") is not False
    ):
        raise RuntimeError("B007 isolated candidate/validation state changed")
    raws: dict[str, bytes] = {}
    for entry in manifest["files"]:
        path = CANDIDATE_ROOT / entry["path"]
        raw = path.read_bytes()
        if len(raw) != entry["bytes"] or sha256_bytes(raw) != entry["sha256"]:
            raise RuntimeError(f"candidate payload identity changed: {entry['path']}")
        raws[entry["path"]] = raw
    raws["CANDIDATE_MANIFEST.json"] = CANDIDATE_MANIFEST_PATH.read_bytes()
    raws["VALIDATION_RECEIPT.json"] = VALIDATION_RECEIPT_PATH.read_bytes()
    return manifest, receipt, raws


def tsv_rows(raw: bytes) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(raw.decode("utf-8"), newline=""), delimiter="\t"))


def exact_line(lines: list[str], text: str) -> int:
    hits = [i for i, value in enumerate(lines, 1) if value == text]
    if len(hits) != 1:
        raise RuntimeError(f"expected one exact line {text!r}; found {len(hits)}")
    return hits[0]


def prefix_lines(lines: list[str], prefix: str, lower_bound: int = 1) -> list[int]:
    return [i for i, value in enumerate(lines, 1) if i >= lower_bound and value.startswith(prefix)]


def balanced_command_end(lines: list[str], start_line: int, command: str) -> int:
    balance = 0
    started = False
    for line_no in range(start_line, len(lines) + 1):
        text = lines[line_no - 1]
        if not started:
            pos = text.find(command)
            if pos < 0:
                raise RuntimeError(f"{command!r} not found on line {start_line}")
            text = text[pos + len(command):]
            started = True
        for index, char in enumerate(text):
            if index > 0 and text[index - 1] == "\\":
                continue
            if char == "{":
                balance += 1
            elif char == "}":
                balance -= 1
        if started and balance == 0:
            return line_no
    raise RuntimeError(f"unclosed command {command!r} at line {start_line}")


def guided_ranges(root: Path, relative: str, section_start: int) -> list[tuple[int, int]]:
    lines = (root / relative).read_text(encoding="utf-8").splitlines()
    starts = prefix_lines(lines, r"\begin{exercisewrap}", section_start)
    if len(starts) != 3:
        raise RuntimeError(f"expected three B007 guided exercises in {relative}, found {len(starts)}")
    ranges: list[tuple[int, int]] = []
    for start in starts:
        foot = next((i for i in range(start, len(lines) + 1) if lines[i - 1].startswith(r"\footnotetext{")), None)
        if foot is None:
            raise RuntimeError("guided exercise lacks public feedback")
        ranges.append((start, balanced_command_end(lines, foot, r"\footnotetext")))
    return ranges


def main_segment_ranges(root: Path, relative: str, target: bool = False) -> list[tuple[int, int, str, str]]:
    lines = (root / relative).read_text(encoding="utf-8").splitlines()
    section_title = r"\section{Studi kasus: vaksin malaria}" if target else r"\section{Case study: malaria vaccine}"
    subsection_titles = (
        [r"\subsection{Variabilitas dalam data}", r"\subsection{Menyimulasikan penelitian}", r"\subsection{Memeriksa independensi}"]
        if target
        else [r"\subsection{Variability within data}", r"\subsection{Simulating the study}", r"\subsection{Checking for independence}"]
    )
    section = exact_line(lines, section_title)
    subs = [exact_line(lines, title) for title in subsection_titles]
    guides = guided_ranges(root, relative, section)
    if not (section < guides[0][0] < subs[0] < guides[1][0] < subs[1] < guides[2][0] < subs[2]):
        raise RuntimeError("B007 instructional topology changed")
    ranges = [
        (section, guides[0][0] - 1, "section_opening", "section-lead"),
        (guides[0][0], guides[0][1], "guided_01", "guided-practice"),
        (subs[0], guides[1][0] - 1, "variability_lead", "subsection-prose"),
        (guides[1][0], guides[1][1], "guided_02", "guided-practice"),
        (guides[1][1] + 1, subs[1] - 1, "variability_continuation", "subsection-prose"),
        (subs[1], guides[2][0] - 1, "simulation_lead", "subsection-prose"),
        (guides[2][0], guides[2][1], "guided_03", "guided-practice"),
        (subs[2], len(lines), "checking_independence", "subsection-prose"),
    ]
    if any(start > end for start, end, _, _ in ranges):
        raise RuntimeError("empty B007 instructional segment")
    return ranges


def marker_ranges(root: Path, relative: str, markers: list[str]) -> list[tuple[int, int]]:
    lines = (root / relative).read_text(encoding="utf-8").splitlines()
    starts = [exact_line(lines, marker) for marker in markers]
    return [(start, starts[i + 1] - 1 if i + 1 < len(starts) else len(lines)) for i, start in enumerate(starts)]


def find_answer_25_range(source_root: Path) -> tuple[int, int]:
    raw = (source_root / ANSWER_PATH).read_bytes()
    lines = raw.splitlines(keepends=True)
    starts = [i for i, line in enumerate(lines, 1) if line.rstrip(b"\r\n") == b"% 25"]
    next_markers = [i for i, line in enumerate(lines, 1) if line.rstrip(b"\r\n") == b"% 27"]
    expected = "84635353bc1dd6edae5ccae6fe44fc9ed574e6ba5cb1f570514d5857c0ee36d6"
    for start in starts:
        end_marker = next((value for value in next_markers if value > start), None)
        if end_marker is None:
            continue
        answer_start = next(
            (value for value in range(start + 1, end_marker) if lines[value - 1].startswith(b"\\eocesol{")),
            None,
        )
        if answer_start is None:
            continue
        end = end_marker - 2 if lines[end_marker - 2].strip() == b"" else end_marker - 1
        byte_start = sum(len(line) for line in lines[: answer_start - 1])
        byte_end = sum(len(line) for line in lines[:end])
        # The candidate manifest identifies the TeX block without its terminal LF.
        if sha256_bytes(raw[byte_start:byte_end].rstrip(b"\r\n")) == expected:
            return answer_start, end
    raise RuntimeError("pinned Chapter 2 public answer 25 span not found by exact hash")


def clean_source_meta(root: Path, relative: str, start: int, end: int) -> dict[str, Any]:
    value = g.source_slice(root, relative, start, end)
    value.pop("source_text", None)
    return value


def target_meta(
    root: Path,
    relative: str,
    start: int,
    end: int,
    *,
    path_prefix: str,
    identity_status: str,
) -> dict[str, Any]:
    value = g.source_slice(root, relative, start, end)
    return {
        "target_path": f"{path_prefix}/{relative}",
        "target_span": value["source_span"],
        "target_sha256": value["source_sha256"],
        "target_text": value["source_text"],
        "target_file_sha256": g.sha256_file(root / relative),
        "target_identity_status": identity_status,
    }


def find_canonical_answer_25_range() -> tuple[int, int]:
    """Locate the exact translated candidate answer inside canonical answers."""
    candidate_text = (CANDIDATE_ROOT / TARGET_ANSWER_PATH).read_text(encoding="utf-8")
    answer_text = candidate_text[candidate_text.index(r"\eocesol{"):].rstrip("\r\n")
    canonical_path = g.TARGET_ROOT / ANSWER_PATH
    canonical_text = canonical_path.read_text(encoding="utf-8")
    if canonical_text.count(answer_text) != 1:
        raise RuntimeError("translated public answer 2.25 does not occur exactly once in canonical answers")
    byte_start = len(canonical_text[:canonical_text.index(answer_text)].encode("utf-8"))
    byte_end = byte_start + len(answer_text.encode("utf-8"))
    raw = canonical_path.read_bytes()
    line_start = raw[:byte_start].count(b"\n") + 1
    line_end = raw[:byte_end].count(b"\n") + 1
    replay = g.source_slice(g.TARGET_ROOT, ANSWER_PATH, line_start, line_end)
    if replay["source_text"].rstrip("\r\n") != answer_text:
        raise RuntimeError("canonical public answer 2.25 line-range replay changed")
    return line_start, line_end


def protected_tokens(text: str) -> list[str]:
    patterns = [
        ("label", r"\\label\{([^{}]+)\}"),
        ("ref", r"\\(?:ref|autoref)\{([^{}]+)\}"),
        ("cite", r"\\(?:cite|footfullcite)\{([^{}]+)\}"),
        ("var", r"\\var\{([^{}]+)\}"),
        ("resp", r"\\resp\{([^{}]+)\}"),
        ("texttt", r"\\texttt\{([^{}]+)\}"),
        ("newcommand", r"\\newcommand\{\\([^{}]+)\}"),
    ]
    values: list[str] = []
    for prefix, pattern in patterns:
        values.extend(f"{prefix}:{match}" for match in re.findall(pattern, text))
    values.extend(f"math:{match}" for match in re.findall(r"(?<!\\)\$([^$]+)(?<!\\)\$", text))
    return values


def source_file_meta(source_root: Path, relative: str) -> dict[str, Any]:
    raw = (source_root / relative).read_bytes()
    return {"source_path": relative, "source_sha256": sha256_bytes(raw), "source_span": None}


def add_relation(records: dict[str, list[dict[str, Any]]], stable_suffix: str, relation_type: str, from_id: str, to_id: str, order: int = 1, qualifier: str = "") -> None:
    records["relations"].append(
        rrecord(
            "relation",
            f"r011/relation/b007-{stable_suffix}",
            relation_type=relation_type,
            from_id=from_id,
            to_id=to_id,
            qualifier=qualifier,
            order=order,
            resource_id=g.stable_id("r011/resource/openintro-statistics"),
            edition_id=g.stable_id("r011/edition/fee25091"),
            source_local_ids=[BOUNDARY_ID],
            parent_id=None,
            source_path=None,
            source_span=None,
            source_sha256=None,
            locale="zxx",
            translation_state=None,
            rights_component_ids=[],
            boundary_id=BOUNDARY_ID,
        )
    )


TERM_DEFINITIONS = {
    "malaria vaccine": "A vaccine intended to reduce malaria infection risk.",
    "variability within data": "Observed differences among data values or statistics produced from samples or assignments.",
    "drug-sensitive strain": "A pathogen strain susceptible to an available drug treatment.",
    "infection rate": "The proportion of individuals in a group who develop an infection.",
    "random noise": "Sample-to-sample fluctuation attributable to chance rather than a systematic relationship.",
    "independence model": "A model under which the variables have no relationship and observed differences arise from chance.",
    "alternative model": "A competing model under which the variables are associated and the observed difference is not explained by chance alone.",
    "simulation": "A computational or physical repetition of a chance process under specified assumptions.",
    "statistical inference": "The use of data and probability models to evaluate claims about a broader process or population.",
    "model selection": "Choosing which competing model is most reasonable given observed data.",
    "retrospective observational study": "An observational study that analyzes outcomes and exposures recorded in the past.",
    "relative frequency histogram": "A histogram whose vertical scale gives proportions or relative frequencies rather than counts.",
    "cardiovascular event": "A medically recorded event involving the heart or blood vessels.",
    "heart transplant": "A surgical procedure that replaces a failing heart with a donor heart.",
    "survival time": "Elapsed time until death or another defined terminal event.",
    "null hypothesis": "The formal baseline claim, represented here by an independence model.",
    "alternative hypothesis": "The formal competing claim, represented here by an association model.",
    "convincing evidence": "Evidence sufficiently inconsistent with a baseline model to support a competing claim.",
    "probability": "A numerical measure of how likely an event is under a specified chance model.",
}

TERM_INTRO_UNIT = {
    "malaria vaccine": "variability",
    "variability within data": "variability",
    "drug-sensitive strain": "variability",
    "infection rate": "variability",
    "random noise": "variability",
    "independence model": "variability",
    "alternative model": "variability",
    "simulation": "simulation",
    "randomization": "simulation",
    "statistical inference": "checking",
    "model selection": "checking",
    "retrospective observational study": "exercise25",
    "relative frequency histogram": "exercise25",
    "cardiovascular event": "exercise25",
    "heart transplant": "exercise26",
    "survival time": "exercise26",
    "null hypothesis": "exercise25",
    "alternative hypothesis": "exercise25",
    "convincing evidence": "checking",
    "probability": "checking",
}

PREREQUISITES = [
    ("proportion", "infection rate"),
    ("variability", "variability within data"),
    ("independent", "independence model"),
    ("dependent", "alternative model"),
    ("randomization", "simulation"),
    ("simulation", "statistical inference"),
    ("independence model", "null hypothesis"),
    ("alternative model", "alternative hypothesis"),
    ("histogram", "relative frequency histogram"),
    ("relative frequency", "relative frequency histogram"),
    ("observational study", "retrospective observational study"),
    ("random noise", "convincing evidence"),
    ("statistical inference", "model selection"),
    ("probability", "statistical inference"),
]

EXERCISE_CONCEPTS = {
    25: ["retrospective observational study", "relative frequency histogram", "cardiovascular event", "null hypothesis", "alternative hypothesis", "independence model", "alternative model", "simulation"],
    26: ["heart transplant", "survival time", "box plot", "mosaic plot", "randomization", "simulation", "independence model", "alternative model"],
}


def build_records() -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    records, base_auxiliary, base_manifest = load_base()
    base_auxiliary, prohibited_token, privacy_prior_records, privacy_auxiliary_revisions = apply_privacy_packaging_revisions(
        records, base_auxiliary, base_manifest
    )
    candidate, candidate_receipt, candidate_raws = read_candidate()
    exact_identity(FIELD_QA_PATH, EXPECTED_FIELD_QA)
    exact_identity(FIELD_QA_NOTE_PATH, EXPECTED_FIELD_QA_NOTE)
    exact_identity(SOURCE_APPLICATION_MANIFEST_PATH, EXPECTED_SOURCE_APPLICATION_MANIFEST)
    exact_identity(SOURCE_APPLICATION_RECEIPT_PATH, EXPECTED_SOURCE_APPLICATION_RECEIPT)
    exact_identity(SOURCE_GATE_QA_PATH, EXPECTED_SOURCE_GATE_QA)
    exact_identity(ASSET_PROMOTION_RECEIPT_PATH, EXPECTED_ASSET_PROMOTION_RECEIPT)
    exact_identity(ASSET_LOCALIZATION_RECEIPT_PATH, EXPECTED_ASSET_LOCALIZATION_RECEIPT)
    exact_identity(ASSET_OUTPUT_MANIFEST_PATH, EXPECTED_ASSET_OUTPUT_MANIFEST)
    exact_identity(ASSET_PRIVACY_QA_PATH, EXPECTED_ASSET_PRIVACY_QA)
    field_qa_raw = FIELD_QA_PATH.read_bytes()
    field_qa_note_raw = FIELD_QA_NOTE_PATH.read_bytes()
    source_application_manifest_raw = SOURCE_APPLICATION_MANIFEST_PATH.read_bytes()
    source_application_receipt_raw = SOURCE_APPLICATION_RECEIPT_PATH.read_bytes()
    source_gate_qa_raw = SOURCE_GATE_QA_PATH.read_bytes()
    asset_promotion_raw = ASSET_PROMOTION_RECEIPT_PATH.read_bytes()
    asset_localization_raw = ASSET_LOCALIZATION_RECEIPT_PATH.read_bytes()
    asset_output_manifest_raw = ASSET_OUTPUT_MANIFEST_PATH.read_bytes()
    asset_privacy_qa_raw = ASSET_PRIVACY_QA_PATH.read_bytes()
    field_qa = json.loads(field_qa_raw)
    source_application_manifest = json.loads(source_application_manifest_raw)
    source_application_receipt = json.loads(source_application_receipt_raw)
    source_gate_qa = json.loads(source_gate_qa_raw)
    asset_promotion = json.loads(asset_promotion_raw)
    asset_localization = json.loads(asset_localization_raw)
    asset_output_manifest = json.loads(asset_output_manifest_raw)
    asset_privacy_qa = json.loads(asset_privacy_qa_raw)
    field_decisions = {item["term_id"]: item for item in field_qa.get("decisions", [])}
    expected_asset_promotion_binding = {
        "path": ASSET_PROMOTION_RECEIPT_PATH.relative_to(LANE).as_posix(),
        **EXPECTED_ASSET_PROMOTION_RECEIPT,
    }
    expected_asset_privacy_binding = {
        "path": ASSET_PRIVACY_QA_PATH.relative_to(LANE).as_posix(),
        **EXPECTED_ASSET_PRIVACY_QA,
    }
    expected_changed_decisions = {
        "R011-TERM-0088": ("bin", "interval kelas (bin)", "refine_and_propagate"),
        "R011-TERM-0150": ("statistical inference", "statistika inferensial", "refine_and_propagate"),
        "R011-TERM-0160": ("probability", "peluang (probabilitas)", "add_scoped_term"),
    }
    if (
        field_qa.get("boundary_id") != BOUNDARY_ID
        or field_qa.get("status") != "decisions_final_propagation_in_progress"
        or field_qa.get("errors") != []
        or field_qa.get("blockers") != []
        or any(
            term_id not in field_decisions
            or (field_decisions[term_id].get("source_term"), field_decisions[term_id].get("after"), field_decisions[term_id].get("decision")) != expected
            for term_id, expected in expected_changed_decisions.items()
        )
    ):
        raise RuntimeError("exact terminology field-QA decisions changed")
    if (
        source_application_manifest.get("boundary_id") != BOUNDARY_ID
        or source_application_manifest.get("status") != "source_applied_assets_promoted"
        or source_application_receipt.get("boundary_id") != BOUNDARY_ID
        or source_application_receipt.get("result") != "PASS_SOURCE_APPLICATION_AND_ASSET_BINDING"
        or source_application_receipt.get("remaining_source_or_asset_dependency") is not None
        or source_gate_qa.get("boundary_id") != BOUNDARY_ID
        or source_gate_qa.get("result") != "PASS_SOURCE_GATE_ASSETS_BOUND"
        or source_gate_qa.get("checks", {}).get("count") != 14
        or source_gate_qa.get("checks", {}).get("failure_count") != 0
        or source_gate_qa.get("adversarial_self_tests", {}).get("count") != 14
        or source_gate_qa.get("adversarial_self_tests", {}).get("failure_count") != 0
        or source_gate_qa.get("replay_contract", {}).get("expected_identical_replays") != 2
        or source_gate_qa.get("remaining_source_or_asset_dependency") is not None
        or source_application_manifest.get("asset_promotion", {}).get("promotion_receipt") != expected_asset_promotion_binding
        or source_application_receipt.get("asset_promotion", {}).get("promotion_receipt") != expected_asset_promotion_binding
        or source_application_manifest.get("privacy_remediation", {}).get("asset_privacy_refresh_qa") != expected_asset_privacy_binding
        or source_application_receipt.get("privacy_remediation", {}).get("asset_privacy_refresh_qa") != expected_asset_privacy_binding
        or source_gate_qa.get("privacy_remediation", {}).get("asset_privacy_refresh_qa") != expected_asset_privacy_binding
        or source_gate_qa.get("privacy_remediation", {}).get("canonical_repo_scan", {}).get("prohibited_token_path_count") != 0
        or source_gate_qa.get("privacy_remediation", {}).get("canonical_repo_scan", {}).get("absolute_profile_path_count") != 0
    ):
        raise RuntimeError("exact B007 source application gate changed")
    if (
        asset_promotion.get("boundary_id") != BOUNDARY_ID
        or asset_promotion.get("status") != "canonical_promotion_complete"
        or asset_promotion.get("operation_count") != 13
        or asset_promotion.get("localized_pdf_count") != 5
        or asset_promotion.get("english_witness_count") != 5
        or asset_promotion.get("localized_R_producer_count") != 3
        or asset_promotion.get("all_destination_byte_and_hash_checks_pass") is not True
        or asset_promotion.get("blocker") is not None
        or asset_promotion.get("qa") != {
            "P0": 0,
            "P1": 0,
            "P2": 0,
            "P3": 0,
            "all_points_visible_in_poppler_and_mupdf": True,
            "portable_point_asset_count": 2,
            "portable_point_source_glyph_runs": 1418,
            "portable_point_unique_visual_centres": 200,
        }
        or asset_localization.get("boundary_id") != BOUNDARY_ID
        or asset_localization.get("status") != "qa_pass_awaiting_root_promotion_approval"
        or asset_localization.get("qa", {}).get("P0_P1_P2_zero") is not True
        or asset_output_manifest.get("boundary_id") != BOUNDARY_ID
        or asset_output_manifest.get("final_pdf_count") != 5
        or asset_output_manifest.get("source_witness_count") != 5
        or asset_privacy_qa.get("boundary_id") != BOUNDARY_ID
        or asset_privacy_qa.get("status") != "pass_privacy_and_portability_ready_for_canonical_promotion"
        or asset_privacy_qa.get("privacy", {}).get("prohibited_requester_token_hits") != 0
        or asset_privacy_qa.get("privacy", {}).get("absolute_profile_path_hits") != 0
        or asset_privacy_qa.get("privacy", {}).get("avandia_author_is_neutral") is not True
        or asset_privacy_qa.get("determinism", {}).get("all_byte_identical") is not True
        or asset_privacy_qa.get("portable_points", {}).get("all_points_visible_in_poppler_and_mupdf") is not True
        or asset_privacy_qa.get("portable_points", {}).get("all_source_coordinate_multisets_preserved") is not True
    ):
        raise RuntimeError("exact B007 asset localization/promotion closure changed")
    authority, source_root = g.read_authority()
    if authority["commit"] != EXPECTED_AUTHORITY["commit"] or authority["calculated_git_tree_sha1"] != EXPECTED_AUTHORITY["tree"]:
        raise RuntimeError("pinned upstream authority changed")

    resource_id = g.stable_id("r011/resource/openintro-statistics")
    edition_id = g.stable_id("r011/edition/fee25091")
    chapter_id = g.stable_id("r011/unit/source-label/ch_summarizing_data")
    default_rights_id = g.stable_id("r011/rights/upstream-cc-by-sa-3.0")
    o001_rights_id = g.stable_id("r011/rights/o001-original-companion-planned")
    package_rights_id = g.stable_id("r011/rights/openintro-r-package-gpl-3")
    generated_rights_key = "r011/rights/b007-generated-figure-expression"
    generated_rights_id = g.stable_id(generated_rights_key)
    data_rights_key = "r011/rights/b007-code-and-factual-data"
    data_rights_id = g.stable_id(data_rights_key)

    main_source_ranges = main_segment_ranges(source_root, MAIN_PATH)
    main_target_ranges = main_segment_ranges(g.TARGET_ROOT, MAIN_PATH, target=True)
    source_exercise_ranges = marker_ranges(source_root, EXERCISE_PATH, ["% 25", "% 26"])
    target_exercise_ranges = marker_ranges(g.TARGET_ROOT, EXERCISE_PATH, ["% 25", "% 26"])
    source_answer_range = find_answer_25_range(source_root)
    target_answer_range = find_canonical_answer_25_range()
    if [item[2:] for item in main_source_ranges] != [item[2:] for item in main_target_ranges]:
        raise RuntimeError("source/target semantic segmentation labels changed")

    source_section_meta = clean_source_meta(source_root, MAIN_PATH, main_source_ranges[0][0], main_source_ranges[-1][1])
    subsection_source_ranges = {
        "variability": (main_source_ranges[2][0], main_source_ranges[4][1]),
        "simulation": (main_source_ranges[5][0], main_source_ranges[6][1]),
        "checking": (main_source_ranges[7][0], main_source_ranges[7][1]),
    }
    section_key = "r011/unit/source-label/caseStudyMalariaVaccine"
    section_id = g.stable_id(section_key)
    records["units"].append(
        rrecord(
            "unit", section_key, unit_type="section", title="Case study: malaria vaccine",
            resource_id=resource_id, edition_id=edition_id, source_local_ids=["caseStudyMalariaVaccine", BOUNDARY_ID],
            parent_id=chapter_id, order=4, locale="en", translation_state="source_frozen",
            rights_component_ids=[default_rights_id], boundary_id=BOUNDARY_ID, **source_section_meta,
        )
    )
    unit_ids: dict[str, str] = {"section": section_id}
    subsection_specs = [
        ("variability", "r011/unit/source-label/variabilityWithinData", "Variability within data", ["variabilityWithinData"]),
        ("simulation", "r011/unit/source-label/simulatingTheStudy", "Simulating the study", ["simulatingTheStudy"]),
        ("checking", "r011/unit/ch02/sec2.3/checking-for-independence", "Checking for independence", []),
    ]
    for order, (name, key, title, local_ids) in enumerate(subsection_specs, 1):
        meta = clean_source_meta(source_root, MAIN_PATH, *subsection_source_ranges[name])
        uid = g.stable_id(key)
        unit_ids[name] = uid
        records["units"].append(
            rrecord(
                "unit", key, unit_type="subsection", title=title, resource_id=resource_id, edition_id=edition_id,
                source_local_ids=local_ids + [f"sec2.3-subsection-{order}", BOUNDARY_ID], parent_id=section_id,
                order=order, locale="en", translation_state="source_frozen", rights_component_ids=[default_rights_id],
                boundary_id=BOUNDARY_ID, **meta,
            )
        )

    guide_parent = [section_id, unit_ids["variability"], unit_ids["simulation"]]
    guide_keys = [
        "r011/unit/guided-practice/ch02-sec2.3-01",
        "r011/unit/guided-practice/ch02-sec2.3-02",
        "r011/unit/source-label/malaria_vaccine_20_exp_summary_rand_1_diff",
    ]
    guide_titles = [
        "Guided practice: independence of seat side and Apple ownership",
        "Guided practice: study type and causal inference",
        "Guided practice: simulated infection-rate difference",
    ]
    guide_segments = [main_source_ranges[1], main_source_ranges[3], main_source_ranges[6]]
    for index, (key, title, span, parent) in enumerate(zip(guide_keys, guide_titles, guide_segments, guide_parent), 1):
        uid = g.stable_id(key)
        unit_ids[f"guide{index}"] = uid
        local_ids = [f"sec2.3-guided-{index:02d}", BOUNDARY_ID]
        if index == 3:
            local_ids.insert(0, "malaria_vaccine_20_exp_summary_rand_1_diff")
        records["units"].append(
            rrecord(
                "unit", key, unit_type="exercise", exercise_role="guided_practice_with_public_feedback",
                answer_availability="inline_public_feedback", title=title, resource_id=resource_id, edition_id=edition_id,
                source_local_ids=local_ids, parent_id=parent, order=index, locale="en", translation_state="source_frozen",
                rights_component_ids=[default_rights_id], boundary_id=BOUNDARY_ID,
                **clean_source_meta(source_root, MAIN_PATH, span[0], span[1]),
            )
        )

    exercise_specs = [(25, "randomization_avandia", "Side effects of Avandia"), (26, "randomization_heart_transplants", "Heart transplants")]
    for (number, label, title), span in zip(exercise_specs, source_exercise_ranges):
        key = f"r011/unit/exercise/2.{number}/{label}"
        uid = g.stable_id(key)
        unit_ids[f"exercise{number}"] = uid
        records["units"].append(
            rrecord(
                "unit", key, unit_type="exercise", title=f"Exercise 2.{number}: {title}", resource_id=resource_id,
                edition_id=edition_id, source_local_ids=[label, f"eoce_2_{number}", BOUNDARY_ID], parent_id=section_id,
                order=number, locale="en", answer_availability="public_appendix" if number == 25 else "none_public_upstream",
                translation_state="source_frozen", rights_component_ids=[default_rights_id], boundary_id=BOUNDARY_ID,
                **clean_source_meta(source_root, EXERCISE_PATH, span[0], span[1]),
            )
        )
    solution_key = "r011/unit/solution/2.25"
    solution_id = g.stable_id(solution_key)
    unit_ids["solution25"] = solution_id
    records["units"].append(
        rrecord(
            "unit", solution_key, unit_type="solution", title="Public answer 2.25", resource_id=resource_id,
            edition_id=edition_id, source_local_ids=["eoce_solution_2_25", BOUNDARY_ID], parent_id=unit_ids["exercise25"],
            order=25, locale="en", answer_availability="public_appendix", translation_state="source_frozen",
            rights_component_ids=[default_rights_id], boundary_id=BOUNDARY_ID,
            **clean_source_meta(source_root, ANSWER_PATH, *source_answer_range),
        )
    )
    gap_key = "r011/unit/o001-gap/2.26"
    gap_id = g.stable_id(gap_key)
    unit_ids["gap26"] = gap_id
    records["units"].append(
        rrecord(
            "unit", gap_key, unit_type="companion_gap", title="O001 mastery-companion answer gap for exercise 2.26",
            resource_id=resource_id, edition_id=edition_id,
            source_local_ids=["O001", "R011-B007-O001-0001", "eoce_2_26", BOUNDARY_ID], parent_id=unit_ids["exercise26"],
            order=1, locale="en", answer_availability="none_public_upstream", gap_reason="no_public_answer_upstream",
            authoring_mode="independent_original_required", source_solution_used=False, translation_state="queued",
            status="planned", rights_component_ids=[o001_rights_id], boundary_id=BOUNDARY_ID,
            source_path=None, source_span=None, source_sha256=None,
        )
    )

    add_relation(records, "contains-section", "contains", chapter_id, section_id, 4)
    for name, _, _, _ in subsection_specs:
        add_relation(records, f"contains-{name}", "contains", section_id, unit_ids[name])
    for index in range(1, 4):
        add_relation(records, f"contains-guide-{index:02d}", "contains", guide_parent[index - 1], unit_ids[f"guide{index}"], index)
    for number in (25, 26):
        add_relation(records, f"contains-exercise-{number}", "contains", section_id, unit_ids[f"exercise{number}"], number)
    add_relation(records, "contains-answer-25", "contains", unit_ids["exercise25"], solution_id, 1)
    add_relation(records, "contains-o001-gap-26", "contains", unit_ids["exercise26"], gap_id, 1)
    add_relation(records, "answer-2-25", "answers", solution_id, unit_ids["exercise25"], 25, "public appendix")
    add_relation(records, "o001-gap-2-26", "requires_companion_answer", unit_ids["exercise26"], gap_id, 26, "O001 independent original")
    add_relation(records, "precedes-b006-b007", "precedes", g.stable_id("r011/unit/source-label/categoricalData"), section_id, 1, "source order")

    segment_specs: list[dict[str, Any]] = []
    main_unit_for_name = {
        "section_opening": section_id, "guided_01": unit_ids["guide1"], "variability_lead": unit_ids["variability"],
        "guided_02": unit_ids["guide2"], "variability_continuation": unit_ids["variability"],
        "simulation_lead": unit_ids["simulation"], "guided_03": unit_ids["guide3"],
        "checking_independence": unit_ids["checking"],
    }
    unit_segment_orders: dict[str, int] = {}
    for source_span, target_span in zip(main_source_ranges, main_target_ranges):
        start, end, name, kind = source_span
        tstart, tend, _, _ = target_span
        unit_id = main_unit_for_name[name]
        unit_segment_orders[unit_id] = unit_segment_orders.get(unit_id, 0) + 1
        segment_specs.append({"name": name, "kind": kind, "unit_id": unit_id, "order": unit_segment_orders[unit_id],
                              "source": (MAIN_PATH, start, end), "target": (MAIN_PATH, tstart, tend)})
    for index, ((number, _, _), source_span, target_span) in enumerate(zip(exercise_specs, source_exercise_ranges, target_exercise_ranges), 1):
        segment_specs.append({"name": f"exercise_{number}", "kind": "end-of-section-exercise", "unit_id": unit_ids[f"exercise{number}"],
                              "order": 1, "source": (EXERCISE_PATH, *source_span), "target": (EXERCISE_PATH, *target_span)})
    segment_specs.append({"name": "public_answer_25", "kind": "public-answer", "unit_id": solution_id, "order": 1,
                          "source": (ANSWER_PATH, *source_answer_range), "target": (ANSWER_PATH, *target_answer_range)})
    if len(segment_specs) != 11:
        raise RuntimeError("B007 segment inventory must contain exactly eleven source/target mappings")
    segment_ids: dict[str, str] = {}
    for offset, spec in enumerate(segment_specs, 173):
        stable_key = f"r011/segment/seg{offset:04d}"
        segment_id = g.stable_id(stable_key)
        segment_ids[spec["name"]] = segment_id
        source_relative, source_start, source_end = spec["source"]
        target_relative, target_start, target_end = spec["target"]
        source = g.source_slice(source_root, source_relative, source_start, source_end)
        target = target_meta(
            g.TARGET_ROOT,
            target_relative,
            target_start,
            target_end,
            path_prefix="repo",
            identity_status="canonical_source_exact_nonadmitted",
        )
        target_state = "language_reviewed"
        terminology_supersession: list[dict[str, str]] = []
        if spec["name"] == "checking_independence":
            terminology_supersession = [
                {
                    "term_id": "R011-TERM-0150",
                    "before": "inferensi statistika",
                    "after": "statistika inferensial",
                    "status": "exact canonical target-span propagated_nonadmitted",
                }
            ]
        source_tokens = protected_tokens(source["source_text"])
        target_tokens = protected_tokens(target["target_text"])
        records["segments"].append(
            rrecord(
                "segment", stable_key, segment_kind=spec["kind"], unit_id=spec["unit_id"], resource_id=resource_id,
                edition_id=edition_id, source_local_ids=[BOUNDARY_ID], parent_id=spec["unit_id"], order=spec["order"],
                locale="en", source_locale="en", target_locales=["id-ID"], protected_tokens=source_tokens,
                translation_state="source_frozen", rights_component_ids=[default_rights_id], boundary_id=BOUNDARY_ID,
                **source,
            )
        )
        localization_key = f"r011/localization/id-ID/seg{offset:04d}"
        localization_id = g.stable_id(localization_key)
        records["localizations"].append(
            rrecord(
                "localization", localization_key, source_segment_id=segment_id, unit_id=spec["unit_id"], resource_id=resource_id,
                edition_id=edition_id, source_local_ids=[BOUNDARY_ID], parent_id=segment_id, order=1, locale="id-ID",
                source_locale="en", target_locale="id-ID", source_path=source["source_path"], source_span=source["source_span"],
                source_sha256=source["source_sha256"], source_protected_tokens=source_tokens,
                target_protected_tokens=target_tokens, protected_tokens=target_tokens,
                protected_token_delta={"added": [], "removed": [], "authorized": True, "reason": "Whole-file structural sequence equality and visible index-alias deltas are bound by the isolated candidate validation receipt."},
                translation_provenance=NEUTRAL_TRANSLATION_PROVENANCE,
                translation_state=target_state, rights_component_ids=[default_rights_id], boundary_id=BOUNDARY_ID,
                candidate_validation_receipt="scratch/R011-B007-candidate/VALIDATION_RECEIPT.json",
                terminology_field_qa="qa/terminology/R011_TERMINOLOGY_FIELD_USAGE_QA.json",
                terminology_supersession=terminology_supersession,
                **target,
            )
        )
        add_relation(records, f"contains-seg{offset:04d}", "contains", spec["unit_id"], segment_id, spec["order"], spec["kind"])
        add_relation(records, f"translates-seg{offset:04d}", "translates", segment_id, localization_id, 1, "exact canonical id-ID target span; backend nonadmitted")

    # Rebind only active localization records affected by the final field-term
    # decisions and the B007 localized-edition scope line. IDs/stable keys/source
    # semantics remain fixed; immutable prior evidence is copied without edits.
    active_overlay_revisions: list[dict[str, Any]] = []
    replacements = [
        ("Kelas-kelas interval", "Interval-interval kelas", "R011-TERM-0088"),
        ("Kelas interval", "Interval kelas", "R011-TERM-0088"),
        ("kelas-kelas interval", "interval-interval kelas", "R011-TERM-0088"),
        ("kelas interval", "interval kelas", "R011-TERM-0088"),
        ("inferensi statistika", "statistika inferensial", "R011-TERM-0150"),
        (
            "\\item Bab~\\ref{ch_intro_to_data},\n    Bagian~\\ref{numericalData},\n    dan Bagian~\\ref{categoricalData} untuk memperoleh",
            "\\item Bab~\\ref{ch_intro_to_data} dan\n    Bagian~\\ref{numericalData}--\\ref{caseStudyMalariaVaccine}\n    untuk memperoleh",
            "R011-B007-SCOPE",
        ),
    ]
    for row in records["localizations"]:
        prior_text = row.get("target_text", "")
        expected_text = prior_text
        applied_supersessions: list[dict[str, str]] = []
        for before, after, term_id in replacements:
            if before in expected_text:
                applied_supersessions.append(
                    {
                        "term_id": term_id,
                        "before": before,
                        "after": after,
                        "status": "exact canonical target-span propagated_nonadmitted",
                    }
                )
            expected_text = expected_text.replace(before, after)
        if expected_text == prior_text:
            continue
        prior_identity = {
            "target_sha256": row.get("target_sha256"),
            "target_file_sha256": row.get("target_file_sha256"),
            "target_span": row.get("target_span"),
        }
        target_path = row["target_path"]
        if target_path.startswith("repo/"):
            target_root = g.TARGET_ROOT
            relative = target_path.removeprefix("repo/")
            identity_status = (
                "terminology_and_scope_propagated_canonical_nonadmitted"
                if any(item["term_id"] == "R011-B007-SCOPE" for item in applied_supersessions)
                else "terminology_field_qa_propagated_canonical_nonadmitted"
            )
        elif target_path.startswith("scratch/R011-B007-candidate/"):
            target_root = CANDIDATE_ROOT
            relative = target_path.removeprefix("scratch/R011-B007-candidate/")
            identity_status = "isolated_candidate_exact_field_qa_propagated_nonadmitted"
        else:
            raise RuntimeError(f"unsupported active localization target path: {target_path}")
        line_start = row["target_span"]["line_start"]
        line_end = row["target_span"]["line_end"]
        live = g.source_slice(target_root, relative, line_start, line_end)
        if live["source_text"] != expected_text:
            raise RuntimeError(
                f"terminology propagation does not replay exact active localization {row['stable_key']} at {target_path}:{line_start}-{line_end}"
            )
        row["target_span"] = live["source_span"]
        row["target_sha256"] = live["source_sha256"]
        row["target_text"] = live["source_text"]
        row["target_file_sha256"] = g.sha256_file(target_root / relative)
        row["target_identity_status"] = identity_status
        row["translation_state"] = "language_reviewed"
        row["recorded_at"] = RECORDED_AT
        row["workflow_id"] = WORKFLOW_ID
        row["revision_boundary_id"] = BOUNDARY_ID
        row["terminology_field_qa"] = "qa/terminology/R011_TERMINOLOGY_FIELD_USAGE_QA.json"
        row["terminology_supersession"] = applied_supersessions
        row["supersedes_target_identity"] = prior_identity
        active_overlay_revisions.append(
            {
                "id": row["id"], "stable_key": row["stable_key"], "origin_boundary_id": row.get("boundary_id"),
                "target_path": target_path, "prior_target_sha256": prior_identity["target_sha256"],
                "target_sha256": row["target_sha256"], "target_file_sha256": row["target_file_sha256"],
                "term_ids": [item["term_id"] for item in applied_supersessions],
            }
        )
    if not active_overlay_revisions or any(
        before in row.get("target_text", "")
        for row in records["localizations"] for before, _after, _term_id in replacements
    ):
        raise RuntimeError("active localization views still contain obsolete field terminology")

    term_rows = tsv_rows(candidate_raws["TERMINOLOGY_PROPOSALS.tsv"])
    if len(term_rows) != 20 or [row["candidate_term_id"] for row in term_rows] != [f"R011-B007-TERM-{n:04d}" for n in range(1, 21)]:
        raise RuntimeError("B007 terminology candidate inventory changed")
    term_by_source = {row["source_en"]: row for row in term_rows}
    global_term_ids = {
        "malaria vaccine": "R011-TERM-0142", "variability within data": "R011-TERM-0143",
        "drug-sensitive strain": "R011-TERM-0144", "infection rate": "R011-TERM-0145",
        "random noise": "R011-TERM-0146", "independence model": "R011-TERM-0147",
        "alternative model": "R011-TERM-0148", "simulation": "R011-TERM-0149",
        "statistical inference": "R011-TERM-0150", "model selection": "R011-TERM-0151",
        "retrospective observational study": "R011-TERM-0152", "relative frequency histogram": "R011-TERM-0153",
        "cardiovascular event": "R011-TERM-0154", "heart transplant": "R011-TERM-0155",
        "survival time": "R011-TERM-0156", "null hypothesis": "R011-TERM-0157",
        "alternative hypothesis": "R011-TERM-0158", "convincing evidence": "R011-TERM-0159",
    }
    existing_concepts = {row.get("preferred_source_term"): row for row in records["concepts"]}
    existing_terms = {row.get("source_term"): row for row in records["terms"]}
    concept_ids: dict[str, str] = {}
    field_term_ids: dict[str, str] = {}
    main_file_meta = source_file_meta(source_root, MAIN_PATH)
    randomization_row = term_by_source["randomization"]
    existing_randomization = existing_terms.get("randomization")
    randomization_concept = existing_concepts.get("randomization")
    if existing_randomization is None or randomization_concept is None or existing_randomization.get("target_term") != randomization_row["target_id_ID"]:
        raise RuntimeError("admitted randomization terminology does not match B007 reuse decision")
    concept_ids["randomization"] = randomization_concept["id"]
    add_relation(records, "reuses-term-randomization", "uses", unit_ids[TERM_INTRO_UNIT["randomization"]], existing_randomization["id"], len(records["terms"]) + 1, "admitted TERM-0062 reused without mutation")

    # Candidate "case study" is a localized title phrase, not a controlled
    # mathematical-statistics term.  The field-QA sequence therefore begins at
    # TERM-0142 with malaria vaccine and adds scoped probability as TERM-0160.
    for concept_order, (source_term, global_term_id) in enumerate(global_term_ids.items(), len(records["concepts"]) + 1):
        row = term_by_source[source_term]
        definition = TERM_DEFINITIONS[source_term]
        concept_key = f"r011/concept/{slugify(source_term)}"
        term_key = f"r011/term/id-ID/{slugify(source_term)}"
        concept_id = g.stable_id(concept_key)
        concept_ids[source_term] = concept_id
        source_ids = [global_term_id, row["candidate_term_id"], BOUNDARY_ID]
        records["concepts"].append(
            rrecord(
                "concept", concept_key, preferred_source_term=source_term, definition=definition, resource_id=resource_id,
                edition_id=edition_id, source_local_ids=source_ids, parent_id=None, order=concept_order, locale="zxx",
                translation_state="source_frozen", rights_component_ids=[default_rights_id], boundary_id=BOUNDARY_ID,
                **main_file_meta,
            )
        )
        extra: dict[str, Any] = {}
        if source_term == "malaria vaccine":
            extra = {"source_sort_key": "data!malaria vaccine", "target_display": "data!vaksin malaria", "latex_argument": "data!malaria vaccine@vaksin malaria"}
        elif source_term == "simulation":
            extra = {"source_sort_key": "simulation", "target_display": "simulasi", "latex_argument": "simulation@simulasi"}
        target_term = "statistika inferensial" if source_term == "statistical inference" else row["target_id_ID"]
        term_order = len(records["terms"]) + 1
        records["terms"].append(
            rrecord(
                "term", term_key, concept_id=concept_id, source_term=source_term, target_term=target_term,
                variants=[], rejected_forms=["inferensi statistika"] if source_term == "statistical inference" else [],
                scope=row["context"], register="academic",
                evidence=f"{row['candidate_term_id']}; {global_term_id}; qa/terminology/R011_TERMINOLOGY_FIELD_USAGE_QA.json; {row['note']}",
                resource_id=resource_id, edition_id=edition_id, source_local_ids=source_ids, parent_id=concept_id, order=term_order,
                locale="id-ID", translation_state="structurally_verified", rights_component_ids=[default_rights_id], boundary_id=BOUNDARY_ID,
                field_qa_decision=field_decisions.get(global_term_id),
                **main_file_meta, **extra,
            )
        )
        field_term_ids[global_term_id] = g.stable_id(term_key)
        add_relation(records, f"introduces-{slugify(source_term)}", "introduces", unit_ids[TERM_INTRO_UNIT[source_term]], concept_id, term_order, "Section 2.3")

    probability_key = "r011/concept/probability"
    probability_id = g.stable_id(probability_key)
    concept_ids["probability"] = probability_id
    probability_source_ids = ["R011-TERM-0160", BOUNDARY_ID]
    records["concepts"].append(
        rrecord(
            "concept", probability_key, preferred_source_term="probability", definition=TERM_DEFINITIONS["probability"],
            resource_id=resource_id, edition_id=edition_id, source_local_ids=probability_source_ids, parent_id=None,
            order=len(records["concepts"]) + 1, locale="zxx", translation_state="source_frozen",
            rights_component_ids=[default_rights_id], boundary_id=BOUNDARY_ID, **main_file_meta,
        )
    )
    probability_term_key = "r011/term/id-ID/probability"
    probability_term_id = g.stable_id(probability_term_key)
    field_term_ids["R011-TERM-0160"] = probability_term_id
    records["terms"].append(
        rrecord(
            "term", probability_term_key, concept_id=probability_id, source_term="probability", target_term="peluang (probabilitas)",
            variants=["peluang", "probabilitas"], rejected_forms=[],
            scope="Use peluang for an individual event; retain probabilitas in established field or chapter names.", register="academic",
            evidence="R011-TERM-0160; qa/terminology/R011_TERMINOLOGY_FIELD_USAGE_QA.json",
            field_qa_decision=field_decisions["R011-TERM-0160"], resource_id=resource_id, edition_id=edition_id,
            source_local_ids=probability_source_ids, parent_id=probability_id, order=len(records["terms"]) + 1,
            locale="id-ID", translation_state="language_reviewed", rights_component_ids=[default_rights_id], boundary_id=BOUNDARY_ID,
            **main_file_meta,
        )
    )
    add_relation(records, "introduces-probability", "introduces", unit_ids["checking"], probability_id, len(records["terms"]), "Section 2.3 scoped field term")

    prior_bin_term = existing_terms.get("bin")
    prior_bin_concept = existing_concepts.get("bin")
    if prior_bin_term is None or prior_bin_concept is None or prior_bin_term.get("target_term") != "kelas interval (bin)":
        raise RuntimeError("admitted TERM-0088 identity changed before field-QA supersession")
    prior_bin_record_identity = sha256_bytes((g.canonical_json(prior_bin_term) + "\n").encode("utf-8"))
    prior_bin_term["target_term"] = "interval kelas (bin)"
    prior_bin_term["variants"] = ["interval kelas"]
    prior_bin_term["rejected_forms"] = ["kelas interval", "kelas interval (bin)"]
    prior_bin_term["evidence"] = "R011-TERM-0088; qa/terminology/R011_TERMINOLOGY_FIELD_USAGE_QA.json"
    prior_bin_term["field_qa_decision"] = field_decisions["R011-TERM-0088"]
    prior_bin_term["prior_active_record_sha256"] = prior_bin_record_identity
    prior_bin_term["revision_boundary_id"] = BOUNDARY_ID
    prior_bin_term["recorded_at"] = RECORDED_AT
    prior_bin_term["workflow_id"] = WORKFLOW_ID
    prior_bin_term["translation_state"] = "language_reviewed"
    field_term_ids["R011-TERM-0088"] = prior_bin_term["id"]

    all_concepts = {row.get("preferred_source_term"): row["id"] for row in records["concepts"]}
    for source_term, target_term in PREREQUISITES:
        if source_term not in all_concepts or target_term not in all_concepts:
            raise RuntimeError(f"unresolved concept prerequisite {source_term!r} -> {target_term!r}")
        add_relation(records, f"prerequisite-{slugify(source_term)}-{slugify(target_term)}", "prerequisite", all_concepts[source_term], all_concepts[target_term], 1, "conceptual")
    for number, concepts in EXERCISE_CONCEPTS.items():
        for concept in concepts:
            if concept not in all_concepts:
                raise RuntimeError(f"unresolved exercise concept {concept!r}")
            add_relation(records, f"exercise-{number}-{slugify(concept)}", "exercises", unit_ids[f"exercise{number}"], all_concepts[concept], 1, "concept index")

    records["rights"].append(
        rrecord(
            "rights", generated_rights_key, component_scope="five B007 source figure PDFs, five exact adjacent English witnesses, and five hash-bound Indonesian localized derivatives",
            license_expression="CC-BY-SA-3.0", verification_status="verified by exact B007 source-application gate with localized/witness identities and canonical promotion receipt bound",
            attribution="OpenIntro Statistics source authors; Indonesian derivative changes must be identified",
            change_notice="Five localized figure PDFs and five exact English witnesses were promoted canonically under the bound B007 asset receipt; backend admission remains pending.",
            non_endorsement="No OpenIntro, study-author, package-author, or data-provider endorsement implied.",
            publication_effect="canonical assets exist but this isolated backend stage does not itself authorize or claim final-edition admission",
            resource_id=resource_id, edition_id=edition_id, source_local_ids=["R011-RIGHTS-B007-GENERATED", BOUNDARY_ID],
            parent_id=resource_id, order=len(records["rights"]) + 1, locale="zxx", translation_state="structurally_verified",
            rights_component_ids=[], boundary_id=BOUNDARY_ID, source_path="scratch/R011-B007-candidate/ASSET_LOCALIZATION_MANIFEST.tsv",
            source_span=None, source_sha256=sha256_bytes(candidate_raws["ASSET_LOCALIZATION_MANIFEST.tsv"]),
        )
    )
    records["rights"].append(
        rrecord(
            "rights", data_rights_key, component_scope="three source R producers, three promoted Indonesian producer overlays, OpenIntro package dependencies, study aggregates, and inference.RData",
            license_expression="GPL-3.0-only AND LicenseRef-Factual-Data", verification_status="verified by exact B007 source-application gate with source/promoted producer and serialized-input identities bound",
            attribution="OpenIntro package authors and cited study/data sources retained in the source work",
            change_notice="The Avandia producer changes N from 100 to 1000 explicitly; its promoted PDF is receipt-bound to a deterministic equivalent NumPy PCG64 hypergeometric render, with no exact R replay claim.",
            non_endorsement="No OpenIntro, study-author, package-author, or data-provider endorsement implied.",
            publication_effect="producer and serialized-input bytes are canonical but the backend and final edition remain nonadmitted until remaining rights/build gates close",
            resource_id=resource_id, edition_id=edition_id, source_local_ids=["R011-RIGHTS-B007-DATA", BOUNDARY_ID],
            parent_id=resource_id, order=len(records["rights"]) + 2, locale="zxx", translation_state="structurally_verified",
            rights_component_ids=[], boundary_id=BOUNDARY_ID, source_path="scratch/R011-B007-candidate/ASSET_LOCALIZATION_MANIFEST.tsv",
            source_span=None, source_sha256=sha256_bytes(candidate_raws["ASSET_LOCALIZATION_MANIFEST.tsv"]),
        )
    )

    asset_rows = tsv_rows(candidate_raws["ASSET_LOCALIZATION_MANIFEST.tsv"])
    if len(asset_rows) != 9:
        raise RuntimeError("B007 asset closure must contain five PDFs, three producers, and inference.RData")
    asset_ids: dict[str, str] = {}
    target_producer_ids: dict[str, str] = {}
    localized_pdf_ids: dict[str, str] = {}
    witness_pdf_ids: dict[str, str] = {}
    producer_for_pdf: dict[str, str] = {}
    parent_by_asset = {
        "R011-B007-ASSET-0001": unit_ids["checking"], "R011-B007-ASSET-0002": unit_ids["exercise25"],
        "R011-B007-ASSET-0003": unit_ids["exercise26"], "R011-B007-ASSET-0004": unit_ids["exercise26"],
        "R011-B007-ASSET-0005": unit_ids["exercise26"], "R011-B007-CODE-0001": unit_ids["checking"],
        "R011-B007-CODE-0002": unit_ids["exercise25"], "R011-B007-CODE-0003": unit_ids["exercise26"],
        "R011-B007-DATA-0001": unit_ids["exercise26"],
    }
    promotion_destinations = {
        (entry.get("asset_id") or entry.get("producer_id"), entry["role"]): entry
        for entry in asset_promotion["destinations"]
    }
    promoted_producers = {entry["producer_id"]: entry for entry in asset_promotion["producers"]}
    if len(promotion_destinations) != 13 or len(promoted_producers) != 3:
        raise RuntimeError("B007 canonical promotion receipt linkage inventory changed")
    for entry in asset_promotion["destinations"]:
        destination = entry["destination"]
        raw = (LANE / destination["path"]).read_bytes()
        if (
            entry.get("post_copy_byte_and_hash_identity") is not True
            or len(raw) != destination["bytes"]
            or sha256_bytes(raw) != destination["sha256"]
        ):
            raise RuntimeError(f"canonical B007 asset destination changed: {destination['path']}")

    for order, row in enumerate(asset_rows, 1):
        source_path = row["source_path"]
        source_file = source_root / source_path
        source_raw = source_file.read_bytes()
        if len(source_raw) != int(row["bytes"]) or sha256_bytes(source_raw) != row["sha256"]:
            raise RuntimeError(f"B007 authority asset identity changed: {source_path}")
        key = f"r011/asset/b007/source/{row['asset_id'].lower()}"
        aid = g.stable_id(key)
        asset_ids[row["asset_id"]] = aid
        if row["role"] == "reader_pdf":
            kind, media, locale, rights = "authority_exact_reader_pdf", "application/pdf", "en", [default_rights_id, generated_rights_id]
            producer_for_pdf[row["asset_id"]] = row["producer_or_input"]
        elif row["role"] == "R_generator":
            kind, media, locale, rights = "authority_exact_figure_producer", "text/x-r-source", "en", [default_rights_id, package_rights_id, data_rights_id]
        else:
            kind, media, locale, rights = "authority_exact_serialized_generator_input", "application/x-r-data", "zxx", [package_rights_id, data_rights_id]
        records["assets"].append(
            rrecord(
                "asset", key, asset_kind=kind, media_type=media, bytes=len(source_raw), sha256=sha256_bytes(source_raw),
                source_visible_strings=row["visible_source_strings"], proposed_id_ID_strings=row["proposed_id_ID_strings"],
                localization_rule=row["localization_rule"], candidate_status=row["status"], resource_id=resource_id,
                edition_id=edition_id, source_local_ids=[row["asset_id"], source_path, BOUNDARY_ID], parent_id=parent_by_asset[row["asset_id"]],
                order=order, locale=locale, translation_state="source_frozen", rights_component_ids=rights, boundary_id=BOUNDARY_ID,
                source_path=source_path, source_span=None, source_sha256=sha256_bytes(source_raw),
            )
        )
        if row["role"] == "R_generator":
            promoted = promoted_producers[row["asset_id"]]
            destination_path = promoted["destination"]
            destination_raw = (LANE / destination_path).read_bytes()
            if len(destination_raw) != promoted["bytes"] or sha256_bytes(destination_raw) != promoted["sha256"]:
                raise RuntimeError(f"promoted producer identity changed: {destination_path}")
            target_key = f"r011/asset/b007/id-id-producer/{row['asset_id'].lower()}"
            target_id = g.stable_id(target_key)
            target_producer_ids[row["asset_id"]] = target_id
            records["assets"].append(
                rrecord(
                    "asset", target_key, asset_kind="canonical_id_id_localized_figure_producer", media_type="text/x-r-source",
                    bytes=len(destination_raw), sha256=sha256_bytes(destination_raw), source_visible_strings=row["visible_source_strings"],
                    target_visible_strings=row["proposed_id_ID_strings"], localization_rule=row["localization_rule"],
                    candidate_status="canonical_promotion_complete_nonadmitted_backend", reproduction_scope=promoted["reproduction_scope"],
                    resource_id=resource_id, edition_id=edition_id,
                    source_local_ids=[row["asset_id"], destination_path, BOUNDARY_ID], parent_id=parent_by_asset[row["asset_id"]],
                    order=order, locale="id-ID", translation_state="language_reviewed", rights_component_ids=[default_rights_id, package_rights_id, data_rights_id],
                    boundary_id=BOUNDARY_ID, source_path=source_path, source_span=None, source_sha256=sha256_bytes(source_raw),
                    target_path=destination_path, target_bytes=len(destination_raw), target_sha256=sha256_bytes(destination_raw),
                    target_identity_status="canonical_asset_promotion_receipt_exact_nonadmitted",
                )
            )
            add_relation(records, f"localized-producer-adapts-{row['asset_id'].lower()}", "adapts", target_id, aid, 1, "canonical presentation localization; Avandia also carries explicit N=1000 correction")

    row_by_asset_id = {row["asset_id"]: row for row in asset_rows}
    for order, linkage in enumerate(asset_promotion["asset_linkage"], 1):
        asset_id = linkage["asset_id"]
        source_row = row_by_asset_id[asset_id]
        localized_entry = promotion_destinations[(asset_id, "localized_reader_pdf")]["destination"]
        witness_entry = promotion_destinations[(asset_id, "exact_english_pdf_witness")]["destination"]
        localized_key = f"r011/asset/b007/id-id-reader/{asset_id.lower()}"
        witness_key = f"r011/asset/b007/source-witness/{asset_id.lower()}"
        localized_id = g.stable_id(localized_key)
        witness_id = g.stable_id(witness_key)
        localized_pdf_ids[asset_id] = localized_id
        witness_pdf_ids[asset_id] = witness_id
        records["assets"].append(
            rrecord(
                "asset", localized_key, asset_kind="canonical_id_id_localized_reader_pdf", media_type="application/pdf",
                bytes=localized_entry["bytes"], sha256=localized_entry["sha256"],
                source_visible_strings=source_row["visible_source_strings"], target_visible_strings=source_row["proposed_id_ID_strings"],
                localization_rule=source_row["localization_rule"], candidate_status="canonical_promotion_complete_nonadmitted_backend",
                resource_id=resource_id, edition_id=edition_id, source_local_ids=[asset_id, localized_entry["path"], BOUNDARY_ID],
                parent_id=parent_by_asset[asset_id], order=order, locale="id-ID", translation_state="visually_checked",
                rights_component_ids=[default_rights_id, generated_rights_id], boundary_id=BOUNDARY_ID,
                source_path=source_row["source_path"], source_span=None, source_sha256=source_row["sha256"],
                target_path=localized_entry["path"], target_bytes=localized_entry["bytes"], target_sha256=localized_entry["sha256"],
                target_identity_status="canonical_asset_promotion_receipt_exact_nonadmitted",
            )
        )
        records["assets"].append(
            rrecord(
                "asset", witness_key, asset_kind="canonical_exact_english_pdf_witness", media_type="application/pdf",
                bytes=witness_entry["bytes"], sha256=witness_entry["sha256"],
                source_visible_strings=source_row["visible_source_strings"], localization_rule="exact adjacent English byte witness",
                candidate_status="canonical_promotion_complete_nonadmitted_backend", resource_id=resource_id, edition_id=edition_id,
                source_local_ids=[asset_id, witness_entry["path"], BOUNDARY_ID], parent_id=parent_by_asset[asset_id],
                order=order, locale="en", translation_state="source_frozen", rights_component_ids=[default_rights_id, generated_rights_id],
                boundary_id=BOUNDARY_ID, source_path=source_row["source_path"], source_span=None, source_sha256=source_row["sha256"],
                target_path=witness_entry["path"], target_bytes=witness_entry["bytes"], target_sha256=witness_entry["sha256"],
                target_identity_status="canonical_asset_promotion_receipt_exact_nonadmitted",
            )
        )
        producer_id = linkage["producer_id"]
        add_relation(records, f"source-to-localized-{asset_id.lower()}", "translates", asset_ids[asset_id], localized_id, 1, "receipt-bound id-ID localized PDF")
        add_relation(records, f"witnesses-source-{asset_id.lower()}", "witnesses", witness_id, asset_ids[asset_id], 1, "exact adjacent English witness")
        add_relation(records, f"localized-producer-produces-{asset_id.lower()}", "produces", target_producer_ids[producer_id], localized_id, 1, "canonical localized producer/output linkage; Avandia uses receipt-bound equivalent renderer")
        add_relation(records, f"localized-asset-illustrates-{asset_id.lower()}", "illustrates", localized_id, parent_by_asset[asset_id], 1, "canonical reader-visible id-ID Section 2.3 asset")

    for asset_id, producer_id in producer_for_pdf.items():
        add_relation(records, f"source-producer-produces-{asset_id.lower()}", "produces", asset_ids[producer_id], asset_ids[asset_id], 1, "pinned authority producer")
        add_relation(records, f"source-asset-illustrates-{asset_id.lower()}", "illustrates", asset_ids[asset_id], parent_by_asset[asset_id], 1, "reader-visible Section 2.3 asset")
    add_relation(records, "heart-source-producer-depends-inference-rdata", "depends-on", asset_ids["R011-B007-CODE-0003"], asset_ids["R011-B007-DATA-0001"], 1, "serialized inference input")
    add_relation(records, "heart-localized-producer-depends-inference-rdata", "depends-on", target_producer_ids["R011-B007-CODE-0003"], asset_ids["R011-B007-DATA-0001"], 1, "byte-identical serialized inference input")

    correction_rows = tsv_rows(candidate_raws["SOURCE_CORRECTIONS.tsv"])
    if len(correction_rows) != 8:
        raise RuntimeError("B007 source correction inventory changed")
    correction_parent = {
        "R011-B007-SC-001": unit_ids["variability"], "R011-B007-SC-002": unit_ids["variability"],
        "R011-B007-SC-003": unit_ids["exercise26"], "R011-B007-SC-004": unit_ids["exercise26"],
        "R011-B007-SC-005": unit_ids["solution25"], "R011-B007-SC-006": unit_ids["exercise25"],
        "R011-B007-SC-007": unit_ids["exercise26"], "R011-B007-SC-008": unit_ids["exercise26"],
    }
    for order, row in enumerate(correction_rows, 1):
        key = f"r011/correction/{row['correction_id'].lower()}"
        affected_id = correction_parent[row["correction_id"]]
        authority_path = row["authority_path"].split(";", 1)[0]
        source_identity = source_file_meta(source_root, authority_path)
        record = rrecord(
            "correction", key, affected_id=affected_id, correction_type="upstream_source_finding", category=row["severity"],
            confidence="high", source_claim=row["verbatim_problem_excerpt"], proposed_correction=row["recommended_upstream_action"],
            rationale=row["evidence"], evidence=f"scratch/R011-B007-candidate/SOURCE_CORRECTIONS.tsv#{row['correction_id']}",
            candidate_handling=row["candidate_handling"], upstream_report_disposition="hold_until_corpus_complete_then_deduplicate",
            target_identity_status="isolated_candidate_exact_nonadmitted", resource_id=resource_id, edition_id=edition_id,
            source_local_ids=[row["correction_id"], BOUNDARY_ID], parent_id=affected_id, order=order, locale="id-ID",
            translation_state="structurally_verified", rights_component_ids=[default_rights_id], boundary_id=BOUNDARY_ID,
            **source_identity,
        )
        records["corrections"].append(record)
        add_relation(records, f"corrects-{row['correction_id'].lower()}", "corrects", record["id"], affected_id, order, "held for single deduplicated end-of-corpus report")

    affected_bin_localizations = sorted(
        row["id"] for row in records["localizations"]
        if any(item.get("term_id") == "R011-TERM-0088" for item in row.get("terminology_supersession", []))
    )
    affected_inference_localizations = sorted(
        row["id"] for row in records["localizations"]
        if any(item.get("term_id") == "R011-TERM-0150" for item in row.get("terminology_supersession", []))
    )
    affected_probability_localizations = sorted(
        row["id"] for row in records["localizations"]
        if "peluang" in row.get("target_text", "") or "probabilitas" in row.get("target_text", "")
    )
    terminology_corrections = [
        (
            "term-0088-field-qa", "R011-TERM-0088", prior_bin_term["id"], "kelas interval (bin)",
            "interval kelas (bin)", affected_bin_localizations,
            "Refine the Indonesian head order throughout already translated histogram material; retain the stable bin concept ID and immutable prior artifact history.",
        ),
        (
            "term-0150-field-qa", "R011-TERM-0150", field_term_ids["R011-TERM-0150"], "inferensi statistika",
            "statistika inferensial", affected_inference_localizations,
            "Use the conventional adjectival name because the source paragraph names the field; active exact canonical target spans are rebound while final backend admission remains gated.",
        ),
        (
            "term-0160-field-qa", "R011-TERM-0160", field_term_ids["R011-TERM-0160"], "uncontrolled mixed usage",
            "peluang for individual events; probabilitas for established field/chapter names", affected_probability_localizations,
            "Add a scoped term rather than mechanically replacing every occurrence; stable code/data tokens remain unchanged.",
        ),
    ]
    for offset, (suffix, term_id, affected_id, before, after, localization_ids, rationale) in enumerate(terminology_corrections, len(correction_rows) + 1):
        key = f"r011/correction/b007-{suffix}"
        record = rrecord(
            "correction", key, affected_id=affected_id, affected_localization_ids=localization_ids,
            correction_type="derivative_terminology_field_refinement", category="terminology_field_usage",
            confidence="high", source_claim=before, proposed_correction=after, rationale=rationale,
            evidence=f"qa/terminology/R011_TERMINOLOGY_FIELD_USAGE_QA.json#{term_id}",
            upstream_report_disposition="not_upstream_derivative_only", target_identity_status="exact_propagated_nonadmitted",
            resource_id=resource_id, edition_id=edition_id, source_local_ids=[term_id, BOUNDARY_ID], parent_id=affected_id,
            order=offset, locale="id-ID", translation_state="language_reviewed", rights_component_ids=[default_rights_id],
            boundary_id=BOUNDARY_ID, source_path="qa/terminology/R011_TERMINOLOGY_FIELD_USAGE_QA.json",
            source_span=None, source_sha256=EXPECTED_FIELD_QA["sha256"],
        )
        records["corrections"].append(record)
        add_relation(records, f"corrects-{suffix}", "corrects", record["id"], affected_id, offset, "field-usage refinement; prior released evidence retained")

    records_by_id = {row["id"]: row for rows in records.values() for row in rows}
    privacy_record_revisions: list[dict[str, Any]] = []
    for record_id, prior in sorted(privacy_prior_records.items()):
        row = records_by_id[record_id]
        if (
            row.get("translation_provenance") != NEUTRAL_TRANSLATION_PROVENANCE
            or row.get("prior_active_record_sha256") != prior["prior_record_sha256"]
            or row.get("revision_boundary_id") != BOUNDARY_ID
        ):
            raise RuntimeError(f"active localization privacy revision changed: {record_id}")
        privacy_record_revisions.append(
            {
                **prior,
                "packaged_record_sha256": record_sha256(row),
                "packaged_translation_provenance_sha256": sha256_bytes(NEUTRAL_TRANSLATION_PROVENANCE.encode("utf-8")),
            }
        )
    privacy_receipt = {
        "$schema": "r011-b007-privacy-sanitization-receipt/v1",
        "boundary_id": BOUNDARY_ID,
        "status": "passed_sanitized_nonadmitted_backend_package_components",
        "recorded_at": RECORDED_AT,
        "workflow_id": WORKFLOW_ID,
        "live_backend_mutated": False,
        "canonical_historical_evidence_mutated": False,
        "stable_ids_changed": False,
        "active_localization_revision_count": len(privacy_record_revisions),
        "canonical_target_text_rebind_count": sum(1 for item in privacy_record_revisions if item["target_text_rebound"]),
        "active_localization_revisions": privacy_record_revisions,
        "sanitized_historical_evidence_copy_count": len(privacy_auxiliary_revisions),
        "sanitized_historical_evidence_copies": [
            {
                **item,
                "canonical_source_path": f"backend/exports/{item['path']}",
                "packaged_path": f"qa/b007-backend/exports/{item['path']}",
            }
            for item in privacy_auxiliary_revisions
        ],
        "neutral_provenance_sha256": sha256_bytes(NEUTRAL_TRANSLATION_PROVENANCE.encode("utf-8")),
        "privacy_contract": {
            "prohibited_requester_token_hits_required": 0,
            "absolute_local_user_profile_path_hits_required": 0,
            "scan_scope": "every emitted qa/b007-backend/exports payload byte",
            "historical_policy": "canonical local evidence remains unchanged; only explicitly receipt-bound sanitized copies are emitted",
        },
    }
    privacy_receipt_raw = (g.canonical_json(privacy_receipt) + "\n").encode("utf-8")

    evidence_payloads = {
        PRIVACY_RECEIPT_EXPORT_PATH: privacy_receipt_raw,
        "evidence/R011-B007_CANDIDATE_MANIFEST.json": candidate_raws["CANDIDATE_MANIFEST.json"],
        "evidence/R011-B007_VALIDATION_RECEIPT.json": candidate_raws["VALIDATION_RECEIPT.json"],
        "evidence/R011-B007_ASSET_LOCALIZATION_MANIFEST.tsv": candidate_raws["ASSET_LOCALIZATION_MANIFEST.tsv"],
        "evidence/R011-B007_TERMINOLOGY_PROPOSALS.tsv": candidate_raws["TERMINOLOGY_PROPOSALS.tsv"],
        "evidence/R011-B007_SOURCE_CORRECTIONS.tsv": candidate_raws["SOURCE_CORRECTIONS.tsv"],
        "evidence/R011-B007_O001_MASTERY_GAPS.tsv": candidate_raws["O001_MASTERY_GAPS.tsv"],
        "evidence/R011_TERMINOLOGY_FIELD_USAGE_QA.json": field_qa_raw,
        "evidence/R011_TERMINOLOGY_FIELD_USAGE_QA.md": field_qa_note_raw,
        "evidence/R011-B007_CANONICAL_ASSET_PROMOTION_RECEIPT.json": asset_promotion_raw,
        "evidence/R011-B007_ASSET_LOCALIZATION_RECEIPT.json": asset_localization_raw,
        "evidence/R011-B007_ASSET_OUTPUT_MANIFEST.json": asset_output_manifest_raw,
        "evidence/R011-B007_ASSET_PRIVACY_REFRESH_QA.json": asset_privacy_qa_raw,
        "evidence/R011-B007_SOURCE_APPLICATION_MANIFEST.json": source_application_manifest_raw,
        "evidence/R011-B007_SOURCE_APPLICATION_RECEIPT.json": source_application_receipt_raw,
        "evidence/R011-B007_SOURCE_GATE_QA.json": source_gate_qa_raw,
    }
    artifact_inputs: list[tuple[str, str, bytes, str, str]] = [
        ("privacy-sanitization", "privacy_sanitization_receipt", privacy_receipt_raw, PRIVACY_RECEIPT_EXPORT_PATH, "structurally_verified"),
        ("candidate-manifest", "isolated_candidate_manifest", candidate_raws["CANDIDATE_MANIFEST.json"], "evidence/R011-B007_CANDIDATE_MANIFEST.json", "structurally_verified"),
        ("candidate-validation", "isolated_candidate_validation_receipt", candidate_raws["VALIDATION_RECEIPT.json"], "evidence/R011-B007_VALIDATION_RECEIPT.json", "structurally_verified"),
        ("asset-manifest", "source_asset_localization_manifest", candidate_raws["ASSET_LOCALIZATION_MANIFEST.tsv"], "evidence/R011-B007_ASSET_LOCALIZATION_MANIFEST.tsv", "source_frozen"),
        ("terminology", "terminology_candidate_table", candidate_raws["TERMINOLOGY_PROPOSALS.tsv"], "evidence/R011-B007_TERMINOLOGY_PROPOSALS.tsv", "structurally_verified"),
        ("source-corrections", "source_correction_candidate_table", candidate_raws["SOURCE_CORRECTIONS.tsv"], "evidence/R011-B007_SOURCE_CORRECTIONS.tsv", "structurally_verified"),
        ("o001-gap", "o001_gap_table", candidate_raws["O001_MASTERY_GAPS.tsv"], "evidence/R011-B007_O001_MASTERY_GAPS.tsv", "structurally_verified"),
        ("terminology-field-qa", "terminology_field_usage_qa", field_qa_raw, "evidence/R011_TERMINOLOGY_FIELD_USAGE_QA.json", "language_reviewed"),
        ("terminology-field-note", "terminology_field_usage_human_note", field_qa_note_raw, "evidence/R011_TERMINOLOGY_FIELD_USAGE_QA.md", "language_reviewed"),
        ("asset-canonical-promotion", "canonical_asset_promotion_receipt", asset_promotion_raw, "evidence/R011-B007_CANONICAL_ASSET_PROMOTION_RECEIPT.json", "visually_checked"),
        ("asset-localization-receipt", "localized_asset_replay_receipt", asset_localization_raw, "evidence/R011-B007_ASSET_LOCALIZATION_RECEIPT.json", "visually_checked"),
        ("asset-output-manifest", "localized_asset_output_manifest", asset_output_manifest_raw, "evidence/R011-B007_ASSET_OUTPUT_MANIFEST.json", "visually_checked"),
        ("asset-privacy-refresh", "localized_asset_privacy_refresh_qa", asset_privacy_qa_raw, "evidence/R011-B007_ASSET_PRIVACY_REFRESH_QA.json", "visually_checked"),
        ("source-application-manifest", "canonical_source_application_manifest", source_application_manifest_raw, "evidence/R011-B007_SOURCE_APPLICATION_MANIFEST.json", "language_reviewed"),
        ("source-application-receipt", "canonical_source_application_receipt", source_application_receipt_raw, "evidence/R011-B007_SOURCE_APPLICATION_RECEIPT.json", "language_reviewed"),
        ("source-gate-qa", "canonical_source_gate_qa", source_gate_qa_raw, "evidence/R011-B007_SOURCE_GATE_QA.json", "language_reviewed"),
    ]
    for relative in [TARGET_MAIN_PATH, TARGET_EXERCISE_PATH, TARGET_ANSWER_PATH,
                     "ch_summarizing_data/figures/malaria_rand_dot_plot/malaria_rand_dot_plot.R",
                     "ch_summarizing_data/figures/eoce/randomization_avandia/randomization_avandia.R",
                     "ch_summarizing_data/figures/eoce/randomization_heart_transplants/randomization_heart_transplants.R"]:
        raw = candidate_raws[relative]
        artifact_inputs.append((slugify(relative), "isolated_candidate_overlay", raw, f"scratch/R011-B007-candidate/{relative}", "draft" if relative.endswith(".R") else "structurally_verified"))
    for suffix, kind, raw, path, state in artifact_inputs:
        records["artifacts"].append(
            rrecord(
                "artifact", f"r011/artifact/b007-{suffix}", artifact_kind=kind, path=(f"qa/b007-backend/exports/{path}" if path.startswith("evidence/") else path),
                bytes=len(raw), sha256=sha256_bytes(raw), result="exact_receipt_or_stage_input", resource_id=resource_id,
                edition_id=edition_id, source_local_ids=[BOUNDARY_ID], parent_id=edition_id, order=len(records["artifacts"]) + 1,
                locale="zxx", translation_state=state, status="passed", rights_component_ids=[], boundary_id=BOUNDARY_ID,
                source_path=None, source_span=None, source_sha256=None, toolchain="R011-B007 isolated candidate stage; no canonical application or build claim",
            )
        )
    for suffix, kind, path in [("generator", "backend_stage_generator", GENERATOR_PATH), ("validator", "backend_stage_validator", VALIDATOR_PATH)]:
        raw = path.read_bytes()
        records["artifacts"].append(
            rrecord(
                "artifact", f"r011/artifact/b007-{suffix}", artifact_kind=kind, path=path.relative_to(LANE).as_posix(),
                bytes=len(raw), sha256=sha256_bytes(raw), result="exact_tool_identity", resource_id=resource_id,
                edition_id=edition_id, source_local_ids=[BOUNDARY_ID], parent_id=edition_id, order=len(records["artifacts"]) + 1,
                locale="zxx", translation_state="structurally_verified", status="passed", rights_component_ids=[], boundary_id=BOUNDARY_ID,
                source_path=None, source_span=None, source_sha256=None, toolchain="deterministic Python 3 standard-library backend tooling",
            )
        )

    qa_specs = [
        ("privacy-package", "privacy", section_id, "All inherited active localization provenance is neutralized with stable IDs and prior-record hashes retained; affected historical evidence is emitted only as receipt-bound sanitized copies; the full staged payload scan requires zero requester-token and local-profile-path hits.", "qa/b007-backend/exports/evidence/R011-B007_PRIVACY_SANITIZATION_RECEIPT.json"),
        ("candidate-integrity", "source", section_id, "The isolated candidate manifest binds every candidate file and the validation receipt replays twice with zero failures.", "scratch/R011-B007-candidate/VALIDATION_RECEIPT.json"),
        ("tex-topology", "topology", section_id, "Whole-file command, environment, label, reference, math, macro, and numeric-token sequences are preserved across the isolated translation.", "scratch/R011-B007-candidate/VALIDATION_RECEIPT.json"),
        ("language", "language", section_id, "Complete reader-prose review found no unexplained English prose or visible English index residue.", "scratch/R011-B007-candidate/VALIDATION_RECEIPT.json"),
        ("exercise-answer-o001", "topology", section_id, "Three guided feedback items, exercises 2.25-2.26, public answer 2.25, and the explicit no-public-answer O001 gap for 2.26 are modeled without invention.", "scratch/R011-B007-candidate/O001_MASTERY_GAPS.tsv"),
        ("terminology-index", "language", section_id, "TERM-0142..0160, admitted randomization reuse, TERM-0088 supersession, and both index source/display aliases are explicit; title phrase case study is not misclassified as a controlled mathematical term.", "qa/terminology/R011_TERMINOLOGY_FIELD_USAGE_QA.json"),
        ("terminology-field-usage", "language", section_id, "The exact one-time field-usage QA finalizes interval kelas (bin), statistika inferensial, and scoped peluang (probabilitas); active term/localization overlays bind propagated canonical spans while prior B005/B006 evidence payloads remain immutable.", "qa/terminology/R011_TERMINOLOGY_FIELD_USAGE_QA.json"),
        ("corrections", "source", section_id, "Eight high-confidence source findings are typed and held for one deduplicated end-of-corpus report; no upstream contact occurred.", "scratch/R011-B007-candidate/SOURCE_CORRECTIONS.tsv"),
        ("asset-source-identities", "rights", section_id, "Five source PDFs, three source R producers, inference.RData, three promoted localized producers, five localized PDFs, and five exact adjacent English witnesses are hash-bound; final file-by-file rights closure remains deferred.", "qa/b007-assets/B007_CANONICAL_PROMOTION_RECEIPT.json"),
        ("producer-diff-review", "math", section_id, "Producer changes are bounded to localized presentation plus explicit Avandia N=1000; the promoted outputs passed two deterministic passes and two-renderer QA, with no exact Avandia R replay claimed.", "qa/b007-assets/B007_ASSET_LOCALIZATION_RECEIPT.json"),
        ("asset-canonical-promotion", "visual", section_id, "All 13 canonical destinations match the promotion receipt exactly; P0-P3 are zero and both point-heavy assets preserve their source coordinate multisets with every point visible in Poppler and MuPDF.", "qa/b007-assets/B007_CANONICAL_PROMOTION_RECEIPT.json"),
        ("canonical-source-gate", "source", section_id, "The canonical source application passes 14/14 checks, 14/14 adversarial self-tests, and two deterministic read-only replays; no source or asset dependency remains.", "qa/R011-B007_SOURCE_GATE_QA.json"),
    ]
    for order, (suffix, qa_type, subject, detail, witness) in enumerate(qa_specs, 1):
        records["qa_events"].append(
            rrecord(
                "qa_event", f"r011/qa/b007-{suffix}", qa_type=qa_type, result="passed", subject_id=subject,
                witness_path=witness, detail=detail, resource_id=resource_id, edition_id=edition_id,
                source_local_ids=[BOUNDARY_ID], parent_id=subject, order=order, locale="zxx",
                translation_state="structurally_verified", status="passed", rights_component_ids=[], boundary_id=BOUNDARY_ID,
                source_path=None, source_span=None, source_sha256=None,
            )
        )

    context = {
        "authority": authority,
        "base_auxiliary": base_auxiliary,
        "base_manifest": base_manifest,
        "candidate": candidate,
        "candidate_receipt": candidate_receipt,
        "candidate_raws": candidate_raws,
        "field_qa": field_qa,
        "field_qa_raw": field_qa_raw,
        "field_qa_note_raw": field_qa_note_raw,
        "source_application_manifest": source_application_manifest,
        "source_application_manifest_raw": source_application_manifest_raw,
        "source_application_receipt": source_application_receipt,
        "source_application_receipt_raw": source_application_receipt_raw,
        "source_gate_qa": source_gate_qa,
        "source_gate_qa_raw": source_gate_qa_raw,
        "asset_promotion": asset_promotion,
        "asset_promotion_raw": asset_promotion_raw,
        "asset_localization": asset_localization,
        "asset_localization_raw": asset_localization_raw,
        "asset_output_manifest": asset_output_manifest,
        "asset_output_manifest_raw": asset_output_manifest_raw,
        "asset_privacy_qa": asset_privacy_qa,
        "asset_privacy_qa_raw": asset_privacy_qa_raw,
        "active_overlay_revisions": active_overlay_revisions,
        "prior_bin_record_identity": prior_bin_record_identity,
        "prohibited_token": prohibited_token,
        "privacy_record_revisions": privacy_record_revisions,
        "privacy_auxiliary_revisions": privacy_auxiliary_revisions,
        "privacy_receipt_raw": privacy_receipt_raw,
        "evidence_payloads": evidence_payloads,
        "resource_id": resource_id,
        "edition_id": edition_id,
        "unit_ids": unit_ids,
        "segment_ids": segment_ids,
        "generated_rights_id": generated_rights_id,
        "data_rights_id": data_rights_id,
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


def payload_privacy_findings(payloads: dict[str, bytes], prohibited_token: str) -> dict[str, list[str]]:
    requester_hits: list[str] = []
    local_profile_hits: list[str] = []
    profile_prefix = re.compile(r"(?i)[a-z]:[\\/]+users[\\/]+")
    requester = prohibited_token.casefold()
    for relative, raw in sorted(payloads.items()):
        text = raw.decode("utf-8", errors="ignore")
        if requester in text.casefold():
            requester_hits.append(relative)
        decoded_escapes = text.replace("\\\\", "\\")
        if profile_prefix.search(text) or profile_prefix.search(decoded_escapes):
            local_profile_hits.append(relative)
    return {
        "prohibited_requester_token_paths": requester_hits,
        "absolute_local_user_profile_path_paths": local_profile_hits,
    }


def final_binding_gaps() -> list[str]:
    """Return every release value that still prevents final-stage generation."""
    gaps: list[str] = []
    for label, identity in EXPECTED_FINAL_INPUTS.items():
        required = ["path", "bytes", "sha256"]
        if label in {"pdf", "render_manifest"}:
            required.append("page_count")
        for key in required:
            value = identity.get(key)
            if value is None:
                gaps.append(f"inputs.{label}.{key}")
            elif key in {"bytes", "page_count"} and (not isinstance(value, int) or value <= 0):
                gaps.append(f"inputs.{label}.{key}")
            elif key == "sha256" and re.fullmatch(r"[0-9a-f]{64}", str(value)) is None:
                gaps.append(f"inputs.{label}.sha256")
    for key in ("candidate", "page_count", "inspected_pages"):
        value = EXPECTED_FINAL_GATE.get(key)
        if value is None:
            gaps.append(f"gate.{key}")
    pages = EXPECTED_FINAL_GATE.get("inspected_pages")
    if pages is not None and (
        not isinstance(pages, list)
        or not pages
        or any(not isinstance(page, int) or page <= 0 for page in pages)
        or pages != sorted(set(pages))
    ):
        gaps.append("gate.inspected_pages")
    if EXPECTED_FINAL_GATE.get("page_count") is not None and EXPECTED_FINAL_INPUTS["pdf"].get("page_count") is not None:
        if EXPECTED_FINAL_GATE["page_count"] != EXPECTED_FINAL_INPUTS["pdf"]["page_count"]:
            gaps.append("gate.page_count!=inputs.pdf.page_count")
    prerequisites = {
        "candidate_manifest": (CANDIDATE_MANIFEST_PATH, EXPECTED_CANDIDATE_MANIFEST),
        "candidate_validation_receipt": (VALIDATION_RECEIPT_PATH, EXPECTED_VALIDATION_RECEIPT),
        "terminology_field_qa": (FIELD_QA_PATH, EXPECTED_FIELD_QA),
        "terminology_field_qa_note": (FIELD_QA_NOTE_PATH, EXPECTED_FIELD_QA_NOTE),
        "source_application_manifest": (SOURCE_APPLICATION_MANIFEST_PATH, EXPECTED_SOURCE_APPLICATION_MANIFEST),
        "source_application_receipt": (SOURCE_APPLICATION_RECEIPT_PATH, EXPECTED_SOURCE_APPLICATION_RECEIPT),
        "source_gate_qa": (SOURCE_GATE_QA_PATH, EXPECTED_SOURCE_GATE_QA),
        "asset_promotion_receipt": (ASSET_PROMOTION_RECEIPT_PATH, EXPECTED_ASSET_PROMOTION_RECEIPT),
        "asset_localization_receipt": (ASSET_LOCALIZATION_RECEIPT_PATH, EXPECTED_ASSET_LOCALIZATION_RECEIPT),
        "asset_output_manifest": (ASSET_OUTPUT_MANIFEST_PATH, EXPECTED_ASSET_OUTPUT_MANIFEST),
        "asset_privacy_qa": (ASSET_PRIVACY_QA_PATH, EXPECTED_ASSET_PRIVACY_QA),
    }
    for label, (path, expected) in prerequisites.items():
        if not path.is_file():
            gaps.append(f"prerequisites.{label}.missing")
            continue
        raw = path.read_bytes()
        if {"bytes": len(raw), "sha256": sha256_bytes(raw)} != expected:
            gaps.append(f"prerequisites.{label}.exact_identity")
    return sorted(set(gaps))


def path_from_final_identity(identity: dict[str, Any]) -> Path:
    relative = identity.get("path")
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise RuntimeError(f"final input path must be a portable lane-relative path: {relative!r}")
    relative_path = Path(relative)
    if relative_path.is_absolute() or ".." in relative_path.parts or relative_path.as_posix() != relative:
        raise RuntimeError(f"final input path escapes or is noncanonical: {relative!r}")
    resolved_lane = LANE.resolve()
    resolved = (LANE / relative_path).resolve()
    try:
        resolved.relative_to(resolved_lane)
    except ValueError as exc:
        raise RuntimeError(f"final input resolves outside the R011 lane: {relative!r}") from exc
    if not resolved.is_file():
        raise RuntimeError(f"required final input is missing: {relative}")
    return resolved


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise RuntimeError(f"duplicate JSON key in final-input manifest: {key}")
        result[key] = value
    return result


def load_final_inputs(path: Path) -> tuple[dict[str, Any], bytes, dict[str, bytes]]:
    gaps = final_binding_gaps()
    if gaps:
        raise RuntimeError("B007 exact final bindings are not frozen: " + ", ".join(gaps))
    if not path.is_file():
        raise RuntimeError(f"B007 exact-final-input manifest is missing: {path}")
    raw = path.read_bytes()
    supplied = json.loads(raw, object_pairs_hook=_reject_duplicate_json_keys)
    if raw != (g.canonical_json(supplied) + "\n").encode("utf-8"):
        raise RuntimeError("B007 exact-final-input manifest is not canonical UTF-8 JSON plus LF")
    if set(supplied) != {"schema_version", "boundary_id", "status", "gate", "inputs"}:
        raise RuntimeError("B007 exact-final-input manifest has an unexpected field set")
    if (
        supplied.get("schema_version") != "r011-b007-final-gate-inputs/1.0.0"
        or supplied.get("boundary_id") != BOUNDARY_ID
        or supplied.get("status") != "supplied_exact_terminal_inputs"
        or supplied.get("gate") != EXPECTED_FINAL_GATE
        or supplied.get("inputs") != EXPECTED_FINAL_INPUTS
    ):
        raise RuntimeError("B007 exact-final-input manifest does not equal the frozen release bindings")
    raws: dict[str, bytes] = {}
    for label, identity in EXPECTED_FINAL_INPUTS.items():
        input_path = path_from_final_identity(identity)
        item_raw = input_path.read_bytes()
        if len(item_raw) != identity["bytes"] or sha256_bytes(item_raw) != identity["sha256"]:
            raise RuntimeError(f"B007 final input identity does not match disk: {label}")
        raws[label] = item_raw
    return supplied, raw, raws


def _identity_core(identity: dict[str, Any]) -> dict[str, Any]:
    return {key: identity[key] for key in ("path", "bytes", "sha256")}


def validate_final_gates(supplied: dict[str, Any], raws: dict[str, bytes]) -> dict[str, Any]:
    """Cross-bind the terminal nonvisual, visual, accessibility, and PDF proof."""
    identities = supplied["inputs"]
    gate = supplied["gate"]
    candidate = json.loads(raws["candidate_build_qa"], object_pairs_hook=_reject_duplicate_json_keys)
    build = json.loads(raws["build_qa"], object_pairs_hook=_reject_duplicate_json_keys)
    visual = json.loads(raws["visual_audit"], object_pairs_hook=_reject_duplicate_json_keys)
    locator = json.loads(raws["page_locator"], object_pairs_hook=_reject_duplicate_json_keys)
    pages = gate["inspected_pages"]
    zero_severity = gate["severity_counts"]

    render_rows: list[dict[str, Any]] = []
    render_root = Path(identities["render_manifest"]["path"]).parent
    for line in raws["render_manifest"].decode("utf-8").splitlines():
        fields = line.split("\t")
        if len(fields) != 4 or re.fullmatch(r"[0-9a-f]{64}", fields[3]) is None:
            raise RuntimeError("B007 render manifest is not canonical page/name/bytes/SHA-256 TSV")
        page = int(fields[0])
        filename = fields[1]
        if filename != f"page-{page:03d}.png":
            raise RuntimeError("B007 render-manifest page/name mapping is noncanonical")
        row = {"page": page, "path": (render_root / filename).as_posix(), "bytes": int(fields[2]), "sha256": fields[3]}
        png_raw = path_from_final_identity(row).read_bytes()
        if len(png_raw) != row["bytes"] or sha256_bytes(png_raw) != row["sha256"]:
            raise RuntimeError(f"B007 rendered page identity changed: {filename}")
        render_rows.append(row)
    if (
        [row["page"] for row in render_rows] != pages
        or len(render_rows) != identities["render_manifest"]["page_count"]
        or locator.get("all_candidate_pages") != pages
        or locator.get("prohibited_reader_visible_token_hits") != []
    ):
        raise RuntimeError("B007 page-locator/render sweep is not the frozen terminal page set")

    pdf_core = _identity_core(identities["pdf"])
    pass3_core = _identity_core(identities["pass3_pdf"])
    snapshot_core = _identity_core(identities["snapshot_manifest"])
    candidate_ok = (
        candidate.get("boundary_id") == BOUNDARY_ID
        and candidate.get("schema") == "openintro-boundary-build-candidate-qa"
        and candidate.get("schema_version") == "0.2.0"
        and candidate.get("status") == "accepted"
        and candidate.get("nonvisual_status") == "passed"
        and candidate.get("errors") == []
        and candidate.get("pending") == []
        and candidate.get("gate_script") == _identity_core(identities["build_gate_script"])
        and candidate.get("build_files", {}).get("main.log") == _identity_core(identities["build_log"])
        and candidate.get("build_files", {}).get("main-final.txt") == _identity_core(identities["build_text"])
        and _identity_core(candidate.get("candidate_artifact", {})) == pdf_core
        and candidate.get("candidate_artifact", {}).get("promoted") is False
        and candidate.get("determinism", {}).get("byte_identical") is True
        and _identity_core(candidate.get("determinism", {}).get("pass_3", {})) == pass3_core
        and _identity_core(candidate.get("determinism", {}).get("pass_4", {})) == pdf_core
        and candidate.get("links_and_structure", {}).get("page_count") == gate["page_count"]
        and candidate.get("links_and_structure", {}).get("document_language") == "id-ID"
        and candidate.get("links_and_structure", {}).get("missing_link_targets") == 0
        and _identity_core(candidate.get("source_closure", {}).get("derived_snapshot_manifest", {})) == snapshot_core
        and candidate.get("source_closure", {}).get("status") == "passed"
        and candidate.get("source_closure", {}).get("privacy_scan", {}).get("result") == "PASS_ZERO_ZERO"
        and candidate.get("visual_evidence", {}).get("candidate_pages") == pages
        and candidate.get("visual_evidence", {}).get("candidate_page_count") == len(pages)
        and candidate.get("visual_evidence", {}).get("contact_sheet") == _identity_core(identities["contact_sheet"])
        and candidate.get("visual_evidence", {}).get("page_locator") == _identity_core(identities["page_locator"])
        and candidate.get("visual_evidence", {}).get("render_manifest") == _identity_core(identities["render_manifest"])
        and candidate.get("visual_evidence", {}).get("pdf") == pdf_core
        and candidate.get("visual_evidence", {}).get("status") == "passed_operator_inspection"
        and candidate.get("visual_evidence", {}).get("required_next_action") == "none for B007 build/visual QA"
        and candidate.get("visual_evidence", {}).get("visual_audit") == _identity_core(identities["visual_audit"])
        and candidate.get("visual_evidence", {}).get("operator_inspection", {}).get("poppler_pages") == pages
        and candidate.get("visual_evidence", {}).get("operator_inspection", {}).get("all_required_b007_pages_inspected") is True
        and candidate.get("candidate_history") == EXPECTED_PENDING_CANDIDATE_HISTORY
        and candidate.get("finalization_script") == _identity_core(identities["visual_finalizer"])
        and candidate.get("build_visual_acceptance", {}).get("status") == "accepted_build_and_visual"
        and candidate.get("build_visual_acceptance", {}).get("nonvisual_status") == "passed"
        and candidate.get("build_visual_acceptance", {}).get("visual_status") == "passed"
        and candidate.get("build_visual_acceptance", {}).get("source_snapshot") == "qa/b007-build/source-snapshot-v8"
        and candidate.get("build_visual_acceptance", {}).get("source_snapshot_manifest") == snapshot_core
        and candidate.get("build_visual_acceptance", {}).get("source_or_layout_mutated_by_finalization") is False
        and candidate.get("build_visual_acceptance", {}).get("output_mutated") is False
        and candidate.get("build_visual_acceptance", {}).get("backend_or_control_mutated") is False
        and candidate.get("build_visual_acceptance", {}).get("publication_performed") is False
        and candidate.get("privacy_final") == {"absolute_profile_path_hits": 0, "prohibited_token_hits": 0, "result": "PASS_ZERO_ZERO"}
    )
    if not candidate_ok:
        raise RuntimeError("B007 candidate build receipt does not prove the exact terminal nonvisual closure")

    build_ok = (
        build.get("boundary_id") == BOUNDARY_ID
        and build.get("schema") == "openintro-boundary-build-final-qa"
        and build.get("schema_version") == "0.3.0"
        and build.get("status") == "passed"
        and build.get("candidate") == gate["candidate"]
        and build.get("nonvisual_status") == "passed"
        and build.get("visual_status") == "passed"
        and build.get("finalization_script") == _identity_core(identities["visual_finalizer"])
        and build.get("accepted_candidate_build_receipt") == _identity_core(identities["candidate_build_qa"])
        and build.get("pending_candidate_preimage") == EXPECTED_PENDING_CANDIDATE_HISTORY
        and build.get("visual_audit") == _identity_core(identities["visual_audit"])
        and build.get("snapshot_manifest") == snapshot_core
        and _identity_core(build.get("candidate_pdf", {})) == pdf_core
        and build.get("candidate_pdf", {}).get("page_count") == gate["page_count"]
        and build.get("candidate_pdf", {}).get("promoted") is False
        and build.get("checks")
        and set(build.get("checks", {}).values()) == {"passed"}
        and build.get("promotion") == {
            "backend_or_control_mutated": False,
            "canonical_pdf_promoted": False,
            "performed": False,
            "publication_performed": False,
        }
        and build.get("privacy") == {"absolute_profile_path_hits": 0, "prohibited_token_hits": 0, "result": "PASS_ZERO_ZERO"}
    )
    if not build_ok:
        raise RuntimeError("B007 final build receipt does not prove the exact terminal build/visual closure")

    visual_rows = visual.get("evidence", {}).get("poppler", {}).get("page_renders", [])
    visual_ok = (
        visual.get("boundary_id") == BOUNDARY_ID
        and visual.get("candidate") == gate["candidate"]
        and visual.get("schema") == "openintro-boundary-visual-audit"
        and visual.get("schema_version") == "0.3.0"
        and visual.get("status") == "passed"
        and visual.get("candidate_build_receipt") == _identity_core(EXPECTED_PENDING_CANDIDATE_HISTORY)
        and visual.get("finalization_script") == _identity_core(identities["visual_finalizer"])
        and visual.get("severity_counts_within_b007") == zero_severity
        and visual.get("findings_within_b007") == []
        and visual.get("checks")
        and all(str(value).startswith("passed") for value in visual.get("checks", {}).values())
        and visual.get("promotion", {}).get("performed") is False
        and visual.get("inspection", {}).get("all_required_b007_pages_inspected") is True
        and visual.get("inspection", {}).get("poppler_inspected_page_count") == len(pages)
        and visual.get("inspection", {}).get("poppler_inspected_pages") == pages
        and _identity_core(visual.get("evidence", {}).get("candidate_pdf", {})) == pdf_core
        and visual.get("evidence", {}).get("candidate_pdf", {}).get("pages") == gate["page_count"]
        and visual.get("evidence", {}).get("poppler", {}).get("contact_sheet") == _identity_core(identities["contact_sheet"])
        and visual.get("evidence", {}).get("poppler", {}).get("page_locator") == _identity_core(identities["page_locator"])
        and visual.get("evidence", {}).get("poppler", {}).get("render_manifest") == _identity_core(identities["render_manifest"])
        and visual.get("evidence", {}).get("poppler", {}).get("page_render_bytes") == sum(row["bytes"] for row in render_rows)
        and visual_rows == render_rows
        and visual.get("privacy") == {"absolute_profile_path_hits": 0, "prohibited_token_hits": 0}
    )
    if not visual_ok:
        raise RuntimeError("B007 visual audit does not prove the exact zero-severity full-page sweep")

    if raws["pass3_pdf"] != raws["pdf"]:
        raise RuntimeError("B007 pass-3 and terminal PDF bytes are not identical")
    reader = PdfReader(path_from_final_identity(identities["pdf"]))
    document_language = str(reader.trailer["/Root"].get("/Lang", ""))
    if reader.is_encrypted or len(reader.pages) != gate["page_count"] or document_language != "id-ID":
        raise RuntimeError("B007 PDF page-count, encryption, or /Lang gate failed")
    if not raws["build_text"] or b"statistika" not in raws["build_text"].lower():
        raise RuntimeError("B007 extracted-text accessibility witness is empty or not Indonesian")
    return {
        "candidate": candidate,
        "build": build,
        "visual": visual,
        "render_rows": render_rows,
        "rendered_page_count": len(render_rows),
        "severity_counts": zero_severity,
        "inspected_pages": pages,
        "document_language": document_language,
        "candidate_pdf_promoted": False,
    }


def augment_final_records(
    records: dict[str, list[dict[str, Any]]],
    context: dict[str, Any],
    supplied_raw: bytes,
    final_raws: dict[str, bytes],
    final_gate: dict[str, Any],
) -> dict[str, str]:
    identities = EXPECTED_FINAL_INPUTS
    evidence = {
        "evidence/R011-B007_FINAL_GATE_INPUTS.json": supplied_raw,
        "evidence/R011-B007_SNAPSHOT_MANIFEST.tsv": final_raws["snapshot_manifest"],
        "evidence/R011-B007_CANDIDATE_BUILD_QA.json": final_raws["candidate_build_qa"],
        "evidence/R011-B007_BUILD_QA.json": final_raws["build_qa"],
        "evidence/R011-B007_RENDER_MANIFEST.tsv": final_raws["render_manifest"],
        "evidence/R011-B007_PAGE_LOCATOR.json": final_raws["page_locator"],
        "evidence/R011-B007_VISUAL_AUDIT.json": final_raws["visual_audit"],
    }
    context["evidence_payloads"].update(evidence)
    copied_paths = {
        "final-inputs": "evidence/R011-B007_FINAL_GATE_INPUTS.json",
        "snapshot-manifest": "evidence/R011-B007_SNAPSHOT_MANIFEST.tsv",
        "candidate-build-qa": "evidence/R011-B007_CANDIDATE_BUILD_QA.json",
        "build-qa": "evidence/R011-B007_BUILD_QA.json",
        "render-manifest": "evidence/R011-B007_RENDER_MANIFEST.tsv",
        "page-locator": "evidence/R011-B007_PAGE_LOCATOR.json",
        "visual-audit": "evidence/R011-B007_VISUAL_AUDIT.json",
    }
    specs = [
        ("final-inputs", "exact_final_input_manifest", supplied_raw, None, "zxx", "structurally_verified"),
        ("snapshot-manifest", "exact_build_snapshot_manifest", final_raws["snapshot_manifest"], None, "zxx", "source_frozen"),
        ("build-gate", "deterministic_build_gate", final_raws["build_gate_script"], identities["build_gate_script"]["path"], "zxx", "structurally_verified"),
        ("candidate-build-qa", "candidate_build_qa_receipt", final_raws["candidate_build_qa"], None, "zxx", "structurally_verified"),
        ("build-qa", "final_build_qa_receipt", final_raws["build_qa"], None, "zxx", "structurally_verified"),
        ("build-log", "build_log", final_raws["build_log"], identities["build_log"]["path"], "id-ID", "built"),
        ("build-text", "extracted_accessibility_text", final_raws["build_text"], identities["build_text"]["path"], "id-ID", "built"),
        ("pass3-pdf", "deterministic_build_pdf_witness", final_raws["pass3_pdf"], identities["pass3_pdf"]["path"], "id-ID", "built"),
        ("pdf", "localized_boundary_pdf", final_raws["pdf"], identities["pdf"]["path"], "id-ID", "visually_checked"),
        ("render-manifest", "visual_qa_manifest", final_raws["render_manifest"], None, "zxx", "visually_checked"),
        ("page-locator", "visual_page_locator", final_raws["page_locator"], None, "zxx", "visually_checked"),
        ("contact-sheet", "visual_contact_sheet", final_raws["contact_sheet"], identities["contact_sheet"]["path"], "zxx", "visually_checked"),
        ("visual-audit", "visual_audit_receipt", final_raws["visual_audit"], None, "zxx", "visually_checked"),
        ("visual-finalizer", "visual_qa_finalizer", final_raws["visual_finalizer"], identities["visual_finalizer"]["path"], "zxx", "structurally_verified"),
    ]
    artifact_ids: dict[str, str] = {}
    upstream_rights_id = g.stable_id("r011/rights/upstream-cc-by-sa-3.0")
    for slug, kind, raw, original_path, locale, state in specs:
        key = f"r011/artifact/b007-final-{slug}"
        artifact_id = g.stable_id(key)
        artifact_ids[slug] = artifact_id
        stored = copied_paths.get(slug)
        path = f"qa/b007-backend/exports/{stored}" if stored else original_path
        extra: dict[str, Any] = {}
        rights_ids: list[str] = []
        result = "exact_terminal_gate_input"
        if slug == "pdf":
            rights_ids = [upstream_rights_id, context["generated_rights_id"], context["data_rights_id"]]
            result = "built_and_visually_verified_not_promoted"
            extra = {
                "page_count": EXPECTED_FINAL_GATE["page_count"],
                "document_language": final_gate["document_language"],
                "consecutive_pass_hashes_identical": True,
                "candidate_pdf_promoted": False,
                "build_receipt": identities["build_qa"]["path"],
                "visual_receipt": identities["visual_audit"]["path"],
            }
        records["artifacts"].append(
            rrecord(
                "artifact", key, artifact_kind=kind, path=path, bytes=len(raw), sha256=sha256_bytes(raw),
                result=result, resource_id=context["resource_id"], edition_id=context["edition_id"],
                source_local_ids=[BOUNDARY_ID, "FINAL-GATE"], parent_id=context["edition_id"],
                order=len(records["artifacts"]) + 1, locale=locale, translation_state=state,
                status="passed", rights_component_ids=rights_ids, boundary_id=BOUNDARY_ID,
                source_path=None, source_span=None, source_sha256=None,
                toolchain="R011-B007 exact terminal build/visual input; separate admission required", **extra,
            )
        )

    qa_specs = [
        ("final-build", "build", "The terminal PDF is byte-identical across consecutive passes and the final build receipt closes all nonvisual and visual checks.", identities["build_qa"]["path"]),
        ("final-visual", "visual", "Every receipt-bound full-resolution page passed operator review with P0-P3 all zero.", identities["visual_audit"]["path"]),
        ("final-accessibility", "accessibility", "The terminal PDF has /Lang id-ID, exact extracted text, a closed page count, and zero missing link targets.", identities["build_qa"]["path"]),
    ]
    for suffix, qa_type, detail, witness in qa_specs:
        records["qa_events"].append(
            rrecord(
                "qa_event", f"r011/qa/b007-{suffix}", qa_type=qa_type, result="passed",
                subject_id=context["edition_id"], witness_path=witness, detail=detail,
                resource_id=context["resource_id"], edition_id=context["edition_id"],
                source_local_ids=[BOUNDARY_ID, "FINAL-GATE"], parent_id=context["edition_id"],
                order=len(records["qa_events"]) + 1, locale="id-ID", translation_state="visually_checked",
                status="passed", rights_component_ids=[], boundary_id=BOUNDARY_ID,
                source_path=None, source_span=None, source_sha256=None,
            )
        )
    add_relation(records, "final-candidate-supports-build", "supports", artifact_ids["candidate-build-qa"], artifact_ids["build-qa"], qualifier="exact preserved candidate history")
    add_relation(records, "final-build-verifies-pdf", "verifies", artifact_ids["build-qa"], artifact_ids["pdf"], qualifier="deterministic nonvisual and accessibility closure")
    add_relation(records, "final-visual-verifies-pdf", "verifies", artifact_ids["visual-audit"], artifact_ids["pdf"], qualifier="zero-severity operator sweep")
    add_relation(records, "final-render-supports-visual", "supports", artifact_ids["render-manifest"], artifact_ids["visual-audit"], qualifier="exact individual PNG inventory")
    return artifact_ids


def build_payloads(final_inputs_path: Path = FINAL_INPUTS_DEFAULT) -> dict[str, bytes]:
    supplied, supplied_raw, final_raws = load_final_inputs(final_inputs_path)
    final_gate = validate_final_gates(supplied, final_raws)
    records, context = build_records()
    augment_final_records(records, context, supplied_raw, final_raws, final_gate)
    payloads = {relative: g.jsonl_bytes(records[name]) for name, relative in RECORD_PATHS.items()}
    all_records = [row for collection in records.values() for row in collection]
    payloads["identity_map.jsonl"] = g.jsonl_bytes(
        {"id": row["id"], "record_type": row["record_type"], "stable_key": row["stable_key"], "source_local_ids": row.get("source_local_ids", [])}
        for row in all_records
    )
    view_schema = json.loads((LIVE_BACKEND / "schemas" / "backend-view-columns-v0.1.0.json").read_text(encoding="utf-8"))
    payloads.update(g.build_views(records, view_schema["views"]))
    payloads.update(context["base_auxiliary"])
    payloads.update(context["evidence_payloads"])
    for schema_path in sorted((LIVE_BACKEND / "schemas").glob("*")):
        if schema_path.is_file():
            payloads[f"schemas/{schema_path.name}"] = schema_path.read_bytes()

    new_counts = {
        name: sum(1 for row in rows if row.get("boundary_id") == BOUNDARY_ID)
        for name, rows in sorted(records.items())
    }
    deferred = [
        "B007 final admission receipt plus atomic exact-PDF and live-backend promotion proof",
    ]
    file_entries = [
        {"path": path, "bytes": len(raw), "sha256": sha256_bytes(raw), "records": payload_record_count(path, raw)}
        for path, raw in sorted(payloads.items())
    ]
    manifest = {
        "$schema": "schemas/backend-manifest-v0.1.0.schema.json",
        "schema_version": SCHEMA_VERSION,
        "backend_id": g.stable_id("r011/backend/R011-B007/nonadmitted-stage/v0"),
        "namespace_uuid": str(g.NAMESPACE),
        "workflow_id": WORKFLOW_ID,
        "recorded_at": RECORDED_AT,
        "authority": {
            "repository": context["authority"]["repository"],
            "branch_observed": context["authority"]["branch_observed"],
            "commit": context["authority"]["commit"],
            "tree": context["authority"]["calculated_git_tree_sha1"],
            "authority_path": "authority/UPSTREAM_AUTHORITY.json",
            "authority_sha256": g.sha256_file(g.AUTHORITY_PATH),
            "source_file_manifest_sha256": context["authority"]["manifest_sha256"],
        },
        "canonicalization": {
            "encoding": "UTF-8 without BOM", "normalization": "Unicode NFC", "line_endings": "LF",
            "json": "RFC-8785-compatible integer/string subset; keys sorted; compact separators", "record_order": "ascending UUID string",
        },
        "scope": {
            "base_boundary": BASE_BOUNDARY_ID,
            "translated_boundaries": ["R011-B001", "R011-B002", "R011-B003", "R011-B004", "R011-B004R", "R011-B005", "R011-B006", BOUNDARY_ID],
            "chapter": "ch_summarizing_data", "unit": "Complete canonical Section 2.3 Case study: malaria vaccine translation checkpoint",
            "instructional_subsections": ["Variability within data", "Simulating the study", "Checking for independence"],
            "guided_feedback_count": 3, "end_of_section_exercises": ["2.25", "2.26"], "public_answers": ["2.25"],
            "o001_gaps": ["2.26"], "translation_segment_count": 11, "original_terminology_candidate_count": 20,
            "controlled_term_range": ["R011-TERM-0142", "R011-TERM-0160"], "new_concept_count": 19,
            "reused_admitted_term": "randomization / pengacakan (R011-TERM-0062)",
            "superseded_admitted_term": "R011-TERM-0088 bin: kelas interval (bin) -> interval kelas (bin)",
            "noncontrolled_title_phrase": "case study / studi kasus",
            "source_correction_count": 8, "source_reader_pdf_count": 5, "source_producer_count": 3,
            "localized_producer_count": 3, "localized_reader_pdf_count": 5, "english_witness_pdf_count": 5,
            "serialized_generator_input_count": 1, "target_locale": "id-ID",
        },
        "candidate_authority": {
            "candidate_manifest": {"path": "scratch/R011-B007-candidate/CANDIDATE_MANIFEST.json", **EXPECTED_CANDIDATE_MANIFEST},
            "validation_receipt": {"path": "scratch/R011-B007-candidate/VALIDATION_RECEIPT.json", **EXPECTED_VALIDATION_RECEIPT},
            "validation_result": context["candidate_receipt"]["result"],
            "canonical_mutation": False, "candidate_r_execution": "not_run", "candidate_pdf_replay": "not_run",
            "terminology_field_qa": {"path": "qa/terminology/R011_TERMINOLOGY_FIELD_USAGE_QA.json", **EXPECTED_FIELD_QA},
            "terminology_field_qa_note": {"path": "qa/terminology/R011_TERMINOLOGY_FIELD_USAGE_QA.md", **EXPECTED_FIELD_QA_NOTE},
            "terminology_propagation_status": context["field_qa"]["status"],
        },
        "canonical_source_gate": {
            "application_manifest": {"path": "qa/R011-B007_SOURCE_APPLICATION_MANIFEST.json", **EXPECTED_SOURCE_APPLICATION_MANIFEST},
            "application_receipt": {"path": "qa/R011-B007_SOURCE_APPLICATION_RECEIPT.json", **EXPECTED_SOURCE_APPLICATION_RECEIPT},
            "qa": {"path": "qa/R011-B007_SOURCE_GATE_QA.json", **EXPECTED_SOURCE_GATE_QA},
            "result": context["source_gate_qa"]["result"],
            "checks": context["source_gate_qa"]["checks"],
            "adversarial_self_tests": context["source_gate_qa"]["adversarial_self_tests"],
            "remaining_source_or_asset_dependency": None,
        },
        "asset_authority": {
            "canonical_promotion_receipt": {"path": "qa/b007-assets/B007_CANONICAL_PROMOTION_RECEIPT.json", **EXPECTED_ASSET_PROMOTION_RECEIPT},
            "localization_receipt": {"path": "qa/b007-assets/B007_ASSET_LOCALIZATION_RECEIPT.json", **EXPECTED_ASSET_LOCALIZATION_RECEIPT},
            "output_manifest": {"path": "qa/b007-assets/B007_ASSET_OUTPUT_MANIFEST.json", **EXPECTED_ASSET_OUTPUT_MANIFEST},
            "privacy_refresh_qa": {"path": "qa/b007-assets/B007_ASSET_PRIVACY_REFRESH_QA.json", **EXPECTED_ASSET_PRIVACY_QA},
            "canonical_destination_count": context["asset_promotion"]["operation_count"],
            "promotion_status": context["asset_promotion"]["status"],
            "qa_severity_counts": context["asset_promotion"]["qa"],
        },
        "final_gates": {
            "status": "passed_exact_terminal_inputs_stage_only",
            "input_manifest": {
                "path": final_inputs_path.resolve().relative_to(LANE.resolve()).as_posix(),
                "bytes": len(supplied_raw),
                "sha256": sha256_bytes(supplied_raw),
            },
            "snapshot_manifest": EXPECTED_FINAL_INPUTS["snapshot_manifest"],
            "build_gate_script": EXPECTED_FINAL_INPUTS["build_gate_script"],
            "candidate_build_qa": EXPECTED_FINAL_INPUTS["candidate_build_qa"],
            "build_qa": EXPECTED_FINAL_INPUTS["build_qa"],
            "build_log": EXPECTED_FINAL_INPUTS["build_log"],
            "build_text": EXPECTED_FINAL_INPUTS["build_text"],
            "pass3_pdf": EXPECTED_FINAL_INPUTS["pass3_pdf"],
            "reviewed_candidate_pdf": EXPECTED_FINAL_INPUTS["pdf"],
            "render_manifest": EXPECTED_FINAL_INPUTS["render_manifest"],
            "page_locator": EXPECTED_FINAL_INPUTS["page_locator"],
            "contact_sheet": EXPECTED_FINAL_INPUTS["contact_sheet"],
            "visual_audit": EXPECTED_FINAL_INPUTS["visual_audit"],
            "visual_finalizer": EXPECTED_FINAL_INPUTS["visual_finalizer"],
            "candidate": EXPECTED_FINAL_GATE["candidate"],
            "page_count": EXPECTED_FINAL_GATE["page_count"],
            "rendered_page_count": final_gate["rendered_page_count"],
            "inspected_pages": final_gate["inspected_pages"],
            "severity_counts": final_gate["severity_counts"],
            "document_language": final_gate["document_language"],
            "candidate_pdf_promoted": False,
        },
        "privacy_gate": {
            "receipt": {
                "path": f"qa/b007-backend/exports/{PRIVACY_RECEIPT_EXPORT_PATH}",
                "bytes": len(context["privacy_receipt_raw"]),
                "sha256": sha256_bytes(context["privacy_receipt_raw"]),
            },
            "active_localization_revision_count": len(context["privacy_record_revisions"]),
            "canonical_target_text_rebind_count": sum(1 for item in context["privacy_record_revisions"] if item["target_text_rebound"]),
            "sanitized_historical_evidence_copy_count": len(context["privacy_auxiliary_revisions"]),
            "prohibited_requester_token_hits": 0,
            "absolute_local_user_profile_path_hits": 0,
            "live_backend_mutated": False,
            "canonical_historical_evidence_mutated": False,
        },
        "stage_state": {
            "status": "isolated_final_backend_validated_ready_for_admission", "live_backend_mutated": False,
            "canonical_source_mutated": False, "canonical_target_spans_bound": True,
            "localized_pdf_assets_built": True, "canonical_asset_promotion_performed": True,
            "build_performed": True, "build_and_visual_gates_passed": True,
            "boundary_admitted": False, "promotion_performed": False,
        },
        "base_preservation": {
            "base_manifest_bytes": BASE_MANIFEST_BYTES, "base_manifest_sha256": BASE_MANIFEST_SHA256,
            "base_record_count": BASE_RECORD_COUNT, "base_boundary": BASE_BOUNDARY_ID,
            "prior_artifact_history": "all admitted auxiliary evidence origins retain exact local identities; six affected historical evidence files are emitted only as privacy-sanitized copies whose original and packaged identities are bound by the B007 privacy receipt",
            "active_record_revision_policy": "stable IDs retained; all inherited localization records receive provenance-only privacy revisions and only exact field-QA-affected term/localization records receive additional semantic target revisions",
            "active_overlay_revisions": context["active_overlay_revisions"],
            "prior_term_0088_record_sha256": context["prior_bin_record_identity"],
            "privacy_provenance_revision_count": len(context["privacy_record_revisions"]),
            "privacy_sanitized_auxiliary_copy_count": len(context["privacy_auxiliary_revisions"]),
            "privacy_receipt_path": f"qa/b007-backend/exports/{PRIVACY_RECEIPT_EXPORT_PATH}",
        },
        "record_counts": {name: len(rows) for name, rows in sorted(records.items())},
        "new_record_counts": new_counts,
        "publication_eligibility": "boundary_ready_for_separate_admission",
        "publication_blockers": deferred,
        "deferred_completion_bindings": deferred,
        "placeholder_count": 0,
        "known_limitations": [
            "The five Indonesian PDFs, five adjacent English witnesses, three localized producers, and inference.RData are exact, canonical, and source-gate bound.",
            "Exercise 2.26 has no public upstream answer; the O001 gap is explicit and no solution was invented.",
            "The Avandia N=1000 PDF is a receipt-bound deterministic NumPy PCG64 hypergeometric render; the localized canonical R producer is preserved, but no exact R replay is claimed.",
            "Active term/localization views bind the propagated field-QA wording and canonical target spans; only the separate exact admission transaction remains deferred.",
        ],
        "files": file_entries,
    }
    payloads["manifest.json"] = (g.canonical_json(manifest) + "\n").encode("utf-8")
    privacy_findings = payload_privacy_findings(payloads, context["prohibited_token"])
    if any(privacy_findings.values()):
        raise RuntimeError(f"public B007 backend payload privacy scan failed: {privacy_findings}")
    return payloads


def write_payloads(payloads: dict[str, bytes]) -> None:
    expected = set(payloads)
    if STAGE_EXPORTS.exists():
        for path in STAGE_EXPORTS.rglob("*"):
            if path.is_file() and path.relative_to(STAGE_EXPORTS).as_posix() not in expected:
                path.unlink()
    for relative, raw in sorted(payloads.items()):
        destination = STAGE_EXPORTS / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--final-inputs", type=Path, default=FINAL_INPUTS_DEFAULT, help="exact canonical B007 terminal-input manifest")
    parser.add_argument("--check-readiness", action="store_true", help="report frozen-binding readiness without reading or writing stage payloads")
    args = parser.parse_args()
    if args.check_readiness:
        gaps = final_binding_gaps()
        print(g.canonical_json({
            "boundary_id": BOUNDARY_ID,
            "status": "ready" if not gaps else "blocked_unfrozen_exact_bindings",
            "binding_manifest": FINAL_INPUTS_DEFAULT.relative_to(LANE).as_posix(),
            "deferred_bindings": gaps,
            "stage_written": False,
            "live_backend_mutated": False,
            "output_mutated": False,
        }))
        return 0 if not gaps else 2
    final_inputs = args.final_inputs.resolve()
    try:
        final_inputs.relative_to(LANE.resolve())
    except ValueError as exc:
        raise RuntimeError("final-input manifest must remain inside the R011 lane") from exc
    first = build_payloads(final_inputs)
    second = build_payloads(final_inputs)
    if first != second:
        raise RuntimeError("B007 backend generator is not deterministic in memory")
    write_payloads(first)
    manifest = json.loads(first["manifest.json"])
    print(f"generated={len(first)}")
    print(f"typed_records={sum(manifest['record_counts'].values())}")
    print(f"new_records={sum(manifest['new_record_counts'].values())}")
    print(f"manifest_sha256={sha256_bytes(first['manifest.json'])}")
    print("boundary_admitted=false")
    print("live_backend_mutated=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
