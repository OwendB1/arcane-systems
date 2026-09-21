using System;
using ProtoBuf;

// ReSharper disable InconsistentNaming
// ReSharper disable MemberCanBePrivate.Global
// ReSharper disable FieldCanBeMadeReadOnly.Global

namespace ShipCoreFramework
{
    /// <summary>
    /// Ship Core Framework API Data Structures.
    /// Other mods can copy this file to get all API-related data types, constants and method IDs.
    /// </summary>
    public static class ApiConstants
    {
        /// <summary>
        /// Process-local API ID for authoritative server consumers.
        /// </summary>
        public const long SERVER_LOCAL_API_ID = 3217652398L;

        /// <summary>
        /// Process-local API ID for read-only client consumers.
        /// Listen hosts and single-player publish this alongside the server-local API.
        /// </summary>
        public const long CLIENT_REPLICA_API_ID = 3217652410L;

        /// <summary>
        /// API Major version.
        /// Increment when you make breaking changes to the API contract.
        /// </summary>
        public const int API_MAJOR = 4;

        /// <summary>
        /// API Minor version.
        /// Increment when you add functionality in a backwards compatible way.
        /// Minor version changes remain compatible as long as the major version matches.
        /// </summary>
        public const int API_MINOR = 6;

        /// <summary>
        /// Encoded API version (Major.Minor) packed into a single int.
        /// Consumers should use major-version compatibility for connection checks.
        /// The full packed value is still useful for logging and optional feature gating.
        /// </summary>
        public const int API_VERSION = (API_MAJOR << 8) | API_MINOR;

        /// <summary>
        /// Extracts the major version from a packed API version.
        /// </summary>
        public static int GetApiMajor(int apiVersion)
        {
            return (apiVersion >> 8) & 0xFF;
        }

        /// <summary>
        /// Extracts the minor version from a packed API version.
        /// </summary>
        public static int GetApiMinor(int apiVersion)
        {
            return apiVersion & 0xFF;
        }

        /// <summary>
        /// Returns true when the supplied API version is compatible with this client/provider.
        /// Compatibility only breaks on major version changes.
        /// </summary>
        public static bool IsApiCompatible(int apiVersion)
        {
            return GetApiMajor(apiVersion) == API_MAJOR;
        }

        /// <summary>
        /// Formats a packed API version as Major.Minor.
        /// </summary>
        public static string FormatApiVersion(int apiVersion)
        {
            return GetApiMajor(apiVersion) + "." + GetApiMinor(apiVersion);
        }

        // Event IDs - Other mods can register handlers for these to receive event notifications.
        // NOTE: If you want cross-assembly safe event payloads, send byte[] and deserialize on the client side.
        public const long EVENT_CORE_ACTIVATED = 3217652399L;
        public const long EVENT_CORE_DEACTIVATED = 3217652400L;
        public const long EVENT_LIMITS_RECALCULATED = 3217652401L;
        public const long EVENT_LIMITS_ENFORCED = 3217652402L;
        public const long EVENT_BOOST_ACTIVATED = 3217652403L;
        public const long EVENT_BOOST_DEACTIVATED = 3217652404L;
        public const long EVENT_ACTIVE_DEFENSE_ACTIVATED = 3217652405L;
        public const long EVENT_ACTIVE_DEFENSE_DEACTIVATED = 3217652406L;
        public const long EVENT_GRID_ADDED_TO_GROUP = 3217652407L;
        public const long EVENT_GRID_REMOVED_FROM_GROUP = 3217652408L;
        public const long EVENT_CONFIG_RECEIVED = 3217652409L;
        public const long EVENT_RUNTIME_SNAPSHOT_READY = 3217652411L;
    }

    /// <summary>
    /// Integer method IDs for the API method factory.
    /// Consumers should prefer these IDs over string keys.
    /// All v4 delegates return MyTuple&lt;int, object&gt;: Item1 is ApiReadStatusData and Item2 is
    /// the documented primitive/MyTuple payload or a serialized DTO byte array.
    /// </summary>
    public static class ApiMethodId
    {
        /// <summary>
        /// Returns <see cref="ApiConstants.API_VERSION"/> as int.
        /// Argument ignored. Payload: int.
        /// </summary>
        public const int GetApiVersion = 0;

        /// <summary>
        /// Gets the provider capability flags.
        /// Signature: object -> MyTuple&lt;int, object&gt; containing an int.
        /// </summary>
        public const int GetCapabilities = 1;

