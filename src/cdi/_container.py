from __future__ import annotations
from typing import Hashable, ForwardRef

import threading
from types import ModuleType

from ._typing import is_forward_ref, is_typevar
from ._exceptions import ResolveForwardRefError
from ._fr_resolver import ForwardRefResolver, ForwardRefResolveByModuleStrategy
from ._factory import Factory, FactoryParameter, FactoryParameters, FactoryBuilder
from ._registry import Registry


__all__ = ("Container",)


def _is_partial_factory(factory: Factory) -> bool:
    if is_forward_ref(factory.return_type) or is_typevar(factory.return_type):
        return False

    for parameter in factory.parameters.values():
        if is_forward_ref(parameter.annotation) or is_typevar(parameter.annotation):
            return False
    return True


def _evaluate_partial_factory(factory: Factory) -> Factory:
    evaluated_parameters = FactoryParameters({})

    if is_forward_ref(factory.return_type):
        try:
            rt = ForwardRefResolver(
                strategy=ForwardRefResolveByModuleStrategy(factory.module)
            ).resolve(factory.return_type)
        except ResolveForwardRefError:
            raise ResolveForwardRefError(
                f"coudln't resolve forward reference for factory `{factory.name}` return type `{factory.return_type}`,"
                + f"`{factory.name}(...) -> {factory.return_type}`"
            )
    else:
        rt = factory.return_type

    for name, parameter in factory.parameters.items():
        if not isinstance(parameter.annotation, (ForwardRef, str)):
            evaluated_parameters[name] = parameter
            continue

        try:
            annotation = ForwardRefResolver(
                strategy=ForwardRefResolveByModuleStrategy(parameter.module)
            ).resolve(parameter.annotation)
        except ResolveForwardRefError:
            raise ResolveForwardRefError(
                f"coudln't resolve forward reference for factory `{factory.name}` parameter name `{name}`, `{factory.name}({name}: {type(parameter.annotation)}, ...)`"
            )

        evaluated_parameters[name] = FactoryParameter(
            annotation=annotation,
            kind=parameter.kind,
            module=parameter.module,
        )
    return (
        FactoryBuilder()
        .with_name(factory.name)
        .with_module(factory.module)
        .with_func_impl(factory.implementor_func)
        .with_parameters(evaluated_parameters)
        .with_return_type(rt)
        .build()
    )


def _factory_registry_key_impl(factory: Factory) -> Hashable:
    return factory.return_type


class Container:
    """
    container is a box that can store given factories of types but cannot create
    instances, container can be thought as a type factory for a `Scope`, if a scope need to create
    a type, it fetches the registered factory for the required type and uses
    that factory to create the type

    THREAD SAFETY:
        containers are thread safe, they can be used in multiple different places that use
        threading, for example, multiple scopes that run on different threads
    """

    def __init__(self) -> None:
        self._factory: Registry[Factory] = Registry(_factory_registry_key_impl)
        self._partially_initialized: list[Factory] = []
        self._lock = threading.Lock()

    def register(self, factory: Factory) -> None:
        """
        registers the given factory with the scope, the factory return type
        will be used as key when calling the container `get_factory` and providing a type
        """
        is_partial = _is_partial_factory(factory)
        with self._lock:
            if is_partial:
                self._factory.add(factory)
            else:
                self._partially_initialized.append(factory)

    def update_forward_ref(self, module: ModuleType) -> None:
        with self._lock:
            self._update_forward_ref(module)

    def _update_forward_ref(self, module: ModuleType) -> None:
        partially_initialized = []

        for factory in self._partially_initialized:
            if factory.module is module:
                self._factory.add(_evaluate_partial_factory(factory))
            else:
                partially_initialized.append(factory)
        self._partially_initialized = partially_initialized

    def _get_factory(self, type_: type) -> Factory | None:
        """
        returns the correct factory for the requested type
        """
        with self._lock:
            return self._factory.get(type_)
