---
name: sattline-scaffold
description: "Create a new SattLine unit library + support library + program scaffold from NNEStart and enforce HA layering rules. Use when creating new ApplLib/SupportLib and UnitLib program files as `.g`, `.l`, and `.s` triplets. Never create `.x`, `.y`, or `.z` scaffolds."
argument-hint: "Unit names, target zone, and dependency choices"
---

# SattLine Scaffold

Create a new unit from NNEStart with program-utility baseline preserved.

In this repo, donor files are `Libs/HA/NNELib/NNEStart.x` and `Libs/HA/NNELib/NNEStart.z`. New scaffold outputs still must be `.s`, `.l`, and `.g`.

Output format is mandatory for new scaffolds:

- create `.s` as source file
- create `.l` as dependency list
- create `.g` as an empty companion file
- do not create `.x`, `.y`, or `.z`

Primary source for rules: `docs/references/SattLineApplicationSpec.md` (if available) or request from user.

## Use When

- Creating a new reusable process unit.
- Starting a new `ProjectLib` pair such as `MyUnitLib` + `MyUnitSupportLib`.
- Creating a new `UnitLib` program that instantiates exported moduletype from the main unit library.

## Inputs To Collect First

- Main library name, example `KaHANewUnitLib`.
- Support library name, example `KaHANewUnitSupportLib`.
- Program name, example `KaHANewUnitZ5`.
- Target area or zone id.
- Closest existing donor unit for dependency baseline.
- Reference to HA specification document (typically the SattLine Application Specification for your project).

## Required Architecture

Use NNEStart as program template only, including OP station utilities.

1. Program keeps NNEStart utility baseline: `OPStationUtility`, `TimeDistribution`, `ProgramUnitUtility`, version panes, and related infrastructure.
2. Inline unit block in NNEStart (`T11A Invocation ... ENDDEF (*T11A*)`) shall not stay inline in final program.
3. Rename `T11A` to the real unit name.
4. Move that unit block to `ProjectLib/<MainLib>.s`.
5. Convert moved unit block to exported moduletype in main library.
6. Move moduletypes declared inside that unit block into `ProjectLib/<SupportLib>.s`.
7. Main library shall reference support-library moduletypes and expose only unit contract intended for program use.
8. Program shall instantiate only the exported moduletype from main library.
9. Program shall not instantiate support library directly.
10. Do not delete donor content from NNEStart during scaffold split. Preserve all donor modules and type definitions across Program, MainLib, and SupportLib outputs.
11. Program shall retain generic NNEStart modules and infrastructure modules.
12. Main library shall contain the unit moduletype wrapper for requested unit.
13. Support library shall contain all remaining donor type definitions that are not part of the main exported unit wrapper.
14. Adapt only equipment-module names, labels, addresses, and unit-specific values needed for requested unit type.
15. Preserve donor unit-control ownership: if donor `T11A` body contains inline `UnitControl`, `Operations`, startup panels, phase paths, or batch-control wiring, those remain part of extracted main-library unit body.
16. Do not flatten donor control logic into a thin shell around a few equipment modules. `UnitControl` and operations subtree are part of the unit, not optional extras.

## Workflow

1. Scaffold files from `Libs/HA/NNELib/NNEStart.x` and `Libs/HA/NNELib/NNEStart.z`, writing the outputs as `.s` and `.l`, then create an empty `.g` companion for each new target.
2. Keep `UnitLib/<Program>.s` as NNEStart-derived program shell.
3. In `UnitLib/<Program>.s`, rename top-level unit invocation from `T11A` to real unit name.
4. Cut unit body from `UnitLib/<Program>.s` and paste into `ProjectLib/<MainLib>.s`.
5. Convert pasted unit from inline module definition to named exported moduletype.
6. Replace old inline unit body in program with invocation of exported main-library moduletype.
7. Move nested moduletype definitions from unit body into `ProjectLib/<SupportLib>.s`.
8. Wire `MainLib.l` to include `SupportLib`, then wire `Program.l` to include `MainLib`, and create empty `.g` companions for all three targets.
9. Keep generic donor modules in Program and do not delete NNEStart content; only move unit ownership to MainLib/SupportLib.
10. Update names, paths, addresses, and labels after extraction rather than inventing a new small module tree.
11. Run focused validation on touched files.
12. Before considering scaffold complete, inspect extracted unit body and confirm donor `UnitControl` module and operations subtree still exist after rename/split.

