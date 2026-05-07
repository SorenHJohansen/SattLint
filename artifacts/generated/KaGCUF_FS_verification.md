# KaGCUF Functional Specification Verification

Generated documents:

- artifacts/generated/KaGCUF_FS_generated.docx
- artifacts/generated/KaGCUF_FS_238A_generated.docx

Reference template:

- DocTemplates/034 FSP 238Functional Specification for Unit 238A UF-DF Tank (LAI287 only) (1).docx

## Structural result

- Comparison target: `artifacts/generated/KaGCUF_FS_238A_generated.docx`
- Scoped unit: `StartMaster.KaGC238A`
- Core section order score: `1.0`
- Scoped generated core sections:
  - introduction
  - references
  - physical_model
  - unit_class
  - equipment_module
  - procedural_model
  - change_log
- Template core sections:
  - introduction
  - references
  - physical_model
  - unit_class
  - equipment_module
  - procedural_model
  - change_log

## What matches well

- The scoped generated document follows the same opening FS progression as the template:
  - Introduction
  - Scope
  - S88 Model
  - Definitions and abbreviations
  - Abbreviations
  - References
  - S88 Physical model
  - Process Cell / Unit Class definition
  - Equipment module instances
- The first 25 generated headings align closely with the first 25 template headings.
- The front matter now matches the template shape much more closely, including:
  - `NNE Author / NNE Author / NNE Author`
  - empty / `Document` / `NN Doc. no.`
  - `Unit / Unit Class / Danish Description / Unit Definition`
- The scoped document now uses the same template-style physical-model table headers for the main unit sections, including:
  - Measurements and logging
  - Special Logging
  - Inlet Consumption Logging
  - Unit Events
  - Interlocks
  - Exceptions
  - Calculations
  - Communication split into `From / Comment` and `To / Comment`

## Remaining differences

- The scoped generated document is still denser than the supplied template.
  - Scoped generated paragraphs: `1079`
  - Template paragraphs: `586`
  - Scoped generated tables: `86`
  - Template tables: `115`
  - Scoped generated headings: `279`
  - Template headings: `193`
- The process-cell heading text is nearly identical but not character-identical.
  - Template: `Process Cell ... UF/DF` using the source document's special separator glyph
  - Generated: `Process Cell - UF/DF`
- Table ordering still diverges after the common front matter and early physical-model sections.
  - The template shows an `Other Devices` table earlier in the sequence.
  - The scoped generated document enters timer and support-style tables earlier, so later table headers drift out of one-to-one alignment.
- Some support and appendix sections still use generic fallback schemas such as `Name / Module Type / Location / Notes`, which are structurally acceptable but not template-identical.

## Conclusion

The regenerated scoped 238A DOCX is now a strong structural match to the supplied template in section ordering, heading flow, front matter shape, and the main physical-model table schemas. It still does not match the template exactly in document density, some table ordering, and a few fallback table layouts, so it should be treated as closely template-shaped rather than template-identical.
