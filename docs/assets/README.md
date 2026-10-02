# Media inventory

The [README demo section](../../README.md#demo) presents two native recordings.
All MP4 files are H.264 with browser-compatible pixel formatting.

| Files | Contents |
|---|---|
| `throughput-comparison.mp4`, `.png`, `.vtt` | Complete side-by-side terminal comparison, poster, and captions |
| `terminal-1.mp4`, `terminal-8.mp4` | Complete individual terminal screen recordings |
| `terminal-{1,8}.txt`, `.log`, `.timing` | Readable transcripts, raw terminal output, and timing logs |
| `terminal-comparison.json` | Capture conditions, verification, and media/report hashes |
| `stage-walkthrough.mp4`, `.vtt`, `.txt` | Real original capstone MRI walkthrough, captions, and transcript |
| `stage-viewer.png`, `stage-provenance.json` | Native viewer poster and input/source/video provenance |
| `export-benchmark.{png,svg}`, `processing-benchmark.{png,svg}` | Charts from retained benchmark evidence |
| `video-hosting.json` | GitHub attachment URLs and hashes of their committed MP4 sources |

GitHub attachment URLs enable native players inside the README. The committed
MP4s are the source files; changing a video requires uploading its replacement
and updating the corresponding README URL and hosting manifest. Do not store
temporary signed playback URLs.

The portfolio may serve byte-identical copies with caption tracks for accessible
playback. Keep posters, captions, transcripts, and evidence alongside the video.
The full DICOM corpus, metadata, and batch exports are not part of these assets.
