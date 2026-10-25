import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";
import test from "node:test";
import * as validation from "./validation.js";

const app = readFileSync(new URL("./app.js", import.meta.url), "utf8");

test("large cores render only open limit editors and preserve their configuration", () => {
  const listeners = {};
  const nodes = new Map();
  const panels = new Map();
  const doc = {
    getElementById(id) {
      if (!nodes.has(id)) nodes.set(id, { innerHTML: "", classList: { toggle() {} } });
      return nodes.get(id);
    },
    addEventListener(name, handler) { listeners[name] = handler; },
    querySelector(selector) { return panels.get(Number(selector.match(/data-l="(\d+)"/)?.[1])); }
  };
  class Details {
    constructor(index) {
      this.dataset = { action: "limit-toggle", c: "1", l: String(index) };
      this.isConnected = true;
      this.content = {
        innerHTML: "",
        hasChildNodes() { return this.innerHTML !== ""; },
        replaceChildren() { this.innerHTML = ""; }
      };
    }
    querySelector() { return this.content; }
    get open() { return this.expanded; }
    set open(value) { this.expanded = value; listeners.toggle({ target: this }); }
  }
  const context = vm.createContext({
    ...validation, document: doc, HTMLDetailsElement: Details,
    restoreCoreTab() {}, renderWorkspaceStatus() {}
  });
  const evaluate = (source) => vm.runInContext(source, context);
  // Use the real editor renderers and delegated handlers, without browser startup.
  evaluate(app.slice(0, app.indexOf('ids("selectedGroup").addEventListener'))
    .replace(/^import[\s\S]*?from "[^"]+";\n/gm, ""));
  evaluate(`
    state.blockGroups = Array.from({length: 148}, (_, i) => ({name: 'Group ' + i, blockTypes: []}));
    state.shipCores = [{...createDefaultCore(), subtypeId: 'Large', uniqueName: 'Large',
      blockLimits: Array.from({length: 96}, (_, i) => ({...createDefaultLimit(), name: 'Limit ' + i,
        blockGroups: ['Group 0'], blockGroupDirections: {'Group 0': 'Forward'}, excludedBlockGroups: ['Group 1']}))}];
    state.selectedCoreIndex = 1;
    renderShipCores();
  `);
  const original = evaluate("JSON.stringify(state.shipCores)");
  const html = () => nodes.get("shipCores").innerHTML;
  assert.equal([...html().matchAll(/<details\b/g)].length, 96);
  assert.doesNotMatch(html(), /data-action="limit-name"/);

  for (let i = 0; i < 3; i++) {
    const panel = new Details(i);
    panels.set(i, panel);
    panel.open = true;
    assert.match(panel.content.innerHTML, /data-action="limit-name"/);
    assert.match(panel.content.innerHTML, /Directions override/);
  }
  assert.equal(panels.get(0).open, false);
  assert.equal(panels.get(0).content.innerHTML, "");
  assert.equal(evaluate("JSON.stringify(state.expandedLimitPanelsByCore[1])"), "[1,2]");
  evaluate("renderShipCores()");
  assert.equal([...html().matchAll(/data-action="limit-name"/g)].length, 2);
  assert.equal(evaluate("JSON.stringify(state.shipCores)"), original);

  // Edits live in state and survive disposing and reopening the DOM controls.
  evaluate("state.shipCores[0].blockLimits[2].maxCount = 42");
  panels.get(2).open = false;
  assert.equal(panels.get(2).content.innerHTML, "");
  panels.get(2).open = true;
  assert.match(panels.get(2).content.innerHTML, /value="42"/);
  assert.match(evaluate("writeBlockLimitXml(state.shipCores[0].blockLimits[2])"), /<MaxCount>42<\/MaxCount>/);

  // Browsers may deliver queued toggle events after an editor was replaced.
  const expanded = evaluate("JSON.stringify(state.expandedLimitPanelsByCore)");
  panels.get(2).isConnected = false;
  panels.get(2).open = false;
  assert.equal(evaluate("JSON.stringify(state.expandedLimitPanelsByCore)"), expanded);
});
