from __future__ import annotations

import threading
from typing import Any, get_origin, Annotated, get_args
from types import NoneType

from ._container import Container
from ._factory import Factory, ParameterKind
from ._exceptions import (
    IncorrectStackPopping,
    CircularDependencyError,
    NoFactoryForTypeError,
    TypeEvaluationError,
)
from ._registry import Registry
from ._typing import _unwrap_union, _get_annotated_injectable_metadata


class Scope:
    def __init__(
        self, name: str, *, container: Container, parent: Scope | None = None
    ) -> None:
        self._name = name
        self._parent = parent
        self._container = container
        self._instances = Registry(type)

        self._stack = []
        self._lock = threading.RLock()

    @property
    def name(self) -> str:
        return self._name

    @property
    def parent(self) -> Scope | None:
        return self._parent

    def fork(self, name: str | None = None) -> Scope:
        return Scope(
            name=name or (self.name + "-fork"), container=self._container, parent=self
        )

    def get_instance(self, type_: Any) -> Any:
        exceptions = []
        for type_ in _unwrap_union(type_):
            if get_origin(type_) is Annotated:
                metadata = _get_annotated_injectable_metadata(type_)
                type_, *_ = get_args(type_)

                if metadata:
                    if metadata._provider_scope is not None:
                        provider_scope = metadata._provider_scope(self)

                        if provider_scope is not self:
                            return provider_scope.get_instance(type_)
                return self.get_instance(type_)
            else:
                try:
                    return self._get_unwrapped_type(type_)
                except NoFactoryForTypeError as e:
                    exceptions.append(e)
        raise TypeEvaluationError(
            f"failed to evaluate type `{type_}` with exceptions:"
            + "\n  "
            + "\n  ".join(map(str, exceptions))
        )

    def _get_unwrapped_type(self, type_: type) -> Any:
        if type_ is NoneType:
            return None

        with self._lock:
            if instance := self._instances.get(type_):
                return instance

            if type_ in self._stack:
                raise CircularDependencyError(tuple(self._stack), type_)

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
            value = self.get_instance(parameter.annotation)

            match parameter.kind:
                case ParameterKind.POSITIONAL:
                    positional_arguments.append(value)
                case ParameterKind.KEYWORD:
                    keyword_arguments[name] = value
        return factory(*positional_arguments, **keyword_arguments)

    def __str__(self) -> str:
        return f"Scope<{self.name}>"
