# Library module contract checks

Status: proposed.
Scope: SattLint analyzer layer.
Evidence: the local HA corpus and the ABB library tree, parsed directly with
`sattline-parser` (166 units, 4,075 module type definitions, 45,204 instances).
No corpus files or corpus values are part of this plan.

## Goal

Add static checks for library module contracts that are not covered by the parser
or the existing analyzers. The checks target the ABB library (`ABB_lib_dir`) and
the nnelib library, and they are selected per run like every other analyzer.

The first five checks come from the first review pass. Checks 6 to 10 come from
the second, domain-oriented pass over PID, valve, flow, message, and batch
modules. The evidence column uses the local corpus only as a validation target,
not as a fixture source.

| Check | Kind | Corpus evidence | Confidence |
| --- | --- | --- | --- |
| 1. Message and event tag collisions | correctness | 6 collision groups, 14 instances | high |
| 2. Operator message acknowledgement reset | correctness | 0 current hits, precise guard | high |
| 3. Handshake completion and success coverage | correctness | about 23 one-sided cases | high |
| 4. PBIOLib hardware identity | correctness | 1 mismatch | high |
| 5. `DispHeader.Usage` value | correctness | 7 non-conforming labels | high |
| 6. PID process value and range pairing | correctness | 1 mismatch in 105 pairs | high |
| 7. PID output and actuator pairing | correctness | 0 mismatches, 60 analog outputs | high guard |
| 8. Transfer display signal pairing | correctness | 0 mismatches in 1,203 pairs | high guard |
| 9. CIP valve seat address equality | heuristic | 3 equal pairs | medium |
| 10. Privilege hardwired | heuristic audit | 16 `EnableManual`, 3 `EnableOpControl`, 6 `EnableEdit`, 1 `EnableControl`, 3 `InterlockManual` false | medium |

## Architecture

Use three analyzer surfaces.

- Extend `alarm-integrity` with check 1. Tag identity, duplicate reporting, and
  module type resolution already live there.
- Add `library-contracts` for checks 2 to 9. It is a per-target correctness
  analyzer with small rule modules.
- Add `library-privileges` for check 10. It is a heuristic audit analyzer, so a
  policy finding never appears as a correctness defect.

Rejected alternatives:

- Five or ten new analyzers. Too much registry and cache boilerplate for rules
  that share a traversal and a contract table.
- Putting the privilege audit in `library-contracts`. The catalog category is
  per analyzer, and the audit is policy, not correctness.

## Shared infrastructure

### Module type resolution

Add `ContractResolver` under
`src/sattlint/analyzers/library_contracts/_mappings.py`.

- Build a name index from `bp.moduletype_defs`, then merge
  `analysis_context.graph.moduletype_defs.values()` when a graph is present.
  The graph dictionary is keyed by language identity, so the index is keyed by
  `casefold_key(moduletype.name)`.
- Resolve with `resolve_moduletype_def_strict`, passing `moduletype_index`,
  `current_library`, `unavailable_libraries`, `library_dependencies`, and
  `source_dependencies` from the graph.
- Return `None` on `ValueError`. Ambiguous or unknown types are skipped, not
  reported.

### Parameter mapping values

Add `ValueFingerprint` with `kind` in `literal`, `reference`, `default`, or
`unknown`, and a normalized `value`.

- Literal mapping: casefolded, stripped string, or `repr` for other values.
- Variable mapping: casefolded full dotted reference.
- No mapping with a parameter default: the default value's fingerprint.
- Unresolved: `unknown`, and any rule that needs every part skips the candidate.

Keep the display string separate from the fingerprint.

### Scope facts

Reuse `collect_statement_facts` from
`src/sattlint/analyzers/shared/_dependency_usage_facts.py` for checks 2 and 3.
It already resolves reads, writes, calls, and `SetBooleanValue` output
arguments, and it preserves the block kind.

Extend `StatementSite` and `StatementFact` with structured location fields
instead of parsing the `site` string:

- `sequence: str | None`
- `step: str | None`
- `phase: Literal["ENTER", "ACTIVE", "EXIT"] | None`
- `transition: str | None`