        /// <summary>
        /// Gets provider/config/runtime readiness (serialized ApiReadinessData).
        /// Signature: object -> MyTuple&lt;int, object&gt; containing byte[].
        /// </summary>
        public const int GetReadiness_Binary = 2;

        /// <summary>
        /// Checks whether authoritative/replicated runtime state exists for a grid.
        /// Signature: long -> MyTuple&lt;int, object&gt; containing bool.
        /// </summary>
        public const int GetRuntimeStateAvailability = 3;

        /// <summary>
        /// Gets the active ShipCore configuration for a grid (serialized).
        /// Argument: long grid entity ID. Payload: byte[] (ShipCoreData).
        /// </summary>
        public const int GetGridCore_Binary = 10;

        /// <summary>
        /// Gets a specific ShipCore configuration by its SubtypeId (serialized).
        /// Argument: string subtype ID. Payload: byte[] (ShipCoreData).
        /// </summary>
        public const int GetCoreBySubtypeId_Binary = 11;

        /// <summary>
        /// Gets all available ShipCore configurations loaded by the framework (serialized).
        /// Argument ignored. Payload: byte[] (List&lt;ShipCoreData&gt;).
        /// </summary>
        public const int GetAllCoreConfigs_Binary = 12;

        /// <summary>
        /// Gets block limit status for a grid (serialized).
        /// Argument: long grid entity ID. Payload: byte[] (Dictionary&lt;string, LimitStatusData&gt;).
        /// </summary>
        public const int GetBlockLimitsStatus_Binary = 13;

        /// <summary>
        /// Checks if adding blocks would violate limits.
        /// Argument: MyTuple&lt;long, string, string, int&gt;. Payload: bool.
        /// </summary>
        public const int IsBlockAllowed = 14;

        /// <summary>
        /// Gets current grid modifiers (serialized).
        /// Argument: long grid entity ID. Payload: byte[] (GridModifiersData).
        /// </summary>
        public const int GetGridModifiers_Binary = 15;

        /// <summary>
        /// Gets the maximum speed allowed for a grid based on its core.
        /// Argument: long grid entity ID. Payload: float.
        /// </summary>
        public const int GetMaxSpeed = 16;

        /// <summary>
        /// Checks if boost is currently active for a grid.
        /// Argument: long grid entity ID. Payload: bool.
        /// </summary>
        public const int IsBoostActive = 17;

        /// <summary>
        /// Gets the currently selected NoCore configuration (serialized).
        /// Argument ignored. Payload: byte[] (ShipCoreData).
        /// </summary>
        public const int GetNoCoreConfig_Binary = 18;
        
        /// <summary>
        /// Gets the SpeedModifiers for the grid's active core (serialized).
        /// Argument: long grid entity ID. Payload: byte[] (SpeedModifiersData).
        /// </summary>
        public const int GetSpeedModifiers_Binary = 19;
        

        /// <summary>
        /// Gets BoostResistance from the grid's active core SpeedModifiers.
        /// Argument: long grid entity ID. Payload: float.
        /// </summary>
        public const int GetBoostResistance = 20;

        /// <summary>
        /// Gets base max speed in m/s (without boost), based on core SpeedModifiers.
        /// Argument: long grid entity ID. Payload: float.
        /// </summary>
        public const int GetBaseMaxSpeed = 21;

        /// <summary>
        /// Gets max boost multiplier (core SpeedModifiers.MaxBoost).
        /// Argument: long grid entity ID. Payload: float.
        /// </summary>
        public const int GetMaxBoostMultiplier = 22;

        /// <summary>
        /// Gets boost duration in seconds (core SpeedModifiers.BoostDuration).
        /// Argument: long grid entity ID. Payload: float.
        /// </summary>
        public const int GetBoostDuration = 23;

        /// <summary>
        /// Gets boost cooldown in seconds (core SpeedModifiers.BoostCoolDown).
        /// Argument: long grid entity ID. Payload: float.
        /// </summary>
        public const int GetBoostCooldown = 24;

        /// <summary>
        /// Enables/disables friction-based speed limiting for a logical grid group.
        /// Friction cores are enabled by default; this is a runtime override.
        /// Server only. Argument: MyTuple&lt;long, bool&gt;. Payload: MyTuple&lt;bool, string&gt;.
        /// </summary>
        public const int SetFrictionEnabledForGroup = 25;

        /// <summary>
        /// Gets whether friction-based speed limiting is currently active for a logical grid group.
        /// Argument: long grid entity ID. Payload: bool.
        /// </summary>
        public const int GetFrictionEnabledForGroup = 26;

