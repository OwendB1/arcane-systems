import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

const components = new URL(
  "../ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/Server/Components/",
  import.meta.url,
);
const abilities = await readFile(new URL("GroupComponent.Abilities.cs", components), "utf8");
const cache = await readFile(new URL("GroupComponent.CachedState.cs", components), "utf8");
const section = (source, start, end) => {
  const first = source.indexOf(start);
  const last = source.indexOf(end, first);
  assert.ok(first >= 0 && last > first, `Missing production section: ${start}`);
  return source.slice(first, last);
};

// Run the actual refresh coordinator, punishment transitions, and cache guard.
// Counters stand in for expensive cache rebuilds and writes across every grid block.
const source = `
using System;
using System.Collections.Generic;
namespace Sandbox.ModAPI {
    static class MyAPIGateway { internal static readonly Utilities Utilities = new Utilities(); }
    class Utilities {
        internal readonly Queue<Action> Pending = new Queue<Action>();
        internal void InvokeOnGameThread(Action action) { Pending.Enqueue(action); }
    }
}
namespace ShipCoreFramework {
    using Sandbox.ModAPI;
    class CoreComponent { }
    static class Session {
        internal static bool IsServer = true, IsGameThread = true, IsShuttingDown;
        internal static void MarkRuntimeStateDirty(GroupComponent group) { }
    }
    static class Utils { internal static void Log(string message, int level) { } }
    class GroupComponent {
        private bool _closing, IsInitializingGrids;
        internal bool Deactivated, Ignored, Grace;
        internal bool PunishSpeed, PunishModifiers, PunishLimitedBlocks;
        internal CoreComponent MainCoreComponent;
        private bool _modifierStateCacheDirty = true;
        internal int Rebuilds, Applications, Clears, DefenseRefreshes;
        internal bool DesiredPunishment;
        private object Modifiers { get { return null; } }
        private bool IsIgnoredByAiOrFactionTagThreadSafe() { return Ignored; }
        private bool EnsureWorkingMainCore() { return false; }
        private bool IsCoreRecoveryGraceActive() { return Grace; }
        private void ClearCoreRecoveryGracePunishmentState() { }
        private void ClearDeactivatedLimitState() {
            Clears++;
            PunishModifiers = PunishSpeed = PunishLimitedBlocks = false;
        }
        private void RefreshLimitedBlockPunishmentState() { }
        private void RefreshDefenseModifierCache() { DefenseRefreshes++; }
        private void RefreshModifierStateCache() { Rebuilds++; _modifierStateCacheDirty = false; }
        private void ApplyModifiers(object modifiers) { Applications++; }
        private GroupPunishmentFlags EvaluatePunishmentGates() {
            return DesiredPunishment ? GroupPunishmentFlags.Both : GroupPunishmentFlags.None;
        }
        private void InvalidateSpeedStateCache() { }
        private void BeginSpeedRampDown() { }
        private List<string> GetSpeedPunishmentGateDescriptions() { return new List<string>(); }
        private List<string> GetModifierPunishmentGateDescriptions() { return new List<string>(); }
        private string GetGroupKey() { return "test"; }
        internal void UpgradeChanged() { InvalidateModifierStateCache(); }
        ${section(abilities, "[Flags]", "private GroupPunishmentFlags EvaluatePunishmentGates()")}
        ${section(abilities, "private void ApplyPunishmentFlags(", "private GridDefenseModifiers GetCurrentDefenseModifiers()")}
        ${section(cache, "private void InvalidateModifierStateCache()", "internal void RefreshGameThreadStateCache()")}
        ${section(cache, "private void RefreshModifierStateCacheIfNeeded()", "private void RefreshIgnoredStateCacheIfNeeded(")}
    }
    static class Checks {
        private static void Check(bool condition, string message) {
            if (!condition) throw new Exception(message);
        }
        private static void Main() {
            var group = new GroupComponent();
            group.RefreshPunishmentState();
            for (var i = 0; i < 120; i++) group.RefreshPunishmentState();
            Check(group.Rebuilds == 1 && group.Applications == 0,
                "Unchanged periodic checks must reuse modifiers without rewriting blocks.");
            group.DesiredPunishment = true;
            group.RefreshPunishmentState();
            Check(group.PunishModifiers && group.PunishSpeed && group.Rebuilds == 2 && group.Applications == 1,
                "Entering punishment must rebuild and apply modifiers immediately.");
            group.DesiredPunishment = false;
            group.RefreshPunishmentState();
            Check(!group.PunishModifiers && group.Rebuilds == 3 && group.Applications == 2,
                "Leaving punishment must restore current modifiers immediately.");
            group.UpgradeChanged();
            group.RefreshPunishmentState();
            Check(group.Rebuilds == 4, "Upgrade invalidation must still refresh the cache.");

            group = new GroupComponent { Deactivated = true };
            for (var i = 0; i < 120; i++) group.RefreshPunishmentState();
            Check(group.Rebuilds == 0 && group.Applications == 0 && group.Clears == 0 && group.DefenseRefreshes == 0,
                "Deactivated groups must not repeat deactivation cleanup or block writes.");
            group = new GroupComponent { Ignored = true };
            group.RefreshPunishmentState();
            Check(group.Clears == 1 && group.Rebuilds == 1 && group.Applications == 1,
                "A newly ignored group still needs cleanup before deactivation runs.");
            group = new GroupComponent { Grace = true };
            group.RefreshPunishmentState();
            Check(group.Rebuilds == 0 && group.Applications == 0,
                "Core recovery grace must still suppress modifier application.");

            group = new GroupComponent();
            Session.IsGameThread = false;
            group.RefreshPunishmentState();
            Check(group.Rebuilds == 0 && MyAPIGateway.Utilities.Pending.Count == 1,
                "Worker-thread refreshes must defer game-state access.");
            Session.IsGameThread = true;
            MyAPIGateway.Utilities.Pending.Dequeue()();
            Check(group.Rebuilds == 1, "Deferred work must execute on the game thread.");
            Console.WriteLine("Punishment refresh behavior and work-count checks passed.");
        }
    }
}
`;

const work = await mkdtemp(join(tmpdir(), "scf-punishment-refresh-"));
try {
  const path = join(work, "Checks.cs");
  const executable = join(work, "checks.exe");
  await writeFile(path, source);
  execFileSync("mcs", ["-langversion:6", `-out:${executable}`, path], { stdio: "pipe" });
  process.stdout.write(execFileSync("mono", [executable], { encoding: "utf8" }));
} finally {
  await rm(work, { recursive: true, force: true });
}
