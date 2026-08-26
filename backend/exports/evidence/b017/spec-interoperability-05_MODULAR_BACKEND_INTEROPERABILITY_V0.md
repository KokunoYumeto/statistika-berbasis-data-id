# Modular Translation Backend — Interoperability Envelope v0

Status: experimental common minimum for eight independent corpus lanes.
Date: 2026-08-20

This file does not prescribe one winning serialization. Each lane may develop a
better JSON/JSONL/CSV/SQLite representation. It does prescribe the information
that must survive export so a later audit can compare the eight designs and
normalize them without reconstructing meaning from rendered books.

## Design invariants

1. The backend is additive. It may improve indexing, identifiers, segmentation,
   machine readability, and build orchestration without silently changing the
   mathematical or pedagogical content.
2. Source authority is immutable and hash-bound. Corrections are explicit,
   separately identified deltas rather than quiet rewrites.
3. Semantic identity is locale-neutral. Indonesian, Chinese, or another edition
   attaches localized expressions to the same concept/unit/exercise identity.
4. Every reader-facing unit can be selected, ordered, translated, built,
   validated, and cited independently while retaining its position in the work.
5. Licenses and third-party rights attach at the smallest materially distinct
   component, not merely at repository level.
6. IDs are persistent across rebuilds and are never derived only from mutable
   translated titles or page numbers.
7. JSON/JSONL/CSV exports must be deterministic, schema-versioned, UTF-8, and
   round-trip testable. CSV is a projection for exchange, not necessarily the
   only canonical representation.

## Required entity classes

- `program`: curriculum/version/language edition.
- `course`: exact curriculum role and prerequisites.
- `resource`: upstream work/repository/license authority.
- `edition`: exact upstream commit/tag/tree/archive and local derivative.
- `unit`: book/chapter/section/subsection/definition/theorem/example/exercise/
  hint/answer/solution/figure/table/program/interactive or other semantic node.
- `concept`: locale-neutral mathematical concept or skill.
- `segment`: translatable reader-facing string or structured prose block.
- `term`: localized terminology choice with variants, rejected forms, scope,
  register, evidence, and examples.
- `asset`: figure/media/code/data/build dependency.
- `relation`: contains, precedes, prerequisite, depends-on, xref, proves,
  illustrates, exercises, hints, answers, solves, translates, adapts,
  supersedes, or corrects.
- `rights`: license/attribution/change/non-endorsement/third-party status.
- `qa_event`: typed source, math, language, topology, build, accessibility, or
  visual check with witness and result.
- `artifact`: deterministic output with manifest, bytes, hash, toolchain, and
  build receipt.
- `correction`: source-backed defect, target correction, rationale, evidence,
  upstream-report disposition, and affected units.

## Minimum fields carried by every applicable record

- schema name and version;
- globally unique stable ID plus source-local ID/label where present;
- parent/order/path within the source topology;
- exact resource and edition authority;
- source locator and content hash;
- language/locale and translation state;
- source/target relationship and provenance;
- concept/skill tags and prerequisite links where justified;
- rights component ID;
- status, timestamp, responsible workflow, and supersession pointer;
- build/QA linkage where applicable.

## Translation states

At minimum distinguish: `source_frozen`, `queued`, `draft`, `translated`,
`structurally_verified`, `mathematically_reviewed`, `language_reviewed`,
`built`, `visually_checked`, `published`, `superseded`, and `blocked`. A lane may
use a more precise state machine, but it must publish a lossless mapping to these
interchange states. Do not treat unavailable human review as an automatic block;
record what review actually occurred.

## Required deterministic exports

Each lane must produce equivalent machine-readable views for:

1. resource/edition authority;
2. unit hierarchy and order;
3. unit relations and prerequisite/concept mapping;
4. translatable segments and locale mappings;
5. terminology;
6. exercises/hints/answers/solutions and their links;
7. rights/attribution components;
8. corrections and upstream-report disposition;
9. QA/build events;
10. artifact manifests and hashes.

## Comparison criteria for the later consolidation audit

- lossless round trip and deterministic serialization;
- stability under title/wording changes;
- ease of selecting one unit or dependency-closed module for a new language;
- preservation of source topology, identifiers, formulas, code, and assets;
- support for divergent source formats without flattening their semantics;
- transparent corrections and rights boundaries;
- low authoring/maintenance burden;
- queryability without proprietary services;
- ability to merge existing Indonesian editions without retranslation;
- usefulness to a human editor as well as an automated pipeline.

The eventual canonical backend will be chosen only after the independent lanes
have produced evidence. Until then, lanes must satisfy this envelope but may
compete on schema shape, storage model, tooling, and ergonomics.

