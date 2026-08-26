#!/usr/bin/env python3
"""Build the bounded R011-B016 source, asset, and rights closure.

This script is deliberately offline and only reads the exact files enumerated
below.  It does not mutate the live translation tree.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import tarfile
from pathlib import Path

from PIL import Image
from pypdf import PdfReader


REPO = Path(__file__).resolve().parents[2]
AUTHORITY_PREFIX = (
    "authority/upstream/"
    "openintro-statistics-fee25091fb24e89c36296fd67c48c1fcf7a93b6e"
)
AUTHORITY = REPO / AUTHORITY_PREFIX
SOURCE_OUT = REPO / "qa/b016-source"
ASSET_OUT = REPO / "qa/b016-assets"
COMMIT = "fee25091fb24e89c36296fd67c48c1fcf7a93b6e"
TREE = "d61cc601e7d97759ce805900520f784d02a0489e"
MODEL = "OpenAI Codex gpt-5.6-sol, Ultra"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(REPO).as_posix()


def identity(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    return {
        "path": rel(path),
        "bytes": len(data),
        "sha256": sha256_bytes(data),
    }


def exact_line_slice(path: Path, start: int, end: int) -> bytes:
    """Return one-based inclusive lines, preserving the authority EOL bytes."""
    data = path.read_bytes()
    lines = data.splitlines(keepends=True)
    assert 1 <= start <= end <= len(lines), (path, start, end, len(lines))
    return b"".join(lines[start - 1 : end])


def write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def write_json(path: Path, value: object) -> None:
    write_bytes(
        path,
        (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
            "utf-8"
        ),
    )


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    write_bytes(path, stream.getvalue().encode("utf-8"))


def source_manifest_row(
    scope: str,
    role: str,
    path: Path,
    disposition: str,
    license_name: str,
    notes: str,
    line_start: int | str = "",
    line_end: int | str = "",
) -> dict[str, object]:
    ident = identity(path)
    return {
        "scope": scope,
        "role": role,
        "disposition": disposition,
        **ident,
        "line_start_inclusive": line_start,
        "line_end_inclusive": line_end,
        "license": license_name,
        "notes": notes,
    }


def asset_manifest_row(
    asset_id: str,
    role: str,
    path_kind: str,
    path: Path,
    media_type: str,
    license_name: str,
    disposition: str,
    reader_visible_text: str,
    dependency_notes: str,
) -> dict[str, object]:
    ident = identity(path)
    return {
        "asset_id": asset_id,
        "role": role,
        "path_kind": path_kind,
        **ident,
        "media_type": media_type,
        "license": license_name,
        "disposition": disposition,
        "reader_visible_text": reader_visible_text,
        "dependency_notes": dependency_notes,
    }


def regex_values(text: str, pattern: str) -> list[str]:
    return [match.group(1) for match in re.finditer(pattern, text)]


def pdf_facts(path: Path) -> dict[str, object]:
    reader = PdfReader(path)
    assert len(reader.pages) == 1
    page = reader.pages[0]
    box = page.mediabox
    extracted = " ".join((page.extract_text() or "").split())
    return {
        "pages": 1,
        "media_box_points": [
            float(box.left),
            float(box.bottom),
            float(box.right),
            float(box.top),
        ],
        "extracted_text_normalized": extracted,
        "encrypted": bool(reader.is_encrypted),
    }


def tar_member_identity(archive: Path, member: str) -> dict[str, object]:
    with tarfile.open(archive, "r:gz") as tar:
        extracted = tar.extractfile(member)
        assert extracted is not None, member
        data = extracted.read()
    return {"member": member, "bytes": len(data), "sha256": sha256_bytes(data)}


def main() -> None:
    SOURCE_OUT.mkdir(parents=True, exist_ok=True)
    ASSET_OUT.mkdir(parents=True, exist_ok=True)

    main_tex = AUTHORITY / "ch_distributions/TeX/ch_distributions.tex"
    eoce_tex = AUTHORITY / "ch_distributions/TeX/binomial_distribution.tex"
    answers_tex = AUTHORITY / "extraTeX/eoceSolutions/eoceSolutions.tex"
    data_tex = AUTHORITY / "extraTeX/data/data.tex"
    bib = AUTHORITY / "eoce.bib"

    # Fail closed on the assigned authority cursor and source topology.
    main_lines = main_tex.read_text(encoding="utf-8").splitlines()
    assert main_lines[1267] == r"\section{Binomial distribution}"
    assert main_lines[1268] == r"\label{binomialModel}"
    assert main_lines[1926] == r"\section{Negative binomial distribution}"
    assert main_lines[1927] == r"\label{negativeBinomial}"

    eoce_text = eoce_tex.read_text(encoding="utf-8")
    eoce_numbers = [int(value) for value in re.findall(r"(?m)^% (\d+)\s*$", eoce_text)]
    assert eoce_numbers == list(range(17, 27)), eoce_numbers
    assert len(re.findall(r"\\eoce\{", eoce_text)) == 10
    assert len(re.findall(r"\\item\b", eoce_text)) == 40

    witness_specs = [
        (
            SOURCE_OUT / "R011-B016_MAIN_AUTHORITY_LINES_1268-1926.tex",
            main_tex,
            1268,
            1926,
        ),
        (
            SOURCE_OUT / "R011-B016_EOCE_17-26_AUTHORITY.tex",
            eoce_tex,
            1,
            len(eoce_tex.read_bytes().splitlines()),
        ),
        (
            SOURCE_OUT
            / "R011-B016_PUBLIC_ODD_ANSWERS_AUTHORITY_LINES_707-748.tex",
            answers_tex,
            707,
            748,
        ),
        (
            SOURCE_OUT / "R011-B016_DATA_APPENDIX_AUTHORITY_LINES_277-294.tex",
            data_tex,
            277,
            294,
        ),
        (
            SOURCE_OUT / "R011-B016_PREBOUNDARY_MACROS_AUTHORITY_LINES_979-982.tex",
            main_tex,
            979,
            982,
        ),
        (
            SOURCE_OUT / "R011-B016_BIB_WEBPAGE_ALCOHOL_LINES_386-388.bib",
            bib,
            386,
            388,
        ),
        (
            SOURCE_OUT / "R011-B016_BIB_WEBPAGE_SPIDERS_LINES_425-427.bib",
            bib,
            425,
            427,
        ),
        (
            SOURCE_OUT
            / "R011-B016_BIB_BOSTON_CHICKENPOX_LINES_833-835.bib",
            bib,
            833,
            835,
        ),
    ]
    for output, source, start, end in witness_specs:
        write_bytes(output, exact_line_slice(source, start, end))

    main_slice_text = witness_specs[0][0].read_text(encoding="utf-8")
    main_labels = regex_values(main_slice_text, r"\\label\{([^}]+)\}")
    main_refs = sorted(
        set(regex_values(main_slice_text, r"\\(?:ref|pageref)\{([^}]+)\}"))
    )
    figure_keys = regex_values(
        main_slice_text,
        r"\\Figure(?:\[[^\]]*\])?\{[^}]+\}\{([^}]+)\}",
    )
    assert figure_keys == [
        "fourBinomialModelsShowingApproxToNormal",
        "normApproxToBinomFail",
    ]
    assert regex_values(main_slice_text, r"\\input\{([^}]+)\}") == [
        "ch_distributions/TeX/binomial_distribution.tex"
    ]

    eoce_labels = regex_values(eoce_text, r"\\label\{([^}]+)\}")
    eoce_refs = sorted(set(regex_values(eoce_text, r"\\ref\{([^}]+)\}")))
    eoce_citations = regex_values(eoce_text, r"\\footfullcite\{([^}]+)\}")
    assert eoce_citations == [
        "webpage:alcohol",
        "bostonchildrenshospital:chickenpox",
        "webpage:spiders",
    ]

    o001_contract_path = SOURCE_OUT / "R011-B016_O001_GAP_CONTRACT.json"
    o001_contract = {
        "$schema": "interlanguage.r011-b016-o001-gap-contract/v1",
        "authority": {"commit": COMMIT, "tree": TREE},
        "boundary_id": "R011-B016",
        "public_answer_exercise_ids": [17, 19, 21, 23, 25],
        "o001_mastery_companion_gap_exercise_ids": [18, 20, 22, 24, 26],
        "restricted_instructor_solutions_sought_or_ingested": False,
        "rule": (
            "Write independent, source-faithful Indonesian mastery-companion "
            "solutions for even exercises only; preserve links to exercises 18, "
            "20, 22, 24, and 26; do not infer or seek restricted instructor files."
        ),
        "status": "FROZEN_GAP_CONTRACT_NO_SOLUTIONS_CREATED_IN_SOURCE_CLOSURE",
    }
    write_json(o001_contract_path, o001_contract)

    source_rows: list[dict[str, object]] = []
    source_rows.extend(
        [
            source_manifest_row(
                "authority",
                "authority metadata",
                REPO / "authority/UPSTREAM_AUTHORITY.json",
                "retain",
                "metadata",
                "Pinned repository, branch, commit, archive, and calculated tree evidence.",
            ),
            source_manifest_row(
                "authority",
                "book source and rights license",
                AUTHORITY / "LICENSE.md",
                "retain and apply",
                "CC BY-SA 3.0 Unported",
                "Includes derivative title, attribution, branding, and third-party figure obligations.",
            ),
            source_manifest_row(
                "authority",
                "build root",
                AUTHORITY / "main.tex",
                "retain as global build dependency",
                "CC BY-SA 3.0 Unported",
                "Resolves chapter and appendix inclusion order.",
            ),
            source_manifest_row(
                "authority",
                "main section source",
                main_tex,
                "retain; translate only the frozen 1268-1926 witness in B016",
                "CC BY-SA 3.0 Unported",
                "Full source contains prerequisite macros at 979-982 and next cursor at 1927.",
                1268,
                1926,
            ),
            source_manifest_row(
                "authority",
                "end-of-chapter exercises 17-26",
                eoce_tex,
                "retain and translate all ten exercises",
                "CC BY-SA 3.0 Unported; embedded dreidel photo separately CC BY 2.0",
                "Ten exercises, forty parts, one embedded photo, three bibliography citations.",
                1,
                211,
            ),
            source_manifest_row(
                "authority",
                "public odd exercise answers",
                answers_tex,
                "retain; translate only 17, 19, 21, 23, and 25",
                "CC BY-SA 3.0 Unported",
                "The bounded public-answer witness is authority lines 707-748.",
                707,
                748,
            ),
            source_manifest_row(
                "authority",
                "data appendix",
                data_tex,
                "retain; translate exactly three binomialModel entries",
                "CC BY-SA 3.0 Unported",
                "Entries are authority lines 277-280, 281-286, and 287-294.",
                277,
                294,
            ),
            source_manifest_row(
                "authority",
                "exercise bibliography",
                bib,
                "retain cited entries and redirect IDs",
                "CC BY-SA 3.0 Unported compilation metadata",
                "Relevant entries: webpage:alcohol, webpage:spiders, bostonchildrenshospital:chickenpox.",
            ),
            source_manifest_row(
                "authority",
                "figure and redirect macro resolver",
                AUTHORITY / "extraTeX/style/style.tex",
                "retain as global build dependency",
                "CC BY-SA 3.0 Unported",
                "Relevant resolver lines: oiRedirect 205; Figure/Figures 239-242.",
            ),
            source_manifest_row(
                "authority",
                "external cross-reference source: variability",
                AUTHORITY / "ch_summarizing_data/TeX/ch_summarizing_data.tex",
                "retain; do not translate in B016",
                "CC BY-SA 3.0 Unported",
                r"Defines \label{variability} at authority line 651.",
                651,
                651,
            ),
            source_manifest_row(
                "authority",
                "predecessor cross-reference source: eye_color_geometric",
                AUTHORITY / "ch_distributions/TeX/geometric_distribution.tex",
                "retain; already belongs to B015",
                "CC BY-SA 3.0 Unported",
                r"Defines \label{eye_color_geometric} at authority line 33.",
                33,
                33,
            ),
            source_manifest_row(
                "control",
                "component-rights control",
                REPO / "00_control/COMPONENT_RIGHTS.csv",
                "read-only; do not mutate in source closure",
                "mixed component rights",
                "Relevant existing rows: R011-RIGHTS-TEXT, -DERIVATIVE, -BRAND, and -RPKG.",
            ),
        ]
    )
    for output, source, start, end in witness_specs:
        source_rows.append(
            source_manifest_row(
                "frozen witness",
                "byte-exact bounded authority witness",
                output,
                "retain for B016 translation and reproducibility",
                "same license as source component",
                f"Byte-exact authority lines {start}-{end} from {rel(source)}.",
                start,
                end,
            )
        )
    source_rows.append(
        source_manifest_row(
            "contract",
            "O001 even-exercise gap contract",
            o001_contract_path,
            "retain; populate independently during translation",
            "new companion work to be released compatibly with the edition",
            "No restricted solution content is present.",
        )
    )

    source_manifest_path = SOURCE_OUT / "R011-B016_SOURCE_MANIFEST.csv"
    write_csv(
        source_manifest_path,
        [
            "scope",
            "role",
            "disposition",
            "path",
            "bytes",
            "sha256",
            "line_start_inclusive",
            "line_end_inclusive",
            "license",
            "notes",
        ],
        source_rows,
    )

    figure_specs = [
        (
            "fourBinomialModelsShowingApproxToNormal",
            "four binomial hollow-histogram figure",
            "ch_distributions/figures/fourBinomialModelsShowingApproxToNormal/"
            "fourBinomialModelsShowingApproxToNormal.pdf",
            "application/pdf",
            "CC BY-SA 3.0 Unported",
            "include unchanged: visible content is numeric and mathematical only",
            "n = 10; n = 30; n = 100; n = 300; numeric tick labels",
            "Generated by adjacent R producer; translated caption and alt text remain in TeX.",
        ),
        (
            "fourBinomialModelsShowingApproxToNormal",
            "adjacent R producer",
            "ch_distributions/figures/fourBinomialModelsShowingApproxToNormal/"
            "fourBinomialModelsShowingApproxToNormal.R",
            "text/x-r-source",
            "CC BY-SA 3.0 Unported; openintro package dependency separately GPL-3",
            "retain byte-exact; no localization required",
            "",
            "Uses base dbinom/plot/axis/abline plus openintro COL and myPDF; no external data read.",
        ),
        (
            "normApproxToBinomFail",
            "normal-approximation continuity-correction figure",
            "ch_distributions/figures/normApproxToBinomFail/normApproxToBinomFail.pdf",
            "application/pdf",
            "CC BY-SA 3.0 Unported",
            "include unchanged: visible content is numeric and graphical only",
            "numeric tick labels 40, 50, 60, 70, 80",
            "Generated by adjacent R producer; translated caption and alt text remain in TeX.",
        ),
        (
            "normApproxToBinomFail",
            "adjacent R producer",
            "ch_distributions/figures/normApproxToBinomFail/normApproxToBinomFail.R",
            "text/x-r-source",
            "CC BY-SA 3.0 Unported; openintro package dependency separately GPL-3",
            "retain byte-exact; no localization required",
            "",
            "Uses base dnorm/dbinom/plot/polygon/axis/abline plus openintro COL and myPDF; no external data read.",
        ),
        (
            "dreidel",
            "end-of-chapter exercise photograph",
            "ch_distributions/figures/eoce/dreidel/dreidel.jpg",
            "image/jpeg",
            "CC BY 2.0",
            "include unchanged with visible attribution and license link",
            "Hebrew letters on the photographed objects; no English prose in pixels",
            "Photo by Staccabees, cropped; source flic.kr/p/7gLZTf; source TeX identifies CC BY 2.0.",
        ),
    ]
    asset_rows: list[dict[str, object]] = []
    for (
        asset_id,
        role,
        source_rel,
        media_type,
        license_name,
        disposition,
        visible_text,
        notes,
    ) in figure_specs:
        authority_path = AUTHORITY / source_rel
        live_path = REPO / "repo" / source_rel
        authority_identity = identity(authority_path)
        live_identity = identity(live_path)
        assert authority_identity["bytes"] == live_identity["bytes"]
        assert authority_identity["sha256"] == live_identity["sha256"]
        asset_rows.append(
            asset_manifest_row(
                asset_id,
                role,
                "authority",
                authority_path,
                media_type,
                license_name,
                disposition,
                visible_text,
                notes,
            )
        )
        asset_rows.append(
            asset_manifest_row(
                asset_id,
                role,
                "live-byte-identical",
                live_path,
                media_type,
                license_name,
                disposition,
                visible_text,
                "Live identity proved equal to authority. " + notes,
            )
        )

    package_dir = (
        REPO
        / "authority/external/r-packages/"
        "openintro-48793d9645e0da033daaca1c1a19a051533d79d2"
    )
    package_archive = (
        package_dir
        / "openintro-48793d9645e0da033daaca1c1a19a051533d79d2.tar.gz"
    )
    package_manifest = package_dir / "AUTHORITY_MANIFEST.json"
    asset_rows.extend(
        [
            asset_manifest_row(
                "openintro-r-package",
                "frozen build dependency archive",
                "external authority",
                package_archive,
                "application/gzip",
                "GPL-3",
                "retain as build authority; do not bundle as book content",
                "",
                "Supplies COL palette data and myPDF helper used by both R producers.",
            ),
            asset_manifest_row(
                "openintro-r-package",
                "frozen build dependency manifest",
                "external authority",
                package_manifest,
                "application/json",
                "metadata",
                "retain",
                "",
                "Pins package commit, archive identity, license, and internal COL member.",
            ),
        ]
    )

    asset_manifest_path = ASSET_OUT / "R011-B016_ASSET_MANIFEST.csv"
    write_csv(
        asset_manifest_path,
        [
            "asset_id",
            "role",
            "path_kind",
            "path",
            "bytes",
            "sha256",
            "media_type",
            "license",
            "disposition",
            "reader_visible_text",
            "dependency_notes",
        ],
        asset_rows,
    )

    four_pdf = (
        AUTHORITY
        / "ch_distributions/figures/fourBinomialModelsShowingApproxToNormal/"
        "fourBinomialModelsShowingApproxToNormal.pdf"
    )
    norm_pdf = (
        AUTHORITY
        / "ch_distributions/figures/normApproxToBinomFail/normApproxToBinomFail.pdf"
    )
    dreidel_jpg = AUTHORITY / "ch_distributions/figures/eoce/dreidel/dreidel.jpg"
    with Image.open(dreidel_jpg) as image:
        dreidel_facts = {
            "width_pixels": image.width,
            "height_pixels": image.height,
            "mode": image.mode,
            "format": image.format,
        }
    assert dreidel_facts == {
        "width_pixels": 1203,
        "height_pixels": 789,
        "mode": "RGB",
        "format": "JPEG",
    }

    package_wrapper = "openintro-48793d9645e0da033daaca1c1a19a051533d79d2"
    package_internal = {
        "COL": tar_member_identity(package_archive, f"{package_wrapper}/data/COL.rda"),
        "myPDF": tar_member_identity(package_archive, f"{package_wrapper}/R/myPDF.R"),
    }
    assert package_internal["COL"]["sha256"] == (
        "51d60038e025a577959b6e89eec03ee92d04ea58038d2084bf19814df80f3be3"
    )

    asset_receipt_path = ASSET_OUT / "R011-B016_ASSET_RIGHTS_CLOSURE.json"
    asset_receipt = {
        "$schema": "interlanguage.r011-b016-asset-rights-closure/v1",
        "authority": {"commit": COMMIT, "tree": TREE},
        "boundary_id": "R011-B016",
        "production_model": MODEL,
        "network_used": False,
        "asset_manifest": identity(asset_manifest_path),
        "closure_counts": {
            "direct_reader_assets": 3,
            "adjacent_r_producers": 2,
            "authority_live_pairs_verified": 5,
            "external_package_archives": 1,
            "external_dataset_reads_by_r_producers": 0,
        },
        "direct_pdf_inspection": {
            "fourBinomialModelsShowingApproxToNormal": {
                **identity(four_pdf),
                **pdf_facts(four_pdf),
                "visual_review": (
                    "PASS: four distinct hollow histograms are complete, sharp, "
                    "centered, and unclipped; all visible labels are numeric or n = value."
                ),
                "localization_decision": (
                    "Reuse byte-exact. No English lexical content appears in the PDF; "
                    "translate the TeX alt text and caption only."
                ),
            },
            "normApproxToBinomFail": {
                **identity(norm_pdf),
                **pdf_facts(norm_pdf),
                "visual_review": (
                    "PASS: normal curve, shaded interval, red outline, axes, and tick "
                    "labels are complete, sharp, centered, and unclipped."
                ),
                "localization_decision": (
                    "Reuse byte-exact. No English lexical content appears in the PDF; "
                    "translate the TeX alt text and caption only."
                ),
            },
        },
        "r_generator_semantics": {
            "fourBinomialModelsShowingApproxToNormal": {
                "numeric_inputs": {"k": "-50:500", "p": 0.1, "n": [10, 30, 100, 300]},
                "output_geometry_inches": {"width": 5.5, "height": 4.1},
                "base_r_functions": ["dbinom", "plot", "axis", "abline"],
                "openintro_roles": ["COL palette", "myPDF helper"],
                "external_or_local_dataset_reads": 0,
            },
            "normApproxToBinomFail": {
                "numeric_inputs": {
                    "k": "0:400",
                    "p": 0.15,
                    "n": 400,
                    "x1": 49,
                    "x2": 51,
                },
                "derived_values": {"mean": 60, "sd_formula": "sqrt(n*p*(1-p))"},
                "output_geometry_inches": {"width": 7.5, "height": 2.6},
                "base_r_functions": [
                    "dnorm",
                    "dbinom",
                    "plot",
                    "polygon",
                    "axis",
                    "abline",
                ],
                "openintro_roles": ["COL palette", "myPDF helper"],
                "external_or_local_dataset_reads": 0,
            },
        },
        "openintro_package_dependency": {
            "commit": "48793d9645e0da033daaca1c1a19a051533d79d2",
            "license": "GPL-3",
            "archive": identity(package_archive),
            "authority_manifest": identity(package_manifest),
            "internal_members": package_internal,
            "redistribution_in_b016_reader": False,
        },
        "dreidel_photo": {
            **identity(dreidel_jpg),
            **dreidel_facts,
            "creator": "Staccabees",
            "source_display": "http://flic.kr/p/7gLZTf",
            "source_redirect_id": "textbook-flickr_staccabees_dreidels",
            "license": "CC BY 2.0",
            "license_redirect_id": "textbook-CC_BY_2",
            "transformation_disclosed_by_source": "cropped",
            "disposition": (
                "Include unchanged and retain visible creator, source, crop notice, "
                "and CC BY 2.0 license link; do not relabel the photo as CC BY-SA."
            ),
            "visual_review": (
                "PASS: two wooden dreidels are sharp and fully framed; no English prose "
                "is embedded in the image."
            ),
        },
        "rights_decisions": {
            "book_text_and_repository_generated_figures": "CC BY-SA 3.0 Unported",
            "indonesian_derivative": "CC BY-SA 3.0 Unported with attribution and change notice",
            "dreidel_photo": "separately governed CC BY 2.0 component",
            "openintro_r_package": "separately governed GPL-3 build dependency; not reader payload",
            "branding": (
                "Do not use OpenIntro name, logo, or marks as derivative branding; "
                "retain nominative source attribution only."
            ),
            "external_fact_sources": (
                "SAMHSA, Boston Children's Hospital, Gallup, and CDC are citation-only "
                "sources. Preserve citations/redirect IDs; no external source bytes are bundled."
            ),
        },
        "exclusions": [
            "No restricted instructor solutions were sought, read, or copied.",
            "No external website, article, or report bytes are bundled.",
            "No OpenIntro logo or other derivative-branding asset is in this boundary.",
            "No localized replacement is required for either direct PDF because both are locale-neutral.",
        ],
        "status": "PASS_EXACT_ASSET_IDENTITY_RIGHTS_AND_REUSE_DECISIONS_CLOSED",
    }
    write_json(asset_receipt_path, asset_receipt)

    source_receipt_path = SOURCE_OUT / "R011-B016_SOURCE_CLOSURE.json"
    source_receipt = {
        "$schema": "interlanguage.r011-b016-source-closure/v1",
        "authority": {
            "repository": "https://github.com/OpenIntroStat/openintro-statistics",
            "branch_observed": "master",
            "commit": COMMIT,
            "tree": TREE,
            "authority_metadata": identity(REPO / "authority/UPSTREAM_AUTHORITY.json"),
        },
        "boundary_id": "R011-B016",
        "production_model": MODEL,
        "network_used": False,
        "mutation_scope": (
            "Only qa/b016-source and qa/b016-assets were created; repo, backend, "
            "00_control, output, and release were not mutated."
        ),
        "main_boundary": {
            "source": identity(main_tex),
            "start": {"line": 1268, "command": r"\section{Binomial distribution}", "label": "binomialModel"},
            "end": {"line": 1926, "content": "%_________________"},
            "frozen_witness": identity(witness_specs[0][0]),
            "next_cursor": {
                "line": 1927,
                "command": r"\section{Negative binomial distribution}",
                "label_line": 1928,
                "label": "negativeBinomial",
            },
            "preboundary_macro_dependency": {
                "source_lines": [979, 980, 981, 982],
                "macros": {
                    "insureSprob": "0.7",
                    "insureSperc": "70%",
                    "insureFprob": "0.3",
                    "insureFperc": "30%",
                },
                "frozen_witness": identity(witness_specs[4][0]),
            },
        },
        "source_topology": {
            "main": {
                "sections": 1,
                "subsections": 3,
                "subsection_titles": [
                    "The binomial distribution",
                    "Normal approximation to the binomial distribution",
                    "The normal approximation breaks down on small intervals",
                ],
                "examples": len(re.findall(r"\\begin\{nexample\}", main_slice_text)),
                "guided_exercises": len(re.findall(r"\\begin\{nexercise\}", main_slice_text)),
                "inline_footnote_answers": len(re.findall(r"\\footnotetext\{", main_slice_text)),
                "oneboxes": len(re.findall(r"\\begin\{onebox\}", main_slice_text)),
                "figures": len(re.findall(r"\\begin\{figure\}", main_slice_text)),
                "newcommands": len(re.findall(r"\\newcommand\{", main_slice_text)),
                "labels": main_labels,
                "references": main_refs,
                "figure_keys": figure_keys,
            },
            "end_of_chapter_exercises": {
                "source": identity(eoce_tex),
                "exercise_ids": list(range(17, 27)),
                "exercise_count": 10,
                "part_count": 40,
                "labels": eoce_labels,
                "references": eoce_refs,
                "citation_keys": eoce_citations,
                "embedded_assets": ["eoce/dreidel/dreidel.jpg"],
                "frozen_witness": identity(witness_specs[1][0]),
            },
            "public_answers": {
                "exercise_ids": [17, 19, 21, 23, 25],
                "source_lines": [707, 748],
                "frozen_witness": identity(witness_specs[2][0]),
            },
            "o001_gaps": {
                "exercise_ids": [18, 20, 22, 24, 26],
                "contract": identity(o001_contract_path),
                "restricted_solutions_ingested": False,
            },
            "data_appendix": {
                "source_lines": [277, 294],
                "entry_count": 3,
                "entries": [
                    {
                        "lines": [277, 280],
                        "title": "Exceeding insurance deductible",
                        "provenance": "made-up but plausible low-deductible-plan statistics",
                    },
                    {
                        "lines": [281, 286],
                        "title": "Smoking friends",
                        "provenance": "30% statistic unverified; source explicitly warns not to treat it as fact",
                    },
                    {
                        "lines": [287, 294],
                        "title": "US smoking rate",
                        "provenance": "CDC 2017 estimate reported as 14%; source uses nearby 15% value",
                        "redirect_id": "cdc_gov-tobacco-data_statistics",
                    },
                ],
                "frozen_witness": identity(witness_specs[3][0]),
            },
        },
        "dependency_closure": {
            "external_label_dependencies": [
                {
                    "label": "variability",
                    "path": f"{AUTHORITY_PREFIX}/ch_summarizing_data/TeX/ch_summarizing_data.tex",
                    "line": 651,
                },
                {
                    "label": "eye_color_geometric",
                    "path": f"{AUTHORITY_PREFIX}/ch_distributions/TeX/geometric_distribution.tex",
                    "line": 33,
                },
            ],
            "bibliography_entries": [
                {
                    "key": "webpage:alcohol",
                    "source_lines": [386, 388],
                    "redirect_id": "textbook-SAMHSA_2007_8",
                    "witness": identity(witness_specs[5][0]),
                },
                {
                    "key": "webpage:spiders",
                    "source_lines": [425, 427],
                    "redirect_id": "textbook-frightens_youth_2005",
                    "witness": identity(witness_specs[6][0]),
                },
                {
                    "key": "bostonchildrenshospital:chickenpox",
                    "source_lines": [833, 835],
                    "redirect_id": "textbook-bostonchildrenshospital_chickenpox_vaccine",
                    "witness": identity(witness_specs[7][0]),
                },
            ],
            "redirect_only_ids_in_bounded_material": [
                "textbook-SAMHSA_2007_8",
                "textbook-bostonchildrenshospital_chickenpox_vaccine",
                "textbook-flickr_staccabees_dreidels",
                "textbook-CC_BY_2",
                "textbook-frightens_youth_2005",
                "cdc_gov-tobacco-data_statistics",
            ],
            "asset_closure_receipt": rel(asset_receipt_path),
            "asset_manifest": identity(asset_manifest_path),
        },
        "high_confidence_source_corrections_for_translation": [
            {
                "path": f"{AUTHORITY_PREFIX}/ch_distributions/TeX/binomial_distribution.tex",
                "line": 7,
                "source": "SAMSHA",
                "correction": "SAMHSA",
                "reason": "The agency's standard acronym is SAMHSA.",
            },
            {
                "path": f"{AUTHORITY_PREFIX}/ch_distributions/TeX/ch_distributions.tex",
                "line": 1531,
                "source": "As the last stage use software",
                "correction": "As the last stage, use software",
                "reason": "The introductory phrase requires a following comma.",
            },
            {
                "path": f"{AUTHORITY_PREFIX}/ch_distributions/TeX/ch_distributions.tex",
                "line": 1777,
                "source": "in last hollow histogram",
                "correction": "in the last hollow histogram",
                "reason": "Missing definite article.",
            },
            {
                "path": f"{AUTHORITY_PREFIX}/ch_distributions/TeX/binomial_distribution.tex",
                "line": 168,
                "source": "will the be the 3rd child",
                "correction": "will be the 3rd child",
                "reason": "Transposed extra article is a clear typographical error.",
            },
        ],
        "rights_and_exclusions": {
            "book_and_generated_figures": "CC BY-SA 3.0 Unported",
            "dreidel_photo": "CC BY 2.0, separately attributed",
            "openintro_r_package": "GPL-3 build dependency, not bundled in reader",
            "restricted_instructor_solutions": "not sought or ingested",
            "external_source_bytes": "not downloaded or bundled",
            "brand_assets": "excluded from derivative branding",
        },
        "source_manifest": identity(source_manifest_path),
        "status": "PASS_EXACT_SOURCE_RIGHTS_ASSET_AND_NEXT_CURSOR_CLOSURE",
    }
    write_json(source_receipt_path, source_receipt)

    validation_path = SOURCE_OUT / "R011-B016_CLOSURE_VALIDATION.json"
    validation_receipt = {
        "$schema": "interlanguage.r011-b016-closure-validation/v1",
        "authority": {"commit": COMMIT, "tree": TREE},
        "boundary_id": "R011-B016",
        "validated_outputs": {
            "source_manifest": identity(source_manifest_path),
            "source_receipt": identity(source_receipt_path),
            "asset_manifest": identity(asset_manifest_path),
            "asset_receipt": identity(asset_receipt_path),
            "o001_gap_contract": identity(o001_contract_path),
            "byte_exact_witnesses": [identity(spec[0]) for spec in witness_specs],
        },
        "checks": {
            "byte_exact_authority_witnesses": 8,
            "source_manifest_rows": len(source_rows),
            "asset_manifest_rows": len(asset_rows),
            "authority_live_asset_pairs": 5,
            "authority_live_pairs_byte_identical": True,
            "main_cursor_asserted": "1268 binomialModel through 1926 inclusive",
            "next_cursor_asserted": "1927 negativeBinomial; label at 1928",
            "eoce_ids_asserted": list(range(17, 27)),
            "public_answer_ids_asserted": [17, 19, 21, 23, 25],
            "o001_gap_ids_asserted": [18, 20, 22, 24, 26],
            "restricted_solution_ingestion": False,
            "network_used": False,
        },
        "status": "PASS_INDEPENDENTLY_REPLAYABLE_EXACT_CLOSURE",
    }
    write_json(validation_path, validation_receipt)

    # A non-circular inventory binds every generated closure output except itself.
    checksum_path = SOURCE_OUT / "R011-B016_CLOSURE_OUTPUT_CHECKSUMS.sha256"
    output_paths = sorted(
        [
            *[spec[0] for spec in witness_specs],
            o001_contract_path,
            source_manifest_path,
            source_receipt_path,
            asset_manifest_path,
            asset_receipt_path,
            validation_path,
            Path(__file__).resolve(),
        ],
        key=lambda path: rel(path),
    )
    checksum_lines = [
        f"{identity(path)['sha256']}  {rel(path)}" for path in output_paths
    ]
    write_bytes(checksum_path, ("\n".join(checksum_lines) + "\n").encode("utf-8"))

    result = {
        "status": "PASS",
        "boundary": "R011-B016",
        "source_manifest": identity(source_manifest_path),
        "source_receipt": identity(source_receipt_path),
        "asset_manifest": identity(asset_manifest_path),
        "asset_receipt": identity(asset_receipt_path),
        "validation": identity(validation_path),
        "checksums": identity(checksum_path),
        "next_cursor": {"line": 1927, "label": "negativeBinomial"},
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
