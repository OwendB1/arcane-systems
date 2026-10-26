"""Build SE1 definition-based prototype and an isolated empty survival test world."""
import copy
import hashlib
import json
import math
import re
import shutil
import uuid
import xml.etree.ElementTree as E
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GAME = Path.home()/'.local/share/Steam/steamapps/common/SpaceEngineers'
USER = Path.home()/'.config/SpaceEngineers'
MOD = ROOT/'src'
REACTOR_TEMPLATE = ROOT/'assets/definitions/ArcanePower_ReactorPrototype.sbc'
COLLISIONS = ROOT/'assets/collisions/Cubes/large'
BASE_MODELS = ROOT/'assets/native-baselines/Cubes/large'
WORLD = USER/'Saves/76561198074076521/Arcane Power - Prototype Lab'
XSI = 'http://www.w3.org/2001/XMLSchema-instance'
E.register_namespace('xsi', XSI)


def set_text(node, path, value):
    current = node
    for part in path.split('/'):
        found = current.find(part)
        current = found if found is not None else E.SubElement(current, part)
    current.text = str(value)


def save(root, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    E.indent(root)
    E.ElementTree(root).write(path, encoding='utf-8', xml_declaration=True)


def write_block_menu(blocks, family, groups, mod):
    """Native scroll groups; only their first member gets a category entry."""
    public={b.findtext('Id/SubtypeId'):b for b in blocks
            if b.findtext('Public','true').lower()=='true'}
    variants=E.Element('Definitions');variant_groups=E.SubElement(variants,'BlockVariantGroups')
    grouped=set();secondary=set()
    for key,label,description,members in groups:
        assert members and len(members)==len(set(members)) and set(members)<=public.keys(), ('Invalid scroll group',key)
        assert not grouped.intersection(members), ('Duplicate scroll membership',key)
        grouped.update(members);secondary.update(members[1:])
        group=E.SubElement(variant_groups,'BlockVariantGroup')
        E.SubElement(group,'Id',Type='MyObjectBuilder_BlockVariantGroup',Subtype='ArcanePower_'+family+'_'+key)
        set_text(group,'Icon',public[members[0]].findtext('Icon'))
        set_text(group,'DisplayName',label);set_text(group,'Description',description)
        entries=E.SubElement(group,'Blocks')
        for subtype in members:
            E.SubElement(entries,'Block',Type='MyObjectBuilder_'+public[subtype].findtext('Id/TypeId'),Subtype=subtype)
    categories=E.Element('Definitions')
    category=E.SubElement(E.SubElement(categories,'CategoryClasses'),'Category',{'{'+XSI+'}type':'MyObjectBuilder_GuiBlockCategoryDefinition'})
    for path,value in {'Id/TypeId':'GuiBlockCategoryDefinition','Id/SubtypeId':'ArcaneSystems_'+family,
                       'DisplayName':'Arcane Systems','Name':'ArcaneSystems'}.items():set_text(category,path,value)
    items=E.SubElement(category,'ItemIds')
    for subtype,block in public.items():
        if subtype not in secondary:E.SubElement(items,'string').text=block.findtext('Id/TypeId')+'/'+subtype
    filename={'Power':'BlockCategories.sbc','Energy':'EnergyCoreCategories.sbc','Thermal':'ThermalCategories.sbc'}[family]
    save(categories,mod/'Data'/filename)
    save(variants,mod/'Data/CubeBlocks'/('ArcanePower_'+family+'Variants.sbc'))


def power_block_menu():
    blocks=[]
    for name in ('ContainmentController','Vents'):
        blocks.extend(E.parse(MOD/'Data/CubeBlocks'/('ArcanePower_'+name+'.sbc')).findall('CubeBlocks/Definition'))
    write_block_menu(blocks,'Power',[
        ('Controllers','Arcane Controllers','Scroll through standard and advanced reactor controllers.',
         ['ArcanePower_ContainmentController','ArcanePower_AdvancedContainmentController']),
        ('Vents','Arcane Vents','Scroll through the vent duct and outlet. Finish each vent route with an outlet.',
         ['ArcanePower_VentDuct','ArcanePower_VentOutlet'])],MOD)


def hardware_components(block):
    """Construction order and material costs for the reactor's required hardware."""
    recipes = {
        'ArcanePower_Thermal_ReactorHousing': [
            ('SteelPlate',2400),('Construction',1000),('MetalGrid',600),('LargeTube',240),
            ('Reactor',2000),('Motor',200),('Superconductor',1500),('BulletproofGlass',160),
            ('Computer',400),('SteelPlate',600)],
        'ArcanePower_ContainmentController': [
            ('SteelPlate',240),('Construction',150),('MetalGrid',40),('SmallTube',80),
            ('Superconductor',300),('Computer',150),('Motor',40),('SteelPlate',60)],
        'ArcanePower_AdvancedContainmentController': [
            ('SteelPlate',480),('Construction',300),('MetalGrid',80),('SmallTube',160),
            ('Superconductor',3000),('Computer',500),('Motor',80),('SteelPlate',120)],
        'ArcanePower_VentDuct': [
            ('SteelPlate',180),('InteriorPlate',40),('Construction',120),('MetalGrid',40),
            ('LargeTube',40),('SmallTube',40),('Computer',16),('Motor',16),
            ('InteriorPlate',40),('SteelPlate',60)],
        'ArcanePower_VentOutlet': [
            ('SteelPlate',280),('InteriorPlate',60),('Construction',180),('MetalGrid',80),
            ('LargeTube',60),('SmallTube',80),('Computer',64),('Motor',64),
            ('InteriorPlate',60),('SteelPlate',80)],
    }
    subtype=block.findtext('Id/SubtypeId')
    # The archived authoring reactor is the template for current native exports.
    if subtype=='ArcanePower_ReactorPrototype':subtype='ArcanePower_Thermal_ReactorHousing'
    recipe=recipes[subtype]
    components=block.find('Components');components.clear()
    for component,count in recipe:
        E.SubElement(components,'Component',Subtype=component,Count=str(count))


BUILD_BLOCKS = {
    'ArcanePower_ReactorPrototype': 'ArcanePower_ReactorPrototype.sbc',
    'ArcanePower_ContainmentController': 'ArcanePower_ContainmentController.sbc',
    'ArcanePower_AdvancedContainmentController': 'ArcanePower_ContainmentController.sbc',
    'ArcanePower_VentDuct': 'ArcanePower_Vents.sbc',
    'ArcanePower_VentOutlet': 'ArcanePower_Vents.sbc',
}


def model_source(name):
    """Find a fresh export or its accepted authoring baseline outside the mod."""
    for folder in (MOD/'Models/Cubes/large', BASE_MODELS):
        source=folder/(name+'.mwm')
        if source.is_file():return source
    raise FileNotFoundError('Export the model from its production blend first: '+name)


def model_revision(name):
    """Give each export a fresh native model/physics cache key."""
    source=model_source(name)
    data=source.read_bytes()
    version=MOD/'Models/Cubes/large'/(source.stem+'_r'+hashlib.sha256(data).hexdigest()[:12]+source.suffix)
    if not version.exists() or version.read_bytes()!=data:version.write_bytes(data)
    return version.relative_to(MOD).as_posix()


def refresh_reactor_model():
    # Subpart filenames are relative to the parent MWM. A parent-only hash
    # misses plasma/ring/tile changes and leaves their native cache keys intact.
    folder=MOD/'Models/Cubes/large'
    names={p.stem for directory in (BASE_MODELS,folder) for p in directory.glob('ArcanePower_*.mwm')
           if '.hkt.' not in p.name and not re.search(r'_BS\d|_LOD\d|_r[0-9a-f]{12}',p.stem)}
    models=[model_source(name) for name in sorted(names)]
    if 'ArcanePower_ReactorPrototype' not in names:
        raise FileNotFoundError('Export the archived reactor from its production blend first')
    digest=hashlib.sha256(b''.join(p.name.encode()+p.read_bytes() for p in models)).hexdigest()[:12]
    revision=folder/('reactor_'+digest)
    revision.mkdir(exist_ok=True)
    for source in models:
        target=revision/source.name
        if not target.exists() or target.read_bytes()!=source.read_bytes():
            shutil.copy2(source,target)
    relative=(revision/'ArcanePower_ReactorPrototype.mwm').relative_to(MOD).as_posix()
    path=REACTOR_TEMPLATE
    tree=E.parse(path)
    model=tree.find('CubeBlocks/Definition/Model')
    if model.text!=relative:
        model.text=relative
        save(tree.getroot(),path)
    path=MOD/'Data/EjectedContainment.sbc'
    if path.exists():
        tree=E.parse(path)
        model=tree.find('CubeBlocks/Definition/Model')
        plasma=(revision/'ArcanePower_Plasma.mwm').relative_to(MOD).as_posix()
        if model.text!=plasma:
            model.text=plasma
            save(tree.getroot(),path)
    return relative


def refresh_build_stages():
    for filename in dict.fromkeys(BUILD_BLOCKS.values()):
        path=REACTOR_TEMPLATE if filename == 'ArcanePower_ReactorPrototype.sbc' else MOD/'Data/CubeBlocks'/filename
        tree=E.parse(path)
        for block in tree.findall('CubeBlocks/Definition'):
            name=block.findtext('Id/SubtypeId')
            if name not in BUILD_BLOCKS:continue
            for old in block.findall('BuildProgressModels'):block.remove(old)
            stages=E.SubElement(block,'BuildProgressModels')
            for stage,limit in enumerate(('0.33','0.67','1.00'),1):
                E.SubElement(stages,'Model',BuildPercentUpperBound=limit,
                             File=model_revision(name+'_BS'+str(stage)))
        save(tree.getroot(),path)


def definitions():
    energy = E.parse(GAME/'Content/Data/CubeBlocks/CubeBlocks_Energy.sbc').getroot()
    reactor = copy.deepcopy(next(n for n in energy.iter('Definition') if n.findtext('Id/SubtypeId')=='LargeBlockSmallGenerator'))
    for key,value in {'Id/SubtypeId':'ArcanePower_ReactorPrototype', 'DisplayName':'Arcane Reactor',
        'Icon':'Textures/GUI/Icons/ArcaneReactor.dds',
        'Description':'Aether: 10 GW. Helion: 100 GW. Empyrean: 1 TW. Two working containment controllers required; their installation tier sets two/three/four rings, 1x/1.5x/2x tile deployment and 80%/90%/99% fuel efficiency. Venting ejects containment through the conveyor-connected top hatch, damages the reactor/modules, and leaves the reactor off. Automatic core ejection at 60% remaining integrity requires intact controllers and vents. Security mode selects shutdown or warning on vent loss after startup.',
        'Model':'Models/Cubes/large/ArcanePower_ReactorPrototype.mwm', 'BlockPairName':'ArcanePower_ReactorPrototype',
        'MaxPowerOutput':10000, 'FuelProductionToCapacityMultiplier':3600, 'PCU':100,
        'IsAirTight':'false','InventorySize/X':2,'InventorySize/Y':1,'InventorySize/Z':1,
        'FuelInfos/FuelInfo/Id/SubtypeId':'ArcaneFuelI'}.items(): set_text(reactor,key,value)
    # Native FuelInfos are simultaneous requirements, not alternative fuels.
    # Reactor.Fuel.cs selects/consumes one tier and supplies native capacity.
    reactor.find('FuelInfos').clear()
    for n in list(reactor.findall('FuelId')):reactor.remove(n)
    reactor.find('Size').attrib.update(x='5',y='3',z='5')
    for name in ['BuildProgressModels','MountPoints','MirroringX','MirroringY','MirroringZ']:
        for n in list(reactor.findall(name)): reactor.remove(n)
    mount=E.SubElement(reactor,'MountPoints')
    E.SubElement(mount,'MountPoint',Side='Bottom',StartX='0',StartY='0',EndX='5',EndY='5')
    # Inscribed strips cover the widened round roof, including its outer grid cells.
    # Keep mount rectangles over physical roof rather than the empty corner cells.
    radius=6.24/2.5
    for row in range(16):
        y0=2.5-radius+row*(2*radius/16)
        y1=y0+2*radius/16
        half=math.sqrt(max(0,radius*radius-max(abs(y0-2.5),abs(y1-2.5))**2))
        if half<.01:continue
        E.SubElement(mount,'MountPoint',Side='Top',StartX=f'{2.5-half:.4f}',EndX=f'{2.5+half:.4f}',StartY=f'{y0:.4f}',EndY=f'{y1:.4f}')
    for side in ['Front','Back','Left','Right']:
        E.SubElement(mount,'MountPoint',Side=side,StartX='2',EndX='3',StartY='0',EndY='1')
    hardware_components(reactor)
    root=E.Element('Definitions'); blocks=E.SubElement(root,'CubeBlocks');blocks.append(reactor)
    save(root,REACTOR_TEMPLATE)
    refresh_reactor_model()

    production=E.parse(GAME/'Content/Data/CubeBlocks/CubeBlocks_Production.sbc').getroot()
    module=copy.deepcopy(next(n for n in production.iter('Definition') if n.findtext('Id/SubtypeId')=='LargeProductivityModule'))
    for path,val in {'Id/SubtypeId':'ArcanePower_ContainmentController','DisplayName':'Arcane Containment Controller',
        'Description':'Attach directly to either reactor side socket. Two standard controllers deploy two rings at 1x tile speed with 80% fuel efficiency and support Aether.',
        'Model':'Models/Cubes/large/ArcanePower_ContainmentController.mwm','BlockPairName':'ArcanePower_ContainmentController',
        'Upgrades/MyUpgradeModuleInfo/UpgradeType':'ArcaneContainment','Upgrades/MyUpgradeModuleInfo/Modifier':1}.items():set_text(module,path,val)
    module.find('Size').attrib.update(x='1',y='1',z='1')
    for tag in ['BuildProgressModels','MountPoints','MirroringX','MirroringY','MirroringZ']:
        for n in list(module.findall(tag)):module.remove(n)
    mount=E.SubElement(module,'MountPoints')
    for side in ['Front','Back','Left','Right','Top','Bottom']:
        E.SubElement(mount,'MountPoint',Side=side,StartX='0',StartY='0',EndX='1',EndY='1')
    hardware_components(module)
    root=E.Element('Definitions');E.SubElement(root,'CubeBlocks').append(module)
    count=copy.deepcopy(module.find('Upgrades/MyUpgradeModuleInfo'))
    set_text(count,'UpgradeType','ArcaneControllerCount')
    module.find('Upgrades').append(count)
    advanced=copy.deepcopy(module)
    for path,val in {'Id/SubtypeId':'ArcanePower_AdvancedContainmentController',
        'DisplayName':'Arcane Advanced Containment Controller',
        'BlockPairName':'ArcanePower_AdvancedContainmentController',
        'Description':'Two working controllers are required. Standard + advanced: three rings, 1.5x tile speed, 90% efficiency, supports Aether/Helion. Two advanced: four rings, 2x tile speed, 99% efficiency, supports all fuels.',
        'Upgrades/MyUpgradeModuleInfo/Modifier':2}.items():set_text(advanced,path,val)
    hardware_components(advanced)
    root.find('CubeBlocks').append(advanced)
    save(root,MOD/'Data/CubeBlocks/ArcanePower_ContainmentController.sbc')

    fuel_definitions()
    external_hardware_definitions()
    refresh_build_stages()
    metadata=E.Element('ModMetadata')
    set_text(metadata,'ModVersion',(ROOT/'workshop/version.txt').read_text().strip())
    save(metadata,MOD/'metadata.mod')


def external_hardware_definitions():
    logistics=E.parse(GAME/'Content/Data/CubeBlocks/CubeBlocks_Logistics.sbc').getroot()
    template=next(n for n in logistics.iter('Definition') if n.findtext('Id/SubtypeId')=='LargeBlockConveyor')
    root=E.Element('Definitions');blocks=E.SubElement(root,'CubeBlocks')
    for subtype,label in [('ArcanePower_VentDuct','Arcane Vent Duct'),('ArcanePower_VentOutlet','Arcane Vent Outlet')]:
        n=copy.deepcopy(template)
        for path,value in {'Id/SubtypeId':subtype,'DisplayName':label,'Description':'Stack matching vent sections above the reactor and finish with an Arcane Vent Outlet. The outlet opens during venting. Central connections also carry conveyor items.',
                'Model':'Models/Cubes/large/'+subtype+'.mwm','EmissiveColorPreset':'ArcaneVentDisconnected','Icon':'Textures/GUI/Icons/'+('ArcaneVentOutlet' if subtype.endswith('Outlet') else 'ArcaneVentDuct')+'.dds','BlockPairName':subtype,'IsAirTight':'false','GuiVisible':'true','PCU':25,'BuildTimeSeconds':30}.items():set_text(n,path,value)
        n.find('Size').attrib.update(x='3',y='1',z='3')
        for tag in ['BuildProgressModels','MountPoints','MirroringX','MirroringY','MirroringZ','Center']:
            for child in list(n.findall(tag)):n.remove(child)
        E.SubElement(n,'Center',x='1',y='0',z='1')
        mount=E.SubElement(n,'MountPoints')
        for side in ('Top','Bottom'):
            for x0,y0,x1,y1 in [(0,0,3,.65),(0,2.35,3,3),(0,.65,.65,2.35),(2.35,.65,3,2.35)]:
                E.SubElement(mount,'MountPoint',Side=side,StartX=str(x0),StartY=str(y0),EndX=str(x1),EndY=str(y1))
        for side in ('Front','Back','Left','Right'):
            E.SubElement(mount,'MountPoint',Side=side,StartX='0',StartY='0',EndX='3',EndY='1')
        hardware_components(n)
        blocks.append(n)
    save(root,MOD/'Data/CubeBlocks/ArcanePower_Vents.sbc')
    p=MOD/'Data/CubeBlocks/ArcanePower_ContainmentController.sbc';r=E.parse(p).getroot()
    for n in r.iter('Definition'):
        subtype=n.findtext('Id/SubtypeId')
        set_text(n,'Model','Models/Cubes/large/'+subtype+'.mwm')
        set_text(n,'Icon','Textures/GUI/Icons/'+('ArcaneAdvancedContainmentController' if 'Advanced' in subtype else 'ArcaneContainmentController')+'.dds')
    save(r,p)
    power_block_menu()
    containment_tiles()


def fuel_definitions():
    """Author the ore -> dense concentrate -> cumulative fuel production chain."""
    existing=E.parse(MOD/'Data/PhysicalItems.sbc').getroot()
    ore_template=next(n for n in existing.iter('PhysicalItem') if n.findtext('Id/SubtypeId')=='ArcaneOre')
    fuel_template=next(n for n in existing.iter('PhysicalItem') if n.findtext('Id/SubtypeId')=='ArcaneFuelI')
    concentrate_template=next(n for n in existing.iter('PhysicalItem') if n.findtext('Id/SubtypeId')=='ArcaneAetherConcentrate')
    items_root=E.Element('Definitions');items=E.SubElement(items_root,'PhysicalItems')
    recipes_root=E.Element('Definitions');recipes=E.SubElement(recipes_root,'Blueprints')
    entries=E.SubElement(recipes_root,'BlueprintClassEntries')
    voxels_root=E.Element('Definitions');voxels=E.SubElement(voxels_root,'VoxelMaterials')
    native=E.parse(GAME/'Content/Data/VoxelMaterials_asteroids.sbc').getroot()
    voxel_template=next(n for n in native.iter('VoxelMaterial') if n.findtext('Id/SubtypeId')=='Uraninite_01')
    tiers=[
        ('Aether','Aetherite','ArcaneOre','ArcaneFuelI','ArcaneAetherConcentrate','ArcaneAetherOreToConcentrate','ArcaneAetherFuel',20,.2,.001,.01,10,'10 GW'),
        ('Helion','Helionite','ArcaneHelionOre','ArcaneFuelII','ArcaneHelionConcentrate','ArcaneHelionOreToConcentrate','ArcaneHelionFuel',2,.03,.0001,.005,20,'100 GW'),
        ('Empyrean','Empyrite','ArcaneEmpyreanOre','ArcaneFuelIII','ArcaneEmpyreanConcentrate','ArcaneEmpyreanOreToConcentrate','ArcaneEmpyreanFuel',1,.01,.00001,.001,40,'1 TW')]

    def recipe(subtype,name,prerequisites,result,amount,seconds,category,result_type='Ingot',whole_canister=False):
        bp=E.SubElement(recipes,'Blueprint')
        for key,value in {'Id/TypeId':'BlueprintDefinition','Id/SubtypeId':subtype,'DisplayName':name,
                'Icon':'Textures/GUI/Icons/ArcanePower/'+result+'.dds','BaseProductionTimeInSeconds':seconds}.items():set_text(bp,key,value)
        pre=E.SubElement(bp,'Prerequisites')
        for kind,item,quantity in prerequisites:
            E.SubElement(pre,'Item',TypeId=kind,SubtypeId=item,Amount=f'{quantity:g}')
        E.SubElement(bp,'Result',TypeId=result_type,SubtypeId=result,Amount=f'{amount:g}')
        if whole_canister:set_text(bp,'IgnoreEfficiencyMultiplier','true')
        E.SubElement(entries,'Entry',Class=category,BlueprintSubtypeId=subtype)

    canister='ArcaneAetherCanister'
    canister_inputs=[('Ingot','Iron',100),('Ingot','Cobalt',40),('Ingot','Silver',10),('Ingot','Platinum',5),
                     ('Component','Superconductor',10),('Component','Computer',4),('Component','MetalGrid',4)]
    native_components={n.findtext('Id/SubtypeId'):float(n.findtext('Mass')) for n in
                       E.parse(GAME/'Content/Data/Components.sbc').findall('Components/Component')}
    canister_mass=sum(amount*(native_components[subtype] if kind=='Component' else 1)
                      for kind,subtype,amount in canister_inputs)
    container=copy.deepcopy(E.parse(MOD/'Data/ContainmentTiles.sbc').getroot().find('Components/Component'))
    for key,value in {'Id/SubtypeId':canister,'DisplayName':'Aether Containment Canister (Empty)',
            'Icon':'Textures/GUI/Icons/ArcanePower/'+canister+'.dds',
            'Model':'Models/Items/ArcanePower/'+canister+'.mwm','Mass':canister_mass,'Volume':24,
            'Size/X':.261,'Size/Y':.438,'Size/Z':.261,
            'Description':'Empty platinum-lined, superconducting fuel container. Fill with 10 kg of Aether Concentrate. The container carries through Helion and Empyrean upgrades; consumed fuel does not return an empty canister.'}.items():set_text(container,key,value)
    E.SubElement(items_root,'Components').append(container)
    recipe(canister,'Aether Containment Canister (Empty)',canister_inputs,canister,1,60,'Components',result_type='Component')
    # Recovered directly by the reactor; deliberately no assembler/refinery recipe.
    residuum=copy.deepcopy(container)
    for key,value in {'Id/SubtypeId':'ArcaneAetherResiduum','DisplayName':'Aether Residuum',
            'Icon':'Textures/GUI/Icons/ArcanePower/ArcaneAetherResiduum.dds',
            'Model':'Models/Items/ArcanePower/ArcaneAetherResiduum.mwm',
            'Mass':1,'Volume':.001,'Size/X':.12,'Size/Y':.10,'Size/Z':.08,
            'MaxIntegrity':100,'Health':100,'DropProbability':1,
            'Description':'An exceptionally dense, heat-resistant material recovered from consumed Aether fuel. Requires no processing. Ten 1 kg units per fully consumed canister, in standalone or Brayton mode. Used in advanced turbines (20 units) and cooling units/panels (10 units). Inventory volume: 0.001 L per unit.'}.items():set_text(residuum,key,value)
    items_root.find('Components').append(residuum)


    for tier,(name,ore_name,ore,fuel,concentrate,refining,preparing,weight,mined,yield_ratio,volume,seconds,rating) in enumerate(tiers):
        raw=copy.deepcopy(ore_template)
        for key,value in {'Id/SubtypeId':ore,'DisplayName':ore_name+' Ore','Mass':1,'Volume':.37,
                'Description':f'Rare asteroid ore. Base refining yield: {yield_ratio*100:g}%. Refine to {name} Concentrate, then prepare fuel in an assembler.'}.items():set_text(raw,key,value)
        set_text(raw,'Icon','Textures/GUI/Icons/ArcanePower/'+ore+'.dds')
        set_text(raw,'Model','Models/Items/ArcanePower/'+ore+'.mwm')
        # Native ore otherwise substitutes an amount-based vanilla debris mesh.
        variants=raw.find('Models')
        if variants is not None:raw.remove(variants)
        set_text(raw,'Models/Model','Models/Items/ArcanePower/'+ore+'.mwm')
        set_text(raw,'VoxelMaterial','Arcane'+name+'Deposit')
        items.append(raw)
        for subtype,label in [(concentrate,name+' Concentrate'),(fuel,name+' Fuel Canister — '+rating)]:
            concentrated=subtype==concentrate
            item=copy.deepcopy(concentrate_template if concentrated else fuel_template)
            description=(f'Dense refined material: {volume:g} L/kg ({1/volume:g} kg/L). Ore matrix is removed during refinement. Assembler ingredient for '+name+' fuel.' if concentrated else
                         'Sealed canister holding 10 fuel units. Ideal full-load endurance: '+('2.5' if tier==0 else '10')+' minutes before controller efficiency. Requires '+str(tier+2)+' containment rings. Upgrades retain the container; consumed fuel does not return an empty canister.')
            if not concentrated:
                description += (' Consuming Aether recovers 10 Aether Residuum per canister in standalone or Brayton mode.' if tier==0 else ' Requires Brayton mode and an advanced controller.' + (' Empyrean also requires upgraded Brayton turbines.' if tier==2 else ''))
            for key,value in {'Id/SubtypeId':subtype,'DisplayName':label,
                    'Mass':1 if concentrated else canister_mass+10*(tier+1),
                    'Volume':volume if concentrated else 24,'Description':description}.items():set_text(item,key,value)
            if not concentrated:
                for axis,dimension in zip('XYZ',(.261,.438,.261)):set_text(item,'Size/'+axis,dimension)
            set_text(item,'Icon','Textures/GUI/Icons/ArcanePower/'+subtype+'.dds')
            set_text(item,'Model','Models/Items/ArcanePower/'+subtype+'.mwm')
            items.append(item)
        voxel=copy.deepcopy(voxel_template)
        for key,value in {'Id/SubtypeId':'Arcane'+name+'Deposit','MinedOre':ore,'MinedOreRatio':mined,
                'IsRare':'true','CanBeHarvested':'true','SpawnsInAsteroids':'true','SpawnsFromMeteorites':'false',
                'MinVersion':3,'MaxVersion':2147483647,'AsteroidGeneratorSpawnProbabilityMultiplier':weight}.items():set_text(voxel,key,value)
        texture='Textures/Voxels/ArcanePower/Arcane'+name
        set_text(voxel,'VoxelHandPreview','Textures/GUI/Icons/ArcanePower/'+ore+'.dds')
        for channel,suffix in [('ColorMetal','cm'),('NormalGloss','ng'),('Ext','add')]:
            set_text(voxel,channel+'XZnY',texture+'_'+suffix+'.dds')
            set_text(voxel,channel+'XZnYFar1',texture+'_far_'+suffix+'.dds')
        voxels.append(voxel)
        # 100 kg input keeps even the lowest yield above fixed-point precision.
        recipe(refining,name+' Concentrate',[('Ore',ore,100)],concentrate,100*yield_ratio,seconds,'Ingots')
        inputs=[('Ingot',concentrate,10)]
        inputs.insert(0,('Component',canister,1) if tier==0 else ('Ingot',tiers[tier-1][3],1))
        recipe(preparing,name+' Fuel Canister',inputs,fuel,1,10*(10,30,90)[tier],'Components',whole_canister=True)
    save(items_root,MOD/'Data/PhysicalItems.sbc')
    save(recipes_root,MOD/'Data/Blueprints.sbc')
    save(voxels_root,MOD/'Data/VoxelMaterials_Arcane.sbc')

    # Native spawn weights are integers and include each material at least once.
    # Scale vanilla weights uniformly to express rare weights below vanilla's 1.
    # Keep geometry, textures, mining yields and vanilla relative weights intact.
    rarity_root=E.Element('Definitions');rarity=E.SubElement(rarity_root,'VoxelMaterials')
    for material in native.iter('VoxelMaterial'):
        if material.findtext('MinedOre')=='Stone' or material.findtext('SpawnsInAsteroids','true')!='true':continue
        adjusted=copy.deepcopy(material)
        set_text(adjusted,'AsteroidGeneratorSpawnProbabilityMultiplier',
            100*max(1,int(material.findtext('AsteroidGeneratorSpawnProbabilityMultiplier','1'))))
        rarity.append(adjusted)
    save(rarity_root,MOD/'Data/VoxelMaterials_ArcaneRarity.sbc')


def containment_tiles():
    """Regenerate all tile grades from the checked-in Standard tile geometry."""
    template=E.parse(MOD/'Data/ContainmentTiles.sbc').getroot().find('Components/Component')
    components=E.Element('Definitions');items=E.SubElement(components,'Components')
    recipes=E.Element('Definitions');blueprints=E.SubElement(recipes,'Blueprints')
    entries=E.SubElement(recipes,'BlueprintClassEntries')
    for grade,subtype,blueprint,factor in [
            ('Standard','ArcaneContainmentTile','ArcaneContainmentTiles',1),
            ('Reinforced','ArcaneReinforcedContainmentTile','ArcaneReinforcedContainmentTiles',10),
            ('Advanced','ArcaneAdvancedContainmentTile','ArcaneAdvancedContainmentTiles',100)]:
        tile=copy.deepcopy(template)
        for key,value in {'Id/SubtypeId':subtype,'DisplayName':grade+' Containment Tile',
                'Description':f'Self-controlling platinum-lined containment with superconducting coils, onboard computers and quartet sensing. Compatible with Aether, Helion and Empyrean. {factor}x Standard lifetime and crafting cost. Install in same-grade quartets; the shell holds 80 tiles. Normal shutdown retains tiles; venting discards them.'}.items():set_text(tile,key,value)
        items.append(tile)
        bp=E.SubElement(blueprints,'Blueprint')
        for key,value in {'Id/TypeId':'BlueprintDefinition','Id/SubtypeId':blueprint,
                'DisplayName':grade+' Containment Tiles','Icon':'Textures/GUI/Icons/ArcaneContainmentTile.dds',
                'BaseProductionTimeInSeconds':10*factor}.items():set_text(bp,key,value)
        pre=E.SubElement(bp,'Prerequisites')
        for kind,material,amount in [('Ingot','Iron',20),('Ingot','Cobalt',8),('Ingot','Silver',4),('Ingot','Platinum',2),
                                     ('Component','Superconductor',4),('Component','Computer',4),
                                     ('Component','Detector',1),('Component','MetalGrid',4)]:
            E.SubElement(pre,'Item',TypeId=kind,SubtypeId=material,Amount=f'{amount*factor:g}')
        E.SubElement(bp,'Result',TypeId='Component',SubtypeId=subtype,Amount='4')
        E.SubElement(entries,'Entry',Class='Components',BlueprintSubtypeId=blueprint)
    save(components,MOD/'Data/ContainmentTiles.sbc')
    save(recipes,MOD/'Data/ContainmentTileBlueprints.sbc')


def deploy():
    target=USER/'Mods/ArcanePower-Prototype'
    if target.is_symlink():
        if target.resolve() != MOD.resolve():
            raise RuntimeError('Mod link points to an unexpected directory: '+str(target.resolve()))
        # Live development link: never copy onto ourselves or rewrite source
        # definitions with deployment-only model cache paths.
        print('Live mod symlink:',target,'->',MOD.resolve())
        return
    target.mkdir(parents=True,exist_ok=True)
    # Remove our obsolete BSL so an installed Animation Engine cannot compete
    # with the direct-script controller after updating an existing local mod.
    legacy=target/'Data/Animation/main.bsl'
    if legacy.exists():legacy.unlink()
    # The old reactor remains an authoring asset, never a loadable definition.
    (target/'Data/CubeBlocks/ArcanePower_ReactorPrototype.sbc').unlink(missing_ok=True)
    copied=[]
    for p in MOD.rglob('*'):
        if p.is_file() and (p.suffix.lower() in ['.sbc','.cs','.bsl','.info','.dds','.mod'] or (p.suffix.lower()=='.mwm' and '.hkt.' not in p.name)):
            q=target/p.relative_to(MOD);q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q);copied.append(str(p.relative_to(MOD)))
    # Subparts resolve relative to their parent's MWM directory. Version the whole
    # model family so new rings/tiles refresh along with their parent after reload.
    # The copied deployment also isolates the relative subpart family.
    model_files=sorted(p for p in (target/'Models/Cubes/large').glob('*.mwm') if '_lab_' not in p.name)
    digest=hashlib.sha256(b''.join(p.name.encode()+p.read_bytes() for p in model_files)).hexdigest()[:12]
    revision_dir=Path('Models/Cubes/large')/('lab_'+digest)
    (target/revision_dir).mkdir(parents=True,exist_ok=True)
    for p in model_files:shutil.copy2(p,target/revision_dir/p.name)
    for definition in (target/'Data').rglob('*.sbc'):
        tree=E.parse(definition)
        for model in tree.getroot().iter('Model'):
            filename=model.get('File') if 'File' in model.attrib else model.text
            if not filename:continue
            relative=Path(filename.replace('\\','/'))
            if relative.parent != Path('Models/Cubes/large') or not (target/relative).is_file(): continue
            revision=revision_dir/relative.name
            if 'File' in model.attrib:model.set('File',str(revision).replace('/','\\'))
            else:model.text=str(revision).replace('/','\\')
        save(tree.getroot(),definition)
    print('Deployed',len(copied),'files to',target)


