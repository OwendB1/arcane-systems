# Arcane Systems

Arcane Systems is an ecosystem of Space Engineers mods, developed together in this repository. Each mod has its own documentation below.

## Mods

| Mod | Description | Documentation |
| --- | --- | --- |
| Ship Core Framework | Core-driven ship classes, block limits, grid modifiers, abilities, and server configuration. | [Ship Core Framework](docs/ship-core-framework.md) |
| Arcane Ship Cores | Core profiles and upgrade modules for combat ships, utility vessels, and stations, built on Ship Core Framework. | [Arcane Ship Cores](docs/arcane-ship-cores.md) |
| Arcane Power | Arcane reactor, containment controllers, and vent hardware. | [Arcane Power](ArcanePower/README.md) |

As new mods join the ecosystem, they will be listed here with their own documentation.

## Shared build menu

Power and Ship Cores contribute to one **Arcane Systems** section in the G menu.
Either mod works independently; together the section contains 36 block definitions
(12 Power blocks, 14 cores, and 10 upgrades). Debug and internal blocks are excluded.

Future mods can join through their own `Data/BlockCategories.sbc`: use a unique
category `Id/SubtypeId` such as `ArcaneSystems_MyMod`, with
`<Name>ArcaneSystems</Name>` and `<DisplayName>Arcane Systems</DisplayName>`.
List that mod's blocks in `ItemIds` as exact `TypeId/SubtypeId` strings, following
[Power's contribution](ArcanePower/src/Data/BlockCategories.sbc) or
[Ship Cores' contribution](ArcaneShipCores/src/Data/BlockCategories.sbc).
Space Engineers merges item lists by `Name`; distinct definition IDs preserve
each contribution regardless of load order. No shared runtime dependency is needed.

`python3 tests/check_arcane_categories.py` checks block coverage and the installed
game's native merge/filter behavior for either mod, both load orders, and duplicate
contributions (requires Mono and the local Steam installation).

## Tools and development

- [XML configurator](docs/scf-configurator/index.html) for authoring and updating Ship Core Framework configurations; see the [local preview instructions](docs/ship-core-framework.md#local-preview).
- [Runtime authority layout](docs/authority-layout.md) for framework contributors.

## License

This project is licensed under the GNU General Public License v3.0 (`GPL-3.0-or-later`). See [LICENSE](LICENSE).
If you distribute modified versions, you must also provide the corresponding source code under the same GPL terms.
