from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import cast

from sattline_parser.models.ast_model import BasePicture

from ._report_defaults import empty_issue_list, empty_object_summary_data
from ._wave2_support import InstanceParameterValue, collect_instance_parameter_values
from .framework import Issue


@dataclass
class ConfigDriftReport:
    name: str
    issues: list[Issue] = field(default_factory=empty_issue_list)
    summary_data: dict[str, object] = field(default_factory=empty_object_summary_data)

    def summary(self) -> str:
        lines = ["Report: Config drift", f"Target: {self.name}"]
        lines.append("Status: issues" if self.issues else "Status: ok")
        summary = self.summary_data.get("summary")
        summary_map = cast(dict[str, object], summary) if isinstance(summary, dict) else None
        raw_drift_count = summary_map.get("config_drift_count", 0) if summary_map is not None else 0
        drift_count = raw_drift_count if isinstance(raw_drift_count, int) else 0
        lines.append(f"Summary: {drift_count} drifting configuration groups")
        drift_keys = self.summary_data.get("config_drift")
        if isinstance(drift_keys, list) and drift_keys:
            lines.append(f"Config drift keys: {', '.join(str(item) for item in cast(list[object], drift_keys))}")
        if not self.issues:
            lines.append("No issues found.")
            return "\n".join(lines)

        lines.append("")
        lines.append("Findings:")
        for issue in self.issues:
            location = ".".join(issue.module_path or [self.name])
            lines.append(f"  - [{location}] {issue.message}")
        return "\n".join(lines)


class ConfigDriftAnalyzer:
    def __init__(
        self,
        base_picture: BasePicture,
        *,
        unavailable_libraries: set[str] | None = None,
    ) -> None:
        self._base_picture = base_picture
        self._unavailable_libraries = unavailable_libraries or set()
        self._issues: list[Issue] = []

    def run(self) -> ConfigDriftReport:
        by_moduletype: dict[str, dict[tuple[str, ...], dict[str, InstanceParameterValue]]] = defaultdict(dict)
        for value in collect_instance_parameter_values(
            self._base_picture,
            unavailable_libraries=self._unavailable_libraries,
        ):
            by_moduletype.setdefault(value.moduletype_label.casefold(), {}).setdefault(value.module_path, {})[
                value.parameter_name.casefold()
            ] = value

        drift_keys: list[str] = []
        for instance_map in by_moduletype.values():
            if len(instance_map) < 2:
                continue
            sample = next(iter(instance_map.values()), None)
            if sample is None:
                continue
            sample_value = next(iter(sample.values()), None)
            if sample_value is None:
                continue
            moduletype_label = sample_value.moduletype_label
            drifting_parameters = self._drifting_parameters(instance_map)
            if not drifting_parameters:
                continue
            drift_keys.extend(f"{moduletype_label}.{parameter}" for parameter in drifting_parameters)
            rendered_instances = ", ".join(
                self._render_instance(path, values, drifting_parameters)
                for path, values in sorted(instance_map.items())
            )
            self._issues.append(
                Issue(
                    kind="config_drift.instance_configuration",
                    message=(
                        f"Module type {moduletype_label!r} has drifting instance configuration for "
                        f"{', '.join(drifting_parameters)}: {rendered_instances}."
                    ),
                    module_path=list(sorted(instance_map)[0]),
                    data={
                        "moduletype": moduletype_label,
                        "drifting_parameters": drifting_parameters,
                        "instances": [
                            {
                                "path": list(path),
                                "parameters": {
                                    parameter: values[parameter.casefold()].value_display
                                    for parameter in drifting_parameters
                                    if parameter.casefold() in values
                                },
                            }
                            for path, values in sorted(instance_map.items())
                        ],
                    },
                )
            )

        drift_keys = sorted(set(drift_keys))
        return ConfigDriftReport(
            name=self._base_picture.header.name,
            issues=self._issues,
            summary_data={
                "kind": "sattlint.config_drift_summary",
                "schema_version": 1,
                "summary": {"config_drift_count": len(drift_keys)},
                "config_drift": drift_keys,
            },
        )

    def _drifting_parameters(
        self,
        instance_map: dict[tuple[str, ...], dict[str, InstanceParameterValue]],
    ) -> list[str]:
        parameters: dict[str, set[str]] = defaultdict(set)
        display_names: dict[str, str] = {}
        for values in instance_map.values():
            for key, value in values.items():
                parameters[key].add(value.value_signature)
                display_names.setdefault(key, value.parameter_name)
        return sorted(display_names[key] for key, signatures in parameters.items() if len(signatures) >= 2)

    def _render_instance(
        self,
        path: tuple[str, ...],
        values: dict[str, InstanceParameterValue],
        drifting_parameters: list[str],
    ) -> str:
        rendered_parameters = ", ".join(
            f"{parameter}={values[parameter.casefold()].value_display}"
            for parameter in drifting_parameters
            if parameter.casefold() in values
        )
        return f"{'.'.join(path)}({rendered_parameters})"


def analyze_config_drift(
    base_picture: BasePicture,
    *,
    unavailable_libraries: set[str] | None = None,
) -> ConfigDriftReport:
    return ConfigDriftAnalyzer(
        base_picture,
        unavailable_libraries=unavailable_libraries,
    ).run()
