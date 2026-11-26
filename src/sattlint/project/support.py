from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypeGuard, cast

from ..config.types import ConfigDict
from ..models.project_graph import ProjectFailure
from ..utils.casefolding import dedupe_unit_names, unit_equal, unit_key

type LoadFailureKind = Literal["load", "read", "parse"]

#: How many entries one failure report shows before it states the remainder.
#: Kept in step with the validation-warning limit so one broken graph never
#: turns a single error into a wall of text.
TARGET_FAILURE_DETAIL_LIMIT = 12

_PICTURE_DISPLAY_WARNING_RE = re.compile(
    r"^PictureDisplay in module '([^']+)' path ('.*?') could not be resolved: (.+)$"
)

#: Prefix for a program that failed parsing or transformation. The failure
#: carries an optional source position.
PARSE_FAILURE_MARKER = " parse/transform error: "
#: Prefix for a target the loader could not load at all. There is no source
#: position; the detail names the failing program and its dependency edge.
LOAD_FAILURE_MARKER = " load error: "


@dataclass(frozen=True, slots=True)
class LoadFailureDetail:
    """One failed target's human message and its typed fields.

    ``kind`` distinguishes a resolution failure, an unreadable file, and a
    parse failure. ``line`` and ``column`` are only set when the parser
    reported them.
    """

    message: str
    kind: LoadFailureKind = "load"
    path: str | None = None
    line: int | None = None
    column: int | None = None


def _failure_cause(exc: BaseException) -> BaseException | None:
    return exc.__cause__ if exc.__cause__ is not None else exc.__context__


def _failure_position(
    exc: BaseException,
    cause: BaseException | None,
) -> tuple[int | None, int | None]:
    for candidate in (exc, cause):
        if candidate is None:
            continue
        line = getattr(candidate, "line", None)
        column = getattr(candidate, "column", None)
        if isinstance(line, int) or isinstance(column, int):
            return (
                line if isinstance(line, int) else None,
                column if isinstance(column, int) else None,
            )
    return None, None


def _failure_path(exc: BaseException, cause: BaseException | None) -> str | None:
    path = getattr(exc, "path", None)
    if isinstance(path, Path):
        return str(path)
    if isinstance(path, str) and path.strip():
        return path
    filename = getattr(cause, "filename", None)
    if isinstance(filename, (str, Path)):
        return str(filename)
    return None


def _has_parser_position(exc: BaseException, cause: BaseException | None) -> bool:
    if _failure_position(exc, cause) != (None, None):
        return True
    return getattr(exc, "source_line", None) is not None


def classify_load_failure(exc: BaseException) -> LoadFailureKind:
    """Name the part of the load a failure came from.

    A read failure is an ``OSError`` the parser wrapped while opening the file,
    a parse failure is one where the parser supplied a source position, and
    everything else is a resolution or structural load failure.
    """
    if isinstance(exc, OSError):
        return "read"
    cause = _failure_cause(exc)
    if isinstance(cause, OSError):
        return "read"
    if isinstance(exc, TargetLoadError):
        root_failure = _root_failure(exc)
        if root_failure is not None and (
            root_failure.line is not None
            or root_failure.column is not None
            or PARSE_FAILURE_MARKER in root_failure.message
        ):
            return "parse"
    if _has_parser_position(exc, cause):
        return "parse"
    return "load"


def describe_load_failure(target_name: str, exc: BaseException) -> LoadFailureDetail:
    """Build the one failure record the loader reports for ``target_name``."""
    cause = _failure_cause(exc)
    path = _failure_path(exc, cause)
    kind = classify_load_failure(exc)
    line, column = _failure_position(exc, cause)
    if kind == "read":
        reason = cause.strerror if isinstance(cause, OSError) and cause.strerror else str(cause or exc)
        where = f" {path}" if path else ""
        message = (
            f"Could not read{where} for target {target_name!r}: {reason}. "
            "Check that the file exists, is a regular file, and is readable."
        )
        return LoadFailureDetail(message=message, kind="read", path=path)
    if isinstance(exc, TargetLoadError):
        root_failure = _root_failure(exc)
        if root_failure is not None:
            line = root_failure.line
            column = root_failure.column
    return LoadFailureDetail(message=str(exc), kind=kind, path=path, line=line, column=column)


def _root_failure(exc: TargetLoadError) -> ProjectFailure | None:
    for failure in exc.failures.values():
        if unit_equal(failure.name, exc.target_name):
            return failure
    return None


