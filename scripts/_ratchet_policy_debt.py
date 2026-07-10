from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from defusedxml import ElementTree  # type: ignore[import-untyped]

try:
    from scripts import _ratchet_policy_context as ratchet_context
except ModuleNotFoundError:  # pragma: no cover - direct script execution resolves from scripts/
    import _ratchet_policy_context as ratchet_context


def metric_mapping(payload: dict[str, Any], label: str) -> dict[str, int]:
    metrics = payload.get("metrics")
    if not isinstance(metrics, dict):
        raise ValueError(f"{label} is missing a metrics object.")
    normalized: dict[str, int] = {}
    for key, value in metrics.items():
        if not isinstance(value, int):
            raise ValueError(f"{label} metric {key!r} must be an integer.")
        normalized[str(key)] = value
    return normalized


def structural_file_line_exception_mapping(payload: dict[str, Any], label: str) -> dict[str, dict[str, Any]]:
    raw = payload.get("file_line_exceptions")
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"{label} file_line_exceptions must be a JSON object keyed by repo-relative path.")

    normalized: dict[str, dict[str, Any]] = {}
    for raw_path, value in raw.items():
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise ValueError(f"{label} file_line_exceptions keys must be non-empty strings.")
        if not isinstance(value, dict):
            raise ValueError(f"{label} file_line_exceptions[{raw_path!r}] must be a JSON object.")

        max_lines = value.get("max_lines")
        reason = value.get("reason")
        if not isinstance(max_lines, int) or max_lines <= 0:
            raise ValueError(f"{label} file_line_exceptions[{raw_path!r}].max_lines must be a positive integer.")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError(f"{label} file_line_exceptions[{raw_path!r}].reason must be a non-empty string.")

        normalized[raw_path.replace("\\", "/").strip("/")] = {
            "max_lines": int(max_lines),
            "reason": reason.strip(),
        }

    return dict(sorted(normalized.items()))


def file_debt_touch_rule(dimension: str, value: Any, *, label: str) -> str:
    if not isinstance(value, str) or value not in ratchet_context.FILE_DEBT_TOUCH_RULES[dimension]:
        allowed = ", ".join(sorted(ratchet_context.FILE_DEBT_TOUCH_RULES[dimension]))
        raise ValueError(f"{label} touch_rule must be one of: {allowed}.")
    return value


def effective_structural_touch_rule(entry: Mapping[str, Any], *, baseline_lines: int) -> str:
    target = int(entry["target"])
    touch_rule = str(entry["touch_rule"])
    if baseline_lines <= target:
        return "must_meet_target"
    if touch_rule == "must_not_grow":
        return "must_shrink"
    return touch_rule


def structural_debt_guidance(*, rel_path: str, effective_touch_rule: str, reason: str) -> str:
    enforcement = (
        "shrink-only touch enforcement" if effective_touch_rule == "must_shrink" else "target-meeting touch enforcement"
    )
    guidance = (
        f" {rel_path} is under {enforcement}; reduce the file in the same change before merge. "
        f"First proof: {ratchet_context.FIRST_STRUCTURAL_DEBT_PROOF_COMMAND}."
    )
    if reason.strip():
        guidance += f" Reason: {reason.strip()}"
    return guidance


