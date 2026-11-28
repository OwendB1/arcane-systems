"""Validate the shared menu contributions against SE's native category merger."""
from pathlib import Path
import os
import subprocess
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
MODS = ('ArcanePower', 'ArcaneShipCores', 'ArcaneThrusters')
paths=[]
ids=[]
for mod in MODS:
    data=ROOT/mod/'src/Data'
    items=[]
    for path in sorted(data.rglob('*.sbc')):
        categories=[c for c in ET.parse(path).findall('CategoryClasses/Category')
                    if c.findtext('Name')=='ArcaneSystems']
        if not categories: continue
        assert len(categories)==1
        category=categories[0]
        paths.append(str(path));ids.append(category.findtext('Id/SubtypeId'))
        assert category.findtext('DisplayName')=='Arcane Systems'
        assert category.findtext('StrictSearch') == 'true', 'Category must suppress expanded block stages'
        items.extend(n.text for n in category.findall('ItemIds/string'))
    assert len(items)==len(set(items))
    blocks = {}
    groups = []
    for file in data.rglob('*.sbc'):
        tree = ET.parse(file)
        for block in tree.findall('CubeBlocks/Definition'):
            subtype = block.findtext('Id/SubtypeId')
            if block.findtext('Public', 'true') != 'false' and subtype != 'Test_Core':
                blocks[block.findtext('Id/TypeId') + '/' + subtype] = block.findtext('BlockPairName')
        for group in tree.findall('BlockVariantGroups/BlockVariantGroup'):
            groups.append([n.get('Type').removeprefix('MyObjectBuilder_') + '/' + n.get('Subtype')
                           for n in group.findall('Blocks/Block')])
    direct = set(items)
    assert direct <= blocks.keys()
    grouped = set()
    for members in groups:
        assert members and set(members) <= blocks.keys()
        assert len(set(members)) == len(members) and not grouped.intersection(members)
        assert direct.intersection(members) == {members[0]}, (mod, members, 'Expected only the group head')
        grouped.update(members)
    # SE combines large and small versions of the same standalone block into one tile.
    standalone = direct - grouped
    assert len(standalone) == len({blocks[item] for item in standalone})
    standalone_pairs = {blocks[key] for key in standalone}
    reachable = grouped | {item for item, pair in blocks.items() if pair in standalone_pairs}
    assert reachable == blocks.keys(), (mod, blocks.keys() - reachable)
    print(f'{mod}: {len(direct)} tiles, {len(groups)} scroll groups, {len(blocks)} reachable blocks', flush=True)
