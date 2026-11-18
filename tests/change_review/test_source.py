"""Tests for the Change Review original-source provider.

The provider slices ``SourceSpan`` offsets out of the file text, so it must read
exactly the text the parser read. SattLine sources reach disk in three flavors
(byte-coded streams, marker-compressed text and plain Windows-1252), and only
the parse-faithful reader keeps offsets meaningful for all three.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from sattlint.change_review.source import SourceTextProvider, source_key
from sattlint.parser_api import source_text_for_parse

pytestmark = pytest.mark.unit

_SOURCE = (
    '"SyntaxVersion"\r\n'
    '"Original file: ProviderFixture.s"\r\n'
    "\r\n"
    "PROGRAM ProviderFixture\r\n"
    "\r\n"
    "   (* Note on the Ø letter and the å sign *)\r\n"
    "\r\n"
    "   EQUATIONBLOCK B0 COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :\r\n"
    "      Value = 1;\r\n"
    "\r\n"
    "ENDDEF (*BasePicture*);\r\n"
)

_CODED_BLOCK_BYTES = 100
_CODED_HEADER = b"\x80 3.1\r\n"
_CODED_SYNC_BYTE = 0x01
#: Bit 7 of a stored byte carries no information: the decoder masks it off. The
#: writer uses it to keep a payload byte from being mistaken for a sync byte.
_CODED_BIT7 = 0x80
#: Padding past the final line terminator is dropped by the decoder. A space
#: never decodes back to a CR, so padding cannot extend the payload.
_CODED_PAD_CHARACTER = " "


def _encode_coded_stream(text: str) -> bytes:
    """Encode *text* as a byte-coded SattLine stream.

    The stream layout is the parser's documented framing: a five-byte header
    line, then 100-byte blocks terminated by CRLF, where each stored byte is the
    plain byte XOR a running key. Characters above 0x7F do not survive the
    encoding (the key mask drops bit 7), so coded fixtures stay ASCII.
    """
    lines = text.replace("\r\n", "\r").replace("\r", "\r\n")
    if not lines.endswith("\r\n"):
        lines += "\r\n"

    payload = bytearray()
    key_index = 0
    for start in range(0, len(lines), _CODED_BLOCK_BYTES):
        chunk = lines[start : start + _CODED_BLOCK_BYTES]
        block = bytearray()
        for character in chunk:
            key = (7 * key_index + 8) % 128
            stored = (ord(character) & 0x7F) ^ key
            if stored == _CODED_SYNC_BYTE:
                stored |= _CODED_BIT7
            block.append(stored)
            key_index += 1
        block.extend(
            (ord(_CODED_PAD_CHARACTER) & 0x7F) ^ ((7 * index + 8) % 128)
            for index in range(key_index, key_index + (_CODED_BLOCK_BYTES - len(chunk)))
        )
        payload.extend(block)
        payload.extend(b"\r\n")
    return _CODED_HEADER + bytes(payload)


def _coded_text() -> str:
    return _SOURCE.replace("Ø", "O").replace("å", "a")


def test_provider_reads_plain_windows_1252_text(tmp_path: Path):
    source_path = tmp_path / "ProviderFixture.s"
    source_path.write_bytes(_SOURCE.encode("cp1252"))

    provider = SourceTextProvider({source_key("ProviderFixture.s", None): source_path})

    assert provider.text("ProviderFixture.s") == _SOURCE
    assert provider.snippet("ProviderFixture.s", 0, len('"SyntaxVersion"')) == '"SyntaxVersion"'


def test_provider_reads_byte_coded_source_as_the_parser_does(tmp_path: Path):
    source_path = tmp_path / "ProviderFixture.x"
    source_path.write_bytes(_encode_coded_stream(_coded_text()))

    provider = SourceTextProvider({source_key("ProviderFixture.x", None): source_path})

    text = provider.text("ProviderFixture.x")
    assert text == source_text_for_parse(source_path)
    assert text is not None
    assert "Value = 1;" in text


def test_provider_keeps_offsets_aligned_with_the_parse_text(tmp_path: Path):
    source_path = tmp_path / "ProviderFixture.x"
    source_path.write_bytes(_encode_coded_stream(_coded_text()))
    parse_text = source_text_for_parse(source_path)
    start = parse_text.index("Value = 1;")
    end = start + len("Value = 1;")

    provider = SourceTextProvider({source_key("ProviderFixture.x", None): source_path})

    assert provider.snippet("ProviderFixture.x", start, end) == "Value = 1;"
    assert provider.lines("ProviderFixture.x", 9, 9) == "      Value = 1;"


def test_provider_distinguishes_same_named_files_in_different_libraries(tmp_path: Path):
    first = tmp_path / "First" / "Shared.s"
    second = tmp_path / "Second" / "Shared.s"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_text("first", encoding="cp1252")
    second.write_text("second", encoding="cp1252")
    provider = SourceTextProvider(
        {
            source_key("Shared.s", "FirstLib"): first,
            source_key("Shared.s", "SecondLib"): second,
        }
    )

    assert provider.text("Shared.s", library="FirstLib") == "first"
    assert provider.text("Shared.s", library="SecondLib") == "second"
    # The bare name is ambiguous, so it does not guess.
    assert provider.text("Shared.s") is None


def test_provider_returns_none_for_unreadable_file(tmp_path: Path):
    provider = SourceTextProvider({source_key("Missing.s", None): tmp_path / "Missing.s"})

    assert provider.text("Missing.s") is None
    assert provider.lines("Missing.s", 1, 1) is None
