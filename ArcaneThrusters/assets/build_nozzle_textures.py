"""Author the bell's two UV regions and convert SE packed maps using Arcane Power's converter."""

import math
import runpy
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "Textures/Models/ArcaneThrusters"
convert = runpy.run_path(str(ROOT.parents[1] / "ArcanePower/tools/texture_conversion.py"))["convert"]
WIDTH, HEIGHT = 2048, 1024
FONT = "/usr/share/fonts/dejavu-sans-fonts/DejaVuSansCondensed-Bold.ttf"


def maps():
    rng = np.random.default_rng(42)
    row, col = np.mgrid[:HEIGHT, :WIDTH]
    u = col / WIDTH
    # The mesh reserves an eight-pixel gutter at either end of each skin.
    outer = row < 608
    t = np.clip(np.where(outer, (row - 8) / 590, (row - 617) / 398), 0, 1)
    phase = math.tau * u
    cloud = np.sin(phase * 7 + 5 * t) + 0.7 * np.sin(phase * 19 - 9 * t) + 0.35 * np.sin(phase * 41 + 10 * t)
    satin = rng.normal(0, 1.7, t.shape) + rng.normal(0, 1.4, (HEIGHT, 1))
    rib = (0.5 + 0.5 * np.cos(phase * 130)) ** 5
    lip = np.exp(-(((t - 0.93 - cloud * 0.008) / 0.062) ** 2))
    straw = np.exp(-(((t - 0.84 - cloud * 0.013) / 0.07) ** 2))
    blue = np.exp(-(((t - 0.72 - cloud * 0.011) / 0.10) ** 2))
    seam = np.exp(-((np.sin(phase * 4) / 0.033) ** 2))
    exterior = np.stack(
        [
            88 + 29 * straw + 10 * lip - 11 * blue,
            93 + 16 * straw + 4 * lip - 8 * blue,
            97 - 8 * straw + 7 * lip + 8 * blue,
        ],
        axis=-1,
    )
    # The liner is darkest deep in the bore, with a lighter burnished mouth.
    interior = np.stack([44 + 38 * t, 48 + 34 * t, 53 + 32 * t], axis=-1)
    color = np.where(outer[:, :, None], exterior, interior)
    color += (satin + cloud * 1.8 + np.where(outer, -2 * seam, -10 * rib))[:, :, None]
    metal = np.where(outer, 151 + 35 * lip, 136 + 41 * t)

    marks = Image.new("L", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(marks)
    word = ImageFont.truetype(FONT, 36)
    serial = ImageFont.truetype(FONT, 17)
    for x in (345, 1369):
        draw.text((x, 115), "ARCANE", font=word, fill=236, anchor="mm", stroke_width=0)
        draw.rectangle((x - 57, 139, x + 57, 142), fill=225)
        draw.text((x, 157), "H2  /  PLASMA", font=serial, fill=218, anchor="mm")
        for offset in (-72, 72):
            draw.rectangle((x + offset - 1, 115, x + offset + 1, 132), fill=188)
    mask = np.asarray(marks) / 255 * np.clip(0.91 + 0.08 * cloud + 0.08 * satin, 0.42, 1)
    color = color * (1 - mask[:, :, None]) + np.array([206, 214, 211]) * mask[:, :, None]
    metal = metal * (1 - mask) + 31 * mask
    # Short circumferential brush strokes and tube fluting affect the normal/gloss map.
    height = np.where(outer, 0.065 * np.sin(row * 1.43) + 0.09 * seam, 0.55 * rib)
    height += rng.normal(0, 0.028, t.shape)
    dy, dx = np.gradient(height)
    gloss = (
        np.where(outer, 116 + 42 * lip - 12 * blue, 73 + 32 * t - 13 * rib) + cloud * 3 + satin - 42 * mask
    )

    def rgba(channels):
        return Image.fromarray(np.clip(np.stack(channels, axis=-1), 0, 255).astype("uint8"))

    return {
        "cm": rgba([*color.transpose(2, 0, 1), metal]),
        "ng": rgba([128 - dx * 104, 128 + dy * 82, 255 / np.sqrt(1 + dx * dx + dy * dy), gloss]),
    }


def casting_maps():
    # Tileable cast grain, with a lower sheen than the machined cover/flanges.
    y, x = np.mgrid[:512, :512] / 512 * math.tau
    rng = np.random.default_rng(17)
    cloud = sum(
        np.cos(ix * x + iy * y + phase)
        for ix, iy, phase in [(2, 3, 0.3), (4, -3, 1.7), (7, 5, 4.1), (9, 1, 2.1)]
    )
    pits = rng.random(x.shape) ** 18
    height = rng.normal(0, 0.15, x.shape) - pits * 0.8
    dx = (np.roll(height, 1, 1) - np.roll(height, -1, 1)) * 0.5
    dy = (np.roll(height, 1, 0) - np.roll(height, -1, 0)) * 0.5
    base = 119 + 2 * cloud + height * 5

    def rgba(*channels):
        return Image.fromarray(np.clip(np.stack(channels, axis=-1), 0, 255).astype("uint8"))

    return {
        "cm": rgba(base - 3, base + 1, base + 3, 146 + cloud * 2),
        "ng": rgba(
            128 + dx * 100, 128 + dy * 100, 255 / np.sqrt(1 + dx * dx + dy * dy), 84 + cloud * 3 - pits * 22
        ),
    }


if __name__ == "__main__":
    with TemporaryDirectory() as tmp:
        for name, channels in (
            ("ShuttleBell", maps()),
            ("ShuttleCasting", casting_maps()),
        ):
            for kind, image in channels.items():
                source = Path(tmp) / f"{name}_{kind}.png"
                image.save(source)
                convert(source, OUTPUT, linear=kind == "ng")
