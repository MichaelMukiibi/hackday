"""Behavioral checks using a tiny synthetic XML archive, not medical assertions."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from filtering import content_key, match_topics, run

HERE = Path(__file__).resolve().parent
RULES = json.loads((HERE / 'filter_rules.json').read_text(encoding='utf-8'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, sort_keys=True), encoding='utf-8')


class FilterTests(unittest.TestCase):
    def test_topic_boundaries(self):
        for focus in ["Reye's syndrome", 'Diabetes insipidus', 'Colorectal cancer screening']:
            self.assertEqual(match_topics(focus, RULES), [])
        self.assertEqual({r['topic'] for r in match_topics('Diabetic Retinopathy', RULES)},
                         {'diabetes', 'diabetic_eye_disease', 'eye_health'})
        self.assertIn('eye_screening', {r['topic'] for r in match_topics('Eye examination', RULES)})

    def test_normalization_keeps_distinct_answers(self):
        self.assertEqual(content_key('ＨＥＬＬＯ  world', 'Answer\ntext'), content_key('hello world', 'answer text'))
        self.assertNotEqual(content_key('Question', 'yes'), content_key('Question', 'no'))

    def test_exports_audit_provenance_and_repeatability(self):
        with tempfile.TemporaryDirectory() as folder:
            here = Path(folder); data = here / 'data'; data.mkdir()
            (here / 'filter_rules.json').write_bytes((HERE / 'filter_rules.json').read_bytes())
            (here / 'filtering.py').write_bytes((HERE / 'filtering.py').read_bytes())
            source = {'revision': 'fixture', 'repository': 'https://example.org/fixture',
                      'license': 'fixture', 'attribution': 'synthetic test'}
            template = '<Document id="1" source="fixture" url="https://example.org/source"><Focus>{}</Focus><QAPairs>{}</QAPairs></Document>'
            pair = '<QAPair pid="1"><Question qid="1-1" qtype="information">{}</Question><Answer>{}</Answer></QAPair>'
            with zipfile.ZipFile(data / 'medquad.zip', 'w') as z:
                z.writestr('root/one/1.xml', template.format('Diabetes', pair.format('A question', 'An answer')))
                z.writestr('root/two/1.xml', template.format('Diabetic Retinopathy', pair.format(' A QUESTION ', 'AN ANSWER')))
                z.writestr('root/three/1.xml', template.format('Eye Diseases', pair.format('Missing answer', '')))
                z.writestr('root/four/1.xml', template.format('Other topic', pair.format('An eye question', 'Mentions diabetes')))
            write_json(data / 'download_manifest.json', {'source': source, 'sha256': digest(data / 'medquad.zip')})
            run(here, data, source, digest, write_json)
            output = data / 'filtered'
            rows = [json.loads(line) for line in (output / 'ijwicare_seed.jsonl').read_text(encoding='utf-8').splitlines()]
            self.assertEqual(len(rows), 1)
            self.assertEqual(len(rows[0]['provenance']), 2)
            self.assertEqual({p['document_path'] for p in rows[0]['provenance']}, {'one/1.xml', 'two/1.xml'})
            self.assertEqual(rows[0]['topics'], ['diabetes', 'diabetic_eye_disease', 'eye_health'])
            self.assertEqual(rows[0]['split'], 'unassigned')
            audit = [json.loads(line) for line in (output / 'selection_audit.jsonl').read_text(encoding='utf-8').splitlines()]
            self.assertEqual(len(audit), 4)
            self.assertEqual({r['decision'] for r in audit}, {'selected', 'duplicate_merged', 'missing_question_or_answer', 'outside_topic_scope'})
            before = {p.name: digest(p) for p in output.iterdir()}
            run(here, data, source, digest, write_json)
            self.assertEqual(before, {p.name: digest(p) for p in output.iterdir()})
            with (data / 'medquad.zip').open('ab') as stream: stream.write(b'tampered')
            with self.assertRaisesRegex(RuntimeError, 'checksum'):
                run(here, data, source, digest, write_json)


if __name__ == '__main__':
    unittest.main()