        /// <summary>
        /// Sets the maximum friction deceleration (m/s^2) override for a logical grid group.
        /// Use a value &gt;= 0 to override the core/config value.
        /// Server only. Argument: MyTuple&lt;long, float&gt;. Payload: MyTuple&lt;bool, string&gt;.
        /// </summary>
        public const int SetFrictionMaximumDecelerationForGroup = 27;

        /// <summary>
        /// Clears the maximum friction deceleration override for a logical grid group.
        /// Server only. Argument: long grid entity ID. Payload: MyTuple&lt;bool, string&gt;.
        /// </summary>
        public const int ClearFrictionMaximumDecelerationForGroup = 28;

        /// <summary>
        /// Gets the maximum friction deceleration override for a logical grid group.
        /// Returns -1 if no override is set.
        /// Argument: long grid entity ID. Payload: float.
        /// </summary>
        public const int GetFrictionMaximumDecelerationForGroup = 29;

        /// <summary>
        /// Gets the current world setting for how friction speeds are interpreted.
        /// 0 = Modifier, 1 = Absolute.
        /// Argument ignored. Payload: int.
        /// </summary>
        public const int GetFrictionSpeedValueMode = 30;

        /// <summary>
        /// Sets the minimum friction speed override (absolute m/s) for a logical grid group.
        /// Use a value &lt; 0 to clear the override.
        /// Server only. Argument: MyTuple&lt;long, float&gt;. Payload: MyTuple&lt;bool, string&gt;.
        /// </summary>
        public const int SetFrictionMinimumSpeedAbsoluteForGroup = 31;

        /// <summary>
        /// Sets the maximum friction speed override (absolute m/s) for a logical grid group.
        /// Use a value &lt; 0 to clear the override.
        /// Server only. Argument: MyTuple&lt;long, float&gt;. Payload: MyTuple&lt;bool, string&gt;.
        /// </summary>
        public const int SetFrictionMaximumSpeedAbsoluteForGroup = 32;

        /// <summary>
        /// Gets the minimum friction speed override (absolute m/s) for a logical grid group.
        /// Returns -1 if no override is set.
        /// Argument: long grid entity ID. Payload: float.
        /// </summary>
        public const int GetFrictionMinimumSpeedAbsoluteForGroup = 33;

        /// <summary>
        /// Gets the maximum friction speed override (absolute m/s) for a logical grid group.
        /// Returns -1 if no override is set.
        /// Argument: long grid entity ID. Payload: float.
        /// </summary>
        public const int GetFrictionMaximumSpeedAbsoluteForGroup = 34;

        /// <summary>
        /// Sets the minimum friction speed override (modifier) for a logical grid group.
        /// Use a value &lt; 0 to clear the override.
        /// Server only. Argument: MyTuple&lt;long, float&gt;. Payload: MyTuple&lt;bool, string&gt;.
        /// </summary>
        public const int SetFrictionMinimumSpeedModifierForGroup = 35;

        /// <summary>
        /// Sets the maximum friction speed override (modifier) for a logical grid group.
        /// Use a value &lt; 0 to clear the override.
        /// Server only. Argument: MyTuple&lt;long, float&gt;. Payload: MyTuple&lt;bool, string&gt;.
        /// </summary>
        public const int SetFrictionMaximumSpeedModifierForGroup = 36;

        /// <summary>
        /// Gets the minimum friction speed override (modifier) for a logical grid group.
        /// Returns -1 if no override is set.
        /// Argument: long grid entity ID. Payload: float.
        /// </summary>
        public const int GetFrictionMinimumSpeedModifierForGroup = 37;

        /// <summary>
        /// Gets the maximum friction speed override (modifier) for a logical grid group.
        /// Returns -1 if no override is set.
        /// Argument: long grid entity ID. Payload: float.
        /// </summary>
        public const int GetFrictionMaximumSpeedModifierForGroup = 38;

        /// <summary>
        /// Gets whether the logical grid group has been deactivated.
        /// Argument: long grid entity ID. Payload: bool.
        /// </summary>
        public const int IsGroupDeactivated = 39;

        /// <summary>
        /// Gets the full effective framework configuration (serialized).
        /// Argument ignored. Payload: byte[] (ModConfigData).
        /// </summary>
        public const int GetFullConfig_Binary = 40;

        /// <summary>
        /// Gets the authoritative cached mass used by mass-limit enforcement for a logical grid group.
        /// Server only. Argument: long grid entity ID. Payload: float in kilograms.
        /// </summary>
        public const int GetGroupMass = 41;

