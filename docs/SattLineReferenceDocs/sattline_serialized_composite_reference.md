# SattLine Serialized Composite Reference

Status: reverse-engineered working note.

This document captures what can be confirmed today about serialized composite-object files with `.g` and `.y` extensions in this repo. In current SattLine file pairing, `.g` is the serialized composite sidecar for draft program files, while `.y` is the serialized composite sidecar for official program files. It is intentionally conservative: fields are marked from repeated observation in repo samples, matching `.s` or `.x` source names, and existing SattLine graphics prose. Unknowns stay unknown.

## Scope

Covered so far:

- shared file and record envelope used by sampled `.g` and `.y` files
- extension pairing: draft `.s` programs use `.g`, official `.x` programs use `.y`
- exact shared family mapping confirmed across `.g` and `.y`
- `PictureDisplay` records in `.g`
- `StringSelector` records in `.g` and `.y`
- `TrendCurve` records in `.g` and `.y`
- `ColumnDiagram` records in `.g` and `.y`
- `Alarmlist` or event-list records in `.y`

Not yet decoded enough for a field map:

- exact meaning of every numeric style code
- full token layout of trend and column-diagram payload sections
- full token layout of alarm-list numeric header fields
- full token layout of mixed payload lines such as `Lit 0 1 0 ...`

## Evidence Base

Main samples used for the first pass:

- [sattline_graphics_reference.md](sattline_graphics_reference.md)
- [../../tests/fixtures/sample_sattline_files/BatchDemo.g](../../tests/fixtures/sample_sattline_files/BatchDemo.g)
- [../../tests/fixtures/sample_sattline_files/SattLineFullGrammarTest.g](../../tests/fixtures/sample_sattline_files/SattLineFullGrammarTest.g)
- [../../Libs/HA/ProjectLib/KaHAApplLib.g](../../Libs/HA/ProjectLib/KaHAApplLib.g)
- [../../Libs/HA/ABBLib/NSupportLib.y](../../Libs/HA/ABBLib/NSupportLib.y)
- [../../Libs/HA/ABBLib/EventLib.y](../../Libs/HA/ABBLib/EventLib.y)
- [../../Libs/HA/ABBLib/BatchReportzLib.y](../../Libs/HA/ABBLib/BatchReportzLib.y)
- [../../Libs/HA/NNELib/nnesystem.y](../../Libs/HA/NNELib/nnesystem.y)
- user-supplied draft test program with eight `CompositeObject` placeholders and matching `.g` sidecar: default then customized `TrendCurve`, `ColumnDiagram`, `StringSelector`, and `Alarmlist`
- user-confirmed rule: `.g` and `.y` use the exact same family mapping

## Shared Envelope

High-confidence observations from sampled files:

0. File pairing follows program mode:

- draft program files use `.s` with `.g`
- official program files use `.x` with `.y`
- this document therefore treats `.g` as draft-sidecar and `.y` as official-sidecar

1. Both `.g` and `.y` files start with a quoted syntax-version header.

```text
" Syntax version 2.23, date: 2026-04-14-14:20:05.290 N "
```

2. Files then contain a flat sequence of serialized records.

3. A record starts with a small integer family code. Observed families so far:

- `5`: table-driven composite records, including `PictureDisplay` and `StringSelector`
- `4`: event-list or alarm-list style records
- `1`: trend-curve style records
- `2`: column-diagram style records

These family codes are now confirmed to match exactly between draft `.g` files and official `.y` files.

4. Every sampled record ends with a single trailing `0` line.

5. In sampled families `1`, `4`, and `5`, the lines immediately after the family code carry the placement rectangle. The last two values on the second line plus the two values on the third line behave like `(x1, y1) -> (x2, y2)`.

6. The first numeric line after the rectangle appears to be a style, colour, or frame code. It repeats in later payload lines often enough that it is probably not a count.

7. The next numeric line often acts like a subtype or payload discriminator inside the family.

8. Composite-object payloads are loaded in encounter order. In the `.s` or `.x` source, the graphics stream only shows `CompositeObject`; the next serialized record in the companion `.g` or `.y` file is then consumed as the payload for that placeholder.

## Family `5`: Table-Driven Composite Records

Family `5` is the most regular serialized shape in sampled `.g` and `.y` files.

Observed skeleton:

```text
5
<header line ending in x1 y1>
<x2 y2>
<style code>
<subtype code>
<payload>
0
```

