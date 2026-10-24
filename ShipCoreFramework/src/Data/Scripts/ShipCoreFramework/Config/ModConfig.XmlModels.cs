using System;
using System.Collections.Generic;
using System.Xml.Serialization;
using VRageMath;

namespace ShipCoreFramework
{
    [XmlRoot("ModConfig")]
    public partial class ModConfig
    {
        [XmlIgnore] private const string GlobalConfigFileName = "ShipCoreConfig_World.xml";
        [XmlIgnore] private const string CoreManifestFileName = @"Data\ShipCoreConfig_Manifest.xml";
        [XmlIgnore] private const string BlockGroupsFileName = @"Data\ShipCoreConfig_Groups.xml";
        [XmlIgnore] private const string DefaultNoCoreFileName = @"Data\ShipCoreConfig_No_Core.xml";
        [XmlIgnore] private const string LegacyIgnoreAiKey = "ShipCore.IgnoreAiV1";
        [XmlIgnore] private const string LegacyIgnoredFactionsKey = "ShipCore.IgnoredFactionsV1";
        [XmlIgnore] private const string LegacySelectedNoCoreKey = "ShipCore.SelectedNoCoreBlobV1";
        [XmlIgnore] internal const double DefaultCombatLoggingBroadcastRangeMeters = 20000d;
        [XmlIgnore] private static readonly string[] DefaultIgnoredFactionTagValues =
        {
            "SPRT", "ADMIN", "FMCA", "BORG", "TERA"
        };
        [XmlIgnore] public readonly List<ShipCore> NoCoreConfigs = new List<ShipCore>();
        [XmlIgnore] public readonly List<BlockGroup> BlockGroups = new List<BlockGroup>();
        [XmlIgnore] public readonly List<ShipCore> ShipCores = new List<ShipCore>();
        [XmlIgnore] public readonly List<ManifestCoreGroup> ManifestCoreGroups = new List<ManifestCoreGroup>();
        [XmlIgnore] public readonly List<UpgradeModuleConfig> UpgradeModules = new List<UpgradeModuleConfig>();
        [XmlIgnore] private readonly HashSet<string> _trackedUpgradeModuleBlockIds =
            new HashSet<string>(StringComparer.OrdinalIgnoreCase);

        [XmlElement("IgnoreAiFactions")]
        public bool IgnoreAiFactions;

        [XmlArray("IgnoredFactionTags")]
        [XmlArrayItem("Tag")]
        public List<string> IgnoredFactionTags = new List<string>();

        [XmlElement("SelectedNoCoreUniqueName")]
        public string SelectedNoCoreUniqueName = string.Empty;

        [XmlIgnore] public ShipCore SelectedNoCore;

        [XmlElement("DebugMode")] public bool DebugMode;
        [XmlElement("CombatLogging")] public bool CombatLogging = true;
        [XmlElement("CombatLoggingBroadcastRangeMeters")]
        public double CombatLoggingBroadcastRangeMeters = DefaultCombatLoggingBroadcastRangeMeters;
        [XmlElement("LOG_LEVEL")] public int LogLevel = 2;
        [XmlElement("CLIENT_OUTPUT_LOG_LEVEL")] public int ClientOutputLogLevel = 2;
        [XmlElement("MaxPossibleSpeedMetersPerSecond")] public float MaxPossibleSpeedMetersPerSecond = 300;
        [XmlElement("SpeedRampDownPercentage")] public float SpeedRampDownPercentage = 5f;
        [XmlElement("FrictionSpeedValueMode")] public FrictionSpeedValueMode FrictionSpeedValueMode = FrictionSpeedValueMode.Modifier;
        [XmlElement("BlockDirectionalPlacementOnSubgrids")] public bool BlockDirectionalPlacementOnSubgrids = true;
        [XmlElement("AllowUnattachedUpgradeModules")] public bool AllowUnattachedUpgradeModules;
        [XmlElement("CreativeCoreCountLimitsEnabled")] public bool CreativeCoreCountLimitsEnabled = true;
        [XmlElement("NoCoreGraceSeconds")] public int NoCoreGraceSeconds = 30;
        [XmlElement("MinimumBlocksGraceSeconds")] public int MinimumBlocksGraceSeconds = 30;
        [XmlElement("NoFlyZones")] public List<Zones> NoFlyZones = new List<Zones>();
    }

    [XmlRoot("Zones")]
    public class Zones
    {
        [XmlElement("ID")]
        public int Id;

        [XmlElement("Position")]
        public Vector3D Position;

        [XmlElement("Radius")]
        public double Radius;

