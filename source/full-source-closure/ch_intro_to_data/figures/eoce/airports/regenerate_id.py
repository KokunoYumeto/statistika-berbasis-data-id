"""Deterministically regenerate the localized airport-facets raster.

The plotted records come directly from the exact official OpenIntro package
commit immediately preceding the book figure's 2019 addition.  State geometry
comes from the book's bundled 2013 U.S. Census Bureau 1:20m shapefile.  This is
a data-first plot rebuild; no text is painted over the prior raster.
"""

from __future__ import annotations

import csv
import hashlib
import io
import math
import os
from pathlib import Path
import re
import struct
import tarfile

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt
from matplotlib.path import Path as MplPath
from matplotlib.patches import PathPatch
from PIL import Image


HERE = Path(__file__).resolve().parent
LANE_ROOT = HERE.parents[4]
AUTHORITY_ARCHIVE = (
    LANE_ROOT
    / "authority"
    / "external"
    / "r-packages"
    / "openintro-48793d9645e0da033daaca1c1a19a051533d79d2"
    / "openintro-48793d9645e0da033daaca1c1a19a051533d79d2.tar.gz"
)
AIRPORT_MEMBER = (
    "openintro-48793d9645e0da033daaca1c1a19a051533d79d2/"
    "data-raw/usairports/usairports.csv"
)
SHAPE_DIR = HERE / "data" / "cb_2013_us_state_20m"
SHP = SHAPE_DIR / "cb_2013_us_state_20m.shp"
DBF = SHAPE_DIR / "cb_2013_us_state_20m.dbf"
OUTPUT = HERE / "airports.png"

EXPECTED = {
    AUTHORITY_ARCHIVE: "e8b9526364e70ca59d945fc83eadfd1d25eb784e3190429637f96bfe72b6dc99",
    SHP: "905d4d5a3e896eb7dbe97da8390e05faa0bf633144cf191470f1d3324afb969c",
    DBF: "29f68d2bdcc4dc08073fc9ed76d97556caa78f462e90ebde06e2b7f590d4ac32",
}
EXPECTED_AIRPORT_CSV_SHA256 = (
    "bd07d811661072443648267d1f9f651903c3657f62132323915842130baafd7c"
)