        /// <summary>
        /// Overrides effective grid modifiers for a logical grid group.
        /// Pass null to clear the override and restore the core/upgrade profile.
        /// Server only. Argument: MyTuple&lt;long, GridModifiersData&gt;.
        /// </summary>
        public const int SetGridModifiersOverrideForGroup = 42;

        /// <summary>
        /// Overrides effective speed modifiers for a logical grid group.
        /// Pass null to clear the override and restore the core/upgrade profile.
        /// Server only. Argument: MyTuple&lt;long, SpeedModifiersData&gt;.
        /// </summary>
        public const int SetSpeedModifiersOverrideForGroup = 43;

        /// <summary>
        /// Overrides effective passive defense modifiers for a logical grid group.
        /// Pass null to clear the override and restore the core/upgrade profile.
        /// Server only. Argument: MyTuple&lt;long, GridDefenseModifiersData&gt;.
        /// </summary>
        public const int SetPassiveDefenseModifiersOverrideForGroup = 44;

        /// <summary>
        /// Overrides effective active defense modifiers for a logical grid group.
        /// Pass null to clear the override and restore the core/upgrade profile.
        /// Server only. Argument: MyTuple&lt;long, GridDefenseModifiersData&gt;.
        /// </summary>
        public const int SetActiveDefenseModifiersOverrideForGroup = 45;
    }

    // ===== Data Structures (DTOs) =====
    //
    // IMPORTANT:
    // These DTOs are intended to be serialized to byte[] by the provider and deserialized by the consumer.
    // The consumer must not attempt to cast provider DTO instances directly.
    //
    // ProtoBuf attributes are used because Space Engineers commonly supports protobuf-net serialization.
    // Fields remain public for simplicity.

    public enum ApiProviderRoleData
    {
        Unknown = 0,
        ServerLocalAuthority = 1,
        ClientLocalReplica = 2
    }

    [Flags]
    public enum ApiCapabilityData
    {
        None = 0,
        ConfigQueries = 1,
        RuntimeQueries = 2,
        RuntimeMutations = 4,
        Authoritative = 8,
        Replicated = 16,
        BestEffortPlacementChecks = 32
    }

    public enum ApiReadStatusData
    {
        Success = 0,
        ProviderNotReady = 1,
        ConfigPending = 2,
        RuntimePending = 3,
        GridNotReplicated = 4,
        InvalidArgument = 5,
        Unsupported = 6,
        Error = 7,
        ConfigurationUnavailable = 8
    }

    /// <summary>
    /// Strongly typed local result returned by the supplied API wrappers.
    /// Provider transport values remain cross-assembly-safe primitives/byte arrays.
    /// </summary>
    public sealed class ApiReadResult<T>
    {
        public ApiReadStatusData Status;
        public T Value;
        public string Error;

        public bool Success
        {
            get { return Status == ApiReadStatusData.Success; }
        }
    }

    [ProtoContract]
    public class ApiReadinessData
    {
        [ProtoMember(1)] public ApiProviderRoleData Role;
        [ProtoMember(2)] public bool ProviderReady;
        [ProtoMember(3)] public bool ConfigReady;
        [ProtoMember(4)] public bool RuntimeSnapshotReady;
        [ProtoMember(5)] public string ConfigurationError;
    }

