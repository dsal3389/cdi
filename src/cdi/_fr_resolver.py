from __future__ import annotations

from types import ModuleType
from typing import ForwardRef, Protocol, Any, TypeVar
from collections.abc import Mapping

from ._exceptions import ResolveForwardRefError


T = TypeVar("T", contravariant=True)


class ForwardRefResolveStrategy(Protocol):
    def evaluate(self, type_: ForwardRef) -> Any: ...


class ForwardRefResolveByMapStrategy:
    def __init__(self, map_: Mapping[str, type]) -> None:
        self._map = map_

    def evaluate(self, type_: ForwardRef) -> Any:
        type_arg = type_.__forward_arg__
        if evaluated := self._map.get(type_arg):
            return evaluated
        raise ResolveForwardRefError(
            f"couldn't resolve forward reference `{type_arg}` from given mapping, available types were: "
            + ", ".join(self._map.keys()),
        )


class ForwardRefResolveByModuleStrategy:
    def __init__(self, module: ModuleType) -> None:
        self._module = module

    def evaluate(self, type_: ForwardRef) -> Any:
        globalns = self._module.__dict__
        localns = {}

        try:
            return type_._evaluate(globalns, localns, frozenset())
        except NameError:
            raise ResolveForwardRefError(
                f"couldn't evaluate forward reference `{type_.__forward_arg__}` from given module `{self._module}`",
            )


class ForwardRefResolver:
    def __init__(
        self,
        strategy: ForwardRefResolveStrategy
    ) -> None:
        self._strategy = strategy

    def resolve(self, forward_ref: ForwardRef | str) -> Any:
        if not isinstance(forward_ref, ForwardRef):
            forward_ref = ForwardRef(forward_ref)
        return self._strategy.evaluate(forward_ref)
