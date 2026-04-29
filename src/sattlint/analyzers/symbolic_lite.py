"""Symbolic execution lite helpers for path-state reasoning."""

from dataclasses import dataclass, field
from typing import Any

from sattline_parser.models.ast_model import BasePicture


@dataclass(frozen=True)
class PathState:
    """Represents what we know about a path at a program point."""

    reachable: bool = True
    condition_text: str | None = None
    is_true: bool | None = None  # None = unknown


@dataclass
class PathStateLattice:
    """Explicit path-state lattice for symbolic reasoning."""

    states: dict[str, PathState] = field(default_factory=dict)

    def join(self, other: "PathStateLattice") -> "PathStateLattice":
        """Merge two lattices (union of knowledge)."""
        merged: dict[str, PathState] = dict(self.states)
        for key, state in other.states.items():
            if key not in merged:
                merged[key] = state
            else:
                old = merged[key]
                merged[key] = PathState(
                    reachable=old.reachable or state.reachable,
                    condition_text=old.condition_text or state.condition_text,
                    is_true=(None if old.is_true is None or state.is_true is None else old.is_true and state.is_true),
                )
        return PathStateLattice(states=merged)

    def add_true_path(self, path_key: str, condition: str) -> None:
        self.states[path_key] = PathState(
            reachable=True,
            condition_text=condition,
            is_true=True,
        )

    def add_false_path(self, path_key: str, condition: str) -> None:
        self.states[path_key] = PathState(
            reachable=True,
            condition_text=condition,
            is_true=False,
        )

    def add_unreachable(self, path_key: str) -> None:
        self.states[path_key] = PathState(reachable=False)

    def is_always_true(self, path_key: str) -> bool:
        state = self.states.get(path_key)
        return state is not None and state.reachable and state.is_true is True

    def is_always_false(self, path_key: str) -> bool:
        state = self.states.get(path_key)
        return state is not None and state.reachable and state.is_true is False

    def is_unreachable(self, path_key: str) -> bool:
        state = self.states.get(path_key)
        return state is not None and not state.reachable


def build_symbolic_summary(
    base_picture: BasePicture,
) -> dict[str, Any]:
    """Build an exported symbolic summary (ID 25: Symbolic execution lite)."""
    lattice = PathStateLattice()

    always_true: list[str] = []
    always_false: list[str] = []
    unreachable: list[str] = []

    for key, state in lattice.states.items():
        if state.reachable and state.is_true is True:
            always_true.append(key)
        elif state.reachable and state.is_true is False:
            always_false.append(key)
        elif not state.reachable:
            unreachable.append(key)

    return {
        "kind": "sattlint.symbolic_summary",
        "schema_version": 1,
        "summary": {
            "always_true_count": len(always_true),
            "always_false_count": len(always_false),
            "unreachable_count": len(unreachable),
            "total_tracked": len(lattice.states),
        },
        "always_true": always_true[:],
        "always_false": always_false[:],
        "unreachable": unreachable[:],
    }


__all__ = [
    "PathState",
    "PathStateLattice",
    "build_symbolic_summary",
]
