import concurrent
import gc
import sys
import cdi
import pytest
from concurrent.futures import ThreadPoolExecutor
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
    assert scope.get_instance(
        FooChildGeneric[FooChildGeneric[int]]
    ).x is scope.get_instance(FooChildGeneric[int])
    assert scope.get_instance(FooChildGeneric[Foo])

    with pytest.raises(cdi.TypeEvaluationError):
        assert scope.get_instance(FooChildGeneric[float])


def test_scope_nested_typealiases(ctr: cdi.Container, scope: cdi.Scope):
    @cdi.Injectable(ctr)
    class LocalFoo(Generic[T]):
        def __init__(self, a: FooGeneric[T]) -> None:
            self.a = a

    scope.insert_instance(100)
    instance = scope.get_instance(LocalFoo[int])

    assert isinstance(instance.a, FooGeneric)
    assert instance.a.x == 100
    assert instance.a.y == 100
    assert scope.get_instance(FooGeneric[int]) is instance.a


def test_scope_inheritance(scope: cdi.Scope):
    fork = scope.fork()

    parent_instance = fork.get_instance(
        Annotated[
            Foo, cdi.InjectableMetadata(provider_scope=lambda scope: scope.parent)
        ]
    )
    fork_instance = fork.get_instance(Foo)

    assert parent_instance is not fork_instance
    assert parent_instance is scope.get_instance(Foo)


def test_unique_types(ctr: cdi.Container, scope: cdi.Scope):
    @cdi.Injectable(ctr)
    class GetGenericType(Generic[T]):
        def __init__(self, t: type[int], g: type[T]) -> None:
            self.t = t
            self.g = g

    instance = scope.get_instance(GetGenericType[str])
    assert instance.t is int
    assert instance.g is str


def test_transient(scope: cdi.Scope):
    transient = scope.get_instance(cdi.Transient[Foo])

    # it is expected that scope won't have `Foo` to provide
    # since the previously request `Foo` is transient so it should
    # not be provided by the scope
    assert not scope.has_instance(Foo)

    instance = scope.get_instance(Foo)
    assert instance is not transient


def test_unsupported_edge_cases(scope: cdi.Scope):
    with pytest.raises(cdi.TypeEvaluationError):
        scope.get_instance(FooGeneric[T])

    with pytest.raises(cdi.TypeEvaluationError):
        scope.get_instance(FooGeneric)


def test_contextvar(ctr: cdi.Container, scope: cdi.Scope, reraise):
    contextvar = scope.get_instance(cdi.ContextVar)

    with contextvar.limited(foo=10, foo2=20):

        def _job(_):
            with reraise:
                # since we are in a different thread it is expected
                # we will not have context var leakage for those vars
                # which were set on the main thread
                assert contextvar.get("foo") is None
                assert contextvar.get("foo2") is None

                with contextvar.limited(thread_foo=10):
                    pass

        with ThreadPoolExecutor(max_workers=2) as executor:
            executor.map(_job, range(2))

        # this var has been set on a local thread, it is not expected
        # to be also on the main thread context
        assert contextvar.get("thread_foo") is None


def test_contextvar_refcount():
    local_scope = cdi.Scope(__name__, container=cdi.Container())
    contextvar = local_scope.get_instance(cdi.ContextVar)

    obj = object()

    with contextvar.limited(obj=obj):
        assert contextvar.get("obj", obj) is obj

    assert sys.getrefcount(local_scope) == 2
    assert sys.getrefcount(contextvar) == 3

    del local_scope
    gc.collect()

    # after the local scope is dropped by GC, we should not have
    # more references except `contextvar` and `sys.getrefcount`
    assert sys.getrefcount(contextvar) == 2
    del contextvar

    gc.collect()

    # `obj` and `sys.getrefcount`
    assert sys.getrefcount(obj) == 2


def test_contextvar_refcount_with_threads(reraise):
    local_scope = cdi.Scope(__name__, container=cdi.Container())
    contextvar = local_scope.get_instance(cdi.ContextVar)

    obj = object()

    def _job(_):
        nonlocal contextvar
        with reraise:
            assert contextvar.get("obj") is None

    with contextvar.limited(obj=obj):
        with ThreadPoolExecutor(max_workers=2) as pool:
            pool.map(_job, range(2))

    del local_scope
    del contextvar
    gc.collect()

    assert sys.getrefcount(obj) == 2


def test_lifetime(ctr: cdi.Container, scope: cdi.Scope):
    scope.insert_instance("hello")
    instance = scope.get_instance(FooGeneric[str])

    with scope.lifetime() as lifetime:
        assert lifetime.get_instance(FooGeneric[str]) is instance

        lifetime.get_instance(FooGeneric[int])
        assert lifetime.has_instance(FooGeneric[int])

    assert not scope.has_instance(FooGeneric[int])

    with scope.lifetime() as lifetime:

        @cdi.Injectable(ctr)
        class Fake:
            def __init__(self, scope: cdi.Scope) -> None:
                self.scope = scope

        instance = lifetime.get_instance(Fake)

        # the instance that creates the `Fake` class should be `scope`
        # and not `lifetime`
        assert instance.scope is scope


def test_scope_evaluation_policy(ctr: cdi.Container):
    scope = cdi.Scope(
        __name__ + "_evluation_policy",
        container=ctr,
        no_factory_policy=cdi.policy.EvaluateUnknownTypesPolicy(),
    )

    class MyType:
        pass

    class GenericParam(Generic[T]):
        def __init__(self, v: T) -> None:
            self.v = v

    class MyTypeGeneric(Generic[T]):
        def __init__(self, param: GenericParam[T]) -> None:
            self.param = param

    assert not scope.has_instance(MyType)
    assert not scope.has_instance(float)
    assert not scope.has_instance(str)
    assert not scope.container.has_registered(MyType)
    assert not scope.container.has_registered(float)
    assert not scope.container.has_registered(str)

    assert scope.get_instance(MyType) is scope.get_instance(MyType)
    assert scope.get_instance(str) == str()

    assert scope.get_instance(MyTypeGeneric[float])
    assert scope.get_instance(MyTypeGeneric[float]).param.v == 0.0
    assert scope.has_instance(MyType)