        [XmlElement("AllowedCoresSubtype")]
        public List<string> AllowedCoresSubtype = new List<string>();

        [XmlElement("OverideBlockLimitsForceShutOff")]
        public bool ForceOff;
    }

    [XmlRoot("CoreManifest")]
    public class CoreManifest
    {
        [XmlArray("ManifestGroups")]
        [XmlArrayItem("Group")]
        public List<ManifestCoreGroup> ManifestGroups = new List<ManifestCoreGroup>();
        [XmlElement("CrossConnectorPunishmentWhitelist")]
        public List<string> CrossConnectorPunishmentWhitelist = new List<string>();
        [XmlElement("ShipCore")]
        public List<ManifestShipCoreEntry> ShipCores = new List<ManifestShipCoreEntry>();
        [XmlElement("UpgradeModule")]
        public List<ManifestUpgradeModuleEntry> UpgradeModules = new List<ManifestUpgradeModuleEntry>();
    }

    [XmlRoot("ManifestGroup")]
    public class ManifestCoreGroup
    {
        [XmlElement("Name")]
        public string Name = string.Empty;

        [XmlElement("MaxCount")]
        public int MaxCount = -1;

        [XmlIgnore]
        internal string ConfigSource = string.Empty;

        [XmlIgnore]
        internal string ConfigFile = string.Empty;

        [XmlIgnore]
        public readonly HashSet<string> CoreSubtypeIds = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
    }

    [XmlRoot("ManifestShipCore")]
    public class ManifestShipCoreEntry
    {
        [XmlElement("Filename")]
        public string Filename = string.Empty;

        [XmlElement("Group")]
        public List<string> Groups = new List<string>();

        [XmlElement("CoreSelectionPriority")]
        public int CoreSelectionPriority;

        [XmlElement("BlacklistedCoreSubtypeId")]
        public List<string> BlacklistedCoreSubtypeIds = new List<string>();
    }

    [XmlRoot("ManifestUpgradeModule")]
    public class ManifestUpgradeModuleEntry
    {
        [XmlElement("Filename")]
        public string Filename = string.Empty;
    }

    [XmlRoot("ShipCore")]
    public class ShipCore
    {
        [XmlElement("SubtypeId")]
        public string SubtypeId = string.Empty;

        [XmlElement("UniqueName")]
        public string UniqueName = string.Empty;

        [XmlElement("MaxBackupCores")]
        public int MaxBackupCores = -1;

        [XmlElement("ForceBroadCast")]
        public bool ForceBroadCast;

        [XmlElement("ForceBroadCastRange")]
        public float ForceBroadCastRange;

        [XmlElement("MobilityType")]
        public MobilityType MobilityType = MobilityType.Both;

        [XmlElement("MaxBlocks")]
        public int MaxBlocks = -1;

        [XmlElement("MinBlocks")]
        public int MinBlocks = -1;

        [XmlElement("MaxMass")]
        public float MaxMass = -1;

        [XmlElement("MaxPCU")]
        public int MaxPCU = -1;

        [XmlElement("MaxPerFaction")]
        public int MaxPerFaction = -1;

        [XmlElement("MinPerFaction")]
        public int MinPerFaction = 0;

        [XmlElement("FactionPlayersNeededPerCore")]
        public int FactionPlayersNeededPerCore = -1;

        [XmlElement("MinFactionRank")]
        public FactionRank MinFactionRank = FactionRank.None;

        [XmlElement("MaxPerPlayer")]
        public int MaxPerPlayer = -1;

        [XmlElement("MinPlayers")]
        public int MinPlayers = -1;

        [XmlElement("MaxPlayers")]
        public int MaxPlayers = -1;

        [XmlIgnore]
        public readonly List<string> ManifestGroupNames = new List<string>();

        [XmlIgnore]
        public readonly HashSet<string> ConnectorBlacklistCoreSubtypeIds =
            new HashSet<string>(StringComparer.OrdinalIgnoreCase);

        [XmlIgnore]
        public bool CrossConnectorPunishmentWhitelisted;

        [XmlIgnore]
        public int CoreSelectionPriority;

        [XmlElement("AllowedUpgradeModules")]
        public UpgradeModuleAllowance[] AllowedUpgradeModules = Array.Empty<UpgradeModuleAllowance>();

        [XmlIgnore]
        public readonly Dictionary<string, int> AllowedUpgradeModuleCounts =
            new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);

