from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from sattline_parser.models.ast_model import (
    BasePicture,
    FrameModule,
    ModuleCode,
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

from ..analyzers.dataflow import DataflowAnalyzer, ScalarValue, StateMap, _is_scalar_value
from ..core.semantic import SemanticSnapshot
from ..resolution.common import resolve_moduletype_def_strict
from ..resolution.scope import ScopeContext
from ._runtime_models import ScanSnapshot, SimulationResult


@dataclass(frozen=True)
class _SimulationTarget:
    module_path: list[str]
    modulecode: ModuleCode | None
    context: ScopeContext
    state: StateMap


def simulate_snapshot_target(
    snapshot: SemanticSnapshot,
    *,
    module_name: str,
    mode: str,
    max_scans: int,
) -> SimulationResult:
    return simulate_module(
        snapshot.base_picture,
        module_name=module_name,
        mode=mode,
        max_scans=max_scans,
        unavailable_libraries=getattr(snapshot.project_graph, "unavailable_libraries", set()),
    )


def simulate_module(
    base_picture: BasePicture,
    *,
    module_name: str,
    mode: str = "steady-state",
    max_scans: int = 25,
    unavailable_libraries: set[str] | None = None,
) -> SimulationResult:
    if max_scans <= 0:
        raise ValueError("max_scans must be positive")
    if mode != "steady-state":
        raise ValueError(f"Unsupported simulation mode: {mode}")

    analyzer = DataflowAnalyzer(base_picture, unavailable_libraries=unavailable_libraries)
    target = _select_target(base_picture, analyzer, module_name)
    if target.modulecode is None or not (target.modulecode.sequences or []):
        raise ValueError(f"Target '{module_name}' has no SFC structure to simulate")

    step_lookup = _collect_steps(target.modulecode)
    active_steps = _initial_active_steps(target.modulecode)
    if not active_steps:
        raise ValueError(f"Target '{module_name}' has no active SFC entry steps to simulate")

    previous_active_steps: set[str] = set()
    current_state = target.state.copy()
    snapshots: list[ScanSnapshot] = []
    seen_signatures: dict[tuple[tuple[str, ...], tuple[tuple[str, ScalarValue], ...]], int] = {}

    for scan in range(1, max_scans + 1):
        current_state = _run_step_phase(
            analyzer,
            active_steps - previous_active_steps,
            step_lookup,
            target.context,
            target.module_path,
            current_state,
            phase="enter",
        )
        current_state = _run_step_phase(
            analyzer,
            active_steps,
            step_lookup,
            target.context,
            target.module_path,
            current_state,
            phase="active",
        )

        next_active_steps, transition_fires = _advance_sequences(
            analyzer,
            target.modulecode.sequences or [],
            active_steps,
            target.context,
            target.module_path,
            current_state,
        )

        current_state = _run_step_phase(
            analyzer,
            active_steps - next_active_steps,
            step_lookup,
            target.context,
            target.module_path,
            current_state,
            phase="exit",
        )
        current_state = _run_step_phase(
            analyzer,
            next_active_steps - active_steps,
            step_lookup,
            target.context,
            target.module_path,
            current_state,
            phase="enter",
        )

        current_state = _run_equations(analyzer, target, current_state)
        exported_state = _export_state(current_state, target)
        snapshot = ScanSnapshot(
            scan=scan,
            active_steps=sorted(next_active_steps),
            state=exported_state,
            transition_fires=sorted(transition_fires),
        )
        snapshots.append(snapshot)

        signature = (
            tuple(snapshot.active_steps),
            tuple((key, snapshot.state[key]) for key in sorted(snapshot.state)),
        )
        prior_scan = seen_signatures.get(signature)
        if prior_scan is not None:
            if prior_scan == scan - 1:
                return SimulationResult(
                    target=module_name,
                    mode=mode,
                    steady_state_reached=True,
                    cycle_detected=False,
                    scan_budget_exhausted=False,
                    outcome="steady-state",
                    total_scans=scan,
                    cycle_start_scan=None,
                    cycle_length=None,
                    snapshots=snapshots,
                )
            return SimulationResult(
                target=module_name,
                mode=mode,
                steady_state_reached=False,
                cycle_detected=True,
                scan_budget_exhausted=False,
                outcome="cycle",
                total_scans=scan,
                cycle_start_scan=prior_scan,
                cycle_length=scan - prior_scan,
                snapshots=snapshots,
            )

        seen_signatures[signature] = scan
        previous_active_steps = active_steps
        active_steps = next_active_steps

    return SimulationResult(
        target=module_name,
        mode=mode,
        steady_state_reached=False,
        cycle_detected=False,
        scan_budget_exhausted=True,
        outcome="scan-budget-exhausted",
        total_scans=max_scans,
        cycle_start_scan=None,
        cycle_length=None,
        snapshots=snapshots,
    )


def _select_target(base_picture: BasePicture, analyzer: DataflowAnalyzer, module_name: str) -> _SimulationTarget:
    matches: list[_SimulationTarget] = []
    query = module_name.casefold()
    for target in _iter_targets(base_picture, analyzer):
        canonical = ".".join(target.module_path)
        if query == canonical.casefold() or query == target.module_path[-1].casefold():
            matches.append(target)
    if not matches:
        raise ValueError(f"Could not resolve simulation target '{module_name}'")
    if len(matches) > 1:
        raise ValueError(f"Simulation target '{module_name}' is ambiguous")
    return matches[0]


def _iter_targets(base_picture: BasePicture, analyzer: DataflowAnalyzer):
    root_path = [base_picture.header.name]
    root_variables = list(base_picture.localvariables or [])
    root_context = analyzer._build_scope_context(
        root_variables,
        param_mappings={},
        module_path=root_path,
        current_library=getattr(base_picture, "origin_lib", None),
        parent_context=None,
    )
    root_state = analyzer._seed_state({}, root_path, root_variables)
    yield _SimulationTarget(root_path, base_picture.modulecode, root_context, root_state)
    yield from _iter_child_targets(
        base_picture,
        analyzer,
        base_picture.submodules or [],
        root_context,
        root_path,
        root_state,
    )


def _iter_child_targets(
    base_picture: BasePicture,
    analyzer: DataflowAnalyzer,
    modules: list[SingleModule | FrameModule | ModuleTypeInstance],
    parent_context: ScopeContext,
    parent_path: list[str],
    state: StateMap,
):
    for child in modules:
        child_path = [*parent_path, child.header.name]
        if isinstance(child, SingleModule):
            child_context = analyzer._build_single_context(child, parent_context, child_path)
            child_state = analyzer._seed_state(
                state,
                child_path,
                [*(child.moduleparameters or []), *(child.localvariables or [])],
            )
            yield _SimulationTarget(child_path, child.modulecode, child_context, child_state)
            yield from _iter_child_targets(
                base_picture,
                analyzer,
                child.submodules or [],
                child_context,
                child_path,
                child_state,
            )
            continue

        if isinstance(child, FrameModule):
            frame_context = ScopeContext(
                env=parent_context.env,
                param_mappings=parent_context.param_mappings,
                module_path=child_path.copy(),
                display_module_path=child_path.copy(),
                current_library=parent_context.current_library,
                parent_context=parent_context,
            )
            frame_state = state.copy()
            yield _SimulationTarget(child_path, child.modulecode, frame_context, frame_state)
            yield from _iter_child_targets(
                base_picture,
                analyzer,
                child.submodules or [],
                frame_context,
                child_path,
                frame_state,
            )
            continue

        try:
            moduletype = resolve_moduletype_def_strict(
                base_picture,
                child.moduletype_name,
                current_library=parent_context.current_library,
                unavailable_libraries=analyzer._unavailable_libraries,
            )
        except ValueError:
            continue

        typedef_context = analyzer._build_typedef_context(moduletype, child, parent_context, child_path)
        typedef_state = analyzer._seed_state(
            state,
            child_path,
            [*(moduletype.moduleparameters or []), *(moduletype.localvariables or [])],
        )
        yield _SimulationTarget(child_path, moduletype.modulecode, typedef_context, typedef_state)
        yield from _iter_child_targets(
            base_picture,
            analyzer,
            moduletype.submodules or [],
            typedef_context,
            child_path,
            typedef_state,
        )


def _collect_steps(modulecode: ModuleCode) -> dict[str, SFCStep]:
    steps: dict[str, SFCStep] = {}
    for sequence in modulecode.sequences or []:
        _collect_steps_from_nodes(sequence.code or [], f"{sequence.name}.", steps)
    return steps


def _collect_steps_from_nodes(nodes: list[Any], prefix: str, steps: dict[str, SFCStep]) -> None:
    for node in nodes:
        if isinstance(node, SFCStep):
            steps[f"{prefix}{node.name}"] = node
            continue
        if isinstance(node, SFCParallel | SFCAlternative):
            for branch in node.branches or []:
                _collect_steps_from_nodes(branch, prefix, steps)
            continue
        if isinstance(node, SFCSubsequence | SFCTransitionSub):
            _collect_steps_from_nodes(node.body or [], f"{prefix}{node.name}.", steps)


def _initial_active_steps(modulecode: ModuleCode) -> set[str]:
    active_steps: set[str] = set()
    for sequence in modulecode.sequences or []:
        active_steps.update(_collect_entry_steps(sequence.code or [], f"{sequence.name}."))
    return active_steps


def _collect_entry_steps(nodes: list[Any], prefix: str) -> set[str]:
    for node in nodes:
        if isinstance(node, SFCStep):
            return {f"{prefix}{node.name}"}
        if isinstance(node, SFCParallel | SFCAlternative):
            active: set[str] = set()
            for branch in node.branches or []:
                active.update(_collect_entry_steps(branch, prefix))
            if active:
                return active
            continue
        if isinstance(node, SFCSubsequence | SFCTransitionSub):
            active = _collect_entry_steps(node.body or [], f"{prefix}{node.name}.")
            if active:
                return active
            continue
    return set()


def _run_step_phase(
    analyzer: DataflowAnalyzer,
    step_labels: set[str],
    step_lookup: dict[str, SFCStep],
    context: ScopeContext,
    module_path: list[str],
    state: StateMap,
    *,
    phase: str,
) -> StateMap:
    current_state = state
    for step_label in sorted(step_labels):
        step = step_lookup.get(step_label)
        if step is None:
            continue
        current_state = analyzer._analyze_block(
            getattr(step.code, phase) or [],
            context,
            module_path,
            current_state,
        )
    return current_state


def _advance_sequences(
    analyzer: DataflowAnalyzer,
    sequences: list[Sequence],
    active_steps: set[str],
    context: ScopeContext,
    module_path: list[str],
    state: StateMap,
) -> tuple[set[str], set[str]]:
    next_active: set[str] = set()
    transition_fires: set[str] = set()
    for sequence in sequences:
        sequence_active, sequence_fires = _advance_nodes(
            analyzer,
            sequence.code or [],
            f"{sequence.name}.",
            active_steps,
            context,
            module_path,
            state,
        )
        next_active.update(sequence_active)
        transition_fires.update(sequence_fires)
    return next_active, transition_fires


def _advance_nodes(
    analyzer: DataflowAnalyzer,
    nodes: list[Any],
    prefix: str,
    active_steps: set[str],
    context: ScopeContext,
    module_path: list[str],
    state: StateMap,
) -> tuple[set[str], set[str]]:
    next_active: set[str] = set()
    transition_fires: set[str] = set()

    for index, node in enumerate(nodes):
        if isinstance(node, SFCStep):
            label = f"{prefix}{node.name}"
            if label not in active_steps:
                continue
            transition = (
                nodes[index + 1] if index + 1 < len(nodes) and isinstance(nodes[index + 1], SFCTransition) else None
            )
            if transition is None:
                next_active.add(label)
                continue
            condition = analyzer._evaluate_condition(transition.condition, context, module_path, state)
            if condition is True:
                transition_fires.add(transition.name or label)
                next_active.update(_collect_entry_steps(nodes[index + 2 :], prefix) or {label})
            else:
                next_active.add(label)
            continue

        if isinstance(node, SFCParallel | SFCAlternative):
            for branch in node.branches or []:
                branch_active, branch_fires = _advance_nodes(
                    analyzer,
                    branch,
                    prefix,
                    active_steps,
                    context,
                    module_path,
                    state,
                )
                next_active.update(branch_active)
                transition_fires.update(branch_fires)
            continue

        if isinstance(node, SFCSubsequence | SFCTransitionSub):
            branch_active, branch_fires = _advance_nodes(
                analyzer,
                node.body or [],
                f"{prefix}{node.name}.",
                active_steps,
                context,
                module_path,
                state,
            )
            next_active.update(branch_active)
            transition_fires.update(branch_fires)

    return next_active, transition_fires


def _run_equations(analyzer: DataflowAnalyzer, target: _SimulationTarget, state: StateMap) -> StateMap:
    current_state = state
    if target.modulecode is None:
        return current_state
    for equation in target.modulecode.equations or []:
        current_state = analyzer._analyze_block(equation.code or [], target.context, target.module_path, current_state)
    return current_state


def _export_state(state: StateMap, target: _SimulationTarget) -> dict[str, ScalarValue]:
    exported: dict[str, ScalarValue] = {}
    path_prefix = tuple(segment.casefold() for segment in target.module_path)
    for key, value in state.items():
        if not isinstance(key, tuple):
            continue
        if key[: len(path_prefix)] != path_prefix:
            continue
        if any(segment in {"__old__", "__pending__"} for segment in key):
            continue
        if not _is_scalar_value(value):
            continue
        relative_key = ".".join(key[len(path_prefix) :])
        if not relative_key:
            continue
        exported[_display_state_name(relative_key, target.context)] = cast(ScalarValue, value)
    return {name: exported[name] for name in sorted(exported)}


def _display_state_name(relative_key: str, context: ScopeContext) -> str:
    head, *tail = relative_key.split(".")
    variable = context.env.get(head)
    display_head = variable.name if variable is not None else head
    if not tail:
        return display_head
    return ".".join([display_head, *tail])
