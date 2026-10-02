# October 2026 demo refresh

The original clinical data was not deleted. On the workstation it is at
`/home/ethioking/FAST/data/Brain-Tumor-Progression`; on the laptop it is at
`/home/caleb2002/FAST/data/Brain-Tumor-Progression`. The full workstation inventory
contains 9,258 DICOM files, including the curated 460-slice
`T1-Post-Combined-P001-P020` directory. A ZIP of that subset is also present on the
workstation. The laptop retains the complete benchmark archive at
`/home/caleb2002/capstone-refresh-20261002`. No dataset download is needed.

## Performance comparison

[Side-by-side screen recording](assets/throughput-comparison.mp4) · [Captions](assets/throughput-comparison.vtt)
· [Verification and hashes](assets/terminal-comparison.json)

The video shows the pixels of real xterm sessions connected over SSH to the
original Ryzen 7 5800U / MX450 laptop on AC power. Actual keyboard events type
commands into an interactive remote bash shell. The sessions verify the 460
inputs, invoke the unchanged native executable with one or eight threads,
display native FAST startup and completion messages, and show GNU time, exit
status, and the actual exported-file count. The terminal's tmux status bar shows
its real UTC clock. Terminal text is not reconstructed or animated.

Each configuration receives one full warmup with the same environment, including
`TZ=UTC`, before recording. The retained captures contain no kernel-cache rebuild
messages. The commands run separately, avoiding GPU contention, and the recordings play
at normal speed. The side-by-side composition preserves both complete raw
recordings without cuts or speed changes. Only the shorter session's final
recorded frame is held until the longer session ends. Static labels identify
the configurations and distinguish capture times from benchmark medians.

[Complete one-thread session](assets/terminal-1.mp4) · [Complete eight-thread session](assets/terminal-8.mp4)
· [One-thread transcript](assets/terminal-1.txt) · [Eight-thread transcript](assets/terminal-8.txt)

Raw `script` output and timing logs are also retained as `terminal-1.log`,
`terminal-8.log`, `terminal-1.timing`, and `terminal-8.timing`. Text transcripts
strip terminal escape sequences for readability. The raw screen recordings
are 1000 × 1000 H.264 MP4s at 20 fps; the composed video is 2004 × 1136 and
40.1 seconds long. Each individual recording includes command entry, execution,
completion, exit status, exported-file count, and a short final hold.

The visible GNU time results are **29.32 and 9.61 seconds**. C++'s internal
processing timer is also visible and measures a narrower scope. These are
single illustrative capture runs, with normal startup and terminal-recording
conditions; **28.92 and 9.18 seconds remain the five-repetition benchmark
medians**. No new benchmark speedup is inferred from the recording.

`scripts/verify_terminal_comparison.py` checks the original input-manifest and
benchmark binary hashes, AC power, 460 successful slices, correct thread counts,
shared/staged scheduling, batches of 64, the exact 1,380-file inventory, and
SHA-256 equality of every mask and PNG. Capture reports and raw terminal/video
hashes are retained in `terminal-comparison.json`. Full reports and exported
images stay in the laptop archive's `terminal-demo-20261002-final` directory.

`scripts/record_terminal_comparison.py` requires Xvfb, xterm, xdotool and ffmpeg
locally; SSH access, tmux, script, bash and GNU time on the laptop. It creates
an isolated X display and a dedicated tmux server, leaving existing sessions
alone. `scripts/compose_terminal_comparison.py` creates the side-by-side video,
poster, captions, readable transcripts, and hash manifest from these recordings.
No manual terminal recording is required.

## Real-scan stage walkthrough

[Video](assets/stage-walkthrough.mp4) · [Captions](assets/stage-walkthrough.vtt)
· [Input and source provenance](assets/stage-provenance.json)

The input is the exact original slice selected in the 2025 `test_pipeline.cpp`,
and its SHA-256 also matches a file in the complete benchmark subset. It is a
real 512 × 512 T1 post-contrast MRI from TCIA Brain-Tumor-Progression. It replaces the synthetic phantom in the
portfolio demonstration. The full dataset and DICOM metadata are not copied
into the portfolio.

