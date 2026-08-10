from collections.abc import Callable, Hashable
from typing import Generic, TypeVar

_T = TypeVar("_T")


class Registry(Generic[_T]):
    def __init__(self, key_factory: Callable[[_T], Hashable]) -> None:
        self._key_factory = key_factory
        self._items = {}

    def add(self, item: _T) -> None:
        key = self._key_factory(item)
        self._items[key] = item

    def get(self, key: Hashable) -> _T | None:
        return self._items.get(key)
