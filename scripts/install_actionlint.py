from __future__ import annotations

import argparse
import hashlib
import io
import os
import platform
import stat
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

DEFAULT_RELEASE_URL_BASE = "https://github.com/rhysd/actionlint/releases/download"


class _ArchiveDownloader(Protocol):
    def __call__(self, url: str) -> bytes: ...


@dataclass(frozen=True, slots=True)
class ActionlintReleaseTarget:
    os_name: str
    arch_name: str
    archive_format: Literal["tar.gz", "zip"]
    binary_name: str


SUPPORTED_TARGETS: dict[tuple[str, str], ActionlintReleaseTarget] = {
    ("linux", "x86_64"): ActionlintReleaseTarget("linux", "amd64", "tar.gz", "actionlint"),
    ("linux", "amd64"): ActionlintReleaseTarget("linux", "amd64", "tar.gz", "actionlint"),
    ("linux", "aarch64"): ActionlintReleaseTarget("linux", "arm64", "tar.gz", "actionlint"),
    ("darwin", "x86_64"): ActionlintReleaseTarget("darwin", "amd64", "tar.gz", "actionlint"),
    ("darwin", "arm64"): ActionlintReleaseTarget("darwin", "arm64", "tar.gz", "actionlint"),
    ("windows", "amd64"): ActionlintReleaseTarget("windows", "amd64", "zip", "actionlint.exe"),
    ("windows", "x86_64"): ActionlintReleaseTarget("windows", "amd64", "zip", "actionlint.exe"),
    ("windows", "arm64"): ActionlintReleaseTarget("windows", "arm64", "zip", "actionlint.exe"),
}


class InstallActionlintError(RuntimeError):
    """Base error for installer failures."""


class UnsupportedPlatformError(InstallActionlintError):
    """Raised when the current platform has no known upstream asset."""


class ChecksumMismatchError(InstallActionlintError):
    """Raised when the downloaded archive does not match the expected digest."""


class ArchiveExtractionError(InstallActionlintError):
    """Raised when the expected binary is missing from the release archive."""


def _normalize_version(version: str) -> str:
    normalized = version.strip().removeprefix("v")
    if not normalized:
        raise ValueError("version must not be empty")
    return normalized


def resolve_release_target(*, system: str | None = None, machine: str | None = None) -> ActionlintReleaseTarget:
    resolved_system = (system or platform.system()).casefold()
    resolved_machine = (machine or platform.machine()).casefold()
    target = SUPPORTED_TARGETS.get((resolved_system, resolved_machine))
    if target is None:
        raise UnsupportedPlatformError(
            f"Unsupported actionlint platform: system={system or platform.system()!r}, machine={machine or platform.machine()!r}"
        )
    return target


def build_download_url(
    version: str,
    target: ActionlintReleaseTarget,
    *,
    release_url_base: str = DEFAULT_RELEASE_URL_BASE,
) -> str:
    normalized_version = _normalize_version(version)
    filename = f"actionlint_{normalized_version}_{target.os_name}_{target.arch_name}.{target.archive_format}"
    return f"{release_url_base}/v{normalized_version}/{filename}"


def _download_archive(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "sattlint-actionlint-installer/1"})
    with urllib.request.urlopen(request) as response:
        return response.read()


def _verify_checksum(archive_bytes: bytes, expected_sha256: str) -> None:
    normalized_expected = expected_sha256.strip().casefold()
    if len(normalized_expected) != 64:
        raise ValueError("sha256 must be a 64-character hex digest")
    actual_sha256 = hashlib.sha256(archive_bytes).hexdigest()
    if actual_sha256.casefold() != normalized_expected:
        raise ChecksumMismatchError(
            f"actionlint archive checksum mismatch: expected {normalized_expected}, got {actual_sha256.casefold()}"
        )


def _extract_binary(archive_bytes: bytes, target: ActionlintReleaseTarget) -> bytes:
    try:
        if target.archive_format == "tar.gz":
            with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:gz") as archive:
                for member in archive.getmembers():
                    if member.isfile() and Path(member.name).name == target.binary_name:
                        extracted = archive.extractfile(member)
                        if extracted is None:
                            break
                        return extracted.read()
        else:
            with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
                for member_name in archive.namelist():
                    if Path(member_name).name == target.binary_name:
                        return archive.read(member_name)
    except (tarfile.TarError, zipfile.BadZipFile) as error:
        raise ArchiveExtractionError(f"Failed to extract actionlint archive: {error}") from error
    raise ArchiveExtractionError(f"actionlint binary {target.binary_name!r} not found in archive")


def _write_binary(destination: Path, binary_bytes: bytes) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, dir=destination.parent, prefix=f"{destination.name}.") as handle:
            handle.write(binary_bytes)
            temp_path = Path(handle.name)
        current_mode = temp_path.stat().st_mode
        temp_path.chmod(current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        os.replace(temp_path, destination)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def install_actionlint(
    *,
    version: str,
    sha256: str,
    bin_dir: Path,
    system: str | None = None,
    machine: str | None = None,
    release_url_base: str = DEFAULT_RELEASE_URL_BASE,
    download_archive: _ArchiveDownloader = _download_archive,
) -> Path:
    target = resolve_release_target(system=system, machine=machine)
    url = build_download_url(version, target, release_url_base=release_url_base)
    archive_bytes = download_archive(url)
    _verify_checksum(archive_bytes, sha256)
    binary_bytes = _extract_binary(archive_bytes, target)
    destination = bin_dir.resolve() / target.binary_name
    _write_binary(destination, binary_bytes)
    return destination


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Download and install a checksum-verified actionlint release.")
    parser.add_argument("--version", required=True, help="actionlint version, for example 1.7.12")
    parser.add_argument("--sha256", required=True, help="Expected SHA-256 digest for the selected platform archive")
    parser.add_argument(
        "--bin-dir", required=True, type=Path, help="Directory that should receive the actionlint binary"
    )
    parser.add_argument("--system", help="Optional platform.system() override for testing")
    parser.add_argument("--machine", help="Optional platform.machine() override for testing")
    parser.add_argument(
        "--release-url-base",
        default=DEFAULT_RELEASE_URL_BASE,
        help="Override the GitHub release download base URL for tests or mirrors",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        installed_path = install_actionlint(
            version=args.version,
            sha256=args.sha256,
            bin_dir=args.bin_dir,
            system=args.system,
            machine=args.machine,
            release_url_base=args.release_url_base,
        )
    except (InstallActionlintError, OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 2

    print(installed_path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
