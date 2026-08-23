RNGversion("3.5.3")
set.seed(2)

n <- 6L * 9L
risk <- sample(
  c("low", "high"),
  n,
  replace = TRUE,
  prob = c(0.8, 1.2)
)
stopifnot(
  length(risk) == 54L,
  sum(risk == "low") == 22L,
  sum(risk == "high") == 32L
)

# Retain the pinned upstream random-number consumption before allocation.
marker_cex <- rnorm(n, 1, 0.001)
allocation <- rep(NA_character_, n)
for (risk_level in c("low", "high")) {
  members <- which(risk == risk_level)
  allocation[sample(members, length(members) / 2L)] <- "control"
  allocation[is.na(allocation) & risk == risk_level] <- "treatment"
}
stopifnot(
  sum(risk == "low" & allocation == "control") == 11L,
  sum(risk == "low" & allocation == "treatment") == 11L,
  sum(risk == "high" & allocation == "control") == 16L,
  sum(risk == "high" & allocation == "treatment") == 16L
)

low_colour <- "#C43C39"
high_colour <- "#2468A2"
frame_colour <- "#3B4A5A"
group_colour <- "#325D88"

draw_patient <- function(x, y, i, number_offset = -0.018) {
  is_low <- risk[i] == "low"
  points(
    x,
    y,
    pch = if (is_low) 21 else 24,
    cex = marker_cex[i],
    col = if (is_low) low_colour else high_colour,
    bg = if (is_low) "white" else high_colour,
    lwd = 0.9
  )
  text(
    x,
    y + number_offset,
    i,
    cex = 0.45,
    pos = 3,
    col = if (is_low) low_colour else high_colour
  )
}

grDevices::pdf(
  "figureShowingBlocking.pdf",
  width = 4,
  height = 7,
  onefile = FALSE,
  paper = "special",
  family = "Helvetica",
  title = "Pemblokan pasien berdasarkan risiko",
  useDingbats = FALSE,
  version = "1.4"
)
par(mar = rep(0, 4), xaxs = "i", yaxs = "i")
plot.new()
plot.window(xlim = c(-0.1, 1.1), ylim = c(-0.05, 3.06))

rect(0, 2.20, 1, 2.90, border = frame_colour)
text(0.5, 2.98, "Pasien bernomor", cex = 0.83)

rect(0, 1.20, 0.45, 1.90, border = frame_colour)
rect(0.55, 1.20, 1, 1.90, border = frame_colour)
arrows(0.56, 2.17, 0.75, 2.02, length = 0.08, lwd = 1.25)
arrows(0.44, 2.17, 0.25, 2.02, length = 0.08, lwd = 1.25)
text(0.5, 2.08, "bentuk\nblok", cex = 0.72)
text(0.225, 1.96, "Pasien berisiko rendah", cex = 0.61)
text(0.775, 1.96, "Pasien berisiko tinggi", cex = 0.61)

rect(0, 0.48, 1, 0.90, border = group_colour)
rect(0, 0.00, 1, 0.42, border = group_colour)
arrows(0.09, 1.16, 0.09, 1.00, length = 0.08, lwd = 1.25)
text(0.10, 1.09, "bagi dua\nsecara acak", cex = 0.62, pos = 4)
arrows(0.67, 1.16, 0.67, 1.00, length = 0.08, lwd = 1.25)
text(0.68, 1.09, "bagi dua\nsecara acak", cex = 0.62, pos = 4)

slim_box <- 0.03
rect(0.02, 0.50, 0.41, 0.88, border = group_colour)
rect(0.02, 0.02, 0.41, 0.40, border = group_colour)
rect(0.57 + slim_box, 0.50, 0.98, 0.88, border = group_colour)
rect(0.57 + slim_box, 0.02, 0.98, 0.40, border = group_colour)

rect(-0.05, 0.86, 0.14, 0.92, col = "white", border = group_colour)
text(0.045, 0.894, "Kontrol", cex = 0.57, col = group_colour)
rect(-0.05, 0.39, 0.16, 0.45, col = "white", border = group_colour)
text(0.055, 0.424, "Perlakuan", cex = 0.55, col = group_colour)

k <- 0L
for (x in seq(0.1, 0.9, length.out = 9)) {
  for (y in rev(seq(0.3, 0.8, length.out = 6))) {
    k <- k + 1L
    draw_patient(x, y + 2, k)
  }
}

members <- which(risk == "low")
x <- 0.078
y <- 1.83
for (i in members) {
  draw_patient(x, y, i, number_offset = -0.02)
  if (y < 1.3) {
    x <- x + 0.095
    y <- 1.83
  } else {
    y <- y - 0.11
  }
}

members <- which(risk == "high")
x <- 0.615
y <- 1.82
for (i in members) {
  draw_patient(x, y, i, number_offset = -0.02)
  if (y < 1.3) {
    x <- x + 0.08
    y <- 1.83
  } else {
    y <- y - 0.095
  }
}

count_in_box <- integer(4)
x <- c(0.10, 0.10, 0.665, 0.665)
# Boxes 1 and 3 are control (upper); boxes 2 and 4 are treatment (lower).
y <- c(0.83, 0.35, 0.83, 0.35) - 0.03
for (i in seq_len(n)) {
  box <- 1L
  if (allocation[i] == "treatment") {
    box <- box + 1L
  }
  if (risk[i] == "high") {
    box <- box + 2L
  }
  count_in_box[box] <- count_in_box[box] + 1L
  draw_patient(x[box], y[box], i, number_offset = -0.02)
  if (y[box] < 0.12 + 0.51 * (box %in% c(1L, 3L)) - 0.03) {
    x[box] <- x[box] + 0.11 - ifelse(box > 2L, 0.025, 0)
    y[box] <- 0.35 + ifelse(box %in% c(1L, 3L), 0.48, 0) - 0.03
  } else {
    y[box] <- y[box] - 0.085
  }
}
stopifnot(identical(count_in_box, c(11L, 11L, 16L, 16L)))

invisible(dev.off())
