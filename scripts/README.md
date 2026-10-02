# Script guide

Run these from the repository root. Python scripts use the standard library
unless a dependency is listed below.

| Script | Purpose | Additional requirements |
|---|---|---|
| `generate_phantom.py` | Generate analytic DICOM fixtures for integration checks | None |
| `check_pipeline.py` | Compare actual FAST masks/previews and verify failure handling | Native build, FAST/OpenCL |
| `benchmark.py` | Run randomized warmups/repetitions and verify every output | Native build, FAST/OpenCL |
| `publish_benchmark.py` | Publish aggregate evidence without input identifiers or pixels | Completed benchmark directory |
| `plot_benchmark.py` | Plot every measured run, median, and full range | matplotlib |
| `record_terminal_comparison.py` | Record complete native commands in actual SSH terminal windows | Local Xvfb, xterm, xdotool, ffmpeg; remote bash, tmux, script, GNU time |
| `verify_terminal_comparison.py` | Verify capture inputs, binaries, warmups, reports, and exported files | Run in the laptop capture archive |
| `compose_terminal_comparison.py` | Combine raw terminal videos without cuts or speed changes | ffmpeg, ffprobe, DejaVu Sans |

See [build and integration commands](../README.md#build-and-try-it),
[benchmark reproduction](../README.md#reproduce-the-benchmark), and
[recording recipes](../docs/demo-production.md#recording-recipes).

Raw patient inputs, complete benchmark logs, reports, and exports remain local.
The published evidence identifies the original measured source snapshot by
SHA-256. Later viewer changes retain more intermediate outputs for presentation;
they do not replace that measured snapshot or its recorded binary.
