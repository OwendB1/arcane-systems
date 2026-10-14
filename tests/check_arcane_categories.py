"""Validate the shared menu contributions against SE's native category merger."""
from pathlib import Path
import os
import subprocess
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
MODS = ('ArcanePower', 'ArcaneShipCores')
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
        items.extend(n.text for n in category.findall('ItemIds/string'))
    assert len(items)==len(set(items))
    expected=set()
    for file in data.rglob('*.sbc'):
        for block in ET.parse(file).findall('CubeBlocks/Definition'):
            subtype=block.findtext('Id/SubtypeId')
            if block.findtext('Public','true')!='false' and subtype!='Test_Core':
                expected.add(block.findtext('Id/TypeId')+'/'+subtype)
    assert set(items)==expected,(mod,'category must cover all production blocks')
    print(mod+': '+str(len(items))+' production blocks, references and coverage verified',flush=True)
assert len(set(ids))==len(ids), 'Separate contribution IDs must not override each other'
source=r'''
using System; using System.Linq; using System.Collections.Generic; using System.Reflection; using System.Xml.Linq;
using Sandbox.Definitions;
class Check {
 static Type type=typeof(MyDefinitionManager).GetNestedType("DefinitionSet",BindingFlags.Public|BindingFlags.NonPublic);
 static FieldInfo classes=type.GetField("m_categoryClasses",BindingFlags.NonPublic|BindingFlags.Instance);
 static FieldInfo categories=type.GetField("m_categories",BindingFlags.NonPublic|BindingFlags.Instance);
 static MyGuiBlockCategoryDefinition Read(string path){
  var node=XDocument.Load(path).Root.Element("CategoryClasses").Element("Category");
  return new MyGuiBlockCategoryDefinition{Name=node.Element("Name").Value,
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
  if(menu.Count!=1 || !menu["ArcaneSystems"].ItemIds.SetEquals(expected))throw new Exception("Native category merge mismatch");
  foreach(string id in expected)if(!menu["ArcaneSystems"].HasItem("MyObjectBuilder_"+id))throw new Exception("Native filter missed "+id);
  Console.WriteLine("PASS native merger: "+paths.Length+" contributions -> one menu section, "+expected.Count+" matching blocks");
 }
 static void Main(string[] args){
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
