import contextvars
import contextlib

from typing import Any, TypeVar
from collections.abc import Hashable, Iterator


_T = TypeVar("_T")


class ContextVar:
    """
    injectable representation of python builtin `contextvars`, providing thread local arguments
    or task local arguments (in async)

    ### memory consumption
    contextvars has a limition that a `ContextVar` is holding a hard reference to its inner value
    and when a thread is dropped, the contextvar is not dropped from the global `Context` causing the inner
    value to never be dropped

    and if the inner value is a list or a dict that holds references, the dict/list items will not be dropped, because
    of that all values can be set only via `limited` contextmanager, so it will ensure a cleanup inside
    the contextvar inner dict
    """

    def __init__(
        self,
        name: str,
    ) -> None:
        """@private"""
        self._name = name
        self._ctx: contextvars.ContextVar[dict[Hashable, Any]] = contextvars.ContextVar(
            name
        )

    @property
    def name(self) -> str:
        return self._name

    def get(self, key: Hashable, default: _T | None = None) -> Any | _T | None:
        """
        tries to return the value for the given key in the thread local contextvar
        if not found returns `default`
        """
        if ctx := self._ctx.get(None):
            return ctx.get(key, default)
        return default

    def _insert(self, key: Hashable, value: Any) -> None:
        current = self._get_value()
        current[key] = value

    def _delete(self, key: Hashable) -> None:
        current = self._get_value()
        current.pop(key, None)

    def _get_value(self) -> dict[Hashable, Any]:
        if (value := self._ctx.get(None)) is None:
            value = {}
            self._ctx.set(value)
        return value

    @contextlib.contextmanager
    def limited(self, **kwargs) -> Iterator[None]:
        """
        binds the given `kwargs` to the thread local contextvar, when leaving the contextmanager
        the `kwargs` are cleaned
        """

        try:
            for key, value in kwargs.items():
                self._insert(key, value)
            yield
        finally:
            for key in kwargs:
                self._delete(key)
