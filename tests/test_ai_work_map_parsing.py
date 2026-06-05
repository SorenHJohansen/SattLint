from typing import Any, cast

import pytest

from sattlint.devtools import ai_work_map


def test_parse_frontmatter_handles_plain_files_lists_and_booleans(tmp_path):
    plain = tmp_path / "plain.md"
    plain.write_text("body\n", encoding="utf-8")

    assert ai_work_map._parse_frontmatter(plain) == {}

    frontmatter = tmp_path / "agent.agent.md"
    frontmatter.write_text(
        "\n".join(
            [
                "---",
                'name: "Repo Audit"',
                "user-invocable: true",
                "enabled: false",
                'applyTo: ["src/sattlint/devtools/**", "tests/test_repo_audit*.py"]',
                "globs: [src/sattlint/devtools/**, tests/test_repo_audit*.py]",
                'owners: ["Copilot", "Human"]',
                "empty: []",
                "---",
                "body",
            ]
        ),
        encoding="utf-8",
    )

    payload = ai_work_map._parse_frontmatter(frontmatter)

    assert payload == {
        "name": "Repo Audit",
        "user-invocable": True,
        "enabled": False,
        "applyTo": ["src/sattlint/devtools/**", "tests/test_repo_audit*.py"],
        "globs": ["src/sattlint/devtools/**", "tests/test_repo_audit*.py"],
        "owners": ["Copilot", "Human"],
        "empty": [],
    }


def test_parse_plan_helpers_extract_routes_owner_suites_and_first_validations(tmp_path):
    routes_file = tmp_path / "routes.md"
    routes_file.write_text(
        "\n".join(
            [
                "Intro",
                "- Parser surface:",
                "  use `cmd one` first",
                "  then inspect nearby helpers",
                "- Repo audit:",
                "  `cmd two`",
            ]
        ),
        encoding="utf-8",
    )
    plan = tmp_path / "plan.md"
    plan.write_text(
        "\n".join(
            [
                "Primary owner suites for this plan:",
                "- `tests/test_alpha.py` -> `src/pkg/alpha.py`",
                "- `tests/test_beta.py`",
                "Per-slice first validations:",
                "    pytest tests/test_alpha.py -x -q --tb=short",
                "    pytest tests/test_beta.py -x -q --tb=short",
                "",
                "Tail",
            ]
        ),
        encoding="utf-8",
    )

    routes = ai_work_map._parse_validation_routes(routes_file)
    suites = ai_work_map._parse_owner_suites(plan)
    first_validation_commands = ai_work_map._parse_first_validation_commands(plan)

    assert routes == [
        {
            "surface": "Parser surface",
            "commands": ["cmd one"],
            "notes": ["use  first", "then inspect nearby helpers"],
        },
        {
            "surface": "Repo audit",
            "commands": ["cmd two"],
            "notes": [],
        },
    ]
    assert suites == [
        {
            "tests": ["tests/test_alpha.py"],
            "targets": ["src/pkg/alpha.py"],
            "target_summary": "`src/pkg/alpha.py`",
        },
        {
            "tests": ["tests/test_beta.py"],
            "targets": [],
            "target_summary": "`tests/test_beta.py`",
        },
    ]
    assert first_validation_commands == [
        "pytest tests/test_alpha.py -x -q --tb=short",
        "pytest tests/test_beta.py -x -q --tb=short",
    ]


def test_parse_progress_checkbox_states_stops_after_progress_section(tmp_path):
    plan = tmp_path / "plan.md"
    plan.write_text(
        "\n".join(
            [
                "# Example Plan",
                "",
                "## Progress",
                "",
                "- [x] first done step",
                "- [ ] remaining step",
                "",
                "## Surprises & Discoveries",
                "",
                "- [ ] not a progress checkbox",
            ]
        ),
        encoding="utf-8",
    )

    assert ai_work_map._parse_progress_checkbox_states(plan) == [True, False]
    assert ai_work_map._is_completed_exec_plan(plan) is False


def test_archive_completed_exec_plans_moves_only_fully_checked_plans(tmp_path):
    repo_root = tmp_path
    active_dir = tmp_path / "docs" / "exec-plans" / "active"
    completed_dir = tmp_path / "docs" / "exec-plans" / "completed"
    active_dir.mkdir(parents=True)

    completed_plan = active_dir / "done.md"
    completed_plan.write_text(
        "\n".join(
            [
                "# Done",
                "",
                "## Progress",
                "",
                "- [x] step one",
                "- [x] step two",
                "",
                "## Outcomes & Retrospective",
                "",
                "See docs/exec-plans/active/done.md for the original path.",
                "",
                "Closed.",
            ]
        ),
        encoding="utf-8",
    )
    note_file = repo_root / "notes.md"
    note_file.write_text("Reference: docs/exec-plans/active/done.md\n", encoding="utf-8")
    active_plan = active_dir / "active.md"
    active_plan.write_text(
        "\n".join(
            [
                "# Active",
                "",
                "## Progress",
                "",
                "- [x] first step",
                "- [ ] remaining step",
            ]
        ),
        encoding="utf-8",
    )

    archived = ai_work_map.archive_completed_exec_plans(active_dir=active_dir, completed_dir=completed_dir)

    assert archived == [{"from": "docs/exec-plans/active/done.md", "to": "docs/exec-plans/completed/done.md"}]
    assert not completed_plan.exists()
    moved_plan = completed_dir / "done.md"
    assert moved_plan.exists()
    assert "docs/exec-plans/completed/done.md" in moved_plan.read_text(encoding="utf-8")
    assert note_file.read_text(encoding="utf-8") == "Reference: docs/exec-plans/completed/done.md\n"
    assert active_plan.exists()


