"""Prove actual tablet rendering/lifetime/access code with engine doubles and native MWM data."""
from pathlib import Path
import os
import subprocess
import tempfile
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src/Data/Scripts/ArcanePower'
GAME = Path.home() / '.local/share/Steam/steamapps/common/SpaceEngineers/Bin64'
status = (SRC / 'Reactor.Status.cs').read_text()
types = status[status.index('    internal sealed class StatusRow'):]
stubs = r'''
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text;
using VRage.Game.GUI.TextPanel;
using VRageMath;
using VRageMath.PackedVector;
using VRageRender.Import;
namespace Sandbox.Game.Entities {
 public class ToolRender { public uint[] RenderObjectIDs=new uint[]{7}; }
 public class ToolId { public string SubtypeName="ArcanePower_Tablet"; }
 public class MyHandToolBase {
  public ToolRender Render=new ToolRender(); public object Components=new object();
  public ToolId DefinitionId=new ToolId(); public long EntityId=123; public bool Closed;
  public float Backlight; public Color BacklightColor;
  public void SetEmissiveParts(string part,Color color,float emissivity){
   if(Closed)throw new Exception("do not update closed tool");
   if(part=="ArcaneTabletScreen"){Backlight=emissivity;BacklightColor=color;}
  }
 }
}
namespace Sandbox.Game.Components {
 public class MyRenderComponentScreenAreas {
  public static int Created,Released,Restored,Draws;
  public static List<MySprite> Last;
  public bool IsUpdateModelPropertiesEnabled=true;
  Sandbox.Game.Entities.MyHandToolBase owner;
  public MyRenderComponentScreenAreas(Sandbox.Game.Entities.MyHandToolBase entity){owner=entity;}
  public void SetContainer(object value){}
  public void AddScreenArea(uint[] ids,string material){if(material!="ArcaneTabletScreen")throw new Exception("wrong material");}
  public void CreateTexture(int area,Vector2I size){Created++;}
  public void ReleaseTexture(int area,bool empty){Released++;if(empty)throw new Exception("must not bind empty texture during release");}
  public string GenerateOffscreenTextureName(long id,int area){return "LCDOffscreenTexture_"+id;}
  public void ChangeTexture(int area,string path){if(IsUpdateModelPropertiesEnabled)throw new Exception("do not alter tool visibility");if(path==null)Restored++;}
  public void RenderSpritesToTexture(int area,VRage.Collections.ListReader<MySprite> sprites,Vector2I size,Vector2 aspect,Color color,byte alpha){Last=sprites.ToList();Draws++;}
 }
}
namespace Sandbox.ModAPI {
 public static class MyAPIGateway {
  public static class Utilities { public static bool IsDedicated; }
  public static class Session { public static Player Player=new Player(); }
  public static class Gui { public static bool IsCursorVisible,ChatEntryVisible; }
  public static class Input {
   public static bool Left,Right;
   public static bool IsNewLeftMousePressed(){return Left;} public static bool IsNewRightMousePressed(){return Right;}
  }
 }
 public class Player { public Character Character=new Character(); }
 public class Character { public object EquippedTool; }
}
namespace ArcanePower {
 class Reactor { public long Id=42;public StatusReport Report;public StatusReport ReadStatus(bool detailed){return Report;} }
 static class VentSession { public static List<Reactor> All=new List<Reactor>();public static Reactor Find(long id){return All.Find(r=>r.Id==id);} }
 static class TabletLink { public static bool Allowed=true;public static bool CanRead(Reactor r,out string reason){reason=r==null?"No reactor linked":"Antenna disconnected";return r!=null && Allowed;} }
''' + types + r'''
namespace ArcanePower {
 class Check {
  static float glyphHeight;
  static void Need(bool value,string message){if(!value)throw new Exception(message);}
  static void Near(float a,float b,string message){Need(Math.Abs(a-b)<.01,message);}
  static StatusReport Report(bool precharging=false,bool waiting=false,bool brayton=false){
   var report=new StatusReport{Name="Arcane Reactor",State=precharging?(waiting?"STARTUP WAITING FOR POWER  /  50%":"CHARGING STARTUP RESERVE  /  50%"):brayton?"REACTOR OVERHEATING / FAILURE RISK":"RUNNING",Tone=precharging?"white":brayton?"red":"green",Fuel="Aether",Precharging=precharging,Brayton=brayton,Reserve=.5};
   string[] labels={"Output","Heat","Reserve","Fuel stock","Spare tiles","Vent","Net","Ramp","Containment","Fuel efficiency","Fuel burn","Fuel remaining","Security mode","Integrity","Controllers","Field","Reserve energy","Tile grade","Quartet wear","Replacing","Dismantle at","Tile demand","Tile reserve","Tile stock","Startup tiles","Conveyors","Route","Doors"};
   foreach(string label in labels)report.Rows.Add(new StatusRow{Section="TEST",Label=label,Value=label=="Fuel stock"?"4991.814 units":label=="Tile stock"?"Standard 308 / Reinforced 0 / Advanced 0":"Test reading",Tone="white"});
   if(brayton){
    string[] coolingLabels={"Circuits available","Conversion efficiency","Cooling capacity","Cooling required","Returned waste","Startup / cooldown draw"};
    string[] coolingValues={"4 / 4 (100% allocation)","78%","15 GW","21 GW at design load","12345678.0 MJ","500 MW"};
    for(int i=0;i<coolingLabels.Length;i++)report.Rows.Add(new StatusRow{Section="POWER",Label=coolingLabels[i],Value=coolingValues[i],Tone="yellow"});
   }
   if(precharging){
    report.Rows.Add(new StatusRow{Section="POWER",Label="Startup charge",Value="50%",Tone="white"});
    report.Rows.Add(new StatusRow{Section="POWER",Label="Charge rate",Value=waiting?"0 MW net":"3 MW net",Tone="white"});
    report.Rows.Add(new StatusRow{Section="POWER",Label="Charge ETA",Value=waiting?"Waiting for surplus power":"~15 s",Tone="white"});
   }
   return report;
  }
  static void Layout(){
   foreach(var report in new[]{Report(),Report(true),Report(true,true),Report(false,false,true),Report(true,false,true)})
   for(int alerts=0;alerts<=2;alerts++){
    if(alerts>0)report.Rows.Add(new StatusRow{Section=null,Label="",Value="Repair the vent route urgently; core cannot eject.",Tone="red"});
    for(int page=0;page<5;page++){
     var sprites=ReactorDashboard.DrawTablet(report,page,"unused");
     foreach(var sprite in sprites){
      if(sprite.Type==SpriteType.TEXT){
       var p=sprite.Position.Value;
       Need(p.X>=0 && p.Y>=0 && p.Y+sprite.RotationOrScale*37<ReactorDashboard.TabletHeight,"text fits physical screen height");
       Need(p.X+sprite.Data.Length*20*sprite.RotationOrScale<=ReactorDashboard.TabletWidth+1,"text fits physical screen width");
       float rasterHeight=sprite.RotationOrScale*(1024/ReactorDashboard.TabletHeight)*glyphHeight;
       Need(rasterHeight>=24,"every page retains readable native glyphs");
      }
     }
     Need(sprites.Any(s=>s.Type==SpriteType.TEXT && s.Data.Contains(ReactorDashboard.Pages[page].ToUpperInvariant())),"every page has its title");
     if(report.Precharging){
      var bar=sprites.Single(s=>s.Type==SpriteType.TEXTURE && s.Size.Value==new Vector2(302,3));
      Need(bar.Color==ReactorDashboard.Tone("white"),"tablet shows neutral charge progress on every page");
      var heading=sprites.Single(s=>s.Type==SpriteType.TEXT && s.Data==report.State);
      Need(heading.Position.Value.Y+heading.RotationOrScale*37<=bar.Position.Value.Y-1.5f,"charge bar clears state text");
     }
     var lcd=ReactorDashboard.Draw(report,page,"unused","LCD / "+ReactorDashboard.Pages[page]);
     Need(lcd.Any(s=>s.Data==(report.Precharging?"STARTUP CHARGE":"EMERGENCY RESERVE")),"LCD identifies charge or reserve correctly");
     if(report.Precharging && page<=1){
      foreach(var label in new[]{"Containment","Charge rate","Charge ETA","Reserve energy","Net"}){
       Need(sprites.Any(s=>s.Data==label) && lcd.Any(s=>s.Data==label),"both overview/power pages show "+label);
       Need(sprites.Any(s=>s.Data==report.Value(label)) && lcd.Any(s=>s.Data==report.Value(label)),"both screens show live "+label);
      }
     }
     if(report.Brayton && !report.Precharging && page==1){
      foreach(var label in new[]{"Circuits available","Conversion efficiency","Cooling capacity","Cooling required","Returned waste"}){
       Need(sprites.Any(s=>s.Data==label) && lcd.Any(s=>s.Data==label),"both power pages show "+label);
       Need(sprites.Any(s=>s.Data==report.Value(label)) && lcd.Any(s=>s.Data==report.Value(label)),"both power pages show live "+label);
      }
     }
    }
   }
   Need(ReactorDashboard.DrawTablet(null,0,"Suit and grid antennas must have a bidirectional connection.").Any(s=>s.Data=="DISCONNECTED"),"offline screen clears telemetry");
   Console.WriteLine("PASS: normal/charging/waiting/Brayton pages, progress bars and live LCD/tablet metrics fit with up to two alerts");
  }
  static void Lifetime(){
   var tool=new Sandbox.Game.Entities.MyHandToolBase();var original=tool.Render;var screen=new TabletScreen();
   var sprites=ReactorDashboard.DrawTablet(Report(),3,"");
   tool.Render.RenderObjectIDs=new[]{uint.MaxValue};Need(!screen.Draw(tool,sprites),"wait for native render IDs");
   Need(tool.Backlight==0,"unready panel remains dark");
   tool.Render.RenderObjectIDs=new uint[]{7};Need(screen.Draw(tool,sprites),"bind native screen when ready");
   Need(tool.Backlight==2 && tool.BacklightColor==Color.White,"active panel has a neutral backlight");
   var rendered=Sandbox.Game.Components.MyRenderComponentScreenAreas.Last;
   var background=rendered[0];var aspect=new Vector2(.270f/.174f,1);var shift=new Vector2(1024,1024)*(aspect-Vector2.One)/2;
   float nativeScale=1024*aspect.X/ReactorDashboard.TabletWidth;
   for(int i=0;i<rendered.Count;i++){
    var sprite=rendered[i];var source=sprites[i];
    // Native screen renderer adds shift, then the sprite shader divides by
    // Resolution * aspect. Check the final sampled texture coordinates.
    var sampled=(sprite.Position.Value+shift)/new Vector2(1024*aspect.X,1024);
    Near(sampled.X,source.Position.Value.X/ReactorDashboard.TabletWidth,"sampled X origin fits screen");
    Near(sampled.Y,source.Position.Value.Y/ReactorDashboard.TabletHeight,"sampled Y origin fits screen");
    if(sprite.Type==SpriteType.TEXT){
     Near(sprite.RotationOrScale/nativeScale,source.RotationOrScale,"font and position share canvas units");
     float height=sprite.RotationOrScale*glyphHeight;
     Need(height>=24 && height<=70,"native glyphs remain readable before mipmapping");
     Need((sprite.Position.Value+shift).Y+height<=1024,"native glyphs stay inside texture");
    }
   }
   Near((background.Position.Value+shift).X-background.Size.Value.X/2,0,"texture starts at left edge");
   Near(background.Size.Value.X,1024*aspect.X,"use full display width");Near(background.Size.Value.Y,1024,"use full display height");
   Need(object.ReferenceEquals(tool.Render,original),"keep native hand renderer");
   for(int i=0;i<20;i++)screen.Draw(tool,sprites);
   Need(Sandbox.Game.Components.MyRenderComponentScreenAreas.Created==1,"reuse one generated texture");
   tool.Render.RenderObjectIDs=new uint[]{8};screen.Draw(tool,sprites);
   Need(Sandbox.Game.Components.MyRenderComponentScreenAreas.Created==2 && Sandbox.Game.Components.MyRenderComponentScreenAreas.Released==1,"rebind replaced render IDs and free old texture");
   var next=new Sandbox.Game.Entities.MyHandToolBase{EntityId=456};screen.Draw(next,sprites);
   Need(tool.Backlight==0 && next.Backlight==2,"switching tools transfers active backlight");
   screen.Release();screen.Release();
   Need(next.Backlight==0,"release switches backlight off");
   Need(Sandbox.Game.Components.MyRenderComponentScreenAreas.Created==Sandbox.Game.Components.MyRenderComponentScreenAreas.Released,"switch/unequip frees every texture exactly once");
   screen.Draw(next,sprites);next.Closed=true;screen.Release();
   Need(Sandbox.Game.Components.MyRenderComponentScreenAreas.Created==Sandbox.Game.Components.MyRenderComponentScreenAreas.Released,"closing entity also frees texture");
   Console.WriteLine("PASS: native render-ID readiness/rebinding, aspect/scale, renderer ownership and texture cleanup");
  }
  static void Access(){
   var tablet=new ReactorTablet();var tool=new Sandbox.Game.Entities.MyHandToolBase();
   Sandbox.ModAPI.MyAPIGateway.Session.Player.Character.EquippedTool=tool;
   VentSession.All.Add(new Reactor{Report=Report()});Sandbox.ModAPI.MyAPIGateway.Input.Left=true;
   tablet.UpdateAfterSimulation();Sandbox.ModAPI.MyAPIGateway.Input.Left=false;
   Need(Sandbox.Game.Components.MyRenderComponentScreenAreas.Last.Any(s=>s.Data=="4991.814 units"),"selected accessible reactor renders live values");
   TabletLink.Allowed=false;
   for(int i=0;i<10;i++)tablet.UpdateAfterSimulation();
   Need(Sandbox.Game.Components.MyRenderComponentScreenAreas.Last.Any(s=>s.Data=="DISCONNECTED") && !Sandbox.Game.Components.MyRenderComponentScreenAreas.Last.Any(s=>s.Data=="4991.814 units"),"antenna/access loss removes stale readings");
   Need(tool.Backlight==2,"disconnected message stays backlit");
   Sandbox.ModAPI.MyAPIGateway.Gui.ChatEntryVisible=true;tablet.UpdateAfterSimulation();
   Need(tool.Backlight==0,"opening chat turns off the hidden panel");
   Need(Sandbox.Game.Components.MyRenderComponentScreenAreas.Created==Sandbox.Game.Components.MyRenderComponentScreenAreas.Released,"opening chat releases native display");
   Sandbox.ModAPI.MyAPIGateway.Gui.ChatEntryVisible=false;TabletLink.Allowed=true;
   Sandbox.ModAPI.MyAPIGateway.Input.Right=true;tablet.UpdateAfterSimulation();Sandbox.ModAPI.MyAPIGateway.Input.Right=false;
   Need(Sandbox.Game.Components.MyRenderComponentScreenAreas.Last.Any(s=>s.Data=="ARCANE / POWER"),"right click changes physical screen page");
   Sandbox.ModAPI.MyAPIGateway.Session.Player.Character.EquippedTool=null;tablet.UpdateAfterSimulation();
   Need(tool.Backlight==0,"unequipping turns backlight off");
   Need(Sandbox.Game.Components.MyRenderComponentScreenAreas.Created==Sandbox.Game.Components.MyRenderComponentScreenAreas.Released,"unequipping releases display");
   Console.WriteLine("PASS: actual selection/page controls, antenna loss, menu visibility and unequip cleanup without Text HUD API");
  }
  static void Model(string path){
   var importer=new MyModelImporter();using(var reader=new BinaryReader(File.OpenRead(path)))
    typeof(MyModelImporter).GetMethod("LoadTagData",BindingFlags.Instance|BindingFlags.NonPublic).Invoke(importer,new object[]{reader,null});
   var data=importer.GetTagData();var parts=(List<MyMeshPartInfo>)data["MeshParts"];
   Need(!parts.Any(p=>p.GetMaterialName()=="ArcaneTabletCard"),"remove baked cards over live display");
   var screen=parts.Single(p=>p.GetMaterialName()=="ArcaneTabletScreen");
   var vertices=(HalfVector4[])data["Vertices"];var uv=(HalfVector2[])data["TexCoords0"];
   int front=0;
   foreach(int index in screen.m_indices.Distinct()){
    var packed=vertices[index];var p=VRage.Import.VF_Packer.UnpackPosition(ref packed);
    if(p.Z>-.0314f)continue;
    var t=uv[index].ToVector2();Near(t.X,(.135f-p.X)/.270f,"U increases toward viewer's right after tool Y half-turn");
    Near(t.Y,1-(p.Y-.012f+.087f)/.174f,"V increases downward on held screen");front++;
   }
   Need(front>=4,"native model contains mapped screen front");
   var light=parts.Single(p=>p.GetMaterialName()=="ArcaneTabletLight");
   foreach(int index in light.m_indices.Distinct()){
    var packed=vertices[index];var p=VRage.Import.VF_Packer.UnpackPosition(ref packed);
    Need(!(Math.Abs(p.X)<.134f && p.Y>-.074f && p.Y<.098f && p.Z<-.0314f),"no static light artwork occludes screen");
   }
   Console.WriteLine("PASS: native MWM screen material, front UV orientation and unobstructed live display");
  }
  static void Main(string[] args){
   var font=new System.Xml.XmlDocument();font.Load(args[1]);
   var glyph=font.SelectSingleNode("//*[local-name()='glyph' and @ch='A']");
   // MyRenderFont.DrawStringAligned applies this native font-unit conversion.
   glyphHeight=float.Parse(glyph.Attributes["size"].Value.Split('x')[1])*0.7783783674240112f;
   Layout();Lifetime();Access();Model(args[0]);
  }
 }
}
'''
for suffix in ('cm', 'ng', 'add'):
    with Image.open(ROOT / ('src/Textures/Models/ArcanePower/ArcaneTabletScreen_' + suffix + '.dds')) as texture:
        channels = texture.convert('RGBA').getextrema()
        assert all(low == high for low, high in channels), 'Inactive screen maps must be uniform'
        assert channels[3][1] <= (25 if suffix == 'ng' else 4), 'Matte gloss / nonmetallic / paint masks preserved'
        if suffix == 'cm':
            assert all(channels[i][1] == 0 for i in range(3)), 'Inactive screen must be black'
        if suffix == 'add':
            assert channels[1][0] >= 250, 'Screen emission mask must support the live backlight'
print('PASS: uniform matte black base DDS maps with preserved packed alpha', flush=True)
with tempfile.TemporaryDirectory(prefix='arcane-tablet-screen-') as directory:
    path = Path(directory)
    stub = path / 'check.cs'
    stub.write_text(stubs)
    exe = path / 'check.exe'
    subprocess.run(['mcs', '-warn:0', '-r:/usr/lib/mono/4.5/Facades/netstandard.dll',
                    *['-r:' + str(GAME / name) for name in ('VRage.dll', 'VRage.Math.dll', 'VRage.Library.dll', 'VRage.Game.dll', 'VRage.Render.dll')],
                    '-out:' + str(exe), str(stub),
                    *[str(SRC / name) for name in ('TabletScreen.cs', 'ReactorTablet.cs', 'ReactorDashboard.cs')]], check=True)
    subprocess.run(['mono', str(exe), str(ROOT / 'src/Models/Items/ArcanePower_Tablet.mwm'),
                    str(GAME.parent / 'Content/Fonts/monospace/FontDataPA.xml')], check=True,
                   env={**os.environ, 'MONO_PATH': str(GAME)})
