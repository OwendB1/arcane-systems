"""Check generated rotor definitions and the production native attachment adapter.

No export, installation or release packaging. Full native/game validation waits
for the next authorized whole-asset export.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

import prepare_thermal_release as release


def main():
    root, contract = release.ROOT, release.CONTRACT
    installed = release.MOD/'Data/CubeBlocks/ArcanePower_Thermal.sbc'
    before = hashlib.sha256(installed.read_bytes()).hexdigest()
    models = {k:v for k,v in json.loads((release.OUT/'models.json').read_text()).items() if k in contract['PLAYABLE']}
    mains = {k:'APT_'+v['subtype'].removeprefix('ArcanePower_Thermal_')+'_M' for k,v in models.items()}
    pending = release.definitions(models, mains, Path('Models/Cubes/large/Thermal/pending_full_export'), write=False)
    definitions = {b.findtext('Id/SubtypeId'):b for b in pending.find('CubeBlocks')}
    for name, native in contract['PIPE_ROTORS'].items():
        block = definitions[contract['subtype'](name)]
        assert block.findtext('Id/TypeId') == native
        assert block.find('Size').attrib == dict(x='1',y='1',z='1')
        assert block.find('ModelOffset').attrib == dict(x='0',y='0',z='0')
        assert block.findtext('IsAirTight') == 'true'
        assert block.findtext('Public') == block.findtext('GuiVisible') == 'true'
        assert len(block.find('BuildProgressModels')) == 3
        assert len(block.find('MountPoints')) == 5
    base = definitions[contract['subtype']('Pipe rotor')]
    head = definitions[contract['subtype']('Pipe rotor head')]
    assert base.findtext('RotorPart') == head.findtext('BlockPairName')
    assert base.find('MediumTopPart') is None
    low, high = contract['PIPE_ROTOR_DISPLACEMENT']
    for suffix in ('', 'Small'):
        assert float(base.findtext('RotorDisplacementMin'+suffix)) == low
        assert float(base.findtext('RotorDisplacementMax'+suffix)) == high
    assert low < 0 < high, 'Native displacement slider must be visible and include its zero default'
    assert float(base.findtext('RotorDisplacementInModel')) == 0
    assert head.find('MechanicalTopInitialPlacementOffset').attrib == dict(x='0',y='0',z='0')
    # MyMotorBase.DummyPosition + MyMotorStator.SetConstraintPosition:
    # head origin = authored electric_motor + slider - in-model displacement.
    # A wheel dummy is not an offset in the native rotor constraint.
    for displacement, expected_gap in ((low,.10),(0,.20),(high,.30)):
        centre = contract['PIPE_ROTOR_HEAD_CENTRE']+displacement
        assert abs(centre-2.5-expected_gap) < 1e-6
        # Preserve overlap with the native large-grid head query box even after
        # the existing 35 mm collider inset. Reattachment still needs a game test.
        assert centre-1.215 < (.35+.29)*2.5
    assert definitions[contract['subtype']('Space radiator')].findtext('Id/TypeId') == 'UpgradeModule'
    assert hashlib.sha256(installed.read_bytes()).hexdigest() == before, 'Source preview changed installed definitions'

    # Compile the actual adapter method against a minimal native-API fixture.
    source = (root/'src/Data/Scripts/ArcanePower/ThermalPipeJoint.cs').read_text()
    start = source.index('internal static long Peer(')
    end = source.index('{', start)+1
    depth = 1
    while depth:
        depth += (source[end] == '{')-(source[end] == '}'); end += 1
    method = source[start:end]
    fixture = r'''
using System;
class Definition { public string SubtypeName; }
interface IMyCubeBlock {
 bool Closed{get;set;} bool MarkedForClose{get;set;} object CubeGrid{get;set;}
 long EntityId{get;set;} Definition BlockDefinition{get;}
}
interface IMyMotorAdvancedStator:IMyCubeBlock {
 bool IsAttached{get;set;} bool PendingAttachment{get;set;} IMyCubeBlock Top{get;set;}
}
interface IMyMotorAdvancedRotor:IMyCubeBlock { IMyCubeBlock Base{get;set;} }
class Block:IMyCubeBlock {
 public bool Closed{get;set;} public bool MarkedForClose{get;set;} public object CubeGrid{get;set;}
 public long EntityId{get;set;} public Definition BlockDefinition{get;private set;} = new Definition();
}
class Stator:Block,IMyMotorAdvancedStator {
 public bool IsAttached{get;set;} public bool PendingAttachment{get;set;} public IMyCubeBlock Top{get;set;}
}
class Head:Block,IMyMotorAdvancedRotor { public IMyCubeBlock Base{get;set;} }
class Checks {
 // METHOD
 static int count;
 static void Need(bool value,string label){count++;if(!value)throw new Exception(label);}
 static void Main(){
  var a=new Stator{EntityId=1,CubeGrid=new object(),IsAttached=true};
  var b=new Head{EntityId=2,CubeGrid=new object(),Base=a};a.Top=b;
  a.BlockDefinition.SubtypeName="ArcanePower_Thermal_PipeRotor";
  b.BlockDefinition.SubtypeName="ArcanePower_Thermal_PipeRotorHead";
  Need(Peer(a)==2 && Peer(b)==1,"reciprocal native attachment");
  a.PendingAttachment=true;Need(Peer(a)==0 && Peer(b)==0,"pending native attachment");a.PendingAttachment=false;
  a.IsAttached=false;Need(Peer(a)==0 && Peer(b)==0,"detached native attachment");a.IsAttached=true;
  foreach(var part in new Block[]{a,b}){
   part.Closed=true;Need(Peer(a)==0 && Peer(b)==0,"closed part");part.Closed=false;
   part.MarkedForClose=true;Need(Peer(a)==0 && Peer(b)==0,"closing part");part.MarkedForClose=false;
   string original=part.BlockDefinition.SubtypeName;part.BlockDefinition.SubtypeName="vanilla";
   Need(Peer(a)==0 && Peer(b)==0,"foreign native part");part.BlockDefinition.SubtypeName=original;
  }
  b.Base=null;Need(Peer(a)==0 && Peer(b)==0,"one-sided native link");b.Base=a;
  var other=new Head{EntityId=3,Base=a};Need(Peer(other)==0,"stale head reference");
  object grid=b.CubeGrid;b.CubeGrid=a.CubeGrid;Need(Peer(a)==0 && Peer(b)==0,"merged grids");b.CubeGrid=grid;
  a.Top=new Block();Need(Peer(a)==0 && Peer(b)==0,"wrong native top type");a.Top=b;
  Need(Peer(new Block())==0,"nonmechanical block");
  Need(Peer(a)==2 && Peer(b)==1,"reattachment after transient failure");
  Console.WriteLine("PASS: "+count+" production attachment checks; definition preview leaves installed definitions unchanged");
 }
}
'''.replace('// METHOD', method)
    with tempfile.TemporaryDirectory(prefix='arcane-pipe-rotor-') as directory:
        path = Path(directory)
        (path/'Check.cs').write_text(fixture)
        subprocess.run(['mcs','-langversion:6','-out:'+str(path/'Check.exe'),str(path/'Check.cs')],check=True)
        subprocess.run(['mono',str(path/'Check.exe')],check=True)


if __name__ == '__main__':
    main()