Keep the existing `site` string unchanged. Add a regression test that the
existing site text is identical, so current analyzer output does not move.

### Declaring scope

Tag uniqueness and handshake coverage are only meaningful inside the scope where
the inputs are fixed.

```python
def declaring_scope(module_path: list[str]) -> tuple[str, ...]:
    if "TypeDef:" in module_path:
        index = module_path.index("TypeDef:")
        return tuple(module_path[: index + 1])
    return tuple(module_path[:1])
```

### Device record index

For the PID and transfer pairing checks, build a per-file index from instances
whose `Signal` or `signal` parameter maps a record:

```text
(file, record source) -> set of module type names
```

This lets a check resolve `Dv.I.FT001.signal` to the transmitter record
`Dv.I.FT001` and `H02DV.V6x3.signal` to the actuator record `H02DV.V6x3`.

### Issue model

Use the existing `Issue` model with `kind`, `message`, `module_path`, `data`,
`explanation`, and `suggestion`. Reports use `SimpleReport` or a small report
class with `format_report_header`.

## Check 1: message and event tag collisions

Owner: `src/sattlint/analyzers/alarm_integrity.py`.

### Contract

From the library documentation:

- `OpMessage*`: `EVENTTAG = TagPrefix + "_" + TagSuffixAck`, and the same with
  `TagSuffixInfo`.
- `EventP2` and `EventP3`: `tag = Prefix + Delimiter + Name`.
- `RegularSystemAlarm`: `Prefix + Name`.
- `DynamicAlarm`: only after its module code confirms the composition.

### Contract table

```python
_COMPOSITE_TAG_RULES = {
    "opmessage": (("tagprefix", "tagsuffixack"), ("tagprefix", "tagsuffixinfo")),
    "opmessage_2l": (("tagprefix", "tagsuffixack"), ("tagprefix", "tagsuffixinfo")),
    "opmessage_3l": (("tagprefix", "tagsuffixack"), ("tagprefix", "tagsuffixinfo")),
    "acs_opmessage": (("tagprefix", "tagsuffixack"), ("tagprefix", "tagsuffixinfo")),
    "eventp2": (("prefix", "delimiter", "name"),),
    "eventp3": (("prefix", "delimiter", "name"),),
    "regularsystemalarm": (("prefix", "name"),),
}
```

Leave `MES_OpMessage`, `MESACS_OpMessage`, `DynamicAlarm`, and `NameSetup` out
until their composition or their helper role is confirmed.

### Collection

For each instance that resolves to a rule type:

1. Resolve each part with the existing `_get_parameter_value` helper.
2. Build a fingerprint tuple.
3. Skip the part tuple if any part is `unknown`.
4. Store the declaring scope, the fingerprint, the display string, the module
   path, and `message` or `event`.

### Emission

Group by `(scope_key, fingerprint)` and report every instance in a group larger
than one. Emit one issue per instance, matching the existing duplicate tag
style.

Kinds: `alarm.duplicate_message_tag` and `alarm.duplicate_event_tag`.

Messages:

- `Message tag 'X' is used by more than one message source: A, B.`
- `Event tag 'X' is used by more than one event source: A, B.`

If every part is a literal, also group by `(target_name, fingerprint)` across
declaring scopes. A literal tag does not vary per instantiation.

### False positive controls

- Different prefix references are different tags.
- Do not compare across scopes unless every part is a literal.
- Skip producers without a tag prefix.
- Do not use `NameSetup`, which is a helper and may legitimately repeat.

### Tests

Extend `tests/analyzers/test_alarm_integrity.py` with synthetic inline module
types:

- Same prefix reference and same suffix: two issues.
- Same prefix reference and different suffixes: no issues.
- Different prefix references and same suffix: no issues.
- Literal tags in two different scopes: two issues.
- `EventP2` with a different name: no issues.
- Unmapped prefix: no issues.

## Check 2: operator message acknowledgement reset

Owner: `src/sattlint/analyzers/library_contracts/_handshake.py`.

### Contract

A step that raises an operator message must clear the previous acknowledgement
before the guard can read it.

Canonical pattern:

