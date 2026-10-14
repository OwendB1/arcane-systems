// Offline authoring only: read locally installed models through SE's native importer.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Web.Script.Serialization;
using System.Text.RegularExpressions;
using VRage.Import;
using VRageMath;
using VRageMath.PackedVector;
using VRageRender.Animations;
using VRageRender.Import;

class TabletPoseReference
{
    public class BonePose { public float[] position { get; set; } public float[] orientation { get; set; } }
    static float[][] Rows(Matrix m) { return new[] { new[] { m.M11,m.M12,m.M13,m.M14 },
        new[] { m.M21,m.M22,m.M23,m.M24 }, new[] { m.M31,m.M32,m.M33,m.M34 }, new[] { m.M41,m.M42,m.M43,m.M44 } }; }

    static void ExportAnimation(string template, string source, string output)
    {
        var poses = new JavaScriptSerializer().Deserialize<Dictionary<string, BonePose>>(File.ReadAllText(source));
        if (poses.Count != 30 || poses.Keys.Any(k => !Regex.IsMatch(k, "^SE_Rig[LR]_(Thumb|Index|Middle|Ring|Little)_[123]$")))
            throw new Exception("Expected the thirty native finger joints");
        var clip = new MyAnimationClip { Name = "ArcaneTabletGrip", Duration = 1 };
        foreach (var pair in poses.OrderBy(p => p.Key))
        {
            var p = pair.Value;
            if (p.position.Length != 3 || p.orientation.Length != 4 || p.position.Concat(p.orientation).Any(v => float.IsNaN(v) || float.IsInfinity(v)))
                throw new Exception("Invalid finger transform " + pair.Key);
            var q = new Quaternion(p.orientation[0], p.orientation[1], p.orientation[2], p.orientation[3]);
            if (q.LengthSquared() < .000001f) throw new Exception("Zero finger quaternion");
            q.Normalize();
            var bone = new MyAnimationClip.Bone(2) { Name = pair.Key };
            for (int i = 0; i < 2; i++) bone.Keyframes[i] = new MyAnimationClip.Keyframe {
                Time = i, Rotation = q, Translation = new Vector3(p.position[0], p.position[1], p.position[2]) };
            clip.Bones.Add(bone);
        }
        var data = Read(template, null);
        // Older vanilla animation files predate mesh sections.
        if (!data.ContainsKey("Sections")) data["Sections"] = new List<MyMeshSectionInfo>();
        var animation = (ModelAnimations)data["Animations"];
        animation.Clips.Clear();
        animation.Clips.Add(clip);
        MyModelExporter.ExportModelData(output, data, false);
        var restored = (ModelAnimations)Read(output, "Animations")["Animations"];
        if (restored.Clips.Count != 1 || restored.Clips[0].Bones.Count != 30 || restored.Clips[0].Name != clip.Name)
            throw new Exception("Animation roundtrip failed");
        foreach (var bone in restored.Clips[0].Bones)
        {
            var original = clip.Bones.Single(b => b.Name == bone.Name);
            for (int i = 0; i < 2; i++)
                if (bone.Keyframes[i].Translation != original.Keyframes[i].Translation || bone.Keyframes[i].Rotation != original.Keyframes[i].Rotation)
                    throw new Exception("Export changed finger transform " + bone.Name);
        }
        Console.WriteLine("PASS native MWM animation roundtrip: thirty finger joints, two identical loop keys");
    }
    static Dictionary<string, object> Read(string path, params string[] tags)
    {
        var importer = new MyModelImporter();
        using (var reader = new BinaryReader(File.OpenRead(path)))
            typeof(MyModelImporter).GetMethod("LoadTagData", BindingFlags.Instance | BindingFlags.NonPublic)
                .Invoke(importer, new object[] { reader, tags });
        return importer.GetTagData();
    }

    static float[] XYZ(Vector3 v) { return new[] { v.X, v.Y, v.Z }; }
    static Vector3[] Vertices(Dictionary<string, object> data)
    {
        var packed = (HalfVector4[])data["Vertices"];
        var result = new Vector3[packed.Length];
        for (int i = 0; i < packed.Length; i++) result[i] = VF_Packer.UnpackPosition(ref packed[i]);
        return result;
    }
    static IEnumerable<int[]> Faces(Dictionary<string, object> data)
    {
        foreach (var part in (List<MyMeshPartInfo>)data["MeshParts"])
            for (int i = 0; i < part.m_indices.Count; i += 3)
                yield return new[] { part.m_indices[i], part.m_indices[i + 1], part.m_indices[i + 2] };
    }

