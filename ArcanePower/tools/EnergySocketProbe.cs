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
        var size = new Vector3I(core ? 3 : 1, 3, core ? 3 : 1);
        var center = new Vector3I(core ? 1 : 0, 1, core ? 1 : 0);
        var dummies = ((Dictionary<string, MyModelDummy>)data["Dummies"])
            .Where(p => p.Key.StartsWith("detector_upgrade")).ToArray();
        Require(dummies.Length == (core ? 4 : 1), "Wrong native upgrade socket count");
        var expected = new HashSet<Vector3I>(core
            ? new[] { Vector3I.Left, Vector3I.Right, Vector3I.Backward, Vector3I.Forward }
            : new[] { Vector3I.Forward });
        foreach (var dummy in dummies)
        {
            Vector3 local = dummy.Value.Matrix.Translation;
            Vector3 shifted = local + new Vector3(size) * 1.25f;
            Vector3I cell = Vector3I.Min(Vector3I.Max(Vector3I.Floor(shifted / 2.5f), Vector3I.Zero), size - Vector3I.One);
            Vector3 direction = Vector3.Normalize(Vector3.DominantAxisProjection(shifted - (new Vector3(cell) + Vector3.Half) * 2.5f));
            var normal = Vector3I.Round(direction);
            Require(expected.Remove(normal), "Unexpected or duplicate socket face: " + local);
            Require(cell - center == (core ? normal : Vector3I.Zero), "Socket not in face-center cell");
            Require(Vector3.Distance(local, new Vector3(normal) * (core ? 3.72f : 1.22f)) < .002f, "Socket not at native mating depth");
            // In grid coordinates, a 1x3x1 module at normal*2 has a connector
            // facing -normal; its connecting cell must be this core face cell.
            if (core) Require(normal * 2 - normal == cell - center, "Module/core adjacency mismatch");
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