```text
step entry:
    Message.Ack = False
    Message.SetAck = True

step transition:
    Message.Ack AND NOT Message.AckActive
```

The clear may also be in the step's active or exit code, or earlier in the
sequence.

### Detection

Use `collect_statement_facts` and the new structured location fields.

For each sequence:

- Walk the facts in source order.
- On a step, collect `raises` from writes to `base.SetAck = True`, and `clears`
  from writes to `base.Ack = False` or `base.Cancel = True` in enter, active, or
  exit.
- On a transition, collect reads of `base.Ack`.
- If a transition reads a base raised by the preceding step, and the base is not
  in the step's clear set or an earlier clear set, report.

Restrict to bases that are `MessageSetup` records of an `OpMessage*` instance in
the same declaring scope. This keeps the rule library-specific.

### Issue

Kind: `library.handshake_not_reset`.

Message: `Operator message handshake 'X.Ack' is waited on by transition 'Tr' without being cleared in step 'Step'; a stale acknowledgement can satisfy the transition immediately.`

### Tests

- Raise and wait with no clear: one issue.
- Clear in entry, active, or exit: no issue.
- Clear in an earlier step: no issue.
- Guard does not read `Ack`: no issue.
- Base is not a `MessageSetup` record: no issue.

## Check 3: handshake completion and success coverage

Owner: `src/sattlint/analyzers/library_contracts/_handshake.py`.

### Contract

`Ready` means the operation finished. `ReadyOK` means it finished successfully.
A caller that observes only one of them must have a failure path.

The module table is explicit:

```python
_HANDSHAKE_RULES = {
    "mes_journaldata": ("ready", "readyok", "error"),
    "jouwriteentry": ("ready", "readyok", "error"),
    "findallstarttimes": ("ready", "readyok", None),
    "zfindallstarttimese": ("ready", "readyok", None),
    "zrestorestringlist": ("ready", "readyok", None),
    "mestransactionctrl": ("ready", "readyok", "error"),
    # add other modules only after reading their parameter descriptions
}
```

The third entry is the failure output, when the module has one.

### Detection

For each instance of a handshake type:

- Read the mapped sources for `Ready`, `ReadyOK`, and the failure output.
- Build a read index for the declaring scope from `StatementFact.reads`.
- Determine which of the three variables are actually read in that scope.
- Report:
  - `Ready` read, `ReadyOK` not read, no failure read: completion only.
  - `ReadyOK` read, `Ready` not read, no failure read: success only.
  - `Ready` and `ReadyOK` both read, or a failure output read: pass.
  - Neither read: skip, the handshake is not used.

Requiring the read in the declaring scope prevents a false positive when the
status variable is passed to a parent that checks the other output.

### Issue

Kind: `library.handshake_status_incomplete`.

Messages:

- `Handshake 'X.Ready' is observed without 'ReadyOK' or an error output; a failed operation will be treated as successful.`
- `Handshake 'X.ReadyOK' is observed without 'Ready' or an error output; a failed operation will never release the wait.`

Data: `instance`, `moduletype`, `ready`, `readyok`, `error`, `site`.

### Tests

- `Ready` only with no failure output: one issue.
- `ReadyOK` only with no failure output: one issue.
- `Ready` and `ReadyOK`: no issue.
- `Ready` and `Error`: no issue.
- `ReadyOK` and `Error`: no issue.
- Status variable passed to a parent: no issue.
- Neither output mapped: no issue.

## Check 4: PBIOLib hardware identity

Owner: `src/sattlint/analyzers/library_contracts/_identity.py`.

### Contract

PBIOLib hardware modules document `Name` as the module instance name. The rack
lookup uses that name.

### Detection

Curated type set: `dim16`, `dom08`, `dom08_blind`, `aim08`, `dim08`, `dom16`,
`aim16`.

For each instance, if `Name` is a literal string, compare it case-insensitively
with the leaf instance name. Report a mismatch. Skip variable, `GLOBAL`, and
unmapped values.

### Issue

Kind: `library.io_name_mismatch`.

Message: `I/O module name 'X' does not match the instance name 'Y'; the rack will not find this module under that name.`

### Tests

