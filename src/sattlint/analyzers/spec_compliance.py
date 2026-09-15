from __future__ import annotations

from collections.abc import Iterator
from collections.abc import Sequence as SequenceABC
from typing import Any

from sattline_parser.models.ast_model import (
    BasePicture,
    FrameModule,
    ModuleCode,
    ModuleTypeDef,
    ModuleTypeInstance,
    Sequence,
    SFCAlternative,
    SFCParallel,
    SFCStep,
    SFCSubsequence,
    SFCTransition,
    SFCTransitionSub,
    SingleModule,
)

from ..config.analysis import spec_compliance_prefixes
from .framework import Issue, SimpleReport
from .shared._walk_utils import iter_nested_modules
from .shared.variable_utils import matches_root_origin


class SpecComplianceAnalyzer:
    def __init__(
        self,
        base_picture: BasePicture,
        unavailable_libraries: set[str] | None = None,
        *,
        analyzed_target_is_library: bool = False,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.bp = base_picture
        self._unavailable_libraries = unavailable_libraries or set()
        self._analyzed_target_is_library = analyzed_target_is_library
        self._issues: list[Issue] = []
        prefixes = spec_compliance_prefixes(config)
        self._step_prefix = prefixes["step_prefix"]
        self._transition_prefix = prefixes["transition_prefix"]
        self._sequence_prefix = prefixes["sequence_prefix"]
        self._equation_prefix = prefixes["equation_prefix"]

    @property
    def issues(self) -> list[Issue]:
        return self._issues

    def run(self) -> list[Issue]:
        root_path = [self.bp.header.name]

        self._check_module_code(self.bp.modulecode, root_path)
        self._walk_modules(self.bp.submodules or [], root_path)

        for moduletype in self.bp.moduletype_defs or []:
            if not self._is_from_root_origin(
                getattr(moduletype, "origin_file", None),
                getattr(moduletype, "origin_lib", None),
            ):
                continue
            self._walk_moduletype_def(moduletype, root_path)

        return self._issues

    def _is_from_root_origin(self, origin_file: str | None, origin_lib: str | None = None) -> bool:
        return matches_root_origin(
            origin_file,
            getattr(self.bp, "origin_file", None),
            analyzed_target_is_library=self._analyzed_target_is_library,
            origin_lib=origin_lib,
            root_origin_lib=getattr(self.bp, "origin_lib", None),
        )

    def _walk_moduletype_def(
        self,
        moduletype: ModuleTypeDef,
        root_path: list[str],
    ) -> None:
        path = [*root_path, moduletype.name]
        self._check_module_code(moduletype.modulecode, path)
        self._walk_modules(moduletype.submodules or [], path)

    def _walk_modules(
        self,
        children: list[SingleModule | FrameModule | ModuleTypeInstance] | None,
        parent_path: list[str],
    ) -> None:
        for module, child_path in iter_nested_modules(children, parent_path=parent_path):
            if isinstance(module, (SingleModule, FrameModule)):
                self._check_module_code(module.modulecode, child_path)

    def _check_module_code(self, modulecode: ModuleCode | None, module_path: list[str]) -> None:
        if modulecode is None:
            return
        for equation in modulecode.equations or []:
            self._check_equation_block(equation, module_path)
        for sequence in modulecode.sequences or []:
            self._check_sequence(sequence, module_path)

    def _check_equation_block(self, equation: object, module_path: list[str]) -> None:
        if not self._equation_prefix:
            return
        name = getattr(equation, "name", None)
        if isinstance(name, str) and name and not name.startswith(self._equation_prefix):
            self._issues.append(
                Issue(
                    kind="spec.equation_block_prefix",
                    message=(
                        f"Equation block {name!r} must start with {self._equation_prefix!r} "
                        "according to the engineering spec."
                    ),
                    module_path=module_path.copy(),
                    data={
                        "equation": name,
                        "prefix": self._equation_prefix,
                        "site": f"EQ:{name}",
                        "context": name,
                    },
                )
            )

    def _check_sequence(self, sequence: Sequence, module_path: list[str]) -> None:
        if self._sequence_prefix and (sequence.name or "") and not sequence.name.startswith(self._sequence_prefix):
            self._issues.append(
                Issue(
                    kind="spec.sequence_name_prefix",
                    message=(
                        f"Sequence {sequence.name!r} must start with {self._sequence_prefix!r} "
                        "according to the engineering spec."
                    ),
                    module_path=module_path.copy(),
                    data={
                        "sequence": sequence.name,
                        "prefix": self._sequence_prefix,
                        "site": f"SQ:{sequence.name}",
                        "context": sequence.name,
                    },
                )
            )
        for node in self._iter_sequence_nodes(sequence.code or []):
            if isinstance(node, SFCStep) and not (node.name or "").startswith(self._step_prefix):
                self._issues.append(
                    Issue(
                        kind="spec.sequence_step_prefix",
                        message=(
                            f"Sequence step {node.name!r} must start with {self._step_prefix!r} "
                            "according to the engineering spec."
                        ),
                        module_path=module_path.copy(),
                        data={
                            "sequence": sequence.name,
                            "step": node.name,
                            "site": f"SQ:{sequence.name} > STEP:{node.name}",
                            "context": node.name,
                        },
                    )
                )
            if isinstance(node, SFCTransition):
                if not node.name:
                    self._issues.append(
                        Issue(
                            kind="spec.transition_name_missing",
                            message=(
                                f"A transition in sequence {sequence.name!r} is missing a name. All transitions must be named."
                            ),
                            module_path=module_path.copy(),
                            data={"sequence": sequence.name, "site": f"SQ:{sequence.name}"},
                        )
                    )
                    continue
                if not node.name.startswith(self._transition_prefix):
                    self._issues.append(
                        Issue(
                            kind="spec.transition_prefix",
                            message=(
                                f"Transition {node.name!r} must start with {self._transition_prefix!r} "
                                "according to the engineering spec."
                            ),
                            module_path=module_path.copy(),
                            data={
                                "sequence": sequence.name,
                                "transition": node.name,
                                "site": f"SQ:{sequence.name} > TRANS:{node.name}",
                                "context": node.name,
                            },
                        )
                    )

    def _iter_sequence_nodes(self, nodes: SequenceABC[object]) -> Iterator[object]:
        for node in nodes:
            yield node
            if isinstance(node, SFCAlternative | SFCParallel):
                for branch in node.branches or []:
                    yield from self._iter_sequence_nodes(branch)
            elif isinstance(node, SFCSubsequence | SFCTransitionSub):
                yield from self._iter_sequence_nodes(node.body or [])


def analyze_spec_compliance(
    base_picture: BasePicture,
    debug: bool = False,
    unavailable_libraries: set[str] | None = None,
    analyzed_target_is_library: bool = False,
    config: dict[str, Any] | None = None,
) -> SimpleReport:
    _ = debug
    analyzer = SpecComplianceAnalyzer(
        base_picture,
        unavailable_libraries=unavailable_libraries,
        analyzed_target_is_library=analyzed_target_is_library,
        config=config,
    )
    analyzer.run()
    return SimpleReport(name=base_picture.header.name, issues=analyzer.issues)
