#!/usr/bin/env python3
"""Compare identical FAST pipelines; retain every run and reject failed/different outputs."""
import argparse
import hashlib
import json
import os
import platform
import random
import statistics
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def checked_output(command):
    try:
        return subprocess.check_output(command, text=True, stderr=subprocess.STDOUT).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def power_state():
    """Record existing policy; never change system power settings."""
    root = Path('/sys/class/power_supply')
    return {str(p.relative_to(root)): p.read_text().strip()
            for supply in root.glob('*')
            for name in ('online', 'status', 'capacity')
            if (p := supply / name).is_file()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, default=Path('build-refresh'))
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--results', type=Path, required=True)
    parser.add_argument('--threads', type=int, nargs='+', default=[1, 2, 4, 8])
    parser.add_argument('--batch-size', type=int, default=64)
    parser.add_argument('--device', choices=['worker', 'shared'], default='shared')
    parser.add_argument('--schedule', choices=['staged', 'slices'], default='staged')
    parser.add_argument('--baseline', choices=['sequential', 'omp-1'], default='omp-1')
    parser.add_argument('--repetitions', type=int, default=5)
    parser.add_argument('--warmups', type=int, default=1)
    parser.add_argument('--limit', type=int)
    parser.add_argument('--export-masks', action='store_true')
    parser.add_argument('--export-previews', action='store_true')
    args = parser.parse_args()
    if args.export_previews:
        args.export_masks = True
    if args.repetitions < 3 or args.warmups < 1 or args.batch_size < 1:
        parser.error('Use at least three measurements, one warmup and a positive batch size')
    if any(n < 1 or n > 256 for n in args.threads):
        parser.error('Thread counts must be between 1 and 256')
    if args.baseline == 'omp-1' and 1 not in args.threads:
        parser.error('Include --threads 1 when using the omp-1 baseline')
    if args.results.exists() and any(args.results.iterdir()):
        parser.error('Results directory must be empty; previous evidence is never overwritten')
    args.results.mkdir(parents=True, exist_ok=True)
    args.build = args.build.resolve()
    args.input = args.input.resolve()
    paths = sorted(args.input.rglob('*.dcm')) if args.input.is_dir() else [args.input]
    if args.limit:
        paths = paths[:args.limit]
    if not paths:
        parser.error('No input slices')
    input_manifest = [
        {'file': str(p.relative_to(args.input)) if args.input.is_dir() else p.name,
         'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'bytes': p.stat().st_size}
        for p in paths
    ]
    write_json(args.results / 'input-manifest.json', input_manifest)
    source_root = Path(__file__).resolve().parent.parent
    source_paths = sorted((source_root / 'src').rglob('*'))
    source_paths += [source_root / 'CMakeLists.txt', Path(__file__).resolve()]
    write_json(args.results / 'source-manifest.json', {
        str(p.relative_to(source_root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in source_paths if p.is_file()
    })
    configs = [('sequential', 'img_processing_sequential', 1)]
    configs += [('omp-' + str(n), 'img_processing_parallel', n) for n in dict.fromkeys(args.threads)]
    metadata = {
        'started_utc': datetime.now(timezone.utc).isoformat(),
        'platform': platform.platform(), 'cpu': checked_output(['lscpu']),
        'gpu': checked_output(['nvidia-smi', '--query-gpu=name,driver_version', '--format=csv,noheader']),
        'compiler': checked_output(['g++', '--version']),
        'git_commit': checked_output(['git', 'rev-parse', 'HEAD']),
        'batch_size': args.batch_size, 'device_mode': args.device,
        'scheduling': args.schedule, 'slice_count': len(paths),
        'export_masks': args.export_masks, 'export_previews': args.export_previews,
        'warmups_per_configuration': args.warmups,
        'repetitions': args.repetitions, 'order_seed': 20261002,
        'binaries': {name: hashlib.sha256((args.build / name).read_bytes()).hexdigest()
                     for _, name, _ in configs},
        'timing': 'External perf_counter around subprocess.run, including startup and report writing',
        'speedup_baseline': args.baseline,
        'power_state': power_state(),
        'environment': {key: os.environ.get(key) for key in
                        ('OMP_WAIT_POLICY', 'OMP_PROC_BIND', 'OMP_PLACES', 'OMP_NUM_THREADS')},
        'validation': 'Every run must finish every slice and match the sequential raw-mask fingerprints',
    }
    write_json(args.results / 'metadata.json', metadata)
    reference = None
    export_reference = None
    measurements = []

    def run(config, role, index):
        nonlocal reference, export_reference
        label, binary, threads = config
        prefix = f'{label}-{role}-{index:02d}'
        report = args.results / (prefix + '.json')
        command = [str(args.build / binary), '--input', str(args.input),
                   '--threads', str(threads), '--batch-size', str(args.batch_size),
                   '--device', args.device,
                   '--schedule', args.schedule,
                   '--report', str(report.resolve())]
        if args.limit:
            command += ['--limit', str(args.limit)]
        if args.export_masks:
            command += ['--output', str((args.results / (prefix + '-masks')).resolve())]
        if args.export_previews:
            command += ['--export-previews']
        measurement_device_state = checked_output(['nvidia-smi', '--query-gpu=pstate,temperature.gpu,clocks.current.sm,clocks.current.memory,utilization.gpu', '--format=csv,noheader'])
        measurement_power_state = power_state()
        started = time.perf_counter()
        with (args.results / (prefix + '.log')).open('w') as log:
            process = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=300)
        elapsed = time.perf_counter() - started
        measurement = {'configuration': label, 'role': role, 'round': index,
                       'wall_seconds': elapsed, 'exit_code': process.returncode,
                       'gpu_state_before': measurement_device_state,
                       'power_state_before': measurement_power_state,
                       'command': command, 'report': report.name}
        measurements.append(measurement)
        write_json(args.results / 'runs.json', measurements)
        if process.returncode != 0 or not report.exists():
            raise RuntimeError(f'{prefix} failed; see retained log')
        data = json.loads(report.read_text())
        if data['completed_slices'] != len(paths) or data['failed_slices'] != 0:
            raise RuntimeError(f'{prefix} has incomplete outputs')
        if data['actual_threads'] != threads:
            raise RuntimeError(f'{prefix} used an unexpected thread count')
        outputs = {s['file']: s['fingerprint'] for s in data['slices'] if s['success']}
        if len(outputs) != len(paths) or set(outputs) != {s['file'] for s in input_manifest}:
            raise RuntimeError(f'{prefix} output inventory differs from input manifest')
        if reference is None:
            if label != 'sequential':
                raise RuntimeError('First run must establish the sequential reference')
            reference = outputs
        elif outputs != reference:
            differences = [name for name in reference if outputs.get(name) != reference[name]]
            raise RuntimeError(f'{prefix} masks differ from sequential: {differences[:5]}')
        if args.export_masks:
            export_root = args.results / (prefix + '-masks')
            exported = {str(p.relative_to(export_root)): hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in export_root.rglob('*') if p.is_file()}
            expected = len(paths) * (3 if args.export_previews else 1)
            if len(exported) != expected:
                raise RuntimeError(f'{prefix} has {len(exported)} exported files, expected {expected}')
            if export_reference is None:
                export_reference = exported
            elif exported != export_reference:
                raise RuntimeError(f'{prefix} exported files differ byte-for-byte from sequential')
            write_json(args.results / (prefix + '-exports.json'), exported)
        print(f'{prefix}: {elapsed:.3f}s; {len(outputs)} matching masks', flush=True)

    for config in configs:
        for index in range(args.warmups):
            run(config, 'warmup', index)
    rng = random.Random(20261002)
    for index in range(args.repetitions):
        order = configs.copy()
        rng.shuffle(order)
        for config in order:
            run(config, 'measurement', index)
    baseline = statistics.median([r['wall_seconds'] for r in measurements
                                  if r['configuration'] == args.baseline and r['role'] == 'measurement'])
    summary = []
    for label, _, threads in configs:
        values = [r['wall_seconds'] for r in measurements
                  if r['configuration'] == label and r['role'] == 'measurement']
        median = statistics.median(values)
        summary.append({'configuration': label, 'threads': threads, 'runs': len(values),
                        'baseline': args.baseline,
                        'median_seconds': median, 'min_seconds': min(values),
                        'max_seconds': max(values), 'speedup': baseline / median,
                        'elapsed_reduction_percent': 100 * (1 - median / baseline)})
    write_json(args.results / 'summary.json', summary)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == '__main__':
    main()
