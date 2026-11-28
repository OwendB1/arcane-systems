"""Bake grayscale, premultiplied exhaust sprites using Arcane Power's DDS pipeline."""
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

import numpy as np
from PIL import Image

pack = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(pack.parent / "ArcanePower/tools"))
from texture_conversion import convert


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t*t*(3 - 2*t)


u, v = np.meshgrid(np.linspace(0, 1, 1024), np.linspace(-1, 1, 128))
entry = smoothstep(0, .032, u)

# Soft, spreading shear layer. Warping the wisps preserves an unbroken jet
# while avoiding mirror symmetry and a ruler-straight, triangular tip.
mix = smoothstep(.12, .84, u)
grain = np.sin(51*u + 7*v + 2*np.sin(8*v - 17*u))
wisp = .5 + .5*np.sin(92*u - 9*v + 2.7*grain)
center = mix * (.043*np.sin(18*u) + .021*np.sin(37*u + .7))
r = np.abs(v - center)
spread = .40 + .37*smoothstep(0, .80, u) + .05*mix*grain
fade = (1 - smoothstep(.32, 1, u))**1.12
envelope = np.exp(-2.3*(r/spread)**2) * (.46 + .13*mix*wisp) * fade
# A full-bore jet leaves the lip, then contracts before the first shock.
# The sprite is 1.45 nozzle radii wide, so the inner rim falls at v = 1/1.45.
exit_radius = (1 - .27*smoothstep(0, .12, u))/1.45
aperture = (1 - smoothstep(.78, 1, r/exit_radius)) * (.49 - .24*(r/exit_radius)**2)
transition = smoothstep(.015, .14, u)
envelope = aperture*(1 - transition) + envelope*transition
# Feather the outer edge to zero across the full sprite, including the faint tail.
envelope *= entry * (1 - smoothstep(.84, 1, np.abs(v)))

# Broad translucent barrels terminate in a brighter, flattened knot. Later
# cells lose their distinct fronts as their light mixes into the tail.
cells = .23*np.exp(-3*(r/.35)**2) * (1 - smoothstep(.015, .095, u))
fronts = (.12, .265, .398, .52, .632, .735)
start = .04
for i, end in enumerate(fronts):
    span = end - start
    t = (u - start)/span
    inside = (t >= 0) & (t < 1)
    profile = np.sin(np.pi*np.clip(t, 0, 1))**.78
    radius = .075 + (.27 - .017*i)*profile
    barrel = np.exp(-1.8*(r/radius)**2)
    edge = np.exp(-((r - .78*radius)/(.065 + .009*i))**2)
    front = np.exp(-((u - end + .035*span*(r/.20)**2)/(.11*span + .002*i))**2
                   - (r/(.18 + .016*i))**4)
    cells += np.exp(-.36*i) * (inside * profile * (.17*barrel + .17*edge) + .91*front)
    start = end
cells = entry * np.clip(cells, 0, 1)
x, y = np.meshgrid(np.linspace(-1, 1, 128), np.linspace(-1, 1, 128))
disc_radius = np.hypot(x, y)
glow = (1 - smoothstep(.80, 1, disc_radius)) * (.52 - .19 * np.minimum(disc_radius, 1)**2)

with TemporaryDirectory() as temp:
    for name, alpha in (("Envelope", envelope), ("Cells", cells), ("Mouth", glow)):
        # The tail loses both opacity and radiance. Keeping its RGB white
        # leaves even the faint, late cells looking chalky under SE tonemapping.
        if name == "Mouth":
            radiance = 1 - .51*smoothstep(.18, 1, disc_radius)
        else:
            radiance = (1 - (.80 if name == "Cells" else .56)*smoothstep(.10, .83, u))
        sprite = Image.fromarray(np.uint8(255 * radiance)).convert("RGBA")
        sprite.putalpha(Image.fromarray(np.uint8(255 * alpha)))
        sprite.save(Path(temp) / (name + ".png"))
    convert(Path(temp) / "*.png", pack / "src/Textures/Particles/ArcaneThrusters", icon=True)
