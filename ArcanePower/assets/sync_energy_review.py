"""Refresh main-model review copies from evaluated source transforms.

Run in the live review file after editing main geometry. Assembly placement is
read from an unchanged drum/spine, never from an inactive scene's cached matrix.
Subpart poses, the comparison reactor and review lighting remain intact.
"""
import importlib

import bpy
from mathutils import Vector

COLS = importlib.import_module('space-engineers-utilities.seut_collections')


def activate(scene):
    bpy.context.window.scene = scene
    bpy.context.view_layer.update()


def refresh(source_names=None):
    original = bpy.context.scene
    report = {}
    reviews = [s for s in bpy.data.scenes if s.name.startswith('Battery /')]
    try:
        for source in bpy.data.scenes:
            if not source.name.startswith('ArcanePower_Energy') or source.seut.sceneType != 'mainScene':
                continue
            if source_names is not None and source.name not in source_names:
                continue
            activate(source)
            main = COLS.get_collections(source)['main'][0]
            meshes = [o for o in main.objects if o.type == 'MESH']
            prefix = 'Energy / machinery drum' if source.name.endswith('Core') else 'Module / front spine'
            marker = next(o for o in meshes if o.name.startswith(prefix))
            inverse = marker.matrix_world.inverted()
            matrices = {o: o.matrix_world.copy() for o in meshes}
            mesh_data = {o.data for o in meshes}
            for review in reviews:
                activate(review)
                poses = []
                copies=[o for o in review.objects if o.get('review_scene')==source.name and o.get('review_source','').startswith(prefix)]
                if copies:
                    # Suffixes can be reassigned when an older review is
                    # appended. Even an exact name match may then identify the
                    # opposite spine/bay. Always use the full tagged marker set.
                    markers=[o for o in meshes if o.name.startswith(prefix)]
                    for index in sorted({o.get('review_instance',0) for o in copies}):
                        group=[o for o in copies if o.get('review_instance',0)==index]
                        assert len(group)==len(markers),(review.name,source.name,'incomplete pose markers')
                        pose=(group[0].matrix_world.to_3x3() @ matrices[marker].to_3x3().inverted()).to_4x4()
                        centre=sum((matrices[o].translation for o in markers),Vector())/len(markers)
                        pose.translation=sum((o.matrix_world.translation for o in group),Vector())/len(group)-pose.to_3x3() @ centre
                        poses.append(pose)
                else:
                    poses = [o.matrix_world.copy() @ inverse for o in review.objects
                             if o.type == 'MESH' and o.data == marker.data]
                if not poses:
                    continue
                # Each complete assembly has exactly one copy of this marker.
                for o in list(review.objects):
                    if o.type == 'MESH' and (o.data in mesh_data or o.get('review_scene') == source.name):
                        bpy.data.objects.remove(o, do_unlink=True)
                for index, pose in enumerate(poses):
                    copies = {}
                    for obj in meshes:
                        copy = obj.copy()
                        copy.name = 'Review / ' + obj.name
                        copy.parent = None
                        review.collection.objects.link(copy)
                        copy.matrix_world = pose @ matrices[obj]
                        copy['review_source'] = obj.name
                        copy['review_scene'] = source.name
                        copy['review_instance'] = index
                        copies[obj.name] = copy
                    for copy in copies.values():
                        if 'fastener_body' in copy:
                            copy['fastener_body'] = copies[copy['fastener_body']].name
                    bpy.context.view_layer.update()
                    error = max(abs(copy.matrix_world[i][j] - (pose @ matrices[obj])[i][j])
                                for obj in meshes for copy in [copies[obj.name]]
                                for i in range(4) for j in range(4))
                    assert error < 1e-5, (review.name, source.name, error)
                report[review.name + ' / ' + source.name] = {
                    'instances': len(poses), 'meshes_each': len(meshes),
                    'max_matrix_error': error,
                }
        return report
    finally:
        activate(original)


def audit():
    """Also run after reload: every review part must retain its assembly pose."""
    original = bpy.context.scene
    report = {}
    try:
        for source in bpy.data.scenes:
            if not source.name.startswith('ArcanePower_Energy') or source.seut.sceneType != 'mainScene':
                continue
            activate(source)
            meshes = {o.name: o for o in COLS.get_collections(source)['main'][0].objects if o.type == 'MESH'}
            matrices = {name: obj.matrix_world.copy() for name, obj in meshes.items()}
            prefix = 'Energy / machinery drum' if source.name.endswith('Core') else 'Module / front spine'
            marker = next(name for name in meshes if name.startswith(prefix))
            for review in [s for s in bpy.data.scenes if s.name.startswith('Battery /')]:
                activate(review)
                copies = [o for o in review.objects if o.get('review_scene') == source.name]
                for index in {o['review_instance'] for o in copies}:
                    group = {o['review_source']: o for o in copies if o['review_instance'] == index}
                    assert group.keys() == meshes.keys(), (review.name, source.name, 'incomplete assembly')
                    pose = group[marker].matrix_world @ matrices[marker].inverted()
                    error = max(abs(copy.matrix_world[i][j] - (pose @ matrices[name])[i][j])
                                for name, copy in group.items() for i in range(4) for j in range(4))
                    assert error < 2e-5, (review.name, source.name, 'offset mismatch', error)
                    for name, copy in group.items():
                        if 'fastener_body' in meshes[name]:
                            assert copy['fastener_body'] == group[meshes[name]['fastener_body']].name
                    report[review.name + ' / ' + source.name + ' / ' + str(index)] = error
        return report
    finally:
        activate(original)


if __name__ == '__main__':
    result = {'review_placements': refresh(), 'audit': audit()}
