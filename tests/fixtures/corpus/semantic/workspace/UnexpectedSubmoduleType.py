from typing import cast

from sattline_parser.models.ast_model import (
    BasePicture,
    FrameModule,
    ModuleHeader,
    ModuleTypeInstance,
    SingleModule,
)


def build_basepicture() -> BasePicture:
    return BasePicture(
        header=ModuleHeader(name="Root", invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0)),
        submodules=cast(list[SingleModule | FrameModule | ModuleTypeInstance], [object()]),
    )
