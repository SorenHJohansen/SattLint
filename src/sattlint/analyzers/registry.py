"""Analyzer registry for CLI entrypoints."""
from __future__ import annotations

from sattlint.analyzers.spec_compliance import analyze_spec_compliance

from .framework import AnalysisContext, AnalyzerSpec
from .sfc import analyze_sfc
from .variables import analyze_variables
from .shadowing import analyze_shadowing
from .comment_code import analyze_comment_code
from .mms import analyze_mms_interface_variables


def get_default_analyzers() -> list[AnalyzerSpec]:
    def _run_variables(context: AnalysisContext):
        return analyze_variables(
            context.base_picture,
            debug=context.debug,
            unavailable_libraries=context.unavailable_libraries,
            analyzed_target_is_library=context.target_is_library,
        )

    def _run_mms_interface(context: AnalysisContext):
        return analyze_mms_interface_variables(
            context.base_picture,
            debug=context.debug,
        )

    def _run_sfc_checks(context: AnalysisContext):
        return analyze_sfc(context.base_picture)

    def _run_shadowing(context: AnalysisContext):
        return analyze_shadowing(
            context.base_picture,
            debug=context.debug,
            unavailable_libraries=context.unavailable_libraries,
        )

    def _run_spec_compliance(context: AnalysisContext):
        return analyze_spec_compliance(
            context.base_picture,
            debug=context.debug,
            unavailable_libraries=context.unavailable_libraries,
        )

    def _run_comment_code(context: AnalysisContext):
        return analyze_comment_code(context)

    return [
        AnalyzerSpec(
            key="variables",
            name="Variable issues",
            description="Unused/read-only/never-read variables and type mismatches",
            run=_run_variables,
        ),
        AnalyzerSpec(
            key="mms-interface",
            name="MMS interface mappings",
            description="MMSWriteVar/MMSReadVar mapping inventory",
            run=_run_mms_interface,
        ),
        AnalyzerSpec(
            key="sfc",
            name="SFC checks",
            description="Parallel-branch write race detection",
            run=_run_sfc_checks,
            enabled=True,
        ),
        AnalyzerSpec(
            key="comment-code",
            name="Commented-out code",
            description="Code-like content inside comments",
            run=_run_comment_code,
            enabled=True,
        ),
        AnalyzerSpec(
            key="shadowing",
            name="Variable shadowing",
            description="Local variables hiding outer or global names",
            run=_run_shadowing,
            enabled=True,
        ),
        AnalyzerSpec(
            key="spec-compliance",
            name="Engineering spec compliance",
            description="AST-visible checks from the application engineering spec",
            run=_run_spec_compliance,
            enabled=True,
        ),
    ]
