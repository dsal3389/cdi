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


class CircularDependencyError(CdiError):
    def __init__(self, stack: tuple[type, ...], type_: type) -> None:
        error_stack_message = f"Circular dependency detected when trying to resolve `{stack[0].__name__}` by type `{type_.__name__}`:"

        for stack_type in stack:
            module = cast(ModuleType, inspect.getmodule(stack_type))
            error_stack_message += f"\n    {module.__name__} - {stack_type.__qualname__}"

        module = cast(ModuleType, inspect.getmodule(type_))
        error_stack_message += f"\n    {module.__name__} - {type_.__qualname__}"
        super().__init__(error_stack_message)
