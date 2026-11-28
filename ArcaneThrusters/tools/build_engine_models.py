"""Compile the exposed and hull engine meshes and validate them with the game importer."""

import argparse
import math
import shutil
import subprocess
from functools import partial
from pathlib import Path
from tempfile import TemporaryDirectory

from build_tank_models import MOD, compile_models, prepare_tools


def check_engine(dummies, grid, family, mount):
    rows = {
        name: tuple(map(float, values.split(",")))
        for name, values, _ in (line.split("\t") for line in dummies.splitlines())
    }
    # Native MWM axes after the SEUT transform. Exhaust positions are in metres.
    half, lip, diameter, centers = {
        "atmospheric": (2.50, 2.32, 1.14 * 3.08, [(0, 0)]),
        "shuttle": (1.25, 1.231, 1.14, [(0, 0)]),
        "main": (3.75, 3.57, 1.14 * 4.52, [(0, 0)]),
        "thermal": (5.0, 4.82, 1.14 * 2.43, [(0, 1.75), (1.73, -1.16), (-1.73, -1.16)]),
    }["thermal" if family == "vacuum" else family]
    if family in ("thermal", "vacuum") and mount == "open":
        half, lip = 3.75, 3.57
        diameter, centers = 1.14 * 2.69, [(0, 1.925), (1.87, -1.35), (-1.87, -1.35)]
    port = "detector_conveyor_small_inlet" if grid == "small" else "detector_conveyor_inlet"
    expected = {port: (-1, 0, 0, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, half, 1)}
    for i, (x, y) in enumerate(centers, 1):
        expected[f"thruster_flame_{i:02}"] = (
            diameter,
            0,
            0,
            0,
            0,
            diameter,
            0,
            0,
            0,
            0,
            diameter,
            0,
            x,
            y,
            -lip,
            1,
        )
    if grid == "large" and mount == "open":
        for i in range(1, len(centers) + 1):
            for axis in ("Yaw", "Pitch"):
                assert f"subpart_{axis}{i:02}" in rows
    assert rows.keys() >= expected.keys(), rows.keys()
    assert {key for key in rows if key.startswith(("thruster_flame", "detector_conveyor"))} == set(expected)
    for key, matrix in expected.items():
        actual = rows[key]
        assert len(actual) == 16 and all(
            math.isclose(a, b, abs_tol=0.0001) for a, b in zip(actual, matrix)
        ), (key, actual)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--family", choices=("shuttle", "main", "thermal", "vacuum", "atmospheric"), help="Build both mounts of one family"
    )
    parser.add_argument("--mount", choices=("open", "hull"), help="Build only the selected mounting style")
    args = parser.parse_args()
    families = (
        ("atmospheric", "large", "AtmosphericLG", ("arcane-atmospheric-lg-open", "arcane-atmospheric-lg-hull")),
        ("shuttle", "small", "DualModeThrusterSG", ("arcane-shuttle-nozzle", "arcane-shuttle-hull")),
        ("main", "large", "DualModeThrusterLG", ("arcane-main-lg-open", "arcane-main-lg-hull")),
        ("vacuum", "large", "VacuumLG", ("arcane-vacuum-lg-open", "arcane-vacuum-lg-hull")),
        ("thermal", "large", "DrivePriorityLG", ("arcane-thermal-lg-open", "arcane-thermal-lg-hull")),
    )
    with TemporaryDirectory(prefix="arcane-engine-build-") as tmp:
        work = Path(tmp)
        builder, probe = prepare_tools(work)
        textures = Path("Textures/Models/ArcaneThrusters")
        shutil.copytree(MOD / "assets" / textures, work / textures)
        assets = list((work / textures).glob("*.dds"))
        for family, grid, subtype, blends in families:
            if args.family and family != args.family:
                continue
            for blend, mount, suffix in zip(blends, ("open", "hull"), ("", "_Hull")):
                if args.mount and mount != args.mount:
                    continue
                subprocess.run(
                    [
                        "blender",
                        "-b",
                        str(MOD / "assets" / (blend + ".blend")),
                        "--python-exit-code",
                        "1",
                        "-P",
                        str(MOD / "assets/export_shuttle_engines.py"),
                        "--",
                        str(work),
                    ],
                    check=True,
                )
                name = "ArcaneThrusters_" + subtype + suffix
                if grid == "large" and mount == "open":
                    count = 3 if family in ("thermal", "vacuum") else 1
                    for bank in range(1, count + 1):
                        for axis in ("Pitch", "Yaw"):
                            assets.extend(compile_models(work, grid, builder, probe, f"{name}_{axis}{bank:02}"))
                assets.extend(
                    compile_models(
                        work,
                        grid,
                        builder,
                        probe,
                        "ArcaneThrusters_" + subtype + suffix,
                        partial(check_engine, family=family, mount=mount),
                    )
                )
        for asset in assets:
            target = MOD / "src" / asset.relative_to(work)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(asset, target)
        print(f"Installed {sum(p.suffix == '.mwm' for p in assets)} validated engine models.")


if __name__ == "__main__":
    main()
