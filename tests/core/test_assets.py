"""Bundled assets load on demand and degrade to empty text."""

from __future__ import annotations

import pytest

from sattlint import assets


def test_bundled_banner_is_available_and_normalized() -> None:
    banner = assets.sqhj_banner()

    assert banner
    assert "\u00a0" not in banner
    assert not banner.startswith("\n")
    assert not banner.endswith("\n")


def test_a_missing_asset_yields_empty_text(monkeypatch: pytest.MonkeyPatch) -> None:
    class _MissingAsset:
        def joinpath(self, _name: str) -> _MissingAsset:
            return self

        def read_text(self, *, encoding: str) -> str:
            raise FileNotFoundError(encoding)

    def _files(_package: str) -> _MissingAsset:
        return _MissingAsset()

    monkeypatch.setattr(assets, "files", _files)

    assert assets.text_asset("missing") == ""
