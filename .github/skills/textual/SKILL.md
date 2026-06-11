---
name: textual
description: 'Expert guidance for building or modifying Python TUI applications with Textual. Use for apps, screens, widgets, TCSS styling, reactive state, workers, focus, message flow, pilot tests, and terminal UI debugging.'
argument-hint: 'Describe the Textual app, screen, widget, layout, test, or error you need help with.'
user-invocable: true
---

# Textual

Use this skill when working on Python terminal UI code built with Textual. It covers application structure, screens, widgets, TCSS styling, reactive state, async workers, focused testing, and common failure modes.

## When To Use

- Build or modify a Textual app, screen, or widget
- Design terminal layouts or TCSS styling
- Wire reactive state, message flow, or focus behavior
- Debug mount, refresh, keyboard, or rendering issues
- Add or repair Textual tests
- Review TUI performance, accessibility, or maintainability

## Working Approach

1. Identify the owning surface first: app, screen, widget, TCSS, or test.
2. Verify lifecycle basics: `compose()`, `on_mount()`, `on_unmount()`, async handlers, and worker usage.
3. Keep state boundaries clear: attributes down, messages up.
4. Prefer composition, external TCSS, and container widgets over custom layout code.
5. Add or update a focused test, then validate with the narrowest runnable check.

## Core Guidance

- `App` owns global bindings, screen navigation, and shared state.
- `Screen` owns a full-terminal view or modal interaction.
- `Widget` owns local rendering, events, and focus behavior.
- Reactive attributes should drive UI updates instead of manual refresh chains.
- Use workers for network or blocking I/O so the event loop stays responsive.
- Prefer semantic TCSS and stable ids or classes over ad hoc styling.

## Common Failure Checks

- Missing `await` on async mount or update APIs
- Reactive values changed too early in `__init__`
- Tests asserting before `await pilot.pause()`
- Blocking work inside event handlers
- Styling or querying widgets before mount completes
- Focus or key-binding conflicts across app, screen, and widget layers

## References

- [Quick reference](./references/quick-reference.md)
- [Architecture and patterns](./references/guide.md)

## SattLint Notes

- SattLint already has a Textual shell in `src/sattlint/app_textual.py` and focused coverage in `tests/test_app_textual.py`.
- Preserve optional-import and typing guards when editing repo Textual surfaces.
- Reuse the repo's existing TCSS and Pilot-style test patterns before introducing new ones.
