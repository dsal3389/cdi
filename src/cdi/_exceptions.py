import inspect
import itertools
from types import ModuleType
from typing import cast
from collections.abc import Iterable

__all__ = (
    "CdiError",
    "ResolveForwardRefError",
    "IncorrectStackPopping",
    "NoFactoryForTypeError",
    "TypeEvaluationError",
    "CircularDependencyError",
)


def _stack_traceback_message(stack: Iterable[type]) -> str:
    traceback = []
    for i, stack_type in enumerate(stack, start=1):
        module = cast(ModuleType, inspect.getmodule(stack_type))
        traceback.append(("  " * i) + f"-> {module.__name__} - {stack_type}")
    return "\n".join(traceback)


class CdiError(Exception):
    """
    an umbrella type that all `cdi` exceptions inherit from, this can
    be used as a catch all possible `cdi` specific errors
    """


class IncorrectStackPopping(CdiError):
    """
    should not be experianced by end user, if you do get this
    errro raised, please open and issue
    """


class ResolveForwardRefError(CdiError):
    """
    raised when the internal forward ref resolver couldn't resolve a forward
    reference to the real python type
    """


class TypeEvaluationError(CdiError):
    """raise when the given type could not be evaluated, couldn't create an instance"""


class NoFactoryForTypeError(CdiError):
    """raise when no factory found for the required type in the container"""

    def __init__(self, stack: tuple[type, ...], type_: type) -> None:
        message = (
            f"No factory was provided for required type `{type_}`, backtrace:\n"
            + _stack_traceback_message(stack)
        )
        super().__init__(message)


class CircularDependencyError(CdiError):
    """
    raise when injectable have circular dependancy, A requires B while B requires
    A, this case is impossible and explicit handling is required, the evaluation
    stacktrace is also printed
    """

    def __init__(self, stack: tuple[type, ...], type_: type) -> None:
        """@private"""
        message = (
            f"Circular dependency detected when trying to resolve `{stack[0].__name__}` by type `{type_.__name__}`, traceback:\n"
            + _stack_traceback_message(itertools.chain(stack, (type_,)))
        )
        super().__init__(message)