The subtype line is the useful discriminator so far:

- subtype `2`: sampled `PictureDisplay`
- subtype `1`: sampled `StringSelector`

### Source-to-Serialized Alignment

High-confidence linkage rule:

- the `.s` or `.x` source does not inline the detailed composite payload
- draft source aligns `.s` to `.g`, while official source aligns `.x` to `.y`
- source only contributes a `CompositeObject` marker in the graphics stream
- composite records in `.g` and `.y` are matched by traversal order
- when parser or runtime reaches a `CompositeObject` in source order, it loads the next composite record from the serialized sidecar file

Practical consequence:

- a token-level decode of `.g` or `.y` has to preserve record order
- a token-level decode of `.s` alone cannot recover which composite subtype follows, because source only says `CompositeObject`
- correlating `.s` with `.g` or `.y` therefore means walking both streams in the same object order, not matching by explicit identifier embedded in the source placeholder

### Order-Confirmed Family Mapping

The strongest direct ordering evidence comes from a dedicated draft test program that contains exactly eight `CompositeObject` entries in source order:

1. default `TrendCurve`
2. default `ColumnDiagram`
3. default `StringSelector`
4. default `Alarmlist`
5. customized `TrendCurve`
6. customized `ColumnDiagram`
7. customized `StringSelector`
8. customized `Alarmlist`

Its `.g` sidecar contains records in this order:

1. family `1`
2. family `2`
3. family `5`, subtype `1`
4. family `4`
5. family `1`
6. family `2`
7. family `5`, subtype `1`
8. family `4`

That draft test establishes the mapping by encounter order, and user confirmation now closes the remaining gap: `.g` and `.y` share this family mapping exactly.

Confirmed shared family mapping:

- family `1` = `TrendCurve`
- family `2` = `ColumnDiagram`
- family `5`, subtype `1` = `StringSelector`
- family `4` = `Alarmlist`

Implication:

- family-code interpretation does not need separate draft and official tables
- the same family map applies in `.g` and `.y`
- differences between `.g` and `.y` should be treated as record content differences, not family-code remapping

### PictureDisplay: subtype `2`

This matches the existing graphics reference: the display content is chosen from a path, the path can be constant or variable, and an integer index can select from a table.

User-confirmed picture-display fields from live examples:

- trailing `t` or `f` line is `KeepPictureShape`
- `t` means true, so the picture keeps scale
- the line immediately before that flag is the zoomable source, either literal or variable
- the first line of the record can carry an activate variable, like modules do
- the numeric line before subtype `2` is the default line colour for the picture display
- the first payload line after subtype `2` can also carry an optional line-colour variable binding

Sampled indexed block from [../../Libs/HA/ProjectLib/KaHAApplLib.g](../../Libs/HA/ProjectLib/KaHAApplLib.g):

```text
5
 Lit  True  4 True  0.00000E+00 0.00000E+00
  1.00000E+00 7.14286E-02
 2
 2
 Var 0 18 Paths.OprPathIndex  None 2     1
0 0 +L2+UnitControl+L1+L2+UnitPanels+L1+L2+SelectOpr
 1 Var  Invalid  19 Paths.OperationPath
 Lit  True  4 True
f
           0
```

Current field map:

| Position | Confidence | Meaning |
|---|---|---|
| family code `5` | high | composite record family |
| rectangle lines | high | placement rectangle |
| first line `Lit ...` or `Var ...` before rectangle end | high | activate source, literal or variable |
| numeric line before subtype | high | default line colour for picture-display frame |
| subtype `2` | high | `PictureDisplay` discriminator |
| `Var ... Paths.OprPathIndex ...` | high | integer index variable |
| `0 0 +...SelectOpr` | high | table row mapping index `0` to a literal path |
| `1 Var Invalid 19 Paths.OperationPath` | high | table row mapping index `1` to a variable path source |
| line before trailing `t` or `f` | high | zoomable source, literal or variable |
| trailing `t` or `f` | high | `KeepPictureShape` flag |

This matches the domain rule you supplied: an indexed picture display carries three logical inputs plus a table.

- `Path` string source
- `KeepPictureShape` boolean
- activate source
- zoomable source
- line colour source
- integer index variable
- table of integer index to path mappings

### PictureDisplay Variants Confirmed

#### Activate variable on first line

The leading line can switch from a literal enable to a variable enable:

