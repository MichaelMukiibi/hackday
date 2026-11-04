# IjwiCare dataset preparation

Run from the workspace root with Python 3.11 or newer; no packages are required:

```powershell
python dataset_pipeline/pipeline.py download
python dataset_pipeline/pipeline.py validate
python dataset_pipeline/pipeline.py filter
python dataset_pipeline/pipeline.py review
python dataset_pipeline/pipeline.py split
```

`source.json` pins the original MedQuAD Git commit and attribution. Downloading
stores the unchanged ZIP in `data/`, alongside a timestamp, size, source and
SHA-256 manifest. Running download again verifies and reuses the existing archive.
The first download records the observed checksum; subsequent runs verify it.

Validation independently verifies that checksum, parses every XML document,
counts answered and unanswered pairs, and writes per-file checksums and a summary.
The original license and readme are copied beside the archive. Dataset bytes are
ignored by Git. The ZIP is read directly without extracting its directory tree.

This stage does not crawl missing copyrighted answers, translate data, upload
anything, or claim clinical review. Source answers may be outdated.

## Filter the IjwiCare candidate pool

The independent `filter` stage verifies the source archive and applies
`filter_rules.json` to each document's Focus title. Incidental answer mentions
and synonyms do not select records. Rules use word boundaries, exclude diabetes
insipidus from the diabetes category, and match only eye-related screening titles.
Categories overlap. Title matching is a transparent candidate-selection heuristic,
not a complete medical taxonomy; titles such as retinitis pigmentosa can be missed.

Only nonempty question/answer pairs are exported. Original text is retained;
Unicode NFKC, case folding, and whitespace normalization are used only for deduplication.
Identical normalized question AND answer pairs are merged, retaining every source
reference and matching reason. Near duplicates are not removed. IDs include a
content hash; source row IDs include the collection path and pair ordinal so
repeated XML document IDs across collections do not collide.

Outputs under ignored `data/filtered/`:

- `ijwicare_seed.jsonl`: unique QA candidates with topics, review status, license,
  attribution, source commit, document paths/IDs, question IDs/types, source URLs,
  and selection reasons. Split is `unassigned`.
- `ijwicare_seed.csv`: equivalent records; list/object columns contain JSON.
- `selection_audit.jsonl`: one decision per input QA pair, including exclusions
  and the retained record ID for merged duplicates.
- `document_inventory.json`: all document titles, topics and pre-dedup counts.
- `selection_report.json` and `.md`: counts, topic inventory, hashes, and review notes.

The pinned release produces 553 candidate pairs from 175 documents, reduced to
526 unique QA records after merging 27 duplicate pairs. Topic counts overlap:
245 diabetes, 22 diabetic eye disease, and 303 eye health. No answered document
matches the explicit eye-screening title rule; this does not establish that the
source has no screening-related content. Broad candidates include rare inherited
conditions and country-specific services. Review relevance and current medical
content before augmentation. A count/checksum snapshot is tracked at
`docs/evidence/medquad-selection.json` relative to the repository root.

Run the synthetic behavioral tests without downloading data:

```powershell
python -m unittest discover -s dataset_pipeline -p test_filtering.py
```

## Scope triage and grouped splits

`review` consumes the checksum-verified filtered JSONL. Versioned
`review_rules.json` identifies general diabetes/eye-health candidates, defers
specialist-source records except explicitly allowed common conditions, and defers
location-specific titles. Text mentioning Medicare, Medicaid, the United States,
or American Indians is flagged for local-context review; a flag alone does not
exclude a whole record. Scope decisions are automated, with reasons attached.
They do not mark any example clinically reviewed or current.

Review outputs in `data/reviewed/`:

- `scope_review.jsonl`: all 526 candidates with their original provenance and new scope decisions.
- `review_queue.csv`: IDs, decisions, titles, questions, source URLs, and flags for human review.
- `review_report.json`: input/config/code checksums and decision counts.

Current scope counts: 280 core candidates, 234 deferred specialist candidates,
and 12 deferred location-specific candidates. Thirty records have local-context
content flags. Deferred records remain available for review and are excluded
from every split. Revisit the versioned rules and rerun downstream stages to
change scope decisions; arbitrary CSV edits are not ingested as approvals.

`split` consumes checksum-verified review output and `split_rules.json`. It
creates transitive connected groups using whole source-document paths,
fragment-free source URL paths (scheme/query ignored), normalized topic titles
and configured aliases, identical normalized questions or answers, and answer
5-word-shingle Jaccard similarity of at least 0.85 for answers of 30+ words.
Similarities are checked before assigning a group, even when links connect
otherwise different documents. This is not broad disease-family isolation and
cannot rule out semantic overlap that these rules do not detect.

Largest groups are assigned first to minimize squared deviation from an 80/10/10
record target; a configured seed resolves size ties. Groups are indivisible,
so proportions can differ and topic distributions are not stratified. Assignment
is independent of input record order. All translations and paraphrases must
inherit their parent ID, group, and split; only training parents may be augmented.
Adding previously deferred records requires regrouping before use.

