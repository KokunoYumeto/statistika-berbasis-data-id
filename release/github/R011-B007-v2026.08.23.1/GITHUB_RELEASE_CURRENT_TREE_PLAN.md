# GitHub release/current-tree plan — R011-B007

Status: planning only. No Git or GitHub mutation has been executed by this plan.

Target repository: `KokunoYumeto/statistika-berbasis-data-id`  
Target tag: `r011-b007-2026.08.23.1`  
Release status: public, non-draft prerelease; explicitly incomplete working checkpoint.

1. Wait for the sanitized B007 Zenodo receipt and require its anonymous metadata, exact file inventory, byte counts, and SHA-256 readback to pass in concept DOI `10.5281/zenodo.22059801`.
2. Build a narrow, explicit current-tree manifest for the admitted B007 source closure and release/control files. Compare path, byte count, and SHA-256 identities without a workspace-wide Git scan. Reject credentials, local profile paths, generated secrets, requester identity, or any path outside the intended closure. Authenticated publisher scripts and the source-QA script that reconstructs requester-privacy test data are operational inputs and are intentionally excluded from the public tree.
3. Commit only that verified closure to the existing repository, preserving upstream author credits and using neutral production attribution: `Codex, atas permintaan pengguna`. Record the production model exactly as `OpenAI Codex gpt-5.6-sol, Ultra`.
4. Create tag `r011-b007-2026.08.23.1` at the admitted release commit. Create the prerelease against that exact commit; do not retarget or move the tag during receipt follow-up.
5. Upload the exact nine Zenodo release files in reader-first order, beginning with `00_STATISTIKA_BERBASIS_DATA_ID_R011-B007_WORKING_READER.pdf`. Require every asset identity to match the sanitized Zenodo receipt.
6. Anonymously read back the public main ref, tag ref, complete recursive Git tree, release metadata, release page, current-tree control files, and every asset. Bind every public tree blob by Git object identity and size; recompute byte counts and SHA-256 hashes for selected raw files and every release asset.
7. Write a sanitized GitHub receipt with repository, commit, tag, release, asset, lineage, and anonymous-readback evidence only. If a receipt/control follow-up commit is needed, keep the release tag fixed at the admitted release commit and verify both refs again.

Terminal gate: complete only when the public tag and prerelease exist at the intended commit, all nine assets and selected raw current-tree files pass anonymous byte/hash readback, and the sanitized receipt contains no credential material or local profile path.