Exact match, case-insensitive match, different literal, variable mapping, no
mapping, and a non-PBIOLib type with a `Name` parameter.

## Check 5: `DispHeader.Usage`

Owner: `src/sattlint/analyzers/library_contracts/_identity.py`.

### Contract

Only `Control` or `Master`, and only for recipe headers. Empty is allowed for
non-recipe headers.

### Detection

For each `DispHeader` instance, if `Usage` is a literal string outside
`{"", "control", "master"}`, report. Skip variable and unmapped values.

### Issue

Kind: `library.usage_value_invalid`.

Message: `DispHeader Usage 'X' is not one of the documented values 'Control' or 'Master'.`

### Tests

`Control`, `Master`, and empty pass. A label such as `Status` fails. A variable
mapping passes.

## Check 6: PID process value and range pairing

Owner: `src/sattlint/analyzers/library_contracts/_pairing.py`.

### Contract

A PID's process value and its range record must come from the same transmitter
record:

```text
Pv    => Dv.I.FT001.signal
PvPar => Dv.I.FT001.par
```

### Detection

For PID types `PidCtrl`, `AutoPidCtrl`, `Pid`, `PidCode`, `AdaptivePid`,
`Pid_Master`, and `PidLogicNew`:

- Compare `Pv` and `PvPar` only when the sources end with `.signal` and `.par`.
- Strip those suffixes and compare the remaining record paths.
- If the paths differ, report.
- Skip bare parameter names without a dot, which are wrapper parameters.
- Skip when the record path is not a device record in the device index.

The `.signal` and `.par` restriction is required. Without it, cascade setpoints
and selector outputs produce 43 false mismatches. With it, the corpus has 105
pairs and 1 real mismatch.

### Issue

Kind: `library.pid_range_pairing`.

Message: `PID 'X' reads its process value from 'A' but its range from 'B'; the controller is scaled against a different transmitter.`

### Tests

- Matching device records: no issue.
- Different device records: one issue.
- Cascade setpoint or selector source: no issue.
- Wrapper parameter without a dot: no issue.
- Missing `.signal` or `.par`: no issue.

## Check 7: PID output and actuator pairing

Owner: `src/sattlint/analyzers/library_contracts/_pairing.py`.

### Contract

A PID output and its output range must come from the same actuator record:

```text
C    => Dv.V101.signal
CPar => Dv.V101.par
```

A PID output must also drive an analog actuator, not a discrete valve.

### Detection

- Compare `C` and `CPar` with the same `.signal`/`.par` rule as check 6.
- Use the device record index to find the device whose `Signal`/`signal` source
  is the `C` record.
- Classify the device type as analog or discrete with a curated table.
- Report a discrete actuator target.

Corpus result: 72 output pairs, 0 mismatches. 60 outputs resolve to analog
devices, 0 to discrete devices.

### Issue

Kinds: `library.pid_output_pairing` and `library.pid_discrete_actuator`.

Messages:

- `PID 'X' writes its output to 'A' but takes the output range from 'B'.`
- `PID 'X' drives discrete device 'Y'; the 0 to 100 output cannot modulate it.`

### Tests

- Matching analog device: no issue.
- Different output record: one pairing issue.
- Discrete valve type: one actuator issue.
- Cascade output to another controller setpoint: no issue.
- Unknown device record: no issue.

## Check 8: transfer display signal pairing

Owner: `src/sattlint/analyzers/library_contracts/_pairing.py`.

### Contract

`TransferDisplayL` and `TransferDisplayR` bind `HighLight` and
`FlashHighLight` to fields of the record mapped to `Transfer`.

### Detection

For each instance, take the `Transfer` source root. If `HighLight` or
`FlashHighLight` is a variable source that does not start with that root, report.
Corpus result: 1,203 pairs, 0 mismatches. This is a guard.

### Issue

Kind: `library.transfer_signal_pairing`.

Message: `Transfer display 'X' reads 'HighLight' from a different transfer record than its 'Transfer' input.`

### Tests

Matching root, different root, variable mapping, literal mapping, and missing
`Transfer`.

## Check 9: CIP valve seat address equality

