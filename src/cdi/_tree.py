from __future__ import annotations
from typing import Generic, TypeVar, get_origin, get_args
from collections.abc import Sequence

from ._typing import is_typevar, _get_type_vars

_T = TypeVar("_T")
_V = TypeVar("_V")


class _TypeVar:
    """a type to use in `PrefixTree` that represent some typevar"""


def _standarize_args(args: Sequence[type | TypeVar]) -> tuple[type, ...]:
    standarized = []
    for arg in args:
        if is_typevar(arg):
            standarized.append(_TypeVar)
        else:
            standarized.append(arg)

    # typeignore since the typechecker cannot see that `is_typevar` catches `TypeVar`
    # and replaces them with `_TypeVar`, it thinks the `standarized` list
    # can contain `TypeVar`
    return tuple(standarized)  # type: ignore


def type_as_prefix_steps(type_: type) -> Sequence[type]:
    """
    convert the given type to step of types that can be inserted into `PrefixTree`, the
    steps are generated like so for each possible type

    Foo[int, str, T] -> (Foo, int, str, _TypeVar)
    Foo -> (Foo, _TypeVar, _TypeVar, _TypeVar)
    int -> (int,)
    """
    if origin := get_origin(type_):
        return (origin, *_standarize_args(get_args(type_)))
    elif typevars := _get_type_vars(getattr(type_, "__orig_bases__", ())):
        return (type_, *_standarize_args(typevars))
    else:
        return (type_,)


class PrefixTreeFindStrategyBase(Generic[_T, _V]):
    def find(self, prefix: Sequence[_T], node: PrefixTreeNode[_T, _V]) -> _V | None:
        raise NotImplementedError


class PrefixTreeFindStrategy(Generic[_T, _V], PrefixTreeFindStrategyBase[_T, _V]):
    def find(self, prefix: Sequence[_T], node: PrefixTreeNode[_T, _V]) -> _V | None:
        for step in prefix:
            if child := node._children.get(step):
                node = child
            else:
                return None
        return node._value


class PrefixTreeTypeFindStrategy(PrefixTreeFindStrategyBase[type, _V]):
    """
    this will look up for a matching prefix, but if a type in the path was not found, then
    it will try to look for a typevar, instead of the type
    """

    def find(self, prefix: Sequence[type], node: PrefixTreeNode[type, _V]) -> _V | None:
        for step in prefix:
            if (child := node._children.get(step)) or (
                child := node._children.get(_TypeVar)
            ):
                node = child
            else:
                return None
        return node._value


class PrefixTreeNode(Generic[_T, _V]):
    def __init__(
        self,
        value: _V | None = None,
        children: dict[_T, PrefixTreeNode[_T, _V]] | None = None,
    ) -> None:
        self._value = value
        self._children = children or {}


class PrefixTree(Generic[_T, _V]):
    def __init__(
        self, find_strategy: PrefixTreeFindStrategyBase[_T, _V] | None = None
    ) -> None:
        self._root = PrefixTreeNode()
        self._find_strategy = find_strategy or PrefixTreeFindStrategy()

    def insert(self, prefix: Sequence[_T], value: _V) -> None:
        node = self._root

        for step in prefix:
            if child := node._children.get(step):
                node = child
            else:
                node._children[step] = PrefixTreeNode()
                node = node._children[step]
        node._value = value

    def find(self, prefix: Sequence[_T]) -> _V | None:
        return self._find_strategy.find(prefix, self._root)
