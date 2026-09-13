# Arcane Ship Cores

[Back to Arcane Systems](../README.md)

Arcane Ship Cores is a content pack for [Ship Core Framework](ship-core-framework.md). It supplies core profiles for combat ships, utility vessels, and stations, along with upgrade modules and a no-core profile for grids without a core.

The mod package lives in [`ArcaneShipCores/`](../ArcaneShipCores/). Enable both this content pack and Ship Core Framework in your world.

## Core profiles

| Role | Profiles |
| --- | --- |
| Combat ships | Interceptor, Fighter, Gunship, Frigate, Destroyer, Cruiser, Battleship |
| Utility vessels | Courier, Utility, Extractor, Harvester |
| Stations | Outpost, Stronghold, Citadel |

Each profile defines its own size and ownership requirements, block limits, performance modifiers, speed, defenses, abilities, and allowed upgrades. The profiles represent specialized roles rather than a single progression of tiers.

## Upgrade modules

Large- and small-grid modules provide Combat, Economy, Handling, Harvester, and Overdrive upgrades. Availability and module counts depend on the core profile. Attach allowed modules to the active main core to apply their effects.

## Using a core

Build a core on a grid to select its profile. The first valid core becomes the main core. Allowed backup cores must match its forward and up orientation.

Use `/core help` for commands and `/core limits` while looking at a grid to inspect its limits. The build-preview HUD explains placement restrictions; the Core Status LCD displays core information.

## Configuration

The pack's XML files live under [`ArcaneShipCores/src/Data/`](../ArcaneShipCores/src/Data/):

- [`ShipCoreConfig_Manifest.xml`](../ArcaneShipCores/src/Data/ShipCoreConfig_Manifest.xml) lists core profiles, upgrade modules, manifest groups, and connector rules.
- [`ShipCoreConfig_Groups.xml`](../ArcaneShipCores/src/Data/ShipCoreConfig_Groups.xml) defines reusable block groups.
- [`ShipCoreConfig_No_Core.xml`](../ArcaneShipCores/src/Data/ShipCoreConfig_No_Core.xml) supplies the no-core profile.
- [`Cores/`](../ArcaneShipCores/src/Data/Cores/) contains individual core definitions.
- [`UpgradeModules/`](../ArcaneShipCores/src/Data/UpgradeModules/) contains upgrade definitions.

See the [framework configuration reference](ship-core-framework.md#config-file-map) for XML fields, commands, and enforcement behavior, and the [XML configurator instructions](ship-core-framework.md#xml-configurator) for editing these files.
