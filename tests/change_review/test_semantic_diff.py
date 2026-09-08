# pyright: reportPrivateUsage=false
"""Semantic diff and relevance scenario tests for the Change Review capability."""

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
   EQUATIONBLOCK LevelSrc COORD 0.0, 1.0 OBJSIZE 1.0, 1.0 :
      Level = Status;
   SEQUENCE MainSeq (SeqControl, SeqTimer) COORD 0.0, 2.0 OBJSIZE 1.0, 0.5
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


def _review(official: VersionSnapshot, draft: VersionSnapshot, changes: list[ChangeChange], *, max_symbols: int = 60):
    provider = _provider(official, draft)
    relevance = compute_relevance(official, draft, changes, max_symbols=max_symbols)
    return build_change_review(official, draft, changes, relevance, snippet_provider=provider)


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


def test_semantic_context_reads_and_produces(tmp_path: Path):
    official, draft, _cfg = load_pair(tmp_path, CONTEXT_PROGRAM, CONTEXT_DRAFT)
    changes = _diff(official, draft)
    review = _review(official, draft, changes)
    flow_calc = next(change for change in review.changes if change.statement_context == "equation FlowCalc")
    context = flow_calc.semantic_context
    assert context is not None
    read_names = {fact.name for fact in context.reads}
    produced_names = {fact.name for fact in context.produces}
    assert "Level" in read_names
    assert "Flow" in produced_names


def test_read_symbol_has_data_origin(tmp_path: Path):
    official, draft, _cfg = load_pair(tmp_path, CONTEXT_PROGRAM, CONTEXT_DRAFT)
    changes = _diff(official, draft)
    review = _review(official, draft, changes)
    flow_calc = next(change for change in review.changes if change.statement_context == "equation FlowCalc")
    context = flow_calc.semantic_context
    assert context is not None
    level_fact = next(fact for fact in context.reads if fact.name == "Level")
    assert level_fact.produced_by == ("BasePicture",)


def test_produced_output_has_consumers(tmp_path: Path):
    official, draft, _cfg = load_pair(tmp_path, CONTEXT_PROGRAM, CONTEXT_DRAFT)
    changes = _diff(official, draft)
    review = _review(official, draft, changes)
    flow_calc = next(change for change in review.changes if change.statement_context == "equation FlowCalc")
    context = flow_calc.semantic_context
    assert context is not None
    consumer_names = {fact.name for fact in context.consumers}
    assert any("Meter" in name for name in consumer_names)
    assert any("FlowMeter" in name for name in consumer_names)


def test_semantic_facts_type_kind_and_definition(tmp_path: Path):
    official, draft, _cfg = load_pair(tmp_path, CONTEXT_PROGRAM, CONTEXT_DRAFT)
    changes = _diff(official, draft)
    review = _review(official, draft, changes)
    flow_calc = next(change for change in review.changes if change.statement_context == "equation FlowCalc")
    context = flow_calc.semantic_context
    assert context is not None
    flow_fact = next(fact for fact in context.produces if fact.name == "Flow")
    assert flow_fact.datatype == "integer"
    assert flow_fact.kind == "local"
    assert flow_fact.defined_by == "BasePicture"


def test_transition_change_carries_state_context(tmp_path: Path):
    official, draft, _cfg = load_pair(tmp_path, CONTEXT_PROGRAM, CONTEXT_DRAFT)
    changes = _diff(official, draft)
    review = _review(official, draft, changes)
    transition = next(change for change in review.changes if change.kind is ChangeKind.TRANSITION_CHANGED)
    context = transition.semantic_context
    assert context is not None
    assert context.sequence_name == "MainSeq"
    assert context.previous_state == "Filling"
    assert context.next_state == "Done"
    assert context.reads and {fact.name for fact in context.reads} == {"Level"}


def test_shared_dependency_is_not_duplicated(tmp_path: Path):
    official, draft, _cfg = load_pair(tmp_path, CONTEXT_PROGRAM, CONTEXT_DRAFT)
    changes = _diff(official, draft)
    review = _review(official, draft, changes)
    symbols = [fact.symbol.casefold() for fact in review.relevant_symbols]
    assert len(symbols) == len(set(symbols))
    level_facts = [fact for fact in review.relevant_symbols if fact.name == "Level"]
    assert len(level_facts) == 1


def test_unrelated_code_excluded_from_context(tmp_path: Path):
    official, draft, _cfg = load_pair(tmp_path, CONTEXT_PROGRAM, CONTEXT_DRAFT)
    changes = _diff(official, draft)
    review = _review(official, draft, changes)
    context_symbols = [block.symbol for block in review.context]
    relevant_symbols = [fact.symbol for fact in review.relevant_symbols]
    assert any("Meter" in symbol for symbol in context_symbols)
    assert not any("UnrelatedBlock" in symbol or "Boiler" in symbol for symbol in context_symbols)
    assert not any("UnrelatedBlock" in symbol or "Boiler" in symbol for symbol in relevant_symbols)


def test_context_size_budget_limits_relevant_symbols(tmp_path: Path):
    official, draft, _cfg = load_pair(tmp_path, CONTEXT_PROGRAM, CONTEXT_DRAFT)
    changes = _diff(official, draft)
    review_small = _review(official, draft, changes, max_symbols=4)
    assert len(review_small.relevant_symbols) <= 4


def test_inclusion_reasons_are_explained(tmp_path: Path):
    official, draft, _cfg = load_pair(tmp_path, CONTEXT_PROGRAM, CONTEXT_DRAFT)
    changes = _diff(official, draft)
    review = _review(official, draft, changes)
    for fact in review.relevant_symbols:
        assert fact.reason
    for block in review.context:
        assert block.reason


def test_s88_parent_context_included(tmp_path: Path):
    official, draft, _cfg = load_pair(tmp_path, FUNCTION_BLOCK_OFFICIAL, FUNCTION_BLOCK_DRAFT)
    changes = _diff(official, draft)
    review = _review(official, draft, changes)
    s88_facts = [fact for fact in review.relevant_symbols if fact.role == "s88"]
    assert any(fact.symbol == "BasePicture" for fact in s88_facts)
