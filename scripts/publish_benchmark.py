#!/usr/bin/env python3
"""Export aggregate benchmark evidence without patient pixels, identifiers or paths."""
import argparse
import hashlib
import json
from pathlib import Path


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = args.results
    metadata = read(root / 'metadata.json')
    summary = read(root / 'summary.json')  # Only completed experiments qualify.
    runs = read(root / 'runs.json')
    public_runs = []
    fingerprints = None
    exports = None
    expected_slices = metadata['slice_count']
    expected_exports = expected_slices * (3 if metadata['export_previews'] else 1)
    for run in runs:
        report_path = root / run['report']
        report = read(report_path)
        if (run['exit_code'] != 0 or report['failed_slices'] != 0 or
                report['completed_slices'] != expected_slices):
            raise RuntimeError('Cannot publish a failed or incomplete experiment')
        current = {s['file']: s['fingerprint'] for s in report['slices'] if s['success']}
        if fingerprints is None:
            fingerprints = current
        if len(current) != expected_slices or current != fingerprints:
            raise RuntimeError('Mask inventory or fingerprints differ')
        record = {key: value for key, value in run.items()
                  if key not in ('command', 'report')}
        record.update({
            'completed_slices': expected_slices,
            'failed_slices': 0,
            'actual_threads': report['actual_threads'],
            'fast_version': report['fast_version'],
            'internal_elapsed_seconds': report['elapsed_seconds'],
            'mask_fingerprints_match_sequential': True,
            'private_report_sha256': digest(report_path),
        })
        if metadata['export_masks']:
            export_path = root / (report_path.stem + '-exports.json')
            current_exports = read(export_path)
            if exports is None:
                exports = current_exports
            if len(current_exports) != expected_exports or current_exports != exports:
                raise RuntimeError('Export inventory or SHA-256 hashes differ')
            record.update({
                'exported_files': expected_exports,
                'export_sha256_match_sequential': True,
                'private_export_manifest_sha256': digest(export_path),
            })
        public_runs.append(record)
    args.output.mkdir(parents=True, exist_ok=True)
    if any(args.output.iterdir()):
        raise RuntimeError('Public evidence directory must be empty')
    metadata['input_manifest_sha256'] = digest(root / 'input-manifest.json')
    metadata['private_runs_sha256'] = digest(root / 'runs.json')
    metadata['public_evidence_scope'] = (
        'Aggregate timings, environment, counts and validation outcomes. '
        'Patient images, relative identifiers, per-slice fingerprints, export '
        'manifests and absolute command paths remain in the private local archive.'
    )
    write(args.output / 'metadata.json', metadata)
    write(args.output / 'runs.json', public_runs)
    write(args.output / 'summary.json', summary)
    write(args.output / 'source-manifest.json', read(root / 'source-manifest.json'))
    print(f'Published {len(public_runs)} validated run records to {args.output}')


if __name__ == '__main__':
    main()
