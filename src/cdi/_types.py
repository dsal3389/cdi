from __future__ import annotations
from typing import TYPE_CHECKING, Annotated, TypeVar, Generic, cast

if TYPE_CHECKING:
    from ._scope import Scope


__all__ = ("FixtureMarker", "FactoryMarker", "Fixture", "Factory", "Lazy")

_T = TypeVar("_T")


__skip_types__ = (object, Generic)


class FixtureMarker:
    pass


class FactoryMarker:
    pass


Fixture = Annotated[_T, FixtureMarker]
Factory = Annotated[_T, FactoryMarker]


class Lazy(Generic[_T]):
    def __init__(self, scope: Scope, type_: _T) -> None:
        self._scope = scope
        self._instance: _T | None = None
        self._type = type_

    def wake(self) -> _T:
        """wake up the lazy type for evalutation!!!"""
        if self._instance is None:
            self._instance = cast(_T, self._scope.get_instance(self._type))
            if self._instance is None:
                raise RuntimeError
        return self._instance

    def __str__(self) -> str:
        return f"Lazy[{self._type!s}]"

    def __repr__(self) -> str:
        return f"Lazy[{self._type!r}]"
