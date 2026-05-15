from __future__ import annotations

from typing import Any


class _FakeVar:
    def __init__(self, value: Any) -> None:
        self.value = value

    def get(self) -> Any:
        return self.value

    def set(self, value: Any) -> None:
        self.value = value


class _FakeLabel:
    def __init__(self) -> None:
        self.text = ""

    def configure(self, *, text: str) -> None:
        self.text = text


class _FakeListbox:
    def __init__(self, items: list[str] | None = None) -> None:
        self.items = list(items or [])
        self._selection: tuple[int, ...] = ()

    def delete(self, first: int, last: Any = None) -> None:
        if last is None:
            del self.items[first]
            return
        self.items.clear()

    def insert(self, _index: Any, value: str) -> None:
        self.items.append(value)

    def get(self, index: int) -> str:
        return self.items[index]

    def size(self) -> int:
        return len(self.items)

    def curselection(self) -> tuple[int, ...]:
        return self._selection


class _FakeTextWidget:
    def __init__(self) -> None:
        self.content = ""
        self.state = "normal"
        self.insert_calls: list[tuple[str, str | None]] = []
        self.tag_calls: list[tuple[str, dict[str, Any]]] = []
        self.seen: str | None = None

    def tag_configure(self, tag: str, **kwargs: Any) -> None:
        self.tag_calls.append((tag, kwargs))

    def configure(self, **kwargs: Any) -> None:
        if "state" in kwargs:
            self.state = kwargs["state"]

    def delete(self, _start: str, _end: str) -> None:
        self.content = ""

    def insert(self, _index: str, text: str, tag: str | None = None) -> None:
        self.content += text
        self.insert_calls.append((text, tag))

    def index(self, _index: str) -> str:
        return "1.0" if not self.content else "2.0"

    def see(self, index: str) -> None:
        self.seen = index

    def get(self, _start: str, _end: str) -> str:
        return self.content


__all__ = ["_FakeLabel", "_FakeListbox", "_FakeTextWidget", "_FakeVar"]
