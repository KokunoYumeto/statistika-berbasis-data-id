# R011-B008 visual QA receipt

Status: PASS

Inspection basis: every English witness and final Indonesian target was rendered at 216 dpi with Poppler 25.07.0 and MuPDF 1.23.0. All 24 current source/target renderings were inspected at their original pixel dimensions. Pass-1 and pass-2 target render bytes are identical within each engine.

| Figure | Centering and clipping | Overlap and legibility | Data fidelity | English residue |
|---|---|---|---|---|
| infant_mortality_rel_freq_hist | Both Indonesian axis labels are centered in their inherited regions and fully inside the page. | No collisions with ticks, grid, or bars. | All 12 bins, relative-frequency ticks, grid lines, axes, and colors match the witness. | None. |
| oscars_winners_hist | Facet labels remain left aligned; the x label is centered and fully visible. | No label/bar/grid overlap. | Both histogram panels, bin boundaries, heights, axes, and colors match the witness. | None. |
| marathon_winners_hist_box | The source clipping rectangle fully suppressed its intended vertical label. The target removes clipping only for that text block, preserving its intended origin; Waktu maraton is now visible and centered in the panel gap. | No collision with either panel or tick labels. | Histogram bins, box, whiskers, outliers, axes, and colors are unchanged. | None. |
| marathon_winners_gender_box | Wanita and Pria remain right aligned within the inherited left margin. | No clipping or collision with the bracket, boxes, or axis. | Both boxes, whiskers, outliers, ticks, and colors match the witness. | None. |
| marathon_winners_time_series | The y label and legend fit their inherited regions. | No legend or axis overlap. | All green cross marks are unchanged. Thirty blue data circles plus the blue legend circle were converted from an unembedded font glyph to the exact explicit vector outline and are visible in both renderers. | None. |
| stats_scores_boxplot | Nilai is centered and fully visible. | No label/axis overlap. | Box, median, whiskers, ticks, and the low outlier are unchanged; the outlier is now an explicit vector and visible in both renderers. | None. |

The localized targets show no clipped intended text, unintended overlap, missing data mark, raster defect, or visible English label.