class TargetLoadError(RuntimeError):
    def __init__(
        self,
        target_name: str,
        *,
        resolved: list[str],
        missing: list[str],
        warnings: list[str] | None = None,
        direct_dependencies: list[str] | None = None,
        failures: Mapping[str, ProjectFailure] | None = None,
    ):
        self.target_name = target_name
        self.resolved = list(resolved)
        self.missing = list(missing)
        self.warnings = list(warnings or [])
        self.direct_dependencies = list(direct_dependencies or [])
        self.failures = dict(failures or {})
        # ``missing`` also carries entries with no program, such as a missing
        # dependency file. Program failures are resolved through the typed
        # record, keyed by the message already stored on it.
        self._failures_by_message = {failure.message: failure for failure in self.failures.values()}
        super().__init__(self._build_message())

    @staticmethod
    def _extract_warning_name(item: str) -> str | None:
        if ": " not in item:
            return None
        return item.split(": ", 1)[0]

    @staticmethod
    def _format_failure_location(failure: ProjectFailure) -> str:
        parts: list[str] = []
        if failure.line is not None:
            parts.append(f"line {failure.line}")
        if failure.column is not None:
            parts.append(f"column {failure.column}")
        if failure.length is not None:
            parts.append(f"length {failure.length}")
        if not parts:
            return ""
        return f" ({', '.join(parts)})"

    def _format_missing_item(self, item: str) -> str:
        failure = self._failures_by_message.get(item)
        if failure is None:
            return item
        detail = failure.detail if failure.detail is not None else failure.message
        return f"{failure.name}: {detail}{self._format_failure_location(failure)}"

    def _missing_item_name(self, item: str) -> str | None:
        failure = self._failures_by_message.get(item)
        return None if failure is None else failure.name

    def _build_message(self) -> str:  # noqa: PLR0915
        direct_keys = {unit_key(name) for name in self.direct_dependencies}
        root_failures: list[str] = []
        direct_failures: list[str] = []
        transitive_failures: list[str] = []
        other_failures: list[str] = []
        root_warnings: list[str] = []
        direct_warnings: list[str] = []
        transitive_warnings: list[str] = []
        other_warnings: list[str] = []

        for item in self.missing:
            failure_name = self._missing_item_name(item)
            if failure_name is None:
                other_failures.append(item)
                continue
            if unit_equal(failure_name, self.target_name):
                root_failures.append(item)
            elif unit_key(failure_name) in direct_keys:
                direct_failures.append(item)
            else:
                transitive_failures.append(item)

        for item in self.warnings:
            warning_name = self._extract_warning_name(item)
            if warning_name is None:
                other_warnings.append(item)
            elif unit_equal(warning_name, self.target_name):
                root_warnings.append(item)
            elif unit_key(warning_name) in direct_keys:
                direct_warnings.append(item)
            else:
                transitive_warnings.append(item)

        parse_failed = any(PARSE_FAILURE_MARKER in item for item in self.missing)
        # An empty failure set means the loader dropped the target without a
        # recorded reason: it was not parsed. Recorded resolution failures say
        # the target could not be loaded, which is a different action for the
        # user than fixing syntax.
        headline = "was not parsed" if parse_failed or not self.missing else "could not be loaded"
        lines = [f"Target {self.target_name!r} {headline}."]
        if self.direct_dependencies:
            lines.append(f"Direct dependencies from the target file ({len(self.direct_dependencies)}):")
            lines.extend(_capped_entries(self.direct_dependencies, str))
        if self.resolved:
            lines.append(f"Resolved targets ({len(self.resolved)}):")
            lines.extend(_capped_entries(self.resolved, str))
        else:
            lines.append("Resolved targets: none")

        if root_failures:
            lines.append(f"Root target validation errors ({len(root_failures)}):")
            lines.extend(_capped_entries(root_failures, self._format_missing_item))

        if root_warnings:
            lines.append(f"Root target warnings ({len(root_warnings)}):")
            lines.extend(_capped_entries(root_warnings, str))

        if direct_failures:
            lines.append(f"Failed direct dependencies ({len(direct_failures)}):")
            lines.extend(_capped_entries(direct_failures, self._format_missing_item))

        if direct_warnings:
            lines.append(f"Direct dependency warnings ({len(direct_warnings)}):")
            lines.extend(_capped_entries(direct_warnings, str))

        if transitive_failures:
            lines.append(f"Transitive dependency failures ({len(transitive_failures)}):")
            lines.extend(_capped_entries(transitive_failures, self._format_missing_item))

        if transitive_warnings:
            lines.append(f"Transitive dependency warnings ({len(transitive_warnings)}):")
            lines.extend(_capped_entries(transitive_warnings, str))

        if other_failures:
            lines.append(f"Other missing/failed entries ({len(other_failures)}):")
            lines.extend(_capped_entries(other_failures, self._format_missing_item))

        if other_warnings:
            lines.append(f"Other warnings ({len(other_warnings)}):")
            lines.extend(_capped_entries(other_warnings, str))

        if not self.missing:
            lines.append("Missing/failed targets: none")

        return "\n".join(lines)


