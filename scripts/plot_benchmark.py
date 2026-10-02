#!/usr/bin/env python3
"""Plot retained benchmark medians, ranges, and every measured run (requires matplotlib)."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='Path without an extension')
    args = parser.parse_args()
    summary = json.loads((args.results / 'summary.json').read_text())
    runs = json.loads((args.results / 'runs.json').read_text())
    metadata = json.loads((args.results / 'metadata.json').read_text())
    fig, ax = plt.subplots(figsize=(10, 5.3), layout='constrained')
    fig.set_facecolor('#f7f6f2')
    ax.set_facecolor('#f7f6f2')
    for i, row in enumerate(summary):
        color = '#1d6141' if row['threads'] > 1 else '#65746d'
        median = row['median_seconds']
        ax.barh(i, median, color=color, height=.53)
        ax.errorbar(median, i, xerr=[[median-row['min_seconds']], [row['max_seconds']-median]],
                    fmt='none', ecolor='#161f1b', capsize=5, linewidth=1.2)
        values = [r['wall_seconds'] for r in runs
                  if r['configuration'] == row['configuration'] and r['role'] == 'measurement']
        offsets = [(j - (len(values)-1)/2) * .055 for j in range(len(values))]
        ax.scatter(values, [i+offset for offset in offsets], s=23,
                   facecolors='#f7f6f2', edgecolors='#161f1b', linewidths=.9, zorder=4)
        ax.text(row['max_seconds'] + .4, i, f'{median:.2f} s', va='center', color='#161f1b')
    labels = ['Sequential' if r['configuration'] == 'sequential'
              else f"OpenMP · {r['threads']} thread" + ('s' if r['threads'] != 1 else '')
              for r in summary]
    ax.set_yticks(range(len(summary)), labels)
    ax.invert_yaxis()
    ax.set_xlim(0, max(r['max_seconds'] for r in summary)*1.18)
    ax.set_xlabel('Whole-program elapsed time (seconds) · lower is faster', labelpad=12)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(axis='both', length=0, pad=10, labelsize=11)
    ax.set_axisbelow(True)
    ax.grid(axis='x', color='#d5dbd6', linewidth=.7)
    scope = 'processing + lossless exports' if metadata['export_previews'] else 'processing + mask readback'
    fig.suptitle(f"{metadata['slice_count']} DICOM slices · {scope}",
                 fontsize=18, fontweight='bold', color='#161f1b', ha='left', x=.02)
    ax.set_title(f"{metadata['repetitions']} measured runs per configuration · bars = median · dots = each run · whiskers = range",
                 loc='left', fontsize=10, color='#38423d', pad=16)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for extension in ('svg', 'png'):
        destination = args.output.with_suffix('.'+extension)
        fig.savefig(destination, dpi=180)
        if extension == 'svg':
            destination.write_text('\n'.join(line.rstrip() for line in destination.read_text().splitlines()) + '\n')
    plt.close(fig)


if __name__ == '__main__':
    main()
