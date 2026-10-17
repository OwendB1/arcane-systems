// Apply shipped runtime matrices to actual packed MWM vertices, then compare
// against independently sampled Blender authoring motion (including native LODs).
using System;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Collections.Generic;
using System.Web.Script.Serialization;
using System.Security.Cryptography;
using VRageMath;
using VRageMath.PackedVector;
using VRageRender.Import;
using ArcanePower;

class ThermalNativeMotionProbe
{
    static Dictionary<string,object> Read(string path)
    {
        var importer=new MyModelImporter();
        using(var reader=new BinaryReader(File.OpenRead(path)))
            typeof(MyModelImporter).GetMethod("LoadTagData",BindingFlags.Instance|BindingFlags.NonPublic)
                .Invoke(importer,new object[]{reader,new[]{"Vertices","TexCoords0","MeshParts","Dummies","LODs"}});
        return importer.GetTagData();
    }
    static float[] Values(Matrix m) { return new[]{m.M11,m.M12,m.M13,m.M14,m.M21,m.M22,m.M23,m.M24,m.M31,m.M32,m.M33,m.M34,m.M41,m.M42,m.M43,m.M44}; }
    static Vector3[] Vertices(Dictionary<string,object> data)
    {
        return ((HalfVector4[])data["Vertices"]).Select(v=>{var p=v.ToVector4();return new Vector3(p.X,p.Y,p.Z)*p.W;}).ToArray();
    }
    static float[][] Bounds(IEnumerable<Vector3> points)
    {
        var box=BoundingBox.CreateInvalid();foreach(var point in points)box.Include(point);
        return new[]{new[]{box.Min.X,box.Min.Y,box.Min.Z},new[]{box.Max.X,box.Max.Y,box.Max.Z}};
    }
    static int Main(string[] args)
    {
        var json=new JavaScriptSerializer{MaxJsonLength=int.MaxValue};
        var contract=(Dictionary<string,object>)json.DeserializeObject(File.ReadAllText(args[0]));
        var output=new List<object>();var failures=new List<object>();var inputs=new Dictionary<string,string>();int checks=0,meshes=0;double maximum=0;
        var models=(object[])contract["models"];
        for(int modelIndex=0;modelIndex<models.Length;modelIndex++)
        {
            var model=(Dictionary<string,object>)models[modelIndex];
            string parent=args[modelIndex+3];
            var dummies=(Dictionary<string,MyModelDummy>)Read(parent)["Dummies"];
            foreach(Dictionary<string,object> part in (object[])model["parts"])
            {
                string name=(string)part["name"];
                var dummy=dummies["subpart_"+name];
                string path=Path.Combine(Path.GetDirectoryName(parent),(string)dummy.CustomData["file"]+".mwm");
                var data=Read(path);var points=Vertices(data);var samples=(object[])part["samples"];
                bool manifold=name.StartsWith("Thermal_L")||name.StartsWith("Thermal_R");
                int bay=manifold?Array.IndexOf(ThermalModels.ManifoldBays,name.Split('_')[1]):-1;
                string kind=manifold?name.Substring(name.LastIndexOf('_')+1):null;
                var poses=new List<float[]>();
                var levels=new List<Tuple<string,Vector3[]>>{Tuple.Create(path,points)};
                foreach(var lod in (MyLODDescriptor[])data["LODs"])
                {
                    string lodPath=Path.Combine(args[2],lod.Model.Replace('\\','/'));
                    levels.Add(Tuple.Create(lodPath,Vertices(Read(lodPath))));
                }
                foreach(var level in levels)
                    using(var sha=SHA256.Create())inputs[Path.GetFullPath(level.Item1).Substring(Path.GetFullPath(args[2]).Length+1).Replace('\\','/')]
                        =BitConverter.ToString(sha.ComputeHash(File.ReadAllBytes(level.Item1))).Replace("-","").ToLowerInvariant();
                meshes+=levels.Count;
                foreach(Dictionary<string,object> sample in samples)
                {
                    double value=Convert.ToDouble(sample["value"]);
                    Matrix pose=manifold?ThermalManifolds.Pose(bay,kind,value):ThermalRotors.Pose(name.EndsWith("TurbineRotor")?0:1,value);
                    poses.Add(Values(pose));
                    var expected=(object[])sample["bounds"];
                    foreach(var level in levels)
                    {
                        var actual=Bounds(level.Item2.Select(p=>Vector3.Transform(p,pose)));
                        double error=0;
                        for(int end=0;end<2;end++)for(int axis=0;axis<3;axis++)
                            error=Math.Max(error,Math.Abs(actual[end][axis]-Convert.ToDouble(((object[])expected[end])[axis])));
                        checks++;maximum=Math.Max(maximum,error);
                        if(error>(level.Item1==path?.012:.05))
                            failures.Add(new{model=model["name"],part=name,value,error_m=error,mesh=Path.GetFileName(level.Item1)});
                    }
                }
                var uv=((HalfVector2[])data["TexCoords0"]).Select(v=>{var p=v.ToVector2();return new[]{p.X,p.Y};}).ToArray();
                output.Add(new{model=model["name"],name,positions=points.Select(p=>new[]{p.X,p.Y,p.Z}).ToArray(),uv,
                    parts=((List<MyMeshPartInfo>)data["MeshParts"]).Select(p=>new{material=p.GetMaterialName(),indices=p.m_indices}).ToArray(),poses});
            }
        }
        var report=new{status=failures.Count==0?"passed":"failed",checks,meshes,moving_parts=output.Count,maximum_error_m=maximum,failed_checks=failures.Count,failures=failures.Take(12).ToArray(),native_mesh_sha256=inputs};
        File.WriteAllText(args[1],json.Serialize(new{report,parts=output}));
        Console.WriteLine(json.Serialize(report));
        return failures.Count==0?0:1;
    }
}
