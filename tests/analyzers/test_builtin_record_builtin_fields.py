# pyright: reportPrivateUsage=false
from sattline_parser.models.ast_model import (
    BasePicture,
    Equation,
    ModuleCode,
    ModuleHeader,
    Simple_DataType,
    SingleModule,
    Variable,
)
from sattlint import constants as const
from sattlint.analyzers.variables import VariablesAnalyzer


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _varref(name: str) -> dict[str, str]:
    return {const.KEY_VAR_NAME: name}


def _eq(code: list[object]) -> Equation:
    return Equation(
        name="E1",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=code,
    )


def test_builtin_progstationdata_fields_are_addressable() -> None:
    progstation_data = Variable(name="ProgStationData", datatype="ProgStationData")
    format_text = Variable(name="FormatText", datatype=Simple_DataType.STRING)
    warning_colour = Variable(name="WarningColour", datatype=Simple_DataType.INTEGER)

    module = SingleModule(
        header=_hdr("M1"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[progstation_data, format_text, warning_colour],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                _eq(
                    [
                        (
                            const.KEY_ASSIGN,
                            _varref("FormatText"),
                            _varref("ProgStationData.TimeFormats.DateAndTime"),
                        ),
                        (
                            const.KEY_ASSIGN,
                            _varref("WarningColour"),
                            _varref("ProgStationData.Colours.WarningColour"),
                        ),
                    ]
                )
            ]
        ),
        parametermappings=[],
    )

    analyzer = VariablesAnalyzer(
        BasePicture(
            header=_hdr("Root"),
            datatype_defs=[],
            moduletype_defs=[],
            localvariables=[],
            submodules=[module],
            modulecode=None,
            moduledef=None,
        ),
        fail_loudly=False,
    )
    analyzer.run()

    usage = analyzer._get_usage(progstation_data)
    read_keys = {key.casefold() for key in (usage.field_reads or {})}

    assert "timeformats.dateandtime" in read_keys
    assert "colours.warningcolour" in read_keys
    assert not any("unknown record datatype" in warning for warning in analyzer._analysis_warnings)


def test_builtin_acof_and_ip4signal_fields_are_addressable() -> None:
    acof = Variable(name="Acof", datatype="AcofType")
    signal = Variable(name="Signal", datatype="IP4Signal")
    elapsed = Variable(name="Elapsed", datatype=Simple_DataType.DURATION)
    unit = Variable(name="Unit", datatype=Simple_DataType.IDENTSTRING)
    hold = Variable(name="Hold", datatype=Simple_DataType.BOOLEAN)

    module = SingleModule(
        header=_hdr("M1"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[acof, signal, elapsed, unit, hold],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                _eq(
                    [
                        (
                            const.KEY_ASSIGN,
                            _varref("Elapsed"),
                            _varref("Acof.Elapsed"),
                        ),
                        (
                            const.KEY_ASSIGN,
                            _varref("Unit"),
                            _varref("Signal.Parameters.Unit"),
                        ),
                        (
                            const.KEY_ASSIGN,
                            _varref("Hold"),
                            _varref("Acof.AcofTimer"),
                        ),
                    ]
                )
            ]
        ),
        parametermappings=[],
    )

    analyzer = VariablesAnalyzer(
        BasePicture(
            header=_hdr("Root"),
            datatype_defs=[],
            moduletype_defs=[],
            localvariables=[],
            submodules=[module],
            modulecode=None,
            moduledef=None,
        ),
        fail_loudly=False,
    )
    analyzer.run()

    acof_usage = analyzer._get_usage(acof)
    signal_usage = analyzer._get_usage(signal)
    acof_read_keys = {key.casefold() for key in (acof_usage.field_reads or {})}
    signal_read_keys = {key.casefold() for key in (signal_usage.field_reads or {})}

    assert "elapsed" in acof_read_keys
    assert "acoftimer" in acof_read_keys
    assert "parameters.unit" in signal_read_keys
    assert not any("unknown record datatype" in warning for warning in analyzer._analysis_warnings)


def test_controllib_builtin_fields_are_addressable() -> None:
    pid = Variable(name="Pid", datatype="PidPar")
    selector = Variable(name="Selector", datatype="SelectorChain")
    curve = Variable(name="Curve", datatype="StaticFunctionRSPar")
    adaptive = Variable(name="Adaptive", datatype="AdaptivePidPar")
    gain = Variable(name="Gain", datatype=Simple_DataType.REAL)
    valid = Variable(name="Valid", datatype=Simple_DataType.BOOLEAN)
    used = Variable(name="Used", datatype=Simple_DataType.BOOLEAN)
    ramp_duration = Variable(name="RampDuration", datatype=Simple_DataType.DURATION)

    module = SingleModule(
        header=_hdr("M1"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[pid, selector, curve, adaptive, gain, valid, used, ramp_duration],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                _eq(
                    [
                        (
                            const.KEY_ASSIGN,
                            _varref("Gain"),
                            _varref("Pid.Gain"),
                        ),
                        (
                            const.KEY_ASSIGN,
                            _varref("Valid"),
                            _varref("Selector.Signal.Valid"),
                        ),
                        (
                            const.KEY_ASSIGN,
                            _varref("Used"),
                            _varref("Curve.x10used"),
                        ),
                        (
                            const.KEY_ASSIGN,
                            _varref("RampDuration"),
                            _varref("Adaptive.RampDuration"),
                        ),
                    ]
                )
            ]
        ),
        parametermappings=[],
    )

    analyzer = VariablesAnalyzer(
        BasePicture(
            header=_hdr("Root"),
            datatype_defs=[],
            moduletype_defs=[],
            localvariables=[],
            submodules=[module],
            modulecode=None,
            moduledef=None,
        ),
        fail_loudly=False,
    )
    analyzer.run()

    pid_usage = analyzer._get_usage(pid)
    selector_usage = analyzer._get_usage(selector)
    curve_usage = analyzer._get_usage(curve)
    adaptive_usage = analyzer._get_usage(adaptive)
    pid_read_keys = {key.casefold() for key in (pid_usage.field_reads or {})}
    selector_read_keys = {key.casefold() for key in (selector_usage.field_reads or {})}
    curve_read_keys = {key.casefold() for key in (curve_usage.field_reads or {})}
    adaptive_read_keys = {key.casefold() for key in (adaptive_usage.field_reads or {})}

    assert "gain" in pid_read_keys
    assert "signal.valid" in selector_read_keys
    assert "x10used" in curve_read_keys
    assert "rampduration" in adaptive_read_keys
    assert not any("unknown record datatype" in warning for warning in analyzer._analysis_warnings)
