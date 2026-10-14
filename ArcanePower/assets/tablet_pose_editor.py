"""Blender visual grip editor, launched by tools/tablet_pose_editor.py."""
import json
import math
from pathlib import Path
import sys
import tempfile
import subprocess
import shutil

import bpy
from mathutils import Matrix, Quaternion, Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "assets"))
from tablet_pose_data import MODES, read_poses, export_poses, same
from tablet_fingers import FINGERS, JOINTS, SOURCE, MODEL, DEFINITION, ANIMATION, validate_fingers, finger_source, export_grip, fingers_same

# All native meshes and transforms use SE coordinates. Apply one common proper
# rotation for Blender's Z-up viewport; never flip or compensate individual wrists.
C = Matrix.Rotation(math.pi / 2, 4, "X")
CI = C.inverted()
SCENE = "Tablet grip editor"
BASELINE = None
REFERENCE = None
FINGER_BASELINE = None
FINGER_SOURCE = None


def native_matrix(position, orientation):
    x, y, z, w = orientation
    result = Quaternion((w, x, y, z)).normalized().to_matrix().to_4x4()
    result.translation = Vector(position)
    return C @ result @ CI


def values(matrix):
    native = CI @ matrix @ C
    if any(abs(v - 1) > 1e-5 for v in native.to_scale()) or native.to_3x3().determinant() < 0:
        raise ValueError("Targets must have unit scale. Use Move and Rotate, not Scale.")
    q = native.to_quaternion().normalized()
    return list(native.translation), [q.x, q.y, q.z, q.w]


def target(name):
    return bpy.data.objects["Grip / " + name]


def current_poses(scene):
    result = json.loads(scene["poses"])
    position, orientation = MODES[scene.tablet_pose.mode]
    result[position], result[orientation] = values(target("Tablet").matrix_basis)
    for side in ("Left", "Right"):
        result[side + "HandPosition"], result[side + "HandOrientation"] = values(target(side).matrix_basis)
    return result


def select(name):
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    obj = target(name)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def switch_mode(self, context):
    scene = context.scene
    poses = json.loads(scene["poses"])
    old_position, old_orientation = MODES[scene["previous_mode"]]
    poses[old_position], poses[old_orientation] = values(target("Tablet").matrix_basis)
    scene["poses"] = json.dumps(poses)
    scene["previous_mode"] = self.mode
    position, orientation = MODES[self.mode]
    target("Tablet").matrix_basis = native_matrix(poses[position], poses[orientation])


class TabletPoseSettings(bpy.types.PropertyGroup):
    mode: bpy.props.EnumProperty(name="Item pose", items=[(k, k, "") for k in MODES], update=switch_mode)
    side: bpy.props.EnumProperty(name="Hand", items=[("Left", "Left", ""), ("Right", "Right", "")])
    finger: bpy.props.EnumProperty(name="Finger", items=[(k, k, "") for k in FINGERS])
    joint: bpy.props.EnumProperty(name="Joint", items=[("1", "Base", ""), ("2", "Middle", ""), ("3", "Tip", "")])


class TABLET_OT_joint(bpy.types.Operator):
    bl_idname = "tablet_pose.joint"
    bl_label = "Edit finger joint"
    bl_description = "Select this joint in Pose Mode; G moves, R rotates"

    def execute(self, context):
        settings = context.scene.tablet_pose
        select(settings.side)
        target(settings.side).select_set(False)
        rig = hand_rig(settings.side)
        rig.select_set(True)
        context.view_layer.objects.active = rig
        name = f"SE_Rig{settings.side[0]}_{settings.finger}_{settings.joint}"
        for pose in rig.pose.bones:
            selection = pose if hasattr(pose, "select") else pose.bone
            selection.select = pose.name == name
        rig.data.bones.active = rig.data.bones[name]
        bpy.ops.object.mode_set(mode="POSE")
        return {"FINISHED"}


class TABLET_OT_select(bpy.types.Operator):
    bl_idname = "tablet_pose.select"
    bl_label = "Select transform"
    side: bpy.props.StringProperty()

    def execute(self, context):
        select(self.side)
        return {"FINISHED"}


