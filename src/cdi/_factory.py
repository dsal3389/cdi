from __future__ import annotations

import enum
import inspect

from types import ModuleType, GenericAlias
from typing import ForwardRef, Generic, TypeVar, NewType, get_args, get_origin, cast
from collections.abc import Sequence, Callable

from ._typing import _get_type_vars, is_typevar, is_forward_ref, evaluate_forward_ref


T = TypeVar("T")


class ParameterKind(enum.Enum):
    POSITIONAL = enum.auto()
    KEYWORD = enum.auto()


class FactoryParameter:
    def __init__(
        self,
        annotation: type,
        kind: ParameterKind,
        module: ModuleType
    ) -> None:
        self._annotation = annotation
        self._module = module
        self._kind = kind

    @property
    def annotation(self) -> type:
        return self._annotation

    @property
    def kind(self) -> ParameterKind:
        return self._kind

    @property
    def module(self) -> ModuleType:
        return self._module

    def evaluate(self) -> bool:
        if is_forward_ref(self._annotation):
            if (evaluated := evaluate_forward_ref(
                cast(ForwardRef | str, self._annotation),
                self._module.__dict__,
                {}
            )) is None:
                return False
            self._annotation = evaluated
        return True


_FactoryParameters = NewType("_FactoryParameters", dict[str, FactoryParameter])


class FactoryParametersFromMro:
    """
    tries to build factory parameters from a mro sequence, this will respect
    generic arguments that were passed in the mro
    """

    __skip__ = (
        object,
        Generic,
    )

    def get_parameters(self, mro: Sequence[type], method_name: str) -> _FactoryParameters:
        parameters = {}
        orig_bases = {}

        for mro_cls in mro:
            # we walk over all the mro orig bases and look for generic aliases, this will
            # help us later when we see the generic alias origin in the mro, we can see what
            # generic arguments were passes to the orig base, for example
            # __mro__ = (Foo, Boo typing.Generic, object)
            # __orig_base__ = (Foo, Boo)
            #
            # `Boo` can accept generic args, but in the `__mro__` we don't know what they
            # were set to, they were set by `Foo`, so `Foo.__orig_bases__` will resolve
            # to `(Boo[int])`, then when we see `Boo` later in the `__mro__` we know
            # what was the value for the generic
            for orig_base in cast(tuple[GenericAlias | type], getattr(mro_cls, '__orig_bases__', ())):
                if (origin := get_origin(orig_base)) is None or origin is Generic:
                    continue

                args = get_args(orig_base)
                orig_bases[origin] = list(zip(_get_type_vars(origin.__orig_bases__), args))

            if args := orig_bases.get(mro_cls):
                typevar_to_value = {typevar: value for typevar, value in args}
            else:
                typevar_to_value = {}

            # we look for the method in the current class, if it is not defined, we move
            # to the next mro class, we do not want to use `getatter` here because it will
            # resolve for us attribute based on the inheritance
            if mro_cls in self.__skip__ or (method := mro_cls.__dict__.get(method_name, None)) is None:
                continue

            should_continue = False
            signature = inspect.signature(method, eval_str=False)

            for name, parameter in signature.parameters.items():
                # if we already processed the parameter with the same name
                # then we don't need to process it from the current signature which
                # is likely to be a parent class
                if name in parameters or name == "self":
                    continue

                # if we have `args` and `**kwargs` parameters
                # we should continue to parse the upper mro `__init__` methods
                if parameter.kind in (parameter.VAR_KEYWORD, parameter.VAR_POSITIONAL):
                    should_continue = True
                    continue

                parameters[name] = parameter = FactoryParameter(
                    annotation=parameter.annotation,
                    kind=ParameterKind.POSITIONAL if parameter.kind is parameter.POSITIONAL_ONLY else ParameterKind.KEYWORD,
                    module=cast(ModuleType, inspect.getmodule(mro_cls))
                )

                # we try to evaluate to the real value is the annotation is a forward ref
                # then we check if it is a typevar and we try to resolve the typevar to the real value
                # that was passed to the mro_cls in the generics
                if parameter.evaluate() and is_typevar(parameter.annotation) and (real_annotation := typevar_to_value.get(parameter.annotation)):
                    parameters[name] = FactoryParameter(
                        annotation=real_annotation,
                        kind=parameter.kind,
                        module=parameter.module
                    )

            if not should_continue:
                break
        return _FactoryParameters(parameters)


class Factory(Generic[T]):
    def __init__(
        self,
        parameters: _FactoryParameters,
        func_impl: Callable[..., T],
        return_type: type[T],
    ) -> None:
        self._func = func_impl
        self._return_type = return_type
        self._parameters = parameters

    @property
    def parameters(self) -> _FactoryParameters:
        return self._parameters

    @property
    def return_type(self) -> type[T]:
        return self._return_type

    def __call__(self, *args, **kwargs) -> T:
        return self._func(*args, **kwargs)
