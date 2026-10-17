# Runtime authority layout

Ship Core Framework is compiled as one Space Engineers mod assembly, but its source is organized by runtime role. The folder boundary makes authority visible during development; it is not a security boundary by itself. Runtime guards and packet validation remain mandatory.

## Source roles

| Folder | Responsibility |
| --- | --- |
| `Client/` | Presentation, local input, replicated-state consumption, and client-bound packet handlers. |
| `Server/` | Rule evaluation, world mutation, persistence, enforcement, authoritative snapshots, and client-to-server packet handlers. |
| `Shared/` | Wire contracts, observer state, and role-neutral coordinators/helpers used by both roles. |
| `Session/` | Session lifecycle and grid-group observation, with role hooks under `Session/Client` and `Session/Server`. |
| `Config/` | Shared configuration models and mod-asset loading, with world persistence under `Config/Server`. |
| `API/` | The external mod API contract and shared read surface, with authoritative mutations under `API/Server`. |

A listen server and single-player session run both roles. Code must therefore use independent `Session.IsClient` and `Session.IsServer` checks rather than treating the roles as mutually exclusive.

## Dependency rules

- Client code may read local observer state and replicated snapshots. It must not calculate authoritative limits, mutate grids, or invoke enforcement to refresh display data.
- Server code owns validation and every gameplay mutation. Never trust a client packet's player identity, permissions, target, timing, or requested state without server-side validation.
- Shared contracts must not depend on presentation or enforcement implementations.
- Shared lifecycle coordinators may dispatch to role-specific partial methods after checking the applicable role.
- Client and server partials may extend the same `Session`, `GroupComponent`, `GridComponent`, `Commands`, or `ModAPI` type. Do not introduce parallel client/server object hierarchies solely to mirror the same grid group.

## Runtime-state flow

1. The server evaluates limits, modifiers, abilities, and speed state.
2. The server snapshot publisher serializes the client-visible result using contracts from `Shared/Network`.
3. The client runtime-state consumer applies the snapshot to observer components.
4. Client UI and read-only API queries render or return that replicated state without re-running enforcement.

Commands follow the same direction: `Client/UI/Commands.Chat.cs` captures local chat, `Server/Commands/Commands.Transport.cs` validates the sender and payload, and `Server/Commands/Commands.Administration.cs` owns administrative mutations.

## Modifier state

Each `GridComponent` stores a value snapshot of its applied framework modifiers.
Group refreshes compare against that snapshot before copying or visiting blocks.
Newly added blocks receive the current modifiers individually; a newly joined grid
has its own empty snapshot and receives an initial application. Grid cleanup clears
the snapshot. Native production upgrade events continue to update the affected
refinery or assembler independently.

Core, upgrade, configuration, override, ability, block/PCU, ownership, mobility, and
faction changes drive refreshes. Bursts of block and ownership events share a queued
game-thread rule refresh. The game-thread cache drain also applies dirty modifier
state, so rebuilding a cache cannot consume an update without applying it. Defense
reads reuse calculated state and publish only changed values or newly joined grids.
The periodic punishment/ignored-state checks remain as a fallback for changes that
arrive without notifications; unchanged values produce no modifier block scans or
writes.

## Placement guide

- Add HUD, LCD, terminal, notification, or local-input behavior under `Client/`.
- Add punishment, persistence, ownership-limit mutation, world-definition mutation, or authoritative timers under `Server/`.
- Add packet DTOs under `Shared/Network`; place each handler on the side that receives the packet.
- Keep session, configuration, and external API domains at the source root. Nest role-specific partials inside those domain folders only when required.
- Put all other business logic under `Client/`, `Server/`, or `Shared/`.
- Keep configuration data shapes and observer component identity shared when both roles need them.
- When a method is genuinely mixed, keep a small shared coordinator and extract the role-specific work into partial files.

The dedicated server build still compiles client source because Space Engineers loads one mod assembly. The practical goal is to prevent client execution of server logic and make accidental cross-role calls easy to spot in review.
