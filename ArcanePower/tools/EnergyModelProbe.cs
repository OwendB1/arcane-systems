using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using VRageRender.Import;

// Validate the compiled main mesh and emit its actual native dependencies.
class EnergyModelProbe
{
    static MyModelImporter Read(string path, params string[] fields)
    {
        var importer = new MyModelImporter();
        using (var reader = new BinaryReader(File.OpenRead(path)))
            typeof(MyModelImporter).GetMethod("LoadTagData", BindingFlags.Instance | BindingFlags.NonPublic)
                .Invoke(importer, new object[] { reader, fields });
        return importer;
    }
    static float[] Elements(VRageMath.Matrix m)
    {
        return new[] { m.M11,m.M12,m.M13,m.M14,m.M21,m.M22,m.M23,m.M24,m.M31,m.M32,m.M33,m.M34,m.M41,m.M42,m.M43,m.M44 };
    }
    static void Main(string[] args)
    {
        if (args[0] == "--highlights")
        {
            var highlightTags = Read(args[1], "Sections", "Dummies").GetTagData();
            var sections = (List<MyMeshSectionInfo>)highlightTags["Sections"];
            var dummies = (Dictionary<string,MyModelDummy>)highlightTags["Dummies"];
            foreach (var section in sections)
                Console.WriteLine("SECTION\t" + section.Name + "\t" + section.Meshes.Sum(m => m.IndexCount));
            foreach (var entry in dummies.Where(d => d.Key.StartsWith("detector_conveyor_")))
            {
                object highlightValue;
                string highlight = entry.Value.CustomData.TryGetValue("highlight", out highlightValue) ? highlightValue as string : null;
                Console.WriteLine("HIGHLIGHT\t" + entry.Key + "\t" + highlight);
                if (string.IsNullOrEmpty(highlight)) throw new Exception("Missing hatch highlight: " + entry.Key);
                foreach (string target in highlight.Split(';'))
                    if (target.StartsWith("subpart_"))
                    {
                        if (!dummies.ContainsKey(target) || !dummies[target].CustomData.ContainsKey("file"))
                            throw new Exception("Unresolved hatch subpart: " + target);
                    }
                    else if (!sections.Any(s => s.Name == target && s.Meshes.Sum(m => m.IndexCount) > 0))
                        throw new Exception("Unresolved hatch mesh section: " + target);
            }
            return;
        }
        if (args[0] == "--dummies")
        {
            object dummyTag;
            if (Read(args[1], "Dummies").GetTagData().TryGetValue("Dummies", out dummyTag))
                foreach (var entry in (Dictionary<string,MyModelDummy>)dummyTag)
                {
                    object file;
                    entry.Value.CustomData.TryGetValue("file", out file);
                    Console.WriteLine(entry.Key + "\t" + string.Join(",", Elements(entry.Value.Matrix)
                        .Select(v => v.ToString("R",System.Globalization.CultureInfo.InvariantCulture))) + "\t" + (file ?? ""));
                }
            return;
        }
        if (args[0] == "--lod-paths")
        {
            // MWMBuilder ignores XML Model paths and derives sibling LOD names.
            // Append a replacement native tag, updating only its index pointer;
            // every geometry, material, interface and physics byte stays intact.
            var lods = (MyLODDescriptor[])Read(args[1], "LODs").GetTagData()["LODs"];
            if (args.Length != lods.Length + 3) throw new Exception("LOD path count differs from native descriptors");
            if (lods.Select(l => l.Model).SequenceEqual(args.Skip(3)))
            {
                File.Copy(args[1], args[2], true);
                Console.WriteLine("LOD paths already match; native bytes preserved");
                return;
            }
            for (int i = 0; i < lods.Length; i++) lods[i].Model = args[i + 3];
            var bytes = File.ReadAllBytes(args[1]);
            long pointer = -1;
            using (var reader = new BinaryReader(new MemoryStream(bytes)))
            {
                if (reader.ReadString() != "Debug") throw new Exception("Unsupported native model header");
                int count = reader.ReadInt32();
                if (count < 0 || count > 10000) throw new Exception("Invalid native debug array");
                bool indexed = false;
                for (int i = 0; i < count; i++)
                {
                    string debugValue = reader.ReadString();
                    if (debugValue.StartsWith("Version:") && int.Parse(debugValue.Substring(8)) >= 1066002) indexed = true;
                }
                if (!indexed) throw new Exception("Native model has no indexed tags");
                count = reader.ReadInt32();
                if (count < 1 || count > 1000) throw new Exception("Invalid native tag index");
                for (int i = 0; i < count; i++)
                {
                    string tag = reader.ReadString();
                    long position = reader.BaseStream.Position;
                    int offset = reader.ReadInt32();
                    if (offset < 0 || offset >= bytes.Length) throw new Exception("Native tag offset outside file");
                    if (tag == "LODs")
                    {
                        if (pointer >= 0) throw new Exception("Duplicate LOD index");
                        pointer = position;
                    }
                }
            }
            if (pointer < 0) throw new Exception("Missing native LOD index");
            using (var stream = new MemoryStream())
            using (var writer = new BinaryWriter(stream))
            {
                writer.Write(bytes);
                writer.Write("LODs"); writer.Write(lods.Length);
                foreach (var lod in lods) lod.Write(writer);
                stream.Position = pointer; writer.Write(bytes.Length);
                File.WriteAllBytes(args[2], stream.ToArray());
            }
            var restored = (MyLODDescriptor[])Read(args[2], "LODs").GetTagData()["LODs"];
            if (!restored.Select(l => l.Model).SequenceEqual(lods.Select(l => l.Model)) ||
                !restored.Select(l => l.Distance).SequenceEqual(lods.Select(l => l.Distance)))
                throw new Exception("Native LOD roundtrip failed");
            Console.WriteLine("LOD paths remapped; all other native tag payloads preserved");
            return;
        }
        if (args[0] == "--collision")
        {
            var source = Read(args[1], "HavokCollisionGeometry");
            object collision;
            var data = source.GetTagData().TryGetValue("HavokCollisionGeometry", out collision) ? (byte[])collision : new byte[0];
            File.WriteAllBytes(args[2], data);
            return;
        }
        var importer = Read(args[0], "ModelInfo", "MeshParts", "Dummies", "HavokCollisionGeometry", "LODs");
        var tags = importer.GetTagData();
        var info = (MyModelInfo)tags["ModelInfo"];
        if (info.TrianglesCount != int.Parse(args[1]))
            throw new Exception("Compiled mesh differs from authoring source: " + info.TrianglesCount + " / " + args[1]);
        if (info.VerticesCount <= 0) throw new Exception("Empty native mesh");
        object geometry;
        var physics = tags.TryGetValue("HavokCollisionGeometry", out geometry) ? (byte[])geometry : new byte[0];
        if (args.Length > 2 && !physics.SequenceEqual(File.ReadAllBytes(args[2])))
            throw new Exception("Accepted collision bytes changed");
        if (args.Length > 3)
        {
            var previous = (Dictionary<string,MyModelDummy>)Read(args[3], "Dummies").GetTagData()["Dummies"];
            var current = (Dictionary<string,MyModelDummy>)tags["Dummies"];
            var keys = previous.Keys.Where(k => k.StartsWith("detector_") || k.StartsWith("subpart_")).OrderBy(k => k).ToArray();
            if (!keys.SequenceEqual(current.Keys.Where(k => k.StartsWith("detector_") || k.StartsWith("subpart_")).OrderBy(k => k)))
                throw new Exception("Native detector/subpart names changed");
            foreach (var key in keys)
            {
                if (Elements(previous[key].Matrix).Zip(Elements(current[key].Matrix), (a,b) => Math.Abs(a-b)).Max() > .00001f)
                    throw new Exception("Native interface pose changed: " + key);
                if (key.StartsWith("subpart_") && (string)previous[key].CustomData["file"] != (string)current[key].CustomData["file"])
                    throw new Exception("Native subpart target changed: " + key);
            }
            Console.WriteLine("INTERFACES\tunchanged");
        }
        var parts = (List<MyMeshPartInfo>)tags["MeshParts"];
        if (parts.Count == 0) throw new Exception("Missing native mesh parts");
        Console.WriteLine("MODEL\t" + Path.GetFileName(args[0]) + "\t" + info.TrianglesCount + "\t" + info.VerticesCount);
        foreach (var part in parts)
        {
            Console.WriteLine("MATERIAL\t" + part.GetMaterialName());
            foreach (var texture in part.m_MaterialDesc.Textures.Values)
                if (!string.IsNullOrEmpty(texture)) Console.WriteLine("TEXTURE\t" + texture);
        }
        object value;
        if (tags.TryGetValue("Dummies", out value))
            foreach (var dummy in (Dictionary<string, MyModelDummy>)value)
                if (dummy.Key.StartsWith("subpart_")) Console.WriteLine("SUBPART\t" + dummy.Value.CustomData["file"]);
        if (tags.TryGetValue("LODs", out value))
            foreach (var lod in (MyLODDescriptor[])value) Console.WriteLine("LOD\t" + lod.Model + "\t" + lod.Distance.ToString(System.Globalization.CultureInfo.InvariantCulture));
    }
}
