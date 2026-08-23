"""Deterministically relabel the pinned vector plot while preserving every data mark."""

from __future__ import annotations

import hashlib
import io
from pathlib import Path

import pikepdf
from pikepdf import ContentStreamInstruction, Name, Operator, parse_content_stream, unparse_content_stream
from reportlab.lib.colors import black
from reportlab.pdfgen import canvas

PIN = "fee25091fb24e89c36296fd67c48c1fcf7a93b6e"
SOURCE_SHA256 = "24999f870fba598bee227a637035eb4a62091c317011079c4b695838a33aefd9"
RELATIVE_SOURCE = Path("ch_intro_to_data/figures/pop_change_v_med_income/pop_change_v_med_income.pdf")
OUTPUT = Path(__file__).resolve().with_name("pop_change_v_med_income.pdf")
REMOVE = {"Median Household Income", "Population Change", "over 7 Years"}


def lane_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "authority" / "upstream" / f"openintro-statistics-{PIN}").is_dir():
            return parent
    raise RuntimeError("Pinned authority tree not found")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def visible_text(block) -> str:
    pieces = []
    for instruction in block:
        if str(instruction.operator) not in {"Tj", "TJ"}:
            continue
        for operand in instruction.operands:
            if isinstance(operand, pikepdf.Array):
                pieces.extend(str(item) for item in operand if isinstance(item, pikepdf.String))
            elif isinstance(operand, pikepdf.String):
                pieces.append(str(operand))
    return "".join(pieces)


def strip_selected_text(pdf: pikepdf.Pdf) -> None:
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
                if visible_text(block) not in REMOVE:
                    kept.extend(block)
                in_text = False
                block = []
        else:
            kept.append(instruction)
    page.obj["/Contents"] = pdf.make_stream(unparse_content_stream(kept))


def make_overlay(width: float, height: float) -> io.BytesIO:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(width, height), invariant=1, pageCompression=1)
    c.setFillColor(black)
    c.setFont("Helvetica", 10.5)
    c.saveState()
    c.translate(12.96, 144.0)
    c.rotate(90)
    c.drawCentredString(0, 0, "Perubahan Populasi")
    c.restoreState()
    c.saveState()
    c.translate(27.36, 144.0)
    c.rotate(90)
    c.drawCentredString(0, 0, "selama 7 Tahun")
    c.restoreState()
    c.drawCentredString(281.5, 4.32, "Pendapatan Median Rumah Tangga")
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
        strip_selected_text(pdf)
        page = pdf.pages[0]
        width = float(page.mediabox[2]) - float(page.mediabox[0])
        height = float(page.mediabox[3]) - float(page.mediabox[1])
        with pikepdf.Pdf.open(make_overlay(width, height)) as overlay:
            add_deterministic_overlay(pdf, page, overlay.pages[0])
        temporary = OUTPUT.with_name("pop_change_v_med_income.tmp-id.pdf")
        pdf.save(temporary, deterministic_id=True, compress_streams=True)
    temporary.replace(OUTPUT)
    print(f"{OUTPUT}\t{sha256(OUTPUT)}")


if __name__ == "__main__":
    main()
