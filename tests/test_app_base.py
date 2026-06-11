# pyright: reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportArgumentType=false, reportPrivateUsage=false
from __future__ import annotations

import builtins
import ctypes
import logging
from pathlib import Path
from typing import Any

import pytest

from sattlint import app_base, engine


class _FakeKernelCall:
    def __init__(self, fn: Any) -> None:
        self._fn = fn
        self.argtypes: Any = None
        self.restype: Any = None
        self.calls: list[tuple[Any, ...]] = []

    def __call__(self, *args: Any) -> Any:
        self.calls.append(args)
        return self._fn(*args)


class _FakeKernel32:
    def __init__(
        self,
        *,
        stdout_handle: Any = 42,
        info_ok: bool = True,
        fill_char_ok: bool = True,
        fill_attr_ok: bool = True,
        cursor_ok: bool = True,
    ) -> None:
        self.GetStdHandle = _FakeKernelCall(lambda _handle: stdout_handle)

        def _get_console_screen_buffer_info(_handle: Any, info_ptr: Any) -> bool:
            info = info_ptr._obj
            info.dwSize.X = 4
            info.dwSize.Y = 3
            info.wAttributes = 7
            return info_ok

        self.GetConsoleScreenBufferInfo = _FakeKernelCall(_get_console_screen_buffer_info)
        self.FillConsoleOutputCharacterW = _FakeKernelCall(lambda *_args: fill_char_ok)
        self.FillConsoleOutputAttribute = _FakeKernelCall(lambda *_args: fill_attr_ok)
        self.SetConsoleCursorPosition = _FakeKernelCall(lambda *_args: cursor_ok)


def _install_fake_kernel(monkeypatch: pytest.MonkeyPatch, **kwargs: Any) -> _FakeKernel32:
    kernel32 = _FakeKernel32(**kwargs)
    monkeypatch.setattr(ctypes, "WinDLL", lambda *_args, **_kwargs: kernel32, raising=False)
    monkeypatch.setattr(ctypes, "get_last_error", lambda: 99, raising=False)
    return kernel32


def test_config_wrappers_delegate_and_save_emits(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    cfg = {"debug": False}
    config_path = Path("config.toml")
    seen: dict[str, Any] = {}

    monkeypatch.setattr(app_base, "_load_config", lambda path: (seen.setdefault("load_path", path), True))
    monkeypatch.setattr(
        app_base,
        "_save_config",
        lambda path, data: seen.update({"save_path": path, "save_cfg": data}),
    )
    monkeypatch.setattr(app_base, "_self_check", lambda data: seen.setdefault("self_check_cfg", data) is cfg)
    monkeypatch.setattr(
        app_base,
        "_target_exists",
        lambda target, data: seen.update({"target": target, "target_cfg": data}) or True,
    )

    loaded_cfg, created = app_base.load_config(config_path)
    app_base.save_config(config_path, cfg)

    assert loaded_cfg == config_path
    assert created is True
    assert app_base.self_check(cfg) is True
    assert app_base.target_exists("RootProgram", cfg) is True
    assert seen == {
        "load_path": config_path,
        "save_path": config_path,
        "save_cfg": cfg,
        "self_check_cfg": cfg,
        "target": "RootProgram",
        "target_cfg": cfg,
    }
    assert capsys.readouterr().out == "Config saved\n"


def test_apply_debug_and_build_cli_parser_cover_both_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    parser_calls: list[str | None] = []
    root_logger = logging.getLogger()
    original_root_level = root_logger.level
    original_log_level = app_base.log.level
    monkeypatch.setattr(
        app_base,
        "_build_cli_parser",
        lambda version=None: parser_calls.append(version) or {"version": version},
    )

    try:
        app_base.apply_debug({"debug": True})
        assert root_logger.level == logging.DEBUG
        assert app_base.log.level == logging.DEBUG

        app_base.apply_debug({"debug": False})
        assert root_logger.level == logging.INFO
        assert app_base.log.level == logging.INFO
    finally:
        root_logger.setLevel(original_root_level)
        app_base.log.setLevel(original_log_level)

    assert app_base.build_cli_parser() == {"version": None}
    assert app_base.build_cli_parser(version="9.9.9") == {"version": "9.9.9"}
    assert parser_calls == [None, "9.9.9"]


def test_syntax_helpers_cover_line_only_unknown_error_and_warning() -> None:
    result = engine.SyntaxValidationResult(
        file_path=Path("Program.s"),
        ok=False,
        stage="validation",
        message=None,
        line=4,
    )

    assert app_base._format_syntax_error(result) == "ERROR [validation] Program.s:4: Unknown error"
    assert (
        app_base._format_syntax_warning(Path("Program.s"), "Watch this") == "WARNING [validation] Program.s: Watch this"
    )


def test_run_syntax_check_command_prints_warnings_before_ok(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source_path = tmp_path / "Program.s"
    source_path.write_text("BasePicture\n", encoding="utf-8")
    monkeypatch.setattr(
        app_base.engine_module,
        "validate_single_file_syntax",
        lambda _path: engine.SyntaxValidationResult(
            file_path=source_path,
            ok=True,
            stage="validation",
            warnings=["Heads up"],
        ),
    )

    assert app_base.run_syntax_check_command(str(source_path)) == app_base.EXIT_SUCCESS

    captured = capsys.readouterr()
    assert captured.out == "OK\n"
    assert "WARNING [validation]" in captured.err
    assert "Heads up" in captured.err


def test_configure_windows_console_api_wrapper_delegates(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}
    monkeypatch.setattr(
        app_base,
        "_configure_windows_console_api",
        lambda kernel32, coord_type, buffer_info_type: seen.update(
            {
                "kernel32": kernel32,
                "coord_type": coord_type,
                "buffer_info_type": buffer_info_type,
            }
        ),
    )

    app_base.configure_windows_console_api("kernel32", "coord", "buffer")

    assert seen == {
        "kernel32": "kernel32",
        "coord_type": "coord",
        "buffer_info_type": "buffer",
    }


def test_clear_windows_console_wrapper_delegates(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(app_base, "_clear_windows_console", lambda: calls.append("clear"))

    app_base.clear_windows_console()

    assert calls == ["clear"]


def test_clear_windows_console_executes_success_path(monkeypatch: pytest.MonkeyPatch) -> None:
    kernel32 = _install_fake_kernel(monkeypatch)

    app_base._clear_windows_console()

    assert kernel32.GetStdHandle.calls
    assert kernel32.GetConsoleScreenBufferInfo.calls
    assert kernel32.FillConsoleOutputCharacterW.calls
    assert kernel32.FillConsoleOutputAttribute.calls
    assert kernel32.SetConsoleCursorPosition.calls


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"stdout_handle": 0}, "unable to access stdout console handle"),
        ({"info_ok": False}, "GetConsoleScreenBufferInfo failed"),
        ({"fill_char_ok": False}, "FillConsoleOutputCharacterW failed"),
        ({"fill_attr_ok": False}, "FillConsoleOutputAttribute failed"),
        ({"cursor_ok": False}, "SetConsoleCursorPosition failed"),
    ],
)
def test_clear_windows_console_raises_for_each_windows_api_failure(
    monkeypatch: pytest.MonkeyPatch,
    kwargs: dict[str, Any],
    message: str,
) -> None:
    _install_fake_kernel(monkeypatch, **kwargs)

    with pytest.raises(OSError, match=message):
        app_base._clear_windows_console()


