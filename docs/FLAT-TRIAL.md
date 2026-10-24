# Gerkinfeltser dev: flat Skyrim trial

This branch is an experimental, source-audited candidate, not an upstream release
or a claim of complete Gate to Sovngarde compatibility.

## Pinned starting points

- Native: Gerkinfeltser/IntelEngine-NativePlugin `6c32c8aef8823b5e1d8553d56870b9ce485fbfee`.
- Game package: Gerkinfeltser/IntelEngine-GamePlugin `83f4dbfb4aff4be363142a35350c5aaacc06b1d9`.
- CommonLib: MinLL/CommonLibVR `550cc4fb9114649dcf526d1f3d73d710c5d7003b`,
  with the existing guarded flat GetSaveParentCell header correction.

## What changes

The inherited dev snapshot queues NPC DM snapshot creation on the SKSE main
thread and rejects stale snapshots/results after a load generation changes.
This addresses an unsafe access context associated with upstream issue #15;
the original crash has not been reproduced here and its exact cause remains unproven.

This fork additionally passes captured game time (days times 86400) to memory
formatting on the worker. This removes one live Calendar lookup. It is a separate,
limited hardening change, not proof that issue #15 is fixed. The existing
SkyrimNet memory API calls and other worker-side state still require their own
thread-safety guarantees. Old work can run after a load; publication is fenced.

Builds default to SE/AE with VR disabled. Visual Studio Build Tools discovery,
matching PDB generation, a basename-only PDB reference, complete Papyrus builds,
and MSVC-compatible offline checks make the candidate inspectable and repeatable.
The migration test's throwing lambda now has an explicit return type, avoiding
MSVC's unreachable-code error without changing production migration behavior.

The pinned game dev repository was ahead of native dev in StoryEngine.psc and
intel_story_dm.prompt. The game dev versions were synchronized back into native
before the final build, preserving the all-types-excluded DM-call guard and the
prompt's allowed-type/repeated-seek restrictions. The first staged package was
rejected by this audit and was not installed. Final scripts are rebuilt from
these reconciled sources and rechecked against the real native exclusion list.

## Build and offline evidence

Validated on Windows with VS 2022 Build Tools 17.14 / MSVC 19.44, static vcpkg
dependencies, Python 3.13, and the checked-in dashboard npm lockfile.

1. Run `SKSE/BuildDLL.ps1 -Threads 2 -BuildDir SKSE/build-gts118-flat`.
2. Run `BuildPapyrus.ps1` with an original Papyrus compiler, dependency source
   import paths, TESV flags, the game-repository quest fragment, and a NEW output
   directory. All ten IntelEngine scripts plus the quest fragment must succeed.
   Use original SkyUI headers before decompiled headers: optional defaults are
   not recoverable from PEX. Local header/tool dependencies are not redistributed.
3. Run `npm ci --ignore-scripts` and `npm run build` in `web/dashboard`.
4. In an x64 developer shell run `SKSE/tests/RunForkChecks.py` with the vcpkg
   triplet directory and a local output directory. Set `CXX=cl.exe` for
   `RunBattleRelationPersistenceCheck.py`, `RunStoryTypeCountFilterCheck.py`,
   and the game repository's `tests/StoryTypeFilteringCheck.py`.
5. Build/run `ReferenceGetterDispatchCheck`; `--wrong-slot` must return 1.
6. Configure `SKSE/migration` separately with the vcpkg prefix, build both targets,
   and run `LegacyCacheMigrationCheck` with a NEW scratch directory argument.
   Never use an actual save directory for this test.

Passed: 8 queued-pipeline scenarios; snapshot clock and negative control; real
JSON/time formatting; codec, generation, biography and candidate checks; actual
CommonLib getter dispatch for 1.5.97 and 1.6.1170 plus wrong-slot control; battle
relation persistence; story count filters; 65,536 toggle/environment combinations;
copy-only legacy migration validation including refusal/partial-output paths.
All 11 Papyrus scripts and the dashboard compiled successfully.

Engine objects, queues and external APIs are substituted in the offline tests.
These checks do not establish gameplay stability, a reproduced CTD fix, or
compatibility with every mod in GTS. The DLL itself was compiled against the
pinned actual CommonLib dependency; the getter check exercises its real wrapper.

## Packaging and rollback

Use the matching game fork's `tests/BuildAuditedPackage.py`, not a DLL overlay
on a 3.5.2 installation. It verifies compiled-source hashes, copies the matching
assets and optional converter, anonymizes only PEX diagnostic user/host metadata,
checks FOMOD paths, and verifies the resulting ZIP contents by SHA-256.
Keep the matching PDB privately for diagnostics; it is not installed in-game.

Trial prerequisites: Skyrim 1.6.1170, SkyrimNet Beta28, SeverActions 4.5.0,
existing SKSE/Address Library/PapyrusUtil/po3 Papyrus Extender/SkyUI, and Papyrus
MessageBox SKSE NG v1.0.0. PrismaUI is optional; MCM works without it. No VR mods.

Install only on the existing SkyrimNet test profile after a verified backup of
both profiles, saves/co-saves, Vortex state, and external SkyrimNet data. Keep
the original GTS profile unchanged. Skip the legacy converter for a save which
has never used IntelEngine. For rollback, disable this package and its newly
added dependency on the test profile, redeploy, and return to a pre-install save
with its matching external AI data. Disabling alone does not undo a saved script
state; do not overwrite newer progress with an old backup without reviewing it.

Live validation is recorded separately; successful offline checks are not a
substitute for loading, NPC cycles, a new manual save, and reloading in-game.
