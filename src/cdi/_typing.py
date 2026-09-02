from __future__ import annotations

import itertools
from collections.abc import Sequence, Iterable, Callable

from types import GenericAlias, UnionType
from typing import (
    TYPE_CHECKING,
    TypeVar,
    Generic,
    ForwardRef,
    Any,
    Annotated,
    Union,
    get_origin,
    get_args,
)

if TYPE_CHECKING:
    from ._scope import Scope


__all__ = ("is_typevar", "is_generic_alias", "is_forward_ref", "InjectableMetadata")


_miss = object()


def _resolve_type_generics(type_: GenericAlias, typevars: dict[TypeVar, Any]) -> GenericAlias:
    origin = get_origin(type_)
    resolved_args = []

    for arg in get_args(type_):
        resolved_args.append(typevars.get(arg, arg))
    return GenericAlias(origin, tuple(resolved_args))


def _get_typevars(orig_bases: Sequence[type | GenericAlias]) -> tuple[TypeVar, ...]:
    for orig_base in orig_bases:
        if get_origin(orig_base) is Generic:
            return get_args(orig_base)
    return ()


def _get_typevar_mapping(typealias: GenericAlias) -> dict[TypeVar, Any]:
    mapping = {}

    if origin := get_origin(typealias):
        for typevar, value in zip(
            _get_typevars(origin.__orig_bases__), get_args(typealias)  # type: ignore
        ):
            mapping[typevar] = value
    return mapping


def _as_forward_ref(v: ForwardRef | str) -> ForwardRef:
    if not isinstance(v, ForwardRef):
        return ForwardRef(v)
    return v


def _unwrap_union(type_: Any) -> Iterable[Any]:
    if is_union(type_):
        yield from itertools.chain.from_iterable(
            map(_unwrap_union, get_args(type_))
        )
    else:
        yield type_


def _get_annotated_injectable_metadata(
    annotated: Annotated[Any, ...],
) -> tuple[type, InjectableMetadata | None]:
    type_, *args = get_args(annotated)
    for arg in args:
        if isinstance(arg, InjectableMetadata):
            return (type_, arg)
    return (type, None)


def is_union(value: Any) -> bool:
    return get_origin(value) in (UnionType, Union)


def is_forward_ref(value: Any) -> bool:
    return isinstance(value, (str, ForwardRef))


def is_typevar(value: Any) -> bool:
    return isinstance(value, TypeVar)


def is_generic_alias(value: Any) -> bool:
    return get_origin(value) is not None


class InjectableMetadata:
    def __init__(
        self,
        *,
        transient: bool = False,
        provider_scope: Callable[[Scope], Scope] | None = None,
        error_message: str | None = None
    ) -> None:
        self._transient = transient
        self._provider_scope = provider_scope
        self._error_message = error_message

    def merge(self, other: InjectableMetadata) -> InjectableMetadata:
        """
        merges data from `other` into `self`, wherever `self` has a falsy value, the value will
        be taken from the given `other`
        """
        return InjectableMetadata(
            transient=self._transient or other._transient,
            provider_scope=self._provider_scope or other._provider_scope,
            error_message=self._error_message or other._error_message,
        )

    def __repr__(self) -> str:
        return (
            "InjectableMetadata("
            f"transient={self._transient}, "
            f"provider_scope={self._provider_scope}, "
            f"error_message={self._error_message}, "
            ")"
        )