        [XmlIgnore]
        public readonly Dictionary<string, int> AllowedUpgradeModuleDefinitionCounts =
            new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);

        [XmlIgnore]
        public readonly Dictionary<string, int> AllowedUpgradeModuleUniqueNameCounts =
            new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);

        [XmlElement("Modifiers")]
        public GridModifiers Modifiers = new GridModifiers();

        [XmlElement("PassiveDefenseModifiers")]
        public GridDefenseModifiers PassiveDefenseModifiers = new GridDefenseModifiers();

        [XmlElement("SpeedBoostEnabled")]
        public bool SpeedBoostEnabled;

        [XmlElement("SpeedLimitType")]
        public SpeedLimitType SpeedLimitType;

        [XmlElement("SpeedOverrideMode")]
        public SpeedOverrideMode SpeedOverrideMode = SpeedOverrideMode.OnlyIfHeavier;

        [XmlElement("SpeedOverridePriority")]
        public int SpeedOverridePriority;

        [XmlElement("SpeedModifiers")]
        public SpeedModifiers SpeedModifiers = new SpeedModifiers();

        [XmlElement("EnableActiveDefenseModifiers")]
        public bool EnableActiveDefenseModifiers;

        [XmlElement("ActiveDefenseModifiers")]
        public GridDefenseModifiers ActiveDefenseModifiers = new GridDefenseModifiers();

        [XmlElement("PowerOverclockEnabled")]
        public bool PowerOverclockEnabled;

        [XmlElement("PowerOverclockMultiplier")]
        public float PowerOverclockMultiplier = 1f;

        [XmlElement("PowerOverclockDuration")]
        public float PowerOverclockDuration = 10f;

        [XmlElement("PowerOverclockCooldown")]
        public float PowerOverclockCooldown = 60f;

        [XmlElement("PowerOverclockDamagePerSecond")]
        public float PowerOverclockDamagePerSecond;

        [XmlElement("BlockLimits")]
        public BlockLimit[] BlockLimits = Array.Empty<BlockLimit>();

        [XmlIgnore]
        internal string ConfigSource = string.Empty;

        [XmlIgnore]
        internal string ConfigFile = string.Empty;

        public bool IsUpgradeModuleAllowed(string moduleSubtypeId)
        {
            return IsUpgradeModuleAllowed(string.Empty, ModConfig.DefaultUpgradeModuleTypeId, moduleSubtypeId);
        }

        public bool IsUpgradeModuleAllowed(string moduleUniqueName, string moduleSubtypeId)
        {
            return IsUpgradeModuleAllowed(moduleUniqueName, ModConfig.DefaultUpgradeModuleTypeId, moduleSubtypeId);
        }

        public bool IsUpgradeModuleAllowed(string moduleUniqueName, string moduleTypeId, string moduleSubtypeId)
        {
            int maxCount;
            return TryGetAllowedUpgradeModuleCount(moduleUniqueName, moduleTypeId, moduleSubtypeId, out maxCount);
        }

        public bool TryGetAllowedUpgradeModuleCount(string moduleSubtypeId, out int maxCount)
        {
            return TryGetAllowedUpgradeModuleCount(string.Empty, ModConfig.DefaultUpgradeModuleTypeId, moduleSubtypeId, out maxCount);
        }

        public bool TryGetAllowedUpgradeModuleCount(string moduleUniqueName, string moduleSubtypeId, out int maxCount)
        {
            return TryGetAllowedUpgradeModuleCount(moduleUniqueName, ModConfig.DefaultUpgradeModuleTypeId, moduleSubtypeId, out maxCount);
        }

        public bool TryGetAllowedUpgradeModuleCount(string moduleUniqueName, string moduleTypeId, string moduleSubtypeId, out int maxCount)
        {
            maxCount = 0;

            if (!string.IsNullOrWhiteSpace(moduleSubtypeId))
            {
                var subtypeId = moduleSubtypeId.Trim();
                var typeId = string.IsNullOrWhiteSpace(moduleTypeId)
                    ? ModConfig.DefaultUpgradeModuleTypeId
                    : ModConfig.NormalizeBlockTypeId(moduleTypeId);
                var definitionId = ModConfig.FormatBlockDefinitionId(typeId, subtypeId);
                if (AllowedUpgradeModuleDefinitionCounts.TryGetValue(definitionId, out maxCount))
                    return true;

                if (typeId.Equals(ModConfig.DefaultUpgradeModuleTypeId, StringComparison.OrdinalIgnoreCase) &&
                    AllowedUpgradeModuleCounts.TryGetValue(subtypeId, out maxCount))
                    return true;
            }

            return !string.IsNullOrWhiteSpace(moduleUniqueName) &&
                   AllowedUpgradeModuleUniqueNameCounts.TryGetValue(moduleUniqueName.Trim(), out maxCount);
        }

        public string GetUpgradeModuleAllowanceKey(string moduleUniqueName, string moduleSubtypeId)
        {
            return GetUpgradeModuleAllowanceKey(moduleUniqueName, ModConfig.DefaultUpgradeModuleTypeId, moduleSubtypeId);
        }

        public string GetUpgradeModuleAllowanceKey(string moduleUniqueName, string moduleTypeId, string moduleSubtypeId)
        {
            if (!string.IsNullOrWhiteSpace(moduleSubtypeId))
            {
                var subtypeId = moduleSubtypeId.Trim();
                var typeId = string.IsNullOrWhiteSpace(moduleTypeId)
                    ? ModConfig.DefaultUpgradeModuleTypeId
                    : ModConfig.NormalizeBlockTypeId(moduleTypeId);
                var definitionId = ModConfig.FormatBlockDefinitionId(typeId, subtypeId);
                if (AllowedUpgradeModuleDefinitionCounts.ContainsKey(definitionId))
                    return definitionId;

                if (typeId.Equals(ModConfig.DefaultUpgradeModuleTypeId, StringComparison.OrdinalIgnoreCase) &&
                    AllowedUpgradeModuleCounts.ContainsKey(subtypeId))
                    return subtypeId;
            }

            if (!string.IsNullOrWhiteSpace(moduleUniqueName))
            {
                var uniqueName = moduleUniqueName.Trim();
                if (AllowedUpgradeModuleUniqueNameCounts.ContainsKey(uniqueName))
                    return uniqueName;
            }

            if (string.IsNullOrWhiteSpace(moduleSubtypeId)) return string.Empty;

            var fallbackTypeId = string.IsNullOrWhiteSpace(moduleTypeId)
                ? ModConfig.DefaultUpgradeModuleTypeId
                : moduleTypeId;
            return ModConfig.FormatBlockDefinitionId(fallbackTypeId, moduleSubtypeId);
        }

        public bool IsConnectorBlacklistedCore(string coreSubtypeId)
        {
            return !string.IsNullOrWhiteSpace(coreSubtypeId) &&
                   ConnectorBlacklistCoreSubtypeIds.Contains(coreSubtypeId);
        }

        public bool ShouldSerializeMinFactionRank()
        {
            return MinFactionRank != FactionRank.None;
        }

        internal void NormalizeAllowedUpgradeModules(string source, string coreFileOrKey)
        {
            AllowedUpgradeModuleCounts.Clear();
            AllowedUpgradeModuleDefinitionCounts.Clear();
            AllowedUpgradeModuleUniqueNameCounts.Clear();
            if (AllowedUpgradeModules == null)
            {
                AllowedUpgradeModules = Array.Empty<UpgradeModuleAllowance>();
                return;
            }

            foreach (var allowance in AllowedUpgradeModules)
            {
                if (allowance == null) continue;

                allowance.UniqueName = (allowance.UniqueName ?? string.Empty).Trim();
                allowance.SubtypeId = (allowance.SubtypeId ?? string.Empty).Trim();
                allowance.TypeId = string.IsNullOrWhiteSpace(allowance.TypeId)
                    ? string.Empty
                    : ModConfig.NormalizeBlockTypeId(allowance.TypeId);

                if (!string.IsNullOrWhiteSpace(allowance.SubtypeId))
                {
                    var typeId = string.IsNullOrWhiteSpace(allowance.TypeId)
                        ? ModConfig.DefaultUpgradeModuleTypeId
                        : allowance.TypeId;
                    var definitionId = ModConfig.FormatBlockDefinitionId(typeId, allowance.SubtypeId);
                    if (AllowedUpgradeModuleDefinitionCounts.ContainsKey(definitionId))
                        throw new Exception(
                            $"ShipCore '{UniqueName}' from {source} ({coreFileOrKey}) has duplicate AllowedUpgradeModules entry for '{definitionId}'.");

                    AllowedUpgradeModuleDefinitionCounts[definitionId] = allowance.MaxCount;
                    if (typeId.Equals(ModConfig.DefaultUpgradeModuleTypeId, StringComparison.OrdinalIgnoreCase))
                    {
                        if (AllowedUpgradeModuleCounts.ContainsKey(allowance.SubtypeId))
                            throw new Exception(
                                $"ShipCore '{UniqueName}' from {source} ({coreFileOrKey}) has duplicate AllowedUpgradeModules entry for '{allowance.SubtypeId}'.");

                        AllowedUpgradeModuleCounts[allowance.SubtypeId] = allowance.MaxCount;
                    }
                    continue;
                }

                if (string.IsNullOrWhiteSpace(allowance.UniqueName)) continue;

                if (AllowedUpgradeModuleUniqueNameCounts.ContainsKey(allowance.UniqueName))
                    throw new Exception(
                        $"ShipCore '{UniqueName}' from {source} ({coreFileOrKey}) has duplicate AllowedUpgradeModules entry for '{allowance.UniqueName}'.");

                AllowedUpgradeModuleUniqueNameCounts[allowance.UniqueName] = allowance.MaxCount;
            }
        }
    }

    [XmlRoot("AllowedUpgradeModules")]
    public class UpgradeModuleAllowance
    {
        [XmlElement("TypeId")]
        public string TypeId = string.Empty;

        [XmlElement("UniqueName")]
        public string UniqueName = string.Empty;

        [XmlElement("SubtypeId")]
        public string SubtypeId = string.Empty;

        [XmlElement("MaxCount")]
        public int MaxCount;
    }

    [XmlRoot("UpgradeModule")]
    public class UpgradeModuleConfig
    {
        [XmlElement("TypeId")]
        public string TypeId = "UpgradeModule";

        [XmlElement("SubtypeId")]
        public string SubtypeId = string.Empty;

        [XmlElement("UniqueName")]
        public string UniqueName = string.Empty;

        [XmlElement("Modifiers")]
        public UpgradeStatModifier[] Modifiers = Array.Empty<UpgradeStatModifier>();

        [XmlElement("BlockLimitModifiers")]
        public BlockLimitModifier[] BlockLimitModifiers = Array.Empty<BlockLimitModifier>();

        [XmlElement("CapacityModifiers")]
        public CapacityModifier[] CapacityModifiers = Array.Empty<CapacityModifier>();

        [XmlIgnore]
        internal string ConfigSource = string.Empty;

        [XmlIgnore]
        internal string ConfigFile = string.Empty;
    }

    [XmlRoot("Modifiers")]
    public class UpgradeStatModifier
    {
        [XmlElement("Stat")]
        public string Stat = string.Empty;

        [XmlElement("Value")]
        public float Value;

        [XmlElement("ModifierType")]
        public UpgradeModifierOperation ModifierType = UpgradeModifierOperation.Multiplicative;
    }

    [XmlRoot("BlockLimitModifiers")]
    public class BlockLimitModifier
    {
        [XmlElement("BlockLimitName")]
        public string BlockLimitName = string.Empty;

        [XmlElement("Value")]
        public float Value;

        [XmlElement("ModifierType")]
        public UpgradeModifierOperation ModifierType = UpgradeModifierOperation.Additive;
    }

    [XmlRoot("CapacityModifiers")]
    public class CapacityModifier
    {
        [XmlElement("Stat")]
        public string Stat = string.Empty;

        [XmlElement("Value")]
        public float Value;

        [XmlElement("ModifierType")]
        public UpgradeModifierOperation ModifierType = UpgradeModifierOperation.Additive;
    }

    [XmlRoot("UpgradeModifierOperation")]
    public enum UpgradeModifierOperation
    {
        Additive = 0,
        Multiplicative = 1
    }

    [XmlRoot("SpeedModifiers")]
    public class SpeedModifiers
    {
        [XmlElement("MaxSpeed")]
        public float MaxSpeed = 0.3f;

        [XmlElement("MaxAngularVelocity")]
        public float MaxAngularVelocity = 0f;

        [XmlElement("MaxBoost")]
        public float MaxBoost = 0.5f;

        [XmlElement("BoostDuration")]
        public float BoostDuration = 10f;

        [XmlElement("BoostCoolDown")]
        public float BoostCoolDown = 60f;

        [XmlElement("MinimumFrictionSpeedAbsolute")]
        public float MinimumFrictionSpeedAbsolute = 100f;

        [XmlElement("MaximumFrictionSpeedAbsolute")]
        public float MaximumFrictionSpeedAbsolute = 290f;

        [XmlElement("MinimumFrictionSpeedModifier")]
        public float MinimumFrictionSpeedModifier = 0.3f;

        [XmlElement("MaximumFrictionSpeedModifier")]
        public float MaximumFrictionSpeedModifier = 0.8f;

        [XmlElement("MaximumFrictionDeceleration")]
        public float MaximumFrictionDeceleration = 1f;

        [XmlElement("CruiseFrictionMultiplier")]
        public float CruiseFrictionMultiplier = 1f;

        [XmlElement("CruiseAccelerationThreshold")]
        public float CruiseAccelerationThreshold = 0.05f;

        [XmlElement("FrictionCurve")]
        public FrictionCurve FrictionCurve;

        [XmlElement("AtmosphericFriction")]
        public AtmosphericFrictionSettings AtmosphericFriction;

        public bool ShouldSerializeFrictionCurve()
        {
            return FrictionCurve != null && FrictionCurve.HasSegments();
        }

        public bool ShouldSerializeAtmosphericFriction()
        {
            return AtmosphericFriction != null && AtmosphericFriction.HasSettings();
        }
    }

    [XmlRoot("FrictionCurve")]
    public class FrictionCurve
    {
        [XmlElement("Segment")]
        public FrictionCurveSegment[] Segments = Array.Empty<FrictionCurveSegment>();

        public bool HasSegments()
        {
            if (Segments == null) return false;

            for (var i = 0; i < Segments.Length; i++)
            {
                if (Segments[i] != null) return true;
            }

            return false;
        }
    }

    [XmlRoot("Segment")]
    public class FrictionCurveSegment
    {
        [XmlElement("StartSpeed")]
        public float StartSpeed;

        [XmlElement("EndSpeed")]
        public float EndSpeed;

        [XmlElement("StartDeceleration")]
        public float StartDeceleration;

        [XmlElement("EndDeceleration")]
        public float EndDeceleration;
    }

    [XmlRoot("AtmosphericFriction")]
    public class AtmosphericFrictionSettings
    {
        [XmlElement("Enabled")]
        public bool Enabled = true;

        [XmlElement("FrictionCurve")]
        public FrictionCurve FrictionCurve;

        [XmlElement("CruiseFrictionMultiplier")]
        public float CruiseFrictionMultiplier = 1f;

        [XmlElement("CruiseAccelerationThreshold")]
        public float CruiseAccelerationThreshold = 0.05f;

        [XmlElement("AirDensityThreshold")]
        public float AirDensityThreshold = 0.05f;

        public bool HasSettings()
        {
            return !Enabled
                   || FrictionCurve != null && FrictionCurve.HasSegments()
                   || CruiseFrictionMultiplier != 1f
                   || CruiseAccelerationThreshold != 0.05f
                   || AirDensityThreshold != 0.05f;
        }
    }

    [XmlRoot("GridModifiers")]
    public class GridModifiers
    {
        [XmlElement("AssemblerSpeed")]
        public float AssemblerSpeed = 1;

        [XmlElement("DrillHarvestMultiplier")]
        public float DrillHarvestMultiplier = 1;

        [XmlElement("GyroEfficiency")]
        public float GyroEfficiency = 1;

        [XmlElement("GyroForce")]
        public float GyroForce = 1;

        [XmlElement("PowerProducersOutput")]
        public float PowerProducersOutput = 1;

        [XmlElement("RefineEfficiency")]
        public float RefineEfficiency = 1;

        [XmlElement("RefineSpeed")]
        public float RefineSpeed = 1;

        [XmlElement("ThrusterEfficiency")]
        public float ThrusterEfficiency = 1;

        [XmlElement("ThrusterForce")]
        public float ThrusterForce = 1;

        public override string ToString()
        {
            return
                $"<GridModifiers ThrusterForce={ThrusterForce} " +
                $"ThrusterEfficiency={ThrusterEfficiency} " +
                $"GyroForce={GyroForce} " +
                $"GyroEfficiency={GyroEfficiency} " +
                $"RefineEfficiency={RefineEfficiency} " +
                $"RefineSpeed={RefineSpeed} " +
                $"AssemblerSpeed={AssemblerSpeed} " +
                $"PowerProducersOutput={PowerProducersOutput} " +
                $"DrillHarvestMultiplier={DrillHarvestMultiplier} />";
        }

        public List<ModifierNameValue> GetModifierValues()
        {
            return new List<ModifierNameValue>
            {
                new ModifierNameValue("Thruster force", ThrusterForce),
                new ModifierNameValue("Thruster efficiency", ThrusterEfficiency),
                new ModifierNameValue("Gyro force", GyroForce),
                new ModifierNameValue("Gyro efficiency", GyroEfficiency),
                new ModifierNameValue("Refinery yield", RefineEfficiency),
                new ModifierNameValue("Refinery speed", RefineSpeed),
                new ModifierNameValue("Assembler speed", AssemblerSpeed),
                new ModifierNameValue("Power output", PowerProducersOutput),
                new ModifierNameValue("Drill harvest", DrillHarvestMultiplier)
            };
        }
    }

    public struct ModifierNameValue
    {
        public readonly string Name;
        public readonly float Value;

        public ModifierNameValue(string name, float value)
        {
            Name = name;
            Value = value;
        }
    }

    [XmlRoot("BlockLimit")]
    public class BlockLimit
    {
        [XmlElement("Name")]
        public string Name = string.Empty;

        [XmlIgnore]
        public string[] BlockGroupsShortHand = Array.Empty<string>();

        [XmlElement("BlockGroups")]
        public BlockGroupReference[] BlockGroupReferences = Array.Empty<BlockGroupReference>();

        [XmlIgnore]
        public List<BlockGroup> BlockGroups = new List<BlockGroup>();

        [XmlElement("ExcludedBlockGroups")]
        public string[] ExcludedBlockGroupsShortHand = Array.Empty<string>();

        [XmlIgnore]
        public List<BlockGroup> ExcludedBlockGroups = new List<BlockGroup>();

        [XmlElement("MaxCount")]
        public float MaxCount;

        [XmlElement("MaxCountPerDirection")]
        public float MaxCountPerDirection = -1f;

        [XmlArray("DirectionBudgets")]
        [XmlArrayItem("DirectionBudget")]
        public DirectionBudget[] DirectionBudgets = Array.Empty<DirectionBudget>();

        [XmlIgnore]
        public bool HasDirectionalBudget => MaxCountPerDirection >= 0f ||
                                            DirectionBudgets != null && DirectionBudgets.Length > 0;

        internal float GetMaxCountForDirection(DirectionType direction)
        {
            if (DirectionBudgets != null)
                foreach (var budget in DirectionBudgets)
                    if (budget != null && budget.Direction == direction)
                        return budget.MaxCount;
            return MaxCountPerDirection;
        }

        public bool ShouldSerializeDirectionBudgets()
        {
            return DirectionBudgets != null && DirectionBudgets.Length > 0;
        }

        [XmlElement("LimitVisibility")]
        public LimitVisibility LimitVisibility = ShipCoreFramework.LimitVisibility.Always;

        [XmlElement("CrossConnectorPunishment")]
        public bool CrossConnectorPunishment;

        [XmlElement("PunishByNoFlyZone")]
        public bool PunishByNoFlyZone;

        [XmlElement("IsCriticalLimit")]
        public bool IsCriticalLimit;

        [XmlElement("IgnoredByNpc")]
        public bool IgnoredByNpc;

        [XmlElement("PunishmentType")]
        public PunishmentType PunishmentType = PunishmentType.ShutOff;

        [XmlElement("AllowedDirections")]
        public List<DirectionType> AllowedDirections;

        public bool ShouldSerializeMaxCountPerDirection()
        {
            return MaxCountPerDirection >= 0f;
        }

        public bool ShouldSerializeLimitVisibility()
        {
            return LimitVisibility != ShipCoreFramework.LimitVisibility.Always;
        }

        internal double GetWeight(BlockKey key)
        {
            var blockType = GetMatchingBlockType(key);
            return blockType?.CountWeight ?? 0d;
        }

        internal BlockType GetMatchingBlockType(BlockKey key)
        {
            if (FindMatchingBlockType(ExcludedBlockGroups, key) != null)
                return null;

            return FindMatchingBlockType(BlockGroups, key);
        }

        internal List<DirectionType> GetAllowedDirections(BlockKey key)
        {
            BlockGroup matchedGroup;
            FindMatchingBlockType(BlockGroups, key, out matchedGroup);
            if (matchedGroup == null || BlockGroupReferences == null)
                return AllowedDirections;

            foreach (BlockGroupReference reference in BlockGroupReferences)
            {
                if (reference == null || !reference.HasDirectionsOverride ||
                    !string.Equals(reference.Name, matchedGroup.Name, StringComparison.OrdinalIgnoreCase))
                    continue;

                return reference.AllowedDirections;
            }

            return AllowedDirections;
        }

        private static BlockType FindMatchingBlockType(List<BlockGroup> groups, BlockKey key)
        {
            BlockGroup ignored;
            return FindMatchingBlockType(groups, key, out ignored);
        }

        private static BlockType FindMatchingBlockType(List<BlockGroup> groups, BlockKey key,
            out BlockGroup matchedGroup)
        {
            matchedGroup = null;
            if (groups == null) return null;

            foreach (BlockGroup group in groups)
            {
                if (group?.BlockTypes == null) continue;

                foreach (BlockType blockType in group.BlockTypes)
                {
                    if (blockType == null) continue;
                    if (blockType.Matches(key))
                    {
                        matchedGroup = group;
                        return blockType;
                    }
                }
            }

            return null;
        }
    }

    public class DirectionBudget
    {
        [XmlAttribute("Direction")]
        public DirectionType Direction = DirectionType.Any;

        [XmlAttribute("MaxCount")]
        public float MaxCount = -1f;
    }

    public class BlockGroupReference
    {
        [XmlText]
        public string Name = string.Empty;

        [XmlAttribute("Directions")]
        public string Directions;

        [XmlIgnore]
        public List<DirectionType> AllowedDirections = new List<DirectionType>();

        [XmlIgnore]
        public bool HasDirectionsOverride => Directions != null;
    }

    [XmlRoot("BlockGroup")]
    public class BlockGroup
    {
        [XmlElement("Name")]
        public string Name = string.Empty;

        [XmlElement("BlockTypes")]
        public List<BlockType> BlockTypes = new List<BlockType>();

        [XmlIgnore]
        internal string ConfigSource = string.Empty;

        [XmlIgnore]
        internal string ConfigFile = string.Empty;
    }

    [XmlRoot("BlockType")]
    public class BlockType
    {
        [XmlElement("TypeId")]
        public string TypeId;

        [XmlElement("SubtypeId")]
        public string SubtypeId;

        [XmlElement("CountWeight")]
        public float CountWeight;

        [XmlElement("PrimaryDirection")]
        public DirectionType PrimaryDirection;

        public BlockType()
        {
            TypeId = string.Empty;
            SubtypeId = string.Empty;
            CountWeight = 1;
            PrimaryDirection = DirectionType.Forward;
        }

        public BlockType(string typeId, string subtypeId = "", float countWeight = 1,
            DirectionType primaryDirection = DirectionType.Forward)
        {
            TypeId = typeId;
            SubtypeId = subtypeId;
            CountWeight = countWeight;
            PrimaryDirection = primaryDirection;
        }

        public bool ShouldSerializePrimaryDirection()
        {
            return PrimaryDirection != DirectionType.Forward;
        }

        internal bool Matches(BlockKey key)
        {
            return Matches(key.TypeId, key.SubtypeId);
        }

        internal bool Matches(string typeId, string subtypeId)
        {
            var configuredTypeId = (TypeId ?? string.Empty).Trim();
            if (!string.Equals(configuredTypeId, (typeId ?? string.Empty).Trim(), StringComparison.Ordinal))
                return false;

            var configuredSubtypeId = (SubtypeId ?? string.Empty).Trim();
            if (string.Equals(configuredSubtypeId, "any", StringComparison.OrdinalIgnoreCase))
                return true;

            return string.Equals(configuredSubtypeId, (subtypeId ?? string.Empty).Trim(), StringComparison.Ordinal);
        }
    }

    [XmlRoot("GridDefenseModifiers")]
    public class GridDefenseModifiers
    {
        [XmlElement("Bullet")]
        public float Bullet = 1f;

        [XmlElement("PostShield")]
        public float PostShield = 1f;

        [XmlElement("Duration")]
        public float Duration;

        [XmlElement("Cooldown")]
        public float Cooldown;

        [XmlElement("Rocket")]
        public float Rocket = 1f;

        [XmlElement("Explosion")]
        public float Explosion = 1f;

        [XmlElement("Environment")]
        public float Environment = 1f;

        [XmlElement("Energy")]
        public float Energy = 1f;

        [XmlElement("Kinetic")]
        public float Kinetic = 1f;
    }

    [XmlRoot("MobilityType")]
    public enum MobilityType
    {
        Static = 0,
        Mobile = 1,
        Both = 2
    }

    [XmlRoot("SpeedLimitType")]
    public enum SpeedLimitType
    {
        Normal = 0,
        Friction = 1
    }

    [XmlRoot("SpeedOverrideMode")]
    public enum SpeedOverrideMode
    {
        None = 0,
        OnlyIfHeavier = 1,
        Priority = 2,
        Any = 3
    }

    [XmlRoot("FrictionSpeedValueMode")]
    public enum FrictionSpeedValueMode
    {
        Modifier = 0,
        Absolute = 1
    }

    [XmlRoot("PunishmentType")]
    public enum PunishmentType
    {
        ShutOff,
        Damage,
        Delete,
        Explode,
        DeleteWithoutRefund
    }

    [XmlRoot("DirectionType")]
    public enum DirectionType
    {
        Forward = 0,
        Backward = 1,
        Up = 2,
        Down = 3,
        Left = 4,
        Right = 5,
        Any = 6
    }

    [XmlRoot("LimitVisibility")]
    public enum LimitVisibility
    {
        Always = 0,
        NearLimit = 1,
        Hidden = 2
    }

    [XmlRoot("FactionRank")]
    public enum FactionRank
    {
        None = 0,
        Member = 1,
        Leader = 2,
        Founder = 3
    }
}