OWNERSHIP_ORDER = ["Milik swasta", "Milik publik"]
USE_ORDER = ["Penggunaan privat", "Penggunaan publik"]
OWNERSHIP_MAP = {"PR": "Milik swasta", "PU": "Milik publik"}
USE_MAP = {"PR": "Penggunaan privat", "PU": "Penggunaan publik"}
REGION_MAP = {
    "AAL": "Alaska",
    "ACE": "Central",
    "AEA": "Eastern",
    "AGL": "Great Lakes",
    "ANE": "New England",
    "ANM": "Northwest Mountain",
    "ASO": "Southern",
    "ASW": "Southwest",
    "AWP": "Western-Pacific",
}
REGION_ORDER = [
    "Central",
    "Eastern",
    "Great Lakes",
    "New England",
    "Northwest Mountain",
    "Southern",
    "Southwest",
    "Western-Pacific",
]
# ggplot2/scales default discrete hue palette for eight levels in the producer.
REGION_COLORS = {
    name: color
    for name, color in zip(
        REGION_ORDER,
        [
            "#F8766D",
            "#CD9600",
            "#7CAE00",
            "#00BE67",
            "#00BFC4",
            "#00A9FF",
            "#C77CFF",
            "#F564E3",
        ],
        strict=True,
    )
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_inputs() -> None:
    for path, expected in EXPECTED.items():
        actual = sha256(path)
        if actual != expected:
            raise RuntimeError(f"Input hash mismatch for {path}: {actual} != {expected}")


def dms_to_decimal(value: str, hemisphere: str) -> float:
    cleaned = value.strip().replace(hemisphere, "").replace("-", " ")
    degrees, minutes, seconds = (float(part) for part in cleaned.split())
    result = degrees + minutes / 60.0 + seconds / 3600.0
    return -result if hemisphere in {"W", "S"} else result


def load_airports() -> list[dict[str, object]]:
    with tarfile.open(AUTHORITY_ARCHIVE, "r:gz") as bundle:
        payload = bundle.extractfile(AIRPORT_MEMBER).read()
    payload_sha = hashlib.sha256(payload).hexdigest()
    if payload_sha != EXPECTED_AIRPORT_CSV_SHA256:
        raise RuntimeError(
            f"Airport CSV hash mismatch: {payload_sha} != {EXPECTED_AIRPORT_CSV_SHA256}"
        )

    records: list[dict[str, object]] = []
    reader = csv.DictReader(io.StringIO(payload.decode("utf-8-sig")))
    for row in reader:
        if "S" in row["ARPLatitude"]:
            continue
        if re.search(r"AK|HI|PR|MQ|GU|CQ", row["State"]):
            continue
        if row["Ownership"] not in OWNERSHIP_MAP:
            continue
        region = REGION_MAP.get(row["Region"])
        use = USE_MAP.get(row["Use"])
        if region is None or use is None:
            continue
        records.append(
            {
                "latitude": dms_to_decimal(row["ARPLatitude"], "N"),
                "longitude": dms_to_decimal(row["ARPLongitude"], "W"),
                "ownership": OWNERSHIP_MAP[row["Ownership"]],
                "region": region,
                "use": use,
            }
        )
    return records


def dbf_rows(path: Path) -> list[dict[str, str]]:
    data = path.read_bytes()
    record_count = struct.unpack_from("<I", data, 4)[0]
    header_length = struct.unpack_from("<H", data, 8)[0]
    record_length = struct.unpack_from("<H", data, 10)[0]
    fields: list[tuple[str, int]] = []
    cursor = 32
    while data[cursor] != 0x0D:
        descriptor = data[cursor : cursor + 32]
        name = descriptor[:11].split(b"\x00", 1)[0].decode("ascii")
        fields.append((name, descriptor[16]))
        cursor += 32

    rows: list[dict[str, str]] = []
    for index in range(record_count):
        record = data[
            header_length + index * record_length :
            header_length + (index + 1) * record_length
        ]
        if not record or record[0:1] == b"*":
            rows.append({})
            continue
        values: dict[str, str] = {}
        offset = 1
        for name, width in fields:
            values[name] = record[offset : offset + width].decode(
                "latin-1", errors="replace"
            ).strip()
            offset += width
        rows.append(values)
    return rows


def shp_polygon_parts(path: Path) -> list[list[list[tuple[float, float]]]]:
    data = path.read_bytes()
    records: list[list[list[tuple[float, float]]]] = []
    cursor = 100
    while cursor < len(data):
        if cursor + 8 > len(data):
            raise RuntimeError("Truncated shapefile record header")
        _record_number, content_words = struct.unpack_from(">ii", data, cursor)
        cursor += 8
        content_length = content_words * 2
        content = data[cursor : cursor + content_length]
        cursor += content_length
        shape_type = struct.unpack_from("<i", content, 0)[0]
        if shape_type == 0:
            records.append([])
            continue
        if shape_type != 5:
            raise RuntimeError(f"Unexpected shapefile geometry type {shape_type}")
        part_count, point_count = struct.unpack_from("<ii", content, 36)
        part_starts = list(struct.unpack_from(f"<{part_count}i", content, 44))
        point_offset = 44 + 4 * part_count
        points = [
            struct.unpack_from("<dd", content, point_offset + 16 * i)
            for i in range(point_count)
        ]
        part_starts.append(point_count)
        records.append(
            [points[start:end] for start, end in zip(part_starts, part_starts[1:])]
        )
    return records


def load_contiguous_states() -> list[list[list[tuple[float, float]]]]:
    attributes = dbf_rows(DBF)
    geometry = shp_polygon_parts(SHP)
    if len(attributes) != len(geometry):
        raise RuntimeError(
            f"Shapefile/DBF record mismatch: {len(geometry)} != {len(attributes)}"
        )
    excluded = {"Alaska", "Hawaii", "Puerto Rico"}
    return [
        polygon
        for row, polygon in zip(attributes, geometry, strict=True)
        if row.get("NAME") not in excluded and polygon
    ]


def add_state(ax, parts: list[list[tuple[float, float]]]) -> None:
    vertices: list[tuple[float, float]] = []
    codes: list[int] = []
    for ring in parts:
        if not ring:
            continue
        vertices.extend(ring)
        codes.extend([MplPath.MOVETO] + [MplPath.LINETO] * (len(ring) - 1))
        vertices.append(ring[0])
        codes.append(MplPath.CLOSEPOLY)
    ax.add_patch(
        PathPatch(
            MplPath(vertices, codes),
            facecolor="#F5F5F5",
            edgecolor="#808080",
            linewidth=0.28,
            zorder=1,
        )
    )


def normalize_png(payload: bytes) -> bytes:
    source = Image.open(io.BytesIO(payload)).convert("RGBA")
    output = io.BytesIO()
    source.save(output, format="PNG", compress_level=9, optimize=False)
    return output.getvalue()


def render(records: list[dict[str, object]], states) -> bytes:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 8,
            "axes.edgecolor": "none",
            "axes.labelcolor": "#4D4D4D",
            "xtick.color": "#4D4D4D",
            "ytick.color": "#4D4D4D",
        }
    )
    fig, axes = plt.subplots(2, 2, figsize=(7, 4), dpi=300, sharex=False, sharey=False)
    fig.subplots_adjust(
        left=0.075, right=0.935, bottom=0.115, top=0.885, wspace=0.035, hspace=0.055
    )
    x_ticks = list(range(-130, -59, 10))
    y_ticks = list(range(20, 51, 5))

    for row_index, ownership in enumerate(OWNERSHIP_ORDER):
        for col_index, use in enumerate(USE_ORDER):
            ax = axes[row_index, col_index]
            ax.set_axisbelow(True)
            ax.grid(True, color="#E6E6E6", linewidth=0.48)
            for state in states:
                add_state(ax, state)

            subset = [
                record
                for record in records
                if record["ownership"] == ownership and record["use"] == use
            ]
            for region in REGION_ORDER:
                regional = [record for record in subset if record["region"] == region]
                if regional:
                    ax.scatter(
                        [record["longitude"] for record in regional],
                        [record["latitude"] for record in regional],
                        s=10,
                        c=REGION_COLORS[region],
                        alpha=0.30,
                        edgecolors="none",
                        linewidths=0,
                        zorder=2,
                    )

            ax.set_xlim(-130, -60)
            ax.set_ylim(20, 50)
            ax.set_aspect(1.0 / math.cos(math.radians(35.0)), adjustable="box")
            ax.set_xticks(x_ticks)
            ax.set_yticks(y_ticks)
            ax.tick_params(length=0, pad=2, labelsize=7.4)
            for spine in ax.spines.values():
                spine.set_visible(False)
            if row_index == 1:
                labels = [f"{abs(value)}°W" for value in x_ticks]
                # Suppress the duplicated seam endpoints so adjacent facet
                # labels never collide at publication size.
                if col_index == 0:
                    labels[-1] = ""
                else:
                    labels[0] = ""
                ax.set_xticklabels(labels)
            else:
                ax.tick_params(labelbottom=False)
            if col_index == 0:
                ax.set_yticklabels([f"{value}°N" for value in y_ticks])
            else:
                ax.tick_params(labelleft=False)
            if row_index == 0:
                ax.set_title(use, fontsize=9.5, pad=5, color="#1A1A1A")

        axes[row_index, 1].yaxis.set_label_position("right")
        axes[row_index, 1].set_ylabel(
            ownership,
            rotation=270,
            labelpad=25,
            fontsize=9.1,
            color="#1A1A1A",
            va="center",
        )

    fig.text(
        0.995,
        0.012,
        "Sumber peta dasar: U.S. Census Bureau (2013)",
        ha="right",
        va="bottom",
        fontsize=4.8,
        color="#666666",
    )
    buffer = io.BytesIO()
    fig.savefig(
        buffer,
        format="png",
        dpi=300,
        facecolor="white",
        edgecolor="white",
        metadata={"Software": "R011 deterministic figure regeneration"},
    )
    plt.close(fig)
    return normalize_png(buffer.getvalue())


def main() -> None:
    verify_inputs()
    records = load_airports()
    states = load_contiguous_states()
    if len(records) != 18472:
        raise RuntimeError(f"Unexpected filtered-airport count: {len(records)}")
    if len(states) != 49:
        raise RuntimeError(f"Unexpected contiguous-state record count: {len(states)}")
    payload = render(records, states)
    image = Image.open(io.BytesIO(payload))
    if image.size != (2100, 1200):
        raise RuntimeError(f"Unexpected output dimensions: {image.size}")
    temporary = OUTPUT.with_suffix(".png.tmp")
    temporary.write_bytes(payload)
    os.replace(temporary, OUTPUT)
    cell_counts = {
        f"{ownership}|{use}": sum(
            record["ownership"] == ownership and record["use"] == use
            for record in records
        )
        for ownership in OWNERSHIP_ORDER
        for use in USE_ORDER
    }
    print(
        f"airports={len(records)} states={len(states)} cells={cell_counts} "
        f"bytes={len(payload)} sha256={hashlib.sha256(payload).hexdigest()}"
    )


if __name__ == "__main__":
    main()
