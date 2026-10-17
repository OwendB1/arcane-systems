using System;
using Sandbox.Common.ObjectBuilders;
using Sandbox.ModAPI;
using VRage.Game.Components;
using VRage.Game.ModAPI;
using VRage.ModAPI;
using VRage.ObjectBuilders;
using VRageMath;

namespace ArcanePower
{
    [MyEntityComponentDescriptor(typeof(MyObjectBuilder_Conveyor), false,
        "ArcanePower_VentDuct", "ArcanePower_VentOutlet")]
    public sealed class VentHardware : MyGameLogicComponent
    {
        public override void Init(MyObjectBuilder_EntityBase builder)
        {
            NeedsUpdate = MyEntityUpdateEnum.BEFORE_NEXT_FRAME | MyEntityUpdateEnum.EACH_10TH_FRAME;
        }

        public override void UpdateOnceBeforeFrame() { UpdateAfterSimulation10(); }

        public override void UpdateAfterSimulation10()
        {
            if (MyAPIGateway.Utilities.IsDedicated) return;
            var section = (IMyCubeBlock)Entity;
            var owner = ConnectedReactor(section);
            bool alarm = owner != null && (owner.Motion.Critical || owner.Motion.Vent != VentPhase.Idle);
            Color color = owner != null && !alarm ? Color.Green : Color.Red;
            float intensity = alarm ? 1f + (float)Math.Cos(MyAPIGateway.Session.GameplayFrameCounter * Math.PI / 60) : 2f;
            // Reapply periodically: native conveyor and recreated render objects
            // may reset emissives. The native fallback preset is always red.
            section.SetEmissiveParts("Emissive", color, intensity);
            section.SetEmissivePartsForSubparts("Emissive", color, intensity);
        }

        internal static Reactor ConnectedReactor(IMyCubeBlock section)
        {
            Vector3I up = Base6Directions.GetIntVector(section.Orientation.Up);
            for (int i = 1; i <= 16; i++)
            {
                Vector3I position = section.Position - up * i;
                var slim = section.CubeGrid.GetCubeBlock(position);
                var block = slim == null ? null : slim.FatBlock;
                if (block == null || block.Orientation.Up != section.Orientation.Up) return null;
                if (block.BlockDefinition.SubtypeName == "ArcanePower_ReactorPrototype"
                    || block.BlockDefinition.SubtypeName == "ArcanePower_Thermal_ReactorHousing")
                {
                    if (!block.IsFunctional || slim.BuildLevelRatio < 1f) return null;
                    var owner = block.GameLogic.GetAs<Reactor>();
                    IMyCubeBlock outlet;
                    int ducts;
                    if (owner == null || !owner.Motion.VentReady || !Reactor.FindVentOutlet(block, out outlet, out ducts)) return null;
                    // A wide reactor footprint must not validate a neighbouring
                    // tube column, nor an extra tube placed above the outlet.
                    for (int n = 0; n <= ducts; n++)
                        if (section.Position == block.Position + up * (2 + n)) return owner;
                    return null;
                }
                if (block.BlockDefinition.SubtypeName != "ArcanePower_VentDuct" || block.Position != position) return null;
            }
            return null;
        }
    }
}
