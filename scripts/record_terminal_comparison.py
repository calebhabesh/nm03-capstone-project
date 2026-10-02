#!/usr/bin/env python3
"""Screen-record actual laptop shell sessions through SSH in a dedicated X display.

Uses Xvfb, xterm, xdotool and ffmpeg locally; tmux, script, bash, GNU time and
the unchanged benchmark build remotely. It types actual commands into a real
interactive terminal. No terminal output is reconstructed or animated.
"""
import argparse
import json
import os
import shlex
import subprocess
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='laptop')
    parser.add_argument('--remote-archive', required=True)
    parser.add_argument('--remote-input', required=True)
    parser.add_argument('--remote-capture', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    ssh = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8', args.host]
    quote = shlex.quote
    remote = args.remote_capture
    build = args.remote_archive + '/source/build'
    metadata = args.remote_archive + '/source/benchmarks/2026-10-02/export-pipeline/metadata.json'
    verifier = args.remote_archive + '/source/scripts/verify_terminal_comparison.py'
    verify_command = shlex.join(['python3', verifier, '--input', args.remote_input,
                                 '--build', build, '--metadata', metadata, '--capture', remote])
    setup = f'''mkdir {quote(remote)}
mkdir {quote(remote + '/omp-1')} {quote(remote + '/omp-8')}
ln -s {quote(build + '/img_processing_parallel')} {quote(remote + '/omp-1/img_processing_parallel')}
ln -s {quote(build + '/img_processing_parallel')} {quote(remote + '/omp-8/img_processing_parallel')}
'''
    subprocess.run(ssh + [setup], check=True)
    subprocess.run(ssh + [verify_command + ' --preflight'], check=True)
    # Match the benchmark's warmup policy. Retain the complete warmup logs and
    # reports; do not hide first-use kernel compilation in a timed comparison.
    for threads in (1, 8):
        directory = remote + f'/omp-{threads}'
        warmup = shlex.join(['env', 'TZ=UTC', 'OMP_WAIT_POLICY=PASSIVE', './img_processing_parallel',
                             '--input', args.remote_input, '--threads', str(threads),
                             '--batch-size', '64', '--output', directory + '/warmup-exports',
                             '--export-previews', '--report', directory + '/warmup.json'])
        subprocess.run(ssh + [f'cd {quote(directory)}\n' + warmup +
                             f' > {quote(directory + "/warmup.log")} 2>&1'], check=True)
        print(f'Completed full 460-slice warmup: {threads} thread(s)', flush=True)
    config = """set -g status-style 'bg=#243528,fg=#e2eee5'
set -g status-left '[#S] '
set -g status-left-length 28
set -g status-right '%H:%M:%S UTC'
set -g status-right-length 24
set -g status-interval 1
set -g default-terminal xterm-256color
"""
    subprocess.run(ssh + [f'cat > {quote(remote + "/tmux.conf")}'], input=config, text=True, check=True)
    display = next(f':{n}' for n in range(110, 140) if not Path(f'/tmp/.X11-unix/X{n}').exists())
    env = {**os.environ, 'DISPLAY': display}
    xvfb = subprocess.Popen(['Xvfb', display, '-screen', '0', '1000x1000x24', '-nolisten', 'tcp'],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    terminal = encoder = None
    socket = 'capstone-video-' + str(os.getpid())
    captures = []
    try:
        for _ in range(50):
            if subprocess.run(['xdpyinfo'], env=env, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL).returncode == 0:
                break
            time.sleep(0.1)
        else:
            raise RuntimeError('Xvfb did not start')
        for threads in (1, 8):
            directory = remote + f'/omp-{threads}'
            shell = shlex.join(['script', '-q', '-f', '-e', '-O', directory + '/terminal.log',
                               '-T', directory + '/terminal.timing', '-c', '/bin/bash --noprofile --norc -i'])
            launch = f'''export CAPSTONE_DATA={quote(args.remote_input)}
export PS1='\\u@\\h:\\W\\$ '
export TZ=UTC
exec tmux -L {quote(socket)} -f {quote(remote + '/tmux.conf')} new-session -s omp-{threads} -c {quote(directory)} {quote(shell)}'''
            terminal = subprocess.Popen(['xterm', '-geometry', '88x41+0+0', '-fa', 'DejaVu Sans Mono',
                                         '-fs', '18', '-bg', '#111820', '-fg', '#eef2f6',
                                         '-xrm', 'XTerm.vt100.allowTitleOps:false', '+sb', '-e',
                                         *ssh[:-1], '-tt', args.host, launch], env=env)
            time.sleep(2)
            window = subprocess.check_output(['xdotool', 'search', '--class', 'XTerm'], env=env, text=True).splitlines()[-1]
            subprocess.run(['xdotool', 'windowsize', window, '1000', '1000'], env=env, check=True)
            subprocess.run(['xdotool', 'windowfocus', window], env=env, check=True)
            # Put the pointer outside the text region of the terminal.
            subprocess.run(['xdotool', 'mousemove', '999', '999'], env=env, check=True)
            video = args.output / f'terminal-{threads}.mp4'
            progress = args.output / f'ffmpeg-{threads}.progress'
            encoder_log = (args.output / f'ffmpeg-{threads}.log').open('wb')
            started = time.perf_counter()
            encoder = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'x11grab',
                                        '-framerate', '20', '-video_size', '1000x1000', '-i', display + '.0',
                                        '-an', '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '18',
                                        '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
                                        '-progress', str(progress), str(video)], stdin=subprocess.PIPE,
                                       stdout=encoder_log, stderr=encoder_log)
            for _ in range(100):
                if progress.exists() and 'frame=' in progress.read_text():
                    break
                if encoder.poll() is not None:
                    raise RuntimeError('Screen recording failed')
                time.sleep(0.05)
            else:
                raise RuntimeError('No captured frames')

            def enter(command, delay=8):
                subprocess.run(['xdotool', 'type', '--clearmodifiers', '--delay', str(delay), '--', command],
                               env=env, check=True)
                subprocess.run(['xdotool', 'key', 'Return'], env=env, check=True)

            enter('find "$CAPSTONE_DATA" -name "*.dcm" | wc -l')
            time.sleep(0.8)
            enter('date -u')
            time.sleep(0.8)
            command = f'''OMP_WAIT_POLICY=PASSIVE \\
  /usr/bin/time -p ./img_processing_parallel \\
  --input "$CAPSTONE_DATA" --threads {threads} \\
  --batch-size 64 --output exports \\
  --export-previews --report run-{threads}.json'''
            command_entered = time.perf_counter() - started
            enter(command)
            submitted = time.perf_counter() - started
            deadline = time.monotonic() + 180
            while subprocess.run(ssh + [f'test -f {quote(directory + f"/run-{threads}.json")}'],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode:
                if time.monotonic() > deadline:
                    raise RuntimeError('Native run timed out')
                time.sleep(0.5)
            time.sleep(1)
            enter('echo "Exit status: $?"')
            time.sleep(0.7)
            enter('find exports -type f | wc -l')
            time.sleep(4)
            finished = time.perf_counter() - started
            encoder.stdin.write(b'q\n')
            encoder.stdin.flush()
            encoder.wait(timeout=20)
            encoder_log.close()
            if encoder.returncode:
                raise RuntimeError('ffmpeg failed to finalize recording')
            encoder = None
            captures.append({'threads': threads, 'video': video.name,
                             'command_typing_seconds': command_entered,
                             'command_submitted_seconds': submitted, 'recorded_seconds': finished})
            subprocess.run(ssh + [f'tmux -L {quote(socket)} kill-server'], check=True)
            terminal.wait(timeout=10)
            terminal = None
            print(f'Recorded complete actual terminal session: {threads} thread(s)', flush=True)
        subprocess.run(ssh + [verify_command], check=True)
        subprocess.run(['scp', '-q', args.host + ':' + remote + '/terminal-comparison.json', str(args.output)], check=True)
        for threads in (1, 8):
            for suffix in ('log', 'timing'):
                subprocess.run(['scp', '-q', args.host + ':' + remote + f'/omp-{threads}/terminal.{suffix}',
                                str(args.output / f'terminal-{threads}.{suffix}')], check=True)
        (args.output / 'screen-capture.json').write_text(json.dumps(captures, indent=2) + '\n')
    finally:
        if encoder is not None and encoder.poll() is None:
            encoder.terminate()
            encoder.wait(timeout=20)
        if terminal is not None and terminal.poll() is None:
            terminal.terminate()
            terminal.wait(timeout=10)
        subprocess.run(ssh + [f'tmux -L {quote(socket)} kill-server'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        xvfb.terminate()
        xvfb.wait(timeout=10)


if __name__ == '__main__':
    main()
