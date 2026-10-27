"""Compile, inspect and install the complete native thermal family.

Exports come from assets/export_thermal_models.py. Player assets are installed
only after every requested main, subpart, construction mesh and LOD passes import.
"""
import copy
import hashlib
import json
import os
import runpy
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from prepare_lab import ROOT, MOD, GAME, XSI, REACTOR_TEMPLATE, save, set_text, hardware_components, write_block_menu
from package_release import resolve

STAGING=MOD/'Models/Cubes/large/.thermal-stage'
OUT=ROOT/'validation/thermal-models'
SETUP=Path.home()/'.local/share/blender-se1-setup'
ENV={**os.environ,'WINEDEBUG':'-all','WINEPREFIX':str(SETUP/'wineprefix')}
NATIVE_ENV={**os.environ,'MONO_PATH':str(GAME/'Bin64')}
CONTRACT=runpy.run_path(str(ROOT/'assets/thermal_model_contract.py'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest(additions=False):
    rows=json.loads((STAGING/'sources.json').read_text())
    models={name:spec for name,spec in json.loads((OUT/'models.json').read_text()).items() if name in CONTRACT['PLAYABLE']}
    rows={stem:row for stem,row in rows.items() if row['block'] in models}
    names={r['block'] for r in rows.values()}
    if additions:
        assert names and names <= set(models), 'Incremental exports must use known authored models'
        models={name:spec for name,spec in models.items() if name in names}
    assert names==set(models),'Incomplete source export'
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


def compile_all(additions=False):
    rows,_,_=manifest(additions)
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


def definitions(models,mains,revision,additions=False):
    reactor=ET.parse(REACTOR_TEMPLATE).find('CubeBlocks/Definition')
    module=ET.parse(MOD/'Data/CubeBlocks/ArcanePower_ContainmentController.sbc').find('CubeBlocks/Definition')
    root=ET.Element('Definitions');blocks=ET.SubElement(root,'CubeBlocks')
    if additions:
        root=ET.parse(MOD/'Data/CubeBlocks/ArcanePower_Thermal.sbc').getroot()
        blocks=root.find('CubeBlocks')
        replacing={CONTRACT['subtype'](name) for name in CONTRACT['RETIRED']}
        for definition in list(blocks):
            if definition.findtext('Id/SubtypeId') in replacing:blocks.remove(definition)
    for name,spec in models.items():
        ident=spec['subtype'];is_source=name=='Reactor housing';is_train=name.startswith('Brayton train')
        definition=copy.deepcopy(reactor if is_source or is_train else module)
        previous=next((b for b in blocks if b.findtext('Id/SubtypeId')==ident),None)
        if previous is None:blocks.append(definition)
        else:
            index=list(blocks).index(previous)
            blocks.remove(previous);blocks.insert(index,definition)
        typeid='Reactor' if is_source or is_train else 'UpgradeModule'
        set_text(definition,'Id/TypeId',typeid);set_text(definition,'Id/SubtypeId',ident)
        set_text(definition,'DisplayName','Arcane '+('Reactor' if is_source else name.replace(' / ',' ').replace('CO2','CO₂')))
        if spec.get('variant_of'):
            set_text(definition,'DisplayName','Arcane '+spec['variant_of'].replace(' / ',' ').replace('CO2','CO₂')+' Pipe (Bare)')
        set_text(definition,'Icon','Textures/GUI/Icons/ArcanePower/Thermal/'+ident+'.dds')
        set_text(definition,'BlockPairName',ident)
        set_text(definition,'Model',(revision/(mains[name]+'.mwm')).as_posix())
        set_text(definition,'Public','true');set_text(definition,'AvailableInSurvival','true')
        if name=='Atmospheric cooler':set_text(definition,'IsAirTight','true')
        size=definition.find('Size');size.attrib.clear();size.attrib.update(zip(('x','y','z'),map(str,spec['cells_se'])))
        if is_source:
            hardware_components(definition)
            set_text(definition,'MaxPowerOutput',1000)
        elif is_train:
            set_text(definition,'MaxPowerOutput',50000 if name.endswith('upgraded') else 250)
            set_text(definition,'PCU',80)
        else:
            if definition.find('Upgrades') is not None:definition.find('Upgrades').clear()
            set_text(definition,'PCU',2 if ' / ' in name else 30)
            set_text(definition,'PrimarySound','')
        set_text(definition,'Description',description(name))
        if not is_source:
            components=definition.find('Components');components.clear()
            volume=__import__('math').prod(spec['cells_se'])
            if is_train:
                # Compact packaging retains the same machinery and power rating.
                volume=30
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
    write_catalog(root)


def write_catalog(root):
    """One public pipe family, with asset-sharing aliases for saved grids."""
    blocks=root.find('CubeBlocks')
    names={CONTRACT['subtype'](name):name for name in CONTRACT['PLAYABLE']}
    for name,base in CONTRACT['COOLER_UPGRADES'].items():
        ident=CONTRACT['subtype'](name)
        for previous in list(blocks):
            if previous.findtext('Id/SubtypeId')==ident:blocks.remove(previous)
        source=next(b for b in blocks if b.findtext('Id/SubtypeId')==CONTRACT['subtype'](base))
        block=copy.deepcopy(source)
        for key,value in {'Id/SubtypeId':ident,'BlockPairName':ident,'DisplayName':'Arcane '+name,
                'Icon':'Textures/GUI/Icons/ArcanePower/Thermal/'+ident+'.dds'}.items():set_text(block,key,value)
        blocks.append(block)
    for block in list(blocks):
        if block.findtext('Id/SubtypeId') not in names:blocks.remove(block)
    canonical={block.findtext('Id/SubtypeId'):block for block in blocks}
    assert set(canonical)==set(names), 'Incomplete public thermal catalog'
    for ident,block in canonical.items():
        name=names[ident]
        if name.startswith('Brayton train'):
            # Keep subtype IDs stable for existing grids and projections.
            set_text(block,'DisplayName','Arcane '+name.replace('Brayton train','Turbine').title())
        set_text(block,'Description',description(name))
        components=block.find('Components')
        for component in list(components):
            if component.get('Subtype')=='ArcaneAetherResiduum':components.remove(component)
        if name.endswith('upgraded'):
            ET.SubElement(components,'Component',Subtype='ArcaneAetherResiduum',Count='20' if name.startswith('Brayton train') else '10')
            critical=block.find('CriticalComponent');critical.set('Subtype','ArcaneAetherResiduum');critical.set('Index','0')
        if ' / ' in name:
            shape=name.split(' / ')[1].removesuffix(' bare')
            style='Bare' if name in CONTRACT['BARE_PIPES'] else 'Manifold'
            set_text(block,'DisplayName','Arcane '+shape+' Pipe ('+style+')')
    for alias,target in CONTRACT['PIPE_ALIASES'].items():
        ident=CONTRACT['subtype'](alias)
        block=copy.deepcopy(canonical[CONTRACT['subtype'](target)])
        set_text(block,'Id/SubtypeId',ident)
        set_text(block,'BlockPairName',ident)
        set_text(block,'Public','false');set_text(block,'GuiVisible','false')
        # Keep survival availability so existing projections can still be welded.
        blocks.append(block)
    save(root,MOD/'Data/CubeBlocks/ArcanePower_Thermal.sbc')
    variant_groups(blocks)
    # Alias icons are no longer referenced; retain their authored PNG sources.
    for alias in CONTRACT['PIPE_ALIASES']:
        (MOD/'Textures/GUI/Icons/ArcanePower/Thermal'/(CONTRACT['subtype'](alias)+'.dds')).unlink(missing_ok=True)


def trim_native_manifest(report):
    prefixes=['APT_'+CONTRACT['subtype'](name).removeprefix('ArcanePower_Thermal_')+'_'
              for name in CONTRACT['RETIRED'] | set(CONTRACT['PIPE_ALIASES'])]
    report['native_models']={stem:row for stem,row in report['native_models'].items()
                             if not any(stem.startswith(prefix) for prefix in prefixes)}
    rows=report['native_models'].values()
    report.update(blocks=len(CONTRACT['PLAYABLE'])-len(CONTRACT['COOLER_UPGRADES']), compatibility_aliases=len(CONTRACT['PIPE_ALIASES']),
                  native_meshes=len(report['native_models']),
                  construction_models=sum(row['type']=='bs' for row in rows),
                  lod_models=sum(row['type']=='lod' for row in rows))


def description(name):
    base=CONTRACT['COOLER_UPGRADES'].get(name,name)
    if base in CONTRACT['COOLER_UPGRADES'].values():
        rating='20 GW' if name.endswith('upgraded') else '2 GW'
        if base == 'Atmospheric cooler': rating='50 GW' if name.endswith('upgraded') else '5 GW'
        detail={
            'Atmospheric cooler': (
                'INSTALLATION\nAirtight hull casing, rear manifold.\n'
                'Keep 2.5 m clear beyond both exhaust fans.\n'
                'Requires reactor auxiliary power for active cooling.\n\n'
                'ENVIRONMENT\nZero cooling in vacuum; full rating at 1 atmosphere.\n'
                'Half-clear exhaust gives 25% cooling; blocked gives none.'),
            'Space radiator': (
                'INSTALLATION\nBottom socket; automatic edge-on sun tracking.\n'
                'Keep both faces exposed to space.\n\n'
                'EXTENSIONS\nStack up to two panels on the top shaft coupling.\n'
                'Match Up; any yaw works. Mixed tiers add their own cooling.\n'
                'Grind either panel face to remove a section.\n\n'
                'ENVIRONMENT\nShade or edge-on: 100% cooling. Full sun: 50%.\n'
                'Angle, shade and weather follow solar-panel exposure.'),
            'Radiator panel': (
                'INSTALLATION\nStack directly above a radiator or its first extension.\n'
                'Aim at the top shaft coupling on the same grid.\n'
                'Match the base Up axis; any yaw works. Panels align automatically.\n'
                'Maximum two extensions; unattached panels provide no cooling.\n'
                'Grind either panel face to remove a section.\n\n'
                'ENVIRONMENT\nShade or edge-on: 100% cooling. Full sun: 50%.')
        }[base]
        return rating+' ideal heat rejection per unit/panel.\n\n'+detail+(
            '\n\nCRAFTING\nRequires 10 Aether Residuum recovered from T1 fuel.' if name.endswith('upgraded') else '')
    if name=='Reactor housing':
        return (
            'FUELS AND OUTPUT\nAether: 2.5 GW heat. Helion: 25 GW. Empyrean: 250 GW.\n'
            'Standalone: Aether only, 20% net / 500 MW electrical.\n'
            'Brayton: up to 40% starter / 80% exotic conversion.\n'
            'Helion and Empyrean require Brayton to prevent meltdown.\n\n'
            'ASSEMBLY\nTwo working controllers and a complete vent route are required.\n'
            'At least one fully built, functional advanced controller unlocks Brayton.\n'
            'The reactor generates CO2 internally.\n\n'
            'CIRCUITS\nFour independent manifolds; one turbine plus cooling per circuit.\n'
            'Each circuit supplies up to 25% capacity.\n'
            'Align H/C, keep circuits separate and cap unused pipe mouths.\n\n'
            'SHUTDOWN AND SAFETY\nA circuit breach isolates that manifold.\n'
            'Losing all valid circuits stops generation.\n'
            'Runtime faults stop generation while intact cooling paths stay open.\n'
            'A manual Start with all four circuits defective latches a startup fault.\n'
            'Normal Stop does not latch. Stop and cool before changing mode.')
    if name.startswith('Brayton train'):
        return (
            'FUELS\n'+('Compatible with T3 Empyrean heat.\nRequires 20 Aether Residuum.'
                if name.endswith('upgraded') else 'T1/T2 fuels only; T3 Empyrean requires upgraded turbines.')+
            '\n\nINSTALLATION\n2 wide x 2 high x 5 long large-grid turbine/compressor.\n'
            'One lower-cell duplex H/C socket; mirrored versions move it to the opposite side.\n\n'
            'CIRCUIT\nConnect exactly one turbine and cooling per reactor manifold.\n'
            'Keep the four circuits separate; each receives up to 25% of reactor heat.\n'
            'The reactor supplies CO2 internally.\n'
            'Running auxiliaries are included in conversion efficiency.\n'
            'Keep reactor auxiliary power available for active coolers during cooldown.')
    if name in ('PRIMARY / Reactor adapter', 'PRIMARY / Reactor adapter bare'):
        return (
            '170 mm reactor offset adapter.\n\n'
            'The offset end connects only to the Arcane Reactor vessel.\n'
            'Use the opposite end for normal duplex pipes.\n\n'
            'Align H with H and C with C.\n'
            'Keep each reactor manifold circuit separate and cap unused pipe mouths.')
    return (
        'CO2 supply/return pipe for one independent reactor manifold circuit.\n'
        'Keep the circuit on one physical grid.\n\n'
        'Align H to H and C to C.\n'
        'Cap unused pipe mouths; a breach closes this circuit at the reactor.\n'
        'Ordinary conveyors do not replace thermal pipes.')


def variant_groups(blocks):
    # Scroll through shapes within one appearance. Read the complete installed
    # catalog so an incremental export does not discard the other pipe members.
    installed={block.findtext('Id/SubtypeId') for block in blocks}
    bare=[block.findtext('Id/SubtypeId') for block in blocks
          if block.findtext('Id/SubtypeId').endswith('Bare') and block.findtext('Public')=='true']
    framed=[subtype.removesuffix('Bare') for subtype in bare]
    assert set(framed)<=installed, 'Bare pipe is missing its manifold counterpart'
    groups=[]
    for key,label,subtypes in (('BarePipes','Bare',bare),('ManifoldPipes','Manifold',framed)):
        if not subtypes:continue
        groups.append((key,'Arcane Pipes ('+label+')',
            'Scroll through '+label.lower()+' thermal pipes and fittings. Connect the shared supply/return network; align H/C on every socket face.',subtypes))
    groups.extend([
        ('Cooling','Arcane Radiators and Coolers','Scroll through radiators, extension panels and atmospheric coolers, including upgraded versions.',
         ['ArcanePower_Thermal_'+name for name in ('SpaceRadiator','SpaceRadiatorUpgraded','RadiatorPanel',
          'RadiatorPanelUpgraded','AtmosphericCooler','AtmosphericCoolerUpgraded')]),
        ('Turbines','Arcane Turbines','Scroll through standard, upgraded and mirrored Brayton turbines.',
         ['ArcanePower_Thermal_BraytonTrain'+suffix for suffix in ('','Upgraded','Mirrored','MirroredUpgraded')])])
    write_block_menu(blocks,'Thermal',groups,MOD)


def install(additions=False):
    rows,models,mains=manifest(additions);exe=probe_exe()
    previous=json.loads((OUT/'native-export.json').read_text()) if additions else None
    if previous:assert previous['status']=='passed'
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
        if row['type']=='main' and '_RadiatorPanels_' in stem:
            assert hkt.is_file() and hkt.stat().st_size>0, ('Missing rotating panel collision',stem)
        data=probe(exe,path,row['triangles'],hkt if hkt.exists() else None)
        if stem==mains.get('Reactor housing'):
            assert any(f[0]=='MATERIAL' and f[1]=='ArcanePower_CoolantGlass' for f in data),'Native reactor lacks current coolant glass'
        for fields in data:
            if fields[0]=='TEXTURE':
                value=fields[1].replace(chr(92),'/')
                assert resolve(MOD,value) or resolve(GAME/'Content',value),('Missing native texture',value)
                native[value]=True
        if row['type']=='bs':
            assert not any(fields[0]=='SUBPART' for fields in data),('Moving construction model',stem)
            assert not any(fields[0]=='MATERIAL' and any(t in fields[1] for t in ('ThermalHot','ThermalCold','ThermalStatus','ThermalRadiatorHeat','ClearChamber','CoolantGlass')) for fields in data),('Powered/glazed weld stage',stem)
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
            hatches=[row for row in sections if 'control ' not in row[1]]
            assert len(hatches)==3 and all(int(row[2])==1146 for row in hatches),'Inventory hatch sections differ from accepted native access meshes'
            assert set(highlights)=={'detector_conveyor_0','detector_conveyor_2','detector_conveyor_top','detector_conveyor_bottom','detector_terminal_control','detector_terminal_control_opposite'}
            assert len(highlights['detector_terminal_control'])==1 and 'control terminal_section' in highlights['detector_terminal_control'][0]
            assert len(highlights['detector_terminal_control_opposite'])==1 and 'control opposite terminal_section' in highlights['detector_terminal_control_opposite'][0]
            positions=[actual[key][0][12:15] for key in ('detector_terminal_control','detector_terminal_control_opposite')]
            assert abs(positions[0][0]+positions[1][0])<1e-5 and abs(positions[0][2]+positions[1][2])<1e-5, 'Control panels must be opposite around the reactor axis'
            assert highlights['detector_conveyor_top']==['subpart_VentHatch'+str(i) for i in range(1,5)]
            for bay in ('LA','LB','RA','RB'):
                for part in ('Carriage','Intermediate','CoverMinus','CoverPlus','ConnectorTail','ChamberVent'):
                    key='subpart_Thermal_'+bay+'_'+part
                    assert key in actual,('Missing manifold subpart',key)
                    identity=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]
                    assert max(abs(a-b) for a,b in zip(actual[key][0],identity))<1e-5,('Nonidentity manifold rest',key,actual[key])
        elif name in ('Space radiator','Radiator panel'):
            key='subpart_Thermal_RadiatorPanels'
            expected=[1,0,0,0,0,1,0,0,0,0,1,0,0,-1.1 if name=='Space radiator' else 0,0,1]
            assert key in actual and max(abs(a-b) for a,b in zip(actual[key][0],expected))<1e-5,('Wrong radiator pivot',actual)
        elif name.startswith('Brayton train'):
            rotors=json.loads((ROOT/'assets/thermal-rotor-runtime.json').read_text())
            for rotor in rotors['rotors']:
                x,y,z=rotor['pivot_blender']
                pivot=(-x,z,y)
                key='subpart_'+rotor['subpart']
                assert key in actual and max(abs(actual[key][0][12+i]-pivot[i]) for i in range(3))<1e-5,('Wrong shaft pivot',key)
                assert max(abs(v-w) for v,w in zip(actual[key][0][:12],[1,0,0,0,0,1,0,0,0,0,1,0]))<1e-5,('Rotated shaft rest frame',key)
    if 'Reactor housing' in mains:
        from check_reactor_roof import check as check_roof
        main = mains['Reactor housing']
        check_roof([STAGING/(stem+'.mwm') for stem in [main, *[key for key, row in rows.items()
                   if row['type']=='lod' and row['reference']==main]]])
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
    definitions(models,mains,revision,additions)
    if previous:compiled={**previous['native_models'],**compiled}
    retired=['APT_'+CONTRACT['subtype'](name).removeprefix('ArcanePower_Thermal_')+'_' for name in CONTRACT['RETIRED']]
    compiled={stem:row for stem,row in compiled.items() if not any(stem.startswith(prefix) for prefix in retired)}
    report={'status':'passed','revision':revision.as_posix(),'blocks':len(CONTRACT['PLAYABLE']),'native_meshes':len(compiled),
            'construction_models':sum(r['type']=='bs' for r in compiled.values()),
            'lod_models':sum(r['type']=='lod' for r in compiled.values()),
            'native_models':compiled,'external_native_subparts':previous['external_native_subparts'] if previous else len(bundle)-sum(r['type']!='lod' for r in rows.values()),
            'inventory_highlights':{k:v for k,v in highlights.items() if k.startswith('detector_conveyor_')} or (previous['inventory_highlights'] if previous else {}),
            'control_panel_highlights':{k:v for k,v in highlights.items() if k.startswith('detector_terminal_control')} or (previous.get('control_panel_highlights',{}) if previous else {}),
            'physics':'Reactor uses ten flat hulls: unchanged deck/roof, four glass quadrants and four fitted pillars; radiator axial docks retain stacking clearance; rotating panel faces and frames have native subpart hulls',
            'co2':'Automatic reactor CO2 supply; metered startup/cooldown circulation; no filling or pressure gate',
            'game_reloaded':False,'workshop_published':False}
    trim_native_manifest(report)
    (OUT/'native-export.json').write_text(json.dumps(report,indent=2)+'\n')
    subprocess.run([sys.executable,str(ROOT/'tools/check_native_thermal_motion.py')],check=True)
    print('Installed',len(mains),'thermal blocks;',len(rows),'validated native meshes at',revision,flush=True)


if __name__=='__main__':
    if '--catalog-only' in sys.argv:
        write_catalog(ET.parse(MOD/'Data/CubeBlocks/ArcanePower_Thermal.sbc').getroot())
        report=json.loads((OUT/'native-export.json').read_text())
        trim_native_manifest(report)
        (OUT/'native-export.json').write_text(json.dumps(report,indent=2)+'\n')
        print('Updated public catalog and compatibility aliases using installed models')
        sys.exit(0)
    additions='--additions' in sys.argv or '--update' in sys.argv
    if '--install-only' not in sys.argv:compile_all(additions)
    install(additions)
