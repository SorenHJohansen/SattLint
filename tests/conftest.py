# tests/conftest.py
import pytest
from pathlib import Path
from lark import Lark
from src.engine import SattLineProjectLoader, create_sl_parser
from src.transformer.sl_transformer import SLTransformer
from src.models.ast_model import BasePicture


@pytest.fixture
def sample_sattline_dir():
    """Path to directory containing sample SattLine files"""
    return Path(__file__).parent / "fixtures" / "sample_sattline"


@pytest.fixture
def parser():
    """Configured Lark parser for SattLine"""
    return create_sl_parser()


@pytest.fixture
def transformer():
    """SLTransformer instance"""
    return SLTransformer()


@pytest.fixture
def sample_config():
    """Sample configuration for testing"""
    return {
        "root": "test_module",
        "mode": "draft",
        "ignore_ABB_lib": True,
        "scan_root_only": False,
        "debug": False,
        "program_dir": "/tmp/test_programs",
        "ABB_lib_dir": "/tmp/test_abb_lib",
        "other_lib_dirs": ["/tmp/test_lib1", "/tmp/test_lib2"],
    }
