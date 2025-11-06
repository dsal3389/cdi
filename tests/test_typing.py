import cdi
import pytest
from typing import Generic, TypeVar, Union, Annotated

from ._common import Base, Foo, Complex, T, R


def test_is_union() -> None:
    assert cdi._typing.is_union(str | int)
    assert cdi._typing.is_union(Union[str, int])

    # check non union types
    assert not cdi._typing.is_union(Base)
    assert not cdi._typing.is_union(str)
    assert not cdi._typing.is_union(Annotated[int, str])
    assert not cdi._typing.is_union(list[int])
    assert not cdi._typing.is_union(list[int | str])


def test_is_typelias() -> None:
    assert cdi._typing.is_typealias(Foo[T])
    assert cdi._typing.is_typealias(Foo[int])
    assert cdi._typing.is_typealias(list[str | int])
    assert cdi._typing.is_typealias(str | int)

    assert not cdi._typing.is_typealias(list)
    assert not cdi._typing.is_typealias(Foo)


def test_get_generics() -> None:
    assert cdi._typing.get_generics(Foo) == (T,)
    assert cdi._typing.get_generics(Complex) == (T, R)

    assert cdi._typing.get_generics(Foo[int]) == (T,)
    assert cdi._typing.get_generics(Complex[T, int]) == (T, R)

    assert cdi._typing.get_generics(Base) == ()
    assert cdi._typing.get_generics(int) == ()
    assert cdi._typing.get_generics(int) == ()


def test_get_typevars() -> None:
    assert cdi._typing.get_typevars(list[int]) == ()
    assert cdi._typing.get_typevars(list[int | str]) == ()
    assert cdi._typing.get_typevars(Base) == ()
    assert cdi._typing.get_typevars(Foo) == ()

    assert cdi._typing.get_typevars(Foo[T]) == (T,)
    assert cdi._typing.get_typevars(Complex[str, R]) == (R,)
    assert cdi._typing.get_typevars(Complex[T, R]) == (T, R)
    assert cdi._typing.get_typevars(list[T]) == (T,)


def test_is_concrete_type() -> None:
    assert cdi._typing.is_concrete_type(int)
    assert cdi._typing.is_concrete_type(int | str)
    assert cdi._typing.is_concrete_type(Foo[int])
    assert cdi._typing.is_concrete_type(Complex[int, str])

    assert not cdi._typing.is_concrete_type(Foo)
    assert not cdi._typing.is_concrete_type(Foo[T])
    assert not cdi._typing.is_concrete_type(Complex[str, R])
