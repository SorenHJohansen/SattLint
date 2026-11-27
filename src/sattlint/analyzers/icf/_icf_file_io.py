"""ICF file decoding and parsing helpers."""

from __future__ import annotations

import codecs
import re
from pathlib import Path

from ...reporting.icf_report import ICFEntry

_ICF_HEADER_RE = re.compile(r"^\[(?P<tag>[^\]\s]+)(?:\s+(?P<label>.+?))?\]$")
_ICF_PLACEHOLDER_RE = re.compile(r"^[A-Za-z]::\.$")
_ICF_VALUE_PREFIX_RE = re.compile(r"^(?P<prefix>[A-Za-z])::")

#: Read size for a bounded ICF read. A rejected file stops at the limit, so
#: this only decides how many bytes are held before the rejection is raised.
_ICF_READ_CHUNK_BYTES = 1024 * 1024


class IcfFileTooLargeError(ValueError):
    """An ICF file is larger than the configured byte limit."""

    def __init__(self, file_path: Path, *, observed_bytes: int, limit: int) -> None:
        self.file_path = file_path
        self.observed_bytes = observed_bytes
        self.limit = limit
        super().__init__(
            f"ICF file {file_path} is at least {observed_bytes} bytes, above [analysis].icf_byte_limit "
            f"of {limit} bytes. Raise the limit or exclude the file."
        )


def _cf(value: str) -> str:
    return value.casefold()


def decode_icf_text(raw_bytes: bytes) -> tuple[str, str, bool]:
    if raw_bytes.startswith(codecs.BOM_UTF8):
        bom_stripped = raw_bytes[len(codecs.BOM_UTF8) :]
        try:
            return bom_stripped.decode("utf-8"), "utf-8", True
        except UnicodeDecodeError:
            raw_bytes = bom_stripped

    for encoding in ("utf-8", "cp1252", "latin-1"):
        try:
            return raw_bytes.decode(encoding), encoding, False
        except UnicodeDecodeError:
            continue
    return raw_bytes.decode("latin-1", errors="replace"), "latin-1", False


def _read_icf_bytes(file_path: Path, max_bytes: int | None) -> bytes:
    """Read an ICF file without ever holding more than ``max_bytes`` bytes.

    The stat check rejects a file that is already known to be too large, and
    the chunk loop covers a file that grows between the stat and the read.
    """
    if max_bytes is None:
        return file_path.read_bytes()

    observed_bytes = file_path.stat().st_size
    if observed_bytes > max_bytes:
        raise IcfFileTooLargeError(file_path, observed_bytes=observed_bytes, limit=max_bytes)

    chunks: list[bytes] = []
    total_bytes = 0
    with file_path.open("rb") as file_handle:
        while True:
            # Read at most one byte past the limit, so a file that grew after
            # the stat is rejected without ever being held whole.
            chunk = file_handle.read(min(_ICF_READ_CHUNK_BYTES, max_bytes - total_bytes + 1))
            if not chunk:
                break
            total_bytes += len(chunk)
            if total_bytes > max_bytes:
                raise IcfFileTooLargeError(file_path, observed_bytes=total_bytes, limit=max_bytes)
            chunks.append(chunk)
    return b"".join(chunks)


def parse_icf_file(file_path: Path, *, max_bytes: int | None = None) -> list[ICFEntry]:
    """Parse a .icf file into key/value entries with section and line number info.

    ``max_bytes`` caps the bytes read from the file. The default ``None`` keeps
    the historical unlimited read for direct callers; the analyzer always
    passes the configured limit.
    """
    entries: list[ICFEntry] = []
    section: str | None = None
    unit: str | None = None
    operation: str | None = None
    journal: str | None = None
    group: str | None = None

    raw_bytes = _read_icf_bytes(file_path, max_bytes)
    text, _encoding, _has_utf8_bom = decode_icf_text(raw_bytes)

    for idx, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith(";") or line.startswith("#"):
            continue

        header_match = _ICF_HEADER_RE.match(line)
        if header_match:
            tag = header_match.group("tag").strip()
            label = (header_match.group("label") or "").strip() or None
            section = f"{tag} {label}".strip() if label else tag
            tag_key = _cf(tag)
            if tag_key == "unit":
                unit = label
                operation = None
                journal = None
                group = None
            elif tag_key == "operation":
                operation = label
                journal = None
                group = None
            elif tag_key == "journal":
                journal = label
                group = None
            elif tag_key == "group":
                group = label
            else:
                operation = None
                journal = None
                group = None
            continue

        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        entries.append(
            ICFEntry(
                file_path=file_path,
                line_no=idx,
                section=section,
                key=key.strip(),
                value=value.strip(),
                unit=unit,
                operation=operation,
                journal=journal,
                group=group,
            )
        )

    return entries


def _without_value_prefix(value: str) -> str:
    """Remove one leading single-letter value prefix such as ``F::``.

    The scan is linear: it walks the ``::`` occurrences once and stops at the
    first one whose preceding character is an ASCII letter. Text before the
    prefix is discarded, which keeps values such as ``note F::Program:Path``
    working without a backtracking regular expression.
    """
    start = value.find("::")
    while start != -1:
        if start > 0:
            preceding = value[start - 1]
            if ("A" <= preceding <= "Z") or ("a" <= preceding <= "z"):
                return value[start + 2 :]
        start = value.find("::", start + 1)
    return value


def extract_icf_sattline_ref(value: str) -> tuple[str | None, str | None]:
    """Extract (program, path) from an ICF value string."""
    text = _without_value_prefix(value.strip())
    program, separator, path = text.partition(":")
    if not separator:
        return None, None
    program = program.strip()
    path = path.strip()
    if not program or not path:
        return None, None
    return program, path


def extract_icf_value_prefix(value: str) -> str | None:
    """Extract the optional single-letter ICF value prefix such as ``F`` from ``F::Program:Path``."""
    match = _ICF_VALUE_PREFIX_RE.match(value.strip())
    if match is None:
        return None
    return match.group("prefix").upper()


def is_placeholder_icf_value(value: str) -> bool:
    """Return True for intentionally unbound ICF placeholders such as ``H::.``."""
    return _ICF_PLACEHOLDER_RE.match(value.strip()) is not None


__all__ = [
    "IcfFileTooLargeError",
    "decode_icf_text",
    "extract_icf_sattline_ref",
    "extract_icf_value_prefix",
    "is_placeholder_icf_value",
    "parse_icf_file",
]
