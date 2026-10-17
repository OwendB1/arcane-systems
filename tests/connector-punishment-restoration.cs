// Game API stubs for the production code compiled by connector-punishment-restoration.test.mjs.
using System;
using System.Collections.Generic;
using Sandbox.ModAPI;
using VRage.Game.ModAPI;
using VRageMath;

namespace VRageMath
{
    public struct Vector3I { public int X, Y, Z; public static Vector3I Zero; }
}

namespace VRage.Game.ModAPI
{
    public class IMyCubeGrid { public bool Closed, MarkedForClose; public long EntityId; }
    public class IMyCubeBlock { public IMyCubeGrid CubeGrid = new IMyCubeGrid(); }
    public class IMySlimBlock
    {
        public bool IsMovedBySplit;
        public IMyCubeBlock FatBlock;
        public IMyCubeGrid CubeGrid { get { return FatBlock.CubeGrid; } }
        public Vector3I Position;
    }
}

namespace Sandbox.ModAPI
{
    public class IMyFunctionalBlock : IMyCubeBlock
    {
        public bool Closed, MarkedForClose, LocalLimitBlocksEnable;
        public int EnableWrites;
        private bool _enabled;
        public bool Enabled
        {
            get { return _enabled; }
            set
            {
                if (value) EnableWrites++;
                _enabled = value && !LocalLimitBlocksEnable;
            }
        }
        public IMyFunctionalBlock(bool enabled) { _enabled = enabled; }
    }
    public static class MyAPIGateway { public static readonly GameUtilities Utilities = new GameUtilities(); }
    public class GameUtilities
    {
        private readonly Queue<Action> _pending = new Queue<Action>();
        public void InvokeOnGameThread(Action action) { _pending.Enqueue(action); }
        public void Drain() { while (_pending.Count > 0) _pending.Dequeue()(); }
    }
}

namespace ShipCoreFramework
{
    internal enum PunishmentType { ShutOff }
    internal enum DirectionType { Forward, Backward, Left, Right, Up, Down }
    internal class BlockType { internal DirectionType PrimaryDirection; }
    internal class BlockLimit
    {
        internal double MaxCount;
        internal bool IsCriticalLimit, HasDirectionalBudget;
        internal PunishmentType PunishmentType;
        internal double GetWeight(int key) { return 1; }
        internal float GetMaxCountForDirection(DirectionType direction) { return -1; }
        internal BlockType GetMatchingBlockType(int key) { return null; }
    }
    internal class LimitBucket
    {
        internal double TotalWeight, ConnectorWeight;
        internal readonly double[] DirectionWeights = new double[6];
        internal readonly object BucketLock = new object();
        internal readonly MeasuredList<IMySlimBlock> Members = new MeasuredList<IMySlimBlock>();
        internal readonly HashSet<IMySlimBlock> ConnectorMembers = new HashSet<IMySlimBlock>();
    }
    internal class MeasuredList<T> : List<T>, ICollection<T>
    {
        internal int CopiedItems;
        void ICollection<T>.CopyTo(T[] array, int index)
        { CopiedItems += Count; CopyTo(array, index); }
    }
    internal static class GridComponent
    {
        internal static int KeyReads;
        internal static int KeyOf(IMySlimBlock block) { KeyReads++; return 0; }
    }
    internal static class Session
    {
        internal static bool IsServer = true, IsGameThread = true, IsShuttingDown;
        internal static void MarkRuntimeStateDirty(GroupComponent group) { }
    }
    internal static class Utils
    {
        internal static void Log(string message, int level) { }
        internal static void WhackABlock(this IMySlimBlock block, PunishmentType harm)
        { ((IMyFunctionalBlock)block.FatBlock).Enabled = false; }
    }
    internal static class ModAPI { internal static void BroadcastLimitsEnforced(long id, int count) { } }
    internal partial class GroupComponent
    {
        private bool _closing;
        internal bool Deactivated, Deferred, Grace, ForceShutOff;
        internal int Generation, Applied;
        internal readonly object MyGroup = new object();
        internal readonly Dictionary<BlockLimit, LimitBucket> Limits = new Dictionary<BlockLimit, LimitBucket>();
        private bool IsLimitPunishmentDeferred() { return Deferred; }
        private bool IsCoreRecoveryGraceActive() { return Grace; }
        private bool IsIgnoredGroup() { return false; }
        private void RefreshPunishmentFlags() { }
        private bool ShouldForceLimitedBlocksOff() { return ForceShutOff; }
        private int GetLimitGeneration() { return Generation; }
        private IMyCubeBlock GetDirectionLockReferenceBlock() { return null; }
        private bool ShouldEvaluateBlockLimit(BlockLimit limit) { return true; }
        private bool DoesBlockViolateAllowedDirection(IMyCubeBlock reference, BlockLimit limit, IMySlimBlock block) { return false; }
        private void NotifyDirectionalPlacementViolation(IMyCubeBlock reference, IMySlimBlock block) { }
        private static bool TryResolveBlockFacing(IMyCubeBlock reference, IMySlimBlock block, DirectionType direction, out DirectionType facing)
        { facing = DirectionType.Forward; return false; }
        private float GetEffectiveMaxCount(BlockLimit limit) { return (float)limit.MaxCount; }
        private string GetGroupKey() { return "test"; }
        private long GetRepresentativeGridId() { return 1; }
        private void MarkLimitsEnforced(int count) { Applied += count; }
        internal void Check(bool full = false) { EnforceGroupPunishment(false, !full); }
        internal void Close() { _closing = true; RestoreConnectorShutOffBlocks(null); }
        internal static int TrackedCount { get { return ConnectorShutOffOwners.Count; } }
    }

