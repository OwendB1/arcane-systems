"""Run the installed AE V2 parser/VM offline with recording subpart libraries.

Uses the workstation's Workshop source and game references without copying them
into the mod. It checks dispatch/timing/cancellation, not game rendering/physics.
"""
import hashlib
import json
import math
import os
import shutil
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
WORK=Path.home()/'.cache/arcane-power/animation-check'
LEGACY=Path.home()/'.local/share/Steam/steamapps/workshop/content/244850/2880317963/Data/Scripts/Math0424/Legacy'
GAME=Path.home()/'.local/share/Steam/steamapps/common/SpaceEngineers/Bin64'
PROBE=r'''
using System; using System.IO; using System.Linq; using System.Collections.Generic;
using System.Reflection; using System.Runtime.Serialization;
using AnimationEngine.Language; using AnimationEngine.Core; using AnimationEngine.Language.Libs;
using VRageRender.Import;
class AEProbe {
 public static int Time;
 public static List<string> Calls=new List<string>();
 class Recorder:ScriptLib {
  string name; public Recorder(string n){name=n;}
  public override SVariable Execute(string method,SVariable[] a){
   if(method=="isworking")return new SVariableBool(true);
   Calls.Add(Time+":"+name+":"+method+(method=="setvisible"?":"+a[0].AsBool():""));return null;
  }
 }
 static void Need(bool condition,string message){if(!condition)throw new Exception(message);}
 static ScriptV2Runner Runtime(ScriptV2Generator compiler,ScriptRunner template){
  var runner=(ScriptV2Runner)template.Clone();
  foreach(var e in compiler.objects){
   string type=e.Type.Value.ToString().ToLower();string name=e.Name.Value.ToString().ToLower();
   if(type=="api")runner.AddLibrary(new ScriptAPI(runner));
   else if(type=="math")runner.AddLibrary(new ScriptMath());
   else runner.AddLibrary(new Recorder(name));
  }
  runner.Execute("func_park");return runner;
 }
 static int Main(string[] args){try{
  var g=(ScriptGenerator)FormatterServices.GetUninitializedObject(typeof(ScriptGenerator));
  typeof(ScriptGenerator).GetProperty("RawScript").SetValue(g,File.ReadAllLines(args[0]));
  typeof(ScriptGenerator).GetProperty("Error").SetValue(g,new ScriptError());
  g.Tokens=new List<Token>();g.headers=new Dictionary<string,string>();
  Lexer.TokenizeScript(g);
  typeof(ScriptGenerator).GetMethod("ParseHeaders",BindingFlags.Instance|BindingFlags.NonPublic).Invoke(g,null);
  ScriptRunner template;List<Subpart> parts;var compiler=new ScriptV2Generator(g,out template,out parts);
  Need(parts.Count==89,"subpart contract");
  var runner=Runtime(compiler,template);Calls.Clear();runner.Execute("func_start");
  for(Time=1;Time<=1800;Time++)runner.Tick(1);
  var visible=Calls.Where(x=>x.Contains(":tile")&&x.EndsWith(":setvisible:True")).ToList();
  Need(visible.Count==80,"80 tile dispatches");
  for(int batch=0;batch<20;batch++)Need(visible.Count(x=>x.StartsWith((320+36*batch)+":"))==4,"quartet timing "+batch);
  Need(Calls.Count(x=>x.EndsWith(":spin"))==8,"two gyroscopic spin periods");
  Need(Calls.Contains("1160:plasma:setvisible:True"),"ignition timing");
  Need(Calls.Count(x=>x.Contains(":floor")&&x.EndsWith(":translate"))==16,"four leaves drop/open/close/seat");
  Need(Calls.Count(x=>x.Contains(":tile")&&x.EndsWith(":rotate"))==80,"physical tile orientations");
  // Interrupt every mechanical/assembly phase, then prove queued work and loops
  // stay cancelled even past the last formerly scheduled operation.
  foreach(int interruption in new[]{10,50,130,260,350,700,1080,1200}){
   Time=0;runner=Runtime(compiler,template);runner.Execute("func_start");
   for(Time=1;Time<=interruption;Time++)runner.Tick(1);
   runner.Execute("func_park");Calls.Clear();
   for(Time=interruption+1;Time<=2200;Time++)runner.Tick(1);
   Need(Calls.Count==0,"stale calls after interruption at "+interruption);
   Time=0;runner.Execute("func_start");Calls.Clear();
   for(Time=1;Time<=1170;Time++)runner.Tick(1);
   Need(Calls.Count(x=>x.Contains(":tile")&&x.EndsWith(":setvisible:True"))==80,"restart at "+interruption);
  }
  Console.WriteLine("PASS installed AE V2 parser+VM: 89 subparts, 20 quartets, ignition at1160, eight interruption/restart phases; "+compiler.program.Count+" bytecode instructions");
  // Read the actual exported binary with the game's importer. Bypass only its
  // virtual filesystem wrapper, which is not initialized in this offline process.
  var importer=new MyModelImporter();
  using(var reader=new BinaryReader(File.OpenRead(args[1])))
   typeof(MyModelImporter).GetMethod("LoadTagData",BindingFlags.Instance|BindingFlags.NonPublic).Invoke(importer,new object[]{reader,new[]{"Dummies"}});
  var dummies=(Dictionary<string,MyModelDummy>)importer.GetTagData()["Dummies"];
  Need(dummies.Keys.Count(x=>x.StartsWith("subpart_"))==89,"89 exported MWM subparts");
  foreach(var entry in dummies.Where(x=>x.Key.StartsWith("subpart_"))){
   var m=entry.Value.Matrix;
   string file=entry.Value.CustomData["file"].ToString();
   Need(File.Exists(Path.Combine(Path.GetDirectoryName(args[1]),file+".mwm")),"missing subpart "+file);
   var values=new[]{m.M11,m.M12,m.M13,m.M21,m.M22,m.M23,m.M31,m.M32,m.M33,m.M41,m.M42,m.M43};
   Console.WriteLine("DUMMY|"+entry.Key.Substring(8)+"|"+file+"|"+string.Join(",",values.Select(x=>x.ToString("R",System.Globalization.CultureInfo.InvariantCulture))));
  }
  return 0;
 }catch(Exception e){Console.Error.WriteLine(e.ToString());return 1;}}
}
'''


