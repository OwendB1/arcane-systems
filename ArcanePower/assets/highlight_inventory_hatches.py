"""Export native hatch sections and point conveyor highlights at those sections."""
import bpy

s=bpy.data.scenes['ArcanePower_ReactorPrototype']
targets={
    'detector_conveyor_0':'Inventory access / side 0',
    'detector_conveyor_2':'Inventory access / side 2',
    'detector_conveyor_top':'Axial conveyor / top / Conveyor Access LG',
    'detector_conveyor_bottom':'Axial conveyor / bottom / Conveyor Access LG',
}
for name,target in targets.items():
    detector=s.objects[name]
    if name=='detector_conveyor_top' and 'subpart_VentHatch4' in s.objects:
        leaves=[s.objects['subpart_VentHatch'+str(i+1)] for i in range(4)]
        detector['highlight']=';'.join(o.name for o in leaves)
        detector.seut.highlight_objects.clear()
        for leaf in leaves:detector.seut.highlight_objects.add().obj=leaf
        continue
    # MWMBuilder only emits mesh sections for names containing "_section".
    # A highlight property alone leaves an unresolved name in the compiled MWM.
    section_name=target+'_section'
    hatch=s.objects.get(section_name)
    if hatch is None:
        hatch=s.objects[target]
        hatch.name=section_name
    detector['highlight']=hatch.name
    detector.seut.highlight_objects.clear()
    detector.seut.highlight_objects.add().obj=hatch
    detector['purpose']='Native conveyor/inventory interaction; highlight the access hatch mesh'
bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
print('Four inventory hatches named for MWM section export and linked to conveyor highlights')
