#!/usr/bin/env python3
"""Generate the desktop icons for every platform Atlas Flow bundles for.

Written by hand rather than pulled from a design tool so the repository can
regenerate them with no dependency and no binary blob whose provenance nobody
can check.

Atlas Flow supports Linux, so only PNGs are written by default. The ICO and
ICNS renderers are kept and reachable with --all-platforms: they work, and
throwing away working code to express a scope decision would mean writing it
again if the scope ever widens. What the repository must not do is *ship* an
icon for a platform it does not build or test.

    python scripts/generate_icons.py [--all-platforms]
"""

from __future__ import annotations

import struct
import sys
import zlib
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "apps" / "desktop" / "src-tauri" / "icons"

BACKGROUND = (15, 23, 42)      # slate-900
STEP = (129, 140, 248)         # indigo-400
FINAL_STEP = (52, 211, 153)    # emerald-400

# Three rising steps: a plan advancing, which is what the product does.
STEPS = ((0.20, 0.42), (0.39, 0.61), (0.58, 0.80))


def inside_rounded_square(x: int, y: int, size: int) -> bool:
    radius = size // 5
    corners = (
        (radius, radius, x < radius, y < radius),
        (size - radius, radius, x > size - radius, y < radius),
        (radius, size - radius, x < radius, y > size - radius),
        (size - radius, size - radius, x > size - radius, y > size - radius),
    )
    for cx, cy, past_x, past_y in corners:
        if past_x and past_y and (x - cx) ** 2 + (y - cy) ** 2 > radius**2:
            return False
    return True


def pixel(x: int, y: int, size: int) -> tuple[int, int, int] | None:
    """The colour at a point, or None where the icon is transparent."""
    if not inside_rounded_square(x, y, size):
        return None
    u, v = x / size, y / size
    for index, (x0, x1) in enumerate(STEPS):
        top = 0.68 - index * 0.16
        if x0 <= u <= x1 and top <= v <= top + 0.11:
            return FINAL_STEP if index == len(STEPS) - 1 else STEP
    return BACKGROUND


def render_png(size: int) -> bytes:
    rows = bytearray()
    for y in range(size):
        rows.append(0)  # filter type 0 for every scanline
        for x in range(size):
            colour = pixel(x, y, size)
            rows.extend(colour if colour else (0, 0, 0))
            rows.append(255 if colour else 0)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(bytes(rows), 9))
        + chunk(b"IEND", b"")
    )


def render_ico(sizes: tuple[int, ...]) -> bytes:
    """An ICO holding PNG frames, which Windows has accepted since Vista."""
    frames = [(size, render_png(size)) for size in sizes]
    directory = b""
    offset = 6 + 16 * len(frames)
    for size, payload in frames:
        directory += struct.pack(
            "<BBBBHHII",
            0 if size >= 256 else size,  # 0 means 256
            0 if size >= 256 else size,
            0,  # palette
            0,  # reserved
            1,  # colour planes
            32,  # bits per pixel
            len(payload),
            offset,
        )
        offset += len(payload)
    return (
        struct.pack("<HHH", 0, 1, len(frames))
        + directory
        + b"".join(payload for _, payload in frames)
    )


# The ICNS type code for each frame size. Anything not listed is ignored by
# macOS rather than rejected, so only well-known codes are emitted.
ICNS_TYPES = {32: b"icp5", 128: b"ic07", 256: b"ic08", 512: b"ic09"}


def render_icns(sizes: tuple[int, ...]) -> bytes:
    body = b""
    for size in sizes:
        code = ICNS_TYPES.get(size)
        if code is None:
            continue
        payload = render_png(size)
        body += code + struct.pack(">I", len(payload) + 8) + payload
    return b"icns" + struct.pack(">I", len(body) + 8) + body


def main() -> int:
    all_platforms = "--all-platforms" in sys.argv
    OUT.mkdir(parents=True, exist_ok=True)
    written: list[tuple[str, int]] = []

    for name, size in (
        ("32x32.png", 32),
        ("128x128.png", 128),
        ("128x128@2x.png", 256),
        ("icon.png", 512),
    ):
        payload = render_png(size)
        (OUT / name).write_bytes(payload)
        written.append((name, len(payload)))

    if all_platforms:
        ico = render_ico((16, 32, 48, 64, 128, 256))
        (OUT / "icon.ico").write_bytes(ico)
        written.append(("icon.ico", len(ico)))

        icns = render_icns((32, 128, 256, 512))
        (OUT / "icon.icns").write_bytes(icns)
        written.append(("icon.icns", len(icns)))

    for name, size in written:
        print(f"  {name:18} {size:>8} bytes")
    print(f"{len(written)} icons written to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