Split outputs in `data/splits/`: `train.jsonl`, `validation.jsonl`, `test.jsonl`,
`groups.json`, `assignment.csv`, and `split_report.json`. Current counts are
**224 train / 28 validation / 28 test**, across 50 groups; the largest group has
27 records. No grouping-key collisions cross splits. The report records missing
held-out topics: all 22 diabetic-eye examples are in one training group, so
independently sourced diabetic-eye evaluation cases are still needed.

Tracked aggregate evidence is in `docs/evidence/medquad-review-report.json` and
`docs/evidence/medquad-split-report.json`. Data and review queues stay ignored.

Run all behavioral tests:

```powershell
python -m unittest discover -b -s dataset_pipeline -p "test_*.py"
```

Next modules: human scope/current-evidence review; an independently sourced
diabetic-eye evaluation set; multilingual pilot preparation; Adaption export;
and clinical/language review. Those modules must preserve split assignments.

## Small English pilot and fast smoke test

```powershell
# Export a pilot from existing split files only:
python dataset_pipeline/pipeline.py pilot
# Rerun every implemented local preparation stage and validate the pilot:
python dataset_pipeline/pipeline.py smoke
```

The smoke command requires the already-downloaded source archive and makes no
network calls. For a fresh checkout, run `download` first. It regenerates stage
outputs from versioned inputs, rather than assuming old files are current.

`pilot_rules.json` selects ten unique English training parents using a fixed seed:
4 diabetic-eye, 3 diabetes excluding diabetic-eye, and 3 other eye-health records.
Answers longer than 6,000 characters and records with local-context content flags
are skipped; insufficient eligible examples cause an error instead of reducing
the requested sample. These rules bound a technical pilot, not a representative
medical evaluation set. Source text is neither truncated nor rewritten.

Pilot outputs in ignored `data/pilot/`:

- `adaption_pilot.csv` and `.jsonl`: identical instruction/output/input columns,
  plus parent IDs, groups, split, language, source revision, and review statuses.
- `pilot_parents.jsonl`: full source records and provenance.
- `pilot_manifest.json`: exact IDs, group IDs, input/output hashes, rule version,
  column mapping, and CSV/JSONL verification results.

The export mapping follows the existing `main.py` example; no live import is
claimed. Validation/test records and groups are rejected. Exported text and
metadata must match the training parent exactly, including multiline content.
`data/smoke_report.json` summarizes all five local stages and their report hashes.
A tracked snapshot is `docs/evidence/medquad-smoke-report.json` at repo root.

No upload, paid Adaption job, translation, model call, or clinical validation is
performed. A separate small live import is the next integration check. Do not run
`main.py` for this pilot: that historical script imports Alpaca and starts a paid
adaptation automatically.

## Hugging Face publication package

```powershell
python dataset_pipeline/prepare_huggingface.py
```

This separate, offline packaging command verifies the pilot and all split-file
checksums, rechecks each pilot row against its training parent, and permits exactly
ten rows. It builds only five allowlisted files under ignored `data/huggingface/`:
`README.md` (dataset card), `LICENSE` (original MedQuAD terms), `train.csv`,
`provenance.json` (full parent metadata), and `manifest.json` (source revision,
pipeline Git commit, hashes and column mapping). Unexpected extra files cause
an error rather than entering an upload. Validation/test data are never packaged.

The dataset card explicitly configures only `train.csv` as the training split;
JSON metadata is not an additional dataset split. The card preserves attribution
and states the unreviewed status and evaluation limits. Run packaging from a
committed feature revision before upload so the recorded Git commit includes
the packaging script. Upload only these five files to the Hugging Face dataset
repository, then record its exact commit and verify its published file hashes.
Packaging itself does not create repositories, upload, read credentials, or run
Adaption jobs.

### Programmatic publishing

