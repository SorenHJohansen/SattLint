# pyright: reportPrivateUsage=false
"""Semantic diff and block-centric relevance tests for the Change Review."""

from __future__ import annotations

from pathlib import Path

import pytest

from sattlint.change_review import (
    ChangeChange,
    ChangeKind,
    VersionSnapshot,
    build_change_review,
    compute_relevance,
    compute_semantic_diff,
)
from sattlint.change_review.source import SourceTextProvider
from tests.helpers.change_review_support import (
    DRAFT_PROGRAM,
    FORMATTED_PROGRAM,
    FUNCTION_BLOCK_DRAFT,
    FUNCTION_BLOCK_OFFICIAL,
    OFFICIAL_PROGRAM,
    SEQUENCE_DRAFT_ADDED_STEP,
    SEQUENCE_DRAFT_CHANGED_TRANSITION,
    SEQUENCE_OFFICIAL,
    load_pair,
)

pytestmark = pytest.mark.unit

CONTEXT_PROGRAM = """\
"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: Demo"

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

TYPEDEFINITIONS
   ValveType = MODULEDEFINITION DateCode_ 1
   MODULEPARAMETERS
      Open: boolean;
   LOCALVARIABLES
      Opening: boolean := False;
      Running: boolean := False;
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   ModuleCode
   EQUATIONBLOCK Ctrl COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      Opening = Open AND NOT Running;
   ENDDEF (*ValveType*);
   FlowMeter = MODULEDEFINITION DateCode_ 1
   LOCALVARIABLES
      Reading: integer := 0;
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   ModuleCode
   EQUATIONBLOCK Measure COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      Reading = Flow;
   ENDDEF (*FlowMeter*);
   UnrelatedBlock = MODULEDEFINITION DateCode_ 1
   LOCALVARIABLES
      Heat: integer := 0;
      Temp: integer := 0;
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   ModuleCode
   EQUATIONBLOCK HeatCalc COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      Heat = Temp + 1;
   ENDDEF (*UnrelatedBlock*);

LOCALVARIABLES
   StartCmd: boolean := False;
   Status: integer := 0;
   Flow: integer := 0;
   Level: integer := 0;
   Backup: integer := 0;
   Log: integer := 0;

SUBMODULES
   FillValve Invocation
      ( 0.0 , 0.0 , 0.0 , 0.5 , 0.5
       ) : ValveType (
      Open => StartCmd);
   Meter Invocation
      ( 0.5 , 0.0 , 0.0 , 0.5 , 0.5
       ) : FlowMeter;
   Boiler Invocation
      ( 0.5 , 0.5 , 0.0 , 0.5 , 0.5
       ) : UnrelatedBlock;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK FlowCalc COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      Flow = Level * 2;
      Backup = Level;
   EQUATIONBLOCK LevelSrc COORD 0.0, 1.0 OBJSIZE 1.0, 1.0 :
      Level = Status;
   EQUATIONBLOCK StatusLog COORD 0.0, 2.0 OBJSIZE 1.0, 1.0 :
      Log = Status;
   SEQUENCE MainSeq (SeqControl, SeqTimer) COORD 0.0, 3.0 OBJSIZE 1.0, 0.5
      SEQINITSTEP Idle
         ENTERCODE
            Status = 0;
      SEQTRANSITION TrGo WAIT_FOR StartCmd
      SEQSTEP Filling
         ENTERCODE
            Status = 1;
      SEQTRANSITION TrDone WAIT_FOR Level >= 100
      SEQSTEP Done
         ENTERCODE
            Status = 3;
   ENDSEQUENCE

ENDDEF (*BasePicture*);
"""

CONTEXT_DRAFT = (
    CONTEXT_PROGRAM.replace("      Flow = Level * 2;", "      Flow = Level * 3;")
    .replace(
        "      SEQTRANSITION TrDone WAIT_FOR Level >= 100",
        "      SEQTRANSITION TrDone WAIT_FOR Level >= 90",
    )
    .replace("      Opening = Open AND NOT Running;", "      Opening = Open AND Running;")
)


def _provider(official: VersionSnapshot, draft: VersionSnapshot) -> SourceTextProvider:
    return SourceTextProvider({**official.source_files, **draft.source_files})


def _snippet_fn(provider: SourceTextProvider):
    def snippet_fn(source_file: str | None, span: object) -> str | None:
        start = getattr(span, "start", None)
        end = getattr(span, "end", None)
        if not isinstance(start, int) or not isinstance(end, int):
            return None
        return provider.snippet(source_file, start, end)

    return snippet_fn


def _diff(official: VersionSnapshot, draft: VersionSnapshot):
    provider = _provider(official, draft)
    return compute_semantic_diff(official, draft, snippet_fn=_snippet_fn(provider))


