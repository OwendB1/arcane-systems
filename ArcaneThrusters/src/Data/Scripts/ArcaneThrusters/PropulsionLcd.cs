using System;
using System.Collections.Generic;
using Sandbox.Game.GameSystems.TextSurfaceScripts;
using Sandbox.ModAPI;
using VRage.Game.GUI.TextPanel;
using VRageMath;
using Surface = Sandbox.ModAPI.Ingame.IMyTextSurface;
using Block = VRage.Game.ModAPI.Ingame.IMyCubeBlock;

namespace ArcaneThrusters
{
    [MyTextSurfaceScript("ArcaneThrusters_Propulsion", "Arcane Plasma Endurance")]
    public sealed class PropulsionLcd : MyTSSCommon
    {
        private readonly IMyTerminalBlock panel;
        private readonly List<IMyThrust> engines = new List<IMyThrust>();
        public PropulsionLcd(Surface surface, Block block, Vector2 size) : base(surface, block, size)
        { panel = block as IMyTerminalBlock; }

        public override ScriptUpdate NeedsUpdate { get { return ScriptUpdate.Update100; } }
        public override void Run()
        {
            if (panel == null || MyAPIGateway.Utilities.IsDedicated) return;
            engines.Clear();
            var terminal = MyAPIGateway.TerminalActionsHelper.GetTerminalSystemForGrid(panel.CubeGrid);
            if (terminal != null) terminal.GetBlocksOfType(engines, t => t.CubeGrid == panel.CubeGrid);
            double force = 0, flow = 0, seconds = double.MaxValue;
            bool sustained = false, connected = false;
            foreach (var engine in engines)
            {
                var drive = engine.GameLogic.GetAs<PlasmaDrive>();
                if (drive == null || drive.Reading == null) continue;
                connected = true;
                var r = drive.Reading;
                force += r.ForceN;
                flow += r.LitresPerSecond;
                if (r.BurnSeconds >= 0) seconds = Math.Min(seconds, r.BurnSeconds);
                sustained |= r.BurnSeconds == -2;
            }
            string endurance = seconds < double.MaxValue ? Math.Ceiling(seconds) + " s" : sustained ? "sustained" : "—";
            string label = !connected ? "Waiting for drive telemetry" : force == 0 ? "Hydrogen" : "Plasma boost";
            string text = string.Format("{0}\nBoost   {1:N0} kN\nDraw   {2:N0} L/s\nBurn remaining   {3}", label, force / 1000, flow, endurance);
            var size = Surface.SurfaceSize;
            var sprite = MySprite.CreateText(text, "Debug", Surface.ScriptForegroundColor,
                Math.Min(size.X, size.Y) / 450f, TextAlignment.LEFT);
            sprite.Position = (Surface.TextureSize - size) / 2 + size * .06f;
            using (var frame = Surface.DrawFrame()) frame.Add(sprite);
        }
    }
}
