import enum
from typing import Generic, TypeVar
from collections.abc import Iterable


T = TypeVar("T")
I = TypeVar("I", bound=Iterable[str])


class Base:
    pass


class Foo(Generic[T]):
    pass


class Parent(Base, Generic[T]):
    pass


class Child(Generic[T], Parent[T]):
    pass


class MaleChild(Child[str]):
    pass


def provider_placehoder() -> None:
    raise NotImplementedError