class TABLET_OT_reload(bpy.types.Operator):
    bl_idname = "tablet_pose.reload"
    bl_label = "Reload definitions (discard edits)"
    bl_description = "Discard unsaved wrist/item and finger edits; load the current definitions and finger source"

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        global BASELINE, FINGER_BASELINE, FINGER_SOURCE
        BASELINE = read_poses(ROOT / "src/Data/Tablet.sbc")
        FINGER_SOURCE = finger_source(ROOT)
        load_fingers(read_fingers())
        FINGER_BASELINE = current_fingers()
        load_targets(context.scene, BASELINE)
        return {"FINISHED"}


class TABLET_OT_mirror(bpy.types.Operator):
    bl_idname = "tablet_pose.mirror"
    bl_label = "Mirror right wrist to left"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        # The two native palm bones have different bind bases. Reflect in item
        # space and compensate that basis, rather than guessing an extra wrist turn.
        basis = Matrix(REFERENCE["mirrorRightToLeft"]).transposed().to_4x4().inverted()
        right = CI @ target("Right").matrix_basis @ C
        left = Matrix.Diagonal((-1, 1, 1, 1)) @ right @ basis
        target("Left").matrix_basis = C @ left @ CI
        select("Left")
        return {"FINISHED"}


class TABLET_OT_copy_modes(bpy.types.Operator):
    bl_idname = "tablet_pose.copy_modes"
    bl_label = "Copy item pose to all eight modes"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        poses = current_poses(context.scene)
        position, orientation = values(target("Tablet").matrix_basis)
        for p, q in MODES.values():
            poses[p], poses[q] = position, orientation
        context.scene["poses"] = json.dumps(poses)
        return {"FINISHED"}


class TABLET_OT_export(bpy.types.Operator):
    bl_idname = "tablet_pose.export"
    bl_label = "Export edited transforms to mod"
    bl_description = "Export wrist/item transforms and edited finger joints as a native tablet grip animation"

    def execute(self, context):
        global BASELINE, FINGER_BASELINE, FINGER_SOURCE
        try:
            BASELINE, changed, FINGER_BASELINE, count = export_grip(
                ROOT, BASELINE, current_poses(context.scene), FINGER_BASELINE,
                FINGER_SOURCE, current_fingers(), REFERENCE["authoring"])
            FINGER_SOURCE = finger_source(ROOT)
            context.scene["poses"] = json.dumps(BASELINE)
            self.report({"INFO"}, f"Exported {len(changed)} wrist/item transforms and {count} finger joints. Reload the SE world to apply.")
        except (ValueError, OSError) as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        return {"FINISHED"}


class TABLET_PT_editor(bpy.types.Panel):
    bl_label = "Tablet hand poses"
    bl_idname = "TABLET_PT_editor"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Tablet"

    def draw(self, context):
        layout = self.layout
        layout.prop(context.scene.tablet_pose, "mode")
        if context.scene.tablet_pose.mode.startswith("Ironsight"):
            layout.label(text="SE shares the ironsight pose between views.")
        row = layout.row(align=True)
        for side in ("Left", "Right", "Tablet"):
            row.operator("tablet_pose.select", text=side).side = side
        layout.label(text="G: move   R: rotate   Ctrl+Z: undo")
        layout.label(text="Use Local axes to adjust wrist twist.")
        obj = context.active_object
        if obj and obj.name in {"Grip / Left", "Grip / Right", "Grip / Tablet"}:
            layout.prop(obj, "location", text="Position (Blender)")
            layout.prop(obj, "rotation_euler", text="Rotation")
            try:
                p, q = values(obj.matrix_basis)
                layout.label(text="SE position: " + ", ".join(format(v, ".4f") for v in p))
            except ValueError as error:
                layout.label(text=str(error), icon="ERROR")
        layout.operator("tablet_pose.mirror")
        layout.operator("tablet_pose.copy_modes")
        layout.separator()
        settings = context.scene.tablet_pose
        layout.prop(settings, "side")
        layout.prop(settings, "finger")
        layout.prop(settings, "joint")
        layout.operator("tablet_pose.joint", icon="BONE_DATA")
        bone = context.active_pose_bone
        if bone and bone.name in JOINTS:
            layout.label(text=bone.name)
            layout.prop(bone, "location", text="Joint offset (Blender)")
            layout.prop(bone, "rotation_euler", text="Joint rotation")
        layout.label(text="Finger joints: G / R in Pose Mode")
        layout.separator()
        layout.operator("tablet_pose.reload")
        layout.operator("tablet_pose.export", icon="EXPORT")
        layout.label(text="Native male astronaut / editable finger rig")
        layout.label(text="Finger grip applies to all eight item poses.")
        layout.label(text="Preview grips; final arm IK is evaluated in SE.")


