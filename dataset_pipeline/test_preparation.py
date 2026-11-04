"""Preparation behavior tests using invented text and source identities."""
import copy
import json
from pathlib import Path
import unittest
from preparation import assign_groups, build_groups, scope_decision

HERE = Path(__file__).resolve().parent
REVIEW = json.loads((HERE / 'review_rules.json').read_text(encoding='utf-8-sig'))
SPLIT = json.loads((HERE / 'split_rules.json').read_text(encoding='utf-8-sig'))


def row(key, focus, source='fixture', document=None, url=None, question=None, answer=None):
    return {'id': key, 'question': question or 'Question ' + key,
            'answer': answer or 'Answer ' + key,
            'provenance': [{'document_path': document or key + '.xml', 'focus': focus,
                            'source': source, 'source_url': url or 'https://example.org/' + key}]}


class PreparationTests(unittest.TestCase):
    def test_scope_triage_and_common_condition_exception(self):
        self.assertEqual(scope_decision(row('a', 'Rare corneal condition', 'GARD'), REVIEW)[0], 'deferred_specialist')
        self.assertEqual(scope_decision(row('a', 'type 1 diabetes', 'GHR'), REVIEW)[0], 'core_candidate')
        self.assertEqual(scope_decision(row('a', 'Financial Help for Diabetes Care'), REVIEW)[0], 'deferred_local_context')
        decision, _, flags = scope_decision(row('a', 'Diabetes', answer='Contact Medicare'), REVIEW)
        self.assertEqual(decision, 'core_candidate')
        self.assertTrue(flags)

    def test_transitive_document_alias_and_url_groups(self):
        rows = [row('a', 'Diabetes Type 1', document='one.xml'),
                row('b', 'Other topic', document='one.xml'),
                row('c', 'type 1 diabetes', url='https://example.org/shared#one'),
                row('d', 'Different topic', url='http://example.org/shared#two')]
        groups, _ = build_groups(rows, SPLIT)
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(next(iter(groups.values()))), 4)

    def test_duplicate_question_and_answer_links(self):
        rows = [row('a', 'One', question='Same question'), row('b', 'Two', question='SAME QUESTION'),
                row('c', 'Three', answer='Answer b')]
        groups, _ = build_groups(rows, SPLIT)
        self.assertEqual(len(groups), 1)

    def test_near_duplicate_answers_grouped(self):
        text = ' '.join('word' + str(i) for i in range(100))
        rows = [row('a', 'One', answer=text), row('b', 'Two', answer=text + ' extra')]
        groups, edges = build_groups(rows, SPLIT)
        self.assertEqual(len(groups), 1)
        self.assertEqual(edges['near_duplicate_answer'], 1)

    def test_split_order_independence_coverage_and_ratio_validation(self):
        groups = {str(i): [row(str(i), 'Topic ' + str(i))] for i in range(20)}
        first = assign_groups(groups, SPLIT)
        self.assertEqual(first, assign_groups(dict(reversed(list(groups.items()))), SPLIT))
        self.assertEqual(set(first.values()), {'train', 'validation', 'test'})
        self.assertEqual(sum(v == 'train' for v in first.values()), 16)
        invalid = copy.deepcopy(SPLIT); invalid['ratios']['train'] = 0.9
        with self.assertRaises(ValueError): assign_groups(groups, invalid)
        with self.assertRaises(ValueError): assign_groups({'a': []}, SPLIT)


if __name__ == '__main__': unittest.main()
