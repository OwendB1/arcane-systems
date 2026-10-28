// Native SE/Havok checks shared by the sealed pipe rotor and radiator base.
using System;
using System.IO;
using System.Collections.Generic;
using System.Reflection;
using System.Runtime.InteropServices;
using Havok;
using VRageMath;
class CasingEntry {
 [DllImport("kernel32.dll",CharSet=CharSet.Unicode)] static extern bool SetDllDirectory(string path);
 static void Main(string[] args) {
  try {
   string game=args[0];SetDllDirectory(game);
   AppDomain.CurrentDomain.AssemblyResolve+=(s,e)=>{string p=Path.Combine(game,new AssemblyName(e.Name).Name+".dll");return File.Exists(p)?Assembly.LoadFrom(p):null;};
   CasingProbe.Run(args);
  } catch(Exception error) {Console.Error.WriteLine(error);Environment.ExitCode=1;}
 }
}
class CasingLock:VRage.Library.Threading.ISharedCriticalSection {
 public VRage.Library.Threading.SharedCriticalSection_UniqueLock EnterUnique(){return new VRage.Library.Threading.SharedCriticalSection_UniqueLock(this);}
 public VRage.Library.Threading.SharedCriticalSection_SharedLock EnterShared(){return new VRage.Library.Threading.SharedCriticalSection_SharedLock(this);}
 public void LeaveUnique_Internal(){} public void LeaveShared_Internal(){} public void Dispose(){}
}
class CasingProbe {
 public static void Run(string[] args) {
  HkBaseSystem.Init(Console.WriteLine,false,new CasingLock());
  for(int file=1;file<args.Length;file++) {
   var shapes=new List<HkShape>();bool scene,destruction;
   if(!HkShapeLoader.LoadShapesListFromBuffer(File.ReadAllBytes(args[file]),shapes,out scene,out destruction))throw new Exception("Cannot load casing collision");
   if(shapes.Count!=6)throw new Exception("Expected six flat casing hulls: "+args[file]);
   var world=new HkWorld(false,100,1,false,4);
   foreach(var shape in shapes) {
    if(shape.ShapeType!=HkShapeType.ConvexVertices)throw new Exception("Nested or non-convex casing hull");
    Vector3[] vertices;((HkConvexVerticesShape)shape).GetVertices(out vertices);
    foreach(var p in vertices)if(Math.Abs(p.X)>1.251||Math.Abs(p.Y)>1.251||Math.Abs(p.Z)>1.251)throw new Exception("Collision leaves the one-cell casing");
    var translation=Vector3.Zero;var rotation=Quaternion.Identity;var scale=Vector3.One;
    var transformed=new HkConvexTransformShape((HkConvexShape)shape,ref translation,ref rotation,ref scale,HkReferencePolicy.None);
    world.AddRigidBody(new HkRigidBody(new HkRigidBodyCinfo{Shape=transformed,MotionType=HkMotionType.Fixed}));
   }
   int contacts=0,clear=0;
   var axes=new[]{Vector3.Right,Vector3.Up,Vector3.Backward};
   for(int axis=0;axis<3;axis++)foreach(float sign in new[]{-1f,1f})
    for(int u=-4;u<=4;u++)for(int v=-4;v<=4;v++) {
     Vector3 b=axes[(axis+1)%3]*(u*.24f)+axes[(axis+2)%3]*(v*.24f),a=b+axes[axis]*(sign*2);
     HkHitInfo hit;
     bool deck=Path.GetFileName(args[file]).StartsWith("APT_SpaceRadiator_")&&axis==1&&sign>0;
     float low=deck?1.14f:1.19f,high=deck?1.17f:1.27f;
     if(!world.CastRay(a,b,out hit,0,false)||Math.Abs(Vector3.Dot(hit.Position,axes[axis]))<low||Math.Abs(Vector3.Dot(hit.Position,axes[axis]))>high)throw new Exception("Missing or displaced casing face: "+args[file]);contacts++;
    }
   // Native Y is Blender Z: no old panel, cuff or equipment collision above
   // the base/head cell. The next radiator panel starts beyond this plane.
   foreach(float y in new[]{1.26f,1.30f,2.5f,4f})for(int n=-5;n<=5;n++) {
    HkHitInfo hit;
    if(world.CastRay(new Vector3(-4,y,n*.24f),new Vector3(4,y,n*.24f),out hit,0,false))throw new Exception("Collision blocks the space above the casing");clear++;
   }
   Console.WriteLine("PASS "+Path.GetFileName(args[file])+": six flat hulls, "+contacts+" face contacts, "+clear+" clear upper sweeps");
   world.Dispose();foreach(var shape in shapes)shape.RemoveReference();
  }
 }
}
