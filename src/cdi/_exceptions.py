import inspect
from types import ModuleType
from typing import Any, ForwardRef, cast

__all__ = (
    "CdiError",
    "NoProviderError",
    "MissingAnnotationError",
    "ForwardRefError",
    "CircularDependencyError",
)


class CdiError(Exception):
    pass


class MissingAnnotationError(CdiError):
    pass


class NoProviderError(CdiError):
    pass


class CircularDependencyError(CdiError):
    def __init__(self, stack: tuple[Any, ...]) -> None:
        self._stack = stack
        error_stack_message = "Circular dependency detected, type stack:"

        for tt in stack:
            module = cast(ModuleType, inspect.getmodule(tt))
            error_stack_message += f"\n\t{tt.__name__}"
            error_stack_message += f"\n\t\tcoming from module `{module.__path__}`"
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
