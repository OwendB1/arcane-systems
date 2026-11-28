"""Validate the SE definitions and build the Arcane Thrusters development package."""

from pathlib import Path
from tempfile import TemporaryDirectory
from xml.etree import ElementTree
from zipfile import ZIP_DEFLATED, ZipFile


def check_tank(block, plasma_id):
    name = block.findtext("Id/SubtypeId")
    if block.findtext("StoredGasId/TypeId") != "GasProperties" or block.findtext("StoredGasId/SubtypeId") != plasma_id:
        raise ValueError(f"{name} must store {plasma_id}")


def check_models(source, block):
    name = block.findtext("Id/SubtypeId")
    stages = block.findall("BuildProgressModels/Model")
    model = source / block.findtext("Model")
    icon = Path("Textures/GUI/Icons/ArcaneThrusters") / (name + ".dds")
    if Path(block.findtext("Icon", "").replace("\\", "/")) != icon:
        raise ValueError(f"{name} must reference its block icon")
    with (source / icon).open("rb") as stream:
        if stream.read(4) != b"DDS ":
            raise ValueError(f"Invalid block icon {icon}")
    if model.stem != name:
        raise ValueError(f"{name} must reference its own model")
    if len(stages) != 3:
        raise ValueError(f"{name} requires three construction stages")
    paths = [model, *(source / stage.attrib["File"] for stage in stages),
             *(model.with_stem(model.stem + suffix) for suffix in ("_LOD1", "_LOD2"))]
    for path in paths:
        # Git LFS pointer text is a valid file but cannot be loaded as a block model.
        with path.open("rb") as stream:
            if stream.read(6) != b"\x05Debug":
                raise ValueError(f"Missing native MWM header in {path}")


