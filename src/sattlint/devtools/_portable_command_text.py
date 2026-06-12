from __future__ import annotations


def repo_python_command(*args: str) -> str:
    parts = ["python", "scripts/run_repo_python.py", *args]
    return " ".join(part for part in parts if part)


def pytest_command(*args: str) -> str:
    return repo_python_command("-m", "pytest", *args)


def pyright_command(*args: str) -> str:
    return repo_python_command("-m", "pyright", *args)


def ruff_command(*args: str) -> str:
    return repo_python_command("-m", "ruff", *args)


def sattlint_command(*args: str) -> str:
    return repo_python_command("-m", "sattlint", *args)


def repo_audit_command(*args: str) -> str:
    return repo_python_command("-m", "sattlint.devtools.audit", *args)
