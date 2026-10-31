# Adaption evidence walkthrough

Inspection date: October 31, 2026. This document distinguishes source code, an observed export, and planned work. No adaptation or training job was started to prepare it.

## 1. Real SDK integration

The [existing script](../main.py) uses the Adaption client rather than a simulated response. Its source calls cover the following workflow:

| Operation | Source evidence |
| --- | --- |
| create | [main.py line 18](https://github.com/MichaelMukiibi/hackday/blob/c86493be01a53cfc2040ce6e0c2f3f7e82fb1b95/main.py#L18) |
| adapt (estimate) | [main.py line 51](https://github.com/MichaelMukiibi/hackday/blob/c86493be01a53cfc2040ce6e0c2f3f7e82fb1b95/main.py#L51) |
| adapt (run) | [main.py line 60](https://github.com/MichaelMukiibi/hackday/blob/c86493be01a53cfc2040ce6e0c2f3f7e82fb1b95/main.py#L60) |
| wait_for_completion | [main.py line 68](https://github.com/MichaelMukiibi/hackday/blob/c86493be01a53cfc2040ce6e0c2f3f7e82fb1b95/main.py#L68) |
| download | [main.py line 74](https://github.com/MichaelMukiibi/hackday/blob/c86493be01a53cfc2040ce6e0c2f3f7e82fb1b95/main.py#L74) |

These links point to the existing source revision `c86493be01a53cfc2040ce6e0c2f3f7e82fb1b95`. The script's configured input is Alpaca, with prompt/completion/context mappings and a `max_rows` cap of 500.

## 2. Export already present in the repository

Archive: [adapted-alpaca.tar.gz](../adapted-alpaca.tar.gz).

- Size: **559,378 bytes**.
- SHA-256: `cf7fc8dd31eab371f41dff7d11d9ab51cff7b314988c64ba6573a6c4b2429156`.
- Parquet parts: **5**.
- Rows per part: **100, 100, 100, 100, 97**.
- Total exported rows: **497**.
- Observed columns: `instruction`, `output`, `enhanced_prompt`, `enhanced_completion`, `input`, `original_context`, `text`.
- Nonempty text in `enhanced_completion`: **497 rows**.
- Nonempty text in `enhanced_prompt`: **0 rows**.
- Enhanced completions differing from original `output`: **483 rows**.

The report contains an individual checksum for every Parquet part. These observations were calculated from the actual existing artifact, not invented sample records. The `.keepalive` archive member is excluded from dataset row counts.

## 3. Reproduce the numbers

From the repository root:

```sh
uv run --no-project --python 3.11 --with pyarrow python scripts/inspect_export.py
```

Read [the machine-readable report](evidence/export-inspection.json). The inspector reads the archive in memory and does not call Adaption, execute `main.py`, extract archive paths, print dataset text, or spend API credits.

## 4. What this evidence supports

The repository demonstrates an Adaption Adaptive Data integration and an existing export containing enhanced completions. It is suitable evidence of the project's data-platform experimentation and preparation workflow.

It does not establish healthcare-data augmentation, Kinyarwanda accuracy, clinical correctness, training of Gemma, AutoScientist execution, TTS training, exact credit consumption, or model-performance gains. No platform-generated run receipt or run ID was found in the repository; the local inspection report is not a provider attestation. A difference from source text is not proof of improved quality.

## 5. Optional additional submission evidence

If available from the owner's Adaption account, add a screenshot or exported report showing dataset name, run status, row count, and actual credit usage. Keep keys and patient data out of screenshots. Describe only what that evidence actually shows. Do not label the current Alpaca export as healthcare data.

See [the submission paragraph](SUBMISSION.md) and [the next-stage training plan](TRAINING_PLAN.md).
