"""Adaption integration behavior tests; no credentials or remote calls."""
import io
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
import adaption_pilot as p


def source_rows():
    return [{'id':str(i),'group_id':'g'+str(i),'split':'train',
             'instruction':'Question '+str(i),'input':'Context "quoted"\n'+str(i),
             'output':'Answer '+str(i)} for i in range(10)]


class AdaptionTests(unittest.TestCase):
    def test_import_uses_raw_pinned_source_and_reuses_saved_id(self):
        receipt={'row_count':10,'repo_id':'MichaelMukiibi/ijwicare-medquad-pilot',
                 'url':'https://huggingface.co/datasets/MichaelMukiibi/ijwicare-medquad-pilot',
                 'revision':'fixed','verified_files':{'train.csv':{'sha256':'fixture'}}}
        client=Mock(); client.datasets.create.return_value=SimpleNamespace(dataset_id='fixture-id',status='pending')
        with tempfile.TemporaryDirectory() as directory, patch.object(p,'STATE',Path(directory)):
            first=p.imported_dataset(client,receipt)
            self.assertEqual(first,p.imported_dataset(client,receipt))
            client.datasets.create.assert_called_once()
            request=client.datasets.create.call_args.kwargs['source']
            self.assertEqual(request['processing_mode'],'raw')
            self.assertTrue(request['url'].endswith('/tree/fixed'))
            self.assertEqual(request['files'],['train.csv'])

    def test_ambiguous_import_is_not_retried(self):
        receipt={'row_count':10,'repo_id':'MichaelMukiibi/ijwicare-medquad-pilot','url':'https://example.org','revision':'fixed',
                 'verified_files':{'train.csv':{'sha256':'fixture'}}}
        client=Mock(); client.datasets.create.side_effect=TimeoutError()
        with tempfile.TemporaryDirectory() as directory, patch.object(p,'STATE',Path(directory)):
            with self.assertRaises(TimeoutError): p.imported_dataset(client,receipt)
            with self.assertRaisesRegex(ValueError,'unknown'): p.imported_dataset(client,receipt)
            client.datasets.create.assert_called_once()

    def test_exact_canonical_content_recovers_parents_after_reordering(self):
        rows=source_rows()
        exported=[{'original_prompt':r['instruction']+'\n\n'+r['input'],'original_completion':r['output']} for r in reversed(rows)]
        matches=p.verify_rows(rows,exported)
        self.assertEqual([m['parent_id'] for m in matches],list(reversed([r['id'] for r in rows])))
        exported[0]['original_completion']='changed'
        with self.assertRaisesRegex(ValueError,'changed'): p.verify_rows(rows,exported)

    def test_duplicate_export_and_count_mismatch_fail(self):
        rows=source_rows()
        exported=[{'original_prompt':r['instruction']+'\n\n'+r['input'],'original_completion':r['output']} for r in rows]
        exported[1]=exported[0]
        with self.assertRaisesRegex(ValueError,'Duplicate'): p.verify_rows(rows,exported)
        with self.assertRaisesRegex(ValueError,'ten'): p.verify_rows(rows,exported[:-1])

    def test_estimate_never_launches_and_rejects_launch_response(self):
        client=Mock();client.datasets.adapt.return_value=SimpleNamespace(estimate=True,run_id=None,
                                                          estimated_credits_consumed=1,estimated_minutes=11)
        with tempfile.TemporaryDirectory() as directory, patch.object(p,'STATE',Path(directory)):
            p.write(p.STATE/'verification.json',{'dataset_id':'fixture'})
            result=p.quote(client,{'dataset_id':'fixture'})
            self.assertTrue(client.datasets.adapt.call_args.kwargs['estimate'])
            self.assertEqual(client.datasets.adapt.call_args.kwargs['job_specification'],{'max_rows':10})
            self.assertFalse(result['paid_run_started'])
            client.datasets.adapt.return_value=SimpleNamespace(estimate=False,run_id='unexpected')
            with self.assertRaisesRegex(ValueError,'estimate-only'): p.quote(client,{'dataset_id':'fixture'})


if __name__=='__main__': unittest.main()
