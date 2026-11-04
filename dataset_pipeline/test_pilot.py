"""Technical pilot checks with invented rows; no remote services."""
import copy
import json
from pathlib import Path
import unittest
from pilot import export_row, select_pilot, verify_export

RULES = json.loads((Path(__file__).parent / 'pilot_rules.json').read_text(encoding='utf-8-sig'))


def fixture():
    rows=[]
    for topic,count in [('diabetic_eye_disease',4),('diabetes',3),('eye_health',3)]:
        for i in range(count):
            key=f'{topic}-{i}'
            rows.append({'id':key, 'question':'Question '+key, 'answer':'Answer '+key,
                         'topics':[topic], 'language':'en', 'split':'train', 'group_id':'g-'+key,
                         'focus':topic, 'source_revision':'fixture',
                         'clinical_review_status':'not_reviewed', 'language_review_status':'not_reviewed',
                         'provenance':[{'source_url':'https://example.org/'+key}],
                         'scope_review':{'decision':'core_candidate','local_context_flags':[]}})
    return rows


class PilotTests(unittest.TestCase):
    def test_selection_is_order_independent_and_fail_closed(self):
        rows=fixture()
        chosen,counts=select_pilot(rows,RULES)
        self.assertEqual(len(chosen),10)
        self.assertEqual(chosen,select_pilot(list(reversed(rows)),RULES)[0])
        self.assertEqual(counts,{'diabetic_eye_disease':4,'diabetes':3,'eye_health':3})
        rows[0]['split']='test'
        with self.assertRaisesRegex(ValueError,'Insufficient'): select_pilot(rows,RULES)

    def test_export_checks_reject_mutation(self):
        rows=fixture();exports=[export_row(r) for r in rows]
        parts={'train':rows,'validation':[],'test':[]}
        verify_export(rows,exports,parts)
        exports[0]['output']='changed answer'
        with self.assertRaisesRegex(ValueError,'round-trip'): verify_export(rows,exports,parts)

    def test_heldout_group_and_parent_mismatch_rejected(self):
        rows=fixture(); exports=[export_row(r) for r in rows]
        held=copy.deepcopy(rows[0]);held['id']='held-out'
        parts={'train':rows,'validation':[held],'test':[]}
        with self.assertRaisesRegex(ValueError,'Held-out'): verify_export(rows,exports,parts)
        parts['validation']=[]
        changed=copy.deepcopy(rows);changed[0]['answer']='changed'
        with self.assertRaisesRegex(ValueError,'parent'): verify_export(changed,exports,parts)


if __name__=='__main__': unittest.main()
