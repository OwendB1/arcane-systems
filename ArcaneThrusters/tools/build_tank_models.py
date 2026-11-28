"""Build both tank model sets with SEUT, check them with SE1's importer, then install."""
import argparse
from functools import partial
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
from xml.etree import ElementTree as ET

MOD = Path(__file__).resolve().parents[1]
POWER = MOD.parent / "ArcanePower"
SETUP = Path.home() / ".local/share/blender-se1-setup"
GAME = Path.home() / ".local/share/Steam/steamapps/common/SpaceEngineers"
sys.path.insert(0, str(POWER / "tools"))
from package_release import resolve


def check_ports(dummies, grid, charger=False):
    # Native MWM basis after SEUT's axis conversion and the authored 90° roll.
    prefix = "detector_conveyor_small_" if grid == "small" else "detector_conveyor_"
    half_length = 1.25 if grid == "small" else 3.75
    remaining = {prefix + "left": 1, prefix + "right": -1}
    if charger:
        del remaining[prefix + "left"]
    for row in dummies.splitlines():
        key, matrix, _ = row.split("\t")
        if key.startswith("detector_conveyor"):
            sign = remaining.pop(key)
            expected = (0, 0, 1, 0, sign, 0, 0, 0, 0, sign, 0, 0, sign * half_length, 0, 0, 1)
            values = tuple(map(float, matrix.split(",")))
            assert len(values) == 16 and all(abs(a-b) < .0001 for a,b in zip(values, expected)), key
    assert not remaining, remaining


def compile_models(staging, grid, builder, probe, name, check_dummies=None):
    directory = staging / "Models/Cubes" / grid
    counts = json.loads((directory / (name + "-counts.json")).read_text())
    suffixes = ("", "_BS1", "_BS2", "_BS3", "_LOD1", "_LOD2")
    if check_dummies is None:
        suffixes = ("", "_LOD1", "_LOD2")
    assert set(counts) == {name + suffix for suffix in suffixes}
    hkt = directory / (name + ".hkt")
    if check_dummies is not None:
        assert hkt.stat().st_size > 0 and "0 Errors" in hkt.with_suffix(".hkt.filter.log").read_text(errors="replace")
    models = []
    for suffix in suffixes:
        stem = name + suffix
        xml = directory / (stem + ".xml")
        tree = ET.parse(xml)
        for node in tree.iter("Parameter"):
            if (node.text or "").startswith("Textures/Models/ArcanePower/Energy/"):
                original = POWER / "src" / node.text
                node.text = "Textures/Models/ArcaneThrusters/" + original.name
                target = staging / node.text
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(original, target)
        tree.write(xml, encoding="utf-8", xml_declaration=True)
        if suffix.startswith("_BS"):
            shutil.copyfile(hkt, directory / (stem + ".hkt"))
        models.append(directory / (stem + ".mwm"))

    def windows(path):
        return "Z:" + str(path).replace("/", "\\")
    for pattern in (name+"_LOD?.fbx", name+"_BS?.fbx", name+".fbx"):
        if not list(directory.glob(pattern)):
            continue
        subprocess.run(["wine", str(builder), "/f", "/s:"+windows(directory), "/m:"+pattern,
                        "/o:"+windows(directory), "/x:"+windows(SETUP / "assets/Materials")],
                       cwd=builder.parent, env={**os.environ, "WINEPREFIX":str(SETUP / "wineprefix"),
                                              "WINEDEBUG":"-all"}, check=True)

    def inspect(*args):
        return subprocess.check_output(["mono", str(probe), *map(str,args)], text=True,
                                       env={**os.environ, "MONO_PATH":str(GAME/"Bin64")})
    main = models[0]
    if check_dummies is not None:
        check_dummies(inspect("--dummies", main), grid)
    fixed = main.with_suffix(".linked.mwm")
    lods = [p.relative_to(staging).as_posix() for p in models[-2:]]
    inspect("--lod-paths", main, fixed, *lods)
    fixed.replace(main)
    for model in models:
        args = [model, counts[model.stem]]
        if check_dummies is not None and (model == main or "_BS" in model.stem):
            args.append(hkt)
        for row in inspect(*args).splitlines():
            kind, *fields = row.split("\t")
            if kind == "TEXTURE":
                path = fields[0].replace("\\","/")
                assert resolve(staging, path) or resolve(MOD/"src", path) or resolve(GAME/"Content", path), path
    return models


def prepare_tools(work):
    builder_dir = work / "builder"
    shutil.copytree(SETUP/"assets/Tools/MWMBuilder", builder_dir)
    (builder_dir/"MwmBuilder.exe.config").write_text(
        "<configuration><system.diagnostics><trace><listeners><clear/></listeners></trace></system.diagnostics></configuration>")
    probe = work / "EnergyModelProbe.exe"
    subprocess.run(["mcs","-out:"+str(probe),"-r:/usr/lib/mono/4.5/Facades/netstandard.dll",
                    *["-r:"+str(GAME/"Bin64"/(lib+".dll")) for lib in ("VRage.Render","VRage.Math","VRage.Library")],
                    str(POWER/"tools/EnergyModelProbe.cs")],check=True)
    return builder_dir/"MwmBuilder.exe", probe


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--charger", action="store_true", help="Build the recovery charger")
    charger = parser.parse_args().charger
    with TemporaryDirectory(prefix="arcane-tank-build-") as tmp:
        work = Path(tmp)
        builder, probe = prepare_tools(work)
        models = []
        for grid, tag in ((("large", "LG"),) if charger else (("large","LG"),("small","SG"))):
            subtype = "ArcaneThrusters_RecoveryChargerLG" if charger else "ArcaneThrusters_PlasmaTank"+tag
            blend = "arcane-recovery-charger.blend" if charger else "arcane-plasma-tanks.blend"
            subprocess.run(["blender","-b",str(MOD/"assets"/blend),"--python-exit-code","1",
                            "-P",str(MOD/"assets/export_plasma_tanks.py"),"--",str(work),
                            subtype],check=True)
            models.extend(compile_models(work, grid, builder, probe, subtype, partial(check_ports, charger=charger)))
        for path in models + list((work/"Textures/Models/ArcaneThrusters").glob("*.dds")):
            target = MOD/"src"/path.relative_to(work)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path,target)
        print(f"Installed {len(models)} validated tank models.")


if __name__ == "__main__":
    main()
