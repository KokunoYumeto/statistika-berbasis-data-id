# R011-B019 offline packaging and publication handoff

The packaging scaffold packages only the exact 190-page B019 boundary-clean learner reader. Separate bounded publication entry points perform the authorized public transactions only when invoked with `--publish`; their self-check mode performs no credential access, Git invocation, network request, upload, publication, or upstream contact. The flow creates no competing Zenodo concept and never invokes local Git.

1. Promote the admitted PDF to `output/pdf/statistika-berbasis-data-batas-R011-B019.pdf`; it must remain 10121910 bytes with SHA-256 `97d3524e413d33d091789b432861065535f84399f59a76e1cf365cfd494bd68b` and exactly 190 pages.
2. Finish pagewise language and visual QA and admit B019 into the modular backend. The backend manifest must bind the exact reader SHA-256 and `R011-B019`.
3. Run `prepare_b019_release.py --prepare` to resolve the exact input identities, then `package_b019.py --package`. Both tools fail closed if the reader, QA, source snapshot, backend, or verified B018 predecessor changes.
4. Run `publish_zenodo_b019.py --publish`. It uses only the existing Zenodo concept `10.5281/zenodo.22059801`, creates one successor to public B018 record `22133317`, keeps access open, and anonymously reads every released byte back.
5. After the sanitized Zenodo receipt exists, run `publish_github_b019.py --publish`. It builds one exact bounded REST-API tree on `KokunoYumeto/statistika-berbasis-data-id`, parented by B018 release commit `d022fdfdfd2798dce9e2e0348d1ec24b6bd37a7b`, tag `r011-b019-2026.08.28.1`, with no local or repository-wide Git scan; it anonymously verifies the exact public tree and every release asset.

Scope truth: partial; 190 accepted Indonesian learner-reader pages through Chapter 5 Section 5.1; all six Section 5.1 exercises; upstream-public answers 1, 3, and 5; O001 gaps 2, 4, and 6; zero untranslated instructional/exercise prose in the learner reader; full source closure contains untranslated source and is not learner output. Model: **OpenAI Codex gpt-5.6-sol, Ultra**. License: **CC BY-SA 3.0 Unported**, subject to component-specific rights.