def _review(official: VersionSnapshot, draft: VersionSnapshot, changes: list[ChangeChange]):
    provider = _provider(official, draft)
    relevance = compute_relevance(official, draft, changes)
    return build_change_review(official, draft, changes, relevance, snippet_provider=provider)


def _context_review(tmp_path: Path):
    official, draft, _cfg = load_pair(tmp_path, CONTEXT_PROGRAM, CONTEXT_DRAFT)
    changes = _diff(official, draft)
    return official, draft, _review(official, draft, changes)


def test_no_changes_does_not_report_noise(tmp_path: Path):
    official, draft, _cfg = load_pair(tmp_path, OFFICIAL_PROGRAM, OFFICIAL_PROGRAM)
    assert _diff(official, draft) == []


def test_formatting_only_differences_do_not_produce_changes(tmp_path: Path):
    official, draft, _cfg = load_pair(tmp_path, OFFICIAL_PROGRAM, FORMATTED_PROGRAM)
    assert _diff(official, draft) == []


def test_one_changed_expression(tmp_path: Path):
    official, draft, _cfg = load_pair(tmp_path, OFFICIAL_PROGRAM, DRAFT_PROGRAM)
    changes = _diff(official, draft)
    assert len(changes) == 1
    assert changes[0].kind is ChangeKind.EXPRESSION_CHANGED
    assert "ValveOpen = Flow > 0" in str(changes[0].official)
    assert "ValveOpen = Flow > 5" in str(changes[0].draft)
    assert changes[0].statement_context == "equation Main"


def test_statement_context_names_sequence_and_step(tmp_path: Path):
    official, draft, _cfg = load_pair(tmp_path, SEQUENCE_OFFICIAL, SEQUENCE_DRAFT_ADDED_STEP)
    changes = _diff(official, draft)
    contexts = {change.statement_context for change in changes if change.statement_context}
    assert any("sequence MainSeq" in context for context in contexts)
    assert any("step" in context for context in contexts)


def test_added_symbol(tmp_path: Path):
    draft = OFFICIAL_PROGRAM.replace("   Flow: integer := 0;", "   Flow: integer := 0;\n   Extra: integer := 7;")
    official, draft_version, _cfg = load_pair(tmp_path, OFFICIAL_PROGRAM, draft)
    changes = _diff(official, draft_version)
    added = [change for change in changes if change.kind is ChangeKind.ADDED]
    assert any(change.symbol.endswith("Extra") for change in added)


def test_removed_symbol(tmp_path: Path):
    draft = OFFICIAL_PROGRAM.replace("   Flow: integer := 0;", "")
    official, draft_version, _cfg = load_pair(tmp_path, OFFICIAL_PROGRAM, draft)
    changes = _diff(official, draft_version)
    removed = [change for change in changes if change.kind is ChangeKind.REMOVED]
    assert any(change.symbol.endswith("Flow") for change in removed)


def test_changed_variable_declaration(tmp_path: Path):
    draft = OFFICIAL_PROGRAM.replace("   Flow: integer := 0;", "   Flow: real := 0.0;")
    official, draft_version, _cfg = load_pair(tmp_path, OFFICIAL_PROGRAM, draft)
    changes = _diff(official, draft_version)
    declared = [change for change in changes if change.kind is ChangeKind.DECLARATION_CHANGED]
    assert any(change.symbol.endswith("Flow") for change in declared)


def test_changed_function_block_implementation(tmp_path: Path):
    official, draft, _cfg = load_pair(tmp_path, FUNCTION_BLOCK_OFFICIAL, FUNCTION_BLOCK_DRAFT)
    changes = _diff(official, draft)
    module_change = [change for change in changes if change.symbol.endswith("Pump")]
    assert module_change
    assert any(change.kind is ChangeKind.EXPRESSION_CHANGED for change in module_change)


def test_changed_call_relationship(tmp_path: Path):
    official = OFFICIAL_PROGRAM.replace(
        "      ValveOpen = Flow > 0;",
        "      ValveOpen = Flow > 0;\n      Flow = GetTime();",
    )
    official_version, draft_version, _cfg = load_pair(tmp_path, official, OFFICIAL_PROGRAM)
    changes = _diff(official_version, draft_version)
    assert any(change.kind is ChangeKind.CALL_CHANGED for change in changes)


def test_changed_dependency(tmp_path: Path):
    official = OFFICIAL_PROGRAM.replace(
        "   Flow: integer := 0;",
        "   Flow: integer := 0;\n   Extra: integer := 7;",
    ).replace("      ValveOpen = Flow > 0;", "      ValveOpen = Extra > 0;")
    draft = official.replace("   Extra: integer := 7;", "")
    official_version, draft_version, _cfg = load_pair(tmp_path, official, draft)
    changes = _diff(official_version, draft_version)
    assert any(change.kind is ChangeKind.DEPENDENCY_CHANGED for change in changes)


