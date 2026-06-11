# Analyzer Authoring

Use one default authoring pattern for new analyzers and for substantial refactors of existing analyzers.

## Default Pattern

- Keep the public entrypoint as a thin module-level `analyze_*` or other registry-facing function.
- Put implementation state on a class derived from `BasePictureAnalyzer`.
- If the class grows beyond one file, split helper behavior into underscore-prefixed helper or mixin modules and compose it through inheritance.
- Keep helper-only test seams in `tests/` support modules instead of re-exporting large private helper surfaces from production modules.

## When To Use Mixins

- Stay in one file when the analyzer is still readable and ownership is obvious.
- Introduce mixins when you are separating traversal, issue emission, or other cohesive behavior across files.
- Name helper or mixin modules with a leading underscore so the public analyzer surface remains small.

## Avoid

- Module-level import-and-rename chains such as `from . import _helper as _helper_module` followed by dozens of `_fn = _helper_module.fn` assignments.
- Duplicating the same analyzer implementation in both underscored and public modules.
- Adding new standalone helper exports to production modules only to support tests.

## Template

```python
from sattline_parser.models.ast_model import BasePicture

from .framework import BasePictureAnalyzer


class ExampleTraversalMixin:
    def _walk(self) -> None:
        ...


class ExampleAnalyzer(BasePictureAnalyzer, ExampleTraversalMixin):
    def run(self) -> ExampleReport:
        self._walk()
        return ExampleReport(...)


def analyze_example(base_picture: BasePicture, **kwargs: object) -> ExampleReport:
    analyzer = ExampleAnalyzer(base_picture)
    return analyzer.run()
```

`src/sattlint/analyzers/reset_contamination.py` is the reference migration for this pattern: one production owner, class-backed implementation, and private helper coverage routed through a test-only support namespace.
