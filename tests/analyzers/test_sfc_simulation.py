# pyright: reportUnknownVariableType=false, reportUnknownParameterType=false, reportUnknownArgumentType=false, reportMissingTypeArgument=false
from __future__ import annotations

from typing import Any, cast

from sattline_parser.models.ast_model import (
    BasePicture,
    ModuleCode,
    ModuleHeader,
    Sequence,
    SFCCodeBlocks,
    SFCStep,
    SFCTransition,
    Simple_DataType,
    Variable,
)
from sattlint import constants as const
from sattlint.simulation import simulate_module


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _varref(name: str) -> dict:
    return {const.KEY_VAR_NAME: name}


def _assign(name: str, value: object) -> tuple:
    return (const.KEY_ASSIGN, _varref(name), value)


def _step(name: str, active_stmts: list[object], *, kind: str = "step") -> SFCStep:
    return SFCStep(kind=kind, name=name, code=SFCCodeBlocks(active=active_stmts))


def _sequence(nodes: list[object]) -> Sequence:
    return Sequence(
        name="SeqMain",
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=nodes,
    )


def test_simulate_module_detects_steady_state():
    bp = BasePicture(
        header=_hdr("Main"),
        localvariables=[Variable(name="Counter", datatype=Simple_DataType.INTEGER)],
        modulecode=ModuleCode(
            sequences=[
                _sequence(
                    [
                        _step("Init", [_assign("Counter", 1)], kind="init"),
                        SFCTransition(name="Stay", condition=False),
                    ]
                )
            ],
            equations=[],
        ),
    )

    result = simulate_module(bp, module_name="Main", mode="steady-state", max_scans=5)

    assert result.steady_state_reached is True
    assert result.cycle_detected is False
    assert result.scan_budget_exhausted is False
    assert result.outcome == "steady-state"
    assert result.total_scans == 2
    assert result.render_summary() == "steady state reached after 2 scans"
    assert result.snapshots[-1].active_steps == ["SeqMain.Init"]
    assert result.snapshots[-1].state["Counter"] == 1


def test_simulate_module_detects_cycle_from_repeated_signature():
    bp = BasePicture(
        header=_hdr("Main"),
        localvariables=[Variable(name="Flag", datatype=Simple_DataType.BOOLEAN, init_value=False)],
        modulecode=ModuleCode(
            sequences=[
                _sequence(
                    [
                        _step("Toggle", [_assign("Flag", (const.GRAMMAR_VALUE_NOT, _varref("Flag")))], kind="init"),
                        SFCTransition(name="Stay", condition=False),
                    ]
                )
            ],
            equations=[],
        ),
    )

    result = simulate_module(bp, module_name="Main", mode="steady-state", max_scans=6)

    assert result.steady_state_reached is False
    assert result.cycle_detected is True
    assert result.scan_budget_exhausted is False
    assert result.outcome == "cycle"
    assert result.total_scans == 3
    assert result.cycle_start_scan == 1
    assert result.cycle_length == 2
    assert result.render_summary() == "cycle detected after 3 scans (start=1, length=2)"


def test_simulate_module_json_payload_uses_stable_keys_and_snapshot_shape():
    bp = BasePicture(
        header=_hdr("Main"),
        localvariables=[Variable(name="Counter", datatype=Simple_DataType.INTEGER)],
        modulecode=ModuleCode(
            sequences=[
                _sequence(
                    [
                        _step("Init", [_assign("Counter", 1)], kind="init"),
                        SFCTransition(name="Stay", condition=False),
                    ]
                )
            ],
            equations=[],
        ),
    )

    payload = simulate_module(bp, module_name="Main", mode="steady-state", max_scans=5).to_dict()

    assert list(payload) == [
        "target",
        "mode",
        "steady_state_reached",
        "cycle_detected",
        "scan_budget_exhausted",
        "outcome",
        "total_scans",
        "cycle_start_scan",
        "cycle_length",
        "snapshots",
    ]
    snapshots = cast(list[dict[str, Any]], payload["snapshots"])
    assert list(snapshots[0]) == ["scan", "active_steps", "state", "transition_fires"]
    assert payload["target"] == "Main"
    assert payload["mode"] == "steady-state"
    assert payload["total_scans"] == 2


def test_simulate_module_reports_scan_budget_exhaustion_summary():
    bp = BasePicture(
        header=_hdr("Main"),
        localvariables=[Variable(name="Counter", datatype=Simple_DataType.INTEGER)],
        modulecode=ModuleCode(
            sequences=[
                _sequence(
                    [
                        _step("Init", [_assign("Counter", 1)], kind="init"),
                        SFCTransition(name="Next", condition=True),
                        _step("Hold", [_assign("Counter", 2)]),
                        SFCTransition(name="Stay", condition=False),
                    ]
                )
            ],
            equations=[],
        ),
    )

    result = simulate_module(bp, module_name="Main", mode="steady-state", max_scans=1)

    assert result.scan_budget_exhausted is True
    assert result.steady_state_reached is False
    assert result.cycle_detected is False
    assert result.render_summary() == "scan budget exhausted after 1 scans"
