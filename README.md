# IjwiCare Data Lab

Reproducible healthcare dataset preparation and Adaption experimentation for
IjwiCare, a retinal-screening assistant for community health workers.

Built for Build54 Hacktoberfest Hack Day Kigali, October 31, 2026.
Companion application: [Ijwi](https://github.com/MichaelMukiibi/ijwi-hack-day).

## Quick start

Python 3.11 or newer; the local pipeline needs no additional packages.

```sh
python dataset_pipeline/pipeline.py download
python dataset_pipeline/pipeline.py smoke
```

`download` fetches the pinned MedQuAD archive. `smoke` runs the five local
preparation stages and checks a 10-row English pilot export. It uses no Adaption
credentials or credits. See [setup and verification](CONTRIBUTING.md) for details.

## Current status

| Item | Result |
| --- | --- |
| MedQuAD source | 16,407 answered QA entries in the pinned release |
| Topic filtering | 526 unique diabetes and eye-health candidates |
| Automated scope triage | 280 core candidates; 246 deferred |
| Grouped splits | 224 training / 28 validation / 28 test |
| English pilot | 10 training examples; local CSV/JSONL checks passed |
| Live Adaption import | Verified; 10 source prompt/answer pairs matched |
| Paid healthcare adaptation, augmentation, and translations | Not run |

Clinical and language review remain pending. All 22 diabetic-eye examples belong
to one training group, so the held-out sets do not measure diabetic-eye performance.
A local smoke pass establishes data-flow integrity, not medical or model quality.

## Published English pilot

[MichaelMukiibi/ijwicare-medquad-pilot](https://huggingface.co/datasets/MichaelMukiibi/ijwicare-medquad-pilot)
is public with ten English training rows, the dataset card, original license,
provenance, and checksum manifest. All five published files were fetched
anonymously at revision `bb8f503313728b29add15bcba0c090b6abe6c0b9` and matched
the local package byte-for-byte. See the [publication receipt](docs/evidence/huggingface-publication.json)
for the pinned CSV URL and column mapping.

The pilot is also imported into Adaption as `9c26e979-7a0f-4277-a3df-a6b677bba341`.
All ten source prompt/answer pairs were verified. Its raw export drops parent
metadata, so the local crosswalk restores IDs/groups/splits by exact content
matching. An estimate-only request quoted **1 credit / 11 minutes** for ten rows;
no paid run was started. See [Adaption import evidence](docs/evidence/adaption-pilot-import.json)
and [live-stage commands](dataset_pipeline/README.md).

## Reusable Adaption commands

The [live-stage guide](dataset_pipeline/README.md) covers `estimate`,
`adapt --max-credits 1`, `run-status`, `download`, and offline `inspect`, backed
by a versioned recipe and reusable job manager. Only `adapt` starts paid
processing. It checks a fresh quote and stores retry-safe run state; adding and
testing this code did not launch a paid job.

## Documentation

- [Architecture](ARCHITECTURE.md): stages, provenance, dataset counts, integration boundaries, and roadmap.
- [Contributing](CONTRIBUTING.md): setup, commands, checks, `doc/` and `feat/` branches, merge/push workflow.
- [Agent instructions](AGENTS.md): repository-specific rules for coding agents.
- [Pipeline reference](dataset_pipeline/README.md): configuration, generated files, and stage details.
- [Smoke evidence](docs/evidence/medquad-smoke-report.json): tracked technical-validation snapshot.
- [Training plan](docs/TRAINING_PLAN.md): planned model customisation and evaluation.
- [Historical Adaption evidence](docs/EVIDENCE.md) and [submission text](docs/SUBMISSION.md).

The historical Alpaca export demonstrates earlier platform experimentation.
MedQuAD is the source for the active healthcare dataset. Source attribution and
reuse notes are preserved in [Architecture](ARCHITECTURE.md).
