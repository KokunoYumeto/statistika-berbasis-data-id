"""Deterministically localize the upstream vector figure without changing geometry."""

from __future__ import annotations

import hashlib
import io
from pathlib import Path

import pikepdf
from pikepdf import ContentStreamInstruction, Name, Operator, parse_content_stream, unparse_content_stream
from reportlab.lib.colors import black
from reportlab.pdfgen import canvas

PIN = "fee25091fb24e89c36296fd67c48c1fcf7a93b6e"
SOURCE_SHA256 = "cb43d8a0974a9b912e15a18bea6302a7adaa483d6a6ee690773b232e0cc05e23"
RELATIVE_SOURCE = Path("ch_intro_to_data/figures/expResp/expResp.pdf")
OUTPUT = Path(__file__).resolve().with_name("expResp.pdf")


def lane_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "authority" / "upstream" / f"openintro-statistics-{PIN}").is_dir():
            return parent
    raise RuntimeError("Pinned authority tree not found")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def strip_all_text(pdf: pikepdf.Pdf) -> None:
    page = pdf.pages[0]
    kept = []
    in_text = False
    block = []
    for instruction in parse_content_stream(page):
        operator = str(instruction.operator)
        if operator == "BT":
            in_text = True
            block = [instruction]
        elif in_text:
            block.append(instruction)
            if operator == "ET":
                in_text = False
                block = []
        else:
            kept.append(instruction)
    page.obj["/Contents"] = pdf.make_stream(unparse_content_stream(kept))


def make_overlay(width: float, height: float) -> io.BytesIO:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(width, height), invariant=1, pageCompression=1)
    c.setFillColor(black)
    c.setFont("Helvetica", 11.5)
    c.drawCentredString(48.4, 18.73, "variabel")
    c.drawCentredString(48.4, 4.33, "penjelas")
    c.drawCentredString(226.66, 18.73, "variabel")
    c.drawCentredString(226.66, 4.33, "respons")
    c.setFont("Helvetica", 7.0)
    c.drawCentredString(137.52, 17.17, "mungkin memengaruhi")
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer


def add_deterministic_overlay(pdf: pikepdf.Pdf, page: pikepdf.Page, overlay: pikepdf.Page) -> None:
    generated_name = page.add_overlay(overlay, shrink=False, expand=False)
    fixed_name = Name("/IDOverlay")
    xobjects = page.obj["/Resources"]["/XObject"]
    if fixed_name in xobjects:
        raise RuntimeError("Deterministic overlay resource name already exists")
    xobjects[fixed_name] = xobjects[generated_name]
    del xobjects[generated_name]
    rewritten = []
    for instruction in parse_content_stream(page):
        if str(instruction.operator) == "Do" and str(instruction.operands[0]) == str(generated_name):
            instruction = ContentStreamInstruction([fixed_name], Operator("Do"))
        rewritten.append(instruction)
    page.obj["/Contents"] = pdf.make_stream(unparse_content_stream(rewritten))


def main() -> None:
    source = lane_root() / "authority" / "upstream" / f"openintro-statistics-{PIN}" / RELATIVE_SOURCE
    actual = sha256(source)
    if actual != SOURCE_SHA256:
        raise RuntimeError(f"Authority hash mismatch: {actual}")
    with pikepdf.Pdf.open(source) as pdf:
        strip_all_text(pdf)
        page = pdf.pages[0]
        width = float(page.mediabox[2]) - float(page.mediabox[0])
        height = float(page.mediabox[3]) - float(page.mediabox[1])
        with pikepdf.Pdf.open(make_overlay(width, height)) as overlay:
            add_deterministic_overlay(pdf, page, overlay.pages[0])
        temporary = OUTPUT.with_name("expResp.tmp-id.pdf")
        pdf.save(temporary, deterministic_id=True, compress_streams=True)
    temporary.replace(OUTPUT)
    print(f"{OUTPUT}\t{sha256(OUTPUT)}")


if __name__ == "__main__":
    main()