def test_s88_step_added(tmp_path: Path):
    official, draft, _cfg = load_pair(tmp_path, SEQUENCE_OFFICIAL, SEQUENCE_DRAFT_ADDED_STEP)
    changes = _diff(official, draft)
    s88 = [change for change in changes if change.kind is ChangeKind.S88_CHANGED]
    assert any("Drain" in change.detail for change in s88)


def test_state_transition_changed(tmp_path: Path):
    official, draft, _cfg = load_pair(tmp_path, SEQUENCE_OFFICIAL, SEQUENCE_DRAFT_CHANGED_TRANSITION)
    changes = _diff(official, draft)
    assert any(change.kind is ChangeKind.TRANSITION_CHANGED for change in changes)


def test_multiple_independent_changes(tmp_path: Path):
    draft = DRAFT_PROGRAM.replace("   Flow: integer := 0;", "   Flow: integer := 0;\n   Extra: integer := 7;")
    official, draft_version, _cfg = load_pair(tmp_path, OFFICIAL_PROGRAM, draft)
    changes = _diff(official, draft_version)
    kinds = {change.kind for change in changes}
    assert ChangeKind.EXPRESSION_CHANGED in kinds
    assert ChangeKind.ADDED in kinds


def test_containing_equation_block_included_complete(tmp_path: Path):
    _official, _draft, review = _context_review(tmp_path)
    block = next(b for b in review.context if b.kind == "equation" and b.name == "FlowCalc")
    assert block.role == "changed"
    assert block.official_source is not None and "Flow = Level * 2;" in block.official_source
    assert block.draft_source is not None and "Flow = Level * 3;" in block.draft_source
    assert "Backup = Level;" in block.draft_source


def test_containing_sequence_block_included_complete(tmp_path: Path):
    _official, _draft, review = _context_review(tmp_path)
    block = next(b for b in review.context if b.kind == "sequence" and b.name == "MainSeq")
    assert block.role == "changed"
    assert block.draft_source is not None
    assert "Level >= 90" in block.draft_source
    assert "SEQSTEP Filling" in block.draft_source


def test_official_and_draft_source_for_changed_block(tmp_path: Path):
    _official, _draft, review = _context_review(tmp_path)
    block = next(b for b in review.context if b.kind == "sequence" and b.name == "MainSeq")
    assert block.official_source is not None and "Level >= 100" in block.official_source
    assert block.draft_source is not None and "Level >= 90" in block.draft_source


def test_related_block_writing_changed_variable_included(tmp_path: Path):
    _official, _draft, review = _context_review(tmp_path)
    blocks = {block.name: block for block in review.context}
    assert "LevelSrc" in blocks
    assert blocks["LevelSrc"].role == "related"
    assert any("Writes" in reason and "Level" in reason for reason in blocks["LevelSrc"].reasons)


def test_related_block_reading_changed_variable_included(tmp_path: Path):
    _official, _draft, review = _context_review(tmp_path)
    blocks = {block.name: block for block in review.context}
    assert "Measure" in blocks
    assert any("Reads" in reason and "Flow" in reason for reason in blocks["Measure"].reasons)


def test_unrelated_block_excluded(tmp_path: Path):
    _official, _draft, review = _context_review(tmp_path)
    block_names = {block.name for block in review.context}
    assert "HeatCalc" not in block_names
    assert "UnrelatedBlock" not in " ".join(block.symbol for block in review.context)


def test_variables_from_selected_blocks_have_definitions(tmp_path: Path):
    _official, _draft, review = _context_review(tmp_path)
    defined = {fact.name for fact in review.variable_definitions}
    assert "Backup" in defined
    assert "Status" in defined
    backup = next(fact for fact in review.variable_definitions if fact.name == "Backup")
    assert "Written by selected block" in backup.reason
    assert backup.datatype == "integer"


def test_context_expansion_stops_at_one_level(tmp_path: Path):
    _official, _draft, review = _context_review(tmp_path)
    block_names = {block.name for block in review.context}
    assert "StatusLog" not in block_names
    defined = {fact.name for fact in review.variable_definitions}
    assert "Status" in defined


def test_shared_block_is_deduplicated(tmp_path: Path):
    _official, _draft, review = _context_review(tmp_path)
    names = [block.name for block in review.context]
    assert len(names) == len(set(names))


