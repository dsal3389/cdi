from collections.abc import Callable, Hashable
from typing import Generic, TypeVar

_T = TypeVar("_T")


class Registry(Generic[_T]):
    """
    a helper class that items can be added into and the items keys will
    be calculated based on the provided `key_factory` in the init, thus providing
    consistant key generation and prevents the key generation in multiple places
    """

    def __init__(self, key_factory: Callable[[_T], Hashable]) -> None:
        self._key_factory = key_factory
        self._items = {}

    def add(self, item: _T) -> None:
        key = self._key_factory(item)
        self._items[key] = item

    def get(self, key: Hashable) -> _T | None:
        return self._items.get(key)