## Layering Rules (From HA Spec)

- Unit shall be created in library and instantiated from program.
- Program shall depend on unit library, not support library.
- Unit library shall have support library pair.
- Public IO datatypes belong in main unit library.
- Support-only moduletype and helpers stay private.
- Add dependencies only when used. Do not pre-add infrastructure libs.

## Sequence And Naming Guardrails (From HA Spec)

- Sequence step names start with `ST_`.
- Transition names start with `TR_`.
- Add timeout and deterministic handling for external waits.
- Keep action labels as actions, state labels as conditions.

## Critical Validation Rules

**SYNTAX-CHECK IS NOT ENOUGH.** Empty module definitions pass syntax validation but are semantically broken.

After each phase, verify semantic completeness:

1. **Unit Moduletype Substance Check**: Main library unit moduletype (e.g., `SprayDryer_299A`) must contain:
   - At least one MODULEPARAMETER (e.g., `Name`, `TankName`, or process parameters)
   - At least one LOCALVARIABLE (e.g., process-specific operational state)
   - At least one SUBMODULE invoking equipment types from support library (e.g., `InletModule`, `HeaterModule`)
   - Donor unit-control logic such as inline `UnitControl`, `Operations`, startup panels, phase paths, or equivalent donor-owned control subtree when present in `T11A`
   - Graphics and description text (GraphObjects with TextObject labels)
   - **Failure mode**: Module with only `Tag: string := "299A"` plus a few submodules is a bare shell, not the donor unit.

2. **Support Library Type Definitions Check**: Support library must contain actual equipment/operation module types referenced by main unit:
   - Each SUBMODULE in main unit must correspond to a MODULEDEFINITION in support library
   - Each equipment moduletype must have parameters and local variables specific to its purpose
   - Preserve donor support surfaces such as `T11AInlet`, `T11AOutlet`, `T11AAgitator`, `T11ACooling`, related state modules, and their command/DV/shared-input records unless there is a concrete donor-based rename plan
   - **Failure mode**: Empty TYPEDEFINITIONS or missing referenced types = dependency errors at runtime.

3. **Cross-Library Reference Verification**:
   - All `<SupportLibType>` names in main library SUBMODULES must be defined in support library
   - Grep for invocation type names in main lib, verify each exists in support lib
   - **Failure mode**: `SprayDryerInlet` referenced but not defined = unresolvable moduletype.

## Structural Donor-Fidelity Gate

Do not treat a semantically non-empty miniature replacement as success. First pass must still look like an extraction of the real donor unit.

Required checks against `NNEStart.x` donor surface:

1. **Main library must be donor-derived**:
   - Exported unit moduletype must be cut from actual `T11A Invocation ... ENDDEF (*T11A*)` body, then renamed.
   - Preserve donor subtrees. Do not delete donor content; relocate ownership between Program, MainLib, and SupportLib instead.
   - Preserve inline donor `UnitControl` and `Operations` subtree inside extracted unit body when present.
   - Failure mode: replacing donor body with a new 20-line wrapper around a few invented submodules.

2. **Support library must carry donor support definitions**:
   - Include donor record types and command/device interfaces used by extracted unit, for example `DVType`, `InletDVType`, `OutletDVType`, `TwoSpeedAgitDVType`, `CoolingDVType`, command types, shared inputs, and other directly referenced helper datatypes.
   - Include named donor equipment modules used by extracted unit, such as `T11AInlet`, `T11AOutlet`, `T11AAgitator`, and `T11ACooling`, or faithful renamed equivalents.
   - Include nested donor operation/state modules owned by those equipment modules; do not collapse them into label-only shells.
   - Failure mode: support lib contains only three invented equipment shells unrelated to donor unit.

