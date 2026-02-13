from __future__ import annotations
from dataclasses import dataclass, field
from typing import TypeAlias

from ..analyzers.framework import Issue, format_report_header


WriteLocation: TypeAlias = tuple[tuple[str, ...], int]
WriteField: TypeAlias = tuple[str, tuple[WriteLocation, ...]]
WriteFields: TypeAlias = tuple[WriteField, ...]


@dataclass(frozen=True)
class MMSInterfaceHit:
    module_path: list[str]
    moduletype_name: str
    parameter_name: str
    source_variable: str
    write_fields: WriteFields = ()
    write_note: str | None = None


@dataclass
class MMSInterfaceReport:
    basepicture_name: str
    hits: list[MMSInterfaceHit]
    issues: list[Issue] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.basepicture_name

    @property
    def unique_variables(self) -> set[str]:
        return {h.source_variable.casefold() for h in self.hits}

    def summary(self) -> str:
        if not self.hits:
            lines = format_report_header(
                "MMS interface mappings",
                self.basepicture_name,
                status="ok",
            )
            lines.append("No mappings found.")
            return "\n".join(lines)

        def _merge_write_counts(
            hits: list[MMSInterfaceHit],
        ) -> tuple[int, dict[str, int], dict[tuple[str, tuple[str, ...]], int]]:
            dedup: dict[tuple[str, tuple[str, ...]], int] = {}
            for hit in hits:
                for field_path, locations in hit.write_fields:
                    field_label = field_path or "<whole>"
                    for path, count in locations:
                        key = (field_label.casefold(), tuple(path))
                        dedup[key] = max(dedup.get(key, 0), count)

            field_totals: dict[str, int] = {}
            total = 0
            for (field_label, _path), count in dedup.items():
                field_totals[field_label] = field_totals.get(field_label, 0) + count
                total += count

            return total, field_totals, dedup

        hits_by_var: dict[str, list[MMSInterfaceHit]] = {}
        for hit in self.hits:
            hits_by_var.setdefault(hit.source_variable.casefold(), []).append(hit)

        lines = format_report_header(
            "MMS interface mappings",
            self.basepicture_name,
            status="data",
        )
        lines.extend(
            [
                f"Total mappings: {len(self.hits)}",
                f"Unique variables: {len(self.unique_variables)}",
                "",
            ]
        )

        ranked_vars = []
        for key, var_hits in hits_by_var.items():
            total, field_totals, _dedup = _merge_write_counts(var_hits)
            display_name = var_hits[0].source_variable
            ranked_vars.append((total, display_name, field_totals))

        ranked_vars.sort(key=lambda item: (-item[0], item[1].casefold()))

        lines.append("Most-written MMS variables:")
        for total, display_name, field_totals in ranked_vars[:10]:
            if total == 0:
                lines.append(f"  - {display_name}: 0 writes")
                continue

            top_fields = sorted(field_totals.items(), key=lambda item: (-item[1], item[0]))[:3]
            top_fields_str = ", ".join(
                f"{field} ({count}x)" for field, count in top_fields
            )
            lines.append(
                f"  - {display_name}: {total} writes (top fields: {top_fields_str})"
            )

        lines.append("")
        lines.append("Details by MMS variable:")

        for _total, display_name, _field_totals in ranked_vars:
            var_hits = hits_by_var[display_name.casefold()]
            total, _field_totals, dedup = _merge_write_counts(var_hits)
            lines.append("")
            lines.append(f"  Variable: {display_name}")
            lines.append(f"    Total writes: {total}")
            lines.append("    Mappings:")
            for hit in sorted(
                var_hits,
                key=lambda h: (".".join(h.module_path), h.parameter_name.casefold()),
            ):
                location = ".".join(hit.module_path)
                lines.append(
                    f"      - {location} | {hit.moduletype_name}.{hit.parameter_name}"
                )

            if dedup:
                lines.append("    Field writes:")
                grouped_paths: dict[str, list[tuple[tuple[str, ...], int]]] = {}
                for (field_label, path), count in sorted(
                    dedup.items(), key=lambda item: (item[0][0], ".".join(item[0][1]))
                ):
                    grouped_paths.setdefault(field_label, []).append((path, count))

                for field_label, locations in grouped_paths.items():
                    write_parts = []
                    for path, count in locations:
                        path_str = ".".join(path)
                        write_parts.append(
                            f"{path_str} ({count}x)" if count > 1 else path_str
                        )
                    lines.append(f"      - {field_label} => {', '.join(write_parts)}")
            else:
                note = next((h.write_note for h in var_hits if h.write_note), None)
                lines.append(f"    Field writes: {note or 'none'}")

        return "\n".join(lines)