def main():
    assert LEGACY.is_dir(), 'Installed Animation Engine Workshop source required'
    WORK.mkdir(parents=True,exist_ok=True)
    (WORK/'Probe.cs').write_text(PROBE)
    (WORK/'AECheck.csproj').write_text(f'''<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup>
<OutputType>Exe</OutputType><TargetFramework>net48</TargetFramework><LangVersion>latest</LangVersion>
<DefineConstants>TRACE</DefineConstants><StartupObject>AEProbe</StartupObject><PlatformTarget>x64</PlatformTarget>
<NoWarn>0649;0414;0169;0618</NoWarn></PropertyGroup><ItemGroup>
<PackageReference Include="Mal.Mdk2.References" Version="2.2.7"/><Compile Include="{LEGACY}/**/*.cs" />
</ItemGroup></Project>''')
    shutil.copy2(ROOT/'ArcanePower.mdk.local.ini',WORK/'AECheck.mdk.local.ini')
    with (WORK/'build.log').open('w') as log:
        subprocess.run(['dotnet','build',str(WORK/'AECheck.csproj'),'-c','Release','--nologo'],stdout=log,stderr=subprocess.STDOUT,check=True)
    script=ROOT/'src/Data/Animation/main.bsl'
    env=dict(os.environ,MONO_PATH=str(GAME))
    model=ROOT/'src/Models/Cubes/large/ArcanePower_ReactorPrototype.mwm'
    result=subprocess.run(['mono',str(WORK/'bin/Release/net48/AECheck.exe'),str(script),str(model)],env=env,capture_output=True,text=True)
    if result.returncode:
        raise RuntimeError(result.stdout+result.stderr)
    lines=result.stdout.splitlines()
    exported={}
    for line in lines:
        if line.startswith('DUMMY|'):
            _,name,file,values=line.split('|')
            exported[name]={'model':file,'matrix':list(map(float,values.split(',')))}
    data=json.loads((ROOT/'assets/deployment.json').read_text())
    expected={r['name']:(0,r['park_z'],0) for r in data['rings']}
    expected.update({p['name']:(0,-1.30,0) for p in data['leaves']})
    expected.update({t['name']:(-t['start'][0],t['start'][2],t['start'][1]) for t in data['tiles']})
    expected['Plasma']=(-data['center'][0],data['center'][2],data['center'][1])
    max_error=max(abs(a-b) for name,pos in expected.items() for a,b in zip(pos,exported[name]['matrix'][9:]))
    assert max_error<.0001, ('Exported dummy coordinate mismatch',max_error)
    def transpose(a):return list(map(list,zip(*a)))
    def multiply(a,b):return [[sum(x*y for x,y in zip(row,column)) for column in zip(*b)] for row in a]
    identity=[[1,0,0],[0,1,0],[0,0,1]]
    main_axes=[[-1,0,0],[0,0,1],[0,1,0]]
    part_axes=[[1,0,0],[0,0,1],[0,-1,0]]
    rotations={r['name']:identity for r in data['rings']}
    rotations['Plasma']=identity
    for i,leaf in enumerate(data['leaves']):
        a=i*math.pi/2;rotations[leaf['name']]=[[math.cos(a),-math.sin(a),0],[math.sin(a),math.cos(a),0],[0,0,1]]
    for tile in data['tiles']:
        normal=data['feeders'][tile['dispenser']]['normal']
        tangent=[normal[1]*math.sqrt(2),-normal[0]*math.sqrt(2),0]
        up=[normal[1]*tangent[2]-normal[2]*tangent[1],normal[2]*tangent[0]-normal[0]*tangent[2],normal[0]*tangent[1]-normal[1]*tangent[0]]
        rotations[tile['name']]=transpose([tangent,up,normal])
    rotation_errors=[]
    for name,rotation in rotations.items():
        # Imported MWM matrices use row vectors. Main and subpart export scenes
        # have different axis conversions; their composite must seat each mesh.
        target=transpose(multiply(multiply(main_axes,rotation),transpose(part_axes)))
        rotation_errors += [abs(a-b) for a,b in zip(sum(target,[]),exported[name]['matrix'][:9])]
    max_rotation_error=max(rotation_errors)
    assert max_rotation_error<.00001,('Exported dummy orientation mismatch',max_rotation_error)
    report={'status':'passed','bsl_sha256':hashlib.sha256(script.read_bytes()).hexdigest(),
            'runtime_source':str(LEGACY),'result':lines[0], 'exported_subparts':len(exported),
            'maximum_dummy_position_error_m':max_error,'mwm_sha256':hashlib.sha256(model.read_bytes()).hexdigest(),
            'maximum_dummy_rotation_element_error':max_rotation_error,
            'dummies':exported,
            'scope':'Actual installed AE parser and VM with recording subpart libraries; not an in-game movement or multiplayer test'}
    (ROOT/'validation/animation-vm.json').write_text(json.dumps(report,indent=2))
    print(lines[0]);print('PASS:89 exported MWM subparts resolve with matching positions/orientations; maximum position error',max_error)


if __name__=='__main__':main()
