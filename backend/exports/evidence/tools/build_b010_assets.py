"""Build and verify the isolated R011-B010 Indonesian figure candidates.

The canonical repository is read-only.  Pinned English producers/PDFs are
copied into ``source-en``; localized R producers and derived PDFs are written
under ``id-ID``.  Because R is absent from the frozen machine, PDF localization
uses declared one-to-one content-stream substitutions against the pinned PDF
witnesses.  The receipt states this limitation explicitly and never claims an
R replay.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from collections import Counter
from pathlib import Path

import pikepdf
from PIL import Image, ImageDraw, ImageFont


LANE = Path(__file__).resolve().parents[2]
ROOT = Path(__file__).resolve().parent
REPO = LANE / "repo"
AUTHORITY = (
    LANE
    / "authority"
    / "upstream"
    / "openintro-statistics-fee25091fb24e89c36296fd67c48c1fcf7a93b6e"
)

AUTHORITY_ID = {
    "repository_url": "https://github.com/OpenIntroStat/openintro-statistics",
    "branch": "master",
    "commit_sha": "fee25091fb24e89c36296fd67c48c1fcf7a93b6e",
    "tree_sha": "d61cc601e7d97759ce805900520f784d02a0489e",
}

RIGHTS = {
    "classification": "CC-BY-SA-3.0-repository-declaration",
    "decision": "include_subject_to_attribution_and_brand_exclusion",
    "basis": "Pinned README.md plus LICENSE.md; no external-photo override applies to these generated diagrams.",
    "derivative_notice": "Indonesian label localization; retain OpenIntro attribution and CC BY-SA 3.0 notice.",
}


def b(value: str) -> bytes:
    return value.encode("ascii")


FIGURES: dict[str, dict[str, object]] = {
    "photoClassifyVenn": {
        "rel_dir": "photoClassifyVenn",
        "source_r_sha256": "06fe1ac62cbe09c1a125f931559ef8c05a162e7ab83141b5cc57be421be852aa",
        "source_pdf_sha256": "2451736277dca3a1852e2d3b5c9b34ff7d75552f619f183f6d47f26647fef5c0",
        "media_box": [0.0, 0.0, 324.0, 172.0],
        "replacements": [
            (b("/F2 1 Tf 12.00 0.00 0.00 12.00 56.62 46.98 Tm [(ML Predicts F) 50 (ashion)] TJ"), b("/F2 1 Tf 10.00 0.00 0.00 10.00 52.00 47.50 Tm (ML memprediksi busana) Tj"), "ML Predicts Fashion", "ML memprediksi busana"),
            (b("/F2 1 Tf 12.00 0.00 0.00 12.00 132.61 122.40 Tm [(F) 50 (ashion Photos)] TJ"), b("/F2 1 Tf 12.00 0.00 0.00 12.00 157.00 122.40 Tm (Foto busana) Tj"), "Fashion Photos", "Foto busana"),
            (b("/F2 1 Tf 12.00 0.00 0.00 12.00 217.47 19.81 Tm [(Neither) -30 (: 0.82)] TJ"), b("/F2 1 Tf 10.00 0.00 0.00 10.00 196.00 20.50 Tm (Bukan keduanya: 0.82) Tj"), "Neither: 0.82", "Bukan keduanya: 0.82"),
        ],
        "forbidden": ["Predicts Fashion", "Fashion Photos", "Neither"],
        "required": ["ML memprediksi busana", "Foto busana", "Bukan keduanya"],
        "r_source": """library(openintro)\n+data(COL)\n+\n+# Proporsi tidak sepenuhnya tepat; sedikit disesuaikan demi tampilan.\n+\n+pdf('photoClassifyVenn.pdf', 4.5, 2.4)\n+par(mar = rep(0, 4))\n+plot(0:1, 0:1, type = 'n', axes = FALSE)\n+rect(0, 0, 1, 1, lwd=2)\n+rect(0.10, 0.35,\n+     0.75, 0.58,\n+     border = COL[4, 2],\n+     col = paste0(COL[4], \"25\"),\n+     lty = 3,\n+     lwd = 2.512)\n+text(0.33, 0.28, 'ML memprediksi busana', col=COL[4,2], cex=0.85)\n+rect(0.18, 0.34,\n+     0.77, 0.69,\n+     border = COL[1],\n+     col = COL[1, 4],\n+     lty = 2,\n+     lwd = 2)\n+text(0.54, 0.68, 'Foto busana', col = COL[1], pos = 3)\n+text(0.45, 0.45, 0.11, col = COL[5])\n+text(0.14, 0.49, 0.01, col = COL[4], cex = 0.9)\n+text(0.6, 0.63, 0.06, col = COL[1])\n+text(0.8, 0.11, 'Bukan keduanya: 0.82', col = COL[6], cex=0.85)\n+dev.off()\n+""",
        "data_provenance": "Probabilities are hard-coded in the producer. The adjacent TeX names the openintro photo_classify dataset and records `library(openintro); table(photo_classify)` as the computation witness; the R figure itself reads no dataset.",
    },
    "smallpoxTreeDiagram": {
        "rel_dir": "smallpoxTreeDiagram",
        "source_r_sha256": "44fb9930c356e4385602719680880f368f675488068864d9cdb0c209d73e0a85",
        "source_pdf_sha256": "e2b2e01b64f9fe2da54ba5e0b29735dc8dd9b4c4b3c2641e028c6ac863b673f6",
        "media_box": [0.0, 0.0, 504.0, 252.0],
        "replacements": [
            (b("/F2 1 Tf 17.00 0.00 0.00 17.00 91.04 226.26 Tm (Inoculated) Tj"), b("/F2 1 Tf 17.00 0.00 0.00 17.00 101.00 226.26 Tm (Inokulasi) Tj"), "Inoculated", "Inokulasi"),
            (b("/F2 1 Tf 17.00 0.00 0.00 17.00 268.49 226.26 Tm (Result) Tj"), b("/F2 1 Tf 17.00 0.00 0.00 17.00 278.00 226.26 Tm (Hasil) Tj"), "Result", "Hasil"),
            (b("/F2 1 Tf 12.00 0.00 0.00 12.00 97.78 165.79 Tm [(y) 20 (es) 15 (,  0.0392)] TJ"), b("/F2 1 Tf 12.00 0.00 0.00 12.00 102.00 165.79 Tm (ya,  0.0392) Tj"), "yes, 0.0392", "ya, 0.0392"),
            (b("/F2 1 Tf 12.00 0.00 0.00 12.00 257.04 193.16 Tm [(liv) 25 (ed,  0.9754)] TJ"), b("/F2 1 Tf 12.00 0.00 0.00 12.00 257.00 193.16 Tm (hidup,  0.9754) Tj"), "lived, 0.9754", "hidup, 0.9754"),
            (b("/F2 1 Tf 12.00 0.00 0.00 12.00 257.89 138.41 Tm (died,  0.0246) Tj"), b("/F2 1 Tf 10.00 0.00 0.00 10.00 246.00 139.00 Tm (meninggal,  0.0246) Tj"), "died, 0.0246", "meninggal, 0.0246"),
            (b("/F2 1 Tf 12.00 0.00 0.00 12.00 100.48 61.51 Tm [(no) 40 (,  0.9608)] TJ"), b("/F2 1 Tf 12.00 0.00 0.00 12.00 91.00 61.51 Tm (tidak,  0.9608) Tj"), "no, 0.9608", "tidak, 0.9608"),
            (b("/F2 1 Tf 12.00 0.00 0.00 12.00 257.04 88.88 Tm [(liv) 25 (ed,  0.8589)] TJ"), b("/F2 1 Tf 12.00 0.00 0.00 12.00 257.00 88.88 Tm (hidup,  0.8589) Tj"), "lived, 0.8589", "hidup, 0.8589"),
            (b("/F2 1 Tf 12.00 0.00 0.00 12.00 257.89 34.13 Tm (died,  0.1411) Tj"), b("/F2 1 Tf 10.00 0.00 0.00 10.00 246.00 34.70 Tm (meninggal,  0.1411) Tj"), "died, 0.1411", "meninggal, 0.1411"),
        ],
        "forbidden": ["Inoculated", "Result", "lived", "died", "yes", "no"],
        "required": ["Inokulasi", "Hasil", "hidup", "meninggal", "ya", "tidak"],
        "r_source": """library(openintro)\n+\n+myPDF('smallpoxTreeDiagram.pdf', 7, 3.5)\n+treeDiag(c('Inokulasi', 'Hasil'),\n+         c(0.0392, 0.9608),\n+         list(c(0.9754, 0.0246),\n+              c(0.8589, 0.1411)),\n+         textwd = 0.2,\n+         solwd = 0.35,\n+         cex.main = 1.4,\n+         c('ya', 'tidak'),\n+         c('hidup', 'meninggal'),\n+         digits = 5,\n+         col.main = COL[1],\n+         showWork = TRUE)\n+dev.off()\n+""",
        "data_provenance": "All probabilities are hard-coded from the textbook's smallpox contingency table: 6,224 Boston residents exposed in 1721 (244 inoculated, 5,980 not inoculated; lived/died counts 238/6 and 5,136/844). The producer reads no dataset file.",
    },
    "testTree": {
        "rel_dir": "testTree",
        "source_r_sha256": "b66dfbf8cdcfd84ec0b592ee51911959aabaf9b2c2d9a608d3c366450dead5fc",
        "source_pdf_sha256": "ee145ace8aa8d524aea1f7685745b37420cc3aee5d3e6ec70b1ea0ed2c30b60c",
        "media_box": [0.0, 0.0, 468.0, 244.0],
        "replacements": [
            (b("/F2 1 Tf 17.00 0.00 0.00 17.00 90.05 219.63 Tm [(Midter) -25 (m)] TJ"), b("/F2 1 Tf 17.00 0.00 0.00 17.00 105.00 219.63 Tm (UTS) Tj"), "Midterm", "UTS"),
            (b("/F2 1 Tf 17.00 0.00 0.00 17.00 253.26 219.63 Tm (Final) Tj"), b("/F2 1 Tf 17.00 0.00 0.00 17.00 261.00 219.63 Tm (UAS) Tj"), "Final", "UAS"),
            (b("/F2 1 Tf 12.00 0.00 0.00 12.00 241.63 134.67 Tm [(other) 50 (,  0.53)] TJ"), b("/F2 1 Tf 11.00 0.00 0.00 11.00 235.00 135.10 Tm (lainnya,  0.53) Tj"), "other, 0.53", "lainnya, 0.53"),
            (b("/F2 1 Tf 12.00 0.00 0.00 12.00 90.90 59.95 Tm [(other) 50 (,  0.87)] TJ"), b("/F2 1 Tf 11.00 0.00 0.00 11.00 82.00 60.30 Tm (lainnya,  0.87) Tj"), "other, 0.87", "lainnya, 0.87"),
            (b("/F2 1 Tf 12.00 0.00 0.00 12.00 241.63 33.36 Tm [(other) 50 (,  0.89)] TJ"), b("/F2 1 Tf 11.00 0.00 0.00 11.00 235.00 33.70 Tm (lainnya,  0.89) Tj"), "other, 0.89", "lainnya, 0.89"),
        ],
        "forbidden": ["Midterm", "Final", "other"],
        "required": ["UTS", "UAS", "lainnya"],
        "r_source": """library(openintro)\n+\n+myPDF('testTree.pdf', 6.5, 3.4)\n+treeDiag(c('UTS', 'UAS'),\n+         c(0.13, 0.87),\n+         list(c(0.47, 0.53),\n+              c(0.11, 0.89)),\n+         textwd = 0.2,\n+         solwd = 0.35,\n+         cex.main = 1.4,\n+         c('A', 'lainnya'),\n+         c('A', 'lainnya'),\n+         digits = 5,\n+         col.main = COL[1],\n+         showWork = TRUE)\n+dev.off()\n+""",
        "data_provenance": "The four marginal/conditional probabilities are hard-coded from the adjacent textbook example about UTS/UAS grades; no external or package dataset is read.",
    },
    "treeDiagramAndPass": {
        "rel_dir": "treeDiagramAndPass",
        "source_r_sha256": "2d857ded7ad8d8de745c28635f663eea4a10360b336c9fca36880324d20e9198",
        "source_pdf_sha256": "28565782d67daa3b68290c555859dddc53fc5caf243cdcef36824718c22439c5",
        "media_box": [0.0, 0.0, 432.0, 194.0],
        "replacements": [
            (b("/F2 1 Tf 17.00 0.00 0.00 17.00 111.65 193.21 Tm ET"), b("/F2 1 Tf 17.00 0.00 0.00 17.00 111.65 193.21 Tm ET"), "[blank leading line]", "[blank leading line preserved]"),
            (b("/F2 1 Tf 17.00 0.00 0.00 17.00 48.39 173.05 Tm [(Ab) 20 (le to constr) -15 (uct)] TJ"), b("/F2 1 Tf 15.00 0.00 0.00 15.00 55.00 174.00 Tm (Mampu membuat) Tj"), "Able to construct", "Mampu membuat"),
            (b("/F2 1 Tf 17.00 0.00 0.00 17.00 59.78 152.89 Tm [(tree diagr) 10 (ams)] TJ"), b("/F2 1 Tf 15.00 0.00 0.00 15.00 62.00 154.00 Tm (diagram pohon) Tj"), "tree diagrams", "diagram pohon"),
            (b("/F2 1 Tf 17.00 0.00 0.00 17.00 210.50 173.18 Tm [(P) 40 (ass class)] TJ"), b("/F2 1 Tf 12.00 0.00 0.00 12.00 208.00 174.50 Tm (Lulus mata kuliah) Tj"), "Pass class", "Lulus mata kuliah"),
            (b("/F2 1 Tf 12.00 0.00 0.00 12.00 85.85 129.54 Tm [(y) 20 (es) 15 (,  0.78)] TJ"), b("/F2 1 Tf 12.00 0.00 0.00 12.00 90.00 129.54 Tm (ya,  0.78) Tj"), "yes, 0.78", "ya, 0.78"),
            (b("/F2 1 Tf 12.00 0.00 0.00 12.00 221.52 150.66 Tm [(pass) 15 (,  0.97)] TJ"), b("/F2 1 Tf 12.00 0.00 0.00 12.00 221.00 150.66 Tm (lulus,  0.97) Tj"), "pass, 0.97", "lulus, 0.97"),
            (b("/F2 1 Tf 12.00 0.00 0.00 12.00 226.61 108.42 Tm [(f) 30 (ail,  0.03)] TJ"), b("/F2 1 Tf 12.00 0.00 0.00 12.00 226.00 108.42 Tm (gagal,  0.03) Tj"), "fail, 0.03", "gagal, 0.03"),
            (b("/F2 1 Tf 12.00 0.00 0.00 12.00 88.54 49.09 Tm [(no) 40 (,  0.22)] TJ"), b("/F2 1 Tf 12.00 0.00 0.00 12.00 80.00 49.09 Tm (tidak,  0.22) Tj"), "no, 0.22", "tidak, 0.22"),
            (b("/F2 1 Tf 12.00 0.00 0.00 12.00 221.52 70.21 Tm [(pass) 15 (,  0.57)] TJ"), b("/F2 1 Tf 12.00 0.00 0.00 12.00 221.00 70.21 Tm (lulus,  0.57) Tj"), "pass, 0.57", "lulus, 0.57"),
            (b("/F2 1 Tf 12.00 0.00 0.00 12.00 226.61 27.98 Tm [(f) 30 (ail,  0.43)] TJ"), b("/F2 1 Tf 12.00 0.00 0.00 12.00 226.00 27.98 Tm (gagal,  0.43) Tj"), "fail, 0.43", "gagal, 0.43"),
        ],
        "forbidden": ["Able to construct", "tree diagrams", "Pass class", "yes", "no", "pass", "fail"],
        "required": ["Mampu membuat", "diagram pohon", "Lulus mata kuliah", "ya", "tidak", "lulus", "gagal"],
        "r_source": """library(openintro)\n+\n+myPDF('treeDiagramAndPass.pdf', 6, 2.7)\n+treeDiag(c('\\nMampu membuat\\ndiagram pohon', 'Lulus kuliah'),\n+         c(0.78, 0.22),\n+         list(c(0.97, 0.03),\n+              c(0.57, 0.43)),\n+         textwd = 0.2,\n+         solwd = 0.35,\n+         cex.main = 1.25,\n+         c('ya', 'tidak'),\n+         c('lulus', 'gagal'),\n+         digits = 5,\n+         col.main = COL[1],\n+         showWork = TRUE)\n+dev.off()\n+""",
        "data_provenance": "All probabilities are hard-coded from the adjacent guided-practice scenario about ability to construct tree diagrams and course completion; no dataset is read.",
    },
    "BreastCancerTreeDiagram": {
        "rel_dir": "BreastCancerTreeDiagram",
        "source_r_sha256": "71724e847d8d3ded1f8f87a9d8aa96e324c84863519f299540ddd325861ff076",
        "source_pdf_sha256": "cd70daeba274942b81cd48bcccdfabfa1bbb1a3273880988659ec3bdb82e8bdc",
        "media_box": [0.0, 0.0, 540.0, 180.0],
        "replacements": [
            (b("/F2 1 Tf 17.00 0.00 0.00 17.00 120.62 159.91 Tm [(T) 120 (r) -15 (uth)] TJ"), b("/F2 1 Tf 17.00 0.00 0.00 17.00 113.00 159.91 Tm (Kondisi) Tj"), "Truth", "Kondisi"),
            (b("/F2 1 Tf 17.00 0.00 0.00 17.00 263.51 161.65 Tm [(Mammogr) 10 (am)] TJ"), b("/F2 1 Tf 17.00 0.00 0.00 17.00 264.00 161.65 Tm (Mamogram) Tj"), "Mammogram", "Mamogram"),
            (b("/F2 1 Tf 12.00 0.00 0.00 12.00 98.51 120.48 Tm [(cancer) 50 (,  0.0035)] TJ"), b("/F2 1 Tf 12.00 0.00 0.00 12.00 100.00 120.48 Tm (kanker,  0.0035) Tj"), "cancer, 0.0035", "kanker, 0.0035"),
            (b("/F2 1 Tf 12.00 0.00 0.00 12.00 276.70 140.03 Tm [(positiv) 25 (e) 15 (,  0.89)] TJ"), b("/F2 1 Tf 12.00 0.00 0.00 12.00 276.00 140.03 Tm (positif,  0.89) Tj"), "positive, 0.89", "positif, 0.89"),
            (b("/F2 1 Tf 12.00 0.00 0.00 12.00 274.36 100.92 Tm [(negativ) 25 (e) 15 (,  0.11)] TJ"), b("/F2 1 Tf 12.00 0.00 0.00 12.00 273.00 100.92 Tm (negatif,  0.11) Tj"), "negative, 0.11", "negatif, 0.11"),
            (b("/F2 1 Tf 12.00 0.00 0.00 12.00 90.17 45.99 Tm [(no cancer) 50 (,  0.9965)] TJ"), b("/F2 1 Tf 11.00 0.00 0.00 11.00 80.00 46.30 Tm (tanpa kanker,  0.9965) Tj"), "no cancer, 0.9965", "tanpa kanker, 0.9965"),
            (b("/F2 1 Tf 12.00 0.00 0.00 12.00 276.70 65.54 Tm [(positiv) 25 (e) 15 (,  0.07)] TJ"), b("/F2 1 Tf 12.00 0.00 0.00 12.00 276.00 65.54 Tm (positif,  0.07) Tj"), "positive, 0.07", "positif, 0.07"),
            (b("/F2 1 Tf 12.00 0.00 0.00 12.00 274.36 26.44 Tm [(negativ) 25 (e) 15 (,  0.93)] TJ"), b("/F2 1 Tf 12.00 0.00 0.00 12.00 273.00 26.44 Tm (negatif,  0.93) Tj"), "negative, 0.93", "negatif, 0.93"),
        ],
        "forbidden": ["Truth", "Mammogram", "cancer", "positive", "negative"],
        "required": ["Kondisi", "Mamogram", "kanker", "tanpa kanker", "positif", "negatif"],
        "r_source": """library(openintro)\n+\n+myPDF('BreastCancerTreeDiagram.pdf', 7.5, 2.5)\n+treeDiag(c('Kondisi', 'Mamogram'),\n+         c(0.0035, 0.9965),\n+         list(c(0.89, 0.11),\n+              c(0.07, 0.93)),\n+         textwd = 0.2,\n+         solwd = 0.35,\n+         cex.main = 1.4,\n+         c('kanker', 'tanpa kanker'),\n+         c('positif', 'negatif'),\n+         digits = 5,\n+         col.main = COL[1],\n+         showWork = TRUE)\n+dev.off()\n+""",
        "data_provenance": "Probabilities are hard-coded. Adjacent `Mammogram Research.txt` attributes 89% sensitivity and a 7.4% false-positive figure to a legacy Breastcancer.org page, and 0.35% annual prevalence to PMC1173421. The committed figure/textbook use 7%, not 7.4%; this is an explicit rounding/source-note discrepancy, not a downloaded dataset.",
    },
    "treeDiagramGarage": {
        "rel_dir": "treeDiagramGarage",
        "source_r_sha256": "bb6d4b4ac8e4f9205c78804a13c5f152991b6ddcfcd8898fe7a9cd7948a24780",
        "source_pdf_sha256": "f4368ee5169b37a6e83d73348f35a05f488c2985017d4b8736e7b0face1459dc",
        "media_box": [0.0, 0.0, 504.0, 252.0],
        "replacements": [
            (b("/F2 1 Tf 17.00 0.00 0.00 17.00 104.68 226.26 Tm [(Ev) 25 (ent)] TJ"), b("/F2 1 Tf 17.00 0.00 0.00 17.00 105.00 226.26 Tm (Acara) Tj"), "Event", "Acara"),
            (b("/F2 1 Tf 17.00 0.00 0.00 17.00 247.03 227.84 Tm [(Gar) 10 (age full)] TJ"), b("/F2 1 Tf 16.00 0.00 0.00 16.00 239.00 227.84 Tm (Garasi penuh) Tj"), "Garage full", "Garasi penuh"),
            (b("/F2 1 Tf 12.00 0.00 0.00 12.00 83.27 178.82 Tm [(Academic) 15 (,  0.35)] TJ"), b("/F2 1 Tf 12.00 0.00 0.00 12.00 83.00 178.82 Tm (Akademik,  0.35) Tj"), "Academic, 0.35", "Akademik, 0.35"),
            (b("/F2 1 Tf 12.00 0.00 0.00 12.00 262.18 195.77 Tm (Full,  0.25) Tj"), b("/F2 1 Tf 12.00 0.00 0.00 12.00 258.00 195.77 Tm (Penuh,  0.25) Tj"), "Full, 0.25", "Penuh, 0.25"),
            (b("/F2 1 Tf 12.00 0.00 0.00 12.00 226.42 161.88 Tm [(Spaces A) 40 (v) 25 (ailab) 20 (le) 15 (,  0.75)] TJ"), b("/F2 1 Tf 11.00 0.00 0.00 11.00 224.00 162.20 Tm (Tempat tersedia,  0.75) Tj"), "Spaces Available, 0.75", "Tempat tersedia, 0.75"),
            (b("/F2 1 Tf 12.00 0.00 0.00 12.00 86.94 113.65 Tm [(Spor) -40 (ting,  0.20)] TJ"), b("/F2 1 Tf 12.00 0.00 0.00 12.00 86.00 113.65 Tm (Olahraga,  0.20) Tj"), "Sporting, 0.20", "Olahraga, 0.20"),
            (b("/F2 1 Tf 12.00 0.00 0.00 12.00 265.51 130.59 Tm (Full,  0.7) Tj"), b("/F2 1 Tf 12.00 0.00 0.00 12.00 261.00 130.59 Tm (Penuh,  0.7) Tj"), "Full, 0.7", "Penuh, 0.7"),
            (b("/F2 1 Tf 12.00 0.00 0.00 12.00 229.76 96.70 Tm [(Spaces A) 40 (v) 25 (ailab) 20 (le) 15 (,  0.3)] TJ"), b("/F2 1 Tf 11.00 0.00 0.00 11.00 227.00 97.00 Tm (Tempat tersedia,  0.3) Tj"), "Spaces Available, 0.3", "Tempat tersedia, 0.3"),
            (b("/F2 1 Tf 12.00 0.00 0.00 12.00 95.27 48.47 Tm [(None) 15 (,  0.45)] TJ"), b("/F2 1 Tf 11.00 0.00 0.00 11.00 86.00 48.80 Tm (Tidak ada,  0.45) Tj"), "None, 0.45", "Tidak ada, 0.45"),
            (b("/F2 1 Tf 12.00 0.00 0.00 12.00 262.18 65.42 Tm (Full,  0.05) Tj"), b("/F2 1 Tf 12.00 0.00 0.00 12.00 258.00 65.42 Tm (Penuh,  0.05) Tj"), "Full, 0.05", "Penuh, 0.05"),
            (b("/F2 1 Tf 12.00 0.00 0.00 12.00 226.42 31.52 Tm [(Spaces A) 40 (v) 25 (ailab) 20 (le) 15 (,  0.95)] TJ"), b("/F2 1 Tf 11.00 0.00 0.00 11.00 224.00 31.90 Tm (Tempat tersedia,  0.95) Tj"), "Spaces Available, 0.95", "Tempat tersedia, 0.95"),
        ],
        "forbidden": ["Event", "Garage full", "Academic", "Sporting", "None", "Full", "Spaces Available"],
        "required": ["Acara", "Garasi penuh", "Akademik", "Olahraga", "Tidak ada", "Penuh", "Tempat tersedia"],
        "r_source": """library(openintro)\n+\n+myPDF('treeDiagramGarage.pdf', 7, 3.5)\n+treeDiag(c('Acara', 'Garasi penuh'),\n+         c(0.35, 0.20, 0.45),\n+         list(c(0.25, 0.75),\n+              c(0.7, 0.3),\n+              c(0.05, 0.95)),\n+         textwd = 0.22,\n+         solwd = 0.35,\n+         cex.main = 1.3,\n+         c('Akademik', 'Olahraga', 'Tidak ada'),\n+         c('Penuh', 'Tempat tersedia'),\n+         digits = 5,\n+         col.main = COL[1],\n+         showWork = TRUE)\n+dev.off()\n+""",
        "data_provenance": "All probabilities are hard-coded from the adjacent textbook parking-garage guided practice; no dataset is read.",
    },
    "tree_drawing_box_plots": {
        "rel_dir": "eoce/tree_drawing_box_plots",
        "source_r_sha256": "fbb3f706bd596a1f0153a049c7ef7c3285996ae3b7dc1c772c2f8145db3813e9",
        "source_pdf_sha256": "8ddf9bc83193c4196e81a9a729c9183829da00f147baec38ed900b1e06ad7245",
        "media_box": [0.0, 0.0, 432.0, 180.0],
        "replacements": [
            (b("/F2 1 Tf 16.00 0.00 0.00 16.00 122.67 178.86 Tm ET"), b("/F2 1 Tf 16.00 0.00 0.00 16.00 122.67 178.86 Tm ET"), "[blank leading line]", "[blank leading line preserved]"),
            (b("/F2 1 Tf 16.00 0.00 0.00 16.00 73.19 160.14 Tm [(Can constr) -15 (uct)] TJ"), b("/F2 1 Tf 14.00 0.00 0.00 14.00 72.00 161.00 Tm (Dapat membuat) Tj"), "Can construct", "Dapat membuat"),
            (b("/F2 1 Tf 16.00 0.00 0.00 16.00 86.44 141.42 Tm [(bo) 30 (x plots?)] TJ"), b("/F2 1 Tf 14.00 0.00 0.00 14.00 69.00 142.00 Tm (diagram kotak?) Tj"), "box plots?", "diagram kotak?"),
            (b("/F2 1 Tf 16.00 0.00 0.00 16.00 244.24 160.19 Tm [(P) 40 (assed?)] TJ"), b("/F2 1 Tf 16.00 0.00 0.00 16.00 249.00 160.19 Tm (Lulus?) Tj"), "Passed?", "Lulus?"),
            (b("/F2 1 Tf 12.00 0.00 0.00 12.00 100.20 120.48 Tm [(y) 20 (es) 15 (,  0.8)] TJ"), b("/F2 1 Tf 12.00 0.00 0.00 12.00 104.00 120.48 Tm (ya,  0.8) Tj"), "yes, 0.8", "ya, 0.8"),
            (b("/F2 1 Tf 12.00 0.00 0.00 12.00 248.96 140.03 Tm [(Y) 140 (es) 15 (,  0.86)] TJ"), b("/F2 1 Tf 12.00 0.00 0.00 12.00 252.00 140.03 Tm (Ya,  0.86) Tj"), "Yes, 0.86", "Ya, 0.86"),
            (b("/F2 1 Tf 12.00 0.00 0.00 12.00 250.94 100.92 Tm [(No) 40 (,  0.14)] TJ"), b("/F2 1 Tf 12.00 0.00 0.00 12.00 246.00 100.92 Tm (Tidak,  0.14) Tj"), "No, 0.14", "Tidak, 0.14"),
            (b("/F2 1 Tf 12.00 0.00 0.00 12.00 102.89 45.99 Tm [(no) 40 (,  0.2)] TJ"), b("/F2 1 Tf 12.00 0.00 0.00 12.00 94.00 45.99 Tm (tidak,  0.2) Tj"), "no, 0.2", "tidak, 0.2"),
            (b("/F2 1 Tf 12.00 0.00 0.00 12.00 248.96 65.54 Tm [(Y) 140 (es) 15 (,  0.65)] TJ"), b("/F2 1 Tf 12.00 0.00 0.00 12.00 252.00 65.54 Tm (Ya,  0.65) Tj"), "Yes, 0.65", "Ya, 0.65"),
            (b("/F2 1 Tf 12.00 0.00 0.00 12.00 250.94 26.44 Tm [(No) 40 (,  0.35)] TJ"), b("/F2 1 Tf 12.00 0.00 0.00 12.00 246.00 26.44 Tm (Tidak,  0.35) Tj"), "No, 0.35", "Tidak, 0.35"),
        ],
        "forbidden": ["Can construct", "box plots", "Passed", "yes", "no", "Yes", "No"],
        "required": ["Dapat membuat", "diagram kotak", "Lulus", "ya", "tidak", "Ya", "Tidak"],
        "r_source": """# Muat openintro untuk fungsi treeDiag.\n+library(openintro)\n+\n+pdf('tree_drawing_box_plots.pdf', width = 6, height = 2.5)\n+treeDiag(c('\\nDapat membuat\\ndiagram kotak?', 'Lulus?'),\n+         c(0.80, 0.20), list(c(0.86, 0.14), c(0.65, 0.35)),\n+         c('ya', 'tidak'), textwd = 0.19, solwd = 0.25, showWork = TRUE,\n+         col.main = COL[1])\n+dev.off()\n+""",
        "data_provenance": "All probabilities are hard-coded from end-of-section exercise 19; no dataset is read.",
    },
    "tree_lupus": {
        "rel_dir": "eoce/tree_lupus",
        "source_r_sha256": "a9d8223c48c0977c431e08946a0f91cf01097d95b24fc22d685f376fca5cb912",
        "source_pdf_sha256": "6eec693d5df94876f304865ea7c90935952b2dba9ed24d750b6a0fec7de92185",
        "media_box": [0.0, 0.0, 432.0, 216.0],
        "replacements": [
            (b("/F2 1 Tf 16.00 0.00 0.00 16.00 252.38 193.44 Tm (Result) Tj"), b("/F2 1 Tf 16.00 0.00 0.00 16.00 258.00 193.44 Tm (Hasil) Tj"), "Result", "Hasil"),
            (b("/F2 1 Tf 12.00 0.00 0.00 12.00 96.86 143.13 Tm [(y) 20 (es) 15 (,  0.02)] TJ"), b("/F2 1 Tf 12.00 0.00 0.00 12.00 101.00 143.13 Tm (ya,  0.02) Tj"), "yes, 0.02", "ya, 0.02"),
            (b("/F2 1 Tf 12.00 0.00 0.00 12.00 238.27 166.60 Tm [(positiv) 25 (e) 15 (,  0.98)] TJ"), b("/F2 1 Tf 12.00 0.00 0.00 12.00 238.00 166.60 Tm (positif,  0.98) Tj"), "positive, 0.98", "positif, 0.98"),
            (b("/F2 1 Tf 12.00 0.00 0.00 12.00 235.93 119.67 Tm [(negativ) 25 (e) 15 (,  0.02)] TJ"), b("/F2 1 Tf 12.00 0.00 0.00 12.00 235.00 119.67 Tm (negatif,  0.02) Tj"), "negative, 0.02", "negatif, 0.02"),
            (b("/F2 1 Tf 12.00 0.00 0.00 12.00 99.55 53.75 Tm [(no) 40 (,  0.98)] TJ"), b("/F2 1 Tf 12.00 0.00 0.00 12.00 91.00 53.75 Tm (tidak,  0.98) Tj"), "no, 0.98", "tidak, 0.98"),
            (b("/F2 1 Tf 12.00 0.00 0.00 12.00 238.27 77.21 Tm [(positiv) 25 (e) 15 (,  0.26)] TJ"), b("/F2 1 Tf 12.00 0.00 0.00 12.00 238.00 77.21 Tm (positif,  0.26) Tj"), "positive, 0.26", "positif, 0.26"),
            (b("/F2 1 Tf 12.00 0.00 0.00 12.00 235.93 30.28 Tm [(negativ) 25 (e) 15 (,  0.74)] TJ"), b("/F2 1 Tf 12.00 0.00 0.00 12.00 235.00 30.28 Tm (negatif,  0.74) Tj"), "negative, 0.74", "negatif, 0.74"),
        ],
        "forbidden": ["Result", "yes", "no", "positive", "negative"],
        "required": ["Hasil", "ya", "tidak", "positif", "negatif"],
        "r_source": """# Muat openintro untuk fungsi treeDiag.\n+library(openintro)\n+\n+pdf('tree_lupus.pdf', width = 6, height = 3)\n+treeDiag(c('Lupus?', 'Hasil'),\n+         c(0.02, 0.98), list(c(0.98, 0.02), c(0.26, 0.74)),\n+         c('ya', 'tidak'), c('positif', 'negatif'),\n+         textwd=0.19, solwd=0.25, showWork=TRUE,\n+         col.main = COL[1])\n+dev.off()\n+""",
        "data_provenance": "All probabilities are hard-coded from end-of-section exercise 21; no dataset is read.",
    },
}

