from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from ..core.safety_paths import SafetyPathTrace, build_safety_path_traces
from ..models.ast_model import BasePicture
from .framework import Issue, format_report_header
from .variables import VariablesAnalyzer

_ISSUE_LABELS = {
    "safety-path.unconsumed_signal": "Unconsumed safety-critical signals",
}


@dataclass
class SafetyPathReport:
    basepicture_name: str
    issues: list[Issue] = field(default_factory=list)
    traces: list[SafetyPathTrace] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.basepicture_name

    def summary(self) -> str:
        if not self.issues:
            lines = format_report_header("Safety paths", self.basepicture_name, status="ok")
            lines.append(f"Traced paths: {len(self.traces)}")
            lines.append("No safety-critical path issues found.")
            return "\n".join(lines)

        counts = Counter(issue.kind for issue in self.issues)
        lines = format_report_header("Safety paths", self.basepicture_name, status="issues")
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


class SafetyPathAnalyzer:
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
        self._traces: list[SafetyPathTrace] = []

    @property
    def issues(self) -> list[Issue]:
        return self._issues

    @property
    def traces(self) -> list[SafetyPathTrace]:
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
        self._traces = build_safety_path_traces(
            {
                key: tuple(events)
                for key, events in variable_analyzer.access_graph.by_path_key.items()
            }
        )

        for trace in self._traces:
            if trace.writer_count <= 0 or trace.reader_count > 0:
                continue
            module_path = list(trace.writer_module_paths[0]) if trace.writer_module_paths else [self.bp.header.name]
            self._issues.append(
                Issue(
                    kind="safety-path.unconsumed_signal",
                    message=(
                        f"Safety-critical path {trace.canonical_path!r} is written but never read "
                        f"across the analyzed target."
                    ),
                    module_path=module_path,
                    data={
                        "canonical_path": trace.canonical_path,
                        "writer_count": trace.writer_count,
                        "reader_count": trace.reader_count,
                        "writer_module_paths": [list(path) for path in trace.writer_module_paths],
                        "reader_module_paths": [list(path) for path in trace.reader_module_paths],
                    },
                )
            )

        return self._issues


def analyze_safety_paths(
    base_picture: BasePicture,
    debug: bool = False,
    unavailable_libraries: set[str] | None = None,
    analyzed_target_is_library: bool = False,
) -> SafetyPathReport:
    analyzer = SafetyPathAnalyzer(
        base_picture,
        unavailable_libraries=unavailable_libraries,
        analyzed_target_is_library=analyzed_target_is_library,
    )
    analyzer.run()
    return SafetyPathReport(
        basepicture_name=base_picture.header.name,
        issues=analyzer.issues,
        traces=analyzer.traces,
    )
