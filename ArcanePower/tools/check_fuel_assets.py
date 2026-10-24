"""Focused export acceptance: definitions, DDS mip chains and native MWM loading."""
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from PIL import Image

from prepare_lab import ROOT, MOD, GAME

definitions = ET.parse(MOD/'Data/PhysicalItems.sbc')
items = definitions.findall('PhysicalItems/PhysicalItem') + definitions.findall('Components/Component')
voxels = ET.parse(MOD/'Data/VoxelMaterials_Arcane.sbc').findall('VoxelMaterials/VoxelMaterial')
recipes = ET.parse(MOD/'Data/Blueprints.sbc').findall('Blueprints/Blueprint')
assert len(items) == 11 and len(voxels) == 3 and len(recipes) == 7
textures, models = set(), set()


def local_asset(value):
    path = MOD/value.replace('\\', '/')
    assert path.is_file(), path
    assert not any(s in str(path).lower() for s in ('uran', 'sphere.mwm')), path
    (textures if path.suffix == '.dds' else models).add(path)
    return path


for item in items:
    local_asset(item.findtext('Icon'))
    model = local_asset(item.findtext('Model'))
    if item.findtext('Id/TypeId') == 'Ore':
        assert item.findtext('Models/Model') == item.findtext('Model')
        assert item.findtext('VoxelMaterial') in {v.findtext('Id/SubtypeId') for v in voxels}
    materials = model.with_suffix('.xml')
    if not materials.exists():materials = ROOT/'assets/fuel-materials'/(model.stem+'.xml')
    for param in ET.parse(materials).findall('Material/Parameter'):
        if param.get('Name').endswith('Texture'):
            local_asset(param.text)
for voxel in voxels:
    assert voxel.findtext('MinedOre') in {i.findtext('Id/SubtypeId') for i in items}
    for key in ('VoxelHandPreview', 'ColorMetalXZnY', 'NormalGlossXZnY', 'ExtXZnY',
                'ColorMetalXZnYFar1', 'NormalGlossXZnYFar1', 'ExtXZnYFar1'):
        local_asset(voxel.findtext(key))
for recipe in recipes:
    item = next(i for i in items if i.findtext('Id/SubtypeId') == recipe.find('Result').get('SubtypeId'))
    assert recipe.findtext('Icon') == item.findtext('Icon')

for path in textures:
    data = path.read_bytes()
    assert data[:4] == b'DDS ' and data[84:88] == b'DX10', path
    height, width = struct.unpack_from('<II', data, 12)
    levels, = struct.unpack_from('<I', data, 28)
    dxgi, = struct.unpack_from('<I', data, 128)
    assert dxgi == (98 if path.stem.endswith('_ng') else 99), (path, dxgi)
    assert levels == max(width, height).bit_length(), (path, levels)
    if 'Voxels' in path.parts:
        assert (width, height) == (2048, 2048), (path, 'incompatible native voxel array size')
    expected = 148+sum(max(1, ((width >> m)+3)//4)*max(1, ((height >> m)+3)//4)*16 for m in range(levels))
    assert len(data) == expected, (path, len(data), expected)
    if path.stem.endswith('_add'):
        with Image.open(path) as image:
            assert image.getchannel('A').getextrema()[1] <= 4, (path, 'unwanted paint mask')
            if 'FuelLight' in path.stem:
                assert image.getchannel('G').getextrema()[1] <= 65, (path, 'cartridge glow exceeds authored limit')

# Load the delivered binaries using the game's own importer, not the authoring FBX.
probe = r'''
using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using VRageRender.Import;
using VRageMath;
class FuelModels {
    static void Main(string[] args) {
        foreach (var file in Directory.GetFiles(args[0], "*.mwm")) {
            var importer = new MyModelImporter();
            using (var reader = new BinaryReader(File.OpenRead(file)))
                typeof(MyModelImporter).GetMethod("LoadTagData", BindingFlags.Instance | BindingFlags.NonPublic)
                    .Invoke(importer, new object[] {reader, new[] {"BoundingBox", "ModelInfo", "MeshParts"}});
            var data = importer.GetTagData();
            var info = (MyModelInfo)data["ModelInfo"];
            var size = ((BoundingBox)data["BoundingBox"]).Size;
            if (info.TrianglesCount <= 0 || size.X < .09f || size.X > .5f || size.Y < .06f || size.Y > .5f || size.Z < .06f || size.Z > .5f)
                throw new Exception("Invalid item geometry: "+file+" "+size);
            if ((Path.GetFileName(file).StartsWith("ArcaneFuel") || Path.GetFileName(file)=="ArcaneAetherCanister.mwm") &&
                Vector3.Distance(size, new Vector3(.261f, .438f, .261f)) > .0001f)
                throw new Exception("Cartridge must be 1.5x the original size: "+file+" "+size);
            var parts = (List<MyMeshPartInfo>)data["MeshParts"];
            if (parts.Count == 0) throw new Exception("No mesh materials: "+file);
            foreach (var part in parts) {
                if (!part.GetMaterialName().StartsWith("Arcane")) throw new Exception("Placeholder material "+part.GetMaterialName()+": "+file);
                if (Path.GetFileName(file)=="ArcaneAetherCanister.mwm" &&
                    part.GetMaterialName()!="ArcaneFuelSteel" && part.GetMaterialName()!="ArcaneFuelCeramic")
                    throw new Exception("Empty canister contains powered fuel material: "+part.GetMaterialName());
                foreach (var channel in new[] {"ColorMetalTexture", "NormalGlossTexture", "AddMapsTexture"}) {
                    string path;
                    if (!part.m_MaterialDesc.Textures.TryGetValue(channel, out path) ||
                        !File.Exists(Path.Combine(args[1], path.Replace('\\', '/'))))
                        throw new Exception("Missing compiled texture "+channel+": "+file);
                }
            }
            Console.WriteLine(Path.GetFileName(file)+": "+info.TrianglesCount+" triangles, "+size);
        }
    }
}'''
with tempfile.TemporaryDirectory(prefix='arcane-fuel-assets-') as tmp:
    source = Path(tmp)/'FuelModels.cs'
    source.write_text(probe)
    exe = source.with_suffix('.exe')
    game = GAME/'Bin64'
    subprocess.run(['mcs', '-out:'+str(exe), '-r:/usr/lib/mono/4.5/Facades/netstandard.dll',
                    *['-r:'+str(game/(name+'.dll')) for name in ('VRage.Render', 'VRage.Math', 'VRage.Library')],
                    str(source)], check=True)
    native = subprocess.run(['mono', str(exe), str(MOD/'Models/Items/ArcanePower'), str(MOD)],
                            text=True, stdout=subprocess.PIPE, env={**os.environ, 'MONO_PATH': str(game)})
    print(native.stdout, end='')
    native.check_returncode()
report = {'items': len(items), 'voxel_materials': len(voxels), 'recipes': len(recipes),
          'dds_textures': len(textures), 'native_model_import': native.stdout.splitlines(),
          'models': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(models)},
          'in_game_validated': False}
(ROOT/'validation/fuel-assets.json').write_text(json.dumps(report, indent=2)+'\n')
print('PASS: eleven custom models/icons, seven recipe icons, three near/far voxel materials, complete BC7 mip chains.')
