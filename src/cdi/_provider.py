from __future__ import annotations

import inspect
from collections import defaultdict
from collections.abc import Callable
from typing import Any, Generic, TypeVar, get_args, get_origin

from ._consts import __skip_types__
from ._exceptions import MissingAnnotation
from ._typing import calculate_type_metric, get_generics, is_typealias

__all__ = ("Provider", "provider_from_class")


class Provider:
    def __init__(
        self,
        callable: Callable[..., Any],
        callable_args: tuple[Any, ...],
        callable_kwargs: dict[str, Any],
        metric: int,
    ) -> None:
        self._callable = callable
        self._args = callable_args
        self._kwargs = callable_kwargs
        self._metric = metric

    @property
    def args(self) -> tuple[Any, ...]:
        return self._args

    @property
    def kwargs(self) -> dict[str, Any]:
        return self._kwargs

    @property
    def metric(self) -> int:
        return self._metric

    def __call__(self, *args, **kwargs) -> Any:
        return self._callable(*args, **kwargs)

    def __str__(self) -> str:
        return f"Provider[{self._callable.__name__} | {self._metric}]"

    def __repr__(self) -> str:
        return f"_Provider(callable={self._callable!r}, priority={self._metric!r})"


def provider_from_class(cls: Any, func_name: str) -> Provider:
    if is_typealias(cls):
        typeargs = {g.__name__: v for g, v in zip(get_generics(cls), get_args(cls))}
        origin = get_origin(cls)
    else:
        typeargs = {g.__name__: g for g in get_generics(cls)}
        origin = cls

    # create a mapping between an origin base type
    # to its typealias as can be found in `cls.__orig_bases__`
    orig_bases_typeargs = defaultdict(dict)

    for orig_base in getattr(origin, "__orig_bases__", ()):
        if not is_typealias(orig_base) or orig_base in __skip_types__:
            continue

        base_origin = get_origin(orig_base)
        for generic, arg in zip(get_generics(orig_base), get_args(orig_base)):
            if isinstance(arg, TypeVar):
                orig_bases_typeargs[base_origin][generic.__name__] = typeargs[
                    arg.__name__
                ]
            else:
                orig_bases_typeargs[base_origin][generic.__name__] = arg

    # start iterating over the mro tree in a reversed ordered
    # this will help us pop items from the end of the stack and if we want to check
    # if a function is inherited from the parent, we can always check the function
    # agains the function from the next parent which is the last item in the mro stack
    mro_stack = list(reversed(origin.__mro__))
    continue_mro = True

    callable_args = []
    callable_kwargs = {}
    processed_parameter_names = set()

    while continue_mro and mro_stack:
        mro_cls = mro_stack.pop()

        if (callable := getattr(mro_cls, func_name, None)) is None:
            break

        # if we still have items in the stack and the current function is also
        # the same function as can be found in the parent class, it means current cls
        # inherit the function from the next cls in the mro stack
        if mro_stack and getattr(mro_stack[-1], func_name, None) is callable:
            continue

        if mro_cls in orig_bases_typeargs:
            typeargs = orig_bases_typeargs[mro_cls]
        else:
            typeargs = {}

        signature = inspect.signature(callable, eval_str=True)

        # we always set continue mro to False and we change it
        # to True only if we find *args or **kwargs in the
        # function signature
        continue_mro = False

        for name, parameter in signature.parameters.items():
            if name == "self":
                continue

            if parameter.kind in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            ):
                continue_mro = True
                continue

            # if we already processed the parameter
            # from some other mro class before, we should skip it
            if name in processed_parameter_names:
                continue

            if parameter.annotation is parameter.empty:
                raise MissingAnnotation(
                    f"missing parameter annotation for `{mro_cls.__name__}.{callable}({name}, ...)`, while parsing mro tree of `{origin.__name__}`"
                )

            if isinstance(parameter.annotation, TypeVar):
                parameter_type = typeargs[parameter.annotation.__name__]
            else:
                parameter_type = parameter.annotation

            if parameter.kind is inspect.Parameter.KEYWORD_ONLY:
                callable_kwargs[name] = parameter_type
            else:
                callable_args.append(parameter_type)
    return Provider(
        callable=cls,
        callable_args=tuple(callable_args),
        callable_kwargs=callable_kwargs,
        metric=calculate_type_metric(cls),
    )
