# Medical Image Processing with FAST and OpenMP

A four-person academic C++ capstone exploring concurrency in a DICOM image-processing workflow. **FAST provides the image algorithms and GPU acceleration.** The application integrates those stages, schedules work with OpenMP, exports images, and verifies outputs.

The original project ran September 2024–May 2025. Caleb's October 2026 refresh adds a shared pipeline, a producer-and-worker scheduler, failure reporting, and retained benchmark evidence. New measurements belong to this refresh. The original submission remains at [`50d5666`](https://github.com/calebhabesh/NM03-Capstone-Project/tree/50d56665a56d8e9b8e775f8e08a8b7f0a5584506).

The refresh measured **3.15× throughput for processing and lossless export of 460 slices** with eight OpenMP threads: **28.92 → 9.18 seconds**, using five measured repetitions on a Ryzen 7 5800U / MX450 laptop. Processing without exports stayed around 8.6 seconds; the gain comes from concurrent host conversion and export overlapping GPU work.

[Watch the demos](#demo) · [Measured results](docs/benchmark-results.md) · [Audit and refresh notes](docs/2026-refresh.md)

## Demo

Two native recordings from the 2026 refresh. The comparison demonstrates execution time; the walkthrough shows the actual filters applied to the original capstone MRI.

### Performance comparison

https://github.com/user-attachments/assets/395b7057-5183-47fe-9871-762cc745681e

**40.1 seconds · actual terminal screen recordings.** Watch the complete one-thread and eight-thread commands process and export all 460 slices, from command entry to exit status zero and 1,380 files. Sessions ran separately on the original laptop, at normal speed with no execution cuts; the shorter pane holds its final recorded frame. All exported files match by SHA-256.

Visible single-run times are **29.32 and 9.61 seconds**. The repeated benchmark remains **28.92 → 9.18 seconds (3.15× throughput)** across five measured repetitions.

[MP4 source](docs/assets/throughput-comparison.mp4) · [Captions](docs/assets/throughput-comparison.vtt) · [One-thread transcript](docs/assets/terminal-1.txt) · [Eight-thread transcript](docs/assets/terminal-8.txt) · [Verification and hashes](docs/assets/terminal-comparison.json)

### MRI stage walkthrough

https://github.com/user-attachments/assets/78fcd69a-8ee5-4aea-88cd-732545ca662e

**32 seconds · real original capstone scan.** The native C++/Qt viewer keeps the original T1 post-contrast MRI visible beside import, normalization, clipping, median filtering, sharpening, region growing, erosion, and dilation. These are actual shared FAST pipeline outputs. Four seconds per stage is presentation timing; the stages finish before playback. Each intensity preview uses its own display range. Erosion and dilation branch independently from the region-growing mask.

[MP4 source](docs/assets/stage-walkthrough.mp4) · [Captions](docs/assets/stage-walkthrough.vtt) · [Transcript](docs/assets/stage-walkthrough.txt) · [Input provenance](docs/assets/stage-provenance.json) · [Capture instructions](docs/demo-production.md)

## Repository layout

| Path | Contents |
|---|---|
| `src/common/`, `src/include/` | Shared FAST pipeline, preview conversion, and CLI runner |
| `src/sequential/`, `src/parallel/` | Sequential and OpenMP entry points |
| `src/test/` | Native stage viewer and recording support |
| `scripts/` | Integration checks, benchmark harness, evidence publishing, and terminal capture tools |
| `benchmarks/2026-10-02/` | Published measurements, environment, and source hashes |
| `docs/` | Benchmark methodology, refresh audit, and demo production notes |
| `docs/assets/` | Videos, captions, transcripts, charts, and provenance manifests |

Builds, full DICOM inputs, per-slice reports, and batch exports stay outside Git. See [the script guide](scripts/README.md) and [media inventory](docs/assets/README.md).

## What runs

DICOM import → normalization → intensity clipping → vector median filtering → sharpening → seeded region growing → dilation → synchronized mask readback.

The fixed thresholds and dimension-based seeds illustrate image-processing operations. Tumor-segmentation accuracy has not been evaluated against annotated masks. The demo also shows erosion as a separate branch; erosion does not feed the final dilation.

In the default **staged** schedule, thread zero owns a reusable FAST GPU pipeline. OpenMP tasks convert completed host images and write lossless previews while the producer processes the next slice. A task wait at each batch boundary bounds retained images. With one worker, each slice finishes immediately, matching the sequential workflow.

The useful concurrency is in the complete processing-and-export workflow. Processing without previews is measured separately to show the limit imposed by the GPU pipeline.

## Build and try it

Requires C++17, CMake 3.16+, OpenMP, and **FAST 4.10.0** with DICOM support and an OpenCL device. The viewer uses FAST's bundled Qt 5. [FAST installation and source](https://github.com/smistad/FAST/tree/v4.10.0).

```sh
cmake -S . -B build-refresh -DFAST_DIR=/opt/fast/cmake -DCMAKE_BUILD_TYPE=Release
cmake --build build-refresh -j 4

# Generate eight analytic DICOM fixtures; no patient data or Python dependencies.
python3 scripts/generate_phantom.py
./build-refresh/test_pipeline --input out-refresh/phantom/synthetic-phantom-000.dcm --synthetic

# Run actual output-equivalence and failure checks.
OMP_WAIT_POLICY=PASSIVE python3 scripts/check_pipeline.py \
  --build build-refresh --input out-refresh/phantom

./build-refresh/img_processing_parallel --input out-refresh/phantom \
  --threads 4 --batch-size 64 --output out-refresh/exports \
  --export-previews --report out-refresh/parallel.json
```

The fixtures test import, processing, and export. They do not simulate MRI acquisition or tumor anatomy. The fixtures remain available for integration checks. The portfolio walkthrough uses the real T1 post-contrast MRI slice from the original 2025 demo, also present in the 460-slice benchmark subset; its walkthrough timing is independent of benchmark timing.

Without `--output`, both runners process every slice, synchronize GPU completion by reading the final mask on the host, and fingerprint it. `--output DIR` adds raw PGM masks; `--export-previews` adds 512-pixel grayscale original and mask PNGs. PGM masks retain raw 0/1 labels; PNG mask previews display them as black and white. Export work is included in timing when enabled. Existing output directories are never deleted, and files with matching names are overwritten. Failed slices or exports cause a nonzero exit status and appear in the JSON report.

`--limit N` selects the first N sorted slices. `--help` lists options. Diagnostic `--schedule slices` and `--device worker` modes retain the alternative whole-slice scheduling and isolated-context experiments; the validated staged/shared design is the default.

## Reproduce the benchmark

The original curated workload contains **460 T1 post-contrast slices from 20 patient directories**, arranged under `T1-Post-Combined-P001-P020` in [TCIA Brain-Tumor-Progression](https://www.cancerimagingarchive.net/collection/brain-tumor-progression/). The collection is subject to [controlled-access terms](https://www.cancerimagingarchive.net/nih-controlled-data-access-policy/). Obtain authorized access separately. The full dataset and batch exports are not included here; the stage walkthrough and poster show one original capstone slice and its processed outputs.

```sh
CAPSTONE_DATA="$HOME/FAST/data/Brain-Tumor-Progression/T1-Post-Combined-P001-P020"
OMP_WAIT_POLICY=PASSIVE python3 scripts/benchmark.py \
  --build build-refresh --input "$CAPSTONE_DATA" \
  --results benchmarks/local/export-run --threads 1 2 4 8 --batch-size 64 \
  --export-previews --repetitions 5 --warmups 1

# Control: same input and stages, without file exports.
OMP_WAIT_POLICY=PASSIVE python3 scripts/benchmark.py \
  --build build-refresh --input "$CAPSTONE_DATA" \
  --results benchmarks/local/processing-run --threads 1 2 4 8 --batch-size 64 \
  --repetitions 5 --warmups 1
```

The standard-library harness retains every command, log, source/binary hash, input manifest, and run report. It shuffles configurations within each measurement round, excludes recorded warmups from medians, and measures whole-program elapsed time. Every run must finish every slice and match the sequential masks. Export benchmarks additionally require SHA-256 equality of every PGM and PNG. The results directory must be empty. The one-worker OpenMP configuration is the speedup baseline, with the separate sequential executable reported alongside it.

To publish aggregate evidence without input identifiers or image files:

```sh
python3 scripts/publish_benchmark.py --results benchmarks/local/export-run \
  --output benchmarks/public/export-run
# Optional plotting dependency: matplotlib.
python3 scripts/plot_benchmark.py --results benchmarks/public/export-run \
  --output docs/assets/export-benchmark
```

## Team and credits

Report authors: **Caleb Habesh, Rayyan Bilal, Brandon Wong, and Taranvir Khakh**. Git history records integration, scheduling, dataset, and filtering work; commit counts do not establish individual responsibilities or leadership. Caleb's 2026 refresh is separate from the original team submission.

FAST is developed by Erik Smistad and contributors under [BSD-2-Clause](https://github.com/smistad/FAST/blob/v4.10.0/LICENSE); bundled third-party components have their own licenses. This application contains no custom GPU image-processing kernels. OpenMP supplies CPU work scheduling.

Dataset citation: Schmainda, K. M., & Prah, M. (2018). *Data from Brain-Tumor-Progression*. The Cancer Imaging Archive. [doi:10.7937/K9/TCIA.2018.15quzvnb](https://doi.org/10.7937/K9/TCIA.2018.15quzvnb).
