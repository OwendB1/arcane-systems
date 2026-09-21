using System;
using System.Collections.Generic;
using System.Text;
using Draygo.API;
using Sandbox.Game.Entities;
using Sandbox.ModAPI;
using VRage.Game.Components;
using VRage.Game.GUI.TextPanel;
using VRage.Utils;
using VRageMath;

namespace ArcanePower
{
    [MySessionComponentDescriptor(MyUpdateOrder.AfterSimulation)]
    public sealed class ReactorTablet : MySessionComponentBase
    {
        private HudAPIv2 api;
        private readonly List<HudAPIv2.HUDMessage> texts=new List<HudAPIv2.HUDMessage>();
        private readonly List<HudAPIv2.BillBoardHUDMessage> boxes=new List<HudAPIv2.BillBoardHUDMessage>();
        private VRage.Game.ModAPI.IMyHudNotification fallback;
        private readonly List<HudAPIv2.MessageBase> drawOrder=new List<HudAPIv2.MessageBase>();
        private long linked;
        private int page, tick;
        private bool wasHeld;
        public override void BeforeStart()
        {
            if(!MyAPIGateway.Utilities.IsDedicated) api=new HudAPIv2();
        }
        public override void UpdateAfterSimulation()
        {
            if(api==null) return;
            if(MyAPIGateway.Session.Player==null) { Hide(); return; }
            var character=MyAPIGateway.Session.Player.Character;
            var tool=character==null ? null : character.EquippedTool as MyHandToolBase;
            bool held=tool!=null && tool.DefinitionId.SubtypeName=="ArcanePower_Tablet";
            bool visible=held && !MyAPIGateway.Gui.IsCursorVisible && !MyAPIGateway.Gui.ChatEntryVisible;
            if(!visible) { if(wasHeld) Hide(); wasHeld=false; return; }
            bool select=MyAPIGateway.Input.IsNewLeftMousePressed();
            bool next=MyAPIGateway.Input.IsNewRightMousePressed();
            bool refresh=!wasHeld || select || next || ++tick%10==0;
            wasHeld=true;
            if(!refresh) return;
            if(next) page=(page+1)%ReactorDashboard.Pages.Length;
            if(select)
            {
                var available=new List<Reactor>(); string ignored;
                foreach(var reactor in VentSession.All) if(TabletLink.CanRead(reactor,out ignored)) available.Add(reactor);
                available.Sort((a,b)=>a.Id.CompareTo(b.Id));
                int index=available.FindIndex(r=>r.Id==linked);
                linked=available.Count==0 ? 0 : available[(index+1)%available.Count].Id;
            }
            string reason;
            var target=VentSession.Find(linked);
            bool online=TabletLink.CanRead(target,out reason);
            // Never retain a report across refreshes: losing access clears live values.
            var report=online ? target.ReadStatus(true) : null;
            tool.SetEmissiveParts("ArcaneTabletLight", ReactorDashboard.Tone(online ? "cyan" : "yellow"), 1.5f);
            if(linked==0 && reason=="No reactor linked") reason="Left click to select an accessible reactor. Suit and grid antennas must have a bidirectional connection.";
            if(api.Heartbeat)
            {
                if(fallback!=null) fallback.Hide();
                Render(ReactorDashboard.Draw(report,page,reason,"LMB: select linked reactor   RMB: "+ReactorDashboard.Pages[(page+1)%5]+"   / READ ONLY"));
            }
            else
            {
                Hide();
                // Functional, live native readout when Text HUD API is not installed.
                // It is deliberately refreshed and hidden with the same access gate.
                if(fallback==null) fallback=MyAPIGateway.Utilities.CreateNotification("",250,"White");
                fallback.Hide();
                var plain=new StringBuilder("ARCANE TABLET / ");
                if(report==null) plain.Append(reason);
                else
                {
                    plain.Append(report.Name).Append(" / ").AppendLine(report.State);
                    string section=page==1 ? "POWER" : page==2 ? "CONTAINMENT" : "SUPPLIES & VENT";
                    foreach(var row in report.Rows)
                    {
                        bool include=row.Section==null || (page==0 ? (row.Label=="Output" || row.Label=="Heat" || row.Label=="Reserve" || row.Label=="Vent") : row.Section==section && row.Label.Length>0);
                        if(include) plain.Append(row.Label).Append(row.Label.Length>0 ? ": " : "").AppendLine(row.Value);
                    }
                }
                plain.Append("\nLMB: select reactor / RMB: page / ").Append(ReactorDashboard.Pages[page]);
                fallback.Text=plain.ToString();
                fallback.Show();
            }
        }
        private void Render(List<MySprite> sprites)
        {
            Hide();
            Vector2 viewport=MyAPIGateway.Session.Camera.ViewportSize;
            if(viewport.X<=0 || viewport.Y<=0) return;
            float size=Math.Min(viewport.Y*.72f,viewport.X*.42f), scale=size/640f;
            Vector2 top=new Vector2(viewport.X-size-28,Math.Max(24,(viewport.Y-size)*.25f-viewport.Y*.03f));
            int ti=0,bi=0;
            foreach(var sprite in sprites)
            {
                Vector2 pixel=top+sprite.Position.Value*scale;
                Vector2D origin=new Vector2D(pixel.X/viewport.X*2-1,1-pixel.Y/viewport.Y*2);
                if(sprite.Type==SpriteType.TEXT)
                {
                    if(ti==texts.Count) texts.Add(new HudAPIv2.HUDMessage(new StringBuilder(),origin,HideHud:false,Shadowing:false,Font:"monospace"));
                    var text=texts[ti++]; text.Visible=false; text.Origin=origin; text.Scale=1;
                    text.Message.Clear().Append("M");
                    double unit=Math.Abs(text.GetTextLength().X);
                    // SE's Monospace glyph advance at scale 1 is 20 texture pixels.
                    text.Scale=unit>0 ? (20*scale*sprite.RotationOrScale*2/viewport.X)/unit : .7;
                    text.Message.Clear().Append(sprite.Data.Replace("<", "(").Replace(">", ")")); text.InitialColor=sprite.Color ?? Color.White; drawOrder.Add(text);
                }
                else
                {
                    if(bi==boxes.Count) boxes.Add(new HudAPIv2.BillBoardHUDMessage(MyStringId.GetOrCompute("SquareFullColor"),origin,Color.White,HideHud:false,Shadowing:false));
                    var box=boxes[bi++]; box.Origin=origin; box.BillBoardColor=sprite.Color ?? Color.White;
                    box.Width=sprite.Size.Value.X*scale/viewport.X*2; box.Height=sprite.Size.Value.Y*scale/viewport.Y*2;
                    box.Visible=false; drawOrder.Add(box);
                }
            }
        }
        public override void Draw()
        {
            foreach(var message in drawOrder) message.Draw();
        }
        private void Hide()
        {
            drawOrder.Clear();
            foreach(var text in texts) text.Visible=false;
            foreach(var box in boxes) box.Visible=false;
            if(fallback!=null) fallback.Hide();
        }
        protected override void UnloadData()
        {
            if(api==null) return;
            Hide(); foreach(var text in texts) text.DeleteMessage(); foreach(var box in boxes) box.DeleteMessage();
            texts.Clear(); boxes.Clear(); api.Unload(); api=null;
        }
    }
}
