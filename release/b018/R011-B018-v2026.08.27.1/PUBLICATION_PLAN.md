# R011-B018 correction publication checklist

This route publishes only the corrected 176-page boundary-clean learner reader in the existing Zenodo concept `10.5281/zenodo.22059801` and GitHub repository `KokunoYumeto/statistika-berbasis-data-id`. It creates no competing concept and performs no upstream contact.

1. Resolve exact correction reader, pagewise-language QA, visual QA, source-closure, backend, and checkpoint identities with `prepare_b018_correction_release.py --prepare`.
2. Run `package_b018.py --self-check`, then `package_b018.py --package`; verify the reader is the zero-prefixed first public file.
3. Run `publish_zenodo_b018.py --publish`; create exactly one new version from public B017 record `22105265`, then anonymously read every byte back.
4. Run `publish_github_b018.py --publish`; require the verified Zenodo receipt, create an exact fresh allowlisted tree and prerelease tag `r011-b018-2026.08.27.1`, then anonymously read the release assets back.
5. Persist sanitized receipts and continue Chapter 5 at `repo/ch_foundations_for_inf/TeX/ch_foundations_for_inf.tex:1`, label `foundationsForInference` on line 3.

Scope truth: partial; 176 accepted Indonesian learner-reader pages; zero untranslated instructional/exercise-prose pages; full source closure contains untranslated source and is not learner output. Model: **OpenAI Codex gpt-5.6-sol, Ultra**. License: **CC BY-SA 3.0 Unported**, subject to component-specific rights.
