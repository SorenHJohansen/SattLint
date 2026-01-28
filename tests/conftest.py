"""Shared pytest fixtures and test utilities."""
import sys
from pathlib import Path

import pytest
from lark import Lark

# Ensure `src/` is on sys.path so `import sattlint` works in dev/test runs.
_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from sattlint.engine import SattLineProjectLoader, create_sl_parser
from sattlint.transformer.sl_transformer import SLTransformer
from sattlint.models.ast_model import BasePicture


@pytest.fixture
def sample_sattline_dir():
    """Path to directory containing sample SattLine files"""
    return Path(__file__).parent / "fixtures" / "sample_sattline"


@pytest.fixture(scope="session")
def parser():
    """Configured Lark parser for SattLine"""
    return create_sl_parser()


@pytest.fixture(scope="session")
def transformer():
    """SLTransformer instance"""
    return SLTransformer()


@pytest.fixture
def sample_config():
    """Sample configuration for testing"""
    return {
        "root": "test_module",
        "mode": "draft",
        "scan_root_only": False,
        "debug": False,
        "program_dir": "/tmp/test_programs",
        "ABB_lib_dir": "/tmp/test_abb_lib",
        "other_lib_dirs": ["/tmp/test_lib1", "/tmp/test_lib2"],
    }
