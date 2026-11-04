# Contributing

## Branch workflow

Start from current local `dev` and use `doc/<scope>` for documentation additions
or `feat/<scope>` for features and pipeline changes. Merge completed, checked
changes into local `dev`, then push `dev` to `origin`. Keep unrelated work out of
the branch and do not overwrite another contributor's changes.

```sh
git switch dev
git fetch origin
git merge --ff-only origin/dev
git switch -c feat/your-scope
# Use doc/your-scope for a documentation change.
# Make and check the change, then:
git add <changed-files>
git commit -m "feat: describe the change"
git switch dev
git merge --no-ff feat/your-scope
git push origin dev
```

For documentation, substitute the `doc/` branch name and a `docs:` commit message.

## Local pipeline setup

Run from the repository root. The dataset pipeline uses Python 3.11 or newer and
only the standard library. The separate SDK project in `pyproject.toml` requires
Python 3.13 or newer; its dependencies are unnecessary for the local pipeline.

```sh
python dataset_pipeline/pipeline.py download
python dataset_pipeline/pipeline.py smoke
```

The first command downloads the pinned source archive. `smoke` uses the existing
archive and runs all implemented local preparation stages without network calls,
API credentials, uploads, inference, or Adaption credits. It prints a concise
summary; details are saved in `dataset_pipeline/data/smoke_stages.log` and
`dataset_pipeline/data/smoke_report.json`.

To run stages independently:

```sh
python dataset_pipeline/pipeline.py validate
python dataset_pipeline/pipeline.py filter
python dataset_pipeline/pipeline.py review
python dataset_pipeline/pipeline.py split
python dataset_pipeline/pipeline.py pilot
```

Outputs and configuration details are documented in the
[pipeline guide](dataset_pipeline/README.md). Configuration changes require
rerunning their stage and all downstream stages. Keep raw inputs immutable.

## Prepare the Hugging Face pilot

After the local smoke test, run `python dataset_pipeline/prepare_huggingface.py`
to build the allowlisted ten-row training-only package. It verifies pilot/split
checksums and preserves the original license and full parent provenance. See
[publication package details](dataset_pipeline/README.md). The command is offline;
uploading is a separate operation. Add `HF_TOKEN` with repository write access to
the ignored `.env`, then run `uv run --frozen python dataset_pipeline/publish_huggingface.py`
for preflight, or add `--publish` to upload and verify the pinned revision.
If the pinned Python 3.13 runtime is unavailable, select an installed compatible
interpreter explicitly, for example `uv run --frozen --python 3.14 python ...`.
Record the returned receipt under `docs/evidence/` before handing the source URL
to Adaption. Never commit the `.env` or token.

## Import the pilot into Adaption

With `ADAPTION_API_KEY` configured locally, use the independent `import`, `status`,
`verify`, and `estimate` stages of `dataset_pipeline/adaption_pilot.py`. See the
[live-stage guide](dataset_pipeline/README.md). These stages reuse the saved import,
verify canonical source content, and obtain a ten-row estimate; none launches paid
adaptation. Preserve the parent crosswalk because the raw provider export omits
source metadata. Keep generated exports and account state in ignored data paths.

## Verification

For pipeline behavior changes, run the relevant behavioral tests and the local
smoke command when the archive is available:

```sh
python -m unittest discover -b -s dataset_pipeline -p "test_*.py"
python dataset_pipeline/pipeline.py smoke
git diff --check
```

Confirm stage accounting, output checksums, parent/group/split preservation, and
stable results on rerun when changing selection or export behavior. For changes
limited to documentation, check relative links, filename casing, command accuracy,
and `git diff --check`; a full data rerun is unnecessary.

## Data and evidence conventions

- Keep raw downloads and generated dataset files under ignored
  `dataset_pipeline/data/`. Never commit `.env`, API keys, private patient data,
  or other credentials. `.env.example` contains placeholders only.
- Preserve source commit, IDs, URLs, attribution, transformation history, and
  applicable source terms. MedQuAD is CC BY 4.0; retain the authors' omitted
  copyrighted answers rather than fetching replacements. See
  [source and license notes](ARCHITECTURE.md).
- Keep deferred candidates available for scope review. Automated scope decisions
  and smoke-test passes are not clinical or language approvals.
- Only training parents may be augmented. Translations and paraphrases inherit
  their parent's group and split. Regroup before admitting deferred material.
- Commit aggregate evidence snapshots under `docs/evidence/` when results change;
  describe how they were obtained. Do not infer improved quality from changed text.
- Keep the documented diabetic-eye evaluation gap visible until independent
  evaluation cases exist. Mark synthetic workflow cases separately from source QA.

## Reproduce the evidence without API calls

Install uv, then run from this repository:

```sh
uv run --no-project --python 3.11 --with pyarrow python scripts/inspect_export.py
```

This inspects the existing archive, computes metadata and field counts, and refreshes `docs/evidence/export-inspection.json`. It does not extract archive members to disk, print conversation text, read your API key, contact Adaption, start training, or consume Adaption credits.

## Run the original practice workflow intentionally

```sh
uv sync --frozen
```

Copy `.env.example` to `.env` if needed and set your Adaption key locally. Then, **only when you intend to start a new credit-consuming adaptation run**:

```sh
uv run main.py
```

The existing script prints an estimate and then launches adaptation automatically. Reading these docs or running the offline inspector does not launch it. This historical workflow is separate from the MedQuAD pilot and must not be used to run that pilot.
