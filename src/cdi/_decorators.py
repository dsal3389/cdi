from collections.abc import Callable

import inspect
from types import ModuleType
from typing import TypeVar, Any, cast

from cdi._typing import is_forward_ref

from ._container import Container
from ._evaluator import TypeModuleEvaluator
from ._exceptions import TypeEvaluationError
from ._factory import MroParameters, FuncParameters, FactoryBuilder


__all__ = ("Injectable",)


T = TypeVar("T")


class Injectable:
    def __init__(self, ctr: Container) -> None:
        self._ctr = ctr

    def __call__(self, injectable: T) -> T:
        if inspect.isfunction(injectable):
            self._inject_func_factory(injectable)
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

    def _inject_func_factory(self, func: Callable[..., Any]) -> None:
        parameters = FuncParameters().get_parameters(func)
        module = cast(ModuleType, inspect.getmodule(func))
        rt = inspect.signature(func).return_annotation

        if is_forward_ref(rt):
            try:
                rt = TypeModuleEvaluator(module).evaluate(rt)
            except TypeEvaluationError:
                pass

        factory = (
            FactoryBuilder()
                .with_module(module)
                .with_parameters(parameters)
                .with_func_impl(func)
                .with_return_type(rt)
                .build()
        )
        self._ctr.register(factory)