The public pilot repository is
[MichaelMukiibi/ijwicare-medquad-pilot](https://huggingface.co/datasets/MichaelMukiibi/ijwicare-medquad-pilot).
Set `HF_TOKEN` in the ignored repository-root `.env` file to a token with write
access to that repository. Do not paste or log the token. The uploader loads it
through python-dotenv and the official Hugging Face client.

```powershell
uv sync --frozen
# Check the package and authenticated account without uploading:
uv run --frozen python dataset_pipeline/publish_huggingface.py
# Explicitly upload and verify the published revision:
uv run --frozen python dataset_pipeline/publish_huggingface.py --publish
```

The uploader accepts only the five package files, checks all hashes and parent
records, verifies the account owner, and uploads one commit with a parent-revision
guard. Existing matching contents are reused. It neither changes repository
visibility nor deletes remote files. After upload it fetches all five files
anonymously at the returned commit and compares their bytes. A receipt with the
pinned CSV URL is written to ignored `data/huggingface-publication.json`.
No Adaption import or credit-consuming job is launched by this command.

## Live Adaption pilot import and estimate

The separate SDK command reads `ADAPTION_API_KEY` from the ignored repository
`.env`. It never prints the key and does not invoke historical `main.py`.

```powershell
uv run --frozen python dataset_pipeline/adaption_pilot.py import
uv run --frozen python dataset_pipeline/adaption_pilot.py status
uv run --frozen python dataset_pipeline/adaption_pilot.py verify
uv run --frozen python dataset_pipeline/adaption_pilot.py estimate
```

Use an explicit installed Python version with uv if needed, as described in
[Contributing](../CONTRIBUTING.md). The `import` command sends the pinned Hugging
Face tree URL and only `train.csv`, with `processing_mode: raw` and explicit
column mapping. Import state is saved immediately under ignored `data/adaption/`;
rerunning reuses that dataset ID. Automatic retries for creation are disabled.
If the outcome of creation is unknown, the saved marker blocks another creation
until it is reconciled against the account's datasets. Do not remove it just to
retry a timed-out import.

`status` checks one current snapshot. If ingestion is pending, wait before
rerunning it; `verify` requires a successful ten-row import. Raw CSV exports
contain canonical `original_prompt` and `original_completion` columns, with
question and JSON context joined by a blank line. The provider export omits
original ID/group/split metadata. Verification matches every complete canonical
prompt/answer pair exactly, rejects missing/changed/duplicate rows, and saves
`parent_crosswalk.json` to recover the original parent ID, group, and split.
It reads tar/ZIP exports in memory without extracting archive paths.

`estimate` requires the successful verification receipt, validates the original
instruction/output/input mapping with a ten-row cap, and sets `estimate=True`.
It explicitly clears language expansion. Only the explicit `adapt` command starts a paid job; see the run-management
commands below. Quote values are point-in-time estimates, not receipts of consumption.
Future adaptation/augmentation must preserve the content-to-parent crosswalk or
carry equivalent provenance rather than assuming the provider exports IDs.

Current evidence: dataset `9c26e979-7a0f-4277-a3df-a6b677bba341` imported ten rows;
all source prompt/context/answer content matched. The estimate-only response was
1 credit and 11 minutes, with no adaptation run ID. See
[import evidence](../docs/evidence/adaption-pilot-import.json). Provider
canonicalization and an accepted mapping do not establish clinical or model quality.

## Reusable adaptation run management

`adaption_jobs.py` exposes a client-injected `AdaptationJob` class for estimate,
launch, status, and CSV download, plus `inspect_result` for offline comparison.
Its request is configured by versioned `adaption_recipe.json`. The existing
`adaption_pilot.py` CLI wires it to the verified ten-row IjwiCare import.

```powershell
# Quote the exact versioned recipe; no paid run:
uv run --frozen python dataset_pipeline/adaption_pilot.py estimate
# Starts paid processing, only if a fresh quote is within one credit:
uv run --frozen python dataset_pipeline/adaption_pilot.py adapt --max-credits 1
# One status snapshot; repeat later while pending/running:
uv run --frozen python dataset_pipeline/adaption_pilot.py run-status
# After the same run succeeds:
uv run --frozen python dataset_pipeline/adaption_pilot.py download
# Local inspection; no API key or network required:
uv run --frozen python dataset_pipeline/adaption_pilot.py inspect
```

If needed, select the installed Python explicitly with uv's `--python 3.14`, or
invoke `.venv\Scripts\python.exe` in this workspace. `--recipe PATH` selects a
recipe; `--run-name NAME` selects an isolated local run folder (default `pilot-v1`).
Use the same recipe and run name to retry or monitor an existing run. Preserve
past run folders; changing a recipe in an occupied folder is rejected. A new
run name alone cannot bypass the check for another provider run on the dataset.

The default recipe caps processing at ten rows, rephrases prompts, requests
concise English drafts for community health workers, disables reasoning traces
and deduplication, and explicitly clears language expansion. Its instructions
request preservation of source facts and uncertainty; they do not establish
clinical correctness. The exact recipe was accepted by an estimate-only API
request quoting 1 credit and 11 minutes. See
[recipe estimate evidence](../docs/evidence/adaption-recipe-estimate.json).

Launches require a finite credit cap, a ready source dataset with the expected
row count, and a fresh estimate. The cap is a client-side quote check, not a
provider-enforced billing maximum or evidence of actual credit consumption.
Before sending a paid request, the manager saves its full request and stable
idempotency key. A timed-out launch replays that same request/key; a recorded
run ID is reused rather than relaunched. Do not delete launch state to retry.

State is ignored under `data/adaption/runs/NAME/`: `estimate.json`, `launch.json`,
`status.json`, `adapted-export.bin`, and `download.json`. Download checks provider
run ownership before and after fetching bytes and requires success. It never
extracts archive members to disk. Monitoring is a single snapshot, so a caller
can schedule checks without holding a long-running wait.

Inspection verifies the export hash and job identity, then matches original
prompt/completion pairs back to training parents. Missing, duplicated, changed,
or untraceable parents and empty enhanced completions fail instead of being
silently assigned IDs. Successful inspection writes `adapted_rows.jsonl`,
`comparison.csv`, and `inspection.json` with parent/group/split links and text
change counts. Generated outputs remain marked `not_reviewed`; text changes are
not labelled as clinical or model-quality improvement. Launch/download/inspection
are covered by mocked behavior tests; no paid run was started while adding them.
