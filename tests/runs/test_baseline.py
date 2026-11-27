"""Focused tests for the checked-in baseline format and diff."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sattlint.application.findings import Severity
from sattlint.runs.baseline import (
    BASELINE_SCHEMA_VERSION,
    Baseline,
    BaselineEntry,
    BaselineInvalidError,
    BaselineWriteError,
    baseline_fails,
    diff_baseline,
    load_baseline,
    relative_source_file,
    save_baseline,
)


def _entry(
    identity: str = "f_a",
    *,
    analyzer: str = "variables",
    kind: str = "unused",
    severity: Severity = "warning",
    module_path: tuple[str, ...] = ("Demo", "A"),
    file: str | None = "programs/Demo.s",
    line: int | None = 12,
    message: str = "declared but never read",
) -> BaselineEntry:
    return BaselineEntry(
        identity=identity,
        analyzer=analyzer,
        kind=kind,
        severity=severity,
        module_path=module_path,
        file=file,
        line=line,
        message=message,
    )


def _baseline(*entries: BaselineEntry) -> Baseline:
    return Baseline.create(
        entries,
        generated_by="sattlint 2026.11.6",
        created="2026-11-27T10:00:00.000Z",
    )


def _entry_document(**overrides: object) -> dict[str, object]:
    document: dict[str, object] = {
        "identity": "f_a",
        "analyzer": "variables",
        "kind": "unused",
        "severity": "warning",
        "module_path": ["Demo", "A"],
        "file": "programs/Demo.s",
        "line": 12,
        "message": "declared but never read",
    }
    document.update(overrides)
    return document


def _write_document(path: Path, *, version: object = BASELINE_SCHEMA_VERSION, entries: object = None) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": version,
                "generated_by": "sattlint 2026.11.6",
                "created": "2026-11-27T10:00:00.000Z",
                "entries": [_entry_document()] if entries is None else entries,
            }
        ),
        encoding="utf-8",
    )


def test_baseline_round_trips_every_field_in_a_sorted_document(tmp_path: Path) -> None:
    baseline = _baseline(
        _entry("f_b", message="second finding", line=20),
        _entry("f_a"),
    )
    path = tmp_path / ".sattlint-baseline.json"

    save_baseline(baseline, path)
    loaded = load_baseline(path)

    assert loaded == baseline
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert list(payload) == ["schema_version", "generated_by", "created", "entries"]
    assert payload["schema_version"] == 1
    assert payload["generated_by"] == "sattlint 2026.11.6"
    assert payload["created"] == "2026-11-27T10:00:00.000Z"
    assert [entry["identity"] for entry in payload["entries"]] == ["f_a", "f_b"]
    assert payload["entries"][0] == {
        "identity": "f_a",
        "analyzer": "variables",
        "kind": "unused",
        "severity": "warning",
        "module_path": ["Demo", "A"],
        "file": "programs/Demo.s",
        "line": 12,
        "message": "declared but never read",
    }


def test_round_trip_preserves_a_missing_file_and_line(tmp_path: Path) -> None:
    path = tmp_path / "baseline.json"
    save_baseline(_baseline(_entry("f_a", file=None, line=None)), path)

    loaded = load_baseline(path)

    assert loaded.entries[0].file is None
    assert loaded.entries[0].line is None
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["entries"][0]["file"] is None
    assert payload["entries"][0]["line"] is None


def test_unknown_schema_version_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "baseline.json"
    _write_document(path, version=2)

    with pytest.raises(BaselineInvalidError) as info:
        load_baseline(path)

    message = str(info.value)
    assert "schema version" in message
    assert "Remove or replace" in message
    assert "baseline update" not in message


def test_a_non_utf8_baseline_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "baseline.json"
    path.write_bytes(b"\xff\xfe{\x00")

    with pytest.raises(BaselineInvalidError, match="UTF-8"):
        load_baseline(path)


def test_malformed_json_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "baseline.json"
    path.write_text("{not json", encoding="utf-8")

    with pytest.raises(BaselineInvalidError, match="not valid JSON"):
        load_baseline(path)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("line", "twelve"),
        ("severity", "fatal"),
        ("module_path", "Demo.A"),
        ("file", 4),
        ("identity", ""),
    ],
)
def test_wrong_field_type_is_rejected(tmp_path: Path, field: str, value: object) -> None:
    path = tmp_path / "baseline.json"
    _write_document(path, entries=[_entry_document(**{field: value})])

    with pytest.raises(BaselineInvalidError, match="entry 0 is invalid"):
        load_baseline(path)


def test_a_directory_baseline_path_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(BaselineInvalidError, match="is a directory"):
        load_baseline(tmp_path)


def test_saving_to_a_directory_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(BaselineWriteError, match="is a directory"):
        save_baseline(_baseline(), tmp_path)


def test_duplicate_identities_are_rejected_on_load(tmp_path: Path) -> None:
    path = tmp_path / "baseline.json"
    _write_document(path, entries=[_entry_document(), _entry_document(line=20)])

    with pytest.raises(BaselineInvalidError, match="duplicate identity"):
        load_baseline(path)


def test_constructing_an_entry_with_an_absolute_file_raises() -> None:
    with pytest.raises(ValueError, match="relative to the project root"):
        _entry(file="/etc/passwd")
    with pytest.raises(ValueError, match="relative to the project root"):
        _entry(file=r"C:\work\Demo.s")


def test_save_rejects_an_entry_that_bypasses_construction(tmp_path: Path) -> None:
    entry = _entry("f_a")
    object.__setattr__(entry, "file", "/etc/passwd")
    baseline = Baseline(
        generated_by="sattlint 2026.11.6",
        created="2026-11-27T10:00:00.000Z",
        entries=(entry,),
    )

    with pytest.raises(BaselineWriteError, match="relative to the project root"):
        save_baseline(baseline, tmp_path / "baseline.json")


def test_duplicate_identities_are_rejected_on_save(tmp_path: Path) -> None:
    baseline = Baseline(
        generated_by="sattlint 2026.11.6",
        created="2026-11-27T10:00:00.000Z",
        entries=(_entry("f_a"), _entry("f_a", line=20)),
    )

    with pytest.raises(BaselineWriteError, match="duplicate identity"):
        save_baseline(baseline, tmp_path / "baseline.json")


def test_an_absolute_file_in_a_document_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "baseline.json"
    _write_document(path, entries=[_entry_document(file="/etc/passwd")])

    with pytest.raises(BaselineInvalidError, match="relative to the project root"):
        load_baseline(path)


def test_relative_file_normalization_never_stores_an_absolute_path(tmp_path: Path) -> None:
    root = tmp_path / "project"
    (root / "programs").mkdir(parents=True)
    inside = root / "programs" / "Demo.s"
    inside.write_text("", encoding="utf-8")
    outside = tmp_path / "outside" / "Demo.s"
    outside.parent.mkdir()
    outside.write_text("", encoding="utf-8")

    assert relative_source_file(str(inside), root) == "programs/Demo.s"
    assert relative_source_file("programs/Demo.s", root) == "programs/Demo.s"
    assert relative_source_file(str(outside), root) == "Demo.s"
    assert relative_source_file("../Demo.s", root) == "Demo.s"
    assert relative_source_file(None, root) is None

    path = tmp_path / "baseline.json"
    save_baseline(_baseline(_entry(file=relative_source_file(str(inside), root))), path)
    text = path.read_text(encoding="utf-8")
    assert str(root) not in text
    assert str(tmp_path) not in text


def test_a_moved_line_is_reported_as_moved_and_does_not_fail() -> None:
    baseline = _baseline(_entry("f_a", line=12))
    current = [_entry("f_a", line=20)]

    diff = diff_baseline(baseline, current)

    assert [entry.status for entry in diff.moved] == ["moved"]
    assert diff.moved[0].line == 20
    assert diff.moved[0].previous_line == 12
    assert diff.changed == ()
    assert diff.unchanged == ()
    assert baseline_fails(diff, "any") is False


def test_a_secondary_match_reports_a_moved_site() -> None:
    baseline = _baseline(_entry("f_a", line=12))
    current = [_entry("f_x", line=20)]

    diff = diff_baseline(baseline, current)

    assert [entry.identity for entry in diff.moved] == ["f_x"]
    assert diff.moved[0].previous_line == 12
    assert diff.added == ()
    assert diff.stale == ()


def test_a_located_icf_message_shift_is_moved_not_added_and_stale() -> None:
    baseline = _baseline(
        _entry(
            "f_icf_old",
            analyzer="icf",
            kind="icf.unresolved_path",
            line=12,
            message="Program.icf:12: unresolved path: X1 = Program:Path.Var",
        )
    )
    current = [
        _entry(
            "f_icf_new",
            analyzer="icf",
            kind="icf.unresolved_path",
            line=13,
            message="Program.icf:13: unresolved path: X1 = Program:Path.Var",
        )
    ]

    diff = diff_baseline(baseline, current)

    assert [entry.identity for entry in diff.moved] == ["f_icf_new"]
    assert diff.added == ()
    assert diff.stale == ()


def test_a_located_comment_code_message_shift_is_moved_not_added_and_stale() -> None:
    baseline = _baseline(
        _entry(
            "f_comment_old",
            analyzer="comments",
            kind="comment_code",
            line=12,
            message="Demo.s:12-14 code",
        )
    )
    current = [
        _entry(
            "f_comment_new",
            analyzer="comments",
            kind="comment_code",
            line=20,
            message="Demo.s:20-22 code",
        )
    ]

    diff = diff_baseline(baseline, current)

    assert [entry.identity for entry in diff.moved] == ["f_comment_new"]
    assert diff.added == ()
    assert diff.stale == ()


def test_a_changed_detail_after_a_location_prefix_is_not_moved() -> None:
    baseline = _baseline(
        _entry(
            "f_comment_old",
            analyzer="comments",
            kind="comment_code",
            line=12,
            message="Demo.s:12-14 code",
        )
    )
    current = [
        _entry(
            "f_comment_new",
            analyzer="comments",
            kind="comment_code",
            line=20,
            message="Demo.s:20-22 changed detail",
        )
    ]

    diff = diff_baseline(baseline, current)

    assert diff.moved == ()
    assert [entry.identity for entry in diff.added] == ["f_comment_new"]
    assert [entry.identity for entry in diff.stale] == ["f_comment_old"]


def test_several_current_entries_with_one_secondary_key_are_all_added() -> None:
    baseline = _baseline(_entry("f_a", line=12))
    current = [_entry("f_x", line=20), _entry("f_y", line=30)]

    diff = diff_baseline(baseline, current)

    assert diff.moved == ()
    assert [entry.identity for entry in diff.added] == ["f_x", "f_y"]
    assert [entry.identity for entry in diff.stale] == ["f_a"]


def test_a_severity_increase_is_changed_with_both_severities() -> None:
    baseline = _baseline(_entry("f_a", severity="info"))
    current = [_entry("f_a", severity="warning")]

    diff = diff_baseline(baseline, current)

    assert [entry.status for entry in diff.changed] == ["changed"]
    assert diff.changed[0].severity == "warning"
    assert diff.changed[0].previous_severity == "info"
    assert diff.moved == ()
    assert diff.unchanged == ()
    assert baseline_fails(diff, "warning") is True
    assert baseline_fails(diff, "error") is False


def test_a_severity_decrease_is_not_changed() -> None:
    baseline = _baseline(_entry("f_a", severity="error"))
    current = [_entry("f_a", severity="info")]

    diff = diff_baseline(baseline, current)

    assert diff.changed == ()
    assert [entry.identity for entry in diff.unchanged] == ["f_a"]
    assert baseline_fails(diff, "any") is False


def test_a_new_finding_is_added_and_a_missing_one_is_stale() -> None:
    baseline = _baseline(_entry("f_a"))
    current = [_entry("f_b", module_path=("Demo", "B"), message="another finding")]

    diff = diff_baseline(baseline, current)

    assert [entry.identity for entry in diff.added] == ["f_b"]
    assert [entry.identity for entry in diff.stale] == ["f_a"]
    assert diff.moved == ()
    assert baseline_fails(diff, "any") is True


def test_a_stale_entry_alone_does_not_fail() -> None:
    diff = diff_baseline(_baseline(_entry("f_a")), [])

    assert [entry.identity for entry in diff.stale] == ["f_a"]
    assert baseline_fails(diff, "none") is False
    assert baseline_fails(diff, "any") is False
    assert baseline_fails(diff, "warning") is False
    assert baseline_fails(diff, "error") is False


def test_ambiguous_secondary_matches_become_added_and_stale() -> None:
    baseline = _baseline(_entry("f_a", line=12), _entry("f_b", line=20))
    current = [_entry("f_c", line=40)]

    diff = diff_baseline(baseline, current)

    assert [entry.identity for entry in diff.added] == ["f_c"]
    assert [entry.identity for entry in diff.stale] == ["f_a", "f_b"]
    assert diff.moved == ()
