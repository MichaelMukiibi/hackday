"""Reusable, client-injected adaptation jobs with bounded launch and traceable exports."""
import copy
import csv
import hashlib
import io
import json
import math
from pathlib import Path


def sha_bytes(value):
    return hashlib.sha256(value).hexdigest()


def write_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def dump(value):
    return value.model_dump(exclude_none=True) if hasattr(value,'model_dump') else value


def request_spec(config):
    fields=('column_mapping','recipe_specification','job_specification','brand_controls','training_type','language_expansion')
    if set(config)-set(fields)-{'version'}: raise ValueError('Unsupported recipe fields')
    result={name:copy.deepcopy(config[name]) for name in fields if name in config}
    rows=result.get('job_specification',{}).get('max_rows')
    if isinstance(rows,bool) or not isinstance(rows,int) or rows<1:
        raise ValueError('max_rows must be a positive integer')
    if set(result['job_specification'])!={'max_rows'}:
        raise ValueError('Run idempotency is controlled by the job manager')
    if result.get('language_expansion') is not None:
        raise ValueError('This workflow supports adaptation only; use a separate expansion workflow')
    # Always clear previously saved language expansion state.
    result['language_expansion']=None
    return result


class AdaptationJob:
    def __init__(self,client,dataset_id,folder,config):
        self.client=client
        self.dataset_id=dataset_id
        self.folder=Path(folder)
        self.request=request_spec(config)
        value=json.dumps({'dataset_id':dataset_id,'request':self.request},sort_keys=True)
        self.fingerprint=sha_bytes(value.encode())
        self.key='ijwicare-adapt-'+self.fingerprint[:32]

    def estimate(self):
        result=self.client.datasets.adapt(self.dataset_id,**self.request,estimate=True)
        if result.estimate is not True or result.run_id is not None:
            raise ValueError('Unexpected response to estimate-only request')
        credits=result.estimated_credits_consumed
        if isinstance(credits,bool) or not isinstance(credits,(int,float)) or not math.isfinite(credits) or credits<0:
            raise ValueError('Provider returned an invalid credit estimate')
        report={'dataset_id':self.dataset_id,'request_sha256':self.fingerprint,
                'request':self.request,'estimate_only':True,'estimated_credits':credits,
                'estimated_minutes':result.estimated_minutes,'run_id':None,'paid_run_started':False}
        write_json(self.folder/'estimate.json',report)
        return report

    def launch(self,max_credits):
        if isinstance(max_credits,bool) or not isinstance(max_credits,(int,float)) or not math.isfinite(max_credits) or max_credits<0:
            raise ValueError('A finite, nonnegative max_credits is required')
        path=self.folder/'launch.json'
        saved=read_json(path) if path.exists() else None
        if saved:
            if saved['request_sha256']!=self.fingerprint or saved['idempotency_key']!=self.key:
                raise ValueError('This run folder belongs to a different request; preserve it and use a new run folder')
            if saved.get('run_id'): return saved
            # An ambiguous request may already have spent credits. Replay exactly
            # the same persisted request/key, never a changed recipe or fresh key.
            if saved['credit_cap']>max_credits:
                raise ValueError('Cannot lower the cap while retrying an uncertain launch')
            request=copy.deepcopy(saved['launch_request'])
        else:
            snapshot=self.client.datasets.get(self.dataset_id)
            if snapshot.status!='succeeded': raise ValueError('Source dataset is not ready')
            if snapshot.run_id and not snapshot.run_id.startswith('passthrough-'):
                raise ValueError('Dataset has another run; inspect it before launching a new job')
            if snapshot.row_count!=self.request['job_specification']['max_rows']:
                raise ValueError('Source row count does not match this bounded pilot')
            estimate=self.estimate()
            if estimate['estimated_credits']>max_credits:
                raise ValueError('Estimated cost exceeds max_credits; no paid request sent')
            request=copy.deepcopy(self.request)
            request['job_specification']['idempotency_key']=self.key
            saved={'dataset_id':self.dataset_id,'request_sha256':self.fingerprint,
                   'idempotency_key':self.key,'launch_request':request,'credit_cap':max_credits,
                   'estimated_credits':estimate['estimated_credits'],'status':'launch_outcome_unknown',
                   'paid_request_may_have_started':True}
            write_json(path,saved)
        result=self.client.datasets.adapt(self.dataset_id,**request,estimate=False)
        if result.estimate is not False or not result.run_id:
            raise ValueError('Launch response has no paid run ID; retain state and replay the same key')
        saved.update(run_id=result.run_id,status='launched')
        write_json(path,saved)
        return saved

    def launched(self):
        saved=read_json(self.folder/'launch.json')
        if saved['request_sha256']!=self.fingerprint or not saved.get('run_id'):
            raise ValueError('Run state is missing or belongs to another recipe')
        return saved

    def status(self):
        saved=self.launched()
        snapshot=self.client.datasets.get(self.dataset_id)
        if snapshot.run_id!=saved['run_id']:
            raise ValueError('Provider dataset now points to another run; refusing to mix outputs')
        report={'dataset_id':self.dataset_id,'run_id':saved['run_id'],'status':snapshot.status,
                'row_count':snapshot.row_count,'progress':dump(snapshot.progress),
                'error_code':getattr(snapshot.error_data,'code',None)}
        write_json(self.folder/'status.json',report)
        return report

    def download(self):
        status=self.status()
        if status['status']!='succeeded': raise ValueError('Run has not succeeded; nothing downloaded')
        payload=self.client.datasets.download(self.dataset_id,file_format='csv').read()
        # Check again so a concurrently replaced run cannot silently be attributed.
        after=self.status()
        if after['status']!='succeeded': raise ValueError('Run changed during download')
        self.folder.mkdir(parents=True,exist_ok=True)
        (self.folder/'adapted-export.bin').write_bytes(payload)
        report={'dataset_id':self.dataset_id,'run_id':status['run_id'],
                'request_sha256':self.fingerprint,'format':'csv','bytes':len(payload),'sha256':sha_bytes(payload)}
        write_json(self.folder/'download.json',report)
        return report


