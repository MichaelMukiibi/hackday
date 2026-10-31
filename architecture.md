# Ijwi Adaption Data Lab architecture

## Existing practice workflow

```text
main.py + ADAPTION_API_KEY from ignored .env
  -> Adaption dataset import (Alpaca)
  -> column mapping + estimate (max_rows=500)
  -> Adaptive Data adaptation
  -> completion polling
  -> Parquet export archive

scripts/inspect_export.py
  -> local archive inspection only
  -> docs/evidence/export-inspection.json
```

The archive currently contains 497 rows across five Parquet parts. The inspector confirms 497 nonempty enhanced completions and 483 changed completions. No paid platform operation is performed by the inspector. Run identifiers, credit receipts, model-training results, and clinical/language validation are not inferred from local artifact inspection.

## Planned Ijwi customisation architecture

Reviewed, licensed healthcare/conversation seeds -> Adaption adaptation/augmentation/localisation -> clinical and language review -> held-out evaluation -> compatible Gemma training -> versioned weights/adapter -> compatible inference hosting.

At runtime, Gemma produces Kinyarwanda text and structured tool requests; a Worker validates and calls FastDRS; the actual screening result returns to the conversation. A separate selected MbazaNLP TTS model produces speech from reviewed text. Gemma text customisation and speech synthesis are distinct components.

The companion application and its existing base-model chatbot remain separate from this data lab. Exporting a training dataset does not automatically deploy customised weights to Cloudflare or Google. Model eligibility, training format, tool schema compatibility, and inference hosting must be checked before that transition.

## Change record

October 31, 2026: added a factual submission evidence pack, offline inspection tool/report, healthcare/Kinyarwanda customisation roadmap, and submission text. Original practice code and export are preserved. No new adaptation, augmentation, or training job was launched, and no additional Adaption credits were spent by this documentation work.
