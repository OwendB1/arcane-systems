"""Render four original tile sound auditions without changing the shipped bank.

Each preview has three deployments, a pause, then three retractions, using the
runtime's 0.60 s quartet cadence and 34/60 s travel time. Run from any directory.
Use --magnetic-lock for the revised, low-frequency magnetic locking audition.
"""
from pathlib import Path
import sys

import numpy as np

from build_audio import RATE, envelope, magnetic_tile_sounds, noise, timeline, tone, write_wave

OUT = Path(__file__).resolve().parents[1] / '.cache/audio/tile-alternatives'


def place(output, sound, seconds, gain=1):
    start = round(seconds * RATE)
    count = min(len(sound), len(output) - start)
    output[start:start + count] += sound[:count] * gain


def click(seed, body=180, weight=1):
    t = timeline(.15)
    # Inharmonic, rapidly damped contact; no sustained note or pitch sweep.
    sound = .32 * envelope(t, .0007, .017) * tone(t, body)
    sound += .12 * envelope(t, .0004, .009) * tone(t, body * 2.71)
    sound += .17 * envelope(t, .0003, .003) * noise(t, 1400, 7600, seed)
    sound += .13 * envelope(t, .001, .012) * noise(t, 90, 1400, seed + 1)
    return sound * weight


def movement(style, seed, retract=False):
    t = timeline(.48)
    sound = np.zeros(len(t))
    if style == 'magnetic':
        place(sound, click(seed, 260, .55), 0)
        # A low coil response under a smooth, non-tonal guide swish.
        shape = np.sin(np.pi * np.clip((t - .025) / .36, 0, 1)) ** 2
        sound += shape * (.10 * noise(t, 250, 2600, seed + 2)
                          + .025 * tone(t, 92))
        if retract:
            place(sound, click(seed + 4, 330, .20), .018)
    elif style == 'industrial':
        place(sound, click(seed, 170, .95), 0)
        place(sound, click(seed + 2, 290, .60), .027)
        shape = envelope(t, .018, .11)
        sound += .105 * shape * noise(t, 100, 2300, seed + 3)
        # A few irregular roller contacts rather than a pitched motor whine.
        rng = np.random.default_rng(seed)
        for i, at in enumerate((.10, .19, .29)):
            place(sound, click(seed + 5 + i * 2, 320, .13),
                  at + rng.uniform(-.012, .012))
    elif style == 'pneumatic':
        place(sound, click(seed, 440, .40), 0)
        shape = envelope(t, .012 if retract else .004, .10)
        sound += .30 * shape * noise(t, 200, 4200 if retract else 6000, seed + 2)
        sound += .07 * envelope(t, .01, .045) * noise(t, 60, 600, seed + 3)
    elif style == 'precision':
        place(sound, click(seed, 600 if retract else 480, .45), 0)
        # The quiet option leaves travel almost silent.
        sound += .018 * envelope(t, .025, .07) * noise(t, 800, 3500, seed + 2)
    else:
        raise ValueError(style)
    # Gentle sample-edge ramps avoid digital clicks while retaining the contact.
    sound[:44] *= np.linspace(0, 1, 44)
    sound[-441:] *= np.linspace(1, 0, 441)
    return sound


def arrival(style, seed, home=False):
    if style == 'magnetic':
        return click(seed, 125 if home else 230, .85 if home else .65)
    if style == 'industrial':
        return click(seed, 95 if home else 140, 1.1)
    if style == 'pneumatic':
        return click(seed, 135 if home else 190, .80)
    if style == 'precision':
        return click(seed, 380 if home else 740, .48)
    raise ValueError(style)


def render(style):
    output = np.zeros(len(timeline(5.6)))
    for cycle in range(3):
        seed = 100 + cycle * 20
        start = .20 + cycle * .60
        place(output, movement(style, seed), start)
        place(output, arrival(style, seed + 10), start + 34 / 60)
        start = 3.20 + cycle * .60
        place(output, movement(style, seed + 200, True), start)
        place(output, arrival(style, seed + 210, True), start + 34 / 60)
    return output


def refined_magnetic_preview():
    output = np.zeros(len(timeline(5.6)))
    for cycle in range(3):
        seed = 400 + cycle * 20
        bank = magnetic_tile_sounds(seed)
        start = .20 + cycle * .60
        place(output, bank['TileDispense'], start)
        place(output, bank['TileLatch'], start + 34 / 60)
        start = 3.20 + cycle * .60
        place(output, bank['TileRetract'], start)
        place(output, bank['TileStore'], start + 34 / 60)
    frequencies = np.fft.rfftfreq(len(output), 1 / RATE)
    output -= np.mean(output)
    ramp = round(.02 * RATE)
    output[:ramp] *= np.linspace(0, 1, ramp)
    output[-ramp:] *= np.linspace(1, 0, ramp)
    output *= .72 / np.max(np.abs(output))
    assert np.isfinite(output).all() and np.max(np.abs(output)) < .73
    power = np.abs(np.fft.rfft(output)) ** 2
    high_fraction = np.sum(power[frequencies > 1500]) / np.sum(power)
    assert high_fraction < .001
    path = OUT / '05-magnetic-lock-refined.wav'
    write_wave(path, output)
    print(f'{path.name}: lossless PCM, {RATE} Hz; '
          f'{100 * high_fraction:.5f}% of spectral energy above 1.5 kHz')


def main():
    if '--magnetic-lock' in sys.argv:
        refined_magnetic_preview()
        return
    styles = ('magnetic', 'industrial', 'pneumatic', 'precision')
    previews = {style: render(style) for style in styles}
    # One shared gain preserves the deliberately quieter precision palette.
    gain = .76 / max(np.max(np.abs(sound)) for sound in previews.values())
    for index, (style, sound) in enumerate(previews.items(), 1):
        sound *= gain
        assert np.isfinite(sound).all() and np.max(np.abs(sound)) < .77
        assert abs(np.mean(sound)) < .001
        path = OUT / f'{index:02d}-{style}.wav'
        write_wave(path, sound)
        print(f'{path.name}: {len(sound) / RATE:.1f}s, '
              f'peak {20 * np.log10(np.max(np.abs(sound))):.1f} dBFS')


if __name__ == '__main__':
    main()
