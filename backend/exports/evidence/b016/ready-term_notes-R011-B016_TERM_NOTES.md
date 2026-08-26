# R011-B016 terminology and translation notes

Scope: the complete main instructional source for Chapter 4, Section 4.3,
from `\section{Binomial distribution}` through the input of
`binomial_distribution.tex`. This is the authority range 1268--1926; in
the admitted B015 live source it is the byte-identical untranslated range
1251--1909 because the localized prefix has a 17-line offset.

The controlling terminology table is
`qa/b016-terminology/R011-B016_CONTROLLED_TERMS.tsv` (4,525 bytes; SHA-256
`a24dbeb63cc74ec4e851a4eeb7e79ca04ca384aed6e2ec54cb5cb10cf8950ebc`).
The candidate follows it without conflict. In particular, it uses
`distribusi binomial`, `model binomial`, `eksperimen binomial`, `percobaan
Bernoulli`, `percobaan`, `sukses`/`gagal`, `peluang sukses`, `faktorial`,
`rata-rata`, `varians`, `simpangan baku`, and `pendekatan normal terhadap
distribusi binomial`. Terms in the table that the source does not introduce
explicitly--`variabel acak binomial`, `peluang gagal`, `kombinasi`, and
`permutasi`--were not inserted merely to force an occurrence.

The notation `${n\choose k}$` is rendered for readers as `n pilih k`.
This choice is provisional but controlled: the preserved Indonesian field
witness directly supports `kombinasi` for unordered selection, while
`n pilih k` is a transparent oral reading of the displayed coefficient.
Every formula and all alternative notations (`$_nC_k$`, `$C_n^k$`, and
`$C(n,k)$`) remain unchanged. No stronger claim of direct attestation for
the spoken form is made.

The B015 insurance term `batas risiko sendiri` is retained for
`deductible`. The reader-visible replacement bodies of `\insureS` and
`\insureF` become `\resp{tidak}` and `\resp{melampaui}`; all macro names,
numeric definitions, and formula calls remain unchanged. English comments
and stable TeX identities remain source-exact because they are not reader
prose.

No reader-layout adaptation was made in the main instructional fragment.
Paragraph source wrapping was allowed to change, but all six forced page-break commands and their order, both
figures and widths, all environments, labels, references, index keys,
inputs, and source-order relations are preserved.

Reader-layout exception for the companion exercise surface: the single
`\D{\newpage}` after Exercise 4.21 was relocated to immediately before
Exercise 4.24. This allows Exercise 4.22 to use the remainder beneath the
dreidel image while distributing Exercises 4.24--4.26 across the following
page. The display-only break count, exercise order, image, visible CC BY 2.0
attribution, mathematics, labels, references, and all other structure remain
unchanged.

Six flexible `\vfill` separators follow Exercises 4.21--4.26. They distribute
the three exercise blocks on each of the final two EoCE pages over the full
text height instead of leaving both pages top-heavy. They add no fixed space,
content, or semantic structure and are normalized explicitly by deterministic
topology QA.

The wording of parts (b) and (c) of Exercise 4.26 was tightened after the
first layout replay. The compact Indonesian retains every number, requested
operation, comparison, and answer-consistency condition, while keeping the
last subpart with the rest of the exercise instead of stranding it alone on
an otherwise empty end-of-section page.

High-confidence source-language repairs made naturally in Indonesian,
without upstream contact:

- `B016-SC001`, authority line 1531: “As the last stage use software”
  requires a comma after the introductory phrase.
- `B016-SC003`, authority line 1776: “in last hollow histogram” requires
  the article “the”.

Production provenance: OpenAI Codex gpt-5.6-sol, Ultra. Source author and
human-contributor credits are outside this fragment and remain untouched.
