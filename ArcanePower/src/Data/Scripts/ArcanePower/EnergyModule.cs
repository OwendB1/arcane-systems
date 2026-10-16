using Sandbox.Common.ObjectBuilders;
using Sandbox.ModAPI;
using VRage.Game.Components;
using VRage.Game.Entity;
using VRage.Game.ModAPI;
using VRage.ModAPI;
using VRage.ObjectBuilders;
using VRageMath;

namespace ArcanePower
{
    // Cosmetic only: the bank owns attachment and power policy.
    [MyEntityComponentDescriptor(typeof(MyObjectBuilder_UpgradeModule), false,
        "ArcanePower_EnergyStabilizer_Pillar", "ArcanePower_EnergyStabilizerAdvanced_Pillar",
        "ArcanePower_EnergyTransfer_Pillar", "ArcanePower_EnergyTransferAdvanced_Pillar")]
    public sealed class EnergyModule : MyGameLogicComponent
    {
        private readonly MyEntitySubpart[] fans = new MyEntitySubpart[3];
        private readonly Matrix[] rest = new Matrix[3];
        private IMyCubeBlock block;
        private float phase;
        private int tick;

        public override void Init(MyObjectBuilder_EntityBase builder)
        {
            block = (IMyCubeBlock)Entity;
            NeedsUpdate = MyEntityUpdateEnum.BEFORE_NEXT_FRAME;
        }

        public override void UpdateOnceBeforeFrame()
        {
            NeedsUpdate = MyAPIGateway.Session == null ? MyEntityUpdateEnum.BEFORE_NEXT_FRAME
                : MyAPIGateway.Utilities.IsDedicated ? MyEntityUpdateEnum.NONE : MyEntityUpdateEnum.EACH_FRAME;
        }

        public override void UpdateBeforeSimulation()
        {
            var direction = Base6Directions.GetIntVector(block.Orientation.Forward);
            var slim = block.CubeGrid.GetCubeBlock(block.Position + direction * 2);
            var core = slim == null || slim.FatBlock == null ? null : slim.FatBlock.GameLogic.GetAs<EnergyCore>();
            bool active = core != null && core.IsModuleRunning(block);
            tick = (tick + 1) % 10;
            // 45 rpm remains readable at engineer scale and freezes when inactive.
            if (active)
                phase = (phase + MathHelper.TwoPi * .75f / 60f) % MathHelper.TwoPi;
            var camera = MyAPIGateway.Session.Camera;
            if (camera == null || Vector3D.DistanceSquared(camera.Position, Entity.GetPosition()) > 300 * 300) return;
            var model = (MyEntity)Entity;
            if (tick == 1)
                model.SetEmissiveParts("EnergyStatus", active ? core.VisualColor : Color.Black, active ? .35f : 0);
            for (int i = 0; i < fans.Length; i++)
            {
                MyEntitySubpart part;
                if (!model.Subparts.TryGetValue("EnergyFan" + (i + 1), out part)) { fans[i] = null; continue; }
                // Welding replaces subparts. Capture a fresh rest transform for
                // each new entity; never accumulate rotation into the last pose.
                if (fans[i] != part) { fans[i] = part; rest[i] = part.PositionComp.LocalMatrixRef; }
                Matrix pose = Matrix.CreateRotationZ(phase) * rest[i];
                pose.Translation = rest[i].Translation;
                part.PositionComp.SetLocalMatrix(ref pose);
            }
        }
    }
}
