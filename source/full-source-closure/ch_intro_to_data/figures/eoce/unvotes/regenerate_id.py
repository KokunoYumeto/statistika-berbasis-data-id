"""Deterministically regenerate the localized UN-voting figure.

Inputs are deterministic CSV exports from the exact CRAN unvotes 0.2.0
archive active when this book figure was added in 2019.  The joins, yearly
aggregation, vote-count filter, facets, colors, and local quadratic smooths
implement the durable R producer's semantics without altering the data.
"""

from __future__ import annotations

import hashlib
import io
import math
import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd
from PIL import Image


HERE = Path(__file__).resolve().parent
LANE_ROOT = HERE.parents[4]
DATA_DIR = (
    LANE_ROOT
    / "authority"
    / "external"
    / "r-packages"
    / "unvotes-0.2.0"
    / "data"
)
VOTES_CSV = DATA_DIR / "un_votes_three_countries.csv"
ROLL_CALLS_CSV = DATA_DIR / "un_roll_calls_dates.csv"
ISSUES_CSV = DATA_DIR / "un_roll_call_issues.csv"
OUTPUT = HERE / "unvotes.png"

EXPECTED_INPUT_SHA256 = {
    VOTES_CSV: "ec7f06487a58ccf0eed07d4e012ddeb3c321430be7ba5c5b913370fb68d3b32b",
    ROLL_CALLS_CSV: "8d3c793af76409988b00f61f54c32d8aa88d724192bdfeb56d757a88b2480ab8",
    ISSUES_CSV: "e11ce281b3e23308d08b7d4f49c80dba03a8853802ac877042f956ae9dcbadc0",
}

COUNTRY_MAP = {
    "Canada": "Kanada",
    "Mexico": "Meksiko",
    "United States of America": "AS",
}
COUNTRY_ORDER = ["Kanada", "Meksiko", "AS"]
COUNTRY_COLORS = {
    "Kanada": "#569BBD",
    "Meksiko": "#4C721D",
    "AS": "#F05133",
}
ISSUE_MAP = {
    "Arms control and disarmament": "Pengendalian dan pelucutan senjata",
    "Colonialism": "Kolonialisme",
    "Economic development": "Pembangunan ekonomi",
    "Human rights": "Hak asasi manusia",
    "Nuclear weapons and nuclear material": "Senjata dan bahan nuklir",
    "Palestinian conflict": "Konflik Palestina",
}
ISSUE_ORDER = list(ISSUE_MAP.values())


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_inputs() -> None:
    for path, expected in EXPECTED_INPUT_SHA256.items():
        actual = sha256(path)
        if actual != expected:
            raise RuntimeError(f"Input hash mismatch for {path}: {actual} != {expected}")


def transform() -> tuple[pd.DataFrame, int]:
    votes = pd.read_csv(VOTES_CSV, dtype={"rcid": "int64", "country": "string", "vote": "string"})
    roll_calls = pd.read_csv(
        ROLL_CALLS_CSV, dtype={"rcid": "int64", "date": "string"}
    )
    issues = pd.read_csv(
        ISSUES_CSV, dtype={"rcid": "int64", "issue": "string"}
    )

    votes["country"] = votes["country"].map(COUNTRY_MAP)
    votes = votes.loc[votes["country"].isin(COUNTRY_ORDER)].copy()
    joined = votes.merge(roll_calls, on="rcid", how="inner", sort=False).merge(
        issues, on="rcid", how="inner", sort=False
    )
    joined["issue"] = joined["issue"].map(ISSUE_MAP)
    joined["year"] = joined["date"].str.slice(0, 4).astype("int64")
    joined["yes"] = (joined["vote"] == "yes").astype("float64")

    summary = (
        joined.groupby(["country", "year", "issue"], observed=True, sort=False)
        .agg(votes=("vote", "size"), percent_yes=("yes", "mean"))
        .reset_index()
    )
    summary = summary.loc[summary["votes"] > 5].copy()
    summary["country"] = pd.Categorical(
        summary["country"], categories=COUNTRY_ORDER, ordered=True
    )
    summary["issue"] = pd.Categorical(
        summary["issue"], categories=ISSUE_ORDER, ordered=True
    )
    summary = summary.sort_values(["issue", "country", "year"], kind="stable")
    return summary, len(joined)


