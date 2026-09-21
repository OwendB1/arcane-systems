using System;
using ProtoBuf;

namespace ShipCoreFramework
{
    [ProtoContract]
    internal sealed class RuntimeLimitState
    {
        [ProtoMember(1)] internal string Name;
        [ProtoMember(2)] internal double CurrentCount;
        [ProtoMember(3)] internal float MaxCount;
        [ProtoMember(4)] internal double ConnectorCount;
        [ProtoMember(5)] internal double[] DirectionCounts = Array.Empty<double>();
        [ProtoMember(6)] internal bool EvaluationDisabled;
    }

    [ProtoContract]
    internal sealed class RuntimeManifestCount
    {
        [ProtoMember(1)] internal string Name;
        [ProtoMember(2)] internal int Count;
    }

    [ProtoContract]
    internal sealed class RuntimeLimitEnforcementEvent
    {
        [ProtoMember(1)] internal int Revision;
        [ProtoMember(2)] internal int BlocksPunished;
    }

    [ProtoContract]
    internal sealed class GroupRuntimeState
    {
        [ProtoMember(1)] internal long GroupId;
        [ProtoMember(2)] internal int Revision;
        [ProtoMember(3)] internal long[] GridIds = Array.Empty<long>();
        [ProtoMember(4)] internal string CoreSubtypeId;
        [ProtoMember(5)] internal long MainCoreBlockId;
        [ProtoMember(6)] internal int CoreCount;
        [ProtoMember(7)] internal long DirectionReferenceBlockId;
        [ProtoMember(8)] internal long OwnerId;
        [ProtoMember(9)] internal bool Deactivated;
        [ProtoMember(10)] internal bool Ignored;
        [ProtoMember(11)] internal bool PunishModifiers;
        [ProtoMember(12)] internal bool PunishSpeed;
        [ProtoMember(13)] internal bool PunishLimitedBlocks;
        [ProtoMember(14)] internal int BlockCount;
        [ProtoMember(15)] internal int Pcu;
        [ProtoMember(16)] internal float Mass;
        [ProtoMember(17)] internal float DryMass;
        [ProtoMember(18)] internal int MaxBlocks;
        [ProtoMember(19)] internal int MaxPcu;
        [ProtoMember(20)] internal float MaxMass;
        [ProtoMember(21)] internal RuntimeLimitState[] Limits = Array.Empty<RuntimeLimitState>();
        [ProtoMember(22)] internal GridModifiersData Modifiers;
        [ProtoMember(23)] internal SpeedModifiersData SpeedModifiers;
        [ProtoMember(24)] internal float BaseSpeed;
        [ProtoMember(25)] internal float EffectiveSpeed;
        [ProtoMember(26)] internal long SpeedSourceGridId;
        [ProtoMember(27)] internal bool FrictionEnabled;
        [ProtoMember(28)] internal float FrictionMaximumDecelerationOverride;
        [ProtoMember(29)] internal float MinimumFrictionSpeedAbsoluteOverride;
        [ProtoMember(30)] internal float MaximumFrictionSpeedAbsoluteOverride;
        [ProtoMember(31)] internal float MinimumFrictionSpeedModifierOverride;
        [ProtoMember(32)] internal float MaximumFrictionSpeedModifierOverride;
        [ProtoMember(33)] internal bool BoostActive;
        [ProtoMember(34)] internal float BoostDurationTimer;
        [ProtoMember(35)] internal float BoostCooldownTimer;
        [ProtoMember(36)] internal bool ActiveDefense;
        [ProtoMember(37)] internal float ActiveDefenseDurationTimer;
        [ProtoMember(38)] internal float ActiveDefenseCooldownTimer;
        [ProtoMember(39)] internal bool PowerOverclockActive;
        [ProtoMember(40)] internal float PowerOverclockDurationTimer;
        [ProtoMember(41)] internal float PowerOverclockCooldownTimer;
        [ProtoMember(42)] internal long RepresentativeGridId;
        [ProtoMember(43)] internal bool EffectiveBoostActive;
        [ProtoMember(44)] internal int PlayerCoreCount;
        [ProtoMember(45)] internal int FactionCoreCount;
        [ProtoMember(46)] internal RuntimeManifestCount[] ManifestCounts = Array.Empty<RuntimeManifestCount>();
        [ProtoMember(47)] internal string[] SpeedPunishmentReasons = Array.Empty<string>();
        [ProtoMember(48)] internal string[] ModifierPunishmentReasons = Array.Empty<string>();
        [ProtoMember(49)] internal string[] LimitedBlockPunishmentReasons = Array.Empty<string>();
        [ProtoMember(50)] internal int LimitRevision;
        [ProtoMember(51)] internal int LimitEnforcementRevision;
        [ProtoMember(52)] internal int LastBlocksPunished;
        [ProtoMember(53)] internal bool Removed;
        [ProtoMember(54)] internal RuntimeLimitEnforcementEvent[] LimitEnforcementEvents =
            Array.Empty<RuntimeLimitEnforcementEvent>();
        [ProtoMember(55)] internal int FactionPlayerCount;
        [ProtoMember(56)] internal int EffectiveFactionCoreLimit;
        [ProtoMember(57)] internal bool SpeedRampDownActive;
        [ProtoMember(58)] internal float SpeedRampDownTarget;
        [ProtoMember(59)] internal GridDefenseModifiersData PassiveDefenseModifiers;
        [ProtoMember(60)] internal GridDefenseModifiersData ActiveDefenseModifiers;
    }
}
