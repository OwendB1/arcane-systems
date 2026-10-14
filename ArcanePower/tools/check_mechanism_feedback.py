"""Focused acceptance checks for actual sound observers and vent lamp methods."""
from pathlib import Path
import os
import re
import subprocess
import tempfile
import wave
import xml.etree.ElementTree as ET
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src/Data/Scripts/ArcanePower'


def method(file, name):
    source = (SRC / file).read_text()
    start = re.search(r'^        (?:private|internal|public) [^{\n]*?\b' + name + r'\(', source, re.M).start()
    opening = source.index('{', start)
    depth, end = 1, opening + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end] + '\n'


motion = (SRC / 'Reactor.Motion.cs').read_text()
state = motion[motion.index('    public enum CorePhase'):motion.index('    public sealed partial class Reactor')]
state = re.sub(r'\[Proto(?:Contract|Member\([^]]+\))\]', '', state)
source = '''using System; using System.Collections.Generic; using VRageMath;
using IMyCubeBlock = Block;
''' + state + (SRC / 'MechanismEvents.cs').read_text() + r'''
static class MyAPIGateway {
 public static class Utilities { public static bool IsDedicated; }
 public static class Session { public static int GameplayFrameCounter; }
}
class Orientation { public Base6Directions.Direction Up=Base6Directions.Direction.Up; }
class Definition { public string SubtypeName; }
class Logic { public Reactor Owner; public T GetAs<T>() where T:class {return Owner as T;} }
class Block {
 public long EntityId;
 public Vector3I Position;
 public Orientation Orientation=new Orientation();
 public Definition BlockDefinition=new Definition();
 public bool IsFunctional=true;
 public Grid CubeGrid;
 public Logic GameLogic=new Logic();
 public Color Lamp,SubpartLamp;
 public void SetEmissiveParts(string n,Color c,float i){Lamp=c;}
 public void SetEmissivePartsForSubparts(string n,Color c,float i){SubpartLamp=c;}
}
class Slim { public Block FatBlock; public float BuildLevelRatio=1; }
class Grid {
 public Dictionary<Vector3I,Slim> Blocks=new Dictionary<Vector3I,Slim>();
 public Slim GetCubeBlock(Vector3I p){Slim s;return Blocks.TryGetValue(p,out s)?s:null;}
}
class Reactor {
 public MotionState Motion=new MotionState();
''' + method('Reactor.VentRoute.cs', 'FindVentOutlet') + r'''
}
class VentHardware {
 public Block Entity;
''' + method('VentHardware.cs', 'ConnectedReactor') + method('VentHardware.cs', 'UpdateAfterSimulation10').replace('public override ', 'public ') + r'''
}
class Emitter {
 public float? CustomVolume;
 public bool IsPlaying;
 public int Starts;
 public void SetPosition(Vector3D p){}
 public void StopSound(bool force){IsPlaying=false;}
 public void PlaySound(int cue,bool stopPrevious,bool skipIntro){IsPlaying=true;Starts++;}
 public void Update(){}
}
class Check {
 Emitter[] soundLoops={new Emitter(),new Emitter(),new Emitter(),new Emitter(),new Emitter(),new Emitter(),new Emitter()};
 int[] loopCues=new int[7]; int soundTick;
 Vector3D LoopSoundPosition(int index){return Vector3D.Zero;}
''' + method('Reactor.Sound.cs', 'MixLoop') + r'''
 static void Need(bool ok,string label){if(!ok)throw new Exception(label);}
 static Slim Add(Grid g,Vector3I p,string subtype,long id=0){
  var b=new Block{Position=p,CubeGrid=g,EntityId=id};b.BlockDefinition.SubtypeName=subtype;
  var slim=new Slim{FatBlock=b};g.Blocks[p]=slim;return slim;
 }
 static void Lamp(Block b,bool green,string label){
  var v=new VentHardware{Entity=b};v.UpdateAfterSimulation10();
  Need(b.Lamp==(green?Color.Green:Color.Red) && b.SubpartLamp==b.Lamp,label);
 }
 static void Main(){
  for(int tier=2;tier<=4;tier++){
   var state=new MotionState();var events=new ArcanePower.MechanismEvents();events.Observe(state,true);
   state.Core=CorePhase.Starting;int releases=0,latches=0;
   for(float age=0;age<=1040;age+=tier*.5f){
    state.CoreTick=(int)age;state.CoreSubtick=age-state.CoreTick;
    int hit=events.Observe(state,true);if((hit&1)!=0)releases++;if((hit&2)!=0)latches++;
    Need(events.Observe(state,true)==0,"stationary duplicate");
   }
   Need(releases==20 && latches==20,"twenty release/latch quartet pairs at tier "+tier);
   state.CoreTick=400;state.CoreSubtick=0;Need(events.Observe(state,true)==0,"snapshot rollback must not repeat");
   state.CoreTick=1039;Need(events.Observe(state,true)==0,"prediction recovery must not repeat");
  }
  var s=new MotionState{Core=CorePhase.Starting,CoreTick=900};var e=new ArcanePower.MechanismEvents();
  Need(e.Observe(s,true)==0 && e.Observe(s,true)==0,"late join has no catch-up burst");
  s.CoreTick=1039;Need(e.Observe(s,false)==0,"out of earshot");Need(e.Observe(s,true)==0,"approach has no replay");
  s=new MotionState();e=new ArcanePower.MechanismEvents();e.Observe(s,true);s.Core=CorePhase.Starting;s.CoreTick=319;e.Observe(s,true);
  s.Paused=true;Need(e.Observe(s,true)==0,"paused tile");s.Paused=false;s.CoreTick=320;Need(e.Observe(s,true)==1,"resume crosses release once");
  s.CoreTick=354;Need(e.Observe(s,true)==2,"latch at authored contact");
  s.Core=CorePhase.Running;
  for(int batch=0;batch<22;batch++){
   s.MaintenanceBatch=batch%20;s.MaintenanceTick=0;Need(e.Observe(s,true)==0,"maintenance shrink is silent");
   s.MaintenanceTick=24;Need(e.Observe(s,true)==1,"replacement exits dispenser");
   s.MaintenanceTick=23;Need(e.Observe(s,true)==0,"maintenance rollback");
   s.MaintenanceTick=24;Need(e.Observe(s,true)==0,"no repeated release");
   s.MaintenanceTick=88;e.Observe(s,true);s.MaintenanceTick=-1;s.MaintenanceBatch=(batch+1)%20;
   Need(e.Observe(s,true)==2 && e.Observe(s,true)==0,"replacement latches once including wrap");
  }
  s.Core=CorePhase.Starting;s.CoreTick=1;Need(ArcanePower.MechanismEvents.DeckMoving(s),"deck opens");
  s.CoreTick=100;Need(!ArcanePower.MechanismEvents.DeckMoving(s),"deck parked");
  s.CoreTick=221;Need(ArcanePower.MechanismEvents.DeckMoving(s),"deck closes");
  s.Core=CorePhase.Stopping;s.StopTick=90;Need(ArcanePower.MechanismEvents.DeckMoving(s),"reverse teardown door");
  s.Paused=true;Need(!ArcanePower.MechanismEvents.DeckMoving(s),"paused deck");
  s.Vent=VentPhase.IntakeOpening;Need(!ArcanePower.MechanismEvents.HatchMoving(s),"paused hatch");
  s.Paused=false;Need(ArcanePower.MechanismEvents.HatchMoving(s),"hatch opening");
  s.Vent=VentPhase.IntakeClosing;Need(ArcanePower.MechanismEvents.HatchMoving(s),"hatch closing");
  s.Vent=VentPhase.Ejecting;Need(!ArcanePower.MechanismEvents.HatchMoving(s) && !ArcanePower.MechanismEvents.DeckMoving(s),"open hatch and frozen deck quiet during launch");
  var audio=new Check();audio.soundTick=1;audio.MixLoop(4,.5f);Need(audio.soundLoops[4].IsPlaying,"motor starts immediately");
  audio.MixLoop(4,0);Need(!audio.soundLoops[4].IsPlaying,"motor stops on pause immediately");
  audio.MixLoop(4,.5f);Need(audio.soundLoops[4].Starts==2,"motor resumes");

  foreach(Base6Directions.Direction axis in Enum.GetValues(typeof(Base6Directions.Direction))){
   var grid=new Grid();var up=Base6Directions.GetIntVector(axis);var r=Add(grid,Vector3I.Zero,"ArcanePower_ReactorPrototype").FatBlock;
   r.Orientation.Up=axis;r.GameLogic.Owner=new Reactor();r.GameLogic.Owner.Motion.VentReady=true;
   grid.Blocks[up]=grid.Blocks[Vector3I.Zero];
   var section=Add(grid,up*2,"ArcanePower_VentDuct").FatBlock;section.Orientation.Up=axis;
   Lamp(section,false,"uncapped reactor tube");
   var outlet=Add(grid,up*3,"ArcanePower_VentOutlet",50).FatBlock;outlet.Orientation.Up=axis;
   Lamp(section,true,"complete tube "+axis);Lamp(outlet,true,"complete hatch "+axis);
   var middle=grid.Blocks[up*2];grid.Blocks.Remove(up*2);Lamp(outlet,false,"gap leaves cap red");grid.Blocks[up*2]=middle;
   grid.Blocks[up*3].BuildLevelRatio=.9f;Lamp(section,false,"unfinished hatch invalidates whole stack");grid.Blocks[up*3].BuildLevelRatio=1;
   section.IsFunctional=false;Lamp(section,false,"damaged section");Lamp(outlet,false,"damaged route");section.IsFunctional=true;
   r.IsFunctional=false;Lamp(section,false,"damaged reactor");r.IsFunctional=true;
   r.GameLogic.Owner.Motion.VentReady=false;Lamp(section,false,"unvalidated snapshot");r.GameLogic.Owner.Motion.VentReady=true;
   r.GameLogic.Owner.Motion.Vent=VentPhase.IntakeOpening;Lamp(section,false,"vent alarm overrides green");r.GameLogic.Owner.Motion.Vent=VentPhase.Idle;
   r.GameLogic.Owner.Motion.Critical=true;Lamp(outlet,false,"critical alarm overrides green");r.GameLogic.Owner.Motion.Critical=false;
   grid.Blocks.Remove(up);grid.Blocks.Remove(Vector3I.Zero);Lamp(section,false,"orphan tube");Lamp(outlet,false,"orphan hatch");
  }
  // Maximum permitted stack, and a piece beyond the terminal cap.
  var g=new Grid();var root=Add(g,Vector3I.Zero,"ArcanePower_ReactorPrototype").FatBlock;g.Blocks[Vector3I.Up]=g.Blocks[Vector3I.Zero];
  root.GameLogic.Owner=new Reactor();root.GameLogic.Owner.Motion.VentReady=true;
  for(int n=2;n<=16;n++)Add(g,Vector3I.Up*n,"ArcanePower_VentDuct");
  var cap=Add(g,Vector3I.Up*17,"ArcanePower_VentOutlet").FatBlock;Lamp(cap,true,"maximum-length cap");
  Lamp(Add(g,Vector3I.Up*18,"ArcanePower_VentDuct").FatBlock,false,"beyond cap is not connected");
  Console.WriteLine("PASS: tier-timed release/latch, maintenance/wrap, no replay, pause/resume, door motors, complete/orphan/broken/rotated/max vent stacks and alarms");
 }
}
'''
game = Path.home()/'.local/share/Steam/steamapps/common/SpaceEngineers/Bin64'
with tempfile.TemporaryDirectory(prefix='arcane-feedback-') as directory:
    target=Path(directory)/'check.cs';target.write_text(source);exe=target.with_suffix('.exe')
    subprocess.run(['mcs','-out:'+str(exe),'-r:'+str(game/'VRage.Math.dll'),'-r:'+str(game/'VRage.Library.dll'),'-r:/usr/lib/mono/4.5/Facades/netstandard.dll',str(target)],check=True)
    subprocess.run(['mono',str(exe)],env=dict(os.environ,MONO_PATH=str(game)),check=True)