def normalized_file_debt_dimension(raw: Any, *, dimension: str, label: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"{label} must be a JSON object.")

    reason = raw.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError(f"{label}.reason must be a non-empty string.")

    allow_rebaseline = raw.get("allow_rebaseline", False)
    if not isinstance(allow_rebaseline, bool):
        raise ValueError(f"{label}.allow_rebaseline must be a boolean.")

    normalized: dict[str, Any] = {
        "allow_rebaseline": allow_rebaseline,
        "reason": reason.strip(),
        "touch_rule": file_debt_touch_rule(dimension, raw.get("touch_rule"), label=label),
    }

    if dimension == "typing":
        unexpected = sorted(set(raw) - {"allow_rebaseline", "reason", "touch_rule"})
        if unexpected:
            raise ValueError(f"{label} contains unsupported keys: {', '.join(unexpected)}.")
        return normalized

    current_baseline = raw.get("current_baseline")
    target = raw.get("target")
    if not isinstance(current_baseline, int) or current_baseline < 0:
        raise ValueError(f"{label}.current_baseline must be a non-negative integer.")
    if not isinstance(target, int) or target < 0:
        raise ValueError(f"{label}.target must be a non-negative integer.")

    if dimension == "structural" and target > current_baseline:
        raise ValueError(f"{label}.target must be less than or equal to current_baseline for structural debt.")
    if dimension == "coverage" and target < current_baseline:
        raise ValueError(f"{label}.target must be greater than or equal to current_baseline for coverage debt.")

    unexpected = sorted(set(raw) - {"allow_rebaseline", "current_baseline", "reason", "target", "touch_rule"})
    if unexpected:
        raise ValueError(f"{label} contains unsupported keys: {', '.join(unexpected)}.")

    normalized["current_baseline"] = current_baseline
    normalized["target"] = target
    return normalized


def file_debt_ratchet_state(text: str, label: str) -> dict[str, dict[str, dict[str, Any]]]:
    payload = ratchet_context.parse_json_payload(text, label)
    if payload.get("kind") != ratchet_context.FILE_DEBT_RATCHET_SCHEMA_KIND:
        raise ValueError(f"{label} kind must be {ratchet_context.FILE_DEBT_RATCHET_SCHEMA_KIND!r}.")
    if payload.get("schema_version") != ratchet_context.FILE_DEBT_RATCHET_SCHEMA_VERSION:
        raise ValueError(f"{label} schema_version must be {ratchet_context.FILE_DEBT_RATCHET_SCHEMA_VERSION}.")

    raw_files = payload.get("files")
    if not isinstance(raw_files, dict):
        raise ValueError(f"{label}.files must be a JSON object keyed by repo-relative path.")

    normalized: dict[str, dict[str, dict[str, Any]]] = {}
    for raw_path, raw_dimensions in raw_files.items():
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise ValueError(f"{label}.files keys must be non-empty strings.")
        if not isinstance(raw_dimensions, dict) or not raw_dimensions:
            raise ValueError(f"{label}.files[{raw_path!r}] must be a non-empty JSON object.")

        rel_path = ratchet_context.normalize_rel_path(raw_path)
        if not any(rel_path.startswith(prefix) for prefix in ratchet_context.FILE_DEBT_ALLOWED_PREFIXES):
            raise ValueError(
                f"{label}.files[{raw_path!r}] must stay within tracked debt surfaces: {', '.join(ratchet_context.FILE_DEBT_ALLOWED_PREFIXES)}."
            )
        if rel_path in normalized:
            raise ValueError(f"{label}.files contains duplicate path {rel_path!r}.")

        normalized_dimensions: dict[str, dict[str, Any]] = {}
        for dimension, dimension_payload in sorted(raw_dimensions.items()):
            if dimension not in ratchet_context.FILE_DEBT_TOUCH_RULES:
                allowed_dimensions = ", ".join(sorted(ratchet_context.FILE_DEBT_TOUCH_RULES))
                raise ValueError(
                    f"{label}.files[{raw_path!r}] dimension {dimension!r} is unsupported. "
                    f"Allowed dimensions: {allowed_dimensions}."
                )
            normalized_dimensions[dimension] = normalized_file_debt_dimension(
                dimension_payload,
                dimension=dimension,
                label=f"{label}.files[{raw_path!r}].{dimension}",
            )

        normalized[rel_path] = normalized_dimensions

    return dict(sorted(normalized.items()))


