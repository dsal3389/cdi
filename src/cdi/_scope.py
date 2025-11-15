from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Annotated, Any, TypeVar, get_args, get_origin

from ._exceptions import CircularDependencyError, NoProviderError
from ._types import Lazy
from ._typing import (
    get_generics,
    get_typevar_mapping,
    is_fixture_annotation,
    is_typealias,
)

if TYPE_CHECKING:
    from ._container import Container


class _InstanceContext:
    def __init__(
        self, typeargs: dict[TypeVar, Any], typevars_mapping: dict[TypeVar, Any]
    ) -> None:
        self._typeargs = typeargs
        self._typevars_mapping = typevars_mapping

    def resolve_typevar(self, typevar: TypeVar) -> Any:
        resolved = typevar
        if resolved in self._typevars_mapping:
            resolved = self._typevars_mapping[typevar]
        if resolved in self._typeargs:
            return self._typeargs[resolved]
        return resolved

    def resolve_typealias(self, type_: Any) -> Any:
        """
        takes a typealias and evalute the typealias typevars to their real types
        based on the context
        """
        origin = get_origin(type_)
        typeargs = []

        for arg in get_args(type_):
            if isinstance(arg, TypeVar):
                typeargs.append(self.resolve_typevar(arg))
            else:
                typeargs.append(arg)
        return origin[*typeargs]


class Scope:
    """
    the scope defines the life time of objects and it is bound to a single container where
    the container provide the supported types for the scope and type resolution
    """

    def __init__(self, container: Container, name: str | None = None) -> None:
        self._container = container
        self._instances = {}
        self._name = name
        self._lock = threading.Lock()

        # prevent circular dependency
        self._stack = []

    def get_instance(self, type_: Any, *, _cx: _InstanceContext | None = None) -> Any:
        with self._lock:
            return self._get_instance(type_, cx=_cx)

    def _get_instance(self, type_: Any, *, cx: _InstanceContext | None) -> Any:
        origin = get_origin(type_)

        if cx is not None:
            if isinstance(type_, TypeVar):
                type_ = cx.resolve_typevar(type_)
            elif is_typealias(type_):
                type_ = cx.resolve_typealias(type_)

        if origin is not None:
            if origin is Lazy:
                lazy_type = get_args(type_)[0]
                return Lazy(scope=self, type_=lazy_type, cx=cx)

            if origin is Annotated:
                anno_type, *_ = get_args(type_)

                if is_fixture_annotation(type_):
                    return self._get_fixture(anno_type, cx=cx)
                else:
                    return self._get_factory(anno_type, cx=cx)
        return self._get_factory(type_, cx=None)

    def _get_factory(self, type_: Any, *, cx: _InstanceContext | None) -> Any:
        if type_ in self._instances:
            return self._instances[type_]

        if type_ in self._stack:
            raise CircularDependencyError(tuple(self._stack))

        self._stack.append(type_)

        instance = self._get_fixture(type_, cx=cx)

        self._instances[type_] = instance
        self._stack.pop()

        return instance

    def _get_fixture(self, type_: type[Any], *, cx: _InstanceContext | None) -> Any:
        if (provider := self._container.get_provider(type_)) is None:
            raise NoProviderError(f"not provider found for required type `{type_}`")

        args = []
        kwargs = {}

        if cx is None:
            cx = _InstanceContext(
                typeargs={g: v for g, v in zip(get_generics(type_), get_args(type_))},
                typevars_mapping=provider.typevar_mapping,
            )

        for tt in provider.args:
            args.append(self._get_instance(tt, cx=cx))

        for name, tt in provider.kwargs.items():
            kwargs[name] = self._get_instance(tt, cx=cx)

        return provider(*args, **kwargs)
