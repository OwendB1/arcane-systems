"""Exercise production radiator motion with recording physics doubles.

Requires a built ArcanePower.dll, native math and Mono; no live Havok simulation.
"""
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
GAME = Path.home() / '.local/share/Steam/steamapps/common/SpaceEngineers/Bin64'
OUTPUT = ROOT / 'bin/Debug/net48'
source = (ROOT / 'src/Data/Scripts/ArcanePower/ThermalBlock.Radiator.cs').read_text()
start = source.index('internal void AdvanceRadiator(')
end = source.index('{', start) + 1
depth = 1
while depth:
    depth += (source[end] == '{') - (source[end] == '}')
    end += 1

fixture = r'''
using System;
using System.Collections.Generic;
using ArcanePower;
using VRageMath;
class Body {
 public bool Enabled=true;
 public Vector3 LinearVelocity=new Vector3(7,8,9),AngularVelocity=new Vector3(1,2,3);
}
class Position {
 public Matrix Pose=Matrix.Identity;
 public void SetLocalMatrix(ref Matrix pose){Pose=pose;}
}
class MyEntity {
 public long EntityId=1;
 public MatrixD WorldMatrix=MatrixD.Identity;
 public Body Physics;
 public Dictionary<string,MyEntitySubpart> Subparts=new Dictionary<string,MyEntitySubpart>();
}
class MyEntitySubpart:MyEntity {public Position PositionComp=new Position();}
class Grid {public Body Physics=new Body();}
class BlockFixture:MyEntity {public Grid CubeGrid=new Grid();}
class StoreFixture {public ThermalRadiatorState Radiator=new ThermalRadiatorState();}
static class MyAPIGateway {
 public static class Multiplayer {public static bool IsServer;}
 public static class Utilities {public static bool IsDedicated;}
}
static class MyVisualScriptLogicProvider {public static Vector3D GetSunDirection(){return Vector3D.Forward;}}
static class ThermalSession {public static ThermalBlock RadiatorParent(long id){return null;}}
class ThermalBlock {
 BlockFixture Block=new BlockFixture();MyEntity Entity{get{return Block;}}
 StoreFixture Store=new StoreFixture();ThermalModel Spec;
 bool IsRadiator=true,Healthy=true,receivedRadiator=true;
 double radiatorVisualAngle,CoolingRejectedMW=100,coolingMW=1000,PanelCoolingMW=1000;
 ThermalBlock RadiatorBase;List<ThermalBlock> RadiatorPanels=new List<ThermalBlock>();
 int glowUpdates;
 void RadiatorGlow(MyEntity surface,double glow){glowUpdates++;}
 // METHOD
 static int checks;
 static void Need(bool ok,string message){checks++;if(!ok)throw new Exception(message);}
 static void Main(){
  foreach(bool server in new[]{false,true})foreach(bool dedicated in new[]{false,true})
   foreach(string subtype in new[]{"SpaceRadiator","SpaceRadiatorUpgraded","RadiatorPanel","RadiatorPanelUpgraded"})
    foreach(bool existingBody in new[]{false,true}){
     MyAPIGateway.Multiplayer.IsServer=server;MyAPIGateway.Utilities.IsDedicated=dedicated;
     var r=new ThermalBlock{Spec=ThermalModels.All["ArcanePower_Thermal_"+subtype]};
     r.Store.Radiator.Angle=.5;
     if(r.Spec.Kind==ThermalKind.RadiatorPanel){r.RadiatorBase=new ThermalBlock();r.RadiatorBase.Store.Radiator.Angle=.8;}
     var part=new MyEntitySubpart{Physics=existingBody?new Body():null};
     r.Entity.Subparts[ThermalRadiators.Subpart]=part;
     var gridBody=r.Block.CubeGrid.Physics;var linear=gridBody.LinearVelocity;var angular=gridBody.AngularVelocity;
     r.AdvanceRadiator();r.AdvanceRadiator();
     Need(existingBody ? !part.Physics.Enabled : part.Physics==null,"animated subpart never has an active independent collision body");
     Need(gridBody.Enabled && gridBody.LinearVelocity==linear && gridBody.AngularVelocity==angular,"native ship collision and motion are untouched");
     Need(part.PositionComp.Pose!=Matrix.Identity,"radiator still tracks using the production pose");
     Need(r.glowUpdates==(dedicated?0:2),"client glow and dedicated-server rendering rules are preserved");
     // A recreated native subpart must not reintroduce pushing physics.
     part=new MyEntitySubpart{Physics=new Body()};r.Entity.Subparts[ThermalRadiators.Subpart]=part;
     r.AdvanceRadiator();Need(!part.Physics.Enabled,"replacement subpart body is disabled too");
     r.Block.CubeGrid.Physics=null;r.AdvanceRadiator();Need(!part.Physics.Enabled,"physics-less preview never enables subpart collision");
    }
  Console.WriteLine("PASS: "+checks+" radiator motion and collision-ownership checks across base/panels, both tiers, clients and dedicated servers");
 }
}
'''.replace('// METHOD', source[start:end])

with tempfile.TemporaryDirectory(prefix='arcane-radiator-physics-') as directory:
    path = Path(directory) / 'check.cs'
    path.write_text(fixture)
    exe = path.with_suffix('.exe')
    subprocess.run(['mcs', '-langversion:6', '-out:' + str(exe),
                    '-r:/usr/lib/mono/4.5/Facades/netstandard.dll', '-r:' + str(OUTPUT / 'ArcanePower.dll'),
                    *['-r:' + str(GAME / (name + '.dll')) for name in ('VRage.Math', 'VRage.Library')],
                    str(path)], check=True)
    subprocess.run(['mono', str(exe)], check=True,
                   env={**os.environ, 'MONO_PATH': str(OUTPUT) + ':' + str(GAME)})