    static Matrix PalmBasis(Dictionary<string, object> data, string name)
    {
        var bones = (MyModelBone[])data["Bones"];
        int index = Array.FindIndex(bones, b => b.Name == name);
        Matrix result = bones[index].Transform;
        for (int parent = bones[index].Parent; parent >= 0; parent = bones[parent].Parent)
            result *= bones[parent].Transform;
        return Matrix.CreateFromQuaternion(Quaternion.Normalize(Quaternion.CreateFromRotationMatrix(result)));
    }

    static object CompositionProof()
    {
        var gripQ = Quaternion.Normalize(new Quaternion(-.365f, .487f, -.551f, .571f));
        var itemQ = Quaternion.CreateFromYawPitchRoll(.37f, -.51f, .24f);
        var grip = Matrix.CreateFromQuaternion(gripQ); grip.Translation = new Vector3(-.162f, -.015f, .023f);
        var item = Matrix.CreateFromQuaternion(itemQ); item.Translation = new Vector3(.04f, -.21f, -.31f);
        var world = grip * item; // MyCharacter.UpdateHandBones uses hand * item.WorldMatrix.
        return new {
            handPosition = XYZ(grip.Translation), handOrientation = new[] { gripQ.X, gripQ.Y, gripQ.Z, gripQ.W },
            itemPosition = XYZ(item.Translation), itemOrientation = new[] { itemQ.X, itemQ.Y, itemQ.Z, itemQ.W },
            world = new[] { new[] { world.M11, world.M12, world.M13, world.M14 },
                new[] { world.M21, world.M22, world.M23, world.M24 },
                new[] { world.M31, world.M32, world.M33, world.M34 },
                new[] { world.M41, world.M42, world.M43, world.M44 } }
        };
    }

