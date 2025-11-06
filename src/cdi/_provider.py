from __future__ import annotations

import inspect
from typing import Any
from collections.abc import Callable

from ._consts import __skip_types__
from ._exceptions import MissingAnnotation
from ._typing import calculate_type_metric


__all__ = ("Provider",)


class Provider:
    def __init__(
        self,
        callable: Callable[..., Any],
        callable_args: tuple[Any, ...],
        callable_kwargs: dict[str, Any],
        metric: int,
    ) -> None:
        # self._dependencies = dependencies
        self._callable = callable
        self._metric = metric

    @property
    def metric(self) -> int:
        return self._metric

    def __str__(self) -> str:
        return f"Provider[{self._callable.__name__} | {self._metric}]"

    def __repr__(self) -> str:
        return f"_Provider(callable={self._callable!r}, priority={self._metric!r})"

    @classmethod
    def from_class(cls, provider_cls: Any) -> Provider:
        args = []
        kwargs = {}
        processed_parameter_names = set()
        continue_mro = True

        for mro_cls in cls.__mro__:
            if mro_cls in __skip_types__:
                continue

            if not continue_mro:
                break

            # by default we want to always not process the
            # mro in the next loop iteration unless we find *args or **kwargs
            # in the init parameter
            continue_mro = False

            signature = inspect.signature(mro_cls.__init__, eval_str=True)

            for name, parameter in signature.parameters.items():
                if name == "self":
                    continue

                # if the the parameter is *args or **kwargs it most likely mean
                # that we want to take the argument from the next (parent) mro
                if parameter.kind in (
                    inspect.Parameter.VAR_POSITIONAL,
                    inspect.Parameter.VAR_KEYWORD,
                ):
                    continue_mro = True
                    continue

                # if we already proccessed a parameter with that name
                # (probably from previous mro classes) we don't need to
                # process the parameter from current mro_cls
                if name in processed_parameter_names:
                    continue

                if parameter.annotation is parameter.empty:
                    raise MissingAnnotation(
                        f"missing parameter `{mro_cls.__name__}.__init__({name}, ...)` annotation "
                        + f"this required by `{provider_cls.__name__}`"
                    )

                if inspect.Parameter.KEYWORD_ONLY:
                    kwargs[name] = parameter.annotation
                else:
                    args.append(parameter.annotation)
                processed_parameter_names.add(name)

        return Provider(
            callable=provider_cls,
            callable_args=tuple(args),
            callable_kwargs=kwargs,
            metric=calculate_type_metric(provider_cls),
        )
