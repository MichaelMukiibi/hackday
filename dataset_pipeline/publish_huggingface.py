"""Explicit, allowlisted Hugging Face publication using HF_TOKEN from .env."""
import argparse
import csv
import hashlib
import io
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FOLDER = HERE / 'data/huggingface'
REPO_ID = 'MichaelMukiibi/ijwicare-medquad-pilot'
FILES = {'README.md', 'LICENSE', 'train.csv', 'provenance.json', 'manifest.json'}


def verified_package(folder):
    if {p.name for p in folder.iterdir()} != FILES or not all((folder/name).is_file() for name in FILES):
        raise ValueError('Publication folder must contain exactly the five allowlisted files')
    manifest = json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    if set(manifest['files']) != FILES-{'manifest.json'}:
        raise ValueError('Manifest allowlist mismatch')
    contents = {name:(folder/name).read_bytes() for name in sorted(FILES)}
    for name, details in manifest['files'].items():
        if hashlib.sha256(contents[name]).hexdigest()!=details['sha256'] or len(contents[name])!=details['bytes']:
            raise ValueError('Publication checksum mismatch: '+name)
    rows=list(csv.DictReader(io.StringIO(contents['train.csv'].decode('utf-8'),newline='')))
    parents=json.loads(contents['provenance.json'])
    from pilot import export_row
    if len(rows)!=10 or manifest['row_count']!=10 or len(parents)!=10:
        raise ValueError('Expected exactly ten pilot rows')
    if rows!=[export_row(row) for row in parents]:
        raise ValueError('Published rows differ from provenance parents')
    if any(row['split']!='train' or row['language']!='en' for row in rows):
        raise ValueError('Only English training parents may be published')
    if [row['id'] for row in rows]!=manifest['parent_ids'] or len(set(manifest['parent_ids']))!=10:
        raise ValueError('Parent ID mismatch or duplicates')
    return contents,manifest


def remote_bytes(name,revision):
    from huggingface_hub import hf_hub_url
    request=urllib.request.Request(hf_hub_url(REPO_ID,name,repo_type='dataset',revision=revision),
                                   headers={'User-Agent':'IjwiCare-publication-verifier/1'})
    with urllib.request.urlopen(request,timeout=60) as response: return response.read()


def publish(api, contents, manifest):
    from huggingface_hub import CommitOperationAdd
    before=api.repo_info(REPO_ID,repo_type='dataset',revision='main')
    if before.private: raise ValueError('Repository is private; visibility will not be changed automatically')
    names={entry.rfilename for entry in before.siblings}
    if names-(FILES|{'.gitattributes'}): raise ValueError('Unexpected remote files; refusing to mix datasets')
    identical=FILES.issubset(names)
    if identical:
        identical=all(remote_bytes(name,before.sha)==contents[name] for name in sorted(FILES))
    if identical:
        revision=before.sha
    else:
        commit=api.create_commit(repo_id=REPO_ID,repo_type='dataset',revision='main',parent_commit=before.sha,
                                 operations=[CommitOperationAdd(path_in_repo=name,path_or_fileobj=contents[name]) for name in sorted(FILES)],
                                 commit_message='Publish verified ten-row IjwiCare MedQuAD English pilot')
        revision=commit.oid
    verified={}
    for name in sorted(FILES):
        published=remote_bytes(name,revision)
        if published!=contents[name]: raise ValueError('Remote bytes differ from local package: '+name)
        verified[name]={'sha256':hashlib.sha256(published).hexdigest(),'bytes':len(published)}
    receipt={'repo_id':REPO_ID,'repo_type':'dataset','visibility':'public','revision':revision,
             'url':f'https://huggingface.co/datasets/{REPO_ID}',
             'dataset_file_url':f'https://huggingface.co/datasets/{REPO_ID}/resolve/{revision}/train.csv',
             'row_count':10,'pipeline_git_commit':manifest['pipeline_git_commit'],
             'column_mapping':manifest['column_mapping'],'verified_files':verified,
             'verification':'All five files fetched anonymously at pinned revision and matched byte-for-byte',
             'adaption_import_status':'not_run'}
    (HERE/'data/huggingface-publication.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(receipt,indent=2))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--publish',action='store_true',help='Upload the verified package; default only checks local package and authentication')
    args=parser.parse_args()
    contents,manifest=verified_package(FOLDER)
    from dotenv import load_dotenv
    load_dotenv(ROOT/'.env',override=False)
    token=os.environ.get('HF_TOKEN','').strip()
    if not token or token=='your_huggingface_token_here':
        print('HF_TOKEN is not configured. Add it to this repository\'s ignored .env file.',file=sys.stderr)
        return 2
    from huggingface_hub import HfApi
    api=HfApi(token=token)
    identity=api.whoami()
    if identity['name']!=REPO_ID.split('/')[0]: raise ValueError('Authenticated account does not match the selected repository owner')
    print('Authenticated account:',identity['name'],'| verified local rows:',manifest['row_count'])
    if args.publish: publish(api,contents,manifest)
    else: print('Preflight passed. No remote changes made. Use --publish to upload.')
    return 0


if __name__=='__main__':
    try: result=main()
    except Exception as error:
        # Avoid dumping HTTP request/authorization details into logs.
        print('Publication stopped:',type(error).__name__,file=sys.stderr)
        result=1
    raise SystemExit(result)
