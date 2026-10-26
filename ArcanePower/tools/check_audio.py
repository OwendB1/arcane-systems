"""Check the delivered sound bank, loop seams and SBC asset references.

Asset validation only; does not run the game or existing regression suites.
"""
from pathlib import Path
import wave
import xml.etree.ElementTree as ET

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sounds = ET.parse(ROOT / "src/Data/Audio.sbc").findall("Sounds/Sound")
assert len(sounds) == 22
names = set()
for sound in sounds:
    name = sound.findtext("Id/SubtypeId")
    assert name not in names
    names.add(name)
    assert sound.findtext("Id/TypeId") == "MyObjectBuilder_AudioDefinition"
    assert int(sound.findtext("PreventSynchronization", "-1")) == -1
    loop = sound.findtext("Loopable") == "true"
    element = sound.find("Waves/Wave")
    assert element.get("Type") == "D3"
    path = ROOT / "src" / element.findtext("Loop" if loop else "Start").replace("\\", "/")
    with wave.open(str(path), "rb") as audio:
        assert (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) == (1, 2, 44100)
        samples = np.frombuffer(audio.readframes(audio.getnframes()), dtype="<i2").astype(float) / 32768
    assert np.isfinite(samples).all()
    minimum_rms = .015 if path.stem in ('TileDispense', 'TileRetract') else .05
    assert minimum_rms < np.sqrt(np.mean(samples ** 2)) < .6, name
    assert np.max(np.abs(samples)) < .73, name
    assert abs(np.mean(samples)) < .002, name
    if path.stem in ('Assembly', 'Resonance', 'Load', 'Instability'):
        # Sustained reactor beds keep their low body at every load. This catches
        # reintroduced bright tones/hiss even when pitch definitions stay low.
        energy = np.abs(np.fft.rfft(samples)) ** 2
        frequency = np.fft.rfftfreq(len(samples), 1 / 44100)
        assert energy[frequency > 500].sum() / energy.sum() < .001, (name, 'High-frequency hum returned')
    if path.stem.startswith('Tile'):
        energy = np.abs(np.fft.rfft(samples)) ** 2
        frequency = np.fft.rfftfreq(len(samples), 1 / 44100)
        assert energy[frequency > 1500].sum() / energy.sum() < .001, (name, 'Bright tile clicks returned')
        assert len(samples) / 44100 < .60, (name, 'Tile cue overlaps the next quartet')
    if loop:
        # The wrap must be no steeper than ordinary steps in this waveform.
        assert abs(samples[-1] - samples[0]) <= max(.002, np.quantile(abs(np.diff(samples)), .999)), name
    else:
        assert samples[0] == samples[-1] == 0, name
    print(f"{name}: {len(samples) / 44100:g}s, peak {np.max(abs(samples)):.3f}, {'loop seam OK' if loop else 'fades OK'}")

assert names == {"ArcaneReactor" + n for n in (
    "Assembly", "Resonance", "Load", "Instability", "Ignition", "Shutdown", "Vent", "Explosion",
    "TileDispense", "TileLatch", "TileRetract", "TileStore", "DeckMotion", "HatchMotion")} | {
        "ArcaneReactor" + name + "Pitch" + str(band)
        for name in ("Resonance", "Load") for band in range(1, 5)}
print("PASS: twenty-two cues sharing fourteen mono PCM assets, low hum/tile spectra, valid paths, headroom, DC and loop seams")
