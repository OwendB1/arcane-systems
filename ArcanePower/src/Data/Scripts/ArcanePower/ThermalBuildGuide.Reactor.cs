using System;
using System.Collections.Generic;
using Sandbox.Game.Entities;
using VRage.Game.ModAPI;
using VRageMath;

namespace ArcanePower
{
    public sealed partial class ThermalBuildGuide
    {
        private IMyCubeBlock assemblyBlock;
        private Reactor assemblyReactor;
        private readonly Dictionary<string, IMyModelDummy> assemblyDummies = new Dictionary<string, IMyModelDummy>();

        private static bool ReactorHardware(string subtype)
        {
            return subtype == "ArcanePower_ContainmentController" || subtype == "ArcanePower_AdvancedContainmentController"
                || subtype == "ArcanePower_VentDuct" || subtype == "ArcanePower_VentOutlet";
        }

        private static IMySlimBlock AssemblyVessel(IMySlimBlock aimed)
        {
            if (aimed == null || aimed.FatBlock == null || !ReactorHardware(aimed.BlockDefinition.Id.SubtypeName)) return aimed;
            foreach (var reactor in VentSession.All)
            {
                var source = reactor.Block;
                if (source.CubeGrid != aimed.CubeGrid) continue;
                if (aimed.BlockDefinition.Id.SubtypeName.EndsWith("ContainmentController"))
                {
                    var attached = ((MyCubeBlock)source).CurrentAttachedUpgradeModules;
                    if (attached != null)
                        foreach (var entry in attached.Values)
                            if (entry.Block == aimed.FatBlock) return source.SlimBlock;
                }
                else
                {
                    Vector3I up = Base6Directions.GetIntVector(source.Orientation.Up);
                    for (int i = 2; i <= 17; i++)
                    {
                        Vector3I cell = source.Position + up * i;
                        if (aimed.FatBlock.Position == cell) return source.SlimBlock;
                        var section = source.CubeGrid.GetCubeBlock(cell);
                        if (section == null || section.FatBlock == null
                            || section.BlockDefinition.Id.SubtypeName != "ArcanePower_VentDuct") break;
                    }
                }
            }
            // Refresh applies the vessel's normal access check after resolution.
            return aimed;
        }

        private void ShowReactorAssembly(IMySlimBlock aimed, Reactor reactor)
        {
            active = true;
            assemblyBlock = aimed.FatBlock;
            assemblyReactor = reactor;
            assemblyDummies.Clear();
            var model = assemblyBlock == null ? null : ((VRage.ModAPI.IMyEntity)assemblyBlock).Model;
            if (model != null) model.GetDummies(assemblyDummies);
            // Keep existing pipe markers when Brayton needs construction help.
            // The assembly panel remains available in every operating mode.
            if (!ThermalConstruction.ShowReactorGuide(reactor == null ? null : reactor.Motion.Thermal, check))
                selected = null;
            text.Clear().Append("<color=100,210,255>REACTOR / ASSEMBLY GUIDE\n");
            if (grid.Physics == null || reactor == null)
            {
                text.Append("<color=255,210,110>")
                    .Append(grid.Physics == null ? "Projection only: weld the physical grid before checking readiness."
                        : "Waiting for reactor state. Finish welding the vessel.")
                    .Append("\n<color=235,240,245>Two lower side controllers; roof ducts + outlet.\nLoad filled Aether canisters and 80 tiles; supply startup power.");
                Present("Reactor: weld the vessel, then fit two controllers and a roof vent route.");
                return;
            }
            var report = reactor.ReadAssemblyGuide();
            text.Append(ColorTag(report.Tone)).Append(report.State);
            string section = null;
            foreach (var row in report.Rows)
            {
                if (row.Section != section)
                {
                    section = row.Section;
                    text.Append("\n").Append(ColorTag("cyan")).Append(section);
                }
                text.Append("\n").Append(ColorTag(row.Tone));
                if (!string.IsNullOrEmpty(row.Label)) text.Append(row.Label).Append(": ");
                text.Append(row.Value);
            }
            if (selected != null)
                text.Append("\n").Append(ColorTag("yellow")).Append("Pipe check: ").Append(check.Next);
            text.Append("\n").Append(ColorTag("muted"))
                .Append("Markers: amber = place/weld/align; green = ready; cyan = supply hatch.\nAim at pipes for H/C alignment. Checks are advisory; startup safeguards still apply.");
            string next = report.Rows.Count > 0 && report.Rows[0].Section == null ? report.Rows[0].Value : report.State;
            Present("Reactor: " + next);
        }

