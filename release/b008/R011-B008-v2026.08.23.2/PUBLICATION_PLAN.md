# R011-B008 publication plan (inert until admission)

This plan targets only the existing lineages: Zenodo concept `10.5281/zenodo.22059801`, Figshare article `33314727` in project `280296` and Indonesian collection `8668413`, and GitHub repository `KokunoYumeto/statistika-berbasis-data-id`.

The release is explicitly **belum lengkap**. Its text and translation use **CC BY-SA 3.0 Unported**, while component-specific rights remain controlling. Full source credit is retained for David M. Diez, Mine Çetinkaya-Rundel, and Christopher D. Barr. The production-model string is exactly **OpenAI Codex gpt-5.6-sol, Ultra**.

Execution order after terminal admission only:

1. Bind exact boundary, admitted backend, admission, post-admission readback, and promoted-PDF identities in `RELEASE_INPUTS.json`; change status to `READY_FOR_PACKAGING` only when every assertion is true.
2. Run the B008 packager. It reconstructs and verifies the V3 source closure, excludes only the recorded nonpublishable component, builds deterministic source/backend ZIPs, places the PDF first, emits exact hashes, and verifies the package.
3. Publish a new version in the existing Zenodo concept, reject any remote version collision, upload the exact ordered assets, publish, then anonymously read back every byte.
4. Update the existing Figshare article. Mirror bytes only if Figshare offers the exact CC BY-SA 3.0 license; otherwise use a CC0 metadata/link-only item pointing to the public Zenodo version, with no edition files. Verify project/collection association and anonymous public state.
5. Update the existing GitHub repository with narrow exact-path operations only, create the collision-free prerelease tag, attach the exact release assets, and anonymously verify raw/tree/release bytes.

There is **no upstream contact** in this workflow. It does not open or comment on issues, discussions, pull requests, email, or any other author channel.

Self-check mode reads no credentials, performs no network request, invokes no Git command, creates no package, and publishes nothing.

