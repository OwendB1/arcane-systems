"""Build SE1 definition-based prototype and an isolated empty survival test world."""
import copy
import hashlib
import json
import math
import shutil
import uuid
import xml.etree.ElementTree as E
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GAME = Path.home()/'.local/share/Steam/steamapps/common/SpaceEngineers'
USER = Path.home()/'.config/SpaceEngineers'
MOD = ROOT/'src'
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


def definitions():
    energy = E.parse(GAME/'Content/Data/CubeBlocks/CubeBlocks_Energy.sbc').getroot()
    reactor = copy.deepcopy(next(n for n in energy.iter('Definition') if n.findtext('Id/SubtypeId')=='LargeBlockSmallGenerator'))
    for key,value in {'Id/SubtypeId':'ArcanePower_ReactorPrototype', 'DisplayName':'Arcane Power Reactor — Prototype',
        'Description':'Arcane Fuel I: 10 GW with two rings. Fuel II: 100 GW with three rings. Fuel III: 1 TW with four rings. Two containment controllers required. Venting ejects containment through the conveyor-connected top hatch, damages the reactor/modules, and leaves the reactor off.',
        'Model':'Models/Cubes/large/ArcanePower_ReactorPrototype.mwm', 'BlockPairName':'ArcanePower_ReactorPrototype',
        'MaxPowerOutput':10000, 'FuelProductionToCapacityMultiplier':3600, 'PCU':100,
        'IsAirTight':'false','InventorySize/X':2,'InventorySize/Y':2,'InventorySize/Z':2,
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
    root=E.Element('Definitions'); blocks=E.SubElement(root,'CubeBlocks');blocks.append(reactor)
    save(root,MOD/'Data/CubeBlocks/ArcanePower_ReactorPrototype.sbc')

    production=E.parse(GAME/'Content/Data/CubeBlocks/CubeBlocks_Production.sbc').getroot()
    module=copy.deepcopy(next(n for n in production.iter('Definition') if n.findtext('Id/SubtypeId')=='LargeProductivityModule'))
    for path,val in {'Id/SubtypeId':'ArcanePower_ContainmentController','DisplayName':'Arcane Containment Controller',
        'Description':'Attach directly to either reactor side socket. Two working controllers are required for fuel tier I.',
        'Model':'Models/Cubes/large/ArcanePower_ContainmentController.mwm','BlockPairName':'ArcanePower_ContainmentController',
        'Upgrades/MyUpgradeModuleInfo/UpgradeType':'ArcaneContainment','Upgrades/MyUpgradeModuleInfo/Modifier':1}.items():set_text(module,path,val)
    module.find('Size').attrib.update(x='1',y='1',z='1')
    for tag in ['BuildProgressModels','MountPoints','MirroringX','MirroringY','MirroringZ']:
        for n in list(module.findall(tag)):module.remove(n)
    mount=E.SubElement(module,'MountPoints')
    for side in ['Front','Back','Left','Right','Top','Bottom']:
        E.SubElement(mount,'MountPoint',Side=side,StartX='0',StartY='0',EndX='1',EndY='1')
    root=E.Element('Definitions');E.SubElement(root,'CubeBlocks').append(module)
    count=copy.deepcopy(module.find('Upgrades/MyUpgradeModuleInfo'))
    set_text(count,'UpgradeType','ArcaneControllerCount')
    module.find('Upgrades').append(count)
    advanced=copy.deepcopy(module)
    for path,val in {'Id/SubtypeId':'ArcanePower_AdvancedContainmentController',
        'DisplayName':'Arcane Advanced Containment Controller',
        'BlockPairName':'ArcanePower_AdvancedContainmentController',
        'Description':'One standard plus one advanced controller permits Fuel II and three rings; two advanced controllers permit Fuel III and four rings.',
        'Upgrades/MyUpgradeModuleInfo/Modifier':2}.items():set_text(advanced,path,val)
    root.find('CubeBlocks').append(advanced)
    save(root,MOD/'Data/CubeBlocks/ArcanePower_ContainmentController.sbc')

    physical=E.parse(GAME/'Content/Data/PhysicalItems.sbc').getroot()
    root=E.Element('Definitions'); items=E.SubElement(root,'PhysicalItems')
    for kind,subtype,label in [('Ore','ArcaneOre','Arcane Ore — Prototype'),
            ('Ingot','ArcaneFuelI','Arcane Fuel I — 10 GW'),('Ingot','ArcaneFuelII','Arcane Fuel II — 100 GW'),
            ('Ingot','ArcaneFuelIII','Arcane Fuel III — 1 TW')]:
        n=copy.deepcopy(next(n for n in physical.iter('PhysicalItem') if n.findtext('Id/TypeId')==kind and n.findtext('Id/SubtypeId')=='Uranium'))
        set_text(n,'Id/SubtypeId',subtype);set_text(n,'DisplayName',label)
        for child in list(n):
            if child.tag.startswith(('Minimum','Maximum','CanPlayer')) or child.tag=='IconSymbol': n.remove(child)
        items.append(n)
    save(root,MOD/'Data/PhysicalItems.sbc')
    root=E.Element('Definitions'); blueprints=E.SubElement(root,'Blueprints');bp=E.SubElement(blueprints,'Blueprint')
    for path,val in {'Id/TypeId':'BlueprintDefinition','Id/SubtypeId':'ArcaneOreToFuelI',
        'DisplayName':'Arcane Fuel I','Icon':'Textures/GUI/Icons/ingot/uranium_ingot.dds',
        'BaseProductionTimeInSeconds':4}.items():set_text(bp,path,val)
    E.SubElement(E.SubElement(bp,'Prerequisites'),'Item',Amount='1',TypeId='Ore',SubtypeId='ArcaneOre')
    E.SubElement(bp,'Result',Amount='0.01',TypeId='Ingot',SubtypeId='ArcaneFuelI')
    E.SubElement(E.SubElement(root,'BlueprintClassEntries'),'Entry',Class='Ingots',BlueprintSubtypeId='ArcaneOreToFuelI')
    for previous,current,seconds in [('I','II',12),('II','III',24)]:
        bp=E.SubElement(blueprints,'Blueprint')
        subtype='ArcaneFuel'+previous+'To'+current
        for path,val in {'Id/TypeId':'BlueprintDefinition','Id/SubtypeId':subtype,
                'DisplayName':'Arcane Fuel '+current,'Icon':'Textures/GUI/Icons/ingot/uranium_ingot.dds',
                'BaseProductionTimeInSeconds':seconds}.items():set_text(bp,path,val)
        E.SubElement(E.SubElement(bp,'Prerequisites'),'Item',Amount='1',TypeId='Ingot',SubtypeId='ArcaneFuel'+previous)
        E.SubElement(bp,'Result',Amount='0.1',TypeId='Ingot',SubtypeId='ArcaneFuel'+current)
        E.SubElement(root.find('BlueprintClassEntries'),'Entry',Class='Ingots',BlueprintSubtypeId=subtype)
    save(root,MOD/'Data/Blueprints.sbc')
    root=E.Element('Definitions');cat=E.SubElement(E.SubElement(root,'CategoryClasses'),'Category',{'{'+XSI+'}type':'MyObjectBuilder_GuiBlockCategoryDefinition'})
    set_text(cat,'Id/TypeId','GuiBlockCategoryDefinition');set_text(cat,'Id/SubtypeId','ArcanePower')
    set_text(cat,'DisplayName','Arcane Power');set_text(cat,'Name','Arcane Power')
    set_text(cat,'ItemIds/string','ArcanePower_ReactorPrototype')
    E.SubElement(cat.find('ItemIds'),'string').text='ArcanePower_ContainmentController'
    E.SubElement(cat.find('ItemIds'),'string').text='ArcanePower_AdvancedContainmentController'
    save(root,MOD/'Data/BlockCategories.sbc')
    external_hardware_definitions()
    (MOD/'metadata.mod').write_text('<?xml version="1.0"?><ModMetadata><Name>Arcane Power — Prototype</Name><Version>0.1</Version></ModMetadata>\n')


def external_hardware_definitions():
    logistics=E.parse(GAME/'Content/Data/CubeBlocks/CubeBlocks_Logistics.sbc').getroot()
    template=next(n for n in logistics.iter('Definition') if n.findtext('Id/SubtypeId')=='LargeBlockConveyor')
    root=E.Element('Definitions');blocks=E.SubElement(root,'CubeBlocks')
    for subtype,label in [('ArcanePower_VentDuct','Arcane Vent Duct'),('ArcanePower_VentOutlet','Arcane Vent Outlet')]:
        n=copy.deepcopy(template)
        for path,value in {'Id/SubtypeId':subtype,'DisplayName':label,'Description':'Stack matching vent sections above the reactor and finish with an Arcane Vent Outlet. The outlet opens during venting. Central connections also carry conveyor items.',
                'Model':'Models/Cubes/large/'+subtype+'.mwm','Icon':'Textures/GUI/Icons/'+('ArcaneVentOutlet' if subtype.endswith('Outlet') else 'ArcaneVentDuct')+'.dds','BlockPairName':subtype,'IsAirTight':'false','GuiVisible':'true','PCU':25,'BuildTimeSeconds':30}.items():set_text(n,path,value)
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
        blocks.append(n)
    save(root,MOD/'Data/CubeBlocks/ArcanePower_Vents.sbc')
    p=MOD/'Data/CubeBlocks/ArcanePower_ContainmentController.sbc';r=E.parse(p).getroot()
    for n in r.iter('Definition'):
        subtype=n.findtext('Id/SubtypeId')
        set_text(n,'Model','Models/Cubes/large/'+subtype+'.mwm')
        set_text(n,'Icon','Textures/GUI/Icons/'+('ArcaneAdvancedContainmentController' if 'Advanced' in subtype else 'ArcaneContainmentController')+'.dds')
    save(r,p)
    p=MOD/'Data/BlockCategories.sbc';r=E.parse(p).getroot();ids=next(r.iter('ItemIds'))
    for subtype in ('ArcanePower_VentDuct','ArcanePower_VentOutlet'):
        if not any(n.text==subtype for n in ids):E.SubElement(ids,'string').text=subtype
    save(r,p)
    components=E.parse(GAME/'Content/Data/Components.sbc').getroot()
    tile=copy.deepcopy(next(n for n in components.iter('Component') if n.findtext('Id/SubtypeId')=='Construction'))
    for key,value in {'Id/SubtypeId':'ArcaneContainmentTile','DisplayName':'Arcane Containment Tile',
            'Icon':'Textures/GUI/Icons/ArcaneContainmentTile.dds','Description':'Replaceable triangular containment cartridge. Eighty installed tiles form a shell; four-tile maintenance batches wear with fuel tier, load and heat. Normal shutdown retains installed tiles; venting discards them.',
            'Model':'Models/Cubes/large/ArcanePower_ContainmentTile.mwm','Size/X':.54,'Size/Y':.40,'Size/Z':.045,
            'Mass':1,'Volume':2,'MaxIntegrity':30}.items():set_text(tile,key,value)
    for child in list(tile):
        if child.tag.startswith(('Minimum','Maximum','CanPlayer')):tile.remove(child)
    root=E.Element('Definitions');E.SubElement(root,'Components').append(tile);save(root,MOD/'Data/ContainmentTiles.sbc')
    root=E.Element('Definitions');bp=E.SubElement(E.SubElement(root,'Blueprints'),'Blueprint')
    for key,value in {'Id/TypeId':'BlueprintDefinition','Id/SubtypeId':'ArcaneContainmentTiles','DisplayName':'Arcane Containment Tiles',
            'Icon':'Textures/GUI/Icons/ArcaneContainmentTile.dds','BaseProductionTimeInSeconds':10}.items():set_text(bp,key,value)
    pre=E.SubElement(bp,'Prerequisites')
    for subtype,amount in [('Iron','2'),('Nickel','.1'),('Silicon','.2')]:E.SubElement(pre,'Item',TypeId='Ingot',SubtypeId=subtype,Amount=amount)
    E.SubElement(bp,'Result',TypeId='Component',SubtypeId='ArcaneContainmentTile',Amount='4')
    E.SubElement(E.SubElement(root,'BlueprintClassEntries'),'Entry',Class='Components',BlueprintSubtypeId='ArcaneContainmentTiles')
    save(root,MOD/'Data/ContainmentTileBlueprints.sbc')


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
    copied=[]
    for p in MOD.rglob('*'):
        if p.is_file() and (p.suffix.lower() in ['.sbc','.cs','.bsl','.info','.dds','.mod'] or (p.suffix.lower()=='.mwm' and '.hkt.' not in p.name)):
            q=target/p.relative_to(MOD);q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q);copied.append(str(p.relative_to(MOD)))
    # Subparts resolve relative to their parent's MWM directory. Version the whole
    # model family so new rings/tiles refresh along with their parent after reload.
    # Only the local deployment changes; distributable definitions keep stable paths.
    model_files=sorted(p for p in (target/'Models/Cubes/large').glob('*.mwm') if '_lab_' not in p.name)
    digest=hashlib.sha256(b''.join(p.name.encode()+p.read_bytes() for p in model_files)).hexdigest()[:12]
    revision_dir=Path('Models/Cubes/large')/('lab_'+digest)
    (target/revision_dir).mkdir(parents=True,exist_ok=True)
    for p in model_files:shutil.copy2(p,target/revision_dir/p.name)
    for definition in (target/'Data').rglob('*.sbc'):
        tree=E.parse(definition)
        for model in tree.getroot().iter('Model'):
            relative=Path(model.text.replace('\\','/'))
            if relative.parent != Path('Models/Cubes/large') or not (target/relative).is_file(): continue
            revision=revision_dir/relative.name
            model.text=str(revision).replace('/','\\')
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
