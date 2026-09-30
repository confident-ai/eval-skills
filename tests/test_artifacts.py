import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
artifacts = load('artifacts', ROOT / 'skills/eval-run/scripts/artifacts.py')
demo = load('demo', ROOT / 'examples/offline_eval.py')


class ArtifactsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.bundle = Path(self.temp.name) / 'bundle'
        demo.run(self.bundle)

    def rewrite_rows(self, name, rows):
        (self.bundle / name).write_text(''.join(json.dumps(r) + '\n' for r in rows))

    def mutate_result(self, **changes):
        rows = artifacts.rows(self.bundle / 'results.jsonl')
        rows[0].update(changes)
        self.rewrite_rows('results.jsonl', rows)

    def test_scenario_bundles(self):
        for name in ("production-agent", "existing-evals"):
            self.assertEqual(artifacts.validate(ROOT / "examples/fixtures" / name)["cases"], 1)

    def test_demo_known_outcomes(self):
        self.assertEqual(artifacts.validate(self.bundle)['results'], 3)
        rows = artifacts.rows(self.bundle / 'results.jsonl')
        self.assertEqual(sum(r['grades']['category_correct']['score'] for r in rows), 2)
        self.assertIsNone(rows[0]['usage'])

    def test_resume_idempotent(self):
        original = (self.bundle / 'results.jsonl').read_bytes()
        demo.run(self.bundle)
        self.assertEqual(original, (self.bundle / 'results.jsonl').read_bytes())

    def test_resume_partial(self):
        rows = artifacts.rows(self.bundle / 'results.jsonl')
        self.rewrite_rows('results.jsonl', rows[:1])
        self.assertFalse(artifacts.validate(self.bundle)['complete'])
        demo.run(self.bundle)
        self.assertTrue(artifacts.validate(self.bundle)['complete'])
        self.assertEqual(len(artifacts.rows(self.bundle / 'results.jsonl')), 3)

    def test_resume_rejects_changed_fingerprint(self):
        manifest = artifacts.read_json(self.bundle / 'manifest.json')
        manifest['run_fingerprint'] = 'different'
        (self.bundle / 'manifest.json').write_text(json.dumps(manifest))
        with self.assertRaisesRegex(demo.artifacts.ArtifactError, 'fingerprint'):
            demo.run(self.bundle)

    def test_duplicate_result(self):
        rows = artifacts.rows(self.bundle / 'results.jsonl')
        self.rewrite_rows('results.jsonl', rows + [rows[0]])
        with self.assertRaisesRegex(artifacts.ArtifactError, 'Duplicate terminal'):
            artifacts.validate(self.bundle)

    def test_missing_trace(self):
        self.mutate_result(trace_ref='traces/absent.json')
        with self.assertRaisesRegex(artifacts.ArtifactError, 'Missing referenced'):
            artifacts.validate(self.bundle)

    def test_traversal(self):
        self.mutate_result(trace_ref='../secret.json')
        with self.assertRaisesRegex(artifacts.ArtifactError, 'Unsafe reference'):
            artifacts.validate(self.bundle)

    def test_symlink_escape(self):
        outside = Path(self.temp.name) / 'outside.json'
        outside.write_text('{}')
        (self.bundle / 'escape.json').symlink_to(outside)
        self.mutate_result(trace_ref='escape.json')
        with self.assertRaisesRegex(artifacts.ArtifactError, 'escapes bundle'):
            artifacts.validate(self.bundle)

    def test_usage_negative_or_boolean_rejected(self):
        for value in (-1, True, 1.5):
            self.mutate_result(usage={'input_tokens': value})
            with self.assertRaises(artifacts.ArtifactError):
                artifacts.validate(self.bundle)

    def test_grade_nan_rejected(self):
        self.mutate_result(grades={'x': {'score': float('nan'), 'reason': '', 'grader_version': 'v1'}})
        with self.assertRaisesRegex(artifacts.ArtifactError, 'finite'):
            artifacts.validate(self.bundle)

    def test_errors_are_not_zero_grades(self):
        self.mutate_result(status='timeout', output=None)
        with self.assertRaisesRegex(artifacts.ArtifactError, 'cannot carry'):
            artifacts.validate(self.bundle)
        self.mutate_result(grades={})
        self.assertEqual(artifacts.validate(self.bundle)['statuses']['timeout'], 1)

    def test_confirmation_requires_reviewer(self):
        row = {'id': 'a1', 'case_id': 'ticket-01', 'criterion_id': 'routing',
               'origin': 'agent', 'status': 'confirmed', 'note': 'Check routing'}
        self.rewrite_rows('annotations.jsonl', [row])
        with self.assertRaisesRegex(artifacts.ArtifactError, 'reviewed_by'):
            artifacts.validate(self.bundle)
        row['reviewed_by'] = 'fixture-reviewer'
        self.rewrite_rows('annotations.jsonl', [row])
        self.assertEqual(artifacts.validate(self.bundle)['annotations'], 1)

    def test_grouped_split_is_deterministic(self):
        cases = artifacts.rows(self.bundle / 'cases.jsonl')
        cases.append({**cases[0], 'id': 'related'})
        a = artifacts.make_splits(cases, 42)
        self.assertEqual(a, artifacts.make_splits(list(reversed(cases)), 42))
        artifacts.validate_splits(cases, a)
        self.assertTrue(any('related' in ids and 'ticket-01' in ids for ids in a.values()))

    def test_split_leakage(self):
        cases = artifacts.rows(self.bundle / 'cases.jsonl')
        cases[1]['group_id'] = cases[0]['group_id']
        with self.assertRaisesRegex(artifacts.ArtifactError, 'crosses'):
            artifacts.validate_splits(cases, {'development': ['ticket-01'],
                                            'test': ['ticket-02', 'ticket-03']})

    def test_too_few_groups(self):
        cases = artifacts.rows(self.bundle / 'cases.jsonl')[:2]
        with self.assertRaisesRegex(artifacts.ArtifactError, 'three independent'):
            artifacts.make_splits(cases, 42)

    def test_duplicate_attempt(self):
        row = {'case_id': 'ticket-01', 'rep': 0, 'attempt': 1, 'status': 'timeout'}
        self.rewrite_rows('attempts.jsonl', [row, row])
        with self.assertRaisesRegex(artifacts.ArtifactError, 'Duplicate attempt'):
            artifacts.validate(self.bundle)

    def test_unknown_annotation_case(self):
        row = {'id': 'a1', 'case_id': 'absent', 'criterion_id': 'routing',
               'origin': 'agent', 'status': 'suggested', 'note': 'Check routing'}
        self.rewrite_rows('annotations.jsonl', [row])
        with self.assertRaisesRegex(artifacts.ArtifactError, 'Unknown annotation'):
            artifacts.validate(self.bundle)

    def test_incomplete_split(self):
        cases = artifacts.rows(self.bundle / 'cases.jsonl')
        with self.assertRaisesRegex(artifacts.ArtifactError, 'cover all'):
            artifacts.validate_splits(cases, {'development': ['ticket-01']})


if __name__ == '__main__':
    unittest.main()
