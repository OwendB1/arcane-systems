using Sandbox.Common.ObjectBuilders;
using Sandbox.Game.EntityComponents;
using Sandbox.ModAPI;
using VRage.Game.Components;
using VRage.ObjectBuilders;
using VRage.ModAPI;
using VRage.Utils;

namespace ArcanePower
{
    // A sink on the generator itself would become a native storage source/sink
    // pair. Draw containment power through the two physical controllers instead.
    [MyEntityComponentDescriptor(typeof(MyObjectBuilder_UpgradeModule), false,
        "ArcanePower_ContainmentController", "ArcanePower_AdvancedContainmentController")]
    public sealed class ContainmentController : MyGameLogicComponent
    {
        private MyResourceSinkComponent sink;
        private long requester;
        private int requestedAt;
        private float demand;

        public override void Init(MyObjectBuilder_EntityBase builder)
        {
            var block = (VRage.Game.ModAPI.IMyCubeBlock)Entity;
            sink = new MyResourceSinkComponent();
            sink.Init(MyStringHash.GetOrCompute("ArcaneContainment"), new MyResourceSinkInfo
            {
                ResourceTypeId = MyResourceDistributorComponent.ElectricityId,
                MaxRequiredInput = 200f,
                RequiredInputFunc = RequiredPower
            });
            block.ResourceSink = sink;
            NeedsUpdate = MyEntityUpdateEnum.EACH_FRAME;
        }

        private float RequiredPower()
        {
            var block = (VRage.Game.ModAPI.IMyCubeBlock)Entity;
            return !block.IsFunctional || MyAPIGateway.Session == null
                || MyAPIGateway.Session.GameplayFrameCounter - requestedAt > 2 ? 0 : demand;
        }

        internal float Request(long reactorId, float megawatts)
        {
            if (sink == null) return 0;
            int frame = MyAPIGateway.Session.GameplayFrameCounter;
            if (requester != reactorId && frame - requestedAt <= 2 && demand > 0) return 0;
            // Account the previous distributed interval before changing demand.
            float input = requester == reactorId ? sink.CurrentInputByType(MyResourceDistributorComponent.ElectricityId) : 0;
            requester = reactorId;
            requestedAt = frame;
            demand = megawatts;
            sink.Update();
            return input;
        }

        public override void UpdateBeforeSimulation()
        {
            // Dropped/removed reactor connections cannot leave a permanent load.
            if (sink != null && MyAPIGateway.Session != null
                && MyAPIGateway.Session.GameplayFrameCounter - requestedAt > 2 && demand > 0)
            {
                demand = 0;
                sink.Update();
            }
        }
    }
}
