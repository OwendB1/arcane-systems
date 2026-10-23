"""Original procedural Arcane reactor sound bank (Python + NumPy).

No sampled recordings or external audio assets. Regenerates shipped mono PCM
waves, SE audio definitions and a staged listening preview; does not deploy.
"""
from pathlib import Path
import wave
import xml.etree.ElementTree as ET

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RATE = 44100
TAU = 2 * np.pi
LOOPS = ("Assembly", "Resonance", "Load", "Instability", "DeckMotion", "HatchMotion")


def timeline(seconds):
    return np.arange(round(seconds * RATE)) / RATE


def tone(t, hz, modulation=0):
    return np.sin(TAU * hz * t + modulation)


def noise(t, low, high, seed):
    """Band-limited periodic noise: the loop boundary has no noise splice."""
    rng = np.random.default_rng(seed)
    bins = np.fft.rfftfreq(len(t), 1 / RATE)
    spectrum = np.fft.rfft(rng.normal(size=len(t)))
    shape = np.exp(-(bins / high) ** 4) * (1 - np.exp(-(bins / low) ** 4))
    result = np.fft.irfft(spectrum * shape, n=len(t))
    return result / max(np.std(result), 1e-8)


def envelope(t, attack, decay):
    return (1 - np.exp(-t / attack)) * np.exp(-t / decay)