def test_clear_screen_covers_default_windows_helper_and_ansi_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    writes: list[str] = []
    flushes: list[str] = []
    clears: list[str] = []
    stdout = type(
        "_Stdout",
        (),
        {
            "flush": lambda self: flushes.append("flush"),
            "write": lambda self, text: writes.append(text),
        },
    )()
    monkeypatch.setattr(app_base, "_clear_windows_console", lambda: clears.append("clear"))

    app_base.clear_screen(
        os_module=type("_Os", (), {"name": "nt", "system": lambda self, command: 1})(),
        sys_module=type("_Sys", (), {"stdout": stdout})(),
    )

    assert clears == ["clear"]
    assert writes == []
    assert flushes == ["flush"]

    app_base.clear_screen(
        os_module=type("_Os", (), {"name": "posix", "system": lambda self, command: 1})(),
        sys_module=type("_Sys", (), {"stdout": stdout})(),
        clear_windows_console=lambda: None,
    )

    assert writes == ["\033[2J\033[H"]
    assert flushes == ["flush", "flush", "flush"]


def test_clear_screen_falls_back_to_cls_or_ansi_after_windows_error() -> None:
    cls_calls: list[str] = []
    ansi_writes: list[str] = []
    stdout_cls = type(
        "_Stdout",
        (),
        {
            "flush": lambda self: None,
            "write": lambda self, text: ansi_writes.append(text),
        },
    )()

    app_base.clear_screen(
        os_module=type("_Os", (), {"name": "nt", "system": lambda self, command: cls_calls.append(command) or 0})(),
        sys_module=type("_Sys", (), {"stdout": stdout_cls})(),
        clear_windows_console=lambda: (_ for _ in ()).throw(OSError("boom")),
    )

    assert cls_calls == ["cls"]
    assert ansi_writes == []

    app_base.clear_screen(
        os_module=type("_Os", (), {"name": "nt", "system": lambda self, command: 1})(),
        sys_module=type("_Sys", (), {"stdout": stdout_cls})(),
        clear_windows_console=lambda: (_ for _ in ()).throw(OSError("boom")),
    )

    assert ansi_writes == ["\033[2J\033[H"]


def test_input_helpers_cover_pause_confirm_prompt_and_quit(monkeypatch: pytest.MonkeyPatch) -> None:
    prompts: list[str] = []
    responses = iter(["", "yes", "", "  custom  "])
    monkeypatch.setattr(
        builtins,
        "input",
        lambda prompt="": prompts.append(prompt) or next(responses),
    )
    clear_calls: list[str] = []
    monkeypatch.setattr(app_base, "clear_screen", lambda: clear_calls.append("clear"))

    app_base.pause()
    assert app_base.confirm("Continue") is True
    assert app_base.prompt("Output", "report.docx") == "report.docx"
    assert app_base.prompt("Name") == "custom"

    with pytest.raises(app_base.QuitAppError):
        app_base.quit_app()

    assert prompts == ["\nPress Enter to continue...", "Continue [y/N]: ", "Output [report.docx]: ", "Name: "]
    assert clear_calls == ["clear"]
