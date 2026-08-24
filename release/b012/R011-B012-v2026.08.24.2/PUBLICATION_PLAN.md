# R011-B012 publication checklist

This workflow is inert until every terminal admission identity is exact and `RELEASE_INPUTS.json` says `READY_FOR_PACKAGING`. It targets only Zenodo concept `10.5281/zenodo.22059801`, fixed Figshare article `33314727` in project `280296` / collection `8668413`, and GitHub repository `KokunoYumeto/statistika-berbasis-data-id`.

1. Admission: run self-test and readiness. After the readiness gate, execute the already-authorized guarded B012 transaction, verify the exact admitted state, then emit the post-admission receipt. Admission updates source/assets/PDF/backend and root README/CITATION/checkpoint/cursor in one rollback-protected transaction.
2. Bind terminal identities: fill every null terminal field, including the admission script’s own final byte identity, then change status to `READY_FOR_PACKAGING`. Do not weaken required fields.
3. Package: run self-check, then the reader-first packager. It verifies the source closure, excludes `earacupuncture.pdf` and all 15 exact `.Rhistory` session-history transients, records their identities and reasons in the public manifest, scans every source/backend/evidence byte and every ZIP member case-insensitively for private profile residue, excludes restricted terminology witnesses and unsafe internal receipts, and emits deterministic ZIPs/checksums. The admission guard's exact terminal identity remains verified internally, but its executable bytes are excluded from backend evidence and GitHub because they contain a local profile identifier. The accepted snapshot and admitted outputs are never changed.
4. Zenodo first: reject version/draft collisions, reuse only the correct existing concept lineage, upload the exact nine ordered assets, publish, and anonymously stream-read every public byte.
5. Figshare second: inspect only the fixed article/account/project/collection. If unavailable, write a sanitized truthful route-status receipt and make no remote mutation; never create a duplicate. If available and licensing is truthful, update that fixed item and verify it anonymously.
6. GitHub last: require the Zenodo receipt and Figshare publication/route-status receipt. Build an exact fresh tree from the bounded desired allowlist (no current-tree overlay), scan every desired raw byte, commit it with the current branch head as parent, create the collision-free tag/release, attach exact assets, and anonymously verify tree, raw files, and assets.
7. Publication completion: update the publication checkpoint/cursor only from sanitized public receipts and exact anonymous readback. Keep concept DOI `10.5281/zenodo.22059801` unchanged.

## Exact invocation and gates

Run from the lane root. Stop on the first nonzero exit or any status other than the one shown.

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -B -c "from pathlib import Path; paths=[Path(p) for p in ('scripts/admit_b012.py','scripts/write_post_admission_verification_b012.py','scripts/bind_release_inputs_b012.py','scripts/release_b012_common.py','scripts/package_release_b012.py','scripts/publish_b012.py','scripts/publish_zenodo_b012.py','scripts/publish_figshare_b012.py','scripts/publish_github_b012.py','scripts/finalize_publication_b012.py')]; [compile(p.read_text(encoding='utf-8'), str(p), 'exec') for p in paths]; print('PASS exact-file no-bytecode syntax check')"
python -B scripts\admit_b012.py --self-test
python -B scripts\admit_b012.py --check-readiness
```

Required pre-admission results: `passed`, then `ready_for_guarded_admission`, with `errors: []` and `mutation_performed: false`.

After the readiness gate, execute the already-authorized admission:

```powershell
python -B scripts\admit_b012.py --promote
python -B scripts\admit_b012.py --verify-admitted
python -B scripts\write_post_admission_verification_b012.py
python -B scripts\bind_release_inputs_b012.py --check
python -B scripts\bind_release_inputs_b012.py --bind
python -B scripts\package_release_b012.py --self-check
python -B scripts\package_release_b012.py --package
```

Required gates are `verified_admitted_exact`, `PASS_VERIFIED_ADMITTED_EXACT`, `READY_FOR_PACKAGING`, `PASS_INERT_FAIL_CLOSED`, and `PASS_PACKAGED_VERIFIED`. Use `--replace` with the packager only after inspecting the exact nine B012 target names if a retry encounters pre-existing package outputs.

Only after the package passes, execute the already authorized public transaction in this order:

```powershell
python -B scripts\publish_zenodo_b012.py --self-check
python -B scripts\publish_zenodo_b012.py --publish
python -B scripts\publish_figshare_b012.py --self-check
python -B scripts\publish_figshare_b012.py --publish
python -B scripts\publish_github_b012.py --self-check
python -B scripts\publish_github_b012.py --publish
python -B scripts\finalize_publication_b012.py
```

Zenodo and GitHub must end in a published-and-anonymously-verified state. Figshare may instead end in a truthful `BLOCKED_FIGSHARE_*` route-status state with both `publication_performed: false` and `duplicate_item_created: false`. GitHub consumes either the verified Figshare publication receipt or that bounded route-status receipt. No local Git command is part of this workflow.

The release remains **belum lengkap**. Full credits for David M. Diez, Mine Çetinkaya-Rundel, Christopher D. Barr, and human contributors are preserved. Model identification is exactly **OpenAI Codex gpt-5.6-sol, Ultra**. Public prose uses only “atas permintaan pengguna”. No upstream contact occurs.