    /// <summary>
    /// Ship Core configuration data.
    /// </summary>
    [ProtoContract]
    public class ShipCoreData
    {
        [ProtoMember(1)] public string SubtypeId;
        [ProtoMember(2)] public string UniqueName;
        [ProtoMember(3)] public bool ForceBroadCast;
        [ProtoMember(4)] public float ForceBroadCastRange;
        [ProtoMember(5)] public MobilityTypeData MobilityTypeData;
        [ProtoMember(6)] public int MaxBlocks;
        [ProtoMember(7)] public float MaxMass;
        [ProtoMember(8)] public int MaxPCU;
        [ProtoMember(9)] public int MaxPerFaction;
        [ProtoMember(10)] public int MaxPerPlayer;
        [ProtoMember(11)] public int MinPlayers;
        [ProtoMember(12)] public GridModifiersData Modifiers;
        [ProtoMember(13)] public GridDefenseModifiersData PassiveDefenseModifiers;
        [ProtoMember(14)] public bool SpeedBoostEnabled;
        [ProtoMember(15)] public bool EnableActiveDefenseModifiers;
        [ProtoMember(16)] public GridDefenseModifiersData ActiveDefenseModifiers;
        [ProtoMember(17)] public bool DynamicBoostEnabled;
        [ProtoMember(18)] public SpeedModifiersData SpeedModifiers;
        [ProtoMember(19)] public int MinBlocks;
        [ProtoMember(20)] public int MaxPlayers;
        [ProtoMember(21)] public bool IsDeactivated;
        [ProtoMember(22)] public int FactionPlayersNeededPerCore;
        [ProtoMember(23)] public string ManifestGroupName;
        [ProtoMember(24)] public int ManifestGroupMaxCount;
        [ProtoMember(25)] public int ManifestGroupCurrentCount;
        [ProtoMember(26)] public ManifestGroupLimitData[] ManifestGroups = Array.Empty<ManifestGroupLimitData>();
        [ProtoMember(27)] public string[] ManifestGroupNames = Array.Empty<string>();
        [ProtoMember(28)] public string[] ConnectorBlacklistCoreSubtypeIds = Array.Empty<string>();
        [ProtoMember(29)] public int MaxBackupCores;
        [ProtoMember(30)] public UpgradeModuleAllowanceData[] AllowedUpgradeModules = Array.Empty<UpgradeModuleAllowanceData>();
        [ProtoMember(31)] public SpeedLimitTypeData SpeedLimitTypeData;
        [ProtoMember(32)] public BlockLimitData[] BlockLimits = Array.Empty<BlockLimitData>();
        [ProtoMember(33)] public int CoreSelectionPriority;
        [ProtoMember(34)] public bool CrossConnectorPunishmentWhitelisted;
        [ProtoMember(35)] public FactionRankData MinFactionRank;
        [ProtoMember(36)] public SpeedOverrideModeData SpeedOverrideMode = SpeedOverrideModeData.OnlyIfHeavier;
        [ProtoMember(37)] public int SpeedOverridePriority;
        [ProtoMember(38)] public bool PowerOverclockEnabled;
        [ProtoMember(39)] public float PowerOverclockMultiplier = 1f;
        [ProtoMember(40)] public float PowerOverclockDuration = 10f;
        [ProtoMember(41)] public float PowerOverclockCooldown = 60f;
        [ProtoMember(42)] public float PowerOverclockDamagePerSecond;
    }

    [ProtoContract]
    public class ManifestGroupLimitData
    {
        [ProtoMember(1)] public string Name;
        [ProtoMember(2)] public int MaxCount;
        [ProtoMember(3)] public int CurrentCount;
    }

    /// <summary>
    /// Full effective mod configuration data.
    /// </summary>
    [ProtoContract]
    public class ModConfigData
    {
        [ProtoMember(1)] public bool IgnoreAiFactions;
        [ProtoMember(2)] public string[] IgnoredFactionTags = Array.Empty<string>();
        [ProtoMember(3)] public string SelectedNoCoreUniqueName;
        [ProtoMember(4)] public bool DebugMode;
        [ProtoMember(5)] public bool CombatLogging;
        [ProtoMember(6)] public int LogLevel;
        [ProtoMember(7)] public int ClientOutputLogLevel;
        [ProtoMember(8)] public float MaxPossibleSpeedMetersPerSecond;
        // API v4 wire compatibility. Framework mass is always full-definition dry mass.
        [ProtoMember(9)] public MassTypeModeData MassTypeMode;
        [ProtoMember(10)] public FrictionSpeedValueModeData FrictionSpeedValueMode;
        [ProtoMember(11)] public NoFlyZoneData[] NoFlyZones = Array.Empty<NoFlyZoneData>();
        [ProtoMember(12)] public ShipCoreData[] NoCoreConfigs = Array.Empty<ShipCoreData>();
        [ProtoMember(13)] public ShipCoreData[] ShipCores = Array.Empty<ShipCoreData>();
        [ProtoMember(14)] public ManifestCoreGroupData[] ManifestCoreGroups = Array.Empty<ManifestCoreGroupData>();
        [ProtoMember(15)] public UpgradeModuleConfigData[] UpgradeModules = Array.Empty<UpgradeModuleConfigData>();
        [ProtoMember(16)] public ShipCoreData SelectedNoCore;
        [ProtoMember(17)] public BlockGroupData[] BlockGroups = Array.Empty<BlockGroupData>();
        [ProtoMember(18)] public bool BlockDirectionalPlacementOnSubgrids = true;
        [ProtoMember(19)] public bool AllowUnattachedUpgradeModules;
        [ProtoMember(20)] public int NoCoreGraceSeconds = 30;
        [ProtoMember(21)] public int MinimumBlocksGraceSeconds = 30;
        [ProtoMember(22)] public double CombatLoggingBroadcastRangeMeters = 20000d;
        [ProtoMember(23)] public float SpeedRampDownPercentage = 5f;
        [ProtoMember(24)] public bool CreativeCoreCountLimitsEnabled = true;
    }

