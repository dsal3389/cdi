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

        self._stack: list[type] = []
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
        return self._get_instance(type_, evaluate=True)

    def _get_instance(self, type_: Any, evaluate: bool) -> Any:
        for type_ in _unwrap_union(type_):
            try:
                scope = self
                origin = get_origin(type_)

                if origin is not None:
                    if origin is Annotated:
                        # we look for the relevant metadata and also update the real
                        # value of the annontated type
                        type_, metadata = _get_annotated_injectable_metadata(type_)
                        origin = get_origin(type_)  # update the origin type

                        if metadata:
                            evaluate = metadata._evaluate
                            if metadata._provider_scope is not None:
                                scope = metadata._provider_scope(self)
                        # if the type was wrapped with `Annotated` we want to
                        # call `_get_instance` to instantiate the real type
                        return scope._get_instance(type_, evaluate=evaluate)
                return scope._get_unwrapped_type(type_, evaluate=evaluate)
            except (NoFactoryForTypeError, TypeEvaluationError):
                pass
        raise TypeEvaluationError(
            f"{self} failed to evaluate type `{type_}`"
        )

    def _get_unwrapped_type(self, type_: type, evaluate: bool) -> Any:
        if type_ is NoneType:
            return None

        with self._lock:
            if instance := self._instances.get(type_):
                return instance

            if not evaluate:
                raise TypeEvaluationError(
                    f"{self} couldn't find existing instance for `{type_.__name__}` and couldn't evaluate the type"
                )

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
                        f"{self} incorrect scope stack popping for {self}, expected `{type_.__name__}`, popped `{popped.__name__}`"
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