def test_ai_work_map_reference_update_helpers_cover_skip_and_decode_edges(tmp_path, monkeypatch):
    class _FakePath:
        def __init__(self, *, suffix: str, relative_parts: tuple[str, ...] | None = None, fail_relative: bool = False):
            self.suffix = suffix
            self._relative_parts = relative_parts
            self._fail_relative = fail_relative

        def is_file(self) -> bool:
            return True

        def relative_to(self, _repo_root):
            if self._fail_relative:
                raise ValueError("outside root")
            assert self._relative_parts is not None
            return type("RelativePath", (), {"parts": self._relative_parts})()

    class _FakeRepoRoot:
        def __init__(self, paths: list[_FakePath]):
            self._paths = paths

        def rglob(self, _pattern: str) -> list[_FakePath]:
            return self._paths

    invalid_path = _FakePath(suffix=".md", fail_relative=True)
    skipped_path = _FakePath(suffix=".md", relative_parts=(".venv-cache", "ignored.md"))
    kept_path = _FakePath(suffix=".md", relative_parts=("docs", "plan.md"))

    files = ai_work_map._iter_reference_update_files(cast(Any, _FakeRepoRoot([invalid_path, skipped_path, kept_path])))
    ai_work_map._rewrite_exec_plan_references([], repo_root=tmp_path)

    undecodable = tmp_path / "notes.md"
    undecodable.write_bytes(b"\xff")
    monkeypatch.setattr(ai_work_map, "_iter_reference_update_files", lambda _repo_root: [undecodable])
    ai_work_map._rewrite_exec_plan_references(
        [{"from": "docs/exec-plans/active/one.md", "to": "docs/exec-plans/completed/one.md"}],
        repo_root=tmp_path,
    )

    assert files == [kept_path]
    assert undecodable.read_bytes() == b"\xff"


def test_archive_completed_exec_plans_raises_when_destination_already_exists(tmp_path):
    active_dir = tmp_path / "docs" / "exec-plans" / "active"
    completed_dir = tmp_path / "docs" / "exec-plans" / "completed"
    active_dir.mkdir(parents=True)
    completed_dir.mkdir(parents=True)

    plan = active_dir / "done.md"
    plan.write_text("## Progress\n\n- [x] done\n", encoding="utf-8")
    (completed_dir / "done.md").write_text("existing\n", encoding="utf-8")

    with pytest.raises(FileExistsError, match="Completed exec plan already exists"):
        ai_work_map.archive_completed_exec_plans(active_dir=active_dir, completed_dir=completed_dir)


def test_ai_work_map_parsers_cover_ignored_lines_and_plan_collection(tmp_path, monkeypatch):
    frontmatter = tmp_path / "agent.instructions.md"
    frontmatter.write_text("---\nname: Demo\nnot-a-field\n---\nbody\n", encoding="utf-8")
    routes_file = tmp_path / "routes.md"
    routes_file.write_text(
        "\n".join(
            [
                "Intro",
                "- Parser:",
                "  ",
                "  `cmd one`",
                "  note",
            ]
        ),
        encoding="utf-8",
    )
    plan = tmp_path / "plan.md"
    plan.write_text(
        "\n".join(
            [
                "Primary owner suites for this plan:",
                "note before suites",
                "- `tests/test_alpha.py` -> `src/pkg/alpha.py`",
                "",
                "Per-slice first validations:",
                "",
                "    pytest tests/test_alpha.py -x -q --tb=short",
                "Tail",
            ]
        ),
        encoding="utf-8",
    )
    exec_plans_dir = tmp_path / "plans"
    exec_plans_dir.mkdir()
    collected_plan = exec_plans_dir / "alpha.md"
    collected_plan.write_text(plan.read_text(encoding="utf-8"), encoding="utf-8")

    payload = ai_work_map._parse_frontmatter(frontmatter)
    routes = ai_work_map._parse_validation_routes(routes_file)
    suites = ai_work_map._parse_owner_suites(plan)
    commands = ai_work_map._parse_first_validation_commands(plan)
    monkeypatch.setattr(ai_work_map, "REPO_ROOT", tmp_path)

    collected = ai_work_map._collect_owner_suite_plans(exec_plans_dir)

    assert payload == {"name": "Demo"}
    assert routes == [{"surface": "Parser", "commands": ["cmd one"], "notes": ["note"]}]
    assert suites == [
        {
            "tests": ["tests/test_alpha.py"],
            "targets": ["src/pkg/alpha.py"],
            "target_summary": "`src/pkg/alpha.py`",
        }
    ]
    assert commands == ["pytest tests/test_alpha.py -x -q --tb=short"]
    assert collected[0]["plan_path"].endswith("alpha.md")


