using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using VRageRender.Import;

// Read native model dependencies instead of shipping every obsolete cache family.
class ModelDependencies
{
    static readonly HashSet<string> Seen = new HashSet<string>();
    static void Walk(string path)
    {
        path = Path.GetFullPath(path);
        if (!Seen.Add(path)) return;
        var importer = new MyModelImporter();
        using (var reader = new BinaryReader(File.OpenRead(path)))
            typeof(MyModelImporter).GetMethod("LoadTagData", BindingFlags.Instance | BindingFlags.NonPublic)
                .Invoke(importer, new object[] { reader, new[] { "Dummies", "MeshParts", "LODs" } });
        var tags = importer.GetTagData();
        Console.WriteLine("MODEL\t" + path);
        object value;
        // Animation-only MWM files have neither mesh parts nor dummies.
        if (tags.TryGetValue("MeshParts", out value))
            foreach (var part in (List<MyMeshPartInfo>)value)
                foreach (var texture in part.m_MaterialDesc.Textures.Values)
                    if (!string.IsNullOrEmpty(texture)) Console.WriteLine("TEXTURE\t" + texture);
        if (tags.TryGetValue("Dummies", out value))
            foreach (var dummy in (Dictionary<string, MyModelDummy>)value)
                if (dummy.Key.StartsWith("subpart_"))
                    Walk(Path.Combine(Path.GetDirectoryName(path),
                        ((string)dummy.Value.CustomData["file"]).Replace('\\', '/') + ".mwm"));
        if (tags.TryGetValue("LODs", out value))
            foreach (var lod in (MyLODDescriptor[])value)
            {
                // Match native GetModelAbsoluteFilePath: LODs start at mod root.
                int models = path.IndexOf("/Models/", StringComparison.OrdinalIgnoreCase);
                if (models < 0) throw new Exception("Cannot resolve LOD outside Models: " + path);
                string relative = lod.Model.Replace('\\', '/');
                if (!relative.EndsWith(".mwm", StringComparison.OrdinalIgnoreCase)) relative += ".mwm";
                string root = path.Substring(0, models + 1);
                string resolved = Path.GetFullPath(Path.Combine(root, relative));
                if (!resolved.StartsWith(root, StringComparison.Ordinal) || relative.Contains("/.") || Path.IsPathRooted(relative))
                    throw new Exception("Invalid/staging LOD reference: " + relative);
                Walk(resolved);
            }
    }
    static void Main(string[] args) { foreach (var path in args) Walk(path); }
}