def loess_quadratic(
    x: np.ndarray,
    y: np.ndarray,
    *,
    span: float = 0.75,
    output_points: int = 80,
) -> tuple[np.ndarray, np.ndarray]:
    """Local quadratic regression matching ggplot2's default loess semantics."""

    order = np.argsort(x, kind="stable")
    x = np.asarray(x, dtype="float64")[order]
    y = np.asarray(y, dtype="float64")[order]
    evaluation = np.linspace(float(x.min()), float(x.max()), output_points)
    neighbors = max(3, int(math.ceil(span * len(x))))
    fitted = np.empty_like(evaluation)

    for index, center in enumerate(evaluation):
        distance = np.abs(x - center)
        bandwidth = np.partition(distance, neighbors - 1)[neighbors - 1]
        if bandwidth == 0:
            positive = distance[distance > 0]
            bandwidth = positive.min() if len(positive) else 1.0
        scaled = distance / bandwidth
        weights = np.where(scaled < 1.0, (1.0 - scaled**3) ** 3, 0.0)
        centered = x - center
        design = np.column_stack(
            [np.ones_like(centered), centered, centered * centered]
        )
        root_weight = np.sqrt(weights)
        coefficients = np.linalg.lstsq(
            design * root_weight[:, None], y * root_weight, rcond=None
        )[0]
        fitted[index] = coefficients[0]
    return evaluation, fitted


def normalize_png(payload: bytes) -> bytes:
    source = Image.open(io.BytesIO(payload)).convert("RGBA")
    output = io.BytesIO()
    source.save(output, format="PNG", compress_level=9, optimize=False)
    return output.getvalue()


def render(summary: pd.DataFrame) -> bytes:
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
    fig, axes = plt.subplots(2, 3, figsize=(7, 4), dpi=300, sharex=True, sharey=True)
    fig.subplots_adjust(
        left=0.078, right=0.818, bottom=0.135, top=0.915, wspace=0.08, hspace=0.23
    )

    for facet_index, issue in enumerate(ISSUE_ORDER):
        row, column = divmod(facet_index, 3)
        ax = axes[row, column]
        ax.set_axisbelow(True)
        ax.grid(which="major", color="#E5E5E5", linewidth=0.62)
        ax.grid(which="minor", color="#F0F0F0", linewidth=0.42)
        for country in COUNTRY_ORDER:
            subset = summary.loc[
                (summary["issue"] == issue) & (summary["country"] == country)
            ]
            x = subset["year"].to_numpy(dtype="float64")
            y = subset["percent_yes"].to_numpy(dtype="float64")
            ax.scatter(
                x,
                y,
                s=14,
                c=COUNTRY_COLORS[country],
                alpha=0.50,
                edgecolors="none",
                linewidths=0,
                zorder=2,
            )
            smooth_x, smooth_y = loess_quadratic(x, y)
            ax.plot(
                smooth_x,
                smooth_y,
                color=COUNTRY_COLORS[country],
                linewidth=1.55,
                zorder=3,
            )

        ax.set_title(issue, fontsize=8.6, pad=4, color="#1A1A1A")
        ax.set_xlim(1943, 2018)
        ax.set_ylim(-0.06, 1.06)
        ax.set_xticks([1960, 1980, 2000])
        ax.set_xticks([1950, 1970, 1990, 2010], minor=True)
        ax.set_yticks([0.00, 0.25, 0.50, 0.75, 1.00])
        ax.set_yticks([0.125, 0.375, 0.625, 0.875], minor=True)
        ax.set_yticklabels(["0,00", "0,25", "0,50", "0,75", "1,00"])
        ax.tick_params(which="both", length=0, pad=2, labelsize=7.5)
        for spine in ax.spines.values():
            spine.set_visible(False)
        if row == 0:
            ax.tick_params(labelbottom=False)
        if column != 0:
            ax.tick_params(labelleft=False)

    fig.text(0.448, 0.042, "Tahun", ha="center", va="center", fontsize=9.5)
    fig.text(
        0.020,
        0.515,
        "Proporsi suara Ya",
        ha="center",
        va="center",
        rotation=90,
        fontsize=9.5,
    )
    legend_handles = [
        Line2D(
            [0],
            [0],
            color=COUNTRY_COLORS[country],
            linewidth=1.55,
            marker="o",
            markersize=4.0,
            markerfacecolor=COUNTRY_COLORS[country],
            markeredgewidth=0,
            alpha=0.82,
            label=country,
        )
        for country in COUNTRY_ORDER
    ]
    fig.legend(
        handles=legend_handles,
        title="Negara",
        loc="center left",
        bbox_to_anchor=(0.835, 0.51),
        frameon=False,
        borderaxespad=0,
        handlelength=1.7,
        labelspacing=0.8,
        fontsize=8.3,
        title_fontsize=9.1,
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
    summary, joined_rows = transform()
    if joined_rows != 15773:
        raise RuntimeError(f"Unexpected joined row count: {joined_rows}")
    if len(summary) != 932:
        raise RuntimeError(f"Unexpected summarized point count: {len(summary)}")
    payload = render(summary)
    image = Image.open(io.BytesIO(payload))
    if image.size != (2100, 1200):
        raise RuntimeError(f"Unexpected output dimensions: {image.size}")
    temporary = OUTPUT.with_suffix(".png.tmp")
    temporary.write_bytes(payload)
    os.replace(temporary, OUTPUT)
    print(
        f"joined={joined_rows} points={len(summary)} bytes={len(payload)} "
        f"sha256={hashlib.sha256(payload).hexdigest()}"
    )


if __name__ == "__main__":
    main()