        private static string ColorTag(string tone)
        {
            Color color = ReactorDashboard.Tone(tone);
            return "<color=" + color.R + "," + color.G + "," + color.B + ">";
        }

        private bool ControllerSocketReady(Vector3D at)
        {
            var attached = ((MyCubeBlock)assemblyBlock).CurrentAttachedUpgradeModules;
            if (attached == null || grid.Physics == null) return false;
            foreach (var entry in attached.Values)
            {
                var block = entry.Block;
                if (!entry.Compatible || block == null || block.Closed || block.CubeGrid != grid
                    || !block.IsFunctional || block.SlimBlock.BuildLevelRatio < 1
                    || block.GameLogic.GetAs<ContainmentController>() == null) continue;
                if (Vector3D.DistanceSquared(block.GetPosition(), at) < grid.GridSize * grid.GridSize) return true;
            }
            return false;
        }

        private void DrawAssemblyMarkers()
        {
            MatrixD world = assemblyBlock.WorldMatrix;
            foreach (var pair in assemblyDummies)
            {
                bool controller = pair.Key.StartsWith("detector_upgrade", StringComparison.OrdinalIgnoreCase);
                bool supply = pair.Key.StartsWith("detector_conveyor", StringComparison.OrdinalIgnoreCase);
                if (!controller && !supply) continue;
                Vector3 local = pair.Value.Matrix.Translation;
                // These are the authored side sockets/hatches. The roof conveyor
                // is covered by the vent marker, not a fuel-loading marker.
                Vector3 normal = new Vector3(local.X, 0, local.Z);
                if (normal.LengthSquared() < .01f) continue;
                Vector3D facing = Vector3D.TransformNormal(Vector3.Normalize(normal), world);
                Vector3D at = Vector3D.Transform(local, world) + facing * .07;
                Vector4 color = (controller ? ControllerSocketReady(at) ? new Color(20, 255, 85)
                    : new Color(255, 180, 0) : new Color(0, 200, 255)).ToVector4();
                Ring(at, world.Up, Vector3D.Cross(world.Up, facing), controller ? .60 : .45, color);
            }

            // Follow the same straight, same-grid route as FindVentOutlet. Mark
            // the next connection rather than drawing through the entire stack.
            Vector3I up = Base6Directions.GetIntVector(assemblyBlock.Orientation.Up);
            for (int i = 0; i < 16; i++)
            {
                Vector3I cell = assemblyBlock.Position + up * (2 + i);
                var slim = grid.GetCubeBlock(cell);
                var block = slim == null ? null : slim.FatBlock;
                string subtype = block == null ? "" : block.BlockDefinition.SubtypeName;
                bool duct = subtype == "ArcanePower_VentDuct";
                bool outlet = subtype == "ArcanePower_VentOutlet" && i > 0;
                bool intact = block != null && block.Position == cell && block.Orientation.Up == assemblyBlock.Orientation.Up
                    && block.IsFunctional && slim.BuildLevelRatio >= 1;
                if (duct && intact && i < 15) continue;
                bool ready = outlet && intact && grid.Physics != null && assemblyReactor != null && assemblyReactor.Motion.VentReady;
                Vector3D at = grid.GridIntegerToWorld(cell) + world.Up * (ready ? 1.28 : -1.21);
                Ring(at, world.Right, world.Backward, 1.05,
                    (ready ? new Color(20, 255, 85) : new Color(255, 180, 0)).ToVector4());
                break;
            }
        }
    }
}
