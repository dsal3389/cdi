from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any, Annotated, get_origin, get_args

from ._types import Lazy
from ._typing import is_fixture_annotation

if TYPE_CHECKING:
    from ._container import Container


class Scope:
    """
    the scope defines the life time of objects and it is bound to a single container where
    the container provide the supported types for the scope and type resolution
    """

    def __init__(self, container: Container, name: str | None = None) -> None:
        self._container = container
        self._instances = {}
        self._name = name
        self._lock = threading.Lock()

    def get_instance(self, type_: Any) -> Any:
        origin = get_origin(type_)

        if origin is Lazy:
            lazy_type = get_args(type_)[0]
            return Lazy(scope=self, type_=lazy_type)

        if origin is Annotated:
            anno_type, *_ = get_args(type_)

            if is_fixture_annotation(anno_type):
                return self._get_fixture(anno_type)
            else:
                return self._get_factory(anno_type)
        return self._get_factory(type_)

    def _get_factory(self, type_: Any) -> Any:
        if type_ in self._instances:
            return self._instances[type_]

        if (provider := self._container.get_provider(type_)) is None:
            return None

        instance = provider._callable()
        self._instances[type_] = instance
        return instance

    def _get_fixture(self, type_: type[Any]) -> Any:
        pass