Owner: `src/sattlint/analyzers/library_contracts/_process.py`.

Status: optional, medium confidence.

### Contract

When both `CIPAddressHigh` and `CIPAddressLow` are configured on a multi-seat CIP
valve, they should differ.

### Detection

For `ValveCIPMP_*` and `Valve3Port*` types, if both parameters are mapped to
equal literals, report. The corpus has 3 such pairs.

Before shipping, confirm from the module code whether the addresses are relative
to separate higher and lower CIP stations. If they are, equality can be valid
and this check should be dropped.

### Issue

Kind: `library.cip_seat_address_equal`.

Message: `CIP valve 'X' uses the same address for both valve seats; the CIP station cannot distinguish the high and low seat.`

## Check 10: privilege hardwired

Owner: `src/sattlint/analyzers/library_privileges.py`.

### Contract

Several parameters are documented as privileges or safety settings. A literal
value that grants or removes the privilege is an audit finding.

Direction table:

```python
_PRIVILEGE_TRUE_RISK = (
    "enablemanual",
    "enableopcontrol",
    "enableedit",
    "enablecontrol",
)
_PRIVILEGE_FALSE_RISK = ("interlockmanual",)
```

Do not include parameters where `False` is the restrictive value (`EnablePar`,
`EnableParChanges`, `EnablePrivilege`). A literal `False` there is safe.

### Detection

For each instance of a library module, if a direction-table parameter is mapped
to a literal with the risky value, report. Skip variable and unmapped values.

Corpus evidence: 16 `EnableManual` true, 3 `EnableOpControl` true, 6
`EnableEdit` true, 1 `EnableControl` true, 3 `InterlockManual` false.

### Issue

Kind: `library.privilege_hardwired`.

Message: `Device or screen 'X' hardwires '<parameter>' to '<value>'; the operator privilege configuration is bypassed.`

For `InterlockManual = False`, the explanation says that interlocks are disabled
in manual mode, which is a safety setting.

### Tests

- Risky true direction: one issue.
- Risky false direction: one issue.
- Safe value: no issue.
- Variable mapping: no issue.
- Non-library module: no issue.

## Rejected candidates

These were investigated and rejected. Keep the reasons close to the code so the
next review does not rediscover them.

- **`InterlockValue` without `Interlock`.** `PidTuneType.Interlock` and
  `PidType.Interlock` default to `True`. Writing the value is effective without
  an explicit enable. The residual "interlock never released" check needs state
  machine context and is noisy.
- **`NewRecipeLoaded` never cleared.** The reset is consumer-owned. Some units
  clear it in a nested state, and `MESRecipeDownLoad` clears
  `p.Control.NewRecipeLoaded` itself. A file-level check reports 47 false
  positives.
- **Unmapped `SumError` parameters.** 2,135 hits. Too generic.
- **`Changed` reset.** 3,129 mappings with centralised resets.
- **`PidAlarming` unmapped.** 113 `AutoPidCtrl` instances. The alarm path may go
  through the alarm record.
- **`DetectIOFault` without `IOError`.** Often harmless because
  `Signal.Valid` carries the same information.
- **`Simulate = True`.** Two instances, both soft inputs driven from a
  calculated concentration.
- **`ButtonType = 0` and `Decimals = -1`.** Nine and one instances, both
  plausibly tolerated defaults.
- **Empty tag delimiters.** Four instances, all with the separator already in
  the name.
- **Duplicate device names.** 39 containers, mostly unit prefixes and DO/DI
  pairs.
- **`MMSReadOnly.GlobalVarName` versus `GlobalData`.** The remote MMS name and
  the local variable are intentionally different.
- **PID `Pv`/`PvPar` root match without `.signal`/`.par`.** 43 false positives
  from cascade setpoints and selector outputs.
- **`MessageLine` and `ValveFBAlarm` pairing.** The wrapper module type passes
  the record as a parameter, so the pairing needs inter-module parameter
  tracing.
- **Local copies of library module types.** 169 duplicate names, mostly
  intentional customisations.

## Registry and wiring

### `library-contracts`

- Add `analyze_library_contracts` to
  `src/sattlint/analyzers/registry/__init__.py` lazy exports.
