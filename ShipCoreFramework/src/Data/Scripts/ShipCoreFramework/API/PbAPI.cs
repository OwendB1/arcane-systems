using System;
using System.Collections.Generic;
using Sandbox.Common.ObjectBuilders;
using Sandbox.ModAPI;
using Sandbox.ModAPI.Interfaces.Terminal;
using VRage;
using VRage.Game.Components;
using VRage.ModAPI;
using VRage.ObjectBuilders;

namespace ShipCoreFramework
{
    /// <summary>
    /// Read-only programmable block API. Exposes the PB's grid group state as terminal
    /// properties, read from an in-game script with e.g. <c>Me.GetValue&lt;float&gt;("SCF.MaxSpeed")</c>.
    /// Registered on every role (server and client) because PB scripts run on the server.
    /// </summary>
    internal static class PbAPI
    {
        internal const string Prefix = "SCF.";
        private const float TicksPerSecond = 60f;
        private static bool _done;

        internal static void RegisterOnce()
        {
            if (_done) return;
            _done = true;

            try
            {
                Add("Available", g => true, false);
                Add("HasCore", g => g.CoreCount > 0, false);
                Add("CoreName", g => g.ShipCore?.UniqueName ?? string.Empty, string.Empty);
                Add("CoreSubtype", g => g.ShipCore?.SubtypeId ?? string.Empty, string.Empty);
                Add("Deactivated", g => g.Deactivated, false);
                Add("Ignored", g => g.IsIgnoredGroup(), false);

                Add("MaxSpeed", g => ReadSpeed(g, true), 0f);
                Add("BaseMaxSpeed", g => ReadSpeed(g, false), 0f);
                Add("MaxBoost", g => g.SpeedModifiers?.MaxBoost ?? 0f, 0f);

                Add("Blocks", g => g.GroupBlocksCount, 0);
                Add("MaxBlocks", g => g.GetEffectiveMaxBlocks(), 0);
                Add("Mass", g => g.GroupMass, 0f);
                Add("MaxMass", g => g.GetEffectiveMaxMass(), 0f);
                Add("PCU", g => g.GroupPCU, 0);
                Add("MaxPCU", g => g.GetEffectiveMaxPCU(), 0);

                Add("PunishSpeed", g => g.PunishSpeed, false);
                Add("PunishModifiers", g => g.PunishModifiers, false);
                Add("PunishBlocks", g => g.PunishLimitedBlocks, false);

                Add("BoostEnabled", g => g.ShipCore != null && g.ShipCore.SpeedBoostEnabled, false);
                Add("BoostActive", g => Ability(g).BoostActive, false);
                Add("BoostTimeLeft", g => Ability(g).BoostDuration, 0f);
                Add("BoostCooldown", g => Ability(g).BoostCooldown, 0f);
                Add("DefenseEnabled", g => g.ShipCore != null && g.ShipCore.EnableActiveDefenseModifiers, false);
                Add("DefenseActive", g => Ability(g).DefenseActive, false);
                Add("DefenseTimeLeft", g => Ability(g).DefenseDuration, 0f);
                Add("DefenseCooldown", g => Ability(g).DefenseCooldown, 0f);
                Add("OverclockActive", g => Ability(g).PowerActive, false);
                Add("OverclockTimeLeft", g => Ability(g).PowerDuration, 0f);
                Add("OverclockCooldown", g => Ability(g).PowerCooldown, 0f);

                AddCollection("BlockLimits", ReadBlockLimits, () => new Dictionary<string, MyTuple<double, double>>());
                AddCollection("Modifiers", ReadModifiers, () => new Dictionary<string, float>());

                Utils.Log("PbAPI: registered programmable block properties.", 1);
            }
            catch (Exception ex)
            {
                Utils.Log("PbAPI: failed to register programmable block properties - " + ex, 0);
            }
        }

        internal static void Unload()
        {
            // MySession clears MyTerminalControlFactory on unload; only reset our flag.
            _done = false;
        }

        private static void Add<T>(string name, Func<GroupComponent, T> read, T fallback)
        {
            AddCollection(name, read, () => fallback);
        }