assert len(set(ids))==len(ids), 'Separate contribution IDs must not override each other'
source=r'''
using System; using System.Linq; using System.Collections.Generic; using System.Reflection; using System.Xml.Linq;
using Sandbox.Definitions; using VRage.Game; using System.IO;
class Check {
 static Type type=typeof(MyDefinitionManager).GetNestedType("DefinitionSet",BindingFlags.Public|BindingFlags.NonPublic);
 static FieldInfo classes=type.GetField("m_categoryClasses",BindingFlags.NonPublic|BindingFlags.Instance);
 static FieldInfo categories=type.GetField("m_categories",BindingFlags.NonPublic|BindingFlags.Instance);
 static MyGuiBlockCategoryDefinition Read(string path){
  var node=XDocument.Load(path).Root.Element("CategoryClasses").Element("Category");
  return new MyGuiBlockCategoryDefinition{Name=node.Element("Name").Value,StrictSearch=(bool)node.Element("StrictSearch"),
   ItemIds=new HashSet<string>(node.Element("ItemIds").Elements("string").Select(n=>n.Value))};
 }
 static void Run(params string[] paths){
  var target=Activator.CreateInstance(type);var expected=new HashSet<string>();
  foreach(string path in paths){
   var contribution=Activator.CreateInstance(type);var category=Read(path);
   expected.UnionWith(category.ItemIds);
   ((List<MyGuiBlockCategoryDefinition>)classes.GetValue(contribution)).Add(category);
   type.GetMethod("OverrideBy",new[]{type,typeof(bool)}).Invoke(target,new object[]{contribution,false});
  }
  var menu=(Dictionary<string,MyGuiBlockCategoryDefinition>)categories.GetValue(target);
  if(menu.Count!=1 || !menu["ArcaneSystems"].StrictSearch || !menu["ArcaneSystems"].ItemIds.SetEquals(expected))throw new Exception("Native category merge mismatch");
  foreach(string id in expected)if(!menu["ArcaneSystems"].HasItem("MyObjectBuilder_"+id))throw new Exception("Native filter missed "+id);
  Console.WriteLine("PASS native merger: "+paths.Length+" contributions -> one menu section, "+expected.Count+" matching blocks");
 }
 // Exercise the installed game's pairing, primary selection and per-size scroll lists.
 static void CheckScrollGroups(string data) {
  var docs=Directory.GetFiles(data,"*.sbc",SearchOption.AllDirectories).Select(XDocument.Load).ToArray();
  var pairs=new Dictionary<string,MyCubeBlockDefinitionGroup>();
  var blocks=new Dictionary<string,MyCubeBlockDefinition>();
  foreach(var node in docs.SelectMany(d=>d.Descendants("CubeBlocks").Elements("Definition"))) {
   string id=(string)node.Element("Id").Element("SubtypeId");
   var block=new MyCubeBlockDefinition { Id=new MyDefinitionId(typeof(MyObjectBuilder_CubeBlock),id),
    BlockPairName=(string)node.Element("BlockPairName"), CubeSize=(MyCubeSize)Enum.Parse(typeof(MyCubeSize),(string)node.Element("CubeSize")),
    Public=(bool?)node.Element("Public")??true };
   blocks.Add(id,block);
   if(!pairs.ContainsKey(block.BlockPairName))pairs.Add(block.BlockPairName,(MyCubeBlockDefinitionGroup)Activator.CreateInstance(typeof(MyCubeBlockDefinitionGroup),true));
   pairs[block.BlockPairName][block.CubeSize]=block;
  }
  type.GetField("m_blockGroups",BindingFlags.NonPublic|BindingFlags.Instance).SetValue(MyDefinitionManager.Static.Definitions,pairs);
  foreach(var node in docs.SelectMany(d=>d.Descendants("BlockVariantGroup"))) {
   var members=node.Element("Blocks").Elements("Block").Select(b=>blocks[(string)b.Attribute("Subtype")]).ToArray();
   var primary=members[0];
   var group=new MyBlockVariantGroup { Blocks=members, Icons=new[]{"icon"}, DisplayNameString="Group" };
   group.Postprocess();
   if(group.PrimaryGUIBlock!=primary)throw new Exception("Wrong native group head: "+group.PrimaryGUIBlock.Id);
   foreach(var size in members.GroupBy(b=>b.CubeSize)) {
    var head=size.First();
    var stages=new HashSet<MyDefinitionId>(head.BlockStages);
    stages.Add(head.Id);
    if(!stages.SetEquals(size.Select(b=>b.Id)))throw new Exception("Incomplete scroll list for "+primary.Id+" "+size.Key);
   }
  }
 }
 static void Main(string[] args){
  foreach(string data in args.Select(Path.GetDirectoryName).Distinct())CheckScrollGroups(data);
  foreach(string path in args)Run(path);
  Run(args);Run(args.Reverse().ToArray());Run(args.Concat(args).ToArray());
  foreach(var mod in args.GroupBy(p=>System.IO.Path.GetDirectoryName(p)))Run(mod.ToArray());
 }
}
'''
game=Path.home()/'.local/share/Steam/steamapps/common/SpaceEngineers/Bin64'
with tempfile.TemporaryDirectory(prefix='arcane-category-') as directory:
    cs=Path(directory)/'check.cs';cs.write_text(source);exe=cs.with_suffix('.exe')
    references=['Sandbox.Game','VRage.Game','VRage.Library','VRage.Math','VRage','VRage.Render','VRage.Render11','Sandbox.Common','VRage.EOS']
    args=['mcs','-out:'+str(exe),'-r:System.Xml.Linq','-r:/usr/lib/mono/4.5/Facades/netstandard.dll']
    args+=['-r:'+str(game/(name+'.dll')) for name in references if (game/(name+'.dll')).exists()]
    subprocess.run(args+[str(cs)],check=True)
    subprocess.run(['mono',str(exe)]+paths,env=dict(os.environ,MONO_PATH=str(game)),check=True)
