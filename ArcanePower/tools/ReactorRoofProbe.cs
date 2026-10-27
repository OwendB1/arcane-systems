// Check actual packed MWM surfaces: source-space gaps can collapse during export.
using System;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Collections.Generic;
using VRageMath;
using VRageMath.PackedVector;
using VRageRender.Import;

class ReactorRoofProbe
{
    struct Triangle { public Vector3 A, B, C; public string Material; }
    static double Height(List<Triangle> triangles, double x, double z, string material)
    {
        double height = double.NegativeInfinity;
        foreach (var t in triangles)
        {
            if (t.Material != material) continue;
            double ax = t.B.X-t.A.X, az = t.B.Z-t.A.Z, bx = t.C.X-t.A.X, bz = t.C.Z-t.A.Z;
            double determinant = ax*bz-az*bx;
            if (Math.Abs(determinant) < 1e-10) continue;
            double u = ((x-t.A.X)*bz-(z-t.A.Z)*bx)/determinant;
            double v = (ax*(z-t.A.Z)-az*(x-t.A.X))/determinant;
            if (u < -1e-6 || v < -1e-6 || u+v > 1+1e-6) continue;
            height = Math.Max(height, t.A.Y+u*(t.B.Y-t.A.Y)+v*(t.C.Y-t.A.Y));
        }
        return height;
    }
    static void Main(string[] args)
    {
        foreach (var path in args)
        {
            var importer = new MyModelImporter();
            using (var reader = new BinaryReader(File.OpenRead(path)))
                typeof(MyModelImporter).GetMethod("LoadTagData", BindingFlags.Instance|BindingFlags.NonPublic)
                    .Invoke(importer, new object[]{reader, new[]{"Vertices", "MeshParts"}});
            var data = importer.GetTagData();
            var vertices = ((HalfVector4[])data["Vertices"]).Select(h => {
                var p = h.ToVector4(); return new Vector3(p.X,p.Y,p.Z)*p.W;
            }).ToArray();
            var triangles = new List<Triangle>();
            foreach (var part in (List<MyMeshPartInfo>)data["MeshParts"])
                for (int i = 0; i < part.m_indices.Count; i += 3)
                {
                    var a = vertices[part.m_indices[i]]; var b = vertices[part.m_indices[i+1]]; var c = vertices[part.m_indices[i+2]];
                    if (Math.Min(a.Y,Math.Min(b.Y,c.Y)) < 3.50) continue;
                    triangles.Add(new Triangle{A=a,B=b,C=c,Material=part.GetMaterialName()});
                }
            double minimum = double.PositiveInfinity;
            int samples = 0;
            foreach (double radius in new[]{2.10,2.25,2.32})
                for (int i = 0; i < 64; i++)
                {
                    double angle = (i+.37)*2*Math.PI/64, x = radius*Math.Cos(angle), z = radius*Math.Sin(angle);
                    double cap = Height(triangles,x,z,"PaintedMetal_Darker");
                    // Newly cut pocket floor uses the native machined-metal material.
                    double backing = Math.Max(Height(triangles,x,z,"PaintedMetal_Colorable"),Height(triangles,x,z,"Metal_Dull"));
                    if (double.IsInfinity(cap) || double.IsInfinity(backing) || cap-backing < .01)
                        throw new Exception(Path.GetFileName(path)+": roof surfaces missing/overlapping at radius "+radius+", sample "+i+", cap "+cap+", backing "+backing);
                    minimum = Math.Min(minimum,cap-backing); samples++;
                }
            Console.WriteLine("PASS: "+Path.GetFileName(path)+" / "+samples+" roof samples / minimum packed clearance "+(minimum*1000).ToString("F2")+" mm");
        }
    }
}
