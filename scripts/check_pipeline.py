#!/usr/bin/env python3
"""Integration checks for actual FAST outputs, failures, and CLI validation."""
import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--build', type=Path, default=Path('build-refresh'))
parser.add_argument('--input', type=Path, required=True)
args = parser.parse_args()
build = args.build.resolve()
with tempfile.TemporaryDirectory(prefix='capstone-check-') as temporary:
    root = Path(temporary)
    inventories = []
    for mode, threads in [('sequential', 1), ('parallel', 1), ('parallel', 4)]:
        tag = f'{mode}-{threads}'
        report = root / (tag + '.json')
        output = root / tag
        subprocess.run([str(build / ('img_processing_' + mode)), '--input', str(args.input.resolve()),
                        '--threads', str(threads), '--limit', '8', '--batch-size', '3',
                        '--output', str(output), '--export-previews',
                        '--report', str(report)], check=True, timeout=90)
        data = json.loads(report.read_text())
        assert data['completed_slices'] == 8 and data['failed_slices'] == 0, data
        assert data['actual_threads'] == threads, data
        masks = {str(p.relative_to(output)): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in output.rglob('*') if p.is_file()}
        assert len(masks) == 24, masks
        inventories.append(masks)
    assert inventories[0] == inventories[1] == inventories[2], 'Raw exported masks differ'
    bad_input = root / 'broken.dcm'
    bad_input.write_bytes(b'This is not a DICOM image')
    for mode in ('sequential', 'parallel'):
        report = root / (mode + '-failure.json')
        process = subprocess.run([str(build / ('img_processing_' + mode)), '--input', str(bad_input),
                                  '--threads', '1' if mode == 'sequential' else '4',
                                  '--report', str(report)], timeout=30)
        assert process.returncode == 1, 'Invalid DICOM was reported as a successful run'
        data = json.loads(report.read_text())
        assert data['completed_slices'] == 0 and data['failed_slices'] == 1, data
    for mode in ('sequential', 'parallel'):
        for options in ([], ['--input', '/does/not/exist'], ['--input', str(args.input), '--batch-size', '0']):
            process = subprocess.run([str(build / ('img_processing_' + mode)), *options], timeout=30)
            assert process.returncode == 1, (mode, options, process.returncode)
print('PASS: 8 masks and 16 previews are byte-identical across serial/1-worker/4-worker modes; corrupt input and invalid CLI fail correctly')
