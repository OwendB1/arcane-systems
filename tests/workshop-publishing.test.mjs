import assert from "node:assert/strict";
import { readFile, mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const root = new URL("../", import.meta.url);
const read = path => readFile(new URL(path, root), "utf8");
const semver = /^\d+\.\d+\.\d+$/;

for (const mod of ["ShipCoreFramework", "ArcaneShipCores", "ArcanePower"]) {
  const [titleFile, versionFile, descriptionFile] = await Promise.all([
    read(`${mod}/workshop/title.txt`),
    read(`${mod}/workshop/version.txt`),
    read(`${mod}/workshop/description.bbcode`),
  ]);
  const title = titleFile.trim();
  const version = versionFile.trim();
  const description = descriptionFile.replace(/\r\n/g, "\n").trimEnd();

  assert.ok(title && !/[\r\n]/.test(title), `${mod} title must be one line`);
  assert.match(version, semver, `${mod} version must be semantic`);
  assert.ok(Buffer.byteLength(`${title} (${version})`) <= 128);
  assert.ok(Buffer.byteLength(description) < 8000);
  assert.match(description, /^\[img]https:\/\/i\.imgur\.com\/fVVaDCS\.gif\[\/img]/);
}

const sharedWorkflow = await read(".github/workflows/steam-workshop-upload.yml");
const dedicatedWorkflows = [
  {
    contents: await read(".github/workflows/arcane-cores-workshop-upload.yml"),
    modDir: "ArcaneShipCores",
    otherModDir: "ShipCoreFramework",
  },
  {
    contents: await read(".github/workflows/shipcore-framework-workshop-upload.yml"),
    modDir: "ShipCoreFramework",
    otherModDir: "ArcaneShipCores",
  },
];

for (const { contents, modDir, otherModDir } of dedicatedWorkflows) {
  assert.match(contents, /group: steam-workshop-upload/);
  assert.match(contents, /default: main/);
  assert.ok(contents.includes(`- ${modDir}/**`));
  assert.ok(!contents.includes(otherModDir));
  assert.match(contents, /uses: \.\/\.github\/workflows\/steam-workshop-upload\.yml/);
  assert.match(contents, new RegExp(`mod_dir: ${modDir}`));
  assert.match(
    contents,
    /sbmi_profile: \$\{\{ github\.event_name == 'workflow_dispatch' && inputs\.sbmi_profile \|\| 'beta' \}\}/,
  );
  assert.match(contents, /secrets: inherit/);
}

assert.match(sharedWorkflow, /workflow_call:/);
assert.match(sharedWorkflow, /needs: build/);
assert.match(sharedWorkflow, /SE_DS_APPID: "298740"/);
assert.match(sharedWorkflow, /uses: actions\/cache@v5/);
assert.match(sharedWorkflow, /key: ds64-linux-\$\{\{ steps\.dsbuild\.outputs\.buildid \}\}/);
assert.match(sharedWorkflow, /steamcmd\.sh" \+quit \|\| true/);
assert.match(sharedWorkflow, /for attempt in 1 2 3 4 5/);
assert.match(sharedWorkflow, /app_update "\$SE_DS_APPID" validate/);
assert.match(sharedWorkflow, /DedicatedServer64\/SpaceEngineersDedicated\.exe/);
assert.match(sharedWorkflow, /test -f ds64\/Sandbox\.Game\.dll/);
assert.match(sharedWorkflow, /dotnet build arcane-systems\.sln --configuration Release/);
assert.match(sharedWorkflow, /SE_DS_DIR="\$RUNNER_TEMP\/space-engineers-dedicated"/);
assert.match(sharedWorkflow, /binarypath = %s\\n' "\$GITHUB_WORKSPACE\/ds64"/);
assert.match(sharedWorkflow, /SBMI_PROFILE: \$\{\{ inputs\.sbmi_profile \}\}/);
assert.match(sharedWorkflow, /\$\{\{ inputs\.workshop_dir \}\}\/title\.txt/);
assert.doesNotMatch(sharedWorkflow, /matrix\./);
assert.doesNotMatch(sharedWorkflow, /\$\{\{ runner\.temp \}\}/);
assert.match(sharedWorkflow, /\("title", title\)/);
assert.match(sharedWorkflow, /\("description", description\)/);
assert.match(sharedWorkflow, /description_bytes >= 8000/);
assert.doesNotMatch(sharedWorkflow, /replace\("\\n", "\\\\n"\)/);
assert.doesNotMatch(sharedWorkflow, /GetPublishedFileDetails\/v1\//);

const power = await read(".github/workflows/arcane-power-workshop-upload.yml");
assert.match(power, /pull_request:/);
assert.match(power, /group: steam-workshop-upload/);
assert.match(power, /sbmi_profile: main/);
assert.match(power, /preview_file: thumb.gif/);
assert.match(sharedWorkflow, /default: thumb.png/);
assert.match(sharedWorkflow, /if: github.event_name != 'pull_request'/);
assert.match(await read("ArcanePower/src/modinfo.sbmi.main"), /<Id>3819727962<\/Id>/);
const gif = await readFile(new URL("ArcanePower/src/thumb.gif", root));
assert.equal(gif.subarray(0, 6).toString(), "GIF89a");
assert.ok(gif.length < 1_000_000, "Workshop GIF must stay below 1 MB");
assert.equal(gif.readUInt16LE(6) * 9, gif.readUInt16LE(8) * 16);

// Execute the actual VDF generator, including old mods' main/beta title policy.
const generator = sharedWorkflow.split("      - name: Create SteamCMD upload script")[1]
  .split("python3 - <<'PY'\n")[1].split("\n          PY")[0]
  .split("\n").map(line => line.slice(10)).join("\n");
const temporary = await mkdtemp(join(tmpdir(), "arcane-workshop-"));
try {
  for (const [mod, profile] of [
    ["ArcanePower", "main"],
    ["ArcaneShipCores", "main"],
    ["ShipCoreFramework", "beta"],
  ]) {
    const metadata = fileURLToPath(new URL(`${mod}/workshop/`, root));
    const expected = (profile === "beta" ? "[BETA] " : "")
      + (await read(`${mod}/workshop/title.txt`)).trim()
      + ` (${(await read(`${mod}/workshop/version.txt`)).trim()})`;
    const result = spawnSync("python3", ["-c", generator], { encoding: "utf8", env: {
      ...process.env, WORKSHOP_TITLE_FILE: join(metadata, "title.txt"),
      WORKSHOP_VERSION_FILE: join(metadata, "version.txt"),
      WORKSHOP_DESCRIPTION_FILE: join(metadata, "description.bbcode"),
      WORKSHOP_PROFILE: profile, WORKSHOP_ID: "3819727962", STAGING_DIR: temporary,
      PREVIEW_FILE: join(temporary, mod === "ArcanePower" ? "thumb.gif" : "thumb.png"),
      RUNNER_TEMP: temporary, GITHUB_ENV: join(temporary, "env"),
      GITHUB_RUN_NUMBER: "1", GITHUB_SHA: "validation",
    }});
    assert.equal(result.status, 0, result.stderr);
    const vdf = await readFile(join(temporary, "workshop_item.vdf"), "utf8");
    assert.ok(vdf.includes(`"title" "${expected}"`));
    const description = (await read(`${mod}/workshop/description.bbcode`)).trimEnd();
    assert.ok(vdf.includes(description.replaceAll("\\", "\\\\").replaceAll('"', '\\"')));
  }
} finally { await rm(temporary, { recursive: true, force: true }); }
console.log("Workshop metadata, GIF and executable VDF checks passed.");
