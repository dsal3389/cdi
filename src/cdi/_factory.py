from __future__ import annotations

import enum
import inspect

from types import ModuleType, GenericAlias
from typing import Generic, TypeVar, NewType, Any, get_args, get_origin, cast
from collections.abc import Sequence, Callable

from typing_extensions import Self

from ._fr_resolver import ForwardRefResolver, ForwardRefResolveByModuleStrategy
from ._exceptions import ResolveForwardRefError
from ._typing import _get_type_vars, is_typevar, is_forward_ref


T = TypeVar("T")


class ParameterKind(enum.Enum):
    POSITIONAL = enum.auto()
    KEYWORD = enum.auto()


class FactoryParameter:
    def __init__(
        self, annotation: type, kind: ParameterKind, module: ModuleType
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


FactoryParameters = NewType("FactoryParameters", dict[str, FactoryParameter])


class MroParameters:
    """
    tries to build factory parameters from a mro sequence, this will respect
    generic arguments that were passed in the mro
    """

    __skip__ = (
        object,
        Generic,
    )

    def get_parameters(
        self, mro: Sequence[type], method_name: str
    ) -> FactoryParameters:
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
            for orig_base in cast(
                tuple[GenericAlias | type], getattr(mro_cls, "__orig_bases__", ())
            ):
                if (origin := get_origin(orig_base)) is None or origin is Generic:
                    continue

                args = get_args(orig_base)
                orig_bases[origin] = list(
                    zip(_get_type_vars(origin.__orig_bases__), args)
                )

            if args := orig_bases.get(mro_cls):
                typevar_to_value = {typevar: value for typevar, value in args}
            else:
                typevar_to_value = {}

            # we look for the method in the current class, if it is not defined, we move
            # to the next mro class, we do not want to use `getatter` here because it will
            # resolve for us attribute based on the inheritance
            if (
                mro_cls in self.__skip__
                or (method := mro_cls.__dict__.get(method_name, None)) is None
            ):
                continue

            should_continue = False
            signature = inspect.signature(method, eval_str=False)

            module = cast(ModuleType, inspect.getmodule(mro_cls))
            resolver = ForwardRefResolver(
                strategy=ForwardRefResolveByModuleStrategy(module)
            )

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

                annotation = parameter.annotation

                if is_forward_ref(annotation):
                    try:
                        annotation = resolver.resolve(parameter.annotation)
                    except ResolveForwardRefError:
                        pass

                if (
                    (not is_forward_ref(annotation))
                    and is_typevar(annotation)
                    and (real_annotation := typevar_to_value.get(annotation))
                ):
                    annotation = real_annotation

                parameters[name] = parameter = FactoryParameter(
                    annotation=annotation,
                    module=module,
                    kind=ParameterKind.POSITIONAL
                    if parameter.kind is parameter.POSITIONAL_ONLY
                    else ParameterKind.KEYWORD,
                )

            if not should_continue:
                break
        return FactoryParameters(parameters)


class FuncParameters:
    def get_parameters(self, func: Callable[..., Any]) -> FactoryParameters:
        parameters = FactoryParameters({})
        signature = inspect.signature(func)

        module = cast(ModuleType, inspect.getmodule(func))
        resolver = ForwardRefResolver(
            strategy=ForwardRefResolveByModuleStrategy(module)
        )

        for name, parameter in signature.parameters.items():
            match parameter.kind:
                case parameter.POSITIONAL_ONLY:
                    kind = ParameterKind.POSITIONAL
                case parameter.KEYWORD_ONLY | parameter.POSITIONAL_OR_KEYWORD:
                    kind = ParameterKind.KEYWORD
                case _:
                    continue

            annotation = parameter.annotation

            if is_forward_ref(annotation):
                try:
                    annotation = resolver.resolve(annotation)
                except ResolveForwardRefError:
                    pass

            parameters[name] = FactoryParameter(
                annotation=annotation,
                module=module,
                kind=kind,
            )
        return parameters


class Factory(Generic[T]):
    """
    a factory represent a type (Factory) that produces a different type (return type)
    the factory contains all the necessary information for the caller to call the
    factory implementation
    """

    def __init__(
        self,
        name: str,
        func_impl: Callable[..., T],
        parameters: FactoryParameters,
        return_type: type[T],
        module: ModuleType,
    ) -> None:
        self._name = name
        self._func = func_impl
        self._return_type = return_type
        self._parameters = parameters
        self._module = module

    @property
    def name(self) -> str:
        return self._name

    @property
    def parameters(self) -> FactoryParameters:
        return self._parameters

    @property
    def implementor_func(self) -> Callable[..., T]:
        return self._func

    @property
    def return_type(self) -> type[T]:
        return self._return_type

    @property
    def module(self) -> ModuleType:
        return self._module

    def set_parameter(self, name: str, parameter: FactoryParameter) -> None:
        self._parameters[name] = parameter

    def __call__(self, *args, **kwargs) -> T:
        return self._func(*args, **kwargs)


class FactoryBuilder:
    def __init__(self) -> None:
        self._name: str | None = None
        self._func_impl: Callable[..., Any] | None = None
        self._module: ModuleType | None = None
        self._parameters: FactoryParameters = FactoryParameters({})
        self._return_type: type | None = None

    def with_name(self, name: str) -> Self:
        self._name = name
        return self

    def with_func_impl(self, func: Callable[..., Any]) -> Self:
        self._func_impl = func
        return self

    def with_module(self, module: ModuleType) -> Self:
        self._module = module
        return self

    def with_parameters(self, parameters: FactoryParameters) -> Self:
        self._parameters = parameters
        return self

    def with_parameter(self, name: str, parameter: FactoryParameter) -> Self:
        self._parameters[name] = parameter
        return self

    def with_return_type(self, rt: type) -> Self:
        self._return_type = rt
        return self

    def build(self) -> Factory:
        assert self._name is not None
        assert self._func_impl is not None
        assert self._return_type is not None
        return Factory(
            name=self._name,
            parameters=self._parameters,
            func_impl=self._func_impl,
            module=self._module or cast(ModuleType, inspect.getmodule(self._func_impl)),
            return_type=self._return_type,
        )
