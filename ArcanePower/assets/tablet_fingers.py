"""Tablet-specific finger animation and transactional editor export (offline only)."""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET

from tablet_pose_data import export_poses, same, validate

FINGERS = ("Thumb", "Index", "Middle", "Ring", "Little")
JOINTS = tuple(f"SE_Rig{side}_{finger}_{joint}" for side in "LR" for finger in FINGERS for joint in range(1, 4))
SOURCE = "assets/tablet-fingers.json"
MODEL = "src/Models/Characters/Animations/ArcaneTabletGrip.mwm"
DEFINITION = "src/Data/TabletFingers.sbc"
ANIMATION = "ArcaneTabletGrip"


def validate_fingers(poses):
    if not isinstance(poses, dict) or set(poses) != set(JOINTS):
        raise ValueError("Expected all thirty native finger joints")
    try:
        return {name: {"position": validate(name + "Position", poses[name]["position"]),
                       "orientation": validate(name + "Orientation", poses[name]["orientation"])} for name in JOINTS}
    except (KeyError, TypeError) as error:
        raise ValueError("Each finger joint needs a finite position and nonzero orientation quaternion") from error


def fingers_same(a, b):
    return all(same(key.title(), a[name][key], b[name][key]) for name in JOINTS for key in ("position", "orientation"))


def definitions():
    # Native merging appends this final layer to both controllers. The mask and
    # equipped-item variable restrict it to tablet digits; other tools pass through.
    root = ET.Element("Definitions", {"xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance"})
    def add(parent, tag, text=None, **attrs):
        node = ET.SubElement(parent, tag, attrs)
        if text is not None:
            node.text = str(text)
        return node
    model = MODEL.removeprefix("src/")
    animation = add(add(root, "Animations"), "Animation")
    add(animation, "Id", Type="AnimationDefinition", Subtype=ANIMATION)
    for tag, value in (("AnimationModel", model), ("ClipIndex", 0), ("Loop", "true"),
                       ("InfluenceArea", "LeftFingers RightFingers"), ("Public", "false")):
        add(animation, tag, value)
    for controller in ("Default_Astronaut", "Default_Astronaut_Female"):
        definition = add(root, "Definition", **{"xsi:type": "AnimationControllerDefinition"})
        add(definition, "Id", Type="MyObjectBuilder_AnimationControllerDefinition", Subtype=controller)
        layer = add(add(definition, "Layers"), "Layer")
        for tag, value in (("Name", "ArcaneTabletFingers"), ("Mode", "Replace"),
                           ("StateMachine", "SMArcaneTabletFingers"), ("InitialSMNode", "Inactive"),
                           ("BoneMask", " ".join(JOINTS))):
            add(layer, tag, value)
        machine = add(add(definition, "StateMachines"), "StateMachine")
        add(machine, "Name", "SMArcaneTabletFingers")
        nodes = add(machine, "Nodes")
        inactive = add(nodes, "Node")
        add(inactive, "Name", "Inactive")
        add(inactive, "Type", "PassThrough")
        grip = add(nodes, "Node")
        add(grip, "Name", "Grip")
        add(grip, "Type", "Normal")
        track = add(add(grip, "AnimationTree"), "Child", **{"xsi:type": "MyObjectBuilder_AnimationTreeNodeTrack"})
        for tag, value in (("PathToModel", model), ("AnimationName", ANIMATION),
                           ("Loop", "true"), ("Speed", 1), ("Interpolate", "true")):
            add(track, tag, value)
        transitions = add(machine, "Transitions")
        for start, end, value in (("Inactive", "Grip", "1"), ("Grip", "Inactive", "0")):
            transition = add(transitions, "Transition", From=start, To=end, TimeInSec="0.15", Sync="Restart", Curve="Smooth")
            conjunction = add(add(transition, "Conditions"), "Conjunction")
            add(conjunction, "Condition", Lhs="arcanepower_tablet", Op="Equal", Rhs=value)
    ET.indent(root)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def finger_source(root):
    path = Path(root) / SOURCE
    return path.read_bytes() if path.exists() else None


def export_grip(root, pose_baseline, poses, finger_baseline, source_baseline, fingers, native):
    """Stage/validate everything first, refuse disk conflicts, roll back write failures."""
    root = Path(root)
    fingers = validate_fingers(fingers)
    count = sum(not all(same(k.title(), fingers[n][k], finger_baseline[n][k])
                        for k in ("position", "orientation")) for n in JOINTS)
    if count and finger_source(root) != source_baseline:
        raise ValueError("Finger poses changed on disk. Reload definitions before exporting.")
    files = {}
    originals = {}
    with tempfile.TemporaryDirectory(prefix="tablet-grip-export-") as folder:
        staging = Path(folder)
        tablet = root / "src/Data/Tablet.sbc"
        original_tablet = tablet.read_bytes()
        staged_tablet = staging / "Tablet.sbc"
        staged_tablet.write_bytes(original_tablet)
        pose_source = staging / "poses.json"
        final, changed = export_poses(staged_tablet, pose_source, pose_baseline, poses)
        files["assets/tablet-poses.json"] = pose_source.read_bytes()
        if count:
            source = staging / "fingers.json"
            source.write_text(json.dumps(fingers, indent=2) + "\n")
            model = staging / "ArcaneTabletGrip.mwm"
            result = subprocess.run(["mono", native["exe"], "--export-animation", native["template"], str(source), str(model)],
                                    env={**os.environ, "MONO_PATH": native["binary"]}, capture_output=True, text=True)
            if result.returncode:
                raise ValueError("Native finger animation export failed: " + result.stdout + result.stderr)
            print(result.stdout.strip())
            text, replaced = re.subn(r"<FingersAnimation>[^<]*</FingersAnimation>",
                                    "<FingersAnimation>" + ANIMATION + "</FingersAnimation>", staged_tablet.read_text())
            if replaced != 1:
                raise ValueError("Expected one tablet FingersAnimation")
            staged_tablet.write_text(text)
            files.update({SOURCE: source.read_bytes(), MODEL: model.read_bytes(), DEFINITION: definitions()})
        if staged_tablet.read_bytes() != original_tablet:
            files["src/Data/Tablet.sbc"] = staged_tablet.read_bytes()
        for relative in files:
            path = root / relative
            originals[relative] = path.read_bytes() if path.exists() else None
        # Native export takes time; reject edits made while it ran.
        if tablet.read_bytes() != original_tablet or (count and finger_source(root) != source_baseline):
            raise ValueError("Tablet poses changed during export. Reload before exporting.")
        written = []
        try:
            for relative, data in files.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
                    temporary = Path(stream.name)
                    stream.write(data)
                try:
                    os.replace(temporary, path)
                finally:
                    temporary.unlink(missing_ok=True)
                written.append(relative)
        except OSError:
            for relative in reversed(written):
                path = root / relative
                if originals[relative] is None:
                    path.unlink(missing_ok=True)
                else:
                    path.write_bytes(originals[relative])
            raise
    return final, changed, fingers, count