def main():
    mod = Path(__file__).resolve().parents[1]
    source = mod / "src"
    metadata = ElementTree.parse(source / "metadata.mod").getroot()
    if metadata.tag != "ModMetadata" or not metadata.findtext("ModVersion"):
        raise ValueError("metadata.mod requires a ModMetadata root and ModVersion")

    plasma_id = "ArcaneThrusters_HydrogenPlasma"
    plasma_count = 0
    chargers = 0
    tanks = []
    engines = []
    for path in sorted((source / "Data").rglob("*.sbc")):
        definitions = ElementTree.parse(path).getroot()
        if definitions.tag != "Definitions":
            raise ValueError(f"{path} requires a Definitions root")
        for block in definitions.findall("CubeBlocks/Definition"):
            if block.findtext("Id/TypeId") == "OxygenTank":
                check_models(source, block)
                if block.findtext("Id/SubtypeId") == "ArcaneThrusters_RecoveryChargerLG":
                    check_tank(block, "Hydrogen")
                    chargers += 1
                    continue
                check_tank(block, plasma_id)
                tanks.append((block.findtext("CubeSize"), block.findtext("Id/SubtypeId")))
            elif block.findtext("Id/TypeId") == "Thrust":
                check_models(source, block)
                size = block.find("Size")
                engines.append((block.findtext("Id/SubtypeId"), block.findtext("CubeSize"),
                                tuple(size.get(k) for k in "xyz"), block.findtext("IsAirTight")))
        for gas in definitions.findall("GasProperties/Gas/Id"):
            if (gas.findtext("TypeId") == "MyObjectBuilder_GasProperties"
                    and gas.findtext("SubtypeId") == plasma_id):
                plasma_count += 1
    if chargers != 1:
        raise ValueError("Expected one hydrogen recovery charger")
    if plasma_count != 1:
        raise ValueError(f"Expected one definition for {plasma_id}, found {plasma_count}")
    if sorted(tanks) != [("Large", "ArcaneThrusters_PlasmaTankLG"), ("Small", "ArcaneThrusters_PlasmaTankSG")]:
        raise ValueError(f"Expected a carrier tank and a shuttle tank, found {tanks}")
    expected = [
        ("ArcaneThrusters_" + family + suffix, grid, ("3", "3", depth), airtight)
        for family, grid, open_depth, hull_depth in (
            ("DualModeThrusterSG", "Small", "5", "5"),
            ("DualModeThrusterLG", "Large", "3", "3"),
            ("AtmosphericLG", "Large", "2", "2"),
            ("VacuumLG", "Large", "3", "4"),
            ("DrivePriorityLG", "Large", "3", "4"),
        )
        for suffix, depth, airtight in (("", open_depth, "false"), ("_Hull", hull_depth, "true"))
    ]
    if sorted(engines) != sorted(expected):
        raise ValueError(f"Unexpected engine subtypes, sizes or airtight flags: {engines}")
    group = ElementTree.parse(source / "Data/CubeBlocks/ThrusterVariants.sbc").find("BlockVariantGroups/BlockVariantGroup")
    members = [b.get("Subtype") for b in group.findall("Blocks/Block") if b.get("Type") == "MyObjectBuilder_Thrust"]
    if sorted(members) != sorted(engine[0] for engine in engines):
        raise ValueError("The thruster scroll group must contain all ten engine mounts exactly once")
    category = ElementTree.parse(source / "Data/BlockCategories.sbc").find("CategoryClasses/Category")
    tiles = {n.text for n in category.findall("ItemIds/string")}
    if category.findtext("StrictSearch") != "true" or tiles != {
        "Thrust/" + members[0], "OxygenTank/ArcaneThrusters_PlasmaTankLG", "OxygenTank/ArcaneThrusters_RecoveryChargerLG"
    }:
        raise ValueError("Expected one thruster group, the plasma tank and the charger in Arcane Systems")
    for group, channels in (("EnergyField", ("cm", "ng", "add")), ("ShuttleBell", ("cm", "ng")), ("ShuttleCasting", ("cm", "ng"))):
        for channel in channels:
            texture = source / f"Textures/Models/ArcaneThrusters/{group}_{channel}.dds"
            with texture.open("rb") as stream:
                if stream.read(4) != b"DDS ":
                    raise ValueError(f"Invalid texture {texture}")

    materials = ElementTree.parse(source / "Data/TransparentMaterials.sbc")
    sprites = {m.findtext("Id/SubtypeId"): m.findtext("Texture")
               for m in materials.findall("TransparentMaterials/TransparentMaterial")}
    for name in ("Envelope", "Cells", "Mouth"):
        expected_path = f"Textures/Particles/ArcaneThrusters/{name}.dds"
        if sprites.get(f"ArcaneThrusters_{name}") != expected_path:
            raise ValueError(f"Missing plume material for {name}")
        with (source / expected_path).open("rb") as stream:
            if stream.read(4) != b"DDS ":
                raise ValueError(f"Invalid plume sprite {name}")

    for family, banks in (("DualModeThrusterLG", 1), ("AtmosphericLG", 1), ("DrivePriorityLG", 3), ("VacuumLG", 3)):
        for bank in range(1, banks + 1):
            for axis in ("Yaw", "Pitch"):
                for level in ("", "_LOD1", "_LOD2"):
                    name = f"ArcaneThrusters_{family}_{axis}{bank:02}{level}.mwm"
                    with (source / "Models/Cubes/large" / name).open("rb") as stream:
                        if stream.read(6) != b"\x05Debug":
                            raise ValueError(f"Invalid steering subpart {name}")

    for name in ("PlasmaTank.cs", "FieldTelemetry.cs", "RecoveryCharger.cs", "EngineFeed.cs",
                 "PlasmaDrive.cs", "ThermalDrive.cs", "NozzleGimbal.cs", "DrivePlume.cs", "PropulsionLcd.cs"):
        if not (source / "Data/Scripts/ArcaneThrusters" / name).is_file():
            raise ValueError(f"Missing propulsion script {name}")

    if not (source / "Examples/LanderAssist.cs").is_file():
        raise ValueError("Missing programmable-block lander assist example")

    output = mod / "artifacts" / "ArcaneThrusters.zip"
    output.parent.mkdir(exist_ok=True)
    with TemporaryDirectory(dir=output.parent) as staging:
        archive = Path(staging) / output.name
        with ZipFile(archive, "w", ZIP_DEFLATED) as package:
            for path in sorted(source.rglob("*")):
                if path.is_file():
                    package.write(path, path.relative_to(source))
        archive.replace(output)
    print(output)


if __name__ == "__main__":
    main()
