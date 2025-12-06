from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any, Generic, TypeVar, cast

if TYPE_CHECKING:
    from ._scope import Scope, _InstanceContext


__all__ = (
    "FixtureMarker",
    "FactoryMarker",
    "Fixture",
    "Factory",
    "Lazy",
    "TypeVarWrapper",
)

_T = TypeVar("_T")


__skip_types__ = (object, Generic)


class FixtureMarker:
    pass


class FactoryMarker:
    pass


Fixture = Annotated[_T, FixtureMarker]
Factory = Annotated[_T, FactoryMarker]


class Lazy(Generic[_T]):
    def __init__(self, scope: Scope, type_: _T, cx: _InstanceContext | None) -> None:
        self._scope = scope
        self._instance: _T | None = None
        self._type = type_
        self._cx = cx

    def wake(self) -> _T:
        """wake up the lazy type for evalutation!!!"""
        if self._instance is None:
            self._instance = cast(
                _T, self._scope.get_instance(self._type, _cx=self._cx)
            )
        return self._instance

    def __str__(self) -> str:
        return f"Lazy[{self._type!s}]"

    def __repr__(self) -> str:
        return f"Lazy[{self._type!r}]"


class TypeVarWrapper:
    def __init__(self, typevar: TypeVar) -> None:
        self._typevar = typevar

    def __hash__(self) -> int:
        from ._typing import hash_typevar

        return hash_typevar(self._typevar)

    def __eq__(self, value: Any, /) -> bool:
        from ._typing import hash_typevar

        if isinstance(value, TypeVar):
            return hash(self) == hash_typevar(value)
        if isinstance(value, TypeVarWrapper):
            return hash(self) == hash(value)
        return False

    def __ne__(self, value: object, /) -> bool:
        return not (self == value)

    def __str__(self) -> str:
        return f"TypeVarWrapper[{self._typevar!s}]"

    def __repr__(self) -> str:
        return f"TypeVarWrapper[{self._typevar!r}]"
