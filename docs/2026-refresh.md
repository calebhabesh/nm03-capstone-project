# October 2026 preservation and verification pass

The September 2024–May 2025 capstone explored batch concurrency around FAST's GPU-accelerated image-processing operations. The 2026 refresh makes the implementation and evaluation inspectable; new measurements belong to this refresh, not the original academic submission.

The original implementation remains available at commit `50d56665a56d8e9b8e775f8e08a8b7f0a5584506`. The laptop also had an uncommitted change from 64 to eight OpenMP workers. Its checkout and original outputs were preserved; refresh builds and runs use a separate directory.

## What the audit established

- FAST implements normalization, clipping, median filtering, sharpening, region growing and morphology. Student code integrated the pipeline, found and sorted inputs, scheduled batches, rendered outputs and configured experiments.
- Both execution paths used the same stage parameters, but sequential processing constructed a renderer per slice while parallel processing reused one. Their end-to-end difference did not isolate scheduling.
- Historical code at `77ad8e5` summed overlapping worker durations into “Total Time.” That is accumulated task time, not program elapsed time. Whether report figures came from this metric or an external timing tool could not be established.
- Neither final report substantiates the résumé's 1.25× figure. Reported batch-25 runtimes imply roughly 1.045×; batch-50 text and chart disagree (28.482 versus 28.842 seconds). These are historical, unverified claims, not accepted benchmark results.
- Failure handling sometimes counted unsuccessful work as successful. The checked-in project contained no complete benchmark evidence or output-equivalence check.
- Seeds are chosen from image dimensions and fixed intensity ranges. The visual result includes outer head contours; no ground-truth tumor accuracy evaluation exists.
- Erosion and dilation in the prototype were independent branches, rather than erosion followed by dilation.

The four report authors are Caleb Habesh, Rayyan Bilal, Brandon Wong and Taranvir Khakh. Git history records contributions from Caleb, Rayyan and Brandon. It does not describe every member's work or establish a leadership role.

## Refresh implementation

One shared C++ pipeline backs the sequential runner, OpenMP runner, and stage demo. FAST process objects and compiled kernels persist between slices; graphs are retained by image dimensions because region-growing seeds depend on those dimensions. Fixed pipeline parameters match the original batch code.

The default staged/shared design has one producer, pinned to OpenMP thread zero, performing DICOM import, GPU processing, and synchronized readback. Export tasks operate on finished host images while the producer advances. Tasks retain only the original and final mask, and each batch ends with a task wait to bound memory. One-worker execution finishes each slice immediately, as the sequential executable does, rather than creating an artificially expensive deferred-export baseline.

Every slice owns an indexed result slot. No worker mutates a shared success counter. An import, processing, or export error fails that slice and the program; valid slices can still complete. Batch boundaries span the sorted inventory rather than restarting for each patient.

The benchmark includes DICOM import, all processing stages, synchronized host readback, and a mask fingerprint. An export workload adds a raw PGM mask and two 512-pixel PNG previews per slice in every configuration. An external timer surrounds the entire subprocess, including startup, discovery, report writing, and shutdown. The internal processing timer is recorded separately. The export benchmark and processing-only control are separate experiments, and their runtimes are not compared as if they perform identical work.

The demo's erosion and dilation remain independent branches of the region-growing mask. Both batch runners compute dilation only, matching the original final-output path.

## FAST concurrency constraints and diagnosis

[FAST 4.10's default OpenCL queue](https://github.com/smistad/FAST/blob/v4.10.0/source/FAST/ExecutionDevice.cpp) is shared and in order. Its named program cache has accesses outside the binary-build mutex. A first full-dataset eight-worker shared-device experiment crashed with SIGSEGV, while smaller and debugger runs passed. The exact cause remains unconfirmed; it is not attributed conclusively to this cache.

Independent worker contexts were tested but introduce transfers: the [DICOM importer](https://github.com/smistad/FAST/blob/v4.10.0/source/FAST/Importers/DICOMFileImporter.cpp) allocates on the global default device, and [image access across contexts](https://github.com/smistad/FAST/blob/v4.10.0/source/FAST/Data/Image.cpp) moves data through the host. Fresh region-growing objects also invoke FAST's serialized program-build path. Merely adding CPU threads did not establish a repeatable GPU-processing gain.

Graph reuse removes repeated setup. A GPU mutex alone still let different CPU workers submit GPU work and produced slower, variable results. The final design keeps GPU submission on one thread and overlaps the independent conversion/export work. The first successful workload slice also initializes named kernels serially, within the measured interval. `OMP_WAIT_POLICY=PASSIVE` is recorded in the final experiments.

The original shared-slice, isolated-context, graph-reuse, mutex, and interrupted battery-powered trials are retained in the laptop's `capstone-refresh-20261002` archive. They are exploratory trials, not pooled with the final measurements. The final AC-powered results use a fixed build, complete workload, randomized measurement order, and all tested configurations. [Final evidence](benchmark-results.md).

## Evidence standard

`scripts/benchmark.py` retains source and binary hashes, input hashes, commands, hardware, power state, every log, and output manifest. Recorded warmups are excluded from medians. Every run must finish every input and match the sequential raw-mask fingerprints. A crash, failed slice, missing report, wrong worker count, or differing output rejects the experiment.

The export experiment also checks SHA-256 equality of every raw PGM and PNG, with an exact file inventory. `scripts/check_pipeline.py` independently checks eight masks and sixteen previews across sequential, one-worker, and four-worker modes over multiple batches. Corrupt DICOM and invalid CLI inputs must fail. These checks run against actual FAST output on the workstation and laptop.

FNV-1a fingerprints are a lightweight regression check. Export SHA-256 checks provide stronger byte-equivalence evidence. Neither validates tumor accuracy. Public evidence contains aggregate timings, environment, counts, and verification outcomes; the full input corpus, input identifiers, and per-slice manifests remain outside the public repository. The separate walkthrough video and poster show one original capstone slice and its processed outputs. Private manifest/report hashes bind the public records to the retained local evidence.

## Public demo and claims

The native viewer now records the real T1 post-contrast MRI slice used by the original 2025 demo. The source file remains present locally and is byte-identical to one file in the benchmark subset. The clip shows the original beside each individual filter and morphology output. An analytic fixture remains available for integration checks. Neither walkthrough duration is a processing measurement.

A separate performance video now shows actual terminal screen recordings of complete one-thread and eight-thread commands, with normal-speed playback. Both sessions execute separately on the original laptop using its unchanged measured binary and verified input manifest. Native output, GNU time, exit status, and export counts remain visible; all 1,380 files per run match by SHA-256. The capture times (29.32 and 9.61 seconds) are distinct from the five-repetition benchmark medians. Complete individual screen recordings, raw terminal output/timing logs, readable transcripts, and verification hashes are retained. The shorter terminal pane holds its final frame while the other finishes.

The [TCIA collection page](https://www.cancerimagingarchive.net/collection/brain-tumor-progression/) lists controlled access. The published walkthrough uses the original capstone scan. Full DICOM inputs, metadata, batch exports, and per-slice reports remain outside the public repository; the video and poster contain the selected slice and its stage outputs.

Use measurements with their workload and hardware. An end-to-end processing-and-export improvement must not be described as acceleration of FAST's segmentation kernels. New 2026 work must not be attributed to the 2025 team submission. The original résumé's unsupported 1.25× and leadership wording require correction.
