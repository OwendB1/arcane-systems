"""Export native hatch sections and point conveyor highlights at those sections."""
import bpy
import re

TARGETS={
    'detector_conveyor_0':'Inventory access / side 0',
    'detector_conveyor_2':'Inventory access / side 2',
    'detector_conveyor_top':'Axial conveyor / top / Conveyor Access LG',
    'detector_conveyor_bottom':'Axial conveyor / bottom / Conveyor Access LG',
}

def remap_highlights(copies, native=False):
    """Keep cloned detectors linked to their own hatch meshes and subparts."""
    for source, target in copies.items():
        if source.type != 'EMPTY' or 'highlight' not in source:
            continue
        refs=[entry.obj for entry in source.seut.highlight_objects]
        assert refs and all(ref in copies for ref in refs), ('Highlight target not copied', source.name)
        refs=[copies[ref] for ref in refs]
        target.seut.highlight_objects.clear()
        if not native:
            for ref in refs:target.seut.highlight_objects.add().obj=ref
        # SEUT strips duplicate suffixes from empties during export. Mesh names
        # retain theirs, and MWM section names must match those names exactly.
        # Write native strings after all copies exist, rather than letting SEUT
        # serialize a subpart reference before that subpart has been renamed.
        target['highlight']=';'.join(re.sub(r'\.\d{3}$', '', ref.name)
            if native and ref.type=='EMPTY' else ref.name for ref in refs)


def apply(s):
    for name,target in TARGETS.items():
        detector=s.objects[name]
        if name=='detector_conveyor_top' and 'subpart_VentHatch4' in s.objects:
            leaves=[s.objects['subpart_VentHatch'+str(i+1)] for i in range(4)]
            detector['highlight']=';'.join(o.name for o in leaves)
            detector.seut.highlight_objects.clear()
            for leaf in leaves:detector.seut.highlight_objects.add().obj=leaf
            continue
        # MWMBuilder only emits mesh sections for names containing "_section".
        section_name=target+'_section'
        hatch=s.objects.get(section_name)
        if hatch is None:
            hatch=s.objects[target]
            hatch.name=section_name
        detector['highlight']=hatch.name
        detector.seut.highlight_objects.clear()
        detector.seut.highlight_objects.add().obj=hatch
        detector['purpose']='Native conveyor/inventory interaction; highlight the access hatch mesh'


if __name__ == '__main__':
    apply(bpy.data.scenes['ArcanePower_ReactorPrototype'])
    bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
    print('Four inventory hatches named for MWM section export and linked to conveyor highlights')
