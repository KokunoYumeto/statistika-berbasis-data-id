# Decision log

## D001 — Canonical source identity

Use commit `fee25091fb24e89c36296fd67c48c1fcf7a93b6e` and tree `d61cc601e7d97759ce805900520f784d02a0489e`. Codeload ZIP SHA-256 is observational because archive packaging may vary; the extracted file manifest and Git tree bind content.

## D002 — Derivative title and attribution

Use the novel Indonesian title **Statistika Berbasis Data**. Identify the source work separately as “Turunan dari (Derivative of) OpenIntro Statistics, Edisi Keempat.” Do not translate the protected source title into a derivative title, use logos, or imply endorsement.

## D003 — Component-rights precedence

CC BY-SA 3.0 Unported is the default for the authored textbook text only. Exact file-level or nearest-component rights override it. Unknown rights remain unresolved and exclude the component from publication.

## D004 — Acupuncture illustration

Exclude `earacupuncture.pdf` from the derivative reader and publication closure. It is an extracted figure from a third-party paper with no adjacent open license. Replace its pedagogical function with independently written text/native layout while retaining the statistical question and table.

## D005 — Public-answer boundary

Translate the guided-practice answer and upstream public odd-numbered appendix answer. Exercise 1.2 has `none_public_upstream`; create an O001 gap record. Do not seek or reconstruct teacher-only solutions.

## D006 — Build portability correction

Replace only pre-document `\include` calls with `\input`, because current LaTeX rejects `\include` before `\begin{document}`. Preserve content and record the delta as an upstream build portability correction.

## D007 — Backend identity

Stable backend IDs are locale-neutral and persist independently of paths, hashes, titles, or translated strings. Source labels seed first-import mappings but never cause later identity churn.

## D008 — Upstream style syntax correction

Remove the lone opening brace immediately before `\eocesol` in `extraTeX/style/style.tex`. The brace has no matching close, leaves the document in a simple group, and causes current LaTeX begin-document hooks to fail. The correction changes grouping only; the exercise/solution counter and link macros remain otherwise unchanged.

## D009 — Deterministic boundary builds

Set `SOURCE_DATE_EPOCH=1787184000` and `FORCE_SOURCE_DATE=1` for the R011-B001 build. Admission requires two consecutive final LaTeX passes to produce the same SHA-256. The epoch corresponds to the frozen production date, not an upstream-commit timestamp claim.

## D010 — PDF language metadata is additive, not accessibility completion

Set the derivative title, original authors, subject, keywords, and `/Lang (id-ID)` in the PDF. Retain the explicit limitation that the current pdfTeX artifact is untagged; language metadata does not substitute for structural tagging or an accessible HTML reader.

## D011 — Generated figures are localized data-first

Localize generated figures from frozen source data and deterministic producers, never by painting translated labels over a raster. R011-B002 carries six localized figures. Four vector figures replay their preserved non-text drawing instructions; the airport and UN-vote rasters replay exact frozen package/data authorities with explicit toolchain, semantic, and two-pass hash checks. File-level rights and source acknowledgments remain attached to each component.

## D012 — Public answers may receive source-backed corrections

Translate only answers that the upstream public edition exposes. When the public answer is internally inconsistent with its own exercise or data, preserve the exercise relation and correct the answer transparently in the derivative, with a typed adverse-ledger record. This does not authorize access to, reconstruction of, or invention of answers for the even-numbered O001 gaps.

## D013 — Local layout deltas must preserve pedagogical topology

Reader-flow corrections may remove a print-only forced page break, replace list-glue wrappers with topology-neutral centering, or adjust figure scale when the full text, task, accessibility description, asset path, ID, mathematics, and answer relation remain unchanged. R011-B002 uses this rule to eliminate a nearly blank orphan page while retaining both dense exercise figures legibly at 0.85 text width.

## D014 — Generated cross-reference prose is part of localization

Localize the `varioref` page-reference phrases in the document preamble rather than patching rendered output. R011-B002 therefore renders phrases such as `di halaman sebelah` and `di halaman berikutnya` while preserving every label, reference target, and page number. The same hooks apply consistently to later translated units.

## D015 — Third-party quoted expression is not imported into the reusable layer

For R011-B003, retain citations, article identities, factual study content, numerical results, and inference questions, but replace unlicensed Hepler/Albarracín, New York Times, and Jon Stewart wording with independently structured Indonesian summaries or paraphrases. This keeps the pedagogical task and attribution while avoiding a translated reproduction of third-party expression inside the CC BY-SA derivative.

## D016 — Correct source-backed sampling claims at the reader layer

R011-B003 corrects mathematically or inferentially determined source defects rather than translating them verbatim: a simple random sample of fixed size gives every possible sample of that size equal probability; prospective and retrospective studies are two common observational forms, not the only forms; generalization is limited to the represented sampling-frame population; and multistage-sampling bias depends on inclusion probabilities, weighting, and nonresponse rather than class similarity alone. Stable labels, exercise identities, and factual data remain unchanged.

