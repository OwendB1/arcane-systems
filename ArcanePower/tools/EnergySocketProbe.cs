using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using VRageRender.Import;
using VRageMath;

// Read the actual shipped MWM, not the Blender source. Same line-position
// calculation as MyMultilineConveyorEndpoint.GetLinePositions.
class EnergySocketProbe
{
    static void Require(bool ok, string message) { if (!ok) throw new Exception(message); }
    static void Main(string[] args)
    {
        var importer = new MyModelImporter();
        using (var reader = new BinaryReader(File.OpenRead(args[0])))
            typeof(MyModelImporter).GetMethod("LoadTagData", BindingFlags.Instance | BindingFlags.NonPublic)
                .Invoke(importer, new object[] { reader, new[] { "Dummies", "BoundingBox", "MeshParts" } });
        var data = importer.GetTagData();
        bool core = Path.GetFileName(args[0]) == "ArcanePower_EnergyCore.mwm";
        var allDummies = (Dictionary<string, MyModelDummy>)data["Dummies"];
        if (core)
            for (int i = 1; i <= 2; i++)
            {
                MyModelDummy ring;
                Require(allDummies.TryGetValue("subpart_EnergyRing" + i, out ring), "Battery ring subpart missing");
                Require((string)ring.CustomData["file"] == "ArcanePower_Ring" + (i + 2), "Battery must reuse reactor ring asset");
                Require(ring.Matrix.Translation.Length() < .001f, "Battery ring pivot must remain at sphere center");
            }
        if (Path.GetFileName(args[0]).Contains("EnergyStabilizer"))
        {
            Require(allDummies.Keys.Count(k => k.StartsWith("subpart_EnergyFan")) == 3, "Three fan pivots required");
            Require(File.Exists(Path.Combine(Path.GetDirectoryName(args[0]), "ArcanePower_EnergyFan.mwm")), "Fan model must ship beside stabilizer");
            var fanImporter = new MyModelImporter();
            using (var reader = new BinaryReader(File.OpenRead(Path.Combine(Path.GetDirectoryName(args[0]), "ArcanePower_EnergyFan.mwm"))))
                typeof(MyModelImporter).GetMethod("LoadTagData", BindingFlags.Instance | BindingFlags.NonPublic)
                    .Invoke(fanImporter, new object[] { reader, new[] { "BoundingBox" } });
            var fanBounds = (BoundingBox)fanImporter.GetTagData()["BoundingBox"];
            Require(fanBounds.Size.Z < .15f && fanBounds.Size.X > 1f && fanBounds.Size.Y > 1f, "Fan mesh shaft must be native Z");
            for (int i = 1; i <= 3; i++)
            {
                MyModelDummy fan;
                Require(allDummies.TryGetValue("subpart_EnergyFan" + i, out fan), "Fan pivot missing");
                Require((string)fan.CustomData["file"] == "ArcanePower_EnergyFan", "Unexpected fan asset");
                Require(Vector3.Distance(fan.Matrix.Translation, new Vector3(0, (i - 2) * 2.3f, .61f)) < .002f, "Fan pivot position");
                Require(Math.Abs(Vector3.Normalize(fan.Matrix.Backward).Z) > .999f, "Fan local Z must follow shaft");
                foreach (var corner in fanBounds.GetCorners())
                {
                    var point = Vector3.Transform(corner, Matrix.Normalize(fan.Matrix));
                    Require(point.Z > .41f && point.Z < .715f, "Native fan clips backplane or stationary grille");
                }
            }
        }
        var size = new Vector3I(core ? 3 : 1, 3, core ? 3 : 1);
        var center = new Vector3I(core ? 1 : 0, 1, core ? 1 : 0);
        var dummies = ((Dictionary<string, MyModelDummy>)data["Dummies"])
            .Where(p => p.Key.StartsWith("detector_upgrade")).ToArray();
        Require(dummies.Length == (core ? 12 : 3), "Wrong native upgrade socket count");
        var expected = new HashSet<string>();
        foreach (var face in core ? new[] { Vector3I.Left, Vector3I.Right, Vector3I.Backward, Vector3I.Forward } : new[] { Vector3I.Forward })
            for (int row = -1; row <= 1; row++) expected.Add(face + "/" + row);
        foreach (var dummy in dummies)
        {
            Vector3 local = dummy.Value.Matrix.Translation;
            Vector3 shifted = local + new Vector3(size) * 1.25f;
            Vector3I cell = Vector3I.Min(Vector3I.Max(Vector3I.Floor(shifted / 2.5f), Vector3I.Zero), size - Vector3I.One);
            Vector3 direction = Vector3.Normalize(Vector3.DominantAxisProjection(shifted - (new Vector3(cell) + Vector3.Half) * 2.5f));
            var normal = Vector3I.Round(direction);
            int row = cell.Y - center.Y;
            Require(expected.Remove(normal + "/" + row), "Unexpected or duplicate socket face: " + local);
            Require(cell - center == (core ? normal : Vector3I.Zero) + Vector3I.Up * row, "Socket not in mating cell");
            Require(Vector3.Distance(local, (new Vector3(normal) * (core ? 3.72f : 1.22f) + Vector3.Up * (row * 2.5f))) < .002f, "Socket not at native mating depth");
            // In grid coordinates, a 1x3x1 module at normal*2 has a connector
            // facing -normal; its connecting cell must be this core face cell.
            if (core) Require(normal * 2 + Vector3I.Up * row - normal == cell - center, "Module/core adjacency mismatch");
        }
        Require(expected.Count == 0, "Missing mating face");
        var bounds = (BoundingBox)data["BoundingBox"];
        float half = core ? 3.751f : 1.251f;
        Require(new BoundingBox(new Vector3(-half, -3.751f, -half), new Vector3(half, 3.751f, half)).Contains(bounds) == ContainmentType.Contains,
            "Model crosses its grid envelope: " + bounds);
        Require(((List<MyMeshPartInfo>)data["MeshParts"]).Any(p => p.GetMaterialName() == "Conveyor"), "Native socket surface missing");
        Console.WriteLine(Path.GetFileName(args[0]) + ": native sockets, directions, grid mating and bounds PASS");
    }
}
