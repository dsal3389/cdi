import itertools
from types import ModuleType, NoneType, UnionType
from typing import (
    Annotated,
    Any,
    ForwardRef,
    Generic,
    TypeVar,
    Union,
    cast,
    get_args,
    get_origin,
)

from ._types import FactoryMarker, FixtureMarker

__all__ = (
    "is_typealias",
    "is_fixture_annotation",
    "is_factory_annotation",
    "is_optional",
    "has_typevars",
    "get_typevars",
    "get_generics",
    "is_concrete_type",
    "is_union",
    "get_typevar_variants",
    "get_typevar_mapping",
    "unwrap_type",
    "all_typealias_variants",
    "calculate_type_metric",
    "forward_ref",
    "evaluate_forward_ref",
)


def is_typealias(type_: Any) -> bool:
    return get_origin(type_) is not None and len(get_args(type_)) > 0


def is_fixture_annotation(anno: type[Any]) -> bool:
    return FixtureMarker in get_args(anno)


def is_factory_annotation(anno: type[Any]) -> bool:
    return FactoryMarker in get_args(anno)


def is_optional(type_: type[Any]) -> bool:
    args = get_args(type_)
    return None in args or NoneType in args


def has_typevars(type_: Any) -> bool:
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


def get_typevars(type_: Any) -> tuple[TypeVar, ...]:
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
        assert _get_typevars(Foo) == ()
    """
    if not is_typealias(type_):
        return ()
    return tuple(filter(lambda arg: isinstance(arg, TypeVar), get_args(type_)))


def get_generics(type_: Any) -> tuple[TypeVar, ...]:
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
        assert _get_generics(Foo) == (T, R)
    """
    if is_typealias(type_):
        type_ = get_origin(type_)

    for orig_base in getattr(type_, "__orig_bases__", []):
        if is_typealias(orig_base) and get_origin(orig_base) is Generic:
            return get_args(orig_base)
    return ()


def get_typevar_mapping(type_: Any) -> dict[str, Any]:
    """
    returns a typevar mapping between the generic name to the typevar value

        T = TypeVar("T")
        R = TypeVar("R")

        class Foo(Generic[T, R]):
            pass

        assert get_typevar_mapping(Foo) == {}
        assert get_typevar_mapping(Foo[int, str]) == {"T": int, "R": str}
    """
    if is_typealias(type_):
        return {g.__name__: v for g, v in zip(get_generics(type_), get_args(type_))}
    return {}


def is_concrete_type(type_: Any) -> bool:
    """
    returns a boolean value indicating if the given type is a concrete type
    or it takes generics
    """
    # if the given type has generics, we check, if its a type alias (if not its not concrete type because it doesn't has args)
    # and we check that it doesn't have typevars in its args
    return (
        (get_generics(type_) == ()) or is_typealias(type_) and not has_typevars(type_)
    )


def is_union(type_: Any) -> bool:
    if is_typealias(type_):
        type_ = cast(Any, get_origin(type_))
    return type_ is Union or type_ is UnionType


def get_typevar_variants(typevar: TypeVar) -> tuple[Any, ...]:
    if typevar.__bound__:
        return unwrap_type(typevar.__bound__)
    if typevar.__constraints__:
        unwraped_map = map(unwrap_type, typevar.__constraints__)
        return tuple(itertools.chain.from_iterable(unwraped_map))
    return (Any,)


def unwrap_type(type_: Any) -> tuple[Any, ...]:
    """
    unwrap annotation types and generics to their concrete types

        T = TypeVar("T")
        R = TypeVar("R", bound=str | int)

        assert _unwrap_type(str | int) == (str, int)
        assert _unwrap_type(str | int | Annotated[list[str]]) == (str, int, list[str])
        assert _unwrap_type(str | int | Annotated[list[str]], group_unions=True) == ((str, int, list[str]),)
        assert _unwrap_type(T) == (Any,)
        assert _unwrap_type(T | R) == (Any, str, int)
    """
    if is_typealias(type_):
        if is_union(type_):
            unwraped_map = map(unwrap_type, get_args(type_))
            return tuple(itertools.chain.from_iterable(unwraped_map))

        origin = get_origin(type_)

        if origin is Annotated:
            anno_type, *_ = get_args(type_)
            return unwrap_type(anno_type)
        elif origin is Generic:
            variants_map = map(get_typevar_variants, get_args(type_))
            return tuple(itertools.chain.from_iterable(variants_map))
        else:
            return all_typealias_variants(type_)

    if isinstance(type_, TypeVar):
        return get_typevar_variants(type_)
    return (type_,)


def all_typealias_variants(type_: Any) -> tuple[Any, ...]:
    """
    returns all the typealias possible variants, this function also
    accept types that have generics but are not typealiases

        T = TypeVar("T")
        R = TypeVar("R", int, str)

        class Foo(Generic[T]): pass

        class Complex(Generic[T, R])

        assert _all_typealias_variants(Foo) == (Foo[Any],)
        assert _all_typealias_variants(Foo[R]) == (Foo[int], Foo[str])
        assert _all_typealias_variants(Complex[str, R]) == (Complex[str, int], Complex[str, str])
        assert _all_typealias_variants(Complex[T, int]) == (Complex[Any, int],)
    """
    origin = get_origin(type_) or type_
    generic_variants: list[tuple[Any, ...]] = []

    if args := get_args(type_):
        for arg in args:
            generic_variants.append(unwrap_type(arg))
    else:
        # unwrap all the generics to their concrete types
        for generic_arg in get_generics(origin):
            generic_variants.append(unwrap_type(generic_arg))

    variants = []
    for variant in itertools.product(*generic_variants, repeat=1):
        variants.append(origin[*variant])  # type: ignore
    return tuple(variants)


def calculate_type_metric(type_: Any) -> int:
    metric = 0

    if is_concrete_type(type_):
        return metric

    if is_typealias(type_):
        for typevar in get_typevars(type_):
            for _ in get_typevar_variants(typevar):
                metric += 5
    else:
        for _ in get_generics(type_):
            metric += 1000
    return metric


def forward_ref(s: str) -> ForwardRef:
    return ForwardRef(s)


def evaluate_forward_ref(fr: ForwardRef, module: ModuleType) -> Any | None:
    return fr._evaluate(module.__dict__, {}, frozenset())
