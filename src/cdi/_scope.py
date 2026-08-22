import threading
from typing import Any

from ._container import Container
from ._factory import Factory, ParameterKind
from ._exceptions import IncorrectStackPopping, CircularDependencyError, NoFactoryForTypeError
from ._registry import Registry


class Scope:
    def __init__(self, name: str, *, container: Container) -> None:
        self._name = name
        self._container = container
        self._instances = Registry(type)

        self._stack = []
        self._lock = threading.Lock()

    @property
    def name(self) -> str:
        return self._name

    def get_instance(self, type_: type) -> Any:
        with self._lock:
            return self._get_instance(type_)

    def _get_instance(self, type_: type) -> Any:
        if instance := self._instances.get(type_):
            return instance

        if type_ in self._stack:
            raise CircularDependencyError(
                tuple(self._stack), type_
            )

        self._stack.append(type_)

        try:
            if factory := self._container._get_factory(type_):
                instance = self._instantiate_from_factory(factory)
                self._instances.add(instance)
            else:
                raise NoFactoryForTypeError(tuple(self._stack), type_)
        finally:
            popped = self._stack.pop()
            if popped is not type_:
                raise IncorrectStackPopping(
                    f"incorrect scope stack popping for {self}, expected `{type_.__name__}`, popped `{popped.__name__}`"
                )
        return instance

    def _instantiate_from_factory(self, factory: Factory) -> Any:
        positional_arguments = []
        keyword_arguments = {}

        for name, parameter in factory.parameters.items():
            value = self._get_instance(parameter.annotation)

            match parameter.kind:
                case ParameterKind.POSITIONAL:
                    positional_arguments.append(value)
                case ParameterKind.KEYWORD:
                    keyword_arguments[name] = value
        return factory(*positional_arguments, **keyword_arguments)

    def __str__(self) -> str:
        return f"Scope<{self.name}>"