CLASSES = (TabletPoseSettings, TABLET_OT_select, TABLET_OT_joint, TABLET_OT_reload, TABLET_OT_mirror,
           TABLET_OT_copy_modes, TABLET_OT_export, TABLET_PT_editor)


def mesh(name, data, parent, colour, vertices="vertices"):
    geometry = bpy.data.meshes.new(name)
    geometry.from_pydata([C.to_3x3() @ Vector(p) for p in data[vertices]], [], data["triangles"])
    geometry.update()
    obj = bpy.data.objects.new(name, geometry)
    bpy.context.scene.collection.objects.link(obj)
    obj.parent = parent
    material = bpy.data.materials.new(name)
    material.diffuse_color = colour
    geometry.materials.append(material)
    for polygon in geometry.polygons:
        polygon.use_smooth = True
    obj.hide_select = True
    return obj


def hand_rig(side):
    return bpy.data.objects[side + " finger rig"]


def reference_matrix(rows):
    return C @ Matrix(rows).transposed() @ CI


def create_hand(side, data, parent, colour):
    armature = bpy.data.armatures.new(side + " fingers")
    rig = bpy.data.objects.new(side + " finger rig", armature)
    bpy.context.scene.collection.objects.link(rig)
    rig.parent = parent
    rig.show_in_front = True
    rig.lock_location = rig.lock_rotation = rig.lock_scale = (True, True, True)
    armature.display_type = "STICK"
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    for source in data["bones"]:
        bone = armature.edit_bones.new(source["name"])
        matrix = reference_matrix(source["bind"])
        # Native bind matrices have tiny floating-point scale errors. Blender
        # bones are rigid; preserve translation and normalized rotation.
        rigid = matrix.to_quaternion().normalized().to_matrix().to_4x4()
        rigid.translation = matrix.translation
        bone.length = .025
        bone.matrix = rigid
    for source in data["bones"]:
        if source["parent"]:
            armature.edit_bones[source["name"]].parent = armature.edit_bones[source["parent"]]
    bpy.ops.object.mode_set(mode="OBJECT")
    rig.select_set(False)
    for bone in armature.bones:
        bone.hide_select = bone.name not in JOINTS
        bone.hide = bone.name not in JOINTS
        pose = rig.pose.bones[bone.name]
        pose.rotation_mode = "XYZ"
        pose.lock_scale = (True, True, True)
    obj = mesh(side + " astronaut glove", data, parent, colour, "restVertices")
    for source in data["bones"]:
        obj.vertex_groups.new(name=source["name"])
    for index, weights in enumerate(data["weights"]):
        for name, weight in weights.items():
            obj.vertex_groups[name].add([index], weight, "REPLACE")
    modifier = obj.modifiers.new("Native finger skinning", "ARMATURE")
    modifier.object = rig
    return rig


def native_fingers():
    result = {}
    for side in ("left", "right"):
        bones = {b["name"]: b for b in REFERENCE[side]["bones"]}
        for name in JOINTS:
            if name in bones:
                bone = bones[name]
                local = reference_matrix(bones[bone["parent"]]["pose"]).inverted() @ reference_matrix(bone["pose"])
                p, q = values(local)
                result[name] = {"position": p, "orientation": q}
    return validate_fingers(result)


def read_fingers():
    source = finger_source(ROOT)
    return validate_fingers(json.loads(source)) if source is not None else native_fingers()


