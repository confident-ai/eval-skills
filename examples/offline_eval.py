"""Synthetic offline demonstration; not a production benchmark or human review."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('artifacts', ROOT / 'skills/eval-run/scripts/artifacts.py')
artifacts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(artifacts)


def app(text):
    # Intentionally narrow application: one expected failure illustrates grading.
    return 'billing' if 'charged' in text.lower() else 'technical'


def run(output):
    output = Path(output)
    source = ROOT / 'examples/fixtures/cases.jsonl'
    cases = artifacts.rows(source, True)
    fingerprint = hashlib.sha256(source.read_bytes() + Path(__file__).read_bytes()).hexdigest()
    manifest = {'schema_version': 1, 'flow': 'synthetic-ticket-routing',
                'dataset_version': hashlib.sha256(source.read_bytes()).hexdigest(),
                'run_id': 'offline-demo', 'run_fingerprint': fingerprint,
                'expected_results': len(cases), 'sample_purpose': 'demonstration',
                'app_version': 'example-v1', 'grader_version': 'exact-category-v1'}
    output.mkdir(parents=True, exist_ok=True)
    if (output / 'manifest.json').exists():
        previous = artifacts.read_json(output / 'manifest.json')
        artifacts.require(previous.get('run_fingerprint') == fingerprint,
                          'Run fingerprint changed; choose a new output directory')
        artifacts.validate(output)
    else:
        artifacts.require(not any(output.iterdir()), 'Output must be empty or a valid resumable demo')
        (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        (output / 'cases.jsonl').write_bytes(source.read_bytes())
    done = {(r['case_id'], r['rep']) for r in artifacts.rows(output / 'results.jsonl')}
    (output / 'traces').mkdir(exist_ok=True)
    with (output / 'results.jsonl').open('a') as results:
        for case in cases:
            if (case['id'], 0) in done:
                continue
            answer = app(case['input'])
            trace_ref = f"traces/{case['id']}_rep0.json"
            trace = [{'role': 'user', 'content': case['input']},
                     {'role': 'assistant', 'content': answer}]
            (output / trace_ref).write_text(json.dumps(trace, indent=2) + '\n')
            row = {'case_id': case['id'], 'rep': 0, 'status': 'ok', 'output': answer,
                   'trace_ref': trace_ref, 'usage': None, 'cost_usd': None,
                   'grades': {'category_correct': {
                       'score': int(answer == case['expected']),
                       'reason': f"Expected {case['expected']}; got {answer}",
                       'grader_version': 'exact-category-v1'}}}
            results.write(json.dumps(row) + '\n')
            results.flush()
    summary = artifacts.validate(output)
    records = artifacts.rows(output / 'results.jsonl')
    passed = sum(r['grades']['category_correct']['score'] for r in records)
    (output / 'report.md').write_text(
        '# Offline demonstration\n\n'
        f'{passed}/{len(records)} synthetic routing examples passed. '
        'This is not a production estimate or calibrated human judgment.\n\n'
        'No model was called; usage and spend are unavailable rather than invented.\n\n'
        '| Case | Pass | Trace |\n| --- | --- | --- |\n' + ''.join(
            f"| {r['case_id']} | {r['grades']['category_correct']['score']} | "
            f"[Trace]({r['trace_ref']}) |\n" for r in records))
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(run(args.output), indent=2))
    except (artifacts.ArtifactError, OSError) as exc:
        parser.exit(1, f'Error: {exc}\n')
