# Ijwi: Kinyarwanda dialogue and FastDRS tool-use customisation

Status: planned healthcare customisation pipeline, following the completed practice workflow documented in EVIDENCE.md. No healthcare adaptation or model-training run is asserted here.

## Objective

Prepare rich training examples for an open-weight Gemma 4 variant that communicates clearly with Rwandan community health workers, requests FastDRS inference when appropriate, and explains actual screening results without inventing findings. Produce short, speakable Kinyarwanda text for a separate MbazaNLP TTS model. Efficiency is an evaluation goal, not an established result.

## Roles

| Component | Role |
| --- | --- |
| Adaption Adaptive Data | Prepare, adapt, augment, and localise permitted text examples; inspect quality signals |
| AutoScientist or another compatible trainer | Optional later Gemma customisation, after model eligibility is checked |
| Gemma 4 | Kinyarwanda dialogue, missing-information questions, structured tool requests, result explanation |
| Worker tool executor | Validate arguments, enforce case/image access, call the existing screening API |
| FastDRS | Run the retinal image model and return actual prediction/scores/provenance |
| MbazaNLP resources | Separate Kinyarwanda speech recognition and/or text-to-speech layer, after model and license checks |
| Qualified clinical and language reviewers | Review clinical meaning and Kinyarwanda wording |

Adaption Data is the data-preparation layer, not the speech synthesiser. A text-adapted Gemma model does not automatically produce speech waveforms. MbazaNLP is a collection of models, datasets, and community resources; select a specific implementation rather than assuming a single installable library covers everything.

## Seed-data requirements

Start with 100–200 reviewed seed examples as a proposed pilot, not an achieved count. Select healthcare and clinician-conversation datasets whose licenses and consent permit the intended use and adaptation. Record source, revision, language, permitted use, reviewer status, and lineage. The current non-commercial Alpaca practice export is separate from this planned corpus.

Remove identifying patient details. Link clinical claims to reviewed source material. Keep examples with uncertainty, missing history, unavailable images, failed inference, and out-of-scope requests. Text augmentation must not invent reference labels for ungraded retinal images.

## Target example families

1. One-question-at-a-time intake, reusing known information and accepting unknowns.
2. English/Kinyarwanda aligned conversations that preserve clinical facts, numbers, units, and uncertainty.
3. Validated tool-call trajectories: image available -> request screening -> receive the real structured result -> explain it.
4. No-image, invalid-image, timeout, and unavailable-tool trajectories with no fabricated screening result.
5. Short result explanations for a health worker; no score presented as a calibrated probability or autonomous diagnosis.
6. Specialist-handoff drafts assembled from supplied facts and tool output, with unsupported fields explicitly unknown.
7. Speech-ready Kinyarwanda text, reviewed for intelligibility before passing to TTS.

A candidate intermediate JSONL schema could include example_id, source_id, source_revision, language, messages, tool_schema_version, tool_results, reference_ids, reviewer_status, and split. It is a proposed interchange format; convert it to the exact selected Gemma training template before training. Final tool names and argument schemas must match the application executor, not an invented API.

## Adaption execution plan

1. Import a reviewed, licensed pilot corpus and map columns or conversation fields.
2. Request a cost estimate before running a batch.
3. Apply task-focused adaptation and, separately where needed, augmentation/localisation.
4. Preserve source facts; inspect source/adapted quality signals and review a sample manually.
5. Export reviewed examples, maintain provenance, and record actual run ID, settings, and credit usage.
6. Expand useful categories in small batches within the owner-reported 650-credit allocation; verify the account's actual balance before committing additional runs.

The current script calls the adapt endpoint. Row-expansion augmentation is a separate operation and has not been implemented or run in this repo. Check supported Kinyarwanda translation/localisation options instead of assuming a locale code is accepted.

## Evaluation and deployment

Split by source conversation/seed before augmentation so related variants do not leak into evaluation. Keep a held-out set. Compare base and customised Gemma on the same cases: correct decision to invoke FastDRS, valid tool arguments, preservation of supplied facts, appropriate uncertainty, Kinyarwanda quality, and clinician-rated usefulness. Evaluate TTS intelligibility and pronunciation separately. Measure end-to-end latency and memory before claiming efficiency gains.

Check Adaption's actual supported model list before selecting AutoScientist. After training, export/version the weights or adapter and deploy through a compatible inference host. The current application's Cloudflare/Google base-model IDs will not automatically serve custom weights. Keep the working chatbot as the baseline until the customised model passes evaluation.

## Official references

- [Adaption adaptation and cost estimation](https://docs.adaptionlabs.ai/api/resources/datasets/methods/adapt)
- [Adaption AutoScientist workflow and model selection](https://docs.adaptionlabs.ai/autoscientist/running-autoscientist/)
- [Gemma open-weight models](https://ai.google.dev/gemma/docs/core)
- [MbazaNLP speech and language resources](https://aimbaza.org/services/)
- [FastDRS](https://github.com/MichaelMukiibi/diabetic-retinopathy-screening)
