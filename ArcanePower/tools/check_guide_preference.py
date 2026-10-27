"""Exercise the production chat handler and persisted client preference with I/O doubles."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / 'src/Data/Scripts/ArcanePower/ThermalBuildGuide.cs').read_text()
preferences = source[source.index('        private const string GuideCommand'):source.index('        public override void LoadData()')]
fixture = r'''
using System;
using System.IO;
static class MyAPIGateway { public static Utilities Utilities = new Utilities(); }
class Utilities {
 public string Saved, Message; public bool FailRead, FailWrite;
 public bool FileExistsInLocalStorage(string file, Type type) { return Saved != null; }
 public TextReader ReadFileInLocalStorage(string file, Type type) {
  if (FailRead) throw new IOException("read failed"); return new StringReader(Saved);
 }
 class Writer : StringWriter {
  Utilities owner; public Writer(Utilities owner) { this.owner = owner; }
  protected override void Dispose(bool disposing) { owner.Saved = ToString(); base.Dispose(disposing); }
 }
 public TextWriter WriteFileInLocalStorage(string file, Type type) {
  if (FailWrite) throw new IOException("write failed"); return new Writer(this);
 }
 public void ShowMessage(string author, string message) { Message = message; }
}
class ThermalBuildGuide {
 bool active = true; int hides, errors;
 void Hide() { active = false; hides++; }
 void Log(Exception error) { errors++; }
 PRODUCTION
 static void Need(bool value, string message) { if (!value) throw new Exception(message); }
 static void Main() {
  var u = MyAPIGateway.Utilities; var guide = new ThermalBuildGuide(); guide.LoadPreference();
  Need(guide.guideEnabled, "new clients default to visible");
  bool send = true; guide.GuideChat("hello", ref send);
  Need(send && guide.guideEnabled && u.Saved == null, "ordinary chat is untouched");
  guide.GuideChat("/ap guides", ref send);
  Need(send && guide.guideEnabled, "similar commands are untouched");
  guide.GuideChat("  /AP GUIDE  ", ref send);
  Need(!send && !guide.guideEnabled && !guide.active && guide.hides == 1, "command hides immediately and stays local");
  Need(u.Saved == "False" && u.Message.Contains("/ap guide"), "off saved and recovery command shown");
  guide = new ThermalBuildGuide(); guide.LoadPreference();
  Need(!guide.guideEnabled, "off survives a new session");
  send = true; guide.GuideChat("/ap guide", ref send);
  Need(!send && guide.guideEnabled && u.Saved == "True", "same command restores and saves");
  guide = new ThermalBuildGuide(); guide.LoadPreference();
  Need(guide.guideEnabled, "on survives a new session");
  u.Saved = "corrupt"; guide = new ThermalBuildGuide(); guide.LoadPreference();
  Need(guide.guideEnabled, "malformed preference defaults to visible");
  u.FailRead = true; guide.LoadPreference();
  Need(guide.guideEnabled && guide.errors == 1, "read failure keeps guide recoverable");
  u.FailWrite = true; send = true; guide.GuideChat("/ap guide", ref send);
  Need(!guide.guideEnabled && !send && u.Message.Contains("only this session"), "failed save does not claim persistence");
  Console.WriteLine("PASS: toggle, local chat, saved on/off across sessions, corrupt preference and I/O failures");
 }
}
'''.replace(' PRODUCTION', preferences)
with tempfile.TemporaryDirectory(prefix='arcane-guide-preference-') as folder:
    path = Path(folder) / 'check.cs'
    path.write_text(fixture)
    exe = path.with_suffix('.exe')
    subprocess.run(['mcs', '-warn:0', '-out:' + str(exe), str(path)], check=True)
    subprocess.run(['mono', str(exe)], check=True)