def test_shared_variable_definition_is_deduplicated(tmp_path: Path):
    _official, _draft, review = _context_review(tmp_path)
    symbols = [fact.symbol.casefold() for fact in review.variable_definitions]
    assert len(symbols) == len(set(symbols))
    level_facts = [fact for fact in review.variable_definitions if fact.name == "Level"]
    assert len(level_facts) == 1


def test_multiple_changes_union_of_context(tmp_path: Path):
    _official, _draft, review = _context_review(tmp_path)
    block_names = {block.name for block in review.context}
    assert {"FlowCalc", "MainSeq", "Ctrl", "LevelSrc", "Measure"} <= block_names


def test_inclusion_reasons_are_explained(tmp_path: Path):
    _official, _draft, review = _context_review(tmp_path)
    for block in review.context:
        assert block.reasons
    for fact in review.variable_definitions:
        assert fact.reason


def test_semantic_metadata_matches_model(tmp_path: Path):
    official, draft, _cfg = load_pair(tmp_path, CONTEXT_PROGRAM, CONTEXT_DRAFT)
    changes = _diff(official, draft)
    review = _review(official, draft, changes)
    flow = next(fact for fact in review.variable_definitions if fact.name == "Flow")
    assert flow.datatype == "integer"
    assert flow.kind == "local"
    assert flow.declared_by == "BasePicture"
    level = next(fact for fact in review.variable_definitions if fact.name == "Level")
    assert any("equation LevelSrc" in site for site in level.written_by)


def test_variable_declaration_and_definition_separated(tmp_path: Path):
    _official, _draft, review = _context_review(tmp_path)
    level = next(fact for fact in review.variable_definitions if fact.name == "Level")
    assert level.declaration_source is not None
    assert "Level: integer" in level.declaration_source
    assert level.official_definition_source is not None
    assert "Level = Status" in level.official_definition_source
    assert level.draft_definition_source is not None
    assert "Level = Status" in level.draft_definition_source
    assert level.declaration_source != level.official_definition_source


def test_variable_definition_source_included(tmp_path: Path):
    _official, _draft, review = _context_review(tmp_path)
    by_name = {fact.name: fact for fact in review.variable_definitions}
    level = by_name["Level"]
    assert level.draft_definition_source is not None
    assert "Level = Status" in level.draft_definition_source
    flow = by_name["Flow"]
    assert flow.draft_definition_source is not None
    assert "Flow = Level * 3" in flow.draft_definition_source
    assert flow.official_definition_source is not None
    assert "Flow = Level * 2" in flow.official_definition_source


def test_direct_reads_do_not_include_broader_context_variables(tmp_path: Path):
    _official, _draft, review = _context_review(tmp_path)
    ctrl_change = next(change for change in review.changes if change.statement_context == "equation Ctrl")
    context = ctrl_change.semantic_context
    assert context is not None
    direct_reads = {fact.name for fact in context.reads}
    direct_writes = {fact.name for fact in context.produces}
    assert direct_reads == {"Open", "Running"}
    assert direct_writes == {"Opening"}
    assert "StartCmd" not in direct_reads
    assert "StartCmd" not in direct_writes


def test_broader_context_variables_still_included(tmp_path: Path):
    _official, _draft, review = _context_review(tmp_path)
    by_name = {fact.name: fact for fact in review.variable_definitions}
    assert "StartCmd" in by_name
    start_cmd = by_name["StartCmd"]
    assert "Read by selected block" in start_cmd.reason
    backup = by_name["Backup"]
    assert backup.draft_definition_source is not None


def test_relationship_terminology_is_precise(tmp_path: Path):
    _official, _draft, review = _context_review(tmp_path)
    flow = next(fact for fact in review.variable_definitions if fact.name == "Flow")
    assert flow.declared_by == "BasePicture"
    assert any("equation FlowCalc" in site for site in flow.written_by)
    assert any("equation Measure" in site for site in flow.read_by)
    running = next(fact for fact in review.variable_definitions if fact.name == "Running")
    assert running.declared_by == "ValveType"


def test_transition_change_carries_state_context(tmp_path: Path):
    _official, _draft, review = _context_review(tmp_path)
    transition = next(change for change in review.changes if change.kind is ChangeKind.TRANSITION_CHANGED)
    context = transition.semantic_context
    assert context is not None
    assert context.sequence_name == "MainSeq"
    assert context.previous_state == "Filling"
    assert context.next_state == "Done"
    assert context.containing_block is not None
    assert context.containing_block.name == "MainSeq"


def test_context_is_smaller_than_project(tmp_path: Path):
    _official, _draft, review = _context_review(tmp_path)
    stats = review.size_stats
    assert stats.selected_source_size < stats.total_project_source_size / 2
    assert 0.0 < stats.source_reduction_percent < 100.0