def inspect_result(folder,expected,decode_csv,verify_parents):
    folder=Path(folder)
    launch=read_json(folder/'launch.json');receipt=read_json(folder/'download.json')
    if receipt['dataset_id']!=launch['dataset_id'] or receipt['run_id']!=launch['run_id'] or receipt['request_sha256']!=launch['request_sha256']:
        raise ValueError('Download receipt does not match launched job')
    payload=(folder/'adapted-export.bin').read_bytes()
    if sha_bytes(payload)!=receipt['sha256']: raise ValueError('Downloaded export checksum mismatch')
    rows=[row for part in decode_csv(payload) for row in csv.DictReader(io.StringIO(part.decode('utf-8-sig'),newline=''))]
    crosswalk=verify_parents(expected,rows)
    source={row['id']:row for row in expected}
    restored=[]
    for row,link in zip(rows,crosswalk):
        if not {'original_prompt','original_completion','enhanced_completion'}.issubset(row):
            raise ValueError('Adapted export is missing canonical comparison columns')
        if not row.get('enhanced_completion','').strip(): raise ValueError('Adapted completion is empty')
        parent=source[link['parent_id']]
        enhanced_prompt=row.get('enhanced_prompt','')
        restored.append({**link,'dataset_id':launch['dataset_id'],'run_id':launch['run_id'],
                         'original_prompt':row['original_prompt'],'original_completion':row['original_completion'],
                         'enhanced_prompt':enhanced_prompt,'enhanced_completion':row['enhanced_completion'],
                         'prompt_changed':bool(enhanced_prompt.strip()) and enhanced_prompt!=row['original_prompt'],
                         'completion_changed':row['enhanced_completion']!=row['original_completion'],
                         'language':parent.get('language','en'),
                         'clinical_review_status':'not_reviewed','language_review_status':'not_reviewed'})
    # Data are written only after every row and parent link passes verification.
    with (folder/'adapted_rows.jsonl').open('w',encoding='utf-8',newline='\n') as stream:
        for row in restored: stream.write(json.dumps(row,ensure_ascii=False,sort_keys=True)+'\n')
    with (folder/'comparison.csv').open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(restored[0]));writer.writeheader();writer.writerows(restored)
    report={'dataset_id':launch['dataset_id'],'run_id':launch['run_id'],'rows':len(restored),
            'parent_links_verified':True,'changed_prompts':sum(r['prompt_changed'] for r in restored),
            'changed_completions':sum(r['completion_changed'] for r in restored),
            'review_status':'not_reviewed','quality_improvement_measured':False,
            'outputs':{name:sha_bytes((folder/name).read_bytes()) for name in ['adapted_rows.jsonl','comparison.csv']}}
    write_json(folder/'inspection.json',report)
    return report
