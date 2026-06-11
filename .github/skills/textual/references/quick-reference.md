# Textual Quick Reference

## Minimal App

```python
from textual.app import App, ComposeResult
from textual.widgets import Footer, Header, Static


class MyApp(App[None]):
    CSS_PATH = "app.tcss"

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Hello, Textual!")
        yield Footer()


if __name__ == "__main__":
    MyApp().run()
```

## Ownership Rules

- `App`: global bindings, screen stack, shared state, workers
- `Screen`: one full-terminal view, often a workflow step or modal
- `Widget`: reusable leaf or container with local state
- TCSS: styling, layout, spacing, and visual states

## Lifecycle Checklist

```python
from textual.app import ComposeResult
from textual.widgets import Static
from textual.widget import Widget


class Example(Widget):
    def __init__(self) -> None:
        super().__init__()
        self._loaded = False

    def compose(self) -> ComposeResult:
        yield Static("Ready")

    def on_mount(self) -> None:
        self._loaded = True

    def on_unmount(self) -> None:
        self._loaded = False
```

- Do not mutate reactives directly in `__init__` unless you use `set_reactive()`.
- Use `on_mount()` for setup that depends on mounted widgets.
- Use `on_unmount()` to release timers, workers, or external resources.

## Reactive Patterns

```python
from textual.reactive import reactive
from textual.widget import Widget


class Counter(Widget):
    count = reactive(0)

    def validate_count(self, value: int) -> int:
        return max(0, value)

    def watch_count(self, old_value: int, new_value: int) -> None:
        self.log(f"count changed: {old_value} -> {new_value}")

    def render(self) -> str:
        return f"Count: {self.count}"
```

- `validate_<name>()` constrains values
- `watch_<name>()` reacts to changes
- `compute_<name>()` derives dependent values
- Use `recompose=True` only when the widget tree really needs rebuilding

## Messages: Attributes Down, Messages Up

```python
from textual.message import Message
from textual.widget import Widget


class ChildWidget(Widget):
    class Updated(Message):
        def __init__(self, value: int) -> None:
            super().__init__()
            self.value = value

    def publish(self, value: int) -> None:
        self.post_message(self.Updated(value))


class ParentWidget(Widget):
    def on_child_widget_updated(self, message: ChildWidget.Updated) -> None:
        self.log(f"updated: {message.value}")
```

## Layout Patterns

- Use `Vertical`, `Horizontal`, and `Grid` for structure before custom sizing logic.
- Use `dock: top` and `dock: bottom` for fixed chrome such as headers and footers.
- Use `1fr` and sibling `fr` values for flexible regions.
- Prefer one scroll owner per pane to avoid awkward nested scroll behavior.

## TCSS Patterns

```css
Screen {
    layout: vertical;
}

#toolbar {
    dock: top;
    height: auto;
}

#body {
    width: 1fr;
    height: 1fr;
}

Button.-danger {
    background: $error;
}
```

- Prefer `CSS_PATH` for apps and screens so live reload stays available.
- Use ids for single-instance layout anchors and classes for reusable styles.
- Prefer semantic theme tokens such as `$primary`, `$success`, and `$error`.

## Async and Workers

```python
from textual.worker import work
from textual.widget import Widget


class Loader(Widget):
    @work(exclusive=True)
    async def load_data(self) -> None:
        data = await self.app.api.fetch_items()
        self.notify(f"Loaded {len(data)} items")
```

- Keep blocking work out of event handlers.
- Use workers for network access, filesystem scanning, or heavy parsing.
- Make worker side effects explicit so tests can observe them.

## Testing Pattern

```python
import pytest

from my_app import MyApp


@pytest.mark.asyncio
async def test_submit_button_updates_status() -> None:
    app = MyApp()
    async with app.run_test() as pilot:
        await pilot.click("#submit-button")
        await pilot.pause()

        status = app.query_one("#status")
        assert "Success" in str(status.renderable)
```

- Always wait for the message queue before asserting post-interaction state.
- Query the owning widget directly instead of scraping terminal output.
- Keep tests focused on one interaction or one state transition.

## Debugging Shortcuts

```bash
textual console
textual run --dev my_app.py
textual run --screenshot 5 my_app.py
```

```python
from textual import log

log("debug", locals())
```

## Common Mistakes

- Calling async widget APIs without `await`
- Mutating reactives too early in construction
- Asserting test state before `pilot.pause()`
- Doing synchronous I/O in handlers
- Building large widgets through inheritance when composition is simpler

## SattLint-Specific Notes

- The existing Textual shell lives in `src/sattlint/app_textual.py`.
- Focused tests for the shell live in `tests/test_app_textual.py`.
- In this repo, Textual can be an optional dependency, so preserve import guards and strict-typing accommodations.
- `SelectionList.add_options()` can fail before mount in this repo's usage patterns; populate initial options during construction and reserve incremental updates for mounted widgets.
