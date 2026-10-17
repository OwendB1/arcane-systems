"""Compile, inspect and install the complete native thermal family.

Exports come from assets/export_thermal_models.py. Player assets are installed
only after every requested main, subpart, construction mesh and LOD passes import.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from prepare_lab import ROOT, MOD, GAME, XSI, REACTOR_TEMPLATE, save, set_text
from package_release import resolve

STAGING=MOD/'Models/Cubes/large/.thermal-stage'
OUT=ROOT/'validation/thermal-models'
SETUP=Path.home()/'.local/share/blender-se1-setup'
ENV={**os.environ,'WINEDEBUG':'-all','WINEPREFIX':str(SETUP/'wineprefix')}
NATIVE_ENV={**os.environ,'MONO_PATH':str(GAME/'Bin64')}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest():
    rows=json.loads((STAGING/'sources.json').read_text())
    models=json.loads((OUT/'models.json').read_text())
    assert {r['block'] for r in rows.values()}==set(models),'Incomplete source export'
    scenes=json.loads((OUT/'native-source-scenes.json').read_text())
    mains={name:next(stem for stem,r in rows.items() if r['type']=='main' and r['scene']==scenes[name]['scenes'][-1])
           for name in models}
    for name,stem in mains.items():
        total=sum(r.get('authored_triangles',r['triangles']) for r in rows.values() if r['block']==name and r['type']=='main')
        assert total==models[name]['triangles'],(name,'Sources differ from latest authored main',total,models[name]['triangles'])
        for i in (1,2,3):assert stem+'_BS'+str(i) in rows,(name,'Missing weld stage',i)
        lod_count=sum(r['type']=='lod' and r['reference']==stem for r in rows.values())
        assert lod_count==2 or (lod_count==0 and rows[stem]['triangles']<1000),(name,'Missing main LODs')
    return rows,models,mains


def compile_all():
    rows,_,_=manifest()
    cache=Path.home()/'.cache/arcane-power/thermal/MWMBuilder'
    shutil.copytree(SETUP/'assets/Tools/MWMBuilder',cache,dirs_exist_ok=True)
    (cache/'MwmBuilder.exe.config').write_text('<configuration><system.diagnostics><trace><listeners><clear /></listeners></trace></system.diagnostics></configuration>')
    win=lambda p:'Z:'+str(p).replace('/',chr(92))
    log=OUT/'native-build.log'
    log.write_text('')
    for pattern in ('APT_*_LOD?.fbx','APT_*_M_BS?.fbx','APT_*_M.fbx'):
        print('Compiling',pattern,flush=True)
        with log.open('a') as output:
            subprocess.run(['wine',str(cache/'MwmBuilder.exe'),'/f','/s:'+win(STAGING),'/m:'+pattern,
                            '/o:'+win(STAGING),'/x:'+win(SETUP/'assets/Materials')],
                           cwd=cache,env=ENV,check=True,stdout=output,stderr=subprocess.STDOUT)
    for stem in rows:
        path=STAGING/(stem+'.mwm')
        assert path.is_file() and path.stat().st_mtime>=(STAGING/(stem+'.fbx')).stat().st_mtime,('Missing/stale MWM',stem)


def probe_exe():
    exe=STAGING/'EnergyModelProbe.exe'
    subprocess.run(['mcs','-out:'+str(exe),'-r:/usr/lib/mono/4.5/Facades/netstandard.dll',
                    *['-r:'+str(GAME/'Bin64'/(n+'.dll')) for n in ('VRage.Render','VRage.Math','VRage.Library')],
                    str(ROOT/'tools/EnergyModelProbe.cs')],check=True)
    return exe


def probe(exe,path,count,collision=None):
    args=['mono',str(exe),str(path),str(count)]
    if collision:args.append(str(collision))
    data=subprocess.check_output(args,env=NATIVE_ENV,text=True)
    return [line.split('\t') for line in data.splitlines()]


def dummies(exe,path):
    output=subprocess.check_output(['mono',str(exe),'--dummies',str(path)],env=NATIVE_ENV,text=True)
    return {parts[0]:(list(map(float,parts[1].split(','))),parts[2])
            for line in output.splitlines() if (parts:=line.split('\t'))}


def definitions(models,mains,revision):
    reactor=ET.parse(REACTOR_TEMPLATE).find('CubeBlocks/Definition')
    module=ET.parse(MOD/'Data/CubeBlocks/ArcanePower_ContainmentController.sbc').find('CubeBlocks/Definition')
    root=ET.Element('Definitions');blocks=ET.SubElement(root,'CubeBlocks')
    category=ET.Element('Definitions');classes=ET.SubElement(category,'CategoryClasses')
    group=ET.SubElement(classes,'Category',{f'{{{XSI}}}type':'MyObjectBuilder_GuiBlockCategoryDefinition'})
    set_text(group,'Id/TypeId','GuiBlockCategoryDefinition')
    set_text(group,'Id/SubtypeId','ArcaneSystems_Thermal')
    set_text(group,'DisplayName','Arcane Systems');set_text(group,'Name','ArcaneSystems')
    ids=ET.SubElement(group,'ItemIds')
    for name,spec in models.items():
        ident=spec['subtype'];is_source=name=='Reactor housing';is_train=name.startswith('Brayton train')
        definition=copy.deepcopy(reactor if is_source or is_train else module)
        blocks.append(definition)
        typeid='Reactor' if is_source or is_train else 'UpgradeModule'
        set_text(definition,'Id/TypeId',typeid);set_text(definition,'Id/SubtypeId',ident)
        set_text(definition,'DisplayName','Arcane '+('Reactor' if is_source else name.replace(' / ',' ').replace('CO2','CO₂')))
        set_text(definition,'Icon','Textures/GUI/Icons/ArcanePower/Thermal/'+ident+'.dds')
        set_text(definition,'BlockPairName',ident)
        set_text(definition,'Model',(revision/(mains[name]+'.mwm')).as_posix())
        set_text(definition,'Public','true');set_text(definition,'AvailableInSurvival','true')
        size=definition.find('Size');size.attrib.clear();size.attrib.update(zip(('x','y','z'),map(str,spec['cells_se'])))
        if is_source:
            desc='Integrated CO2 generation and powered loop pressurization. Standalone: 20% net. Brayton: 40% starter, up to 78% with source tier, recovery and cooling. Two containment controllers and a working vent route required. Select the thermal mode in the reactor controls; stop and cool before changing modes.'
        elif is_train:
            desc='Closed-loop sCO2 turbine/compressor train. The reactor generates its working fluid internally. Connect typed HP and LP sockets through recuperation and cooling, preserve H/C roll, and supply startup electricity to the primary heater. No gas generator or tank required.'
            set_text(definition,'MaxPowerOutput',1950000 if name.endswith('upgraded') else 19500)
            set_text(definition,'PCU',80)
        else:
            desc='Closed-loop thermal '+name+'. Match typed socket faces and H/C roll on one physical large grid. Use the placement guide and cap unused sockets. The reactor supplies its own CO2; ordinary conveyors do not replace thermal pipes.'
            if definition.find('Upgrades') is not None:definition.find('Upgrades').clear()
            set_text(definition,'PCU',2 if ' / ' in name else 30)
            set_text(definition,'PrimarySound','')
        set_text(definition,'Description',desc)
        if not is_source:
            components=definition.find('Components');components.clear()
            volume=__import__('math').prod(spec['cells_se'])
            recipe=[('SteelPlate',max(6,volume*2)),('Construction',max(4,volume)),('LargeTube',max(2,volume//2)),
                    ('Motor',2 if ' / ' in name else 12),('Computer',2 if ' / ' in name else 15),('SteelPlate',4)]
            for component,count in recipe:ET.SubElement(components,'Component',Subtype=component,Count=str(count))
            critical=definition.find('CriticalComponent');critical.set('Subtype','Computer');critical.set('Index','0')
            set_text(definition,'BuildTimeSeconds',8 if ' / ' in name else 40)
            mounts=definition.find('MountPoints')
            if mounts is not None:definition.remove(mounts)
            # Native default full-face mounting permits arbitrary grid orientation;
            # thermal socket compatibility remains the authoritative flow gate.
        stages=definition.find('BuildProgressModels')
        if stages is None:stages=ET.SubElement(definition,'BuildProgressModels')
        stages.clear()
        for i,percent in ((1,'.33'),(2,'.67'),(3,'1.00')):
            ET.SubElement(stages,'Model',BuildPercentUpperBound=percent,File=(revision/(mains[name]+'_BS'+str(i)+'.mwm')).as_posix())
        ET.SubElement(ids,'string').text=typeid+'/'+ident
    save(root,MOD/'Data/CubeBlocks/ArcanePower_Thermal.sbc')
    save(category,MOD/'Data/ThermalCategories.sbc')


def install():
    rows,models,mains=manifest();exe=probe_exe()
    lods={};native={};compiled={}
    highlights={}
    lod_folder=MOD/'Models/Cubes/large/Thermal/LOD'
    for stem,row in rows.items():
        if row['type']!='lod':continue
        path=STAGING/(stem+'.mwm')
        lods[stem]=lod_folder/(stem+'_r'+digest(path)[:12]+'.mwm')
    for stem,row in rows.items():
        path=STAGING/(stem+'.mwm')
        references=[(key,value) for key,value in rows.items() if value['type']=='lod' and value['reference']==stem]
        references.sort(key=lambda item:item[1]['index'])
        if references:
            fixed=path.with_suffix('.relinked.mwm')
            subprocess.run(['mono',str(exe),'--lod-paths',str(path),str(fixed),
                            *[lods[key].relative_to(MOD).as_posix() for key,_ in references]],env=NATIVE_ENV,check=True,stdout=subprocess.DEVNULL)
            fixed.replace(path)
        hkt=path.with_suffix('.hkt')
        data=probe(exe,path,row['triangles'],hkt if hkt.exists() else None)
        if stem==mains['Reactor housing']:
            assert any(f[0]=='MATERIAL' and f[1]=='ArcanePower_CoolantGlass' for f in data),'Native reactor lacks current coolant glass'
        for fields in data:
            if fields[0]=='TEXTURE':
                value=fields[1].replace(chr(92),'/')
                assert resolve(MOD,value) or resolve(GAME/'Content',value),('Missing native texture',value)
                native[value]=True
        if row['type']=='bs':
            assert not any(fields[0]=='SUBPART' for fields in data),('Moving construction model',stem)
            assert not any(fields[0]=='MATERIAL' and any(t in fields[1] for t in ('ThermalHot','ThermalCold','ThermalStatus','ClearChamber','CoolantGlass')) for fields in data),('Powered/glazed weld stage',stem)
        compiled[stem]={'sha256':digest(path),'triangles':row['triangles'],'type':row['type'],
                        'lods':[lods[key].relative_to(MOD).as_posix() for key,_ in references],
                        'subparts':[fields[1] for fields in data if fields[0]=='SUBPART']}
    # Native origins must match the direct C# manifold and shaft pose contract.
    for name,stem in mains.items():
        actual=dummies(exe,STAGING/(stem+'.mwm'))
        if name=='Reactor housing':
            evidence=subprocess.check_output(['mono',str(exe),'--highlights',str(STAGING/(stem+'.mwm'))],env=NATIVE_ENV,text=True)
            sections=[line.split('\t') for line in evidence.splitlines() if line.startswith('SECTION\t')]
            highlights={parts[1]:parts[2].split(';') for line in evidence.splitlines()
                        if (parts:=line.split('\t'))[0]=='HIGHLIGHT'}
            assert len(sections)==3 and all(int(row[2])==1146 for row in sections),'Inventory hatch sections differ from accepted native access meshes'
            assert set(highlights)=={'detector_conveyor_0','detector_conveyor_2','detector_conveyor_top','detector_conveyor_bottom'}
            assert highlights['detector_conveyor_top']==['subpart_VentHatch'+str(i) for i in range(1,5)]
            for bay in ('LA','LB','RA','RB'):
                for part in ('Carriage','Intermediate','CoverMinus','CoverPlus','ConnectorTail'):
                    key='subpart_Thermal_'+bay+'_'+part
                    assert key in actual,('Missing manifold subpart',key)
                    identity=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]
                    assert max(abs(a-b) for a,b in zip(actual[key][0],identity))<1e-5,('Nonidentity manifold rest',key,actual[key])
        elif name.startswith('Brayton train'):
            for part,pivot in (('TurbineRotor',(1.35,.45,0)),('CompressorRotor',(4.25,.45,0))):
                key='subpart_Thermal_'+part
                assert key in actual and max(abs(actual[key][0][12+i]-pivot[i]) for i in range(3))<1e-5,('Wrong shaft pivot',key)
                assert max(abs(v-w) for v,w in zip(actual[key][0][:12],[1,0,0,0,0,1,0,0,0,0,1,0]))<1e-5,('Rotated shaft rest frame',key)
    bundle={stem+'.mwm':STAGING/(stem+'.mwm') for stem,row in rows.items() if row['type']!='lod'}
    pending=list(bundle.values())
    current=next(block for block in ET.parse(MOD/'Data/CubeBlocks/ArcanePower_Thermal.sbc').findall('CubeBlocks/Definition')
                 if block.findtext('Id/SubtypeId')=='ArcanePower_Thermal_ReactorHousing')
    inherited=MOD/current.findtext('Model')
    while pending:
        path=pending.pop()
        for matrix,file in dummies(exe,path).values():
            if not file:continue
            relative=Path(file.replace(chr(92),'/')+'.mwm')
            assert not relative.is_absolute() and '..' not in relative.parts,('Invalid native subpart',file)
            key=relative.as_posix()
            if key in bundle:continue
            source=next((folder/relative for folder in (STAGING,inherited.parent,MOD/'Models/Cubes/large') if (folder/relative).is_file()),None)
            assert source is not None,('Missing native subpart dependency',file,path)
            bundle[key]=source;pending.append(source)
    stamp=hashlib.sha256(b''.join(key.encode()+path.read_bytes() for key,path in sorted(bundle.items()))).hexdigest()[:12]
    revision=Path('Models/Cubes/large/Thermal')/('thermal_'+stamp)
    target=MOD/revision;target.mkdir(parents=True,exist_ok=True);lod_folder.mkdir(parents=True,exist_ok=True)
    for stem,path in lods.items():
        source=STAGING/(stem+'.mwm')
        if path.exists():assert digest(path)==digest(source),'Immutable LOD path collision'
        else:shutil.copy2(source,path)
    for key,source in bundle.items():
        destination=target/key;destination.parent.mkdir(parents=True,exist_ok=True)
        if destination.exists():assert digest(destination)==digest(source),'Immutable model path collision'
        else:shutil.copy2(source,destination)
    definitions(models,mains,revision)
    report={'status':'passed','revision':revision.as_posix(),'blocks':len(mains),'native_meshes':len(rows),
            'construction_models':sum(r['type']=='bs' for r in rows.values()),
            'lod_models':sum(r['type']=='lod' for r in rows.values()),
            'native_models':compiled,'external_native_subparts':len(bundle)-sum(r['type']!='lod' for r in rows.values()),
            'inventory_highlights':highlights,
            'physics':'Accepted reactor collision preserved; other blocks use up to ten hulls derived from real authored solids',
            'co2':'Integrated reactor generation and powered commissioning; no separate gas supply blocks',
            'game_reloaded':False,'workshop_published':False}
    (OUT/'native-export.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Installed',len(mains),'thermal blocks;',len(rows),'validated native meshes at',revision,flush=True)


if __name__=='__main__':
    if '--install-only' not in sys.argv:compile_all()
    install()
