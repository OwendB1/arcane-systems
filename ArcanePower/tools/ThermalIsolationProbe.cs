// Compare compiled valve vertices with live-Blender samples using shipped poses.
using System;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Collections.Generic;
using System.Web.Script.Serialization;
using VRageMath;
using VRageMath.PackedVector;
using VRageRender.Import;
using ArcanePower;

class ThermalIsolationProbe
{
    static void Require(bool ok, string message) { if (!ok) throw new Exception(message); }
    static Dictionary<string,object> Read(string path)
    {
        var importer=new MyModelImporter();
        using(var reader=new BinaryReader(File.OpenRead(path)))
            typeof(MyModelImporter).GetMethod("LoadTagData",BindingFlags.Instance|BindingFlags.NonPublic)
                .Invoke(importer,new object[]{reader,new[]{"Vertices","TexCoords0","ModelInfo","MeshParts","Dummies","HavokCollisionGeometry"}});
        return importer.GetTagData();
    }
    static int Main(string[] args)
    {
        var json=new JavaScriptSerializer{MaxJsonLength=int.MaxValue};
        var source=(Dictionary<string,object>)json.DeserializeObject(File.ReadAllText(args[0]));
        var points=new Dictionary<string,Vector3[]>();
        var textures=new HashSet<string>();
        Require(new HashSet<string>(((Dictionary<string,object>)source["models"]).Keys)
            .SetEquals(new[]{"ArcaneIsolationSeat","ArcaneIsolationGate"}),"Missing reactor valve mesh");
        foreach(var row in (Dictionary<string,object>)source["models"])
        {
            var data=Read(Path.Combine(args[1],row.Key+".mwm"));
            var model=(MyModelInfo)data["ModelInfo"];
            Require(model.TrianglesCount==Convert.ToInt32(((Dictionary<string,object>)row.Value)["triangles"]),"Native triangle count: "+row.Key);
            Require(model.TrianglesCount<1000,"Valve needs LODs");
            object physics;
            Require(!data.TryGetValue("HavokCollisionGeometry",out physics)||((byte[])physics).Length==0,"Cosmetic valve has collision");
            points[row.Key]=((HalfVector4[])data["Vertices"]).Select(v=>{var p=v.ToVector4();return new Vector3(p.X,p.Y,p.Z)*p.W;}).ToArray();
            var uv=(HalfVector2[])data["TexCoords0"];
            foreach(var part in (List<MyMeshPartInfo>)data["MeshParts"])
            {
                Require(part.m_MaterialDesc!=null && part.m_MaterialDesc.Textures.Count>0,"Shaderless native valve");
                foreach(var texture in part.m_MaterialDesc.Textures.Values) if(!String.IsNullOrEmpty(texture)) textures.Add(texture);
                for(int i=0;i<part.m_indices.Count;i+=3)
                {
                    var a=uv[part.m_indices[i]].ToVector2();
                    var b=uv[part.m_indices[i+1]].ToVector2()-a;
                    var c=uv[part.m_indices[i+2]].ToVector2()-a;
                    Require(Math.Abs(b.X*c.Y-b.Y*c.X)>1e-10,"Degenerate native UV triangle: "+row.Key+" / "+part.GetMaterialName());
                }
            }
            var dummies=(Dictionary<string,MyModelDummy>)data["Dummies"];
            if(row.Key.EndsWith("Seat"))
            {
                var gate=dummies["subpart_Gate"];
                Require((string)gate.CustomData["file"]=="ArcaneIsolationGate","Wrong gate dependency");
                Require(gate.Matrix.Translation.Length()<.0001f
                    && Vector3.Distance(gate.Matrix.Right,Vector3.Right)<.0001f
                    && Vector3.Distance(gate.Matrix.Up,Vector3.Up)<.0001f
                    && Vector3.Distance(gate.Matrix.Backward,Vector3.Backward)<.0001f,"Gate dummy not identity");
            }
        }
        int checks=0;double maximum=0;
        var reactor=ThermalModels.All.Values.Single(m=>m.Kind==ThermalKind.Reactor);
        Require(reactor.Ports.Length==4,"Expected four reactor valve mounts");
        // The sliding reactor stem is narrower than the external pipe block.
        // Test the exported vertices through full travel inside its faceted ID.
        double boreRadius=Convert.ToDouble(source["bore_radius"]);
        int boreSides=Convert.ToInt32(source["bore_sides"]);
        Require(boreRadius>0 && boreSides>=3,"Invalid reactor bore contract");
        double boreLimit=boreRadius*Math.Cos(Math.PI/boreSides);
        double minimumClearance=double.MaxValue;
        int clearanceChecks=0;
        foreach(var port in reactor.Ports) foreach(int side in new[]{-1,1})
        {
            var seat=ThermalIsolation.Seat(port,side);
            var mouth=port.Position+port.HotAxis*(side*ThermalIsolation.BoreOffset);
            foreach(var mesh in points) for(int degrees=0;degrees<=(mesh.Key.EndsWith("Gate")?90:0);degrees+=5)
            {
                var turn=mesh.Key.EndsWith("Gate")?ThermalIsolation.Gate(degrees/90.0):Matrix.Identity;
                foreach(var vertex in mesh.Value)
                {
                    var offset=Vector3.Transform(vertex,turn*seat)-mouth;
                    float depth=Vector3.Dot(offset,port.Normal);
                    Require(depth<-.005f,"Valve protrudes through connector mouth: "+mesh.Key);
                    double clearance=boreLimit-(offset-port.Normal*depth).Length();
                    Require(clearance>.001,"Valve leaves reactor bore clearance: "+mesh.Key+" / "+degrees);
                    minimumClearance=Math.Min(minimumClearance,clearance);
                }
                clearanceChecks++;
            }
        }
        var covered=new HashSet<string>();
        foreach(Dictionary<string,object> row in (object[])source["samples"])
        {
            Require((string)row["subtype"]==reactor.Subtype,"Valve samples must cover reactor mounts only");
            int index=Convert.ToInt32(row["port"]);
            Require(index>=0&&index<reactor.Ports.Length,"Unknown reactor valve mount");
            var spec=reactor;
            var port=spec.Ports[index];
            int side=Convert.ToInt32(row["side"]);
            string name=(string)row["model"];
            double opening=Convert.ToDouble(row["opening"]);
            Require(side==-1||side==1,"Unknown reactor bore");
            Require(points.ContainsKey(name),"Unknown valve mesh");
            Require(opening>=0&&opening<=1&&opening*4==Math.Floor(opening*4)
                &&(name.EndsWith("Gate")||opening==0),"Unknown valve pose");
            Require(covered.Add(index+"/"+side+"/"+name+"/"+(int)(opening*4)),"Duplicate reactor valve sample");
            var seat=ThermalIsolation.Seat(port,side);
            var turn=name.EndsWith("Gate")?ThermalIsolation.Gate(opening):Matrix.Identity;
            var box=BoundingBox.CreateInvalid();
            foreach(var v in points[name])
            {
                var point=Vector3.Transform(v,turn*seat);box.Include(point);
            }
            var expected=(object[])row["bounds"];
            double error=0;
            for(int end=0;end<2;end++) for(int axis=0;axis<3;axis++)
                error=Math.Max(error,Math.Abs((end==0?box.Min:box.Max).GetDim(axis)-Convert.ToDouble(((object[])expected[end])[axis])));
            Require(error<.002,"Native valve pose differs from authored sample: "+spec.Subtype+" "+name+" / "+error);
            maximum=Math.Max(maximum,error);checks++;
        }
        Require(covered.Count==reactor.Ports.Length*2*6,"Missing reactor bore or valve pose");
        Console.WriteLine(json.Serialize(new{status="passed",checks,maximum_error_m=maximum,
            clearance_checks=clearanceChecks,minimum_wall_clearance_m=minimumClearance,textures=textures.ToArray()}));
        return 0;
    }
}
