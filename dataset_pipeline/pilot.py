"""Small English pilot export and local integrity checks; no external calls."""
import csv
import contextlib
import io
import hashlib
import json
from preparation import read_rows, read_rules
from filtering import write_jsonl


def select_pilot(rows, rules):
    selected, seen, bucket_counts = [], set(), {}
    if len({r['id'] for r in rows}) != len(rows):
        raise ValueError('Duplicate training IDs')
    for bucket in rules['buckets']:
        eligible = [r for r in rows if r['id'] not in seen and r['split'] == 'train'
                    and r['language'] == 'en' and r['scope_review']['decision'] == 'core_candidate'
                    and bucket['topic'] in r['topics'] and not set(bucket['exclude_topics']) & set(r['topics'])
                    and r['question'].strip() and r['answer'].strip()
                    and len(r['answer']) <= rules['max_answer_characters']
                    and (not rules['exclude_local_context_flags'] or not r['scope_review']['local_context_flags'])]
        eligible.sort(key=lambda r: hashlib.sha256((rules['seed'] + r['id']).encode()).hexdigest())
        if len(eligible) < bucket['count']:
            raise ValueError(f"Insufficient eligible training examples for {bucket['topic']}")
        picked = eligible[:bucket['count']]
        selected.extend(picked); seen.update(r['id'] for r in picked)
        bucket_counts[bucket['topic']] = len(picked)
    return selected, bucket_counts


def export_row(row):
    return {'id': row['id'], 'instruction': row['question'], 'output': row['answer'],
            'input': json.dumps({'focus': row['focus'], 'source_urls': sorted({p['source_url'] for p in row['provenance']})}, ensure_ascii=False, sort_keys=True),
            'group_id': row['group_id'], 'split': row['split'], 'language': row['language'],
            'source_revision': row['source_revision'], 'clinical_review_status': row['clinical_review_status'],
            'language_review_status': row['language_review_status']}


def verify_export(pilot_rows, exported, parts):
    if len(pilot_rows) != len(exported) or not pilot_rows:
        raise ValueError('Pilot/export row count mismatch or empty pilot')
    train = {r['id']: r for r in parts['train']}
    heldout_ids = {r['id'] for n in ['validation', 'test'] for r in parts[n]}
    heldout_groups = {r['group_id'] for n in ['validation', 'test'] for r in parts[n]}
    if len({r['id'] for r in pilot_rows}) != len(pilot_rows):
        raise ValueError('Pilot IDs are not unique')
    for row, imported in zip(pilot_rows, exported):
        if row['id'] not in train or row != train[row['id']]:
            raise ValueError('Pilot differs from its training parent')
        if row['split'] != 'train' or row['id'] in heldout_ids or row['group_id'] in heldout_groups:
            raise ValueError('Held-out data leaked into pilot')
        if imported != export_row(row):
            raise ValueError('Export round-trip changed content or metadata')