def file_debt_ratchet_backslide_errors(
    base_state: dict[str, dict[str, dict[str, Any]]],
    head_state: dict[str, dict[str, dict[str, Any]]],
) -> list[str]:
    errors: list[str] = []

    for rel_path, base_dimensions in sorted(base_state.items()):
        head_dimensions = head_state.get(rel_path)
        if head_dimensions is None:
            continue

        for dimension, base_entry in sorted(base_dimensions.items()):
            head_entry = head_dimensions.get(dimension)
            if head_entry is None:
                continue

            if head_entry["allow_rebaseline"] and not base_entry["allow_rebaseline"]:
                errors.append(
                    f"Per-file debt ratchet loosened {dimension} rebaseline policy for {rel_path}. "
                    "Keep allow_rebaseline false in normal work."
                )

            base_rank = ratchet_context.FILE_DEBT_TOUCH_RULE_RANKS[dimension][base_entry["touch_rule"]]
            head_rank = ratchet_context.FILE_DEBT_TOUCH_RULE_RANKS[dimension][head_entry["touch_rule"]]
            if head_rank > base_rank:
                errors.append(
                    f"Per-file debt ratchet weakened {dimension} touch rule for {rel_path}: "
                    f"{base_entry['touch_rule']} -> {head_entry['touch_rule']}."
                )

            if dimension == "structural":
                if head_entry["current_baseline"] > base_entry["current_baseline"]:
                    errors.append(
                        f"Per-file structural debt baseline grew for {rel_path}: "
                        f"{base_entry['current_baseline']} -> {head_entry['current_baseline']}."
                    )
                if head_entry["target"] > base_entry["target"]:
                    errors.append(
                        f"Per-file structural debt target loosened for {rel_path}: "
                        f"{base_entry['target']} -> {head_entry['target']}."
                    )
            elif dimension == "coverage":
                if head_entry["current_baseline"] < base_entry["current_baseline"]:
                    errors.append(
                        f"Per-file coverage debt baseline decreased for {rel_path}: "
                        f"{base_entry['current_baseline']} -> {head_entry['current_baseline']}."
                    )
                if head_entry["target"] < base_entry["target"]:
                    errors.append(
                        f"Per-file coverage debt target decreased for {rel_path}: "
                        f"{base_entry['target']} -> {head_entry['target']}."
                    )

    return errors


def file_debt_surface_errors(file_debt_state: Mapping[str, dict[str, dict[str, Any]]]) -> list[str]:
    errors: list[str] = []
    for rel_path, dimensions in sorted(file_debt_state.items()):
        if rel_path.endswith(".md") and "structural" in dimensions:
            errors.append(f"Per-file structural debt must not target Markdown paths: {rel_path}.")
    return errors


def file_debt_ratchet_addition_errors(
    base_state: dict[str, dict[str, dict[str, Any]]],
    head_state: dict[str, dict[str, dict[str, Any]]],
    *,
    structural_exceptions: dict[str, dict[str, Any]],
    base_structural_exceptions: dict[str, dict[str, Any]],
    typing_debt_allowlist: Sequence[str],
    coverage_by_path: Mapping[str, int],
) -> list[str]:
    errors: list[str] = []
    typing_debt_paths = set(typing_debt_allowlist)

    for rel_path, head_dimensions in sorted(head_state.items()):
        base_dimensions = base_state.get(rel_path, {})
        for dimension, head_entry in sorted(head_dimensions.items()):
            if dimension in base_dimensions:
                continue

            if dimension == "structural":
                structural_exception = structural_exceptions.get(rel_path) or base_structural_exceptions.get(rel_path)
                if structural_exception is None:
                    errors.append(
                        f"Per-file structural debt entry for {rel_path} must mirror an existing structural file-line exception."
                    )
                    continue
                if head_entry["current_baseline"] != structural_exception["max_lines"]:
                    errors.append(
                        f"Per-file structural debt baseline for {rel_path} must match the checked-in structural exception: "
                        f"expected {structural_exception['max_lines']}, found {head_entry['current_baseline']}."
                    )
                if (
                    head_entry["current_baseline"] > head_entry["target"]
                    and head_entry["touch_rule"] == "must_not_grow"
                ):
                    errors.append(
                        f"Per-file structural debt entry for {rel_path} must use must_shrink or must_meet_target "
                        "to preserve inevitable convergence toward the target."
                    )
            elif dimension == "typing":
                if rel_path not in typing_debt_paths:
                    errors.append(
                        f"Per-file typing debt entry for {rel_path} must mirror tool.sattlint.typing_ratchet.debt_allowlist."
                    )
            elif dimension == "coverage":
                baseline_basis_points = coverage_by_path.get(rel_path)
                if baseline_basis_points is None:
                    errors.append(
                        f"Per-file coverage debt entry for {rel_path} must mirror an existing coverage.xml module entry."
                    )
                    continue
                if head_entry["current_baseline"] != baseline_basis_points:
                    errors.append(
                        f"Per-file coverage debt baseline for {rel_path} must match the current coverage.xml module rate: "
                        f"expected {baseline_basis_points}, found {head_entry['current_baseline']}."
                    )
                if head_entry["touch_rule"] != "must_reach_target_on_touch":
                    errors.append(
                        f"Per-file coverage debt entry for {rel_path} must use must_reach_target_on_touch in normal work."
                    )
                if head_entry["target"] != ratchet_context.NEW_SOURCE_FILE_COVERAGE_BASIS_POINTS:
                    errors.append(
                        f"Per-file coverage debt target for {rel_path} must be {ratchet_context.NEW_SOURCE_FILE_COVERAGE_BASIS_POINTS}."
                    )

    return errors


