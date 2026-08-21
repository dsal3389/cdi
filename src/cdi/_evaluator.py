from __future__ import annotations

from types import ModuleType
from typing import TYPE_CHECKING, ForwardRef, Protocol, Any, TypeVar, Generic
from collections.abc import Mapping

from ._exceptions import TypeEvaluationError
from ._typing import _as_forward_ref

if TYPE_CHECKING:
    from ._factory import Factory, FactoryParameter


T = TypeVar("T", contravariant=True)


class TypeEvaluator(Generic[T], Protocol):
    def evaluate(self, type_: T) -> Any: ...


class TypeMapEvaluator:
    def __init__(self, map_: Mapping[str, type]) -> None:
        self._map = map_

    def evaluate(self, type_: str | ForwardRef) -> Any:
        if isinstance(type_, ForwardRef):
            type_ = type_.__forward_arg__
        if evaluated := self._map.get(type_):
            return evaluated
        raise TypeEvaluationError(
            f"couldn't evaluate forward reference `{type_}` from given mapping, available types were: "
            + ", ".join(self._map.keys()),
            type_name=type_,
        )


class TypeModuleEvaluator:
    def __init__(self, module: ModuleType) -> None:
        self._module = module

    def evaluate(self, type_: str | ForwardRef) -> Any:
        if not isinstance(type_, ForwardRef):
            type_ = _as_forward_ref(type_)

        globalns = self._module.__dict__
        localns = {}

        try:
            return type_._evaluate(globalns, localns, frozenset())
        except NameError:
            raise TypeEvaluationError(
                f"couldn't evaluate forward reference `{type_.__forward_arg__}` from given module `{self._module}`",
                type_name=type_.__forward_arg__,
            )


class FactoryParameterEvaluatorProxy:
    """
    the class has no evaluation logic, it is a proxy to the given evaluator
    that gives a helpful error message in case of evaluation error
    """

    def __init__(self, factory: Factory, evaluator: TypeEvaluator) -> None:
        self._factory = factory
        self._evaluator = evaluator

    def evaluate(self, type_: tuple[str, FactoryParameter]) -> type:
        name, parameter = type_

        try:
            return self._evaluator.evaluate(parameter.annotation)
        except TypeEvaluationError as e:
            raise TypeEvaluationError(
                f"couldn't evaluate factory parameter `{self._factory.name}({name}: {e.type_name}, ...)`",
                type_name=e.type_name,
            )