```text
5
 Var  True  24 KritKvitLOGData.Smal_Top  0.00000E+00 1.42857E-01
  1.00000E+00 2.14286E-01
 7
 2
 Lit 0 1 0  None 7     0
 0 +L2+UnitControl+L1+L2+UnitPanels+L1+L2+ToolBar
 Lit  True  4 True
f
           0
```

Confirmed meaning:

- `Var ... KritKvitLOGData.Smal_Top ...` is the activate variable for the picture display
- the rectangle still occupies the tail of the first two lines

#### Zoomable variable before keep-shape flag

The line before the trailing `t` or `f` flag is the zoomable source:

```text
5
 Var  True  24 KritKvitLOGData.Smal_Top  0.00000E+00 1.42857E-01
  1.00000E+00 2.14286E-01
 7
 2
 Lit 0 1 0  None 7     0
 0 +L2+UnitControl+L1+L2+UnitPanels+L1+L2+ToolBar
 Var  True  14 InletDV.V104.c
f
           0
```

Confirmed meaning:

- `Var  True  14 InletDV.V104.c` is the zoomable variable binding
- when no variable is bound, the same slot appears as a literal such as `Lit  True  4 True`
- the following single-letter line is not zoomable; it is `KeepPictureShape`

#### KeepPictureShape flag

The trailing one-letter line is now confirmed:

- `t` means `KeepPictureShape = True`
- `f` means `KeepPictureShape = False`

That field should no longer be treated as unidentified.

#### Default line colour and line-colour variable

The numeric line before subtype `2` is the default line colour. In the examples, it can change from `7` to `24`.

The first payload line after subtype `2` can also carry an optional variable binding for that colour:

```text
5
 Var  True  24 KritKvitLOGData.Smal_Top  0.00000E+00 1.42857E-01
  1.00000E+00 2.14286E-01
 24
 2
 Lit 0 1 0  Var 24 11 PanelColour     0
 0 +L2+UnitControl+L1+L2+UnitPanels+L1+L2+ToolBar
 Var  True  14 InletDV.V104.c
f
           0
```

Confirmed meaning:

- line `24` sets default line colour to `24`
- `Var 24 11 PanelColour` on the next payload line binds the line colour to variable `PanelColour`

Open detail:

- the full token-by-token structure of `Lit 0 1 0 ...` is still not decoded, but the line-colour segment inside it is now identified

The fixed-path case appears to be the same shape with the index selector effectively collapsed to a literal path row.

Sampled fixed blocks:

```text
5
 Lit  True  4 True  0.00000E+00 1.42857E-01
  1.00000E+00 2.14286E-01
 7
 2
 Lit 0 1 0  None 7     0
 0 +L2+UnitControl+L1+L2+UnitPanels+L1+L2+ToolBar
 Lit  True  4 True
f
           0
```

Working interpretation:

- subtype `2` still identifies `PictureDisplay`
- the path payload is literal rather than index-variable driven
- the trailing `t` or `f` is `KeepPictureShape`
- the zoomable source sits on the line immediately before that flag
- the default line colour sits on the numeric line immediately before subtype `2`

### StringSelector: subtype `1`

String selectors are easier to identify because the payload is visibly a title, an "otherwise" string, and an integer-to-string table.

Sample block from [../../Libs/HA/ABBLib/BatchReportzLib.y](../../Libs/HA/ABBLib/BatchReportzLib.y):

```text
5
 None  True   5.50000E-001 0.00000E+000
  7.50000E-001 5.00001E-002
 0
 1
CurveMode
Index not in table.
10
1
 Var 0 12 CS.CurveMode
 None 0
5
0
Momentary
1
Min
2
Max
3
MinMax
4
Mean
           0
```

Current field map:

| Position | Confidence | Meaning |
|---|---|---|
| family code `5` | high | composite record family |
| rectangle lines | high | placement rectangle |
| style code line | medium | visual or frame style code |
| subtype `1` | high | `StringSelector` discriminator |
| first string after subtype | high | selector title or label |
| second string after subtype | high | fallback or "otherwise" text |
| `Var ... CS.CurveMode` | high | integer index variable |
| line `5` before table rows | high | row count |
| alternating integer and string lines | high | lookup table |

Open detail: the two numeric lines between fallback text and the `Var ...` index declaration are stable in many samples, but their exact meaning is still unclear.

The dedicated draft test program also confirms two additional behaviors for subtype `1`:

