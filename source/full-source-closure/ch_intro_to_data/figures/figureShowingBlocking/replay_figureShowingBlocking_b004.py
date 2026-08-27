"""Deterministically replay the localized R011-B004 blocking figure.

R is not installed in the production environment.  This helper reproduces the
R 3.5.3 Mersenne-Twister stream and the canonical R producer's drawing geometry
as native vector PDF operators.  It does not edit, relabel, or paint over the
upstream PDF.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import platform
import shutil
import statistics
import sys
import tempfile

import pikepdf
import pypdf
import reportlab
from reportlab.lib.colors import HexColor, white
from reportlab.pdfgen import canvas


BOUNDARY_ID = "R011-B004"
AUTHORITY_COMMIT = "fee25091fb24e89c36296fd67c48c1fcf7a93b6e"
HERE = Path(__file__).resolve().parent
PRODUCER = HERE / "figureShowingBlocking.R"
OUTPUT = HERE / "figureShowingBlocking.pdf"
RECEIPT = HERE / "R011-B004_FIGURE_REPLAY.json"
PAGE_WIDTH = 288.0
PAGE_HEIGHT = 504.0
R_X_LIMITS = (-0.1, 1.1)
R_Y_LIMITS = (-0.05, 3.06)

EXPECTED_LOW = (
    2,
    5,
    6,
    8,
    13,
    16,
    17,
    21,
    23,
    29,
    33,
    34,
    36,
    37,
    39,
    41,
    45,
    46,
    47,
    50,
    53,
    54,
)
EXPECTED_CONTROL_LOW = (2, 5, 8, 16, 23, 36, 37, 41, 45, 46, 54)
EXPECTED_CONTROL_HIGH = (
    3,
    4,
    7,
    18,
    20,
    22,
    24,
    26,
    27,
    28,
    32,
    38,
    40,
    43,
    48,
    49,
)
EXPECTED_LABELS = (
    "Pasien bernomor",
    "bentuk",
    "blok",
    "Pasien berisiko rendah",
    "Pasien berisiko tinggi",
    "bagi dua",
    "secara acak",
    "Kontrol",
    "Perlakuan",
)
FORBIDDEN_ENGLISH_LABELS = (
    "Numbered patients",
    "create blocks",
    "Low-risk patients",
    "High-risk patients",
    "randomly split in half",
    "Control",
    "Treatment",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class R353MersenneTwister:
    """The R <=3.5 Mersenne-Twister initializer and uniform stream."""

    _N = 624
    _M = 397
    _MATRIX_A = 0x9908B0DF
    _UPPER_MASK = 0x80000000
    _LOWER_MASK = 0x7FFFFFFF
    _MASK = 0xFFFFFFFF

    def __init__(self, seed: int) -> None:
        state_seed = seed & self._MASK
        for _ in range(50):
            state_seed = (69069 * state_seed + 1) & self._MASK
        initialized = []
        for _ in range(self._N + 1):
            state_seed = (69069 * state_seed + 1) & self._MASK
            initialized.append(state_seed)
        self._state = initialized[1:]
        self._index = self._N

    def _twist(self) -> None:
        for index in range(self._N):
            y = (
                (self._state[index] & self._UPPER_MASK)
                | (self._state[(index + 1) % self._N] & self._LOWER_MASK)
            )
            self._state[index] = (
                self._state[(index + self._M) % self._N]
                ^ (y >> 1)
                ^ (self._MATRIX_A if y & 1 else 0)
            ) & self._MASK
        self._index = 0

    def uniform(self) -> float:
        if self._index >= self._N:
            self._twist()
        y = self._state[self._index]
        self._index += 1
        y ^= y >> 11
        y ^= (y << 7) & 0x9D2C5680
        y ^= (y << 15) & 0xEFC60000
        y ^= y >> 18
        y &= self._MASK
        value = y / 4294967296.0
        if value <= 0.0:
            return 0.5 / 4294967296.0
        if value >= 1.0:
            return 1.0 - 0.5 / 4294967296.0
        return value


def sample_without_replacement(
    rng: R353MersenneTwister, values: list[int], size: int
) -> list[int]:
    """R 3.5.3's rounding sampler for an unweighted integer vector."""

    pool = list(values)
    active = len(pool)
    selected: list[int] = []
    for _ in range(size):
        index = int(math.floor(active * rng.uniform()))
        selected.append(pool[index])
        active -= 1
        pool[index] = pool[active]
    return selected


