from typing import TypeVar
from collections.abc import Callable

from ._scope import Scope
from ._factory import FuncParameters, ParameterKind
from ._exceptions import ResolveForwardRefError
from ._typing import is_forward_ref


T = TypeVar("T")


def call(scope: Scope, func: Callable[..., T]) -> T:
    """
    calls the given function, the function arguments are resolved
    with the provided scope
    """
    func_args = []
    func_kwargs = {}

    for name, parameter in FuncParameters().get_parameters(func).items():
        if is_forward_ref(parameter.annotation):
            raise ResolveForwardRefError(
                f"function `{func.__name__}` annotated argument `{name}` is forward reference that was not resolved"  # type: ignore
            )

        value = scope.get_instance(parameter.annotation)

        match parameter.kind:
            case ParameterKind.POSITIONAL:
                func_args.append(value)
            case ParameterKind.KEYWORD:
                func_kwargs[name] = value
    return func(*func_args, **func_kwargs)
