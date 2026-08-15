import inspect
from types import ModuleType
from typing import Any, cast

__all__ = (
    "CdiError",
    "IncorrectStackPopping",
    "TypeEvaluationError",
    "NoProviderError",
    "CircularDependencyError",
)


class CdiError(Exception):
    pass


class IncorrectStackPopping(CdiError):
    pass


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


class NoProviderError(CdiError):
    pass


class CircularDependencyError(CdiError):
    def __init__(self, stack: tuple[Any, ...]) -> None:
        self._stack = stack
        error_stack_message = "Circular dependency detected, type stack:"

        for i, tt in enumerate(stack):
            module = cast(ModuleType, inspect.getmodule(tt))
            error_stack_message += f"\n\t{i}. module {module.__name__} :: {tt}"
        super().__init__(error_stack_message)