def coverage_basis_points(payload: dict[str, Any], label: str) -> int:
    metrics = metric_mapping(payload, label)
    value = metrics.get("min_line_rate_basis_points")
    if value is None:
        raise ValueError(f"{label} is missing metrics.min_line_rate_basis_points.")
    return value


def coverage_summary_basis_points(payload: dict[str, Any], label: str) -> int:
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        raise ValueError(f"{label} is missing a summary object.")

    raw_total_line_rate = summary.get("total_line_rate")
    try:
        total_line_rate = Decimal(str(raw_total_line_rate))
    except InvalidOperation as exc:
        raise ValueError(f"{label} summary.total_line_rate must be a decimal between 0 and 1.") from exc

    if total_line_rate < 0 or total_line_rate > 1:
        raise ValueError(f"{label} summary.total_line_rate must be between 0 and 1.")

    return int((total_line_rate * Decimal("10000")).quantize(Decimal("1")))


def expected_coverage_floor_basis_points(payload: dict[str, Any], label: str) -> int:
    baseline_basis_points = coverage_summary_basis_points(payload, label)
    return max(baseline_basis_points - ratchet_context.COVERAGE_FLOOR_BUFFER_BASIS_POINTS, 0)


def coverage_floor_decimal_from_basis_points(value: int) -> Decimal:
    return Decimal(value) / Decimal("100")


def cov_fail_under(text: str, label: str) -> Decimal:
    payload = ratchet_context.pyproject_payload(text, label)
    addopts = payload.get("tool", {}).get("pytest", {}).get("ini_options", {}).get("addopts", [])
    if not isinstance(addopts, list):
        raise ValueError(f"{label} addopts must be a list.")
    for entry in addopts:
        if not isinstance(entry, str):
            continue
        if not entry.startswith("--cov-fail-under="):
            continue
        raw_value = entry.split("=", 1)[1].strip()
        try:
            return Decimal(raw_value)
        except InvalidOperation as exc:
            raise ValueError(f"{label} has an invalid --cov-fail-under value: {raw_value!r}.") from exc
    raise ValueError(f"{label} is missing --cov-fail-under in [tool.pytest.ini_options].addopts.")


def normalize_coverage_filename(filename: str) -> str:
    normalized = filename.replace("\\", "/").lstrip("./")
    if not normalized:
        return ""
    if normalized.startswith(("src/", "tests/")):
        return normalized
    if normalized.startswith("/") or (len(normalized) > 1 and normalized[1] == ":"):
        return normalized
    return f"src/{normalized}"


