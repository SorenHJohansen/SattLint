from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

try:
    from scripts import _ratchet_policy_context as ratchet_context
except ModuleNotFoundError:  # pragma: no cover - direct script execution resolves from scripts/
    import _ratchet_policy_context as ratchet_context


def path_is_within_roots(rel_path: str, roots: Sequence[str]) -> bool:
    return any(rel_path == root or rel_path.startswith(f"{root}/") for root in roots)


def typing_scope_expansion_roots(base_roots: Sequence[str], head_roots: Sequence[str]) -> tuple[str, ...]:
    return tuple(rel_root for rel_root in head_roots if not path_is_within_roots(rel_root, base_roots))


def typing_scope_python_files(repo_root: Path, roots: Sequence[str]) -> tuple[str, ...]:
    files: list[str] = []
    for root_text in roots:
        root_path = repo_root / root_text
        if not root_path.exists():
            raise ValueError(f"{ratchet_context.PYPROJECT_PATH} typing strict root {root_text!r} does not exist.")
        if root_path.is_file():
            if root_path.suffix.casefold() != ".py":
                raise ValueError(
                    f"{ratchet_context.PYPROJECT_PATH} typing strict root {root_text!r} must point to Python code."
                )
            files.append(root_text)
            continue
        files.extend(path.relative_to(repo_root).as_posix() for path in sorted(root_path.rglob("*.py")))
    return tuple(dict.fromkeys(files))


def typing_ratchet_state(
    text: str,
    label: str,
    *,
    allow_missing: bool = False,
) -> ratchet_context.TypingRatchetState | None:
    payload = ratchet_context.pyproject_payload(text, label)
    tool_section = payload.get("tool")
    if not isinstance(tool_section, dict):
        if allow_missing:
            return None
        raise ValueError(f"{label} is missing a [tool] table.")

    pyright_section = tool_section.get("pyright")
    sattlint_section = tool_section.get("sattlint")
    if not isinstance(pyright_section, dict) or not isinstance(sattlint_section, dict):
        if allow_missing:
            return None
        raise ValueError(f"{label} is missing typing ratchet configuration.")

    typing_ratchet_section = sattlint_section.get("typing_ratchet")
    if not isinstance(typing_ratchet_section, dict):
        if allow_missing:
            return None
        raise ValueError(f"{label} is missing [tool.sattlint.typing_ratchet].")

    type_checking_mode = pyright_section.get("typeCheckingMode", "off")
    strict_paths = ratchet_context.normalized_string_list(
        pyright_section.get("strict", []), f"{label} [tool.pyright].strict"
    )
    global_strict = type_checking_mode == "strict" and not strict_paths
    strict_roots = ratchet_context.normalized_string_list(
        typing_ratchet_section.get("strict_roots", []),
        f"{label} [tool.sattlint.typing_ratchet].strict_roots",
    )
    debt_allowlist = ratchet_context.normalized_string_list(
        typing_ratchet_section.get("debt_allowlist", []),
        f"{label} [tool.sattlint.typing_ratchet].debt_allowlist",
    )
    if not strict_roots and not global_strict:
        raise ValueError(f"{label} typing ratchet strict_roots must not be empty.")

    return ratchet_context.TypingRatchetState(
        strict_paths=strict_paths,
        strict_roots=strict_roots,
        debt_allowlist=debt_allowlist,
        global_strict=global_strict,
    )


