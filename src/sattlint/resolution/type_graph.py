"""Type graph for record/datatype field resolution."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from functools import cache
from typing import Literal

from sattlint.parser_api import BUILTIN_RECORD_SPECS, BasePicture, DataType, ScalarDatatype, Variable


def _cf(s: str) -> str:
    return s.casefold()


def _library_key(library: str | None) -> str:
    """Casefolded library key; the empty string means "no library"."""
    return library.casefold() if library else ""


def _require_datatype(value: object) -> DataType:
    if not isinstance(value, DataType):
        raise TypeError(f"Expected a DataType definition, got {type(value).__name__}")
    return value


def _datatype_fields(record: DataType) -> Iterable[Variable]:
    return record.var_list or []


def _field_definition(field: Variable) -> FieldDef:
    return FieldDef(name=field.name, datatype=field.datatype, state=field.state, const=bool(field.const))


@dataclass(frozen=True, slots=True)
class FieldDef:
    name: str
    datatype: ScalarDatatype | str
    state: bool | None = False
    const: bool = False


@dataclass(frozen=True, slots=True)
class RecordDef:
    name: str
    fields_by_key: dict[str, FieldDef]
    #: Library that declares the record; ``None`` for the library-agnostic
    #: built-in tier and for hand-built definitions without provenance.
    library: str | None = None


class AmbiguousRecordError(ValueError):
    """A record name matches several libraries and no library disambiguates it."""

    def __init__(self, type_name: str, libraries: tuple[str | None, ...]) -> None:
        self.type_name = type_name
        self.libraries = libraries
        labels = ", ".join(sorted(library for library in libraries if library)) or "unknown libraries"
        super().__init__(
            f"Record datatype {type_name!r} is declared in several libraries ({labels}); "
            "resolve it from a library-aware caller instead of picking one arbitrarily."
        )


LeafExpansionIssueKind = Literal["cycle", "unknown_record", "ambiguous_record"]


@dataclass(frozen=True, slots=True)
class LeafExpansionIssue:
    """A structural problem found while expanding a datatype's leaf paths."""

    kind: LeafExpansionIssueKind
    type_name: str
    #: Libraries that declare an ``ambiguous_record`` name; empty otherwise.
    libraries: tuple[str | None, ...] = ()


def _never_opaque(_type_name: str) -> bool:
    return False


def _ignore_leaf_issue(_issue: LeafExpansionIssue) -> None:
    return None


def _raise_on_ambiguity(issue: LeafExpansionIssue) -> None:
    if issue.kind == "ambiguous_record":
        raise AmbiguousRecordError(issue.type_name, issue.libraries)


@dataclass(frozen=True, slots=True)
class LeafExpansionPolicy:
    """Caller policy for datatypes that cannot be expanded further.

    ``is_opaque`` names types that are intentionally treated as leaves without
    reporting, and ``on_issue`` receives cycles, unknown records, and record
    names that several libraries declare. Every kind still terminates at the
    current prefix, so the result stays a set of leaf paths regardless of the
    caller's reaction.
    """

    is_opaque: Callable[[str], bool] = _never_opaque
    on_issue: Callable[[LeafExpansionIssue], None] = _ignore_leaf_issue


_DEFAULT_LEAF_POLICY = LeafExpansionPolicy()
_AMBIGUITY_RAISING_POLICY = LeafExpansionPolicy(on_issue=_raise_on_ambiguity)


