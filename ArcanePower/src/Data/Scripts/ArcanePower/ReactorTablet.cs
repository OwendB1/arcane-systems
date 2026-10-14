using System.Collections.Generic;
using Sandbox.Game.Entities;
using Sandbox.ModAPI;
using VRage.Game.Components;

namespace ArcanePower
{
    [MySessionComponentDescriptor(MyUpdateOrder.AfterSimulation)]
    public sealed class ReactorTablet : MySessionComponentBase
    {
        private readonly TabletScreen screen = new TabletScreen();
        private long linked;
        private int page, tick;
        private bool wasHeld;
        public override void UpdateAfterSimulation()
        {
            if(MyAPIGateway.Utilities.IsDedicated) return;
            if(MyAPIGateway.Session.Player==null) { screen.Release(); wasHeld=false; return; }
            var character=MyAPIGateway.Session.Player.Character;
            var tool=character==null ? null : character.EquippedTool as MyHandToolBase;
            bool held=tool!=null && tool.DefinitionId.SubtypeName=="ArcanePower_Tablet";
            bool visible=held && !MyAPIGateway.Gui.IsCursorVisible && !MyAPIGateway.Gui.ChatEntryVisible;
            if(!visible) { screen.Release(); wasHeld=false; return; }
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
            if (!screen.Draw(tool, ReactorDashboard.DrawTablet(report, page, reason))) wasHeld = false;
        }
        protected override void UnloadData()
        {
            screen.Release();
        }
    }
}
