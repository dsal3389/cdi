import inspect
from types import ModuleType
from typing import Any, ForwardRef, cast

__all__ = (
    "CdiError",
    "TypeEvaluationError",
    "NoProviderError",
    "ForwardRefError",
    "CircularDependencyError",
)


class CdiError(Exception):
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


class ForwardRefError(CdiError):
    def __init__(self, fr: ForwardRef, module: ModuleType) -> None:
        self._fr = fr
        self._module = module
        super().__init__(
            f"could not evaluate forward reference for {self._fr!s} from module {module.__file__}\n"
            + "try calling `update_forward_ref()` on your container after defining this value"
        )


class CdiInternalError(Exception):
    """
    internal errors act more like signals rather then exceptions, they stop
    execution and the cdi library should act in a specific way when receiving
    those errors
    """


class InternalForwardRefError(CdiInternalError):
    def __init__(self, fr: ForwardRef, module: ModuleType) -> None:
        self._fr = fr
        self._module = module
        super().__init__(
            f"couldn't resolve forward ref {self._fr} coming from module {self._module.__file__}"
        )

    @property
    def fr(self) -> ForwardRef:
        return self._fr

    @property
    def module(self) -> ModuleType:
        return self._module
