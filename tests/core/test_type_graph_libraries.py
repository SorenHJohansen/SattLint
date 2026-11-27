"""Record resolution across libraries that declare the same record name."""

from __future__ import annotations

import pytest
from sattline_parser.models.ast_model import BasePicture, DataType, ScalarDatatype, Variable

from sattlint.parser_api import BUILTIN_RECORD_SPECS
from sattlint.resolution import AmbiguousRecordError, TypeGraph
from sattlint.resolution.type_graph import LeafExpansionIssue, LeafExpansionPolicy
from tests.helpers.variable_test_support import hdr as _hdr


def _datatype(name: str, fields: tuple[tuple[str, ScalarDatatype | str], ...], library: str | None) -> DataType:
    return DataType(
        name=name,
        description=None,
        datecode=None,
        var_list=[Variable(name=field_name, datatype=datatype) for field_name, datatype in fields],
        origin_file=f"{library}.s" if library else None,
        origin_lib=library,
    )


def _two_library_graph() -> TypeGraph:
    return TypeGraph.from_datatypes(
        [
            _datatype(
                "SharedRecord",
                (("Alpha", ScalarDatatype.INTEGER), ("Inner", "InnerAlpha")),
                "LibA",
            ),
            _datatype("InnerAlpha", (("AlphaLeaf", ScalarDatatype.INTEGER),), "LibA"),
            _datatype(
                "SharedRecord",
                (("Beta", ScalarDatatype.BOOLEAN), ("Inner", "InnerBeta")),
                "LibB",
            ),
            _datatype("InnerBeta", (("BetaLeaf", ScalarDatatype.BOOLEAN),), "LibB"),
        ]
    )


def test_field_resolution_follows_the_requesting_library() -> None:
    graph = _two_library_graph()

    assert graph.field("SharedRecord", "Alpha", library="LibA") is not None
    assert graph.field("SharedRecord", "Beta", library="LibA") is None
    assert graph.field("SharedRecord", "Beta", library="LibB") is not None
    assert graph.field("SharedRecord", "Alpha", library="LibB") is None

    record_a = graph.record("SharedRecord", library="LibA")
    record_b = graph.record("SharedRecord", library="LibB")
    assert record_a is not None and record_a.library == "LibA"
    assert record_b is not None and record_b.library == "LibB"
    assert record_a.name == record_b.name == "SharedRecord"


def test_leaf_paths_follow_the_requesting_library() -> None:
    graph = _two_library_graph()

    assert set(graph.iter_leaf_field_paths("SharedRecord", library="LibA")) == {
        ("Alpha",),
        ("Inner", "AlphaLeaf"),
    }
    assert set(graph.iter_leaf_field_paths("SharedRecord", library="LibB")) == {
        ("Beta",),
        ("Inner", "BetaLeaf"),
    }
    assert set(graph.expand_leaf_paths("SharedRecord", library="LibB")) == {
        ("Beta",),
        ("Inner", "BetaLeaf"),
    }


def test_name_only_lookup_prefers_the_root_library_then_a_unique_candidate() -> None:
    graph = TypeGraph.from_datatypes(
        [
            _datatype("SharedRecord", (("Alpha", ScalarDatatype.INTEGER),), "LibA"),
            _datatype("SharedRecord", (("Beta", ScalarDatatype.BOOLEAN),), "LibB"),
            _datatype("OnlyHere", (("Gamma", ScalarDatatype.INTEGER),), "LibB"),
        ],
        root_library="LibB",
    )

    record = graph.record("SharedRecord")
    assert record is not None and record.library == "LibB"
    assert graph.field("SharedRecord", "Beta") is not None
    assert graph.field("SharedRecord", "Alpha") is None

    unique = graph.record("OnlyHere")
    assert unique is not None and unique.library == "LibB"


def test_name_only_lookup_with_several_candidates_raises() -> None:
    graph = _two_library_graph()

    with pytest.raises(AmbiguousRecordError) as error:
        graph.record("SharedRecord")
    assert set(error.value.libraries) == {"LibA", "LibB"}

    with pytest.raises(AmbiguousRecordError):
        graph.field("SharedRecord", "Alpha")


def test_leaf_expansion_treats_an_ambiguous_name_as_a_leaf_by_default() -> None:
    graph = _two_library_graph()

    assert list(graph.iter_leaf_field_paths("SharedRecord")) == [()]
    assert list(graph.expand_leaf_paths("SharedRecord")) == [()]

    issues: list[LeafExpansionIssue] = []
    reported = list(
        graph.iter_leaf_field_paths(
            "SharedRecord",
            policy=LeafExpansionPolicy(on_issue=issues.append),
        )
    )
    assert reported == [()]
    assert [(issue.kind, issue.type_name) for issue in issues] == [("ambiguous_record", "SharedRecord")]


def test_ambiguous_name_is_reported_through_the_leaf_policy() -> None:
    graph = _two_library_graph()
    issues: list[LeafExpansionIssue] = []

    paths = list(
        graph.expand_leaf_paths(
            "SharedRecord",
            policy=LeafExpansionPolicy(on_issue=issues.append),
        )
    )

    assert paths == [()]
    assert [(issue.kind, issue.type_name) for issue in issues] == [("ambiguous_record", "SharedRecord")]


def test_builtin_records_stay_library_agnostic() -> None:
    builtin_name = next(iter(BUILTIN_RECORD_SPECS))
    graph = _two_library_graph()

    builtin = graph.record(builtin_name)
    assert builtin is not None
    assert builtin.library is None
    assert graph.record(builtin_name, library="LibA") is not None


def test_a_library_record_shadows_the_builtin_of_the_same_name() -> None:
    builtin_name = next(iter(BUILTIN_RECORD_SPECS))
    graph = TypeGraph.from_datatypes(
        [_datatype(builtin_name, (("OnlyField", ScalarDatatype.INTEGER),), "LibA")],
    )

    record = graph.record(builtin_name, library="LibA")
    assert record is not None and record.library == "LibA"
    assert set(record.fields_by_key) == {"onlyfield"}


def test_from_basepicture_uses_the_picture_library_as_root() -> None:
    picture = BasePicture(
        header=_hdr("Root"),
        origin_file="LibB.s",
        origin_lib="LibB",
        datatype_defs=[
            _datatype("SharedRecord", (("Alpha", ScalarDatatype.INTEGER),), "LibA"),
            _datatype("SharedRecord", (("Beta", ScalarDatatype.BOOLEAN),), "LibB"),
        ],
    )

    graph = TypeGraph.from_basepicture(picture)

    assert graph.root_library == "LibB"
    record = graph.record("SharedRecord")
    assert record is not None and record.library == "LibB"