    internal static class ConnectorRestorationChecks
    {
        private static void Check(bool condition, string message)
        { if (!condition) throw new Exception(message); }
        private static IMySlimBlock Block(bool enabled, int position = 0)
        { return new IMySlimBlock { FatBlock = new IMyFunctionalBlock(enabled), Position = new Vector3I { X = position } }; }
        private static IMyFunctionalBlock Functional(IMySlimBlock block) { return (IMyFunctionalBlock)block.FatBlock; }
        private static BlockLimit Import(GroupComponent group, double capacity, params IMySlimBlock[] blocks)
        {
            var limit = new BlockLimit { MaxCount = capacity };
            var bucket = new LimitBucket { TotalWeight = blocks.Length, ConnectorWeight = blocks.Length };
            bucket.Members.AddRange(blocks);
            bucket.ConnectorMembers.UnionWith(blocks);
            group.Limits.Add(limit, bucket);
            return limit;
        }
        private static void Run(GroupComponent group, bool full = false)
        { group.Check(full); MyAPIGateway.Utilities.Drain(); }
        private static void Disconnect(GroupComponent group)
        { group.Limits.Clear(); group.Generation++; Run(group); }

        private static void Main()
        {
            var group = new GroupComponent();
            var enabled = Block(true);
            var manualOff = Block(false, 1);
            var limit = Import(group, 0, enabled, manualOff);
            Run(group, true);
            for (var i = 0; i < 10; i++) Run(group, i % 2 == 0);
            Check(!Functional(enabled).Enabled && Functional(enabled).EnableWrites == 0,
                "Repeated connector and full refreshes must never pulse a punished block on.");
            Check(group.Applied == 1, "Rechecking a tracked shutdown must not apply it again.");
            limit.MaxCount = 2;
            Run(group);
            Check(Functional(enabled).Enabled && Functional(enabled).EnableWrites == 1, "Capacity relief restores tracked blocks.");
            Check(!Functional(manualOff).Enabled && Functional(manualOff).EnableWrites == 0, "Previously disabled blocks stay off.");
            group.Close();

            group = new GroupComponent();
            enabled = Block(true);
            Import(group, 0, enabled);
            Run(group);
            group.Deferred = true;
            group.Limits.Clear();
            Run(group);
            Check(!Functional(enabled).Enabled, "Deferred checks do not mean punishment cleared.");
            group.Deferred = false;
            Disconnect(group);
            Check(Functional(enabled).Enabled, "Disconnect restores the recorded block.");
            group.Close();

            group = new GroupComponent();
            enabled = Block(true);
            Import(group, 0, enabled);
            group.Check();
            group.Generation++;
            MyAPIGateway.Utilities.Drain();
            Check(Functional(enabled).Enabled, "Stale queued punishment must not shut a block off.");
            Run(group);
            group.Limits.Clear();
            group.Check();
            Import(group, 0, enabled);
            group.Generation++;
            MyAPIGateway.Utilities.Drain();
            Check(!Functional(enabled).Enabled && Functional(enabled).EnableWrites == 0,
                "Stale queued clearance must not restore an actively punished block.");
            Disconnect(group);
            group.Close();

            var first = new GroupComponent();
            var second = new GroupComponent();
            enabled = Block(true);
            Import(first, 0, enabled);
            Import(second, 0, enabled);
            Run(first);
            Run(second);
            Disconnect(first);
            Check(!Functional(enabled).Enabled && Functional(enabled).EnableWrites == 0, "Other punishment keeps the block off.");
            Disconnect(second);
            Check(Functional(enabled).Enabled && Functional(enabled).EnableWrites == 1, "Last punishment clearing restores the block once.");
            first.Close(); second.Close();

            group = new GroupComponent { ForceShutOff = true };
            enabled = Block(true);
            Import(group, 10, enabled);
            Run(group, true);
            Run(group);
            Check(!Functional(enabled).Enabled && Functional(enabled).EnableWrites == 0, "Minimum-block punishment remains active during connector checks.");
            group.ForceShutOff = false;
            Run(group);
            Check(Functional(enabled).Enabled, "Clearing the forced gate restores the block.");
            group.Close();

            group = new GroupComponent();
            enabled = Block(true);
            Import(group, 0, enabled);
            Run(group);
            Functional(enabled).LocalLimitBlocksEnable = true;
            Disconnect(group);
            Check(!Functional(enabled).Enabled, "Restoration must respect the local enable guard.");
            group.Close();

            group = new GroupComponent();
            enabled = Block(true);
            Import(group, 0, enabled);
            Run(group);
            Functional(enabled).Closed = true;
            Disconnect(group);
            Check(Functional(enabled).EnableWrites == 0, "Destroyed blocks must not be restored.");
            group.Close();

            // A connector-only check must scale with imported blocks, not the owner's local grid.
            group = new GroupComponent();
            var imported = new[] { Block(true), Block(true, 1) };
            limit = Import(group, 10002, imported);
            var largeBucket = group.Limits[limit];
            for (var i = 0; i < 10000; i++) largeBucket.Members.Add(Block(true, i + 2));
            largeBucket.TotalWeight += 10000;
            GridComponent.KeyReads = 0;
            Run(group);
            Check(largeBucket.Members.CopiedItems == 0 && GridComponent.KeyReads == 0,
                "An under-capacity connector check must not copy or inspect any members.");
            limit.MaxCount = 10000;
            Run(group);
            Check(largeBucket.Members.CopiedItems == 0 && GridComponent.KeyReads == imported.Length,
                "An over-capacity connector check must inspect only imported members.");
            Check(!Functional(imported[0]).Enabled && !Functional(imported[1]).Enabled,
                "Local totals must still consume capacity during connector-only checks.");
            Run(group, true);
            Check(largeBucket.Members.CopiedItems == largeBucket.Members.Count,
                "Full enforcement must retain local membership checks.");
            limit.MaxCount = 10002;
            Run(group);
            Check(Functional(imported[0]).Enabled && Functional(imported[1]).Enabled,
                "The under-capacity fast path must restore previously punished imports.");
            group.ForceShutOff = true;
            GridComponent.KeyReads = 0;
            Run(group);
            Check(!Functional(imported[0]).Enabled && GridComponent.KeyReads == imported.Length,
                "Forced shutdown must bypass the capacity fast path and inspect only imports.");
            Disconnect(group);
            group.Close();

            group = new GroupComponent();
            enabled = Block(true);
            Import(group, 0, enabled);
            Run(group);
            Session.IsShuttingDown = true;
            group.Close();
            Check(Functional(enabled).EnableWrites == 0, "World unload must only clear tracking.");
            Check(GroupComponent.TrackedCount == 0, "All shutdown records must be released.");
            Console.WriteLine("Connector punishment restoration behavior checks passed.");
        }
    }
}