- Add a spec template in `_registry_spec_templates.py` with key
  `library-contracts`, category `correctness`, and context kwargs
  `analysis_context`, `analyzed_target_is_library`, `unavailable_libraries`.
- Add delivery metadata in `registry/_registry_delivery_data.py`.
- Add a cache version marker in `src/sattlint/cache/__init__.py`.
- Add the key to `tests/cache/test_analyzer_cache_versions.py` pins.
- Add the key to `tests/analyzers/suites/test_registry_catalog.py`.

### `library-privileges`

- Add `analyze_library_privileges` to the lazy exports.
- Add a spec template with key `library-privileges`, category `heuristic`.
- Add delivery metadata and a cache version marker.
- Add the key to the catalog and cache tests.

### `alarm-integrity`

- Add the two composite tag kinds to its report labels.
- Update its spec description.
- Bump its cache version and refresh its pin.

## Tests

Unit tests:

- `tests/analyzers/test_library_contracts.py` for checks 2 to 9.
- `tests/analyzers/test_library_privileges.py` for check 10.
- Extend `tests/analyzers/test_alarm_integrity.py` for check 1.
- Use synthetic inline AST objects or small synthetic `.s` files. No reference
  corpus content.

Integration tests:

- One end-to-end synthetic project with two library units and one program.
- Run each new analyzer and check the JSON finding shape.

Registry and cache tests:

- Catalog keys and descriptions.
- Cache version pins.
- Analyzer architecture rules: no absolute analyzer imports, public
  `analyze_*` functions are registry-backed, no banned boundary imports.

Manual corpus validation:

- `alarm-integrity`: 6 collision groups.
- `library-contracts`: 1 I/O name mismatch, 7 `DispHeader.Usage` findings, 1 PID
  range pairing, about 23 handshake coverage findings.
- `library-privileges`: 29 audit findings.
- Guards remain silent.

Do not commit a corpus baseline.

## Documentation

Update `docs/analyzers.md`:

- Add `Library module contracts` with checks 2 to 9.
- Add `Library privileges` with the direction table.
- Extend `Alarm integrity` with message and event tag collisions.
- Use synthetic examples only.

Update `CHANGELOG.md` under `[Unreleased]`.

## Validation ladder

After each phase:

1. Focused `pytest` for the touched analyzer.
2. `python -m ruff check .`
3. `python -m ruff format --check .`
4. `python -m pyright src/sattlint tests`
5. `python -m pytest -q --tb=short`
6. `python -m pre_commit run --all-files` when Markdown changes.

## Sequencing

1. Extend `StatementSite` and `StatementFact` with structured locations. Keep
   the existing site text unchanged and prove it with a test.
2. Add `ContractResolver`, `ValueFingerprint`, and the device record index.
3. Implement check 1 in `alarm-integrity`.
4. Create `library-contracts` and implement checks 2 and 3.
5. Implement checks 4 and 5.
6. Implement checks 6, 7, and 8. Add check 9 only after the CIP address
   semantics are confirmed.
7. Create `library-privileges` and implement check 10.
8. Wire registry, cache versions, catalog tests, docs, and changelog.
9. Run the full ladder and the manual corpus pass.

## Risks and open questions

- **Ambiguous module types.** The corpus has many copied module types. The
  resolver skips ambiguous names instead of guessing.
- **Variable tag parts.** Tags are compared by variable identity, not runtime
  value. This is conservative.
- **Scope mistakes.** Tag collisions are reported inside one declaring scope,
  with a separate literal pass.
- **Handshake false positives.** A status variable passed to a parent that
  checks the other output must not be reported. The same-scope read rule
  handles this.
- **Privilege policy.** Hardwiring a privilege may be a deliberate plant
  standard. The analyzer is heuristic and opt-in.
- **CIP seat addresses.** Confirm whether the addresses are relative to separate
  CIP stations before shipping check 9.
- **`DynamicAlarm` and `MES_OpMessage`.** Confirm their tag composition before
  adding them to the rule table.
- **Ack guard.** The first version checks the clear only. Requiring `AckActive`
  in the guard is a follow-up decision.
