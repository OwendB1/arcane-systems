"""Focused checks for core growth, the static dark material and localized sound definitions."""
from pathlib import Path
import os
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src/Data/Scripts/ArcanePower'


def method(file, name):
    source = (SRC / file).read_text()
    start = re.search(r'^        (?:private|internal) [^{\n]*?\b' + name + r'\(', source, re.M).start()
    opening = source.index('{', start)
    depth, end = 1, opening + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end] + '\n'


motion = (SRC / 'Reactor.Motion.cs').read_text()
state = motion[motion.index('    public enum CorePhase'):motion.index('    public sealed partial class Reactor')]
state = re.sub(r'\[Proto(?:Contract|Member\([^]]+\))\]', '', state)
constant = re.search(r'private const int PlasmaStartTick = \d+;', motion).group()
source = 'using System; using VRageMath;\n' + state + '\nclass Check {\n' + constant + r'''
 MotionState Motion=new MotionState();
 Matrix Rest(string name){var m=Matrix.CreateRotationZ(.3f);m.Translation=new Vector3(0,2,0);return m;}
 Vector3 ContainmentOffset(float age){return new Vector3(.01f,.02f,.03f);}
 Vector3 EjectionOffset(){return Vector3.Up*5;}
''' + ''.join(method(file, name) for file, name in (
    ('Reactor.Motion.cs', 'PlasmaScale'), ('Reactor.Motion.cs', 'PayloadPlasmaPose'),
    ('Reactor.Motion.cs', 'Span'), ('Reactor.Motion.cs', 'Ease'))) + r'''
 static void Need(bool ok,string message){if(!ok)throw new Exception(message);}
 static void Near(float a,float b,string message){Need(Math.Abs(a-b)<.0001f,message);}
 static void Main(){
  var c=new Check();c.Motion.Core=CorePhase.Starting;
  Near(c.PlasmaScale(1038),0,"no ball until final quartet latches");
  Near(c.PlasmaScale(1104),.5f,"half grown at 1.1 seconds");
  Near(c.PlasmaScale(1170),1,"full size at 2.2 seconds");
  for(int age=1039;age<=1170;age++)Need(c.PlasmaScale(age)>c.PlasmaScale(age-1),"smooth monotonic growth");
  var pose=c.PayloadPlasmaPose(1104);
  Near(pose.Right.Length(),.5f,"actual pose carries growth scale");
  Need(Vector3.Distance(Vector3.Normalize(pose.Right),c.Rest("Plasma").Right)<.0001f,"core preserves its independent rest orientation");
  Need(Vector3.Distance(pose.Translation,c.Rest("Plasma").Translation+c.ContainmentOffset(1104)+c.EjectionOffset())<.0001f,"bobbing and ejection preserved");
  c.Motion.Core=CorePhase.Cooling;Near(c.PlasmaScale(5000),1,"cooldown retains ball until dismantling");
  c.Motion.Core=CorePhase.Stopping;c.Motion.StopSpinAge=5000;
  for(int tick=0;tick<=90;tick++){
   c.Motion.StopTick=tick;Near(c.PlasmaScale(1170),1-Span(tick,0,90),"shutdown shrink follows braking");
  }
  Near(c.PlasmaScale(1170),0,"ball hidden completely at end of braking");
  c.Motion.StopSpinAge=1104;Near(c.PlasmaScale(1104),.5f,"interrupted startup does not pop to full size or vanish");
  Near(c.PlasmaScale(1038),0,"partial growth reverses to zero");
  c.Motion.Core=CorePhase.Running;c.Motion.PayloadReleased=true;Near(c.PlasmaScale(5000),0,"released carrier hides original ball");
  c.Motion.PayloadReleased=false;c.Motion.Core=CorePhase.Off;Near(c.PlasmaScale(1170),0,"off is invisible even with stale age");
  Console.WriteLine("PASS: growth/shrink, partial startup, cooldown, orientation, bob and ejection");
 }
}
'''
game = Path.home() / '.local/share/Steam/steamapps/common/SpaceEngineers/Bin64'
with tempfile.TemporaryDirectory(prefix='arcane-core-feedback-') as directory:
    target = Path(directory) / 'check.cs'
    target.write_text(source)
    exe = target.with_suffix('.exe')
    subprocess.run(['mcs', '-out:' + str(exe), '-r:' + str(game / 'VRage.Math.dll'),
                    '-r:' + str(game / 'VRage.Library.dll'),
                    '-r:/usr/lib/mono/4.5/Facades/netstandard.dll', str(target)], check=True)
    subprocess.run(['mono', str(exe)], check=True, env={**os.environ, 'MONO_PATH': str(game)})

material = ET.parse(ROOT/'src/Models/Cubes/large/ArcanePower_Plasma.xml')
for channel, parameter in (('cm', 'ColorMetalTexture'), ('ng', 'NormalGlossTexture'), ('add', 'AddMapsTexture')):
    texture = material.find("Material/Parameter[@Name='"+parameter+"']").text
    with Image.open(ROOT/'src'/texture.replace('\\', '/')) as image:
        assert image.getchannel('A').getextrema()[0] >= 250, 'original dark plasma packing changed'
    canonical = ROOT/'src/Textures/Models/ArcanePower'/('ArcanePlasma_'+channel+'.dds')
    assert (ROOT/'src'/texture.replace('\\', '/')).read_bytes() == canonical.read_bytes()
print('PASS: revised material binds the original dark static DDS maps')

mechanisms = {'DeckMotion', 'HatchMotion', 'TileDispense', 'TileLatch', 'TileRetract'}
for sound in ET.parse(ROOT / 'src/Data/Audio.sbc').findall('Sounds/Sound'):
    name = sound.findtext('Id/SubtypeId').removeprefix('ArcaneReactor')
    distance = 1500 if name == 'Explosion' else 60 if name == 'Vent' else 18 if name in mechanisms else 24
    assert float(sound.findtext('MaxDistance')) == distance, name
    if name != 'Explosion':
        assert sound.findtext('VolumeCurve') == 'Poly2', name
print('PASS: interior range 18/24m with steep native Poly2 falloff, vent 60m, explosion 1500m')
