"""
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


def _is_typealias(type_: Any) -> bool:
    return get_origin(type_) is not None and len(get_args(type_)) > 0


def _is_fixture_annotation(anno: type[Any]) -> bool:
    return _Fixture in get_args(anno)


def _is_factory_annotation(anno: type[Any]) -> bool:
    return _Factory in get_args(anno)


def _has_typevars(type_: Any) -> bool:
    """
    returns a boolean value indicating if given type has at least 1 typevar instead of concrete types

        T = TypeVar("T")
        R = TypeVar("R")

        class Foo(Generic[T, R]):
            pass

        assert not _has_typevars(Foo)
        assert not _has_typevars(Foo[int, int])
        assert _has_typevars(Foo[int, T])
    """
    for arg in get_args(type_):
        if isinstance(arg, TypeVar):
            return True
    return False


def _get_typevars(type_: Any) -> tuple[TypeVar, ...]:
    """
    returns the typevars that were passed to the type as arguments

        T = TypeVar("T")
        R = TypeVar("R")
        F = TypeVar("F")

        class Foo(Generic[T, R]):
            pass

        assert _get_typevars(Foo[str, str]) == ()
        assert _get_typevars(Foo[T, str]) == (T)
        assert _get_typevars(Foo[str, T]) == (T)
        assert _get_typevars(Foo[T, R]) == (T, R)
        assert _get_typevars(Foo[F, T]) == (F, T)
    """
    if not _is_typealias(type_):
        return ()
    return tuple(filter(lambda arg: isinstance(arg, TypeVar), get_args(type_)))


def _get_generics(type_: Any) -> tuple[TypeVar, ...]:
    """
    if given type expect generics, this function will returns the generics it expects
    without considering what was passed in its arguments

        T = TypeVar("T")
        R = TypeVar("R")
        F = TypeVar("F")

        class Foo(Generic[T, R]):
            pass

        assert _get_generics(Foo[int, str]) == (T, R)
        assert _get_generics(Foo[F, str]) == (T, R)
    """
    for orig_base in getattr(type_, "__orig_bases__", []):
        if _is_typealias(orig_base) and get_origin(orig_base) is Generic:
            return get_args(orig_base)
    return ()


def _is_union(type_: Any) -> bool:
    if _is_typealias(type_):
        type_ = cast(Any, get_origin(type_))
    return type_ is Union or type_ is UnionType


def _get_typevar_variants(typevar: TypeVar) -> tuple[Any, ...]:
    if typevar.__bound__:
        return _unwrap_type(typevar.__bound__)
    return typevar.__constraints__ or (Any,)


def _unwrap_type(type_: Any) -> tuple[Any, ...]:
    """
    unwrap annotation types and generics to their concrete types

        T = TypeVar("T")
        R = TypeVar("R", bound=str | int)

        assert _unwrap_type(str | int) == (str, int)
        assert _unwrap_type(str | int | Annotated[list[str]]) == (str, int, list[str])
        assert _unwrap_type(T) == (Any,)
        assert _unwrap_type(T | R) == (Any, str, int)
    """
    if _is_typealias(type_):
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


class _TypeNode:
    def __init__(self) -> None:
        self._provider: Callable[..., Any] | None = None
        self._implementors: list[Any] = []

    @property
    def provider(self) -> Callable[..., Any] | None:
        return self._provider

    def set_provider(self, provider: Callable[..., None]) -> None:
        self._provider = provider

    def add_implementor(self, subtype: type) -> None:
        """add the given type as an implementor of the current typenode"""
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
        self._entries: dict[type[Any], _TypeNode] = defaultdict(_TypeNode)

    def get_provider(self, type_: type[Any]) -> Callable[..., Any] | None:
        if _is_typealias(type_) and _has_typevars(type_):
            # TODO
            # return self._get_generic_entry(type_)
            raise NotImplementedError

        if type_ in self._entries:
            return self._entries[type_].provider
        return None

    def add_provider(
        self, type_: type[Any] | TypeVar, callable: Callable[..., Any]
    ) -> None:
        if isinstance(type_, TypeVar):
            variants = _unwrap_type(type_)

            if variants == (Any,):
                raise TypeError(
                    f"given typevar `{type_}` for provider `{callable.__name__}` is not bounded or constraint"
                )

            for variant in variants:
                self._add_entry(variant).set_provider(callable)
        else:
            self._add_entry(type_).set_provider(callable)

    def _add_type_provider(
        self, type_: type[Any], callable: Callable[..., Any]
    ) -> None:
        self._add_entry(type_).set_provider(callable)

    def _add_entry(self, type_: type[Any]) -> _TypeNode:
        if type_ in self._entries:
            return self._entries[type_]

        if _is_typealias(type_):
            # if _has_typevars(type_):
            #     return self._add_generic_entry(type_)
            # else:
            return self._add_typealias_entry(type_)
        return self._add_type_entry(type_)

    def _add_type_entry(self, type_: type[Any]) -> _TypeNode:
        """add a concrete type that doesn't take any generics"""
        seen_parents = []

        # although we add a concrete type that doesn't take generics
        # the type_ can inherit from a type that do expect generics, but it will
        # pass it types and not generics (we will see `Foo[int]` but never `Foo[T]`)
        for orig_base in getattr(type_, "__orig_bases__", []):
            if _is_typealias(orig_base) and get_origin(orig_base) is not Generic:
                self._add_entry(orig_base).add_implementor(type_)
                seen_parents.append(get_origin(orig_base))

        self._add_direct_parents(
            type_, mro=type_.__mro__, skip_types=(object, Generic, type_, *seen_parents)
        )
        return self._entries[type_]

    def _add_typealias_entry(self, type_: type[Any]) -> _TypeNode:
        """
        add typealias entry, it is expected that the typ alias
        called when adding a typevar that doesn't take generics in
        its arguments
        """

        origin = cast(type[Any], get_origin(type_))

        # create a mapping between the generics the current typealias expects and
        # to the value that was passed to the type alias
        # Foo[int, str] (Foo[T, R]) -> {"T": int, "R": str}
        typevar_values = {
            g.__name__: v for g, v in zip(_get_generics(origin), get_args(type_))
        }

        # remember the orig base parents `origin` so we won't iterate
        # over them when we iter our `__mro__`
        orig_base_parents = []

        # iterate over the parents that expect generics
        for orig_base in origin.__orig_bases__:
            if not _is_typealias(orig_base) or get_origin(orig_base) is Generic:
                continue

            parent_typevars = []

            for arg in get_args(orig_base):
                if isinstance(arg, TypeVar):
                    # if the parent takes a generic, we need to convert that generic
                    # to a concrete type from our typevar values
                    parent_typevars.append(typevar_values[arg.__name__])
                else:
                    parent_typevars.append(arg)

            parent_origin = get_origin(orig_base)
            orig_base_parents.append(parent_origin)

            # add the current type as an implementor of the parent variant
            self._add_entry(parent_origin[*parent_typevars]).add_implementor(type_)

        self._add_direct_parents(
            type_,
            mro=origin.__mro__,
            skip_types=(origin, Generic, object, *orig_base_parents),
        )
        return self._entries[type_]

    def _add_generic_entry(self, type_: Any) -> _TypeNode:
        origin = cast(type, get_origin(type_))
        generic_variants: list[tuple[Any, ...]] = []

        # unwrap all the generics to their concrete types
        for generic_arg in _get_generics(origin):
            generic_variants.append(_unwrap_type(generic_arg))

        for variant in itertools.product(*generic_variants, repeat=1):
            variant_type = origin[*variant]  # type: ignore

            # add the current type variant as subtype for the direct parents
            self._add_direct_parents(
                variant_type, mro=origin.__mro__, skip_types=(object, Generic, origin)
            )

        # trigger the defaultdict to create an entiry for this type if doesn't exists
        return self._entries[type_]

    def _add_direct_parents(
        self, type_: type[Any], mro: tuple[Any], skip_types: tuple[Any]
    ) -> None:
        """
        adds the given type to the direct parents it inherits from the
        given mro

            class Base: pass
            class Foo(Base): pass
            class Boo(Base): pass
            class Standalone: pass

            class MyClass(Foo, Standalone):
                pass

            # this will find `MyClass` direct parents
            # (Foo, Standalone) and it will not return `Base` because it is not direct parent
            _add_direct_parents(MyClass, mro=MyClass.__mro__, skip_types=(object, MyClass))
        """
        last_cls: type[Any] | None = None
        parents_count = 0

        for cls in reversed(mro):
            if cls in skip_types:
                continue

            if last_cls and not issubclass(cls, last_cls):
                self._add_entry(last_cls).add_implementor(type_)
                parents_count += 1
            last_cls = cls

        # if we have last_cls but we didn't inherit from any parent, it means
        # the current type inherits only from 1 class, so we automatically should
        # add the `last_cls` as the parent of type_
        if last_cls and parents_count == 0:
            self._add_entry(last_cls).add_implementor(type_)
