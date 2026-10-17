import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { getFieldHelp } from "./field-help.js";

const app = readFileSync(new URL("./app.js", import.meta.url), "utf8");
const html = readFileSync(new URL("./index.html", import.meta.url), "utf8");
const help = (action, field, value) => getFieldHelp({ dataset: { action, field }, value });
const defaults = (name) => Object.keys(JSON.parse(app.match(new RegExp(`const ${name} = (\\{[\\s\\S]*?\\n\\});`))[1].replace(/(\w+):/g, '"$1":')));

test("every static and rendered configuration field has detailed help", () => {
  for (const [, attributes] of html.matchAll(/<(?:input|select|textarea)\b([^>]+)>/g)) {
    const id = attributes.match(/\bid="([^"]+)"/)?.[1];
    assert.ok(getFieldHelp({ id }).length >= 120, `Missing detailed help for #${id}`);
  }
  for (const [, attributes] of app.matchAll(/<(?:input|select|textarea)\b([^>]+)>/g)) {
    const action = attributes.match(/data-action="([^"]+)"/)?.[1];
    const field = attributes.match(/data-field="([^"]+)"/)?.[1];
    if (action === "${action}") {
      if (attributes.includes('data-m="${field.name}"')) {
        for (const [action, fields] of [
          ["core-modifier-grid", defaults("DEFAULT_GRID_MODIFIERS")],
          ["core-modifier-passive-defense", defaults("DEFAULT_DEFENSE_MODIFIERS")],
          ["core-modifier-active-defense", defaults("DEFAULT_DEFENSE_MODIFIERS")]
        ]) for (const field of fields) assert.ok(help(action, field).length >= 120, `${action}/${field}`);
      } else if (field) {
        for (const action of ["core-friction-segment-field", "core-atmospheric-friction-segment-field"])
          assert.ok(help(action, field).length >= 120, `${action}/${field}`);
      } else {
        assert.match(attributes, /data-group-name=/, "Unrecognized dynamic field template");
        for (const action of ["limit-group-toggle", "limit-excluded-group-toggle"])
          assert.ok(help(action).length >= 120, action);
      }
    } else if (attributes.includes('data-m="${field.name}"')) {
      assert.equal(action, "core-modifier-speed");
      for (const field of defaults("DEFAULT_SPEED_MODIFIERS"))
        assert.ok(help(action, field).length >= 120, `${action}/${field}`);
    } else {
      assert.ok(help(action, field).length >= 120, `Missing detailed help for ${action}/${field || ""}`);
    }
  }
});

test("priority help explains ranking, blacklist prerequisite, ties, and separate selection systems", () => {
  const text = help("core-selection-priority");
  for (const pattern of [/Higher numbers/, /default to 0/, /block count/, /both match/, /must also blacklist/,
    /non-critical/, /overflow is shut off/, /carrier 10/, /transitive/, /Does not select the main\/backup/, /SpeedOverridePriority/])
    assert.match(text, pattern);
});

test("upgrade stat selectors describe every recognized stat and preserve runtime caveats", () => {
  const stats = JSON.parse(app.match(/const UPGRADE_STAT_OPTIONS = (\[[\s\S]*?\n\]);/)[1]);
  for (const stat of stats) assert.match(help("upgrade-mod-stat", null, stat), /Selected stat:/, stat);
  assert.match(help("upgrade-mod-stat", null, "ActiveBulletDamage"), /bullet routing/);
  assert.match(help("upgrade-mod-stat", null, "ActiveDefenseDuration"), /not those live timers/);
  assert.match(help("bt-subtype"), /empty\/base subtype/);
  assert.match(help("limit-group-directions"), /Forward=0, Backward=1, Up=2, Down=3, Left=4, Right=5, or Any=6/);
});