def run(here, data, source, digest, write_json):
    splits = data / 'splits'
    split_report = read_rules(splits / 'split_report.json')
    parts = {}
    for name in ['train', 'validation', 'test']:
        path = splits / f'{name}.jsonl'
        if digest(path) != split_report['outputs'][path.name]:
            raise ValueError('Split checksum mismatch; rerun split')
        parts[name] = read_rows(path)
    if split_report['source_revision'] != source['revision']:
        raise ValueError('Split source revision mismatch')
    rules_path = here / 'pilot_rules.json'; rules = read_rules(rules_path)
    rows, buckets = select_pilot(parts['train'], rules)
    output = data / 'pilot'; output.mkdir(exist_ok=True)
    write_jsonl(output / 'pilot_parents.jsonl', rows)
    exports = [export_row(row) for row in rows]
    write_jsonl(output / 'adaption_pilot.jsonl', exports)
    with (output / 'adaption_pilot.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(exports[0]))
        writer.writeheader(); writer.writerows(exports)
    with (output / 'adaption_pilot.csv').open(encoding='utf-8', newline='') as stream:
        csv_rows = list(csv.DictReader(stream))
    verify_export(read_rows(output / 'pilot_parents.jsonl'), csv_rows, parts)
    verify_export(rows, read_rows(output / 'adaption_pilot.jsonl'), parts)
    manifest = {'source_revision': source['revision'], 'train_sha256': digest(splits / 'train.jsonl'),
                'rules_version': rules['version'], 'rules_sha256': digest(rules_path),
                'code_sha256': digest(here / 'pilot.py'), 'seed': rules['seed'],
                'row_count': len(rows), 'bucket_counts': buckets,
                'column_mapping': rules['column_mapping'],
                'parent_ids': [r['id'] for r in rows],
                'group_ids': sorted({r['group_id'] for r in rows}),
                'checks': {'training_parents_only': True, 'heldout_groups_excluded': True,
                           'csv_round_trip': True, 'jsonl_round_trip': True},
                'status': 'local_export_verified_live_adaption_import_not_tested',
                'purpose': rules['purpose'],
                'outputs': {name: {'sha256': digest(output / name), 'bytes': (output / name).stat().st_size}
                            for name in ['pilot_parents.jsonl', 'adaption_pilot.csv', 'adaption_pilot.jsonl']}}
    write_json(output / 'pilot_manifest.json', manifest)
    print(json.dumps({'row_count': len(rows), 'bucket_counts': buckets, 'checks': manifest['checks'], 'status': manifest['status']}, indent=2))


def smoke(here, data, source, digest, write_json, validate):
    from filtering import run as filter_stage
    from preparation import review, split
    log = io.StringIO()
    try:
        with contextlib.redirect_stdout(log):
            validate()
            filter_stage(here, data, source, digest, write_json)
            review(here, data, source, digest, write_json)
            split(here, data, source, digest, write_json)
            run(here, data, source, digest, write_json)
    finally:
        data.mkdir(exist_ok=True)
        (data / 'smoke_stages.log').write_text(log.getvalue(), encoding='utf-8')
    selection = read_rules(data / 'filtered/selection_report.json')
    scope = read_rules(data / 'reviewed/review_report.json')
    splitting = read_rules(data / 'splits/split_report.json')
    pilot = read_rules(data / 'pilot/pilot_manifest.json')
    if sum(selection['decisions'].values()) != selection['input_qa_pairs']:
        raise ValueError('Selection accounting mismatch')
    if sum(scope['decisions'].values()) != selection['unique_records']:
        raise ValueError('Scope accounting mismatch')
    if sum(v['records'] for v in splitting['splits'].values()) != scope['decisions']['core_candidate']:
        raise ValueError('Split accounting mismatch')
    report = {'status': 'passed', 'source_revision': source['revision'],
              'stages': ['validate', 'filter', 'review', 'split', 'pilot'],
              'candidate_records': selection['unique_records'], 'scope_decisions': scope['decisions'],
              'split_counts': {n: v['records'] for n, v in splitting['splits'].items()},
              'pilot_rows': pilot['row_count'], 'pilot_checks': pilot['checks'],
              'stage_report_sha256': {name: digest(data / name) for name in [
                  'validation_report.json', 'filtered/selection_report.json', 'reviewed/review_report.json',
                  'splits/split_report.json', 'pilot/pilot_manifest.json']},
              'limitations': ['Local data-flow test, not a medical-quality or model-performance evaluation.',
                              'No live Adaption import, augmentation, translation, or inference has run.',
                              'Held-out diabetic-eye coverage remains missing.']}
    write_json(data / 'smoke_report.json', report)
    print(f"SMOKE PASS: five local stages; validated {pilot['row_count']}-row English pilot export.")
    print("Split counts:", report["split_counts"])
    print("Report:", data / "smoke_report.json")
