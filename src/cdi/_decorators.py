from __future__ import annotations

import inspect
from types import ModuleType
from typing import TYPE_CHECKING, TypeVar, Any, cast
from collections.abc import Callable

from ._fr_resolver import ForwardRefResolver, ForwardRefResolveByModuleStrategy
from ._exceptions import ResolveForwardRefError
from ._factory import MroParameters, FuncParameters, FactoryBuilder
from ._typing import is_forward_ref

if TYPE_CHECKING:
    from ._container import Container


__all__ = ("Injectable",)


T = TypeVar("T")


class Injectable:
    """
    responsible for creating factories from given types to inject
    into the bounded container

    the class can be used as standalone or as a decorator
    ```py
    ctr = cdi.Container()

    @cdi.Injectable(ctr)
    class Foo:
        def __init__(self, name: str) -> None: ...
    ```

    to read more about how the Injectable behaves for different data types
    look at `cdi.Injectable.register`
    """

    def __init__(self, __ctr: Container, /) -> None:
        self._ctr = __ctr

    @property
    def container(self) -> Container:
        """returns the container the injector is bounded to"""
        return self._ctr

    def register(self, injectable: T) -> None:
        """
        registers the given type into the provided container, an internal factory
        will be generated based on the given type

        ### Constant values
        when registering an instance (value) and not a class or a function, a wrapper factory
        will be built for that instance, calling the factory will always yield the same instance

        in a way it is like creating a global instances for a container that any scope
        will have access to

        ```py
        ctr = cdi.Container()

        class Foo:
            pass

        instance = Foo()
        cdi.Injectable(ctr).register(instance)

        scope1 = cdi.Scope(__name__ + "1", container=ctr)
        scope2 = cdi.Scope(__name__ + "2", container=ctr)

        # both share the same `instance` of `Foo`
        assert scope1.get_instance(Foo) is scope2.get_instance(Foo)
        ```

        ### Classes
        when injecting a class, the parameters will be fetched from the class `__init__`
        and on instanciation time, the correct type will be injected based on the type hint,
        the factory implementation will call the class `__call__` method

        inheritance is supported, including `*args, **kwargs` in your `__init__` class will cause
        the injector to move up the parent classes with respect to the `MRO` and evaluate the parent
        parameters too

        ```py
        ctr = cdi.Container()

        class Parent:
            def __init__(self, parent_field: int) -> None: ...

        class Child(Parent):
            def __init__(self, child_field: int, *args, **kwargs) -> None: ...

        # register int so it will be injected to `parent_field` and `child_field`
        cdi.Injectable(ctr).register(100)

        # the instance is able to be created without error, `parent_field` and `child_field`
        # are required fields, and they will be injected
        cdi.Scope(__name__, container=ctr).get_instance(Child)
        ```

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
