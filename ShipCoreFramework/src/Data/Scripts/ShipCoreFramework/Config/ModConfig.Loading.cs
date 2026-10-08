using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Sandbox.ModAPI;
using VRage.Game;

namespace ShipCoreFramework
{
    public partial class ModConfig
    {
        private const string RetiredDefaultNoCoreUniqueName = "DEFAULT-NO-CORE-ALL-GRID-TYPES";

        internal void LoadConfig()
        {
            LoadConfig(Session.IsServer);
        }

        internal void LoadConfig(bool allowWorldStorageReadWrite)
        {
            var hasIgnoreAiSetting = false;
            var hasIgnoredFactionTagsSetting = false;
            var hasSelectedNoCoreSetting = false;

            if (allowWorldStorageReadWrite)
                LoadWorldSettings(out hasIgnoreAiSetting, out hasIgnoredFactionTagsSetting,
                    out hasSelectedNoCoreSetting);

            foreach (var mod in MyAPIGateway.Session.Mods)
            {
                LoadBlockGroupsFromMod(mod);
                LoadNoCoreConfigFromMod(mod);
                LoadManifestContentFromMod(mod);
            }
            ThrowErrorIfDuplicates(NoCoreConfigs, core => core.UniqueName, "NoCoreConfig UniqueName",
                core => FormatConfigOrigin(core.ConfigSource, core.ConfigFile));
            ThrowErrorIfDuplicates(ShipCores, core => core.UniqueName, "ShipCore UniqueName",
                core => FormatConfigOrigin(core.ConfigSource, core.ConfigFile));
            ThrowErrorIfDuplicates(ManifestCoreGroups, group => group.Name, "ManifestCoreGroup Name",
                group => FormatConfigOrigin(group.ConfigSource, group.ConfigFile));
            ThrowErrorIfDuplicates(UpgradeModules, module => FormatBlockDefinitionId(module.TypeId, module.SubtypeId),
                "UpgradeModule TypeId/SubtypeId",
                module => FormatConfigOrigin(module.ConfigSource, module.ConfigFile));
            RebuildTrackedUpgradeModuleBlockIds();
            NormalizeBlockGroups(BlockGroups, "All Loaded Mods");
            ThrowErrorIfDuplicates(BlockGroups, groups => groups.Name, "BlockGroup Name",
                group => FormatConfigOrigin(group.ConfigSource, group.ConfigFile));
            Utils.Log($"NoCoreConfigs.Count = {NoCoreConfigs.Count}", 1, "Ship Core Config");
            Utils.Log($"BlockGroups.Count = {BlockGroups.Count}", 1, "Ship Core Config");
            Utils.Log($"ManifestCoreGroups.Count = {ManifestCoreGroups.Count}", 1, "Ship Core Config");
            Utils.Log($"UpgradeModules.Count = {UpgradeModules.Count}", 1, "Ship Core Config");

            NormalizeNoCoreConfigs();
            ResolveBlockGroupsForCores(NoCoreConfigs);
            ResolveBlockGroupsForCores(ShipCores);

            if (allowWorldStorageReadWrite)
                ImportLegacyWorldSettingsIfNeeded(hasIgnoreAiSetting, hasIgnoredFactionTagsSetting,
                    hasSelectedNoCoreSetting);
            NormalizeIgnoredFactionTags(hasIgnoredFactionTagsSetting);
            EnsurePersistedWorldSettings();
            ResolveSelectedNoCore(allowWorldStorageReadWrite);
        }

        internal void EnsurePersistedWorldSettings()
        {
            if (IgnoredFactionTags == null)
                IgnoredFactionTags = new List<string>();

            if (SelectedNoCoreUniqueName == null)
                SelectedNoCoreUniqueName = string.Empty;
        }

