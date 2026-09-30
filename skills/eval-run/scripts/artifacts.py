"""Validate portable eval bundles, inspect exports, and create group splits."""
import argparse
import json
import math
import random
from collections import Counter
from pathlib import Path


class ArtifactError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ArtifactError(message)


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def integer(value, minimum=0):
    return type(value) is int and value >= minimum


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ArtifactError(f"Cannot read JSON at {path}: {exc}") from exc


def rows(path, required=False):
    if not path.exists():
        require(not required, f"Missing {path.name}")
        return []
    records = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except ValueError as exc:
            raise ArtifactError(f"{path.name}:{n}: invalid JSON") from exc
        require(isinstance(record, dict), f"{path.name}:{n}: expected an object")
        records.append(record)
    return records


def local_reference(root, value):
    require(nonempty(value), "trace_ref must be a nonempty relative path")
    relative = Path(value)
    require(not relative.is_absolute() and '..' not in relative.parts,
            f"Unsafe reference: {value}")
    target = (root / relative).resolve()
    require(target.is_relative_to(root.resolve()), f"Reference escapes bundle: {value}")
    require(target.is_file(), f"Missing referenced file: {value}")


def accounting(row):
    for key in ('usage', 'judge_usage'):
        usage = row.get(key)
        if usage is not None:
            require(isinstance(usage, dict), f"{key} must be an object or null")
            for field, value in usage.items():
                require(value is None or integer(value), f"Invalid measured {key}.{field}")
    for key in ('cost_usd', 'latency_s'):
        value = row.get(key)
        require(value is None or (number(value) and value >= 0), f"Invalid {key}")


def validate_splits(cases, splits):
    require(isinstance(splits, dict) and splits, 'splits must be a nonempty object')
    require(set(splits) <= {'development', 'validation', 'test'}, 'Unknown split name')
    lookup = {c['id']: c for c in cases}
    seen, groups = set(), {}
    for name, ids in splits.items():
        require(isinstance(ids, list), f'{name} IDs must be an array')
        for cid in ids:
            require(nonempty(cid) and cid in lookup, f'Unknown split case: {cid}')
            require(cid not in seen, f'Duplicate split case: {cid}')
            seen.add(cid)
            group = lookup[cid]['group_id']
            require(groups.get(group, name) == name, f'Group crosses splits: {group}')
            groups[group] = name
    require(seen == set(lookup), 'Splits must cover all cases exactly once')


