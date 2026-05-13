from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from sattline_parser.models.ast_model import BasePicture, ModuleCode, Variable

from ..grammar import constants as const
from ._wave2_support import iter_read_variable_names, iter_statement_sites, root_variable_name, walk_module_scopes
from .framework import Issue


@dataclass
class SignalLifecycleReport:
    name: str
    issues: list[Issue] = field(default_factory=list)
    summary_data: dict[str, int] = field(default_factory=dict)

    def summary(self) -> str:
        lines = ["Report: Signal lifecycle", f"Target: {self.name}"]
        lines.append("Status: issues" if self.issues else "Status: ok")
        lines.append(
            "Summary: "
            f"{self.summary_data.get('written_then_read_count', 0)} written-then-read, "
            f"{self.summary_data.get('read_before_write_count', 0)} read-before-write, "
            f"{self.summary_data.get('unconsumed_write_count', 0)} unconsumed writes"
        )
        if not self.issues:
            lines.append("No issues found.")
            return "\n".join(lines)

        lines.append("")
        lines.append("Findings:")
        for issue in self.issues:
            location = ".".join(issue.module_path or [self.name])
            lines.append(f"  - [{location}] {issue.message}")
        return "\n".join(lines)


class SignalLifecycleAnalyzer:
    def __init__(self, base_picture: BasePicture) -> None:
        self._base_picture = base_picture
        self._issues: list[Issue] = []
        self._written_then_read_count = 0
        self._read_before_write_count = 0
        self._unconsumed_write_count = 0

    def run(self) -> SignalLifecycleReport:
        for scope in walk_module_scopes(self._base_picture):
            self._analyze_scope(scope.module_path, scope.env, scope.modulecode)
        return SignalLifecycleReport(
            name=self._base_picture.header.name,
            issues=self._issues,
            summary_data={
                "written_then_read_count": self._written_then_read_count,
                "read_before_write_count": self._read_before_write_count,
                "unconsumed_write_count": self._unconsumed_write_count,
            },
        )

    def _analyze_scope(
        self,
        module_path: tuple[str, ...],
        env: dict[str, Variable],
        modulecode: ModuleCode | None,
    ) -> None:
        if modulecode is None:
            return

        written = {name for name, variable in env.items() if variable.init_value is not None}
        explicit_writes: set[str] = set()
        read_after_write: set[str] = set()
        read_before_write: dict[str, set[str]] = defaultdict(set)
        write_sites: dict[str, set[str]] = defaultdict(set)

        for site in iter_statement_sites(modulecode):
            written = self._process_node(
                site.statement,
                written=written,
                env=env,
                explicit_writes=explicit_writes,
                read_after_write=read_after_write,
                read_before_write=read_before_write,
                write_sites=write_sites,
                site_label=site.label,
            )

        for key in sorted(read_before_write):
            variable = env[key]
            self._read_before_write_count += 1
            self._issues.append(
                Issue(
                    kind="signal_lifecycle.read_before_write",
                    message=(
                        f"Signal {variable.name!r} may be consumed before any known write in "
                        f"{', '.join(sorted(read_before_write[key]))}."
                    ),
                    module_path=list(module_path),
                    data={"signal": variable.name, "sites": sorted(read_before_write[key])},
                )
            )

        for key in sorted(explicit_writes - read_after_write):
            variable = env[key]
            self._unconsumed_write_count += 1
            self._issues.append(
                Issue(
                    kind="signal_lifecycle.unconsumed_write",
                    message=(
                        f"Signal {variable.name!r} is written but never consumed later in this scope; "
                        f"writes appear in {', '.join(sorted(write_sites[key]))}."
                    ),
                    module_path=list(module_path),
                    data={"signal": variable.name, "sites": sorted(write_sites[key])},
                )
            )

        self._written_then_read_count += len(read_after_write)

    def _process_node(
        self,
        node: Any,
        *,
        written: set[str],
        env: dict[str, Variable],
        explicit_writes: set[str],
        read_after_write: set[str],
        read_before_write: dict[str, set[str]],
        write_sites: dict[str, set[str]],
        site_label: str,
    ) -> set[str]:
        if hasattr(node, "data") and getattr(node, "data", None) == const.KEY_STATEMENT:
            current = set(written)
            for child in getattr(node, "children", []):
                current = self._process_node(
                    child,
                    written=current,
                    env=env,
                    explicit_writes=explicit_writes,
                    read_after_write=read_after_write,
                    read_before_write=read_before_write,
                    write_sites=write_sites,
                    site_label=site_label,
                )
            return current

        if isinstance(node, tuple) and node:
            tag = node[0]
            if tag == const.KEY_ASSIGN and len(node) >= 3:
                _assign, target, expr = node[:3]
                self._mark_reads(
                    expr,
                    written=written,
                    env=env,
                    explicit_writes=explicit_writes,
                    read_after_write=read_after_write,
                    read_before_write=read_before_write,
                    site_label=site_label,
                )
                target_name = root_variable_name(target)
                if target_name is None:
                    return written
                key = target_name.casefold()
                if key not in env:
                    return written
                next_written = set(written)
                next_written.add(key)
                explicit_writes.add(key)
                write_sites[key].add(site_label)
                return next_written

            if tag == const.GRAMMAR_VALUE_IF and len(node) == 3:
                _if_tag, branches, else_block = node
                branch_written: list[set[str]] = []
                for condition, branch_statements in branches or []:
                    self._mark_reads(
                        condition,
                        written=written,
                        env=env,
                        explicit_writes=explicit_writes,
                        read_after_write=read_after_write,
                        read_before_write=read_before_write,
                        site_label=site_label,
                    )
                    branch_state = set(written)
                    for statement in branch_statements or []:
                        branch_state = self._process_node(
                            statement,
                            written=branch_state,
                            env=env,
                            explicit_writes=explicit_writes,
                            read_after_write=read_after_write,
                            read_before_write=read_before_write,
                            write_sites=write_sites,
                            site_label=site_label,
                        )
                    branch_written.append(branch_state)
                else_state = set(written)
                for statement in else_block or []:
                    else_state = self._process_node(
                        statement,
                        written=else_state,
                        env=env,
                        explicit_writes=explicit_writes,
                        read_after_write=read_after_write,
                        read_before_write=read_before_write,
                        write_sites=write_sites,
                        site_label=site_label,
                    )
                branch_written.append(else_state)
                return set.intersection(*branch_written) if branch_written else set(written)

        self._mark_reads(
            node,
            written=written,
            env=env,
            explicit_writes=explicit_writes,
            read_after_write=read_after_write,
            read_before_write=read_before_write,
            site_label=site_label,
        )
        return written

    def _mark_reads(
        self,
        node: Any,
        *,
        written: set[str],
        env: dict[str, Variable],
        explicit_writes: set[str],
        read_after_write: set[str],
        read_before_write: dict[str, set[str]],
        site_label: str,
    ) -> None:
        for name in iter_read_variable_names(node):
            key = name.casefold()
            if key not in env:
                continue
            if key not in written:
                read_before_write[key].add(site_label)
                continue
            if key in explicit_writes:
                read_after_write.add(key)


def analyze_signal_lifecycle(base_picture: BasePicture) -> SignalLifecycleReport:
    return SignalLifecycleAnalyzer(base_picture).run()
