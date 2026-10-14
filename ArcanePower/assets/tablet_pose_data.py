"""Native hand-item pose I/O shared by the editor and definition generator."""
import json
import math
import os
from pathlib import Path
import re
import tempfile
import xml.etree.ElementTree as ET

MODES = {
    "Idle / first person": ("ItemPosition", "ItemOrientation"),
    "Walking / first person": ("ItemWalkingPosition", "ItemWalkingOrientation"),
    "Use / first person": ("ItemShootPosition", "ItemShootOrientation"),
    "Ironsight / first person": ("ItemIronsightPosition", "ItemIronsightOrientation"),
    "Idle / third person": ("ItemPosition3rd", "ItemOrientation3rd"),
    "Walking / third person": ("ItemWalkingPosition3rd", "ItemWalkingOrientation3rd"),
    "Use / third person": ("ItemShootPosition3rd", "ItemShootOrientation3rd"),
    # Native MyHandItemDefinition uses one ironsight transform for both views.
    "Ironsight / third person": ("ItemIronsightPosition", "ItemIronsightOrientation"),
}
TAGS = ["LeftHandPosition", "LeftHandOrientation", "RightHandPosition", "RightHandOrientation"]
TAGS += [tag for pair in MODES.values() for tag in pair]
TAGS = list(dict.fromkeys(TAGS))


def validate(tag, values):
    size = 4 if "Orientation" in tag else 3
    if len(values) != size or not all(math.isfinite(v) for v in values):
        raise ValueError("Invalid transform: " + tag)
    if size == 4 and sum(v * v for v in values) < 1e-12:
        raise ValueError("Zero quaternion: " + tag)
    return list(values)


def read_poses(path):
    root = ET.parse(path).getroot()
    items = [hand for hand in root.findall("HandItems/HandItem")
             if hand.find("Id").get("Subtype") == "ArcanePower_Tablet"]
    if len(items) != 1:
        raise ValueError("Expected exactly one ArcanePower_Tablet hand definition")
    return {tag: validate(tag, [float(items[0].findtext(tag + "/" + axis))
                              for axis in ("XYZW" if "Orientation" in tag else "XYZ")]) for tag in TAGS}


def same(tag, a, b):
    if "Orientation" in tag:
        a = [v / math.sqrt(sum(n * n for n in a)) for v in a]
        b = [v / math.sqrt(sum(n * n for n in b)) for v in b]
        return min(max(abs(x - y) for x, y in zip(a, b)),
                   max(abs(x + y) for x, y in zip(a, b))) < 2e-6
    return max(abs(x - y) for x, y in zip(a, b)) < 2e-7


def atomic_write(path, text):
    path = Path(path)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(text)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def export_poses(path, authoring_path, baseline, edited):
    """Patch only edited vectors; refuse conflicts with changes made since import."""
    path = Path(path)
    current = read_poses(path)
    changes = {tag: validate(tag, edited[tag]) for tag in TAGS if not same(tag, baseline[tag], edited[tag])}
    for tag in changes:
        if not same(tag, current[tag], baseline[tag]):
            raise ValueError(tag + " changed on disk. Reload definitions before exporting.")
    text = path.read_text()
    pattern = r"<HandItem\b[^>]*>.*?</HandItem>"
    candidates = [m for m in re.finditer(pattern, text, re.S)
                  if re.search(r'<Id\b[^>]*\bSubtype=[\"\']ArcanePower_Tablet[\"\']', m.group())]
    if len(candidates) != 1:
        raise ValueError("Cannot locate tablet hand definition")
    match = candidates[0]
    hand = match.group()
    for tag, values in changes.items():
        if "Orientation" in tag:
            length = math.sqrt(sum(v * v for v in values))
            values = [v / length for v in values]
        node = re.search(r"<" + tag + r">.*?</" + tag + ">", hand, re.S)
        if node is None:
            raise ValueError("Missing transform: " + tag)
        replacement = node.group()
        for axis, value in zip("XYZW", values):
            replacement = re.sub(r"(<" + axis + r">)[^<]*(</" + axis + ">)",
                                 lambda m: m[1] + format(value, ".9g") + m[2], replacement)
        hand = hand[:node.start()] + replacement + hand[node.end():]
    if changes:
        atomic_write(path, text[:match.start()] + hand + text[match.end():])
    final = read_poses(path)
    atomic_write(authoring_path, json.dumps(final, indent=2) + "\n")
    return final, list(changes)