3. **Program shell must keep donor baseline**:
   - Preserve `OPStationUtility`, `TimeDistribution`, `ProgramUnitUtility`, version panes, and other program-level baseline modules from NNEStart unless there is a specific runtime reason to remove them.
   - Remove inline `T11A` body from program and replace it with invocation of extracted main-library moduletype.
   - Keep generic NNEStart modules present in the donor template. Do not delete donor modules in scaffold flow.

## SattLine Syntax Constraints Learned From Failed Hand Scaffold

- Identifier length is capped at 20 characters. Check new library names, program names, moduletype names, and helper-generated invocation names before writing files.
- Every `MODULEDEFINITION` body needs a real `ModuleDef` section. `MODULEPARAMETERS`, `LOCALVARIABLES`, and `SUBMODULES` alone are not sufficient.
- `TextObject` belongs inside `GraphObjects` under `ModuleDef`; it is not a valid submodule invocation target.
- Passing `syntax-check` does not mean donor fidelity is preserved. A file can parse and still be an invalid scaffold if `UnitControl` or operations were deleted.

4. **Repo reality check**:
   - This repo does not provide `NNEStart.s` or `NNEStart.l` donor files.
   - If a helper or workflow assumes `.s/.l` donors, that workflow is wrong here and must use `.x/.z` donors to produce `.s/.l` outputs.

## Commands

Use the helper script in this skill:

```powershell
pwsh .github/skills/sattline-scaffold/assets/new-unit-scaffold.ps1 \
  -MainLibName KaHANewUnitLib \
  -SupportLibName KaHANewUnitSupportLib \
  -ProgramName KaHANewUnitZ5 \
  -UnitName KaHA999A \
  -UnitModuleTypeName ApplTank_999A
```

The helper only bootstraps donor-based files and a first rename. It does not finish extraction by itself. Work is incomplete until the donor-fidelity and semantic checks both pass.

Then validate with **BOTH syntax and semantic checks**:

```powershell
# Phase 1: Syntax validity (necessary but not sufficient)
.venv/Scripts/sattlint.exe syntax-check Libs/HA/ProjectLib/KaHANewUnitLib.s
.venv/Scripts/sattlint.exe syntax-check Libs/HA/ProjectLib/KaHANewUnitSupportLib.s
.venv/Scripts/sattlint.exe syntax-check Libs/HA/UnitLib/KaHANewUnitZ5.s

# Phase 2: Semantic completeness (verify module substance and references)
# - Read main lib .s file; verify unit moduletype has MODULEPARAMETERS, LOCALVARIABLES, and SUBMODULES
# - Read support lib .s file; verify each referenced equipment type is defined
# - Cross-check: every <Type> name in main lib SUBMODULES exists in support lib TYPEDEFINITIONS
# - Verify SUBMODULES reference count >= 1 (at minimum one equipment or operation module)
```

**DO NOT mark scaffold complete if syntax-check passes but modules are empty.**

## Required Adaptation Checklist

- `.l` contains only needed dependencies for its layer.
- Program `.l` includes main unit library, not support library-only dependency path.
- Each new scaffold target has an empty `.g` companion.
- Program keeps OP-station and program utility baseline from NNEStart.
- Program keeps generic donor modules from NNEStart; do not delete donor content.
- Main library contains extracted unit (former `T11A`) as exported moduletype.
- Main library contains the requested unit moduletype contract and unit wrapper ownership.
- Program instantiates extracted exported moduletype instead of inline unit body.
- Nested and remaining donor type definitions not owned by MainLib are moved to SupportLib.
- Support library contains all remaining donor type definitions and supporting equipment modules.
- Main library exports explicit moduletype wrapper used by program.
- Support modules not intended for export are private.
- No scaffold step creates `.x`, `.y`, or `.z` companions.
- No leftover `DEMO` text or `NNEStart` names.
- Equipment-module and unit-specific values are adapted to requested unit without deleting donor structure.
- First operation names describe process purpose, not generic `Run`/`Stop`.
- First sequence follows `ST_` and `TR_` naming.
