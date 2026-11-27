"""Checked-in baseline of accepted findings.

A baseline records the findings a team has decided are known, so a later run
can fail only on new or more severe ones. The document lives next to the
project file and is meant to be committed. It stores identities and a small
human-readable match record, never absolute paths or source snippets.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Literal, cast
from uuid import uuid4

from ..models.severity import SEVERITIES, Severity

BASELINE_SCHEMA_VERSION = 1
BASELINE_FILENAME = ".sattlint-baseline.json"

type BaselineStatus = Literal["unchanged", "moved", "changed", "added", "stale"]

type BaselineFailOn = Literal["error", "warning", "any", "none"]

_SEVERITY_RANK: dict[Severity, int] = {"info": 0, "warning": 1, "error": 2}

_SECONDARY_KEY = tuple[str, str, tuple[str, ...], str]

# Analyzer messages for located findings often lead with the source position,
# for example ``Program.icf:12: detail`` or ``Demo.s:12-14 detail``. A line
# shift changes that prefix, so the secondary match key ignores only the
# leading position, never the detail text.
_LOCATION_PREFIX_RE = re.compile(r"^.+?:\d+(?:-\d+)?(?::\s*|\s+)(?P<rest>.*)$")


class BaselineError(Exception):
    """A baseline file could not be read, parsed, or written."""


class BaselineNotFoundError(BaselineError):
    """The requested baseline file does not exist."""

    def __init__(self, path: Path) -> None:
        self.path = path
        super().__init__(f"Baseline file {path} was not found.")


class BaselineInvalidError(BaselineError):
    """The baseline path is unusable or the document does not match the schema."""


class BaselineWriteError(BaselineError):
    """The baseline document could not be written."""


def utc_now_iso() -> str:
    """The UTC ``...Z`` timestamp form used by the run store."""
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _is_absolute_path_text(value: str) -> bool:
    return PurePosixPath(value).is_absolute() or PureWindowsPath(value).is_absolute()


def _required_text(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise ValueError(f"{key!r} must be a string")
    return value


def _non_empty_text(payload: Mapping[str, object], key: str) -> str:
    value = _required_text(payload, key)
    if not value:
        raise ValueError(f"{key!r} must not be empty")
    return value


def _optional_file(payload: Mapping[str, object]) -> str | None:
    value = payload.get("file")
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("'file' must be a string or null")
    if _is_absolute_path_text(value):
        raise ValueError("'file' must be relative to the project root")
    return value


def _optional_positive_int(payload: Mapping[str, object], key: str) -> int | None:
    value = payload.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{key!r} must be a positive integer or null")
    return value


def _severity_field(payload: Mapping[str, object]) -> Severity:
    value = payload.get("severity")
    if not isinstance(value, str) or value not in SEVERITIES:
        raise ValueError("'severity' must be 'error', 'warning', or 'info'")
    return cast(Severity, value)


def _module_path_field(payload: Mapping[str, object]) -> tuple[str, ...]:
    value = payload.get("module_path")
    if not isinstance(value, (list, tuple)):
        raise ValueError("'module_path' must be a list of strings")
    sequence = cast(Sequence[object], value)
    if not all(isinstance(segment, str) for segment in sequence):
        raise ValueError("'module_path' must be a list of strings")
    return tuple(cast(Sequence[str], sequence))


@dataclass(frozen=True, slots=True)
class BaselineEntry:
    """One accepted finding, with only the fields a baseline needs."""

    identity: str
    analyzer: str
    kind: str
    severity: Severity
    module_path: tuple[str, ...]
    file: str | None
    line: int | None
    message: str

    def __post_init__(self) -> None:
        _validate_entry(self)

    @property
    def module(self) -> str:
        return ".".join(self.module_path)

    def to_dict(self) -> dict[str, object]:
        return {
            "identity": self.identity,
            "analyzer": self.analyzer,
            "kind": self.kind,
            "severity": self.severity,
            "module_path": list(self.module_path),
            "file": self.file,
            "line": self.line,
            "message": self.message,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> BaselineEntry:
        return cls(
            identity=_non_empty_text(payload, "identity"),
            analyzer=_required_text(payload, "analyzer"),
            kind=_required_text(payload, "kind"),
            severity=_severity_field(payload),
            module_path=_module_path_field(payload),
            file=_optional_file(payload),
            line=_optional_positive_int(payload, "line"),
            message=_required_text(payload, "message"),
        )


def _reject_duplicate_identities(entries: Sequence[BaselineEntry]) -> None:
    seen: set[str] = set()
    for entry in entries:
        if entry.identity in seen:
            raise ValueError(f"duplicate identity {entry.identity!r}")
        seen.add(entry.identity)


def _validate_entry(entry: BaselineEntry) -> None:
    """Reject an entry that cannot be written to a baseline document."""
    identity = cast(object, entry.identity)
    severity = cast(object, entry.severity)
    line = cast(object, entry.line)
    file = cast(object, entry.file)
    if not isinstance(identity, str) or not identity:
        raise ValueError("'identity' must be a non-empty string")
    if not isinstance(severity, str) or severity not in SEVERITIES:
        raise ValueError("'severity' must be 'error', 'warning', or 'info'")
    if line is not None and (isinstance(line, bool) or not isinstance(line, int) or line < 1):
        raise ValueError("'line' must be a positive integer or null")
    if file is not None and not isinstance(file, str):
        raise ValueError("'file' must be a string or null")
    if isinstance(file, str) and _is_absolute_path_text(file):
        raise ValueError("'file' must be relative to the project root")


@dataclass(frozen=True, slots=True)
class Baseline:
    """A versioned, sorted collection of accepted findings."""

    generated_by: str
    created: str
    entries: tuple[BaselineEntry, ...]
    schema_version: int = BASELINE_SCHEMA_VERSION

    @classmethod
    def create(
        cls,
        entries: Iterable[BaselineEntry],
        *,
        generated_by: str,
        created: str,
    ) -> Baseline:
        ordered = tuple(sorted(entries, key=lambda entry: entry.identity))
        _reject_duplicate_identities(ordered)
        return cls(generated_by=generated_by, created=created, entries=ordered)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "generated_by": self.generated_by,
            "created": self.created,
            "entries": [entry.to_dict() for entry in self.entries],
        }


@dataclass(frozen=True, slots=True)
class BaselineDiffEntry:
    """One finding in a baseline comparison.

    The current entry is flattened into the fields. ``previous_*`` fields are
    populated only when the match crossed a site or a severity boundary.
    """

    status: BaselineStatus
    identity: str
    analyzer: str
    kind: str
    severity: Severity
    module_path: tuple[str, ...]
    file: str | None
    line: int | None
    message: str
    previous_file: str | None = None
    previous_line: int | None = None
    previous_severity: Severity | None = None

    @property
    def module(self) -> str:
        return ".".join(self.module_path)


@dataclass(frozen=True, slots=True)
class BaselineDiff:
    """The five categories a baseline comparison reports."""

    unchanged: tuple[BaselineDiffEntry, ...] = ()
    moved: tuple[BaselineDiffEntry, ...] = ()
    changed: tuple[BaselineDiffEntry, ...] = ()
    added: tuple[BaselineDiffEntry, ...] = ()
    stale: tuple[BaselineDiffEntry, ...] = ()

    @property
    def reported(self) -> tuple[BaselineDiffEntry, ...]:
        """Every non-unchanged entry, grouped by category."""
        return (*self.changed, *self.added, *self.moved, *self.stale)

    def count(self, status: BaselineStatus) -> int:
        if status == "unchanged":
            return len(self.unchanged)
        if status == "moved":
            return len(self.moved)
        if status == "changed":
            return len(self.changed)
        if status == "added":
            return len(self.added)
        return len(self.stale)


def _diff_entry(
    entry: BaselineEntry,
    status: BaselineStatus,
    *,
    previous: BaselineEntry | None = None,
    previous_severity: Severity | None = None,
) -> BaselineDiffEntry:
    return BaselineDiffEntry(
        status=status,
        identity=entry.identity,
        analyzer=entry.analyzer,
        kind=entry.kind,
        severity=entry.severity,
        module_path=entry.module_path,
        file=entry.file,
        line=entry.line,
        message=entry.message,
        previous_file=None if previous is None else previous.file,
        previous_line=None if previous is None else previous.line,
        previous_severity=previous_severity,
    )


def _secondary_message(message: str) -> str:
    match = _LOCATION_PREFIX_RE.match(message)
    return match.group("rest") if match is not None else message


def _secondary_key(entry: BaselineEntry) -> _SECONDARY_KEY:
    return (entry.analyzer, entry.kind, entry.module_path, _secondary_message(entry.message))


def _sorted_diff(entries: Iterable[BaselineDiffEntry]) -> tuple[BaselineDiffEntry, ...]:
    return tuple(sorted(entries, key=lambda entry: entry.identity))


def diff_baseline(baseline: Baseline, current: Sequence[BaselineEntry]) -> BaselineDiff:
    """Compare a baseline with the findings of the current run.

    Identity wins. An unmatched current entry is recognized as moved only when
    exactly one unmatched baseline entry shares its analyzer, kind, module path,
    and message after any leading source position is removed. An ambiguous
    secondary match is reported as added and stale, never guessed.
    """
    baseline_by_id = {entry.identity: entry for entry in baseline.entries}
    current_by_id = {entry.identity: entry for entry in current}

    unchanged: list[BaselineDiffEntry] = []
    moved: list[BaselineDiffEntry] = []
    changed: list[BaselineDiffEntry] = []
    matched_baseline: set[str] = set()
    matched_current: set[str] = set()

    for identity, current_entry in current_by_id.items():
        previous = baseline_by_id.get(identity)
        if previous is None:
            continue
        matched_baseline.add(identity)
        matched_current.add(identity)
        if _SEVERITY_RANK[current_entry.severity] > _SEVERITY_RANK[previous.severity]:
            changed.append(
                _diff_entry(
                    current_entry,
                    "changed",
                    previous=previous,
                    previous_severity=previous.severity,
                )
            )
        elif current_entry.file != previous.file or current_entry.line != previous.line:
            moved.append(_diff_entry(current_entry, "moved", previous=previous))
        else:
            unchanged.append(_diff_entry(current_entry, "unchanged"))

    secondary: dict[_SECONDARY_KEY, list[BaselineEntry]] = {}
    for entry in baseline.entries:
        if entry.identity not in matched_baseline:
            secondary.setdefault(_secondary_key(entry), []).append(entry)

    unmatched_current: dict[_SECONDARY_KEY, list[BaselineEntry]] = {}
    for identity, current_entry in current_by_id.items():
        if identity not in matched_current:
            unmatched_current.setdefault(_secondary_key(current_entry), []).append(current_entry)

    added: list[BaselineDiffEntry] = []
    for key, current_group in unmatched_current.items():
        candidates = [entry for entry in secondary.get(key, ()) if entry.identity not in matched_baseline]
        if len(current_group) == 1 and len(candidates) == 1:
            previous = candidates[0]
            matched_baseline.add(previous.identity)
            moved.append(_diff_entry(current_group[0], "moved", previous=previous))
        else:
            added.extend(_diff_entry(entry, "added") for entry in current_group)

    stale = [_diff_entry(entry, "stale") for entry in baseline.entries if entry.identity not in matched_baseline]

    return BaselineDiff(
        unchanged=_sorted_diff(unchanged),
        moved=_sorted_diff(moved),
        changed=_sorted_diff(changed),
        added=_sorted_diff(added),
        stale=_sorted_diff(stale),
    )


def baseline_fails(diff: BaselineDiff, fail_on: BaselineFailOn) -> bool:
    """Whether the added or changed entries cross the fail-on threshold.

    Stale, moved, and unchanged entries never fail a run. A severity decrease
    is not a change, so it cannot fail either.
    """
    if fail_on == "none":
        return False
    for entry in (*diff.added, *diff.changed):
        if fail_on == "any":
            return True
        rank = _SEVERITY_RANK[entry.severity]
        if fail_on == "warning" and rank >= _SEVERITY_RANK["warning"]:
            return True
        if fail_on == "error" and rank >= _SEVERITY_RANK["error"]:
            return True
    return False


def relative_source_file(file: str | None, project_root: Path) -> str | None:
    """Normalize a finding's source file against the project root.

    A file inside the root becomes a POSIX relative path. A file outside the
    root, or a path that cannot be resolved, keeps only its name. An absent
    file stays ``None``. The result is never absolute.
    """
    text = (file or "").strip()
    if not text:
        return None
    root = project_root.expanduser().resolve()
    candidate = Path(text).expanduser()
    if not candidate.is_absolute():
        windows_path = PureWindowsPath(text)
        if windows_path.is_absolute():
            # A Windows absolute path read on another platform must not become
            # a path under the project root.
            return windows_path.name or None
        candidate = root / candidate
    try:
        relative = candidate.resolve().relative_to(root)
    except (OSError, ValueError):
        return candidate.name or None
    return relative.as_posix()


def load_baseline(path: str | Path) -> Baseline:
    """Read and validate a baseline document.

    A missing file, a directory, malformed JSON, an unknown schema version, or
    a wrong field type is an error. An empty baseline is valid but must be
    written as an explicit document.
    """
    resolved = Path(path).expanduser()
    if not resolved.exists():
        raise BaselineNotFoundError(resolved)
    if resolved.is_dir():
        raise BaselineInvalidError(f"Baseline path {resolved} is a directory, not a file.")
    try:
        with resolved.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except OSError as exc:
        raise BaselineInvalidError(f"Baseline {resolved} could not be read: {exc}") from exc
    except UnicodeDecodeError as exc:
        raise BaselineInvalidError(f"Baseline {resolved} is not valid UTF-8: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise BaselineInvalidError(f"Baseline {resolved} is not valid JSON: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise BaselineInvalidError(f"Baseline {resolved} must contain a JSON object.")
    document = cast(Mapping[str, object], payload)

    version = document.get("schema_version")
    if isinstance(version, bool) or not isinstance(version, int) or version != BASELINE_SCHEMA_VERSION:
        raise BaselineInvalidError(
            f"Baseline {resolved} uses schema version {version!r}, but this version of SattLint supports "
            f"{BASELINE_SCHEMA_VERSION}. Remove or replace the file with a baseline written by this version."
        )
    generated_by = _document_text(document, "generated_by", path=resolved)
    created = _document_text(document, "created", path=resolved)

    raw_entries = document.get("entries")
    if not isinstance(raw_entries, (list, tuple)):
        raise BaselineInvalidError(f"Baseline {resolved}: 'entries' must be a list.")
    entries: list[BaselineEntry] = []
    for index, item in enumerate(cast(Sequence[object], raw_entries)):
        if not isinstance(item, Mapping):
            raise BaselineInvalidError(f"Baseline {resolved}: entry {index} must be an object.")
        try:
            entries.append(BaselineEntry.from_dict(cast(Mapping[str, object], item)))
        except ValueError as exc:
            raise BaselineInvalidError(f"Baseline {resolved}: entry {index} is invalid: {exc}") from exc

    ordered = tuple(sorted(entries, key=lambda entry: entry.identity))
    try:
        _reject_duplicate_identities(ordered)
    except ValueError as exc:
        raise BaselineInvalidError(f"Baseline {resolved}: {exc}") from exc
    return Baseline(generated_by=generated_by, created=created, entries=ordered, schema_version=version)


def _document_text(document: Mapping[str, object], key: str, *, path: Path) -> str:
    value = document.get(key)
    if not isinstance(value, str) or not value.strip():
        raise BaselineInvalidError(f"Baseline {path}: {key!r} must be a non-empty string.")
    return value


def _atomic_write_json(path: Path, payload: object) -> None:
    """Write through a unique temp file in the same directory, then replace."""
    temp_path = path.with_name(f"{path.name}.{os.getpid()}.{uuid4().hex}.tmp")
    try:
        fd = os.open(temp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    except (OSError, TypeError, ValueError):
        with contextlib.suppress(OSError):
            temp_path.unlink()
        raise


def save_baseline(baseline: Baseline, path: str | Path) -> Path:
    """Write a baseline atomically, sorted by identity.

    A directory target is rejected before anything is written. The returned
    path is the one that was written.
    """
    target = Path(path).expanduser()
    if target.exists() and target.is_dir():
        raise BaselineWriteError(f"Baseline path {target} is a directory, not a file.")
    ordered = tuple(sorted(baseline.entries, key=lambda entry: entry.identity))
    try:
        _reject_duplicate_identities(ordered)
        for entry in ordered:
            _validate_entry(entry)
    except ValueError as exc:
        raise BaselineWriteError(str(exc)) from exc
    document = replace(baseline, entries=ordered).to_dict()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_json(target, document)
    except (OSError, TypeError, ValueError) as exc:
        raise BaselineWriteError(f"Baseline {target} could not be written: {exc}") from exc
    return target


__all__ = [
    "BASELINE_FILENAME",
    "BASELINE_SCHEMA_VERSION",
    "Baseline",
    "BaselineDiff",
    "BaselineDiffEntry",
    "BaselineEntry",
    "BaselineError",
    "BaselineFailOn",
    "BaselineInvalidError",
    "BaselineNotFoundError",
    "BaselineStatus",
    "BaselineWriteError",
    "baseline_fails",
    "diff_baseline",
    "load_baseline",
    "relative_source_file",
    "save_baseline",
    "utc_now_iso",
]