def coverage_basis_points_by_path(repo_root: Path) -> dict[str, int]:
    coverage_path = repo_root / "coverage.xml"
    if not coverage_path.exists():
        return {}

    root_xml = ElementTree.fromstring(coverage_path.read_text(encoding="utf-8"))
    coverage_by_path: dict[str, int] = {}
    for class_node in root_xml.findall(".//class"):
        normalized_path = normalize_coverage_filename(class_node.attrib.get("filename", ""))
        if not normalized_path.startswith("src/"):
            continue
        line_rate = float(class_node.attrib.get("line-rate", "0") or 0)
        coverage_by_path[normalized_path] = round(line_rate * 10000)
    return coverage_by_path


def line_count(text: str) -> int:
    return len(text.splitlines())


def file_debt_runtime_errors(
    *,
    repo_root: Path,
    context: ratchet_context.ChangeContext,
    file_debt_state: dict[str, dict[str, dict[str, Any]]],
    structural_exceptions: Mapping[str, dict[str, Any]],
    typing_state: ratchet_context.TypingRatchetState,
    enforce_unlisted_source_coverage: bool = True,
    enforce_unlisted_structural_exception_size: bool = True,
) -> list[str]:
    touched_paths = tuple(path for path in context.changed_files if path in file_debt_state)
    unlisted_touched_paths = tuple(path for path in context.changed_files if path not in file_debt_state)
    if not touched_paths and not unlisted_touched_paths:
        return []

    errors: list[str] = []
    debt_allowlist = set(typing_state.debt_allowlist)
    structural_runtime_paths = tuple(
        path
        for path in dict.fromkeys(
            [
                *(path for path in touched_paths if "structural" in file_debt_state[path]),
                *(path for path in unlisted_touched_paths if path in structural_exceptions),
            ]
        )
    )
    current_text_by_path = ratchet_context.load_current_texts(
        repo_root, tuple(dict.fromkeys((*touched_paths, *structural_runtime_paths)))
    )
    base_text_by_path = ratchet_context.load_base_texts(repo_root, context.base_ref, touched_paths)
    needs_coverage = any("coverage" in file_debt_state[path] for path in touched_paths) or any(
        path.startswith("src/") and path.endswith(".py") for path in unlisted_touched_paths
    )
    coverage_by_path = coverage_basis_points_by_path(repo_root) if needs_coverage else {}

    for rel_path in touched_paths:
        dimensions = file_debt_state[rel_path]
        typing_entry = dimensions.get("typing")
        if typing_entry is not None and rel_path in debt_allowlist:
            errors.append(
                "Touched file in per-file typing debt ratchet remains in tool.sattlint.typing_ratchet.debt_allowlist: "
                f"{rel_path}. Touched typing-debt files must exit the allowlist."
            )

        structural_entry = dimensions.get("structural")
        current_text = current_text_by_path.get(rel_path)
        if structural_entry is not None and current_text is not None:
            current_lines = line_count(current_text)
            base_text = base_text_by_path.get(rel_path)
            baseline_lines = line_count(base_text) if base_text is not None else structural_entry["current_baseline"]
            touch_rule = effective_structural_touch_rule(structural_entry, baseline_lines=baseline_lines)
            if touch_rule == "must_shrink" and current_lines >= baseline_lines:
                errors.append(
                    f"Touched structural debt file did not shrink: {rel_path} remains {current_lines} lines "
                    f"against baseline {baseline_lines}."
                    + structural_debt_guidance(
                        rel_path=rel_path,
                        effective_touch_rule=touch_rule,
                        reason=str(structural_entry.get("reason", "")),
                    )
                )
            elif touch_rule == "must_meet_target" and current_lines > structural_entry["target"]:
                errors.append(
                    f"Touched structural debt file must meet target: {rel_path} is {current_lines} lines "
                    f"but target is {structural_entry['target']}."
                    + structural_debt_guidance(
                        rel_path=rel_path,
                        effective_touch_rule=touch_rule,
                        reason=str(structural_entry.get("reason", "")),
                    )
                )

        coverage_entry = dimensions.get("coverage")
        if coverage_entry is not None:
            basis_points = coverage_by_path.get(rel_path)
            if basis_points is None:
                errors.append(
                    f"Touched coverage debt file is missing from coverage.xml: {rel_path}. "
                    "Generate coverage before changing per-file coverage debt."
                )
                continue
            touch_rule = coverage_entry["touch_rule"]
            if touch_rule == "must_not_drop" and basis_points < coverage_entry["current_baseline"]:
                errors.append(
                    f"Touched coverage debt file regressed: {rel_path} {coverage_entry['current_baseline'] / 100:.2f}% -> "
                    f"{basis_points / 100:.2f}%."
                )
            elif touch_rule == "must_reach_target_on_touch" and basis_points < coverage_entry["target"]:
                errors.append(
                    f"Touched coverage debt file must reach target: {rel_path} is {basis_points / 100:.2f}% "
                    f"but target is {coverage_entry['target'] / 100:.2f}%."
                )

    for rel_path in unlisted_touched_paths:
        if enforce_unlisted_source_coverage and rel_path.startswith("src/") and rel_path.endswith(".py"):
            basis_points = coverage_by_path.get(rel_path)
            if basis_points is None:
                errors.append(
                    f"Touched source file missing per-file coverage debt entry is missing from coverage.xml: {rel_path}. "
                    "Unlisted touched source files must already meet the 100.00% coverage target."
                )
            elif basis_points < ratchet_context.NEW_SOURCE_FILE_COVERAGE_BASIS_POINTS:
                errors.append(
                    "Touched source file missing per-file coverage debt entry does not meet the 100.00% coverage target: "
                    f"{rel_path} is {basis_points / 100:.2f}%."
                )

        if enforce_unlisted_structural_exception_size and rel_path in structural_exceptions:
            current_text = current_text_by_path.get(rel_path)
            if current_text is None:
                continue
            current_lines = line_count(current_text)
            if current_lines > ratchet_context.NEW_PYTHON_FILE_LINE_LIMIT:
                errors.append(
                    "Touched structural exception file missing per-file debt entry does not meet the "
                    f"{ratchet_context.NEW_PYTHON_FILE_LINE_LIMIT}-line target: {rel_path} is {current_lines} lines."
                )

    return errors


