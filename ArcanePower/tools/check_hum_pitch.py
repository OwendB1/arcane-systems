"""Focused checks for actual hum crossfades and native pitched cue definitions."""
from pathlib import Path
import math
import os
import subprocess
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sound = (ROOT / 'src/Data/Scripts/ArcanePower/Reactor.Sound.cs').read_text()
hum = 'private void MixHum' + sound.split('private void MixHum', 1)[1].split('private void MixLoop', 1)[0]
loop = 'private void MixLoop' + sound.split('private void MixLoop', 1)[1].split('private Vector3D LoopSoundPosition', 1)[0]
source = r'''
using System; using VRageMath;
class State { public float Load; }
class Emitter {
 public float? CustomVolume; public bool IsPlaying; public int Starts;
 public void SetPosition(Vector3D p){}
 public void StopSound(bool force){IsPlaying=false;}
 public void PlaySound(int cue,bool stopPrevious,bool skipIntro){Starts++;IsPlaying=true;}
 public void Update(){}
}
class LoopCheck {
 Emitter[] soundLoops=new Emitter[15]; int[] loopCues=new int[15]; int soundTick=10;
 Vector3D LoopSoundPosition(int i){return Vector3D.Zero;}
''' + loop + r'''
 public static void Run(){
  var c=new LoopCheck();for(int i=0;i<15;i++)c.soundLoops[i]=new Emitter();
  c.MixLoop(7,.5f);c.MixLoop(7,.6f);
  if(c.soundLoops[7].Starts!=1)throw new Exception("gain change restarts voice");
  c.MixLoop(7,0);if(!c.soundLoops[7].IsPlaying)throw new Exception("pitch band must fade, not stop like machinery");
  for(int i=0;i<100;i++)c.MixLoop(7,0);
  if(c.soundLoops[7].IsPlaying)throw new Exception("silent pitch band must release voice");
  c.MixLoop(4,.5f);c.MixLoop(4,0);
  if(c.soundLoops[4].IsPlaying)throw new Exception("mechanical pause must remain immediate");
 }
}
class Check {
 State Motion=new State();float[] gains=new float[15];
 void MixLoop(int index,float target){gains[index]=target;}
''' + hum + r'''
 static void Need(bool ok,string message){if(!ok)throw new Exception(message);}
 static void Near(float a,float b){Need(Math.Abs(a-b)<.0001f,"wrong mix: "+a+" != "+b);}
 static void Main(){
  var c=new Check();
  for(int layer=1;layer<=2;layer++)for(int n=-10;n<=110;n++){
   Array.Clear(c.gains,0,15);c.Motion.Load=n/100f;c.MixHum(layer,.6f);
   float power=0,position=0;int audible=0;
   for(int band=0;band<=4;band++){
    int index=band==0?layer:5+2*band+layer-1;
    float energy=c.gains[index]*c.gains[index];power+=energy;position+=energy*band;
    if(energy>0)audible++;
   }
   Near(power,.36f);Near(position/power,MathHelper.Clamp(c.Motion.Load,0,1)*4);
   Need(audible<=2,"only adjacent pitch bands audible");
   Near(c.gains[0],0);for(int i=3;i<=6;i++)Near(c.gains[i],0);
  }
  c.Motion.Load=.125f;c.MixHum(1,1);Near(c.gains[1],(float)Math.Sqrt(.5));Near(c.gains[7],(float)Math.Sqrt(.5));
  c.Motion.Load=0;c.MixHum(1,1);Near(c.gains[1],1);Near(c.gains[7],0);
  LoopCheck.Run();
  Console.WriteLine("PASS: continuous equal-power adjacent hum blends, clamped load, decreasing demand, layer isolation, voice fades and no gain-change restart");
 }
}
'''
game = Path.home() / '.local/share/Steam/steamapps/common/SpaceEngineers/Bin64'
with tempfile.TemporaryDirectory(prefix='arcane-hum-pitch-') as directory:
    target = Path(directory) / 'check.cs'
    target.write_text(source)
    exe = target.with_suffix('.exe')
    subprocess.run(['mcs', '-out:' + str(exe), '-r:' + str(game / 'VRage.Math.dll'),
                    '-r:' + str(game / 'VRage.Library.dll'),
                    '-r:/usr/lib/mono/4.5/Facades/netstandard.dll', str(target)], check=True)
    subprocess.run(['mono', str(exe)], check=True, env={**os.environ, 'MONO_PATH': str(game)})

cues = {s.findtext('Id/SubtypeId'): s for s in ET.parse(ROOT / 'src/Data/Audio.sbc').findall('Sounds/Sound')}
for name in ('Assembly', 'Resonance', 'Load'):
    for band in range(1 if name == 'Assembly' else 5):
        cue = cues['ArcaneReactor' + name + ('Pitch' + str(band) if band else '')]
        assert math.isclose(2 ** (float(cue.findtext('Pitch')) / 12), .65 + .45 * band / 4, abs_tol=1e-6)
        assert cue.findtext('Loopable') == 'true'
        assert cue.findtext('Waves/Wave/Loop') == 'Audio\\ArcanePower\\' + name + '.wav'
        assert cue.findtext('VolumeCurve') == 'Poly2' and cue.findtext('MaxDistance') == '24'
print('PASS: native semitone pitches, shared WAVs and localized falloff for all hum bands')
