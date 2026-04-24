from types import SimpleNamespace
from typing import Any, cast

from sattlint_gui import binding, main
from sattlint_gui import gui as package_gui
from sattlint_gui.frames.config_frame import apply_editable_config, extract_editable_config
from sattlint_gui.frames.docs_frame import DocsFrame


def test_package_exports_gui_callable():
    assert callable(package_gui)


def test_binding_load_config_uses_first_tuple_item(monkeypatch, tmp_path):
    fake_app = SimpleNamespace(CONFIG_PATH="config.json", load_config=lambda path: ({"mode": "draft"}, True))
    monkeypatch.setattr(binding, "_APP_MODULE", fake_app)
    monkeypatch.setattr(binding, "_workspace_root", lambda: tmp_path)

    gui_binding = binding.SattLintBinding()
    loaded = gui_binding.load_config()

    assert loaded["mode"] == "draft"
    assert loaded["other_lib_dirs"] == []
    assert "program_dir" not in loaded


def test_gui_entrypoint_creates_window_and_runs_mainloop(monkeypatch):
    events: list[str] = []

    class FakeWindow:
        def mainloop(self) -> None:
            events.append("mainloop")

    monkeypatch.setattr(main, "create_window", lambda theme=None: FakeWindow())

    assert main.gui() == 0
    assert events == ["mainloop"]


def test_extract_editable_config_normalizes_defaults():
    extracted = extract_editable_config({"mode": "draft", "program_dir": None, "other_lib_dirs": None})

    assert extracted["mode"] == "draft"
    assert extracted["program_dir"] == ""
    assert extracted["other_lib_dirs"] == []
    assert extracted["analyzed_programs_and_libraries"] == []


def test_apply_editable_config_preserves_nested_sections():
    base_cfg = {
        "mode": "official",
        "program_dir": "old-program",
        "analysis": {"keep": True},
        "documentation": {"classifications": {"em": {"name_contains": ["Equip"]}}},
    }
    editable_cfg = {
        "mode": "draft",
        "program_dir": "new-program",
        "ABB_lib_dir": "abb",
        "icf_dir": "icf",
        "scan_root_only": True,
        "fast_cache_validation": False,
        "debug": True,
        "analyzed_programs_and_libraries": ["TargetA"],
        "other_lib_dirs": ["lib-a", "lib-b"],
    }

    merged = apply_editable_config(base_cfg, editable_cfg)

    assert merged["mode"] == "draft"
    assert merged["program_dir"] == "new-program"
    assert merged["analysis"] == {"keep": True}
    assert merged["documentation"] == {"classifications": {"em": {"name_contains": ["Equip"]}}}
    assert merged["analyzed_programs_and_libraries"] == ["TargetA"]
    assert merged["other_lib_dirs"] == ["lib-a", "lib-b"]


def test_binding_run_docgen_delegates_to_app(monkeypatch):
    captured = {}

    fake_app = SimpleNamespace(
        run_docgen_command=lambda cfg, *, output_dir, output_path, use_cache: (
            captured.update(
                {
                    "cfg": cfg,
                    "output_dir": output_dir,
                    "output_path": output_path,
                    "use_cache": use_cache,
                }
            )
            or 0
        ),
    )
    monkeypatch.setattr(binding, "_APP_MODULE", fake_app)

    gui_binding = binding.SattLintBinding()
    result = gui_binding.run_docgen({"mode": "draft"}, output_dir="docs-out")

    assert result.ok is True
    assert captured == {
        "cfg": {"mode": "draft"},
        "output_dir": "docs-out",
        "output_path": None,
        "use_cache": True,
    }


def test_suggest_workspace_ha_config_fills_missing_paths(monkeypatch, tmp_path):
    libs_root = tmp_path / "Libs" / "HA"
    for relative in ("UnitLib", "ABBLib", "ICF", "ProjectLib", "NNELib", "PPLib"):
        (libs_root / relative).mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(binding, "_workspace_root", lambda: tmp_path)

    suggested = binding.suggest_workspace_ha_config({"mode": "draft", "other_lib_dirs": []})

    assert suggested["program_dir"].endswith("UnitLib")
    assert suggested["ABB_lib_dir"].endswith("ABBLib")
    assert suggested["icf_dir"].endswith("ICF")
    assert len(suggested["other_lib_dirs"]) == 3


