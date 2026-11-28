"""Create a new offline SE1 landing fixture from a disposable local XML save."""
import argparse
import math
from pathlib import Path
from shutil import copy2
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
XSI_NAMESPACE = "http://www.w3.org/2001/XMLSchema-instance"
ET.register_namespace("xsi", XSI_NAMESPACE)
XSI = "{" + XSI_NAMESPACE + "}type"
BASE = 880056000000000


def put(node, key, value):
    child = node.find(key)
    if child is None:
        child = ET.SubElement(node, key)
    child.text = str(value)
    return child


def vector(node, name, xyz):
    ET.SubElement(node, name, dict(zip("xyz", map(str, xyz))))


def grid(objects, number, name, position, tilt=0):
    grid = ET.SubElement(objects, "MyObjectBuilder_EntityBase", {XSI: "MyObjectBuilder_CubeGrid"})
    put(grid, "EntityId", BASE + number)
    put(grid, "PersistentFlags", "CastShadows InScene")
    put(grid, "DisplayName", name)
    pose = ET.SubElement(grid, "PositionAndOrientation")
    vector(pose, "Position", position)
    vector(pose, "Forward", (-math.cos(math.radians(tilt)), -math.sin(math.radians(tilt)), 0))
    vector(pose, "Up", (0, 0, 1))
    put(grid, "GridSizeEnum", "Large")
    put(grid, "DampenersEnabled", "false")
    return grid


def block(blocks, kind, subtype, xyz, number=None):
    block = ET.SubElement(blocks, "MyObjectBuilder_CubeBlock", {XSI: "MyObjectBuilder_" + kind})
    put(block, "SubtypeName", subtype)
    vector(block, "Min", xyz)
    if number is not None:
        put(block, "EntityId", BASE + number)
    return block


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("seed", type=Path, help="XML save with a local player identity")
    parser.add_argument("home_system", type=Path, help="SE Content/CustomWorlds/Home System")
    parser.add_argument("destination", type=Path, help="new scratch save directory")
    parser.add_argument("--assist", choices=["on", "off"], required=True)
    parser.add_argument("--power-mod", default="ArcanePower-Prototype")
    parser.add_argument("--thrusters-mod", default="ArcaneThrusters-RecoveryReview")
    args = parser.parse_args()
    dest = args.destination
    dest.mkdir(parents=True, exist_ok=False)
    for filename in ("Sandbox.sbc", "Sandbox_config.sbc"):
        tree = ET.parse(args.seed / filename)
        root = tree.getroot()
        root.set("xmlns:xsd", "http://www.w3.org/2001/XMLSchema")
        if filename == "Sandbox.sbc":
            owner = root.findtext("Identities/MyObjectBuilder_Identity/IdentityId")
            if not owner:
                raise ValueError("Seed must contain a player identity")
        mods = root.find("Mods")
        mods.clear()
        for name in (args.power_mod, args.thrusters_mod, "ArcaneLanderTest"):
            put(ET.SubElement(mods, "ModItem"), "Name", name)
        for key, value in dict(OnlineMode="OFFLINE", EnableIngameScripts="true", EnableScripterRole="false",
                               AutoSaveInMinutes=0, ThrusterDamage="false", StationVoxelSupport="true").items():
            put(root.find("Settings"), key, value)
        tree.write(dest / filename, encoding="utf-8", xml_declaration=True)

    sector = "SANDBOX_0_0_0_.sbs"
    tree = ET.parse(args.seed / sector)
    objects = tree.find("SectorObjects")
    for obj in list(objects):
        if obj.get(XSI) != "MyObjectBuilder_Character":
            objects.remove(obj)
    planets = ET.parse(args.home_system / sector).find("SectorObjects")
    planet = next(p for p in planets if p.findtext("StorageName", "").startswith("EarthLike"))
    planet.find("PositionAndOrientation/Position").attrib.update(x=str(200000 - 131072), y="-131072", z="-131072")
    objects.append(planet)
    copy2(args.home_system / (planet.findtext("StorageName") + ".vx2"), dest)
    lander = grid(objects, 0, "Lander", (261250, 0, 0), tilt=4)
    blocks = ET.SubElement(lander, "CubeBlocks")
    engine = block(blocks, "Thrust", "ArcaneThrusters_AtmosphericLG", (-1, -1, 0), 1)
    put(engine, "CustomName", "[Lander Assist] Lift")
    tank = block(blocks, "OxygenTank", "LargeHydrogenTank", (-1, -1, 2), 2)
    put(tank, "FilledRatio", 1)
    battery = block(blocks, "BatteryBlock", "LargeBlockBatteryBlock", (0, 0, 5), 3)
    put(battery, "CurrentStoredPower", 2)
    helm = block(blocks, "RemoteControl", "LargeBlockRemoteControl", (-1, 0, 5), 4)
    ET.SubElement(helm, "BlockOrientation", Forward="Up", Up="Backward")
    put(helm, "CustomName", "[Lander Assist] Upright")
    pb = block(blocks, "MyProgrammableBlock", "LargeProgrammableBlock", (1, 0, 5), 5)
    put(pb, "CustomName", "Test assist " + args.assist)
    put(pb, "Program", (HERE.parents[1] / "src/Examples/LanderAssist.cs").read_text())
    for terminal in blocks:
        put(terminal, "Owner", owner)
        put(terminal, "BuiltBy", owner)
    # Two skids extend one cell beyond the bell, parallel to the pad.
    for x in (-2, 2):
        for z in range(-1, 4):
            block(blocks, "CubeBlock", "LargeBlockArmorBlock", (x, 0, z))
    pad = grid(objects, 100, "Landing pad", (261000, 0, 0))
    put(pad, "IsStatic", "true")
    deck = ET.SubElement(pad, "CubeBlocks")
    for x in range(-16, 17):
        for y in range(-3, 4):
            block(deck, "CubeBlock", "LargeBlockArmorBlock", (x, y, 0))
    tree.write(dest / sector, encoding="utf-8", xml_declaration=True)


if __name__ == "__main__":
    main()
