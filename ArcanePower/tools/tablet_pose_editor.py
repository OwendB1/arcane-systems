"""Launch the offline Blender grip editor with native locally installed hand meshes."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", type=Path, default=Path.home() / ".local/share/Steam/steamapps/common/SpaceEngineers")
    parser.add_argument("--background-check", action="store_true", help="Run the focused editor/export check without opening a window")
    args = parser.parse_args()
    blender = shutil.which("blender")
    if not blender:
        parser.error("Blender must be installed and on PATH")
    cache = ROOT / ".cache/tablet-pose"
    cache.mkdir(parents=True, exist_ok=True)
    binary = args.game / "Bin64"
    exe = cache / "TabletPoseReference.exe"
    reference = cache / "reference.json"
    sources = [
        args.game / "Content/Models/Characters/Astronaut/SE_astronaut_LOD0.mwm",
        args.game / "Content/Models/Characters/Animations/holding_tool.mwm",
        ROOT / "src/Models/Items/ArcanePower_Tablet.mwm",
    ]
    for source in sources:
        if not source.is_file():
            parser.error("Required local model missing: " + str(source))
    subprocess.run(["mcs", "-r:System.Web.Extensions", "-r:/usr/lib/mono/4.5/Facades/netstandard.dll",
                    *["-r:" + str(binary / name) for name in ("VRage.dll", "VRage.Render.dll", "VRage.Math.dll", "VRage.Library.dll")],
                    "-out:" + str(exe), str(ROOT / "tools/TabletPoseReference.cs")], check=True)
    subprocess.run(["mono", str(exe), *map(str, sources), str(reference)], check=True,
                   env={**os.environ, "MONO_PATH": str(binary)})
    data = json.loads(reference.read_text())
    data["authoring"] = {"exe": str(exe), "template": str(sources[1]), "binary": str(binary)}
    reference.write_text(json.dumps(data))
    command = [blender, "--factory-startup"]
    if args.background_check:
        command.append("--background")
    command += ["--python-exit-code", "1", "--python", str(ROOT / "assets/tablet_pose_editor.py"), "--", str(reference)]
    if args.background_check:
        command.append("--check")
    return subprocess.call(command)


if __name__ == "__main__":
    raise SystemExit(main())
