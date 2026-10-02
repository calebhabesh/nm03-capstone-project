#!/usr/bin/env python3
"""Generate a deterministic synthetic DICOM intensity phantom; contains no patient data.

This is an analytic test fixture, not a simulation of MRI acquisition or tumor
anatomy. Explicit-VR Little-Endian encoding follows DICOM PS3.5 section 7.1.2.
No dependencies beyond Python's standard library are needed.
"""
import argparse
import math
import struct
import uuid
from pathlib import Path


def uid(label):
    return '2.25.' + str(uuid.uuid5(uuid.NAMESPACE_URL, 'capstone-synthetic/' + label).int)


def element(group, number, vr, value):
    if isinstance(value, str):
        value = value.encode('ascii')
    if len(value) % 2:
        value += b'\0' if vr in ('UI', 'OB', 'OW') else b' '
    tag = struct.pack('<HH', group, number) + vr.encode('ascii')
    if vr in ('OB', 'OW', 'SQ', 'UN', 'UT'):
        return tag + b'\0\0' + struct.pack('<I', len(value)) + value
    return tag + struct.pack('<H', len(value)) + value


def phantom(size, index):
    pixels = []
    shift = 0.025 * math.sin(index)
    for row in range(size):
        y = (row + 0.5) / size * 2 - 1
        for column in range(size):
            x = (column + 0.5) / size * 2 - 1
            radius = (x / 0.72) ** 2 + (y / 0.91) ** 2
            value = 0
            if radius < 1:
                value = 3800 if radius > 0.88 else 1700
                # Deterministic, smooth interior structure for denoising/sharpening.
                if radius <= 0.88:
                    value += int(90 * math.sin(21 * x) * math.cos(17 * y))
                if ((x + 0.09) / 0.09) ** 2 + ((y + 0.06) / 0.23) ** 2 < 1:
                    value = 650
                if ((x - 0.09) / 0.09) ** 2 + ((y + 0.06) / 0.23) ** 2 < 1:
                    value = 650
                ring = ((x + 0.32 + shift) / 0.19) ** 2 + ((y - 0.24) / 0.20) ** 2
                if ring < 1:
                    value = 2600 if ring > 0.60 else 950
                if ((x - 0.26) / 0.13) ** 2 + ((y - 0.40) / 0.10) ** 2 < 1:
                    value = 2150
            pixels.append(value)
    return struct.pack('<' + str(len(pixels)) + 'H', *pixels)


def generate(size, index):
    sop_class = '1.2.840.10008.5.1.4.1.1.7'  # Secondary Capture Image Storage
    sop_instance = uid(f'image-{size}-{index}')
    metadata = b''.join([
        element(2, 1, 'OB', b'\0\1'), element(2, 2, 'UI', sop_class),
        element(2, 3, 'UI', sop_instance),
        element(2, 0x10, 'UI', '1.2.840.10008.1.2.1'),
        element(2, 0x12, 'UI', uid('implementation')),
        element(2, 0x13, 'SH', 'CAPSTONE_PHANTOM'),
    ])
    attributes = [
        (8, 0x16, 'UI', sop_class), (8, 0x18, 'UI', sop_instance),
        (8, 0x20, 'DA', '20261002'), (8, 0x30, 'TM', '000000'),
        (8, 0x60, 'CS', 'OT'), (8, 0x64, 'CS', 'WSD'),
        (8, 0x103e, 'LO', 'Synthetic intensity phantom; not clinical data'),
        (0x10, 0x10, 'PN', 'CAPSTONE^SYNTHETIC'), (0x10, 0x20, 'LO', 'PHANTOM'),
        (0x20, 0x0d, 'UI', uid('study')), (0x20, 0x0e, 'UI', uid('series')),
        (0x20, 0x11, 'IS', '1'), (0x20, 0x13, 'IS', str(index + 1)),
        (0x28, 2, 'US', struct.pack('<H', 1)), (0x28, 4, 'CS', 'MONOCHROME2'),
        (0x28, 0x10, 'US', struct.pack('<H', size)),
        (0x28, 0x11, 'US', struct.pack('<H', size)), (0x28, 0x30, 'DS', '1\\1'),
        (0x28, 0x100, 'US', struct.pack('<H', 16)),
        (0x28, 0x101, 'US', struct.pack('<H', 16)),
        (0x28, 0x102, 'US', struct.pack('<H', 15)),
        (0x28, 0x103, 'US', struct.pack('<H', 0)),
        (0x7fe0, 0x10, 'OW', phantom(size, index)),
    ]
    return (bytes(128) + b'DICM' + element(2, 0, 'UL', struct.pack('<I', len(metadata)))
            + metadata + b''.join(element(*attribute) for attribute in attributes))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('out-refresh/phantom'))
    parser.add_argument('--count', type=int, default=8)
    parser.add_argument('--size', type=int, default=512)
    args = parser.parse_args()
    if not 1 <= args.count <= 100 or not 100 <= args.size <= 1024:
        parser.error('Count must be 1–100; image size must be 100–1024')
    args.output.mkdir(parents=True, exist_ok=True)
    for index in range(args.count):
        filename = args.output / f'synthetic-phantom-{index:03d}.dcm'
        filename.write_bytes(generate(args.size, index))
    print(f'Generated {args.count} synthetic DICOM fixtures in {args.output}; no patient data')


if __name__ == '__main__':
    main()
