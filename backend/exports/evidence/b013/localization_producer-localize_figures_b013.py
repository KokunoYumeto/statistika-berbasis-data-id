#!/usr/bin/env python3
"""Create deterministic id-ID label overlays for R011-B013 figures.

Only reader-visible x-axis labels change. Every datum, graphical mark, scale,
page box, and source figure identity remains fixed to the pinned authority.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import fitz


ROOT = Path(__file__).resolve().parents[2]
MODEL = "OpenAI Codex gpt-5.6-sol, Ultra"
OUTPUT_ROOT = ROOT / "scratch" / "b013-candidate" / "assets"
RECEIPT = Path(__file__).with_name("R011-B013_LOCALIZED_FIGURE_RECEIPT.json")

FIGURES = (
    {
        "id": "fdicHistograms",
        "source": Path(
            "repo/ch_probability/figures/fdicHistograms/fdicHistograms.pdf"
        ),
        "sha256": "71302f94a80df3afbc9a82deaf7b751b822c34b4e05c0527cb00c381d2083162",
        "destination": Path(
            "ch_probability/figures/fdicHistograms/fdicHistograms.pdf"
        ),
        "page_box": [0.0, 0.0, 446.0, 237.0],
        "source_text": "height (cm)",
        "source_count": 4,
        "localized_text": "tinggi (cm)",
        "insertions": (
            ([70.0, 102.0, 155.0, 119.0], 10.0),
            ([293.0, 102.0, 378.0, 119.0], 10.0),
            ([70.0, 220.0, 155.0, 237.0], 10.0),
            ([293.0, 220.0, 378.0, 237.0], 10.0),
        ),
    },
    {
        "id": "usHeightsHist180185",
        "source": Path(
            "repo/ch_probability/figures/usHeightsHist180185/"
            "usHeightsHist180185.pdf"
        ),
        "sha256": "3fc3fead04b32067b15e6863c6ad4776351e10e75955a1498dc1692141206c42",
        "destination": Path(
            "ch_probability/figures/usHeightsHist180185/"
            "usHeightsHist180185.pdf"
        ),
        "page_box": [0.0, 0.0, 496.0, 227.0],
        "source_text": "height (cm)",
        "source_count": 1,
        "localized_text": "tinggi (cm)",
        "insertions": (([180.0, 204.0, 316.0, 227.0], 11.0),),
    },
    {
        "id": "fdicHeightContDist",
        "source": Path(
            "repo/ch_probability/figures/fdicHeightContDist/"
            "fdicHeightContDist.pdf"
        ),
        "sha256": "fc6179b789afdeca709a6ce707cf5111c71a43a3ef43e5bb42ae6a3a778d4952",
        "destination": Path(
            "ch_probability/figures/fdicHeightContDist/"
            "fdicHeightContDist.pdf"
        ),
        "page_box": [0.0, 0.0, 480.0, 231.0],
        "source_text": "height (cm)",
        "source_count": 1,
        "localized_text": "tinggi (cm)",
        "insertions": (([175.0, 208.0, 305.0, 231.0], 11.0),),
    },
    {
        "id": "fdicHeightContDistFilled",
        "source": Path(
            "repo/ch_probability/figures/fdicHeightContDistFilled/"
            "fdicHeightContDistFilled.pdf"
        ),
        "sha256": "10a87bce4c78fd6708770798f471e5c91c6093d758ac0e115d772ea7853a9149",
        "destination": Path(
            "ch_probability/figures/fdicHeightContDistFilled/"
            "fdicHeightContDistFilled.pdf"
        ),
        "page_box": [0.0, 0.0, 410.0, 198.0],
        "source_text": "height (cm)",
        "source_count": 1,
        "localized_text": "tinggi (cm)",
        "insertions": (([138.0, 175.0, 272.0, 198.0], 11.0),),
    },
    {
        "id": "cat_weights",
        "source": Path(
            "repo/ch_probability/figures/eoce/cat_weights/cat_weights.pdf"
        ),
        "sha256": "26dd765ba632563b41e40aee564dfc1eb456e34464ae318685140729c786d72e",
        "destination": Path(
            "ch_probability/figures/eoce/cat_weights/cat_weights.pdf"
        ),
        "page_box": [0.0, 0.0, 396.0, 309.0],
        "source_text": "Body weight",
        "source_count": 1,
        "localized_text": "Berat badan (kg)",
        "insertions": (([100.0, 278.0, 320.0, 309.0], 15.0),),
    },
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def identity(path: Path) -> dict[str, object]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def localize(spec: dict[str, object]) -> dict[str, object]:
    source = ROOT / spec["source"]
    if sha256(source) != spec["sha256"]:
        raise RuntimeError(f"source identity changed: {spec['source']}")

    destination = OUTPUT_ROOT / spec["destination"]
    destination.parent.mkdir(parents=True, exist_ok=True)
    document = fitz.open(source)
    if document.page_count != 1:
        raise RuntimeError(f"expected one page: {spec['source']}")
    page = document[0]
    if [float(value) for value in page.rect] != spec["page_box"]:
        raise RuntimeError(f"page box changed: {spec['source']}")

    matches = page.search_for(spec["source_text"])
    if len(matches) != spec["source_count"]:
        raise RuntimeError(
            f"label count mismatch for {spec['id']}: "
            f"expected {spec['source_count']}, observed {len(matches)}"
        )
    for match in matches:
        match.x0 -= 1.0
        match.y0 -= 0.5
        match.x1 += 1.0
        match.y1 += 0.5
        page.add_redact_annot(match, fill=(1, 1, 1))
    page.apply_redactions(images=0, graphics=0, text=0)

    for rectangle, fontsize in spec["insertions"]:
        remainder = page.insert_textbox(
            fitz.Rect(rectangle),
            spec["localized_text"],
            fontname="helv",
            fontsize=fontsize,
            align=fitz.TEXT_ALIGN_CENTER,
            color=(0, 0, 0),
            overlay=True,
        )
        if remainder < 0:
            raise RuntimeError(f"localized label does not fit: {spec['id']}")

    visible = page.get_text("text")
    if spec["source_text"] in visible:
        raise RuntimeError(f"English label remains: {spec['id']}")
    observed_localized = visible.count(spec["localized_text"])
    if observed_localized != spec["source_count"]:
        raise RuntimeError(
            f"localized label count mismatch for {spec['id']}: "
            f"expected {spec['source_count']}, observed {observed_localized}"
        )

    metadata = dict(document.metadata)
    metadata.update(
        {
            "title": f"{spec['id']} - label Bahasa Indonesia",
            "subject": "Localized derivative for R011-B013",
            "keywords": "Bahasa Indonesia, OpenIntro Statistics, R011-B013",
            "creator": MODEL,
            "producer": "PyMuPDF deterministic label-localization producer",
            "creationDate": "D:20260824000000+02'00'",
            "modDate": "D:20260824000000+02'00'",
        }
    )
    document.set_metadata(metadata)
    document.save(
        destination,
        garbage=4,
        clean=True,
        deflate=True,
        no_new_id=True,
        preserve_metadata=True,
    )
    document.close()

    check = fitz.open(destination)
    try:
        check_page = check[0]
        if [float(value) for value in check_page.rect] != spec["page_box"]:
            raise RuntimeError(f"localized page box changed: {spec['id']}")
        check_text = check_page.get_text("text")
        if spec["source_text"] in check_text:
            raise RuntimeError(f"saved English label remains: {spec['id']}")
        if check_text.count(spec["localized_text"]) != spec["source_count"]:
            raise RuntimeError(f"saved localized label missing: {spec['id']}")
    finally:
        check.close()

    return {
        "id": spec["id"],
        "source": identity(source),
        "localized": identity(destination),
        "page_box": spec["page_box"],
        "forbidden_visible_text": [spec["source_text"]],
        "required_visible_text": [spec["localized_text"]],
        "required_visible_count": spec["source_count"],
        "semantic_change": "none; reader-visible axis-label localization only",
    }


def main() -> int:
    rows = [localize(spec) for spec in FIGURES]
    receipt = {
        "$schema": "interlanguage.r011-b013-localized-figure-receipt/v1",
        "boundary_id": "R011-B013",
        "status": "PASS_EXACT_LABEL_ONLY_LOCALIZATION",
        "production_model": MODEL,
        "license": (
            "CC BY-SA 3.0 repository declaration; preserve source attribution"
        ),
        "figures": rows,
    }
    RECEIPT.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "receipt": identity(RECEIPT),
                "localized": [row["localized"] for row in rows],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
