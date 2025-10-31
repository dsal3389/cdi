f"""
no support for unbounded generic


T = TypeVar("T")
R = TypeVar("R", int, str)

class Complex(Generic[T, R])

class Base(Generic[T]):
    pass


class Foo(Base[int]):
    pass


class Boo(Foo):
    pass


<type> -> (<provider> | None, set(<implementors>, ...))

Base[Any] -> (None, set(Base[int]))
Base[int] -> (None, set(Foo))
Foo -> (provider, set(Boo))
Boo -> (None, ())
Complex[Any, int] -> (None, set())
Complex[Any, str] -> (None, set())


# both are the same looks for something that
# implements `Base[int]`
T = TypeVar(bound=Base[int])
cdi.Bound[Base[int]]

# looks for Base int type
Base[int]

cdi.MultiBound[Base[int], Foo]

def func(int_base: cdi.Bounded[Base]) -> None:
    ...

"""

import itertools
from types import UnionType
from typing import Any, TypeVar, Union, Annotated, Generic, cast, get_origin, get_args
from collections.abc import Callable
from collections import defaultdict


T = TypeVar("T")

_Fixture = object()
_Factory = object()

Fixture = Annotated[T, _Fixture]
Factory = Annotated[T, _Factory]


def _is_generic_alias(type_: Any) -> bool:
    return get_origin(type_) is not None and len(get_args(type_)) > 0


def _is_fixture_annotation(anno: type[Any]) -> bool:
    return _Fixture in get_args(anno)


def _is_factory_annotation(anno: type[Any]) -> bool:
    return _Factory in get_args(anno)


def _is_union(type_: Any) -> bool:
    if _is_generic_alias(type_):
        type_ = cast(Any, get_origin(type_))
    return type_ is Union or type_ is UnionType


def _get_typevar_variants(typevar: TypeVar) -> tuple[type[Any], ...]:
    if typevar.__bound__:
        return _unwrap_type(typevar.__bound__)
    return typevar.__constraints__ or (Any,)


def _unwrap_type(type_: Any) -> tuple[type[Any], ...]:
    if _is_generic_alias(type_):
        if _is_union(type_):
            unwraped_map = map(_unwrap_type, get_args(type_))
            return tuple(itertools.chain.from_iterable(unwraped_map))

        origin = get_origin(type_)

        if origin is Annotated:
            anno_type, *_ = get_args(type_)
            return _unwrap_type(anno_type)
        if origin is Generic:
            variants_map = map(_get_typevar_variants, get_args(type_))
            return tuple(itertools.chain.from_iterable(variants_map))

    if isinstance(type_, TypeVar):
        return _get_typevar_variants(type_)
    return (type_,)


class _TypeData:
    def __init__(self) -> None:
        self._provider = None
        self._implementors = []

    def set_provider(self, provider: Callable[..., None]) -> None:
        self._provider = provider

    def add_implementor(self, subtype: type[Any]) -> None:
        if subtype not in self._implementors:
            self._implementors.append(subtype)

    def __repr__(self) -> str:
        return f"_TypeData({self._provider}, {self._implementors})"


class Scope:
    def __init__(self, name: str | None = None) -> None:
        self._name = name
        self._instances = {}

    def get_instance(self, type_: type[Any]) -> Any:
        if get_origin(type_) is Annotated:
            anno_type, *_ = get_args(type_)

            if _is_fixture_annotation(anno_type):
                return self._get_fixture(anno_type)
            else:
                return self._get_factory(anno_type)
        return self._get_factory(type_)

    def _get_factory(self, type_: type[Any]) -> None:
        pass

    def _get_fixture(self, type_: type[Any]) -> Any:
        pass


class Container:
    def __init__(self) -> None:
        self._entries: dict[type[Any], _TypeData] = defaultdict(_TypeData)

    def add_provider(self, type_: type[Any], callable: Callable[..., Any]) -> None:
        if _is_generic_alias(type_):
            if get_origin(type_) is not Annotated:
                self._add_generic_entry(type_).set_provider(callable)
                return

            # if the type is a generic alias but it is annotation, we don't care about
            # the annotation arguments, we only care about the wrapped type
            type_, _ = cast(tuple[type[Any], ...], get_args(type_))
        self._add_type_provider(type_, callable)

    def _add_type_provider(
        self, type_: type[Any], callable: Callable[..., Any]
    ) -> None:
        self._add_entry(type_).set_provider(callable)

    def _add_entry(self, type_: type[Any]) -> _TypeData:
        if type_ in self._entries:
            return self._entries[type_]

        if _is_generic_alias(type_):
            return self._add_generic_entry(type_)
        else:
            return self._add_type_entry(type_)

    def _add_type_entry(self, type_: type[Any]) -> _TypeData:
        origins = []

        breakpoint()
        for orig_base in getattr(type_, "__orig_bases__", []):
            if orig_base in (object, Generic):
                continue

            if _is_generic_alias(orig_base):
                # if we inherit from a generic alias we store origin so later
                # when we iterate `__mro__` we know to skip those classes
                origins.append(get_origin(orig_base))
            self._add_entry(orig_base).add_implementor(type_)

        last_cls: type[Any] | None = None

        for cls in reversed(type_.__mro__):
            if cls in (object, Generic, type_):
                continue

            if last_cls and not isinstance(cls, last_cls):
                if last_cls not in origins:
                    self._add_entry(last_cls).add_implementor(type_)
            last_cls = cls

        if last_cls and last_cls not in origins:
            self._add_entry(last_cls).add_implementor(type_)

        return self._entries[type_]

    def _add_generic_entry(self, type_: type[Any]) -> _TypeData:
        origin = cast(Any, get_origin(type_))
        generics: tuple[type[Any], ...] = []

        __orig_bases__ = cast(tuple[type[Any], ...], origin.__orig_bases__)

        breakpoint()
        for orig_base in __orig_bases__:
            if _is_generic_alias(orig_base) and get_origin(orig_base) is Generic:
                generics = cast(tuple[type[Any]], get_args(orig_base))
            else:
                self._add_entry(orig_base).add_implementor(type_)

        generic_variants = []

        for generic_arg in generics:  #  get_args(type_):
            if not isinstance(generic_arg, TypeVar):
                generic_variants.append((generic_arg,))
                continue

            # try to get the generic bounds or constraints (we don't differ between them), if the generic
            # has no bounds or constraints we use the concrete type `Any`
            variants = generic_arg.__bound__ or generic_arg.__constraints__ or (Any,)
            generic_variants.append(variants)

        for variants in itertools.product(*generic_variants, repeat=1):
            type_ = origin[*variants]
            self._entries[origin].add_implementor(type_)

        # trigger the defaultdict to create an entiry for this type if doesn't exists
        return self._entries[type_]
