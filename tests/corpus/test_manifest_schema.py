"""Schema and presence checks for every corpus manifest.

Only the analyzer family has an executing harness
(``tests/test_corpus_analyzers.py``). The semantic, valid, edge, and workspace
manifests describe workspace-level behavior that no runner executes yet, so this
module keeps them honest: every manifest parses, declares the fields the corpus
format requires, names an existing target fixture, and resolves every analyzer
key it declares. These checks do not run analyzers or assert findings.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from sattlint.analyzers.dispatch import get_registry_analyzer_spec

CORPUS_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "corpus"
MANIFEST_DIR = CORPUS_DIR / "manifests"
FIXTURES_DIR = CORPUS_DIR.parent

MANIFEST_PATHS = sorted(MANIFEST_DIR.glob("*.json"))

_MANIFEST_IDS = [path.stem for path in MANIFEST_PATHS]


def test_manifest_directory_contains_manifests() -> None:
    """A missing or empty manifest directory fails as a test, not at collection."""
    assert MANIFEST_PATHS, f"no corpus manifests found under {MANIFEST_DIR}"


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _load(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_keys)
    except ValueError as exc:
        pytest.fail(f"{path.name}: invalid manifest JSON: {exc}")
    assert isinstance(payload, dict), f"{path.name}: manifest root is not an object"
    return cast("dict[str, object]", payload)


def _expect_object(value: object, *, path: Path, field: str) -> dict[str, object]:
    assert isinstance(value, dict), f"{path.name}: {field} is not an object"
    return cast("dict[str, object]", value)


def _expect_string(value: object, *, path: Path, field: str) -> str:
    assert isinstance(value, str) and value, f"{path.name}: {field} is not a non-empty string"
    return value


def _expect_string_list(value: object, *, path: Path, field: str) -> list[str]:
    assert isinstance(value, list), f"{path.name}: {field} is not a list"
    items: list[str] = []
    for item in cast("list[object]", value):
        assert isinstance(item, str), f"{path.name}: {field} contains a non-string entry"
        items.append(item)
    return items


def _expectation(payload: dict[str, object], path: Path) -> dict[str, object]:
    return _expect_object(payload.get("expectation"), path=path, field="expectation")


def _artifact_fragments(payload: dict[str, object], path: Path) -> dict[str, object]:
    return _expect_object(
        _expectation(payload, path).get("artifact_fragments", {}),
        path=path,
        field="expectation.artifact_fragments",
    )


@pytest.mark.parametrize("manifest_path", MANIFEST_PATHS, ids=_MANIFEST_IDS)
def test_manifest_declares_required_fields(manifest_path: Path) -> None:
    """Every manifest parses and declares the corpus format's required fields."""
    payload = _load(manifest_path)

    case_id = _expect_string(payload.get("case_id"), path=manifest_path, field="case_id")
    assert case_id == manifest_path.stem, f"{manifest_path.name}: case_id {case_id!r} does not match the file name"

    _expect_string(payload.get("target_file"), path=manifest_path, field="target_file")
    _expect_string(payload.get("mode"), path=manifest_path, field="mode")
    _expect_string_list(payload.get("required_artifacts"), path=manifest_path, field="required_artifacts")

    expectation = _expectation(payload, manifest_path)
    expected = _expect_string_list(
        expectation.get("expected_finding_ids", []),
        path=manifest_path,
        field="expectation.expected_finding_ids",
    )
    forbidden = _expect_string_list(
        expectation.get("forbidden_finding_ids", []),
        path=manifest_path,
        field="expectation.forbidden_finding_ids",
    )
    assert not (set(expected) & set(forbidden)), f"{manifest_path.name}: a finding id is both expected and forbidden"
    assert len(expected) == len(set(expected)), f"{manifest_path.name}: duplicate expected finding id"
    assert len(forbidden) == len(set(forbidden)), f"{manifest_path.name}: duplicate forbidden finding id"

    fragments = _artifact_fragments(payload, manifest_path)
    for fragment_name, fragment in fragments.items():
        assert fragment_name.endswith(".json"), f"{manifest_path.name}: artifact fragment {fragment_name!r} is not JSON"
        _expect_object(fragment, path=manifest_path, field=f"expectation.artifact_fragments.{fragment_name}")

    summary = fragments.get("summary.json")
    if isinstance(summary, dict):
        summary_object = cast("dict[str, object]", summary)
        rule_counts = summary_object.get("rule_counts")
        finding_count = summary_object.get("finding_count")
        if rule_counts is not None:
            counts = _expect_object(rule_counts, path=manifest_path, field="summary.json.rule_counts")
            total = 0
            for rule, count in counts.items():
                assert isinstance(count, int), f"{manifest_path.name}: rule count for {rule!r} is not an integer"
                total += count
            if finding_count is not None:
                assert isinstance(finding_count, int), f"{manifest_path.name}: finding_count is not an integer"
                assert finding_count == total, (
                    f"{manifest_path.name}: finding_count {finding_count} != sum(rule_counts) {total}"
                )


@pytest.mark.parametrize("manifest_path", MANIFEST_PATHS, ids=_MANIFEST_IDS)
def test_manifest_target_fixture_exists(manifest_path: Path) -> None:
    """Every manifest names a real ``.s`` fixture inside the fixture tree."""
    payload = _load(manifest_path)
    target_file = _expect_string(payload.get("target_file"), path=manifest_path, field="target_file")
    target_path = (MANIFEST_DIR / target_file).resolve()

    assert target_path.is_file(), f"{manifest_path.name}: target fixture missing: {target_path}"
    assert FIXTURES_DIR in target_path.parents, (
        f"{manifest_path.name}: target fixture escapes the fixture tree: {target_path}"
    )

    load_strategy = payload.get("load_strategy")
    if load_strategy is not None:
        load_strategy = _expect_string(load_strategy, path=manifest_path, field="load_strategy")
    expected_suffix = ".py" if load_strategy == "python-factory" else ".s"
    assert target_path.suffix == expected_suffix, (
        f"{manifest_path.name}: {load_strategy or 'default'} load strategy expects a "
        f"{expected_suffix} target, found {target_path.name}"
    )


@pytest.mark.parametrize("manifest_path", MANIFEST_PATHS, ids=_MANIFEST_IDS)
def test_declared_analyzer_keys_resolve(manifest_path: Path) -> None:
    """Every analyzer key a manifest declares maps to a registered analyzer."""
    payload = _load(manifest_path)

    keys: list[str] = []
    top_level = payload.get("analyzer_key")
    if top_level is not None:
        keys.append(_expect_string(top_level, path=manifest_path, field="analyzer_key"))

    fragments = _artifact_fragments(payload, manifest_path)
    for fragment_name in ("status.json", "summary.json"):
        fragment = fragments.get(fragment_name)
        if fragment is None:
            continue
        analyzer_key = _expect_object(
            fragment,
            path=manifest_path,
            field=f"expectation.artifact_fragments.{fragment_name}",
        ).get("analyzer_key")
        if analyzer_key is not None:
            keys.append(
                _expect_string(
                    analyzer_key,
                    path=manifest_path,
                    field=f"expectation.artifact_fragments.{fragment_name}.analyzer_key",
                )
            )

    mode = _expect_string(payload.get("mode"), path=manifest_path, field="mode")
    if mode.startswith("analyzer-"):
        keys.append(mode.removeprefix("analyzer-"))

    for analyzer_key in keys:
        spec = get_registry_analyzer_spec(analyzer_key)
        assert spec.key, f"{manifest_path.name}: analyzer key {analyzer_key!r} resolved to an empty spec"