def _capped_entries(items: Sequence[str], formatter: Callable[[str], str]) -> list[str]:
    """Render one bounded list with an explicit remainder count."""
    shown = items[:TARGET_FAILURE_DETAIL_LIMIT]
    lines = [f"  - {formatter(item)}" for item in shown]
    remaining = len(items) - len(shown)
    if remaining:
        lines.append(f"  - ... and {remaining} more")
    return lines


def print_validation_warnings(warnings: list[str], *, print_fn: Callable[..., None], limit: int = 12) -> None:
    if not warnings:
        return

    print_fn(f"Validation warnings ({len(warnings)}):")
    for item in _format_validation_warning_items(warnings[:limit]):
        print_fn(item)
    if len(warnings) > limit:
        print_fn(f"  - ... (+{len(warnings) - limit} more)")


def is_picture_display_warning(item: str) -> bool:
    display_item = item.split(": ", 1)[1] if ": " in item else item
    return _PICTURE_DISPLAY_WARNING_RE.match(display_item) is not None


def _format_validation_warning_items(warnings: Sequence[str]) -> tuple[str, ...]:
    shared_target = _shared_warning_target(warnings)
    lines: list[str] = []
    for item in warnings:
        display_item = item.split(": ", 1)[1] if shared_target and ": " in item else item
        picture_display_match = _PICTURE_DISPLAY_WARNING_RE.match(display_item)
        if picture_display_match is not None:
            module_path, path_text, detail = picture_display_match.groups()
            lines.append(f"  - [{module_path}] {path_text}")
            lines.append(f"    {detail}")
            continue
        lines.append(f"  - {display_item}")
    return tuple(lines)


def _shared_warning_target(warnings: Sequence[str]) -> str | None:
    target_name: str | None = None
    for item in warnings:
        warning_name = extract_warning_name(item)
        if warning_name is None:
            return None
        if target_name is None:
            target_name = warning_name
            continue
        if not unit_equal(target_name, warning_name):
            return None
    return target_name


def extract_warning_name(item: str) -> str | None:
    if ": " not in item:
        return None
    return item.split(": ", 1)[0]


def target_validation_warnings(target_name: str, warnings: list[str]) -> list[str]:
    return [
        item
        for item in warnings
        if ((warning_name := extract_warning_name(item)) is None or unit_equal(warning_name, target_name))
    ]


def configured_icf_files(cfg: ConfigDict) -> tuple[Path | None, list[Path]]:
    icf_dir_raw = str(cfg.get("icf_dir", "") or "").strip()
    if not icf_dir_raw:
        return None, []

    icf_dir = Path(icf_dir_raw)
    if not icf_dir.exists() or not icf_dir.is_dir():
        return icf_dir, []

    icf_files = sorted(path for path in icf_dir.iterdir() if path.is_file() and path.suffix.lower() == ".icf")
    return icf_dir, icf_files


def get_analyzed_targets(cfg: Mapping[str, object]) -> list[str]:
    raw_targets = cfg.get("analyzed_programs_and_libraries", [])
    if not _is_string_sequence(raw_targets):
        return []
    return dedupe_unit_names(raw_targets)


def _is_string_sequence(value: object) -> TypeGuard[Sequence[str]]:
    if isinstance(value, str) or not isinstance(value, Sequence):
        return False
    return all(isinstance(target, str) for target in cast(Sequence[object], value))


def require_analyzed_targets(cfg: ConfigDict) -> list[str]:
    targets = get_analyzed_targets(cfg)
    if not targets:
        raise RuntimeError(
            "No analyzed programs/libraries configured. Add entries to 'analyzed_programs_and_libraries' first."
        )
    return targets


def has_analyzed_targets(
    cfg: ConfigDict,
    *,
    get_analyzed_targets_fn: Callable[[ConfigDict], list[str]] = get_analyzed_targets,
) -> bool:
    return bool(get_analyzed_targets_fn(cfg))


def require_targets_for_menu_action(
    cfg: ConfigDict,
    action: str,
    *,
    has_analyzed_targets_fn: Callable[[ConfigDict], bool],
    print_fn: Callable[..., None],
    pause_fn: Callable[[], None],
) -> bool:
    if has_analyzed_targets_fn(cfg):
        return True
    print_fn(f"\nNo analyzed programs/libraries configured. Add entries in Setup before {action}.")
    pause_fn()
    return False


def cache_key_for_target(
    cfg: ConfigDict,
    target_name: str,
    *,
    compute_cache_key_fn: Callable[..., str],
) -> str:
    return compute_cache_key_fn(cfg, analysis_target=target_name)


def split_csv_values(raw: str) -> list[str]:
    return [value.strip() for value in raw.split(",") if value.strip()]