def test_select_demo_target_prefers_configured_target():
    demo_target = binding.select_demo_target({"analyzed_programs_and_libraries": ["KaHAApplSupportLib"]})

    assert demo_target is not None
    assert demo_target.name == "KaHAApplSupportLib"
    assert demo_target.reason == "first configured analysis target"


def test_select_demo_target_falls_back_to_program_dir(tmp_path):
    (tmp_path / "Alpha.x").write_text("", encoding="utf-8")
    (tmp_path / "Beta.x").write_text("", encoding="utf-8")

    demo_target = binding.select_demo_target({"program_dir": str(tmp_path), "mode": "official"})

    assert demo_target is not None
    assert demo_target.name == "Alpha"
    assert "program_dir" in demo_target.reason


def test_binding_run_demo_combines_outputs(monkeypatch):
    gui_binding = binding.SattLintBinding()
    monkeypatch.setattr(gui_binding, "select_demo_target", lambda cfg: binding.DemoTarget("DemoTarget", "configured"))
    monkeypatch.setattr(gui_binding, "run_self_check", lambda cfg: binding.BindingResult(ok=True, output="self-check ok"))
    monkeypatch.setattr(
        gui_binding,
        "run_variable_analysis",
        lambda cfg: binding.BindingResult(ok=True, output="variable-analysis ok"),
    )

    result = gui_binding.run_demo({"mode": "draft"})

    assert result.ok is True
    assert "Demo target: DemoTarget (configured)" in result.output
    assert "[Self-check]\nself-check ok" in result.output
    assert "[Variable Analysis]\nvariable-analysis ok" in result.output


def test_docs_frame_generate_docs_reports_status(monkeypatch):
    events: list[tuple[str, str]] = []

    class FakeStringVar:
        def __init__(self, value="") -> None:
            self.value = value

        def get(self) -> str:
            return self.value

        def set(self, value: str) -> None:
            self.value = value

    class FakeBinding:
        config_path = "config.toml"

        def load_config(self) -> dict:
            return {"analyzed_programs_and_libraries": ["TargetA"], "mode": "official"}

        def run_docgen(self, cfg: dict, *, output_dir: str, output_path=None):
            assert cfg["analyzed_programs_and_libraries"] == ["TargetA"]
            assert output_dir == "docs-out"
            return binding.BindingResult(ok=True, output="Wrote docs-out/TargetA_FS.docx")

    class FakeReportView:
        def __init__(self) -> None:
            self.text = ""

        def set_text(self, text: str) -> None:
            self.text = text

    class FakeConsoleView(FakeReportView):
        pass

    class FakeThread:
        def __init__(self, *, target, daemon) -> None:
            self.target = target

        def start(self) -> None:
            self.target()

    monkeypatch.setattr("sattlint_gui.frames.docs_frame.threading.Thread", FakeThread)

    frame = cast(Any, DocsFrame.__new__(DocsFrame))
    frame.binding = FakeBinding()
    frame.on_result = lambda title, text: events.append(("result", f"{title}:{text}"))
    frame.on_status = lambda text: events.append(("status", text))
    frame.cfg = frame.binding.load_config()
    frame.output_dir_var = FakeStringVar("docs-out")
    frame.summary = FakeReportView()
    frame.preview = FakeReportView()
    frame.console = FakeConsoleView()
    frame.after = lambda _delay, callback: (callback() or "after-id")

    frame.generate_docs()

    assert frame.console.text == "Wrote docs-out/TargetA_FS.docx"
    assert ("status", "Documentation generation running...") in events
    assert ("status", "Documentation generation finished") in events
    assert ("result", "Documentation:Wrote docs-out/TargetA_FS.docx") in events