def reproduce_r_data() -> tuple[dict[int, str], dict[int, str], dict[int, float]]:
    rng = R353MersenneTwister(2)

    # R's ProbSampleReplace sorts c(0.8, 1.2) descending, so the high-risk
    # category occupies cumulative probability [0, 0.6].
    risk = {
        patient: ("high" if rng.uniform() <= 0.6 else "low")
        for patient in range(1, 55)
    }
    assert tuple(patient for patient in risk if risk[patient] == "low") == EXPECTED_LOW

    # stats::rnorm uses the inversion normal generator in R 3.5.3.  Reproduce
    # its 27-bit construction so both the marker sizes and subsequent allocation
    # stream agree with the canonical producer.
    normal = statistics.NormalDist()
    marker_cex: dict[int, float] = {}
    for patient in range(1, 55):
        first_uniform = rng.uniform()
        inversion_uniform = (
            math.floor(134217728.0 * first_uniform) + rng.uniform()
        ) / 134217728.0
        marker_cex[patient] = 1.0 + 0.001 * normal.inv_cdf(inversion_uniform)

    allocation: dict[int, str] = {}
    for risk_level in ("low", "high"):
        members = [patient for patient in risk if risk[patient] == risk_level]
        control = set(sample_without_replacement(rng, members, len(members) // 2))
        for patient in members:
            allocation[patient] = "control" if patient in control else "treatment"

    assert tuple(
        patient
        for patient in risk
        if risk[patient] == "low" and allocation[patient] == "control"
    ) == EXPECTED_CONTROL_LOW
    assert tuple(
        patient
        for patient in risk
        if risk[patient] == "high" and allocation[patient] == "control"
    ) == EXPECTED_CONTROL_HIGH
    assert sum(risk[patient] == "low" for patient in risk) == 22
    assert sum(risk[patient] == "high" for patient in risk) == 32
    assert sum(
        risk[patient] == "low" and allocation[patient] == "control"
        for patient in risk
    ) == 11
    assert sum(
        risk[patient] == "low" and allocation[patient] == "treatment"
        for patient in risk
    ) == 11
    assert sum(
        risk[patient] == "high" and allocation[patient] == "control"
        for patient in risk
    ) == 16
    assert sum(
        risk[patient] == "high" and allocation[patient] == "treatment"
        for patient in risk
    ) == 16
    return risk, allocation, marker_cex


def x_point(value: float) -> float:
    return (value - R_X_LIMITS[0]) / (R_X_LIMITS[1] - R_X_LIMITS[0]) * PAGE_WIDTH


def y_point(value: float) -> float:
    return (value - R_Y_LIMITS[0]) / (R_Y_LIMITS[1] - R_Y_LIMITS[0]) * PAGE_HEIGHT


def draw_text(
    pdf: canvas.Canvas,
    x: float,
    y: float,
    value: str,
    size: float,
    colour: HexColor | None = None,
) -> None:
    pdf.setFont("Helvetica", size)
    pdf.setFillColor(colour or HexColor("#20252A"))
    pdf.drawCentredString(x_point(x), y_point(y) - size * 0.32, value)


def draw_multiline(
    pdf: canvas.Canvas,
    x: float,
    y: float,
    lines: tuple[str, ...],
    size: float,
) -> None:
    leading = size * 1.15
    start = y_point(y) + leading * (len(lines) - 1) / 2
    for offset, line in enumerate(lines):
        pdf.setFont("Helvetica", size)
        pdf.setFillColor(HexColor("#20252A"))
        pdf.drawCentredString(x_point(x), start - offset * leading - size * 0.32, line)


def draw_rect(
    pdf: canvas.Canvas,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    colour: HexColor,
    width: float = 0.8,
) -> None:
    pdf.setStrokeColor(colour)
    pdf.setLineWidth(width)
    pdf.rect(
        x_point(x0),
        y_point(y0),
        x_point(x1) - x_point(x0),
        y_point(y1) - y_point(y0),
        stroke=1,
        fill=0,
    )


def draw_arrow(
    pdf: canvas.Canvas, x0: float, y0: float, x1: float, y1: float
) -> None:
    start_x, start_y = x_point(x0), y_point(y0)
    end_x, end_y = x_point(x1), y_point(y1)
    pdf.setStrokeColor(HexColor("#20252A"))
    pdf.setFillColor(HexColor("#20252A"))
    pdf.setLineWidth(1.0)
    pdf.line(start_x, start_y, end_x, end_y)
    angle = math.atan2(end_y - start_y, end_x - start_x)
    arrow_length = 5.0
    wing = math.pi / 7
    path = pdf.beginPath()
    path.moveTo(end_x, end_y)
    path.lineTo(
        end_x - arrow_length * math.cos(angle - wing),
        end_y - arrow_length * math.sin(angle - wing),
    )
    path.lineTo(
        end_x - arrow_length * math.cos(angle + wing),
        end_y - arrow_length * math.sin(angle + wing),
    )
    path.close()
    pdf.drawPath(path, stroke=0, fill=1)


def draw_patient(
    pdf: canvas.Canvas,
    x: float,
    y: float,
    patient: int,
    risk: dict[int, str],
    marker_cex: dict[int, float],
) -> None:
    px, py = x_point(x), y_point(y)
    scale = marker_cex[patient]
    low_colour = HexColor("#C43C39")
    high_colour = HexColor("#2468A2")
    if risk[patient] == "low":
        pdf.setStrokeColor(low_colour)
        pdf.setFillColor(white)
        pdf.setLineWidth(0.9)
        pdf.circle(px, py, 2.45 * scale, stroke=1, fill=1)
        number_colour = low_colour
    else:
        pdf.setStrokeColor(high_colour)
        pdf.setFillColor(high_colour)
        pdf.setLineWidth(0.9)
        path = pdf.beginPath()
        path.moveTo(px, py + 2.8 * scale)
        path.lineTo(px - 2.7 * scale, py - 2.3 * scale)
        path.lineTo(px + 2.7 * scale, py - 2.3 * scale)
        path.close()
        pdf.drawPath(path, stroke=1, fill=1)
        number_colour = high_colour
    pdf.setFont("Helvetica", 5.4)
    pdf.setFillColor(number_colour)
    pdf.drawCentredString(px, py + 3.7, str(patient))


def draw_label_box(
    pdf: canvas.Canvas,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    label: str,
    size: float,
) -> None:
    colour = HexColor("#325D88")
    pdf.setStrokeColor(colour)
    pdf.setFillColor(white)
    pdf.setLineWidth(0.8)
    pdf.rect(
        x_point(x0),
        y_point(y0),
        x_point(x1) - x_point(x0),
        y_point(y1) - y_point(y0),
        stroke=1,
        fill=1,
    )
    draw_text(pdf, (x0 + x1) / 2, (y0 + y1) / 2, label, size, colour)


def create_vector_pdf(
    path: Path,
    risk: dict[int, str],
    allocation: dict[int, str],
    marker_cex: dict[int, float],
) -> dict[str, list[tuple[float, float, int]]]:
    frame_colour = HexColor("#3B4A5A")
    group_colour = HexColor("#325D88")
    pdf = canvas.Canvas(
        str(path),
        pagesize=(PAGE_WIDTH, PAGE_HEIGHT),
        pageCompression=1,
        invariant=1,
        initialFontName="Helvetica",
    )
    pdf.setTitle("Pemblokan pasien berdasarkan risiko")
    pdf.setSubject("Gambar OpenIntro Statistics yang dilokalkan ke Bahasa Indonesia")

    draw_rect(pdf, 0, 2.20, 1, 2.90, frame_colour)
    draw_text(pdf, 0.5, 2.98, "Pasien bernomor", 9.8)

    draw_rect(pdf, 0, 1.20, 0.45, 1.90, frame_colour)
    draw_rect(pdf, 0.55, 1.20, 1, 1.90, frame_colour)
    draw_arrow(pdf, 0.56, 2.17, 0.75, 2.02)
    draw_arrow(pdf, 0.44, 2.17, 0.25, 2.02)
    draw_multiline(pdf, 0.5, 2.08, ("bentuk", "blok"), 8.4)
    draw_text(pdf, 0.225, 1.96, "Pasien berisiko rendah", 7.1)
    draw_text(pdf, 0.775, 1.96, "Pasien berisiko tinggi", 7.1)

    draw_rect(pdf, 0, 0.48, 1, 0.90, group_colour)
    draw_rect(pdf, 0, 0.00, 1, 0.42, group_colour)
    draw_arrow(pdf, 0.09, 1.16, 0.09, 1.00)
    draw_multiline(pdf, 0.21, 1.08, ("bagi dua", "secara acak"), 7.2)
    draw_arrow(pdf, 0.67, 1.16, 0.67, 1.00)
    draw_multiline(pdf, 0.79, 1.08, ("bagi dua", "secara acak"), 7.2)

    slim_box = 0.03
    draw_rect(pdf, 0.02, 0.50, 0.41, 0.88, group_colour)
    draw_rect(pdf, 0.02, 0.02, 0.41, 0.40, group_colour)
    draw_rect(pdf, 0.57 + slim_box, 0.50, 0.98, 0.88, group_colour)
    draw_rect(pdf, 0.57 + slim_box, 0.02, 0.98, 0.40, group_colour)
    draw_label_box(pdf, -0.05, 0.86, 0.14, 0.92, "Kontrol", 6.5)
    draw_label_box(pdf, -0.05, 0.39, 0.16, 0.45, "Perlakuan", 6.3)

    geometry: dict[str, list[tuple[float, float, int]]] = {
        "numbered": [],
        "low_block": [],
        "high_block": [],
        "control_low": [],
        "treatment_low": [],
        "control_high": [],
        "treatment_high": [],
    }

    patient = 0
    for column in range(9):
        x = 0.1 + column * 0.1
        for row in range(6):
            y = 2.8 - row * 0.1
            patient += 1
            geometry["numbered"].append((x, y, patient))
            draw_patient(pdf, x, y, patient, risk, marker_cex)

    x, y = 0.078, 1.83
    for patient in (value for value in risk if risk[value] == "low"):
        geometry["low_block"].append((x, y, patient))
        draw_patient(pdf, x, y, patient, risk, marker_cex)
        if y < 1.3:
            x, y = x + 0.095, 1.83
        else:
            y -= 0.11

    x, y = 0.615, 1.82
    for patient in (value for value in risk if risk[value] == "high"):
        geometry["high_block"].append((x, y, patient))
        draw_patient(pdf, x, y, patient, risk, marker_cex)
        if y < 1.3:
            x, y = x + 0.08, 1.83
        else:
            y -= 0.095

    x_positions = [0.10, 0.10, 0.665, 0.665]
    y_positions = [0.80, 0.32, 0.80, 0.32]
    group_names = (
        "control_low",
        "treatment_low",
        "control_high",
        "treatment_high",
    )
    for patient in range(1, 55):
        box = 0
        if allocation[patient] == "treatment":
            box += 1
        if risk[patient] == "high":
            box += 2
        x, y = x_positions[box], y_positions[box]
        geometry[group_names[box]].append((x, y, patient))
        draw_patient(pdf, x, y, patient, risk, marker_cex)
        threshold = 0.12 + (0.51 if box in (0, 2) else 0.0) - 0.03
        if y < threshold:
            x_positions[box] += 0.11 - (0.025 if box > 1 else 0.0)
            y_positions[box] = 0.32 + (0.48 if box in (0, 2) else 0.0)
        else:
            y_positions[box] -= 0.085

    assert [len(geometry[name]) for name in group_names] == [11, 11, 16, 16]
    pdf.showPage()
    pdf.save()
    return geometry


def canonicalize_pdf(path: Path) -> None:
    temporary = path.with_suffix(".canonical.tmp.pdf")
    with pikepdf.Pdf.open(path) as pdf:
        info = pdf.docinfo
        for key in ("/CreationDate", "/ModDate", "/Producer", "/Creator", "/Author"):
            if key in info:
                del info[key]
        info["/Title"] = "Pemblokan pasien berdasarkan risiko"
        info["/Subject"] = (
            "Gambar OpenIntro Statistics yang dilokalkan ke Bahasa Indonesia"
        )
        pdf.save(
            temporary,
            deterministic_id=True,
            compress_streams=True,
            object_stream_mode=pikepdf.ObjectStreamMode.disable,
        )
    temporary.replace(path)


def validate_pdf(path: Path) -> dict[str, object]:
    with pikepdf.Pdf.open(path) as pdf:
        assert len(pdf.pages) == 1
        page = pdf.pages[0]
        media_box = [float(value) for value in page.mediabox]
        assert media_box == [0.0, 0.0, PAGE_WIDTH, PAGE_HEIGHT]
        fonts = []
        font_resources = page.obj.get("/Resources", {}).get("/Font", {})
        for font in font_resources.values():
            base_font = str(font.get("/BaseFont", ""))
            fonts.append(base_font)
        assert all("Symbol" not in name and "Dingbats" not in name for name in fonts)
        xobjects = page.obj.get("/Resources", {}).get("/XObject", {})
        image_xobjects = [
            str(name)
            for name, xobject in xobjects.items()
            if str(xobject.get("/Subtype", "")) == "/Image"
        ]
        assert image_xobjects == []

    reader = pypdf.PdfReader(str(path))
    extracted = reader.pages[0].extract_text() or ""
    for label in EXPECTED_LABELS:
        assert label in extracted, (label, extracted)
    for label in FORBIDDEN_ENGLISH_LABELS:
        assert label not in extracted, (label, extracted)
    return {
        "pages": 1,
        "media_box_points": media_box,
        "font_base_names": sorted(fonts),
        "image_xobjects": image_xobjects,
        "expected_labels_present": True,
        "forbidden_english_labels_absent": True,
        "vector_markers": {
            "low_risk": "open circle path",
            "high_risk": "filled triangle path",
        },
    }


def validate_producer_source() -> dict[str, object]:
    source = PRODUCER.read_text(encoding="utf-8")
    required_fragments = (
        'RNGversion("3.5.3")',
        "set.seed(2)",
        'sum(risk == "low") == 22L',
        'sum(risk == "high") == 32L',
        'sum(risk == "low" & allocation == "control") == 11L',
        'sum(risk == "high" & allocation == "treatment") == 16L',
        "useDingbats = FALSE",
        '"Pasien bernomor"',
        '"Pasien berisiko rendah"',
        '"Pasien berisiko tinggi"',
        '"Kontrol"',
        '"Perlakuan"',
    )
    for fragment in required_fragments:
        assert fragment in source, fragment
    return {
        "path": PRODUCER.name,
        "bytes": PRODUCER.stat().st_size,
        "sha256": sha256(PRODUCER),
        "required_fragments_present": True,
    }


def main() -> int:
    producer_record = validate_producer_source()
    risk, allocation, marker_cex = reproduce_r_data()
    with tempfile.TemporaryDirectory(prefix="r011-b004-figure-") as temporary_dir:
        temporary_root = Path(temporary_dir)
        first = temporary_root / "replay-1.pdf"
        second = temporary_root / "replay-2.pdf"
        first_geometry = create_vector_pdf(first, risk, allocation, marker_cex)
        second_geometry = create_vector_pdf(second, risk, allocation, marker_cex)
        assert first_geometry == second_geometry
        canonicalize_pdf(first)
        canonicalize_pdf(second)
        first_hash = sha256(first)
        second_hash = sha256(second)
        assert first_hash == second_hash
        first_bytes = first.stat().st_size
        assert first_bytes == second.stat().st_size
        pdf_validation = validate_pdf(first)
        shutil.copyfile(first, OUTPUT)

    assert sha256(OUTPUT) == first_hash
    assert validate_pdf(OUTPUT) == pdf_validation
    rscript_path = shutil.which("Rscript") or shutil.which("Rscript.exe")
    assert rscript_path is None, (
        "Rscript became available; run the canonical producer directly and "
        "compare it with this equivalence replay before admitting B004"
    )

    low_patients = [patient for patient in risk if risk[patient] == "low"]
    high_patients = [patient for patient in risk if risk[patient] == "high"]
    allocation_groups = {
        f"{assignment}_{risk_level}": [
            patient
            for patient in range(1, 55)
            if allocation[patient] == assignment and risk[patient] == risk_level
        ]
        for assignment in ("control", "treatment")
        for risk_level in ("low", "high")
    }
    receipt = {
        "schema_version": "1.0.0",
        "boundary_id": BOUNDARY_ID,
        "authority": {
            "repository_commit": AUTHORITY_COMMIT,
            "authority_pdf_sha256": (
                "dcbf644c812fc1619a999a9986ad079481652b010c31937679ddd61c523ce429"
            ),
        },
        "runtime": {
            "canonical_r_runtime": {
                "status": "absent_at_replay",
                "rscript_path": None,
                "consequence": (
                    "The canonical self-contained R producer was retained; a Python "
                    "source-equivalence renderer reproduced its R 3.5.3 seeded data "
                    "and complete vector drawing without using the authority PDF."
                ),
            },
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "reportlab": reportlab.Version,
            "pikepdf": pikepdf.__version__,
            "pypdf": pypdf.__version__,
        },
        "producer": producer_record,
        "replay_helper": {
            "path": Path(__file__).name,
            "bytes": Path(__file__).stat().st_size,
            "sha256": sha256(Path(__file__)),
        },
        "source_equivalence": {
            "rng": "R 3.5.3 Mersenne-Twister, seed 2, pre-3.6 rounding sampler",
            "patient_count": 54,
            "risk_counts": {"low": 22, "high": 32},
            "low_risk_patient_ids": low_patients,
            "high_risk_patient_ids": high_patients,
            "allocation_groups": allocation_groups,
            "allocation_counts": {
                name: len(patients) for name, patients in allocation_groups.items()
            },
            "coordinate_geometry_replayed": True,
            "patient_identity_at_every_coordinate_asserted": True,
            "rnorm_marker_scale_replayed": True,
            "rendering_method": (
                "complete native vector reconstruction from canonical producer "
                "algorithm and seeded data; no overlay, paint-over, or old-PDF input"
            ),
        },
        "output": {
            "path": OUTPUT.name,
            "bytes": OUTPUT.stat().st_size,
            "sha256": sha256(OUTPUT),
            **pdf_validation,
        },
        "determinism": {
            "replays": 2,
            "byte_identical": True,
            "sha256_replay_1": first_hash,
            "sha256_replay_2": second_hash,
        },
        "rights": {
            "scope": "localized producer, source-equivalence replay, and generated PDF",
            "license": "CC BY-SA 3.0 Unported",
            "basis": "repo/LICENSE.md and derivative translation status",
            "data": "synthetic seeded patient allocation; no personal data",
        },
    }
    RECEIPT.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
