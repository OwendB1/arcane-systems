using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using VRageRender.Import;
using VRageMath;

class ConstructionModelProbe
{
    static Dictionary<string, object> Read(string path)
    {
        var importer = new MyModelImporter();
        using (var reader = new BinaryReader(File.OpenRead(path)))
            typeof(MyModelImporter).GetMethod("LoadTagData", BindingFlags.Instance | BindingFlags.NonPublic)
                .Invoke(importer, new object[] { reader, new[] { "Dummies", "BoundingBox", "ModelInfo", "MeshParts", "HavokCollisionGeometry" } });
        return importer.GetTagData();
    }

    static void Main(string[] args)
    {
        // Delivered stage, authoritative HKT, finished model.
        var data = Read(args[0]);
        var info = (MyModelInfo)data["ModelInfo"];
        if (info.TrianglesCount <= 0 || info.VerticesCount <= 0) throw new Exception("Empty stage");
        var dummies = (Dictionary<string, MyModelDummy>)data["Dummies"];
        if (dummies.Keys.Any(k => k.StartsWith("subpart_"))) throw new Exception("Animated stage dummy");
        if (!((byte[])data["HavokCollisionGeometry"]).SequenceEqual(File.ReadAllBytes(args[1])))
            throw new Exception("Incorrect embedded collision");
        var bounds = (BoundingBox)data["BoundingBox"];
        var finished = (BoundingBox)Read(args[2])["BoundingBox"];
        finished.Inflate(.1f);
        if (finished.Contains(bounds) != ContainmentType.Contains) throw new Exception("Stage exceeds block envelope: "+bounds);
        var parts = (List<MyMeshPartInfo>)data["MeshParts"];
        if (parts.Count == 0 || !parts.Any(p => p.GetMaterialName() == "Construction")) throw new Exception("Missing construction steel");
        Console.WriteLine(Path.GetFileName(args[0])+": "+info.TrianglesCount+" triangles; bounds, construction material and embedded collision PASS");
    }
}
