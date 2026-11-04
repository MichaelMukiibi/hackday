# Ijwi - Adaption Data Lab

**Reproducible healthcare dataset preparation and Adaption experimentation for IjwiCare, a retinal-screening assistant for community health workers.**

Built for Build54 Hacktoberfest Hack Day Kigali, October 31, 2026. Companion application: [Ijwi](https://github.com/MichaelMukiibi/ijwi-hack-day).

## Quick technical validation

With the pinned dataset already downloaded, run this offline smoke test:

```sh
python dataset_pipeline/pipeline.py smoke
```

For a fresh checkout, first run `python dataset_pipeline/pipeline.py download`.
The smoke command reruns validation, filtering, scope triage, grouped splitting,
and a deterministic **10-row English pilot export**: 4 diabetic-eye, 3 diabetes,
and 3 other eye-health examples. It checks record accounting, training-only
parent selection, held-out group exclusion, and exact CSV/JSONL round trips.
No Adaption credentials, uploads, credits, generation, or inference are involved.

The pilot files are `dataset_pipeline/data/pilot/adaption_pilot.csv` and `.jsonl`;
`pilot_parents.jsonl` retains full provenance. `pilot_manifest.json` records IDs,
hashes, selection rules, and column mapping (`instruction` -> prompt, `output`
-> completion, `input` -> context), following the existing repo example.
Actual Adaption import compatibility remains unverified. The local
`dataset_pipeline/data/smoke_report.json` and tracked
[smoke evidence](docs/evidence/medquad-smoke-report.json) record the technical result.

A smoke-test pass establishes local data-flow integrity, not clinical accuracy,
translation quality, augmentation quality, or model performance. The next
integration check is a real import of this small pilot into Adaption.

## IjwiCare dataset: MedQuAD

The active healthcare dataset work starts from [MedQuAD](https://github.com/abachaa/MedQuAD). We will select diabetes and eye-health examples, then prepare reviewed Kinyarwanda and Luganda variants and task-specific augmentation in Adaption. The existing Alpaca export below is historical integration evidence; it is not the source for this healthcare dataset.

### Download, validate, and filter

Run these independent stages from the repository root with Python 3.11 or newer. The pipeline uses only the Python standard library; it requires no Adaption credentials or credits.

```sh
python dataset_pipeline/pipeline.py download
python dataset_pipeline/pipeline.py validate
python dataset_pipeline/pipeline.py filter
python dataset_pipeline/pipeline.py review
python dataset_pipeline/pipeline.py split
```

The download stage saves the unchanged source archive and a manifest. Repeated runs verify and reuse the archive. Validation checks its SHA-256, parses every XML document, and writes file checksums and a count report. See [pipeline instructions](dataset_pipeline/README.md) and [pinned source configuration](dataset_pipeline/source.json).

| Locally verified item | Value |
| --- | --- |
| Source commit | `577bd37b96c02d1833b2c9eed2de9f96964e96cb` |
| Archive size | 16,953,181 bytes (16.95 MB) |
| Uncompressed file bytes | 36,735,138 bytes (36.74 MB) |
| XML documents | 11,274 |
| Question-answer entries | 47,441 |
| Entries with nonempty answers | 16,407 |
| Entries without answers | 31,034 |
| Archive SHA-256 | `161d948f8ce8f82accca1f5769a512dff2a01af2b3004d48f2b3da2758a38a09` |

These are observed counts for the pinned release; the project's advertised total is 47,457. Raw data and generated reports live in ignored `dataset_pipeline/data/` and are regenerated locally. The first download records the observed archive checksum; subsequent runs verify against that local manifest.

MedQuAD is published under **CC BY 4.0**. Attribute Asma Ben Abacha and Dina Demner-Fushman, *A Question-Entailment Approach to Question Answering*, BMC Bioinformatics (2019), retain source provenance, and identify modifications. The original authors removed answers from three MedlinePlus subsets for copyright reasons; the pipeline preserves those omissions and does not fetch replacement answers. See the [original source documentation and license](https://github.com/abachaa/MedQuAD).

### Filtered candidate dataset

The implemented filter applies [versioned topic rules](dataset_pipeline/filter_rules.json) to document titles, keeps answered records, and merges exact normalized QA duplicates while retaining every source reference and selection reason.

- **526 unique QA candidates** from 175 documents; 553 pairs before merging 27 duplicates.
- Overlapping topics: **245 diabetes**, **22 diabetic eye disease**, and **303 eye health**.
- No answered document matched the explicit eye-screening title rule. This is a limitation of title-based selection, not evidence that screening content is absent.
- JSONL, CSV, full selection audit, document inventory, and reports are generated in ignored `dataset_pipeline/data/filtered/`.
- The tracked [selection evidence](docs/evidence/medquad-selection.json) records counts, rules/code hashes, and output checksums.

This is a broad candidate pool: rare inherited conditions and country-specific guidance require relevance review. Original source answers remain unreviewed. See [filter documentation and test command](dataset_pipeline/README.md).

### Scope triage and evaluation splits

Automated [scope rules](dataset_pipeline/review_rules.json) retain **280 core candidates**, defer **234 specialist** and **12 location-specific** examples, and flag local-context content for review. All clinical and language review statuses remain unreviewed. The full 526-record review queue is preserved locally.

[Split rules](dataset_pipeline/split_rules.json) keep linked source documents, URL paths, configured topic aliases, identical text, and near-duplicate answers together. Fifty connected groups produce **224 training, 28 validation, and 28 test records**, with no cross-split grouping-key collisions. Translations and paraphrases must inherit their parent's split; only training parents may be augmented.

**Evaluation coverage limitation:** all 22 diabetic-eye records are in one training group. The held-out sets do not establish diabetic-eye performance; independently sourced evaluation cases are needed. Grouping also does not guarantee elimination of all semantic overlap.

See the tracked [scope evidence](docs/evidence/medquad-review-report.json), [split evidence](docs/evidence/medquad-split-report.json), and [stage documentation](dataset_pipeline/README.md). Generated data, review queues, assignments, and reports live under ignored `dataset_pipeline/data/`.

### Next stages

1. Review clinical currency and local applicability of the core candidates and flagged records.
2. Prepare independently sourced diabetic-eye evaluation cases without using augmented training material.
3. Prepare a small multilingual pilot with translation provenance and explicit clinical and language review status.
4. Export selected training records to Adaption for augmentation, then evaluate against the held-out cases.
5. Add clearly marked synthetic intake, FastDRS tool-use, and specialist-handoff examples separately from source-derived medical Q&A.

Acquisition, structural validation, topic filtering, automated scope triage, and grouped splitting are implemented. Human relevance review, translation, clinical review, and healthcare augmentation remain planned; these pipeline checks do not establish medical accuracy or model improvement.

## Historical Adaption practice evidence

This repository contains an Adaption SDK workflow and its existing exported practice dataset. The export has been inspected locally; no new paid run was launched while preparing these documents.

| Verifiable item | Observed evidence |
| --- | --- |
| Adaption integration | [main.py](main.py): import, map columns, estimate cost, adapt, wait, export |
| Requested processing cap | `max_rows: 500` in the script |
| Existing exported rows | **497** across **5 Parquet files** |
| Enhanced completions present | **497 nonempty enhanced completions** |
| Enhanced completions different from source output | **483 rows** |
| Export archive | [adapted-alpaca.tar.gz](adapted-alpaca.tar.gz), **559,378 bytes** |
| Reproducible evidence | [inspection report](docs/evidence/export-inspection.json) and [local inspector](scripts/inspect_export.py) |

Differences are evidence of changed text, not a measured improvement in quality. The input cap of 500 is not the exported row count. No reason for the 3-row difference is inferred. Platform run IDs, credit receipts, and before/after model benchmarks are not stored here.

**For judges:** start with [the evidence walkthrough](docs/EVIDENCE.md) and [the submission paragraph](docs/SUBMISSION.md).

## What the existing workflow does

1. Connects to Adaption using `ADAPTION_API_KEY` from an ignored `.env` file.
2. Imports the `tatsu-lab/alpaca` instruction dataset from Hugging Face.
3. Maps `instruction` to prompt, `output` to completion, and `input` to context.
4. Requests an adaptation cost estimate for a maximum of 500 rows.
5. Starts Adaptive Data adaptation and waits for completion.
6. Downloads the resulting Parquet export archive.

The current script demonstrates **adaptation of existing rows**, not row-expansion augmentation or model training. Adaption documents augmentation separately. [Adaption API](https://docs.adaptionlabs.ai/api/resources/datasets/methods/adapt).

The existing source is a general-purpose practice dataset. It is not a clinician-conversation corpus, and the export is not a clinical training dataset. The [Alpaca dataset card](https://huggingface.co/datasets/tatsu-lab/alpaca) lists **CC BY-NC 4.0**; do not assume it is suitable for the planned commercial healthcare product. Preserve applicable source terms and select appropriate licensed sources for the next phase.

## Why this matters for Ijwi

Ijwi combines two open foundations: **FastDRS**, an open-source diabetic-retinopathy screening library, and **Gemma 4**, an open-weight conversational model. The application already separates image inference from text conversation. This repo develops the data-preparation work needed to customise that conversation for Rwandan community health workers.

Adaption's planned role is to help turn permitted healthcare and clinician-conversation data into varied, task-specific examples: clear Kinyarwanda explanations, one-question-at-a-time intake, correct FastDRS tool requests, and careful interpretation of actual screening results.

**MbazaNLP's Kinyarwanda speech resources** are planned for the speech layer. Gemma produces the conversation and tool requests; a separate TTS model produces audio. This repo does not claim that Gemma has been trained to synthesise speech. [MbazaNLP resources](https://aimbaza.org/services/), [Gemma open-weight models](https://ai.google.dev/gemma/docs/core).

## Customisation roadmap - planned

```text
Permitted healthcare/clinician data + reviewed reference material
                 |
                 v
Adaption: adapt / augment / localise / evaluate
                 |
                 v
Clinical and Kinyarwanda-language review + held-out evaluation
                 |
                 v
Customised Gemma 4: text conversation and validated tool requests
                 |
          Worker -> FastDRS -> real screening result
                 |
                 v
Gemma Kinyarwanda explanation -> separate MbazaNLP TTS
```

The detailed [training plan](docs/TRAINING_PLAN.md) covers provenance, target examples, review, evaluation, and deployment boundaries. The owner-reported allocation is **650 Adaption credits**; the current balance and credits consumed are not verified in this repo.

| Capability | Status |
| --- | --- |
| Adaption SDK practice workflow | Present |
| Existing adapted-data export and offline verification | Present |
| MedQuAD acquisition and structural validation | Implemented and verified locally |
| Diabetes and eye-health filtering | Implemented; 526 unreviewed candidate QA records |
| Automated scope triage | Implemented; 280 core candidates and 246 deferred |
| Grouped train/validation/test split | Implemented; 224 / 28 / 28, with diabetic-eye evaluation gap |
| Kinyarwanda and Luganda pilot | Planned |
| Healthcare-specific augmentation | Planned |
| Clinician-reviewed Kinyarwanda training examples | Planned |
| Gemma 4 fine-tuning / AutoScientist training | Planned; supported model must be verified |
| FastDRS tool-call training dataset | Planned |
| MbazaNLP speech integration | Planned |
| Clinical/language validation or measured model improvement | Not established |

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

The existing script prints an estimate and then launches adaptation automatically. Reading these docs or running the offline inspector does not launch it. No new clinical or fine-tuning job is part of this documentation update.

## Repository workflow

Use `doc/<scope>` branches for documentation additions and `feat/<scope>` branches for features and pipeline changes. Merge completed changes into local `dev`, then push `dev` to the remote.

Never commit `.env`, API keys, private patient data, raw dataset downloads, or unreviewed claims of clinical performance.
