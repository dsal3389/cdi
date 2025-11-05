import enum
from typing import Generic, TypeVar
from collections.abc import Iterable


T = TypeVar("T")
R = TypeVar("R", str, int)


class Base:
    pass


class Foo(Generic[T]):
    pass


class Complex(Generic[T, R]):
    pass


def provider_placehoder() -> None:
    raise NotImplementedError
