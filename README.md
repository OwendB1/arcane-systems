# Arcane Systems

Arcane Systems is an ecosystem of Space Engineers mods, developed together in this repository. Each mod has its own documentation below.

## Mods

| Mod | Description | Documentation |
| --- | --- | --- |
| Ship Core Framework | Core-driven ship classes, block limits, grid modifiers, abilities, and server configuration. | [Ship Core Framework](docs/ship-core-framework.md) |
| Arcane Ship Cores | Core profiles and upgrade modules for combat ships, utility vessels, and stations, built on Ship Core Framework. | [Arcane Ship Cores](docs/arcane-ship-cores.md) |
| Arcane Power | Arcane reactor, containment controllers, and vent hardware. | [Arcane Power](ArcanePower/README.md) |
| Arcane Thrusters | Hydrogen plasma propulsion and reactor heat recovery. In development. | [Design and milestones](ArcaneThrusters/README.md) |

As new mods join the ecosystem, they will be listed here with their own documentation.

## Shared build menu

Arcane Power, Thrusters and Ship Cores share one **Arcane Systems** category in the G menu. Power contributes ten tiles, including separate bare and manifold pipe groups. Thrusters adds one engine group, a grid-size-paired plasma tank and a recovery charger. Ship Cores adds four groups for station cores, warship cores, utility cores and upgrades.

Each pack declares a unique category definition ID with the same `Name`, `ArcaneSystems`. SE merges the item IDs by name and uses the first contribution’s category settings. Set `StrictSearch` to `true` on every contribution and list just the group heads and standalone blocks. Players can scroll through the other variants after selecting a group. [Power menu](ArcanePower/src/Data/BlockCategories.sbc) · [Thruster menu](ArcaneThrusters/src/Data/BlockCategories.sbc) · [Ship Core menu](ArcaneShipCores/src/Data/BlockCategories.sbc)

Run `python3 tests/check_arcane_categories.py` with Mono and the local SE1 installation to verify shared-category merging and per-grid scroll lists.

## Tools and development

- [XML configurator](docs/scf-configurator/index.html) for authoring and updating Ship Core Framework configurations; see the [local preview instructions](docs/ship-core-framework.md#local-preview).
- [CoreSelectionPriority](docs/ship-core-framework.md#coreselectionpriority-example) controls connector blacklist ranking: higher values win, then group block count. It does not select the main core within a mechanical group.
- [Runtime authority layout](docs/authority-layout.md) for framework contributors.

## License

This project is licensed under the GNU General Public License v3.0 (`GPL-3.0-or-later`). See [LICENSE](LICENSE).
If you distribute modified versions, you must also provide the corresponding source code under the same GPL terms.
