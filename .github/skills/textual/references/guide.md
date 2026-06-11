# Textual Guide

## What This Skill Covers

This guide helps with designing, implementing, testing, and debugging terminal UI code built with Textual. It favors maintainable structure, predictable message flow, and focused validation.

## Architecture Model

Textual is event-driven. The app, active screen, and widget tree cooperate through messages, focus, and reactive state.

### App

- Entry point via `run()`
- Owns global bindings, modes, workers, and shared state
- Pushes and pops screens
- Configures TCSS with `CSS_PATH` or inline `CSS`

### Screen

- Full-terminal container for one workflow or dialog
- Good fit for modal prompts, settings pages, browsers, and multi-step flows
- Can define bindings, actions, and screen-local composition

### Widget

- Reusable component that owns a rectangular region
- Handles local rendering, events, and small state transitions
- Best when composed from smaller widgets instead of deep inheritance chains

## Recommended Design Process

1. Sketch the screen before writing code.
2. Build fixed chrome first: headers, footers, side panels, status bars.
3. Add flexible content areas with `fr` sizing.
4. Decide where state lives before wiring events.
5. Add one focused interaction test for each critical path.

## State and Communication

The safest default is attributes down, messages up.

- Parent widgets pass configuration and state into children.
- Children post messages when something happened.
- Shared cross-screen state belongs at the app layer.
- Screen-specific workflow state belongs on the active screen.
- Widget-private display state stays inside the widget.

Use reactive attributes for state that should refresh the UI. Use plain attributes for supporting data that does not affect rendering.

## Reactive Programming Guidance

Reactive attributes are powerful, but they need discipline.

- Use `validate_<name>()` to enforce invariants.
- Use `watch_<name>()` for side effects or synchronized updates.
- Use `compute_<name>()` for derived values.
- Prefer direct rendering from reactives instead of calling refresh methods manually.
- Avoid changing reactives directly in `__init__` unless you use `set_reactive()`.

Example:

```python
from textual.reactive import reactive
from textual.widget import Widget


class SearchPanel(Widget):
    query = reactive("")
    result_count = reactive(0)

    def watch_query(self, value: str) -> None:
        self.result_count = len(value.split()) if value else 0

    def render(self) -> str:
        return f"Results: {self.result_count}"
```

## Layout and TCSS

Textual layout is usually simpler when structure and style stay separate.

- Define layout structure in widgets and containers.
- Define spacing, alignment, colors, and focus states in TCSS.
- Prefer ids for anchors like `#sidebar` or `#results`.
- Prefer classes for reusable semantic styles.
- Use semantic colors instead of hard-coded ANSI assumptions.

Useful layout defaults:

- `dock: top` or `dock: bottom` for fixed bars
- `height: auto` for content-sized controls
- `width: 1fr` and `height: 1fr` for fill regions
- `overflow-y: auto` on the scrollable child pane instead of the outer layout shell

## Code Organization

For anything beyond a small demo, split responsibilities.

Suggested layout:

```text
project/
├── src/
│   ├── app.py
│   ├── screens/
│   ├── widgets/
│   └── services/
├── static/
│   └── app.tcss
└── tests/
```

Practical rules:

- Keep business logic outside widgets when possible.
- Use services or model objects for data loading and transformation.
- Let widgets focus on presentation, interaction, and local state.
- Prefer composition over inheritance for reusable UI building blocks.

## Performance Guidance

- Aim for smooth updates instead of maximum feature density.
- Use `Static` when cached rendering is enough.
- Avoid rebuilding large subtrees when a reactive text or class update is sufficient.
- Cache expensive pure computations.
- Move network or blocking work into workers.

## Accessibility and Keyboard UX

- Ensure every interactive control is reachable by keyboard.
- Set `can_focus = True` when a custom widget must participate in navigation.
- Provide clear key bindings for primary actions.
- Test narrow terminal widths and short heights.
- Avoid relying only on color to convey status.

## Testing Strategy

Textual tests are strongest when they validate behavior through the public widget tree.

Recommended pattern:

```python
import pytest

from my_app import MyApp


@pytest.mark.asyncio
async def test_opens_dialog() -> None:
    app = MyApp()

    async with app.run_test() as pilot:
        await pilot.press("ctrl+d")
        await pilot.pause()

        dialog = app.screen.query_one("#dialog")
        assert dialog.display is True
```

Testing rules:

- One interaction, one expectation cluster.
- Always pause after interactions that enqueue work.
- Query widgets and state directly.
- Keep tests deterministic by isolating external I/O.
- Prefer focused screen or widget tests over broad snapshot-style tests.

## Debugging Workflow

When a Textual feature misbehaves, check these in order:

1. Is the handler async when it needs to await Textual APIs?
2. Is the widget mounted before it is queried or mutated?
3. Is a reactive watcher firing earlier than expected?
4. Is focus on the widget that owns the binding?
5. Is TCSS hiding or collapsing the widget?
6. Is blocking work starving the event loop?

Useful tools:

- `textual console`
- `textual run --dev my_app.py`
- `textual run --screenshot 5 my_app.py`
- `textual.log()` or `from textual import log`

## Common Mistakes and Fixes

### Forgetting to await mount or screen operations

```python
# Wrong
def on_button_pressed(self) -> None:
    self.mount(StatusWidget())

# Right
async def on_button_pressed(self) -> None:
    await self.mount(StatusWidget())
```

### Asserting test results before the queue settles

```python
# Wrong
await pilot.click("#submit")
assert app.query_one("#status").text == "Done"

# Right
await pilot.click("#submit")
await pilot.pause()
assert app.query_one("#status").text == "Done"
```

### Triggering watchers too early

```python
# Wrong
def __init__(self) -> None:
    super().__init__()
    self.count = 10

# Right
def __init__(self) -> None:
    super().__init__()
    self.set_reactive(MyWidget.count, 10)
```

### Blocking the UI thread

```python
# Wrong
def on_button_pressed(self) -> None:
    data = requests.get("https://example.com").json()
    self.notify(str(data))

# Better
from textual.worker import work


@work(exclusive=True)
async def load_data(self) -> None:
    data = await self.api.fetch_json()
    self.notify(str(data))
```

## Repo-Specific Notes For SattLint

If you are modifying the existing SattLint Textual shell, start with these files:

- `src/sattlint/app_textual.py`
- `src/sattlint/_app_textual_shared.py`
- `src/sattlint/_app_textual_setup.py`
- `tests/test_app_textual.py`

Important local constraints:

- Textual is optional in the default repo environment, so preserve import guards and typing workarounds already in place.
- In this repo, `SelectionList.add_options()` can fail before mount; build initial options during construction and use incremental updates only after mount.
- `src/sattlint/app_textual.tcss` has duplicated layout rules for some header and view selectors, so mirrored edits may be required.
- Keep scrolling on child panes rather than `#view-host` to avoid scrollbar overlap with header actions.

## How To Assist Well

When using this skill to help a user:

1. Identify the concrete Textual surface first.
2. Verify lifecycle, async, focus, and mount assumptions.
3. Prefer minimal examples that can run unchanged.
4. Explain the recommended pattern, not just the fix.
5. Include a focused test when implementing behavior changes.
6. Offer debugging steps when the failure mode is not obvious.