## D017 — B003 figures remain code-native and reproducible

Localize the seven R011-B003 generated figures through their source data and R drawing programs, not through raster overlays. Preserve population/sample geometry, sampling selections, colors, data order, media boxes, the frozen CIA Factbook input, and the unchanged David M. Diez photograph. Bind the localized outputs and producer closure in `ch_intro_to_data/figures/B003_FIGURE_REPLAY.json`; retain GPL-3.0-only OpenIntro R helpers as a separately governed build dependency rather than relicensing them under the book's CC BY-SA layer.

## D018 — B004 blocking figure uses a source-equivalent vector replay

Retain a self-contained canonical R producer with the frozen R 3.5.3 random-number semantics, seed 2, portable vector markers, and the corrected control/treatment mapping. Because no R runtime was available at the B004 replay boundary, generate the admitted PDF independently from the producer algorithm and exact seeded identities with a B004-specific Python vector renderer; do not use the authority PDF as input or paint translated labels over it. Admission requires exact assertions for all 54 patient identities and logical anchor coordinates, 22/32 risk counts, 11/11/16/16 allocations, the 288-by-504-point media box, absence of Symbol/Dingbats and raster image objects, and two byte-identical canonical outputs. The replay is not claimed to be operator-identical to base R's device expansion, typography, arrows, or marker radii; its equivalence claim is limited to the retained producer's logical data, topology, identities, and anchor coordinates. Bind the method, runtime versions, producer, output, and invariants in `figureShowingBlocking/R011-B004_FIGURE_REPLAY.json`.

## D019 — Close Chapter 1 review exercises before admitting Chapter 2

Treat the ten Chapter 1 review exercises 1.35–1.44 and their five upstream-public odd answers as the inserted source-order boundary R011-B004R. They were included only as untranslated layout witnesses in R011-B004 and therefore were not semantically admitted there. Preserve the already translated Chapter 2 Section 2.1 work as forward R011-B005 work, but do not admit B005 until B004R has translated its exercises and public answers, localized its two generated figures, passed source/build/visual/backend gates, and received a frozen receipt. Because forward B005 source and control rows already exist, B004R evidence must reconstruct from the admitted B004 snapshot and include only the explicit B004R overlays and selected correction rows.

## D020 — Reflow the complete Chapter 1 review without shrinking reader text

Keep the translated review in the admitted local layout group and reduce `eoceAfterSpace` from 2.5 mm to 0 mm without changing font size, line spacing, list typography, exercise order, labels, answers, mathematics, or figures. The first complete B004R build left all three parts of exercise 1.44 on a severely underfilled page; candidate v3 moved part (a) back but still orphaned parts (b)–(c), and candidate v4 proved that zeroing list-boundary glue had no pagination effect. Remove that ineffective override. Instead, tighten only genuinely verbose Indonesian wording in exercises 1.41–1.44, sentence for sentence, while preserving every fact, variable, number, inference claim, question, citation, and answer relation. Admission requires an independent semantic re-audit plus a fresh deterministic build and full-resolution visual proof that 1.44 completes before the Chapter 2 opener.

## D021 — Reflow B005 by omitting four print-only forced breaks

The first complete B005 build exposed three effectively blank continuation pages in the Section 2.1 body (pages 45, 48, and 50) and one in its exercises (page 61). Omit only the four corresponding `\D{\newpage}` directives: before Example 2.6, before Guided Practice 2.9, before the variance subsection, and between exercises 2.6 and 2.7. Retain every reader-visible word, formula, footnote, label, reference, exercise, answer, figure, font size, line spacing, and source order. Rebuild from a newly frozen source manifest and admit only after every B005 page is reinspected at full resolution with no clipping, overlap, severe underfill, centering defect, or new orphan.

## D022 — Continue B005 reflow at the box-plot subsection

The D021 rebuild repaired the four original continuation-page defects and the stacked-dot renderer failure, but pagination exposed one new severe underfill on page 50: Figure 2.9 and one short continuation paragraph occupied only the upper third because the box-plot subsection was still forced to the next page. Omit only the print-only `\D{\newpage}` immediately before `Diagram kotak, kuartil, dan median`. Retain every reader-visible word, formula, footnote, label, reference, exercise, answer, figure, font size, line spacing, and source order. Preserve the rejected v2 build and its full-page finding, refreeze the exact D022 source, and admit only after a new deterministic build and inspection of every newly rendered B005 page.

## D023 — Complete the cascading B005 subsection reflow