def validate(root):
    root = Path(root)
    manifest = read_json(root / 'manifest.json')
    require(isinstance(manifest, dict), 'Manifest must be an object')
    require(type(manifest.get('schema_version')) is int and manifest['schema_version'] == 1,
            'Unsupported schema_version')
    for key in ('flow', 'dataset_version'):
        require(nonempty(manifest.get(key)), f'Missing manifest {key}')
    cases = rows(root / 'cases.jsonl', required=True)
    require(cases, 'Dataset is empty')
    ids = set()
    for case in cases:
        for key in ('id', 'group_id'):
            require(nonempty(case.get(key)), f'Invalid case {key}')
        require(case['id'] not in ids, f"Duplicate case: {case['id']}")
        ids.add(case['id'])
        require(isinstance(case.get('input'), (str, dict)), 'Case input must be text or object')
        require(isinstance(case.get('source'), dict) and nonempty(case['source'].get('kind')),
                'Case source.kind is required')
    if 'splits' in manifest:
        validate_splits(cases, manifest['splits'])

    annotations = rows(root / 'annotations.jsonl')
    annotation_ids = set()
    for row in annotations:
        for key in ('id', 'criterion_id'):
            require(nonempty(row.get(key)), f'Invalid annotation {key}')
        require(row['id'] not in annotation_ids, 'Duplicate annotation ID')
        annotation_ids.add(row['id'])
        require(nonempty(row.get('case_id')) and row['case_id'] in ids, 'Unknown annotation case')
        require(row.get('origin') in ('human', 'agent'), 'Invalid annotation origin')
        require(row.get('status') in ('suggested', 'confirmed', 'dismissed', 'uncertain'),
                'Invalid annotation status')
        require(isinstance(row.get('note'), str), 'Annotation note is required')
        if 'label' in row:
            require(row['label'] in ('pass', 'fail'), 'Invalid annotation label')
        if row['status'] == 'confirmed':
            require(nonempty(row.get('reviewed_by')), 'Confirmed annotation needs reviewed_by')

    results = rows(root / 'results.jsonl')
    seen = set()
    if results:
        for key in ('run_id', 'run_fingerprint'):
            require(nonempty(manifest.get(key)), f'Missing manifest {key}')
    for row in results:
        require(nonempty(row.get('case_id')) and row['case_id'] in ids, 'Unknown result case')
        require(integer(row.get('rep')), 'Invalid repetition')
        key = (row['case_id'], row['rep'])
        require(key not in seen, f'Duplicate terminal result: {key}')
        seen.add(key)
        require(row.get('status') in ('ok', 'app_error', 'grader_error', 'timeout', 'truncated'),
                'Invalid result status')
        require('output' in row, 'Result output field is required')
        local_reference(root, row.get('trace_ref'))
        grades = row.get('grades')
        require(isinstance(grades, dict), 'grades must be an object')
        if row['status'] == 'ok':
            require(row['output'] is not None and grades, 'Successful result needs output and grades')
        else:
            require(not grades, 'Non-ok result cannot carry quality grades')
        for metric, grade in grades.items():
            require(nonempty(metric) and isinstance(grade, dict), 'Invalid grade')
            require(number(grade.get('score')), 'Grade score must be finite numeric')
            require(isinstance(grade.get('reason'), str), 'Grade reason is required')
            require(nonempty(grade.get('grader_version')), 'Missing grader_version')
        accounting(row)
    expected = manifest.get('expected_results')
    if expected is not None:
        require(integer(expected), 'Invalid expected_results')
        require(len(results) <= expected, 'More results than expected')

    attempts = rows(root / 'attempts.jsonl')
    attempt_keys = set()
    for row in attempts:
        require(nonempty(row.get('case_id')) and row['case_id'] in ids, 'Unknown attempt case')
        require(integer(row.get('rep')) and integer(row.get('attempt'), 1), 'Invalid attempt identity')
        key = (row['case_id'], row['rep'], row['attempt'])
        require(key not in attempt_keys, 'Duplicate attempt')
        attempt_keys.add(key)
        require(nonempty(row.get('status')), 'Attempt status required')
        accounting(row)
    return {'cases': len(cases), 'annotations': len(annotations), 'results': len(results),
            'attempts': len(attempts), 'statuses': dict(Counter(r['status'] for r in results)),
            'complete': None if expected is None else len(results) == expected}


def make_splits(cases, seed):
    grouped = {}
    for case in cases:
        grouped.setdefault(case['group_id'], []).append(case['id'])
    groups = sorted(grouped)
    require(len(groups) >= 3, 'Need at least three independent groups; do not fake a holdout')
    random.Random(seed).shuffle(groups)
    dev_count = min(len(groups) - 2, max(1, int(len(groups) * .6)))
    val_count = min(len(groups) - dev_count - 1, max(1, int(len(groups) * .2)))
    slices = [groups[:dev_count], groups[dev_count:dev_count + val_count],
              groups[dev_count + val_count:]]
    return {name: [cid for g in part for cid in sorted(grouped[g])]
            for name, part in zip(('development', 'validation', 'test'), slices)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('validate', 'inspect', 'split'))
    parser.add_argument('bundle', type=Path)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        summary = validate(args.bundle)
        if args.command == 'split':
            require(args.output is not None, 'split requires --output')
            split = make_splits(rows(args.bundle / 'cases.jsonl', True), args.seed)
            with args.output.open('x', encoding='utf-8') as stream:
                json.dump({'seed': args.seed, 'splits': split}, stream, indent=2)
                stream.write('\n')
            print(f'Wrote {args.output}; review coverage before freezing')
        else:
            print(json.dumps(summary, indent=2))
    except (ArtifactError, OSError) as exc:
        parser.exit(1, f'Error: {exc}\n')


if __name__ == '__main__':
    main()
