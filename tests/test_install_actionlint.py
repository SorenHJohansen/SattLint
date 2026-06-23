from __future__ import annotations

import hashlib
import io
import tarfile
import zipfile
from pathlib import Path

import pytest

from scripts import install_actionlint


def _build_tar_gz(binary_name: str, content: bytes) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        info = tarfile.TarInfo(name=binary_name)
        info.size = len(content)
        info.mode = 0o755
        archive.addfile(info, io.BytesIO(content))
    return buffer.getvalue()


def _build_zip(binary_name: str, content: bytes) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w") as archive:
        archive.writestr(binary_name, content)
    return buffer.getvalue()


def test_install_actionlint_writes_verified_binary(tmp_path: Path) -> None:
    archive_bytes = _build_tar_gz("actionlint", b"#!/bin/sh\necho actionlint\n")
    expected_sha = hashlib.sha256(archive_bytes).hexdigest()
    chmod_calls: list[int] = []

    original_chmod = Path.chmod

    def record_chmod(self: Path, mode: int, /, *, follow_symlinks: bool = True) -> None:
        chmod_calls.append(mode)
        original_chmod(self, mode, follow_symlinks=follow_symlinks)

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(Path, "chmod", record_chmod)

    try:
        installed_path = install_actionlint.install_actionlint(
            version="1.7.12",
            sha256=expected_sha,
            bin_dir=tmp_path,
            system="Linux",
            machine="x86_64",
            download_archive=lambda url: archive_bytes,
        )
    finally:
        monkeypatch.undo()

    assert installed_path == tmp_path.resolve() / "actionlint"
    assert installed_path.read_bytes() == b"#!/bin/sh\necho actionlint\n"
    assert chmod_calls
    assert chmod_calls[-1] & 0o111


def test_install_actionlint_writes_windows_binary(tmp_path: Path) -> None:
    archive_bytes = _build_zip("actionlint.exe", b"MZ-actionlint")
    expected_sha = hashlib.sha256(archive_bytes).hexdigest()

    installed_path = install_actionlint.install_actionlint(
        version="1.7.12",
        sha256=expected_sha,
        bin_dir=tmp_path,
        system="Windows",
        machine="x86_64",
        download_archive=lambda url: archive_bytes,
    )

    assert installed_path == tmp_path.resolve() / "actionlint.exe"
    assert installed_path.read_bytes() == b"MZ-actionlint"


def test_install_actionlint_rejects_checksum_mismatch(tmp_path: Path) -> None:
    archive_bytes = _build_tar_gz("actionlint", b"binary-data")

    with pytest.raises(install_actionlint.ChecksumMismatchError):
        install_actionlint.install_actionlint(
            version="1.7.12",
            sha256="0" * 64,
            bin_dir=tmp_path,
            system="Linux",
            machine="x86_64",
            download_archive=lambda url: archive_bytes,
        )

    assert not (tmp_path / "actionlint").exists()


def test_resolve_release_target_rejects_unsupported_platform() -> None:
    with pytest.raises(install_actionlint.UnsupportedPlatformError):
        install_actionlint.resolve_release_target(system="Plan9", machine="mips64")