def typing_ratchet_state_errors(
    *,
    repo_root: Path,
    added_files: Sequence[str],
    changed_files: Sequence[str] = (),
    base_state: ratchet_context.TypingRatchetState | None = None,
    state: ratchet_context.TypingRatchetState,
) -> list[str]:
    errors: list[str] = []
    strict_paths = set(state.strict_paths)
    debt_allowlist = set(state.debt_allowlist)
    scope_files = set(typing_scope_python_files(repo_root, state.strict_roots))

    overlap = sorted(strict_paths & debt_allowlist)
    if overlap:
        errors.append("Pyright strict paths overlap the typing debt allowlist: " + ", ".join(overlap) + ".")

    strict_outside_scope = sorted(strict_paths - scope_files)
    if strict_outside_scope:
        errors.append(
            "Pyright strict paths fall outside the typing ratchet scope or reference missing files: "
            + ", ".join(strict_outside_scope)
            + "."
        )

    debt_outside_scope = sorted(debt_allowlist - scope_files)
    if debt_outside_scope:
        errors.append(
            "Typing debt allowlist paths fall outside the typing ratchet scope or reference missing files: "
            + ", ".join(debt_outside_scope)
            + "."
        )

    if state.global_strict:
        uncovered_scope_files: set[str] = set()
    else:
        uncovered_scope_files = set(scope_files - strict_paths - debt_allowlist)
    if base_state is None:
        if uncovered_scope_files:
            errors.append(
                "Typing ratchet scope has uncovered Python files: " + ", ".join(sorted(uncovered_scope_files)) + "."
            )
    else:
        if base_state.global_strict:
            base_uncovered_scope_files: set[str] = set()
        else:
            base_uncovered_scope_files = (
                set(typing_scope_python_files(repo_root, base_state.strict_roots))
                - set(base_state.strict_paths)
                - set(base_state.debt_allowlist)
            )
        newly_uncovered_scope_files = sorted(uncovered_scope_files - base_uncovered_scope_files)
        if newly_uncovered_scope_files:
            errors.append(
                "Typing ratchet scope gained newly uncovered Python files: "
                + ", ".join(newly_uncovered_scope_files)
                + "."
            )

    added_scope_files = sorted(
        rel_path
        for rel_path in added_files
        if rel_path.endswith(".py") and path_is_within_roots(rel_path, state.strict_roots)
    )
    added_scope_file_set = set(added_scope_files)
    for rel_path in added_scope_files:
        if rel_path in debt_allowlist:
            errors.append(
                "Typing debt allowlist grew with a new scoped file: "
                f"{rel_path}. New files under the strict scope must land in tool.pyright.strict."
            )
        elif not state.global_strict and rel_path not in strict_paths:
            errors.append(f"New file under the typing strict scope is not covered by tool.pyright.strict: {rel_path}.")

    touched_scope_debt = sorted(
        rel_path
        for rel_path in changed_files
        if rel_path.endswith(".py")
        and rel_path not in added_scope_file_set
        and rel_path in debt_allowlist
        and path_is_within_roots(rel_path, state.strict_roots)
    )
    for rel_path in touched_scope_debt:
        if (
            base_state is not None
            and rel_path in base_state.debt_allowlist
            and typing_scope_expansion_roots(base_state.strict_roots, state.strict_roots)
        ):
            continue
        errors.append(
            "Touched file under the typing strict scope remains in typing debt allowlist: "
            f"{rel_path}. Touched files under the strict scope must move to tool.pyright.strict."
        )

    return errors


def typing_ratchet_backslide_errors(
    base_state: ratchet_context.TypingRatchetState | None,
    head_state: ratchet_context.TypingRatchetState,
) -> list[str]:
    if base_state is None:
        return []

    errors: list[str] = []
    base_roots = set(base_state.strict_roots)
    head_roots = set(head_state.strict_roots)
    base_strict = set(base_state.strict_paths)
    head_strict = set(head_state.strict_paths)
    base_debt = set(base_state.debt_allowlist)
    head_debt = set(head_state.debt_allowlist)
    expanded_roots = typing_scope_expansion_roots(base_state.strict_roots, head_state.strict_roots)

    for rel_root in sorted(
        rel_root for rel_root in base_roots - head_roots if not path_is_within_roots(rel_root, head_state.strict_roots)
    ):
        errors.append(f"Typing strict scope shrank: removed strict root {rel_root}.")

    for rel_path in sorted(base_strict - head_strict):
        if head_state.global_strict:
            continue
        if rel_path in head_debt:
            errors.append(
                f"Pyright strict coverage moved into typing debt: {rel_path}. Fix types first; do not rebaseline."
            )
        else:
            errors.append(f"Pyright strict coverage removed: {rel_path}. Fix types first; do not rebaseline.")

    for rel_path in sorted(head_debt - base_debt):
        if path_is_within_roots(rel_path, expanded_roots) and not path_is_within_roots(
            rel_path, base_state.strict_roots
        ):
            continue
        errors.append(f"Typing debt allowlist grew: {rel_path}. Fix types first; do not add new exceptions.")

    return errors
