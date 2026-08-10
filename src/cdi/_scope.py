import threading
from typing import Any

from ._container import Container
from ._factory import Factory, ParameterKind
from ._registry import Registry


class Scope:
    def __init__(
        self,
        container: Container
    ) -> None:
        self._container = container
        self._instances = Registry(type)

        self._stack = []
        self._lock = threading.Lock()

    def get_instance(self, type_: type) -> Any:
        with self._lock:
            return self._get_instance(type_)

    def _get_instance(self, type_: type) -> Any:
        if instance := self._instances.get(type_):
            return instance

        self._stack.append(type_)

        try:
            if (factory := self._container.get_factory(type_)):
                instance = self._instantiate_from_factory(factory)
                self._instances.add(instance)
            else:
                instance = None
        finally:
            assert self._stack.pop() is type_
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
