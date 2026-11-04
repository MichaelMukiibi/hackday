"""Import, inspect, and quote the pinned pilot in Adaption; no paid launch."""
import argparse
import csv
import hashlib
import io
import json
import os
import sys
import tarfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
STATE = HERE / 'data/adaption'
RECEIPT = ROOT / 'docs/evidence/huggingface-publication.json'
MAPPING = {'prompt':'instruction','completion':'output','context':['input']}


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')


def source_spec(receipt):
    if receipt['row_count']!=10 or receipt['repo_id']!='MichaelMukiibi/ijwicare-medquad-pilot':
        raise ValueError('Unexpected pilot source')
    return {'url':receipt['url']+'/tree/'+receipt['revision'], 'files':['train.csv'],
            'processing_mode':'raw', 'column_mapping':MAPPING}


def imported_dataset(client,receipt):
    source=source_spec(receipt)
    fingerprint=hashlib.sha256(json.dumps(source,sort_keys=True).encode()).hexdigest()
    path=STATE/'import.json'
    if path.exists():
        state=json.loads(path.read_text(encoding='utf-8'))
        if state['request_sha256']!=fingerprint: raise ValueError('Saved import uses another source')
        if not state.get('dataset_id'): raise ValueError('Earlier import outcome is unknown; reconcile it before retrying create')
        return state
    state={'request':source,'request_sha256':fingerprint,'source_revision':receipt['revision'],
           'expected_rows':10,'source_csv_sha256':receipt['verified_files']['train.csv']['sha256'],
           'status':'creating','paid_run_started':False}
    write(path,state)
    result=client.datasets.create(source=source)
    state.update(dataset_id=result.dataset_id,status=result.status)
    write(path,state)
    return state


def check_status(client,state):
    result=client.datasets.get(state['dataset_id'])
    mapping=result.configured_column_mapping
    mapping=mapping.model_dump(exclude_none=True) if hasattr(mapping,'model_dump') else mapping
    summary={'dataset_id':state['dataset_id'],'status':result.status,'row_count':result.row_count,
             'configured_column_mapping':mapping,'run_id':result.run_id,
             'source_revision':state['source_revision'],'paid_run_started':False}
    if result.status=='failed':
        summary['error_code']=getattr(result.error_data,'code',None)
        write(STATE/'status.json',summary)
        raise ValueError('Adaption ingestion failed; check the dataset in the app')
    if result.row_count not in [None,0,10]: raise ValueError('Imported row count differs from ten')
    write(STATE/'status.json',summary)
    return summary


def csv_payloads(payload):
    buffer=io.BytesIO(payload)
    if zipfile.is_zipfile(buffer):
        with zipfile.ZipFile(buffer) as archive:
            return [archive.read(name) for name in sorted(archive.namelist()) if name.endswith('.csv')]
    buffer.seek(0)
    try:
        with tarfile.open(fileobj=buffer,mode='r:*') as archive:
            return [archive.extractfile(member).read() for member in sorted(archive.getmembers(),key=lambda m:m.name)
                    if member.isfile() and member.name.endswith('.csv')]
    except tarfile.ReadError:
        return [payload]


def verify_rows(expected,actual):
    if len(expected)!=10 or len(actual)!=10: raise ValueError('Expected ten source and imported rows')
    # Raw exports canonicalize mapped fields and omit source metadata. Match the
    # complete prompt/answer pair, never a fuzzy prompt or answer alone.
    expected_pairs={}
    for parent in expected:
        key=(parent['instruction']+'\n\n'+parent['input'],parent['output'])
        if key in expected_pairs: raise ValueError('Ambiguous duplicate source prompt/completion pair')
        expected_pairs[key]=parent
    used=set();crosswalk=[]
    for ordinal,row in enumerate(actual):
        if 'original_prompt' in row and 'original_completion' in row:
            key=(row['original_prompt'],row['original_completion'])
            if key not in expected_pairs: raise ValueError('Canonical source prompt/completion changed')
            parent=expected_pairs[key]
        else:
            matches=[p for p in expected if p['id']==row.get('id')]
            if len(matches)!=1: raise ValueError('Imported parent IDs missing or duplicated')
            parent=matches[0]
            if any(row.get(field)!=value for field,value in parent.items()):
                raise ValueError('Imported source value changed')
        if parent['id'] in used: raise ValueError('Duplicate imported parent')
        used.add(parent['id'])
        crosswalk.append({'export_row_index':ordinal,'parent_id':parent['id'],
                          'group_id':parent['group_id'],'split':parent['split'],
                          'match':'exact_source_prompt_and_completion'})
    if used!={p['id'] for p in expected}: raise ValueError('Imported parent coverage differs')
    return crosswalk


