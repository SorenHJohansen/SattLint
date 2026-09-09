"""Atheris fuzz target for SattLint's own ICF config reader.

Exercises ``decode_icf_text``, ``format_icf_text``, and ``parse_icf_file``
against arbitrary bytes. These are SattLint-owned — the .icf format is not
parsed by ``sattline-parser`` (which fuzzes its own grammar in its own repo),
so any crash found here is a bug in SattLint's ICF handling.

The readers are tolerant by design, so an exception escaping any of them is a
genuine crash and is left uncaught for atheris to record.

Run locally::

    python -m pip install "atheris>=3.1"
    python scripts/fuzz/icf_fuzzer.py -runs=100000 -max_len=4096

CI runs a short bounded session (see .github/workflows/ci.yml fuzz-smoke).
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import atheris  # type: ignore[import-untyped]

from sattlint.analyzers.icf._icf_file_io import decode_icf_text, format_icf_text, parse_icf_file


def test_one_input(data: bytes) -> None:
    text, _encoding, _has_bom = decode_icf_text(data)
    format_icf_text(text)

    with tempfile.NamedTemporaryFile(suffix=".icf", delete=False) as handle:
        handle.write(data)
        tmp_path = Path(handle.name)
    try:
        parse_icf_file(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()
