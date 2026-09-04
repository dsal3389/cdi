import cdi
import pytest
from typing import TypeVar, Generic


T = TypeVar("T")
V = TypeVar("V")


@pytest.fixture
def ctr() -> cdi.Container:
    return cdi.Container()


def test_registration(ctr: cdi.Container):
    @cdi.Injectable(ctr)
    class Foo:
        def __init__(self, x: int, y: int) -> None: ...

    @cdi.Injectable(ctr)
    class Foo2:
        pass

    assert (foo_factory := ctr._get_factory(Foo))
    assert (foo2_factory := ctr._get_factory(Foo2))

    assert foo_factory.return_type is Foo
    assert foo2_factory.return_type is Foo2

    assert "x" in foo_factory.parameters
    assert "y" in foo_factory.parameters

    assert tuple(foo2_factory.parameters.keys()) == ()


def test_with_inheritance(ctr: cdi.Container):
    class Parent:
        def __init__(self, name: str, age: int) -> None: ...

    @cdi.Injectable(ctr)
    class Child(Parent):
        def __init__(self, age: float, *args, **kwargs) -> None: ...

    assert (child_factory := ctr._get_factory(Child))
    assert "name" in child_factory.parameters
    assert "age" in child_factory.parameters

    assert child_factory.parameters["name"].annotation is str
    assert child_factory.parameters["age"].annotation is float


def test_with_generics(ctr: cdi.Container):
    ctr = cdi.Container()

    @cdi.Injectable(ctr)
    class Foo(Generic[T, V]):
        def __init__(self, x: T, y: V) -> None: ...

    @cdi.Injectable(ctr)
    def specific() -> Foo[str, str]:
        return Foo("foo", "foo")

    assert (foo_factory := ctr._get_factory(Foo))
    assert foo_factory is ctr._get_factory(Foo[int, str])
    assert foo_factory is ctr._get_factory(Foo[T, str])
    assert foo_factory is not ctr._get_factory(Foo[str, str])

    assert "x" in foo_factory.parameters
    assert "y" in foo_factory.parameters

    assert foo_factory.parameters["x"].annotation is T
    assert foo_factory.parameters["y"].annotation is V


def test_container_has_registered(ctr: cdi.Container):
    @cdi.Injectable(ctr)
    class Foo(Generic[T, V]):
        def __init__(self, x: T, y: V) -> None: ...

    assert ctr.has_registered(Foo[int, str])
    assert ctr.has_registered(Foo)
    assert not ctr.has_registered(int)
    assert not ctr.has_registered(str)
