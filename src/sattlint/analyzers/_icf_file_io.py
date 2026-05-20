"""ICF file decoding, formatting, and parsing helpers."""

from __future__ import annotations

import codecs
import re
from dataclasses import dataclass
from pathlib import Path

from ..reporting.icf_report import ICFEntry

_ICF_REF_RE = re.compile(r"(?:^|.*?)(?:[A-Za-z]::)?(?P<program>[^:]+):(?P<path>.+)$")
_ICF_HEADER_RE = re.compile(r"^\[(?P<tag>[^\]\s]+)(?:\s+(?P<label>.+?))?\]$")
_ICF_PLACEHOLDER_RE = re.compile(r"^[A-Za-z]::\.$")
_ICF_VALUE_PREFIX_RE = re.compile(r"^(?P<prefix>[A-Za-z])::")
_ICF_FORMATTING_SPACING: dict[str, int] = {
    "unit": 2,
    "journal": 2,
    "operation": 2,
    "group": 1,
}


@dataclass(frozen=True)
class ICFFormatResult:
    file_path: Path
    changed: bool


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


def detect_icf_newline(raw_bytes: bytes) -> str:
    return "\r\n" if b"\r\n" in raw_bytes else "\n"


def header_spacing(tag: str) -> int:
    return _ICF_FORMATTING_SPACING.get(_cf(tag), 1)


def format_icf_text(text: str) -> str:
    """Normalize blank-line spacing around ICF headers without changing nonblank lines."""
    lines = text.splitlines()
    first_header_index = next((index for index, line in enumerate(lines) if _ICF_HEADER_RE.match(line.strip())), None)
    if first_header_index is None:
        return text

    prefix = lines[:first_header_index]
    body = lines[first_header_index:]
    formatted_body: list[str] = []

    for raw_line in body:
        stripped = raw_line.strip()
        if not stripped:
            continue

        header_match = _ICF_HEADER_RE.match(stripped)
        if header_match is None:
            formatted_body.append(raw_line)
            continue

        if formatted_body:
            while formatted_body and formatted_body[-1] == "":
                formatted_body.pop()
            formatted_body.extend([""] * header_spacing(header_match.group("tag")))

        formatted_body.append(raw_line)

    while formatted_body and formatted_body[-1] == "":
        formatted_body.pop()

    formatted_lines = prefix[:]
    while formatted_lines and formatted_lines[-1] == "":
        formatted_lines.pop()
    if formatted_lines and formatted_body:
        formatted_lines.append("")
    formatted_lines.extend(formatted_body)

    normalized = "\n".join(formatted_lines)
    if text.endswith(("\n", "\r\n")):
        normalized += "\n"
    return normalized


def format_icf_file(file_path: Path, *, check: bool = False) -> ICFFormatResult:
    """Rewrite one ICF file with normalized header spacing while preserving encoding and newline style."""
    raw_bytes = file_path.read_bytes()
    text, encoding, has_utf8_bom = decode_icf_text(raw_bytes)
    newline = detect_icf_newline(raw_bytes)
    formatted_text = format_icf_text(text)
    rendered_text = formatted_text.replace("\n", newline)
    changed = text != rendered_text
    if changed and not check:
        encoded = rendered_text.encode(encoding)
        if has_utf8_bom:
            encoded = codecs.BOM_UTF8 + encoded
        file_path.write_bytes(encoded)
    return ICFFormatResult(file_path=file_path, changed=changed)


def parse_icf_file(file_path: Path) -> list[ICFEntry]:
    """Parse a .icf file into key/value entries with section and line number info."""
    entries: list[ICFEntry] = []
    section: str | None = None
    unit: str | None = None
    operation: str | None = None
    journal: str | None = None
    group: str | None = None

    raw_bytes = file_path.read_bytes()
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


def extract_icf_sattline_ref(value: str) -> tuple[str | None, str | None]:
    """Extract (program, path) from an ICF value string."""
    match = _ICF_REF_RE.match(value.strip())
    if not match:
        return None, None
    program = match.group("program").strip()
    path = match.group("path").strip()
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
    "ICFFormatResult",
    "decode_icf_text",
    "detect_icf_newline",
    "extract_icf_sattline_ref",
    "extract_icf_value_prefix",
    "format_icf_file",
    "format_icf_text",
    "header_spacing",
    "is_placeholder_icf_value",
    "parse_icf_file",
]
