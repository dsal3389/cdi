import inspect
from typing import TypeVar

from ._container import Container
from ._factory import Factory, FactoryParametersFromMro


__all__ = (
    "Injectable",
)


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
        parameters = FactoryParametersFromMro().get_parameters(
            inspect.getmro(cls),
            "__init__"
        )
        factory = Factory(
            parameters=parameters,
            func_impl=getattr(cls, "__call__"),
            return_type=cls,
        )
        self._ctr.register(factory)
