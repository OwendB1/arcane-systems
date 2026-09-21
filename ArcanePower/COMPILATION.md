# Compile Arcane Power for SE1

Run from the repository root:

```sh
python ArcanePower/tools/compile_mod.py
```

The helper compiles a temporary source copy with the compatibility imports that
SE1's `MyScriptManager.UpdateCompatibility` adds to every mod source. It uses
ArcanePower.csproj and its MDK analyzers against the installed game assemblies.
It does not deploy, run regression suites, control the game or modify source files.
The local `ArcanePower.mdk.local.ini` selects the game binary directory.

Arcane Power already uses the same packages as ShipCoreFramework:
`Mal.Mdk2.ModAnalyzers` 2.1.15 and `Mal.Mdk2.References` 2.2.7, C# 6, net48/x64.
A plain `dotnet build` checks the whitelist and normal compilation, but does not
include SE's injected imports. Use the helper before deployment. It covers those
imports and MDK diagnostics, not runtime behavior or native SBC/model validation.

On 2026-09-16, the game log reported CS0104 in TabletLink.cs because both
`Sandbox.Game.Entities` and injected `VRage.Game.ModAPI.Interfaces` define
`IMyControllableEntity`. The suit broadcast check needs the former. Fully
qualifying that cast fixes the collision. The compatibility build reproduced the
failure before the fix and passed with zero warnings/errors afterward:
`validation/compatibility-before.log` and `validation/compatibility-build.log`.
