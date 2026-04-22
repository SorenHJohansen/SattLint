from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from ..core.taint_paths import TaintPathTrace, build_taint_path_traces
from ..models.ast_model import BasePicture
from .framework import Issue, format_report_header
from .variables import VariablesAnalyzer

_ISSUE_LABELS = {
    "taint-path.external_input_to_critical_sink": "External input reaches safety-critical sink",
}

_SOURCE_LABELS = {
    "mes": "MES/MMS input",
    "operator": "operator input",
    "sensor": "sensor input",
}


@dataclass
class TaintPathReport:
    basepicture_name: str
    issues: list[Issue] = field(default_factory=list)
    traces: list[TaintPathTrace] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.basepicture_name

    def summary(self) -> str:
        if not self.issues:
            lines = format_report_header("Taint paths", self.basepicture_name, status="ok")
            lines.append(f"Traced paths: {len(self.traces)}")
            lines.append("No taint-path issues found.")
            return "\n".join(lines)

        counts = Counter(issue.kind for issue in self.issues)
        lines = format_report_header("Taint paths", self.basepicture_name, status="issues")
        lines.append(f"Traced paths: {len(self.traces)}")
        lines.append(f"Issues: {len(self.issues)}")
        lines.append("")
        lines.append("Kinds:")
        for kind, label in _ISSUE_LABELS.items():
            count = counts.get(kind, 0)
            if count:
                lines.append(f"  - {label}: {count}")
        lines.append("")
        lines.append("Findings:")
        for issue in self.issues:
            location = ".".join(issue.module_path or [self.basepicture_name])
            lines.append(f"  - [{location}] {issue.message}")
        return "\n".join(lines)


class TaintPathAnalyzer:
    def __init__(
        self,
        base_picture: BasePicture,
        unavailable_libraries: set[str] | None = None,
        analyzed_target_is_library: bool = False,
    ) -> None:
        self.bp = base_picture
        self._unavailable_libraries = unavailable_libraries or set()
        self._analyzed_target_is_library = analyzed_target_is_library
        self._issues: list[Issue] = []
        self._traces: list[TaintPathTrace] = []

    @property
    def issues(self) -> list[Issue]:
        return self._issues

    @property
    def traces(self) -> list[TaintPathTrace]:
        return self._traces

    def run(self) -> list[Issue]:
        variable_analyzer = VariablesAnalyzer(
            self.bp,
            debug=False,
            fail_loudly=False,
            unavailable_libraries=self._unavailable_libraries,
            analyzed_target_is_library=self._analyzed_target_is_library,
            include_dependency_moduletype_usage=self._analyzed_target_is_library,
        )
        variable_analyzer.run()
        self._traces = build_taint_path_traces(
            variable_analyzer.effect_flow_edges,
            {key: tuple(events) for key, events in variable_analyzer.access_graph.by_path_key.items()},
            display_names_by_key=variable_analyzer.effect_flow_display_names,
        )

        for trace in self._traces:
            if not trace.spans_multiple_modules:
                continue
            sink_module_path = trace.sink_canonical_path.split(".")[:-1] or [self.bp.header.name]
            source_label = _SOURCE_LABELS.get(trace.source_kind, trace.source_kind)
            path_suffix = ""
            if len(trace.path) > 2:
                path_suffix = f" via {', '.join(trace.path[1:-1])}"
            self._issues.append(
                Issue(
                    kind="taint-path.external_input_to_critical_sink",
                    message=(
                        f"{source_label.capitalize()} {trace.source_canonical_path!r} reaches safety-critical sink "
                        f"{trace.sink_canonical_path!r}{path_suffix}."
                    ),
                    module_path=list(sink_module_path),
                    data={
                        "source_kind": trace.source_kind,
                        "source_canonical_path": trace.source_canonical_path,
                        "sink_canonical_path": trace.sink_canonical_path,
                        "path": list(trace.path),
                        "module_paths": [list(path) for path in trace.module_paths],
                    },
                )
            )

        return self._issues


def analyze_taint_paths(
    base_picture: BasePicture,
    debug: bool = False,
    unavailable_libraries: set[str] | None = None,
    analyzed_target_is_library: bool = False,
) -> TaintPathReport:
    analyzer = TaintPathAnalyzer(
        base_picture,
        unavailable_libraries=unavailable_libraries,
        analyzed_target_is_library=analyzed_target_is_library,
    )
    analyzer.run()
    return TaintPathReport(
        basepicture_name=base_picture.header.name,
        issues=analyzer.issues,
        traces=analyzer.traces,
    )