def load_fingers(poses):
    poses = validate_fingers(poses)
    for side in ("Left", "Right"):
        rig = hand_rig(side)
        matrices = {}
        sources = {b["name"]: b for b in REFERENCE[side.lower()]["bones"]}
        def visit(name):
            if name in matrices:
                return matrices[name]
            source = sources[name]
            if name in poses:
                parent = visit(source["parent"])
                value = poses[name]
                matrix = parent @ native_matrix(value["position"], value["orientation"])
            else:
                matrix = reference_matrix(source["pose"])
            matrices[name] = matrix
            return matrix
        for name in sources:
            desired = visit(name)
            bone = rig.data.bones[name]
            if bone.parent:
                basis = bone.convert_local_to_pose(desired, bone.matrix_local,
                    parent_matrix=visit(bone.parent.name), parent_matrix_local=bone.parent.matrix_local, invert=True)
            else:
                basis = bone.convert_local_to_pose(desired, bone.matrix_local, invert=True)
            rig.pose.bones[name].matrix_basis = basis
    bpy.context.view_layer.update()


def current_fingers():
    bpy.context.view_layer.update()
    result = {}
    for side in ("Left", "Right"):
        for bone in hand_rig(side).pose.bones:
            if bone.name in JOINTS:
                p, q = values(bone.parent.matrix.inverted() @ bone.matrix)
                result[bone.name] = {"position": p, "orientation": q}
    return validate_fingers(result)


def empty(name, parent=None):
    obj = bpy.data.objects.new("Grip / " + name, None)
    bpy.context.scene.collection.objects.link(obj)
    obj.empty_display_type = "ARROWS"
    obj.empty_display_size = .065
    obj.show_in_front = True
    obj.rotation_mode = "XYZ"
    obj.lock_scale = (True, True, True)
    obj.parent = parent
    return obj


def load_targets(scene, poses):
    scene["poses"] = json.dumps(poses)
    scene["previous_mode"] = scene.tablet_pose.mode
    p, q = MODES[scene.tablet_pose.mode]
    target("Tablet").matrix_basis = native_matrix(poses[p], poses[q])
    for side in ("Left", "Right"):
        target(side).matrix_basis = native_matrix(poses[side + "HandPosition"], poses[side + "HandOrientation"])


def setup(reference):
    global BASELINE, REFERENCE, FINGER_BASELINE, FINGER_SOURCE
    REFERENCE = reference
    BASELINE = read_poses(ROOT / "src/Data/Tablet.sbc")
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.tablet_pose = bpy.props.PointerProperty(type=TabletPoseSettings)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    scene = bpy.context.scene
    scene.name = SCENE
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.length_unit = "METERS"
    scene.transform_orientation_slots[0].type = "LOCAL"
    item = empty("Tablet")
    left, right = empty("Left", item), empty("Right", item)
    mesh("Native tablet", reference["tablet"], item, (.08, .16, .20, 1))
    create_hand("Left", reference["left"], left, (.28, .55, .8, 1))
    create_hand("Right", reference["right"], right, (.9, .48, .15, 1))
    FINGER_SOURCE = finger_source(ROOT)
    load_fingers(read_fingers())
    FINGER_BASELINE = current_fingers()
    head = empty("Head reference")
    head.empty_display_size = .12
    head.hide_select = True
    load_targets(scene, BASELINE)
    select("Left")
    bpy.context.view_layer.update()
    for area in bpy.context.screen.areas:
        if area.type == "VIEW_3D":
            space = area.spaces.active
            space.show_region_ui = True
            space.shading.type = "SOLID"
            space.shading.color_type = "MATERIAL"
            space.overlay.show_floor = False
            space.overlay.show_axis_x = False
            space.overlay.show_axis_y = False
            space.region_3d.view_distance = .85
            space.region_3d.view_location = item.location
            # Look toward the held tablet from near the head reference.
            space.region_3d.view_rotation = Vector((0, -.85, .3)).to_track_quat("Z", "Y")
            if not bpy.app.background:
                with bpy.context.temp_override(area=area, region=next(r for r in area.regions if r.type == "WINDOW")):
                    bpy.ops.wm.tool_set_by_id(name="builtin.move")
    return scene


