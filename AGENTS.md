# Repository instructions for agents

## Scope and documentation

This is the IjwiCare dataset repository. Work in the selected repository; the
companion `ijwi-hack-day` application is separate. Read [README.md](README.md)
for the overview, [ARCHITECTURE.md](ARCHITECTURE.md) for pipeline design and
limitations, and [CONTRIBUTING.md](CONTRIBUTING.md) for commands and workflow.
The stage reference is [dataset_pipeline/README.md](dataset_pipeline/README.md).

## Git workflow

- Use `doc/<scope>` branches for documentation additions and `feat/<scope>` for
  features and pipeline changes, starting from current `dev`.
- After appropriate checks, commit the scoped changes, merge into local `dev`,
  and push `dev` to `origin` as requested by the established repository workflow.
- Preserve unrelated user changes. Do not force-push or rewrite shared history.

## Implementation and verification

- Keep acquisition, validation, filtering, scope triage, splitting, and pilot export
  independently rerunnable. Version configuration and record input/output hashes.
- Preserve source text, IDs, URLs, attribution, review statuses, and parent/group/split
  metadata. Only training parents may be augmented; descendants inherit the split.
- Run `python -m unittest discover -b -s dataset_pipeline -p "test_*.py"` for
  pipeline behavior changes and `python dataset_pipeline/pipeline.py smoke` when
  the source archive is available. Use targeted checks for documentation-only work.
- Do not download data just to validate documentation. Keep `git diff --check`
  clean and verify changed relative documentation links, including filename case.

## Data and integration boundaries

- Store downloaded and generated data in ignored `dataset_pipeline/data/`.
  Commit code, configuration, documentation, and aggregate evidence, not raw data.
- Do not read, print, or commit API keys or `.env` values. Use placeholders in examples.
- `main.py` is a historical Alpaca workflow that starts a paid adaptation after
  estimating cost. Do not execute it as part of tests, documentation work, or the
  MedQuAD pilot. Keep live platform jobs separate from local validation.
- Label automated scope triage as automated. Do not mark examples clinically or
  linguistically reviewed without actual review evidence.
- Local smoke tests and changed completions do not establish clinical accuracy,
  translation quality, live Adaption compatibility, or model improvement.
- All 22 current diabetic-eye examples are in a single training group. Document
  the held-out coverage gap until independently sourced evaluation cases exist.
- Preserve the source's omitted copyrighted answers and applicable license terms.
