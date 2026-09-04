from __future__ import annotations

import copy
import threading
from collections import deque
from types import NoneType, GenericAlias
from typing import Any, Annotated, TypeVar, get_origin, get_args, cast
from typing_extensions import TypeForm, TypeAliasType

from ._container import Container
from ._factory import Factory, ParameterKind
from ._exceptions import (
    IncorrectStackPopping,
    CircularDependencyError,
    NoFactoryForTypeError,
    TypeEvaluationError,
)
from .policy import NoFactoryPolicy, ErrorNoFactoryPolicy
from ._tree import PrefixTree, PrefixTreeTypeFindStrategy, type_as_prefix_steps
from ._typing import (
    _miss,
    _unwrap_union,
    _get_annotated_injectable_metadata,
    _resolve_type_generics,
    _get_typevar_mapping,
    is_generic_alias,
    is_union,
    InjectableMetadata,
)


_T = TypeVar("_T")


class Scope:
    """
    hold the live instances, different scope do not share instances
    between them unless explicitly annotated via `cdi.InjectableMetadata(provider_scope=...)`

    live instances can be inserted into the scope more about it look at `Scope.insert_instance`,
    the scope cannot manipulate the bounded container in any way

    scopes can inherit from different scopes, aquiring those roles do not effect the scope
    behavior, it is more for conviniance when using `cdi.InjectableMetadata(provider_scope=...)`

    the scope name is mostly for easier debugging and clearer errors

    ## evaluation
    the scope uses the given `Container` to look up for factories that can produce the desired type
    if the container has no such type the type evaluation will be moved to the provided `no_factory_policy`
    that is called when a type has no factory and continue the evaluation from there

    by default the policy is `cdi.policy.ErrorNoFactoryPolicy()`

    ## thread safety
    scope is threadsafe, for every instance an internal lock is aquired preventing
    2 threads evaluating at the same time

    if the evaluation requires the parent, and no evaluation operation is required on the child scope
    then the child scope lock will not be acquired
    """

    def __init__(
        self, __name: str, /, *, container: Container, parent: Scope | None = None,
        no_factory_policy: NoFactoryPolicy | None = None
    ) -> None:
        self._name = __name
        self._parent = parent
        self._container = container
        self._instances: PrefixTree[type, Any] = PrefixTree(
            find_strategy=PrefixTreeTypeFindStrategy()
        )
        self._no_factory_policy = no_factory_policy or ErrorNoFactoryPolicy()

        self._stack: list[type] = []
        self._lock = threading.RLock()
        self._setup()

    @property
    def name(self) -> str:
        return self._name

    @property
    def container(self) -> Container:
        return self._container

    @property
    def parent(self) -> Scope | None:
        """returns the parent of the scope if any"""
        return self._parent

    def fork(self, __name: str | None = None, /) -> Scope:
        """
        forks the scope, creating a sub scope that has the same container
        as the current scope, and set the current scope as the parent
        """
        return Scope(
            __name or (self.name + "-fork"), container=self._container, parent=self
        )

    def has_instance(self, __type: Any, /) -> bool:
        """
        returns a boolean value indicating if the scope has a live
        instance of the given type

        it doesn't check if the scope can create such type, for possibility
        of type creation refer to the scope `cdi.Container` from `scope.container`
        """
        prefix = type_as_prefix_steps(__type)
        with self._lock:
            return self._instances.find(prefix) is not None

    def get_instance(self, __type: TypeForm[_T], /) -> _T:
        """
        returns an instance of the given type, assuming some factory
        is registered at the container level that can create the type
        """
        return self._get_instance_impl(__type, typevars={})

    def insert_instance(self, __instance: Any, /) -> None:
        """
        inserts the live instance into the scope, mapping between the instance
        type to the instance itself

        ```py
        my_obj = object()

        scope = cdi.Scope(...)
        scope.insert_instance(100)
        scope.insert_instance(my_obj)

        assert scope.get_instance(int) is 100
        assert scope.get_instance(object) is my_obj
        ```
        """
        prefix = type_as_prefix_steps(type(__instance))
        with self._lock:
            self._instances.insert(prefix, __instance)

    def _get_instance_impl(
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
                    inner, annotated_metadata = _get_annotated_injectable_metadata(
                        type_
                    )
                    types_.appendleft(
                        (
                            inner,
                            # try to merge previous metadata with the annotated metadata
                            # but we give more priority to the annotation truthy values
                            annotated_metadata.merge(metadata)
                            if annotated_metadata
                            else metadata,
                        )
                    )
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
                        return scope._get_instance_impl(
                            Annotated[type_, metadata_copy],  # type: ignore
                            typevars=typevars,
                        )

                dry_instance = self._get_dry_type(type_)
                if dry_instance is not _miss:
                    return dry_instance
                elif metadata._transient:
                    return scope._create_instance(type_)
                else:
                    return scope._get_unwrapped_type(type_)
            except NoFactoryForTypeError as e:
                exception = TypeEvaluationError(
                    f"{self} failed to evaluate type `{type_.__name__}` due to error: "
                    + str(e)
                    + "\n"
                    + (custom_error_message or "")
                )

                if not types_:
                    raise exception
                exceptions.append(exception)

        error_message = (
            f"{self} failed to evaluate type {type_} due to errors:\n"
            + "\n - ".join(map(str, exceptions))
        )
        raise TypeEvaluationError(error_message)

    def _get_unwrapped_type(self, type_: Any) -> Any:
        with self._lock:
            tree_prefix = type_as_prefix_steps(type_)
            if instance := self._instances.find(tree_prefix):
                return instance

            if type_ in self._stack:
                raise CircularDependencyError(tuple(self._stack), type_)

            # TODO: I am pretty sure there is a bug with generic aliases
            # types since each generic alias is a different instance so in `in` operation will be falsy
            # check in future
            self._stack.append(type_)

            try:
                instance = self._create_instance(type_)
                self._instances.insert(tree_prefix, instance)
                return instance
            finally:
                popped = self._stack.pop()
                if popped is not type_:
                    raise IncorrectStackPopping(
                        f"{self} incorrect scope stack popping for {self}, expected `{type_.__name__}`, popped `{popped.__name__}`"
                    )

    def _get_dry_type(self, type_: Any) -> Any:
        """
        the term "dry" here means that the type doesn't require touching
        the `self` (scope) instances, so no locking is required
        or getting anything from the scope

        this method can be `staticmethod` for all I care, but it is better
        keeping it here
        """
        if type_ is NoneType:
            return None

        if is_generic_alias(type_):
            type_ = cast(GenericAlias, type_)
            origin = get_origin(type_)

            if origin is type:
                return get_args(type_)[0]
        return _miss

    def _create_instance(self, type_: Any) -> Any:
        if factory := self._container._get_factory(type_):
            return self._instantiate_from_factory(factory, _get_typevar_mapping(type_))

        try:
            return self._no_factory_policy.handle(self, type_)
        except Exception as e:
            raise NoFactoryForTypeError(tuple(self._stack), type_) from e

    def _instantiate_from_factory(
        self, factory: Factory, typevars: dict[TypeVar, Any]
    ) -> Any:
        positional_arguments = []
        keyword_arguments = {}

        for name, parameter in factory.parameters.items():
            annotation = typevars.get(parameter.annotation, parameter.annotation)
            value = self._get_instance_impl(annotation, typevars=typevars)

            match parameter.kind:
                case ParameterKind.POSITIONAL:
                    positional_arguments.append(value)
                case ParameterKind.KEYWORD:
                    keyword_arguments[name] = value
        return factory(*positional_arguments, **keyword_arguments)

    def _setup(self) -> None:
        self.insert_instance(self)

    def __str__(self) -> str:
        return f"Scope<{self.name}>"
