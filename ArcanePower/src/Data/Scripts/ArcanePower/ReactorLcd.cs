using System;
using Sandbox.Game.GameSystems.TextSurfaceScripts;
using Sandbox.ModAPI;
using VRage.Game.ModAPI.Ingame.Utilities;
using VRageMath;
using Surface = Sandbox.ModAPI.Ingame.IMyTextSurface;
using Block = VRage.Game.ModAPI.Ingame.IMyCubeBlock;

namespace ArcanePower
{
    [MyTextSurfaceScript("ArcanePower_Reactor", "Arcane Reactor")]
    public sealed class ReactorLcd : MyTSSCommon
    {
        private readonly IMyTerminalBlock panel;
        private readonly MyIni config = new MyIni();
        public ReactorLcd(Surface surface, Block block, Vector2 size) : base(surface, block, size) { panel=block as IMyTerminalBlock; }
        public override ScriptUpdate NeedsUpdate { get { return ScriptUpdate.Update10; } }
        public override void Run()
        {
            if (MyAPIGateway.Utilities.IsDedicated || panel == null) return;
            config.Clear(); config.TryParse(panel.CustomData);
            string selector=config.Get("ArcaneReactor","Reactor").ToString().Trim();
            string selectedPage=config.Get("ArcaneReactor","Page").ToString("Overview");
            int page=Array.FindIndex(ReactorDashboard.Pages,p=>p.Equals(selectedPage,StringComparison.OrdinalIgnoreCase));
            if(page<0) page=0;
            Reactor match=null; int matches=0;
            foreach(var reactor in VentSession.All)
            {
                if(!panel.IsSameConstructAs(reactor.Block)) continue;
                if(selector.Length>0 && selector!=reactor.Id.ToString() && !selector.Equals(reactor.Block.CustomName,StringComparison.OrdinalIgnoreCase)) continue;
                match=reactor; matches++;
            }
            string reason=matches>1 ? "Multiple reactors: set [ArcaneReactor] Reactor=<name or entity ID> in this panel's Custom Data." : "No matching reactor on this construct. Configure [ArcaneReactor] Reactor=<name or entity ID>.";
            var sprites=ReactorDashboard.Draw(matches==1 ? match.ReadStatus(true) : null,page,reason,"LCD / "+ReactorDashboard.Pages[page]+" / page selected in Custom Data");
            float scale=Math.Min(Surface.SurfaceSize.X,Surface.SurfaceSize.Y)/640f;
            Vector2 offset=(Surface.TextureSize-new Vector2(640*scale))/2;
            using(var frame=Surface.DrawFrame())
                foreach(var source in sprites)
                {
                    var sprite=source; sprite.Position=offset+source.Position.Value*scale;
                    if(source.Size.HasValue) sprite.Size=source.Size.Value*scale;
                    if(source.Type==VRage.Game.GUI.TextPanel.SpriteType.TEXT) sprite.RotationOrScale*=scale;
                    frame.Add(sprite);
                }
        }
    }
}