def finish(samples, loop=False, attack=.025):
    samples = samples - np.mean(samples)
    if not loop:
        fade = min(round(attack * RATE), len(samples) // 2)
        samples[:fade] *= np.linspace(0, 1, fade)
        tail = min(round(.4 * RATE), len(samples) // 2)
        samples[-tail:] *= np.linspace(1, 0, tail) ** 2
    return samples * (.72 / max(np.max(np.abs(samples)), 1e-8))


def write_wave(path, samples):
    path.parent.mkdir(parents=True, exist_ok=True)
    assert np.max(np.abs(samples)) < 1, path
    with wave.open(str(path), "wb") as output:
        output.setparams((1, 2, RATE, len(samples), "NONE", "not compressed"))
        output.writeframes(np.round(samples * 32767).astype("<i2").tobytes())


def sound_bank():
    t = timeline(8)
    # Integer cycle counts for carriers AND modulators keep all four beds seamless.
    # Sustained field sounds retain the low body without upper whistles or hiss.
    breath = .72 + .28 * tone(t, .25)
    assembly = breath * (tone(t, 110, .8 * tone(t, .5)) + .36 * tone(t, 165))
    resonance = (.8 + .2 * tone(t, 1.5)) * (
        tone(t, 41.25, .25 * tone(t, .25)) + .48 * tone(t, 82.5)
        + .22 * tone(t, 123.75))
    load = (.45 + .55 * (.5 + .5 * tone(t, 4)) ** 2) * (
        .65 * tone(t, 82.5, 1.8 * tone(t, 41.25)) + .35 * tone(t, 165)
        + .18 * tone(t, 248.25) + .08 * noise(t, 40, 180, 1))
    unstable = np.tanh(2 * (tone(t, 56, 2 * tone(t, 7.25))
                           + .45 * tone(t, 83.125))) * (.35 + .65 * (.5 + .5 * tone(t, 6)) ** 4)
    unstable += .2 * noise(t, 30, 180, 2) * (.5 + .5 * tone(t, 9.5)) ** 12
    bank = {name: finish(samples, True) for name, samples in
            zip(LOOPS[:4], (assembly, resonance, load, unstable))}

    # Geared actuators: motor body, upper gear harmonics and dry roller/tooth
    # chatter. Periodic pulse trains preserve the seamless eight-second bed.
    deck = .65 * tone(t, 75) + .26 * tone(t, 150) + .12 * tone(t, 900)
    deck += .1 * tone(t, 1800, .2 * tone(t, 6)) + .1 * noise(t, 250, 7500, 10)
    deck += .35 * (.5 + .5 * tone(t, 18)) ** 16 * noise(t, 600, 10000, 15)
    hatch = .45 * tone(t, 137.5) + .22 * tone(t, 275) + .12 * tone(t, 550)
    hatch += .17 * tone(t, 1100, .3 * tone(t, 8)) + .08 * tone(t, 3300)
    hatch += .13 * noise(t, 350, 9000, 11)
    hatch += .42 * (.5 + .5 * tone(t, 24)) ** 20 * noise(t, 1000, 11000, 16)
    bank["DeckMotion"] = finish(deck, True)
    bank["HatchMotion"] = finish(hatch, True)

    t = timeline(.26)
    dispense = envelope(t, .002, .035) * noise(t, 800, 10500, 12)
    dispense += .5 * envelope(t, .003, .05) * np.sin(TAU * (240 * t + 450 * t * t))
    bank["TileDispense"] = finish(dispense, attack=.001)
    t = timeline(.22)
    # A damped structural thunk with a brief hard catch. No sustained metallic
    # 880/1320 Hz ring; retain the high-frequency click only at initial contact.
    latch = 1.2 * envelope(t, .001, .04) * tone(t, 115)
    latch += .45 * envelope(t, .001, .025) * tone(t, 230)
    latch += .4 * envelope(t, .001, .025) * noise(t, 60, 650, 13)
    latch += .65 * envelope(t, .0004, .0035) * noise(t, 1600, 11000, 17)
    bank["TileLatch"] = finish(latch, attack=.0005)

    t = timeline(.48)
    # Short release click followed by a descending geared pull. The separate
    # TileLatch cue supplies the deeper catch when the quartet reaches home.
    retract = .6 * envelope(t, .0005, .009) * noise(t, 1200, 10000, 18)
    pull = envelope(t, .015, .12)
    retract += pull * (.7 * np.sin(TAU * (310 * t - 170 * t * t))
        + .24 * np.sin(TAU * (1240 * t - 680 * t * t))
        + .15 * noise(t, 300, 7000, 19))
    bank["TileRetract"] = finish(retract, attack=.0005)

    t = timeline(3.5)
    ignition = envelope(t, .008, .65) * (tone(t, 55) + .5 * tone(t, 110))
    ignition += envelope(t, .035, 1.1) * (
        .5 * np.sin(TAU * (330 * t + 90 * (1 - np.exp(-3 * t))))
        + .32 * tone(t, 660) + .15 * noise(t, 300, 5000, 3))
    bank["Ignition"] = finish(ignition)

    t = timeline(4)
    shutdown = envelope(t, .035, .9) * np.sin(TAU * (42 * t + 160 * (1 - np.exp(-t))))
    shutdown += .2 * envelope(t, .04, 1.3) * tone(t, 165)
    bank["Shutdown"] = finish(shutdown)

    t = timeline(3)
    vent = envelope(t, .009, .5) * (noise(t, 180, 4200, 4)
        + .6 * np.sin(TAU * (60 * t + 100 * (1 - np.exp(-4 * t)))))
    vent += .2 * envelope(t, .02, .8) * tone(t, 440, 2 * tone(t, 55))
    bank["Vent"] = finish(vent)

    t = timeline(8)
    # Immediate energy fracture, low pressure body, dissonant ringing and long tail.
    blast = 1.4 * envelope(t, .002, .065) * noise(t, 700, 6500, 5)
    blast += envelope(t, .005, .8) * noise(t, 22, 600, 6)
    blast += 1.5 * envelope(t, .005, 1.1) * np.sin(TAU * (30 * t + 45 * (1 - np.exp(-5 * t))))
    blast += .2 * envelope(t, .008, 1.8) * (tone(t, 220) + .5 * tone(t, 311))
    blast += .18 * envelope(t, .3, 1.5) * noise(t, 80, 1800, 7)
    bank["Explosion"] = finish(np.tanh(blast))
    return bank


def definitions(bank):
    root = ET.Element("Definitions")
    sounds = ET.SubElement(root, "Sounds")
    entries = [(name, name, 0) for name in bank]
    entries += [(name + "Pitch" + str(band), name, band)
                for band in range(1, 5) for name in ("Resonance", "Load")]
    for name, source, band in entries:
        loop = source in LOOPS
        sound = ET.SubElement(sounds, "Sound")
        identity = ET.SubElement(sound, "Id")
        ET.SubElement(identity, "TypeId").text = "MyObjectBuilder_AudioDefinition"
        ET.SubElement(identity, "SubtypeId").text = "ArcaneReactor" + name
        ET.SubElement(sound, "Category").text = "SHIP"
        mechanical = name in ("DeckMotion", "HatchMotion", "TileDispense", "TileLatch", "TileRetract")
        ET.SubElement(sound, "MaxDistance").text = "1500" if name == "Explosion" else "60" if name == "Vent" else "18" if mechanical else "24"
        # Poly2 is SE's steep (1-distance)^2 falloff. The default Custom_1
        # stays almost full-volume through most of the audible radius.
        if name != "Explosion":
            ET.SubElement(sound, "VolumeCurve").text = "Poly2"
        ET.SubElement(sound, "Volume").text = "1" if loop else ".85"
        if source in ("Assembly", "Resonance", "Load"):
            # Native Pitch is measured in semitones. Reuse the same WAVs;
            # Keep the low idle tone: full load rises less than one semitone.
            # Runtime crossfades five load points from 0.65x to 0.68x playback.
            ET.SubElement(sound, "Pitch").text = f"{12 * np.log2(.65 + .03 * band / 4):.6f}"
        ET.SubElement(sound, "Loopable").text = str(loop).lower()
        waves = ET.SubElement(sound, "Waves")
        waveform = ET.SubElement(waves, "Wave", Type="D3")
        ET.SubElement(waveform, "Loop" if loop else "Start").text = "Audio\\ArcanePower\\" + source + ".wav"
    ET.indent(root, space="  ")
    ET.ElementTree(root).write(ROOT / "src/Data/Audio.sbc", encoding="utf-8", xml_declaration=True)


def preview(bank):
    """Palette demo, not a recording or a simulation of the tier-specific startup."""
    t = timeline(44)
    output = np.zeros(len(t))

    def bed(name, start, end, gain):
        mask = (t >= start) & (t < end)
        age = t[mask] - start
        fade = np.minimum(np.minimum(age / .5, (end - t[mask]) / .5), 1)
        source = np.resize(bank[name], len(age))
        if name in ("Assembly", "Resonance", "Load"):
            step = np.zeros(len(age)) if name == "Assembly" else 4 * np.clip((t[mask] - 13) / 8, 0, 1)
            source = np.zeros(len(age))
            for band in range(5):
                index = np.arange(len(age)) * (.65 + .03 * band / 4) % len(bank[name])
                low = index.astype(int)
                shifted = bank[name][low] * (1 - (index - low)) + bank[name][(low + 1) % len(bank[name])] * (index - low)
                source += shifted * np.sqrt(np.maximum(0, 1 - abs(step - band)))
        output[mask] += source * gain(age) * fade

    def cue(name, start, gain):
        offset = round(start * RATE)
        samples = bank[name][:len(output) - offset]
        output[offset:offset + len(samples)] += samples * gain

    bed("Assembly", 0, 8, lambda a: .12 + .28 * a / 8)
    cue("Ignition", 8, .65)
    bed("Resonance", 8, 30, lambda a: .38 + .12 * np.clip((a - 5) / 8, 0, 1))
    bed("Load", 13, 30, lambda a: .65 * np.clip(a / 8, 0, 1))
    bed("Instability", 23, 30, lambda a: .6 * np.clip(a / 5, 0, 1))
    cue("Vent", 30, .85)
    cue("Explosion", 34, .85)
    cue("Shutdown", 40, .65)
    write_wave(ROOT / ".cache/audio/reactor-palette.wav", output * .7)


def mechanism_preview(bank):
    """Deck 0-2s; placement 3-5s; hatch 6-7.5/9-10.5s; retraction 12-14s."""
    output = np.zeros(len(timeline(15)))
    for name, start, duration in [("DeckMotion", 0, 2), ("HatchMotion", 6, 1.5), ("HatchMotion", 9, 1.5)]:
        count = round(duration * RATE)
        samples = bank[name][:count].copy()
        fade = np.minimum(np.minimum(np.arange(count) / (.05 * RATE), np.arange(count)[::-1] / (.05 * RATE)), 1)
        offset = round(start * RATE)
        output[offset:offset + count] += samples * fade * .55
    for start in (3, 3.7, 4.4):
        for name, delay in (("TileDispense", 0), ("TileLatch", .4)):
            samples = bank[name];offset = round((start + delay) * RATE)
            output[offset:offset + len(samples)] += samples * .55
    for start in (12, 12.7, 13.4):
        for name, delay in (("TileRetract", 0), ("TileLatch", 34 / 60)):
            samples = bank[name];offset = round((start + delay) * RATE)
            output[offset:offset + len(samples)] += samples * .55
    write_wave(ROOT / ".cache/audio/reactor-mechanisms.wav", output)


if __name__ == "__main__":
    bank = sound_bank()
    for name, samples in bank.items():
        write_wave(ROOT / "src/Audio/ArcanePower" / (name + ".wav"), samples)
    definitions(bank)
    preview(bank)
    mechanism_preview(bank)
    print("Wrote thirteen original WAVs, twenty-one cue definitions and both listening previews")
