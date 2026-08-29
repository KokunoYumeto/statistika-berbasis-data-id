#!/usr/bin/env python3
"""Regenerate the three R011-B024 charts that contain visible English labels."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path

import matplotlib

matplotlib.use("pdf")
import matplotlib.pyplot as plt
import numpy as np
import pdfplumber
from pypdf import PdfReader
from scipy.stats import chi2


ROOT = Path(__file__).resolve().parents[1]
AUTHORITY = ROOT / (
    "authority/upstream/openintro-statistics-"
    "fee25091fb24e89c36296fd67c48c1fcf7a93b6e"
)
FIGURES = AUTHORITY / "ch_inference_for_props/figures"
OUTPUT_DIR = ROOT / "qa/b024-translation/staging/assets"
RECEIPT = ROOT / "qa/b024-translation/R011-B024_LOCALIZED_CHARTS_QA.json"

SOURCE_IDENTITIES = {
    "chi_square_df": {
        "path": FIGURES
        / "chiSquareDistributionWithInceasingDF/chiSquareDistributionWithInceasingDF.pdf",
        "bytes": 11_998,
        "sha256": "78ca28a7f9c8c0584ac3d72cc6f848a197e85304c34630854ee1bb4543bc0698",
        "producer": FIGURES
        / "chiSquareDistributionWithInceasingDF/chiSquareDistributionWithInceasingDF.R",
        "producer_bytes": 741,
        "producer_sha256": "fdb1620322a3e0aa737f5b980211f3097cc59501b0f91ec10316dd010ad44c2a",
    },
    "sp500_fit": {
        "path": FIGURES / "geomFitEvaluationForSP500/geomFitEvaluationForSP500.pdf",
        "bytes": 5_356,
        "sha256": "6bee90022a0d24498b37e4aea7db27f6d03720e3b285d41d57b3beafc57a8655",
        "producer": FIGURES / "geomFitEvaluationForSP500/geomFitEvaluationForSP500.R",
        "producer_bytes": 1_291,
        "producer_sha256": "91728b5ccccf3e9cb473a29c12bd872dd7e6786e24a2e1f2184cbd6e0e3e8508",
    },
    "sp500_pvalue": {
        "path": FIGURES / "geomFitPValueForSP500/geomFitPValueForSP500.pdf",
        "bytes": 6_231,
        "sha256": "592a45f22d8265a8603b24ca13955dd2d4dcdb7a42bc7c1131ef04652870a4d2",
        "producer": FIGURES / "geomFitPValueForSP500/geomFitPValueForSP500.R",
        "producer_bytes": 395,
        "producer_sha256": "e5fefdad61bfe5018ac7c3a7ad94c7b0b62a1467e6e1fcbf77abf14521fc873d",
    },
}
DATA = FIGURES / "geomFitEvaluationForSP500/sp500_1950_2018.csv"
DATA_IDENTITY = {
    "bytes": 1_301_875,
    "sha256": "fb4271bbb4284c03848eda46624734ad37e1b81ca16258385a160c1aa459dd6a",
}

OUTPUTS = {
    "chi_square_df": OUTPUT_DIR / "chiSquareDistributionWithInceasingDF.id.pdf",
    "sp500_fit": OUTPUT_DIR / "geomFitEvaluationForSP500.id.pdf",
    "sp500_pvalue": OUTPUT_DIR / "geomFitPValueForSP500.id.pdf",
}
BLUE = "#5ba2c5"
YELLOW = "#f4df00"
ORANGE = "#d97932"
GREEN = "#3b9b72"
FIXED_DATE = dt.datetime(2000, 1, 1, tzinfo=dt.timezone.utc)


class GateError(RuntimeError):
    pass


def canonical(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def identity(path: Path) -> dict[str, object]:
    raw = path.read_bytes()
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GateError(message)


def verify_authority() -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for role, spec in SOURCE_IDENTITIES.items():
        source = identity(spec["path"])
        producer = identity(spec["producer"])
        require(
            (source["bytes"], source["sha256"]) == (spec["bytes"], spec["sha256"]),
            f"pinned source figure changed: {role}",
        )
        require(
            (producer["bytes"], producer["sha256"])
            == (spec["producer_bytes"], spec["producer_sha256"]),
            f"pinned source producer changed: {role}",
        )
        records.append({"role": role, "source": source, "producer": producer})
    data = identity(DATA)
    require(
        (data["bytes"], data["sha256"])
        == (DATA_IDENTITY["bytes"], DATA_IDENTITY["sha256"]),
        "pinned S&P 500 data changed",
    )
    records.append({"role": "sp500_data", "source": data})
    return records


def configure() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.linewidth": 0.8,
            "pdf.fonttype": 42,
            "savefig.transparent": False,
        }
    )


def metadata(title: str, subject: str) -> dict[str, object]:
    return {
        "Title": title,
        "Author": "OpenIntro; turunan lokal oleh OpenAI Codex gpt-5.6-sol, Ultra",
        "Subject": subject,
        "Creator": "OpenAI Codex gpt-5.6-sol, Ultra",
        "Producer": "Matplotlib deterministic PDF backend",
        "CreationDate": FIXED_DATE,
        "ModDate": FIXED_DATE,
    }


def finish(fig: plt.Figure, path: Path, title: str, subject: str) -> None:
    fig.savefig(path, format="pdf", metadata=metadata(title, subject))
    plt.close(fig)


def build_chi_square_df(path: Path) -> None:
    fig, ax = plt.subplots(figsize=(6.5, 3.0))
    x = np.linspace(1e-6, 25.0, 1200)
    styles = ["-", "--", ":"]
    colors = [BLUE, ORANGE, GREEN]
    for df, style, color, width in zip((2, 4, 9), styles, colors, (1.6, 1.8, 2.0)):
        ax.plot(x, chi2.pdf(x, df), linestyle=style, color=color, linewidth=width, label=str(df))
    ax.set_xlim(0, 25)
    ax.set_ylim(0, 0.52)
    ax.set_xticks((0, 5, 10, 15, 20, 25))
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["top"].set_visible(False)
    ax.legend(
        title="Derajat kebebasan",
        loc="upper right",
        frameon=True,
        fancybox=False,
        edgecolor="black",
        framealpha=1,
    )
    fig.subplots_adjust(left=0.035, right=0.985, top=0.97, bottom=0.17)
    finish(
        fig,
        path,
        "Distribusi khi-kuadrat dengan beberapa derajat kebebasan",
        "Kurva df 2, 4, dan 9; label terlihat dilokalkan ke Bahasa Indonesia.",
    )


def sp500_statistics() -> dict[str, object]:
    rows: list[dict[str, str]] = []
    with DATA.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if "2009-01-01" <= row["Date"] <= "2018-12-31":
                rows.append(row)
    adjusted = [float(row["Adj Close"]) for row in rows]
    rises = [1 if right - left > 0 else 0 for left, right in zip(adjusted, adjusted[1:])]
    rise_indices = [index for index, value in enumerate(rises) if value == 1]
    waits = [right - left for left, right in zip(rise_indices, rise_indices[1:])]
    observed = [sum(wait == value for wait in waits) for value in range(1, 7)]
    observed.append(sum(wait >= 7 for wait in waits))
    fitted_p = sum(rises) / len(rises)
    probabilities = [fitted_p * (1 - fitted_p) ** exponent for exponent in range(6)]
    probabilities.append(1 - sum(probabilities))
    expected = [probability * sum(observed) for probability in probabilities]
    statistic = sum((actual - fitted) ** 2 / fitted for actual, fitted in zip(observed, expected))
    p_value = float(chi2.sf(statistic, 5))
    require(len(rows) == 2501 and len(rises) == 2500, "ten-year S&P 500 interval changed")
    require(observed == [717, 369, 155, 69, 28, 14, 10], "observed waiting counts changed")
    require(sum(observed) == 1362, "observed waiting-count total changed")
    require(math.isclose(fitted_p, 0.5452, rel_tol=0, abs_tol=1e-12), "fitted p changed")
    require(math.isclose(sum(expected), 1362.0, rel_tol=0, abs_tol=1e-9), "unrounded expectations do not close")
    require(math.isclose(statistic, 4.612002912979501, rel_tol=0, abs_tol=1e-12), "Pearson statistic changed")
    require(math.isclose(p_value, 0.4650390952024728, rel_tol=0, abs_tol=1e-12), "corrected df=5 p-value changed")
    return {
        "rows": len(rows),
        "daily_differences": len(rises),
        "fitted_p": fitted_p,
        "observed": observed,
        "expected_unrounded": expected,
        "expected_total": sum(expected),
        "pearson_chi_square": statistic,
        "degrees_of_freedom": 5,
        "p_value": p_value,
    }


def build_sp500_fit(path: Path, stats: dict[str, object]) -> None:
    categories = np.arange(1, 8)
    observed = np.asarray(stats["observed"], dtype=float)
    expected = np.asarray(stats["expected_unrounded"], dtype=float)
    fig, ax = plt.subplots(figsize=(7.0, 3.5))
    width = 0.25
    ax.bar(categories - width / 2, observed, width=width, color=BLUE, edgecolor="black", linewidth=0.7, label="Teramati")
    ax.bar(categories + width / 2, expected, width=width, color=YELLOW, edgecolor="black", linewidth=0.7, label="Harapan")
    ax.set_xlim(0.45, 7.75)
    ax.set_ylim(0, 800)
    ax.set_xticks(categories, ["1", "2", "3", "4", "5", "6", "7+"])
    ax.set_yticks((0, 200, 400, 600, 800))
    ax.set_xlabel("Waktu tunggu hingga hari kenaikan", labelpad=8)
    # Keep this label horizontal so it is both easier to scan and extracted in
    # the correct reading order by PDF accessibility/search tooling.
    ax.set_ylabel("")
    ax.text(-0.075, 1.015, "Frekuensi", transform=ax.transAxes, ha="left", va="bottom")
    ax.spines["right"].set_visible(False)
    ax.spines["top"].set_visible(False)
    ax.legend(loc="upper right", frameon=True, fancybox=False, edgecolor="black", framealpha=1)
    fig.subplots_adjust(left=0.11, right=0.985, top=0.90, bottom=0.22)
    finish(
        fig,
        path,
        "Kecocokan geometrik untuk S&P 500, 2009–2018",
        "Frekuensi teramati dibanding nilai harapan tak dibulatkan; jumlah harapan tepat 1362.",
    )


def build_sp500_pvalue(path: Path, stats: dict[str, object]) -> None:
    cutoff = float(stats["pearson_chi_square"])
    df = int(stats["degrees_of_freedom"])
    x = np.linspace(0.0, 25.0, 1800)
    y = chi2.pdf(x, df)
    fig, ax = plt.subplots(figsize=(6.6, 2.387))
    ax.plot(x, y, color="black", linewidth=1.0)
    mask = x >= cutoff
    ax.fill_between(x[mask], 0, y[mask], color=BLUE)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.axvline(cutoff, ymin=0, ymax=float(chi2.pdf(cutoff, df) / max(y)), color="black", linewidth=0.8)
    ax.annotate(
        "Luas yang menyatakan\nnilai-p",
        xy=(10.5, float(chi2.pdf(10.5, df)) * 0.7),
        xytext=(15.2, max(y) * 0.58),
        color=BLUE,
        ha="left",
        va="center",
        arrowprops={"arrowstyle": "->", "color": BLUE, "linewidth": 0.9},
    )
    ax.set_xlim(-1, 26)
    ax.set_ylim(-max(y) * 0.035, max(y) * 1.08)
    ax.set_xticks((0, 5, 10, 15, 20, 25))
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["top"].set_visible(False)
    fig.subplots_adjust(left=0.035, right=0.985, top=0.96, bottom=0.19)
    finish(
        fig,
        path,
        "Nilai-p kecocokan geometrik S&P 500",
        "Ekor khi-kuadrat pada X²=4.612 dengan df=5; nilai-p sekitar 0.4650.",
    )


def build_one_replay(targets: dict[str, Path]) -> dict[str, object]:
    configure()
    stats = sp500_statistics()
    build_chi_square_df(targets["chi_square_df"])
    build_sp500_fit(targets["sp500_fit"], stats)
    build_sp500_pvalue(targets["sp500_pvalue"], stats)
    return stats


def extracted_text(path: Path) -> str:
    with pdfplumber.open(path) as document:
        return "\n".join((page.extract_text() or "") for page in document.pages)


def verify_outputs(stats: dict[str, object]) -> list[dict[str, object]]:
    requirements = {
        "chi_square_df": ("Derajat kebebasan", "2", "4", "9"),
        "sp500_fit": ("Teramati", "Harapan", "Frekuensi", "Waktu tunggu hingga hari kenaikan", "7+"),
        "sp500_pvalue": ("Luas yang menyatakan", "nilai-p", "5", "10", "15", "20", "25"),
    }
    forbidden = {
        "chi_square_df": ("Degrees of Freedom",),
        "sp500_fit": ("Observed", "Expected", "Frequency", "Wait Until Positive Day"),
        "sp500_pvalue": ("Area representing", "p-value"),
    }
    records: list[dict[str, object]] = []
    for role, path in OUTPUTS.items():
        reader = PdfReader(str(path))
        require(len(reader.pages) == 1, f"localized {role} must have one page")
        text = extracted_text(path)
        require(all(token in text for token in requirements[role]), f"localized text inventory incomplete: {role}")
        require(all(token not in text for token in forbidden[role]), f"English visible label remains: {role}")
        records.append({
            "role": role,
            **identity(path),
            "pages": 1,
            "visible_text": text.splitlines(),
        })
    require(stats["degrees_of_freedom"] == 5, "fitted-parameter df correction not applied")
    require(math.isclose(float(stats["p_value"]), 0.4650390952024728, abs_tol=1e-12), "corrected p-value not applied")
    return records


def build() -> dict[str, object]:
    authority = verify_authority()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    replay_a = {role: path.with_name(path.name + ".replay-a.tmp.pdf") for role, path in OUTPUTS.items()}
    replay_b = {role: path.with_name(path.name + ".replay-b.tmp.pdf") for role, path in OUTPUTS.items()}
    for path in (*replay_a.values(), *replay_b.values()):
        require(not path.exists(), f"refusing stale replay temporary: {path}")
    stats_a = build_one_replay(replay_a)
    stats_b = build_one_replay(replay_b)
    require(stats_a == stats_b, "S&P 500 calculations differ across replays")
    for role in OUTPUTS:
        require(replay_a[role].read_bytes() == replay_b[role].read_bytes(), f"PDF replay differs: {role}")
        os.replace(replay_a[role], OUTPUTS[role])
        replay_b[role].unlink()
    outputs = verify_outputs(stats_a)
    payload = {
        "$schema": "interlanguage.r011-b024-localized-charts/v1",
        "boundary_id": "R011-B024",
        "status": "PASS_THREE_LABEL_BEARING_CHARTS_LOCALIZED_AND_EXACTLY_REPLAYED",
        "authority": authority,
        "outputs": outputs,
        "deterministic_two_replay": True,
        "visible_english_labels_remaining": 0,
        "data_and_correction_closure": stats_a,
        "corrections_applied": [
            "expected bars use unrounded counts whose sum is exactly 1362",
            "Pearson statistic is computed from unrounded expectations",
            "one fitted geometric parameter reduces chi-square degrees of freedom from 6 to 5",
            "corrected p-value is approximately 0.4650 and leaves the conclusion unchanged",
        ],
        "rights": "CC BY-SA 3.0 repository declaration; upstream source and producer identities retained",
        "translation_provenance": "OpenAI Codex gpt-5.6-sol, Ultra",
        "upstream_contact": False,
        "git_used": False,
        "credentials_accessed": False,
        "publication_performed": False,
    }
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    temporary = RECEIPT.with_name(RECEIPT.name + ".tmp")
    require(not temporary.exists(), f"refusing stale receipt temporary: {temporary}")
    temporary.write_bytes(canonical(payload))
    os.replace(temporary, RECEIPT)
    return {**payload, "receipt": identity(RECEIPT)}


def verify() -> dict[str, object]:
    authority = verify_authority()
    stats = sp500_statistics()
    outputs = verify_outputs(stats)
    expected = {
        "$schema": "interlanguage.r011-b024-localized-charts/v1",
        "boundary_id": "R011-B024",
        "status": "PASS_THREE_LABEL_BEARING_CHARTS_LOCALIZED_AND_EXACTLY_REPLAYED",
        "authority": authority,
        "outputs": outputs,
        "deterministic_two_replay": True,
        "visible_english_labels_remaining": 0,
        "data_and_correction_closure": stats,
        "corrections_applied": [
            "expected bars use unrounded counts whose sum is exactly 1362",
            "Pearson statistic is computed from unrounded expectations",
            "one fitted geometric parameter reduces chi-square degrees of freedom from 6 to 5",
            "corrected p-value is approximately 0.4650 and leaves the conclusion unchanged",
        ],
        "rights": "CC BY-SA 3.0 repository declaration; upstream source and producer identities retained",
        "translation_provenance": "OpenAI Codex gpt-5.6-sol, Ultra",
        "upstream_contact": False,
        "git_used": False,
        "credentials_accessed": False,
        "publication_performed": False,
    }
    require(RECEIPT.is_file() and RECEIPT.read_bytes() == canonical(expected), "localized-chart receipt changed")
    return {**expected, "status": "PASS_EXACT_LOCALIZED_CHART_REPLAY", "receipt": identity(RECEIPT)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--build", action="store_true")
    mode.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    result = build() if args.build else verify()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    try:
        main()
    except GateError as exc:
        raise SystemExit(f"ERROR: {exc}")