def check(scene):
    """Prove conversion, composition, mirror, mode changes and safe XML exports."""
    check_fingers(scene)
    poses = current_poses(scene)
    assert all(same(tag, poses[tag], BASELINE[tag]) for tag in poses), "Untouched scene must round-trip"
    proof = REFERENCE["compositionProof"]
    composed = native_matrix(proof["itemPosition"], proof["itemOrientation"]) @ native_matrix(proof["handPosition"], proof["handOrientation"])
    native_world = C @ Matrix(proof["world"]).transposed() @ CI
    assert max(abs(composed[i][j] - native_world[i][j]) for i in range(4) for j in range(4)) < 1e-6, "Must match native VRage matrix/quaternion conventions"
    item_native = CI @ target("Tablet").matrix_basis @ C
    grip_native = CI @ target("Left").matrix_basis @ C
    expected = C @ item_native @ grip_native @ CI
    assert max(abs(expected[i][j] - target("Left").matrix_world[i][j]) for i in range(4) for j in range(4)) < 1e-6
    bpy.ops.tablet_pose.mirror()
    assert abs(target("Left").matrix_basis.to_3x3().determinant() - 1) < 1e-5
    assert abs(target("Left").location.x + target("Right").location.x) < 1e-6
    palm_mapping = Matrix(REFERENCE["mirrorRightToLeft"]).transposed().to_4x4()
    left_mapped = CI @ target("Left").matrix_basis @ C @ palm_mapping
    reflected_right = Matrix.Diagonal((-1, 1, 1, 1)) @ CI @ target("Right").matrix_basis @ C
    assert max(abs(left_mapped[i][j] - reflected_right[i][j]) for i in range(4) for j in range(4)) < 1e-6
    load_targets(scene, BASELINE)
    target("Left").location.x += .01
    target("Left").rotation_euler.y += .2
    edited = current_poses(scene)
    scene.tablet_pose.mode = "Walking / third person"
    target("Tablet").location.z += .02
    scene.tablet_pose.mode = "Idle / first person"
    edited = current_poses(scene)
    assert not same("ItemWalkingPosition3rd", edited["ItemWalkingPosition3rd"], BASELINE["ItemWalkingPosition3rd"])
    with tempfile.TemporaryDirectory(prefix="tablet-pose-check-") as folder:
        path = Path(folder) / "Tablet.sbc"
        authored = Path(folder) / "poses.json"
        original = (ROOT / "src/Data/Tablet.sbc").read_text()
        path.write_text(original)
        _, changed = export_poses(path, authored, BASELINE, BASELINE)
        assert not changed and path.read_text() == original, "No-op export must preserve every byte"
        final, changed = export_poses(path, authored, BASELINE, edited)
        assert set(changed) == {"LeftHandPosition", "LeftHandOrientation", "ItemWalkingPosition3rd"}
        for tag in final:
            assert same(tag, final[tag], edited[tag])
        assert json.loads(authored.read_text()) == final
        # Rebuilding definitions must preserve the editor's authored transforms.
        generated = Path(folder) / "generator"
        (generated / "assets").mkdir(parents=True)
        (generated / "src/Data").mkdir(parents=True)
        for name in ("build_tablet_definitions.py", "tablet_pose_data.py"):
            shutil.copy2(ROOT / "assets" / name, generated / "assets" / name)
        shutil.copy2(authored, generated / "assets/tablet-poses.json")
        subprocess.run([bpy.app.binary_path, "--background", "--factory-startup", "--python-exit-code", "1", "--python-expr",
                        "import runpy; runpy.run_path(" + repr(str(generated / "assets/build_tablet_definitions.py")) + ")"],
                       check=True, stdout=subprocess.DEVNULL)
        regenerated = read_poses(generated / "src/Data/Tablet.sbc")
        assert all(same(tag, final[tag], regenerated[tag]) for tag in final)
        # Unrelated definition text survives both normal export and concurrent edits.
        import re
        assert re.search(r"<FingersAnimation>[^<]*</FingersAnimation>", path.read_text()).group() == re.search(
            r"<FingersAnimation>[^<]*</FingersAnimation>", original).group()
        path.write_text(original.replace("<Mass>1.4</Mass>", "<Mass>2.5</Mass>"))
        export_poses(path, authored, BASELINE, edited)
        assert "<Mass>2.5</Mass>" in path.read_text()
        try:
            export_poses(path, authored, BASELINE, edited)
            raise AssertionError("Conflicting external transform edits must be rejected")
        except ValueError:
            pass
    load_targets(scene, BASELINE)
    print("PASS: native glove meshes, native VRage matrix proof, SE/Blender conversion, mirror basis, eight views/shared ironsight, no-op/edited exports, regeneration and conflict checks")


