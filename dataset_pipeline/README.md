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
