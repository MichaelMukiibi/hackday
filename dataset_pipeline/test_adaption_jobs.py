"""Offline adaptation-job checks: cost bounds, retries, run ownership, and export traceability."""
import copy
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace as Obj
from unittest.mock import Mock
from adaption_jobs import AdaptationJob, inspect_result, read_json, sha_bytes, write_json
from adaption_pilot import csv_payloads, verify_rows

CONFIG=json.loads((Path(__file__).parent/'adaption_recipe.json').read_text(encoding='utf-8-sig'))


def client_fixture(credits=1):
    client=Mock()
    client.datasets.get.return_value=Obj(status='succeeded',run_id='passthrough-fixture',row_count=10,progress=None,error_data=None)
    quote=Obj(estimate=True,run_id=None,estimated_credits_consumed=credits,estimated_minutes=11)
    launch=Obj(estimate=False,run_id='adapt-fixture',estimated_credits_consumed=credits,estimated_minutes=11)
    client.datasets.adapt.side_effect=lambda *args,**kwargs: quote if kwargs['estimate'] else launch
    return client


class JobTests(unittest.TestCase):
    def test_cap_blocks_paid_request_and_invalid_numbers(self):
        with tempfile.TemporaryDirectory() as folder:
            client=client_fixture(credits=2);job=AdaptationJob(client,'fixture',folder,CONFIG)
            with self.assertRaisesRegex(ValueError,'exceeds'):job.launch(1)
            self.assertEqual(client.datasets.adapt.call_count,1)
            self.assertTrue(client.datasets.adapt.call_args.kwargs['estimate'])
            self.assertFalse((Path(folder)/'launch.json').exists())
            for value in [float('nan'),float('inf'),-1,True]:
                with self.assertRaises(ValueError):job.launch(value)

    def test_launch_is_bounded_and_saved_run_is_reused(self):
        with tempfile.TemporaryDirectory() as folder:
            client=client_fixture();job=AdaptationJob(client,'fixture',folder,CONFIG)
            first=job.launch(1)
            self.assertEqual(first,job.launch(1))
            self.assertEqual(client.datasets.adapt.call_count,2)
            actual=client.datasets.adapt.call_args.kwargs
            self.assertFalse(actual['estimate'])
            self.assertEqual(actual['job_specification']['max_rows'],10)
            self.assertEqual(actual['job_specification']['idempotency_key'],job.key)
            self.assertIsNone(actual['language_expansion'])

    def test_uncertain_launch_replays_exact_key_and_request(self):
        with tempfile.TemporaryDirectory() as folder:
            client=client_fixture();seen=[]
            def responses(*args,**kwargs):
                if kwargs['estimate']:return Obj(estimate=True,run_id=None,estimated_credits_consumed=1,estimated_minutes=11)
                seen.append(copy.deepcopy(kwargs))
                if len(seen)==1:raise TimeoutError()
                return Obj(estimate=False,run_id='adapt-fixture')
            client.datasets.adapt.side_effect=responses
            job=AdaptationJob(client,'fixture',folder,CONFIG)
            with self.assertRaises(TimeoutError):job.launch(1)
            self.assertEqual(job.launch(1)['run_id'],'adapt-fixture')
            self.assertEqual(seen[0],seen[1])

    def test_changed_recipe_and_foreign_run_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            client=client_fixture();job=AdaptationJob(client,'fixture',folder,CONFIG);job.launch(1)
            changed=copy.deepcopy(CONFIG);changed['brand_controls']['length']='detailed'
            with self.assertRaisesRegex(ValueError,'different request'):AdaptationJob(client,'fixture',folder,changed).launch(1)
            client.datasets.get.return_value.run_id='different-run'
            with self.assertRaisesRegex(ValueError,'another run'):job.download()
            client.datasets.download.assert_not_called()

    def test_status_and_download_require_actual_success(self):
        with tempfile.TemporaryDirectory() as folder:
            client=client_fixture();job=AdaptationJob(client,'fixture',folder,CONFIG);job.launch(1)
            client.datasets.get.return_value=Obj(status='running',run_id='adapt-fixture',row_count=10,progress={'percent':10},error_data=None)
            self.assertEqual(job.status()['status'],'running')
            with self.assertRaisesRegex(ValueError,'not succeeded'):job.download()
            client.datasets.get.return_value.status='succeeded'
            client.datasets.download.return_value.read.return_value=b'fixture bytes'
            receipt=job.download()
            self.assertEqual(receipt['sha256'],sha_bytes(b'fixture bytes'))
            self.assertEqual(receipt['run_id'],'adapt-fixture')

    def test_inspection_restores_parents_and_flags_changes_without_quality_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            parents=[{'id':str(i),'group_id':'g'+str(i),'split':'train','language':'en',
                      'instruction':'Question '+str(i),'input':'Context '+str(i),'output':'Answer '+str(i)} for i in range(10)]
            rows=[{'original_prompt':p['instruction']+'\n\n'+p['input'],'original_completion':p['output'],
                   'enhanced_prompt':'','enhanced_completion':'Edited '+p['output']} for p in reversed(parents)]
            stream=io.StringIO(newline='');writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
            payload=stream.getvalue().encode()
            write_json(folder/'launch.json',{'dataset_id':'fixture','run_id':'run','request_sha256':'recipe'})
            write_json(folder/'download.json',{'dataset_id':'fixture','run_id':'run','request_sha256':'recipe','sha256':sha_bytes(payload)})
            (folder/'adapted-export.bin').write_bytes(payload)
            report=inspect_result(folder,parents,csv_payloads,verify_rows)
            self.assertEqual(report['changed_completions'],10)
            self.assertFalse(report['quality_improvement_measured'])
            restored=[json.loads(line) for line in (folder/'adapted_rows.jsonl').read_text(encoding='utf-8').splitlines()]
            self.assertEqual(restored[0]['parent_id'],'9')
            self.assertEqual(restored[0]['clinical_review_status'],'not_reviewed')
            (folder/'adapted-export.bin').write_bytes(b'corrupted')
            with self.assertRaisesRegex(ValueError,'checksum'):inspect_result(folder,parents,csv_payloads,verify_rows)

    def test_expansion_and_invalid_row_cap_rejected(self):
        config=copy.deepcopy(CONFIG);config['language_expansion']={'type':'translate','languages':['rw'],'sample_rate':1}
        with self.assertRaisesRegex(ValueError,'expansion'):AdaptationJob(Mock(),'fixture','unused',config)
        config=copy.deepcopy(CONFIG);config['job_specification']['max_rows']=0
        with self.assertRaisesRegex(ValueError,'positive'):AdaptationJob(Mock(),'fixture','unused',config)


if __name__=='__main__':unittest.main()
