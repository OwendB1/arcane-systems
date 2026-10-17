"""Focused acceptance check: shipped stage models and animation cache transitions."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import xml.etree.ElementTree as ET

from prepare_lab import BUILD_BLOCKS, MOD, ROOT, GAME, COLLISIONS, model_source

game = GAME/'Bin64'
folder = MOD/'Models/Cubes/large'
report_path = ROOT/'validation/construction-stages.json'
report = json.loads(report_path.read_text())
models = []
with tempfile.TemporaryDirectory(prefix='arcane-stages-') as tmp:
    probe = Path(tmp)/'Models.exe'
    subprocess.run(['mcs','-out:'+str(probe),'-r:/usr/lib/mono/4.5/Facades/netstandard.dll',
                    *['-r:'+str(game/(name+'.dll')) for name in ('VRage.Render','VRage.Math','VRage.Library')],
                    str(ROOT/'tools/ConstructionModelProbe.cs')],check=True)
    for name, filename in BUILD_BLOCKS.items():
        if name=='ArcanePower_ReactorPrototype':continue  # Archived authoring design.
        definitions = ET.parse(MOD/'Data/CubeBlocks'/filename)
        block = next(n for n in definitions.findall('CubeBlocks/Definition') if n.findtext('Id/SubtypeId')==name)
        stages = block.findall('BuildProgressModels/Model')
        assert [n.get('BuildPercentUpperBound') for n in stages] == ['0.33','0.67','1.00']
        collision = COLLISIONS/('ArcanePower_ContainmentController.hkt' if 'Advanced' in name else name+'.hkt')
        for stage, node in enumerate(stages,1):
            canonical = model_source(name+'_BS'+str(stage))
            delivered = MOD/node.get('File')
            data = delivered.read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            assert data == canonical.read_bytes() and digest[:12] in delivered.stem
            subprocess.run(['mono',str(probe),str(delivered),str(collision),str(model_source(name))],
                           check=True,env={**os.environ,'MONO_PATH':str(game)})
            models.append({'subtype':name,'stage':stage,'file':node.get('File'),'sha256':digest,'bytes':len(data)})

    # Compile the actual refresh method against minimal model doubles.
    source = (MOD/'Data/Scripts/ArcanePower/Reactor.Motion.cs').read_text()
    method = source[source.index('        private void RefreshRestPoses()'):source.index('        private void RestoreMotionState(')]
    update = (MOD/'Data/Scripts/ArcanePower/Reactor.cs').read_text().split('public override void UpdateBeforeSimulation()',1)[1]
    assert update.index('RefreshRestPoses();') < update.index('if (initializationFrames')
    harness = '''using System; using System.Collections.Generic;
class IMyModelDummy { public int Matrix; }
class IMyModel {
 public int Reads; public Dictionary<string,IMyModelDummy> Data=new Dictionary<string,IMyModelDummy>();
 public void GetDummies(Dictionary<string,IMyModelDummy> d) { Reads++;foreach(var p in Data)d[p.Key]=p.Value; }
}
class Block { public IMyModel Model; }
class Check {
 Block reactor=new Block(); IMyModel restModel;
 Dictionary<string,int> restPoses=new Dictionary<string,int>();
 METHOD
 static void Expect(bool value) { if(!value)throw new Exception("Model transition failed"); }
 static void Main() {
  var c=new Check();var build=new IMyModel();var full=new IMyModel();
  full.Data["subpart_Ring1"]=new IMyModelDummy{Matrix=17};
  full.Data["conveyor"]=new IMyModelDummy{Matrix=99};
  c.reactor.Model=build;c.RefreshRestPoses();Expect(c.restPoses.Count==0);
  c.reactor.Model=full;c.RefreshRestPoses();Expect(c.restPoses.Count==1 && c.restPoses["Ring1"]==17);
  c.RefreshRestPoses();Expect(full.Reads==1);
  c.reactor.Model=build;c.RefreshRestPoses();Expect(c.restPoses.Count==0);
  c.reactor.Model=null;c.RefreshRestPoses();Expect(c.restPoses.Count==0);
  c.reactor.Model=full;c.RefreshRestPoses();Expect(c.restPoses["Ring1"]==17 && full.Reads==2);
  Console.WriteLine("PASS construction / completion / grinding / repair rest-pose refresh; unchanged model is cached");
 }
}'''.replace('METHOD',method)
    path = Path(tmp)/'Motion.cs'
    path.write_text(harness)
    exe = path.with_suffix('.exe')
    subprocess.run(['mcs','-out:'+str(exe),str(path)],check=True)
    subprocess.run(['mono',str(exe)],check=True)
report.update(exported=True, models=models, native_model_import_passed=True, model_transitions_passed=True)
report_path.write_text(json.dumps(report,indent=2)+'\n')
print('PASS:',len(models),'shipped hardware stages, four native build progress definitions, runtime model transitions')
