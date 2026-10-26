using System;using System.IO;using System.Collections.Generic;using System.Reflection;using System.Runtime.InteropServices;
class Entry {
 [DllImport("kernel32.dll",CharSet=CharSet.Unicode)] static extern bool SetDllDirectory(string p);
 static void Main(string[] args){
  try {
  var game=args[0];SetDllDirectory(game);
  AppDomain.CurrentDomain.AssemblyResolve+=(s,e)=>{var p=Path.Combine(game,new AssemblyName(e.Name).Name+".dll");return File.Exists(p)?Assembly.LoadFrom(p):null;};
  if(args[1]=="--merge")Probe.Merge(args[2],args[3],args[4]);
  else Probe.Run(args[1]);
  } catch(Exception error){Console.Error.WriteLine(error);Environment.ExitCode=1;}
 }
}
class Lock:VRage.Library.Threading.ISharedCriticalSection {
 public VRage.Library.Threading.SharedCriticalSection_UniqueLock EnterUnique(){return new VRage.Library.Threading.SharedCriticalSection_UniqueLock(this);}
 public VRage.Library.Threading.SharedCriticalSection_SharedLock EnterShared(){return new VRage.Library.Threading.SharedCriticalSection_SharedLock(this);}
 public void LeaveUnique_Internal(){} public void LeaveShared_Internal(){} public void Dispose(){}
}
class Probe {
 static List<Havok.HkShape> Load(string path){
  var shapes=new List<Havok.HkShape>();bool scene,destruction;
  if(!Havok.HkShapeLoader.LoadShapesListFromBuffer(File.ReadAllBytes(path),shapes,out scene,out destruction))throw new Exception("Cannot load collision: "+path);
  return shapes;
 }
 public static void Merge(string original,string pillars,string output){
  Havok.HkBaseSystem.Init(Console.WriteLine,false,new Lock());
  var shapes=Load(original);var added=Load(pillars);
  if(shapes.Count!=10||added.Count!=4)throw new Exception("Expected ten accepted housing hulls and four pillar hulls");
  var flat=new List<Havok.HkShape>();var glass=new List<VRageMath.Vector3[]>();
  foreach(var shape in shapes){
   VRageMath.Vector3[] vertices;((Havok.HkConvexVerticesShape)shape).GetVertices(out vertices);
   float radius=0;foreach(var vertex in vertices)radius=Math.Max(radius,(float)Math.Sqrt(vertex.X*vertex.X+vertex.Z*vertex.Z));
   if(radius<5)glass.Add(vertices);else flat.Add(shape);
  }
  if(flat.Count!=2||glass.Count!=8)throw new Exception("Expected base/roof and eight glass hulls");
  glass.Sort((a,b)=>GlassAngle(a).CompareTo(GlassAngle(b)));
  // Four convex glass quadrants leave room for all four pillars within SE's
  // ten top-level shapes. Keep the accepted deck, roof and pillar hulls exact.
  for(int i=0;i<glass.Count;i+=2){
   var vertices=new List<VRageMath.Vector3>(glass[i]);vertices.AddRange(glass[i+1]);
   flat.Add(new Havok.HkConvexVerticesShape(vertices.ToArray(),vertices.Count,false,.01f));
  }
  flat.AddRange(added);
  var exportList=new Havok.HkListShape(flat.ToArray(),Havok.HkReferencePolicy.None);
  if(!Havok.HkShapeLoader.SaveShapesListToFile(output,exportList,false))throw new Exception("Collision save failed");
  Console.WriteLine("Saved ten flat hulls: unchanged deck/roof, four glass quadrants and four unchanged pillars");
 }
 static double GlassAngle(VRageMath.Vector3[] vertices){
  double x=0,z=0;foreach(var vertex in vertices){x+=vertex.X;z+=vertex.Z;}return Math.Atan2(z,x);
 }
 public static void Run(string path){
  Havok.HkBaseSystem.Init(Console.WriteLine,false,new Lock());
  var shapes=Load(path);
  // MyModel keeps at most ten top-level shapes. AddShapesCustom expands List
  // children but records shapes.Length; MyGridShape then consumes only that
  // recorded count. A fourteen-child List silently retains just its first hull.
  if(shapes.Count!=10)throw new Exception("Expected ten flat convex hulls for SE model/grid bookkeeping");
  foreach(var shape in shapes)
   if(shape.ShapeType!=Havok.HkShapeType.ConvexVertices)throw new Exception("Nested/non-convex shape cannot preserve SE grid shape counts");
  var world=new Havok.HkWorld(false,100,1,false,4);
  // Match both collector transforms and the count consumed by MyGridShape.
  for(int i=0;i<shapes.Count;i++){
   var translation=VRageMath.Vector3.Zero;var rotation=VRageMath.Quaternion.Identity;var scale=VRageMath.Vector3.One;
   var shape=new Havok.HkConvexTransformShape((Havok.HkConvexShape)shapes[i],ref translation,ref rotation,ref scale,Havok.HkReferencePolicy.None);
   var info=new Havok.HkRigidBodyCinfo{Shape=shape,MotionType=Havok.HkMotionType.Fixed};
   var body=new Havok.HkRigidBody(info);world.AddRigidBody(body);
  }
  int contacts=0;
  for(int i=0;i<128;i++){
   float a=(float)((i+.5)*Math.PI*2/128);float x=(float)Math.Cos(a),z=(float)Math.Sin(a);
   Havok.HkHitInfo hit;
   if(!world.CastRay(new VRageMath.Vector3(x*7,-2,z*7),new VRageMath.Vector3(0,-2,0),out hit,0,false))throw new Exception("Missing base side "+i);
   if(Math.Abs(Math.Sqrt(hit.Position.X*hit.Position.X+hit.Position.Z*hit.Position.Z)-6.24)>.03)throw new Exception("Base side bounds");contacts++;
   foreach(float radius in new[]{0f,2f,3.9f,5.3f,5.7f,6.1f}){
    if(!world.CastRay(new VRageMath.Vector3(x*radius,-1.24f,z*radius),new VRageMath.Vector3(x*radius,-4,z*radius),out hit,0,false)||Math.Abs(hit.Position.Y+1.26)>.02)throw new Exception("Missing deck "+i);contacts++;
    if(!world.CastRay(new VRageMath.Vector3(x*radius,4.5f,z*radius),new VRageMath.Vector3(x*radius,2,z*radius),out hit,0,false)||Math.Abs(hit.Position.Y-3.75)>.02)throw new Exception("Missing roof "+i);contacts++;
   }
  }
  Console.WriteLine("PASS native Havok world: "+contacts+" base side/deck/roof contacts across128 angles");
  int glassContacts=0;
  for(int i=0;i<128;i++){
   double angle=(i+.5)*Math.PI*2/128;
   var direction=new VRageMath.Vector3((float)Math.Cos(angle),0,(float)Math.Sin(angle));
   Havok.HkHitInfo hit;
   if(!world.CastRay(direction*5.02f,direction*2,out hit,0,false))throw new Exception("Missing glass quadrant "+i);
   double radius=Math.Sqrt(hit.Position.X*hit.Position.X+hit.Position.Z*hit.Position.Z);
   if(radius<4.85||radius>4.98)throw new Exception("Glass outer silhouette changed "+radius);glassContacts++;
  }
  Console.WriteLine("PASS glass: "+glassContacts+" contacts around all four quadrants");
  int pillarContacts=0,sweeps=0,clearPaths=0;
  // A 1.9 m tall, 0.6 m wide character surrogate, with its feet 40 mm above
  // the deck so floor contact cannot mask a missing pillar or block a clear path.
  var character=new Havok.HkCapsuleShape(new VRageMath.Vector3(0,.30f,0),new VRageMath.Vector3(0,1.60f,0),.30f);
  for(int i=0;i<4;i++){
   double angle=-Math.PI/4+i*Math.PI/2;
   var n=new VRageMath.Vector3((float)Math.Cos(angle),0,(float)Math.Sin(angle));
   var t=new VRageMath.Vector3(-n.Z,0,n.X);
   foreach(float height in new[]{-.9f,0f,.8f,2.4f}){
    Havok.HkHitInfo hit;var up=new VRageMath.Vector3(0,height,0);
    if(!world.CastRay(n*7+up,n*5+up,out hit,0,false)||Math.Abs(VRageMath.Vector3.Dot(hit.Position,n)-6.1f)>.03)throw new Exception("Missing outer pillar "+i);pillarContacts++;
    if(!world.CastRay(n*5+up,n*7+up,out hit,0,false)||Math.Abs(VRageMath.Vector3.Dot(hit.Position,n)-5.1f)>.03)throw new Exception("Missing inner pillar "+i);pillarContacts++;
    foreach(float side in new[]{-1f,1f}){
     if(!world.CastRay(n*5.6f+t*(side*1.4f)+up,n*5.6f+up,out hit,0,false)||Math.Abs(Math.Abs(VRageMath.Vector3.Dot(hit.Position,t))-.8f)>.03)throw new Exception("Missing pillar side "+i);pillarContacts++;
    }
   }
   foreach(float side in new[]{-1f,1f}){
    var start=n*5.8f+t*(side*1.5f)+new VRageMath.Vector3(0,-1.22f,0);
    var end=n*5.8f-t*(side*1.5f)+new VRageMath.Vector3(0,-1.22f,0);
    var transform=VRageMath.Matrix.CreateTranslation(start);
    var hit=world.CastShape(end,character,ref transform,0,0);
    if(!hit.HasValue||hit.Value<=0||hit.Value>=.5f)throw new Exception("Character walks through pillar "+i);sweeps++;
   }
   // Cardinal sections of the exterior ledge remain unobstructed.
   double clearAngle=i*Math.PI/2;
   var outward=new VRageMath.Vector3((float)Math.Cos(clearAngle),0,(float)Math.Sin(clearAngle));
   var across=new VRageMath.Vector3(-outward.Z,0,outward.X);
   var freeStart=outward*5.7f-across*.8f+new VRageMath.Vector3(0,-1.22f,0);
   var freeEnd=outward*5.7f+across*.8f+new VRageMath.Vector3(0,-1.22f,0);
   var freeTransform=VRageMath.Matrix.CreateTranslation(freeStart);
   if(world.CastShape(freeEnd,character,ref freeTransform,0,0).HasValue)throw new Exception("Blocked clear walkway "+i);clearPaths++;
  }
  Console.WriteLine("PASS pillars: "+pillarContacts+" face contacts, "+sweeps+" blocked character sweeps, "+clearPaths+" clear walkway sweeps");
 }
}