    [ProtoContract]
    public class ManifestCoreGroupData
    {
        [ProtoMember(1)] public string Name;
        [ProtoMember(2)] public int MaxCount;
        [ProtoMember(3)] public string[] CoreSubtypeIds = Array.Empty<string>();
    }

    [ProtoContract]
    public class NoFlyZoneData
    {
        [ProtoMember(1)] public int Id;
        [ProtoMember(2)] public Vector3DData Position;
        [ProtoMember(3)] public double Radius;
        [ProtoMember(4)] public string[] AllowedCoresSubtype = Array.Empty<string>();
        [ProtoMember(5)] public bool ForceOff;
    }

    [ProtoContract]
    public class Vector3DData
    {
        [ProtoMember(1)] public double X;
        [ProtoMember(2)] public double Y;
        [ProtoMember(3)] public double Z;
    }

    [ProtoContract]
    public class UpgradeModuleAllowanceData
    {
        [ProtoMember(1)] public string SubtypeId;
        [ProtoMember(2)] public int MaxCount;
        [ProtoMember(3)] public string UniqueName;
        [ProtoMember(4)] public string TypeId;
    }

    [ProtoContract]
    public class UpgradeModuleConfigData
    {
        [ProtoMember(1)] public string SubtypeId;
        [ProtoMember(2)] public string UniqueName;
        [ProtoMember(3)] public UpgradeStatModifierData[] Modifiers = Array.Empty<UpgradeStatModifierData>();
        [ProtoMember(4)] public BlockLimitModifierData[] BlockLimitModifiers = Array.Empty<BlockLimitModifierData>();
        [ProtoMember(5)] public string TypeId;
        [ProtoMember(6)] public CapacityModifierData[] CapacityModifiers = Array.Empty<CapacityModifierData>();
    }

    [ProtoContract]
    public class UpgradeStatModifierData
    {
        [ProtoMember(1)] public string Stat;
        [ProtoMember(2)] public float Value;
        [ProtoMember(3)] public UpgradeModifierOperationData ModifierType;
    }

    [ProtoContract]
    public class BlockLimitModifierData
    {
        [ProtoMember(1)] public string BlockLimitName;
        [ProtoMember(2)] public float Value;
        [ProtoMember(3)] public UpgradeModifierOperationData ModifierType;
    }

    [ProtoContract]
    public class CapacityModifierData
    {
        [ProtoMember(1)] public string Stat;
        [ProtoMember(2)] public float Value;
        [ProtoMember(3)] public UpgradeModifierOperationData ModifierType;
    }

    [ProtoContract]
    public class BlockLimitData
    {
        [ProtoMember(1)] public string Name;
        [ProtoMember(2)] public string[] BlockGroupNames = Array.Empty<string>();
        [ProtoMember(3)] public float MaxCount;
        [ProtoMember(4)] public bool CrossConnectorPunishment;
        [ProtoMember(5)] public bool PunishByNoFlyZone;
        [ProtoMember(6)] public PunishmentTypeData PunishmentType;
        [ProtoMember(7)] public DirectionTypeData[] AllowedDirections = Array.Empty<DirectionTypeData>();
        [ProtoMember(8)] public bool IsCriticalLimit;
        [ProtoMember(9)] public string[] ExcludedBlockGroupNames = Array.Empty<string>();
        [ProtoMember(10)] public float MaxCountPerDirection = -1f;
        [ProtoMember(11)] public LimitVisibilityData LimitVisibility;
        [ProtoMember(12)] public bool IgnoredByNpc;
        [ProtoMember(13)] public DirectionBudgetData[] DirectionBudgets = Array.Empty<DirectionBudgetData>();
    }

    [ProtoContract]
    public class DirectionBudgetData
    {
        [ProtoMember(1)] public DirectionTypeData Direction;
        [ProtoMember(2)] public float MaxCount;
    }

    [ProtoContract]
    public class BlockGroupData
    {
        [ProtoMember(1)] public string Name;
        [ProtoMember(2)] public BlockTypeData[] BlockTypes = Array.Empty<BlockTypeData>();
    }

    [ProtoContract]
    public class BlockTypeData
    {
        [ProtoMember(1)] public string TypeId;
        [ProtoMember(2)] public string SubtypeId;
        [ProtoMember(3)] public float CountWeight;
        [ProtoMember(4)] public DirectionTypeData PrimaryDirection;
    }