def glove_vertices(side):
    obj = bpy.data.objects[side + " astronaut glove"]
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    geometry = evaluated.to_mesh()
    points = [v.co.copy() for v in geometry.vertices]
    evaluated.to_mesh_clear()
    return points


def check_fingers(scene):
    """Prove native skinning, parent-local export and tablet-only activation."""
    import xml.etree.ElementTree as ET
    load_fingers(native_fingers())
    baseline = current_fingers()
    assert fingers_same(native_fingers(), baseline), "Native finger joints must round-trip"
    for side in ("Left", "Right"):
        expected = [C.to_3x3() @ Vector(v) for v in REFERENCE[side.lower()]["vertices"]]
        actual = glove_vertices(side)
        error = max((a - b).length for a, b in zip(actual, expected))
        print(f"{side} glove skinning error: {error * 1000:.4f} mm")
        assert error < .0001, "Blender skinning must match the native HoldingTool pose"
    left_before, right_before = glove_vertices("Left"), glove_vertices("Right")
    scene.tablet_pose.side = "Left"
    scene.tablet_pose.finger = "Index"
    scene.tablet_pose.joint = "2"
    bpy.ops.tablet_pose.joint()
    bone = bpy.context.active_pose_bone
    assert bone.name == "SE_RigL_Index_2" and bpy.context.object.mode == "POSE"
    bone.rotation_euler.x += .35
    bone.location.y += .002
    edited = current_fingers()
    assert sum(not all(same(k.title(), baseline[n][k], edited[n][k]) for k in ("position", "orientation")) for n in JOINTS) == 1
    assert max((a - b).length for a, b in zip(left_before, glove_vertices("Left"))) > .003
    assert max((a - b).length for a, b in zip(right_before, glove_vertices("Right"))) < 1e-7
    # Wrist/item selection must leave Pose Mode cleanly.
    select("Tablet")
    assert bpy.context.object.mode == "OBJECT"
    with tempfile.TemporaryDirectory(prefix="tablet-finger-check-") as folder:
        root = Path(folder)
        (root / "src/Data").mkdir(parents=True)
        (root / "assets").mkdir()
        path = root / "src/Data/Tablet.sbc"
        original = (ROOT / "src/Data/Tablet.sbc").read_bytes()
        path.write_bytes(original)
        export_grip(root, BASELINE, BASELINE, baseline, None, baseline, REFERENCE["authoring"])
        assert path.read_bytes() == original and not (root / MODEL).exists(), "No-op must not install an animation"
        final, changes, exported, count = export_grip(root, BASELINE, BASELINE, baseline, None, edited, REFERENCE["authoring"])
        assert not changes and count == 1
        assert fingers_same(json.loads((root / SOURCE).read_text()), edited)
        assert (root / MODEL).stat().st_size > 1000
        assert "<FingersAnimation>ArcaneTabletGrip</FingersAnimation>" in path.read_text()
        xml = ET.parse(root / DEFINITION).getroot()
        controllers = xml.findall("Definition")
        assert {d.find("Id").get("Subtype") for d in controllers} == {"Default_Astronaut", "Default_Astronaut_Female"}
        for controller in controllers:
            assert len(controller.findall("Layers/Layer")) == 1
            assert set(controller.findtext("Layers/Layer/BoneMask").split()) == set(JOINTS)
            machine = controller.find("StateMachines/StateMachine")
            assert machine.findtext("Nodes/Node/Type") == "PassThrough"
            conditions = machine.findall("Transitions/Transition/Conditions/Conjunction/Condition")
            assert [(c.get("Lhs"), c.get("Rhs")) for c in conditions] == [("arcanepower_tablet", "1"), ("arcanepower_tablet", "0")]
        load_fingers(json.loads((root / SOURCE).read_text()))
        assert fingers_same(current_fingers(), edited), "Reload must preserve joint-local transforms"
        # Definition regeneration preserves both wrist poses and custom clip selection.
        for name in ("build_tablet_definitions.py", "tablet_pose_data.py"):
            shutil.copy2(ROOT / "assets" / name, root / "assets" / name)
        subprocess.run([bpy.app.binary_path, "--background", "--factory-startup", "--python-exit-code", "1", "--python-expr",
                        "import runpy; runpy.run_path(" + repr(str(root / "assets/build_tablet_definitions.py")) + ")"],
                       check=True, stdout=subprocess.DEVNULL)
        assert "<FingersAnimation>ArcaneTabletGrip</FingersAnimation>" in path.read_text()
        assert all(same(k, read_poses(path)[k], BASELINE[k]) for k in BASELINE)
        saved = {name: (root / name).read_bytes() for name in (MODEL, DEFINITION, "src/Data/Tablet.sbc")}
        try:
            export_grip(root, BASELINE, BASELINE, baseline, None, edited, REFERENCE["authoring"])
            raise AssertionError("Conflicting finger edits must be rejected")
        except ValueError as error:
            assert "changed on disk" in str(error)
        assert all((root / name).read_bytes() == data for name, data in saved.items())
        token = finger_source(root)
        altered = json.loads(json.dumps(edited))
        altered["SE_RigR_Thumb_1"]["position"][0] += .003
        try:
            export_grip(root, BASELINE, BASELINE, edited, token, altered,
                        {**REFERENCE["authoring"], "template": str(root / "missing.mwm")})
            raise AssertionError("Native export failures must be rejected")
        except ValueError as error:
            assert "Native finger animation export failed" in str(error)
        assert finger_source(root) == token
        assert all((root / name).read_bytes() == data for name, data in saved.items())
        # A disk failure after earlier files were replaced must restore the grip.
        from unittest.mock import patch
        import os
        saved.update({name: (root / name).read_bytes() for name in (SOURCE, "assets/tablet-poses.json")})
        replace = os.replace
        def fail_definition(source, destination):
            if Path(destination) == root / DEFINITION:
                raise OSError("Simulated write failure")
            return replace(source, destination)
        with patch("tablet_fingers.os.replace", side_effect=fail_definition):
            try:
                export_grip(root, BASELINE, BASELINE, edited, token, altered, REFERENCE["authoring"])
                raise AssertionError("Disk failures must be rejected")
            except OSError as error:
                assert "Simulated write failure" in str(error)
        assert all((root / name).read_bytes() == data for name, data in saved.items()), "Partial exports must roll back"
    load_fingers(FINGER_BASELINE)
    select("Left")
    print("PASS: thirty joints, native skinning, isolated joint deformation, pose selection, native MWM roundtrip, finger persistence, tablet-only controller layers, regeneration/conflicts/failure safety")


def preview(scene):
    camera_data = bpy.data.cameras.new("Editor preview")
    camera = bpy.data.objects.new("Editor preview", camera_data)
    scene.collection.objects.link(camera)
    centre = target("Tablet").matrix_world.translation
    camera.location = centre + Vector((.25, -.75, .3))
    camera.rotation_euler = (centre - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = .68
    scene.camera = camera
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "MATERIAL"
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True
    scene.display.shading.background_type = "WORLD"
    scene.world.color = (.045, .045, .045)
    scene.render.resolution_x = 1000
    scene.render.resolution_y = 800
    scene.render.resolution_percentage = 100
    scene.render.filepath = str(ROOT / ".cache/tablet-pose/preview.png")
    bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    arguments = sys.argv[sys.argv.index("--") + 1:]
    scene = setup(json.loads(Path(arguments[0]).read_text()))
    if "--check" in arguments:
        check(scene)
        preview(scene)