def file_debt_stale_entry_errors(
    *,
    repo_root: Path,
    file_debt_state: Mapping[str, dict[str, dict[str, Any]]],
) -> list[str]:
    errors: list[str] = []
    structural_paths = tuple(
        rel_path for rel_path, dimensions in sorted(file_debt_state.items()) if "structural" in dimensions
    )
    if structural_paths:
        current_text_by_path = ratchet_context.load_current_texts(repo_root, structural_paths)
        for rel_path in structural_paths:
            current_text = current_text_by_path.get(rel_path)
            if current_text is None:
                continue
            target = int(file_debt_state[rel_path]["structural"]["target"])
            current_lines = line_count(current_text)
            if current_lines <= target:
                errors.append(
                    f"Per-file structural debt entry is stale for {rel_path}: current line count {current_lines} "
                    f"is at or below target {target}. Remove the structural entry from {ratchet_context.FILE_DEBT_RATCHET_PATH}."
                )

    coverage_paths = tuple(
        rel_path for rel_path, dimensions in sorted(file_debt_state.items()) if "coverage" in dimensions
    )
    if coverage_paths:
        coverage_by_path = coverage_basis_points_by_path(repo_root)
        for rel_path in coverage_paths:
            current_basis_points = coverage_by_path.get(rel_path)
            if current_basis_points is None:
                continue
            target = int(file_debt_state[rel_path]["coverage"]["target"])
            if current_basis_points >= target:
                errors.append(
                    f"Per-file coverage debt entry is stale for {rel_path}: current coverage {current_basis_points / 100:.2f}% "
                    f"meets or exceeds target {target / 100:.2f}%. Remove the coverage entry from {ratchet_context.FILE_DEBT_RATCHET_PATH}."
                )

    return errors
