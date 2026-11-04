# IjwiCare dataset preparation

Run from the workspace root with Python 3.11 or newer; no packages are required:

```powershell
python dataset_pipeline/pipeline.py download
python dataset_pipeline/pipeline.py validate
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

Next modules: versioned topic filtering with original document IDs and URLs;
document/topic-grouped deterministic splits; multilingual pilot generation;
Adaption export; and clinical/language review. Those modules should consume
this immutable source and write separate outputs, never modify the raw archive.
