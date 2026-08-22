import inspect
import itertools
from collections.abc import Iterable
from types import ModuleType
from typing import cast

__all__ = (
    "CdiError",
    "IncorrectStackPopping",
    "NoFactoryForTypeError",
    "TypeEvaluationError",
    "CircularDependencyError",
)

def _stack_traceback_message(stack: Iterable[type]) -> str:
    traceback = []
    for i, stack_type in enumerate(stack, start=1):
        module = cast(ModuleType, inspect.getmodule(stack_type))
        traceback.append(("  " * i) + f"-> {module.__name__} - {stack_type.__qualname__}")
    return "\n".join(traceback)


class CdiError(Exception):
    pass


class IncorrectStackPopping(CdiError):
    pass


class NoFactoryForTypeError(CdiError):
    def __init__(
        self,
        stack: tuple[type, ...],
        type_: type
    ) -> None:
        message = (
            f"No factory was provided for required type `{type_}`, backtrace:\n"
            + _stack_traceback_message(stack)
        )
        super().__init__(message)


class TypeEvaluationError(CdiError):
    def __init__(
        self,
        message: str,
        type_name: str,
    ) -> None:
        super().__init__(message)
        self._type_name = type_name

    @property
    def type_name(self) -> str:
        return self._type_name


class CircularDependencyError(CdiError):
    def __init__(self, stack: tuple[type, ...], type_: type) -> None:
        message = (
            f"Circular dependency detected when trying to resolve `{stack[0].__name__}` by type `{type_.__name__}`, traceback:\n"
            + _stack_traceback_message(itertools.chain(stack, (type_,)))
        )
        super().__init__(message)
