"""Build the allowlisted Hugging Face pilot package without uploading anything."""
import csv
import json
import shutil
from pathlib import Path
from pipeline import DATA, HERE, SOURCE, digest, write_json
from preparation import read_rows
from pilot import verify_export


def main():
    pilot = DATA / 'pilot'
    manifest = json.loads((pilot / 'pilot_manifest.json').read_text(encoding='utf-8'))
    if manifest['source_revision'] != SOURCE['revision']:
        raise ValueError('Pilot source revision mismatch')
    for name, details in manifest['outputs'].items():
        if digest(pilot / name) != details['sha256']:
            raise ValueError('Pilot checksum mismatch: ' + name)
    parts = {name: read_rows(DATA / 'splits' / f'{name}.jsonl') for name in ['train','validation','test']}
    split_report = json.loads((DATA / 'splits/split_report.json').read_text(encoding='utf-8'))
    for name in parts:
        if digest(DATA / 'splits' / f'{name}.jsonl') != split_report['outputs'][f'{name}.jsonl']:
            raise ValueError('Split checksum mismatch')
    parents = read_rows(pilot / 'pilot_parents.jsonl')
    with (pilot / 'adaption_pilot.csv').open(encoding='utf-8', newline='') as stream:
        verify_export(parents, list(csv.DictReader(stream)), parts)
    if len(parents) != 10 or manifest['row_count'] != 10:
        raise ValueError('Publication package must contain exactly ten pilot parents')
    output = DATA / 'huggingface'
    output.mkdir(exist_ok=True)
    expected = {'README.md','LICENSE','train.csv','provenance.json','manifest.json'}
    unexpected = {p.name for p in output.iterdir()} - expected
    if unexpected: raise ValueError('Unexpected publication files: ' + str(sorted(unexpected)))
    shutil.copyfile(pilot / 'adaption_pilot.csv', output / 'train.csv')
    shutil.copyfile(DATA / 'license.txt', output / 'LICENSE')
    write_json(output / 'provenance.json', parents)
    card = '''---
pretty_name: IjwiCare MedQuAD English Pilot
language:
- en
license: cc-by-4.0
size_categories:
- n<1K
task_categories:
- text-generation
tags:
- medical-question-answering
- diabetes
- eye-health
- ijwicare
- unreviewed
configs:
- config_name: default
  data_files:
  - split: train
    path: train.csv
---

# IjwiCare MedQuAD English Pilot

Ten English training examples for testing dataset import and column mapping in
Adaption. This pilot has **not been clinically reviewed** and is not a benchmark
or a validated medical assistant dataset. It contains no Kinyarwanda or Luganda
translations and no generated or augmented answers.

## Contents and schema

`train.csv` contains exactly ten rows: 4 diabetic-eye, 3 general-diabetes, and
3 other eye-health examples. All were selected from the training partition.
Validation and test records are excluded. The dataset configuration reads only
`train.csv`; `provenance.json` and `manifest.json` are audit metadata, not extra
examples or splits.

| Field | Meaning |
| --- | --- |
| instruction | Original source question; map to prompt |
| output | Original source answer; map to completion |
| input | JSON text with source focus and source URLs; map to context |
| id | Stable parent record ID |
| group_id | Source/content group; preserve for all descendants |
| split | train |
| language | en |
| source_revision | Pinned MedQuAD commit |
| clinical_review_status | not_reviewed |
| language_review_status | not_reviewed |

Full original source paths, URLs, question IDs/types, attribution, and selection
reasons are retained in `provenance.json`. File checksums are in `manifest.json`.

## Source and changes

Source: [MedQuAD](https://github.com/abachaa/MedQuAD), commit
`577bd37b96c02d1833b2c9eed2de9f96964e96cb`.

Authors: Asma Ben Abacha and Dina Demner-Fushman.
*A Question-Entailment Approach to Question Answering*, BMC Bioinformatics (2019).
[Paper](https://doi.org/10.1186/s12859-019-3119-4).

MedQuAD is published under CC BY 4.0; the original license is included as
`LICENSE`. Preserve attribution and identify further changes. The original
omissions of copyrighted answers from three MedlinePlus collections are preserved.

Preparation selected diabetes/eye-health document titles, kept answered records,
merged normalized duplicate QA pairs while retaining provenance, performed
automated scope triage, and grouped source/content links before deterministic
splitting. This ten-row pilot uses a fixed-seed selection. Original question and
answer text is retained; metadata and the serialized source context were added.
No answer rewriting, translation, or clinical approval is claimed.

## Limitations and intended use

This is a small technical integration fixture, not a representative medical
sample. Source material is historical and can be outdated or location-specific.
Automated scope decisions and local export checks do not establish accuracy,
clinical safety, translation quality, or model improvement. No live Adaption
import or paid processing result is asserted by this publication.

All 22 diabetic-eye candidates in the larger preparation set belong to one
training group. Its held-out partitions have no diabetic-eye records, so an
independently sourced evaluation set is needed to measure that capability.
Only training parents may be augmented; derivatives must retain parent ID,
group and split. Do not derive independent test cases by paraphrasing this pilot.

## Reproduce

Pipeline code and versioned source/rules:
[MichaelMukiibi/hackday](https://github.com/MichaelMukiibi/hackday/tree/dev).
Use the exact `pipeline_git_commit` recorded in `manifest.json` for this release.

```sh
python dataset_pipeline/pipeline.py download
python dataset_pipeline/pipeline.py smoke
python dataset_pipeline/prepare_huggingface.py
```

The final command builds only the five allowlisted publication files under
ignored `dataset_pipeline/data/huggingface/`; it makes no network calls.
'''
    (output / 'README.md').write_text(card, encoding='utf-8', newline='\n')
    import subprocess
    commit = subprocess.check_output(['git','rev-parse','HEAD'], cwd=HERE.parent, text=True).strip()
    publication = {'source': SOURCE, 'pipeline_git_commit': commit,
                   'packaging_code_sha256': digest(HERE / 'prepare_huggingface.py'),
                   'pilot_rules_sha256': digest(HERE / 'pilot_rules.json'),
                   'row_count': len(parents), 'language': 'en', 'split': 'train',
                   'column_mapping': manifest['column_mapping'],
                   'parent_ids': [r['id'] for r in parents],
                   'files': {name: {'sha256': digest(output / name), 'bytes': (output / name).stat().st_size}
                             for name in sorted(expected - {'manifest.json'})}}
    write_json(output / 'manifest.json', publication)
    print('Prepared exactly five publication files at', output)
    print('Rows:', len(parents), '| clinical and language review: not_reviewed')


if __name__ == '__main__': main()
