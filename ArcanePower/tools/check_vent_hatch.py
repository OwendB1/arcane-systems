"""Check native hatch closure and clearance using the production outlet motion."""
import os
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from prepare_lab import ROOT, MOD, GAME


def main():
    blocks={b.findtext('Id/SubtypeId'):b for b in ET.parse(MOD/'Data/CubeBlocks/ArcanePower_Vents.sbc').findall('CubeBlocks/Definition')}
    assert blocks['ArcanePower_VentOutlet'].findtext('IsAirTight')=='true'
    assert blocks['ArcanePower_VentDuct'].findtext('IsAirTight')=='false'
    scripts=MOD/'Data/Scripts/ArcanePower'
    motion=(scripts/'Reactor.Motion.cs').read_text()
    easing=motion[motion.index('        private static float Ease('):motion.index('        private Matrix Rest(')]
    outlet=(scripts/'Reactor.VentRoute.cs').read_text()
    translation=re.search(r'pose\.Translation \+=.*?;',outlet,re.S).group().replace('Motion.Intake','opening')
    source=r'''
using System;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Collections.Generic;
using VRageMath;
using VRageMath.PackedVector;
using VRageRender.Import;
using ArcanePower;
class Check {
 static int checks;
 static void Need(bool condition,string message){checks++;if(!condition)throw new Exception(message);}
 EASING
 static Dictionary<string,object> Read(string path){
  var importer=new MyModelImporter();
  using(var reader=new BinaryReader(File.OpenRead(path)))
   typeof(MyModelImporter).GetMethod("LoadTagData",BindingFlags.Instance|BindingFlags.NonPublic)
    .Invoke(importer,new object[]{reader,new[]{"Vertices","MeshParts","Dummies","LODs"}});
  return importer.GetTagData();
 }
 static Vector3[] Points(Dictionary<string,object> tags){
  return ((HalfVector4[])tags["Vertices"]).Select(v=>{var p=v.ToVector4();return new Vector3(p.X,p.Y,p.Z)*p.W;}).ToArray();
 }
 static void Triangles(List<Vector3[]> triangles,Dictionary<string,object> tags,Matrix pose){
  var points=Points(tags).Select(p=>Vector3.Transform(p,pose)).ToArray();
  foreach(var part in (List<MyMeshPartInfo>)tags["MeshParts"])
   for(int n=0;n<part.m_indices.Count;n+=3)
    triangles.Add(new[]{points[part.m_indices[n]],points[part.m_indices[n+1]],points[part.m_indices[n+2]]});
 }
 static bool Covered(List<Vector3[]> triangles,float x,float z){
  foreach(var t in triangles){
   var a=t[0];var b=t[1]-a;var c=t[2]-a;
   double cross=b.X*c.Z-b.Z*c.X;if(Math.Abs(cross)<1e-10)continue;
   double u=((x-a.X)*c.Z-(z-a.Z)*c.X)/cross;
   double v=(b.X*(z-a.Z)-b.Z*(x-a.X))/cross;
   if(u>=-1e-5 && v>=-1e-5 && u+v<=1.00001)return true;
  }
  return false;
 }
 static void Main(string[] args){
  var parent=Read(args[0]);var dummies=(Dictionary<string,MyModelDummy>)parent["Dummies"];
  var dummy=dummies["subpart_OutletHatch1"];
  var leafPath=Path.Combine(Path.GetDirectoryName(args[0]),(string)dummy.CustomData["file"]+".mwm");
  var leaf=Read(leafPath);var levels=new List<Dictionary<string,object>>{leaf};
  foreach(var lod in (MyLODDescriptor[])leaf["LODs"])levels.Add(Read(Path.Combine(args[1],lod.Model.Replace('\\','/'))));
  foreach(var mesh in levels){
   var closed=new List<Vector3[]>();Triangles(closed,parent,Matrix.Identity);
   var opened=new List<Vector3[]>();Triangles(opened,parent,Matrix.Identity);
   for(int i=0;i<4;i++){
    Matrix rest=dummies["subpart_OutletHatch"+(i+1)].Matrix;
    for(int sample=0;sample<=100;sample++){
     float opening=sample/100f;Matrix pose=rest;
     TRANSLATION
     foreach(var p in Points(mesh).Select(v=>Vector3.Transform(v,pose))){
      Need(Math.Abs(p.X)<3.65 && Math.Abs(p.Z)<3.65,"Hatch leaves casing");
      if(opening>.3f)Need(p.Y>.70 && p.Y<1.0,"Hatch does not clear storage pocket");
     }
     if(sample==0)Triangles(closed,mesh,pose);
     if(sample==100)Triangles(opened,mesh,pose);
    }
   }
   for(int n=-185;n<=185;n++){
    float v=n*.01f;
    Need(Covered(closed,v,0) && Covered(closed,0,v),"Open leaf seam");
   }
   for(int n=0;n<128;n++){
    float angle=(float)(n*Math.PI/64);float x=(float)Math.Cos(angle),z=(float)Math.Sin(angle);
    Need(Covered(closed,1.852f*x,1.852f*z),"Open perimeter seal");
    Need(!Covered(opened,1.82f*x,1.82f*z),"Ejection bore blocked when open");
   }
   Need(!Covered(opened,0,0),"Open hatch blocks centre");
   foreach(int x in new[]{-1,1})foreach(int z in new[]{-1,1})Need(Covered(closed,3.74f*x,3.74f*z),"Open hull corner");
  }
  Console.WriteLine("PASS: "+checks+" native hatch closure, full-travel and LOD checks; outlet airtight definition");
 }
}
'''.replace('EASING',easing).replace('TRANSLATION',translation)
    with tempfile.TemporaryDirectory(prefix='arcane-hatch-') as directory:
        work=Path(directory);cs=work/'Check.cs';cs.write_text(source);exe=work/'Check.exe'
        subprocess.run(['mcs','-out:'+str(exe),'-r:/usr/lib/mono/4.5/Facades/netstandard.dll',
                        *['-r:'+str(GAME/'Bin64'/(n+'.dll')) for n in ('VRage.Render','VRage.Math','VRage.Library')],
                        str(scripts/'AnimationGeometry.cs'),str(cs)],check=True)
        subprocess.run(['mono',str(exe),str(MOD/blocks['ArcanePower_VentOutlet'].findtext('Model')),str(MOD)],
                       env={**os.environ,'MONO_PATH':str(GAME/'Bin64')},check=True)


if __name__=='__main__':main()
