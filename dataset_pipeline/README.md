# IjwiCare dataset preparation

Run from the workspace root with Python 3.11 or newer; no packages are required:

```powershell
python dataset_pipeline/pipeline.py download
python dataset_pipeline/pipeline.py validate
python dataset_pipeline/pipeline.py filter
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

Next modules: relevance review; document/topic-grouped deterministic splits;
multilingual pilot generation; Adaption export; and clinical/language review.
Each module should consume immutable inputs and write separate outputs.