    /// <summary>
    /// Grid modifiers data (performance multipliers).
    /// </summary>
    [ProtoContract]
    public class GridModifiersData
    {
        [ProtoMember(1)] public float AssemblerSpeed;
        [ProtoMember(2)] public float DrillHarvestMultiplier;
        [ProtoMember(3)] public float GyroEfficiency;
        [ProtoMember(4)] public float GyroForce;
        [ProtoMember(5)] public float PowerProducersOutput;
        [ProtoMember(6)] public float RefineEfficiency;
        [ProtoMember(7)] public float RefineSpeed;
        [ProtoMember(8)] public float ThrusterEfficiency;
        [ProtoMember(9)] public float ThrusterForce;
    }

    /// <summary>
    /// Speed modifiers data (movement/boost tuning).
    /// </summary>
    [ProtoContract]
    public class SpeedModifiersData
    {
        [ProtoMember(1)] public float MaxSpeed;
        [ProtoMember(2)] public float MaxBoost;
        [ProtoMember(3)] public float BoostDuration;
        [ProtoMember(4)] public float BoostCoolDown;

        // Legacy field kept for backwards compatibility (previously BoostResistance).
        [ProtoMember(5)] public float BoostResistance;

        // Friction tuning
        [ProtoMember(6)] public float MinimumFrictionSpeedAbsolute;
        [ProtoMember(7)] public float MaximumFrictionSpeedAbsolute;
        [ProtoMember(8)] public float MaximumFrictionDeceleration;
        [ProtoMember(9)] public float MinimumFrictionSpeedModifier;
        [ProtoMember(10)] public float MaximumFrictionSpeedModifier;
        [ProtoMember(11)] public FrictionCurveSegmentData[] FrictionCurve = Array.Empty<FrictionCurveSegmentData>();
        [ProtoMember(12)] public float CruiseFrictionMultiplier;
        [ProtoMember(13)] public float CruiseAccelerationThreshold;
        [ProtoMember(14)] public AtmosphericFrictionData AtmosphericFriction;
        [ProtoMember(15)] public float MaxAngularVelocity;
    }

    [ProtoContract]
    public class FrictionCurveSegmentData
    {
        [ProtoMember(1)] public float StartSpeed;
        [ProtoMember(2)] public float EndSpeed;
        [ProtoMember(3)] public float StartDeceleration;
        [ProtoMember(4)] public float EndDeceleration;
    }

    [ProtoContract]
    public class AtmosphericFrictionData
    {
        [ProtoMember(1)] public FrictionCurveSegmentData[] FrictionCurve = Array.Empty<FrictionCurveSegmentData>();
        [ProtoMember(2)] public float CruiseFrictionMultiplier;
        [ProtoMember(3)] public float CruiseAccelerationThreshold;
        [ProtoMember(4)] public float AirDensityThreshold;
        [ProtoMember(5)] public bool Enabled = true;
    }

    /// <summary>
    /// Defense modifiers data (damage reduction multipliers).
    /// </summary>
    [ProtoContract]
    public class GridDefenseModifiersData
    {
        [ProtoMember(1)] public float Bullet;
        [ProtoMember(2)] public float PostShield;
        [ProtoMember(3)] public float Duration;
        [ProtoMember(4)] public float Cooldown;
        [ProtoMember(5)] public float Rocket;
        [ProtoMember(6)] public float Explosion;
        [ProtoMember(7)] public float Environment;
        [ProtoMember(8)] public float Energy;
        [ProtoMember(9)] public float Kinetic;
    }

    /// <summary>
    /// Status information for a block limit.
    /// </summary>
    [ProtoContract]
    public class LimitStatusData
    {
        [ProtoMember(1)] public string Name;
        [ProtoMember(2)] public double Current;
        [ProtoMember(3)] public double Max;
        [ProtoMember(4)] public bool IsOverLimit;

        public override string ToString()
        {
            return $"{Name}: {Current:F1}/{Max:F1} {(IsOverLimit ? "[OVER LIMIT]" : "")}";
        }
    }

    /// <summary>
    /// Mobility type data for a grid core.
    /// </summary>
    public enum MobilityTypeData
    {
        Static = 0,
        Mobile = 1,
        Both = 2
    }

    public enum FrictionSpeedValueModeData
    {
        Modifier = 0,
        Absolute = 1
    }

    public enum SpeedLimitTypeData
    {
        Normal = 0,
        Friction = 1
    }