# The multiline literals above retain patch-leading plus signs as inert source
# notation.  Strip those markers before emitting executable candidate R files.
for _figure_spec in FIGURES.values():
    _figure_spec["r_source"] = str(_figure_spec["r_source"]).replace("\n+", "\n")
FIGURES["treeDiagramAndPass"]["r_source"] = (
    str(FIGURES["treeDiagramAndPass"]["r_source"])
    .replace("Lulus kuliah", "Lulus mata kuliah")
    .replace("cex.main = 1.25", "cex.main = 1.1")
)


ALT_TEXT: dict[str, dict[str, str]] = {
    "photoClassifyVenn": {
        "tex_path": "ch_probability/TeX/ch_probability.tex",
        "macro": "Figure",
        "id_ID": 'Diagram Venn berbentuk persegi panjang ditampilkan untuk dua kategori yang saling tumpang tindih, yaitu "ML memprediksi busana" dan "Foto busana". Bagian persegi panjang ML memprediksi busana yang tidak tumpang tindih berlabel 0.01. Bagian persegi panjang Foto busana yang tidak tumpang tindih berlabel 0.06. Bagian tumpang tindih berlabel 0.11. Di luar kedua persegi panjang terdapat label "Bukan keduanya" dengan nilai 0.82.',
        "macro_tail": "{0.65}{photoClassifyVenn}",
    },
    "smallpoxTreeDiagram": {
        "tex_path": "ch_probability/TeX/ch_probability.tex",
        "macro": "Figure",
        "id_ID": 'Diagram pohon dengan cabang utama "Inokulasi" dan cabang sekunder "Hasil". Cabang utama Inokulasi terbagi menjadi "ya" dengan peluang 0.0392 dan "tidak" dengan peluang 0.9608. Cabang ya terbagi menjadi "hidup" (0.9754) dan "meninggal" (0.0246), dengan peluang gabungan masing-masing 0.03824 dan 0.00096. Cabang tidak terbagi menjadi hidup (0.8589) dan meninggal (0.1411), dengan peluang gabungan masing-masing 0.82523 dan 0.13557.',
        "macro_tail": "{0.93}{smallpoxTreeDiagram}",
    },
    "testTree": {
        "tex_path": "ch_probability/TeX/ch_probability.tex",
        "macro": "Figure",
        "id_ID": 'Diagram pohon dengan cabang utama "UTS" dan cabang sekunder "UAS". Cabang UTS terbagi menjadi nilai A dengan peluang 0.13 dan nilai lainnya dengan peluang 0.87. Cabang UTS-A terbagi menjadi UAS-A (0.47; peluang gabungan 0.0611) dan UAS-lainnya (0.53; peluang gabungan 0.0689). Cabang UTS-lainnya terbagi menjadi UAS-A (0.11; peluang gabungan 0.0957) dan UAS-lainnya (0.89; peluang gabungan 0.7743).',
        "macro_tail": "{0.85}{testTree}",
    },
    "treeDiagramAndPass": {
        "tex_path": "ch_probability/TeX/ch_probability.tex",
        "macro": "Figure",
        "id_ID": 'Diagram pohon dengan cabang utama "Mampu membuat diagram pohon" dan cabang sekunder "Lulus kuliah". Cabang utama terbagi menjadi ya dengan peluang 0.78 dan tidak dengan peluang 0.22. Cabang ya terbagi menjadi lulus (0.97; peluang gabungan 0.7566) dan gagal (0.03; peluang gabungan 0.0234). Cabang tidak terbagi menjadi lulus (0.57; peluang gabungan 0.1254) dan gagal (0.43; peluang gabungan 0.0946).',
        "macro_tail": "{0.7}{treeDiagramAndPass}",
    },
    "BreastCancerTreeDiagram": {
        "tex_path": "ch_probability/TeX/ch_probability.tex",
        "macro": "Figure",
        "id_ID": 'Diagram pohon dengan cabang utama "Kondisi" dan cabang sekunder "Mamogram". Cabang kondisi terbagi menjadi kanker dengan peluang 0.0035 dan tanpa kanker dengan peluang 0.9965. Cabang kanker terbagi menjadi hasil positif (0.89; peluang gabungan 0.00312) dan negatif (0.11; peluang gabungan 0.00038). Cabang tanpa kanker terbagi menjadi hasil positif (0.07; peluang gabungan 0.06976) dan negatif (0.93; peluang gabungan 0.92675).',
        "macro_tail": "{0.9}{BreastCancerTreeDiagram}",
    },
    "treeDiagramGarage": {
        "tex_path": "ch_probability/TeX/ch_probability.tex",
        "macro": "Figure",
        "id_ID": 'Diagram pohon dengan cabang utama "Acara" dan cabang sekunder "Garasi penuh". Cabang acara terbagi menjadi Akademik (0.35), Olahraga (0.20), dan Tidak ada (0.45). Masing-masing memiliki cabang Penuh dan Tempat tersedia: untuk Akademik, 0.25 dan 0.75 dengan peluang gabungan 0.0875 dan 0.2625; untuk Olahraga, 0.7 dan 0.3 dengan peluang gabungan 0.14 dan 0.06; untuk Tidak ada, 0.05 dan 0.95 dengan peluang gabungan 0.0225 dan 0.4275.',
        "macro_tail": "{}{treeDiagramGarage}",
    },
    "tree_drawing_box_plots": {
        "tex_path": "extraTeX/eoceSolutions/eoceSolutions.tex",
        "macro": "FigureFullPath",
        "id_ID": 'Diagram pohon dengan cabang utama "Dapat membuat diagram kotak?" dan cabang sekunder "Lulus?". Cabang utama terbagi menjadi ya dengan peluang 0.8 dan tidak dengan peluang 0.2. Cabang ya terbagi menjadi lulus (0.86; peluang gabungan 0.688) dan tidak lulus (0.14; peluang gabungan 0.112). Cabang tidak terbagi menjadi lulus (0.65; peluang gabungan 0.13) dan tidak lulus (0.35; peluang gabungan 0.07).',
        "macro_tail": "{0.375}{ch_probability/figures/eoce/tree_drawing_box_plots/tree_drawing_box_plots}",
    },
    "tree_lupus": {
        "tex_path": "extraTeX/eoceSolutions/eoceSolutions.tex",
        "macro": "FigureFullPath",
        "id_ID": 'Diagram pohon dengan cabang utama "Lupus?" dan cabang sekunder "Hasil" untuk tes lupus. Cabang utama terbagi menjadi ya dengan peluang 0.02 dan tidak dengan peluang 0.98. Cabang ya terbagi menjadi hasil positif (0.98; peluang gabungan 0.0196) dan negatif (0.02; peluang gabungan 0.0004). Cabang tidak terbagi menjadi hasil positif (0.26; peluang gabungan 0.2548) dan negatif (0.74; peluang gabungan 0.7252).',
        "macro_tail": "{0.375}{ch_probability/figures/eoce/tree_lupus/tree_lupus.pdf}",
    },
}

