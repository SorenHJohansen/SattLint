from __future__ import annotations

from pathlib import Path
from typing import Any

_WORKFLOW_DOWNLOAD_TOKENS = ("curl ", "curl\t", "wget ", "invoke-webrequest", "invoke-restmethod")
_CHECKSUM_MARKERS = ("sha256", "shasum", "get-filehash", "checksum")
_DB_BIND_MARKERS = ("0.0.0.0:", "--bind 0.0.0.0")
_DB_CREDENTIAL_MARKERS = ("--user root", "--pass root", "root/root", "user=root", "password=root")


def _repo_audit_module() -> Any:
    from . import repo_audit as repo_audit_module  # noqa: PLC0415

    return repo_audit_module


def _tracked_path_present(root: Path, tracked_path_set: set[str] | None, rel_path: str) -> bool:
    return (root / rel_path).exists() if tracked_path_set is None else rel_path in tracked_path_set


def _read_tracked_text(root: Path, *, tracked_path_set: set[str] | None, rel_path: str) -> str | None:
    if tracked_path_set is not None and rel_path not in tracked_path_set:
        return None
    path = root / rel_path
    if not path.exists() or not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def _leading_spaces(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _find_yamlish_block(lines: list[str], key: str, *, indent: int) -> tuple[int | None, list[tuple[int, str]]]:
    for index, line in enumerate(lines, start=1):
        if _leading_spaces(line) != indent or line.strip() != f"{key}:":
            continue
        block: list[tuple[int, str]] = []
        for next_index in range(index + 1, len(lines) + 1):
            next_line = lines[next_index - 1]
            if next_line.strip() and _leading_spaces(next_line) <= indent:
                break
            block.append((next_index, next_line))
        return index, block
    return None, []


def _iter_tracked_workflow_paths(root: Path, *, tracked_path_set: set[str] | None) -> tuple[str, ...]:
    if tracked_path_set is None:
        workflow_dir = root / ".github" / "workflows"
        if not workflow_dir.exists():
            return ()
        return tuple(sorted(path.relative_to(root).as_posix() for path in workflow_dir.glob("*.y*ml")))
    return tuple(
        sorted(
            rel_path
            for rel_path in tracked_path_set
            if rel_path.startswith(".github/workflows/") and rel_path.endswith((".yml", ".yaml"))
        )
    )


def _manifest_directory(rel_path: str) -> str:
    if "/" not in rel_path:
        return "/"
    return f"/{rel_path.rsplit('/', 1)[0]}"


def _node_manifest_directories(root: Path, *, tracked_path_set: set[str] | None) -> tuple[str, ...]:
    if tracked_path_set is None:
        rel_paths = [
            path.relative_to(root).as_posix()
            for pattern in ("package.json", "package-lock.json")
            for path in root.rglob(pattern)
            if path.is_file() and "/node_modules/" not in f"/{path.relative_to(root).as_posix()}"
        ]
    else:
        rel_paths = [
            rel_path
            for rel_path in tracked_path_set
            if Path(rel_path).name in {"package.json", "package-lock.json"} and "/node_modules/" not in f"/{rel_path}"
        ]
    return tuple(sorted({_manifest_directory(rel_path) for rel_path in rel_paths}))


def _dependabot_directories(text: str, *, ecosystem: str) -> set[str]:
    directories: set[str] = set()
    current_ecosystem: str | None = None
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("- package-ecosystem:"):
            current_ecosystem = stripped.split(":", 1)[1].strip().strip("\"'")
            continue
        if stripped.startswith("package-ecosystem:"):
            current_ecosystem = stripped.split(":", 1)[1].strip().strip("\"'")
            continue
        if current_ecosystem != ecosystem or not stripped.startswith("directory:"):
            continue
        directories.add(stripped.split(":", 1)[1].strip().strip("\"'"))
    return directories


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


def _publish_workflow_security_findings(root: Path, *, tracked_path_set: set[str] | None) -> list[Any]:
    repo_audit = _repo_audit_module()
    rel_path = ".github/workflows/publish.yml"
    workflow_text = _read_tracked_text(root, tracked_path_set=tracked_path_set, rel_path=rel_path)
    if workflow_text is None:
        return []

    id_token_permission = "-".join(("id", "token")) + ":"
    write_permission = "write"
    lines = workflow_text.splitlines()
    findings: list[Any] = []

    _, permissions_block = _find_yamlish_block(lines, "permissions", indent=0)
    for line_number, line in permissions_block:
        stripped = line.strip().casefold()
        if stripped.startswith(id_token_permission) and write_permission in stripped:
            findings.append(
                repo_audit.Finding(
                    id="workflow-level-id-token-write",
                    category="public-readiness",
                    severity="high",
                    confidence="high",
                    message="Publish workflow grants id-token write permission at workflow scope.",
                    path=rel_path,
                    line=line_number,
                    suggestion="Move id-token: write to the publish job so only the PyPI publish step receives OIDC credentials.",
                )
            )
            break

    publish_line, publish_block = _find_yamlish_block(lines, "publish", indent=2)
    if publish_line is None:
        return findings

    publish_block_text = "\n".join(line for _, line in publish_block).casefold()
    has_environment = any(
        _leading_spaces(line) == 4 and line.strip().startswith("environment:") for _, line in publish_block
    )
    if not has_environment:
        findings.append(
            repo_audit.Finding(
                id="publish-workflow-missing-environment",
                category="public-readiness",
                severity="high",
                confidence="high",
                message="Publish workflow does not declare a protected release environment on the publish job.",
                path=rel_path,
                line=publish_line,
                suggestion="Declare a protected GitHub Actions environment on the publish job before PyPI publication.",
            )
        )

    publish_is_tag_guarded = (
        "github.event_name == 'push'" in publish_block_text
        and "startswith(github.ref, 'refs/tags/v')" in publish_block_text
    )
    if not publish_is_tag_guarded:
        findings.append(
            repo_audit.Finding(
                id="publish-workflow-missing-tag-guard",
                category="public-readiness",
                severity="high",
                confidence="high",
                message="Publish workflow does not clearly restrict the publish job to real version-tag pushes.",
                path=rel_path,
                line=publish_line,
                suggestion="Guard the publish job with a push-and-tag condition so workflow_dispatch rehearsals cannot publish.",
            )
        )

    return findings


def _workflow_download_findings(root: Path, *, tracked_path_set: set[str] | None) -> list[Any]:
    repo_audit = _repo_audit_module()
    findings: list[Any] = []
    for rel_path in _iter_tracked_workflow_paths(root, tracked_path_set=tracked_path_set):
        workflow_text = _read_tracked_text(root, tracked_path_set=tracked_path_set, rel_path=rel_path)
        if workflow_text is None:
            continue
        lowered_lines = [line.casefold() for line in workflow_text.splitlines()]
        for index, lowered in enumerate(lowered_lines, start=1):
            if not any(token in lowered for token in _WORKFLOW_DOWNLOAD_TOKENS):
                continue
            if "https://" not in lowered and "http://" not in lowered:
                continue
            window = "\n".join(lowered_lines[max(0, index - 2) : min(len(lowered_lines), index + 5)])
            if any(marker in window for marker in _CHECKSUM_MARKERS):
                continue
            findings.append(
                repo_audit.Finding(
                    id="workflow-download-without-verification",
                    category="public-readiness",
                    severity="medium",
                    confidence="medium",
                    message="Workflow downloads an external artifact without visible checksum verification.",
                    path=rel_path,
                    line=index,
                    detail=workflow_text.splitlines()[index - 1].strip(),
                    suggestion="Use a pinned action or verify the downloaded artifact checksum before execution.",
                )
            )
            break
    return findings


def _npm_monitoring_findings(root: Path, *, tracked_path_set: set[str] | None) -> list[Any]:
    repo_audit = _repo_audit_module()
    manifest_directories = _node_manifest_directories(root, tracked_path_set=tracked_path_set)
    if not manifest_directories:
        return []

    dependabot_rel_path = ".github/dependabot.yml"
    dependabot_text = _read_tracked_text(root, tracked_path_set=tracked_path_set, rel_path=dependabot_rel_path)
    monitored_directories: set[str] = (
        set() if dependabot_text is None else _dependabot_directories(dependabot_text, ecosystem="npm")
    )
    missing_directories = [directory for directory in manifest_directories if directory not in monitored_directories]
    if not missing_directories:
        return []
    return [
        repo_audit.Finding(
            id="missing-npm-dependabot-monitoring",
            category="public-readiness",
            severity="medium",
            confidence="high",
            message="Node package manifests are tracked, but Dependabot does not monitor them with an npm update entry.",
            path=dependabot_rel_path,
            detail=", ".join(missing_directories),
            suggestion="Add an npm Dependabot entry for each tracked package.json or package-lock.json directory.",
        )
    ]


def _unsafe_helper_script_findings(root: Path, *, tracked_path_set: set[str] | None) -> list[Any]:
    repo_audit = _repo_audit_module()
    if tracked_path_set is None:
        rel_paths = tuple(
            sorted(path.relative_to(root).as_posix() for path in (root / "scripts").rglob("*") if path.is_file())
        )
    else:
        rel_paths = tuple(sorted(rel_path for rel_path in tracked_path_set if rel_path.startswith("scripts/")))

    findings: list[Any] = []
    for rel_path in rel_paths:
        script_text = _read_tracked_text(root, tracked_path_set=tracked_path_set, rel_path=rel_path)
        if script_text is None:
            continue
        lowered = script_text.casefold()
        if not any(marker in lowered for marker in _DB_BIND_MARKERS):
            continue
        if not any(marker in lowered for marker in _DB_CREDENTIAL_MARKERS):
            continue
        line_number = next(
            (
                index
                for index, line in enumerate(script_text.splitlines(), start=1)
                if any(marker in line.casefold() for marker in _DB_BIND_MARKERS + _DB_CREDENTIAL_MARKERS)
            ),
            1,
        )
        findings.append(
            repo_audit.Finding(
                id="unsafe-local-db-helper",
                category="public-readiness",
                severity="high",
                confidence="high",
                message="Helper script exposes a local database surface with all-interface bind and hardcoded credentials.",
                path=rel_path,
                line=line_number,
                suggestion="Remove the helper or require explicit local-only configuration instead of checked-in default credentials.",
            )
        )
    return findings


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
    findings.extend(_publish_workflow_security_findings(root, tracked_path_set=tracked_path_set))
    findings.extend(_workflow_download_findings(root, tracked_path_set=tracked_path_set))
    findings.extend(_npm_monitoring_findings(root, tracked_path_set=tracked_path_set))
    findings.extend(_unsafe_helper_script_findings(root, tracked_path_set=tracked_path_set))
    findings.extend(_tracked_generated_findings(root, tracked_paths=tracked_paths, tracked_path_set=tracked_path_set))
    findings.extend(_unexpected_root_entry_findings(root, tracked_paths=tracked_paths))
    return findings


__all__ = ["_find_public_readiness_findings"]