    public enum SpeedOverrideModeData
    {
        None = 0,
        OnlyIfHeavier = 1,
        Priority = 2,
        Any = 3
    }

    public enum MassTypeModeData
    {
        Dry = 0,
        Wet = 1
    }

    public enum UpgradeModifierOperationData
    {
        Additive = 0,
        Multiplicative = 1
    }

    public enum PunishmentTypeData
    {
        ShutOff = 0,
        Damage = 1,
        Delete = 2,
        Explode = 3,
        DeleteWithoutRefund = 4
    }

    public enum DirectionTypeData
    {
        Forward = 0,
        Backward = 1,
        Up = 2,
        Down = 3,
        Left = 4,
        Right = 5,
        Any = 6
    }

    public enum LimitVisibilityData
    {
        Always = 0,
        NearLimit = 1,
        Hidden = 2
    }

    public enum FactionRankData
    {
        None = 0,
        Member = 1,
        Leader = 2,
        Founder = 3
    }

    // ===== Event Argument Classes =====
    //
    // NOTE:
    // If you keep sending these directly as objects across assemblies, consumers will hit the same type identity issue.
    // If you want events to be cross-assembly safe, the recommended approach is to send byte[] payloads and deserialize.

    /// <summary>
    /// Event arguments for CoreActivated event.
    /// Fired when a core becomes the main/active core for a grid group.
    /// </summary>
    [ProtoContract]
    public class CoreActivatedEventArgs
    {
        [ProtoMember(1)] public long GroupGridId;
        [ProtoMember(2)] public string CoreSubtypeId;
        [ProtoMember(3)] public string CoreName;
        [ProtoMember(4)] public DateTime Timestamp;
    }

    /// <summary>
    /// Event arguments for CoreDeactivated event.
    /// Fired when all cores are destroyed or the group loses its main core.
    /// </summary>
    [ProtoContract]
    public class CoreDeactivatedEventArgs
    {
        [ProtoMember(1)] public long GroupGridId;
        [ProtoMember(2)] public string PreviousCoreSubtypeId;
        [ProtoMember(3)] public string PreviousCoreName;
        [ProtoMember(4)] public DateTime Timestamp;
    }

    /// <summary>
    /// Event arguments for LimitsRecalculated event.
    /// Fired when block limits are recalculated for a grid group.
    /// </summary>
    [ProtoContract]
    public class LimitsRecalculatedEventArgs
    {
        [ProtoMember(1)] public long GroupGridId;
        [ProtoMember(2)] public DateTime Timestamp;
    }

    /// <summary>
    /// Event arguments for LimitsEnforced event.
    /// Fired when block limit enforcement runs and blocks are punished.
    /// </summary>
    [ProtoContract]
    public class LimitsEnforcedEventArgs
    {
        [ProtoMember(1)] public long GroupGridId;
        [ProtoMember(2)] public int BlocksPunished;
        [ProtoMember(3)] public DateTime Timestamp;
    }

    /// <summary>
    /// Event arguments for Boost activation/deactivation events.
    /// </summary>
    [ProtoContract]
    public class BoostEventArgs
    {
        [ProtoMember(1)] public long GroupGridId;
        [ProtoMember(2)] public DateTime Timestamp;
    }

    /// <summary>
    /// Event arguments for Active Defense activation/deactivation events.
    /// </summary>
    [ProtoContract]
    public class ActiveDefenseEventArgs
    {
        [ProtoMember(1)] public long GroupGridId;
        [ProtoMember(2)] public DateTime Timestamp;
    }

    /// <summary>
    /// Event arguments for grid group membership changes.
    /// </summary>
    [ProtoContract]
    public class GridGroupEventArgs
    {
        [ProtoMember(1)] public long GridId;
        [ProtoMember(2)] public long GroupGridId;
        [ProtoMember(3)] public DateTime Timestamp;
    }

    /// <summary>
    /// Event arguments for config synchronization from server.
    /// </summary>
    [ProtoContract]
    public class ConfigReceivedEventArgs
    {
        [ProtoMember(1)] public ModConfigData Config;
        [ProtoMember(2)] public DateTime Timestamp;
    }

    /// <summary>
    /// Event arguments for the first complete authoritative runtime snapshot applied by a remote client.
    /// Server-local consumers receive this after the initial group scan completes.
    /// </summary>
    [ProtoContract]
    public class RuntimeSnapshotReadyEventArgs
    {
        [ProtoMember(1)] public int Sequence;
        [ProtoMember(2)] public int SnapshotRevision;
        [ProtoMember(3)] public DateTime Timestamp;
    }
}
