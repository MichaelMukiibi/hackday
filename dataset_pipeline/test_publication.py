import csv
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from publish_huggingface import verified_package

HERE=Path(__file__).parent

def package_fixture(folder):
    from pilot import export_row
    parents=[]
    for i in range(10):
        parents.append({'id':str(i),'question':'Question '+str(i),'answer':'Answer '+str(i),
                        'focus':'Synthetic fixture','group_id':'group-'+str(i),'split':'train','language':'en',
                        'source_revision':'fixture','clinical_review_status':'not_reviewed','language_review_status':'not_reviewed',
                        'provenance':[{'source_url':'https://example.org/'+str(i)}]})
    (folder/'README.md').write_text('Synthetic fixture card',encoding='utf-8')
    (folder/'LICENSE').write_text('Synthetic fixture license',encoding='utf-8')
    (folder/'provenance.json').write_text(json.dumps(parents),encoding='utf-8')
    exports=[export_row(r) for r in parents]
    with (folder/'train.csv').open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(exports[0]));writer.writeheader();writer.writerows(exports)
    manifest={'row_count':10,'parent_ids':[r['id'] for r in parents],
              'files':{name:{'sha256':hashlib.sha256((folder/name).read_bytes()).hexdigest(),'bytes':(folder/name).stat().st_size}
                       for name in ['README.md','LICENSE','train.csv','provenance.json']}}
    (folder/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')


class PublicationTests(unittest.TestCase):
    def test_extra_file_is_rejected_before_any_api_call(self):
        with tempfile.TemporaryDirectory() as name:
            folder=Path(name)
            (folder/'.env').write_text('synthetic placeholder',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'allowlisted'): verified_package(folder)

    def test_missing_package_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            with self.assertRaisesRegex(ValueError,'allowlisted'): verified_package(Path(name))

    def test_complete_package_is_accepted(self):
        with tempfile.TemporaryDirectory() as name:
            folder=Path(name);package_fixture(folder)
            contents,manifest=verified_package(folder)
            self.assertEqual(len(contents),5)
            self.assertEqual(manifest['row_count'],10)

    def test_modified_csv_is_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            folder=Path(name);package_fixture(folder)
            with (folder/'train.csv').open('a',encoding='utf-8') as stream: stream.write('changed')
            with self.assertRaisesRegex(ValueError,'checksum'): verified_package(folder)

    def test_metadata_disagreement_is_rejected_even_with_valid_hashes(self):
        with tempfile.TemporaryDirectory() as name:
            folder=Path(name);package_fixture(folder)
            parents=json.loads((folder/'provenance.json').read_text(encoding='utf-8'))
            parents[0]['split']='test'
            (folder/'provenance.json').write_text(json.dumps(parents),encoding='utf-8')
            manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
            contents=(folder/'provenance.json').read_bytes()
            manifest['files']['provenance.json']={'sha256':hashlib.sha256(contents).hexdigest(),'bytes':len(contents)}
            (folder/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'provenance'): verified_package(folder)

if __name__=='__main__': unittest.main()