        internal bool ResolveSelectedNoCore(bool logFailure = true)
        {
            SelectedNoCore = null;

            if (!string.IsNullOrWhiteSpace(SelectedNoCoreUniqueName))
            {
                SelectedNoCore = NoCoreConfigs.FirstOrDefault(core =>
                    !string.IsNullOrWhiteSpace(core?.UniqueName) &&
                    core.UniqueName.Equals(SelectedNoCoreUniqueName, StringComparison.OrdinalIgnoreCase));
            }

            if (Session.IsServer && SelectedNoCore == null &&
                (string.IsNullOrWhiteSpace(SelectedNoCoreUniqueName) ||
                 string.Equals(SelectedNoCoreUniqueName, RetiredDefaultNoCoreUniqueName,
                     StringComparison.OrdinalIgnoreCase)) &&
                NoCoreConfigs.Count == 1 &&
                !string.IsNullOrWhiteSpace(NoCoreConfigs[0]?.UniqueName))
            {
                SelectedNoCore = NoCoreConfigs[0];
                Utils.Log($"Automatically selected sole no-core profile '{SelectedNoCore.UniqueName}'.", 1,
                    "Config Validation");
            }

            if (SelectedNoCore == null)
            {
                if (logFailure)
                    Utils.Log(GetNoCoreConfigurationError(), 0, "Config Validation");
                return false;
            }

            SelectedNoCoreUniqueName = SelectedNoCore.UniqueName ?? string.Empty;
            NormalizeAndResolveSelectedNoCore();
            return true;
        }

        internal string GetNoCoreConfigurationError()
        {
            if (SelectedNoCore != null) return string.Empty;
            if (NoCoreConfigs.Count == 0)
                return "No content-pack no-core profiles were loaded. Ship Core Framework cannot start.";
            if (string.IsNullOrWhiteSpace(SelectedNoCoreUniqueName))
                return "No content-pack no-core profile is selected. Use /core listnocores and /core select <name>.";
            if (string.Equals(SelectedNoCoreUniqueName, RetiredDefaultNoCoreUniqueName,
                    StringComparison.OrdinalIgnoreCase))
                return "The retired built-in no-core profile is still selected. Use /core listnocores and /core select <name>.";
            return $"Selected no-core profile '{SelectedNoCoreUniqueName}' was not loaded. Restore its content pack and use /core reloadconfig, or select another profile.";
        }

        private void NormalizeNoCoreConfigs()
        {
            foreach (var core in NoCoreConfigs)
            {
                if (core == null) continue;
                NormalizeShipCoreBlockLimits(core, GetCoreConfigSource(core, "NoCoreConfig"),
                    GetCoreConfigFile(core, core.UniqueName));
            }
        }

        private void NormalizeAndResolveSelectedNoCore()
        {
            if (SelectedNoCore == null) return;

            NormalizeShipCoreBlockLimits(SelectedNoCore, GetCoreConfigSource(SelectedNoCore, "SelectedNoCore"),
                GetCoreConfigFile(SelectedNoCore, SelectedNoCoreUniqueName));
            ResolveBlockGroups(SelectedNoCore);
        }

        private static string GetCoreConfigSource(ShipCore core, string fallback)
        {
            return core != null && !string.IsNullOrWhiteSpace(core.ConfigSource)
                ? core.ConfigSource
                : fallback;
        }

        private static string GetCoreConfigFile(ShipCore core, string fallback)
        {
            return core != null && !string.IsNullOrWhiteSpace(core.ConfigFile)
                ? core.ConfigFile
                : fallback;
        }

        private void NormalizeIgnoredFactionTags(bool hasIgnoredFactionTagsSetting)
        {
            if (IgnoredFactionTags == null)
                IgnoredFactionTags = new List<string>();

            IgnoredFactionTags = IgnoredFactionTags
                .Where(tag => !string.IsNullOrWhiteSpace(tag))
                .Select(tag => tag.Trim())
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .ToList();

            if (!hasIgnoredFactionTagsSetting && IgnoredFactionTags.Count == 0)
                IgnoredFactionTags = new List<string>(DefaultIgnoredFactionTagValues);
        }

        private void LoadBlockGroupsFromMod(MyObjectBuilder_Checkpoint.ModItem mod)
        {
            string text;
            if (!TryReadModTextFile(mod, BlockGroupsFileName, out text)) return;

            var newBlockGroups = MyAPIGateway.Utilities.SerializeFromXML<List<BlockGroup>>(text);

            if (newBlockGroups == null)
                throw new Exception($"Failed to load block groups from Mod: {mod.FriendlyName}");
            NormalizeBlockGroups(newBlockGroups, mod.FriendlyName);
            foreach (var group in newBlockGroups.Where(group => group != null))
            {
                group.ConfigSource = mod.FriendlyName;
                group.ConfigFile = BlockGroupsFileName;
            }

            BlockGroups.AddRange(newBlockGroups);
            Utils.Log($"Loaded Groups From: {mod.FriendlyName}", 1, "Ship Core Config");
        }

