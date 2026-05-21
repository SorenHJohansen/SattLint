from __future__ import annotations

from pathlib import Path
from typing import Any


def _repo_audit_module() -> Any:
    from sattlint.devtools import repo_audit as repo_audit_module

    return repo_audit_module


def _tracked_path_present(root: Path, tracked_path_set: set[str] | None, rel_path: str) -> bool:
    return (root / rel_path).exists() if tracked_path_set is None else rel_path in tracked_path_set


def _missing_required_public_files(root: Path, *, tracked_path_set: set[str] | None) -> list[Any]:
    repo_audit = _repo_audit_module()
    findings: list[Any] = []
    for filename in ("README.md", "LICENSE", "CONTRIBUTING.md", ".gitignore"):
        if _tracked_path_present(root, tracked_path_set, filename):
            continue
        findings.append(
            repo_audit.Finding(
                id="missing-public-file",
                category="public-readiness",
                severity="high",
                confidence="high",
                message=f"Expected public-facing file '{filename}' is missing.",
                path=filename,
                suggestion="Add the missing file before publishing the repository.",
            )
        )
    return findings


def _missing_support_documents(root: Path, *, tracked_path_set: set[str] | None) -> list[Any]:
    repo_audit = _repo_audit_module()
    support_files = ["SECURITY.md", "CODE_OF_CONDUCT.md", "SUPPORT.md", "docs/references/public-support-matrix.md"]
    missing_support_files = [
        filename for filename in support_files if not _tracked_path_present(root, tracked_path_set, filename)
    ]
    if not missing_support_files:
        return []
    return [
        repo_audit.Finding(
            id="missing-public-support-file",
            category="public-readiness",
            severity="high",
            confidence="high",
            message="Public support documentation is incomplete.",
            path=missing_support_files[0],
            detail=", ".join(missing_support_files[:5]) + (" ..." if len(missing_support_files) > 5 else ""),
            suggestion="Add the missing security, conduct, support, and support-matrix docs before publishing.",
        )
    ]


def _missing_project_url_findings(root: Path) -> list[Any]:
    repo_audit = _repo_audit_module()
    pyproject = repo_audit._load_pyproject(root)
    urls = pyproject.get("project", {}).get("urls", {})
    if urls:
        return []
    return [
        repo_audit.Finding(
            id="missing-project-urls",
            category="public-readiness",
            severity="low",
            confidence="high",
            message="pyproject metadata does not declare project URLs.",
            path="pyproject.toml",
            suggestion="Add homepage, repository, and issue tracker URLs.",
        )
    ]


def _readme_public_link_findings(root: Path) -> list[Any]:
    repo_audit = _repo_audit_module()
    readme_path = root / "README.md"
    if not readme_path.exists():
        return []
    try:
        readme_text = readme_path.read_text(encoding="utf-8")
    except OSError as exc:
        return [
            repo_audit.Finding(
                id="unreadable-public-file",
                category="public-readiness",
                severity="medium",
                confidence="medium",
                message="README.md could not be read to validate public support links.",
                path="README.md",
                detail=str(exc),
                suggestion="Ensure README.md is readable as UTF-8 text.",
            )
        ]

    required_readme_links = ["SUPPORT.md", "SECURITY.md", "docs/references/public-support-matrix.md"]
    missing_readme_links = [link for link in required_readme_links if link not in readme_text]
    if not missing_readme_links:
        return []
    return [
        repo_audit.Finding(
            id="missing-readme-public-links",
            category="public-readiness",
            severity="medium",
            confidence="high",
            message="README.md does not point users at the public support policy documents.",
            path="README.md",
            detail=", ".join(missing_readme_links),
            suggestion="Link README.md to SUPPORT.md, SECURITY.md, and the public support matrix.",
        )
    ]