for _alt_spec in ALT_TEXT.values():
    _alt_spec["id_ID"] = (
        _alt_spec["id_ID"]
        .replace("peluang gabungan", "peluang bersama")
        .replace("Lulus kuliah", "Lulus mata kuliah")
    )

SOURCE_ALT_PATTERNS = {
    asset_id: re.compile(
        rf"\\{re.escape(spec['macro'])}\[([^\r\n]*)\]{re.escape(spec['macro_tail'])}",
    )
    for asset_id, spec in ALT_TEXT.items()
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8", newline="\n")


def validate_r_candidate(text: str, asset_id: str) -> bool:
    if any(line.startswith("+") for line in text.splitlines()):
        raise RuntimeError(f"patch marker leaked into candidate R: {asset_id}")
    if "library(openintro)" not in text:
        raise RuntimeError(f"openintro dependency missing from candidate R: {asset_id}")
    if f"{asset_id}.pdf" not in text:
        raise RuntimeError(f"expected output filename missing from candidate R: {asset_id}")
    for opening, closing in (("(", ")"), ("[", "]"), ("{", "}")):
        if text.count(opening) != text.count(closing):
            raise RuntimeError(f"unbalanced {opening}{closing} in candidate R: {asset_id}")
    if text.count("'") % 2 or text.count('"') % 2:
        raise RuntimeError(f"unbalanced string delimiters in candidate R: {asset_id}")
    return True


def run_checked(command: list[str]) -> str:
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    return completed.stdout


def pdf_text(path: Path) -> str:
    return run_checked(["pdftotext", "-layout", str(path), "-"])


def numeric_tokens(text: str) -> list[str]:
    return re.findall(r"(?<![A-Za-z])(?:\d+\.\d+|\d+)(?![A-Za-z])", text)


def render_pdf(path: Path, out_png: Path) -> None:
    out_png.parent.mkdir(parents=True, exist_ok=True)
    prefix = out_png.with_suffix("")
    run_checked(["pdftoppm", "-f", "1", "-singlefile", "-r", "180", "-png", str(path), str(prefix)])
    if not out_png.is_file():
        raise RuntimeError(f"render missing: {out_png}")


def build_contact_sheet(rows: list[tuple[str, Path, Path]], output: Path) -> None:
    font = ImageFont.load_default()
    prepared: list[tuple[str, Image.Image, Image.Image]] = []
    max_w = 0
    total_h = 20
    for asset_id, source_png, target_png in rows:
        source = Image.open(source_png).convert("RGB")
        target = Image.open(target_png).convert("RGB")
        max_w = max(max_w, source.width + target.width + 30)
        total_h += max(source.height, target.height) + 38
        prepared.append((asset_id, source, target))
    canvas = Image.new("RGB", (max_w + 20, total_h), "white")
    draw = ImageDraw.Draw(canvas)
    y = 10
    for asset_id, source, target in prepared:
        draw.text((10, y), f"{asset_id}: source-en (left) | id-ID (right)", fill="black", font=font)
        y += 20
        canvas.paste(source, (10, y))
        canvas.paste(target, (20 + source.width, y))
        y += max(source.height, target.height) + 18
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, format="PNG", optimize=False)