- the first line can carry an enable source, for example `Var  True  6 Enable ...`
- changing string-selector colour settings from defaults to `24` affects both the numeric line before subtype `1` and the numeric slot after the index-variable line, but the exact per-token colour mapping is still open

## Family `1`: TrendCurve Records in `.g` and `.y`

Trend-style blocks in [../../Libs/HA/NNELib/nnesystem.y](../../Libs/HA/NNELib/nnesystem.y) and in the user-supplied draft test `.g` begin with family code `1` and have a much larger payload than family `5`.

High-confidence indicators inside one sampled block:

- repeated per-curve groups for `Trend1`, `Trend2`, and `Trend3`
- `JournalName`, `StartTime`, `JournalSystem`, and `Tag`
- enable flags such as `enable1`
- sample-count input such as `NoOfSamples`
- per-curve scaling variables such as `Trend1.Min` and `Trend1.Max`
- time-range values such as `DefaultRange`, `AltRange1`, `AltRange2`, and `TimeOffset`
- grid and relative-time flags

Working interpretation:

- family `1` is a serialized `TrendCurve` payload
- one record can contain multiple curves plus shared scale and time-axis configuration
- the payload is structured in nested sub-blocks rather than the simple key-value table used by family `5`

The dedicated draft test program confirms two additional points:

- the first line can carry a record-level enable source, for example `Var  True  6 Enable ...`
- changing the trend colour to `24` affects the numeric header at the start of the payload, confirming that early numeric fields in family `1` include colour-related configuration

This is enough to classify the family, but not yet enough to publish a stable field-by-field grammar.

## Family `2`: ColumnDiagram Records in `.g` and `.y`

Family `2` is now source-order-confirmed as `ColumnDiagram` by the dedicated draft test program.

Why confidence is high:

- the source contains eight `CompositeObject` placeholders with known creation order
- the second and sixth placeholders are `ColumnDiagram`
- the second and sixth serialized records are both family `2`

Observed characteristics from the default and customized draft samples:

- family `2` uses the same rectangle-first envelope style as the other families
- the first line can carry an enable source, for example `Var  True  6 Enable ...`
- changing the diagram colour to `24` changes early numeric fields in the record
- later payload lines include what looks like limit or scale values such as `1.00000E+02` and `0.00000E+00`

This is enough to identify family `2` reliably as `ColumnDiagram`, but not yet enough to publish a trustworthy token-by-token field map.

## Family `4`: EventList or AlarmList Records in `.y`

Very compact records in [../../Libs/HA/ABBLib/EventLib.y](../../Libs/HA/ABBLib/EventLib.y), [../../Libs/HA/ABBLib/NSupportLib.y](../../Libs/HA/ABBLib/NSupportLib.y), and the user-supplied draft test `.g` look like serialized event-list or alarm-list widgets.

Sample block:

```text
4
0.00000E+000  0.00000E+000  4.00000E+000  2.40000E+000
12            0            7  EventList.ListObject
0
```

Current field map:

| Position | Confidence | Meaning |
|---|---|---|
| family code `4` | medium | list-widget record family |
| four reals on next line | high | placement rectangle |
| trailing token `EventList.ListObject` | high | bound list object path |
| final `0` | high | end-of-record marker |

Working interpretation:

- family `4` is used for event-list or alarm-list presentation objects
- the bound object name is the most reliable semantic anchor currently available
- the three numbers before `EventList.ListObject` are still not decoded

The dedicated draft test program tightens this further:

- family `4` is not only list-like; it is source-order-confirmed as `Alarmlist`
- the bound object path can be a variable-like name such as `AlarmListVariable`
- changing colours to `24` changes the first two numeric fields before the trailing path, while the trailing `7` stays stable in the supplied example

## Practical Reading Rules

When reading raw `.g` or `.y` blocks, this order has been reliable:

1. Identify the family code.
2. Pull out the rectangle first.
3. In family `5`, use the subtype line before trying to decode payload.
4. Use literal strings and variable names as anchors.
5. Only then infer the surrounding numeric fields.

That keeps the note grounded in stable evidence instead of forcing meaning onto every integer token too early.

## Open Questions

- Is the first numeric line after the rectangle always a style code, or can it switch role by family?
- Does the `PictureDisplay` table always store both literal and variable path rows in the same shape?
- Are some family `5` records in `.y` still string selectors, or does `.y` reuse family `5` for additional composite widgets?
- Which family code identifies `ColumnDiagram` with enough consistency to document it separately?