def _ci_workflow_findings(root: Path, *, tracked_path_set: set[str] | None) -> list[Any]:
    repo_audit = _repo_audit_module()
    if tracked_path_set is None:
        workflow_dir = root / ".github" / "workflows"
        has_workflow = workflow_dir.exists() and any(workflow_dir.glob("*.y*ml"))
    else:
        has_workflow = any(
            rel_path.startswith(".github/workflows/") and rel_path.endswith((".yml", ".yaml"))
            for rel_path in tracked_path_set
        )
    if has_workflow:
        return []
    return [
        repo_audit.Finding(
            id="missing-ci-workflow",
            category="public-readiness",
            severity="medium",
            confidence="high",
            message="Repository does not define a CI workflow.",
            path=".github/workflows",
            suggestion="Add an audit or test workflow so external contributors get immediate feedback.",
        )
    ]


def _tracked_generated_findings(
    root: Path,
    *,
    tracked_paths: tuple[str, ...] | None,
    tracked_path_set: set[str] | None,
) -> list[Any]:
    repo_audit = _repo_audit_module()
    tracked = list(tracked_paths or ())
    if not tracked and tracked_path_set is None:
        git_executable = repo_audit.shutil.which("git")
        completed = None
        if git_executable is not None:
            try:
                completed = repo_audit.subprocess.run(  # nosec B603 - fixed git command with controlled arguments
                    [git_executable, "ls-files", "artifacts", "build", "htmlcov", "coverage.xml"],
                    cwd=root,
                    capture_output=True,
                    text=True,
                    check=False,
                )
            except OSError:
                completed = None
        if completed and completed.returncode == 0:
            tracked = [line.strip() for line in completed.stdout.splitlines() if line.strip()]

    generated = [
        line
        for line in tracked
        if any(line == prefix or line.startswith(prefix) for prefix in repo_audit.GENERATED_PATH_PREFIXES)
    ]
    if not generated:
        return []
    generated_scope_path = generated[0].split("/", 1)[0]
    return [
        repo_audit.Finding(
            id="tracked-generated-artifacts",
            category="public-readiness",
            severity="high",
            confidence="high",
            message="Generated artifacts are tracked in git and may embed workstation-specific data.",
            path=generated_scope_path,
            detail=", ".join(generated[:5]) + (" ..." if len(generated) > 5 else ""),
            suggestion="Remove generated outputs from version control and consider history cleanup for already-published leaks.",
            history_cleanup_recommended=True,
        )
    ]


def _unexpected_root_entry_findings(root: Path, *, tracked_paths: tuple[str, ...] | None) -> list[Any]:
    repo_audit = _repo_audit_module()
    tracked_top_level_entries = sorted(
        {
            rel_path.split("/", 1)[0]
            for rel_path in (
                tracked_paths if tracked_paths is not None else (repo_audit._list_tracked_repo_paths(root) or ())
            )
            if rel_path
        }
    )
    unexpected_root_entries = [
        entry for entry in tracked_top_level_entries if entry not in repo_audit.TOP_LEVEL_TRACKED_ENTRY_ALLOWLIST
    ]
    if not unexpected_root_entries:
        return []
    return [
        repo_audit.Finding(
            id="unexpected-tracked-root-entry",
            category="public-readiness",
            severity="medium",
            confidence="high",
            message="Repository root contains tracked helper or scratch entries outside the approved top-level layout.",
            path=unexpected_root_entries[0],
            detail=", ".join(unexpected_root_entries[:5]) + (" ..." if len(unexpected_root_entries) > 5 else ""),
            suggestion="Move reusable tooling under scripts/ or another owner directory, and delete one-off scratch files from the repo root.",
        )
    ]


def _find_public_readiness_findings(
    root: Path,
    *,
    tracked_paths: tuple[str, ...] | None = None,
) -> list[Any]:
    tracked_path_set = None if tracked_paths is None else set(tracked_paths)
    findings: list[Any] = []
    findings.extend(_missing_required_public_files(root, tracked_path_set=tracked_path_set))
    findings.extend(_missing_support_documents(root, tracked_path_set=tracked_path_set))
    findings.extend(_missing_project_url_findings(root))
    findings.extend(_readme_public_link_findings(root))
    findings.extend(_ci_workflow_findings(root, tracked_path_set=tracked_path_set))
    findings.extend(_tracked_generated_findings(root, tracked_paths=tracked_paths, tracked_path_set=tracked_path_set))
    findings.extend(_unexpected_root_entry_findings(root, tracked_paths=tracked_paths))
    return findings


__all__ = ["_find_public_readiness_findings"]
