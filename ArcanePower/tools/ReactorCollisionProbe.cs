using System;using System.IO;using System.Collections.Generic;using System.Reflection;using System.Runtime.InteropServices;
class Entry {
 [DllImport("kernel32.dll",CharSet=CharSet.Unicode)] static extern bool SetDllDirectory(string p);
 static void Main(string[] args){
  var game=args[0];SetDllDirectory(game);
  AppDomain.CurrentDomain.AssemblyResolve+=(s,e)=>{var p=Path.Combine(game,new AssemblyName(e.Name).Name+".dll");return File.Exists(p)?Assembly.LoadFrom(p):null;};
  Probe.Run(args[1]);
 }
}
class Lock:VRage.Library.Threading.ISharedCriticalSection {
 public VRage.Library.Threading.SharedCriticalSection_UniqueLock EnterUnique(){return new VRage.Library.Threading.SharedCriticalSection_UniqueLock(this);}
 public VRage.Library.Threading.SharedCriticalSection_SharedLock EnterShared(){return new VRage.Library.Threading.SharedCriticalSection_SharedLock(this);}
 public void LeaveUnique_Internal(){} public void LeaveShared_Internal(){} public void Dispose(){}
}
class Probe {
 public static void Run(string path){
  Havok.HkBaseSystem.Init(Console.WriteLine,false,new Lock());
  var shapes=new List<Havok.HkShape>();bool scene,destruction;
  Console.WriteLine("Loaded="+Havok.HkShapeLoader.LoadShapesListFromBuffer(File.ReadAllBytes(path),shapes,out scene,out destruction)+" count="+shapes.Count);
  var world=new Havok.HkWorld(false,100,1,false,4);
  foreach(var shape in shapes){
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
    if(!world.CastRay(new VRageMath.Vector3(x*radius,-1,z*radius),new VRageMath.Vector3(x*radius,-4,z*radius),out hit,0,false)||Math.Abs(hit.Position.Y+1.26)>.02)throw new Exception("Missing deck "+i);contacts++;
    if(!world.CastRay(new VRageMath.Vector3(x*radius,4.5f,z*radius),new VRageMath.Vector3(x*radius,2,z*radius),out hit,0,false)||Math.Abs(hit.Position.Y-3.75)>.02)throw new Exception("Missing roof "+i);contacts++;
   }
  }
  Console.WriteLine("PASS native Havok world: "+contacts+" base side/deck/roof contacts across128 angles");
 }
}