The D022 rebuild filled page 50 cleanly, but moving the box-plot subsection forward exposed the next inherited print break: page 52 ended after Guided Practice 2.16 with more than half the page empty because `Statistik robust` was forced to page 53. Omit that print-only `\D{\newpage}`. Because the robust subsection currently fills page 53 and the transformation subsection fills page 54, this omission necessarily moves the same underfill cascade to the still-hard breaks before `Mentransformasi data` and `Memetakan data`; omit those two print-only breaks in the same bounded reflow instead of commissioning two already-predictable rejected builds. Retain every reader-visible word, formula, footnote, label, reference, exercise, answer, figure, font size, line spacing, and source order. Preserve the rejected v3 build and its full-page finding, prove that restoring exactly these three directives reconstructs the D022 bytes, and admit only after a fresh deterministic build and inspection of every newly rendered B005 page.

## D024 — Restore the map-subsection break after observing float flow

The D023 build proved that omitting the breaks before `Statistik robust` and `Mentransformasi data` fills pages 52–54 cleanly, but it disproved the predicted benefit of omitting the third break. Without the break before `Memetakan data`, the map introduction moves onto page 54 while Example 2.21 and Guided Practice 2.22 remain alone on severely underfilled page 55; the two full-page map figures still follow on pages 56–57. Restore exactly the upstream `\D{\newpage}` before `Memetakan data`. This allows the deferred transformed-population plot, map introduction, example, and guided practice to share page 55 as a readable source-order unit, as already evidenced in the v3 render. The net live D023/D024 layout delta is therefore two removed print breaks, not three. Preserve all reader-visible content and revalidate the complete source/build/visual/backend chain before admission.

## D025 — Reflow each landscape map pair across the page width

The D024 build restored the coherent map-subsection start but left roughly half of page 55 empty while two pairs of landscape county maps each consumed a full following page. Keep the map-subsection break and preserve both figure environments, all four source-order assets, subfigure labels, captions, references, accessibility descriptions, and data. Scale each map from `1.00\textwidth` to `0.48\textwidth` and separate each pair with `\hfill`, so the two maps belonging to one comparison can sit side by side. This is a layout-only reflow: it changes no reader prose, mathematics, data, semantic identity, or asset bytes. Admission requires source proof that reversing only these six tokens reconstructs D024 exactly, a deterministic rebuild, and full-resolution inspection that map legends remain readable and no clipping, overlap, severe underfill, centering defect, or orphan is introduced.

## D026 — Keep the map pairs in pedagogical order and continue into exercises

The D025 build proves that all four legends remain readable at `0.48\textwidth` and reduces the reader by one page, but the default float policy moves Figure 2.15 above subsection 2.1.8 and leaves Figure 2.16 alone on a severely underfilled float page before the inherited exercise-header clear page. Retain D025's scale and pairing. Constrain the first figure to bottom placement and the second to top placement, then suppress `\clearpageforsection` only within the local `\exercisesheader{}` call for Section 2.1. This lets the text that precedes Figure 2.15 stay visually before it and permits the exercises to continue below Figure 2.16. Preserve every heading, exercise, source-order figure, caption, label, reference, footnote, map asset, accessibility description, font size, and line spacing. Admission requires exact reconstruction of D025 by reversing only the two placement options and the four-line local header wrapper, a deterministic rebuild, and inspection of every B005 page for order, readable legends, clipping, overlap, severe underfill, centering, and orphans.

## D027 — Place both map pairs before the exercise sequence

The D026 build fixes the earlier two defects but permits the exercise header and opening text of Exercise 2.1 to pass the still-pending Figure 2.15 float, placing source-later exercise material before the first map pair. Load the inert `placeins` package in the preamble and insert one `\FloatBarrier` immediately after Figure 2.16 and before the Section 2.1 exercise input. Retain D025's side-by-side scale, D026's bottom/top preferences and locally scoped exercise-header clear-page suppression. The barrier changes no content or typography; it only requires both declared source-order map floats to be placed before exercise content may proceed. Admission requires exact D027 reversal to D026, a deterministic rebuild, and complete visual confirmation that subsection prose precedes Figures 2.15–2.16, both figures precede Exercise 2.1, legends remain readable, and no clipping, overlap, severe underfill, centering defect, or orphan is introduced.

## D028 — Repair the final Section 2.1 reader-polish findings

The complete v8 visual sweep confirms that D027 fixes the map/exercise order, but rejects v8 for three later findings: Exercise 2.10's six-panel graphic occupies only the top quarter of page 58 because the inherited `\D{\newpage}` immediately after it blocks Exercise 2.11; the displayed weighted-mean URL hyphenates misleadingly as `openin-` / `tro.org/...`; and Example 2.20 leaves a visible space before its first period because an invisible index command separates the word and punctuation. Omit only that post-2.10 print break, keep the short displayed URL in one unbreakable box so it moves intact to the next line, and place the period before the zero-width index command. These edits preserve every word, target URL, exercise, figure, formula, label, reference, index term, accessibility description, answer relation, font size, and source order. Reject and archive v8; freeze the exact D028 bytes as source gate v9; then require a fresh deterministic build and full visual inspection with P1/P2/P3 all zero before admission.
