import cdi
import pytest
from typing import Generic, TypeVar, Annotated


T = TypeVar("T")
V = TypeVar("V")


class Foo:
    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y


class FooChild(Foo):
    pass


class FooGeneric(Generic[T]):
    def __init__(self, x: T, y: T) -> None:
        self.x = x
        self.y = y


class FooChildGeneric(Generic[T], FooGeneric[T]):
    pass


@pytest.fixture
def ctr() -> cdi.Container:
    ctr = cdi.Container()
    cdi.Injectable(ctr).register(100)
    cdi.Injectable(ctr).register(Foo)
    cdi.Injectable(ctr).register(FooChild)
    cdi.Injectable(ctr).register(FooGeneric)
    cdi.Injectable(ctr).register(FooChildGeneric)
    return ctr


@pytest.fixture
def scope(ctr: cdi.Container) -> cdi.Scope:
    return cdi.Scope(__name__, container=ctr)


def test_scope_basic(scope: cdi.Scope):
    assert scope.get_instance(Foo)
    assert scope.get_instance(FooChild)

    assert scope.get_instance(Foo) is scope.get_instance(Foo)
    assert scope.get_instance(FooChild) is scope.get_instance(FooChild)
    assert scope.get_instance(Foo).x


def test_scope_typealiases(ctr: cdi.Container, scope: cdi.Scope):
    @cdi.Injectable(ctr)
    def create_generic_str() -> FooChildGeneric[str]:
        return FooChildGeneric("hello", "world")

    assert scope.get_instance(FooChildGeneric[int])
    assert scope.get_instance(FooChildGeneric[int]).x == 100
    assert scope.get_instance(FooChildGeneric[int]).y == 100
    assert scope.get_instance(FooChildGeneric[str]).x == "hello"
    assert scope.get_instance(FooChildGeneric[str]).y == "world"
    assert scope.get_instance(FooChildGeneric[FooChildGeneric[int]]).x is scope.get_instance(FooChildGeneric[int])
    assert scope.get_instance(FooChildGeneric[Foo])

    with pytest.raises(cdi.TypeEvaluationError):
        assert scope.get_instance(FooChildGeneric[float])


def test_scope_inheritance(scope: cdi.Scope):
    fork = scope.fork()

    parent_instance = fork.get_instance(Annotated[Foo, cdi.InjectableMetadata(provider_scope=lambda scope: scope.parent)])
    fork_instance = fork.get_instance(Foo)

    assert parent_instance is not fork_instance
    assert parent_instance is scope.get_instance(Foo)