# Validate the four new assets and the native disconnected fallback.
sounds=ET.parse(ROOT/'src/Data/Audio.sbc').findall('Sounds/Sound')
for name in ('TileDispense','TileLatch','DeckMotion','HatchMotion'):
    sound=next(s for s in sounds if s.findtext('Id/SubtypeId')=='ArcaneReactor'+name)
    loop=name.endswith('Motion');assert (sound.findtext('Loopable')=='true')==loop
    path=ROOT/'src'/sound.findtext('Waves/Wave/'+('Loop' if loop else 'Start')).replace('\\','/')
    with wave.open(str(path)) as audio:
        assert (audio.getnchannels(),audio.getsampwidth(),audio.getframerate())==(1,2,44100)
        samples=np.frombuffer(audio.readframes(audio.getnframes()),dtype='<i2').astype(float)/32768
    assert abs(samples).max()<.73 and abs(samples.mean())<.002
    assert np.sqrt(np.mean(samples**2))>.02
    if loop:assert abs(samples[-1]-samples[0])<=max(.002,np.quantile(abs(np.diff(samples)),.999))
    else:assert samples[0]==samples[-1]==0
    print(name+': PCM, headroom, DC, seam/fades passed')
for definition in ET.parse(ROOT/'src/Data/CubeBlocks/ArcanePower_Vents.sbc').findall('CubeBlocks/Definition'):
    assert definition.findtext('EmissiveColorPreset')=='ArcaneVentDisconnected'
for state in ET.parse(ROOT/'src/Data/EmissiveColors.sbc').findall('.//EmissiveState'):
    assert state.get('EmissiveColorName')=='Red'
print('PASS: shipped sound definitions/assets and fail-red native vent preset')
