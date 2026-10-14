"""Focused offline check of the actual field gain and emitter fade; requires Mono."""
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sound = (ROOT / "src/Data/Scripts/ArcanePower/Reactor.Sound.cs").read_text()
motion = (ROOT / "src/Data/Scripts/ArcanePower/Reactor.Motion.cs").read_text()
threshold = re.search(r"private const float CooldownHeat = [^;]+;", motion).group()
gain = sound[sound.index("        private static float FieldSoundGain("):
             sound.index("        private void MixHum(")]
mix = sound[sound.index("        private void MixLoop("):
            sound.index("        private Vector3D LoopSoundPosition(")]
source = r'''
using System;
enum CorePhase { Off, Starting, Running, Stopping, Cooling }
static class MathHelper {
    public static float Clamp(float n,float low,float high) { return Math.Max(low,Math.Min(high,n)); }
}
class Emitter {
    public float? CustomVolume;
    public bool IsPlaying;
    public int Starts;
    public void SetPosition(int p) {}
    public void StopSound(bool force) { IsPlaying=false; }
    public void PlaySound(int cue,bool stopPrevious,bool skipIntro) { IsPlaying=true;Starts++; }
    public void Update() {}
}
class Check {
    Emitter[] soundLoops = { new Emitter() };
    int[] loopCues = { 0 };
    int soundTick;
    int LoopSoundPosition(int index) { return 0; }
'''+threshold+gain+mix+r'''
    static void Need(bool ok,string message) { if(!ok)throw new Exception(message); }
    static void Main() {
        Need(FieldSoundGain(CorePhase.Running,0)==1,"cold running field must hum");
        Need(FieldSoundGain(CorePhase.Starting,0)==1,"ignition field must hum");
        Need(FieldSoundGain(CorePhase.Cooling,4)==1,"supercritical field remains audible");
        float previous=1;
        for(int i=100;i>=0;i--) {
            float gain=FieldSoundGain(CorePhase.Cooling,i/100f);
            Need(gain>=0 && gain<=previous,"cooldown must fade monotonically");
            previous=gain;
        }
        Need(FieldSoundGain(CorePhase.Cooling,.5f)>0 && FieldSoundGain(CorePhase.Cooling,.5f)<1,
            "residual field must be quieter during cooldown");
        Need(FieldSoundGain(CorePhase.Cooling,CooldownHeat)==0,"safe heat must silence even while teardown waits");
        Need(FieldSoundGain(CorePhase.Stopping,1)==0,"direct shutdown must silence hum");
        Need(FieldSoundGain(CorePhase.Off,1)==0,"off must silence hum");
        var check=new Check();
        for(int i=0;i<120;i++){check.soundTick++;check.MixLoop(0,.5f);}
        Need(check.soundLoops[0].IsPlaying,"running loop starts");
        float volume=check.soundLoops[0].CustomVolume.Value;
        check.MixLoop(0,FieldSoundGain(CorePhase.Stopping,.1f));
        Need(check.soundLoops[0].CustomVolume<volume,"shutdown immediately starts fading");
        for(int i=0;i<120;i++){check.soundTick++;check.MixLoop(0,0);}
        Need(!check.soundLoops[0].IsPlaying,"fade must actually stop the emitter");
        int starts=check.soundLoops[0].Starts;
        for(int i=0;i<120;i++){check.soundTick++;check.MixLoop(0,0);}
        Need(check.soundLoops[0].Starts==starts,"silent loops must stay stopped");
        Console.WriteLine("PASS: running, monotonic cooldown, safe-heat silence, direct shutdown, emitter stop");
    }
}
'''
with tempfile.TemporaryDirectory(prefix="arcane-sound-check-") as directory:
    path = Path(directory) / "check.cs"
    path.write_text(source)
    exe = path.with_suffix(".exe")
    subprocess.run(["mcs", "-out:" + str(exe), str(path)], check=True)
    subprocess.run(["mono", str(exe)], check=True)
