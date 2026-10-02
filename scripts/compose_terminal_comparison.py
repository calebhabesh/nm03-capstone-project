#!/usr/bin/env python3
"""Place complete terminal screen recordings side by side, without retiming.

Requires ffmpeg/ffprobe and DejaVu Sans. The shorter recording holds its final
frame. Static labels are the only generated visual content.
"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='Destination MP4')
    args = parser.parse_args()
    root, assets = args.capture.resolve(), args.output.resolve().parent
    assets.mkdir(parents=True, exist_ok=True)
    evidence = json.loads((root / 'terminal-comparison.json').read_text())
    assert evidence['outputs_byte_identical'] and evidence['warmups_per_configuration'] == 1
    captures = {r['threads']: r for r in json.loads((root / 'screen-capture.json').read_text())}
    durations = []
    for n in (1, 8):
        video = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries',
                         'stream=width,height', '-show_entries', 'format=duration', '-of', 'json',
                         str(root / f'terminal-{n}.mp4')], text=True))
        assert video['streams'][0]['width'] == video['streams'][0]['height'] == 1000
        durations.append(float(video['format']['duration']))
    assert durations[0] >= durations[1]
    font = next(p for p in (Path('/usr/share/fonts/TTF/DejaVuSans.ttf'),
                            Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')) if p.is_file())
    wall = [r['wall_seconds'] for r in evidence['runs']]
    with tempfile.TemporaryDirectory(prefix='capstone-video-') as temporary:
        directory = Path(temporary)
        labels = [
            ('one', 'One thread · sequential workflow', 18, 18, 26),
            ('eight', 'Eight threads · OpenMP export', 1022, 18, 26),
            ('capture', 'Actual terminal screen recordings · separate laptop runs · 1x playback · finished pane held', 18, 1070, 24),
            ('benchmark', f'Repeated benchmark: 28.92 → 9.18 s (3.15x) | Capture /usr/bin/time: {wall[0]:.2f} s / {wall[1]:.2f} s', 18, 1104, 22)]
        filters = (f'[0:v]pad=1004:1000:0:0:color=0x111820[left];'
                   f'[1:v]tpad=stop_mode=clone:stop_duration={durations[0]-durations[1]+1:.2f}[right];'
                   '[left][right]hstack=inputs=2:shortest=1,pad=2004:1136:0:60:color=0x111820')
        for name, text, x, y, size in labels:
            path = directory / f'{name}.txt'
            path.write_text(text)
            filters += f',drawtext=fontfile={font}:textfile={path}:x={x}:y={y}:fontsize={size}:fontcolor=0xeef2f6'
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(root / 'terminal-1.mp4'),
                        '-i', str(root / 'terminal-8.mp4'), '-filter_complex', filters, '-an',
                        '-c:v', 'libx264', '-crf', '19', '-preset', 'fast', '-pix_fmt', 'yuv420p',
                        '-movflags', '+faststart', str(args.output)], check=True)
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-ss', str(durations[0] - 2),
                    '-i', str(args.output), '-frames:v', '1', str(args.output.with_suffix('.png'))], check=True)
    for n in (1, 8):
        for suffix in ('mp4', 'log', 'timing'):
            shutil.copy2(root / f'terminal-{n}.{suffix}', assets / f'terminal-{n}.{suffix}')
        raw = (root / f'terminal-{n}.log').read_text(errors='replace')
        plain = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', raw).replace('\r', '')
        (assets / f'terminal-{n}.txt').write_text('\n'.join(line.rstrip() for line in plain.splitlines()) + '\n')
        evidence['runs'][0 if n == 1 else 1]['raw_video_sha256'] = hashlib.sha256(
            (assets / f'terminal-{n}.mp4').read_bytes()).hexdigest()
    evidence['composition'] = {'playback_speed': 1, 'raw_videos_cut_or_retimed': False,
        'shorter_pane': 'Final recorded frame held until the longer session ends',
        'duration_seconds': durations[0], 'width': 2004, 'height': 1136,
        'comparison_video_sha256': hashlib.sha256(args.output.read_bytes()).hexdigest()}
    (assets / 'terminal-comparison.json').write_text(json.dumps(evidence, indent=2) + '\n')
    def stamp(t):
        milliseconds = round(t * 1000)
        return f'00:{milliseconds // 60000:02d}:{milliseconds // 1000 % 60:02d}.{milliseconds % 1000:03d}'
    start = round(captures[1]['command_submitted_seconds'])
    parallel_done = round(captures[8]['command_submitted_seconds'] + wall[1] + 2)
    serial_done = round(captures[1]['command_submitted_seconds'] + wall[0] + 2)
    cues = [(0, start, 'Actual terminal screen recordings. Both sessions verify 460 input slices and type the native command.'),
            (start, parallel_done, 'The same processing and lossless-export command runs with one or eight threads. Sessions execute separately on the laptop.'),
            (parallel_done, serial_done, f'Eight threads finish in {wall[1]:.2f} seconds, with exit status zero and 1,380 files. Its final recorded frame holds while the one-thread run continues.'),
            (serial_done, durations[0], f'One thread finishes in {wall[0]:.2f} seconds. Both complete all 460 slices. These capture times are separate from the repeated benchmark’s 3.15-times throughput result.')]
    args.output.with_suffix('.vtt').write_text('WEBVTT\n\n' + '\n\n'.join(
        f'{stamp(a)} --> {stamp(b)}\n{text}' for a, b, text in cues if b > a) + '\n')
    print(f'Composed {durations[0]:.2f}s actual screen recording; capture times {wall[0]:.2f}s / {wall[1]:.2f}s')


if __name__ == '__main__':
    main()
