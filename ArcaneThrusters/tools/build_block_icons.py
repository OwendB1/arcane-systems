"""Render every playable block, then compile the icons with Arcane Power's DDS converter."""
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.etree import ElementTree

MOD = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MOD.parent / "ArcanePower/tools"))
from texture_conversion import convert


def main():
    assets = MOD / "assets"
    expected = {block.findtext("Id/SubtypeId")
                for sbc in (MOD / "src/Data/CubeBlocks").glob("*.sbc")
                for block in ElementTree.parse(sbc).findall("CubeBlocks/Definition")}
    with TemporaryDirectory(prefix="arcane-block-icons-") as staging:
        pngs = Path(staging)
        for blend in sorted(assets.glob("arcane-*.blend")):
            subprocess.run(["blender", "-b", str(blend), "--python-exit-code", "1",
                            "-P", str(assets / "render_block_icons.py"), "--", staging], check=True)
        rendered = {p.stem for p in pngs.glob("*.png")}
        if expected != rendered:
            raise ValueError(f"Unexpected icon render set: {expected ^ rendered}")
        convert(pngs / "*.png", MOD / "src/Textures/GUI/Icons/ArcaneThrusters", icon=True)


if __name__ == "__main__":
    main()