def verify_export(client,state,receipt):
    status=check_status(client,state)
    if status['status']!='succeeded' or status['row_count']!=10:
        raise ValueError('Import not ready; rerun status/verify after ingestion completes')
    payload=client.datasets.download(state['dataset_id'],file_format='csv').read()
    parts=csv_payloads(payload)
    rows=[row for part in parts for row in csv.DictReader(io.StringIO(part.decode('utf-8-sig'),newline=''))]
    with (HERE/'data/huggingface/train.csv').open(encoding='utf-8',newline='') as stream:
        expected=list(csv.DictReader(stream))
    local=(HERE/'data/huggingface/train.csv').read_bytes()
    if hashlib.sha256(local).hexdigest()!=receipt['verified_files']['train.csv']['sha256']:
        raise ValueError('Local source CSV differs from published receipt')
    crosswalk=verify_rows(expected,rows)
    write(STATE/'parent_crosswalk.json',crosswalk)
    (STATE/'raw-export.bin').write_bytes(payload)
    report={'dataset_id':state['dataset_id'],'source_revision':receipt['revision'],'rows':len(rows),
            'parent_ids_recovered_by_exact_content_match':True,'source_text_fields_verified':True,
            'source_metadata_columns_retained_by_export':all(name in rows[0] for name in ['id','group_id','split']),
            'parent_crosswalk_sha256':hashlib.sha256((STATE/'parent_crosswalk.json').read_bytes()).hexdigest(),
            'export_columns':sorted(rows[0]),'export_sha256':hashlib.sha256(payload).hexdigest(),
            'source_csv_sha256':state['source_csv_sha256'],'paid_run_started':False}
    write(STATE/'verification.json',report)
    return report


def quote(client,state):
    path=STATE/'verification.json'
    verified=json.loads(path.read_text(encoding='utf-8'))
    if verified['dataset_id']!=state['dataset_id']: raise ValueError('Verify this import before quoting')
    result=client.datasets.adapt(state['dataset_id'],column_mapping=MAPPING,
                                job_specification={'max_rows':10},estimate=True,
                                language_expansion=None)
    if not result.estimate or result.run_id is not None:
        raise ValueError('Unexpected response to estimate-only request')
    report={'dataset_id':state['dataset_id'],'column_mapping':MAPPING,'max_rows':10,
            'estimate_only':True,'run_id':result.run_id,
            'estimated_credits':result.estimated_credits_consumed,
            'estimated_minutes':result.estimated_minutes,'paid_run_started':False}
    write(STATE/'estimate.json',report)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=['import','status','verify','estimate'])
    args=parser.parse_args()
    from dotenv import load_dotenv
    load_dotenv(ROOT/'.env',override=False)
    token=os.environ.get('ADAPTION_API_KEY','').strip()
    if not token or token=='your_adaption_api_key_here':
        print('ADAPTION_API_KEY is not configured in the ignored repository .env file.',file=sys.stderr)
        return 2
    from adaption import Adaption
    # Do not automatically retry non-idempotent dataset creation.
    client=Adaption(api_key=token,max_retries=0,timeout=60)
    receipt=json.loads(RECEIPT.read_text(encoding='utf-8'))
    if args.stage=='import': result=imported_dataset(client,receipt)
    else:
        state=json.loads((STATE/'import.json').read_text(encoding='utf-8'))
        if args.stage=='status': result=check_status(client,state)
        elif args.stage=='verify': result=verify_export(client,state,receipt)
        else: result=quote(client,state)
    print(json.dumps(result,indent=2,ensure_ascii=False))
    return 0


if __name__=='__main__':
    try: code=main()
    except Exception as error:
        # Do not print HTTP requests, headers, or API credentials.
        print('Adaption stage stopped:',type(error).__name__,file=sys.stderr)
        if isinstance(error,ValueError): print(str(error),file=sys.stderr)
        response=getattr(error,'response',None)
        if response is not None: print('HTTP status:',response.status_code,file=sys.stderr)
        code=1
    raise SystemExit(code)