def test_ai_work_map_parsers_skip_blank_and_non_command_lines_before_collecting(tmp_path):
    owner_suites_plan = tmp_path / "owner-suites.md"
    owner_suites_plan.write_text(
        "\n".join(
            [
                "Primary owner suites for this plan:",
                "",
                "note before suites",
                "- `tests/test_alpha.py` -> `src/pkg/alpha.py`",
            ]
        ),
        encoding="utf-8",
    )
    first_validations_plan = tmp_path / "first-validations.md"
    first_validations_plan.write_text(
        "\n".join(
            [
                "Per-slice first validations:",
                "misc note",
                "    pytest tests/test_alpha.py -x -q --tb=short",
            ]
        ),
        encoding="utf-8",
    )

    suites = ai_work_map._parse_owner_suites(owner_suites_plan)
    commands = ai_work_map._parse_first_validation_commands(first_validations_plan)

    assert suites == [
        {
            "tests": ["tests/test_alpha.py"],
            "targets": ["src/pkg/alpha.py"],
            "target_summary": "`src/pkg/alpha.py`",
        }
    ]
    assert commands == ["pytest tests/test_alpha.py -x -q --tb=short"]


def test_ai_work_map_parsing_collectors_and_wrappers_cover_remaining_branches(tmp_path, monkeypatch):
    instructions_dir = tmp_path / ".github" / "instructions"
    agents_dir = tmp_path / ".github" / "agents"
    exec_plans_dir = tmp_path / "docs" / "exec-plans"
    instructions_dir.mkdir(parents=True)
    agents_dir.mkdir(parents=True)
    exec_plans_dir.mkdir(parents=True)

    instruction = instructions_dir / "demo.instructions.md"
    instruction.write_text(
        '---\nname: Demo Instruction\ndescription: Route demo work\napplyTo: ["src/demo.py"]\n---\n',
        encoding="utf-8",
    )
    agent = agents_dir / "demo.agent.md"
    agent.write_text(
        "---\nname: Demo Agent\ndescription: Handles demo work\nuser-invocable: true\n---\n",
        encoding="utf-8",
    )

    skipped_plan = exec_plans_dir / "skip.md"
    skipped_plan.write_text("No owner heading here\n- `tests/test_skip.py`\n", encoding="utf-8")
    collected_plan = exec_plans_dir / "collect.md"
    collected_plan.write_text(
        "\n".join(
            [
                "Existing owner suites that this plan may reuse instead of creating new suites when the fit is real:",
                "- `tests/test_collect.py` -> `src/demo.py`",
                "Per-slice first validations:",
                "    pytest tests/test_collect.py -x -q --tb=short",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(ai_work_map, "REPO_ROOT", tmp_path)

    assert ai_work_map._render_json({"b": 2, "a": 1}) == '{\n  "a": 1,\n  "b": 2\n}\n'
    assert ai_work_map._read_lines(skipped_plan) == ["No owner heading here", "- `tests/test_skip.py`"]
    assert ai_work_map._extract_backtick_items("run `cmd one` then `cmd two`") == ["cmd one", "cmd two"]
    assert ai_work_map._strip_quotes('"quoted"') == "quoted"

    assert ai_work_map._collect_instruction_metadata(instructions_dir) == [
        {
            "file_path": ".github/instructions/demo.instructions.md",
            "name": "Demo Instruction",
            "description": "Route demo work",
            "apply_to": ["src/demo.py"],
        }
    ]
    assert ai_work_map._collect_agent_metadata(agents_dir) == [
        {
            "file_path": ".github/agents/demo.agent.md",
            "name": "Demo Agent",
            "description": "Handles demo work",
            "user_invocable": True,
        }
    ]
    assert ai_work_map._parse_owner_suites(skipped_plan) == []
    assert ai_work_map._collect_owner_suite_plans(exec_plans_dir) == [
        {
            "plan_path": "docs/exec-plans/collect.md",
            "owner_heading": "Existing owner suites that this plan may reuse instead of creating new suites when the fit is real:",
            "suites": [
                {
                    "tests": ["tests/test_collect.py"],
                    "targets": ["src/demo.py"],
                    "target_summary": "`src/demo.py`",
                }
            ],
            "first_validation_commands": ["pytest tests/test_collect.py -x -q --tb=short"],
        }
    ]