def main() -> None:
    source_root = ROOT / "source-en"
    target_root = ROOT / "id-ID"
    visual_root = ROOT / "visual"
    receipt_root = ROOT / "receipts"
    for directory in (source_root, target_root, visual_root, receipt_root, ROOT / "tex"):
        directory.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, object]] = []
    contact_rows: list[tuple[str, Path, Path]] = []
    for asset_id in sorted(FIGURES):
        spec = FIGURES[asset_id]
        rel_dir = Path(str(spec["rel_dir"]))
        source_dir = REPO / "ch_probability" / "figures" / rel_dir
        authority_dir = AUTHORITY / "ch_probability" / "figures" / rel_dir
        source_r = source_dir / f"{asset_id}.R"
        source_pdf = source_dir / f"{asset_id}.pdf"
        authority_r = authority_dir / f"{asset_id}.R"
        authority_pdf = authority_dir / f"{asset_id}.pdf"
        if sha256(source_r) != spec["source_r_sha256"] or sha256(authority_r) != spec["source_r_sha256"]:
            raise RuntimeError(f"R authority/current identity mismatch: {asset_id}")
        if sha256(source_pdf) != spec["source_pdf_sha256"] or sha256(authority_pdf) != spec["source_pdf_sha256"]:
            raise RuntimeError(f"PDF authority/current identity mismatch: {asset_id}")

        witness_dir = source_root / rel_dir
        candidate_dir = target_root / rel_dir
        witness_dir.mkdir(parents=True, exist_ok=True)
        candidate_dir.mkdir(parents=True, exist_ok=True)
        witness_r = witness_dir / source_r.name
        witness_pdf = witness_dir / source_pdf.name
        candidate_r = candidate_dir / source_r.name
        candidate_pdf = candidate_dir / source_pdf.name
        shutil.copyfile(source_r, witness_r)
        shutil.copyfile(source_pdf, witness_pdf)
        write_text(candidate_r, str(spec["r_source"]))
        r_static_syntax_sanity = validate_r_candidate(
            candidate_r.read_text(encoding="utf-8"), asset_id
        )

        with pikepdf.open(witness_pdf) as pdf:
            if len(pdf.pages) != 1:
                raise RuntimeError(f"expected one page: {asset_id}")
            page = pdf.pages[0]
            actual_box = [float(value) for value in page.MediaBox]
            if actual_box != spec["media_box"]:
                raise RuntimeError(f"MediaBox mismatch for {asset_id}: {actual_box}")
            stream = page.Contents.read_bytes()
            label_map: list[dict[str, str]] = []
            for source_bytes, target_bytes, source_label, target_label in spec["replacements"]:
                if stream.count(source_bytes) != 1:
                    raise RuntimeError(f"declared source text run not unique for {asset_id}: {source_label}")
                stream = stream.replace(source_bytes, target_bytes, 1)
                label_map.append({"source": source_label, "id_ID": target_label})
            page.Contents.write(stream)
            pdf.save(
                candidate_pdf,
                deterministic_id=True,
                compress_streams=True,
                recompress_flate=True,
                object_stream_mode=pikepdf.ObjectStreamMode.disable,
            )

        source_text = pdf_text(witness_pdf)
        target_text = pdf_text(candidate_pdf)
        numeric_exact = Counter(numeric_tokens(source_text)) == Counter(numeric_tokens(target_text))
        residuals = [
            term
            for term in spec["forbidden"]
            if re.search(
                rf"(?<![A-Za-z]){re.escape(term)}(?![A-Za-z])",
                target_text,
                flags=re.IGNORECASE,
            )
        ]
        missing_targets = [term for term in spec["required"] if term.lower() not in target_text.lower()]
        if not numeric_exact or residuals or missing_targets:
            raise RuntimeError(
                f"text QA failed for {asset_id}: numeric={numeric_exact}, residuals={residuals}, missing={missing_targets}"
            )

        source_png = visual_root / "source-en" / f"{asset_id}.png"
        target_png = visual_root / "id-ID" / f"{asset_id}.png"
        render_pdf(witness_pdf, source_png)
        render_pdf(candidate_pdf, target_png)
        with Image.open(source_png) as source_image, Image.open(target_png) as target_image:
            same_raster_dimensions = source_image.size == target_image.size
        if not same_raster_dimensions:
            raise RuntimeError(f"raster dimension mismatch: {asset_id}")
        contact_rows.append((asset_id, source_png, target_png))

        records.append(
            {
                "asset_id": asset_id,
                "repository_relative_directory": f"ch_probability/figures/{rel_dir.as_posix()}",
                "source_and_current_identical": True,
                "source_r": {"bytes": source_r.stat().st_size, "sha256": sha256(source_r)},
                "source_pdf": {"bytes": source_pdf.stat().st_size, "sha256": sha256(source_pdf)},
                "candidate_r": {"path": candidate_r.relative_to(ROOT).as_posix(), "bytes": candidate_r.stat().st_size, "sha256": sha256(candidate_r), "execution_status": "not_executed_Rscript_absent", "static_syntax_sanity": r_static_syntax_sanity},
                "candidate_pdf": {"path": candidate_pdf.relative_to(ROOT).as_posix(), "bytes": candidate_pdf.stat().st_size, "sha256": sha256(candidate_pdf), "derivation": "exact_declared_content_stream_substitution"},
                "english_witnesses": {"r": witness_r.relative_to(ROOT).as_posix(), "pdf": witness_pdf.relative_to(ROOT).as_posix()},
                "visible_label_map": label_map,
                "numeric_tokens_preserved_as_multiset": numeric_exact,
                "page_geometry_preserved": True,
                "render_dimensions_preserved": same_raster_dimensions,
                "render_sha256": {"source": sha256(source_png), "id_ID": sha256(target_png)},
                "r_dependencies": {
                    "package": "openintro",
                    "version": "not pinned by upstream producer and unavailable locally",
                    "symbols": ["COL"] + (["treeDiag"] if asset_id != "photoClassifyVenn" else []) + (["myPDF"] if asset_id in {"smallpoxTreeDiagram", "testTree", "treeDiagramAndPass", "BreastCancerTreeDiagram", "treeDiagramGarage"} else []),
                    "base_graphics": ["pdf", "par", "plot", "rect", "text", "dev.off"] if asset_id == "photoClassifyVenn" else ["pdf", "dev.off"],
                    "data_files_read": [],
                },
                "data_provenance": spec["data_provenance"],
                "rights": RIGHTS,
            }
        )

    research_source = REPO / "ch_probability" / "figures" / "BreastCancerTreeDiagram" / "Mammogram Research.txt"
    research_authority = AUTHORITY / "ch_probability" / "figures" / "BreastCancerTreeDiagram" / "Mammogram Research.txt"
    expected_research_hash = "f9e6745d04ab99f05f48cf9d408a97dc573a38195c8e16c2ff021f7c3dbd9964"
    if sha256(research_source) != expected_research_hash or sha256(research_authority) != expected_research_hash:
        raise RuntimeError("Mammogram Research.txt authority/current identity mismatch")
    research_witness = source_root / "BreastCancerTreeDiagram" / "Mammogram Research.txt"
    shutil.copyfile(research_source, research_witness)
    research_summary = """# Catatan asal data mamogram (kandidat id-ID)\n+\n+- Berkas sumber dipertahankan tanpa perubahan di `source-en/BreastCancerTreeDiagram/Mammogram Research.txt`.\n+- Catatan sumber menghubungkan sensitivitas 89% dan angka positif palsu 7,4% ke halaman Breastcancer.org lama, serta prevalensi tahunan 0,35% ke PMC1173421.\n+- Produser gambar dan teks buku memakai 7%, bukan 7,4%; ini dicatat sebagai perbedaan pembulatan/asal data dan tidak diubah diam-diam.\n+- Tautan UCSF, Komen, ACP, dan Wikipedia di catatan merupakan jejak riset tambahan; tidak ada data eksternal yang diunduh atau dibundel untuk batas ini.\n+- Catatan sumber mengandung salah ketik `resulte`; karena berkas ini adalah saksi upstream, salah ketik itu tetap dipertahankan pada salinan sumber.\n+"""
    research_summary_path = target_root / "BreastCancerTreeDiagram" / "Mammogram Research.provenance-id.md"
    write_text(research_summary_path, research_summary)

    tex_source_identities: dict[str, dict[str, object]] = {}
    alt_records: list[dict[str, object]] = []
    for tex_rel in sorted({value["tex_path"] for value in ALT_TEXT.values()}):
        current_path = REPO / tex_rel
        authority_path = AUTHORITY / tex_rel
        tex_source_identities[tex_rel] = {
            "authority": {"bytes": authority_path.stat().st_size, "sha256": sha256(authority_path)},
            "current": {"bytes": current_path.stat().st_size, "sha256": sha256(current_path)},
        }
    for asset_id in sorted(ALT_TEXT):
        spec = ALT_TEXT[asset_id]
        authority_text = (AUTHORITY / spec["tex_path"]).read_text(encoding="utf-8")
        current_text = (REPO / spec["tex_path"]).read_text(encoding="utf-8")
        pattern = SOURCE_ALT_PATTERNS[asset_id]
        authority_matches = pattern.findall(authority_text)
        current_matches = pattern.findall(current_text)
        if len(authority_matches) != 1 or len(current_matches) != 1:
            raise RuntimeError(f"alt text lookup not unique for {asset_id}")
        if authority_matches[0] != current_matches[0]:
            raise RuntimeError(f"relevant alt text changed from authority for {asset_id}")
        alt_records.append(
            {
                "asset_id": asset_id,
                "tex_path": spec["tex_path"],
                "macro": spec["macro"],
                "macro_tail": spec["macro_tail"],
                "source_en": authority_matches[0],
                "current_equals_source_for_relevant_alt_text": True,
                "id_ID": spec["id_ID"],
            }
        )

    alt_mapping_path = ROOT / "tex" / "R011-B010_ALT_TEXT_MAPPING.json"
    write_text(
        alt_mapping_path,
        json.dumps(
            {"schema": "r011-b010-alt-text-mapping", "schema_version": "1.0.0", "records": alt_records},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
    )
    candidate_lines = [
        "% R011-B010 ready-to-integrate Indonesian alternative-text candidates.",
        "% Generated from the pinned/source-equal alt text recorded in R011-B010_ALT_TEXT_MAPPING.json.",
        "",
    ]
    for record in alt_records:
        candidate_lines.extend(
            [
                f"% {record['asset_id']} -- {record['tex_path']}",
                f"\\{record['macro']}[{record['id_ID']}]{record['macro_tail']}",
                "",
            ]
        )
    candidate_tex_path = ROOT / "tex" / "R011-B010_ALT_TEXT_CANDIDATES.tex"
    write_text(candidate_tex_path, "\n".join(candidate_lines))

    contact_sheet = visual_root / "R011-B010_SOURCE_VS_ID_CONTACT_SHEET.png"
    build_contact_sheet(contact_rows, contact_sheet)

    controlled_vocabulary = [
        {"source_en": "conditional probability", "id_ID": "peluang bersyarat", "scope": "concept"},
        {"source_en": "marginal probability", "id_ID": "peluang marginal", "scope": "concept"},
        {"source_en": "joint probability", "id_ID": "peluang bersama", "scope": "concept and alt text"},
        {"source_en": "tree diagram", "id_ID": "diagram pohon", "scope": "concept and visible label"},
        {"source_en": "Bayes' Theorem", "id_ID": "Teorema Bayes", "scope": "concept"},
        {"source_en": "primary branch", "id_ID": "cabang utama", "scope": "alt text"},
        {"source_en": "secondary branch", "id_ID": "cabang sekunder", "scope": "alt text"},
        {"source_en": "Midterm", "id_ID": "UTS", "scope": "visible label; underlying variable identity remains midterm"},
        {"source_en": "Final", "id_ID": "UAS", "scope": "visible label; underlying variable identity remains final"},
        {"source_en": "Pass class", "id_ID": "Lulus mata kuliah", "scope": "visible label"},
        {"source_en": "yes / no", "id_ID": "ya / tidak", "scope": "visible outcomes"},
        {"source_en": "Result", "id_ID": "Hasil", "scope": "visible label"},
    ]
    vocabulary_rows = ["source_en\tid_ID\tscope"]
    for term in controlled_vocabulary:
        vocabulary_rows.append(f"{term['source_en']}\t{term['id_ID']}\t{term['scope']}")
    for record in records:
        for mapping in record["visible_label_map"]:
            vocabulary_rows.append(
                f"{mapping['source']}\t{mapping['id_ID']}\tfigure:{record['asset_id']}"
            )
    label_vocabulary_path = ROOT / "R011-B010_LABEL_VOCABULARY.tsv"
    write_text(label_vocabulary_path, "\n".join(vocabulary_rows) + "\n")

    manifest = {
        "schema": "r011-b010-asset-code-data-closure",
        "schema_version": "1.0.0",
        "boundary_id": "R011-B010",
        "locale": "id-ID",
        "status": "candidate_isolated_not_admitted",
        "authority": AUTHORITY_ID,
        "scope": {
            "figure_pair_count": len(records),
            "research_note_count": 1,
            "alt_text_record_count": len(alt_records),
            "canonical_files_modified": 0,
        },
        "assets": records,
        "controlled_vocabulary": {
            "terms": controlled_vocabulary,
            "full_visible_label_table": {
                "path": label_vocabulary_path.relative_to(ROOT).as_posix(),
                "bytes": label_vocabulary_path.stat().st_size,
                "sha256": sha256(label_vocabulary_path),
            },
        },
        "research_note": {
            "path": "ch_probability/figures/BreastCancerTreeDiagram/Mammogram Research.txt",
            "source_and_current_identical": True,
            "bytes": research_source.stat().st_size,
            "sha256": sha256(research_source),
            "witness": research_witness.relative_to(ROOT).as_posix(),
            "provenance_summary": research_summary_path.relative_to(ROOT).as_posix(),
            "rights": RIGHTS,
            "source_quality_flags": [
                "legacy HTTP links are research-note pointers rather than bundled evidence",
                "7.4% false-positive statement is rounded to 7% in producer and reader text",
                "source-note typo `resulte` preserved in witness",
            ],
        },
        "tex_sources": tex_source_identities,
        "alt_text_mapping": {
            "path": alt_mapping_path.relative_to(ROOT).as_posix(),
            "bytes": alt_mapping_path.stat().st_size,
            "sha256": sha256(alt_mapping_path),
            "candidate_tex_path": candidate_tex_path.relative_to(ROOT).as_posix(),
            "candidate_tex_bytes": candidate_tex_path.stat().st_size,
            "candidate_tex_sha256": sha256(candidate_tex_path),
        },
        "toolchain": {
            "builder": {
                "path": Path(__file__).relative_to(ROOT).as_posix(),
                "bytes": Path(__file__).stat().st_size,
                "sha256": sha256(Path(__file__)),
            },
            "pdf_derivation": f"pikepdf {pikepdf.__version__}",
            "text_extraction": "pdftotext",
            "rendering": "pdftoppm 180 dpi",
            "rscript": "absent; candidate R scripts statically prepared but not executed",
        },
        "rights_closure": {
            "all_scoped_repository_components": RIGHTS,
            "openintro_R_package": "External build dependency, not bundled; version and exact component license are not pinned by the figure producers.",
            "external_research_links": "Cited as provenance pointers only; no external page or dataset bytes are redistributed.",
        },
        "blockers": [
            "Rscript and the openintro R package are absent, so localized producer replay remains unverified.",
            "Standalone PDFs are untagged; translated surrounding TeX alternative text must remain the accessibility layer.",
            "Mammogram Research.txt has legacy links and a 7.4%-versus-7% discrepancy; preserve the committed 7% math unless editorial source revalidation is separately authorized.",
        ],
    }
    manifest_path = ROOT / "R011-B010_ASSET_CODE_DATA_CLOSURE.json"
    write_text(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")

    inventory_rows = [
        "asset_id\tsource_r_bytes\tsource_r_sha256\tsource_pdf_bytes\tsource_pdf_sha256\tcandidate_r_bytes\tcandidate_r_sha256\tcandidate_pdf_bytes\tcandidate_pdf_sha256\tnumeric_tokens_preserved\tpage_geometry_preserved"
    ]
    for record in records:
        inventory_rows.append(
            "\t".join(
                [
                    str(record["asset_id"]),
                    str(record["source_r"]["bytes"]),
                    str(record["source_r"]["sha256"]),
                    str(record["source_pdf"]["bytes"]),
                    str(record["source_pdf"]["sha256"]),
                    str(record["candidate_r"]["bytes"]),
                    str(record["candidate_r"]["sha256"]),
                    str(record["candidate_pdf"]["bytes"]),
                    str(record["candidate_pdf"]["sha256"]),
                    str(record["numeric_tokens_preserved_as_multiset"]).lower(),
                    str(record["page_geometry_preserved"]).lower(),
                ]
            )
        )
    inventory_path = ROOT / "R011-B010_ASSET_INVENTORY.tsv"
    write_text(inventory_path, "\n".join(inventory_rows) + "\n")

    receipt = {
        "schema": "r011-b010-asset-qa-receipt",
        "schema_version": "1.0.0",
        "boundary_id": "R011-B010",
        "status": "PASS_CANDIDATE_ISOLATED_WITH_R_REPLAY_BLOCKED",
        "authority": AUTHORITY_ID,
        "checks": {
            "authority_current_identity_17_of_17": True,
            "figure_pairs_built": 8,
            "declared_content_replacements_unique": True,
            "numeric_token_multisets_preserved_8_of_8": True,
            "media_boxes_preserved_8_of_8": True,
            "raster_dimensions_preserved_8_of_8": True,
            "declared_English_labels_absent_8_of_8": True,
            "declared_id_ID_labels_present_8_of_8": True,
            "relevant_alt_text_source_equal_8_of_8": True,
            "candidate_R_static_syntax_sanity_8_of_8": True,
            "canonical_files_modified": 0,
            "r_replay": False,
        },
        "artifacts": {
            "manifest": {"path": manifest_path.relative_to(ROOT).as_posix(), "bytes": manifest_path.stat().st_size, "sha256": sha256(manifest_path)},
            "builder": {"path": Path(__file__).relative_to(ROOT).as_posix(), "bytes": Path(__file__).stat().st_size, "sha256": sha256(Path(__file__))},
            "inventory": {"path": inventory_path.relative_to(ROOT).as_posix(), "bytes": inventory_path.stat().st_size, "sha256": sha256(inventory_path)},
            "alt_mapping": {"path": alt_mapping_path.relative_to(ROOT).as_posix(), "bytes": alt_mapping_path.stat().st_size, "sha256": sha256(alt_mapping_path)},
            "candidate_tex": {"path": candidate_tex_path.relative_to(ROOT).as_posix(), "bytes": candidate_tex_path.stat().st_size, "sha256": sha256(candidate_tex_path)},
            "label_vocabulary": {"path": label_vocabulary_path.relative_to(ROOT).as_posix(), "bytes": label_vocabulary_path.stat().st_size, "sha256": sha256(label_vocabulary_path)},
            "contact_sheet": {"path": contact_sheet.relative_to(ROOT).as_posix(), "bytes": contact_sheet.stat().st_size, "sha256": sha256(contact_sheet)},
        },
        "blocker": "Rscript/openintro unavailable; derived id-ID PDFs were deterministically localized from pinned PDF witnesses and candidate R producers await replay.",
    }
    receipt_path = receipt_root / "R011-B010_ASSET_QA_RECEIPT.json"
    write_text(receipt_path, json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "figure_pairs": len(records),
                "manifest": {"path": str(manifest_path), "bytes": manifest_path.stat().st_size, "sha256": sha256(manifest_path)},
                "inventory": {"path": str(inventory_path), "bytes": inventory_path.stat().st_size, "sha256": sha256(inventory_path)},
                "receipt": {"path": str(receipt_path), "bytes": receipt_path.stat().st_size, "sha256": sha256(receipt_path)},
                "contact_sheet": {"path": str(contact_sheet), "bytes": contact_sheet.stat().st_size, "sha256": sha256(contact_sheet)},
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