        private void LoadNoCoreConfigFromMod(MyObjectBuilder_Checkpoint.ModItem mod)
        {
            string text;
            if (!TryReadModTextFile(mod, DefaultNoCoreFileName, out text)) return;

            var newNoCore = MyAPIGateway.Utilities.SerializeFromXML<ShipCore>(text);

            if (newNoCore == null)
                throw new Exception($"Failed to load no-core from Mod: {mod.FriendlyName}");
            newNoCore.ConfigSource = mod.FriendlyName;
            newNoCore.ConfigFile = DefaultNoCoreFileName;
            NoCoreConfigs.Add(newNoCore);
            Utils.Log($"Loaded No-Core Config From: {mod.FriendlyName}", 1, "Ship Core Config");
        }

        private void LoadManifestContentFromMod(MyObjectBuilder_Checkpoint.ModItem mod)
        {
            string text;
            if (!TryReadModTextFile(mod, CoreManifestFileName, out text)) return;

            Utils.Log($"Found Manifest in: {mod.FriendlyName}", 1, "Ship Core Config");
            var coreManifest = MyAPIGateway.Utilities.SerializeFromXML<CoreManifest>(text);
            if (coreManifest == null)
                throw new Exception($"Failed to Load Classes from Mod: {mod.FriendlyName}");
            NormalizeCoreManifest(coreManifest, mod.FriendlyName);
            RegisterManifestGroups(coreManifest.ManifestGroups, mod.FriendlyName, CoreManifestFileName);

            foreach (var shipCoreEntry in coreManifest.ShipCores)
            {
                if (shipCoreEntry == null || string.IsNullOrWhiteSpace(shipCoreEntry.Filename)) continue;
                LoadShipCoreFromManifest(mod, shipCoreEntry.Filename, shipCoreEntry.Groups,
                        shipCoreEntry.BlacklistedCoreSubtypeIds, coreManifest.CrossConnectorPunishmentWhitelist,
                        shipCoreEntry.CoreSelectionPriority);
            }

            foreach (var upgradeModuleEntry in coreManifest.UpgradeModules)
            {
                if (upgradeModuleEntry == null || string.IsNullOrWhiteSpace(upgradeModuleEntry.Filename)) continue;

                string modText;
                if (!TryReadModTextFile(mod, upgradeModuleEntry.Filename, out modText))
                {
                    Utils.Log($"Upgrade module file '{upgradeModuleEntry.Filename}' was listed in {CoreManifestFileName} but could not be read from Mod: {mod.FriendlyName}", 2, "Ship Core Config");
                    continue;
                }

                var newUpgradeModule = MyAPIGateway.Utilities.SerializeFromXML<UpgradeModuleConfig>(modText);

                if (newUpgradeModule == null)
                    throw new Exception($"Failed to load upgrade module from file {upgradeModuleEntry.Filename} in Mod: {mod.FriendlyName}");
                NormalizeUpgradeModule(newUpgradeModule, mod.FriendlyName, upgradeModuleEntry.Filename);
                newUpgradeModule.ConfigSource = mod.FriendlyName;
                newUpgradeModule.ConfigFile = upgradeModuleEntry.Filename;
                UpgradeModules.Add(newUpgradeModule);
                Utils.Log($"Loaded Upgrade Module {newUpgradeModule.UniqueName} From: {mod.FriendlyName}", 1, "Ship Core Config");
            }
        }

        private void RegisterManifestGroups(IEnumerable<ManifestCoreGroup> groups, string source, string sourceFile)
        {
            foreach (var group in groups)
            {
                if (group == null) continue;

                var duplicate = GetManifestGroupByName(group.Name);
                if (duplicate != null)
                    throw new Exception(
                        $"Duplicate manifest group '{group.Name}' found while loading {FormatConfigOrigin(source, sourceFile)}; already loaded from {FormatConfigOrigin(duplicate.ConfigSource, duplicate.ConfigFile)}.");

                group.ConfigSource = source;
                group.ConfigFile = sourceFile;
                ManifestCoreGroups.Add(group);
            }
        }