def create_world():
    if WORLD.exists():
        print('Preserving existing test world:',WORLD)
        return
    WORLD.mkdir(parents=True)
    template=GAME/'Content/CustomWorlds/Empty World'
    for name in ['SANDBOX_0_0_0_.sbs','thumb.jpg']:
        shutil.copy2(template/name,WORLD/name)
    checkpoint=E.parse(template/'Sandbox.sbc').getroot()
    for path,val in {'SessionName':'Arcane Power - Prototype Lab','WorldId':str(uuid.uuid4()),
        'Description':'Isolated Arcane Power prototype: empty space, no planets, native fuel and directly scripted reactor mechanisms.',
        'Settings/GameMode':'Survival','Settings/OnlineMode':'OFFLINE','Settings/EnableCopyPaste':'true',
        'Settings/EnableSpectator':'true','Settings/EnableResearch':'false','Settings/EnableEconomy':'false',
        'Settings/EnableEncounters':'false','Settings/CargoShipsEnabled':'false','Settings/EnableDrones':'false',
        'Settings/AutoSaveInMinutes':0}.items():set_text(checkpoint,path,val)
    mods=checkpoint.find('Mods')
    if mods is None:mods=E.SubElement(checkpoint,'Mods')
    mods.clear()
    m=E.SubElement(mods,'ModItem',FriendlyName='Arcane Power Prototype');set_text(m,'Name','ArcanePower-Prototype');set_text(m,'PublishedFileId','0');set_text(m,'PublishedServiceName','Steam')
    save(checkpoint,WORLD/'Sandbox.sbc')
    print('Created empty survival world:',WORLD)


if __name__=='__main__':
    definitions();deploy();create_world()