class TypeGraph:
    """Case-insensitive graph of nested/complex datatypes (record types).

    Backed by BasePicture.datatype_defs (record definitions), where each field is
    represented by a Variable in DataType.var_list. Records are indexed by
    ``(library, name)`` so two libraries can each declare a record of the same
    name with a different field layout. Built-in records form a separate,
    library-agnostic tier that only answers when no library declares the name.

    Resolution order for a lookup that passes ``library``:

    1. the exact ``(library, name)`` record,
    2. the graph's root library (the library of the analyzed picture),
    3. the sole remaining definition.

    A caller that passes no library still resolves a name declared by exactly
    one library. When more than one definition remains, :meth:`record`,
    :meth:`field`, :meth:`field_type`, and :meth:`iter_leaf_field_paths` raise
    :class:`AmbiguousRecordError` instead of picking one arbitrarily, while
    :meth:`expand_leaf_paths` reports the ambiguity through the caller's
    :class:`LeafExpansionPolicy` and treats the type as a leaf.
    """

    def __init__(self, records_by_key: dict[tuple[str, str], RecordDef], *, root_library: str | None = None):
        self._records_by_key = records_by_key
        self._root_library = root_library
        records_by_name: dict[str, list[RecordDef]] = {}
        for record in records_by_key.values():
            records_by_name.setdefault(_cf(record.name), []).append(record)
        self._records_by_name: dict[str, tuple[RecordDef, ...]] = {
            name: tuple(records) for name, records in records_by_name.items()
        }
        self._leaf_paths_by_key: dict[tuple[str, str], tuple[tuple[str, ...], ...]] = {}

    @property
    def root_library(self) -> str | None:
        """Library of the analyzed picture, used as the second resolution tier."""
        return self._root_library

    @staticmethod
    @cache
    def _builtin_records() -> dict[str, RecordDef]:
        records: dict[str, RecordDef] = {}
        for datatype_name, field_specs in BUILTIN_RECORD_SPECS.items():
            fields = {
                _cf(field_name): FieldDef(name=field_name, datatype=datatype) for field_name, datatype in field_specs
            }
            records[_cf(datatype_name)] = RecordDef(name=datatype_name, fields_by_key=fields)
        return records

    @classmethod
    def from_datatypes(
        cls,
        datatypes: Iterable[DataType],
        *,
        root_library: str | None = None,
    ) -> TypeGraph:
        records_by_key: dict[tuple[str, str], RecordDef] = {}
        for dt in datatypes:
            datatype = _require_datatype(dt)
            fields: dict[str, FieldDef] = {}
            for field in _datatype_fields(datatype):
                definition = _field_definition(field)
                fields[_cf(definition.name)] = definition
            library = datatype.origin_lib
            records_by_key[(_library_key(library), _cf(datatype.name))] = RecordDef(
                name=datatype.name,
                fields_by_key=fields,
                library=library,
            )
        return cls(records_by_key, root_library=root_library)

    @classmethod
    def from_basepicture(cls, bp: BasePicture, *, root_library: str | None = None) -> TypeGraph:
        """Build the per-library record index once from the merged picture.

        The root library defaults to the picture's own library, which keeps a
        lookup that names no library anchored to the analyzed target.
        """
        effective_root = root_library if root_library is not None else getattr(bp, "origin_lib", None)
        return cls.from_datatypes(bp.datatype_defs or [], root_library=effective_root)

    def _resolve_record(self, type_name: str, library: str | None) -> RecordDef | None:
        name_key = _cf(type_name)
        library_key = _library_key(library)
        if library_key:
            record = self._records_by_key.get((library_key, name_key))
            if record is not None:
                return record

        root_key = _library_key(self._root_library)
        if root_key and root_key != library_key:
            record = self._records_by_key.get((root_key, name_key))
            if record is not None:
                return record

        candidates = self._records_by_name.get(name_key, ())
        if len(candidates) == 1:
            return candidates[0]
        if len(candidates) > 1:
            raise AmbiguousRecordError(type_name, tuple(record.library for record in candidates))
        return self._builtin_records().get(name_key)

    def has_record(self, type_name: str, *, library: str | None = None) -> bool:
        """Whether a record with this name resolves; an ambiguous name still exists."""
        try:
            return self._resolve_record(type_name, library) is not None
        except AmbiguousRecordError:
            return True

    def record(self, type_name: str, *, library: str | None = None) -> RecordDef | None:
        """Resolve a record by name, preferring the caller's library.

        ``library`` should be the library whose code references the type; pass
        ``None`` only when the caller genuinely has no library. A name that
        several libraries declare then raises :class:`AmbiguousRecordError`.
        """
        return self._resolve_record(type_name, library)

    def field(self, record_type: str, field_name: str, *, library: str | None = None) -> FieldDef | None:
        rec = self.record(record_type, library=library)
        if rec is None:
            return None
        return rec.fields_by_key.get(_cf(field_name))

    def field_type(
        self, record_type: str, field_name: str, *, library: str | None = None
    ) -> ScalarDatatype | str | None:
        f = self.field(record_type, field_name, library=library)
        return f.datatype if f else None

    def iter_leaf_field_paths(
        self,
        root_type: ScalarDatatype | str,
        *,
        library: str | None = None,
    ) -> Iterable[tuple[str, ...]]:
        """Yield field paths from a type down to leaf (simple) datatypes.

        For a simple datatype, yields empty path (no further fields).
        For a record datatype, yields tuples like ("I", "WT001", "value").

        ``library`` is the library that uses the type. Without it, a record name
        that several libraries declare raises :class:`AmbiguousRecordError`.
        """
        if isinstance(root_type, ScalarDatatype):
            yield ()
            return

        yield from self._leaf_paths_for(str(root_type), library)

    def expand_leaf_paths(
        self,
        root_type: ScalarDatatype | str,
        *,
        library: str | None = None,
        policy: LeafExpansionPolicy = _DEFAULT_LEAF_POLICY,
    ) -> Iterable[tuple[str, ...]]:
        """Yield leaf paths using one traversal shared by every caller.

        The default policy silently treats cycles and unknown records as
        leaves; callers that need diagnostics or strictness pass their own
        policy. Ordering is identical for every policy. An ambiguous record
        name is reported as ``ambiguous_record`` and also treated as a leaf,
        because the shared traversal has no basis for picking a library.
        """
        if isinstance(root_type, ScalarDatatype):
            yield ()
            return

        yield from self._expand_leaf_paths(str(root_type), policy, library)

    def _leaf_paths_for(
        self,
        type_name: str,
        library: str | None,
    ) -> tuple[tuple[str, ...], ...]:
        """Expand one datatype's leaf paths once and reuse them for later variables."""
        cache_key = (_library_key(library), _cf(type_name))
        cached = self._leaf_paths_by_key.get(cache_key)
        if cached is not None:
            return cached

        paths = tuple(self._expand_leaf_paths(type_name, _AMBIGUITY_RAISING_POLICY, library))
        self._leaf_paths_by_key[cache_key] = paths
        return paths

    def _expand_leaf_paths(
        self,
        root_type: str,
        policy: LeafExpansionPolicy,
        library: str | None,
    ) -> Iterable[tuple[str, ...]]:
        # Each entry carries the library of the record that declared the field,
        # so a nested type resolves in the same library that used it.
        stack: list[tuple[str, tuple[str, ...], frozenset[tuple[str, str]], str | None]] = [
            (root_type, (), frozenset(), library)
        ]

        while stack:
            tname, prefix, ancestors, current_library = stack.pop()
            if policy.is_opaque(tname):
                yield prefix
                continue
            try:
                record = self._resolve_record(tname, current_library)
            except AmbiguousRecordError as exc:
                policy.on_issue(
                    LeafExpansionIssue(
                        kind="ambiguous_record",
                        type_name=tname,
                        libraries=exc.libraries,
                    )
                )
                yield prefix
                continue
            if record is None:
                # Unknown external type; treat as leaf after the caller reacts.
                policy.on_issue(LeafExpansionIssue(kind="unknown_record", type_name=tname))
                yield prefix
                continue

            if not record.fields_by_key:
                yield prefix
                continue

            type_key = (_library_key(record.library), _cf(tname))
            if type_key in ancestors:
                # Cycle; stop expanding.
                policy.on_issue(LeafExpansionIssue(kind="cycle", type_name=tname))
                yield prefix
                continue

            next_ancestors = ancestors | {type_key}
            for field in record.fields_by_key.values():
                new_prefix = (*prefix, field.name)
                if isinstance(field.datatype, ScalarDatatype):
                    yield new_prefix
                else:
                    stack.append((str(field.datatype), new_prefix, next_ancestors, record.library))

    def iter_all_addressable_paths(
        self,
        root_var: Variable,
        *,
        library: str | None = None,
    ) -> Iterable[tuple[str, ...]]:
        """Convenience: expand leaf paths for a variable's datatype.

        ``library`` is the library that declares the variable, so a record name
        it shares with another library resolves to the declaring layout.
        """
        yield from self.iter_leaf_field_paths(root_var.datatype, library=library)