        private void LoadShipCoreFromManifest(MyObjectBuilder_Checkpoint.ModItem mod, string shipCoreFilename,
            IEnumerable<string> manifestGroupNames, IEnumerable<string> blacklistedCoreSubtypeIds,
            IEnumerable<string> crossConnectorPunishmentWhitelist, int coreSelectionPriority)
        {
            string modText;
            if (!TryReadModTextFile(mod, shipCoreFilename, out modText))
            {
                Utils.Log($"Ship core file '{shipCoreFilename}' was listed in {CoreManifestFileName} but could not be read from Mod: {mod.FriendlyName}", 2, "Ship Core Config");
                return;
            }

            var newShipCore = MyAPIGateway.Utilities.SerializeFromXML<ShipCore>(modText);

            if (newShipCore == null)
                throw new Exception($"Failed to load ship core from file {shipCoreFilename} in Mod: {mod.FriendlyName}");
            NormalizeShipCoreBlockLimits(newShipCore, mod.FriendlyName, shipCoreFilename);
            AssignManifestGroupsToCore(newShipCore, manifestGroupNames, mod.FriendlyName, shipCoreFilename);
            AssignManifestConnectorBlacklistToCore(newShipCore, blacklistedCoreSubtypeIds);
            AssignCrossConnectorPunishmentWhitelistToCore(newShipCore, crossConnectorPunishmentWhitelist);
            newShipCore.CoreSelectionPriority = coreSelectionPriority;
            newShipCore.ConfigSource = mod.FriendlyName;
            newShipCore.ConfigFile = shipCoreFilename;
            ShipCores.Add(newShipCore);
            Utils.Log($"Loaded Core {newShipCore.UniqueName} From: {mod.FriendlyName}", 1, "Ship Core Config");
        }

        private static bool TryReadModTextFile(MyObjectBuilder_Checkpoint.ModItem mod, string fileName, out string text)
        {
            text = null;
            if (string.IsNullOrWhiteSpace(fileName) || MyAPIGateway.Utilities == null)
                return false;

            var candidates = BuildModPathCandidates(fileName);
            for (var i = 0; i < candidates.Count; i++)
            {
                var reader = TryOpenModTextFile(mod, candidates[i]);
                if (reader == null) continue;

                using (reader)
                    text = reader.ReadToEnd();

                return true;
            }

            return false;
        }

        private static TextReader TryOpenModTextFile(MyObjectBuilder_Checkpoint.ModItem mod, string fileName)
        {
            try
            {
                var reader = MyAPIGateway.Utilities.ReadFileInModLocation(fileName, mod);
                if (reader != null) return reader;
            }
            catch
            {
            }

            try
            {
                if (MyAPIGateway.Utilities.FileExistsInModLocation(fileName, mod))
                    return MyAPIGateway.Utilities.ReadFileInModLocation(fileName, mod);
            }
            catch
            {
            }

            return null;
        }

        private static List<string> BuildModPathCandidates(string fileName)
        {
            var candidates = new List<string>();
            var forward = fileName.Replace('\\', '/');
            AddModPathCandidate(candidates, fileName);
            AddModPathCandidate(candidates, forward);
            AddModPathCandidate(candidates, fileName.Replace('/', '\\'));

            while (forward.StartsWith("/", StringComparison.Ordinal))
                forward = forward.Substring(1);

            if (forward.StartsWith("data/", StringComparison.OrdinalIgnoreCase) && forward.Length > 5)
            {
                AddModPathCandidate(candidates, "Data/" + forward.Substring(5));
                AddModPathCandidate(candidates, "data/" + forward.Substring(5));
            }

            return candidates;
        }

        private static void AddModPathCandidate(List<string> candidates, string fileName)
        {
            if (candidates == null || string.IsNullOrWhiteSpace(fileName)) return;

            var normalized = fileName.Trim();
            while (normalized.StartsWith("/", StringComparison.Ordinal) ||
                   normalized.StartsWith("\\", StringComparison.Ordinal))
                normalized = normalized.Substring(1);

            for (var i = 0; i < candidates.Count; i++)
                if (string.Equals(candidates[i], normalized, StringComparison.Ordinal))
                    return;

            candidates.Add(normalized);
        }