    static object Hand(Dictionary<string, object> data, MyAnimationClip clip, string palmName)
    {
        var bones = (MyModelBone[])data["Bones"];
        int palm = Array.FindIndex(bones, b => b.Name == palmName);
        if (palm < 0) throw new Exception("Missing palm " + palmName);
        var members = new bool[bones.Length];
        for (int i = 0; i < bones.Length; i++)
            for (int p = i; p >= 0; p = bones[p].Parent)
                if (p == palm) { members[i] = true; break; }
        var keys = clip.Bones.Where(b => b.Keyframes.Length > 0).ToDictionary(b => b.Name, b => b.Keyframes[0]);
        var bind = new Matrix[bones.Length];
        var posed = new Matrix[bones.Length];
        var done = new bool[bones.Length];
        Action<int> visit = null;
        visit = i => {
            if (done[i]) return;
            int parent = bones[i].Parent;
            if (parent >= 0) visit(parent);
            Matrix local = bones[i].Transform;
            MyAnimationClip.Keyframe key;
            // HoldingTool affects finger bones only. Keep the palm target itself unchanged.
            if (members[i] && i != palm && keys.TryGetValue(bones[i].Name, out key))
            {
                local = Matrix.CreateFromQuaternion(Quaternion.Normalize(key.Rotation));
                local.Translation = key.Translation;
            }
            bind[i] = parent < 0 ? bones[i].Transform : bones[i].Transform * bind[parent];
            posed[i] = parent < 0 ? local : local * posed[parent];
            done[i] = true;
        };
        for (int i = 0; i < bones.Length; i++) visit(i);
        var skin = new Matrix[bones.Length];
        for (int i = 0; i < bones.Length; i++) skin[i] = Matrix.Invert(bind[i]) * posed[i];
        Matrix toPalm = Matrix.Invert(posed[palm]);
        var vertices = Vertices(data);
        var indices = (Vector4I[])data["BlendIndices"];
        var weights = (Vector4[])data["BlendWeights"];
        var belongs = new bool[vertices.Length];
        var positions = new Vector3[vertices.Length];
        for (int i = 0; i < vertices.Length; i++)
        {
            int[] joint = { indices[i].X, indices[i].Y, indices[i].Z, indices[i].W };
            float[] weight = { weights[i].X, weights[i].Y, weights[i].Z, weights[i].W };
            float handWeight = 0;
            Vector3 point = Vector3.Zero;
            for (int k = 0; k < 4; k++)
            {
                if (weight[k] <= 0) continue;
                if (members[joint[k]]) handWeight += weight[k];
                point += Vector3.Transform(vertices[i], skin[joint[k]]) * weight[k];
            }
            belongs[i] = handWeight >= .75f;
            positions[i] = Vector3.Transform(point, toPalm);
        }
        var map = new Dictionary<int, int>();
        var points = new List<float[]>();
        var restPoints = new List<float[]>();
        var vertexWeights = new List<Dictionary<string, float>>();
        var triangles = new List<int[]>();
        foreach (int[] face in Faces(data))
        {
            if (!face.All(i => belongs[i])) continue;
            var triangle = new int[3];
            for (int k = 0; k < 3; k++)
            {
                int index;
                if (!map.TryGetValue(face[k], out index))
                {
                    int vertex = face[k];
                    index = points.Count; map.Add(vertex, index); points.Add(XYZ(positions[vertex]));
                    restPoints.Add(XYZ(Vector3.Transform(vertices[vertex], Matrix.Invert(bind[palm]))));
                    int[] joints = { indices[vertex].X, indices[vertex].Y, indices[vertex].Z, indices[vertex].W };
                    float[] w = { weights[vertex].X, weights[vertex].Y, weights[vertex].Z, weights[vertex].W };
                    var groups = new Dictionary<string, float>();
                    for (int j = 0; j < 4; j++)
                    {
                        if (w[j] <= 0) continue;
                        string name = members[joints[j]] ? bones[joints[j]].Name : palmName;
                        groups[name] = (groups.ContainsKey(name) ? groups[name] : 0) + w[j];
                    }
                    vertexWeights.Add(groups);
                }
                triangle[k] = index;
            }
            triangles.Add(triangle);
        }
        if (triangles.Count < 100) throw new Exception("Incomplete hand mesh " + palmName);
        var rig = Enumerable.Range(0, bones.Length).Where(i => members[i]).Select(i => new {
            name = bones[i].Name,
            parent = i == palm ? "" : bones[bones[i].Parent].Name,
            bind = Rows(bind[i] * Matrix.Invert(bind[palm])),
            pose = Rows(posed[i] * Matrix.Invert(posed[palm]))
        }).ToArray();
        return new { vertices = points, restVertices = restPoints, weights = vertexWeights, bones = rig,
            triangles, palm = palmName, fingerClip = clip.Name };
    }

    static void Main(string[] args)
    {
        if (args[0] == "--export-animation") { ExportAnimation(args[1], args[2], args[3]); return; }
        var character = Read(args[0], "Vertices", "MeshParts", "Bones", "BlendIndices", "BlendWeights");
        var animations = (ModelAnimations)Read(args[1], "Animations")["Animations"];
        var tablet = Read(args[2], "Vertices", "MeshParts");
        Matrix reflection = Matrix.Identity; reflection.M11 = -1;
        Matrix mirror = PalmBasis(character, "SE_RigRPalm") * reflection * Matrix.Invert(PalmBasis(character, "SE_RigLPalm"));
        var document = new {
            source = "Local SE astronaut mesh; HoldingTool finger keyframe 0; palm-local coordinates in metres",
            compositionProof = CompositionProof(),
            left = Hand(character, animations.Clips[0], "SE_RigLPalm"),
            right = Hand(character, animations.Clips[0], "SE_RigRPalm"),
            mirrorRightToLeft = new[] { new[] { mirror.M11, mirror.M12, mirror.M13 },
                new[] { mirror.M21, mirror.M22, mirror.M23 }, new[] { mirror.M31, mirror.M32, mirror.M33 } },
            tablet = new { vertices = Vertices(tablet).Select(XYZ).ToArray(), triangles = Faces(tablet).ToArray() }
        };
        var serializer = new JavaScriptSerializer { MaxJsonLength = 50000000 };
        File.WriteAllText(args[3], serializer.Serialize(document));
        Console.WriteLine("Read native tablet and astronaut hands: " + args[3]);
    }
}
