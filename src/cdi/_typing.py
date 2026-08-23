import itertools
from collections.abc import Sequence, Iterable

from types import GenericAlias, UnionType
from typing import TypeVar, Generic, ForwardRef, Any, get_origin, get_args, cast

__all__ = (
    "is_typevar",
    "is_forward_ref",
    "evaluate_forward_ref",
)


def _get_type_vars(orig_bases: Sequence[type | GenericAlias]) -> tuple[TypeVar, ...]:
    for orig_base in orig_bases:
        if get_origin(orig_base) is Generic:
            return get_args(orig_base)
    return ()


def _as_forward_ref(v: ForwardRef | str) -> ForwardRef:
    if not isinstance(v, ForwardRef):
        return ForwardRef(v)
    return v


def _unwrap_union(type_: Any) -> Iterable[Any]:
    if origin := get_origin(type_):
        if origin is UnionType:
            yield from itertools.chain.from_iterable(
                map(_unwrap_union, get_args(type_))
            )
    yield type_


def is_forward_ref(value: Any) -> bool:
    return isinstance(value, (str, ForwardRef))


def is_typevar(value: Any) -> bool:
    return isinstance(value, TypeVar)


def evaluate_forward_ref(
    fr: ForwardRef | str, globalns: dict[str, Any], localns: dict[str, Any]
) -> type | None:
    forward_ref = _as_forward_ref(fr)
    if evaluated := forward_ref._evaluate(globalns, localns, frozenset()):
        return evaluated
    return None