        private void AssignManifestGroupsToCore(ShipCore core, IEnumerable<string> manifestGroupNames, string source, string coreFile)
        {
            if (core == null)
                return;

            core.ManifestGroupNames.Clear();
            if (manifestGroupNames == null)
                return;

            foreach (var manifestGroupName in manifestGroupNames
                         .Where(manifestGroupName => !string.IsNullOrWhiteSpace(manifestGroupName))
                         .Distinct(StringComparer.OrdinalIgnoreCase))
            {
                var group = GetManifestGroupByName(manifestGroupName);
                if (group == null)
                    throw new Exception($"ShipCore '{core.UniqueName}' from {source} ({coreFile}) references unknown manifest group '{manifestGroupName}'.");

                core.ManifestGroupNames.Add(group.Name);
                if (!string.IsNullOrWhiteSpace(core.SubtypeId))
                    group.CoreSubtypeIds.Add(core.SubtypeId);
            }
        }

        private static void AssignManifestConnectorBlacklistToCore(ShipCore core,
            IEnumerable<string> blacklistedCoreSubtypeIds)
        {
            if (core == null)
                return;

            core.ConnectorBlacklistCoreSubtypeIds.Clear();
            if (blacklistedCoreSubtypeIds == null)
                return;

            foreach (var coreSubtypeId in blacklistedCoreSubtypeIds
                         .Where(coreSubtypeId => !string.IsNullOrWhiteSpace(coreSubtypeId))
                         .Select(coreSubtypeId => coreSubtypeId.Trim()))
                core.ConnectorBlacklistCoreSubtypeIds.Add(coreSubtypeId);
        }

        private static void AssignCrossConnectorPunishmentWhitelistToCore(ShipCore core,
            IEnumerable<string> crossConnectorPunishmentWhitelist)
        {
            if (core == null)
                return;

            core.CrossConnectorPunishmentWhitelisted = false;
            if (crossConnectorPunishmentWhitelist == null || string.IsNullOrWhiteSpace(core.SubtypeId))
                return;

            core.CrossConnectorPunishmentWhitelisted = crossConnectorPunishmentWhitelist
                .Any(coreSubtypeId => string.Equals(coreSubtypeId, core.SubtypeId, StringComparison.OrdinalIgnoreCase));
        }

        private void ResolveBlockGroupsForCores(IEnumerable<ShipCore> cores)
        {
            foreach (var core in cores)
                ResolveBlockGroups(core);
        }

        private void ResolveBlockGroups(ShipCore core)
        {
            if (core?.BlockLimits == null) return;

            foreach (var limit in core.BlockLimits)
            {
                if (limit == null) continue;
                if (limit.BlockGroupsShortHand == null)
                {
                    limit.BlockGroupsShortHand = Array.Empty<string>();
                    Utils.Log("Config warning: A <BlockLimit> had null <BlockGroups>; treating as empty.", 2, "Config Validation");
                }

                if (limit.ExcludedBlockGroupsShortHand == null)
                    limit.ExcludedBlockGroupsShortHand = Array.Empty<string>();

                var resolvedBlockGroups = ResolveBlockGroupReferences(core, limit, limit.BlockGroupsShortHand,
                    "BlockGroups");
                var resolvedExcludedBlockGroups = ResolveBlockGroupReferences(core, limit,
                    limit.ExcludedBlockGroupsShortHand, "ExcludedBlockGroups");
                limit.BlockGroups = resolvedBlockGroups;
                limit.ExcludedBlockGroups = resolvedExcludedBlockGroups;
            }
        }

        private List<BlockGroup> ResolveBlockGroupReferences(ShipCore core, BlockLimit limit,
            IEnumerable<string> names, string elementName)
        {
            var resolvedGroups = new List<BlockGroup>();
            foreach (string shorthand in names)
            {
                string groupName = shorthand == null ? string.Empty : shorthand.Trim();
                bool found = false;
                foreach (BlockGroup group in BlockGroups)
                {
                    if (group?.Name == null ||
                        !group.Name.Equals(groupName, StringComparison.OrdinalIgnoreCase))
                        continue;

                    resolvedGroups.Add(group);
                    found = true;
                }

                if (!found && !string.IsNullOrWhiteSpace(groupName))
                    Utils.Log($"Config warning: ShipCore '{core.UniqueName}' references unknown BlockGroup '{groupName}' in <{elementName}> for limit '{limit.Name}'.", 2, "Config Validation");
            }

            return resolvedGroups;
        }
    }
}
