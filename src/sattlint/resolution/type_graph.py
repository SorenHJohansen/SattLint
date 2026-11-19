"""Type graph for record/datatype field resolution."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from functools import cache
from typing import Literal

from sattlint.parser_api import BUILTIN_RECORD_SPECS, BasePicture, DataType, ScalarDatatype, Variable


def _cf(s: str) -> str:
    return s.casefold()


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


LeafExpansionIssueKind = Literal["cycle", "unknown_record"]


@dataclass(frozen=True, slots=True)
class LeafExpansionIssue:
    """A structural problem found while expanding a datatype's leaf paths."""

    kind: LeafExpansionIssueKind
    type_name: str


def _never_opaque(_type_name: str) -> bool:
    return False


def _ignore_leaf_issue(_issue: LeafExpansionIssue) -> None:
    return None


@dataclass(frozen=True, slots=True)
class LeafExpansionPolicy:
    """Caller policy for datatypes that cannot be expanded further.

    ``is_opaque`` names types that are intentionally treated as leaves without
    reporting, and ``on_issue`` receives cycles and unknown records. Both kinds
    still terminate at the current prefix, so the result stays a set of leaf
    paths regardless of the caller's reaction.
    """

    is_opaque: Callable[[str], bool] = _never_opaque
    on_issue: Callable[[LeafExpansionIssue], None] = _ignore_leaf_issue


_DEFAULT_LEAF_POLICY = LeafExpansionPolicy()


class TypeGraph:
    """Case-insensitive graph of nested/complex datatypes (record types).

    Backed by BasePicture.datatype_defs (record definitions), where each field is
    represented by a Variable in DataType.var_list.
    """

    def __init__(self, records_by_key: dict[str, RecordDef]):
        self._records_by_key = records_by_key
        self._leaf_paths_by_key: dict[str, tuple[tuple[str, ...], ...]] = {}

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
    def from_datatypes(cls, datatypes: Iterable[DataType]) -> TypeGraph:
        records = dict(cls._builtin_records())
        for dt in datatypes:
            datatype = _require_datatype(dt)
            fields: dict[str, FieldDef] = {}
            for field in _datatype_fields(datatype):
                definition = _field_definition(field)
                fields[_cf(definition.name)] = definition
            records[_cf(datatype.name)] = RecordDef(name=datatype.name, fields_by_key=fields)
        return cls(records)

    @classmethod
    def from_basepicture(cls, bp: BasePicture) -> TypeGraph:
        return cls.from_datatypes(bp.datatype_defs or [])

    def has_record(self, type_name: str) -> bool:
        return _cf(type_name) in self._records_by_key

    def record(self, type_name: str) -> RecordDef | None:
        return self._records_by_key.get(_cf(type_name))

    def field(self, record_type: str, field_name: str) -> FieldDef | None:
        rec = self.record(record_type)
        if rec is None:
            return None
        return rec.fields_by_key.get(_cf(field_name))

    def field_type(self, record_type: str, field_name: str) -> ScalarDatatype | str | None:
        f = self.field(record_type, field_name)
        return f.datatype if f else None

    def iter_leaf_field_paths(self, root_type: ScalarDatatype | str) -> Iterable[tuple[str, ...]]:
        """Yield field paths from a type down to leaf (simple) datatypes.

        For a simple datatype, yields empty path (no further fields).
        For a record datatype, yields tuples like ("I", "WT001", "value").
        """
        if isinstance(root_type, ScalarDatatype):
            yield ()
            return

        yield from self._leaf_paths_for(_cf(root_type))

    def expand_leaf_paths(
        self,
        root_type: ScalarDatatype | str,
        *,
        policy: LeafExpansionPolicy = _DEFAULT_LEAF_POLICY,
    ) -> Iterable[tuple[str, ...]]:
        """Yield leaf paths using one traversal shared by every caller.

        The default policy silently treats cycles and unknown records as
        leaves; callers that need diagnostics or strictness pass their own
        policy. Ordering is identical for every policy.
        """
        if isinstance(root_type, ScalarDatatype):
            yield ()
            return

        yield from self._expand_leaf_paths(_cf(str(root_type)), policy)

    def _leaf_paths_for(self, type_key: str) -> tuple[tuple[str, ...], ...]:
        """Expand one datatype's leaf paths once and reuse them for later variables."""
        cached = self._leaf_paths_by_key.get(type_key)
        if cached is not None:
            return cached

        paths = tuple(self._expand_leaf_paths(type_key, _DEFAULT_LEAF_POLICY))
        self._leaf_paths_by_key[type_key] = paths
        return paths

    def _expand_leaf_paths(
        self,
        root_key: str,
        policy: LeafExpansionPolicy,
    ) -> Iterable[tuple[str, ...]]:
        stack: list[tuple[str, tuple[str, ...], frozenset[str]]] = [(root_key, (), frozenset())]

        while stack:
            tname, prefix, ancestors = stack.pop()
            if policy.is_opaque(tname):
                yield prefix
                continue
            tkey = _cf(tname)
            rec = self._records_by_key.get(tkey)
            if rec is None:
                # Unknown external type; treat as leaf after the caller reacts.
                policy.on_issue(LeafExpansionIssue(kind="unknown_record", type_name=tname))
                yield prefix
                continue

            if not rec.fields_by_key:
                yield prefix
                continue

            if tkey in ancestors:
                # Cycle; stop expanding.
                policy.on_issue(LeafExpansionIssue(kind="cycle", type_name=tname))
                yield prefix
                continue

            next_ancestors = ancestors | {tkey}
            for field in rec.fields_by_key.values():
                new_prefix = (*prefix, field.name)
                if isinstance(field.datatype, ScalarDatatype):
                    yield new_prefix
                else:
                    stack.append((str(field.datatype), new_prefix, next_ancestors))

    def iter_all_addressable_paths(self, root_var: Variable) -> Iterable[tuple[str, ...]]:
        """Convenience: expand leaf paths for a variable's datatype."""
        yield from self.iter_leaf_field_paths(root_var.datatype)
