from __future__ import annotations

import copy
import threading
from collections import deque
from types import NoneType, GenericAlias
from typing import Any, Annotated, TypeVar, get_origin, get_args, cast
from typing_extensions import TypeAliasType

from ._container import Container
from ._factory import Factory, ParameterKind
from ._exceptions import (
    IncorrectStackPopping,
    CircularDependencyError,
    NoFactoryForTypeError,
    TypeEvaluationError,
)
from ._tree import PrefixTree, PrefixTreeTypeFindStrategy, type_as_prefix_steps
from ._typing import (
    _unwrap_union,
    _get_annotated_injectable_metadata,
    _resolve_type_generics,
    _get_typevar_mapping,
    is_generic_alias,
    is_union,
    InjectableMetadata,
)


class Scope:
    def __init__(
        self, __name: str, /, *, container: Container, parent: Scope | None = None
    ) -> None:
        self._name = __name
        self._parent = parent
        self._container = container
        self._instances = PrefixTree(find_strategy=PrefixTreeTypeFindStrategy())

        self._stack: list[type] = []
        self._lock = threading.RLock()

    @property
    def name(self) -> str:
        return self._name

    @property
    def parent(self) -> Scope | None:
        """returns the parent of the scope if any"""
        return self._parent

    def fork(self, name: str | None = None) -> Scope:
        """
        forks the scope, creating a sub scope that has the same container
        as the current scope, and set the current scope as the parent
        """
        return Scope(
            name or (self.name + "-fork"), container=self._container, parent=self
        )

    def get_instance(self, type_: Any) -> Any:
        """
        returns an instance of the given type, assuming some factory
        is registered at the container level that can create the type
        """
        return self._get_instance(type_, typevars={})

    def insert_instance(self, instance: Any) -> None:
        """
        inserts the live instance into the scope, mapping between the instance
        type to the instance itself
        """
        prefix = type_as_prefix_steps(type(instance))
        with self._lock:
            self._instances.insert(prefix, instance)

    def _get_instance(
        self,
        type_: Any,
        typevars: dict[TypeVar, Any],
    ) -> Any:
        """
        responsible to take any possible type and unwrap it to the real
        value to check annotations metadata before evaluation

        type evaluation should not be here, but prepare the type
        for the next step
        """
        exceptions = []

        # deque is used to prevent extra stack calls if the `type_` is a
        # union or annotated, the stack calls can add up for deep injections
        # with a lot of unions
        types_: deque[tuple[Any, InjectableMetadata]] = deque()
        types_.append((type_, InjectableMetadata()))

        while types_:
            type_, metadata = types_.popleft()
            origin = get_origin(type_)

            if origin is not None:
                if typevars:
                    # if we are in a typealias and we have typevars forwarded
                    # we should try to resolve possible generics in the current
                    # `type_` if any, to their real value
                    type_ = _resolve_type_generics(type_, typevars)
                if is_union(type_):
                    types_.extendleft((t, metadata) for t in _unwrap_union(type_))
                    continue
                if origin is Annotated:
                    # we look for the relevant metadata and also update the real
                    # value of the annontated type
                    type_, annotated_metadata = _get_annotated_injectable_metadata(type_)
                    types_.appendleft((type_, annotated_metadata or metadata))
                    continue

            scope = self
            custom_error_message = None

            try:
                if metadata._error_message:
                    custom_error_message = metadata._error_message
                if metadata._provider_scope is not None:
                    scope = metadata._provider_scope(self)

                    if scope is not self:
                        # if we need to call a different scope to evaluate the
                        # type, we don't want the provider scope to call `_provider_scope`
                        # the results can be unexpected
                        metadata_copy = copy.copy(metadata)
                        metadata_copy._provider_scope = None

                        # if the type was wrapped with `Annotated` we want to
                        # call `_get_instance` to instantiate the real type
                        return scope._get_instance(
                            Annotated[type_, metadata_copy],
                            typevars=typevars
                        )
                return scope._get_unwrapped_type(type_, typevars=typevars)
            except NoFactoryForTypeError as e:
                exceptions.append(TypeEvaluationError(
                    f"{self} failed to evaluate type `{type_.__name__}` due to error: " + str(e) + "\n" + (custom_error_message or "")
                ))

        error_message = f"{self} failed to evaluate type {type_} due to errors:\n" + "\n - ".join(map(str, exceptions))
        raise TypeEvaluationError(error_message)

    def _get_unwrapped_type(self, type_: type | GenericAlias | TypeAliasType, typevars: dict[TypeVar, Any]) -> Any:
        if type_ is NoneType:
            return None

        if is_generic_alias(type_):
            type_ = cast(GenericAlias, type_)
            origin = get_origin(type_)

            if origin is type:
                arg = get_args(type_)[0]
                return typevars.get(arg, arg)

        with self._lock:
            tree_prefix = type_as_prefix_steps(type_)
            if instance := self._instances.find(tree_prefix):
                return instance

            if type_ in self._stack:
                raise CircularDependencyError(tuple(self._stack), type_)

            self._stack.append(type_)

            try:
                if not (factory := self._container._get_factory(type_)):
                    raise NoFactoryForTypeError(tuple(self._stack), type_)

                if is_generic_alias(type_):
                    typevars = _get_typevar_mapping(type_)  # type: ignore
                else:
                    typevars = {}

                instance = self._instantiate_from_factory(factory, typevars)
                self._instances.insert(tree_prefix, instance)
                return instance
            finally:
                popped = self._stack.pop()
                if popped is not type_:
                    raise IncorrectStackPopping(
                        f"{self} incorrect scope stack popping for {self}, expected `{type_.__name__}`, popped `{popped.__name__}`"
                    )

    def _instantiate_from_factory(
        self, factory: Factory, typevars: dict[TypeVar, Any]
    ) -> Any:
        positional_arguments = []
        keyword_arguments = {}

        for name, parameter in factory.parameters.items():
            annotation = typevars.get(parameter.annotation, parameter.annotation)
            value = self._get_instance(annotation, typevars=typevars)

            match parameter.kind:
                case ParameterKind.POSITIONAL:
                    positional_arguments.append(value)
                case ParameterKind.KEYWORD:
                    keyword_arguments[name] = value
        return factory(*positional_arguments, **keyword_arguments)

    def __str__(self) -> str:
        return f"Scope<{self.name}>"
