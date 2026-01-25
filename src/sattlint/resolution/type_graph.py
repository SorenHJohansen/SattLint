from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from ..models.ast_model import BasePicture, DataType, Simple_DataType, Variable


def _cf(s: str) -> str:
    return s.casefold()


@dataclass(frozen=True, slots=True)
class FieldDef:
    name: str
    datatype: Simple_DataType | str


@dataclass(frozen=True, slots=True)
class RecordDef:
    name: str
    fields_by_key: dict[str, FieldDef]


class TypeGraph:
    """Case-insensitive graph of nested/complex datatypes (record types).

    Backed by BasePicture.datatype_defs (record definitions), where each field is
    represented by a Variable in DataType.var_list.
    """

    def __init__(self, records_by_key: dict[str, RecordDef]):
        self._records_by_key = records_by_key

    @classmethod
    def from_basepicture(cls, bp: BasePicture) -> "TypeGraph":
        records: dict[str, RecordDef] = {}
        for dt in bp.datatype_defs or []:
            fields: dict[str, FieldDef] = {}
            for v in dt.var_list or []:
                fields[_cf(v.name)] = FieldDef(name=v.name, datatype=v.datatype)
            records[_cf(dt.name)] = RecordDef(name=dt.name, fields_by_key=fields)
        return cls(records)

    def has_record(self, type_name: str) -> bool:
        return _cf(type_name) in self._records_by_key

    def record(self, type_name: str) -> RecordDef | None:
        return self._records_by_key.get(_cf(type_name))

    def field(self, record_type: str, field_name: str) -> FieldDef | None:
        rec = self.record(record_type)
        if rec is None:
            return None
        return rec.fields_by_key.get(_cf(field_name))

    def field_type(self, record_type: str, field_name: str) -> Simple_DataType | str | None:
        f = self.field(record_type, field_name)
        return f.datatype if f else None

    def iter_leaf_field_paths(self, root_type: Simple_DataType | str) -> Iterable[tuple[str, ...]]:
        """Yield field paths from a type down to leaf (simple) datatypes.

        For a simple datatype, yields empty path (no further fields).
        For a record datatype, yields tuples like ("I", "WT001", "value").
        """
        if isinstance(root_type, Simple_DataType):
            yield ()
            return

        start = root_type
        stack: list[tuple[str, tuple[str, ...]]] = [(start, ())]
        visiting: set[str] = set()

        while stack:
            tname, prefix = stack.pop()
            tkey = _cf(tname)
            rec = self._records_by_key.get(tkey)
            if rec is None:
                # Unknown external type; treat as leaf.
                yield prefix
                continue

            if tkey in visiting:
                # Cycle; stop expanding.
                yield prefix
                continue

            visiting.add(tkey)
            for field in rec.fields_by_key.values():
                new_prefix = prefix + (field.name,)
                if isinstance(field.datatype, Simple_DataType):
                    yield new_prefix
                else:
                    stack.append((str(field.datatype), new_prefix))
            visiting.remove(tkey)

    def iter_all_addressable_paths(self, root_var: Variable) -> Iterable[tuple[str, ...]]:
        """Convenience: expand leaf paths for a variable's datatype."""
        yield from self.iter_leaf_field_paths(root_var.datatype)
