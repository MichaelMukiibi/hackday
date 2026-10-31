# Adaption contribution - submission text

## Short version

For Ijwi, we implemented an Adaption Adaptive Data SDK workflow covering dataset import, column mapping, cost estimation, adaptation, and export. The repository includes the existing practice export: **497 rows across five Parquet files**, with **497 nonempty enhanced completions** and **483 completions differing from their source outputs**. A reproducible inspector and checksums make this work reviewable. This establishes our data-preparation workflow for the next phase: reviewed healthcare conversations and Kinyarwanda FastDRS tool-use examples for customising open-weight Gemma 4, with separate MbazaNLP speech synthesis.

## Status sentence to keep with the submission

The current artifact uses the general-purpose Alpaca dataset. Healthcare-specific augmentation, Gemma fine-tuning, Kinyarwanda validation, and speech integration are planned; changed text is not a claim of improved model or clinical performance.

## What to show a judge

1. Open [main.py](../main.py) to show real Adaption client calls and the estimate-before-run workflow.
2. Open [the evidence report](evidence/export-inspection.json) to show the observed 497-row export and checksums.
3. Point to [the existing export](../adapted-alpaca.tar.gz), including original and enhanced-completion fields.
4. Explain the [Ijwi training plan](TRAINING_PLAN.md): open-weight Gemma conversation/tool use, open-source FastDRS screening, and separate MbazaNLP Kinyarwanda speech resources.
5. Show an actual Adaption dashboard run report if available; no run ID, credit usage, or training score is invented in these docs.

## Publish the documentation

The documentation is prepared on local dev. After the owner pushes dev, share the dev branch or merge it into the intended public submission branch. The default main README will remain unchanged until you publish/merge these commits there.

Repository: https://github.com/MichaelMukiibi/hackday
Companion Ijwi app: https://github.com/MichaelMukiibi/ijwi-hack-day
