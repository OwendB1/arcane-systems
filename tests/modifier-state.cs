using System;
using System.Collections.Generic;
using Sandbox.ModAPI;

namespace Sandbox.ModAPI
{
    internal class IMyTerminalBlock
    {
        internal int Writes;
        internal bool Fail;
        internal Action OnWrite;
        internal ShipCoreFramework.GridModifiers Last;
    }
    internal static class MyAPIGateway { internal static readonly Utilities Utilities = new Utilities(); }
    internal class Utilities
    {
        internal readonly Queue<Action> Pending = new Queue<Action>();
        internal void InvokeOnGameThread(Action action) { Pending.Enqueue(action); }
        internal void Drain() { while (Pending.Count > 0) Pending.Dequeue()(); }
    }
}
namespace ShipCoreFramework
{
    internal class Block { internal IMyTerminalBlock FatBlock = new IMyTerminalBlock(); }
    internal class Grid { internal long EntityId; }
    internal partial class GridComponent
    {
        internal int Copies;
        internal readonly List<Block> Blocks = new List<Block> { new Block() };
        private List<Block> GetBlocksCopy() { Copies++; return new List<Block>(Blocks); }
    }
    internal class MeasuredRegistry : Dictionary<long, GridDefenseModifiers>
    {
        internal int Writes;
        internal bool TryRemove(long key, out GridDefenseModifiers value)
        { if (!TryGetValue(key, out value)) return false; return Remove(key); }
        internal new GridDefenseModifiers this[long key]
        {
            get { return base[key]; }
            set { Writes++; base[key] = value; }
        }
    }
    internal static partial class CubeGridModifiers
    {
        internal static readonly MeasuredRegistry DefenseModifiers = new MeasuredRegistry();
        internal static void ApplyModifiers(IMyTerminalBlock block, GridModifiers modifiers)
        {
            if (block.Fail) throw new Exception("simulated write failure");
            block.Writes++;
            block.Last = Clone(modifiers);
            if (block.OnWrite != null) block.OnWrite();
        }
    }
    internal static class Session
    {
        internal static bool IsServer = true, IsGameThread = true, IsShuttingDown;
        internal static void MarkPhysicalSpeedClusterSourceDirty(GroupComponent group) { }
        internal static void MarkRuntimeStateDirty(GroupComponent group) { }
    }
    internal partial class GroupComponent
    {
        internal bool _closing, Deactivated, IsInitializingGrids;
        internal readonly Dictionary<Grid, GridComponent> GridDictionary = new Dictionary<Grid, GridComponent>();
        internal object MainCoreComponent = new object();
        private readonly object _abilityStateLock = new object();
        internal bool _activeDefenseEnabled;
        internal int Builds, RuleRefreshes;
        private bool _modifierStateCacheDirty = true;
        private GridDefenseModifiers _passive, _active;
        internal readonly GridModifiers Modifiers = new GridModifiers();
        internal readonly GridDefenseModifiers Passive = new GridDefenseModifiers();
        internal readonly GridDefenseModifiers Active = new GridDefenseModifiers { Bullet = 0.5f };
        private void RefreshModifierStateCacheIfNeeded()
        {
            if (!_modifierStateCacheDirty) return;
            Builds++;
            _modifierStateCacheDirty = false;
            _passive = CubeGridModifiers.Clone(Passive);
            _active = CubeGridModifiers.Clone(Active);
        }
        private GridDefenseModifiers GetCachedActiveDefenseModifiers() { return _active; }
        private GridDefenseModifiers GetCachedPassiveDefenseModifiers() { return _passive; }
        private void RefreshPunishmentState() { RuleRefreshes++; }
        private void InvalidateGameThreadStateCache(bool directionMayChange) { }
        private void InvalidateModifierStateCache() { _modifierStateCacheDirty = true; }
        internal void MarkDirty() { InvalidateModifierStateCache(); }
        private void RefreshGridStateCacheIfNeeded(bool periodic) { }
        private bool RefreshNoCoreDirectionLockReferenceCacheIfNeeded() { return false; }
        private void RefreshIgnoredStateCacheIfNeeded(bool periodic) { }
        private void RevalidateNoCoreDirectionLock() { }
        private void InvalidateSpeedStateCache() { }
        private void ApplyModifiers(GridModifiers modifiers)
        { foreach (var grid in GridDictionary.Values) grid.ApplyModifiers(modifiers); }
    }
    internal static class ModifierStateChecks
    {
        private static void Check(bool condition, string message)
        { if (!condition) throw new Exception(message); }
        private static void Main()
        {
            var grid = new GridComponent();
            var values = new GridModifiers();
            grid.ApplyModifiers(values);
            for (var i = 0; i < 120; i++) grid.ApplyModifiers(new GridModifiers());
            Check(grid.Copies == 1 && grid.Blocks[0].FatBlock.Writes == 1,
                "Unchanged values must skip both block copies and block writes.");
            // Every public modifier field participates in comparison and is copied independently.
            foreach (var field in typeof(GridModifiers).GetFields())
            {
                int copies = grid.Copies;
                field.SetValue(values, 2f);
                grid.ApplyModifiers(values);
                Check(grid.Copies == copies + 1, "Changed modifier was missed: " + field.Name);
                Check((float)field.GetValue(grid.Blocks[0].FatBlock.Last) == 2f,
                    "Changed modifier was not applied: " + field.Name);
            }
            var joined = new GridComponent();
            joined.ApplyModifiers(values);
            Check(joined.Copies == 1 && joined.Blocks[0].FatBlock.Last.ThrusterForce == 2f,
                "A newly joined grid must receive unchanged group values.");
            var added = new Block();
            grid.Blocks.Add(added);
            CubeGridModifiers.ApplyModifiers(added.FatBlock, values);
            int oldWrites = grid.Blocks[0].FatBlock.Writes;
            grid.ApplyModifiers(values);
            Check(added.FatBlock.Writes == 1 && grid.Blocks[0].FatBlock.Writes == oldWrites,
                "Adding one block must not rewrite the existing grid.");

            var failed = new GridComponent();
            failed.Blocks[0].FatBlock.Fail = true;
            try { failed.ApplyModifiers(values); } catch (Exception) { }
            failed.Blocks[0].FatBlock.Fail = false;
            failed.ApplyModifiers(values);
            Check(failed.Blocks[0].FatBlock.Writes == 1, "Failed writes must remain eligible for retry.");
            failed.Blocks[0].FatBlock.OnWrite = () => failed.ApplyModifiers(new GridModifiers());
            failed.ApplyModifiers(new GridModifiers());
            Check(failed.Blocks[0].FatBlock.Writes == 2, "Identical reentrant requests must not recurse.");

            var group = new GroupComponent();
            group.GridDictionary.Add(new Grid { EntityId = 1 }, new GridComponent());
            group.RefreshDefenseModifierCache();
            for (var i = 0; i < 120; i++) group.RefreshDefenseModifierCache();
            Check(group.Builds == 1 && CubeGridModifiers.DefenseModifiers.Writes == 1,
                "Unchanged defense checks must neither rebuild nor republish modifiers.");
            group._activeDefenseEnabled = true;
            group.RefreshDefenseModifierCache();
            Check(CubeGridModifiers.DefenseModifiers[1].Bullet == 0.5f && group.Builds == 1,
                "Defense activation must select cached active values immediately.");
            foreach (var field in typeof(GridDefenseModifiers).GetFields())
            {
                int writes = CubeGridModifiers.DefenseModifiers.Writes;
                field.SetValue(group.Active, 3f);
                group.OnOwnershipOrMobilityChanged();
                MyAPIGateway.Utilities.Drain();
                Check(CubeGridModifiers.DefenseModifiers.Writes == writes + 1,
                    "Defense field change was missed: " + field.Name);
            }
            group.GridDictionary.Add(new Grid { EntityId = 2 }, new GridComponent());
            int before = CubeGridModifiers.DefenseModifiers.Writes;
            group.RefreshDefenseModifierCache();
            Check(CubeGridModifiers.DefenseModifiers.Writes == before + 1,
                "Only a newly joined grid needs defense publication.");
            group.MainCoreComponent = null;
            group.RefreshDefenseModifierCache();
            Check(CubeGridModifiers.DefenseModifiers.Count == 0, "Core removal must clear defense state.");

            group = new GroupComponent();
            grid = new GridComponent();
            group.GridDictionary.Add(new Grid { EntityId = 3 }, grid);
            for (var i = 0; i < 1000; i++) group.QueuePunishmentStateRefresh();
            Check(MyAPIGateway.Utilities.Pending.Count == 1, "Bursts of block/PCU changes must coalesce.");
            group.Modifiers.ThrusterForce = 4f;
            MyAPIGateway.Utilities.Drain();
            Check(group.RuleRefreshes == 1 && grid.Blocks[0].FatBlock.Last.ThrusterForce == 4f,
                "The queued refresh must use the latest group state.");
            group.QueuePunishmentStateRefresh();
            MyAPIGateway.Utilities.Drain();
            Check(grid.Copies == 1, "An unchanged queued refresh must not scan blocks.");
            group.Modifiers.GyroForce = 5f;
            group.MarkDirty();
            group.RefreshGameThreadStateCache();
            Check(grid.Blocks[0].FatBlock.Last.GyroForce == 5f && grid.Copies == 2,
                "The game-thread dirty-cache drain must publish changes even without a queued rule refresh.");
            group.RefreshGameThreadStateCache();
            Check(grid.Copies == 2, "Clean game-thread ticks must perform no modifier block scans.");
            Session.IsGameThread = false;
            group.RefreshDefenseModifierCache();
            Check(MyAPIGateway.Utilities.Pending.Count == 1, "Defense publication must defer to the game thread.");
            Session.IsGameThread = true;
            MyAPIGateway.Utilities.Drain();
            group.QueuePunishmentStateRefresh();
            group._closing = true;
            MyAPIGateway.Utilities.Drain();
            Check(group.RuleRefreshes == 2, "Queued work must not run after group cleanup.");
            Console.WriteLine("Modifier state, event coalescing, defense, and lifecycle behavior checks passed.");
        }
    }
}