        /// <param name="fallback">Builds the value returned when the PB's group cannot be resolved.</param>
        private static void AddCollection<T>(string name, Func<GroupComponent, T> read, Func<T> fallback)
        {
            IMyTerminalControlProperty<T> property =
                MyAPIGateway.TerminalControls.CreateProperty<T, IMyProgrammableBlock>(Prefix + name);
            if (property == null) return;

            property.Getter = block =>
            {
                try
                {
                    GroupComponent group = Resolve(block);
                    if (group != null) return read(group);
                }
                catch (Exception ex)
                {
                    Utils.Log("PbAPI: " + name + " getter failed - " + ex.Message, 2);
                }
                return fallback();
            };
            property.Setter = (block, value) => { };
            MyAPIGateway.TerminalControls.AddControl<IMyProgrammableBlock>(property);
        }

        private static GroupComponent Resolve(IMyTerminalBlock block)
        {
            if (block?.CubeGrid == null || Session.IsShuttingDown) return null;
            GroupComponent group = block.GetGroupComponent();
            if (group == null) return null;
            return Session.IsServer || group.HasRuntimeState ? group : null;
        }

        private static float ReadSpeed(GroupComponent group, bool effective)
        {
            if (Session.IsServer && Session.IsGameThread)
                SpeedEnforcement.RefreshSpeedState(group);
            lock (group.SpeedStateLock)
            {
                return effective ? group.EffectiveSpeedLimitMetersPerSecond : group.BaseSpeedLimitMetersPerSecond;
            }
        }

        private struct AbilitySnapshot
        {
            internal bool BoostActive;
            internal float BoostDuration;
            internal float BoostCooldown;
            internal bool DefenseActive;
            internal float DefenseDuration;
            internal float DefenseCooldown;
            internal bool PowerActive;
            internal float PowerDuration;
            internal float PowerCooldown;
        }

        /// <summary>Ability timers converted from ticks to seconds.</summary>
        private static AbilitySnapshot Ability(GroupComponent group)
        {
            AbilitySnapshot s;
            group.GetAbilityTimers(out s.BoostActive, out s.BoostDuration, out s.BoostCooldown,
                out s.DefenseActive, out s.DefenseDuration, out s.DefenseCooldown,
                out s.PowerActive, out s.PowerDuration, out s.PowerCooldown);
            s.BoostDuration /= TicksPerSecond;
            s.BoostCooldown /= TicksPerSecond;
            s.DefenseDuration /= TicksPerSecond;
            s.DefenseCooldown /= TicksPerSecond;
            s.PowerDuration /= TicksPerSecond;
            s.PowerCooldown /= TicksPerSecond;
            return s;
        }

        /// <summary>Limit name -> (current weight, effective max). Mirrors the core status HUD.</summary>
        private static Dictionary<string, MyTuple<double, double>> ReadBlockLimits(GroupComponent group)
        {
            Dictionary<string, MyTuple<double, double>> result = new Dictionary<string, MyTuple<double, double>>();
            BlockLimit[] configured = group.ShipCore?.BlockLimits;
            if (configured == null) return result;

            for (int index = 0; index < configured.Length; index++)
            {
                BlockLimit limit = configured[index];
                if (limit == null || string.IsNullOrWhiteSpace(limit.Name)) continue;
                if (!group.ShouldEvaluateBlockLimit(limit)) continue;

                double current = 0d;
                LimitBucket bucket;
                if (group.Limits.TryGetValue(limit, out bucket) && bucket != null)
                {
                    lock (bucket.BucketLock) current = bucket.TotalWeight;
                }
                result[limit.Name] = MyTuple.Create(current, (double)group.GetEffectiveMaxCount(limit));
            }
            return result;
        }

        private static Dictionary<string, float> ReadModifiers(GroupComponent group)
        {
            Dictionary<string, float> result = new Dictionary<string, float>();
            GridModifiers modifiers = group.Modifiers;
            if (modifiers == null) return result;

            List<ModifierNameValue> values = modifiers.GetModifierValues();
            for (int index = 0; index < values.Count; index++)
                result[values[index].Name] = values[index].Value;
            return result;
        }
    }

    /// <summary>
    /// Registers <see cref="PbAPI"/> once a programmable block exists. Vanilla PB terminal controls are
    /// created in BeforeGameLogicInit; adding ours earlier would stop the vanilla ones from being created.
    /// </summary>
    [MyEntityComponentDescriptor(typeof(MyObjectBuilder_MyProgrammableBlock), false)]
    public class PbApiRegistrar : MyGameLogicComponent
    {
        public override void Init(MyObjectBuilder_EntityBase objectBuilder)
        {
            NeedsUpdate |= MyEntityUpdateEnum.BEFORE_NEXT_FRAME;
        }

        public override void UpdateOnceBeforeFrame()
        {
            PbAPI.RegisterOnce();
        }
    }
}
