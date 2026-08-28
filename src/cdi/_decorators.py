from collections.abc import Callable

import inspect
from types import ModuleType
from typing import TypeVar, Any, cast

from ._container import Container
from ._fr_resolver import ForwardRefResolver, ForwardRefResolveByModuleStrategy
from ._exceptions import ResolveForwardRefError
from ._factory import MroParameters, FuncParameters, FactoryBuilder
from ._typing import is_forward_ref


__all__ = ("Injectable",)


T = TypeVar("T")


class Injectable:
    """
    responsible for creating factories from given types to inject
    into the given container, mostly used as decorator, on a class or a function

    the factory parameters will be generated based on the function parameters, or if used
    on class, it will be based on the `__init__` parameters

    ```py
    ctr = cdi.Container()
    Inject = cdi.Injectable(ctr=ctr)

    @Inject
    class Foo:
        def __init__(self, name: str) -> None:
            pass
    ```
    """

    def __init__(self, __ctr: Container, /) -> None:
        self._ctr = __ctr

    @property
    def container(self) -> Container:
        return self._ctr

    def register(self, injectable: T) -> None:
        """
        registers the given injectable into the provided container, based on the given type
        a correct factory will be registered in the container

        CONSTANTS:
            when a constant value will be provided, a factory that provide
            the constant will be created, evaluations for the constant type will evaluate to that factory
            which will return the same given instance, acting as a "global variable" for a container

        CLASSES:
            when a class is provided, the factory signature will be fetched from the class `__init__`
            and the factory implementation will call the class `__call__`, the factory return type
            will assume the given class

        FUNCTIONS:
            parameters and return type are calculated based on the function signature
        """
        if inspect.isfunction(injectable):
            self._inject_func_factory(injectable)
        elif inspect.isclass(injectable):
            self._inject_class_factory(injectable)
        else:
            self._inject_constant(injectable)

    def __call__(self, injectable: T) -> T:
        self.register(injectable)
        return injectable

    def _inject_class_factory(self, cls: type) -> None:
        parameters = MroParameters().get_parameters(inspect.getmro(cls), "__init__")
        self._ctr._register(
            FactoryBuilder()
            .with_name(f"{cls.__name__}.__init__")
            .with_func_impl(getattr(cls, "__call__"))
            .with_module(cast(ModuleType, inspect.getmodule(cls)))
            .with_parameters(parameters)
            .with_return_type(cls)
            .build()
        )

    def _inject_func_factory(self, func: Callable[..., Any]) -> None:
        parameters = FuncParameters().get_parameters(func)
        module = cast(ModuleType, inspect.getmodule(func))
        rt = inspect.signature(func).return_annotation

        if is_forward_ref(rt):
            try:
                rt = ForwardRefResolver(
                    strategy=ForwardRefResolveByModuleStrategy(module)
                ).resolve(rt)
            except ResolveForwardRefError:
                pass

        self._ctr._register(
            FactoryBuilder()
            .with_name(func.__name__)  # type: ignore
            .with_module(module)
            .with_parameters(parameters)
            .with_func_impl(func)
            .with_return_type(rt)
            .build()
        )

    def _inject_constant(self, constant: Any) -> None:
        self._ctr._register(
            FactoryBuilder()
            .with_name(str(constant))
            .with_func_impl(lambda: constant)
            .with_return_type(type(constant))
            .with_module(cast(ModuleType, inspect.getmodule(constant)))
            .build()
        )
