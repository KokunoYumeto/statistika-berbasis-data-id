# SPDX-License-Identifier: GPL-3.0-only
# Helper pemutaran ulang untuk gambar batas R011-B003.
# Palet ini dibekukan dari objek data COL pada paket openintro,
# commit 48793d9645e0da033daaca1c1a19a051533d79d2.
# Implementasi minimal myPDF dan AxisInPercent berasal dari paket yang sama.

COL <- structure(
  c(
    "#569BBD", "#4C721D", "#F4DC00", "#F05133", "#000000", "#808080", "#D9D9D9",
    "#569BBDC0", "#4C721DC0", "#F4DC00C0", "#F05133C0", "#000000C0", "#808080C0", "#D9D9D9C0",
    "#569BBD80", "#4C721D80", "#F4DC0080", "#F0513380", "#00000080", "#80808080", "#D9D9D980",
    "#569BBD40", "#4C721D40", "#F4DC0040", "#F0513340", "#00000040", "#80808040", "#D9D9D940",
    "#569BBD30", "#4C721D30", "#F4DC0030", "#F0513330", "#00000030", "#80808030", "#D9D9D930",
    "#569BBD20", "#4C721D20", "#F4DC0020", "#F0513320", "#00000020", "#80808020", "#D9D9D920",
    "#569BBD18", "#4C721D18", "#F4DC0018", "#F0513318", "#00000018", "#80808018", "#D9D9D918",
    "#569BBD10", "#4C721D10", "#F4DC0010", "#F0513310", "#00000010", "#80808010", "#D9D9D910",
    "#569BBD0A", "#4C721D0A", "#F4DC000A", "#F051330A", "#0000000A", "#8080800A", "#D9D9D90A",
    "#569BBD08", "#4C721D08", "#F4DC0008", "#F0513308", "#00000008", "#80808008", "#D9D9D908",
    "#569BBD06", "#4C721D06", "#F4DC0006", "#F0513306", "#00000006", "#80808006", "#D9D9D906",
    "#569BBD04", "#4C721D04", "#F4DC0004", "#F0513304", "#00000004", "#80808004", "#D9D9D904",
    "#569BBD02", "#4C721D02", "#F4DC0002", "#F0513302", "#00000002", "#80808002", "#D9D9D902"
  ),
  dim = c(7L, 13L),
  dimnames = list(
    c("blue", "green", "yellow", "red", "black", "gray", "lgray"),
    c("full", "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10", "f11", "f12")
  )
)

# Pertahankan perilaku pengambilan sampel R yang digunakan oleh sumber lama.
use_legacy_rng <- function() {
  suppressWarnings(RNGversion("3.5.3"))
}

# Padanan mandiri fungsi openintro::myPDF dengan parameter asli.
myPDF <- function(fileName,
                  width = 5,
                  height = 3,
                  mar = c(3.9, 3.9, 1, 1),
                  mgp = c(2.8, 0.55, 0),
                  las = 1,
                  tcl = -0.3,
                  ...) {
  grDevices::pdf(fileName, width, height)
  graphics::par(mar = mar, mgp = mgp, las = las, tcl = tcl, ...)
}

# Padanan mandiri openintro::AxisInPercent.
AxisInPercent <- function(side, at, include.symbol = TRUE, ...) {
  labels <- at
  if (include.symbol) {
    labels <- paste0(labels, "%")
  }
  axis(side, at, labels, ...)
}
