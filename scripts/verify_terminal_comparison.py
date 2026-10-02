#!/usr/bin/env python3
"""Check terminal-demo inputs against the benchmark, then verify actual exports."""
import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--metadata', type=Path, required=True)
    parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--preflight', action='store_true')
    args = parser.parse_args()
    metadata = json.loads(args.metadata.read_text())
    paths = sorted(args.input.rglob('*.dcm'))
    assert len(paths) == metadata['slice_count'] == 460, 'Wrong workload'
    manifest = [{'file': str(p.relative_to(args.input)), 'sha256': sha(p), 'bytes': p.stat().st_size}
                for p in paths]
    input_hash = hashlib.sha256((json.dumps(manifest, indent=2) + '\n').encode()).hexdigest()
    binary_hash = sha(args.build / 'img_processing_parallel')
    assert input_hash == metadata['input_manifest_sha256'], 'Input differs from benchmark'
    assert binary_hash == metadata['binaries']['img_processing_parallel'], 'Binary differs from benchmark'
    power = {str(p.relative_to('/sys/class/power_supply')): p.read_text().strip()
             for p in Path('/sys/class/power_supply').glob('*/online')}
    assert any(k.startswith('AC') and v == '1' for k, v in power.items()), 'AC power required'
    if args.preflight:
        print('PASS: original 460-slice inventory, unchanged benchmark binary, AC power')
        return
    inventories, runs = [], []
    expected = {str(p.relative_to(args.input)) + suffix for p in paths
                for suffix in ('.pgm', '.original.png', '.processed.png')}
    for threads in (1, 8):
        root = args.capture / f'omp-{threads}'
        report_path = root / f'run-{threads}.json'
        report = json.loads(report_path.read_text())
        assert report['completed_slices'] == 460 and not report['failed_slices']
        assert report['actual_threads'] == threads
        assert report['export_previews'] and report['export_masks']
        assert report['scheduling'] == 'staged' and report['device_mode'] == 'shared'
        assert report['batch_size'] == 64
        warmup = json.loads((root / 'warmup.json').read_text())
        assert warmup['completed_slices'] == 460 and not warmup['failed_slices']
        assert warmup['actual_threads'] == threads
        assert [(r['file'], r['fingerprint']) for r in report['slices']] == [
            (r['file'], r['fingerprint']) for r in warmup['slices']], 'Warmup masks differ'
        inventory = {str(p.relative_to(root / 'exports')): sha(p)
                     for p in (root / 'exports').rglob('*') if p.is_file()}
        assert set(inventory) == expected, 'Wrong export inventory'
        inventory_path = root / 'export-manifest.json'
        inventory_path.write_text(json.dumps(inventory, indent=2) + '\n')
        inventories.append(inventory)
        # GNU time's output comes from the live terminal, not the C++ timer.
        lines = (root / 'terminal.log').read_text(errors='replace').replace('\r', '').splitlines()
        assert not any('Kernel binary' in line and 'Compiling' in line for line in lines), \
            'Kernel cache rebuilt during capture; warm up with the same environment first'
        wall = [float(line[5:]) for line in lines if line.startswith('real ')]
        assert len(wall) == 1, 'Missing external time output'
        assert any('Exit status: 0' == line for line in lines), 'Native command did not exit successfully'
        runs.append({'threads': threads, 'wall_seconds': wall[0],
                     'internal_elapsed_seconds': report['elapsed_seconds'],
                     'completed_slices': 460, 'exported_files': len(inventory),
                     'report_sha256': sha(report_path), 'transcript_sha256': sha(root / 'terminal.log'),
                     'terminal_timing_sha256': sha(root / 'terminal.timing'),
                     'warmup_report_sha256': sha(root / 'warmup.json'),
                     'export_manifest_sha256': sha(inventory_path)})
    assert inventories[0] == inventories[1], 'Export bytes differ'
    evidence = {'schema': 1, 'capture': 'Actual X11 terminal screen recordings of separately executed laptop sessions',
                'scope': 'Processing and lossless PGM/PNG export, full native command through exit',
                'slice_count': 460, 'files_per_run': 1380, 'outputs_byte_identical': True,
                'warmups_per_configuration': 1,
                'binary_sha256': binary_hash, 'input_manifest_sha256': input_hash,
                'power_state': power, 'gpu': metadata['gpu'], 'runs': runs}
    (args.capture / 'terminal-comparison.json').write_text(json.dumps(evidence, indent=2) + '\n')
    print('PASS: every captured native run completed 460 slices; all 1,380 files match by SHA-256')


if __name__ == '__main__':
    main()
