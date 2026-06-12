"""Parsing and metadata helpers for the analysis pipeline."""

from __future__ import annotations

import importlib.metadata as metadata
import json
import tomllib
from pathlib import Path
from re import Pattern
from typing import Any

from defusedxml import ElementTree  # type: ignore[import-untyped]


def read_pyproject(pyproject_path: Path) -> dict[str, Any]:
    raw = pyproject_path.read_bytes()
    for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            return tomllib.loads(raw.decode(encoding))
        except (UnicodeDecodeError, tomllib.TOMLDecodeError):
            continue
    return tomllib.loads(raw.decode("utf-8", errors="replace"))


def tool_version(package_name: str) -> str | None:
    try:
        return metadata.version(package_name)
    except metadata.PackageNotFoundError:
        return None


def parse_json_lines(raw_output: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line in raw_output.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        records.append(json.loads(stripped))
    return records


def parse_vulture_output(raw_output: str, line_re: Pattern[str]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for line in raw_output.splitlines():
        match = line_re.match(line.strip())
        if match is None:
            continue
        findings.append(
            {
                "file": match.group("file"),
                "line": int(match.group("line")),
                "message": match.group("message"),
                "confidence": int(match.group("confidence")),
            }
        )
    return findings


def parse_pytest_junit(xml_path: Path) -> dict[str, Any]:
    root = ElementTree.fromstring(xml_path.read_text(encoding="utf-8"))
    suites = root.findall("testsuite") if root.tag == "testsuites" else [root]
    testcases: list[dict[str, Any]] = []
    summary = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    for suite in suites:
        summary["tests"] += int(suite.attrib.get("tests", 0))
        summary["failures"] += int(suite.attrib.get("failures", 0))
        summary["errors"] += int(suite.attrib.get("errors", 0))
        summary["skipped"] += int(suite.attrib.get("skipped", 0))
        for testcase in suite.findall("testcase"):
            failure = testcase.find("failure")
            error = testcase.find("error")
            skipped = testcase.find("skipped")
            if failure is not None:
                outcome = "failed"
                detail = failure.attrib.get("message") or (failure.text or "")
            elif error is not None:
                outcome = "error"
                detail = error.attrib.get("message") or (error.text or "")
            elif skipped is not None:
                outcome = "skipped"
                detail = skipped.attrib.get("message") or (skipped.text or "")
            else:
                outcome = "passed"
                detail = ""
            testcases.append(
                {
                    "classname": testcase.attrib.get("classname", ""),
                    "name": testcase.attrib.get("name", ""),
                    "time": testcase.attrib.get("time", "0"),
                    "outcome": outcome,
                    "detail": detail.strip(),
                }
            )
    return {"summary": summary, "testcases": testcases}


__all__ = [
    "ElementTree",
    "parse_json_lines",
    "parse_pytest_junit",
    "parse_vulture_output",
    "read_pyproject",
    "tool_version",
]
