// Executes the production C# detector with a small game API stub. Requires mcs and mono.
import assert from "node:assert/strict";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { execFileSync } from "node:child_process";

const root = new URL("../ShipCoreFramework/src/Data/Scripts/ShipCoreFramework/", import.meta.url);
const source = await readFile(new URL("Shared/Utilities/Utils.Grid.cs", root), "utf8");
const method = source.match(/        internal static bool IsNpcGrid\(this IMyCubeGrid grid\)\n        \{[\s\S]*?\n        \}/)?.[0];
assert.ok(method, "Production NPC detector must exist");
const authority = await readFile(new URL("Server/Components/CoreComponent.Authority.cs", root), "utf8");
assert.match(authority, /Session\.Config\.IgnoreAiFactions && CoreBlock\.CubeGrid\.IsNpcGrid\(\)/);

const directory = await mkdtemp(join(tmpdir(), "scf-npc-detection-"));
try {
  const program = join(directory, "Checks.cs");
  await writeFile(program, `
using System;
using System.Collections.Generic;
class IMyCubeGrid {
    public bool IsNpcSpawnedGrid;
    public List<long> BigOwners = new List<long>();
    public List<long> SmallOwners = new List<long>();
}
class Player { public bool IsBot; }
class Players {
    // Both online player 10 and offline player 20 retain Steam identity mappings.
    public ulong TryGetSteamId(long id) { return id == 10 || id == 20 || id == 40 ? 123UL : 0UL; }
    public Player TryGetIdentityId(long id) {
        return id == 10 ? new Player() : id == 40 ? new Player { IsBot = true } : null;
    }
}
static class MyAPIGateway { public static Players Players = new Players(); }
static class Utils {
${method}
}
class Checks {
    static void Check(bool expected, IMyCubeGrid grid, string scenario) {
        if (Utils.IsNpcGrid(grid) != expected) throw new Exception(scenario);
    }
    static void Main() {
        Check(false, null, "null grid");
        Check(false, new IMyCubeGrid(), "unowned grid");
        Check(false, new IMyCubeGrid { BigOwners = null }, "missing owners");
        Check(false, new IMyCubeGrid { BigOwners = new List<long> { 0 } }, "owner zero is not NPC");
        Check(false, new IMyCubeGrid { BigOwners = new List<long> { 10 } }, "online player");
        Check(false, new IMyCubeGrid { BigOwners = new List<long> { 20 } }, "offline player");
        Check(true, new IMyCubeGrid { BigOwners = new List<long> { 30 } }, "NPC without Steam mapping");
        Check(true, new IMyCubeGrid { BigOwners = new List<long> { 40 } }, "bot with Steam mapping");
        Check(false, new IMyCubeGrid { BigOwners = new List<long> { 10 }, SmallOwners = new List<long> { 30 } }, "NPC minority alone");
        Check(true, new IMyCubeGrid { BigOwners = new List<long> { 30 }, SmallOwners = new List<long> { 10 } }, "player minority does not override NPC big owner");

        foreach (var playerId in new long[] { 10, 20 }) {
            foreach (var flagged in new bool[] { false, true }) {
                Check(false, new IMyCubeGrid { IsNpcSpawnedGrid = flagged, BigOwners = new List<long> { playerId, 30 } }, "player before NPC wins");
                Check(false, new IMyCubeGrid { IsNpcSpawnedGrid = flagged, BigOwners = new List<long> { 30, playerId } }, "player after NPC wins");
                Check(false, new IMyCubeGrid { IsNpcSpawnedGrid = flagged, BigOwners = new List<long> { 40, playerId } }, "player overrides bot too");
            }
        }

        var grid = new IMyCubeGrid { BigOwners = new List<long> { 0, 30 } };
        Check(true, grid, "NPC big owner");
        if (grid.IsNpcSpawnedGrid) throw new Exception("Must not change game flag");
        grid.BigOwners.Add(10);
        Check(false, grid, "player capture immediately overrides remaining NPC");
        grid.BigOwners.Remove(10);
        Check(true, grid, "NPC ownership restored");

        grid.IsNpcSpawnedGrid = true;
        grid.BigOwners.Clear();
        Check(true, grid, "vanilla flag without owners");
        grid.BigOwners.Add(20);
        Check(false, grid, "offline player overrides vanilla flag");
        if (!grid.IsNpcSpawnedGrid) throw new Exception("Must not clear game flag");
        MyAPIGateway.Players = null;
        Check(true, grid, "vanilla flag without player API");
        grid.IsNpcSpawnedGrid = false;
        Check(false, grid, "unavailable player API is not NPC evidence");
        Console.WriteLine("NPC detection behavior checks passed.");
    }
}
`);
  const executable = join(directory, "Checks.exe");
  execFileSync("mcs", ["-langversion:6", `-out:${executable}`, program], { stdio: "pipe" });
  process.stdout.write(execFileSync("mono", [executable], { encoding: "utf8" }));
} finally {
  await rm(directory, { recursive: true, force: true });
}
