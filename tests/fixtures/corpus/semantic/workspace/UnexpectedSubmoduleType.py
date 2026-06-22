from sattline_parser.models.ast_model import BasePicture, ModuleHeader


def build_basepicture() -> BasePicture:
    return BasePicture(
        header=ModuleHeader(name="Root", invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0)),
        submodules=[object()],
    )
