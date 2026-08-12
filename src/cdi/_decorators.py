import inspect
from types import ModuleType
from typing import TypeVar, cast

from ._container import Container
from ._factory import MroParameters, FactoryBuilder


__all__ = ("Injectable",)


T = TypeVar("T")


class Injectable:
    def __init__(self, ctr: Container) -> None:
        self._ctr = ctr

    def __call__(self, injectable: T) -> T:
        if inspect.isfunction(injectable):
            if "." in injectable.__qualname__:
                class_name, method_name = injectable.__qualname__.split(".")
            raise NotImplementedError
        elif inspect.isclass(injectable):
            self._inject_class_factory(injectable)
        return injectable

    def _inject_class_factory(self, cls: type) -> None:
        parameters = MroParameters().get_parameters(inspect.getmro(cls), "__init__")
        factory = (
            FactoryBuilder()
            .with_name(f"{cls.__name__}.__init__")
            .with_func_impl(getattr(cls, "__call__"))
            .with_module(cast(ModuleType, inspect.getmodule(cls)))
            .with_parameters(parameters)
            .with_return_type(cls)
            .build()
        )
        self._ctr.register(factory)