The actual native Qt viewer keeps the original visible beside the current FAST
output. Eight four-second steps show import, normalization, intensity clipping,
vector median filtering, sharpening, seeded region growing, erosion, and
dilation. The viewer exports each actual intermediate image, then captures its
own widget at 10 fps; ffmpeg encodes the 32-second H.264 video. Stage images are
computed before presentation. The capture clock does not measure processing
time. The original and each intensity-stage preview use independent display
ranges, so displayed brightness is not an absolute intensity measurement.

Erosion and dilation branch independently from the region-growing mask.
The final batch output is dilation of the un-eroded mask. Fixed intensity
thresholds and dimension-based seeds remain unchanged; this demonstration does
not establish tumor accuracy or disease progression.

Source: Schmainda, K. M., & Prah, M. (2018), *Data from Brain-Tumor-Progression*,
TCIA, [doi:10.7937/K9/TCIA.2018.15quzvnb](https://doi.org/10.7937/K9/TCIA.2018.15quzvnb).
The [collection page](https://www.cancerimagingarchive.net/collection/brain-tumor-progression/)
lists controlled access. Only the selected-slice walkthrough and poster are
included publicly; the full corpus and its DICOM metadata remain local.

The synthetic generator remains a convenient fixture for integration checks.
Its image is no longer used as the portfolio demo.

## Recording recipes

`scripts/record_terminal_comparison.py` opens real SSH terminals on a private local X display, types commands with xdotool, and records their actual pixels with ffmpeg. The laptop's tmux clock keeps elapsed time visible during quiet processing; `script` retains terminal output and timing logs. It requires Xvfb, xterm, xdotool, and ffmpeg locally, and tmux, script, bash, and GNU time on the laptop. Upload `scripts/verify_terminal_comparison.py` to the archive's `source/scripts` directory first. Use fresh capture directories:

```sh
python3 scripts/record_terminal_comparison.py --host laptop \
  --remote-archive /home/caleb2002/capstone-refresh-20261002 \
  --remote-input /home/caleb2002/FAST/data/Brain-Tumor-Progression/T1-Post-Combined-P001-P020 \
  --remote-capture /home/caleb2002/capstone-refresh-20261002/terminal-demo-new \
  --output out-refresh/terminal-demo-new
python3 scripts/compose_terminal_comparison.py \
  --capture out-refresh/terminal-demo-new \
  --output docs/assets/throughput-comparison.mp4
```

The recording script verifies input and binary hashes before capture, then checks native reports and every exported file afterward. The composed video adds static pane labels and benchmark context; it does not generate terminal text. Individual recordings, raw terminal logs, timing logs, and hashes are retained for inspection.

The [32-second pipeline walkthrough](assets/stage-walkthrough.mp4) records the actual native C++/Qt viewer using the same real MRI slice as the 2025 demo. The original stays visible next to eight actual stage outputs: import, normalization, clipping, median filtering, sharpening, region growing, erosion, and dilation. Each intensity preview has its own display range. Erosion and dilation remain separate branches. [Input provenance](assets/stage-provenance.json) binds the clip to the original slice by SHA-256 without including DICOM metadata in the video.

```sh
DEMO_SLICE="$CAPSTONE_DATA/PGBM-017/16.000000-T1post-19554/1-14.dcm"
./build-refresh/test_pipeline --input "$DEMO_SLICE" --headless \
  --output out-refresh/real-stages --record-frames out-refresh/real-demo-frames \
  --timeout-ms 32000 \
  --input-label 'Original capstone scan · T1 post-contrast MRI · TCIA Brain-Tumor-Progression'
ffmpeg -framerate 10 -i out-refresh/real-demo-frames/frame-%05d.png \
  -c:v libx264 -crf 20 -pix_fmt yuv420p -movflags +faststart \
  docs/assets/stage-walkthrough.mp4
```

The stages finish before the walkthrough starts: four seconds per stage is presentation timing, not processing time. Both videos have [comparison captions](assets/throughput-comparison.vtt) / [pipeline captions](assets/stage-walkthrough.vtt) and transcripts on the portfolio page. No terminal recording needs to be arranged manually.
