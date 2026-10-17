"""Check native moving meshes against evaluated authoring poses, not pose math alone."""
import json
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from prepare_lab import ROOT,MOD,GAME


def check():
    contract=ROOT/'assets/thermal-native-motion-contract.json'
    specs=json.loads(contract.read_text())
    blocks={b.findtext('Id/SubtypeId'):b for b in ET.parse(MOD/'Data/CubeBlocks/ArcanePower_Thermal.sbc').findall('CubeBlocks/Definition')}
    output=ROOT/'.cache/native-thermal-motion.json'
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='arcane-native-motion-') as directory:
        work=Path(directory)
        build=subprocess.run(['dotnet','build',str(ROOT/'ArcanePower.csproj'),'--nologo','-o',str(work)],capture_output=True,text=True)
        if build.returncode:raise RuntimeError(build.stdout+build.stderr)
        exe=work/'MotionProbe.exe'
        subprocess.run(['mcs','-out:'+str(exe),'-r:System.Web.Extensions','-r:/usr/lib/mono/4.5/Facades/netstandard.dll',
                        '-r:'+str(work/'ArcanePower.dll'),*['-r:'+str(GAME/'Bin64'/(n+'.dll')) for n in ('VRage.Render','VRage.Math','VRage.Library')],
                        str(ROOT/'tools/ThermalNativeMotionProbe.cs')],check=True)
        output.unlink(missing_ok=True)
        result=subprocess.run(['mono',str(exe),str(contract),str(output),str(MOD),
                               *[str(MOD/blocks[m['subtype']].findtext('Model')) for m in specs['models']]],
                              env={**os.environ,'MONO_PATH':str(work)+':'+str(GAME/'Bin64')},capture_output=True,text=True)
        if not output.exists():raise RuntimeError(result.stdout+result.stderr)
        report=json.loads(output.read_text())['report']
        report['models']=[{'subtype':m['subtype'],'path':blocks[m['subtype']].findtext('Model'),
                          'sha256':hashlib.sha256((MOD/blocks[m['subtype']].findtext('Model')).read_bytes()).hexdigest()} for m in specs['models']]
        report['contract_sha256']=hashlib.sha256(contract.read_bytes()).hexdigest()
        report['runtime_pose_sha256']=hashlib.sha256(b''.join((MOD/'Data/Scripts/ArcanePower'/name).read_bytes()
            for name in ('ThermalManifolds.cs','ThermalRotors.cs','ThermalModels.cs','ThermalPlant.cs'))).hexdigest()
        (ROOT/'validation/thermal-models/native-motion.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps({k:v for k,v in report.items() if k not in ('native_mesh_sha256','models')},indent=2))
        if result.returncode:raise SystemExit(result.returncode)
    return report


if __name__=='__main__':check()
